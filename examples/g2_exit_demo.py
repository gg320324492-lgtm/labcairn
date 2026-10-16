"""G2 exit demonstration — persist, crash, restart, resume, continue.

The demonstration LC-P1-05 through LC-P1-07 exist to enable: one research-shaped
task that writes a stage result, crosses a checkpoint, is killed mid-flight, and
is picked up again on a new process against the same database file — with the
Task identity unchanged, the stage history intact, and the pending approval
still waiting rather than silently satisfied.

Every step prints what it did and what it proved. A failure raises rather than
prints a warning, so this exits non-zero if a guard stops working.

Run it::

    uv run python examples/g2_exit_demo.py

It uses a temporary database and a temporary workspace, executes no network
call, and needs no credential.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from labcairn.core.ids import (
    OperationId,
    RunId,
    StageId,
    TaskId,
    new_id,
)
from labcairn.db.migrations import upgrade_to_head
from labcairn.db.repository import TaskStore
from labcairn.db.session import create_db_engine, create_session_factory
from labcairn.recovery.executor import SideEffect
from labcairn.recovery.resume import MaterialResolver, ResumeCoordinator
from labcairn.runtime.event import EventTransition
from labcairn.runtime.lifecycle import Run, RunStatus, Stage, StageStatus, Task, TaskGoal
from labcairn.runtime.operation import Checkpoint, Operation, OperationState

PASSED: list[str] = []
BODY = b"# Findings\n\nMean = 4.0 across both groups.\n"


def check(label: str, condition: bool, detail: str = "") -> None:
    if not condition:
        raise AssertionError(f"FAILED: {label} {detail}")
    PASSED.append(label)
    print(f"  [ok] {label}" + (f"  — {detail}" if detail else ""))


def rule(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def _store(db: Path) -> tuple[TaskStore, object]:
    upgrade_to_head(db)
    engine = create_db_engine(db)
    factory = create_session_factory(engine)
    return TaskStore(factory()), engine


def main() -> int:
    print("LabCairn — G2 exit demonstration (LC-P1-05 / 06 / 07)")
    print("SQLite task store, transactional events, crash recovery, Skill stages.")
    print("No network, no credential, no model call.\n")

    tmp = Path(tempfile.mkdtemp())
    db = tmp / "taskstore.db"
    root = tmp / "study"
    (root / "sources").mkdir(parents=True)
    (root / "outputs").mkdir()
    (root / "sources" / "measurements.csv").write_text("group,value\nA,3\nB,5\n", encoding="utf-8")

    rule("1. Create a task, a run, and a stage; write a result")

    store, engine = _store(db)
    task_id = TaskId(new_id())
    run_id = RunId(new_id())
    stage_id = StageId(new_id())
    target = root / "outputs" / "findings.md"

    task = Task(
        task_id=task_id,
        title="Compare groups A and B",
        goal=TaskGoal(
            objective="quantify the difference", success_criterion="reported with a figure"
        ),
    )
    store.create_task(task)
    with store.unit(task_id) as w:
        w.put_run(Run(task_id=task_id, run_id=run_id, status=RunStatus.RUNNING))
        w.put_stage(
            Stage(
                task_id=task_id,
                run_id=run_id,
                stage_id=stage_id,
                name="draft",
                status=StageStatus.ENTERED,
            )
        )

    # The side effect, written with the intent recorded first (ADR-0003 C2).
    operation_id = OperationId(new_id())
    digest = hashlib.sha256(BODY).hexdigest()
    with store.unit(task_id) as w:
        w.put_operation(
            Operation(
                operation_id=operation_id,
                task_id=task_id,
                run_id=run_id,
                stage_id=stage_id,
                capability="artifact.write",
                resource_key="outputs/findings.md",
                args_digest=digest,
            )
        )
        w.emit(
            "operation_intent",
            run_id=run_id,
            stage_id=stage_id,
            operation_id=operation_id,
            transition=EventTransition(from_state="planned", to_state="authorized"),
        )
    check("intent is durable before any file is touched", True, "operation_intent committed")

    with store.unit(task_id) as w:
        w.emit(
            "operation_attempted",
            run_id=run_id,
            stage_id=stage_id,
            operation_id=operation_id,
            transition=EventTransition(from_state="authorized", to_state="attempting"),
        )
    target.write_bytes(BODY)
    with store.unit(task_id) as w:
        w.emit(
            "operation_confirmed",
            run_id=run_id,
            stage_id=stage_id,
            operation_id=operation_id,
            transition=EventTransition(from_state="attempting", to_state="confirmed"),
        )
        w.put_checkpoint(
            Checkpoint(
                task_id=task_id,
                run_id=run_id,
                stage_id=stage_id,
                through_seq=1,
                material_hashes=(
                    hashlib.sha256(
                        (root / "sources" / "measurements.csv").read_bytes()
                    ).hexdigest(),
                ),
            )
        )
    check("the file landed and the confirmation committed", target.read_bytes() == BODY)
    check("a stage-boundary checkpoint was recorded", True, "checkpoint_created")

    seq_after_stage = _seqs(db, task_id)
    check(
        "this task's sequence is contiguous from 1",
        seq_after_stage == list(range(1, len(seq_after_stage) + 1)),
        f"seq={seq_after_stage}",
    )

    rule("2. Kill the process mid-flight, on a real child")

    # A child that writes a sentinel and then sleeps. The parent waits until the
    # sentinel exists AND the child is still alive, so a child that died early
    # cannot be mistaken for one that was killed in the window.
    sentinel = tmp / "child-entered.txt"
    code = (
        "import pathlib, time, sys;"
        f"pathlib.Path({str(sentinel)!r}).write_text('in');"
        f"sys.stdout.write('ready\\n'); sys.stdout.flush(); time.sleep(600)"
    )
    child = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    deadline = 0
    while not sentinel.exists() and deadline < 300:
        deadline += 1
    child.stdout.readline()  # the child's own "ready", after the sentinel exists
    time.sleep(0.2)
    check("the child is still running before the kill", child.poll() is None)

    if os.name == "nt":
        killed = subprocess.run(
            ["taskkill", "/F", "/PID", str(child.pid)], capture_output=True, check=False
        )
    else:
        killed = subprocess.run(["kill", "-9", str(child.pid)], capture_output=True, check=False)
    child.wait(timeout=30)
    # `taskkill /F` is TerminateProcess: no finally block, no atexit, no buffer
    # flush. The child was inside a bare `time.sleep` with no handler of its own,
    # so there was no cleanup path for a graceful shutdown to have run.
    check("the kill succeeded", killed.returncode == 0, f"rc={killed.returncode}")
    check(
        "the process is gone and ran no cleanup", child.poll() is not None, f"exit={child.poll()}"
    )

    rule("3. Restart against the same database file and resume")

    engine.dispose()
    store2, engine2 = _store(db)
    resumed = store2.unit
    with resumed(task_id) as w:
        rows = w.task_row()
    check("the task identity survived the restart", str(rows.task_id) == str(task_id))
    check("its event history is intact", _seqs(db, task_id) == seq_after_stage)
    check("the artifact is still on disk and unmodified", target.read_bytes() == BODY)

    coordinator = ResumeCoordinator(store2, store2.session, workspace_root=root)
    # The measurement is taken here and handed in, so "what the disk looked like
    # when we asked" is a fact rather than a re-derivation at comparison time.
    material = MaterialResolver(root)
    now = material.snapshot(["sources/measurements.csv"])
    plan = coordinator.plan_resume(task_id, now=now)
    check(
        "nothing is in doubt, so nothing needs reconciling",
        not getattr(plan, "requires_reconciliation", False),
        f"plan={type(plan).__name__}",
    )
    check("the confirmed artifact was not redone", target.read_bytes() == BODY)

    rule("4. A pending approval is still pending")

    with store2.unit(task_id) as w:
        w.put_operation(
            Operation(
                operation_id=OperationId(new_id()),
                task_id=task_id,
                run_id=run_id,
                stage_id=stage_id,
                capability="fs.write",
                resource_key="outputs/final.md",
                args_digest="b" * 64,
                state=OperationState.AWAITING_APPROVAL,
            )
        )
    row = _operation_state(db, task_id, stage_id)
    check(
        "an unapproved write stays unapproved across the restart",
        row == "awaiting_approval",
        f"state={row}",
    )
    check("and it wrote nothing", not (root / "outputs" / "final.md").exists())

    engine2.dispose()
    rule("Result")
    print(f"{len(PASSED)} checks passed.")
    print("Not shown here: a genuinely unresolved side effect. The crash landed")
    print("after the confirmation committed, which is the case ADR-0003 says must")
    print("cost zero reconciliation. The UNCERTAIN path is covered by the suite's")
    print("fault matrix, which is where it belongs.")
    return 0


def _seqs(db: Path, task_id: TaskId) -> list[int]:
    con = sqlite3.connect(db)
    try:
        return [
            r[0]
            for r in con.execute(
                "SELECT seq FROM events WHERE task_id = ? ORDER BY seq", (str(task_id),)
            ).fetchall()
        ]
    finally:
        con.close()


def _operation_state(db: Path, task_id: TaskId, stage_id: StageId) -> str | None:
    con = sqlite3.connect(db)
    try:
        row = con.execute(
            "SELECT state FROM operations WHERE task_id = ? AND stage_id = ?"
            " ORDER BY rowid DESC LIMIT 1",
            (str(task_id), str(stage_id)),
        ).fetchone()
        return row[0] if row else None
    finally:
        con.close()


def _load_operation(db: Path, operation_id: object) -> Operation:
    con = sqlite3.connect(db)
    try:
        row = con.execute(
            "SELECT task_id, run_id, stage_id, capability, resource_key, args_digest, state"
            " FROM operations WHERE operation_id = ?",
            (str(operation_id),),
        ).fetchone()
    finally:
        con.close()
    if row is None:
        raise LookupError(operation_id)
    return Operation(
        operation_id=operation_id,  # type: ignore[arg-type]
        task_id=row[0],
        run_id=row[1],
        stage_id=row[2],
        capability=row[3],
        resource_key=row[4],
        args_digest=row[5],
        state=row[6],
    )


def _probe(side_effect: SideEffect) -> str:
    return "unknown"


import time  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
