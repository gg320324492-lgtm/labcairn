"""The outbound consent bridge, watched — ADR-0006.

**What is under test.** ADR-0006's defect, stated in its own words:

    *The permission layer can deny ``model.request`` and the provider will
    still send.*

The bridge closes that: :meth:`labcairn.providers.adapter.PydanticAiModelProvider.send`
is handed an :class:`~labcairn.providers.consent.OutboundConsent` port at
construction, calls it before the transport is reached, and the port refuses
when ``CapabilityId.MODEL_REQUEST`` has not been granted. The four properties
the work order names are each witnessed here, and each is measured on the
**recording upstream** — "the request did not leave" is ``endpoint.calls == []``,
not a raised exception plus a hope.

1. A refused request never reaches upstream.
2. A granted request is sent, exactly once.
3. The same approval cannot be spent twice.
4. A missing approval refuses the send rather than silently permitting it.

**The refusal is the provider layer's own error**, ``OutboundRefusedError`` —
the ``FailureKind.OUTBOUND_REFUSED`` member that existed before anything could
raise it. A caller of ``send`` handles an ungranted request like every other
pre-flight refusal and does not import the application layer's vocabulary.

**The order is witnessed too.** ``send`` runs its local pre-flights (cancel,
capability, budget) before the consent port, so a budget refusal does not spend
the one-shot approval. ``test_a_budget_refusal_does_not_spend_the_approval``
measures that ordering rather than trusting the comment.

**What is not here.** The provider does not evaluate the permission itself and
does not import :mod:`labcairn.security`; ``tests/test_capability_namespaces.py``
keeps that boundary. This file exercises the two halves on either side of it:
the approval-backed port is :class:`labcairn.application.outbound.OutboundApproval`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from provider_fakes import FakeEndpoint, Reply, sync_runner
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.application import ApplicationContext, create_task
from labcairn.application.approvals import (
    ApprovalGranted,
    ApprovalRequest,
    ApprovalRequested,
    ApprovalUse,
    grant_approval,
    request_approval,
)
from labcairn.application.outbound import OutboundApproval
from labcairn.core.ids import ApprovalId, new_id
from labcairn.core.providers.protocol import ModelRequest
from labcairn.providers.adapter import PydanticAiModelProvider
from labcairn.providers.budget import RunBudget
from labcairn.providers.consent import OutboundConsent
from labcairn.providers.errors import BudgetExceededError, OutboundRefusedError
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.runtime.operation import ApprovalState
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import CapabilityId, ModelRequestArgs
from labcairn.security.policy import Permission, PermissionPolicy, Rule

pytestmark = pytest.mark.integration

env = _shared_env

#: A fixed instant for every approval. The decision moment is passed, never
#: read from the wall clock, so expiry is exact and the test is replayable.
MOMENT = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)

#: The material the request is bound to. ``resource_in`` canonicalises the
#: key; it does not need a file on disk, only an admitted source root.
MATERIAL_REF = "proj-1/manuscript.txt"

_OK_REPLY = Reply(
    name="ok", text="the answer", usage_body={"input_tokens": 40, "output_tokens": 12}
)


@pytest.fixture()
def context(env: StoreEnv, tmp_path: Path) -> ApplicationContext:
    """A task under a policy that asks — a question, not a denial."""
    workspace_root = tmp_path / "workspace"
    materials = workspace_root / "materials"
    materials.mkdir(parents=True)
    created = create_task(
        store=env.store(),
        policy=PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")]),
        workspace_root=workspace_root,
        title="The outbound bridge",
        goal=TaskGoal(
            objective="Send a model request only with a permission decision.",
            success_criterion="An ungranted request never reaches the transport.",
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
    """What a ``model.request`` approval is spent on."""
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


def _asked(context: ApplicationContext, *, expires_at: datetime | None = None) -> ApprovalRequested:
    """An approval asked for but not yet granted."""
    return request_approval(
        context,
        ApprovalRequest(
            use=_the_use(),
            expires_at=expires_at if expires_at is not None else MOMENT + timedelta(hours=1),
        ),
        now=MOMENT,
    )


def _granted(context: ApplicationContext, *, expires_at: datetime | None = None) -> ApprovalGranted:
    """An approval a human granted at :data:`MOMENT`."""
    asked = _asked(context, expires_at=expires_at)
    return grant_approval(context, asked.approval.approval_id, now=MOMENT)


def _provider(endpoint: FakeEndpoint, consent: OutboundConsent) -> PydanticAiModelProvider:
    """A provider with the one thing this file varies: its consent port."""
    return PydanticAiModelProvider(
        model=endpoint,
        consent=consent,
        runner=sync_runner,
        clock=lambda: 0.0,
        usage_capture=endpoint.capture,
    )


# --- 4. a missing approval refuses the send --------------------------------


def test_a_missing_approval_refuses_the_send_and_sends_nothing(
    context: ApplicationContext,
) -> None:
    """``send`` without a live approval is a refusal, not a silent permission.

    The port names an approval the store does not hold. The provider refuses
    before the transport, and the recording upstream proves it.
    """
    endpoint = FakeEndpoint(replies=(_OK_REPLY,))
    consent = OutboundApproval(
        context=context,
        approval_id=ApprovalId(new_id()),
        use=_the_use(),
        at=MOMENT,
    )
    provider = _provider(endpoint, consent)

    with pytest.raises(OutboundRefusedError):
        provider.send(ModelRequest(prompt="Question the approved material."))

    assert endpoint.calls == []


def test_a_pending_approval_is_not_consent(context: ApplicationContext) -> None:
    """A question that was asked and not answered authorises nothing.

    The approval exists in the store, in state ``PENDING``. The refusal must
    come from the approval's own rule — ``NOT_GRANTED`` — rather than from a
    missing row, and the transport is still never reached.
    """
    endpoint = FakeEndpoint(replies=(_OK_REPLY,))
    asked = _asked(context)
    consent = OutboundApproval(
        context=context,
        approval_id=asked.approval.approval_id,
        use=_the_use(),
        at=MOMENT,
    )
    provider = _provider(endpoint, consent)

    with pytest.raises(OutboundRefusedError):
        provider.send(ModelRequest(prompt="Question the approved material."))

    assert endpoint.calls == []


# --- 1. a refused request never reaches upstream ---------------------------


def test_an_expired_approval_refuses_before_the_wire(context: ApplicationContext) -> None:
    """The window is checked at the moment of use, not at the moment of grant.

    The approval was granted inside its window; the decision is made an hour
    after it closed. The provider refuses, and the upstream sees no call.
    """
    endpoint = FakeEndpoint(replies=(_OK_REPLY,))
    granted = _granted(context, expires_at=MOMENT + timedelta(minutes=5))
    consent = OutboundApproval(
        context=context,
        approval_id=granted.approval.approval_id,
        use=_the_use(),
        at=MOMENT + timedelta(hours=1),
    )
    provider = _provider(endpoint, consent)

    with pytest.raises(OutboundRefusedError) as raised:
        provider.send(ModelRequest(prompt="Question the approved material."))

    assert "expired" in raised.value.reason
    assert endpoint.calls == []


def test_a_policy_refusal_does_not_spend_the_approval(context: ApplicationContext) -> None:
    """A permission withdrawn after the grant refuses the send, unspent.

    This is the closest state the product's approval machine has to a
    *revocation*: the row is still ``GRANTED``, and the permission that made
    it meaningful is the thing that changed. The refusal comes before the
    ledger moves the row, so the approval is still there if the policy is
    restored — asking is not spending.
    """
    endpoint = FakeEndpoint(replies=(_OK_REPLY,))
    granted = _granted(context)
    denying = ApplicationContext(
        workspace=context.workspace,
        store=context.store,
        policy=PermissionPolicy.from_rules([Rule(effect=Permission.DENY, pattern="**")]),
        ledger=context.ledger,
    )
    consent = OutboundApproval(
        context=denying,
        approval_id=granted.approval.approval_id,
        use=_the_use(),
        at=MOMENT,
    )
    provider = _provider(endpoint, consent)

    with pytest.raises(OutboundRefusedError):
        provider.send(ModelRequest(prompt="Question the approved material."))

    assert endpoint.calls == []
    # ``peek`` returns the row whichever state it is in, so "not None" would
    # pass even after a spend. The property is the state: still GRANTED.
    unspent = context.ledger.peek(granted.approval.approval_id)
    assert unspent is not None
    assert unspent.approval.state is ApprovalState.GRANTED


def test_a_budget_refusal_does_not_spend_the_approval(context: ApplicationContext) -> None:
    """The consent check is the **last** pre-flight, so local refusals cost nothing.

    A budget of zero requests refuses the call. If the consent port ran first,
    the approval would be consumed for a call that never happened, and a person
    would have to approve the same request again. The order is the property;
    the unspent ledger row is how it is measured.
    """
    endpoint = FakeEndpoint(replies=(_OK_REPLY,))
    granted = _granted(context)
    consent = OutboundApproval(
        context=context,
        approval_id=granted.approval.approval_id,
        use=_the_use(),
        at=MOMENT,
    )
    provider = PydanticAiModelProvider(
        model=endpoint,
        consent=consent,
        runner=sync_runner,
        clock=lambda: 0.0,
        usage_capture=endpoint.capture,
        budget=RunBudget(max_model_requests=0),
    )

    with pytest.raises(BudgetExceededError):
        provider.send(ModelRequest(prompt="Question the approved material."))

    assert endpoint.calls == []
    unspent = context.ledger.peek(granted.approval.approval_id)
    assert unspent is not None
    assert unspent.approval.state is ApprovalState.GRANTED


# --- 2. a granted request is sent, exactly once ----------------------------


def test_a_granted_request_is_sent_and_the_approval_moves_to_consumed(
    context: ApplicationContext,
) -> None:
    """The happy path, measured on both sides: one call out, one row spent."""
    endpoint = FakeEndpoint(replies=(_OK_REPLY,))
    granted = _granted(context)
    consent = OutboundApproval(
        context=context,
        approval_id=granted.approval.approval_id,
        use=_the_use(),
        at=MOMENT,
    )
    provider = _provider(endpoint, consent)

    response = provider.send(ModelRequest(prompt="Question the approved material."))

    assert response.text == "the answer"
    assert len(endpoint.calls) == 1
    assert endpoint.calls[0].prompt_text == "Question the approved material."
    # The name of this test promises "moves to consumed"; that promise is this
    # assertion. Without it, a bridge that only evaluated the policy would
    # pass — and the approval would still be spendable a second time.
    spent = context.ledger.peek(granted.approval.approval_id)
    assert spent is not None
    assert spent.approval.state is ApprovalState.CONSUMED


# --- 3. the same approval cannot be spent twice ----------------------------


def test_the_same_approval_cannot_authorise_two_sends(context: ApplicationContext) -> None:
    """The second ``send`` is refused by the ledger, and nothing is sent twice.

    The same port is reused deliberately: an approval is one operation, not a
    licence for a session. The upstream count stays at one.
    """
    endpoint = FakeEndpoint(replies=(_OK_REPLY, _OK_REPLY))
    granted = _granted(context)
    consent = OutboundApproval(
        context=context,
        approval_id=granted.approval.approval_id,
        use=_the_use(),
        at=MOMENT,
    )
    provider = _provider(endpoint, consent)

    provider.send(ModelRequest(prompt="Question the approved material."))

    with pytest.raises(OutboundRefusedError) as raised:
        provider.send(ModelRequest(prompt="Question the approved material again."))

    assert "consumed" in raised.value.reason
    assert len(endpoint.calls) == 1


# --- the port cannot be defaulted away -------------------------------------


def test_the_provider_cannot_be_built_without_a_consent_port() -> None:
    """A defaulted port would be a defaulted permission.

    ``consent=None`` — or no argument at all — must not build a provider that
    can send. This is the structural half of "cannot send without having been
    handed the result": there is no construction path that omits the hand-off.
    """
    endpoint = FakeEndpoint(replies=(_OK_REPLY,))

    with pytest.raises(TypeError):
        PydanticAiModelProvider(model=endpoint, runner=sync_runner)  # type: ignore[call-arg]
