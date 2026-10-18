"""C1, run against a real migrated store.

Every case here is built by writing rows into the tables C1 reads --
``sources``, ``source_texts``, ``source_anchors`` -- and then asking C1 what it
concludes. There is no stub index in this file, because a stub index would
make every assertion here a statement about the stub: C1's whole job is to
answer about what the ledger actually holds, and a fake ledger can only prove
that C1 reads the fake ledger the way the test wrote it.

The interesting cases are the ones where an implementation could *look* right.
A check that returns ``pass`` for a record citing nothing is not obviously
wrong until you notice it is the one answer that lets ``verified_by_rule`` be
reached with no evidence behind it. A check that substituted page 3 for page 99
would produce a real address for a false claim, shaped exactly like a citation.
Both are tested, and both are mutation-checked afterwards.

One limit, stated rather than glossed: the ``UNADDRESSABLE`` branch needs a
``source_texts`` row belonging to a source whose ``readability`` is not
``readable``, and LC-P1-08's walk never writes that combination -- a scan
produces no text rows at all, so its anchors resolve to nothing and answer
``UNRESOLVABLE``. The case is exercised by inserting the row directly, which
tests the check honestly but says nothing about whether ingestion can reach it.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text as sql_text
from sqlalchemy.engine import Connection

from labcairn.db.migrations import upgrade_to_head
from labcairn.db.session import create_db_engine
from labcairn.evidence.checks.c1 import C1_CHECKER_ID
from labcairn.evidence.cite_support import (
    CiteSupportNotImplementedError,
    check_numeric_consistency,
    check_quotation_support,
    check_source_exists,
)
from labcairn.evidence.index import LabCairnIndex
from labcairn.evidence.record import EvidenceRecord, VerificationRecord
from labcairn.evidence.states import (
    CheckKind,
    CheckOutcome,
    EvidenceCreator,
    EvidenceKind,
    VerificationStatus,
)
from labcairn.material.addressing import render_locator_key
from labcairn.sources.locators import CsvLocator, PdfLocator

NOW = dt.datetime(2026, 10, 18, tzinfo=dt.UTC)

#: Three distinct hashes, because the three things C1 compares are three
#: different claims and a test that used one value everywhere could not tell
#: them apart.
ORIGINAL = "a" * 64
EDITED = "b" * 64
UNKNOWN = "c" * 64

#: The fixture's shape, named so every test's signature says what it is.
Store = tuple[Connection, LabCairnIndex]


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _insert_source(connection: Connection, source_id: str, sha: str, readability: str) -> None:
    """Write a source row.

    ``readability_disclosure`` is not optional decoration: ``sources`` has a
    CHECK that makes a non-readable state owe a reason and a readable one carry
    none. A test that passed NULL here would be refused by the schema, which is
    the point -- A7's "the reader must know why" is enforced where a report is
    written, not only in a verdict's prose.
    """
    disclosure = None if readability == "readable" else "no extractable text layer"
    connection.execute(
        sql_text(
            "INSERT INTO sources (source_id, owner_id, kind, display_name, relative_path,"
            " content_sha256, size_bytes, readability, readability_disclosure, identifiers,"
            " ingested_at, schema_version)"
            " VALUES (:sid,'local-user','pdf',:name,:rel,:sha,1,:read,:disc,'[]',:now,1)"
        ),
        {
            "sid": source_id,
            "name": f"{source_id}.pdf",
            "rel": f"{source_id}.pdf",
            "sha": sha,
            "read": readability,
            "disc": disclosure,
            "now": NOW,
        },
    )


def _insert_text(connection: Connection, sha: str, locator: Any, body: str) -> None:
    connection.execute(
        sql_text(
            "INSERT INTO source_texts (source_content_sha256, extraction_version,"
            " locator_kind, locator_key, page, row_number, column_name, text, text_sha256,"
            " created_at)"
            " VALUES (:sha,'v1',:kind,:key,:page,:row,:col,:body,:tsha,:now)"
        ),
        {
            "sha": sha,
            "kind": locator.locator_kind.value,
            "key": render_locator_key(locator),
            "page": getattr(locator, "page", None),
            "row": getattr(locator, "row", None),
            "col": getattr(locator, "column", None),
            "body": body,
            "tsha": _sha(body),
            "now": NOW,
        },
    )


def _insert_anchor(
    connection: Connection, anchor_id: str, source_id: str, locator: Any, bound: str
) -> None:
    connection.execute(
        sql_text(
            "INSERT INTO source_anchors (anchor_id, source_id, kind, locator_key,"
            " bound_source_sha256, excerpt_sha256, created_at)"
            " VALUES (:aid,:sid,'quotation',:key,:bound,NULL,:now)"
        ),
        {
            "aid": anchor_id,
            "sid": source_id,
            "key": render_locator_key(locator),
            "bound": bound,
            "now": NOW,
        },
    )


def _record(
    anchor_ids: tuple[str, ...],
    source_hash: str | None = ORIGINAL,
    status: str = "extracted",
) -> EvidenceRecord:
    """A record in the shape a real extraction would produce.

    ``extracted_span`` and its hash are always present, because
    ``EvidenceRecord`` refuses any status past ``planned`` without them (ADR-0004
    Contract 2). C1 does not read them -- C2 does -- so they are filled in
    honestly rather than left null to make the constructor happy.
    """
    span = "Dijkstra's algorithm is not greedy."
    return EvidenceRecord(
        evidence_id="ev-1",
        task_id="task-1",
        kind=EvidenceKind.CLAIM,
        text=span,
        anchor_ids=anchor_ids,
        extracted_span=span,
        extracted_span_sha256=_sha(span),
        status=VerificationStatus(status),
        created_by=EvidenceCreator.RULE,
        created_by_id="seed",
        source_content_hash=source_hash,
        created_at=NOW,
    )


@pytest.fixture()
def store(tmp_path: Path) -> Iterator[tuple[Connection, LabCairnIndex]]:
    """A three-page paper, anchored at page 2, with its text stored.

    Page 2 carries the quoted sentence so a resolving anchor has something real
    to point at; page 1 and page 3 exist too, which is what makes "page 99" a
    failure rather than a typo.
    """
    target = tmp_path / "c1.db"
    upgrade_to_head(target)
    engine = create_db_engine(target)
    connection = engine.connect()
    _insert_source(connection, "src-1", ORIGINAL, "readable")
    for page, body in (
        (1, "Introduction. This paper is about shortest paths."),
        (2, "Dijkstra's algorithm is not greedy."),
        (3, "Results and discussion."),
    ):
        _insert_text(connection, ORIGINAL, PdfLocator(page=page), body)
    _insert_anchor(connection, "anchor-1", "src-1", PdfLocator(page=2), ORIGINAL)
    connection.commit()
    yield connection, LabCairnIndex(connection)
    engine.dispose()


# --------------------------------------------------------------------------- #
# the positive case, and what it actually proves
# --------------------------------------------------------------------------- #


def test_a_resolved_anchor_with_matching_hashes_passes(store: Store) -> None:
    _, index = store
    verdict = check_source_exists(_record(("anchor-1",), source_hash=ORIGINAL), index=index)
    assert verdict.outcome is CheckOutcome.PASS
    assert verdict.check is CheckKind.C1
    assert verdict.checker_id == C1_CHECKER_ID


def test_every_anchor_must_hold_not_just_the_first(store: Store) -> None:
    """Three good anchors pass; adding a bad one does not average out.

    The failure is reported in anchor order, and the count in the detail is what
    tells a reader how much of the record is unsupported.
    """
    connection, index = store
    _insert_anchor(connection, "anchor-2", "src-1", PdfLocator(page=1), ORIGINAL)
    _insert_anchor(connection, "anchor-3", "src-1", PdfLocator(page=3), ORIGINAL)
    connection.commit()
    verdict = check_source_exists(
        _record(("anchor-1", "anchor-2", "anchor-3"), source_hash=ORIGINAL), index=index
    )
    assert verdict.outcome is CheckOutcome.PASS
    assert "3 anchor(s)" in verdict.detail

    # The same record with one anchor pointing outside the document.
    _insert_anchor(connection, "anchor-4", "src-1", PdfLocator(page=99), ORIGINAL)
    connection.commit()
    verdict = check_source_exists(
        _record(("anchor-1", "anchor-2", "anchor-3", "anchor-4"), source_hash=ORIGINAL),
        index=index,
    )
    assert verdict.outcome is CheckOutcome.FAIL
    assert "1 of 4" in verdict.detail


# --------------------------------------------------------------------------- #
# A1 -- an unresolvable locator fails, and cites nothing else
# --------------------------------------------------------------------------- #


def test_page_99_of_a_3_page_document_fails(store: Store) -> None:
    connection, index = store
    _insert_anchor(connection, "far", "src-1", PdfLocator(page=99), ORIGINAL)
    connection.commit()
    verdict = check_source_exists(_record(("far",), source_hash=ORIGINAL), index=index)
    assert verdict.outcome is CheckOutcome.FAIL


def test_the_failure_names_the_bad_address_and_no_other_one(store: Store) -> None:
    """The nearest-page fallback is not in the answer, literally.

    A reader of this verdict must be able to see which address failed and
    nothing else. Asserting that no *other* page number appears in the detail is
    the only way to test "cites nothing" without a report layer: the fallback
    would have to name a substitute page, and there is nowhere to name one.
    """
    connection, index = store
    _insert_anchor(connection, "far", "src-1", PdfLocator(page=99), ORIGINAL)
    connection.commit()
    detail = check_source_exists(_record(("far",), source_hash=ORIGINAL), index=index).detail
    assert "page 99" in detail
    for page in (1, 2, 3, 98, 100):
        assert f"page {page}" not in detail
    assert "nothing is cited in its place" in detail.lower()


def test_a_failing_c1_cannot_lift_a_record_to_verified_by_rule(store: Store) -> None:
    """The consequence of A1, expressed as a state the ledger cannot reach.

    ``EvidenceRecord`` requires a ``pass`` entry from C1-C3 for
    ``verified_by_rule``, so a record carrying only C1's ``fail`` cannot be
    written in that state at all. This is the seam where "the report cites
    nothing" stops being a promise and becomes a construction failure.
    """
    connection, index = store
    _insert_anchor(connection, "far", "src-1", PdfLocator(page=99), ORIGINAL)
    connection.commit()
    verdict = check_source_exists(_record(("far",), source_hash=ORIGINAL), index=index)
    entry = VerificationRecord(
        check=verdict.check,
        checker_id=verdict.checker_id,
        outcome=verdict.outcome,
        detail=verdict.detail,
        checked_at=NOW,
    )
    with pytest.raises(ValueError):
        EvidenceRecord(
            evidence_id="ev-2",
            task_id="task-1",
            kind=EvidenceKind.CLAIM,
            text="A claim about page 99.",
            anchor_ids=("far",),
            extracted_span="whatever",
            extracted_span_sha256=_sha("whatever"),
            status=VerificationStatus.VERIFIED_BY_RULE,
            verification_log=(entry,),
            created_by=EvidenceCreator.RULE,
            created_by_id="seed",
            source_content_hash=ORIGINAL,
            created_at=NOW,
        )
    # The same record is storable as `unsupported`, which is what A1 means.
    unsupported = EvidenceRecord(
        evidence_id="ev-2",
        task_id="task-1",
        kind=EvidenceKind.CLAIM,
        text="A claim about page 99.",
        anchor_ids=("far",),
        extracted_span="whatever",
        extracted_span_sha256=_sha("whatever"),
        status=VerificationStatus.UNSUPPORTED,
        verification_log=(entry,),
        created_by=EvidenceCreator.RULE,
        created_by_id="seed",
        source_content_hash=ORIGINAL,
        created_at=NOW,
    )
    assert unsupported.status is VerificationStatus.UNSUPPORTED


# --------------------------------------------------------------------------- #
# A2 -- the source changed after the anchor was written
# --------------------------------------------------------------------------- #


def test_a_source_edited_after_anchoring_fails(store: Store) -> None:
    connection, index = store
    # The file's bytes move; the anchor keeps the hash it was made against.
    connection.execute(
        sql_text("UPDATE sources SET content_sha256 = :sha WHERE source_id = 'src-1'"),
        {"sha": EDITED},
    )
    connection.commit()
    verdict = check_source_exists(_record(("anchor-1",), source_hash=ORIGINAL), index=index)
    assert verdict.outcome is CheckOutcome.FAIL
    assert "changed after the anchor was made" in verdict.detail


def test_the_drift_is_named_by_both_hashes(store: Store) -> None:
    """A report has to say which bytes were expected and which are present.

    "Hash mismatch" is not actionable. Two 64-character values are, because the
    reader can look at the file and see which one it now hashes to.
    """
    connection, index = store
    connection.execute(
        sql_text("UPDATE sources SET content_sha256 = :sha WHERE source_id = 'src-1'"),
        {"sha": EDITED},
    )
    connection.commit()
    detail = check_source_exists(_record(("anchor-1",), source_hash=ORIGINAL), index=index).detail
    assert ORIGINAL in detail and EDITED in detail


def test_a_record_extracted_from_different_bytes_than_its_source_fails(store: Store) -> None:
    """The record's own hash is checked, not only the anchor's.

    These are different failures and they need different messages. An anchor
    bound to the current bytes with a record extracted from older ones means the
    address is fine and the copy out of it is not.

    This is also why the anchor's hash is checked before the record's. A drifted
    file keeps its old extraction rows under the old hash (ADR-0009), so an
    anchor bound to the old bytes still *resolves* -- the locator is not broken,
    the bytes moved. Reporting that as an unresolvable address would send a
    reader to fix a locator that is working.
    """
    connection, index = store
    _insert_source(connection, "src-2", EDITED, "readable")
    _insert_text(connection, EDITED, PdfLocator(page=2), "Dijkstra's algorithm is not greedy.")
    _insert_anchor(connection, "fresh", "src-2", PdfLocator(page=2), EDITED)
    connection.commit()
    verdict = check_source_exists(_record(("fresh",), source_hash=ORIGINAL), index=index)
    assert verdict.outcome is CheckOutcome.FAIL
    assert "disagree about what was read" in verdict.detail


def test_a_drifted_anchor_still_resolves_before_the_hash_catches_it(store: Store) -> None:
    """The order of the two checks is a decision, and it is observable.

    A re-ingested file keeps its previous extraction rows keyed on the old hash,
    so a stale anchor locates successfully. If C1 reported that as
    ``UNRESOLVABLE`` the reader would chase a broken locator instead of a moved
    file, and the message would be wrong in a way that is invisible to anyone
    reading the report.
    """
    connection, index = store
    connection.execute(
        sql_text("UPDATE sources SET content_sha256 = :sha WHERE source_id = 'src-1'"),
        {"sha": EDITED},
    )
    connection.commit()
    verdict = check_source_exists(_record(("anchor-1",), source_hash=ORIGINAL), index=index)
    assert "not in the ingested material" not in verdict.detail
    assert "changed after the anchor was made" in verdict.detail


def test_c1_reads_the_ledger_and_never_writes_to_it(store: Store) -> None:
    """ADR-0004 I4: a drifted record is invalidated, not silently refreshed.

    The only way to make a drifted anchor pass is to change what is stored, so
    the claim worth testing is that C1 touches nothing. Snapshotting every hash
    in the ledger and comparing it after the call is falsifiable in the way
    "the record object is unchanged" is not: a check that updated the source row
    or rewrote the anchor would pass an immutability test on the Pydantic model
    and fail this one.
    """
    connection, index = store
    connection.execute(
        sql_text("UPDATE sources SET content_sha256 = :sha WHERE source_id = 'src-1'"),
        {"sha": EDITED},
    )
    connection.commit()
    before = {
        table: connection.execute(sql_text(f"SELECT COUNT(*) FROM {table}")).scalar()
        for table in ("sources", "source_texts", "source_anchors")
    }
    hashes = connection.execute(
        sql_text(
            "SELECT s.content_sha256, a.bound_source_sha256 FROM sources AS s"
            " JOIN source_anchors AS a ON a.source_id = s.source_id"
        )
    ).fetchall()

    verdict = check_source_exists(_record(("anchor-1",), source_hash=ORIGINAL), index=index)
    assert verdict.outcome is CheckOutcome.FAIL

    after = {
        table: connection.execute(sql_text(f"SELECT COUNT(*) FROM {table}")).scalar()
        for table in ("sources", "source_texts", "source_anchors")
    }
    now = connection.execute(
        sql_text(
            "SELECT s.content_sha256, a.bound_source_sha256 FROM sources AS s"
            " JOIN source_anchors AS a ON a.source_id = s.source_id"
        )
    ).fetchall()
    assert before == after
    assert list(hashes) == list(now)


def test_a_located_anchor_holding_no_text_still_resolves(store: Store) -> None:
    """C1 answers about addresses, not about content.

    A page whose extracted text is empty is a real address, and C1 says so.
    Whether anything supports a quotation is C2's question; collapsing the two
    would let an empty page silence a claim that belongs to a check that has not
    run yet.
    """
    connection, index = store
    _insert_text(connection, ORIGINAL, PdfLocator(page=4), "")
    _insert_anchor(connection, "blank", "src-1", PdfLocator(page=4), ORIGINAL)
    connection.commit()
    verdict = check_source_exists(_record(("blank",), source_hash=ORIGINAL), index=index)
    assert verdict.outcome is CheckOutcome.PASS


# --------------------------------------------------------------------------- #
# A12 -- the fabricated source
# --------------------------------------------------------------------------- #


def test_an_anchor_id_that_does_not_exist_fails(store: Store) -> None:
    _, index = store
    verdict = check_source_exists(_record(("invented",), source_hash=ORIGINAL), index=index)
    assert verdict.outcome is CheckOutcome.FAIL
    assert "never made" in verdict.detail


def test_an_anchor_naming_a_source_with_no_row_fails(store: Store) -> None:
    """The anchor exists; the source behind it does not.

    Distinguishable from the case above in the detail, because the repair is
    different: one is a record pointing at nothing, the other is a ledger whose
    source row went missing.
    """
    connection, index = store
    _insert_anchor(connection, "orphan", "src-gone", PdfLocator(page=2), ORIGINAL)
    connection.commit()
    detail = check_source_exists(_record(("orphan",), source_hash=ORIGINAL), index=index).detail
    assert "not in the ledger" in detail
    assert "no anchor with that id" not in detail


# --------------------------------------------------------------------------- #
# A7 -- present but unreadable
# --------------------------------------------------------------------------- #


def test_a_source_that_cannot_be_read_is_indeterminate_not_fail(store: Store) -> None:
    """The claim may be true of a document nobody has been able to open.

    ``fail`` would tell a reader the material contradicts the record. It does
    not; the reader could not get to it. That is ADR-0004's explicit distinction,
    and it routes to ``user_attested`` rather than to automatic failure.

    Reached only by inserting the row directly: LC-P1-08's walk never produces a
    text row for a source it marks unreadable, so this combination tests the
    check, not the ingestion.
    """
    connection, index = store
    _insert_source(connection, "src-scan", EDITED, "unreadable_no_ocr")
    _insert_text(connection, EDITED, PdfLocator(page=1), "Some text that survives.")
    _insert_anchor(connection, "scan-anchor", "src-scan", PdfLocator(page=1), EDITED)
    connection.commit()
    verdict = check_source_exists(_record(("scan-anchor",), source_hash=EDITED), index=index)
    assert verdict.outcome is CheckOutcome.INDETERMINATE
    assert "cannot" in verdict.detail or "no text" in verdict.detail


def test_drift_buried_under_an_unreadable_anchor_still_fails(store: Store) -> None:
    """A hard fact is not downgraded because a softer one is also present.

    Every anchor is examined and ``fail`` outranks ``indeterminate``. An
    implementation that returned on the first non-pass would answer
    ``indeterminate`` here and bury the drift, which is the more dangerous of the
    two: "we could not tell" invites a reader to move on, while "the file
    changed" tells them the record is wrong. The order of the anchor ids is
    reversed on purpose so the softer answer is the one an early-return
    implementation would reach first.
    """
    connection, index = store
    _insert_source(connection, "src-scan", EDITED, "unreadable_no_ocr")
    _insert_text(connection, EDITED, PdfLocator(page=1), "Text stored for a scan.")
    _insert_anchor(connection, "scan", "src-scan", PdfLocator(page=1), EDITED)
    # The paper's bytes move; the anchor keeps the hash it was made against.
    connection.execute(
        sql_text("UPDATE sources SET content_sha256 = :sha WHERE source_id = 'src-1'"),
        {"sha": EDITED},
    )
    _insert_anchor(connection, "drifted", "src-1", PdfLocator(page=3), ORIGINAL)
    connection.commit()

    verdict = check_source_exists(_record(("scan", "drifted"), source_hash=ORIGINAL), index=index)
    assert verdict.outcome is CheckOutcome.FAIL
    assert "changed after the anchor was made" in verdict.detail
    assert "1 of 2" in verdict.detail

    # The reverse order must give the same verdict, which is what makes the
    # aggregation a rule rather than an accident of iteration.
    verdict = check_source_exists(_record(("drifted", "scan"), source_hash=ORIGINAL), index=index)
    assert verdict.outcome is CheckOutcome.FAIL


def test_the_record_model_refuses_a_verified_record_with_no_anchors(store: Store) -> None:
    """Two independent locks on the same failure, and both are tested.

    C1 answers ``indeterminate`` for an anchorless record, and
    ``EvidenceRecord`` separately refuses ``verified_by_rule`` for a record that
    is not located. Either alone would stop the bad state; a test of only one
    would not know whether the other held. The second lock is the one that
    survives someone rewriting the check.
    """
    verdict = check_source_exists(_record((), status="planned"), index=store[1])
    entry = VerificationRecord(
        check=CheckKind.C1,
        checker_id=C1_CHECKER_ID,
        outcome=verdict.outcome,
        detail=verdict.detail,
        checked_at=NOW,
    )
    with pytest.raises(ValueError):
        EvidenceRecord(
            evidence_id="ev-none",
            task_id="task-1",
            kind=EvidenceKind.CLAIM,
            text="A claim with no evidence.",
            anchor_ids=(),
            extracted_span="whatever",
            extracted_span_sha256=_sha("whatever"),
            status=VerificationStatus.VERIFIED_BY_RULE,
            verification_log=(entry,),
            created_by=EvidenceCreator.RULE,
            created_by_id="seed",
            source_content_hash=ORIGINAL,
            created_at=NOW,
        )


def test_a_locators_kind_that_has_no_text_is_not_silently_resolved(store: Store) -> None:
    """A CSV cell anchor resolves only if the cell is in the store.

    Different locator kinds go through the same three-state answer, and a kind
    is not a special case: an unaddressed cell is ``UNRESOLVABLE``, the same as
    an out-of-range page.
    """
    connection, index = store
    _insert_text(connection, ORIGINAL, CsvLocator(row=2, column="mean"), "3.50")
    _insert_anchor(connection, "cell", "src-1", CsvLocator(row=2, column="mean"), ORIGINAL)
    _insert_anchor(connection, "missing-cell", "src-1", CsvLocator(row=9, column="mean"), ORIGINAL)
    connection.commit()
    verdict = check_source_exists(_record(("cell",), source_hash=ORIGINAL), index=index)
    assert verdict.outcome is CheckOutcome.PASS
    verdict = check_source_exists(_record(("missing-cell",), source_hash=ORIGINAL), index=index)
    assert verdict.outcome is CheckOutcome.FAIL


# --------------------------------------------------------------------------- #
# the empty record
# --------------------------------------------------------------------------- #


def test_a_record_citing_nothing_is_not_passed(store: Store) -> None:
    """A vacuous pass is the most dangerous answer C1 could give.

    An anchorless record is only constructable at ``planned`` --
    ``EvidenceRecord`` refuses any later status without a located record -- and
    ``planned -> extracted`` is exactly the transition ADR-0004 Contract 2 says
    C1 decides. So this is not an edge case: it is the case where a ``pass``
    would let a record with no evidence advance to ``verified_by_rule``.

    ``indeterminate`` is the answer that cannot be mistaken for agreement, and
    the assertion that it is not ``pass`` is the whole point of the test.
    """
    _, index = store
    verdict = check_source_exists(_record((), status="planned"), index=index)
    assert verdict.outcome is CheckOutcome.INDETERMINATE
    assert "cites no anchors" in verdict.detail


# --------------------------------------------------------------------------- #
# the wiring
# --------------------------------------------------------------------------- #


def test_a_record_that_recorded_no_hash_is_not_passed(store: Store) -> None:
    """No hash means nothing to re-verify, which is not the same as agreement.

    ``pass`` asserts "the hashes match". A record that never stored a source
    hash cannot support that assertion, and an implementation that defaulted the
    comparison to a pass on ``None`` would report every planned record as
    verified.

    The state is reachable only at ``planned``: ``EvidenceRecord`` refuses any
    later status without a recorded hash, which is Contract 2's requirement
    rather than C1's. So the two locks cover the same failure from different
    sides, and the test asserts both -- a record that C1 could wave through
    still cannot be constructed as ``verified_by_rule``.
    """
    _, index = store
    verdict = check_source_exists(
        _record(("anchor-1",), source_hash=None, status="planned"), index=index
    )
    assert verdict.outcome is CheckOutcome.INDETERMINATE
    assert "nothing to re-verify" in verdict.detail

    with pytest.raises(ValueError):
        _record(("anchor-1",), source_hash=None, status="verified_by_rule")


class _IndexWithNoAnswer(LabCairnIndex):
    """An index that resolves nothing, to test C1's handling of it.

    ``SourceIndex.locate`` is documented as returning ``None`` for an unknown
    anchor, and the shipped :class:`LabCairnIndex` never does: every anchor it
    is handed either resolves or does not. The branch is therefore only
    reachable through another implementation of the Protocol, and C1 must still
    not treat it as a pass.
    """

    def locate(self, anchor: Any) -> Any:
        return None


def test_an_index_that_cannot_answer_fails_rather_than_passing(store: Store) -> None:
    connection, _ = store
    index = _IndexWithNoAnswer(connection)
    verdict = check_source_exists(_record(("anchor-1",), source_hash=ORIGINAL), index=index)
    assert verdict.outcome is CheckOutcome.FAIL
    assert "cannot resolve it at all" in verdict.detail


def test_c1_answers_while_c2_and_c3_still_refuse(store: Store) -> None:
    """What this build can establish, as data a report can ask.

    ``IMPLEMENTED_CHECKS`` is the honest version of a capability probe. ADR-0002
    is the reason it is a set rather than a boolean: a probe that says "fine"
    without having looked is the failure this whole ledger exists to avoid.
    """
    from labcairn.evidence.states import IMPLEMENTED_CHECKS

    record = _record(("anchor-1",), source_hash=ORIGINAL)
    _, index = store
    assert check_source_exists(record, index=index).outcome is CheckOutcome.PASS
    for not_yet in (check_quotation_support, check_numeric_consistency):
        with pytest.raises(CiteSupportNotImplementedError) as caught:
            not_yet(record, index=index)
        assert caught.value.check in {CheckKind.C2, CheckKind.C3}
    assert CheckKind.C1 in IMPLEMENTED_CHECKS
    assert CheckKind.C2 not in IMPLEMENTED_CHECKS
