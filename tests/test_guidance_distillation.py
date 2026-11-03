"""The distillation: a model proposes, a person confirms, nobody invents a scope.

**What is under test.** LC-P2-11 T01's model half: ``distil_candidate``
and the three properties the work order names for it.

=====================================================  =========================
A7  a distilled rule is a **candidate** until a person  the creator is
    confirms it                                        ``model_proposal``,
                                                       and the proposer
                                                       cannot confirm their
                                                       own rule
A8  a suggestion does not become an advisor's rule by  retrieval has no
    being retrieved often                              side effects
A9  a rule whose scope the cases do not support is     the scope is the
    refused                                            cases', or there is
                                                       no rule
A** a re-run of one distillation is one row             the clock does not
                                                       name the rule, and a
                                                       re-run writes nothing
=====================================================  =========================

**And A9 has a second half.** The scope the cases give is the
*applicability condition*, and it has to be **true**: a case whose
comment the reader could not place in the body carries no anchored text
at all, and a scope that quoted that empty string as the advisor's words
would say the advisor wrote about nothing — which is not what happened.
So the scope names every case it holds: the text the comment was written
against, or the fact that the reader could not place it, with the reason
the chain gives.

**And a comment rule can be written again under its own id.** The comment
path's version door is ``distil_comment_version_of``, the sibling of the
revision path's ``distil_revision_version_of``: it keeps the rule's
``rule_id``, takes the scope and the example from the cases, carries the
comment path's ``model_proposal``, and lands as a candidate that only a
second reader may confirm. Its witnesses are the second half of this
file.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from docx_fixtures import Comment
from feedback_chain_fixtures import PARAGRAPH, a_comment, build_chain
from sqlalchemy import select, text
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.application import chain as chain_layer
from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import ApplicationRefusedError
from labcairn.db.models import EditActionRow, GuidanceRuleRow, ResponseLinkRow
from labcairn.guidance.distil import (
    MODEL_PROPOSER,
    distil_candidate,
    distil_comment_version_of,
)
from labcairn.guidance.refusals import GuidanceRefusal
from labcairn.guidance.retrieval import search_rules
from labcairn.guidance.rules import GuidanceRule, confirm_rule, read_rule
from labcairn.papers.feedback import record_feedback, set_issue_key
from labcairn.security.policy import Permission, PermissionPolicy, Rule

pytestmark = pytest.mark.integration

env = _shared_env

MOMENT = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)
LATER = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)

KEY = "iss-gold-a-r1"
#: The key of a second case, on the manuscript's second paragraph. **The
#: version witness uses a different case from the first version**, so a
#: scope or example copied from the old row cannot pass for the cases'.
KEY_OTHER = "iss-gold-d-r1"
#: The key of a case whose comment the reader could not place in the body.
KEY_UNPLACED = "iss-gold-b-r1"
#: The key of a case whose comment the reader placed on a point, so the
#: anchor resolved to an empty text.
KEY_POINT = "iss-gold-c-r1"
#: The second paragraph of the two-paragraph manuscript.
SECOND_PARAGRAPH = "The comparison group is not named."

STATEMENT = (
    "When the claim rests on a comparison, the advisor asks for the baseline"
    " to be named in the same paragraph."
)


def allow_all() -> PermissionPolicy:
    """A policy that permits everything, for a test about something else."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])


def _refusal(error: ApplicationRefusedError) -> GuidanceRefusal:
    return GuidanceRefusal(error.reason.value.removeprefix("guidance_"))


@pytest.fixture()
def cases(env: StoreEnv, tmp_path: Path) -> tuple[ApplicationContext, str]:
    """A chain with one judged comment under one key: a case to distil from.

    **No judgement rows** — the distillation reads the case, not the
    verdict on what was done about it; whether the change answered the
    comment is the retrieval's question, asked at serve time.
    """
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    store = env.store()
    chain = build_chain(
        store,
        workspace_root,
        comments=(a_comment("201"),),
    )
    events = record_feedback(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.version_id,
        now=MOMENT,
    )
    set_issue_key(chain.context, feedback_id=events[0].feedback_id, issue_key=KEY, now=MOMENT)
    return chain.context, chain.project_id


def _distil(context: ApplicationContext, **overrides: object) -> GuidanceRule:
    kwargs: dict[str, object] = {
        "issue_type": "method_and_hypothesis",
        "statement": STATEMENT,
        "rule_context": "A results section whose claim is comparative.",
        "issue_keys": (KEY,),
        "now": MOMENT,
    }
    kwargs.update(overrides)
    return distil_candidate(context, **kwargs)  # type: ignore[arg-type]


def _chain_keyed(
    env: StoreEnv,
    workspace_root: Path,
    comments: tuple[Comment, ...],
    keys: tuple[str, ...],
    *,
    paragraphs: tuple[str, ...] = (PARAGRAPH,),
    point_comment_ids: tuple[str, ...] = (),
) -> ApplicationContext:
    """A chain whose comments are recorded and filed under the keys given.

    **The keys are in the order the reader found the comments**, so a test
    may say which case is filed where without reading the file.
    """
    workspace_root.mkdir(parents=True)
    store = env.store()
    chain = build_chain(
        store,
        workspace_root,
        comments=comments,
        paragraphs=paragraphs,
        point_comment_ids=point_comment_ids,
    )
    events = record_feedback(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.version_id,
        now=MOMENT,
    )
    for key, event in zip(keys, events, strict=True):
        set_issue_key(chain.context, feedback_id=event.feedback_id, issue_key=key, now=MOMENT)
    return chain.context


def _judged_chain(env: StoreEnv, workspace_root: Path) -> ApplicationContext:
    """A chain with one comment under *KEY*, judged ``addressed``.

    **The judgement is written as the chain's own rows**, the way
    ``tests/test_guidance_retrieval.py`` writes it: the retrieval's
    source check reads ``response_links``, and a rule is served only
    while a judgement says the change answered the comment. The
    distillation's own fixture deliberately holds no judgement — the
    distillation reads the case, not the verdict — so the witness that
    has to see a rule served builds a judged chain of its own.
    """
    workspace_root.mkdir(parents=True)
    store = env.store()
    chain = build_chain(store, workspace_root, comments=(a_comment("201"),))
    events = record_feedback(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.version_id,
        now=MOMENT,
    )
    assert len(events) == 1, "the fixture's manuscript carries one comment"
    event = events[0]
    set_issue_key(chain.context, feedback_id=event.feedback_id, issue_key=KEY, now=MOMENT)
    session = chain.context.store.session
    session.add(
        EditActionRow(
            edit_action_id="edit-1",
            feedback_id=event.feedback_id,
            version_edge_id=chain.edge_id,
            actor_kind="student",
            grade="observed",
            created_at=MOMENT,
        )
    )
    session.add(
        ResponseLinkRow(
            response_link_id="resp-1",
            feedback_id=event.feedback_id,
            edit_action_id="edit-1",
            state="addressed",
            grade="human_verified",
            decided_by="user",
            decided_at=LATER,
            evidence_refs=["check:key"],
            created_at=LATER,
        )
    )
    session.flush()
    return chain.context


def _quoted_texts(scope: str) -> tuple[str, ...]:
    """The texts a scope quotes, as the scope spells them.

    **Read out of the scope itself**, so a witness cannot pass by agreeing
    with the code that built it: the scope is the only thing inspected.
    """
    return tuple(part for part in scope.split('"')[1::2])


def test_a_distilled_rule_is_a_candidate_until_a_person_confirms_it(
    cases: tuple[ApplicationContext, str],
) -> None:
    """A7: the creator is ``model_proposal``, and a person's word moves the state.

    **And the second-reader rule holds for a model's proposal too** —
    ``model_proposal`` is a proposer like any other, so the model cannot
    confirm its own work by any name.
    """
    context, _ = cases
    distilled = _distil(context)
    assert distilled.state == "candidate"
    assert distilled.proposed_by == MODEL_PROPOSER
    assert distilled.confirmed_by is None

    with pytest.raises(ApplicationRefusedError) as raised:
        confirm_rule(context, rule_id=distilled.rule_id, confirmed_by=MODEL_PROPOSER, now=LATER)
    assert _refusal(raised.value) is GuidanceRefusal.CONFIRMER_IS_PROPOSER

    confirmed = confirm_rule(
        context, rule_id=distilled.rule_id, confirmed_by="the-advisor", now=LATER
    )
    assert confirmed.state == "confirmed"
    assert confirmed.confirmed_by == "the-advisor"
    assert confirmed.confirmed_at == LATER


def test_a_rerun_of_one_distillation_is_one_row(
    cases: tuple[ApplicationContext, str],
) -> None:
    """The distillation door is idempotent: the same cases propose the same row.

    **This is the debt the stopgap paid for.** The pilot run pinned a chosen
    instant so that re-running it would reproduce the identity; but a re-run
    at that instant collides with the primary key, and a re-run at the real
    clock mints a second id. Deriving the identity from the draft makes the
    re-run land on the row that is already there, and lets ``proposed_at`` be
    the real clock: the second call returns the first row and writes nothing.
    """
    context, _ = cases
    first = _distil(context, now=MOMENT)
    second = _distil(context, now=LATER)
    assert second.rule_id == first.rule_id, "the clock moved the distilled identity"
    assert second.proposed_at == MOMENT, "a re-run rewrote the instant it was proposed at"
    rows = context.store.session.query(GuidanceRuleRow).all()
    assert len(rows) == 1, f"a re-run wrote a second row: {[(r.rule_id, r.version) for r in rows]}"


def test_a_frequently_retrieved_suggestion_is_still_a_candidate(
    cases: tuple[ApplicationContext, str],
) -> None:
    """A8: retrieval has no side effects, so no amount of it promotes anything.

    **D9 in one query loop**: five retrievals of the suggestion leave the
    row's state where it was, and leave the store holding no more rows
    than it did — a suggestion does not become an advisor's rule by
    being retrieved often, because nothing about retrieval writes
    anything down.
    """
    context, _ = cases
    distilled = _distil(context)
    before = context.store.session.query(GuidanceRuleRow).count()
    for _ in range(5):
        served = search_rules(context, include_candidates=True)
    assert [hit.rule.rule_id for hit in served] == [distilled.rule_id]
    after = context.store.session.query(GuidanceRuleRow).count()
    assert after == before, "retrieval wrote something, and a write is a promotion path"
    assert read_rule(context, rule_id=distilled.rule_id).state == "candidate"


def test_a_rule_with_an_unsupported_scope_is_refused(
    cases: tuple[ApplicationContext, str],
) -> None:
    """A9: the scope is the cases', or there is no rule.

    **No cases, no scope, no rule** — an empty case list is refused. A
    case the chain cannot show is refused by name. And a distilled
    rule's scope is the anchored text the cases were written against:
    the caller had no parameter to write it with, and the assembled
    scope says where it came from.
    """
    context, _ = cases

    with pytest.raises(ApplicationRefusedError) as raised:
        _distil(context, issue_keys=())
    assert _refusal(raised.value) is GuidanceRefusal.RULE_WITHOUT_SOURCE

    with pytest.raises(ApplicationRefusedError) as raised:
        _distil(context, issue_keys=("iss-nowhere",))
    assert _refusal(raised.value) is GuidanceRefusal.RULE_WITHOUT_SOURCE
    assert "iss-nowhere" in str(raised.value)

    distilled = _distil(context)
    assert distilled.scope == (
        'Cases whose anchored text reads: "The method estimates the parameter'
        ' from a single observation."'
    ), "the scope is the case's anchored text, assembled, not a caller's words"
    assert distilled.example.startswith("The advisor's comment (iss-gold-a-r1):")
    assert "Define the parameter." in distilled.example


# --------------------------------------------------------------------------- #
# the scope tells the truth about every case it names
# --------------------------------------------------------------------------- #


def test_a_case_the_reader_could_not_place_is_named_as_unplaced_and_never_quoted(
    env: StoreEnv, tmp_path: Path
) -> None:
    """A case with no anchored text is named as unplaced, and never as ``""``.

    **The empty string is not the advisor's words.** A comment the reader
    could not place in the body carries no anchored text, and a scope
    that quoted that empty string as though it were a quotation of the
    manuscript would say the advisor wrote about nothing — which is not
    what happened: the reader could not find where the remark sits.

    **So the scope says what happened**, and it says it with the reason
    the chain gives: the reader's own account of why the anchor is
    unknown, carried through rather than re-guessed here.

    **What breaks it:** a scope that quotes the empty string, or one that
    drops the case and names only the texts it can quote.
    """
    context = _chain_keyed(
        env,
        tmp_path / "chain",
        comments=(a_comment("201"), a_comment("202", anchor="none")),
        keys=(KEY, KEY_UNPLACED),
    )

    distilled = _distil(context, issue_keys=(KEY, KEY_UNPLACED))

    assert '""' not in distilled.scope, (
        f"the empty string was quoted as though it were the advisor's words: {distilled.scope!r}"
    )
    assert "could not place" in distilled.scope, (
        f"the scope does not say the comment was not placed: {distilled.scope!r}"
    )
    assert "the comment carries no range markers" in distilled.scope, (
        f"the scope does not name the reason the chain gives: {distilled.scope!r}"
    )
    assert f"the comment under {KEY_UNPLACED!r}" in distilled.scope, (
        f"the scope does not name the case it could not place: {distilled.scope!r}"
    )
    assert f'"{PARAGRAPH}"' in distilled.scope, (
        f"the scope dropped the case it could quote: {distilled.scope!r}"
    )


def test_a_scope_of_cases_that_all_have_anchored_text_is_the_shape_it_was(
    env: StoreEnv, tmp_path: Path
) -> None:
    """Every case names a text, and the scope reads as it always has.

    **The shape is unchanged**: the same lead, the same quoted texts, the
    same separator. A fix that made the scope say more about the cases it
    could quote would be a fix that changed every rule the product has
    ever written, and the change here is only about the cases it could
    not quote.

    **What breaks it:** a lead of its own for the ordinary case, or a
    separator that is not the one the scope has always used.
    """
    context = _chain_keyed(
        env,
        tmp_path / "chain",
        comments=(a_comment("201"), a_comment("202", paragraph=1, anchor_text="comparison group")),
        keys=(KEY, "iss-gold-a-r2"),
        paragraphs=(PARAGRAPH, SECOND_PARAGRAPH),
    )

    distilled = _distil(context, issue_keys=(KEY, "iss-gold-a-r2"))

    assert distilled.scope == (
        'Cases whose anchored text reads: "The comparison group is not named."; '
        '"The method estimates the parameter from a single observation."'
    ), "the scope of cases that all name a text reads as it always has"


def test_a_case_that_resolved_to_an_empty_text_is_not_a_case_that_was_never_placed(
    env: StoreEnv, tmp_path: Path
) -> None:
    """Two facts, and the scope keeps them apart.

    **These are different facts.** A comment anchored on a point *is*
    placed — the reader found where it sits — and the text it covers is
    empty; a comment the reader could not place is not placed at all.
    **Both carry an empty anchored text**, so the text alone cannot tell
    them apart, and a scope that gave them the same words would be wrong
    about one of them.

    **So the scope says which is which**: *"resolved to an empty text"*
    for the one the reader placed, and *"could not place"* for the one it
    did not. **And neither is quoted as the empty string.**

    **What breaks it:** a scope that treats a resolved-but-empty anchor as
    an unplaced one (or the other way round), and a scope that quotes
    the empty string for either.
    """
    context = _chain_keyed(
        env,
        tmp_path / "chain",
        comments=(a_comment("301"), a_comment("302", anchor="none")),
        keys=(KEY_POINT, KEY_UNPLACED),
        point_comment_ids=("301",),
    )

    point_scope = _distil(context, issue_keys=(KEY_POINT,), now=MOMENT).scope
    unplaced_scope = _distil(context, issue_keys=(KEY_UNPLACED,), now=LATER).scope

    assert '""' not in point_scope, (
        f"the empty string was quoted as the advisor's words: {point_scope!r}"
    )
    assert "resolved to an empty text" in point_scope, (
        f"the scope does not say the anchor resolved to nothing: {point_scope!r}"
    )
    assert "could not place" not in point_scope, (
        f"a case the reader placed was called unplaced: {point_scope!r}"
    )

    assert '""' not in unplaced_scope, (
        f"the empty string was quoted as the advisor's words: {unplaced_scope!r}"
    )
    assert "could not place" in unplaced_scope, (
        f"the scope does not say the comment was not placed: {unplaced_scope!r}"
    )
    assert "resolved to an empty text" not in unplaced_scope, (
        f"a case the reader could not place was called resolved: {unplaced_scope!r}"
    )

    assert point_scope != unplaced_scope, (
        "the two facts were given the same words, and they are not the same fact"
    )


def test_the_scope_names_every_case_it_claims_and_the_sources_agree(
    env: StoreEnv, tmp_path: Path
) -> None:
    """Every case under the rule's sources is named in the scope.

    **The scope and the sources are two halves of one statement**, and
    they have to agree: a scope that named a case the rule does not
    source would claim a case the rule never learned from, and a scope
    that dropped one would lose a case the rule does.

    **Both directions are checked.** Every case under every source is
    accounted for — by the text it was written against, or by being named
    as a case the reader could not place — and every text the scope
    quotes belongs to one of those cases.
    """
    context = _chain_keyed(
        env,
        tmp_path / "chain",
        comments=(a_comment("401"), a_comment("402", anchor="none")),
        keys=(KEY, KEY_UNPLACED),
    )

    distilled = _distil(context, issue_keys=(KEY, KEY_UNPLACED))

    assert distilled.sources == (KEY, KEY_UNPLACED), "the rule sources both cases"
    cases = chain_layer.read_comments(context, issue_keys=distilled.sources)
    assert len(cases) == 2, "the chain holds the two cases the rule named"

    for case in cases:
        if case.anchor_status == "resolved" and case.anchor_text:
            assert f'"{case.anchor_text}"' in distilled.scope, (
                f"the scope dropped the case {case.issue_key!r}: {distilled.scope!r}"
            )
        else:
            assert f"the comment under {case.issue_key!r}" in distilled.scope, (
                f"the scope dropped the case {case.issue_key!r}: {distilled.scope!r}"
            )

    assert set(_quoted_texts(distilled.scope)) == {
        case.anchor_text for case in cases if case.anchor_text
    }, f"the scope quotes a text no case holds: {distilled.scope!r}"


# --------------------------------------------------------------------------- #
# A comment rule written again: the next version, from comment cases.
# --------------------------------------------------------------------------- #

#: The statement of the **first** version of the rule — the thin one, the
#: kind a run that read one remark writes.
_FIRST_STATEMENT = STATEMENT

#: The statement of the **second** version — the one a reader could apply.
_SECOND_STATEMENT = (
    "When the claim rests on a comparison, the rule names the baseline in the"
    " same paragraph as the quantity it is compared against."
)


def _version(context: ApplicationContext, rule_id: str, **overrides: object) -> GuidanceRule:
    """Write a new version of *rule_id* from the advisor's comment."""
    kwargs: dict[str, object] = {
        "rule_id": rule_id,
        "issue_type": "method_and_hypothesis",
        "statement": _SECOND_STATEMENT,
        "rule_context": "A results section whose claim is comparative.",
        "issue_keys": (KEY,),
        "now": LATER,
    }
    kwargs.update(overrides)
    return distil_comment_version_of(context, **kwargs)  # type: ignore[arg-type]


def test_a_new_version_keeps_the_rule_it_replaces(
    cases: tuple[ApplicationContext, str],
) -> None:
    """**The rule keeps its place.** A new rule under a new id would be a
    second rule about the same thing, and the memory would hold two
    answers to one question.

    So the new version is written under the same ``rule_id``, as the next
    version of it — **and the reader gets the newest words and nothing
    else.**
    """
    context, _ = cases
    first = _distil(context)
    second = _version(context, first.rule_id)

    assert second.rule_id == first.rule_id, "the version must keep the rule's place"
    assert second.version == first.version + 1, "the version must be the next one"
    assert second.statement == _SECOND_STATEMENT
    assert second.state == "candidate", "a rewording is not a confirmation"


def test_the_old_version_keeps_the_state_it_had(
    cases: tuple[ApplicationContext, str],
) -> None:
    """**The memory does not rewrite its past.**

    The old version's row keeps its own state and its own words, so a
    reader who looks at the past finds the past — **and a rule that
    outlives its work is not a second place to look for the same code.**
    """
    context, _ = cases
    first = _distil(context)
    confirm_rule(context, rule_id=first.rule_id, confirmed_by="reviewer-2", now=MOMENT)

    _version(context, first.rule_id)

    rows = (
        context.store.session.execute(
            select(GuidanceRuleRow)
            .where(GuidanceRuleRow.rule_id == first.rule_id)
            .order_by(GuidanceRuleRow.version)
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2, "the version must be a new row, not a rewrite"
    assert rows[0].statement == _FIRST_STATEMENT, "the old version keeps its own words"
    assert rows[0].state == "confirmed", "the old version keeps the state it had"
    assert rows[1].statement == _SECOND_STATEMENT
    assert rows[1].state == "candidate"


def test_the_scope_and_the_example_are_the_cases_not_the_callers(
    env: StoreEnv, tmp_path: Path
) -> None:
    """**A caller cannot write a scope the cases do not support.**

    The scope is the anchored text the comment was written against and
    the example is the advisor's own words — **so a caller that had to
    hand-write them would have had to go around the product to do it**,
    and a rule whose scope the cases do not support is a rule bound to
    material that does not exist.

    **And the version's cases are the version's, not the first version's.**
    The first version is distilled from one comment and the new version
    from another, so a scope or an example copied from the old row is a
    scope or an example the new cases did not give.
    """
    context = _chain_keyed(
        env,
        tmp_path / "chain",
        comments=(
            a_comment("301"),
            a_comment(
                "302",
                text="Name the comparison group.",
                anchor_text="comparison group",
                paragraph=1,
            ),
        ),
        keys=(KEY, KEY_OTHER),
        paragraphs=(PARAGRAPH, SECOND_PARAGRAPH),
    )
    first = _distil(context, issue_keys=(KEY,))
    second = _version(context, first.rule_id, issue_keys=(KEY_OTHER,))

    assert f'"{SECOND_PARAGRAPH}"' in second.scope, (
        "the scope is the anchored text the new version's case was written against"
    )
    assert PARAGRAPH not in second.scope, "the scope is not the old version's"
    assert second.example.startswith("The advisor's comment ("), "the example is the comment"
    assert KEY_OTHER in second.example, "and it names the new version's key"
    assert KEY not in second.example, "and not the old version's"
    assert "Name the comparison group." in second.example, (
        "and it quotes the new version's advisor's words"
    )


def test_a_new_version_is_not_confirmed_by_its_own_proposer(
    cases: tuple[ApplicationContext, str],
) -> None:
    """**A rewording is not a confirmation**, and the second-reader door
    does not open for the hand that wrote the words.

    **And the proposer is the comment path's.** The version was distilled
    from comments, so the record says ``model_proposal`` — not the
    revision path's ``operator_proposal``, and not whatever the old row
    happened to carry.
    """
    context, _ = cases
    first = _distil(context)
    second = _version(context, first.rule_id)

    assert second.proposed_by == MODEL_PROPOSER, (
        "a comment distillation is a model's work, and the version says so"
    )
    with pytest.raises(ApplicationRefusedError) as raised:
        confirm_rule(context, rule_id=second.rule_id, confirmed_by=second.proposed_by, now=LATER)
    assert _refusal(raised.value) is GuidanceRefusal.CONFIRMER_IS_PROPOSER

    confirmed = confirm_rule(context, rule_id=second.rule_id, confirmed_by="reviewer-3", now=LATER)
    assert confirmed.state == "confirmed"
    assert confirmed.confirmed_by == "reviewer-3"


def test_only_the_newest_version_is_served(env: StoreEnv, tmp_path: Path) -> None:
    """**The reader gets the newest words and nothing else.**

    The memory keeps its past, and a reader sees each rule's newest
    version — **so a rule written twice is one rule to a query, never
    two.** And because the newest version is a candidate until a second
    reader confirms it, **a rule whose newest version is unconfirmed is
    not served at all**: a proposal reaching a card would be a proposal
    dressed as a record.
    """
    context = _judged_chain(env, tmp_path / "judged")
    first = _distil(context)
    confirm_rule(context, rule_id=first.rule_id, confirmed_by="reviewer-2", now=MOMENT)

    second = _version(context, first.rule_id)

    served = [hit for hit in search_rules(context) if hit.rule.rule_id == first.rule_id]
    assert not served, (
        "the newest version is a candidate, and a candidate is not served — even"
        " though an older version of the same rule was confirmed"
    )

    # **Once the second reader confirms the new version, it is the one
    # served** — and it is served once, not twice.
    confirm_rule(context, rule_id=second.rule_id, confirmed_by="reviewer-3", now=LATER)
    served = [hit for hit in search_rules(context) if hit.rule.rule_id == first.rule_id]
    assert len(served) == 1, "one rule is one answer, however many versions it has"
    assert served[0].rule.version == second.version
    assert served[0].rule.statement == _SECOND_STATEMENT


def test_a_version_of_a_rule_that_is_not_there_is_refused(
    cases: tuple[ApplicationContext, str],
) -> None:
    """**A rule that is not there cannot be given a version.**

    The new version is written under a rule's own id, so the rule is
    read first — and a rule nobody holds is refused before anything is
    written.
    """
    context, _ = cases
    with pytest.raises(ApplicationRefusedError) as raised:
        _version(context, "rule-does-not-exist")
    assert _refusal(raised.value) is GuidanceRefusal.RULE_NOT_FOUND

    written: int = context.store.session.execute(
        text("SELECT count(*) FROM guidance_rules WHERE rule_id = :r"),
        {"r": "rule-does-not-exist"},
    ).scalar_one()
    assert written == 0, "a refused version must write nothing"


def test_a_version_with_no_case_is_refused(
    cases: tuple[ApplicationContext, str],
) -> None:
    """**A version with no source behind it is not a version.**

    The new version's sources are the cases, so a version naming no
    comment — or a key the chain holds nothing under — is a rule bound to
    material that does not exist.
    """
    context, _ = cases
    first = _distil(context)

    with pytest.raises(ApplicationRefusedError) as raised:
        _version(context, first.rule_id, issue_keys=())
    assert _refusal(raised.value) is GuidanceRefusal.RULE_WITHOUT_SOURCE

    with pytest.raises(ApplicationRefusedError) as raised:
        _version(context, first.rule_id, issue_keys=("iss-nobody-holds",))
    assert _refusal(raised.value) is GuidanceRefusal.RULE_WITHOUT_SOURCE

    assert read_rule(context, rule_id=first.rule_id).version == first.version, (
        "a refused version must leave the rule where it was"
    )
