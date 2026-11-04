"""Did the composition lose a witness?

A composition that resolves a conflict by keeping both sides can also keep
both sides of a *deletion* -- and the file it produces parses, passes every
test, and is green in CI, because the thing that was lost was the noticing.

This compares the set of test functions in `tests/` between two commits and
names every one that exists in the first and not in the second.  It is the
check that would have caught F44: the composition commit `2f7ffc5` deleted
four test functions that its parents had, and the whole suite stayed green.

    python witness_ledger.py <before> <after> [repo]

The repository defaults to the one this script lives in, so it answers the
same question in any checkout rather than in the one it was written in.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(__file__).resolve().parent.parent
BEFORE, AFTER = sys.argv[1], sys.argv[2]

#: A top-level test function, and a test method inside a class.
TOP_LEVEL = re.compile(r"^def (test_[A-Za-z0-9_]+)\(", re.MULTILINE)
METHOD = re.compile(r"^    def (test_[A-Za-z0-9_]+)\(", re.MULTILINE)


def functions(ref: str) -> set[tuple[str, str]]:
    """Every test function at `ref`, as ``(file, name)``.

    **The name alone is not the identity.** Two files may each hold a witness
    with the same name — a mirrored witness, or a copy an agent happened to
    write into both — and a keyed-by-name collector lets one overwrite the
    other. Measured on 2026-11-03: a merge added seven witnesses whose names
    already existed in a sibling file, and the ledger reported **ADDED — none**
    with both totals unchanged. The same collision hides a **loss** in the
    other direction, which is the failure this tool exists to catch: deleting
    the copy in one file leaves the other's identical name in place, so
    "LOST -- none" would be printed over a tree that lost a witness.
    """
    listing = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", ref, "tests/"],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out: set[tuple[str, str]] = set()
    for path in listing.stdout.split():
        if not path.endswith(".py"):
            continue
        blob = subprocess.run(
            ["git", "show", f"{ref}:{path}"],
            cwd=REPO,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if blob.returncode != 0:
            continue
        for match in list(TOP_LEVEL.finditer(blob.stdout)) + list(METHOD.finditer(blob.stdout)):
            out.add((path, match.group(1)))
    return out


def main() -> int:
    before, after = functions(BEFORE), functions(AFTER)
    lost = sorted(set(before) - set(after))
    added = sorted(set(after) - set(before))

    print(f"before {BEFORE}: {len(before)} test functions")
    print(f"after  {AFTER}: {len(after)} test functions")
    print()
    if lost:
        print(f"LOST -- {len(lost)} test function(s) that existed before and do not now:")
        for path, name in lost:
            print(f"  {name}   (was in {path})")
    else:
        print("LOST -- none.  Every test function that existed before still exists.")
    if added:
        print()
        print(f"ADDED -- {len(added)} test function(s):")
        for path, name in added:
            print(f"  {name}   (now in {path})")
    return 1 if lost else 0


if __name__ == "__main__":
    raise SystemExit(main())
