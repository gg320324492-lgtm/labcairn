"""The approval's window: the layer refuses what the store would only reject.

An approval is asked for inside a window, and the window is what makes the
answer mean something: a question nobody answered in time is not a question
any more, and a grant recorded after the window closed would be a record of
an answer to a question that is no longer being asked.

The store holds that as a constraint — ``ck_approvals_expiry_after_grant`` and
``ck_approvals_consume_after_grant`` — and the constraint is right. But a
constraint refuses in the only language it has: a raw ``IntegrityError`` out
of the middle of the transaction, which a surface renders as a 500 and a
person reads as "the service is broken". So the layer asks the
:class:`~labcairn.runtime.operation.Approval` model instead, and translates
what the model says into the one refusal the layer raises.

What is asserted here:

* **the refusal is named.** A lapsed approval is refused with the layer's own
  refusal type and a reason a caller can branch on, and the message names the
  approval and the moment its window closed;
* **the boundaries are the model's.** The window is half-open — it closes at
  the moment it says it does — and a consumption at the very instant of the
  grant is not before it;
* **a refusal writes nothing.** No row moved, no event was emitted, and the
  ledger holds no grant, because "we refused" is not "we did it";
* **the constraint is still the store's.** The layer refuses before the
  database is asked, and the database still refuses the row the model would
  never build.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import text as sql_text
from sqlalchemy.exc import IntegrityError
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
    read_task_state,
    request_approval,
)
from labcairn.db.repository import count_events
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.runtime.operation import ApprovalState
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import CapabilityId
from labcairn.security.policy import Permission, PermissionPolicy, Rule

# pytest resolves a fixture by the parameter name in a test's signature, so the
# shared `env` fixture must be bound under that name here.
env = _shared_env

_MOMENT = datetime(2026, 1, 1, tzinfo=UTC)
_HASH = "b" * 64


# --------------------------------------------------------------------------- #
# the environment
# --------------------------------------------------------------------------- #


def _ask_all() -> PermissionPolicy:
    """A policy that asks about everything, which is a question, not a denial."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ASK, pattern="**")])


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """A workspace with a source directory in it."""
    root = tmp_path / "workspace"
    (root / "materials").mkdir(parents=True)
    return root


def _make_context(
    env: StoreEnv,
    workspace_root: Path,
    *,
    ledger: ApprovalLedger | None = None,
) -> ApplicationContext:
    """A context for a task that exists, under a policy that asks.

    Built here rather than imported from the layer's other test module, so
    that this file stands on its own and does not have to be re-read whenever
    that one is edited.
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
        policy=_ask_all(),
        ledger=ledger if ledger is not None else ApprovalLedger(),
    )


def _use() -> ApprovalUse:
    """What an approval is spent on."""
    return ApprovalUse(
        capability=CapabilityId.ANALYSIS_RUN,
        arguments={"operator_id": "mean", "parameters": {}},
        root_id="source:0",
        resource_key="one.csv",
    )


def _refusal(call: Callable[[], object], what: str) -> ApplicationRefusedError:
    """Run *call* and hand back the refusal it raised.

    **A raw ``IntegrityError`` is the defect, not a failing test**, so it is
    reported as one: a caller that has been told "the database said no" cannot
    tell a stale approval from a broken service, and neither can a reader of
    the failure.
    """
    try:
        call()
    except ApplicationRefusedError as error:
        return error
    except IntegrityError as error:
        pytest.fail(
            f"{what} reached the database ({error}). The layer is supposed to refuse "
            "it by name: a raw IntegrityError tells the caller that the service is "
            "broken rather than that its question has gone stale."
        )
    raise AssertionError(f"{what} was not refused at all")


def _the_store_refuses(env: StoreEnv, statement: str, params: dict[str, object]) -> str:
    """Write a row the model would never build, and report the store's refusal.

    Rolled back rather than committed, so a row the schema *does* accept does
    not stay in the store.
    """
    try:
        env.session.execute(sql_text(statement), params)
    except IntegrityError as error:
        return str(error)
    finally:
        env.session.rollback()
    raise AssertionError("the store accepted a row the model would never build")


# --------------------------------------------------------------------------- #
# the grant
# --------------------------------------------------------------------------- #


def test_granting_an_approval_whose_window_has_closed_is_refused(
    env: StoreEnv, workspace_root: Path
) -> None:
    """An answer to a question that has gone stale is refused by name.

    The approval was asked for inside a window, and the grant is stamped
    outside it. The store refuses that row — ``ck_approvals_expiry_after_grant``
    says the window must outlive the grant — but it refuses it as a database
    error in the middle of a transaction, which a surface renders as a 500.

    The layer is where that refusal belongs, because the layer is the one place
    that knows what a refusal is for. So the layer refuses, with its own
    refusal type and a reason a caller can branch on.
    """
    context = _make_context(env, workspace_root)
    asked = request_approval(
        context,
        ApprovalRequest(use=_use(), expires_at=_MOMENT - timedelta(hours=1)),
        now=_MOMENT,
    )

    refusal = _refusal(
        lambda: grant_approval(context, asked.approval.approval_id, now=_MOMENT),
        "granting an approval whose window had closed",
    )

    assert refusal.reason is ApplicationRefusal.APPROVAL_REFUSED


def test_the_refusal_names_the_approval_and_the_moment_it_expired(
    env: StoreEnv, workspace_root: Path
) -> None:
    """A refusal that says "expired" is only actionable if it says *which* one.

    The detail names the approval and the instant its window closed, so a
    person reading it knows which question to ask again and a caller reading it
    can tell a lapsed approval from any other refusal.
    """
    context = _make_context(env, workspace_root)
    expires_at = _MOMENT - timedelta(hours=1)
    asked = request_approval(
        context,
        ApprovalRequest(use=_use(), expires_at=expires_at),
        now=_MOMENT,
    )

    refusal = _refusal(
        lambda: grant_approval(context, asked.approval.approval_id, now=_MOMENT),
        "granting an approval whose window had closed",
    )

    assert str(asked.approval.approval_id) in refusal.detail
    assert expires_at.isoformat() in refusal.detail


def test_granting_at_the_moment_the_window_closes_is_refused(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The window is half-open: it closes at the moment it says it does.

    An approval whose expiry is the grant instant has no window left to be
    granted in, and the store's constraint says so too —
    ``expires_at > granted_at`` is the rule, not ``>=``.
    """
    context = _make_context(env, workspace_root)
    expires_at = _MOMENT + timedelta(hours=1)
    asked = request_approval(
        context,
        ApprovalRequest(use=_use(), expires_at=expires_at),
        now=_MOMENT,
    )

    refusal = _refusal(
        lambda: grant_approval(context, asked.approval.approval_id, now=expires_at),
        "granting an approval at the instant its window closed",
    )

    assert refusal.reason is ApplicationRefusal.APPROVAL_REFUSED


def test_a_refused_grant_writes_nothing_and_grants_nothing(
    env: StoreEnv, workspace_root: Path
) -> None:
    """A refused grant leaves no trace that could be mistaken for a success.

    No row moved, no event was emitted, and the ledger holds no grant — the
    last of those because the ledger is issued before the row is written, and
    an approval the ledger believes is granted but the store does not is a
    grant that half-happened.
    """
    context = _make_context(env, workspace_root)
    asked = request_approval(
        context,
        ApprovalRequest(use=_use(), expires_at=_MOMENT - timedelta(hours=1)),
        now=_MOMENT,
    )
    before = count_events(env.session, context.task_id)

    refusal = _refusal(
        lambda: grant_approval(context, asked.approval.approval_id, now=_MOMENT),
        "granting an approval whose window had closed",
    )

    assert refusal.reason is ApplicationRefusal.APPROVAL_REFUSED
    assert count_events(env.session, context.task_id) == before
    stored = read_task_state(context).approvals[0]
    assert stored.state is ApprovalState.PENDING
    assert stored.granted_at is None
    assert context.ledger.peek(asked.approval.approval_id) is None


def test_a_grant_is_recorded_with_the_moment_it_was_given(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The row carries the grant, and the grant carries the moment.

    Read back out of the store rather than taken from the value the layer
    returned: a layer that corrected the value it returned and wrote the row it
    was given would look right from the return value alone.
    """
    context = _make_context(env, workspace_root)
    asked = request_approval(
        context,
        ApprovalRequest(use=_use(), expires_at=_MOMENT + timedelta(hours=1)),
        now=_MOMENT,
    )

    granted = grant_approval(context, asked.approval.approval_id, now=_MOMENT)

    assert granted.approval.state is ApprovalState.GRANTED
    assert granted.approval.granted_at == _MOMENT
    stored = read_task_state(context).approvals[0]
    assert stored.state is ApprovalState.GRANTED
    assert stored.granted_at == _MOMENT


# --------------------------------------------------------------------------- #
# the consumption
# --------------------------------------------------------------------------- #


def test_consuming_an_approval_before_it_was_granted_is_refused(
    env: StoreEnv, workspace_root: Path
) -> None:
    """An approval cannot be spent before it was granted.

    The grant is the moment the approval came into being; there is nothing to
    spend before then. The store refuses the row —
    ``ck_approvals_consume_after_grant`` says the consumption must not precede
    the grant — and the layer refuses it first, by name.
    """
    context = _make_context(env, workspace_root)
    asked = request_approval(
        context,
        ApprovalRequest(use=_use(), expires_at=_MOMENT + timedelta(hours=1)),
        now=_MOMENT,
    )
    grant_approval(context, asked.approval.approval_id, now=_MOMENT)

    refusal = _refusal(
        lambda: consume_approval(
            context,
            asked.approval.approval_id,
            _use(),
            now=_MOMENT - timedelta(seconds=1),
        ),
        "spending an approval before it was granted",
    )

    assert refusal.reason is ApplicationRefusal.APPROVAL_REFUSED


def test_a_refused_consumption_spends_nothing(env: StoreEnv, workspace_root: Path) -> None:
    """The refusal arrives before the ledger is spent.

    The ledger is spent by the call that authorises the request, so a refusal
    that arrived after it would have spent the approval and refused the
    request at once: the approval would be gone and the work would not have
    happened, and neither record would say so.
    """
    context = _make_context(env, workspace_root)
    asked = request_approval(
        context,
        ApprovalRequest(use=_use(), expires_at=_MOMENT + timedelta(hours=1)),
        now=_MOMENT,
    )
    grant_approval(context, asked.approval.approval_id, now=_MOMENT)

    _refusal(
        lambda: consume_approval(
            context,
            asked.approval.approval_id,
            _use(),
            now=_MOMENT - timedelta(seconds=1),
        ),
        "spending an approval before it was granted",
    )

    held = context.ledger.peek(asked.approval.approval_id)
    assert held is not None
    assert held.approval.state is ApprovalState.GRANTED
    stored = read_task_state(context).approvals[0]
    assert stored.state is ApprovalState.GRANTED
    assert stored.consumed_at is None


def test_consuming_an_approval_at_the_moment_it_was_granted_is_allowed(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The same instant is not before itself.

    The store's rule is ``consumed_at >= granted_at``, so a consumption at the
    grant instant is exactly what the rule allows.
    """
    context = _make_context(env, workspace_root)
    asked = request_approval(
        context,
        ApprovalRequest(use=_use(), expires_at=_MOMENT + timedelta(hours=1)),
        now=_MOMENT,
    )
    grant_approval(context, asked.approval.approval_id, now=_MOMENT)

    consumed = consume_approval(context, asked.approval.approval_id, _use(), now=_MOMENT)

    assert consumed.approval.state is ApprovalState.CONSUMED
    assert consumed.approval.consumed_at == _MOMENT
    stored = read_task_state(context).approvals[0]
    assert stored.state is ApprovalState.CONSUMED
    assert stored.consumed_at == _MOMENT


# --------------------------------------------------------------------------- #
# the constraint
# --------------------------------------------------------------------------- #


def test_the_store_still_refuses_the_row_the_layer_refuses(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The constraint is untouched, and it is still the last line of defence.

    The layer refuses before the database is asked, so the constraint is not
    what the layer's refusal rests on. It is still there, and it still says
    no: a row written past the layer, by something that does not ask the
    model, is refused by the schema and the refusal names the constraint.
    """
    context = _make_context(env, workspace_root)
    expires_at = _MOMENT + timedelta(hours=1)
    asked = request_approval(
        context,
        ApprovalRequest(use=_use(), expires_at=expires_at),
        now=_MOMENT,
    )

    refusal = _the_store_refuses(
        env,
        "UPDATE approvals SET state = 'granted', granted_at = :granted_at "
        "WHERE approval_id = :approval_id",
        {"granted_at": expires_at.isoformat(), "approval_id": str(asked.approval.approval_id)},
    )

    assert "ck_approvals_expiry_after_grant" in refusal
