"""What every operation is given, and what it addresses.

The application layer takes one :class:`ApplicationContext` and reads and
writes everything through it. Three things live in it, and the third is the
one that makes the layer a seam rather than a convenience:

* the **workspace**, which names the task and the roots its resources may live
  in. A resource key is meaningless without the root it is relative to, so the
  layer never accepts a bare path;
* the **store**, which is the task authority and the only way to the database;
* the **policy** and the **approval ledger**, which together are the
  capability model every operation goes through.

A surface that holds one of these can call the layer; a surface that holds
none of them cannot reach the task state at all, because the layer is the only
thing that reads it.

The resources
-------------

An operation does not name a filesystem path. It names a **resource**: a
canonical key inside a named root, and the layer resolves that into the
:class:`~labcairn.security.paths.CanonicalPath` the policy reasons about.

Three kinds of resource are used, and the choice of kind is not free:

* **the task's own area** — the workspace's output directory, where every
  task's outputs live. The task's area cannot name *itself* as a resource key
  (a directory that is a root reduces to the root, and a key that names the
  container it sits in is refused), so the operations that read a task's own
  record are bound to the directory that holds it;
* **a file inside the workspace**, addressed by its workspace-relative path.
  An artefact's receipt names one, and the ledger's own ``relative_path`` is
  workspace-relative, so this is the spelling the receipts use;
* **a file inside a source root**, addressed by its key in that root. Source
  material is read-only by construction, and the capability registry refuses a
  write capability aimed at one whatever the policy says.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.core.ids import TaskId
from labcairn.db.repository import TaskStore, UnknownTaskError
from labcairn.security.approval import ApprovalLedger
from labcairn.security.paths import CanonicalPath
from labcairn.security.policy import PermissionPolicy
from labcairn.workspace.roots import OUTPUT_DIR_NAME, Workspace, WorkspaceError

#: The root the task's own area is addressed in. The workspace root, because
#: the output root *is* the task's area and cannot name itself.
TASK_AREA_ROOT = "workspace"

#: The key the task's own area is addressed by, in :data:`TASK_AREA_ROOT`.
TASK_AREA_KEY = OUTPUT_DIR_NAME


@dataclass(frozen=True, slots=True)
class ApplicationContext:
    """Everything an operation is given.

    Immutable, so a context cannot be swapped underneath an operation in
    flight — the policy a decision was made under is the policy the operation
    was authorised against.
    """

    workspace: Workspace
    store: TaskStore
    policy: PermissionPolicy
    ledger: ApprovalLedger

    @property
    def task_id(self) -> TaskId:
        """The task this context is about."""
        return self.workspace.task_id

    # -- the resources ------------------------------------------------------- #

    def task_area(self) -> CanonicalPath:
        """The task's own area, as the workspace's output directory.

        Named once, here, because every operation that reads the task's own
        record must name the *same* resource: two spellings of "the task's
        area" would be two things for a policy rule to match, and a rule
        written against one of them would silently not cover the other.
        """
        return self.resource_in(TASK_AREA_ROOT, TASK_AREA_KEY)

    def resource_in(self, root_id: str, key: str) -> CanonicalPath:
        """A resource addressed by its key inside a named root.

        :raises ApplicationRefusedError: the key could not be admitted into
            that root. A path that cannot be canonicalised is a deny and not an
            ask (ADR-0003 C4), so it is refused here rather than passed on to
            the policy as something it cannot judge.
        """
        try:
            return self.workspace.path_in(key, root_id)
        except WorkspaceError as error:
            raise ApplicationRefusedError(
                ApplicationRefusal.PATH_REFUSED,
                f"the resource {key!r} was refused in root {root_id!r}: {error}",
            ) from error

    def resource_for(self, relative_path: str) -> CanonicalPath:
        """A resource addressed by its workspace-relative path.

        The spelling an artefact receipt carries. The path is resolved against
        the workspace's roots, so the root it lands in — and therefore whether
        it is source material or generated output — is decided by the
        filesystem rather than by the caller.
        """
        candidate = self.workspace.selected_root.joinpath(*relative_path.split("/"))
        try:
            return self.workspace.canonicalize(candidate)
        except WorkspaceError as error:
            raise ApplicationRefusedError(
                ApplicationRefusal.PATH_REFUSED,
                f"the path {relative_path!r} was refused: {error}",
            ) from error


__all__ = [
    "TASK_AREA_KEY",
    "TASK_AREA_ROOT",
    "ApplicationContext",
    "store_refusals",
]


@contextmanager
def store_refusals() -> Iterator[None]:
    """Translate the store's own refusals into this layer's one.

    The store raises :class:`~labcairn.db.repository.UnknownTaskError` for a
    task that does not exist — a rule it states for itself in
    :meth:`~labcairn.db.repository.UnitOfWork.task_row`, where the reasoning is
    that "a unit of work without a Task is a caller bug and ``None`` would push
    that check into every call site where nobody writes it". The layer keeps
    the rule and changes the spelling, so a surface catches one exception and
    not two.
    """
    try:
        yield
    except UnknownTaskError as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.TASK_NOT_FOUND,
            str(error),
        ) from error
