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
import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import text as sql_text
from test_analysis_report_render import (
    _read_docx,
    _read_html,
    _read_markdown,
    _read_pdf,
    _the_snapshot_a_form_states,
)
from test_store_support import StoreEnv, make_source_id
from test_store_support import env as _shared_env

from labcairn.analysis.manifest import (
    FileRef,
    RenderEnvironment,
    ReproducibilityManifest,
    build_figure_receipt,
    canonical_digest,
    write_manifest,
)
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
from labcairn.application import records as records_layer
from labcairn.application import reports as report_layer
from labcairn.application.events import MAX_EVENT_LIMIT, MIN_EVENT_LIMIT
from labcairn.application.reports import ReportRequest
from labcairn.core.ids import ApprovalId, RunId, SourceId, TaskId, new_id
from labcairn.db.materials import ExtractedTextRow, put_source, put_source_texts
from labcairn.db.repository import count_events, events_after, list_operations
from labcairn.evidence.record import EvidenceRecord
from labcairn.evidence.states import EvidenceCreator, EvidenceKind, VerificationStatus
from labcairn.evidence.store import append_record
from labcairn.material.addressing import render_locator_key
from labcairn.reports.receipt import (
    ArtifactKind,
    ArtifactProducerKind,
    ArtifactReceipt,
    DerivationRef,
    DerivationTargetKind,
)
from labcairn.runtime.event import Event, EventStreamRequest, EventType
from labcairn.runtime.lifecycle import StageStatus, TaskGoal
from labcairn.runtime.operation import ApprovalState, Operation, OperationState
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import CapabilityId
from labcairn.security.policy import Permission, PermissionPolicy, Rule
from labcairn.sources.locators import ComputationLocator, TextLocator
from labcairn.sources.source import Source, SourceKind, SourceReadability
from labcairn.workspace.roots import Workspace

# pytest resolves a fixture by the parameter name in a test's signature, so the
# shared `env` fixture must be bound under that name here.
env = _shared_env

_MOMENT = datetime(2026, 1, 1, tzinfo=UTC)
_HASH = "b" * 64


# --------------------------------------------------------------------------- #
# the death a test stages
# --------------------------------------------------------------------------- #


class _TheRunDiedError(Exception):
    """The run stopped between the intent and the attempt.

    The layer turns a failure of the **work** into a refusal, and it does not
    handle a failure of its own bookkeeping — so one of those leaves the store
    exactly as a killed process leaves it, which is the state the operation
    reuse after a crash is about.
    """


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
    run_id: RunId | None = None,
) -> StageRequest:
    """A stage run over a file in the source root."""
    return StageRequest(
        stage_name=stage_name,
        capability=capability,
        arguments=arguments if arguments is not None else {"operator_id": "mean", "parameters": {}},
        root_id=root_id,
        resource_key=resource_key,
        approval_id=approval_id,
        run_id=run_id,
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
        "labcairn.application.material_ingestion",
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
    source_id = str(make_source_id("materials/one.csv"))
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


def test_a_run_that_follows_an_approval_reuses_the_operation_it_was_bound_to(
    env: StoreEnv, workspace_root: Path
) -> None:
    """One piece of work, one operation, whatever the log says about it.

    The approval was asked for against an operation, and the stage that runs
    once the answer arrives is that operation and not a new one. A second row
    would put two operations in the audit log for one piece of work, and the
    log is what a reader takes the history from.

    The count is the property, and the identity is what makes it the *same*
    operation: a run that planned a fresh one would also leave a confirmed
    operation behind, so the stage would still complete and the operation
    would still be confirmed — of the wrong operation.
    """
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

    operations = list_operations(env.session, context.task_id)
    assert len(operations) == 1, (
        "the store holds "
        f"{len(operations)} operations for one piece of work: "
        f"{[str(operation.operation_id) for operation in operations]}"
    )
    assert operations[0].operation_id == requested.approval.operation_id
    assert result.operation.operation_id == requested.approval.operation_id


def test_a_run_that_follows_an_approval_reuses_that_approvals_operation_and_not_another(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The operation the approval names, and not the one that happens to be first.

    A task can be waiting for an answer about more than one thing, and the
    store holds an operation for each of them. The stage that follows an
    approval must pick out the operation **that approval** was asked for: the
    operations are held in the order they were planned, and the one planned
    first is not the one this consent was given for.
    """
    ledger = ApprovalLedger()
    context = _make_context(env, workspace_root, _ask_all(), ledger=ledger)
    # Another question was put to the operator first, about another file, and
    # it is still unanswered — so its operation is the older of the two.
    request_approval(
        context,
        ApprovalRequest(use=_use("two.csv"), expires_at=_MOMENT.replace(hour=1)),
        now=_MOMENT,
    )
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

    assert result.operation.operation_id == requested.approval.operation_id
    operations = list_operations(env.session, context.task_id)
    assert len(operations) == 2, (
        "the run planned a third operation for work that was already planned: "
        f"{[str(operation.operation_id) for operation in operations]}"
    )


def test_a_run_that_follows_a_crash_reuses_the_operation_that_was_authorised(
    env: StoreEnv, workspace_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The operation that was authorised and never attempted is the one that runs.

    **The intent is written ahead of the attempt**, so a run that dies between
    the two leaves an operation ``AUTHORIZED`` and nothing attempted. The run
    that follows must pick that operation up and attempt it, rather than plan
    a second operation for the same work: two operations for one piece of work
    would make the audit log say it happened twice.

    The death is staged where the product's own ordering puts it — between the
    intent and the attempt — so what the resumed run finds is a state the
    product can reach on its own, and not one this test wrote by hand.
    """
    context = _make_context(env, workspace_root, _allow_all())
    run_id = RunId(new_id())
    move = records_layer.move_operation
    died = False

    def _die_before_the_attempt(
        ctx: ApplicationContext,
        operation: Operation,
        *,
        event: EventType,
        to_state: OperationState,
        now: datetime,
    ) -> Operation:
        nonlocal died
        if to_state is OperationState.ATTEMPTING and not died:
            died = True
            raise _TheRunDiedError("the run died between the intent and the attempt")
        return move(ctx, operation, event=event, to_state=to_state, now=now)

    monkeypatch.setattr(records_layer, "move_operation", _die_before_the_attempt)

    with pytest.raises(_TheRunDiedError):
        run_stage(context, _stage_request(run_id=run_id), _work, now=_MOMENT)

    # What the death left behind: one operation, authorised, never attempted.
    planned = list_operations(env.session, context.task_id)
    assert len(planned) == 1
    assert planned[0].state is OperationState.AUTHORIZED

    result = run_stage(context, _stage_request(run_id=run_id), _work, now=_MOMENT)

    operations = list_operations(env.session, context.task_id)
    assert len(operations) == 1, (
        "the store holds "
        f"{len(operations)} operations for one piece of work: "
        f"{[str(operation.operation_id) for operation in operations]}"
    )
    assert result.operation.operation_id == planned[0].operation_id
    assert result.operation.state is OperationState.CONFIRMED


def test_a_stage_that_runs_twice_plans_two_operations(env: StoreEnv, workspace_root: Path) -> None:
    """The work ran twice, so the log says it ran twice.

    An operation that is already ``CONFIRMED`` is not one a later run may
    pick up: the stage does the work again, and an operation that carried
    both attempts would leave the audit log saying the work happened once when
    it happened twice. The second run plans its own operation, and the store
    holds one per attempt.
    """
    context = _make_context(env, workspace_root, _allow_all())
    run_id = RunId(new_id())
    first = run_stage(context, _stage_request(run_id=run_id), _work, now=_MOMENT)
    second = run_stage(context, _stage_request(run_id=run_id), _work, now=_MOMENT)

    operations = list_operations(env.session, context.task_id)
    assert len(operations) == 2, (
        f"the store holds {len(operations)} operations for two attempts: "
        f"{[str(operation.operation_id) for operation in operations]}"
    )
    assert second.operation.operation_id != first.operation.operation_id


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
    first = make_source_id("materials/one.csv")
    second = make_source_id("materials/two.csv")
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
    bound = make_source_id("materials/one.csv")
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
    source_id = str(make_source_id("materials/one.csv"))
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
        bound_sources=(make_source_id("materials/absent.csv"),),
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
# the report render
# --------------------------------------------------------------------------- #


#: The material the report is about, and the address it is read at.
_MATERIAL_TEXT = "The yield across the five runs was 4.253%.\n"
_MATERIAL_HASH = hashlib.sha256(_MATERIAL_TEXT.encode("utf-8")).hexdigest()

#: The number the ledger holds, and the unit it declares.
_LEDGER_VALUE = 4.253
_LEDGER_UNIT = "%"

#: The figure's bytes, on disk.
_FIGURE_BYTES = b"<svg xmlns='http://www.w3.org/2000/svg'><rect width='10' height='10'/></svg>"

#: The table's bytes, on disk.
_TABLE_BYTES = b"run,yield\n1,4.253\n"

#: The caption the recipe carries: the author's words about what is plotted.
#:
#: Without a full stop, because the Markdown writer escapes one and the test
#: below reads the caption out of the rendered form.
_CAPTION = "The mean of the yield column over the five runs"

#: The interpretation the recipe carries: what the figure means.
_INTERPRETATION = "The second run reads lower than the first"

#: The marker the renderers put on an interpretation.
_INTERPRETATION_MARKER = "[interpretation not machine-verified]"


def _recipe_text(interpretation: str | None) -> str:
    """The chart recipe, as it is written on disk.

    A recipe is a person-written document, so it is written here as the JSON a
    person would write rather than as a model dump. The one field that varies
    is the interpretation, because the whole of ADR-0004's A10 for a figure is
    that it is a separate field from the caption and that it is optional.
    """
    return json.dumps(
        {
            "data": {
                "operator": "labcairn.analysis.mean@1.0.0",
                "parameters": {},
                "selection": {
                    "source": "materials/one.txt",
                    "columns": ["group", "value"],
                    "rows": {"start": 1, "end": 5},
                    "missing": "exclude",
                },
            },
            "encoding": {
                "mark": "bar",
                "x": "group",
                "y": "value",
                "title": "Mean yield per run",
                "x_label": "run",
                "y_label": "mean yield",
                "caption": _CAPTION,
                "interpretation": interpretation,
            },
            "output": {"format": "svg", "dpi": 200},
        },
        indent=2,
        sort_keys=True,
    )


@dataclass(frozen=True)
class _ReportWorld:
    """A task with the material, the records and the artefacts a report is made of.

    Everything in it is real: the material is a file, the citation resolves at
    an address that holds text, the record is in the ledger, and the figure's
    chain runs file, result, manifest, figure. A stub would make every
    assertion below a statement about the stub.
    """

    context: ApplicationContext
    material_hash: str
    recipe_path: str
    figure_receipt_id: str
    manifest_receipt_id: str


def _seed_a_task_with_a_report(
    env: StoreEnv,
    workspace_root: Path,
    *,
    interpretation: str | None = _INTERPRETATION,
    resolve_citation: bool = True,
    record_anchors: tuple[str, ...] = ("anc-1",),
    omit_the_manifest_from_the_ledger: bool = False,
) -> _ReportWorld:
    """Seed a task with everything a report is made of.

    The keyword arguments are the ways the world can be broken, and each one
    breaks it in a way the layer has to notice: a citation that resolves to
    nothing, a record that cannot be cited, a manifest the ledger does not
    hold, a recipe with no interpretation.
    """
    # The source id the ingestion path mints for this material's path, so the
    # id the test binds is one a real ingestion would have produced. The
    # ingestion path derives the id from the *path* and not from the bytes,
    # so this is the id for this material whatever the bytes are — and the
    # bytes are this test's own, because the source row and the text rows
    # below are written by hand: the test needs its own content hash, and it
    # needs to be able to leave the text rows out.
    source_id = make_source_id("materials/one.txt")
    context = _make_context(
        env,
        workspace_root,
        _allow_all(),
        bound_sources=(source_id,),
    )

    # The material: a file in the source root, and the source it was read as.
    # Written as bytes, because a text write would translate the line ending
    # and the file's hash would not be the hash the ledger records.
    material = workspace_root / "materials" / "one.txt"
    material.write_bytes(_MATERIAL_TEXT.encode("utf-8"))
    put_source(
        env.session,
        Source(
            source_id=source_id,
            kind=SourceKind.TEXT,
            display_name="one.txt",
            relative_path="materials/one.txt",
            content_sha256=_MATERIAL_HASH,
            size_bytes=len(_MATERIAL_TEXT.encode("utf-8")),
            readability=SourceReadability.READABLE,
            ingested_at=_MOMENT,
        ),
    )
    env.session.flush()

    connection = env.session.connection()
    locator = TextLocator(line=1)
    locator_key = render_locator_key(locator)
    if resolve_citation:
        body = _MATERIAL_TEXT.strip()
        put_source_texts(
            env.session,
            source_content_sha256=_MATERIAL_HASH,
            extraction_version="v1",
            rows=[
                ExtractedTextRow(
                    locator_kind=locator.locator_kind.value,
                    locator_key=locator_key,
                    text=body,
                    text_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
                    created_at=_MOMENT,
                    line_start=1,
                    line_end=1,
                )
            ],
        )
        env.session.flush()
    connection.execute(
        sql_text(
            "INSERT INTO source_anchors (anchor_id, source_id, kind, locator_key,"
            " bound_source_sha256, excerpt_sha256, created_at)"
            " VALUES ('anc-1',:sid,'quotation',:key,:bound,NULL,:now)"
        ),
        {"sid": source_id, "key": locator_key, "bound": _MATERIAL_HASH, "now": _MOMENT},
    )

    # The record the report states: a number, a unit, and where it was read.
    span = str(_LEDGER_VALUE)
    append_record(
        connection,
        EvidenceRecord(
            evidence_id="ev-1",
            task_id=str(context.task_id),
            kind=EvidenceKind.NUMERIC,
            text=None,
            value=_LEDGER_VALUE,
            unit=_LEDGER_UNIT,
            anchor_ids=record_anchors,
            extracted_span=span,
            extracted_span_sha256=hashlib.sha256(span.encode("utf-8")).hexdigest(),
            status=VerificationStatus.EXTRACTED,
            created_by=EvidenceCreator.RULE,
            created_by_id="seed",
            source_content_hash=_MATERIAL_HASH,
            created_at=_MOMENT,
        ),
    )

    # The recipe: the author's words about the figure.
    recipe_path = "recipes/chart.json"
    recipe_file = workspace_root / "recipes" / "chart.json"
    recipe_file.parent.mkdir(parents=True, exist_ok=True)
    recipe_text = _recipe_text(interpretation)
    recipe_file.write_bytes(recipe_text.encode("utf-8"))

    # The manifest: the figure's own derivation, and the file that holds it.
    output: dict[str, Any] = {"mean": _LEDGER_VALUE, "n_used": 5}
    manifest = ReproducibilityManifest(
        input_file=FileRef(relative_path="materials/one.txt", content_sha256=_MATERIAL_HASH),
        operator="labcairn.analysis.mean@1.0.0",
        locator=ComputationLocator(
            operator_id="labcairn.analysis.mean",
            operator_version="1.0.0",
            parameters={
                "selection": {
                    "source_id": source_id,
                    "content_sha256": _MATERIAL_HASH,
                    "columns": ["group", "value"],
                    "rows": {"kind": "range", "start": 1, "end": 5},
                    "missing": "exclude",
                }
            },
            input_hashes=(_MATERIAL_HASH,),
        ),
        recipe=FileRef(
            relative_path=recipe_path,
            content_sha256=hashlib.sha256(recipe_text.encode("utf-8")).hexdigest(),
        ),
        output=output,
        output_sha256=canonical_digest(output),
        environment=RenderEnvironment(
            matplotlib_version="3.11.2",
            svg_hashsalt="labcairn",
            font_families=("sans-serif",),
            platform="TestOS-1.0",
        ),
    )
    manifest_receipt = write_manifest(
        context.workspace,
        key="figures/manifest.json",
        manifest=manifest,
        receipt_id="manifest-1",
        created_at=_MOMENT,
    )

    # The figure: the bytes, and the receipt whose chain runs back to the
    # manifest and through it to the material.
    figure_relative = f"output/{context.task_id}/figures/fig-1.svg"
    figure_file = context.workspace.selected_root / figure_relative
    figure_file.parent.mkdir(parents=True, exist_ok=True)
    figure_file.write_bytes(_FIGURE_BYTES)
    figure_receipt = build_figure_receipt(
        manifest_receipt=manifest_receipt,
        relative_path=figure_relative,
        content_sha256=hashlib.sha256(_FIGURE_BYTES).hexdigest(),
        size_bytes=len(_FIGURE_BYTES),
        receipt_id="figure-1",
        created_at=_MOMENT,
    )

    # The table: the bytes, and the upstream that names the material.
    table_relative = f"output/{context.task_id}/tables/tab-1.csv"
    table_file = context.workspace.selected_root / table_relative
    table_file.parent.mkdir(parents=True, exist_ok=True)
    table_file.write_bytes(_TABLE_BYTES)
    table_receipt = ArtifactReceipt(
        receipt_id="table-1",
        task_id=str(context.task_id),
        kind=ArtifactKind.TABLE,
        relative_path=table_relative,
        content_sha256=hashlib.sha256(_TABLE_BYTES).hexdigest(),
        size_bytes=len(_TABLE_BYTES),
        produced_by=ArtifactProducerKind.ANALYSIS_OPERATOR,
        producer_id="labcairn.analysis.mean@1.0.0",
        derived_from=(
            DerivationRef(
                target_kind=DerivationTargetKind.MATERIAL_FILE,
                target_id="materials/one.txt",
                content_sha256=_MATERIAL_HASH,
            ),
        ),
        media_type="text/csv",
        created_at=_MOMENT,
    )

    with context.store.unit(context.task_id) as work:
        if not omit_the_manifest_from_the_ledger:
            work.put_artifact(manifest_receipt)
        work.put_artifact(figure_receipt)
        work.put_artifact(table_receipt)

    return _ReportWorld(
        context=context,
        material_hash=_MATERIAL_HASH,
        recipe_path=recipe_path,
        figure_receipt_id=figure_receipt.receipt_id,
        manifest_receipt_id=manifest_receipt.receipt_id,
    )


@pytest.fixture()
def report_world(env: StoreEnv, workspace_root: Path) -> _ReportWorld:
    """A task with the material, the records and the artefacts a report is made of."""
    return _seed_a_task_with_a_report(env, workspace_root)


def _report_dir(context: ApplicationContext) -> Path:
    """Where the revisions of this task's report live."""
    return context.workspace.output_root.path / "report"


def test_rendering_a_report_writes_a_revision_and_records_it(
    env: StoreEnv, report_world: _ReportWorld
) -> None:
    """The report is written as a revision, and the revision is in the ledger.

    A report that was rendered and not recorded does not exist, so this is
    one test and not two: the six files on disk and the six receipts in the
    ledger are the same fact.
    """
    context = report_world.context
    rendered = render_report(
        context,
        ReportRequest(path="report", template_id="default"),
        now=_MOMENT,
    )

    revision = _report_dir(context) / "v1"
    for name in ("report.json", "report-manifest.json", "report.md", "report.html"):
        assert (revision / name).is_file(), f"{name} was not written"
    assert (revision / "report.docx").read_bytes()[:2] == b"PK"
    assert (revision / "report.pdf").read_bytes()[:4] == b"%PDF"

    recorded = {view.receipt.receipt_id for view in list_artifacts(context)}
    assert rendered.receipt.receipt_id in recorded
    assert len(recorded) == 9  # three seeded artefacts and the revision's six
    assert rendered.receipt.revision == 1
    assert rendered.resource_key == "report"

    kinds = [event.type for event in events_after(env.session, context.task_id)]
    assert EventType.ARTIFACT_RECORDED in kinds


def test_rendering_a_report_is_denied_by_a_deny_policy(env: StoreEnv, workspace_root: Path) -> None:
    """The capability check runs before anything is read or written.

    A surface that reached this operation under a policy that denies
    ``report.render`` must be told that, and nothing may be written.
    """
    world = _seed_a_task_with_a_report(env, workspace_root)
    context = world.context
    context = ApplicationContext(
        workspace=context.workspace,
        store=context.store,
        policy=_deny_all(),
        ledger=context.ledger,
    )
    before = count_events(env.session, context.task_id)
    _assert_refused(
        lambda: render_report(
            context,
            ReportRequest(path="report", template_id="default"),
            now=_MOMENT,
        ),
        ApplicationRefusal.PERMISSION_DENIED,
    )
    assert count_events(env.session, context.task_id) == before
    assert not _report_dir(context).exists()


def test_a_policy_that_asks_about_the_render_refuses_it(
    env: StoreEnv, workspace_root: Path
) -> None:
    """A render the policy asked about needs consent, and cannot have it here.

    The request carries no approval, so a policy that asks has no way to be
    answered; refusing is the honest answer and writing anyway would be a
    report nobody agreed to.
    """
    world = _seed_a_task_with_a_report(env, workspace_root)
    context = world.context
    context = ApplicationContext(
        workspace=context.workspace,
        store=context.store,
        policy=_ask_all(),
        ledger=context.ledger,
    )
    _assert_refused(
        lambda: render_report(
            context,
            ReportRequest(path="report", template_id="default"),
            now=_MOMENT,
        ),
        ApplicationRefusal.POLICY_ASKED,
    )
    assert not _report_dir(context).exists()


def test_an_unknown_template_is_refused(report_world: _ReportWorld) -> None:
    """There is one template, and a name that is not it is refused.

    A parameter that is accepted and ignored is a parameter that lies: a
    caller that was told "slate" had been rendered would have no way to know
    it was not.
    """
    context = report_world.context
    _assert_refused(
        lambda: render_report(
            context,
            ReportRequest(path="report", template_id="slate"),
            now=_MOMENT,
        ),
        ApplicationRefusal.ARGUMENTS_INVALID,
    )
    assert not _report_dir(context).exists()


def test_a_path_that_is_not_the_report_is_refused(report_world: _ReportWorld) -> None:
    """The revisions are written under one key, so a report named otherwise has nowhere to go.

    The request's path is the base the revision paths hang from, and the
    revision machinery writes under ``report`` — so ``report.md`` names
    somewhere the report does not go.
    """
    context = report_world.context
    refusal = _assert_refused(
        lambda: render_report(
            context,
            ReportRequest(path="report.md", template_id="default"),
            now=_MOMENT,
        ),
        ApplicationRefusal.PATH_REFUSED,
    )
    assert "report" in refusal.detail
    assert not _report_dir(context).exists()
    assert not (context.workspace.output_root.path / "report.md").exists()


def test_a_path_that_escapes_the_output_area_is_refused(report_world: _ReportWorld) -> None:
    """A caller cannot use the path to write outside the task's own area.

    The path is admitted into the output area before anything else happens,
    and a path that walks out of it is refused there — it is not a path the
    policy can be asked about, because the policy has no way to judge it.
    """
    context = report_world.context
    _assert_refused(
        lambda: render_report(
            context,
            ReportRequest(path="../../materials/one.txt", template_id="default"),
            now=_MOMENT,
        ),
        ApplicationRefusal.PATH_REFUSED,
    )
    assert not _report_dir(context).exists()


def test_a_report_the_checks_refuse_is_not_written(env: StoreEnv, workspace_root: Path) -> None:
    """A citation that resolves to nothing is a report that is not written.

    The checks run against the ledger and the material, not against the
    document's own copy of either. This is the test that holds the checks in
    place: with them skipped, the report below would be written.
    """
    world = _seed_a_task_with_a_report(env, workspace_root, resolve_citation=False)
    context = world.context
    refusal = _assert_refused(
        lambda: render_report(
            context,
            ReportRequest(path="report", template_id="default"),
            now=_MOMENT,
        ),
        ApplicationRefusal.REPORT_CONTENT_REFUSED,
    )
    assert "links" in refusal.detail
    assert not _report_dir(context).exists()


def test_a_refused_report_reaches_the_surface_as_a_content_refusal(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The reason that arrives is the report's, and not a stage's.

    The two fields a surface renders are the refusal's own payload — the
    API's error body and the CLI's JSON are the same two fields — so the
    reason that arrives is what this test reads. A report whose content was
    refused says so, and it does not say that a stage failed: no stage ran.
    """
    world = _seed_a_task_with_a_report(env, workspace_root, resolve_citation=False)
    context = world.context
    refusal = _assert_refused(
        lambda: render_report(
            context,
            ReportRequest(path="report", template_id="default"),
            now=_MOMENT,
        ),
        ApplicationRefusal.REPORT_CONTENT_REFUSED,
    )
    payload = refusal.to_payload()
    assert set(payload) == {"reason", "message"}
    assert payload["reason"] == "report_content_refused"
    assert "links check refused the report" in payload["message"]


def test_a_report_the_checks_refuse_is_not_even_rendered(
    monkeypatch: pytest.MonkeyPatch, env: StoreEnv, workspace_root: Path
) -> None:
    """The refusal happens before the first byte of any form.

    The four forms are bytes, and the layer runs the checks over the document
    **before** it draws it. That is the layer's own reason for running them as
    well as handing them to the revision machinery: a report the checks
    refuse is not rendered at all, rather than rendered and then refused.
    """
    world = _seed_a_task_with_a_report(env, workspace_root, resolve_citation=False)
    context = world.context

    drawn: list[str] = []

    def _spy(name: str) -> Callable[[object], bytes]:
        def _draw(document: object) -> bytes:
            drawn.append(name)
            return b""

        return _draw

    for name in ("render_markdown", "render_html", "render_docx", "render_pdf"):
        monkeypatch.setattr(report_layer, name, _spy(name))

    _assert_refused(
        lambda: render_report(
            context,
            ReportRequest(path="report", template_id="default"),
            now=_MOMENT,
        ),
        ApplicationRefusal.REPORT_CONTENT_REFUSED,
    )
    assert drawn == []
    assert not _report_dir(context).exists()


def test_a_report_that_cannot_be_built_is_not_written(env: StoreEnv, workspace_root: Path) -> None:
    """A record that may be stated but cannot be cited is not reported around.

    The builder refuses rather than producing a document with a hole in it:
    dropping the record would leave a verified finding out of a report whose
    snapshot claims to be a view of the records.
    """
    world = _seed_a_task_with_a_report(env, workspace_root, record_anchors=("anc-9",))
    context = world.context
    _assert_refused(
        lambda: render_report(
            context,
            ReportRequest(path="report", template_id="default"),
            now=_MOMENT,
        ),
        ApplicationRefusal.REPORT_CONTENT_REFUSED,
    )
    assert not _report_dir(context).exists()


def test_a_figure_whose_manifest_the_ledger_does_not_hold_is_refused(
    env: StoreEnv, workspace_root: Path
) -> None:
    """A figure whose derivation the ledger cannot name is not carried.

    The manifest artefact is found through the figure's own chain, so a
    ledger that has lost it leaves the figure with no derivation at all.
    """
    world = _seed_a_task_with_a_report(env, workspace_root, omit_the_manifest_from_the_ledger=True)
    context = world.context
    _assert_refused(
        lambda: render_report(
            context,
            ReportRequest(path="report", template_id="default"),
            now=_MOMENT,
        ),
        ApplicationRefusal.ARTIFACT_NOT_FOUND,
    )
    assert not _report_dir(context).exists()


def test_a_figure_whose_recipe_has_changed_is_refused(
    report_world: _ReportWorld, workspace_root: Path
) -> None:
    """A recipe that has changed under the manifest is not the figure's recipe.

    The caption would not be the caption the figure was drawn from, and a
    report that carried it would be reporting something nobody wrote.
    """
    context = report_world.context
    recipe = workspace_root / "recipes" / "chart.json"
    recipe.write_text(_recipe_text("A different reading of the figure."), encoding="utf-8")
    _assert_refused(
        lambda: render_report(
            context,
            ReportRequest(path="report", template_id="default"),
            now=_MOMENT,
        ),
        ApplicationRefusal.REPORT_CONTENT_REFUSED,
    )
    assert not _report_dir(context).exists()


def test_a_figure_with_no_interpretation_contributes_no_interpretation_block(
    env: StoreEnv, workspace_root: Path
) -> None:
    """An absent interpretation and an empty one are different facts.

    The recipe's field is optional, and a recipe with none carries no block
    at all: a marker on nothing would be a claim about a reading nobody made.
    """
    world = _seed_a_task_with_a_report(env, workspace_root, interpretation=None)
    context = world.context
    render_report(
        context,
        ReportRequest(path="report", template_id="default"),
        now=_MOMENT,
    )
    markdown = (_report_dir(context) / "v1" / "report.md").read_text(encoding="utf-8")
    assert _INTERPRETATION_MARKER not in markdown
    assert _CAPTION in markdown


def test_the_four_forms_are_drawn_from_the_canonical_document(
    report_world: _ReportWorld,
) -> None:
    """The four forms and the canonical document say the same thing.

    The revision machinery takes the four forms as bytes, so it cannot tell
    whether they belong to the document beside them. This test holds that:
    the forms carry the document's own moment, the document's own caption and
    the document's own records, and a form drawn from any other document
    would not.

    **All four forms are compared, and each is read by the reader its own
    test reads it with.** A comparison that stopped at the Markdown and the
    HTML would leave the DOCX and the PDF unwatched, and the two lines that
    would have shown it — the snapshot and the records — are the two the
    comparison of the forms' words does not read either.

    The expectation is read out of the canonical document, so that a document
    that changed moves the expectation with it.
    """
    context = report_world.context
    render_report(
        context,
        ReportRequest(path="report", template_id="default"),
        now=_MOMENT,
    )
    revision = _report_dir(context) / "v1"
    document = json.loads((revision / "report.json").read_text(encoding="utf-8"))
    # Each form is read by the reader its own test reads it with: the DOCX out
    # of its package, the PDF by a reader that did not write it, and the two
    # text forms by a parser.
    forms = {
        "markdown": _read_markdown((revision / "report.md").read_bytes()),
        "html": _read_html((revision / "report.html").read_bytes()),
        "docx": _read_docx((revision / "report.docx").read_bytes()),
        "pdf": _read_pdf((revision / "report.pdf").read_bytes()),
    }
    markdown = forms["markdown"]
    html = forms["html"]

    as_of = datetime.fromisoformat(document["snapshot"]["as_of"])
    records = frozenset(document["snapshot"]["record_ids"])
    for form, text in forms.items():
        moments, named = _the_snapshot_a_form_states(text)
        assert moments == {as_of}, (
            f"the {form} form is a view of {sorted(moments)}, and the document is a view of {as_of}"
        )
        assert named == records, (
            f"the {form} form names {sorted(named)}, and the document is a view of "
            f"{sorted(records)}"
        )

    assert document["snapshot"]["record_ids"] == ["ev-1"]
    assert _CAPTION in markdown
    assert _CAPTION in html
    assert "ev-1" in markdown
    assert _INTERPRETATION in markdown
    assert _INTERPRETATION_MARKER in markdown
    assert document["figures"][0]["caption"] == _CAPTION


def test_the_reports_chain_names_the_material(report_world: _ReportWorld) -> None:
    """The chain reaches outside the report's own files, to the material.

    A report whose chain names nothing but its own files could not be marked
    stale when the material moves: the staleness walk compares the hashes in
    the artefact's own ``derived_from``, and the report's own files never
    change when the material does.
    """
    context = report_world.context
    rendered = render_report(
        context,
        ReportRequest(path="report", template_id="default"),
        now=_MOMENT,
    )
    named = {
        (link.target_kind.value, link.target_id): link.content_sha256
        for link in rendered.receipt.derived_from
    }
    assert ("material_file", "materials/one.txt") in named
    assert named[("material_file", "materials/one.txt")] == report_world.material_hash


def test_a_second_render_writes_a_second_revision_and_leaves_the_first_alone(
    report_world: _ReportWorld,
) -> None:
    """A second render is a new revision, and the first revision's bytes are untouched.

    A revision is immutable once written, so the second render cannot be the
    first render again: it is a new set of files beside the old ones.
    """
    context = report_world.context
    render_report(
        context,
        ReportRequest(path="report", template_id="default"),
        now=_MOMENT,
    )
    first = _report_dir(context) / "v1"
    before = {path.name: path.read_bytes() for path in first.iterdir()}

    second = render_report(
        context,
        ReportRequest(path="report", template_id="default"),
        now=datetime(2026, 2, 2, tzinfo=UTC),
    )
    assert second.receipt.revision == 2
    assert (_report_dir(context) / "v2" / "report.md").is_file()
    assert {path.name: path.read_bytes() for path in first.iterdir()} == before


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


def _use(resource_key: str = "one.csv") -> ApprovalUse:
    """What an approval is spent on, matching the stage request."""
    return ApprovalUse(
        capability=CapabilityId.ANALYSIS_RUN,
        arguments={"operator_id": "mean", "parameters": {}},
        root_id="source:0",
        resource_key=resource_key,
    )
