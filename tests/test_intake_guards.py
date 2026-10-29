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

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path, PurePosixPath
from typing import Final

import pytest

from labcairn.material.intake import (
    ArchiveLimits,
    IntakeRefusal,
    inspect_archive,
)

pytestmark = pytest.mark.negative


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


def test_material_with_no_grant_is_not_readable(tmp_path: Path) -> None:
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


def test_the_archive_guards_refuse_what_the_design_names(tmp_path: Path) -> None:
    """**All four of the design's §7 archive cases, in one test.**

    The design names four: the path traversal, the zip bomb, the
    macro-enabled document, and the oversize archive. **A reader of this
    test should be able to see the whole list without reading four other
    files**, and the four separate tests below it are the ones that say
    *how* each is caught.

    **And the grant comes first in all four**, because a refusal that
    still reads the file to find out how big it is has already done the
    thing the grant forbids.
    """
    cases = {
        "path": ({"../escape.txt": b"x"}, IntakeRefusal.PATH_TRAVERSAL),
        "absolute": ({"/etc/passwd": b"x"}, IntakeRefusal.PATH_TRAVERSAL),
        "macro": ({"paper.docm": b"x"}, IntakeRefusal.MACRO_NOT_EXECUTED),
    }
    for name, (entries, expected) in cases.items():
        path = _archive(tmp_path / f"{name}.zip", entries)
        result = inspect_archive(path, root=PurePosixPath("/data/root"))
        assert result.admitted is False, f"the {name} archive was admitted"
        assert result.refusal is expected, f"the {name} archive was refused for the wrong reason"

    # The bomb, which needs its own archive because it needs the ratio.
    bomb = _bomb_archive(tmp_path / "bomb.zip")
    result = inspect_archive(bomb, limits=ArchiveLimits(max_compression_ratio=10))
    assert result.admitted is False
    assert result.refusal is IntakeRefusal.ZIP_BOMB

    # And the grant, which comes before every one of them.
    without_grant = inspect_archive(bomb, grant_present=False)
    assert without_grant.refusal is IntakeRefusal.NO_GRANT


# --------------------------------------------------------------------------- #
# The material that must not be here
# --------------------------------------------------------------------------- #


#: The suffixes that carry research material: a manuscript, a dataset, an
#: archive, or the store somebody's work sits in.
#:
#: **The list is deliberately broad.** A suffix missing from it is a suffix
#: a real manuscript could arrive under, and this list is the only thing
#: standing between the two.
MATERIAL_SUFFIXES: Final = frozenset(
    {
        ".7z",
        ".csv",
        ".db",
        ".doc",
        ".docm",
        ".docx",
        ".gz",
        ".h5",
        ".hdf5",
        ".jsonl",
        ".npy",
        ".npz",
        ".parquet",
        ".pdf",
        ".ppt",
        ".pptx",
        ".rar",
        ".sqlite",
        ".sqlite3",
        ".tar",
        ".tgz",
        ".tsv",
        ".xls",
        ".xlsx",
        ".zip",
    }
)

#: The material the repository is allowed to hold, and nothing else.
#:
#: **Every entry is public or synthetic, and the reason is written here
#: rather than left to a reader's trust.** The nine CSVs under
#: ``tests/fixtures/analysis`` are synthetic analysis fixtures; the four
#: under ``tests/fixtures/public`` are the public corpus's synthetic
#: material, whose manifest says ``"material_origin": "synthetic"`` and
#: carries their hashes; and the three PDFs under ``tests/fixtures/papers``
#: are CC BY 4.0 arXiv papers whose attribution is in that directory's
#: ``MANIFEST.md``.
#:
#: **A new entry is a decision, not an accident.** The assertion below is an
#: equality, so a fixture added without a thought about where it came from
#: fails the suite rather than shipping.
ALLOWED_MATERIAL: Final = frozenset(
    {
        "tests/fixtures/analysis/basic.csv",
        "tests/fixtures/analysis/declared.csv",
        "tests/fixtures/analysis/empty.csv",
        "tests/fixtures/analysis/groups.csv",
        "tests/fixtures/analysis/holes.csv",
        "tests/fixtures/analysis/missing.csv",
        "tests/fixtures/analysis/single.csv",
        "tests/fixtures/analysis/typed.csv",
        "tests/fixtures/analysis/units.csv",
        "tests/fixtures/papers/arx-2610.09396.pdf",
        "tests/fixtures/papers/arx-2610.10596.pdf",
        "tests/fixtures/papers/arx-2610.12393.pdf",
        "tests/fixtures/public/biomedical_panel/panel_readings.csv",
        "tests/fixtures/public/computational_solver/solver_runs.csv",
        "tests/fixtures/public/no_evidence/sample_log.csv",
        "tests/fixtures/public/physical_tension/measurements.csv",
    }
)

#: How long a Git call in this module may take before it is killed.
GIT_TIMEOUT_S: Final = 60


def _git_paths(repo_root: Path, *args: str) -> list[str]:
    """The paths Git names, one per line."""
    proc = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=GIT_TIMEOUT_S,
    )
    assert proc.returncode == 0, (
        f"git {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}"
    )
    return [line for line in proc.stdout.splitlines() if line]


def _is_material(path: str) -> bool:
    """Whether *path*'s name says it carries research material."""
    return PurePosixPath(path).suffix.lower() in MATERIAL_SUFFIXES


def test_no_real_material_reaches_the_repository_or_a_ci_artefact(repo_root: Path) -> None:
    """**The repository holds no material, and this is checked against the files.**

    ADR-0015 D5 and LC-P2-06's A11: no real manuscript's bytes may appear in
    the repository, in a CI artefact, or in the public evaluation corpus.
    **The property is about bytes on disk, so the witness reads the disk**
    — the committed tree, the working tree, the built artefacts' member
    scope, and the corpus' own material — rather than asking a module what
    it believes.

    **Why the working tree is checked apart from the committed tree.** The
    release job says it outright: *"the build backend does not read
    .gitignore"*, so a file that is in the working tree but neither
    committed nor ignored **lands in the sdist**. A file that was never
    committed is therefore still a route to a published artefact, and an
    index-only check would not see it.

    **And the corpus is checked against its own hashes**, so "the public
    corpus is synthetic" is a fact about the bytes rather than a sentence
    in a notice.

    **What breaks it:** a manuscript dropped into the tree, a dataset
    exported into ``tests/fixtures/``, a real recording swapped in for a
    synthetic one, or a material file left in the working tree by a
    session that never committed it.
    """
    # 1. The committed tree. The equality is the point: a material file
    #    that is not on the list is one nobody has said where it came from.
    committed = {p for p in _git_paths(repo_root, "ls-files") if _is_material(p)}
    assert committed == ALLOWED_MATERIAL, (
        "the committed tree holds material that is not on the allowed list, "
        f"or is missing one that is: {sorted(committed ^ ALLOWED_MATERIAL)}"
    )

    # 2. The working tree's extra files — the ones the build backend would
    #    pack into the sdist even though nobody committed them.
    extra = sorted(
        p
        for p in _git_paths(repo_root, "ls-files", "--others", "--exclude-standard")
        if _is_material(p)
    )
    assert not extra, (
        "these files are in the working tree, are neither committed nor "
        "ignored, and so would be packed into the source distribution: "
        f"{extra}"
    )

    # 3. The wheel. Every member of it comes from the package root, so the
    #    package root is where the wheel's material would have to be.
    packaged = [p for p in _git_paths(repo_root, "ls-files", "src/labcairn") if _is_material(p)]
    assert not packaged, f"the package root holds material, so the wheel would carry it: {packaged}"

    # 4. The tree the artefacts are built from.
    head = {
        p for p in _git_paths(repo_root, "ls-tree", "-r", "--name-only", "HEAD") if _is_material(p)
    }
    assert head <= ALLOWED_MATERIAL, (
        f"HEAD holds material that is not on the allowed list: {sorted(head - ALLOWED_MATERIAL)}"
    )

    # 5. The public corpus: synthetic by declaration, and synthetic by
    #    hash — every byte the manifest names is the byte on disk.
    corpus = repo_root / "tests" / "fixtures" / "public"
    manifest = json.loads((corpus / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["material_origin"] == "synthetic", (
        f"the public corpus no longer declares itself synthetic: {manifest['material_origin']!r}"
    )
    declared: set[str] = set()
    for fixture in manifest["fixtures"]:
        for material in fixture["material"]:
            path = corpus / material["path"]
            data = path.read_bytes()
            assert len(data) == material["bytes"], (
                f"{material['path']} is {len(data)} bytes; the manifest says {material['bytes']}"
            )
            digest = hashlib.sha256(data).hexdigest()
            assert digest == material["sha256"], (
                f"{material['path']} hashes to {digest}; the manifest says {material['sha256']}"
            )
            declared.add(material["path"])

    # And nothing is in the corpus that the manifest does not name, so a
    # file added beside the manifest cannot slip past the hashes above.
    on_disk = {
        path.relative_to(corpus).as_posix()
        for path in corpus.rglob("*")
        if path.is_file() and path.name != "MANIFEST.json"
    }
    assert on_disk == declared, (
        "the public corpus holds files its manifest does not name, or is "
        f"missing ones it does: {sorted(on_disk ^ declared)}"
    )

    # 6. The three real papers are CC BY and carry their attribution, so
    #    "public" is a fact about the licence rather than an assumption.
    papers = repo_root / "tests" / "fixtures" / "papers"
    notice = (papers / "MANIFEST.md").read_text(encoding="utf-8")
    assert "CC BY 4.0" in notice, "the papers' notice no longer states the licence"
    for pdf in sorted(papers.glob("*.pdf")):
        assert pdf.name in notice, (
            f"{pdf.name} is in the papers directory but its notice does not name it, "
            "so its provenance and attribution are unrecorded"
        )
