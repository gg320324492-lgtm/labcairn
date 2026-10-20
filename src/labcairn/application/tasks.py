"""The task itself: making one, and reading one back.

A Task is the continuing research objective — the thing that outlives every
execution attempt — so these are the two operations everything else is about.
The CLI's ``task create`` and ``task status`` are them, and so are the API's
task document and the UI's task panel.

Creating a task is the one operation with no approval to bind
---------------------------------------------------------------

An approval is scoped to a task, and a task does not exist until it is
created, so there is nothing for a create to be approved against. Its consent
is the policy's verdict and the policy's verdict alone. That is stated here
rather than left to be discovered, because "why does this one operation differ"
is exactly the question a reader of the layer will have.

The task's output area is created before the verdict
-----------------------------------------------------

The verdict needs a canonical path, and a directory that does not exist cannot
be one. So a refused task leaves an empty directory behind and **no task**:
nothing is written to the store, and the directory holds nothing. The
alternative — refusing before the directory exists — would mean judging a
resource the workspace cannot yet name.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from labcairn.application import consent
from labcairn.application.context import ApplicationContext, store_refusals
from labcairn.application.models import Result
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.core.ids import SourceId
from labcairn.db.repository import TaskStore, last_seq, list_approvals, list_artifacts, load_task
from labcairn.db.repository import list_runs as store_list_runs
from labcairn.db.repository import list_stages as store_list_stages
from labcairn.db.repository import list_tasks as store_list_tasks
from labcairn.reports.receipt import ArtifactReceipt
from labcairn.runtime.lifecycle import Run, Stage, Task, TaskGoal
from labcairn.runtime.operation import Approval
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import CapabilityId
from labcairn.security.policy import PermissionPolicy
from labcairn.workspace.roots import Workspace, WorkspaceError


@dataclass(frozen=True, slots=True)
class TaskCreated:
    """A task that has been made, and the workspace that belongs to it.

    The workspace is carried with the task because it is what a caller needs
    next: every other operation in the layer is given a context, and a context
    is a workspace plus the store, the policy and the ledger.
    """

    task: Task
    workspace: Workspace


class TaskState(Result):
    """What a task currently is, as one value.

    The whole state rather than the task's own row, because the question a
    surface asks is "where is this task?" — and answering it from the task
    row alone would mean a second round trip for the runs, another for the
    stages and another for the artefacts. One value, one read, one answer.

    ``last_event_seq`` is the cursor a client resumes an event stream from.
    It is here so that a surface can read the state and follow the events
    without a gap between the two.
    """

    task: Task
    runs: tuple[Run, ...]
    stages: tuple[Stage, ...]
    artifacts: tuple[ArtifactReceipt, ...]
    approvals: tuple[Approval, ...]
    last_event_seq: int


def create_task(
    *,
    store: TaskStore,
    policy: PermissionPolicy,
    workspace_root: Path,
    title: str,
    goal: TaskGoal,
    source_dirs: tuple[Path, ...] = (),
    bound_source_ids: tuple[SourceId, ...] = (),
    now: datetime | None = None,
) -> TaskCreated:
    """Make a task, its workspace and its first event.

    The task row and the ``task_created`` event are written in one transaction
    by the store's own :meth:`~labcairn.db.repository.TaskStore.create_task`,
    because ADR-0003 C3 requires the event and the state it describes to
    commit together.

    :raises ApplicationRefusedError: the workspace could not be bound, or the
        policy denied writing the task's area.
    """
    moment = now if now is not None else datetime.now(UTC)
    task = Task(
        title=title,
        goal=goal,
        bound_source_ids=bound_source_ids,
        created_at=moment,
        updated_at=moment,
    )
    try:
        workspace = Workspace.bind(
            workspace_root,
            task_id=task.task_id,
            source_dirs=source_dirs,
        )
    except (WorkspaceError, OSError) as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.PATH_REFUSED,
            f"the workspace could not be bound at {workspace_root}: {error}",
        ) from error

    context = ApplicationContext(
        workspace=workspace,
        store=store,
        policy=policy,
        ledger=_unused_ledger(),
    )
    area = context.task_area()
    consent.evaluate(
        context,
        capability=CapabilityId.FS_WRITE,
        arguments={"path": area.declared_key},
        resource=area,
    )

    store.create_task(task)
    return TaskCreated(task=task, workspace=workspace)


def read_task_state(context: ApplicationContext) -> TaskState:
    """The task's state, as one value.

    :raises ApplicationRefusedError: the policy denied reading the task's area,
        or the store holds no task with that id.
    """
    area = context.task_area()
    consent.evaluate(
        context,
        capability=CapabilityId.FS_READ,
        arguments={"path": area.declared_key},
        resource=area,
    )
    with store_refusals():
        task = load_task(context.store.session, context.task_id)
        runs = store_list_runs(context.store.session, context.task_id)
        stages = store_list_stages(context.store.session, context.task_id)
        artifacts = list_artifacts(context.store.session, context.task_id)
        approvals = list_approvals(context.store.session, context.task_id)
        seq = last_seq(context.store.session, context.task_id)
    return TaskState(
        task=task,
        runs=runs,
        stages=stages,
        artifacts=artifacts,
        approvals=approvals,
        last_event_seq=seq,
    )


def list_tasks(context: ApplicationContext) -> tuple[Task, ...]:
    """Every task in this workspace's store, oldest first.

    Not task-scoped — a Task is the root of the hierarchy rather than something
    inside one — but still capability-checked, against the same resource the
    task's own state is bound to, because listing the tasks *is* reading the
    workspace's task area.

    :raises ApplicationRefusedError: the policy denied listing the area.
    """
    area = context.task_area()
    consent.evaluate(
        context,
        capability=CapabilityId.FS_LIST,
        arguments={"path": area.declared_key, "pattern": "*"},
        resource=area,
    )
    with store_refusals():
        return store_list_tasks(context.store.session)


def _unused_ledger() -> ApprovalLedger:
    """A ledger for an operation that cannot have an approval.

    Creating a task has nothing to be approved against — see the module
    docstring — so no approval can be consumed and the ledger is never read.
    It is still part of the context because the context's shape is the same for
    every operation, and a context that changes shape is a context every
    caller has to know the type of.
    """
    return ApprovalLedger()


__all__ = [
    "TaskCreated",
    "TaskState",
    "create_task",
    "list_tasks",
    "read_task_state",
]
