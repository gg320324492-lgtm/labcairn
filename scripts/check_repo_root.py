#!/usr/bin/env python3
"""Read-only guard: is the Git repository root this LabCairn checkout?

The single highest-severity operating hazard in this project is a ``git init``
rooted above the repository. ``.gitignore`` applies only to its own directory
and below, so it says nothing about a sibling directory -- and on a machine
where a checkout lives beside unrelated projects, that is exactly how an entire
directory tree becomes tracked content. No in-repository configuration can
prevent it; only the habit of looking before running anything.

This script exists so that habit is one command. It performs **no Git write
operation**: ``subprocess`` is used only for ``git rev-parse``, which reads.

The raw check in CONTRIBUTING.md remains the authority::

    git rev-parse --show-toplevel

This is a convenience, not a substitute. It also cannot be the authority for
detecting a bad ``git init`` that has not happened yet -- at that point there
is no repository to ask, so the script reports "not a Git repository" and exits
non-zero, which is the correct answer to "is this safe to work in?".

Exit codes: 0 = the root is this LabCairn checkout; 1 = it is not, or there is
no repository, or git is unavailable. Every failure prints what it found and
what it expected, because a guard that fails without saying why gets ignored.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

#: The package directory that must sit directly under the repository root.
MARKER = Path("src") / "labcairn" / "__init__.py"


def _repo_root(start: Path) -> tuple[Path | None, str]:
    """Return (root, diagnostic). ``root`` is None when git could not answer."""
    try:
        completed = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None, "git is not on PATH"
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip().splitlines()
        return None, detail[-1] if detail else "git rev-parse failed"
    text = completed.stdout.strip()
    if not text:
        return None, "git rev-parse returned an empty path"
    return Path(text).resolve(), "ok"


def main() -> int:
    # The script's own location, not the cwd: running it from anywhere must
    # check the checkout it ships with, which is the whole point of the
    # "cd elsewhere and run it by absolute path" case in CONTRIBUTING.md.
    script_root = Path(__file__).resolve().parent.parent
    print(f"script belongs to : {script_root}")

    root, detail = _repo_root(Path.cwd())
    if root is None:
        print(f"FAIL: no Git repository here ({detail}).")
        print("       An ancestor `git init` may not have happened yet -- that is")
        print("       the hazard this script exists to catch. Do not create one.")
        return 1

    print(f"git root at cwd   : {root}")
    if root != script_root:
        print(f"FAIL: this is not the LabCairn checkout ({script_root}).")
        print("       Running Git here would act on a different repository.")
        print("       Stop, and do not run add / commit / status / checkout /")
        print("       clean / stash / restore until this is understood.")
        return 1

    marker = root / MARKER
    if not marker.is_file():
        print(f"FAIL: repository root is {root} but {MARKER} is absent.")
        print("       Right root, wrong project -- treat as a hazard.")
        return 1

    print(f"marker found      : {marker}")
    print("OK: repository root is this LabCairn checkout. No Git write performed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
