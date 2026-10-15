"""What a run has spent, accumulated without ever inventing a number.

The one job
-----------
Every quantity a budget can bound arrives here, and every one of them is a
:class:`~labcairn.core.providers.usage.UsageValue` — a measured integer or a
recorded reason it is not known. This module adds no arithmetic to that. It
totals with :func:`~labcairn.core.providers.usage.merge`, which refuses to add
across an ``Unknown``, and it never calls ``int()``, ``float()`` or ``or 0`` on a
quantity. ``tests/test_provider_budget.py::test_budget_module_contains_no_numeric_coercion``
asserts the absence at the source level, because "we were careful" is not a
property anyone can check next year.

Money without floats
--------------------
Cost is a :data:`UsageValue` too, in **micro-USD** as a plain ``int``
(:data:`COST_SCALE`) rather than in :class:`~decimal.Decimal`. Three reasons:

* ``labcairn.core.providers.usage.Known`` holds an ``int`` by construction, so a
  Decimal would mean a second, parallel tri-state type for one quantity — which
  is how ``known/unknown`` quietly stops being *the* answer to "did we measure
  this?" and becomes true of only some quantities.
* A float dollar figure is not exactly representable, so two runs that spent the
  same money can disagree on ``>`` at the boundary. Micro-USD is integral.
* The unit is declared once, here, and every conversion goes through
  :func:`usd_to_micros` / :func:`micros_to_usd`, so the scale cannot drift
  between the ceiling and the spend.

``max_cost_usd`` in :class:`~labcairn.providers.budget.RunBudget` is still a
``Decimal``, because that is what an operator types. It is converted exactly
(:func:`usd_to_micros` raises on a sub-micro-USD ceiling rather than rounding a
guard down).

Counting the two kinds of request separately
--------------------------------------------
``labcairn_requests`` counts calls LabCairn issued. ``provider_attempts`` counts
HTTP requests that reached the provider, which is the larger number once
transport-level retries happen. ADR-0002 §"RunBudget" refuses to conflate them,
grounded in pydantic-ai's own admission::

    RunUsage.requests  usage.py:377-387
    "It can be lower than the number of requests sent to the provider: ...
     retries made by the provider SDK or HTTP transport aren't counted."

So a ceiling bounds the first, and the second is recorded next to it so a report
can show both. A ceiling on ``provider_attempts`` would not bound anything the
operator can control from the UI, which is why there is not one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from decimal import ROUND_HALF_UP, Decimal

from labcairn.core.providers.usage import (
    Known,
    Unknown,
    UnknownReason,
    UsageValue,
    merge,
)
from labcairn.providers.capabilities import Capability, ProviderCapabilities

#: Micro-USD per USD. Integer money: 1 USD == 1_000_000.
COST_SCALE: int = 1_000_000


def _unpriced() -> Unknown:
    """The cost a run starts at when no price table entry exists."""
    return Unknown(reason=UnknownReason.UNPRICED)


def _zero() -> Known:
    """A fresh, measured zero. The default of a run that has spent nothing.

    A ``default_factory`` rather than a bare ``Known(0)`` literal because ruff's
    RUF009 is right that a shared mutable-looking default in a frozen dataclass is
    a smell worth naming, and because a factory makes the "this is a measurement"
    reading explicit at the declaration site.
    """
    return Known(0)


def usd_to_micros(amount: Decimal) -> int:
    """Convert a dollar ceiling to micro-USD, or refuse to lose precision.

    Rounding a ceiling *down* would silently widen the budget by up to a
    micro-dollar per check; rounding *up* would silently narrow it. Neither is
    acceptable for a guard, so a ceiling that is not a whole number of
    micro-dollars is an error the operator has to see.
    """
    scaled = amount * COST_SCALE
    if scaled != scaled.to_integral_value():
        raise ValueError(
            f"cost ceiling {amount} is not a whole number of micro-USD; "
            "ceilings finer than 1e-6 USD cannot be represented exactly"
        )
    return int(scaled)


def micros_to_usd(micros: int) -> Decimal:
    return (Decimal(micros) / COST_SCALE).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class LedgerSnapshot:
    """An immutable reading of one run's spend."""

    #: Requests LabCairn issued. What a ceiling bounds.
    labcairn_requests: int = 0
    #: HTTP requests that reached the provider, including transport-level retries.
    provider_attempts: int = 0
    #: Tool-call **attempts**, not successes — ADR-0002 §"RunBudget" divergence 2,
    #: because a failing-tool loop is otherwise bounded by nothing
    #: (``test_failed_tool_calls_not_counted``, ``test_usage_limits.py:1012``).
    tool_call_attempts: int = 0
    input_tokens: UsageValue = field(default_factory=_zero)
    output_tokens: UsageValue = field(default_factory=_zero)
    #: Micro-USD. ``Known(0)`` is "this really was free"; ``Unknown`` is
    #: "no price for this model", which ADR-0002 says must fail closed.
    # A snapshot with no cost stated is unpriced, not free. Defaulting to
    # Known(0) would make an unreported cost indistinguishable from a measured
    # zero, which is the exact conflation ADR-0002 exists to prevent.
    cost_micros: UsageValue = field(default_factory=_unpriced)
    elapsed_s: float = 0.0
    #: The probe result this run was gated on, if any. Carried so a budget
    #: decision can consult ``USAGE_REPORTING`` without a second lookup.
    capabilities: ProviderCapabilities | None = None

    @property
    def total_tokens(self) -> UsageValue:
        """Input + output, via :func:`merge`. Never ``input + output``.

        Half-measured yields ``Unknown``, not the measured half dressed up as a
        total. This is ADR-0002's ``test_usage_merge_is_not_sum_when_any_unknown``
        and ``test_usage_reporting_capability_unverified_blocks_token_ceiling``
        meeting in one property.
        """
        return merge(self.input_tokens, self.output_tokens)


class RunLedger:
    """The mutable accumulator behind :class:`LedgerSnapshot`.

    Holds an injected monotonic clock rather than calling one. The cost of that
    is one parameter; the benefit is that the wall-clock ceiling is testable by
    setting the clock, which a test that has to ``time.sleep`` will get wrong
    eventually.
    """

    __slots__ = ("_clock", "_start", "_state")

    def __init__(
        self,
        *,
        clock: Callable[[], float],
        capabilities: ProviderCapabilities | None = None,
        priced: bool,
    ) -> None:
        self._clock = clock
        self._start = clock()
        # ``priced`` is a **required** keyword, deliberately. It defaulted to
        # True while this very docstring argued that Phase 1 has no price table
        # and every ledger should therefore be constructed with False — so a
        # caller who forgot the argument silently got `Known(0)` and a
        # `max_cost_usd` ceiling that never tripped. A boolean whose wrong value
        # disables a budget guard does not get a default; it gets to be stated.
        #
        # `priced=False` starts the run's cost as `Unknown(UNPRICED)` rather
        # than `Known(0)`. That distinction is the whole of ADR-0002's cost rule:
        # a run against a model with no entry in the price table has *not* spent
        # zero, it has an amount it cannot compute.
        self._state = LedgerSnapshot(
            capabilities=capabilities,
            cost_micros=Known(0) if priced else Unknown(reason=UnknownReason.UNPRICED),
        )

    def set_capabilities(self, capabilities: ProviderCapabilities | None) -> None:
        self._state = replace(self._state, capabilities=capabilities)

    def record_request(self, *, provider_attempts: int = 1) -> None:
        """Count one LabCairn-issued call and the HTTP attempts it cost.

        ``provider_attempts`` defaults to 1 and is raised by the transport when
        it retried, so the two counters diverge exactly when they should.
        """
        self._state = replace(
            self._state,
            labcairn_requests=self._state.labcairn_requests + 1,
            provider_attempts=self._state.provider_attempts + provider_attempts,
            elapsed_s=self._elapsed(),
        )

    def record_transport_attempt(self) -> None:
        """One extra HTTP attempt that LabCairn did not ask for (a transport retry).

        Deliberately does **not** touch ``labcairn_requests``: that is the whole
        reason both counters exist. ``test_provider_retry_does_not_consume_model_request_budget``
        pins the behaviour.
        """
        self._state = replace(
            self._state,
            provider_attempts=self._state.provider_attempts + 1,
            elapsed_s=self._elapsed(),
        )

    def record_tool_attempt(self) -> None:
        self._state = replace(
            self._state,
            tool_call_attempts=self._state.tool_call_attempts + 1,
            elapsed_s=self._elapsed(),
        )

    def record_usage(self, *, input_tokens: UsageValue, output_tokens: UsageValue) -> None:
        """Fold one response's usage into the run.

        Uses :func:`merge`, so a response that omitted ``output_tokens`` leaves
        the run total ``Unknown`` even though ``input_tokens`` was measured. The
        alternative — keeping the last known pair — is the "once unknown, stays
        known" lie ADR-0002's propagation rule forbids.
        """
        self._state = replace(
            self._state,
            input_tokens=merge(self._state.input_tokens, input_tokens),
            output_tokens=merge(self._state.output_tokens, output_tokens),
            elapsed_s=self._elapsed(),
        )

    def record_cost(self, cost_micros: UsageValue) -> None:
        self._state = replace(
            self._state,
            cost_micros=merge(self._state.cost_micros, cost_micros),
            elapsed_s=self._elapsed(),
        )

    def record_price_known(self, *, input_micros: int = 0, output_micros: int = 0) -> None:
        """Fold in spend computed from a price the LabCairn price table supplied.

        The price table is LabCairn-owned and user-extendable (ADR-0002 §Risks),
        so this is a measurement of *our own arithmetic on a known price*, not a
        value read off the wire — which is why it arrives as a plain ``int``
        rather than as something to be parsed.
        """
        if isinstance(self._state.cost_micros, Unknown):
            # A run that already failed closed on an unpriced model must not
            # recover by accident when a later step happens to know a price.
            raise ValueError(
                "cannot record a priced cost onto a run whose cost is already unknown; "
                "the earlier Unknown is the truthful one"
            )
        self.record_cost(Known(input_micros + output_micros))

    def snapshot(self) -> LedgerSnapshot:
        return replace(self._state, elapsed_s=self._elapsed())

    def _elapsed(self) -> float:
        return max(0.0, self._clock() - self._start)


def unknown_usage(*, reason: UnknownReason) -> tuple[UsageValue, UsageValue]:
    """The (input, output) pair for a response that reported nothing.

    Named so the reason cannot be forgotten at the call site: every place that
    decides a response had no usage calls this with an explicit
    :class:`~labcairn.core.providers.usage.UnknownReason`, rather than
    constructing an ``Unknown`` inline where a typo in the enum member would
    surface as a ``ValueError`` three modules later.
    """
    return Unknown(reason=reason), Unknown(reason=reason)


def usage_reporting_is_usable(capabilities: ProviderCapabilities | None) -> bool:
    """Whether ``USAGE_REPORTING`` was confirmed.

    ``None`` means no probe record reached this run, which is ``False`` here —
    the same answer as ``UNVERIFIED``, and for the same reason: a ceiling that
    cannot be checked must not be reported as checked.

    Takes the capability rather than the raw usage values on purpose. A provider
    can report usage for one response and not the next; asking "has this endpoint
    ever demonstrated it can?" is the stable question, and the per-response
    :class:`~labcairn.core.providers.usage.UsageValue` is the volatile one.
    """
    if capabilities is None:
        return False
    return capabilities.outcome_for(Capability.USAGE_REPORTING).usable
