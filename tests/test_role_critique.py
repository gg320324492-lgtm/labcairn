"""Role C: the independent critique, and the grade its verdict carries.

**What is under test.** LC-P2-12 T03: ``roles.critique`` — the review
that reads the sources and retrieves its own counter-evidence, and the
verdict that never promotes anything.

====================================================  =========================
     the review reads the sources                        the card's evidence
                                                          is checked, not taken
                                                          on trust, and the
                                                          counter-evidence is
                                                          C's own retrieval
     the verdict does not promote                        the grade is the
                                                          evidence's, the review
                                                          writes nothing, and two
                                                          agreeing models are a
                                                          corroboration, not a
                                                          confirmation
     a hand-over carries its reason                      a refusing verdict
                                                          without one is refused
====================================================  =========================
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
from feedback_chain_fixtures import a_comment, build_chain
from test_store_support import StoreEnv
from test_store_support import env as _shared_env

from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import ApplicationRefusedError
from labcairn.guidance.rules import confirm_rule, propose_rule, record_counterexample
from labcairn.papers.feedback import record_feedback, set_issue_key
from labcairn.roles.critique import VERDICTS, review_card
from labcairn.roles.guidance import GuidanceCard, Uncertainty, build_card
from labcairn.roles.refusals import RoleRefusal
from labcairn.roles.spec import FORBIDDEN_ACTIONS, AgentRoleSpec, define_role_spec
from labcairn.security.capabilities import CapabilityId

pytestmark = pytest.mark.integration

env = _shared_env

MOMENT = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)

KEY = "iss-gold-a-r1"

RULE = (
    "When the claim rests on a comparison, the advisor asks for the baseline"
    " to be named in the same paragraph."
)


@dataclass(frozen=True)
class Critique:
    """The context, a card to review, and a rule with a case against it."""

    context: ApplicationContext
    spec: AgentRoleSpec
    second_spec: AgentRoleSpec
    card: GuidanceCard
    rule_id: str


def _refusal(call: object) -> RoleRefusal:
    """The contract's refusal an expected error carries, so the test fails loudly."""
    assert isinstance(call, ApplicationRefusedError), f"expected a refusal, saw {call!r}"
    return RoleRefusal(call.reason.value.removeprefix("role_"))


def _card(context: ApplicationContext, spec: AgentRoleSpec, key: str) -> GuidanceCard:
    """A card whose evidence is the chain's, with the key beside it."""
    return build_card(
        context,
        spec=spec,
        target_locator="docx:word/document.xml#para=12",
        issue_type="method_and_hypothesis",
        severity="major",
        reason="the comparison's baseline is nowhere in the paragraph.",
        evidence_refs=("chain:" + key,),
        suggested_next_action="name the baseline.",
        uncertainty=Uncertainty(kind="low", what_is_uncertain="nothing"),
    )


def _spec(context: ApplicationContext, role_id: str) -> AgentRoleSpec:
    """A critique role's contract."""
    return define_role_spec(
        context,
        role_id=role_id,
        role_version=1,
        objective="Check the card against the sources, independently.",
        input_schema="GuidanceCard",
        output_schema="ReviewVerdict",
        allowed_capabilities=(CapabilityId.SOURCE_READ,),
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
        prompt_template_version="critique-v1",
        model_config_ref="configs/model.json",
        now=MOMENT,
    )


@pytest.fixture()
def critique(env: StoreEnv, tmp_path: Path) -> Critique:
    """A chain, a card over it, and a confirmed rule with a case against it.

    **The rule is in the memory with its counterexample**, so the
    counter-evidence C retrieves for itself has something in it — and
    two critique specs stand ready, because two models agreeing is the
    corroboration the verdict must never turn into a confirmation.
    """
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
    from labcairn.db.models import EditActionRow, ResponseLinkRow

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
    session.add(
        ResponseLinkRow(
            response_link_id="resp-201",
            feedback_id=event.feedback_id,
            edit_action_id="edit-201",
            state="addressed",
            grade="human_verified",
            decided_by="user",
            decided_at=MOMENT,
            evidence_refs=[f"check:{KEY}"],
            created_at=MOMENT,
        )
    )
    session.flush()
    rule = propose_rule(
        chain.context,
        issue_type="method_and_hypothesis",
        statement=RULE,
        rule_context="A results section whose claim is comparative.",
        scope="Empirical papers in this group's field.",
        example="The comment of the run, on the ablation paragraph.",
        sources=(KEY,),
        proposed_by="a-mentor",
        now=MOMENT,
    )
    confirm_rule(
        chain.context,
        rule_id=rule.rule_id,
        confirmed_by="the-advisor",
        now=MOMENT,
    )
    record_counterexample(
        chain.context,
        rule_id=rule.rule_id,
        statement="The baseline was in the paragraph, and the advisor still asked.",
        recorded_by="a-reader",
        now=MOMENT,
    )
    spec = _spec(chain.context, "critique")
    second_spec = _spec(chain.context, "critique-2")
    return Critique(
        context=chain.context,
        spec=spec,
        second_spec=second_spec,
        card=_card(chain.context, spec, KEY),
        rule_id=rule.rule_id,
    )


def test_role_c_reads_the_sources_and_its_own_counterevidence(
    critique: Critique,
) -> None:
    """The card's evidence is checked against the chain, and the counter-evidence is C's own.

    **The counter-evidence arrives whether the card survives or not** —
    it is what the review retrieved, not what the card declared.
    """
    verdict = review_card(
        critique.context,
        spec=critique.spec,
        card=critique.card,
        verdict="supported",
        repair_advice="none needed",
    )
    assert verdict.verdict == "supported"
    assert verdict.grade == "inferred"
    assert verdict.counter_evidence, "the memory held a case against the rule"
    assert verdict.counter_evidence[0].rule_id == critique.rule_id
    assert verdict.counter_evidence[0].counterexamples

    bad_card = _card(critique.context, critique.spec, "iss-nowhere")
    refused = _refusal(
        _capture(
            lambda: review_card(
                critique.context,
                spec=critique.spec,
                card=bad_card,
                verdict="supported",
                repair_advice="none needed",
            )
        )
    )
    assert refused is RoleRefusal.EVIDENCE_NOT_IN_THE_CHAIN

    unverifiable = build_card(
        critique.context,
        spec=critique.spec,
        target_locator="docx:word/document.xml#para=12",
        issue_type="method_and_hypothesis",
        severity="major",
        reason="the comparison's baseline is nowhere in the paragraph.",
        evidence_refs=("study:nowhere",),
        suggested_next_action="name the baseline.",
        uncertainty=Uncertainty(kind="low", what_is_uncertain="nothing"),
    )
    refused = _refusal(
        _capture(
            lambda: review_card(
                critique.context,
                spec=critique.spec,
                card=unverifiable,
                verdict="supported",
                repair_advice="none needed",
            )
        )
    )
    assert refused is RoleRefusal.UNVERIFIABLE_EVIDENCE_ACCEPTED
    honest = review_card(
        critique.context,
        spec=critique.spec,
        card=unverifiable,
        verdict="cannot_assess",
        repair_advice="name the evidence in a form the chain holds",
        handover_reason="the card's evidence is in no form the review can check",
    )
    assert honest.verdict == "cannot_assess"
    assert honest.handover_reason


def test_a_verdict_does_not_promote_a_proposal(critique: Critique) -> None:
    """The verdict enters at the grade its evidence supports, and writes nothing.

    **Two models agreeing is a corroboration.** A second critique, a
    second verdict, the same conclusion — and the store holds exactly
    what it held, because a promotion is a person's act and a record
    constructor's, and a review is neither.
    """
    before = _store_row_count(critique.context)
    first = review_card(
        critique.context,
        spec=critique.spec,
        card=critique.card,
        verdict="needs_revision",
        repair_advice="name the baseline the estimate is measured against.",
        handover_reason="the card's advice rests on the rule; the rule has a case against it",
    )
    second = review_card(
        critique.context,
        spec=critique.second_spec,
        card=critique.card,
        verdict="needs_revision",
        repair_advice="name the baseline the estimate is measured against.",
        handover_reason="the card's advice rests on the rule; the rule has a case against it",
    )
    assert first.grade == second.grade == "inferred"
    assert first.verdict == second.verdict == "needs_revision"
    assert _store_row_count(critique.context) == before, (
        "a review that wrote anything would be a review that promoted"
    )
    refused = _refusal(
        _capture(
            lambda: review_card(
                critique.context,
                spec=critique.spec,
                card=critique.card,
                verdict="perhaps",
                repair_advice="a fifth verdict",
            )
        )
    )
    assert refused is RoleRefusal.VERDICT_UNKNOWN
    refused = _refusal(
        _capture(
            lambda: review_card(
                critique.context,
                spec=critique.spec,
                card=critique.card,
                verdict="needs_revision",
                repair_advice="   ",
            )
        )
    )
    assert refused is RoleRefusal.CARD_FIELD_EMPTY
    refused = _refusal(
        _capture(
            lambda: review_card(
                critique.context,
                spec=critique.spec,
                card=critique.card,
                verdict="needs_revision",
                repair_advice="name the baseline.",
            )
        )
    )
    assert refused is RoleRefusal.HANDOVER_WITHOUT_A_REASON
    assert frozenset({"supported", "needs_revision", "unsupported", "cannot_assess"}) == VERDICTS


def _store_row_count(context: ApplicationContext) -> int:
    """Every row the store holds, so a review that wrote anywhere is caught."""
    from sqlalchemy import text

    session = context.store.session
    tables: Iterable[str] = session.execute(
        text(
            "SELECT name FROM sqlite_master WHERE type='table'"
            " AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'alembic_%'"
        )
    ).scalars()
    total = 0
    for name in tables:
        total += session.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar_one()
    return total


def _capture(call: object) -> ApplicationRefusedError:
    """The refusal a call that must raise carries."""
    assert callable(call)
    try:
        call()
    except ApplicationRefusedError as refused:
        return refused
    raise AssertionError("the call was expected to refuse, and it did not")
