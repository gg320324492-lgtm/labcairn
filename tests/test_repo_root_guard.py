"""CONTRIBUTING.md documents `scripts/check_repo_root.py` as a runnable guard.

A documented command that does not exist is a documentation defect, and an
unguarded guard is worse than none: it reads as protection that is not there.
These tests run the script for real and assert both directions, plus the case
that matters most -- a repository that exists at the cwd but is *not* this
project.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_repo_root.py"


def _run(cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        # Explicit, not the system code page: a decode error surfaces in
        # subprocess's reader thread, which returns None rather than raising
        # where the caller can see it. CI is UTF-8; a Windows checkout on
        # another code page is not.
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
        check=False,
        timeout=60,
    )


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
