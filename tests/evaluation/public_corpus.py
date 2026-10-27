"""The public fixture corpus, measured against the product's own reading.

**What this module is for.** ``docs/EVALUATION.md`` asks for fixtures that
carry *"actual source locators, hashes and answer keys"* and forbids *"using
generated outputs as their own oracle"*, and it names *"unsupported-claim
detection and appropriate abstention"* among the metrics it wants reported.
Abstention only shows up where the answer is not, so the corpus has to hold
a question whose honest answer is that the material does not say — and the
corpus that does is ``tests/fixtures/public/``.

A corpus nobody measures against is not evidence, and a harness that reports
a metric as *"not measured"* because *"the tree holds no no-evidence fixture"*
is reporting a falsehood about a tree that holds one. So this module reads
that corpus's answer key and **asks the product** what it makes of the
material beside it.

**The three rules the measurement follows.**

1. **The product answers; the key judges.** Every question in the corpus is
   put to the product's own machinery — its selection code, its operators,
   its quantity reader — and the answer the product gives is the one
   compared with the key. A key the harness only counted would measure
   nothing, and the report would be counting a file.
2. **The key is the judge and the material is the evidence.** The key says
   what the answer is and which addresses it comes from; the material is
   what the product reads. Where they disagree, the disagreement is a
   finding, and it is listed rather than averaged away.
3. **An abstention is an answer, and it is measured like one.** The corpus
   holds a question the material cannot answer. The product is asked for that
   quantity, and its **refusal** is the correct answer — a product that
   produced a number there would be stating something the material does not
   hold, which is the failure the protocol's metric names.

**Where the selection comes from, and why not from the key's prose.** The
key's ``derivation`` field explains each answer in English, and a harness
that parsed English would break the day somebody reworded it. So the
selection is read out of things that are not prose:

* the **column** comes from the question's own citation — a table address
  names its column — and a prose question is answered from the cited line;
* the **rows** are the rows of the table whose id the question's prompt
  names, and every data row when the prompt names none;
* the **quantity an abstention question asks about** is named by the
  question's id, after the fixture's name.

**The limits, stated.** A prose answer is read by a narrow rule: the first
quantity in the cited line that the product's reader will read. A tabular
answer is compared against the product's mean over the selected cells, or
against the value every cell of the selection carries. And this module
measures **the corpus**, not a produced report: what it says is what the
product reads out of the material the corpus ships. Whether a *report*
states the answer, abstains, or invents one is the report path's business,
and the report path is a different measurement.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

from .model import Measurement

#: Where the public fixture corpus lives, relative to the repository root.
PUBLIC_CORPUS_DIR: Final = Path("tests") / "fixtures" / "public"

#: The manifest that carries the corpus's answer key.
MANIFEST_NAME: Final = "MANIFEST.json"

#: The instant the material is ingested at.
#:
#: Fixed, because the measurement must not depend on when it ran: the same
#: tree has to give the same numbers on every day it is measured.
INGESTED_AT: Final = dt.datetime(2026, 10, 25, tzinfo=dt.UTC)

#: The runs of digits in a line that the product's reader may be given.
#:
#: A prose answer is a number in a sentence, and the sentence is not a
#: quantity: the reader refuses a segment that carries more than one number
#: and one token. So the runs are cut out first and the product's reader is
#: asked about each of them.
_NUMBER_RUN: Final = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")

#: The tokens of a prompt, as the subject of a question is looked up.
_PROMPT_TOKEN: Final = re.compile(r"[A-Za-z0-9_-]+")

#: The answer kinds the corpus uses.
_NUMERIC: Final = "numeric"
_NOT_STATED: Final = "not_stated"


@dataclass(frozen=True, slots=True)
class PublicCorpusMeasurement:
    """What the public fixture corpus measured.

    **Every count here names what it counts.** A number whose unit is
    unstated is a number a reader cannot check, and the protocol's whole
    instruction is that denominators be transparent.
    """

    #: The fixtures the corpus holds.
    fixtures: int
    #: The questions the corpus asks.
    questions: int
    #: The questions whose key names a number.
    numeric_questions: int
    #: The numeric questions the product's own reading reproduces.
    numeric_agreed: int
    #: The questions whose key says the material does not state the answer.
    abstention_questions: int
    #: The abstention questions the product answers by abstaining.
    abstentions_honoured: int
    #: What did not match, one line per question.
    failures: tuple[str, ...] = ()

    @property
    def abstention(self) -> Measurement:
        """The abstention measurement.

        **The unit is a question.** The denominator is the corpus's questions
        whose honest answer is an abstention — the only questions over which
        abstention can be measured at all — and the numerator is those the
        product answers by abstaining. A corpus with no such question would
        make the numerator count nothing, which is why the corpus holds one.
        """
        return Measurement(
            status="MEASURED",
            numerator=self.abstentions_honoured,
            denominator=self.abstention_questions,
            how=(
                "the public fixture corpus's questions whose answer key says the "
                "material does not state the answer, over the corpus's questions "
                "that require an abstention — a question is answered correctly "
                "when the product's own machinery refuses to produce a value for "
                "the quantity the question asks about, and when the wrong answers "
                "the key forbids are values the material really holds, so the "
                "abstention is a choice and not a free pass"
            ),
        )

    @property
    def agreement(self) -> Measurement:
        """The agreement measurement.

        **The unit is a question.** The denominator is the corpus's questions
        with a numeric answer, and the numerator is those the product's own
        reading of the material reproduces, within the key's own tolerance.
        """
        return Measurement(
            status="MEASURED",
            numerator=self.numeric_agreed,
            denominator=self.numeric_questions,
            how=(
                "the public fixture corpus's questions with a numeric answer, over "
                "the corpus's numeric questions — a question is answered correctly "
                "when the product's own reading of the material reproduces the "
                "answer key's number, within the key's own tolerance"
            ),
        )


@dataclass(frozen=True, slots=True)
class _Material:
    """One fixture's material, as the product's own ingest path made it."""

    #: The table's source id, empty when the fixture has no table.
    source_id: str
    #: The table's content hash, empty when the fixture has no table.
    content_sha256: str
    #: The table's cells, by (physical row, column header).
    cells: Mapping[tuple[int, str], str]
    #: The table's physical rows, ascending.
    rows: tuple[int, ...]
    #: The column that identifies a row — the table's first column.
    id_column: str
    #: The prose lines, by the rendered address of the line.
    lines: Mapping[str, str]


def _read_manifest(repo_root: Path) -> Mapping[str, Any] | None:
    """The corpus's manifest, or ``None`` when the corpus is not in the tree."""
    path = repo_root / PUBLIC_CORPUS_DIR / MANIFEST_NAME
    if not path.is_file():
        return None
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return None
    return cast(Mapping[str, Any], loaded)


def _ingest_fixture(repo_root: Path, fixture: Mapping[str, Any]) -> _Material:
    """One fixture's material, ingested through the product's ingest path."""
    from labcairn.material.addressing import render_locator_key
    from labcairn.material.ingest import ingest_bytes
    from labcairn.sources.locators import CsvLocator

    cells: dict[tuple[int, str], str] = {}
    lines: dict[str, str] = {}
    source_id = ""
    content_sha256 = ""
    id_column = ""
    for entry in fixture.get("material", []):
        relative = str(entry["path"])
        raw = (repo_root / PUBLIC_CORPUS_DIR / relative).read_bytes()
        ingested = ingest_bytes(
            raw,
            relative_path=relative,
            display_name=Path(relative).name,
            ingested_at=INGESTED_AT,
        )
        for unit in ingested.texts:
            locator = unit.locator
            if isinstance(locator, CsvLocator):
                cells[(locator.row, locator.column)] = unit.text
                if not id_column:
                    id_column = locator.column
                source_id = ingested.source.source_id
                content_sha256 = ingested.source.content_sha256
            else:
                lines[render_locator_key(locator)] = unit.text
    rows = tuple(sorted({row for row, _ in cells}))
    return _Material(
        source_id=source_id,
        content_sha256=content_sha256,
        cells=cells,
        rows=rows,
        id_column=id_column,
        lines=lines,
    )


def _named_rows(material: _Material, prompt: str) -> tuple[int, ...]:
    """The rows of the table a question is about.

    **The rule.** A question names its subject, and the subject is a row's
    id: the rows whose id the question's prompt names, and every data row
    when the prompt names none. The rule is read out of the prompt and the
    table rather than out of the key's prose, so rewording the prose cannot
    change what is measured.
    """
    tokens = set(_PROMPT_TOKEN.findall(prompt))
    named = {
        row
        for (row, column), text in material.cells.items()
        if column == material.id_column and text in tokens
    }
    if named:
        return tuple(sorted(named))
    return material.rows


def _first_quantity(text: str) -> tuple[float, str | None] | None:
    """The first quantity in a line, as the product's reader reads it."""
    from labcairn.sources.quantity import read_number

    for run in _NUMBER_RUN.findall(text):
        reading = read_number(run)
        if reading.value is not None:
            return reading.value, reading.unit
    return None


def _agrees(computed: float, expected: Any, tolerance: Any) -> bool:
    """Whether the product's number is the key's number, within the key's own tolerance."""
    if not isinstance(expected, (int, float)):
        return False
    limit = tolerance if isinstance(tolerance, (int, float)) else 0.0
    return math.isclose(computed, float(expected), rel_tol=0.0, abs_tol=float(limit))


def _tabular_answer(material: _Material, column: str, rows: tuple[int, ...]) -> float | None:
    """The product's own answer over a selection, or ``None`` when it refuses."""
    from labcairn.analysis.operators.descriptive import DescriptiveArgs, mean
    from labcairn.analysis.selection import MissingPolicy, RowSet, Selection

    selection = Selection(
        source_id=material.source_id,
        content_sha256=material.content_sha256,
        columns=(column,),
        rows=RowSet(rows=tuple(rows)),
        missing=MissingPolicy.REFUSE,
    )
    result = mean(DescriptiveArgs(selection=selection), _TableSource(material))
    return result.value


def _agrees_with_the_selection(
    material: _Material, column: str, rows: tuple[int, ...], expected: Any, tolerance: Any
) -> tuple[bool, str]:
    """Whether the key's number is what the product reads over a selection.

    **Two shapes, one rule.** A question may ask for the mean of a column
    over some rows, or for the value a column carries on every row. The
    product's own mean answers the first; the second is the mean too, when
    the rows agree — and the value every cell carries when they do not.
    """
    from labcairn.analysis.selection import (
        MissingPolicy,
        RowSet,
        Selection,
        SelectionRefusedError,
        resolve_selection,
    )
    from labcairn.analysis.units import UnitDisagreementError

    selection = Selection(
        source_id=material.source_id,
        content_sha256=material.content_sha256,
        columns=(column,),
        rows=RowSet(rows=tuple(rows)),
        missing=MissingPolicy.REFUSE,
    )
    source = _TableSource(material)
    try:
        resolved = resolve_selection(selection, source)
    except (SelectionRefusedError, UnitDisagreementError) as refusal:
        return False, f"the product refused the selection: {refusal}"

    computed = _tabular_answer(material, column, rows)
    if computed is None:
        return False, "the product produced no value for the selection"
    if _agrees(computed, expected, tolerance):
        return True, f"the mean over {len(rows)} row(s) is {computed!r}"

    carried = {
        cell.reading.value
        for cell in resolved.cells
        if cell.outcome.name == "VALUE"
        and cell.reading is not None
        and cell.reading.value is not None
    }
    if len(carried) == 1:
        only = carried.pop()
        if _agrees(only, expected, tolerance):
            return True, f"every one of the {len(rows)} row(s) carries {only!r}"
    return False, f"the product reads {computed!r} where the key says {expected!r}"


class _TableSource:
    """The cell source the operators read: the fixture's own ingested cells."""

    def __init__(self, material: _Material) -> None:
        self._material = material

    def text_at(self, address: Any) -> str | None:
        return self._material.cells.get((address.row, address.column))

    def rows(self) -> tuple[int, ...]:
        return self._material.rows

    @property
    def records_blank_cells(self) -> bool:
        """A CSV records a blank cell, so a blank and an absent are different."""
        return True


def _forbidden_values_are_in_the_material(
    material: _Material, question: Mapping[str, Any]
) -> list[str]:
    """The wrong answers the key forbids that the material does not hold.

    A forbidden value that the material does not hold forbids nothing: a
    report that invented it would be inventing it out of the air, which is a
    different failure from reaching for the wrong cell. So the corpus's
    abstention case is only a real test when the material really does offer
    the wrong answers.
    """
    from labcairn.sources.quantity import read_number

    held: set[float] = set()
    for text in material.cells.values():
        reading = read_number(text)
        if reading.value is not None:
            held.add(reading.value)
    missing: list[str] = []
    for check in question.get("expected_artifact_checks", []):
        if check.get("kind") != "no_fabricated_value":
            continue
        value = check.get("value")
        if not isinstance(value, (int, float)):
            continue
        if not any(math.isclose(float(value), other, rel_tol=0.0, abs_tol=1e-12) for other in held):
            missing.append(f"{value!r}")
    return missing


def _quantity_a_question_asks_about(question_id: str, fixture_id: str) -> str:
    """The quantity a question asks about, named by its id.

    The id is a machine key: ``no_evidence.buffer_ph`` names the fixture and
    the quantity. It is the only place the corpus states the quantity in a
    form a machine can read, and reading it here keeps the measurement off
    the key's prose.
    """
    if question_id.startswith(f"{fixture_id}."):
        return question_id[len(fixture_id) + 1 :]
    return question_id


def _the_product_abstains(material: _Material, quantity: str) -> bool:
    """Whether the product refuses to produce a value for a quantity.

    **The refusal is the abstention.** The product's own selection machinery
    is asked for the quantity the question asks about; a material that does
    not carry it has no cell to read, and the product says so rather than
    producing a number. A product that produced one would be stating
    something the material does not hold.
    """
    from labcairn.analysis.selection import (
        MissingPolicy,
        RowSet,
        Selection,
        SelectionRefusedError,
        resolve_selection,
    )
    from labcairn.analysis.units import UnitDisagreementError

    selection = Selection(
        source_id=material.source_id,
        content_sha256=material.content_sha256,
        columns=(quantity,),
        rows=RowSet(rows=tuple(material.rows)),
        missing=MissingPolicy.REFUSE,
    )
    try:
        resolve_selection(selection, _TableSource(material))
    except (SelectionRefusedError, UnitDisagreementError):
        return True
    return False


def measure_public_corpus(repo_root: Path) -> PublicCorpusMeasurement | None:
    """Measure the public fixture corpus, or ``None`` when it is not in the tree."""
    manifest = _read_manifest(repo_root)
    if manifest is None:
        return None
    fixtures = manifest.get("fixtures")
    if not isinstance(fixtures, list):
        return None

    questions = 0
    numeric_questions = 0
    numeric_agreed = 0
    abstention_questions = 0
    abstentions_honoured = 0
    failures: list[str] = []

    for entry in fixtures:
        if not isinstance(entry, dict):
            continue
        fixture = cast(Mapping[str, Any], entry)
        fixture_id = str(fixture.get("id", ""))
        material = _ingest_fixture(repo_root, fixture)
        for raw in fixture.get("questions", []):
            if not isinstance(raw, dict):
                continue
            question = cast(Mapping[str, Any], raw)
            questions += 1
            question_id = str(question.get("id", ""))
            answer = question.get("answer")
            if not isinstance(answer, dict):
                failures.append(f"{question_id}: the question names no answer")
                continue
            kind = str(answer.get("kind", ""))
            expected = answer.get("value")
            tolerance = answer.get("tolerance")

            if kind == _NOT_STATED:
                abstention_questions += 1
                quantity = _quantity_a_question_asks_about(question_id, fixture_id)
                if not _the_product_abstains(material, quantity):
                    failures.append(
                        f"{question_id}: the key says the material does not state "
                        f"{quantity!r}, but the product read a value for it"
                    )
                    continue
                absent = _forbidden_values_are_in_the_material(material, question)
                if absent:
                    failures.append(
                        f"{question_id}: the forbidden value(s) {', '.join(absent)} are "
                        "not in the material, so the abstention would forbid nothing"
                    )
                    continue
                abstentions_honoured += 1
                continue

            if kind != _NUMERIC:
                failures.append(f"{question_id}: the answer kind {kind!r} is not one this reads")
                continue

            numeric_questions += 1
            citations = [
                check
                for check in question.get("expected_artifact_checks", [])
                if check.get("kind") == "citation_resolves"
            ]
            if not citations:
                failures.append(f"{question_id}: the question cites no address")
                continue
            key = str(citations[0].get("locator_key", ""))

            from labcairn.evidence.index import locator_from_key
            from labcairn.sources.locators import CsvLocator, TextLocator

            locator = locator_from_key(key)
            if isinstance(locator, TextLocator):
                text = material.lines.get(key)
                if text is None:
                    failures.append(f"{question_id}: the cited line {key} is not in the material")
                    continue
                found = _first_quantity(text)
                if found is None:
                    failures.append(f"{question_id}: the cited line holds no quantity")
                    continue
                computed, _unit = found
                if _agrees(computed, expected, tolerance):
                    numeric_agreed += 1
                else:
                    failures.append(
                        f"{question_id}: the cited line reads {computed!r} where the key "
                        f"says {expected!r}"
                    )
                continue

            if isinstance(locator, CsvLocator):
                rows = _named_rows(material, str(question.get("prompt", "")))
                agreed, detail = _agrees_with_the_selection(
                    material, locator.column, rows, expected, tolerance
                )
                if agreed:
                    numeric_agreed += 1
                else:
                    failures.append(f"{question_id}: {detail}")
                continue

            failures.append(
                f"{question_id}: the cited address {key} is of a kind this does not read"
            )

    return PublicCorpusMeasurement(
        fixtures=len(fixtures),
        questions=questions,
        numeric_questions=numeric_questions,
        numeric_agreed=numeric_agreed,
        abstention_questions=abstention_questions,
        abstentions_honoured=abstentions_honoured,
        failures=tuple(failures),
    )
