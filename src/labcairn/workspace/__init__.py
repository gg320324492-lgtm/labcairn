"""Selected roots and dedicated generated output.

A workspace is the place the user pointed at, plus what LabCairn makes inside
it. Three kinds of root, and they are not interchangeable:

* :attr:`Workspace.workspace_root` — the boundary the user selected.
* :attr:`Workspace.source_roots` — supplied material. Read-only.
* :attr:`Workspace.output_root` — this task's output area. The only writable
  place, and per-task so two tasks cannot overwrite each other's artifacts.

The ordering the package enforces, cheapest first:

1. :func:`~labcairn.security.paths.canonicalize` decides whether a path is
   admissible at all (traversal, symlink, junction, encoding, case);
2. :meth:`Workspace.path_in` re-canonicalises and requires a *named* root, so
   "read something in the workspace" cannot silently become "read something that
   is source";
3. :class:`~labcairn.workspace.readonly.SourceMaterial` refuses writes before
   any syscall;
4. :class:`~labcairn.workspace.outputs.TaskOutputArea` is the only writer, and
   it re-checks that it landed in an output root before creating a temp file.

Four checks for one write is not redundancy. Each catches a failure the others
do not: a caller that skips (2) reads output as evidence, a caller that skips
(3) corrupts a user's document, and a caller that skips (4) writes atomically
into the wrong place.
"""

from __future__ import annotations

from labcairn.workspace.outputs import (
    CountingWriteObserver,
    OutputRefusedError,
    TaskOutputArea,
    WriteOutcome,
    WriteReceipt,
)
from labcairn.workspace.readonly import (
    SourceIsReadOnlyError,
    SourceMaterial,
    bind_source_material,
    resolve_source_path,
)
from labcairn.workspace.roots import OUTPUT_DIR_NAME, Workspace, WorkspaceError

__all__ = [
    "OUTPUT_DIR_NAME",
    "CountingWriteObserver",
    "OutputRefusedError",
    "SourceIsReadOnlyError",
    "SourceMaterial",
    "TaskOutputArea",
    "Workspace",
    "WorkspaceError",
    "WriteOutcome",
    "WriteReceipt",
    "bind_source_material",
    "resolve_source_path",
]
