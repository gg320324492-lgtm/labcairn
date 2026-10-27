"""Approvals are single-use, and single-use is enforced by a statement.

ADR-0003 C4 lists seven refusal reasons, and this file walks every one of them
against the DB-backed :class:`~labcairn.recovery.approvals.ApprovalStore` rather
than against the frozen
:meth:`~labcairn.runtime.operation.Approval.refusal_reason` contract directly.
That distinction is the point: LC-P1-04 proved the *rules* are right by passing
*flags* to the contract. This proves the *enforcement* around them is right, and
the enforcement is where a rule quietly stops applying — a check computed but
not compared, a comparison whose result is ignored, a consume that happens after
the effect instead of before it.

The test that matters most is
:func:`test_two_connections_cannot_spend_one_approval`. It is the only one that
would fail if the conditional ``UPDATE ... WHERE state='granted'`` were replaced
with an ordinary Python read-check-write, because a single session cannot
observe its own write-check-write race.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_recovery_support import SCENARIO_NOW, Scenario, build_scenario
from test_store_support import StoreEnv, make_task
from test_store_support import env as _shared_env

from labcairn.core.ids import ApprovalId, OperationId, TaskId, new_id
from labcairn.db.models import ApprovalRow
from labcairn.db.repository import TaskStore
from labcairn.recovery.approvals import (
    ApprovalAlreadySpentError,
    ApprovalStore,
    conditional_spend,
)
from labcairn.recovery.contracts import hash_bytes
from labcairn.reports.receipt import ArtifactKind
from labcairn.runtime.operation import Approval, ApprovalRefusal, ApprovalState
from labcairn.security.approval import (
    AuthorizationRefusedError,
    NoSuchApprovalError,
    SourceBinding,
    content_hash,
)

pytestmark = pytest.mark.integration

# pytest resolves a fixture by the parameter name in a test's signature, so the
# shared `env` fixture must be bound under that name. Aliasing the import and
# rebinding it reads as a plain assignment rather than an F811 redefinition —
# the same idiom as tests/test_store_atomicity.py.
env = _shared_env

CAPABILITY = "labcairn.artifact.write"
RESOURCE = "outputs/report.md"
ARGS: dict[str, object] = {"kind": "report"}
POLICY = "policy-digest-at-grant"
BODY = b"# Findings\n"


def _granted(env: StoreEnv, tmp_path: Path, **kwargs: object) -> tuple[Scenario, ApprovalId]:
    """A scenario plus one GRANTED approval, with the run/stage it needs.

    Built in one place because every refusal test needs the identical starting
    point, and a test that varied the setup would be testing its own fixture.
    """
    scenario = build_scenario(env, tmp_path)
    store = ApprovalStore(scenario.store(), scenario.session, clock=lambda: SCENARIO_NOW)
    operation_id = OperationId(new_id())

    # The approval's events are Run-scoped, so the operation it names must exist.
    _seed_operation(scenario, operation_id)

    approval = store.request(
        scenario.task_id,
        scenario.run_id,
        operation_id,
        capability=CAPABILITY,
        resource_key=RESOURCE,
        args=ARGS,
    )
    granted = store.grant(scenario.task_id, approval.approval_id)
    assert granted.state is ApprovalState.GRANTED
    return scenario, approval.approval_id


def _seed_operation(scenario: Scenario, operation_id: OperationId) -> None:
    """Write the operation row an approval's events point at."""
    from labcairn.runtime.operation import Operation, OperationState, compute_args_digest

    operation = Operation(
        operation_id=operation_id,
        task_id=scenario.task_id,
        run_id=scenario.run_id,
        stage_id=scenario.stage_id,
        state=OperationState.PLANNED,
        capability=CAPABILITY,
        resource_key=RESOURCE,
        depends_on=(),
        args_digest=compute_args_digest(
            task_id=scenario.task_id,
            capability=CAPABILITY,
            resource_key=RESOURCE,
            args=dict(ARGS),
        ),
    )
    with scenario.store().unit(scenario.task_id) as work:
        work.put_operation(operation)


def _consume(
    scenario: Scenario,
    approval_id: ApprovalId,
    *,
    args: dict[str, object] | None = None,
    task_id: TaskId | None = None,
    policy: str = POLICY,
    sources: tuple[SourceBinding, ...] = (),
    resolve_source: Callable[[str], Path] | None = None,
) -> Approval:
    """Consume *approval_id* through the store, with every input overridable."""
    resolve = resolve_source or (lambda key: scenario.root.joinpath(*key.split("/")))
    store = ApprovalStore(scenario.store(), scenario.session, clock=lambda: SCENARIO_NOW)
    return store.consume(
        task_id or scenario.task_id,
        approval_id,
        capability=CAPABILITY,
        resource_key=RESOURCE,
        args=args if args is not None else dict(ARGS),
        depends_on=(),
        current_policy_digest=policy,
        policy_digest_at_grant=POLICY,
        sources=sources,
        resolve_source=resolve,
    )


# --------------------------------------------------------------------------- #
# the happy path, so the refusals below are refusals and not a broken fixture
# --------------------------------------------------------------------------- #


def test_a_granted_approval_is_consumed_once(env, tmp_path):  # type: ignore[no-untyped-def]
    scenario, approval_id = _granted(env, tmp_path)
    consumed = _consume(scenario, approval_id)
    assert consumed.state is ApprovalState.CONSUMED
    assert consumed.consumed_at == SCENARIO_NOW


# --------------------------------------------------------------------------- #
# ADR-0003 C4's refusal reasons
# --------------------------------------------------------------------------- #


def test_expired_approval_is_not_reusable(env, tmp_path):  # type: ignore[no-untyped-def]
    """An approval that aged out is expired even though no row says so.

    The row still reads GRANTED — nothing moved it — and the refusal comes from
    comparing ``expires_at`` against the supplied ``now``. A store that trusted
    the row's own state would honour it.
    """
    scenario = build_scenario(env, tmp_path)
    store = ApprovalStore(scenario.store(), scenario.session, clock=lambda: SCENARIO_NOW)
    operation_id = OperationId(new_id())
    _seed_operation(scenario, operation_id)

    approval = store.request(
        scenario.task_id,
        scenario.run_id,
        operation_id,
        capability=CAPABILITY,
        resource_key=RESOURCE,
        args=ARGS,
        expires_at=SCENARIO_NOW + timedelta(seconds=60),
    )
    store.grant(scenario.task_id, approval.approval_id)

    later = ApprovalStore(
        scenario.store(),
        scenario.session,
        clock=lambda: SCENARIO_NOW + timedelta(hours=1),
    )
    with pytest.raises(AuthorizationRefusedError) as raised:
        later.consume(
            scenario.task_id,
            approval.approval_id,
            capability=CAPABILITY,
            resource_key=RESOURCE,
            args=dict(ARGS),
            depends_on=(),
            current_policy_digest=POLICY,
            policy_digest_at_grant=POLICY,
            resolve_source=lambda key: scenario.root.joinpath(*key.split("/")),
        )
    assert raised.value.refusal is ApprovalRefusal.EXPIRED
    assert _state_of(scenario, approval.approval_id) == "granted", (
        "a refused approval must still be unspent — refusing a request is not using it"
    )


def test_approval_is_single_use(env, tmp_path):  # type: ignore[no-untyped-def]
    """Identical arguments, twice. The second is refused."""
    scenario, approval_id = _granted(env, tmp_path)
    _consume(scenario, approval_id)

    with pytest.raises(AuthorizationRefusedError) as raised:
        _consume(scenario, approval_id)
    assert raised.value.refusal is ApprovalRefusal.CONSUMED


def test_approval_rejected_when_arguments_change(env, tmp_path):  # type: ignore[no-untyped-def]
    """Granted for one argument set, attempted with another."""
    scenario, approval_id = _granted(env, tmp_path)
    with pytest.raises(AuthorizationRefusedError) as raised:
        _consume(scenario, approval_id, args={"kind": "figure"})
    assert raised.value.refusal is ApprovalRefusal.ARGS_CHANGED


def test_approval_rejected_on_task_scope_mismatch(env, tmp_path):  # type: ignore[no-untyped-def]
    """Granted in task A, attempted from task B."""
    scenario, approval_id = _granted(env, tmp_path)
    other = _second_task(scenario)

    with pytest.raises(AuthorizationRefusedError) as raised:
        _consume(scenario, approval_id, task_id=other.task_id)
    assert raised.value.refusal is ApprovalRefusal.TASK_SCOPE_MISMATCH


def test_approval_rejected_when_policy_changed(env, tmp_path):  # type: ignore[no-untyped-def]
    """The policy in force at use is not the one it was decided under."""
    scenario, approval_id = _granted(env, tmp_path)
    with pytest.raises(AuthorizationRefusedError) as raised:
        _consume(scenario, approval_id, policy="a-different-policy-digest")
    assert raised.value.refusal is ApprovalRefusal.POLICY_CHANGED


def test_approval_invalidated_by_source_change(env, tmp_path):  # type: ignore[no-untyped-def]
    """``depends_on`` holds H1; the file is now H2.

    The material is written *after* the approval was granted and is never
    mentioned to the store again — the store re-reads it from disk at the moment
    of use, which is the only version of this check that means anything.
    """
    scenario, _issued = _granted(env, tmp_path)
    material = scenario.root / "materials" / "input.txt"
    material.parent.mkdir(parents=True, exist_ok=True)
    material.write_bytes(b"the original source\n")

    binding = SourceBinding(
        resource_key="materials/input.txt", expected_hash=content_hash(material)
    )

    # Unchanged material: the approval is usable.
    _consume(scenario, _fresh_granted(scenario), sources=(binding,))

    # Now the source moves under us. A brand-new approval is issued for the same
    # request, so the only thing that can refuse it is the re-hash the store does
    # at the moment of use.
    material.write_bytes(b"an edited source\n")
    later = _fresh_granted(scenario)
    with pytest.raises(AuthorizationRefusedError) as raised:
        _consume(scenario, later, sources=(binding,))
    assert raised.value.refusal is ApprovalRefusal.SOURCE_CHANGED
    assert "materials/input.txt" in str(raised.value), (
        "the refusal must name which source moved; 'retry the stage' and 'the "
        "upstream document was edited' are different advice"
    )


def test_a_missing_source_counts_as_changed(env, tmp_path):  # type: ignore[no-untyped-def]
    """A binding whose file is gone has not been verified, so it has not held.

    Failing closed here is what stops a resume from re-running an operation
    against an input that no longer exists.
    """
    scenario = build_scenario(env, tmp_path)
    binding = SourceBinding(resource_key="materials/absent.txt", expected_hash=hash_bytes(b"x"))
    granted = _fresh_granted(scenario)
    with pytest.raises(AuthorizationRefusedError) as raised:
        _consume(scenario, granted, sources=(binding,))
    assert raised.value.refusal is ApprovalRefusal.SOURCE_CHANGED


# --------------------------------------------------------------------------- #
# the guarantee the ADR actually rests on
# --------------------------------------------------------------------------- #


def test_the_conditional_update_is_what_makes_an_approval_single_use(env, tmp_path):  # type: ignore[no-untyped-def]
    """The ``state='granted'`` predicate is load-bearing; assert that directly.

    **What mutation testing forced this test to be.** A first draft tried to
    provoke the lost update end-to-end, with two threads released from a barrier
    from inside ``consume``. It proved nothing, twice over:

    1. With the barrier *before* ``consume``, thread 1 could finish before thread
       2's SELECT, so the second thread was refused by
       :meth:`Approval.refusal_reason`'s ordinary state check and never reached
       the UPDATE.
    2. With the barrier moved *inside* the call — at ``resolve_source``, which
       runs between the row read and the write — both threads deadlock instead:
       every unit opens with ``BEGIN IMMEDIATE`` (ADR-0003 C3), so thread 1 holds
       SQLite's write lock from its own SELECT while waiting at the barrier, and
       thread 2 blocks on the lock. The test timed out with no outcome at all.

    The second result is the real finding, and it is a *good* one: under
    ``BEGIN IMMEDIATE`` a lost update through this API is structurally
    unreachable, because the read that precedes the write is already serialised.
    The predicate is defence in depth against a future change to the transaction
    boundary — it is not what is currently holding the guarantee up.

    So this test asserts the claim that can actually be established: the
    statement itself refuses a second spend. Dropping the predicate turns the
    second call from zero matched rows into one, and this goes red.
    """
    scenario, approval_id = _granted(env, tmp_path)
    session = scenario.session
    before = session.execute(
        select(ApprovalRow.state).where(ApprovalRow.approval_id == str(approval_id))
    ).scalar_one()
    assert before == "granted"

    # The product's own statement, not a copy of it. An earlier draft re-wrote
    # the UPDATE here, which meant deleting the predicate from `approvals.py`
    # left this test green — the single most important thing this test exists to
    # catch, missed because it was not testing the real thing.
    first = session.execute(conditional_spend(approval_id, SCENARIO_NOW))
    second = session.execute(conditional_spend(approval_id, SCENARIO_NOW))

    assert first.rowcount == 1, "the first spend must match exactly one row"
    assert second.rowcount == 0, (
        "the second spend matched a row. This is the value "
        "ApprovalStore.consume asserts on, and it is what a read-check-write "
        "in Python would fail to detect."
    )
    session.rollback()


def test_concurrent_spends_leave_the_row_consumed_exactly_once(env, tmp_path):  # type: ignore[no-untyped-def]
    """Whatever the interleaving, one approval is spent once.

    Weaker than the statement test above, and deliberately so: it asserts the
    *invariant* rather than forcing a particular race. With ``BEGIN IMMEDIATE``
    every unit takes the write lock up front, so the threads serialise at their
    first statement and the loser is refused on read rather than at the UPDATE.
    The outcome markers are disjoint — ``"spent"`` versus ``"raced"`` versus a
    refusal — because ``ApprovalRefusal.CONSUMED.value`` is the string
    ``"consumed"``, which a shared marker would have recorded as a second
    success.
    """
    scenario, approval_id = _granted(env, tmp_path)
    factory = scenario.env.factory
    outcomes: list[str] = []
    lock = threading.Lock()

    def attempt() -> None:
        session = factory()
        try:
            store = ApprovalStore(_store_for(session), session, clock=lambda: SCENARIO_NOW)
            try:
                store.consume(
                    scenario.task_id,
                    approval_id,
                    capability=CAPABILITY,
                    resource_key=RESOURCE,
                    args=dict(ARGS),
                    depends_on=(),
                    current_policy_digest=POLICY,
                    policy_digest_at_grant=POLICY,
                    resolve_source=lambda key: scenario.root.joinpath(*key.split("/")),
                )
                marker = "spent"
            except ApprovalAlreadySpentError:
                marker = "raced"
            except AuthorizationRefusedError as exc:
                marker = f"refused:{exc.refusal.value}"
            with lock:
                outcomes.append(marker)
        finally:
            session.close()

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert not any(thread.is_alive() for thread in threads), "a consuming thread hung"
    assert outcomes.count("spent") == 1, (
        f"an approval was spent {outcomes.count('spent')} times; outcomes={outcomes}"
    )
    assert len(outcomes) == 2, outcomes
    assert _state_of(scenario, approval_id) == "consumed"


def test_consumption_happens_before_the_effect(env, tmp_path):  # type: ignore[no-untyped-def]
    """A spent approval stops a second *effect*, not merely a second record.

    The executor refuses to start a write-ahead intent on an approval that is
    already CONSUMED, so the spend is visible at the point where it would matter
    — before anything has been attempted.
    """
    scenario, approval_id = _granted(env, tmp_path)
    consumed = _consume(scenario, approval_id)

    counter = scenario.counter()
    effect = counter.plan(RESOURCE, BODY)

    from labcairn.recovery.contracts import RecoveryError

    with pytest.raises(RecoveryError, match="already consumed"):
        scenario.executor().execute(
            scenario.task_id,
            scenario.run_id,
            scenario.stage_id,
            capability=CAPABILITY,
            effect=effect,
            args=dict(ARGS),
            approval=consumed,
            kind=ArtifactKind.REPORT,
        )
    assert counter.calls == 0, "refusal must precede the effect, not follow it"


def test_an_unknown_approval_is_distinct_from_a_refused_one(env, tmp_path):  # type: ignore[no-untyped-def]
    """ "Was this ever approved?" and "was it refused?" are different questions."""
    scenario = build_scenario(env, tmp_path)
    with pytest.raises(NoSuchApprovalError):
        _consume(scenario, ApprovalId(new_id()))


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _state_of(scenario: Scenario, approval_id: ApprovalId) -> str:
    found: str = scenario.session.execute(
        select(ApprovalRow.state).where(ApprovalRow.approval_id == str(approval_id))
    ).scalar_one()
    return found


def _fresh_granted(scenario: Scenario) -> ApprovalId:
    """A newly granted approval, for tests that need two independent spends."""
    store = ApprovalStore(scenario.store(), scenario.session, clock=lambda: SCENARIO_NOW)
    operation_id = OperationId(new_id())
    _seed_operation(scenario, operation_id)
    approval = store.request(
        scenario.task_id,
        scenario.run_id,
        operation_id,
        capability=CAPABILITY,
        resource_key=RESOURCE,
        args=ARGS,
    )
    return store.grant(scenario.task_id, approval.approval_id).approval_id


def _store_for(session: Session) -> TaskStore:
    return TaskStore(session, clock=lambda: SCENARIO_NOW)


def _second_task(scenario: Scenario):  # type: ignore[no-untyped-def]
    task = make_task(title="Another task", now=SCENARIO_NOW)
    scenario.store().create_task(task)
    return task
