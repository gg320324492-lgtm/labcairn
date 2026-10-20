"""The application layer: the seam, the consent, and the one refusal.

Three properties are asserted here, and each of them is the property the layer
exists to have.

**It is the only way to the task state.** The first test walks the package and
fails if any module outside the layer and the store reaches past it. That test
is a *guard*, not a description: it is the thing that keeps the layer a seam
when the next module is written.

**Every operation goes through the capability model.** A policy that denies
the capability must stop the operation, and the work must not run. The tests
are written so that a denial is checked *after* the fact as well — the effect
is not run, and nothing is written — because an operation that refuses but
has already had its effect is worse than one that did not refuse at all.

**One refusal, one shape.** Every refusal is an
:class:`~labcairn.application.refusal.ApplicationRefusedError` with a
machine-readable reason, and every surface renders it the same way, without
knowing which operation produced it.

The rest is behavioural: what the operations return, what the plan and the
steps say, what happens when an approval is granted for one set of
arguments and spent on another, and what a page of the event log says about
where a client resumes from.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_store_support import StoreEnv
from test_store_support import env as _shared_env

from labcairn.application import (
    ApplicationContext,
    ApplicationRefusal,
    ApplicationRefusedError,
    ApprovalRequest,
    ApprovalUse,
    EventPage,
    Result,
    StageOutcome,
    StageRequest,
    consume_approval,
    create_task,
    grant_approval,
    inspect_source,
    list_artifacts,
    list_sources,
    list_tasks,
    read_artifact,
    read_events,
    read_plan,
    read_steps,
    read_task_state,
    render_report,
    request_approval,
    run_stage,
)
from labcairn.application.events import MAX_EVENT_LIMIT, MIN_EVENT_LIMIT
from labcairn.application.reports import ReportRequest
from labcairn.core.ids import ApprovalId, SourceId, TaskId, new_id
from labcairn.db.materials import put_source
from labcairn.db.repository import count_events, events_after
from labcairn.reports.receipt import ArtifactKind, ArtifactProducerKind, ArtifactReceipt
from labcairn.runtime.event import Event, EventStreamRequest, EventType
from labcairn.runtime.lifecycle import StageStatus, TaskGoal
from labcairn.runtime.operation import ApprovalState, OperationState
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import CapabilityId
from labcairn.security.policy import Permission, PermissionPolicy, Rule
from labcairn.sources.source import Source, SourceKind, SourceReadability
from labcairn.workspace.roots import Workspace

# pytest resolves a fixture by the parameter name in a test's signature, so the
# shared `env` fixture must be bound under that name here.
env = _shared_env

_MOMENT = datetime(2026, 1, 1, tzinfo=UTC)
_HASH = "b" * 64


# --------------------------------------------------------------------------- #
# the policies
# --------------------------------------------------------------------------- #


def _allow_all() -> PermissionPolicy:
    """A policy that allows everything, so a test can vary one thing at a time."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])


def _deny_all() -> PermissionPolicy:
    """A policy that denies everything."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.DENY, pattern="**")])


def _ask_all() -> PermissionPolicy:
    """A policy that asks about everything, which is a question, not a denial."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ASK, pattern="**")])


# --------------------------------------------------------------------------- #
# the environment
# --------------------------------------------------------------------------- #


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """A workspace with a source directory in it."""
    root = tmp_path / "workspace"
    (root / "materials").mkdir(parents=True)
    return root


def _source(source_id: str, relative_path: str) -> Source:
    """A valid source, for the ledger."""
    return Source(
        source_id=source_id,
        kind=SourceKind.CSV,
        display_name=f"Material {source_id}",
        relative_path=relative_path,
        content_sha256=_HASH,
        size_bytes=12,
        readability=SourceReadability.READABLE,
        ingested_at=_MOMENT,
    )


def _make_context(
    env: StoreEnv,
    workspace_root: Path,
    policy: PermissionPolicy,
    *,
    ledger: ApprovalLedger | None = None,
    bound_sources: tuple[SourceId, ...] = (),
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
        bound_source_ids=bound_sources,
    )
    return ApplicationContext(
        workspace=created.workspace,
        store=store,
        policy=policy,
        ledger=ledger if ledger is not None else ApprovalLedger(),
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
        arguments=arguments if arguments is not None else {"operator_id": "mean", "parameters": {}},
        root_id=root_id,
        resource_key=resource_key,
        approval_id=approval_id,
    )


def _work(resource: object) -> StageOutcome:
    """A stage's work that succeeds and produces nothing."""
    del resource
    return StageOutcome(output_hashes=(_HASH,))


def _assert_refused(
    call: Callable[[], object], reason: ApplicationRefusal
) -> ApplicationRefusedError:
    """Run *call*, and insist it refused for *reason*."""
    with pytest.raises(ApplicationRefusedError) as caught:
        call()
    assert caught.value.reason is reason
    return caught.value


# --------------------------------------------------------------------------- #
# the guard: the layer is the only way to the store
# --------------------------------------------------------------------------- #


#: The modules that may reach the store's readers or its rows.
#:
#: The store package is the store. The application package is the layer. The
#: rest **predate** the layer: they are merged, accepted code that the layer
#: was added on top of and that this task may not rewrite. They are recorded
#: here rather than tolerated, so that the set is a decision somebody made
#: rather than a drift nobody noticed.
_ALLOWED_STORE_READERS = frozenset(
    {
        # The store itself.
        "labcairn.db",
        "labcairn.db.materials",
        "labcairn.db.models",
        "labcairn.db.repository",
        "labcairn.db.session",
        # The layer.
        "labcairn.application.approvals",
        "labcairn.application.artifacts",
        "labcairn.application.context",
        "labcairn.application.events",
        "labcairn.application.records",
        "labcairn.application.sources",
        "labcairn.application.stages",
        "labcairn.application.tasks",
        # Predate the layer.
        "labcairn.analysis.service",
        "labcairn.recovery.approvals",
        "labcairn.recovery.executor",
        "labcairn.recovery.persistence",
        "labcairn.recovery.reconciliation",
        "labcairn.recovery.resume",
        "labcairn.recovery.stages",
    }
)


def _modules_touching_the_store(package_root: Path) -> set[str]:
    """The modules that import the store's readers or the store's rows.

    Parsed rather than grepped: a docstring that *names* ``labcairn.db.models``
    is not an import of it, and a guard that counted prose would be a guard
    that could be satisfied by a comment.
    """
    found: set[str] = set()
    for path in sorted((package_root / "src" / "labcairn").rglob("*.py")):
        relative = path.relative_to(package_root / "src").with_suffix("")
        parts = list(relative.parts)
        if parts[-1] == "__init__":
            parts.pop()
        module = ".".join(parts)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            imported: list[str] = []
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = [node.module]
            if any(name in ("labcairn.db.repository", "labcairn.db.models") for name in imported):
                found.add(module)
    return found


def test_no_module_outside_the_layer_reaches_past_it(repo_root: Path) -> None:
    """The layer is the only way to the store, and the exceptions are recorded.

    A surface that imported the store's readers could read the task state
    without the capability model, and a guard applied to an operation would
    apply to seven of the eight callers. This test is what keeps that from
    happening by accident: a new module that reaches the store fails here,
    and the failure says what the recorded set is.
    """
    touching = _modules_touching_the_store(repo_root)
    unexpected = touching - _ALLOWED_STORE_READERS
    assert not unexpected, (
        "these modules reach the task store from outside the application layer: "
        f"{sorted(unexpected)}. The layer exists so that a guard applied to an "
        "operation applies to every caller; a module that reads the store directly "
        "is a caller the guard does not reach. Add it to "
        "_ALLOWED_STORE_READERS only if it predates the layer, and say why."
    )


def test_the_layer_itself_reads_and_writes_through_the_store(repo_root: Path) -> None:
    """The guard is not vacuous: the layer really does use the store.

    Without this, a layer that stopped touching the store would satisfy the
    guard above for the wrong reason.
    """
    touching = _modules_touching_the_store(repo_root)
    assert "labcairn.application.events" in touching
    assert "labcairn.application.records" in touching
    assert "labcairn.application.tasks" in touching


# --------------------------------------------------------------------------- #
# the consent
# --------------------------------------------------------------------------- #


def test_creating_a_task_is_denied_by_a_deny_policy(env: StoreEnv, workspace_root: Path) -> None:
    """The one operation with no approval to bind is still gated.

    Creating a task has nothing to be approved against -- an approval is
    scoped to a task and the task does not exist yet -- so its consent is the
    policy's verdict and the policy's verdict alone.
    """
    _assert_refused(
        lambda: create_task(
            store=env.store(),
            policy=_deny_all(),
            workspace_root=workspace_root,
            title="Refused task",
            goal=TaskGoal(
                objective="Establish whether the observation holds.",
                success_criterion="A cited answer.",
            ),
            source_dirs=(workspace_root / "materials",),
        ),
        ApplicationRefusal.PERMISSION_DENIED,
    )


def test_the_callers_path_argument_cannot_change_what_the_policy_judged(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The arguments and the verdict cannot name different things.

    The capability's ``path`` is taken from the resource the operation
    addresses, not from the caller. A caller that could put a different path
    in the arguments would have the policy say yes about one file while the
    operation went on to name another, and the approval's digest would cover
    the wrong one.

    The two runs differ only in the path the caller supplied, and their
    digests are equal because the caller's path was not in the digest.
    """
    context = _make_context(env, workspace_root, _allow_all())
    honest = run_stage(context, _stage_request(), _work, now=_MOMENT)
    lying = run_stage(
        context,
        _stage_request(arguments={"path": "other.csv", "operator_id": "mean", "parameters": {}}),
        _work,
        now=_MOMENT,
    )
    assert honest.operation.args_digest == lying.operation.args_digest


def test_reading_the_task_state_is_denied_by_a_deny_policy(
    env: StoreEnv, workspace_root: Path
) -> None:
    """A policy that denies the capability stops the read."""
    context = _make_context(env, workspace_root, _deny_all())
    _assert_refused(lambda: read_task_state(context), ApplicationRefusal.PERMISSION_DENIED)


def test_listing_the_tasks_is_denied_by_a_deny_policy(env: StoreEnv, workspace_root: Path) -> None:
    """Listing is a read of the task area, and it is gated like any other."""
    context = _make_context(env, workspace_root, _deny_all())
    _assert_refused(lambda: list_tasks(context), ApplicationRefusal.PERMISSION_DENIED)


def test_listing_the_artifacts_is_denied_by_a_deny_policy(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The artefact list is gated like the others."""
    context = _make_context(env, workspace_root, _deny_all())
    _assert_refused(lambda: list_artifacts(context), ApplicationRefusal.PERMISSION_DENIED)


def test_reading_the_plan_is_denied_by_a_deny_policy(env: StoreEnv, workspace_root: Path) -> None:
    """The plan is a read of the task's own record, and it is gated."""
    context = _make_context(env, workspace_root, _deny_all())
    _assert_refused(lambda: read_plan(context), ApplicationRefusal.PERMISSION_DENIED)


def test_reading_the_steps_is_denied_by_a_deny_policy(env: StoreEnv, workspace_root: Path) -> None:
    """The steps are gated like the plan."""
    context = _make_context(env, workspace_root, _deny_all())
    _assert_refused(lambda: read_steps(context), ApplicationRefusal.PERMISSION_DENIED)


def test_inspecting_a_source_is_denied_by_a_deny_policy(
    env: StoreEnv, workspace_root: Path
) -> None:
    """Reading supplied material is gated."""
    source_id = str(SourceId(new_id()))
    put_source(env.session, _source(source_id, "materials/one.csv"))
    context = _make_context(env, workspace_root, _deny_all())
    _assert_refused(
        lambda: inspect_source(context, source_id),
        ApplicationRefusal.PERMISSION_DENIED,
    )


def test_a_denied_policy_means_the_work_never_runs(env: StoreEnv, workspace_root: Path) -> None:
    """The consent comes before the effect, not after it.

    The work records that it ran; a refusal that arrived afterwards would
    leave the effect done and the caller told it was refused, which is the
    worst of the two answers.
    """
    context = _make_context(env, workspace_root, _deny_all())
    ran: list[object] = []

    def work(resource: object) -> StageOutcome:
        ran.append(resource)
        return StageOutcome()

    _assert_refused(
        lambda: run_stage(context, _stage_request(), work),
        ApplicationRefusal.PERMISSION_DENIED,
    )
    assert ran == []


def test_a_denied_policy_writes_nothing(env: StoreEnv, workspace_root: Path) -> None:
    """A refusal leaves no trace that could look like a partial success."""
    context = _make_context(env, workspace_root, _deny_all())
    before = count_events(env.session, context.task_id)
    _assert_refused(
        lambda: run_stage(context, _stage_request(), _work),
        ApplicationRefusal.PERMISSION_DENIED,
    )
    assert count_events(env.session, context.task_id) == before


def test_a_policy_that_asks_is_a_question_not_a_denial(env: StoreEnv, workspace_root: Path) -> None:
    """An ASK is refused as ``policy_asked``, which says the remedy is consent."""
    context = _make_context(env, workspace_root, _ask_all())
    _assert_refused(
        lambda: run_stage(context, _stage_request(), _work),
        ApplicationRefusal.POLICY_ASKED,
    )


def test_an_ask_is_answered_by_an_approval(env: StoreEnv, workspace_root: Path) -> None:
    """With an approval supplied, the ask is answered and the work runs."""
    ledger = ApprovalLedger()
    context = _make_context(env, workspace_root, _ask_all(), ledger=ledger)
    requested = request_approval(
        context,
        ApprovalRequest(
            use=_use(),
            expires_at=_MOMENT.replace(hour=1),
        ),
    )
    granted = grant_approval(context, requested.approval.approval_id, now=_MOMENT)
    assert granted.approval.state is ApprovalState.GRANTED

    result = run_stage(
        context,
        _stage_request(approval_id=granted.approval.approval_id),
        _work,
        now=_MOMENT,
    )
    assert result.operation.state is OperationState.CONFIRMED
    assert result.approval is not None
    assert result.approval.state is ApprovalState.CONSUMED


def test_an_approval_for_other_arguments_is_refused(env: StoreEnv, workspace_root: Path) -> None:
    """The digest is recomputed at the moment of use.

    An approval is bound to the arguments it was granted for, so a stage run
    with different arguments is refused rather than authorised by a consent
    that was given for something else.
    """
    ledger = ApprovalLedger()
    context = _make_context(env, workspace_root, _ask_all(), ledger=ledger)
    requested = request_approval(
        context,
        ApprovalRequest(use=_use(), expires_at=_MOMENT.replace(hour=1)),
    )
    grant_approval(context, requested.approval.approval_id, now=_MOMENT)

    _assert_refused(
        lambda: run_stage(
            context,
            _stage_request(
                approval_id=requested.approval.approval_id,
                arguments={"operator_id": "median", "parameters": {}},
            ),
            _work,
            now=_MOMENT,
        ),
        ApplicationRefusal.APPROVAL_REFUSED,
    )


def test_an_approval_is_spent_only_once(env: StoreEnv, workspace_root: Path) -> None:
    """One approval cannot authorise two effects."""
    ledger = ApprovalLedger()
    context = _make_context(env, workspace_root, _ask_all(), ledger=ledger)
    requested = request_approval(
        context,
        ApprovalRequest(use=_use(), expires_at=_MOMENT.replace(hour=1)),
    )
    grant_approval(context, requested.approval.approval_id, now=_MOMENT)
    run_stage(
        context,
        _stage_request(approval_id=requested.approval.approval_id),
        _work,
        now=_MOMENT,
    )
    _assert_refused(
        lambda: run_stage(
            context,
            _stage_request(approval_id=requested.approval.approval_id),
            _work,
            now=_MOMENT,
        ),
        ApplicationRefusal.APPROVAL_REFUSED,
    )


def test_consuming_an_approval_spends_it(env: StoreEnv, workspace_root: Path) -> None:
    """The standalone consume is the same machinery the run path uses."""
    ledger = ApprovalLedger()
    context = _make_context(env, workspace_root, _ask_all(), ledger=ledger)
    requested = request_approval(
        context,
        ApprovalRequest(use=_use(), expires_at=_MOMENT.replace(hour=1)),
    )
    grant_approval(context, requested.approval.approval_id, now=_MOMENT)
    consumed = consume_approval(
        context,
        requested.approval.approval_id,
        _use(),
        now=_MOMENT,
    )
    assert consumed.approval.state is ApprovalState.CONSUMED


def test_requesting_an_approval_for_a_denied_capability_is_refused(
    env: StoreEnv, workspace_root: Path
) -> None:
    """There is nothing to ask consent about when the policy says no."""
    context = _make_context(env, workspace_root, _deny_all())
    _assert_refused(
        lambda: request_approval(
            context,
            ApprovalRequest(use=_use(), expires_at=_MOMENT.replace(hour=1)),
        ),
        ApplicationRefusal.PERMISSION_DENIED,
    )


# --------------------------------------------------------------------------- #
# the refusal
# --------------------------------------------------------------------------- #


def test_every_refusal_is_the_same_type_with_a_reason_and_a_payload(
    env: StoreEnv, workspace_root: Path
) -> None:
    """A surface renders a refusal without knowing which operation produced it."""
    context = _make_context(env, workspace_root, _deny_all())
    refusal = _assert_refused(
        lambda: read_task_state(context),
        ApplicationRefusal.PERMISSION_DENIED,
    )
    payload = refusal.to_payload()
    assert payload["reason"] == "permission_denied"
    assert "permission_denied" in payload["message"]
    assert refusal.detail


def test_the_refusal_reason_is_machine_readable(env: StoreEnv, workspace_root: Path) -> None:
    """The reason is an enum member, not a string somebody parses."""
    context = _make_context(env, workspace_root, _deny_all())
    refusal = _assert_refused(
        lambda: read_task_state(context),
        ApplicationRefusal.PERMISSION_DENIED,
    )
    assert refusal.reason.value == "permission_denied"
    assert ApplicationRefusal("permission_denied") is ApplicationRefusal.PERMISSION_DENIED


# --------------------------------------------------------------------------- #
# the operations
# --------------------------------------------------------------------------- #


def test_the_task_state_carries_what_the_task_holds(env: StoreEnv, workspace_root: Path) -> None:
    """One read, one value: the task, its runs, its stages, its artefacts."""
    context = _make_context(env, workspace_root, _allow_all())
    state = read_task_state(context)
    assert state.task.task_id == context.task_id
    assert state.runs == ()
    assert state.stages == ()
    assert state.artifacts == ()
    assert state.last_event_seq >= 1


def test_the_task_state_is_serialisable_as_data(env: StoreEnv, workspace_root: Path) -> None:
    """The CLI's ``--json`` and the API's body are the same model."""
    context = _make_context(env, workspace_root, _allow_all())
    payload = read_task_state(context).model_dump_json()
    assert '"task_id"' in payload
    assert "Test task" in payload


def test_running_a_stage_records_the_run_the_stage_and_the_operation(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The stage run leaves the three records a reader needs."""
    context = _make_context(env, workspace_root, _allow_all())
    result = run_stage(context, _stage_request(), _work, now=_MOMENT)
    assert result.stage.name == "intake"
    assert result.stage.status is StageStatus.COMPLETED
    assert result.operation.state is OperationState.CONFIRMED

    state = read_task_state(context)
    assert len(state.runs) == 1
    assert len(state.stages) == 1
    assert state.stages[0].name == "intake"


def test_a_failing_stage_is_recorded_and_refused(env: StoreEnv, workspace_root: Path) -> None:
    """A failure is a refusal with a reason, and the failure is on the record."""
    context = _make_context(env, workspace_root, _allow_all())

    def work(resource: object) -> StageOutcome:
        del resource
        raise RuntimeError("the operator could not be resolved")

    _assert_refused(
        lambda: run_stage(context, _stage_request(), work, now=_MOMENT),
        ApplicationRefusal.STAGE_FAILED,
    )
    state = read_task_state(context)
    assert state.stages[0].status is StageStatus.FAILED


def test_asking_for_an_approval_parks_the_stage_with_the_reason(
    env: StoreEnv, workspace_root: Path
) -> None:
    """A stage waiting for a human looks different from a stage that is running.

    The stage is ``BLOCKED`` and the reason is on the row, because a bare
    status cannot say *why* a stage stopped, and a reader who sees
    ``BLOCKED`` with no reason has nothing to act on.
    """
    context = _make_context(env, workspace_root, _ask_all())
    request_approval(
        context,
        ApprovalRequest(use=_use(), expires_at=_MOMENT.replace(hour=1)),
        now=_MOMENT,
    )
    state = read_task_state(context)
    assert state.stages[0].status is StageStatus.BLOCKED
    assert state.stages[0].blocked_reason is not None
    assert "approval" in state.stages[0].blocked_reason
    assert state.approvals[0].state is ApprovalState.PENDING


def test_a_parked_stage_completes_when_the_approval_arrives(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The stage that was waiting for a human runs when the answer comes."""
    ledger = ApprovalLedger()
    context = _make_context(env, workspace_root, _ask_all(), ledger=ledger)
    requested = request_approval(
        context,
        ApprovalRequest(use=_use(), expires_at=_MOMENT.replace(hour=1)),
        now=_MOMENT,
    )
    grant_approval(context, requested.approval.approval_id, now=_MOMENT)
    result = run_stage(
        context,
        _stage_request(approval_id=requested.approval.approval_id),
        _work,
        now=_MOMENT,
    )
    assert result.stage.status is StageStatus.COMPLETED
    assert result.operation.state is OperationState.CONFIRMED


def test_the_plan_shows_the_declared_workflow_and_the_task_s_progress(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The plan is the declaration, with this task's place in it."""
    context = _make_context(env, workspace_root, _allow_all())
    plan = read_plan(context)
    assert plan.skill_id == "labcairn.research-report.v1"
    assert [step.stage.value for step in plan.steps][:2] == ["intake", "inventory"]
    assert all(step.status is StageStatus.PENDING for step in plan.steps)

    run_stage(context, _stage_request(), _work, now=_MOMENT)
    after = read_plan(context)
    assert after.steps[0].status is StageStatus.COMPLETED


def test_the_steps_show_what_the_runtime_actually_did(env: StoreEnv, workspace_root: Path) -> None:
    """The steps are the runtime's stages, with the run they belonged to."""
    context = _make_context(env, workspace_root, _allow_all())
    run_stage(context, _stage_request(), _work, now=_MOMENT)
    steps = read_steps(context)
    assert len(steps) == 1
    assert steps[0].stage.name == "intake"
    assert steps[0].attempt == 1


def test_the_sources_of_a_task_are_listed_in_the_binding_order(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The order is the task's own binding, not the ledger's."""
    first = SourceId(new_id())
    second = SourceId(new_id())
    put_source(env.session, _source(str(first), "materials/one.csv"))
    put_source(env.session, _source(str(second), "materials/two.csv"))
    # The ledger holds the source under the id the Task is bound by.
    context = _make_context(
        env,
        workspace_root,
        _allow_all(),
        bound_sources=(second, first),
    )
    listed = list_sources(context)
    assert [view.source.source_id for view in listed] == [str(second), str(first)]


def test_a_source_the_policy_denies_is_dropped_from_the_list(
    env: StoreEnv, workspace_root: Path
) -> None:
    """A listing filters denied entries out, as ADR-0003 §C5 requires.

    Refusing the whole listing would disclose that something is there **and**
    deny work the operator wanted allowed, so the denied source is absent
    rather than the call refused.
    """
    bound = SourceId(new_id())
    put_source(env.session, _source(str(bound), "materials/one.csv"))
    context = _make_context(
        env,
        workspace_root,
        _deny_all(),
        bound_sources=(bound,),
    )
    assert list_sources(context) == ()


def test_asking_for_a_denied_source_by_name_is_refused(env: StoreEnv, workspace_root: Path) -> None:
    """The other half of the rule: a direct request for one thing is refused."""
    source_id = str(SourceId(new_id()))
    put_source(env.session, _source(source_id, "materials/one.csv"))
    context = _make_context(env, workspace_root, _deny_all())
    _assert_refused(
        lambda: inspect_source(context, source_id),
        ApplicationRefusal.PERMISSION_DENIED,
    )


def test_a_source_the_ledger_does_not_hold_is_refused(env: StoreEnv, workspace_root: Path) -> None:
    """A broken binding is loud rather than a shorter list."""
    context = _make_context(
        env,
        workspace_root,
        _allow_all(),
        bound_sources=(SourceId(new_id()),),
    )
    _assert_refused(
        lambda: list_sources(context),
        ApplicationRefusal.SOURCE_NOT_FOUND,
    )


def test_reading_an_artefact_returns_its_record_and_its_bytes(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The layer is the way to the bytes too, so the policy judged them."""
    context = _make_context(env, workspace_root, _allow_all())
    relative = "output/" + str(context.task_id) + "/report.md"
    target = context.workspace.selected_root.joinpath(*relative.split("/"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"# the report\n")

    receipt = ArtifactReceipt(
        receipt_id="artifact-1",
        task_id=str(context.task_id),
        kind=ArtifactKind.REPORT,
        relative_path=relative,
        content_sha256=_HASH,
        size_bytes=len(b"# the report\n"),
        produced_by=ArtifactProducerKind.STAGE,
        producer_id="draft",
        created_at=_MOMENT,
    )
    with context.store.unit(context.task_id) as work:
        work.put_artifact(receipt)

    found = read_artifact(context, "artifact-1")
    assert found.content == b"# the report\n"
    assert found.receipt.receipt_id == "artifact-1"


def test_an_artefact_over_the_bound_is_refused(env: StoreEnv, workspace_root: Path) -> None:
    """The capability's own bound is checked before a byte is read.

    A limit checked afterwards is a report, not a bound, so the size is
    compared with the limit before the file is opened for reading.
    """
    context = _make_context(env, workspace_root, _allow_all())
    relative = "output/" + str(context.task_id) + "/report.md"
    target = context.workspace.selected_root.joinpath(*relative.split("/"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"# a report that is longer than four bytes\n")

    receipt = ArtifactReceipt(
        receipt_id="artifact-1",
        task_id=str(context.task_id),
        kind=ArtifactKind.REPORT,
        relative_path=relative,
        content_sha256=_HASH,
        size_bytes=48,
        produced_by=ArtifactProducerKind.STAGE,
        producer_id="draft",
        created_at=_MOMENT,
    )
    with context.store.unit(context.task_id) as work:
        work.put_artifact(receipt)

    _assert_refused(
        lambda: read_artifact(context, "artifact-1", max_bytes=4),
        ApplicationRefusal.LIMITS_EXCEEDED,
    )


def test_an_artefact_the_store_does_not_hold_is_refused(
    env: StoreEnv, workspace_root: Path
) -> None:
    """Reading one that is not there is a refusal, not an empty artefact."""
    context = _make_context(env, workspace_root, _allow_all())
    _assert_refused(
        lambda: read_artifact(context, "no-such-artefact"),
        ApplicationRefusal.ARTIFACT_NOT_FOUND,
    )


def test_the_artefacts_of_a_task_are_listed(env: StoreEnv, workspace_root: Path) -> None:
    """The artefact list is the store's list, in the store's order."""
    context = _make_context(env, workspace_root, _allow_all())
    relative = "output/" + str(context.task_id) + "/report.md"
    receipt = ArtifactReceipt(
        receipt_id="artifact-1",
        task_id=str(context.task_id),
        kind=ArtifactKind.REPORT,
        relative_path=relative,
        content_sha256=_HASH,
        size_bytes=1,
        produced_by=ArtifactProducerKind.STAGE,
        producer_id="draft",
        created_at=_MOMENT,
    )
    with context.store.unit(context.task_id) as work:
        work.put_artifact(receipt)

    listed = list_artifacts(context)
    assert [view.receipt.receipt_id for view in listed] == ["artifact-1"]


# --------------------------------------------------------------------------- #
# the declared report render
# --------------------------------------------------------------------------- #


def test_rendering_a_report_is_declared_and_not_implemented(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The operation refuses, and says what is missing.

    It is a refusal and not a stub: nothing is written, and the reason names
    the two subtasks that will provide the implementation.
    """
    context = _make_context(env, workspace_root, _allow_all())
    before = count_events(env.session, context.task_id)
    refusal = _assert_refused(
        lambda: render_report(
            context,
            ReportRequest(path="report.md", template_id="default"),
        ),
        ApplicationRefusal.NOT_IMPLEMENTED,
    )
    assert "T00" in refusal.detail
    assert "T01" in refusal.detail
    assert count_events(env.session, context.task_id) == before
    assert not (context.workspace.output_root.path / "report.md").exists()


def test_rendering_a_report_still_asks_the_policy_first(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The capability check runs before the refusal, so a denial is a denial.

    A surface that reached this operation under a policy that denies
    ``report.render`` must be told that, rather than being told that the
    renderer is missing — the two have different remedies.
    """
    context = _make_context(env, workspace_root, _deny_all())
    _assert_refused(
        lambda: render_report(
            context,
            ReportRequest(path="report.md", template_id="default"),
        ),
        ApplicationRefusal.PERMISSION_DENIED,
    )


# --------------------------------------------------------------------------- #
# the event log
# --------------------------------------------------------------------------- #


def _emit(context: ApplicationContext, *occurred_at: datetime) -> None:
    """Append task-level events to the log, stamped as the test says.

    The stamps are the test's own, so a read that ordered by the clock
    would disagree with a read that ordered by the seq, and the difference
    would be visible rather than theoretical.
    """
    with context.store.unit(context.task_id) as work:
        for moment in occurred_at:
            work.emit(EventType.TASK_REVISED, occurred_at=moment)


def test_reading_the_events_is_denied_by_a_deny_policy(env: StoreEnv, workspace_root: Path) -> None:
    """The event log is a read of the task's own record, and it is gated."""
    context = _make_context(env, workspace_root, _deny_all())
    _assert_refused(lambda: read_events(context), ApplicationRefusal.PERMISSION_DENIED)


def test_the_read_is_checked_against_the_tasks_own_area(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The capability and the resource are the task's own, not a nearby one.

    The read is of the task's own record, so it goes through the same check
    ``read_task_state`` goes through: ``fs.read`` on the task's area. A rule
    scoped to another capability must not authorise it, and a rule aimed at
    another key must not cover it — a read of the event log is a read of the
    area the log belongs to, and of nothing else.

    Each policy below allows one thing and nothing else, so the default-deny
    is what refuses everything the rule did not name.
    """
    only_read = PermissionPolicy.from_rules(
        [Rule(effect=Permission.ALLOW, pattern="**", capabilities=frozenset({"fs.read"}))]
    )
    context = _make_context(env, workspace_root, only_read)
    assert read_events(context).events

    only_list = PermissionPolicy.from_rules(
        [Rule(effect=Permission.ALLOW, pattern="**", capabilities=frozenset({"fs.list"}))]
    )
    context = _make_context(env, workspace_root, only_list)
    _assert_refused(lambda: read_events(context), ApplicationRefusal.PERMISSION_DENIED)

    the_area = PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="output")])
    context = _make_context(env, workspace_root, the_area)
    assert read_events(context).events

    another_area = PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="materials")])
    context = _make_context(env, workspace_root, another_area)
    _assert_refused(lambda: read_events(context), ApplicationRefusal.PERMISSION_DENIED)


def test_reading_the_events_writes_nothing(env: StoreEnv, workspace_root: Path) -> None:
    """A read is a read: the log is the same size afterwards."""
    context = _make_context(env, workspace_root, _allow_all())
    before = count_events(env.session, context.task_id)
    read_events(context)
    assert count_events(env.session, context.task_id) == before


def test_the_page_carries_the_stores_events_by_value_and_by_type(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The port's contract is a layer model, and the events in it are the store's.

    Two properties in one test, because they are one decision: the layer
    returns a model of its own, and that model carries **the store's events**
    -- by value and by type -- rather than a re-spelling of them. An event is
    a fact about what happened, and a second shape for it would be a second
    thing to keep true.

    **By value and by type, and not by identity.** The store's readers read
    the log afresh on every call, so the events a caller holds and the ones
    the layer holds are never the same objects even when they are the same
    events. Identity is not a property the layer could satisfy, so it is not
    the property; what would be wrong is a layer that re-shaped the event
    into a model of its own, and that is what the type assertion rules out.
    """
    context = _make_context(env, workspace_root, _allow_all())
    page = read_events(context)
    assert isinstance(page, Result)
    assert isinstance(page, EventPage)
    assert all(isinstance(event, Event) for event in page.events)
    assert page.events == events_after(env.session, context.task_id)


def test_the_events_after_the_cursor_are_the_ones_the_client_has_not_seen(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The cursor is exclusive: the event the client stopped after is not sent again."""
    context = _make_context(env, workspace_root, _allow_all())
    _emit(context, _MOMENT, _MOMENT)
    everything = read_events(context)
    assert [event.seq for event in everything.events] == [1, 2, 3]

    after_the_first = read_events(context, after_seq=everything.events[0].seq)
    assert [event.seq for event in after_the_first.events] == [2, 3]


def test_the_events_come_back_in_seq_order_and_not_in_wall_clock_order(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The log's order is the seq, and the timestamp is not a sort key.

    Wall-clock is not monotonic: a resumed process can emit a timestamp
    earlier than one already recorded. A read that ordered by the clock
    would hand the client the same events in a different order each time,
    and a client that replays them would see the task's history change
    shape.
    """
    context = _make_context(env, workspace_root, _allow_all())
    _emit(context, _MOMENT + timedelta(seconds=10), _MOMENT)
    page = read_events(context)
    assert [event.seq for event in page.events] == [1, 2, 3]
    # The two emitted events are stamped in the opposite order to their seqs,
    # so a clock-ordered read would have returned them the other way round.
    assert [event.occurred_at for event in page.events[1:]] == [
        _MOMENT + timedelta(seconds=10),
        _MOMENT,
    ]


def test_the_limit_bounds_the_page(env: StoreEnv, workspace_root: Path) -> None:
    """A limit is a page length, and it changes what comes back."""
    context = _make_context(env, workspace_root, _allow_all())
    _emit(context, _MOMENT, _MOMENT, _MOMENT)
    assert [event.seq for event in read_events(context, limit=2).events] == [1, 2]
    assert len(read_events(context, limit=4).events) == 4
    assert len(read_events(context).events) == 4


def test_a_full_page_leaves_the_cursor_where_the_page_stopped(
    env: StoreEnv, workspace_root: Path
) -> None:
    """A client that resumes from the page's cursor gets the next events, and only those."""
    context = _make_context(env, workspace_root, _allow_all())
    _emit(context, _MOMENT, _MOMENT)
    first = read_events(context, limit=2)
    assert first.next_after_seq == 2
    assert first.last_seq == 3
    assert not first.caught_up

    second = read_events(context, after_seq=first.next_after_seq)
    assert [event.seq for event in second.events] == [3]
    assert second.next_after_seq == 3
    assert second.caught_up


def test_an_empty_page_resumes_from_the_tasks_counter(env: StoreEnv, workspace_root: Path) -> None:
    """A cursor past the end does not skip the events that are yet to come.

    The cursor the page hands back is the task's own counter, not the one
    that was asked for: a cursor beyond the counter would skip every event
    between the two, and those are the events the client has not seen.
    """
    context = _make_context(env, workspace_root, _allow_all())
    page = read_events(context, after_seq=999)
    assert page.events == ()
    assert page.next_after_seq == page.last_seq


def test_a_page_length_that_is_not_a_page_is_refused(env: StoreEnv, workspace_root: Path) -> None:
    """A limit of none would never advance the cursor, and a limit of -1 is no limit.

    SQLite reads ``LIMIT -1`` as unbounded, so a limit that was passed on
    unchecked would hand the caller the whole log under a name that says
    otherwise.
    """
    context = _make_context(env, workspace_root, _allow_all())
    _assert_refused(
        lambda: read_events(context, limit=MIN_EVENT_LIMIT - 1),
        ApplicationRefusal.ARGUMENTS_INVALID,
    )
    _assert_refused(
        lambda: read_events(context, limit=-1),
        ApplicationRefusal.ARGUMENTS_INVALID,
    )
    _assert_refused(
        lambda: read_events(context, limit=MAX_EVENT_LIMIT + 1),
        ApplicationRefusal.ARGUMENTS_INVALID,
    )


def test_a_cursor_below_the_log_is_refused(env: StoreEnv, workspace_root: Path) -> None:
    """Every event's seq is one or more, so a cursor below zero names the whole log."""
    context = _make_context(env, workspace_root, _allow_all())
    _assert_refused(
        lambda: read_events(context, after_seq=-1),
        ApplicationRefusal.ARGUMENTS_INVALID,
    )


def test_the_page_bounds_are_the_runtime_requests_own(env: StoreEnv, workspace_root: Path) -> None:
    """The layer and the runtime's own event stream request cannot disagree.

    The layer's read is that request applied to the task the context is
    about, so a page that one of them serves and the other refuses is a
    request the API cannot build.
    """
    context = _make_context(env, workspace_root, _allow_all())
    request = EventStreamRequest(task_id=context.task_id, after_seq=0, limit=MAX_EVENT_LIMIT)
    assert request.limit == MAX_EVENT_LIMIT
    with pytest.raises(ValidationError):
        EventStreamRequest(task_id=context.task_id, after_seq=0, limit=MAX_EVENT_LIMIT + 1)
    with pytest.raises(ValidationError):
        EventStreamRequest(task_id=context.task_id, after_seq=0, limit=MIN_EVENT_LIMIT - 1)
    with pytest.raises(ValidationError):
        EventStreamRequest(task_id=context.task_id, after_seq=-1)

    assert read_events(context, limit=MAX_EVENT_LIMIT).events
    _assert_refused(
        lambda: read_events(context, limit=MAX_EVENT_LIMIT + 1),
        ApplicationRefusal.ARGUMENTS_INVALID,
    )


def test_reading_the_events_of_a_task_the_store_does_not_hold_is_refused(
    env: StoreEnv, workspace_root: Path
) -> None:
    """A task that does not exist is not a task with no events.

    The store states that rule for every other task-scoped read it owns, and
    the layer keeps it: a client that cannot tell the two apart reports
    "no events" for a task id it mistyped.
    """
    missing = ApplicationContext(
        workspace=Workspace.bind(workspace_root, task_id=TaskId(new_id())),
        store=env.store(),
        policy=_allow_all(),
        ledger=ApprovalLedger(),
    )
    _assert_refused(lambda: read_events(missing), ApplicationRefusal.TASK_NOT_FOUND)


def test_the_page_is_serialisable_as_data(env: StoreEnv, workspace_root: Path) -> None:
    """The CLI's ``--json`` and the API's body are the same model."""
    context = _make_context(env, workspace_root, _allow_all())
    payload = read_events(context).model_dump_json()
    assert '"events"' in payload
    assert '"next_after_seq"' in payload
    assert '"last_seq"' in payload


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _use() -> ApprovalUse:
    """What an approval is spent on, matching the stage request."""
    return ApprovalUse(
        capability=CapabilityId.ANALYSIS_RUN,
        arguments={"operator_id": "mean", "parameters": {}},
        root_id="source:0",
        resource_key="one.csv",
    )
