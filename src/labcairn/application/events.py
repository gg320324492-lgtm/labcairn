"""The task's event log: the tail of it, and the cursor that resumes it.

An event is a fact about what happened, and the log is where the facts live:
the runs, the stages and the artefacts are all derived from it. So a surface
that follows a task reads the log, and the read is made here — a surface that
read the log itself would be a surface that could read it without the
policy's verdict.

The page carries the cursor
---------------------------

A client that follows a task has to say where it stopped, and the answer has
to travel with the events it stopped after. A client that had to work the
cursor out for itself would have to tell "nothing happened" from "you are
past the end", and those two are different answers to different questions.

The events are the store's events
---------------------------------

The page carries the :class:`~labcairn.runtime.event.Event` objects **by value
and by type**. An event is a fact about what happened, and a copy of it in a
shape of the layer's own would be a second spelling of a fact the store has
already spelled once: two spellings of one event, and a client that compared
them would be comparing a fact with a copy of it.

The store's readers read the log afresh on every call, so the objects a caller
holds and the ones the page holds are never the same objects even when they
are the same events. Identity is therefore not a property the layer could
satisfy, and it is not the property; the one that matters is that the layer
does not re-shape the event.

A task that does not exist is not a task with no events
--------------------------------------------------------

The store's event readers answer an empty page for a task id that was never
created. The layer does not pass that on, because the store states the rule
for every other task-scoped read it owns — a task that does not exist is not
an empty list — and a client that cannot tell the two apart reports "no
events" for a task id it mistyped. So the read establishes that the task is
there before it reads its log.
"""

from __future__ import annotations

from labcairn.application import consent
from labcairn.application.context import ApplicationContext, store_refusals
from labcairn.application.models import Result
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.db.repository import events_after as store_events_after
from labcairn.db.repository import last_seq as store_last_seq
from labcairn.db.repository import load_task
from labcairn.runtime.event import Event
from labcairn.security.capabilities import CapabilityId

#: How many events a page holds when the caller does not say.
#:
#: The store's own default, which is also the runtime's event stream
#: request's default. The layer does not invent a number here: a page that
#: is a different length on each side of the seam is a page the client
#: cannot predict.
DEFAULT_EVENT_LIMIT = 500

#: The shortest page this operation will serve.
#:
#: A page of none would return no events and never advance the cursor, so a
#: client that asked for one would poll the same cursor for ever.
MIN_EVENT_LIMIT = 1

#: The longest page this operation will serve.
#:
#: The runtime's own event stream request
#: (:class:`~labcairn.runtime.event.EventStreamRequest`) caps a page at five
#: thousand events, and the layer applies the same bound: the layer's read is
#: that request applied to the task the context is about, so the two cannot
#: disagree about how long a page may be.
MAX_EVENT_LIMIT = 5000


class EventPage(Result):
    """A page of a task's events, and where to resume from.

    ``next_after_seq`` is the cursor the next read starts from, and
    ``last_seq`` is the task's own counter — the ``seq`` of its newest event.
    A client that has read the whole log has reached ``last_seq``; a client
    that has not can see how far behind it is.
    """

    events: tuple[Event, ...]
    next_after_seq: int
    last_seq: int

    @property
    def caught_up(self) -> bool:
        """Whether the page reached the end of the log.

        Derived from the two numbers beside it rather than carried beside
        them, so it cannot disagree with them.
        """
        return self.next_after_seq >= self.last_seq


def read_events(
    context: ApplicationContext,
    *,
    after_seq: int = 0,
    limit: int = DEFAULT_EVENT_LIMIT,
) -> EventPage:
    """The task's events after *after_seq*, at most *limit* of them.

    *after_seq* is the cursor the caller last saw, and the page holds the
    events that came after it. The cursor itself is excluded, because a
    client that resumed from the last event it had seen would be sent that
    event again.

    *limit* bounds the page, and the store applies it by dropping the events
    beyond it. A task with more events than the limit is therefore read in
    more than one call, and the page says where the last one stopped.

    :raises ApplicationRefusedError: the request is not one this operation
        can apply, the policy denied reading the task's area, or the store
        holds no task with that id.
    """
    _refuse_unusable_request(after_seq=after_seq, limit=limit)
    area = context.task_area()
    consent.evaluate(
        context,
        capability=CapabilityId.FS_READ,
        arguments={"path": area.declared_key},
        resource=area,
    )
    with store_refusals():
        # The task has to be there: the store's event readers would answer an
        # empty page for a task id that was never created.
        task = load_task(context.store.session, context.task_id)
        events = store_events_after(
            context.store.session, task.task_id, after_seq=after_seq, limit=limit
        )
        counter = store_last_seq(context.store.session, task.task_id)
    return EventPage(
        events=events,
        next_after_seq=events[-1].seq if events else counter,
        last_seq=counter,
    )


def _refuse_unusable_request(*, after_seq: int, limit: int) -> None:
    """Refuse a request this operation cannot apply.

    The bounds are the runtime's own event stream request's bounds: a cursor
    is a non-negative integer, and a page is one to five thousand events
    long. The layer has no bound of its own, so the layer and the request
    the API builds cannot disagree about what a page is.

    A negative limit is *no limit* to the store — SQLite reads ``LIMIT -1``
    as unbounded — so a caller asking for a limit of -1 would be handed the
    whole log under a name that says otherwise. A cursor below zero would
    be handed the whole log too, since every event's ``seq`` is above it.

    :raises ApplicationRefusedError: the request is not one this operation
        can apply.
    """
    if after_seq < 0:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the cursor {after_seq} is not a position in the log: an event's "
            "seq is one or more, so a cursor below zero names the whole log "
            "rather than a place to resume from.",
        )
    if limit < MIN_EVENT_LIMIT or limit > MAX_EVENT_LIMIT:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the page length {limit} is not a page: a page is "
            f"{MIN_EVENT_LIMIT} to {MAX_EVENT_LIMIT} events long. A page of "
            "none would never advance the cursor, and a page of everything "
            "is not a page.",
        )


__all__ = [
    "DEFAULT_EVENT_LIMIT",
    "MAX_EVENT_LIMIT",
    "MIN_EVENT_LIMIT",
    "EventPage",
    "read_events",
]
