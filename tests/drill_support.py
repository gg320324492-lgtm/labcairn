"""Shared assembly for the LC-P3-07 drill witnesses. Not a test module.

The drills all need the same rig: a workspace with a real original file, a
task under an asking policy, a loop opened over the original, and the two
granted consents. The loop's guarantees are about real files on disk and real
approvals spent, so everything here is real: files are written by the test,
approvals are asked and granted through the layer, and the only substitute in
sight is the one the provider drills inject deliberately.

Time is a fixed moment, per the repository's determinism rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from labcairn.application import ApplicationContext, create_task, grant_approval
from labcairn.application.revision_loop import (
    COPY_STAGE_NAME,
    LOOP_DIR_NAME,
    PUBLICATION_STAGE_NAME,
    LoopOpened,
    open_loop,
    publish_revision,
    request_loop_approval,
    stage_copy,
)
from labcairn.core.ids import ApprovalId
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.policy import Permission, PermissionPolicy, Rule

#: The fixed moment the drill witnesses date themselves with.
MOMENT: datetime = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)
WINDOW_END: datetime = MOMENT + timedelta(hours=1)

ORIGINAL_BYTES: bytes = (
    b"drill original line one\ndrill original line two\ndrill original line three\n"
)
EDITED_BYTES: bytes = b"drill original line one\ndrill edited line two\ndrill original line three\n"


def allow_all() -> PermissionPolicy:
    """The policy the task is created under."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])


def ask_all() -> PermissionPolicy:
    """The policy the loop's own context runs under: every effect asks."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ASK, pattern="**")])


@dataclass(slots=True)
class DrillRig:
    """One workspace, one task, one original, one opened loop, two grants."""

    context: ApplicationContext
    workspace_root: Path
    source_dir: Path
    original_path: Path
    loop: LoopOpened
    copy_approval_id: ApprovalId | None = None
    publication_approval_id: ApprovalId | None = None
    #: Set by a drill that published, for the recovery assertions.
    published: Any = None

    @property
    def output_dir(self) -> Path:
        from labcairn.workspace.roots import OUTPUT_DIR_NAME

        return self.workspace_root / OUTPUT_DIR_NAME / str(self.context.task_id)

    def loop_dir(self) -> Path:
        """The loop's fixed directory under the task output area."""
        return self.output_dir / LOOP_DIR_NAME / self.loop.import_receipt.receipt_id

    def copy_path(self) -> Path:
        return self.loop_dir() / "copy.bin"

    def publication_path(self) -> Path:
        return self.loop_dir() / "published.bin"

    def manifest_path(self) -> Path:
        return self.loop_dir() / "import-receipt.json"


def build_rig(env_store: Any, workspace_root: Path) -> DrillRig:
    """Bind a workspace whose source root holds a real original, and open a loop."""
    source_dir = workspace_root / "materials"
    source_dir.mkdir(parents=True, exist_ok=True)
    original = source_dir / "original.bin"
    original.write_bytes(ORIGINAL_BYTES)

    created = create_task(
        store=env_store,
        policy=allow_all(),
        workspace_root=workspace_root,
        title="Drill rig task",
        goal=TaskGoal(
            objective="Survive the drills.",
            success_criterion="A published revision and an untouched original.",
        ),
        source_dirs=(source_dir,),
        now=MOMENT,
    )
    context = ApplicationContext(
        workspace=created.workspace,
        store=env_store,
        policy=ask_all(),
        ledger=ApprovalLedger(),
    )
    loop = open_loop(
        context,
        source_root_id="source:0",
        source_key="original.bin",
        now=MOMENT,
    )
    return DrillRig(
        context=context,
        workspace_root=workspace_root,
        source_dir=source_dir,
        original_path=original,
        loop=loop,
    )


def grant_copy(rig: DrillRig) -> ApprovalId:
    """Ask and grant the copy consent, dated at the fixed moment."""
    asked = request_loop_approval(
        rig.context,
        rig.loop,
        stage_name=COPY_STAGE_NAME,
        expires_at=WINDOW_END,
        now=MOMENT,
    )
    granted = grant_approval(rig.context, asked.approval.approval_id, now=MOMENT)
    rig.copy_approval_id = granted.approval.approval_id
    return rig.copy_approval_id


def grant_publication(rig: DrillRig) -> ApprovalId:
    """Ask and grant the publication consent, dated at the fixed moment."""
    asked = request_loop_approval(
        rig.context,
        rig.loop,
        stage_name=PUBLICATION_STAGE_NAME,
        expires_at=WINDOW_END,
        now=MOMENT,
    )
    granted = grant_approval(rig.context, asked.approval.approval_id, now=MOMENT)
    rig.publication_approval_id = granted.approval.approval_id
    return rig.publication_approval_id


def run_loop_to_publication(rig: DrillRig, *, edited: bytes = EDITED_BYTES) -> None:
    """Copy, edit, publish: the loop's happy path, with both consents granted."""
    stage_copy(rig.context, rig.loop, approval_id=grant_copy(rig), now=MOMENT)
    rig.copy_path().write_bytes(edited)
    publish_revision(
        rig.context,
        rig.loop,
        approval_id=grant_publication(rig),
        edited_bytes=edited,
        now=MOMENT,
    )
