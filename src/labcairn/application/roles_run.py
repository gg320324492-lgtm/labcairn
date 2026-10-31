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

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final, Protocol, cast

from pydantic import create_model

from labcairn.application.approvals import ApprovalRequest, ApprovalUse, request_approval
from labcairn.application.context import ApplicationContext
from labcairn.application.model_request import ModelInvocation, request_model
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
    """

    roles: tuple[str, ...]
    project_id: str
    issue_key: str
    version_ids: tuple[str, ...] = ()
    rule_id: str | None = None
    target_locator: str | None = None
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
    """

    provider: str
    model: str
    root_id: str
    resource_key: str
    purpose: str
    destination: str
    subject_ref: str
    material_ref: str | None = None


# --------------------------------------------------------------------------- #
# what the loop writes down, and what it returns
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RoleRunTicket:
    """The question, written down.

    **This is the first step's whole output.** It names the roles that will
    run, the contracts they run under, the material, the prompt, and the
    consent the run will need -- and **nothing has been spent**: the
    approval it carries is *pending*, no exchange was recorded, and no role
    ran.
    """

    request: RoleRunRequest
    contracts: tuple[AgentRoleSpec, ...]
    prompt: str
    excerpts: tuple[str, ...]
    plan: ModelCallPlan
    use: ApprovalUse
    approval_id: ApprovalId | None
    rule_citation: RuleCitation | None
    asked_at: datetime


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


#: The document each role's judgement takes, by the role's id.
_JUDGEMENT_MODELS: Final[dict[str, type[LabCairnModel]]] = {
    "trajectory": TrajectoryJudgementModel,
    "guidance": GuidanceJudgementModel,
    "critique": CritiqueJudgementModel,
}


class _JudgementDocument(Protocol):
    """The document the model was asked for, read one part at a time.

    **The parts are the roles the caller named and did not supply**, so a
    document read through this shape has a part for each of them and for
    nothing else.
    """

    trajectory: TrajectoryJudgementModel
    guidance: GuidanceJudgementModel
    critique: CritiqueJudgementModel


def _schema_for(roles: tuple[str, ...]) -> type[LabCairnModel]:
    """The document the model is asked for: one part per role that needs a judgement.

    **The parts are exactly the roles the caller named and did not supply.**
    A part for a role the caller did not ask for is an **extra key**, and
    the schema forbids extra keys -- so the model cannot volunteer a card
    for a role nobody asked for, and the loop cannot run one.
    """
    fields: dict[str, Any] = {role: (_JUDGEMENT_MODELS[role], ...) for role in roles}
    return cast(
        "type[LabCairnModel]",
        create_model("RoleJudgements", __base__=LabCairnModel, **fields),
    )


# --------------------------------------------------------------------------- #
# the two steps
# --------------------------------------------------------------------------- #


def request_role_run(
    context: ApplicationContext,
    request: RoleRunRequest,
    *,
    plan: ModelCallPlan,
    expires_at: datetime,
    now: datetime | None = None,
) -> RoleRunTicket:
    """Write the question down, and spend nothing.

    The request names the roles; this operation reads their contracts, reads
    the material they will work on, builds the prompt, and -- **only if some
    judgement is missing** -- asks the consent layer for the approval the run
    will spend. The approval it asks for is **pending**: nothing is granted
    and nothing is consumed, because a grant is a person's act and a spend
    is the run's.

    :raises ApplicationRefusedError: the request names no role, a role the
        loop does not know, the same role twice, or the critique without the
        guidance that makes a card to review; a named role has no contract,
        or its contract does not list the capability the run exercises; the
        memory holds no rule under the id the request names; or the policy
        denied the request the approval is for.
    """
    moment = now if now is not None else datetime.now(UTC)
    roles = _the_roles(request.roles)
    contracts = tuple(_the_contract(context, role_id=role_id) for role_id in roles)

    missing = _missing_judgements(request, roles)
    if missing:
        for contract in contracts:
            contract.require_allowed(CapabilityId.MODEL_REQUEST)

    material = _the_material(context, request)
    prompt = _the_prompt(request, contracts, material)
    excerpts = material.excerpts
    use = ApprovalUse(
        capability=CapabilityId.MODEL_REQUEST,
        arguments=ModelRequestArgs(
            provider=plan.provider,
            model=plan.model,
            path=plan.resource_key,
            excerpts=excerpts,
            purpose=plan.purpose,
        ).model_dump(),
        root_id=plan.root_id,
        resource_key=plan.resource_key,
    )
    approval_id: ApprovalId | None = None
    if missing:
        asked = request_approval(
            context,
            ApprovalRequest(use=use, expires_at=expires_at),
            now=moment,
        )
        approval_id = asked.approval.approval_id
    return RoleRunTicket(
        request=request,
        contracts=contracts,
        prompt=prompt,
        excerpts=excerpts,
        plan=plan,
        use=use,
        approval_id=approval_id,
        rule_citation=material.rule_citation,
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

    :raises ApplicationRefusedError: the run needs a model judgement and no
        provider invocation was given; the consent refused the call; the
        answer did not satisfy the schema it was asked for; or a role
        refused its own judgement.
    """
    request = ticket.request
    roles = _the_roles(request.roles)
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
                ApplicationRefusal.ARGUMENTS_INVALID,
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
            use=ticket.use,
            subject_ref=ticket.plan.subject_ref,
            destination=ticket.plan.destination,
            material_ref=ticket.plan.material_ref,
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
        document = captured[0].structured if captured else None
        judgements = _the_judgements(document, missing, judgements)

    result = _run_the_roles(context, ticket, roles, judgements)
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
            ApplicationRefusal.ARGUMENTS_INVALID,
            "the request names no role, and a request that asks for nothing has nothing to run",
        )
    unknown = sorted(set(named) - ROLE_IDS)
    if unknown:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the request names {unknown!r}, and the loop runs only"
            f" {sorted(ROLE_IDS)}; a role the loop does not know is not routed"
            " by a default",
        )
    repeated = sorted({role for role in named if named.count(role) > 1})
    if repeated:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the request names {repeated!r} more than once, and a role that runs"
            " twice is not the role the caller asked for",
        )
    if "critique" in named and "guidance" not in named:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
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
class _Material:
    """What the run reads: the chain's own words, and the rule the card cites."""

    issue_key: str
    comment_texts: tuple[str, ...]
    version_ids: tuple[str, ...]
    edit_ids: tuple[str, ...]
    rule_statement: str | None
    rule_counterexamples: tuple[str, ...]
    rule_citation: RuleCitation | None

    @property
    def excerpts(self) -> tuple[str, ...]:
        """The material that leaves the machine, and nothing else.

        **The loop's own instructions are not excerpts** -- they are the
        repository's text, not the reader's material -- and neither is the
        model's own earlier words. The approval binds this set.
        """
        parts = list(self.comment_texts)
        if self.rule_statement is not None:
            parts.append(self.rule_statement)
        parts.extend(self.rule_counterexamples)
        return tuple(parts)


def _the_material(context: ApplicationContext, request: RoleRunRequest) -> _Material:
    """The chain's comments and the memory's rule, read through the layer.

    **The chain is read through the role that reads it**, so the material
    the loop sends is the same material the roles will work on, and the
    refusals the read raises are the roles' own.

    :raises ApplicationRefusedError: the memory holds no rule under the id
        the request names; the chain holds no comment under the issue key;
        or a version named is outside the project's graph, or the accepted
        edges leave the order ambiguous.
    """
    from labcairn.roles.guidance import cite_rule
    from labcairn.roles.trajectory import TrajectoryInput, read_trajectory

    chain = read_trajectory(
        context,
        trajectory_input=TrajectoryInput(
            project_id=request.project_id,
            version_ids=request.version_ids,
            issue_keys=(request.issue_key,),
        ),
    )
    texts = tuple(comment.comment_text for comment in chain.comments)
    statement: str | None = None
    counterexamples: tuple[str, ...] = ()
    citation: RuleCitation | None = None
    if request.rule_id is not None:
        citation = cite_rule(context, rule_id=request.rule_id)
        statement = citation.statement
        counterexamples = citation.counterexamples
    return _Material(
        issue_key=request.issue_key,
        comment_texts=texts,
        version_ids=chain.ordered_version_ids,
        edit_ids=tuple(edit.edit_action_id for edit in chain.edits),
        rule_statement=statement,
        rule_counterexamples=counterexamples,
        rule_citation=citation,
    )


def _the_prompt(
    request: RoleRunRequest,
    contracts: Sequence[AgentRoleSpec],
    material: _Material,
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
    if material.version_ids:
        lines.append(
            f"the versions, in the accepted edges' order: {', '.join(material.version_ids)}"
        )
    if material.comment_texts:
        lines.append("the advisor's comment, in their own words:")
        lines.extend(f"  {text}" for text in material.comment_texts)
    if material.edit_ids:
        lines.append(f"the changes that answered it: {', '.join(material.edit_ids)}")
    if material.rule_statement is not None:
        lines.append("the rule the card cites:")
        lines.append(f"  {material.rule_statement}")
        if material.rule_counterexamples:
            lines.append("the cases against that rule:")
            lines.extend(f"  - {item}" for item in material.rule_counterexamples)
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
        trajectory = TrajectoryJudgement(
            issue_type=trajectory_part.issue_type,
            alignment=trajectory_part.alignment,
            advisor_quote=trajectory_part.advisor_quote,
            note=trajectory_part.note,
            edit_action_id=trajectory_part.edit_action_id,
        )
    if "guidance" in missing:
        guidance_part = parsed.guidance
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
        critique = CritiqueJudgement(
            verdict=critique_part.verdict,
            repair_advice=critique_part.repair_advice,
            handover_reason=critique_part.handover_reason,
        )
    return _Judgements(trajectory=trajectory, guidance=guidance, critique=critique)


def _the_judgement[T](judgement: T | None, role_id: str) -> T:
    """The judgement a named role works from.

    **A named role always has one.** A role the caller named and did not
    supply a judgement for is one the model was asked for, and the model
    path refuses an answer that does not carry it -- so a role without a
    judgement here is a wiring fault, and it is named rather than skipped.
    Skipping it would be the one thing this module must never do: **a role
    the caller asked for that silently did not run.**

    :raises ApplicationRefusedError: no judgement reached the role.
    """
    if judgement is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the request named {role_id!r} and no judgement reached it",
        )
    return judgement


def _run_the_roles(
    context: ApplicationContext,
    ticket: RoleRunTicket,
    roles: tuple[str, ...],
    judgements: _Judgements,
) -> RoleRunResult:
    """Run the roles named, in order, each through its own operation."""
    from labcairn.roles.critique import review_card
    from labcairn.roles.guidance import Uncertainty, build_card
    from labcairn.roles.trajectory import propose_candidate

    request = ticket.request
    contracts = {contract.role_id: contract for contract in ticket.contracts}
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
                target_locator=request.target_locator or f"chain:{request.issue_key}",
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
                rule_refs=(ticket.rule_citation,) if ticket.rule_citation is not None else (),
            )
        else:
            critique_judgement = _the_judgement(judgements.critique, role_id)
            if card is None:
                raise ApplicationRefusedError(
                    ApplicationRefusal.ARGUMENTS_INVALID,
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
    "ClaimModel",
    "CritiqueJudgement",
    "CritiqueJudgementModel",
    "GuidanceJudgement",
    "GuidanceJudgementModel",
    "ModelCallPlan",
    "RoleRunRequest",
    "RoleRunResult",
    "RoleRunTicket",
    "TrajectoryJudgement",
    "TrajectoryJudgementModel",
    "request_role_run",
    "run_role_run",
]
