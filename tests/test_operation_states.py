"""The operation's states, and which of them this tree writes.

ADR-0003 C2's state machine has eight states, and the tree used to write five
of them. ``DENIED`` was defined and never written: a policy denial became a
refusal before the operation was planned, and a refusal wrote nothing. A run
stopped by policy was therefore indistinguishable from a run that was never
started, and the operator had no way to see that a write had been refused or
why.

This file witnesses what a denial leaves, and — just as important — what it
does not:

* a denied write leaves an operation in state ``denied``, and the event that
  describes it carries the reason the permission layer produced;
* a refusal for any other reason still leaves nothing at all, so the denial
  is a fact about the policy and not a catch-all for every refusal;
* the denial is terminal — the recovery layer refuses to replay it — and the
  states it refused before are still refused.

Every witness says how it goes red when its property is broken.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from store_support import StoreEnv, make_operation
from store_support import env as _shared_env

from labcairn.application import (
    ApplicationContext,
    ApplicationRefusal,
    ApplicationRefusedError,
    StageOutcome,
    StageRequest,
    create_task,
    run_stage,
)
from labcairn.application.context import store_refusals
from labcairn.core.ids import TaskId
from labcairn.db.repository import (
    count_events,
    events_after,
    list_operations,
    list_runs,
    list_stages,
)
from labcairn.recovery.contracts import ReconciliationRequired, SideEffect
from labcairn.recovery.executor import AlreadyConfirmedError, SideEffectExecutor
from labcairn.runtime.event import EventType
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.runtime.operation import Operation, OperationState
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import CapabilityId
from labcairn.security.policy import (
    DecisionReason,
    Permission,
    PermissionPolicy,
    ResourceRef,
    Rule,
)

#: The shared store fixture, imported rather than rebuilt.
env = _shared_env

_HASH = "b" * 64


# --------------------------------------------------------------------------- #
# the environment
# --------------------------------------------------------------------------- #


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """A workspace with a source directory in it."""
    root = tmp_path / "workspace"
    (root / "materials").mkdir(parents=True)
    return root


def _allow_all() -> PermissionPolicy:
    """A policy that allows everything."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])


def _deny_all() -> PermissionPolicy:
    """A policy that denies everything."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.DENY, pattern="**")])


def _deny_nothing() -> PermissionPolicy:
    """A policy with no rule at all, so the verdict is the default deny."""
    return PermissionPolicy.from_rules([])


def _ask_all() -> PermissionPolicy:
    """A policy that asks about everything, which is a question, not a denial."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ASK, pattern="**")])


def _make_context(
    env: StoreEnv,
    workspace_root: Path,
    policy: PermissionPolicy,
) -> ApplicationContext:
    """A context for a task that exists, under the policy the test wants.

    The task is made under an allowing policy whatever the test's policy is,
    because the test is about what happens *after* the task exists.
    """
    store = env.store()
    created = create_task(
        store=store,
        policy=_allow_all(),
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
        store=store,
        policy=policy,
        ledger=ApprovalLedger(),
    )


def _stage_request(
    *,
    stage_name: str = "intake",
    capability: CapabilityId = CapabilityId.ANALYSIS_RUN,
    arguments: Mapping[str, Any] | None = None,
    root_id: str = "source:0",
    resource_key: str = "one.csv",
) -> StageRequest:
    """A stage run over a file in the source root."""
    return StageRequest(
        stage_name=stage_name,
        capability=capability,
        arguments=arguments
        if arguments is not None
        else {"operator_id": "mean", "recipe": "recipe.json", "parameters": {}},
        root_id=root_id,
        resource_key=resource_key,
    )


def _work(resource: object) -> StageOutcome:
    """A stage's work that succeeds and produces nothing."""
    del resource
    return StageOutcome(output_hashes=(_HASH,))


def _assert_refused(call: Any, reason: ApplicationRefusal) -> ApplicationRefusedError:
    """Run *call*, and insist it refused for *reason*."""
    with pytest.raises(ApplicationRefusedError) as caught:
        call()
    assert caught.value.reason is reason
    return caught.value


def _denial_event(env: StoreEnv, context: ApplicationContext) -> Any:
    """The one event that describes the denial."""
    written = [
        event
        for event in events_after(env.session, context.task_id, after_seq=0)
        if event.type is EventType.OPERATION_DENIED
    ]
    assert len(written) == 1, f"expected exactly one operation_denied event, found {written}"
    return written[0]


# --------------------------------------------------------------------------- #
# what a denial leaves
# --------------------------------------------------------------------------- #


def test_a_denied_write_leaves_an_operation_in_the_denied_state(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The state that was defined and never written is now written.

    **How it goes red.** The operation row is read back out of the database
    rather than taken from the object the layer returned: a fix that
    corrected the object and left the row alone would look right from the
    return value and wrong from here. Remove the write in
    :func:`labcairn.application.stages._record_denial` and the table is empty
    and this fails on the first assertion.
    """
    context = _make_context(env, workspace_root, _deny_all())
    _assert_refused(
        lambda: run_stage(context, _stage_request(), _work),
        ApplicationRefusal.PERMISSION_DENIED,
    )

    operations = list_operations(env.session, context.task_id)
    assert [operation.state for operation in operations] == [OperationState.DENIED]

    denied = operations[0]
    assert denied.capability == CapabilityId.ANALYSIS_RUN.value
    assert denied.resource_key.endswith("one.csv")

    event = _denial_event(env, context)
    assert event.transition is not None
    assert event.transition.from_state == OperationState.PLANNED.value
    assert event.transition.to_state == OperationState.DENIED.value
    assert event.operation_id == denied.operation_id


def test_the_denial_carries_the_reason_the_permission_layer_produced(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The record says *why*, in the permission layer's own word.

    **How it goes red.** The expected reason is computed by asking the policy
    layer itself, not written out by hand: a payload that carried a
    paraphrase, or a made-up word, or the wrong rule, fails here. The word is
    also checked against the enum, so a string that merely looks like a
    ``DecisionReason`` is refused.
    """
    context = _make_context(env, workspace_root, _deny_all())
    _assert_refused(
        lambda: run_stage(context, _stage_request(), _work),
        ApplicationRefusal.PERMISSION_DENIED,
    )

    decision = context.policy.evaluate(
        task_id=context.task_id,
        capability=CapabilityId.ANALYSIS_RUN.value,
        resource=ResourceRef.from_canonical(context.resource_in("source:0", "one.csv")),
    )
    payload = _denial_event(env, context).payload

    reason = payload["reason"]
    assert reason in {member.value for member in DecisionReason}
    assert reason == decision.reason.value
    assert payload["matched_rule"] == decision.matched_rule
    assert payload["matched_spelling"] == decision.matched_spelling


def test_a_denial_with_no_matching_rule_records_the_default_deny(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The default deny is recorded as the default deny.

    The reason is a word, so the two ways a policy can stop a write stay
    apart: a rule of the operator's, and the absence of any rule at all.

    **How it goes red.** A payload that hard-coded ``rule_deny`` would pass
    the witness above and fail this one.
    """
    context = _make_context(env, workspace_root, _deny_nothing())
    _assert_refused(
        lambda: run_stage(context, _stage_request(), _work),
        ApplicationRefusal.PERMISSION_DENIED,
    )
    payload = _denial_event(env, context).payload
    assert payload["reason"] == DecisionReason.DEFAULT_DENY.value
    assert payload["matched_rule"] is None


def test_the_refusal_after_the_denial_is_the_refusal_it_has_always_been(
    env: StoreEnv, workspace_root: Path
) -> None:
    """Recording the denial does not change what the caller is told.

    The refusal is still one exception, of one type, with one reason, and its
    message still names the reason the permission layer produced — so a
    surface that renders the refusal renders what it always rendered.

    **How it goes red.** The message is asserted to carry the reason word:
    a refusal that stopped naming it would still refuse, and the operator
    would have lost the only place the reason was ever in prose.
    """
    context = _make_context(env, workspace_root, _deny_all())
    refused = _assert_refused(
        lambda: run_stage(context, _stage_request(), _work),
        ApplicationRefusal.PERMISSION_DENIED,
    )
    assert refused.reason is ApplicationRefusal.PERMISSION_DENIED
    assert "denied" in refused.detail
    assert DecisionReason.RULE_DENY.value in refused.detail


def test_a_denied_write_whose_arguments_cannot_be_json_is_still_the_policy_s_denial(
    env: StoreEnv, workspace_root: Path
) -> None:
    """A denied write is recorded even when its arguments are not JSON.

    The operation's row is bound to a digest of the arguments, and a digest
    over arguments no compliant reader could reproduce would be a lie. The
    capability's own model is what makes this case survivable: the validated
    arguments are dumped in JSON mode, which renders a value JSON cannot
    represent as null, so the digest is computable and the denial is still
    recorded — and the caller still hears the policy's refusal, not the
    arguments' problem.

    **How it goes red.** The refusal's reason is the assertion, and the event
    count says the rest of it: a change that let the arguments' own problem
    come out as ``arguments_invalid`` would report a policy denial as an
    argument fault, and the operator would chase the wrong remedy.
    """
    context = _make_context(env, workspace_root, _deny_all())
    _assert_refused(
        lambda: run_stage(
            context,
            _stage_request(
                arguments={
                    "operator_id": "mean",
                    "recipe": "recipe.json",
                    "parameters": {"threshold": float("nan")},
                }
            ),
            _work,
        ),
        ApplicationRefusal.PERMISSION_DENIED,
    )
    operations = list_operations(env.session, context.task_id)
    assert [operation.state for operation in operations] == [OperationState.DENIED]


def test_a_refusal_for_another_reason_leaves_no_row_at_all(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The denial is not a catch-all: every other refusal still writes nothing.

    A policy that *asks* is a question, not a denial, and the refusal it
    produces is a different fact with a different remedy. Recording it as a
    denial would tell the operator that a rule of theirs stopped the write
    when nothing of the kind happened.

    **How it goes red.** The event count and the operations table are both
    read: if any refusal other than the policy's own ``DENY`` reached the
    writer, one of the two fails.
    """
    context = _make_context(env, workspace_root, _ask_all())
    before = count_events(env.session, context.task_id)
    _assert_refused(
        lambda: run_stage(context, _stage_request(), _work),
        ApplicationRefusal.POLICY_ASKED,
    )
    assert count_events(env.session, context.task_id) == before
    assert list_operations(env.session, context.task_id) == ()


# --------------------------------------------------------------------------- #
# the denial is terminal
# --------------------------------------------------------------------------- #


def _store_an_operation(
    env: StoreEnv,
    task_id: TaskId,
    state: OperationState,
) -> Operation:
    """Put an operation in *state* into the store, so a refusal can be tried."""
    with store_refusals():
        run = list_runs(env.session, task_id)[-1]
        stage = list_stages(env.session, task_id)[-1]
    operation = make_operation(
        task_id,
        run.run_id,
        stage.stage_id,
        state=state,
        capability=CapabilityId.ANALYSIS_RUN.value,
        resource_key="materials/one.csv",
    )
    with env.store().unit(task_id) as work:
        work.put_operation(operation)
    return operation


def _effect(resource_key: str) -> tuple[SideEffect, list[int]]:
    """An effect that counts how many times it was applied."""
    calls: list[int] = []

    def apply() -> str:
        calls.append(1)
        return _HASH

    return SideEffect(resource_key=resource_key, expected_sha256=_HASH, apply=apply), calls


def test_a_denial_is_terminal_and_the_recovery_layer_refuses_to_replay_it(
    env: StoreEnv, workspace_root: Path
) -> None:
    """A denied operation cannot be re-run, because it never ran.

    The refusal is the deliverable, and the effect is not called at all — the
    counter is what says so, because a replay that refused *after* calling
    the effect would leave the same bytes and a different count.

    **How it goes red.** The guard in
    :meth:`labcairn.recovery.executor.SideEffectExecutor.replay` is the only
    thing between the denial and a second attempt; drop the ``DENIED`` case
    from it and this fails on the missing exception.
    """
    context = _make_context(env, workspace_root, _deny_all())
    _assert_refused(
        lambda: run_stage(context, _stage_request(), _work),
        ApplicationRefusal.PERMISSION_DENIED,
    )
    denied = list_operations(env.session, context.task_id)[0]

    effect, calls = _effect(denied.resource_key)
    executor = SideEffectExecutor(
        env.store(),
        env.session,
        workspace_root=workspace_root,
    )
    with pytest.raises(AlreadyConfirmedError):
        executor.replay(denied.operation_id, effect=effect, args={})
    assert calls == [], "a refused replay must not have called the effect at all"


def test_the_states_the_recovery_layer_refused_before_are_still_refused(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The refusals that were there before the denial are still there.

    Writing a new state must not loosen the machine around it: an uncertain
    operation still has to be resolved rather than replayed, and a confirmed
    one still must not be run again.

    **How it goes red.** Each state is put in the store and replayed, and the
    exception is the assertion — so a guard that stopped covering a state
    fails here even though nothing about the denial changed.
    """
    context = _make_context(env, workspace_root, _deny_all())
    _assert_refused(
        lambda: run_stage(context, _stage_request(), _work),
        ApplicationRefusal.PERMISSION_DENIED,
    )
    executor = SideEffectExecutor(
        env.store(),
        env.session,
        workspace_root=workspace_root,
    )

    uncertain = _store_an_operation(env, context.task_id, OperationState.UNCERTAIN)
    effect, calls = _effect(uncertain.resource_key)
    with pytest.raises(ReconciliationRequired):
        executor.replay(uncertain.operation_id, effect=effect, args={})
    assert calls == []

    confirmed = _store_an_operation(env, context.task_id, OperationState.CONFIRMED)
    effect, calls = _effect(confirmed.resource_key)
    with pytest.raises(AlreadyConfirmedError):
        executor.replay(confirmed.operation_id, effect=effect, args={})
    assert calls == []
