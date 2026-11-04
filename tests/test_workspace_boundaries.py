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
import inspect
import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from labcairn.core.ids import TaskId, new_id
from labcairn.papers import feedback as feedback_module
from labcairn.papers import replies as replies_module
from labcairn.papers import revisions as revisions_module
from labcairn.security.capabilities import (
    MAX_SOURCE_READ_BYTES,
    CapabilityId,
    FsReadArgs,
    SourceReadArgs,
    parse_args,
)
from labcairn.security.paths import PathRefusedError, RootKind
from labcairn.security.policy import Permission, PermissionPolicy, Rule
from labcairn.workspace.outputs import (
    CountingWriteObserver,
    OutputRefusedError,
    TaskOutputArea,
    WriteOutcome,
)
from labcairn.workspace.readonly import (
    MAX_SOURCE_READ_BYTES as DOOR_CEILING,
)
from labcairn.workspace.readonly import (
    SourceIsReadOnlyError,
    SourceMaterial,
)
from labcairn.workspace.roots import Workspace, WorkspaceError

pytestmark = pytest.mark.negative


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    root = tmp_path / "ws"
    sources = root / "sources"
    (sources / "papers").mkdir(parents=True)
    (sources / "papers" / "a.pdf").write_bytes(b"%PDF-1.4 a")
    return Workspace.bind(root, task_id=TaskId(new_id()), source_dirs=(sources,))


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
    first = Workspace.bind(root, task_id=TaskId(new_id()))
    second = Workspace.bind(root, task_id=TaskId(new_id()))
    assert first.output_root.path != second.output_root.path


def test_a_source_root_outside_the_selected_root_is_refused(tmp_path: Path) -> None:
    """A source the workspace does not contain is a root selection that failed."""
    ws = tmp_path / "ws"
    elsewhere = tmp_path / "elsewhere"
    ws.mkdir()
    elsewhere.mkdir()
    with pytest.raises(WorkspaceError, match="outside the selected workspace"):
        Workspace.bind(ws, task_id=TaskId(new_id()), source_dirs=(elsewhere,))


def test_binding_requires_an_existing_selected_root(tmp_path: Path) -> None:
    """No "create it and carry on": a root that had to be invented is not selected."""
    with pytest.raises(PathRefusedError):
        Workspace.bind(tmp_path / "never-created", task_id=TaskId(new_id()))


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


def _oversized(workspace: Workspace, *, size: int) -> str:
    """A source file whose **size** is *size*, with no bytes written to fill it.

    The ceiling is checked on ``stat``, so the arrangement needs a length and
    not a payload. Writing 96 MB to make a point about a number would make
    every run of this file pay for it.
    """
    path = workspace.selected_root / "sources" / "papers" / "oversized.csv"
    with path.open("wb") as handle:
        handle.seek(size - 1)
        handle.write(b"x")
    assert path.stat().st_size == size, "the arrangement must be the size it claims"
    return "papers/oversized.csv"


@pytest.mark.parametrize("door", ["read", "read_permitted"])
def test_a_file_over_the_ceiling_is_refused_by_both_read_doors(
    workspace: Workspace, source_id: str, door: str
) -> None:
    """One ceiling, and **both doors enforce it**.

    :meth:`SourceMaterial.read` and :meth:`SourceMaterial.read_permitted` are
    two doors onto the same byte. They once carried two defaults that could be
    moved apart, and one was moved: the manuscript ceiling was raised for the
    ingest path and only the door that path uses was raised with it, so the
    doors disagreed and a fixture parked between the two numbers stopped being
    refused. **A caller that reads through the door nobody tested is the case
    a witness has to cover.**
    """
    material = SourceMaterial(
        workspace, PermissionPolicy.from_rules([Rule(Permission.ALLOW, "**")])
    )
    key = _oversized(workspace, size=MAX_SOURCE_READ_BYTES + 1)

    with pytest.raises(SourceIsReadOnlyError) as raised:
        if door == "read":
            material.read(key, root_id=source_id)
        else:
            material.read_permitted(key, root_id=source_id, capability="source.inventory")

    assert "oversized.csv" in str(raised.value), "the refusal must name the file"
    assert str(MAX_SOURCE_READ_BYTES) in str(raised.value), "and name the ceiling it crossed"


def test_both_read_doors_default_to_the_one_ceiling(workspace: Workspace, source_id: str) -> None:
    """The two doors' defaults are **the same constant**, not two numbers that agree today.

    **Why the signature and not only the behaviour.** A refusal test at
    ceiling + 1 catches a default that was *raised*; it does not catch one that
    was *lowered*, because the smaller door still refuses. Reading the defaults
    binds the claim to the number it is about: change either one without the
    other and this goes red.
    """
    defaults = {
        name: inspect.signature(getattr(SourceMaterial, name)).parameters["max_bytes"].default
        for name in ("read", "read_permitted")
    }

    assert defaults == {
        "read": MAX_SOURCE_READ_BYTES,
        "read_permitted": MAX_SOURCE_READ_BYTES,
    }, f"the read doors carry two different ceilings: {defaults}"


def _literal_spellings_of_the_ceiling() -> dict[str, int]:
    """Every place in the product that **writes the ceiling as digits**.

    The scan is the point: a claim that a number is written once is not held by
    a behaviour test, because two identical literals behave identically right up
    until the day someone changes one of them.
    """
    src = Path(__file__).resolve().parents[1] / "src" / "labcairn"
    found: dict[str, int] = {}
    for path in sorted(src.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        hits = text.count("96_000_000") + text.count("96000000")
        if hits:
            found[path.relative_to(src).as_posix()] = hits
    return found


def test_the_ceiling_is_written_once_in_the_product() -> None:
    """The ceiling's digits are written in exactly two files, and both are named.

    **One is the definition and one is watched, not unified.**
    ``security/capabilities.py`` holds the number
    (:data:`~labcairn.security.capabilities.MAX_SOURCE_READ_BYTES`);
    ``papers/revisions.py`` still writes its own copy because that file is
    another window's lane and this work order was told not to edit it — so the
    copy is held by :func:`test_the_manuscript_readers_share_the_one_ceiling`
    rather than by an import. Naming the second file is what makes the witness
    fail for the property: a **third** spelling anywhere is this test going red,
    and it says which file to import instead.

    **The count is pinned in both files, not just the set.** A set assertion
    alone lets a second literal be added *inside* ``papers/revisions.py``, where
    nothing would notice — measured: with ``_DUPLICATE_CEILING_LITERAL =
    96_000_000`` added there, every witness in this file stayed green, because
    the set was unchanged and the value still equalled the ceiling. Two literals
    in one file are two places to move, so each allowed file is pinned to one.
    """
    spelled = _literal_spellings_of_the_ceiling()

    assert set(spelled) == {"security/capabilities.py", "papers/revisions.py"}, (
        f"the ceiling is written as digits in {spelled}; the definition belongs in "
        "security/capabilities.py and every reader should import it"
    )
    assert spelled["security/capabilities.py"] == 1, (
        "the ceiling's digits are written twice even in its own home"
    )
    assert spelled["papers/revisions.py"] == 1, (
        "papers/revisions.py carries more than one copy of the ceiling's digits; "
        "that file is watched rather than imported, so every extra literal there "
        "is another place a raise can miss"
    )


def test_the_manuscript_readers_share_the_one_ceiling() -> None:
    """The doors, the papers' size check and the ``source.read`` default are one value.

    **Identity, not equality, where the code imports the constant.** Two modules
    that each write ``96_000_000`` are equal forever until a raise touches one of
    them — which is the exact accident that left a fixture parked between two
    defaults, and the accident the remaining spellings still invite. So the
    readers that were brought onto the one definition are checked with ``is``:
    re-spelling the literal there keeps the values equal and still goes red.

    ``papers/revisions.py`` is checked by value only, because its literal is a
    lane this work order may not edit; that is the weakest link in the claim and
    the test says so rather than pretending otherwise.
    """
    readers = {
        "workspace.readonly re-export": DOOR_CEILING,
        "papers/feedback": feedback_module.MAX_MANUSCRIPT_BYTES,
        "papers/replies": replies_module.MAX_MANUSCRIPT_BYTES,
    }
    retyped = [name for name, value in readers.items() if value is not MAX_SOURCE_READ_BYTES]
    assert not retyped, (
        f"these spellings are re-typed literals, not imports of the one ceiling: {retyped}"
    )

    assert feedback_module.MAX_MANUSCRIPT_BYTES == revisions_module.MAX_MANUSCRIPT_BYTES, (
        "papers/revisions.py writes its own copy of the ceiling and it has drifted; "
        "import MAX_SOURCE_READ_BYTES there or raise both together"
    )

    unnamed = cast(SourceReadArgs, parse_args(CapabilityId.SOURCE_READ, {"path": "papers/a.docx"}))
    assert unnamed.max_bytes == MAX_SOURCE_READ_BYTES, (
        f"a source.read approval that names no bound carries {unnamed.max_bytes} while the "
        f"doors read up to {MAX_SOURCE_READ_BYTES}: the consent and the operation differ"
    )


def test_the_source_read_schema_admits_the_ceiling() -> None:
    """Every manuscript operation hands the ceiling to ``source.read`` — so it must fit.

    **Behavioural, not a metadata compare.** All seven ``consent.evaluate`` sites
    in ``papers/`` and ``guidance/`` pass ``arguments={"max_bytes": ceiling}``,
    and ``consent.evaluate`` validates that dict against the closed model. A
    ceiling above the model's bound is therefore not a cosmetic disagreement: it
    refuses every manuscript operation with ``ARGUMENTS_INVALID`` before a byte
    is read. Lowering ``le`` under the ceiling, or raising the ceiling over it,
    both go red here — which is the day the next material measurement is the
    change that breaks the chain, and the reason the number is re-measured and
    not carried forward.
    """
    admitted = cast(
        SourceReadArgs,
        parse_args(
            CapabilityId.SOURCE_READ,
            {"path": "papers/a.docx", "max_bytes": MAX_SOURCE_READ_BYTES},
        ),
    )
    assert admitted.max_bytes == MAX_SOURCE_READ_BYTES

    le = next(m.le for m in SourceReadArgs.model_fields["max_bytes"].metadata if hasattr(m, "le"))
    assert le > MAX_SOURCE_READ_BYTES, (
        f"source.read may be approved up to {le} but the ceiling is {MAX_SOURCE_READ_BYTES}: "
        "there is no room left to raise the ceiling without first raising the bound"
    )

    with pytest.raises(ValidationError):
        parse_args(CapabilityId.SOURCE_READ, {"path": "papers/a.docx", "max_bytes": le + 1})


def test_an_artefact_read_may_not_be_approved_at_the_manuscript_ceiling() -> None:
    """``fs.read`` is a **different question**, and the split is held on purpose.

    The manuscript ceiling bounds one read of *supplied* material. ``fs.read``
    bounds one read of an artefact the product wrote itself, and its
    ``max_bytes`` is the only approved bound in the registry that is read back
    and enforced (:func:`labcairn.application.artifacts.read_artifact`). Measured
    2026-11-03: no call site feeds the manuscript ceiling to ``fs.read`` — the
    papers send it to ``source.read``, whose bound is 512 MB — so the 64 MB here
    refused nothing today, and ``docs/RELEASE-NOTES.md`` §2.23 said so while
    describing the mechanism backwards.

    **This is the witness against the tidy-up.** Unifying the two numbers makes
    this red, because a supplied manuscript's ceiling is not a licence to pull
    that many artefact bytes into memory on one ``fs.read``; if the bound is
    genuinely to move, that is a decision about artefacts and it should say so.
    """
    field = FsReadArgs.model_fields["max_bytes"]
    assert field.default != MAX_SOURCE_READ_BYTES, (
        "the artefact read default was joined to the manuscript ceiling; they answer "
        "different questions and read_artifact enforces this one"
    )

    with pytest.raises(ValidationError):
        parse_args(
            CapabilityId.FS_READ,
            {"path": "out/report.pdf", "max_bytes": MAX_SOURCE_READ_BYTES},
        )


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
