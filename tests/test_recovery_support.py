"""Shared builders for the LC-P1-06 recovery tests.

Not a test module — it defines no ``test_*`` functions. The store fixtures and
the contract builders come from :mod:`test_store_support`, which LC-P1-05 owns
and which this ticket does not touch; what is here is only the machinery
specific to crash recovery.

Three pieces carry the weight.

:class:`WriteCounter` exists because every acceptance test claiming "the effect
was not performed twice" has to mean it by something other than reading the file
back. A file that happens to hold the right bytes proves nothing about how many
times it was produced — one write and two writes of the same payload are
indistinguishable on disk. So the effect each test installs is a closure around
a counter, and the counter is what the assertions read.

:class:`RecordingSink` exists for crash case 3, whose entire claim is about what
a client was and was not told. Distinguishing "not notified" from "notified and
the notification lost" needs something that records delivery; a sink that simply
discards makes the two identical, and the test then passes for the wrong reason.

:func:`workspace_entries` exists because a counter that counts only
``effect.apply()`` cannot see a writer that bypassed the effect — and a probe
that wrote the output file itself is precisely such a writer. "The effect was
not performed twice" is the claim that writer would defeat, so the workspace is
measured as well as the counter.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

# `env` and `frozen_clock` are imported for their fixture role, not their value:
# pytest only sees a fixture that is present in the test module's namespace,
# which is why the shared environment lives in an importable module rather than
# a conftest this ticket does not own.
from test_store_support import (
    StoreEnv,
    env,
    frozen_clock,
    make_operation,
    make_run,
    make_stage,
    make_task,
)

from labcairn.core.ids import RunId, StageId, TaskId
from labcairn.db.repository import TaskStore
from labcairn.recovery import (
    ArmedFaults,
    CrashPoint,
    FaultInjector,
    FileSystemProbe,
    MaterialResolver,
    RecoveryCoordinator,
    ResumeCoordinator,
    SideEffect,
    SideEffectExecutor,
    hash_bytes,
)
from labcairn.recovery.executor import NULL_SINK
from labcairn.runtime.event import Event, EventTransition, EventType
from labcairn.runtime.lifecycle import RunStatus, StageStatus
import pytest

pytestmark = pytest.mark.integration

#: The one timestamp every scenario runs at. Matches the repository's
#: ``FROZEN_NOW`` rather than reading a wall clock — see the root ``conftest``.
SCENARIO_NOW: datetime = datetime(2026, 1, 1, tzinfo=UTC)

__all__ = [
    "SCENARIO_NOW",
    "RecordingSink",
    "Scenario",
    "WriteCounter",
    "arm",
    "build_scenario",
    "env",
    "frozen_clock",
    "make_operation",
    "make_run",
    "make_stage",
    "make_task",
    "plan_write",
    "workspace_digest",
    "workspace_entries",
]


def frozen() -> datetime:
    return SCENARIO_NOW


class WriteCounter:
    """A side effect whose every invocation is counted."""

    __slots__ = ("_root", "calls", "written")

    def __init__(self, root: Path) -> None:
        self._root = root
        self.calls = 0
        #: ``(resource_key, hash)`` in call order, so a test can assert not just
        #: *how many* writes but *what* each one left.
        self.written: list[tuple[str, str]] = []

    def plan(self, resource_key: str, payload: bytes) -> SideEffect:
        """A :class:`SideEffect` writing *payload* to *resource_key*.

        The prediction is computed from *payload* before anything runs, which is
        what makes the probe's later comparison meaningful rather than circular.
        """
        target = self._root.joinpath(*resource_key.split("/"))
        expected = hash_bytes(payload)

        def _apply() -> str:
            self.calls += 1
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            actual = hash_bytes(payload)
            self.written.append((resource_key, actual))
            return actual

        return SideEffect(resource_key=resource_key, expected_sha256=expected, apply=_apply)


@dataclass
class RecordingSink:
    """Records what a client was told, and can be made to swallow it."""

    delivered: list[Event] = field(default_factory=list)
    #: When true the notification silently does not land — which is exactly what
    #: a crash between COMMIT and the client is.
    dropping: bool = False

    def deliver(self, events: Sequence[Event]) -> None:
        if self.dropping:
            return
        self.delivered.extend(events)

    @property
    def types(self) -> list[str]:
        return [event.type.value for event in self.delivered]

    @property
    def last_seq(self) -> int:
        return self.delivered[-1].seq if self.delivered else 0


@dataclass(frozen=True, slots=True)
class Scenario:
    """A task, a run, a stage, and the three coordinators over one session."""

    env: StoreEnv
    task_id: TaskId
    run_id: RunId
    stage_id: StageId
    root: Path

    # -- accessors ----------------------------------------------------------- #

    @property
    def session(self):  # type: ignore[no-untyped-def]
        return self.env.session

    def store(self) -> TaskStore:
        return self.env.store(clock=frozen)

    def executor(
        self,
        *,
        faults: FaultInjector | None = None,
        sink: object = NULL_SINK,
    ) -> SideEffectExecutor:
        return SideEffectExecutor(
            self.store(),
            self.session,
            workspace_root=self.root,
            clock=frozen,
            faults=faults,
            sink=sink,  # type: ignore[arg-type]
        )

    def recovery(self) -> RecoveryCoordinator:
        return RecoveryCoordinator(
            self.store(),
            self.session,
            workspace_root=self.root,
            probe=FileSystemProbe(self.root),
            clock=frozen,
        )

    def resume(self) -> ResumeCoordinator:
        return ResumeCoordinator(self.store(), self.session, workspace_root=self.root, clock=frozen)

    def materials(self) -> MaterialResolver:
        return MaterialResolver(self.root)

    def counter(self) -> WriteCounter:
        return WriteCounter(self.root)

    # -- the restart ---------------------------------------------------------- #

    def restart(self) -> Scenario:
        """A genuinely new process view: a new session on the same database.

        Closes the old session and disposes the engine first. Reusing the live
        session would read SQLAlchemy's identity map rather than the database,
        which would quietly hide exactly the bug these tests exist to find: a
        write that rolled back is still visible in the session cache and reads
        as committed.
        """
        self.env.session.close()
        self.env.engine.dispose()
        return self.rebind()

    def rebind(self) -> Scenario:
        """Re-open onto the same identities without tearing anything down."""
        return Scenario(
            env=self.env,
            task_id=self.task_id,
            run_id=self.run_id,
            stage_id=self.stage_id,
            root=self.root,
        )


def build_scenario(env: StoreEnv, tmp_path: Path) -> Scenario:
    """Create the task/run/stage every recovery test drives.

    Identities are created exactly once, here. :meth:`Scenario.restart`
    deliberately does **not** call this: a resumed run keeps its Task id, and a
    test that got a fresh Task after a crash would be proving nothing about
    resuming.
    """
    root = tmp_path / "workspace"
    (root / "outputs").mkdir(parents=True, exist_ok=True)

    store = env.store(clock=frozen)
    task = make_task(now=SCENARIO_NOW)
    store.create_task(task)

    run = make_run(task.task_id, now=SCENARIO_NOW)
    with store.unit(task.task_id) as work:
        work.put_run(run)
        work.emit(
            EventType.RUN_STARTED,
            run_id=run.run_id,
            transition=EventTransition(
                from_state=RunStatus.PENDING.value, to_state=RunStatus.RUNNING.value
            ),
        )

    stage = make_stage(task.task_id, run.run_id)
    with store.unit(task.task_id) as work:
        work.put_stage(stage)
        work.emit(
            EventType.STAGE_ENTERED,
            run_id=run.run_id,
            stage_id=stage.stage_id,
            transition=EventTransition(
                from_state=StageStatus.PENDING.value, to_state=StageStatus.ENTERED.value
            ),
        )

    return Scenario(
        env=env,
        task_id=task.task_id,
        run_id=run.run_id,
        stage_id=stage.stage_id,
        root=root,
    )


def arm(point: CrashPoint) -> ArmedFaults:
    """An injector armed at *point*. Named so a test reads as prose."""
    return ArmedFaults(point)


def plan_write(scenario: Scenario, text: str) -> tuple[WriteCounter, SideEffect, bytes]:
    """The usual trio: a counter, the effect it counts, and the bytes it writes.

    One helper because every crash test needs the same three things wired the
    same way, and a test that built its own effect would be free to forget the
    counter — which is the one part the assertion actually rests on.
    """
    counter = scenario.counter()
    body = text.encode("utf-8")
    return counter, counter.plan("outputs/report.md", body), body


def workspace_entries(root: Path) -> list[str]:
    """One line per entry under *root*: what it is, where it is, what it holds.

    Built for the claim that a *read-only* question of the filesystem leaves
    the filesystem alone. :class:`WriteCounter` cannot witness that claim: it
    counts calls to ``effect.apply()``, and a probe that wrote the file itself
    would never go through it — an effect that happened twice and was recorded
    once is invisible to a counter.

    So the workspace itself is measured. A list rather than a hash, because a
    comparison that fails should say *what* changed instead of that two hex
    strings differ.

    Every entry is described by its kind, its path relative to *root*, and its
    contents — the bytes of a file, the target of a link — plus the timestamp
    it carries. The timestamp is not decoration: a probe that rewrote a file
    with the same bytes would leave the content identical and the mtime
    different, and a rewrite is still a write.
    """
    entries: list[str] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            entries.append(f"link {relative} -> {path.readlink()}")
            continue
        if path.is_dir():
            entries.append(f"dir {relative} mtime={path.stat().st_mtime_ns}")
            continue
        try:
            payload = path.read_bytes()
        except OSError as exc:
            entries.append(f"unreadable {relative} {type(exc).__name__}")
            continue
        entries.append(
            f"file {relative} bytes={len(payload)} sha256={hash_bytes(payload)} "
            f"mtime={path.stat().st_mtime_ns}"
        )
    return entries


def workspace_digest(root: Path) -> str:
    """A digest of the whole workspace: equal digests mean an identical workspace.

    The single-value form of :func:`workspace_entries`, for the assertion that
    wants to say "nothing moved" and nothing more.
    """
    return hash_bytes("\n".join(workspace_entries(root)).encode("utf-8"))
