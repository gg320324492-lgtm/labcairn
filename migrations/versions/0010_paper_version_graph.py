"""the paper project and the version graph

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-29

LC-P2-08. The mentor-trajectory line's first tables: one row per
manuscript, one per version, and the directed edges between versions.

**Three decisions the schema holds, and each is a refusal rather than a
convention.**

**A version has no parent column.** The teacher's process contains
**parallel branches** -- a student sent two different revised drafts and the
advisor replied to both -- and a column holding one parent cannot hold two.
The parent therefore lives in the edge table, and the graph can branch.

**An edge that claims an acceptance names who accepted it.** A row with an
``accepted_by`` and no acceptor is a human decision with nobody behind it,
and it is refused. The constraint is the way round that is easy to get
backwards: **the absence of an acceptor is not an error**, because that is
what a proposal looks like. A similarity score may never silently decide an
order, so an ``evidence`` edge stays unaccepted however confident it is, and
a ``human`` edge is what settles a relationship.

**An unresolved version is listed.** Its ``status`` is ``unresolved`` until
its place in the sequence is established, and the row is there rather than
absent: the version exists, it is material in the project, and hiding it
because its parent is unknown would make the archive look complete when it
is not.

Direct DDL, for the reason 0007 records: a frozen revision must not import
today's ``labcairn.db.models``, or editing that class would silently
rewrite what this revision meant to create.
``tests/test_evidence_schema.py``'s parity test holds the two together.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_projects",
        # Caller-minted, so a project may be cited from an earlier run and
        # identity cannot depend on insertion order.
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("workspace_id", sa.Text(), nullable=False),
        # A pseudonym. Never the author's name -- ADR-0015 D5 keeps the two
        # apart, and a name here would defeat the separation.
        sa.Column("subject_pseudonym", sa.String(200), nullable=False),
        # A reference LC-P2-06 resolves to a grant. It grants nothing by
        # being present.
        sa.Column("consent_ref", sa.String(200), nullable=True),
        # sa.String(), not sa.DateTime: the models use UtcDateTime, a
        # TypeDecorator whose impl is String because SQLite has no timestamp
        # type and SQLAlchemy's DateTime drops the offset. Revision 0007
        # spells it the same way.
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("project_id", name="pk_paper_projects"),
        sa.CheckConstraint(
            "length(project_id) > 0 AND length(workspace_id) > 0 AND length(subject_pseudonym) > 0",
            name="paper_projects_ids_present",
        ),
        sa.CheckConstraint(
            "consent_ref IS NULL OR length(consent_ref) > 0",
            name="paper_projects_consent_ref_non_empty",
        ),
    )

    op.create_table(
        "paper_versions",
        sa.Column("version_id", sa.Text(), nullable=False),
        sa.Column(
            "project_id",
            sa.Text(),
            sa.ForeignKey("paper_projects.project_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            sa.Text(),
            sa.ForeignKey("sources.source_id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Kept verbatim. **Not evidence of order**: the design says a name
        # like ``最终版2.docx`` is not a statement about which is newer.
        sa.Column("version_label_raw", sa.String(2000), nullable=False),
        # A closed vocabulary, because a stage that could hold any string is
        # a stage that carries no information.
        sa.Column("stage_candidate", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("version_id", name="pk_paper_versions"),
        sa.CheckConstraint(
            "length(version_id) > 0 AND length(project_id) > 0 AND length(source_id) > 0",
            name="paper_versions_ids_present",
        ),
        sa.CheckConstraint(
            "stage_candidate IN ('draft', 'advisor_reviewed', 'submitted', "
            "'camera_ready', 'unknown')",
            name="paper_versions_stage_vocabulary",
        ),
        sa.CheckConstraint(
            "status IN ('resolved', 'unresolved')",
            name="paper_versions_status_vocabulary",
        ),
    )
    op.create_index("ix_paper_versions_project", "paper_versions", ["project_id"])

    op.create_table(
        "version_edges",
        sa.Column("edge_id", sa.Text(), nullable=False),
        sa.Column(
            "project_id",
            sa.Text(),
            sa.ForeignKey("paper_projects.project_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_version_id",
            sa.Text(),
            sa.ForeignKey("paper_versions.version_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "child_version_id",
            sa.Text(),
            sa.ForeignKey("paper_versions.version_id", ondelete="CASCADE"),
            nullable=False,
        ),
        # How the relationship was established.
        sa.Column("source", sa.String(32), nullable=False),
        # How strong the evidence is. A number, not a decision.
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_spans", sa.JSON(), nullable=False),
        # Who accepted it. None while the edge is a proposal.
        sa.Column("accepted_by", sa.String(200), nullable=True),
        sa.Column("accepted_at", sa.String(), nullable=True),
        # The edge's own revision number, for corrections.
        sa.Column("edge_version", sa.Integer(), nullable=False),
        # The edge this one corrects, when it is a correction.
        sa.Column("superseded_by", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("edge_id", name="pk_version_edges"),
        sa.CheckConstraint(
            "length(edge_id) > 0 AND length(project_id) > 0 "
            "AND length(parent_version_id) > 0 AND length(child_version_id) > 0",
            name="version_edges_ids_present",
        ),
        # A version cannot be its own parent. A contradiction, not a
        # self-loop to be tolerated.
        sa.CheckConstraint(
            "parent_version_id <> child_version_id",
            name="version_edges_not_self_parent",
        ),
        sa.CheckConstraint(
            "source IN ('evidence', 'human', 'model')",
            name="version_edges_source_vocabulary",
        ),
        sa.CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="version_edges_confidence_in_range",
        ),
        sa.CheckConstraint(
            "edge_version >= 1",
            name="version_edges_version_positive",
        ),
        # An edge that claims an acceptance names who accepted it. The
        # absence of an acceptor is NOT an error -- that is a proposal.
        sa.CheckConstraint(
            "(accepted_by IS NULL AND accepted_at IS NULL) OR "
            "(accepted_by IS NOT NULL AND length(accepted_by) > 0 "
            "AND accepted_at IS NOT NULL)",
            name="version_edges_acceptance_names_an_acceptor",
        ),
    )
    op.create_index("ix_version_edges_child", "version_edges", ["child_version_id"])
    op.create_index("ix_version_edges_project", "version_edges", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_version_edges_project", table_name="version_edges")
    op.drop_index("ix_version_edges_child", table_name="version_edges")
    op.drop_table("version_edges")
    op.drop_index("ix_paper_versions_project", table_name="paper_versions")
    op.drop_table("paper_versions")
    op.drop_table("paper_projects")
