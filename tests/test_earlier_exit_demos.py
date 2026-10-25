"""The exit demonstrations of the earlier gates, watched.

**What is watched here.** G1's and G2's exit demonstrations —
``examples/g1_exit_demo.py``, ``examples/g2_exit_demo.py`` and
``examples/g2_uncertain_demo.py`` — are the demonstrations that **nothing
runs**. The repository says so about itself, in two places:
``tests/test_analysis_demo.py`` and ``tests/test_smoke_path.py`` both open
by saying *"Neither g1_exit_demo.py nor g2_exit_demo.py is run by CI or by
any test, and that is a hole"* — and the second adds that **G3's
independent review named it as one**.

**Why it is still a hole.** An exit demonstration is a gate's **exit
test**: it is the thing a gate is accepted on. G1's exit test is *"fake
provider, typed tools, safe workspace"*; G2's is *"persistent task, stage
plan, injected restart"*. A demonstration nobody runs is a demonstration
that **quietly stops being true** — and unlike a test, it does not fail
loudly; it simply stops being evidence, and the gate it closed stays closed
on a claim that is no longer measured.

**The exit code is the assertion, and the exit code has to be shown to
mean something.** Each of these demonstrations carries every claim in a
``check()`` that *raises* rather than warns, so a non-zero exit means a
guard stopped working. **That is only true if the raising is still there**,
and this file checks that too: each demonstration is run a second time with
**one of its claims planted false from outside**, and it must then exit
**non-zero**.

**Why the second run is necessary.** A demonstration whose ``check()`` had
been neutered — made to always pass — would print the same ``[ok]`` lines,
print the same summary, and exit zero. **The first run alone cannot tell
"every claim held" from "the claims were never checked".** The second run
tells them apart, and it is the same shape as G4's: the fault is planted
by the driver, **the demonstration's source is never edited**, and what the
test observes is the demonstration's own exit code.

**The count is checked against itself, not against a number written here.**
A demonstration that printed fewer checks would still exit zero if it also
printed a smaller summary, so the witness compares the number of ``[ok]``
lines with the number the demonstration's own summary claims. **The numbers
36, 14 and 18 are not written down here on purpose**: a demonstration that
grows a check is not broken, and a witness that failed when it grew would
teach the next person to stop adding checks.

**One of the three is Windows-only in part, and the witness says so.**
G1's demonstration makes a **Windows junction** to show that a junction is
not a symlink and that a junction escape is refused. That case needs
``cmd``, so it is real evidence **only on Windows**; elsewhere the
demonstration says the junction was "skipped: not permitted here" and the
rest of its claims still stand. **The witness does not pretend the case ran
where it could not**: it runs the demonstration, and the demonstration's own
output says which case it skipped.

**What this does not do.** It does not re-open G1 or G2. Whether those two
gates get an independent review is a separate question, and one that is the
owner's — see ``docs/plans/LC-P1-13-14-task-breakdown.md`` §1.4.4. **This
file makes their exit demonstrations measured again; it does not make their
reviews independent.**
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

#: The three demonstrations, and the steps each one names. A step that
#: stopped running would leave its heading out of the output, so their
#: presence is a fact about what the demonstration did rather than a fact
#: about its prose.
DEMOS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "g1_exit_demo",
        (
            "1. An operation that is allowed to happen",
            "2. What must be refused",
            "3. Budgets, and zero versus unknown",
            "4. The record that survives",
        ),
    ),
    (
        "g2_exit_demo",
        (
            "1. Create a task, a run, and a stage; write a result",
            "2. Kill the process mid-flight, on a real child",
            "3. Restart against the same database file and resume",
            "4. A pending approval is still pending",
        ),
    ),
    (
        "g2_uncertain_demo",
        (
            "1. The process dies between writing and confirming",
            "2. The system records what it cannot tell",
            "3. Replay is refused until a probe resolves it",
            "4. A probe over the actual bytes resolves it",
        ),
    ),
)

#: The driver that plants the fault. It loads the demonstration **as a
#: module** and wraps its ``check()``, so the demonstration's source is
#: never edited and what the test observes is the demonstration's own
#: behaviour under the fault.
#:
#: The fault is planted on **the first check the demonstration makes**, and
#: not on a label written down here: a label written down here would be a
#: second thing to keep in step with the demonstration, and this repository
#: has been bitten by exactly that more than once.
DRIVER: str = """
import importlib.util
import sys

demo_path = sys.argv[1]
spec = importlib.util.spec_from_file_location("the_demo", demo_path)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)

unplanted = demo.check
planted = []


def check(label, condition, detail=""):
    # The first claim the demonstration makes is made false. Every other
    # claim is left alone, so the run is the demonstration's own run with one
    # thing wrong -- not a different demonstration.
    if not planted:
        planted.append(label)
        condition = False
    return unplanted(label, condition, detail)


demo.check = check
raise SystemExit(demo.main())
"""


def _environment() -> dict[str, str]:
    """The child's environment, with the two variables that are its own business.

    **Both ends of the pipe state their encoding.** The demonstrations print
    em-dashes and the paths they worked with, so their output is not ASCII.
    Leaving either half to the machine's locale is how a demonstration comes
    back *broken for a reason that says nothing about it* — and that failure
    is indistinguishable from a real one, which is the worst kind.
    """
    return {**os.environ, "PYTHONIOENCODING": "utf-8", "COLUMNS": "200"}


def _run(repo_root: Path, name: str) -> subprocess.CompletedProcess[str]:
    """One demonstration, run the way a person runs it."""
    return subprocess.run(
        [sys.executable, str(repo_root / "examples" / f"{name}.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_environment(),
        timeout=900,
        cwd=repo_root,
    )


def _run_with_a_planted_claim(repo_root: Path, name: str) -> subprocess.CompletedProcess[str]:
    """The same demonstration, with its first claim planted false.

    The child is the demonstration itself — the same file, the same
    ``main()`` — and the fault is planted by the driver before the
    demonstration runs.
    """
    return subprocess.run(
        [sys.executable, "-c", DRIVER, str(repo_root / "examples" / f"{name}.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_environment(),
        timeout=900,
        cwd=repo_root,
    )


@pytest.mark.integration
@pytest.mark.parametrize(("name", "steps"), DEMOS)
def test_an_earlier_gates_exit_demonstration_still_holds(
    repo_root: Path,
    name: str,
    steps: tuple[str, ...],
) -> None:
    """The demonstration exits zero, reached every step, and counted itself right.

    The exit code is the assertion that matters. Every claim each of these
    demonstrations makes is carried by a ``check()`` that raises rather than
    warns, so a non-zero exit means a guard stopped working and a zero exit
    means every one of them still holds. A test that only read the output
    would be testing the prose.
    """
    run = _run(repo_root, name)
    assert run.returncode == 0, run.stdout + run.stderr
    output = run.stdout

    for step in steps:
        assert step in output, f"{name} never reached the step {step!r}"

    checks = [line for line in output.splitlines() if line.strip().startswith("[ok]")]
    assert checks, f"{name} printed no checks at all"
    assert f"{len(checks)} checks passed." in output, (
        f"{name}'s own count of its checks does not match the number it "
        "printed, so its summary is not a fact about the run"
    )


@pytest.mark.integration
@pytest.mark.parametrize(("name", "steps"), DEMOS)
def test_the_demonstrations_exit_code_still_means_something(
    repo_root: Path,
    name: str,
    steps: tuple[str, ...],
) -> None:
    """A planted false claim makes the demonstration fail.

    **This is what makes the other test mean anything.** A demonstration
    whose ``check()`` had been neutered — made to always pass — would
    print the same ``[ok]`` lines, print the same summary and exit zero.
    **The first test cannot tell "every claim held" from "the claims were
    never checked".** This one tells them apart.

    So the demonstration is run a second time with **its first claim planted
    false from outside**: the driver wraps the demonstration's own
    ``check()``, and **the demonstration's source is never edited**. The
    demonstration then makes the same run with one thing wrong, and it must
    exit non-zero.

    The failure is expected here — it is the demonstration working. A
    **zero** exit under a planted false claim is the failure: it means the
    demonstration's claims are not being checked at all, and every other
    assertion in this file would then be reading a demonstration that says
    nothing.
    """
    run = _run_with_a_planted_claim(repo_root, name)
    assert run.returncode != 0, (
        f"{name} exited zero with a false claim planted, so its exit code "
        "does not mean that its checks held -- and every other assertion "
        "about it is reading a demonstration that says nothing:\n" + run.stdout
    )
    assert "FAILED:" in run.stdout + run.stderr, (
        f"{name} did not exit zero under a planted false claim, and it did "
        "not say which claim failed either -- so the failure is not the "
        "demonstration's own, and the test above is not measuring what it "
        "thinks it is:\n" + run.stdout + run.stderr
    )
