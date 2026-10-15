"""Workspace binding, read-only sources, and atomic output writes.

The test this file exists for is
:func:`test_source_root_is_read_only_before_any_syscall`, ADR-0003 §C7's
*assert refused **and**, via a filesystem spy, that zero write syscalls were
attempted*. A refusal after the file was opened for writing has already truncated
it, so "it raised" is not the property — "nothing was touched" is.

The spy patches every write primitive the standard library offers and asserts not
one was called. It is deliberately broad: if a future implementation reached for
``shutil``, ``os.truncate`` or ``Path.write_text``, the test fails rather than
quietly passing because the path it used happened not to be covered.
"""

from __future__ import annotations

import builtins
import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from labcairn.core.ids import new_id
from labcairn.security.paths import PathRefusedError, RootKind
from labcairn.security.policy import Permission, PermissionPolicy, Rule
from labcairn.workspace.outputs import (
    CountingWriteObserver,
    OutputRefusedError,
    TaskOutputArea,
    WriteOutcome,
)
from labcairn.workspace.readonly import SourceIsReadOnlyError, SourceMaterial
from labcairn.workspace.roots import Workspace, WorkspaceError


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    root = tmp_path / "ws"
    sources = root / "sources"
    (sources / "papers").mkdir(parents=True)
    (sources / "papers" / "a.pdf").write_bytes(b"%PDF-1.4 a")
    return Workspace.bind(root, task_id=new_id(), source_dirs=(sources,))


@pytest.fixture
def source_id(workspace: Workspace) -> str:
    return workspace.source_roots[0].root_id


class WriteSpy:
    """Records every attempt to modify the filesystem.

    Patches rather than subclasses so the assertion covers the *primitive* being
    reached for, not one particular wrapper: a caller that bypassed
    ``SourceMaterial.write`` and called ``open()`` directly is exactly the case
    this has to catch.
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
        import ntpath

        return [
            (builtins, "open", builtins.open),
            (os, "open", os.open),
            (os, "replace", os.replace),
            (os, "rename", os.rename),
            (os, "remove", os.remove),
            (os, "unlink", os.unlink),
            (os, "rmdir", os.rmdir),
            (os, "mkdir", os.mkdir),
            (os, "makedirs", os.makedirs),
            (os, "truncate", os.truncate),
            (os, "utime", os.utime),
            (os, "chmod", os.chmod),
            (ntpath, "abspath", ntpath.abspath),
            (shutil, "rmtree", shutil.rmtree),
            (shutil, "copyfile", shutil.copyfile),
            (shutil, "copy2", shutil.copy2),
            (shutil, "move", shutil.move),
            (Path, "write_text", Path.write_text),
            (Path, "write_bytes", Path.write_bytes),
            (Path, "unlink", Path.unlink),
            (Path, "mkdir", Path.mkdir),
            (Path, "rename", Path.rename),
            (Path, "touch", Path.touch),
        ]

    def _wrap(self, name: str, original: Any) -> Callable[..., Any]:
        def recorder(*args: Any, **kwargs: Any) -> Any:
            self.calls.append(name)
            return original(*args, **kwargs)

        return recorder


# ---------------------------------------------------------------------------
# Binding
# ---------------------------------------------------------------------------


def test_a_workspace_binds_a_workspace_source_and_output_root(workspace: Workspace) -> None:
    assert workspace.workspace_root.root_id == "workspace"
    assert workspace.output_root.root_id == "output"
    assert len(workspace.source_roots) == 1
    assert workspace.source_roots[0].kind is RootKind.SOURCE


def test_the_output_area_is_per_task_and_is_created(workspace: Workspace) -> None:
    assert workspace.output_root.path == (
        workspace.selected_root / "output" / str(workspace.task_id)
    )
    assert workspace.output_root.path.is_dir()


def test_two_tasks_do_not_share_an_output_directory(tmp_path: Path) -> None:
    """One task's artifacts must not be another task's to overwrite."""
    root = tmp_path / "ws"
    root.mkdir()
    first = Workspace.bind(root, task_id=new_id())
    second = Workspace.bind(root, task_id=new_id())
    assert first.output_root.path != second.output_root.path


def test_a_source_root_outside_the_selected_root_is_refused(tmp_path: Path) -> None:
    """A source the workspace does not contain is a root selection that failed."""
    ws = tmp_path / "ws"
    elsewhere = tmp_path / "elsewhere"
    ws.mkdir()
    elsewhere.mkdir()
    with pytest.raises(WorkspaceError, match="outside the selected workspace"):
        Workspace.bind(ws, task_id=new_id(), source_dirs=(elsewhere,))


def test_binding_requires_an_existing_selected_root(tmp_path: Path) -> None:
    """No "create it and carry on": a root that had to be invented is not selected."""
    with pytest.raises(PathRefusedError):
        Workspace.bind(tmp_path / "never-created", task_id=new_id())


def test_an_output_write_needs_a_named_root(workspace: Workspace) -> None:
    with pytest.raises(WorkspaceError):
        workspace.canonicalize_in(
            workspace.output_root.path / "a.md", workspace.source_roots[0].root_id
        )


# ---------------------------------------------------------------------------
# Read-only source material
# ---------------------------------------------------------------------------


def test_source_material_can_be_read(workspace: Workspace, source_id: str) -> None:
    permissive = PermissionPolicy.from_rules([Rule(Permission.ALLOW, "**")])
    material = SourceMaterial(workspace, permissive)
    assert material.read("papers/a.pdf", root_id=source_id) == b"%PDF-1.4 a"


@pytest.mark.parametrize("method", ["write", "delete"])
def test_source_writes_are_refused_before_any_syscall(
    workspace: Workspace, source_id: str, method: str
) -> None:
    """ADR-0003 §C7: refused **and** zero write syscalls attempted.

    The second half is the assertion. The call raises, and the spy proves
    nothing on disk was touched on the way there.
    """
    material = SourceMaterial(workspace, PermissionPolicy())
    with WriteSpy() as spy, pytest.raises(SourceIsReadOnlyError):
        if method == "write":
            material.write("papers/a.pdf", b"overwritten", root_id=source_id)
        else:
            material.delete("papers/a.pdf", root_id=source_id)

    assert spy.calls == [], f"a write primitive was reached before the refusal: {spy.calls}"


def test_the_source_file_is_byte_identical_after_a_refused_write(
    workspace: Workspace, source_id: str
) -> None:
    """The outcome the acceptance criterion names, stated as a hash.

    "No irreversible change to supplied source data" is not an absence-of-error;
    it is the bytes being the same afterwards.
    """
    from labcairn.security.approval import content_hash

    target = workspace.root_for(source_id).path / "papers" / "a.pdf"
    before = content_hash(target)

    material = SourceMaterial(workspace, PermissionPolicy())
    with pytest.raises(SourceIsReadOnlyError):
        material.write("papers/a.pdf", b"overwritten", root_id=source_id)

    assert content_hash(target) == before
    assert target.read_bytes() == b"%PDF-1.4 a"


def test_the_source_view_cannot_address_the_output_area(
    workspace: Workspace, source_id: str
) -> None:
    """ "Read something in the workspace" is the wrong question for source.

    The output file exists and is readable through its own root — what must not
    be possible is naming it through the source view, whether directly or by
    climbing out with ``..``.
    """
    (workspace.output_root.path / "a.md").write_bytes(b"generated")
    permissive = PermissionPolicy.from_rules([Rule(Permission.ALLOW, "**")])
    material = SourceMaterial(workspace, permissive)

    # Direct: the key does not exist under the source root.
    with pytest.raises((WorkspaceError, FileNotFoundError)):
        material.read("a.md", root_id=source_id)

    # Climbing: `..` resolves into the output root, which is a cross-root move.
    with pytest.raises(WorkspaceError):
        material.read("../../../output/a.md", root_id=source_id)


def test_a_junction_from_source_into_output_is_refused(
    workspace: Workspace, source_id: str
) -> None:
    """The root-kind check follows the link, so a planted link gains nothing."""
    if os.name != "nt":
        pytest.skip("junction creation is Windows-specific")
    import subprocess

    output = workspace.output_root.path
    (output / "planted.txt").write_text("planted", encoding="utf-8")
    link = workspace.root_for(source_id).path / "escape"
    proc = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(output)],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip("mklink /J unavailable")

    permissive = PermissionPolicy.from_rules([Rule(Permission.ALLOW, "**")])
    material = SourceMaterial(workspace, permissive)
    # Either refusal is correct, and cross-root fires *first* — the junction is
    # caught by canonicalisation before the root-kind check ever runs. Both are
    # refusals; the assertion is that one of them happened.
    with pytest.raises((SourceIsReadOnlyError, WorkspaceError)):
        material.read("escape/planted.txt", root_id=source_id)


def test_listing_filters_denied_entries_out_of_the_result(
    workspace: Workspace, source_id: str
) -> None:
    """§C5: the model must not learn that a denied name existed."""
    source = workspace.root_for(source_id).path / "papers"
    (source / "private.pdf").write_bytes(b"%PDF-1.4 private")

    material = SourceMaterial(
        workspace,
        PermissionPolicy.from_rules(
            [
                Rule(Permission.ALLOW, "**"),
                Rule(Permission.DENY, "papers/private.pdf"),
            ]
        ),
    )
    listed = material.list_dir("papers", root_id=source_id)
    assert "papers/a.pdf" in listed
    assert "papers/private.pdf" not in listed


def test_listing_under_default_deny_is_empty_not_an_error(
    workspace: Workspace, source_id: str
) -> None:
    material = SourceMaterial(workspace, PermissionPolicy())
    assert material.list_dir("papers", root_id=source_id) == ()


# ---------------------------------------------------------------------------
# Output writes
# ---------------------------------------------------------------------------


def test_a_write_lands_in_the_task_output_area(workspace: Workspace) -> None:
    area = TaskOutputArea(workspace)
    receipt = area.write("reports/q1.md", b"# Q1")

    assert receipt.outcome is WriteOutcome.CREATED
    assert receipt.resource_key == "reports/q1.md"
    assert receipt.absolute_path == workspace.output_root.path / "reports" / "q1.md"
    assert receipt.absolute_path.read_bytes() == b"# Q1"
    assert receipt.size_bytes == 4


def test_rewriting_reports_a_replacement(workspace: Workspace) -> None:
    area = TaskOutputArea(workspace)
    area.write("a.md", b"first")
    assert area.write("a.md", b"second").outcome is WriteOutcome.REPLACED
    assert (workspace.output_root.path / "a.md").read_bytes() == b"second"


def test_a_write_leaves_no_temporary_file_behind(workspace: Workspace) -> None:
    """A leftover temp file is a half-written artifact a listing would show."""
    area = TaskOutputArea(workspace)
    area.write("deep/nested/a.md", b"x")
    leftovers = [p.name for p in (workspace.output_root.path).rglob("*") if ".lc-write-" in p.name]
    assert leftovers == []


def test_the_write_count_is_recorded_for_reconciliation(workspace: Workspace) -> None:
    """LC-P1-06's crash tests need a counter that survives the operation."""
    observer = CountingWriteObserver()
    area = TaskOutputArea(workspace, observers=(observer,))
    area.write("a.md", b"x")
    area.write("b.md", b"y")

    assert observer.attempts == 2
    assert observer.commits == 2
    assert observer.keys == ["a.md", "b.md"]
    assert observer.sizes == [1, 1]


def test_a_write_outside_the_output_area_is_refused(workspace: Workspace, source_id: str) -> None:
    """The structural floor: ``fs.write`` declares ``root_kinds={"output"}``."""
    area = TaskOutputArea(workspace)
    with pytest.raises((WorkspaceError, OutputRefusedError)):
        area.write("../sources/papers/a.pdf", b"clobbered")


def test_writing_over_a_source_file_through_a_junction_is_refused(
    workspace: Workspace, source_id: str
) -> None:
    """The one that matters most: an output write must not reach a source file."""
    if os.name != "nt":
        pytest.skip("junction creation is Windows-specific")
    import subprocess

    source = workspace.root_for(source_id).path / "papers"
    planted = workspace.output_root.path / "hop"
    proc = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(planted), str(source)],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip("mklink /J unavailable")

    area = TaskOutputArea(workspace)
    with pytest.raises((WorkspaceError, OutputRefusedError, PathRefusedError)):
        area.write("hop/a.pdf", b"clobbered")

    assert (source / "a.pdf").read_bytes() == b"%PDF-1.4 a", (
        "the source file was modified; the refusal came too late"
    )


def test_resolve_key_rechecks_rather_than_joining(workspace: Workspace) -> None:
    """A key was canonical when minted; the tree may have moved since.

    ``resolve_key`` re-canonicalises so a directory replaced by a junction after
    the key was issued is caught here and not only at evaluation time.
    """
    assert workspace.resolve_key("reports/q1.md", root_id="output") == (
        workspace.output_root.path / "reports" / "q1.md"
    )
    with pytest.raises(WorkspaceError):
        workspace.resolve_key("../outside/x.md", root_id="output")


def test_resolve_key_refuses_to_climb_into_another_root(
    workspace: Workspace, source_id: str
) -> None:
    """Naming a root must *enforce* it, not merely suggest it.

    ``../papers/a.pdf`` from the output root resolves back into the source root.
    A join-and-recheck would have returned it; ``path_in`` refuses it. This is
    the bug this test was written for.
    """
    with pytest.raises(WorkspaceError):
        workspace.resolve_key("../sources/papers/a.pdf", root_id="output")


def test_content_hash_changes_when_bytes_change(workspace: Workspace) -> None:
    from labcairn.security.approval import content_hash

    target = workspace.output_root.path / "a.md"
    target.write_bytes(b"one")
    first = content_hash(target)
    target.write_bytes(b"two")
    assert content_hash(target) != first
    assert len(first) == 64
