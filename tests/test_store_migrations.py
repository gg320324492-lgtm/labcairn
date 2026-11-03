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

import hashlib
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from alembic import command as alembic_command
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, Table, UniqueConstraint, inspect, text
from store_support import (  # noqa: F401
    StoreEnv,
    db_path,
    db_path_for,
    frozen_clock,
    make_run,
    make_task,
    migrated_db,
)
from store_support import env as _shared_env

from labcairn.db.base import Base
from labcairn.db.migrations import (
    ALEMBIC_INI,
    MIGRATIONS_DIR,
    alembic_config,
    current_revision,
    downgrade_to_base,
    head_revision,
    upgrade_to_head,
)
from labcairn.db.repository import TaskStore, count_events
from labcairn.db.session import create_db_engine
from labcairn.runtime.event import EventType

pytestmark = pytest.mark.integration

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
        # LC-P2-08. The mentor-trajectory line's first tables: the
        # manuscript a body of material belongs to, the versions of it, and
        # the directed edges between those versions. The edges are separate
        # because the process **branches** -- a student sent two different
        # revised drafts -- and a column on the version could hold only one
        # parent.
        "paper_projects",
        "paper_versions",
        "version_edges",
        # LC-P2-09 T00. The record of a refusal. The other two outcomes
        # leave their own mark on the graph -- an acceptance is the edge
        # with an acceptor, a correction is a second edge -- and a rejection
        # left nothing, so a proposal that was looked at and turned down was
        # indistinguishable from a proposal nobody had looked at.
        "version_edge_rejections",
        # LC-P2-06. The consent machinery. `access_grants` holds only
        # grants -- there is no row shape that means "denied", because
        # ADR-0015 D2 says the permission is denied by *absence*. And
        # `derived_copies` records the grant a copy was made under, so a
        # withdrawal can reach the copies that depended on it.
        "access_grants",
        "derived_copies",
        # LC-P2-09. The feedback chain: a comment found in a manuscript, the
        # change made in answer to it, the judgement that the change
        # answered the comment, and a later assessment of the issue. Four
        # tables because a comment, an edit, a response and an assessment
        # have different owners and different failure modes -- and one
        # comment may be answered by three edits, so a single wide table
        # would have to answer "how many comments does this edit answer?"
        # with a list, and a list is a place where a link can be lost
        # without anything failing.
        "feedback_events",
        "edit_actions",
        "response_links",
        "followup_assessments",
        "guidance_rules",
        "guidance_rule_sources",
        "guidance_rule_counterexamples",
        # LC-P2-11's next piece. The checks that decide the rules -- the
        # questions a reader can run against a manuscript and answer yes or
        # no -- and the binding that says which check decides which rule.
        # The binding names the rule's *version*, because a rule is a
        # versioned row and a new statement is a new version, so the check
        # that decides one version's words is not the check that decides
        # the next one's.
        "guidance_checks",
        "guidance_rule_checks",
        "agent_role_specs",
        # ADR-0014 D8. The third of that ADR's four tables, and the first
        # one that ever had a writer: one row per tracked change a
        # Word document records, with its text, its address and its
        # author. The reader has produced this object since LC-P2-07 and
        # nothing stored it, so a marked-up manuscript was a file the
        # archive could cite but could not describe.
        "revision_events",
        # LC-P2-09. The reply: one party's answer to another's objection,
        # read out of a response document. **It is not the mentor's
        # exchange** -- a reviewer's objection and the authors' answer
        # are the paper's own review history -- and it holds no state, no
        # decider and no evidence, because a reply is a record of what was
        # said and not a verdict on anything.
        "replies",
        # LC-P2-13. The judgement over that record: did the authors'
        # answer settle the reviewer's point. **The verdict is a row of
        # its own, never a column on the reply** -- a record of what was
        # said must not be readable as a ruling -- and a settled
        # settlement names the claim terms the operation found in the
        # manuscript's accepted text and the place in the manuscript they
        # live at, or says unknown that the change could not be placed.
        "reply_settlements",
        # LC-P2-17. The scholarly identifiers: the shelf a record cites a
        # DOI or an arXiv id from, with who supplied it and whether anyone
        # resolved it, and the join that lets an evidence record carry
        # one. Resolution is a state, not a failure -- ``not_attempted``
        # is what a resolution request records in a build that cannot
        # consent an outbound lookup.
        "identifier_records",
        "evidence_identifiers",
        # LC-P1-06's G2 debt, paid after the fact. The artifact ledger has
        # re-hashed every read since LC-P1-07, but it kept the entries in the
        # process that made them; this table is where they live now. There is
        # no UNIQUE on `stage` -- a re-run appends a second row, and the
        # current view is the latest entry per stage.
        "artifact_ledger_entries",
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


# --------------------------------------------------------------------------- #
# LC-P2-27  the anchor that covers no text: the placeholder the old shape
#           forced onto every unknown row is cleaned on the way through,
#           and a position row downgrades to what it was called before
# --------------------------------------------------------------------------- #


#: The columns of ``feedback_events``, in the order the legacy rows below
#: are spelled and read back. Spelled out rather than derived: a row the
#: migration moved is read with nothing between it and the file.
_LEGACY_COLUMNS = (
    "feedback_id",
    "project_id",
    "version_id",
    "comment_locator",
    "anchor_paragraph",
    "anchor_start",
    "anchor_end",
    "anchor_status",
    "anchor_reason",
    "anchor_text",
    "anchor_text_sha256",
    "comment_text",
    "comment_text_sha256",
    "author",
    "author_unknown_reason",
    "commented_at",
    "date_unknown_reason",
    "grade",
    "issue_key",
    "created_at",
)


def _legacy_feedback_row(feedback_id: str, *, status: str, reason: str | None) -> dict[str, object]:
    """One feedback row in the shape revision 0022 demands.

    A resolved row with real text, or the shape every unknown row was
    forced into: no anchored words, and the digest of the empty string
    standing as the integrity value of a text that is not there.
    """
    text_of = "" if status == "unknown" else "The"
    digest_of = hashlib.sha256(text_of.encode()).hexdigest()
    return {
        "feedback_id": feedback_id,
        "project_id": "proj-1",
        "version_id": "ver-1",
        "comment_locator": '{"locator_kind": "docx"}',
        "anchor_paragraph": 0,
        "anchor_start": 3 if status == "resolved" else None,
        "anchor_end": 6 if status == "resolved" else None,
        "anchor_status": status,
        "anchor_reason": reason,
        "anchor_text": text_of,
        "anchor_text_sha256": digest_of,
        "comment_text": "Define the parameter.",
        "comment_text_sha256": hashlib.sha256(b"Define the parameter.").hexdigest(),
        "author": "Prof. Lin",
        "author_unknown_reason": None,
        "commented_at": "2026-03-02T09:30:00+00:00",
        "date_unknown_reason": None,
        "grade": "observed",
        "issue_key": None,
        "created_at": "2026-03-02T09:30:00+00:00",
    }


def _sqlite_feedback_row(db: Path, feedback_id: str) -> tuple[object, ...] | None:
    """One row read straight back, in the order the columns are listed."""
    conn = sqlite3.connect(db)
    try:
        columns = ", ".join(_LEGACY_COLUMNS)
        row: tuple[object, ...] | None = conn.execute(
            f"SELECT {columns} FROM feedback_events WHERE feedback_id = ?", (feedback_id,)
        ).fetchone()
        return row
    finally:
        conn.close()


def _sqlite_write_row(db: Path, row: dict[str, object]) -> None:
    """One row written straight in, past the foreign keys.

    The row under test is the row the checks refuse or keep, not the
    foreign keys -- and the store the pilot has carries rows whose
    project and version the schema alone cannot vouch for.
    """
    conn = sqlite3.connect(db)
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        placeholders = ", ".join("?" for _ in _LEGACY_COLUMNS)
        columns = ", ".join(_LEGACY_COLUMNS)
        conn.execute(
            f"INSERT INTO feedback_events ({columns}) VALUES ({placeholders})",
            tuple(row.values()),
        )
        conn.commit()
    finally:
        conn.close()


def test_a_store_with_legacy_unknown_rows_upgrades_and_loses_nothing(tmp_path: Path) -> None:
    """The placeholder the old shape forced is cleaned; nothing else moves.

    A store recorded before the third anchor status carries unknown rows
    whose anchored text is the empty string and whose digest is the digest
    of the empty string -- values the old checks demanded, not facts the
    reader saw. The upgrade writes ``NULL`` over those two columns and
    **leaves every other column of every row exactly as it was**, resolved
    rows included. It is the data move that makes the new shape check
    installable, in the shape revision 0012's backfill took.

    **What breaks it:** a cleaning that touches more than the two columns,
    one that skips the rows -- the new check then fails to install on a
    store that carries the placeholder -- or one that rewrites the row's
    status, which is the store's data correction to decide, not a schema
    revision's.
    """
    path = db_path_for(tmp_path)
    alembic_command.upgrade(alembic_config(path), "0022")

    legacy_ids = (
        "fb-legacy-unknown",
        "fb-legacy-plain-unknown",
        "fb-legacy-resolved",
    )
    for feedback_id, status, reason in (
        (
            "fb-legacy-unknown",
            "unknown",
            "the comment's range is a position, not a passage of text",
        ),
        ("fb-legacy-plain-unknown", "unknown", "the comment carries no range markers"),
        ("fb-legacy-resolved", "resolved", None),
    ):
        _sqlite_write_row(path, _legacy_feedback_row(feedback_id, status=status, reason=reason))
    before = {fid: _sqlite_feedback_row(path, fid) for fid in legacy_ids}

    upgrade_to_head(path)

    text_ix = _LEGACY_COLUMNS.index("anchor_text")
    digest_ix = _LEGACY_COLUMNS.index("anchor_text_sha256")

    # The placeholder is gone, and only the placeholder.
    for fid in ("fb-legacy-unknown", "fb-legacy-plain-unknown"):
        after = _sqlite_feedback_row(path, fid)
        assert after is not None
        assert after[text_ix] is None and after[digest_ix] is None, (
            "the forced empty string and its digest are cleaned to NULL"
        )
        # Every other column of the row is exactly what went in.
        before_row = before[fid]
        assert before_row is not None
        expected = list(before_row)
        expected[text_ix] = None
        expected[digest_ix] = None
        assert list(after) == expected, (
            f"row {fid!r} moved no column but the two the cleaning names"
        )
    resolved = _sqlite_feedback_row(path, "fb-legacy-resolved")
    assert resolved is not None
    assert resolved[text_ix] == "The"
    assert resolved[digest_ix] == hashlib.sha256(b"The").hexdigest(), (
        "a resolved row's text and digest are untouched"
    )
    before_resolved = before["fb-legacy-resolved"]
    assert before_resolved is not None
    assert list(resolved) == list(before_resolved)


def test_a_position_row_downgrades_to_what_it_was_called_before(tmp_path: Path) -> None:
    """Downgrading calls a position what the two-word vocabulary called it.

    A ``position`` row cannot survive a downgrade to 0022 -- the two-word
    vocabulary has no word for it -- so the downgrade writes back the
    status and the reason the reader used before the third word existed,
    and the placeholder the old shape demands goes back onto the row with
    it. Upgrading again cleans it away. **The row's content survives the
    round trip; only its spelling changes.**
    """
    path = db_path_for(tmp_path)
    upgrade_to_head(path)

    position_row = _legacy_feedback_row("fb-position-roundtrip", status="resolved", reason=None)
    position_row.update(
        {
            "anchor_status": "position",
            "anchor_reason": None,
            "anchor_start": 9,
            "anchor_end": 9,
            "anchor_text": None,
            "anchor_text_sha256": None,
        }
    )
    _sqlite_write_row(path, position_row)

    alembic_command.downgrade(alembic_config(path), "0022")

    status_ix = _LEGACY_COLUMNS.index("anchor_status")
    reason_ix = _LEGACY_COLUMNS.index("anchor_reason")
    text_ix = _LEGACY_COLUMNS.index("anchor_text")
    digest_ix = _LEGACY_COLUMNS.index("anchor_text_sha256")
    downgraded = _sqlite_feedback_row(path, "fb-position-roundtrip")
    assert downgraded is not None
    assert downgraded[status_ix] == "unknown"
    assert downgraded[reason_ix] == "the comment's range is a position, not a passage of text", (
        "the reason the reader used before the third word existed is written back"
    )
    assert downgraded[text_ix] == "" and downgraded[digest_ix] == hashlib.sha256(b"").hexdigest(), (
        "the shape 0022 demands is restored"
    )

    alembic_command.upgrade(alembic_config(path), "head")
    upgraded = _sqlite_feedback_row(path, "fb-position-roundtrip")
    assert upgraded is not None
    assert upgraded[text_ix] is None and upgraded[digest_ix] is None, (
        "the upgrade cleans the placeholder it finds"
    )
    # The offset does not survive the downgrade, and the upgrade does not
    # re-derive it: a store at 0022 has nowhere to keep a placed
    # position's offset, and re-casting the row as a position again is
    # the data correction's work, not a schema revision's. The row comes
    # back as what the two-word vocabulary called it, cleaned.
    assert upgraded[status_ix] == "unknown"
    assert upgraded[_LEGACY_COLUMNS.index("anchor_start")] is None
    assert upgraded[_LEGACY_COLUMNS.index("anchor_end")] is None
