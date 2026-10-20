"""The event stream: events, and only events.

``docs/plans/LC-P1-11-12-task-breakdown.md`` §2.6's third point is the
stream, and the plan's T07 cost note says why its shape is not negotiable:
*"the event stream is a long-lived request, and a browser that reconnects must
not replay operations — which is why the stream carries **events** (facts about
what happened) and never commands."*

So the contract here is the runtime's own: :class:`~labcairn.runtime.event.EventStreamRequest`
in, :class:`~labcairn.runtime.event.EventStreamPage` out. The page is a list of
:class:`~labcairn.runtime.event.Event` — sealed contracts with a ``seq``, a
``type``, a ``transition`` and a ``payload`` — and a cursor to resume from.
There is no field anywhere in it that could hold a command, because an
``Event`` is a statement about what happened and the runtime's vocabulary of
those is closed.

Why the source is a port
------------------------

The stream reads the task's event log, and the event log lives in the store.
This package does not read the store, and that is a rule rather than an
accident: ``tests/test_application_layer.py`` asserts that the application
layer is the only way to the store, and a module of this package that
imported the store's readers would fail that test.

The application layer is the layer that should own the read — it owns every
other read of the task's rows — but its operation list is T05's and is frozen,
and it has no operation that returns events. So the read is a **port**:
:class:`EventSource` says what the stream needs, and the host that starts the
service supplies the thing that answers it. When nothing is supplied, the
stream says so in the layer's own refusal vocabulary rather than pretending
to be empty: a stream that returned no events because it was not wired to
anything would be a service that looked alive and was not.

The port's contract is the runtime's, not this package's, so the thing that
implements it is small: read the events after a cursor, and say whether the
caller is caught up.

**The source is handed the session to read on, and holds none.** A
SQLAlchemy ``Session`` is not thread-safe, and the service serves several
requests at once; a source that held one would be a session shared by every
request that read the stream, which is the defect the service's per-request
sessions exist to remove. So the caller owns the session, passes it in, and
closes it when the read is over — and the source is left with nothing to
share.
"""

from __future__ import annotations

from typing import Protocol

from sqlalchemy.orm import Session

from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.runtime.event import EventStreamPage, EventStreamRequest


class EventSource(Protocol):
    """Where the event stream reads its events from.

    One method, and the method is the runtime's own request and the runtime's
    own page. An implementation that had to translate would be a second
    spelling of the cursor.

    **The session is an argument, and the source keeps none.** The caller
    opens one per request and closes it when the request is over, so two
    readers of the stream never share a session and neither can discard the
    other's work.
    """

    def page(self, session: Session, request: EventStreamRequest) -> EventStreamPage:
        """The events after the request's cursor, read on *session*."""
        ...


class UnwiredEventSource:
    """The source used when the host supplied none.

    It refuses in the layer's vocabulary — ``not_implemented`` — because that
    is what it is: the operation is declared and the piece it is built on is
    not in this build. It does **not** return an empty page, because an empty
    page says "the task has no events", and a task that has events and a
    stream that cannot see them would be a service quietly lying about the
    state of the work.
    """

    def page(self, session: Session, request: EventStreamRequest) -> EventStreamPage:
        """Refuse, and say which piece is missing.

        :raises ApplicationRefusedError: always.
        """
        del session, request
        raise ApplicationRefusedError(
            ApplicationRefusal.NOT_IMPLEMENTED,
            "the event stream was not given a source to read from. The service "
            "answers the request for an event page with this refusal rather than "
            "an empty page, because an empty page would say the task has no events "
            "and a task that has events and a stream that cannot see them is a "
            "service lying about the state of the work. The source belongs to the "
            "application layer, which owns every other read of the task's rows.",
        )


def sse_frame(page: EventStreamPage) -> str:
    """A page as one server-sent event.

    The page is serialised by the model that defines it, so the frame carries
    the same bytes the JSON endpoint would, and a client that reconnects reads
    the same cursor either way.
    """
    return f"data: {page.model_dump_json()}\n\n"


__all__ = ["EventSource", "UnwiredEventSource", "sse_frame"]
