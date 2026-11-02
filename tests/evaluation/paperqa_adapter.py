"""LC-P2-18's competitor adapter: corpus files in, answers out.

**What this module is.** The smallest honest I/O translation between
LabCairn's corpus and paper-qa's document interface. It is *not* the run:
nothing here calls a provider, and nothing here decides what a number
means. It does exactly three things:

* **renders** a corpus fixture into the text paper-qa ingests;
* **asks** the one question the answer key describes, built by a fixed
  template from the key's own structure;
* **captures** paper-qa's output verbatim in an artifact, and scores it
  against the committed key.

**What it may not do.** The brief's rule (``docs/plans/
LC-P2-18-competitor-baseline-brief.md`` §3 and §5 clause 5) is that the
adapter contains **no task logic**: no question rewritten toward an
answer's shape, no repair of the model's text beyond mechanical parsing,
and no retry the product side does not also get. The witnesses in
``tests/test_paperqa_adapter.py`` hold that rule: the question is a
pure function of the key's structure and carries no expected value; the
artifact's answer is the system's text untouched; scoring reads the
answer and the key and nothing else; a system that raises is called
exactly once and recorded.

**The genuinely open translation choice, and the choice made.** An XLSX
is a binary blob; paper-qa is PDF/text-first. The dumbest rendering that
can be parsed is the one chosen: the spreadsheet is read cell by cell
and written as the same comma-separated text its source CSV holds. The
witness asserts the rendering *is* the source CSV, byte for byte, so the
choice introduces no formatting of its own. One honest loss is recorded
rather than hidden: the CSV distinguishes an empty cell (the field is
present and empty) from an absent field (the row is short), and a
textual rendering cannot — ``holes.csv`` and ``holes.xlsx`` render
identically even though the corpus records different cell inventories
for them. paper-qa itself is text-first and cannot see that difference
either, so the loss belongs to the competitor's input format, not to
this translation; the preparation record states it.

**Scoring is deliberately asymmetric, in the direction that flatters the
competitor.** Our side answers a structured selection and is scored cell
by cell. A free-text answer cannot be scored that way by any mechanical
rule, so the competitor's score is a **recall** of the key's expected
statistics over the numbers that appear anywhere in its answer: each
expected value must appear, within the key's tolerance, among the
numbers the answer contains. Extra numbers are not penalised, because
citing values from the table is legitimate and any stricter rule would
be a rule about prose. Recall only can only raise a competitor's score;
the record says so, so a competitor's advantage is never an artifact of
this adapter.

**Refusals are not scored on the competitor side.** The key names some
selections refused (a header unit the data contradicts, two unit tokens
in one selection). Refusal is a semantic judgement of prose, and a
mechanical adapter that claimed to detect it would be inventing a task
rule. So the question lists those selections like any other, and the
score counts only the statistics the key attaches to ``ok`` selections.
"""

from __future__ import annotations

import io
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Final, Mapping

from analysis_fixtures import (
    CORPUS_DIR,
    SPREADSHEET_SOURCES,
    build_spreadsheet_fixtures,
)

__all__ = [
    "CaseScore",
    "STAT_ORDER",
    "STAT_PHRASES",
    "build_artifact",
    "extract_numbers",
    "question_for",
    "render_fixture",
    "run_case",
    "score_artifact",
]

#: The statistics the corpus key carries, in the fixed order the question
#: names them. The order is data, not a convention: it is the order the key
#: writes its statistics in, and a witness checks that every key's keys are
#: a subset of it.
STAT_ORDER: Final[tuple[str, ...]] = (
    "sum",
    "min",
    "max",
    "mean",
    "median",
    "stdev_population",
    "stdev_sample",
)

#: How each key name is said in the question. The table is the only place
#: the two vocabularies meet, exactly as ``corpus.KEY_OUTCOMES`` is for the
#: cell outcomes.
STAT_PHRASES: Final[dict[str, str]] = {
    "sum": "sum",
    "min": "minimum",
    "max": "maximum",
    "mean": "mean",
    "median": "median",
    "stdev_population": "population standard deviation",
    "stdev_sample": "sample standard deviation",
}

#: The one number pattern the scorer uses. It is deliberately plain — no
#: thousands separators, no percentages — because the key's values are
#: plain decimals and a richer pattern would be a claim about prose.
_NUMBER: Final[re.Pattern[str]] = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")

#: A document handed to the system: the fixture's name and its rendered text.
Document = str


def render_fixture(
    fixture: str, *, spreadsheets: Mapping[str, bytes] | None = None
) -> str:
    """The text paper-qa ingests for one corpus fixture.

    A CSV is its own bytes decoded; a spreadsheet is read cell by cell and
    written as the same comma-separated text, so the two formats reach the
    system as the same document. The rendering adds no header, no sheet
    name and no annotation: anything added here would be adapter-authored
    content the product side never sees.
    """
    if fixture in SPREADSHEET_SOURCES:
        data = (spreadsheets or build_spreadsheet_fixtures())[fixture]
        return _render_spreadsheet(data)
    return (CORPUS_DIR / fixture).read_text(encoding="utf-8")


def _render_spreadsheet(data: bytes) -> str:
    """Read a spreadsheet's cells and write them as comma-separated text.

    Every cell is read as text (the corpus writes it as text). ``None`` is
    the empty string, which is what the source CSV holds for an emptied
    cell. Rows are joined with ``\\n`` and the text ends with one, matching
    the CSV writer the fixtures were produced by.
    """
    import openpyxl

    workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        sheet = workbook.worksheets[0]
        lines = [
            ",".join("" if value is None else str(value) for value in row)
            for row in sheet.iter_rows(values_only=True)
        ]
    finally:
        workbook.close()
    return "\n".join(lines) + "\n"


def _rows_phrase(spec: Any) -> str:
    """The key's row address, said in words without interpreting it."""
    if isinstance(spec, str):
        return f"data rows {spec}"
    if isinstance(spec, (list, tuple)):
        return "data rows " + ", ".join(str(row) for row in spec)
    return f"data rows {spec}"


def question_for(expected: Mapping[str, Any]) -> str:
    """The one question a case asks, built from the key's structure.

    The template is fixed and reads only the key's **shape** — selection
    names, row addresses, column names, group keys — never a statistic's
    value. ``tests/test_paperqa_adapter.py`` asserts that no expected
    number appears in the question, which is what keeps the question a
    task definition rather than a hint.
    """
    lines = [
        "The attached document is a table of experimental data.",
        "Compute the following values from the table.",
    ]
    number = 0
    for selection in expected.get("selections", []):
        number += 1
        columns = ", ".join(selection.get("columns", ()))
        asked = "; ".join(STAT_PHRASES[key] for key in STAT_ORDER)
        lines.append(
            f'{number}. For "{selection["name"]}" '
            f"({_rows_phrase(selection.get('rows'))}, columns: {columns}), "
            f"report the {asked}."
        )
    grouped = expected.get("grouped")
    if grouped:
        number += 1
        asked = "; ".join(STAT_PHRASES[key] for key in STAT_ORDER)
        groups = ", ".join(str(group["key"]) for group in grouped.get("groups", ()))
        lines.append(
            f'{number}. Grouped by "{grouped["by"]}": for each group '
            f"({groups}), report the {asked} of the {grouped['of']} column."
        )
    lines.append(
        "If a stated computation cannot be performed on the table as given, "
        "say why instead of inventing a value."
    )
    return "\n".join(lines)


def build_artifact(
    fixture: str,
    question: str,
    answer: str,
    *,
    contexts: tuple[str, ...] = (),
) -> dict[str, Any]:
    """The artifact one case produces, with the answer left untouched.

    No trimming, no normalisation and no extraction happen here: the run's
    artifact is what the system said. Mechanical parsing happens in
    :func:`score_artifact`, after the artifact exists, so a reader can
    re-score the recorded artifact with the committed key.
    """
    return {
        "fixture": fixture,
        "question": question,
        "status": "answered",
        "answer": answer,
        "contexts": list(contexts),
    }


def build_failure(
    fixture: str, question: str, *, stage: str, error: str
) -> dict[str, Any]:
    """The artifact of a case the system could not complete.

    The case is a **reported fact with its reason** (brief §3): it is
    never dropped, and the artifact says which stage stopped it.
    """
    return {
        "fixture": fixture,
        "question": question,
        "status": "failed",
        "answer": None,
        "failure": {"stage": stage, "error": error},
    }


def run_case(
    system: Callable[[str, Document], str],
    fixture: str,
    expected: Mapping[str, Any],
    *,
    spreadsheets: Mapping[str, bytes] | None = None,
) -> dict[str, Any]:
    """Drive one case through the system exactly once.

    ``system`` receives the question and the rendered document and returns
    its answer text. A raise is recorded as this case's failure: the
    adapter does not retry, because a retry the product side does not get
    would spend the competitor's money on a second attempt the comparison
    never granted ours.
    """
    question = question_for(expected)
    document = render_fixture(fixture, spreadsheets=spreadsheets)
    try:
        answer = system(question, document)
    except Exception as error:  # noqa: BLE001 - every failure is a reported case
        return build_failure(
            fixture,
            question,
            stage="system",
            error=f"{type(error).__name__}: {error}",
        )
    return build_artifact(fixture, question, answer)


def extract_numbers(text: str) -> tuple[float, ...]:
    """Every number the text contains, in the order it appears.

    The one parser both sides' artifacts would share. It makes no attempt
    to decide which number *is* a statistic; :func:`score_artifact` only
    asks whether each expected value appears somewhere.
    """
    numbers: list[float] = []
    for match in _NUMBER.finditer(text):
        try:
            numbers.append(float(match.group()))
        except ValueError:  # unreachable for this pattern, kept honest
            continue
    return tuple(numbers)


def _expected_statistics(expected: Mapping[str, Any]) -> tuple[float, ...]:
    """The values the key expects, over the selections it calls ``ok``.

    Refused selections carry no statistics, and grouped statistics are
    expected only where the group's outcome is ``ok``.
    """
    values: list[float] = []
    for selection in expected.get("selections", []):
        outcome = selection.get("expect", {})
        if outcome.get("outcome") != "ok":
            continue
        statistics = outcome.get("statistics") or {}
        values.extend(
            float(statistics[key])
            for key in STAT_ORDER
            if key in statistics and statistics[key] is not None
        )
    grouped = expected.get("grouped")
    if grouped:
        for group in grouped.get("groups", ()):
            if group.get("outcome") != "ok":
                continue
            statistics = group.get("statistics") or {}
            values.extend(
                float(statistics[key])
                for key in STAT_ORDER
                if key in statistics and statistics[key] is not None
            )
    return tuple(values)


@dataclass(frozen=True, slots=True)
class CaseScore:
    """What one case's answer recalled of its key.

    ``expected`` counts the key's expected statistics; ``matched`` counts
    those that appear, within tolerance, among the answer's numbers. The
    score is a recall and says so: extra numbers are not counted against
    the case.
    """

    expected: int
    matched: int

    @property
    def exact(self) -> bool:
        """Every expected value appeared. A case with no expectation is not exact."""
        return self.expected > 0 and self.matched == self.expected


def score_artifact(artifact: Mapping[str, Any], expected: Mapping[str, Any]) -> CaseScore:
    """Score one artifact against the committed key, mechanically.

    **The only inputs are the artifact's answer text and the key.** Not
    the system's name, not the contexts, not the failure reason, not the
    question: a witness builds two artifacts that differ in all of those
    and asserts the score is identical. That is brief §5 clause 5's
    "scoring depends on nothing but the answer keys and the artifacts".
    """
    if artifact.get("status") != "answered":
        return CaseScore(expected=len(_expected_statistics(expected)), matched=0)
    answer = artifact.get("answer")
    if not isinstance(answer, str):
        return CaseScore(expected=len(_expected_statistics(expected)), matched=0)
    tolerance = float(expected.get("tolerance", 0.0))
    numbers = extract_numbers(answer)
    matched = 0
    for value in _expected_statistics(expected):
        if any(math.isclose(value, number, rel_tol=tolerance, abs_tol=tolerance) for number in numbers):
            matched += 1
    return CaseScore(expected=len(_expected_statistics(expected)), matched=matched)


def fixture_path(fixture: str) -> Path:
    """Where a text fixture lives. Spreadsheets are derived and have no path."""
    return CORPUS_DIR / fixture
