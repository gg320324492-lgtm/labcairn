"""Supplied source material, and the fact that nothing here can write it.

ADR-0003 §C7 names the test that matters here:
``test_source_root_is_read_only_before_any_syscall`` — *assert refused **and**,
via a filesystem spy, that zero write syscalls were attempted*. The "and" is the
substance. A refusal that happens after opening the file for writing has already
truncated it.

So read-only is enforced in three places, and this module is the one that makes
the *last* line of defence real:

1. the capability registry declares ``root_kinds={"source"}`` for read
   capabilities and excludes ``source`` from every write capability, so policy
   refuses before this code runs;
2. :meth:`SourceMaterial.write` re-checks the resolved path against a read-only
   root and raises **before opening anything**;
3. even if 1 and 2 were bypassed, the only write primitive in this package
   (:mod:`labcairn.workspace.outputs`) requires a
   :class:`~labcairn.security.paths.RootKind.OUTPUT` root.

Point 3 is why :meth:`SourceMaterial.write` refuses on the *root kind* rather
than on a path comparison: the kind is a property established once, at binding
time, and it cannot be re-derived wrongly from a string at call time.

Listing filters rather than refuses
-----------------------------------
:meth:`SourceMaterial.list_dir` applies
:meth:`~labcairn.security.policy.PermissionPolicy.filter_listing`, so a denied
entry is absent from the result rather than the whole call failing. ADR-0003 §C5
is explicit that this is the difference between a model learning "something is
there but I may not see it" and a model learning nothing at all.
"""

from __future__ import annotations

import fnmatch
import os
from collections.abc import Callable
from pathlib import Path

from labcairn.security.approval import content_hash
from labcairn.security.paths import RootKind
from labcairn.security.policy import PermissionPolicy
from labcairn.workspace.roots import OUTPUT_DIR_NAME, Workspace


class SourceIsReadOnlyError(PermissionError):
    """An attempt to write supplied source material.

    A :class:`PermissionError` rather than a ``ValueError`` because this is a
    policy outcome, not a malformed argument, and a caller that handles path
    errors by converting them to a tool error should not swallow this one.
    """


class SourceMaterial:
    """Read-only access to the directories a user supplied."""

    def __init__(self, workspace: Workspace, policy: PermissionPolicy) -> None:
        self._workspace = workspace
        self._policy = policy

    @property
    def workspace(self) -> Workspace:
        return self._workspace

    def read(self, key: str, *, root_id: str, max_bytes: int = 64_000_000) -> bytes:
        """Read a source file, re-checking containment on the way.

        ``root_id`` is required rather than optional. "Read something inside the
        workspace" is the wrong question for source material — the right one is
        "read something that is *source*", and making the caller name the root
        is what stops an output file being served as if it were evidence.
        """
        path = self._require_source(key, root_id)
        size = path.stat().st_size
        if size > max_bytes:
            msg = f"{key} is {size} bytes, over the {max_bytes} byte read limit"
            raise SourceIsReadOnlyError(msg)
        return path.read_bytes()

    def hash_of(self, key: str, *, root_id: str) -> str:
        """Content hash of a source file, for an approval's ``depends_on``."""
        return content_hash(self._require_source(key, root_id))

    def list_dir(self, key: str, *, root_id: str, pattern: str = "*") -> tuple[str, ...]:
        """List a source directory with denied entries filtered out.

        Entries are returned as resource keys relative to the *workspace*, not
        as absolute paths, so a caller cannot accidentally use one where a
        canonical key is required — or hand it to something that will join it
        onto a different root.
        """
        root = self._workspace.root_for(root_id)
        directory = self._require_source(key, root_id) if key else root.path
        if not directory.is_dir():
            msg = f"{key or root_id} is not a directory"
            raise NotADirectoryError(msg)

        try:
            names = sorted(entry.name for entry in os.scandir(directory))
        except OSError:
            return ()

        prefix = f"{key}/" if key else ""
        keys = [f"{prefix}{name}" for name in names if fnmatch.fnmatchcase(name, pattern)]

        return self._policy.filter_listing(
            keys,
            task_id=self._workspace.task_id,
            capability="source.inventory",
            root_id=root_id,
            root_kind=RootKind.SOURCE,
            real_root=directory,
        )

    def write(self, key: str, data: bytes, *, root_id: str) -> None:
        """Refuse. Always. Before any syscall.

        This method exists to make the refusal *reachable and testable* rather
        than merely implied by the registry. It does not open, truncate, create,
        touch or stat the target — the first thing it does is raise.
        ``test_source_root_is_read_only_before_any_syscall`` patches every write
        primitive in the standard library and asserts none was called.

        The unused arguments are part of the signature on purpose: this is the
        method a wrong caller reaches for, and it must accept the call shape it
        would otherwise have used so that the refusal is what stops them.
        """
        del data, root_id  # named in the message, never used to touch the disk
        raise SourceIsReadOnlyError(
            f"source material is read-only: {key!r}. Supplied source data is never "
            f"written, moved or deleted by LabCairn; outputs go to the dedicated "
            f"task output area under {OUTPUT_DIR_NAME}/."
        )

    def delete(self, key: str, *, root_id: str) -> None:
        """Refuse, by the same mechanism as :meth:`write`."""
        del root_id
        raise SourceIsReadOnlyError(f"source material is read-only: {key!r} cannot be deleted.")

    # -- internals ----------------------------------------------------------

    def _require_source(self, key: str, root_id: str) -> Path:
        """Canonicalise and confirm the path really landed in a source root.

        :meth:`~labcairn.workspace.roots.Workspace.canonicalize_in` performs
        both halves. The check that matters is the one on the *resolved* root:
        a source root containing a junction to the output area resolves into the
        output root and is refused, even though the declared path looked like
        plain source material.
        """
        path = self._workspace.path_in(key, root_id)
        if path.root_kind is not RootKind.SOURCE:
            raise SourceIsReadOnlyError(
                f"{key!r} resolved into a {path.root_kind.value} root, not a source root"
            )
        return path.real_path


def bind_source_material(
    workspace: Workspace,
    policy: PermissionPolicy,
) -> SourceMaterial:
    """Build the read-only view for a bound workspace."""
    return SourceMaterial(workspace, policy)


def resolve_source_path(workspace: Workspace, *, root_id: str) -> Callable[[str], Path]:
    """A ``resolve`` callable for :func:`~labcairn.security.approval.sources_intact`.

    Returns the callable rather than being one, so a caller cannot bind the
    wrong workspace by accident. It re-canonicalises, which is what lets
    ``depends_on`` notice that a source file was replaced by a symlink as well
    as that its bytes changed.
    """

    def _resolve(source_key: str) -> Path:
        return workspace.resolve_key(source_key, root_id=root_id)

    return _resolve


__all__ = [
    "SourceIsReadOnlyError",
    "SourceMaterial",
    "bind_source_material",
    "resolve_source_path",
]
