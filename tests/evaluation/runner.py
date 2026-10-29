"""Running a gate class, as a subprocess.

**Why a subprocess and not an in-process pytest run.** The protocol's classes
are **partitions of this repository's test suite**, and a suite that runs
inside the suite is a suite whose result cannot be trusted: the inner run
inherits the outer run's plugins, fixtures and working directory, and a
collection error in the inner run takes the outer run with it. A subprocess
gets a clean interpreter, a clean working directory and its own exit code,
and it is the same way the CI runs these files.

**The temporary directory rules are not optional here.** The repository's
own rules (``CLAUDE.md``, "Running the suite") say three things that this
module has to honour, because the harness runs the suite and inherits every
one of their failure modes:

* ``--basetemp`` goes **outside** the repository. Inside it, two tests fail
  for a reason that has nothing to do with the property under test, and the
  checkout is left dirty.
* The temporary directory goes **outside** the repository too, and not
  merely off the C drive — a workspace inside the checkout makes the run
  depend on the tree it runs in.
* **Two runs must not share one temporary directory**, and this machine has
  other projects running: ``MPLCONFIGDIR`` is pinned under the temporary
  directory, so two runs sharing one fight over matplotlib's font cache.

So the harness makes a directory **of its own** under the ambient temporary
directory, points ``TEMP``, ``TMP``, ``MPLCONFIGDIR`` and
``LABCAIRN_TEMP_ROOT`` at it, and **refuses to run** if that directory turns
out to be inside the repository.

**One flag that changes what is measured, and why.** The inner run gets
``--continue-on-collection-errors``, which the CI step does not use. The
reason is that a collection error in one file would otherwise abandon the
rest of the class, and the harness's job is to report *how many* cases
passed and which failed. A collection error is still reported — as an
errored case, in the report, with its message.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .junit import parse_junit
from .model import TestOutcome

#: The flags the inner run always carries.
#:
#: ``-p no:cacheprovider`` keeps ``.pytest_cache`` out of the checkout, so
#: running the harness does not dirty the tree it measures.
INNER_FLAGS: Final[tuple[str, ...]] = (
    "-p",
    "no:cacheprovider",
    "--continue-on-collection-errors",
    "-q",
)

#: How long a class may take before the harness gives up on it.
DEFAULT_TIMEOUT_SECONDS: Final = 3600.0


@dataclass(frozen=True, slots=True)
class ClassRun:
    """What one class's subprocess produced."""

    #: The class key.
    key: str
    #: The files the class was run over.
    files: tuple[str, ...]
    #: Every collected case.
    outcomes: tuple[TestOutcome, ...]
    #: The inner pytest's exit code.
    exit_code: int
    #: How long the run took, in seconds.
    duration_seconds: float
    #: The inner pytest's standard output, trimmed.
    stdout: str
    #: The inner pytest's standard error, trimmed.
    stderr: str
    #: Why the run could not be made at all, when it could not be.
    error: str = ""

    @property
    def ran(self) -> bool:
        """Whether the subprocess ran and produced a report."""
        return not self.error


def make_run_root(temp_root: Path, key: str) -> Path:
    """A directory of this run's own, for one class.

    The name carries the process id as well as the class, so two harness
    runs on the same machine never share one.
    """
    root = temp_root / f"labcairn-evaluation-{os.getpid()}" / key
    root.mkdir(parents=True, exist_ok=True)
    return root


def _environment(root: Path, repo_root: Path) -> dict[str, str]:
    """The environment the inner run gets.

    The temporary variables are pointed at ``root`` and nothing else is
    changed, so the inner run sees the same installed package, the same
    ``PATH`` and the same credentials-as-none as the outer one.
    """
    env = dict(os.environ)
    matplotlib = root / "matplotlib"
    matplotlib.mkdir(parents=True, exist_ok=True)
    env["TEMP"] = str(root)
    env["TMP"] = str(root)
    # ``TMPDIR`` is set as well, and it comes first: Python's
    # :func:`tempfile.gettempdir` looks at ``TMPDIR``, then ``TEMP``, then
    # ``TMP`` — in that order, on **every** platform. So an environment that
    # carries a ``TMPDIR`` wins over the two this module sets, and the inner
    # run would put its temporary files somewhere this module never looked at.
    # The isolation would have a hole in it the same on Windows as on Linux,
    # and the hole would only open on a machine that happens to have a
    # ``TMPDIR`` set.
    env["TMPDIR"] = str(root)
    env["MPLCONFIGDIR"] = str(matplotlib)
    env["LABCAIRN_TEMP_ROOT"] = str(root)
    # The inner run must not inherit a base temp directory that pytest would
    # clear out from under an outer run that shares it.
    env["PYTEST_ADDOPTS"] = ""
    return env


def _assert_outside_repository(root: Path, repo_root: Path) -> None:
    """Refuse a temporary directory that is inside the repository.

    The repository's own rules are explicit that a workspace inside the
    checkout makes a run depend on the tree it runs in, and two of its
    tests enforce it. The harness runs the whole suite, so it would
    inherit the failure — and it would also leave the checkout dirty. The
    check is here rather than in a test because the harness is a tool
    somebody runs by hand.
    """
    resolved_root = root.resolve()
    resolved_repo = repo_root.resolve()
    if resolved_root == resolved_repo or resolved_repo in resolved_root.parents:
        msg = (
            f"the harness's temporary directory {resolved_root} is inside the "
            f"repository {resolved_repo}; point TEMP at a directory outside "
            "the checkout (E:\\labcairn-local\\tmp on this machine)"
        )
        raise ValueError(msg)


def run_class(
    repo_root: Path,
    key: str,
    files: tuple[str, ...],
    temp_root: Path,
    *,
    python: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> ClassRun:
    """Run one gate class's files as a pytest subprocess."""
    if not files:
        return ClassRun(
            key=key,
            files=(),
            outcomes=(),
            exit_code=0,
            duration_seconds=0.0,
            stdout="",
            stderr="",
            error="no file is filed under this class, so there was nothing to run",
        )

    # The check comes before the directory is made, so a refused run leaves
    # nothing behind in the tree it was about to measure.
    _assert_outside_repository(temp_root, repo_root)
    root = make_run_root(temp_root, key)
    env = _environment(root, repo_root)
    junit = root / "junit.xml"
    base_temp = root / "basetemp"

    command = [
        python or sys.executable,
        "-m",
        "pytest",
        *files,
        f"--junit-xml={junit}",
        f"--basetemp={base_temp}",
        *INNER_FLAGS,
    ]

    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=str(repo_root),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        duration = time.monotonic() - started
        return ClassRun(
            key=key,
            files=files,
            outcomes=(),
            exit_code=-1,
            duration_seconds=duration,
            stdout="",
            stderr="",
            error=f"the class did not finish within {timeout:.0f} seconds",
        )
    duration = time.monotonic() - started

    if not junit.is_file():
        return ClassRun(
            key=key,
            files=files,
            outcomes=(),
            exit_code=completed.returncode,
            duration_seconds=duration,
            stdout=completed.stdout[-4000:],
            stderr=completed.stderr[-4000:],
            error=(
                "the class produced no JUnit XML, so its outcomes are unknown; "
                "a class with no report is not a class that passed"
            ),
        )

    outcomes = parse_junit(junit, repo_root=repo_root)
    return ClassRun(
        key=key,
        files=files,
        outcomes=outcomes,
        exit_code=completed.returncode,
        duration_seconds=duration,
        stdout=completed.stdout[-4000:],
        stderr=completed.stderr[-4000:],
    )
