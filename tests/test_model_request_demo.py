"""The model-call path's demonstration, watched.

**What is watched here.** ``examples/model_request_demo.py`` is
LC-P2-01's exit demonstration (A14): one call consented, one ceiling
that cannot be measured stopping the call before anything is spent, the
exchange recorded in digests and counts, and a schema request an
unprobed provider cannot make — stopped before a socket exists, with
nothing sent. **A demonstration nobody runs is a demonstration that
quietly stops working** — so this file runs it on every suite.

**And the exit code is shown to mean something.** The demonstration
carries every claim in a ``check()`` that raises. That is only true if
the raising is still there, so the demonstration is run a second time
with **the first claim it makes planted false from outside** — the
source is never edited, and what the test observes is the
demonstration's own exit code. A demonstration whose ``check()`` had
been neutered would print the same lines and exit zero; the second run
tells those two apart.

**What this does not do.** It does not make a real cloud call, and it
does not re-run every mutation of the path's properties. That is the
reviewer's job, and the work order's §4 names the witnesses the
mutations should turn red.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

DEMO = "model_request_demo"

#: The steps the demonstration names. A step that stopped running would leave
#: its heading out of the output, so their presence is a fact about what the
#: demonstration did rather than a fact about its prose.
STEPS: tuple[str, ...] = (
    "1. Consented — the material gate permits, and the approval pays",
    "2. Budgeted — a ceiling that cannot be measured stops the call",
    "3. Recorded — what the call left in the log, and what it did not",
    "4. Refused — an unprobed schema request, stopped before a socket exists",
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

spec = importlib.util.spec_from_file_location("the_demo", sys.argv[1])
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
def test_the_model_request_demo_runs(repo_root: Path) -> None:
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
    assert "The demonstration holds:" in output, "the demonstration did not finish its own summary"


@pytest.mark.integration
def test_the_demonstrations_exit_code_still_means_something(repo_root: Path) -> None:
    """A planted claim stops the show, and the exit code says so.

    The first check the demonstration makes is made false from outside —
    the source is never edited — and the demonstration must answer with a
    non-zero exit and the failed assertion on its stderr. A demonstration
    whose checks had been neutered would pass this run's first half and
    fail here.
    """
    run = _run_with_a_planted_claim(repo_root)
    assert run.returncode != 0, (
        "the demonstration exited zero with its first claim made false;"
        " its checks do not raise, and the exit code means nothing"
    )
    assert "AssertionError" in run.stderr, (
        "the planted claim did not reach the demonstration's own check"
    )
