"""The three real-run machinery repairs, watched without a provider call.

LC-P2-14's single-case calibration exposed three gaps: a shared keep-alive
connection reused across the adapter's fresh event loops, an approval spent
before a request reached the wire, and an output with no completeness gate.
The arrangement pair also had configuration checks but no runnable path.

Every witness in this file is synthetic: no credential, no network, no model.
W1 reproduces the event-loop fault on a loopback HTTP/1.1 server and proves
that the client the product builds survives six fresh loops. W2 and W3 use
recording fakes to measure the approval ledger and the provider's output
settings. W4 walks the two B variants through the driver and refuses the
shapes the protocol does not define.
"""

from __future__ import annotations

import asyncio
import http.server
import importlib.util
import json
import socketserver
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar
from uuid import UUID

import httpx
import pytest
from evaluation import arms as arm_module
from evaluation import blind_runner
from provider_fakes import FakeEndpoint, PermissiveConsent, Reply, sync_runner
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.application import ApplicationContext, create_task
from labcairn.application.approvals import (
    ApprovalRequest,
    ApprovalUse,
    grant_approval,
    request_approval,
)
from labcairn.core.ids import ApprovalId
from labcairn.core.providers.protocol import ModelRequest
from labcairn.core.providers.usage import Known
from labcairn.providers.adapter import PydanticAiModelProvider
from labcairn.providers.budget import RunBudget
from labcairn.providers.consent import WireAuthorizedConsent
from labcairn.providers.credentials import Protocol, ProviderSettings
from labcairn.providers.errors import (
    OutboundRefusedError,
    ProviderError,
    ProviderOutputTruncatedError,
)
from labcairn.providers.pydantic_models import build_http_client, make_sniffer
from labcairn.providers.usage_capture import HttpxUsageSniffer
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.runtime.operation import ApprovalState
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import CapabilityId, ModelRequestArgs
from labcairn.security.policy import Permission, PermissionPolicy, Rule

pytestmark = pytest.mark.integration

env = _shared_env
MOMENT = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
MATERIAL_REF = "proj-1/manuscript.txt"


# --- W1: the shared client across fresh loops -------------------------------


class _KeepAliveHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    bodies: ClassVar[list[dict[str, Any]]] = []

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        self.bodies.append(json.loads(self.rfile.read(length) or b"{}"))
        body = json.dumps(
            {
                "ok": True,
                "usage": {
                    "prompt_tokens": 2,
                    "completion_tokens": 1,
                    "total_tokens": 3,
                },
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: Any) -> None:
        return None


class _LoopServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


@contextmanager
def _loopback_server() -> Iterator[str]:
    _KeepAliveHandler.bodies = []
    server = _LoopServer(("127.0.0.1", 0), _KeepAliveHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/wire"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _run_six_loops(client: httpx.AsyncClient, url: str) -> list[str]:
    outcomes: list[str] = []

    async def one() -> None:
        response = await client.post(url, json={"call": len(outcomes)})
        assert response.status_code == 200

    for _ in range(6):
        try:
            asyncio.run(one())
        except RuntimeError as error:
            outcomes.append(f"{type(error).__name__}: {error}")
        else:
            outcomes.append("OK")
    asyncio.run(client.aclose())
    return outcomes


def _cli_module() -> Any:
    """Load the executable run driver without importing its module name twice."""
    path = Path(__file__).resolve().parent.parent / "scripts" / "run_blind_evaluation.py"
    spec = importlib.util.spec_from_file_location("run_blind_evaluation_machinery", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_real_run_cli_builds_a_no_keep_alive_sniffer() -> None:
    """The driver's own sniffer must not reconstruct the faulty transport."""
    sniffer = _cli_module()._build_sniffer()
    assert sniffer is not None
    assert sniffer.inner._pool._max_keepalive_connections == 0


def test_a_pooled_keep_alive_client_reproduces_the_calibration_fault() -> None:
    """The old client shape really fails on the second fresh event loop."""
    with _loopback_server() as url:
        client: httpx.AsyncClient = httpx.AsyncClient(timeout=5.0)
        outcomes = _run_six_loops(client, url)
    assert [outcome.startswith("RuntimeError") for outcome in outcomes] == [
        False,
        True,
        False,
        True,
        False,
        True,
    ]
    assert any("Event loop is closed" in outcome for outcome in outcomes)


def test_the_product_client_has_no_pooled_keep_alive_connections() -> None:
    """Six sequential sends survive the adapter's per-send fresh loop.

    Both client shapes are measured: the plain client and the sniffer-wrapped
    transport the real calibration uses. ``AsyncClient(limits=...)`` does not
    configure a supplied transport's own pool, so a witness that tried only
    the plain client would stay green while the real run still failed.
    """
    settings = ProviderSettings(protocol=Protocol.OPENAI, model="test-model")
    for sniffer in (None, make_sniffer()):
        with _loopback_server() as url:
            client = build_http_client(settings, sniffer=sniffer)
            assert client._transport is not None
            assert isinstance(client, httpx.AsyncClient)
            inner = getattr(client._transport, "inner", client._transport)
            assert inner._pool._max_keepalive_connections == 0
            outcomes = _run_six_loops(client, url)
        assert outcomes == ["OK"] * 6
        assert len(_KeepAliveHandler.bodies) == 6


# --- W2: approval spent only after the wire answered -----------------------


@pytest.fixture()
def context(env: StoreEnv, tmp_path: Path) -> ApplicationContext:
    workspace_root = tmp_path / "workspace"
    materials = workspace_root / "materials"
    materials.mkdir(parents=True)
    created = create_task(
        store=env.store(),
        policy=PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")]),
        workspace_root=workspace_root,
        title="The wire-authorized run",
        goal=TaskGoal(
            objective="Spend an approval only for a response that came back.",
            success_criterion="A local fault leaves the approval granted.",
        ),
        source_dirs=(materials,),
    )
    return ApplicationContext(
        workspace=created.workspace,
        store=env.store(),
        policy=PermissionPolicy.from_rules([Rule(effect=Permission.ASK, pattern="**")]),
        ledger=ApprovalLedger(),
    )


def _the_use() -> ApprovalUse:
    return ApprovalUse(
        capability=CapabilityId.MODEL_REQUEST,
        arguments=ModelRequestArgs(
            provider="fake",
            model="scripted",
            path=MATERIAL_REF,
            excerpts=(),
            purpose="blind_evaluation",
        ).model_dump(),
        root_id="source:0",
        resource_key=MATERIAL_REF,
    )


def _granted(context: ApplicationContext) -> ApprovalId:
    asked = request_approval(
        context,
        ApprovalRequest(use=_the_use(), expires_at=MOMENT + timedelta(hours=1)),
        now=MOMENT,
    )
    return grant_approval(context, asked.approval.approval_id, now=MOMENT).approval.approval_id


@dataclass(slots=True)
class _CapturingUpstream:
    """A fake upstream whose wire response drives the real sniffer callback."""

    sniffer: HttpxUsageSniffer | None = None
    calls: list[Any] | None = None
    fail: bool = False
    finish_reason: str | None = "stop"
    #: Per-call switches for the "one response bypassed the wire" witness.
    observe_on: tuple[bool, ...] = ()

    def __post_init__(self) -> None:
        if self.calls is None:
            self.calls = []

    def observe(self, *, call_index: int) -> None:
        if self.sniffer is None:
            return
        if self.observe_on and not self.observe_on[call_index]:
            return
        self.sniffer.observe({"usage": {"input_tokens": 10, "output_tokens": 2}})

    def settings_seen(self) -> list[Any]:
        return self.calls if self.calls is not None else []

    @property
    def model_name(self) -> str:
        return "wire-fake"

    async def request(
        self, messages: Any, model_settings: Any, model_request_parameters: Any
    ) -> Any:
        del messages, model_request_parameters
        call_index = len(self.settings_seen())
        self.settings_seen().append(model_settings)
        if self.fail:
            raise RuntimeError("Event loop is closed")
        self.observe(call_index=call_index)
        return _UpstreamResponse(text="A complete answer.", finish_reason=self.finish_reason)


@dataclass(frozen=True, slots=True)
class _UpstreamResponse:
    text: str
    finish_reason: str | None

    @property
    def parts(self) -> tuple[Any, ...]:
        from pydantic_ai.messages import TextPart

        return (TextPart(content=self.text),)

    @property
    def timestamp(self) -> datetime:
        return MOMENT


def _wire_provider(
    context: ApplicationContext,
    approvals: Sequence[ApprovalId],
    upstream: _CapturingUpstream,
) -> tuple[PydanticAiModelProvider, blind_runner.ConsumingApprovals]:
    consent = blind_runner.ConsumingApprovals(
        context,
        tuple(
            blind_runner.ApprovalGrant(UUID(str(approval)), _the_use()) for approval in approvals
        ),
        clock=lambda: MOMENT,
    )
    assert isinstance(consent, WireAuthorizedConsent)
    sniffer = HttpxUsageSniffer(object(), on_observed=consent.authorize_wire)
    upstream.sniffer = sniffer
    provider = PydanticAiModelProvider(
        model=upstream,
        consent=consent,
        runner=sync_runner,
        clock=lambda: 0.0,
        usage_capture=sniffer,
        budget=RunBudget(max_model_requests=2),
        max_output_tokens=12000,
    )
    return provider, consent


def _state(context: ApplicationContext, approval: ApprovalId) -> ApprovalState:
    with context.store.session as session:
        del session
    row = context.ledger.peek(approval)
    assert row is not None
    return row.approval.state


def test_a_local_fault_before_the_wire_does_not_spend_the_approval(
    context: ApplicationContext,
) -> None:
    """A closed-loop fault leaves one granted approval and consumes none."""
    approval = _granted(context)
    upstream = _CapturingUpstream(sniffer=None, fail=True)
    provider, consent = _wire_provider(context, (approval,), upstream)

    with pytest.raises(ProviderError):
        provider.send(ModelRequest(prompt="A question."))

    assert _state(context, approval) is ApprovalState.GRANTED
    assert consent.spent == 0
    assert consent.remaining == 1


def test_a_measured_response_spends_exactly_one_approval(
    context: ApplicationContext,
) -> None:
    """The sniffer's observation is what consumes the reserved approval."""
    approval = _granted(context)
    upstream = _CapturingUpstream(sniffer=None)
    provider, consent = _wire_provider(context, (approval,), upstream)

    response = provider.send(ModelRequest(prompt="A question."))

    assert response.text == "A complete answer."
    assert _state(context, approval) is ApprovalState.CONSUMED
    assert consent.spent == 1
    assert isinstance(response.usage.input_tokens, Known)


def test_two_consecutive_measured_calls_each_spend_their_own_approval(
    context: ApplicationContext,
) -> None:
    """The five-arm path spends one fresh approval on each measured call."""
    first, second = _granted(context), _granted(context)
    upstream = _CapturingUpstream(sniffer=None)
    provider, consent = _wire_provider(context, (first, second), upstream)

    assert provider.send(ModelRequest(prompt="First arm.")).text == "A complete answer."
    assert provider.send(ModelRequest(prompt="Second arm.")).text == "A complete answer."

    assert _state(context, first) is ApprovalState.CONSUMED
    assert _state(context, second) is ApprovalState.CONSUMED
    assert consent.spent == 2
    assert consent.remaining == 0


def test_a_stale_wire_observation_cannot_authorize_the_next_response(
    context: ApplicationContext,
) -> None:
    """The second call is refused if its own response bypassed the wire."""
    first, second = _granted(context), _granted(context)
    upstream = _CapturingUpstream(sniffer=None, observe_on=(True, False))
    provider, consent = _wire_provider(context, (first, second), upstream)

    assert provider.send(ModelRequest(prompt="First arm.")).text == "A complete answer."
    with pytest.raises(OutboundRefusedError):
        provider.send(ModelRequest(prompt="Second arm."))

    assert _state(context, first) is ApprovalState.CONSUMED
    assert _state(context, second) is ApprovalState.GRANTED
    assert consent.spent == 1
    assert consent.remaining == 1


def test_a_response_without_wire_authorization_is_refused(
    context: ApplicationContext,
) -> None:
    """An answer that bypassed the sniffer cannot become a blind artefact."""
    approval = _granted(context)
    upstream = _CapturingUpstream(sniffer=None)
    provider, consent = _wire_provider(context, (approval,), upstream)
    upstream.sniffer = None  # the response arrives without a wire observation

    with pytest.raises(OutboundRefusedError) as raised:
        provider.send(ModelRequest(prompt="A question."))
    assert "wire observation" in raised.value.reason

    assert _state(context, approval) is ApprovalState.GRANTED
    assert consent.spent == 0


# --- W3: the output constraint and the refusal of truncated answers --------


def test_the_output_ceiling_reaches_the_provider_settings() -> None:
    """The provider sends a bounded output and a low reasoning depth."""
    endpoint = FakeEndpoint(
        replies=(
            Reply(
                name="bounded",
                text="A complete answer.",
                usage_body={"input_tokens": 1, "output_tokens": 1},
            ),
        )
    )
    provider = PydanticAiModelProvider(
        model=endpoint,
        consent=PermissiveConsent(),
        runner=sync_runner,
        usage_capture=endpoint.capture,
        max_output_tokens=12000,
        reasoning_effort="low",
    )

    response = provider.send(ModelRequest(prompt="A question."))

    settings = endpoint.calls[0].model_settings
    assert settings is not None
    assert settings["max_tokens"] == 12000
    assert settings["openai_reasoning_effort"] == "low"
    assert response.text == "A complete answer."


def test_a_length_limited_reply_is_refused_before_it_becomes_an_artifact(
    tmp_path: Path,
) -> None:
    """A constructed long/truncated response is unusable, not a scored answer."""
    endpoint = FakeEndpoint(
        replies=(
            Reply(
                name="truncated",
                text="An answer cut off in the middle",
                finish_reason="length",
                usage_body={"input_tokens": 1, "output_tokens": 12000},
            ),
        )
    )
    provider = PydanticAiModelProvider(
        model=endpoint,
        consent=PermissiveConsent(),
        runner=sync_runner,
        usage_capture=endpoint.capture,
        max_output_tokens=12000,
    )

    with pytest.raises(ProviderOutputTruncatedError) as raised:
        provider.send(ModelRequest(prompt="A question."))
    assert raised.value.finish_reason == "length"
    assert raised.value.max_output_tokens == 12000

    # The refusal happens in the provider, before any blind artefact can exist.
    assert not (tmp_path / "blind_packet.json").exists()
    assert not (tmp_path / "artifacts").exists()
    assert endpoint.call_count == 1


def test_a_truncated_response_is_unusable_in_a_full_dry_run_path(
    tmp_path: Path,
) -> None:
    """The driver's own artifact writer never sees a length-limited answer."""
    endpoint = FakeEndpoint(
        replies=(
            Reply(
                name="truncated",
                text="An answer cut off in the middle",
                finish_reason="length",
                usage_body={"input_tokens": 1, "output_tokens": 12000},
            ),
        )
    )
    provider = PydanticAiModelProvider(
        model=endpoint,
        consent=PermissiveConsent(),
        runner=sync_runner,
        usage_capture=endpoint.capture,
        max_output_tokens=12000,
    )
    arms = blind_runner.default_arms(model="test-model", budget="max_model_requests=1")

    with pytest.raises(ProviderOutputTruncatedError):
        blind_runner._record_artifacts(provider, arms, blind_runner.synthetic_cases()[:1])
    assert not (tmp_path / "artifacts").exists()


# --- W4: the two B variants have a runnable path ---------------------------


def test_the_arrangement_pair_is_a_legal_same_id_configuration() -> None:
    """Two B variants differing only in roles pass the protocol's own check."""
    pair = blind_runner.arrangement_arms(model="test-model", budget="max_model_requests=2")
    assert len(pair) == 2
    assert pair[0].arm_id == pair[1].arm_id == "B"
    assert pair[0].inputs == pair[1].inputs
    assert pair[0].roles != pair[1].roles
    assert arm_module.assess_arrangement_set(pair).admissible
    five_arm_view = arm_module.assess_configuration(pair)
    assert not five_arm_view.admissible
    assert any("two arms share one arm_id" in item for item in five_arm_view.violations)


def test_the_arrangement_pair_runs_two_anonymous_answers_per_case(
    tmp_path: Path,
) -> None:
    """The runnable path carries roles into prompts, item ids and unblinding."""
    pair = blind_runner.arrangement_arms(model="test-model", budget="max_model_requests=2")
    cases = blind_runner.synthetic_cases()[:1]
    summary = blind_runner.run_dry(out_dir=tmp_path, cases=cases, arms=pair)

    assert summary.stub_calls == 2
    assert len(summary.artifacts) == 2
    assert len({artifact.item_id for artifact in summary.artifacts}) == 2
    assert all(artifact.arm_id == "B" for artifact in summary.artifacts)
    assert {artifact.roles for artifact in summary.artifacts} == {
        pair[0].roles,
        pair[1].roles,
    }
    prompts = [blind_runner.render_prompt(cases[0], arm) for arm in pair]
    assert prompts[0] != prompts[1]
    assert "independent critique role" in prompts[1]
    unblinding = json.loads((tmp_path / "unblinding.json").read_text(encoding="utf-8"))
    roles = {tuple(entry["roles"]) for entry in unblinding["items"].values()}
    assert roles == {pair[0].roles, pair[1].roles}
    report = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    assert len(report["significance"]["contrasts"]) == 1
    assert report["significance"]["contrasts"][0]["contrast"] == "B+C vs B-only"


def test_a_five_arm_b_and_an_arrangement_b_only_answer_have_distinct_ids() -> None:
    """Two independent calls with the same arm, case and role stay distinct.

    The 12-case scaling run found this collision: the five-arm B and the
    arrangement pair's B-only answer had the same arm id, case and guidance
    role, so the old digest gave them one anonymous item and one artifact
    overwrote the other. The run scope is now part of the digest and the
    unblinding provenance.
    """
    case = blind_runner.synthetic_cases()[0]
    five = blind_runner.item_id_for("B", case.case_id, ("guidance",), "five_arm")
    alone = blind_runner.item_id_for("B", case.case_id, ("guidance",), "arrangement_pair")
    assert five != alone

    endpoint = FakeEndpoint(
        replies=(
            Reply(
                name="five",
                text="five-arm answer",
                usage_body={"input_tokens": 1, "output_tokens": 1},
            ),
            Reply(
                name="arrangement",
                text="arrangement answer",
                usage_body={"input_tokens": 1, "output_tokens": 1},
            ),
        )
    )
    provider = PydanticAiModelProvider(
        model=endpoint,
        consent=PermissiveConsent(),
        runner=sync_runner,
        usage_capture=endpoint.capture,
    )
    arms = (blind_runner.arrangement_arms(model="test-model", budget="max_model_requests=2")[0],)
    five_artifacts, _ = blind_runner._record_artifacts(
        provider, arms, (case,), run_scope="five_arm"
    )
    pair_artifacts, _ = blind_runner._record_artifacts(
        provider, arms, (case,), run_scope="arrangement_pair"
    )
    assert five_artifacts[0].item_id == five
    assert pair_artifacts[0].item_id == alone
    assert five_artifacts[0].run_scope == "five_arm"
    assert pair_artifacts[0].run_scope == "arrangement_pair"


def test_a_dry_run_rides_its_run_scope_through(tmp_path: Path) -> None:
    """The dry run's anonymous items live in the run scope the caller names.

    A second unseen paper runs the same case shape under its own scope: a
    dry run that ignored the scope would mint the first paper's item ids
    for the second paper's answers, and two papers would share one
    blind-sheet namespace.
    """
    case = blind_runner.synthetic_cases()[0]
    blind_runner.run_dry(out_dir=tmp_path / "scoped", cases=[case], run_scope="five_arm_unseen2")
    blind_runner.run_dry(out_dir=tmp_path / "plain", cases=[case])
    scoped = json.loads((tmp_path / "scoped" / "unblinding.json").read_text(encoding="utf-8"))
    plain = json.loads((tmp_path / "plain" / "unblinding.json").read_text(encoding="utf-8"))
    assert set(scoped["items"]) != set(plain["items"])
    assert {entry["run_scope"] for entry in scoped["items"].values()} == {"five_arm_unseen2"}
    assert {entry["run_scope"] for entry in plain["items"].values()} == {"five_arm"}


def test_the_driver_rides_its_run_scope_through(tmp_path: Path) -> None:
    """``--run-scope`` reaches the dry run; leaving it out keeps the default."""
    module = _cli_module()
    argv = [
        "--mode",
        "dry-run",
        "--out",
        str(tmp_path / "scoped"),
        "--run-scope",
        "five_arm_unseen2",
    ]
    assert module._dry_run(module._parser().parse_args(argv)) == module.EXIT_OK
    argv_default = ["--mode", "dry-run", "--out", str(tmp_path / "plain")]
    assert module._dry_run(module._parser().parse_args(argv_default)) == module.EXIT_OK
    scoped = json.loads((tmp_path / "scoped" / "unblinding.json").read_text(encoding="utf-8"))
    plain = json.loads((tmp_path / "plain" / "unblinding.json").read_text(encoding="utf-8"))
    assert {entry["run_scope"] for entry in scoped["items"].values()} == {"five_arm_unseen2"}
    assert {entry["run_scope"] for entry in plain["items"].values()} == {"five_arm"}
    assert set(scoped["items"]) != set(plain["items"])


def test_a_pair_that_moves_evidence_is_refused_by_the_driver(
    tmp_path: Path,
) -> None:
    """The runnable path does not relax the same-evidence rule."""
    alone, critiqued = blind_runner.arrangement_arms(
        model="test-model", budget="max_model_requests=2"
    )
    altered = arm_module.ArmConfiguration(
        arm_id="B",
        model=alone.model,
        budget=alone.budget,
        inputs=arm_module.EXPECTED_INPUTS["C"],
        roles=critiqued.roles,
    )
    with pytest.raises(blind_runner.RunRefusedError, match="exactly the protocol's B evidence"):
        blind_runner.run_dry(
            out_dir=tmp_path,
            cases=blind_runner.synthetic_cases()[:1],
            arms=(alone, altered),
        )


def test_three_b_variants_are_not_an_arrangement_pair(tmp_path: Path) -> None:
    """A third variant is refused; there is no silent fallback to five arms."""
    pair = blind_runner.arrangement_arms(model="test-model", budget="max_model_requests=2")
    triple = (*pair, pair[1])
    with pytest.raises(blind_runner.RunRefusedError, match="two arms share one arm_id"):
        blind_runner.run_dry(
            out_dir=tmp_path,
            cases=blind_runner.synthetic_cases()[:1],
            arms=triple,
        )
    assert not arm_module.assess_arrangement_set(triple).admissible
