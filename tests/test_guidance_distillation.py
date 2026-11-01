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
=====================================================  =========================

**And A9 has a second half.** The scope the cases give is the
*applicability condition*, and it has to be **true**: a case whose
comment the reader could not place in the body carries no anchored text
at all, and a scope that quoted that empty string as the advisor's words
would say the advisor wrote about nothing — which is not what happened.
So the scope names every case it holds: the text the comment was written
against, or the fact that the reader could not place it, with the reason
the chain gives.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from docx_fixtures import Comment
from feedback_chain_fixtures import PARAGRAPH, a_comment, build_chain
from test_store_support import StoreEnv
from test_store_support import env as _shared_env

from labcairn.application import chain as chain_layer
from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import ApplicationRefusedError
from labcairn.db.models import GuidanceRuleRow
from labcairn.guidance.distil import MODEL_PROPOSER, distil_candidate
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
