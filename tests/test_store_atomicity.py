"""Rollback: a crash before COMMIT must undo the events *and* the state rows.

ADR-0003 C3 states the guarantee, and this file is the evidence for it. The
mechanism under test is the awkward one — a failure in the window *between* the
events going to the database and the state rows going after them. That window
is real: ADR-0003 C3 requires events first so an ``operation_intent`` can name an
operation whose row does not exist yet, so for a moment the database holds
events describing state that has not been written.

The injection point is SQLAlchemy's ``before_cursor_execute``, not a hook in the
store. Nothing in ``labcairn.db`` knows this test exists, so what is exercised
is the production code path and the production transaction — the only way the
result means anything about the shipped implementation rather than about a
testing scaffold shaped like it.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import pytest
from sqlalchemy import event as sa_event
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_store_support import (  # noqa: F401
    StoreEnv,
    frozen_clock,
    make_run,
    make_stage,
    make_task,
)
from test_store_support import env as _shared_env

from labcairn.core.ids import TaskId
from labcairn.db.repository import count_events, events_after, last_seq
from labcairn.runtime.event import EventTransition, EventType
from labcairn.runtime.lifecycle import StageStatus

pytestmark = pytest.mark.negative

# pytest resolves a fixture by the parameter name in a test's signature, so the
# shared `env` fixture must be bound under that name here. Importing it directly
# and taking `env` as a parameter makes every signature below an F811
# redefinition; aliasing the import and rebinding it reads as a plain
# assignment instead.
env = _shared_env


class InjectedFailureError(RuntimeError):
    """Stands in for a crash, a constraint the application did not expect, or
    an operation that failed halfway. It never escapes the ``with`` block."""


def _committed_state(env: StoreEnv, task_id: TaskId) -> tuple[dict[str, int], int, list[int]]:
    """What actually got committed, read through a **fresh** session.

    A rollback assertion that reads through the failed unit's own session proves
    little: if the transaction was left un-rolled-back, that session is simply
    unusable and the test dies with a ``PendingRollbackError`` instead of naming
    what survived. A new connection answers the question that matters — did this
    data reach the database — and answers it the same way whether or not the
    implementation under test cleaned up after itself.
    """
    session = env.new_session()
    try:
        return _counts(session), last_seq(session, task_id), _all_seqs(session, task_id)
    finally:
        session.close()


def _fail_on(table: str) -> tuple[Callable[..., None], list[str]]:
    """A ``before_cursor_execute`` hook that raises on any write to *table*.

    Returns ``(hook, seen)`` where ``seen`` is the list of statements that ran,
    so a test can assert *where in the flush* the failure landed rather than
    merely that it landed.
    """

    seen: list[str] = []

    def hook(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        seen.append(statement)
        normalised = " ".join(statement.split()).lower()
        if f" into {table} " in f" {normalised} " or normalised.startswith(f"update {table} "):
            raise InjectedFailureError(f"injected failure while writing {table}")

    return hook, seen


def _all_seqs(session: Session, task_id: TaskId) -> list[int]:
    """A Task's committed ``seq`` values, read as plain ints."""
    rows: Sequence[Any] = (
        session.execute(
            text("SELECT seq FROM events WHERE task_id = :t ORDER BY seq"), {"t": str(task_id)}
        )
        .scalars()
        .all()
    )
    return [int(value) for value in rows]


def _counts(session: Session) -> dict[str, int]:
    return dict(
        session.execute(
            text(
                "SELECT 'tasks', COUNT(*) FROM tasks UNION ALL"
                " SELECT 'runs', COUNT(*) FROM runs UNION ALL"
                " SELECT 'stages', COUNT(*) FROM stages UNION ALL"
                " SELECT 'events', COUNT(*) FROM events UNION ALL"
                " SELECT 'operations', COUNT(*) FROM operations UNION ALL"
                " SELECT 'approvals', COUNT(*) FROM approvals UNION ALL"
                " SELECT 'checkpoints', COUNT(*) FROM checkpoints UNION ALL"
                " SELECT 'artifacts', COUNT(*) FROM artifacts"
            )
        ).all()
    )


# --------------------------------------------------------------------------- #
# the headline case
# --------------------------------------------------------------------------- #


def test_a_failure_between_events_and_state_rolls_back_both(env: StoreEnv) -> None:
    """Events inserted, then the state write fails: neither half survives.

    This is the exact scenario ADR-0003 C3 is written about. Before the failure
    the database holds an event describing a Stage that does not exist; after it
    the database must hold neither the event nor the counter that advanced for
    it. A rollback that removed the events but left ``last_event_seq`` advanced
    would be the worse bug of the two — it would leave a permanent hole in the
    sequence, which is precisely the property this whole design exists to
    protect.
    """
    session = env.session
    store = env.store()
    task = make_task()
    store.create_task(task)
    run = make_run(task.task_id)
    with store.unit(task.task_id) as work:
        work.put_run(run)

    before = _counts(session)
    # create_task took seq 1; the run-only unit that follows allocates none.
    assert last_seq(session, task.task_id) == 1

    stage = make_stage(task.task_id, run.run_id, status=StageStatus.ENTERED)
    hook, seen = _fail_on("stages")
    sa_event.listen(env.engine, "before_cursor_execute", hook)
    try:
        with (
            pytest.raises(InjectedFailureError, match="injected failure"),
            store.unit(task.task_id) as work,
        ):
            work.emit(
                EventType.STAGE_ENTERED,
                run_id=run.run_id,
                transition=EventTransition(from_state="pending", to_state="entered"),
            )
            work.put_stage(stage)
    finally:
        sa_event.remove(env.engine, "before_cursor_execute", hook)

    # The failure really did land in the window this test claims: the events
    # INSERT was issued and sent before the stages INSERT was attempted.
    assert any("INTO events" in s for s in seen)
    assert any("INTO stages" in s for s in seen)
    assert max(i for i, s in enumerate(seen) if "INTO events" in s) < min(
        i for i, s in enumerate(seen) if "INTO stages" in s
    ), "the events must reach the database before the state rows"

    # Both halves are gone, and so is the counter. Read through a fresh
    # connection so the assertion is about what reached the database, not about
    # the state of the session the failure happened in.
    counts_after, counter_after, seqs_after = _committed_state(env, task.task_id)
    assert counts_after == before
    assert counter_after == 1
    assert seqs_after == [1]

    # And the same unit can now be replayed successfully, which it could not if
    # the counter had advanced behind the rollback.
    with store.unit(task.task_id) as work:
        work.emit(
            EventType.STAGE_ENTERED,
            run_id=run.run_id,
            transition=EventTransition(from_state="pending", to_state="entered"),
        )
        work.put_stage(stage)
    assert last_seq(session, task.task_id) == 2
    assert [e.seq for e in events_after(session, task.task_id)] == [1, 2]


def test_a_failure_rolls_back_every_event_in_the_unit(env: StoreEnv) -> None:
    """Not just the first event: a block of three is undone as a block.

    Allocation hands out one contiguous range for the whole unit, so a partial
    commit would leave the counter holding a range it only partly used. This
    asserts all three events and the counter both disappear together.
    """
    session = env.session
    store = env.store()
    task = make_task()
    store.create_task(task)
    before = _counts(session)

    hook, _ = _fail_on("runs")
    sa_event.listen(env.engine, "before_cursor_execute", hook)
    try:
        with (
            pytest.raises(InjectedFailureError, match="injected failure"),
            store.unit(task.task_id) as work,
        ):
            for _ in range(3):
                work.emit(EventType.SOURCE_CHANGED)
            work.put_run(make_run(task.task_id))
    finally:
        sa_event.remove(env.engine, "before_cursor_execute", hook)

    counts_after, counter_after, seqs_after = _committed_state(env, task.task_id)
    assert counts_after == before
    assert len(seqs_after) == 1
    # The counter did not keep the three values it handed out. This is the
    # assertion that distinguishes a correct rollback from one that undoes the
    # rows but leaks the sequence.
    assert counter_after == 1


def test_a_caller_exception_before_the_flush_writes_nothing(env: StoreEnv) -> None:
    """An exception raised by the caller, before anything is written."""
    session = env.session
    store = env.store()
    task = make_task()
    store.create_task(task)
    run = make_run(task.task_id)
    before = _counts(session)

    class RefusedError(Exception):
        """The caller's own refusal, e.g. a policy denial."""

    with pytest.raises(RefusedError), store.unit(task.task_id) as work:
        work.put_run(run)
        work.emit(
            EventType.RUN_STARTED,
            run_id=run.run_id,
            transition=EventTransition(from_state="pending", to_state="running"),
        )
        raise RefusedError("the operation was refused before it was attempted")

    counts_after, counter_after, _seqs = _committed_state(env, task.task_id)
    assert counts_after == before
    assert counter_after == 1


def test_an_empty_unit_changes_nothing(env: StoreEnv) -> None:
    """A unit with no events and no state writes is a no-op, not an error."""
    session = env.session
    store = env.store()
    task = make_task()
    store.create_task(task)
    before = _counts(session)

    with store.unit(task.task_id):
        pass

    assert _counts(session) == before
    assert last_seq(session, task.task_id) == 1


# --------------------------------------------------------------------------- #
# "and nothing else"
# --------------------------------------------------------------------------- #


def test_a_unit_writes_only_what_it_was_asked_to(env: StoreEnv) -> None:
    """An annotation event creates exactly one row and touches no state.

    This is the testable half of ADR-0003 C3's "**and nothing else**": there is
    no implicit save, no flush of unrelated dirty objects, so a unit's footprint
    on the database is the sum of its explicit ``emit`` and ``put_*`` calls.
    """
    session = env.session
    store = env.store()
    task = make_task()
    store.create_task(task)
    before = _counts(session)

    with store.unit(task.task_id) as work:
        work.emit(EventType.SOURCE_CHANGED)

    after = _counts(session)
    assert after["events"] == before["events"] + 1
    for table in ("tasks", "runs", "stages", "operations", "approvals", "checkpoints", "artifacts"):
        assert after[table] == before[table], f"{table} was written by an annotation-only unit"


# --------------------------------------------------------------------------- #
# deferred foreign keys are actually enforced
# --------------------------------------------------------------------------- #


def test_a_dangling_reference_is_caught_at_commit(env: StoreEnv) -> None:
    """Deferred foreign keys are enforced, not merely declared.

    The events table's foreign keys are ``DEFERRABLE INITIALLY DEFERRED`` so an
    event may be inserted before the state row it describes — which is what
    ADR-0003 C3's ordering requires. Deferral must not mean *unenforced*: an
    event naming a Run that never exists has to fail at COMMIT, once it is
    clear it never will.

    If ``PRAGMA foreign_keys`` were off, this test would fail: the insert would
    succeed. That is the whole reason the pragma is set per connection in
    :mod:`labcairn.db.session` — SQLite ships with foreign keys disabled.
    """
    from labcairn.core.ids import RunId, new_id

    session = env.session
    store = env.store()
    task = make_task()
    store.create_task(task)

    phantom_run = RunId(new_id())
    with pytest.raises(IntegrityError, match="FOREIGN KEY"), store.unit(task.task_id) as work:
        work.emit(
            EventType.RUN_STARTED,
            run_id=phantom_run,
            transition=EventTransition(from_state="pending", to_state="running"),
        )

    session.rollback()
    assert count_events(session, task.task_id) == 1
    assert last_seq(session, task.task_id) == 1


def test_events_precede_the_state_rows_they_describe(env: StoreEnv) -> None:
    """The ordering C3 mandates, observed rather than assumed.

    An ``operation_intent`` names an operation whose row does not exist yet. If
    the foreign key were immediate this insert could not happen at all — so the
    fact that this test passes is the proof that deferral is doing its job.
    """
    from test_store_support import make_operation

    session = env.session
    store = env.store()
    task = make_task()
    store.create_task(task)
    run = make_run(task.task_id)
    stage = make_stage(task.task_id, run.run_id)
    operation = make_operation(task.task_id, run.run_id, stage.stage_id)

    seen: list[str] = []

    def record(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        seen.append(" ".join(statement.split()).lower())

    sa_event.listen(env.engine, "before_cursor_execute", record)
    try:
        with store.unit(task.task_id) as work:
            work.emit(
                EventType.OPERATION_INTENT,
                run_id=run.run_id,
                stage_id=stage.stage_id,
                operation_id=operation.operation_id,
                transition=EventTransition(from_state="planned", to_state="planned"),
            )
            work.put_run(run)
            work.put_stage(stage)
            work.put_operation(operation)
    finally:
        sa_event.remove(env.engine, "before_cursor_execute", record)

    event_insert = next(i for i, s in enumerate(seen) if "into events" in s)
    operation_insert = next(i for i, s in enumerate(seen) if "into operations" in s)
    assert event_insert < operation_insert

    # And the committed log is intact, not merely tolerated.
    stored = events_after(session, task.task_id, after_seq=1)
    assert [e.type for e in stored] == [EventType.OPERATION_INTENT]
    assert stored[0].operation_id == operation.operation_id
    assert _counts(session)["operations"] == 1
