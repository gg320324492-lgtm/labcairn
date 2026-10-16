"""G2's remaining demonstration — what happens when the system cannot tell.

The other exit demonstration shows recovery after a **confirmed** side effect,
which ADR-0003 says must cost zero reconciliation. This one shows the case the
whole design exists for: the process died between writing the file and
committing the confirmation, so the database cannot say whether the effect
landed. It records UNCERTAIN, blocks, probes the bytes, and refuses to replay
until a probe resolves it.

It also demonstrates the refusal that makes it safe. A second attempt to write
the same file, while the operation is still UNCERTAIN, must be refused — because
"the effect did not land" is exactly the assumption this project forbids.

Run it::

    uv run python examples/g2_uncertain_demo.py

Temporary database, temporary workspace, no network, no credential.
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from labcairn.core.ids import OperationId, RunId, StageId, TaskId, new_id
from labcairn.db.migrations import upgrade_to_head
from labcairn.db.repository import TaskStore
from labcairn.db.session import create_db_engine, create_session_factory
from labcairn.recovery import (
    ArmedFaults,
    FileSystemProbe,
    InjectedCrash,
    RecoveryCoordinator,
    SideEffectExecutor,
    hash_bytes,
)
from labcairn.recovery.contracts import CrashPoint, SideEffect
from labcairn.recovery.persistence import load_operation
from labcairn.runtime.event import EventType
from labcairn.runtime.lifecycle import Run, RunStatus, Stage, StageStatus, Task, TaskGoal
from labcairn.runtime.operation import OperationState

PASSED: list[str] = []
BODY = b"# Draft\n\nGroup A mean = 3.0, group B mean = 5.0.\n"
RESOURCE = "outputs/draft.md"


def check(label: str, condition: bool, detail: str = "") -> None:
    if not condition:
        raise AssertionError(f"FAILED: {label} {detail}")
    PASSED.append(label)
    print(f"  [ok] {label}" + (f"  — {detail}" if detail else ""))


def rule(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def main() -> int:
    print("LabCairn — G2, the uncertain path")
    print("A side effect whose outcome the database cannot vouch for.\n")

    tmp = Path(tempfile.mkdtemp())
    db = tmp / "taskstore.db"
    root = tmp / "study"
    (root / "outputs").mkdir(parents=True)
    target = root / "outputs" / "draft.md"
    expected = hashlib.sha256(BODY).hexdigest()

    upgrade_to_head(db)
    engine = create_db_engine(db)
    store = TaskStore(create_session_factory(engine)())

    task_id, run_id, stage_id = TaskId(new_id()), RunId(new_id()), StageId(new_id())
    store.create_task(
        Task(
            task_id=task_id,
            title="Draft a findings section",
            goal=TaskGoal(objective="report both group means", success_criterion="a figure"),
        )
    )
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

    rule("1. The process dies between writing and confirming")

    def write_the_file() -> str:
        target.write_bytes(BODY)
        return hash_bytes(target.read_bytes())

    executor = SideEffectExecutor(
        store,
        store.session,
        workspace_root=root,
        # A real injection point inside the executor, not a flag the demo sets.
        faults=ArmedFaults(CrashPoint.AFTER_WRITE_BEFORE_CONFIRM),
    )
    try:
        executor.execute(
            task_id,
            run_id,
            stage_id,
            capability="artifact.write",
            effect=SideEffect(
                resource_key=RESOURCE, expected_sha256=expected, apply=write_the_file
            ),
            args={"path": RESOURCE},
        )
        raise AssertionError("FAILED: the injected crash did not fire")
    except InjectedCrash:
        check("the process died inside the write-then-confirm window", True)

    check("the file is on disk", target.is_file())
    check("its bytes are exactly what was intended", hash_bytes(target.read_bytes()) == expected)

    # The database rolled back, because the confirmation never committed.
    rolled_back = load_operation(store.session, _sole_operation_id(db))
    check(
        "the confirmation rolled back, so the database has no receipt",
        rolled_back.state is OperationState.ATTEMPTING,
        f"state={rolled_back.state.value}",
    )

    rule("2. The system records what it cannot tell")

    recovery = RecoveryCoordinator(
        store, store.session, workspace_root=root, probe=FileSystemProbe(root)
    )
    entered = recovery.mark_uncertain(task_id)
    check("the in-flight operation entered UNCERTAIN", len(entered) == 1)

    operation_id = _sole_operation_id(db)
    state = load_operation(store.session, operation_id).state
    check(
        "its state is UNCERTAIN, not a guess",
        state is OperationState.UNCERTAIN,
        f"state={state.value}",
    )
    check(
        "the stage was blocked with a reason a reader can act on",
        _stage_blocked_reason(db) is not None,
        (_stage_blocked_reason(db) or "")[:60],
    )

    rule("3. Replay is refused until a probe resolves it")

    try:
        recovery.assert_replayable(operation_id)
        raise AssertionError("FAILED: an unresolved UNCERTAIN operation was replayable")
    except Exception as exc:
        check(
            "replay is refused while the outcome is unknown",
            "uncertain" in str(exc).lower(),
            type(exc).__name__,
        )

    try:
        executor.replay(
            operation_id,
            effect=SideEffect(
                resource_key=RESOURCE, expected_sha256=expected, apply=write_the_file
            ),
            args={"path": RESOURCE},
        )
        raise AssertionError("FAILED: replay ran against an unresolved operation")
    except Exception as exc:
        check(
            "the executor refuses to replay it too",
            type(exc).__name__ != "AssertionError",
            type(exc).__name__,
        )
    check("the file was not written a second time", hash_bytes(target.read_bytes()) == expected)

    rule("4. A probe over the actual bytes resolves it")

    verdict = recovery.probe(operation_id, expected_sha256=expected)
    check(
        "the probe found the intended bytes",
        verdict.observed_sha256 == expected,
        f"resolution={verdict.resolution.value}",
    )
    check("and said so in words a human can check", bool(verdict.detail), verdict.detail[:70])

    outcome = recovery.reconcile(operation_id, expected_sha256=expected)
    final = load_operation(store.session, operation_id).state
    check("the operation is CONFIRMED", final is OperationState.CONFIRMED, f"state={final.value}")
    check("reached by a probe, not by re-running the write", outcome.reached_by.value == "probe")
    check("the file is still the same bytes", hash_bytes(target.read_bytes()) == expected)

    import json

    event = _reconciled_event_payload(db)
    check(
        "the resolution is stored, not inferred",
        event.get("resolution") == "confirmed",
        f"payload={json.dumps(event, sort_keys=True)[:80]}",
    )
    check("and the mechanism is stored beside it", event.get("reached_by") == "probe")

    recovery.assert_replayable(operation_id)
    check("replay is permitted once the outcome is settled", True)

    engine.dispose()
    rule("Result")
    print(f"{len(PASSED)} checks passed.")
    print("The database never decided whether the write landed. The bytes did.")
    return 0


def _sole_operation_id(db: Path) -> OperationId:
    import sqlite3
    import uuid

    con = sqlite3.connect(db)
    try:
        rows = [r[0] for r in con.execute("SELECT operation_id FROM operations")]
    finally:
        con.close()
    if len(rows) != 1:
        raise AssertionError(f"expected exactly one operation, found {rows}")
    return OperationId(uuid.UUID(rows[0]))


def _stage_blocked_reason(db: Path) -> str | None:
    import sqlite3

    con = sqlite3.connect(db)
    try:
        row = con.execute("SELECT blocked_reason FROM stages").fetchone()
    finally:
        con.close()
    return row[0] if row else None


def _reconciled_event_payload(db: Path) -> dict:
    import json
    import sqlite3

    con = sqlite3.connect(db)
    try:
        row = con.execute(
            "SELECT payload FROM events WHERE type = ?", (EventType.OPERATION_RECONCILED.value,)
        ).fetchone()
    finally:
        con.close()
    if row is None:
        raise AssertionError("no operation_reconciled event was written")
    return json.loads(row[0])


if __name__ == "__main__":
    raise SystemExit(main())
