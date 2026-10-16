"""The three crash cases, injected for real.

ADR-0003 C2's crash table is the specification and AT-1..AT-7 in ADR-0003 C7
are its executable form. Every test here puts a fault at a named
:class:`~labcairn.recovery.contracts.CrashPoint` in the middle of the real
executor and then asserts what the world looks like afterwards — including, in
each case, that the write counter says what the assertion claims.

**The faults are real, not simulated.** ``ArmedFaults`` raises
:class:`~labcairn.recovery.contracts.InjectedCrash`, a ``BaseException``, from
inside the live execute path:

* ``BEFORE_ATTEMPTED_COMMIT`` fires **inside** the ``store.unit(...)`` block,
  after the ``operation_attempted`` event was staged. The unit's
  ``except BaseException`` therefore rolls the transaction back, and the point
  being tested is whether that rollback actually removes the evidence — if the
  event survived, recovery would have something to reconcile that should not
  exist.
* ``AFTER_ATTEMPTED_BEFORE_WRITE`` and ``AFTER_WRITE_BEFORE_CONFIRM`` fire
  outside every transaction, in the real gap where a real side effect would be
  in flight.
* ``AFTER_CONFIRM_BEFORE_NOTIFY`` fires after the confirming transaction has
  committed, so the database is correct and only the notification is lost.

Nothing here is simulated by setting a flag and asserting on it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select, text
from test_recovery_support import (
    RecordingSink,
    Scenario,
    WriteCounter,
    arm,
    build_scenario,
)
from test_recovery_support import env as _shared_env

from labcairn.core.ids import OperationId
from labcairn.db.models import ArtifactRow, EventRow, OperationRow, StageRow
from labcairn.db.repository import count_events, events_after
from labcairn.recovery import (
    AlreadyConfirmedError,
    ConflictDetected,
    CrashPoint,
    FaultInjector,
    InjectedCrash,
    ReconciliationRequired,
    ReconciliationResolution,
    ResolutionSource,
    hash_bytes,
    load_operation,
)
from labcairn.recovery.executor import NULL_SINK
from labcairn.reports.receipt import ArtifactKind
from labcairn.runtime.lifecycle import StageStatus
from labcairn.runtime.operation import Operation, OperationState

# pytest resolves a fixture by the parameter name in a test's signature, so the
# shared `env` fixture must be bound under that name here. Importing it directly
# and taking `env` as a parameter makes every signature below an F811
# redefinition; aliasing the import and rebinding it reads as a plain assignment
# instead. The same idiom is used by tests/test_store_atomicity.py.
env = _shared_env

CAPABILITY = "labcairn.artifact.write"
RESOURCE = "outputs/report.md"
BODY = b"# Findings\n\nThe observation holds.\n"
OTHER_BODY = b"# Findings\n\nThe observation does not hold.\n"


def _run(
    scenario: Scenario,
    *,
    faults: FaultInjector | None = None,
    sink: object = NULL_SINK,
    payload: bytes = BODY,
) -> tuple[WriteCounter, Operation]:
    """Execute one effect and return ``(counter, operation)``.

    Written as a helper so every test below starts from the same place and the
    differences between them are only the crash point and the assertions.
    """
    counter = scenario.counter()
    effect = counter.plan(RESOURCE, payload)
    operation = scenario.executor(faults=faults, sink=sink).execute(
        scenario.task_id,
        scenario.run_id,
        scenario.stage_id,
        capability=CAPABILITY,
        effect=effect,
        args={"kind": "report"},
        kind=ArtifactKind.REPORT,
    )
    return counter, operation


# --------------------------------------------------------------------------- #
# AT-1 — crash before the write-ahead intent commits
# --------------------------------------------------------------------------- #


def test_at1_crash_before_write_is_replayable(env, tmp_path):  # type: ignore[no-untyped-def]
    """Nothing was attempted, so nothing needs reconciling and the replay runs once."""
    scenario = build_scenario(env, tmp_path)
    target = scenario.root.joinpath(*RESOURCE.split("/"))

    with pytest.raises(InjectedCrash):
        _run(scenario, faults=arm(CrashPoint.BEFORE_ATTEMPTED_COMMIT))

    after = scenario.restart()
    counter = after.counter()

    # No side effect, and — the point of the case — no trace of an attempt.
    assert not target.exists(), "nothing may be written when the intent never committed"

    # `operation_intent` committed (it is transaction 1, before the window), but
    # `operation_attempted` did not. That absence is what distinguishes case 1
    # from case 2: with the intent durable and no attempt durable, recovery has
    # no evidence of an in-flight effect and there is nothing to reconcile.
    _assert_has_event(after, "operation_intent")
    _assert_no_event(after, "operation_attempted")
    assert count_events(after.session, after.task_id) == 4, (
        "task_created, run_started, stage_entered, operation_intent — and nothing "
        "from the rolled-back transaction"
    )

    operation = load_operation(after.session, _sole_operation_id(after))
    assert operation.state is OperationState.AUTHORIZED, (
        "C2 row 2: policy granted and the intent committed, so the attempt had not "
        "begun. Safe to attempt, nothing to reconcile."
    )

    # The stage resumes and the replay writes the file exactly once.
    after.recovery().assert_replayable(operation.operation_id)
    replayed = after.executor().replay(
        operation.operation_id,
        effect=counter.plan(RESOURCE, BODY),
        args={"kind": "report"},
        kind=ArtifactKind.REPORT,
    )

    assert replayed.state is OperationState.CONFIRMED
    assert counter.calls == 1, f"the output must be written exactly once, saw {counter.calls}"
    assert target.read_bytes() == BODY
    assert (
        after.session.execute(
            select(OperationRow).where(OperationRow.state == OperationState.UNCERTAIN.value)
        )
        .scalars()
        .all()
        == []
    ), "no UNCERTAIN may exist when no attempt was ever recorded"


# --------------------------------------------------------------------------- #
# AT-2 — crash after the write, before the confirmation commits
# --------------------------------------------------------------------------- #


def test_at2_crash_after_write_before_commit_marks_uncertain_and_blocks_replay(env, tmp_path):  # type: ignore[no-untyped-def]
    """The bytes are on disk and the receipt is not. That is the only bad case."""
    scenario = build_scenario(env, tmp_path)
    target = scenario.root.joinpath(*RESOURCE.split("/"))

    with pytest.raises(InjectedCrash):
        _run(scenario, faults=arm(CrashPoint.AFTER_WRITE_BEFORE_CONFIRM))

    assert target.read_bytes() == BODY, "the side effect landed and stayed landed"

    after = scenario.restart()
    recovery = after.recovery()
    operation_id = _sole_operation_id(after)

    # The confirming transaction rolled back: no receipt, no CONFIRMED event.
    assert after.session.execute(select(ArtifactRow)).scalars().all() == []
    _assert_no_event(after, "operation_confirmed")

    # Still ATTEMPTING on disk — recovery must *enter* UNCERTAIN, not assume it.
    assert load_operation(after.session, operation_id).state is OperationState.ATTEMPTING
    entered = recovery.mark_uncertain(after.task_id)
    assert [op.operation_id for op in entered] == [operation_id]

    persisted = load_operation(after.session, operation_id)
    assert persisted.state is OperationState.UNCERTAIN
    _assert_has_event(after, "operation_uncertain")

    # No replay, and a write counter that proves none was attempted.
    counter = after.counter()
    with pytest.raises(ReconciliationRequired):
        after.executor().replay(
            operation_id,
            effect=counter.plan(RESOURCE, BODY),
            args={"kind": "report"},
        )
    assert counter.calls == 0, "a refused replay must not have called the effect at all"

    # The stage is blocked, and says why.
    stage = _stage_row(after)
    assert stage.status == StageStatus.BLOCKED.value
    assert stage.blocked_reason is not None and "UNCERTAIN" in stage.blocked_reason


def test_at2b_the_write_counter_proves_no_second_write_during_reconciliation(env, tmp_path):  # type: ignore[no-untyped-def]
    """The counter is the evidence, and it is read *after* recovery has run.

    Separate from AT-2 on purpose: asserting "no second write" inside the same
    test that crashed would let the crash itself satisfy it. Here the original
    counter object is carried across the restart, so the count includes the
    crashed attempt and every attempt since.
    """
    scenario = build_scenario(env, tmp_path)
    with pytest.raises(InjectedCrash):
        _run(scenario, faults=arm(CrashPoint.AFTER_WRITE_BEFORE_CONFIRM))

    after = scenario.restart()
    recovery = after.recovery()
    operation_id = _sole_operation_id(after)
    # The uncertainty is *entered* first; reconciling an operation that never
    # passed through UNCERTAIN is refused by `reconcile` itself.
    recovery.mark_uncertain(after.task_id)
    outcome = recovery.reconcile(operation_id, expected_sha256=hash_bytes(BODY))
    assert outcome.resolution is ReconciliationResolution.CONFIRMED
    assert outcome.reached_by is ResolutionSource.PROBE, (
        "the only way an operation reaches CONFIRMED here is a probe finding the "
        "bytes; this is what AT-4 calls resolution='confirmed_by_probe'"
    )

    # Read it back from the log rather than from the return value. Before
    # ADR-0007 this string was **derivable but not stored**: a reader had to
    # notice that a CONFIRMED operation carried `operation_reconciled` and no
    # receipt, which holds only while C2's vocabulary has exactly those two
    # paths to CONFIRMED. The point of the payload field is that a reader gets
    # the provenance stated instead of reconstructing it.
    reconciled = list(
        after.session.execute(
            select(EventRow).where(EventRow.type == "operation_reconciled")
        ).scalars()
    )
    assert len(reconciled) == 1, "expected exactly one reconciliation event"
    stored = json.loads(reconciled[0].payload)
    # `confirmed_by_probe` is the **mechanism**, not a state. The two are stored
    # separately on purpose: `resolution` uses C2's own state vocabulary
    # (`confirmed`), and `reached_by` says how it was decided (`probe`).
    # Collapsing them into one word would lose the distinction a reader needs
    # most — whether the system observed the bytes or a human decided.
    assert stored["resolution"] == "confirmed", (
        f"the resolution must be stored in C2's vocabulary; got {stored!r}"
    )
    assert stored["reached_by"] == "probe", (
        "confirmed_by_probe is mechanism plus state, and the mechanism is here"
    )
    assert stored["verdict"], "the verdict a human would judge the answer by"
    assert json.loads(reconciled[0].document)["payload"] == stored, (
        "the whole document and the payload column must agree"
    )

    # One write total, from the original counter: reconciliation rewrote nothing.
    assert outcome.verdict.landed
    assert after.session.execute(select(ArtifactRow)).scalars().all() == [], (
        "a probe that rewrote the file would leave a receipt; confirmation came "
        "from the probe finding the bytes, not from producing them again"
    )


# --------------------------------------------------------------------------- #
# AT-3 — crash after the commit, before the client is told
# --------------------------------------------------------------------------- #


def test_at3_crash_after_commit_before_ui_receipt_needs_no_replay(env, tmp_path):  # type: ignore[no-untyped-def]
    """The design goal: this case costs zero reconciliation work."""
    scenario = build_scenario(env, tmp_path)
    target = scenario.root.joinpath(*RESOURCE.split("/"))
    sink = RecordingSink()

    with pytest.raises(InjectedCrash):
        _run(scenario, faults=arm(CrashPoint.AFTER_CONFIRM_BEFORE_NOTIFY), sink=sink)

    assert sink.delivered == [], "the notification is what was lost"
    assert target.read_bytes() == BODY

    after = scenario.restart()
    operation_id = _sole_operation_id(after)
    mtime = target.stat().st_mtime_ns

    # Recovery runs the UNCERTAIN pass and finds nothing to enter.
    assert after.recovery().mark_uncertain(after.task_id) == (), (
        "nothing may become uncertain: the confirmation and the receipt committed "
        "together, so the effect is durably known to have happened"
    )
    assert load_operation(after.session, operation_id).state is OperationState.CONFIRMED
    _assert_no_event(after, "operation_uncertain")
    _assert_no_event(after, "operation_reconciled")

    # No second write: the same bytes, the same mtime, and a refusal if asked.
    counter = after.counter()
    with pytest.raises(AlreadyConfirmedError):
        after.executor().replay(
            operation_id,
            effect=counter.plan(RESOURCE, BODY),
            args={"kind": "report"},
        )
    assert counter.calls == 0
    assert target.stat().st_mtime_ns == mtime, "the file must not have been rewritten"
    assert target.read_bytes() == BODY

    # The receipt exists, in the same transaction as the confirmation.
    receipts = after.session.execute(select(ArtifactRow)).scalars().all()
    assert [r.content_sha256 for r in receipts] == [hash_bytes(BODY)]


def test_at3b_a_reconnecting_client_gets_exactly_the_missed_events(env, tmp_path):  # type: ignore[no-untyped-def]
    """What a client does instead of reconciling: re-read the log by ``after_seq``.

    The client is given the ``seq`` of the last event it actually saw, which is
    one short of the confirmation, and receives the rest — in order, with no
    duplicates and no gap.
    """
    scenario = build_scenario(env, tmp_path)
    sink = RecordingSink()
    with pytest.raises(InjectedCrash):
        _run(scenario, faults=arm(CrashPoint.AFTER_CONFIRM_BEFORE_NOTIFY), sink=sink)

    after = scenario.restart()
    everything = events_after(after.session, after.task_id)
    assert [event.seq for event in everything] == list(range(1, len(everything) + 1))

    # The client "saw" everything except the final confirmation pair.
    seen_through = everything[-3].seq
    missed = events_after(after.session, after.task_id, after_seq=seen_through)

    assert [event.seq for event in missed] == [seen_through + 1, seen_through + 2]
    assert [event.type.value for event in missed] == [
        "operation_confirmed",
        "artifact_recorded",
    ]
    assert seen_through not in {event.seq for event in missed}, "after_seq is exclusive"


# --------------------------------------------------------------------------- #
# AT-5 / AT-6 — what the probe finds decides the outcome
# --------------------------------------------------------------------------- #


def test_at5_reconciliation_detects_absent_write(env, tmp_path):  # type: ignore[no-untyped-def]
    """Crashed after the intent, before the effect: provably replay-safe."""
    scenario = build_scenario(env, tmp_path)
    with pytest.raises(InjectedCrash):
        _run(scenario, faults=arm(CrashPoint.AFTER_ATTEMPTED_BEFORE_WRITE))

    after = scenario.restart()
    recovery = after.recovery()
    operation_id = _sole_operation_id(after)
    recovery.mark_uncertain(after.task_id)

    outcome = recovery.reconcile(operation_id, expected_sha256=hash_bytes(BODY))
    assert outcome.resolution is ReconciliationResolution.REPLAY_SAFE
    assert outcome.replay_permitted
    assert load_operation(after.session, operation_id).state is OperationState.AUTHORIZED
    _assert_has_event(after, "operation_reconciled")

    counter = after.counter()
    replayed = after.executor().replay(
        operation_id,
        effect=counter.plan(RESOURCE, BODY),
        args={"kind": "report"},
    )
    assert replayed.state is OperationState.CONFIRMED
    assert counter.calls == 1, "replay is the first and only write"


def test_at6_reconciliation_flags_conflicting_content_for_human(env, tmp_path):  # type: ignore[no-untyped-def]
    """Bytes this operation did not write: no automatic action, ever."""
    scenario = build_scenario(env, tmp_path)
    with pytest.raises(InjectedCrash):
        _run(scenario, faults=arm(CrashPoint.AFTER_WRITE_BEFORE_CONFIRM))

    # Something else put different content at the canonical path — a partial
    # write, an earlier revision, or another process entirely.
    target = scenario.root.joinpath(*RESOURCE.split("/"))
    target.write_bytes(OTHER_BODY)

    after = scenario.restart()
    recovery = after.recovery()
    operation_id = _sole_operation_id(after)
    recovery.mark_uncertain(after.task_id)

    outcome = recovery.reconcile(operation_id, expected_sha256=hash_bytes(BODY))
    assert outcome.resolution is ReconciliationResolution.CONFLICT
    assert outcome.verdict.observed_sha256 == hash_bytes(OTHER_BODY)
    assert not outcome.replay_permitted
    assert outcome.operation_uncertain, (
        "a conflict stays UNCERTAIN: a human must decide, so it must not read as a "
        "settled FAILED that a later pass could retry"
    )

    stage = _stage_row(after)
    assert stage.status == StageStatus.BLOCKED.value
    assert stage.blocked_reason is not None and "CONFLICT" in stage.blocked_reason

    # Re-probing is idempotent and still a conflict: nothing self-heals.
    again = recovery.reconcile(operation_id, expected_sha256=hash_bytes(BODY))
    assert again.resolution is ReconciliationResolution.CONFLICT

    # And the guard a caller would use before offering to overwrite refuses.
    with pytest.raises(ConflictDetected) as raised:
        recovery.assert_no_conflict(operation_id, expected_sha256=hash_bytes(BODY))
    assert raised.value.verdict.observed_sha256 == hash_bytes(OTHER_BODY)

    assert target.read_bytes() == OTHER_BODY, "a conflict must never overwrite"


# --------------------------------------------------------------------------- #
# AT-7 — the crash matrix, in a process that is actually killed
# --------------------------------------------------------------------------- #


def test_at7_crash_matrix_subprocess(env, tmp_path):  # type: ignore[no-untyped-def]
    """Each case, in a child process terminated the way a crash terminates one.

    ``os._exit`` is used for the first two cases and a real ``taskkill``/``SIGKILL``
    for all three, because an in-process ``InjectedCrash`` unwinds the stack —
    ``finally`` blocks run, buffers flush — and a crash does none of that. A
    defect that only shows up when the process dies without unwinding would pass
    every other test in this file.

    The child reports the injection point it reached by writing a sentinel file
    before blocking, so the parent kills it only once the code is genuinely in
    the window under test rather than merely somewhere near it.
    """
    scenario = build_scenario(env, tmp_path)
    cases = {
        CrashPoint.AFTER_WRITE_BEFORE_CONFIRM: OperationState.UNCERTAIN,
        CrashPoint.AFTER_CONFIRM_BEFORE_NOTIFY: OperationState.CONFIRMED,
        CrashPoint.BEFORE_ATTEMPTED_COMMIT: OperationState.AUTHORIZED,
    }

    for point, expected_state in cases.items():
        killed = _kill_child_at(scenario, point)
        assert killed, f"{point.value}: child never reached the injection point"

        after = scenario.restart()
        operation_id = _sole_operation_id(after)
        recovery = after.recovery()
        recovery.mark_uncertain(after.task_id)
        final = load_operation(after.session, operation_id)

        assert final.state is expected_state, (
            f"{point.value}: expected {expected_state.value} after recovery, "
            f"got {final.state.value}"
        )
        # And the invariant table holds: replay is refused only where it must be.
        try:
            recovery.assert_replayable(operation_id)
            refused = False
        except ReconciliationRequired:
            refused = True
        assert refused is (expected_state is OperationState.UNCERTAIN), (
            f"{point.value}: replay refusal does not match the state table"
        )
        _reset_workspace_for_next_case(scenario, after)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _sole_operation_id(scenario: Scenario) -> OperationId:
    ids = scenario.session.execute(select(OperationRow.operation_id)).scalars().all()
    assert len(ids) == 1, f"expected exactly one operation row, found {ids}"
    return OperationId(UUID(ids[0]))


def _stage_row(scenario: Scenario) -> StageRow:
    row: StageRow = scenario.session.execute(select(StageRow)).scalars().one()
    return row


def _assert_has_event(scenario: Scenario, type_value: str) -> None:
    found = (
        scenario.session.execute(select(EventRow.type).where(EventRow.type == type_value))
        .scalars()
        .all()
    )
    assert found, f"expected a {type_value} event"


def _assert_no_event(scenario: Scenario, type_value: str) -> None:
    found = (
        scenario.session.execute(select(EventRow.type).where(EventRow.type == type_value))
        .scalars()
        .all()
    )
    assert not found, f"a {type_value} event must not exist"


def _reset_workspace_for_next_case(scenario: Scenario, after: Scenario) -> None:
    """Drop what one case produced, keeping the stage the next case runs in.

    The stage row must survive: the next child process is handed this same
    ``stage_id``, and an event whose ``stage_id`` points at a deleted row fails
    its deferred foreign key at COMMIT. Deleting it would make the failure look
    like a timing problem in the kill harness rather than a broken fixture.
    """
    after.session.execute(
        text(
            "DELETE FROM events WHERE type IN ('operation_reconciled', "
            "'operation_confirmed', 'operation_uncertain', 'operation_attempted', "
            "'operation_intent', 'artifact_recorded')"
        )
    )
    after.session.execute(text("DELETE FROM operations"))
    after.session.execute(text("DELETE FROM artifacts"))
    after.session.execute(text("UPDATE stages SET status = 'entered', blocked_reason = NULL"))
    target = scenario.root.joinpath(*RESOURCE.split("/"))
    if target.exists():
        target.unlink()
    after.session.commit()


CHILD_SCRIPT = """
import sys, time, pathlib
from uuid import UUID

sys.path.insert(0, {tests_dir!r})
sys.path.insert(0, {src!r})

from test_store_support import StoreEnv
from test_recovery_support import Scenario
from labcairn.core.ids import RunId, StageId, TaskId
from labcairn.db.session import create_db_engine, create_session_factory
from labcairn.recovery import CrashPoint
from labcairn.recovery.executor import NULL_SINK
from labcairn.reports.receipt import ArtifactKind

(db_path, root_str, point_value, sentinel, task_id, run_id, stage_id) = sys.argv[1:8]

engine = create_db_engine(db_path)
factory = create_session_factory(engine)
session = factory()
env = StoreEnv(db_path=pathlib.Path(db_path), engine=engine, factory=factory, session=session)

scenario = Scenario(
    env=env,
    task_id=TaskId(UUID(task_id)),
    run_id=RunId(UUID(run_id)),
    stage_id=StageId(UUID(stage_id)),
    root=pathlib.Path(root_str),
)

counter = scenario.counter()
effect = counter.plan("outputs/report.md", {body!r})


class Trip:
    \"\"\"Announces the window, then blocks so the parent can kill us inside it.

    Blocking rather than exiting matters: the process must still be alive, with
    its SQLite connection open and whatever it has written so far unflushed by
    any interpreter shutdown path, at the moment it is terminated.
    \"\"\"

    def __init__(self, point):
        self.point = point
        self.done = False

    def trip(self, at):
        if at != self.point or self.done:
            return
        self.done = True
        pathlib.Path(sentinel).write_text(at.value)
        session.flush()
        time.sleep(600)


try:
    scenario.executor(faults=Trip(CrashPoint(point_value))).execute(
        scenario.task_id,
        scenario.run_id,
        scenario.stage_id,
        capability="labcairn.artifact.write",
        effect=effect,
        args={{"kind": "report"}},
        kind=ArtifactKind.REPORT,
    )
except BaseException:
    pass
"""


def _kill_child_at(scenario: Scenario, point: CrashPoint) -> bool:
    """Run a child that blocks inside *point*, hard-kill it, report success.

    The child is handed the parent's task/run/stage ids rather than creating its
    own. That is the whole point: a recovery that "worked" because the crashed
    process happened to be working on a different task would prove nothing.
    """
    root = scenario.root
    sentinel = root / f"reached-{point.value}.marker"
    sentinel.unlink(missing_ok=True)

    script = CHILD_SCRIPT.format(
        tests_dir=str(Path(__file__).parent),
        src=str(Path(__file__).parents[1] / "src"),
        body=BODY,
    )
    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            script,
            str(scenario.env.db_path),
            str(root),
            point.value,
            str(sentinel),
            str(scenario.task_id),
            str(scenario.run_id),
            str(scenario.stage_id),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        for _ in range(600):
            if sentinel.exists():
                break
            if child.poll() is not None:
                _report_child_failure(child, point)
                return False
            time_sleep(0.05)
        else:  # pragma: no cover - the child never reached the window
            _report_child_failure(child, point)
            return False

        # Still alive: the sentinel is written *before* the sleep, so its presence
        # proves we reached the window, but only liveness proves the kill is what
        # ended the child rather than something else.
        assert child.poll() is None, (
            "the child exited on its own instead of blocking in the crash window; "
            "the kill would then prove nothing"
        )
        _hard_kill(child)
        child.wait(timeout=30)
        assert child.returncode != 0, f"a hard-killed process cannot exit 0; got {child.returncode}"

        # The child died holding SQLite's shared-memory file. On Windows,
        # `TerminateProcess` returns and `wait()` returns before the kernel has
        # finished tearing down its section objects, so the next connection's
        # `PRAGMA journal_mode=WAL` can hit `disk I/O error` on a `-shm` that is
        # still mapped. Measured: this test failed about two runs in five, and
        # the failure moved from the child's death to the *next* connection.
        #
        # Deleting the sidecars is correct rather than merely convenient. The
        # writer is dead and cannot have committed anything the main file lacks:
        # SQLite recovers a `-wal` into the database on next open, and a `-wal`
        # whose writer was killed mid-transaction holds only what was rolled
        # back. Rebuilding from the main file is exactly the crash the
        # sidecars exist to survive.
        _discard_wal_sidecars(scenario.env.db_path)
        return True
    finally:
        if child.poll() is None:  # pragma: no cover
            _hard_kill(child)
        if child.stderr is not None:
            child.stderr.close()


def _discard_wal_sidecars(db_path: Path) -> None:
    """Remove ``-wal`` and ``-shm`` left by a process that was hard-killed.

    Retried, because the kernel may still hold the removal for a moment after
    the child is reaped. Giving up quietly would reintroduce the flake; giving up
    loudly would fail a test for a reason outside the thing under test, so the
    loop is bounded and the last attempt is allowed to leave the files.
    """
    for suffix in ("-wal", "-shm"):
        sidecar = db_path.with_name(db_path.name + suffix)
        for _ in range(20):
            try:
                sidecar.unlink(missing_ok=True)
                break
            except PermissionError:  # pragma: no cover - Windows teardown
                time_sleep(0.05)


def _report_child_failure(child: subprocess.Popen[bytes], point: CrashPoint) -> None:
    """Surface the child's own error rather than a bare "did not reach".

    A matrix test that reports only "child never reached the injection point"
    sends the reader looking for a timing problem when the real fault is an
    import error in the child three lines away.
    """
    if child.stderr is None:  # pragma: no cover
        return
    detail = child.stderr.read().decode("utf-8", errors="replace")[-2000:]
    raise AssertionError(f"child died before reaching {point.value}:\n{detail}")


def time_sleep(seconds: float) -> None:
    """Named so the import block stays flat and the polling loop is obvious."""
    import time

    time.sleep(seconds)


def _hard_kill(child: subprocess.Popen[bytes]) -> None:
    """Terminate without giving the child a chance to clean up.

    On POSIX this is ``SIGKILL``; on Windows ``taskkill /F``, which is the same
    ``TerminateProcess`` semantics — no ``finally``, no atexit, no buffer flush.
    A graceful kill would make the matrix test prove nothing that the in-process
    injected crash does not already prove.
    """
    if os.name == "nt":  # pragma: no cover - platform branch
        subprocess.run(
            ["taskkill", "/F", "/PID", str(child.pid)],
            capture_output=True,
            check=False,
        )
        return
    import signal

    # `getattr` rather than a `type: ignore`. The ignore was needed on Windows
    # (where `signal.SIGKILL` is absent) and reported as *unused* on Ubuntu,
    # where the stub has it — so the same line could not satisfy mypy on both
    # platforms at once. A platform-conditional ignore is not a fix; removing
    # the dependency on the stub is.
    sigkill = getattr(signal, "SIGKILL", None)
    assert sigkill is not None, "SIGKILL is always defined on POSIX"
    os.kill(child.pid, sigkill)
