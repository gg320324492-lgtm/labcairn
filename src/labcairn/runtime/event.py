"""The event envelope — the record everything else is derived from.

Two decisions here were corrections rather than design, and both are load
bearing:

**``run_id`` is nullable.** An earlier contract said "always non-null", seven
lines above an enum containing ``task_created`` — which by definition precedes
the first Run. Those events were uninsertable. ``run_id`` is therefore required
only for ``run.*``, ``stage.*``, ``operation.*``, ``approval.*`` and
``checkpoint.*`` events, and validation happens per event type rather than per
column.

**``seq`` is per-Task and is not the rowid.** In SQLite an ``INTEGER PRIMARY
KEY`` is the rowid, unique table-wide, so its values are distributed across
Tasks rather than restarted per Task: Task A would hold 1, 2, 5 while Task B
held 3, 4. No client resuming with ``after_seq=<last_seen>`` can reason about
one Task's contiguous tail. Per-Task gaplessness needs a plain counter
allocated under the Task's own row inside the same transaction.

``occurred_at`` is informational only and must never be used to order anything:
wall-clock is not monotonic, and a resumed process can emit a timestamp earlier
than one already recorded.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import Field, model_validator

from labcairn.core.ids import EventId, OperationId, RunId, StageId, TaskId, new_id
from labcairn.core.primitives import StrictNonNegInt, StrictPosInt
from labcairn.core.schema import LabCairnModel


class EventType(StrEnum):
    """The closed vocabulary. An unknown value is rejected, never coerced.

    Closing the set is the point: an event type this build has never heard of
    means a newer writer produced it, and silently dropping it would lose
    provenance without anyone noticing.
    """

    TASK_CREATED = "task_created"
    TASK_REVISED = "task_revised"

    RUN_STARTED = "run_started"
    RUN_PAUSED = "run_paused"
    RUN_RESUMED = "run_resumed"
    RUN_FINISHED = "run_finished"

    STAGE_ENTERED = "stage_entered"
    STAGE_COMPLETED = "stage_completed"
    STAGE_BLOCKED = "stage_blocked"

    OPERATION_INTENT = "operation_intent"
    OPERATION_AWAITING_APPROVAL = "operation_awaiting_approval"
    OPERATION_ATTEMPTED = "operation_attempted"
    OPERATION_CONFIRMED = "operation_confirmed"
    OPERATION_FAILED = "operation_failed"
    OPERATION_UNCERTAIN = "operation_uncertain"
    OPERATION_RECONCILED = "operation_reconciled"

    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    APPROVAL_EXPIRED = "approval_expired"
    APPROVAL_CONSUMED = "approval_consumed"

    CHECKPOINT_CREATED = "checkpoint_created"
    ARTIFACT_RECORDED = "artifact_recorded"
    SOURCE_CHANGED = "source_changed"
    OUTBOUND_CONSENT_REQUESTED = "outbound_consent_requested"

    # LC-P2-09, ADR-0017 D8: the four events of the feedback chain — a
    # comment, an edit, a judgement and an assessment. They are annotations
    # and not attempts: a comment found in a manuscript did not happen inside
    # a Run, so these carry no transition and no ``run_id``.
    FEEDBACK_RECORDED = "feedback_recorded"
    EDIT_ACTION_RECORDED = "edit_action_recorded"
    RESPONSE_RECORDED = "response_recorded"
    FOLLOWUP_ASSESSED = "followup_assessed"

    # LC-P2-01, ADR-0016 C8: one model call, recorded. An exchange is an
    # annotation and not an attempt — it says what was asked, what came
    # back, and under which consent, and it carries no transition.
    MODEL_EXCHANGED = "model_exchanged"


#: Event types that carry neither run_id nor the operation context.
TASK_LEVEL_EVENTS: frozenset[EventType] = frozenset(
    {EventType.TASK_CREATED, EventType.TASK_REVISED}
)

#: The five families that belong to a Run, per ADR-0003 C1. Prefixes are
#: underscore-separated because the enum *values* are; ADR prose writes them
#: with dots. Getting this wrong twice is what prompted
#: :func:`_run_scoped_prefixes_are_matched_against_real_values`.
RUN_SCOPED_PREFIXES: tuple[str, ...] = (
    "run_",
    "stage_",
    "operation_",
    "approval_",
    "checkpoint_",
)

#: Events that are neither Task-level nor Run-scoped: annotations about the
#: Task's material and products, which may be observed outside any attempt.
ANNOTATION_EVENTS: frozenset[EventType] = frozenset(
    {
        EventType.ARTIFACT_RECORDED,
        EventType.SOURCE_CHANGED,
        EventType.OUTBOUND_CONSENT_REQUESTED,
        # ADR-0017 D8: the feedback chain's four events. A comment, an edit,
        # a response and an assessment are observations about the manuscript,
        # not attempts to do something to it.
        EventType.FEEDBACK_RECORDED,
        # LC-P2-01: the model-call path's exchange record. A call that
        # happened is a fact about the task, whatever the attempt around it.
        EventType.MODEL_EXCHANGED,
        EventType.EDIT_ACTION_RECORDED,
        EventType.RESPONSE_RECORDED,
        EventType.FOLLOWUP_ASSESSED,
    }
)

#: Events that describe a change and therefore must carry from/to state.
_TRANSITION_TYPES: frozenset[EventType] = frozenset(
    t for t in EventType if t.name.startswith(("RUN_", "STAGE_", "OPERATION_", "APPROVAL_"))
)


def event_requires_run(type_: EventType) -> bool:
    """Whether *type_* must name the Run it happened in.

    True for exactly the five families ADR-0003 names, and False for Task-level
    events *and* for annotations such as ``artifact_recorded`` — which describe
    the Task's material rather than an attempt. Defining this as "everything
    except Task-level" wrongly required a Run of an annotation.
    """
    return type_.value.startswith(RUN_SCOPED_PREFIXES)


def event_requires_operation_context(type_: EventType) -> bool:
    """Whether *type_* must name both the Stage and the Operation.

    ``operation_*`` events are the only ones where both are required: the
    attempt, the outcome and the uncertainty all belong to one operation
    inside one stage.

    The prefix is underscore-separated because the enum *values* are
    (``operation_confirmed``). An earlier draft matched ``"operation."`` — the
    shorthand ADR-0003 uses in prose — which never matched anything, so
    operation events were neither required to carry their context nor allowed
    to. The test that caught it asserted both directions.
    """
    return type_.value.startswith("operation_")


#: Per-type payload schemas, empty until an event type has content to carry.
#:
#: ADR-0003 C1 lists a ``payload`` column "validated against the type's Pydantic
#: model". Writing 25 models up front would be 25 empty classes; instead a type
#: gets a schema when some work order has content for it, and this table is the
#: only place that knows which types carry content.
#:
#: The rule that makes this safe is in :class:`Event`: a type with **no**
#: registered schema must carry an **empty** payload. Without it ``payload``
#: becomes a free-form bag, which is the state ``extra="forbid"`` exists to
#: prevent, reintroduced through the back door.
EVENT_PAYLOAD_SCHEMAS: dict[EventType, type[LabCairnModel]] = {}


def register_payload_schema(event_type: EventType, schema: type[LabCairnModel]) -> None:
    """Declare the model an event type's payload must satisfy.

    Kept as a function rather than a dict literal so the registration site is
    greppable and so a duplicate registration is an error rather than a silent
    overwrite.

    **Registration must reach the reader, and the reader imports this module
    and little else.** :func:`~labcairn.db.repository.events_after` validates
    every stored document through :class:`Event`; it does not import the
    writer. A schema registered as a side effect of importing a writer is
    therefore absent in a process that only reads, and every event of that
    type becomes unreadable there while remaining valid in the writer's own
    process — a defect no write-path test can see. The payload models for the
    vocabulary live here for that reason; a schema may be registered elsewhere
    only if this module (or something it already imports) imports that module.

    **And the package counts as something this module imports.** ADR-0017 D8's
    four chain events put their payload models in
    :mod:`labcairn.runtime.trajectory`, because that file is the trajectory's
    and this one is the vocabulary's. Importing a module of a package imports
    the package first, so :mod:`labcairn.runtime`'s own ``__init__`` pulls the
    trajectory in — and every process that reads an event, this one included,
    has the four schemas registered before it validates anything. The
    alternative would be a schema that exists only where the writer was
    imported, which is the defect this paragraph exists to prevent.
    """
    if event_type in EVENT_PAYLOAD_SCHEMAS:
        raise ValueError(f"{event_type.value} already has a registered payload schema")
    EVENT_PAYLOAD_SCHEMAS[event_type] = schema


class EventTransition(LabCairnModel):
    """The state a change moved *from* and *to*.

    Events without a transition (``artifact_recorded``, ``source_changed``) are
    annotations and must not be used to reconstruct state — which is why the
    fields are required rather than optional when a transition is declared.
    """

    from_state: str = Field(min_length=1, max_length=64)
    to_state: str = Field(min_length=1, max_length=64)


class ReconciliationPayload(LabCairnModel):
    """What an ``operation_reconciled`` event carries beyond its transition.

    ADR-0007 added the ``payload`` field the event contract always specified.
    Before it, ``confirmed_by_probe`` was **re-derivable but not stored**: the
    resolution had to be inferred from the fact that an operation reached
    ``CONFIRMED`` while carrying ``operation_reconciled`` and no receipt, which
    is sound only for as long as C2's vocabulary has exactly those two paths. A
    reader should not have to reconstruct provenance the log could simply state.

    It lives here rather than beside the coordinator that writes it because
    the reader imports the vocabulary and not the writer; see
    :func:`register_payload_schema`.
    """

    #: The C2 vocabulary word for how this was resolved.
    resolution: str = Field(min_length=1)
    #: What the probe actually observed, so a human can judge the answer rather
    #: than only the conclusion.
    verdict: str = Field(min_length=1)
    #: Which mechanism reached it. ``probe`` means bytes were read; a future
    #: ``policy`` would mean a human decided. Recording the source separately
    #: from the resolution keeps "what was concluded" and "on what basis"
    #: distinguishable, which is the distinction ADR-0004's evidence states exist
    #: for.
    reached_by: str = Field(min_length=1)


register_payload_schema(EventType.OPERATION_RECONCILED, ReconciliationPayload)


class Event(LabCairnModel):
    """One immutable, append-only fact about a Task."""

    event_id: EventId = Field(default_factory=lambda: EventId(new_id()))
    #: Per-Task, gapless from 1. Allocated inside the same transaction that
    #: writes the rows this event describes. Never a rowid.
    #: Per-Task, gapless from 1. Strictly parsed: ADR-0003 calls this
    #: "the only order", and lax coercion would let a value the caller never
    #: wrote become the order of an event log.
    seq: StrictPosInt
    task_id: TaskId
    #: None for Task-level events; required otherwise. See the module docstring.
    run_id: RunId | None = None
    stage_id: StageId | None = None
    operation_id: OperationId | None = None
    type: EventType
    #: Present and required on events that describe a change.
    transition: EventTransition | None = None
    #: Type-specific content. Empty for every type that has no registered
    #: schema, which is enforced below rather than assumed.
    payload: Mapping[str, object] = Field(default_factory=dict)
    #: Informational only. Never used to order anything.
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _scope_matches_type(self) -> Event:
        if event_requires_run(self.type):
            if self.run_id is None:
                raise ValueError(f"{self.type.value} requires run_id")
        elif self.run_id is not None:
            # Three distinct reasons a type may not carry a run_id, and they
            # are not interchangeable. Calling an annotation "Task-level" was
            # wrong: it is neither Task-level nor Run-scoped, and a reader
            # chasing the message would look in the wrong place.
            kind = "Task-level" if self.type in TASK_LEVEL_EVENTS else "an annotation"
            raise ValueError(f"{self.type.value} is {kind} and must not carry run_id")

        if event_requires_operation_context(self.type):
            if self.stage_id is None or self.operation_id is None:
                raise ValueError(f"{self.type.value} requires both stage_id and operation_id")
        elif self.operation_id is not None:
            raise ValueError(f"{self.type.value} must not carry operation_id")

        if self.type in _TRANSITION_TYPES and self.transition is None:
            raise ValueError(f"{self.type.value} describes a change and requires a transition")
        if self.type not in _TRANSITION_TYPES and self.transition is not None:
            raise ValueError(f"{self.type.value} is an annotation and must not carry a transition")

        schema = EVENT_PAYLOAD_SCHEMAS.get(self.type)
        if schema is None:
            # The anti-bag rule. A type with no declared content must carry none,
            # or ``payload`` is a hole in ``extra="forbid"``.
            if self.payload:
                raise ValueError(
                    f"{self.type.value} has no registered payload schema, so its "
                    f"payload must be empty; got {sorted(self.payload)}. Register a "
                    f"schema with register_payload_schema() if this content is real."
                )
        else:
            schema.model_validate(dict(self.payload))
        return self


class EventStreamRequest(LabCairnModel):
    """A client asking for the tail of one Task's events.

    ``after_seq`` is the resumption mechanism for a client that disconnected
    between commit and receipt (ADR-0003, LC-P1-06 case 3). It is per-Task for
    exactly the reason ``seq`` is.
    """

    task_id: TaskId
    after_seq: StrictNonNegInt = 0
    limit: Annotated[int, Field(strict=True, ge=1, le=5000)] = 500


class EventStreamPage(LabCairnModel):
    """A page of events plus the cursor to resume from."""

    task_id: TaskId
    events: Annotated[tuple[Event, ...], Field(max_length=5000)]
    #: Resume from here. Equals the last event's ``seq``, or the request's
    #: ``after_seq`` when the page is empty.
    next_after_seq: StrictNonNegInt
    #: True only when the caller knows there is nothing after this page.
    #: **Defaults to False on purpose.** A caller who forgets to set it must not
    #: tell a client it is caught up when more events may be waiting — the
    #: failure would be a client that silently stops following a Task. Default
    #: False costs at most one extra empty poll.
    caught_up: bool = False

    @property
    def last_seq(self) -> int:
        return self.events[-1].seq if self.events else 0
