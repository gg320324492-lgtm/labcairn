"""The migration path: a fresh database builds, and a rerun is safe.

Two acceptance criteria live here. LC-P1-05 asks for "migration rerun and fresh
DB tests"; both directions are covered, plus the guard that makes them worth
anything — :func:`test_the_migrated_schema_matches_the_orm_models`, without
which a green "upgrade head" proves only that a file ran, not that the schema it
produced is the schema the application expects.

The self-containment test is deliberate. Alembic's autogenerate rendered the
custom ``UtcDateTime`` type into revision 0001 as an unimported reference to
``labcairn.db.models``, which would have made a frozen migration depend on
today's source. It is rewritten to ``sa.String()`` — the same DDL, since that is
the type's impl — and this test stops anyone putting the dependency back.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, Table, UniqueConstraint, inspect, text
from test_store_support import (  # noqa: F401
    StoreEnv,
    db_path,
    frozen_clock,
    make_run,
    make_task,
    migrated_db,
)
from test_store_support import env as _shared_env

from labcairn.db.base import Base
from labcairn.db.migrations import (
    ALEMBIC_INI,
    MIGRATIONS_DIR,
    current_revision,
    downgrade_to_base,
    head_revision,
    upgrade_to_head,
)
from labcairn.db.repository import TaskStore, count_events
from labcairn.db.session import create_db_engine
from labcairn.runtime.event import EventType

# pytest resolves a fixture by the parameter name in a test's signature, so the
# shared `env` fixture must be bound under that name here. Importing it directly
# and taking `env` as a parameter makes every signature below an F811
# redefinition; aliasing the import and rebinding it reads as a plain assignment.
env = _shared_env

#: The eight tables LC-P1-05 names. Spelled out rather than derived from the
#: metadata: a test that derives its expectations from the code it is checking
#: cannot fail when the code drifts.
EXPECTED_TABLES = frozenset(
    {
        "tasks",
        "runs",
        "stages",
        "events",
        "operations",
        "approvals",
        "checkpoints",
        "artifacts",
        # ADR-0009 / LC-P1-08. `sources` persists the material a report
        # cites; `source_texts` holds extracted text keyed by content hash,
        # extraction version and locator. The store held outputs and nothing
        # held inputs until this revision.
        "sources",
        "source_texts",
        "source_problems",
        # LC-P1-09 / ADR-0004. The ledger is the first thing in this schema
        # that must answer a question about absence: C1-C3 need somewhere to
        # resolve an anchor and re-read a value.
        "evidence_records",
        "evidence_anchors",
        "verification_records",
        # LC-P1-09 T05a. `evidence_anchors` above records *which* anchors a
        # record cites; this is what an anchor *is*, and without it C1 cannot
        # turn the `anchor_ids` a record carries into a locator.
        "source_anchors",
        # The FTS5 index, and the only table in this schema deliberately
        # absent from ``Base.metadata``. It is listed here rather than derived
        # from the metadata precisely because it is not there -- a test that
        # read its expectations from the ORM could not notice its absence, and
        # an index that quietly did not get created reads as a database with
        # nothing to find.
        "evidence_fts",
    }
)


def _tables(db: Path) -> set[str]:
    """The tables this project declares, excluding SQLite's own bookkeeping.

    ``PRAGMA table_list`` rather than ``sqlite_master``, because an FTS5
    virtual table registers **six** rows in ``sqlite_master`` -- the table
    itself plus five shadow tables (``_data``, ``_idx``, ``_content``,
    ``_docsize``, ``_config``). Listing them as expected tables would assert
    SQLite's internal layout, which is not this project's to promise and not
    guaranteed across versions.

    They are filtered by *kind*, not by name: ``table_list`` classifies each
    row as ``table``, ``virtual`` or ``shadow``, and only ``shadow`` is dropped.
    Filtering on a name prefix would be the tempting shortcut and would hide a
    real table that happened to share it.

    ``sqlite_`` names go for a different reason: ``table_list`` reports
    ``sqlite_schema`` and ``sqlite_temp_schema``, which the ``sqlite_master``
    query this replaced did not return at all. ``sqlite_`` is SQLite's reserved
    prefix, so excluding it by prefix is the rule rather than a guess.
    """
    with sqlite3.connect(str(db)) as connection:
        return {
            row[1]
            for row in connection.execute("PRAGMA table_list")
            if row[2] in ("table", "virtual") and not row[1].startswith("sqlite_")
        } - {"alembic_version"}


# --------------------------------------------------------------------------- #
# fresh database
# --------------------------------------------------------------------------- #


def test_a_fresh_database_builds_every_table(tmp_path: Path) -> None:
    """``upgrade head`` on a path that does not exist creates the whole schema."""
    target = tmp_path / "brand_new.db"
    assert not target.exists()

    assert current_revision(target) is None, "an absent file must report no revision"

    upgrade_to_head(target)

    assert target.exists()
    assert current_revision(target) == head_revision()
    assert _tables(target) == EXPECTED_TABLES


def test_a_fresh_database_is_usable_immediately(tmp_path: Path) -> None:
    """No separate "seed" step: the migrated database takes a write at once."""
    from labcairn.db.session import create_session_factory

    target = tmp_path / "usable.db"
    upgrade_to_head(target)
    engine = create_db_engine(target)
    try:
        session = create_session_factory(engine)()
        task = make_task()
        store = TaskStore(session)
        store.create_task(task)
        assert count_events(session, task.task_id) == 1
    finally:
        session.close()
        engine.dispose()


# --------------------------------------------------------------------------- #
# rerun on an existing database
# --------------------------------------------------------------------------- #


def test_rerunning_the_migration_is_a_no_op(tmp_path: Path) -> None:
    """Second and third ``upgrade head`` change nothing and lose nothing.

    This is the rerun criterion. Alembic compares ``alembic_version`` against the
    revision tree and finds nothing to apply; the assertion that the *data*
    survives is what separates "idempotent" from "quietly rebuilt".
    """
    target = tmp_path / "rerun.db"
    upgrade_to_head(target)

    from labcairn.db.session import create_session_factory

    engine = create_db_engine(target)
    session = create_session_factory(engine)()
    store = TaskStore(session)
    task = make_task()
    store.create_task(task)
    session.close()
    engine.dispose()

    for attempt in (2, 3):
        upgrade_to_head(target)
        assert current_revision(target) == head_revision(), f"rerun {attempt} moved the revision"

    engine = create_db_engine(target)
    session = create_session_factory(engine)()
    try:
        assert count_events(session, task.task_id) == 1, "a rerun lost committed data"
        assert _tables(target) == EXPECTED_TABLES
    finally:
        session.close()
        engine.dispose()


def test_downgrade_then_upgrade_rebuilds_the_same_schema(tmp_path: Path) -> None:
    """The full cycle works, so a bad revision is recoverable rather than terminal."""
    target = tmp_path / "cycle.db"
    upgrade_to_head(target)
    assert _tables(target) == EXPECTED_TABLES

    downgrade_to_base(target)
    assert current_revision(target) is None
    assert _tables(target) == set()

    upgrade_to_head(target)
    assert _tables(target) == EXPECTED_TABLES
    assert current_revision(target) == head_revision()


def test_the_repository_refuses_to_operate_on_an_unmigrated_database(tmp_path: Path) -> None:
    """Writing to an unmigrated file fails loudly instead of creating a half schema.

    ``create_all`` would quietly build the current models in a file that has no
    revision recorded, leaving a database no later migration could reason about.
    The store never calls it, so the failure has to arrive as an error.
    """
    from labcairn.db.session import create_session_factory

    target = tmp_path / "unmigrated.db"
    engine = create_db_engine(target)
    session = create_session_factory(engine)()
    try:
        store = TaskStore(session)
        with pytest.raises(Exception, match="no such table"):
            store.create_task(make_task())
    finally:
        session.rollback()
        session.close()
        engine.dispose()


# --------------------------------------------------------------------------- #
# drift guards
# --------------------------------------------------------------------------- #


def test_the_migrated_schema_matches_the_orm_models(tmp_path: Path) -> None:
    """The migration and the models describe the same schema.

    Without this, editing ``models.py`` and forgetting the migration leaves the
    application querying columns that do not exist, and every migration test
    still passes because the migration ran perfectly.

    Comparing column *names* alone was not enough, and this test was widened
    because review found real drift it could not see: revision 0003 rendered
    two ``UtcDateTime`` columns as ``sa.Text`` where the models use
    ``sa.String``. SQLite treats both identically, so nothing failed, and the
    guard that exists precisely for "a migration reported success and changed
    something else" reported nothing. Types, nullability, unique constraints
    and CHECK constraint bodies are all compared now.
    """
    target = tmp_path / "drift.db"
    upgrade_to_head(target)
    engine = create_db_engine(target)
    try:
        inspector = inspect(engine)
        for name, table in Base.metadata.tables.items():
            assert inspector.has_table(name), f"migration is missing table {name}"

            migrated = {c["name"]: c for c in inspector.get_columns(name)}
            modelled = {c.name: c for c in table.columns}
            assert set(migrated) == set(modelled), (
                f"table {name}: migration has {sorted(set(migrated) - set(modelled))} extra "
                f"and {sorted(set(modelled) - set(migrated))} missing relative to the models"
            )

            for column_name, column in modelled.items():
                seen = migrated[column_name]
                assert bool(seen["nullable"]) == bool(column.nullable), (
                    f"{name}.{column_name}: migration nullable={seen['nullable']}, "
                    f"models nullable={column.nullable}"
                )
                # The impl, not the declared type: UtcDateTime renders as
                # String, which is what a frozen migration is required to use.
                wanted = column.type.compile(dialect=engine.dialect)
                assert seen["type"].compile(dialect=engine.dialect) == wanted, (
                    f"{name}.{column_name}: migration has {seen['type']!r}, "
                    f"models compile to {wanted!r}"
                )

            assert _unique_sets(inspector, name) == _unique_sets_from_models(table), (
                f"table {name}: unique constraints differ between migration and models"
            )
            assert _check_sets(inspector, name) == _check_sets_from_models(table), (
                f"table {name}: CHECK constraints differ between migration and models"
            )
    finally:
        engine.dispose()


def _unique_sets(inspector: Any, table: str) -> set[tuple[str, ...]]:
    return {
        tuple(sorted(c["column_names"] or ())) for c in inspector.get_unique_constraints(table)
    } | {tuple(sorted(c["column_names"])) for c in inspector.get_indexes(table) if c.get("unique")}


def _unique_sets_from_models(table: Table) -> set[tuple[str, ...]]:
    found = {
        tuple(sorted(c.name for c in constraint.columns))
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    return {key for key in found if key}


def _check_sets(inspector: Any, table: str) -> set[str]:
    """Normalised CHECK bodies: whitespace collapsed, so a reformat is not drift."""
    return {norm(c.get("sqltext")) for c in inspector.get_check_constraints(table)}


def _check_sets_from_models(table: Table) -> set[str]:
    # ``sqltext`` is a TextClause at schema level, not a str.
    return {
        norm(c.sqltext.text) if hasattr(c.sqltext, "text") else norm(c.sqltext)
        for c in table.constraints
        if isinstance(c, CheckConstraint)
    }


def norm(text: str | None) -> str:
    return " ".join((text or "").split())


def test_the_migration_does_not_import_labcairn() -> None:
    """Revision 0001 is a frozen historical record, not a view of current code."""
    sources = sorted(MIGRATIONS_DIR.glob("versions/*.py"))
    assert sources, "no migration files found"
    for path in sources:
        source = path.read_text(encoding="utf-8")
        assert "import labcairn" not in source, (
            f"{path.name} imports labcairn.db; a frozen migration must not depend on "
            "the live package, whose types may change after this revision was written"
        )
        # Matched with the call parentheses so the explanatory comment above the
        # revision identifiers — which names the type it replaced — does not
        # trip the check it exists to justify.
        assert "UtcDateTime()" not in source, (
            f"{path.name} uses UtcDateTime(); render the underlying sa.String() instead"
        )


def test_the_head_revision_is_the_one_the_tests_expect() -> None:
    """Anchored rather than assumed.

    A future revision legitimately changes the head; a test that hard-codes
    ``0001`` would then fail for the wrong reason. What is asserted is that the
    head is a single, named, non-empty revision — the value a deployment would
    report — and that revision 0001 is still an ancestor of it.
    """
    head = head_revision()
    assert head, "the head revision must be named"
    scripts = ScriptDirectory(str(MIGRATIONS_DIR))
    revisions = {r.revision for r in scripts.walk_revisions()}
    assert head in revisions, f"head {head} is not among {sorted(revisions)}"
    # 0001 stays an ancestor: the original schema must remain reachable, or a
    # database built under it could not be migrated forward.
    ancestors = {r.revision for r in scripts.iterate_revisions(head, "base")}
    assert "0001" in ancestors, f"0001 is no longer reachable from head {head}"
    assert ALEMBIC_INI.is_file()


def test_migration_files_are_discovered_by_alembic() -> None:
    """``env.py``'s script_location actually resolves to the versions directory."""
    scripts = ScriptDirectory(str(MIGRATIONS_DIR))
    assert scripts.get_current_head() == head_revision()
    # A count of one was true when there was a single revision; what matters is
    # that every file on disk is reachable from head, so a migration that was
    # written and never wired into the chain is caught.
    versions = MIGRATIONS_DIR / "versions"
    on_disk = {p.stem.split("_", 1)[0] for p in versions.glob("*.py")} - {"__init__"}
    reachable = {r.revision for r in scripts.walk_revisions()}
    assert on_disk == reachable, f"on disk {sorted(on_disk)} vs reachable {sorted(reachable)}"


def test_the_schema_records_its_owner_scope(env: StoreEnv) -> None:
    """``tasks.owner_id`` is NOT NULL: Phase 1's single-user scope is structural."""
    session = env.session
    columns = {c["name"]: c for c in inspect(session.get_bind()).get_columns("tasks")}
    assert columns["owner_id"]["nullable"] is False


def test_the_events_table_declares_deferred_foreign_keys(env: StoreEnv) -> None:
    """The deferral that lets events precede their state rows is in the schema.

    Asserted from ``sqlite_master`` rather than from the ORM, so it verifies the
    migration carried the property across rather than that the model asked for it.
    """
    session = env.session
    ddl: str = session.execute(
        text("SELECT sql FROM sqlite_master WHERE name = 'events' AND type = 'table'")
    ).scalar_one()
    assert ddl.count("DEFERRABLE INITIALLY DEFERRED") == 4
    assert "AUTOINCREMENT" in ddl


def test_an_annotation_event_commits_without_a_run(env: StoreEnv) -> None:
    """End-to-end through the store: an annotation needs no Run row at all."""
    from labcairn.runtime.event import EventTransition

    session = env.session
    store = env.store()
    task = make_task()
    store.create_task(task)
    run = make_run(task.task_id)
    with store.unit(task.task_id) as work:
        work.put_run(run)
        work.emit(
            EventType.RUN_STARTED,
            run_id=run.run_id,
            transition=EventTransition(from_state="pending", to_state="running"),
        )
    # artifact_recorded is an annotation: no run_id, no transition, no state row.
    with store.unit(task.task_id) as work:
        work.emit(EventType.ARTIFACT_RECORDED)

    runs: int = session.execute(text("SELECT COUNT(*) FROM runs")).scalar_one()
    assert runs == 1
    null_runs: int = session.execute(
        text("SELECT COUNT(*) FROM events WHERE type = 'artifact_recorded' AND run_id IS NULL")
    ).scalar_one()
    assert null_runs == 1
