"""the real-model suggestion loop's run record

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-23

Phase 4 (P4-CAP, real-model loop), execution plan §7.2 and baseline-freeze
G0 §5. One loop run generates suggestions for a version's pending opinions
under a budget, and the budget is only a budget if what was spent is
recorded: **a call nobody can account for is a call that did not happen
honestly.** ``model_suggestion_runs`` is that account -- one row per run,
carrying the mode (``real`` or ``substitute``), the model id, the request
count, the token estimate, which stop condition fired (if one did), and the
per-opinion request entries as JSON.

Direct DDL against ``sa`` types, for the reason 0007, 0012, 0021, 0023,
0024 and 0025 record: a frozen revision must not import today's
``labcairn.db.models``, or the schema it installs drifts with the code
around it. Datetime columns are ``sa.String()`` for the same reason earlier
revisions spell them so: the models' ``UtcDateTime`` is a ``TypeDecorator``
over ``String``, and the parity witness compares compiled types.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_suggestion_runs",
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("version_id", sa.Text(), nullable=False),
        # 'real' -- the authorised model answered; 'substitute' -- the
        # local stand-in answered, and both surfaces say so. The closed
        # vocabulary, because a mode that is neither is a run whose
        # provenance nobody can state.
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column("requests_made", sa.Integer(), nullable=False),
        sa.Column("tokens_estimated", sa.Integer(), nullable=False),
        # Which stop condition fired: 'request_budget', 'token_budget',
        # 'consecutive_failures', 'cancelled' -- or NULL when the walk
        # finished because the opinions ran out.
        sa.Column("stopped_reason", sa.String(length=32), nullable=True),
        sa.Column("suggestions_recorded", sa.Integer(), nullable=False),
        sa.Column("opinions_skipped", sa.Integer(), nullable=False),
        # One entry per transport call: the opinion it was for (by id),
        # the outcome kind, the duration, the token estimate and a
        # failure class name. Digests and counts, never text -- the same
        # discipline the exchange event holds. A JSON column, the way the
        # task rows' id lists have been since 0001, and what the ORM's
        # ``JSON`` type compiles to.
        sa.Column("requests_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.String(), nullable=False),
        sa.Column("finished_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["paper_projects.project_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["version_id"], ["paper_versions.version_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("run_id"),
        sa.CheckConstraint(
            "mode IN ('real', 'substitute')",
            name="model_suggestion_runs_mode_vocabulary",
        ),
        sa.CheckConstraint(
            "requests_made >= 0 AND tokens_estimated >= 0 "
            "AND suggestions_recorded >= 0 AND opinions_skipped >= 0",
            name="model_suggestion_runs_counts_non_negative",
        ),
        sa.CheckConstraint(
            "length(run_id) > 0 AND length(project_id) > 0 "
            "AND length(version_id) > 0 AND length(model_id) > 0",
            name="model_suggestion_runs_ids_present",
        ),
    )
    op.create_index(
        "ix_model_suggestion_runs_project", "model_suggestion_runs", ["project_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_model_suggestion_runs_project", table_name="model_suggestion_runs")
    op.drop_table("model_suggestion_runs")
