"""The ledger's persistence and its state machine.

Two halves, and the second is the point of the first.

**The round trip.** A store that cannot read back what it wrote makes every
check above it untestable, and the ledger's whole promise is that a record's
status is backed by an audit trail a reader can inspect. So the first test here
is not about a rule; it is that :func:`append_record` and :func:`load_record`
are inverses.

**The state machine.** ADR-0004 Contract 2 is a table of transitions with
preconditions, and every row of it has to be a refusal somewhere. A transition
machine that permits what the table does not list is not enforcing the table.

The cases run against a real migrated store with a real source, a real page of
text and a real anchor. A stubbed store would let a test assert that the
transition code calls the stub, which is a statement about the test.
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
from labcairn.evidence.catalog import RULE_CHECKER_IDS, is_registered_rule
from labcairn.evidence.checks.c1 import C1_CHECKER_ID
from labcairn.evidence.checks.c3 import C3_CHECKER_ID
from labcairn.evidence.index import LabCairnIndex
from labcairn.evidence.record import EvidenceRecord, VerificationRecord
from labcairn.evidence.states import (
    CheckKind,
    CheckOutcome,
    EvidenceCreator,
    EvidenceKind,
    VerificationStatus,
)
from labcairn.evidence.store import (
    LedgerError,
    UnknownRecordError,
    advance,
    append_record,
    append_verification,
    attest,
    detect_conflicts,
    load_record,
    supersede_record,
)
from labcairn.material.addressing import render_locator_key
from labcairn.sources.locators import CsvLocator, PdfLocator

NOW = dt.datetime(2026, 10, 19, tzinfo=dt.UTC)
SHA = "a" * 64
OTHER_SHA = "b" * 64

Store = tuple[Connection, LabCairnIndex]


@pytest.fixture()
def store(tmp_path: Path) -> Iterator[Store]:
    """A store with one readable page and one numeric cell."""
    target = tmp_path / "store.db"
    upgrade_to_head(target)
    engine = create_db_engine(target)
    connection = engine.connect()

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
        page_key = render_locator_key(PdfLocator(page=2))
        cell_key = render_locator_key(CsvLocator(row=2, column="latency_ms"))
        cell2_key = render_locator_key(CsvLocator(row=3, column="latency_ms"))
        for sha, key, page, row_no, body in (
            (SHA, page_key, 2, None, "Dijkstra's algorithm is not greedy."),
            (SHA, cell_key, None, 2, "3.50"),
            # A second cell holding the same number, so a record can cite two
            # cells and still pass C3 -- which is what the primary-anchor rule
            # needs in order to be tested at all.
            (SHA, cell2_key, None, 3, "3.50"),
        ):
            connection.execute(
                sql_text(
                    "INSERT INTO source_texts (source_content_sha256, extraction_version,"
                    " locator_kind, locator_key, page, row_number, column_name, text,"
                    " text_sha256, created_at)"
                    " VALUES (:sha,'v1',:kind,:key,:page,:row,:col,:body,:tsha,:now)"
                ),
                {
                    "sha": sha,
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
        # An anchor at an address with no text behind it: registered, and
        # unresolvable. That is the case a "planned -> extracted" transition has
        # to refuse, and it is not the same as an unregistered anchor.
        missing_key = render_locator_key(PdfLocator(page=99))
        for anchor_id, key in (
            ("a-page", page_key),
            ("a-cell", cell_key),
            ("a-cell2", cell2_key),
            ("a-missing", missing_key),
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


def _must_load(connection: Connection, evidence_id: str) -> EvidenceRecord:
    """The record, or a failure that names it.

    ``load_record`` returns ``None`` for an id it does not hold, and a test
    that dereferences that ``None`` would fail with an AttributeError that
    says nothing about which record went missing.
    """
    record = load_record(connection, evidence_id)
    if record is None:
        raise AssertionError(f"no record with id {evidence_id!r}")
    return record


def _claim(
    evidence_id: str = "ev-1",
    *,
    status: str = "planned",
    anchors: tuple[str, ...] = (),
    created_by: str = "rule",
    task_id: str = "task-1",
    with_span: bool | None = None,
) -> EvidenceRecord:
    """A record, positioned for the transition under test.

    ``with_span`` overrides whether the record carries the quoted span.
    It has to be overridable because Contract 2 makes the span a
    *precondition* of ``planned -> extracted``: the author knows the sentence
    before the locator is verified, so a planned record can carry it.
    """
    located = status != "planned" if with_span is None else with_span
    span = "Dijkstra's algorithm is not greedy." if located else None
    return EvidenceRecord(
        evidence_id=evidence_id,
        task_id=task_id,
        kind=EvidenceKind.CLAIM,
        text="A claim about the greedy characterisation.",
        anchor_ids=anchors,
        extracted_span=span,
        extracted_span_sha256=(
            hashlib.sha256(span.encode()).hexdigest() if span is not None else None
        ),
        source_content_hash=SHA if located else None,
        status=VerificationStatus(status),
        created_by=EvidenceCreator(created_by),
        created_by_id="seed",
        created_at=NOW,
    )


def _numeric(
    evidence_id: str,
    value: float,
    *,
    anchors: tuple[str, ...] = ("a-cell",),
    tolerance: float | None = 0.01,
    task_id: str = "task-1",
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        task_id=task_id,
        kind=EvidenceKind.NUMERIC,
        text=None,
        value=value,
        unit="ms",
        tolerance=tolerance,
        anchor_ids=anchors,
        extracted_span=str(value),
        extracted_span_sha256=hashlib.sha256(str(value).encode()).hexdigest(),
        source_content_hash=SHA,
        status=VerificationStatus.EXTRACTED,
        created_by=EvidenceCreator.RULE,
        created_by_id="seed",
        created_at=NOW,
    )


# --------------------------------------------------------------------------- #
# the round trip
# --------------------------------------------------------------------------- #


def test_a_record_round_trips_through_the_store(store: Store) -> None:
    """What is written is what is read, exactly.

    A store that could not read its own writes back would make every check
    above it untestable -- and the ledger's promise is that a status is backed
    by a trail a reader can inspect.
    """
    connection, _ = store
    record = _claim(status="extracted", anchors=("a-page", "a-cell"))
    append_record(connection, record)
    loaded = load_record(connection, "ev-1")
    assert loaded == record


def test_the_anchors_keep_their_cited_order(store: Store) -> None:
    """Position 0 is the primary address, and order carries meaning.

    A store that sorted the anchors would make the primary anchor a function
    of the alphabet rather than of the citation.
    """
    connection, _ = store
    record = _claim(status="extracted", anchors=("a-cell", "a-page"))
    append_record(connection, record)
    loaded = load_record(connection, "ev-1")
    assert loaded is not None
    assert loaded.anchor_ids == ("a-cell", "a-page")


def test_the_log_entries_keep_a_dense_sequence(store: Store) -> None:
    """The ledger allocates the sequence, not the caller.

    A caller-chosen ``seq`` would let two writers claim the same position, and
    the UNIQUE constraint would refuse the second as a constraint error rather
    than as a duplicate append.
    """
    connection, _ = store
    append_record(connection, _claim(status="extracted", anchors=("a-page",)))
    for detail in ("first", "second"):
        append_verification(
            connection,
            "ev-1",
            VerificationRecord(
                check=CheckKind.C4,
                checker_id="someone",
                outcome=CheckOutcome.NOT_CHECKED,
                detail=detail,
                checked_at=NOW,
            ),
        )
    seqs: list[int] = list(
        connection.execute(
            sql_text("SELECT seq FROM verification_records WHERE evidence_id = 'ev-1' ORDER BY seq")
        ).scalars()
    )
    assert seqs == [1, 2]


def test_the_anchor_key_column_matches_the_join_table(store: Store) -> None:
    """The rendering exists so a CHECK can see the anchors; the two must agree.

    The column is what ``evidence_records_located_past_planned`` reads, and it
    is derived from the join table. If they could drift, the constraint would
    be enforcing a claim the join table contradicts.
    """
    connection, _ = store
    append_record(connection, _claim(status="extracted", anchors=("a-page", "a-cell")))
    stored = connection.execute(
        sql_text("SELECT anchor_key FROM evidence_records WHERE evidence_id = 'ev-1'")
    ).scalar()
    assert stored == '["a-page", "a-cell"]'


# --------------------------------------------------------------------------- #
# the rule catalog
# --------------------------------------------------------------------------- #


def test_the_catalog_holds_the_three_rule_ids() -> None:
    """One spelling of each id, taken from the check modules themselves.

    A frozenset written out here would be a second spelling of a closed set --
    exactly what ADR-0009's canonical key exists to prevent.
    """
    assert (
        frozenset({"c1.source_exists", "c2.quotation_match", "c3.numeric_consistency"})
        == RULE_CHECKER_IDS
    )
    assert is_registered_rule(C1_CHECKER_ID)
    assert is_registered_rule(C3_CHECKER_ID)
    assert not is_registered_rule("a.person")
    assert not is_registered_rule("c4.not_implemented")


def test_a_verified_record_backed_by_an_unregistered_id_is_refused(store: Store) -> None:
    """The model's validator accepts any checker_id, and the store does not.

    The model has to accept a person's id, because an attestation is logged by
    a human. That means it cannot also enforce "the id names a rule this build
    implements" -- and that is the half only the store can check.
    """
    connection, _ = store
    record = EvidenceRecord(
        evidence_id="ev-bad",
        task_id="task-1",
        kind=EvidenceKind.CLAIM,
        text="A claim verified by something that is not a rule.",
        anchor_ids=("a-page",),
        extracted_span="Dijkstra's algorithm is not greedy.",
        extracted_span_sha256=hashlib.sha256(b"x").hexdigest(),
        source_content_hash=SHA,
        status=VerificationStatus.VERIFIED_BY_RULE,
        verification_log=(
            VerificationRecord(
                check=CheckKind.C1,
                checker_id="a.person",
                outcome=CheckOutcome.PASS,
                detail="looks fine to me",
                checked_at=NOW,
            ),
        ),
        created_by=EvidenceCreator.RULE,
        created_by_id="seed",
        created_at=NOW,
    )
    with pytest.raises(LedgerError) as caught:
        append_record(connection, record)
    assert "registered rule catalog" in str(caught.value)


# --------------------------------------------------------------------------- #
# the transition table
# --------------------------------------------------------------------------- #


def test_a_transition_that_is_not_on_the_table_is_refused(store: Store) -> None:
    """Contract 2's table is a list of pairs, and every pair off it is refused.

    ``extracted -> planned`` is the one that matters most: it would be a way to
    un-verify a record without saying so, and nothing else in the ledger would
    notice -- the row would still be well formed, just less true.
    """
    connection, index = store
    append_record(connection, _claim(status="extracted", anchors=("a-page",)))
    with pytest.raises(LedgerError) as caught:
        advance(
            connection,
            "ev-1",
            VerificationStatus.PLANNED,
            index=index,
            checked_at=NOW,
        )
    assert "does not allow" in str(caught.value)
    assert _must_load(connection, "ev-1").status is VerificationStatus.EXTRACTED


def test_verified_by_rule_needs_a_check_that_actually_passed(store: Store) -> None:
    """The passing entry has to exist, not merely be possible.

    A record whose C1 *failed* cannot become ``verified_by_rule`` by asking
    again with no check at all: the precondition is a passing entry in the log,
    and a refusal to run a check is not a passing entry.
    """
    connection, index = store
    append_record(connection, _claim(status="extracted", anchors=("a-page",)))
    connection.execute(
        sql_text("UPDATE sources SET content_sha256 = :sha WHERE source_id = 'src-1'"),
        {"sha": OTHER_SHA},
    )
    connection.commit()
    with pytest.raises(LedgerError) as caught:
        advance(
            connection,
            "ev-1",
            VerificationStatus.VERIFIED_BY_RULE,
            index=index,
            checks=(CheckKind.C1,),
            checked_at=NOW,
        )
    assert "no such entry" in str(caught.value)
    assert _must_load(connection, "ev-1").status is VerificationStatus.EXTRACTED


def test_a_planned_record_cannot_jump_to_verified_by_rule(store: Store) -> None:
    """Contract 2's table is a list of pairs, and a pair not on it is refused."""
    connection, index = store
    append_record(connection, _claim(status="planned"))
    with pytest.raises(LedgerError) as caught:
        advance(
            connection,
            "ev-1",
            VerificationStatus.VERIFIED_BY_RULE,
            index=index,
            checks=(CheckKind.C1,),
            checked_at=NOW,
        )
    assert "does not allow" in str(caught.value)
    assert _must_load(connection, "ev-1").status is VerificationStatus.PLANNED


def test_a_record_with_no_resolving_anchor_cannot_be_extracted(store: Store) -> None:
    """Located nowhere is not located."""
    connection, index = store
    append_record(connection, _claim(status="planned", anchors=("a-missing",), with_span=True))
    with pytest.raises(LedgerError) as caught:
        advance(
            connection,
            "ev-1",
            VerificationStatus.EXTRACTED,
            index=index,
            checked_at=NOW,
        )
    assert "resolving under C1" in str(caught.value)


def test_a_record_with_a_resolving_anchor_becomes_extracted(store: Store) -> None:
    connection, index = store
    append_record(connection, _claim(status="planned", anchors=("a-page",), with_span=True))
    moved = advance(
        connection,
        "ev-1",
        VerificationStatus.EXTRACTED,
        index=index,
        checked_at=NOW,
    )
    assert moved.status is VerificationStatus.EXTRACTED


def test_a_record_becomes_verified_by_rule_after_a_check_passes(store: Store) -> None:
    """The passing entry is produced by running the check, not by asserting one."""
    connection, index = store
    append_record(connection, _claim(status="extracted", anchors=("a-page",)))
    moved = advance(
        connection,
        "ev-1",
        VerificationStatus.VERIFIED_BY_RULE,
        index=index,
        checks=(CheckKind.C1,),
        checked_at=NOW,
    )
    assert moved.status is VerificationStatus.VERIFIED_BY_RULE
    assert any(
        entry.check is CheckKind.C1 and entry.outcome is CheckOutcome.PASS
        for entry in moved.verification_log
    )


def test_a_failing_check_moves_the_record_to_unsupported(store: Store) -> None:
    """A drifted source is a fact, and the record cannot be verified on it."""
    connection, index = store
    append_record(connection, _claim(status="extracted", anchors=("a-page",)))
    connection.execute(
        sql_text("UPDATE sources SET content_sha256 = :sha WHERE source_id = 'src-1'"),
        {"sha": OTHER_SHA},
    )
    connection.commit()
    moved = advance(
        connection,
        "ev-1",
        VerificationStatus.UNSUPPORTED,
        index=index,
        checks=(CheckKind.C1,),
        checked_at=NOW,
    )
    assert moved.status is VerificationStatus.UNSUPPORTED
    assert any(entry.outcome is CheckOutcome.FAIL for entry in moved.verification_log)


def test_the_status_is_not_written_when_the_precondition_fails(store: Store) -> None:
    """The verdict is evidence and stays; the status is the thing that is refused.

    A check's verdict is true whether or not the move it justifies is allowed,
    so it is appended first. The *status* is written last, and only once the
    preconditions are met -- a refused transition leaves the record where it was.
    """
    connection, index = store
    append_record(connection, _claim(status="extracted", anchors=("a-page",)))
    with pytest.raises(LedgerError):
        advance(
            connection,
            "ev-1",
            VerificationStatus.UNSUPPORTED,
            index=index,
            checked_at=NOW,
        )
    record = _must_load(connection, "ev-1")
    assert record.status is VerificationStatus.EXTRACTED


# --------------------------------------------------------------------------- #
# attestation
# --------------------------------------------------------------------------- #


def test_a_user_attestation_is_logged_as_c4_not_checked(store: Store) -> None:
    """C4's only verdict is ``not_checked``, which is what an attestation is.

    "No machine checked this, and a person is standing behind it" -- and the
    checker_id is the person's, so an attestation can never be mistaken for a
    rule's pass.
    """
    connection, _ = store
    append_record(connection, _claim(status="extracted", anchors=("a-page",), created_by="user"))
    moved = attest(connection, "ev-1", user_id="dr-who", note="I read the paper.", checked_at=NOW)
    assert moved.status is VerificationStatus.USER_ATTESTED
    entry = moved.verification_log[-1]
    assert entry.check is CheckKind.C4
    assert entry.outcome is CheckOutcome.NOT_CHECKED
    assert entry.checker_id == "dr-who"
    assert not is_registered_rule(entry.checker_id)


def test_a_rule_written_record_cannot_become_a_persons_attestation(store: Store) -> None:
    """The record's creator does not change when someone else attests to it.

    Rewriting ``created_by`` to ``user`` would erase who actually wrote the
    claim, and the record model refuses the same thing.
    """
    connection, _ = store
    append_record(connection, _claim(status="extracted", anchors=("a-page",), created_by="rule"))
    with pytest.raises(LedgerError) as caught:
        attest(connection, "ev-1", user_id="dr-who", note="I read it.", checked_at=NOW)
    assert "created_by='user'" in str(caught.value)


def test_an_attestation_needs_a_named_person(store: Store) -> None:
    connection, _ = store
    append_record(connection, _claim(status="extracted", anchors=("a-page",), created_by="user"))
    with pytest.raises(LedgerError) as caught:
        attest(connection, "ev-1", user_id="   ", note="I read it.", checked_at=NOW)
    assert "non-empty user identity" in str(caught.value)


# --------------------------------------------------------------------------- #
# conflicts (A5)
# --------------------------------------------------------------------------- #


def test_two_records_about_the_same_cell_with_disagreeing_verdicts_conflict(
    store: Store,
) -> None:
    """One cell cannot hold two different numbers, and neither wins by recency.

    The cell says 3.50. One record claims 3.5 and one claims 4.0, so C3 passes
    the first and fails the second. That disagreement is the conflict A5
    exists to surface -- and it is surfaced on *both*, because the later row
    is not thereby the right one.
    """
    connection, index = store
    append_record(connection, _numeric("ev-a", 3.5))
    append_record(connection, _numeric("ev-b", 4.0))

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

    first = load_record(connection, "ev-a")
    second = load_record(connection, "ev-b")
    assert first is not None and second is not None
    assert detect_conflicts(connection, first) == ("ev-b",)
    assert detect_conflicts(connection, second) == ("ev-a",)


def test_records_merely_sharing_a_background_anchor_do_not_conflict(store: Store) -> None:
    """The primary anchor is the key, not any anchor in common.

    Two records that both mention a background page but whose *primary*
    address differs are not making claims about the same thing, and flagging
    them would make the conflict signal useless.
    """
    connection, index = store
    # Both records cite the same two cells, so C3 reads the same material for
    # each. ev-a claims 3.5, which both cells hold, so it passes; ev-b claims
    # 9.0, which neither holds, so it fails. The verdicts disagree and the
    # only thing separating them from a conflict is *which* anchor is primary.
    append_record(connection, _numeric("ev-a", 3.5, anchors=("a-cell", "a-cell2")))
    append_record(connection, _numeric("ev-b", 9.0, anchors=("a-cell2", "a-cell")))
    # C3 has to run on both, or there are no verdicts to disagree about and
    # the rule is never reached. The verdicts here *do* disagree -- 3.5 passes
    # and 4.0 fails -- so the only thing separating them from a conflict is
    # which anchor is the primary one.
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
    assert detect_conflicts(connection, _must_load(connection, "ev-a")) == ()
    assert detect_conflicts(connection, _must_load(connection, "ev-b")) == ()


def test_a_conflict_needs_disagreeing_verdicts_not_just_two_records(store: Store) -> None:
    """Two records that agree are not in conflict.

    Without this the rule would flag every pair of records about the same cell,
    which is not what "disagree" means.
    """
    connection, index = store
    # Two values that differ but both sit inside the tolerance: the cell says
    # 3.50, so 3.5 and 3.51 both pass C3 and the two records agree.
    append_record(connection, _numeric("ev-a", 3.5))
    append_record(connection, _numeric("ev-b", 3.51))
    for evidence_id in ("ev-a", "ev-b"):
        advance(
            connection,
            evidence_id,
            VerificationStatus.VERIFIED_BY_RULE,
            index=index,
            checks=(CheckKind.C3,),
            checked_at=NOW,
        )
    assert detect_conflicts(connection, _must_load(connection, "ev-a")) == ()


def test_an_indeterminate_verdict_against_a_failure_is_not_a_conflict(
    store: Store,
) -> None:
    """A disagreement about the cell is one pass and one fail.

    ``indeterminate`` against ``fail`` says something else entirely: one record
    had an anchor it could not read -- a prose page alongside the cell -- and
    that is not a dispute about the number. Two records about the same cell
    where one of them could not finish reading are not in conflict, and calling
    them so would bury the real conflicts under noise.
    """
    connection, index = store
    # ev-a cites the cell and a page of prose: C3 can read the cell and cannot
    # read the page, so its verdict is indeterminate.
    append_record(connection, _numeric("ev-a", 3.5, anchors=("a-cell", "a-page")))
    # ev-b cites the same cell and claims a number the cell does not hold.
    append_record(connection, _numeric("ev-b", 9.0, anchors=("a-cell",)))
    # ev-a's C3 verdict is indeterminate, and it is *logged* as such rather
    # than moved: an indeterminate verdict is not a failure, so the record
    # cannot become unsupported on it.
    append_verification(
        connection,
        "ev-a",
        VerificationRecord(
            check=CheckKind.C3,
            checker_id="c3.numeric_consistency",
            outcome=CheckOutcome.INDETERMINATE,
            detail="the page behind the second anchor is prose, not a quantity",
            checked_at=NOW,
        ),
    )
    advance(
        connection,
        "ev-b",
        VerificationStatus.UNSUPPORTED,
        index=index,
        checks=(CheckKind.C3,),
        checked_at=NOW,
    )
    assert detect_conflicts(connection, _must_load(connection, "ev-a")) == ()
    assert detect_conflicts(connection, _must_load(connection, "ev-b")) == ()


def test_a_record_written_with_a_log_gets_sequence_one(store: Store) -> None:
    """The sequence a record is written with is the ledger's, not the caller's.

    ``append_record`` writes a record's log as part of the record, and the
    sequence it allocates has to start at 1 like the one ``append_verification``
    allocates. A record whose log started at 4 would be a log with a hole in it,
    and the hole would be invisible to anyone reading the rows in order.
    """
    connection, _ = store
    record = EvidenceRecord(
        evidence_id="ev-log",
        task_id="task-1",
        kind=EvidenceKind.CLAIM,
        text="A claim written with its first log entry already attached.",
        anchor_ids=("a-page",),
        extracted_span="Dijkstra's algorithm is not greedy.",
        extracted_span_sha256=hashlib.sha256(b"x").hexdigest(),
        source_content_hash=SHA,
        status=VerificationStatus.EXTRACTED,
        verification_log=(
            VerificationRecord(
                check=CheckKind.C1,
                checker_id="c1.source_exists",
                outcome=CheckOutcome.PASS,
                detail="resolved",
                checked_at=NOW,
            ),
        ),
        created_by=EvidenceCreator.RULE,
        created_by_id="seed",
        created_at=NOW,
    )
    append_record(connection, record)
    seqs: list[int] = list(
        connection.execute(
            sql_text(
                "SELECT seq FROM verification_records WHERE evidence_id = 'ev-log' ORDER BY seq"
            )
        ).scalars()
    )
    assert seqs == [1]
    loaded = _must_load(connection, "ev-log")
    assert len(loaded.verification_log) == 1


def test_superseding_keeps_the_old_record_and_marks_it(store: Store) -> None:
    """The old row is kept, not deleted, and says what replaced it.

    A record that was wrong is worth more in the ledger than outside it: its log
    is the evidence of what was claimed and when.
    """
    connection, _ = store
    append_record(connection, _claim("ev-old"))
    replacement = _claim("ev-new")
    updated = supersede_record(connection, "ev-old", replacement)

    assert updated.superseded_by == "ev-new"
    assert _must_load(connection, "ev-old").superseded_by == "ev-new"
    assert _must_load(connection, "ev-new").evidence_id == "ev-new"


def test_a_record_cannot_be_superseded_across_tasks(store: Store) -> None:
    """Otherwise "superseded" would mean nothing a reader could check."""
    connection, _ = store
    append_record(connection, _claim("ev-old"))
    with pytest.raises(LedgerError) as caught:
        supersede_record(connection, "ev-old", _claim("ev-new", task_id="task-2"))
    assert "different piece of work" in str(caught.value)


def test_a_record_is_superseded_once(store: Store) -> None:
    """Replacing the replacement would rewrite history rather than extend it."""
    connection, _ = store
    append_record(connection, _claim("ev-old"))
    supersede_record(connection, "ev-old", _claim("ev-new"))
    with pytest.raises(LedgerError) as caught:
        supersede_record(connection, "ev-old", _claim("ev-third"))
    assert "already superseded" in str(caught.value)


def test_a_record_cannot_supersede_itself(store: Store) -> None:
    connection, _ = store
    append_record(connection, _claim("ev-old"))
    with pytest.raises(LedgerError) as caught:
        supersede_record(connection, "ev-old", _claim("ev-old"))
    assert "cannot supersede itself" in str(caught.value)


def test_the_exit_for_a_rule_written_ambiguous_record(store: Store) -> None:
    """A4's route, end to end.

    A record a rule wrote whose quotation came out ambiguous cannot be verified
    (no check passed) and cannot be attested (Contract 2 wants ``created_by ==
    "user"`` and the record model agrees). Superseding is the way out: a person
    writes their own record, and the rule's is kept and marked. Without it the
    record had nowhere to go at all.
    """
    connection, _index = store
    append_record(connection, _claim("ev-rule"))
    with pytest.raises(LedgerError):
        attest(connection, "ev-rule", user_id="dr-who", note="I read it.", checked_at=NOW)

    supersede_record(
        connection,
        "ev-rule",
        _claim("ev-person", created_by="user", status="extracted", anchors=("a-page",)),
    )
    moved = attest(connection, "ev-person", user_id="dr-who", note="I read it.", checked_at=NOW)
    assert moved.status is VerificationStatus.USER_ATTESTED
    assert _must_load(connection, "ev-rule").superseded_by == "ev-person"


def test_an_unknown_record_is_named_rather_than_returned_as_none(store: Store) -> None:
    """Refusing is the difference between "no such record" and "no answer"."""
    connection, index = store
    with pytest.raises(UnknownRecordError) as caught:
        advance(
            connection,
            "never-existed",
            VerificationStatus.EXTRACTED,
            index=index,
            checked_at=NOW,
        )
    assert "never-existed" in str(caught.value)
