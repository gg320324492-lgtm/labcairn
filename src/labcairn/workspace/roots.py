"""Binding a workspace: which roots exist, and what each one is *for*.

``docs/ARCHITECTURE.md`` states the first privacy invariant as *"Workspace root
must be explicitly selected"*. Explicit selection is the whole of this module:
there is no default root, no "current directory", no environment variable and no
inference from where the process was started. If nobody named a root, nothing is
reachable, and :func:`bind_workspace` fails rather than falling back.

Three roots, three different jobs
--------------------------------
* **workspace** — the directory the user selected. The outermost boundary. It
  is *not* itself writable by anything: every capability that writes declares
  ``root_kinds={"output"}``, and no output capability addresses the workspace
  root directly.
* **source** — supplied material, one root per directory the user pointed at.
  Read-only by construction: the capability registry refuses a write capability
  aimed here, so read-only is a property of the type system rather than of
  anyone remembering a rule.
* **output** — a dedicated directory for **one task**, created under
  ``<workspace>/output/<task_id>/``. Per-task rather than per-workspace on
  purpose: two tasks must not be able to overwrite each other's artifacts, and a
  shared output directory would make "did this task touch that file" a question
  the filesystem cannot answer.

Nesting is allowed and resolved by specificity
---------------------------------------------
A workspace root normally *contains* its source and output roots.
:meth:`Workspace.canonicalize` attributes a path to the **most specific** root
that contains it, so a file under ``sources/`` is governed by the source root's
rules even though the workspace root also contains it. That is what lets a
read-only guarantee apply to the subtree without denying the whole workspace.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from labcairn.core.ids import TaskId
from labcairn.security.paths import (
    AllowedRoot,
    CanonicalPath,
    PathRefusedError,
    PathRejection,
    RootKind,
    bind_root,
    canonicalize,
)

#: Directory name, under the selected workspace, holding every task's output.
OUTPUT_DIR_NAME = "output"


class WorkspaceError(ValueError):
    """The workspace could not be bound, or a path could not be admitted."""


@dataclass(frozen=True, slots=True)
class Workspace:
    """An explicitly selected root and the roots derived from it."""

    selected_root: Path
    task_id: TaskId
    roots: tuple[AllowedRoot, ...]

    # -- construction -------------------------------------------------------

    @classmethod
    def bind(
        cls,
        selected_root: Path,
        *,
        task_id: TaskId,
        source_dirs: tuple[Path, ...] = (),
    ) -> Workspace:
        """Bind a workspace around an explicitly selected directory.

        :param selected_root: the directory the user chose. Resolved strictly;
            if it does not exist, this raises. There is no "create it and
            carry on", because a root that had to be invented is not one the
            user selected.
        :param task_id: whose output area this is. Every task gets its own.
        :param source_dirs: directories of supplied material. Each is resolved
            and must sit **inside** the selected root — a source root outside
            the workspace would be a path the user's root selection does not
            actually govern.
        :raises PathRefusedError: if any root cannot be canonicalised.
        """
        workspace_root = bind_root("workspace", selected_root, RootKind.OUTPUT)

        roots: list[AllowedRoot] = [workspace_root]

        for index, source_dir in enumerate(source_dirs):
            real_source = bind_root(f"source:{index}", source_dir, RootKind.SOURCE)
            if not _contains(workspace_root.path, real_source.path):
                raise WorkspaceError(
                    f"source directory {real_source.path} is outside the selected "
                    f"workspace {workspace_root.path}. A source root the workspace "
                    f"does not contain is a root the user's selection does not govern."
                )
            roots.append(real_source)

        output_dir = workspace_root.path / OUTPUT_DIR_NAME / str(task_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        roots.append(bind_root("output", output_dir, RootKind.OUTPUT))

        return cls(selected_root=workspace_root.path, task_id=task_id, roots=tuple(roots))

    # -- roots --------------------------------------------------------------

    @property
    def workspace_root(self) -> AllowedRoot:
        return self.root_for("workspace")

    @property
    def output_root(self) -> AllowedRoot:
        return self.root_for("output")

    @property
    def source_roots(self) -> tuple[AllowedRoot, ...]:
        return tuple(r for r in self.roots if r.kind is RootKind.SOURCE)

    def root_for(self, root_id: str) -> AllowedRoot:
        """The bound root with this id. Public: callers name their root."""
        for root in self.roots:
            if root.root_id == root_id:
                return root
        msg = f"no root {root_id!r} is bound to this workspace"
        raise WorkspaceError(msg)

    # -- the boundary -------------------------------------------------------

    def path_in(self, key: str, root_id: str) -> CanonicalPath:
        """Canonicalise ``key`` as a path inside the named root.

        The one correct way to turn a resource key into a checkable path. It
        does not assume the key is well-formed — it canonicalises the *result*,
        so a key that escaped its root is caught by the same machinery that
        catches a path from a model.
        """
        return self.canonicalize_in(self.root_for(root_id).path / Path(*key.split("/")), root_id)

    def canonicalize(self, declared: str | Path) -> CanonicalPath:
        """Admit a path, or refuse it.

        The whole of ADR-0003 §C4's path half, applied. A relative path is
        refused rather than resolved against the process working directory,
        because that is the documented bypass deepagents has (ADR-0003 §A5) and
        because a caller that means "inside my output area" should say so.
        """
        try:
            return canonicalize(declared, self.roots)
        except PathRefusedError as refused:
            raise WorkspaceError(f"{declared!r} refused: {refused.rejection.value}") from refused

    def canonicalize_in(self, declared: str | Path, root_id: str) -> CanonicalPath:
        """Admit a path that must land in one named root.

        Stricter than :meth:`canonicalize`: the resolved path must belong to
        ``root_id``. Used where "some allowed root" is too weak — reading source
        material must read *source*, not merely something inside the workspace.
        """
        path = self.canonicalize(declared)
        if path.root_id != root_id:
            raise WorkspaceError(
                f"{declared!r} resolved into root {path.root_id!r}, but {root_id!r} was required"
            )
        return path

    def resolve_key(self, key: str, *, root_id: str | None = None) -> Path:
        """Map a canonical resource key back to a real path, re-checking.

        **Re-canonicalises rather than joining.** A key was canonical when it was
        minted; the tree underneath may have changed since — a directory could
        have been replaced with a junction pointing somewhere else. Re-running
        the full check closes that window as far as it can be closed in-process.

        :param root_id: the root the key belongs to. Preferred, and what every
            caller inside this package passes, because the key is only
            unambiguous relative to a known root. When omitted the roots are
            tried most-specific-first and the first that round-trips wins.

        The residual race — between this check and the ``open()`` that follows —
        is real and is documented in the module docstring of
        :mod:`labcairn.security.paths`. Closing it completely needs an
        OS-level handle-relative open, which Phase 1 does not claim.
        """
        if root_id is not None:
            root = self.root_for(root_id)
            # canonicalize_in, not canonicalize: naming a root must *enforce*
            # it. Joining onto the output root and merely re-checking would let
            # `../sources/a.pdf` resolve into the source root and be returned as
            # if it were output, which is precisely what the named root exists
            # to prevent.
            return self.path_in(key, root_id).real_path

        # Most specific first, so `output/<task>` is tried before the workspace
        # root and a key that exists under both resolves to the tighter one.
        for root in sorted(self.roots, key=lambda r: len(r.path.parts), reverse=True):
            try:
                return self.canonicalize(root.path / Path(*key.split("/"))).real_path
            except WorkspaceError:
                continue
        raise WorkspaceError(f"resource key {key!r} resolves under no bound root")


def _contains(parent: Path, child: Path) -> bool:
    try:
        return child.is_relative_to(parent)
    except ValueError:  # different drives on Windows
        return False


__all__ = [
    "OUTPUT_DIR_NAME",
    "AllowedRoot",
    "CanonicalPath",
    "PathRejection",
    "RootKind",
    "Workspace",
    "WorkspaceError",
]
