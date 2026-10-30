"""The response: the judgement that a change answered a comment, and its
evidence.

**Why this is the hardest table in the chain.** The work order's clause
is blunt: *"an unaddressed comment is not reported as addressed, and
neither is a wrong response or a partial one."* So the four states are
not four labels for one thing:

- a comment with **no** link is ``pending``, and it is **listed as
  unaddressed** — not as addressed, and not absent from the listing;
- a link whose evidence says the change does **not** answer the comment
  is ``not_addressed``, and it **exists**: the student did something, and
  the record says it did not help;
- a link whose evidence says the change answers **part** of the comment
  is ``partially_addressed``;
- only ``addressed`` says the comment was answered.

**And a judgement is a judgement with evidence behind it.** ``pending`` is
the only state a row may hold without a decision, and the other three
require a decider and the evidence that decided them. A status anybody can
set is not a status, so the schema refuses one.

**And the acceptance of a change is not an answer.** A link is
``addressed`` only when a rule or a person says so, and the thing that
said so is on the row. A model may put a link forward — that is a
*candidate*, at grade ``inferred`` — but it may not decide one.
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
from labcairn.db.models import FeedbackEventRow, ResponseLinkRow
from labcairn.papers.chain import (
    ChainRefusal,
    edit_row,
    feedback_row,
    material_relative_path,
    project_row,
    project_version_rows,
)
from labcairn.papers.feedback import FeedbackEvent, event_from_row
from labcairn.runtime.trajectory import emit_response_recorded
from labcairn.security.capabilities import CapabilityId
from labcairn.security.paths import CanonicalPath

#: The four states a link may hold. **Only ``addressed`` says the comment
#: was answered.**
RESPONSE_STATES: frozenset[str] = frozenset(
    {"pending", "addressed", "partially_addressed", "not_addressed"}
)

#: Who may decide a link. **A model may not**: a rule or a person
#: settles whether a change answered a comment.
DECIDERS: frozenset[str] = frozenset({"rule", "user"})

#: The grades a link may carry.
LINK_GRADES: frozenset[str] = frozenset({"observed", "human_verified", "inferred"})

#: Why a comment is on the unaddressed listing.
UNADDRESSED_REASONS: frozenset[str] = frozenset(
    {"no_response", "pending", "not_addressed", "partially_addressed"}
)


@dataclass(frozen=True, slots=True)
class ResponseLink:
    """One judgement about one change, as the chain records it."""

    response_link_id: str
    feedback_id: str
    edit_action_id: str
    state: str
    grade: str
    decided_by: str | None
    decided_at: datetime | None
    evidence_refs: tuple[str, ...]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class UnaddressedComment:
    """A comment the chain holds, and why it is not answered.

    **The reason is part of the answer.** "Unaddressed" is four different
    situations — nobody answered, somebody is answering, somebody answered
    and it did not help, somebody answered it partly — and a reader asking
    "what has not been dealt with?" wants to tell them apart.
    """

    feedback: FeedbackEvent
    reason: str


def _link_from_row(row: ResponseLinkRow) -> ResponseLink:
    """The record a row is."""
    return ResponseLink(
        response_link_id=row.response_link_id,
        feedback_id=row.feedback_id,
        edit_action_id=row.edit_action_id,
        state=row.state,
        grade=row.grade,
        decided_by=row.decided_by,
        decided_at=row.decided_at,
        evidence_refs=tuple(row.evidence_refs),
        created_at=row.created_at,
    )


def _material(context: ApplicationContext, version_id: str) -> CanonicalPath:
    """The material a version was made from, as a resource.

    :raises ApplicationRefusedError: the version names material the ledger
        does not hold.
    """
    relative_path = material_relative_path(context.store.session, version_id)
    if relative_path is None:
        raise chain_refused(
            ChainRefusal.SOURCE_NOT_FOUND,
            f"the manuscript version {version_id!r} names material the ledger does "
            "not hold. A response is about a manuscript, and a response about a "
            "manuscript nobody holds is a response about nothing.",
        )
    return context.resource_for(relative_path)


def record_response(
    context: ApplicationContext,
    *,
    response_link_id: str,
    feedback_id: str,
    edit_action_id: str,
    state: str,
    grade: str = "observed",
    decided_by: str | None = None,
    decided_at: datetime | None = None,
    evidence_refs: tuple[str, ...] = (),
    now: datetime,
) -> ResponseLink:
    """Record the judgement that a change answered a comment.

    **A state other than ``pending`` needs a decider and the evidence
    behind it.** A judgement with no evidence is refused here and by the
    schema, because a status anybody can set is not a status.

    **And a model may not decide one.** A model may put a link forward —
    ``state='pending'``, ``grade='inferred'``, ``decided_by='model'`` —
    and that candidate is a fact about what the model proposed. It may
    not mark a comment answered.

    :raises ApplicationRefusedError: the comment or the change is not
        there; the state, the grade or the decider is outside its
        vocabulary; a decided link has no evidence; a model tried to
        decide; or the policy denied reading the manuscript.
    """
    session = context.store.session
    if state not in RESPONSE_STATES:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"{state!r} is not a state a response may hold. A link is pending, "
            "addressed, partly addressed or not addressed, and a state outside those "
            "four says nothing about whether the comment was answered.",
        )
    if grade not in LINK_GRADES:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"{grade!r} is not a grade. A judgement is observed, confirmed by a "
            "person, or the system's own inference.",
        )
    if feedback_row(session, feedback_id) is None:
        raise chain_refused(
            ChainRefusal.FEEDBACK_NOT_FOUND,
            f"the store holds no feedback event with the id {feedback_id!r}. A "
            "response is about a comment, and a response about a comment nobody "
            "holds is a response about nothing.",
        )
    if edit_row(session, edit_action_id) is None:
        raise chain_refused(
            ChainRefusal.EDIT_NOT_FOUND,
            f"the store holds no edit action with the id {edit_action_id!r}. A "
            "response links a comment to a change, and a link to a change nobody "
            "made is a link to nothing.",
        )
    if decided_by is not None and decided_by not in DECIDERS | {"model"}:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"{decided_by!r} is not a decider. A link is decided by a rule, by a "
            "person, or put forward by a model.",
        )
    if state != "pending":
        if decided_by is None or decided_at is None or not evidence_refs:
            raise chain_refused(
                ChainRefusal.RESPONSE_NEEDS_EVIDENCE,
                f"the response {response_link_id!r} is {state!r} and names no "
                "decision, no moment and no evidence. A status anybody can set is "
                "not a status: a link that is not pending must say who decided it, "
                "when, and on what.",
            )
        if decided_by == "model":
            raise chain_refused(
                ChainRefusal.RESPONSE_MAY_NOT_BE_DECIDED_BY_A_MODEL,
                f"the response {response_link_id!r} is decided by a model. A model "
                "may put a link forward — that is a candidate, at grade 'inferred' — "
                "but only a rule or a person settles whether a change answered a "
                "comment.",
            )
        if grade == "inferred":
            raise ApplicationRefusedError(
                ApplicationRefusal.ARGUMENTS_INVALID,
                f"the response {response_link_id!r} is decided by {decided_by!r} and "
                "graded 'inferred'. A judgement the system inferred and a judgement "
                "a rule or a person made are two different things, and a row may "
                "not be both.",
            )
    if decided_by == "model" and grade != "inferred":
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the response {response_link_id!r} was put forward by a model and is "
            f"graded {grade!r}. A model's candidate is the system's own inference, "
            "and it is graded 'inferred' because nothing has confirmed it.",
        )
    if decided_by is None and grade == "inferred":
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the response {response_link_id!r} is graded 'inferred' and names no "
            "one who put it forward. An inference is somebody's proposal, and the "
            "row says who made it.",
        )

    feedback = feedback_row(session, feedback_id)
    assert feedback is not None  # checked above
    consent.evaluate_all(
        context,
        capability=CapabilityId.SOURCE_INVENTORY,
        arguments={},
        resources=(_material(context, feedback.version_id),),
    )

    existing = session.get(ResponseLinkRow, response_link_id)
    if existing is not None:
        return _link_from_row(existing)
    row = ResponseLinkRow(
        response_link_id=response_link_id,
        feedback_id=feedback_id,
        edit_action_id=edit_action_id,
        state=state,
        grade=grade,
        decided_by=decided_by,
        decided_at=decided_at,
        evidence_refs=list(evidence_refs),
        created_at=now,
    )
    session.add(row)
    if state == "pending":
        # **A pending response is not an event.** "No response row" is how
        # "unanswered" is represented, and an event saying a judgement was
        # made would say the opposite of what a pending row means. So the
        # row commits and the stream is left alone.
        session.commit()
    else:
        with context.store.unit(context.task_id) as work:
            emit_response_recorded(
                work,
                response_link_id=response_link_id,
                project_id=feedback.project_id,
                feedback_id=feedback_id,
                edit_action_id=edit_action_id,
                state=state,
            )
    return _link_from_row(row)


def list_response_links(
    context: ApplicationContext,
    *,
    feedback_id: str | None = None,
    edit_action_id: str | None = None,
) -> tuple[ResponseLink, ...]:
    """The judgements the chain holds, by comment or by change.

    **Denied material is dropped, not refused** — ADR-0003 C5's rule for a
    bulk listing.

    :raises ApplicationRefusedError: the arguments are not usable.
    """
    session = context.store.session
    statement = select(ResponseLinkRow).order_by(
        ResponseLinkRow.created_at, ResponseLinkRow.response_link_id
    )
    if feedback_id is not None:
        statement = statement.where(ResponseLinkRow.feedback_id == feedback_id)
    if edit_action_id is not None:
        statement = statement.where(ResponseLinkRow.edit_action_id == edit_action_id)
    rows = tuple(session.scalars(statement))
    if not rows:
        return ()
    resources = tuple(
        _material(context, feedback.version_id)
        for feedback in (feedback_row(session, row.feedback_id) for row in rows)
        if feedback is not None
    )
    permitted = consent.evaluate_each(
        context,
        capability=CapabilityId.SOURCE_INVENTORY,
        arguments={},
        resources=resources,
    )
    allowed = {resource.resolved_key for resource in permitted}
    kept = [
        row
        for row in rows
        if (feedback := feedback_row(session, row.feedback_id)) is not None
        and _material(context, feedback.version_id).resolved_key in allowed
    ]
    return tuple(_link_from_row(row) for row in kept)


def list_unaddressed(
    context: ApplicationContext,
    *,
    project_id: str,
    version_id: str | None = None,
) -> tuple[UnaddressedComment, ...]:
    """The comments that have not been answered, **and why not**.

    **A comment with no response is on this list.** Not absent from it —
    absent from it would make the chain's silence indistinguishable from
    its having nothing to say, and the reader asking "what has not been
    dealt with?" would get an empty answer that looks like "nothing is
    outstanding".

    **And a partly-answered comment is on it too.** ``partially_addressed``
    is not ``addressed``: the student did something, and it did not
    finish the job.

    :raises ApplicationRefusedError: the project or the version is not
        there, or the arguments are not usable.
    """
    session = context.store.session
    if project_row(session, project_id) is None:
        raise chain_refused(
            ChainRefusal.PROJECT_NOT_FOUND,
            f"the store holds no paper project with the id {project_id!r}.",
        )
    versions = project_version_rows(session, project_id)
    if version_id is not None:
        versions = tuple(version for version in versions if version.version_id == version_id)
        if not versions:
            raise chain_refused(
                ChainRefusal.VERSION_NOT_FOUND,
                f"the store holds no manuscript version with the id {version_id!r} in "
                f"the project {project_id!r}.",
            )
    resources = tuple(
        context.resource_for(path)
        for path in (material_relative_path(session, version.version_id) for version in versions)
        if path is not None
    )
    permitted = consent.evaluate_each(
        context,
        capability=CapabilityId.SOURCE_INVENTORY,
        arguments={},
        resources=resources,
    )
    allowed = {resource.resolved_key for resource in permitted}
    wanted = {
        version.version_id
        for version in versions
        if (path := material_relative_path(session, version.version_id)) is not None
        and context.resource_for(path).resolved_key in allowed
    }

    links = tuple(
        session.scalars(
            select(ResponseLinkRow).order_by(
                ResponseLinkRow.created_at, ResponseLinkRow.response_link_id
            )
        )
    )
    by_feedback: dict[str, list[ResponseLinkRow]] = {}
    for link in links:
        by_feedback.setdefault(link.feedback_id, []).append(link)

    comments = tuple(
        session.scalars(
            select(FeedbackEventRow)
            .where(FeedbackEventRow.project_id == project_id)
            .order_by(FeedbackEventRow.created_at, FeedbackEventRow.feedback_id)
        )
    )
    unaddressed: list[UnaddressedComment] = []
    for comment in comments:
        if comment.version_id not in wanted:
            continue
        states = {link.state for link in by_feedback.get(comment.feedback_id, [])}
        if "addressed" in states:
            continue
        if not states:
            reason = "no_response"
        elif "pending" in states:
            reason = "pending"
        elif "not_addressed" in states:
            reason = "not_addressed"
        else:
            reason = "partially_addressed"
        unaddressed.append(UnaddressedComment(feedback=event_from_row(comment), reason=reason))
    return tuple(unaddressed)


__all__ = [
    "DECIDERS",
    "LINK_GRADES",
    "RESPONSE_STATES",
    "UNADDRESSED_REASONS",
    "ResponseLink",
    "UnaddressedComment",
    "list_response_links",
    "list_unaddressed",
    "record_response",
]
