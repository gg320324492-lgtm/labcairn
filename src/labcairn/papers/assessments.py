"""The later assessment: a judgement about an issue, with its own evidence.

**And the design's hard line lives here.** *"The advisor's advice must not
be recorded as correct because the student's change was accepted."*
Acceptance is a fact about the process; the correctness of the advice is a
claim about the science, and the second needs its own evidence.

**So the assessment carries its own evidence, and it can say "not
established."** The same way ``VerificationStatus`` can be
``unsupported`` and ``conflicted``, and the same way ``StageCandidate``
has an ``UNKNOWN`` member.

**And the basis it rests on is a closed vocabulary with no member meaning
"the change was accepted."** The refusal is a fact about the row rather
than a convention nobody keeps.

**And a recurrence is recorded, not inferred.** Two comments are about the
same problem when somebody says they are, through an ``issue_key``. The
same wording is not the same issue, and inferring it from similarity is
the thing ADR-0014 already refused to do for version order.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from labcairn.application import consent
from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import (
    ApplicationRefusal,
    ApplicationRefusedError,
    chain_refused,
)
from labcairn.db.models import FeedbackEventRow, FollowupAssessmentRow
from labcairn.papers.chain import (
    ChainRefusal,
    feedback_row,
    feedback_rows_for_issue,
    material_relative_path,
    project_row,
    project_version_rows,
)
from labcairn.runtime.trajectory import emit_followup_assessed
from labcairn.security.capabilities import CapabilityId
from labcairn.security.paths import CanonicalPath

#: What an assessment may rest on. **There is no member meaning "the
#: change was accepted"** — the change being accepted says the process
#: went on, and it does not say the advice was right.
ASSESSMENT_BASES: frozenset[str] = frozenset(
    {
        "advisor_evidence",
        "revised_manuscript",
        "independent_check",
        "human_attestation",
    }
)

#: What an assessment concluded. **``not_established`` is a member**, and
#: it is the one the design needs: a system that can only say "correct"
#: cannot say "we do not know".
ASSESSMENT_OUTCOMES: frozenset[str] = frozenset({"established", "not_established", "conflicted"})

#: Who may make an assessment.
ASSESSOR_KINDS: frozenset[str] = frozenset({"advisor", "student", "model", "human", "rule"})

#: The grades an assessment may carry.
ASSESSMENT_GRADES: frozenset[str] = frozenset({"observed", "inferred", "human_verified"})


@dataclass(frozen=True, slots=True)
class FollowupAssessment:
    """One later judgement about an issue, as the chain records it."""

    assessment_id: str
    project_id: str
    feedback_id: str | None
    issue_key: str | None
    assessment: str
    outcome: str
    basis: str
    assessor_kind: str
    grade: str
    evidence_refs: tuple[str, ...]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RecurringIssue:
    """One issue that came back, and the rounds it came back in.

    **A recurrence is visible without being stored.** The relation is in
    the rows — two comments carrying the same person-given key in two
    versions — and this is that relation read back. **No table of
    recurrences exists**, because a table whose name means two things is a
    table nobody can read.
    """

    issue_key: str
    project_id: str
    feedback_ids: tuple[str, ...]
    version_ids: tuple[str, ...]


def _assessment_from_row(row: FollowupAssessmentRow) -> FollowupAssessment:
    """The record a row is."""
    return FollowupAssessment(
        assessment_id=row.assessment_id,
        project_id=row.project_id,
        feedback_id=row.feedback_id,
        issue_key=row.issue_key,
        assessment=row.assessment,
        outcome=row.outcome,
        basis=row.basis,
        assessor_kind=row.assessor_kind,
        grade=row.grade,
        evidence_refs=tuple(row.evidence_refs),
        created_at=row.created_at,
    )


def _materials(context: ApplicationContext, project_id: str) -> tuple[CanonicalPath, ...]:
    """The materials of a project's versions, as resources."""
    session = context.store.session
    return tuple(
        context.resource_for(path)
        for path in (
            material_relative_path(session, version.version_id)
            for version in project_version_rows(session, project_id)
        )
        if path is not None
    )


def record_assessment(
    context: ApplicationContext,
    *,
    assessment_id: str,
    project_id: str,
    assessment: str,
    outcome: str,
    basis: str,
    assessor_kind: str,
    feedback_id: str | None = None,
    issue_key: str | None = None,
    grade: str = "observed",
    evidence_refs: tuple[str, ...] = (),
    now: datetime,
) -> FollowupAssessment:
    """Record a later judgement about an issue.

    **It must carry its own evidence.** An assessment with no evidence
    behind it is a conclusion anybody can reach, so it is refused here and
    by the schema.

    **And the basis it rests on is closed.** "The change was accepted" is
    not one of the bases, because **the acceptance of a change is a fact
    about the process and not a claim about the science** — a row that
    rests on it is refused.

    **And it names a comment or an issue.** An assessment about nothing is
    not an assessment.

    :raises ApplicationRefusedError: the project, the comment or the issue
        is not there; the basis, the outcome, the assessor or the grade is
        outside its vocabulary; the assessment has no evidence; or the
        policy denied reading the manuscript.
    """
    session = context.store.session
    if project_row(session, project_id) is None:
        raise chain_refused(
            ChainRefusal.PROJECT_NOT_FOUND,
            f"the store holds no paper project with the id {project_id!r}. An "
            "assessment is about a manuscript's issue, and an assessment about a "
            "manuscript nobody holds is an assessment about nothing.",
        )
    if basis not in ASSESSMENT_BASES:
        raise chain_refused(
            ChainRefusal.ASSESSMENT_BASIS_REFUSED,
            f"{basis!r} is not a thing an assessment may rest on. An assessment rests "
            "on the advisor's own evidence, on the revised manuscript, on an "
            "independent check, or on a person's attestation — and **the acceptance "
            "of a change is not among them**: acceptance is a fact about the "
            "process, and the correctness of the advice is a claim about the science "
            "that needs its own evidence.",
        )
    if outcome not in ASSESSMENT_OUTCOMES:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"{outcome!r} is not a conclusion. An assessment concludes that the "
            "advice is established, that it is not established, or that the "
            "evidence is in conflict — and 'we do not know' is one of them.",
        )
    if assessor_kind not in ASSESSOR_KINDS:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"{assessor_kind!r} is not a kind of assessor.",
        )
    if grade not in ASSESSMENT_GRADES:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"{grade!r} is not a grade. An assessment is observed, inferred, or "
            "confirmed by a person.",
        )
    if not evidence_refs:
        raise chain_refused(
            ChainRefusal.ASSESSMENT_NEEDS_EVIDENCE,
            f"the assessment {assessment_id!r} names no evidence. An assessment with "
            "no evidence behind it is a conclusion anybody can reach, and the "
            "advisor's advice may not be recorded as correct because the student's "
            "change was accepted.",
        )
    if feedback_id is None and not (issue_key or "").strip():
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the assessment {assessment_id!r} names neither a comment nor an issue "
            "key. An assessment is about something: a comment, or an issue somebody "
            "named.",
        )
    if feedback_id is not None:
        feedback = feedback_row(session, feedback_id)
        if feedback is None:
            raise chain_refused(
                ChainRefusal.FEEDBACK_NOT_FOUND,
                f"the store holds no feedback event with the id {feedback_id!r}. An "
                "assessment about a comment nobody holds is an assessment about "
                "nothing.",
            )
        if feedback.project_id != project_id:
            raise chain_refused(
                ChainRefusal.FEEDBACK_NOT_FOUND,
                f"the feedback {feedback_id!r} belongs to the project "
                f"{feedback.project_id!r}, not to {project_id!r}.",
            )

    consent.evaluate_all(
        context,
        capability=CapabilityId.SOURCE_INVENTORY,
        arguments={},
        resources=_materials(context, project_id),
    )

    existing = session.get(FollowupAssessmentRow, assessment_id)
    if existing is not None:
        return _assessment_from_row(existing)
    row = FollowupAssessmentRow(
        assessment_id=assessment_id,
        project_id=project_id,
        feedback_id=feedback_id,
        issue_key=issue_key,
        assessment=assessment,
        outcome=outcome,
        basis=basis,
        assessor_kind=assessor_kind,
        grade=grade,
        evidence_refs=list(evidence_refs),
        created_at=now,
    )
    session.add(row)
    # **The row and the event land together**: an assessment the stream
    # cannot show is a conclusion the report's hash chain does not cover.
    with context.store.unit(context.task_id) as work:
        emit_followup_assessed(
            work,
            assessment_id=assessment_id,
            project_id=project_id,
            verdict=outcome,
            feedback_id=feedback_id,
            issue_key=issue_key,
        )
    return _assessment_from_row(row)


def list_assessments(
    context: ApplicationContext,
    *,
    project_id: str,
    feedback_id: str | None = None,
    issue_key: str | None = None,
) -> tuple[FollowupAssessment, ...]:
    """The assessments the chain holds about a project, a comment or an issue.

    **Denied material is dropped, not refused** — ADR-0003 C5's rule for a
    bulk listing.

    :raises ApplicationRefusedError: the project is not there, or the
        arguments are not usable.
    """
    session = context.store.session
    if project_row(session, project_id) is None:
        raise chain_refused(
            ChainRefusal.PROJECT_NOT_FOUND,
            f"the store holds no paper project with the id {project_id!r}.",
        )
    statement = select(FollowupAssessmentRow).where(FollowupAssessmentRow.project_id == project_id)
    if feedback_id is not None:
        statement = statement.where(FollowupAssessmentRow.feedback_id == feedback_id)
    if issue_key is not None:
        statement = statement.where(FollowupAssessmentRow.issue_key == issue_key)
    statement = statement.order_by(
        FollowupAssessmentRow.created_at, FollowupAssessmentRow.assessment_id
    )
    rows = tuple(session.scalars(statement))
    if not rows:
        return ()
    permitted = consent.evaluate_each(
        context,
        capability=CapabilityId.SOURCE_INVENTORY,
        arguments={},
        resources=_materials(context, project_id),
    )
    if not permitted:
        return ()
    return tuple(_assessment_from_row(row) for row in rows)


def list_recurring_issues(
    context: ApplicationContext,
    *,
    project_id: str,
) -> tuple[RecurringIssue, ...]:
    """The issues that came back, one entry each.

    **A recurrence is two comments in one project with the same
    person-given key in two different versions.** The round is a document,
    not an entity: a round is the set of comments written against one
    manuscript version, so a recurrence is a fact about two versions and
    **no table of rounds is needed**.

    **And a key nobody gave is not a key.** Only rows carrying an
    ``issue_key`` are grouped; a comment with none is uncategorised, and it
    is not guessed at.

    :raises ApplicationRefusedError: the project is not there.
    """
    session = context.store.session
    if project_row(session, project_id) is None:
        raise chain_refused(
            ChainRefusal.PROJECT_NOT_FOUND,
            f"the store holds no paper project with the id {project_id!r}.",
        )
    consent.evaluate_each(
        context,
        capability=CapabilityId.SOURCE_INVENTORY,
        arguments={},
        resources=_materials(context, project_id),
    )
    # The keys the feedback rows carry, not the keys the assessments
    # carry: a recurrence is a relation between *comments*.
    feedback_keys = tuple(
        sorted(
            {
                str(row.issue_key)
                for row in session.scalars(
                    select(FeedbackEventRow).where(FeedbackEventRow.project_id == project_id)
                )
                if row.issue_key
            }
        )
    )
    recurring: list[RecurringIssue] = []
    for key in feedback_keys:
        rows = feedback_rows_for_issue(session, project_id, key)
        versions = tuple(sorted({row.version_id for row in rows}))
        if len(versions) < 2:
            continue
        recurring.append(
            RecurringIssue(
                issue_key=key,
                project_id=project_id,
                feedback_ids=tuple(row.feedback_id for row in rows),
                version_ids=versions,
            )
        )
    return tuple(recurring)


__all__ = [
    "ASSESSMENT_BASES",
    "ASSESSMENT_GRADES",
    "ASSESSMENT_OUTCOMES",
    "ASSESSOR_KINDS",
    "FollowupAssessment",
    "RecurringIssue",
    "list_assessments",
    "list_recurring_issues",
    "record_assessment",
]
