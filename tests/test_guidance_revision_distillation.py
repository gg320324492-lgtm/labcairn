"""The distillation's second case: a rule learned from a revision.

**What is under test.** The distillation's revision half: a rule
distilled from the chain's **tracked changes** rather than from its
comments, and the four properties that half has to hold.

=====================================================  =========================
A7  a distilled rule is a **candidate** until a person  the creator is
    confirms it                                        ``operator_proposal``,
                                                       and the proposer
                                                       cannot confirm their
                                                       own rule
A9  a rule whose scope the cases do not support is     the scope is the
    refused                                            cases', or there is
                                                       no rule
=====================================================  =========================

**And A9 has a second half here too.** A revision case's scope is the
**paragraph the change sits in**, read in the change's own view — an
insertion belongs to the accepted text and a deletion to the rejected
one, so a paragraph read in the wrong view is a different paragraph.
And a paragraph that could not be read is **named as unread**, never
quoted as the empty string: an empty string quoted as the reviewer's
surroundings would say the reviewer changed something in a paragraph
that does not exist.

**And the key is the product's.** A comment's issue key is a person's
judgement (ADR-0017 C10) and is given; **a revision has no such
judgement to give** — a tracked change is a fact about a file whose
address already names it. So the caller names the *revision* and the
product mints the key. **A key a caller could write would name material
the chain may not hold**, and a rule bound to that is not a rule.

**And this is the shape the third pilot has.** 23 versions, 208
revisions, **no comment at all** — so a distillation that reads only
comments has no case in that manuscript. The fixture below is that
shape: revisions, and not one comment.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from docx_fixtures import Revision
from feedback_chain_fixtures import ChainEnv, build_chain
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import ApplicationRefusedError
from labcairn.guidance.distil import (
    MODEL_PROPOSER,
    OPERATOR_PROPOSER,
    distil_candidate_from_revisions,
    distil_revision_version_of,
)
from labcairn.guidance.models import GuidanceRule
from labcairn.guidance.refusals import GuidanceRefusal
from labcairn.guidance.retrieval import search_rules
from labcairn.guidance.rules import confirm_rule, read_rule
from labcairn.papers.chain import REVISION_SOURCE_PREFIX, revision_source_key
from labcairn.papers.edits import ActorClaim, record_edits_from_revisions
from labcairn.papers.revisions import record_revision_events

pytestmark = pytest.mark.integration

env = _shared_env

MOMENT = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)
LATER = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)

#: The advisor's name, as the file records it. **A name in a file is a
#: string somebody typed**, so the roster names who it is.
_ADVISOR_NAME = "Prof. Lin"
#: The student's name, as the file records it.
_STUDENT_NAME = "Wang"

#: The paragraph the changes sit in.
_PARAGRAPH = "The method estimates the parameter roughly from a single observation."

#: **Two changes by two people**: the mentor's insertion and the
#: student's deletion. **A rule distilled from the mentor's change must
#: not carry the student's change as its own.**
_REVISIONS = (
    Revision(
        kind="ins",
        text="carefully",
        author=_ADVISOR_NAME,
        date="2026-03-02T09:30:00Z",
        element_id="101",
        paragraph=0,
        after_text="estimates",
    ),
    Revision(
        kind="del",
        text="roughly",
        author=_STUDENT_NAME,
        date="2026-03-03T10:15:00Z",
        element_id="102",
        paragraph=0,
        anchor_text="roughly",
    ),
)

_ROSTER = {
    _ADVISOR_NAME: ActorClaim(actor_kind="advisor", actor_id="advisor-1"),
    _STUDENT_NAME: ActorClaim(actor_kind="student", actor_id="student-1"),
}

STATEMENT = "The mentor asks for the method's care to be visible in the wording."
CONTEXT = "A methods section whose sentence hides how careful the estimate was."

#: **Two halves of one parenthetical clause**, written in two moments —
#: which is how Word records a change a writer made in one go.
#:
#: **The first half is a fragment**, and a rule illustrated by the
#: fragment would not show what the reviewer wrote.
#:
#: **The order matters, and it is the order that makes the witness
#: bite.** The revision event's id is derived from the element's path,
#: and the fixture writer places a revision by **the point it follows**
#: in the paragraph's text — so the fuller half is written at the point
#: after "concentrates" and the fragment at the same point after it, and
#: the fragment's derived id happens to sort **first**. **A reader that
#: picked the example by key order would pick the fragment**, and the
#: witness below would see it — which is the point of the fixture being
#: built this way rather than the other way round.
_HALF_PARAGRAPH = "The bubbles collapse and the energy concentrates."
_HALF_REVISIONS = (
    Revision(
        kind="ins",
        text=", the energy concentrates and attacks the algae)",
        author=_ADVISOR_NAME,
        date="2026-03-02T09:31:00Z",
        element_id="202",
        paragraph=0,
        after_text="concentrates",
    ),
    Revision(
        kind="ins",
        text="(after the collapse",
        author=_ADVISOR_NAME,
        date="2026-03-02T09:30:00Z",
        element_id="201",
        paragraph=0,
        after_text="concentrates",
    ),
)


def _refusal(error: ApplicationRefusedError) -> GuidanceRefusal:
    return GuidanceRefusal(error.reason.value.removeprefix("guidance_"))


@pytest.fixture()
def marked_up(env: StoreEnv, tmp_path: Path) -> ChainEnv:
    """A chain whose manuscript carries **two changes and no comment at all**.

    **This is the third pilot's shape.** A marked-up manuscript may hold
    hundreds of tracked changes and not one comment, and **a distillation
    that reads only comments has no case at all in such a manuscript.**
    So the fixture records the changes and records **no feedback**.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return build_chain(
        env.store(),
        workspace,
        comments=(),
        paragraphs=(_PARAGRAPH,),
        revisions=_REVISIONS,
    )


@pytest.fixture()
def the_changes(marked_up: ChainEnv) -> dict[str, str]:
    """The changes the chain holds, by the name the file gave them.
    **Keyed by the author, so a test may ask for the mentor's change
    without reading the file.** The ids are derived from the version and
    the element's path, so they are not written down here — **the ids are
    read from the chain, not assumed.**
    """
    recorded = record_revision_events(
        marked_up.context,
        project_id=marked_up.project_id,
        version_id=marked_up.second_version_id,
        now=MOMENT,
    )
    by_author = {
        record.author: record.revision_event_id for record in recorded if record.author is not None
    }
    record_edits_from_revisions(
        marked_up.context,
        project_id=marked_up.project_id,
        version_id=marked_up.second_version_id,
        version_edge_id=marked_up.edge_id,
        actors=_ROSTER,
        now=MOMENT,
    )
    return by_author


@pytest.fixture()
def halves(env: StoreEnv, tmp_path: Path) -> tuple[ApplicationContext, tuple[str, ...]]:
    """A chain whose mentor wrote **one clause in two moments**.

    **Word records a change the writer made in one go as two events** —
    the half typed first and the half typed after — and the first half is
    a fragment on its own. **A rule illustrated by the fragment would not
    show what the reviewer wrote**, so the example has to be the half that
    shows most.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    chain = build_chain(
        env.store(),
        workspace,
        comments=(),
        paragraphs=(_HALF_PARAGRAPH,),
        revisions=_HALF_REVISIONS,
    )
    recorded = record_revision_events(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.second_version_id,
        now=MOMENT,
    )
    record_edits_from_revisions(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.second_version_id,
        version_edge_id=chain.edge_id,
        actors=_ROSTER,
        now=MOMENT,
    )
    return chain.context, tuple(record.revision_event_id for record in recorded)


#: A document part with **a deletion nested inside an insertion**, in a
#: paragraph that is **nothing but that insertion**.
#:
#: **This is what the third pilot's mentor wrote**, and the fixture
#: writer cannot say it: Word writes "inserted, then deleted" as a
#: ``w:del`` inside a ``w:ins``, and a paragraph that holds only an
#: insertion has **no baseline at all** — there is no manuscript before
#: the change, so the rejected view of it is empty.
#:
#: **And the deletion's own view is the rejected one** — the text it
#: removed — so the case's context is the rejected paragraph, and that
#: paragraph is empty. **The scope has to say so.**
_NESTED_DELETION_DOCUMENT = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">\n'
    "<w:body>\n"
    "<w:p>"
    '<w:ins w:id="401" w:author="Prof. Lin" w:date="2026-03-02T09:30:00Z">'
    '<w:r><w:t xml:space="preserve">The energy barrier </w:t></w:r>'
    '<w:del w:id="402" w:author="Prof. Lin" w:date="2026-03-02T09:31:00Z">'
    '<w:r><w:delText xml:space="preserve">of the surface reaction</w:delText></w:r>'
    "</w:del>"
    '<w:r><w:t xml:space="preserve"> concentrates.</w:t></w:r>'
    "</w:ins>"
    "</w:p>\n"
    "</w:body>\n"
    "</w:document>\n"
)


@pytest.fixture()
def an_entirely_inserted_paragraph(env: StoreEnv, tmp_path: Path) -> tuple[ApplicationContext, str]:
    """A chain whose paragraph **is nothing but an insertion**.

    **This is the third pilot's shape, exactly.** The mentor's deletion
    there sits **inside** an insertion — Word writes "inserted, then
    deleted" as a ``w:del`` nested in a ``w:ins`` — and **a paragraph
    that is entirely inserted has no baseline at all**. The rejected view
    of such a paragraph is empty, because there is no manuscript before
    the insertion.

    **So the deletion has no context to be read in, and the scope has to
    say so.** The empty string is not the reviewer's surroundings: it is
    the absence of a manuscript that existed before the change.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    chain = build_chain(
        env.store(),
        workspace,
        comments=(),
        paragraphs=("The energy barrier concentrates.",),
        document_xml=_NESTED_DELETION_DOCUMENT,
    )
    recorded = record_revision_events(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.second_version_id,
        now=MOMENT,
    )
    record_edits_from_revisions(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.second_version_id,
        version_edge_id=chain.edge_id,
        actors=_ROSTER,
        now=MOMENT,
    )
    deletions = [record for record in recorded if record.kind == "del"]
    assert deletions, "the document must record the nested deletion"
    return chain.context, deletions[0].revision_event_id


def test_the_example_is_the_half_that_shows_the_change_best(
    halves: tuple[ApplicationContext, tuple[str, str]],
) -> None:
    """The example is the case that shows most, not the first by key.

    **Word records a change the writer made in one go as two events**,
    and the first half is a fragment on its own. **A rule illustrated by
    the fragment would not show what the reviewer wrote** — and the
    example is the evidence the rule is checked against.
    """
    context, event_ids = halves

    rule = _distil(context, revision_event_ids=event_ids)

    assert "attacks the algae" in rule.example, (
        "the example must be the change that shows what the reviewer wrote, "
        "and the fragment on its own does not"
    )
    assert "(after the collapse" not in rule.example, (
        "the first half by key order is the fragment, and it must not be the example"
    )


def test_the_example_names_the_key_of_the_case_it_shows(
    halves: tuple[ApplicationContext, tuple[str, str]],
) -> None:
    """The key beside the example is **the example's own key**.

    **A reader must be able to open the case the example came from** —
    and a key beside a *different* case's words would send them to the
    wrong place.
    """
    context, event_ids = halves

    rule = _distil(context, revision_event_ids=event_ids)

    named = [source for source in rule.sources if source in rule.example]
    assert named, "the example must name the key of the case it shows"
    assert len(named) == 1, "the example names one case, and one key"


def test_a_paragraph_that_cannot_be_read_is_named_not_quoted(
    an_entirely_inserted_paragraph: tuple[ApplicationContext, str],
) -> None:
    """A case with no context says so, and does not quote an empty string.

    **A paragraph that is entirely an insertion has no baseline at all** —
    there is no manuscript before the change, so the rejected view of it
    is empty. **Quoting that empty string as the reviewer's surroundings
    would say the reviewer changed something in a paragraph that does not
    exist**, which is not what happened.

    **So the scope names the case as one whose paragraph could not be
    read**, and the change's own words are still there in the example.
    """
    context, event_id = an_entirely_inserted_paragraph

    rule = _distil(context, revision_event_ids=(event_id,))

    assert "could not be read" in rule.scope, "the scope must say the paragraph could not be read"
    assert '""' not in rule.scope, (
        "the empty string must never be quoted as the reviewer's surroundings"
    )
    assert "of the surface reaction" in rule.example, (
        "the change's own words are still the example, whatever the context"
    )


def _distil(context: ApplicationContext, **overrides: Any) -> GuidanceRule:
    kwargs: dict[str, Any] = {
        "issue_type": "method_and_hypothesis",
        "statement": STATEMENT,
        "rule_context": CONTEXT,
        "revision_event_ids": (),
        "now": MOMENT,
    }
    kwargs.update(overrides)
    return distil_candidate_from_revisions(context, **kwargs)


def test_a_manuscript_with_no_comment_can_still_yield_a_candidate(
    marked_up: ChainEnv,
    the_changes: dict[str, str],
) -> None:
    """The point of the second case: **a comment is not the only case.**

    **A marked-up manuscript with no comment in it is a shape the chain
    can report and does not explain away** — 23 versions, 208 revisions
    and not one comment. A distillation that reads only comments has
    **no case at all** in such a manuscript, and a rule distilled from
    nothing is not a rule.

    So the mentor's own change is a case, and a rule is distilled from
    it and lands as a candidate.
    """
    assert (
        marked_up.context.store.session.execute(
            __import__("sqlalchemy").text("SELECT COUNT(*) FROM feedback_events")
        ).scalar_one()
        == 0
    ), "the fixture must carry no comment at all"

    rule = _distil(marked_up.context, revision_event_ids=(the_changes[_ADVISOR_NAME],))

    assert rule.state == "candidate"
    assert rule.proposed_by == OPERATOR_PROPOSER
    assert rule.statement == STATEMENT
    assert rule.sources, "a rule with no source is not a rule"


def test_a_revision_case_is_bound_to_the_chain_address_and_the_key_is_the_products(
    marked_up: ChainEnv,
    the_changes: dict[str, str],
) -> None:
    """The rule is bound to the chain's own address, and the key is minted.

    **The key is derived from the revision event's own id** — the id the
    chain already has — so it is an address a reader can follow. **And the
    caller cannot write one**: the caller named the revision, and the
    product minted the key.
    """
    event_id = the_changes[_ADVISOR_NAME]
    rule = _distil(marked_up.context, revision_event_ids=(event_id,))

    expected = revision_source_key(event_id)
    assert rule.sources == (expected,)
    assert expected == event_id, (
        "the key is the revision's own address, so a reader who follows it finds the change itself"
    )

    # **And the rule's example names the same key**, so the sentence
    # traces back to the case it was derived from.
    assert expected in rule.example


def test_the_scope_is_the_paragraph_the_change_sits_in(
    marked_up: ChainEnv,
    the_changes: dict[str, str],
) -> None:
    """The scope is the applicability condition, and it is the paragraph.

    **A revision's context is the paragraph around it** — a change is a
    fact about a file, and the paragraph is where the reviewer put it.
    **And the paragraph is read in the change's own view**: an insertion
    belongs to the accepted text, so the accepted text is what the scope
    quotes.
    """
    rule = _distil(marked_up.context, revision_event_ids=(the_changes[_ADVISOR_NAME],))

    assert "estimates" in rule.scope, "the scope must quote the paragraph the change sits in"
    assert "carefully" in rule.scope, (
        "the accepted view is the manuscript with the insertion kept, so the scope "
        "must show the mentor's own word in it"
    )


def test_a_deletion_is_read_in_the_rejected_view(
    marked_up: ChainEnv,
    the_changes: dict[str, str],
) -> None:
    """A deletion's paragraph is the manuscript *as it was*.

    **The view is part of the address** (ADR-0014 D4a), so a paragraph
    read in the wrong view is a different paragraph. A deletion belongs
    to the **rejected** text — the words it was removed from — and a
    scope that quoted the accepted text instead would show the student
    quoting a sentence the change is in the middle of removing.
    """
    rule = _distil(marked_up.context, revision_event_ids=(the_changes[_STUDENT_NAME],))

    assert "roughly" in rule.scope, (
        "the rejected view is the manuscript before the deletion, so the deleted "
        "word is still in it"
    )
    assert "carefully" not in rule.scope, (
        "the rejected view is the manuscript before the deletion, so the mentor's "
        "later insertion is not in it"
    )


def test_a_rule_with_no_case_is_refused(marked_up: ChainEnv) -> None:
    """A rule with no case behind it has nothing to scope it."""
    with pytest.raises(ApplicationRefusedError) as raised:
        _distil(marked_up.context, revision_event_ids=())
    assert _refusal(raised.value) is GuidanceRefusal.RULE_WITHOUT_SOURCE


def test_a_revision_the_chain_holds_no_case_for_is_refused(
    marked_up: ChainEnv,
    the_changes: dict[str, str],
) -> None:
    """A named revision the chain does not hold is refused, not skipped.

    **A rule that cites a case the chain cannot show is a rule whose
    scope the cases do not support** — the same refusal the comment case
    raises, and for the same reason.
    """
    with pytest.raises(ApplicationRefusedError) as raised:
        _distil(marked_up.context, revision_event_ids=("rv-nobody-holds",))
    assert _refusal(raised.value) is GuidanceRefusal.RULE_WITHOUT_SOURCE


def test_the_caller_cannot_write_the_key(
    marked_up: ChainEnv,
    the_changes: dict[str, str],
) -> None:
    """The key is the product's, and a caller has no way to supply one.

    **The entry point takes revisions, not keys** — so a caller cannot
    name a case the chain does not hold, and cannot bind a rule to
    material of its own choosing. **And the key the rule ends up with is
    the one the product minted**, whatever the caller passed.
    """
    with pytest.raises(TypeError):
        _distil(marked_up.context, issue_keys=("iss-forged",))

    event_id = the_changes[_ADVISOR_NAME]
    rule = _distil(marked_up.context, revision_event_ids=(event_id,))
    for source in rule.sources:
        assert source == revision_source_key(event_id)
        assert source.startswith(REVISION_SOURCE_PREFIX), (
            "a revision case is filed under the product's key"
        )
        assert source == event_id, (
            "the key is the revision's own address, so a reader who follows it "
            "finds the change itself"
        )


def test_the_candidate_is_not_confirmed_by_its_own_proposer(
    marked_up: ChainEnv,
    the_changes: dict[str, str],
) -> None:
    """A7: the proposer cannot be the one who confirms it.

    **The second-reader rule holds for this proposer too.** An operator's
    proposal is a proposal like any other, and the operator cannot
    confirm their own work by any name.
    """
    rule = _distil(marked_up.context, revision_event_ids=(the_changes[_ADVISOR_NAME],))

    with pytest.raises(ApplicationRefusedError) as raised:
        confirm_rule(
            marked_up.context,
            rule_id=rule.rule_id,
            confirmed_by=rule.proposed_by,
            now=LATER,
        )
    assert _refusal(raised.value) is GuidanceRefusal.CONFIRMER_IS_PROPOSER

    assert read_rule(marked_up.context, rule_id=rule.rule_id).state == "candidate"


def test_a_second_reader_confirms_the_revision_distillation(
    marked_up: ChainEnv,
    the_changes: dict[str, str],
) -> None:
    """The confirmation door is the same door, and it opens for a person.

    **A revision case does not weaken the door.** The rule was proposed
    by an operator; a person who did not propose it confirms it, and the
    rule becomes confirmed — and the confirmer is written down.
    """
    rule = _distil(marked_up.context, revision_event_ids=(the_changes[_ADVISOR_NAME],))

    confirmed = confirm_rule(
        marked_up.context,
        rule_id=rule.rule_id,
        confirmed_by="reviewer-2",
        now=LATER,
    )
    assert confirmed.state == "confirmed"
    assert confirmed.confirmed_by == "reviewer-2"


def test_the_two_distillations_name_two_different_proposers(
    marked_up: ChainEnv,
    the_changes: dict[str, str],
) -> None:
    """A corpus distillation is a model's work, and a revision one is not.

    **The record must not claim a model did something a person did.** A
    distillation run over a corpus of comments is a model's work and
    says ``model_proposal``; an operator reading a mentor's tracked
    changes is a person's work and says ``operator_proposal``.
    """
    assert MODEL_PROPOSER != OPERATOR_PROPOSER

    rule = _distil(marked_up.context, revision_event_ids=(the_changes[_ADVISOR_NAME],))
    assert rule.proposed_by == OPERATOR_PROPOSER


def test_a_confirmed_rule_on_a_revision_is_served_with_its_source(
    marked_up: ChainEnv,
    the_changes: dict[str, str],
) -> None:
    """The revision source is **live**, and the retrieval says so.

    **A rule bound to a revision is not a dead rule.** The retrieval
    resolves each source against the chain, and a revision's source is
    the change itself — so it lives as long as the chain holds the
    change and the reader may read the manuscript.
    """
    rule = _distil(marked_up.context, revision_event_ids=(the_changes[_ADVISOR_NAME],))
    confirm_rule(
        marked_up.context,
        rule_id=rule.rule_id,
        confirmed_by="reviewer-2",
        now=LATER,
    )

    hits = search_rules(marked_up.context, query=STATEMENT)
    served = [hit for hit in hits if hit.rule.rule_id == rule.rule_id]
    assert served, "a confirmed rule on a revision must be served"
    assert [source.issue_key for source in served[0].sources] == list(rule.sources)
    assert all(source.found for source in served[0].sources)


# --------------------------------------------------------------------------- #
# The third way a rule is written: a new version of it, from revision cases.
# --------------------------------------------------------------------------- #

#: The statement of the **first** version of the rule — the thin one, the
#: kind a run that split an edit into its fragments writes.
_FIRST_STATEMENT = "The rule states what the mentor's change says."

#: The statement of the **second** version — the one a reader could apply.
_SECOND_STATEMENT = (
    "When the mechanism a sentence names is quantified, the rule states the "
    "causal chain the quantity belongs to."
)


def _version(context: ApplicationContext, rule_id: str, **overrides: Any) -> GuidanceRule:
    """Write a new version of *rule_id* from the mentor's change."""
    kwargs: dict[str, Any] = {
        "rule_id": rule_id,
        "issue_type": "method_and_hypothesis",
        "statement": _SECOND_STATEMENT,
        "rule_context": CONTEXT,
        "revision_event_ids": (),
        "now": LATER,
    }
    kwargs.update(overrides)
    return distil_revision_version_of(context, **kwargs)


def test_a_new_version_keeps_the_rule_it_replaces(
    marked_up: ChainEnv,
    the_changes: dict[str, str],
) -> None:
    """**The rule keeps its place.** A new rule under a new id would be a
    second rule about the same thing, and the memory would hold two
    answers to one question.

    So the new version is written under the same ``rule_id``, as the next
    version of it — **and the reader gets the newest words and nothing
    else.**
    """
    first = _distil(marked_up.context, revision_event_ids=(the_changes[_ADVISOR_NAME],))

    second = _version(
        marked_up.context,
        first.rule_id,
        revision_event_ids=(the_changes[_ADVISOR_NAME],),
    )

    assert second.rule_id == first.rule_id, "the version must keep the rule's place"
    assert second.version == first.version + 1, "the version must be the next one"
    assert second.statement == _SECOND_STATEMENT
    assert second.state == "candidate", "a rewording is not a confirmation"


def test_the_old_version_keeps_the_state_it_had(
    marked_up: ChainEnv,
    the_changes: dict[str, str],
) -> None:
    """**The memory does not rewrite its past.**

    The old version's row keeps its own state and its own words, so a
    reader who looks at the past finds the past — **and a rule that
    outlives its work is not a second place to look for the same code.**
    """
    first = _distil(marked_up.context, revision_event_ids=(the_changes[_ADVISOR_NAME],))
    confirm_rule(
        marked_up.context,
        rule_id=first.rule_id,
        confirmed_by="reviewer-2",
        now=MOMENT,
    )

    _version(
        marked_up.context,
        first.rule_id,
        revision_event_ids=(the_changes[_ADVISOR_NAME],),
    )

    rows = marked_up.context.store.session.execute(
        __import__("sqlalchemy").text(
            "SELECT version, state, statement FROM guidance_rules "
            "WHERE rule_id = :r ORDER BY version"
        ),
        {"r": first.rule_id},
    ).all()
    assert len(rows) == 2, "the version must be a new row, not a rewrite"
    assert rows[0].statement == STATEMENT, "the old version keeps its own words"
    assert rows[0].state == "confirmed", "the old version keeps the state it had"
    assert rows[1].statement == _SECOND_STATEMENT
    assert rows[1].state == "candidate"


def test_the_scope_and_the_example_are_the_cases_not_the_callers(
    marked_up: ChainEnv,
    the_changes: dict[str, str],
) -> None:
    """**A caller cannot write a scope the cases do not support.**

    The scope is the paragraph the change sits in and the example is the
    reviewer's own change — **so a caller that had to hand-write them
    would have had to go around the product to do it**, and a rule whose
    scope the cases do not support is a rule bound to material that does
    not exist.
    """
    first = _distil(marked_up.context, revision_event_ids=(the_changes[_ADVISOR_NAME],))

    second = _version(
        marked_up.context,
        first.rule_id,
        revision_event_ids=(the_changes[_ADVISOR_NAME],),
    )

    assert "estimatescarefully the parameter" in second.scope, (
        "the scope is the paragraph the change sits in, read in the change's own view"
    )
    assert second.example.startswith("The reviewer's change ("), "the example is the change"
    assert the_changes[_ADVISOR_NAME] in second.example, "and it names the case's own key"


def test_a_new_version_is_not_confirmed_by_its_own_proposer(
    marked_up: ChainEnv,
    the_changes: dict[str, str],
) -> None:
    """**A rewording is not a confirmation**, and the second-reader door
    does not open for the hand that wrote the words.
    """
    first = _distil(marked_up.context, revision_event_ids=(the_changes[_ADVISOR_NAME],))
    second = _version(
        marked_up.context,
        first.rule_id,
        revision_event_ids=(the_changes[_ADVISOR_NAME],),
    )

    with pytest.raises(ApplicationRefusedError) as raised:
        confirm_rule(
            marked_up.context,
            rule_id=second.rule_id,
            confirmed_by=second.proposed_by,
            now=LATER,
        )
    assert _refusal(raised.value) is GuidanceRefusal.CONFIRMER_IS_PROPOSER

    assert read_rule(marked_up.context, rule_id=second.rule_id).state == "candidate"


def test_only_the_newest_version_is_served(
    marked_up: ChainEnv,
    the_changes: dict[str, str],
) -> None:
    """**The reader gets the newest words and nothing else.**

    The memory keeps its past, and a reader sees each rule's newest
    version — **so a rule written twice is one rule to a query, never
    two.** And because the newest version is a candidate until a second
    reader confirms it, **a rule whose newest version is unconfirmed is
    not served at all**: a proposal reaching a card would be a proposal
    dressed as a record.

    **Both halves are the point, and they are different halves.** A
    memory that served the old words while the new ones waited would be
    serving words its author has already rewritten; a memory that served
    both would be answering one question twice.
    """
    first = _distil(marked_up.context, revision_event_ids=(the_changes[_ADVISOR_NAME],))
    confirm_rule(
        marked_up.context,
        rule_id=first.rule_id,
        confirmed_by="reviewer-2",
        now=MOMENT,
    )
    second = _version(
        marked_up.context,
        first.rule_id,
        revision_event_ids=(the_changes[_ADVISOR_NAME],),
    )

    served = [hit for hit in search_rules(marked_up.context) if hit.rule.rule_id == first.rule_id]
    assert not served, (
        "the newest version is a candidate, and a candidate is not served — even"
        " though an older version of the same rule was confirmed"
    )

    # **Once the second reader confirms the new version, it is the one
    # served** — and it is served once, not twice.
    confirm_rule(
        marked_up.context,
        rule_id=second.rule_id,
        confirmed_by="reviewer-3",
        now=LATER,
    )
    served = [hit for hit in search_rules(marked_up.context) if hit.rule.rule_id == first.rule_id]
    assert len(served) == 1, "a rule written twice must not answer a query twice"
    assert served[0].rule.version == second.version, "and it must be the newest words"
    assert served[0].rule.statement == _SECOND_STATEMENT, "and the newest words are the new ones"


def test_a_version_of_a_rule_that_is_not_there_is_refused(
    marked_up: ChainEnv,
    the_changes: dict[str, str],
) -> None:
    """**A rule that is not there cannot be given a version.**

    The new version is written under a rule's own id, so the rule is
    read first — and a rule nobody holds is refused before anything is
    written.
    """
    with pytest.raises(ApplicationRefusedError) as raised:
        _version(
            marked_up.context,
            "rule-does-not-exist",
            revision_event_ids=(the_changes[_ADVISOR_NAME],),
        )
    assert raised.value is not None


def test_a_version_with_no_case_is_refused(
    marked_up: ChainEnv,
    the_changes: dict[str, str],
) -> None:
    """**A version with no source behind it is not a version.**

    The new version's sources are the cases, so a version naming no
    revision is a rule bound to material that does not exist.
    """
    first = _distil(marked_up.context, revision_event_ids=(the_changes[_ADVISOR_NAME],))

    with pytest.raises(ApplicationRefusedError) as raised:
        _version(marked_up.context, first.rule_id, revision_event_ids=())
    assert _refusal(raised.value) is GuidanceRefusal.RULE_WITHOUT_SOURCE

    assert read_rule(marked_up.context, rule_id=first.rule_id).version == first.version, (
        "a refused version must leave the rule where it was"
    )
