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
     a card carries an address of its own                  minted by the
                                                          product, the card's
                                                          own, and not a
                                                          caller's to write
====================================================  =========================
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
from feedback_chain_fixtures import ChainEnv, a_comment, build_chain
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import ApplicationRefusedError
from labcairn.application.roles_run import (
    ModelCallPlan,
    RoleRunQuestion,
    RoleRunRequest,
    the_role_run_question,
)
from labcairn.db.models import EditActionRow
from labcairn.guidance.retrieval import invalidated_rules, search_rules
from labcairn.guidance.rules import confirm_rule, propose_rule, record_counterexample
from labcairn.papers.feedback import FeedbackEvent, record_feedback, set_issue_key
from labcairn.papers.responses import record_response
from labcairn.roles.guidance import (
    CardClaim,
    RuleCitation,
    Uncertainty,
    abstaining_card,
    build_card,
    cite_rule,
)
from labcairn.roles.refusals import RoleRefusal
from labcairn.roles.spec import FORBIDDEN_ACTIONS, AgentRoleSpec, define_role_spec
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import CapabilityId
from labcairn.security.policy import Permission, PermissionPolicy, Rule

pytestmark = pytest.mark.integration

env = _shared_env

MOMENT = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)

KEY = "iss-gold-a-r1"

#: A second key, whose comment was judged **not** answered by its change.
WITHDRAWN_KEY = "iss-gold-a-r3"

#: A third key, whose comment was judged answered — a source a rule can stand on.
ALIVE_KEY = "iss-gold-a-r4"

#: A fourth key, whose comment **nobody judged** — a source that is
#: unattested rather than withdrawn.
UNATTESTED_KEY = "iss-gold-a-r5"

RULE = (
    "When the claim rests on a comparison, the advisor asks for the baseline"
    " to be named in the same paragraph."
)

WITHDRAWN_RULE = "When a figure carries the claim, the advisor asks for the numbers in the caption."

STANDING_RULE = "When a table carries the comparison, the advisor asks for the units in the header."

UNATTESTED_RULE = "When nobody has judged the figure, the advisor's question is still open."

#: The material the chain's manuscript is addressed by — the address the
#: role run's declaration is checked against.
MATERIAL_ROOT = "source:0"
MATERIAL_KEY = "manuscript.docx"
MATERIAL_PATH = "materials/manuscript.docx"
DESTINATION = "api.model-provider.example"


@dataclass(frozen=True)
class Guidance:
    """The context, the comment under its key, and a candidate rule over it.

    **The rule is a candidate, and its source is unattested** — the
    chain holds the comment and no judgement on it. The fixture says so
    because the two facts decide what the memory does with the rule.
    """

    context: ApplicationContext
    chain: ChainEnv
    key: str
    event: FeedbackEvent
    spec: AgentRoleSpec
    rule_id: str


@dataclass(frozen=True)
class Unattested:
    """A chain whose comment nobody judged, and a confirmed rule over it.

    **The source is unattested, not withdrawn**: the chain holds the
    comment and no judgement on it at all. The rule is confirmed, and a
    confirmed rule stands only on the sources that carry a judgement
    saying the change answered.
    """

    context: ApplicationContext
    chain: ChainEnv
    key: str
    spec: AgentRoleSpec
    rule_id: str


def _refusal(call: object) -> RoleRefusal:
    """The contract's refusal an expected error carries, so the test fails loudly."""
    assert isinstance(call, ApplicationRefusedError), f"expected a refusal, saw {call!r}"
    return RoleRefusal(call.reason.value.removeprefix("role_"))


def _guidance_spec(context: ApplicationContext) -> AgentRoleSpec:
    """Role B's contract, as both fixtures define it."""
    return define_role_spec(
        context,
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


@pytest.fixture()
def guidance(env: StoreEnv, tmp_path: Path) -> Guidance:
    """A chain with one keyed comment, and a **candidate** rule over it.

    **The source is unattested: nobody has judged the comment.** The chain
    holds the comment and the key, and there is no judgement on it — so
    the material is *unattested*, not withdrawn. The rule is a candidate,
    and a candidate is the case the memory serves on a found, reachable
    source whatever the judgement says. The fixture says both, because
    the two facts decide what the citation path does with the rule.
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
    spec = _guidance_spec(chain.context)
    return Guidance(
        context=chain.context,
        chain=chain,
        key=KEY,
        event=keyed,
        spec=spec,
        rule_id=rule.rule_id,
    )


@dataclass(frozen=True)
class Withdrawn:
    """Two commented sources, judged both ways, and the confirmed rules over them.

    ``rule_id`` is a rule that stands **only** on the withdrawn source;
    ``standing_rule_id`` names both sources and so still stands on the
    answered one.
    """

    context: ApplicationContext
    chain: ChainEnv
    key: str
    rule_id: str
    standing_rule_id: str
    spec: AgentRoleSpec


@pytest.fixture()
def withdrawn(env: StoreEnv, tmp_path: Path) -> Withdrawn:
    """A chain whose comments were judged both ways, and the rules over them.

    **The judgements are recorded from the start**, the way the retrieval
    layer's own witness records them: the chain is append-only, and a
    judgement is not rewritten in place. So the rules are proposed and
    confirmed over sources the chain has already judged.
    """
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    store = env.store()
    chain = build_chain(store, workspace_root, comments=(a_comment("203"), a_comment("204")))
    events = record_feedback(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.version_id,
        now=MOMENT,
    )
    assert len(events) == 2, "the fixture's manuscript carries two comments"
    session = chain.context.store.session
    for event, key, state in zip(
        events, (WITHDRAWN_KEY, ALIVE_KEY), ("not_addressed", "addressed"), strict=True
    ):
        set_issue_key(chain.context, feedback_id=event.feedback_id, issue_key=key, now=MOMENT)
        edit_action_id = f"edit-{key[-2:]}"
        session.add(
            EditActionRow(
                edit_action_id=edit_action_id,
                feedback_id=event.feedback_id,
                version_edge_id=chain.edge_id,
                actor_kind="student",
                grade="observed",
                created_at=MOMENT,
            )
        )
        session.flush()
        record_response(
            chain.context,
            response_link_id=f"resp-{key[-2:]}",
            feedback_id=event.feedback_id,
            edit_action_id=edit_action_id,
            state=state,
            grade="human_verified",
            decided_by="user",
            decided_at=MOMENT,
            evidence_refs=(f"check:{key}",),
            now=MOMENT,
        )
    withdrawn_rule = propose_rule(
        chain.context,
        issue_type="method_and_hypothesis",
        statement=WITHDRAWN_RULE,
        rule_context="A figure whose caption carries the numbers.",
        scope="Empirical papers in this group's field.",
        example="The comment of the run, on the figure caption.",
        sources=(WITHDRAWN_KEY,),
        proposed_by="a-mentor",
        now=MOMENT,
    )
    standing_rule = propose_rule(
        chain.context,
        issue_type="method_and_hypothesis",
        statement=STANDING_RULE,
        rule_context="A table whose comparison carries the claim.",
        scope="Empirical papers in this group's field.",
        example="The comment of the run, on the results table.",
        sources=(WITHDRAWN_KEY, ALIVE_KEY),
        proposed_by="a-mentor",
        now=MOMENT,
    )
    for rule in (withdrawn_rule, standing_rule):
        confirm_rule(chain.context, rule_id=rule.rule_id, confirmed_by="the-advisor", now=MOMENT)
    return Withdrawn(
        context=chain.context,
        chain=chain,
        key=WITHDRAWN_KEY,
        rule_id=withdrawn_rule.rule_id,
        standing_rule_id=standing_rule.rule_id,
        spec=_guidance_spec(chain.context),
    )


@pytest.fixture()
def unattested(env: StoreEnv, tmp_path: Path) -> Unattested:
    """A chain whose comment **nobody has judged**, and a confirmed rule over it.

    **The source is unattested, not withdrawn.** The chain holds the
    comment and the key, and there is no judgement on it at all — so
    nobody has said the change did not answer it, and nothing has been
    withdrawn from under the rule. The rule is confirmed, and a confirmed
    rule stands only on the sources that carry a judgement saying the
    change answered, so this is the case the memory does not serve.
    """
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    store = env.store()
    chain = build_chain(store, workspace_root, comments=(a_comment("205"),))
    (event,) = record_feedback(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.version_id,
        now=MOMENT,
    )
    set_issue_key(
        chain.context, feedback_id=event.feedback_id, issue_key=UNATTESTED_KEY, now=MOMENT
    )
    rule = propose_rule(
        chain.context,
        issue_type="method_and_hypothesis",
        statement=UNATTESTED_RULE,
        rule_context="A figure whose caption nobody has judged.",
        scope="Empirical papers in this group's field.",
        example="The comment of the run, on the figure caption.",
        sources=(UNATTESTED_KEY,),
        proposed_by="a-mentor",
        now=MOMENT,
    )
    confirm_rule(chain.context, rule_id=rule.rule_id, confirmed_by="the-advisor", now=MOMENT)
    return Unattested(
        context=chain.context,
        chain=chain,
        key=UNATTESTED_KEY,
        spec=_guidance_spec(chain.context),
        rule_id=rule.rule_id,
    )


def _denied_reader(context: ApplicationContext) -> ApplicationContext:
    """The same store, under a policy that denies reading the material."""
    return ApplicationContext(
        workspace=context.workspace,
        store=context.store,
        policy=PermissionPolicy.from_rules(
            [
                Rule(
                    effect=Permission.DENY,
                    pattern="**",
                    capabilities=frozenset({CapabilityId.SOURCE_READ.value}),
                )
            ]
        ),
        ledger=ApprovalLedger(),
    )


def test_a_card_carries_its_fields_and_one_without_evidence_is_refused(
    guidance: Guidance,
) -> None:
    """Every field the architecture names is on the card, and evidence is not optional."""
    card = build_card(
        guidance.context,
        spec=guidance.spec,
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
    assert card.target_locator.startswith("card:")
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
                issue_type="method_and_hypothesis",
                severity="major",
                reason="   ",
                evidence_refs=("chain:" + guidance.key,),
                suggested_next_action="name the baseline.",
                uncertainty=Uncertainty(kind="low", what_is_uncertain="nothing"),
            )
        )
    )
    assert refused is RoleRefusal.CARD_FIELD_EMPTY


def test_a_card_carries_an_address_of_its_own_and_a_caller_cannot_supply_it(
    guidance: Guidance,
) -> None:
    """The address is minted by the product, and it is the card's own.

    **Three pieces, and each is a name the chain holds**: the issue the
    card is about, the comment under it, and the manuscript state the
    comment was written against. The address is spelled in the card's own
    namespace, so it cannot be mistaken for a source address in the
    ledger's sense — the ledger's anchors name body paragraphs, and the
    advisor's words are in ``word/comments.xml``.

    **And there is no parameter to fill it in.** A caller that could
    write the address could point the card at a comment it is not about.
    """
    card = build_card(
        guidance.context,
        spec=guidance.spec,
        issue_type="method_and_hypothesis",
        severity="major",
        reason="the comparison's baseline is nowhere in the paragraph.",
        evidence_refs=("chain:" + guidance.key,),
        suggested_next_action="name the baseline.",
        uncertainty=Uncertainty(kind="low", what_is_uncertain="nothing"),
    )
    assert card.target_locator == (
        f"card:{guidance.key}@{guidance.event.feedback_id}@{guidance.chain.version_id}"
    )
    assert not card.target_locator.startswith("docx:"), (
        "a card's address is not a place in the manuscript"
    )
    assert not card.target_locator.startswith("k="), (
        "a card's address is not a source anchor in the ledger's sense"
    )

    # **A caller may not supply the address.** The shape refuses it
    # before the body runs, so the pretending is not a mistake a caller
    # can make.
    assert "target_locator" not in inspect.signature(build_card).parameters
    with pytest.raises(TypeError):
        inspect.signature(build_card).bind(
            guidance.context,
            spec=guidance.spec,
            target_locator="docx:word/document.xml#para=12",
            issue_type="method_and_hypothesis",
            severity="major",
            reason="a card that points nowhere.",
            evidence_refs=("chain:" + guidance.key,),
            suggested_next_action="name the baseline.",
            uncertainty=Uncertainty(kind="low", what_is_uncertain="nothing"),
        )

    # **A card that names no comment in the chain has no address**, and
    # a card nobody can find advises nobody.
    refused = _refusal(
        _capture(
            lambda: build_card(
                guidance.context,
                spec=guidance.spec,
                issue_type="method_and_hypothesis",
                severity="major",
                reason="a card about nothing the chain holds.",
                evidence_refs=("study:nowhere",),
                suggested_next_action="name the baseline.",
                uncertainty=Uncertainty(kind="low", what_is_uncertain="nothing"),
            )
        )
    )
    assert refused is RoleRefusal.CARD_WITHOUT_AN_ADDRESS

    # **A card that names two comments does not say which one it is
    # about**, and an address that could be two addresses is not an
    # address.
    refused = _refusal(
        _capture(
            lambda: build_card(
                guidance.context,
                spec=guidance.spec,
                issue_type="method_and_hypothesis",
                severity="major",
                reason="a card about two comments at once.",
                evidence_refs=("chain:" + guidance.key, "chain:iss-other"),
                suggested_next_action="name the baseline.",
                uncertainty=Uncertainty(kind="low", what_is_uncertain="nothing"),
            )
        )
    )
    assert refused is RoleRefusal.CARD_ADDRESS_AMBIGUOUS


def test_a_recurring_issue_is_addressed_by_the_comment_the_card_quotes(
    env: StoreEnv,
    tmp_path: Path,
) -> None:
    """One key can hold two comments, and the card's own words say which.

    **A recurrence is a fact about two versions**, and both comments wear
    the same key — so the key alone is not an address. The card quotes
    one of them, and the quote is the advisor's own words in the chain,
    so the address names the comment the card is about.
    """
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    store = env.store()
    chain = build_chain(
        store,
        workspace_root,
        comments=(a_comment("201"),),
        second_comments=(a_comment("202", text="Name the quantity."),),
    )
    first = record_feedback(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.version_id,
        now=MOMENT,
    )[0]
    second = record_feedback(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.second_version_id,
        now=MOMENT,
    )[0]
    set_issue_key(chain.context, feedback_id=first.feedback_id, issue_key=KEY, now=MOMENT)
    set_issue_key(chain.context, feedback_id=second.feedback_id, issue_key=KEY, now=MOMENT)
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

    card = build_card(
        chain.context,
        spec=spec,
        issue_type="method_and_hypothesis",
        severity="major",
        reason="the advisor asked for the quantity, in the advisor's own words.",
        evidence_refs=("chain:" + KEY,),
        suggested_next_action="name the quantity.",
        uncertainty=Uncertainty(kind="low", what_is_uncertain="nothing"),
        claims=(
            CardClaim(
                text="the advisor asked for the quantity",
                kind="advisor",
                issue_key=KEY,
                advisor_quote="Name the quantity.",
            ),
        ),
    )
    assert card.target_locator == f"card:{KEY}@{second.feedback_id}@{chain.second_version_id}"

    # **A card that quotes neither of them cannot be addressed**, because
    # the key alone would be two addresses.
    refused = _refusal(
        _capture(
            lambda: build_card(
                chain.context,
                spec=spec,
                issue_type="method_and_hypothesis",
                severity="major",
                reason="a card that says which comment nowhere.",
                evidence_refs=("chain:" + KEY,),
                suggested_next_action="name the quantity.",
                uncertainty=Uncertainty(kind="low", what_is_uncertain="nothing"),
            )
        )
    )
    assert refused is RoleRefusal.CARD_ADDRESS_AMBIGUOUS


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
        issue_type="method_and_hypothesis",
        severity="major",
        reason="the comparison's baseline is nowhere in the paragraph.",
        evidence_refs=("chain:" + guidance.key,),
        suggested_next_action="name the baseline.",
        uncertainty=Uncertainty(kind="low", what_is_uncertain="nothing"),
        rule_refs=(citation,),
    )
    assert card.rule_refs[0].counterexamples, "the cases travel with the advice"


def test_a_card_cannot_cite_a_rule_whose_source_a_judgement_withdrew(
    withdrawn: Withdrawn,
) -> None:
    """ADR-0016 C10: the citation path asks the memory's question.

    **The rule is named directly**, so the retrieval layer is not in the
    way: the caller hands in the id and the memory has stopped serving the
    rule, because the judgement on its only source says the change did
    not answer the comment. **A card cannot carry the citation**, because
    the citation never exists — the card's assembly is refused before it
    produces one.

    **And the two layers agree**: the retrieval layer reports the same
    rule as invalidated, over the same source, for the same reason — and
    a rule that stands on one living source is still citable, and still
    served, so neither layer refuses more than the contract says.

    **What would make this red:** a citation path that asked its own
    question instead of the memory's. A check that looked for a withdrawn
    judgement and nothing else would hand this rule out, and the refusal
    would never be raised.
    """
    refused = _capture(lambda: cite_rule(withdrawn.context, rule_id=withdrawn.rule_id))
    assert _refusal(refused) is RoleRefusal.RULE_NOT_SERVED_BY_THE_MEMORY
    assert withdrawn.rule_id in refused.detail
    assert withdrawn.key in refused.detail
    assert "source material has been withdrawn" in refused.detail

    # **The card path is the one the contract names, and it is driven.**
    # The citation the memory will not mint is written by hand here, and
    # the card refuses it: a citation the memory did not mint is not a
    # citation a card may carry. (The minting is witnessed on its own
    # below; this is the card path refusing, not the citation path
    # refusing twice.)
    refused_card = _refusal(
        _capture(
            lambda: build_card(
                withdrawn.context,
                spec=withdrawn.spec,
                issue_type="method_and_hypothesis",
                severity="major",
                reason="the caption carries no numbers.",
                evidence_refs=("chain:" + withdrawn.key,),
                suggested_next_action="put the numbers in the caption.",
                uncertainty=Uncertainty(kind="low", what_is_uncertain="nothing"),
                rule_refs=(
                    RuleCitation(
                        rule_id=withdrawn.rule_id,
                        version=1,
                        statement=WITHDRAWN_RULE,
                        counterexamples=(),
                    ),
                ),
            )
        )
    )
    assert refused_card is RoleRefusal.CITATION_NOT_MINTED_BY_THE_MEMORY

    # **The retrieval layer reports the same rule, on the same source.**
    gone = invalidated_rules(withdrawn.context)
    assert [item.rule.rule_id for item in gone] == [withdrawn.rule_id]
    assert [
        (source.issue_key, source.found, source.reachable, source.addressed)
        for source in gone[0].reasons
    ] == [(withdrawn.key, True, True, False)]

    # **And a rule that still stands on a living source is citable.** The
    # rule names the withdrawn source and the answered one; the memory
    # serves it on the source that stands, and the citation path cites
    # what the memory serves.
    standing = cite_rule(withdrawn.context, rule_id=withdrawn.standing_rule_id)
    assert standing.rule_id == withdrawn.standing_rule_id
    assert [hit.rule.rule_id for hit in search_rules(withdrawn.context)] == [
        withdrawn.standing_rule_id
    ]


def test_a_card_cannot_cite_a_rule_whose_source_the_reader_may_not_read(
    withdrawn: Withdrawn,
) -> None:
    """The reader's permission decides what the memory serves them.

    **The same rule, read by a reader the policy denies the material to.**
    The source is found and judged answered, and it is out of *this*
    reader's reach — so the memory does not serve it, and the citation
    path, which asks the memory's question, does not either.

    **And the refusal says which of the three deaths it was.** A refusal
    that said only "not served" would be a refusal nobody could act on:
    the reach is what the reader can act on, and the withdrawal is not
    what happened here.

    **What would make this red:** a citation path that looked for a
    withdrawn judgement only. It would find none, cite the rule, and the
    reader would be handed material the policy denies them.
    """
    denied = _denied_reader(withdrawn.context)
    refused = _capture(lambda: cite_rule(denied, rule_id=withdrawn.standing_rule_id))
    assert _refusal(refused) is RoleRefusal.RULE_NOT_SERVED_BY_THE_MEMORY
    assert withdrawn.standing_rule_id in refused.detail
    assert "out of this reader's reach" in refused.detail

    # **And the reader who may read it is served it.**
    assert cite_rule(withdrawn.context, rule_id=withdrawn.standing_rule_id).rule_id == (
        withdrawn.standing_rule_id
    )


def test_a_card_cannot_cite_a_confirmed_rule_nobody_judged(
    unattested: Unattested,
) -> None:
    """A source nobody judged is not withdrawn — and it is not served either.

    **The decision, and why.** The contract (ADR-0016 C10) forbids a
    card that cites a rule whose source material has been *withdrawn*: a
    judgement that says the change did not answer the comment. A source
    nobody has judged has not been withdrawn — nobody has said anything
    about it — and **the refusal says so, in those words**, because
    saying "withdrawn" here would be false.

    **But the citation path asks the memory's question, not a narrower
    one.** The retrieval layer serves a *confirmed* rule only on the
    sources that carry a judgement saying the change answered, and it
    reports this rule as invalidated; a citation that asked a different
    question would be a second definition of what the memory serves, and
    the two could disagree. So the citation is refused.

    **What would make this red:** a citation path that asked only about
    withdrawal. It would find no withdrawn judgement, cite the rule, and
    a card would advise on material the memory reports as invalidated.
    """
    refused = _capture(lambda: cite_rule(unattested.context, rule_id=unattested.rule_id))
    assert _refusal(refused) is RoleRefusal.RULE_NOT_SERVED_BY_THE_MEMORY
    assert unattested.rule_id in refused.detail
    assert unattested.key in refused.detail
    assert "nobody has judged" in refused.detail
    assert "withdrawn" not in refused.detail, (
        "nothing was withdrawn from under this rule, and the refusal says so"
    )

    # **And the retrieval layer reports the same rule, on the same source.**
    gone = invalidated_rules(unattested.context)
    assert [item.rule.rule_id for item in gone] == [unattested.rule_id]
    assert [(source.issue_key, source.found, source.reachable) for source in gone[0].reasons] == [
        (unattested.key, True, True)
    ]


def test_a_candidate_whose_source_nobody_judged_is_still_cited(
    guidance: Guidance,
) -> None:
    """A proposal's cases have usually not been judged at all.

    **The candidate is the case the memory exempts**: a rule nobody has
    confirmed yet is shown to its reviewer on the cases that exist, and
    requiring a judgement to show the proposal would hide from the
    reviewer the very thing they are to judge. So the memory serves a
    candidate whose source is found and in the reader's reach — an
    unattested source and a live one — and the citation path cites what
    the memory serves, counterexamples and all.

    **What would make this red:** a citation path that asked for a
    judgement on every source. It would refuse this rule, and the card
    would lose the very rule the reviewer is there to judge.
    """
    citation = cite_rule(guidance.context, rule_id=guidance.rule_id)
    assert citation.rule_id == guidance.rule_id
    assert citation.statement == RULE
    assert citation.counterexamples
    assert [
        hit.rule.rule_id for hit in search_rules(guidance.context, include_candidates=True)
    ] == [guidance.rule_id]


def test_a_rule_the_memory_does_not_hold_and_one_it_does_not_serve_have_two_reasons(
    withdrawn: Withdrawn,
) -> None:
    """A caller that switches on the reason has to be able to tell them apart.

    **"The memory holds no rule under that id"** and **"the memory holds
    the rule and does not serve it"** are two situations with two
    remedies, and the vocabulary's own rule is that each member names
    what was wrong. The first is a mistake about an id; the second is a
    rule whose material has been withdrawn, and no amount of retrying the
    id will bring it back.

    **What would make this red:** one member for both — the second
    refusal would carry the first's reason, and a caller could not tell
    a typo from a withdrawal.
    """
    missing = _capture(lambda: cite_rule(withdrawn.context, rule_id="rule-nowhere"))
    unserved = _capture(lambda: cite_rule(withdrawn.context, rule_id=withdrawn.rule_id))
    assert _refusal(missing) is RoleRefusal.RULE_NOT_IN_THE_MEMORY
    assert _refusal(unserved) is RoleRefusal.RULE_NOT_SERVED_BY_THE_MEMORY
    assert missing.reason is not unserved.reason


def test_a_card_refuses_a_citation_the_memory_did_not_mint(guidance: Guidance) -> None:
    """The card's subject is the card, and a citation is the memory's.

    **A caller can write a citation by hand** — the type is public and
    its fields are plain — and a statement the memory never held is not a
    citation. So the citation carries a token only
    :func:`cite_rule` can present, and the card refuses a citation that
    does not carry it. **The token says where the citation came from and
    nothing else**: it is not rendered, not compared, and not carried
    onto the wire.

    **And the positive case holds**: a card with a citation the memory
    minted is accepted, with the statement and the counterexamples the
    memory's own read gave.

    **What would make this red:** a card that took any citation it was
    handed. The statement below would go into the card and out to the
    reader as the memory's own advice.
    """
    forged = RuleCitation(
        rule_id=guidance.rule_id,
        version=1,
        statement="A statement the memory never held.",
        counterexamples=(),
    )
    refused = _capture(
        lambda: build_card(
            guidance.context,
            spec=guidance.spec,
            issue_type="method_and_hypothesis",
            severity="major",
            reason="the comparison's baseline is nowhere in the paragraph.",
            evidence_refs=("chain:" + guidance.key,),
            suggested_next_action="name the baseline.",
            uncertainty=Uncertainty(kind="low", what_is_uncertain="nothing"),
            rule_refs=(forged,),
        )
    )
    assert _refusal(refused) is RoleRefusal.CITATION_NOT_MINTED_BY_THE_MEMORY
    assert "never held" in refused.detail

    minted = cite_rule(guidance.context, rule_id=guidance.rule_id)
    card = build_card(
        guidance.context,
        spec=guidance.spec,
        issue_type="method_and_hypothesis",
        severity="major",
        reason="the comparison's baseline is nowhere in the paragraph.",
        evidence_refs=("chain:" + guidance.key,),
        suggested_next_action="name the baseline.",
        uncertainty=Uncertainty(kind="low", what_is_uncertain="nothing"),
        rule_refs=(minted,),
    )
    assert card.rule_refs == (minted,)
    assert card.rule_refs[0].statement == RULE
    assert card.rule_refs[0].counterexamples


def test_the_role_run_does_not_send_a_rule_the_memory_does_not_serve(
    withdrawn: Withdrawn,
) -> None:
    """The citation is the first read of the rule, and the excerpts are what leave.

    **The role run puts the citation's statement into the excerpts** the
    approval binds, so a check that came after the excerpts were built
    would come after the withdrawn rule had already left the machine.
    The citation path is before that, and this drives the run to show it:
    the same request with a rule the memory serves carries that rule's
    statement in the excerpts, and the same request with the withdrawn
    rule is refused — so there is no excerpt, and no statement in it.

    **What would make this red:** a role run that built its citation by
    hand, or one that asked the excerpts before it asked the memory. The
    first would put the withdrawn rule's statement into the excerpts; the
    second would refuse, but too late to keep the text off the machine.
    """
    plan = ModelCallPlan(
        provider="fake",
        model="scripted",
        root_id=MATERIAL_ROOT,
        resource_key=MATERIAL_KEY,
        material_ref=MATERIAL_PATH,
        purpose="guidance_review",
        destination=DESTINATION,
        subject_ref=withdrawn.chain.project_id,
    )

    def _question(rule_id: str) -> RoleRunQuestion:
        return the_role_run_question(
            withdrawn.context,
            RoleRunRequest(
                roles=("guidance",),
                project_id=withdrawn.chain.project_id,
                issue_key=withdrawn.key,
                version_ids=(withdrawn.chain.version_id,),
                rule_id=rule_id,
            ),
            plan=plan,
        )

    # **The positive control.** The same request with a rule the memory
    # serves carries that rule's statement in the excerpts the approval
    # binds — so the excerpts really do carry a rule's text.
    served = _question(withdrawn.standing_rule_id)
    assert STANDING_RULE in served.excerpts

    # **And the withdrawn rule produces no excerpts at all.** The run is
    # refused at the citation, before the question is built, so the
    # withdrawn rule's statement is nowhere in what the run produced.
    refused = _capture(lambda: _question(withdrawn.rule_id))
    assert _refusal(refused) is RoleRefusal.RULE_NOT_SERVED_BY_THE_MEMORY
    assert withdrawn.rule_id in refused.detail
    assert WITHDRAWN_RULE not in refused.detail, (
        "the withdrawn rule's statement does not go out with the refusal either"
    )


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
    assert card.claims[0].advisor_quote == quote
    assert quote in guidance.event.comment_text


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
