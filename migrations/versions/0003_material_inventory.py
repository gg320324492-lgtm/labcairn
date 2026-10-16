"""materials and their extracted text

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-17

LC-P1-08, per ADR-0009. The store held outputs (``artifacts``) and nothing
held the inputs a report cites. LC-P1-02 froze ``Source`` and ``SourceAnchor``
as contracts and LC-P1-05 never persisted them, so a locator could only be
resolved by re-reading a file with a parser at the moment somebody checked it.

Two tables:

``sources`` — the material itself: workspace-relative path, content hash,
size, readability, and a disclosure that is required when unreadable and
forbidden when readable. There is no ``task_id``: a material belongs to the
workspace and must outlive the Tasks citing it.

``source_texts`` — extracted text for one addressable place, keyed by
``(source_content_sha256, extraction_version, locator)``. The content hash
binds text to the exact bytes it came from, so a modified file cannot inherit
old text and ADR-0004's A2 hash drift fires instead of a silent re-read. The
extraction version keeps a new extraction beside an old one rather than
overwriting it, so an anchor written under the old version still resolves and
the divergence is detectable. Both columns together make extraction
effectively content-addressed: same bytes plus same extractor yields the same
row, so re-ingesting an unchanged file is idempotent.

**Why ``locator_key`` exists at all.** SQLite treats NULLs as distinct inside
a UNIQUE index, so a unique constraint spanning the nullable typed locator
columns would not constrain a single row — the constraint would look present
and enforce nothing. ``locator_key`` is a canonical NOT NULL rendering of
those columns and is what makes the key enforceable. It is derived, never the
source of truth: ADR-0004 rejects prose locators because they cannot be
re-derived from anything, and this one is re-derivable from typed columns that
can be.

Stated because it is a real consequence: **this table holds text extracted
from the user's research material.** It is derived content, not the original
— the originals are read and never written — but deleting a source file does
not delete its text. Phase 1 has no "forget this material" operation, and
ADR-0009 records that as a gap rather than assuming it is someone else's
problem.

Direct DDL, not ``batch_alter_table``, for the reason 0002 records: batch mode
reflects the live schema and silently did nothing there. These are plain
CREATE TABLE statements, so there is nothing to reflect.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("owner_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=2000), nullable=False),
        sa.Column("relative_path", sa.String(length=2000), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("readability", sa.String(length=32), nullable=False),
        sa.Column("readability_disclosure", sa.Text(), nullable=True),
        sa.Column("identifiers", sa.JSON(), nullable=False),
        sa.Column("ingested_at", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("relative_path", name="uq_sources_relative_path"),
        sa.UniqueConstraint("source_id", name="uq_sources_source_id"),
        sa.CheckConstraint("size_bytes >= 0", name="source_size_non_negative"),
        # ADR-0004 A7: "we could not look" is not "there was nothing there".
        sa.CheckConstraint(
            "(readability = 'unreadable_no_ocr') = (readability_disclosure IS NOT NULL)",
            name="source_disclosure_paired",
        ),
    )
    op.create_index("ix_sources_content_sha256", "sources", ["content_sha256"])

    op.create_table(
        "source_texts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_content_sha256", sa.String(length=64), nullable=False),
        sa.Column("extraction_version", sa.String(length=64), nullable=False),
        sa.Column("locator_kind", sa.String(length=32), nullable=False),
        sa.Column("locator_key", sa.String(length=2000), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("line_start", sa.Integer(), nullable=True),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(length=2000), nullable=True),
        sa.Column("row_number", sa.Integer(), nullable=True),
        sa.Column("column_name", sa.String(length=2000), nullable=True),
        sa.Column("sheet_name", sa.String(length=2000), nullable=True),
        sa.Column("cell_ref", sa.String(length=200), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_content_sha256",
            "extraction_version",
            "locator_key",
            name="uq_source_texts_address",
        ),
        # Exactly the typed columns each kind defines, and no others. A
        # half-populated locator resolves to the wrong thing silently.
        sa.CheckConstraint(
            "locator_kind <> 'pdf' OR (page IS NOT NULL AND line_start IS NULL "
            "AND line_end IS NULL AND section IS NULL AND row_number IS NULL "
            "AND column_name IS NULL AND sheet_name IS NULL AND cell_ref IS NULL)",
            name="source_texts_pdf_shape",
        ),
        # A text locator is defined by its line, and nothing else kind is
        # allowed to carry one. Written as an equivalence rather than an
        # implication: the other way round rejects every PDF, CSV and XLSX
        # row for lacking a line number.
        sa.CheckConstraint(
            "(locator_kind = 'text') = (line_start IS NOT NULL)",
            name="source_texts_text_shape",
        ),
        sa.CheckConstraint(
            "locator_kind <> 'csv' OR (row_number IS NOT NULL AND column_name IS NOT NULL "
            "AND page IS NULL AND line_start IS NULL AND sheet_name IS NULL)",
            name="source_texts_csv_shape",
        ),
        sa.CheckConstraint(
            "locator_kind <> 'xlsx' OR (sheet_name IS NOT NULL AND cell_ref IS NOT NULL "
            "AND page IS NULL AND line_start IS NULL AND row_number IS NULL)",
            name="source_texts_xlsx_shape",
        ),
        sa.CheckConstraint("page IS NULL OR page >= 1", name="source_texts_page_positive"),
        sa.CheckConstraint(
            "row_number IS NULL OR row_number >= 1", name="source_texts_row_positive"
        ),
        sa.CheckConstraint(
            "line_start IS NULL OR (line_start >= 1 "
            "AND (line_end IS NULL OR line_end >= line_start))",
            name="source_texts_line_range",
        ),
    )
    op.create_index("ix_source_texts_sha", "source_texts", ["source_content_sha256"])


def downgrade() -> None:
    op.drop_index("ix_source_texts_sha", table_name="source_texts")
    op.drop_table("source_texts")
    op.drop_index("ix_sources_content_sha256", table_name="sources")
    op.drop_table("sources")
