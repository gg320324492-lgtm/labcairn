"""Shared builders and fixtures for the LC-P1-05 store tests.

Not a test module — it defines no ``test_*`` functions. The other store test
files import from it directly, which is how a fixture is shared without a
``tests/conftest.py``: the repository's own convention, per the root
``conftest.py``, is that a test needing more than the three shared fixtures
should build its own "locally and visibly", and a store whose tests each
rebuild a Task by hand in five slightly different ways tests nothing useful.

Everything here is deterministic. Time comes from the ``frozen_now`` fixture
rather than the wall clock, and ids come from :func:`labcairn.core.ids.new_id`
(which is monotonic, not random, within a millisecond) rather than ``uuid4``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from labcairn.core.ids import (
    ApprovalId,
    CheckpointId,
    OperationId,
    RunId,
    SourceId,
    StageId,
    TaskId,
    new_id,
)
from labcairn.db.migrations import upgrade_to_head
from labcairn.db.repository import Clock, TaskStore
from labcairn.db.session import create_db_engine, create_session_factory
from labcairn.material import ingest_bytes
from labcairn.reports.receipt import (
    ArtifactKind,
    ArtifactProducerKind,
    ArtifactReceipt,
    ArtifactStaleness,
)
from labcairn.runtime.lifecycle import Run, RunStatus, Stage, StageStatus, Task, TaskGoal
from labcairn.runtime.operation import (
    Approval,
    ApprovalState,
    Checkpoint,
    Operation,
    OperationState,
    compute_args_digest,
)

#: A fixed 64-hex content hash. Real-looking but constant, so a test that
#: asserts a hash round-trips is not asserting against a value it generated
#: with the same call it is testing.
STABLE_HASH = hashlib.sha256(b"labcairn-store-test").hexdigest()


def other_hash(seed: str) -> str:
    """A second stable hash, for tests that need two distinct ones."""
    return hashlib.sha256(seed.encode()).hexdigest()


# --------------------------------------------------------------------------- #
# contract builders
# --------------------------------------------------------------------------- #


def make_task(*, title: str = "Test task", now: datetime | None = None) -> Task:
    """A valid Task. ``now`` keeps timestamps deterministic under the frozen clock."""
    stamp = now or datetime(2026, 1, 1, tzinfo=UTC)
    return Task(
        task_id=TaskId(new_id()),
        title=title,
        goal=TaskGoal(
            objective="Establish whether the observation holds.",
            success_criterion="A cited answer, or an honest 'not established'.",
        ),
        created_at=stamp,
        updated_at=stamp,
    )


def make_run(task_id: TaskId, *, attempt: int = 1, now: datetime | None = None) -> Run:
    """A valid Run against *task_id*, already started."""
    return Run(
        run_id=RunId(new_id()),
        task_id=task_id,
        status=RunStatus.RUNNING,
        attempt=attempt,
        started_at=now or datetime(2026, 1, 1, tzinfo=UTC),
    )


def make_stage(
    task_id: TaskId,
    run_id: RunId,
    *,
    name: str = "intake",
    status: StageStatus = StageStatus.ENTERED,
) -> Stage:
    """A valid Stage. ``status`` defaults to entered so ``blocked_reason`` stays legal."""
    return Stage(
        stage_id=StageId(new_id()), task_id=task_id, run_id=run_id, name=name, status=status
    )


def make_operation(
    task_id: TaskId,
    run_id: RunId,
    stage_id: StageId,
    *,
    state: OperationState = OperationState.PLANNED,
    capability: str = "labcairn.sources.read",
    resource_key: str = "materials/input.txt",
    args: dict[str, object] | None = None,
) -> Operation:
    """A valid Operation with a digest computed the way the contract computes it."""
    payload: dict[str, object] = args if args is not None else {"encoding": "utf-8"}
    depends_on = (STABLE_HASH,)
    return Operation(
        operation_id=OperationId(new_id()),
        task_id=task_id,
        run_id=run_id,
        stage_id=stage_id,
        state=state,
        capability=capability,
        resource_key=resource_key,
        depends_on=depends_on,
        args_digest=compute_args_digest(
            task_id=task_id,
            capability=capability,
            resource_key=resource_key,
            args=payload,
            depends_on=depends_on,
        ),
    )


def make_approval(
    task_id: TaskId, operation_id: OperationId, *, now: datetime | None = None
) -> Approval:
    """A pending Approval expiring well after the frozen clock.

    The expiry is a parameter of construction, not of validation: the frozen
    contract deliberately refuses to reach for a wall clock, so a test that
    wanted an already-expired approval has to say so rather than wait.
    """
    stamp = now or datetime(2026, 1, 1, tzinfo=UTC)
    return Approval(
        approval_id=ApprovalId(new_id()),
        task_id=task_id,
        operation_id=operation_id,
        capability="labcairn.sources.write",
        resource_key="outputs/derived.csv",
        args_digest=STABLE_HASH,
        state=ApprovalState.PENDING,
        expires_at=stamp + timedelta(days=7),
    )


def make_checkpoint(
    task_id: TaskId,
    run_id: RunId,
    stage_id: StageId,
    *,
    through_seq: int = 1,
    now: datetime | None = None,
) -> Checkpoint:
    """A valid Checkpoint. ``through_seq`` names a per-Task ``seq``, not a rowid."""
    return Checkpoint(
        checkpoint_id=CheckpointId(new_id()),
        task_id=task_id,
        run_id=run_id,
        stage_id=stage_id,
        through_seq=through_seq,
        material_hashes=(STABLE_HASH,),
        created_at=now or datetime(2026, 1, 1, tzinfo=UTC),
    )


def make_receipt(task_id: TaskId, *, relative_path: str = "outputs/report.md") -> ArtifactReceipt:
    """A valid ArtifactReceipt, matching the frozen reports contract."""
    return ArtifactReceipt(
        receipt_id=f"artifact-{new_id()}",
        task_id=str(task_id),
        kind=ArtifactKind.REPORT,
        relative_path=relative_path,
        content_sha256=STABLE_HASH,
        size_bytes=1234,
        produced_by=ArtifactProducerKind.STAGE,
        producer_id="draft",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        staleness=ArtifactStaleness.CURRENT,
    )


def make_source_id(relative_path: str = "materials/one.csv") -> SourceId:
    """A source id of the shape the ingestion path mints.

    Minted through the public ingestion path rather than assembled by hand, so
    that the id a test binds is the id a real ingestion would have produced. A
    change to the id's form then shows up here, instead of quietly
    invalidating every test that binds a source.
    """
    material = ingest_bytes(
        b"a,b\n1,2\n",
        relative_path=relative_path,
        display_name=relative_path.rsplit("/", 1)[-1],
        ingested_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    return SourceId(material.source.source_id)


# --------------------------------------------------------------------------- #
# environment
# --------------------------------------------------------------------------- #


@dataclass
class StoreEnv:
    """A migrated database and everything bound to it.

    Holds one session by default, because that is how the product uses it: a
    process opens a session and drives the store through it. Tests that need a
    genuinely separate connection — restart, concurrency — ask for
    :meth:`new_session` instead of discovering the difference by accident.
    """

    db_path: Path
    engine: Engine
    factory: sessionmaker[Session]
    session: Session

    def store(self, *, clock: Clock | None = None) -> TaskStore:
        """A TaskStore over this environment's session."""
        return TaskStore(self.session) if clock is None else TaskStore(self.session, clock=clock)

    def new_session(self) -> Session:
        """A second, independent connection to the same database."""
        return self.factory()

    def dispose(self) -> None:
        """Close the engine, simulating a process restart."""
        self.engine.dispose()


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """A path for a database that does not exist yet.

    Migrating to a path rather than to ``:memory:`` is deliberate. An in-memory
    database has no second connection to reopen, so it cannot express "restart"
    or "two writers", and both are acceptance criteria here.
    """
    return tmp_path / "labcairn.db"


@pytest.fixture
def migrated_db(tmp_path: Path) -> Path:
    """A database migrated to head, at :func:`db_path`'s location.

    Takes ``tmp_path`` rather than :func:`db_path` on purpose. Fixtures imported
    into another module do not carry their own dependencies with them, so a
    fixture that builds on another fixture defined here would resolve in this
    module and then fail in the module that imported it. Every fixture below
    therefore depends on ``tmp_path`` alone and does its own migrating.
    """
    path = db_path_for(tmp_path)
    upgrade_to_head(path)
    return path


@pytest.fixture
def env(tmp_path: Path) -> Iterator[StoreEnv]:
    """A migrated database, an engine on it, and a session factory.

    The engine is disposed at teardown so a Windows test run does not fail to
    remove ``tmp_path`` because a connection is still open on the file.
    """
    path = db_path_for(tmp_path)
    upgrade_to_head(path)
    engine = create_db_engine(path)
    factory = create_session_factory(engine)
    session = factory()
    try:
        yield StoreEnv(db_path=path, engine=engine, factory=factory, session=session)
    finally:
        session.close()
        engine.dispose()


def db_path_for(tmp_path: Path) -> Path:
    """The one database path all the store fixtures share for a test."""
    return tmp_path / "labcairn.db"


@pytest.fixture
def frozen_clock(frozen_now: datetime) -> Clock:
    """A clock that returns the frozen time, matching the repository rule that
    no test reads a wall clock."""
    return lambda: frozen_now
