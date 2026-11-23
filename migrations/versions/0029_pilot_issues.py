"""the pilot's in-system issue record

Revision ID: 0029
Revises: 0028
Create Date: 2026-11-24

Phase 4 (P4-PILOT §9.4), execution plan §9.4. The real trial records its
problems **in the system as well as in the feedback form**: one row per
problem, naming the task, the version, the opinion it concerns, the
operation step it happened at, the error the user saw, how long the step
took and how often it was retried -- plus a severity (``blocker``,
``serious``, ``minor``, ``suggestion``) and a type (``function``,
``interface``, ``performance``, ``model``, ``documentation``). The
feedback form records the subjective experience; this table is the
system-side record the form's line points at.

**The status is the trial team's word on the problem, and the vocabulary
is closed**: ``open`` when recorded, ``confirmed`` when a second person
has seen it, ``fixed`` -- which names the version that fixed it -- or
``wontfix`` with a reason. A transition that skips a state is a record
that says something nobody said; the application layer moves the row
along the four states rather than letting a caller set it.

Direct DDL against ``sa`` types, for the reason 0007, 0012, 0021, 0023,
0024, 0025 and 0027 record: a frozen revision must not import today's
``labcairn.db.models``, or the schema it installs drifts with the code
around it. Datetime columns are ``sa.String()`` for the same reason
earlier revisions spell them so: the models' ``UtcDateTime`` is a
``TypeDecorator`` over ``String``, and the parity witness compares
compiled types.

The meeting-text slice lands its own revision as 0028 after this one; alembic
resolves the chain at the batch merge, so the pair lands as one head
when the batch's branches come together.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pilot_issues",
        sa.Column("issue_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        # What the problem is about. All three may be unknown at the moment
        # of recording -- a login failure names no version -- and None is a
        # fact the row keeps rather than a blank it papers over.
        sa.Column("task_id", sa.Text(), nullable=True),
        sa.Column("version_id", sa.Text(), nullable=True),
        sa.Column("feedback_id", sa.Text(), nullable=True),
        # The operation step the problem happened at, e.g. ``apply``,
        # ``export``, ``suggest``. A problem without a step is a problem
        # nobody can reproduce.
        sa.Column("step", sa.String(length=100), nullable=False),
        # What the user saw, in their own words. The record holds it
        # verbatim: a paraphrase is a second opinion about the error.
        sa.Column("error_text", sa.Text(), nullable=False),
        # How long the step took, in seconds, and how often it was retried.
        # Both are the trial's efficiency readings (execution plan §9.3).
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=True),
        # §9.4's two closed vocabularies: 阻断/严重/一般/建议 and
        # 功能/界面/性能/模型/文档, in this repository's English. A word
        # outside either is a tag nobody can group by.
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("reported_by", sa.Text(), nullable=False),
        sa.Column("reported_at", sa.String(), nullable=False),
        # The team's word on the problem, moved along the four states by
        # the application layer, not set by a caller.
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="open",
        ),
        sa.Column("fix_version", sa.Text(), nullable=True),
        sa.Column("regression_note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["paper_projects.project_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("issue_id"),
        sa.CheckConstraint(
            "severity IN ('blocker', 'serious', 'minor', 'suggestion')",
            name="pilot_issues_severity_vocabulary",
        ),
        sa.CheckConstraint(
            "category IN ('function', 'interface', 'performance', 'model', 'documentation')",
            name="pilot_issues_category_vocabulary",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'confirmed', 'fixed', 'wontfix')",
            name="pilot_issues_status_vocabulary",
        ),
        sa.CheckConstraint(
            "length(issue_id) > 0 AND length(project_id) > 0 "
            "AND length(step) > 0 AND length(reported_by) > 0",
            name="pilot_issues_ids_present",
        ),
        sa.CheckConstraint(
            "retry_count IS NULL OR retry_count >= 0",
            name="pilot_issues_retry_non_negative",
        ),
    )
    op.create_index(
        "ix_pilot_issues_project",
        "pilot_issues",
        ["project_id"],
    )
    op.create_index(
        "ix_pilot_issues_status",
        "pilot_issues",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_pilot_issues_status", table_name="pilot_issues")
    op.drop_index("ix_pilot_issues_project", table_name="pilot_issues")
    op.drop_table("pilot_issues")
