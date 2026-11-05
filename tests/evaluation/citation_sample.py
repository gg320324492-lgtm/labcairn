"""The citation-support sample: the human-checked table the locator metric
is measured over.

**What this table is.** The protocol asks for *"evidence locator validity and
citation support precision (human-checked sample)"*. A machine cannot stand
in for the human reading: whether a report's citation actually supports the
claim it is attached to is judged by a person who reads the material. So the
input this metric runs on is a **table a person wrote** — one row per
citation a produced report makes, saying which report, which record, which
anchor address, and what the reader judged.

**What a row holds, and what it must not.** Five fields:
``sample_id``, ``report``, ``record_id``, ``anchor_id`` and ``verdict``.
The first four locate the citation the way the product locates it — a report
carries records, a record carries anchor ids — and the fifth is the human
judgement, ``supported`` or ``unsupported``. There is **no field for text**:
not the claim, not the material's words, not a reason. This repository is
public and the material it indexes is the owner's unpublished manuscript, so
a table that carried quoted material would leak the manuscript into the tree
the moment it was committed. The loader refuses any row that carries a field
beyond the five, which makes the leak a load-time refusal rather than a
review-time hope.

**Why an empty sample is not a zero rate.** A rate with no rows behind it
would be ``0 / 0`` printed as a number, and the protocol asks for
*denominators* — a denominator of zero states a measurement that was not
made. So an empty sample loads, and the metric built from it is
``NOT_MEASURED`` with the reason on it. The sample arriving at all is the
run's choice: a run that is given no table has not been handed the input the
metric needs, and that is a different reason from an empty table, but both
end at ``NOT MEASURED``.

**Who writes the table, and where it lives.** The human pass over produced
reports is the work order's ``labour``: read the reports, judge each
citation, record the verdict. The table that results carries addresses into
the real corpus, so it lives **outside this public repository** and is
handed to a run with ``--citation-sample``. What this tree carries is the
schema, the loader, the measurement and an empty sample in
``tests/fixtures/retrieval/citation-support-sample.empty.json`` that shows
the shape a filled table must take.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from .model import Measurement

#: The judgement a human reader records for one citation. Two values, and a
#: third — "checked, and the verdict is neither" — does not exist: a reader
#: who cannot decide says so in the row's absence, not in a value this
#: schema refuses to spell.
SUPPORTED: Final = "supported"
UNSUPPORTED: Final = "unsupported"
VERDICTS: Final[tuple[str, ...]] = (SUPPORTED, UNSUPPORTED)

#: The five fields a row carries, and no others. A sixth field is refused —
#: most importantly a field carrying text, which is how a manuscript leaks
#: into a public tree.
ROW_FIELDS: Final[frozenset[str]] = frozenset(
    {"sample_id", "report", "record_id", "anchor_id", "verdict"}
)


class CitationSampleError(ValueError):
    """The sample file the run was handed is not a sample this harness reads.

    The refusal names every row that is wrong and why, because a reader
    fixing a table they have just typed deserves the whole list in one pass
    rather than one error per attempt.
    """


@dataclass(frozen=True, slots=True)
class CitationSampleRow:
    """One citation a produced report makes, and what a human judged it."""

    #: The row's own id, unique within the table.
    sample_id: str
    #: Which produced report the citation is read from.
    report: str
    #: The record of that report the citation is attached to.
    record_id: str
    #: The address the citation points at, as the record carries it.
    anchor_id: str
    #: The human's judgement: ``supported`` or ``unsupported``.
    verdict: str


def load_citation_sample(path: Path) -> tuple[CitationSampleRow, ...]:
    """Read and validate a citation-support sample table.

    Every rule the table must follow is checked, and **all** the failures
    are reported together: a loader that stopped at the first bad row would
    hand back one error per attempt for a table with three problems. An
    empty ``rows`` list is a valid sample — an empty table is a fact about
    the human pass that has not happened yet, and the measurement says what
    that fact means rather than pretending it is a zero rate.
    """
    document = json.loads(path.read_text(encoding="utf-8"))
    problems = _validate_document(document)
    if problems:
        raise CitationSampleError(
            f"{path.name} is not a citation-support sample this harness "
            "reads:\n" + "\n".join(f"- {problem}" for problem in problems)
        )
    assert isinstance(document, dict) and isinstance(document["rows"], list)
    return tuple(
        CitationSampleRow(
            sample_id=row["sample_id"],
            report=row["report"],
            record_id=row["record_id"],
            anchor_id=row["anchor_id"],
            verdict=row["verdict"],
        )
        for row in document["rows"]
    )


def _validate_document(document: Any) -> list[str]:
    """Every way the document fails to be a sample table, as one list."""
    if not isinstance(document, dict):
        return ["the top level is not an object"]
    problems: list[str] = []
    label = document.get("label")
    if not isinstance(label, str) or not label:
        problems.append(
            'the "label" field is missing or empty; it names the '
            "sample — who read what, and when — without quoting it"
        )
    rows = document.get("rows")
    if not isinstance(rows, list):
        problems.append('the "rows" field is missing or is not a list')
        return problems

    seen: set[str] = set()
    for position, row in enumerate(rows):
        where = f"row {position + 1}"
        if not isinstance(row, dict):
            problems.append(f"{where} is not an object")
            continue
        unexpected = sorted(set(row) - ROW_FIELDS)
        if unexpected:
            problems.append(
                f"{where} carries field(s) outside the five a row holds: "
                + ", ".join(f'"{name}"' for name in unexpected)
                + ". A row carries no text: not the claim, not the material's "
                "words, not a reason — a table that carried them would leak "
                "the corpus into this public tree."
            )
        missing = sorted(ROW_FIELDS - set(row))
        if missing:
            problems.append(
                f"{where} is missing field(s): " + ", ".join(f'"{name}"' for name in missing)
            )
            continue
        empty = [name for name in sorted(ROW_FIELDS) if not str(row[name]).strip()]
        if empty:
            problems.append(
                f"{where} holds empty value(s) for: " + ", ".join(f'"{name}"' for name in empty)
            )
        if row["verdict"] not in VERDICTS:
            problems.append(
                f"{where} has a verdict of {row['verdict']!r}; a verdict is "
                f'"supported" or "unsupported"'
            )
        sample_id = str(row["sample_id"])
        if sample_id in seen:
            problems.append(f'{where} repeats sample_id "{sample_id}"')
        seen.add(sample_id)
    return problems


def measure_locator_validity(rows: tuple[CitationSampleRow, ...]) -> Measurement:
    """The locator metric over the human-checked sample.

    The numerator is the citations a human judged ``supported``; the
    denominator is the rows the human judged at all — supported and
    unsupported together, because an unsupported citation is a measurement,
    not a missing one. An empty sample produces ``NOT_MEASURED`` and says
    why: printing ``0 / 0`` would state a measurement that was not made,
    and the protocol asks for the denominator to be named, not for it to be
    zero.
    """
    if not rows:
        return Measurement(
            status="NOT_MEASURED",
            reason=(
                "the citation-support sample holds no rows — the human pass "
                "over the produced reports has not produced a judgement yet, "
                "and a 0/0 rate would state a measurement that was not made"
            ),
        )
    supported = sum(1 for row in rows if row.verdict == SUPPORTED)
    reports = len({row.report for row in rows})
    return Measurement(
        status="MEASURED",
        numerator=supported,
        denominator=len(rows),
        how=(
            "the fraction of the human-checked citation-support sample the "
            "produced reports' citations were judged to be supported; the "
            f"sample holds {len(rows)} citation(s) across {reports} report(s), "
            "judged by a person reading the material"
        ),
    )
