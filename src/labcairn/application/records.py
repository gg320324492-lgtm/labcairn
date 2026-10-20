"""Writing the store's records: runs, stages, operations and approvals.

Every write in this layer goes through here, so the rules that hold for all of
them are stated once rather than repeated in each operation:

* **an event and the state it describes commit together.** ADR-0003 C3
  requires it, and :meth:`~labcairn.db.repository.TaskStore.unit` is the only
  way to do it: the events are staged first and the state rows second, so an
  ``operation_intent`` may name an operation whose row does not exist yet.
* **a transition event carries the states it moved between**, so the event log
  can say what happened without the rows being read.
* **nothing is written on a refusal.** A refused operation leaves no trace
  that could be mistaken for a partial success.

The runs and stages are created here rather than by the caller, because a Run
and a Stage are not free parameters: a Run's attempt number is derived from
the task's other runs, and a Stage belongs to exactly one Run. A caller that
minted its own would have to know both rules, and two callers would know them
differently.
"""

from __future__ import annotations

from datetime import datetime

from labcairn.application.context import ApplicationContext, store_refusals
from labcairn.core.ids import RunId, StageId, new_id
from labcairn.db.repository import list_runs, list_stages
from labcairn.reports.receipt import ArtifactReceipt
from labcairn.runtime.event import EventTransition, EventType
from labcairn.runtime.lifecycle import Run, RunStatus, Stage, StageStatus
from labcairn.runtime.operation import Approval, ApprovalState, Operation, OperationState


def ensure_run(context: ApplicationContext, run_id: RunId | None, *, now: datetime) -> Run:
    """The task's run, created if it does not exist.

    A resume is a **new** Run against the same Task and never a new Task
    (ADR-0003 C1, R-02), so the attempt number is one more than the highest
    the task's runs already carry. Deriving it rather than counting the rows
    means two runs cannot both claim to be the first.
    """
    with store_refusals():
        runs = list_runs(context.store.session, context.task_id)
    chosen = RunId(new_id()) if run_id is None else run_id
    existing = next((run for run in runs if run.run_id == chosen), None)
    if existing is not None:
        return existing

    attempt = max((run.attempt for run in runs), default=0) + 1
    started = Run(
        run_id=chosen,
        task_id=context.task_id,
        status=RunStatus.RUNNING,
        attempt=attempt,
        started_at=now,
    )
    with context.store.unit(context.task_id) as work:
        work.emit(
            EventType.RUN_STARTED,
            run_id=chosen,
            transition=EventTransition(
                from_state=RunStatus.PENDING.value,
                to_state=RunStatus.RUNNING.value,
            ),
            occurred_at=now,
        )
        work.put_run(started)
    return started


def ensure_stage(context: ApplicationContext, run: Run, stage_name: str, *, now: datetime) -> Stage:
    """The named stage in that run, created if it does not exist.

    Scoped to the Run, because a stage name repeats across Runs of the same
    Task and a name-only lookup would silently bridge two different attempts.
    """
    with store_refusals():
        stages = list_stages(context.store.session, context.task_id)
    existing = next(
        (stage for stage in stages if stage.run_id == run.run_id and stage.name == stage_name),
        None,
    )
    if existing is not None:
        return existing

    entered = Stage(
        stage_id=StageId(new_id()),
        task_id=context.task_id,
        run_id=run.run_id,
        name=stage_name,
        status=StageStatus.ENTERED,
    )
    with context.store.unit(context.task_id) as work:
        work.emit(
            EventType.STAGE_ENTERED,
            run_id=run.run_id,
            stage_id=entered.stage_id,
            transition=EventTransition(
                from_state=StageStatus.PENDING.value,
                to_state=StageStatus.ENTERED.value,
            ),
            occurred_at=now,
        )
        work.put_stage(entered)
    return entered


def move_operation(
    context: ApplicationContext,
    operation: Operation,
    *,
    event: EventType,
    to_state: OperationState,
    now: datetime,
) -> Operation:
    """An operation moving to another state, and the event that says so.

    The state it moved *from* is the operation's own current state, so a
    caller cannot assert a transition that did not happen.
    """
    moved = operation.model_copy(update={"state": to_state})
    with context.store.unit(context.task_id) as work:
        work.emit(
            event,
            run_id=moved.run_id,
            stage_id=moved.stage_id,
            operation_id=moved.operation_id,
            transition=EventTransition(
                from_state=operation.state.value,
                to_state=to_state.value,
            ),
            occurred_at=now,
        )
        work.put_operation(moved)
    return moved


def complete_operation(
    context: ApplicationContext,
    operation: Operation,
    stage: Stage,
    artifacts: tuple[ArtifactReceipt, ...],
    *,
    run_id: RunId | None,
    output_hashes: tuple[str, ...],
    now: datetime,
) -> tuple[Operation, Stage]:
    """The operation confirmed, the stage completed and the artefacts recorded.

    One transaction, because they are one fact: the work happened, here is
    what it produced. Split across three transactions, a crash between them
    would leave an operation claiming to have landed with no artefact
    describing what it produced — which is exactly the reconciliation
    ADR-0003 C3 exists to avoid.
    """
    confirmed = operation.model_copy(update={"state": OperationState.CONFIRMED})
    completed = stage.model_copy(
        update={"status": StageStatus.COMPLETED, "output_hashes": output_hashes}
    )
    with context.store.unit(context.task_id) as work:
        work.emit(
            EventType.OPERATION_CONFIRMED,
            run_id=confirmed.run_id,
            stage_id=confirmed.stage_id,
            operation_id=confirmed.operation_id,
            transition=EventTransition(
                from_state=operation.state.value,
                to_state=OperationState.CONFIRMED.value,
            ),
            occurred_at=now,
        )
        work.emit(
            EventType.STAGE_COMPLETED,
            run_id=completed.run_id,
            stage_id=completed.stage_id,
            transition=EventTransition(
                from_state=stage.status.value,
                to_state=StageStatus.COMPLETED.value,
            ),
            occurred_at=now,
        )
        for receipt in artifacts:
            work.put_artifact(receipt, run_id=run_id)
        if artifacts:
            work.emit(EventType.ARTIFACT_RECORDED, occurred_at=now)
        work.put_operation(confirmed)
        work.put_stage(completed)
    return confirmed, completed


def fail_operation(
    context: ApplicationContext,
    operation: Operation,
    stage: Stage,
    *,
    now: datetime,
) -> tuple[Operation, Stage]:
    """The operation failed, and the stage it failed in.

    **The event vocabulary has no ``stage_failed``.** ADR-0003 C1's closed list
    has ``stage_entered``, ``stage_completed`` and ``stage_blocked``, and C3
    forbids a state-row update that no event describes. So the failure is
    recorded where the vocabulary has room for it — on the operation, whose
    state machine does have ``FAILED`` — and the stage row records where it
    happened, in the same transaction.

    Leaving the stage ``ENTERED`` instead was the alternative, and it is
    worse: it would report a stage as still running after it had failed.
    """
    failed = operation.model_copy(update={"state": OperationState.FAILED})
    stopped = stage.model_copy(update={"status": StageStatus.FAILED})
    with context.store.unit(context.task_id) as work:
        work.emit(
            EventType.OPERATION_FAILED,
            run_id=failed.run_id,
            stage_id=failed.stage_id,
            operation_id=failed.operation_id,
            transition=EventTransition(
                from_state=operation.state.value,
                to_state=OperationState.FAILED.value,
            ),
            occurred_at=now,
        )
        work.put_operation(failed)
        work.put_stage(stopped)
    return failed, stopped


def block_stage(
    context: ApplicationContext,
    stage: Stage,
    reason: str,
    *,
    now: datetime,
) -> Stage:
    """The stage parked, waiting for something that has not happened.

    The operation is left where it is: the effect did not happen, and an
    operation that was authorised and never attempted is the honest state.
    """
    blocked = stage.model_copy(update={"status": StageStatus.BLOCKED, "blocked_reason": reason})
    with context.store.unit(context.task_id) as work:
        work.emit(
            EventType.STAGE_BLOCKED,
            run_id=blocked.run_id,
            stage_id=blocked.stage_id,
            transition=EventTransition(
                from_state=stage.status.value,
                to_state=StageStatus.BLOCKED.value,
            ),
            occurred_at=now,
        )
        work.put_stage(blocked)
    return blocked


def plan_approval(
    context: ApplicationContext,
    operation: Operation,
    approval: Approval,
    stage: Stage,
    reason: str,
    *,
    run_id: RunId,
    now: datetime,
) -> tuple[Operation, Approval, Stage]:
    """The operation awaiting approval, the approval asked for, and the stage parked.

    One transaction, because they are one fact: a question was put about this
    operation, and the stage that asked it is waiting for the answer. Two
    transactions would leave an approval with no operation or an operation with
    no approval, and neither is a state the audit log should be able to show.

    The stage is parked as ``BLOCKED`` here rather than left ``ENTERED``, and
    the reason is on the row: a stage that is waiting for a human and a stage
    that is running look identical otherwise, and only one of them is true.
    """
    awaiting = operation.model_copy(update={"state": OperationState.AWAITING_APPROVAL})
    blocked = stage.model_copy(update={"status": StageStatus.BLOCKED, "blocked_reason": reason})
    with context.store.unit(context.task_id) as work:
        work.emit(
            EventType.OPERATION_AWAITING_APPROVAL,
            run_id=run_id,
            stage_id=awaiting.stage_id,
            operation_id=awaiting.operation_id,
            transition=EventTransition(
                from_state=operation.state.value,
                to_state=OperationState.AWAITING_APPROVAL.value,
            ),
            occurred_at=now,
        )
        work.emit(
            EventType.APPROVAL_REQUESTED,
            run_id=run_id,
            transition=EventTransition(
                from_state=ApprovalState.PENDING.value,
                to_state=ApprovalState.PENDING.value,
            ),
            occurred_at=now,
        )
        work.emit(
            EventType.STAGE_BLOCKED,
            run_id=run_id,
            stage_id=blocked.stage_id,
            transition=EventTransition(
                from_state=stage.status.value,
                to_state=StageStatus.BLOCKED.value,
            ),
            occurred_at=now,
        )
        work.put_operation(awaiting)
        work.put_approval(approval)
        work.put_stage(blocked)
    return awaiting, approval, blocked


def move_approval(
    context: ApplicationContext,
    approval: Approval,
    *,
    event: EventType,
    from_state: ApprovalState,
    to_state: ApprovalState,
    run_id: RunId,
    now: datetime,
    granted_at: datetime | None = None,
    consumed_at: datetime | None = None,
) -> Approval:
    """An approval moving between two states, and the event that says so.

    Approval events are run-scoped, so the Run the approval belongs to is
    named: it is the Run of the operation the approval was asked for.
    """
    moved = approval.model_copy(
        update={
            "state": to_state,
            "granted_at": granted_at if granted_at is not None else approval.granted_at,
            "consumed_at": consumed_at if consumed_at is not None else approval.consumed_at,
        }
    )
    with context.store.unit(context.task_id) as work:
        work.emit(
            event,
            run_id=run_id,
            transition=EventTransition(
                from_state=from_state.value,
                to_state=to_state.value,
            ),
            occurred_at=now,
        )
        work.put_approval(moved)
    return moved


__all__ = [
    "block_stage",
    "complete_operation",
    "ensure_run",
    "ensure_stage",
    "fail_operation",
    "move_approval",
    "move_operation",
    "plan_approval",
]
