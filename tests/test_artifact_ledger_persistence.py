"""The ledger on disk: the record outlives the process and still re-hashes.

The in-memory ledger's two properties are tested in ``test_skill_ledger.py``.
What is new here is where the entries live between reads, and every witness is
written against a *second* ledger instance or a reopened engine — a ledger that
answered from something it remembered would pass a test that only read it back
through the instance that wrote it.

Five properties, one test each:

* a new ledger on the same database loads the same artifact and the same digest;
* a restart — engine disposed and a fresh one opened on the same file — keeps the
  history and the current view per stage;
* tampering with the stored payload is caught by ``verify_all`` and by ``load``,
  which is only possible if the read goes to the table's bytes;
* a second record for one stage appends a second row and moves ``by_stage``
  forward, with the first row still readable;
* the stored payload is the canonical JSON ``artifact_digest`` hashes, not a
  second serialisation that happens to parse.

A sixth witness covers the column that makes a durable row safe across releases:
an entry written under another digest algorithm is refused instead of being
compared. And a seventh covers the store's isolation, because "one database,
one ledger" is an assumption the orchestrator's per-run contract does not allow.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import text as sql_text
from test_skill_support import build_inventory, make_objective
from test_store_support import StoreEnv
from test_store_support import env as _shared_env

from labcairn.db.ledger import DEFAULT_LEDGER_ID, SqliteArtifactLedgerStore
from labcairn.db.session import create_db_engine, create_session_factory
from labcairn.skills import (
    ArtifactKind,
    ArtifactLedger,
    ArtifactSubstitutedError,
    LedgerAlgorithmError,
    RecordedArtifact,
    StageName,
    artifact_digest,
)

pytestmark = pytest.mark.integration

#: pytest resolves a fixture by the parameter name, so the shared ``env``
#: fixture is bound under that name here. Importing it directly and taking
#: ``env`` as a parameter is an F811 redefinition; the alias reads as a plain
#: assignment, which is the same pattern ``test_store_migrations.py`` uses.
env = _shared_env

NOW = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
LINEAGE = ("a" * 64,)


def _ledger(env: StoreEnv, ledger_id: str = DEFAULT_LEDGER_ID) -> ArtifactLedger:
    """A ledger over *env*'s database. A new store every time, on purpose."""
    return ArtifactLedger(SqliteArtifactLedgerStore(env.factory, ledger_id=ledger_id))


def _record_objective(ledger: ArtifactLedger, text: str = "what is X?") -> RecordedArtifact:
    """Record a root objective and return the recorded entry."""
    return ledger.record(
        ArtifactKind.RESEARCH_OBJECTIVE,
        StageName.INTAKE,
        make_objective("task", objective=text),
        produced_by=StageName.INTAKE,
        now=NOW,
    )


def test_a_new_instance_on_the_same_database_loads_the_same_entry(env: StoreEnv) -> None:
    """Record in one ledger, read in another: same artifact, same digest."""
    recorded = _record_objective(_ledger(env))

    reopened = _ledger(env)
    loaded = reopened.load(StageName.INTAKE, ArtifactKind.RESEARCH_OBJECTIVE)

    assert loaded.artifact == recorded.artifact
    assert loaded.digest == recorded.digest
    assert loaded.digest == artifact_digest(recorded.artifact)
    assert reopened.history == [recorded]
    assert reopened.completed_stages() == (StageName.INTAKE,)


def test_history_and_by_stage_survive_a_restart(env: StoreEnv) -> None:
    """Dispose the engine, open a new one on the same file: the record is there."""
    first = _ledger(env)
    objective = _record_objective(first)
    first.record(
        ArtifactKind.SOURCE_INVENTORY,
        StageName.INVENTORY,
        build_inventory((objective.digest,)),
        produced_by=StageName.INVENTORY,
        now=NOW,
    )

    env.session.close()
    env.dispose()

    engine = create_db_engine(env.db_path)
    factory = create_session_factory(engine)
    try:
        reopened = ArtifactLedger(SqliteArtifactLedgerStore(factory))

        assert [entry.stage for entry in reopened.history] == [
            StageName.INTAKE,
            StageName.INVENTORY,
        ]
        assert reopened.completed_stages() == (StageName.INTAKE, StageName.INVENTORY)
        assert reopened.by_stage[StageName.INTAKE].digest == objective.digest
        # The read-time check runs against the bytes the new process read.
        loaded = reopened.load(StageName.INVENTORY, ArtifactKind.SOURCE_INVENTORY)
        assert artifact_digest(loaded.artifact) == loaded.digest
    finally:
        engine.dispose()


def test_verify_all_reports_a_payload_changed_in_the_table(env: StoreEnv) -> None:
    """The tamper is in the stored bytes, and verification is what finds it."""
    recorded = _record_objective(_ledger(env))

    # Change the artifact's content in the table, leaving the digest column
    # exactly as it was -- the substitution the read-time check exists for.
    with env.factory.begin() as session:
        row = session.execute(sql_text("SELECT payload FROM artifact_ledger_entries")).one()
        payload = json.loads(row.payload)
        payload["objective"] = "a different objective"
        tampered = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        session.execute(
            sql_text("UPDATE artifact_ledger_entries SET payload = :payload"),
            {"payload": tampered},
        )

    reopened = _ledger(env)
    mismatches = reopened.verify_all()

    assert len(mismatches) == 1
    assert mismatches[0].stage is StageName.INTAKE
    assert mismatches[0].recorded_digest == recorded.digest
    assert mismatches[0].actual_digest != recorded.digest
    with pytest.raises(ArtifactSubstitutedError):
        reopened.load(StageName.INTAKE, ArtifactKind.RESEARCH_OBJECTIVE)


def test_a_second_record_for_a_stage_appends_and_moves_by_stage(env: StoreEnv) -> None:
    """History keeps both; ``by_stage`` points at the latest; the order holds."""
    ledger = _ledger(env)
    first = _record_objective(ledger, "the first objective")
    second = _record_objective(ledger, "the second objective")

    reopened = _ledger(env)

    assert len(reopened.history) == 2
    assert [entry.digest for entry in reopened.history] == [first.digest, second.digest]
    assert reopened.by_stage[StageName.INTAKE].digest == second.digest
    assert reopened.completed_stages() == (StageName.INTAKE,)


def test_the_stored_payload_is_the_canonical_json_the_digest_is_over(env: StoreEnv) -> None:
    """One serialisation, stored and hashed; a re-parse keeps the digest."""
    artifact = build_inventory(LINEAGE, materials=(("论文.pdf", "b" * 64, True),))
    recorded = _ledger(env).record(
        ArtifactKind.SOURCE_INVENTORY,
        StageName.INVENTORY,
        artifact,
        produced_by=StageName.INVENTORY,
        now=NOW,
    )

    with env.factory() as session:
        row = session.execute(sql_text("SELECT payload, digest FROM artifact_ledger_entries")).one()

    assert row.payload == artifact.json_canonical()
    assert row.digest == artifact_digest(artifact) == recorded.digest

    loaded = _ledger(env).load(StageName.INVENTORY, ArtifactKind.SOURCE_INVENTORY)
    assert artifact_digest(loaded.artifact) == row.digest
    assert loaded.artifact == artifact


def test_an_entry_written_under_another_algorithm_is_refused(env: StoreEnv) -> None:
    """A digest from a different algorithm is not evidence, and is not compared."""
    _record_objective(_ledger(env))

    with env.factory.begin() as session:
        session.execute(
            sql_text("UPDATE artifact_ledger_entries SET digest_algorithm = 'sha256/other/v9'")
        )

    with pytest.raises(LedgerAlgorithmError):
        _ledger(env).load(StageName.INTAKE, ArtifactKind.RESEARCH_OBJECTIVE)


def test_two_ledgers_on_one_database_do_not_see_each_other(env: StoreEnv) -> None:
    """The ledger id, not the database, is the scope of a ledger."""
    _record_objective(_ledger(env, "run-a"))

    assert _ledger(env, "run-b").history == []
    assert _ledger(env, "run-a").completed_stages() == (StageName.INTAKE,)
