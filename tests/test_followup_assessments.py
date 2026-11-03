"""The later assessment, and the recurrence it is about.

**What is under test.** LC-P2-09 T04: ``followup_assessments``, the
``issue_key`` on the feedback row, and the three acceptance clauses that
carry them.

======  ================================================================
A11     no issue key is inferred from the text, and a comment with no key
        is uncategorised
A12     two comments with the same key in different versions are visible
        as one recurring issue
A13     an assessment carries its own evidence, and one that derives the
        advisor's correctness from the change's acceptance is refused
A14     an assessment names an issue the chain holds **in that project**,
        on either route — a comment's key or a revision's — and the key's
        spelling decides nothing
======  ================================================================

**Why the schema's refusals are witnessed by writing rows.** The
project's lesson from revision 0007: *"the parity test passed through it,
because the migration and the ORM were mangled identically — a test
comparing two texts cannot catch both being wrong."* So each rule is
witnessed by **writing a row the schema must refuse** and watching the
database refuse it, with a raw ``INSERT`` that bypasses the ORM.

**And the design's hard line lives here.** *"The advisor's advice must not
be recorded as correct because the student's change was accepted."*
Acceptance is a fact about the process; the correctness of the advice is a
claim about the science, and the second needs its own evidence.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from docx_fixtures import Revision
from feedback_chain_fixtures import MOMENT, ChainEnv, a_comment, build_chain
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.db.models import PaperProjectRow, PaperVersionRow, RevisionEventRow
from labcairn.papers.assessments import (
    FollowupAssessment,
    list_assessments,
    list_recurring_issues,
    record_assessment,
)
from labcairn.papers.chain import revision_source_key
from labcairn.papers.feedback import record_feedback, set_issue_key
from labcairn.papers.revisions import record_revision_events

pytestmark = pytest.mark.integration

env = _shared_env


@pytest.fixture()
def chain(env: StoreEnv, tmp_path: Path) -> ChainEnv:
    """A workspace with one manuscript, one comment and one project."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return build_chain(env.store(), workspace, comments=(a_comment("201"),))


def _raw_insert(session: Session, **overrides: object) -> None:
    """Write an assessment row directly, so the schema is what is under
    test.

    **The evidence is written as JSON text**, because a raw ``INSERT``
    carries no type information and a Python list is not a value SQLite
    can bind.
    """
    values: dict[str, object] = {
        "assessment_id": "as-raw",
        "project_id": "proj-1",
        "feedback_id": None,
        "issue_key": "parameter-definition",
        "assessment": "The advice was right.",
        "outcome": "established",
        "basis": "advisor_evidence",
        "assessor_kind": "human",
        "grade": "observed",
        "evidence_refs": '["evidence:1"]',
        "created_at": "2026-04-01T09:00:00+00:00",
    }
    values.update(overrides)
    columns = ", ".join(values)
    placeholders = ", ".join(f":{key}" for key in values)
    session.execute(
        text(f"INSERT INTO followup_assessments ({columns}) VALUES ({placeholders})"),
        values,
    )
    session.commit()


# --------------------------------------------------------------------------- #
# A11 — no key is inferred
# --------------------------------------------------------------------------- #


def test_no_issue_key_is_inferred_from_the_text(env: StoreEnv, tmp_path: Path) -> None:
    """No issue key is inferred from the text, and a comment with no key
    is uncategorised.

    **The same wording is not the same issue**, and the same issue is not
    the same wording. So the operation never derives a key: a key is a
    person's judgement, and until somebody makes it the comment is
    uncategorised.

    **Two comments with the same words and no key stay two uncategorised
    comments** — and a key given to one of them is given, not derived.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    chain = build_chain(
        env.store(),
        workspace,
        comments=(a_comment("201"), a_comment("202", text="Define the parameter.")),
    )

    recorded = record_feedback(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.version_id,
        now=MOMENT,
    )

    assert len(recorded) == 2
    for event in recorded:
        assert event.issue_key is None, (
            "a comment nobody keyed is uncategorised, not keyed by similarity"
        )

    # And a key is given, not derived.
    keyed = set_issue_key(
        chain.context,
        feedback_id=recorded[0].feedback_id,
        issue_key="parameter-definition",
        now=MOMENT,
    )
    assert keyed.issue_key == "parameter-definition"
    assert recorded[1].issue_key is None


def test_a_key_is_never_inferred_by_the_operation(chain: ChainEnv) -> None:
    """The operation that records a comment has no path that derives a key.

    **A key is given by a person, and only a person can give one.** The
    operation that records a comment takes no key at all, so there is
    nothing for it to derive one from — and the operation that *does* take
    a key is the one a person calls.
    """
    from labcairn.papers import feedback as feedback_module

    recorded = record_feedback(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.version_id,
        now=MOMENT,
    )
    assert all(event.issue_key is None for event in recorded)
    assert hasattr(feedback_module, "set_issue_key"), (
        "the operation that gives a comment a key is a separate one, and a person calls it"
    )


# --------------------------------------------------------------------------- #
# A12 — a recurrence is visible
# --------------------------------------------------------------------------- #


def test_the_same_issue_recurring_is_visible_as_one_issue(env: StoreEnv, tmp_path: Path) -> None:
    """Two comments with the same key in different versions are **one
    recurring issue**.

    **A recurrence is a query, not a table.** The relation is in the rows
    — two comments carrying the same person-given key in two versions —
    and this is that relation read back. **No table of recurrences
    exists**, because a table whose name means two things is a table
    nobody can read.

    **And a round is a document.** A round is the set of comments written
    against one manuscript version, so a recurrence is a fact about two
    versions.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    chain = build_chain(
        env.store(),
        workspace,
        comments=(a_comment("201"),),
        second_comments=(a_comment("202"),),
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

    # Before anybody names the issue, there is no recurrence to see.
    assert list_recurring_issues(chain.context, project_id=chain.project_id) == ()

    set_issue_key(
        chain.context,
        feedback_id=first.feedback_id,
        issue_key="parameter-definition",
        now=MOMENT,
    )
    set_issue_key(
        chain.context,
        feedback_id=second.feedback_id,
        issue_key="parameter-definition",
        now=MOMENT,
    )

    recurring = list_recurring_issues(chain.context, project_id=chain.project_id)

    assert len(recurring) == 1, "the two rounds are one recurring issue"
    assert recurring[0].issue_key == "parameter-definition"
    assert recurring[0].version_ids == (chain.version_id, chain.second_version_id)
    assert set(recurring[0].feedback_ids) == {first.feedback_id, second.feedback_id}


def test_a_key_in_one_version_only_is_not_a_recurrence(env: StoreEnv, tmp_path: Path) -> None:
    """Two comments with the same key in **one** version are not a
    recurrence.

    **A recurrence is a fact about two versions.** A round is a document,
    and a comment and another comment in the same document are the same
    round.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    chain = build_chain(
        env.store(),
        workspace,
        comments=(a_comment("201"), a_comment("202")),
    )

    recorded = record_feedback(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.version_id,
        now=MOMENT,
    )
    for event in recorded:
        set_issue_key(
            chain.context,
            feedback_id=event.feedback_id,
            issue_key="parameter-definition",
            now=MOMENT,
        )

    assert list_recurring_issues(chain.context, project_id=chain.project_id) == ()


# --------------------------------------------------------------------------- #
# A13 — an assessment carries its own evidence
# --------------------------------------------------------------------------- #


def test_an_assessment_cannot_derive_correctness_from_acceptance(chain: ChainEnv) -> None:
    """An assessment carries its own evidence, and one that rests on the
    acceptance of a change is **refused**.

    **The acceptance of a change is a fact about the process; the
    correctness of the advice is a claim about the science.** The second
    needs its own evidence, so the vocabulary of what an assessment may
    rest on has **no member meaning "the change was accepted"** — and a
    row that names one is refused by the schema rather than by a
    convention nobody keeps.

    **And an assessment can say "not established."** A system that can
    only say "correct" cannot say "we do not know".
    """
    session = chain.context.store.session
    feedback = record_feedback(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.version_id,
        now=MOMENT,
    )[0]

    # The operation refuses it, and says why.
    with pytest.raises(ApplicationRefusedError) as caught:
        record_assessment(
            chain.context,
            assessment_id="as-accepted",
            project_id=chain.project_id,
            feedback_id=feedback.feedback_id,
            assessment="The advisor was right.",
            outcome="established",
            basis="change_accepted",
            assessor_kind="human",
            evidence_refs=("edge:edge-1 accepted",),
            now=MOMENT,
        )
    assert caught.value.reason is ApplicationRefusal.CHAIN_ASSESSMENT_BASIS_REFUSED

    # And the schema refuses it.
    with pytest.raises(IntegrityError):
        _raw_insert(session, assessment_id="as-accepted", basis="change_accepted")
    session.rollback()

    # And an assessment with no evidence of its own is refused.
    with pytest.raises(IntegrityError):
        _raw_insert(session, assessment_id="as-no-evidence", evidence_refs="[]")
    session.rollback()

    with pytest.raises(ApplicationRefusedError) as caught:
        record_assessment(
            chain.context,
            assessment_id="as-no-evidence",
            project_id=chain.project_id,
            feedback_id=feedback.feedback_id,
            assessment="The advisor was right.",
            outcome="established",
            basis="advisor_evidence",
            assessor_kind="human",
            evidence_refs=(),
            now=MOMENT,
        )
    assert caught.value.reason is ApplicationRefusal.CHAIN_ASSESSMENT_NEEDS_EVIDENCE

    # And the assessment that *is* allowed says what it rests on.
    recorded = record_assessment(
        chain.context,
        assessment_id="as-not-established",
        project_id=chain.project_id,
        feedback_id=feedback.feedback_id,
        assessment="The advice cannot be checked against anything yet.",
        outcome="not_established",
        basis="independent_check",
        assessor_kind="human",
        evidence_refs=("check:1",),
        now=MOMENT,
    )
    assert recorded.outcome == "not_established"
    assert recorded.basis == "independent_check"
    assert recorded.evidence_refs == ("check:1",)

    listed = list_assessments(chain.context, project_id=chain.project_id)
    assert [item.assessment_id for item in listed] == ["as-not-established"]


def test_an_assessment_must_name_something(chain: ChainEnv) -> None:
    """An assessment about nothing is not an assessment.

    **So it names a comment or an issue**, and a row that names neither is
    refused.
    """
    session = chain.context.store.session

    with pytest.raises(IntegrityError):
        _raw_insert(session, assessment_id="as-nothing", issue_key=None)
    session.rollback()

    with pytest.raises(ApplicationRefusedError) as caught:
        record_assessment(
            chain.context,
            assessment_id="as-nothing",
            project_id=chain.project_id,
            assessment="Something.",
            outcome="not_established",
            basis="advisor_evidence",
            assessor_kind="human",
            evidence_refs=("evidence:1",),
            now=MOMENT,
        )
    assert caught.value.reason is ApplicationRefusal.ARGUMENTS_INVALID


def test_an_outcome_outside_the_vocabulary_is_refused(chain: ChainEnv) -> None:
    """A conclusion outside the three says nothing.

    **And "not established" is one of them** — the design needs a
    vocabulary that can say "we do not know".
    """
    session = chain.context.store.session

    with pytest.raises(IntegrityError):
        _raw_insert(session, assessment_id="as-bad-outcome", outcome="probably_right")
    session.rollback()


# --------------------------------------------------------------------------- #
# A14 — an assessment names a case the chain holds, in that project
# --------------------------------------------------------------------------- #

#: The paragraph the marked-up manuscript is built on, and the one change
#: in it. **A change and no comment is the third and fourth pilots' shape**
#: — hundreds of edits, not one margin note — and it is the shape whose key
#: has no foreign key behind it.
_MARKED_PARAGRAPH = "The method estimates the parameter from a single observation."
_MARKED_CHANGE = Revision(
    kind="ins",
    text="carefully",
    author="Prof. Lin",
    date="2026-03-02T09:30:00Z",
    element_id="101",
    paragraph=0,
    after_text="estimates",
)


@pytest.fixture()
def marked_up(env: StoreEnv, tmp_path: Path) -> ChainEnv:
    """A project with one comment **and** one tracked change.

    **Both kinds of case in one manuscript**, because an assessment may be
    about either and the door has to reach each through its own table.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return build_chain(
        env.store(),
        workspace,
        comments=(a_comment("201"),),
        paragraphs=(_MARKED_PARAGRAPH,),
        revisions=(_MARKED_CHANGE,),
    )


def _the_change_the_chain_holds(chain: ChainEnv) -> str:
    """The key the product mints for the manuscript's one change."""
    events = record_revision_events(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.second_version_id,
        now=MOMENT,
    )
    assert len(events) == 1, "the fixture's manuscript holds exactly one tracked change"
    return revision_source_key(events[0].revision_event_id)


def _a_keyed_comment(chain: ChainEnv, *, issue_key: str) -> str:
    """The project's comment, filed under *issue_key* by a person."""
    feedback = record_feedback(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.version_id,
        now=MOMENT,
    )[0]
    set_issue_key(
        chain.context,
        feedback_id=feedback.feedback_id,
        issue_key=issue_key,
        now=MOMENT,
    )
    return feedback.feedback_id


def _assessment(
    chain: ChainEnv,
    assessment_id: str,
    *,
    project_id: str | None = None,
    feedback_id: str | None = None,
    issue_key: str | None = None,
) -> FollowupAssessment:
    """One assessment through the door, with everything but its target filled in."""
    return record_assessment(
        chain.context,
        assessment_id=assessment_id,
        project_id=project_id or chain.project_id,
        feedback_id=feedback_id,
        issue_key=issue_key,
        assessment="The advisor's advice was borne out by the later version.",
        outcome="established",
        basis="revised_manuscript",
        assessor_kind="human",
        grade="human_verified",
        evidence_refs=("manuscript-2:the paragraph carries the change",),
        now=MOMENT,
    )


def test_an_assessment_naming_an_issue_the_chain_does_not_hold_is_refused(
    chain: ChainEnv,
) -> None:
    """**The two columns refuse, and each with its own reason.**

    ``feedback_id`` has always been resolved — the store holds no such
    comment, the door says so. ``issue_key`` had **no foreign key and no
    check at all**, so a judgement about an issue nobody ever raised, or
    about a change that was never made, was a row like any other: the
    column is a bare string, and a bare string that names nothing is a
    claim nothing can resolve.

    **The measured hole, before this witness existed.** Against a copy of
    the pilot store the door took ``issue_key="iss-no-such-issue-in-any-table"``
    and committed the row, while the equivalent ``feedback_id`` was refused
    with ``chain_feedback_not_found``. That asymmetry — one of two paths
    validated and the other treated as done — is this project's recurring
    failure, and it is what this test closes.
    """
    _a_keyed_comment(chain, issue_key="parameter-definition")

    with pytest.raises(ApplicationRefusedError) as by_key:
        _assessment(chain, "as-ghost-issue", issue_key="parameter-definission")
    assert by_key.value.reason is ApplicationRefusal.CHAIN_ASSESSMENT_ISSUE_NOT_FOUND
    assert "parameter-definission" in by_key.value.detail, "the refusal names the key"
    assert chain.project_id in by_key.value.detail, "and the project it looked in"

    with pytest.raises(ApplicationRefusedError) as by_comment:
        _assessment(chain, "as-ghost-comment", feedback_id="fb-no-such-feedback")
    assert by_comment.value.reason is ApplicationRefusal.CHAIN_FEEDBACK_NOT_FOUND
    assert "fb-no-such-feedback" in by_comment.value.detail

    # **Each column keeps its own reason, and its own text.** The key's
    # refusal says which project was searched; the comment's names no
    # project, because a comment id is not project-relative — it either
    # is in the store or it is not. A reader told the wrong one would be
    # told the wrong thing, so the texts are part of what is witnessed.
    assert chain.project_id in by_key.value.detail
    assert chain.project_id not in by_comment.value.detail

    # **Refused, not warned.** Nothing reached the table.
    assert list_assessments(chain.context, project_id=chain.project_id) == ()


def test_an_assessment_about_an_issue_key_the_chain_holds_records(chain: ChainEnv) -> None:
    """The good path stays good: a key a comment carries is an issue.

    **The fix must not break what it did not aim at.** Before this work
    order the only way an assessment could name an issue was through a
    comment's key, and the pilot's first two rounds are built that way.
    """
    _a_keyed_comment(chain, issue_key="parameter-definition")

    recorded = _assessment(chain, "as-by-key", issue_key="parameter-definition")
    assert recorded.issue_key == "parameter-definition"
    assert recorded.feedback_id is None, "the assessment is about the issue, not one comment"

    listed = list_assessments(chain.context, project_id=chain.project_id)
    assert [item.assessment_id for item in listed] == ["as-by-key"]


def test_an_assessment_about_a_revision_the_chain_holds_records(marked_up: ChainEnv) -> None:
    """A revision case is assessable by the key the product minted for it.

    **This is the route the next step needs.** Eight of the twenty-four
    rules bind to revision cases, and a revision case has no
    ``feedback_id`` — a manuscript may hold hundreds of changes and not one
    comment — so the assessment can only be made through ``issue_key``.
    """
    key = _the_change_the_chain_holds(marked_up)
    assert key.startswith("rv-"), "the product mints these keys, and they carry its prefix"

    recorded = _assessment(marked_up, "as-by-revision", issue_key=key)
    assert recorded.issue_key == key
    assert recorded.feedback_id is None


def test_a_revision_key_the_chain_does_not_hold_is_refused(marked_up: ChainEnv) -> None:
    """A key that *spells* like a change the chain holds is not one.

    **The prefix is not the proof.** The id is derived from the version,
    the part and the element's path, and a caller who types a plausible
    digest invents a change nobody made — which is exactly what an
    assessment must not be allowed to cite.
    """
    held = _the_change_the_chain_holds(marked_up)
    # Same prefix, same length, one character of the digest changed: the shape
    # is right and the chain holds nothing under it.
    last = held[-1]
    invented = held[:-1] + ("0" if last != "0" else "1")
    assert invented != held and len(invented) == len(held)

    with pytest.raises(ApplicationRefusedError) as caught:
        _assessment(marked_up, "as-invented-revision", issue_key=invented)
    assert caught.value.reason is ApplicationRefusal.CHAIN_ASSESSMENT_ISSUE_NOT_FOUND

    # And the key the chain really holds still records, in the same breath.
    assert _assessment(marked_up, "as-real-revision", issue_key=held).issue_key == held


def test_the_key_is_routed_by_lookup_and_not_by_its_spelling(chain: ChainEnv) -> None:
    """A key spelled like a revision is a **comment** when a comment carries it.

    **A comment's issue key is a person's judgement, and a person may type
    anything** — including the letters the product's own revision ids
    begin with. So the door cannot ask what the key *looks like*: it asks
    the chain, comments first and then the changes, and accepts whichever
    holds it. This is the rule the retrieval already follows
    (``labcairn.guidance.retrieval._living_sources``, ADR-0017 C10), and a
    door that routed by prefix would disagree with the reader about what
    the same key means.
    """
    spelled_like_a_revision = "rv-not-a-change-at-all"
    _a_keyed_comment(chain, issue_key=spelled_like_a_revision)

    recorded = _assessment(
        chain, "as-comment-in-revision-spelling", issue_key=spelled_like_a_revision
    )
    assert recorded.issue_key == spelled_like_a_revision, (
        "a comment carries this key, so it is a comment's issue — the letters decide nothing"
    )

    # And the same *spelling*, carried by nobody, is refused.
    with pytest.raises(ApplicationRefusedError) as caught:
        _assessment(chain, "as-the-same-spelling-held-nowhere", issue_key="rv-no-comment-no-change")
    assert caught.value.reason is ApplicationRefusal.CHAIN_ASSESSMENT_ISSUE_NOT_FOUND


def test_a_case_held_only_in_another_project_is_refused(chain: ChainEnv) -> None:
    """The key must resolve **in the project being assessed**, both ways.

    **A key means "the same problem" only inside one manuscript's
    history**, and two projects may each hold ``"stats"`` without their
    being one problem — the schema says so, and until this work order the
    door checked it for ``feedback_id`` and not for ``issue_key``. Each
    route gets its own half: a comment's key held by the first project is
    not the second's case, and a change held by the second is not the
    first's.
    """
    session = chain.context.store.session
    keyed_elsewhere = "stats"
    _a_keyed_comment(chain, issue_key=keyed_elsewhere)

    # A second project, with a change of its own. **The rows are written
    # directly**, the way the chain's scaffolding writes the version graph.
    session.add(
        PaperProjectRow(
            project_id="proj-2",
            workspace_id="ws-1",
            subject_pseudonym="subject-2",
            consent_ref=None,
            created_at=MOMENT,
        )
    )
    # ``ver-1`` and ``ver-2`` are the first project's, and a version belongs
    # to one project — so the other project's version is named for it.
    session.add(
        PaperVersionRow(
            version_id="ver-of-proj-2",
            project_id="proj-2",
            source_id=chain.source_id,
            source_content_sha256=None,
            version_label_raw="manuscript.docx",
            stage_candidate="draft",
            status="resolved",
            created_at=MOMENT,
        )
    )
    other_projects_change = "rv-belonging-to-proj-2"
    session.add(
        RevisionEventRow(
            revision_event_id=other_projects_change,
            version_id="ver-of-proj-2",
            kind="ins",
            text="",
            text_sha256=hashlib.sha256(b"").hexdigest(),
            author=None,
            author_unknown_reason="written by the scaffolding, not read from a file",
            occurred_at=None,
            date_unknown_reason="the scaffolding writes the row, and no file was read",
            nested=False,
            parser_version="test",
            grade="inferred",
            created_at=MOMENT,
        )
    )
    session.commit()

    # The comment's key is proj-1's, so proj-2 may not assess under it...
    with pytest.raises(ApplicationRefusedError) as caught:
        _assessment(
            chain, "as-key-from-the-other-project", project_id="proj-2", issue_key=keyed_elsewhere
        )
    assert caught.value.reason is ApplicationRefusal.CHAIN_ASSESSMENT_ISSUE_NOT_FOUND
    assert "proj-2" in caught.value.detail

    # ...and the change is proj-2's, so proj-1 may not assess under it.
    with pytest.raises(ApplicationRefusedError) as caught:
        _assessment(
            chain,
            "as-change-from-the-other-project",
            issue_key=other_projects_change,
        )
    assert caught.value.reason is ApplicationRefusal.CHAIN_ASSESSMENT_ISSUE_NOT_FOUND

    # But each project assesses its own case, and the refusal was about the
    # scope, not about the key existing anywhere at all.
    assert _assessment(chain, "as-own-key", issue_key=keyed_elsewhere).issue_key == keyed_elsewhere
    assert (
        _assessment(
            chain,
            "as-own-change",
            project_id="proj-2",
            issue_key=other_projects_change,
        ).issue_key
        == other_projects_change
    )


def test_a_blank_issue_key_beside_a_comment_is_refused(chain: ChainEnv) -> None:
    """An ``issue_key`` that is blank names nothing, even beside a comment.

    **The row would carry a key no reader can resolve** — the schema's own
    rule is that a key is present or absent, never empty — and the door
    that lets a blank one through next to a good ``feedback_id`` is the
    same door that let an invented one through alone.
    """
    feedback = _a_keyed_comment(chain, issue_key="parameter-definition")

    with pytest.raises(ApplicationRefusedError) as caught:
        _assessment(chain, "as-blank-key", feedback_id=feedback, issue_key="   ")
    assert caught.value.reason is ApplicationRefusal.ARGUMENTS_INVALID
    assert list_assessments(chain.context, project_id=chain.project_id) == ()


def test_an_assessment_naming_a_comment_still_records_without_a_key(chain: ChainEnv) -> None:
    """The ``feedback_id`` path is unchanged, and the two may be named together.

    **A judgement about one comment, and about the issue it belongs to.**
    When both are given, each is resolved by its own rule: the comment by
    the foreign key and the door's project check, the issue by the chain.
    """
    feedback = _a_keyed_comment(chain, issue_key="parameter-definition")

    by_comment = _assessment(chain, "as-by-comment", feedback_id=feedback)
    assert by_comment.feedback_id == feedback
    assert by_comment.issue_key is None

    both = _assessment(
        chain,
        "as-comment-and-its-issue",
        feedback_id=feedback,
        issue_key="parameter-definition",
    )
    assert both.feedback_id == feedback
    assert both.issue_key == "parameter-definition"

    # And the comment alone does not vouch for a key it was never given.
    with pytest.raises(ApplicationRefusedError) as caught:
        _assessment(
            chain,
            "as-comment-and-an-invented-issue",
            feedback_id=feedback,
            issue_key="parameter-definission",
        )
    assert caught.value.reason is ApplicationRefusal.CHAIN_ASSESSMENT_ISSUE_NOT_FOUND
