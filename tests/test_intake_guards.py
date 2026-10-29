"""The intake guards, and the archives they refuse.

**What is under test.** LC-P2-06 T04: the four archive cases the
design's §7 names — the zip bomb, the path traversal, the macro, the
oversize archive — and the grant that has to come before all of them.

**The order is the property.** A file with no grant is **not opened, not
listed and not measured**, because the archive's contents are the material
and the material is what the grant is about. **A refusal that still reads
the file to find out how big it is has already done the thing the grant
forbids.** So the no-grant case is witnessed by a file that could not be
opened at all — if the check opened it, the test would fail.

**And every ceiling is declared**, and a refusal names the ceiling it
exceeded. A limit buried in the code is a limit nobody knows exists.

**And the macro is refused rather than cleaned.** A macro-enabled document
with its macro removed is still a document whose provenance is unclear, and
the design says the macro is *not executed* — not that the file is made
safe. **A refusal is honest; a partial acceptance is not.**
"""

from __future__ import annotations

import zipfile
from pathlib import Path, PurePosixPath

import pytest

from labcairn.material.intake import (
    ArchiveLimits,
    IntakeRefusal,
    inspect_archive,
)


def _archive(path: Path, entries: dict[str, bytes]) -> Path:
    """A zip holding *entries*, written verbatim.

    **The compression ratio is controlled by the content**, so the bomb
    fixture is a real one rather than a declared one: a file of repeated
    bytes compresses far better than the ceiling allows, and the check
    must catch it from the archive's own declarations.
    """
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return path


def _bomb_archive(path: Path) -> Path:
    """An archive with one entry that compresses far beyond the ceiling."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("big.txt", b"0" * (4 * 1024 * 1024))
    return path


# --------------------------------------------------------------------------- #
# the grant comes first
# --------------------------------------------------------------------------- #


def test_a_file_with_no_grant_is_not_read(tmp_path: Path) -> None:
    """**The archive is not opened at all.**

    **What breaks it:** a check that inspects the file and then refuses.
    The refusal would be honest and the reading would already have
    happened, and **the reading is what the grant is about**.

    **The witness is a file that could not be opened.** If the check
    opened it, the failure would be the open, not the refusal.
    """
    result = inspect_archive(
        tmp_path / "not-there.zip",
        grant_present=False,
    )

    assert result.admitted is False
    assert result.refusal is IntakeRefusal.NO_GRANT
    assert "grant" in result.detail.lower()
    # Nothing was read, so nothing was listed.
    assert result.entries == ()


def test_a_grant_is_the_remedy_the_refusal_names(tmp_path: Path) -> None:
    """A refusal names what would satisfy it."""
    result = inspect_archive(tmp_path / "not-there.zip", grant_present=False)

    assert "remedy" in result.detail.lower()


# --------------------------------------------------------------------------- #
# the four archive cases
# --------------------------------------------------------------------------- #


def test_a_zip_bomb_is_refused_and_the_ceiling_is_named(tmp_path: Path) -> None:
    """**A zip bomb is refused by its declared ratio**, so the check never
    expands the archive.

    **What breaks it:** a check that expands the archive to measure it.
    The check would then be the thing that exhausts the memory, which is
    the opposite of refusing the bomb.

    **And the refusal names the ceiling**, because a refusal that says
    "too big" leaves the person guessing which limit they hit.
    """
    path = _bomb_archive(tmp_path / "bomb.zip")
    limits = ArchiveLimits(max_compression_ratio=10)

    result = inspect_archive(path, limits=limits)

    assert result.admitted is False
    assert result.refusal is IntakeRefusal.ZIP_BOMB
    assert "10" in result.detail


def test_a_path_that_escapes_the_root_is_refused(tmp_path: Path) -> None:
    """**The check is on the canonical path, not on the name as it was
    written.**

    **What breaks it:** a string comparison. ``../`` is the obvious case
    and it is not the only one — an absolute path, a drive letter and a
    path that merely *starts* with the root's name all escape, and a
    string comparison lets two of them through.
    """
    path = _archive(
        tmp_path / "escape.zip",
        {"../outside.txt": b"not mine"},
    )

    result = inspect_archive(path, root=PurePosixPath("/data/proj-1"))

    assert result.admitted is False
    assert result.refusal is IntakeRefusal.PATH_TRAVERSAL
    assert "escape" in result.detail.lower()


def test_an_absolute_path_in_an_archive_is_refused(tmp_path: Path) -> None:
    """**An absolute path escapes, and a string comparison would miss it.**

    **What breaks it:** a check that only looks for ``..``. A path that
    starts at the root would be written into the root's own place.
    """
    path = _archive(tmp_path / "absolute.zip", {"/etc/passwd": b"root:root"})

    result = inspect_archive(path, root=PurePosixPath("/data/proj-1"))

    assert result.admitted is False
    assert result.refusal is IntakeRefusal.PATH_TRAVERSAL


def test_a_sibling_that_merely_starts_with_the_roots_name_is_refused(
    tmp_path: Path,
) -> None:
    """``proj-1-secrets`` is not under ``proj-1``.

    **What breaks it:** a prefix comparison without the separator. The
    sibling's name starts with the root's name, and a check that only
    looked at the characters would let it through.

    **The root here is absolute**, because that is what an extraction root
    is: a directory on the filesystem. **An entry's name is either
    absolute** -- and then it is compared against the root's own path --
    **or relative**, and then the extractor resolves it against the root
    itself, which is safe.
    """
    path = _archive(
        tmp_path / "sibling.zip",
        {"/data/proj-1-secrets/notes.txt": b"not mine"},
    )

    result = inspect_archive(path, root=PurePosixPath("/data/proj-1"))

    assert result.admitted is False
    assert result.refusal is IntakeRefusal.PATH_TRAVERSAL


def test_a_macro_enabled_document_is_refused_not_cleaned(tmp_path: Path) -> None:
    """**The macro is not executed, and the file is not stripped.**

    **What breaks it:** extracting the archive and keeping everything but
    the macro. The result would be a document that looks fine and whose
    provenance is unclear, and **a refusal is honest where a partial
    acceptance is not**.
    """
    path = _archive(tmp_path / "macro.zip", {"paper.docm": b"PK-ish macro"})

    result = inspect_archive(path)

    assert result.admitted is False
    assert result.refusal is IntakeRefusal.MACRO_NOT_EXECUTED
    assert "refused rather than cleaned" in result.detail


def test_an_oversize_archive_is_refused_and_the_ceiling_is_named(
    tmp_path: Path,
) -> None:
    """A declared ceiling, and the refusal names it."""
    path = _archive(tmp_path / "big.zip", {"a.txt": b"x" * 100})
    limits = ArchiveLimits(max_total_bytes=10)

    result = inspect_archive(path, limits=limits)

    assert result.admitted is False
    assert result.refusal is IntakeRefusal.ARCHIVE_TOO_LARGE
    assert "10" in result.detail


def test_an_oversize_entry_is_refused(tmp_path: Path) -> None:
    """The per-entry ceiling, and the archive ceiling, are two limits."""
    path = _archive(tmp_path / "one-big.zip", {"big.txt": b"x" * 1000})
    limits = ArchiveLimits(max_entry_bytes=100, max_total_bytes=10_000_000)

    result = inspect_archive(path, limits=limits)

    assert result.admitted is False
    assert result.refusal is IntakeRefusal.ARCHIVE_TOO_LARGE


def test_a_file_that_is_not_an_archive_is_refused(tmp_path: Path) -> None:
    """Bytes that are not an archive are inventoried and hashed, and
    nothing is taken from them."""
    path = tmp_path / "not-a-zip.zip"
    path.write_bytes(b"this is not a zip file")

    result = inspect_archive(path)

    assert result.admitted is False
    assert result.refusal is IntakeRefusal.NOT_AN_ARCHIVE
    assert "hashed" in result.detail


# --------------------------------------------------------------------------- #
# the ordinary case
# --------------------------------------------------------------------------- #


def test_a_clean_archive_is_admitted_and_its_entries_listed(tmp_path: Path) -> None:
    """The ordinary case: the archive is admitted and its entries are
    listed.

    **And the entries are listed even when the archive is refused**,
    because a person who handed over a folder needs to know what was in it
    either way.
    """
    path = _archive(
        tmp_path / "papers.zip",
        {
            "draft.docx": b"first draft",
            "revised.docx": b"second draft",
            "notes/readme.txt": b"a note",
        },
    )

    result = inspect_archive(path, root=PurePosixPath("/data/papers"))

    assert result.admitted is True
    assert result.refusal is None
    assert {entry.name for entry in result.entries} == {
        "draft.docx",
        "revised.docx",
        "notes/readme.txt",
    }
    assert len(result.readable_entries) == 3


def test_a_refused_archive_still_lists_its_entries(tmp_path: Path) -> None:
    """**The person who handed over the folder needs to know what was in
    it**, refused or not."""
    path = _archive(
        tmp_path / "mixed.zip",
        {"draft.docx": b"fine", "../escape.txt": b"not fine"},
    )

    result = inspect_archive(path, root=PurePosixPath("/data/mixed"))

    assert result.admitted is False
    assert {entry.name for entry in result.entries} == {
        "draft.docx",
        "../escape.txt",
    }


def test_the_limits_are_declared_values_not_buried_numbers() -> None:
    """**A limit buried in the code is a limit nobody knows exists.**

    **What breaks it:** a ceiling written as a literal inside the check.
    The value would still work, and nobody could find it, argue with it or
    change it without reading the implementation.
    """
    limits = ArchiveLimits()

    assert limits.max_total_bytes > 0
    assert limits.max_entry_bytes > 0
    assert limits.max_compression_ratio > 0
    assert limits.max_entries > 0
    # And the dataclass is frozen, so a limit cannot be changed at runtime by
    # something that found the object.
    with pytest.raises((AttributeError, TypeError)):
        limits.max_entries = 1  # type: ignore[misc]
