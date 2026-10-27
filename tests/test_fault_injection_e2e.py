"""Fault injection through the surfaces: a real process, killed, and the state on disk.

**What this file is.** G5's own fault injection, run *through a surface*
rather than at the layer. ``tests/test_recovery_crash_matrix.py`` puts a
fault at a named :class:`~labcairn.recovery.contracts.CrashPoint` inside the
executor and asserts what the world looks like afterwards. This file puts the
crash in a **CLI process**, kills that process the way a crash kills one, and
then asks the surfaces what they make of what was left behind on disk.

**The product has no switch for injecting a crash from outside.** The fault
injector lives in the test support module (``tests/test_recovery_support.py``),
not in ``src/``, so a crash cannot be *asked for* through the CLI or the
service. What the product does offer is that its code runs in a process the
test owns, and the test can decide **when** that process stops. So the crash
is placed by pausing the real code at a named point and letting the parent
kill the process: the child writes a sentinel and blocks, the parent waits for
the sentinel and then kills it with ``taskkill /F`` on Windows and ``SIGKILL``
on POSIX — the same two ways ``AT-7`` ends a child.

**No file under ``src/`` is changed, and the pause changes nothing about what
the product does.** It decides *when* the child stops, and the parent's kill
is what ends it. Nothing here asks the product to behave differently; the
product is run, and then it is killed.

**The windows.** ``run_stage`` writes the operation's records in the order
that makes a crash answerable: the intent, then the attempt, then the effect,
then the confirmation. A crash can therefore land in two places that matter,
and they are not the same case.

* **Before the attempt is durable** — the intent committed and the attempt did
  not. Nothing was attempted, so the operation is still ``AUTHORIZED``, and
  the next run **adopts** it: one operation for the work, one attempt, one
  confirmation. This is ADR-0003 C2's first row, and the application layer
  already has a rule for it (``_find_operation``: *"a run that follows a crash
  reuses the operation that was authorised but never attempted"*).
* **After the effect and before the confirmation** — the work happened and the
  record of it did not. This is ADR-0003 C2's *only bad case*, and the
  recovery layer is what answers it: ``UNCERTAIN`` is a state recovery
  **enters**, never one it assumes away, and only a probe may resolve it.

And a third window, in the **ingestion**, which is the one place the CLI
*writes*: the material is written one file at a time, so a crash there leaves
the ledger holding some of the material and not the rest.

**What the surfaces do with the second window is the recovery pass, and it runs
at the front of every stage run.** `labcairn.application.recovery` moves an
operation a crash left ``ATTEMPTING`` into ``UNCERTAIN``, blocks its stage with
the reason the recovery layer states, and **refuses** the run rather than
planning a second operation for work whose outcome is unknown. (The window
between the two is the same on disk: a crash after the attempt commits but
before the effect runs leaves exactly the same record, and the effect never ran
at all — which is the point of ``UNCERTAIN``, and the reason a probe rather than
a flag is what resolves it.)

**What the pass does not do is answer the doubt by itself.** The hash a probe
compares against lived inside ``args_digest``, which is a hash of a hash, so no
value on disk supplies it and the operator does: ``labcairn task reconcile
<operation-id> --expected-sha256 <hash>``. That is the difference between a
recovery and a guess, and it is why the run is refused rather than replayed.

That is the protocol's fourth blocker in the shape it takes at a surface, and it
is watched here rather than described:
:func:`test_the_surfaces_enter_uncertain_and_refuse_an_abandoned_operation`
counts the operations and the events, and
:func:`test_a_run_refused_for_an_uncertain_operation_does_not_spend_its_approval`
says the refusal consumed nothing.

**What this file does assert** is the four things that breakdown's §2.3
names, and each of them is watched where it can fail — **with one exception,
and the exception is stated rather than rounded off:**

============================  ==========================================================
no repeated operation        **holds**: an authorised operation is adopted, and an
                             operation a crash abandoned is entered into
                             ``UNCERTAIN`` with the run refused, so one piece of
                             work is never *planned* twice. **The limit is the
                             bookkeeping, not the effect** — a probe can say the
                             effect landed, and the transaction the crash
                             interrupted (confirmation, completed stage,
                             receipts) is performed by the run that follows, so
                             the log holds two operations for one work whose side
                             effect happened once. See
                             ``test_a_task_continues_from_what_was_recorded_after_a_crash``
no duplicated side effect    the material a crashed ingestion had already written
                             is written once: the second run writes no rows for
                             it, and the store holds no second copy
the report is regenerated    the stage's output is regenerated from the state on
or refused with a reason     disk; and when the policy asks about the capability
                             the run is **refused with a reason** and plans nothing
the state is on disk         the task, its run, its stage and its operation are
                             on disk, and a fresh CLI process and a fresh service
                             both read them back
============================  ==========================================================

**The exception is a limit, not an omission, and it is watched.** §1.3 of the
breakdown says G5 measures and hands over, and the pass it handed over missing is
now wired into the layer. What remains is the half a probe cannot do — recording
the completion of work whose confirmation the crash interrupted — and it is
asserted above rather than closed by claiming the two halves are one thing.

**What the service can and cannot show.** The service is task-scoped and
serves the state the store holds, so a service that is killed and restarted
comes back to the same state — that is the "forced-restart task continuation"
the protocol asks for, at the second surface. The service cannot run a stage
in this build: the CLI's ``serve`` gives the application no stage work, and
``POST /stages`` is refused with ``not_implemented``. So a crash through the
service cannot leave a half-done stage; the crash this file places is the
CLI's, and the service is the second reader of what the CLI left behind.

**Every assertion here is read back from the disk, through a session of its
own.** SQLAlchemy's identity map would otherwise answer with what a session
read before the crash — which is exactly the failure a test like this exists
to find.
"""

from __future__ import annotations

import http.client
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any
from uuid import UUID

import pytest
from sqlalchemy import func, select

from labcairn.cli.commands import EXIT_REFUSED
from labcairn.core.ids import TaskId
from labcairn.db.models import SourceTextRow
from labcairn.db.repository import (
    events_after,
    list_operations,
    list_sources,
    load_source,
    load_task,
)
from labcairn.db.session import create_db_engine, create_session_factory

# The payload schema an ``operation_reconciled`` event carries is registered when
# :mod:`labcairn.recovery.reconciliation` is imported, and ADR-0007's rule is that
# an event with an unregistered schema must have an empty payload — so a reader of
# the ledger that never imported the writer's module cannot read the event at all.
# Every product reader reaches it through the application layer, which imports the
# recovery module; this file reads the store directly, so it imports it too.
# The wart is recorded as a carried issue in ``docs/PHASE_1_WORKORDERS.md``.
from labcairn.recovery import reconciliation as _reconciliation  # noqa: F401
from labcairn.runtime.event import Event, EventType
from labcairn.runtime.operation import Operation, OperationState

# --------------------------------------------------------------------------- #
# the windows a crash can land in
# --------------------------------------------------------------------------- #

#: The intent committed; the attempt did not. Nothing was attempted, so the
#: operation is still ``AUTHORIZED`` and the next run adopts it.
BEFORE_ATTEMPT = "before_attempt"

#: The effect ran; the confirmation did not. ADR-0003 C2's only bad case, and
#: the one the recovery layer exists to answer.
AFTER_THE_EFFECT = "after_the_effect"

#: Inside the ingestion, after one material has been written.
DURING_INGEST = "during_ingest"

#: The fault planted in the child, from outside.
#:
#: The child is the real CLI. This module is put on the child's ``PYTHONPATH``
#: as ``sitecustomize``, which Python imports at start-up, so the pause is in
#: place before the command's first line runs.
#:
#: **It changes no behaviour.** It pauses the real code at a named point, and
#: the parent's kill is what ends the process. The window it pauses in is
#: named by the environment, so the same file serves all three.
INJECTOR = '''
"""A pause planted in the child, from outside.

The product is run; this only decides *when* it stops. The parent waits for
the sentinel and then kills the process, so the crash is the parent's kill
and not an exit this module performs.
"""

import os
import pathlib
import time

WINDOW = os.environ["F5_WINDOW"]
SENTINEL = pathlib.Path(os.environ["F5_SENTINEL"])


def reach() -> None:
    """Say the window was reached, and wait to be killed."""
    SENTINEL.write_text(WINDOW, encoding="utf-8")
    time.sleep(600)


if WINDOW == "before_attempt":
    import labcairn.application.records as records
    from labcairn.runtime.event import EventType

    _original = records.move_operation

    def move_operation(context, operation, *, event, to_state, now):
        if event is EventType.OPERATION_ATTEMPTED:
            reach()
        return _original(context, operation, event=event, to_state=to_state, now=now)

    records.move_operation = move_operation

elif WINDOW == "after_the_effect":
    # The effect is the caller's, and the layer calls it between the attempt
    # and the confirmation. Pausing it there is the crash of ADR-0003 C2's
    # only bad case: the work happened and the record of it did not.
    import labcairn.application as application

    _original = application.run_stage

    def run_stage(context, request, work, *, now=None):
        def _work(resource):
            outcome = work(resource)
            reach()
            return outcome

        return _original(context, request, _work, now=now)

    application.run_stage = run_stage

elif WINDOW == "during_ingest":
    import labcairn.material.walk as walk

    _original = walk.ingest_into_store
    _reached = []

    def ingest_into_store(session, data, **kwargs):
        outcome = _original(session, data, **kwargs)
        if not _reached:
            _reached.append(True)
            reach()
        return outcome

    walk.ingest_into_store = ingest_into_store

else:  # pragma: no cover - only the three windows above are asked for
    raise SystemExit("unknown crash window " + repr(WINDOW))
'''


# --------------------------------------------------------------------------- #
# running the CLI
# --------------------------------------------------------------------------- #


def _console_script() -> Path:
    """The script a developer types, as this interpreter would find it.

    Beside the running interpreter rather than on ``PATH``: the test must
    exercise the script the project installs, and ``PATH`` is the machine's
    business.
    """
    name = "labcairn.exe" if os.name == "nt" else "labcairn"
    return Path(sys.executable).parent / name


def _environment(**extra: str) -> dict[str, str]:
    """The child's environment.

    **Both ends of the pipe state their encoding.** The CLI prints em-dashes
    and the paths it worked with, so its output is not ASCII. Leaving either
    half to the machine's locale is how a command comes back *broken for a
    reason that says nothing about it*.
    """
    return {**os.environ, "PYTHONIOENCODING": "utf-8", "COLUMNS": "200", **extra}


@dataclass(frozen=True, slots=True)
class CliResult:
    """What one run of the CLI produced."""

    returncode: int
    stdout: str
    stderr: str

    def json(self) -> Any:
        """The machine-readable form, parsed."""
        return json.loads(self.stdout)


def run_cli(*args: str, env: Mapping[str, str] | None = None) -> CliResult:
    """The CLI, run as a process.

    As a process rather than in this one, because the exit code and the two
    streams are what a script depends on and a call in this process would not
    produce them.
    """
    script = _console_script()
    if not script.is_file():
        pytest.fail(
            f"the console script is not installed at {script}. The CLI is tested "
            "through the script a developer types, so it has to be there; run "
            "`uv sync`."
        )
    completed = subprocess.run(
        [str(script), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=dict(env) if env is not None else _environment(),
        timeout=600,
    )
    return CliResult(completed.returncode, completed.stdout, completed.stderr)


def hard_kill(child: subprocess.Popen[Any]) -> None:
    """Terminate without giving the child a chance to clean up.

    On POSIX this is ``SIGKILL``; on Windows ``taskkill /F``, which is the same
    ``TerminateProcess`` semantics — no ``finally``, no atexit, no buffer
    flush. A graceful kill would make this file prove nothing that the
    in-process injected crash does not already prove.
    """
    if os.name == "nt":  # pragma: no cover - platform branch
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(child.pid)],
            capture_output=True,
            check=False,
        )
        return
    sigkill = getattr(signal, "SIGKILL", None)
    assert sigkill is not None, "SIGKILL is always defined on POSIX"
    os.kill(child.pid, sigkill)


# --------------------------------------------------------------------------- #
# the crash
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Crash:
    """The fault injector, and the place the child reports it reached a window."""

    inject: Path
    sentinel: Path

    def place(self, *args: str, window: str) -> None:
        """Run the CLI as a process and kill it inside *window*.

        The child announces the window it reached by writing a sentinel file
        before it blocks, so the parent kills it only once the code is
        genuinely in the window under test rather than merely somewhere near
        it.
        """
        self.sentinel.unlink(missing_ok=True)
        child = subprocess.Popen(
            [str(_console_script()), *args],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            env=_environment(
                PYTHONPATH=str(self.inject),
                F5_WINDOW=window,
                F5_SENTINEL=str(self.sentinel),
            ),
        )
        try:
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                if self.sentinel.exists():
                    break
                if child.poll() is not None:
                    raise AssertionError(self._died(child))
                time.sleep(0.05)
            else:  # pragma: no cover - the child never reached the window
                raise AssertionError(f"the CLI never reached the {window} window")

            # Still alive: the sentinel is written *before* the pause, so its
            # presence proves the window was reached, but only liveness proves
            # the kill is what ended the child rather than something else.
            assert child.poll() is None, (
                "the child exited on its own instead of blocking in the crash "
                "window; the kill would then prove nothing"
            )
            hard_kill(child)
            child.wait(timeout=60)
            assert child.returncode != 0, (
                f"a hard-killed process cannot exit 0; got {child.returncode}"
            )
        finally:
            if child.poll() is None:  # pragma: no cover
                hard_kill(child)
            if child.stderr is not None:
                child.stderr.close()

    @staticmethod
    def _died(child: subprocess.Popen[bytes]) -> str:
        """The child's own error, rather than a bare "did not reach".

        A test that reports only "the CLI never reached the window" sends the
        reader looking for a timing problem when the real fault is an import
        error in the child three lines away.
        """
        if child.stderr is None:  # pragma: no cover
            return "the CLI died before reaching the crash window"
        detail = child.stderr.read().decode("utf-8", errors="replace")[-2000:]
        return f"the CLI died before reaching the crash window:\n{detail}"


@pytest.fixture
def crash(tmp_path: Path) -> Crash:
    """The injector, written where only the crashing child will find it."""
    inject = tmp_path / "inject"
    inject.mkdir()
    (inject / "sitecustomize.py").write_text(INJECTOR, encoding="utf-8")
    return Crash(inject=inject, sentinel=tmp_path / "reached-window.marker")


# --------------------------------------------------------------------------- #
# the workspace, and the task in it
# --------------------------------------------------------------------------- #

#: The material the task is bound to. One file, so that the ledger's shape
#: after a crash is a fact about the crash and not about how many files there
#: were.
MATERIAL_NAME = "notes.md"
MATERIAL_BODY = "# Notes\n\nThe observation holds.\n"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A workspace the CLI itself made."""
    root = tmp_path / "workspace"
    result = run_cli("--workspace", str(root), "init")
    assert result.returncode == 0, f"init failed: {result.stderr}"
    return root


def _make_a_task(workspace: Path, *, with_material: bool) -> str:
    """A task the CLI itself made, and its id.

    *with_material* says whether the workspace holds a material file when the
    task is made. A task created with material binds it; one created without
    holds nothing until an ingestion gives it something.
    """
    materials = workspace / "materials"
    materials.mkdir(parents=True, exist_ok=True)
    if with_material:
        (materials / MATERIAL_NAME).write_text(MATERIAL_BODY, encoding="utf-8")
    result = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "create",
        "--title",
        "Read the corpus",
        "--objective",
        "Establish what the corpus says about the question.",
        "--criterion",
        "A cited answer, or an honest 'not established'.",
        "--json",
    )
    assert result.returncode == 0, f"task create failed: {result.stderr}"
    return str(result.json()["task_id"])


@pytest.fixture
def task(workspace: Path) -> str:
    """A task the CLI itself made, with one material bound to it."""
    return _make_a_task(workspace, with_material=True)


def _bound_source(workspace: Path, task_id: str) -> str:
    """The source id the task holds, as the store holds it."""
    with _session(workspace) as session:
        bound = load_task(session, TaskId(UUID(task_id))).bound_source_ids
        assert bound, "the task holds no source, so there is nothing to inventory"
        return str(bound[0])


# --------------------------------------------------------------------------- #
# reading the store
# --------------------------------------------------------------------------- #


@contextmanager
def _session(workspace: Path) -> Iterator[Any]:
    """A session of its own on the workspace's database.

    **Its own, every time.** A session that had read the store before the
    crash would answer with its identity map rather than with the database,
    and would hide exactly the bug these tests exist to find: a write that
    rolled back is still visible in the session cache and reads as committed.
    """
    engine = create_db_engine(workspace / "labcairn.db")
    factory = create_session_factory(engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@dataclass(frozen=True, slots=True)
class Ledger:
    """What the store holds about one task's work, read from disk."""

    operations: tuple[Operation, ...]
    events: tuple[Event, ...]

    @property
    def event_types(self) -> tuple[EventType, ...]:
        return tuple(event.type for event in self.events)

    def count(self, event_type: EventType) -> int:
        """How many events of this type the task holds."""
        return sum(1 for kind in self.event_types if kind is event_type)


def read_ledger(workspace: Path, task_id: str) -> Ledger:
    """The task's operations and events, read through a session of their own."""
    with _session(workspace) as session:
        identifier = TaskId(UUID(task_id))
        return Ledger(
            operations=list_operations(session, identifier),
            events=events_after(session, identifier),
        )


def count_text_rows(workspace: Path, content_sha256: str) -> int:
    """How many extracted rows the store holds for one material.

    Counted by the content hash, because that is the key the text is stored
    under: a second copy of the same material would be a second set of rows
    under the same hash.
    """
    with _session(workspace) as session:
        return int(
            session.scalar(
                select(func.count())
                .select_from(SourceTextRow)
                .where(SourceTextRow.source_content_sha256 == content_sha256)
            )
            or 0
        )


def list_source_rows(workspace: Path) -> tuple[Any, ...]:
    """The ledger's sources, as the store holds them."""
    with _session(workspace) as session:
        return list_sources(session)


# --------------------------------------------------------------------------- #
# the policy
# --------------------------------------------------------------------------- #


def _set_the_inventory_rule(workspace: Path, effect: str) -> None:
    """Change what the policy says about inventorying the material.

    The policy file is the workspace's own, and the CLI writes it so that the
    operator can see it and change it. This is that change, made the way the
    operator would make it.
    """
    path = workspace / ".labcairn" / "policy.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    changed = [
        rule for rule in document["rules"] if rule.get("capabilities") == ["source.inventory"]
    ]
    assert len(changed) == 1, (
        "the workspace's policy does not hold exactly one rule about "
        f"source.inventory, so it cannot be changed: {document['rules']!r}"
    )
    changed[0]["effect"] = effect
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# the service
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class RunningService:
    """A service that is really running, and the way to stop it."""

    host: str
    port: int
    process: subprocess.Popen[str]
    out_lines: list[str]
    err_lines: list[str]
    readers: list[threading.Thread]

    def get(self, path: str) -> tuple[int, str]:
        """One request to the running service."""
        return _request(self.host, self.port, path)

    def stop(self) -> None:
        """Stop the service, and let go of the port it held.

        Idempotent, so a test may stop the service to look at its output and
        the fixture may stop it again on the way out.
        """
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=30)
            except subprocess.TimeoutExpired:  # pragma: no cover - the service ignored it
                hard_kill(self.process)
                self.process.wait(timeout=30)
        for reader in self.readers:
            reader.join(30)


def _request(host: str, port: int, path: str) -> tuple[int, str]:
    """One request to the service, and its status and body.

    ``http.client`` rather than ``urllib``, because urllib consults the
    environment's proxy settings and a proxied request to the loopback address
    would not reach the service at all.
    """
    connection = http.client.HTTPConnection(host, port, timeout=30)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        return response.status, response.read().decode("utf-8")
    finally:
        connection.close()


def _collect(stream: IO[str] | None, lines: list[str]) -> None:
    """Read a stream as it arrives, until it ends."""
    if stream is None:  # pragma: no cover - the pipes are always there
        return
    try:
        for line in stream:
            lines.append(line)
    except (OSError, ValueError):  # pragma: no cover - the pipe was closed
        return


def _free_port() -> int:
    """A port the operating system says is free.

    Never the default port: 8000 is the port the workbench's proxy points at,
    so it is the port a developer will have something on, and a test that
    failed because the machine's 8000 was busy would be a test that fails at
    random.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def start_service(workspace: Path) -> RunningService:
    """The service, really running, on a port the machine had free.

    **The command is run through the interpreter, not through the console
    script's launcher.** On Windows that launcher is a program which runs the
    script in a child process, so stopping the launcher can leave the child
    running — and a service still running after the test that started it is a
    service that holds a port for the rest of the run. The interpreter runs
    the very same script.
    """
    failures: list[str] = []
    for _ in range(3):
        port = _free_port()
        process = subprocess.Popen(
            [
                sys.executable,
                str(_console_script()),
                "--workspace",
                str(workspace),
                "serve",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--json",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=_environment(),
        )
        out_lines: list[str] = []
        err_lines: list[str] = []
        readers = [
            threading.Thread(target=_collect, args=(process.stdout, out_lines), daemon=True),
            threading.Thread(target=_collect, args=(process.stderr, err_lines), daemon=True),
        ]
        for reader in readers:
            reader.start()
        try:
            _wait_for_the_service(process, port)
        except _ServiceDidNotStartError as error:
            failures.append(str(error))
            if process.poll() is None:
                hard_kill(process)
                process.wait(timeout=30)
            continue
        return RunningService(
            host="127.0.0.1",
            port=port,
            process=process,
            out_lines=out_lines,
            err_lines=err_lines,
            readers=readers,
        )
    raise AssertionError("the service did not start: " + "; ".join(failures))


class _ServiceDidNotStartError(RuntimeError):
    """The command did not become a service."""


def _wait_for_the_service(
    process: subprocess.Popen[str], port: int, timeout: float = 120.0
) -> None:
    """Wait until the service answers, or the command gives up."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise _ServiceDidNotStartError(f"the command exited with {process.returncode}")
        try:
            status, _ = _request("127.0.0.1", port, "/health")
        except OSError:
            status = 0
        if status == 200:
            return
        time.sleep(0.2)
    raise _ServiceDidNotStartError("the service did not answer /health in time")


# --------------------------------------------------------------------------- #
# the tests
# --------------------------------------------------------------------------- #


@pytest.mark.e2e
def test_a_crash_through_the_cli_leaves_the_task_state_on_disk(
    workspace: Path, task: str, crash: Crash
) -> None:
    """The task, its run, its stage and its operation survive the crash.

    The crash is placed in ADR-0003 C2's only bad case: the stage's effect
    has run and the confirmation of it has not. The process died with the
    work half-done, which is the one situation in which nothing on disk can
    say whether the work happened.

    **What is asserted is what the surfaces make of it.** The store holds the
    task's records; the CLI — a *fresh process*, reading the same database
    file — reports them; and the service, also a fresh process, reports the
    same document. **And the work is not claimed to be done**: the operation
    is still ``ATTEMPTING``, there is no confirmation, no completed stage and
    no output hash. A crash that left the surface claiming success would be
    the failure this test exists to catch.

    **What the surfaces do next is a finding, and it is not asserted here.**
    Nothing under ``src/labcairn/application/`` runs the recovery pass, so the
    abandoned operation is never reconciled and the next ``task run`` plans a
    second operation for the same work. That is the protocol's fourth blocker
    in the shape it takes at a surface, and this gate measures findings
    rather than fixing them
    (``docs/plans/LC-P1-13-14-task-breakdown.md`` §1.3).
    """
    source_id = _bound_source(workspace, task)

    crash.place(
        "--workspace",
        str(workspace),
        "task",
        "run",
        "--source",
        source_id,
        window=AFTER_THE_EFFECT,
    )

    # -- the store holds the task's records --------------------------------- #
    ledger = read_ledger(workspace, task)
    assert len(ledger.operations) == 1, (
        "the crash must leave the operation it was running on disk, or there "
        "is nothing for the surfaces to come back to"
    )
    assert ledger.operations[0].state is OperationState.ATTEMPTING, (
        "the operation must not read as confirmed: the process died before "
        "the confirmation, and the store cannot tell whether the effect ran"
    )
    assert ledger.count(EventType.OPERATION_ATTEMPTED) == 1
    assert ledger.count(EventType.OPERATION_CONFIRMED) == 0, (
        "the confirmation must not be there: the process died before it"
    )
    assert ledger.count(EventType.STAGE_COMPLETED) == 0

    # -- the CLI, a fresh process, reads the same state --------------------- #
    reported = run_cli("--workspace", str(workspace), "task", "status", "--json")
    assert reported.returncode == 0, reported.stderr
    state = reported.json()
    assert state["task"]["task_id"] == task
    assert state["runs"][0]["status"] == "running"
    assert state["stages"][0]["status"] == "entered", (
        "the stage must not read as finished: the process died inside it"
    )
    assert state["stages"][0]["output_hashes"] == [], (
        "the stage must carry no output: nothing confirmed it"
    )

    # -- and so does the service -------------------------------------------- #
    running = start_service(workspace)
    try:
        status, body = running.get("/task")
    finally:
        running.stop()
    assert status == 200
    assert json.loads(body) == state, (
        "the two surfaces must say the same thing about the same task: they "
        "are the same model read from the same store, and a task that reads "
        "differently through the CLI and the service is a task nobody can "
        "reason about"
    )


@pytest.mark.e2e
def test_a_task_continues_from_what_was_recorded_after_a_crash(
    workspace: Path, task: str, crash: Crash
) -> None:
    """The task continues, in a new attempt, and the crashed attempt is kept.

    This is the protocol's *"forced-restart task continuation demonstrated"*:
    a restart **in the middle of a task**, with the surfaces, and the task
    continues from what was recorded.

    **A resume is a new Run against the same Task** (ADR-0003 C1, R-02) — the
    task's identity survives every attempt and the attempt number is what
    says how many there have been. So the continuation is a second run of the
    same task, and what it must not do is *erase* the first one: the run that
    crashed, its stage and its abandoned operation are still on disk, because
    a record that a crash removed is a record nobody can reason about.

    And the report is regenerated: the new run's stage completes with the
    material's own content hash.
    """
    source_id = _bound_source(workspace, task)

    crash.place(
        "--workspace",
        str(workspace),
        "task",
        "run",
        "--source",
        source_id,
        window=AFTER_THE_EFFECT,
    )

    crashed = read_ledger(workspace, task)
    assert len(crashed.operations) == 1
    assert crashed.operations[0].state is OperationState.ATTEMPTING

    # -- the surfaces refuse to replay it, and the operator answers ------------ #
    # The recovery pass runs at the front of every stage run, so the resume below
    # would be refused until the doubt is answered. This is the whole path a
    # person on the keyboard takes: crash, read the refusal, reconcile, continue.
    refused = run_cli("--workspace", str(workspace), "task", "run", "--source", source_id, "--json")
    assert refused.returncode != 0, refused.stdout
    assert refused.json()["reason"] == "operation_uncertain"

    resolved = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "reconcile",
        str(crashed.operations[0].operation_id),
        "--expected-sha256",
        _content_hash(workspace, source_id),
        "--json",
    )
    assert resolved.returncode == 0, resolved.stderr
    assert resolved.json()["resolution"] == "confirmed"

    # -- the operator continues the task --------------------------------------- #
    resumed = run_cli(
        "--workspace", str(workspace), "task", "resume", "--source", source_id, "--json"
    )
    assert resumed.returncode == 0, resumed.stderr

    # -- it is the same task, in a second attempt ---------------------------- #
    reported = run_cli("--workspace", str(workspace), "task", "status", "--json")
    assert reported.returncode == 0, reported.stderr
    state = reported.json()
    assert state["task"]["task_id"] == task, (
        "a resume is a new run against the same task; a new task would be a "
        "different task, and the work before the crash would be lost"
    )
    assert [run["attempt"] for run in state["runs"]] == [1, 2], (
        "the continuation must be a second attempt against the first, and the "
        "attempt number is what says so"
    )
    assert sorted(stage["status"] for stage in state["stages"]) == ["completed", "entered"], (
        "the stage the crash left unfinished must still be there, and the "
        "continuation must have run a second one"
    )

    # -- and the crashed attempt is still there ------------------------------ #
    ledger = read_ledger(workspace, task)
    assert len(ledger.operations) == 2, (
        "the continuation must not erase the operation the crash abandoned: "
        "a record a crash removed is a record nobody can reason about"
    )
    assert {operation.state for operation in ledger.operations} == {OperationState.CONFIRMED}, (
        "the abandoned operation is confirmed **because a probe said so**, and the "
        "continuation's own operation is confirmed because it ran. **This is the "
        "limit that remains**: a probe can say an effect landed, and the stage's "
        "bookkeeping — confirmation, completed stage, receipts, which "
        "``records.complete_operation`` writes in one transaction — was what the "
        "crash interrupted, so the log holds two operations for one piece of work. "
        "The effect happened once, and the second operation is a record of its "
        "completion rather than a second write."
    )
    assert ledger.count(EventType.STAGE_COMPLETED) == 1, (
        "exactly one stage completed: the one the continuation ran"
    )

    # -- and the report was regenerated from the material --------------------- #
    stage = resumed.json()["stage"]
    assert stage["status"] == "completed"
    assert stage["output_hashes"] == [_content_hash(workspace, source_id)]


@pytest.mark.e2e
def test_a_crash_before_the_attempt_is_durable_does_not_repeat_the_operation(
    workspace: Path, task: str, crash: Crash
) -> None:
    """The authorised operation is adopted, so one piece of work is planned once.

    The crash is placed in the window where the intent committed and the
    attempt did not. Nothing was attempted, so the operation is still
    ``AUTHORIZED`` — and the application layer's own rule is that *"a run
    which follows a crash reuses the operation that was authorised but never
    attempted"*. **The rule is the property, so the witness counts the
    operations rather than reading the rule.**

    What is asserted: after the crash and the run that follows it, the store
    holds **one** operation for the work, **one** attempt, **one**
    confirmation and **one** completed stage — and the stage's output is the
    material's own content hash, so the report was regenerated from the state
    the crash left behind rather than invented.
    """
    source_id = _bound_source(workspace, task)

    crash.place(
        "--workspace",
        str(workspace),
        "task",
        "run",
        "--source",
        source_id,
        window=BEFORE_ATTEMPT,
    )

    ledger = read_ledger(workspace, task)
    assert len(ledger.operations) == 1
    assert ledger.operations[0].state is OperationState.AUTHORIZED, (
        "the attempt must not be durable: the process died before it, and an "
        "operation that reads as attempting is one the next run may not adopt"
    )
    assert ledger.count(EventType.OPERATION_ATTEMPTED) == 0

    # -- the operator runs the stage again ---------------------------------- #
    again = run_cli("--workspace", str(workspace), "task", "run", "--source", source_id, "--json")
    assert again.returncode == 0, again.stderr

    # -- one piece of work, planned once ------------------------------------ #
    ledger = read_ledger(workspace, task)
    assert len(ledger.operations) == 1, (
        "the run that followed the crash planned a second operation for the "
        "same work, so the audit log says the work happened twice"
    )
    assert ledger.operations[0].state is OperationState.CONFIRMED
    assert ledger.count(EventType.OPERATION_INTENT) == 1
    assert ledger.count(EventType.OPERATION_ATTEMPTED) == 1
    assert ledger.count(EventType.OPERATION_CONFIRMED) == 1
    assert ledger.count(EventType.STAGE_COMPLETED) == 1

    # -- and the report was regenerated from the recovered state ------------- #
    stage = again.json()["stage"]
    assert stage["status"] == "completed"
    assert stage["output_hashes"] == [_content_hash(workspace, source_id)], (
        "the stage's output must be the material's own hash: the run "
        "regenerated the report from the state on disk"
    )


@pytest.mark.e2e
def test_the_report_is_refused_with_a_reason_when_the_policy_asks_after_a_crash(
    workspace: Path, task: str, crash: Crash
) -> None:
    """The other half of §2.3's clause: refused, with a reason, and nothing planned.

    A report is not always regenerated: sometimes the operator's policy asks
    about the capability, and then the run is **refused with a reason**. The
    refusal is a real answer — the state is not silently advanced and the
    work is not silently repeated.

    **The refusal plans nothing.** The consent is settled before the records
    are written, so a refused run leaves the store exactly as the crash left
    it: the one authorised operation, not attempted. That is what makes the
    refusal a safe answer rather than a slower way of repeating the work.

    And with the policy restored, the run continues on **the same operation**,
    so the refusal cost an attempt and not a record.
    """
    source_id = _bound_source(workspace, task)

    crash.place(
        "--workspace",
        str(workspace),
        "task",
        "run",
        "--source",
        source_id,
        window=BEFORE_ATTEMPT,
    )

    _set_the_inventory_rule(workspace, "ask")

    refused = run_cli("--workspace", str(workspace), "task", "run", "--source", source_id, "--json")
    assert refused.returncode == EXIT_REFUSED, (
        f"a refused run must carry the refusal's exit code; got {refused.returncode}"
    )
    payload = json.loads(refused.stdout)
    assert payload["reason"] == "policy_asked"
    assert "source.inventory" in payload["message"], (
        "the refusal must name the capability that was asked about, or a reader cannot act on it"
    )

    # -- the refusal planned nothing ---------------------------------------- #
    ledger = read_ledger(workspace, task)
    assert len(ledger.operations) == 1, (
        "the refused run planned an operation, so the refusal advanced the work it declined to do"
    )
    assert ledger.operations[0].state is OperationState.AUTHORIZED
    assert ledger.count(EventType.OPERATION_ATTEMPTED) == 0
    assert ledger.count(EventType.OPERATION_CONFIRMED) == 0

    # -- and with the policy restored, the run continues on the same one ----- #
    _set_the_inventory_rule(workspace, "allow")
    again = run_cli("--workspace", str(workspace), "task", "run", "--source", source_id, "--json")
    assert again.returncode == 0, again.stderr

    ledger = read_ledger(workspace, task)
    assert len(ledger.operations) == 1, (
        "the run after the refusal planned a second operation, so the refusal "
        "and the run together planned the work twice"
    )
    assert ledger.operations[0].state is OperationState.CONFIRMED
    assert ledger.count(EventType.OPERATION_ATTEMPTED) == 1
    assert ledger.count(EventType.OPERATION_CONFIRMED) == 1


@pytest.mark.e2e
def test_a_crash_during_the_ingestion_does_not_duplicate_the_material(
    workspace: Path, crash: Crash
) -> None:
    """The material a crashed ingestion had written is written once.

    The ingestion writes **one transaction per file**, so a crash in the
    middle of it leaves a ledger holding some of the material and not the
    rest. The continuation is another ingestion, and the question is whether
    it writes the material that is already there a second time.

    **The answer is no, and it is the product's own answer that is watched.**
    The ingestion reports how many rows *this run* wrote, per file; the file
    the crashed run had written reports zero, because it was already there.
    And the store agrees: the extracted rows for that material did not grow,
    and the ledger holds one row per file and not two.

    The material is added to the workspace *after* the task was made, so the
    crash lands on material the ledger has never held.
    """
    task_id = _make_a_task(workspace, with_material=False)

    materials = workspace / "materials"
    for name in ("one.md", "two.md", "three.md"):
        (materials / name).write_text(f"# {name}\n\nThe content of {name}.\n", encoding="utf-8")

    crash.place("--workspace", str(workspace), "sources", "ingest", window=DURING_INGEST)

    # -- the crash left part of the material on disk ------------------------ #
    sources = list_source_rows(workspace)
    assert len(sources) == 1, (
        "the crash must leave the ledger holding the material it had written "
        f"and not the rest; it holds {len(sources)}"
    )
    written = sources[0]
    rows_before = count_text_rows(workspace, written.content_sha256)

    # -- the ingestion again ------------------------------------------------ #
    report = run_cli("--workspace", str(workspace), "sources", "ingest", "--json")
    assert report.returncode == 0, report.stderr
    files = report.json()["files"]
    assert len(files) == 3, "every material the workspace holds must be reported"

    by_path = {entry["source"]["relative_path"]: entry for entry in files}
    already = by_path[written.relative_path]
    assert already["rows_written"] == 0, (
        "the ingestion wrote rows for material it had already written, so the "
        "side effect happened twice"
    )
    for path, entry in by_path.items():
        if path == written.relative_path:
            continue
        assert entry["rows_written"] > 0, (
            f"the ingestion wrote nothing for {path}, so the crash left the "
            "material unwritten and the continuation did not finish it"
        )

    # -- and the store agrees ----------------------------------------------- #
    assert count_text_rows(workspace, written.content_sha256) == rows_before, (
        "the store holds a second copy of the material the crashed ingestion had already written"
    )
    sources = list_source_rows(workspace)
    assert len(sources) == 3, (
        f"the ledger holds {len(sources)} sources for three material files, "
        "so the ingestion wrote one of them twice"
    )
    assert len({source.source_id for source in sources}) == 3, (
        "two of the ledger's sources share an id, so the ingestion wrote the "
        "same material under two rows"
    )
    assert len({source.relative_path for source in sources}) == 3, (
        "two of the ledger's sources share a path, so the ingestion wrote the "
        "same material under two rows"
    )

    # -- and the task ends up holding all of it ------------------------------ #
    with _session(workspace) as session:
        bound = load_task(session, TaskId(UUID(task_id))).bound_source_ids
    assert len(bound) == 3, (
        f"the task holds {len(bound)} sources after the continuation, so the "
        "task does not rest on the material the workspace holds"
    )


def _content_hash(workspace: Path, source_id: str) -> str:
    """The content hash the ledger holds for one source."""
    with _session(workspace) as session:
        source = load_source(session, source_id)
        assert source is not None, f"the ledger holds no source with the id {source_id}"
        return source.content_sha256


@pytest.mark.e2e
def test_the_service_comes_back_to_the_same_state_after_its_process_is_killed(
    workspace: Path, task: str
) -> None:
    """The service is killed and restarted, and serves the same state.

    The service is the second surface, and it holds the task's state in the
    store rather than in its memory — so a service that is killed mid-life
    loses nothing, and the one that starts afterwards reads the same task.

    **The kill is a real one.** ``taskkill /F`` on Windows and ``SIGKILL`` on
    POSIX terminate the process without unwinding it: no ``finally``, no
    atexit, no buffer flush. A service that was asked to stop politely would
    prove nothing about a service that was killed.
    """
    running = start_service(workspace)
    try:
        status, body = running.get("/task")
        assert status == 200
        served = json.loads(body)
        assert served["task"]["task_id"] == task

        hard_kill(running.process)
        running.process.wait(timeout=60)
    finally:
        running.stop()
    assert running.process.returncode != 0, (
        f"a hard-killed process cannot exit 0; got {running.process.returncode}"
    )

    # -- a fresh service, on the same workspace ----------------------------- #
    restarted = start_service(workspace)
    try:
        status, body = restarted.get("/task")
    finally:
        restarted.stop()
    assert status == 200
    assert json.loads(body) == served, (
        "the restarted service serves a different task than the one it served "
        "before it was killed, so the state did not survive the crash"
    )

    # -- and the CLI agrees with it ----------------------------------------- #
    reported = run_cli("--workspace", str(workspace), "task", "status", "--json")
    assert reported.returncode == 0, reported.stderr
    assert reported.json() == served


@pytest.mark.e2e
def test_the_surfaces_enter_uncertain_and_refuse_an_abandoned_operation(
    workspace: Path, task: str, crash: Crash
) -> None:
    """What a surface does with an operation a crash abandoned.

    **This is the successor to the finding G5 handed over.** The gate's own
    end-to-end test found that nothing under ``src/labcairn/application/`` ran
    the recovery pass, so an operation left ``ATTEMPTING`` sat there forever and
    the next ``task run`` planned a **second** operation for the same work — and
    the file asserted that behaviour as its evidence. The pass is wired now, so
    this asserts what the surfaces do instead.

    **What the surface may say, and what it may not.** It may record that the
    outcome is unknown: ``UNCERTAIN`` is the state recovery *enters*, and the
    stage is blocked with the reason the recovery layer states. It may **not**
    resolve the doubt by itself, because the value a probe needs — the hash the
    operation predicted — is not in the store; it lived inside ``args_digest``,
    which is a hash of a hash. So the run is refused rather than replayed, and
    the refusal names the operation, the command that answers it, and the fact
    that the number has to come from the operator.
    """
    source_id = _bound_source(workspace, task)

    crash.place(
        "--workspace",
        str(workspace),
        "task",
        "run",
        "--source",
        source_id,
        window=AFTER_THE_EFFECT,
    )

    ledger = read_ledger(workspace, task)
    assert len(ledger.operations) == 1
    assert ledger.operations[0].state is OperationState.ATTEMPTING

    again = run_cli("--workspace", str(workspace), "task", "run", "--source", source_id, "--json")

    # -- the run is refused, with a reason a script can branch on ------------ #
    assert again.returncode != 0, (
        "a surface that replanned over an unknown outcome would exit zero here; "
        "the refusal is the property, so the exit code is the witness"
    )
    refused = again.json()
    assert refused["reason"] == "operation_uncertain", refused

    ledger = read_ledger(workspace, task)

    # -- one operation, and it now says what it does not know ------------------ #
    assert len(ledger.operations) == 1, (
        "the abandoned operation must not gain a twin: one piece of work is "
        "planned once, and a second operation for it is the blocker's shape"
    )
    assert ledger.operations[0].state is OperationState.UNCERTAIN
    assert ledger.count(EventType.OPERATION_UNCERTAIN) == 1
    assert ledger.count(EventType.OPERATION_RECONCILED) == 0, (
        "nothing probed it: a surface that resolved the doubt would have had to "
        "invent the hash the operation predicted"
    )
    assert ledger.count(EventType.OPERATION_ATTEMPTED) == 1, (
        "no second attempt was booked against the work"
    )
    blocked = run_cli("--workspace", str(workspace), "task", "status", "--json")
    assert blocked.returncode == 0, blocked.stderr
    waiting = [stage for stage in blocked.json()["stages"] if stage["status"] == "blocked"]
    assert waiting, "the stage the abandoned operation belonged to is blocked"
    assert "UNCERTAIN" in waiting[0]["blocked_reason"], (
        "and it says so: a reader must be able to tell a human-approval wait from "
        "a crash whose outcome is unknown"
    )

    # -- and the answer the operator holds does resolve it --------------------- #
    predicted = _content_hash(workspace, source_id)
    operation_id = str(ledger.operations[0].operation_id)
    resolved = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "reconcile",
        operation_id,
        "--expected-sha256",
        predicted,
        "--json",
    )
    assert resolved.returncode == 0, resolved.stderr
    answer = resolved.json()
    assert answer["operation_id"] == operation_id
    assert answer["resolution"] == "confirmed", (
        f"probed {answer['resource_key']!r}: expected {answer['expected_sha256'][:12]}..., "
        f"observed {answer['observed_sha256']}"
    )
    assert answer["observed_sha256"] == predicted
    assert answer["resulting_state"] == "confirmed"
    ledger = read_ledger(workspace, task)
    assert ledger.count(EventType.OPERATION_RECONCILED) == 1


@pytest.mark.e2e
def test_a_run_refused_for_an_uncertain_operation_does_not_spend_its_approval(
    workspace: Path, task: str, crash: Crash
) -> None:
    """The recovery pass runs before the consent is spent, so a refusal burns nothing.

    **Why it matters**: the run path asks a human before it acts, and a refusal
    that spent the answer would force the question to be asked again for a fact
    that changed nothing. The layer's own order is policy verdict → recovery pass
    → approval consumption, and this counts the events to prove the middle step
    does not consume the consent.
    """
    source_id = _bound_source(workspace, task)
    crash.place(
        "--workspace",
        str(workspace),
        "task",
        "run",
        "--source",
        source_id,
        window=AFTER_THE_EFFECT,
    )

    again = run_cli("--workspace", str(workspace), "task", "run", "--source", source_id, "--json")
    assert again.returncode != 0
    ledger = read_ledger(workspace, task)
    assert ledger.count(EventType.OPERATION_UNCERTAIN) == 1, (
        "the recovery half happened: the abandoned operation is no longer called in flight"
    )
    assert ledger.count(EventType.APPROVAL_CONSUMED) == 0, "and nothing was consumed to do it"
