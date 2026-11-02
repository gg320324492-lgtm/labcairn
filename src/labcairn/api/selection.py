"""The selection port: which task the service is bound to.

The service answers about one task, and ``GET /health`` names it. Until this
port existed the binding was fixed when the process started, so the workbench
could show that a workspace held more than one task and could not ask to be
bound to another one. The owner's Phase 2 work order lists that as a carried
limitation, and the limitation's cause is in the acceptance record: *the API
has no such operation*.

The operation is a **selection**, not a write to the store. The workspace's
configuration already says which task is current — ``labcairn task create``
points it at the task it made, and every command without ``--task`` reads it —
so the service switching tasks must change the same pointer, or the two
surfaces would disagree about which task the workspace is looking at. That is
why the port is supplied by the host rather than implemented here: the host is
the thing that holds the workspace's configuration, and this package does not
read or write files.

**Why a port and not an import.** The application layer owns the store, and
this package owns the wire. The selection is neither: it is a fact about the
workspace file, which the CLI's workspace module owns and documents as *"meant
to be imported rather than reimplemented"*. So the host hands the service a
callable, exactly as it hands it an :class:`~labcairn.api.events.EventSource`.

**Why two contexts.** The selector is given the **base** context — the
request-independent one the app holds — and the **request's** context. The
first is what a successful selection returns and what later requests fork
from. The second carries the request's own session, and the selection is
validated on it before anything is persisted: a task id the store does not
hold must be refused without moving the pointer, because a pointer moved to a
task that does not exist would be a workspace whose next command fails.

**The stream is not re-bound.** A stream that is already open keeps reading
the task it was opened for; a selection decides what **subsequent** requests
are about. Saying so here is cheaper than letting a reader assume otherwise.
"""

from __future__ import annotations

from typing import Protocol

from labcairn.application import ApplicationContext
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.core.ids import TaskId


class TaskSelector(Protocol):
    """The host's way to bind the service to another task.

    The callable validates the task through the request's context, persists
    the selection where the other surfaces read it, and returns the context
    the service should use from then on.

    :raises ApplicationRefusedError: the store holds no such task, or the
        workspace cannot bind it. Nothing is persisted in that case.
    """

    def __call__(
        self,
        base: ApplicationContext,
        request_context: ApplicationContext,
        task_id: TaskId,
    ) -> ApplicationContext:
        """Select *task_id*, and return the service's new base context."""
        ...


class UnwiredTaskSelector:
    """The selector used when the host supplied none.

    It refuses in the layer's vocabulary — ``not_implemented`` — rather than
    reporting success or silently keeping the old binding. A service that
    answered "selected" and stayed on the old task would be a service lying
    about what it is bound to, which is the failure mode this port exists to
    make impossible.
    """

    def __call__(
        self,
        base: ApplicationContext,
        request_context: ApplicationContext,
        task_id: TaskId,
    ) -> ApplicationContext:
        """Refuse, and say which piece is missing.

        :raises ApplicationRefusedError: always.
        """
        del base, request_context, task_id
        raise ApplicationRefusedError(
            ApplicationRefusal.NOT_IMPLEMENTED,
            "the service was not given a way to select a task, so it stays "
            "bound to the task it was started with. The selection belongs to "
            "the workspace's configuration, which only the host that started "
            "the service can read and write; a service that answered this "
            "request without moving that pointer would be a service that "
            "said it had switched and had not.",
        )


__all__ = ["TaskSelector", "UnwiredTaskSelector"]
