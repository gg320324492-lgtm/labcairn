"""Writing the store's records: runs, stages, operations and approvals.

Every write in this layer goes through here, so the rules that hold for all of
them are stated once rather than repeated in each operation:

* **an event and the state it describes commit together.** ADR-0003 C3
  requires it, and :meth:`~labcairn.db.repository.TaskStore.unit` is the only
  way to do it: the events are staged first and the state rows second, so an
  ``operation_intent`` may name an operation whose row does not exist yet.
* **a transition event carries the states it moved between**, so the event log
  can say what happened without the rows being read.
* **nothing is written on a refusal — except a policy denial, and only on the
  path that writes.** A refused operation leaves no trace that could be
  mistaken for a partial success. **The path that records a denial is the one
  that writes**: the stage layer asks the policy for a verdict
  (:func:`labcairn.application.consent.decide`), and a ``DENY`` there is
  recorded as an operation in state ``denied`` — carrying the reason the
  permission layer produced — and *then* refused, because a refusal nobody can
  see is a refusal the operator cannot act on, and a row whose state says
  ``denied`` is not a trace that could be mistaken for a partial success.
  Every other path asks the policy through
  :func:`labcairn.application.consent.evaluate`, which raises
  ``PERMISSION_DENIED`` and writes nothing — and that is the right shape
  rather than a gap: a request for approval that the policy refuses never got
  as far as a write, so there is no run, no stage and no operation for a
  denial to belong to, and inventing them would be the very trace that could
  be mistaken for a partial success.
* **a denial's whole trace is one transaction.** The run, the stage, the
  operation and the events that describe them are written by one unit of
  work, so they commit together or not at all: a denial whose
  ``operation_denied`` event cannot be written leaves **nothing** behind,
  because a run in ``running`` and a stage in ``entered`` are exactly the
  trace that could be mistaken for a partial success. The unit of work commits
  on a clean exit and rolls back on an exception, which is what makes the
  operation's row and the event that describes it one fact — ADR-0003 C3
  requires it, and
  :meth:`~labcairn.db.repository.TaskStore.unit` is the only way to do it.
* **a stage's status and its reason are written together.** The schema pairs
  them — a stage is ``blocked`` if and only if it carries a reason — so the
  two are set in one update. A stage that is waiting says why it is waiting;
  a stage that has finished says nothing, because it is waiting for nothing.

The runs and stages are created here rather than by the caller, because a Run
and a Stage are not free parameters: a Run's attempt number is derived from
the task's other runs, and a Stage belongs to exactly one Run. A caller that
minted its own would have to know both rules, and two callers would know them
differently.
"""

from __future__ import annotations

from datetime import datetime

from labcairn.application.context import ApplicationContext, store_refusals
from labcairn.core.ids import OperationId, RunId, StageId, new_id
from labcairn.db.repository import UnitOfWork, list_runs, list_stages
from labcairn.reports.receipt import ArtifactReceipt
from labcairn.runtime.event import EventTransition, EventType
from labcairn.runtime.lifecycle import Run, RunStatus, Stage, StageStatus
from labcairn.runtime.operation import Approval, ApprovalState, Operation, OperationState


def _planned_run(
    context: ApplicationContext, run_id: RunId | None, *, now: datetime
) -> tuple[Run, bool]:
    """The task's run, and whether it still has to be created.

    **Planning is separate from writing** so that a caller that needs the
    run's id *inside* a larger unit of work — the denial does, because its
    operation's row names the run — can have the answer without committing
    anything yet.

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
        return existing, False

    attempt = max((run.attempt for run in runs), default=0) + 1
    started = Run(
        run_id=chosen,
        task_id=context.task_id,
        status=RunStatus.RUNNING,
        attempt=attempt,
        started_at=now,
    )
    return started, True


def _write_run(work: UnitOfWork, run: Run, *, now: datetime) -> None:
    """The run's event and its row, into a unit of work the caller owns.

    The two are written together because ADR-0003 C3 requires it: an event
    and the state it describes commit together, or not at all.
    """
    work.emit(
        EventType.RUN_STARTED,
        run_id=run.run_id,
        transition=EventTransition(
            from_state=RunStatus.PENDING.value,
            to_state=RunStatus.RUNNING.value,
        ),
        occurred_at=now,
    )
    work.put_run(run)


def ensure_run(context: ApplicationContext, run_id: RunId | None, *, now: datetime) -> Run:
    """The task's run, created if it does not exist.

    The attempt number is **derived rather than counted** — one more than the
    highest the task's runs already carry — so two runs cannot both claim to
    be the first; :func:`_planned_run` is where that happens.

    The run is created in a unit of work of its own, because a run on its own
    is a fact on its own: a caller that wanted the run and something else to
    be one fact asks :func:`record_denial` instead, which writes both in one
    transaction.
    """
    run, created = _planned_run(context, run_id, now=now)
    if not created:
        return run
    with context.store.unit(context.task_id) as work:
        _write_run(work, run, now=now)
    return run


def _planned_stage(context: ApplicationContext, run: Run, stage_name: str) -> tuple[Stage, bool]:
    """The named stage in that run, and whether it still has to be created.

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
        return existing, False

    entered = Stage(
        stage_id=StageId(new_id()),
        task_id=context.task_id,
        run_id=run.run_id,
        name=stage_name,
        status=StageStatus.ENTERED,
    )
    return entered, True


def _write_stage(work: UnitOfWork, stage: Stage, *, now: datetime) -> None:
    """The stage's event and its row, into a unit of work the caller owns."""
    work.emit(
        EventType.STAGE_ENTERED,
        run_id=stage.run_id,
        stage_id=stage.stage_id,
        transition=EventTransition(
            from_state=StageStatus.PENDING.value,
            to_state=StageStatus.ENTERED.value,
        ),
        occurred_at=now,
    )
    work.put_stage(stage)


def ensure_stage(context: ApplicationContext, run: Run, stage_name: str, *, now: datetime) -> Stage:
    """The named stage in that run, created if it does not exist.

    Scoped to the Run, because a stage name repeats across Runs of the same
    Task and a name-only lookup would silently bridge two different attempts.
    """
    stage, created = _planned_stage(context, run, stage_name)
    if not created:
        return stage
    with context.store.unit(context.task_id) as work:
        _write_stage(work, stage, now=now)
    return stage


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


def _finished(stage: Stage, status: StageStatus, output_hashes: tuple[str, ...]) -> Stage:
    """The stage in the status it has finished in, with nothing left to wait for.

    A reason belongs to a stage that is waiting for something, and the schema
    pairs the two: ``(status = 'blocked') = (blocked_reason IS NOT NULL)``. A
    stage that has finished is waiting for nothing, so the reason goes when the
    wait ends — and it goes here, where the status is set, because that is
    where the two halves are one decision and are written together.

    Left on the row, it is a row the database refuses to write, and the refusal
    reaches the caller as a raw ``IntegrityError`` out of the middle of the
    transaction rather than as a finished stage.

    Re-validated rather than copied, for the reason
    :mod:`labcairn.recovery.reconciliation` gives: ``model_copy`` does not run
    the model's validators, and the ``Stage`` model's ``blocked_reason``
    validator is what keeps a reason attached only to a blocked stage. Going
    through :meth:`Stage.model_validate` means a mistake here fails here
    instead of producing a row that cannot be loaded back.
    """
    return Stage.model_validate(
        {
            **stage.model_dump(),
            "status": status,
            "output_hashes": output_hashes,
            "blocked_reason": None,
        }
    )


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
    completed = _finished(stage, StageStatus.COMPLETED, output_hashes)
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
    stopped = _finished(stage, StageStatus.FAILED, stage.output_hashes)
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


def record_denial(
    context: ApplicationContext,
    *,
    run_id: RunId | None,
    stage_name: str,
    capability: str,
    resource_key: str,
    depends_on: tuple[str, ...],
    args_digest: str,
    reason: str,
    matched_rule: str | None = None,
    matched_spelling: str | None = None,
    now: datetime,
) -> tuple[Operation, Stage]:
    """The denial, and everything it needs, in one transaction.

    **One unit of work holds the whole trace.** The run, the stage, the
    operation and the three events that describe them are written together, so
    they commit together or not at all: if the ``operation_denied`` event
    cannot be written, nothing the denial created survives — no run, no stage,
    no operation. Three transactions would not do that, because the run and
    the stage would be committed before the event that says the write was
    refused, and a failure at the last step would leave the first two behind:
    a run in ``running`` and a stage in ``entered`` are precisely the trace
    that could be mistaken for a partial success.

    **The operation's row and its event are one fact**, written in the same
    unit as the run and the stage. ADR-0003 C3 requires it, and the unit of
    work commits on a clean exit and rolls back on an exception — so a
    denial that cannot be written leaves nothing behind rather than half of
    something.

    **The reason is the permission layer's own word** — a
    :class:`~labcairn.security.policy.DecisionReason` value rather than
    prose, because a reader asking "was this the default deny, or a rule of
    mine?" needs the word and only the word answers it. The rule that
    matched, and which spelling of the path matched it, ride with it.

    **The stage is written twice, and the second write is the one that
    stands.** It enters as ``ENTERED`` and stops as ``FAILED``, because a
    stage that is still reported as running after the policy stopped it is
    worse than one that says it failed. Both writes are in the same unit, so
    a reader sees the same end state it saw when they were two units — and
    an interruption between them leaves neither.

    **The digest is the caller's to compute, and it comes first.** The
    operation's row is bound to a digest of the arguments, and a row carrying
    a digest no reader could reproduce would be a lie — so the caller
    computes the digest and the run and the stage are created only once it is
    in hand.
    """
    run, run_is_new = _planned_run(context, run_id, now=now)
    stage, stage_is_new = _planned_stage(context, run, stage_name)
    operation = Operation(
        operation_id=OperationId(new_id()),
        task_id=context.task_id,
        run_id=run.run_id,
        stage_id=stage.stage_id,
        state=OperationState.PLANNED,
        capability=capability,
        resource_key=resource_key,
        depends_on=depends_on,
        args_digest=args_digest,
    )
    denied = operation.model_copy(update={"state": OperationState.DENIED})
    stopped = _finished(stage, StageStatus.FAILED, stage.output_hashes)
    with context.store.unit(context.task_id) as work:
        if run_is_new:
            _write_run(work, run, now=now)
        if stage_is_new:
            _write_stage(work, stage, now=now)
        work.emit(
            EventType.OPERATION_DENIED,
            run_id=denied.run_id,
            stage_id=denied.stage_id,
            operation_id=denied.operation_id,
            transition=EventTransition(
                from_state=operation.state.value,
                to_state=OperationState.DENIED.value,
            ),
            payload={
                "reason": reason,
                "matched_rule": matched_rule,
                "matched_spelling": matched_spelling,
            },
            occurred_at=now,
        )
        work.put_operation(denied)
        work.put_stage(stopped)
    return denied, stopped


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
    "record_denial",
]
