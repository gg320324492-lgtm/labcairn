"""The service, under the concurrency the workbench actually makes.

The workbench's first load fires **eight requests at the service at once**.
``web/src/app/useWorkbench.ts``'s ``readEverything`` is a ``Promise.all`` over
``health``, ``session``, ``tasks``, ``task``, ``plan``, ``steps``, ``sources``
and ``artifacts``, and every handler in :mod:`labcairn.api.routes` is a plain
``def``, so FastAPI runs them in a threadpool — at the same time.

**One shared session cannot carry that.** A SQLAlchemy ``Session`` is not
thread-safe, so two threads on one session do not merely interleave their
reads: one thread's rollback discards the other thread's work, and the SQLite
driver, called from two threads at once, can take the whole process down. Both
were measured before the fix: a concurrent read answered ``403 task_not_found``
for a task that had just been read successfully, and the process then
segfaulted. The same fifty rounds of the same eight concurrent reads, with a
lock around each request, failed **zero** times — which is what makes the
shared session the cause and not the concurrency.

Nothing in the repository saw it: the web package's tests drive a fake at the
``fetch`` boundary, the API's own tests use ``TestClient`` *sequentially*, and
the end-to-end demonstration makes sequential requests. So the test that
watches this property has to drive real concurrency, and this file does.

**The burst runs in a subprocess.** A crash in the SQLite C extension takes
the whole pytest process with it, and a CI job that dies with a signal has a
log that says nothing. So the burst is a separate process, and the test
asserts on what that process reports: its exit status, and whether any
response was wrong. A segfault then arrives as a non-zero exit and a signal
number — a *finding* — rather than as a dead test runner.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.pool import QueuePool
from test_store_support import StoreEnv
from test_store_support import env as _shared_env

from labcairn.api.app import create_app
from labcairn.application.context import ApplicationContext
from labcairn.application.tasks import create_task
from labcairn.db import create_db_engine
from labcairn.db.migrations import upgrade_to_head
from labcairn.db.repository import TaskStore, events_after
from labcairn.db.session import create_session_factory
from labcairn.runtime.event import EventStreamPage, EventStreamRequest, EventType
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.policy import Permission, PermissionPolicy, Rule

pytestmark = pytest.mark.integration

# pytest resolves a fixture by the parameter name in a test's signature, so the
# shared `env` fixture must be bound under that name here.
env = _shared_env

#: The origin the service answers to by default.
OWN_ORIGIN = "http://127.0.0.1:8000"

#: A moment far enough ahead that an approval asked for now has not lapsed.
_FUTURE = datetime(2027, 1, 1, tzinfo=UTC)

#: The eight paths the workbench reads at once.
#:
#: The same eight, in the same order, as ``readEverything``'s ``Promise.all``.
#: They are the burst's units because they are what the product actually does
#: at once: a burst of eight invented paths would test the same machinery and
#: prove nothing about the first load of the page.
BURST_PATHS: tuple[str, ...] = (
    "/health",
    "/session",
    "/tasks",
    "/task",
    "/plan",
    "/steps",
    "/sources",
    "/artifacts",
)

#: How many rounds of eight concurrent reads the burst makes.
#:
#: Forty rounds is four hundred requests, which is enough for the broken
#: service to be wrong in every one of the eight paths, and few enough that
#: the burst finishes in seconds. The property is not "the burst is right
#: once": it is "**no** request is ever wrong", so the assertion is over
#: every response of every round, not over a sample.
BURST_ROUNDS: int = 40

#: How many rounds of one write beside seven reads the write test makes.
WRITE_ROUNDS: int = 10


# --------------------------------------------------------------------------- #
# the environment
# --------------------------------------------------------------------------- #


def _allow_all() -> PermissionPolicy:
    """A policy that allows everything, so a test can vary one thing at a time."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])


@pytest.fixture
def context(env: StoreEnv, tmp_path: Path) -> ApplicationContext:
    """A context for a task that exists, in a workspace of its own."""
    root = tmp_path / "workspace"
    materials = root / "materials"
    materials.mkdir(parents=True)
    store = env.store()
    created = create_task(
        store=store,
        policy=_allow_all(),
        workspace_root=root,
        title="Concurrency test task",
        goal=TaskGoal(
            objective="Establish whether the observation holds.",
            success_criterion="A cited answer, or an honest 'not established'.",
        ),
        source_dirs=(materials,),
    )
    return ApplicationContext(
        workspace=created.workspace,
        store=store,
        policy=_allow_all(),
        ledger=ApprovalLedger(),
    )


@pytest.fixture
def token(client: TestClient) -> str:
    """The service's session token, read the way a client reads it."""
    response = client.get("/session")
    assert response.status_code == 200
    return str(response.json()["token"])


@pytest.fixture
def client(context: ApplicationContext) -> Iterator[TestClient]:
    """A client for the service, with the event stream wired to the store."""
    app = create_app(context, event_source=_RecordingSource())
    with TestClient(app) as wired:
        yield wired


# --------------------------------------------------------------------------- #
# the burst
# --------------------------------------------------------------------------- #


def test_a_forked_store_is_another_connection_to_the_same_store(
    context: ApplicationContext,
) -> None:
    """A fork is another connection to the same store, and not another store.

    The same engine, so the same database and the same pool; a different
    session, so a different connection; and the same clock, so a forked store
    stamps its events the way the store it was forked from would have
    stamped them.
    """
    forked = context.store.fork()
    assert forked is not context.store
    assert forked.session is not context.store.session
    assert forked.session.get_bind() is context.store.session.get_bind()
    assert forked.clock is context.store.clock


@contextmanager
def _service(root: Path) -> Iterator[tuple[Any, str]]:
    """The real service, over a real database, in a real workspace.

    The same construction the product makes: a migrated SQLite file, an
    engine on it, a session, a store, a task, and the app over the context
    that names it. Nothing here is a fake, because the defect is in the
    session's ownership and a fake session would not have one.

    The engine is disposed and the session closed on the way out. On Windows
    an open file cannot be deleted, so a database file left open is a
    temporary directory that cannot be removed — and the subprocess that
    runs the burst would fail on its way out rather than on the thing it
    was asked to find.
    """
    materials = root / "materials"
    materials.mkdir(parents=True)
    database = root / "labcairn.db"
    upgrade_to_head(database)
    engine = create_db_engine(database)
    factory = create_session_factory(engine)
    session = factory()
    try:
        store = TaskStore(session)
        created = create_task(
            store=store,
            policy=_allow_all(),
            workspace_root=root,
            title="Concurrent task",
            goal=TaskGoal(
                objective="See what happens.",
                success_criterion="An honest answer.",
            ),
            source_dirs=(materials,),
        )
        context = ApplicationContext(
            workspace=created.workspace,
            store=store,
            policy=_allow_all(),
            ledger=ApprovalLedger(),
        )
        yield create_app(context), str(created.task.task_id)
    finally:
        session.close()
        engine.dispose()


def _burst(app: Any, task_id: str) -> dict[str, Any]:
    """The eight reads, eight at a time, forty times over.

    Every response is checked, and every response is *kept* if it is wrong:
    a summary that said "something went wrong" would not say which path
    answered wrongly, and the path is the finding.
    """
    wrong: list[dict[str, Any]] = []
    requests = 0

    with TestClient(app) as client:
        # One warm read, so that the first concurrent round is not racing the
        # service's own start-up.
        client.get("/task")

        def one(path: str) -> tuple[str, str | None]:
            try:
                response = client.get(path)
            except Exception as error:
                return path, f"{type(error).__name__}: {error}"
            if response.status_code != 200:
                return path, f"HTTP {response.status_code}: {response.text[:200]}"
            if path == "/task" and task_id not in response.text:
                return path, f"the task document does not name {task_id}: {response.text[:200]}"
            return path, None

        for _ in range(BURST_ROUNDS):
            with ThreadPoolExecutor(max_workers=len(BURST_PATHS)) as pool:
                for path, problem in pool.map(one, BURST_PATHS):
                    requests += 1
                    if problem is not None:
                        wrong.append({"path": path, "problem": problem})

    return {
        "rounds": BURST_ROUNDS,
        "requests": requests,
        "wrong": len(wrong),
        "failures": wrong[:20],
    }


def _burst_main(report: Path) -> int:
    """Run the burst and write what it saw to *report*, as JSON.

    **The report is a file and not the process's output.** A segfault in the
    SQLite driver kills the process before it can say anything, and a report
    that is only half-written is a report the parent cannot trust; so the
    summary is written at the end, in one go, and the exit status is the
    subprocess's own report of whether it *survived*.
    """
    with (
        tempfile.TemporaryDirectory(prefix="lcp-concurrency-") as raw,
        _service(Path(raw) / "workspace") as (app, task_id),
    ):
        summary = _burst(app, task_id)
    report.write_text(json.dumps(summary), encoding="utf-8")
    return 0


def _how_it_died(returncode: int) -> str:
    """How the burst's process ended, in words.

    A process killed by a signal reports a negative status on POSIX, and
    Windows gives the same death the NTSTATUS name ``0xC0000005`` — an
    access violation, which is what a segmentation fault is called there.
    Both are the SQLite driver taking the process down, and both are a
    *finding* rather than a dead test runner.
    """
    if returncode < 0:
        return f"signal {-returncode}"
    if returncode == 0xC0000005:
        return "STATUS_ACCESS_VIOLATION (0xC0000005), the Windows name for a segmentation fault"
    return ""


def test_the_workbench_s_first_load_is_answered_correctly_under_concurrency(
    tmp_path: Path,
) -> None:
    """Eight concurrent reads, forty times over, and **not one** of them wrong.

    The property is the strong one: *no request ever sees a task that exists
    as missing*, and no request is answered with anything but the answer it
    asked for. It is asserted over every response of every round rather than
    over a sample, because the broken service was wrong in a way that a
    sample would have missed.

    **It is not flaky, and that is why the assertion is this shape.** Every
    round is checked, so there is no "retry until it passes" and no
    threshold to tune: on the fixed service every response is right every
    time, because every request has a session of its own and no request's
    transaction can end another request's work.

    The burst runs in a subprocess, and the subprocess's exit status is
    asserted first: a crash in the SQLite driver takes the whole pytest
    process down with it, and a CI job that dies with a signal has a log that
    says nothing at all.
    """
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    report = tmp_path / "burst.json"
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), str(report)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=900,
    )
    died = _how_it_died(result.returncode)
    assert result.returncode == 0, (
        f"the concurrent burst did not survive: exit {result.returncode}"
        + (f", {died}" if died else "")
        + f"\n--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert report.is_file(), (
        f"the burst reported nothing at all:\n--- stdout ---\n{result.stdout}"
        f"\n--- stderr ---\n{result.stderr}"
    )
    summary = json.loads(report.read_text(encoding="utf-8"))
    assert summary["requests"] == BURST_ROUNDS * len(BURST_PATHS), (
        f"the burst made {summary['requests']} request(s), not "
        f"{BURST_ROUNDS * len(BURST_PATHS)}: the burst did not run"
    )
    assert summary["wrong"] == 0, (
        f"{summary['wrong']} of {summary['requests']} concurrent reads were wrong: "
        f"{summary['failures']}"
    )


# --------------------------------------------------------------------------- #
# the event stream's session
# --------------------------------------------------------------------------- #


class _RecordingSource:
    """An event source that keeps the sessions it was handed.

    It reads the store's event log the way the service's host would, and it
    remembers the session so that a test can look at what the stream was
    given: the stream's own session, opened when the stream started and
    closed when it ended.
    """

    def __init__(self) -> None:
        self.sessions: list[Session] = []

    def page(self, session: Session, request: EventStreamRequest) -> EventStreamPage:
        """The events after the request's cursor, read on the session given."""
        self.sessions.append(session)
        events = events_after(
            session, request.task_id, after_seq=request.after_seq, limit=request.limit
        )
        return EventStreamPage(
            task_id=request.task_id,
            events=events,
            next_after_seq=events[-1].seq if events else request.after_seq,
            caught_up=len(events) < request.limit,
        )


class _StopTheStreamError(Exception):
    """Raised by the source to end a stream that would otherwise never end."""


class _FailingSource:
    """A source that reads, and then fails.

    **The read is what makes the failure matter.** The store's engine opens
    every transaction with ``BEGIN IMMEDIATE``, so a read leaves the session
    holding SQLite's *write* lock. A stream that failed without letting go
    of its session would leave that lock held — and every other request in
    the service would be refused with *"database is locked"* for as long as
    the session lived.
    """

    def __init__(self) -> None:
        self.sessions: list[Session] = []

    def page(self, session: Session, request: EventStreamRequest) -> EventStreamPage:
        """Read, and then fail."""
        self.sessions.append(session)
        session.execute(text("SELECT 1")).scalar_one()
        raise _StopTheStreamError("the test asked the stream to fail")


class _PollingSource:
    """A source that polls twice, says what it saw, and then stops the stream.

    The second poll is the interesting one: it happens *after* the first poll
    has been answered, and it is the moment at which the stream is between
    its reads. The source records whether the session was still in a
    transaction when it was called, which is the whole of the question: the
    store's engine opens every transaction with ``BEGIN IMMEDIATE``, so a
    session that is still in a transaction is holding SQLite's **write** lock,
    and a stream that held it between its polls would refuse every other
    request in the service for as long as the client stayed connected.

    The stream is stopped by raising, because ``follow=true`` never ends on
    its own and the test wants to look at what happened *between* the polls.
    """

    def __init__(self) -> None:
        self.polls = 0
        self.in_transaction_at_entry: list[bool] = []

    def page(self, session: Session, request: EventStreamRequest) -> EventStreamPage:
        """The events after the request's cursor, read on the session given.

        **The read is what opens the transaction.** A source that did not
        read would leave the session in no transaction at all, and the
        question this source exists to ask would have nothing to look at.
        """
        self.polls += 1
        self.in_transaction_at_entry.append(session.in_transaction())
        events = events_after(
            session, request.task_id, after_seq=request.after_seq, limit=request.limit
        )
        if self.polls == 2:
            raise _StopTheStreamError("the test asked the stream to stop")
        return EventStreamPage(
            task_id=request.task_id,
            events=events,
            next_after_seq=events[-1].seq if events else request.after_seq,
            caught_up=len(events) < request.limit,
        )


def test_the_event_stream_owns_its_session_for_the_life_of_the_stream(
    context: ApplicationContext, env: StoreEnv
) -> None:
    """The stream reads on a session of its own, and lets it go when it ends.

    **It is not the service's shared session.** A source that read on the
    service's session would be a session shared by every request that read
    the stream, which is the defect this whole change is about.

    **And it lets go of it when the stream ends.** A session that outlived
    its stream would hold a connection the pool never gets back, and — since
    the store's engine opens every transaction with ``BEGIN IMMEDIATE`` — a
    transaction that outlived its stream would hold SQLite's write lock for
    as long as the client stayed connected.

    The connection is what is watched, because that is what a session gives
    back: the pool's count of checked-out connections is the fact, and a
    session that was left open is a connection the pool is still missing.
    """
    source = _RecordingSource()
    app = create_app(context, event_source=source)
    pool = env.engine.pool
    assert isinstance(pool, QueuePool)
    before = pool.checkedout()
    with TestClient(app) as client:
        response = client.get("/events/stream?follow=false")
    assert response.status_code == 200, response.text
    assert len(source.sessions) == 1, (
        f"the stream read on {len(source.sessions)} session(s); it should read on one"
    )
    session = source.sessions[0]
    assert session is not context.store.session, (
        "the stream read on the service's shared session, so two requests that read "
        "the stream would share one"
    )
    assert not session.in_transaction(), "the stream's session is still in a transaction"
    assert pool.checkedout() == before, (
        f"the pool still has {pool.checkedout()} connection(s) checked out and had "
        f"{before} before the request: the stream did not let go of its session"
    )


def _the_sessions_the_request_owns(
    context: ApplicationContext, monkeypatch: pytest.MonkeyPatch
) -> list[Session]:
    """The sessions the *request* owns, recorded as the request forks them.

    The app holds one store, and every request forks a session of its own
    from it — that is the request's session, and the request's own teardown
    closes it. The stream must not read on it: the stream's session belongs
    to the stream, and the stream closes it when the stream ends.

    Recorded on the *store the app holds*, so that only the request's own
    fork is caught: the stream forks from the request's store, and that
    store is not this one.
    """
    forked: list[Session] = []
    original = context.store.fork

    def recording_fork() -> TaskStore:
        store = original()
        forked.append(store.session)
        return store

    monkeypatch.setattr(context.store, "fork", recording_fork)
    return forked


def test_the_event_stream_reads_on_a_session_of_its_own_not_the_requests(
    context: ApplicationContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stream's session is the stream's, and not the request's.

    **The other half of the property the test above states.** That one
    watches the stream let go of its session, and checks that the session
    it used is not the *service's* shared one. This one watches the session
    the *request* owns: the request forks a session of its own from the
    store the app holds, and the stream must not read on it. A stream that
    read on the request's session would be reading on a session the
    request's own teardown closes — one lifetime where the code says there
    are two, and the stream's closing would be the request's closing.

    The request's session is found by watching the fork the request makes,
    rather than by guessing which session the service happens to hold.
    """
    source = _RecordingSource()
    requests = _the_sessions_the_request_owns(context, monkeypatch)
    app = create_app(context, event_source=source)
    with TestClient(app) as client:
        response = client.get("/events/stream?follow=false")
    assert response.status_code == 200, response.text
    assert len(requests) == 1, (
        f"the request forked {len(requests)} session(s); it owns one of its own, "
        "and the stream must not read on it"
    )
    assert len(source.sessions) == 1, (
        f"the stream read on {len(source.sessions)} session(s); it should read on one"
    )
    assert source.sessions[0] is not requests[0], (
        "the stream read on the request's own session, so the session the "
        "request's teardown closes is the one the stream reads on, and the "
        "stream's closing is the request's closing"
    )


def test_a_failed_event_stream_leaves_no_transaction_behind(
    context: ApplicationContext,
) -> None:
    """A stream that fails lets go of its session, lock and all.

    The failure is what makes the closing load-bearing. A poll that reads
    leaves the session holding SQLite's write lock, and a stream that failed
    half way through a poll never reaches the line that ends the poll's
    transaction. So the closing is the only thing that ends it — and a
    stream that left the lock held would refuse every other request in the
    service with *"database is locked"*.
    """
    source = _FailingSource()
    app = create_app(context, event_source=source)
    with TestClient(app) as client, pytest.raises(_StopTheStreamError):
        client.get("/events/stream?follow=true&poll_seconds=0.01")
    assert len(source.sessions) == 1, (
        f"the stream read on {len(source.sessions)} session(s); it should read on one"
    )
    assert not source.sessions[0].in_transaction(), (
        "the failed stream left its session in a transaction, and a transaction holds "
        "SQLite's write lock: every other request would be refused with 'database "
        "is locked'"
    )


def test_the_event_stream_holds_no_transaction_between_its_polls(
    context: ApplicationContext,
) -> None:
    """A stream between its polls holds nothing that blocks another request.

    The store's engine opens **every** transaction with ``BEGIN IMMEDIATE`` —
    ADR-0003 C3's clause — so a read takes SQLite's *write* lock, not a read
    lock. A stream that left its transaction open between its polls would
    therefore hold the write lock for the whole of the connection, and every
    other request in the service would be refused with *"database is
    locked"* once the busy timeout ran out.

    The question is asked at the only moment it can be asked at: the entry to
    the second poll, which is after the first poll was answered and before
    the second one began. A session that is still in a transaction there is
    holding the lock.
    """
    source = _PollingSource()
    app = create_app(context, event_source=source)
    with TestClient(app) as client, pytest.raises(_StopTheStreamError):
        client.get("/events/stream?follow=true&poll_seconds=0.01")
    assert source.polls == 2, f"the stream polled {source.polls} time(s); it should poll twice"
    assert source.in_transaction_at_entry == [False, False], (
        "the stream held a transaction between its polls, and a transaction holds "
        f"SQLite's write lock: {source.in_transaction_at_entry}"
    )


# --------------------------------------------------------------------------- #
# a write that is under way
# --------------------------------------------------------------------------- #


def test_a_request_s_end_cannot_discard_another_request_s_write(
    context: ApplicationContext, env: StoreEnv
) -> None:
    """A write that is under way is not another request's to discard.

    Every request ends its transaction when the request ends. That must end
    **that request's** transaction and nobody else's: a reader that rolled
    back the transaction a writer was inside would take the writer's work
    with it, and the approval would never reach the store.

    The write is made *beside* the reads, round after round, and the store
    is read afterwards **through another connection** — so what is counted is
    what was committed, not what the service remembers.
    """
    app = create_app(context)
    with TestClient(app) as client:
        token = str(client.get("/session").json()["token"])
        headers = {"Origin": OWN_ORIGIN, "Authorization": f"Bearer {token}"}
        before = _approvals_asked(env, context)

        for _ in range(WRITE_ROUNDS):
            with ThreadPoolExecutor(max_workers=8) as pool:
                written = pool.submit(
                    client.post,
                    "/approvals",
                    json={
                        "capability": "fs.read",
                        "arguments": {},
                        "root_id": "output",
                        "resource_key": "report.md",
                        "expires_at": _FUTURE.isoformat(),
                    },
                    headers=headers,
                )
                read = pool.submit(client.get, "/task")
                approval = written.result()
                task = read.result()
            assert approval.status_code == 201, (
                f"the write was refused: {approval.status_code} {approval.text[:200]}"
            )
            assert task.status_code == 200, (
                f"the read beside the write was refused: {task.status_code} {task.text[:200]}"
            )

        after = _approvals_asked(env, context)

    assert after - before == WRITE_ROUNDS, (
        f"the store holds {after - before} new approval(s) and {WRITE_ROUNDS} were "
        "asked for: a request's end discarded a write that was under way"
    )


def _approvals_asked(env: StoreEnv, context: ApplicationContext) -> int:
    """How many approvals the store has been asked for, through another connection.

    Another engine, as a second process has, so what is counted is what was
    committed to the database and not what a session happens to be holding.
    The count is of the ``approval_requested`` events and not of every event,
    because an approval is recorded by more than one event and the question
    is how many *approvals* the store holds.
    """
    other = create_db_engine(env.db_path, busy_timeout_ms=250)
    try:
        with other.connect() as connection:
            return int(
                connection.execute(
                    text("SELECT COUNT(*) FROM events WHERE task_id = :t AND type = :type"),
                    {"t": str(context.task_id), "type": EventType.APPROVAL_REQUESTED.value},
                ).scalar_one()
            )
    finally:
        other.dispose()


# --------------------------------------------------------------------------- #
# the burst, as a program
# --------------------------------------------------------------------------- #


if __name__ == "__main__":
    raise SystemExit(_burst_main(Path(sys.argv[1])))
