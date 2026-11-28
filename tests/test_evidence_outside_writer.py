"""The three refusals, measured against a writer outside the product.

**The gap this closes.** The acceptance record
``docs/acceptance/LC-P4-PILOT-verified-by-rule-unreachable-2026-11-28.md``
lists, under *"What was not measured"*, an item it says was not measured:

> **Behaviour under a writer outside the product.** A SQL client or a future
> code path could insert a ``verified_by_rule`` row directly; the model, the
> store boundary and the schema each hold one of the three refusals, but this
> window did not build such a writer and drive it.

The witnesses at ``tests/test_evidence_store.py`` cover the store's own
refusals. This file covers what they cannot: a writer that never imports the
model, never calls the store, and writes the database with raw SQL — the way
a SQL client, a migration, or a future contributor who does not know the
model would.

**The writer.** :class:`OutsideWriter` below is that writer. It has one
method per row it wants to land, and every one of them is a ``connection.execute``
of a SQL string. It never imports :class:`~labcairn.evidence.record.EvidenceRecord`,
never calls
:func:`~labcairn.evidence.store.append_record`, and never touches the
application layer. It holds the database the way ``psql`` holds it.

**What this file asserts, and what it deliberately does not.** Each of the
three refusals is driven once, aimed at the refusal it is meant to meet, and
the file says what each one *actually did* — the error, the constraint, the
boundary — rather than what it was expected to do. Where a refusal fired at a
different moment than the attempt expected, the file says that too: the
model's refusal fires on the *read*, because a writer that does not use the
model is not in the model's path at all.

The measurement found something the record's item did not anticipate, and the
file says so rather than papering over it: **the three refusals do not add up
to a closed door.** A writer that lands a located row *and* a forged passing
log entry produces a record the model reads, the store never saw, and the
report's evidence gate accepts with no finding at all. The refusals each hold
— every one of them refused its own case — and together they leave a path
open. That gap is the file's most important claim, and it is watched rather
than asserted: see
:func:`test_the_three_refusals_do_not_add_up_to_a_closed_door`.

**Why the witnesses are negative.** Every case here is a case that must be
refused, or must find nothing — which is the ``negative`` class the
repository's own marker vocabulary defines. The file is marked
``pytest.mark.negative``, and it is the integrating session that files it in
``tests/evaluation/manifest.py``; the class it must be filed under is
``negative`` (its own marker rules out the others), and the clause the
integrating session should use is ``fabricated-citation`` — the outside
writer fabricates a verification the product never performed.

**A note on the mutation check.** Each test's docstring names what makes it
red. A test that failed because of an unrelated encoding or line-length
matter would not be a witness of the property under test, so each assertion
here is about a named refusal, and the mutation check is reported in the
record.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import text as sql_text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from conftest import migrated_database_from
from labcairn.db.session import create_db_engine
from labcairn.evidence.gate import evaluate_records
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
    append_record,
    load_record,
    render_anchor_key,
)
from labcairn.material.addressing import render_locator_key
from labcairn.sources.locators import PdfLocator

pytestmark = pytest.mark.negative

NOW = dt.datetime(2026, 10, 19, tzinfo=dt.UTC)
SHA = "a" * 64
SPAN = "Dijkstra's algorithm is not greedy."


class OutsideWriter:
    """A writer that reaches the database without going through the product.

    **Every method here is raw SQL.** That is the whole point: a writer that
    imported :class:`~labcairn.evidence.record.EvidenceRecord` or called
    :func:`~labcairn.evidence.store.append_record` would be testing the
    store's own refusals, which ``tests/test_evidence_store.py`` already
    covers. This writer is what a ``sqlite3`` shell, a migration, or a future
    contributor who has never read the model would do.

    It holds the same connection the product holds, and it commits, because a
    refusal that only holds until the next transaction is not a refusal.
    """

    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    def write_row(
        self,
        evidence_id: str,
        *,
        task_id: str = "task-1",
        status: str = "verified_by_rule",
        anchor_id: str = "a-page",
        located: bool = True,
        span: str = SPAN,
    ) -> None:
        """Insert one ``evidence_records`` row, as SQL text.

        ``located=False`` writes a row with no span, no hash and an empty
        anchor key — the shape the schema has a CHECK for. ``span`` is the
        quoted text the record carries, and it is a parameter because a
        forgery is not always the one that quotes the source exactly.
        """
        quoted = span if located else None
        span_sha = hashlib.sha256(span.encode()).hexdigest() if located else None
        anchor_key = render_anchor_key((anchor_id,)) if located else "[]"
        self.connection.execute(
            sql_text(
                "INSERT INTO evidence_records (evidence_id, schema_version, task_id,"
                " kind, text, value, unit, tolerance, anchor_key, extracted_span,"
                " extracted_span_sha256, source_content_hash, status, created_by,"
                " created_by_id, created_at, superseded_by)"
                " VALUES (:eid,1,:tid,'claim','A claim.',NULL,NULL,NULL,:akey,"
                ":span,:ssha,:shash,:status,'rule','seed',:now,NULL)"
            ),
            {
                "eid": evidence_id,
                "tid": task_id,
                "akey": anchor_key,
                "span": quoted,
                "ssha": span_sha,
                "shash": SHA if located else None,
                "status": status,
                "now": NOW.isoformat(),
            },
        )
        if located:
            self.connection.execute(
                sql_text(
                    "INSERT INTO evidence_anchors (evidence_id, position, anchor_id)"
                    " VALUES (:eid,0,:aid)"
                ),
                {"eid": evidence_id, "aid": anchor_id},
            )

    def write_log_entry(
        self,
        evidence_id: str,
        *,
        check_kind: str = "c1",
        checker_id: str = "c1.source_exists",
        outcome: str = "pass",
    ) -> None:
        """Insert one ``verification_records`` row, as SQL text."""
        self.connection.execute(
            sql_text(
                "INSERT INTO verification_records (evidence_id, seq, schema_version,"
                " check_kind, checker_id, outcome, detail, checked_at,"
                " normalization_profile)"
                " VALUES (:eid,1,1,:kind,:cid,:outcome,'forged',:now,:profile)"
            ),
            {
                "eid": evidence_id,
                "kind": check_kind,
                "cid": checker_id,
                "outcome": outcome,
                "now": NOW.isoformat(),
                # The schema's own CHECK says a profile belongs to C2 and to
                # nothing else, so the writer has to honour it to get as far
                # as the refusal this file is about.
                "profile": "exact" if check_kind == "c2" else None,
            },
        )

    def write_status_update(self, evidence_id: str, status: str) -> None:
        """Move a row's status with a bare ``UPDATE``."""
        self.connection.execute(
            sql_text("UPDATE evidence_records SET status = :status WHERE evidence_id = :eid"),
            {"status": status, "eid": evidence_id},
        )

    def read_status(self, evidence_id: str) -> str | None:
        row = self.connection.execute(
            sql_text("SELECT status FROM evidence_records WHERE evidence_id = :eid"),
            {"eid": evidence_id},
        ).fetchone()
        return None if row is None else str(row[0])


@pytest.fixture()
def writer(migrated_database_template: Path, tmp_path: Path) -> Iterator[OutsideWriter]:
    """A store with one source, one page of text and one anchor.

    The same fixture the store's own tests use, so the outside writer writes
    into a database that is indistinguishable from one the product wrote.
    """
    target = tmp_path / "outside.db"
    migrated_database_from(migrated_database_template, target)
    engine = create_db_engine(target)
    connection = engine.connect()

    with connection.begin():
        connection.execute(
            sql_text(
                "INSERT INTO sources (source_id, owner_id, kind, display_name,"
                " relative_path, content_sha256, size_bytes, readability,"
                " readability_disclosure, identifiers, ingested_at, schema_version)"
                " VALUES ('src-1','local-user','pdf','a.pdf','a.pdf',:sha,1,'readable',"
                "NULL,'[]',:now,1)"
            ),
            {"sha": SHA, "now": NOW.isoformat()},
        )
        page_key = render_locator_key(PdfLocator(page=2))
        connection.execute(
            sql_text(
                "INSERT INTO source_texts (source_content_sha256, extraction_version,"
                " locator_kind, locator_key, page, row_number, column_name, text,"
                " text_sha256, created_at)"
                " VALUES (:sha,'v1','pdf',:key,2,NULL,NULL,:body,:tsha,:now)"
            ),
            {
                "sha": SHA,
                "key": page_key,
                "body": SPAN,
                "tsha": hashlib.sha256(SPAN.encode()).hexdigest(),
                "now": NOW.isoformat(),
            },
        )
        connection.execute(
            sql_text(
                "INSERT INTO source_anchors (anchor_id, source_id, kind, locator_key,"
                " bound_source_sha256, excerpt_sha256, created_at)"
                " VALUES ('a-page','src-1','quotation',:key,:sha,NULL,:now)"
            ),
            {"key": page_key, "sha": SHA, "now": NOW.isoformat()},
        )
    connection.commit()
    yield OutsideWriter(connection)
    engine.dispose()


# --------------------------------------------------------------------------- #
# The three refusals
# --------------------------------------------------------------------------- #


def test_the_model_refuses_a_verified_row_the_writer_landed(writer: OutsideWriter) -> None:
    """**The model.** A status with no passing log entry is refused.

    **What it did.** The writer landed a located row whose status is
    ``verified_by_rule`` and which holds no log entry at all. The write
    succeeded — the row is in the database, and the schema's own CHECKs are
    satisfied. The refusal came when the *product* read the row back:
    :func:`~labcairn.evidence.store.load_record` raised
    ``pydantic.ValidationError``, and its message is the model's own:

        verified_by_rule requires a verification_log entry with check in
        {c1, c2, c3} and outcome 'pass' (ADR-0004 Contract 2). Status without
        a log entry is a schema violation (I3).

    **What makes this red.** If the model's `_an_upgrade_requires_the_entry_that_earned_it`
    validator stopped refusing, the read would succeed and this test would
    fail on the ``pytest.raises`` — the row would come back as a record with
    no log, which is I3's exact defect.
    """
    writer.write_row("ev-model")
    writer.connection.commit()

    # The write itself was accepted. That is the point: the schema let it in.
    assert writer.read_status("ev-model") == "verified_by_rule"

    with pytest.raises(ValidationError) as caught:
        load_record(writer.connection, "ev-model")
    message = str(caught.value)
    assert "verified_by_rule requires a verification_log entry" in message
    assert "ADR-0004 Contract 2" in message


def test_the_store_boundary_refuses_a_verified_row_from_an_unregistered_rule(
    writer: OutsideWriter,
) -> None:
    """**The store boundary.** A passing entry must name a registered rule.

    **What it did.** The writer's *only* way through the store is
    :func:`~labcairn.evidence.store.append_record`, and it handed it a record
    whose status is ``verified_by_rule`` and whose log names ``a.person`` —
    a checker id no build implements. The store refused:

        Contract 2: a verified_by_rule record needs a passing entry from a
        checker_id in the registered rule catalog, and 'a.person' is not one.

    The refusal is the store's own :class:`~labcairn.evidence.store.LedgerError`.

    **What makes this red.** If `_require_catalog_backed` stopped consulting
    the catalog, the append would succeed and this test would fail on the
    ``pytest.raises``. This is the half of the rule the model cannot check,
    because the model has to accept a person's id — an attestation is logged
    by a human.

    **Why the refusal is the store's and not the model's.** The record this
    test builds *passes* the model's own validator — it is constructed
    successfully, right here, before ``append_record`` is ever called. So the
    model was asked and said yes; the refusal that follows can only be the
    store's. That is the whole division of labour the store's docstring
    claims, measured rather than asserted.
    """
    record = EvidenceRecord(
        evidence_id="ev-store",
        task_id="task-1",
        kind=EvidenceKind.CLAIM,
        text="A claim verified by something that is not a rule.",
        anchor_ids=("a-page",),
        extracted_span=SPAN,
        extracted_span_sha256=hashlib.sha256(SPAN.encode()).hexdigest(),
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

    # The model was asked first, and said yes: the record exists.
    assert record.status is VerificationStatus.VERIFIED_BY_RULE
    assert record.verification_log[0].checker_id == "a.person"

    with pytest.raises(LedgerError) as caught:
        append_record(writer.connection, record)
    assert "registered rule catalog" in str(caught.value)
    assert "'a.person' is not one" in str(caught.value)

    # And nothing was written: a refused append leaves no row behind.
    assert writer.read_status("ev-store") is None


def test_the_schema_refuses_a_verified_row_with_no_location(writer: OutsideWriter) -> None:
    """**The schema.** A record past ``planned`` must carry its location.

    **What it did.** The writer landed a row whose status is
    ``verified_by_rule`` with no span, no span hash, no source hash and an
    empty anchor key. The database refused the write outright, with the
    constraint named:

        CHECK constraint failed:
        ck_evidence_records_evidence_records_located_past_planned

    This is the refusal that needs no product code at all: it fires inside
    SQLite, on the write, before anything can read the row back.

    **What makes this red.** If revision 0005's
    ``evidence_records_located_past_planned`` CHECK were dropped, the write
    would succeed and this test would fail on the ``pytest.raises``.
    """
    with pytest.raises(IntegrityError) as caught:
        writer.write_row("ev-schema", located=False)
        writer.connection.commit()
    assert "ck_evidence_records_evidence_records_located_past_planned" in str(caught.value.orig)


def test_the_schema_refuses_a_status_outside_its_vocabulary(writer: OutsideWriter) -> None:
    """**The schema**, again: the status column is a closed vocabulary.

    **What it did.** The writer tried ``verified_by_ruel`` — a typo, and the
    kind of thing a hand-written INSERT gets wrong. The database refused:

        CHECK constraint failed:
        ck_evidence_records_evidence_records_status_vocabulary

    **What makes this red.** If the vocabulary CHECK were dropped, the row
    would land with a status the product does not have a name for, and this
    test would fail on the ``pytest.raises``.
    """
    with pytest.raises(IntegrityError) as caught:
        writer.write_row("ev-vocab", status="verified_by_ruel")
        writer.connection.commit()
    assert "ck_evidence_records_evidence_records_status_vocabulary" in str(caught.value.orig)


# --------------------------------------------------------------------------- #
# What the three refusals do not add up to
# --------------------------------------------------------------------------- #


def test_the_three_refusals_do_not_add_up_to_a_closed_door(writer: OutsideWriter) -> None:
    """**The finding.** The three refusals each hold, and together they leave
    a path open.

    This is the measurement the record's open item did not anticipate, and
    it is the most important claim in this file, so it is stated as plainly
    as the measurements allow.

    **What the writer did.** Two raw INSERTs and no product code:

    1. a located row whose status is ``verified_by_rule``, and
    2. a ``verification_records`` row claiming C1 concluded ``pass``, with
       ``checker_id`` ``c1.source_exists`` — an id that *is* in the registered
       rule catalog, because the writer copied it from a real check.

    The schema accepted both: every CHECK was satisfied, and there is no
    trigger on these tables (the schema has none by design — revision 0005's
    own comment says triggers "would silently miss every write by anything
    else"). The store never saw the write. The model accepted the row back:
    :func:`~labcairn.evidence.store.load_record` returned a record in
    ``verified_by_rule`` carrying one log entry.

    **And the report's gate accepted it too.** The evidence gate — the last
    thing that runs before a report says something — judged the forged record
    and reported ``passed`` with **no findings at all**.

    **Why each of the three refusals did not stop it.**

    - The **model** requires *a* passing entry. It does not require the entry
      to be true, and it cannot: a ``VerificationRecord`` is a statement
      about the past, and the model has nothing to compare it against.
    - The **store boundary** holds the registered-rule rule — but the writer
      used a *registered* id, so there was nothing to refuse. The store's
      rule is a rule about *which* rules may vouch, not about whether the
      vouch happened.
    - The **schema** holds the location rule — and the writer satisfied it,
      because a located row is easy to write.

    **What makes this red.** This test is red if the system becomes *safer*
    than measured: if a forgery is refused somewhere, or if the gate starts
    finding it, the assertions fail. That is the correct direction for a
    witness of an open door — it is a floor, not a ceiling. The test asserts
    that the forgery succeeds, and a tree that closes the door must update
    this test and this record together.

    **The narrow finding this test does NOT make.** The gate does have
    powers the three refusals do not: it re-runs the checks the log records,
    so a forged *C2* pass, or a forged C1 pass whose anchor resolves
    nowhere, is caught as a drift finding (see
    :func:`test_the_gate_catches_a_forged_entry_that_re_running_would_refuse`).
    A forged **C1** pass whose anchor does resolve is not caught — because
    re-running C1 confirms it. That is the narrow case this file measures.
    """
    writer.write_row("ev-forged", task_id="task-forged")
    writer.write_log_entry("ev-forged")
    writer.connection.commit()

    # 1. The schema accepted the row and the log entry.
    assert writer.read_status("ev-forged") == "verified_by_rule"

    # 2. The model reads the forged row back as a real record.
    record = load_record(writer.connection, "ev-forged")
    assert record is not None
    assert record.status is VerificationStatus.VERIFIED_BY_RULE
    assert len(record.verification_log) == 1
    assert record.verification_log[0].checker_id == "c1.source_exists"

    # 3. And the report's gate passes it, with nothing to say.
    index = LabCairnIndex(writer.connection)
    result = evaluate_records(
        writer.connection,
        task_id="task-forged",
        index=index,
        evidence_ids=["ev-forged"],
    )
    assert result.passed is True
    assert result.findings == ()


def test_the_gate_catches_a_forged_entry_that_re_running_would_refuse(
    writer: OutsideWriter,
) -> None:
    """**The narrow finding.** The gate does catch forgeries it can disprove.

    The previous test's forgery names C1 and cites an anchor that *does*
    resolve, so re-running C1 confirms the forged entry and the gate has
    nothing to say. This one is the case where the gate's own power applies:
    the forged entry claims C2 concluded ``pass``, and re-running C2 says
    ``fail`` — because the record's text is not the source's text.

    The gate's finding names the disagreement:

        the record's log says c2 concluded 'pass', but re-running it now
        concludes 'fail'.

    **What makes this red.** If the gate stopped re-running the checks the
    log records, this finding would disappear and the test would fail on the
    ``kind == "drift"`` assertion.
    """
    writer.write_row(
        "ev-drift",
        task_id="task-drift",
        span="A sentence the source never said.",
    )
    writer.write_log_entry("ev-drift", check_kind="c2", checker_id="c2.quotation_match")
    writer.connection.commit()

    index = LabCairnIndex(writer.connection)
    result = evaluate_records(
        writer.connection,
        task_id="task-drift",
        index=index,
        evidence_ids=["ev-drift"],
    )
    assert result.passed is False
    assert [finding.kind for finding in result.findings] == ["drift"]
    assert "concluded 'pass'" in result.findings[0].reason
    assert "concludes 'fail'" in result.findings[0].reason


def test_a_forged_status_alone_leaves_the_record_unreadable(writer: OutsideWriter) -> None:
    """**What a forged status costs.** A forged status is not free.

    This is the case where the writer moves a legitimate record's status with
    a bare ``UPDATE`` and does *not* forge the log entry. The write succeeds
    — the schema's location CHECK is satisfied, because the record it moved
    was a real located record. But the record then cannot be read: the
    model's refusal (I3) fires on the read, so the record is unreadable
    rather than falsely verified.

    That is a real property and it is worth stating, because it is the
    difference between the two forgeries: a forged status *breaks* the
    record, while a forged status *plus* a forged log entry *disguises* it.

    **What makes this red.** If the model's I3 validator stopped refusing,
    the read would succeed and this test would fail on the ``pytest.raises``.
    """
    writer.write_row("ev-moved", task_id="task-moved", status="extracted")
    writer.connection.commit()
    assert writer.read_status("ev-moved") == "extracted"

    writer.write_status_update("ev-moved", "verified_by_rule")
    writer.connection.commit()
    assert writer.read_status("ev-moved") == "verified_by_rule"

    with pytest.raises(ValidationError) as caught:
        load_record(writer.connection, "ev-moved")
    assert "verified_by_rule requires a verification_log entry" in str(caught.value)


def test_a_forged_row_breaks_the_task_that_holds_it(writer: OutsideWriter) -> None:
    """**What a forged row costs the task around it.**

    A landed forgery is not confined to itself. The task's records are read
    as a set — :func:`~labcairn.evidence.store.load_task_records` loads every
    record the task holds and validates each one — so a forged row with no
    log entry makes the *task* unreadable, not just the row.

    The refusal that fires is the model's I3 rule, the same one the single
    record's read fires: a status with no passing log entry is refused.

    **What makes this red.** If the product's read path stopped validating
    what it loads, the task would come back and this test would fail on the
    ``pytest.raises``.
    """
    writer.write_row("ev-broken", task_id="task-broken")
    writer.connection.commit()

    with pytest.raises(ValidationError) as caught:
        from labcairn.evidence.store import load_task_records

        load_task_records(writer.connection, "task-broken")
    assert "requires a verification_log entry" in str(caught.value)
