"""CONTRIBUTING.md documents `scripts/check_repo_root.py` as a runnable guard.

A documented command that does not exist is a documentation defect, and an
unguarded guard is worse than none: it reads as protection that is not there.
These tests run the script for real and assert both directions, plus the case
that matters most -- a repository that exists at the cwd but is *not* this
project.

They also run it at a checkout path that is not ASCII. A guard that can only
answer at a path it can spell in the machine's locale encoding fails exactly
where the hazard is likeliest, and it fails by crashing rather than by
answering, which is the one thing a guard must never do.
"""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_repo_root.py"

#: A directory name that is not ASCII.
#:
#: The guard has to answer at a path that is not ASCII, and the characters
#: matter: the defect was found on a machine whose locale encoding is cp936,
#: where git writes the path as UTF-8 and those bytes cannot be read back
#: as cp936. Chinese is the case that reproduces it.
NON_ASCII_NAME = "路径"

#: A wrapper that runs the guard on a machine whose locale encoding cannot
#: read the path.
#:
#: Which encoding a pipe is decoded with is the machine's business, and on a
#: machine whose locale encoding cannot represent the characters in the
#: checkout path, the decode fails -- inside subprocess's reader thread,
#: where the exception is swallowed and the capture comes back as None. The
#: guard then died on ``completed.stdout.strip()`` with "AttributeError:
#: 'NoneType' object has no attribute 'strip'", at exactly the moment
#: somebody was about to run a Git write.
#:
#: This wrapper forces the narrowest possible answer to "which encoding is
#: that?": every text stream created without a stated encoding is decoded as
#: ASCII here. That is a machine no UTF-8 locale has, and it is what makes
#: the test a witness on every machine rather than only on the ones whose
#: locale happens to disagree with git. A guard that states its encoding is
#: unaffected by the wrapper; a guard that leaves it to the machine is not,
#: and that is the whole point.
NARROW_LOCALE_WRAPPER = textwrap.dedent(
    """
    import io
    import runpy
    import sys

    _original = io.TextIOWrapper


    def _narrow(stream, *args, **kwargs):
        if kwargs.get("encoding") is None and "encoding" not in args:
            kwargs["encoding"] = "ascii"
        return _original(stream, *args, **kwargs)


    io.TextIOWrapper = _narrow
    runpy.run_path(sys.argv[1], run_name="__main__")
    """
)


def _run(
    cwd: Path,
    *,
    script: Path | None = None,
    argv: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    # The guard writes the path it found to its own standard output, and that
    # output is encoded with the machine's locale encoding -- which is not
    # necessarily able to represent the path. This says UTF-8, so that the
    # guard can *print* a path with any character in it. It does not touch
    # the encoding of the pipe the guard reads git's output through: that is
    # the machine's locale encoding, and it is the thing under test.
    environment["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        argv if argv is not None else [sys.executable, str(script or SCRIPT)],
        capture_output=True,
        text=True,
        # Explicit, not the system code page: a decode error surfaces in
        # subprocess's reader thread, which returns None rather than raising
        # where the caller can see it. CI is UTF-8; a Windows checkout on
        # another code page is not.
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
        env=environment,
        check=False,
        timeout=60,
    )


def _checkout(base: Path, name: str) -> Path:
    """A checkout of this project at *base*/*name*.

    It holds the two things the guard looks at: its own script, and the
    marker directory it checks for. The guard never asks anything else of a
    checkout, so this is a checkout in the sense the guard means.
    """
    checkout = base / name
    (checkout / "scripts").mkdir(parents=True)
    (checkout / "src" / "labcairn").mkdir(parents=True)
    shutil.copy2(SCRIPT, checkout / "scripts" / SCRIPT.name)
    shutil.copy2(
        SCRIPT.parent.parent / "src" / "labcairn" / "__init__.py",
        checkout / "src" / "labcairn" / "__init__.py",
    )
    subprocess.run(["git", "init", "-q", str(checkout)], check=True, timeout=60)
    return checkout


def _narrow_locale_guard(
    cwd: Path, script: Path, wrapper: Path
) -> subprocess.CompletedProcess[str]:
    """Run *script* on a machine whose locale encoding cannot read the path."""
    return _run(cwd, argv=[sys.executable, str(wrapper), str(script)])


def test_the_script_documented_in_contributing_exists() -> None:
    contributing = SCRIPT.parent.parent / "CONTRIBUTING.md"
    assert SCRIPT.is_file(), f"CONTRIBUTING.md documents {SCRIPT.name} but it does not exist"
    assert "check_repo_root.py" in contributing.read_text(encoding="utf-8")


def test_it_passes_inside_the_checkout() -> None:
    repo_root = SCRIPT.parent.parent
    result = _run(repo_root)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK: repository root is this LabCairn checkout" in result.stdout


def test_it_fails_in_a_directory_that_is_not_a_repository(tmp_path: Path) -> None:
    """The ancestor-`git init` hazard: no repository here *yet* is the danger."""
    result = _run(tmp_path)
    assert result.returncode != 0, result.stdout
    assert "FAIL" in result.stdout
    assert "ancestor" in result.stdout.lower()


def test_it_fails_in_a_repository_that_is_not_labcairn(tmp_path: Path) -> None:
    """Right kind of thing, wrong project: the case a bare rev-parse check misses."""
    other = tmp_path / "other-repo"
    other.mkdir()
    subprocess.run(["git", "init", "-q", str(other)], check=True, timeout=60)
    (other / "README.md").write_text("not LabCairn\n", encoding="utf-8")

    result = _run(other)
    assert result.returncode != 0, result.stdout
    assert "not the LabCairn checkout" in result.stdout
    assert "other-repo" in result.stdout


# --------------------------------------------------------------------------- #
# The guard at a path that is not ASCII
#
# Every test above runs in a directory pytest named, and pytest names those
# in ASCII. A guard that cannot answer at a path with a non-ASCII character
# in it is a guard that fails exactly where the hazard is likeliest -- a
# machine whose locale encoding is not UTF-8 and whose checkout path says
# something in its own script.
# --------------------------------------------------------------------------- #


def test_it_answers_at_a_checkout_path_that_is_not_ascii(tmp_path: Path) -> None:
    """The guard answers at a path it cannot spell in the machine's locale.

    On a machine whose locale encoding is cp936 this is the reproduction:
    git writes the path as UTF-8, the guard decoded it as cp936, the decode
    failed in subprocess's reader thread, and the guard died with an
    AttributeError instead of saying whether the checkout was safe.
    """
    checkout = _checkout(tmp_path, NON_ASCII_NAME)
    result = _run(checkout, script=checkout / "scripts" / SCRIPT.name)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK: repository root is this LabCairn checkout" in result.stdout
    assert "Traceback" not in result.stderr


def test_it_answers_when_the_locale_cannot_read_the_path(tmp_path: Path) -> None:
    """The guard answers on a machine whose locale cannot read the path.

    This is the witness that does not depend on the machine: the wrapper
    forces every text stream created without a stated encoding to be decoded
    as ASCII, which is what a narrow locale looks like from inside
    subprocess. A guard that states its encoding is unaffected; a guard that
    leaves it to the machine dies here, whatever the machine's locale is.
    """
    checkout = _checkout(tmp_path, NON_ASCII_NAME)
    wrapper = tmp_path / "narrow-locale.py"
    wrapper.write_text(NARROW_LOCALE_WRAPPER, encoding="utf-8")

    result = _narrow_locale_guard(checkout, checkout / "scripts" / SCRIPT.name, wrapper)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK: repository root is this LabCairn checkout" in result.stdout
    assert "Traceback" not in result.stderr


def test_it_still_refuses_a_non_ascii_repository_that_is_not_labcairn(tmp_path: Path) -> None:
    """The answer is still the answer: exit 1, and the same words.

    The guard's exit codes and its diagnostics are its contract, and the fix
    is not allowed to change either. A repository at a path that is not
    ASCII, which is not this project, must still be refused -- and refused
    with a message rather than a traceback.
    """
    base = tmp_path / NON_ASCII_NAME
    checkout = _checkout(base, "LabCairn")
    other = base / "other-repo"
    other.mkdir()
    subprocess.run(["git", "init", "-q", str(other)], check=True, timeout=60)
    (other / "README.md").write_text("not LabCairn\n", encoding="utf-8")
    wrapper = tmp_path / "narrow-locale.py"
    wrapper.write_text(NARROW_LOCALE_WRAPPER, encoding="utf-8")

    result = _narrow_locale_guard(other, checkout / "scripts" / SCRIPT.name, wrapper)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "not the LabCairn checkout" in result.stdout
    assert "Traceback" not in result.stderr


def test_the_guard_invokes_git_read_only() -> None:
    """A guard that can mutate is not a guard.

    Checked against the AST rather than the text: a substring scan flags the
    module docstring, which legitimately contains the word "checkout". What
    matters is which command lists the script actually builds.
    """
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    # -C asks git about another directory; it reads, it does not write.
    read_only = {"rev-parse", "--show-toplevel", "--is-inside-work-tree", "-C"}
    write_verbs = {
        "add",
        "commit",
        "checkout",
        "reset",
        "clean",
        "stash",
        "restore",
        "rm",
        "mv",
        "push",
        "pull",
        "merge",
        "rebase",
        "init",
        "clone",
        "gc",
    }

    commands: list[list[str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        target = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if target not in {"run", "check_output", "check_call", "Popen", "call"}:
            continue
        if not node.args:
            continue
        first = node.args[0]
        if not isinstance(first, ast.List):
            continue
        # Only literal string elements are inspected; non-literals such as
        # str(start) are arguments, not commands.
        literal = [
            e.value for e in first.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)
        ]
        if literal and literal[0] == "git":
            commands.append(literal)

    assert commands, "the guard must be found to invoke git at least once"
    for command in commands:
        for token in command[1:]:
            if token.startswith("-"):
                assert token in read_only, f"non-read-only git option in guard: {token}"
            else:
                assert token not in write_verbs, f"guard may run git {token}"
