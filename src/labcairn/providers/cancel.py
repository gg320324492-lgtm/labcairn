"""Cooperative cancellation and the wall-clock deadline, both fail-closed.

Two distinct mechanisms, deliberately not merged
-----------------------------------------------
``cancel()`` is an **operator's decision** arriving from outside the run.
:meth:`CancellationToken.wait_for` is the **run's own** deadline expiring. They
produce different exceptions (:class:`~labcairn.providers.errors.ProviderCancelledError`
vs :class:`~labcairn.providers.errors.ProviderTimeoutError`) with different retry
semantics, because "the user pressed stop" and "the provider was too slow" are
not the same event and collapsing them is how a cancelled run gets reported as a
network fault.

What cancellation cannot do
---------------------------
Nothing here interrupts a socket read. A token is checked *between* provider
calls — before a request is built, and after one completes — which bounds the
overshoot to one in-flight request. Killing the in-flight HTTP read means
closing the connection, which is the transport's job and is not something a
token can do without owning the transport. The consequence is stated rather than
hidden: **cancel is not immediate while a request is in flight**, and
:attr:`CancellationToken.cancelled` plus the ``ProviderTimeoutError`` path are what
the adapter uses to make the window as small as the HTTP client allows.

The in-flight bound that *does* exist is :meth:`CancellationToken.wait_for`,
because ``asyncio.wait_for`` genuinely cancels the awaiting task. The adapter
uses it for the request timeout, which is why a hung endpoint is bounded even
though a cooperative cancel is not.

Thread safety
-------------
A token is set from the UI thread and read from the event loop's thread. The
:class:`~threading.Lock` is not decoration — CPython's GIL makes a bare
``bool`` assignment atomic, which is exactly the kind of "it works on my
machine" that a reader will later copy into a two-field invariant.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from threading import Lock

from labcairn.providers.errors import ProviderCancelledError, ProviderTimeoutError


class CancellationToken:
    """A one-way flag with a deadline, shared between an operator and a run.

    ``clock`` defaults to :func:`time.monotonic` — deliberately *not*
    ``time.time``. A wall clock can jump backwards under NTP and produce a
    negative deadline, which would make a timeout fire immediately or never.
    """

    __slots__ = ("_cancelled", "_clock", "_deadline", "_lock", "_origin", "_reason")

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        deadline: float | None = None,
    ) -> None:
        self._lock = Lock()
        self._clock = clock
        self._origin = clock()
        self._deadline = deadline
        self._cancelled = False
        self._reason = ""

    @property
    def cancelled(self) -> bool:
        with self._lock:
            return self._cancelled

    @property
    def reason(self) -> str:
        with self._lock:
            return self._reason

    def cancel(self, reason: str = "cancelled by operator") -> None:
        """Request cancellation. Idempotent; the first reason wins.

        First-writer-wins because the second caller is usually the timeout
        unwinding the same path, and overwriting "cancelled by operator" with
        "timeout" would misreport who stopped the run.
        """
        with self._lock:
            if not self._cancelled:
                self._cancelled = True
                self._reason = reason

    def raise_if_cancelled(self) -> None:
        """Check the flag. Called at each await point inside a run."""
        with self._lock:
            cancelled, reason = self._cancelled, self._reason
        if cancelled:
            raise ProviderCancelledError(reason or "cancelled")

    def raise_if_expired(self) -> None:
        """Check the deadline against the injected clock."""
        with self._lock:
            deadline = self._deadline
        if deadline is not None and self._clock() >= deadline:
            raise ProviderTimeoutError(max(0.0, deadline - self._clock()))

    def check(self) -> None:
        """Both checks. The one an adapter calls between steps."""
        self.raise_if_expired()
        self.raise_if_cancelled()

    def wait_for(self, timeout_s: float) -> None:
        """Raise :class:`~labcairn.providers.errors.ProviderTimeoutError` after ``timeout_s``.

        Synchronous and clock-injected, so a test drives it with a fake clock
        instead of sleeping. The adapter's real timeout goes through
        ``asyncio.wait_for`` as well — this is the guard that runs *around* it,
        for a provider whose event loop is not the one this call is on.
        """
        if timeout_s < 0:
            raise ValueError(f"timeout must be non-negative, got {timeout_s!r}")
        if self._clock() - self._origin >= timeout_s:
            raise ProviderTimeoutError(timeout_s)

    def with_deadline_from_now(self, seconds: float) -> CancellationToken:
        """A *new* token sharing this one's clock, anchored at the current reading.

        Returning a new token rather than mutating is what keeps a run's
        per-request deadline from leaking into the next request's budget: the
        wall-clock ceiling in :class:`~labcairn.providers.budget.RunBudget` is
        cumulative, the per-request timeout is not.
        """
        deadline = self._clock() + seconds
        child = CancellationToken(clock=self._clock, deadline=deadline)
        if self.cancelled:
            child.cancel(self.reason)
        return child
