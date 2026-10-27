"""The same Task, the same identity, after the process goes away.

LC-P1-05's last acceptance criterion: *same-task stable identity across
restarts*. The word doing the work is "same". A Task is a continuing research
objective that outlives every execution attempt; a crash-and-resume is a **new
Run against the same Task**, never a new Task. If a restart minted a fresh
Task id, the resumed attempt would have no history to attach to and the whole
Task/Run separation in ``runtime.lifecycle`` would be decorative.

"Restart" here is a genuine one: the engine is disposed and a new one is built
against the same file, with a new connection pool and a new session. Nothing is
carried over in memory — the database file is the only thing that persists, so
a value that survived did so because it was written down.

The assertions are about *identity and continuity*, not liveness: the ids, the
event history and the sequence counter must be byte-identical, and a Task
resumed after restart must continue its sequence rather than restart at 1.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, NamedTuple

import pytest
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session, sessionmaker
from test_store_support import (  # noqa: F401
    StoreEnv,
    frozen_clock,
    make_approval,
    make_checkpoint,
    make_operation,
    make_receipt,
    make_run,
    make_stage,
    make_task,
)
from test_store_support import env as _shared_env

from labcairn.db.models import TaskRow
from labcairn.db.repository import (
    TaskStore,
    count_events,
    events_after,
    last_seq,
)
from labcairn.db.session import create_db_engine, create_session_factory
from labcairn.reports.receipt import ArtifactReceipt
from labcairn.runtime.event import EventTransition, EventType
from labcairn.runtime.lifecycle import Run, RunStatus, Stage, Task
from labcairn.runtime.operation import Approval, Checkpoint, Operation

pytestmark = pytest.mark.integration

# pytest resolves a fixture by the parameter name in a test's signature, so the
# shared `env` fixture must be bound under that name here. Importing it directly
# and taking `env` as a parameter makes every signature below an F811
# redefinition; aliasing the import and rebinding it reads as a plain
# assignment instead.
env = _shared_env


class _Lifecycle(NamedTuple):
    """What a seeded Task looks like once a run, stage, operation, approval,
    checkpoint and artifact all hang off it. A NamedTuple rather than a bare
    tuple so the unpacking sites below stay checked."""

    task: Task
    run: Run
    stage: Stage
    operation: Operation
    approval: Approval
    checkpoint: Checkpoint
    receipt: ArtifactReceipt


def _reopen(db_path: Path) -> tuple[Engine, sessionmaker[Session]]:
    """Dispose the old engine and build a new one — a process restart."""
    engine = create_db_engine(db_path)
    return engine, create_session_factory(engine)


def _seed_full_lifecycle(store: TaskStore) -> _Lifecycle:
    """Create a Task and drive it far enough that identity has something to hold."""
    task = make_task(title="Durable task")
    store.create_task(task)

    run = make_run(task.task_id)
    stage = make_stage(task.task_id, run.run_id)
    operation = make_operation(task.task_id, run.run_id, stage.stage_id)
    approval = make_approval(task.task_id, operation.operation_id)
    checkpoint = make_checkpoint(task.task_id, run.run_id, stage.stage_id, through_seq=1)
    receipt = make_receipt(task.task_id)

    with store.unit(task.task_id) as work:
        work.put_run(run)
        work.put_stage(stage)
        work.put_operation(operation)
        work.put_approval(approval)
        work.put_checkpoint(checkpoint)
        work.put_artifact(receipt, run_id=run.run_id)
        work.emit(
            EventType.RUN_STARTED,
            run_id=run.run_id,
            transition=EventTransition(
                from_state=RunStatus.PENDING.value, to_state=RunStatus.RUNNING.value
            ),
        )
    return _Lifecycle(task, run, stage, operation, approval, checkpoint, receipt)


def test_task_identity_survives_a_restart(env: StoreEnv) -> None:
    """The id, the history and the counter are identical after reopening."""
    session_before = env.session
    store = env.store()
    task, run, *_rest = _seed_full_lifecycle(store)

    before_ids = [e.event_id for e in events_after(session_before, task.task_id)]
    before_seq = [e.seq for e in events_after(session_before, task.task_id)]
    before_counter = last_seq(session_before, task.task_id)
    before_row = (
        session_before.execute(select(TaskRow).where(TaskRow.task_id == str(task.task_id)))
        .scalars()
        .one()
    )
    assert before_counter == 2

    # --- restart ---
    db_path = env.db_path
    session_before.close()
    env.dispose()

    engine, factory = _reopen(db_path)
    session_after = factory()
    try:
        after_row = (
            session_after.execute(select(TaskRow).where(TaskRow.task_id == str(task.task_id)))
            .scalars()
            .one()
        )
        # Identity: the natural key is what a resumed process looks up.
        assert after_row.task_id == before_row.task_id
        assert after_row.owner_id == before_row.owner_id
        # The surrogate key is table-wide and is not the identity.
        assert after_row.id == before_row.id

        # History: same events, same ids, same order, same seqs.
        after_events = events_after(session_after, task.task_id)
        assert [e.event_id for e in after_events] == before_ids
        assert [e.seq for e in after_events] == before_seq == [1, 2]
        assert [e.type for e in after_events] == [EventType.TASK_CREATED, EventType.RUN_STARTED]
        assert after_events[1].run_id == run.run_id

        # Continuity of the counter.
        assert last_seq(session_after, task.task_id) == before_counter == 2
        assert count_events(session_after, task.task_id) == 2

        # And the state rows are still there, joined to the same Task.
        counts: dict[str, int] = dict(
            session_after.execute(
                text(
                    "SELECT 'runs', COUNT(*) FROM runs UNION ALL"
                    " SELECT 'stages', COUNT(*) FROM stages UNION ALL"
                    " SELECT 'operations', COUNT(*) FROM operations UNION ALL"
                    " SELECT 'approvals', COUNT(*) FROM approvals UNION ALL"
                    " SELECT 'checkpoints', COUNT(*) FROM checkpoints UNION ALL"
                    " SELECT 'artifacts', COUNT(*) FROM artifacts"
                )
            ).all()
        )
        assert counts == {
            "runs": 1,
            "stages": 1,
            "operations": 1,
            "approvals": 1,
            "checkpoints": 1,
            "artifacts": 1,
        }
    finally:
        session_after.close()
        engine.dispose()


def test_a_resumed_task_continues_its_sequence(env: StoreEnv) -> None:
    """After a restart the next event takes the next seq, not seq 1 again.

    This is the criterion that would actually fail if sequence allocation were
    derived from something transient — an in-memory counter, a rowid reused by
    ``VACUUM``, a fresh autoincrement on a new file. Restarting the sequence
    would make ``after_seq`` resumption ambiguous: a client that had seen seq 7
    could be handed a second seq 3.
    """
    store = env.store()
    task = make_task()
    store.create_task(task)
    with store.unit(task.task_id) as work:
        work.emit(EventType.SOURCE_CHANGED)
        work.emit(EventType.SOURCE_CHANGED)

    db_path = env.db_path
    env.session.close()
    env.dispose()

    engine, factory = _reopen(db_path)
    session = factory()
    try:
        reopened = TaskStore(session)
        with reopened.unit(task.task_id) as work:
            work.emit(EventType.SOURCE_CHANGED)

        seqs = [e.seq for e in events_after(session, task.task_id)]
        assert seqs == [1, 2, 3, 4]
        assert len(set(seqs)) == len(seqs), "a restart reissued a seq"
        assert last_seq(session, task.task_id) == 4

        # And resumption still works from the pre-restart cursor.
        tail = events_after(session, task.task_id, after_seq=3)
        assert [e.seq for e in tail] == [4]
    finally:
        session.close()
        engine.dispose()


def test_a_restart_creates_a_second_task_without_disturbing_the_first(env: StoreEnv) -> None:
    """Two Tasks across a restart: the new one does not inherit the old ids."""
    store = env.store()
    first = make_task(title="first")
    store.create_task(first)

    db_path = env.db_path
    env.session.close()
    env.dispose()

    engine, factory = _reopen(db_path)
    session = factory()
    try:
        reopened = TaskStore(session)
        second = make_task(title="second")
        reopened.create_task(second)

        assert second.task_id != first.task_id
        # The first Task is untouched: same events, same starting seq of 1.
        assert [e.seq for e in events_after(session, first.task_id)] == [1]
        assert [e.seq for e in events_after(session, second.task_id)] == [1]
        assert last_seq(session, first.task_id) == 1
        assert last_seq(session, second.task_id) == 1
    finally:
        session.close()
        engine.dispose()


def test_a_run_is_not_a_task(env: StoreEnv) -> None:
    """A resumed attempt is a new Run against the same Task.

    The identity guarantee is only meaningful if Task and Run are genuinely
    separate: this writes two Runs to one Task across two "processes" and
    asserts the Task id is unchanged while the Run ids differ. It is the
    ``lifecycle`` module's central claim, asserted through the store.
    """
    store = env.store()
    task, run_one, *_rest = _seed_full_lifecycle(store)

    db_path = env.db_path
    env.session.close()
    env.dispose()

    engine, factory = _reopen(db_path)
    session = factory()
    try:
        resumed = TaskStore(session)
        # "Resume" creates a second Run against the *same* Task.
        run_two = make_run(task.task_id, attempt=2)
        with resumed.unit(task.task_id) as work:
            work.put_run(run_two)
            work.emit(
                EventType.RUN_STARTED,
                run_id=run_two.run_id,
                transition=EventTransition(
                    from_state=RunStatus.PENDING.value, to_state=RunStatus.RUNNING.value
                ),
            )

        assert run_two.run_id != run_one.run_id
        assert run_two.task_id == task.task_id

        raw_runs: Sequence[Any] = (
            session.execute(
                text("SELECT run_id FROM runs WHERE task_id = :t ORDER BY run_id"),
                {"t": str(task.task_id)},
            )
            .scalars()
            .all()
        )
        runs = [str(value) for value in raw_runs]
        assert len(runs) == 2
        # Both run_started events belong to the same Task's single sequence.
        started = [
            e for e in events_after(session, task.task_id) if e.type is EventType.RUN_STARTED
        ]
        assert [e.seq for e in started] == [2, 3]
        assert {e.run_id for e in started} == {run_one.run_id, run_two.run_id}
    finally:
        session.close()
        engine.dispose()


def test_the_events_table_survives_reopen_without_rewriting(env: StoreEnv) -> None:
    """Reopening is a read of the log, not a re-emission of it.

    A resumed process that re-ran its startup events would double every
    ``task_created`` and make the history a fiction. The event count and the
    ``event_id`` set are compared across the restart.
    """
    store = env.store()
    task = make_task()
    store.create_task(task)
    with store.unit(task.task_id) as work:
        work.emit(EventType.SOURCE_CHANGED)

    db_path = env.db_path
    before = [e.event_id for e in events_after(env.session, task.task_id)]
    env.session.close()
    env.dispose()

    engine, factory = _reopen(db_path)
    session = factory()
    try:
        assert [e.event_id for e in events_after(session, task.task_id)] == before
        assert count_events(session, task.task_id) == 2
    finally:
        session.close()
        engine.dispose()


def test_a_checkpoint_survives_a_restart_with_its_through_seq(env: StoreEnv) -> None:
    """The checkpoint's ``through_seq`` still resolves to the same event.

    ``through_seq`` is a per-Task ``seq``, so it is only meaningful if the
    sequence is stable across a restart. This is the storage half of what
    LC-P1-06 will build on; LC-P1-06 owns the reconciliation itself and is not
    implemented here.
    """
    store = env.store()
    task, _run, _stage, _op, _appr, checkpoint, _receipt = _seed_full_lifecycle(store)

    db_path = env.db_path
    env.session.close()
    env.dispose()

    engine, factory = _reopen(db_path)
    session = factory()
    try:
        through: int = session.execute(
            text("SELECT through_seq FROM checkpoints WHERE checkpoint_id = :c"),
            {"c": str(checkpoint.checkpoint_id)},
        ).scalar_one()
        assert through == checkpoint.through_seq
        # seq 1 is still the same event it was when the checkpoint was written.
        assert events_after(session, task.task_id, after_seq=through - 1, limit=1)[0].type is (
            EventType.TASK_CREATED
        )
    finally:
        session.close()
        engine.dispose()
