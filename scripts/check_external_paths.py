"""The external-path ledger: check that every path a live record names is accounted for.

**The problem.** The repository's records name paths under
``E:/labcairn-local`` — the delivery packs that live outside the
checkout. A record that names a path where nothing is left sends a
reader to a place that is not there, and **nothing in CI can see that**,
because the packs are not on a runner.

So the repository keeps a **ledger** of those paths
(``docs/ci/external-paths.json``) and this script checks the ledger
against the tree. For every path a live record names, the ledger says
what the path is expected to be:

``present``
    the path is on disk and the record may offer it.
``renamed``
    the path is not on disk any more; ``replacement`` names where it
    went, and the record has to name that too.
``absent``
    the path is not on disk and is not expected to be — a scratch
    directory a run cleaned up, a path a script creates, a path that was
    deleted and the record says so.

**The rule the ledger encodes.** *A rename is not a defect; a bare
pointer to the old name is.* A path that moved is still the material a
reader wants, so the record is repaired by naming the new address
beside the old one, dated. A path that is simply gone is repaired by
saying so, dated. What is not allowed is a record that names a path
which is not there **and says nothing about it** — that is the dangling
pointer, and it is the failure this ledger exists to catch.

**What runs where — the split is deliberate.**

* **The half CI can check** is the repository side: every path a
  tracked file names is in the ledger; a path the ledger says is dead is
  never named bare; a renamed path is named together with the path that
  replaced it. None of that needs the packs, so it runs on a runner.
* **The half only a development machine can check** is the packs side:
  whether ``E:/labcairn-local/...`` is on disk is a question about a
  machine, not about the tree. It is **skipped, not failed**, where the
  root is absent.

Run with:

    python scripts/check_external_paths.py            # everything that can run here
    python scripts/check_external_paths.py --ci-only  # the repository half only

Exit codes
    0  every check that could run passed
    2  at least one check failed (a dangling pointer, a stale ledger entry)
    1  the ledger could not be read, or the tree could not be listed
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

#: The repository's shared test helpers, for the deadline this
#: script's waits carry.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

from deadline_support import bounded_git

#: The root every external path in this repository lives under.
ROOT_MARKER: Final = "labcairn-local"

#: The ledger, relative to the repository root.
LEDGER_RELPATH: Final = "docs/ci/external-paths.json"

#: The files that talk about the ledger instead of being watched by it.
#: They are excluded from the scan for the same reason the external
#: liveness tool excluded its own output directory: a file that quotes
#: the paths the check is about must not be read as a record that
#: *offers* them. The list is checked against the witness's own copy,
#: so an exclusion cannot be added quietly.
#:
#: The reading that explains the ledger is **not** on this list: it is a
#: record like any other, it names external paths, and those paths are
#: held to the same rule.
APPARATUS: Final[tuple[str, ...]] = (
    "docs/ci/external-paths.json",
    "scripts/check_external_paths.py",
    "scripts/build_external_path_ledger.py",
    "tests/test_external_path_references.py",
)

#: The expectation vocabulary, and what each one means.
EXPECTATIONS: Final[tuple[str, ...]] = ("present", "renamed", "absent")

#: The kind vocabulary, and what each one means for the announcement rule.
#:
#: ``material``
#:     the path held something a reader was sent to. When it is gone the
#:     record has to say so, dated — this is the kind the announcement
#:     rule is about.
#: ``scratch``
#:     a directory a run used and cleaned up. The record describes the
#:     arrangement; it does not offer the path.
#: ``created``
#:     a path a script creates. The record names the path the script
#:     will make, not one that is there.
#: ``prospective``
#:     a path a future step will create. Same reasoning.
#: ``historical``
#:     a path a past run used and that is gone, with no offer in the
#:     sentence.
#: ``pattern``
#:     the record wrote a shape rather than an address — a wildcard or a
#:     placeholder. There is no single path to lose.
KINDS: Final[tuple[str, ...]] = (
    "material",
    "scratch",
    "created",
    "prospective",
    "historical",
    "pattern",
)

#: The suffixes the scan reads. A binary file cannot name a path a
#: reader follows, and reading one as text invents paths out of noise.
TEXT_SUFFIXES: Final[frozenset[str]] = frozenset(
    {
        ".cfg",
        ".csv",
        ".ini",
        ".json",
        ".md",
        ".ps1",
        ".py",
        ".toml",
        ".txt",
        ".yaml",
        ".yml",
    }
)

#: One external path as it is written in a record. The drive is
#: optional — a record may write the path without it — and the
#: separator may be either. Everything after the root marker is taken
#: until a character that cannot be in a path; a space ends it, which is
#: why a path whose *file name* holds a space is matched in two
#: pieces: the ledger's longest entry covers the truncated run.
_PATH_RE: Final = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"(?:(?P<drive>[A-Za-z]:)[\\/])?"
    r"(?P<root>" + ROOT_MARKER + r")"
    r"(?P<tail>[A-Za-z0-9._~+\-\\/:()\[\]]*)"
)

#: The characters that end a path but are not part of it.
_TRAILING: Final = ".,;:!?)]}'\"`"

#: The kinds whose record has to announce the loss.
ANNOUNCED_KINDS: Final[frozenset[str]] = frozenset({"material"})

#: The characters that mean the record wrote a shape, not an address.
PATTERN_MARKERS: Final = "*…{<"


class LedgerError(Exception):
    """The ledger could not be read, or the tree could not be listed."""


@dataclass(frozen=True)
class PathRef:
    """One external path, as a line names it.

    ``line`` is 1-based, the way an editor counts. ``start`` and ``end``
    are offsets into that line, so a caller that needs to look at the
    text around the path — a generator that has to extend a path whose
    file name holds a space — can.
    """

    line: int
    path: str
    start: int
    end: int


def normalise(raw: str) -> str:
    """Return the path in the ledger's own spelling.

    Backslashes become forward slashes, repeated separators collapse (a
    path written inside a JSON document carries its backslashes
    escaped, and the escaping is not part of the path), the drive is
    upper-cased, a path written without a drive gets the one the root
    lives on, and the punctuation that ends a sentence is dropped. A
    trailing separator is dropped too, so a directory and its files are
    two different entries rather than one entry and a prefix of it.
    """
    text = raw.replace("\\", "/")
    text = re.sub(r"/{2,}", "/", text)
    text = text.rstrip(_TRAILING)
    text = text.rstrip("/")
    if re.match(r"^[A-Za-z]:", text):
        text = text[0].upper() + text[1:]
    elif text.startswith(ROOT_MARKER):
        text = f"E:/{text}"
    return text


def extract_refs(text: str) -> list[PathRef]:
    """Return every external path the text names, with where it sits.

    A line can hold more than one path, and a path can be written with
    either separator. The line number is 1-based, the way an editor
    counts.
    """
    found: list[PathRef] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for match in _PATH_RE.finditer(line):
            path = normalise(match.group(0))
            if path:
                found.append(PathRef(number, path, match.start(), match.end()))
    return found


def extract_runs(text: str) -> list[tuple[int, str]]:
    """The paths a text names, as (line number, path) pairs."""
    return [(ref.line, ref.path) for ref in extract_refs(text)]


def covers(entry_path: str, run: str) -> bool:
    """Whether a ledger entry accounts for a run the scan found.

    Three shapes count, and no others:

    * the run is the entry;
    * the run is the entry cut short at a space inside a file name, and
      the entry continues with that space;
    * the run names something inside a directory the entry declares.

    The third shape is the loose one, and the coverage rule does not use
    it: a directory entry must not be able to stand in for a file the
    ledger has not heard of, or a new dead file inside a known directory
    would pass unnoticed. The announcement rule and the rename rule use
    the strict shape, which is :func:`names`.
    """
    entry = entry_path.lower()
    candidate = run.lower()
    if candidate == entry:
        return True
    if entry.startswith(candidate) and (
        len(entry) == len(candidate) or entry[len(candidate)] == " "
    ):
        return True
    return candidate.startswith(entry + "/")


def names(run: str, entry_path: str) -> bool:
    """Whether a run names the entry itself (rather than something inside it).

    A record that writes ``.../row-marker-measure/mut/`` names that
    directory; a record that writes ``.../row-marker-measure/mut/x.py``
    names a file inside it, which is a different path with its own
    ledger entry.

    The one loose case is a file name that holds a space: the scan
    stops the run at the space, so the run is the entry cut short, and
    the entry continues with that space.
    """
    entry = entry_path.lower()
    candidate = run.lower()
    if candidate == entry:
        return True
    return entry.startswith(candidate) and (
        len(entry) == len(candidate) or entry[len(candidate)] == " "
    )


def repo_root() -> Path:
    """The repository this script lives in."""
    return Path(__file__).resolve().parent.parent


def tracked_files(root: Path) -> list[str]:
    """The tracked files of the repository, as paths relative to its root.

    The list comes from git rather than from a walk, because a walk
    would read the working files — caches, a virtualenv, the working
    directory's own leftovers — and the ledger is about what the
    repository *says*, which is what is tracked.
    """
    try:
        finished = bounded_git(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise LedgerError(f"the tracked files could not be listed: {error}") from error
    names_ = finished.stdout.decode("utf-8", errors="replace").split("\0")
    return [name for name in names_ if name]


def read_text(root: Path, relative: str) -> str:
    """One tracked file, read as text."""
    path = root / relative
    try:
        return path.read_bytes().decode("utf-8", errors="replace")
    except OSError as error:
        raise LedgerError(f"{relative} could not be read: {error}") from error


def ledger_entries(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    """The ledger's entries, in the shape the checks expect."""
    entries = ledger.get("paths")
    if not isinstance(entries, list):
        raise LedgerError("the ledger has no 'paths' list")
    return [entry for entry in entries if isinstance(entry, dict)]


def load_ledger(path: Path) -> dict[str, Any]:
    """Read and parse the ledger."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise LedgerError(f"{path} could not be read: {error}") from error
    except json.JSONDecodeError as error:
        raise LedgerError(f"{path} is not valid JSON: {error}") from error
    if not isinstance(document, dict):
        raise LedgerError(f"{path} is not a JSON object")
    return document


def block_bounds(lines: list[str], index: int) -> tuple[int, int]:
    """The paragraph a line belongs to: the run of non-blank lines around it.

    A dated note is allowed to sit on the next line rather than on the
    line that names the path, because a record is written in
    paragraphs and a note is written in prose.
    """
    start = index
    while start > 0 and lines[start - 1].strip():
        start -= 1
    end = index
    while end + 1 < len(lines) and lines[end + 1].strip():
        end += 1
    return start, end


def well_formed_problems(ledger: dict[str, Any]) -> list[str]:
    """The ledger's own shape: the vocabulary, and what must go with what."""
    problems: list[str] = []
    schema = ledger.get("schema")
    if schema != "labcairn-external-path-ledger/v1":
        problems.append(f"the ledger's schema is {schema!r}, not the one this tool reads")
    apparatus = ledger.get("apparatus")
    if list(APPARATUS) != list(apparatus or []):
        problems.append(
            "the ledger's apparatus list does not match the tool's: "
            f"{apparatus!r} against {list(APPARATUS)!r}"
        )
    entries = ledger_entries(ledger)
    seen: set[str] = set()
    for entry in entries:
        path = str(entry.get("path", ""))
        if not path:
            problems.append("an entry has no path")
            continue
        if path in seen:
            problems.append(f"{path} is in the ledger twice")
        seen.add(path)
        expectation = str(entry.get("expectation", ""))
        if expectation not in EXPECTATIONS:
            problems.append(f"{path}: the expectation {expectation!r} is not one of {EXPECTATIONS}")
        kind = str(entry.get("kind", ""))
        if kind not in KINDS:
            problems.append(f"{path}: the kind {kind!r} is not one of {KINDS}")
        replacement = entry.get("replacement")
        if expectation == "renamed":
            if not isinstance(replacement, str) or not replacement:
                problems.append(f"{path}: it is renamed, so it must name the path that replaced it")
        elif replacement:
            problems.append(f"{path}: it is not renamed, so it must not name a replacement")
        announcements = entry.get("announcements")
        if not isinstance(announcements, list):
            problems.append(f"{path}: the announcements must be a list")
            announcements = []
        if kind in ANNOUNCED_KINDS and expectation != "present" and not announcements:
            problems.append(
                f"{path}: it held material and it is not there, so the record has to say so"
            )
        if expectation == "present" and announcements:
            problems.append(f"{path}: it is there, so there is nothing to announce")
        sites = entry.get("sites")
        if not isinstance(sites, list):
            problems.append(f"{path}: the sites must be a list")
    return problems


def coverage_problems(ledger: dict[str, Any], root: Path, files: list[str]) -> list[str]:
    """Every path a tracked file names must be in the ledger.

    This is the check that makes the ledger a ledger rather than a
    snapshot: a record that starts naming a new external path is a
    record the ledger does not know about, and the ledger says so
    instead of staying quietly out of date.

    The rule is strict: the path has an entry of its own. A directory
    entry does not stand in for a file inside it, because that would
    let a new dead file inside a known directory through unnoticed.
    """
    problems: list[str] = []
    entries = ledger_entries(ledger)
    known = [str(entry.get("path", "")) for entry in entries]
    for relative in files:
        if relative in APPARATUS:
            continue
        if Path(relative).suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = read_text(root, relative)
        for number, run in extract_runs(text):
            if not any(names(run, entry) for entry in known):
                problems.append(
                    f"{relative}:{number}: {run} is named by a record and is not in the ledger"
                )
    return problems


def announcement_problems(ledger: dict[str, Any], root: Path, files: list[str]) -> list[str]:
    """A path that is gone must never be named bare.

    A record that names a path the ledger says is gone may still
    mention it — the reading of a past run is worth keeping — but the
    paragraph that mentions it has to say that the path is not there.
    That is the difference between a dated supersede and a dangling
    pointer, and it is the whole point of the ledger.
    """
    problems: list[str] = []
    for entry in ledger_entries(ledger):
        path = str(entry.get("path", ""))
        expectation = str(entry.get("expectation", ""))
        kind = str(entry.get("kind", ""))
        if kind not in ANNOUNCED_KINDS or expectation == "present":
            continue
        announcements = [str(item) for item in entry.get("announcements", [])]
        sites = [str(item) for item in entry.get("sites", [])]
        for relative in files:
            if relative in APPARATUS:
                continue
            if Path(relative).suffix.lower() not in TEXT_SUFFIXES:
                continue
            text = read_text(root, relative)
            lines = text.splitlines()
            runs = extract_runs(text)
            if not any(names(run, path) for _, run in runs):
                continue
            if relative not in sites:
                problems.append(
                    f"{relative} names {path}, which the ledger does not list as a site"
                )
                continue
            for number, run in runs:
                if not names(run, path):
                    continue
                start, end = block_bounds(lines, number - 1)
                paragraph = "\n".join(lines[start : end + 1])
                if not any(item in paragraph for item in announcements):
                    problems.append(
                        f"{relative}:{number}: {path} is named without saying it is gone"
                    )
        for relative in sites:
            if relative not in files:
                problems.append(f"{path}: the site {relative} is not a tracked file")
    return problems


def rename_problems(ledger: dict[str, Any], root: Path, files: list[str]) -> list[str]:
    """A record that names the old address has to name the new one too.

    Otherwise the reader is left with the old name alone, which is the
    situation the rename was supposed to end.
    """
    problems: list[str] = []
    for entry in ledger_entries(ledger):
        path = str(entry.get("path", ""))
        if str(entry.get("expectation", "")) != "renamed":
            continue
        replacement = str(entry.get("replacement", ""))
        for relative in [str(item) for item in entry.get("sites", [])]:
            if relative in APPARATUS or relative not in files:
                continue
            text = read_text(root, relative)
            runs = [run for _, run in extract_runs(text)]
            if not any(covers(replacement, run) or names(run, replacement) for run in runs):
                problems.append(
                    f"{relative} names {path} but not the path that replaced it, {replacement}"
                )
    return problems


def existence_problems(ledger: dict[str, Any]) -> list[str]:
    """Whether each path is where the ledger says it is.

    This is the half that needs a machine with the packs on it. On a
    runner the root is not there, so the check is skipped rather than
    failed — a question about a machine is not a failure of the tree.
    """
    problems: list[str] = []
    for entry in ledger_entries(ledger):
        path = str(entry.get("path", ""))
        expectation = str(entry.get("expectation", ""))
        here = Path(path)
        if expectation == "present":
            if not here.exists():
                problems.append(f"{path} is not on disk, and the ledger says it is there")
        elif expectation == "renamed":
            replacement = str(entry.get("replacement", ""))
            if here.exists():
                problems.append(f"{path} is on disk, and the ledger says it moved to {replacement}")
            if replacement and not Path(replacement).exists():
                problems.append(f"{replacement} is not on disk, and it replaced {path}")
        else:
            if here.exists():
                problems.append(f"{path} is on disk, and the ledger says it is not there")
    return problems


def check(root: Path, ledger_path: Path, existence: bool) -> tuple[list[str], bool]:
    """Run the checks. Returns the problems, and whether existence ran."""
    ledger = load_ledger(ledger_path)
    files = tracked_files(root)
    problems: list[str] = []
    problems.extend(well_formed_problems(ledger))
    problems.extend(coverage_problems(ledger, root, files))
    problems.extend(announcement_problems(ledger, root, files))
    problems.extend(rename_problems(ledger, root, files))
    ran_existence = False
    if existence and Path(f"E:/{ROOT_MARKER}").exists():
        problems.extend(existence_problems(ledger))
        ran_existence = True
    return problems, ran_existence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=None, help="the repository root")
    parser.add_argument("--ledger", default=None, help="the ledger to read")
    parser.add_argument(
        "--ci-only",
        action="store_true",
        help="only the checks that need no packs (the CI half)",
    )
    args = parser.parse_args()
    root = Path(args.repo) if args.repo else repo_root()
    ledger_path = Path(args.ledger) if args.ledger else root / LEDGER_RELPATH
    try:
        problems, ran_existence = check(root, ledger_path, existence=not args.ci_only)
    except LedgerError as error:
        print(f"the check could not run: {error}")
        return 1
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} problem(s)")
        return 2
    if not ran_existence:
        print("the repository half passed; the packs half was skipped (the root is not here)")
    else:
        print("every check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
