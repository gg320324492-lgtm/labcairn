"""The scholarly identifiers: recorded as data, resolved as a state, never a check.

Five properties, and the tests are grouped by the layer that carries each:

**A record can carry an identifier, with its provenance** (the schema, the
model, the store's round trip). The provenance is the half the work order is
about -- ingestion, a person, or a model -- and it is a column, not a mode.

**Resolution is a state, not a failure** (the schema's state rules, and the
application's ``not_attempted`` path). A resolution request in this build is
*recorded, not sent*: the row lands ``not_attempted`` with the boundary's own
reason appended, and the tests run it with the machine's sockets forbidden,
so "nothing reached the network" is measured rather than promised.

**A claim may not rest on an identifier nothing resolved** (the store's
refusal, and the gate's finding). The store refuses it when the record is
written or moved; the gate catches it again at the report's last door, and
the finding names the identifier, its state and its provenance.

**A model-supplied identifier is not a citation check** (the resolution
path's behaviour, and the vocabularies' disjointness). Even a person's
confirmation of a model's proposal writes no ``verification_log`` entry and
moves no record's status, and the resolution and verification vocabularies
share no words at all -- so no sequence of identifier events can spell
"checked".

The schema tests insert rows **directly with SQL** and assert the database
refuses them, on the reasoning ``test_evidence_schema.py`` records: a CHECK
whose body names a misspelled column evaluates to NULL and passes, so the
only proof a constraint refuses is a refused row.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text as sql_text
from sqlalchemy.engine import Connection

from conftest import migrated_database_from
from labcairn.db.session import create_db_engine
from labcairn.evidence.checks.c1 import C1_CHECKER_ID
from labcairn.evidence.gate import evaluate_task
from labcairn.evidence.identifiers import (
    IdentifierError,
    IdentifierProvenance,
    IdentifierScheme,
    ResolutionState,
    ScholarlyIdentifier,
    confirm_resolution,
    load_identifier,
    load_task_identifiers,
    put_identifier,
    request_resolution,
)
from labcairn.evidence.index import LabCairnIndex
from labcairn.evidence.record import EvidenceRecord, VerificationRecord
from labcairn.evidence.states import (
    VERIFICATION_STATES,
    CheckKind,
    CheckOutcome,
    EvidenceCreator,
    EvidenceKind,
    VerificationStatus,
)
from labcairn.evidence.store import LedgerError, advance, append_record, attest, load_record
from labcairn.material.addressing import render_locator_key
from labcairn.sources.locators import PdfLocator

pytestmark = pytest.mark.integration

NOW = dt.datetime(2026, 11, 2, tzinfo=dt.UTC)
NOW_TEXT = "2026-11-02T00:00:00+00:00"
SHA = "a" * 64

# --------------------------------------------------------------------------- #
# the schema: the rows it must refuse, written by hand
# --------------------------------------------------------------------------- #

#: A row every CHECK accepts. Each schema test varies one field from this.
LEGAL_ROW: dict[str, Any] = {
    "identifier_id": "id-legal",
    "task_id": "task-1",
    "scheme": "doi",
    "value": "10.1234/abc.def",
    "supplied_by": "model",
    "supplied_by_id": "run-1",
    "resolution_state": "unresolved",
    "resolution_detail": None,
    "resolved_by": None,
    "resolved_at": None,
    "created_at": NOW_TEXT,
}


@pytest.fixture()
def schema_db(migrated_database_template: Path, tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """A migrated database, opened raw: the schema's own refusals are the test."""
    target = tmp_path / "schema.db"
    migrated_database_from(migrated_database_template, target)
    connection = sqlite3.connect(str(target))
    try:
        yield connection
    finally:
        connection.close()


def _insert_identifier(connection: sqlite3.Connection, **overrides: Any) -> None:
    row = {**LEGAL_ROW, **overrides}
    connection.execute(
        "INSERT INTO identifier_records (identifier_id, task_id, scheme, value,"
        " supplied_by, supplied_by_id, resolution_state, resolution_detail,"
        " resolved_by, resolved_at, created_at)"
        " VALUES (:identifier_id,:task_id,:scheme,:value,:supplied_by,:supplied_by_id,"
        ":resolution_state,:resolution_detail,:resolved_by,:resolved_at,:created_at)",
        row,
    )


def test_a_scheme_outside_the_vocabulary_is_not_storable(schema_db: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        _insert_identifier(schema_db, scheme="isbn")


def test_a_provenance_outside_the_vocabulary_is_not_storable(
    schema_db: sqlite3.Connection,
) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        _insert_identifier(schema_db, supplied_by="llm")


def test_a_resolution_state_outside_the_vocabulary_is_not_storable(
    schema_db: sqlite3.Connection,
) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        _insert_identifier(schema_db, resolution_state="verified")


def test_an_unresolved_row_carries_none_of_the_resolution_fields(
    schema_db: sqlite3.Connection,
) -> None:
    detailled = dict.fromkeys(
        ("resolution_detail", "resolved_by", "resolved_at"), "someone said so"
    )
    for field in detailled:
        with pytest.raises(sqlite3.IntegrityError):
            _insert_identifier(schema_db, **{field: detailled[field]})


def test_a_not_attempted_row_without_a_reason_is_not_storable(
    schema_db: sqlite3.Connection,
) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        _insert_identifier(schema_db, resolution_state="not_attempted")


def test_a_not_attempted_row_naming_a_resolver_is_not_storable(
    schema_db: sqlite3.Connection,
) -> None:
    """A row that says no lookup ran cannot also say who answered."""
    with pytest.raises(sqlite3.IntegrityError):
        _insert_identifier(
            schema_db,
            resolution_state="not_attempted",
            resolution_detail="why: outbound is not consented",
            resolved_by="a-person",
        )


def test_a_resolved_row_without_its_evidence_is_not_storable(
    schema_db: sqlite3.Connection,
) -> None:
    complete = {
        "resolution_state": "resolved",
        "resolution_detail": "the DOI resolves to the paper",
        "resolved_by": "the-owner",
        "resolved_at": NOW_TEXT,
    }
    for missing in ("resolution_detail", "resolved_by", "resolved_at"):
        row = {key: value for key, value in complete.items() if key != missing}
        with pytest.raises(sqlite3.IntegrityError):
            _insert_identifier(schema_db, **row)


def test_an_empty_value_is_not_storable(schema_db: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        _insert_identifier(schema_db, value="")


def test_the_same_identifier_twice_in_one_task_is_not_storable(
    schema_db: sqlite3.Connection,
) -> None:
    _insert_identifier(schema_db)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_identifier(schema_db, identifier_id="id-second")


def test_the_same_identifier_in_two_tasks_is_two_rows(schema_db: sqlite3.Connection) -> None:
    """The uniqueness is per task: two tasks may each hold the same DOI."""
    _insert_identifier(schema_db)
    _insert_identifier(schema_db, identifier_id="id-elsewhere", task_id="task-2")


def test_a_join_row_at_a_negative_position_is_not_storable(schema_db: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        schema_db.execute(
            "INSERT INTO evidence_identifiers (evidence_id, position, identifier_id)"
            " VALUES ('ev-1', -1, 'id-legal')"
        )


def test_a_join_row_citing_an_identifier_twice_is_not_storable(
    schema_db: sqlite3.Connection,
) -> None:
    schema_db.execute(
        "INSERT INTO evidence_identifiers (evidence_id, position, identifier_id)"
        " VALUES ('ev-1', 0, 'id-legal')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        schema_db.execute(
            "INSERT INTO evidence_identifiers (evidence_id, position, identifier_id)"
            " VALUES ('ev-1', 1, 'id-legal')"
        )


# --------------------------------------------------------------------------- #
# the model: the closed vocabularies, and the state carrying what it names
# --------------------------------------------------------------------------- #


def _identifier(**overrides: Any) -> ScholarlyIdentifier:
    fields: dict[str, Any] = {
        "identifier_id": "id-1",
        "task_id": "task-1",
        "scheme": IdentifierScheme.DOI,
        "value": "10.1234/abc.def",
        "supplied_by": IdentifierProvenance.MODEL,
        "supplied_by_id": "run-1",
        "resolution_state": ResolutionState.UNRESOLVED,
        "created_at": NOW,
    }
    fields.update(overrides)
    return ScholarlyIdentifier(**fields)


def test_a_state_disagreeing_with_its_fields_is_refused_at_construction() -> None:
    with pytest.raises(ValueError):
        _identifier(resolution_state=ResolutionState.UNRESOLVED, resolution_detail="a note")
    with pytest.raises(ValueError):
        _identifier(
            resolution_state=ResolutionState.NOT_ATTEMPTED,
            resolution_detail="why not",
            resolved_by="a-person",
        )
    with pytest.raises(ValueError):
        _identifier(resolution_state=ResolutionState.RESOLVED, resolution_detail="found it")


def test_an_unknown_spelling_is_refused_not_coerced() -> None:
    with pytest.raises(ValueError):
        _identifier(scheme="DOI")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        _identifier(resolution_state="Verified")  # type: ignore[arg-type]


def test_the_resolution_and_verification_vocabularies_share_no_words() -> None:
    """Two axes, two vocabularies: no identifier state spells "checked"."""
    resolution_words = {state.value for state in ResolutionState}
    assert not resolution_words & VERIFICATION_STATES, (
        "a word that means both 'an identifier was resolved' and 'a record was"
        " checked' would let one answer the other's question"
    )


# --------------------------------------------------------------------------- #
# the store: the round trip, and the refusal
# --------------------------------------------------------------------------- #

Store = tuple[Connection, LabCairnIndex]


@pytest.fixture()
def ledger(migrated_database_template: Path, tmp_path: Path) -> Iterator[Store]:
    """A ledger with one readable page, one anchor, and one identifier on the shelf."""
    target = tmp_path / "ledger.db"
    migrated_database_from(migrated_database_template, target)
    engine = create_db_engine(target)
    connection = engine.connect()

    page_key = render_locator_key(PdfLocator(page=2))
    with connection.begin():
        connection.execute(
            sql_text(
                "INSERT INTO sources (source_id, owner_id, kind, display_name, relative_path,"
                " content_sha256, size_bytes, readability, readability_disclosure, identifiers,"
                " ingested_at, schema_version)"
                " VALUES ('src-1','local-user','pdf','a.pdf','a.pdf',:sha,1,'readable',NULL,"
                "'[]',:now,1)"
            ),
            {"sha": SHA, "now": NOW_TEXT},
        )
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
                "body": "Dijkstra's algorithm is not greedy.",
                "tsha": hashlib.sha256(b"Dijkstra's algorithm is not greedy.").hexdigest(),
                "now": NOW_TEXT,
            },
        )
        connection.execute(
            sql_text(
                "INSERT INTO source_anchors (anchor_id, source_id, kind, locator_key,"
                " bound_source_sha256, excerpt_sha256, created_at)"
                " VALUES ('a-page','src-1','quotation',:key,:sha,NULL,:now)"
            ),
            {"key": page_key, "sha": SHA, "now": NOW_TEXT},
        )
        connection.execute(
            sql_text(
                "INSERT INTO identifier_records (identifier_id, task_id, scheme, value,"
                " supplied_by, supplied_by_id, resolution_state, resolution_detail,"
                " resolved_by, resolved_at, created_at)"
                " VALUES ('id-1','task-1','doi','10.1234/abc.def','model','run-1',"
                "'unresolved',NULL,NULL,NULL,:now)"
            ),
            {"now": NOW_TEXT},
        )
    connection.commit()
    yield connection, LabCairnIndex(connection)
    engine.dispose()


def _claim(
    evidence_id: str,
    *,
    identifiers: tuple[str, ...] = (),
    status: str = "extracted",
    created_by: str = "rule",
    log: tuple[VerificationRecord, ...] = (),
) -> EvidenceRecord:
    span = "Dijkstra's algorithm is not greedy."
    return EvidenceRecord(
        evidence_id=evidence_id,
        task_id="task-1",
        kind=EvidenceKind.CLAIM,
        text="A claim about the greedy characterisation.",
        anchor_ids=("a-page",),
        identifier_ids=identifiers,
        extracted_span=span,
        extracted_span_sha256=hashlib.sha256(span.encode()).hexdigest(),
        source_content_hash=SHA,
        status=VerificationStatus(status),
        created_by=EvidenceCreator(created_by),
        created_by_id="rule-1",
        verification_log=log,
        created_at=NOW,
    )


def _c1_pass() -> VerificationRecord:
    return VerificationRecord(
        check=CheckKind.C1,
        checker_id=C1_CHECKER_ID,
        outcome=CheckOutcome.PASS,
        detail="the source exists and the locator resolves",
        checked_at=NOW,
    )


def test_an_identifier_round_trips(ledger: Store) -> None:
    connection, _index = ledger
    put_identifier(
        connection,
        _identifier(
            identifier_id="id-2",
            scheme=IdentifierScheme.ARXIV,
            value="2401.01234",
            supplied_by=IdentifierProvenance.INGESTION,
            supplied_by_id="ingest-1",
            resolution_state=ResolutionState.NOT_ATTEMPTED,
            resolution_detail="the metadata named it; nothing resolved it",
        ),
    )
    loaded = load_identifier(connection, "id-2")
    assert loaded is not None
    assert loaded.scheme is IdentifierScheme.ARXIV
    assert loaded.supplied_by is IdentifierProvenance.INGESTION
    assert loaded.resolution_state is ResolutionState.NOT_ATTEMPTED


def test_a_record_carrying_an_identifier_round_trips(ledger: Store) -> None:
    """The first clause, at the layer a report reads: the id survives the store."""
    connection, _index = ledger
    record = _claim("ev-1", identifiers=("id-1",))
    append_record(connection, record)
    loaded = load_record(connection, "ev-1")
    assert loaded is not None
    assert loaded.identifier_ids == ("id-1",)


def test_a_record_citing_an_identifier_nobody_recorded_is_refused(ledger: Store) -> None:
    connection, _index = ledger
    with pytest.raises(LedgerError, match="holds no row for"):
        append_record(connection, _claim("ev-1", identifiers=("id-nowhere",)))


def test_a_record_citing_another_tasks_identifier_is_refused(ledger: Store) -> None:
    connection, _index = ledger
    put_identifier(connection, _identifier(identifier_id="id-other", task_id="task-2"))
    with pytest.raises(LedgerError, match="belongs to task"):
        append_record(connection, _claim("ev-1", identifiers=("id-other",)))


def test_a_verified_record_cannot_rest_on_an_unresolved_identifier(ledger: Store) -> None:
    """The fourth clause, at the store: the refusal names the id and its state."""
    connection, index = ledger
    append_record(connection, _claim("ev-1", identifiers=("id-1",), log=(_c1_pass(),)))
    with pytest.raises(LedgerError, match=r"id-1.*unresolved"):
        advance(
            connection,
            "ev-1",
            VerificationStatus.VERIFIED_BY_RULE,
            index=index,
            checks=(),
            checked_at=NOW,
        )
    after = load_record(connection, "ev-1")
    assert after is not None
    assert after.status is VerificationStatus.EXTRACTED, (
        "a refused move leaves the record where it was"
    )


def test_an_attested_record_cannot_rest_on_an_unresolved_identifier(ledger: Store) -> None:
    connection, _index = ledger
    record = _claim(
        "ev-1",
        identifiers=("id-1",),
        status="extracted",
        created_by="user",
    )
    append_record(connection, record)
    with pytest.raises(LedgerError, match="nothing resolved"):
        attest(
            connection,
            "ev-1",
            user_id="the-owner",
            note="I read it myself",
            checked_at=NOW,
        )


def test_a_verified_record_may_rest_on_a_resolved_identifier(ledger: Store) -> None:
    """The rule is about *unresolved*, not about identifiers: resolving unblocks."""
    connection, index = ledger
    confirm_resolution(
        connection,
        "id-1",
        resolved_by="the-owner",
        detail="the DOI resolves to the paper",
        resolved_at=NOW,
    )
    append_record(connection, _claim("ev-1", identifiers=("id-1",), log=(_c1_pass(),)))
    moved = advance(
        connection,
        "ev-1",
        VerificationStatus.VERIFIED_BY_RULE,
        index=index,
        checks=(),
        checked_at=NOW,
    )
    assert moved.status is VerificationStatus.VERIFIED_BY_RULE


def test_a_planned_proposal_may_carry_an_unresolved_identifier(ledger: Store) -> None:
    """A model's DOI on a planned proposal is data; refusing it would refuse provenance."""
    connection, _index = ledger
    record = _claim("ev-1", identifiers=("id-1",), status="planned")
    append_record(connection, record)
    loaded = load_record(connection, "ev-1")
    assert loaded is not None
    assert loaded.status is VerificationStatus.PLANNED
    assert loaded.identifier_ids == ("id-1",)


# --------------------------------------------------------------------------- #
# the gate: the report's last door
# --------------------------------------------------------------------------- #


def test_the_gate_names_an_identifier_a_citable_record_rests_on(ledger: Store) -> None:
    connection, index = ledger
    append_record(connection, _claim("ev-1", identifiers=("id-1",), log=(_c1_pass(),)))
    confirm_resolution(
        connection,
        "id-1",
        resolved_by="the-owner",
        detail="the DOI resolves to the paper",
        resolved_at=NOW,
    )
    moved = advance(
        connection,
        "ev-1",
        VerificationStatus.VERIFIED_BY_RULE,
        index=index,
        checks=(),
        checked_at=NOW,
    )
    assert moved.status is VerificationStatus.VERIFIED_BY_RULE
    # Now put a second, unresolved identifier on the shelf and rewrite the
    # record's citations directly, the way a writer that went around the
    # store would -- the gate is the door such a writer has not passed.
    put_identifier(
        connection,
        _identifier(
            identifier_id="id-2",
            scheme=IdentifierScheme.ARXIV,
            value="2401.01234",
            supplied_by=IdentifierProvenance.MODEL,
            supplied_by_id="run-2",
        ),
    )
    connection.execute(
        sql_text(
            "INSERT INTO evidence_identifiers (evidence_id, position, identifier_id)"
            " VALUES ('ev-1', 1, 'id-2')"
        )
    )
    result = evaluate_task(connection, task_id="task-1", index=index)
    assert not result.passed
    findings = [f for f in result.findings if f.kind == "unresolved_identifier"]
    assert findings, "a citeable record resting on an unresolved identifier must be named"
    reason = findings[0].reason
    assert "id-2" in reason and "unresolved" in reason
    assert "model" in reason, "the finding says the identifier was a model's proposal"
    assert "proposing is not checking" in reason


def test_the_gate_is_quiet_about_a_resolved_identifier(ledger: Store) -> None:
    connection, index = ledger
    append_record(connection, _claim("ev-1", identifiers=("id-1",), log=(_c1_pass(),)))
    confirm_resolution(
        connection,
        "id-1",
        resolved_by="the-owner",
        detail="the DOI resolves to the paper",
        resolved_at=NOW,
    )
    advance(
        connection,
        "ev-1",
        VerificationStatus.VERIFIED_BY_RULE,
        index=index,
        checks=(),
        checked_at=NOW,
    )
    result = evaluate_task(connection, task_id="task-1", index=index)
    assert not [f for f in result.findings if f.kind == "unresolved_identifier"]


# --------------------------------------------------------------------------- #
# resolution: recorded, not sent; confirmed, not checked
# --------------------------------------------------------------------------- #


@pytest.fixture()
def forbid_sockets(monkeypatch: pytest.MonkeyPatch) -> None:
    """The machine's doors are shut, so "nothing reached the network" is measured."""

    def _no_socket(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("an identifier operation opened a network socket")

    import socket
    import urllib.request

    monkeypatch.setattr(socket, "socket", _no_socket)
    monkeypatch.setattr(socket, "create_connection", _no_socket)
    monkeypatch.setattr(urllib.request, "urlopen", _no_socket)


def test_a_resolution_request_is_recorded_not_attempted_and_not_sent(
    ledger: Store, forbid_sockets: None
) -> None:
    """The second clause. The honest answer to "resolve this" lands as a row."""
    connection, _index = ledger
    resolved = request_resolution(
        connection,
        "id-1",
        detail="the report needs to know where this DOI points",
        requested_at=NOW,
    )
    assert resolved.resolution_state is ResolutionState.NOT_ATTEMPTED
    assert resolved.resolved_by is None and resolved.resolved_at is None
    assert "cannot consent an outbound lookup" in (resolved.resolution_detail or "")
    assert "the report needs to know" in (resolved.resolution_detail or ""), (
        "the row keeps both the caller's reason and the boundary's own"
    )


def test_an_already_resolved_identifier_is_not_rewritten_by_a_request(
    ledger: Store, forbid_sockets: None
) -> None:
    connection, _index = ledger
    confirm_resolution(
        connection,
        "id-1",
        resolved_by="the-owner",
        detail="the DOI resolves to the paper",
        resolved_at=NOW,
    )
    with pytest.raises(IdentifierError, match="already resolved"):
        request_resolution(connection, "id-1", detail="again", requested_at=NOW)


def test_a_person_confirms_a_resolution_and_signs_it(ledger: Store) -> None:
    connection, _index = ledger
    resolved = confirm_resolution(
        connection,
        "id-1",
        resolved_by="the-owner",
        detail="the DOI resolves to the paper",
        resolved_at=NOW,
    )
    assert resolved.resolution_state is ResolutionState.RESOLVED
    assert resolved.resolved_by == "the-owner"
    with pytest.raises(IdentifierError, match="not unwritten"):
        confirm_resolution(
            connection,
            "id-1",
            resolved_by="someone-else",
            detail="a second opinion",
            resolved_at=NOW,
        )
    # And the state machine is one-way: not_attempted does not go back to
    # unresolved, and resolved does not go anywhere at all.
    assert load_identifier(connection, "id-1") is not None
    task_ids = {
        identifier.identifier_id for identifier in load_task_identifiers(connection, "task-1")
    }
    assert task_ids == {"id-1"}


def test_a_request_and_a_confirmation_can_both_be_read_back(ledger: Store) -> None:
    """The third clause, at the layer a report asks: the state is queryable."""
    connection, _index = ledger
    put_identifier(
        connection,
        _identifier(
            identifier_id="id-2",
            scheme=IdentifierScheme.ARXIV,
            value="2401.01234",
            supplied_by=IdentifierProvenance.PERSON,
            supplied_by_id="the-owner",
        ),
    )
    request_resolution(connection, "id-1", detail="asked", requested_at=NOW)
    states = {
        identifier.identifier_id: identifier.resolution_state
        for identifier in load_task_identifiers(connection, "task-1")
    }
    assert states == {
        "id-1": ResolutionState.NOT_ATTEMPTED,
        "id-2": ResolutionState.UNRESOLVED,
    }


# --------------------------------------------------------------------------- #
# proposing is not checking
# --------------------------------------------------------------------------- #


def test_confirming_a_models_proposal_writes_no_check_and_moves_no_status(
    ledger: Store,
) -> None:
    """The fifth clause. The record's log is byte-identical across a resolution."""
    connection, _index = ledger
    record = _claim("ev-1", identifiers=("id-1",), status="planned")
    append_record(connection, record)
    before = load_record(connection, "ev-1")
    assert before is not None

    confirm_resolution(
        connection,
        "id-1",
        resolved_by="the-owner",
        detail="I checked the model's DOI by hand",
        resolved_at=NOW,
    )
    after = load_record(connection, "ev-1")
    assert after is not None
    assert after.model_dump_json() == before.model_dump_json(), (
        "resolving the identifier changed the record: a resolution is not a"
        " citation check, and a model-supplied identifier confirmed by a"
        " person is still not one"
    )


def test_a_verified_record_still_needs_its_checks_beside_a_resolved_identifier(
    ledger: Store,
) -> None:
    """A resolved identifier is not a shortcut past the log."""
    connection, index = ledger
    confirm_resolution(
        connection,
        "id-1",
        resolved_by="the-owner",
        detail="the DOI resolves to the paper",
        resolved_at=NOW,
    )
    append_record(connection, _claim("ev-1", identifiers=("id-1",)))
    with pytest.raises(LedgerError, match="requires a VerificationRecord"):
        # The log holds no passing entry from C1-C3, and the identifier the
        # record cites is resolved: neither fact stands in for the other.
        # A resolution is about where a citation points; a check is about
        # whether the material says what the record says it does.
        advance(
            connection,
            "ev-1",
            VerificationStatus.VERIFIED_BY_RULE,
            index=index,
            checks=(),
            checked_at=NOW,
        )
    still = load_record(connection, "ev-1")
    assert still is not None
    assert still.status is VerificationStatus.EXTRACTED
