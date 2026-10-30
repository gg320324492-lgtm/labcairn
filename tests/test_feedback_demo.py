"""The feedback chain's exit demonstration, watched.

**What is watched here.** ``examples/feedback_demo.py`` is LC-P2-09's exit
test: a comment found in a synthetic DOCX, the edit made in answer to it, a
response refused for want of evidence and then recorded with it, the same
issue in a later version, an assessment that says *"not established"*, and
the four annotation events in the task's own stream. **A demonstration nobody
runs is a demonstration that quietly stops working** — so this file runs it
on every suite.

**And the exit code is shown to mean something.** The demonstration carries
every claim in a ``check()`` that raises. That is only true if the raising is
still there, so the demonstration is run a second time with **the first
claim it makes planted false from outside** — the source is never edited, and
what the test observes is the demonstration's own exit code. A demonstration
whose ``check()`` had been neutered would print the same lines and exit zero;
the second run tells those two apart.

**What this does not do.** It does not re-run every mutation of the chain's
properties. That is the reviewer's job, and ADR-0017 names the witnesses the
mutations should turn red.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

DEMO = "feedback_demo"

#: The steps the demonstration names. A step that stopped running would leave
#: its heading out of the output, so their presence is a fact about what the
#: demonstration did rather than a fact about its prose.
STEPS: tuple[str, ...] = (
    "1. The project",
    "2. The version graph",
    "3. The comment, and the two questions it answers",
    "4. The edit",
    "5. A response with no evidence",
    "6. The same judgment, with what decided it",
    "7. The same issue in a later version",
    "8. A later assessment",
    "9. The chain, in the task's own event stream",
)

#: The driver that plants the fault. It loads the demonstration **as a
#: module** and wraps its ``check()``, so the source is never edited.
#:
#: The fault is planted on **the first check the demonstration makes**, not on
#: a message written down here: a message written down here would be a second
#: thing to keep in step with the demonstration.
DRIVER: str = """
import importlib.util
import sys

demo_path = sys.argv[1]
spec = importlib.util.spec_from_file_location("the_demo", demo_path)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)

unplanted = demo.check
planted = []


def check(condition, message=""):
    if not planted:
        planted.append(message)
        condition = False
    return unplanted(condition, message)


demo.check = check
raise SystemExit(demo.main())
"""


def _environment() -> dict[str, str]:
    """The child's environment, with both ends of the pipe stating their encoding."""
    return {**os.environ, "PYTHONIOENCODING": "utf-8", "COLUMNS": "200"}


def _run(repo_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(repo_root / "examples" / f"{DEMO}.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_environment(),
        timeout=900,
        cwd=repo_root,
    )


def _run_with_a_planted_claim(repo_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", DRIVER, str(repo_root / "examples" / f"{DEMO}.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_environment(),
        timeout=900,
        cwd=repo_root,
    )


@pytest.mark.integration
def test_the_feedback_demo_runs(repo_root: Path) -> None:
    """It exits zero, and it reached every step it names.

    The exit code is the assertion that matters: every claim is carried by a
    ``check()`` that raises, so a non-zero exit means a guard stopped working
    and a zero exit means every one of them still holds.
    """
    run = _run(repo_root)
    assert run.returncode == 0, run.stdout + run.stderr
    output = run.stdout
    for step in STEPS:
        assert step in output, f"the demonstration never reached the step {step!r}"
    assert "All checks held." in output, "the demonstration did not finish its own summary"
    assert "Feedback rows: 2" in output, "the two rounds' comments are two rows"


@pytest.mark.integration
def test_the_demonstrations_exit_code_still_means_something(repo_root: Path) -> None:
    """With one claim planted false, the demonstration exits non-zero.

    **This is the half a first run cannot see.** A demonstration whose
    ``check()`` always passed would print the same steps and exit zero; the
    planted run is what tells the two apart.
    """
    run = _run_with_a_planted_claim(repo_root)
    assert run.returncode != 0, (
        "the demonstration exited zero with its first claim planted false, so its "
        "exit code does not carry its claims\n" + run.stdout
    )
    assert "AssertionError" in run.stdout + run.stderr, "the planted claim did not raise"
