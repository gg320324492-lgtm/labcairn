"""The two gates, and the order they run in.

**What is under test.** LC-P2-06 T02: the transmit gate, and the rule
that it runs **before** the approval is consumed.

**The property at the centre.** A request refused for want of a transmit
grant must leave the approval **unspent**. Asking is not spending — the
existing consent layer already holds to that, and this path has to hold to
it too, or a person would need a fresh approval every time a grant was
missing.

**And the second gate is not the first gate.** The operation approval says
*this operation may run once, now*. The transmit grant says *this material
may go to this place*. **Passing one does not imply the other**, and
merging them would make the design's default-deny for transmission
unrepresentable.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from test_store_support import StoreEnv
from test_store_support import env as _shared_env

from labcairn.application import create_task
from labcairn.application.approvals import (
    ApprovalRequest,
    ApprovalUse,
    grant_approval,
    request_approval,
    spendable_approval,
)
from labcairn.application.context import ApplicationContext
from labcairn.application.model_transmit import (
    check_transmit,
    transmit_refusal_for,
    transmit_request,
)
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.core.ids import ApprovalId
from labcairn.db.repository import list_approvals
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import CapabilityId
from labcairn.security.permissions import Grant
from labcairn.security.policy import Permission, PermissionPolicy, Rule

pytestmark = pytest.mark.integration

# pytest resolves a fixture by the parameter name in a test's signature, so the
# shared `env` fixture must be bound under that name here.
env = _shared_env

NOW = datetime(2026, 3, 2, 9, 15, tzinfo=UTC)


def _transmit_grant(
    grant_id: str = "g1",
    *,
    subject_ref: str = "proj-1",
    scope: str = "proj-1/**",
    destination: str = "api.minimax.cn",
    purpose: str = "transmit",
    state: str = "active",
) -> Grant:
    return Grant(
        grant_id=grant_id,
        subject_ref=subject_ref,
        permission="external_transmit",
        purpose=purpose,
        scope=scope,
        destination=destination,
        granted_by="Dr. Chen",
        granted_at=NOW,
        expires_at=None,
        state=state,
        withdrawn_at=None,
        withdrawn_by=None,
        withdrawal_reason=None,
    )


def _read_grant(grant_id: str = "g2") -> Grant:
    return Grant(
        grant_id=grant_id,
        subject_ref="proj-1",
        permission="store_read",
        purpose="read",
        scope="proj-1/**",
        destination=None,
        granted_by="Dr. Chen",
        granted_at=NOW,
        expires_at=None,
        state="active",
        withdrawn_at=None,
        withdrawn_by=None,
        withdrawal_reason=None,
    )


# --------------------------------------------------------------------------- #
# the approval the path spends
# --------------------------------------------------------------------------- #


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """A workspace with a source directory in it."""
    root = tmp_path / "workspace"
    (root / "materials").mkdir(parents=True)
    return root


def _make_context(env: StoreEnv, workspace_root: Path) -> ApplicationContext:
    """A context for a task that exists, under a policy that asks.

    Built here rather than imported from another test module, so that this
    file stands on its own and does not have to be re-read whenever that one
    is edited.
    """
    created = create_task(
        store=env.store(),
        policy=PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")]),
        workspace_root=workspace_root,
        title="Test task",
        goal=TaskGoal(
            objective="Establish whether the observation holds.",
            success_criterion="A cited answer, or an honest 'not established'.",
        ),
        source_dirs=(workspace_root / "materials",),
    )
    return ApplicationContext(
        workspace=created.workspace,
        store=env.store(),
        policy=PermissionPolicy.from_rules([Rule(effect=Permission.ASK, pattern="**")]),
        ledger=ApprovalLedger(),
    )


def _use() -> ApprovalUse:
    """What the approval is spent on.

    **The capability is the analysis one**, and that is deliberate: which
    capability a *model* request runs under is the model path's business
    (LC-P2-01), and this file is about the **order** the two gates run in,
    not about the capability the request carries. The order does not depend
    on it, and choosing it here would only be a way of asserting something
    the model path has not decided yet.
    """
    return ApprovalUse(
        capability=CapabilityId.ANALYSIS_RUN,
        arguments={"operator_id": "mean", "parameters": {}, "recipe": "figure.recipe.json"},
        root_id="source:0",
        resource_key="one.csv",
    )


@pytest.fixture
def context(env: StoreEnv, workspace_root: Path) -> ApplicationContext:
    """A context with a task under it."""
    return _make_context(env, workspace_root)


@pytest.fixture
def approval(context: ApplicationContext) -> ApprovalId:
    """An approval asked for and granted, and **not yet spent**."""
    asked = request_approval(
        context,
        ApprovalRequest(
            use=_use(),
            expires_at=NOW + timedelta(hours=1),
        ),
        now=NOW,
    )
    granted = grant_approval(context, asked.approval.approval_id, now=NOW)
    return granted.approval.approval_id


# --------------------------------------------------------------------------- #
# the gate
# --------------------------------------------------------------------------- #


def test_a_transmit_grant_permits_the_request() -> None:
    """The ordinary case: the material may go to the named destination."""
    check = check_transmit(
        [_transmit_grant()],
        subject_ref="proj-1",
        destination="api.minimax.cn",
        at=NOW,
    )

    assert check.permitted is True
    assert check.reason is None
    assert check.decision.grant_id == "g1"


def test_a_request_without_a_transmit_grant_is_refused_and_the_approval_is_unspent(
    context: ApplicationContext,
    approval: ApprovalId,
) -> None:
    """**The refusal does not spend the approval.**

    **What breaks it:** a path that consumes the approval before it asks
    the gate, so that a request refused for want of a grant costs the
    person their approval as well. **Asking is not spending** — the
    existing consent layer already holds to that, and this path has to hold
    to it too, or a person would need a fresh approval every time the
    grant was missing.

    **And the refusal is the layer's own.** A model request with no
    transmit grant must be refused *with a reason* — the model call itself
    is the thing that leaves the machine — and the reason is one a surface
    can render, looked up in the layer's vocabulary rather than invented
    here.
    """
    with pytest.raises(ApplicationRefusedError) as caught:
        transmit_request(
            context,
            approval,
            [],
            use=_use(),
            subject_ref="proj-1",
            destination="api.minimax.cn",
            at=NOW,
        )

    assert caught.value.reason is ApplicationRefusal.CONSENT_NO_GRANT
    assert "remedy" in caught.value.detail

    # **And the approval is still spendable.** Asking is not spending.
    still = spendable_approval(context, approval, now=NOW)
    assert still.approval_id == approval

    # **And the store says it was not spent.** `spendable_approval` asks
    # whether the moment is right to spend, not whether it has been spent
    # already — so it alone would not notice a path that spent the
    # approval and then refused the request. **The record of what was
    # spent is a fact about the store**, and this is that fact read.
    rows = list_approvals(context.store.session, context.task_id)
    assert all(row.state != "consumed" for row in rows), (
        "the request was refused and the approval was spent anyway"
    )


def test_a_read_grant_does_not_authorise_a_transmission() -> None:
    """**The two gates are not the same gate.**

    **What breaks it:** a check that looks at "any grant for this subject".
    A read grant is not a transmit grant, and the design's default-deny for
    transmission depends on the difference being real.
    """
    check = check_transmit(
        [_read_grant()],
        subject_ref="proj-1",
        destination="api.minimax.cn",
        at=NOW,
    )

    assert check.permitted is False
    assert check.reason == "purpose_not_granted"


def test_a_grant_for_one_destination_does_not_authorise_another() -> None:
    """**ADR-0015 D3's rule, on the path where it matters.**

    **What breaks it:** a check that treats any transmit grant as a
    transmit grant. The refusal has to name both destinations, because
    the person reading it can then either ask the granted one or ask for a
    grant for the other.
    """
    check = check_transmit(
        [_transmit_grant()],
        subject_ref="proj-1",
        destination="api.openai.com",
        at=NOW,
    )

    assert check.permitted is False
    assert check.reason == "destination_not_granted"
    assert "api.minimax.cn" in check.detail
    assert "api.openai.com" in check.detail


def test_a_withdrawn_grant_is_refused_as_withdrawn() -> None:
    """A withdrawal is not an absence, and the path says which."""
    grant = _transmit_grant()
    withdrawn = Grant(
        **{
            **grant.__dict__,
            "state": "withdrawn",
            "withdrawn_by": "Dr. Chen",
            "withdrawn_at": NOW,
        }
    )

    check = check_transmit(
        [withdrawn],
        subject_ref="proj-1",
        destination="api.minimax.cn",
        at=NOW,
    )

    assert check.permitted is False
    assert check.reason == "grant_withdrawn"
    assert "Dr. Chen" in check.detail


def test_the_refusal_reason_is_the_consent_layer_s_own_string() -> None:
    """**A refusal reason is not re-spelled at every call site.**

    **What breaks it:** a second vocabulary for the same reasons. The
    design's rule is that the caller can branch on the reason without
    reading a message — and that only works if there is one spelling.
    """
    for destination, expected in (
        ("api.openai.com", "destination_not_granted"),
        ("api.minimax.cn", None),
    ):
        check = check_transmit(
            [_transmit_grant()],
            subject_ref="proj-1",
            destination=destination,
            at=NOW,
        )
        assert transmit_refusal_for(check) == expected


def test_the_transmit_check_runs_before_the_approval_is_consumed(
    context: ApplicationContext,
    approval: ApprovalId,
) -> None:
    """**The gate runs first, and only a permitted request spends the approval.**

    **What breaks it:** a path that consumes the approval before it asks
    the gate, so that a request refused for want of a grant costs the
    person their approval as well. The caller would have to ask for a new
    approval every time the grant was missing, and the person would be
    paying for a refusal.

    **And the other direction has to hold as well.** A request the gate
    permits **does** spend the approval — or "the check runs first" would
    be satisfied by a path that never spends anything at all, which is
    not the property and would pass for it.
    """
    check = transmit_request(
        context,
        approval,
        [_transmit_grant()],
        use=_use(),
        subject_ref="proj-1",
        destination="api.minimax.cn",
        at=NOW,
    )

    assert check.permitted is True
    assert check.decision.grant_id == "g1"

    # And the approval is spent — **read from the store**, because the
    # record of what was spent is a fact about the store and not a fact
    # about the function that spent it.
    rows = list_approvals(context.store.session, context.task_id)
    assert any(row.state == "consumed" for row in rows), (
        "the request was permitted and the approval was not spent"
    )


def test_the_gate_takes_no_approval_of_its_own() -> None:
    """**The two gates are separate, and the second one does not touch the
    first one's state.**

    The gate is a question: it asks whether the material may go, and it
    answers. **It does not spend anything and it does not carry an
    approval** — the path above is what holds the two together, and the
    gate's own signature is what says it is not two gates wearing one
    name.
    """
    import inspect

    parameters = inspect.signature(check_transmit).parameters
    assert "approval" not in parameters
    assert "approval_id" not in parameters
    assert set(parameters) == {
        "grants",
        "subject_ref",
        "material_ref",
        "destination",
        "purpose",
        "at",
    }


def test_the_check_needs_a_destination() -> None:
    """**A transmit request names where it is going.**

    **What breaks it:** a default destination, or an optional one. A
    request that did not say where it was going is a request to send
    anywhere, and the grant table's destination field exists to refuse
    that.
    """
    with pytest.raises(TypeError):
        check_transmit(  # type: ignore[call-arg]
            [_transmit_grant()],
            subject_ref="proj-1",
            at=NOW,
        )


def test_a_grant_for_another_subject_does_not_answer() -> None:
    """A grant belongs to one project."""
    check = check_transmit(
        [_transmit_grant(subject_ref="proj-2")],
        subject_ref="proj-1",
        destination="api.minimax.cn",
        at=NOW,
    )

    assert check.permitted is False
    assert check.reason == "no_grant"
