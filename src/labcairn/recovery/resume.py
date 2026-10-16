"""Checkpoints, resume, scoped pause/stop, and what a changed source invalidates.

The rule this module exists to enforce is the one in
:class:`~labcairn.runtime.lifecycle.Stage`: *"Changed input invalidates
downstream" is enforced by comparing hashes, not by timestamps, because a file
can change without its mtime moving.*

So every comparison here is content-hash to content-hash. The store deals in
hashes and nothing else — ``Stage.input_hashes``, ``Stage.output_hashes``,
``Checkpoint.material_hashes`` are all digests, never paths — so a caller that
wants a verification answer supplies a **measurement**: which resource keys
exist now, and what each hashes to. The checkpoint holds what was true then;
the measurement holds what is true now; the comparison is the question.

That division is what keeps a path out of the durable record. A path moves and
a digest does not, and binding to a path is how a Task silently ends up
describing a different file than it started with.

Unverifiable means changed
-------------------------
A recorded hash that appears against **no** current resource key fails the
check. A file that has been deleted, renamed or made unreadable is not evidence
that the old content is still there, and a resume that treated "cannot check"
as "fine" would skip work whose inputs had vanished. Failing closed here is the
whole reason the comparison is over hashes rather than over presence.

Scoping pause and stop
----------------------
"Scoped" means by run, and optionally by stage, and it means the scope is part
of the event rather than a convention. A ``run_paused`` event carrying a
``stage_id`` says "this stage is parked"; one without says "the whole run is".
Collapsing the two would make "resume" ambiguous — there is no way to know what
was parked — and the ambiguity surfaces as a stage that silently restarts.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from labcairn.core.ids import CheckpointId, RunId, StageId, TaskId, new_id
from labcairn.db.models import ArtifactRow, StageRow
from labcairn.db.repository import Clock, TaskStore, last_seq, utc_now
from labcairn.recovery.persistence import (
    find_stage,
    list_checkpoints,
    load_artifacts,
    load_run,
    row_to_receipt,
    row_to_stage,
)
from labcairn.reports.receipt import ArtifactReceipt, ArtifactStaleness
from labcairn.runtime.event import EventTransition, EventType
from labcairn.runtime.lifecycle import Run, RunStatus, Stage
from labcairn.runtime.operation import Checkpoint
from labcairn.security.approval import content_hash

#: The reason recorded on every artifact invalidated by a source change. Fixed
#: text rather than an interpolated one so that "why is this stale?" is
#: greppable in a user's export rather than a sentence to be re-parsed.
STALE_REASON: Final = (
    "stale: a source material changed after this artifact was produced. The "
    "derivation chain no longer matches the bytes on disk; regenerate before "
    "relying on it."
)

#: A measurement of the workspace: resource key -> the hash it has right now.
type MaterialSnapshot = Mapping[str, str]


@dataclass(frozen=True, slots=True)
class InvalidationReport:
    """Everything one source-change pass touched.

    Returned rather than merely logged so that a caller which wants to warn a
    human has names to warn about. Three separate counts because they answer
    three different questions: which outputs are now suspect, which stages must
    re-run, and which material moved.
    """

    changed_hashes: tuple[str, ...]
    stale_artifact_ids: tuple[str, ...]
    invalidated_stages: tuple[StageId, ...]


@dataclass(frozen=True, slots=True)
class ResumePlan:
    """Where a Task should pick up, and why.

    ``from_stage`` is ``None`` when the newest checkpoint still verifies and
    nothing follows it — there is nothing to redo, and a resume that "resumes"
    anyway would re-run work whose inputs have not moved.

    ``stopped_reason`` is populated whenever a checkpoint failed verification,
    and names the material that moved, so a user asking "why is it doing that
    again?" gets an answer pointing at a file rather than at a status code.
    """

    task_id: TaskId
    #: The stage to redo, or ``None`` to start fresh after the last verified stage.
    from_stage: StageId | None
    through_seq: int
    stopped_reason: str | None
    #: The attempt number a new Run against this Task should carry.
    next_attempt: int

    @property
    def must_redo(self) -> bool:
        """Whether anything at all needs re-running."""
        return self.stopped_reason is not None


class MaterialResolver:
    """Measure a workspace: which resource keys exist, and what each hashes to.

    The measurement is taken by the caller and handed in, rather than being
    re-read later, so that "what did the disk look like at the moment I asked"
    is a fact rather than a re-derivation. A key whose file is missing or
    unreadable is simply **absent** from the snapshot, which the comparison
    treats as changed.
    """

    __slots__ = ("_root",)

    def __init__(self, root: Path) -> None:
        self._root = root

    def snapshot(self, resource_keys: Iterable[str]) -> dict[str, str]:
        """Re-hash each key that currently resolves to a readable file.

        Absent keys are omitted rather than mapped to a sentinel. An omitted
        key and a key hashing to something unexpected are both "changed", and
        keeping the snapshot a plain ``dict[str, str]`` means a caller cannot
        invent a value that reads as current.
        """
        measured: dict[str, str] = {}
        for key in resource_keys:
            try:
                measured[key] = content_hash(self._root.joinpath(*key.split("/")))
            except OSError:
                continue
        return measured


class ResumeCoordinator:
    """Checkpoints, resume, run control and source invalidation."""

    __slots__ = ("_clock", "_session", "_store", "_workspace")

    def __init__(
        self,
        store: TaskStore,
        session: Session,
        *,
        workspace_root: Path,
        clock: Clock | None = None,
    ) -> None:
        self._store = store
        self._session = session
        self._workspace = workspace_root
        self._clock: Clock = clock or utc_now

    # -- checkpoints ---------------------------------------------------------- #

    def record_checkpoint(
        self,
        task_id: TaskId,
        stage_id: StageId,
        *,
        material_hashes: Sequence[str] = (),
    ) -> Checkpoint:
        """Freeze a stage boundary.

        ``through_seq`` is the task's counter read **before** this checkpoint's
        own ``checkpoint_created`` event allocates one, so the recorded seq is
        the last event the checkpoint *includes* rather than the one announcing
        it. A checkpoint that included its own announcement would claim one more
        piece of history than actually happened, and a client resuming from it
        would skip the announcement.

        A ``seq`` of zero is refused rather than clamped. It would mean the task
        has no ``task_created`` event, which means this method was called
        against a Task that does not exist — and writing ``1`` would turn a
        caller bug into a plausible-looking checkpoint.
        """
        stage = find_stage(self._session, stage_id)
        if stage is None:
            raise ValueError(f"no stage {stage_id}")
        through = last_seq(self._session, task_id)
        if through < 1:
            raise ValueError(
                f"task {task_id} has no events yet, so no checkpoint can name a "
                f"'through_seq'; got {through}"
            )
        checkpoint = Checkpoint(
            checkpoint_id=CheckpointId(new_id()),
            task_id=task_id,
            run_id=stage.run_id,
            stage_id=stage_id,
            through_seq=through,
            material_hashes=tuple(material_hashes) or tuple(stage.output_hashes),
            created_at=self._clock(),
        )
        with self._store.unit(task_id) as work:
            # No transition: `checkpoint_created` is an annotation, not a change.
            # The frozen envelope refuses a transition on it, and it is right to
            # — a checkpoint records that a boundary *is*; it does not move
            # anything from one state to another.
            work.emit(
                EventType.CHECKPOINT_CREATED,
                run_id=stage.run_id,
                stage_id=stage_id,
            )
            work.put_checkpoint(checkpoint)
        return checkpoint

    def plan_resume(self, task_id: TaskId, *, now: MaterialSnapshot) -> ResumePlan:
        """Find the last verified stage boundary.

        Walks checkpoints **oldest first** and stops at the first whose material
        no longer matches the measurement. That direction is the whole point, and
        it was wrong in a first draft that walked newest-first: a later stage may
        have been produced from material that is still intact, so scanning from
        the top would find it, declare "nothing to redo", and silently keep an
        output that was derived from a source that has since moved. A checkpoint
        only verifies if every checkpoint at or before it does, because
        downstream was produced *from* upstream.

        The first failure is therefore the redo point, and every checkpoint
        after it is discarded as a resume target regardless of its own material.
        """
        checkpoints = list_checkpoints(self._session, task_id)
        attempt = self._next_attempt(task_id)

        if not checkpoints:
            return ResumePlan(
                task_id=task_id,
                from_stage=None,
                through_seq=0,
                stopped_reason="no checkpoint exists; nothing has been verified yet",
                next_attempt=attempt,
            )

        current = frozenset(now.values())
        verified: Checkpoint | None = None
        for checkpoint in checkpoints:
            missing = tuple(sorted(set(checkpoint.material_hashes) - current))
            if missing:
                return ResumePlan(
                    task_id=task_id,
                    from_stage=checkpoint.stage_id,
                    through_seq=verified.through_seq if verified is not None else 0,
                    stopped_reason=(
                        f"checkpoint {checkpoint.checkpoint_id} at stage "
                        f"{checkpoint.stage_id} no longer verifies: material changed "
                        f"or is gone, {len(missing)} hash(es) no longer match any "
                        f"source. Everything after this boundary was produced from it "
                        f"and is discarded as a resume target."
                    ),
                    next_attempt=attempt,
                )
            verified = checkpoint

        return ResumePlan(
            task_id=task_id,
            from_stage=None,
            through_seq=verified.through_seq if verified is not None else 0,
            stopped_reason=None,
            next_attempt=attempt,
        )

    # -- runs ----------------------------------------------------------------- #

    def start_run(self, task_id: TaskId, run: Run) -> Run:
        """Begin a run. A resume creates a *new* run against the same Task."""
        started = run.model_copy(update={"status": RunStatus.RUNNING, "started_at": self._clock()})
        with self._store.unit(task_id) as work:
            work.emit(
                EventType.RUN_STARTED,
                run_id=run.run_id,
                transition=_run_transition(RunStatus.PENDING, RunStatus.RUNNING),
            )
            work.put_run(started)
        return started

    def pause(self, task_id: TaskId, run_id: RunId, *, stage_id: StageId | None = None) -> Run:
        """Park a run, or one stage of it.

        The scope is carried on the event: a ``stage_id`` means this stage is
        parked, its absence means the whole run is. See the module docstring.
        """
        run = self._require_run(task_id, run_id)
        paused = run.model_copy(update={"status": RunStatus.PAUSED})
        with self._store.unit(task_id) as work:
            work.emit(
                EventType.RUN_PAUSED,
                run_id=run_id,
                stage_id=stage_id,
                transition=_run_transition(run.status, RunStatus.PAUSED),
            )
            work.put_run(paused)
        return paused

    def resume_run(self, task_id: TaskId, run_id: RunId) -> Run:
        """Continue a paused run.

        Scoped to the run: a stage-level pause is released by resuming the run
        that stage belongs to, because a stage has no run of its own to resume
        and pretending otherwise would let two runs claim the same stage.
        """
        run = self._require_run(task_id, run_id)
        if run.status is not RunStatus.PAUSED:
            raise ValueError(f"run {run_id} is {run.status.value}, not paused")
        resumed = run.model_copy(update={"status": RunStatus.RUNNING})
        with self._store.unit(task_id) as work:
            work.emit(
                EventType.RUN_RESUMED,
                run_id=run_id,
                transition=_run_transition(RunStatus.PAUSED, RunStatus.RUNNING),
            )
            work.put_run(resumed)
        return resumed

    def stop(self, task_id: TaskId, run_id: RunId) -> Run:
        """Abandon a run. Terminal, and distinct from PAUSED.

        A stopped run is never resumed; a new run against the same Task is.
        That is :class:`~labcairn.runtime.lifecycle.Run`'s own rule — a
        crash-and-resume is a new Run against the same Task, never a new Task —
        and honouring it here is what keeps a Task's history intact across an
        abandonment.
        """
        run = self._require_run(task_id, run_id)
        stopped = run.model_copy(
            update={"status": RunStatus.ABANDONED, "finished_at": self._clock()}
        )
        with self._store.unit(task_id) as work:
            work.emit(
                EventType.RUN_FINISHED,
                run_id=run_id,
                transition=_run_transition(run.status, RunStatus.ABANDONED),
            )
            work.put_run(stopped)
        return stopped

    # -- changed source invalidates downstream --------------------------------- #

    def invalidate_on_source_change(
        self, task_id: TaskId, changed_hashes: Sequence[str]
    ) -> InvalidationReport:
        """Mark every artifact derived from a changed source ``STALE``.

        The derivation walk is the whole mechanism: an artifact is stale when
        its ``derived_from`` cites a ``MATERIAL_FILE`` whose ``content_sha256``
        is one of *changed_hashes*. ``MATERIAL_FILE`` and ``ARTIFACT`` citations
        are exactly the two kinds the receipt model *requires* to carry a hash,
        which is what lets this be a content comparison rather than a name
        match.

        A stale mark is *recorded*, not acted on. Nothing is regenerated and
        nothing is deleted; a human decides whether the change mattered. The
        receipt model enforces the pairing itself — ``staleness`` without a
        ``staleness_reason`` fails validation — so a stale mark nobody can act
        on is not representable.
        """
        changed = set(changed_hashes)
        if not changed:
            return InvalidationReport((), (), ())

        stale_ids: list[str] = []
        with self._store.unit(task_id) as work:
            work.emit(EventType.SOURCE_CHANGED)
            for row in self._artifact_rows(task_id):
                if row.staleness == ArtifactStaleness.STALE.value:
                    continue
                receipt = row_to_receipt(row)
                if not _derives_from(receipt, changed):
                    continue
                work.put_artifact(
                    receipt.model_copy(
                        update={
                            "staleness": ArtifactStaleness.STALE,
                            "staleness_reason": STALE_REASON,
                        }
                    ),
                    # run_id is carried through rather than defaulted: a row that
                    # already names the Run that produced it must keep naming
                    # it, and passing None here would erase it.
                    run_id=RunId(UUID(row.run_id)) if row.run_id else None,
                )
                stale_ids.append(receipt.receipt_id)

        invalidated = tuple(
            stage.stage_id
            for stage in self._stages_of(task_id)
            if set(stage.input_hashes) & changed
        )

        return InvalidationReport(
            changed_hashes=tuple(sorted(changed)),
            stale_artifact_ids=tuple(stale_ids),
            invalidated_stages=invalidated,
        )

    def stale_artifacts(self, task_id: TaskId) -> tuple[ArtifactReceipt, ...]:
        """Every artifact currently marked stale, oldest first."""
        return tuple(
            receipt
            for receipt in load_artifacts(self._session, task_id)
            if receipt.staleness is ArtifactStaleness.STALE
        )

    # -- reads ---------------------------------------------------------------- #

    def _artifact_rows(self, task_id: TaskId) -> tuple[ArtifactRow, ...]:
        rows = self._session.execute(
            select(ArtifactRow)
            .where(ArtifactRow.task_id == str(task_id))
            .order_by(ArtifactRow.revision.asc(), ArtifactRow.artifact_id.asc())
        ).scalars()
        return tuple(rows)

    def _stages_of(self, task_id: TaskId) -> tuple[Stage, ...]:
        rows = self._session.execute(
            select(StageRow)
            .where(StageRow.task_id == str(task_id))
            .order_by(StageRow.stage_id.asc())
        ).scalars()
        return tuple(row_to_stage(row) for row in rows)

    def _next_attempt(self, task_id: TaskId) -> int:
        """The attempt number the next run against this Task should carry.

        Derived from the runs the checkpoints name rather than from a counter, so
        two runs can never both claim to be the first.
        """
        highest = 0
        for checkpoint in list_checkpoints(self._session, task_id):
            run = load_run(self._session, checkpoint.run_id)
            if run is not None and run.attempt > highest:
                highest = run.attempt
        return highest + 1

    def _require_run(self, task_id: TaskId, run_id: RunId) -> Run:
        run = load_run(self._session, run_id)
        if run is None:
            raise ValueError(f"no run {run_id}")
        if str(run.task_id) != str(task_id):
            raise ValueError(f"run {run_id} belongs to task {run.task_id}, not {task_id}")
        return run


def _derives_from(receipt: ArtifactReceipt, changed: set[str]) -> bool:
    """Whether any derivation of *receipt* cites one of *changed*.

    Only citations that carry a hash can answer this, and the filter makes that
    explicit rather than letting ``None`` fall through a set membership test
    into a false positive.
    """
    return any(
        reference.content_sha256 in changed
        for reference in receipt.derived_from
        if reference.content_sha256 is not None
    )


def _run_transition(from_status: RunStatus, to_status: RunStatus) -> EventTransition:
    return EventTransition(from_state=from_status.value, to_state=to_status.value)


__all__ = [
    "STALE_REASON",
    "InvalidationReport",
    "MaterialResolver",
    "MaterialSnapshot",
    "ResumeCoordinator",
    "ResumePlan",
]
