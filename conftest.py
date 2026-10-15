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

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

#: The single wall-clock value tests are allowed to observe.
#: Chosen as a round UTC instant so a rendered timestamp is recognisable at a glance.
FROZEN_NOW: datetime = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)


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
