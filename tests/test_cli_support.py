"""The rig every ``test_cli_*`` split file runs on.

This is ``tests/test_cli.py``'s shared rig — the runner, the workspace
fixtures, the fixed constants — moved out of the monolith so the suite can
be sharded per section. The property the rig carries is unchanged: **the
CLI is tested by running it** — a real process, the console script a
developer types, the exit code and the two streams.

The monolith's own docstring states the properties each section witnesses;
this module carries only the means.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from labcairn.application import (
    ApplicationContext,
)
from labcairn.cli.workspace import (
    application_context,
    locate,
    read_config,
)
from labcairn.core.ids import TaskId
from labcairn.db import create_db_engine, create_session_factory, session_scope
from labcairn.db.materials import put_source
from labcairn.reports.receipt import (
    ArtifactKind,
    ArtifactProducerKind,
    ArtifactReceipt,
)
from labcairn.sources.source import Source, SourceKind, SourceReadability

pytestmark = pytest.mark.e2e

#: A fixed content hash. Constant so a test that asserts a hash round-trips
#: is not asserting against a value it generated with the call it is testing.
_HASH = "b" * 64

#: A second fixed hash, so two receipts are distinguishable.
_OTHER_HASH = "c" * 64

#: A fixed instant. The ledger's rows carry one, and a wall clock would make
#: the ordering assertions depend on when the test ran.
_MOMENT = datetime(2026, 1, 1, tzinfo=UTC)

#: The source id the product's own ingestion mints: location-derived, and
#: **not** a UUIDv7. See ``test_the_task_cannot_bind_a_material_the_product_ingests``.
_SOURCE_ID = "src-0123456789abcdef"


# --------------------------------------------------------------------------- #
# running the CLI
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class CliResult:
    """What one run of the CLI produced."""

    returncode: int
    stdout: str
    stderr: str

    def json(self) -> Any:
        """The machine-readable form, parsed."""
        return json.loads(self.stdout)


def _console_script() -> Path:
    """The script a developer types, as this interpreter would find it.

    Beside the running interpreter rather than on ``PATH``: the test must
    exercise the script the project installs, and ``PATH`` is the machine's
    business.
    """
    name = "labcairn.exe" if os.name == "nt" else "labcairn"
    return Path(sys.executable).parent / name


def run_cli(*args: str, cwd: Path | None = None, encoding: str = "utf-8") -> CliResult:
    """Run the console script and return what it produced.

    ``PYTHONIOENCODING`` is set because the child's output encoding is
    otherwise the machine's locale encoding, and a path with a non-ASCII
    character in it would make the test fail for a reason that has nothing
    to do with the CLI.

    ``COLUMNS`` is set for the same kind of reason. Rich asks the terminal
    how wide it is, and a pipe is not a terminal, so without this the
    rendered output would be laid out for eighty columns and a long path
    would be wrapped in the middle. The width of a terminal is a property of
    the terminal, and a test that asserted on a wrapped path would be
    asserting on the machine rather than on the CLI.
    """
    script = _console_script()
    if not script.is_file():
        pytest.fail(
            f"the console script is not installed at {script}. The CLI is tested "
            "through the script a developer types, so it has to be there; run "
            "`uv sync`."
        )
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = encoding
    environment["COLUMNS"] = "200"
    completed = subprocess.run(
        [str(script), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(cwd) if cwd is not None else None,
        env=environment,
        timeout=300,
    )
    return CliResult(completed.returncode, completed.stdout, completed.stderr)


# --------------------------------------------------------------------------- #
# the environment
# --------------------------------------------------------------------------- #


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A workspace the CLI itself made."""
    root = tmp_path / "workspace"
    result = run_cli("--workspace", str(root), "init")
    assert result.returncode == 0, f"init failed: {result.stderr}"
    return root


@pytest.fixture
def task_id(workspace: Path) -> str:
    """A task the CLI itself made, and the workspace's current task."""
    result = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "create",
        "--title",
        "Read the literature",
        "--objective",
        "Establish what the corpus says about the question.",
        "--criterion",
        "A cited answer, or an honest 'not established'.",
        "--json",
    )
    assert result.returncode == 0, f"task create failed: {result.stderr}"
    return str(result.json()["task_id"])


@pytest.fixture
def material(workspace: Path) -> Path:
    """A file of supplied material, in the workspace's source root."""
    path = workspace / "materials" / "one.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")
    return path


@pytest.fixture
def source_id(workspace: Path, material: Path) -> str:
    """A material in the ledger, as the product's own ingestion leaves it.

    Written here rather than through the CLI because the application layer
    has no ingestion operation, so no surface can put a source in the ledger.
    The CLI's job is to *inspect* what is there.
    """
    engine = create_db_engine(workspace / "labcairn.db")
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            put_source(
                session,
                Source(
                    source_id=_SOURCE_ID,
                    kind=SourceKind.CSV,
                    display_name="one.csv",
                    relative_path="materials/one.csv",
                    content_sha256=_HASH,
                    size_bytes=12,
                    readability=SourceReadability.READABLE,
                    ingested_at=_MOMENT,
                ),
            )
    finally:
        engine.dispose()
    return _SOURCE_ID


@contextmanager
def _context(workspace: Path, task_id: str) -> Iterator[ApplicationContext]:
    """The layer's context, in this process, for the same workspace.

    Built the way the CLI builds it — the same configuration, the same
    policy — so that comparing the CLI's JSON with the layer's model is a
    comparison of two reads of the same store and not of two configurations.
    """
    location = locate(workspace)
    config = read_config(location)
    with application_context(location, config, TaskId(uuid.UUID(task_id))) as context:
        yield context


@pytest.fixture
def artifacts(workspace: Path, task_id: str) -> tuple[ArtifactReceipt, ...]:
    """Two artefacts in the store, in the order the store keeps them.

    Written here rather than through the CLI because the layer has no
    operation that records one: an artefact is recorded by the stage that
    produced it, and the CLI's stage produces none.

    Two, and not one, because a single-element list cannot show an ordering.
    """
    receipts = (
        ArtifactReceipt(
            receipt_id="artifact-first",
            task_id=task_id,
            kind=ArtifactKind.REPORT,
            relative_path=f"output/{task_id}/report.md",
            content_sha256=_HASH,
            size_bytes=10,
            produced_by=ArtifactProducerKind.STAGE,
            producer_id="draft",
            created_at=_MOMENT,
            revision=1,
        ),
        ArtifactReceipt(
            receipt_id="artifact-second",
            task_id=task_id,
            kind=ArtifactKind.REPORT,
            relative_path=f"output/{task_id}/report-revised.md",
            content_sha256=_OTHER_HASH,
            size_bytes=20,
            produced_by=ArtifactProducerKind.STAGE,
            producer_id="draft",
            created_at=_MOMENT,
            revision=2,
        ),
    )
    with _context(workspace, task_id) as context, context.store.unit(context.task_id) as work:
        for receipt in receipts:
            work.put_artifact(receipt)
    return receipts
