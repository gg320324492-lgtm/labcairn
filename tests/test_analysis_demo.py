"""The exit demonstration is run by a test, so it cannot quietly stop working.

Neither ``g1_exit_demo.py`` nor ``g2_exit_demo.py`` is run by CI or by any
test, and that is a hole: an exit demonstration nobody runs is one that
quietly stops working, and G3's exit test is *"correct source/cell locators,
ledger, deterministic plot"*. This file runs LC-P1-10's exit demonstration, as
a subprocess, the way a person runs it, and asserts that it exits zero.

**The exit code is the assertion that matters.** Every claim the
demonstration makes is carried by a ``check()`` that raises rather than warns,
so a non-zero exit means a guard stopped working and a zero exit means every
one of them still holds. A test that only read the output would be testing the
prose. The output is asserted too, but for the two things the exit code
cannot say on its own: that the six steps actually ran, and that the refusals
were refusals with a reason rather than crashes.

The subprocess runs the interpreter pytest is running under, which is the
project's own environment -- the same program ``uv run python
examples/analysis_demo.py`` would start, without a second dependency
resolution in the middle of a test run. It is run **once** for the whole
module and its output is shared, because a demonstration that draws three
figures is not cheap to run twice.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

#: The demonstration, as a person runs it.
DEMO: Path = Path(__file__).parent.parent / "examples" / "analysis_demo.py"

#: The six steps, in the order the task breakdown fixes. A step that stopped
#: running would leave its heading out of the output, so their presence is a
#: fact about what the demonstration did rather than a fact about its prose.
STEPS: tuple[str, ...] = (
    "1. The controlled CSV, ingested",
    "2. The consent, and the number it authorises",
    "3. The figure, drawn from the recipe",
    "4. The manifest: the six fields, and both hashes",
    "5. The same figure, twice",
    "6. The input file changes",
)


@pytest.fixture(scope="module")
def demonstration(repo_root: Path) -> subprocess.CompletedProcess[str]:
    """The demonstration's run, once for the whole module.

    Its own temporary workspace and database, so it leaves nothing behind and
    needs nothing from the test.

    **Both ends of the pipe state their encoding.** The demonstration prints
    em-dashes, so its output is not ASCII, and an encoding left to the
    machine means the test's verdict is the machine's: the child writes in
    whatever code page the environment gives it and the parent reads it back
    in whatever code page the locale gives it, and the two agree only by
    coincidence. On this machine they do not agree -- the child writes UTF-8
    while the parent reads GBK -- and the demonstration is then reported as
    broken for a reason that says nothing about it.

    Pinning **one** side does not fix that, it turns the failure around. A
    parent told to read UTF-8 while the child still writes the machine's
    code page fails the same way, and it fails for the same reason: the two
    sides have to be pinned *together*, or neither is pinned. So the child's
    ``PYTHONIOENCODING`` is fixed here as well as the parent's ``encoding``,
    and the rest of the environment is handed over unchanged, so that pinning
    that one variable takes nothing away from the child.
    """
    return subprocess.run(
        [sys.executable, str(DEMO)],
        capture_output=True,
        text=True,
        # Both halves of the pipe are stated, and they agree: the child is
        # told to write UTF-8 and the parent decodes UTF-8. The demonstration
        # prints the paths it worked with, so its output can carry characters
        # the machine's locale encoding cannot read; leaving either half to
        # the locale is how that becomes a swallowed decode error and a
        # capture that comes back as None.
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        timeout=900,
        cwd=repo_root,
    )


@pytest.mark.integration
def test_the_exit_demonstration_runs_and_every_check_holds(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """The demonstration exits zero, and every claim it makes was made.

    A failure here is a failure of the demonstration, not of the
    demonstration's environment: it exits non-zero because a ``check()``
    raised, and the assertion prints the whole of its output so the failing
    claim is the first thing a reader sees.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr
    output = demonstration.stdout

    for step in STEPS:
        assert step in output, f"the demonstration never reached the step {step!r}"

    checks = [line for line in output.splitlines() if line.strip().startswith("[ok]")]
    assert checks, "the demonstration printed no checks at all"
    assert f"{len(checks)} checks passed." in output, (
        "the demonstration's own count of its checks does not match the number "
        "it printed, so its summary is not a fact about the run"
    )


@pytest.mark.integration
def test_the_exit_demonstration_refuses_what_it_must_refuse(
    demonstration: subprocess.CompletedProcess[str],
) -> None:
    """The consent has teeth, and a changed input is not analysed again.

    Asserted on the reasons rather than on the messages, because a reason is
    a closed vocabulary: ``approval_missing`` and ``approval_refused`` are
    different facts, and a demonstration that printed the same word for both
    would pass a test that looked at the prose.
    """
    assert demonstration.returncode == 0, demonstration.stdout + demonstration.stderr
    output = demonstration.stdout

    assert "approval_missing" in output, "a run with no approval was not refused"
    assert "approval_refused" in output, "an approval for a different selection authorised this one"
    assert "source_drifted" in output, "a run over a file that had changed was not refused"
