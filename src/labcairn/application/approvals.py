"""Consent: asking for it, granting it, and spending it.

Three operations, and the middle one is the one that makes the other two
meaningful.

**Asking** (:func:`request_approval`) plans the operation the consent is for
and records a **pending** approval bound to it. Nothing is authorised yet: a
pending approval is a question that has been put, and a question that nobody
answered is not consent.

**Granting** (:func:`grant_approval`) records the human's answer. It is a
separate operation because the answer and the question are different events,
and only one of them is the system's to make: a surface that could grant an
approval on the user's behalf would be a surface that grants itself a
permission the other surfaces would not.

**Spending** (:func:`consume_approval`) is the act of using a granted
approval for one specific request. It is single-use by construction — the
ledger's own accounting moves the approval to ``CONSUMED`` — and the digest
is recomputed at the moment of use, so an approval for one set of arguments
does not authorise another.

What the approval is bound to
-----------------------------

ADR-0003 C4: the capability, the resource key and the **arguments digest**,
inside the task's scope. The digest covers the dependency hashes as well, so
an approval for material whose bytes have changed does not authorise the new
bytes. The file on disk is not re-hashed here: the layer binds no files, and
the hash in the digest is the binding. A layer that re-hashed files would have
to know which root each file lives in, and a task's materials and a task's
outputs do not live in the same one.

The window
----------

An approval is good for a moment and not for ever, and **the layer is where
that is said**. The store holds the rule as a constraint —
``granted_at IS NULL OR expires_at > granted_at`` — and the constraint is
right, but a constraint refuses in the only language it has: a raw
``IntegrityError`` out of the middle of the transaction. A client whose
question has gone stale would learn that the service is broken rather than
that its answer is too late.

So the layer asks the :class:`~labcairn.runtime.operation.Approval` model
instead, and translates what the model says into the one refusal this layer
raises. **The model is asked rather than the rule written out again here**,
because the two constraints are the model's own two rules, and a rule stated
twice is a rule that drifts. It is asked through
:meth:`~labcairn.runtime.operation.Approval.model_validate` rather than
``model_copy``, because ``model_copy`` does not run the validators — which is
how a row the database refuses ever reached the database at all.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from labcairn.application import consent, records
from labcairn.application.context import ApplicationContext, store_refusals
from labcairn.application.models import Result
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.core.ids import ApprovalId, OperationId, RunId, new_id
from labcairn.db.repository import list_approvals, list_operations, list_runs
from labcairn.runtime.event import EventType
from labcairn.runtime.operation import (
    Approval,
    ApprovalState,
    Operation,
    OperationState,
    compute_args_digest,
)
from labcairn.security.approval import ApprovalGrant, make_approval
from labcairn.security.capabilities import CapabilityId


@dataclass(frozen=True, slots=True)
class ApprovalUse:
    """What an approval is spent on.

    The same shape as the operation that consumes it, so the arguments and the
    resource can be handed over without either side being re-derived.
    """

    capability: CapabilityId
    arguments: Mapping[str, Any]
    root_id: str
    resource_key: str
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    """An approval asked for: what it covers, and when it lapses.

    ``run_id`` and ``stage_name`` say where the operation lives; an approval
    belongs to an operation, and an operation belongs to a stage inside a run.
    """

    use: ApprovalUse
    expires_at: datetime
    run_id: RunId | None = None
    stage_name: str = "approval"


class ApprovalRequested(Result):
    """An approval that has been asked for, and the operation it is for."""

    operation: Operation
    approval: Approval


class ApprovalGranted(Result):
    """An approval the human has granted."""

    approval: Approval


class ApprovalConsumed(Result):
    """An approval that has been spent, and the operation it authorised."""

    approval: Approval
    operation: Operation | None


def request_approval(
    context: ApplicationContext,
    request: ApprovalRequest,
    *,
    now: datetime | None = None,
) -> ApprovalRequested:
    """Plan the operation and put the question.

    The operation is recorded as ``AWAITING_APPROVAL`` and the approval as
    ``PENDING``, in one transaction, so an audit log cannot show an approval
    that was asked for without the operation it was asked for.

    :raises ApplicationRefusedError: the policy denied the capability, so
        there is nothing to ask consent about.
    """
    moment = now if now is not None else datetime.now(UTC)
    use = request.use
    resource = context.resource_in(use.root_id, use.resource_key)
    authorisation = consent.evaluate(
        context,
        capability=use.capability,
        arguments=use.arguments,
        resource=resource,
    )
    digest_arguments = authorisation.digest_arguments()
    try:
        digest = compute_args_digest(
            task_id=context.task_id,
            capability=use.capability.value,
            resource_key=resource.resolved_key,
            args=digest_arguments,
            depends_on=use.depends_on,
        )
    except (TypeError, ValueError) as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the approval's arguments are not digestible: {error}",
        ) from error

    run = records.ensure_run(context, request.run_id, now=moment)
    stage = records.ensure_stage(context, run, request.stage_name, now=moment)
    operation = Operation(
        operation_id=OperationId(new_id()),
        task_id=context.task_id,
        run_id=run.run_id,
        stage_id=stage.stage_id,
        state=OperationState.PLANNED,
        capability=use.capability.value,
        resource_key=resource.resolved_key,
        depends_on=use.depends_on,
        args_digest=digest,
    )
    approval = make_approval(
        task_id=context.task_id,
        operation_id=operation.operation_id,
        capability=use.capability.value,
        resource=resource,
        args=digest_arguments,
        depends_on=use.depends_on,
        expires_at=request.expires_at,
    )
    awaiting, pending, _blocked = records.plan_approval(
        context,
        operation,
        approval,
        stage,
        f"awaiting approval for {use.capability.value} on {resource.resolved_key!r}",
        run_id=run.run_id,
        now=moment,
    )
    return ApprovalRequested(operation=awaiting, approval=pending)


def grant_approval(
    context: ApplicationContext,
    approval_id: ApprovalId,
    *,
    now: datetime | None = None,
) -> ApprovalGranted:
    """Record the human's answer, and put the approval in the ledger.

    The grant is bound to the policy as it stands now, because ADR-0003 C4
    requires *the policy snapshot still equals current policy* — the digest of
    the policy at grant time is kept beside the approval and compared when the
    approval is spent.

    **An answer to a question that has gone stale is refused.** The approval
    carries the window it was asked for, and a grant stamped after that window
    closed records an answer to a question nobody is asking any more. The
    refusal names the approval and the moment its window closed, because
    "your approval expired" is only actionable if it says *which* one.

    :raises ApplicationRefusedError: no such approval, one that is not
        waiting for an answer, or one whose window has closed.
    """
    moment = now if now is not None else datetime.now(UTC)
    approval = _approval_row(context, approval_id)
    if approval.state is not ApprovalState.PENDING:
        raise ApplicationRefusedError(
            ApplicationRefusal.APPROVAL_REFUSED,
            f"the approval {approval_id} is {approval.state.value}, and an approval "
            "that is not waiting for an answer cannot be granted. A spent approval "
            "never authorises a second effect (ADR-0003 C4).",
        )
    granted = _granted(approval, moment)
    operation = _operation_row(context, approval)
    # **The policy's answer is written down now, because the spend must not be
    # the one that says what the policy was.** LC-P2-02 §2.2: the row keeps
    # what the policy said at the grant, and the spend compares it with what
    # the policy says at the moment of use. A grant that recorded no digest
    # would leave the spend comparing nothing with nothing.
    digest = context.policy.digest()
    granted = granted.model_copy(update={"grant_policy_digest": digest})
    context.ledger.issue(ApprovalGrant(approval=granted, policy_digest=digest))
    recorded = records.move_approval(
        context,
        granted,
        event=EventType.APPROVAL_GRANTED,
        from_state=ApprovalState.PENDING,
        to_state=ApprovalState.GRANTED,
        run_id=operation.run_id if operation is not None else _run_of(context, approval),
        now=moment,
    )
    return ApprovalGranted(approval=recorded)


def consume_approval(
    context: ApplicationContext,
    approval_id: ApprovalId,
    use: ApprovalUse,
    *,
    now: datetime | None = None,
) -> ApprovalConsumed:
    """Spend a granted approval on one specific request.

    The digest is recomputed from the arguments as they are right now, and
    compared with the one the approval carries. The approval is spent even if
    the operation that follows fails, because re-asking a human is cheap and
    repeating a side effect is not.

    **The row is read and checked before anything is spent.** An approval
    cannot be spent at a moment before it was granted, and the ledger is spent
    by the call below — so a refusal that arrived afterwards would have spent
    the approval and refused the request at the same time.

    :raises ApplicationRefusedError: no such approval, or one that does not
        cover this request.
    """
    moment = now if now is not None else datetime.now(UTC)
    resource = context.resource_in(use.root_id, use.resource_key)
    authorisation = consent.evaluate(
        context,
        capability=use.capability,
        arguments=use.arguments,
        resource=resource,
    )
    spent = spendable_approval(context, approval_id, now=moment)
    consent.consume(
        context,
        authorisation=authorisation,
        capability=use.capability,
        approval_id=approval_id,
        now=moment,
        depends_on=use.depends_on,
    )
    operation = _operation_row(context, spent)
    run_id = operation.run_id if operation is not None else _run_of(context, spent)
    consumed = records.move_approval(
        context,
        spent,
        event=EventType.APPROVAL_CONSUMED,
        from_state=ApprovalState.GRANTED,
        to_state=ApprovalState.CONSUMED,
        run_id=run_id,
        now=moment,
    )
    authorised: Operation | None = None
    if operation is not None and operation.state is OperationState.AWAITING_APPROVAL:
        authorised = records.move_operation(
            context,
            operation,
            event=EventType.OPERATION_INTENT,
            to_state=OperationState.AUTHORIZED,
            now=moment,
        )
    return ApprovalConsumed(approval=consumed, operation=authorised)


def _granted(approval: Approval, moment: datetime) -> Approval:
    """The approval as it is granted, or a refusal naming the window that closed.

    **The model is asked, and its answer is translated.** The
    :class:`~labcairn.runtime.operation.Approval` model's own rule — the window
    must outlive the grant — is the layer's copy of the store's
    ``ck_approvals_expiry_after_grant``, and asking the model keeps the two
    from drifting apart. It is asked through
    :meth:`~labcairn.runtime.operation.Approval.model_validate` rather than
    ``model_copy``, because ``model_copy`` does not run the validators, and
    that is how a row the database refuses ever reached the database.

    The only rule a pending approval can fail is the window's: it has no grant
    and no consumption, so the message below is true of every refusal this
    raises.
    """
    try:
        return Approval.model_validate(
            {**approval.model_dump(), "state": ApprovalState.GRANTED, "granted_at": moment}
        )
    except ValidationError as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.APPROVAL_REFUSED,
            f"the approval {approval.approval_id} expired at "
            f"{approval.expires_at.isoformat()}, and an approval whose window has "
            "closed cannot be granted. The answer is about a question that has "
            "gone stale: ask for another approval.",
        ) from error


def _spent(approval: Approval, moment: datetime) -> Approval:
    """The approval as it is spent, or a refusal naming the impossible order.

    **The model is asked, and its answer is translated**, for the reason
    :func:`_granted` asks it: the model's rule — a consumption must not
    precede the grant — is the layer's copy of the store's
    ``ck_approvals_consume_after_grant``, and ``model_copy`` would not have
    run it.

    An approval granted at one moment cannot be spent at a moment before it:
    the grant is the moment the approval came into being, and there is
    nothing to spend before then. The refusal names the approval and the two
    moments, because a caller that has been told "refused" and nothing else
    cannot tell a stale approval from a mis-stamped one.
    """
    try:
        return Approval.model_validate(
            {**approval.model_dump(), "state": ApprovalState.CONSUMED, "consumed_at": moment}
        )
    except ValidationError as error:
        granted_at = approval.granted_at
        detail = (
            f"the approval {approval.approval_id} was granted at "
            f"{granted_at.isoformat() if granted_at is not None else 'an unrecorded moment'}, "
            f"and it cannot be spent at {moment.isoformat()}, which is before that. "
            "An approval cannot be spent before it was granted."
        )
        raise ApplicationRefusedError(ApplicationRefusal.APPROVAL_REFUSED, detail) from error


def spendable_approval(
    context: ApplicationContext,
    approval_id: ApprovalId,
    *,
    now: datetime,
) -> Approval:
    """The approval as it would be spent, or a refusal naming why it cannot be.

    **The row is read and checked before anything is spent.** An approval
    cannot be spent at a moment before it was granted: the grant is the
    moment the approval came into being, and there is nothing to spend
    before then. The ledger is spent by the call that authorises the
    request, so a refusal that arrived afterwards would have spent the
    approval and refused the request at the same time — the approval would
    be gone and the work would not have happened, and neither record would
    say so.

    **The model is asked, and its answer is translated**, for the reason
    :func:`_granted` gives: the model's rule — a consumption must not
    precede the grant — is the layer's copy of the store's
    ``ck_approvals_consume_after_grant``, and ``model_copy`` does not run
    the validators, so the rule has to be asked of the model rather than
    assumed.

    The row read here is one the store holds, and the store holds it under
    ``ck_approvals_expiry_after_grant``, so the model's other rule — the
    window must outlive the grant — cannot be the one that refuses, and the
    message is true of every refusal this raises.
    """
    return _spent(_approval_row(context, approval_id), now)


def _approval_row(context: ApplicationContext, approval_id: ApprovalId) -> Approval:
    """The approval the store holds, or a refusal naming that it holds none."""
    with store_refusals():
        approvals = list_approvals(context.store.session, context.task_id)
    for approval in approvals:
        if approval.approval_id == approval_id:
            return approval
    raise ApplicationRefusedError(
        ApplicationRefusal.APPROVAL_MISSING,
        f"the store holds no approval {approval_id} for this task.",
    )


def _operation_row(context: ApplicationContext, approval: Approval) -> Operation | None:
    """The operation the approval was asked for, if the store still holds it."""
    with store_refusals():
        operations = list_operations(context.store.session, context.task_id)
    for operation in operations:
        if operation.operation_id == approval.operation_id:
            return operation
    return None


def _run_of(context: ApplicationContext, approval: Approval) -> RunId:
    """A run to name an approval event under.

    Approval events are run-scoped, so one has to be named. The operation the
    approval was asked for is the authority; when the store does not hold it,
    the task's newest run is used, so the event is still attached to a run
    rather than refused for want of one.
    """
    with store_refusals():
        runs = list_runs(context.store.session, context.task_id)
    if not runs:
        raise ApplicationRefusedError(
            ApplicationRefusal.OPERATION_NOT_FOUND,
            f"the approval {approval.approval_id} names an operation the store does "
            "not hold, and the task has no run to record it under.",
        )
    return runs[-1].run_id


__all__ = [
    "ApprovalConsumed",
    "ApprovalGranted",
    "ApprovalRequest",
    "ApprovalRequested",
    "ApprovalUse",
    "consume_approval",
    "grant_approval",
    "request_approval",
    "spendable_approval",
]
