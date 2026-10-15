r"""Reference-exclusion acceptance gate — LC-P1-01 T05.

This file is the executable form of the binding exclusion checklist in
``docs/UPSTREAM_REFERENCES.md`` ("Binding exclusion checklist (applies from
LC-P1-01)"). Until it existed, "reference clones are not committed and not
packaged" was prose: true by construction, and true for the same reason that an
empty box is empty. This module turns it into a gate that fails.

Three families are excluded, stated as glob patterns throughout the project
documents: ``_references*``, ``.upstreams*``, ``labcairn-upstreams*``.

How this file asserts (LC-P1-01 approved amendment **C-8**)
------------------------------------------------------------
C-8 is the reason this file is written the way it is: *assert behaviour, not
text*. Concretely, for each promise:

============================  ===========================================
Promise                       How it is proven here
============================  ===========================================
"not committed"               ``git ls-files`` — the real index
"git ignores them"            ``git check-ignore`` — Git's own matcher,
                              never a regex over ``.gitignore`` text
"not packaged"                real ``uv build`` output, read as archive
                              member name lists (sdist + wheel)
"not archived"                ``git archive --format=tar HEAD`` members
"the artifact still works"    install the wheel into a throwaway venv and
                              import ``labcairn`` / ``labcairn.core``
============================  ===========================================

Why not grep ``.gitignore``: a file can list ``_references*`` and still fail to
exclude it (wrong anchoring, missing case variant, trailing-slash semantics), and
a text match cannot tell the difference. ``git check-ignore`` is the same code
path Git actually applies, so a green result means Git would skip the file.

Why ``-c core.ignorecase=false``
--------------------------------
The development machine runs ``core.ignorecase=true`` (Windows, ``E:\LabCairn``);
Linux CI runners run ``false``. A lowercase-only pattern therefore matches here
and silently stops matching in the build that actually publishes — the failure
mode the checklist calls out in "Two known limits that configuration cannot
close", §2. Every ``check-ignore`` call below forces ``ignorecase=false`` so the
development machine reproduces the Linux runner. The reverse direction is
verified too: the exclusion is not *only* case-exact, it still holds with the
local case-insensitive setting.

The false-green guards
----------------------
An exclusion test is easy to write so that it always passes. Three guards stop
that here, and they are the most important tests in the file:

* :func:`test_probe_files_are_observable_to_the_build` — before "the probe is
  absent from the artifact" can mean anything, a *control* file planted in the
  same tree must be *present*. If the build silently ignored the whole
  directory, every exclusion assertion would be vacuous.
* :func:`test_tracked_set_contains_the_expected_labcairn_files` and
  :func:`test_reference_glob_ignores_nothing_else` — the positive controls. An
  implementation of "ignore everything" passes every negative assertion.
* :func:`test_reference_path_matcher_is_case_insensitive_and_anchored` — the
  matcher itself is tested, so it cannot degenerate into "always False".

Independence from the sibling reference clones
----------------------------------------------
This module never reads, needs, or asserts on ``../labcairn-upstreams``. It
plants its own synthetic probe files inside a temporary *copy* of the project,
so it passes identically on a developer laptop, on a Linux CI runner, and on an
external contributor's machine that has never seen a reference clone. That is
LC-P1-01 acceptance item 5 ("No hard runtime/CI dependency on reference
clones") and approved-amendment gate 6, exercised as a test rather than
asserted in prose.

Owned by T05. The only file this task may write is this one.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

import pytest

pytestmark = pytest.mark.reference_exclusion

# ---------------------------------------------------------------------------
# The excluded families, spelled out
# ---------------------------------------------------------------------------

#: The three glob families, verbatim from the binding checklist.
REFERENCE_GLOBS: Final = ("_references*", ".upstreams*", "labcairn-upstreams*")

#: Segment prefixes behind those globs. A path is reference-shaped when *any* of
#: its segments starts with one of these, case-insensitively.
REFERENCE_SEGMENT_PREFIXES: Final = ("_references", ".upstreams", "labcairn-upstreams")

#: Every case variant ``.gitignore`` and the packaging config spell out. The
#: development machine cannot distinguish these (core.ignorecase=true); a Linux
#: runner can, so all of them must be enumerated rather than inferred.
CASE_VARIANT_STEMS: Final = (
    "_references",
    "_References",
    "_REFERENCES",
    ".upstreams",
    ".Upstreams",
    ".UPSTREAMS",
    "labcairn-upstreams",
    "labcairn-Upstreams",
    "LabCairn-upstreams",
    "LabCairn-Upstreams",
    "LABCAIRN-UPSTREAMS",
)

#: The same families as concrete probe directory names. The `-t05probe` suffix
#: makes a planted path unmistakably synthetic if it ever shows up in a diff.
CASE_VARIANT_DIRS: Final = tuple(f"{stem}-t05probe" for stem in CASE_VARIANT_STEMS)

#: Paths that must stay visible. Chosen as near misses: `docs/UPSTREAM_REFERENCES.md`
#: is a real tracked file that *sounds* like a reference path,
#: `labcairn-upstream-tools/` differs from `labcairn-upstreams*` by one letter,
#: and `docs/_reference.md` is singular where the family is plural. If the
#: exclusion rules were over-broad these would start vanishing, which is a real
#: regression — an over-broad ignore rule hides product code.
NOT_IGNORED_PATHS: Final = (
    "docs/README.md",
    "docs/UPSTREAM_REFERENCES.md",
    "docs/_reference.md",
    "docs/plans/LC-P1-01-task-breakdown.md",
    "src/labcairn/__init__.py",
    "src/references_helper.py",
    "tests/test_scaffolding.py",
    "tests/test_no_reference_leakage.py",
    "conftest.py",
    "README.md",
    "pyproject.toml",
    "web/package.json",
    "scripts/checkout_upstreams.py",
    "references/notes.md",
    ".upstream/notes.md",
    "labcairn-upstream-tools/src/module.py",
)

#: Tracked files that must exist. Guards the `git ls-files` assertion against
#: passing on an empty or wrong-repository listing.
EXPECTED_TRACKED_PATHS: Final = (
    ".gitignore",
    "pyproject.toml",
    "README.md",
    "conftest.py",
    "docs/UPSTREAM_REFERENCES.md",
    "src/labcairn/__init__.py",
    "src/labcairn/core/__init__.py",
    "tests/test_scaffolding.py",
)

# ---------------------------------------------------------------------------
# Synthetic probe payload planted into a throwaway copy of the project
# ---------------------------------------------------------------------------

#: Reference-shaped files planted before the probe build. Covers all three
#: families, every case variant `.gitignore` declares, a glob sibling whose
#: suffix differs (`labcairn-upstreams-cache`), two nesting depths, and two
#: placements *inside* the wheel's package root (where the wheel exclude, not
#: only the sdist exclude, has to fire).
PROBE_FILES: Final = (
    "_references-t05probe/LEAK.md",
    "_references-t05probe/nested/deeper/LEAK.md",
    "_References-t05probe/LEAK.md",
    "_REFERENCES-t05probe/LEAK.md",
    ".upstreams-t05probe/LEAK.md",
    ".Upstreams-t05probe/LEAK.md",
    ".UPSTREAMS-t05probe/LEAK.md",
    "labcairn-upstreams-t05probe/LEAK.md",
    "labcairn-upstreams-cache/LEAK.md",
    "labcairn-Upstreams-t05probe/LEAK.md",
    "LabCairn-upstreams-t05probe/LEAK.md",
    "LabCairn-Upstreams-t05probe/LEAK.md",
    "LABCAIRN-UPSTREAMS-t05probe/LEAK.md",
    "docs/_references-t05probe/LEAK.md",
    "docs/labcairn-upstreams-cache/LEAK.md",
    "src/labcairn/_REFERENCES-t05probe/LEAK.py",
    "src/labcairn/labcairn-upstreams-t05probe/LEAK.py",
)

#: Control files. No segment starts with an excluded prefix, so they must be
#: present in the built artifacts. Their presence is what makes the absence of
#: :data:`PROBE_FILES` meaningful.
CONTROL_FILES: Final = (
    "t05-control/CONTROL_ROOT.md",
    "docs/t05-control/CONTROL.md",
    "src/labcairn/t05_control_module.py",
)

#: Files the probe build needs in order to succeed at all.
REQUIRED_PROJECT_FILES: Final = ("pyproject.toml", "README.md")

#: Copied when present. Not required: a future refactor may legitimately drop
#: one of these without breaking the build, and the probe should not fail for it.
OPTIONAL_PROJECT_FILES: Final = ("LICENSE.PENDING.md", ".python-version", "conftest.py")

#: Directories copied wholesale into the probe project.
COPIED_PROJECT_TREES: Final = ("src", "tests", "scripts")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def is_reference_path(name: str) -> bool:
    """True when *name* is shaped like a reference path.

    Segment-based rather than substring-based: ``docs/UPSTREAM_REFERENCES.md``
    contains the word "upstream" and is a tracked product document, while
    ``labcairn-upstreams-cache/x.py`` is reference material. Only a whole path
    *segment* starting with one of :data:`REFERENCE_SEGMENT_PREFIXES` counts.

    Matching is case-insensitive because that is the strictest reading — on a
    case-insensitive filesystem all three spellings collide, so a case-sensitive
    artifact check would be the wrong one to run on Windows.
    """
    parts = PurePosixPath(name.replace("\\", "/")).parts
    return any(part.lower().startswith(REFERENCE_SEGMENT_PREFIXES) for part in parts)


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        check=False,
    )


def _git_ignores(repo_root: Path, relpath: str) -> bool:
    """Ask Git itself whether it would ignore *relpath*.

    Uses ``-c core.ignorecase=false`` so the answer is the one a Linux runner
    would give, not the case-insensitive answer this machine would give.
    """
    proc = _git(repo_root, "-c", "core.ignorecase=false", "check-ignore", "-q", "--", relpath)
    if proc.returncode not in (0, 1):
        msg = (
            f"git check-ignore exited {proc.returncode} for {relpath!r}: "
            f"{proc.stderr.decode('utf-8', 'replace').strip()}"
        )
        raise AssertionError(msg)
    return proc.returncode == 0


def _tracked_paths(repo_root: Path) -> list[str]:
    proc = _git(repo_root, "ls-files", "-z")
    assert proc.returncode == 0, (
        f"git ls-files failed ({proc.returncode}): {proc.stderr.decode('utf-8', 'replace').strip()}"
    )
    return [p for p in proc.stdout.decode("utf-8").split("\0") if p]


def _strip_archive_root(members: Sequence[str]) -> list[str]:
    """Drop the sdist's single top-level directory (``labcairn-0.1.0/...``)."""
    stripped: list[str] = []
    for member in members:
        parts = PurePosixPath(member).parts
        stripped.append("/".join(parts[1:]) if len(parts) > 1 else member)
    return stripped


def _require_uv() -> str:
    """Locate ``uv``, failing loudly when it is absent.

    Deliberately a failure, not a skip. This module is the hard acceptance gate;
    a skip here would mean the packaging half of the gate silently disappears
    from a run that reports success, which is the exact failure shape this whole
    task exists to prevent.
    """
    found = shutil.which("uv")
    if found is None:
        pytest.fail(
            "uv is not on PATH, so no artifact can be built and every packaging "
            "assertion in this module is void. LabCairn is a uv-managed project "
            "(uv.lock, .python-version); install uv and re-run."
        )
    return found


def _ignore_cache_entries() -> set[str]:
    return {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def _iter_project_files(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file() and not _ignore_cache_entries().intersection(path.parts):
            yield path


# ---------------------------------------------------------------------------
# Probe build fixture
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BuiltArtifacts:
    """A real ``uv build`` of a throwaway copy of this project."""

    project_dir: Path
    sdist: Path
    wheel: Path
    #: sdist members with the ``labcairn-0.1.0/`` root stripped.
    sdist_members: tuple[str, ...]
    #: wheel member names as recorded in the zip central directory.
    wheel_members: tuple[str, ...]
    #: Repo-relative probe paths planted before the build.
    probe_paths: tuple[str, ...]
    #: Repo-relative control paths planted before the build.
    control_paths: tuple[str, ...]
    #: Every file under ``src/labcairn`` in the probe copy, as wheel-relative
    #: paths (``labcairn/...``), probes excluded.
    package_files: tuple[str, ...]


@pytest.fixture(scope="session")
def built_artifacts(
    tmp_path_factory: pytest.TempPathFactory,
    repo_root: Path,
) -> BuiltArtifacts:
    """Build the project with reference-shaped probe files planted in it.

    Why a *copy* rather than the working tree:

    * the test never writes into the repository, so it cannot leave junk behind
      if it is killed mid-run;
    * the copy carries no ``.gitignore``. Hatchling falls back to VCS ignore
      files when they are present, and a ``.gitignore`` that already excludes
      ``_references*`` would mask a broken ``tool.hatch...exclude`` list. The
      probe build therefore measures **only** the declared packaging exclusion —
      which is what the binding checklist row actually requires — and is strictly
      stricter than the real build on this machine.

    Why the build happens at all rather than reading ``dist/``: a stale
    ``dist/`` from before a fix would turn a real regression green, and a
    missing ``dist/`` would turn the assertion into a no-op.
    """
    uv = _require_uv()
    base = tmp_path_factory.mktemp("reference_leakage_probe")
    project = base / "project"
    project.mkdir()

    for name in REQUIRED_PROJECT_FILES:
        source = repo_root / name
        assert source.is_file(), f"{name} must exist at the repository root to build"
        shutil.copy2(source, project / name)
    for name in OPTIONAL_PROJECT_FILES:
        source = repo_root / name
        if source.is_file():
            shutil.copy2(source, project / name)
    for tree in COPIED_PROJECT_TREES:
        source = repo_root / tree
        if source.is_dir():
            shutil.copytree(
                source,
                project / tree,
                ignore=shutil.ignore_patterns(*_ignore_cache_entries()),
            )

    for rel in (*PROBE_FILES, *CONTROL_FILES):
        target = project / PurePosixPath(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        marker = "REFERENCE_PROBE" if rel in PROBE_FILES else "T05_CONTROL"
        target.write_text(
            f"{marker}: must never appear in a LabCairn artifact.\n", encoding="utf-8"
        )

    # Computed after copying, so it cannot race with the tree it describes, and
    # with the probes removed — they are asserted absent separately.
    probe_set = {PurePosixPath(p).as_posix() for p in PROBE_FILES}
    package_root = project / "src" / "labcairn"
    package_files = tuple(
        p.relative_to(project / "src").as_posix()
        for p in _iter_project_files(package_root)
        if p.relative_to(project).as_posix() not in probe_set
    )

    out_dir = base / "dist"
    out_dir.mkdir()
    proc = subprocess.run(
        [uv, "build", "--out-dir", str(out_dir)],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, (
        f"uv build failed in the probe project (rc={proc.returncode})\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )

    sdists = sorted(out_dir.glob("*.tar.gz")) + sorted(out_dir.glob("*.zip"))
    wheels = sorted(out_dir.glob("*.whl"))
    assert len(sdists) == 1, f"expected exactly one sdist, found {[p.name for p in sdists]}"
    assert len(wheels) == 1, f"expected exactly one wheel, found {[p.name for p in wheels]}"

    with tarfile.open(sdists[0]) as archive:
        sdist_members = _strip_archive_root(archive.getnames())
    with zipfile.ZipFile(wheels[0]) as archive:
        wheel_members = archive.namelist()

    return BuiltArtifacts(
        project_dir=project,
        sdist=sdists[0],
        wheel=wheels[0],
        sdist_members=tuple(sdist_members),
        wheel_members=tuple(wheel_members),
        probe_paths=tuple(PROBE_FILES),
        control_paths=tuple(CONTROL_FILES),
        package_files=package_files,
    )


# ---------------------------------------------------------------------------
# Git fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def git_checkout(repo_root: Path) -> Path:
    """Guard: these tests only mean anything inside a Git checkout.

    A contributor running the suite from an unpacked sdist has no index and no
    ignore rules; skipping there is correct, and it is the only skip in this
    module's Git half. It is skipped loudly (``-ra`` is on) rather than passing
    silently.
    """
    proc = _git(repo_root, "rev-parse", "--show-toplevel")
    if proc.returncode != 0:
        pytest.skip(
            "not a Git checkout (git rev-parse failed); the index and ignore-rule "
            "half of the exclusion gate cannot run here"
        )
    top = Path(proc.stdout.decode("utf-8").strip()).resolve()
    assert top == repo_root.resolve(), (
        f"repository root resolves to {repo_root} but Git's top level is {top}; "
        "the exclusion tests would be reading a different repository"
    )
    return repo_root


# ===========================================================================
# 0. The matcher itself
# ===========================================================================


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("_references/x.py", True),
        ("_References/x.py", True),
        ("_REFERENCES/x.py", True),
        ("docs/_references/x.py", True),
        (".upstreams/x.py", True),
        ("a/b/.UPSTREAMS/deep/x.py", True),
        ("labcairn-upstreams/x.py", True),
        ("LabCairn-Upstreams/cache/x.py", True),
        ("labcairn-upstreams-cache/x.py", True),
        ("src/labcairn/_REFERENCES-t05probe/LEAK.py", True),
        # Product paths that must not be mistaken for reference material.
        ("docs/UPSTREAM_REFERENCES.md", False),
        ("src/labcairn/core/__init__.py", False),
        ("labcairn-0.1.0/pyproject.toml", False),
        ("labcairn-0.1.0.dist-info/METADATA", False),
        ("scripts/checkout_upstreams.py", False),
        ("references/notes.md", False),
        ("labcairn-upstream-tools/x.py", False),
        ("docs/_reference.md", False),
        ("", False),
    ],
)
def test_reference_path_matcher_is_case_insensitive_and_anchored(path: str, expected: bool) -> None:
    """The matcher must discriminate, or every assertion built on it is noise."""
    assert is_reference_path(path) is expected


# ===========================================================================
# 1. Tracked set — "not committed"
# ===========================================================================


def test_git_ls_files_contains_no_reference_path(git_checkout: Path) -> None:
    """Acceptance row: *git ls-files* contains no reference path.

    The index, not the working tree: a reference clone sitting untracked and
    ignored is the intended state and must not fail this. A reference file that
    someone ``git add -f``'d is the failure this exists to catch, and it appears
    here and nowhere else.
    """
    tracked = _tracked_paths(git_checkout)
    assert tracked, "git ls-files returned nothing; the index cannot be inspected"
    leaked = [p for p in tracked if is_reference_path(p)]
    assert not leaked, (
        "reference-study material is tracked in the LabCairn index:\n  "
        + "\n  ".join(leaked)
        + "\nUntrack it (`git rm --cached -r <path>`) and confirm .gitignore still "
        "excludes it before re-adding."
    )


def test_tracked_set_contains_the_expected_labcairn_files(git_checkout: Path) -> None:
    """Positive control for the assertion above.

    Without this, a `git ls-files` that returned an empty string, ran in the
    wrong directory, or matched nothing at all would pass
    :func:`test_git_ls_files_contains_no_reference_path` for the wrong reason.
    """
    tracked = set(_tracked_paths(git_checkout))
    missing = [p for p in EXPECTED_TRACKED_PATHS if p not in tracked]
    assert not missing, f"expected LabCairn product files to be tracked, missing: {missing}"


def _archive_file_paths(git_checkout: Path) -> list[str]:
    """File paths in ``git archive HEAD``, with no directory entries.

    ``tar -tf`` emits CRLF on Windows, and archive directory entries (``docs/``)
    that ``git ls-tree -r`` does not list. Both are normalized away here so the
    two listings are directly comparable.
    """
    proc = _git(git_checkout, "archive", "--format=tar", "HEAD")
    assert proc.returncode == 0, (
        f"git archive HEAD failed ({proc.returncode}): "
        f"{proc.stderr.decode('utf-8', 'replace').strip()}"
    )
    listing = subprocess.run(
        ["tar", "-tf", "-"], input=proc.stdout, capture_output=True, check=False
    )
    if listing.returncode != 0:
        pytest.fail(
            "could not list the members of `git archive HEAD` output "
            f"({listing.stderr.decode('utf-8', 'replace').strip()}); "
            "the archive-member assertion cannot run"
        )
    entries = [m.strip() for m in listing.stdout.decode("utf-8").split("\n") if m.strip()]
    return [m for m in entries if not m.endswith("/")]


def _committed_tree_paths(git_checkout: Path) -> set[str]:
    tree = _git(git_checkout, "ls-tree", "-r", "--name-only", "HEAD")
    assert tree.returncode == 0, (
        f"git ls-tree failed ({tree.returncode}): {tree.stderr.decode('utf-8', 'replace').strip()}"
    )
    return {p for p in tree.stdout.decode("utf-8").split("\n") if p}


def test_git_archive_contains_no_reference_path(git_checkout: Path) -> None:
    """Release-archive row of the checklist: archives come from ``git archive``.

    Complements ``git ls-files``: the index covers staged-and-committed state,
    ``git archive`` covers what a tag or a release download would actually
    produce. A file force-added but not yet committed passes the archive check
    and fails the ``ls-files`` check; the pair covers both.
    """
    members = _archive_file_paths(git_checkout)
    assert members, "git archive produced an empty member list"

    leaked = [m for m in members if is_reference_path(m)]
    assert not leaked, (
        "reference-study material would ship in a release archive:\n  " + "\n  ".join(leaked)
    )


def test_git_archive_contains_the_expected_labcairn_files(git_checkout: Path) -> None:
    """Positive control for the archive check (an empty archive passes it).

    Asserted as an equality against ``git ls-tree`` rather than a hardcoded file
    list: the release archive must mirror the committed tree exactly, which is
    both the invariant the checklist asks for and a self-maintaining guarantee
    that the member list is non-trivial. A hardcoded list would break every time
    a file is legitimately added or renamed, and would tempt someone into
    deleting the assertion instead of fixing it.
    """
    committed = _committed_tree_paths(git_checkout)
    archived = set(_archive_file_paths(git_checkout))

    assert committed, "HEAD is an empty tree; the archive check would be vacuous"
    assert len(committed) > 10, (
        f"HEAD holds only {len(committed)} files, which is not enough for the archive "
        "comparison to mean anything"
    )
    assert archived == committed, (
        "the release archive does not mirror the committed tree.\n"
        f"only in HEAD: {sorted(committed - archived)}\n"
        f"only in archive: {sorted(archived - committed)}"
    )


# ===========================================================================
# 2. Ignore behaviour — C-8, Git's own matcher, case-sensitive
# ===========================================================================


@pytest.mark.parametrize("directory", CASE_VARIANT_DIRS)
@pytest.mark.parametrize("depth", ("", "docs/", "src/labcairn/"))
def test_gitignore_ignores_reference_paths_in_every_case_variant(
    git_checkout: Path, directory: str, depth: str
) -> None:
    """Every case variant is ignored, at every depth, on a case-sensitive matcher.

    ``check-ignore`` is given pathnames that do not exist: Git evaluates the
    exclude rules against the path without needing the file, so this asserts the
    rule set without creating anything in the working tree.
    """
    probe = f"{depth}{directory}/LEAK.md"
    assert _git_ignores(git_checkout, probe), (
        f"{probe!r} is not ignored with core.ignorecase=false. On this Windows "
        "checkout core.ignorecase=true, so this exclusion would appear to work "
        "here and fail on the Linux runner that publishes. Add the exact spelling "
        "to .gitignore."
    )


@pytest.mark.parametrize(
    "probe",
    [
        "labcairn-upstreams-cache/LEAK.md",
        "labcairn-upstreams-2/LEAK.md",
        "deep/nested/dir/labcairn-upstreams-cache/LEAK.md",
        "docs/_references-alt/multi/level/LEAK.md",
        "web/_references-old/LEAK.ts",
    ],
)
def test_gitignore_ignores_glob_siblings_not_only_exact_names(
    git_checkout: Path, probe: str
) -> None:
    """The families are globs; ``_references_old/`` was the original bug.

    An earlier ``.gitignore`` listed bare directory names, so ``_references_old/``
    and ``labcairn-upstreams-cache/`` were untracked-but-visible — and therefore
    packable. The exclusions must hold for the whole family, not one name.
    """
    assert _git_ignores(git_checkout, probe), f"{probe!r} is not ignored"


@pytest.mark.parametrize("probe", NOT_IGNORED_PATHS)
def test_reference_glob_ignores_nothing_else(git_checkout: Path, probe: str) -> None:
    """Positive control: the exclusions are narrow.

    ``docs/UPSTREAM_REFERENCES.md`` is a tracked product document whose name
    contains every excluded word; ``labcairn-upstream-tools/`` is one letter away
    from the excluded family. An over-broad rule would hide product code, which
    is a silent, slow-moving failure — it looks like "nothing to commit" rather
    than like a bug.
    """
    assert not _git_ignores(git_checkout, probe), (
        f"{probe!r} is a normal LabCairn path but is being ignored. The exclusion "
        "rules are over-broad and are hiding product files."
    )


def test_exclusions_hold_under_the_local_case_insensitive_setting(git_checkout: Path) -> None:
    """The other direction: this machine's own setting must not break them either.

    ``check-ignore`` elsewhere is pinned to ``ignorecase=false``. This one runs
    with the repository's real configuration, so a rule that only worked by
    accident of ``ignorecase=true`` is caught here rather than on a developer's
    machine after they clone on macOS.
    """
    for probe in ("_references-t05probe/LEAK.md", "labcairn-upstreams-cache/LEAK.md"):
        proc = _git(git_checkout, "check-ignore", "-q", "--", probe)
        assert proc.returncode == 0, (
            f"{probe!r} is not ignored under this checkout's own core.ignorecase "
            f"setting (rc={proc.returncode})"
        )


# ===========================================================================
# 3. Packaging — sdist and wheel member lists
# ===========================================================================


def test_probe_files_are_observable_to_the_build(built_artifacts: BuiltArtifacts) -> None:
    """False-green guard for the whole packaging section.

    The control files are planted in the same tree, with names no exclusion rule
    touches. If they are missing from the artifact, the build never saw this
    directory at all — and then "the probe is absent" would be true for reasons
    that have nothing to do with the exclusion rules.
    """
    sdist = set(built_artifacts.sdist_members)
    wheel = set(built_artifacts.wheel_members)

    missing_sdist = [p for p in built_artifacts.control_paths if p not in sdist]
    assert not missing_sdist, (
        "control files planted in the probe project are missing from the sdist: "
        f"{missing_sdist}. The build did not read this tree, so the sdist "
        "exclusion assertion below would pass vacuously."
    )

    package_control = "labcairn/t05_control_module.py"
    assert package_control in wheel, (
        f"{package_control!r} is missing from the wheel. The build did not read "
        "the package tree, so the wheel exclusion assertion below would pass "
        "vacuously."
    )


def test_built_sdist_contains_no_reference_path(built_artifacts: BuiltArtifacts) -> None:
    """Acceptance row: the sdist's member names contain no reference path.

    A real ``uv build`` of a tree carrying planted probe files in all three
    families, all case variants, at two depths and inside the package root.
    """
    leaked = [m for m in built_artifacts.sdist_members if is_reference_path(m)]
    assert not leaked, (
        f"{built_artifacts.sdist.name} packages reference-study material:\n  "
        + "\n  ".join(sorted(leaked))
        + "\nAdd the matching glob to [tool.hatch.build.targets.sdist].exclude."
    )


def test_built_wheel_contains_no_reference_path(built_artifacts: BuiltArtifacts) -> None:
    """Acceptance row: the wheel's member names contain no reference path.

    Separate from the sdist because the wheel target has its own ``exclude``
    list. The wheel is scoped to ``src/labcairn``, so this only fires if a
    reference directory is created *inside the package* — which is why
    :data:`PROBE_FILES` plants two probes there.
    """
    leaked = [m for m in built_artifacts.wheel_members if is_reference_path(m)]
    assert not leaked, (
        f"{built_artifacts.wheel.name} packages reference-study material:\n  "
        + "\n  ".join(sorted(leaked))
        + "\nAdd the matching glob to [tool.hatch.build.targets.wheel].exclude."
    )


def test_probe_build_actually_exercised_all_three_families(
    built_artifacts: BuiltArtifacts,
) -> None:
    """Meta-guard: the probes must span every family, or the test is partial.

    A typo in :data:`PROBE_FILES` that silently reduced it to one family would
    leave the other two untested and everything green.
    """
    covered = {
        glob
        for glob in REFERENCE_GLOBS
        if any(glob.strip("*") in p.lower() for p in built_artifacts.probe_paths)
    }
    missing = sorted(set(REFERENCE_GLOBS) - covered)
    assert not missing, f"the probe set does not exercise these families: {missing}"


def test_wheel_ships_every_file_under_the_package_root(built_artifacts: BuiltArtifacts) -> None:
    """LC-P1-01 amendment C-2 / C-7, asserted against the real wheel.

    This is the reproduced setuptools failure, generalised. Under setuptools,
    ``packages = ["labcairn"]`` means a leaf-package list: the build reports
    success and silently ships a wheel with no subpackages. Rather than checking
    the one directory that happened to break, this asserts the recursive-root
    contract — every file present under ``src/labcairn`` in the built tree is in
    the wheel — so a future ``providers/`` or ``runtime/`` is covered by
    construction rather than by remembering to add an assertion.
    """
    assert built_artifacts.package_files, "no files found under src/labcairn to compare"
    wheel = set(built_artifacts.wheel_members)
    missing = sorted(p for p in built_artifacts.package_files if p not in wheel)
    assert not missing, (
        "files under src/labcairn are missing from the wheel:\n  "
        + "\n  ".join(missing)
        + "\nThe wheel package root is not recursive — subpackages are being dropped."
    )


def test_wheel_contains_the_declared_importable_packages(
    built_artifacts: BuiltArtifacts,
) -> None:
    """Amendment C-7 by name, so the failure names the package rather than a path."""
    wheel = set(built_artifacts.wheel_members)
    for member in ("labcairn/__init__.py", "labcairn/core/__init__.py"):
        assert member in wheel, f"{member!r} is not a member of the built wheel"


def test_developer_scripts_are_not_shipped_in_the_wheel(built_artifacts: BuiltArtifacts) -> None:
    """``scripts/checkout_upstreams.py`` is developer tooling, not product code.

    It clones third-party repositories and embeds the reference catalog. Shipping
    it would put a network-fetching script into every consumer's install.
    """
    wheel = set(built_artifacts.wheel_members)
    offenders = sorted(
        m for m in wheel if m.startswith("scripts/") or m.endswith("checkout_upstreams.py")
    )
    assert not offenders, f"developer scripts leaked into the wheel: {offenders}"


def test_wheel_installs_clean_and_imports(built_artifacts: BuiltArtifacts, tmp_path: Path) -> None:
    """C-8's "installed imports": the artifact is usable, and it is *this* artifact.

    The wheel is installed into a throwaway venv with ``--no-deps`` (nothing
    here imports a third-party package at module scope) and imported in a
    subprocess started outside the source tree. The assertion is that
    ``labcairn.__file__`` lands inside the throwaway venv — an editable install
    of the working tree would otherwise satisfy the import and prove nothing.
    """
    uv = _require_uv()
    venv_dir = tmp_path / "clean-room"
    created = subprocess.run(
        [
            uv,
            "venv",
            "--python",
            f"{sys.version_info.major}.{sys.version_info.minor}",
            str(venv_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert created.returncode == 0, f"uv venv failed:\n{created.stdout}\n{created.stderr}"

    python_exe = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    assert python_exe.is_file(), f"expected an interpreter at {python_exe}"

    installed = subprocess.run(
        [
            uv,
            "pip",
            "install",
            "--no-deps",
            "--python",
            str(python_exe),
            str(built_artifacts.wheel),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert installed.returncode == 0, (
        f"installing the built wheel into a clean venv failed:\n"
        f"{installed.stdout}\n{installed.stderr}"
    )

    probe = subprocess.run(
        [
            str(python_exe),
            "-c",
            "import json, labcairn, labcairn.core;"
            "print(json.dumps({'pkg': labcairn.__file__,"
            "'core': labcairn.core.__file__, 'version': labcairn.__version__}))",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert probe.returncode == 0, (
        f"importing labcairn from the installed wheel failed:\n{probe.stdout}\n{probe.stderr}"
    )
    report = json.loads(probe.stdout.strip().splitlines()[-1])
    resolved = Path(report["pkg"]).resolve()
    assert resolved.is_relative_to(venv_dir.resolve()), (
        f"labcairn resolved to {resolved}, outside the clean venv at {venv_dir}. "
        "The editable install of the working tree shadowed the wheel, so this "
        "assertion proved nothing."
    )
    assert Path(report["core"]).resolve().is_relative_to(venv_dir.resolve()), (
        "labcairn.core did not resolve inside the clean venv"
    )
    assert report["version"] == "0.1.0"


# ===========================================================================
# 4. IDE / code index
# ===========================================================================


def test_vscode_excludes_reference_paths(repo_root: Path) -> None:
    """Both keys, every case variant.

    A ``.vscode/settings.json`` glob has no runtime to exercise — the JSON key
    *is* the behaviour, so this is a configuration assertion by nature. It is
    here because an unexcluded reference tree is exactly what gets indexed into
    search, embeddings and assistant context by an editor.
    """
    settings_path = repo_root / ".vscode" / "settings.json"
    if not settings_path.is_file():
        pytest.skip(f"{settings_path} does not exist; no IDE config to assert on")

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    for key in ("files.exclude", "search.exclude", "files.watcherExclude"):
        excludes = settings.get(key)
        assert isinstance(excludes, dict) and excludes, (
            f".vscode/settings.json must define a non-empty {key!r} object"
        )
        missing = [
            stem
            for stem in CASE_VARIANT_STEMS
            if not any(
                pattern.startswith(f"**/{stem}") and enabled
                for pattern, enabled in excludes.items()
            )
        ]
        assert not missing, f"{key!r} does not exclude these reference paths: {missing}"

    # `search.useIgnoreFiles` makes gitignore authoritative for search; without
    # it the hand-written globs are the only thing standing between an editor
    # and a third-party source tree.
    assert settings.get("search.useIgnoreFiles") is True, (
        "search.useIgnoreFiles must be true so search.exclude defers to the Git "
        "exclude rules instead of only the hand-maintained globs"
    )


# ===========================================================================
# 5. CI workflows — inert until T06 lands
# ===========================================================================

#: Tokens that mean "this job cannot run without a reference clone". If one of
#: these appears outside an exclusion context, the "external contributor can
#: build without them" claim is false.
UPSTREAM_CLONE_TOKENS: Final = (
    "labcairn-upstreams",
    "checkout_upstreams.py",
)

#: Contexts in which those tokens are legitimate: a paths-ignore glob, an
#: exclude glob, or prose in a comment explaining that they must not be used.
UPSTREAM_TOKENS_ALLOWED_CONTEXTS: Final = ("paths-ignore", "paths_ignore", "exclude", "#")


@pytest.fixture(scope="session")
def workflows_dir(repo_root: Path) -> Path:
    """The CI half of the gate, active only once ``.github/workflows/`` exists.

    ``.github/workflows/**`` is owned by T06. Until that directory lands these
    four tests skip — a skip, not a pass, and it is reported by ``-ra``. The
    moment T06 lands they start asserting. They are not written to be satisfiable
    by an absent directory.
    """
    directory = repo_root / ".github" / "workflows"
    if not directory.is_dir():
        pytest.skip(
            ".github/workflows/ does not exist yet (LC-P1-01 T06 not landed): the "
            "CI-side half of the reference-exclusion gate is INERT, not passing."
        )
    if not any(directory.glob("*.y*ml")):
        pytest.skip(".github/workflows/ exists but contains no workflow files")
    return directory


def _workflow_files(workflows: Path) -> list[Path]:
    return sorted([*workflows.glob("*.yml"), *workflows.glob("*.yaml")])


def _lines_outside_exclusion_contexts(lines: Sequence[str]) -> list[tuple[int, str]]:
    """Yield ``(lineno, text)`` for lines that are not part of an exclusion block.

    A token may legitimately appear in ``paths-ignore:`` / ``exclude:`` globs and
    in comments. Everything else is a real reference to a clone.
    """
    kept: list[tuple[int, str]] = []
    in_exclusion_block = False
    exclusion_indent = -1
    for index, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip())
        if stripped.startswith((*UPSTREAM_TOKENS_ALLOWED_CONTEXTS, "#")):
            in_exclusion_block = "exclude" in stripped or stripped.startswith("#")
            exclusion_indent = indent
            continue
        if in_exclusion_block:
            if stripped and indent > exclusion_indent:
                continue  # a continuation of the exclusion list
            in_exclusion_block = False
        kept.append((index, raw))
    return kept


def test_no_workflow_requires_an_upstream_checkout(workflows_dir: Path) -> None:
    """The "external contributor has no clone" gate, for CI.

    Amendment gate 6 and the last unchecked LC-P1-00 acceptance item. A CI job
    that clones ``../labcairn-upstreams`` works on exactly one machine and fails
    on every runner and every external contributor — a green local run is
    possible, a green CI run is not.
    """
    offenders: list[str] = []
    for path in _workflow_files(workflows_dir):
        lines = path.read_text(encoding="utf-8").splitlines()
        for lineno, raw in _lines_outside_exclusion_contexts(lines):
            lowered = raw.lower()
            if any(token in lowered for token in UPSTREAM_CLONE_TOKENS):
                offenders.append(f"{path.relative_to(workflows_dir)}:{lineno}: {raw.strip()}")
    assert not offenders, (
        "workflows reference a reference clone outside an exclusion context:\n  "
        + "\n  ".join(offenders)
        + "\nCI must build and test from a fresh checkout with no reference clones present."
    )


def _artifact_and_cache_path_values(text: str) -> list[tuple[int, str]]:
    """Extract the ``path:`` values of every ``upload-artifact`` / ``cache`` step.

    A deliberately small line-oriented scan, not a YAML parse: PyYAML is not a
    project dependency, and the property under test is "does this step's path
    list mention the excluded families", which a ``path:``-line scan answers.
    The scanner itself is verified by
    :func:`test_artifact_path_scanner_reads_inline_and_block_forms`.
    """
    values: list[tuple[int, str]] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        lowered = line.lower()
        if "actions/upload-artifact@" not in lowered and "actions/cache@" not in lowered:
            index += 1
            continue
        step_indent = len(line) - len(line.lstrip())
        index += 1
        while index < len(lines):
            current = lines[index]
            if not current.strip():
                index += 1
                continue
            current_indent = len(current) - len(current.lstrip())
            if current_indent <= step_indent:
                break  # dedented out of the step block
            stripped = current.strip()
            if stripped.startswith("path:"):
                inline = stripped[len("path:") :].strip()
                if inline and inline not in {">", "|", ">-", "|-"}:
                    values.append((index + 1, inline))
                else:
                    # block sequence form
                    probe = index + 1
                    while probe < len(lines):
                        entry = lines[probe]
                        if not entry.strip():
                            probe += 1
                            continue
                        entry_indent = len(entry) - len(entry.lstrip())
                        if entry_indent <= current_indent:
                            break
                        values.append((probe + 1, entry.strip().lstrip("- ").strip()))
                        probe += 1
                    index = probe
                    continue
            index += 1
    return values


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "      - uses: actions/upload-artifact@v4\n"
            "        with:\n"
            "          name: dist\n"
            "          path: dist/\n",
            ["dist/"],
        ),
        (
            "      - uses: actions/upload-artifact@v4\n"
            "        with:\n"
            "          path: |\n"
            "            dist/\n"
            "            !**/_references*/**\n"
            "          name: dist\n",
            ["dist/", "!**/_references*/**"],
        ),
        (
            "      - uses: actions/cache@v4\n"
            "        with:\n"
            "          path: uv-cache\n"
            "          key: ${{ hashFiles('uv.lock') }}\n",
            ["uv-cache"],
        ),
        ("      - uses: actions/checkout@v4\n        with:\n          path: .\n", []),
        (
            "      - uses: actions/upload-artifact@v4\n"
            "        with:\n"
            "          path: dist/\n"
            "      - run: echo done\n",
            ["dist/"],
        ),
    ],
)
def test_artifact_path_scanner_reads_inline_and_block_forms(text: str, expected: list[str]) -> None:
    """Verify the scanner before relying on it.

    Without this, a scanner that returned ``[]`` would make
    :func:`test_upload_artifact_and_cache_steps_exclude_reference_paths` pass
    unconditionally — the scanner's own version of a vacuous assertion.
    """
    assert [value for _, value in _artifact_and_cache_path_values(text)] == expected


def test_upload_artifact_and_cache_steps_exclude_reference_paths(workflows_dir: Path) -> None:
    """Checklist row: an artifact is a source bundle and carries what it is handed.

    Every ``actions/upload-artifact`` and ``actions/cache`` path must either name
    a narrow directory (``dist/``, a cache key directory) or carry an explicit
    negative glob for the reference families. A bare ``path: .`` is the case that
    matters: it sweeps the whole working tree into an artifact.
    """
    offenders: list[str] = []
    for path in _workflow_files(workflows_dir):
        text = path.read_text(encoding="utf-8")
        for lineno, value in _artifact_and_cache_path_values(text):
            lowered = value.lower()
            if any(prefix in lowered for prefix in REFERENCE_SEGMENT_PREFIXES):
                continue  # explicit exclusion — the intended shape
            if value.strip() in {".", "./", "**", "*"}:
                offenders.append(
                    f"{path.relative_to(workflows_dir)}:{lineno}: {value!r} sweeps the "
                    "whole working tree into an artifact"
                )
    assert not offenders, (
        "artifact/cache steps that would capture reference material:\n  " + "\n  ".join(offenders)
    )


# ===========================================================================
# 6. Standing limits that configuration cannot close
# ===========================================================================


def test_the_sibling_reference_clone_directory_is_outside_this_repository(
    repo_root: Path,
) -> None:
    """Record the one thing no in-repo rule can enforce.

    ``.gitignore`` applies only below its own directory, so it says nothing about
    ``../labcairn-upstreams/``. If anyone runs ``git init`` at ``E:/`` the sibling
    clones become tracked content of *some* repository immediately, and no file
    in this repository can prevent it. This test cannot fix that; it can only
    fail loudly if the guard conditions ever change in a way a reviewer should
    look at (the reference directory becoming a sibling *inside* the repo tree).
    """
    parent = repo_root.parent
    assert parent != repo_root, "the repository has no parent directory to check"
    # Merely assert the shape: the sibling must not be inside the working tree.
    assert not (repo_root / "labcairn-upstreams").exists(), (
        "a reference clone directory exists INSIDE the repository at "
        "repo/labcairn-upstreams. The documented layout prefers the sibling "
        "directory ../labcairn-upstreams; an in-repo clone needs the ignore rules "
        "to be holding, and this test file cannot confirm that from the index alone."
    )


def test_no_module_level_dependency_on_the_sibling_reference_directory(repo_root: Path) -> None:
    """This file must not become a hard dependency on the clones existing.

    LC-P1-00's last open acceptance item and amendment gate 6: an external
    contributor with no reference clones must be able to build and test. The
    probe build plants its own synthetic files, so nothing here reads the
    sibling directory. This asserts the source-level version of that: the
    project never names a sibling reference path as something it opens, reads or
    requires.
    """
    product = repo_root / "src"
    offenders: list[str] = []
    for path in sorted([*product.rglob("*.py")]):
        if _ignore_cache_entries().intersection(path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            # Prose in a docstring or comment may name the directory; code may not.
            if "labcairn-upstreams" not in stripped.lower():
                continue
            if stripped.startswith(("#", '"""', "'''")):
                continue
            offenders.append(f"{path.relative_to(repo_root)}:{lineno}: {stripped}")
    assert not offenders, (
        "product code references the sibling reference directory:\n  "
        + "\n  ".join(offenders)
        + "\nProduct code must not require reference clones to exist."
    )


def test_workflows_do_not_use_no_git_secret_scan(workflows_dir: Path) -> None:
    """Referenced by .gitleaks.toml, which claims a sibling assertion guards this.

    A whole-disk scan (``gitleaks dir`` / ``--no-git``) would sweep the sibling
    reference clones — third-party source trees carrying their own token-shaped
    strings — producing findings LabCairn cannot act on and cannot distinguish
    from its own. The scan must stay in git mode so it sees tracked files only.
    """
    offenders: list[str] = []
    for path in _workflow_files(workflows_dir):
        text = path.read_text(encoding="utf-8")
        for lineno, raw in enumerate(text.splitlines(), 1):
            stripped = raw.strip()
            if stripped.startswith("#"):
                continue
            lowered = stripped.lower()
            if "--no-git" in lowered or "gitleaks dir" in lowered:
                offenders.append(f"{path.name}:{lineno}: {stripped}")
    assert not offenders, (
        "secret scan must stay in git mode; whole-disk scanning would sweep the "
        "sibling reference clones:\n" + "\n".join(offenders)
    )
