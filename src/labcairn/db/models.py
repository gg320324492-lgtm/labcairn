"""The fifteen tables that make SQLite the task authority.

Fifteen is not a claim to be trusted: ``tests/test_evidence_schema.py``'s parity
test walks ``Base.metadata`` and the migrated schema independently, and that is
what catches a table added to one and not the other. It is written here so a
reader knows the scope of the file, and it has been wrong before -- it still said
"eight" after LC-P1-08 and T01 added six tables -- because nothing recomputed it.

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


def _locator_kind_glob_check() -> str:
    """SQL restricting ``locator_key`` to the kinds LabCairn can resolve.

    A rendered key opens with its length-prefixed discriminator --
    ``k=3:csv|``, ``k=4:xlsx|``, ``k=4:docx|`` -- so the prefix is
    *generated* from the kind rather than written out, for two reasons that
    each cost a bug:

    * the prefix length is the kind's spelling length and is not constant
      (``pdf`` and ``csv`` are 3, ``text``, ``xlsx`` and ``docx`` are 4). A
      hand-written ``k=3:`` accepted the first two and refused the others;
    * the length prefix is exactly what makes the key injective, so a
      constraint that ignores it is not constraining the thing the key is for.

    Generated here for the reason :func:`_a1_glob_check` generates its 21
    alternatives: a hand-written list of GLOBs is a second spelling of a
    closed set, and closed sets are where the second spelling drifts.

    **No ``?`` wildcard, and that is not an oversight.** ``locator_key GLOB
    'k=?:csv|*'`` reads better and cannot be used: SQLAlchemy reads ``:csv`` as
    a bind parameter, so all the alternatives compiled to the literal
    ``'k=?NULL|*'`` and the table accepted nothing. The parity test passed
    through it, because the migration and the ORM were mangled identically --
    a test comparing two texts cannot catch both being wrong. Only writing a
    row that must be refused catches it.

    **LC-P2-07 added ``docx``**, which is the fifth kind rather than a
    widening of the four. It is a separate kind because a Word address is
    structurally different: it names a package part and an element path
    rather than a page or a cell, and it carries the **view** the character
    range is in -- which is what makes the same range mean different
    characters in the accepted and the rejected text.
    """
    return " OR ".join(
        f"locator_key GLOB 'k={len(kind)}:{kind}|*'"
        for kind in ("pdf", "text", "csv", "xlsx", "docx")
    )


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
    #: The ids of the materials the Task is bound to, as SourceId strings.
    #: Each id is minted from the material's location, so an edited file keeps
    #: its identity; the content hash is what detects drift, and it lives on
    #: the source row and on the receipt's chain, not here.
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
    #: LC-P2-07. The DOCX address: which package part, which element in
    #: it, which view, and the character range within that element's text.
    #: ``view`` is a column and not an implicit default because the same
    #: range means different characters in the accepted and the rejected
    #: text, and an address that could mean either is not an address.
    docx_part: Mapped[str | None] = mapped_column(String(200), nullable=True)
    docx_element_path: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    docx_view: Mapped[str | None] = mapped_column(String(16), nullable=True)
    docx_char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    docx_char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
            "locator_kind IN ('pdf', 'text', 'csv', 'xlsx', 'docx')",
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
            "AND column_name IS NULL AND sheet_name IS NULL AND cell_ref IS NULL "
            "AND docx_part IS NULL AND docx_element_path IS NULL AND docx_view IS NULL "
            "AND docx_char_start IS NULL AND docx_char_end IS NULL)",
            name="source_texts_pdf_shape",
        ),
        CheckConstraint(
            "locator_kind <> 'text' OR (line_start IS NOT NULL AND page IS NULL "
            "AND row_number IS NULL AND column_name IS NULL AND sheet_name IS NULL "
            "AND cell_ref IS NULL AND docx_part IS NULL AND docx_element_path IS NULL "
            "AND docx_view IS NULL AND docx_char_start IS NULL "
            "AND docx_char_end IS NULL)",
            name="source_texts_text_shape",
        ),
        CheckConstraint(
            "locator_kind <> 'csv' OR (row_number IS NOT NULL AND column_name IS NOT NULL "
            "AND page IS NULL AND line_start IS NULL AND line_end IS NULL "
            "AND section IS NULL AND sheet_name IS NULL AND cell_ref IS NULL "
            "AND docx_part IS NULL AND docx_element_path IS NULL AND docx_view IS NULL "
            "AND docx_char_start IS NULL AND docx_char_end IS NULL)",
            name="source_texts_csv_shape",
        ),
        CheckConstraint(
            "locator_kind <> 'xlsx' OR (sheet_name IS NOT NULL AND cell_ref IS NOT NULL "
            "AND page IS NULL AND line_start IS NULL AND line_end IS NULL "
            "AND section IS NULL AND row_number IS NULL AND column_name IS NULL "
            "AND docx_part IS NULL AND docx_element_path IS NULL AND docx_view IS NULL "
            "AND docx_char_start IS NULL AND docx_char_end IS NULL)",
            name="source_texts_xlsx_shape",
        ),
        # LC-P2-07. A DOCX address names a package part, an element path in
        # it, the view the range is in, and the range itself. The view is
        # constrained to the two ADR-0014 D4 views because a third would be
        # an address that resolves to nothing.
        #
        # The character range is optional -- absent means the whole element --
        # and both endpoints are set or neither, exactly as the PDF locator
        # requires. A one-ended range cannot be located, and inferring the
        # missing end would be the silent correction LC-P1-02 forbids.
        CheckConstraint(
            "locator_kind <> 'docx' OR (docx_part IS NOT NULL "
            "AND docx_element_path IS NOT NULL AND docx_view IS NOT NULL "
            "AND docx_view IN ('accepted', 'rejected') "
            "AND ((docx_char_start IS NULL AND docx_char_end IS NULL) "
            "OR (docx_char_start IS NOT NULL AND docx_char_end IS NOT NULL "
            "AND docx_char_end >= docx_char_start)) "
            "AND page IS NULL AND line_start IS NULL AND line_end IS NULL "
            "AND section IS NULL AND row_number IS NULL AND column_name IS NULL "
            "AND sheet_name IS NULL AND cell_ref IS NULL)",
            name="source_texts_docx_shape",
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


class SourceAnchorRow(Base):
    """One :class:`~labcairn.sources.source.SourceAnchor`, persisted.

    This is the *address* half of a citation. ``EvidenceAnchorRow`` below is the
    *reference* half -- which anchors one record cites, in what order -- and the
    two are easy to confuse, so: this table is what an anchor **is**, that one is
    who **points at** it. C1 needs this one, because a record carries
    ``anchor_ids`` as bare strings and cannot reach a locator without it.

    **The locator is one column, not eight.** ``source_texts`` stores the
    rendered ``locator_key`` *and* the typed locator columns, and nothing in
    that schema requires the two to agree. Storing both here would have been
    consistent with that precedent and wrong: :meth:`load_anchor` would have to
    pick which to rebuild the anchor from, and picking wrong does not raise --
    it yields a *different, valid* address, which C1 then resolves successfully
    against the wrong page. That is ADR-0004 A1's prohibition (no nearest-page
    fallback) arriving by a route nobody was watching.

    So ``locator_key`` is the whole locator, and the union discriminator is its
    leading component rather than a column of its own::

        k=3:pdf|p=1:4
        k=3:csv|r=2:12|c=4:mean

    ``split_locator_key`` hands the ``k`` back like any other field, so nothing
    is left that could fall out of step. ``kind`` is still a column because it is
    not a locator fact: it records what the anchor is *for* (quotation, numeric,
    structural, absence_scan) and never appears in the key.
    """

    __tablename__ = "source_anchors"

    #: Caller-minted, not a row number: a record may cite an anchor made in an
    #: earlier run, so identity cannot depend on insertion order.
    anchor_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    locator_key: Mapped[str] = mapped_column(String(2000), nullable=False)
    #: The source's hash **as it was when this anchor was made**. C1 compares
    #: it against the current hash; nothing ever refreshes it (ADR-0004 I4),
    #: which is why it is stored rather than joined through ``sources``.
    bound_source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    excerpt_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)

    __table_args__ = (
        # Closed vocabulary, same standard as ``events.type`` and
        # ``source_texts``: an unrecognised value must be refused rather than
        # coerced, because a coerced kind reconstructs an anchor nobody made.
        CheckConstraint(
            "kind IN ('quotation', 'numeric', 'structural', 'absence_scan')",
            name="source_anchors_kind_vocabulary",
        ),
        # The locator's kind is the key's leading `k=` component, generated by
        # the length prefix's own rule rather than written out. See
        # _locator_kind_glob_check for why a `?` wildcard cannot be used here.
        CheckConstraint(
            _locator_kind_glob_check(),
            name="source_anchors_locator_key_vocabulary",
        ),
        CheckConstraint(
            "length(bound_source_sha256) = 64 AND bound_source_sha256 NOT GLOB '*[^0-9a-f]*'",
            name="source_anchors_bound_sha256_shape",
        ),
        CheckConstraint(
            "excerpt_sha256 IS NULL OR (length(excerpt_sha256) = 64 "
            "AND excerpt_sha256 NOT GLOB '*[^0-9a-f]*')",
            name="source_anchors_excerpt_sha256_shape",
        ),
        # '' as a locator_key is a storable address that resolves to nothing --
        # the defect 0005 found in source_texts.
        CheckConstraint(
            "length(locator_key) > 0 AND length(anchor_id) > 0 AND length(source_id) > 0",
            name="source_anchors_ids_present",
        ),
        # C1 resolves by id on every check, so this is the table's only hot path.
        Index("ix_source_anchors_source", "source_id"),
    )


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
        # No foreign key to ``source_anchors``, even though revision 0007 now
        # creates it. Deliberate, and the reason is A12 rather than sequencing:
        # an anchor id naming nothing is precisely a fabricated source, and C1
        # is what must catch it. A foreign key would make the row unstorable
        # instead, turning a checkable failure into a constraint error the
        # caller cannot read -- and it would refuse the *write* rather than
        # report the *finding*, which are different acts.
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


# --------------------------------------------------------------------------- #
# LC-P2-08: the paper project and the version graph
# --------------------------------------------------------------------------- #


class PaperProjectRow(Base):
    """One manuscript — the body of material a version graph hangs from.

    **A project is not a Task.** Phase 1's ``tasks`` table owns *work*; a
    paper project owns *material*, and the material outlives the work that
    read it. The same reason ``sources`` has no ``task_id``: a material
    belongs to a workspace, not to a Task, and it must outlive the Tasks
    that cite it.

    **``subject_pseudonym`` is not the author's name.** ADR-0015 D5 keeps a
    person's name apart from the material and the analysis; this table
    holds the pseudonym and points at the name held elsewhere. A row with
    a name in it would defeat that separation, and the separation is what
    makes the material shareable with an annotator who is not the author.

    **``consent_ref`` is a reference and not a permission.** It names the
    grant that LC-P2-06 will resolve; it grants nothing by being present.
    A project with no grant is **readable as a project and unreadable as
    material**, and those are two different states rather than one state
    with a missing field.
    """

    __tablename__ = "paper_projects"

    #: Caller-minted, not a row number: a project may be cited from an
    #: earlier run, so identity cannot depend on insertion order.
    project_id: Mapped[str] = mapped_column(Text, nullable=False, primary_key=True)
    #: The workspace the material lives in. A project's material is in a
    #: workspace, and the workspace is what the permission boundary is
    #: checked against.
    workspace_id: Mapped[str] = mapped_column(Text, nullable=False)
    #: A pseudonym for the subject. **Never** the author's name — see the
    #: class docstring.
    subject_pseudonym: Mapped[str] = mapped_column(String(200), nullable=False)
    #: The reference LC-P2-06 resolves to a grant. ``None`` means no grant
    #: has been recorded, and the material is not readable.
    consent_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "length(project_id) > 0 AND length(workspace_id) > 0 AND length(subject_pseudonym) > 0",
            name="paper_projects_ids_present",
        ),
        CheckConstraint(
            "consent_ref IS NULL OR length(consent_ref) > 0",
            name="paper_projects_consent_ref_non_empty",
        ),
    )


class PaperVersionRow(Base):
    """One version of a manuscript — a node in the version graph.

    **There is no ``parent_id`` column, and that is the point.** The
    teacher's process contains **parallel branches**: a student sent two
    different revised drafts and the advisor replied to both. A column that
    holds one parent cannot hold two, so the parent lives in
    :class:`VersionEdgeRow` and the graph can branch.

    **``version_label_raw`` is kept verbatim and is not evidence.** It is
    whatever the author's file name said — ``最终版2.docx``, ``投稿版.docx``
    — and the design says plainly that such a name is not a statement about
    which is newer. It is kept because a person reading the archive needs to
    see what the file was called, not because it decides anything.

    **``status`` is ``unresolved`` until the version's place in the sequence
    is established.** An unresolved version is **listed**: it exists, it is
    material in the project, and hiding it because its parent is unknown
    would make the archive look complete when it is not.
    """

    __tablename__ = "paper_versions"

    version_id: Mapped[str] = mapped_column(Text, nullable=False, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("paper_projects.project_id", ondelete="CASCADE"),
        nullable=False,
    )
    #: The ingested file this version came from. A version with no file is
    #: not a version; the bytes are what the version *is*.
    source_id: Mapped[str] = mapped_column(
        Text, ForeignKey("sources.source_id", ondelete="CASCADE"), nullable=False
    )
    #: **The bytes as they were when the version was recorded.**
    #:
    #: The row above names the *file*, and the file's bytes move: re-ingesting
    #: it after an edit changes what the ledger holds under that id. A version
    #: that took its identity from the file would move with it — and two files
    #: with the same bytes are one version, which a moving identity cannot
    #: hold. So the hash is recorded here, once, when the version is written,
    #: and the version is that set of bytes for ever.
    #:
    #: Nullable because a column added by a later revision cannot be NOT NULL
    #: without a default that would be a lie (see revision 0012), and because
    #: the reader refuses a row that carries no hash rather than reading it as
    #: a version of unknown bytes.
    source_content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: The label the author's file name gave, kept verbatim. **Not
    #: evidence of order** — see the class docstring.
    version_label_raw: Mapped[str] = mapped_column(String(2000), nullable=False)
    #: The stage the system inferred, and ``unknown`` when it inferred
    #: nothing. A closed vocabulary, because a stage that could hold any
    #: string is a stage that carries no information.
    stage_candidate: Mapped[str] = mapped_column(String(32), nullable=False)
    #: ``resolved`` or ``unresolved``.
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)

    __table_args__ = (
        Index("ix_paper_versions_project", "project_id"),
        CheckConstraint(
            "length(version_id) > 0 AND length(project_id) > 0 AND length(source_id) > 0",
            name="paper_versions_ids_present",
        ),
        CheckConstraint(
            "stage_candidate IN ('draft', 'advisor_reviewed', 'submitted', "
            "'camera_ready', 'unknown')",
            name="paper_versions_stage_vocabulary",
        ),
        CheckConstraint(
            "status IN ('resolved', 'unresolved')",
            name="paper_versions_status_vocabulary",
        ),
    )


class VersionEdgeRow(Base):
    """A directed relationship between two versions: parent to child.

    **Three separate facts, and conflating any two of them is the
    failure this table exists to make impossible.**

    ================ ==================================================
    ``source``        **how** the relationship was established —
                      ``evidence``, ``human`` or ``model``.
    ``confidence``    how strong the evidence is — **a number**, and not
                      a decision.
    ``accepted_by``   **who** accepted it — ``None`` until a person does.
    ================ ==================================================

    **A similarity score may never silently decide an order.** So an
    ``evidence`` edge with a confidence of 0.99 is still **unaccepted**, and
    the version graph reports it as a proposal. A ``human`` edge records
    who accepted it, and that is what makes it settled.

    **The constraint is the way round that is easy to get backwards.** An
    edge that *claims* an acceptance must name **who** accepted it — that is
    a human decision with nobody behind it, and it is refused. An edge with
    no acceptor is not refused: it is simply unaccepted, and that is the
    state a proposal is in.

    **A correction is a new version of the edge, not an overwrite.** The
    project's rule is that a human revision produces a new version rather
    than silently replacing what was there, and ``edge_version`` and
    ``superseded_by`` carry that: the previous edge stays readable.
    """

    __tablename__ = "version_edges"

    edge_id: Mapped[str] = mapped_column(Text, nullable=False, primary_key=True)
    project_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("paper_projects.project_id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_version_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("paper_versions.version_id", ondelete="CASCADE"),
        nullable=False,
    )
    child_version_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("paper_versions.version_id", ondelete="CASCADE"),
        nullable=False,
    )
    #: **How** the relationship was established. ``evidence`` is a
    #: proposal; ``human`` is a decision; ``model`` is a proposal the system
    #: made and no person has accepted.
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    #: How strong the evidence is. **A number, not a decision.**
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    #: What supports the edge, as text. A reader must be able to see why.
    #:
    #: **A list of strings, not of objects.** The contract carries
    #: ``evidence_spans: tuple[str, ...]``, and the column is JSON, so the
    #: annotation is the only thing that says what a row holds. It said
    #: ``list[dict[str, Any]]`` before the version graph had a writer, and
    #: that was a description of nothing: the contract's spans are text, and
    #: a reader of this table would have been told to expect records.
    evidence_spans: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    #: **Who** accepted it. ``None`` while the edge is a proposal.
    accepted_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    #: The edge's own revision number, for corrections.
    edge_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    #: The edge this one corrects, when it is a correction.
    superseded_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)

    __table_args__ = (
        Index("ix_version_edges_child", "child_version_id"),
        Index("ix_version_edges_project", "project_id"),
        CheckConstraint(
            "length(edge_id) > 0 AND length(project_id) > 0 "
            "AND length(parent_version_id) > 0 AND length(child_version_id) > 0",
            name="version_edges_ids_present",
        ),
        # A version cannot be its own parent. That is not a self-loop to be
        # tolerated; it is a contradiction, and the schema says so rather
        # than letting the application layer decide.
        CheckConstraint(
            "parent_version_id <> child_version_id",
            name="version_edges_not_self_parent",
        ),
        CheckConstraint(
            "source IN ('evidence', 'human', 'model')",
            name="version_edges_source_vocabulary",
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="version_edges_confidence_in_range",
        ),
        CheckConstraint(
            "edge_version >= 1",
            name="version_edges_version_positive",
        ),
        # **An edge that claims an acceptance names who accepted it.** An
        # ``accepted_by`` with no acceptor is a human decision with nobody
        # behind it, and a proposal wearing a person's name is the same
        # forgery by another route. The absence of an acceptor is NOT an
        # error -- that is what a proposal looks like -- and the two are
        # told apart by this constraint rather than by the application
        # layer's discretion.
        CheckConstraint(
            "(accepted_by IS NULL AND accepted_at IS NULL) OR "
            "(accepted_by IS NOT NULL AND length(accepted_by) > 0 "
            "AND accepted_at IS NOT NULL)",
            name="version_edges_acceptance_names_an_acceptor",
        ),
    )


class VersionEdgeRejectionRow(Base):
    """The record of a refusal: a person looked at a proposed edge and said no.

    **A refusal is not the absence of a row.** The other two outcomes leave
    their own mark on the graph — an acceptance is the edge with an acceptor,
    a correction is a second edge with the proposal pointing at it — and a
    rejection leaves nothing, because there is no relationship to record. A
    proposal that was looked at and turned down would otherwise be
    indistinguishable from a proposal nobody has looked at, and the archive
    would propose it again having learned nothing from the refusal.

    **So the refusal is a row of its own**, and it says who decided, when,
    why, and about which proposal. The proposal it names stays in the graph:
    the refusal is a fact about the review, not a deletion of the thing that
    was reviewed.

    **The edge is not deleted with the refusal.** The foreign key cascades
    only if the *edge* is deleted, and nothing deletes edges — a correction
    writes a second one — so the record of a refusal outlives the review it
    is about rather than vanishing with it.
    """

    __tablename__ = "version_edge_rejections"

    #: Caller-minted, not a row number: a refusal is cited from a later run.
    rejection_id: Mapped[str] = mapped_column(Text, nullable=False, primary_key=True)
    #: The proposal that was refused. It stays in the graph.
    edge_id: Mapped[str] = mapped_column(
        Text, ForeignKey("version_edges.edge_id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        Text, ForeignKey("paper_projects.project_id", ondelete="CASCADE"), nullable=False
    )
    #: Who decided. A refusal with nobody behind it is not a refusal anybody
    #: made.
    decided_by: Mapped[str] = mapped_column(String(200), nullable=False)
    #: When they decided.
    decided_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    #: Why, in their words. Empty is allowed; the refusal is what matters.
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)

    __table_args__ = (
        Index("ix_version_edge_rejections_edge", "edge_id"),
        CheckConstraint(
            "length(rejection_id) > 0 AND length(edge_id) > 0 "
            "AND length(project_id) > 0 AND length(decided_by) > 0",
            name="version_edge_rejections_ids_present",
        ),
    )


# --------------------------------------------------------------------------- #
# LC-P2-06: the access grant table
# --------------------------------------------------------------------------- #


class AccessGrantRow(Base):
    """One permission, granted to somebody, for one purpose and one place.

    **This table holds only grants.** There is no row shape that means
    "denied", and there is no ``permitted`` column — because ADR-0015 D2 says
    the permission is *denied in the model*: *"There is no row, so there is
    nothing to check, so the path cannot proceed."* A column that could
    hold ``False`` could also be flipped to ``True`` by an update nobody
    audited, and the whole design is that **the answer is a fact on the
    record rather than a flag somebody flipped**.

    **The four permissions are four grant kinds**, each independently
    absent, independently withdrawn, independently expiring. They are not
    one row with four flags, because that is the shape that lets one
    withdrawal quietly leave the other three standing.

    **A grant names one purpose and one destination**, and both are
    narrower than "the material may be used". ADR-0015 D3's rule is that
    *"a grant naming provider A does not authorise provider B"*, so the
    destination is a field rather than an assumption.

    **No name, no email, no author.** ADR-0015 D5 keeps a person's identity
    apart from the material, and this table carries only the pseudonymous
    subject reference.
    """

    __tablename__ = "access_grants"

    #: Caller-minted, not a row number: a grant is cited from an earlier run
    #: and from a decision record, so identity cannot depend on insertion
    #: order.
    grant_id: Mapped[str] = mapped_column(Text, nullable=False, primary_key=True)
    #: What the grant covers: a paper project's id, or a body of material.
    subject_ref: Mapped[str] = mapped_column(Text, nullable=False)
    #: What the grant **is**. One of the four.
    permission: Mapped[str] = mapped_column(String(32), nullable=False)
    #: What the grant is **for**. The narrow axis: the same permission can
    #: be granted for reading and refused for training.
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    #: Which material the grant covers.
    scope: Mapped[str] = mapped_column(String(2000), nullable=False)
    #: Where the material may go. **Required for ``external_transmit`` and
    #: forbidden for the other three** -- see the constraint below.
    destination: Mapped[str | None] = mapped_column(String(200), nullable=True)
    #: Who granted it. A grant without a granter is a permission nobody
    #: conferred.
    granted_by: Mapped[str] = mapped_column(String(200), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    #: When it runs out. Optional: a grant with no expiry is a standing
    #: grant, and that is a thing a person may decide on purpose.
    expires_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    #: ``active``, ``withdrawn`` or ``expired``.
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    withdrawn_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    withdrawn_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    withdrawal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_access_grants_subject", "subject_ref"),
        Index("ix_access_grants_permission", "permission"),
        CheckConstraint(
            "length(grant_id) > 0 AND length(subject_ref) > 0 AND length(scope) > 0 "
            "AND length(granted_by) > 0",
            name="access_grants_ids_present",
        ),
        # The four permissions, closed. A typo like ``transmit`` instead of
        # ``external_transmit`` must not sail through as a permission
        # nobody holds -- and it must not be *coerced* into one either.
        CheckConstraint(
            "permission IN ('store_read', 'parse_annotate', 'external_transmit', 'train_reuse')",
            name="access_grants_permission_vocabulary",
        ),
        # The five purposes, closed, on the same standard.
        CheckConstraint(
            "purpose IN ('read', 'annotate', 'retrieve', 'transmit', 'train')",
            name="access_grants_purpose_vocabulary",
        ),
        CheckConstraint(
            "state IN ('active', 'withdrawn', 'expired')",
            name="access_grants_state_vocabulary",
        ),
        # **A transmit grant names one destination, and the other three
        # name none.** A transmit grant with no destination is a grant to
        # send anywhere, which is the thing D3 exists to prevent. A read
        # grant *with* a destination is a grant that says where the
        # material goes, which nothing needs.
        CheckConstraint(
            "(permission = 'external_transmit' AND destination IS NOT NULL "
            "AND length(destination) > 0) OR "
            "(permission <> 'external_transmit' AND destination IS NULL)",
            name="access_grants_destination_belongs_to_transmit",
        ),
        # **A withdrawal names who and when.** A state of ``withdrawn`` with
        # no granter is a refusal nobody made, and a permission check that
        # cannot say *who* withdrew it cannot answer the question a person
        # will ask.
        CheckConstraint(
            "(state = 'withdrawn' AND withdrawn_by IS NOT NULL "
            "AND length(withdrawn_by) > 0 AND withdrawn_at IS NOT NULL) OR "
            "(state <> 'withdrawn' AND withdrawn_by IS NULL AND withdrawn_at IS NULL)",
            name="access_grants_withdrawal_names_who_and_when",
        ),
    )


class DerivedCopyRow(Base):
    """Something made **from** material, and the grant it came from.

    **The row exists so a withdrawal can reach its copies.** ADR-0015 D4:
    *"Withdrawing a grant must invalidate what depended on it: derived
    embeddings, index entries built from the material, queued training
    runs, cached model transcripts, and any guidance rule distilled from
    it."*

    **And the design asks the question precisely** — *"撤回同意后历史
    embedding/缓存/训练队列是否失效"* — so the answer has to be a fact and
    not a promise. **A copy records the grant it came from**, and a check
    asks whether that grant is still active.

    **What this cannot do, and says so.** It cannot find copies written
    before the mechanism existed, and it cannot undo a copy that has
    already been used. **It makes the next use impossible**, which is the
    part that is enforceable.
    """

    __tablename__ = "derived_copies"

    copy_id: Mapped[str] = mapped_column(Text, nullable=False, primary_key=True)
    #: The grant this copy was made under. **The provenance**, and the
    #: whole reason the row exists.
    grant_id: Mapped[str] = mapped_column(
        Text, ForeignKey("access_grants.grant_id", ondelete="CASCADE"), nullable=False
    )
    #: What kind of copy: an index entry, an embedding, a queued run, a
    #: cached transcript, a distilled rule.
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    #: Where the copy lives, so a withdrawal can find it.
    location: Mapped[str] = mapped_column(String(2000), nullable=False)
    #: The material the copy was made from.
    subject_ref: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)

    __table_args__ = (
        Index("ix_derived_copies_grant", "grant_id"),
        CheckConstraint(
            "length(copy_id) > 0 AND length(grant_id) > 0 AND length(kind) > 0 "
            "AND length(location) > 0 AND length(subject_ref) > 0",
            name="derived_copies_ids_present",
        ),
        CheckConstraint(
            "kind IN ('index_entry', 'embedding', 'queued_run', 'cached_transcript', "
            "'distilled_rule')",
            name="derived_copies_kind_vocabulary",
        ),
    )
