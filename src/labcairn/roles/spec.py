"""A role's contract, as data — and the code that enforces it.

LC-P2-12 T00. The three roles of the guidance loop (ADR-0018) do not
work under prompts; they work under contracts that are **rows**: the
objective, the typed input and output schemas, the capabilities the role
may exercise, the actions it may not take, the purposes it may read
material for, the budgets and the routing, and the conditions under
which it abstains and under which it hands the work to a person. The
prompt is one field of it, and the least load-bearing one.

**And the spec is enforced, not read.** A role's operation asks the
spec what it may do — :meth:`AgentRoleSpec.require_allowed` for a
capability, :meth:`AgentRoleSpec.refuse_forbidden` for an action — and
each refusal carries a machine-readable reason, because a caller that
can only read a message cannot branch on it. **A contract the code
cannot check is a suggestion the code ignores**, which is how a role
that was only ever a prompt loses its boundary silently.

**The vocabularies are closed.** A capability's name is one the security
layer has registered (:class:`labcairn.security.capabilities.CapabilityId`),
and a forbidden action is one of the five the architecture names — a
sixth arrives by editing :class:`ForbiddenAction`, not by typing it into
a spec. The schema checks only that the list columns are JSON arrays;
membership is this module's refusal, stated in its docstring rather than
in a CHECK that cannot say it.

**The rows are reached through the application layer.** Every read and
every write of ``agent_role_specs`` goes through
:mod:`labcairn.application.roles`, so the contracts are reached in one
place and a guard applied there reaches every caller. **The rules about
the words stay here**: the fields that may not be empty, the capability
the security layer has not registered, the forbidden action outside the
closed five, the purpose that was not declared, and the ceilings that
were set to zero. The layer holds the row; this module holds what may be
said about it.

**And the contract itself is data, in :mod:`labcairn.roles.models`.** The
types live below the layer and below this module, because both of them
answer with a contract and neither may import the other back.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from labcairn.application import roles as roles_layer
from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import role_refused
from labcairn.roles.models import (
    FORBIDDEN_ACTIONS,
    AgentRoleSpec,
    ForbiddenAction,
    RoleOutput,
)
from labcairn.roles.refusals import RoleRefusal
from labcairn.security.capabilities import CapabilityId

__all__ = [
    "FORBIDDEN_ACTIONS",
    "AgentRoleSpec",
    "ForbiddenAction",
    "RoleOutput",
    "define_role_spec",
    "load_spec",
]


def _text(*, value: str, reason: RoleRefusal, what: str) -> str:
    """A required text field, or the refusal."""
    if not value.strip():
        raise role_refused(reason, f"the spec's {what} is empty")
    return value


def _lists(
    *,
    capabilities: Sequence[CapabilityId],
    forbidden: Sequence[ForbiddenAction],
    purposes: Sequence[str],
) -> tuple[tuple[CapabilityId, ...], tuple[ForbiddenAction, ...], tuple[str, ...]]:
    """The contract's list clauses, each item checked against its vocabulary.

    :raises ApplicationRefusedError: a capability is not one the security
        layer registered, a forbidden action is not one of the five, or
        no data purpose was declared.
    """
    for capability in capabilities:
        if not isinstance(capability, CapabilityId):
            raise role_refused(
                RoleRefusal.SPEC_CAPABILITY_UNKNOWN,
                f"{capability!r} is not a capability the security layer has registered",
            )
    if not capabilities:
        raise role_refused(
            RoleRefusal.SPEC_CAPABILITY_UNKNOWN,
            "a spec that names no capability grants nothing, which is not a"
            " contract but an empty box",
        )
    for action in forbidden:
        if not isinstance(action, ForbiddenAction):
            raise role_refused(
                RoleRefusal.SPEC_FORBIDDEN_ACTION_UNKNOWN,
                f"{action!r} is not one of the five forbidden actions the architecture closes",
            )
    if not purposes:
        raise role_refused(
            RoleRefusal.SPEC_PURPOSE_EMPTY,
            "a role that may read material for no purpose may read it for any,"
            " which is not a grant",
        )
    return (
        tuple(capabilities),
        tuple(forbidden),
        tuple(purpose.strip() for purpose in purposes),
    )


def define_role_spec(
    context: ApplicationContext,
    *,
    role_id: str,
    role_version: int,
    objective: str,
    input_schema: str,
    output_schema: str,
    allowed_capabilities: Sequence[CapabilityId],
    forbidden_actions: Sequence[ForbiddenAction],
    allowed_data_purposes: Sequence[str],
    provider_routing_policy: str,
    cost_budget: float | None,
    token_budget: int,
    timeout_seconds: int,
    retry_policy: str,
    fallback_policy: str,
    abstain_conditions: Sequence[str],
    escalation_conditions: Sequence[str],
    prompt_template_version: str,
    model_config_ref: str,
    now: datetime,
) -> AgentRoleSpec:
    """Define a role's contract, as a versioned row.

    Every field is checked here, by name: the vocabulary of each list
    against its closed enum, the required texts against emptiness, the
    ceilings against a zero. **A contract the API would write but the
    schema would refuse is a bug caught before the commit, not after.**

    :raises ApplicationRefusedError: a required field is empty; a
        capability is not registered; a forbidden action is not one of
        the five; no data purpose was declared; the version is not at
        least one; or the role and version are already defined.
    """
    checked_id = _text(value=role_id, reason=RoleRefusal.SPEC_FIELD_EMPTY, what="role id")
    checked_objective = _text(
        value=objective, reason=RoleRefusal.SPEC_FIELD_EMPTY, what="objective"
    )
    checked_input = _text(
        value=input_schema, reason=RoleRefusal.SPEC_FIELD_EMPTY, what="input schema"
    )
    checked_output = _text(
        value=output_schema, reason=RoleRefusal.SPEC_FIELD_EMPTY, what="output schema"
    )
    checked_routing = _text(
        value=provider_routing_policy,
        reason=RoleRefusal.SPEC_FIELD_EMPTY,
        what="provider routing policy",
    )
    checked_retry = _text(
        value=retry_policy, reason=RoleRefusal.SPEC_FIELD_EMPTY, what="retry policy"
    )
    checked_fallback = _text(
        value=fallback_policy, reason=RoleRefusal.SPEC_FIELD_EMPTY, what="fallback policy"
    )
    checked_prompt = _text(
        value=prompt_template_version,
        reason=RoleRefusal.SPEC_FIELD_EMPTY,
        what="prompt template version",
    )
    checked_config = _text(
        value=model_config_ref, reason=RoleRefusal.SPEC_FIELD_EMPTY, what="model config"
    )
    if role_version < 1:
        raise role_refused(
            RoleRefusal.SPEC_FIELD_EMPTY,
            "a contract binds from version one, and a version below one was named",
        )
    if token_budget <= 0 or timeout_seconds <= 0:
        raise role_refused(
            RoleRefusal.SPEC_FIELD_EMPTY,
            "a role works under a ceiling, and a zero was named for one of them",
        )
    capabilities, forbidden, purposes = _lists(
        capabilities=allowed_capabilities,
        forbidden=forbidden_actions,
        purposes=allowed_data_purposes,
    )
    if not abstain_conditions:
        raise role_refused(
            RoleRefusal.SPEC_FIELD_EMPTY,
            "a role that cannot say “I do not know” is a role that will"
            " guess; the abstain conditions are the contract's, and they are"
            " not empty",
        )
    return roles_layer.write_role_spec(
        context,
        roles_layer.RoleSpecDraft(
            role_id=checked_id,
            role_version=role_version,
            objective=checked_objective,
            input_schema=checked_input,
            output_schema=checked_output,
            allowed_capabilities=capabilities,
            forbidden_actions=forbidden,
            allowed_data_purposes=purposes,
            provider_routing_policy=checked_routing,
            cost_budget=cost_budget,
            token_budget=token_budget,
            timeout_seconds=timeout_seconds,
            retry_policy=checked_retry,
            fallback_policy=checked_fallback,
            abstain_conditions=tuple(abstain_conditions),
            escalation_conditions=tuple(escalation_conditions),
            prompt_template_version=checked_prompt,
            model_config_ref=checked_config,
            defined_at=now,
        ),
    )


def load_spec(
    context: ApplicationContext, *, role_id: str, version: int | None = None
) -> AgentRoleSpec:
    """The contract a role works under — the version named, or the highest.

    :raises ApplicationRefusedError: no row carries that role id, at the
        version named or at any version.
    """
    return roles_layer.read_role_spec(context, role_id=role_id, version=version)
