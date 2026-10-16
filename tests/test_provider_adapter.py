"""The adapter's gate: what happens before a request, and what the truth is after.

These are the integration-level tests. Each one drives a real
:class:`~labcairn.providers.adapter.PydanticAiModelProvider` against a
:class:`~tests.provider_fakes.FakeEndpoint` that counts its calls, so the
assertions are about *how many HTTP requests were made* and not merely about
whether something was raised.

The four properties
-------------------
1. **The gate is before the wire.** A blocked capability, a cancelled run and an
   unenforceable ceiling each stop the run with zero calls recorded.
2. **Unknown is what the wire said.** A response with no ``usage`` block yields
   ``Unknown(PROVIDER_OMITTED)`` — while the fake's pydantic-ai ``usage`` says
   zero throughout, so a code path reading the framework's counter would produce
   ``Known(0)`` and fail these tests.
3. **Stop, cancel and timeout are distinguishable.**
4. **The outbound disclosure is declared per call**, and Phase 1 declares
   excerpts off.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest
from provider_fakes import FakeEndpoint, Reply, sync_runner

from labcairn.core.providers.protocol import ModelRequest
from labcairn.core.providers.usage import Known, Unknown, UnknownReason
from labcairn.providers.adapter import (
    PHASE_1_OUTBOUND_POLICY,
    OutboundDisclosure,
    PydanticAiModelProvider,
    default_runner,
)
from labcairn.providers.budget import RunBudget
from labcairn.providers.cancel import CancellationToken
from labcairn.providers.capabilities import (
    ALL_CAPABILITIES,
    Capability,
    CapabilityOutcome,
    ProviderCapabilities,
)
from labcairn.providers.errors import (
    BudgetEnforcementUnavailableError,
    BudgetExceededError,
    FailureKind,
    OutboundRefusedError,
    ProviderCancelledError,
    ProviderError,
    ProviderTimeoutError,
    UnsupportedCapabilityError,
)
from labcairn.providers.redaction import Redactor


class FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _capabilities(*, tool_calls: CapabilityOutcome = CapabilityOutcome.OK) -> ProviderCapabilities:
    outcomes = dict.fromkeys(ALL_CAPABILITIES, CapabilityOutcome.OK)
    outcomes[Capability.TOOL_CALLS] = tool_calls
    return ProviderCapabilities.from_outcomes(
        endpoint_fingerprint="fp",
        model="m",
        protocol="p",
        outcomes=outcomes,
        unsupported_reason=dict.fromkeys(ALL_CAPABILITIES, "probe said no"),
    )


def _provider(endpoint: FakeEndpoint, **kwargs: object) -> PydanticAiModelProvider:
    kwargs.setdefault("runner", sync_runner)
    kwargs.setdefault("clock", FakeClock())
    kwargs.setdefault("usage_capture", endpoint.capture)
    return PydanticAiModelProvider(model=endpoint, **kwargs)  # type: ignore[arg-type]


_OK_REPLY = Reply(
    name="ok", text="the answer", usage_body={"input_tokens": 40, "output_tokens": 12}
)


# --- 1. the gate is before the wire ----------------------------------------


@pytest.mark.unit
def test_capability_failure_decided_before_request_not_after() -> None:
    """ADR-0002 §Contracts, verbatim.

    The gate must raise *before* an HTTP call, not after a ``UserError`` from
    inside ``prepare_request`` (``models/__init__.py:399-400``). The assertion is
    ``call_count == 0``, not merely that something was raised.
    """
    endpoint = FakeEndpoint(replies=(_OK_REPLY,))
    provider = _provider(
        endpoint,
        capabilities=_capabilities(tool_calls=CapabilityOutcome.UNSUPPORTED),
        required_capabilities=frozenset({Capability.TOOL_CALLS}),
    )

    with pytest.raises(UnsupportedCapabilityError) as raised:
        provider.send(ModelRequest(prompt="do the thing", tools=("read_file",)))

    assert endpoint.call_count == 0
    assert raised.value.capability == Capability.TOOL_CALLS.value
    assert raised.value.failure.kind.value == "capability_unavailable"


@pytest.mark.unit
def test_no_probe_record_blocks_exactly_like_an_unsupported_probe() -> None:
    """``UNVERIFIED`` is enforced as ``UNSUPPORTED``, per ADR-0002 §4."""
    endpoint = FakeEndpoint(replies=(_OK_REPLY,))
    provider = _provider(
        endpoint,
        capabilities=None,
        required_capabilities=frozenset({Capability.TOOL_CALLS}),
    )

    with pytest.raises(UnsupportedCapabilityError) as raised:
        provider.send(ModelRequest(prompt="do the thing", tools=("read_file",)))
    assert endpoint.call_count == 0
    assert "no capability probe has run" in raised.value.reason


@pytest.mark.unit
def test_a_gated_capability_that_probed_ok_lets_the_call_through() -> None:
    endpoint = FakeEndpoint(replies=(_OK_REPLY,))
    provider = _provider(
        endpoint,
        capabilities=_capabilities(),
        required_capabilities=frozenset({Capability.TOOL_CALLS}),
    )

    response = provider.send(ModelRequest(prompt="do the thing", tools=("read_file",)))
    assert endpoint.call_count == 1
    assert response.text == "the answer"
    assert endpoint.calls[0].tool_names == ("read_file",)


@pytest.mark.unit
def test_no_capability_gate_when_none_is_required() -> None:
    """A caller that genuinely needs no capability may leave the gate off."""
    endpoint = FakeEndpoint(replies=(_OK_REPLY,))
    provider = _provider(endpoint, required_capabilities=None, capabilities=None)
    provider.send(ModelRequest(prompt="summarise"))
    assert endpoint.call_count == 1


@pytest.mark.unit
def test_a_token_ceiling_blocks_before_the_request_when_usage_is_unproven() -> None:
    """ADR-0002: the halt comes before the request, not after the spend."""
    endpoint = FakeEndpoint(replies=(_OK_REPLY,))
    provider = _provider(
        endpoint,
        budget=RunBudget(max_total_tokens=Known(100)),
        capabilities=_capabilities(),
    )
    # Downgrade USAGE_REPORTING only.
    capabilities = ProviderCapabilities.from_outcomes(
        endpoint_fingerprint="fp",
        model="m",
        protocol="p",
        outcomes={
            c: CapabilityOutcome.OK for c in ALL_CAPABILITIES if c is not Capability.USAGE_REPORTING
        }
        | {Capability.USAGE_REPORTING: CapabilityOutcome.UNSUPPORTED},
        unsupported_reason=dict.fromkeys(ALL_CAPABILITIES, "no usage block seen"),
    )
    provider.set_capabilities(capabilities)

    with pytest.raises(BudgetEnforcementUnavailableError):
        provider.send(ModelRequest(prompt="summarise"))
    assert endpoint.call_count == 0


@pytest.mark.unit
def test_a_cost_ceiling_blocks_before_the_request_when_the_model_is_unpriced() -> None:
    """Every provider is unpriced until a LabCairn price table exists."""
    endpoint = FakeEndpoint(replies=(_OK_REPLY,))
    provider = _provider(
        endpoint,
        budget=RunBudget(max_cost_usd=Decimal("1.00")),
        capabilities=_capabilities(),
    )
    # Force the ledger's cost to Unknown the way a real unpriced run would.
    provider.ledger_snapshot()

    with pytest.raises(BudgetEnforcementUnavailableError):
        provider.send(ModelRequest(prompt="summarise"))
    assert endpoint.call_count == 0


@pytest.mark.unit
def test_an_exceeded_ceiling_stops_the_next_call() -> None:
    """Pre-flight, so the overshoot is at most one request."""
    endpoint = FakeEndpoint(replies=(_OK_REPLY, _OK_REPLY))
    provider = _provider(
        endpoint,
        budget=RunBudget(max_model_requests=1),
        capabilities=_capabilities(),
    )
    provider.send(ModelRequest(prompt="one"))
    with pytest.raises(BudgetExceededError) as raised:
        provider.send(ModelRequest(prompt="two"))

    assert endpoint.call_count == 1
    assert raised.value.observed == 2


# --- 2. usage truthfulness -------------------------------------------------


@pytest.mark.unit
def test_provider_omitting_usage_field_yields_unknown_not_zero() -> None:
    """ADR-0002 §Contracts, and the exact inverse of ``test_usage_unknown_provider``.

    The fake's pydantic-ai ``usage`` is zero for *every* reply, so a ``Known(0)``
    here would mean the adapter read the framework's counter rather than the raw
    body — the failure this work order exists to prevent.
    """
    endpoint = FakeEndpoint(replies=(Reply(name="no-usage", text="fine"),))
    provider = _provider(endpoint, capabilities=_capabilities())

    response = provider.send(ModelRequest(prompt="summarise"))
    assert response.usage.input_tokens == Unknown(reason=UnknownReason.PROVIDER_OMITTED)
    assert response.usage.output_tokens == Unknown(reason=UnknownReason.PROVIDER_OMITTED)
    assert response.usage.total_tokens == Unknown(reason=UnknownReason.PROVIDER_OMITTED)


@pytest.mark.unit
def test_a_usage_block_is_read_verbatim_from_the_wire() -> None:
    endpoint = FakeEndpoint(replies=(_OK_REPLY,))
    provider = _provider(endpoint, capabilities=_capabilities())

    response = provider.send(ModelRequest(prompt="summarise"))
    assert response.usage.input_tokens == Known(40)
    assert response.usage.output_tokens == Known(12)
    assert response.usage.total_tokens == Known(52)


@pytest.mark.unit
def test_a_provider_reporting_a_real_zero_keeps_it() -> None:
    """The row both upstreams lose: ``{"input_tokens": 0}`` is a *measurement*.

    If this came back ``Unknown``, a free local model could never run under a
    token ceiling, and the distinction the whole module is built on would be
    gone.
    """
    endpoint = FakeEndpoint(
        replies=(Reply(name="free", text="ok", usage_body={"input_tokens": 0, "output_tokens": 0}),)
    )
    provider = _provider(endpoint, capabilities=_capabilities())

    response = provider.send(ModelRequest(prompt="summarise"))
    assert response.usage.input_tokens == Known(0)
    assert response.usage.total_tokens == Known(0)


@pytest.mark.unit
def test_a_partially_reported_usage_block_leaves_only_that_field_unknown() -> None:
    """A provider may report input tokens and omit output tokens. Both facts survive."""
    endpoint = FakeEndpoint(
        replies=(Reply(name="half", text="ok", usage_body={"input_tokens": 7}),)
    )
    provider = _provider(endpoint, capabilities=_capabilities())

    usage = provider.send(ModelRequest(prompt="summarise")).usage
    assert usage.input_tokens == Known(7)
    assert usage.output_tokens == Unknown(reason=UnknownReason.PROVIDER_OMITTED)
    assert usage.total_tokens == Unknown(reason=UnknownReason.PROVIDER_OMITTED)


@pytest.mark.unit
def test_the_ledger_totals_across_calls_and_the_counters_diverge_on_a_retry() -> None:
    endpoint = FakeEndpoint(replies=(_OK_REPLY, _OK_REPLY))
    provider = _provider(endpoint, capabilities=_capabilities())

    provider.send(ModelRequest(prompt="one"))
    provider.record_transport_attempt()
    provider.send(ModelRequest(prompt="two"))

    snapshot = provider.ledger_snapshot()
    assert snapshot.input_tokens == Known(80)
    assert snapshot.labcairn_requests == 2
    assert snapshot.provider_attempts == 3


# --- 3. stop, cancel, timeout ----------------------------------------------


@pytest.mark.unit
def test_a_cancelled_run_makes_no_request() -> None:
    endpoint = FakeEndpoint(replies=(_OK_REPLY,))
    token = CancellationToken(clock=FakeClock())
    token.cancel("operator pressed stop")
    provider = _provider(endpoint, token=token, capabilities=_capabilities())

    with pytest.raises(ProviderCancelledError) as raised:
        provider.send(ModelRequest(prompt="summarise"))

    assert endpoint.call_count == 0
    assert raised.value.reason == "operator pressed stop"
    assert raised.value.failure.retryable is False
    assert raised.value.failure.kind.value == "cancelled"


@pytest.mark.unit
def test_cancellation_is_idempotent_and_the_first_reason_wins() -> None:
    """The second caller is usually the timeout unwinding the same path."""
    token = CancellationToken(clock=FakeClock())
    token.cancel("operator pressed stop")
    token.cancel("timeout during unwinding")
    assert token.reason == "operator pressed stop"


@pytest.mark.unit
def test_an_expired_deadline_stops_before_the_request() -> None:
    """A run deadline is checked before a call, not discovered afterwards."""
    clock = FakeClock()
    token = CancellationToken(clock=clock, deadline=30.0)
    endpoint = FakeEndpoint(replies=(_OK_REPLY,))
    provider = _provider(endpoint, token=token, capabilities=_capabilities())

    provider.send(ModelRequest(prompt="one"))
    assert endpoint.call_count == 1

    clock.advance(600.0)
    with pytest.raises(ProviderTimeoutError):
        provider.send(ModelRequest(prompt="two"))
    assert endpoint.call_count == 1


@pytest.mark.unit
def test_a_per_request_timeout_bounds_a_hung_endpoint() -> None:
    """The one in-flight bound that actually interrupts.

    A cooperative cancel cannot kill a socket read, and this file says so rather
    than implying otherwise. ``asyncio.wait_for`` genuinely cancels the awaiting
    task, so a hung provider is bounded by the timeout instead of by hope.

    The only test here with real time in it: the fake's coroutine never returns,
    so the 50 ms budget is a floor on the duration rather than a measurement.
    """
    endpoint = FakeEndpoint(replies=(Reply(name="hangs", hangs=True),))
    provider = _provider(endpoint, timeout_s=0.05, capabilities=_capabilities())

    with pytest.raises(ProviderTimeoutError) as raised:
        provider.send(ModelRequest(prompt="summarise"))

    assert raised.value.failure.kind.value == "timeout"
    assert raised.value.failure.retryable is True
    assert raised.value.failure.user_action == "retry"


@pytest.mark.unit
def test_a_transport_failure_is_classified_by_status_not_by_its_body() -> None:
    class _Response:
        status_code = 429

    class _HTTPStatusError(Exception):
        response = _Response()

    endpoint = FakeEndpoint(
        replies=(), always_raises=_HTTPStatusError("Rate limit: retry after 30s")
    )
    provider = _provider(
        endpoint, capabilities=_capabilities(), redactor=Redactor(["sk-ant-fake-key-0000000"])
    )

    with pytest.raises(ProviderError) as raised:
        provider.send(ModelRequest(prompt="summarise"))
    assert raised.value.failure.kind.value == "provider_rate_limit"
    assert raised.value.failure.retryable is True
    # The body is discarded, so no amount of it can reach a record.
    assert "retry after 30s" not in str(raised.value)


@pytest.mark.unit
def test_send_from_inside_a_running_loop_says_which_knob_to_turn() -> None:
    """asyncio's own message is about asyncio; an operator needs the parameter."""
    endpoint = FakeEndpoint(replies=(_OK_REPLY,))
    provider = _provider(endpoint, capabilities=_capabilities())

    async def call() -> None:
        provider._runner = default_runner  # deliberately the default
        provider.send(ModelRequest(prompt="summarise"))

    with pytest.raises(ProviderError) as raised:
        asyncio.run(call())
    assert "runner=" in raised.value.hint


# --- 4. outbound disclosure ------------------------------------------------


@pytest.mark.unit
def test_phase_1_outbound_policy_forbids_excerpts() -> None:
    """A declaration, asserted so it cannot be changed by accident.

    What this is **not**: enforcement. This layer cannot tell a document excerpt
    from ordinary user text, and no regex will. The control that makes the
    declaration true lives in the retrieval layer (LC-P1-09); this is the
    statement of intent and the tripwire if someone edits it.
    """
    assert PHASE_1_OUTBOUND_POLICY.sends_document_excerpts is False
    assert PHASE_1_OUTBOUND_POLICY.sends_prompt is True


@pytest.mark.unit
def test_the_disclosure_is_narrowed_per_call() -> None:
    """A call with no tools sends no tool names — checkable per exchange."""
    endpoint = FakeEndpoint(replies=(_OK_REPLY, _OK_REPLY))
    provider = _provider(endpoint, capabilities=_capabilities())

    provider.send(ModelRequest(prompt="summarise"))
    provider.send(ModelRequest(prompt="read", tools=("read_file",)))

    plain, with_tools = provider.exchanges()
    assert plain.outbound.sends_tool_names is False
    assert with_tools.outbound.sends_tool_names is True
    assert plain.outbound.sends_document_excerpts is False


@pytest.mark.unit
def test_outbound_refusal_is_a_first_class_failure() -> None:
    """A caller that declares excerpts permitted and then sends one is refused.

    ADR-0002 §5 lists ``POLICY_DENIED``/``OUT_OF_SCOPE`` as terminal and
    non-retryable. Phase 1 sets ``sends_document_excerpts=False`` everywhere, so
    this is the shape a future relaxation has to keep honest rather than a path
    that can be reached today.
    """
    policy = OutboundDisclosure(sends_document_excerpts=True)
    assert policy.sends_document_excerpts is True

    failure = FailureKind.OUTBOUND_REFUSED
    assert failure.value == "outbound_refused"
    assert OutboundRefusedError("excerpt in prompt").failure.retryable is False


# --- the seam itself -------------------------------------------------------


@pytest.mark.unit
def test_the_adapter_satisfies_the_frozen_provider_protocol() -> None:
    """LC-P1-01's Protocol is unchanged; the adapter drops in behind it."""
    from labcairn.core.providers.protocol import ModelProvider

    endpoint = FakeEndpoint(replies=(_OK_REPLY,))
    provider = _provider(endpoint, capabilities=_capabilities(), provider_label="anthropic")
    assert isinstance(provider, ModelProvider)
    assert provider.name == "anthropic:fake-model"


@pytest.mark.unit
def test_a_tool_call_in_the_response_survives_translation() -> None:
    endpoint = FakeEndpoint(
        replies=(Reply(name="tool", text="", tool_calls=(("read_file", {"path": "a.csv"}),)),)
    )
    provider = _provider(endpoint, capabilities=_capabilities())

    response = provider.send(ModelRequest(prompt="read", tools=("read_file",)))
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].name == "read_file"
    assert response.tool_calls[0].arguments_json == '{"path":"a.csv"}'


@pytest.mark.unit
def test_tool_attempts_are_counted_separately_from_requests() -> None:
    """A tool loop spends requests *and* tool attempts; both ceilings exist."""
    endpoint = FakeEndpoint(replies=(_OK_REPLY, _OK_REPLY))
    provider = _provider(endpoint, capabilities=_capabilities())

    provider.send(ModelRequest(prompt="one", tools=("read_file",)))
    provider.record_tool_attempt()
    provider.record_tool_attempt()
    provider.send(ModelRequest(prompt="two", tools=("read_file",)))

    snapshot = provider.ledger_snapshot()
    assert snapshot.labcairn_requests == 2
    assert snapshot.tool_call_attempts == 2


@pytest.mark.unit
def test_a_default_provider_without_a_capture_reports_everything_unknown() -> None:
    """The fail-safe default, asserted rather than assumed.

    Omitting ``usage_capture`` is the easy mistake; making it produce
    ``Unknown`` rather than zeros is what keeps that mistake safe.
    """
    endpoint = FakeEndpoint(replies=(_OK_REPLY,))
    provider = PydanticAiModelProvider(
        model=endpoint, runner=sync_runner, clock=FakeClock(), capabilities=_capabilities()
    )

    response = provider.send(ModelRequest(prompt="summarise"))
    assert response.usage.total_tokens == Unknown(reason=UnknownReason.PROVIDER_OMITTED)
