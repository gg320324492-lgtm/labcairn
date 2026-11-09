"""The refusal ladder, rehearsed end to end with a substitute behind the gate.

**What is under test.** Work orders §11 §4.8, left column, row 2 and row 4:
*rehearsal of the refusal ladder end to end with a substitute behind the gate*
and *the degraded-path witnesses with the substitute*. Every call in this
file lands on ``FakeEndpoint`` — no socket, no credential, no spend, no real
route. The phase-2 ``real_model_smoke = NOT RUN`` record is untouched.

The ladder, in the adapter's own order, with each rung's witness:

1. **Budget preflight, fail-closed** — a run whose budget carries no number
   is refused before a provider exists; a token ceiling with no probe record
   is refused as unevaluable; Q4's 20 / 50 000 shape is named in the run's
   fixture. Each refusal leaves ``endpoint.calls == []``.
2. **Probe-record gate** — a supplier name is not a capability. With no
   probe record the capability rung refuses before the wire; with a probed
   ``ProviderCapabilities`` the same case is sent exactly once.
3. **Consent bridge** — ``MODEL_REQUEST`` is the only ``Effect.NETWORK``
   capability, every outbound decision is ASK, a pending approval refuses,
   and an excerpt whose port is bound to a *different* digest does not leave.
4. **Capability refusal** — a probe record saying ``UNSUPPORTED`` for the
   capability the request needs refuses before the wire.

Then the degraded paths (budget, permission, timeout) and Q7's compound
stop-loss. Each rung is mutation-checked: break it and the named witness
reddens (the mutation script and its results are in the acceptance record).

**One measured boundary, stated rather than smoothed over.** A timeout is
the one degraded path that *does* reach the substitute: the fake records one
call, then hangs. §4.6 says "budget or permission failures cause no outbound
call; timeout and unavailability have explicit degraded paths" — the two
pre-wire failures are the ones the row says cause no call. This file asserts
zero calls for those two and, for the timeout, one call to the substitute,
a classified refusal, a stop-loss event and zero calls after it. No claim
that a request which already left caused no outbound call.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from provider_fakes import FakeEndpoint, Reply, sync_runner
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.application import ApplicationContext, create_task
from labcairn.application.approvals import (
    ApprovalRequest,
    ApprovalUse,
    grant_approval,
    request_approval,
)
from labcairn.application.outbound import OutboundApproval
from labcairn.core.ids import ApprovalId, new_id
from labcairn.core.providers.protocol import ModelRequest
from labcairn.core.providers.usage import Known
from labcairn.providers.adapter import prompt_digest
from labcairn.providers.bounded_run import (
    REHEARSAL_MAX_REQUESTS,
    REHEARSAL_MAX_TOTAL_TOKENS,
    BoundedRun,
    CompoundStopLoss,
    RunNotAuthorisedError,
    RunRequestRefusedError,
    StopLossTriggeredError,
    StopLossVerdict,
)
from labcairn.providers.budget import RunBudget
from labcairn.providers.capabilities import (
    ALL_CAPABILITIES,
    Capability,
    CapabilityOutcome,
    ProviderCapabilities,
)
from labcairn.providers.consent import OutboundConsent
from labcairn.providers.deidentify import (
    DeidentificationPipeline,
    DeidentifiedCase,
    SampleClass,
)
from labcairn.providers.errors import (
    OutboundRefusedError,
    ProviderTimeoutError,
)
from labcairn.providers.ledger import RunLedger
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import CAPABILITIES, CapabilityId, Effect, ModelRequestArgs
from labcairn.security.policy import Permission, PermissionPolicy, Rule, default_policy

pytestmark = pytest.mark.integration

env = _shared_env

MOMENT = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)
MATERIAL_REF = "proj-1/manuscript.txt"

#: The substitute's scripted answer, with a usage block so a token ceiling is
#: enforceable — the capture, not the upstream object, is the measured source.
_OK_REPLY = Reply(
    name="ok", text="the answer", usage_body={"input_tokens": 40, "output_tokens": 12}
)

MATERIAL = (
    "The green algae inhibition assay was repeated three times under identical "
    "lighting conditions and the results disagreed with the earlier published "
    "curve at every measured concentration point without exception or explanation."
)
CLEAN_RENDERING = (
    "Assay S-1 was run on three occasions; luminance held fixed. Its trace "
    "diverges from a prior reference trace across the dilution series. "
    "No mechanism is offered here."
)
RENDERED_EXCERPT = "Disagrees with a reference trace."


# --- the substitute-side fixtures -----------------------------------------


@pytest.fixture()
def context(env: StoreEnv, tmp_path: Any) -> ApplicationContext:
    """A task under a policy that ASKs — a question, not a denial."""
    workspace_root = tmp_path / "workspace"
    (workspace_root / "materials").mkdir(parents=True)
    created = create_task(
        store=env.store(),
        policy=PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")]),
        workspace_root=workspace_root,
        title="The refusal ladder rehearsal",
        goal=TaskGoal(
            objective="Send nothing until every rung of the ladder permits it.",
            success_criterion="An unauthorised request never reaches the substitute.",
        ),
        source_dirs=(workspace_root / "materials",),
    )
    return ApplicationContext(
        workspace=created.workspace,
        store=env.store(),
        policy=PermissionPolicy.from_rules([Rule(effect=Permission.ASK, pattern="**")]),
        ledger=ApprovalLedger(),
    )


def _probed(*, tool_calls: CapabilityOutcome = CapabilityOutcome.OK) -> ProviderCapabilities:
    """A probe record: the endpoint answered the capability questions."""
    outcomes = dict.fromkeys(ALL_CAPABILITIES, CapabilityOutcome.OK)
    outcomes[Capability.TOOL_CALLS] = tool_calls
    return ProviderCapabilities.from_outcomes(
        endpoint_fingerprint="substitute-fingerprint",
        model="scripted",
        protocol="fake",
        outcomes=outcomes,
        unsupported_reason=dict.fromkeys(ALL_CAPABILITIES, "the probe said no"),
    )


def _the_use(excerpts: tuple[str, ...]) -> ApprovalUse:
    """An approval bound to excerpt **digests**, never to excerpt text (Q3)."""
    return ApprovalUse(
        capability=CapabilityId.MODEL_REQUEST,
        arguments=ModelRequestArgs(
            provider="fake",
            model="scripted",
            path=MATERIAL_REF,
            excerpts=excerpts,
            purpose="bounded_rehearsal",
        ).model_dump(),
        root_id="source:0",
        resource_key=MATERIAL_REF,
    )


class DigestBoundPort:
    """A real approval-backed port, plus the digest its approval binds.

    ``require`` delegates to :class:`OutboundApproval`, so the ledger really
    moves the row to ``CONSUMED`` — a fake that merely returned would make
    the consent rung a sentiment. The extra attribute is the provider side's
    view of the same binding; the harness pairs it with the excerpt's digest.
    """

    def __init__(
        self,
        *,
        context: ApplicationContext,
        approval_id: ApprovalId,
        use: ApprovalUse,
        bound_excerpt_digest: str | None,
        at: datetime = MOMENT,
    ) -> None:
        self.bound_excerpt_digest = bound_excerpt_digest
        self._approval = OutboundApproval(context=context, approval_id=approval_id, use=use, at=at)

    def require(self, request: ModelRequest) -> None:
        self._approval.require(request)


def _ports(
    context: ApplicationContext,
    *,
    digests: tuple[str, ...],
    granted: bool = True,
    bind_first_digest: str | None = None,
) -> tuple[OutboundConsent, ...]:
    """One port per request. The prompt's port binds no excerpt digest.

    ``bind_first_digest`` deliberately mis-binds the excerpt port — the
    counter-mutation that "a different digest does not leave" watches.
    """
    ports: list[OutboundConsent] = []
    # Request 0: the case's prompt. Its approval's excerpts are empty.
    prompt_use = _the_use(())
    prompt_id = _approval_id(context, prompt_use, granted=granted)
    ports.append(
        DigestBoundPort(
            context=context,
            approval_id=prompt_id,
            use=prompt_use,
            bound_excerpt_digest=None,
        )
    )
    for index, digest in enumerate(digests):
        use = _the_use((digest,))
        approval_id = _approval_id(context, use, granted=granted)
        bound = bind_first_digest if index == 0 and bind_first_digest is not None else digest
        ports.append(
            DigestBoundPort(
                context=context,
                approval_id=approval_id,
                use=use,
                bound_excerpt_digest=bound,
            )
        )
    return tuple(ports)


def _approval_id(context: ApplicationContext, use: ApprovalUse, *, granted: bool) -> ApprovalId:
    asked = request_approval(
        context,
        ApprovalRequest(use=use, expires_at=MOMENT + timedelta(hours=1)),
        now=MOMENT,
    )
    if granted:
        grant_approval(context, asked.approval.approval_id, now=MOMENT)
    return asked.approval.approval_id


def _case() -> DeidentifiedCase:
    """A case minted by the pipeline — the only path to an outbound case."""
    return DeidentificationPipeline().redact_case(
        case_id="rehearsal-1",
        source_digest=hashlib.sha256(MATERIAL.encode("utf-8")).hexdigest(),
        material_text=MATERIAL,
        excerpts=("the assay disagreed with the curve",),
        rendered_prompt=CLEAN_RENDERING,
        rendered_excerpts=(RENDERED_EXCERPT,),
        sample_class=SampleClass.PUBLIC_SYNTHETIC,
    )


def _budget() -> RunBudget:
    """Q4's answered ceiling: 20 requests / 50 000 tokens."""
    return RunBudget(
        max_model_requests=REHEARSAL_MAX_REQUESTS,
        max_total_tokens=Known(REHEARSAL_MAX_TOTAL_TOKENS),
    )


def _run(
    endpoint: FakeEndpoint,
    *,
    capabilities: ProviderCapabilities | None = None,
    required: frozenset[Capability] | None = None,
    budget: RunBudget | None = None,
    timeout_s: float | None = None,
    stop_loss: CompoundStopLoss | None = None,
    max_requests: int = REHEARSAL_MAX_REQUESTS,
) -> BoundedRun:
    caps = _probed() if capabilities is None else capabilities
    return BoundedRun(
        model=endpoint,
        budget=_budget() if budget is None else budget,
        ledger=RunLedger(clock=lambda: 0.0, capabilities=caps, priced=False),
        capabilities=caps,
        required_capabilities=required,
        usage_capture=endpoint.capture,
        timeout_s=timeout_s,
        runner=sync_runner,
        stop_loss=stop_loss,
        max_requests=max_requests,
        clock=lambda: MOMENT,
    )


def _successful_case(
    context: ApplicationContext,
    endpoint: FakeEndpoint,
    **kwargs: Any,
) -> tuple[BoundedRun, DeidentifiedCase]:
    case = _case()
    run = _run(endpoint, **kwargs)
    run.submit_case(case, consents=_ports(context, digests=case.excerpt_digests))
    return run, case


# --- rung 1: budget preflight, fail-closed --------------------------------


def test_a_budget_without_the_number_refuses_before_a_request_exists(
    context: ApplicationContext,
) -> None:
    """Q4: "the preflight refuses without the number". Zero calls.

    Counter-mutation: make ``_budget_names_a_ceiling`` return ``True``.
    The run would then be built, the case sent, and this witness reddens.
    """
    endpoint = FakeEndpoint(replies=(_OK_REPLY, _OK_REPLY))
    with pytest.raises(RunNotAuthorisedError, match="names no ceiling"):
        _run(endpoint, budget=RunBudget())
    assert endpoint.calls == []


def test_a_token_ceiling_with_no_probe_record_is_unevaluable_and_refuses(
    context: ApplicationContext,
) -> None:
    """A ceiling nobody can measure is not a ceiling. Zero calls.

    The adapter's ``BudgetEnforcementUnavailableError`` is the fail-closed
    answer, and the recording upstream is the measurement.
    """
    endpoint = FakeEndpoint(replies=(_OK_REPLY, _OK_REPLY))
    unprobed = ProviderCapabilities.unverified(
        endpoint_fingerprint="substitute-fingerprint", model="scripted", protocol="fake"
    )
    run = _run(endpoint, capabilities=unprobed)
    case = _case()
    with pytest.raises(RunRequestRefusedError) as raised:
        run.submit_case(case, consents=_ports(context, digests=case.excerpt_digests))
    assert raised.value.kind.value == "budget_enforcement_unavailable"
    assert endpoint.calls == []
    assert run.record().requests_refused == 1


def test_the_answered_numbers_are_named_in_the_run_fixture() -> None:
    """20 / 50 000, as the owner answered them (§4.9, Q4)."""
    assert REHEARSAL_MAX_REQUESTS == 20
    assert REHEARSAL_MAX_TOTAL_TOKENS == 50_000
    assert _budget().max_model_requests == 20


def test_the_budget_ceiling_stops_the_run_before_the_wire_when_spent(
    context: ApplicationContext,
) -> None:
    """A spent request ceiling refuses the request before it is built."""
    endpoint = FakeEndpoint(replies=(_OK_REPLY,))
    run = _run(endpoint, budget=RunBudget(max_model_requests=0), required=frozenset())
    case = _case()
    with pytest.raises(RunRequestRefusedError) as raised:
        run.submit_case(case, consents=_ports(context, digests=case.excerpt_digests))
    assert raised.value.kind.value == "budget_exhausted"
    assert endpoint.calls == []


# --- rung 2: the probe-record gate ----------------------------------------


def test_a_supplier_name_is_not_a_capability(context: ApplicationContext) -> None:
    """No probe record → the capability rung refuses before the wire.

    Counter-mutation: hand the run a probed ``ProviderCapabilities`` instead
    of ``None``. The request would be issued, and ``endpoint.calls == []``
    would fail. The model label in a configuration is not a probe.
    """
    endpoint = FakeEndpoint(replies=(_OK_REPLY, _OK_REPLY))
    unprobed = ProviderCapabilities.unverified(
        endpoint_fingerprint="substitute-fingerprint", model="scripted", protocol="fake"
    )
    # A budget with no token ceiling, so the capability rung is the one that
    # decides — otherwise the undecidable ceiling would refuse first.
    run = _run(
        endpoint,
        capabilities=unprobed,
        required=frozenset({Capability.TOOL_CALLS}),
        budget=RunBudget(max_model_requests=REHEARSAL_MAX_REQUESTS),
    )
    case = _case()
    with pytest.raises(RunRequestRefusedError) as raised:
        run.submit_case(case, consents=_ports(context, digests=case.excerpt_digests))
    assert raised.value.kind.value == "capability_unavailable"
    assert endpoint.calls == []


def test_an_unsupported_capability_refuses_before_the_wire(
    context: ApplicationContext,
) -> None:
    """A probe record that said UNSUPPORTED blocks the required capability.

    Counter-mutation: change the probe record's TOOL_CALLS outcome to OK.
    The request would be issued and this witness reddens.
    """
    endpoint = FakeEndpoint(replies=(_OK_REPLY, _OK_REPLY))
    unsupported = _probed(tool_calls=CapabilityOutcome.UNSUPPORTED)
    run = _run(
        endpoint,
        capabilities=unsupported,
        required=frozenset({Capability.TOOL_CALLS}),
        budget=RunBudget(max_model_requests=REHEARSAL_MAX_REQUESTS),
    )
    case = _case()
    with pytest.raises(RunRequestRefusedError) as raised:
        run.submit_case(case, consents=_ports(context, digests=case.excerpt_digests))
    assert raised.value.kind.value == "capability_unavailable"
    assert endpoint.calls == []


def test_the_probed_substitute_sends_exactly_one_request_per_case_field(
    context: ApplicationContext,
) -> None:
    """Every rung permits a fully authorised case; the substitute sees 2 calls.

    This is the positive control. A ladder whose refusals are wired to
    ``send`` at all would leave this green while quietly refusing — so the
    recording upstream's call count is the measurement, not the absence of an
    exception.
    """
    endpoint = FakeEndpoint(replies=(_OK_REPLY, _OK_REPLY))
    run, case = _successful_case(context, endpoint)
    assert endpoint.call_count == 2
    record = run.record()
    assert record.requests_made == 2
    assert record.cases_completed == 1
    assert record.stop_loss is None
    # The exchange records carry digests and counts, never the case's text.
    exchanges = run.exchanges()
    assert len(exchanges) == 2
    for exchange in exchanges:
        assert exchange.prompt_digest == prompt_digest(
            case.safe_prompt if exchanges.index(exchange) == 0 else RENDERED_EXCERPT
        )
    assert all(
        RENDERED_EXCERPT not in str(exchange) and MATERIAL not in str(exchange)
        for exchange in exchanges
    )


# --- rung 3: the consent bridge -------------------------------------------


def test_model_request_is_the_only_network_capability_and_every_outbound_is_ask() -> None:
    """The bridge's static half: one NETWORK capability, ASK by default.

    ``providers/`` does not import the permission layer, so the rehearsal
    asserts this from the application side and the harness only ever sees a
    port. A second NETWORK capability, or an ALLOW default, would let an
    outbound request leave without anyone being asked.
    """
    network = [c for c, v in CAPABILITIES.items() if v.effect is Effect.NETWORK]
    assert network == [CapabilityId.MODEL_REQUEST]
    decision = default_policy().evaluate(
        task_id=None,
        capability=CapabilityId.MODEL_REQUEST,
        resource=_resource(),
    )
    assert decision.permission is Permission.ASK
    assert decision.effect is Effect.NETWORK


def _resource() -> Any:
    """The source-root resource a transmit grant is written against."""
    from pathlib import Path

    from labcairn.security.paths import RootKind
    from labcairn.security.policy import ResourceRef

    return ResourceRef(
        declared_key=MATERIAL_REF,
        resolved_key=MATERIAL_REF,
        root_id="source:0",
        root_kind=RootKind.SOURCE,
        real_path=Path("unused") / MATERIAL_REF,
    )


def test_a_pending_approval_refuses_without_reaching_the_substitute(
    context: ApplicationContext,
) -> None:
    """A question that was asked and not answered authorises nothing.

    Counter-mutation: grant the approvals. The substitute would see the call
    and ``endpoint.calls == []`` would fail.
    """
    endpoint = FakeEndpoint(replies=(_OK_REPLY, _OK_REPLY))
    case = _case()
    run = _run(endpoint)
    with pytest.raises(RunRequestRefusedError) as raised:
        run.submit_case(case, consents=_ports(context, digests=case.excerpt_digests, granted=False))
    assert raised.value.kind.value == "outbound_refused"
    assert endpoint.calls == []
    assert run.record().requests_refused == 1


def test_an_excerpt_port_bound_to_a_different_digest_does_not_leave(
    context: ApplicationContext,
) -> None:
    """Q3: each excerpt leaves only under its own digest-bound approval.

    Counter-mutation: remove the ``bound_excerpt_digest`` comparison in
    ``_before_request``. The excerpt would leave under the wrong approval and
    this witness reddens.
    """
    endpoint = FakeEndpoint(replies=(_OK_REPLY, _OK_REPLY))
    case = _case()
    run = _run(endpoint)
    with pytest.raises(RunNotAuthorisedError, match="different excerpt digest"):
        run.submit_case(
            case,
            consents=_ports(
                context,
                digests=case.excerpt_digests,
                bind_first_digest="0" * 64,
            ),
        )
    assert endpoint.calls == []


def test_one_port_for_several_requests_is_refused_whole() -> None:
    """A single-use approval does not cover a second request."""
    endpoint = FakeEndpoint(replies=(_OK_REPLY, _OK_REPLY))
    run = _run(endpoint)
    with pytest.raises(RunNotAuthorisedError, match="one consent port per request"):
        run.submit_case(_case(), consents=())
    assert endpoint.calls == []


def test_the_consent_rung_is_the_adapters_own_refusal_not_a_fake(
    context: ApplicationContext,
) -> None:
    """The port really raises ``OutboundRefusedError`` from the application side.

    A harness that swallowed the port's refusal and returned a made-up one
    would still be green on every zero-call assertion above. This drives the
    adapter directly with a missing approval and checks the error's kind.
    """
    from labcairn.providers.adapter import PydanticAiModelProvider

    endpoint = FakeEndpoint(replies=(_OK_REPLY,))
    port = DigestBoundPort(
        context=context,
        approval_id=ApprovalId(new_id()),
        use=_the_use(()),
        bound_excerpt_digest=None,
    )
    provider = PydanticAiModelProvider(
        model=endpoint,
        consent=port,
        runner=sync_runner,
        clock=lambda: 0.0,
        usage_capture=endpoint.capture,
        budget=RunBudget(max_model_requests=20),
    )
    with pytest.raises(OutboundRefusedError):
        provider.send(ModelRequest(prompt=CLEAN_RENDERING))
    assert endpoint.calls == []


# --- the degraded paths ---------------------------------------------------


def test_budget_refusal_causes_no_outbound_call(context: ApplicationContext) -> None:
    """Degraded path 1: budget. Zero calls, and the approval stays unspent.

    ``_ports`` granted two approvals. The budget rung runs before the consent
    port, so neither was spent — asking is not spending.
    """
    endpoint = FakeEndpoint(replies=(_OK_REPLY, _OK_REPLY))
    case = _case()
    ports = _ports(context, digests=case.excerpt_digests)
    run = _run(endpoint, budget=RunBudget(max_model_requests=0))
    with pytest.raises(RunRequestRefusedError):
        run.submit_case(case, consents=ports)
    assert endpoint.calls == []
    # A granted-but-unspent approval can still be consumed: the store's row
    # remains GRANTED. Drive one direct adapter send with the prompt's port.
    from labcairn.providers.adapter import PydanticAiModelProvider

    probe = PydanticAiModelProvider(
        model=endpoint,
        consent=ports[0],
        runner=sync_runner,
        clock=lambda: 0.0,
        usage_capture=endpoint.capture,
        budget=RunBudget(max_model_requests=20),
    )
    probe.send(ModelRequest(prompt=CLEAN_RENDERING))
    assert endpoint.call_count == 1


def test_permission_refusal_causes_no_outbound_call(context: ApplicationContext) -> None:
    """Degraded path 2: permission. Zero calls, classified OUTBOUND_REFUSED."""
    endpoint = FakeEndpoint(replies=(_OK_REPLY, _OK_REPLY))
    case = _case()
    run = _run(endpoint)
    with pytest.raises(RunRequestRefusedError) as raised:
        run.submit_case(case, consents=_ports(context, digests=case.excerpt_digests, granted=False))
    assert raised.value.kind.value == "outbound_refused"
    assert endpoint.calls == []


def test_a_timeout_has_an_explicit_degraded_path_and_stops_after_three(
    context: ApplicationContext,
) -> None:
    """Degraded path 3: timeout. One call per attempt, then the stop-loss.

    The fake hangs; ``asyncio.wait_for`` bounds it; the refusal is classified
    TIMEOUT; Q7's first arm counts it as an issued-and-failed request, and on
    the third consecutive one the run stops before a fourth call. The
    acceptance record states this measured boundary plainly: §4.6 promises
    "explicit degraded paths" for timeout, not zero calls. Budget and
    permission refusals are the two paths whose zero-call claim is measured.
    """
    endpoint = FakeEndpoint(replies=tuple(Reply(name="hangs", hangs=True) for _ in range(3)))
    case = _case()
    loss = CompoundStopLoss()
    run = _run(
        endpoint,
        timeout_s=0.05,
        budget=RunBudget(max_model_requests=20),
        stop_loss=loss,
    )
    for _ in range(3):
        with pytest.raises(RunRequestRefusedError) as raised:
            run.submit_case(case, consents=_ports(context, digests=case.excerpt_digests))
        assert raised.value.kind.value == "timeout"
    assert endpoint.call_count == 3
    assert run.record().requests_failed == 3
    assert run.record().requests_made == 0
    assert loss.verdict is StopLossVerdict.STOP_CONSECUTIVE_FAILURES
    with pytest.raises(StopLossTriggeredError):
        run.submit_case(case, consents=_ports(context, digests=case.excerpt_digests))
    assert endpoint.call_count == 3


def test_a_timeout_error_is_the_adapters_own_class(context: ApplicationContext) -> None:
    """The degraded path is the adapter's classified refusal, not a bare raise."""
    from labcairn.providers.adapter import PydanticAiModelProvider

    endpoint = FakeEndpoint(replies=(Reply(name="hangs", hangs=True),))
    provider = PydanticAiModelProvider(
        model=endpoint,
        consent=_ports(context, digests=())[0],
        runner=sync_runner,
        clock=lambda: 0.0,
        usage_capture=endpoint.capture,
        budget=RunBudget(max_model_requests=20),
        timeout_s=0.05,
    )
    with pytest.raises(ProviderTimeoutError):
        provider.send(ModelRequest(prompt=CLEAN_RENDERING))
    assert endpoint.call_count == 1


# --- Q7: the compound stop-loss ------------------------------------------


def test_three_consecutive_failures_fire_the_first_arm_and_a_success_resets_it() -> None:
    """Arm one's own arithmetic: three consecutive failures stop; a success resets.

    Counter-mutation: make ``record_failure`` a no-op. The third verdict
    stays HOLD and this witness reddens. The success assertion watches the
    counter's reset rather than trusting the word "consecutive".
    """
    loss = CompoundStopLoss()
    assert loss.record_failure("c1") is StopLossVerdict.HOLD
    assert loss.record_failure("c1") is StopLossVerdict.HOLD
    assert loss.record_failure("c1") is StopLossVerdict.STOP_CONSECUTIVE_FAILURES

    reset = CompoundStopLoss()
    assert reset.record_failure("c1") is StopLossVerdict.HOLD
    assert reset.record_failure("c1") is StopLossVerdict.HOLD
    assert reset.record_success("c1") is StopLossVerdict.HOLD
    assert reset.record_failure("c1") is StopLossVerdict.HOLD


def test_the_first_arm_fires_on_three_real_substitute_failures(
    context: ApplicationContext,
) -> None:
    """The measured version of arm one, with real ports and a failing fake."""
    endpoint = FakeEndpoint(replies=(), always_raises=RuntimeError("the substitute is unavailable"))
    loss = CompoundStopLoss()
    run = _run(endpoint, stop_loss=loss, budget=RunBudget(max_model_requests=20))
    case = _case()
    for _ in range(3):
        with pytest.raises(RunRequestRefusedError):
            run.submit_case(case, consents=_ports(context, digests=case.excerpt_digests))
    assert endpoint.call_count == 3
    assert loss.verdict is StopLossVerdict.STOP_CONSECUTIVE_FAILURES
    assert run.record().requests_failed == 3
    with pytest.raises(StopLossTriggeredError, match="stop_consecutive_failures"):
        run.submit_case(case, consents=_ports(context, digests=case.excerpt_digests))
    assert endpoint.call_count == 3


def test_a_per_case_refusal_rate_above_half_fires_the_second_arm(
    context: ApplicationContext,
) -> None:
    """One refused request in a one-request case is rate 1.0 → stop.

    Counter-mutation: remove ``OUTBOUND_REFUSED`` from ``PRE_WIRE_KINDS``.
    The refusal would be counted as a failure, arm two would stay asleep and
    the verdict assertion reddens.
    """
    endpoint = FakeEndpoint(replies=(_OK_REPLY, _OK_REPLY))
    loss = CompoundStopLoss()
    run = _run(endpoint, stop_loss=loss)
    case = _case()
    with pytest.raises(RunRequestRefusedError):
        run.submit_case(case, consents=_ports(context, digests=case.excerpt_digests, granted=False))
    assert loss.verdict is StopLossVerdict.STOP_REFUSAL_RATE
    assert loss.case_refusal_rate(case.case_id) == 1.0
    assert endpoint.calls == []
    with pytest.raises(StopLossTriggeredError, match="stop_refusal_rate"):
        run.submit_case(case, consents=_ports(context, digests=case.excerpt_digests))
    assert endpoint.calls == []


def test_the_record_carries_digests_and_counts_never_text(
    context: ApplicationContext,
) -> None:
    """Q3: the run record is safe to export without a disclosure review."""
    endpoint = FakeEndpoint(replies=(_OK_REPLY, _OK_REPLY))
    run, case = _successful_case(context, endpoint)
    record = run.record()
    serialised = repr(record)
    assert CLEAN_RENDERING not in serialised
    assert RENDERED_EXCERPT not in serialised
    assert MATERIAL not in serialised
    assert record.requests[1].excerpt_digest == case.excerpt_digests[0]
    assert record.requests[1].request_digest == case.excerpt_digests[0]
    assert record.to_counts()["requests_made"] == 2
