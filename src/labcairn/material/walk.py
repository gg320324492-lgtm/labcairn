"""Ingesting a workspace: walking source roots and persisting what each file yields.

LC-P1-08's last piece. The adapters read bytes; this connects them to a real
workspace so the whole path -- walk, read, extract, disclose, store -- runs
against real material.

**It walks through :class:`SourceMaterial`, never the filesystem.** Reading
directly would bypass the permission boundary entirely, so every listing and
read here goes through it.

**A denied subtree is invisible here, and that took two fixes to be true.**
Review demonstrated that a **symlink inside a permitted directory, pointing
into a denied one, was followed**: with ``DENY source.inventory private/**``,
``read("public/hop/secret.md")`` where ``public/hop -> private`` returned
the denied file's bytes, and this walk ingested them. Two causes, both in the
boundary rather than here -- ``policy.filter_listing`` matched only the
declared spelling, and ``SourceMaterial.read`` never consulted the policy --
and this walk is what turned the gap into persisted, searchable rows.

Both are now closed. The listing evaluates the policy on the **canonical**
entry, and the read does the same before opening, so neither depends on the
other being right. ``read_permitted`` is the protected read;
``read`` remains the unchecked primitive it always was, and says so.

One :class:`~labcairn.workspace.readonly.SourceMaterial` read and one
:func:`~labcairn.material.ingest.ingest_into_store` per file, each in its own
transaction, so a file that fails its constraints does not roll back the
files already ingested. That is a deliberate choice: a workspace with one
corrupt PDF should still be inventoried, and the failure is recorded on that
file rather than stopping the walk.

**The path it records is the workspace-relative one.** ``Source.relative_path``
is workspace-relative -- where the material is measured from the *workspace*
root -- and the walk is handed a **root-relative** key. Recording the key as
it stands puts the row in the wrong root, where the ``source.inventory``
capability refuses it, and makes two source roots holding a file of the same
name collide on the ledger's UNIQUE path. The source root's own place in the
workspace is the prefix that turns one spelling into the other.

The source id is deliberately **not** derived from that prefix: the id is a
function of the root and the root-relative key, so a material keeps its
identity across the change, and the text and the hash the ledger already
recorded against that id stay attached to it.

Materials are inventoried even when no adapter claims their format -- a
``.zip`` or a format Phase 1 cannot address is a *recorded fact about the
workspace*, distinct from a file that was never seen.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any

from labcairn.material.ingest import IngestOutcome, ingest_into_store
from labcairn.security.paths import AllowedRoot
from labcairn.workspace.readonly import SourceMaterial
from labcairn.workspace.roots import Workspace

__all__ = ["WalkReport", "ingest_workspace"]

#: Bound on directory depth, so a symlink loop or a pathological tree cannot
#: make the walk unbounded.
#:
#: Hitting it **truncates silently** -- ``_walk`` returns what it has and
#: ``WalkReport`` has no field for "there was more". An earlier comment here
#: claimed the bound was "reported rather than silently truncating", which was
#: false in the same file that needed it to be true. Fixing it properly means a
#: `truncated` field on the report; until then the comment says what happens.
_MAX_DEPTH = 16


@dataclass
class WalkReport:
    """What a workspace walk did, per file and in total."""

    outcomes: tuple[IngestOutcome, ...] = ()
    #: Files the walk could not read or store, and why. The key is the
    #: **root-relative** one the walk was handed, not the workspace-relative
    #: path the ledger holds: the report names what the walk was given.
    failures: tuple[tuple[str, str], ...] = ()
    #: Files whose format has no adapter: inventoried and hashed, not extracted.
    skipped: tuple[str, ...] = ()

    @property
    def source_ids(self) -> tuple[str, ...]:
        return tuple(o.material.source.source_id for o in self.outcomes)

    @property
    def texts_written(self) -> int:
        return sum(o.text_rows_written for o in self.outcomes)

    @property
    def problems_written(self) -> int:
        return sum(o.problem_rows_written for o in self.outcomes)


def ingest_workspace(
    session: Any,
    material: SourceMaterial,
    *,
    ingested_at: datetime,
    max_files: int | None = None,
) -> WalkReport:
    """Ingest every readable source file under the workspace's source roots.

    One transaction per file. A file that raises -- an unreadable container, a
    constraint the store refuses -- is recorded in ``failures`` and the walk
    continues, so one bad file does not leave the workspace half-inventoried
    with no record of why.
    """
    outcomes: list[IngestOutcome] = []
    failures: list[tuple[str, str]] = []
    skipped: list[str] = []

    for root in material.workspace.source_roots:
        root_id = root.root_id
        # The ledger's contract is a **workspace-relative** path, and the key
        # the walk is handed is **root-relative**. Where the root itself sits
        # in the workspace is what turns one into the other, and it is the
        # same for every file under that root.
        prefix = _the_workspace_prefix(material.workspace, root)
        # Per root, not shared. ``list_dir`` returns **root-relative** keys, so
        # two roots each holding ``notes.md`` produce the same string and a
        # shared ``seen`` silently swallowed the second file.
        seen: set[str] = set()
        for key in _walk(material, root_id=root_id, max_files=max_files, seen=seen):
            try:
                # read_permitted, not read: the listing already refuses a
                # denied entry, but a listing entry is a *name* and a name
                # can be a symlink. Evaluating the policy on the canonical
                # entry before reading is the second of the two checks, and
                # the one that does not depend on the listing being right.
                data = material.read_permitted(key, root_id=root_id, capability="source.inventory")
            except Exception as exc:
                failures.append((key, f"{type(exc).__name__}: {exc}"))
                continue
            try:
                outcome = ingest_into_store(
                    session,
                    data,
                    relative_path=f"{prefix}/{key}" if prefix else key,
                    display_name=key.rsplit("/", 1)[-1],
                    ingested_at=ingested_at,
                    # Stable across content changes, unlike the
                    # content-derived default. ``sources.relative_path`` is
                    # UNIQUE, so a content-derived id made every re-walk of an
                    # *edited* file a permanent IntegrityError, leaving the
                    # recorded hash and text frozen at the first version -- and
                    # ADR-0004 A2's drift detection nothing to detect against.
                    #
                    # Derived from the **root-relative** key, and that is not
                    # an accident: the ids are already recorded in the ledger
                    # for material ingested before the path was fixed, and an
                    # id that moved would orphan the text and the hash
                    # recorded against it.
                    source_id=_stable_source_id(root_id, key),
                )
            except Exception as exc:
                session.rollback()
                failures.append((key, f"{type(exc).__name__}: {exc}"))
                continue
            if outcome.material.source.kind.value == "other":
                skipped.append(key)
            outcomes.append(outcome)

    return WalkReport(
        outcomes=tuple(outcomes),
        failures=tuple(failures),
        skipped=tuple(skipped),
    )


def _walk(
    material: SourceMaterial,
    *,
    root_id: str,
    max_files: int | None,
    seen: set[str],
    depth: int = 0,
    key: str = "",
) -> list[str]:
    """Depth-first list of file keys, directories recursed, seen-keys deduped.

    ``seen`` is **per root**, which is what the caller passes. It was
    previously shared across roots on the reasoning that a material reachable
    from two roots should be ingested once -- but ``list_dir`` keys are
    root-relative, so two roots each holding ``notes.md`` produce the same
    string and the shared set silently swallowed one.

    Nothing dedups across roots, and this is the accurate statement of it: the
    keys are **root-relative**, so two roots each holding ``notes.md`` produce
    the same string, and each root is walked under its own ``seen``. An
    earlier version of this docstring claimed the workspace had a
    ``cross_root`` refusal doing the work. It does not -- ``CROSS_ROOT`` is a
    denial reason in ``security/paths.py`` that ``list_dir`` never consults --
    and a comment naming a safety net that is not there is worse than no
    comment, because it is read as one.

    The two roots' files are kept apart by the path they are **recorded**
    under, not by this walk: the ledger's path is workspace-relative, so the
    same file name under two roots is two different rows.
    """
    if max_files is not None and len(seen) >= max_files:
        return []
    if depth > _MAX_DEPTH:
        return []
    try:
        entries = material.list_dir(key, root_id=root_id)
    except Exception:
        return []

    files: list[str] = []
    for entry in entries:
        if entry in seen:
            continue
        if _is_directory(material, entry, root_id=root_id):
            files.extend(
                _walk(
                    material,
                    root_id=root_id,
                    max_files=max_files,
                    seen=seen,
                    depth=depth + 1,
                    key=entry,
                )
            )
        else:
            seen.add(entry)
            files.append(entry)
        # After **every** entry, directory or file. The check used to sit only
        # in the file branch, so a directory recursion walked past the limit
        # and ``max_files=1`` returned two files -- an order-dependent limit
        # that looked like a bound.
        if max_files is not None and len(seen) >= max_files:
            break
    return files


def _stable_source_id(root_id: str, key: str) -> str:
    """A source id that identifies a *location*, not a version of its bytes.

    Root-scoped and path-scoped, so the same file keeps its identity when it
    is edited -- which is what lets ``put_source`` take its refresh branch and
    move the recorded hash. A content-derived id cannot: every edit looks
    like a new file at a path already taken.

    **The key is the root-relative one**, and it stays that way whatever the
    ledger records the path as. The ids this mints are already written in the
    ledger for material ingested before the recorded path was made
    workspace-relative, and the recorded text, the recorded hash and the
    drift detection that reads them all hang off the id. An id derived from
    the recorded path would change with it and orphan all three.
    """
    digest = hashlib.sha256(f"{root_id}{chr(0)}{key}".encode()).hexdigest()
    return f"src-{digest[:16]}"


def _the_workspace_prefix(workspace: Workspace, root: AllowedRoot) -> str:
    """Where the source root sits inside the workspace, in the ledger's spelling.

    ``Source.relative_path`` is workspace-relative and the walk is handed a
    root-relative key, so the root's own place in the workspace is the prefix
    that turns one into the other. It is the same for every file under the
    root, so it is computed once per root rather than once per file.

    **Empty when the root *is* the workspace root**, because then the key
    already is the workspace-relative path and there is nothing to prefix.
    """
    try:
        relative = root.path.relative_to(workspace.selected_root)
    except ValueError:
        # A root outside the workspace. ``Workspace.bind`` refuses one, and a
        # workspace built by hand with one has nothing walkable under it --
        # the boundary refuses the listing -- so no file is ever named with
        # this prefix.
        return ""
    if not relative.parts:
        return ""
    return PurePosixPath(*relative.parts).as_posix()


def _is_directory(material: SourceMaterial, key: str, *, root_id: str) -> bool:
    """Whether a workspace key names a directory, via the workspace's own resolution.

    Asked through ``path_in`` and read off ``real_path`` -- the
    symlink-and-junction-resolved target the permission boundary itself
    uses -- rather than by ``os.path.isdir`` on a joined path, which would
    let the walk see through a symlink the boundary refuses. A key that
    resolves to neither a file nor a directory, a broken symlink, is treated
    as a file; the read that follows fails and is recorded, which is the
    honest outcome for something that is not there.
    """
    try:
        return material.workspace.path_in(key, root_id).real_path.is_dir()
    except Exception:
        return False
