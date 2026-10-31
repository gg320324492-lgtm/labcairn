"""The arrangement, on demand — and the decisions it leaves behind.

LC-P2-12 T04. **The rule for which roles run is data, not a branch in
the code.** The routing table maps a named condition to the roles it
requires; :func:`decide_roles` walks the table and returns the decision
with, for every role, **the reason it was chosen** — because a decision
nobody can read back is a decision nobody can check. A caller may hand
in a different table, and the decision follows the table, not the
code's opinion of what a request deserves.

**And the roles that run are the ones the request needed.** A simple
comment extraction runs role A and nothing else; a research suggestion
adds role B; the critique runs when the risk is high, the evidence is
thin, the models disagree, or a person asks — **and there is no
swarm**.

**An unmeasurable cost refuses** (§2.6): a spec whose cost ceiling is
not priced cannot send a real call, because a budget whose price is
unknown fails closed. A retry reuses **the same plan** — the one
reservation, not a second — because a request that was sent and did
not answer is *unknown*, and paying for it twice is paying for a guess.

**And a person decides, and the decision is audited** (§2.7):
:func:`record_human_decision` appends an immutable record — who
decided, what they decided, and why — to a ledger that has no update
and no delete. A decision nobody can attribute is a decision nobody
made.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final

from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import role_refused
from labcairn.roles.refusals import RoleRefusal
from labcairn.roles.spec import AgentRoleSpec, ForbiddenAction

#: The request kinds, and the roles each kind needs **by itself**. The
#: escalation conditions below may add role C on top; nothing else does.
ROUTING_TABLE: Final[Mapping[str, tuple[str, ...]]] = {
    "a_comment_extraction": ("trajectory",),
    "a_research_suggestion": ("trajectory", "guidance"),
}

#: The conditions under which the critique runs, each with the reason
#: it records. **Four ways in, and no fifth** — a swarm is what happens
#: when the fifth is allowed to accrete.
ESCALATION_TABLE: Final[Mapping[str, str]] = {
    "high_risk": "the request is high risk, and the critique runs",
    "thin_evidence": "the evidence is thin, and the critique runs",
    "models_disagree": "the models disagree, and the critique runs",
    "a_person_asks": "a person asked for the critique",
}

#: The risks a request can carry.
RISKS: Final[frozenset[str]] = frozenset({"low", "high"})

#: The kinds of request the table knows. A kind outside them is refused
#: rather than routed by a default — a default is a branch wearing
#: data's clothes.
REQUEST_KINDS: Final[frozenset[str]] = frozenset(ROUTING_TABLE)


@dataclass(frozen=True)
class LoopRequest:
    """What was asked, with the facts that decide who runs."""

    kind: str
    risk: str
    evidence_thin: bool = False
    models_disagree: bool = False
    a_person_asks: bool = False


@dataclass(frozen=True)
class RoutingDecision:
    """Who runs, and why each of them does.

    The ``reasons`` are the record: one per role, naming the condition
    that chose it. **A decision with no reasons is a decision that was
    not made** — it was fallen into.
    """

    request: LoopRequest
    roles: tuple[str, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class InvocationPlan:
    """One priced invocation of one role, under its contract's ceilings.

    The plan is what a retry retries — the same object, the same
    reservation — and what a budget report reads afterwards.
    """

    spec: AgentRoleSpec
    token_budget: int
    timeout_seconds: int


def decide_roles(
    request: LoopRequest,
    *,
    table: Mapping[str, tuple[str, ...]] | None = None,
    escalation: Mapping[str, str] | None = None,
) -> RoutingDecision:
    """The roles this request needs, from the table, with the reasons.

    **The tables are parameters with defaults.** The default tables are
    the arrangement's own; a caller handing in another one gets a
    decision that follows it — which is what makes the routing data
    rather than a branch in the code.

    :raises ApplicationRefusedError: the request's kind or risk is
        outside its vocabulary.
    """
    conditions = table if table is not None else ROUTING_TABLE
    escalations = escalation if escalation is not None else ESCALATION_TABLE
    if request.kind not in REQUEST_KINDS:
        raise role_refused(
            RoleRefusal.REQUEST_KIND_UNKNOWN,
            f"{request.kind!r} is not one of {sorted(REQUEST_KINDS)}; a request"
            " the table does not know is not routed by a default",
        )
    if request.risk not in RISKS:
        raise role_refused(
            RoleRefusal.REQUEST_RISK_UNKNOWN,
            f"{request.risk!r} is not one of {sorted(RISKS)}",
        )
    roles = list(conditions[request.kind])
    reasons = [f"the request is {request.kind}, which needs these roles"]
    if request.risk == "high" and "high_risk" in escalations:
        if "critique" not in roles:
            roles.append("critique")
        reasons.append(escalations["high_risk"])
    for flag, condition in (
        (request.evidence_thin, "thin_evidence"),
        (request.models_disagree, "models_disagree"),
        (request.a_person_asks, "a_person_asks"),
    ):
        if flag and condition in escalations:
            if "critique" not in roles:
                roles.append("critique")
            reasons.append(escalations[condition])
    return RoutingDecision(
        request=request,
        roles=tuple(roles),
        reasons=tuple(reasons),
    )


def prepare_invocation(context: ApplicationContext, *, spec: AgentRoleSpec) -> InvocationPlan:
    """One priced plan for one role, or the refusal that says the price is unknown.

    :raises ApplicationRefusedError: the spec's cost ceiling is not
        priced — a real call cannot be measured against no ceiling, so
        it is refused rather than sent and hoped about.
    """
    if spec.cost_budget is None:
        raise role_refused(
            RoleRefusal.SPEC_COST_UNMEASURED,
            f"the role {spec.role_id!r} has no cost ceiling, and a budget"
            " whose price is unknown fails closed",
        )
    return InvocationPlan(
        spec=spec,
        token_budget=spec.token_budget,
        timeout_seconds=spec.timeout_seconds,
    )


def retry(plan: InvocationPlan) -> InvocationPlan:
    """The same plan again — one reservation, paid once.

    A request that was sent and did not answer is *unknown*, not a
    failure; the retry is the same invocation continuing, and the
    budget it reserved is the budget it spends.
    """
    return plan


@dataclass(frozen=True)
class DecisionRecord:
    """A person's decision on a card, immutable and attributed."""

    card_locator: str
    decision: str
    decided_by: str
    decided_at: datetime
    reason: str


@dataclass
class DecisionLedger:
    """The audit trail of human decisions on cards. **Append-only.**

    The ledger has no update and no delete: a decision a person made
    stays made, and a change of mind is a second record, not an
    overwrite of the first.
    """

    _records: list[DecisionRecord] = field(default_factory=list)

    def record(self, entry: DecisionRecord) -> DecisionRecord:
        """Append the decision. The ledger returns it as it now stands."""
        self._records.append(entry)
        return entry

    def decisions_for(self, card_locator: str) -> tuple[DecisionRecord, ...]:
        """Every decision on the card, in the order they were made."""
        return tuple(entry for entry in self._records if entry.card_locator == card_locator)


def record_human_decision(
    ledger: DecisionLedger,
    *,
    card_locator: str,
    decision: str,
    decided_by: str,
    reason: str,
    now: datetime,
) -> DecisionRecord:
    """A person's accept or reject of a card, recorded so it can be audited.

    :raises ApplicationRefusedError: the decision is not one of the two;
        the person who decided is unnamed; or the reason is empty.
    """
    if decision not in {"accepted", "rejected"}:
        raise role_refused(
            RoleRefusal.DECISION_UNKNOWN,
            f"{decision!r} is neither accepted nor rejected, and a third"
            " answer is a decision nobody made",
        )
    if not decided_by.strip():
        raise role_refused(
            RoleRefusal.DECISION_WITHOUT_A_PERSON,
            "a decision without a name behind it is a decision nobody made",
        )
    if not reason.strip():
        raise role_refused(
            RoleRefusal.DECISION_WITHOUT_A_REASON,
            "a decision without its reason is a shrug with a signature",
        )
    return ledger.record(
        DecisionRecord(
            card_locator=card_locator,
            decision=decision,
            decided_by=decided_by,
            decided_at=now,
            reason=reason,
        )
    )


def enforce_contract(
    spec: AgentRoleSpec,
    *,
    capability: str | None = None,
    action: ForbiddenAction | None = None,
) -> None:
    """The arrangement's one gate: nothing runs a role's contract does not allow.

    :raises ApplicationRefusedError: the capability is not listed in the
        contract, or the action is one it forbids.
    """
    if capability is not None:
        spec.require_allowed_by_name(capability)
    if action is not None:
        spec.refuse_forbidden(action)
