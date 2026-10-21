"""Running a stage, and reading the plan and the steps.

The workflow is already declared as data — :mod:`labcairn.skills.declaration`
states the ``intake → inventory → retrieve → evidence → propose → [approval] →
draft → validate → deliver`` flow with typed ports and a digest — so this layer
does not re-declare a pipeline. It reads the declaration, reads what the store
recorded, and joins them.

What "the plan" and "the steps" are
----------------------------------

They are two different things and the distinction is worth stating, because
one of them is a declaration and the other is a record:

* **the plan** is the *declared* workflow, each declared stage with the status
  this task has reached in it. It answers "where should this task be";
* **the steps** are the *runtime* stages the store holds, each with the run it
  belonged to and that run's attempt. It answers "what actually happened".

Neither is derived from the other, so a stage that ran outside the declared
workflow is still visible in the steps, and a declared stage nobody reached is
still visible in the plan.

What a stage run is
-------------------

A stage run is a **capability-guarded effect**, and the layer owns three
things around it: the consent, the bookkeeping, and the record of the outcome.
The effect itself is supplied by the caller as a :class:`StageWork`, because
the stage bodies belong to the packages that own them — material ingestion,
retrieval, the analysis operators — and a layer that grew its own would be a
second implementation of each of them.

The consent is the layer's own. The work is called only after the policy has
allowed the capability and any approval has been consumed, so a surface cannot
run an effect the policy would not allow, whichever surface it is.

A stage that cannot proceed is **not** an outcome of the work. ADR-0003 C2's
state machine has a state for "waiting for a human" — ``AWAITING_APPROVAL``,
reached by asking for an approval — and none for "the attempt finished without
the effect", so a stage that has to wait asks for an approval rather than
reporting a third kind of outcome. :func:`labcairn.application.approvals.request_approval`
is that path, and it parks the stage as ``BLOCKED`` with the reason on it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from labcairn.application import consent, records
from labcairn.application.approvals import spendable_approval
from labcairn.application.context import ApplicationContext, store_refusals
from labcairn.application.models import Result
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.core.ids import ApprovalId, OperationId, RunId, TaskId, new_id
from labcairn.db.repository import list_approvals, list_operations, list_runs, list_stages
from labcairn.reports.receipt import ArtifactReceipt
from labcairn.runtime.event import EventType
from labcairn.runtime.lifecycle import Run, Stage, StageStatus
from labcairn.runtime.operation import (
    Approval,
    ApprovalState,
    Operation,
    OperationState,
    compute_args_digest,
)
from labcairn.security.capabilities import CapabilityId
from labcairn.security.paths import CanonicalPath
from labcairn.security.policy import Permission
from labcairn.skills.artifacts import StageName
from labcairn.skills.declaration import SkillDeclaration, research_report_skill


@dataclass(frozen=True, slots=True)
class StageRequest:
    """One stage run: what to run, against what, and under whose consent.

    ``root_id`` and ``resource_key`` name the resource the operation
    addresses; the capability's own ``path`` argument is taken from it, so the
    arguments and the policy's verdict can never name different things.
    """

    stage_name: str
    capability: CapabilityId
    arguments: Mapping[str, Any]
    root_id: str
    resource_key: str
    run_id: RunId | None = None
    approval_id: ApprovalId | None = None
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StageOutcome:
    """What the stage's work produced.

    Two outcomes, and no third: the work either produced something, or it
    raised. **A stage that cannot proceed is not an outcome of the work** — it
    is a stage waiting for a human, and ADR-0003 C2's state machine has a
    state for that (``AWAITING_APPROVAL``, reached through
    :func:`labcairn.application.approvals.request_approval`) and none for "the
    attempt finished without the effect". A work that has to wait should ask
    for an approval rather than report a third kind of outcome.
    """

    output_hashes: tuple[str, ...] = ()
    artifacts: tuple[ArtifactReceipt, ...] = ()


class StageWork(Protocol):
    """The effect a stage performs, once the layer has authorised it.

    The work is given the canonical path the policy judged, so it cannot
    address a different file than the one that was authorised. Its own
    arguments are the caller's business — the work is a closure over whatever
    it needs, and the layer passes it the resource it may act on.
    """

    def __call__(self, resource: CanonicalPath) -> StageOutcome:
        """Do the stage's work, against *resource*."""
        ...


class TaskStep(Result):
    """One runtime stage of a task, with the run it belonged to."""

    stage: Stage
    attempt: int


class PlanStage(Result):
    """One declared stage of the workflow, and where this task is in it."""

    stage: StageName
    status: StageStatus
    blocked_reason: str | None = None


class TaskPlan(Result):
    """The declared workflow, with this task's progress through it."""

    task_id: TaskId
    skill_id: str
    skill_digest: str
    steps: tuple[PlanStage, ...]


class StageRun(Result):
    """What running a stage produced."""

    run: Run
    stage: Stage
    operation: Operation
    approval: Approval | None
    artifacts: tuple[ArtifactReceipt, ...]


def run_stage(
    context: ApplicationContext,
    request: StageRequest,
    work: StageWork,
    *,
    now: datetime | None = None,
) -> StageRun:
    """Run one stage: consent, bookkeeping, the effect, the record.

    The order is the order that makes the crash answerable, and it is the
    order the recovery layer already uses: the consent is settled **before**
    the effect, and the effect's outcome is recorded **after** it.

    :raises ApplicationRefusedError: the policy denied the capability, the
        policy asked and no approval was supplied, the approval does not cover
        this request, the approval cannot be spent at this moment, or the
        stage's work failed.
    """
    moment = now if now is not None else datetime.now(UTC)
    resource = context.resource_in(request.root_id, request.resource_key)
    authorisation = consent.evaluate(
        context,
        capability=request.capability,
        arguments=request.arguments,
        resource=resource,
    )
    digest = _args_digest(context, request, resource, authorisation.digest_arguments())

    # -- the consent --------------------------------------------------------- #
    approval: Approval | None = None
    if request.approval_id is not None:
        # The approval is read and checked *before* the ledger is spent: an
        # approval cannot be spent at a moment before it was granted, and a
        # refusal that arrived after the spend would have spent the approval
        # and refused the request at the same time.
        approval = spendable_approval(context, request.approval_id, now=moment)
        consent.consume(
            context,
            authorisation=authorisation,
            capability=request.capability,
            approval_id=request.approval_id,
            now=moment,
            depends_on=request.depends_on,
        )
    elif authorisation.permission is Permission.ASK:
        raise ApplicationRefusedError(
            ApplicationRefusal.POLICY_ASKED,
            f"the policy asked about {request.capability.value} on "
            f"{resource.resolved_key!r}, and no approval was supplied. An operation "
            "the policy asked about needs consent: ask for an approval and run the "
            "stage again with it.",
        )

    # -- the records --------------------------------------------------------- #
    run = records.ensure_run(context, request.run_id, now=moment)
    stage = records.ensure_stage(context, run, request.stage_name, now=moment)
    operation = _find_operation(context, stage, request, resource, digest)
    if operation is None:
        operation = Operation(
            operation_id=OperationId(new_id()),
            task_id=context.task_id,
            run_id=run.run_id,
            stage_id=stage.stage_id,
            state=OperationState.PLANNED,
            capability=request.capability.value,
            resource_key=resource.resolved_key,
            depends_on=request.depends_on,
            args_digest=digest,
        )
    if approval is not None:
        approval = records.move_approval(
            context,
            approval,
            event=EventType.APPROVAL_CONSUMED,
            from_state=ApprovalState.GRANTED,
            to_state=ApprovalState.CONSUMED,
            run_id=run.run_id,
            now=moment,
        )
    if operation.state is not OperationState.AUTHORIZED:
        operation = records.move_operation(
            context,
            operation,
            event=EventType.OPERATION_INTENT,
            to_state=OperationState.AUTHORIZED,
            now=moment,
        )
    operation = records.move_operation(
        context,
        operation,
        event=EventType.OPERATION_ATTEMPTED,
        to_state=OperationState.ATTEMPTING,
        now=moment,
    )

    # -- the effect ---------------------------------------------------------- #
    try:
        outcome = work(resource)
    except ApplicationRefusedError:
        records.fail_operation(context, operation, stage, now=moment)
        raise
    except Exception as error:
        records.fail_operation(context, operation, stage, now=moment)
        raise ApplicationRefusedError(
            ApplicationRefusal.STAGE_FAILED,
            f"the stage {request.stage_name!r} failed: {error}",
        ) from error

    # -- the outcome --------------------------------------------------------- #
    confirmed, completed = records.complete_operation(
        context,
        operation,
        stage,
        outcome.artifacts,
        run_id=run.run_id,
        output_hashes=outcome.output_hashes,
        now=moment,
    )
    return StageRun(
        run=run,
        stage=completed,
        operation=confirmed,
        approval=approval,
        artifacts=outcome.artifacts,
    )


def read_plan(
    context: ApplicationContext,
    *,
    declaration: SkillDeclaration | None = None,
) -> TaskPlan:
    """The declared workflow, with this task's progress through it.

    :raises ApplicationRefusedError: the policy denied reading the task's area.
    """
    area = context.task_area()
    consent.evaluate(
        context,
        capability=CapabilityId.FS_READ,
        arguments={"path": area.declared_key},
        resource=area,
    )
    graph = declaration if declaration is not None else research_report_skill()
    with store_refusals():
        stages = list_stages(context.store.session, context.task_id)

    latest: dict[str, Stage] = {}
    for stage in stages:
        latest[stage.name] = stage

    steps: list[PlanStage] = []
    for spec in graph.stages:
        recorded = latest.get(spec.stage.value)
        steps.append(
            PlanStage(
                stage=spec.stage,
                status=recorded.status if recorded is not None else StageStatus.PENDING,
                blocked_reason=recorded.blocked_reason if recorded is not None else None,
            )
        )
    return TaskPlan(
        task_id=context.task_id,
        skill_id=graph.skill_id,
        skill_digest=graph.digest(),
        steps=tuple(steps),
    )


def read_steps(context: ApplicationContext) -> tuple[TaskStep, ...]:
    """The runtime stages this task has, oldest first.

    :raises ApplicationRefusedError: the policy denied reading the task's area.
    """
    area = context.task_area()
    consent.evaluate(
        context,
        capability=CapabilityId.FS_READ,
        arguments={"path": area.declared_key},
        resource=area,
    )
    with store_refusals():
        stages = list_stages(context.store.session, context.task_id)
        runs = list_runs(context.store.session, context.task_id)
    attempts = {run.run_id: run.attempt for run in runs}
    return tuple(TaskStep(stage=stage, attempt=attempts.get(stage.run_id, 1)) for stage in stages)


def _args_digest(
    context: ApplicationContext,
    request: StageRequest,
    resource: CanonicalPath,
    digest_arguments: Mapping[str, object],
) -> str:
    """The digest the approval is bound to, computed the same way twice.

    ADR-0003 C4's digest covers the schema version, the task, the capability,
    the resource key, the arguments and the dependency hashes. It is computed
    here from the arguments **as they are right now**, and the ledger recomputes
    it at the moment of use, so an approval for one set of arguments does not
    authorise another.
    """
    try:
        return compute_args_digest(
            task_id=context.task_id,
            capability=request.capability.value,
            resource_key=resource.resolved_key,
            args=dict(digest_arguments),
            depends_on=request.depends_on,
        )
    except (TypeError, ValueError) as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the stage's arguments are not digestible: {error}",
        ) from error


def _find_operation(
    context: ApplicationContext,
    stage: Stage,
    request: StageRequest,
    resource: CanonicalPath,
    digest: str,
) -> Operation | None:
    """The operation this run is already planned as, if there is one.

    A stage run that follows an approval reuses the operation the approval
    was bound to, and a run that follows a crash reuses the operation that was
    authorised but never attempted. Two operations for one piece of work would
    make the audit log say it happened twice.

    **Only an authorised operation is one.** An operation that is still waiting
    for an approval is a question nobody has answered, and a run that adopted
    it would attempt an effect nobody authorised — and the answer, when it came,
    would arrive for an operation that had already been attempted. ADR-0003 C2
    says what a crash on such an operation means: nothing was performed, and
    the stage is resumed rather than the operation adopted.

    **The newest authorised one is taken.** The store holds operations in the
    order they were planned, and that order is the ledger's only one, so the
    choice between two of them is a fact about the record and not a preference
    of the run: the most recent plan for the work is the one that runs. It is
    not the order the authorisations happened in — an operation can be
    authorised after a later one was planned — so neither the older nor the
    newer is reliably the one that was authorised last. Two authorised
    operations for one piece of work is a state the product should not reach;
    when it does, the older is left where it was rather than adopted, and it
    stays visible in the ledger as an operation that was authorised and never
    attempted.

    """
    with store_refusals():
        operations = list_operations(context.store.session, context.task_id)
    if request.approval_id is not None:
        approvals = list_approvals(context.store.session, context.task_id)
        for approval in approvals:
            if approval.approval_id == request.approval_id:
                return next(
                    (
                        operation
                        for operation in operations
                        if operation.operation_id == approval.operation_id
                    ),
                    None,
                )
        return None
    matches = [
        operation
        for operation in operations
        if operation.stage_id == stage.stage_id
        and operation.capability == request.capability.value
        and operation.resource_key == resource.resolved_key
        and operation.args_digest == digest
        and operation.state is OperationState.AUTHORIZED
    ]
    return matches[-1] if matches else None


__all__ = [
    "PlanStage",
    "StageOutcome",
    "StageRequest",
    "StageRun",
    "StageWork",
    "TaskPlan",
    "TaskStep",
    "read_plan",
    "read_steps",
    "run_stage",
]
