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
        replaced = _replaced_in_place(lost, added)
        if replaced:
            print()
            print(
                f"  Of those, {len(replaced)} were replaced in the same file -- a "
                "witness renamed because the property it holds changed. The name "
                "is gone and a new one stands in its place:"
            )
            for path, old_name, new_name in replaced:
                print(f"  {old_name} -> {new_name}   (both in {path})")
            print(
                "  **A rename is not a loss, and it is not a silent one either.** "
                "Read the new witness before taking the rename for a covering."
            )
    else:
        print("LOST -- none.  Every test function that existed before still exists.")
    if added:
        print()
        print(f"ADDED -- {len(added)} test function(s):")
        for path, name in added:
            print(f"  {name}   (now in {path})")
    return 1 if lost else 0


def _replaced_in_place(
    lost: list[tuple[str, str]], added: list[tuple[str, str]]
) -> list[tuple[str, str, str]]:
    """The lost names a new name in the same file stands in for.

    **A witness is often renamed, and a rename is not a loss.** The batch
    that closed the dangling-source gap flipped the witness that held the
    behaviour *as it was* -- the one that asserted an attestation succeeded
    over a source the ledger no longer held -- into the witness that asserts
    the refusal. The old name stopped existing and a new one started, in the
    same file, and the ledger reported the old one as LOST. **That is the
    false alarm this function exists to soften**, because a report that cries
    loss over a deliberate rename teaches a reader to skim past the one that
    matters.

    **What it does not do.** It does not decide that a rename happened. It
    pairs a lost name with an added name **in the same file** and prints the
    pairing, so a reader sees what the tool noticed and judges it. The exit
    code is unchanged: a name that stopped existing is still a name that
    stopped existing, and the tool must not go quiet about it because a
    plausible pairing happened to exist.
    """
    by_file: dict[str, list[str]] = {}
    for path, name in added:
        by_file.setdefault(path, []).append(name)
    paired: list[tuple[str, str, str]] = []
    for path, old_name in lost:
        candidates = by_file.get(path, [])
        if candidates:
            paired.append((path, old_name, candidates[0]))
            candidates.pop(0)
    return paired


if __name__ == "__main__":
    raise SystemExit(main())
