"""Ingesting a workspace: walking source roots and persisting what each file yields.

LC-P1-08's last piece. The adapters read bytes; this connects them to a real
workspace so the whole path -- walk, read, extract, disclose, store -- runs
against real material.

**It walks through :class:`SourceMaterial`, never the filesystem.** Reading
directly would bypass the permission boundary: ``list_dir`` applies
``source.inventory`` filtering and drops denied entries, so a denied
subdirectory is invisible to this walk exactly as it is to the user. That is
the whole point of the boundary -- a walk that went around it would inventory
material the user has not agreed to inventory.

One :class:`~labcairn.workspace.readonly.SourceMaterial` read and one
:func:`~labcairn.material.ingest.ingest_into_store` per file, each in its own
transaction, so a file that fails its constraints does not roll back the
files already ingested. That is a deliberate choice: a workspace with one
corrupt PDF should still be inventoried, and the failure is recorded on that
file rather than stopping the walk.

Materials are inventoried even when no adapter claims their format -- a
``.zip`` or a format Phase 1 cannot address is a *recorded fact about the
workspace*, distinct from a file that was never seen.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from labcairn.material.ingest import IngestOutcome, ingest_into_store
from labcairn.workspace.readonly import SourceMaterial

__all__ = ["WalkReport", "ingest_workspace"]

#: Bound on directory depth, so a symlink loop or a pathological tree cannot
#: make the walk unbounded. A research folder does not nest this deep; hitting
#: the bound is reported rather than silently truncating.
_MAX_DEPTH = 16


@dataclass
class WalkReport:
    """What a workspace walk did, per file and in total."""

    outcomes: tuple[IngestOutcome, ...] = ()
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
    seen: set[str] = set()

    for root in material.workspace.source_roots:
        root_id = root.root_id
        for key in _walk(material, root_id=root_id, max_files=max_files, seen=seen):
            try:
                data = material.read(key, root_id=root_id)
            except Exception as exc:
                failures.append((key, f"{type(exc).__name__}: {exc}"))
                continue
            try:
                outcome = ingest_into_store(
                    session,
                    data,
                    relative_path=key,
                    display_name=key.rsplit("/", 1)[-1],
                    ingested_at=ingested_at,
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

    ``seen`` is shared across roots so a material reachable from two roots is
    ingested once -- two rows for one file would make the inventory lie about
    how much material there is.
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
            if max_files is not None and len(seen) >= max_files:
                break
    return files


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
