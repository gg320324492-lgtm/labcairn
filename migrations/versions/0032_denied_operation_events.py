"""the denied write's event, for a store that was built before it

Revision ID: 0032
Revises: 0031
Create Date: 2026-11-25

**Why this revision exists.** A policy denial is now recorded as an
operation in state ``denied`` and as an ``operation_denied`` event. The
closed vocabulary of event types lives in the *first* migration, as four
CHECK constraints on the ``events`` table, and revision 0001 was amended
to carry the new type -- on the ground that the product never migrates an
existing workspace, because ``labcairn init`` builds the database at head
and refuses to overwrite one.

That ground does not hold for every store there is. Alembic's upgrade path
exists, the repository witnesses it, and the 0.1.0 installer has been in
users' hands since 2026-11-24: a workspace built before the amendment
keeps the constraints it was built with, because alembic does not run the
first migration again. **Measured on 2026-11-25:** a store built with the
pre-amendment 0001 and then upgraded to head still refused
``operation_denied``, while a store built from scratch accepted it.

So this revision rebuilds the ``events`` table with the vocabulary the
models already carry. The four sets below are the same four the models
derive from the frozen ``EventType`` enum, and they are written out here
because a frozen migration may not import the live package -- the same
reason revision 0001 carries its own copies.

**Direct DDL rather than ``op.batch_alter_table``.** Batch mode reflects
the live schema, and revision 0002 found that reflection silently does
nothing on this table. A migration that reports success and changes
nothing is the worst of the available failures, so this one issues the
statements it means.

**The downgrade takes the vocabulary back.** It rebuilds the table with the
four sets as they stood before the amendment -- the same shape the first
migration produced -- so a rollback is the same shape as the upgrade.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: str | None = "0031"
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
    "response_recorded",
    "run_finished",
    "run_paused",
    "run_resumed",
    "run_started",
    "source_changed",
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
    "response_recorded",
    "source_changed",
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
    "response_recorded",
    "run_finished",
    "run_paused",
    "run_resumed",
    "run_started",
    "source_changed",
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
    "response_recorded",
    "source_changed",
    "task_created",
    "task_revised",
)


def _list_of(values: Sequence[str]) -> str:
    """Render an IN list the way the models render it."""
    return "(" + ", ".join(f"'{value}'" for value in sorted(values)) + ")"


def _checks(*, denied: bool) -> list[sa.CheckConstraint]:
    """The four vocabulary constraints, with or without the new type."""
    all_types: tuple[str, ...] = _ALL_TYPES
    run_scoped: tuple[str, ...] = _RUN_SCOPED_TYPES
    operation_context: tuple[str, ...] = _OPERATION_CONTEXT_TYPES
    transition: tuple[str, ...] = _TRANSITION_TYPES
    if not denied:
        all_types = tuple(value for value in all_types if value != "operation_denied")
        run_scoped = tuple(value for value in run_scoped if value != "operation_denied")
        operation_context = tuple(
            value for value in operation_context if value != "operation_denied"
        )
        transition = tuple(value for value in transition if value != "operation_denied")
    task_level: tuple[str, ...] = tuple(
        value for value in _TASK_LEVEL_TYPES if value != "operation_denied"
    )
    non_operation_context: tuple[str, ...] = tuple(
        value for value in _NON_OPERATION_CONTEXT_TYPES if value != "operation_denied"
    )
    non_transition: tuple[str, ...] = tuple(
        value for value in _NON_TRANSITION_TYPES if value != "operation_denied"
    )
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


def _rebuild(*, denied: bool) -> None:
    """Rebuild the table, carrying every row across."""
    op.create_table(
        "events_new",
        *_columns(),
        *_constraints(),
        *_checks(denied=denied),
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
    _rebuild(denied=True)


def downgrade() -> None:
    _rebuild(denied=False)
