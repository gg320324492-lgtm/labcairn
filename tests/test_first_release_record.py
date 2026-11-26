"""The first runnable release record, watched.

``docs/releases/v0.1.0.json`` is Phase 4's first runnable version's
structured record -- the first real record under ``docs/releases/``, written
with the tool the fourth batch delivered.  A record nobody measures is prose
with a ``.json`` suffix, so this file measures the one property that makes it
a release record rather than a wish:

- the seven elements Phase 4 §10 requires are present and non-empty;
- the ``commit`` is a commit in this repository's history -- an ancestor of
  ``HEAD``, not a hash copied from somewhere;
- ``created_at`` is a UTC ISO-8601 timestamp that does not sit in the future;
- the ``version`` matches the file name, so the record cannot be renamed
  past its own content;
- the artifact digest is the sha256 the installer build measured from the
  produced bytes, and the build's own companion record says so -- the
  installer's own version line still reads 0.0.3, and the record names that
  rather than glossing over it;
- the version number and date are announced as **confirmed by the owner on
  2026-11-24**, which is plan §12's third decision;
- the tool's own ``check`` subcommand accepts the record (exit code 0).

The witnesses read this checkout's record but never write into the
repository: the one that runs the ``check`` subcommand copies the record
into a temporary directory first.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

#: Where the first release record lives, relative to the repository root.
RECORD_RELATIVE = Path("docs") / "releases" / "v0.1.0.json"

#: The version the record names -- and the file name stem it must match.
VERSION = "v0.1.0"

#: The migration range the data-compatibility column must name, measured:
#: the Phase 4 store work runs from 0025 (trajectory index) to 0030 (rule
#: sharing), and both ends belong in the record's data column.
FIRST_PHASE4_MIGRATION = "0025"
LAST_PHASE4_MIGRATION = "0030"

#: The release-record script, driven the way its callers drive it.
RELEASE_SCRIPT = Path("scripts") / "release_record.py"


def _record(repo_root: Path) -> dict[str, Any]:
    """The parsed first release record, read fresh on every call."""
    path = repo_root / RECORD_RELATIVE
    assert path.is_file(), f"the first release record is missing: {path}"
    parsed: Any = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(parsed, dict), "the release record must be a JSON object"
    return parsed


def _nonempty(value: object) -> bool:
    """Whether the value is a string with something besides whitespace."""
    return isinstance(value, str) and value.strip() != ""


def _git(repo_root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run git in the repository and return the completed process."""
    return subprocess.run(
        ["git", *arguments],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def test_the_first_release_record_exists_and_parses(repo_root: Path) -> None:
    """The record file exists, parses, and names the version it was cut for."""
    record = _record(repo_root)
    assert record.get("version") == VERSION, (
        f"the record must name {VERSION!r}, found {record.get('version')!r}"
    )


def test_the_seven_elements_are_present(repo_root: Path) -> None:
    """Every element Phase 4 §10 requires is present and non-empty.

    A record missing one element is not a release record; the tool refuses
    to write one, and this witness refuses to read one.
    """
    record = _record(repo_root)

    # 1. the version number and the source commit
    assert _nonempty(record.get("version")), "element 1: version is missing or empty"
    assert _nonempty(record.get("commit")), "element 1: commit is missing or empty"

    # 2. the artifact digest -- an explicit null with its reason, or a digest
    assert "artifact_sha256" in record, "element 2: artifact_sha256 is missing"
    digest = record.get("artifact_sha256")
    if digest is None:
        assert _nonempty(record.get("artifact_sha256_reason")), (
            "element 2: artifact_sha256 is null without a non-empty reason"
        )
    else:
        assert isinstance(digest, str) and len(digest) == 64, (
            "element 2: artifact_sha256 is not a sha256 digest"
        )

    # 3. data and API compatibility, two columns
    compatibility = record.get("compatibility")
    assert isinstance(compatibility, dict), "element 3: compatibility is not an object"
    assert _nonempty(compatibility.get("data")), "element 3: data compatibility is empty"
    assert _nonempty(compatibility.get("api")), "element 3: API compatibility is empty"

    # 4-6. added, fixed, known_limits -- non-empty lists of non-empty strings
    for field in ("added", "fixed", "known_limits"):
        value = record.get(field)
        assert isinstance(value, list) and value, f"element: {field} is missing or empty"
        assert all(_nonempty(item) for item in value), f"element: {field} holds an empty string"

    # 7. rollback
    assert _nonempty(record.get("rollback")), "element 7: rollback is missing or empty"

    # bookkeeping: the branch and the timestamp ride along
    assert _nonempty(record.get("branch")), "the branch field is missing or empty"
    assert _nonempty(record.get("created_at")), "created_at is missing or empty"


def test_the_commit_is_in_this_repositorys_history(repo_root: Path) -> None:
    """The recorded commit exists in git, and is an ancestor of HEAD.

    ``git cat-file -e`` proves the object exists; ``git merge-base`` proves
    the record's tree grew out of this history rather than naming a hash
    from somewhere else.  A record cut on a batch branch points at that
    branch's commit, which main does not contain until the merge lands --
    being an ancestor of HEAD is the property that survives both states.
    """
    record = _record(repo_root)
    commit = record["commit"]
    assert isinstance(commit, str)

    exists = _git(repo_root, "cat-file", "-e", f"{commit}^{{commit}}")
    assert exists.returncode == 0, (
        f"the recorded commit {commit} is not an object in this repository: {exists.stderr.strip()}"
    )

    ancestor = _git(repo_root, "merge-base", "--is-ancestor", commit, "HEAD")
    assert ancestor.returncode == 0, (
        f"the recorded commit {commit} exists but is not an ancestor of HEAD, "
        "so this record does not describe the tree it sits in"
    )


def test_created_at_is_a_valid_utc_timestamp(repo_root: Path) -> None:
    """The timestamp is UTC ISO-8601, and does not sit in the future.

    ``created_at`` is written by the tool, never typed by hand -- so it must
    parse, carry a UTC offset, and predate the moment this witness runs by
    more than the clock-skew allowance.
    """
    record = _record(repo_root)
    created_at = record.get("created_at")
    assert isinstance(created_at, str)

    parsed = datetime.fromisoformat(created_at)
    assert parsed.tzinfo is not None, "created_at carries no timezone"
    assert parsed.utcoffset() == timedelta(0), f"created_at is not UTC: offset {parsed.utcoffset()}"
    assert parsed <= datetime.now(UTC) + timedelta(minutes=5), (
        "created_at sits in the future, which no honest measurement can"
    )

    # The record was re-anchored to the post-batch-7 HEAD after the owner
    # confirmed the version and date. The timestamp is when the record was
    # first cut; the commit it names is checked for existence elsewhere.


def test_the_version_matches_the_file_name(repo_root: Path) -> None:
    """The version and the file name stem are the same string.

    The file name is not decoration: ``check`` verifies this match, so a
    record cannot be renamed past its own content.
    """
    record = _record(repo_root)
    path = repo_root / RECORD_RELATIVE
    assert record.get("version") == path.stem, (
        f"version {record.get('version')!r} does not match the file name stem {path.stem!r}"
    )
    assert path.stem == VERSION


def test_the_artifact_digest_is_the_measured_installer_digest(repo_root: Path) -> None:
    """The digest is the one the build measured, and the build's own record says so.

    **Why the digest is not simply present.** A field carrying a plausible
    64-character string is not a measurement. The release record's digest
    must be the digest the installer build actually measured from the
    produced bytes, and the companion record
    (``docs/releases/v0.1.0-artifact.json``) is where that measurement
    lives -- with the build's commands, the toolchain versions and the
    evidence. So the witness compares the two records against each other:
    a digest in the release record that no build produced is a digest of
    nothing.

    **And the version line is named.** The installer's own name and
    product version still read 0.0.3, because the shell's package
    manifest was not bumped for this workbench release. That is the
    owner's call to make, and until it is made the release record has to
    say so rather than let a reader infer that the installer's name
    agrees with the version it carries.
    """
    record = _record(repo_root)
    digest = record.get("artifact_sha256")
    assert isinstance(digest, str) and len(digest) == 64, (
        f"the release record must carry the installer's measured sha256, found {digest!r}"
    )
    reason = record.get("artifact_sha256_reason")
    assert _nonempty(reason), "the digest needs the record that says what it is"
    assert isinstance(reason, str)

    companion_path = repo_root / "docs" / "releases" / "v0.1.0-artifact.json"
    assert companion_path.is_file(), (
        f"the build's own measurement record is missing: {companion_path}"
    )
    companion: Any = json.loads(companion_path.read_text(encoding="utf-8"))
    assert isinstance(companion, dict), "the companion record must be a JSON object"

    measured = companion.get("artifact_sha256")
    assert isinstance(measured, str) and len(measured) == 64, (
        f"the build record carries no measured digest: {measured!r}"
    )
    assert digest == measured, (
        "the release record's digest is not the digest the build measured: "
        f"{digest!r} against {measured!r}"
    )

    # The build measured from the recorded commit, so the two records
    # describe the same tree.
    assert companion.get("commit") == record.get("commit"), (
        "the build was made from a different commit than the record names: "
        f"{companion.get('commit')!r} against {record.get('commit')!r}"
    )

    # The bytes are counted, so the digest is not the digest of an empty file.
    size = companion.get("artifact_bytes")
    assert isinstance(size, int) and size > 0, (
        f"the build record carries no artifact size: {size!r}"
    )

    # The unsettled version line is named rather than glossed over.
    #
    # **The version is read from the build's own record, not written into
    # this test.** The installer's declared version is a fact about the
    # artifact, and the artifact changes: a version bump makes the name
    # `LabCairn Setup 0.1.0.exe` and the digest new, and a witness that
    # spelled the old number out would go red on the very change it was
    # written to allow. So the test reads the number the build measured and
    # requires the record to name **that** number when it differs from the
    # version the record calls itself -- which is the case the release
    # record has to be honest about, and the case that disappears the
    # moment the two agree.
    declared = companion.get("artifact_declared_version")
    assert isinstance(declared, str) and declared.strip(), (
        f"the build record carries no declared artifact version: {declared!r}"
    )
    if declared.strip().lstrip("v") != VERSION.lstrip("v"):
        assert declared in reason, (
            "the record must name the installer's own version line, which "
            f"reads {declared!r} while the record calls itself {VERSION!r}: "
            "the difference is the owner's to settle, and the record has to "
            "say so rather than let a reader infer the names agree"
        )


def test_the_compatibility_columns_name_the_measured_surface(repo_root: Path) -> None:
    """The data column names the Phase 4 migration range; the API column
    names the route surface.

    These are the two facts the record was asked to state, and both are
    measurable in this tree: the migration chain runs 0025..0030, and the
    API mounts one router whose /health route is the surface's anchor.
    """
    record = _record(repo_root)
    compatibility = record["compatibility"]
    data = compatibility["data"]
    api = compatibility["api"]
    assert isinstance(data, str) and isinstance(api, str)

    assert FIRST_PHASE4_MIGRATION in data, (
        f"the data column must name the first Phase 4 migration ({FIRST_PHASE4_MIGRATION})"
    )
    assert LAST_PHASE4_MIGRATION in data, (
        f"the data column must name the last Phase 4 migration ({LAST_PHASE4_MIGRATION})"
    )
    assert "API" in api and "routes" in api, (
        "the API column must name the route surface the web and CLI call"
    )


def test_the_owner_confirmation_is_announced(repo_root: Path) -> None:
    """The record and the releases README both announce the confirmation.

    The owner confirmed v0.1.0 and the target date on 2026-11-24 (plan §12's
    third decision). The record and the README must say so rather than
    leave the old pending marker; a later rename goes through create
    --force, never by silently editing this file.
    """
    record = _record(repo_root)
    data = json.dumps(record)
    assert "confirmed" in data.lower(), (
        "the record must announce the owner's confirmation of the version and date"
    )
    assert "signature" in data.lower(), (
        "the record must still name the pending authorisation signature as a limit"
    )

    readme = repo_root / "docs" / "releases" / "README.md"
    assert readme.is_file(), "the releases README is missing"
    text = readme.read_text(encoding="utf-8")
    assert "confirmed by the owner on 2026-11-24" in text, (
        "the README must announce that v0.1.0's version and date are confirmed"
    )
    assert VERSION in text, "the README must name the v0.1.0 record"


def test_the_tools_check_subcommand_accepts_the_record(repo_root: Path, tmp_path: Path) -> None:
    """``release_record.py check`` exits 0 on this record.

    The check runs against a **copy** in ``tmp_path`` -- the witness reads
    the repository, it does not write into it -- with the working directory
    set to the repository so the commit lookup measures this history.
    """
    source = repo_root / RECORD_RELATIVE
    copy = tmp_path / source.name
    copy.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(RELEASE_SCRIPT), "check", str(copy)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert result.returncode == 0, (
        f"the tool's own check refused the record (exit {result.returncode}):\n"
        f"{result.stdout}\n{result.stderr}"
    )
    assert "OK" in result.stdout, f"the check passed but did not say so: {result.stdout!r}"


def test_the_record_passes_the_tools_own_validator(repo_root: Path) -> None:
    """The in-process validator reports no problems for this record.

    This is the same measurement the subcommand makes, made directly -- so
    a regression in the record is named element by element here, not just
    reported as a non-zero exit.
    """
    spec_path = repo_root / RELEASE_SCRIPT
    assert spec_path.is_file(), f"the release tool is missing: {spec_path}"

    import importlib.util

    spec = importlib.util.spec_from_file_location("release_record_for_first_release", spec_path)
    assert spec is not None and spec.loader is not None, (
        "scripts/release_record.py could not be loaded as a module"
    )
    module: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    record = _record(repo_root)
    problems = module.record_problems(record, expected_stem=VERSION, verify_commit=True)
    assert problems == [], "the release tool's own validator names these problems: " + "; ".join(
        problems
    )


@pytest.mark.parametrize(
    ("field", "minimum"),
    [("added", 5), ("fixed", 3), ("known_limits", 3)],
)
def test_the_narrative_fields_carry_substance(repo_root: Path, field: str, minimum: int) -> None:
    """The narrative fields are not stubs: each carries real entries.

    A release record with one-word entries describes nothing.  The first
    record documents the six batches' delivery, so each narrative field
    carries at least this many statements.
    """
    record = _record(repo_root)
    value = record.get(field)
    assert isinstance(value, list) and len(value) >= minimum, (
        f"{field} carries {len(value) if isinstance(value, list) else 0} "
        f"entries, fewer than the {minimum} the delivery record needs"
    )
