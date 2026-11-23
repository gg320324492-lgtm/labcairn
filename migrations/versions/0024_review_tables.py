"""the reviewer's verdict and the model's proposal are rows, not memories

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-23

**A verdict that lives only in the caller's request body is a verdict the
workbench cannot show twice.** Phase 4's three-column workbench renders each
opinion with its current decision, and the apply step reads the approved set
from the store -- so both the suggestion the model made and the decision a
reviewer made have to persist, under the same ``feedback_id`` the opinion
carries, or the second read would forget the first.

Two tables, because ADR-0016's rule is that the model's proposal and the
person's verdict are **separate records that are never merged**: a reader of
one must not read the other through it. ``review_suggestions`` holds what
was proposed (in the seam's own vocabulary -- one whole plain run of one
paragraph); ``review_decisions`` holds what the reviewer decided. Both are
keyed by the opinion's id, so the binding's apply step reads the pair back
without a join table of its own.

Direct DDL against ``sa`` types, for the reason 0007, 0012, 0021 and 0023
record: a frozen revision must not import today's ``labcairn.db.models``, or
the schema it installs drifts with the code around it. Datetime columns are
``sa.String()`` for the same reason earlier revisions spell them so: the
models' ``UtcDateTime`` is a ``TypeDecorator`` over ``String``, and the
parity witness compares compiled types.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_suggestions",
        sa.Column("feedback_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("version_id", sa.Text(), nullable=False),
        sa.Column("part", sa.String(length=500), nullable=False),
        sa.Column("paragraph", sa.Integer(), nullable=False),
        sa.Column("old_text", sa.Text(), nullable=False),
        sa.Column("new_text", sa.Text(), nullable=False),
        sa.Column("author", sa.String(length=200), nullable=False),
        sa.Column("proposed_at", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["feedback_id"], ["feedback_events.feedback_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["paper_projects.project_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["paper_versions.version_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("feedback_id"),
        sa.CheckConstraint(
            "length(feedback_id) > 0 AND length(project_id) > 0 AND length(version_id) > 0",
            name="review_suggestions_ids_present",
        ),
        sa.CheckConstraint(
            "paragraph >= 1",
            name="review_suggestions_paragraph_positive",
        ),
        sa.CheckConstraint(
            "length(part) > 0 AND length(author) > 0",
            name="review_suggestions_part_and_author_present",
        ),
    )
    op.create_index("ix_review_suggestions_project", "review_suggestions", ["project_id"])

    op.create_table(
        "review_decisions",
        sa.Column("feedback_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("version_id", sa.Text(), nullable=False),
        sa.Column("verdict", sa.String(length=32), nullable=False),
        sa.Column("needs_evidence", sa.Boolean(), nullable=False),
        sa.Column("operator", sa.String(length=200), nullable=False),
        sa.Column("decided_at", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["feedback_id"], ["feedback_events.feedback_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["paper_projects.project_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["paper_versions.version_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("feedback_id"),
        sa.CheckConstraint(
            "verdict IN ('accepted', 'partly_accepted', 'rejected', 'pending')",
            name="review_decisions_verdict_vocabulary",
        ),
        sa.CheckConstraint(
            "length(feedback_id) > 0 AND length(project_id) > 0 AND length(version_id) > 0",
            name="review_decisions_ids_present",
        ),
        sa.CheckConstraint(
            "length(operator) > 0",
            name="review_decisions_operator_present",
        ),
    )
    op.create_index("ix_review_decisions_project", "review_decisions", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_review_decisions_project", table_name="review_decisions")
    op.drop_table("review_decisions")
    op.drop_index("ix_review_suggestions_project", table_name="review_suggestions")
    op.drop_table("review_suggestions")
