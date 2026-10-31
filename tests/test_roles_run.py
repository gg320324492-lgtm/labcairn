"""The loop, on demand: the roles a request names, and only those.

**What is under test.** LC-P2-16 T05: ``application.roles_run`` — the
operation that routes a request to the roles it names, the two-step action
that asks before it spends, and the refusals the roles raise through it.

====================================================  =========================
     the loop runs the roles it names                  a role the caller did
                                                          not ask for is not
                                                          run, not paid for, and
                                                          not given a contract
     asking asks before it spends                      the request writes the
                                                          question down and
                                                          spends nothing; the
                                                          run spends once, and
                                                          a refusal at the gate
                                                          spends nothing
     the refusals are the roles' own                   an alignment outside the
                                                          vocabulary, a claim
                                                          without evidence and a
                                                          quote the chain does not
                                                          hold are refused by the
                                                          roles, through the loop
====================================================  =========================

**Why the refusals are witnessed one at a time.** A test that watches two
refusals proves one of them at a time: the first assertion that fails is
the one that tells the story. So each refusal the loop can raise has a
test of its own, and the test names the reason it expects.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from feedback_chain_fixtures import ChainEnv, a_comment, build_chain
from test_store_support import StoreEnv
from test_store_support import env as _shared_env

from labcairn.application.approvals import grant_approval
from labcairn.application.context import ApplicationContext
from labcairn.application.events import read_events
from labcairn.application.model_request import ModelInvocation
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.application.roles_run import (
    CritiqueJudgement,
    GuidanceJudgement,
    ModelCallPlan,
    RoleRunRequest,
    TrajectoryJudgement,
    request_role_run,
    run_role_run,
)
from labcairn.db.models import EditActionRow
from labcairn.db.repository import list_approvals
from labcairn.guidance.rules import confirm_rule, propose_rule, record_counterexample
from labcairn.papers.feedback import record_feedback, set_issue_key
from labcairn.providers.capabilities import (
    ALL_CAPABILITIES,
    Capability,
    CapabilityOutcome,
    ProviderCapabilities,
)
from labcairn.roles.guidance import CardClaim
from labcairn.roles.refusals import RoleRefusal
from labcairn.roles.spec import FORBIDDEN_ACTIONS, AgentRoleSpec, define_role_spec
from labcairn.runtime.event import EventType
from labcairn.security.capabilities import CapabilityId
from labcairn.security.permissions import Grant

pytestmark = pytest.mark.integration

env = _shared_env

MOMENT = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)
EXPIRES = MOMENT.replace(year=2027)

KEY = "iss-gold-a-r1"
COMMENT = "Define the parameter."
QUOTE = "Define the parameter"

RULE = (
    "When the advisor asks what a parameter is, the answer names the quantity"
    " it estimates and where it comes from."
)
COUNTEREXAMPLE = "The parameter was defined in the previous draft, and the advisor still asked."

DESTINATION = "api.model-provider.example"
OTHER_DESTINATION = "api.other-provider.example"
MATERIAL_REF = "proj-1/manuscript.docx"

OBJECTIVES: dict[str, str] = {
    "trajectory": "Align the advisor's comments with the edits actually made.",
    "guidance": "Turn a confirmed case into a card a student can act on.",
    "critique": "Review a card independently and retrieve the counter-evidence.",
}


@dataclass
class Loop:
    """The chain, the rule, and the contracts the roles work under.

    **The contracts are defined by the test, not by the fixture.** The
    fixture defines the two the loop needs for a candidate and a card, and
    the critique's contract is defined on demand — because one of the
    properties under test is what the loop does when a contract is missing
    or when a contract does not list the capability the run exercises, and
    a fixture that defined everything could not show either.
    """

    context: ApplicationContext
    chain: ChainEnv
    key: str
    quote: str
    rule_id: str
    specs: dict[str, AgentRoleSpec] = field(default_factory=dict)


@pytest.fixture()
def loop(env: StoreEnv, tmp_path: Path) -> Loop:
    """A chain with a keyed comment and its edit, and a confirmed rule with a case against it."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    store = env.store()
    chain = build_chain(store, workspace_root, comments=(a_comment("201"),))
    (event,) = record_feedback(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.version_id,
        now=MOMENT,
    )
    set_issue_key(chain.context, feedback_id=event.feedback_id, issue_key=KEY, now=MOMENT)
    session = chain.context.store.session
    session.add(
        EditActionRow(
            edit_action_id="edit-201",
            feedback_id=event.feedback_id,
            version_edge_id=chain.edge_id,
            actor_kind="student",
            grade="observed",
            created_at=MOMENT,
        )
    )
    session.flush()
    rule = propose_rule(
        chain.context,
        issue_type="method_and_hypothesis",
        statement=RULE,
        rule_context="A methods section whose parameter is never named.",
        scope="Empirical papers in this group's field.",
        example="The comment of the run, on the methods paragraph.",
        sources=(KEY,),
        proposed_by="a-mentor",
        now=MOMENT,
    )
    confirm_rule(chain.context, rule_id=rule.rule_id, confirmed_by="the-advisor", now=MOMENT)
    record_counterexample(
        chain.context,
        rule_id=rule.rule_id,
        statement=COUNTEREXAMPLE,
        recorded_by="a-reader",
        now=MOMENT,
    )
    built = Loop(
        context=chain.context,
        chain=chain,
        key=KEY,
        quote=QUOTE,
        rule_id=rule.rule_id,
    )
    built.specs["trajectory"] = _spec(built.context, "trajectory")
    built.specs["guidance"] = _spec(built.context, "guidance")
    return built


def _spec(
    context: ApplicationContext,
    role_id: str,
    *,
    capability: CapabilityId = CapabilityId.MODEL_REQUEST,
) -> AgentRoleSpec:
    """One role's contract, with the capability the run exercises."""
    return define_role_spec(
        context,
        role_id=role_id,
        role_version=1,
        objective=OBJECTIVES[role_id],
        input_schema="Input",
        output_schema="Output",
        allowed_capabilities=(capability,),
        forbidden_actions=FORBIDDEN_ACTIONS,
        allowed_data_purposes=("guidance_review",),
        provider_routing_policy="single-provider-per-call",
        cost_budget=None,
        token_budget=4000,
        timeout_seconds=120,
        retry_policy="no-retry",
        fallback_policy="abstain",
        abstain_conditions=("material_under_two_comments",),
        escalation_conditions=("a_conflict_between_two_rules",),
        prompt_template_version=f"{role_id}-v1",
        model_config_ref="configs/model.json",
        now=MOMENT,
    )


def _plan() -> ModelCallPlan:
    """What the model call needs from the caller."""
    return ModelCallPlan(
        provider="fake",
        model="scripted",
        root_id="source:0",
        resource_key="manuscript.docx",
        purpose="guidance_review",
        destination=DESTINATION,
        subject_ref="proj-1",
        material_ref=MATERIAL_REF,
    )


def _grants(destination: str = DESTINATION) -> list[Grant]:
    """The material-purpose grants the request is judged against."""
    return [
        Grant(
            grant_id="g-model-1",
            subject_ref="proj-1",
            permission="external_transmit",
            purpose="transmit",
            scope="proj-1/**",
            destination=destination,
            granted_by="Dr. Chen",
            granted_at=MOMENT,
            expires_at=None,
            state="active",
            withdrawn_at=None,
            withdrawn_by=None,
            withdrawal_reason=None,
        )
    ]


def _probed(*capable: Capability) -> ProviderCapabilities:
    """A probe record that licenses exactly the capabilities named."""
    outcomes = {
        capability: (
            CapabilityOutcome.OK if capability in capable else CapabilityOutcome.UNSUPPORTED
        )
        for capability in ALL_CAPABILITIES
    }
    return ProviderCapabilities.from_outcomes(
        endpoint_fingerprint="fp-" + "p" * 16,
        model="scripted",
        protocol="openai-chat",
        outcomes=outcomes,
        unsupported_reason=dict.fromkeys(
            ALL_CAPABILITIES, "the probe asked and it did not do the thing"
        ),
    )


def _invocation(structured: Mapping[str, object] | None) -> ModelInvocation:
    """One call's record, in the provider layer's wire form."""
    return ModelInvocation(
        answer="the model's answer",
        provider="fake",
        model="scripted",
        exchanges=(
            {
                "provider": "fake",
                "model": "scripted",
                "transcript_step": "the-judgements",
                "prompt_digest": "a" * 64,
                "tool_names": [],
                "outbound": {"destination": DESTINATION, "digest": "b" * 64},
                "provider_attempts": 1,
                "observed_at": MOMENT.isoformat(),
                "usage_input": {"kind": "known", "tokens": 120},
                "usage_output": {"kind": "known", "tokens": 40},
            },
        ),
        credential_fingerprint="fp-" + "c" * 16,
        cost_micros=1200,
        structured=structured,
    )


def _trajectory_answer(**overrides: object) -> dict[str, object]:
    """The document role A's judgement takes."""
    answer: dict[str, object] = {
        "issue_type": "method_and_hypothesis",
        "alignment": "partial",
        "advisor_quote": QUOTE,
        "note": "the change answered the wording, not the missing quantity.",
    }
    answer.update(overrides)
    return answer


def _guidance_answer(**overrides: object) -> dict[str, object]:
    """The document role B's judgement takes."""
    answer: dict[str, object] = {
        "issue_type": "method_and_hypothesis",
        "severity": "major",
        "reason": "the parameter is never named.",
        "suggested_next_action": "name the quantity the estimate is of.",
        "uncertainty_kind": "low",
        "what_is_uncertain": "the rule's scope",
        "claims": [],
        "style_notes": [],
    }
    answer.update(overrides)
    return answer


def _critique_answer(**overrides: object) -> dict[str, object]:
    """The document role C's judgement takes."""
    answer: dict[str, object] = {
        "verdict": "supported",
        "repair_advice": "none needed; the evidence is the chain's",
        "handover_reason": None,
    }
    answer.update(overrides)
    return answer


def _request(
    loop: Loop,
    *,
    roles: tuple[str, ...],
    rule_id: str | None = None,
    trajectory: TrajectoryJudgement | None = None,
    guidance: GuidanceJudgement | None = None,
    critique: CritiqueJudgement | None = None,
) -> RoleRunRequest:
    """A request for the roles named, on the chain the fixture planted."""
    return RoleRunRequest(
        roles=roles,
        project_id=loop.chain.project_id,
        issue_key=loop.key,
        version_ids=(loop.chain.version_id, loop.chain.second_version_id),
        rule_id=rule_id,
        trajectory=trajectory,
        guidance=guidance,
        critique=critique,
    )


def _trajectory_judgement(**overrides: object) -> TrajectoryJudgement:
    """The judgement role A works from, as the rehearsal supplied it."""
    judgement: dict[str, object] = {
        "issue_type": "method_and_hypothesis",
        "alignment": "partial",
        "advisor_quote": QUOTE,
        "note": "the change answered the wording, not the missing quantity.",
        "edit_action_id": "edit-201",
    }
    judgement.update(overrides)
    return TrajectoryJudgement(**judgement)  # type: ignore[arg-type]


def _guidance_judgement(**overrides: object) -> GuidanceJudgement:
    """The judgement role B works from, as the rehearsal supplied it."""
    judgement: dict[str, object] = {
        "issue_type": "method_and_hypothesis",
        "severity": "major",
        "reason": "the parameter is never named.",
        "suggested_next_action": "name the quantity the estimate is of.",
        "uncertainty_kind": "low",
        "what_is_uncertain": "the rule's scope",
        "claims": (),
        "style_notes": (),
    }
    judgement.update(overrides)
    return GuidanceJudgement(**judgement)  # type: ignore[arg-type]


def _critique_judgement(**overrides: object) -> CritiqueJudgement:
    """The judgement role C works from, as the rehearsal supplied it."""
    judgement: dict[str, object] = {
        "verdict": "supported",
        "repair_advice": "none needed; the evidence is the chain's",
        "handover_reason": None,
    }
    judgement.update(overrides)
    return CritiqueJudgement(**judgement)  # type: ignore[arg-type]


def _capture(call: object) -> ApplicationRefusedError:
    """The refusal a call that must raise carries."""
    assert callable(call)
    try:
        call()
    except ApplicationRefusedError as refused:
        return refused
    raise AssertionError("the call was expected to refuse, and it did not")


def _role_reason(call: object) -> RoleRefusal:
    """The role's refusal an expected error carries, so the test fails loudly."""
    refused = _capture(call)
    assert refused.reason.value.startswith("role_"), (
        f"expected a role refusal, saw {refused.reason.value!r}"
    )
    return RoleRefusal(refused.reason.value.removeprefix("role_"))


# --------------------------------------------------------------------------- #
# the loop runs the roles it names, and only those
# --------------------------------------------------------------------------- #


def test_the_loop_runs_the_roles_the_request_names_and_no_others(loop: Loop) -> None:
    """A role the caller did not ask for is not run, not paid for, and not given a contract.

    **The card's judgement is supplied and the card is still not built** —
    the loop runs the roles the request names, so a judgement nobody asked
    for is not a request for that role.
    """
    ticket = request_role_run(
        loop.context,
        _request(
            loop,
            roles=("trajectory",),
            trajectory=_trajectory_judgement(),
            guidance=_guidance_judgement(),
        ),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    assert [spec.role_id for spec in ticket.contracts] == ["trajectory"], (
        "a role nobody asked for is not given a contract"
    )
    assert ticket.approval_id is None, "nothing was needed, so nothing was asked for"

    result = run_role_run(loop.context, ticket, grants=_grants(), at=MOMENT)
    assert result.roles == ("trajectory",)
    assert result.candidate is not None
    assert result.card is None, "the card belongs to a role the caller did not ask for"
    assert result.verdict is None
    assert result.answer is None, "no model call was needed, and none was made"
    assert result.exchange_event_id is None


def test_the_roles_run_in_the_dependency_order_whatever_order_they_were_named_in(
    loop: Loop,
) -> None:
    """The critique reviews a card, so the card is made first.

    **The caller named them in the other order**, and the loop runs them
    in the order the roles depend on each other — a caller that got the
    order wrong does not get a critique of nothing.
    """
    loop.specs["critique"] = _spec(loop.context, "critique")
    ticket = request_role_run(
        loop.context,
        _request(
            loop,
            roles=("critique", "guidance"),
            rule_id=loop.rule_id,
            guidance=_guidance_judgement(),
            critique=_critique_judgement(),
        ),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    assert [spec.role_id for spec in ticket.contracts] == ["guidance", "critique"]
    result = run_role_run(loop.context, ticket, grants=_grants(), at=MOMENT)
    assert result.roles == ("guidance", "critique")
    assert result.card is not None
    assert result.verdict is not None
    assert result.verdict.reviewed_locator == result.card.target_locator


# --------------------------------------------------------------------------- #
# asking asks before it spends
# --------------------------------------------------------------------------- #


def test_asking_writes_the_question_down_and_spends_nothing(loop: Loop) -> None:
    """The request records the question, and spends nothing to record it.

    **The approval it asks for is pending**, no exchange was written, and
    no role ran: asking is a question, and a question nobody answered is
    not consent.
    """
    ticket = request_role_run(
        loop.context,
        _request(loop, roles=("trajectory", "guidance"), rule_id=loop.rule_id),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    assert ticket.approval_id is not None, "the run will need a judgement, so it needs consent"
    rows = list_approvals(loop.context.store.session, loop.context.task_id)
    assert [row.state for row in rows] == ["pending"], "the question is written down and ungranted"
    page = read_events(loop.context)
    assert not [event for event in page.events if event.type is EventType.MODEL_EXCHANGED], (
        "asking reached no wire"
    )

    assert QUOTE in ticket.prompt, "the question carries the advisor's own words"
    assert RULE in ticket.prompt, "and the rule the card will cite"
    assert COUNTEREXAMPLE in ticket.prompt, "and the cases against that rule"
    assert "trajectory" in ticket.prompt and "guidance" in ticket.prompt
    assert "critique" not in ticket.prompt, "the question does not ask for a role nobody named"
    assert ticket.excerpts == (COMMENT, RULE, COUNTEREXAMPLE), (
        "the approval binds the material that leaves, and it is the material"
    )


def test_the_run_spends_the_consent_once_and_records_the_call(loop: Loop) -> None:
    """The run spends the approval, records the exchange, and cannot spend it twice."""
    ticket = request_role_run(
        loop.context,
        _request(loop, roles=("trajectory",)),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    assert ticket.approval_id is not None
    grant_approval(loop.context, ticket.approval_id, now=MOMENT)

    answer = {"trajectory": _trajectory_answer()}
    result = run_role_run(
        loop.context,
        ticket,
        grants=_grants(),
        at=MOMENT,
        send=lambda prompt: _invocation(answer),
        capabilities=_probed(Capability.STRUCTURED_OUTPUT_NATIVE),
    )
    assert result.answer == "the model's answer"
    assert result.exchange_event_id is not None
    assert result.candidate is not None
    rows = list_approvals(loop.context.store.session, loop.context.task_id)
    assert [row.state for row in rows] == ["consumed"], "the approval paid for the one call"
    page = read_events(loop.context)
    exchanges = [event for event in page.events if event.type is EventType.MODEL_EXCHANGED]
    assert len(exchanges) == 1, "one call, one exchange record"

    refused = _capture(
        lambda: run_role_run(
            loop.context,
            ticket,
            grants=_grants(),
            at=MOMENT,
            send=lambda prompt: _invocation(answer),
            capabilities=_probed(Capability.STRUCTURED_OUTPUT_NATIVE),
        )
    )
    assert refused.reason is ApplicationRefusal.APPROVAL_REFUSED, (
        "a spent approval never authorises a second call"
    )


def test_a_refusal_at_the_transmit_gate_leaves_the_approval_unspent(loop: Loop) -> None:
    """The gate runs first, so a refusal costs the person nothing.

    **The grant names another destination**, and the request asks for this
    one: the gate refuses, the wire is never reached, and the approval is
    still there to be granted again once the grant is fixed.
    """
    ticket = request_role_run(
        loop.context,
        _request(loop, roles=("trajectory",)),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    assert ticket.approval_id is not None
    grant_approval(loop.context, ticket.approval_id, now=MOMENT)
    reached: list[str] = []

    def _spy(prompt: str) -> ModelInvocation:
        reached.append("the wire was reached")
        return _invocation({"trajectory": _trajectory_answer()})

    refused = _capture(
        lambda: run_role_run(
            loop.context,
            ticket,
            grants=_grants(destination=OTHER_DESTINATION),
            at=MOMENT,
            send=_spy,
            capabilities=_probed(Capability.STRUCTURED_OUTPUT_NATIVE),
        )
    )
    assert refused.reason is ApplicationRefusal.CONSENT_DESTINATION_NOT_GRANTED
    assert reached == [], "a refused request reached the wire"
    rows = list_approvals(loop.context.store.session, loop.context.task_id)
    assert all(row.state != "consumed" for row in rows), "the approval stayed unspent"


# --------------------------------------------------------------------------- #
# the refusals are the roles' own
# --------------------------------------------------------------------------- #


def test_an_alignment_outside_the_vocabulary_is_refused_by_the_role_that_owns_it(
    loop: Loop,
) -> None:
    """A fifth alignment state is refused by role A, through the loop."""
    ticket = request_role_run(
        loop.context,
        _request(
            loop,
            roles=("trajectory",),
            trajectory=_trajectory_judgement(alignment="maybe"),
        ),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    refused = _role_reason(lambda: run_role_run(loop.context, ticket, grants=_grants(), at=MOMENT))
    assert refused is RoleRefusal.ALIGNMENT_STATE_UNKNOWN


def test_a_quote_the_chain_does_not_hold_is_refused_by_the_role_that_owns_it(
    loop: Loop,
) -> None:
    """A paraphrase offered as a quotation is refused by role A, through the loop."""
    ticket = request_role_run(
        loop.context,
        _request(
            loop,
            roles=("trajectory",),
            trajectory=_trajectory_judgement(advisor_quote="and the advisor said more than that"),
        ),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    refused = _role_reason(lambda: run_role_run(loop.context, ticket, grants=_grants(), at=MOMENT))
    assert refused is RoleRefusal.QUOTE_NOT_IN_THE_CHAIN


def test_a_claim_citing_evidence_the_card_does_not_declare_is_refused(
    loop: Loop,
) -> None:
    """A claim nothing supports is refused by role B, through the loop."""
    ticket = request_role_run(
        loop.context,
        _request(
            loop,
            roles=("guidance",),
            guidance=_guidance_judgement(
                claims=(
                    CardClaim(
                        text="the parameter is never named.",
                        kind="scientific",
                        evidence_ref="chain:iss-nowhere",
                    ),
                )
            ),
        ),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    refused = _role_reason(lambda: run_role_run(loop.context, ticket, grants=_grants(), at=MOMENT))
    assert refused is RoleRefusal.CLAIM_WITHOUT_EVIDENCE


def test_the_models_answer_is_judged_by_the_same_roles(loop: Loop) -> None:
    """The model's alignment is refused by role A, through the loop.

    **The judgement came from the model**, not from the caller, and the
    role's own refusal is the one that reaches the surface. A loop that
    pre-validated the answer would have refused it as a decoding failure,
    and the role's rule would never have been reached.
    """
    ticket = request_role_run(
        loop.context,
        _request(loop, roles=("trajectory",)),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    assert ticket.approval_id is not None
    grant_approval(loop.context, ticket.approval_id, now=MOMENT)
    answer = {"trajectory": _trajectory_answer(alignment="maybe")}

    refused = _role_reason(
        lambda: run_role_run(
            loop.context,
            ticket,
            grants=_grants(),
            at=MOMENT,
            send=lambda prompt: _invocation(answer),
            capabilities=_probed(Capability.STRUCTURED_OUTPUT_NATIVE),
        )
    )
    assert refused is RoleRefusal.ALIGNMENT_STATE_UNKNOWN


# --------------------------------------------------------------------------- #
# the loop's own refusals
# --------------------------------------------------------------------------- #


def test_a_request_that_cannot_be_run_is_refused_by_name(loop: Loop) -> None:
    """Each way a request cannot be run is named, and none of them is routed by a default."""
    refused = _capture(
        lambda: request_role_run(
            loop.context,
            _request(loop, roles=()),
            plan=_plan(),
            expires_at=EXPIRES,
            now=MOMENT,
        )
    )
    assert refused.reason is ApplicationRefusal.ARGUMENTS_INVALID
    assert "names no role" in refused.detail

    refused = _capture(
        lambda: request_role_run(
            loop.context,
            _request(loop, roles=("oracle",)),
            plan=_plan(),
            expires_at=EXPIRES,
            now=MOMENT,
        )
    )
    assert refused.reason is ApplicationRefusal.ARGUMENTS_INVALID
    assert "oracle" in refused.detail

    refused = _capture(
        lambda: request_role_run(
            loop.context,
            _request(loop, roles=("trajectory", "trajectory")),
            plan=_plan(),
            expires_at=EXPIRES,
            now=MOMENT,
        )
    )
    assert refused.reason is ApplicationRefusal.ARGUMENTS_INVALID
    assert "more than once" in refused.detail

    refused = _capture(
        lambda: request_role_run(
            loop.context,
            _request(loop, roles=("critique",)),
            plan=_plan(),
            expires_at=EXPIRES,
            now=MOMENT,
        )
    )
    assert refused.reason is ApplicationRefusal.ARGUMENTS_INVALID
    assert "without the guidance" in refused.detail


def test_a_role_the_store_holds_no_contract_for_is_refused(loop: Loop) -> None:
    """A role with no contract is refused before it runs.

    **The contract is what says what may be asked of the role**, so a role
    the store holds no contract for is a role nobody may ask anything of.
    """
    refused = _capture(
        lambda: request_role_run(
            loop.context,
            _request(loop, roles=("guidance", "critique")),
            plan=_plan(),
            expires_at=EXPIRES,
            now=MOMENT,
        )
    )
    assert refused.reason is ApplicationRefusal.ROLE_SPEC_NOT_FOUND


def test_a_contract_that_does_not_list_the_capability_refuses_the_run(loop: Loop) -> None:
    """The boundary is the list, not the prompt.

    **The critique's contract does not list the model capability**, so the
    loop refuses before it asks for anything: the request would spend a
    call the contract does not allow.
    """
    loop.specs["critique"] = _spec(loop.context, "critique", capability=CapabilityId.SOURCE_READ)
    refused = _capture(
        lambda: request_role_run(
            loop.context,
            _request(loop, roles=("guidance", "critique")),
            plan=_plan(),
            expires_at=EXPIRES,
            now=MOMENT,
        )
    )
    assert refused.reason is ApplicationRefusal.ROLE_SPEC_CAPABILITY_NOT_LISTED


def test_a_rule_the_memory_does_not_hold_is_refused(loop: Loop) -> None:
    """A card cannot cite a rule the memory does not hold.

    **The citation is built by the role from the memory's own read**, so a
    rule id nobody wrote is refused by name on the way in.
    """
    refused = _capture(
        lambda: request_role_run(
            loop.context,
            _request(loop, roles=("guidance",), rule_id="rule-nowhere"),
            plan=_plan(),
            expires_at=EXPIRES,
            now=MOMENT,
        )
    )
    assert refused.reason is ApplicationRefusal.ROLE_RULE_NOT_IN_THE_MEMORY


def test_a_comment_the_chain_does_not_hold_is_refused(loop: Loop) -> None:
    """A judgement about a comment that is not there is refused by name.

    **The workbench asks about a comment the reader picked**, and a key the
    chain holds nothing under is a mistake the loop names rather than a
    card about nothing.
    """
    request = _request(loop, roles=("trajectory",))
    refused = _role_reason(
        lambda: request_role_run(
            loop.context,
            replace(request, issue_key="iss-nowhere"),
            plan=_plan(),
            expires_at=EXPIRES,
            now=MOMENT,
        )
    )
    assert refused is RoleRefusal.COMMENT_NOT_IN_THE_CHAIN


def test_a_version_outside_the_graph_is_refused(loop: Loop) -> None:
    """A round the project does not hold is refused by name.

    **A missing round is not a present one**, and the order the run reads
    the chain in is the accepted edges' order -- so a version nobody
    recorded is refused rather than invented.
    """
    request = _request(loop, roles=("trajectory",))
    refused = _role_reason(
        lambda: request_role_run(
            loop.context,
            replace(request, version_ids=(*request.version_ids, "ver-99")),
            plan=_plan(),
            expires_at=EXPIRES,
            now=MOMENT,
        )
    )
    assert refused is RoleRefusal.VERSION_OUTSIDE_THE_GRAPH


def test_an_empty_answer_is_not_an_answer(loop: Loop) -> None:
    """A call that came back with nothing in the schema's shape is refused.

    **The refusal is the model path's**, and the loop does not turn it into
    an empty result: a loop that ran the roles on no judgement would be
    running them on nothing.
    """
    ticket = request_role_run(
        loop.context,
        _request(loop, roles=("trajectory",)),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    assert ticket.approval_id is not None
    grant_approval(loop.context, ticket.approval_id, now=MOMENT)

    refused = _capture(
        lambda: run_role_run(
            loop.context,
            ticket,
            grants=_grants(),
            at=MOMENT,
            send=lambda prompt: _invocation({}),
            capabilities=_probed(Capability.STRUCTURED_OUTPUT_NATIVE),
        )
    )
    assert refused.reason is ApplicationRefusal.MODEL_ANSWER_EMPTY


def test_the_model_cannot_volunteer_a_role_nobody_asked_for(loop: Loop) -> None:
    """An answer carrying a part for an unnamed role does not fit the schema it was asked for.

    **There is no swarm.** The document the model is asked for holds a part
    for each role the caller named and no others, and the schema forbids
    extra keys — so a model that volunteers a card for a role nobody asked
    for has produced an answer the loop cannot read.

    **And the answer carries every part there is.** The refusal is
    therefore the *extra* keys and nothing else: an answer that left a
    part out would be refused for a missing one, and the two are different
    faults with different remedies.
    """
    ticket = request_role_run(
        loop.context,
        _request(loop, roles=("trajectory",)),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    assert ticket.approval_id is not None
    grant_approval(loop.context, ticket.approval_id, now=MOMENT)
    answer = {
        "trajectory": _trajectory_answer(),
        "guidance": _guidance_answer(),
        "critique": _critique_answer(),
    }

    refused = _capture(
        lambda: run_role_run(
            loop.context,
            ticket,
            grants=_grants(),
            at=MOMENT,
            send=lambda prompt: _invocation(answer),
            capabilities=_probed(Capability.STRUCTURED_OUTPUT_NATIVE),
        )
    )
    assert refused.reason is ApplicationRefusal.MODEL_ANSWER_UNDECODABLE
    assert "guidance" in refused.detail, "the refusal names the part that was not asked for"


def test_a_run_that_needs_a_judgement_and_has_no_invocation_is_refused(loop: Loop) -> None:
    """A run with nothing to ask the model with is refused by name."""
    ticket = request_role_run(
        loop.context,
        _request(loop, roles=("trajectory",)),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    assert ticket.approval_id is not None
    refused = _capture(lambda: run_role_run(loop.context, ticket, grants=_grants(), at=MOMENT))
    assert refused.reason is ApplicationRefusal.ARGUMENTS_INVALID
    assert "no provider invocation was given" in refused.detail


# --------------------------------------------------------------------------- #
# the outputs carry the contract they were made under
# --------------------------------------------------------------------------- #


def test_the_outputs_carry_the_contract_they_were_made_under(loop: Loop) -> None:
    """An output names the contract that governed it.

    **A replay opens the contract the output was made under**, so the role
    id and the version travel with the output rather than beside it.
    """
    loop.specs["critique"] = _spec(loop.context, "critique")
    ticket = request_role_run(
        loop.context,
        _request(
            loop,
            roles=("trajectory", "guidance", "critique"),
            rule_id=loop.rule_id,
            trajectory=_trajectory_judgement(),
            guidance=_guidance_judgement(),
            critique=_critique_judgement(),
        ),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    result = run_role_run(loop.context, ticket, grants=_grants(), at=MOMENT)
    assert result.candidate is not None
    assert result.card is not None
    assert result.verdict is not None
    assert (result.candidate.role_id, result.candidate.role_version) == ("trajectory", 1)
    assert (result.card.role_id, result.card.role_version) == ("guidance", 1)
    assert (result.verdict.role_id, result.verdict.role_version) == ("critique", 1)
    assert result.card.rule_refs, "the card cites the rule the request named"
    assert result.card.rule_refs[0].rule_id == loop.rule_id
    assert result.card.rule_refs[0].counterexamples, "and the cases against it travel with it"
