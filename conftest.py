"""Shared pytest fixtures for LabCairn.

This is the **repository root** ``conftest.py``, owned by T02 of LC-P1-01. It holds
the three fixtures every other test is expected to build on, and nothing else:

* repository-root discovery,
* an isolated temporary workspace,
* a frozen clock.

Deliberately small. A fixture that grows a second responsibility is a fixture that
later tests cannot reason about; and the project principle is that a test which
needs more than these should build its own, locally and visibly.

Determinism rule (docs/plans/LC-P1-01-task-breakdown.md §5.2): no wall clock, no
RNG, no ``uuid4``. Tests that need a time read :data:`FROZEN_NOW` through the
``frozen_now`` fixture. ``ruff``'s ``DTZ`` rules are on, so a naive
``datetime.now()`` fails the lint gate rather than the byte-identity assertion.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

#: The single wall-clock value tests are allowed to observe.
#: Chosen as a round UTC instant so a rendered timestamp is recognisable at a glance.
FROZEN_NOW: datetime = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)


def give_this_worker_its_own_temp() -> None:
    """Point this process's temporary directory at a directory of its own.

    **Why this is here.** The product pins ``MPLCONFIGDIR`` to
    ``tempfile.gettempdir() / "labcairn-matplotlib"`` — a path derived from the
    *ambient* temp directory, not from the test's own ``tmp_path``. Matplotlib
    writes its font cache there, and two processes building that cache at the
    same moment can read a half-written one.

    That is not a hypothetical: it is the shape of F38, where two runs sharing
    one temp directory fight over the same file. ``pytest-xdist`` gives every
    worker its own ``tmp_path`` automatically, but it cannot fix a path the
    product computes from the environment — so this does.

    **It must run before the product is imported**, because the product reads
    ``tempfile.gettempdir()`` at import time and ``tempfile`` caches the answer
    in a module global. This module is imported by pytest before any test
    module, which is early enough; the cache is cleared so the answer is
    computed again from the environment this has just set.

    A run without ``pytest-xdist`` has no worker id, and this does nothing:
    one process keeps the ambient temp directory it already had.

    **It is watched by a test of its own**
    (``tests/test_parallel_temp_isolation.py``): a mechanism that nobody
    watches can be removed, and then two workers would share a font cache
    again — and the failure would be a rare, timing-dependent one, which is
    the hardest kind to notice and the easiest to misread.
    """
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if worker is None:
        return
    root = Path(os.environ.get("LABCAIRN_TEMP_ROOT", tempfile.gettempdir()))
    own = root / f"labcairn-worker-{worker}"
    own.mkdir(parents=True, exist_ok=True)
    for name in ("TEMP", "TMP"):
        os.environ[name] = str(own)
    # `tempfile` caches the directory it chose; clearing the cache makes the
    # next reader recompute it from the environment set above.
    tempfile.tempdir = None


give_this_worker_its_own_temp()


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute path of the LabCairn repository root.

    Derived from this file's location, not from the working directory, so a test
    run from a subdirectory still finds the right root. Asserts ``pyproject.toml``
    is there: a wrong root fails loudly here instead of producing a confusing
    "no such file" three tests later.
    """
    root = Path(__file__).resolve().parent
    if not (root / "pyproject.toml").is_file():
        msg = f"expected a pyproject.toml at the repository root, found none in {root}"
        raise RuntimeError(msg)
    return root


@pytest.fixture
def frozen_now() -> datetime:
    """The injected clock. UTC, microsecond-exact, constant."""
    return FROZEN_NOW


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Iterator[Path]:
    """An isolated, empty directory for one test to write into.

    Named ``workspace`` rather than reusing ``tmp_path`` directly so tests read as
    *what the directory is for*, and so the future read-only-source /
    task-controlled-output split (docs/ARCHITECTURE.md "Privacy and security
    invariants") can be added here without rewriting every call site.
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    yield workspace
