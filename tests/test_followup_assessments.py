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

from pathlib import Path

import pytest
from feedback_chain_fixtures import MOMENT, ChainEnv, a_comment, build_chain
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_store_support import StoreEnv
from test_store_support import env as _shared_env

from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.papers.assessments import (
    list_assessments,
    list_recurring_issues,
    record_assessment,
)
from labcairn.papers.feedback import record_feedback, set_issue_key

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
