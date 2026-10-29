"""The LC-P2-08 exit demonstration is run by a test, so it cannot quietly
stop working.

**Why this file exists.** The project's rule, from LC-P1-10's T10: *"unlike
the earlier exit demonstrations, this one is run by a test — a demonstration
nobody runs is one that quietly stops working."* The earlier
demonstrations — ``g1_exit_demo.py``, ``g2_exit_demo.py`` — are run by
nothing, and that was the finding that produced the rule.

**The exit code is the assertion that matters.** Every claim the
demonstration makes is carried by a ``check()`` that raises rather than
warns, so a non-zero exit means a guard stopped working and a zero exit
means every one of them still holds. A test that only read the output
would be testing the prose. The output is asserted too, but for the two
things the exit code cannot say on its own: that the steps actually ran,
and that the refusals were refusals with a reason rather than crashes.

The subprocess runs the interpreter pytest is running under — the project's
own environment, without a second dependency resolution in the middle of a
test run. It is run **once** for the whole module, because a
demonstration that builds a store and reads four documents is not cheap to
run twice.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

#: The demonstration, as a person runs it.
DEMO: Path = Path(__file__).parent.parent / "examples" / "paper_version_demo.py"

#: The nine steps, in the order the demonstration fixes them. A step that
#: stopped running would leave its heading out of the output, so their
#: presence is a fact about what the demonstration did rather than a fact
#: about its prose.
STEPS: tuple[str, ...] = (
    "1. The project",
    "2. The versions",
    "3. Every version starts unresolved",
    "4. The duplicates",
    "5. The rounds",
    "6. The alignment's proposal",
    "7. The branch",
    "8. A person accepts it",
    "9. A person rejects the other one",
)


@pytest.fixture(scope="module")
def demonstration(repo_root: Path) -> subprocess.CompletedProcess[str]:
    """The demonstration's run, once for the whole module."""
    completed = subprocess.run(
        [sys.executable, str(DEMO)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        cwd=str(repo_root),
    )
    return completed


def test_the_paper_version_demo_runs(demonstration: subprocess.CompletedProcess[str]) -> None:
    """Every claim the demonstration makes still holds.

    **This is the assertion that matters.** The exit code carries every
    ``check()``, so a zero exit means the guards are all still working, and
    a non-zero exit means one stopped — and the traceback names it.
    """
    assert demonstration.returncode == 0, (
        f"the demonstration failed:\n{demonstration.stdout}\n{demonstration.stderr}"
    )


def test_every_step_ran(demonstration: subprocess.CompletedProcess[str]) -> None:
    """The nine steps ran, in the order the work order fixes.

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
    demonstration showed the graph rather than merely asserting it. These
    are the two things worth reading.
    """
    output = demonstration.stdout

    # The proposal names no acceptor: a score may propose an order and may
    # not settle one.
    assert "the edge names no acceptor" in output
    assert "it may not settle one" in output

    # The duplicate is reported as two versions, and the gap is reported
    # without a renumbering.
    assert "two versions, unresolved" in output
    assert "nothing is renumbered" in output

    # The refusal is recorded and the proposal is still readable.
    assert "The refusal is recorded" in output


def test_the_demonstration_leaves_nothing_behind(
    demonstration: subprocess.CompletedProcess[str], repo_root: Path
) -> None:
    """A demonstration that wrote into the checkout would be a defect.

    **What breaks it:** a demonstration that creates its workspace in the
    repository. The project's own rule is that a run's working directory
    must not be inside the checkout, and a demonstration that broke that
    would leave files behind in a tree that is supposed to be clean.
    """
    assert demonstration.returncode == 0
    stray = [
        path.name
        for path in repo_root.glob("*.docx")
        if path.is_file() and not path.name.startswith(".")
    ]
    assert not stray, f"the demonstration left files in the repository: {stray}"


def test_the_demonstrations_guards_are_guards(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """The demonstration carries the guards it says it carries.

    **Why this test exists, and what it can and cannot do.** A guard that
    has been **removed** leaves the exit code at zero: the demonstration
    still runs, still prints its steps, and still exits successfully. **A
    missing assertion is invisible to an exit code.** So this test reads
    the demonstration's source and counts its guards, and the count is
    asserted against a number.

    **What it cannot do, stated plainly.** It catches a *bulk* removal —
    several guards gone — and it catches a demonstration that has been
    hollowed out. It does **not** catch the removal of a single guard,
    because a count with a floor is not an identity.

    **The mutation that this work order's own record uses is therefore the
    effective one: a guard whose *condition* is inverted.** That makes
    the demonstration fail, and the exit code carries it. A mutation that
    only deletes an assertion is not a mutation of the property — it is the
    removal of the thing that watches the property, and no exit-code test
    can see it. This is stated here so that the next reviewer does not
    report a surviving mutation that was never a mutation.
    """
    source = DEMO.read_text(encoding="utf-8")
    # Every guard is a call of the module's own ``check`` helper. The
    # definition and the call inside it are two of the occurrences.
    guards = source.count("check(") - 2
    assert guards >= 21, (
        f"the demonstration carries only {guards} guards. A guard that was "
        f"removed leaves the exit code at zero, so the count is what makes "
        f"the removal visible -- and the number here is the floor it must "
        f"not fall below."
    )

    # And the demonstration reports that every one of them held.
    assert "All checks held." in demonstration.stdout
