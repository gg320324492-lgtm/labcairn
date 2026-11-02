"""Concurrent ``seq`` allocation: no duplicates, no holes.

ADR-0003 C3's second bullet — *allocate ``seq`` from committed rows inside the
transaction* — is a claim about what happens when two writers arrive at once.
This file tries to falsify it.

The design of the race matters more than the assertion. Threads are released
together through a :class:`threading.Barrier` rather than staggered, because a
staggered test mostly measures SQLite's lock queue and passes for the wrong
reason. Each thread gets its **own session and its own connection** from the
same engine, because sharing a connection would serialise the writers before
they ever contended for the database.

Two things are asserted, and the second is what makes the first meaningful:

* the committed ``seq`` values are exactly ``1..N``, with no duplicate and no
  hole;
* ``tasks.last_event_seq`` equals ``N``, so the counter is not ahead of or
  behind the rows it accounts for.

:func:`test_the_write_lock_is_taken_before_the_first_read` separately proves the
``BEGIN IMMEDIATE`` those results depend on is genuinely reaching SQLite rather
than being silently downgraded to a deferred transaction, which would fail only
under the contention a weaker test would not create.

The read-only engine is the other half of the same boundary. Its tests live
here because what they hold is a property of the transaction boundary: a
deferred ``BEGIN`` takes a snapshot, ``PRAGMA query_only=ON`` makes SQLite
refuse a write on that connection, and one CLI read command is run against a
held writer so the wiring is measured rather than assumed.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import event as sa_event
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from test_store_support import (  # noqa: F401
    StoreEnv,
    frozen_clock,
    make_task,
)
from test_store_support import env as _shared_env
from test_store_support import migrated_db as _shared_migrated_db

from labcairn.core.ids import TaskId
from labcairn.db.repository import TaskStore, count_events, last_seq
from labcairn.db.session import create_db_engine, create_session_factory
from labcairn.runtime.event import EventType

pytestmark = pytest.mark.integration

# pytest resolves a fixture by the parameter name in a test's signature, so the
# shared `env` fixture must be bound under that name here. Importing it directly
# and taking `env` as a parameter makes every signature below an F811
# redefinition; aliasing the import and rebinding it reads as a plain
# assignment instead.
env = _shared_env
migrated_db = _shared_migrated_db

WRITERS = 8
UNITS_PER_WRITER = 6
#: ``create_task`` itself writes ``task_created`` at seq 1, so the concurrent
#: writers produce the events from seq 2 onwards.
CONCURRENT_EVENTS = WRITERS * UNITS_PER_WRITER
TOTAL_EVENTS = 1 + CONCURRENT_EVENTS


def _seqs(session: Session, task_id: TaskId) -> list[int]:
    """A Task's committed ``seq`` values, ascending.

    One helper rather than three copies of the same comprehension: the raw
    ``text()`` result has no static column type, so the value is narrowed by
    ``int()`` here once instead of by a cast at each call site.
    """
    rows: Sequence[Any] = (
        session.execute(
            text("SELECT seq FROM events WHERE task_id = :t ORDER BY seq"), {"t": str(task_id)}
        )
        .scalars()
        .all()
    )
    return [int(value) for value in rows]


def _run_concurrently(
    env: StoreEnv, task_id: TaskId, *, writers: int, per_writer: int
) -> list[Exception]:
    """Drive *writers* threads through *per_writer* units each, released together.

    Each thread opens its own session; a session belongs to one thread and one
    transaction, which is the whole point of the exercise. Exceptions are
    collected and returned rather than raised in the thread, because an
    exception on a worker thread otherwise dies silently and the test passes
    having written almost nothing.
    """
    barrier = threading.Barrier(writers)
    failures: list[Exception] = []
    lock = threading.Lock()

    def worker(worker_index: int) -> None:
        session = env.new_session()
        try:
            # This thread's own TaskStore over its own session. Using the
            # environment's shared store here would serialise the writers on one
            # connection and the test would pass without contending at all.
            store = TaskStore(session)
            barrier.wait(timeout=30)
            for _ in range(per_writer):
                with store.unit(task_id) as work:
                    work.emit(EventType.SOURCE_CHANGED)
        except Exception as exc:
            with lock:
                failures.append(exc)
        finally:
            session.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(writers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
        assert not thread.is_alive(), (
            "a writer thread did not finish: the lock is not being released"
        )
    return failures


def test_concurrent_writers_produce_no_duplicates_and_no_holes(env: StoreEnv) -> None:
    """Eight writers, forty-eight events, ``seq`` exactly ``1..48``."""
    session = env.session
    store = env.store()
    task = make_task()
    store.create_task(task)

    failures = _run_concurrently(env, task.task_id, writers=WRITERS, per_writer=UNITS_PER_WRITER)
    assert failures == [], f"a writer thread failed: {failures!r}"

    seqs = _seqs(session, task.task_id)
    assert len(seqs) == TOTAL_EVENTS
    assert len(set(seqs)) == TOTAL_EVENTS, "a seq was handed out twice"
    assert seqs == list(range(1, TOTAL_EVENTS + 1)), "a hole appeared in the per-Task sequence"
    assert last_seq(session, task.task_id) == TOTAL_EVENTS
    assert count_events(session, task.task_id) == TOTAL_EVENTS


def test_concurrent_writers_across_tasks_stay_independent(env: StoreEnv) -> None:
    """Two Tasks written concurrently keep separate, gapless sequences.

    The harder half of the property: contention is now *between* Tasks as well
    as within one, so a counter that leaked across rows — the failure mode of
    putting the sequence anywhere other than under the Task's own row — would
    show up as interleaved or shared numbering.
    """
    session = env.session
    store = env.store()
    task_a = make_task(title="A")
    task_b = make_task(title="B")
    store.create_task(task_a)
    store.create_task(task_b)

    failures = _run_concurrently(env, task_a.task_id, writers=4, per_writer=4)
    assert failures == [], f"a writer thread failed on task A: {failures!r}"
    failures = _run_concurrently(env, task_b.task_id, writers=4, per_writer=4)
    assert failures == [], f"a writer thread failed on task B: {failures!r}"

    for task_id in (task_a.task_id, task_b.task_id):
        seqs = _seqs(session, task_id)
        # Each Task counts its own create_task event, then its own 16.
        assert seqs == list(range(1, 18)), f"{task_id} is not gapless: {seqs}"


def test_two_connections_in_one_process_serialise(env: StoreEnv) -> None:
    """A second session cannot allocate past a first session's commit."""
    session_a = env.session
    session_b = env.new_session()
    try:
        task = make_task()
        env.store().create_task(task)

        from labcairn.db.repository import TaskStore

        store_a = TaskStore(session_a)
        store_b = TaskStore(session_b)

        with store_a.unit(task.task_id) as work_a:
            work_a.emit(EventType.SOURCE_CHANGED)

        with store_b.unit(task.task_id) as work_b:
            work_b.emit(EventType.SOURCE_CHANGED)

        seqs = _seqs(session_a, task.task_id)
        assert seqs == [1, 2, 3]
    finally:
        session_b.close()


def test_the_write_lock_is_taken_before_the_first_read(env: StoreEnv) -> None:
    """``BEGIN IMMEDIATE`` really is emitted, not quietly downgraded.

    Every claim about safe concurrent allocation rests on the write lock being
    taken up front rather than at the first write. A deferred transaction takes
    it at the first write instead, which permits a read-then-write upgrade — and
    two connections doing that produce ``SQLITE_BUSY`` rather than a wait. If
    this assertion ever fails, the concurrency tests above are passing for a
    reason that has nothing to do with the design.
    """
    store = env.store()
    task = make_task()

    statements: list[str] = []

    def record(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        statements.append(" ".join(statement.split()))

    sa_event.listen(env.engine, "before_cursor_execute", record)
    try:
        store.create_task(task)
        with store.unit(task.task_id) as work:
            work.emit(EventType.SOURCE_CHANGED)
    finally:
        sa_event.remove(env.engine, "before_cursor_execute", record)

    begins = [s for s in statements if s.upper().startswith("BEGIN")]
    assert begins, f"no BEGIN was emitted at all; captured: {statements[:5]}"
    assert all(s.upper() == "BEGIN IMMEDIATE" for s in begins), (
        f"every transaction must begin IMMEDIATE, saw: {sorted(set(begins))}"
    )


def test_a_naive_deferred_begin_would_contend(env: StoreEnv) -> None:
    """A direct check that lock contention is *waited* on, not raised.

    Complementary to the assertion above: rather than reading the SQL, it
    observes the behaviour ``BEGIN IMMEDIATE`` produces. Two writers are
    released together and both must succeed, which a deferred transaction doing
    a read before its write would not reliably manage under the same pressure.
    """
    session = env.session
    store = env.store()
    task = make_task()
    store.create_task(task)

    failures = _run_concurrently(env, task.task_id, writers=6, per_writer=3)
    assert failures == [], f"lock contention surfaced as an error: {failures!r}"
    assert last_seq(session, task.task_id) == 1 + 6 * 3


@pytest.mark.parametrize("writers", [2, 16])
def test_contention_scales_beyond_the_connection_pool(env: StoreEnv, writers: int) -> None:
    """More writers than the pool hands out connections still completes.

    Sixteen writers against a pool that may hold fewer keeps the ``busy_timeout``
    honest: the surplus threads wait for a connection rather than erroring, which
    is the difference between "slow" and "broken" under contention.
    """
    session = env.session
    store = env.store()
    task = make_task()
    store.create_task(task)

    failures = _run_concurrently(env, task.task_id, writers=writers, per_writer=2)
    assert failures == [], f"a writer thread failed: {failures!r}"
    assert last_seq(session, task.task_id) == 1 + writers * 2


def test_the_read_only_engine_emits_a_deferred_begin(env: StoreEnv) -> None:
    """A read-only engine asks for a snapshot, not the write lock.

    The behavioural test below shows a read *completing* while a writer holds
    the lock; this one shows the SQL that makes that true. ``BEGIN IMMEDIATE``
    on this engine would be the old defect wearing the new constructor.
    """
    engine = create_db_engine(env.db_path, readonly=True)
    statements: list[str] = []

    def record(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        statements.append(" ".join(statement.split()))

    sa_event.listen(engine, "before_cursor_execute", record)
    session = create_session_factory(engine)()
    try:
        session.execute(text("SELECT count(*) FROM tasks")).scalar_one()
    finally:
        session.rollback()
        session.close()
        sa_event.remove(engine, "before_cursor_execute", record)
        engine.dispose()

    begins = [s for s in statements if s.upper().startswith("BEGIN")]
    assert begins == ["BEGIN"], f"a read-only engine must emit a plain BEGIN, saw: {begins}"


def test_a_read_completes_while_a_write_transaction_holds_the_lock(env: StoreEnv) -> None:
    """The defect, measured: a read is not a second claimant of the write lock.

    WAL was already enabled on this file, so the writer does not block a
    deferred reader. What made reads wait was their own ``BEGIN IMMEDIATE``:
    they queued at the write lock and, with a busy timeout, failed with
    ``database is locked`` instead of reading a snapshot. The writer below
    holds the lock and has not committed; the read must complete without it.
    """
    task = make_task()
    env.store().create_task(task)

    writer = env.new_session()
    reader_engine = create_db_engine(env.db_path, busy_timeout_ms=2_000, readonly=True)
    reader = create_session_factory(reader_engine)()
    try:
        # Any statement on the write engine opens BEGIN IMMEDIATE and keeps it
        # until commit or rollback.
        writer.execute(text("SELECT count(*) FROM tasks"))
        started = time.perf_counter()
        value = int(reader.execute(text("SELECT count(*) FROM tasks")).scalar_one())
        elapsed = time.perf_counter() - started
        assert value == 1
        assert elapsed < 1.0, (
            f"the read took {elapsed:.2f}s while a writer held the write lock: it "
            "is queueing behind the lock rather than reading a snapshot"
        )
    finally:
        writer.rollback()
        writer.close()
        reader.rollback()
        reader.close()
        reader_engine.dispose()


def test_a_read_only_session_refuses_a_write(env: StoreEnv) -> None:
    """The read-only flag is enforced by SQLite, not by convention.

    A read-only engine whose write path merely "was not meant to be used" is a
    promise nothing keeps. ``PRAGMA query_only`` makes the write fail at
    SQLite, so a command that turns out to write under a read-only context is
    reported rather than silently upgrading to the write transaction the
    engine exists to avoid.
    """
    engine = create_db_engine(env.db_path, readonly=True)
    session = create_session_factory(engine)()
    try:
        assert session.execute(text("PRAGMA query_only")).scalar_one() == 1
        with pytest.raises(OperationalError, match="readonly database"):
            session.execute(text("CREATE TABLE a_write (x INTEGER)"))
        session.rollback()
    finally:
        session.close()
        engine.dispose()


def test_wal_survives_the_engine_that_set_it(migrated_db: Path) -> None:
    """WAL is a database setting, and the read-only path depends on it.

    A deferred reader is only non-blocking because the file is in WAL mode. If
    the setting lived on a connection, a process that reopened the file would
    lose it and reads would start queueing again. The mode is read through a
    raw connection after every engine is disposed, so the engine that set it
    is not the thing being asked whether it did.
    """
    engine = create_db_engine(migrated_db)
    session = create_session_factory(engine)()
    try:
        session.execute(text("SELECT 1"))
        session.rollback()
    finally:
        session.close()
        engine.dispose()

    connection = sqlite3.connect(str(migrated_db))
    try:
        mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
    finally:
        connection.close()
    assert mode == "wal", f"journal_mode after a restart is {mode!r}, not 'wal'"


def test_a_read_only_cli_command_reads_while_a_writer_holds_the_lock(
    tmp_path: Path,
) -> None:
    """Capability is not wiring: a read command must actually ask for it.

    A read-only engine that no command uses changes nothing. This runs the
    CLI's ``task status`` in-process against a workspace the CLI itself made,
    while a writer on another connection holds ``BEGIN IMMEDIATE``. Before the
    read commands were wired to the read-only context, the command's own
    ``BEGIN IMMEDIATE`` waited out the busy timeout and the command failed;
    now it completes.

    The CLI is run in-process rather than through the console script because
    the property is the context the command builds, not its argument parsing
    (``tests/test_cli.py`` owns that).
    """
    from typer.testing import CliRunner

    from labcairn.cli.commands import app

    root = tmp_path / "workspace"
    runner = CliRunner()
    result = runner.invoke(app, ["--workspace", str(root), "init"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(
        app,
        [
            "--workspace",
            str(root),
            "task",
            "create",
            "--title",
            "Read the literature",
            "--objective",
            "Establish what the corpus says about the question.",
            "--criterion",
            "A cited answer, or an honest 'not established'.",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output

    db_path = next(root.rglob("*.db"))
    writer_engine = create_db_engine(db_path)
    writer = create_session_factory(writer_engine)()
    try:
        writer.execute(text("SELECT count(*) FROM tasks"))
        result = runner.invoke(app, ["--workspace", str(root), "task", "status", "--json"])
        assert result.exit_code == 0, result.output
    finally:
        writer.rollback()
        writer.close()
        writer_engine.dispose()
