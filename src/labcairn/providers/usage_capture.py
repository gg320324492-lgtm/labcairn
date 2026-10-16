"""Recovering the usage block before the framework flattens it to zeros.

The information loss, measured
-------------------------------
pydantic-ai at ``1.107.7`` types every token counter as a plain ``int``::

    # pydantic_ai/usage.py
    Usage.input_tokens      int
    Usage.output_tokens     int
    Usage.requests          int
    RequestUsage.input_tokens  int

and its own regression test pins it there::

    # tests/test_usage_limits.py:1166
    test_usage_limits_explicit_zero
    "regression: zero is not coerced to None"

ADR-0002 §A1 records the consequence with the test that demonstrates it::

    # tests/test_usage_limits.py:1162
    test_usage_unknown_provider
    assert RequestUsage.extract({}, ...) == RequestUsage()  # every counter zero

So by the time a response reaches LabCairn through ``ModelResponse.usage``, the
difference between *"the provider said this cost zero"* and *"the provider said
nothing"* **does not exist in the type**. There is no application-side
correction available: ADR-0005's consequence 1 is exactly this — *"a framework
that defaults a missing number to 0 cannot be corrected by the application
afterwards, because by then the zero has been compared, summed and budgeted."*

The way out
-----------
Not by replacing the framework (ADR-0005 keeps Pydantic AI as the interaction
layer) but by reading the raw response body on the way past, before the
extraction step that loses the distinction. That is all this module is: an httpx
transport wrapper that keeps the ``usage`` sub-object of the last response
verbatim, and a two-method protocol the adapter consumes.

Design points that matter
-------------------------
**No new parsing logic.** :meth:`UsageCapture.report` feeds the captured block to
:meth:`~labcairn.core.providers.protocol.UsageReport.from_wire`, which LC-P1-01
already wrote with the four rows of the contrast table in mind (absent → Unknown,
``{}`` → Unknown, ``{"input_tokens": 0}`` → ``Known(0)``, ``{"input_tokens": 12}``
→ ``Known(12)``). This module adds no parsing of its own, so the honest-usage
behaviour under test here is the behaviour LC-P1-01 shipped and
``tests/test_fake_provider_usage.py`` already pins. If that parser is wrong, one
test fixes it for both the fake and every real adapter.

**Only the ``usage`` key is kept.** The sniffer reads the body, extracts
``payload["usage"]``, and drops the rest. A completion body carries the model's
own text, which after one retrieval step is a document excerpt. Keeping the body
even briefly would make this class a document cache, and the expiry would be
someone else's problem.

**pydantic-ai's numbers are never used as a fallback.** If the sniffer saw
nothing, the answer is ``Unknown``. Not "whatever ``ModelResponse.usage``
happened to be", which is the zero that started all of this.

Cost
----
Cost is *not* captured here, because no provider reports a price. It comes from
a LabCairn-owned price table keyed on ``(model, endpoint)``, and until one exists
it is :class:`~labcairn.core.providers.usage.Unknown` with reason ``UNPRICED`` —
which :class:`~labcairn.providers.budget.BudgetGuard` treats as *fail closed*,
not as free.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from labcairn.core.providers.protocol import UsageReport
from labcairn.core.providers.usage import UnknownReason


@runtime_checkable
class UsageCapture(Protocol):
    """What the adapter needs from whatever is watching the wire."""

    def observe(self, body: Mapping[str, object]) -> None:
        """Record the last response body. Called with the decoded JSON object."""
        ...

    def report(self) -> UsageReport:
        """The usage of the most recently observed response.

        Must return ``Unknown`` fields when nothing usable was observed. Every
        implementation here does so by delegating to
        :meth:`UsageReport.from_wire`, which is the only parser in the project.
        """
        ...


class NullUsageCapture:
    """Observes nothing, so everything is ``Unknown(EXTRACTION_FAILED)``.

    The correct default for any provider whose transport LabCairn does not own —
    including the :class:`~labcairn.providers.adapter.FakeUpstreamModel` the tests
    use. Picking this default is what makes the fail-closed path the *easy* one:
    an adapter that forgets to wire a real sniffer reports every token count as
    unmeasured and therefore refuses to run under a token ceiling, instead of
    quietly budgeting against zeros.
    """

    __slots__ = ()

    def observe(self, body: Mapping[str, object]) -> None:
        """Discard. This capture has no wire to learn from."""

    def report(self) -> UsageReport:
        return UsageReport.from_wire({})


class RecordingUsageCapture:
    """A capture the caller feeds by hand. Test double and offline-replay input.

    Deliberately a *different class* from :class:`NullUsageCapture` rather than a
    flag on it: "observed nothing because I did not bother" and "observed
    nothing because nothing came back" are different states, and a boolean
    ``enabled=False`` on one class is exactly the kind of switch that later ships
    set to the wrong value.
    """

    __slots__ = ("_block", "_observed")

    def __init__(self) -> None:
        self._block: Mapping[str, object] | None = None
        self._observed = False

    def observe(self, body: Mapping[str, object]) -> None:
        raw = body.get("usage")
        self._block = raw if isinstance(raw, Mapping) else None
        self._observed = True

    @property
    def observed_anything(self) -> bool:
        return self._observed

    def report(self) -> UsageReport:
        return UsageReport.from_wire({"usage": self._block})


class HttpxUsageSniffer:
    """Keeps the last response's ``usage`` block. Real provider path.

    Used as an ``httpx.AsyncBaseTransport`` wrapper:

        inner = httpx.AsyncHTTPTransport()
        client = httpx.AsyncClient(transport=HttpxUsageSniffer(inner))

    Why a transport and not a pydantic-ai hook: pydantic-ai offers
    ``customize_request_parameters`` for *requests* and nothing equivalent for
    *responses*, and its ``ModelResponse`` is already extracted by the time any
    hook could run. The transport is the last point where the raw body exists.

    The transport API is duck-typed rather than imported. ``httpx`` reaches this
    project transitively through ``pydantic-ai`` (``OpenAIProvider.__init__``
    has an ``http_client: httpx.AsyncClient`` parameter, so the dependency is
    part of pydantic-ai's public surface) but is not a declared LabCairn
    dependency and ``pyproject.toml`` is not this work order's to edit. Duck
    typing means the wrapper works whether or not httpx is importable here, and
    that the tests need no network stack at all.
    """

    __slots__ = ("_block", "_inner", "_observed")

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self._block: Mapping[str, object] | None = None
        self._observed = False

    @property
    def inner(self) -> Any:
        return self._inner

    def as_transport(self) -> HttpxUsageSniffer:
        """The wrapper itself, typed as the transport httpx expects.

        Returns ``self`` rather than the inner transport: a caller that passes a
        sniffer in and then wraps the client in a plain transport has silently
        disabled usage capture, and every token count becomes ``Unknown`` with no
        error anywhere. Making the sniffer the transport object removes the
        mistake rather than documenting it.
        """
        return self

    async def handle_async_request(self, request: Any) -> Any:
        """Forward, then keep the ``usage`` key. Never raise from the sniffing."""
        response = await self._inner.handle_async_request(request)
        await self._observe_response(response)
        return response

    async def aclose(self) -> None:
        """Close the wrapped transport.

        Not optional. ``httpx.AsyncClient.aclose()`` calls ``aclose()`` on its
        transport, so a wrapper that does not forward it turns every shutdown into
        an ``AttributeError`` — a bug that only appears when a connection is
        being released, which is the worst time to find it.
        """
        close = getattr(self._inner, "aclose", None)
        if close is not None:
            await close()

    def observe(self, body: Mapping[str, object]) -> None:
        """Keep the ``usage`` key of a decoded body.

        Public, and part of the :class:`UsageCapture` contract, so the sniffer is
        usable two ways: as a transport that feeds itself, and as a capture a test
        (or an offline replay) fills by hand. Both paths go through the same
        extraction, so there is no second place for the "absent means unknown"
        rule to be re-implemented slightly differently.
        """
        self._observed = True
        raw = body.get("usage")
        self._block = raw if isinstance(raw, Mapping) else None

    async def _observe_response(self, response: Any) -> None:
        """Read the body if the transport has not, then keep its ``usage`` key.

        A transport-level response is a *streaming* response: httpx has not read
        the body, so ``response.content`` raises ``ResponseNotRead``. The first
        version of this method called ``json.loads(response.content)`` inside a
        bare ``except``, swallowed it, and reported "no usage" for every
        endpoint.

        That failure direction is safe — token ceilings fail closed — and it is
        exactly how the real smoke hid it: the endpoint returned
        ``usage: {input_tokens: 83, output_tokens: 9}`` and the probe recorded
        ``usage_reporting: unsupported``. A guard that is safe when broken is
        still broken, because it also makes every provider unusable.

        ``aread()`` loads the body without consuming it, so the client still
        reads the same response afterwards.
        """
        with contextlib.suppress(Exception):
            await response.aread()
        try:
            body = json.loads(response.content)
        except Exception:
            # A non-JSON body is a normal provider failure (an HTML error page,
            # a truncated stream). It is recorded as "we saw a response and could
            # not read usage from it", which is exactly what it is.
            self._observed = True
            return
        if not isinstance(body, Mapping):
            self._observed = True
            return
        self.observe(body)

    def report(self) -> UsageReport:
        return UsageReport.from_wire({"usage": self._block})


class PricedUsage:
    """Cost for a response, or the reason there is none.

    Separated from :class:`UsageCapture` because a price is not on the wire. ADR-0002
    §Risks: *"Priced from a LabCairn-owned price table; entries are user-extendable.
    When absent, ``max_cost_usd`` fails closed only if explicitly set."*

    Not implemented here — the table itself belongs with the settings layer, and a
    Phase 1 default of "every model is unpriced" is the honest starting point. What
    is implemented is the reason vocabulary, so a caller cannot accidentally
    report an unpriced run as ``Known(0)``.
    """

    __slots__ = ()

    @staticmethod
    def unpriced() -> UnknownReason:
        return UnknownReason.UNPRICED
