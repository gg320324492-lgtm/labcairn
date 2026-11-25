"""The capability model, applied once, in one place.

Every operation in this layer goes through the same three steps, and they
happen here rather than in each operation:

1. **The capability's arguments are validated against its closed model.**
   :func:`~labcairn.security.capabilities.parse_args` rejects an unrecognised
   key and names it, because an unrecognised key is a typo or a newer caller
   and both deserve to be loud.

2. **The resource is admitted and the policy is asked about it.**
   :meth:`~labcairn.security.policy.PermissionPolicy.evaluate` is the only
   function that makes a verdict, and its verdict is the same whatever called
   it — which is the whole point of a layer that three surfaces share.

3. **The approval is consumed, with the arguments' digest recomputed.**
   :meth:`~labcairn.security.approval.ApprovalLedger.consume` re-derives the
   digest from the arguments *as they are right now* and compares it with the
   one the approval carries. A check that trusted the stored digest would be
   satisfied by any row at all.

The path in the arguments is not the caller's to choose
-------------------------------------------------------

Every argument model in the registry carries exactly one ``path``, and the
layer sets it from the resource the operation addresses. A caller that could
put a different path in the arguments than the one the policy judged could
have the policy say yes about ``report.md`` while the operation went on to
touch something else — so the two are the same value by construction, and a
caller that passes its own ``path`` has it overwritten rather than honoured.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.core.ids import ApprovalId
from labcairn.security.approval import (
    ApprovalGrant,
    AuthorizationRefusedError,
    NoSuchApprovalError,
)
from labcairn.security.capabilities import (
    CapabilityId,
    UnknownArgumentKeyError,
    UnknownCapabilityError,
    parse_args,
)
from labcairn.security.paths import CanonicalPath
from labcairn.security.policy import Permission, PermissionDecision, ResourceRef


@dataclass(frozen=True, slots=True)
class Authorisation:
    """What the policy said, and what it was said about.

    The validated arguments are carried with the decision because the two are
    one fact: an approval is bound to the arguments, and the digest has to be
    computed from the same mapping at grant time and at the moment of use.
    """

    arguments: BaseModel
    resource: CanonicalPath
    decision: PermissionDecision

    @property
    def permission(self) -> Permission:
        """The verdict. Never DENY — that is a refusal, not an authorisation."""
        return self.decision.permission

    def digest_arguments(self) -> dict[str, object]:
        """The mapping the approval's digest is computed over.

        The canonical JSON form of the validated arguments, so two spellings of
        the same call produce the same digest and a different call produces a
        different one.
        """
        return _digest_arguments(self.arguments)


@dataclass(frozen=True, slots=True)
class Verdict:
    """The policy's answer, and what it was said about.

    **Not an authorisation.** A ``DENY`` is a refusal, and this is the shape
    that can carry one: the caller decides what a denial means for it. This
    layer's :func:`evaluate` turns it into a refusal, and the stage layer
    turns it into a denial that is *recorded* before the refusal is raised.

    The decision is carried whole rather than as its prose, because the reason
    the permission layer produced — a
    :class:`~labcairn.security.policy.DecisionReason` — has to reach the
    record, and a sentence about it cannot be told apart from any other
    sentence.
    """

    arguments: BaseModel
    resource: CanonicalPath
    decision: PermissionDecision

    @property
    def denied(self) -> bool:
        """Whether the policy refused this request outright."""
        return self.decision.permission is Permission.DENY

    @property
    def authorisation(self) -> Authorisation:
        """The verdict as an authorisation. A ``DENY`` has none."""
        if self.denied:
            raise ValueError("a DENY verdict is a refusal, not an authorisation")
        return Authorisation(
            arguments=self.arguments,
            resource=self.resource,
            decision=self.decision,
        )

    def digest_arguments(self) -> dict[str, object]:
        """The mapping the approval's digest is computed over."""
        return _digest_arguments(self.arguments)


def _digest_arguments(arguments: BaseModel) -> dict[str, object]:
    """The canonical JSON form of the validated arguments.

    Shared by :class:`Authorisation` and :class:`Verdict` so the two spellings
    of the same mapping cannot drift: an approval's digest and a denial's
    record are computed over one thing, not two.
    """
    payload = arguments.model_dump(mode="json")
    try:
        json.dumps(payload, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the capability's arguments are not JSON: {error}. A digest over them "
            "could not be reproduced by another reader.",
        ) from error
    return dict(payload)


def decide(
    context: ApplicationContext,
    *,
    capability: CapabilityId,
    arguments: Mapping[str, Any],
    resource: CanonicalPath,
) -> Verdict:
    """The capability's arguments validated, and the policy's verdict on the resource.

    **The verdict is returned, not raised.** A ``DENY`` is a refusal, and a
    refusal has two consequences — it stops the caller, and it is a fact worth
    recording — and only the caller can say which of them it wants.
    :func:`evaluate` is the raising form every other caller uses; the stage
    layer calls this one, so it can record the denial and *then* refuse.

    :raises ApplicationRefusedError: the arguments are not usable.
    """
    try:
        parsed = parse_args(capability, {**arguments, "path": resource.declared_key})
    except UnknownArgumentKeyError as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            str(error),
        ) from error
    except UnknownCapabilityError as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            str(error),
        ) from error
    except ValidationError as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the {capability.value} arguments are not usable: {error}",
        ) from error

    decision = context.policy.evaluate(
        task_id=context.task_id,
        capability=capability.value,
        resource=ResourceRef.from_canonical(resource),
    )
    return Verdict(arguments=parsed, resource=resource, decision=decision)


def permission_denied(
    decision: PermissionDecision,
    *,
    capability: CapabilityId,
    resource: CanonicalPath,
) -> ApplicationRefusedError:
    """The refusal a ``DENY`` becomes.

    One place builds it, so the refusal a caller sees is the same refusal
    whoever raised it: the reason the permission layer produced is in the
    message, and the rule that produced it is named when there was one.
    """
    return ApplicationRefusedError(
        ApplicationRefusal.PERMISSION_DENIED,
        f"the policy denied {capability.value} on {resource.resolved_key!r}: "
        f"{decision.reason.value}"
        + (f" (rule: {decision.matched_rule})" if decision.matched_rule else ""),
    )


def evaluate(
    context: ApplicationContext,
    *,
    capability: CapabilityId,
    arguments: Mapping[str, Any],
    resource: CanonicalPath,
) -> Authorisation:
    """The capability's arguments validated, and the policy's verdict on the resource.

    :raises ApplicationRefusedError: the arguments are not usable, or the policy
        denied the request.
    """
    verdict = decide(
        context,
        capability=capability,
        arguments=arguments,
        resource=resource,
    )
    if verdict.denied:
        raise permission_denied(verdict.decision, capability=capability, resource=resource)
    return verdict.authorisation


def evaluate_all(
    context: ApplicationContext,
    *,
    capability: CapabilityId,
    arguments: Mapping[str, Any],
    resources: Sequence[CanonicalPath],
) -> tuple[Authorisation, ...]:
    """The capability evaluated on **every one** of *resources*.

    **And all of them, not the first that passes.** An operation that
    reads a whole project reads every manuscript in it, and a policy that
    denies one of them denies the reading. A listing that quietly omitted
    the denied material would be a listing nobody can trust, and a chain
    that showed one round of a manuscript and not another would be a chain
    that says the rest of the story was answered.

    **The first denial is raised as it stands**, so the caller learns
    which resource was refused rather than that "something" was.

    :raises ApplicationRefusedError: the arguments are not usable, or the
        policy denied one of the resources.
    """
    return tuple(
        evaluate(
            context,
            capability=capability,
            arguments=arguments,
            resource=resource,
        )
        for resource in resources
    )


def evaluate_each(
    context: ApplicationContext,
    *,
    capability: CapabilityId,
    arguments: Mapping[str, Any],
    resources: Sequence[CanonicalPath],
) -> tuple[CanonicalPath, ...]:
    """The resources the policy permits, **and only those**.

    **Denied resources are dropped, not refused.** ADR-0003 C5 asks a bulk
    listing to filter denied entries out of its results rather than
    refusing the call, because refusing the whole listing discloses that
    something is there and denies work the operator wanted allowed.

    **And a failure that is not a denial is still raised.** A path that
    cannot be admitted, or arguments that do not make sense, are faults
    rather than permissions — and dropping them would hide a broken call
    behind a short list.
    """
    permitted: list[CanonicalPath] = []
    for resource in resources:
        try:
            evaluate(
                context,
                capability=capability,
                arguments=arguments,
                resource=resource,
            )
        except ApplicationRefusedError as error:
            if error.reason is ApplicationRefusal.PERMISSION_DENIED:
                continue
            raise
        permitted.append(resource)
    return tuple(permitted)


def consume(
    context: ApplicationContext,
    *,
    authorisation: Authorisation,
    capability: CapabilityId,
    approval_id: ApprovalId,
    now: datetime,
    depends_on: tuple[str, ...] = (),
    resolve_source: Callable[[str], Path] | None = None,
) -> ApprovalGrant:
    """The approval, consumed — or a refusal naming why not.

    The digest is **recomputed** here from the arguments as they are right now
    and compared with the one the approval carries. A check that trusted the
    stored digest would be satisfied by any row at all, since whoever can write
    a row can write its digest.

    **``resolve_source`` says where the bound material lives.** The default
    resolves a bound source against the root of the resource being written,
    which is right for every effect that reads and writes the same root — and
    wrong for one that copies *from* a source root *into* the output area:
    there, resolving the original against the output root would hash a file
    that is not the original, or fail to find it, and ``SOURCE_CHANGED`` would
    be reported for material that never moved. A caller that knows which root
    its material lives in says so; guessing from the write target is how a
    re-hash becomes a fiction.

    :raises ApplicationRefusedError: no such approval, or one that does not
        cover this request.
    """
    root_id = authorisation.resource.root_id
    resolver = resolve_source or (lambda key: context.workspace.path_in(key, root_id).real_path)
    try:
        return context.ledger.consume(
            approval_id,
            now=now,
            task_id=context.task_id,
            capability=capability.value,
            resource=authorisation.resource,
            args=authorisation.digest_arguments(),
            depends_on=depends_on,
            current_policy_digest=context.policy.digest(),
            resolve_source=resolver,
        )
    except NoSuchApprovalError as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.APPROVAL_MISSING,
            f"no approval {approval_id} was issued, or it has already been consumed. "
            "An operation without an approval is an operation nobody agreed to.",
        ) from error
    except AuthorizationRefusedError as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.APPROVAL_REFUSED,
            f"the approval does not cover this request: {error.refusal.value}. "
            f"{error.args[0] if error.args else ''}".strip(),
        ) from error


__all__ = [
    "Authorisation",
    "Verdict",
    "consume",
    "decide",
    "evaluate",
    "evaluate_all",
    "evaluate_each",
    "permission_denied",
]
