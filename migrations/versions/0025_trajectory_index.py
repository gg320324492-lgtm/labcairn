"""the multi-source index: a paper's revision trajectory, searchable

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-23

Phase 4 (P4-MS), execution plan §8.1-§8.2, first source: the paper and its
revision trajectory. The chain already holds the facts -- the comments, the
tracked changes, the edits made in answer, and the judgements on them -- but
the facts are spread across four tables keyed for the chain's own questions.
A learner that asks "what did the advisor say about this parameter, and what
happened to that remark" needs one searchable place that answers with the
comment, the change, and **where both of them came from**.

Two tables, following the evidence ledger's precedent (0005/0006):

``trajectory_index_rows``
    One row per trajectory entry. A **comment** entry carries the advisor's
    words, the text they were anchored to, and the judgement (if any) that
    answered them; an **edit** entry carries the change's kind, the words it
    inserted or deleted, and the comment it answered. Every row keeps the
    **source version and the locator** the entry came from, because §8.2's
    rule is that raw material enters the knowledge base with its provenance
    intact -- an entry that cannot say which version of the manuscript it
    was read from is an entry nobody can check.

    The primary key is **derived** (the application layer hashes the project,
    the kind and the chain's own id), so re-ingesting a project is the same
    rows: an index that grew a second copy of its past on every re-read
    would be a record of ingestions, not of the trajectory.

``trajectory_fts``
    The FTS5 index over each entry's searchable digest, on the **trigram**
    tokenizer for the same measured reason 0006 rebuilt ``evidence_fts``:
    extracted manuscript text runs words together, and only a substring
    tokenizer finds them. Standalone rather than external-content, identity
    columns ``UNINDEXED``, no triggers -- the application writes both tables
    in one transaction, the way the evidence index's rebuild does.

Direct DDL against ``sa`` types, for the reason 0007, 0012, 0021, 0023 and
0024 record: a frozen revision must not import today's ``labcairn.db.models``,
or the schema it installs drifts with the code around it. Datetime columns
are ``sa.String()`` for the same reason earlier revisions spell them so: the
models' ``UtcDateTime`` is a ``TypeDecorator`` over ``String``, and the
parity witness compares compiled types.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trajectory_index_rows",
        sa.Column("trajectory_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        # 'comment' -- the advisor's words, anchored; 'edit' -- a tracked
        # change and the comment it answered. The closed vocabulary, because
        # an entry that is neither is a row nobody can render.
        sa.Column("entry_kind", sa.String(length=32), nullable=False),
        sa.Column("feedback_id", sa.Text(), nullable=True),
        sa.Column("edit_action_id", sa.Text(), nullable=True),
        # The revision event behind an edit entry, carried so the change's
        # own address stays reachable without a join through the edit row.
        sa.Column("revision_event_id", sa.Text(), nullable=True),
        sa.Column("version_id", sa.Text(), nullable=False),
        sa.Column("issue_key", sa.Text(), nullable=True),
        sa.Column("comment_text", sa.Text(), nullable=True),
        sa.Column("anchor_text", sa.Text(), nullable=True),
        sa.Column("anchor_paragraph", sa.Integer(), nullable=True),
        # The judgement that answered the comment, as the response link's
        # own state -- 'addressed', 'partially_addressed', 'not_addressed',
        # 'pending' -- or NULL while nobody has judged.
        sa.Column("verdict", sa.Text(), nullable=True),
        # The change's kind ('ins', 'del', 'moveFrom', 'moveTo') and the
        # words it inserted or deleted: the edit entry's old/new summary.
        sa.Column("change_kind", sa.Text(), nullable=True),
        sa.Column("change_text", sa.Text(), nullable=True),
        # The searchable digest: the comment's words and anchor for a
        # comment entry, the change and its comment for an edit entry.
        sa.Column("text_digest", sa.Text(), nullable=False),
        # Provenance: which version the entry was read from, where in it,
        # and the content hash that makes drift detectable.
        sa.Column("source_version_id", sa.Text(), nullable=False),
        sa.Column("source_locator", sa.Text(), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("ingested_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["paper_projects.project_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["feedback_id"], ["feedback_events.feedback_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["edit_action_id"], ["edit_actions.edit_action_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["version_id"], ["paper_versions.version_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("trajectory_id"),
        sa.CheckConstraint(
            "entry_kind IN ('comment', 'edit')",
            name="trajectory_index_entry_kind_vocabulary",
        ),
        sa.CheckConstraint(
            "length(trajectory_id) > 0 AND length(project_id) > 0",
            name="trajectory_index_ids_present",
        ),
        sa.CheckConstraint(
            "(entry_kind = 'comment' AND feedback_id IS NOT NULL) OR "
            "(entry_kind = 'edit' AND edit_action_id IS NOT NULL)",
            name="trajectory_index_entry_names_its_source",
        ),
        sa.CheckConstraint(
            "length(trim(text_digest)) > 0",
            name="trajectory_index_digest_present",
        ),
        sa.CheckConstraint(
            "length(source_version_id) > 0 AND length(source_locator) > 0",
            name="trajectory_index_provenance_present",
        ),
    )
    op.create_index("ix_trajectory_index_project", "trajectory_index_rows", ["project_id"])

    # Standalone FTS5, trigram-tokenized, for the reason 0006 measured:
    # manuscript text arrives with words run together, and a substring
    # tokenizer is the only thing that answers a substring question over
    # it. The id is UNINDEXED -- stored, not searchable -- so a query for
    # an id matches nothing by accident.
    op.execute(
        """
        CREATE VIRTUAL TABLE trajectory_fts USING fts5(
            text_digest,
            trajectory_id UNINDEXED,
            tokenize = 'trigram'
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS trajectory_fts")
    op.drop_index("ix_trajectory_index_project", table_name="trajectory_index_rows")
    op.drop_table("trajectory_index_rows")
