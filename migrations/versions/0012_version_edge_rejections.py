"""the refusal has a row, and a version keeps its bytes

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-30

LC-P2-09 T00. Two changes, and both are about a fact that had nowhere to
live.

**A rejection is a row of its own.** The other two outcomes leave their own
mark on the version graph: an acceptance is the edge with an acceptor, and a
correction is a second edge with the proposal pointing at it. A rejection
leaves nothing -- there is no relationship to record -- and a proposal that
was looked at and turned down was therefore indistinguishable from a
proposal nobody has looked at. The archive would propose it again, having
learned nothing from the refusal. The design says plainly that "a person
looked at this and said no" is information the archive needs, and this
revision gives it somewhere to be.

**A version keeps the bytes it was recorded with.** The row named the *file*,
and a file's bytes move: re-ingesting it after an edit changes what the
ledger holds under that id. A version that took its identity from the file
would move with it, and the rule that two files with the same bytes are one
version cannot be held by an identity that moves. So the hash is recorded
once, when the version is written, and the version is that set of bytes for
ever.

**The column is nullable, and that is a deliberate cost.** SQLite cannot add
a NOT NULL column to a table that holds rows without a default, and every
default here would be a lie -- a version whose bytes hash to nothing is not a
version of nothing. So the column is nullable, the rows that exist are
backfilled from the ledger, and a row that carries no hash is refused by the
reader rather than read as a version of unknown bytes. It is the same
choice revision 0009 made for the five columns it added.

Direct DDL, for the reason 0007 records: a frozen revision must not import
today's ``labcairn.db.models``, or editing that class would silently
rewrite what this revision meant to create.
``tests/test_store_migrations.py``'s parity test holds the two together.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -- the version's bytes, as they were when it was recorded ---------------
    op.add_column(
        "paper_versions",
        sa.Column("source_content_sha256", sa.String(64), nullable=True),
    )
    # The rows that exist are the ones a previous revision wrote, and their
    # bytes are the ledger's answer for the file they name. The foreign key
    # says the file is there, so the subquery always finds one.
    op.execute(
        "UPDATE paper_versions SET source_content_sha256 = "
        "(SELECT content_sha256 FROM sources WHERE sources.source_id = paper_versions.source_id)"
    )

    # -- the record of a refusal ----------------------------------------------
    op.create_table(
        "version_edge_rejections",
        # Caller-minted, so a refusal is cited from a later run.
        sa.Column("rejection_id", sa.Text(), nullable=False),
        # The proposal that was refused. It stays in the graph.
        sa.Column("edge_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        # Who decided, and when. A refusal with nobody behind it is not a
        # refusal anybody made.
        sa.Column("decided_by", sa.String(200), nullable=False),
        sa.Column("decided_at", sa.String(), nullable=False),
        # Why, in their words. Empty is allowed; the refusal is what matters.
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("rejection_id", name="pk_version_edge_rejections"),
        sa.ForeignKeyConstraint(["edge_id"], ["version_edges.edge_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["paper_projects.project_id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "length(rejection_id) > 0 AND length(edge_id) > 0 "
            "AND length(project_id) > 0 AND length(decided_by) > 0",
            name="version_edge_rejections_ids_present",
        ),
    )
    op.create_index("ix_version_edge_rejections_edge", "version_edge_rejections", ["edge_id"])


def downgrade() -> None:
    op.drop_index("ix_version_edge_rejections_edge", table_name="version_edge_rejections")
    op.drop_table("version_edge_rejections")
    # Plain ALTER, not a table rebuild: rebuilding would drop the table and
    # cascade the deletion into every edge that names one of its versions.
    op.execute("ALTER TABLE paper_versions DROP COLUMN source_content_sha256")
