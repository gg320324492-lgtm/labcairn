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

**The judgement's word is carried; its authority is not.** ADR-0017 D8 says
*"the events are not the links... the events say that the chain happened"* —
the chain's substance is not the payload's business. But the **word** the
row used is: a response's state, an edit's actor, an assessment's verdict.
Carrying it means a reader replaying the stream sees what was judged without
a second query, and it puts the claim inside the report's hash chain rather
than outside it — which is the difference between a chain that proves the
bookkeeping and one that proves the judgement.

**The vocabulary is the row's, and this module checks nothing against it**
— with one exception, and the exception is the point. A payload that refused
a word the table does not have would couple the runtime layer to a table
that does not exist yet, and the layer must not import the store's layer. So
the words are carried verbatim, and a reader who wants the row's own value
reads the row; the two are the same string unless something changed one of
them, which is exactly what a reader comparing them would want to see.

**The exception is ``pending``**, and it is refused because it would make
the event a lie: a ``response_recorded`` event is emitted **only when a
judgement was made**, and a response whose state is ``pending`` is **not**
an event. A comment nobody has answered has no response row at all — "no
row" is how "unanswered" is represented — so an event carrying ``pending``
would say that a response was recorded when the truth is that nothing was
judged. See
:meth:`ResponseRecordedPayload._a_pending_response_is_not_a_judgement`.

**The three judgements are required, and there is no default for any of
them.** An edit has an actor (ADR-0017 D4: no default actor — a default is
exactly how a model's change becomes the advisor's); a response that is
recorded has a judgement; and an assessment that says *"not established"* has
a verdict, which is a verdict and not an absence. So a call site that
forgets is a construction failure and not a ``null`` in the chain.

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

from pydantic import Field, model_validator

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
    #: **Who made the change, as the row's own word** — ``student``,
    #: ``advisor``, ``model`` or ``human``, whatever the row says.
    #:
    #: The word is carried so that a reader replaying the stream sees the
    #: substance and not only the bookkeeping, and so that the chain carries
    #: what ADR-0017 D4 calls the whole point of the table: a change made by
    #: a model and recorded as somebody else's is a forged signature, and the
    #: column that makes one impossible to write by accident is the one the
    #: chain has to cover. The vocabulary is the row's, and this module checks
    #: nothing against it — a payload that refused a word the table does not
    #: have would couple the runtime layer to a table that does not exist
    #: yet. So the word is copied verbatim, and a reader who wants the row's
    #: own value reads the row; the two are the same string unless something
    #: changed one of them, which is exactly what a reader comparing them
    #: would want to see.
    #:
    #: **Required, and there is no default actor.** ADR-0017 D4: a row names
    #: who made the change, and *there is no default* — a default is exactly
    #: how a model's change becomes the advisor's. A payload that let the
    #: word be omitted would put the same hole in the chain.
    actor_kind: str = Field(min_length=1)


class ResponseRecordedPayload(LabCairnModel):
    """What a ``response_recorded`` event says.

    A judgement that links a comment to a change. The event names the two
    rows the link joins, which is what makes the chain traversable from the
    stream: the comment, the change, and the response that connects them.

    **The state is the row's word, carried verbatim.** ADR-0017 D5's states
    are the hardest clause of the work order — an unaddressed comment must
    not be reported as addressed — and the rule that decides them lives in
    the row and in the evidence behind it. What the chain carries is the
    **word the row used**, not the authority behind it: the evidence and the
    decision stay in the row, and this module checks the word against
    nothing, because a closed vocabulary that lives in a table this layer
    must not know would be a second vocabulary to keep in step.

    **And a response whose state is ``pending`` is not an event.** A
    ``response_recorded`` event is emitted **only when a judgement was
    made**. ``pending`` is the state a row holds when nobody has judged
    anything yet, and a comment nobody has answered has **no response row
    at all** — "no row" is how "unanswered" is represented. So a response
    event whose state is ``pending`` would say the opposite of what it
    means, and this model refuses it. See
    :meth:`_a_pending_response_is_not_a_judgement`.
    """

    #: The row this event is about.
    response_link_id: str = Field(min_length=1)
    #: The project the chain belongs to.
    project_id: str = Field(min_length=1)
    #: The comment the response is about.
    feedback_id: str = Field(min_length=1)
    #: The change the response judges.
    edit_action_id: str = Field(min_length=1)
    #: **The judgement, as the row's own word** — ``addressed``,
    #: ``partially_addressed`` or ``not_addressed``, whatever the row says.
    #: **Not** ``pending``: see the class docstring and
    #: :meth:`_a_pending_response_is_not_a_judgement`.
    #:
    #: Carried so that a reader replaying the stream sees what was judged
    #: without a second query: "a response was recorded" says that something
    #: happened, and this says what was concluded. The vocabulary is the
    #: row's — the payload copies the word and checks nothing against it,
    #: because a payload that refused a state the table does not have would
    #: couple the runtime layer to a table that does not exist yet. A reader
    #: who wants the row's own value reads the row; the two are the same
    #: string unless something changed one of them, which is exactly what a
    #: reader comparing them would want to see.
    #:
    #: **Required**, because a response event is for a judgement that was
    #: made, and a judgement with no word is not a judgement.
    state: str = Field(min_length=1)

    @model_validator(mode="after")
    def _a_pending_response_is_not_a_judgement(self) -> ResponseRecordedPayload:
        """A response whose state is ``pending`` is not an event.

        **The rule:** a ``response_recorded`` event is emitted **only when a
        judgement was made**, and a response whose state is ``pending`` is
        **not** an event.

        Why: ``pending`` is the state a response row holds when nobody has
        judged anything yet, and a comment nobody has answered has no
        response row at all — "no row" is how "unanswered" is represented.
        An event that carried ``pending`` would say that a response was
        recorded when the truth is that nothing was judged.

        **This is the one word of the response vocabulary the runtime layer
        knows**, and it knows it because it is the one that would make the
        event a lie. Every other word is the row's own and is carried
        verbatim, unchecked. The comparison is case-insensitive, so a
        differently spelled ``Pending`` is refused too: it is not a state the
        row's vocabulary has, and the layer does not know which other words
        are states.
        """
        if self.state.strip().casefold() == "pending":
            raise ValueError(
                "a response_recorded event is emitted only when a judgement was "
                "made, and a state of 'pending' means nobody has judged "
                "anything yet: a comment nobody has answered has no response "
                "row at all, and 'no row' is how 'unanswered' is represented"
            )
        return self


class FollowupAssessedPayload(LabCairnModel):
    """What a ``followup_assessed`` event says.

    A later judgement about an issue. ADR-0017 D7 gives an assessment two
    subjects — a comment or an issue key — and both are carried, because the
    issue key is what makes a recurrence visible: two comments with one key
    in different rounds are one recurring issue and not two unrelated
    comments.

    **The verdict is the row's word, carried verbatim.** ADR-0017 D7's hard
    line lives in the row — an assessment must carry its own evidence and be
    able to say *"not established"* — and that evidence stays there. What the
    chain carries is the **word the row used**, so that a reader replaying
    the stream can see what was concluded without a second query.
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
    #: **The verdict, as the row's own word** — including, when the row says
    #: so, *"not established"*.
    #:
    #: The vocabulary is the row's, and this module checks nothing against
    #: it: a payload that refused a verdict the table does not have would
    #: couple the runtime layer to a table that does not exist yet. So the
    #: word is copied verbatim, and a reader who wants the row's own value
    #: reads the row; the two are the same string unless something changed
    #: one of them, which is exactly what a reader comparing them would want
    #: to see. The word alone is not the assessment's authority — that is the
    #: evidence, which lives in the row and not here.
    #:
    #: **Required**, because *"not established"* is a verdict and not an
    #: absence: an assessment that concluded nothing has no verdict to carry,
    #: and one that says it concluded nothing has to say so in words.
    verdict: str = Field(min_length=1)


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
    actor_kind: str,
    feedback_id: str | None = None,
) -> Event:
    """Record a change made against a version edge.

    *feedback_id* is the comment the change answers, and ``None`` when it
    answers none — which ADR-0017 D4 says is not an error but a fact.

    *actor_kind* is **who made the change**, as the row's own word. It is the
    chain's copy of the thing ADR-0017 D4 calls the whole point of the
    table: a change made by a model and recorded as somebody else's is a
    forged signature, and the chain has to cover it and not only the row.
    Pass the row's word; this module checks nothing against it.

    **Required, and there is no default actor.** A change has an actor, and
    ADR-0017 D4 refuses to give it one: a default is exactly how a model's
    change becomes the advisor's.

    The provisional ``seq``, the transaction and the row are as
    :func:`emit_feedback_recorded` describes them.
    """
    payload = EditActionRecordedPayload(
        edit_action_id=edit_action_id,
        project_id=project_id,
        version_edge_id=version_edge_id,
        feedback_id=feedback_id,
        actor_kind=actor_kind,
    )
    return work.emit(EventType.EDIT_ACTION_RECORDED, payload=payload.model_dump(mode="json"))


def emit_response_recorded(
    work: EventWriter,
    *,
    response_link_id: str,
    project_id: str,
    feedback_id: str,
    edit_action_id: str,
    state: str,
) -> Event:
    """Record a judgement that links a comment to a change.

    *state* is **what was judged**, as the row's own word. The event names
    the row and the two rows it joins, and this says what was concluded —
    so that a reader replaying the stream sees the judgement and not only
    that a judgement happened. The evidence behind the state, and the rule
    that decides it, stay in the row.

    **Required, and ``pending`` is not one of the answers.** A
    ``response_recorded`` event is emitted **only when a judgement was
    made**. A response whose state is ``pending`` means nobody has judged
    anything yet, and a comment nobody has answered has no response row at
    all — "no row" is how "unanswered" is represented. Passing ``pending``
    here is refused at construction; see
    :meth:`ResponseRecordedPayload._a_pending_response_is_not_a_judgement`.

    The provisional ``seq``, the transaction and the row are as
    :func:`emit_feedback_recorded` describes them.
    """
    payload = ResponseRecordedPayload(
        response_link_id=response_link_id,
        project_id=project_id,
        feedback_id=feedback_id,
        edit_action_id=edit_action_id,
        state=state,
    )
    return work.emit(EventType.RESPONSE_RECORDED, payload=payload.model_dump(mode="json"))


def emit_followup_assessed(
    work: EventWriter,
    *,
    assessment_id: str,
    project_id: str,
    verdict: str,
    feedback_id: str | None = None,
    issue_key: str | None = None,
) -> Event:
    """Record a later judgement about an issue.

    The assessment is about a comment, about an issue key, or about both.

    *verdict* is **what was concluded**, as the row's own word — including,
    when the row says so, *"not established"*. The assessment's evidence, and
    the refusal that keeps "the change was accepted" out of the verdict, are
    the row's business.

    **Required, because *"not established"* is a verdict and not an
    absence.** An assessment that concluded nothing has no verdict to carry,
    and one that says it concluded nothing has to say so in words.

    The provisional ``seq``, the transaction and the row are as
    :func:`emit_feedback_recorded` describes them.
    """
    payload = FollowupAssessedPayload(
        assessment_id=assessment_id,
        project_id=project_id,
        feedback_id=feedback_id,
        issue_key=issue_key,
        verdict=verdict,
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
