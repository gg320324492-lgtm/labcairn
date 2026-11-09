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

**The file's second property is about what one request did to every other
one.** `test_one_unwired_event_stream_leaves_the_service_able_to_answer`
watches the service's *request capacity across an unwired event stream* — the
defect the LC-P3-05 selection window measured and named O6, where one short
``GET /events/stream`` was followed by no answer to anything, ``/openapi.json``
included. It runs the service in a subprocess for the same reason the burst
does, and for one more: the stall is a blocked write to the process's own
stdout, and a pytest process whose stdout is a pipe nobody reads is exposed to
exactly that.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
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
from store_support import StoreEnv
from store_support import env as _shared_env

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

#: The reads the O6 probe makes on either side of an unwired stream.
#:
#: ``/openapi.json`` is in the list on purpose: it is FastAPI's own endpoint,
#: behind neither the product's guards nor its store. When the stall was live,
#: it timed out too — which is what says the failure is the application not
#: serving at all, and not one route being slow.
O6_READS: tuple[str, ...] = ("/health", "/openapi.json", "/session", "/tasks")

#: How much one unwired stream costs the unfixed service.
#:
#: Measured on this machine on 2026-11-10: **6,205 bytes for one short unwired
#: stream** (two tracebacks, each through the full ASGI stack), against **0
#: bytes for an ordinary read** and about 944 for start-up. It is used here as a
#: *floor* rather than as the number a dose is computed from: a traceback of
#: that size is what this build writes, and the dose is sized from the pipe's
#: own measured capacity divided by this floor.
O6_UNWIRED_STREAM_FLOOR: int = 1024

#: How many unwired short streams the probe opens, as a floor.
#:
#: Two is the measured dose that overflowed this machine's 8,192-byte pipe on
#: the unfixed code (944 + 2 x 6,205). The probe raises it to whatever the pipe
#: in front of it actually needs — see `_pipe_capacity` — because the capacity
#: is not one number across platforms.
O6_DOSE_MIN: int = 2

#: The ceiling on that dose.
#:
#: The dose exists to overflow the pipe, and a pipe that needs 64 streams to
#: overflow is a pipe whose probe would spend 64 timeouts of 8 seconds each on
#: the unfixed code — a run that takes ten minutes to be red. The cap keeps the
#: worst case under three minutes, and the probe reports the capacity it measured
#: alongside the number it used, so a dose that was capped is visible rather than
#: silently too small.
O6_DOSE_MAX: int = 20

#: The capacity the probe asks its pipe for, where the platform takes the
#: request (it does on Linux, and does not on Windows).
#:
#: A bounded pipe is what keeps the dose bounded. The dose is sized from the
#: pipe's measured capacity, so against a default Linux pipe of 65,536 bytes it
#: would need some 65 streams and the probe would spend its life opening streams.
#: 16 KiB overflows comfortably at the measured per-stream cost and keeps the
#: capped dose able to fill it.
O6_PIPE_CAPACITY_REQUEST: int = 16384

#: The request, as a keyword mapping, for the reason given in
#: `_new_anonymous_pipe`: the platform's own type stubs are what `mypy --strict`
#: reads, and the Windows ones do not know the keyword.
O6_PIPE_CAPACITY_KWARGS: dict[str, int] = {"pipe_size": O6_PIPE_CAPACITY_REQUEST}

#: The ceiling on what the service may write into its own output across the
#: probe.
#:
#: It is several times the 6,205 bytes one unwired stream used to write, and a
#: fraction of the capacity the probe asks for. The unfixed service blew through
#: it by an order of magnitude; the fixed one writes only what a refusal that
#: *is a response* costs, which is nothing: no traceback, no exception, nothing
#: to drain.
O6_LOG_BUDGET: int = 4096

#: How long one ordinary read may take before the probe calls it unanswered.
#:
#: The stall's own signature: every read of every path ended at the client's
#: timeout, 8 seconds, while the process stayed alive and the port still
#: accepted a connection.
O6_REQUEST_TIMEOUT: float = 8.0

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
# O6: one unwired event stream used to stop the whole service
# --------------------------------------------------------------------------- #


def _free_loopback_port() -> int:
    """Ask the kernel for a port, the way every other socket here does."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _new_anonymous_pipe() -> tuple[int, int]:
    """An anonymous pipe, with a requested capacity where the platform takes one.

    Linux accepts ``pipe_size``; Windows does not, and its default is small
    enough already. Asking for a bounded capacity is what keeps the probe's dose
    bounded on a platform whose default pipe is an order of magnitude larger —
    the dose is sized from the pipe (see `_pipe_capacity`), so a pipe that needs
    a hundred streams to fill is a probe that spends a hundred timeouts getting
    to its red.

    The keyword goes through a dict rather than in the call, because the type
    stubs are the platform's: the Windows stubs say ``os.pipe()`` takes no
    argument, and naming one there would be a claim about the platform this file
    is type-checked on rather than about the code. The ``TypeError`` is the
    platform saying so, and it is the path Windows takes.
    """
    try:
        return os.pipe(**O6_PIPE_CAPACITY_KWARGS)
    except TypeError:
        return os.pipe()


def _pipe_capacity() -> int:
    """How many bytes a fresh anonymous pipe holds before a write stops fitting.

    Measured, not carried: it is the quantity the stall depends on, and it is
    not one number — **4,096 bytes on this machine** (measured 2026-11-10, and a
    `subprocess.PIPE` sweep put the same boundary between 4,096 and 4,608), while
    a Linux pipe defaults to an order of magnitude more. A witness with a
    hard-coded dose would be a witness on one platform and an anecdote on the
    other.

    **It is measured with a non-blocking writer, and that is not an
    implementation detail.** On a full pipe a blocking write does not raise — it
    waits (measured: 4,096 bytes accepted, then the writer parked with no error).
    That *is* the defect, so a capacity probe that writes in blocking mode is a
    probe that reproduces the defect on itself and hangs. `BlockingIOError` is
    what says the pipe is full, and only a non-blocking descriptor produces it.
    """
    read_fd, write_fd = _new_anonymous_pipe()
    try:
        os.set_blocking(write_fd, False)
        fitted = 0
        while True:
            try:
                # What `os.write` *says* it wrote, not what was asked for: a
                # partial write returns the count it managed, and adding 1024
                # per call would report a capacity the pipe never held.
                fitted += os.write(write_fd, b"x" * 1024)
            except BlockingIOError:
                return fitted
    finally:
        os.close(read_fd)
        os.close(write_fd)


def _o6_arrangement(root: Path, *, drained: bool, dose: int) -> dict[str, object]:
    """One service, one unwired stream, and the reads on both sides of it.

    **Why a subprocess at all.** The stall is a blocked write to the *process's
    own stdout*, and a pytest process whose stdout is a pipe nobody reads is
    exposed to it exactly as the service is. A probe that parked the pytest
    process would take the run down instead of reporting what it saw, so the
    service runs in a child of this file and reports through a file.

    The service is built the way the product builds it — ``create_app`` over a
    real store in a real workspace, and no event source — and it is served by a
    real uvicorn on a real loopback port. It is not the console script: that
    script is a compiled launcher whose editable-install ``.pth`` can point at
    another checkout's ``src``, so a measurement taken through it can be a
    measurement of somebody else's code. A child of this file imports this
    checkout, which is what the change landed in.

    ``drained`` says whether anything reads the service's output while it runs.
    That is the whole difference between the two arrangements, and it is the
    difference between the arrangement that stalls and the one that does not:
    ``tests/workbench_serve_helper.py`` writes the service's log to a *file*
    for exactly this reason, and the selection window's probes used a pipe
    nobody read.

    The output is redirected with ``dup2`` onto a real anonymous pipe rather than
    onto a file object, because the thing being probed is a *pipe's capacity* and
    a file has no capacity to fill. It is the same kind of pipe the capacity probe
    measured (`_new_anonymous_pipe`), so the dose the parent computed is a dose for
    the pipe this arrangement is actually running against — and both the measured
    capacity and the dose it produced are in the report.
    """
    import uvicorn

    pipe_read, pipe_write = _new_anonymous_pipe()
    saved_out, saved_err = os.dup(1), os.dup(2)
    os.dup2(pipe_write, 1)
    os.dup2(pipe_write, 2)

    captured: list[bytes] = []

    def drain() -> None:
        while True:
            try:
                chunk = os.read(pipe_read, 65536)
            except OSError:
                break
            if not chunk:
                break
            captured.append(chunk)

    drain_thread: threading.Thread | None = None
    if drained:
        drain_thread = threading.Thread(target=drain, daemon=True)
        drain_thread.start()

    try:
        with _service(root) as (app, _task_id):
            port = _free_loopback_port()
            server = uvicorn.Server(
                uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
            )
            loop_thread = threading.Thread(target=server.run, daemon=True)
            loop_thread.start()
            base = f"http://127.0.0.1:{port}"

            def ask(path: str, timeout: float = O6_REQUEST_TIMEOUT) -> dict[str, object]:
                started = time.monotonic()
                try:
                    with urllib.request.urlopen(base + path, timeout=timeout) as reply:
                        reply.read()
                        status: object = reply.status
                except urllib.error.HTTPError as exc:
                    # A refusal the client can see. The unwired stream's answer
                    # is one of these, and it is recorded as the status it is
                    # rather than as a failure: the point of the refusal is that
                    # it reached the reader.
                    status = exc.code
                except (urllib.error.URLError, OSError, TimeoutError) as exc:
                    status = f"no answer: {type(exc).__name__}"
                return {
                    "path": path,
                    "status": status,
                    "ms": round((time.monotonic() - started) * 1000),
                }

            for _ in range(200):
                if ask("/health", timeout=2.0)["status"] == 200:
                    break
                time.sleep(0.1)

            before = [ask(path) for path in O6_READS]
            streams: list[dict[str, object]] = []
            stalled_after: int | None = None
            for index in range(dose):
                streams.append(ask("/events/stream?follow=false", timeout=30.0))
                # Watch for the stall between the streams rather than only after
                # the whole dose. On the unfixed service the pipe fills partway
                # through, and a probe that pays every remaining 8-second
                # timeout is a probe that takes minutes to say what it already
                # knows — while this line says *at which stream* the service
                # stopped answering.
                if ask("/health", timeout=2.0)["status"] != 200:
                    stalled_after = index + 1
                    break
            after = [ask(path) for path in O6_READS]
            answered = sum(1 for r in after if r["status"] == 200)

            # The rescue the mechanism was measured with. If nothing has been
            # reading this output, start reading it now: a loop parked in a
            # write to a full pipe is stopped by nothing else, and a probe that
            # leaves it parked ends by hanging rather than by reporting. On the
            # fixed service this changes nothing — there is nothing parked.
            if drain_thread is None:
                drain_thread = threading.Thread(target=drain, daemon=True)
                drain_thread.start()

            server.should_exit = True
            loop_thread.join(timeout=60)
    finally:
        # Put the process's own output back before anything else, so a failure
        # after here can still be reported. Then close the pipe's write end and
        # let a drain thread finish collecting what it read.
        os.dup2(saved_out, 1)
        os.dup2(saved_err, 2)
        os.close(saved_out)
        os.close(saved_err)
        os.close(pipe_write)
        if drain_thread is not None:
            drain_thread.join(timeout=20)
        os.close(pipe_read)

    return {
        "before": before,
        "streams": streams,
        "after": after,
        "answered_after": f"{answered} / {len(after)}",
        "dose": dose,
        "stalled_after_stream": stalled_after,
        "service_output_bytes": sum(len(chunk) for chunk in captured),
    }


def _o6_main(workspace: Path) -> int:
    """Run both arrangements and write what each one saw.

    **The dose is sized from the pipe, not from a remembered number.** The
    capacity is measured on the machine running this probe and divided by the
    measured per-stream cost, floored at the dose that overflowed this machine's
    pipe and capped so a red run stays fast. The numbers the probe used are in
    the report, so a dose that had to be capped is visible in the failure rather
    than silently too small to witness anything.

    The report is written after *each* arrangement: on the unfixed service the
    second one ends with the application parked in a write, and a report that
    is only written at the end is a report a red run never gets to read.
    """
    report = workspace / "o6-report.json"
    phases: dict[str, object] = {}

    capacity = _pipe_capacity()
    needed = -(-capacity // O6_UNWIRED_STREAM_FLOOR) + 1
    dose = max(O6_DOSE_MIN, min(needed, O6_DOSE_MAX))

    def publish() -> None:
        report.write_text(json.dumps(phases), encoding="utf-8")

    phases["pipe_capacity_bytes"] = capacity
    phases["dose"] = dose
    phases["dose_capped"] = needed > O6_DOSE_MAX
    publish()
    phases["drained"] = _o6_arrangement(workspace / "drained", drained=True, dose=dose)
    publish()
    phases["undrained"] = _o6_arrangement(workspace / "undrained", drained=False, dose=dose)
    publish()
    return 0


def test_one_unwired_event_stream_leaves_the_service_able_to_answer(tmp_path: Path) -> None:
    """O6, witnessed: the service still answers everything across an unwired stream.

    **The defect, as it was measured** (`docs/acceptance/`'s O6 record; the
    selection window's §9 and §11): on a service with no event source, one
    ``GET /events/stream`` — even the short ``follow=false`` form — was followed
    by **nothing**. Every later request timed out at the client's 8 seconds,
    ``/health`` and ``/openapi.json`` included, while the process stayed alive
    and the port still accepted a connection.

    **What the measurement says the mechanism was.** The refusal was raised
    *after* the ``200`` and ``text/event-stream`` headers had gone out, so it
    could not become a response; what the service wrote instead was a traceback
    — **6,205 bytes for one short stream, measured**, against a pipe that holds
    **8,192 bytes here and 4,096 for a subprocess pipe here, measured** — into
    whatever the caller had attached to its output. A caller that captures that
    output in a pipe it does not read has a pipe that fills, and a writer parked
    in a full pipe is an event loop that has stopped serving every request in
    the process.

    **The dose is sized from the pipe, not from a remembered number,** because
    the capacity is not one number across platforms: the probe measures the
    capacity it is about to work against and opens enough streams to overflow
    it at the measured per-stream cost. That is the difference between a witness
    and a Windows-only anecdote. The capacity, the dose and whether the dose had
    to be capped are all in the report, and the test asserts the dose could fill
    the pipe at all — a dose that could not is a witness witnessing nothing, and
    it says so rather than passing.

    **What the test asserts is the property, not the mechanism:** after streams
    it was never going to answer, the service answers every ordinary read. Both
    arrangements are run — the service's output drained, and its output in a
    pipe nobody reads — because the second is the arrangement the defect was
    measured in, and a witness that only runs in the safe one witnesses nothing.
    The drained arm is the control that says the probe itself is sound, and its
    byte count is the mechanism-level assertion: a refusal that reaches the
    client *as a response* costs the service nothing to write, so a number over
    the budget means the service is producing a traceback again.
    """
    workspace = tmp_path / "o6"
    workspace.mkdir()

    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--o6", str(workspace)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=900,
    )
    died = _how_it_died(result.returncode)
    report = workspace / "o6-report.json"
    seen = report.read_text(encoding="utf-8") if report.is_file() else "<no report>"
    assert result.returncode == 0, (
        f"the O6 probe did not survive: exit {result.returncode}"
        + (f", {died}" if died else "")
        + f"\n--- what it got to ---\n{seen}\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )
    assert report.is_file(), (
        "the O6 probe survived and reported nothing, which means the probe is "
        f"not measuring the thing it is named for: {report}"
    )

    phases = json.loads(report.read_text(encoding="utf-8"))

    capacity = phases["pipe_capacity_bytes"]
    dose = phases["dose"]
    assert isinstance(capacity, int) and isinstance(dose, int), phases
    assert dose * O6_UNWIRED_STREAM_FLOOR > capacity, (
        f"the probe opened {dose} stream(s) against a {capacity}-byte pipe, and at the "
        f"{O6_UNWIRED_STREAM_FLOOR}-byte-per-stream floor that dose cannot fill the pipe. "
        "The witness would be asserting a property in an arrangement that could not have "
        "shown the defect: raise O6_DOSE_MAX, or measure the arrangement again on a "
        "machine whose pipe this dose can overflow."
    )

    for label in ("drained", "undrained"):
        assert label in phases, f"the probe never ran the {label} arrangement: {phases}"
        phase = phases[label]
        assert isinstance(phase, dict), phase
        expected = f"{len(O6_READS)} / {len(O6_READS)}"
        assert phase["answered_after"] == expected, (
            f"the service stopped answering ordinary reads after {phase['dose']} unwired "
            f"stream(s) in the {label} arrangement — this is O6, back, and it stalled at "
            f"stream {phase['stalled_after_stream']}: {json.dumps(phase['after'])}"
        )

    drained_phase = phases["drained"]
    assert isinstance(drained_phase["service_output_bytes"], int)
    assert drained_phase["service_output_bytes"] < O6_LOG_BUDGET, (
        f"the service wrote {drained_phase['service_output_bytes']} bytes into its own "
        f"output across the probe, over the {O6_LOG_BUDGET}-byte budget. That is the "
        "stall's fuel: the number is what the service costs itself to refuse an unwired "
        "stream, and an unwired refusal answered as a response costs it nothing."
    )


# --------------------------------------------------------------------------- #
# the burst and the O6 probe, as programs
# --------------------------------------------------------------------------- #


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--o6":
        raise SystemExit(_o6_main(Path(sys.argv[2])))
    raise SystemExit(_burst_main(Path(sys.argv[1])))
