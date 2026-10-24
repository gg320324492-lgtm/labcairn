"""The parallel runs' temp isolation, watched.

**The property.** When the suite is run in parallel — which the CI workflow
does, with ``pytest-xdist`` — every worker gets a temporary directory of its
own, so two workers never write to the same file.

**Why it needs watching.** The product pins ``MPLCONFIGDIR`` to
``tempfile.gettempdir() / "labcairn-matplotlib"``: a path computed from the
*ambient* temp directory, not from the test's own ``tmp_path``. Matplotlib
writes its font cache there, and two processes building that cache at the same
moment can read a half-written one. ``pytest-xdist`` isolates ``tmp_path`` on
its own, but it cannot isolate a path the product computes from the
environment — so the repository's root ``conftest.py`` does that, by pointing
the process's temp directory at a directory named after the worker.

**What goes wrong without it.** Nothing, visibly, and that is the problem.
The failure is a race: it appears when two workers happen to build the font
cache at the same moment, on a machine that happens to be busy. It reads as a
sporadic, unrelated failure in a rendering test — and a gate that fails
sporadically gets ignored, which is worse than a gate that is slow.

So this file watches the mechanism directly, in a way that is **red the moment
the mechanism is gone**, and it does it in an ordinary sequential run: it asks
a subprocess what temp directory it would get, with and without a worker id.

Two things are watched here, and the second is the one that matters:

* a worker gets a directory **named after it**, and
* two different workers get **different** directories.

The second is the property the font cache depends on. The first is only how
it is arranged.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

#: The program the subprocess runs: import the repository's root ``conftest``
#: — which is what applies the isolation — and print the temp directory the
#: process ends up with.
_PROBE = "import tempfile; import conftest; print(tempfile.gettempdir())"


def _temp_dir_for_worker(repo_root: Path, probe_root: Path, worker: str | None) -> str:
    """The temp directory a process would use, with ``worker`` set or not.

    Run in a subprocess, because the answer depends on module-import order:
    the isolation has to be applied *before* anything reads
    ``tempfile.gettempdir()``, and in this process that has already happened.
    """
    env = dict(os.environ)
    if worker is None:
        env.pop("PYTEST_XDIST_WORKER", None)
    else:
        env["PYTEST_XDIST_WORKER"] = worker
    # A root the test owns, so the probe writes nothing outside it — and
    # nothing inside the repository, which other tests hold to be clean.
    env["LABCAIRN_TEMP_ROOT"] = str(probe_root)
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"the probe failed: {proc.stderr}"
    return proc.stdout.strip()


def test_a_worker_is_given_a_directory_named_after_itself(repo_root: Path, tmp_path: Path) -> None:
    """The worker's directory carries the worker's name, so it is its own."""
    temp_dir = _temp_dir_for_worker(repo_root, tmp_path, "gw0")
    assert "gw0" in Path(temp_dir).name, (
        f"a worker's temp directory must carry the worker's name, but gw0 was given {temp_dir!r}"
    )


def test_two_workers_are_given_two_different_directories(repo_root: Path, tmp_path: Path) -> None:
    """The property the font cache depends on: no two workers share a path.

    This is the one that goes red if the isolation is removed. The first test
    above would still pass, because a single worker's directory would still be
    named after it — but both workers would be pointing at the *same* path
    underneath, which is the race.
    """
    first = _temp_dir_for_worker(repo_root, tmp_path, "gw0")
    second = _temp_dir_for_worker(repo_root, tmp_path, "gw1")
    assert first != second, (
        f"two workers were given the same temp directory ({first!r}); "
        "they would share matplotlib's font cache and race to write it"
    )


def test_a_run_without_a_worker_keeps_the_temp_directory_it_had(
    repo_root: Path, tmp_path: Path
) -> None:
    """A sequential run is left alone.

    The isolation exists for parallel runs. A sequential run that found its
    temp directory moved out from under it would be a surprise, and every
    developer who runs the suite locally would get one.

    **The comparison is against the parent's own ``gettempdir()``, not
    against the ``TEMP`` variable.** The two are not the same thing:
    ``tempfile.gettempdir()`` skips a candidate directory that does not exist
    or cannot be written to, and falls through to the next one. So a process
    whose ``TEMP`` names a directory that was never created is *given* a
    different directory than the one its environment names — and comparing
    the two would report a difference that is not the isolation's doing.
    """
    before = tempfile.gettempdir()
    temp_dir = _temp_dir_for_worker(repo_root, tmp_path, None)
    assert temp_dir == before, (
        f"a run without a worker id must keep the ambient temp directory, "
        f"but it was given {temp_dir!r} instead of {before!r}"
    )
