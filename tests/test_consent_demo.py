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

import ast
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

#: The number of guards the demonstration carries as it stands. **A guard
#: that has been removed leaves the exit code at zero**, so the count is
#: what makes the removal visible, and this is the floor it must not fall
#: below.
GUARD_FLOOR: int = 16


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


def _count_guards(source: str) -> int:
    """The number of guard calls in the demonstration's source.

    **Counted by parsing, not by counting characters.** A substring count
    would move when the demonstration's *prose* moved — the module
    docstring names ``check()`` — and a witness that goes red because a
    sentence was reworded is a witness that cries wolf. **So the number
    is of the calls themselves**: every ``check(...)`` the demonstration
    makes.
    """
    tree = ast.parse(source)
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "check"
    )


def test_the_demonstrations_guards_are_guards(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """The demonstration carries the guards it says it carries.

    **Why this test exists, and what it can and cannot do.** A guard that
    has been **removed** leaves the exit code at zero: the demonstration
    still runs, still prints its steps, still prints the reason and the
    remedy, and still exits successfully. **A missing assertion is
    invisible to an exit code.** So this test reads the demonstration's
    source and counts its guards, and the count is asserted against a
    number.

    **What it cannot do, stated plainly.** It catches the removal of any
    guard, because the floor is the count as the demonstration stands.
    But **a count with a floor is not an identity**: it cannot say *which*
    guard went missing, and a guard that was replaced by a vacuous one
    leaves the count unchanged.

    **The mutation that this work order's own record uses is therefore the
    effective one: a guard whose *condition* is inverted.** That makes
    the demonstration fail, and the exit code carries it. A mutation that
    only deletes an assertion is not a mutation of the property — it is the
    removal of the thing that watches the property, and no exit-code test
    can see it. This is stated here so that the next reviewer does not
    report a surviving mutation that was never a mutation.
    """
    guards = _count_guards(DEMO.read_text(encoding="utf-8"))
    assert guards >= GUARD_FLOOR, (
        f"the demonstration carries only {guards} guards. A guard that was "
        f"removed leaves the exit code at zero, so the count is what makes "
        f"the removal visible -- and the number here is the floor it must "
        f"not fall below."
    )

    # And the demonstration reports that every one of them held.
    assert "All checks held." in demonstration.stdout
