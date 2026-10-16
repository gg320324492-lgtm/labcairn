"""Bridging the Skill's stage names to the runtime's stage ids.

LC-P1-06 and LC-P1-07 were built by two agents that never read each other's
work, and they disagreed about what identifies a stage:

- ``skills`` names stages with :class:`~labcairn.skills.artifacts.StageName`, a
  closed enum, because the workflow's stage sequence is declared and fixed.
- ``runtime`` identifies them with ``StageId``, a UUID, because a stage row
  belongs to one Run and two Runs of the same Task must not collide.

Neither is wrong. A name is the right key for a declared workflow; a UUID is the
right key for a row. They are not the same question, and the store already holds
both — ``stages`` has a ``stage_id`` column and a ``name`` column.

This module is the one place that converts between them, and it converts by
**looking the name up in the database** rather than by inventing a derivation.
The alternative — hashing the name into a UUID, say — would produce an
identifier that no row carries and that changes meaning if the workflow is
renamed.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from labcairn.core.ids import RunId, StageId, TaskId
from labcairn.db.models import StageRow
from labcairn.runtime.operation import Checkpoint


class UnknownStageError(LookupError):
    """The workflow names a stage the store has no row for.

    Not a ``KeyError`` and not silently ``None``: a caller bridging a checkpoint
    is about to write a durable record, and "this stage was never created" is a
    bug in the caller's sequencing rather than a missing optional value.
    """


def stage_id_for(session: Session, run_id: RunId, stage_name: str) -> StageId:
    """The ``StageId`` the store holds for *stage_name* within *run_id*.

    Scoped to the Run, because a stage name repeats across Runs of the same Task
    and a name-only lookup would silently bridge two different attempts.
    """
    row = session.execute(
        select(StageRow).where(StageRow.run_id == str(run_id), StageRow.name == stage_name)
    ).scalar_one_or_none()
    if row is None:
        raise UnknownStageError(
            f"run {run_id} has no stage named {stage_name!r}; the workflow must "
            f"create its stages before a boundary can be recorded against them"
        )
    # `NewType` is nominal, so the parse is explicit: the column holds a
    # string and the type demands a UUID. Skipping this is the mistake the
    # type checker exists to catch, and it did.
    return StageId(uuid.UUID(row.stage_id))


def checkpoint_from_stage_boundary(
    session: Session,
    *,
    task_id: TaskId,
    run_id: RunId,
    stage_name: str,
    through_seq: int,
    material_hashes: tuple[str, ...] = (),
) -> Checkpoint:
    """Build the runtime ``Checkpoint`` for a Skill stage boundary.

    ``through_seq`` is supplied by the caller rather than derived here, and that
    is deliberate. It is the highest per-Task event sequence the boundary
    covers, and ADR-0003 C1 makes it the *only* ordering — so it must come from
    the same transaction that wrote the events being checkpointed. Deriving it
    here would read a sequence number that a concurrent writer may already have
    moved past, and the resulting checkpoint would claim to cover events it does
    not.

    This is why ``StageCheckpoint`` alone cannot drive resume: the Skill
    orchestrator knows *what happened* at a boundary but not *how far the log
    had got*, and only the store can say that.
    """
    return Checkpoint(
        task_id=task_id,
        run_id=run_id,
        stage_id=stage_id_for(session, run_id, stage_name),
        through_seq=through_seq,
        material_hashes=material_hashes,
    )
