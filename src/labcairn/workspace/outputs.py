"""The only place in LabCairn that writes a file.

Two guarantees, and both are about what happens when something goes wrong
halfway.

**Writes go to the task output area and nowhere else.** :meth:`TaskOutputArea.write`
re-canonicalises the target and refuses unless it resolves into an
:class:`~labcairn.security.paths.RootKind.OUTPUT` root. This is the choke point
that makes "no irreversible change to supplied source data" (LC-P1-04's
acceptance) structural rather than a matter of every call site remembering.

**Writes are atomic where the platform allows it.** The bytes go to a temporary
file in the *same directory* as the target, are flushed and ``fsync``-ed, and
are then moved into place with :func:`os.replace`. Same-directory matters:
``os.replace`` is only atomic within a volume, and a temp file in the system temp
directory would silently give up that guarantee. After a crash the target is
therefore either the old content or the new content, never a half-written file
— which is what lets LC-P1-06's reconciliation probe find a matching content
hash and conclude *landed* rather than guessing.

What atomicity does **not** give
--------------------------------
A crash between the replace and the database commit still leaves the file
written and the row uncommitted. That is ADR-0003 §C2's ``UNCERTAIN`` state, and
it is why the write counter matters: ``test_crash_after_write_before_commit``
needs to prove *no second write occurred*, and that proof needs a counter that
survives the process. :class:`WriteObserver` is that hook — injected rather than
global, so tests get their own and product code has none.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from labcairn.core.ids import new_id
from labcairn.security.approval import content_hash
from labcairn.security.paths import RootKind
from labcairn.workspace.roots import Workspace


class WriteOutcome(StrEnum):
    """What a write did. Recorded so a receipt can state it, not imply it."""

    CREATED = "created"
    REPLACED = "replaced"


class OutputRefusedError(PermissionError):
    """A write aimed somewhere that is not a task output area."""


@dataclass(frozen=True, slots=True)
class WriteReceipt:
    """Evidence that a write landed, in the shape LC-P1-06 reconciles against.

    ``content_hash`` is over the bytes that were written, so a reconciliation
    probe that finds the file with this hash can conclude the effect landed
    rather than infer it from an mtime.
    """

    resource_key: str
    absolute_path: Path
    content_hash: str
    size_bytes: int
    outcome: WriteOutcome


#: Injected hook for counting and inspecting writes.
#:
#: A parameter rather than a module-level counter because a global would be
#: shared across tests and would make "the write counter is still 1" depend on
#: test ordering — the exact nondeterminism the project's determinism rule
#: forbids. Called **once per accepted write**, with the resource key, the
#: absolute path and the byte count.
WriteObserver = Callable[[str, Path, int], None]


class CountingWriteObserver:
    """The observer LC-P1-06's crash tests use.

    Counts every write it is told about and remembers the keys, so a test can
    assert both "a second write did not happen" and "the one that did was the
    one I expected". A single ``__call__`` rather than an ``on_write`` protocol
    method: two entry points for one event is how an implementation ends up
    calling one while a test reads the other, which is exactly the bug that
    made an earlier version of this file silently count zero writes.
    """

    def __init__(self) -> None:
        self.attempts = 0
        self.keys: list[str] = []
        self.sizes: list[int] = []

    def __call__(self, resource_key: str, path: Path, size: int) -> None:
        del path
        self.attempts += 1
        self.keys.append(resource_key)
        self.sizes.append(size)

    @property
    def commits(self) -> int:
        """Alias kept for the crash-test vocabulary in ADR-0003 §C2.

        A write reported here has already been accepted by the output area, so
        for an observer injected as a callback the two are the same number.
        """
        return self.attempts


class TaskOutputArea:
    """The dedicated output directory for exactly one task."""

    def __init__(
        self,
        workspace: Workspace,
        *,
        observers: tuple[WriteObserver, ...] = (),
    ) -> None:
        self._workspace = workspace
        self._observers = observers

    @property
    def root(self) -> Path:
        return self._workspace.output_root.path

    def write(self, key: str, data: bytes, *, fsync: bool = True) -> WriteReceipt:
        """Atomically write *data* to ``key`` inside the task output area.

        The sequence, and why each step is where it is:

        1. **canonicalise the target first.** Before any temporary file exists.
           If this raises, nothing was created — not even a stray temp file that
           a later ``list_dir`` would show.
        2. write to a temp file in the target's own directory,
        3. flush and ``fsync`` so the bytes are durable before they are visible
           under the real name,
        4. :func:`os.replace`, which is atomic within a volume,
        5. clean up the temp file on any failure, so a crashed write leaves
           either the old file or the new one.

        :param fsync: on by default. Disabling it is for a caller writing a
            large intermediate that will be rewritten; it is not the default
            because a durability bug that only shows up after a power loss is
            close to undebuggable.
        """
        target = self._workspace.path_in(key, self._workspace.output_root.root_id)
        if target.root_kind is not RootKind.OUTPUT:
            raise OutputRefusedError(
                f"{key!r} resolved into a {target.root_kind.value} root; writes are "
                f"only permitted into the task output area."
            )

        destination = target.real_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        existed = destination.exists()

        for observer in self._observers:
            observer(target.resolved_key, destination, len(data))

        temp = destination.parent / f".lc-write-{new_id().hex}.tmp"
        try:
            with temp.open("xb") as handle:
                handle.write(data)
                handle.flush()
                if fsync:
                    os.fsync(handle.fileno())
            # Path.replace is os.replace: a same-directory rename, atomic
            # within the volume. Same-directory is why the temp file is a
            # sibling of the target rather than a system temp file.
            temp.replace(destination)
        except BaseException:
            # A crash or an error here must not leave the temp file behind: a
            # leftover is a half-written artifact that a later listing would
            # present as if it were real output.
            temp.unlink(missing_ok=True)
            raise

        if fsync:
            self._fsync_directory(destination.parent)

        return WriteReceipt(
            resource_key=target.resolved_key,
            absolute_path=destination,
            content_hash=content_hash(destination),
            size_bytes=len(data),
            outcome=WriteOutcome.REPLACED if existed else WriteOutcome.CREATED,
        )

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        """Best-effort directory fsync so the rename itself is durable.

        Windows cannot open a directory as a file, so this is a no-op there and
        the durability guarantee comes from ``os.replace`` alone. That is stated
        rather than hidden: on Windows an fsync-precise rename is not available
        to an unprivileged process, and pretending otherwise would be a claim
        the code cannot keep.
        """
        try:
            fd = os.open(directory, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(fd)
        except OSError:
            pass
        finally:
            os.close(fd)


__all__ = [
    "CountingWriteObserver",
    "OutputRefusedError",
    "TaskOutputArea",
    "WriteObserver",
    "WriteOutcome",
    "WriteReceipt",
]
