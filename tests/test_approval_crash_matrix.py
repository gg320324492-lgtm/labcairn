"""The approval survives the process, and the second spend does not.

**What is under test.** LC-P2-02 T05: the crash matrix. A grant that lived only
in memory is a grant the next process has never heard of — the spend fails
closed with ``APPROVAL_MISSING``, which is safe and is not what a consent is
for. And an approval spent twice across a restart is the double spend this
work order exists to prevent.

**The process really is a process.** Each case starts a **child interpreter**
that grants (and, in the first case, spends) and then calls ``os._exit`` — no
cleanup, no teardown, nothing the parent can rely on beyond what reached the
database. The parent then builds a **fresh session and a fresh ledger** against
the same file, which is exactly what a restart hands a surface.

============================  =================================================
A6  the crash, and the row     a spend after a crash is refused **from the row**
A7  a restart un-spends nothing  a grant outlives the process that granted it
============================  =================================================
"""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from labcairn.application import (
    ApplicationContext,
    ApplicationRefusedError,
    ApprovalUse,
    consume_approval,
    create_task,
)
from labcairn.application.context import approval_ledger_for
from labcairn.core.ids import ApprovalId, TaskId
from labcairn.db import create_db_engine, create_session_factory
from labcairn.db.migrations import upgrade_to_head
from labcairn.db.models import ApprovalRow
from labcairn.db.repository import TaskStore
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.runtime.operation import ApprovalState
from labcairn.security.capabilities import CapabilityId
from labcairn.security.policy import Permission, PermissionPolicy, Rule
from labcairn.workspace.roots import Workspace

pytestmark = pytest.mark.integration

_MOMENT = datetime(2026, 1, 1, tzinfo=UTC)

#: The child. It builds its own context from the database file and dies with
#: ``os._exit`` — a crash rather than a return, so the parent inherits nothing
#: but what the store holds. It prints the approval id it minted **before**
#: dying, because that is the one thing the parent cannot read back reliably:
#: two rows could share a moment, and the id names the one that matters.
DRIVER: str = """
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from labcairn.application import (
    ApplicationContext,
    ApprovalUse,
    consume_approval,
    grant_approval,
    request_approval,
)
from labcairn.application.approvals import ApprovalRequest
from labcairn.application.context import approval_ledger_for
from labcairn.core.ids import TaskId
from labcairn.db import create_db_engine, create_session_factory
from labcairn.db.repository import TaskStore
from labcairn.security.capabilities import CapabilityId
from labcairn.security.policy import Permission, PermissionPolicy, Rule
from labcairn.workspace.roots import Workspace

root = Path(sys.argv[1])
task_id = TaskId(UUID(sys.argv[2]))
mode = sys.argv[3]
now = datetime(2026, 1, 1, tzinfo=UTC)

THE_USE = ApprovalUse(
    capability=CapabilityId.ANALYSIS_RUN,
    arguments={"operator_id": "mean", "parameters": {}, "recipe": "figure.recipe.json"},
    root_id="source:0",
    resource_key="one.csv",
)

engine = create_db_engine(root / "labcairn.db")
session = create_session_factory(engine)()
store = TaskStore(session)
workspace = Workspace.bind(root, task_id=task_id, source_dirs=(root / "materials",))
policy = PermissionPolicy.from_rules([Rule(effect=Permission.ASK, pattern="**")])
context = ApplicationContext(
    workspace=workspace,
    store=store,
    policy=policy,
    ledger=approval_ledger_for(store),
)
asked = request_approval(
    context,
    ApprovalRequest(use=THE_USE, expires_at=now + timedelta(hours=1)),
    now=now,
)
granted = grant_approval(context, asked.approval.approval_id, now=now)
sys.stdout.write(str(granted.approval.approval_id))
sys.stdout.flush()
if mode == "consume":
    consume_approval(context, granted.approval.approval_id, THE_USE, now=now)
os._exit(0)
"""


def _ask_all() -> PermissionPolicy:
    return PermissionPolicy.from_rules([Rule(effect=Permission.ASK, pattern="**")])


def _use() -> ApprovalUse:
    return ApprovalUse(
        capability=CapabilityId.ANALYSIS_RUN,
        arguments={"operator_id": "mean", "parameters": {}, "recipe": "figure.recipe.json"},
        root_id="source:0",
        resource_key="one.csv",
    )


def _workspace(tmp_path: Path) -> tuple[Path, TaskId]:
    """A workspace, a migrated database and a task — the parent's side."""
    root = tmp_path / "workspace"
    (root / "materials").mkdir(parents=True)
    upgrade_to_head(root / "labcairn.db")
    engine = create_db_engine(root / "labcairn.db")
    session = create_session_factory(engine)()
    try:
        store = TaskStore(session)
        created = create_task(
            store=store,
            policy=PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")]),
            workspace_root=root,
            title="Restart-durable consent",
            goal=TaskGoal(
                objective="Establish whether the observation holds.",
                success_criterion="A cited answer, or an honest 'not established'.",
            ),
            source_dirs=(root / "materials",),
        )
        return root, created.task.task_id
    finally:
        session.close()
        engine.dispose()


def _child(root: Path, task_id: TaskId, mode: str) -> ApprovalId:
    """Run the child, and return the approval id it printed before dying."""
    completed = subprocess.run(
        [sys.executable, "-c", DRIVER, str(root), str(task_id), mode],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return ApprovalId(UUID(completed.stdout.strip()))


def _context(root: Path, task_id: TaskId) -> tuple[ApplicationContext, Session, Engine]:
    engine = create_db_engine(root / "labcairn.db")
    session = create_session_factory(engine)()
    store = TaskStore(session)
    workspace = Workspace.bind(root, task_id=task_id, source_dirs=(root / "materials",))
    context = ApplicationContext(
        workspace=workspace,
        store=store,
        policy=_ask_all(),
        ledger=approval_ledger_for(store),
    )
    return context, session, engine


def test_a_crash_between_grant_and_consume_refuses_the_second_spend(
    tmp_path: Path,
) -> None:
    """A6 — granted and spent in one process, refused in the next.

    The child grants **and spends** before it dies, so the row it leaves says
    `CONSUMED`. The parent's spend is the second one, and it is refused
    **from the row** — not from a dict the crash emptied, because the dict is
    gone.
    """
    root, task_id = _workspace(tmp_path)
    approval_id = _child(root, task_id, "consume")
    context, session, engine = _context(root, task_id)
    try:
        row = session.execute(
            select(ApprovalRow).where(ApprovalRow.approval_id == str(approval_id))
        ).scalar_one()
        assert row.state == ApprovalState.CONSUMED.value, (
            "the row the child wrote is what the parent reads, and it says the approval was spent"
        )
        with pytest.raises(ApplicationRefusedError):
            consume_approval(context, approval_id, _use(), now=_MOMENT)
    finally:
        session.close()
        engine.dispose()


def test_a_grant_outlives_the_process_that_granted_it(tmp_path: Path) -> None:
    """A7 — the grant a crash left behind is spendable exactly once.

    **This is the property the in-memory ledger could not have.** The child
    grants and dies; the parent — a different interpreter, a different ledger —
    spends it, and the second spend is refused.
    """
    root, task_id = _workspace(tmp_path)
    approval_id = _child(root, task_id, "grant")
    context, session, engine = _context(root, task_id)
    try:
        consume_approval(context, approval_id, _use(), now=_MOMENT)
        with pytest.raises(ApplicationRefusedError):
            consume_approval(context, approval_id, _use(), now=_MOMENT)
    finally:
        session.close()
        engine.dispose()
