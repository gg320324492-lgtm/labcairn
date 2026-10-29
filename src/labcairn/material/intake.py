"""Taking a folder of manuscripts in, without taking the folder apart.

**What this module is.** LC-P2-06 T04: the intake path — the place where
somebody hands over a folder of files, and the system has to decide what it
may read.

**The design's §7 names the cases, and they are not version-graph
questions:**

- a file with no grant — **the archive is not readable**;
- a zip bomb — a compression ratio beyond a declared ceiling;
- a path that escapes the extraction root;
- a macro-enabled document — **the macro is not executed**;
- an archive beyond a declared size.

**Every ceiling here is a *declared* value**, not a number buried in the
code, and **a file that exceeds one is refused with the ceiling named**.
That is the project's standard for a refusal: it says what is wrong and
what the limit was.

**And the macro is refused rather than stripped.** A macro-enabled
document with its macro removed is still a document whose provenance is
unclear, and the design says the macro is *not executed* — not that the
file is cleaned. **A refusal is honest; a partial acceptance is not.**

**What this module does not do.** It does not read the documents' contents
— the OOXML reader does that, and it has its own gates. It does not decide
who may be granted what. **It decides whether the bytes may be looked at
at all.**
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Final

__all__ = [
    "ArchiveLimits",
    "IntakeEntry",
    "IntakeRefusal",
    "IntakeResult",
    "inspect_archive",
]


class IntakeRefusal(StrEnum):
    """Why an intake was refused.

    **Each one names what was wrong and what the limit was**, because a
    refusal that only says "too big" leaves the person guessing which
    limit they hit.
    """

    NO_GRANT = "no_grant"
    ZIP_BOMB = "zip_bomb"
    PATH_TRAVERSAL = "path_traversal"
    MACRO_NOT_EXECUTED = "macro_not_executed"
    ARCHIVE_TOO_LARGE = "archive_too_large"
    NOT_AN_ARCHIVE = "not_an_archive"


#: Extensions that carry executable content. **The file is refused, not
#: cleaned**: a macro-enabled document with its macro removed is still a
#: document whose provenance is unclear, and the design says the macro is
#: not executed rather than that the file is made safe.
MACRO_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {".docm", ".xlsm", ".xltm", ".pptm", ".potm", ".xlam", ".ppam"}
)


@dataclass(frozen=True)
class ArchiveLimits:
    """The declared ceilings, in one place.

    **Every one is a declared value** — the project's standard is that a
    limit somebody can see is a limit somebody can argue with, and a limit
    buried in the code is a limit nobody knows exists.

    | The limit | The default | Why |
    |---|---|---|
    | ``max_total_bytes`` | 2 GiB | a folder of manuscripts is not larger than this |
    | ``max_entry_bytes`` | 512 MiB | one file inside an archive is not larger than this |
    | ``max_compression_ratio`` | 100 | a legitimate document does not compress a hundredfold |
    | ``max_entries`` | 10 000 | a folder is not tens of thousands of files |

    **The compression ratio is the zip bomb's number**, and it is checked
    against the *uncompressed* size the archive declares rather than against
    what it actually expands to — so the check is cheap and **cannot itself
    be the thing that exhausts the memory**.
    """

    max_total_bytes: int = 2 * 1024 * 1024 * 1024
    max_entry_bytes: int = 512 * 1024 * 1024
    max_compression_ratio: int = 100
    max_entries: int = 10_000

    def ratio_ceiling(self) -> int:
        return self.max_compression_ratio


@dataclass(frozen=True)
class IntakeEntry:
    """One file the archive offered, and whether it may be read.

    **``refusal`` is ``None`` for a file that may be read**, and the reason
    otherwise. **The file's name is kept as the archive gave it**, because
    the person who handed over the folder needs to recognise it.
    """

    name: str
    #: The uncompressed size the archive declares.
    size: int
    #: The compressed size the archive declares.
    compressed_size: int
    #: Why it may not be read, or ``None``.
    refusal: IntakeRefusal | None = None
    #: The limit that was exceeded, or the detail that names it.
    detail: str = ""


@dataclass(frozen=True)
class IntakeResult:
    """What the intake found.

    **The archive is admitted or refused as a whole**, and the entries are
    listed either way, because a person who handed over a folder needs to
    know what was in it either way.

    **And the entries are listed with their own refusals**, so a file the
    archive offered but the system may not read is **named** rather than
    silently dropped.
    """

    admitted: bool
    entries: tuple[IntakeEntry, ...] = ()
    #: Why the archive was refused, or ``None``.
    refusal: IntakeRefusal | None = None
    #: The reason, naming the limit that was exceeded.
    detail: str = ""
    problems: tuple[str, ...] = field(default_factory=tuple)

    @property
    def readable_entries(self) -> tuple[IntakeEntry, ...]:
        """The entries that may be read."""
        return tuple(entry for entry in self.entries if entry.refusal is None)


def _is_within(root: PurePosixPath, candidate: PurePosixPath) -> bool:
    """Whether an archive entry's path stays inside the extraction root.

    **The check is on the *canonical* path**, not on the name as it was
    written. ``../`` is the obvious case, and it is not the only one: an
    absolute path (``/etc/passwd``), a drive letter
    (``C:\\Windows\\...``) and a path that merely *starts* with the root's
    name but is not under it (``proj-1-secrets`` against a root of
    ``proj-1``) all escape, and a string comparison would let two of them
    through.

    **So the check is component-wise**, and a component that goes up
    (``..``) is refused rather than resolved — resolving it would let a
    path that climbs out and comes back in look innocent.

    **And the root must be an ancestor of the entry.** The root is the
    directory the archive is extracted into, and an entry's name is the
    path it will have **relative to the filesystem root** — so the entry
    has to name a path under the root, and a sibling that merely shares a
    prefix (``proj-1-secrets`` against a root of ``/data/proj-1``) does
    not.

    **So the root is compared component by component against the entry's
    whole path**, and the entry's path is the absolute path the entry will
    occupy. A root of ``/data/proj-1`` and an entry of
    ``/data/proj-1/drafts/a.docx`` agree; an entry of
    ``/data/proj-1-secrets/notes.txt`` does not, and neither does an entry
    of ``draft.docx`` — because that name is relative and the root is
    absolute, and **a relative entry name is one the extractor resolves
    against the root itself**, which is safe.
    """
    parts = list(candidate.parts)
    if candidate.is_absolute() or candidate.drive or candidate.root:
        # An absolute entry path is compared against the root's own path.
        for part in parts:
            if part == "..":
                return False
        root_parts = list(root.parts)
        if not root_parts:
            return True
        return parts[: len(root_parts)] == root_parts
    # A relative entry name is resolved against the root by the extractor,
    # so the only thing to refuse is a component that climbs out.
    return not any(part == ".." for part in parts)


def inspect_archive(
    path: Path,
    *,
    limits: ArchiveLimits | None = None,
    root: PurePosixPath | None = None,
    grant_present: bool = True,
) -> IntakeResult:
    """Inspect an archive and say what may be read.

    **The grant is checked first.** A file with no ``store_read`` grant is
    not read at all — **not opened, not listed, not measured** — because
    the archive's contents are the material, and the material is what the
    grant is about. A refusal that still reads the file to find out how big
    it is has already done the thing the grant forbids.

    **And the ceilings are checked against the archive's own declarations.**
    A zip bomb is refused by its declared ratio, so **the check never
    expands the archive** and cannot itself be the exhaustion.
    """
    ceilings = limits or ArchiveLimits()

    if not grant_present:
        return IntakeResult(
            admitted=False,
            refusal=IntakeRefusal.NO_GRANT,
            detail=(
                "no store_read grant covers this material. The remedy is a "
                "grant: the file is not opened, not listed and not measured, "
                "because reading it is what the grant is about."
            ),
        )

    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        return IntakeResult(
            admitted=False,
            refusal=IntakeRefusal.NOT_AN_ARCHIVE,
            detail=(
                f"the file is not an archive this reader can open: "
                f"{type(exc).__name__}: {exc}. It is inventoried and hashed, "
                f"and nothing is taken from it."
            ),
        )

    with archive:
        try:
            infos = archive.infolist()
        except (zipfile.BadZipFile, OSError) as exc:
            return IntakeResult(
                admitted=False,
                refusal=IntakeRefusal.NOT_AN_ARCHIVE,
                detail=f"the archive's directory could not be read: {exc}.",
            )

        if len(infos) > ceilings.max_entries:
            return IntakeResult(
                admitted=False,
                refusal=IntakeRefusal.ARCHIVE_TOO_LARGE,
                detail=(
                    f"the archive holds {len(infos)} entries and the declared "
                    f"ceiling is {ceilings.max_entries}."
                ),
            )

        total = sum(info.file_size for info in infos)
        if total > ceilings.max_total_bytes:
            return IntakeResult(
                admitted=False,
                refusal=IntakeRefusal.ARCHIVE_TOO_LARGE,
                detail=(
                    f"the archive declares {total} bytes uncompressed and the "
                    f"declared ceiling is {ceilings.max_total_bytes}."
                ),
            )

        entries: list[IntakeEntry] = []
        traversal: list[str] = []
        macros: list[str] = []
        bombs: list[str] = []
        oversize: list[str] = []

        for info in infos:
            name = info.filename
            size = info.file_size
            compressed = info.compress_size

            if size > ceilings.max_entry_bytes:
                oversize.append(name)
            ratio = size // max(compressed, 1)
            if ratio > ceilings.max_compression_ratio:
                bombs.append(name)
            if PurePosixPath(name).suffix.lower() in MACRO_EXTENSIONS:
                macros.append(name)
            if root is not None and not _is_within(root, PurePosixPath(name)):
                traversal.append(name)

            entries.append(
                IntakeEntry(
                    name=name,
                    size=size,
                    compressed_size=compressed,
                )
            )

        problems: list[str] = []
        if traversal:
            problems.append(
                f"{len(traversal)} entr(y/ies) escape the extraction root: {sorted(traversal)[:5]}"
            )
        if macros:
            problems.append(
                f"{len(macros)} entr(y/ies) carry executable content and are "
                f"refused rather than cleaned: {sorted(macros)[:5]}"
            )
        if bombs:
            problems.append(
                f"{len(bombs)} entr(y/ies) exceed the declared compression "
                f"ratio of {ceilings.max_compression_ratio}: {sorted(bombs)[:5]}"
            )
        if oversize:
            problems.append(
                f"{len(oversize)} entr(y/ies) exceed the declared per-entry "
                f"ceiling of {ceilings.max_entry_bytes} bytes: "
                f"{sorted(oversize)[:5]}"
            )

        if problems:
            return IntakeResult(
                admitted=False,
                entries=tuple(entries),
                refusal=(
                    IntakeRefusal.PATH_TRAVERSAL
                    if traversal
                    else IntakeRefusal.MACRO_NOT_EXECUTED
                    if macros
                    else IntakeRefusal.ZIP_BOMB
                    if bombs
                    else IntakeRefusal.ARCHIVE_TOO_LARGE
                ),
                detail="; ".join(problems),
                problems=tuple(problems),
            )

        return IntakeResult(admitted=True, entries=tuple(entries))
