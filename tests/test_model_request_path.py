"""The model-call path, watched.

**What is under test.** LC-P2-01: one product operation that asks a
declared model and records what came back, under the repository's
existing consent, budget, capability and refusal machinery — with the
bridge at the caller, so ``providers/`` keeps its disjointness from the
permission layer.

**And a fresh checkout cannot spend money by accident.** The dependency
is declared, and the tree carries no model.
"""

from __future__ import annotations

import json
import re
import tomllib
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from test_store_support import StoreEnv
from test_store_support import env as _shared_env

from labcairn.application import create_task
from labcairn.application.approvals import (
    ApprovalRequest,
    ApprovalUse,
    grant_approval,
    request_approval,
)
from labcairn.application.context import ApplicationContext
from labcairn.application.events import read_events
from labcairn.application.model_request import ModelInvocation, request_model
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.core.ids import ApprovalId
from labcairn.core.providers.usage import Unknown, UnknownReason
from labcairn.core.schema import LabCairnModel
from labcairn.db.repository import list_approvals
from labcairn.providers.budget import RunBudget
from labcairn.providers.capabilities import (
    ALL_CAPABILITIES,
    Capability,
    CapabilityOutcome,
    ProviderCapabilities,
)
from labcairn.providers.errors import BudgetEnforcementUnavailableError, ProviderTimeoutError
from labcairn.providers.ledger import LedgerSnapshot
from labcairn.runtime.event import EventType
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import CapabilityId, ModelRequestArgs
from labcairn.security.permissions import Grant
from labcairn.security.policy import Permission, PermissionPolicy, Rule

pytestmark = pytest.mark.integration

env = _shared_env

#: The suppliers the capability probe has measured, by the strings that
#: would mark a written configuration: a model id, and the endpoint a
#: configuration would carry. **The list grows only when the owner
#: authorises a supplier** — a supplier that is not authorised has no
#: entry, and an authorised one arrives here by editing this tuple, which
#: is a review of the writing, not an accident of it. ``api.minimax.cn``
#: is deliberately absent: it is already the destination the consent
#: demonstration sends *against* — data in an example, not configuration.
WRITTEN_MODEL_MARKERS: tuple[str, ...] = (
    "MiniMax-M3.1-Flash",
    "dashscope.aliyuncs",
)


def _pyproject(repo_root: Path) -> dict[str, Any]:
    """The parsed ``pyproject.toml``."""
    return tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))


def test_httpx_is_a_declared_dependency(repo_root: Path) -> None:
    """The HTTP client the provider path runs on is a version this project chose.

    It arrived transitively through ``pydantic-ai`` and was declared by
    nobody; the provider path is built on it, so it belongs in the
    runtime dependencies, and the lockfile moves with the declaration.
    """
    pyproject = _pyproject(repo_root)
    declared = [
        line for line in pyproject["project"]["dependencies"] if re.match(r"^httpx[\s>=<~!]", line)
    ]
    assert declared, "httpx is not in the runtime dependencies"

    lock = tomllib.loads((repo_root / "uv.lock").read_text(encoding="utf-8"))
    root = next(package for package in lock["package"] if package["name"] == "labcairn")
    assert any(dep["name"] == "httpx" for dep in root["dependencies"]), (
        "the lockfile's root package does not depend on httpx"
    )
    locked = next(package for package in lock["package"] if package["name"] == "httpx")
    major, minor = (int(part) for part in locked["version"].split(".")[:2])
    assert (major, minor) >= (0, 27), f"httpx {locked['version']} is outside the declared range"


def test_no_model_id_endpoint_or_price_is_written_into_the_tree(repo_root: Path) -> None:
    """A supplier's identity is the operator's configuration, never the tree's.

    The repository's own configuration is the fake default: no
    ``configs/`` directory exists, because a configuration file is an
    operator's act. And no source file, example or project metadata
    carries a model id or a supplier endpoint — the probe's measured
    answers live in the store and the work orders' measurement
    histories, which are records, not configuration.
    """
    configs = repo_root / "configs"
    assert not configs.exists(), (
        "configs/ exists; the repository ships no configuration, and an"
        " operator's providers.json lives in a workspace, not in the tree"
    )
    surfaces = [
        repo_root / "pyproject.toml",
        *(path for path in (repo_root / "src").rglob("*.py")),
        *(path for path in (repo_root / "examples").rglob("*.py")),
    ]
    for surface in surfaces:
        text = surface.read_text(encoding="utf-8")
        for marker in WRITTEN_MODEL_MARKERS:
            assert marker not in text, f"{surface.name} carries {marker!r}"


# --------------------------------------------------------------------------- #
# the bridge: the material gate first, then the approval (LC-P2-01 T01)
# --------------------------------------------------------------------------- #

MOMENT = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)

#: The destination a permitted request sends to. An example domain, the
#: way the consent demonstration's own destination is one.
DESTINATION = "api.model-provider.example"

MATERIAL_REF = "proj-1/manuscript.txt"


def _model_use() -> ApprovalUse:
    """What a model call is spent on — the capability whose payload leaves.

    The arguments are the request's canonical form: the digest is
    recomputed over them at the moment of use, so an approval to send
    one excerpt set does not authorise another.
    """
    return ApprovalUse(
        capability=CapabilityId.MODEL_REQUEST,
        arguments=ModelRequestArgs(
            provider="fake",
            model="scripted",
            path=MATERIAL_REF,
            excerpts=(),
            purpose="guidance_review",
        ).model_dump(),
        root_id="source:0",
        resource_key=MATERIAL_REF,
    )


def _grants(destination: str = DESTINATION) -> list[Grant]:
    """The material-purpose grants the request is judged against."""
    return [
        Grant(
            grant_id="g-model-1",
            subject_ref="proj-1",
            permission="external_transmit",
            purpose="transmit",
            scope="proj-1/**",
            destination=destination,
            granted_by="Dr. Chen",
            granted_at=MOMENT,
            expires_at=None,
            state="active",
            withdrawn_at=None,
            withdrawn_by=None,
            withdrawal_reason=None,
        )
    ]


@pytest.fixture()
def context(env: StoreEnv, tmp_path: Path) -> ApplicationContext:
    """A migrated store and a task under it, with a policy that asks."""
    workspace_root = tmp_path / "workspace"
    materials = workspace_root / "materials"
    materials.mkdir(parents=True)
    created = create_task(
        store=env.store(),
        policy=PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")]),
        workspace_root=workspace_root,
        title="The model-call path",
        goal=TaskGoal(
            objective="Ask a declared model under the two gates.",
            success_criterion="An answer the consent layer permitted.",
        ),
        source_dirs=(materials,),
    )
    return ApplicationContext(
        workspace=created.workspace,
        store=env.store(),
        policy=PermissionPolicy.from_rules([Rule(effect=Permission.ASK, pattern="**")]),
        ledger=ApprovalLedger(),
    )


def _invocation(
    answer: str = "the model's answer",
    structured: dict[str, object] | None = None,
) -> ModelInvocation:
    """One call's record, in the provider layer's wire form.

    The exchange is what an :class:`~labcairn.providers.adapter.ExchangeRecord`
    persists — a prompt digest, an outbound disclosure, usage — and nothing
    else, because that is the shape the path records by construction.
    """
    return ModelInvocation(
        answer=answer,
        provider="fake",
        model="scripted",
        exchanges=(
            {
                "provider": "fake",
                "model": "scripted",
                "transcript_step": "the-card",
                "prompt_digest": "a" * 64,
                "tool_names": [],
                "outbound": {"destination": DESTINATION, "digest": "b" * 64},
                "provider_attempts": 1,
                "observed_at": MOMENT.isoformat(),
                "usage_input": {"kind": "known", "tokens": 120},
                "usage_output": {"kind": "known", "tokens": 40},
            },
        ),
        credential_fingerprint="fp-" + "c" * 16,
        cost_micros=1200,
        structured=structured,
    )


def _spy(reached: list[str]) -> ModelInvocation:
    """The invocation a refused request must never reach."""
    reached.append("the wire was reached")
    return _invocation("an answer")


def _asked(context: ApplicationContext) -> ApprovalId:
    """An approval that has been asked for, and not granted."""
    return request_approval(
        context,
        ApprovalRequest(use=_model_use(), expires_at=MOMENT.replace(year=2027)),
    ).approval.approval_id


def _granted(context: ApplicationContext) -> ApprovalId:
    """An approval asked for and granted, and not yet spent."""
    approval_id = _asked(context)
    grant_approval(context, approval_id, now=MOMENT)
    return approval_id


def test_an_unapproved_model_request_refuses_and_sends_nothing(
    context: ApplicationContext,
) -> None:
    """No granted approval, no request: the wire is never reached."""
    approval_id = _asked(context)
    reached: list[str] = []

    with pytest.raises(ApplicationRefusedError):
        request_model(
            context,
            approval_id,
            _grants(),
            use=_model_use(),
            subject_ref="proj-1",
            destination=DESTINATION,
            material_ref=MATERIAL_REF,
            at=MOMENT,
            send=lambda: _spy(reached),
        )
    assert reached == [], "an unapproved request reached the wire"
    rows = list_approvals(context.store.session, context.task_id)
    assert all(row.state != "consumed" for row in rows), "nothing was spent"


def test_the_material_gate_runs_before_the_approval_is_spent(
    context: ApplicationContext,
) -> None:
    """A refusal for want of a grant leaves the approval unspent.

    The grant names the destination, and the request asks for another:
    the gate refuses, the approval is still grantable, and fixing the
    grant is enough — the person is not asked to pay for the refusal.
    """
    approval_id = _granted(context)
    reached: list[str] = []

    with pytest.raises(ApplicationRefusedError):
        request_model(
            context,
            approval_id,
            _grants(destination="api.other-provider.example"),
            use=_model_use(),
            subject_ref="proj-1",
            destination=DESTINATION,
            material_ref=MATERIAL_REF,
            at=MOMENT,
            send=lambda: _spy(reached),
        )
    assert reached == [], "a refused request reached the wire"
    rows = list_approvals(context.store.session, context.task_id)
    assert all(row.state != "consumed" for row in rows), "the approval stayed unspent"

    answer = request_model(
        context,
        approval_id,
        _grants(),
        use=_model_use(),
        subject_ref="proj-1",
        destination=DESTINATION,
        material_ref=MATERIAL_REF,
        at=MOMENT,
        send=lambda: _invocation(),
    )
    assert answer.answer == "the model's answer"
    assert answer.destination == DESTINATION
    assert answer.provider == "fake" and answer.model == "scripted"
    rows = list_approvals(context.store.session, context.task_id)
    assert any(row.state == "consumed" for row in rows)


def test_the_transcript_and_usage_land_and_no_key_is_written(
    context: ApplicationContext,
) -> None:
    """The exchange is recorded in the provider layer's own wire form.

    The event log carries the digest of what was sent and the usage of
    what came back, beside the fact of the call — and no plaintext key
    is written, because the record's shape has no field for one.
    """
    approval_id = _granted(context)
    answer = request_model(
        context,
        approval_id,
        _grants(),
        use=_model_use(),
        subject_ref="proj-1",
        destination=DESTINATION,
        material_ref=MATERIAL_REF,
        at=MOMENT,
        send=lambda: _invocation(),
    )
    page = read_events(context)
    exchanges = [event for event in page.events if event.type is EventType.MODEL_EXCHANGED]
    assert len(exchanges) == 1, "one call, one exchange record"
    payload = json.loads(json.dumps(exchanges[0].payload))
    assert payload["destination"] == DESTINATION
    assert payload["model"] == "scripted"
    assert payload["credential_fingerprint"] == "fp-" + "c" * 16
    exchange = payload["exchanges"][0]
    assert exchange["prompt_digest"] == "a" * 64, "what was sent is a digest"
    assert exchange["usage_input"] == {"kind": "known", "tokens": 120}
    assert payload["cost_micros"] == 1200
    rendered = json.dumps(payload)
    assert "sk-" not in rendered, "no plaintext key-shaped string is in the record"
    assert "the model's answer" not in rendered, "the answer is not the record"
    assert answer.exchange_event_id == str(exchanges[0].event_id)


# --------------------------------------------------------------------------- #
# the budget, the unknown answer, and the retry (LC-P2-01 T03)
# --------------------------------------------------------------------------- #


def _unpriced_budget() -> RunBudget:
    """A cost ceiling, for a model whose price nobody has measured."""
    return RunBudget(max_cost_usd=Decimal("5.00"))


def test_a_cost_ceiling_fails_closed_when_the_price_is_unknown(
    context: ApplicationContext,
) -> None:
    """A ceiling that cannot be measured halts the call — before anything is spent.

    The layer's own witness (``test_cost_ceiling_fails_closed_when_price_unknown``)
    establishes the guard; this one establishes that the **path** runs it
    before the gate and before the approval, so an unpriced model cannot
    spend a person's approval to reach a refusal.
    """
    approval_id = _granted(context)
    reached: list[str] = []

    with pytest.raises(BudgetEnforcementUnavailableError):
        request_model(
            context,
            approval_id,
            _grants(),
            use=_model_use(),
            subject_ref="proj-1",
            destination=DESTINATION,
            material_ref=MATERIAL_REF,
            at=MOMENT,
            send=lambda: _spy(reached),
            budget=_unpriced_budget(),
            ledger=LedgerSnapshot(cost_micros=Unknown(reason=UnknownReason.UNPRICED)),
        )
    assert reached == [], "an unmeasurable cost never reached the wire"
    rows = list_approvals(context.store.session, context.task_id)
    assert all(row.state != "consumed" for row in rows), "the approval stayed unspent"


def test_an_unanswered_request_is_unknown_and_not_a_success(
    context: ApplicationContext,
) -> None:
    """A call that was sent and did not answer records no success.

    The approval stays spent — the wire may have carried the request —
    and no exchange event is written, because a record shaped like an
    answer would be a lie about what came back. The doubt is a person's
    to reconcile; the path's job is to leave it visible.
    """
    approval_id = _granted(context)

    def unanswered() -> ModelInvocation:
        raise ProviderTimeoutError(120.0)

    with pytest.raises(ProviderTimeoutError):
        request_model(
            context,
            approval_id,
            _grants(),
            use=_model_use(),
            subject_ref="proj-1",
            destination=DESTINATION,
            material_ref=MATERIAL_REF,
            at=MOMENT,
            send=unanswered,
        )
    page = read_events(context)
    assert not [event for event in page.events if event.type is EventType.MODEL_EXCHANGED], (
        "an unanswered call recorded no exchange"
    )
    rows = list_approvals(context.store.session, context.task_id)
    assert any(row.state == "consumed" for row in rows), (
        "the approval was spent, because the wire may have carried it"
    )


def test_a_retry_does_not_pay_twice(context: ApplicationContext) -> None:
    """One approval, one call: a retry of a spent approval is refused.

    The provider layer's own witness
    (``test_the_ledger_totals_across_calls_and_the_counters_diverge_on_a_retry``)
    separates a transport retry from a second charge inside one call; this
    one holds the same line across calls — the approval that paid for the
    first call cannot pay for the second, whatever its outcome was.
    """
    approval_id = _granted(context)
    first = request_model(
        context,
        approval_id,
        _grants(),
        use=_model_use(),
        subject_ref="proj-1",
        destination=DESTINATION,
        material_ref=MATERIAL_REF,
        at=MOMENT,
        send=lambda: _invocation("the first answer"),
    )
    assert first.answer == "the first answer"

    with pytest.raises(ApplicationRefusedError):
        request_model(
            context,
            approval_id,
            _grants(),
            use=_model_use(),
            subject_ref="proj-1",
            destination=DESTINATION,
            material_ref=MATERIAL_REF,
            at=MOMENT,
            send=lambda: _invocation("the second answer"),
        )
    rows = list_approvals(context.store.session, context.task_id)
    assert sum(1 for row in rows if row.state == "consumed") == 1, "one approval, one consumption"
    page = read_events(context)
    exchanges = [event for event in page.events if event.type is EventType.MODEL_EXCHANGED]
    assert len(exchanges) == 1, "the second call never happened, and was never recorded"


# --------------------------------------------------------------------------- #
# the output, decoded or refused (LC-P2-01 T04)
# --------------------------------------------------------------------------- #


class _Card(LabCairnModel):
    """The schema a test asks for: a title and a verdict, both required."""

    title: str
    verdict: str


def _probed(*capable: Capability) -> ProviderCapabilities:
    """A probe record that licenses exactly the capabilities named."""
    outcomes = {
        capability: (
            CapabilityOutcome.OK if capability in capable else CapabilityOutcome.UNSUPPORTED
        )
        for capability in ALL_CAPABILITIES
    }
    return ProviderCapabilities.from_outcomes(
        endpoint_fingerprint="fp-" + "p" * 16,
        model="scripted",
        protocol="openai-chat",
        outcomes=outcomes,
        unsupported_reason=dict.fromkeys(
            ALL_CAPABILITIES, "the probe asked and it did not do the thing"
        ),
    )


def _schema_request(
    context: ApplicationContext,
    approval_id: ApprovalId,
    send: Callable[[], ModelInvocation] | None = None,
    **extra: Any,
) -> None:
    """One schema-carrying call, with whatever capabilities the test supplies."""
    request_model(
        context,
        approval_id,
        _grants(),
        use=_model_use(),
        subject_ref="proj-1",
        destination=DESTINATION,
        material_ref=MATERIAL_REF,
        at=MOMENT,
        send=send if send is not None else (lambda: _invocation()),
        output_schema=_Card,
        **extra,
    )


def test_an_unprobed_provider_is_blocked(context: ApplicationContext) -> None:
    """A schema request a probe does not license is refused before anything runs.

    A provider that cannot produce a schema's output is blocked from
    that request, rather than being asked to try — so the refusal lands
    at the gate: no approval spent, no wire touched. And the two ways
    not to be licensed name themselves: never probed is one reason, and
    probed-and-failed is another, because the remedies differ.
    """
    approval_id = _granted(context)
    reached: list[str] = []

    with pytest.raises(ApplicationRefusedError) as raised:
        _schema_request(context, approval_id, send=lambda: _spy(reached))
    assert raised.value.reason is ApplicationRefusal.MODEL_SCHEMA_UNPROBED, (
        "no probe record at all is the unprobed refusal"
    )
    assert reached == [], "an unprobed schema request reached the wire"

    with pytest.raises(ApplicationRefusedError) as raised:
        _schema_request(
            context,
            approval_id,
            send=lambda: _spy(reached),
            capabilities=ProviderCapabilities.unverified(
                endpoint_fingerprint="fp-" + "p" * 16,
                model="scripted",
                protocol="openai-chat",
            ),
        )
    assert raised.value.reason is ApplicationRefusal.MODEL_SCHEMA_UNPROBED, (
        "a record of never having asked is still the unprobed refusal"
    )

    with pytest.raises(ApplicationRefusedError) as raised:
        _schema_request(
            context,
            approval_id,
            send=lambda: _spy(reached),
            capabilities=_probed(Capability.TOOL_CALLS),
        )
    assert raised.value.reason is ApplicationRefusal.MODEL_SCHEMA_UNSUPPORTED, (
        "a probe that asked and saw both channels fail is the unsupported refusal"
    )
    assert "structured_output_native" in raised.value.detail
    assert "structured_output_prompted" in raised.value.detail
    assert reached == [], "a provider that cannot follow a schema was never asked to try"

    rows = list_approvals(context.store.session, context.task_id)
    assert all(row.state != "consumed" for row in rows), (
        "every schema refusal left the approval unspent"
    )


def test_a_licensed_schema_request_runs_and_decodes(context: ApplicationContext) -> None:
    """A probe that licenses a channel lets the request through, and it decodes.

    The block is about capability, not about schemas: a provider whose
    probe says it can do the thing does the thing, and the decoded
    request is an ordinary recorded call.
    """
    approval_id = _granted(context)
    answer = request_model(
        context,
        approval_id,
        _grants(),
        use=_model_use(),
        subject_ref="proj-1",
        destination=DESTINATION,
        material_ref=MATERIAL_REF,
        at=MOMENT,
        send=lambda: _invocation(structured={"title": "the title", "verdict": "the verdict"}),
        capabilities=_probed(Capability.STRUCTURED_OUTPUT_NATIVE),
        output_schema=_Card,
    )
    assert answer.answer == "the model's answer"
    rows = list_approvals(context.store.session, context.task_id)
    assert any(row.state == "consumed" for row in rows)


def test_an_undecodable_answer_is_refused_with_the_expectation(
    context: ApplicationContext,
) -> None:
    """An answer that does not satisfy the schema is a refusal naming it.

    The refusal names what was expected, and it does not unstate the
    call: the wire carried the request, the approval is spent, and the
    exchange record stays — what is refused is the *answer*, not the
    fact that a call happened.
    """
    approval_id = _granted(context)
    answer_refused = False

    def undecodable() -> ModelInvocation:
        nonlocal answer_refused
        answer_refused = True
        return _invocation(structured={"title": "the title"})

    with pytest.raises(ApplicationRefusedError) as raised:
        request_model(
            context,
            approval_id,
            _grants(),
            use=_model_use(),
            subject_ref="proj-1",
            destination=DESTINATION,
            material_ref=MATERIAL_REF,
            at=MOMENT,
            send=undecodable,
            capabilities=_probed(Capability.STRUCTURED_OUTPUT_NATIVE),
            output_schema=_Card,
        )
    assert answer_refused, "the call was made"
    assert raised.value.reason is ApplicationRefusal.MODEL_ANSWER_UNDECODABLE
    assert "_Card" in raised.value.detail, "the refusal names what was expected"
    assert "verdict" in raised.value.detail, "and where the answer fell short"

    rows = list_approvals(context.store.session, context.task_id)
    assert any(row.state == "consumed" for row in rows), (
        "the wire carried the request, so the approval is spent"
    )
    page = read_events(context)
    exchanges = [event for event in page.events if event.type is EventType.MODEL_EXCHANGED]
    assert len(exchanges) == 1, "the call's record stays: a refusal unstates nothing"


def test_an_empty_result_is_not_a_result(context: ApplicationContext) -> None:
    """A call that came back with nothing in the schema's shape refused.

    ``None`` and ``{}`` are both nothing: an empty result is not a
    result, and handing it on as an answer would be a lie with a
    schema's clothes on.
    """
    approval_id = _granted(context)

    with pytest.raises(ApplicationRefusedError) as raised:
        request_model(
            context,
            approval_id,
            _grants(),
            use=_model_use(),
            subject_ref="proj-1",
            destination=DESTINATION,
            material_ref=MATERIAL_REF,
            at=MOMENT,
            send=lambda: _invocation(structured=None),
            capabilities=_probed(Capability.STRUCTURED_OUTPUT_NATIVE),
            output_schema=_Card,
        )
    assert raised.value.reason is ApplicationRefusal.MODEL_ANSWER_EMPTY, (
        "nothing came back, and nothing is not an answer"
    )

    with pytest.raises(ApplicationRefusedError) as raised:
        request_model(
            context,
            _granted(context),
            _grants(),
            use=_model_use(),
            subject_ref="proj-1",
            destination=DESTINATION,
            material_ref=MATERIAL_REF,
            at=MOMENT,
            send=lambda: _invocation(structured={}),
            capabilities=_probed(Capability.STRUCTURED_OUTPUT_NATIVE),
            output_schema=_Card,
        )
    assert raised.value.reason is ApplicationRefusal.MODEL_ANSWER_EMPTY, (
        "an empty document is the same nothing"
    )
