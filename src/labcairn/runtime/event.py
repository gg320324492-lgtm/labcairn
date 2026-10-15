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

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import Field, model_validator

from labcairn.core.ids import EventId, OperationId, RunId, StageId, TaskId, new_id
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
    {EventType.ARTIFACT_RECORDED, EventType.SOURCE_CHANGED, EventType.OUTBOUND_CONSENT_REQUESTED}
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


class EventTransition(LabCairnModel):
    """The state a change moved *from* and *to*.

    Events without a transition (``artifact_recorded``, ``source_changed``) are
    annotations and must not be used to reconstruct state — which is why the
    fields are required rather than optional when a transition is declared.
    """

    from_state: str = Field(min_length=1, max_length=64)
    to_state: str = Field(min_length=1, max_length=64)


class Event(LabCairnModel):
    """One immutable, append-only fact about a Task."""

    event_id: EventId = Field(default_factory=new_id)
    #: Per-Task, gapless from 1. Allocated inside the same transaction that
    #: writes the rows this event describes. Never a rowid.
    seq: int = Field(ge=1)
    task_id: TaskId
    #: None for Task-level events; required otherwise. See the module docstring.
    run_id: RunId | None = None
    stage_id: StageId | None = None
    operation_id: OperationId | None = None
    type: EventType
    #: Present and required on events that describe a change.
    transition: EventTransition | None = None
    #: Informational only. Never used to order anything.
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _scope_matches_type(self) -> Event:
        if event_requires_run(self.type):
            if self.run_id is None:
                raise ValueError(f"{self.type.value} requires run_id")
        elif self.run_id is not None:
            raise ValueError(f"{self.type.value} is Task-level and must not carry run_id")

        if event_requires_operation_context(self.type):
            if self.stage_id is None or self.operation_id is None:
                raise ValueError(f"{self.type.value} requires both stage_id and operation_id")
        elif self.operation_id is not None:
            raise ValueError(f"{self.type.value} must not carry operation_id")

        if self.type in _TRANSITION_TYPES and self.transition is None:
            raise ValueError(f"{self.type.value} describes a change and requires a transition")
        if self.type not in _TRANSITION_TYPES and self.transition is not None:
            raise ValueError(f"{self.type.value} is an annotation and must not carry a transition")
        return self


class EventStreamRequest(LabCairnModel):
    """A client asking for the tail of one Task's events.

    ``after_seq`` is the resumption mechanism for a client that disconnected
    between commit and receipt (ADR-0003, LC-P1-06 case 3). It is per-Task for
    exactly the reason ``seq`` is.
    """

    task_id: TaskId
    after_seq: int = Field(default=0, ge=0)
    limit: int = Field(default=500, ge=1, le=5000)


class EventStreamPage(LabCairnModel):
    """A page of events plus the cursor to resume from."""

    task_id: TaskId
    events: Annotated[tuple[Event, ...], Field(max_length=5000)]
    #: Resume from here. Equals the last event's ``seq``, or the request's
    #: ``after_seq`` when the page is empty.
    next_after_seq: int = Field(ge=0)
    #: True only when the caller knows there is nothing after this page.
    #: **Defaults to False on purpose.** A caller who forgets to set it must not
    #: tell a client it is caught up when more events may be waiting — the
    #: failure would be a client that silently stops following a Task. Default
    #: False costs at most one extra empty poll.
    caught_up: bool = False

    @property
    def last_seq(self) -> int:
        return self.events[-1].seq if self.events else 0
