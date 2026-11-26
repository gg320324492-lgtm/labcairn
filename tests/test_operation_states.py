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
* **the denial's whole trace is one transaction**: a denial whose event
  cannot be written leaves no run, no stage and no operation behind, because
  a run in ``running`` and a stage in ``entered`` are exactly the trace that
  could be mistaken for a partial success;
* a refusal for any other reason still leaves nothing at all, so the denial
  is a fact about the policy and not a catch-all for every refusal — and
  **each** of those refusals has a witness of its own, because a witness that
  covers one case and claims the rule is no witness of the rule;
* the denial is terminal — the recovery layer refuses to replay it — and the
  states it refused before are still refused.

Every witness says how it goes red when its property is broken.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import event as sa_event
from store_support import StoreEnv, make_operation, make_run, make_stage
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
from labcairn.application.approvals import (
    ApprovalRequest,
    ApprovalUse,
    grant_approval,
    request_approval,
)
from labcairn.application.context import store_refusals
from labcairn.core.ids import ApprovalId, TaskId, new_id
from labcairn.db.repository import (
    count_events,
    events_after,
    last_seq,
    list_approvals,
    list_operations,
    list_runs,
    list_stages,
)
from labcairn.recovery.contracts import ReconciliationRequired, SideEffect
from labcairn.recovery.executor import AlreadyConfirmedError, SideEffectExecutor
from labcairn.runtime.event import EventType
from labcairn.runtime.lifecycle import RunStatus, StageStatus, TaskGoal
from labcairn.runtime.operation import ApprovalState, Operation, OperationState
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

#: The class this file belongs to, declared so that nothing outside the
#: partition table has to say it.
pytestmark = pytest.mark.integration

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
    approval_id: ApprovalId | None = None,
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
        approval_id=approval_id,
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
# the denial is one transaction
# --------------------------------------------------------------------------- #


class _TheEventWriteFailedError(RuntimeError):
    """Stands in for a store that cannot write the event it was given."""


def _a_hook_that_fails_the_denial_event_write() -> Callable[..., None]:
    """A ``before_cursor_execute`` hook that makes the denial's event fail to write.

    **The injection point is SQLAlchemy's ``before_cursor_execute``, not a
    hook in the store**, for the reason
    :mod:`tests.test_store_atomicity` gives: nothing in ``labcairn.db`` knows
    this test exists, so what is exercised is the production code path and the
    production transaction — the only way the result means anything about the
    shipped implementation rather than about a testing scaffold shaped like
    it. The product has no switch for injecting a fault and none is added
    here: the fault is injected by the test, and by nothing else.

    **The fault is the denial's own event and nothing else.** The write is
    failed for the row that carries the ``operation_denied`` event, found by
    that event's own document — and *only* for it, because a fault that hit
    the first event written would say nothing about the denial: the run's
    event is written first, and the run is not what is under test.

    The failure therefore lands inside the unit of work, after it has
    reserved the sequence numbers the events would have taken — so the
    rollback has something real to undo.
    """

    def hook(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        normalised = " ".join(statement.split()).lower()
        if " into events " not in f" {normalised} ":
            return
        values: list[Any] = []
        for item in parameters if isinstance(parameters, (list, tuple)) else (parameters,):
            if isinstance(item, (list, tuple)):
                values.extend(item)
            else:
                values.append(item)
        for value in values:
            if isinstance(value, str) and '"operation_denied"' in value:
                raise _TheEventWriteFailedError("the store could not write the event")

    return hook


def _what_the_store_holds(env: StoreEnv, task_id: TaskId) -> dict[str, int]:
    """What the database holds for this task, read through a **fresh** session.

    A rollback assertion that reads through the failed unit's own session
    proves little: an un-rolled-back transaction leaves that session unusable
    and the test dies with a ``PendingRollbackError`` instead of naming what
    survived. A new connection answers the question that matters — did this
    data reach the database — and answers it the same way whether or not the
    implementation under test cleaned up after itself.

    The counter is read as well, because it is the one thing the failed unit
    had already written when the write failed: a denial that leaves it
    advanced has not rolled back, whatever else the tables say.

    **The store's own session is committed first, and that is deliberate.**
    Every transaction in this database begins with ``BEGIN IMMEDIATE``, so a
    second connection cannot start while the first one is open; and a
    transaction left open by a unit of work that did not roll back would
    otherwise be invisible here — a *commit* ends it and lets the fresh
    connection see whatever it was holding, so a denial that left a
    half-written trace behind is caught rather than quietly discarded.
    """
    env.session.commit()
    session = env.new_session()
    try:
        return {
            "runs": len(list_runs(session, task_id)),
            "stages": len(list_stages(session, task_id)),
            "operations": len(list_operations(session, task_id)),
            "events": count_events(session, task_id),
            "seq": last_seq(session, task_id),
        }
    finally:
        session.close()


def test_a_denial_whose_event_cannot_be_written_leaves_nothing_at_all(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The denial's whole trace is one transaction, so a failed write leaves nothing.

    The run, the stage, the operation and the events that describe them are
    written by one unit of work. If the ``operation_denied`` event cannot be
    written, the transaction is rolled back and **nothing the denial created
    survives**: no run, no stage, no operation. A run in ``running`` and a
    stage in ``entered`` are exactly the trace that could be mistaken for a
    partial success, and the records module says a refusal must not leave
    one.

    **How it goes red.** The event write is made to fail and the store is read
    back through a fresh connection. Put the run and the stage back into units
    of work of their own — the shape the code had before — and they are
    committed before the event that says the write was refused, so the store
    holds them afterwards and this fails on the first assertion. The counter is
    asserted too: it was advanced inside the transaction, so a denial that
    leaves it advanced has not rolled back.
    """
    context = _make_context(env, workspace_root, _deny_all())
    before = _what_the_store_holds(env, context.task_id)
    hook = _a_hook_that_fails_the_denial_event_write()
    sa_event.listen(env.engine, "before_cursor_execute", hook)
    try:
        with pytest.raises(_TheEventWriteFailedError):
            run_stage(context, _stage_request(), _work)
    finally:
        sa_event.remove(env.engine, "before_cursor_execute", hook)

    after = _what_the_store_holds(env, context.task_id)
    assert after["runs"] == 0
    assert after["stages"] == 0
    assert after["operations"] == 0
    assert after == before


def test_a_denial_that_succeeds_leaves_the_run_the_stage_and_the_operation(
    env: StoreEnv, workspace_root: Path
) -> None:
    """What the denial leaves when it works is what it always left.

    The transaction changed how the denial is written, not what it writes: a
    run in ``running``, a stage in ``failed``, an operation in ``denied``, and
    the three events that say so — ``run_started``, ``stage_entered`` and
    ``operation_denied``.

    **How it goes red.** Every one of those is read back out of the database,
    and the events are read in order, so a fix that made the denial atomic by
    dropping one of the three rows would fail here rather than pass quietly.
    """
    context = _make_context(env, workspace_root, _deny_all())
    _assert_refused(
        lambda: run_stage(context, _stage_request(), _work),
        ApplicationRefusal.PERMISSION_DENIED,
    )

    runs = list_runs(env.session, context.task_id)
    stages = list_stages(env.session, context.task_id)
    operations = list_operations(env.session, context.task_id)
    assert [run.status for run in runs] == [RunStatus.RUNNING]
    assert [stage.status for stage in stages] == [StageStatus.FAILED]
    assert [operation.state for operation in operations] == [OperationState.DENIED]
    written = [event.type for event in events_after(env.session, context.task_id, after_seq=0)]
    assert written == [
        EventType.TASK_CREATED,
        EventType.RUN_STARTED,
        EventType.STAGE_ENTERED,
        EventType.OPERATION_DENIED,
    ]


# --------------------------------------------------------------------------- #
# the refusals that write nothing, each witnessed by name
# --------------------------------------------------------------------------- #


def _an_operation_whose_outcome_is_unknown(env: StoreEnv, task_id: TaskId) -> None:
    """A run, a stage, and an operation the record cannot say the outcome of.

    Written straight into the store rather than through the layer, because the
    question the witness asks is what the *refusal* leaves, and the layer's
    own writes would be indistinguishable from it.
    """
    run = make_run(task_id)
    stage = make_stage(task_id, run.run_id)
    with env.store().unit(task_id) as work:
        work.put_run(run)
        work.put_stage(stage)
    operation = make_operation(
        task_id,
        run.run_id,
        stage.stage_id,
        state=OperationState.UNCERTAIN,
        capability=CapabilityId.ANALYSIS_RUN.value,
        resource_key="materials/one.csv",
    )
    with env.store().unit(task_id) as work:
        work.put_operation(operation)


def test_the_recovery_uncertain_refusal_leaves_nothing_at_all(
    env: StoreEnv, workspace_root: Path
) -> None:
    """**The recovery-uncertain refusal** leaves the store exactly as it found it.

    The refusal says the outcome of an earlier operation is unknown, and it
    is raised before anything is planned for this one. Nothing is written for
    the refused work: no run, no stage, no operation, and no event.

    **How it goes red.** The store is read before and after, through a fresh
    connection. Move the recovery pass after the records — the order
    :func:`labcairn.application.stages.run_stage` has today — and the refused
    run's records are written before the refusal, and the counts differ.
    """
    context = _make_context(env, workspace_root, _allow_all())
    _an_operation_whose_outcome_is_unknown(env, context.task_id)
    before = _what_the_store_holds(env, context.task_id)
    _assert_refused(
        lambda: run_stage(context, _stage_request(), _work),
        ApplicationRefusal.OPERATION_UNCERTAIN,
    )
    assert _what_the_store_holds(env, context.task_id) == before


def _an_approval_over_one_file() -> ApprovalRequest:
    """A request for an approval over one file."""
    return ApprovalRequest(
        use=ApprovalUse(
            capability=CapabilityId.ANALYSIS_RUN,
            arguments=_stage_request().arguments,
            root_id="source:0",
            resource_key="one.csv",
        ),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def _a_granted_approval_over_one_file(context: ApplicationContext) -> ApprovalId:
    """An approval a human granted, over one file."""
    moment = datetime.now(UTC)
    asked = request_approval(context, _an_approval_over_one_file(), now=moment)
    granted = grant_approval(context, asked.approval.approval_id, now=moment)
    return granted.approval.approval_id


def test_the_approval_that_does_not_cover_the_request_leaves_nothing_at_all(
    env: StoreEnv, workspace_root: Path
) -> None:
    """**The approval-consumed refusal** leaves the store exactly as it found it.

    An approval was granted over one file and the request is for another, so
    the digest the ledger recomputes is not the one the approval carries, and
    the approval cannot be spent. The refusal is raised before anything is
    planned for the work, and the approval is not spent either: an approval
    that was spent and refused at the same time would leave the operator with
    neither the consent nor the work.

    **How it goes red.** The store is read before and after, through a fresh
    connection, and the approval's own state is read as well. Write anything
    for the refused request — an operation, a stage, or a spent approval — and
    one of the two differs.
    """
    context = _make_context(env, workspace_root, _ask_all())
    approval_id = _a_granted_approval_over_one_file(context)
    moment = datetime.now(UTC) + timedelta(minutes=1)
    before = _what_the_store_holds(env, context.task_id)
    _assert_refused(
        lambda: run_stage(
            context,
            _stage_request(resource_key="two.csv", approval_id=approval_id),
            _work,
            now=moment,
        ),
        ApplicationRefusal.APPROVAL_REFUSED,
    )
    assert _what_the_store_holds(env, context.task_id) == before
    with store_refusals():
        approvals = list_approvals(env.session, context.task_id)
    assert [approval.state for approval in approvals] == [ApprovalState.GRANTED]


def test_the_approval_that_was_never_issued_leaves_nothing_at_all(
    env: StoreEnv, workspace_root: Path
) -> None:
    """**The approval-missing refusal** leaves the store exactly as it found it.

    An approval id nobody issued is refused before anything is planned for the
    request — and before the approval could be spent, because an approval
    that was spent and refused at the same time would leave the operator with
    neither the consent nor the work.

    **How it goes red.** The store is read before and after, through a fresh
    connection: a run, a stage, an operation or an event written for a
    request nobody agreed to is one of them.
    """
    context = _make_context(env, workspace_root, _ask_all())
    before = _what_the_store_holds(env, context.task_id)
    _assert_refused(
        lambda: run_stage(
            context,
            _stage_request(approval_id=ApprovalId(new_id())),
            _work,
        ),
        ApplicationRefusal.APPROVAL_MISSING,
    )
    assert _what_the_store_holds(env, context.task_id) == before


def test_the_approval_requests_own_refusal_leaves_nothing_at_all(
    env: StoreEnv, workspace_root: Path
) -> None:
    """**The approval request's own refusal** leaves the store as it found it.

    This is the other consent path: the approval module asks the policy
    through :func:`labcairn.application.consent.evaluate`, which raises, where
    the stage layer asks through
    :func:`labcairn.application.consent.decide` and records the verdict it is
    given. A request for approval that the policy refuses never got as far as
    a write — there is no run, no stage and no operation for a denial to
    belong to, and inventing them would be the very trace that could be
    mistaken for a partial success.

    **How it goes red.** The store is read before and after, through a fresh
    connection: a run, a stage, an operation, an approval or an event written
    for a request the policy refused is one of them.
    """
    context = _make_context(env, workspace_root, _deny_all())
    before = _what_the_store_holds(env, context.task_id)
    _assert_refused(
        lambda: request_approval(context, _an_approval_over_one_file()),
        ApplicationRefusal.PERMISSION_DENIED,
    )
    assert _what_the_store_holds(env, context.task_id) == before


def test_the_approval_grants_own_refusal_leaves_nothing_at_all(
    env: StoreEnv, workspace_root: Path
) -> None:
    """**The approval grant's own refusal** leaves the store as it found it.

    An approval that has already been granted is not waiting for an answer,
    so granting it again is refused. The refusal comes before the grant is
    written, so the ledger does not carry two grants for one approval.

    **How it goes red.** The store is read before and after, through a fresh
    connection: a second grant, a second event, or a changed approval row is
    one of them.
    """
    context = _make_context(env, workspace_root, _ask_all())
    asked = request_approval(context, _an_approval_over_one_file())
    grant_approval(context, asked.approval.approval_id)
    before = _what_the_store_holds(env, context.task_id)
    _assert_refused(
        lambda: grant_approval(context, asked.approval.approval_id),
        ApplicationRefusal.APPROVAL_REFUSED,
    )
    assert _what_the_store_holds(env, context.task_id) == before


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
