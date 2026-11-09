"""Shared builders for the revision-loop witnesses. Not a test module.

The loop's witnesses all need the same four things — a workspace with a real
original file in it, a task bound to that workspace, a policy that asks (so
every effect needs a consent), and the ask/grant/spend sequence of an approval
— and a loop test whose whole body is fixture assembly tests nothing useful.
This is the repository's own convention for shared setup: a support module the
test files import, no ``tests/conftest.py`` growth.

Everything here is deterministic: a fixed moment rather than the wall clock,
ids from the store's own minting, and files that are **real files on disk**.
The loop's claim is about real file operations; a witness that faked the
filesystem would witness the fake.
"""

from __future__ import annotations

import builtins
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from labcairn.application import ApplicationContext, create_task, grant_approval
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.application.revision_loop import (
    COPY_STAGE_NAME,
    PUBLICATION_STAGE_NAME,
    LoopOpened,
    open_loop,
    request_loop_approval,
)
from labcairn.core.ids import ApprovalId, TaskId
from labcairn.db.repository import TaskStore
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.policy import Permission, PermissionPolicy, Rule

#: The single moment the loop witnesses date themselves with. Determinism rule:
#: no wall clock, no fixture drift.
MOMENT: datetime = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

#: An approval's window. The window matters to the stale-approval witness: the
#: staleness must be about the *material*, not about a closed window.
WINDOW_END: datetime = MOMENT + timedelta(hours=1)

#: The original's bytes. ASCII on purpose: the tree's CJK ceiling watches what
#: witnesses say about material, and the loop's original is bytes, not prose.
ORIGINAL_BYTES: bytes = b"first line\nsecond line\nthird line\n"
EDITED_BYTES: bytes = b"first line\nsecond line EDITED\nthird line\n"


def ask_all() -> PermissionPolicy:
    """A policy that asks about everything: a question, not a denial."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ASK, pattern="**")])


def allow_all() -> PermissionPolicy:
    """The policy a task is created under; the loop's own context uses ``ask_all``."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])


@dataclass
class LoopFixture:
    """One workspace, one task, one original, one context — and the file paths."""

    context: ApplicationContext
    workspace_root: Path
    source_dir: Path
    original_path: Path
    source_key: str = "original.bin"
    source_root_id: str = "source:0"


def build_fixture(env_store: TaskStore, workspace_root: Path) -> LoopFixture:
    """Bind a workspace whose source directory holds a real original file.

    The original is written with the test's own hands before anything runs:
    the loop's guarantee is about a file that exists on disk, not about a file
    a fixture promised to create.
    """
    source_dir = workspace_root / "materials"
    source_dir.mkdir(parents=True, exist_ok=True)
    original = source_dir / "original.bin"
    original.write_bytes(ORIGINAL_BYTES)

    created = create_task(
        store=env_store,
        policy=allow_all(),
        workspace_root=workspace_root,
        title="Loop witness task",
        goal=TaskGoal(
            objective="Revise the original without touching it.",
            success_criterion="A published revision and an untouched original.",
        ),
        source_dirs=(source_dir,),
    )
    context = ApplicationContext(
        workspace=created.workspace,
        store=env_store,
        policy=ask_all(),
        ledger=ApprovalLedger(),
    )
    return LoopFixture(
        context=context,
        workspace_root=workspace_root,
        source_dir=source_dir,
        original_path=original,
    )


def second_task(store: TaskStore, fixture: LoopFixture) -> TaskId:
    """Bind a second task over the same selected root, and leave a real output file in it.

    This is what "cross-project" means when a witness asserts it: another
    task's output area, holding bytes that task generated, on the same disk.
    The file is written here rather than produced by a second loop so the
    witness does not depend on the loop under test to set its own trap.
    """
    created = create_task(
        store=store,
        policy=allow_all(),
        workspace_root=fixture.workspace_root,
        title="The other task",
        goal=TaskGoal(
            objective="A second project sharing the selected root.",
            success_criterion="Its output stays its own.",
        ),
    )
    other_output = fixture.workspace_root / "output" / str(created.task.task_id)
    other_output.mkdir(parents=True, exist_ok=True)
    (other_output / "foreign.bin").write_bytes(b"another task's generated bytes\n")
    return created.task.task_id


def open_a_loop(fixture: LoopFixture) -> LoopOpened:
    """Open the loop over the fixture's original, dated at the fixed moment."""
    return open_loop(
        fixture.context,
        source_root_id=fixture.source_root_id,
        source_key=fixture.source_key,
        now=MOMENT,
    )


def granted_copy_approval(context: ApplicationContext, loop: LoopOpened) -> ApprovalId:
    """Ask and grant the copy consent, both dated at the fixed moment."""
    requested = request_loop_approval(
        context, loop, stage_name=COPY_STAGE_NAME, expires_at=WINDOW_END, now=MOMENT
    )
    granted = grant_approval(context, requested.approval.approval_id, now=MOMENT)
    return granted.approval.approval_id


def granted_publication_approval(context: ApplicationContext, loop: LoopOpened) -> ApprovalId:
    """Ask and grant the publication consent, both dated at the fixed moment."""
    requested = request_loop_approval(
        context, loop, stage_name=PUBLICATION_STAGE_NAME, expires_at=WINDOW_END, now=MOMENT
    )
    granted = grant_approval(context, requested.approval.approval_id, now=MOMENT)
    return granted.approval.approval_id


class WriteSpy:
    """Records every write-class filesystem call made while it is armed.

    The loop's refusals claim *"refused before any file is touched"*, and the
    assertion that carries that claim needs to see the primitive, not one
    wrapper around it — the same reason ``tests/test_workspace_boundaries.py``
    patches ``builtins.open`` and ``os.replace`` rather than the layer. A read
    (``open(path, "rb")``) is **not** a write; the loop hashes originals with
    it, and a spy that counted reads would make every witness vacuously red.
    """

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __enter__(self) -> WriteSpy:
        self._saved: list[tuple[Any, str, Any]] = []
        for module, name, attribute in self._targets():
            self._saved.append((module, name, getattr(module, name)))
            setattr(module, name, self._wrap(name, attribute))
        return self

    def __exit__(self, *exc: object) -> None:
        for module, name, original in self._saved:
            setattr(module, name, original)

    @staticmethod
    def _targets() -> list[tuple[Any, str, Any]]:
        return [
            (builtins, "open", builtins.open),
            (os, "open", os.open),
            (os, "replace", os.replace),
            (os, "rename", os.rename),
            (os, "remove", os.remove),
            (os, "unlink", os.unlink),
            (os, "mkdir", os.mkdir),
            (os, "makedirs", os.makedirs),
            (shutil, "copyfile", shutil.copyfile),
            (shutil, "copy2", shutil.copy2),
            (shutil, "move", shutil.move),
        ]

    def _wrap(self, name: str, original: Any) -> Callable[..., Any]:
        def probe(*args: Any, **kwargs: Any) -> Any:
            if self._is_write_call(name, args, kwargs):
                self.calls.append(name)
            return original(*args, **kwargs)

        return probe

    @staticmethod
    def _is_write_call(name: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> bool:
        if name != "open":
            return True
        mode = kwargs.get("mode") or (args[1] if len(args) > 1 else "r")
        mode = str(mode).replace("b", "").replace("t", "")
        return any(marker in mode for marker in "wax+")


def refusal_of(call: Callable[[], object], what: str) -> ApplicationRefusedError:
    """Run *call* and hand back the refusal it raised, or fail telling why.

    **A completed call is the defect, reported as one.** A class the loop
    claims to refuse must refuse; a test that asserts afterwards that the file
    "was not changed" would pass on a loop that wrote the file and left the
    old copy readable.
    """
    try:
        call()
    except ApplicationRefusedError as error:
        return error
    pytest.fail(
        f"{what} was not refused: the call completed. A class the loop claims to "
        "refuse must refuse, not succeed and be asserted about afterwards."
    )
    raise AssertionError  # unreachable: pytest.fail raises


__all__ = [
    "EDITED_BYTES",
    "MOMENT",
    "ORIGINAL_BYTES",
    "WINDOW_END",
    "ApplicationRefusal",
    "ApplicationRefusedError",
    "LoopFixture",
    "WriteSpy",
    "allow_all",
    "ask_all",
    "build_fixture",
    "granted_copy_approval",
    "granted_publication_approval",
    "open_a_loop",
    "refusal_of",
    "second_task",
]
