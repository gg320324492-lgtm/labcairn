"""the removal's event, for a store that was built before the vocabulary carried it

Revision ID: 0034
Revises: 0033
Create Date: 2026-11-27

**Why this revision exists.** Taking a source back out of the ledger is now
recorded as a ``source_removed`` event carrying the id, the path and the
digest of the row that left, and the tasks that had to let it go. The closed
vocabulary lives in four CHECK constraints on the ``events`` table, and those
constraints were rebuilt by revision 0033 with the vocabulary as it stood
then. A store built at 0033 keeps the constraints it was built with, because
alembic does not run earlier revisions again; it would refuse the new type
while a store built from scratch accepted it.

So this revision rebuilds the ``events`` table with the vocabulary the
models now carry. The sets below are the four the models derive from the
frozen ``EventType`` enum, written out because a frozen migration may not
import the live package -- the same reason revisions 0001, 0032 and 0033
carry their own copies.

**``source_removed`` is an annotation, and the constraints say so.** It must
not name a Run (a removal can happen to a task outside any run), must not
name an Operation (there is no attempt to attach it to), and must not carry a
transition (taking a stale location back is not a state change inside an
attempt). It is therefore in ``_ALL_TYPES`` and in the three "must not" sets,
and in none of the three "must" sets.

**Direct DDL rather than ``op.batch_alter_table``**, for the reason revision
0032 records: batch mode reflects the live schema, and revision 0002 found
that reflection silently does nothing on this table. A migration that
reports success and changes nothing is the worst of the available failures,
so this one issues the statements it means.

**The downgrade takes the vocabulary back.** It rebuilds the table with the
four sets as they stood at 0033 -- without ``source_removed`` -- so a
rollback is the same shape as the upgrade.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: The four vocabulary sets, as the models derive them from the frozen
#: ``EventType`` enum. Written out because this migration may not import the
#: live package; the sets are the ones ``labcairn.db.models`` renders.
_ALL_TYPES = (
    "approval_consumed",
    "approval_denied",
    "approval_expired",
    "approval_granted",
    "approval_requested",
    "artifact_recorded",
    "checkpoint_created",
    "edit_action_recorded",
    "feedback_recorded",
    "followup_assessed",
    "model_exchanged",
    "operation_attempted",
    "operation_awaiting_approval",
    "operation_confirmed",
    "operation_denied",
    "operation_failed",
    "operation_intent",
    "operation_reconciled",
    "operation_uncertain",
    "outbound_consent_requested",
    "refusal_recorded",
    "response_recorded",
    "run_finished",
    "run_paused",
    "run_resumed",
    "run_started",
    "source_changed",
    "source_removed",
    "stage_blocked",
    "stage_completed",
    "stage_entered",
    "task_created",
    "task_revised",
)
_RUN_SCOPED_TYPES = (
    "approval_consumed",
    "approval_denied",
    "approval_expired",
    "approval_granted",
    "approval_requested",
    "checkpoint_created",
    "operation_attempted",
    "operation_awaiting_approval",
    "operation_confirmed",
    "operation_denied",
    "operation_failed",
    "operation_intent",
    "operation_reconciled",
    "operation_uncertain",
    "run_finished",
    "run_paused",
    "run_resumed",
    "run_started",
    "stage_blocked",
    "stage_completed",
    "stage_entered",
)
_TASK_LEVEL_TYPES = (
    "artifact_recorded",
    "edit_action_recorded",
    "feedback_recorded",
    "followup_assessed",
    "model_exchanged",
    "outbound_consent_requested",
    "refusal_recorded",
    "response_recorded",
    "source_changed",
    "source_removed",
    "task_created",
    "task_revised",
)
_OPERATION_CONTEXT_TYPES = (
    "operation_attempted",
    "operation_awaiting_approval",
    "operation_confirmed",
    "operation_denied",
    "operation_failed",
    "operation_intent",
    "operation_reconciled",
    "operation_uncertain",
)
_NON_OPERATION_CONTEXT_TYPES = (
    "approval_consumed",
    "approval_denied",
    "approval_expired",
    "approval_granted",
    "approval_requested",
    "artifact_recorded",
    "checkpoint_created",
    "edit_action_recorded",
    "feedback_recorded",
    "followup_assessed",
    "model_exchanged",
    "outbound_consent_requested",
    "refusal_recorded",
    "response_recorded",
    "run_finished",
    "run_paused",
    "run_resumed",
    "run_started",
    "source_changed",
    "source_removed",
    "stage_blocked",
    "stage_completed",
    "stage_entered",
    "task_created",
    "task_revised",
)
_TRANSITION_TYPES = (
    "approval_consumed",
    "approval_denied",
    "approval_expired",
    "approval_granted",
    "approval_requested",
    "operation_attempted",
    "operation_awaiting_approval",
    "operation_confirmed",
    "operation_denied",
    "operation_failed",
    "operation_intent",
    "operation_reconciled",
    "operation_uncertain",
    "run_finished",
    "run_paused",
    "run_resumed",
    "run_started",
    "stage_blocked",
    "stage_completed",
    "stage_entered",
)
_NON_TRANSITION_TYPES = (
    "artifact_recorded",
    "checkpoint_created",
    "edit_action_recorded",
    "feedback_recorded",
    "followup_assessed",
    "model_exchanged",
    "outbound_consent_requested",
    "refusal_recorded",
    "response_recorded",
    "source_changed",
    "source_removed",
    "task_created",
    "task_revised",
)


def _list_of(values: Sequence[str]) -> str:
    """Render an IN list the way the models render it."""
    return "(" + ", ".join(f"'{value}'" for value in sorted(values)) + ")"


def _checks(*, source_removed: bool) -> list[sa.CheckConstraint]:
    """The four vocabulary constraints, with or without the new type."""
    all_types: tuple[str, ...] = _ALL_TYPES
    run_scoped: tuple[str, ...] = _RUN_SCOPED_TYPES
    operation_context: tuple[str, ...] = _OPERATION_CONTEXT_TYPES
    transition: tuple[str, ...] = _TRANSITION_TYPES
    task_level: tuple[str, ...] = _TASK_LEVEL_TYPES
    non_operation_context: tuple[str, ...] = _NON_OPERATION_CONTEXT_TYPES
    non_transition: tuple[str, ...] = _NON_TRANSITION_TYPES
    if not source_removed:
        all_types = tuple(value for value in all_types if value != "source_removed")
        task_level = tuple(value for value in task_level if value != "source_removed")
        non_operation_context = tuple(
            value for value in non_operation_context if value != "source_removed"
        )
        non_transition = tuple(value for value in non_transition if value != "source_removed")
        run_scoped = tuple(value for value in run_scoped if value != "source_removed")
        operation_context = tuple(value for value in operation_context if value != "source_removed")
        transition = tuple(value for value in transition if value != "source_removed")
    return [
        sa.CheckConstraint(
            f"type IN {_list_of(all_types)}",
            name=op.f("ck_events_type_is_closed_vocabulary"),
        ),
        sa.CheckConstraint(
            f"((type IN {_list_of(run_scoped)}) AND run_id IS NOT NULL)"
            f" OR ((type IN {_list_of(task_level)}) AND run_id IS NULL)",
            name=op.f("ck_events_run_id_matches_event_type"),
        ),
        sa.CheckConstraint(
            f"((type IN {_list_of(operation_context)})"
            f" AND stage_id IS NOT NULL AND operation_id IS NOT NULL)"
            f" OR ((type IN {_list_of(non_operation_context)})"
            f" AND operation_id IS NULL)",
            name=op.f("ck_events_operation_context_matches_event_type"),
        ),
        sa.CheckConstraint(
            f"((type IN {_list_of(transition)})"
            f" AND from_state IS NOT NULL AND to_state IS NOT NULL)"
            f" OR ((type IN {_list_of(non_transition)})"
            f" AND from_state IS NULL AND to_state IS NULL)",
            name=op.f("ck_events_transition_matches_event_type"),
        ),
        sa.CheckConstraint("seq >= 1", name=op.f("ck_events_seq_positive")),
    ]


def _columns() -> list[sa.Column[Any]]:
    """The table's columns, as the models declare them."""
    return [
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=True),
        sa.Column("stage_id", sa.Text(), nullable=True),
        sa.Column("operation_id", sa.Text(), nullable=True),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("from_state", sa.String(length=64), nullable=True),
        sa.Column("to_state", sa.String(length=64), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.String(), nullable=False),
        sa.Column("document", sa.Text(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False, server_default="{}"),
    ]


def _constraints() -> list[sa.schema.SchemaItem]:
    """The table's foreign keys, its unique constraints and its primary key."""
    return [
        sa.ForeignKeyConstraint(
            ["operation_id"],
            ["operations.operation_id"],
            name=op.f("fk_events_operation_id_operations"),
            ondelete="CASCADE",
            initially="DEFERRED",
            deferrable=True,
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["runs.run_id"],
            name=op.f("fk_events_run_id_runs"),
            ondelete="CASCADE",
            initially="DEFERRED",
            deferrable=True,
        ),
        sa.ForeignKeyConstraint(
            ["stage_id"],
            ["stages.stage_id"],
            name=op.f("fk_events_stage_id_stages"),
            ondelete="CASCADE",
            initially="DEFERRED",
            deferrable=True,
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.task_id"],
            name=op.f("fk_events_task_id_tasks"),
            ondelete="CASCADE",
            initially="DEFERRED",
            deferrable=True,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_events")),
        sa.UniqueConstraint("event_id", name=op.f("uq_events_event_id")),
        sa.UniqueConstraint("task_id", "seq", name=op.f("uq_events_task_seq")),
    ]


def _rebuild(*, source_removed: bool) -> None:
    """Rebuild the table, carrying every row across."""
    op.create_table(
        "events_new",
        *_columns(),
        *_constraints(),
        *_checks(source_removed=source_removed),
        sqlite_autoincrement=True,
    )
    op.execute(
        "INSERT INTO events_new (id, seq, event_id, task_id, run_id, stage_id, "
        "operation_id, type, from_state, to_state, schema_version, occurred_at, "
        "document, payload) "
        "SELECT id, seq, event_id, task_id, run_id, stage_id, operation_id, type, "
        "from_state, to_state, schema_version, occurred_at, document, payload FROM events"
    )
    op.drop_table("events")
    op.rename_table("events_new", "events")
    op.create_index("ix_events_run_id", "events", ["run_id"], unique=False)
    op.create_index("ix_events_task_id_type", "events", ["task_id", "type"], unique=False)


def upgrade() -> None:
    _rebuild(source_removed=True)


def downgrade() -> None:
    _rebuild(source_removed=False)
