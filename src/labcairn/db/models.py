"""The eight tables that make SQLite the task authority.

Three decisions in this file are load bearing, and two of them were corrections
rather than design:

**``events.id`` and ``events.seq`` are different columns.** ``id`` is
``INTEGER PRIMARY KEY AUTOINCREMENT`` — the SQLite rowid, table-wide identity,
never used for ordering and never exposed to a client. ``seq`` is a plain
``INTEGER NOT NULL`` with ``UNIQUE(task_id, seq)``. In SQLite an
``INTEGER PRIMARY KEY`` *is* the rowid, so making ``seq`` one would have made it
unique table-wide: Task A would hold 1, 2, 5 while Task B held 3, 4, and no
client resuming with ``after_seq=<last_seen>`` could reason about one Task's
contiguous tail. ``tasks.last_event_seq`` is the counter that ``seq`` is
allocated from, inside the same transaction.

**``events.run_id`` is nullable and the requirement is enforced per event
type, by CHECK constraint.** A column-level ``NOT NULL`` would make
``task_created`` uninsertable, because a Task exists before its first Run and
can be revised between Runs (ADR-0003 C1, R-02). The constraints below are
generated from :class:`~labcairn.runtime.event.EventType` at import time, so
the closed vocabulary is enforced by the database as well as by Pydantic: an
unknown type is rejected by both, never coerced.

**Foreign keys on ``events`` are deferred.** ADR-0003 C3 requires the events to
be inserted *before* the state rows they describe, so an ``operation_intent``
event naming an ``operation_id`` whose row does not exist yet is the normal
case, not a bug. ``DEFERRABLE INITIALLY DEFERRED`` lets the insert happen first
and still checks referential integrity at COMMIT, when every row exists. The
cost is that a dangling reference is reported at commit time rather than at
insert time, which is the price of the ordering the ADR mandates.

Nothing here is a domain decision; every column traces to a frozen contract in
``labcairn.runtime`` or ``labcairn.reports``. Where a table holds a contract's
JSON document (``events.payload``), the dedicated columns beside it exist so the
event stream can be queried without deserialising.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any, Final

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from labcairn.db.base import Base, sql_string_list
from labcairn.runtime.event import EventType, event_requires_operation_context, event_requires_run

#: The single Phase-1 principal. See :data:`OWNER_SCOPE_NOTE`.
LOCAL_USER_ID: Final[str] = "local-user"

#: Why ``tasks.owner_id`` exists, and what it is not.
#:
#: Phase 1 is a **local, single-user** application: there is no account system,
#: no credential, and no trust boundary here. ``owner_id`` is not
#: authentication and must never be presented as one — it carries no secret and
#: authorises nothing. It exists so that two questions are answerable from the
#: schema rather than from convention: *whose* Task this is, and *what a future
#: multi-user migration has a column to populate*. When multi-user scope
#: arrives (ADR to be written; not in Phase 1), the column becomes a real
#: foreign key to a ``users`` table and the single value below becomes the
#: bootstrap principal. Until then it is a scope label, and every row written
#: by this build carries the same one.
OWNER_SCOPE_NOTE: Final[str] = (
    "Phase 1 is local single user. owner_id is a scope label, not authentication; "
    "it authorises nothing and holds no credential."
)

#: Event types that must name a Run. Generated from the frozen contract.
_RUN_SCOPED_TYPES: Final[frozenset[str]] = frozenset(
    t.value for t in EventType if event_requires_run(t)
)

#: Event types that must *not* name a Run: the Task-level pair plus the three
#: annotations about material rather than attempts.
_TASK_LEVEL_TYPES: Final[frozenset[str]] = frozenset(
    t.value for t in EventType if not event_requires_run(t)
)

#: Event types that must name both a Stage and an Operation.
_OPERATION_CONTEXT_TYPES: Final[frozenset[str]] = frozenset(
    t.value for t in EventType if event_requires_operation_context(t)
)

_NON_OPERATION_CONTEXT_TYPES: Final[frozenset[str]] = frozenset(
    t.value for t in EventType if not event_requires_operation_context(t)
)

#: Event types that describe a change and therefore carry from/to state.
#: Mirrors ``runtime.event._TRANSITION_TYPES``, which is private; a behavioural
#: test asserts this set agrees with what ``Event(...)`` actually enforces, so
#: the duplication cannot drift.
_TRANSITION_TYPES: Final[frozenset[str]] = frozenset(
    t.value for t in EventType if t.name.startswith(("RUN_", "STAGE_", "OPERATION_", "APPROVAL_"))
)

#: The annotation events: no transition, and not to be used to rebuild state.
_NON_TRANSITION_TYPES: Final[frozenset[str]] = (
    frozenset(t.value for t in EventType) - _TRANSITION_TYPES
)


class UtcDateTime(TypeDecorator[datetime | None]):
    """ISO-8601 UTC text, with a naive datetime refused at the boundary.

    SQLite has no native timestamp type, and SQLAlchemy's ``DateTime`` would
    store an aware datetime without its offset and hand back a naive one —
    which is exactly the ambiguity that makes ``occurred_at`` untrustworthy.
    Storing the canonical string and **raising** on a naive value means a
    caller in the wrong timezone finds out at the write rather than discovering
    six months later that two events are four hours apart.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, datetime):
            raise TypeError(f"expected a datetime, got {type(value).__name__}")
        if value.tzinfo is None:
            raise ValueError(
                "refusing a naive datetime: the store has one timezone (UTC) and a naive "
                "value does not say which instant it means"
            )
        return value.astimezone(UTC).isoformat()

    def process_result_value(self, value: str | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _list_of(values: Iterable[str]) -> str:
    return sql_string_list(list(values))


# --------------------------------------------------------------------------- #
# tasks
# --------------------------------------------------------------------------- #


class TaskRow(Base):
    """The continuing research objective, and the per-Task ``seq`` counter.

    ``last_event_seq`` is the reason this table is the natural place for the
    counter: it is the row the transaction already has a write lock on (under
    ``BEGIN IMMEDIATE``), so allocating from it cannot interleave with another
    writer's allocation for the same Task. A counter in the ``events`` table
    would need its own lock and could be raced.
    """

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    #: See :data:`OWNER_SCOPE_NOTE`. Not authentication.
    owner_id: Mapped[str] = mapped_column(Text, nullable=False, default=LOCAL_USER_ID)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    success_criterion: Mapped[str] = mapped_column(Text, nullable=False)
    #: Materials the Task is bound to, as SourceId strings. Hashes, not paths:
    #: a path moves, a content hash does not.
    bound_source_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    #: Highest ``seq`` handed out for this Task. 0 means "no events yet".
    last_event_seq: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        CheckConstraint("last_event_seq >= 0", name="last_event_seq_non_negative"),
        CheckConstraint("revision >= 1", name="revision_positive"),
    )


# --------------------------------------------------------------------------- #
# runs
# --------------------------------------------------------------------------- #


class RunRow(Base):
    """One execution attempt against a Task. A resume is a new Run."""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    task_id: Mapped[str] = mapped_column(
        Text, ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    started_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        Index("ix_runs_task_id", "task_id"),
        CheckConstraint("attempt >= 1", name="attempt_positive"),
    )


# --------------------------------------------------------------------------- #
# stages
# --------------------------------------------------------------------------- #


class StageRow(Base):
    """A bounded unit of work inside a Run with declared inputs and outputs."""

    __tablename__ = "stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stage_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    task_id: Mapped[str] = mapped_column(
        Text, ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[str] = mapped_column(
        Text, ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    #: Content hashes consumed and produced. "Changed input invalidates
    #: downstream" is enforced by comparing these, never by mtime.
    input_hashes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    output_hashes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    blocked_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        Index("ix_stages_run_id", "run_id"),
        # A reason attached to something that is not blocked is a claim about
        # something that did not happen. Mirrors Stage._reason_only_when_blocked.
        CheckConstraint(
            "(status = 'blocked') = (blocked_reason IS NOT NULL)", name="reason_only_when_blocked"
        ),
    )


# --------------------------------------------------------------------------- #
# operations
# --------------------------------------------------------------------------- #


class OperationRow(Base):
    """One attempt at one side effect."""

    __tablename__ = "operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operation_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    task_id: Mapped[str] = mapped_column(
        Text, ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[str] = mapped_column(
        Text, ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False
    )
    stage_id: Mapped[str] = mapped_column(
        Text, ForeignKey("stages.stage_id", ondelete="CASCADE"), nullable=False
    )
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    #: A registered capability id, not free text: policy resolves by capability
    #: and a typo must fail closed rather than fall through to a default.
    capability: Mapped[str] = mapped_column(String(200), nullable=False)
    resource_key: Mapped[str] = mapped_column(String(2000), nullable=False)
    depends_on: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    args_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        Index("ix_operations_run_id", "run_id"),
        Index("ix_operations_stage_id", "stage_id"),
    )


# --------------------------------------------------------------------------- #
# approvals
# --------------------------------------------------------------------------- #


class ApprovalRow(Base):
    """A human decision, recorded as a row rather than a transient UI flag."""

    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    approval_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    task_id: Mapped[str] = mapped_column(
        Text, ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False
    )
    operation_id: Mapped[str] = mapped_column(
        Text, ForeignKey("operations.operation_id", ondelete="CASCADE"), nullable=False
    )
    capability: Mapped[str] = mapped_column(String(200), nullable=False)
    resource_key: Mapped[str] = mapped_column(String(2000), nullable=False)
    args_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    granted_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        Index("ix_approvals_operation_id", "operation_id"),
        CheckConstraint(
            "granted_at IS NULL OR expires_at > granted_at",
            name="expiry_after_grant",
        ),
        CheckConstraint(
            "consumed_at IS NULL OR granted_at IS NULL OR consumed_at >= granted_at",
            name="consume_after_grant",
        ),
    )


# --------------------------------------------------------------------------- #
# checkpoints
# --------------------------------------------------------------------------- #


class CheckpointRow(Base):
    """Immutable, versioned evidence that a stage boundary was crossed.

    ``through_seq`` is a per-Task ``seq``, not a rowid and not a wall clock:
    it names the highest event included, so "resume from here" is expressible
    without trusting the timestamps (ADR-0003 C1).
    """

    __tablename__ = "checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    checkpoint_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    task_id: Mapped[str] = mapped_column(
        Text, ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[str] = mapped_column(
        Text, ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=False
    )
    stage_id: Mapped[str] = mapped_column(
        Text, ForeignKey("stages.stage_id", ondelete="CASCADE"), nullable=False
    )
    through_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    material_hashes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        Index("ix_checkpoints_run_id", "run_id"),
        CheckConstraint("through_seq >= 1", name="through_seq_positive"),
    )


# --------------------------------------------------------------------------- #
# artifacts
# --------------------------------------------------------------------------- #


class ArtifactRow(Base):
    """One generated output and everything needed to say where it came from.

    Mirrors :class:`labcairn.reports.receipt.ArtifactReceipt`. The contract is
    frozen and owned by another task, so this table stores its fields rather
    than redefining them, and ``derived_from`` keeps the provenance chain as
    JSON so it stays comparable against the contract's own model.
    """

    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    #: The receipt's ``receipt_id``. Named ``artifact_id`` here because the table
    #: is the artifact ledger; the value is the frozen contract's id verbatim.
    artifact_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    task_id: Mapped[str] = mapped_column(
        Text, ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False
    )
    #: Nullable: an artifact may be recorded against the Task outside any Run
    #: (``artifact_recorded`` is an annotation event and carries no run_id).
    run_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("runs.run_id", ondelete="CASCADE"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(2000), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    produced_by: Mapped[str] = mapped_column(String(32), nullable=False)
    producer_id: Mapped[str] = mapped_column(String(200), nullable=False)
    derived_from: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    staleness: Mapped[str] = mapped_column(String(16), nullable=False, default="current")
    staleness_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        # LC-P1-11 versions artifacts rather than overwriting them, so the
        # previous bytes stay addressable. (task, path, revision) is unique.
        UniqueConstraint("task_id", "relative_path", "revision", name="uq_artifacts_revision"),
        Index("ix_artifacts_run_id", "run_id"),
        CheckConstraint("size_bytes >= 0", name="size_non_negative"),
        CheckConstraint("revision >= 1", name="revision_positive"),
        # A stale mark nobody can act on is decoration; a reason on something
        # that is not stale is a claim about something that did not happen.
        CheckConstraint(
            "(staleness = 'stale') = (staleness_reason IS NOT NULL)",
            name="staleness_reason_paired",
        ),
    )


# --------------------------------------------------------------------------- #
# events
# --------------------------------------------------------------------------- #


class EventRow(Base):
    """One immutable, append-only fact. Append-only is enforced, not merely
    documented: :mod:`labcairn.db.repository` is the only writer and it never
    issues an UPDATE or DELETE against this table.
    """

    __tablename__ = "events"

    #: Table-wide row identity. **Never** used for ordering and never exposed
    #: as a Task-local number. See the module docstring for why it cannot be.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    #: Per-Task, gapless from 1, allocated inside the same transaction from
    #: ``tasks.last_event_seq``. A plain column, not a rowid.
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    event_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    task_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("tasks.task_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"),
        nullable=False,
    )
    #: **Nullable.** Required only for the five Run-scoped families; a Task
    #: exists before its first Run and can be revised between Runs (R-02).
    run_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("runs.run_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"),
        nullable=True,
    )
    stage_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("stages.stage_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"),
        nullable=True,
    )
    operation_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey(
            "operations.operation_id", ondelete="CASCADE", deferrable=True, initially="DEFERRED"
        ),
        nullable=True,
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    to_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    #: Informational only. Never used to order anything.
    occurred_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    #: The frozen ``Event`` document, so the whole contract round-trips and a
    #: field added to it later is not lost by the columns above.
    #:
    #: Named ``document`` rather than ``payload`` deliberately. ADR-0003 C1
    #: reserves ``payload`` for the **type-specific** content an event carries,
    #: and this column holds the entire event. Two different things sharing one
    #: name is how a reader comes to believe the store keeps the C1 payload when
    #: it keeps something else.
    document: Mapped[str] = mapped_column(Text, nullable=False)

    #: ADR-0003 C1's ``payload``: JSON, validated against the type's model.
    #: Empty for every event type with no registered schema (ADR-0007).
    payload: Mapped[str] = mapped_column(Text, nullable=False, server_default="{}")

    __table_args__ = (
        # The gapless backstop. Allocation under BEGIN IMMEDIATE should make this
        # unreachable; it exists so that an allocation bug is a loud IntegrityError
        # rather than a silently interleaved log.
        UniqueConstraint("task_id", "seq", name="uq_events_task_seq"),
        Index("ix_events_run_id", "run_id"),
        Index("ix_events_task_id_type", "task_id", "type"),
        CheckConstraint("seq >= 1", name="seq_positive"),
        # --- the closed vocabulary, enforced by the database -----------------
        # An event type this build has never heard of is a newer writer.
        # Rejecting it here means a raw INSERT bypassing the ORM is refused too.
        CheckConstraint(
            f"type IN {_list_of(t.value for t in EventType)}",
            name="type_is_closed_vocabulary",
        ),
        # --- R-02: run_id required per event type, never per column ----------
        CheckConstraint(
            f"((type IN {_list_of(_RUN_SCOPED_TYPES)}) AND run_id IS NOT NULL)"
            f" OR ((type IN {_list_of(_TASK_LEVEL_TYPES)}) AND run_id IS NULL)",
            name="run_id_matches_event_type",
        ),
        # --- operation.* events name both a Stage and an Operation ----------
        CheckConstraint(
            f"((type IN {_list_of(_OPERATION_CONTEXT_TYPES)})"
            f" AND stage_id IS NOT NULL AND operation_id IS NOT NULL)"
            f" OR ((type IN {_list_of(_NON_OPERATION_CONTEXT_TYPES)})"
            f" AND operation_id IS NULL)",
            name="operation_context_matches_event_type",
        ),
        # --- an event that describes a change carries from/to; an
        #     annotation carries neither and must not be used to rebuild state
        CheckConstraint(
            f"((type IN {_list_of(_TRANSITION_TYPES)})"
            f" AND from_state IS NOT NULL AND to_state IS NOT NULL)"
            f" OR ((type IN {_list_of(_NON_TRANSITION_TYPES)})"
            f" AND from_state IS NULL AND to_state IS NULL)",
            name="transition_matches_event_type",
        ),
        # Must stay last: SQLAlchemy only accepts the __table_args__ dict in
        # final position. AUTOINCREMENT is what stops SQLite from ever reusing
        # an events.id, so a row deleted by hand cannot have its identity
        # silently handed to a different event.
        {"sqlite_autoincrement": True},
    )
