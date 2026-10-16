"""Reading the frozen store's rows back as contracts, and nothing else.

:mod:`labcairn.db` owns the schema and LC-P1-05 froze it, so this module only
*reads*. Every helper here is a projection in one direction —
``row → contract`` — because the write direction already exists and is the
right one: ``UnitOfWork.put_*`` takes a contract, and there is deliberately no
"update this column" escape hatch on it. Writing therefore goes through a
contract that has been validated, which is the property worth keeping.

Two conversions deserve their reason stated:

* :func:`row_to_receipt` rebuilds an :class:`ArtifactReceipt` from an
  :class:`ArtifactRow` so that marking an artifact stale goes through the
  frozen model's own validator. That validator is what requires
  ``staleness_reason`` to be present whenever ``staleness`` is ``STALE``, and
  going around it would produce rows the contract cannot load back.

* :func:`row_to_operation` re-derives nothing. ``args_digest`` is read as
  stored, not recomputed, because recomputing it here would need the original
  arguments and the fact that we no longer have them is precisely why the
  digest was stored.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from labcairn.core.ids import ApprovalId, CheckpointId, OperationId, RunId, StageId, TaskId
from labcairn.db.models import (
    ApprovalRow,
    ArtifactRow,
    CheckpointRow,
    OperationRow,
    RunRow,
    StageRow,
)
from labcairn.recovery.contracts import UnknownOperationError, UnknownStageError
from labcairn.reports.receipt import (
    ArtifactKind,
    ArtifactProducerKind,
    ArtifactReceipt,
    ArtifactStaleness,
    DerivationRef,
)
from labcairn.runtime.lifecycle import Run, RunStatus, Stage, StageStatus
from labcairn.runtime.operation import (
    Approval,
    ApprovalState,
    Checkpoint,
    Operation,
    OperationState,
)


def load_operation(session: Session, operation_id: OperationId) -> Operation:
    """One Operation by its domain id."""
    row = session.execute(
        select(OperationRow).where(OperationRow.operation_id == str(operation_id))
    ).scalar_one_or_none()
    if row is None:
        raise UnknownOperationError(f"no operation {operation_id}")
    return row_to_operation(row)


def find_operations_in_state(
    session: Session, task_id: TaskId, state: OperationState
) -> tuple[Operation, ...]:
    """Every operation of *task_id* currently in *state*, ordered by id.

    Ordered by ``operation_id`` rather than by rowid or timestamp: the id is
    generated monotonically (UUIDv7), so this is the one ordering here that is
    a property of the data rather than of how SQLite happens to lay out a table.
    """
    rows = session.execute(
        select(OperationRow)
        .where(
            OperationRow.task_id == str(task_id),
            OperationRow.state == state.value,
        )
        .order_by(OperationRow.operation_id.asc())
    ).scalars()
    return tuple(row_to_operation(row) for row in rows)


def load_stage(session: Session, stage_id: StageId) -> Stage:
    """One Stage by its domain id."""
    row = session.execute(
        select(StageRow).where(StageRow.stage_id == str(stage_id))
    ).scalar_one_or_none()
    if row is None:
        raise UnknownStageError(f"no stage {stage_id}")
    return row_to_stage(row)


def find_stage(session: Session, stage_id: StageId) -> Stage | None:
    """As :func:`load_stage`, but ``None`` rather than raising."""
    row = session.execute(
        select(StageRow).where(StageRow.stage_id == str(stage_id))
    ).scalar_one_or_none()
    return None if row is None else row_to_stage(row)


def load_run(session: Session, run_id: str | RunId) -> Run | None:
    """One Run by its domain id."""
    row = session.execute(select(RunRow).where(RunRow.run_id == str(run_id))).scalar_one_or_none()
    if row is None:
        return None
    return Run(
        run_id=RunId(UUID(row.run_id)),
        task_id=TaskId(UUID(row.task_id)),
        status=RunStatus(row.status),
        attempt=row.attempt,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


def list_checkpoints(session: Session, task_id: TaskId) -> tuple[Checkpoint, ...]:
    """A task's checkpoints, oldest ``through_seq`` first.

    ``through_seq`` is per-Task and gapless (ADR-0003 C1), so it is a total
    order over checkpoints that needs no tiebreak and no wall clock.
    """
    rows = session.execute(
        select(CheckpointRow)
        .where(CheckpointRow.task_id == str(task_id))
        .order_by(CheckpointRow.through_seq.asc())
    ).scalars()
    return tuple(
        Checkpoint(
            checkpoint_id=CheckpointId(UUID(row.checkpoint_id)),
            task_id=TaskId(UUID(row.task_id)),
            run_id=RunId(UUID(row.run_id)),
            stage_id=StageId(UUID(row.stage_id)),
            through_seq=row.through_seq,
            material_hashes=tuple(row.material_hashes),
            created_at=row.created_at,
        )
        for row in rows
    )


def load_approval(session: Session, approval_id: ApprovalId) -> Approval | None:
    """One Approval by its domain id."""
    row = session.execute(
        select(ApprovalRow).where(ApprovalRow.approval_id == str(approval_id))
    ).scalar_one_or_none()
    if row is None:
        return None
    return Approval(
        approval_id=ApprovalId(UUID(row.approval_id)),
        task_id=TaskId(UUID(row.task_id)),
        operation_id=OperationId(UUID(row.operation_id)),
        capability=row.capability,
        resource_key=row.resource_key,
        args_digest=row.args_digest,
        state=ApprovalState(row.state),
        expires_at=row.expires_at,
        granted_at=row.granted_at,
        consumed_at=row.consumed_at,
    )


def load_artifacts(session: Session, task_id: TaskId) -> tuple[ArtifactReceipt, ...]:
    """A task's artifact receipts, oldest first.

    Ordered by ``(revision, artifact_id)``. Artifact ids are opaque strings
    rather than UUIDv7s, so they do not order by creation, and revision is the
    only field that carries the project's own notion of sequence.
    """
    rows = session.execute(
        select(ArtifactRow)
        .where(ArtifactRow.task_id == str(task_id))
        .order_by(ArtifactRow.revision.asc(), ArtifactRow.artifact_id.asc())
    ).scalars()
    return tuple(row_to_receipt(row) for row in rows)


# --------------------------------------------------------------------------- #
# row -> contract
# --------------------------------------------------------------------------- #


def row_to_operation(row: OperationRow) -> Operation:
    return Operation(
        operation_id=OperationId(UUID(row.operation_id)),
        task_id=TaskId(UUID(row.task_id)),
        run_id=RunId(UUID(row.run_id)),
        stage_id=StageId(UUID(row.stage_id)),
        state=OperationState(row.state),
        capability=row.capability,
        resource_key=row.resource_key,
        depends_on=tuple(row.depends_on),
        args_digest=row.args_digest,
    )


def row_to_stage(row: StageRow) -> Stage:
    return Stage(
        stage_id=StageId(UUID(row.stage_id)),
        task_id=TaskId(UUID(row.task_id)),
        run_id=RunId(UUID(row.run_id)),
        name=row.name,
        status=StageStatus(row.status),
        input_hashes=tuple(row.input_hashes),
        output_hashes=tuple(row.output_hashes),
        blocked_reason=row.blocked_reason,
    )


def row_to_receipt(row: ArtifactRow) -> ArtifactReceipt:
    """Rebuild the frozen receipt contract from its row.

    ``derived_from`` is stored as already-dumped JSON, so it round-trips through
    :class:`DerivationRef` validation here. A row this build cannot read raises,
    which is the intended behaviour: the store is the authority and a receipt
    it cannot load is a receipt nobody may claim to have produced.
    """
    return ArtifactReceipt(
        receipt_id=row.artifact_id,
        task_id=row.task_id,
        kind=ArtifactKind(row.kind),
        relative_path=row.relative_path,
        content_sha256=row.content_sha256,
        size_bytes=row.size_bytes,
        revision=row.revision,
        produced_by=ArtifactProducerKind(row.produced_by),
        producer_id=row.producer_id,
        derived_from=tuple(DerivationRef.model_validate(ref) for ref in row.derived_from),
        staleness=ArtifactStaleness(row.staleness),
        staleness_reason=row.staleness_reason,
        media_type=row.media_type,
        created_at=row.created_at,
    )


__all__ = [
    "find_operations_in_state",
    "find_stage",
    "list_checkpoints",
    "load_approval",
    "load_artifacts",
    "load_operation",
    "load_run",
    "load_stage",
    "row_to_operation",
    "row_to_receipt",
    "row_to_stage",
]
