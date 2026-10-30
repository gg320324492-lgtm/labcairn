"""The retrieval: a rule is served only while its sources stand.

**What is under test.** LC-P2-11 T02 and T03: the serve-time source check
and the search over the memory.

=====================================================  =========================
T02  a rule is served only while its source stands     the chain's judgement,
                                                       the reader's permission,
                                                       not the memory's, says
                                                       whether material
                                                       supports the rule
T03  the withdrawal, and what it invalidates           the retrieval stops
                                                       serving the rule, and
                                                       the invalidation is
                                                       reported, with the
                                                       reason
=====================================================  =========================

**Why the chain rows are real.** The source check reads
``feedback_events`` and ``response_links`` as the chain's own API wrote
them — ``build_chain`` and ``record_feedback`` produce exactly the rows a
real manuscript round produces, and the judgement rows are written by hand
because writing them is the judgement itself: a test that mints a
judgement by hand is saying what a person said, which is what the
``response_links`` row records anyway.
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
from labcairn.db.models import (
    EditActionRow,
    FeedbackEventRow,
    GuidanceRuleRow,
    PaperVersionRow,
    ResponseLinkRow,
    VersionEdgeRow,
)
from labcairn.guidance.distil import distil_candidate
from labcairn.guidance.retrieval import RuleHit, invalidated_rules, search_rules
from labcairn.guidance.rules import (
    GuidanceRule,
    confirm_rule,
    dispute_rule,
    propose_rule,
    record_counterexample,
    supersede_rule,
)
from labcairn.papers.feedback import FeedbackEvent, record_feedback, set_issue_key
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import CapabilityId
from labcairn.security.policy import Permission, PermissionPolicy, Rule

pytestmark = pytest.mark.integration

env = _shared_env

MOMENT = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)
LATER = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)

KEY_ONE = "iss-gold-a-r1"
KEY_TWO = "iss-gold-a-r2"

BASELINE = (
    "When the claim rests on a comparison, the advisor asks for the baseline"
    " to be named in the same paragraph."
)
CAPTION = "When a figure carries the claim, the advisor asks for the numbers in the caption."

EFFECT = (
    "When the claim rests on an effect size, the advisor asks for the"
    " interval to be shown beside it."
)


@dataclass(frozen=True)
class Memory:
    """The context, the chain it reads, and the feedback ids under their keys."""

    context: ApplicationContext
    chain: ChainEnv
    events: tuple[FeedbackEvent, ...]


def _rejudge(memory: Memory, response_link_id: str, state: str) -> None:
    """Change one judgement's state — the row a re-judgement leaves behind."""
    session = memory.context.store.session
    row = session.get(ResponseLinkRow, response_link_id)
    assert row is not None, f"the chain holds no response link {response_link_id!r}"
    row.state = state
    session.flush()


def _propose(
    context: ApplicationContext,
    *,
    statement: str = BASELINE,
    issue_type: str = "method_and_hypothesis",
    sources: tuple[str, ...] = (KEY_ONE,),
    proposed_by: str = "distil-run-7",
    now: datetime = MOMENT,
) -> GuidanceRule:
    return propose_rule(
        context,
        issue_type=issue_type,
        statement=statement,
        rule_context="A results section whose claim is comparative.",
        scope="Empirical papers in this group's field.",
        example="The comment of 2026-03-02 on the ablation paragraph.",
        sources=sources,
        proposed_by=proposed_by,
        now=now,
    )


def _confirm(context: ApplicationContext, **propose_kwargs: object) -> GuidanceRule:
    """A confirmed rule: proposed by one, confirmed by a second reader."""
    rule = _propose(context, **propose_kwargs)  # type: ignore[arg-type]
    return confirm_rule(context, rule_id=rule.rule_id, confirmed_by="the-advisor", now=LATER)


def _denied_reader(memory: Memory) -> ApplicationContext:
    """The same store, under a policy that denies reading the material."""
    return ApplicationContext(
        workspace=memory.context.workspace,
        store=memory.context.store,
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


@pytest.fixture()
def memory(env: StoreEnv, tmp_path: Path) -> Memory:
    """A chain with two judged comments, under the keys the rules cite.

    **Both comments are judged ``addressed``,** so a rule over either
    source stands until the test re-judges it — the default is a healthy
    chain, and the witnesses change one thing each.
    """
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    store = env.store()
    chain = build_chain(store, workspace_root, comments=(a_comment("201"), a_comment("202")))
    events = record_feedback(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.version_id,
        now=MOMENT,
    )
    assert len(events) == 2, "the fixture's manuscript carries two comments"
    session = chain.context.store.session
    keyed: list[FeedbackEvent] = []
    for event, key in zip(events, (KEY_ONE, KEY_TWO), strict=True):
        edit_action_id = f"edit-{event.feedback_id[-6:]}"
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
        session.add(
            ResponseLinkRow(
                response_link_id=f"resp-{key[-2:]}",
                feedback_id=event.feedback_id,
                edit_action_id=edit_action_id,
                state="addressed",
                grade="human_verified",
                decided_by="user",
                decided_at=LATER,
                evidence_refs=[f"check:{key}"],
                created_at=LATER,
            )
        )
        keyed.append(
            set_issue_key(chain.context, feedback_id=event.feedback_id, issue_key=key, now=MOMENT)
        )
    session.flush()
    return Memory(context=chain.context, chain=chain, events=tuple(keyed))


def test_a_withdrawn_source_invalidates_its_rule_and_says_so(memory: Memory) -> None:
    """T02: the chain's judgement, read at query time, decides the serving.

    **And a re-judgement brings the rule back** — the memory was never
    touched; what changed is the row that says whether the source stands,
    and the retrieval reads it again on every query. An expired thing is
    judged by its state, not by the clock.
    """
    _confirm(memory.context)
    served = search_rules(memory.context)
    assert [hit.rule.statement for hit in served] == [BASELINE]
    assert [
        (source.issue_key, source.found, source.reachable, source.addressed)
        for source in served[0].sources
    ] == [(KEY_ONE, True, True, True)]

    _rejudge(memory, "resp-r1", "not_addressed")
    assert search_rules(memory.context) == (), (
        "a rule whose source was judged unanswered is not a rule a card may cite"
    )
    # And the withdrawal is not silent: the rule is reported, with the
    # reason the dead source gives.
    gone = invalidated_rules(memory.context)
    assert [item.rule.statement for item in gone] == [BASELINE]
    assert [
        (source.issue_key, source.found, source.reachable, source.addressed)
        for source in gone[0].reasons
    ] == [(KEY_ONE, True, True, False)]

    _rejudge(memory, "resp-r1", "addressed")
    served_back = search_rules(memory.context)
    assert [hit.rule.statement for hit in served_back] == [BASELINE]


def test_a_rule_with_two_sources_stands_on_the_one_that_lives(memory: Memory) -> None:
    """T02: one source withdrawn does not take the rule with it.

    **The dead source leaves the served tuple** — a card that cites a
    source the chain has withdrawn is citing something that is not there,
    so the hit carries the sources that live and nothing else.
    """
    _confirm(memory.context, sources=(KEY_ONE, KEY_TWO))
    _rejudge(memory, "resp-r1", "not_addressed")
    served = search_rules(memory.context)
    assert len(served) == 1
    assert [source.issue_key for source in served[0].sources] == [KEY_TWO]


def test_a_source_that_names_no_material_does_not_stand(memory: Memory) -> None:
    """T02: a key the chain cannot show is not a source.

    **The memory claiming to have learned from material it cannot point
    at is the claim the serve-time check exists to catch** — propose-time
    does not resolve the key, so a mistyped key gets in and stays out of
    the cards, visibly, by the rule not being served.
    """
    _confirm(memory.context, sources=("iss-nowhere",))
    assert search_rules(memory.context) == ()
    # The rule is not gone — it is unserved. The reviewer's view shows it.
    pending = search_rules(memory.context, include_candidates=True)
    assert pending == (), "a confirmed rule with no standing source is not served either way"
    # And the report says why: the key names material the chain cannot show.
    gone = invalidated_rules(memory.context)
    assert [item.rule.rule_id for item in gone] != []
    assert gone[0].reasons[0].found is False


def test_a_rule_outside_the_readers_consent_is_not_retrieved(memory: Memory) -> None:
    """T02: the permission layer decides which sources stand, per reader.

    **The same memory answers differently to two readers**, because the
    permission layer is asked at query time and the denied material is
    dropped rather than refused (ADR-0003 C5) — a rule whose only source
    is out of a reader's reach does not come back to that reader, and
    nothing in the memory was changed to make it so.
    """
    _confirm(memory.context)
    assert len(search_rules(memory.context)) == 1, "the allowed reader is served"

    session = memory.context.store.session
    denied_context = _denied_reader(memory)
    assert search_rules(denied_context) == (), (
        "a rule whose source the reader cannot read is not a rule that reader is served"
    )
    # The report still speaks: the reason is reach, not the chain's state.
    gone = invalidated_rules(denied_context)
    assert [item.rule.statement for item in gone] == [BASELINE]
    assert gone[0].reasons[0].reachable is False
    assert gone[0].reasons[0].addressed is True
    # And the denied reader's query changed nothing: the allowed reader
    # asking again is served exactly as before, and the chain rows were
    # never touched by any of this.
    assert len(search_rules(memory.context)) == 1
    assert session.query(ResponseLinkRow).filter_by(state="addressed").count() == 2, (
        "the queries judged nothing; only the reader's view changed"
    )


def test_a_rule_with_one_dead_source_is_not_invalidated(memory: Memory) -> None:
    """T03: partial invalidation is the living source's business.

    **A rule still served is not a rule reported invalid** — the two
    answers must agree about the same rule at the same moment: served on
    one source, and absent from the invalidation report.
    """
    _confirm(memory.context, sources=(KEY_ONE, KEY_TWO))
    _rejudge(memory, "resp-r1", "not_addressed")
    served = search_rules(memory.context)
    assert len(served) == 1
    assert invalidated_rules(memory.context) == ()


def test_two_conflicting_rules_are_both_returned_and_neither_wins_by_recency(
    memory: Memory,
) -> None:
    """T03: the retrieval does not resolve conflicts, and never by recency.

    **Two confirmed rules over the same problem both come back**, and the
    order between them is their ids and nothing else — not who proposed
    later, not which version is higher. The work order's refusal is
    *"an advisor prefers this style"*; a retrieval that let the newest
    rule win would hand the preference a gatekeeper.
    """
    first = _confirm(memory.context, statement=BASELINE)
    second = _confirm(memory.context, statement=EFFECT)
    assert first.rule_id != second.rule_id
    served = search_rules(memory.context, issue_type="method_and_hypothesis")
    assert {hit.rule.statement for hit in served} == {BASELINE, EFFECT}
    assert len(served) == 2
    assert [hit.rule.rule_id for hit in served] == sorted(hit.rule.rule_id for hit in served)
    assert all(hit.sources for hit in served), "each rule comes back with its sources"


def test_a_candidate_is_not_served_unless_asked(memory: Memory) -> None:
    """T03: a proposal reaches a reviewer's query, never a card.

    **And the newest version does not displace the served one by being
    newer.** After a supersede, the confirmed first version is shadowed
    by its own candidate successor — a rule mid-rewording leaves the
    cards until its second reader confirms it — while the reviewer's
    query sees only the highest version, once, not both.
    """
    candidate = _propose(memory.context)
    assert search_rules(memory.context) == ()
    pending = search_rules(memory.context, include_candidates=True)
    assert [hit.rule.rule_id for hit in pending] == [candidate.rule_id]

    confirmed = confirm_rule(
        memory.context, rule_id=candidate.rule_id, confirmed_by="the-advisor", now=LATER
    )
    replacement = supersede_rule(
        memory.context,
        rule_id=confirmed.rule_id,
        statement=(
            "When the claim rests on a comparison, the advisor names the"
            " baseline and the effect size together."
        ),
        rule_context="A results section whose claim is comparative.",
        scope="Empirical papers in this group's field.",
        example="The comment of 2026-03-02 on the ablation paragraph.",
        issue_type="method_and_hypothesis",
        sources=(KEY_ONE,),
        proposed_by="distil-run-8",
        now=LATER,
    )
    served = search_rules(memory.context)
    assert served == (), (
        "the confirmed first version is shadowed by its own candidate successor —"
        " a rule mid-rewording leaves the cards until its second reader confirms it"
    )
    reviewer = search_rules(memory.context, include_candidates=True)
    assert [hit.rule.version for hit in reviewer] == [2], (
        "the reviewer sees the highest version only, once, not both"
    )
    assert [hit.rule.rule_id for hit in reviewer] == [replacement.rule_id]


def test_a_disputed_rule_is_served_with_its_reason_and_ranks_last(memory: Memory) -> None:
    """T03: disputed is served — with the case against it, after the sound ones.

    **The reason travels in the rule itself**, so a card showing a
    disputed rule cannot show it without the dispute. And the disputed
    rule does not come first: the order says what is settled and what is
    contested without a single word of display logic.
    """
    _confirm(memory.context, statement=BASELINE)
    challenged = _confirm(memory.context, statement=EFFECT)
    dispute_rule(
        memory.context,
        rule_id=challenged.rule_id,
        reason="The two corpus cases where the interval was already shown.",
        disputed_by="reader-2",
        now=LATER,
    )
    served = search_rules(memory.context)
    assert [hit.rule.state for hit in served] == ["confirmed", "disputed"]
    assert served[1].rule.resolution_reason is not None
    assert "corpus cases" in served[1].rule.resolution_reason


def test_the_query_filters_and_the_vocabulary_gates_it(memory: Memory) -> None:
    """T03: containment over the rule's own fields; the vocabulary at the door.

    **A miss is an empty answer, not a refusal** — the empty result for a
    query nobody's statement contains is the retrieval being honest, and
    the refusal is reserved for a problem outside the closed vocabulary,
    where the query itself is not one the memory can hold.
    """
    _confirm(memory.context, statement=BASELINE)
    _confirm(memory.context, statement=EFFECT, issue_type="statistical_conclusion")

    hit = search_rules(memory.context, query="baseline")
    assert [rule.statement for rule in (h.rule for h in hit)] == [BASELINE]
    assert search_rules(memory.context, query="confounder") == ()
    assert search_rules(memory.context, issue_type="statistical_conclusion") != ()
    assert search_rules(memory.context, issue_type="figures") == ()

    with pytest.raises(ApplicationRefusedError) as raised:
        search_rules(memory.context, issue_type="advisor_preference")
    assert raised.value.reason.value == "guidance_problem_outside_vocabulary"


def test_a_counterexample_comes_back_with_the_rule(memory: Memory) -> None:
    """T03: the case against the rule is inside the hit, not beside it.

    **The caller cannot drop the cases** — they are fields of the rule
    the hit carries, so serving without them would mean not serving the
    rule at all.
    """
    confirmed = _confirm(memory.context)
    record_counterexample(
        memory.context,
        rule_id=confirmed.rule_id,
        statement=(
            "The ablation paragraph of 2026-03-09 named its baseline, and the advisor said nothing."
        ),
        recorded_by="reader-2",
        now=LATER,
        issue_key=KEY_TWO,
    )
    served = search_rules(memory.context)
    assert len(served) == 1
    hit: RuleHit = served[0]
    assert len(hit.rule.counterexamples) == 1
    assert hit.rule.counterexamples[0].recorded_by == "reader-2"


def test_the_ceiling_cuts_after_the_ordering(memory: Memory) -> None:
    """T03: the limit takes the hits the order ranked first, not first come.

    **A ceiling applied before the ordering would make the result depend
    on the table's row order** — which rule happened to be stored first —
    and that is an order that consults nothing and decides everything.
    """
    _confirm(memory.context, statement=BASELINE)
    _confirm(memory.context, statement=EFFECT)
    _confirm(
        memory.context,
        statement=(
            "When a figure carries the claim, the advisor asks for the numbers in the caption."
        ),
        issue_type="figures",
    )
    served = search_rules(memory.context, limit=2)
    assert len(served) == 2
    whole = search_rules(memory.context)
    assert served == whole[:2]


def test_every_rule_reaches_a_real_comment_and_a_real_difference(memory: Memory) -> None:
    """A1: a served rule's sources resolve to words somebody wrote, and a change.

    **The trace is walked to the end, not to the first table**: the key
    finds the comment (with its words), the comment finds the edit made
    in answer, and the edit finds the version pair it moved — which is a
    *difference*, two versions, not one row pointing at itself.
    """
    _confirm(memory.context, sources=(KEY_ONE, KEY_TWO))
    session = memory.context.store.session
    for hit in search_rules(memory.context):
        for source in hit.sources:
            events = session.query(FeedbackEventRow).filter_by(issue_key=source.issue_key).all()
            assert events, f"the chain holds no comment under {source.issue_key!r}"
            for event in events:
                assert event.comment_text.strip(), "the comment has no words in it"
                edits = session.query(EditActionRow).filter_by(feedback_id=event.feedback_id).all()
                assert edits, "no change was made in answer to the comment"
                for edit in edits:
                    edge = session.get(VersionEdgeRow, edit.version_edge_id)
                    assert edge is not None, "the edit names no version pair"
                    parent = session.get(PaperVersionRow, edge.parent_version_id)
                    child = session.get(PaperVersionRow, edge.child_version_id)
                    assert parent is not None and child is not None, (
                        "the edge names versions the store does not hold"
                    )
                    assert parent.version_id != child.version_id, "the pair is no difference at all"


def test_the_retrieval_returns_the_rule_with_its_source_and_its_conditions(
    memory: Memory,
) -> None:
    """A10: the hit carries the anchor and the conditions, never a bare sentence.

    **An empty condition would make the statement bare** — a rule whose
    scope or example is missing cannot be checked against a paper it is
    applied to, so the retrieval's answer carries all of them, filled.
    """
    _confirm(memory.context)
    hit = search_rules(memory.context)[0]
    assert hit.sources and hit.sources[0].issue_key == KEY_ONE
    assert hit.rule.rule_id
    for condition in (hit.rule.statement, hit.rule.context, hit.rule.scope, hit.rule.example):
        assert condition.strip(), "an empty condition is a bare sentence with a title"
    assert hit.rule.counterexamples == ()


def test_the_memory_reads_through_the_consent_layer(
    memory: Memory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A11: every read asks the permission layer, and nothing bypasses it.

    **The spy is the witness of "every"**: the memory's two read paths —
    the search and the invalidation report — both go through
    ``evaluate_each``, the same function a bulk listing goes through.
    The mutation that discards the policy's answer reddens
    ``test_a_rule_outside_the_readers_consent_is_not_retrieved``, which
    is what keeps this spy from watching an unused call.
    """
    from labcairn.guidance import retrieval as retrieval_module

    _confirm(memory.context)
    asked: list[str] = []
    real = retrieval_module.consent.evaluate_each

    def spy(context: object, **kwargs: object):
        asked.append(kwargs["capability"].value)
        return real(context, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(retrieval_module.consent, "evaluate_each", spy)
    assert search_rules(memory.context), "the served rules exercise the read path"
    assert asked, "the memory answered without asking the permission layer"
    assert asked.count(CapabilityId.SOURCE_READ.value) == len(asked)

    asked.clear()
    _rejudge(memory, "resp-r1", "not_addressed")
    assert invalidated_rules(memory.context)
    assert asked, "the invalidation report read the material without asking either"


def test_a_new_comment_changes_the_retrieval_without_anything_trained(
    memory: Memory,
) -> None:
    """A12: the case library grows, the retrieval finds it, nothing is trained.

    **There is no trainer to assert the absence of** — this product has
    no weights, so the mechanical witness is where the change lives: in
    the memory's rows, one distilled and confirmed, and nowhere else.
    The retrieval's answer changes because a row was added, and the
    difference between the two queries is exactly that row.
    """
    _confirm(memory.context, statement=BASELINE)
    before = search_rules(memory.context)
    assert [hit.rule.statement for hit in before] == [BASELINE]

    distilled = distil_candidate(
        memory.context,
        issue_type="figures",
        statement=CAPTION,
        rule_context="A figure that carries the claim.",
        issue_keys=(KEY_TWO,),
        now=LATER,
    )
    confirm_rule(memory.context, rule_id=distilled.rule_id, confirmed_by="the-advisor", now=LATER)

    served = search_rules(memory.context)
    assert {hit.rule.statement for hit in served} == {BASELINE, CAPTION}
    rows = memory.context.store.session.query(GuidanceRuleRow).count()
    assert rows == 2, "the change the retrieval found is the row the memory gained"
