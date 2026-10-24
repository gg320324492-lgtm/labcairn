"""C3 — does the number agree with the anchored data?

Two clauses carry this whole check, and both are easy to break in a way that
looks correct:

**An undeclared tolerance is not zero.** ``record.tolerance`` defaults to
``None``, and an implementation that treats ``None`` as ``0.0`` makes every float
whose last digit differs a failure. The opposite error is subtler: treating an
absent tolerance as "close enough" would pass a comparison nobody specified. Both
are tested, and the pair of tests that distinguishes ``None`` from ``0.0`` is the
one that matters -- a record claiming exactly ``3.5`` with no tolerance declared
is not making a precision claim, so C3 cannot answer it.

**The parsed value, not the display string.** A cell stored as ``"3.50"`` and a
record claiming ``3.5`` agree. String equality would call that a conflict.

The corpus has no CSV or XLSX fixture -- the three papers are all PDFs -- so every
case here is written into ``source_texts`` by the fixture. That is stated rather
than glossed: the check is tested against the shapes a spreadsheet cell can have,
but no cell in this repository came from a spreadsheet.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import text as sql_text
from sqlalchemy.engine import Connection

from conftest import migrated_database_from
from labcairn.db.session import create_db_engine
from labcairn.evidence.checks.c3 import C3_CHECKER_ID, check_numeric_consistency, read_number
from labcairn.evidence.cite_support import CiteSupportNotImplementedError
from labcairn.evidence.index import LabCairnIndex
from labcairn.evidence.record import EvidenceRecord
from labcairn.evidence.states import (
    CheckKind,
    CheckOutcome,
    EvidenceCreator,
    EvidenceKind,
    VerificationStatus,
)
from labcairn.material.addressing import render_locator_key
from labcairn.sources.locators import CsvLocator

NOW = dt.datetime(2026, 10, 19, tzinfo=dt.UTC)
SHA = "a" * 64

Cells = tuple[Connection, LabCairnIndex]

#: ``(cell text, value, unit, tolerance, expected outcome)``. The outcomes are
#: written out rather than computed, because a test that derives its expectation
#: from the same helper it is testing proves nothing.
CASES: tuple[tuple[str, float, str, float | None, CheckOutcome], ...] = (
    ("3.50", 3.5, "kg", 0.01, CheckOutcome.PASS),
    ("3.5", 3.5, "kg", 0.0, CheckOutcome.PASS),
    ("3.50001", 3.5, "kg", 0.0, CheckOutcome.FAIL),
    ("4.0", 3.5, "kg", 0.01, CheckOutcome.FAIL),
    ("3.5", 3.5, "kg", None, CheckOutcome.INDETERMINATE),
    ("3.5", 3.5, "kg", 1e-9, CheckOutcome.PASS),
    ("3.5 kg", 3.5, "kg", 0.01, CheckOutcome.PASS),
    ("3.5 KG", 3.5, "kg", 0.01, CheckOutcome.PASS),
    ("3.5 g", 3.5, "kg", 0.01, CheckOutcome.FAIL),
    ("1 kg", 1000.0, "g", 0.01, CheckOutcome.FAIL),
    ("12%", 12.0, "%", 0.01, CheckOutcome.PASS),
    ("12%", 12.0, "percent", 0.01, CheckOutcome.FAIL),
    ("3.5 kilograms", 3.5, "kg", 0.01, CheckOutcome.FAIL),
    ("$3.50", 3.5, "$", 0.01, CheckOutcome.PASS),
    ("not a number", 3.5, "dimensionless", 0.01, CheckOutcome.INDETERMINATE),
    ("1,234", 1234.0, "dimensionless", 0.01, CheckOutcome.INDETERMINATE),
    ("3.5 ms on page 4", 3.5, "ms", 0.01, CheckOutcome.INDETERMINATE),
    ("", 3.5, "dimensionless", 0.01, CheckOutcome.INDETERMINATE),
    ("3.5 4.5", 3.5, "dimensionless", 0.01, CheckOutcome.INDETERMINATE),
)


def _numeric_record(
    value: float, unit: str, tolerance: float | None, anchors: tuple[str, ...] = ("a-cell",)
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id="ev-num",
        task_id="task-1",
        kind=EvidenceKind.NUMERIC,
        text=None,
        value=value,
        unit=unit,
        tolerance=tolerance,
        anchor_ids=anchors,
        extracted_span=str(value),
        extracted_span_sha256=hashlib.sha256(str(value).encode()).hexdigest(),
        status=VerificationStatus.EXTRACTED,
        created_by=EvidenceCreator.RULE,
        created_by_id="seed",
        source_content_hash=SHA,
        created_at=NOW,
    )


@pytest.fixture()
def cells(migrated_database_template: Path, tmp_path: Path) -> Iterator[Cells]:
    """One CSV source with a single cell, rewritten per case by the caller."""
    target = tmp_path / "c3.db"
    migrated_database_from(migrated_database_template, target)
    engine = create_db_engine(target)
    connection = engine.connect()
    key = render_locator_key(CsvLocator(row=2, column="latency_ms"))

    with connection.begin():
        connection.execute(
            sql_text(
                "INSERT INTO sources (source_id, owner_id, kind, display_name, relative_path,"
                " content_sha256, size_bytes, readability, readability_disclosure, identifiers,"
                " ingested_at, schema_version)"
                " VALUES ('src-csv','local-user','csv','data.csv','data.csv',:sha,1,'readable',"
                "NULL,'[]',:now,1)"
            ),
            {"sha": SHA, "now": NOW},
        )
        connection.execute(
            sql_text(
                "INSERT INTO source_texts (source_content_sha256, extraction_version,"
                " locator_kind, locator_key, row_number, column_name, text,"
                " text_sha256, created_at)"
                " VALUES (:sha,'v1','csv',:key,2,'latency_ms',:body,:tsha,:now)"
            ),
            {
                "sha": SHA,
                "key": key,
                "body": "3.50",
                "tsha": hashlib.sha256(b"3.50").hexdigest(),
                "now": NOW,
            },
        )
        connection.execute(
            sql_text(
                "INSERT INTO source_anchors (anchor_id, source_id, kind, locator_key,"
                " bound_source_sha256, excerpt_sha256, created_at)"
                " VALUES ('a-cell','src-csv','numeric',:key,:sha,NULL,:now)"
            ),
            {"key": key, "sha": SHA, "now": NOW},
        )

    yield connection, LabCairnIndex(connection)
    engine.dispose()


def _set_cell(connection: Connection, body: str) -> None:
    connection.execute(
        sql_text(
            "UPDATE source_texts SET text = :body, text_sha256 = :tsha"
            " WHERE locator_kind = 'csv' AND row_number = 2"
        ),
        {"body": body, "tsha": hashlib.sha256(body.encode()).hexdigest()},
    )
    connection.commit()


@pytest.mark.parametrize(("cell", "value", "unit", "tolerance", "expected"), CASES)
def test_each_cell_shape_gives_the_verdict_the_contract_promises(
    cells: Cells,
    cell: str,
    value: float,
    unit: str,
    tolerance: float | None,
    expected: CheckOutcome,
) -> None:
    """Nineteen shapes, each with its outcome written out, not computed."""
    connection, index = cells
    _set_cell(connection, cell)
    verdict = check_numeric_consistency(_numeric_record(value, unit, tolerance), index=index)
    assert verdict.outcome is expected, f"{cell!r} vs {value} {unit} tol={tolerance}"
    assert verdict.check is CheckKind.C3
    assert verdict.checker_id == C3_CHECKER_ID


# --------------------------------------------------------------------------- #
# the tolerance clause
# --------------------------------------------------------------------------- #


def test_absent_tolerance_is_not_zero_tolerance(cells: Cells) -> None:
    """The two cases that look identical and are not.

    ``None`` and ``0.0`` both describe "no slop allowed" to a careless
    implementation. ADR-0004 says an undeclared tolerance is never 0, and the
    distinction is observable: the same cell, the same value, differing only in
    whether a tolerance was written down.
    """
    connection, index = cells
    _set_cell(connection, "3.5")

    undeclared = check_numeric_consistency(_numeric_record(3.5, "kg", None), index=index)
    declared_zero = check_numeric_consistency(_numeric_record(3.5, "kg", 0.0), index=index)

    assert undeclared.outcome is CheckOutcome.INDETERMINATE
    assert declared_zero.outcome is CheckOutcome.PASS
    assert "No tolerance was declared" in undeclared.detail


def test_a_declared_zero_tolerance_requires_exactness(cells: Cells) -> None:
    """Tolerance 0.0 is a decision, not an absence, and it bites."""
    connection, index = cells
    _set_cell(connection, "3.500001")
    verdict = check_numeric_consistency(_numeric_record(3.5, "kg", 0.0), index=index)
    assert verdict.outcome is CheckOutcome.FAIL
    assert "exceeds the declared tolerance" in verdict.detail


def test_a_difference_exactly_equal_to_tolerance_passes(cells: Cells) -> None:
    """The boundary is inclusive, and a half-open reading would fail it.

    "A difference exceeding tolerance" is the contract's wording: equal to the
    tolerance does not exceed it. An implementation using ``<`` instead of ``<=``
    fails here, and fails on the most common real case -- a measurement reported
    at exactly its stated precision.
    """
    connection, index = cells
    _set_cell(connection, "3.51")
    verdict = check_numeric_consistency(_numeric_record(3.5, "kg", 0.01), index=index)
    assert verdict.outcome is CheckOutcome.PASS


# --------------------------------------------------------------------------- #
# units: compared, never converted
# --------------------------------------------------------------------------- #


def test_c3_does_not_convert_units(cells: Cells) -> None:
    """1 kg and 1000 g are the same quantity and a contradiction as records.

    C3 compares unit tokens. If it converted, it would be implementing a unit
    algebra inside a cite-support check, and the arithmetic of that algebra would
    itself need the evidence standard this ledger is built to enforce. Refusing is
    the honest answer: the record says "kg", the source says "g", those are
    different claims about the same number.
    """
    connection, index = cells
    _set_cell(connection, "1 kg")
    verdict = check_numeric_consistency(_numeric_record(1000.0, "g", 0.01), index=index)
    assert verdict.outcome is CheckOutcome.FAIL
    assert "does not convert between units" in verdict.detail


def test_the_known_false_negative_is_visible_in_the_detail(cells: Cells) -> None:
    """``kilograms`` and ``kg`` are one unit spelled two ways, and C3 fails it.

    This is the cost of not building an alias table, and the test exists so the
    cost is stated rather than discovered by a user. A false negative is exactly
    what ADR-0004 R2 warns about -- a strict matcher trains people to switch the
    check off -- so the detail names both tokens and says what C3 did not do,
    leaving the reader able to correct the record instead of guessing why it
    failed.
    """
    connection, index = cells
    _set_cell(connection, "3.5 kilograms")
    verdict = check_numeric_consistency(_numeric_record(3.5, "kg", 0.01), index=index)
    assert verdict.outcome is CheckOutcome.FAIL
    assert "kilograms" in verdict.detail and "kg" in verdict.detail


def test_a_cell_with_no_unit_leaves_the_unit_unverified(cells: Cells) -> None:
    """A bare number in a table says nothing about units, and C3 says so."""
    connection, index = cells
    _set_cell(connection, "3.5")
    verdict = check_numeric_consistency(_numeric_record(3.5, "lightyears", 0.01), index=index)
    assert verdict.outcome is CheckOutcome.PASS
    assert "lightyears" not in verdict.detail


# --------------------------------------------------------------------------- #
# the parsed value, not the display string
# --------------------------------------------------------------------------- #


def test_three_point_five_zero_agrees_with_three_point_five(cells: Cells) -> None:
    """``"3.50"`` and ``3.5`` are the same number.

    The contract calls this out explicitly, and it is the case a string
    comparison would get wrong. ``read_number`` parses before comparing, so the
    trailing zero is not a disagreement.
    """
    assert read_number("3.50").value == 3.5
    connection, index = cells
    _set_cell(connection, "3.50")
    verdict = check_numeric_consistency(_numeric_record(3.5, "dimensionless", 0.0), index=index)
    assert verdict.outcome is CheckOutcome.PASS


def test_editing_the_cell_after_the_record_breaks_the_agreement(cells: Cells) -> None:
    """C3's real value is drift, not arithmetic.

    A record whose number was read from a cell will agree with that cell forever
    unless something changes it. Mutating the stored cell is the only way to test
    that the check is actually re-reading the source rather than echoing the
    record.
    """
    connection, index = cells
    _set_cell(connection, "3.50")
    before = check_numeric_consistency(_numeric_record(3.5, "kg", 0.01), index=index)
    assert before.outcome is CheckOutcome.PASS

    _set_cell(connection, "9.7")
    after = check_numeric_consistency(_numeric_record(3.5, "kg", 0.01), index=index)
    assert after.outcome is CheckOutcome.FAIL
    assert "reads 9.7" in after.detail


# --------------------------------------------------------------------------- #
# the shapes that are not quantities
# --------------------------------------------------------------------------- #


def test_a_thousands_separator_is_refused_not_guessed(cells: Cells) -> None:
    """``1,234`` is 1234 in one locale and 1.234 in another.

    C3 has no locale in scope. Reading it as either would be a confident number
    built on a guess, and a wrong number that looks verified is the failure the
    ledger exists to prevent. ``indeterminate`` names the uncertainty.
    """
    connection, index = cells
    _set_cell(connection, "1,234")
    verdict = check_numeric_consistency(_numeric_record(1234.0, "dimensionless", 0.01), index=index)
    assert verdict.outcome is CheckOutcome.INDETERMINATE


def test_a_claim_record_is_not_a_quantity(cells: Cells) -> None:
    """C3 on a non-numeric record answers "not applicable", not "wrong"."""
    _, index = cells
    claim = EvidenceRecord(
        evidence_id="ev-claim",
        task_id="task-1",
        kind=EvidenceKind.CLAIM,
        text="Dijkstra's algorithm is not greedy.",
        anchor_ids=("a-cell",),
        extracted_span="Dijkstra's algorithm is not greedy.",
        extracted_span_sha256=hashlib.sha256(b"x").hexdigest(),
        status=VerificationStatus.EXTRACTED,
        created_by=EvidenceCreator.RULE,
        created_by_id="seed",
        source_content_hash=SHA,
        created_at=NOW,
    )
    verdict = check_numeric_consistency(claim, index=index)
    assert verdict.outcome is CheckOutcome.INDETERMINATE
    assert "statement rather than a quantity" in verdict.detail


def test_a_non_finite_value_is_indeterminate_not_a_failure(cells: Cells) -> None:
    """NaN compares falsely with everything, so it cannot be a disagreement.

    ``abs(nan - x) <= tolerance`` is ``False`` for every x, which an unguarded
    implementation reports as a failure. There is no fact of the matter to fail
    on: the record carries a value that is not a number in any sense the
    comparison can use.
    """
    _, index = cells
    verdict = check_numeric_consistency(_numeric_record(float("nan"), "kg", 0.01), index=index)
    assert verdict.outcome is CheckOutcome.INDETERMINATE
    assert "not finite" in verdict.detail


# --------------------------------------------------------------------------- #
# anchors and absences
# --------------------------------------------------------------------------- #


def test_an_unregistered_anchor_fails(cells: Cells) -> None:
    _, index = cells
    verdict = check_numeric_consistency(
        _numeric_record(3.5, "kg", 0.01, anchors=("invented",)), index=index
    )
    assert verdict.outcome is CheckOutcome.FAIL
    assert "not registered" in verdict.detail


def test_an_anchor_outside_the_document_fails(cells: Cells) -> None:
    """The number's address does not exist, so there is nothing to re-read."""
    connection, index = cells
    key = render_locator_key(CsvLocator(row=99, column="latency_ms"))
    connection.execute(
        sql_text(
            "INSERT INTO source_anchors (anchor_id, source_id, kind, locator_key,"
            " bound_source_sha256, excerpt_sha256, created_at)"
            " VALUES ('a-missing','src-csv','numeric',:key,:sha,NULL,:now)"
        ),
        {"key": key, "sha": SHA, "now": NOW},
    )
    connection.commit()
    verdict = check_numeric_consistency(
        _numeric_record(3.5, "kg", 0.01, anchors=("a-missing",)), index=index
    )
    assert verdict.outcome is CheckOutcome.FAIL
    assert "no address" in verdict.detail


def test_two_anchors_that_disagree_fail_the_record(cells: Cells) -> None:
    """A record citing two cells holding different numbers cannot be verified.

    Neither cell contradicts the claim on its own if the claim matches one of
    them; together they are the conflict ADR-0004 A5 surfaces rather than
    resolves. C3 reports the disagreement; deciding which number wins is not this
    check's job.
    """
    connection, index = cells
    key2 = render_locator_key(CsvLocator(row=3, column="latency_ms"))
    connection.execute(
        sql_text(
            "INSERT INTO source_texts (source_content_sha256, extraction_version,"
            " locator_kind, locator_key, row_number, column_name, text, text_sha256, created_at)"
            " VALUES (:sha,'v1','csv',:key,3,'latency_ms',:body,:tsha,:now)"
        ),
        {
            "sha": SHA,
            "key": key2,
            "body": "4.0",
            "tsha": hashlib.sha256(b"4.0").hexdigest(),
            "now": NOW,
        },
    )
    connection.execute(
        sql_text(
            "INSERT INTO source_anchors (anchor_id, source_id, kind, locator_key,"
            " bound_source_sha256, excerpt_sha256, created_at)"
            " VALUES ('a-cell2','src-csv','numeric',:key,:sha,NULL,:now)"
        ),
        {"key": key2, "sha": SHA, "now": NOW},
    )
    connection.commit()

    verdict = check_numeric_consistency(
        _numeric_record(3.5, "kg", 0.01, anchors=("a-cell", "a-cell2")), index=index
    )
    assert verdict.outcome is CheckOutcome.FAIL
    assert "1 of 2" in verdict.detail


def test_no_check_raises_the_unimplemented_error_anymore(cells: Cells) -> None:
    """The error class exists and nothing raises it.

    That is a claim about the code, and a claim about code needs a test that
    would fail if it stopped being true. ``CiteSupportNotImplementedError`` is
    still exported because callers were written against it; keeping an
    unreachable exception is a decision, and this is where the decision is
    recorded. If it stays dead through Phase 1, removing it is a contract change
    that should be made on purpose.
    """
    from labcairn.evidence.cite_support import (
        check_numeric_consistency as c3,
    )
    from labcairn.evidence.cite_support import (
        check_quotation_support as c2,
    )
    from labcairn.evidence.cite_support import (
        check_scientific_interpretation as c4,
    )
    from labcairn.evidence.cite_support import (
        check_source_exists as c1,
    )
    from labcairn.evidence.states import IMPLEMENTED_CHECKS

    _, index = cells
    record = _numeric_record(3.5, "kg", 0.01)
    for call in (c1, c2, c3):
        try:
            call(record, index=index)
        except CiteSupportNotImplementedError:
            pytest.fail(f"{call.__name__} still raises CiteSupportNotImplementedError")
    assert c4(record).outcome is CheckOutcome.NOT_CHECKED
    assert frozenset(CheckKind) == IMPLEMENTED_CHECKS
