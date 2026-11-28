"""The structured release record: one JSON file per version, seven elements.

A free-text release note can drift away from the tree it describes, and
nothing in the tree notices.  A structured record that this same tool can
check cannot drift silently: every version is one JSON file under
`docs/releases/`, and every record carries the seven elements Phase 4 §10
asks a release to name:

    1. the version number and the source commit it was built from
    2. the installer artifact's sha256, or an explicit null and the reason
    3. the data and API compatibility
    4. what was added
    5. what was fixed
    6. the limits that remain open
    7. how to roll the release back

Two subcommands:

    python scripts/release_record.py create --version 0.2.0 [...]
    python scripts/release_record.py check docs/releases/0.2.0.json

`create` assembles the record from git (the current commit and branch,
measured here, never taken from the notes), an optional artifact file
(hashed, never copied), a JSON or YAML notes file and the command-line
arguments, and refuses a version number that already has a record unless
`--force` is given.  `check` measures a record against the seven elements
and against git, names everything that is missing or wrong, and exits
non-zero when any element fails.

The rule the records obey is the repository's own: **every number and
digest in a record is measured at that release, never carried forward
from an older one.**
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TypeGuard

#: The repository's shared test helpers, for the deadline this
#: script's waits carry.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

from deadline_support import bounded_git

#: Where the records live, relative to the repository root.
RELEASES_SUBDIR = Path("docs") / "releases"

#: A version may name a file, so it must not be able to traverse one.
VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")

#: A digest is 64 lowercase hex digits -- what hashlib writes, nothing else.
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ReleaseRecordError(Exception):
    """A refusal the tool can state in one line."""


# ---------------------------------------------------------------------------
# Git and file helpers
# ---------------------------------------------------------------------------


def _git(*arguments: str) -> str:
    """Run git in the current repository and return its stripped stdout."""
    result = bounded_git(
        ["git", *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise ReleaseRecordError(
            f"git {' '.join(arguments)} failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout.strip()


def _git_succeeds(*arguments: str) -> bool:
    """Whether git accepts the arguments -- for existence probes."""
    result = bounded_git(
        ["git", *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result.returncode == 0


def git_root() -> Path:
    """The repository the current working directory belongs to."""
    return Path(_git("rev-parse", "--show-toplevel"))


def sha256_file(path: Path) -> str:
    """The sha256 of a file's bytes, measured now."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 16), b""):
            digest.update(block)
    return digest.hexdigest()


def utc_now_iso() -> str:
    """The current UTC time as an ISO-8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _nonempty_str(value: object) -> TypeGuard[str]:
    """Whether the value is a string with something besides whitespace."""
    return isinstance(value, str) and value.strip() != ""


def _parse_utc(value: str) -> datetime | None:
    """Parse an ISO-8601 timestamp that is explicitly UTC, or None."""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        return None
    return parsed


# ---------------------------------------------------------------------------
# The notes file: JSON or YAML, inline or on disk
# ---------------------------------------------------------------------------


def _load_yaml(text: str) -> Any:
    """Parse YAML, importing PyYAML only when a YAML notes file appears."""
    try:
        import yaml
    except ImportError as error:
        raise ReleaseRecordError("reading a YAML notes file needs PyYAML installed") from error
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ReleaseRecordError(f"the YAML notes do not parse: {error}") from error


def load_notes(source: str) -> dict[str, Any]:
    """Read a notes payload: inline JSON, a JSON file, or a YAML file."""
    stripped = source.strip()
    if stripped.startswith("{"):
        try:
            parsed: Any = json.loads(stripped)
        except json.JSONDecodeError as error:
            raise ReleaseRecordError(f"the inline notes are not valid JSON: {error}") from error
    else:
        path = Path(source)
        if not path.is_file():
            raise ReleaseRecordError(f"the notes file {source} does not exist")
        text = path.read_text(encoding="utf-8")
        suffix = path.suffix.lower()
        try:
            parsed = _load_yaml(text) if suffix in {".yaml", ".yml"} else json.loads(text)
        except json.JSONDecodeError as error:
            raise ReleaseRecordError(
                f"the notes file {source} is not valid JSON: {error}"
            ) from error
    if not isinstance(parsed, dict):
        raise ReleaseRecordError("the notes must be a JSON or YAML object")
    return parsed


def _first_str(mapping: dict[str, Any], *keys: str) -> str | None:
    """The first non-empty string among the keys, or None."""
    for key in keys:
        value = mapping.get(key)
        if _nonempty_str(value):
            return value
    return None


def apply_notes(record: dict[str, Any], notes: dict[str, Any]) -> None:
    """Fold a notes object into the record.

    Only the statements a release author writes are notes-worthy.  The
    measured fields -- the commit, the branch, the timestamp, the artifact
    digest -- are never taken from the notes: they are measured, not
    asserted.
    """
    compatibility = notes.get("compatibility")
    if isinstance(compatibility, dict):
        target = record["compatibility"]
        target["data"] = _first_str(compatibility, "data", "data_compatibility") or target["data"]
        target["api"] = _first_str(compatibility, "api", "api_compatibility") or target["api"]
    for key in ("added", "fixed", "known_limits"):
        value = notes.get(key)
        if isinstance(value, list):
            record[key] = [item for item in value if _nonempty_str(item)]
    rollback = notes.get("rollback")
    if _nonempty_str(rollback):
        record["rollback"] = rollback
    reason = notes.get("artifact_sha256_reason")
    if _nonempty_str(reason) and record["artifact_sha256"] is None:
        record["artifact_sha256_reason"] = reason


# ---------------------------------------------------------------------------
# The record itself
# ---------------------------------------------------------------------------


def build_record(namespace: argparse.Namespace, artifact: Path | None) -> dict[str, Any]:
    """Assemble the record: git measures, the artifact is hashed, notes fill in."""
    record: dict[str, Any] = {
        "version": namespace.version,
        "commit": _git("rev-parse", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "created_at": utc_now_iso(),
        "artifact_sha256": sha256_file(artifact) if artifact is not None else None,
        "artifact_sha256_reason": (None if artifact is not None else namespace.artifact_reason),
        "compatibility": {"data": None, "api": None},
        "added": [],
        "fixed": [],
        "known_limits": [],
        "rollback": None,
    }
    notes_source: str | None = namespace.notes
    if notes_source:
        apply_notes(record, load_notes(notes_source))
    # The command-line arguments win over the notes file, field by field.
    if namespace.data_compatibility:
        record["compatibility"]["data"] = namespace.data_compatibility
    if namespace.api_compatibility:
        record["compatibility"]["api"] = namespace.api_compatibility
    for argument in ("added", "fixed", "known_limits"):
        values = getattr(namespace, argument)
        if values:
            record[argument] = list(values)
    if namespace.rollback:
        record["rollback"] = namespace.rollback
    return record


def record_problems(record: object, *, expected_stem: str, verify_commit: bool = True) -> list[str]:
    """Every way the record fails the seven elements, each as one line.

    The seven elements are all checked, not just the first one that
    fails -- a record missing three things reports three problems, so a
    release author fixes them in one pass.
    """
    problems: list[str] = []

    def problem(field: str, message: str) -> None:
        problems.append(f"{field}: {message}")

    if not isinstance(record, dict):
        return [f"record: expected a JSON object, found {type(record).__name__}"]

    # 1. the version number and the source commit
    version = record.get("version")
    if not _nonempty_str(version):
        problem("version", "missing or empty")
    elif version != expected_stem:
        problem("version", f"{version!r} does not match the file name stem {expected_stem!r}")

    commit = record.get("commit")
    if not _nonempty_str(commit):
        problem("commit", "missing or empty")
    elif verify_commit and not _git_succeeds("cat-file", "-e", f"{commit}^{{commit}}"):
        problem("commit", f"{commit} is not a commit in this repository's history")

    # 2. the installer artifact digest
    if "artifact_sha256" not in record:
        problem("artifact_sha256", "missing")
    else:
        digest = record["artifact_sha256"]
        if digest is None:
            if not _nonempty_str(record.get("artifact_sha256_reason")):
                problem(
                    "artifact_sha256",
                    "explicitly null without a non-empty artifact_sha256_reason "
                    "(pass --artifact-reason, or set artifact_sha256_reason in the notes)",
                )
        elif not (isinstance(digest, str) and SHA256_PATTERN.match(digest)):
            problem("artifact_sha256", "not a 64-hex-digit sha256 digest")

    # 3. data and API compatibility
    compatibility = record.get("compatibility")
    if not isinstance(compatibility, dict):
        problem("compatibility", "missing or not an object with data and api columns")
    else:
        for column in ("data", "api"):
            if not _nonempty_str(compatibility.get(column)):
                problem(f"compatibility.{column}", "missing or empty")

    # 4-6. added, fixed, known limits
    for field in ("added", "fixed", "known_limits"):
        value = record.get(field)
        if (
            not isinstance(value, list)
            or not value
            or not all(_nonempty_str(item) for item in value)
        ):
            problem(field, "missing, empty, or not a list of non-empty strings")

    # 7. rollback
    if not _nonempty_str(record.get("rollback")):
        problem("rollback", "missing or empty")

    # the timestamp, measured at write time
    created_at = record.get("created_at")
    if not _nonempty_str(created_at):
        problem("created_at", "missing or empty")
    elif _parse_utc(created_at) is None:
        problem("created_at", f"{created_at!r} is not a UTC ISO-8601 timestamp")

    return problems


# ---------------------------------------------------------------------------
# The subcommands
# ---------------------------------------------------------------------------


def cmd_create(namespace: argparse.Namespace) -> int:
    """Write docs/releases/<version>.json, or refuse to."""
    version: str = namespace.version
    if not VERSION_PATTERN.match(version):
        raise ReleaseRecordError(
            f"--version {version!r} is not a version string "
            "(letters, digits and . _ + - , starting with a letter or digit)"
        )
    target = git_root() / RELEASES_SUBDIR / f"{version}.json"
    if target.exists() and not namespace.force:
        raise ReleaseRecordError(f"{target} already exists; pass --force to overwrite it")
    artifact: Path | None = namespace.artifact
    if artifact is not None and not artifact.is_file():
        raise ReleaseRecordError(f"the artifact {artifact} does not exist")
    record = build_record(namespace, artifact)
    problems = record_problems(record, expected_stem=version, verify_commit=True)
    if problems:
        for line in problems:
            print(f"missing or invalid: {line}", file=sys.stderr)
        raise ReleaseRecordError("the assembled record fails its own check; nothing was written")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {target}")
    print(f"  version {version} at commit {record['commit']}")
    return 0


def cmd_check(namespace: argparse.Namespace) -> int:
    """Measure one record against the seven elements, and report."""
    path: Path = namespace.file
    if not path.is_file():
        raise ReleaseRecordError(f"{path} does not exist")
    try:
        record: Any = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ReleaseRecordError(f"{path} is not valid JSON: {error}") from error
    problems = record_problems(record, expected_stem=path.stem, verify_commit=True)
    if problems:
        print(f"{path}: {len(problems)} problem(s):")
        for line in problems:
            print(f"  - {line}")
        return 1
    print(
        f"{path}: OK -- the seven elements are present, the commit is in this "
        "repository's history, and created_at is a UTC ISO-8601 timestamp."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    """The command line: create writes a record, check measures one."""
    parser = argparse.ArgumentParser(
        description=(
            "Write and check the structured release records under docs/releases/ "
            "(the seven elements of Phase 4 §10)."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser(
        "create", help="write docs/releases/<version>.json from git, an artifact and notes"
    )
    create.add_argument(
        "--version",
        required=True,
        help="the version number the record names; also the file name stem",
    )
    create.add_argument(
        "--artifact",
        type=Path,
        default=None,
        help="the installer artifact to hash; its sha256 is recorded, the file is not copied",
    )
    create.add_argument(
        "--artifact-reason",
        default=None,
        help="why artifact_sha256 is null; required when --artifact is not given",
    )
    create.add_argument(
        "--notes",
        default=None,
        help="a JSON or YAML file (or inline JSON) carrying compatibility, added, "
        "fixed, known_limits and rollback",
    )
    create.add_argument(
        "--data-compatibility", default=None, help="the data compatibility statement"
    )
    create.add_argument("--api-compatibility", default=None, help="the API compatibility statement")
    create.add_argument("--added", action="append", help="one added capability; repeatable")
    create.add_argument("--fixed", action="append", help="one fixed issue; repeatable")
    create.add_argument(
        "--known-limits", action="append", help="one limit that remains open; repeatable"
    )
    create.add_argument("--rollback", default=None, help="how to roll this release back")
    create.add_argument(
        "--force", action="store_true", help="overwrite an existing record for this version"
    )

    check = subparsers.add_parser("check", help="check one record against the seven elements")
    check.add_argument("file", type=Path, help="the record JSON file to check")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """The entry point: dispatch to the subcommand, report refusals in one line."""
    namespace = build_parser().parse_args(argv)
    try:
        if namespace.command == "create":
            return cmd_create(namespace)
        if namespace.command == "check":
            return cmd_check(namespace)
    except ReleaseRecordError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    raise AssertionError(f"unhandled subcommand {namespace.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
