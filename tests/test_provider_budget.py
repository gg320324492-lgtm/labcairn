r"""Budgets: a ceiling that cannot be checked must stop the run, not pass it.

The failure under test
----------------------
ADR-0002 §A1, from reading the two upstreams:

* pydantic-ai ``usage.py:604-612`` — ``check_cost`` *warns and returns* when the
  cost is unmeasurable, so ``cost_limit`` on an unpriced model enforces nothing,
  permanently, with one warning.
* OpenHands ``local_conversation.py:735-737`` — ``spent < max_budget_per_run``
  where ``spent`` came from ``accumulated_cost: float = 0.0``, so an unknown cost
  reads as \$0 and the budget never trips.

Both reach "the ceiling is not enforced" from opposite directions. ADR-0002
§Risks names the result the LC-P1-03 failure. So the tests below are mostly
negative: the assertion is that the run **stops**.

What is asserted here
---------------------
* An ``Unknown`` cost against a set ``max_cost_usd`` raises, never allows.
* An ``Unknown`` token total against a set ``max_total_tokens`` raises.
* ``USAGE_REPORTING`` unverified blocks a token ceiling *before* the request.
* A **measured zero** still passes — the distinction that matters, and the one
  both upstreams lose.
* ``provider_attempts`` diverging from ``labcairn_requests`` under a transport
  retry does not consume the request ceiling.
* Nothing in :mod:`labcairn.providers.budget` or :mod:`labcairn.providers.ledger`
  coerces a quantity to a number — asserted at the source level, because "we were
  careful" is not a property anyone can check next year.
"""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

import pytest

from labcairn.core.providers.usage import Known, Unknown, UnknownReason
from labcairn.providers.budget import (
    BudgetDecision,
    BudgetGuard,
    RunBudget,
    preflight_check,
)
from labcairn.providers.capabilities import (
    ALL_CAPABILITIES,
    Capability,
    CapabilityOutcome,
    ProviderCapabilities,
)
from labcairn.providers.errors import (
    BudgetEnforcementUnavailableError,
    BudgetExceededError,
)
from labcairn.providers.ledger import (
    COST_SCALE,
    LedgerSnapshot,
    RunLedger,
    micros_to_usd,
    usage_reporting_is_usable,
    usd_to_micros,
)


class FakeClock:
    """A monotonic clock a test advances by hand. No ``time.sleep``, ever."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _capabilities(*, usage_reporting: CapabilityOutcome) -> ProviderCapabilities:
    """Everything probed OK except ``usage_reporting``, which the caller controls.

    The parameter sets *that one* capability, so a test can hold the rest of the
    probe result constant and vary only the thing under test.
    """
    outcomes = dict.fromkeys(ALL_CAPABILITIES, CapabilityOutcome.OK)
    outcomes[Capability.USAGE_REPORTING] = usage_reporting
    return ProviderCapabilities.from_outcomes(
        endpoint_fingerprint="fp",
        model="m",
        protocol="p",
        outcomes=outcomes,
        unsupported_reason=dict.fromkeys(ALL_CAPABILITIES, "probe said no"),
    )


_OK_USAGE = _capabilities(usage_reporting=CapabilityOutcome.OK)
_NO_USAGE = _capabilities(usage_reporting=CapabilityOutcome.UNSUPPORTED)


# --- the two headline failures --------------------------------------------


@pytest.mark.unit
def test_cost_ceiling_fails_closed_when_price_unknown() -> None:
    """``max_cost_usd`` set, model unpriced ⇒ halt. Never a silent pass.

    Guards ``local_conversation.py:735-737`` and ``metrics.py:83-84`` together:
    the visualizer coerces with ``or 0.0`` and the budget then compares that
    ``0.0`` against its ceiling.
    """
    ledger = LedgerSnapshot(cost_micros=Unknown(reason=UnknownReason.UNPRICED))
    guard = BudgetGuard(RunBudget(max_cost_usd=Decimal("5.00")), capabilities=_OK_USAGE)

    assert guard.evaluate(ledger) is BudgetDecision.UNDECIDABLE
    with pytest.raises(BudgetEnforcementUnavailableError) as raised:
        guard.require(ledger)
    assert raised.value.ceiling == "max_cost_usd"
    assert raised.value.reason == UnknownReason.UNPRICED.value


@pytest.mark.unit
def test_token_ceiling_fails_closed_when_tokens_unknown() -> None:
    """A provider that reports no usage cannot be bounded by a token ceiling."""
    ledger = LedgerSnapshot(
        input_tokens=Unknown(reason=UnknownReason.PROVIDER_OMITTED),
        output_tokens=Unknown(reason=UnknownReason.PROVIDER_OMITTED),
    )
    guard = BudgetGuard(RunBudget(max_total_tokens=Known(1000)), capabilities=_OK_USAGE)

    assert guard.evaluate(ledger) is BudgetDecision.UNDECIDABLE
    with pytest.raises(BudgetEnforcementUnavailableError) as raised:
        guard.require(ledger)
    assert raised.value.ceiling == "max_total_tokens"


@pytest.mark.unit
def test_a_half_measured_response_leaves_the_total_unknown() -> None:
    """``input_tokens`` known and ``output_tokens`` omitted ⇒ total unknown.

    The merge case ADR-0002 names: ``merge(Known(5), Unknown(...))`` is
    ``Unknown``, *"not ``Known(5)``"*. Reporting the measured half as the total
    is the same lie as reporting zero, and it would let a run under a token
    ceiling pass on a partial measurement.
    """
    guard = BudgetGuard(RunBudget(max_total_tokens=Known(1000)), capabilities=_OK_USAGE)
    ledger = LedgerSnapshot(
        input_tokens=Known(4),
        output_tokens=Unknown(reason=UnknownReason.PROVIDER_OMITTED),
    )

    assert ledger.total_tokens == Unknown(reason=UnknownReason.PROVIDER_OMITTED)
    with pytest.raises(BudgetEnforcementUnavailableError):
        guard.require(ledger)


@pytest.mark.unit
def test_usage_reporting_capability_unverified_blocks_token_ceiling_before_the_request() -> None:
    """ADR-0002: *"the run halts with ``BudgetEnforcementUnavailable`` before issuing the request."*

    Checked against an empty ledger, which is the state a run is in before its
    first call — so a halt here cannot be mistaken for a halt after spending.
    """
    guard = BudgetGuard(RunBudget(max_total_tokens=Known(1000)))
    fresh = LedgerSnapshot()

    # Not blocking on the ledger alone — it has measured nothing yet.
    assert guard.evaluate(fresh) is BudgetDecision.ALLOW

    # Blocking as soon as the endpoint's reporting ability is known to be absent.
    with pytest.raises(BudgetEnforcementUnavailableError) as raised:
        guard.require_capability_for_ceilings(_NO_USAGE)
    # The reason lives on the exception; the message is a fixed template that
    # deliberately carries no endpoint detail.
    assert "reports usage" in raised.value.reason
    assert raised.value.reason.endswith("(unsupported)")
    # The message a user sees is a fixed template with no endpoint detail.
    assert "reports usage" not in str(raised.value)

    with pytest.raises(BudgetEnforcementUnavailableError):
        guard.require_capability_for_ceilings(
            ProviderCapabilities.unverified(endpoint_fingerprint="fp", model="m", protocol="p")
        )
    guard.require_capability_for_ceilings(_OK_USAGE)  # does not raise


@pytest.mark.unit
def test_no_token_ceiling_means_no_capability_gate() -> None:
    """Fail closed only where the operator actually set a ceiling.

    ADR-0002 §Risks: *"Fail closed only where the operator explicitly set the
    ceiling ... When no ceiling is set, run normally and surface
    ``usage_reporting: unverified`` in doctor."* A blanket refusal would make an
    unpriced local model unusable, which is a different failure.
    """
    BudgetGuard(RunBudget(max_cost_usd=Decimal("1"))).require_capability_for_ceilings(_NO_USAGE)
    BudgetGuard(RunBudget.unbounded()).require_capability_for_ceilings(
        ProviderCapabilities.unverified(endpoint_fingerprint="fp", model="m", protocol="p")
    )


# --- measured zero is a measurement ----------------------------------------


@pytest.mark.unit
def test_a_measured_zero_passes_every_ceiling() -> None:
    """The row both upstreams lose.

    ADR-0002 §A1: pydantic-ai pins it deliberately
    (``test_usage_limits.py:1166``, *"zero is not coerced to None"*), and
    ``test_usage_unknown_provider`` shows an absent block becoming
    ``RequestUsage()``. If zero and unknown are the same, then either every
    request is free or nothing is measurable, and a ceiling on a genuinely free
    local model can never be checked at all.
    """
    ledger = LedgerSnapshot(
        labcairn_requests=0,
        input_tokens=Known(0),
        output_tokens=Known(0),
        cost_micros=Known(0),
    )
    guard = BudgetGuard(
        RunBudget(
            max_total_tokens=Known(0),
            max_cost_usd=Decimal("0.01"),
            max_model_requests=0,
        ),
        capabilities=_OK_USAGE,
    )

    assert guard.evaluate(ledger) is BudgetDecision.ALLOW
    guard.require(ledger)  # does not raise


@pytest.mark.unit
def test_a_measured_value_past_the_ceiling_raises_and_is_terminal() -> None:
    """ADR-0002: ``BUDGET_EXHAUSTED`` is terminal, non-retryable, ``user_action="settings"``.

    Mirrors OpenHands' ``MaxBudgetExhausted -> QUOTA, retryable=False``
    (``error_classification.py:71-72``) and diverges from pydantic-ai's single
    ``UsageLimitExceeded``, which terminates with no classification at all.
    """
    ledger = LedgerSnapshot(labcairn_requests=3)
    guard = BudgetGuard(RunBudget(max_model_requests=2), capabilities=_OK_USAGE)

    with pytest.raises(BudgetExceededError) as raised:
        guard.require(ledger)
    failure = raised.value.failure
    assert failure.kind.value == "budget_exhausted"
    assert failure.retryable is False
    assert failure.user_action == "settings"
    assert raised.value.observed == 3


# --- known counts ----------------------------------------------------------


@pytest.mark.unit
def test_every_countable_ceiling_raises_once_it_is_passed() -> None:
    clock = FakeClock()
    ledger = RunLedger(clock=clock, capabilities=_OK_USAGE)
    ledger.record_request()
    ledger.record_request()
    ledger.record_tool_attempt()
    clock.advance(30.0)

    for budget, ceiling in (
        (RunBudget(max_model_requests=1), "max_model_requests"),
        (RunBudget(max_tool_calls=0), "max_tool_calls"),
        (RunBudget(max_wall_clock_s=10.0), "max_wall_clock_s"),
    ):
        with pytest.raises(BudgetExceededError) as raised:
            BudgetGuard(budget, capabilities=_OK_USAGE).require(ledger.snapshot())
        assert raised.value.ceiling == ceiling


@pytest.mark.unit
def test_tool_calls_are_counted_as_attempts_not_successes() -> None:
    """A failing tool loop must be bounded by something.

    Upstream counts successes only — ``test_failed_tool_calls_not_counted``
    (``test_usage_limits.py:1012``) asserts a tool that raises ``ModelRetry``
    consumes no ``tool_calls`` budget — so a loop of failing-but-retryable calls
    is bounded by nothing but the request ceiling.
    """
    ledger = RunLedger(clock=FakeClock(), capabilities=_OK_USAGE)
    for _ in range(5):
        ledger.record_tool_attempt()

    snapshot = ledger.snapshot()
    assert snapshot.tool_call_attempts == 5
    with pytest.raises(BudgetExceededError):
        BudgetGuard(RunBudget(max_tool_calls=4), capabilities=_OK_USAGE).require(snapshot)


# --- the two request counters ----------------------------------------------


@pytest.mark.unit
def test_provider_retry_does_not_consume_model_request_budget() -> None:
    """ADR-0002 §Contracts, verbatim.

    ``max_model_requests`` bounds *LabCairn-issued* calls. A transport-level
    retry is recorded in ``provider_attempts`` so a report can show both, but
    must not spend the ceiling — grounding pydantic-ai's own admission that
    ``RunUsage.requests`` *"isn't counted"* for transport retries
    (``usage.py:377-387``).
    """
    ledger = RunLedger(clock=FakeClock(), capabilities=_OK_USAGE)
    ledger.record_request(provider_attempts=1)
    ledger.record_transport_attempt()

    snapshot = ledger.snapshot()
    assert snapshot.labcairn_requests == 1
    assert snapshot.provider_attempts == 2

    guard = BudgetGuard(RunBudget(max_model_requests=1), capabilities=_OK_USAGE)
    assert guard.evaluate(snapshot) is BudgetDecision.ALLOW
    guard.require(snapshot)


@pytest.mark.unit
def test_the_ledger_reports_both_counters_so_a_report_can_show_the_gap() -> None:
    ledger = RunLedger(clock=FakeClock(), capabilities=_OK_USAGE)
    ledger.record_request(provider_attempts=1)
    ledger.record_transport_attempt()
    ledger.record_transport_attempt()

    snapshot = ledger.snapshot()
    assert (snapshot.labcairn_requests, snapshot.provider_attempts) == (1, 3)


# --- accumulation ----------------------------------------------------------


@pytest.mark.unit
def test_usage_accumulates_across_responses_and_stays_unknown_once_unknown() -> None:
    """ADR-0002's propagation rule: *once a run's count is unknown it stays unknown*.

    A later measured response must not "repair" an earlier gap, because a total
    that silently dropped one response's cost under-reports the run.
    """
    ledger = RunLedger(clock=FakeClock(), capabilities=_OK_USAGE)
    ledger.record_usage(input_tokens=Known(100), output_tokens=Known(20))
    ledger.record_usage(
        input_tokens=Unknown(reason=UnknownReason.PROVIDER_OMITTED),
        output_tokens=Known(30),
    )
    ledger.record_usage(input_tokens=Known(50), output_tokens=Known(10))

    snapshot = ledger.snapshot()
    assert snapshot.input_tokens == Unknown(reason=UnknownReason.PROVIDER_OMITTED)
    assert snapshot.output_tokens == Known(60)
    assert snapshot.total_tokens == Unknown(reason=UnknownReason.PROVIDER_OMITTED)


@pytest.mark.unit
def test_a_priced_cost_cannot_be_recorded_onto_a_run_that_failed_closed() -> None:
    """An ``Unknown`` that later becomes ``Known(0)`` would un-trip the guard.

    The sequence is: an unpriced response marks the run's cost unknown, the
    budget halts, and then a later step happens to know a price. Accepting that
    would make the halt depend on which step ran next.
    """
    ledger = RunLedger(clock=FakeClock(), capabilities=_OK_USAGE)
    ledger.record_cost(Unknown(reason=UnknownReason.UNPRICED))

    with pytest.raises(ValueError, match="earlier Unknown"):
        ledger.record_price_known(input_micros=1500)


# --- money without floats --------------------------------------------------


@pytest.mark.unit
def test_cost_is_integral_micro_usd_so_a_ceiling_is_comparable_exactly() -> None:
    assert usd_to_micros(Decimal("1.25")) == 1_250_000
    assert micros_to_usd(1_250_000) == Decimal("1.250000")
    # A ceiling finer than a micro-dollar cannot be represented without rounding
    # a guard, so it is refused rather than silently widened or narrowed.
    with pytest.raises(ValueError, match="whole number of micro-USD"):
        usd_to_micros(Decimal("0.0000001"))
    assert COST_SCALE == 1_000_000


@pytest.mark.unit
def test_a_cost_ceiling_is_enforced_in_micros_not_floats() -> None:
    ledger = RunLedger(clock=FakeClock(), capabilities=_OK_USAGE)
    ledger.record_price_known(input_micros=usd_to_micros(Decimal("2.00")))
    guard = BudgetGuard(RunBudget(max_cost_usd=Decimal("1.00")), capabilities=_OK_USAGE)

    with pytest.raises(BudgetExceededError) as raised:
        guard.require(ledger.snapshot())
    assert raised.value.ceiling == "max_cost_usd"
    assert micros_to_usd(int(raised.value.observed)) == Decimal("2.000000")


# --- construction refuses nonsense -----------------------------------------


@pytest.mark.unit
def test_an_unknown_token_ceiling_is_refused_at_construction() -> None:
    """A ceiling nobody can measure is not a ceiling.

    Accepting one would make every run undecidable by construction, which is the
    opposite of the intent.
    """
    with pytest.raises(ValueError, match="Unknown ceiling is not a ceiling"):
        RunBudget(max_total_tokens=Unknown(reason=UnknownReason.UNPRICED))


@pytest.mark.unit
@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_tool_calls": -1},
        {"max_model_requests": -1},
        {"max_wall_clock_s": -0.5},
        {"max_cost_usd": Decimal("-1")},
    ],
)
def test_negative_ceilings_are_refused(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        RunBudget(**kwargs)  # type: ignore[arg-type]


@pytest.mark.unit
def test_an_unbounded_budget_gates_nothing() -> None:
    budget = RunBudget.unbounded()
    assert budget.is_unbounded
    guard = BudgetGuard(budget)
    ledger = LedgerSnapshot(
        labcairn_requests=10_000,
        cost_micros=Unknown(reason=UnknownReason.UNPRICED),
        input_tokens=Unknown(reason=UnknownReason.PROVIDER_OMITTED),
    )
    assert guard.evaluate(ledger) is BudgetDecision.ALLOW
    guard.require(ledger)


@pytest.mark.unit
def test_preflight_reads_capabilities_off_the_snapshot() -> None:
    """A pre-flight with a token ceiling must halt on an unproven endpoint.

    The snapshot has measured nothing, so a ledger-only check would allow the
    first request through and only discover the problem once the money was
    spent. ADR-0002 requires the halt to come first.
    """
    snapshot = LedgerSnapshot(capabilities=_NO_USAGE)
    with pytest.raises(BudgetEnforcementUnavailableError):
        preflight_check(RunBudget(max_total_tokens=Known(5)), snapshot)
    # And a snapshot with no capabilities record at all blocks the same way.
    with pytest.raises(BudgetEnforcementUnavailableError):
        preflight_check(RunBudget(max_total_tokens=Known(5)), LedgerSnapshot())


# --- structural guarantees -------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("module_name", ["budget.py", "ledger.py"])
def test_budget_module_contains_no_numeric_coercion(module_name: str) -> None:
    """No ``int()``, ``float()`` or ``or 0`` anywhere in the budget path.

    The whole of this work order rests on a quantity never being turned into a
    number it is not. A behavioural test covers the paths it thought of; this
    covers the ones nobody did. ``require_known`` is the only sanctioned exit and
    it lives in ``core.providers.usage``, where LC-P1-01 wrote its own test for
    exactly this.
    """
    source = (
        Path(__file__).resolve().parents[1] / "src" / "labcairn" / "providers" / module_name
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Attribute every int()/float() call to the function it appears in, so a
    # legitimate Decimal -> micro-USD conversion is distinguishable from a
    # UsageValue being forced into a number.
    coercions: dict[str, set[str]] = {}
    for function in ast.walk(tree):
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(function):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"int", "float"}
            ):
                coercions.setdefault(function.name, set()).add(node.func.id)

    # `usd_to_micros` converts a Decimal (a configured dollar ceiling) to an
    # integer count of micro-USD. That is a unit conversion between two exact
    # representations, not the coercion of an unmeasured quantity to a number.
    allowed = {"usd_to_micros"} if module_name == "ledger.py" else set()
    offending = {name: calls for name, calls in coercions.items() if name not in allowed}
    assert not offending, (
        f"{module_name} coerces to a number in {sorted(offending)}; "
        "require_known is the only sanctioned exit from a UsageValue"
    )

    # `x or 0` on a UsageValue is the same bug wearing different clothes: a bare
    # `Unknown` instance is truthy, so it would *not* yield 0 — but a
    # `Known(0)` would pass unnoticed as a measured value, which is the confusion
    # this whole module exists to prevent.
    or_zero = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.BoolOp)
        and isinstance(node.op, ast.Or)
        and any(isinstance(v, ast.Constant) and v.value == 0 for v in node.values)
    ]
    assert not or_zero, f"{module_name} contains an `or 0` fallback on a quantity"


@pytest.mark.unit
def test_usage_reporting_is_usable_is_false_for_every_unproven_case() -> None:
    """``None``, ``UNVERIFIED`` and ``UNSUPPORTED`` all answer "no"."""
    assert usage_reporting_is_usable(None) is False
    assert usage_reporting_is_usable(_NO_USAGE) is False
    assert usage_reporting_is_usable(_OK_USAGE) is True
    assert (
        usage_reporting_is_usable(
            ProviderCapabilities.unverified(endpoint_fingerprint="fp", model="m", protocol="p")
        )
        is False
    )
