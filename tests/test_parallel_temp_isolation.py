"""The parallel runs' temp isolation, watched.

**The property.** When the suite is run in parallel — which the CI workflow
does, with ``pytest-xdist`` — every worker gets a temporary directory of its
own, so two workers never write to the same file.

**Why it needs watching.** The product pins ``MPLCONFIGDIR`` to
``tempfile.gettempdir() / "labcairn-matplotlib"``: a path computed from the
*ambient* temp directory, not from the test's own ``tmp_path``. Matplotlib
writes its font cache there, and two processes building the cache at the same
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

**The ambient ``TMPDIR`` is part of what is watched.** ``tempfile`` consults
``TMPDIR`` *before* ``TEMP`` and ``TMP``, on every platform — the candidate
list is built from the environment first and only then from the operating
system's own locations. So an ambient ``TMPDIR`` defeats an isolation that
sets only the other two: every worker is handed the *same* directory, which
is the very race this file exists to prevent. A witness that waited for the
environment to happen to carry a ``TMPDIR`` would be *reactive* about that
condition and *assuming* about the mechanism, whose correctness must not
depend on the environment it happens to run in. So this one **constructs**
the condition: every probe is given a ``TMPDIR`` of its own, and the
isolation has to hold in spite of it.

Three things are watched here, and the last is the one that matters:

* a worker gets a directory **named after it**,
* two different workers get **different** directories, and
* an ambient ``TMPDIR`` does **not** become the worker's directory.

The second is the property the font cache depends on. The first is only how
it is arranged. The third is the one that was missing.
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

#: The name of the directory the probes' ``TMPDIR`` points at, inside the
#: probe's own root. No worker owns it, and it is not named after a worker.
_AMBIENT_DIR_NAME = "ambient-tmpdir"


def _ambient_tmpdir(probe_root: Path) -> Path:
    """A directory for the probes' ``TMPDIR`` to point at, that exists.

    **It has to exist.** ``tempfile.gettempdir()`` tries its candidates in
    order and *skips* any that is not a writable directory, so a ``TMPDIR``
    naming a path that is not there falls through to ``TEMP`` — and a
    mechanism that never set ``TMPDIR`` at all would still look correct.
    Creating the directory is what gives the witness the power to fail.
    """
    ambient = probe_root / _AMBIENT_DIR_NAME
    ambient.mkdir(parents=True, exist_ok=True)
    return ambient


def _temp_dir_for_worker(
    repo_root: Path, probe_root: Path, worker: str | None, ambient: Path
) -> str:
    """The temp directory a process would use, with ``worker`` set or not.

    Run in a subprocess, because the answer depends on module-import order:
    the isolation has to be applied *before* anything reads
    ``tempfile.gettempdir()``, and in this process that has already happened.

    **The probe is always given a ``TMPDIR``** — the one at ``ambient`` — so
    that the condition the isolation has to survive is constructed rather
    than waited for. What the ambient value is, is the caller's decision:
    a worker probe needs a directory no worker owns, and a sequential probe
    needs the ambient one this process is using.
    """
    env = dict(os.environ)
    if worker is None:
        env.pop("PYTEST_XDIST_WORKER", None)
    else:
        env["PYTEST_XDIST_WORKER"] = worker
    env["TMPDIR"] = str(ambient)
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
    ambient = _ambient_tmpdir(tmp_path)
    temp_dir = _temp_dir_for_worker(repo_root, tmp_path, "gw0", ambient)
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
    ambient = _ambient_tmpdir(tmp_path)
    first = _temp_dir_for_worker(repo_root, tmp_path, "gw0", ambient)
    second = _temp_dir_for_worker(repo_root, tmp_path, "gw1", ambient)
    assert first != second, (
        f"two workers were given the same temp directory ({first!r}); "
        "they would share matplotlib's font cache and race to write it"
    )


def test_an_ambient_tmpdir_does_not_become_the_workers_directory(
    repo_root: Path, tmp_path: Path
) -> None:
    """The hole this file was missing: ``TMPDIR`` is consulted first.

    ``tempfile.gettempdir()`` builds its candidate list from the environment
    before the operating system's own locations, and ``TMPDIR`` comes first
    in that list. So an isolation that sets ``TEMP`` and ``TMP`` but leaves
    ``TMPDIR`` alone is defeated by the ambient environment: the worker is
    handed the ambient directory, every worker is handed the *same* one, and
    the font cache this whole mechanism exists to keep apart is shared by
    them all.

    The probe below is given a ``TMPDIR`` of its own — a directory that
    exists, so that ``tempfile`` really accepts it as a candidate and a
    mechanism that ignored it would really lose. The worker's directory has
    to be the one the isolation computed instead.
    """
    ambient = _ambient_tmpdir(tmp_path)
    temp_dir = _temp_dir_for_worker(repo_root, tmp_path, "gw0", ambient)
    assert Path(temp_dir) != ambient, (
        f"the worker was given the ambient TMPDIR ({temp_dir!r}); every worker "
        "would share it and race to write matplotlib's font cache"
    )
    assert Path(temp_dir).parent == tmp_path, (
        f"the worker's directory must be the one the isolation computed under "
        f"its own root, but it was given {temp_dir!r}"
    )


def test_a_run_without_a_worker_keeps_the_temp_directory_it_had(
    repo_root: Path, tmp_path: Path
) -> None:
    """A sequential run is left alone.

    The isolation exists for parallel runs. A sequential run that found its
    temp directory moved out from under it would be a surprise, and every
    developer who runs the suite locally would get one.

    **The comparison is against a directory the probe is given, not against
    the ``TEMP`` variable.** The two are not the same thing:
    ``tempfile.gettempdir()`` skips a candidate directory that does not exist
    or cannot be written to, and falls through to the next one. So a process
    whose ``TEMP`` names a directory that was never created is *given* a
    different directory than the one its environment names — and comparing
    the two would report a difference that is not the isolation's doing.

    The probe's ``TMPDIR`` is set to the ambient temp directory this process
    is using, so the two agree on what "the temp directory it had" means and
    the comparison is about the isolation having left it alone.
    """
    before = tempfile.gettempdir()
    temp_dir = _temp_dir_for_worker(repo_root, tmp_path, None, Path(before))
    assert temp_dir == before, (
        f"a run without a worker id must keep the ambient temp directory, "
        f"but it was given {temp_dir!r} instead of {before!r}"
    )
