"""The approval carries what the policy said, and the spend reads it there.

**What is under test.** LC-P2-02 T00 and T01. ADR-0003 C4 binds an approval to
the capability, the resource key and the arguments digest, and requires that
**the policy snapshot still equals current policy** when the approval is spent.
The row used to carry none of it: `consume` took the policy digest as an
argument, so a caller could present a digest nobody had recorded and the store
had nothing to compare it with.

**The property, and why it is the one that matters.** A consent that a restart
empties is a consent a person has to give twice — and a consent that a caller
can describe at the moment of use is a consent the caller describes, not one a
person gave. Both are the same gap from two sides: **the row has to own the
fact**.

=============================  ===============================================
A1  the row carries it         the digest is written at the grant
A2  the spend reads it there    the row's value decides, not an argument
A3  a changed policy refuses    the old approval does not cover the new policy
A7  a restart does not un-spend the second spend is refused from the row
A10 the ledger cannot outlive   what the row says is what the reader answers
=============================  ===============================================
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select, update
from test_store_support import StoreEnv
from test_store_support import env as _shared_env

from labcairn.application import (
    ApplicationContext,
    ApplicationRefusal,
    ApplicationRefusedError,
    ApprovalRequest,
    ApprovalUse,
    consume_approval,
    create_task,
    grant_approval,
    request_approval,
)
from labcairn.application.context import approval_ledger_for
from labcairn.core.ids import ApprovalId
from labcairn.db.models import ApprovalRow
from labcairn.db.repository import StoredApprovalLedger, events_after
from labcairn.runtime.event import EventType
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.runtime.operation import ApprovalRefusal, ApprovalState
from labcairn.security.capabilities import CapabilityId
from labcairn.security.policy import Permission, PermissionPolicy, Rule

pytestmark = pytest.mark.integration

env = _shared_env

_MOMENT = datetime(2026, 1, 1, tzinfo=UTC)


def _ask_all() -> PermissionPolicy:
    return PermissionPolicy.from_rules([Rule(effect=Permission.ASK, pattern="**")])


def _another_policy() -> PermissionPolicy:
    """A policy whose digest is not the one that granted the approval."""
    return PermissionPolicy.from_rules(
        [
            Rule(effect=Permission.ASK, pattern="**"),
            Rule(effect=Permission.DENY, pattern="materials/**"),
        ]
    )


def _use() -> ApprovalUse:
    return ApprovalUse(
        capability=CapabilityId.ANALYSIS_RUN,
        arguments={"operator_id": "mean", "parameters": {}, "recipe": "figure.recipe.json"},
        root_id="source:0",
        resource_key="one.csv",
    )


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    (root / "materials").mkdir(parents=True)
    return root


@pytest.fixture
def context(env: StoreEnv, workspace_root: Path) -> ApplicationContext:
    """A task and a context whose ledger is the store's, not a dict."""
    created = create_task(
        store=env.store(),
        policy=PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")]),
        workspace_root=workspace_root,
        title="Durable consent",
        goal=TaskGoal(
            objective="Establish whether the observation holds.",
            success_criterion="A cited answer, or an honest 'not established'.",
        ),
        source_dirs=(workspace_root / "materials",),
    )
    return ApplicationContext(
        workspace=created.workspace,
        store=env.store(),
        policy=_ask_all(),
        ledger=approval_ledger_for(env.store()),
    )


def _granted(context: ApplicationContext) -> ApprovalId:
    asked = request_approval(
        context,
        ApprovalRequest(use=_use(), expires_at=_MOMENT + timedelta(hours=1)),
        now=_MOMENT,
    )
    granted = grant_approval(context, asked.approval.approval_id, now=_MOMENT)
    return granted.approval.approval_id


def _row(env: StoreEnv, approval_id: ApprovalId) -> ApprovalRow:
    row = env.session.execute(
        select(ApprovalRow).where(ApprovalRow.approval_id == str(approval_id))
    ).scalar_one()
    return row


def test_the_approval_row_carries_the_grant_time_binding(
    env: StoreEnv, context: ApplicationContext
) -> None:
    """A1 — the digest the policy gave is written down when the approval is granted.

    **The grant is the one moment that knows what the policy said.** A row that
    did not record it leaves the spend comparing two things it cannot both see,
    which is how the old argument-shaped `consume` passed a digest nobody had
    ever written down.
    """
    approval_id = _granted(context)
    row = _row(env, approval_id)
    assert row.state == ApprovalState.GRANTED.value
    assert row.grant_policy_digest == context.policy.digest()
    assert row.bound_sources == [], (
        "no source was bound to this request, and empty is the fact rather than "
        "an absence to be filled in later"
    )


def test_the_spend_reads_the_binding_from_the_row(
    env: StoreEnv, context: ApplicationContext
) -> None:
    """A2 — the row's digest decides, and a row nobody recorded refuses.

    **The mutation this watches for**: a spend that compares the current
    policy with something the caller handed over. Rewriting the row's recorded
    digest must change the answer, because the row is what the reader reads.
    """
    approval_id = _granted(context)
    env.session.execute(
        update(ApprovalRow)
        .where(ApprovalRow.approval_id == str(approval_id))
        .values(grant_policy_digest="c" * 64)
    )
    env.session.commit()

    with pytest.raises(ApplicationRefusedError) as refused:
        consume_approval(context, approval_id, _use(), now=_MOMENT)
    assert refused.value.reason is ApplicationRefusal.APPROVAL_REFUSED, (
        "a recorded digest that no longer matches the policy is the approval not "
        "covering the request, which is ADR-0003 C4's own refusal"
    )


def test_a_changed_policy_does_not_satisfy_the_old_approval(
    env: StoreEnv, context: ApplicationContext
) -> None:
    """A3 — a policy that changed between the grant and the spend closes the door.

    The approval was granted under one policy and is spent under another. The
    row keeps the first; the spend asks the second; they disagree, and the
    approval does not cover the request.
    """
    approval_id = _granted(context)
    changed = ApplicationContext(
        workspace=context.workspace,
        store=context.store,
        policy=_another_policy(),
        ledger=approval_ledger_for(env.store()),
    )
    with pytest.raises(ApplicationRefusedError) as refused:
        consume_approval(changed, approval_id, _use(), now=_MOMENT)
    assert refused.value.reason is ApplicationRefusal.APPROVAL_REFUSED


def test_a_restart_does_not_un_spend_an_approval(
    env: StoreEnv, context: ApplicationContext
) -> None:
    """A7 — a spent approval is spent, whatever process asks.

    **The failure this work order is measured against is the double spend.**
    The first spend succeeds; the second is made by a *fresh* ledger built on
    the same database, which is exactly what a restart hands a surface. It is
    refused, and it is refused **from the row**: the conditional UPDATE matches
    nothing because the row already says `CONSUMED`.
    """
    approval_id = _granted(context)
    consume_approval(context, approval_id, _use(), now=_MOMENT)

    after_restart = ApplicationContext(
        workspace=context.workspace,
        store=context.store,
        policy=context.policy,
        ledger=approval_ledger_for(env.store()),
    )
    with pytest.raises(ApplicationRefusedError):
        consume_approval(after_restart, approval_id, _use(), now=_MOMENT)
    assert _row(env, approval_id).state == ApprovalState.CONSUMED.value


def test_the_ledger_cannot_outlive_its_row(env: StoreEnv, context: ApplicationContext) -> None:
    """A10 — what the reader answers is what the row says.

    **A cache that can be read when the row says otherwise is a second source
    of truth.** The row is moved to `CONSUMED` behind the ledger's back; the
    ledger's own `peek` has to report that, because it reads the row rather
    than holding a copy of the grant.
    """
    approval_id = _granted(context)
    env.session.execute(
        update(ApprovalRow)
        .where(ApprovalRow.approval_id == str(approval_id))
        .values(state=ApprovalState.CONSUMED.value, consumed_at=_MOMENT)
    )
    env.session.commit()

    grant = context.ledger.peek(approval_id)
    assert grant is not None, "the row is still there, so the reader still finds it"
    assert grant.approval.state is ApprovalState.CONSUMED


def test_no_approval_operation_emits_twice(env: StoreEnv, context: ApplicationContext) -> None:
    """A4 — the row owns the state, the event owns the history, once each.

    Asking emits one event, granting one, consuming one. A reader asking
    "what happened to this approval" reads the stream and gets one of each;
    a second event of the same kind would be a history that says the same
    thing twice, which is how a reader stops trusting either copy.
    """
    approval_id = _granted(context)
    consume_approval(context, approval_id, _use(), now=_MOMENT)

    types = [event.type for event in events_after(env.session, context.task_id)]
    assert types.count(EventType.APPROVAL_REQUESTED) == 1, (
        "asking is one event, not one per stage the request happens to plan"
    )
    assert types.count(EventType.APPROVAL_GRANTED) == 1
    assert types.count(EventType.APPROVAL_CONSUMED) == 1


def test_the_surfaces_spend_from_the_store(env: StoreEnv, context: ApplicationContext) -> None:
    """A5 — the thing a surface hands the layer reads the row.

    **An in-memory ledger would pass every test on its own terms and still
    forget the grant on restart.** The surface's ledger is the store's, and
    the witness is that it answers about a grant this context did not
    create in memory.
    """
    ledger = approval_ledger_for(env.store())
    assert isinstance(ledger, StoredApprovalLedger)
    approval_id = _granted(context)
    assert ledger.peek(approval_id) is not None


def test_the_eight_refusal_reasons_are_unchanged() -> None:
    """A8 — a restart does not soften one of them.

    The eight are ADR-0003 C4's vocabulary, and they are closed: a reason
    that disappeared would be a condition nothing refuses any more, and a
    reason that appeared would be a new condition the ADR does not name.
    """
    assert {reason.value for reason in ApprovalRefusal} == {
        "not_granted",
        "expired",
        "consumed",
        "task_scope_mismatch",
        "args_changed",
        "source_changed",
        "policy_changed",
        "capability_unregistered",
    }
