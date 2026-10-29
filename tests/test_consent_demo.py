"""The LC-P2-06 exit demonstration is run by a test, so it cannot quietly
stop working.

**Why this file exists.** The project's rule, from LC-P1-10's T10: *"a
demonstration nobody runs is one that quietly stops working."* The earlier
demonstrations are run by nothing, and that was the finding that produced
the rule.

**The exit code is the assertion that matters.** Every claim the
demonstration makes is carried by a ``check()`` that raises rather than
warns, so a zero exit means every one of them still holds, and a non-zero
exit names the one that stopped. A test that only read the output would be
testing the prose. The output is asserted too, but for the two things the
exit code cannot say on its own: that the steps actually ran, and that the
refusals were refusals with a reason rather than crashes.

The subprocess runs the interpreter pytest is running under — the project's
own environment, without a second dependency resolution in the middle of a
test run.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

#: The demonstration, as a person runs it.
DEMO: Path = Path(__file__).parent.parent / "examples" / "consent_demo.py"

#: The five steps, in the order the demonstration fixes them. A step that
#: stopped running would leave its heading out of the output, so their
#: presence is a fact about what the demonstration did rather than a fact
#: about its prose.
STEPS: tuple[str, ...] = (
    "1. A grant, and a use it permits",
    "2. A request to transmit, with no transmit grant",
    "3. A request to a destination the grant does not name",
    "4. A withdrawal, and the copy it reaches",
    "5. A material with no grant at all",
)


@pytest.fixture(scope="module")
def demonstration(repo_root: Path) -> subprocess.CompletedProcess[str]:
    """The demonstration's run, once for the whole module."""
    return subprocess.run(
        [sys.executable, str(DEMO)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        cwd=str(repo_root),
    )


def test_the_consent_demo_runs(demonstration: subprocess.CompletedProcess[str]) -> None:
    """Every claim the demonstration makes still holds.

    **This is the assertion that matters.** The exit code carries every
    ``check()``, so a zero exit means the guards are all still working.
    """
    assert demonstration.returncode == 0, (
        f"the demonstration failed:\n{demonstration.stdout}\n{demonstration.stderr}"
    )


def test_every_step_ran(demonstration: subprocess.CompletedProcess[str]) -> None:
    """The five steps ran, in the order the work order fixes.

    **What breaks it:** a step that stopped running. The exit code would
    still be zero if a step were removed along with its checks, so the
    headings are asserted separately.
    """
    for step in STEPS:
        assert step in demonstration.stdout, f"the step {step!r} did not run"


def test_the_demonstration_says_the_things_that_matter(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """The output says the two things the exit code cannot.

    **The exit code says a guard holds.** It cannot say *which* refusals
    were refusals with a reason rather than crashes, and it cannot say the
    demonstration showed the machinery rather than merely asserting it.
    """
    output = demonstration.stdout

    # The refusal names its reason and its remedy.
    assert "purpose_not_granted" in output
    assert "destination_not_granted" in output
    assert "remedy" in output

    # And the two facts the exit code cannot carry: the approval was not
    # spent, and the archive was not opened.
    assert "asking is not spending" in output
    assert "not opened, not listed and not measured" in output


def test_the_demonstration_leaves_nothing_behind(repo_root: Path) -> None:
    """A demonstration that wrote into the checkout would be a defect."""
    stray = [
        path.name
        for path in repo_root.glob("*.docx")
        if path.is_file() and not path.name.startswith(".")
    ]
    assert not stray, f"the demonstration left files in the repository: {stray}"
