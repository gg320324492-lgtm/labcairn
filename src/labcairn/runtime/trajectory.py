"""The feedback chain's four events, and the payloads that make them replayable.

**What the chain is.** ADR-0017's chain has five links — a question, a piece
of guidance, an edit, the evidence after the edit, and a later assessment —
and four of them leave an event on the append-only stream, so that the
report's hash chain covers *what happened and when*:

``feedback_recorded``
    a comment was found in the manuscript;
``edit_action_recorded``
    a change was recorded against a version edge;
``response_recorded``
    a judgement linked a change to the comment it answers;
``followup_assessed``
    a later assessment of the issue.

**They are annotations, and the event model says so.** A comment is not an
attempt: it happened outside any Run, so these events carry no transition and
no ``run_id``, and :class:`~labcairn.runtime.event.Event` refuses both.

**The payload is what makes the chain replayable.** The event stream is
per-Task and says only *that* something happened; the payload says *which
row*. A reader following the chain from the stream alone needs, for each
event:

* the **project** the chain belongs to — the scope every link shares;
* the **row** the event is about — its id;
* the **links** to the neighbouring rows — the version the comment was written
  against, the edge the edit moved along, the feedback and the edit a
  response joins, the feedback or the issue key an assessment is about.

That is what the four models below carry, and nothing more.

**The judgement itself belongs to the row, not to the event.** ADR-0017 D8
says it plainly: *"the events are not the links... the events say that the
chain happened."* So the response's state, the edit's actor and the
assessment's verdict are not copied here. A second copy of a closed
vocabulary is a second thing that can drift from the first, and the tables
are where the chain's content lives.

**Why the models are not in** :mod:`~labcairn.runtime.event`. That file is
the vocabulary; these are the trajectory's. The registration still reaches
every reader: importing a module of a package imports the package first, and
:mod:`labcairn.runtime`'s own ``__init__`` imports this one. See
:func:`~labcairn.runtime.event.register_payload_schema`.

**These functions write the event and not the row.** The row is the
application layer's to write, in the same unit of work, so that the row and
the event land together or neither does. **And they do not import the
store's layer to do it** -- see :class:`EventWriter`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from pydantic import Field

from labcairn.core.schema import LabCairnModel
from labcairn.runtime.event import Event, EventType, register_payload_schema


class EventWriter(Protocol):
    """What the emitters need from the store's unit of work.

    **The runtime layer does not import the store's layer.** The dependency
    runs the other way -- :mod:`labcairn.db.repository` imports
    :mod:`labcairn.runtime.event` -- and
    ``tests/test_application_layer.py``'s boundary test says so: a module
    outside the application layer that reaches the store is a caller the
    layer's guards do not reach. So the emitters declare what they need and
    the application layer hands them a unit of work, which satisfies it.
    """

    def emit(
        self,
        event_type: EventType,
        *,
        payload: Mapping[str, object] | None = None,
    ) -> Event: ...


class FeedbackRecordedPayload(LabCairnModel):
    """What a ``feedback_recorded`` event says.

    A comment found in a manuscript, and the two things a reader needs to
    find it again: which row it is, and which manuscript state it was written
    against.

    **The version is not decoration.** ADR-0017 D1 refuses a feedback row
    that names no version — a comment that names no manuscript state cannot
    be said to have been answered by any change, because there is no
    "before" to have been answered against. The event carries the same
    version for the same reason: without it, the round the comment belongs to
    is a question the stream cannot answer.
    """

    #: The row this event is about.
    feedback_id: str = Field(min_length=1)
    #: The project the chain belongs to. Every link of one chain shares it.
    project_id: str = Field(min_length=1)
    #: The manuscript version the comment was written against.
    version_id: str = Field(min_length=1)


class EditActionRecordedPayload(LabCairnModel):
    """What an ``edit_action_recorded`` event says.

    A change made against a version edge, and the two links that make the
    chain traversable: the edge the manuscript moved along, and the comment
    the change answers.

    **``feedback_id`` is nullable, and that is not a hole.** ADR-0017 D4:
    *"a change that answers nothing is not an error"* — a student may edit
    for reasons the advisor never wrote down, and forcing every edit into a
    comment it does not answer would be a false claim rather than a complete
    one.
    """

    #: The row this event is about.
    edit_action_id: str = Field(min_length=1)
    #: The project the chain belongs to.
    project_id: str = Field(min_length=1)
    #: The edge it is — the parent/child pair the manuscript moved along.
    version_edge_id: str = Field(min_length=1)
    #: The comment it answers, when it answers one.
    feedback_id: str | None = Field(default=None, min_length=1)


class ResponseRecordedPayload(LabCairnModel):
    """What a ``response_recorded`` event says.

    A judgement that links a comment to a change. The event names the two
    rows the link joins, which is what makes the chain traversable from the
    stream: the comment, the change, and the response that connects them.

    **The state is the row's, not the event's.** ADR-0017 D5's states are
    the hardest clause of the work order — an unaddressed comment must not
    be reported as addressed — and the rule that decides them lives in the
    row and in the evidence behind it. Copying the state here would put a
    second copy of a closed vocabulary beside the first, and the two could
    disagree.
    """

    #: The row this event is about.
    response_id: str = Field(min_length=1)
    #: The project the chain belongs to.
    project_id: str = Field(min_length=1)
    #: The comment the response is about.
    feedback_id: str = Field(min_length=1)
    #: The change the response judges.
    edit_action_id: str = Field(min_length=1)


class FollowupAssessedPayload(LabCairnModel):
    """What a ``followup_assessed`` event says.

    A later judgement about an issue. ADR-0017 D7 gives an assessment two
    subjects — a comment or an issue key — and both are carried, because the
    issue key is what makes a recurrence visible: two comments with one key
    in different rounds are one recurring issue and not two unrelated
    comments.

    **The verdict is the row's.** The assessment's own evidence, and its
    ability to say *"not established"*, are D7's business and stay there.
    """

    #: The row this event is about.
    assessment_id: str = Field(min_length=1)
    #: The project the chain belongs to.
    project_id: str = Field(min_length=1)
    #: The comment the assessment is about, when it is about one.
    feedback_id: str | None = Field(default=None, min_length=1)
    #: The issue the assessment is about, when it is about an issue rather
    #: than a single comment.
    issue_key: str | None = Field(default=None, min_length=1)


register_payload_schema(EventType.FEEDBACK_RECORDED, FeedbackRecordedPayload)
register_payload_schema(EventType.EDIT_ACTION_RECORDED, EditActionRecordedPayload)
register_payload_schema(EventType.RESPONSE_RECORDED, ResponseRecordedPayload)
register_payload_schema(EventType.FOLLOWUP_ASSESSED, FollowupAssessedPayload)


def emit_feedback_recorded(
    work: EventWriter,
    *,
    feedback_id: str,
    project_id: str,
    version_id: str,
) -> Event:
    """Record that a comment was found in the manuscript.

    *work* is the unit of work the feedback row is written in. The event
    belongs to the same transaction, so the row and the event land together
    or neither does.

    The returned event's ``seq`` is **provisional** — the store allocates the
    real one when it flushes. Read the unit of work's ``events`` after the
    context manager exits.

    **The row is not written here.** This function writes the event that
    names the row; writing the row is the application layer's job.
    """
    payload = FeedbackRecordedPayload(
        feedback_id=feedback_id,
        project_id=project_id,
        version_id=version_id,
    )
    return work.emit(EventType.FEEDBACK_RECORDED, payload=payload.model_dump(mode="json"))


def emit_edit_action_recorded(
    work: EventWriter,
    *,
    edit_action_id: str,
    project_id: str,
    version_edge_id: str,
    feedback_id: str | None = None,
) -> Event:
    """Record a change made against a version edge.

    *feedback_id* is the comment the change answers, and ``None`` when it
    answers none — which ADR-0017 D4 says is not an error but a fact.

    The provisional ``seq``, the transaction and the row are as
    :func:`emit_feedback_recorded` describes them.
    """
    payload = EditActionRecordedPayload(
        edit_action_id=edit_action_id,
        project_id=project_id,
        version_edge_id=version_edge_id,
        feedback_id=feedback_id,
    )
    return work.emit(EventType.EDIT_ACTION_RECORDED, payload=payload.model_dump(mode="json"))


def emit_response_recorded(
    work: EventWriter,
    *,
    response_id: str,
    project_id: str,
    feedback_id: str,
    edit_action_id: str,
) -> Event:
    """Record a judgement that links a comment to a change.

    The judgement's state and the evidence behind it are the response row's
    business; the event names the row and the two rows it joins.

    The provisional ``seq``, the transaction and the row are as
    :func:`emit_feedback_recorded` describes them.
    """
    payload = ResponseRecordedPayload(
        response_id=response_id,
        project_id=project_id,
        feedback_id=feedback_id,
        edit_action_id=edit_action_id,
    )
    return work.emit(EventType.RESPONSE_RECORDED, payload=payload.model_dump(mode="json"))


def emit_followup_assessed(
    work: EventWriter,
    *,
    assessment_id: str,
    project_id: str,
    feedback_id: str | None = None,
    issue_key: str | None = None,
) -> Event:
    """Record a later judgement about an issue.

    The assessment is about a comment, about an issue key, or about both.

    The provisional ``seq``, the transaction and the row are as
    :func:`emit_feedback_recorded` describes them.
    """
    payload = FollowupAssessedPayload(
        assessment_id=assessment_id,
        project_id=project_id,
        feedback_id=feedback_id,
        issue_key=issue_key,
    )
    return work.emit(EventType.FOLLOWUP_ASSESSED, payload=payload.model_dump(mode="json"))


__all__ = [
    "EditActionRecordedPayload",
    "EventWriter",
    "FeedbackRecordedPayload",
    "FollowupAssessedPayload",
    "ResponseRecordedPayload",
    "emit_edit_action_recorded",
    "emit_feedback_recorded",
    "emit_followup_assessed",
    "emit_response_recorded",
]
