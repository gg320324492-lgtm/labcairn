"""The structured release record, watched.

``scripts/release_record.py`` writes and checks the JSON files under
``docs/releases/`` that carry the seven elements Phase 4 §10 requires of
every version.  A record the tool cannot check is prose with a suffix, and
a tool that accepts its own incomplete output is no gate at all.

So this file drives the script the way its callers do -- through its own
``main``, over real files in a temporary repository -- and witnesses the
properties that make the records trustworthy:

- ``create`` writes a record with all seven elements present, and the
  measured fields come from git and the artifact's bytes, not from the
  notes.
- a version that already has a record is refused unless ``--force``.
- ``check`` accepts a complete record and names *every* problem in an
  incomplete one -- the seven elements, the commit's presence in the
  repository's history, and the timestamp's UTC ISO-8601 shape.

The witnesses run the script inside a temporary git repository, so nothing
here reads or writes this checkout's own ``docs/releases/``.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import subprocess
import sys
from collections.abc import Iterator
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "release_record.py"

_spec = importlib.util.spec_from_file_location("release_record_under_test", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None, (
    "scripts/release_record.py could not be loaded as a module"
)
release_record: ModuleType = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release_record)
release_record_main = release_record.main


def _run(*arguments: str) -> tuple[int, str, str]:
    """Run the tool in-process, capturing stdout and stderr."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code: int = release_record_main(list(arguments))
    return code, out.getvalue(), err.getvalue()


# A commit hash that is 40 hex digits and not in any temporary repository.
FOREIGN_COMMIT = "0123456789abcdef0123456789abcdef01234567"


# ---------------------------------------------------------------------------
# The temporary repository
# ---------------------------------------------------------------------------


def _git(repo: Path, *arguments: str) -> str:
    """Run one git command in *repo* and return its stripped stdout."""
    result = subprocess.run(
        ["git", *arguments],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return result.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A temporary git repository, with the tool's idea of "here" pointed at it.

    The script resolves the repository from the current directory, so the
    fixture changes directory for the duration: every ``create`` call lands
    in the temporary repository's ``docs/releases/``, and this checkout's
    own records are never read or written.
    """
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "Release Record Witness")
    _git(tmp_path, "config", "user.email", "witness@example.invalid")
    source = tmp_path / "src"
    source.mkdir()
    (source / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "src/module.py")
    _git(tmp_path, "commit", "-q", "-m", "The only commit")
    monkeypatch.chdir(tmp_path)
    yield tmp_path


def _write_notes(path: Path, payload: dict[str, object]) -> Path:
    """Write a notes file and return its path."""
    notes = path / "notes.json"
    notes.write_text(json.dumps(payload), encoding="utf-8")
    return notes


def _read_record(repo: Path, version: str = "0.2.0") -> dict[str, object]:
    """The record ``create`` wrote for *version*."""
    text = (repo / "docs" / "releases" / f"{version}.json").read_text(encoding="utf-8")
    parsed: object = json.loads(text)
    assert isinstance(parsed, dict), "the record file did not hold a JSON object"
    return parsed


def _record_field(record: dict[str, object], key: str) -> dict[str, object]:
    """One nested object column of a record, typed for mypy."""
    value = record[key]
    assert isinstance(value, dict), f"record[{key!r}] is not an object"
    return value


# ---------------------------------------------------------------------------
# create: a complete record, measured where it says it was measured
# ---------------------------------------------------------------------------


def test_create_writes_a_record_with_all_seven_elements(repo: Path) -> None:
    """A created record carries every element, plus branch and created_at."""
    code, _out, err = _run(
        "create",
        "--version",
        "0.2.0",
        "--artifact-reason",
        "source-only release; no installer is built for this version",
        "--data-compatibility",
        "reads the v1 store schema",
        "--api-compatibility",
        "the /review routes of 0.1.x",
        "--added",
        "the multi-source retrieval desk",
        "--fixed",
        "the suggestion loop double-label",
        "--known-limits",
        "the real-model smoke is not run offline",
        "--rollback",
        "reinstall 0.1.0 from the previous tag",
    )
    assert code == 0, f"create refused: {err}"
    record = _read_record(repo)
    assert record["version"] == "0.2.0"
    assert record["commit"] == _git(repo, "rev-parse", "HEAD")
    assert record["branch"] == _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    assert record["artifact_sha256"] is None
    assert record["compatibility"] == {
        "data": "reads the v1 store schema",
        "api": "the /review routes of 0.1.x",
    }
    assert record["added"] == ["the multi-source retrieval desk"]
    assert record["fixed"] == ["the suggestion loop double-label"]
    assert record["known_limits"] == ["the real-model smoke is not run offline"]
    assert record["rollback"] == "reinstall 0.1.0 from the previous tag"
    # created_at ends in UTC: a Z suffix or a +00:00 offset, never a naive stamp.
    created_at = record["created_at"]
    assert isinstance(created_at, str), "created_at is not a string"
    assert created_at.endswith(("+00:00", "Z")), f"created_at is not stamped UTC: {created_at!r}"


def test_create_hashes_the_artifact_from_its_bytes(repo: Path) -> None:
    """The recorded digest is the artifact's own sha256, measured now."""
    artifact = repo / "dist" / "labcairn-0.2.0-py3-none-any.whl"
    artifact.parent.mkdir()
    artifact.write_bytes(b"the wheel's bytes")
    code, _out, err = _run(
        "create",
        "--version",
        "0.2.0",
        "--artifact",
        str(artifact),
        "--data-compatibility",
        "unchanged",
        "--api-compatibility",
        "unchanged",
        "--added",
        "the wheel",
        "--fixed",
        "the missing artifact record",
        "--known-limits",
        "none",
        "--rollback",
        "delete the wheel",
    )
    assert code == 0, f"create refused: {err}"
    record = _read_record(repo)
    expected = hashlib.sha256(b"the wheel's bytes").hexdigest()
    assert record["artifact_sha256"] == expected
    assert record["artifact_sha256_reason"] is None


def test_create_takes_the_commit_from_git_not_from_the_notes(repo: Path) -> None:
    """The measured fields are git's, however wrong the notes' claims are."""
    notes = _write_notes(
        repo,
        {
            "commit": FOREIGN_COMMIT,  # the notes lie about the commit
            "artifact_sha256_reason": "source-only release",
            "compatibility": {"data": "from the notes", "api": "from the notes"},
            "added": ["from the notes"],
            "fixed": ["from the notes"],
            "known_limits": ["from the notes"],
            "rollback": "from the notes",
        },
    )
    code, _out, err = _run("create", "--version", "0.2.0", "--notes", str(notes))
    assert code == 0, f"create refused: {err}"
    record = _read_record(repo)
    assert record["commit"] == _git(repo, "rev-parse", "HEAD"), (
        "create took the commit from the notes instead of measuring it in git"
    )
    # The author's statements, by contrast, are the notes' to make.
    assert _record_field(record, "compatibility")["data"] == "from the notes"
    assert record["rollback"] == "from the notes"


def test_create_refuses_a_duplicate_version_without_force(repo: Path) -> None:
    """A second record for one version is refused until --force says otherwise."""
    arguments = (
        "create",
        "--version",
        "0.2.0",
        "--artifact-reason",
        "source-only release",
        "--data-compatibility",
        "d",
        "--api-compatibility",
        "a",
        "--added",
        "x",
        "--fixed",
        "y",
        "--known-limits",
        "z",
        "--rollback",
        "r",
    )
    code, _out, err = _run(*arguments)
    assert code == 0, f"the first create refused: {err}"
    first = _read_record(repo)
    code, _out, err = _run(*arguments)
    assert code == 1, "the duplicate create was not refused"
    assert "already exists" in err
    code, _out, err = _run(*arguments, "--force")
    assert code == 0, f"--force was refused: {err}"
    assert str(_read_record(repo)["created_at"]) >= str(first["created_at"])


def test_create_requires_a_reason_when_no_artifact_is_given(repo: Path) -> None:
    """A null digest without a stated reason is refused at write time."""
    code, _out, err = _run(
        "create",
        "--version",
        "0.2.0",
        "--data-compatibility",
        "d",
        "--api-compatibility",
        "a",
        "--added",
        "x",
        "--fixed",
        "y",
        "--known-limits",
        "z",
        "--rollback",
        "r",
    )
    assert code == 1, "create accepted a record with no artifact and no reason"
    assert "--artifact-reason" in err
    assert not (repo / "docs" / "releases" / "0.2.0.json").exists(), (
        "the refused record was written anyway"
    )
    code, _out, _err = _run(
        "create",
        "--version",
        "0.2.0",
        "--artifact-reason",
        "source-only release; no installer is built for this version",
        "--data-compatibility",
        "d",
        "--api-compatibility",
        "a",
        "--added",
        "x",
        "--fixed",
        "y",
        "--known-limits",
        "z",
        "--rollback",
        "r",
    )
    assert code == 0
    assert (
        _read_record(repo)["artifact_sha256_reason"]
        == "source-only release; no installer is built for this version"
    )


def test_create_refuses_a_version_that_could_name_a_path(repo: Path) -> None:
    """A version is a name, never a traversal."""
    code, _out, err = _run(
        "create",
        "--version",
        "../evil",
        "--data-compatibility",
        "d",
        "--api-compatibility",
        "a",
        "--added",
        "x",
        "--fixed",
        "y",
        "--known-limits",
        "z",
        "--rollback",
        "r",
    )
    assert code == 1, "a path-traversing version was accepted"
    assert "not a version string" in err


@pytest.mark.parametrize("suffix", [".yaml", ".yml"])
def test_create_reads_yaml_notes(repo: Path, suffix: str) -> None:
    """A YAML notes file is read as readily as a JSON one."""
    notes = repo / f"notes{suffix}"
    notes.write_text(
        "artifact_sha256_reason: source-only release\n"
        "compatibility:\n"
        "  data: the v2 store schema\n"
        "  api: unchanged\n"
        "added:\n"
        "  - the yaml notes\n"
        "fixed:\n"
        "  - the json-only reader\n"
        "known_limits:\n"
        "  - still no windows installer\n"
        "rollback: revert the tag\n",
        encoding="utf-8",
    )
    code, _out, err = _run("create", "--version", "0.2.0", "--notes", str(notes))
    assert code == 0, f"create refused the YAML notes: {err}"
    record = _read_record(repo)
    assert _record_field(record, "compatibility")["data"] == "the v2 store schema"
    assert record["added"] == ["the yaml notes"]


# ---------------------------------------------------------------------------
# check: the complete record passes, and every broken one names its problems
# ---------------------------------------------------------------------------


def _complete_record(repo: Path, **overrides: object) -> dict[str, object]:
    """A record that passes check, with the caller's fields replaced."""
    record: dict[str, object] = {
        "version": "0.2.0",
        "commit": _git(repo, "rev-parse", "HEAD"),
        "branch": "main",
        "created_at": "2026-11-24T12:00:00+00:00",
        "artifact_sha256": hashlib.sha256(b"the wheel").hexdigest(),
        "artifact_sha256_reason": None,
        "compatibility": {"data": "the v1 store schema", "api": "the 0.1 routes"},
        "added": ["one capability"],
        "fixed": ["one issue"],
        "known_limits": ["one limit"],
        "rollback": "reinstall 0.1.0",
    }
    record.update(overrides)
    return record


def _write_record(repo: Path, record: object, version: str = "0.2.0") -> Path:
    """Write a record file the way a release author would."""
    path = repo / "docs" / "releases" / f"{version}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path


def test_check_accepts_a_complete_record(repo: Path) -> None:
    """The happy path: every element present, the commit real, the time UTC."""
    path = _write_record(repo, _complete_record(repo))
    code, out, err = _run("check", str(path))
    assert code == 0, f"check refused a complete record: {err}"
    assert "OK" in out


def test_check_accepts_an_explicit_null_digest_with_a_reason(repo: Path) -> None:
    """A null artifact digest is honest when the reason stands beside it."""
    record = _complete_record(
        repo,
        artifact_sha256=None,
        artifact_sha256_reason="source-only release",
    )
    path = _write_record(repo, record)
    code, _out, err = _run("check", str(path))
    assert code == 0, f"check refused an explained null digest: {err}"


def test_check_names_every_missing_element_at_once(repo: Path) -> None:
    """A record missing three elements reports three problems, not one."""
    record = _complete_record(repo)
    del record["rollback"]
    del record["compatibility"]
    record["added"] = []
    path = _write_record(repo, record)
    code, out, _err = _run("check", str(path))
    assert code == 1, "check passed a record missing three elements"
    for needle in ("rollback", "compatibility", "added"):
        assert needle in out, f"check did not name the {needle} problem"
    assert out.count("- ") >= 3, "check stopped at the first problem"


def test_check_rejects_a_commit_outside_the_repository(repo: Path) -> None:
    """A commit that is not in this repository's history is caught."""
    record = _complete_record(repo, commit=FOREIGN_COMMIT)
    path = _write_record(repo, record)
    code, out, _err = _run("check", str(path))
    assert code == 1, "check accepted a commit that exists nowhere"
    assert FOREIGN_COMMIT in out


def test_check_rejects_a_naive_and_a_non_utc_timestamp(repo: Path) -> None:
    """created_at must say UTC: no naive stamps, no other offsets."""
    for bad in ("2026-11-24T12:00:00", "2026-11-24T12:00:00+08:00", "not a time"):
        record = _complete_record(repo, created_at=bad)
        path = _write_record(repo, record)
        code, out, _err = _run("check", str(path))
        assert code == 1, f"check accepted the timestamp {bad!r}"
        assert "created_at" in out


def test_check_rejects_a_version_that_disagrees_with_its_file(repo: Path) -> None:
    """A record renamed past its own content is caught by the file name."""
    record = _complete_record(repo, version="0.3.0")
    path = _write_record(repo, record, version="0.2.0")
    code, out, _err = _run("check", str(path))
    assert code == 1, "check accepted a record whose version contradicts its file name"
    assert "0.3.0" in out and "0.2.0" in out


def test_check_rejects_a_malformed_digest(repo: Path) -> None:
    """A digest that is not 64 hex digits is caught, not carried."""
    record = _complete_record(repo, artifact_sha256="deadbeef")
    path = _write_record(repo, record)
    code, out, _err = _run("check", str(path))
    assert code == 1, "check accepted a truncated digest"
    assert "artifact_sha256" in out


def test_check_rejects_a_null_digest_without_a_reason(repo: Path) -> None:
    """The explicit null needs its reason; an unexplained one is caught."""
    record = _complete_record(repo, artifact_sha256=None, artifact_sha256_reason=None)
    path = _write_record(repo, record)
    code, out, _err = _run("check", str(path))
    assert code == 1, "check accepted an unexplained null digest"
    assert "artifact_sha256_reason" in out


def test_check_refuses_a_file_that_is_not_json(repo: Path) -> None:
    """A file that does not parse is a refusal, not a crash."""
    path = repo / "docs" / "releases" / "0.2.0.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    code, _out, err = _run("check", str(path))
    assert code == 1
    assert "not valid JSON" in err


def test_check_refuses_a_missing_file() -> None:
    """A missing record is a one-line error, not a traceback."""
    code, _out, err = _run("check", "docs/releases/9.9.9.json")
    assert code == 1
    assert "does not exist" in err


def test_the_script_runs_standalone() -> None:
    """The console entry point dispatches -- the file is a tool, not a module."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "check", "docs/releases/9.9.9.json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=120,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "does not exist" in result.stderr
