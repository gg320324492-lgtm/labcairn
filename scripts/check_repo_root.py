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
import sys
from pathlib import Path

#: The package directory that must sit directly under the repository root.
MARKER = Path("src") / "labcairn" / "__init__.py"

#: The encoding git writes a path in, and therefore the encoding this script
#: decodes it with.
#:
#: Both halves of the pipe have to be stated, and they have to agree. The
#: decode used to be left to the machine's locale encoding, and on a
#: cp936 Windows with a checkout path containing Chinese characters that is
#: how this guard became a traceback: git writes the path as UTF-8 (it
#: converts from the wide-character filesystem itself, whatever the locale
#: is), the parent decoded those bytes as cp936, and the decode failed
#: inside subprocess's reader thread -- where the exception is swallowed and
#: the capture comes back as None. The guard then died at
#: ``completed.stdout.strip()`` with "AttributeError: 'NoneType' object has
#: no attribute 'strip'", a message that says nothing about the cause, at
#: exactly the moment somebody was about to run a Git write.
#:
#: Pinning only this half would turn the failure around rather than fix it.
#: The child is what writes the bytes, so the child's half is the half that
#: has to be pinned too; a UTF-8 decode of a cp936 child is the same failure
#: with the arrow turned round. For git there is no environment variable to
#: pin it -- its path output is UTF-8 unconditionally -- so the two halves
#: are: git writes UTF-8, and this decodes UTF-8.
#:
#: ``errors="replace"`` is the promise that this guard always answers. A
#: byte that is not UTF-8 must cost the guard a wrong path, which it reports
#: and exits non-zero on, and never a dead stream. A guard that cannot answer
#: is worse than no guard, because it is the one thing a person runs before
#: doing something irreversible.
GIT_OUTPUT_ENCODING = "utf-8"


def _repo_root(start: Path) -> tuple[Path | None, str]:
    """Return (root, diagnostic). ``root`` is None when git could not answer."""
    try:
        completed = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            encoding=GIT_OUTPUT_ENCODING,
            errors="replace",
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


def _answer_on_any_console() -> None:
    """Make the guard's own output impossible to fail on.

    The guard prints the path it found, and the path may hold characters the
    machine's stdout encoding cannot represent -- a checkout under a path
    with an ideograph in it, printed on a console whose code page is
    Western. Left alone, ``print`` raises ``UnicodeEncodeError`` there, and
    the guard dies **before it answers**, with a traceback and exit code 1 --
    the same exit code as a legitimate refusal, so the crash reads as an
    answer.

    The encoding itself is left to the machine: a console that can show the
    path should show it, and this script does not decide what a terminal is
    able to display. What is changed is that a character it cannot show is
    replaced rather than raised. **A guard that cannot answer is worse than
    no guard**, because it is the one thing a person runs before doing
    something irreversible.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):  # pragma: no cover - not a TextIOBase
            pass


def main() -> int:
    _answer_on_any_console()
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
