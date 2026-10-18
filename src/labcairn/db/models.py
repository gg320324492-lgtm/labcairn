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
    Float,
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
from labcairn.evidence.states import (
    CheckKind,
    CheckOutcome,
    EvidenceCreator,
    EvidenceKind,
    NormalizationProfile,
    VerificationStatus,
)
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


#: Characters a value may not consist of *entirely* of, for ``NonEmptyText``.
#:
#: ``NonEmptyText`` in :mod:`labcairn.sources.primitives` means *length >= 1
#: and not entirely whitespace*. ``length(trim(x)) > 0`` looks like it says
#: that and does not: SQLite's ``trim()`` removes the **space character
#: only**, so it happily accepts a tab, a newline, an NBSP and an ideographic
#: space. An earlier draft of this schema used that form, and review found 65
#: wrong-acceptances from it — one root cause across eight columns.
#:
#: Exactly the code points ``str.strip()`` removes — verified against
#: ``str.isspace()`` by ``test_the_blank_character_class_matches_python``.
#: Space is included: ``'a b'`` still matches outside the class so it is
#: accepted, while a value made entirely of spaces has nothing outside it.
#: Excluding space, as a first attempt here did, looks right and is not.
#:
#: A comment in an earlier draft said the remaining Unicode whitespace
#: "cannot be expressed in a CHECK". **That was false**, and worse than the
#: bug it documented, because it tells the next reader to stop looking: a GLOB
#: character class is one pattern term however many characters it holds. An
#: 8-point class was replaced by this one and closed the family completely.
#:
#: Written with ``chr()`` rather than escapes so the code points are visible
#: in the source instead of surviving a copy through a shell.
_NON_WHITESPACE_CODEPOINTS: Final[tuple[int, ...]] = (
    0x0009, 0x000A, 0x000B, 0x000C, 0x000D, 0x001C, 0x001D, 0x001E, 0x001F,
    0x0020, 0x0085, 0x00A0, 0x1680,
    0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006, 0x2007, 0x2008,
    0x2009, 0x200A, 0x2028, 0x2029, 0x202F, 0x205F, 0x3000,
)  # fmt: skip


def _whitespace_class() -> str:
    """A GLOB character class matching one whitespace code point (no negation)."""
    return "[" + "".join(chr(code) for code in _NON_WHITESPACE_CODEPOINTS) + "]"


def _has_content(column: str) -> str:
    """SQL for "this column holds at least one non-whitespace character"."""
    negated = "[" + chr(94) + _whitespace_class()[1:]
    return f"{column} GLOB '*{negated}*'"


def _no_edge_whitespace(column: str) -> str:
    """SQL for "this column neither begins nor ends with whitespace"."""
    cls = _whitespace_class()
    return f"{column} NOT GLOB '{cls}*' AND {column} NOT GLOB '*{cls}'"


def _a1_glob_check(column: str) -> str:
    """Render ``XlsxCellRef``'s pattern as a SQLite GLOB disjunction.

    ``XlsxCellRef`` in :mod:`labcairn.sources.locators` is
    ``^[A-Z]{1,3}[1-9][0-9]{0,6}$``, and GLOB has no bounded repetition, so
    the pattern is expanded into one alternative per (letters, digits) pair
    — 3 x 7 = 21 terms. GLOB matches the whole string, so each alternative
    is an exact shape rather than a prefix.

    Generated rather than hand-written because a hand-written approximation
    is how ``b12`` and ``B12`` end up as two rows in the same ledger, which
    is the failure ``locators.py`` names when it explains why lowercase is
    rejected rather than upcased.
    """
    alternatives = [
        f"{column} GLOB '{'[A-Z]' * letters}{'[1-9]' + '[0-9]' * (digits - 1)}'"
        for letters in range(1, 4)
        for digits in range(1, 8)
    ]
    return " OR ".join(alternatives)


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


# --------------------------------------------------------------------------- #
# sources
# --------------------------------------------------------------------------- #


class SourceRow(Base):
    """One ingested material file.

    Persists :class:`labcairn.sources.source.Source`, whose contract LC-P1-02
    froze and which LC-P1-05 left unstored -- the store held outputs
    (``artifacts``) but nothing held the inputs a report cites. There is no
    ``task_id``: a material belongs to the workspace, not to a Task, and it
    must outlive the Tasks that cite it.

    ``content_sha256`` is stored, never refreshed. ADR-0004 I4 says drift
    invalidates downstream rather than silently re-reading, and a hash that
    updated itself would make drift undetectable.
    """

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    #: See :data:`LOCAL_USER_ID`. Not authentication; the question it answers
    #: is whose material this is, so a future multi-user migration has a
    #: column to populate.
    owner_id: Mapped[str] = mapped_column(Text, nullable=False, default=LOCAL_USER_ID)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(2000), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(2000), nullable=False, unique=True)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    readability: Mapped[str] = mapped_column(String(32), nullable=False)
    #: Required non-empty when unreadable, absent otherwise. A disclosure
    #: nobody has to write is a disclosure nobody writes, so its absence is a
    #: schema error rather than a default.
    readability_disclosure: Mapped[str | None] = mapped_column(Text, nullable=True)
    identifiers: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    ingested_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        Index("ix_sources_content_sha256", "content_sha256"),
        CheckConstraint("size_bytes >= 0", name="source_size_non_negative"),
        # Closed vocabulary, mirroring ``events.type``. Without it the pairing
        # check below is one-sided: a typo like 'unreadable' would sail through
        # with no disclosure, and ADR-0004 A7 would not be enforced by the
        # database at all. An event type this build has never heard of is a
        # newer writer or a bug, and a raw INSERT bypassing the ORM is refused
        # too; the same standard applies here.
        CheckConstraint(
            "kind IN ('pdf', 'markdown', 'text', 'csv', 'xlsx', 'other')",
            name="source_kind_vocabulary",
        ),
        CheckConstraint(
            "readability IN ('readable', 'unreadable_no_ocr', 'unparseable')",
            name="source_readability_vocabulary",
        ),
        # ADR-0004 A7: "we could not look" is not "there was nothing there".
        # A disclosure attached to something we did read is a claim about
        # something that did not happen.
        CheckConstraint(
            "(readability <> 'readable') = (readability_disclosure IS NOT NULL)",
            name="source_disclosure_paired",
        ),
        # Paired is not the same as meaningful. A disclosure nobody can read is
        # the same failure the pairing exists to prevent, wearing a string.
        CheckConstraint(
            "readability_disclosure IS NULL OR " + _has_content("readability_disclosure"),
            name="source_disclosure_non_empty",
        ),
        # Defence in depth, not a second implementation of
        # ``require_workspace_relative``. The application validator is the
        # contract; this refuses the shapes that make a stored path dangerous
        # if a row is ever written by something that skipped it -- absolute,
        # parent-escaping, a Windows separator, or a redundant '.' segment.
        # A stored ``..`` is precisely what that validator refuses.
        CheckConstraint(
            "relative_path NOT GLOB '/*' AND relative_path NOT GLOB '*\\*' "
            "AND relative_path NOT GLOB '../*' AND relative_path NOT GLOB '*/../*' "
            "AND relative_path NOT GLOB '*/..' AND relative_path <> '..' "
            "AND relative_path NOT GLOB './*' AND relative_path NOT GLOB '*/./*' "
            "AND relative_path NOT GLOB '*/.' AND relative_path <> '.' "
            "AND " + _has_content("relative_path"),
            name="source_relative_path_workspace_relative",
        ),
        # The four shapes above are not the whole set. Also refused: a Windows
        # drive letter written with forward slashes (`C:win/path` has no
        # backslash to catch), an empty path segment (`papers/`, `papers//p.pdf`
        # both split to `''`), and surrounding whitespace — every one of which
        # require_workspace_relative rejects.
        CheckConstraint(
            "relative_path NOT GLOB '[A-Za-z]:*' "
            "AND relative_path NOT LIKE '%/' AND relative_path NOT LIKE '%//%' "
            "AND " + _no_edge_whitespace("relative_path"),
            name="source_relative_path_no_empty_segment",
        ),
        CheckConstraint(
            "length(content_sha256) = 64 AND content_sha256 NOT GLOB '*[^0-9a-f]*'",
            name="source_content_sha256_shape",
        ),
        CheckConstraint(_has_content("display_name"), name="source_display_name_non_empty"),
        CheckConstraint(_has_content("source_id"), name="source_id_non_empty"),
        CheckConstraint(_has_content("owner_id"), name="source_owner_id_non_empty"),
        # ``size_bytes`` is declared INTEGER, and SQLite will happily store the
        # string 'abc' in it, or convert '1e3' to 1000 without a trace. The
        # latter is what ``primitives.py`` calls the thing this project exists
        # to prevent: a payload written where a string belonged is accepted,
        # silently rewritten, and nothing downstream can tell.
        CheckConstraint("typeof(size_bytes) = 'integer'", name="source_size_bytes_is_integer"),
    )


# --------------------------------------------------------------------------- #
# source_problems


class SourceProblemRow(Base):
    """One disclosure about a material: why it could not be read, or what was
    found in it that a reader must know.

    Revision 0004 added this because every adapter produced these records and
    **nothing wrote them**. A disclosure with no destination is not a
    disclosure -- the same argument ``sources.readability_disclosure`` makes
    for itself.

    ``location`` is a not-null sentinel rather than a nullable column because
    SQLite compares NULLs as distinct inside a UNIQUE index, so a nullable
    location would let "the same whole-file problem, once per run" succeed.
    """

    __tablename__ = "source_problems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    extraction_version: Mapped[str] = mapped_column(String(64), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(String(2000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "extraction_version",
            "code",
            "location",
            name="uq_source_problems",
        ),
        Index("ix_source_problems_source_id", "source_id"),
        CheckConstraint("length(trim(detail)) > 0", name="source_problem_detail_non_empty"),
    )


# --------------------------------------------------------------------------- #
# source_texts
# --------------------------------------------------------------------------- #


class SourceTextRow(Base):
    """Extracted text for one addressable place in one material.

    ADR-0009. The key is ``(source_content_sha256, extraction_version,
    locator)``, and every part of it is load-bearing:

    * the **content hash** binds the text to the exact bytes it came from, so
      a modified file cannot inherit old text and ADR-0004's A2 fires;
    * the **extraction version** keeps a new extraction beside an old one
      rather than overwriting it, so an anchor written under the old version
      still resolves and the divergence becomes detectable rather than silent;
    * the **locator** separates the many addresses of one material.

    ``locator_key`` is a canonical, NOT NULL, indexable rendering of the typed
    locator columns beside it. SQLite treats NULLs as distinct inside a UNIQUE
    index, so a unique constraint over the nullable locator columns would not
    constrain even one row; this column is what makes the key enforceable. It
    is derived, never the source of truth -- ADR-0004 rejects prose locators
    precisely because they cannot be re-derived from anything, and this one is
    re-derivable from typed columns that can be.
    """

    __tablename__ = "source_texts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    #: The material's content hash at extraction time. Deliberately *not* a
    #: foreign key to ``sources.content_sha256``: text outlives the row it was
    #: extracted from, because a replaced file must not orphan the text that
    #: existing anchors still resolve against.
    source_content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Which extraction produced this. Derived from the library version and an
    #: adapter revision, not a constant somebody has to remember to bump.
    extraction_version: Mapped[str] = mapped_column(String(64), nullable=False)
    locator_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    #: Canonical rendering of the typed columns below. See the class docstring.
    locator_key: Mapped[str] = mapped_column(String(2000), nullable=False)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_name: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    sheet_name: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    cell_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    #: The extracted text. Wrapped in
    #: :class:`labcairn.security.untrusted.UntrustedText` on the way *out*, not
    #: on the way in: storage is not what makes material untrusted, and
    #: dropping the wrapper at the database boundary would defeat ADR-0003 C6.
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "source_content_sha256",
            "extraction_version",
            "locator_key",
            name="uq_source_texts_address",
        ),
        Index("ix_source_texts_sha", "source_content_sha256"),
        # Closed vocabulary, same standard as ``events.type``. Every shape
        # CHECK below is an implication keyed on ``locator_kind``, so an
        # unrecognised kind satisfies all of them vacuously and every typed
        # column can be NULL. 'banana', 'PDF' and '' must not be storable.
        # COMPUTATION is a real LocatorKind but has no extracted text -- a
        # derived number is addressed by the operator that produced it, so it
        # belongs in no row of this table.
        CheckConstraint(
            "locator_kind IN ('pdf', 'text', 'csv', 'xlsx')",
            name="source_texts_kind_vocabulary",
        ),
        # Exactly the typed columns each locator kind defines, and no others.
        # A half-populated locator resolves to the wrong thing silently, which
        # is the failure this table exists to make impossible.
        #
        # These must be **exhaustive**: an earlier draft constrained only the
        # columns a kind *uses*, so a row could claim to be a text locator and
        # a PDF page and a CSV cell at once -- a row no conforming code can
        # produce and none can consume. Each check now names every column.
        CheckConstraint(
            "locator_kind <> 'pdf' OR (page IS NOT NULL AND line_start IS NULL "
            "AND line_end IS NULL AND section IS NULL AND row_number IS NULL "
            "AND column_name IS NULL AND sheet_name IS NULL AND cell_ref IS NULL)",
            name="source_texts_pdf_shape",
        ),
        CheckConstraint(
            "locator_kind <> 'text' OR (line_start IS NOT NULL AND page IS NULL "
            "AND row_number IS NULL AND column_name IS NULL AND sheet_name IS NULL "
            "AND cell_ref IS NULL)",
            name="source_texts_text_shape",
        ),
        CheckConstraint(
            "locator_kind <> 'csv' OR (row_number IS NOT NULL AND column_name IS NOT NULL "
            "AND page IS NULL AND line_start IS NULL AND line_end IS NULL "
            "AND section IS NULL AND sheet_name IS NULL AND cell_ref IS NULL)",
            name="source_texts_csv_shape",
        ),
        CheckConstraint(
            "locator_kind <> 'xlsx' OR (sheet_name IS NOT NULL AND cell_ref IS NOT NULL "
            "AND page IS NULL AND line_start IS NULL AND line_end IS NULL "
            "AND section IS NULL AND row_number IS NULL AND column_name IS NULL)",
            name="source_texts_xlsx_shape",
        ),
        # Every kind pins line_end and section to its own columns. text may
        # carry them; nothing else may.
        # NOTE: these two became wholly implied once the shape checks above
        # were made exhaustive. They are kept as belt and braces for
        # readability, not because they constrain anything a shape check does
        # not — a test cannot distinguish them, which is why this says so
        # rather than leaving two constraints looking load-bearing.
        CheckConstraint(
            "line_end IS NULL OR locator_kind = 'text'",
            name="source_texts_line_end_is_text",
        ),
        CheckConstraint(
            "section IS NULL OR locator_kind = 'text'",
            name="source_texts_section_is_text",
        ),
        CheckConstraint(
            "section IS NULL OR " + _has_content("section"),
            name="source_texts_section_non_empty",
        ),
        CheckConstraint(
            "column_name IS NULL OR " + _has_content("column_name"),
            name="source_texts_column_name_non_empty",
        ),
        CheckConstraint(
            "sheet_name IS NULL OR " + _has_content("sheet_name"),
            name="source_texts_sheet_name_non_empty",
        ),
        # The key column of the key table. It had no shape constraint at all,
        # so '', 'not-a-hash' and '../../etc/passwd' were storable -- and since
        # the UNIQUE is (sha, version, locator_key), two rows with '' and
        # different versions coexist as "the same content", which is the exact
        # guarantee this design rests on.
        CheckConstraint(
            "length(source_content_sha256) = 64 AND source_content_sha256 NOT GLOB '*[^0-9a-f]*'",
            name="source_texts_content_sha256_shape",
        ),
        # Declared INTEGER, but SQLite stores 'abc' and silently converts
        # '1e3' to 1000. Comparisons do not help: INTEGER sorts before TEXT,
        # so 'abc' >= 1 is TRUE and every `>= 1` check above is bypassable
        # with a string. typeof() is the only thing that distinguishes them.
        CheckConstraint(
            "(page IS NULL) OR typeof(page) = 'integer'",
            name="source_texts_page_is_integer",
        ),
        CheckConstraint(
            "(line_start IS NULL) OR typeof(line_start) = 'integer'",
            name="source_texts_line_start_is_integer",
        ),
        CheckConstraint(
            "(line_end IS NULL) OR typeof(line_end) = 'integer'",
            name="source_texts_line_end_is_integer",
        ),
        CheckConstraint(
            "(row_number IS NULL) OR typeof(row_number) = 'integer'",
            name="source_texts_row_number_is_integer",
        ),
        # XlsxCellRef's pattern, expanded into GLOB alternatives. Without it
        # 'b2', '$B$2', 'B0', 'Sheet1!A1' and 'BB2' are all storable, and this
        # table *is* the ledger locators.py warns would make seen_cells() lie.
        CheckConstraint(_a1_glob_check("cell_ref"), name="source_texts_cell_ref_a1"),
        CheckConstraint(
            _has_content("locator_key") + " AND " + _has_content("extraction_version"),
            name="source_texts_key_non_empty",
        ),
        CheckConstraint(
            "length(text_sha256) = 64 AND text_sha256 NOT GLOB '*[^0-9a-f]*'",
            name="source_texts_text_sha256_shape",
        ),
        # Bounded by what a consumer can accept: UntrustedText refuses above
        # two million characters, so a longer row could be written and then
        # never read back through the only sanctioned path.
        CheckConstraint(
            "length(text) <= 2000000",
            name="source_texts_text_length",
        ),
        CheckConstraint("page IS NULL OR page >= 1", name="source_texts_page_positive"),
        CheckConstraint("row_number IS NULL OR row_number >= 1", name="source_texts_row_positive"),
        CheckConstraint(
            "line_start IS NULL OR (line_start >= 1 "
            "AND (line_end IS NULL OR line_end >= line_start))",
            name="source_texts_line_range",
        ),
    )


# ---------------------------------------------------------------------------
# LC-P1-09 — the evidence ledger
# ---------------------------------------------------------------------------
# ADR-0004 Contract 1 types these records in Pydantic, and every invariant
# below is already a validator on ``labcairn.evidence.record``. The CHECK
# constraints are not a second opinion on those rules; they are the same rules
# where they *can* be expressed, so a row written by a SQL client, a migration,
# or a future contributor who never imports the Pydantic model is refused the
# same way. ``source_texts`` sets the precedent: closed vocabularies and a
# derived canonical column that exists so a constraint can see what a nullable
# one could not.
#
# What is deliberately NOT in the schema, and why:
#
# * **Append-only-ness of the log.** No CHECK can see that a row was not
#   rewritten; only the writer and its tests can establish that.
# * **"at least one resolving anchor".** A CHECK cannot read a join table, and
#   the alternative -- a denormalised count that could disagree with the join
#   table -- buys constraint coverage at the price of a second source of truth.
#   So ``anchor_key`` below is the trade ``source_texts.locator_key`` already
#   makes: a canonical, re-derivable rendering used *for* the constraint, with
#   the join table remaining authoritative.
# * **The state machine.** ADR-0004 Contract 2's transitions describe a record
#   moving between states over time, which is a relation between two versions of
#   a row rather than a property of one.


class EvidenceAnchorRow(Base):
    """One anchor cited by one evidence record.

    A join table rather than a column, because ``anchor_ids`` is an ordered
    tuple and order carries meaning: the first anchor is the primary one, and a
    report that cites the wrong anchor first is citing something real in the
    wrong role. ``position`` is that order, dense from 0, so a gap means a bug
    rather than a choice.
    """

    __tablename__ = "evidence_anchors"

    #: Surrogate key, as ``source_problems`` uses. The natural key is the
    #: (evidence_id, position) pair below, carried as a UNIQUE constraint
    #: rather than as the primary key, so the two can differ in one place only.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evidence_id: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    anchor_id: Mapped[str] = mapped_column(String(200), nullable=False)

    __table_args__ = (
        # The anchor table is not created by this work order, so a foreign key
        # to it is not available yet. It is deliberately NOT faked with a loose
        # reference: an anchor id naming nothing is precisely a fabricated
        # source, and C1 is what must catch it. A foreign key here would make
        # the row unstorable instead, turning a checkable failure into a
        # constraint error the caller cannot read.
        UniqueConstraint("evidence_id", "position", name="uq_evidence_anchors_position"),
        # Duplicates are not meaningful, and ADR-0004's validator rejects them
        # on the record. This makes the same refusal true of the rows.
        UniqueConstraint("evidence_id", "anchor_id", name="uq_evidence_anchors_anchor"),
        CheckConstraint("position >= 0", name="evidence_anchors_position_non_negative"),
        CheckConstraint(
            "length(anchor_id) > 0 AND length(evidence_id) > 0", name="evidence_anchors_ids_present"
        ),
        Index("ix_evidence_anchors_anchor", "anchor_id"),
    )


class EvidenceRecordRow(Base):
    """A claim, a number or a result, with the provenance it will be judged on.

    ADR-0004 Contract 1. The columns mirror
    :class:`~labcairn.evidence.record.EvidenceRecord` field for field, and the
    CHECK constraints are the SQL-expressible half of its validators.
    """

    __tablename__ = "evidence_records"

    evidence_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    task_id: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)

    #: ``None`` for a numeric record, and required to say so. In Pydantic the
    #: key must be *present* even when its value is ``None``; in a row every
    #: column is present by construction, so a nullable column is the faithful
    #: shape of that rule.
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(200), nullable=True)
    #: Never defaulted to 0.0 anywhere. An undeclared tolerance is not an
    #: exact-match requirement, and C3 returns ``indeterminate`` without one.
    tolerance: Mapped[float | None] = mapped_column(Float, nullable=True)

    #: Canonical rendering of this record's ``evidence_anchors``, so the "a
    #: located record cites something" rule is expressible in a CHECK. See the
    #: module comment on why this is a rendering rather than a count.
    anchor_key: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_span: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_span_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Hash of the source as read at extraction. Compared against the index,
    #: never refreshed: ADR-0004 I4 invalidates on drift rather than silently
    #: re-reading.
    source_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by_id: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    #: Set when a newer record replaces this one. The old row is kept, not
    #: deleted, so the history of a claim stays auditable.
    superseded_by: Mapped[str | None] = mapped_column(String(200), nullable=True)

    __table_args__ = (
        UniqueConstraint("task_id", "extracted_span_sha256", name="uq_evidence_task_span"),
        Index("ix_evidence_records_status", "status"),
        Index("ix_evidence_records_task", "task_id"),
        CheckConstraint(
            f"kind IN {sql_string_list(k.value for k in EvidenceKind)}",
            name="evidence_records_kind_vocabulary",
        ),
        CheckConstraint(
            f"status IN {sql_string_list(s.value for s in VerificationStatus)}",
            name="evidence_records_status_vocabulary",
        ),
        CheckConstraint(
            f"created_by IN {sql_string_list(c.value for c in EvidenceCreator)}",
            name="evidence_records_creator_vocabulary",
        ),
        # ADR-0004 Contract 1's kind discipline. A sentence attached to a number
        # is a second claim no check will ever look at, so the two are mutually
        # exclusive rather than merely discouraged.
        CheckConstraint(
            "(kind <> 'numeric' OR (text IS NULL AND value IS NOT NULL AND unit IS NOT NULL)) "
            "AND (kind = 'numeric' OR (text IS NOT NULL AND value IS NULL "
            "AND unit IS NULL AND tolerance IS NULL))",
            name="evidence_records_kind_fields",
        ),
        # Quoted text without its hash cannot be checked for drift; a hash
        # without the text cannot be shown to anyone.
        CheckConstraint(
            "(extracted_span IS NULL) = (extracted_span_sha256 IS NULL)",
            name="evidence_records_span_all_or_nothing",
        ),
        # Everything past ``planned`` claims to have been located, so it must
        # carry what a location is made against: the quoted span and its hash,
        # the source hash it was read from, and at least one anchor. This is the
        # checkable half of ADR-0004 Contract 2 -- whether the anchor *resolves*
        # is C1's call, and deliberately not this constraint's.
        CheckConstraint(
            "status = 'planned' OR (extracted_span IS NOT NULL "
            "AND extracted_span_sha256 IS NOT NULL AND source_content_hash IS NOT NULL "
            "AND anchor_key <> '[]')",
            name="evidence_records_located_past_planned",
        ),
        CheckConstraint(
            "length(evidence_id) > 0 AND length(task_id) > 0 AND length(created_by_id) > 0",
            name="evidence_records_ids_present",
        ),
        CheckConstraint(
            "(extracted_span_sha256 IS NULL OR (length(extracted_span_sha256) = 64 "
            "AND extracted_span_sha256 NOT GLOB '*[^0-9a-f]*')) "
            "AND (source_content_hash IS NULL OR (length(source_content_hash) = 64 "
            "AND source_content_hash NOT GLOB '*[^0-9a-f]*'))",
            name="evidence_records_hash_shape",
        ),
        # A tolerance is a declared comparison width, so a negative one would be
        # a comparison no number could satisfy.
        CheckConstraint("tolerance IS NULL OR tolerance >= 0", name="evidence_records_tolerance"),
    )


class VerificationRecordRow(Base):
    """One entry in a record's append-only verification log.

    The log is a relation, not a column: it grows, it is ordered, and a report
    reads it as a sequence of dated verdicts with named checkers. ``seq`` is
    that order, dense from 1, because a gap in an audit trail is a defect.
    """

    __tablename__ = "verification_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evidence_id: Mapped[str] = mapped_column(String(200), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Named ``check_kind``, not ``check``: ``check`` is a SQL keyword, so a
    #: CHECK constraint body referring to it -- ``check IN ('c1', ...)`` -- is a
    #: syntax error, since a body cannot quote its own column. The DDL quotes
    #: the column definition happily; it is the three constraints below that
    #: cannot. Renaming costs one word in the storage mapping and saves every
    #: future hand-written query from the same trap.
    check_kind: Mapped[str] = mapped_column(String(8), nullable=False)
    checker_id: Mapped[str] = mapped_column(String(200), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    normalization_profile: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint("evidence_id", "seq", name="uq_verification_records_seq"),
        CheckConstraint(
            f"check_kind IN {sql_string_list(c.value for c in CheckKind)}",
            name="verification_records_check_vocabulary",
        ),
        CheckConstraint(
            f"outcome IN {sql_string_list(o.value for o in CheckOutcome)}",
            name="verification_records_outcome_vocabulary",
        ),
        # ADR-0004 I2. There is no seventh state that could hold a C4 pass, so
        # the combination is unrepresentable rather than discouraged.
        CheckConstraint(
            "check_kind <> 'c4' OR outcome = 'not_checked'",
            name="verification_records_c4_never_passes",
        ),
        # "How lenient was this comparison" is a question a reader of the log
        # must be able to answer. An absent profile on C2 answers it as
        # "unknown", which is not "exact"; a profile on a check that compares
        # no text is a claim about a comparison that did not happen.
        CheckConstraint(
            "(check_kind = 'c2') = (normalization_profile IS NOT NULL)",
            name="verification_records_profile_belongs_to_c2",
        ),
        CheckConstraint(
            f"normalization_profile IS NULL OR normalization_profile IN "
            f"{sql_string_list(p.value for p in NormalizationProfile)}",
            name="verification_records_profile_vocabulary",
        ),
        CheckConstraint("seq >= 1", name="verification_records_seq_positive"),
        CheckConstraint(
            "length(evidence_id) > 0 AND length(checker_id) > 0 AND length(detail) > 0",
            name="verification_records_ids_present",
        ),
        Index("ix_verification_records_evidence", "evidence_id"),
    )
