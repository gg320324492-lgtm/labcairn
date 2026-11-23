"""the multi-source index: a deck's objects, searchable

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-23

Phase 4 (P4-MS), execution plan §8.3, second source: a PowerPoint deck's
titles, body text, speaker notes, tables and images. §8.3's rule is that
every extraction result keeps the deck version, the slide number or object
position and the source fingerprint -- and §8.5's is that a hit points back
at the correct slide or object. One table holds the objects with that
provenance; one FTS5 index makes them searchable; the application layer
writes both in one transaction, the way the trajectory index does.

Two tables, following the trajectory index's precedent (0025):

``ppt_index_rows``
    One row per extracted object. The ``object_kind`` names what the row
    holds -- a title, a body paragraph, a speaker note, a table row or a
    picture name -- and every row carries the **slide number (1-based),
    the object's position within the slide (1-based) and the source
    fingerprint** the extraction recorded, so a hit says not only what the
    deck says but which slide and which object says it.

    The primary key is **derived** (the application layer hashes the
    project, the source file's content hash and the object's fingerprint),
    so re-ingesting the same deck is the same rows: an index that grew a
    second copy of a deck on every re-read would be a record of
    ingestions, not of the deck.

    ``project_id`` names the paper project the deck belongs to. The
    trajectory index's rows hang off the project the same way, and a deck
    whose project is deleted goes with it -- ``ON DELETE CASCADE``, the
    same rule the trajectory rows follow.

``ppt_fts``
    The FTS5 index over each object's text, on the **trigram** tokenizer
    for the same measured reason 0006 rebuilt ``evidence_fts`` and 0025
    reused: extracted slide text runs words together, and only a substring
    tokenizer finds them. Standalone rather than external-content, the id
    column ``UNINDEXED``, no triggers -- the application writes both tables
    in one transaction, the way the trajectory index's write does.

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
        "ppt_index_rows",
        sa.Column("object_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        # The deck's own identity: the content hash of the file the objects
        # were read from. Two decks with the same words are two decks, and
        # the hash is what says so.
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        # The slide the object sits on, 1-based -- the number a viewer
        # shows -- and the object's 1-based position within that slide, in
        # document order. Together with the kind they are the address §8.5
        # asks a hit to point at.
        sa.Column("slide_no", sa.Integer(), nullable=False),
        sa.Column("object_position", sa.Integer(), nullable=False),
        # 'title', 'body', 'notes', 'table' or 'image' -- the closed
        # vocabulary, because a row that is none of these is a row nobody
        # can render.
        sa.Column("object_kind", sa.String(length=32), nullable=False),
        # The object's own fingerprint, as the extraction recorded it: the
        # file's hash, the slide part and the object's XML path, folded.
        # Re-reading the same deck yields the same fingerprint, which is
        # what makes the derived id stable across re-ingestions.
        sa.Column("object_fingerprint", sa.Text(), nullable=False),
        # What the object says. A picture's text is its name -- the deck's
        # own word for the object -- and the kind column is what keeps
        # that distinction readable.
        sa.Column("text", sa.Text(), nullable=False),
        # The media part a picture references, resolved through the
        # slide's relationships, or NULL for every other kind. Naming the
        # part is what makes an image reference checkable.
        sa.Column("media_target", sa.Text(), nullable=True),
        # The structured locator, as JSON -- the PptxLocator's fields --
        # so a hit can hand back the address without re-deriving it.
        sa.Column("locator_json", sa.Text(), nullable=False),
        # When the object was indexed.
        sa.Column("ingested_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["paper_projects.project_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("object_id"),
        sa.CheckConstraint(
            "object_kind IN ('title', 'body', 'notes', 'table', 'image')",
            name="ppt_index_object_kind_vocabulary",
        ),
        sa.CheckConstraint(
            "slide_no >= 1 AND object_position >= 1",
            name="ppt_index_positions_positive",
        ),
        sa.CheckConstraint(
            "length(object_id) > 0 AND length(project_id) > 0",
            name="ppt_index_ids_present",
        ),
        sa.CheckConstraint(
            "length(trim(text)) > 0",
            name="ppt_index_text_present",
        ),
        sa.CheckConstraint(
            "length(source_sha256) = 64 AND source_sha256 NOT GLOB '*[^0-9a-f]*'",
            name="ppt_index_source_sha256_well_formed",
        ),
        sa.CheckConstraint(
            "length(trim(object_fingerprint)) > 0 AND length(trim(locator_json)) > 0",
            name="ppt_index_address_present",
        ),
    )
    op.create_index("ix_ppt_index_project", "ppt_index_rows", ["project_id"])
    op.create_index("ix_ppt_index_source", "ppt_index_rows", ["source_sha256"])

    # Standalone FTS5, trigram-tokenized, for the reason 0006 measured and
    # 0025 reused: slide text arrives with words run together, and a
    # substring tokenizer is the only thing that answers a substring
    # question over it. The id is UNINDEXED -- stored, not searchable -- so
    # a query for an id matches nothing by accident.
    op.execute(
        """
        CREATE VIRTUAL TABLE ppt_fts USING fts5(
            text,
            object_id UNINDEXED,
            tokenize = 'trigram'
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ppt_fts")
    op.drop_index("ix_ppt_index_source", table_name="ppt_index_rows")
    op.drop_index("ix_ppt_index_project", table_name="ppt_index_rows")
    op.drop_table("ppt_index_rows")
