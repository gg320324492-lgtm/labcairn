"""Ingesting a workspace: walking source roots and persisting what each file yields.

LC-P1-08's last piece. The adapters read bytes; this connects them to a real
workspace so the whole path -- walk, read, extract, disclose, store -- runs
against real material.

**It walks through :class:`SourceMaterial`, never the filesystem.** Reading
directly would bypass the permission boundary entirely, so every listing and
read here goes through it.

**What the walk does not claim.** It does not claim a denied subtree is
invisible, because that is not yet true and pretending otherwise would be the
worst kind of bug in this package. Review demonstrated that a **symlink inside
a permitted directory, pointing into a denied one, is followed**: with
``DENY source.inventory private/**``, ``read("public/hop/secret.md")`` where
``public/hop -> private`` returns the denied file's bytes, and this walk
ingests them. The cause is in the boundary rather than here --
``policy.filter_listing`` matches only the declared spelling and
``SourceMaterial.read`` never consults the policy -- but this walk is what
turns the gap into persisted, searchable rows. Recorded as a known gap; the
fix belongs to the policy layer, not to this module.

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

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from labcairn.material.ingest import IngestOutcome, ingest_into_store
from labcairn.workspace.readonly import SourceMaterial

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
        # Per root, not shared. ``list_dir`` returns **root-relative** keys, so
        # two roots each holding ``notes.md`` produce the same string and a
        # shared ``seen`` silently swallowed the second file.
        seen: set[str] = set()
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
                    # Stable across content changes, unlike the
                    # content-derived default. ``sources.relative_path`` is
                    # UNIQUE, so a content-derived id made every re-walk of an
                    # *edited* file a permanent IntegrityError, leaving the
                    # recorded hash and text frozen at the first version -- and
                    # ADR-0004 A2's drift detection nothing to detect against.
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
    string and the shared set silently swallowed one. Cross-root dedup
    happens instead through the workspace's own ``cross_root`` refusal.
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
    """
    digest = hashlib.sha256(f"{root_id}{chr(0)}{key}".encode()).hexdigest()
    return f"src-{digest[:16]}"


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
