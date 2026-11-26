"""The loop, on demand: the roles a request names, and only those.

LC-P2-16 T05. The three roles of LC-P2-12 are finished, and this module
**calls** them; it does not re-implement them, and it does not change what
they do. What it adds is the operation they did not have: **one request,
routed to the roles it names, and run.**

**"On demand" is the whole of the claim.** The loop does not run every role
every time. The caller says which roles it wants; the loop runs those and
no others, in the order the roles depend on each other, and **a role the
caller did not ask for is not run** -- not consulted, not paid for, and
not given a contract.

**And the loop is two steps, because asking is not spending.** The
workbench's *"ask for a judgement on this comment"* is
:func:`request_role_run` and then :func:`run_role_run`:

* the **request** writes the question down -- the roles, the material, the
  contracts they run under, the prompt, and the consent the run will need
  -- and **spends nothing**: no approval is consumed, no wire is touched,
  and no role runs;
* the **run** spends the consent, and only through
  :func:`labcairn.application.model_request.request_model`, which is the
  one path that may spend a model call -- the transmit gate first, the
  approval ledger second, and the exchange recorded beside it.

**The refusals are the roles' own.** The loop does not check the values it
hands a role; the role does, and the refusal the role raises reaches the
caller unchanged -- an alignment outside the closed vocabulary, a claim
whose evidence the card does not declare, a quote the chain does not hold.
**A loop that pre-validated them would be a second spelling of the roles'
rules**, and the second spelling is the one that drifts.

**And the judgement comes from one place.** The caller may supply the
judgements outright -- the shape the operator's rehearsal walked by hand --
or leave the ones it does not have to the model, and the model's answer is
judged by the same roles. **There is one route to a judgement and one set
of refusals on it.**

**And the card's address is the product's.** The loop does not fill in the
card's address: a card carries an address of its own, minted from the
comment the card's evidence names, and the request has no field for it --
so a caller cannot point the card at a comment it is not about.

**The question is a function of the request.** :func:`the_role_run_question`
is a pure read: it writes nothing, asks for nothing and mints nothing, so
the same request against the same chain and the same memory gives the same
question, byte for byte. **A ticket is therefore something that can be
rebuilt rather than something that has to be kept** -- which is what lets
the workbench's two steps be two HTTP requests with no table between them.
The one thing a ticket carries that a rebuild cannot mint is the approval
id, and **that is already a row in the store**.

**What this module does not do.** It writes no manuscript, no artefact and
no ledger record; it grants no approval (a person's act); and it never
calls a provider itself. The roles' own prohibitions are the architecture's,
and this module is bound by them like everything else.

**The roles' modules are imported late, on purpose.** Every module under
:mod:`labcairn.roles` reaches for the application layer, and the layer
reaches for the roles -- so a module-level import of a role here would make
the import graph a circle whose broken side depends on which module a
process happened to import first. The roles are therefore imported inside
the functions that call them, which is what
:mod:`labcairn.application.roles` does for the contract types for the same
reason.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final, Protocol, cast

from pydantic import create_model

from labcairn.application import records
from labcairn.application.approvals import ApprovalRequest, ApprovalUse, request_approval
from labcairn.application.context import ApplicationContext
from labcairn.application.model_request import ModelInvocation, request_model
from labcairn.application.models import Result
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.core.ids import ApprovalId
from labcairn.core.schema import LabCairnModel
from labcairn.providers.budget import RunBudget
from labcairn.providers.capabilities import ProviderCapabilities
from labcairn.providers.ledger import LedgerSnapshot
from labcairn.security.capabilities import CapabilityId, ModelRequestArgs
from labcairn.security.permissions import Grant

if TYPE_CHECKING:
    from labcairn.roles.critique import ReviewVerdict
    from labcairn.roles.guidance import CardClaim, GuidanceCard, RuleCitation
    from labcairn.roles.models import AgentRoleSpec
    from labcairn.roles.trajectory import TrajectoryCandidate


#: The roles the loop can run. **Closed**: a role that is not here is not run,
#: and a caller that names one is refused by name rather than served by a
#: default.
ROLE_IDS: Final[frozenset[str]] = frozenset({"trajectory", "guidance", "critique"})

#: The order the roles run in. **The dependency order, not the caller's
#: order**: the critique reviews a card, so the card is made first. A caller
#: that names two roles gets them in this order whatever order it wrote them
#: in.
ROLE_ORDER: Final[tuple[str, ...]] = ("trajectory", "guidance", "critique")

#: The consent layer's purpose for material that leaves the machine. **The
#: purpose the model is asked for is a different thing** and travels in the
#: request's arguments; this is the purpose the transmit gate is asked
#: about, and the security layer's vocabulary closes it.
TRANSMIT_PURPOSE: Final[str] = "transmit"


# --------------------------------------------------------------------------- #
# what the caller asks for
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class TrajectoryJudgement:
    """What role A is asked to judge.

    **The fields are the ones the role takes, and the role checks them.**
    The alignment and the issue type are closed vocabularies the role owns,
    and the quote must be the advisor's own words; the loop passes these
    through and lets the role refuse what is wrong.
    """

    issue_type: str
    alignment: str
    advisor_quote: str
    note: str
    edit_action_id: str | None = None


@dataclass(frozen=True)
class GuidanceJudgement:
    """What role B is asked to judge.

    The claims are the caller's own objects --
    :class:`labcairn.roles.guidance.CardClaim` -- because the role checks
    each claim against the card's declared evidence, and a claim shaped like
    a mapping would be a second spelling.
    """

    issue_type: str
    severity: str
    reason: str
    suggested_next_action: str
    uncertainty_kind: str
    what_is_uncertain: str
    claims: tuple[CardClaim, ...] = ()
    style_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CritiqueJudgement:
    """What role C is asked to judge."""

    verdict: str
    repair_advice: str
    handover_reason: str | None = None


@dataclass(frozen=True)
class RoleRunRequest:
    """What the caller asks the loop to do.

    **``roles`` is the whole of the routing.** The loop runs those and no
    others. A judgement supplied for a role that is not named is **not** a
    request for that role: it is simply not used, because the caller did not
    ask for that role.

    The judgements are optional, and one missing means one thing: **the
    model must supply it.** A caller that has them all spends nothing and
    reaches no wire; a caller that has none has the model supply every one,
    and the roles judge the model's answers exactly as they judge the
    caller's.

    **And there is no target locator to supply.** The card's address is
    minted by the product from the comment the card's evidence names, and
    a caller that could write it could point the card at a comment it is
    not about.
    """

    roles: tuple[str, ...]
    project_id: str
    issue_key: str
    version_ids: tuple[str, ...] = ()
    rule_id: str | None = None
    evidence_refs: tuple[str, ...] | None = None
    trajectory: TrajectoryJudgement | None = None
    guidance: GuidanceJudgement | None = None
    critique: CritiqueJudgement | None = None


@dataclass(frozen=True)
class ModelCallPlan:
    """What the model call needs from the caller: who to ask, and where the material is.

    **The excerpts are not here.** They are the material the loop reads out
    of the chain and the memory, and the loop builds them, so the thing the
    approval binds is the thing the call actually sends.

    **And the material's address is a declaration, not a fact.** The loop
    knows where the comment's material is -- it read it -- and it **checks
    this declaration against what it read**, refusing by name when the two
    are not the same material. A declaration the loop cannot check is a
    declaration the loop cannot trust, and the grant the transmit gate
    checks would then cover one material while another leaves.
    """

    provider: str
    model: str
    root_id: str
    resource_key: str
    material_ref: str
    purpose: str
    destination: str
    subject_ref: str


# --------------------------------------------------------------------------- #
# what the loop writes down, and what it returns
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class MaterialAddress:
    """Where the material the run sends actually is.

    **The loop computes this; the caller declares it.** The two are
    compared, and a difference is refused by name.
    """

    #: The workspace-relative path of the comment's material.
    workspace_path: str
    #: The root the path landed in.
    root_id: str
    #: The key of the material inside that root.
    resource_key: str


@dataclass(frozen=True)
class RoleRunQuestion:
    """The question the request asks: what will be sent, and what it is made of.

    **Nothing in it is minted.** Every field is read from the store or
    derived from the request, so the same request against the same chain
    and the same memory gives the same question -- which is what makes a
    ticket rebuildable rather than something that has to be kept.
    """

    request: RoleRunRequest
    contracts: tuple[AgentRoleSpec, ...]
    prompt: str
    excerpts: tuple[str, ...]
    plan: ModelCallPlan
    material: MaterialAddress
    rule_citation: RuleCitation | None


@dataclass(frozen=True)
class RoleRunTicket:
    """The question, written down, and the consent the run will spend.

    **This is the first step's whole output.** It names the roles that will
    run, the contracts they run under, the material, the prompt, and the
    consent the run will need -- and **nothing has been spent**: the
    approval it carries is *pending*, no exchange was recorded, and no role
    ran.

    **And it is a function of the request, apart from the approval id.**
    The question is rebuilt by :func:`the_role_run_question`; the approval
    id is minted by the store, and it is already a row there.
    """

    question: RoleRunQuestion
    approval_id: ApprovalId | None
    asked_at: datetime

    @property
    def request(self) -> RoleRunRequest:
        """The request the question answers."""
        return self.question.request

    @property
    def contracts(self) -> tuple[AgentRoleSpec, ...]:
        """The contracts the roles run under."""
        return self.question.contracts

    @property
    def prompt(self) -> str:
        """The question, as it will be asked."""
        return self.question.prompt

    @property
    def excerpts(self) -> tuple[str, ...]:
        """The material that leaves the machine."""
        return self.question.excerpts

    @property
    def plan(self) -> ModelCallPlan:
        """Who to ask, and where the material is."""
        return self.question.plan

    @property
    def rule_citation(self) -> RuleCitation | None:
        """The rule the card cites, with the cases against it."""
        return self.question.rule_citation

    @property
    def use(self) -> ApprovalUse:
        """What the approval is spent on, derived from the question as it now stands.

        **Derived, not carried.** A caller that changed the question changed
        this, and the digest it carries is over the question as it now
        stands -- which is what makes the change visible to the approval.
        """
        return _the_use(self.question)


@dataclass(frozen=True)
class RoleRunResult:
    """What the run produced: one output per role that ran, and what was spent.

    **The outputs carry the contract they were made under** -- the role id
    and the version the contract had when it was read -- because an output
    that does not say which contract governed it cannot be replayed against
    that contract.
    """

    roles: tuple[str, ...]
    candidate: TrajectoryCandidate | None = None
    card: GuidanceCard | None = None
    verdict: ReviewVerdict | None = None
    answer: str | None = None
    exchange_event_id: str | None = None


# --------------------------------------------------------------------------- #
# the document the model is asked for
# --------------------------------------------------------------------------- #


class TrajectoryJudgementModel(LabCairnModel):
    """The shape role A's judgement has, as the model is asked for it.

    **The closed vocabularies are not closed here.** The alignment and the
    issue type are the role's to judge, and a schema that closed them would
    turn the role's refusal into a decoding failure -- the role's rule
    would never be reached, and the refusal that names the vocabulary would
    never be seen. The schema is a shape; the role is the judge.
    """

    issue_type: str
    alignment: str
    advisor_quote: str
    note: str
    edit_action_id: str | None = None


class ClaimModel(LabCairnModel):
    """One claim as the model states it."""

    text: str
    kind: str
    evidence_ref: str | None = None
    issue_key: str | None = None
    advisor_quote: str | None = None


class GuidanceJudgementModel(LabCairnModel):
    """The shape role B's judgement has, as the model is asked for it."""

    issue_type: str
    severity: str
    reason: str
    suggested_next_action: str
    uncertainty_kind: str
    what_is_uncertain: str
    claims: tuple[ClaimModel, ...] = ()
    style_notes: tuple[str, ...] = ()


class CritiqueJudgementModel(LabCairnModel):
    """The shape role C's judgement has, as the model is asked for it."""

    verdict: str
    repair_advice: str
    handover_reason: str | None = None


class _JudgementDocument(Protocol):
    """The document the model was asked for, read one part at a time.

    **The parts are the roles the caller named and did not supply**, so a
    document read through this shape has a part for each of them and for
    nothing else. A part that is absent is the loop's own refusal, not a
    decoding failure: the answer fitted the shape it was asked for, and it
    did not carry what the run needed.
    """

    trajectory: TrajectoryJudgementModel | None
    guidance: GuidanceJudgementModel | None
    critique: CritiqueJudgementModel | None


#: The document each role's judgement takes, by the role's id.
_JUDGEMENT_MODELS: Final[dict[str, type[LabCairnModel]]] = {
    "trajectory": TrajectoryJudgementModel,
    "guidance": GuidanceJudgementModel,
    "critique": CritiqueJudgementModel,
}


def _schema_for(roles: tuple[str, ...]) -> type[LabCairnModel]:
    """The document the model is asked for: one part per role that needs a judgement.

    **The parts are exactly the roles the caller named and did not supply.**
    A part for a role the caller did not ask for is an **extra key**, and
    the schema forbids extra keys -- so the model cannot volunteer a card
    for a role nobody asked for, and the loop cannot run one.
    """
    fields: dict[str, Any] = {role: (_JUDGEMENT_MODELS[role] | None, None) for role in roles}
    return cast(
        "type[LabCairnModel]",
        create_model("RoleJudgements", __base__=LabCairnModel, **fields),
    )


# --------------------------------------------------------------------------- #
# the two steps
# --------------------------------------------------------------------------- #


def the_role_run_question(
    context: ApplicationContext,
    request: RoleRunRequest,
    *,
    plan: ModelCallPlan,
) -> RoleRunQuestion:
    """The question the request asks, rebuilt from the request and the store.

    **A pure read.** It writes nothing, asks for nothing and mints nothing,
    so the same request against the same chain and the same memory gives the
    same question -- and that is what lets the workbench's two steps be two
    requests with no table between them.

    :raises ApplicationRefusedError: the request names no role, a role the
        loop does not know, the same role twice, or the critique without the
        guidance that makes a card to review; a named role has no contract,
        or its contract does not list the capability the run exercises; the
        memory holds no rule under the id the request names; the chain holds
        no comment under the issue key, or a version named is outside the
        project's graph; or the caller's declaration of the material is not
        the material the chain holds.
    """
    roles = _the_roles(request.roles)
    contracts = tuple(_the_contract(context, role_id=role_id) for role_id in roles)
    missing = _missing_judgements(request, roles)
    if missing:
        for contract in contracts:
            contract.require_allowed(CapabilityId.MODEL_REQUEST)

    chain = _the_chain(context, request)
    material = _the_material(context, request, chain)
    _check_the_declaration(plan, material)
    rule_citation = _the_rule(context, request)
    prompt = _the_prompt(request, contracts, chain, rule_citation)
    return RoleRunQuestion(
        request=request,
        contracts=contracts,
        prompt=prompt,
        excerpts=_the_excerpts(chain, rule_citation),
        plan=plan,
        material=material,
        rule_citation=rule_citation,
    )


def _asked_for_request(request: RoleRunRequest) -> dict[str, str]:
    """What the caller asked for, as the refusal event records it.

    **Identifiers, keys and counts — never the material's text.** The point
    is that a person reading the log knows which request was refused without
    the log becoming a second copy of the manuscript. Values are strings so
    the payload stays a flat mapping a reader can print.
    """
    asked = {
        "operation": "roles run: request",
        "roles": ", ".join(request.roles),
        "project": request.project_id,
        "issue_key": request.issue_key,
    }
    if request.version_ids:
        asked["versions"] = ", ".join(request.version_ids)
    if request.rule_id is not None:
        asked["rule"] = request.rule_id
    return asked


def _asked_for_run(ticket: RoleRunTicket) -> dict[str, str]:
    """What the spend asked for, as the refusal event records it."""
    asked = {
        "operation": "roles run: spend",
        "roles": ", ".join(contract.role_id for contract in ticket.contracts),
        "issue_key": ticket.request.issue_key,
    }
    if ticket.approval_id is not None:
        asked["approval"] = str(ticket.approval_id)
    return asked


def request_role_run(
    context: ApplicationContext,
    request: RoleRunRequest,
    *,
    plan: ModelCallPlan,
    expires_at: datetime,
    now: datetime | None = None,
) -> RoleRunTicket:
    """Write the question down, and spend nothing.

    The request names the roles; this operation rebuilds the question, and
    -- **only if some judgement is missing** -- asks the consent layer for
    the approval the run will spend. The approval it asks for is
    **pending**: nothing is granted and nothing is consumed, because a grant
    is a person's act and a spend is the run's.

    :raises ApplicationRefusedError: everything
        :func:`the_role_run_question` refuses, and the policy's refusal of
        the request the approval is for.

    **A refusal is recorded before it is raised.** The pilot measured the
    gap: a refusal that reached only the exit code and the message left no
    trace in the task's event log, so the next morning the log could not
    say that anything was asked for. The event names the refusal's own
    reason, its message, and the request — ids, keys and counts, never the
    material's text — and it is written before the exception leaves this
    function so the caller still gets the same refusal it always did.
    """
    moment = now if now is not None else datetime.now(UTC)
    try:
        question = the_role_run_question(context, request, plan=plan)
        roles = _the_roles(request.roles)
        missing = _missing_judgements(request, roles)
        approval_id: ApprovalId | None = None
        if missing:
            asked = request_approval(
                context,
                ApprovalRequest(use=_the_use(question), expires_at=expires_at),
                now=moment,
            )
            approval_id = asked.approval.approval_id
    except ApplicationRefusedError as refused:
        records.record_refusal(
            context,
            reason=refused.reason.value,
            message=refused.detail,
            asked_for=_asked_for_request(request),
            now=moment,
        )
        raise
    return RoleRunTicket(
        question=question,
        approval_id=approval_id,
        asked_at=moment,
    )


def run_role_run(
    context: ApplicationContext,
    ticket: RoleRunTicket,
    *,
    grants: Sequence[Grant],
    at: datetime,
    send: Callable[[str], ModelInvocation] | None = None,
    capabilities: ProviderCapabilities | None = None,
    budget: RunBudget | None = None,
    ledger: LedgerSnapshot | None = None,
) -> RoleRunResult:
    """Run the roles the request named, and only those.

    **A missing judgement is asked of the model, and the model call is
    spent through :func:`labcairn.application.model_request.request_model`**
    -- the one path that may spend one. The gate order is the path's, not
    this module's: the transmit check runs before the approval is consumed,
    so a request refused for want of a grant leaves the approval unspent.

    **And the roles run in the dependency order, each through its own
    operation**, so the refusal a role raises is the refusal that reaches
    the caller: an alignment outside the vocabulary, a claim whose evidence
    the card does not declare, a quote the chain does not hold. **A role the
    caller did not name is not run at all** -- not asked about, not paid for.

    **And the approval binds the question, not only the material.** The
    question's own digest goes into the approval's dependency list, so a
    ticket that changed between the asking and the running -- a different
    prompt, a different set of roles -- produces a different digest, and
    the spend is refused because the approval does not cover this question.

    **An answered request closes what asked for it.** Once the model call
    returns, the operation its approval authorised is confirmed, the stage
    that was parked on the approval is completed, and the run that held the
    stage is finished -- one transaction, the transitions in the order they
    happened. Before that closure the stage read ``blocked`` and the run
    ``running`` long after both had stopped being true.

    **A refusal is recorded before it is raised.** The same rule the ask
    follows: the reason, the message and the request land in the task's
    event log, so a refusal nobody watched is still a refusal the product
    can show.

    :raises ApplicationRefusedError: the run needs a model judgement and no
        provider invocation was given; the consent refused the call; the
        answer did not carry a judgement for a role the request named; or a
        role refused its own judgement.
    """
    try:
        return _run_role_run(
            context,
            ticket,
            grants=grants,
            at=at,
            send=send,
            capabilities=capabilities,
            budget=budget,
            ledger=ledger,
        )
    except ApplicationRefusedError as refused:
        records.record_refusal(
            context,
            reason=refused.reason.value,
            message=refused.detail,
            asked_for=_asked_for_run(ticket),
            now=at,
        )
        raise


def _run_role_run(
    context: ApplicationContext,
    ticket: RoleRunTicket,
    *,
    grants: Sequence[Grant],
    at: datetime,
    send: Callable[[str], ModelInvocation] | None,
    capabilities: ProviderCapabilities | None,
    budget: RunBudget | None,
    ledger: LedgerSnapshot | None,
) -> RoleRunResult:
    """The run's body, under :func:`run_role_run`'s refusal record."""
    question = ticket.question
    request = question.request
    # **The contracts are the authority for what runs.** They are the part of
    # the question the approval's digest covers, so a ticket that changed
    # between the asking and the running cannot make a role run that was not
    # approved -- the spend is refused before it.
    roles = tuple(contract.role_id for contract in question.contracts)
    missing = _missing_judgements(request, roles)

    answer: str | None = None
    exchange_event_id: str | None = None
    judgements = _Judgements(
        trajectory=request.trajectory,
        guidance=request.guidance,
        critique=request.critique,
    )
    if missing:
        if send is None:
            raise ApplicationRefusedError(
                ApplicationRefusal.ROLE_RUN_NO_PROVIDER_INVOCATION,
                f"the run needs a judgement for {sorted(missing)} and no provider"
                " invocation was given, so there is nothing to ask the model with",
            )
        if ticket.approval_id is None:
            raise ApplicationRefusedError(
                ApplicationRefusal.APPROVAL_MISSING,
                "the ticket carries no approval, and a model call may only be spent with one",
            )
        asked = send
        captured: list[ModelInvocation] = []

        def _send() -> ModelInvocation:
            """The provider invocation, reached only after every gate permitted."""
            invocation = asked(ticket.prompt)
            captured.append(invocation)
            return invocation

        model_answer = request_model(
            context,
            ticket.approval_id,
            list(grants),
            use=_the_use(question),
            subject_ref=question.plan.subject_ref,
            destination=question.plan.destination,
            material_ref=question.plan.material_ref,
            purpose=TRANSMIT_PURPOSE,
            at=at,
            send=_send,
            budget=budget,
            ledger=ledger,
            capabilities=capabilities,
            output_schema=_schema_for(missing),
        )
        answer = model_answer.answer
        exchange_event_id = model_answer.exchange_event_id
        # **The request was answered, so what asked for it is closed.** The
        # approval was consumed and the call returned; the operation its
        # intent named is confirmed, the stage parked on it completed, and
        # the run finished — the transitions that were missing from the
        # pilot's chain, written now in the order they happened. The role
        # work below may still refuse, and that refusal is recorded as a
        # refusal; it does not unstate the call that happened.
        records.complete_consumed_approval(context, approval_id=ticket.approval_id, now=at)
        document = captured[0].structured if captured else None
        judgements = _the_judgements(document, missing, judgements)

    result = _run_the_roles(context, question, roles, judgements)
    return RoleRunResult(
        roles=result.roles,
        candidate=result.candidate,
        card=result.card,
        verdict=result.verdict,
        answer=answer,
        exchange_event_id=exchange_event_id,
    )


# --------------------------------------------------------------------------- #
# the loop's own checks
# --------------------------------------------------------------------------- #


def _the_roles(named: tuple[str, ...]) -> tuple[str, ...]:
    """The roles the request names, in the order they run.

    :raises ApplicationRefusedError: no role was named, a role the loop does
        not know was named, a role was named twice, or the critique was named
        without the guidance that makes a card to review.
    """
    if not named:
        raise ApplicationRefusedError(
            ApplicationRefusal.ROLE_RUN_NO_ROLE_NAMED,
            "the request names no role, and a request that asks for nothing has nothing to run",
        )
    unknown = sorted(set(named) - ROLE_IDS)
    if unknown:
        raise ApplicationRefusedError(
            ApplicationRefusal.ROLE_RUN_UNKNOWN_ROLE,
            f"the request names {unknown!r}, and the loop runs only"
            f" {sorted(ROLE_IDS)}; a role the loop does not know is not routed"
            " by a default",
        )
    repeated = sorted({role for role in named if named.count(role) > 1})
    if repeated:
        raise ApplicationRefusedError(
            ApplicationRefusal.ROLE_RUN_ROLE_NAMED_TWICE,
            f"the request names {repeated!r} more than once, and a role that runs"
            " twice is not the role the caller asked for",
        )
    if "critique" in named and "guidance" not in named:
        raise ApplicationRefusedError(
            ApplicationRefusal.ROLE_RUN_CRITIQUE_WITHOUT_GUIDANCE,
            "the request asks for the critique without the guidance that makes a"
            " card to review, and a review of nothing is not a review",
        )
    return tuple(role for role in ROLE_ORDER if role in named)


def _the_contract(context: ApplicationContext, *, role_id: str) -> AgentRoleSpec:
    """The contract the role runs under: the versioned row, read through the layer.

    :raises ApplicationRefusedError: the store holds no contract under that
        role id.
    """
    from labcairn.application.roles import read_role_spec

    return read_role_spec(context, role_id=role_id)


def _missing_judgements(request: RoleRunRequest, roles: tuple[str, ...]) -> tuple[str, ...]:
    """The roles the caller named and did not supply a judgement for."""
    supplied = {
        "trajectory": request.trajectory,
        "guidance": request.guidance,
        "critique": request.critique,
    }
    return tuple(role for role in roles if supplied[role] is None)


# --------------------------------------------------------------------------- #
# the material, and the question
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _ChainFacts:
    """What the chain holds for the request: the comment's words and the rounds."""

    comment_texts: tuple[str, ...]
    version_ids: tuple[str, ...]
    edit_ids: tuple[str, ...]
    comment_version_id: str


def _the_chain(context: ApplicationContext, request: RoleRunRequest) -> _ChainFacts:
    """The chain's facts for the request, read through the layer.

    **The chain is read through the role that reads it**, so the material
    the loop sends is the same material the roles will work on, and the
    refusals the read raises are the roles' own.

    :raises ApplicationRefusedError: the chain holds no comment under the
        issue key, or a version named is outside the project's graph, or the
        accepted edges leave the order ambiguous.
    """
    from labcairn.application import chain as chain_layer
    from labcairn.roles.trajectory import TrajectoryInput, read_trajectory

    chain = read_trajectory(
        context,
        trajectory_input=TrajectoryInput(
            project_id=request.project_id,
            version_ids=request.version_ids,
            issue_keys=(request.issue_key,),
        ),
    )
    held = chain_layer.read_comments(context, issue_keys=(request.issue_key,))
    if not held:
        raise ApplicationRefusedError(
            ApplicationRefusal.ROLE_COMMENT_NOT_IN_THE_CHAIN,
            f"the chain holds no comment under the key {request.issue_key!r}",
        )
    return _ChainFacts(
        comment_texts=tuple(comment.comment_text for comment in chain.comments),
        version_ids=chain.ordered_version_ids,
        edit_ids=tuple(edit.edit_action_id for edit in chain.edits),
        comment_version_id=held[0].version_id,
    )


def _the_material(
    context: ApplicationContext, request: RoleRunRequest, chain: _ChainFacts
) -> MaterialAddress:
    """Where the comment's material is, computed from the chain.

    **The loop does not take the caller's word for it.** The comment names
    a version, the version names a source, and the source names a path --
    and that path is what the run would send. So the address is a fact the
    loop can prove, and the caller's declaration is checked against it.

    :raises ApplicationRefusedError: the version names material the ledger
        does not hold.
    """
    from labcairn.application import chain as chain_layer

    paths = chain_layer.read_material_paths(context, version_ids=(chain.comment_version_id,))
    workspace_path = paths.get(chain.comment_version_id)
    if workspace_path is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.CHAIN_SOURCE_NOT_FOUND,
            f"the version {chain.comment_version_id!r} names material the ledger"
            " does not hold, so the run has no address for the material it would send",
        )
    canonical = context.resource_for(workspace_path)
    return MaterialAddress(
        workspace_path=workspace_path,
        root_id=canonical.root_id,
        resource_key=canonical.declared_key,
    )


def _check_the_declaration(plan: ModelCallPlan, material: MaterialAddress) -> None:
    """The caller's declaration and the chain's material must be one material.

    **The grant the transmit gate checks names a material, and the approval
    binds a set of excerpts.** If the two were not the same material, the
    grant would cover one thing and another would leave. So the loop reads
    the material itself and compares: a declaration that does not match is
    **refused by name**, and the refusal says which part differs. **It is
    not silently replaced** -- a caller that was told it had its material
    must not be handed somebody else's.

    :raises ApplicationRefusedError: the declaration names a different
        material than the chain holds.
    """
    declared = {
        "root id": plan.root_id,
        "resource key": plan.resource_key,
        "material ref": plan.material_ref,
    }
    computed = {
        "root id": material.root_id,
        "resource key": material.resource_key,
        "material ref": material.workspace_path,
    }
    differing = sorted(name for name, value in declared.items() if value != computed[name])
    if differing:
        raise ApplicationRefusedError(
            ApplicationRefusal.ROLE_RUN_MATERIAL_MISMATCH,
            f"the request declares the material as {declared!r}, and the chain holds"
            f" it as {computed!r}; {', '.join(differing)} differ",
        )


def _the_rule(context: ApplicationContext, request: RoleRunRequest) -> RuleCitation | None:
    """The rule the card cites, with the cases against it.

    :raises ApplicationRefusedError: the memory holds no rule under the id
        the request names.
    """
    if request.rule_id is None:
        return None
    from labcairn.roles.guidance import cite_rule

    return cite_rule(context, rule_id=request.rule_id)


def _the_excerpts(chain: _ChainFacts, rule: RuleCitation | None) -> tuple[str, ...]:
    """The material that leaves the machine, and nothing else.

    **The loop's own instructions are not excerpts** -- they are the
    repository's text, not the reader's material -- and neither is the
    model's own earlier words. The approval binds this set.
    """
    parts = list(chain.comment_texts)
    if rule is not None:
        parts.append(rule.statement)
        parts.extend(rule.counterexamples)
    return tuple(parts)


def _the_prompt(
    request: RoleRunRequest,
    contracts: Sequence[AgentRoleSpec],
    chain: _ChainFacts,
    rule: RuleCitation | None,
) -> str:
    """The question, as it will be asked.

    **The roles' own objectives are the instructions.** They come from the
    contracts, so the question a role is asked is the one its contract
    states, and a contract that changes its objective changes the question.
    """
    lines: list[str] = [
        "The guidance loop asks for judgements on one comment.",
        "",
        f"Roles to run: {', '.join(contract.role_id for contract in contracts)}.",
        "",
        "Each role's contract:",
    ]
    for contract in contracts:
        lines.append(f"- {contract.role_id}, version {contract.role_version}: {contract.objective}")
    lines.extend(["", "The material:", f"issue key: {request.issue_key}"])
    if chain.version_ids:
        lines.append(f"the versions, in the accepted edges' order: {', '.join(chain.version_ids)}")
    if chain.comment_texts:
        lines.append("the advisor's comment, in their own words:")
        lines.extend(f"  {text}" for text in chain.comment_texts)
    if chain.edit_ids:
        lines.append(f"the changes that answered it: {', '.join(chain.edit_ids)}")
    if rule is not None:
        lines.append("the rule the card cites:")
        lines.append(f"  {rule.statement}")
        if rule.counterexamples:
            lines.append("the cases against that rule:")
            lines.extend(f"  - {item}" for item in rule.counterexamples)
    lines.extend(["", "Answer with one part per role, and only those parts:"])
    for contract in contracts:
        lines.append(f"- {contract.role_id}: {_the_part(contract.role_id)}")
    return "\n".join(lines)


def _the_part(role_id: str) -> str:
    """The fields one role's part carries."""
    if role_id == "trajectory":
        return (
            "issue_type, alignment, advisor_quote (a verbatim span of the advisor's"
            " comment above), note, edit_action_id."
        )
    if role_id == "guidance":
        return (
            "issue_type, severity, reason, suggested_next_action, uncertainty_kind,"
            " what_is_uncertain, claims, style_notes."
        )
    return "verdict, repair_advice, handover_reason."


# --------------------------------------------------------------------------- #
# what the approval binds
# --------------------------------------------------------------------------- #


def _question_digest(question: RoleRunQuestion) -> str:
    """A digest of everything the run depends on: the roles, the prompt, the material.

    **It goes into the approval's dependency list**, so the approval binds
    the *question* and not only the material. A ticket that changed between
    the asking and the running -- a different prompt, a different set of
    roles, a different material -- produces a different digest, and the
    spend is refused because the approval does not cover this question.
    """
    payload = {
        "request": asdict(question.request),
        "roles": [contract.role_id for contract in question.contracts],
        "prompt": question.prompt,
        "excerpts": list(question.excerpts),
        "material": {
            "workspace_path": question.material.workspace_path,
            "root_id": question.material.root_id,
            "resource_key": question.material.resource_key,
        },
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _the_use(question: RoleRunQuestion) -> ApprovalUse:
    """What the approval is spent on: the model's request, and the question's digest.

    **The use is derived from the question, not carried beside it.** A
    caller that changed the question changed this, and the digest it
    carries is over the question as it now stands -- which is what makes
    the change visible to the approval.
    """
    plan = question.plan
    material = question.material
    return ApprovalUse(
        capability=CapabilityId.MODEL_REQUEST,
        arguments=ModelRequestArgs(
            provider=plan.provider,
            model=plan.model,
            path=material.resource_key,
            excerpts=question.excerpts,
            purpose=plan.purpose,
        ).model_dump(),
        root_id=material.root_id,
        resource_key=material.resource_key,
        depends_on=(_question_digest(question),),
    )


# --------------------------------------------------------------------------- #
# running the roles
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _Judgements:
    """The judgements the run works from, whoever supplied them."""

    trajectory: TrajectoryJudgement | None = None
    guidance: GuidanceJudgement | None = None
    critique: CritiqueJudgement | None = None


def _the_judgements(document: object, missing: tuple[str, ...], known: _Judgements) -> _Judgements:
    """The judgements the run works from: the caller's, and the model's for the rest.

    **The document was decoded by the model path**, which refused an answer
    that did not fit the schema it was asked for -- so what arrives here is
    already the shape the roles take, and it is turned into the same
    objects the caller would have supplied.

    :raises ApplicationRefusedError: the answer carried no judgement for a
        role the request named.
    """
    from labcairn.roles.guidance import CardClaim

    if not isinstance(document, dict):
        raise ApplicationRefusedError(
            ApplicationRefusal.MODEL_ANSWER_EMPTY,
            "the call came back with nothing in the schema's shape, and an empty"
            " result is not a result",
        )
    parsed = cast("_JudgementDocument", _schema_for(missing).model_validate(document))
    trajectory = known.trajectory
    guidance = known.guidance
    critique = known.critique
    if "trajectory" in missing:
        trajectory_part = parsed.trajectory
        if trajectory_part is None:
            raise ApplicationRefusedError(
                ApplicationRefusal.ROLE_RUN_NO_JUDGEMENT,
                "the answer carried no judgement for the role 'trajectory', and a role"
                " the request named is not run without one",
            )
        trajectory = TrajectoryJudgement(
            issue_type=trajectory_part.issue_type,
            alignment=trajectory_part.alignment,
            advisor_quote=trajectory_part.advisor_quote,
            note=trajectory_part.note,
            edit_action_id=trajectory_part.edit_action_id,
        )
    if "guidance" in missing:
        guidance_part = parsed.guidance
        if guidance_part is None:
            raise ApplicationRefusedError(
                ApplicationRefusal.ROLE_RUN_NO_JUDGEMENT,
                "the answer carried no judgement for the role 'guidance', and a role"
                " the request named is not run without one",
            )
        guidance = GuidanceJudgement(
            issue_type=guidance_part.issue_type,
            severity=guidance_part.severity,
            reason=guidance_part.reason,
            suggested_next_action=guidance_part.suggested_next_action,
            uncertainty_kind=guidance_part.uncertainty_kind,
            what_is_uncertain=guidance_part.what_is_uncertain,
            claims=tuple(
                CardClaim(
                    text=claim.text,
                    kind=claim.kind,
                    evidence_ref=claim.evidence_ref,
                    issue_key=claim.issue_key,
                    advisor_quote=claim.advisor_quote,
                )
                for claim in guidance_part.claims
            ),
            style_notes=guidance_part.style_notes,
        )
    if "critique" in missing:
        critique_part = parsed.critique
        if critique_part is None:
            raise ApplicationRefusedError(
                ApplicationRefusal.ROLE_RUN_NO_JUDGEMENT,
                "the answer carried no judgement for the role 'critique', and a role"
                " the request named is not run without one",
            )
        critique = CritiqueJudgement(
            verdict=critique_part.verdict,
            repair_advice=critique_part.repair_advice,
            handover_reason=critique_part.handover_reason,
        )
    return _Judgements(trajectory=trajectory, guidance=guidance, critique=critique)


def _the_judgement[T](judgement: T | None, role_id: str) -> T:
    """The judgement a named role works from.

    :raises ApplicationRefusedError: no judgement reached the role.
    """
    if judgement is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.ROLE_RUN_NO_JUDGEMENT,
            f"the request named {role_id!r} and no judgement reached it",
        )
    return judgement


def _run_the_roles(
    context: ApplicationContext,
    question: RoleRunQuestion,
    roles: tuple[str, ...],
    judgements: _Judgements,
) -> RoleRunResult:
    """Run the roles named, in order, each through its own operation."""
    from labcairn.roles.critique import review_card
    from labcairn.roles.guidance import Uncertainty, build_card
    from labcairn.roles.trajectory import propose_candidate

    request = question.request
    contracts = {contract.role_id: contract for contract in question.contracts}
    candidate = None
    card = None
    verdict = None

    for role_id in roles:
        if role_id == "trajectory":
            trajectory_judgement = _the_judgement(judgements.trajectory, role_id)
            candidate = propose_candidate(
                context,
                spec=contracts["trajectory"],
                issue_key=request.issue_key,
                issue_type=trajectory_judgement.issue_type,
                alignment=trajectory_judgement.alignment,
                advisor_quote=trajectory_judgement.advisor_quote,
                note=trajectory_judgement.note,
                edit_action_id=trajectory_judgement.edit_action_id,
            )
        elif role_id == "guidance":
            guidance_judgement = _the_judgement(judgements.guidance, role_id)
            card = build_card(
                context,
                spec=contracts["guidance"],
                issue_type=guidance_judgement.issue_type,
                severity=guidance_judgement.severity,
                reason=guidance_judgement.reason,
                evidence_refs=(
                    request.evidence_refs
                    if request.evidence_refs is not None
                    else (f"chain:{request.issue_key}",)
                ),
                suggested_next_action=guidance_judgement.suggested_next_action,
                uncertainty=Uncertainty(
                    kind=guidance_judgement.uncertainty_kind,
                    what_is_uncertain=guidance_judgement.what_is_uncertain,
                ),
                claims=guidance_judgement.claims,
                style_notes=guidance_judgement.style_notes,
                rule_refs=((question.rule_citation,) if question.rule_citation is not None else ()),
            )
        else:
            critique_judgement = _the_judgement(judgements.critique, role_id)
            if card is None:
                raise ApplicationRefusedError(
                    ApplicationRefusal.ROLE_RUN_CRITIQUE_WITHOUT_GUIDANCE,
                    "the critique ran without a card to review, and a review of"
                    " nothing is not a review",
                )
            verdict = review_card(
                context,
                spec=contracts["critique"],
                card=card,
                verdict=critique_judgement.verdict,
                repair_advice=critique_judgement.repair_advice,
                handover_reason=critique_judgement.handover_reason,
            )
    return RoleRunResult(
        roles=roles,
        candidate=candidate,
        card=card,
        verdict=verdict,
    )


__all__ = [
    "ROLE_IDS",
    "ROLE_ORDER",
    "TRANSMIT_PURPOSE",
    "ClaimModel",
    "CritiqueJudgement",
    "CritiqueJudgementModel",
    "GuidanceJudgement",
    "GuidanceJudgementModel",
    "MaterialAddress",
    "ModelCallPlan",
    "RoleRunBackend",
    "RoleRunCandidate",
    "RoleRunCard",
    "RoleRunCardClaim",
    "RoleRunQuestion",
    "RoleRunRequest",
    "RoleRunResult",
    "RoleRunRuleCitation",
    "RoleRunRun",
    "RoleRunTicket",
    "RoleRunTicketWire",
    "RoleRunUncertainty",
    "RoleRunVerdict",
    "TrajectoryJudgement",
    "TrajectoryJudgementModel",
    "request_role_run",
    "run_role_run",
    "run_role_run_service",
    "the_role_run_question",
    "the_role_run_run",
    "the_role_run_ticket",
]


# --------------------------------------------------------------------------- #
# the result on the wire
# --------------------------------------------------------------------------- #


class RoleRunRuleCitation(Result):
    """A rule the card cites, with the cases against it, as the wire carries it.

    The fields are
    :class:`labcairn.roles.guidance.RuleCitation`'s own, spelled out because
    the role outputs are frozen dataclasses and have no schema of their own.
    """

    rule_id: str
    version: int
    statement: str
    counterexamples: tuple[str, ...] = ()


class RoleRunCardClaim(Result):
    """One claim on a card, as the wire carries it."""

    text: str
    kind: str
    evidence_ref: str | None = None
    issue_key: str | None = None
    advisor_quote: str | None = None


class RoleRunUncertainty(Result):
    """How sure the card is, as the wire carries it."""

    kind: str
    what_is_uncertain: str
    missing: tuple[str, ...] = ()


class RoleRunCandidate(Result):
    """Role A's candidate, as the wire carries it.

    The role outputs are frozen dataclasses rather than pydantic models, so
    the run's result carries them as these validated shapes: the same
    fields, and nothing added. ``role_id`` and ``role_version`` are the
    contract the candidate was made under -- the pair a replay opens.
    """

    role_id: str
    role_version: int
    issue_key: str
    issue_type: str
    edit_action_id: str | None
    alignment: str
    advisor_quote: str
    note: str


class RoleRunCard(Result):
    """Role B's card, as the wire carries it. The fields are the card's own."""

    role_id: str
    role_version: int
    target_locator: str
    issue_type: str
    severity: str
    reason: str
    evidence_refs: tuple[str, ...]
    suggested_next_action: str
    uncertainty: RoleRunUncertainty
    claims: tuple[RoleRunCardClaim, ...] = ()
    style_notes: tuple[str, ...] = ()
    rule_refs: tuple[RoleRunRuleCitation, ...] = ()
    historical_case_refs: tuple[str, ...] = ()
    counterexamples_or_limits: tuple[str, ...] = ()


class RoleRunVerdict(Result):
    """Role C's verdict, as the wire carries it. The fields are the verdict's own."""

    role_id: str
    role_version: int
    reviewed_locator: str
    reviewed_issue_type: str
    verdict: str
    grade: str
    counter_evidence: tuple[RoleRunRuleCitation, ...] = ()
    repair_advice: str
    handover_reason: str | None


class RoleRunRun(Result):
    """What a run produced, as the wire carries it.

    The layer's :class:`RoleRunResult` is the model; the role outputs it
    holds are spelled out as the validated shapes above, because a frozen
    dataclass has no JSON schema of its own and the API's document is read
    from schemas. **Nothing is added and nothing is re-spelled**: a field
    the layer's result carries reaches this shape unchanged, so the wire
    and the CLI's ``--json`` are the same bytes.
    """

    roles: tuple[str, ...]
    #: The model's own words, when the run asked for one. ``None`` is the
    #: ordinary state of a run whose judgements were all supplied: nothing
    #: was asked, so there is no answer to carry.
    answer: str | None
    #: The exchange record the model call landed in, when one was made.
    exchange_event_id: str | None
    candidate: RoleRunCandidate | None = None
    card: RoleRunCard | None = None
    verdict: RoleRunVerdict | None = None


class RoleRunTicketWire(Result):
    """The question, written down, as the wire carries it.

    The layer's :class:`RoleRunTicket` is the model. **This is the ask's
    whole output, and it spends nothing**: the approval it names is
    *pending* -- a person grants it over the approval door, or does not --
    and no role has run. The prompt and the excerpts are carried so the
    caller can read exactly what a run would send before it consents.
    """

    roles: tuple[str, ...]
    #: The contracts the roles run under, each with the role id and the
    #: version that was read.
    contracts: tuple[dict[str, Any], ...]
    #: The question, as it will be asked.
    prompt: str
    #: The material that leaves the machine, and nothing else.
    excerpts: tuple[str, ...]
    #: Where the material is: the workspace path, the root it landed in and
    #: the key it holds.
    material: dict[str, str]
    #: Who the model call would ask, and where the material is declared.
    plan: dict[str, str]
    #: The approval the run will spend, when a judgement is missing and one
    #: was asked for. It is *pending*; the run refuses to spend it until a
    #: person grants it.
    approval_id: str | None
    asked_at: datetime


def the_role_run_ticket(ticket: RoleRunTicket) -> RoleRunTicketWire:
    """The ticket, as the wire carries it.

    **One conversion, one place**, for the same reason the run's is: the
    API and the CLI read the same bytes from the same function.
    """
    from dataclasses import asdict

    return RoleRunTicketWire(
        roles=tuple(contract.role_id for contract in ticket.contracts),
        contracts=tuple(asdict(contract) for contract in ticket.contracts),
        prompt=ticket.prompt,
        excerpts=ticket.excerpts,
        material=asdict(ticket.question.material),
        plan=asdict(ticket.plan),
        approval_id=str(ticket.approval_id) if ticket.approval_id is not None else None,
        asked_at=ticket.asked_at,
    )


def _the_rule_citation_wire(citation: RuleCitation) -> RoleRunRuleCitation:
    """The citation, as the wire carries it."""
    return RoleRunRuleCitation(
        rule_id=citation.rule_id,
        version=citation.version,
        statement=citation.statement,
        counterexamples=citation.counterexamples,
    )


def _the_candidate_wire(candidate: TrajectoryCandidate) -> RoleRunCandidate:
    """The candidate, as the wire carries it."""
    return RoleRunCandidate(
        role_id=candidate.role_id,
        role_version=candidate.role_version,
        issue_key=candidate.issue_key,
        issue_type=candidate.issue_type,
        edit_action_id=candidate.edit_action_id,
        alignment=candidate.alignment,
        advisor_quote=candidate.advisor_quote,
        note=candidate.note,
    )


def _the_card_wire(card: GuidanceCard) -> RoleRunCard:
    """The card, as the wire carries it."""
    return RoleRunCard(
        role_id=card.role_id,
        role_version=card.role_version,
        target_locator=card.target_locator,
        issue_type=card.issue_type,
        severity=card.severity,
        reason=card.reason,
        evidence_refs=card.evidence_refs,
        suggested_next_action=card.suggested_next_action,
        uncertainty=RoleRunUncertainty(
            kind=card.uncertainty.kind,
            what_is_uncertain=card.uncertainty.what_is_uncertain,
            missing=card.uncertainty.missing,
        ),
        claims=tuple(
            RoleRunCardClaim(
                text=claim.text,
                kind=claim.kind,
                evidence_ref=claim.evidence_ref,
                issue_key=claim.issue_key,
                advisor_quote=claim.advisor_quote,
            )
            for claim in card.claims
        ),
        style_notes=card.style_notes,
        rule_refs=tuple(_the_rule_citation_wire(item) for item in card.rule_refs),
        historical_case_refs=card.historical_case_refs,
        counterexamples_or_limits=card.counterexamples_or_limits,
    )


def _the_verdict_wire(verdict: ReviewVerdict) -> RoleRunVerdict:
    """The verdict, as the wire carries it."""
    return RoleRunVerdict(
        role_id=verdict.role_id,
        role_version=verdict.role_version,
        reviewed_locator=verdict.reviewed_locator,
        reviewed_issue_type=verdict.reviewed_issue_type,
        verdict=verdict.verdict,
        grade=verdict.grade,
        counter_evidence=tuple(_the_rule_citation_wire(item) for item in verdict.counter_evidence),
        repair_advice=verdict.repair_advice,
        handover_reason=verdict.handover_reason,
    )


def the_role_run_run(result: RoleRunResult) -> RoleRunRun:
    """The run's result, as the wire carries it.

    **One conversion, one place.** The API's route and the CLI's ``--json``
    both pass through this function, so the two surfaces serve the same
    bytes by construction rather than by a promise that somebody will keep
    two serialisations in step.
    """
    return RoleRunRun(
        roles=result.roles,
        answer=result.answer,
        exchange_event_id=result.exchange_event_id,
        candidate=None if result.candidate is None else _the_candidate_wire(result.candidate),
        card=None if result.card is None else _the_card_wire(result.card),
        verdict=None if result.verdict is None else _the_verdict_wire(result.verdict),
    )


# --------------------------------------------------------------------------- #
# the service's assembly point
# --------------------------------------------------------------------------- #


class RoleRunBackend:
    """The service's assembly point for a real-model role-loop run.

    **This is the service's wiring, not a consent of its own** — the same
    shape the suggestion loop's backend holds. A service that carries no
    backend refuses a run that needs a model judgement with
    ``role_run_no_provider`` — the refusal, not a failure, is the honest
    state of a service the owner has not authorised — and a run whose
    judgements are all supplied needs no backend at all, because it
    reaches no wire and spends nothing.

    ``grants`` are the material-purpose grants the model call is judged
    against, and ``destination`` is the destination they name. Neither is
    read from anywhere here: the service wires them, and the run spends
    through the consent gates like every other call that leaves the
    machine.
    """

    def __init__(
        self,
        *,
        provider: str,
        model: str,
        send: Callable[[str], ModelInvocation],
        capabilities: ProviderCapabilities | None = None,
        grants: Sequence[Grant] = (),
        destination: str = "",
    ) -> None:
        self.provider = provider
        self.model = model
        self.send = send
        self.capabilities = capabilities
        self.grants = grants
        self.destination = destination


def run_role_run_service(
    context: ApplicationContext,
    ticket: RoleRunTicket,
    *,
    backend: RoleRunBackend | None,
    at: datetime,
) -> RoleRunRun:
    """Run the roles a ticket names, through the service's backend.

    **The backend is the service's wiring, and its absence is a refusal
    with a name.** A run that needs a model judgement and finds no backend
    is refused with ``role_run_no_provider`` -- the honest state of a
    service the owner has not authorised -- rather than simulated, because
    an invented judgement would put words in a model's mouth that no model
    said. A run whose judgements are all supplied needs no backend, and
    reaches no wire.

    **The consent has already been given.** The ticket carries the approval
    id the ask minted; a person granted it over the approval door
    (``POST /approvals/{id}/grant`` or ``task approval-grant``) before this
    was called, and the run spends it through
    :func:`labcairn.application.model_request.request_model` like every
    other call that leaves the machine. This operation mints no consent of
    its own.

    :raises ApplicationRefusedError: the run needs a model judgement and no
        backend is wired; the consent refused the call; the answer did not
        carry a judgement for a role the request named; or a role refused
        its own judgement.
    """
    if backend is None:
        missing = _missing_judgements(
            ticket.request, tuple(contract.role_id for contract in ticket.contracts)
        )
        if missing:
            # **This refusal belongs to the service, so the service records
            # it.** It never reaches `run_role_run`, whose wrapper records
            # the refusals of the spend; recording it here keeps every
            # refusal on the task's path a fact the log holds, and keeps
            # the two wrappers from recording the same refusal twice.
            refused = ApplicationRefusedError(
                ApplicationRefusal.ROLE_RUN_NO_PROVIDER,
                "no real-model transport is wired into this service, so there is"
                " nothing to ask. A run that needs a model judgement is refused"
                " rather than simulated: an invented judgement would put words in"
                " a model's mouth that no model said.",
            )
            records.record_refusal(
                context,
                reason=refused.reason.value,
                message=refused.detail,
                asked_for=_asked_for_run(ticket),
                now=at,
            )
            raise refused
        return the_role_run_run(run_role_run(context, ticket, grants=(), at=at))
    return the_role_run_run(
        run_role_run(
            context,
            ticket,
            grants=backend.grants,
            at=at,
            send=backend.send,
            capabilities=backend.capabilities,
        )
    )
