"""Role B: the guidance card, and the four prohibitions that shape it.

**What is under test.** LC-P2-12 T02: ``roles.guidance`` — the card
with every field the architecture names, the claims and the style notes
kept apart, the advisor quoted rather than invented, the abstention
that says what was missing, and the rule cited with its counterexamples.

====================================================  =========================
     the card carries its fields                          and one without
                                                          evidence is refused
     a card cites a rule with its counterexamples          the citation is the
                                                          memory's own read
     insufficient material produces a named abstention    not an empty result,
                                                          not a crash
     a card invents nothing                                a claim without
                                                          declared evidence, a
                                                          voice without a source
====================================================  =========================
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
from feedback_chain_fixtures import ChainEnv, a_comment, build_chain
from test_store_support import StoreEnv
from test_store_support import env as _shared_env

from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import ApplicationRefusedError
from labcairn.guidance.rules import propose_rule, record_counterexample
from labcairn.papers.feedback import FeedbackEvent, record_feedback, set_issue_key
from labcairn.roles.guidance import (
    CardClaim,
    Uncertainty,
    abstaining_card,
    build_card,
    cite_rule,
)
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
class Guidance:
    """The context, the comment under its key, and a confirmed rule to cite."""

    context: ApplicationContext
    chain: ChainEnv
    key: str
    event: FeedbackEvent
    spec: AgentRoleSpec
    rule_id: str


def _refusal(call: object) -> RoleRefusal:
    """The contract's refusal an expected error carries, so the test fails loudly."""
    assert isinstance(call, ApplicationRefusedError), f"expected a refusal, saw {call!r}"
    return RoleRefusal(call.reason.value.removeprefix("role_"))


@pytest.fixture()
def guidance(env: StoreEnv, tmp_path: Path) -> Guidance:
    """A chain with one keyed comment, and a confirmed rule with a case against it."""
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
    keyed = set_issue_key(chain.context, feedback_id=event.feedback_id, issue_key=KEY, now=MOMENT)
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
    record_counterexample(
        chain.context,
        rule_id=rule.rule_id,
        statement="The baseline was in the paragraph, and the advisor still asked.",
        recorded_by="a-reader",
        now=MOMENT,
    )
    spec = define_role_spec(
        chain.context,
        role_id="guidance",
        role_version=1,
        objective="Turn the trajectory's candidates into a card a student can act on.",
        input_schema="GuidanceCardInput",
        output_schema="GuidanceCard",
        allowed_capabilities=(CapabilityId.MODEL_REQUEST,),
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
        prompt_template_version="guidance-card-v1",
        model_config_ref="configs/model.json",
        now=MOMENT,
    )
    return Guidance(
        context=chain.context,
        chain=chain,
        key=KEY,
        event=keyed,
        spec=spec,
        rule_id=rule.rule_id,
    )


def test_a_card_carries_its_fields_and_one_without_evidence_is_refused(
    guidance: Guidance,
) -> None:
    """Every field the architecture names is on the card, and evidence is not optional."""
    card = build_card(
        guidance.context,
        spec=guidance.spec,
        target_locator="docx:word/document.xml#para=12",
        issue_type="method_and_hypothesis",
        severity="major",
        reason="the comparison's baseline is nowhere in the paragraph.",
        evidence_refs=("chain:" + guidance.key,),
        suggested_next_action="name the baseline the estimate is measured against.",
        uncertainty=Uncertainty(kind="low", what_is_uncertain="nothing material"),
        claims=(
            CardClaim(
                text="The paragraph estimates the parameter from a single observation.",
                kind="scientific",
                evidence_ref="chain:" + guidance.key,
            ),
        ),
        style_notes=("the paragraph is long; the claim could lead it.",),
        historical_case_refs=(guidance.key,),
        counterexamples_or_limits=("the rule does not hold where the baseline is present.",),
    )
    assert (card.role_id, card.role_version) == ("guidance", 1)
    assert card.target_locator.startswith("docx:")
    assert card.severity == "major"
    assert card.reason and card.suggested_next_action
    assert card.evidence_refs == ("chain:" + guidance.key,)
    assert card.claims[0].kind == "scientific"
    assert card.style_notes and card.historical_case_refs
    assert card.counterexamples_or_limits
    assert card.uncertainty.kind == "low"

    refused = _refusal(
        _capture(
            lambda: build_card(
                guidance.context,
                spec=guidance.spec,
                target_locator="docx:word/document.xml#para=12",
                issue_type="method_and_hypothesis",
                severity="major",
                reason="the comparison's baseline is nowhere in the paragraph.",
                evidence_refs=(),
                suggested_next_action="name the baseline.",
                uncertainty=Uncertainty(kind="low", what_is_uncertain="nothing"),
            )
        )
    )
    assert refused is RoleRefusal.CARD_WITHOUT_EVIDENCE
    refused = _refusal(
        _capture(
            lambda: build_card(
                guidance.context,
                spec=guidance.spec,
                target_locator="docx:word/document.xml#para=12",
                issue_type="method_and_hypothesis",
                severity="catastrophic",
                reason="a degree the vocabulary does not close.",
                evidence_refs=("chain:" + guidance.key,),
                suggested_next_action="name the baseline.",
                uncertainty=Uncertainty(kind="low", what_is_uncertain="nothing"),
            )
        )
    )
    assert refused is RoleRefusal.SEVERITY_UNKNOWN
    refused = _refusal(
        _capture(
            lambda: build_card(
                guidance.context,
                spec=guidance.spec,
                target_locator="   ",
                issue_type="method_and_hypothesis",
                severity="major",
                reason="a card that points nowhere.",
                evidence_refs=("chain:" + guidance.key,),
                suggested_next_action="name the baseline.",
                uncertainty=Uncertainty(kind="low", what_is_uncertain="nothing"),
            )
        )
    )
    assert refused is RoleRefusal.CARD_FIELD_EMPTY


def test_a_card_cites_a_rule_with_its_counterexamples(guidance: Guidance) -> None:
    """The citation is the memory's own read, and the cases against it travel.

    The counterexamples are **not a parameter**: the caller cannot thin
    them, because :func:`cite_rule` takes only the rule's id.
    """
    citation = cite_rule(guidance.context, rule_id=guidance.rule_id)
    assert citation.rule_id == guidance.rule_id
    assert citation.version == 1
    assert citation.statement == RULE
    assert citation.counterexamples == (
        "The baseline was in the paragraph, and the advisor still asked.",
    )
    refused = _refusal(_capture(lambda: cite_rule(guidance.context, rule_id="rule-nowhere")))
    assert refused is RoleRefusal.RULE_NOT_IN_THE_MEMORY

    card = build_card(
        guidance.context,
        spec=guidance.spec,
        target_locator="docx:word/document.xml#para=12",
        issue_type="method_and_hypothesis",
        severity="major",
        reason="the comparison's baseline is nowhere in the paragraph.",
        evidence_refs=("chain:" + guidance.key,),
        suggested_next_action="name the baseline.",
        uncertainty=Uncertainty(kind="low", what_is_uncertain="nothing"),
        rule_refs=(citation,),
    )
    assert card.rule_refs[0].counterexamples, "the cases travel with the advice"


def test_insufficient_material_produces_a_named_abstention(guidance: Guidance) -> None:
    """An abstention is a structured result that names what was missing."""
    card = abstaining_card(
        spec=guidance.spec,
        issue_type="method_and_hypothesis",
        what_is_uncertain="whether the comment was ever answered",
        missing=(
            "no revision of the manuscript is in reach",
            "the comment's version has no child in the graph",
        ),
    )
    assert card.uncertainty.kind == "abstention"
    assert card.uncertainty.missing == (
        "no revision of the manuscript is in reach",
        "the comment's version has no child in the graph",
    )
    assert card.evidence_refs == ()
    assert card.reason

    refused = _refusal(
        _capture(
            lambda: abstaining_card(
                spec=guidance.spec,
                issue_type="method_and_hypothesis",
                what_is_uncertain="whether the comment was ever answered",
                missing=(),
            )
        )
    )
    assert refused is RoleRefusal.ABSTENTION_WITHOUT_A_MISSING


def test_a_card_invents_no_experiment_reference_or_opinion(
    guidance: Guidance,
) -> None:
    """A claim's warrant is declared, and the advisor's voice is quoted, not invented."""
    quote = guidance.event.comment_text[:24]

    # **A scientific claim whose evidence the card does not declare** is
    # the invented experiment's shape: a finding with no warrant.
    refused = _refusal(
        _capture(
            lambda: build_card(
                guidance.context,
                spec=guidance.spec,
                target_locator="docx:word/document.xml#para=12",
                issue_type="method_and_hypothesis",
                severity="major",
                reason="a finding nobody measured.",
                evidence_refs=("chain:" + guidance.key,),
                suggested_next_action="name the baseline.",
                uncertainty=Uncertainty(kind="low", what_is_uncertain="nothing"),
                claims=(
                    CardClaim(
                        text="a replicated experiment shows the effect",
                        kind="scientific",
                        evidence_ref="study:nowhere",
                    ),
                ),
            )
        )
    )
    assert refused is RoleRefusal.CLAIM_WITHOUT_EVIDENCE
    refused = _refusal(
        _capture(
            lambda: build_card(
                guidance.context,
                spec=guidance.spec,
                target_locator="docx:word/document.xml#para=12",
                issue_type="method_and_hypothesis",
                severity="major",
                reason="a reference nothing declares.",
                evidence_refs=("chain:" + guidance.key,),
                suggested_next_action="name the baseline.",
                uncertainty=Uncertainty(kind="low", what_is_uncertain="nothing"),
                claims=(
                    CardClaim(
                        text="the literature agrees (Someone, 2020)",
                        kind="reference",
                    ),
                ),
            )
        )
    )
    assert refused is RoleRefusal.CLAIM_WITHOUT_EVIDENCE

    # **An advisor claim quoting words the chain does not hold** is the
    # invented opinion's shape; the verbatim quote stands.
    refused = _refusal(
        _capture(
            lambda: build_card(
                guidance.context,
                spec=guidance.spec,
                target_locator="docx:word/document.xml#para=12",
                issue_type="method_and_hypothesis",
                severity="major",
                reason="a voice nobody wrote down.",
                evidence_refs=("chain:" + guidance.key,),
                suggested_next_action="name the baseline.",
                uncertainty=Uncertainty(kind="low", what_is_uncertain="nothing"),
                claims=(
                    CardClaim(
                        text="the advisor approves of this section",
                        kind="advisor",
                        issue_key=guidance.key,
                        advisor_quote="the advisor approves of this section",
                    ),
                ),
            )
        )
    )
    assert refused is RoleRefusal.ADVICE_NOT_IN_THE_CHAIN
    refused = _refusal(
        _capture(
            lambda: build_card(
                guidance.context,
                spec=guidance.spec,
                target_locator="docx:word/document.xml#para=12",
                issue_type="method_and_hypothesis",
                severity="major",
                reason="a voice without a source.",
                evidence_refs=("chain:" + guidance.key,),
                suggested_next_action="name the baseline.",
                uncertainty=Uncertainty(kind="low", what_is_uncertain="nothing"),
                claims=(
                    CardClaim(
                        text="the advisor approves of this section",
                        kind="advisor",
                    ),
                ),
            )
        )
    )
    assert refused is RoleRefusal.ADVICE_NOT_IN_THE_CHAIN
    card = build_card(
        guidance.context,
        spec=guidance.spec,
        target_locator="docx:word/document.xml#para=12",
        issue_type="method_and_hypothesis",
        severity="major",
        reason="the advisor's own words, carried verbatim.",
        evidence_refs=("chain:" + guidance.key,),
        suggested_next_action="name the baseline.",
        uncertainty=Uncertainty(kind="low", what_is_uncertain="nothing"),
        claims=(
            CardClaim(
                text="the advisor's comment, quoted",
                kind="advisor",
                issue_key=guidance.key,
                advisor_quote=quote,
            ),
        ),
    )
    assert card.claims[0].advisor_quote in guidance.event.comment_text


def test_facts_and_style_are_recorded_separately(guidance: Guidance) -> None:
    """A scientific fact and a stylistic note are different kinds of sentence.

    **The separation is the type's, not a convention.** A fact is a
    ``CardClaim`` with a warrant; a style note is a bare sentence in
    ``style_notes``. And a style note cannot ride in as a claim — the
    claim kinds are closed, and "style" is not one of them.
    """
    card = build_card(
        guidance.context,
        spec=guidance.spec,
        target_locator="docx:word/document.xml#para=12",
        issue_type="method_and_hypothesis",
        severity="moderate",
        reason="the comparison's baseline is nowhere in the paragraph.",
        evidence_refs=("chain:" + guidance.key,),
        suggested_next_action="name the baseline.",
        uncertainty=Uncertainty(kind="low", what_is_uncertain="nothing"),
        claims=(
            CardClaim(
                text="The paragraph estimates the parameter from a single observation.",
                kind="scientific",
                evidence_ref="chain:" + guidance.key,
            ),
        ),
        style_notes=("the paragraph is long; the claim could lead it.",),
    )
    assert all(isinstance(claim, CardClaim) for claim in card.claims)
    assert {claim.kind for claim in card.claims} <= {"scientific", "reference", "advisor"}
    assert card.style_notes == ("the paragraph is long; the claim could lead it.",)
    assert all(isinstance(note, str) for note in card.style_notes)
    refused = _refusal(
        _capture(
            lambda: build_card(
                guidance.context,
                spec=guidance.spec,
                target_locator="docx:word/document.xml#para=12",
                issue_type="method_and_hypothesis",
                severity="moderate",
                reason="a style note smuggled in as a claim.",
                evidence_refs=("chain:" + guidance.key,),
                suggested_next_action="name the baseline.",
                uncertainty=Uncertainty(kind="low", what_is_uncertain="nothing"),
                claims=(
                    CardClaim(
                        text="the paragraph is long; the claim could lead it.",
                        kind="style",
                    ),
                ),
            )
        )
    )
    assert refused is RoleRefusal.CLAIM_KIND_UNKNOWN


def _capture(call: object) -> ApplicationRefusedError:
    """The refusal a call that must raise carries."""
    assert callable(call)
    try:
        call()
    except ApplicationRefusedError as refused:
        return refused
    raise AssertionError("the call was expected to refuse, and it did not")
