"""The final evidence gate.

The work order's acceptance is four sentences: a fabricated DOI or source, a
wrong locator, missing evidence and conflicting numbers must all fail. Each has
a test here, and each fails for a *different* reason -- which is the point.
A gate that caught all four for one reason would be catching a symptom.

The gate re-runs the checks rather than reading the log, and most of these
tests are about that. A stored verdict says what was true when it was made; a
report is made later, and ADR-0004 I4 says a record whose source has drifted is
invalidated rather than quietly kept. So the gate asks the source again.

Every case runs against a real migrated store with a real source, a real page
and real anchors. A stubbed ledger would make these assertions statements
about the stub.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import text as sql_text
from sqlalchemy.engine import Connection

from labcairn.db.migrations import upgrade_to_head
from labcairn.db.session import create_db_engine
from labcairn.evidence.checks.c3 import C3_CHECKER_ID
from labcairn.evidence.gate import evaluate_task
from labcairn.evidence.index import LabCairnIndex
from labcairn.evidence.record import EvidenceRecord, VerificationRecord
from labcairn.evidence.states import (
    CheckKind,
    CheckOutcome,
    EvidenceCreator,
    EvidenceKind,
    VerificationStatus,
)
from labcairn.evidence.store import advance, append_record, attest
from labcairn.material.addressing import render_locator_key
from labcairn.sources.locators import CsvLocator, PdfLocator

NOW = dt.datetime(2026, 10, 19, tzinfo=dt.UTC)
SHA = "a" * 64
OTHER_SHA = "b" * 64

Store = tuple[Connection, LabCairnIndex]


@pytest.fixture()
def store(tmp_path: Path) -> Iterator[Store]:
    """A source, a page, two cells, and anchors onto each."""
    target = tmp_path / "gate.db"
    upgrade_to_head(target)
    engine = create_db_engine(target)
    connection = engine.connect()

    page_key = render_locator_key(PdfLocator(page=2))
    cell_key = render_locator_key(CsvLocator(row=2, column="latency_ms"))
    cell2_key = render_locator_key(CsvLocator(row=3, column="latency_ms"))
    with connection.begin():
        connection.execute(
            sql_text(
                "INSERT INTO sources (source_id, owner_id, kind, display_name, relative_path,"
                " content_sha256, size_bytes, readability, readability_disclosure, identifiers,"
                " ingested_at, schema_version)"
                " VALUES ('src-1','local-user','pdf','a.pdf','a.pdf',:sha,1,'readable',NULL,"
                "'[]',:now,1)"
            ),
            {"sha": SHA, "now": NOW},
        )
        for key, page, row_no, body in (
            (page_key, 2, None, "Dijkstra's algorithm is not greedy."),
            (cell_key, None, 2, "3.50"),
            (cell2_key, None, 3, "3.50"),
        ):
            connection.execute(
                sql_text(
                    "INSERT INTO source_texts (source_content_sha256, extraction_version,"
                    " locator_kind, locator_key, page, row_number, column_name, text,"
                    " text_sha256, created_at)"
                    " VALUES (:sha,'v1',:kind,:key,:page,:row,:col,:body,:tsha,:now)"
                ),
                {
                    "sha": SHA,
                    "kind": "pdf" if page is not None else "csv",
                    "key": key,
                    "page": page,
                    "row": row_no,
                    "col": None if page is not None else "latency_ms",
                    "body": body,
                    "tsha": hashlib.sha256(body.encode()).hexdigest(),
                    "now": NOW,
                },
            )
        for anchor_id, key in (
            ("a-page", page_key),
            ("a-cell", cell_key),
            ("a-cell2", cell2_key),
        ):
            connection.execute(
                sql_text(
                    "INSERT INTO source_anchors (anchor_id, source_id, kind, locator_key,"
                    " bound_source_sha256, excerpt_sha256, created_at)"
                    " VALUES (:aid,'src-1','quotation',:key,:sha,NULL,:now)"
                ),
                {"aid": anchor_id, "key": key, "sha": SHA, "now": NOW},
            )
    connection.commit()
    yield connection, LabCairnIndex(connection)
    engine.dispose()


def _claim(
    evidence_id: str,
    *,
    status: str = "extracted",
    anchors: tuple[str, ...] = ("a-page",),
    created_by: str = "rule",
    task_id: str = "task-1",
    span: str = "Dijkstra's algorithm is not greedy.",
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        task_id=task_id,
        kind=EvidenceKind.CLAIM,
        text="A claim about the greedy characterisation.",
        anchor_ids=anchors,
        extracted_span=span,
        extracted_span_sha256=hashlib.sha256(span.encode()).hexdigest(),
        source_content_hash=SHA,
        status=VerificationStatus(status),
        created_by=EvidenceCreator(created_by),
        created_by_id="seed",
        created_at=NOW,
    )


def _numeric(evidence_id: str, value: float, *, task_id: str = "task-1") -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        task_id=task_id,
        kind=EvidenceKind.NUMERIC,
        text=None,
        value=value,
        unit="ms",
        tolerance=0.01,
        anchor_ids=("a-cell",),
        extracted_span=str(value),
        extracted_span_sha256=hashlib.sha256(str(value).encode()).hexdigest(),
        source_content_hash=SHA,
        status=VerificationStatus.EXTRACTED,
        created_by=EvidenceCreator.RULE,
        created_by_id="seed",
        created_at=NOW,
    )


def _verify(connection: Connection, index: LabCairnIndex, evidence_id: str) -> None:
    advance(
        connection,
        evidence_id,
        VerificationStatus.VERIFIED_BY_RULE,
        index=index,
        checks=(CheckKind.C1,),
        checked_at=NOW,
    )


# --------------------------------------------------------------------------- #
# the gate passes
# --------------------------------------------------------------------------- #


def test_a_task_with_one_verified_record_passes(store: Store) -> None:
    connection, index = store
    append_record(connection, _claim("ev-1"))
    _verify(connection, index, "ev-1")

    result = evaluate_task(connection, task_id="task-1", index=index)
    assert result.passed
    assert result.findings == ()
    assert result.citable == ("ev-1",)


def test_a_persons_attestation_is_citable_too(store: Store) -> None:
    """``user_attested`` is a person's word, and a report may cite it.

    A gate that accepted only a rule's pass would make a human's attestation
    uncitable, which is the opposite of what it is for.
    """
    connection, index = store
    append_record(connection, _claim("ev-1", created_by="user"))
    attest(connection, "ev-1", user_id="dr-who", note="I read it.", checked_at=NOW)

    result = evaluate_task(connection, task_id="task-1", index=index)
    assert result.passed
    assert result.citable == ("ev-1",)


def test_a_task_with_no_records_passes(store: Store) -> None:
    """Nothing to check is not a failure, but it is also nothing to cite."""
    connection, index = store
    result = evaluate_task(connection, task_id="task-empty", index=index)
    assert result.passed
    assert result.citable == ()


# --------------------------------------------------------------------------- #
# the four things the work order says must fail
# --------------------------------------------------------------------------- #


def test_a_record_that_was_never_verified_fails(store: Store) -> None:
    """Missing evidence: located, but nothing has confirmed it."""
    connection, index = store
    append_record(connection, _claim("ev-1", status="extracted"))

    result = evaluate_task(connection, task_id="task-1", index=index)
    assert not result.passed
    assert [f.kind for f in result.findings] == ["status"]
    assert result.citable == ()


def test_a_record_with_no_anchor_at_all_fails(store: Store) -> None:
    """A record that cites nothing has nothing behind it."""
    connection, index = store
    record = EvidenceRecord(
        evidence_id="ev-1",
        task_id="task-1",
        kind=EvidenceKind.CLAIM,
        text="A claim with no anchor at all.",
        anchor_ids=(),
        extracted_span=None,
        extracted_span_sha256=None,
        source_content_hash=None,
        status=VerificationStatus.PLANNED,
        created_by=EvidenceCreator.RULE,
        created_by_id="seed",
        created_at=NOW,
    )
    append_record(connection, record)

    result = evaluate_task(connection, task_id="task-1", index=index)
    assert not result.passed
    assert result.findings[0].kind == "status"


def test_a_fabricated_source_fails_the_gate(store: Store) -> None:
    """A12: a source the ledger has never heard of.

    The record claims a rule verified it, and the log says so -- but the anchor
    it names is not in the ledger, so re-running C1 says otherwise. The gate
    trusts the re-run: the log's "pass" is a claim about the past, and the
    source is what the report is about.
    """
    connection, index = store
    # The record cites an anchor id the ledger does not hold. Nothing has to be
    # inserted to make that true: ``evidence_anchors`` has no foreign key to
    # ``source_anchors`` on purpose -- ADR-0004 A12 is C1's job to catch, not
    # the schema's -- so a fabricated id is storable and checkable.
    record = EvidenceRecord(
        evidence_id="ev-1",
        task_id="task-1",
        kind=EvidenceKind.CLAIM,
        text="A claim citing a source nobody ever ingested.",
        anchor_ids=("invented-anchor",),
        extracted_span="Dijkstra's algorithm is not greedy.",
        extracted_span_sha256=hashlib.sha256(b"x").hexdigest(),
        source_content_hash=SHA,
        status=VerificationStatus.VERIFIED_BY_RULE,
        verification_log=(
            VerificationRecord(
                check=CheckKind.C1,
                checker_id="c1.source_exists",
                outcome=CheckOutcome.PASS,
                detail="it looked fine when the rule ran it",
                checked_at=NOW,
            ),
        ),
        created_by=EvidenceCreator.RULE,
        created_by_id="seed",
        created_at=NOW,
    )
    append_record(connection, record)

    result = evaluate_task(connection, task_id="task-1", index=index)
    assert not result.passed
    assert any(finding.kind == "drift" for finding in result.findings)
    assert result.citable == ()


def test_a_source_edited_after_verification_fails_the_gate(store: Store) -> None:
    """A2 and I4: the file moved under the record.

    The record was verified when the source said what it said. Then the source
    changed. Nothing about the record changed -- its log still says the rule
    passed -- and the gate is the only thing that notices, because it asks the
    source again.
    """
    connection, index = store
    append_record(connection, _claim("ev-1"))
    _verify(connection, index, "ev-1")
    assert evaluate_task(connection, task_id="task-1", index=index).passed

    connection.execute(
        sql_text("UPDATE sources SET content_sha256 = :sha WHERE source_id = 'src-1'"),
        {"sha": OTHER_SHA},
    )
    connection.commit()

    result = evaluate_task(connection, task_id="task-1", index=index)
    assert not result.passed
    assert [f.kind for f in result.findings] == ["drift"]
    assert "no longer holds" in result.findings[0].reason


def test_conflicting_numbers_fail_the_gate_and_name_both_records(store: Store) -> None:
    """A5: two records about the same cell, and neither wins.

    The cell says 3.50. One record claims 3.5 and one claims 9.0, so C3 passes
    the first and fails the second. The gate names both, and the sentence must
    not read as though one had been chosen.
    """
    connection, index = store
    append_record(connection, _numeric("ev-a", 3.5))
    append_record(connection, _numeric("ev-b", 9.0))
    advance(
        connection,
        "ev-a",
        VerificationStatus.VERIFIED_BY_RULE,
        index=index,
        checks=(CheckKind.C3,),
        checked_at=NOW,
    )
    advance(
        connection,
        "ev-b",
        VerificationStatus.UNSUPPORTED,
        index=index,
        checks=(CheckKind.C3,),
        checked_at=NOW,
    )

    result = evaluate_task(connection, task_id="task-1", index=index)
    assert not result.passed
    conflicts = [f for f in result.findings if f.kind == "conflict"]
    assert {f.evidence_id for f in conflicts} == {"ev-a", "ev-b"}
    for finding in conflicts:
        assert "neither is preferred" in finding.reason


# --------------------------------------------------------------------------- #
# how the gate refuses
# --------------------------------------------------------------------------- #


def test_every_objection_is_reported_not_just_the_first(store: Store) -> None:
    """A gate that stops at the first failure hides the rest.

    The rest is usually the part that matters: one unverified record and one
    contradicted one are two different problems, and a reader told about only
    one of them will fix that one and find the other next time.
    """
    connection, index = store
    append_record(connection, _claim("ev-1", status="extracted"))
    append_record(connection, _numeric("ev-b", 9.0))
    advance(
        connection,
        "ev-b",
        VerificationStatus.UNSUPPORTED,
        index=index,
        checks=(CheckKind.C3,),
        checked_at=NOW,
    )

    result = evaluate_task(connection, task_id="task-1", index=index)
    assert not result.passed
    assert len(result.findings) >= 2
    assert {f.evidence_id for f in result.findings} == {"ev-1", "ev-b"}
    assert result.considered == ("ev-1", "ev-b")


def test_a_failed_gate_cites_nothing_at_all(store: Store) -> None:
    """A1's "cites nothing", in the form the gate can enforce.

    A partial list of citable ids would invite a caller to cite the ones that
    survived, which is the degradation the gate exists to prevent. The gate
    says no, and says no for all of them.
    """
    connection, index = store
    append_record(connection, _claim("ev-good"))
    _verify(connection, index, "ev-good")
    # A different quoted sentence, because two records in one task cannot share
    # a span hash -- the schema's own constraint, and a reminder that the
    # ledger's "same key" is not the same as the ledger's "same claim".
    append_record(connection, _claim("ev-bad", status="extracted", span="Another sentence."))

    result = evaluate_task(connection, task_id="task-1", index=index)
    assert not result.passed
    assert result.citable == ()
    assert "ev-good" in result.considered


def test_every_finding_carries_a_reason_a_person_can_read(store: Store) -> None:
    """A finding nobody can read is a finding nobody acts on."""
    connection, index = store
    append_record(connection, _claim("ev-1", status="extracted"))

    result = evaluate_task(connection, task_id="task-1", index=index)
    for finding in result.findings:
        assert finding.reason.strip()
        assert len(finding.reason) > 20
        assert finding.evidence_id


def test_the_gate_only_looks_at_its_own_task(store: Store) -> None:
    """Another task's failure is not this report's failure."""
    connection, index = store
    append_record(connection, _claim("ev-other", status="extracted", task_id="task-2"))
    append_record(connection, _claim("ev-mine"))
    _verify(connection, index, "ev-mine")

    result = evaluate_task(connection, task_id="task-1", index=index)
    assert result.passed
    assert result.considered == ("ev-mine",)


def test_the_c3_checker_id_is_the_one_the_catalog_knows() -> None:
    """The gate's re-run and the ledger's log must name the same rule.

    If they did not, a re-run would look like a disagreement with the log every
    time -- and a gate that always finds drift is a gate nobody reads.
    """
    from labcairn.evidence.catalog import is_registered_rule

    assert is_registered_rule(C3_CHECKER_ID)
