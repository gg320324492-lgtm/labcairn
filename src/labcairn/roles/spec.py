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
membership is this module's refusal, stated in its docstring rather
than in a CHECK that cannot say it.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import role_refused
from labcairn.db.models import AgentRoleSpecRow
from labcairn.roles.refusals import RoleRefusal
from labcairn.security.capabilities import CapabilityId


class ForbiddenAction(StrEnum):
    """An action a role's contract forbids.

    The five the architecture names, closed. A role that could modify a
    manuscript, write an artefact without consent, execute code, approve
    its own outbound transfer, or raise a claim to a verified state
    would not be a role working under a contract — it would be the
    manuscript's author, the archivist, the operator and the reviewer at
    once, and every gate the repository has would sit behind it.
    """

    #: The manuscript is a person's to change. A role proposes; the file
    #: does not move by the role's hand.
    MODIFY_A_MANUSCRIPT = "modify_a_manuscript"
    #: Output lands where the consent layer says it may land, and
    #: nowhere else.
    WRITE_AN_ARTEFACT_WITHOUT_CONSENT = "write_an_artefact_without_consent"
    #: A role reasons over text; it does not run the machine it runs on.
    EXECUTE_CODE = "execute_code"
    #: The outbound transfer's approval is a person's act, recorded
    #: before the bytes leave — never the requester's own.
    APPROVE_AN_OUTBOUND_TRANSFER = "approve_an_outbound_transfer"
    #: A verified state is something a check earned. A role's word does
    #: not earn one, and ADR-0016 D4 makes the record's constructor say
    #: so in code as well.
    RAISE_A_VERIFIED_STATE = "raise_a_verified_state"


#: The actions no role may take, closed (ADR-0018's D1 list). The list
#: exists so the code can check it; a sixth action arrives by editing
#: :class:`ForbiddenAction`, not by typing it into a spec.
FORBIDDEN_ACTIONS: Final[tuple[ForbiddenAction, ...]] = (
    ForbiddenAction.MODIFY_A_MANUSCRIPT,
    ForbiddenAction.WRITE_AN_ARTEFACT_WITHOUT_CONSENT,
    ForbiddenAction.EXECUTE_CODE,
    ForbiddenAction.APPROVE_AN_OUTBOUND_TRANSFER,
    ForbiddenAction.RAISE_A_VERIFIED_STATE,
)


@dataclass(frozen=True)
class AgentRoleSpec:
    """The contract in memory, read from its row.

    The fields are ADR-0018's D1 list. ``input_schema`` and
    ``output_schema`` name **typed models** in the code — the output one
    every role's output type answers to by carrying
    :class:`RoleOutput` — because a schema described in prose is a
    schema nothing validates.
    """

    role_id: str
    role_version: int
    objective: str
    input_schema: str
    output_schema: str
    allowed_capabilities: tuple[CapabilityId, ...]
    forbidden_actions: tuple[ForbiddenAction, ...]
    allowed_data_purposes: tuple[str, ...]
    provider_routing_policy: str
    cost_budget: float | None
    token_budget: int
    timeout_seconds: int
    retry_policy: str
    fallback_policy: str
    abstain_conditions: tuple[str, ...]
    escalation_conditions: tuple[str, ...]
    prompt_template_version: str
    model_config_ref: str

    def allows(self, capability: CapabilityId) -> bool:
        """Whether the contract lists the capability.

        The list is the whole of it: a capability the spec does not
        name is a capability the role does not have, whatever a prompt
        once said about being careful.
        """
        return capability in self.allowed_capabilities

    def require_allowed(self, capability: CapabilityId) -> None:
        """Refuse, with a machine-readable reason, a capability not listed.

        Every operation that reaches outside the process asks this
        before it asks anything else.

        :raises ApplicationRefusedError: the capability is not one the
            contract lists.
        """
        if not self.allows(capability):
            raise role_refused(
                RoleRefusal.SPEC_CAPABILITY_NOT_LISTED,
                f"the role {self.role_id!r} at version {self.role_version} lists"
                f" {[item.value for item in self.allowed_capabilities]}, and"
                f" {capability.value!r} is not one of them",
            )

    def require_allowed_by_name(self, capability: str) -> None:
        """Refuse a capability named as a string, the way an operation names it.

        A name the security layer never registered is refused with its own
        reason before the contract's list is consulted, so a misspelling
        arrives as *unknown* rather than as *not listed*.

        :raises ApplicationRefusedError: the name is not a registered
            capability, or the contract does not list it.
        """
        try:
            registered = CapabilityId(capability)
        except ValueError:
            raise role_refused(
                RoleRefusal.SPEC_CAPABILITY_UNKNOWN,
                f"{capability!r} is not a capability the security layer has registered",
            ) from None
        self.require_allowed(registered)

    def forbids(self, action: ForbiddenAction) -> bool:
        """Whether the contract forbids the action."""
        return action in self.forbidden_actions

    def refuse_forbidden(self, action: ForbiddenAction) -> None:
        """Refuse, with a machine-readable reason, an action the spec forbids.

        :raises ApplicationRefusedError: the action is one the contract
            forbids.
        """
        if self.forbids(action):
            raise role_refused(
                RoleRefusal.SPEC_FORBIDDEN_ACTION_REQUESTED,
                f"the role {self.role_id!r} at version {self.role_version} forbids"
                f" {action.value!r}, and the operation asked for it",
            )


@dataclass(frozen=True)
class RoleOutput:
    """The typed base every role's output carries.

    **A1: the contract is versioned, and the version is on every output
    it produces.** An output that does not say which contract governed
    it cannot be replayed against that contract, so the pair is not
    metadata a caller may forget — it is fields the type carries, and a
    role's output type inherits them.
    """

    role_id: str = field(kw_only=True)
    role_version: int = field(kw_only=True)


def _text(*, value: str, reason: RoleRefusal, what: str) -> str:
    """A required text field, or the refusal."""
    if not value.strip():
        raise role_refused(RoleRefusal.SPEC_FIELD_EMPTY, f"the spec's {what} is empty")
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


def _row_to_spec(row: AgentRoleSpecRow) -> AgentRoleSpec:
    """The contract a row holds, decoded."""
    return AgentRoleSpec(
        role_id=row.role_id,
        role_version=row.role_version,
        objective=row.objective,
        input_schema=row.input_schema,
        output_schema=row.output_schema,
        allowed_capabilities=tuple(
            CapabilityId(item) for item in json.loads(row.allowed_capabilities)
        ),
        forbidden_actions=tuple(
            ForbiddenAction(item) for item in json.loads(row.forbidden_actions)
        ),
        allowed_data_purposes=tuple(json.loads(row.allowed_data_purposes)),
        provider_routing_policy=row.provider_routing_policy,
        cost_budget=row.cost_budget,
        token_budget=row.token_budget,
        timeout_seconds=row.timeout_seconds,
        retry_policy=row.retry_policy,
        fallback_policy=row.fallback_policy,
        abstain_conditions=tuple(json.loads(row.abstain_conditions)),
        escalation_conditions=tuple(json.loads(row.escalation_conditions)),
        prompt_template_version=row.prompt_template_version,
        model_config_ref=row.model_config_ref,
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
    session = context.store.session
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
    existing = session.get(AgentRoleSpecRow, (checked_id, role_version))
    if existing is not None:
        raise role_refused(
            RoleRefusal.SPEC_ALREADY_DEFINED,
            f"a spec for {checked_id!r} at version {role_version} is already"
            " defined; a new contract is a new version, not an overwrite",
        )
    row = AgentRoleSpecRow(
        role_id=checked_id,
        role_version=role_version,
        objective=checked_objective,
        input_schema=checked_input,
        output_schema=checked_output,
        allowed_capabilities=json.dumps([item.value for item in capabilities]),
        forbidden_actions=json.dumps([item.value for item in forbidden]),
        allowed_data_purposes=json.dumps(list(purposes)),
        provider_routing_policy=checked_routing,
        cost_budget=cost_budget,
        token_budget=token_budget,
        timeout_seconds=timeout_seconds,
        retry_policy=checked_retry,
        fallback_policy=checked_fallback,
        abstain_conditions=json.dumps(list(abstain_conditions)),
        escalation_conditions=json.dumps(list(escalation_conditions)),
        prompt_template_version=checked_prompt,
        model_config_ref=checked_config,
        defined_at=now,
    )
    session.add(row)
    session.flush()
    return _row_to_spec(row)


def load_spec(
    context: ApplicationContext, *, role_id: str, version: int | None = None
) -> AgentRoleSpec:
    """The contract a role works under — the version named, or the highest.

    :raises ApplicationRefusedError: no row carries that role id, at the
        version named or at any version.
    """
    session: Session = context.store.session
    if version is not None:
        row = session.get(AgentRoleSpecRow, (role_id, version))
    else:
        row = session.scalars(
            select(AgentRoleSpecRow)
            .where(AgentRoleSpecRow.role_id == role_id)
            .order_by(AgentRoleSpecRow.role_version.desc())
            .limit(1)
        ).first()
    if row is None:
        raise role_refused(
            RoleRefusal.SPEC_NOT_FOUND,
            f"the store holds no spec for {role_id!r}"
            + ("" if version is None else f" at version {version}"),
        )
    return _row_to_spec(row)
