"""The transaction boundary: one unit of work, one SQLite transaction.

ADR-0003 C3 says a transaction contains *one or more events with contiguous
``seq``, and all state-row updates those events describe, **and nothing else**,
and that a crash before COMMIT rolls back both. This module is where that is
enforced rather than described.

The ordering inside a flush is the ADR's, not SQLite's:

1. **Allocate.** ``UPDATE tasks SET last_event_seq = last_event_seq + n ...
   RETURNING last_event_seq`` reads a committed row and hands back a contiguous
   block in one statement. Under ``BEGIN IMMEDIATE`` the write lock is already
   held, so two connections cannot interleave their allocations; the
   ``UNIQUE(task_id, seq)`` index is the backstop if this ever stops being true.
2. **Insert events.** Before the state rows, because an ``operation_intent``
   names an operation whose row does not exist yet. The foreign keys on
   ``events`` are deferred, so this ordering is legal *and* still checked at
   COMMIT.
3. **Update state rows.** Only those the caller asked for, by the explicit
   ``put_*`` methods on :class:`UnitOfWork`. There is no "save everything" call
   and no attribute scanning, which is what keeps "and nothing else" true by
   construction rather than by review.

Any exception at any point — including one raised after the events are in but
before the state rows are written — rolls the whole unit back. That is not a
claim this module makes; ``tests/test_store_atomicity.py`` injects a failure
*between* steps 2 and 3 and asserts both halves are gone.

``events`` is append-only here: this module contains no UPDATE and no DELETE
against that table, so immutability is a property of the only writer rather
than a convention someone might follow loosely.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import partial
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Engine, Select, func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session, sessionmaker

from labcairn.core.ids import ApprovalId, OperationId, RunId, SourceId, StageId, TaskId
from labcairn.db.models import (
    LOCAL_USER_ID,
    ApprovalRow,
    ArtifactRow,
    CheckpointRow,
    EventRow,
    OperationRow,
    RunRow,
    SourceRow,
    StageRow,
    TaskRow,
)
from labcairn.db.session import create_session_factory
from labcairn.reports.receipt import (
    ArtifactKind,
    ArtifactProducerKind,
    ArtifactReceipt,
    ArtifactStaleness,
    DerivationRef,
)
from labcairn.runtime.event import Event, EventTransition, EventType
from labcairn.runtime.lifecycle import Run, RunStatus, Stage, StageStatus, Task, TaskGoal
from labcairn.runtime.operation import (
    Approval,
    ApprovalState,
    Checkpoint,
    Operation,
    OperationState,
)
from labcairn.sources.source import Source, SourceIdentifier, SourceKind, SourceReadability

#: A clock returning an aware UTC datetime. Injected so tests can freeze time
#: instead of asserting against a wall clock that moves.
type Clock = Callable[[], datetime]


def utc_now() -> datetime:
    """The default clock.

    ``datetime.now(UTC)`` rather than ``utcnow()``: the latter is deprecated
    precisely because it returns a *naive* value, and a naive timestamp written
    into ``occurred_at`` is the ambiguity
    :class:`~labcairn.db.models.UtcDateTime` refuses on the way in.
    """
    return datetime.now(UTC)


class StoreError(RuntimeError):
    """Base for the store's own refusals."""


class UnknownTaskError(StoreError):
    """A unit of work named a Task that has no row.

    Raised rather than surfacing as ``NoResultFound`` from the RETURNING clause,
    because the caller who hits it is holding a Task id that was never created —
    a different bug from an empty query, and worth a different message.
    """


@dataclass
class _PendingEvent:
    """An event whose ``seq`` has not been allocated yet.

    The frozen ``Event`` contract requires a positive ``seq`` at construction,
    so validation happens against a provisional value and the real one is
    substituted at flush. Nothing observes the provisional value: it never
    leaves this object, and only ``flush`` reads it.
    """

    provisional: Event


@dataclass
class UnitOfWork:
    """Events and the state rows they describe, pending inside one transaction.

    Obtain one from :meth:`TaskStore.unit`. Every ``put_*`` and ``emit`` call
    records intent; nothing is written until the context manager exits cleanly.
    """

    session: Session
    task_id: TaskId
    clock: Clock
    _events: list[_PendingEvent] = field(default_factory=list)
    #: Each entry writes one state row. The return value (the row) is ignored
    #: by the flush; ``object`` rather than ``None`` because the upserts are
    #: written as lambdas over functions that hand the row back.
    _state_writes: list[Callable[[Session], object]] = field(default_factory=list)
    _committed: list[Event] = field(default_factory=list)

    # -- recording ---------------------------------------------------------- #

    def emit(
        self,
        event_type: EventType,
        *,
        run_id: RunId | None = None,
        stage_id: StageId | None = None,
        operation_id: OperationId | None = None,
        transition: EventTransition | None = None,
        payload: Mapping[str, object] | None = None,
        occurred_at: datetime | None = None,
    ) -> Event:
        """Record an event, validated by the frozen contract.

        Returns the provisional event. The returned value's ``seq`` is **not**
        final — it is replaced during the flush. Read :attr:`events` after the
        context manager exits for the committed values.
        """
        provisional = Event(
            seq=1,  # replaced at flush; validated here, discarded there
            task_id=self.task_id,
            run_id=run_id,
            stage_id=stage_id,
            operation_id=operation_id,
            type=event_type,
            transition=transition,
            payload=dict(payload) if payload else {},
            occurred_at=occurred_at if occurred_at is not None else self.clock(),
        )
        self._events.append(_PendingEvent(provisional))
        return provisional

    def put_run(self, run: Run) -> None:
        """Include a Run row in this unit."""
        self._state_writes.append(partial(_upsert_run, run=run))

    def put_stage(self, stage: Stage) -> None:
        """Include a Stage row in this unit."""
        self._state_writes.append(partial(_upsert_stage, stage=stage))

    def put_operation(self, operation: Operation) -> None:
        """Include an Operation row in this unit."""
        self._state_writes.append(partial(_upsert_operation, operation=operation))

    def put_approval(self, approval: Approval) -> None:
        """Include an Approval row in this unit."""
        self._state_writes.append(partial(_upsert_approval, approval=approval))

    def put_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Include a Checkpoint row in this unit."""
        self._state_writes.append(partial(_upsert_checkpoint, checkpoint=checkpoint))

    def put_artifact(self, receipt: ArtifactReceipt, *, run_id: RunId | None = None) -> None:
        """Include an Artifact row in this unit.

        *run_id* is optional because ``artifact_recorded`` is an annotation
        event: an artifact may be recorded against the Task outside any Run.
        """
        self._state_writes.append(partial(_upsert_artifact, receipt=receipt, run_id=run_id))

    # -- reading back ------------------------------------------------------- #

    @property
    def events(self) -> tuple[Event, ...]:
        """This unit's events with their final ``seq``. Valid after the context
        manager exits."""
        return tuple(self._committed)

    def task_row(self) -> TaskRow:
        """The Task row this unit belongs to.

        Selected by the ``task_id`` column, not ``session.get``: the table's
        primary key is the integer surrogate ``id``, and ``session.get`` looks up
        by primary key — passing a Task id string there silently misses. Raises
        :class:`UnknownTaskError` rather than returning ``None``, because a unit
        of work without a Task is a caller bug and ``None`` would push that
        check into every call site where nobody writes it.
        """
        row = self.session.execute(
            select(TaskRow).where(TaskRow.task_id == str(self.task_id))
        ).scalar_one_or_none()
        if row is None:
            raise UnknownTaskError(f"no Task row for {self.task_id}")
        return row

    # -- the flush ---------------------------------------------------------- #

    def flush(self) -> None:
        """Allocate, insert events, then write state rows. ADR-0003 C3's order."""
        if not self._events and not self._state_writes:
            # An empty unit commits an empty transaction. Allowed and cheap; the
            # alternative is a special case in every caller.
            return

        # --- 1. allocate ----------------------------------------------------- #
        block_start = self._allocate_seq(len(self._events)) if self._events else 0

        # --- 2. events before state, so deferred FKs are satisfied at COMMIT -- #
        for offset, pending in enumerate(self._events):
            final = pending.provisional.model_copy(update={"seq": block_start + offset})
            self.session.add(_event_row(final))
            self._committed.append(final)
        if self._events:
            # Put the INSERTs on the wire before the state writes, so the
            # ordering above is real and not merely the order of the session's
            # unit-of-work queue.
            self.session.flush()

        # --- 3. state rows ---------------------------------------------------- #
        for write in self._state_writes:
            write(self.session)

    def _allocate_seq(self, count: int) -> int:
        """Reserve *count* contiguous ``seq`` values; return the first.

        Reads and advances ``tasks.last_event_seq`` in a single statement
        against a committed row. That row's write lock is already held by
        ``BEGIN IMMEDIATE``, so this read-modify-write cannot interleave with
        another connection's allocation for the same Task.
        """
        statement = (
            update(TaskRow)
            .where(TaskRow.task_id == str(self.task_id))
            .values(last_event_seq=TaskRow.last_event_seq + count)
            .returning(TaskRow.last_event_seq)
        )
        try:
            new_last = self.session.execute(statement).scalar_one()
        except NoResultFound as exc:
            raise UnknownTaskError(f"no Task row for {self.task_id}") from exc
        return new_last - count + 1


class TaskStore:
    """Read/write access to the task authority.

    One instance per :class:`~sqlalchemy.orm.Session`. The session, not this
    object, owns the transaction; :meth:`unit` scopes exactly one.
    """

    def __init__(self, session: Session, *, clock: Clock = utc_now) -> None:
        self._session = session
        self._clock = clock
        #: The factory :meth:`fork` opens its own sessions from. Built on
        #: demand, because a store that is never forked never needs one.
        self._sessions: sessionmaker[Session] | None = None

    @property
    def session(self) -> Session:
        """The session this store reads and writes through.

        Exposed because the recovery layer needs it. ``ResumeCoordinator``
        walks checkpoints and reconciles operations in its own reads, and
        without this it reached into ``_session`` — a private attribute — which
        the G2 exit demonstration did while wiring the two layers together.

        Read-only accessor, not a transfer of ownership: :meth:`unit` still
        scopes every transaction on this store, and callers must not commit or
        roll back through the returned session while a unit is open.
        """
        return self._session

    @property
    def clock(self) -> Clock:
        """The clock this store stamps its events with.

        Read-only, like :attr:`session`, and for the same reason: the store
        owns the clock, and a caller that changed it would be changing the
        store under the operations that are already in flight.
        """
        return self._clock

    def fork(self) -> TaskStore:
        """A store on a session of its own.

        **A session is not thread-safe, and a surface that serves two callers
        at once must not share one.** Two threads on one session do not merely
        interleave their reads: one thread's rollback discards the other
        thread's work, and the SQLite driver — called from two threads at
        once — can take the whole process down with it.

        The new session comes from the same engine, so a fork is another
        connection to the same store and not another store. The clock comes
        along, so a forked store stamps its events the way the store it was
        forked from would have stamped them.

        :raises StoreError: this store's session is bound to a connection
            rather than to an engine. A connection belongs to one session, and
            two sessions on one connection are one session wearing two hats.
        """
        bind = self._session.get_bind()
        if not isinstance(bind, Engine):
            raise StoreError(
                "this store's session is bound to a connection rather than to an "
                "engine, so it cannot open a session of its own: a connection "
                "belongs to one session, and two sessions sharing one are one "
                "session wearing two hats."
            )
        if self._sessions is None:
            self._sessions = create_session_factory(bind)
        return TaskStore(self._sessions(), clock=self._clock)

    @contextmanager
    def unit(self, task_id: TaskId) -> Iterator[UnitOfWork]:
        """One transaction: the events emitted inside, plus their state rows.

        Commits on clean exit. On any exception — including one raised while
        the flush is applying state rows, after the events are already on the
        wire — both halves roll back.
        """
        work = UnitOfWork(self._session, task_id, clock=self._clock)
        try:
            yield work
            # The flush is *inside* the guard on purpose. Moving it out means a
            # failure while writing state rows escapes without a rollback and
            # leaves a half-applied unit pending on the session.
            work.flush()
            self._session.commit()
        except BaseException:
            self._session.rollback()
            raise

    def create_task(self, task: Task) -> Event:
        """Create a Task and its first event in one transaction.

        The Task row is written first because it *is* the counter the first
        ``seq`` is allocated from; there is no row to increment otherwise. This
        is the one ordering exception in the module, and it is not a violation
        of C3: that row is not a state change an event describes, it is the
        thing the event log hangs off.

        Returns the committed ``task_created`` event.
        """
        self._session.add(
            TaskRow(
                task_id=str(task.task_id),
                owner_id=LOCAL_USER_ID,
                title=task.title,
                objective=task.goal.objective,
                success_criterion=task.goal.success_criterion,
                bound_source_ids=[str(s) for s in task.bound_source_ids],
                revision=task.revision,
                last_event_seq=0,
                created_at=task.created_at,
                updated_at=task.updated_at,
                schema_version=task.schema_version,
            )
        )
        self._session.flush()
        with self.unit(task.task_id) as work:
            work.emit(EventType.TASK_CREATED, occurred_at=task.created_at)
        return work.events[0]

    def relocate_sources(self, renames: Mapping[str, str]) -> int:
        """Move source rows to the paths the ledger's contract names.

        **Why this exists.** ``Source.relative_path`` is workspace-relative,
        and the layer's readers resolve it against the workspace root: a row
        holding a root-relative path resolves into the wrong root, and the
        ``source.inventory`` capability refuses it because the root it landed
        in is not a source root. The walk writes the key it was given, and
        the key is root-relative, so a material the walk ingested cannot be
        read back at all.

        The rename is by source id, so it moves the row the walk wrote rather
        than a row that happens to hold the same path.

        :param renames: the source ids, and the workspace-relative path each
            one should hold.
        :returns: how many rows moved.
        """
        moved = 0
        for source_id, relative_path in renames.items():
            statement = (
                update(SourceRow)
                .where(SourceRow.source_id == source_id)
                .values(relative_path=relative_path)
            )
            changed = cast(CursorResult[Any], self._session.execute(statement)).rowcount
            moved += max(changed, 0)
        self._session.commit()
        return moved

    def bind_sources(
        self,
        task_id: TaskId,
        source_ids: Sequence[SourceId],
        *,
        occurred_at: datetime | None = None,
    ) -> Event | None:
        """Bind material to a Task, and record the revision, in one transaction.

        The binding is a **state change**, so it is written with the event that
        describes it: ADR-0003 C3 puts a state row and the event that describes
        it in one transaction, and a binding nobody was told about is a change
        the log does not record. The column is a JSON one, so the update needs
        no migration.

        **No event when nothing changed.** A binding that already holds these
        ids is not a revision, and emitting ``task_revised`` for it would put
        a second event in the log for a state that did not move -- which is
        what "the same operation twice changes nothing" has to mean.

        :returns: the committed event, or ``None`` when the binding already
            held these ids.
        :raises UnknownTaskError: the store holds no Task with that id.
        """
        bound = [str(source_id) for source_id in source_ids]
        moment = occurred_at if occurred_at is not None else self._clock()
        with self.unit(task_id) as work:
            row = self._session.execute(
                select(TaskRow).where(TaskRow.task_id == str(task_id))
            ).scalar_one_or_none()
            if row is None:
                raise UnknownTaskError(f"no Task row for {task_id}")
            if list(row.bound_source_ids) == bound:
                return None
            row.bound_source_ids = bound
            row.updated_at = moment
            # Flushed here rather than left to the unit's own flush, so that
            # the row the event allocator updates is the row this write
            # changed: the allocator's statement is a bulk update, and a
            # pending change of ours still in the session would be
            # synchronised from the database against it.
            self._session.flush()
            work.emit(EventType.TASK_REVISED, occurred_at=moment)
        return work.events[0]


# --------------------------------------------------------------------------- #
# contract -> row projections
# --------------------------------------------------------------------------- #


def _event_row(event: Event) -> EventRow:
    transition = event.transition
    return EventRow(
        seq=event.seq,
        event_id=str(event.event_id),
        task_id=str(event.task_id),
        run_id=str(event.run_id) if event.run_id is not None else None,
        stage_id=str(event.stage_id) if event.stage_id is not None else None,
        operation_id=str(event.operation_id) if event.operation_id is not None else None,
        type=event.type.value,
        from_state=transition.from_state if transition is not None else None,
        to_state=transition.to_state if transition is not None else None,
        schema_version=event.schema_version,
        occurred_at=event.occurred_at,
        document=event.model_dump_json(),
        payload=json.dumps(dict(event.payload), sort_keys=True),
    )


def _upsert[RowT](
    session: Session,
    model: type[RowT],
    key_column: Any,
    key_value: str,
    values: dict[str, Any],
) -> RowT:
    """Update the row with this natural key, or insert it.

    ``session.merge`` was rejected: it SELECTs unconditionally and treats a
    missing row as an insert carrying a default primary key, which turns a typo
    in a Task id into a *new* row rather than an error. The lookup here is on
    the natural key column, which is also what the unique index guarantees.
    """
    existing: RowT | None = session.execute(
        select(model).where(key_column == key_value)
    ).scalar_one_or_none()
    if existing is None:
        row = model(**values)
        session.add(row)
        return row
    for name, value in values.items():
        setattr(existing, name, value)
    return existing


def _upsert_run(session: Session, run: Run) -> RunRow:
    return _upsert(
        session,
        RunRow,
        RunRow.run_id,
        str(run.run_id),
        {
            "run_id": str(run.run_id),
            "task_id": str(run.task_id),
            "status": run.status.value,
            "attempt": run.attempt,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "schema_version": run.schema_version,
        },
    )


def _upsert_stage(session: Session, stage: Stage) -> StageRow:
    return _upsert(
        session,
        StageRow,
        StageRow.stage_id,
        str(stage.stage_id),
        {
            "stage_id": str(stage.stage_id),
            "task_id": str(stage.task_id),
            "run_id": str(stage.run_id),
            "name": stage.name,
            "status": stage.status.value,
            "input_hashes": list(stage.input_hashes),
            "output_hashes": list(stage.output_hashes),
            "blocked_reason": stage.blocked_reason,
            "schema_version": stage.schema_version,
        },
    )


def _upsert_operation(session: Session, operation: Operation) -> OperationRow:
    return _upsert(
        session,
        OperationRow,
        OperationRow.operation_id,
        str(operation.operation_id),
        {
            "operation_id": str(operation.operation_id),
            "task_id": str(operation.task_id),
            "run_id": str(operation.run_id),
            "stage_id": str(operation.stage_id),
            "state": operation.state.value,
            "capability": operation.capability,
            "resource_key": operation.resource_key,
            "depends_on": list(operation.depends_on),
            "args_digest": operation.args_digest,
            "schema_version": operation.schema_version,
        },
    )


def _upsert_approval(session: Session, approval: Approval) -> ApprovalRow:
    return _upsert(
        session,
        ApprovalRow,
        ApprovalRow.approval_id,
        str(approval.approval_id),
        {
            "approval_id": str(approval.approval_id),
            "task_id": str(approval.task_id),
            "operation_id": str(approval.operation_id),
            "capability": approval.capability,
            "resource_key": approval.resource_key,
            "args_digest": approval.args_digest,
            "state": approval.state.value,
            "expires_at": approval.expires_at,
            "granted_at": approval.granted_at,
            "consumed_at": approval.consumed_at,
            "schema_version": approval.schema_version,
        },
    )


def _upsert_checkpoint(session: Session, checkpoint: Checkpoint) -> CheckpointRow:
    return _upsert(
        session,
        CheckpointRow,
        CheckpointRow.checkpoint_id,
        str(checkpoint.checkpoint_id),
        {
            "checkpoint_id": str(checkpoint.checkpoint_id),
            "task_id": str(checkpoint.task_id),
            "run_id": str(checkpoint.run_id),
            "stage_id": str(checkpoint.stage_id),
            "through_seq": checkpoint.through_seq,
            "material_hashes": list(checkpoint.material_hashes),
            "created_at": checkpoint.created_at,
            "schema_version": checkpoint.schema_version,
        },
    )


def _upsert_artifact(
    session: Session, receipt: ArtifactReceipt, run_id: RunId | None
) -> ArtifactRow:
    return _upsert(
        session,
        ArtifactRow,
        ArtifactRow.artifact_id,
        receipt.receipt_id,
        {
            "artifact_id": receipt.receipt_id,
            "task_id": receipt.task_id,
            "run_id": str(run_id) if run_id is not None else None,
            "kind": receipt.kind.value,
            "relative_path": receipt.relative_path,
            "content_sha256": receipt.content_sha256,
            "size_bytes": receipt.size_bytes,
            "revision": receipt.revision,
            "produced_by": receipt.produced_by.value,
            "producer_id": receipt.producer_id,
            "derived_from": [ref.model_dump(mode="json") for ref in receipt.derived_from],
            "staleness": receipt.staleness.value,
            "staleness_reason": receipt.staleness_reason,
            "media_type": receipt.media_type,
            "created_at": receipt.created_at,
            "schema_version": receipt.schema_version,
        },
    )


# --------------------------------------------------------------------------- #
# reading
# --------------------------------------------------------------------------- #


def select_events(task_id: TaskId, *, after_seq: int = 0, limit: int = 500) -> Select[EventRow]:
    """The resume query ADR-0003 C1's ``after_seq`` exists to make possible.

    Ordering is by ``seq`` and nothing else. ``occurred_at`` is not a sort key
    and not a tiebreak: wall-clock is not monotonic, and a resumed process can
    emit a timestamp earlier than one already recorded.
    """
    return (
        select(EventRow)
        .where(EventRow.task_id == str(task_id), EventRow.seq > after_seq)
        .order_by(EventRow.seq.asc())
        .limit(limit)
    )


def events_after(
    session: Session, task_id: TaskId, *, after_seq: int = 0, limit: int = 500
) -> tuple[Event, ...]:
    """A Task's event tail as frozen contracts, excluding ``after_seq`` itself."""
    rows = session.execute(select_events(task_id, after_seq=after_seq, limit=limit)).scalars()
    return tuple(Event.model_validate_json(row.document) for row in rows)


def count_events(session: Session, task_id: TaskId) -> int:
    """How many events a Task has."""
    return int(
        session.execute(
            select(func.count()).select_from(EventRow).where(EventRow.task_id == str(task_id))
        ).scalar_one()
    )


def last_seq(session: Session, task_id: TaskId) -> int:
    """The Task's counter, i.e. the ``seq`` of its newest event.

    A column select rather than ``session.get(TaskRow, ...)``. ``get`` answers
    from the session's identity map when the row is already loaded there, and
    with ``expire_on_commit=False`` that cached object is *not* refreshed by a
    later commit — so a caller reading the counter after writing would be told
    the value it already knew. Selecting the single column bypasses the map and
    always goes to the database.
    """
    found = session.execute(
        select(TaskRow.last_event_seq).where(TaskRow.task_id == str(task_id))
    ).scalar_one_or_none()
    return 0 if found is None else int(found)


# --------------------------------------------------------------------------- #
# the list queries
# --------------------------------------------------------------------------- #
#
# LC-P1-12's three surfaces — the CLI's task list, the API's index and the UI's
# task list — all need the same four answers, and there was nowhere in the
# store to get them: only ``create_task``, the unit of work and the event
# readers existed. These are that surface, added once.
#
# Two conventions hold across all of them, and both are properties of the data
# rather than of how SQLite happens to lay out a table.
#
# **The order is a total order, and it is stated.** A list whose order depends
# on the query plan is a list that reshuffles between two reads of the same
# state, and a reader reports that as "it shuffled". Each list leads with the
# column that carries the project's own notion of sequence for that kind — the
# Task's ``created_at``, the Run's ``attempt``, the artefact's ``revision`` —
# and every list ends with the row's unique natural key, so no two rows can
# tie. Where the kind has no sequence column of its own, the id leads: ids are
# UUIDv7, which the project mints monotonically, so id order is creation order.
#
# **A Task that does not exist is not an empty list.** :meth:`UnitOfWork.task_row`
# already draws the line — "a unit of work without a Task is a caller bug and
# ``None`` would push that check into every call site where nobody writes it" —
# and these readers keep it. A task-scoped read of a task that was never
# created raises :class:`UnknownTaskError`; a task-scoped read of a task that
# exists and holds nothing returns an empty tuple. Those are two different
# facts, and a caller that cannot tell them apart will report "no stages" for a
# task id it mistyped.


def list_tasks(session: Session) -> tuple[Task, ...]:
    """Every Task the store holds, oldest first.

    Ordered by ``(created_at, task_id)``. ``created_at`` is when the Task came
    into being, and ``task_id`` breaks the tie, because two Tasks created in the
    same instant are as common as two files written in the same second and a
    list that leaves their order to the query plan is a list that reshuffles.

    Not task-scoped: this is the only one of the four that is not, because a
    Task is the root of the hierarchy rather than something inside one.
    """
    rows = session.execute(
        select(TaskRow).order_by(TaskRow.created_at.asc(), TaskRow.task_id.asc())
    ).scalars()
    return tuple(_task_from_row(row) for row in rows)


def load_task(session: Session, task_id: TaskId) -> Task:
    """One Task by its domain id.

    :raises UnknownTaskError: the store holds no Task with that id. The same
        refusal the unit of work raises, because a Task id that was never
        created is a caller bug rather than an empty answer.
    """
    row = session.execute(
        select(TaskRow).where(TaskRow.task_id == str(task_id))
    ).scalar_one_or_none()
    if row is None:
        raise UnknownTaskError(f"no Task row for {task_id}")
    return _task_from_row(row)


def list_runs(session: Session, task_id: TaskId) -> tuple[Run, ...]:
    """A Task's Runs, earliest attempt first.

    Ordered by ``(attempt, run_id)``. ``attempt`` is the project's own notion
    of sequence for a Run — a resume is a *new* Run against the same Task with
    the next attempt number — so it leads, and ``run_id`` breaks the tie.

    :raises UnknownTaskError: the store holds no Task with that id.
    """
    _require_task(session, task_id)
    rows = session.execute(
        select(RunRow)
        .where(RunRow.task_id == str(task_id))
        .order_by(RunRow.attempt.asc(), RunRow.run_id.asc())
    ).scalars()
    return tuple(
        Run(
            run_id=RunId(UUID(row.run_id)),
            task_id=TaskId(UUID(row.task_id)),
            status=RunStatus(row.status),
            attempt=row.attempt,
            started_at=row.started_at,
            finished_at=row.finished_at,
        )
        for row in rows
    )


def list_stages(session: Session, task_id: TaskId) -> tuple[Stage, ...]:
    """A Task's Stages, in the order they were created.

    Ordered by ``stage_id``. A Stage has no sequence column of its own — the
    runtime identifies a stage by a UUID precisely because a stage belongs to
    one Run and two Runs of the same Task must not collide — and UUIDv7 ids are
    minted monotonically, so the id order is the creation order. This is the
    same ordering :mod:`labcairn.recovery.resume` already uses to read a Task's
    stages, so the two readers cannot disagree about what "the stages" are.

    :raises UnknownTaskError: the store holds no Task with that id.
    """
    _require_task(session, task_id)
    rows = session.execute(
        select(StageRow).where(StageRow.task_id == str(task_id)).order_by(StageRow.stage_id.asc())
    ).scalars()
    return tuple(
        Stage(
            stage_id=StageId(UUID(row.stage_id)),
            task_id=TaskId(UUID(row.task_id)),
            run_id=RunId(UUID(row.run_id)),
            name=row.name,
            status=StageStatus(row.status),
            input_hashes=tuple(row.input_hashes),
            output_hashes=tuple(row.output_hashes),
            blocked_reason=row.blocked_reason,
        )
        for row in rows
    )


def list_artifacts(session: Session, task_id: TaskId) -> tuple[ArtifactReceipt, ...]:
    """A Task's artefact receipts, oldest first.

    Ordered by ``(revision, artifact_id)``, which is the ordering
    :mod:`labcairn.recovery.persistence` already uses for the same rows.
    ``revision`` is LC-P1-11's own version counter, so v1 of a report comes
    before v2 of it, and ``artifact_id`` breaks the tie.

    :raises UnknownTaskError: the store holds no Task with that id.
    """
    _require_task(session, task_id)
    rows = session.execute(
        select(ArtifactRow)
        .where(ArtifactRow.task_id == str(task_id))
        .order_by(ArtifactRow.revision.asc(), ArtifactRow.artifact_id.asc())
    ).scalars()
    return tuple(_receipt_from_row(row) for row in rows)


def list_operations(session: Session, task_id: TaskId) -> tuple[Operation, ...]:
    """A Task's operations, oldest first.

    Ordered by ``operation_id``. An operation has no sequence column, and
    UUIDv7 ids are minted monotonically, so the id order is the order they
    were planned in — the same reasoning
    :func:`labcairn.recovery.persistence.find_operations_in_state` gives for
    the subset it reads.

    :raises UnknownTaskError: the store holds no Task with that id.
    """
    _require_task(session, task_id)
    rows = session.execute(
        select(OperationRow)
        .where(OperationRow.task_id == str(task_id))
        .order_by(OperationRow.operation_id.asc())
    ).scalars()
    return tuple(
        Operation(
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
        for row in rows
    )


def list_approvals(session: Session, task_id: TaskId) -> tuple[Approval, ...]:
    """A Task's approvals, oldest first.

    Ordered by ``approval_id``: an approval has no sequence column, and
    UUIDv7 ids are minted monotonically, so the id order is the order they
    were requested in.

    :raises UnknownTaskError: the store holds no Task with that id.
    """
    _require_task(session, task_id)
    rows = session.execute(
        select(ApprovalRow)
        .where(ApprovalRow.task_id == str(task_id))
        .order_by(ApprovalRow.approval_id.asc())
    ).scalars()
    return tuple(
        Approval(
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
        for row in rows
    )


def list_sources(session: Session) -> tuple[Source, ...]:
    """Every source in the ledger, oldest ingest first.

    Ordered by ``(ingested_at, source_id)``. The ledger holds **no** ``task_id``
    column — a material belongs to the workspace and must outlive the Tasks
    that cite it — so this is the one query that is not task-scoped. Which of
    these a Task is bound to is the Task's own binding, not a column.

    The ledger is the workspace's, not this store's, and
    :mod:`labcairn.db.materials` writes it; this reader is here because the
    application layer is not allowed to reach into a table it does not own, and
    a source a Task is bound to has to be readable somewhere.
    """
    rows = session.execute(
        select(SourceRow).order_by(SourceRow.ingested_at.asc(), SourceRow.source_id.asc())
    ).scalars()
    return tuple(_source_from_row(row) for row in rows)


def load_source(session: Session, source_id: str) -> Source | None:
    """One source by its id, or ``None`` when the ledger holds no such row.

    ``None`` rather than a refusal, because a missing source is an **empty
    answer** and not a caller bug: the ledger holds material, and a caller
    asking for material that was never ingested is asking a question with a
    legitimate empty answer. The refusal lives in the layer above, which knows
    whether a missing source is fatal for the operation being performed.
    """
    row = session.execute(
        select(SourceRow).where(SourceRow.source_id == str(source_id))
    ).scalar_one_or_none()
    return None if row is None else _source_from_row(row)


# --------------------------------------------------------------------------- #
# row -> contract
# --------------------------------------------------------------------------- #


def _require_task(session: Session, task_id: TaskId) -> None:
    """Refuse a task-scoped read of a Task that does not exist.

    A separate statement rather than a join on the first query, because the
    answer differs: an empty list means "this Task holds nothing of that kind"
    and a refusal means "this Task id names nothing". Folding the two together
    would make a mistyped id look like a Task with no stages.
    """
    found = session.execute(
        select(TaskRow.task_id).where(TaskRow.task_id == str(task_id))
    ).scalar_one_or_none()
    if found is None:
        raise UnknownTaskError(f"no Task row for {task_id}")


def _task_from_row(row: TaskRow) -> Task:
    """Rebuild the Task contract from its row."""
    return Task(
        task_id=TaskId(UUID(row.task_id)),
        title=row.title,
        goal=TaskGoal(objective=row.objective, success_criterion=row.success_criterion),
        bound_source_ids=tuple(SourceId(source_id) for source_id in row.bound_source_ids),
        revision=row.revision,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _receipt_from_row(row: ArtifactRow) -> ArtifactReceipt:
    """Rebuild the frozen receipt contract from its row.

    ``derived_from`` is stored as already-dumped JSON, so it round-trips
    through :class:`DerivationRef` validation here. A row this build cannot
    read raises, which is the intended behaviour: the store is the authority
    and a receipt it cannot load is a receipt nobody may claim to have produced.
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


def _source_from_row(row: SourceRow) -> Source:
    """Rebuild the source contract from its row.

    ``identifiers`` round-trips through the contract's own validation, so a row
    carrying an identifier this build cannot read is refused rather than
    silently carried through as an opaque string.
    """
    return Source(
        source_id=row.source_id,
        kind=SourceKind(row.kind),
        display_name=row.display_name,
        relative_path=row.relative_path,
        content_sha256=row.content_sha256,
        size_bytes=row.size_bytes,
        readability=SourceReadability(row.readability),
        readability_disclosure=row.readability_disclosure,
        identifiers=tuple(SourceIdentifier.model_validate(item) for item in row.identifiers),
        ingested_at=row.ingested_at,
    )


__all__ = [
    "Clock",
    "StoreError",
    "TaskStore",
    "UnitOfWork",
    "UnknownTaskError",
    "count_events",
    "events_after",
    "last_seq",
    "list_approvals",
    "list_artifacts",
    "list_operations",
    "list_runs",
    "list_sources",
    "list_stages",
    "list_tasks",
    "load_source",
    "load_task",
    "select_events",
    "utc_now",
]
