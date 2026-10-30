"""initial task store

Revision ID: 0001
Revises:
Create Date: 2026-10-16 20:01:55.932734

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
# NOTE ON TIMESTAMP COLUMNS: these render as plain sa.String() rather than the
# labcairn.db.models.UtcDateTime decorator used by the ORM. UtcDateTime's impl
# IS String, so the emitted DDL is identical (VARCHAR holding ISO-8601 UTC), but
# a migration is a frozen historical record: rendering the live type here would
# make revision 0001 import today's labcairn.db.models, and a later change to
# that class would silently rewrite what this revision meant to create. The
# decorator still applies on every write, because the repository goes through
# the ORM.

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# The four CHECK constraints below are wrapped across lines rather than left as
# the single ~600-character lines autogenerate emits. The SQL is identical; the
# wrapping exists so that the constraint encoding ADR-0003's closed event
# vocabulary and its per-type run_id rule can be read and reviewed at all.
#
# **And the vocabulary moved here when LC-P2-09 added four types to it.**
# ADR-0017 D8's ``feedback_recorded``, ``edit_action_recorded``,
# ``response_recorded`` and ``followup_assessed`` are annotations, so they
# belong in the "no run", "no transition" and "no operation" lists and in the
# closed list itself. The models generate the same four bodies from
# ``labcairn.runtime.event.EventType`` at import time, and
# ``tests/test_store_migrations.py``'s parity test holds the two renderings
# together -- so a type that reached the models and not this revision would be
# a type the database refuses, which is exactly what happened before this was
# amended. Revision 0001 was amended rather than superseded because the
# product never migrates an existing workspace (``labcairn init`` creates the
# database at head and refuses to overwrite one), so there is no deployed
# schema this changes underneath.

_RUN_ID_MATCHES_EVENT_TYPE = (
    "((type IN ('approval_consumed', 'approval_denied', "
    "'approval_expired', 'approval_granted', "
    "'approval_requested', 'checkpoint_created', "
    "'operation_attempted', 'operation_awaiting_approval', "
    "'operation_confirmed', 'operation_failed', "
    "'operation_intent', 'operation_reconciled', "
    "'operation_uncertain', 'run_finished', "
    "'run_paused', 'run_resumed', 'run_started', "
    "'stage_blocked', 'stage_completed', "
    "'stage_entered')) AND run_id IS NOT NULL) OR ((type IN ('artifact_recorded', "
    "'edit_action_recorded', 'feedback_recorded', "
    "'followup_assessed', 'outbound_consent_requested', "
    "'response_recorded', 'source_changed', "
    "'task_created', 'task_revised')) AND run_id IS NULL)"
)

_TRANSITION_MATCHES_EVENT_TYPE = (
    "((type IN ('approval_consumed', 'approval_denied', "
    "'approval_expired', 'approval_granted', "
    "'approval_requested', 'operation_attempted', "
    "'operation_awaiting_approval', 'operation_confirmed', "
    "'operation_failed', 'operation_intent', "
    "'operation_reconciled', 'operation_uncertain', "
    "'run_finished', 'run_paused', 'run_resumed', "
    "'run_started', 'stage_blocked', 'stage_completed', "
    "'stage_entered')) AND from_state IS NOT NULL AND to_state IS NOT NULL) OR ((type"
    " IN ('artifact_recorded', "
    "'checkpoint_created', 'edit_action_recorded', "
    "'feedback_recorded', 'followup_assessed', "
    "'outbound_consent_requested', "
    "'response_recorded', 'source_changed', 'task_created', "
    "'task_revised')) AND from_state IS NULL AND to_state IS NULL)"
)

_OPERATION_CONTEXT_MATCHES_EVENT_TYPE = (
    "((type IN ('operation_attempted', "
    "'operation_awaiting_approval', 'operation_confirmed', "
    "'operation_failed', 'operation_intent', "
    "'operation_reconciled', 'operation_uncertain')) AND stage_id IS NOT NULL AND ope"
    "ration_id IS NOT NULL) OR ((type IN ('approval_consumed', "
    "'approval_denied', 'approval_expired', "
    "'approval_granted', 'approval_requested', "
    "'artifact_recorded', 'checkpoint_created', "
    "'edit_action_recorded', 'feedback_recorded', "
    "'followup_assessed', 'outbound_consent_requested', "
    "'response_recorded', 'run_finished', "
    "'run_paused', 'run_resumed', 'run_started', "
    "'source_changed', 'stage_blocked', "
    "'stage_completed', 'stage_entered', "
    "'task_created', 'task_revised')) AND operation_id IS NULL)"
)

_TYPE_IS_CLOSED_VOCABULARY = (
    "type IN ('approval_consumed', 'approval_denied', "
    "'approval_expired', 'approval_granted', "
    "'approval_requested', 'artifact_recorded', "
    "'checkpoint_created', 'edit_action_recorded', "
    "'feedback_recorded', 'followup_assessed', "
    "'operation_attempted', "
    "'operation_awaiting_approval', 'operation_confirmed', "
    "'operation_failed', 'operation_intent', "
    "'operation_reconciled', 'operation_uncertain', "
    "'outbound_consent_requested', 'response_recorded', "
    "'run_finished', 'run_paused', 'run_resumed', "
    "'run_started', 'source_changed', 'stage_blocked', "
    "'stage_completed', 'stage_entered', "
    "'task_created', 'task_revised')"
)


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("success_criterion", sa.Text(), nullable=False),
        sa.Column("bound_source_ids", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("last_event_seq", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "last_event_seq >= 0", name=op.f("ck_tasks_last_event_seq_non_negative")
        ),
        sa.CheckConstraint("revision >= 1", name=op.f("ck_tasks_revision_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
        sa.UniqueConstraint("task_id", name=op.f("uq_tasks_task_id")),
    )
    op.create_table(
        "runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.String(), nullable=True),
        sa.Column("finished_at", sa.String(), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.CheckConstraint("attempt >= 1", name=op.f("ck_runs_attempt_positive")),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.task_id"], name=op.f("fk_runs_task_id_tasks"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_runs")),
        sa.UniqueConstraint("run_id", name=op.f("uq_runs_run_id")),
    )
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.create_index("ix_runs_task_id", ["task_id"], unique=False)

    op.create_table(
        "artifacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("artifact_id", sa.Text(), nullable=False),
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("relative_path", sa.String(length=2000), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("produced_by", sa.String(length=32), nullable=False),
        sa.Column("producer_id", sa.String(length=200), nullable=False),
        sa.Column("derived_from", sa.JSON(), nullable=False),
        sa.Column("staleness", sa.String(length=16), nullable=False),
        sa.Column("staleness_reason", sa.Text(), nullable=True),
        sa.Column("media_type", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "(staleness = 'stale') = (staleness_reason IS NOT NULL)",
            name=op.f("ck_artifacts_staleness_reason_paired"),
        ),
        sa.CheckConstraint("revision >= 1", name=op.f("ck_artifacts_revision_positive")),
        sa.CheckConstraint("size_bytes >= 0", name=op.f("ck_artifacts_size_non_negative")),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.run_id"], name=op.f("fk_artifacts_run_id_runs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.task_id"],
            name=op.f("fk_artifacts_task_id_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artifacts")),
        sa.UniqueConstraint("artifact_id", name=op.f("uq_artifacts_artifact_id")),
        sa.UniqueConstraint("task_id", "relative_path", "revision", name="uq_artifacts_revision"),
    )
    with op.batch_alter_table("artifacts", schema=None) as batch_op:
        batch_op.create_index("ix_artifacts_run_id", ["run_id"], unique=False)

    op.create_table(
        "stages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stage_id", sa.Text(), nullable=False),
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input_hashes", sa.JSON(), nullable=False),
        sa.Column("output_hashes", sa.JSON(), nullable=False),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "(status = 'blocked') = (blocked_reason IS NOT NULL)",
            name=op.f("ck_stages_reason_only_when_blocked"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.run_id"], name=op.f("fk_stages_run_id_runs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.task_id"], name=op.f("fk_stages_task_id_tasks"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stages")),
        sa.UniqueConstraint("stage_id", name=op.f("uq_stages_stage_id")),
    )
    with op.batch_alter_table("stages", schema=None) as batch_op:
        batch_op.create_index("ix_stages_run_id", ["run_id"], unique=False)

    op.create_table(
        "checkpoints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("checkpoint_id", sa.Text(), nullable=False),
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("stage_id", sa.Text(), nullable=False),
        sa.Column("through_seq", sa.Integer(), nullable=False),
        sa.Column("material_hashes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.CheckConstraint("through_seq >= 1", name=op.f("ck_checkpoints_through_seq_positive")),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.run_id"], name=op.f("fk_checkpoints_run_id_runs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["stage_id"],
            ["stages.stage_id"],
            name=op.f("fk_checkpoints_stage_id_stages"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.task_id"],
            name=op.f("fk_checkpoints_task_id_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_checkpoints")),
        sa.UniqueConstraint("checkpoint_id", name=op.f("uq_checkpoints_checkpoint_id")),
    )
    with op.batch_alter_table("checkpoints", schema=None) as batch_op:
        batch_op.create_index("ix_checkpoints_run_id", ["run_id"], unique=False)

    op.create_table(
        "operations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("operation_id", sa.Text(), nullable=False),
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("stage_id", sa.Text(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("capability", sa.String(length=200), nullable=False),
        sa.Column("resource_key", sa.String(length=2000), nullable=False),
        sa.Column("depends_on", sa.JSON(), nullable=False),
        sa.Column("args_digest", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.run_id"], name=op.f("fk_operations_run_id_runs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["stage_id"],
            ["stages.stage_id"],
            name=op.f("fk_operations_stage_id_stages"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.task_id"],
            name=op.f("fk_operations_task_id_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_operations")),
        sa.UniqueConstraint("operation_id", name=op.f("uq_operations_operation_id")),
    )
    with op.batch_alter_table("operations", schema=None) as batch_op:
        batch_op.create_index("ix_operations_run_id", ["run_id"], unique=False)
        batch_op.create_index("ix_operations_stage_id", ["stage_id"], unique=False)

    op.create_table(
        "approvals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("approval_id", sa.Text(), nullable=False),
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("operation_id", sa.Text(), nullable=False),
        sa.Column("capability", sa.String(length=200), nullable=False),
        sa.Column("resource_key", sa.String(length=2000), nullable=False),
        sa.Column("args_digest", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.String(), nullable=False),
        sa.Column("granted_at", sa.String(), nullable=True),
        sa.Column("consumed_at", sa.String(), nullable=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "consumed_at IS NULL OR granted_at IS NULL OR consumed_at >= granted_at",
            name=op.f("ck_approvals_consume_after_grant"),
        ),
        sa.CheckConstraint(
            "granted_at IS NULL OR expires_at > granted_at",
            name=op.f("ck_approvals_expiry_after_grant"),
        ),
        sa.ForeignKeyConstraint(
            ["operation_id"],
            ["operations.operation_id"],
            name=op.f("fk_approvals_operation_id_operations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.task_id"],
            name=op.f("fk_approvals_task_id_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approvals")),
        sa.UniqueConstraint("approval_id", name=op.f("uq_approvals_approval_id")),
    )
    with op.batch_alter_table("approvals", schema=None) as batch_op:
        batch_op.create_index("ix_approvals_operation_id", ["operation_id"], unique=False)

    op.create_table(
        "events",
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
        sa.Column("payload", sa.Text(), nullable=False),
        sa.CheckConstraint(
            _RUN_ID_MATCHES_EVENT_TYPE,
            name=op.f("ck_events_run_id_matches_event_type"),
        ),
        sa.CheckConstraint(
            _TRANSITION_MATCHES_EVENT_TYPE,
            name=op.f("ck_events_transition_matches_event_type"),
        ),
        sa.CheckConstraint(
            _OPERATION_CONTEXT_MATCHES_EVENT_TYPE,
            name=op.f("ck_events_operation_context_matches_event_type"),
        ),
        sa.CheckConstraint(
            _TYPE_IS_CLOSED_VOCABULARY,
            name=op.f("ck_events_type_is_closed_vocabulary"),
        ),
        sa.CheckConstraint("seq >= 1", name=op.f("ck_events_seq_positive")),
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
        sa.UniqueConstraint("task_id", "seq", name="uq_events_task_seq"),
        sqlite_autoincrement=True,
    )
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.create_index("ix_events_run_id", ["run_id"], unique=False)
        batch_op.create_index("ix_events_task_id_type", ["task_id", "type"], unique=False)

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.drop_index("ix_events_task_id_type")
        batch_op.drop_index("ix_events_run_id")

    op.drop_table("events")
    with op.batch_alter_table("approvals", schema=None) as batch_op:
        batch_op.drop_index("ix_approvals_operation_id")

    op.drop_table("approvals")
    with op.batch_alter_table("operations", schema=None) as batch_op:
        batch_op.drop_index("ix_operations_stage_id")
        batch_op.drop_index("ix_operations_run_id")

    op.drop_table("operations")
    with op.batch_alter_table("checkpoints", schema=None) as batch_op:
        batch_op.drop_index("ix_checkpoints_run_id")

    op.drop_table("checkpoints")
    with op.batch_alter_table("stages", schema=None) as batch_op:
        batch_op.drop_index("ix_stages_run_id")

    op.drop_table("stages")
    with op.batch_alter_table("artifacts", schema=None) as batch_op:
        batch_op.drop_index("ix_artifacts_run_id")

    op.drop_table("artifacts")
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.drop_index("ix_runs_task_id")

    op.drop_table("runs")
    op.drop_table("tasks")
    # ### end Alembic commands ###
