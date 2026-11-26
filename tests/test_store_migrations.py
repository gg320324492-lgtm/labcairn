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
        # Phase 4 (LC-P4-CAP). The model's proposal and the reviewer's
        # verdict, keyed by the opinion each answers. Two tables, never one:
        # ADR-0016's rule that a suggestion and its decision are separate
        # records is made durable here -- reading one must not read as the
        # other. The apply step reads the approved set from these rows.
        "review_suggestions",
        "review_decisions",
        # Phase 4 (P4-MS). The multi-source index's first slice: the paper's
        # revision trajectory, one row per indexed entry with the provenance
        # §8.2 requires, and the FTS5 index over the entries' digests. The
        # FTS table is the second deliberately-ORM-less table here, after
        # ``evidence_fts``, for the same reason it is listed by hand.
        "trajectory_index_rows",
        "trajectory_fts",
        # Phase 4 (P4-CAP, real-model loop). One row per loop run: the
        # budget's own account -- mode, model id, counts, the stop that
        # fired -- without which a ceiling would bound an unrecorded spend.
        "model_suggestion_runs",
        # Phase 4 (P4-MS), second source. A deck's objects -- titles, body
        # text, speaker notes, table rows and picture names -- one row per
        # indexed object with the provenance §8.3 requires, and the FTS5
        # index over the objects' text. Listed by hand for the same reason
        # the two FTS tables above are.
        "ppt_index_rows",
        "ppt_fts",
        # P4-MS third source (§8.4): the meeting-text index -- one row per
        # transcript entry or organised paragraph with the provenance §8.3
        # requires (record index, container timestamp when it has one,
        # fingerprint), and the FTS5 index over the records' text. Listed
        # by hand for the same reason the deck index's two tables are.
        "meeting_index_rows",
        "meeting_fts",
        # Phase 4 (P4-PILOT §9.4). The real trial's in-system issue record:
        # one row per problem, naming what it happened to (task, version,
        # opinion), where it happened (the operation step), what the user
        # saw, how long it took and how often it was retried, under the two
        # closed vocabularies -- severity (blocker/serious/minor/suggestion)
        # and type (function/interface/performance/model/documentation). The
        # unified feedback form records the subjective experience; this
        # table is the system-side record the form's line points at.
        "pilot_issues",
        # ADR-0002 §Contracts. The capability probe's record: one row per
        # ``(endpoint, model, protocol)``, carrying the outcome of each
        # capability, the one-liner that explains it, the capabilities a
        # request was issued for, and when the probe ran. Without it a probe
        # result was a thing a document could record and the product could
        # not -- ``doctor`` reported every capability as unverified however
        # many times the endpoint had actually been asked.
        "probe_records",
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


def test_the_chain_has_exactly_one_head() -> None:
    """One head, no branching.

    **A second ``down_revision`` pointing at an existing revision forks the
    chain**, and alembic then refuses to say what "head" means. That failure
    is not a red test: it is a refused upgrade on a machine that deploys,
    which is the worst place to discover it.

    **The tip's parent is a real revision and is not the tip.** A revision
    that names a parent that does not exist, or names itself, is caught
    here rather than by the first deployment that tries to build it.

    The numbers are not hard-coded: a future revision legitimately changes
    the head, and this test is about the shape of the chain rather than
    about which revision is currently at the top of it.
    """
    scripts = ScriptDirectory(str(MIGRATIONS_DIR))
    heads = scripts.get_heads()
    assert len(heads) == 1, f"the chain has {len(heads)} heads: {sorted(heads)}"

    head = scripts.get_revision(heads[0])
    assert head.down_revision is not None, "the tip of the chain must have a parent"
    assert head.down_revision != head.revision, "a revision cannot be its own parent"
    reachable = {r.revision for r in scripts.walk_revisions()}
    assert head.down_revision in reachable, (
        f"the tip's parent {head.down_revision} is not among {sorted(reachable)}"
    )


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


# ---------------------------------------------------------------------------
# The event vocabulary a store that predates it must still be able to reach
# ---------------------------------------------------------------------------


def _insert_a_denied_event(path: Path, event_id: str) -> None:
    """Write one ``operation_denied`` event the way a raw writer would.

    The foreign keys are deferred and SQLite does not check them unless it is
    asked to, so the row only has to satisfy the table's CHECK constraints --
    which is exactly what the vocabulary is.
    """
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "INSERT INTO events (seq, event_id, task_id, run_id, stage_id, "
            "operation_id, type, from_state, to_state, schema_version, "
            "occurred_at, document, payload) "
            "VALUES (1, ?, 'task-1', 'run-1', 'stage-1', 'op-1', "
            "'operation_denied', 'intent', 'denied', 1, '2026-11-25T00:00:00Z', "
            "'{}', '{}')",
            (event_id,),
        )
        connection.commit()
    finally:
        connection.close()


def test_a_store_built_before_the_new_event_type_reaches_it_after_the_upgrade(
    tmp_path: Path,
) -> None:
    """The vocabulary has to reach a store that was built before it carried it.

    Revision 0001 was amended to carry ``operation_denied``, on the ground
    that the product never migrates an existing workspace. That ground does
    not hold for every store: alembic's upgrade path exists, the repository
    witnesses it, and the 0.1.0 installer has been in users' hands since
    2026-11-24. A store built before the amendment keeps the constraints it
    was built with, because alembic does not run the first migration again.

    So revision 0032 rebuilds the table for those stores. This witnesses the
    rebuild by making the older shape the thing it starts from: the
    downgrade puts the pre-amendment vocabulary back, and the upgrade has to
    carry the type into it.

    Red by: the upgrade leaving the type out of the vocabulary, which the
    refusal below would then not raise.
    """
    path = tmp_path / "vocabulary.db"
    upgrade_to_head(path)

    alembic_command.downgrade(alembic_config(path), "0031")
    with pytest.raises(sqlite3.IntegrityError, match="ck_events_type_is_closed_vocabulary"):
        _insert_a_denied_event(path, "denied-before")

    alembic_command.upgrade(alembic_config(path), "head")
    _insert_a_denied_event(path, "denied-after")

    connection = sqlite3.connect(path)
    try:
        count = connection.execute(
            "SELECT count(*) FROM events WHERE type = 'operation_denied'"
        ).fetchone()[0]
    finally:
        connection.close()
    assert count == 1, "the event the upgrade made possible was not written"


def _insert_an_event(path: Path, event_id: str, seq: int) -> None:
    """Write one event into a store, the way the store held them before.

    ``task_created`` is a task-level event: it carries no run, no stage and
    no transition, so it satisfies the vocabulary of any revision.
    """
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "INSERT INTO events (seq, event_id, task_id, type, schema_version, "
            "occurred_at, document, payload) "
            "VALUES (?, ?, 'task-1', 'task_created', 1, '2026-11-25T00:00:00Z', "
            "'{}', '{}')",
            (seq, event_id),
        )
        connection.commit()
    finally:
        connection.close()


def _event_rows(path: Path) -> list[tuple[int, int, str, str]]:
    connection = sqlite3.connect(path)
    try:
        return list(
            connection.execute("SELECT id, seq, event_id, type FROM events ORDER BY id").fetchall()
        )
    finally:
        connection.close()


def _event_indexes(path: Path) -> set[str]:
    connection = sqlite3.connect(path)
    try:
        return {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'events'"
            ).fetchall()
        }
    finally:
        connection.close()


def test_the_rebuild_carries_the_rows_and_the_indexes(tmp_path: Path) -> None:
    """Revision 0032 rebuilds the table, and a rebuild has to carry what was in it.

    **The witness the other witness cannot give.** The one above inserts its
    row *after* the upgrade, so a rebuild that lost every row would pass it.
    Revision 0032 is a destructive operation on a user's store -- the 0.1.0
    installer has been in users' hands since 2026-11-24 -- so what the
    rebuild carries is the property to hold, and it has to be measured on a
    store that held rows before the upgrade.

    The rows come back **with their ids**, because the ids are the table's
    own identity and a copy that renumbered them would break anything that
    holds one.

    Red by: the copy dropping a row, renumbering it, or the rebuild leaving
    an index behind.
    """
    path = tmp_path / "carry.db"
    alembic_command.upgrade(alembic_config(path), "0031")
    for index in range(1, 4):
        _insert_an_event(path, f"event-{index}", index)
    before = _event_rows(path)
    assert len(before) == 3, "the store did not take the rows before the upgrade"
    indexes_before = _event_indexes(path)

    alembic_command.upgrade(alembic_config(path), "head")

    assert _event_rows(path) == before, "the rebuild did not carry the rows as they were"
    indexes_after = _event_indexes(path)
    assert indexes_after == indexes_before, (
        "the rebuild changed the table's indexes: "
        f"{sorted(indexes_before)} became {sorted(indexes_after)}"
    )


# ---------------------------------------------------------------------------
# The refusal vocabulary a store at the previous head must still reach
# ---------------------------------------------------------------------------


def _insert_a_refusal_event(path: Path, event_id: str) -> None:
    """Write one ``refusal_recorded`` event the way a raw writer would.

    The row names no Run, no Stage, no Operation and no transition, because
    the vocabulary says a refusal is an annotation about the task rather
    than an attempt inside a run -- so the four CHECK constraints are all
    exercised by the same insert.
    """
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "INSERT INTO events (seq, event_id, task_id, run_id, stage_id, "
            "operation_id, type, from_state, to_state, schema_version, "
            "occurred_at, document, payload) "
            "VALUES (1, ?, 'task-1', NULL, NULL, NULL, "
            "'refusal_recorded', NULL, NULL, 1, '2026-11-26T00:00:00Z', "
            "'{}', '{}')",
            (event_id,),
        )
        connection.commit()
    finally:
        connection.close()


def test_a_store_at_the_previous_head_reaches_the_refusal_event_after_the_upgrade(
    tmp_path: Path,
) -> None:
    """The refusal type has to reach a store that was built before it.

    A store created at 0032 keeps the four vocabulary constraints it was
    built with, because alembic does not run an earlier revision again. So
    revision 0033 rebuilds the events table for those stores, and this
    witnesses both halves of the shape: the downgrade puts the 0032
    vocabulary back, and the upgrade carries ``refusal_recorded`` into it.

    The inserted row is also the constraint witness. It carries no
    ``run_id``, no ``operation_id`` and no transition, so it proves the new
    type is in the three "must not" sets as well as in the closed list --
    a vocabulary that listed the type but left it in the run-scoped or
    transition sets would refuse the very event the product writes.

    Red by: the upgrade leaving the type out of the vocabulary (the insert
    after the upgrade would raise), or the downgrade leaving it in (the
    insert before the upgrade would not raise).
    """
    path = tmp_path / "refusal-vocabulary.db"
    upgrade_to_head(path)

    alembic_command.downgrade(alembic_config(path), "0032")
    with pytest.raises(sqlite3.IntegrityError, match="ck_events_type_is_closed_vocabulary"):
        _insert_a_refusal_event(path, "refused-before")

    alembic_command.upgrade(alembic_config(path), "head")
    _insert_a_refusal_event(path, "refused-after")

    connection = sqlite3.connect(path)
    try:
        count = connection.execute(
            "SELECT count(*) FROM events WHERE type = 'refusal_recorded'"
        ).fetchone()[0]
    finally:
        connection.close()
    assert count == 1, "the refusal event did not land in the store after the upgrade"


def _insert_a_source_removed_event(path: Path, event_id: str) -> None:
    """Write one ``source_removed`` event the way a raw writer would.

    The row names no Run, no Stage, no Operation and no transition, because
    the vocabulary says a removal is an annotation about the task rather
    than an attempt inside a run -- so the four CHECK constraints are all
    exercised by the same insert.
    """
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "INSERT INTO events (seq, event_id, task_id, run_id, stage_id, "
            "operation_id, type, from_state, to_state, schema_version, "
            "occurred_at, document, payload) "
            "VALUES (1, ?, 'task-1', NULL, NULL, NULL, "
            "'source_removed', NULL, NULL, 1, '2026-11-27T00:00:00Z', "
            "'{}', '{}')",
            (event_id,),
        )
        connection.commit()
    finally:
        connection.close()


def test_a_store_at_the_previous_head_reaches_the_source_removal_event_after_the_upgrade(
    tmp_path: Path,
) -> None:
    """The removal type has to reach a store that was built before it.

    A store created at 0033 keeps the four vocabulary constraints it was
    built with, because alembic does not run an earlier revision again. So
    revision 0034 rebuilds the events table for those stores, and this
    witnesses both halves of the shape: the downgrade puts the 0033
    vocabulary back, and the upgrade carries ``source_removed`` into it.

    The inserted row is also the constraint witness. It carries no
    ``run_id``, no ``operation_id`` and no transition, so it proves the new
    type is in the three "must not" sets as well as in the closed list --
    a vocabulary that listed the type but left it in the run-scoped or
    transition sets would refuse the very event the product writes.

    Red by: the upgrade leaving the type out of the vocabulary (the insert
    after the upgrade would raise), or the downgrade leaving it in (the
    insert before the upgrade would not raise).
    """
    path = tmp_path / "removal-vocabulary.db"
    upgrade_to_head(path)

    alembic_command.downgrade(alembic_config(path), "0033")
    with pytest.raises(sqlite3.IntegrityError, match="ck_events_type_is_closed_vocabulary"):
        _insert_a_source_removed_event(path, "removed-before")

    alembic_command.upgrade(alembic_config(path), "head")
    _insert_a_source_removed_event(path, "removed-after")

    connection = sqlite3.connect(path)
    try:
        count = connection.execute(
            "SELECT count(*) FROM events WHERE type = 'source_removed'"
        ).fetchone()[0]
    finally:
        connection.close()
    assert count == 1, "the removal event did not land in the store after the upgrade"
