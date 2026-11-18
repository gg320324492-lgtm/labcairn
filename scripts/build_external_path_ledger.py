"""Build or refresh the external-path ledger.

**What this does.** The ledger (``docs/ci/external-paths.json``) lists
every path under ``E:/labcairn-local`` that a tracked file names, and
says what each one is expected to be — present, renamed, or absent. It
is written by hand once and refreshed by this tool, because a ledger
that is edited by hand for two hundred entries stops being a ledger.

**What it reads.** The tracked files of the repository, the existing
ledger, and — for the first build — the seed of judgements below. It
never writes anything outside the ledger.

**The three ways a path's expectation is decided.**

* the existing ledger says so, and this tool keeps it. An expectation
  is a judgement about a path, and a judgement is not re-made by a
  refresh;
* the seed says so, for a path the seed knows about;
* the disk says so, for a path nobody has judged yet: it is there, so
  it is expected to be there.

**What it refuses to do.** It will not invent an announcement. A path
that holds material and is not on disk has to be announced by the
record that names it, and the wording of that announcement is a human's
sentence, not a tool's. So a new dead path arrives with no
announcement, and the witness then refuses the ledger until the record
has been fixed and the wording written down.

Run with:

    python scripts/build_external_path_ledger.py            # report the differences
    python scripts/build_external_path_ledger.py --write    # write the ledger

Exit codes
    0  the ledger is up to date, or was written
    2  the ledger would change (without ``--write``)
    1  the ledger could not be read, or the tree could not be listed
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Final

sys.path.insert(0, str(Path(__file__).resolve().parent))

# The checker is imported by path rather than as a package, because
# ``scripts/`` is not one and this tool is run from the repository root.
import check_external_paths as checker

#: How the seed's vocabulary maps onto the ledger's kinds.
_DISPOSITIONS: Final[dict[str, str]] = {
    "artifact": "material",
    "dead-material": "material",
    "historical": "historical",
    "moved": "material",
    "obsolete-renamed": "material",
    "prospective": "prospective",
    "run-scratch": "scratch",
    "script-created": "created",
}

#: The characters that end a file name inside a line of prose.
_NAME_END: Final = re.compile(r"[`'\"|<>\n]")

#: The date the ledger records, when the caller does not give one.
_DEFAULT_READ_AT: Final = "2026-11-18"


def _seed_entries(path: Path) -> dict[str, dict[str, Any]]:
    """The seed's judgements, keyed by path."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise checker.LedgerError(f"{path} could not be read: {error}") from error
    except json.JSONDecodeError as error:
        raise checker.LedgerError(f"{path} is not valid JSON: {error}") from error
    entries = document.get("entries") if isinstance(document, dict) else None
    if not isinstance(entries, list):
        raise checker.LedgerError(f"{path} has no 'entries' list")
    seeded: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        raw = str(entry.get("path", ""))
        if not raw:
            continue
        disposition = str(entry.get("disposition", ""))
        kind = _DISPOSITIONS.get(disposition, "material")
        status = str(entry.get("status_at_scan", ""))
        replacement = str(entry.get("replacement", ""))
        if (disposition == "moved" or status == "renamed") and replacement:
            expectation = "renamed"
        elif status == "present":
            expectation = "present"
        else:
            expectation = "absent"
        seeded[checker.normalise(raw)] = {
            "expectation": expectation,
            "kind": kind,
            "note": str(entry.get("note", "")),
            "replacement": checker.normalise(replacement) if replacement else None,
        }
    return seeded


def _resolve_over_space(ref: checker.PathRef, line: str) -> str:
    """Extend a path whose file name holds a space.

    The scan stops a path at the first space, because a space usually
    ends a path in prose. When the file name itself holds a space, the
    rest of the name is still on the line, and the disk is the judge:
    if the longer spelling is there, that is the path.
    """
    if Path(ref.path).exists():
        return ref.path
    rest = line[ref.end :]
    cut = _NAME_END.search(rest)
    if cut is None:
        return ref.path
    tail = rest[: cut.start()].strip().rstrip(".,;:!?")
    if not tail:
        return ref.path
    candidate = f"{ref.path} {tail}"
    if Path(candidate).exists():
        return checker.normalise(candidate)
    return ref.path


def scan(root: Path, files: list[str]) -> dict[str, dict[str, Any]]:
    """Every path the tracked files name, with the files that name it.

    A path that the record wrote with a wildcard or a placeholder is
    marked, because it is a shape rather than an address: there is no
    single path there to lose, and a record that offers it is not
    offering a place.
    """
    found: dict[str, dict[str, Any]] = {}
    for relative in files:
        if relative in checker.APPARATUS:
            continue
        if Path(relative).suffix.lower() not in checker.TEXT_SUFFIXES:
            continue
        text = checker.read_text(root, relative)
        lines = text.splitlines()
        for ref in checker.extract_refs(text):
            line = lines[ref.line - 1] if ref.line - 1 < len(lines) else ""
            marker = line[ref.end : ref.end + 1]
            pattern = bool(marker) and marker in checker.PATTERN_MARKERS
            path = ref.path if pattern else _resolve_over_space(ref, line)
            entry = found.setdefault(path, {"sites": [], "pattern": pattern})
            if relative not in entry["sites"]:
                entry["sites"].append(relative)
    return found


def build(
    root: Path,
    files: list[str],
    existing: dict[str, dict[str, Any]],
    seeded: dict[str, dict[str, Any]],
    read_at: str,
) -> dict[str, Any]:
    """The ledger the tree and the judgements call for."""
    found = scan(root, files)
    entries: list[dict[str, Any]] = []
    for path in sorted(found):
        known = existing.get(path) or seeded.get(path)
        if known is None:
            here = Path(path).exists()
            known = {
                "expectation": "present" if here else "absent",
                "kind": "pattern" if found[path]["pattern"] else "material",
                "note": (
                    "the record writes a shape rather than an address — a wildcard "
                    "or a placeholder, so there is no single path here to lose"
                    if found[path]["pattern"]
                    else (
                        "named by a record and found on disk when the ledger was built"
                        if here
                        else "named by a record and not on disk; the record has to say so"
                    )
                ),
                "replacement": None,
            }
        replacement = known.get("replacement")
        if known["expectation"] == "renamed" and isinstance(replacement, str):
            replacement = checker.normalise(replacement)
            if replacement:
                # A file that moved into a directory is named by its new
                # full path; a directory that was renamed is named by the
                # directory itself. The disk says which.
                joined = f"{replacement}/{Path(path).name}"
                if Path(path).suffix and Path(joined).exists():
                    replacement = checker.normalise(joined)
        entry: dict[str, Any] = {
            "path": path,
            "expectation": known["expectation"],
            "kind": known["kind"],
            "replacement": replacement if known["expectation"] == "renamed" else None,
            "note": known.get("note", ""),
            "announcements": list(known.get("announcements", [])),
            "sites": sorted(found[path]["sites"]),
        }
        entries.append(entry)
    return {
        "schema": "labcairn-external-path-ledger/v1",
        "read_at": read_at,
        "root": f"E:/{checker.ROOT_MARKER}",
        "what_this_is": (
            "Every path under E:/labcairn-local that a tracked file names, and "
            "what each one is expected to be: present, renamed (with the path "
            "that replaced it), or absent. The rule it encodes: a rename is not "
            "a defect, a bare pointer to the old name is. The half that needs "
            "the packs runs on a development machine; the half that only needs "
            "the tree runs in CI."
        ),
        "apparatus": list(checker.APPARATUS),
        "paths": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=None, help="the repository root")
    parser.add_argument("--ledger", default=None, help="the ledger to read and write")
    parser.add_argument(
        "--seed", default=None, help="a judgements file to seed the kinds and notes from"
    )
    parser.add_argument("--read-at", default=_DEFAULT_READ_AT, help="the date the reading is from")
    parser.add_argument("--write", action="store_true", help="write the ledger")
    args = parser.parse_args()
    root = Path(args.repo) if args.repo else checker.repo_root()
    ledger_path = Path(args.ledger) if args.ledger else root / checker.LEDGER_RELPATH
    try:
        files = checker.tracked_files(root)
        existing: dict[str, dict[str, Any]] = {}
        if ledger_path.exists():
            document = checker.load_ledger(ledger_path)
            for entry in checker.ledger_entries(document):
                existing[checker.normalise(str(entry.get("path", "")))] = entry
        seeded = _seed_entries(Path(args.seed)) if args.seed else {}
        ledger = build(root, files, existing, seeded, args.read_at)
    except checker.LedgerError as error:
        print(f"the build could not run: {error}")
        return 1
    text = json.dumps(ledger, indent=2, ensure_ascii=False) + "\n"
    if not args.write:
        if ledger_path.exists() and ledger_path.read_text(encoding="utf-8") == text:
            print("the ledger is up to date")
            return 0
        print("the ledger would change; run again with --write")
        return 2
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(text, encoding="utf-8")
    print(f"the ledger was written: {ledger_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
