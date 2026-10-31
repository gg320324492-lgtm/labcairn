"""The role contracts and the roles' own outputs, as data.

**Why these live apart from the operations.** :mod:`labcairn.roles.spec` is
the contract's lifecycle, and the lifecycle reads and writes through the
application layer — and the application layer answers with an
:class:`AgentRoleSpec`. So the layer and the lifecycle would import each
other, and the import would run in a circle. The contracts sit **below
both**, in a module that the layer's operations and the roles' own checks
both import.

That is the arrangement the rest of the repository already uses for the same
reason: :mod:`labcairn.papers.versions` and :mod:`labcairn.evidence.record`
hold the contracts their operations read back.

**And a contract is data.** The objective, the typed schemas, the
capabilities, the forbidden actions, the purposes, the budgets and the
conditions are ADR-0018's D1 list, and the code enforces them rather than
reading them: :meth:`AgentRoleSpec.require_allowed` for a capability and
:meth:`AgentRoleSpec.refuse_forbidden` for an action, each refusal carrying a
machine-readable reason. **A contract the code cannot check is a suggestion
the code ignores.**
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

from labcairn.application.refusal import role_refused
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


__all__ = [
    "FORBIDDEN_ACTIONS",
    "AgentRoleSpec",
    "ForbiddenAction",
    "RoleOutput",
]
