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
        # sa.String, not sa.Text: UtcDateTime's impl is String, and 0001 used
        # sa.String for the same columns. An earlier draft of this revision
        # used sa.Text, which SQLite treats identically but which the project's
        # own migration test docstring says to render as the underlying
        # sa.String. The parity test now compares types, so the drift is caught
        # rather than invisible.
        sa.Column("ingested_at", sa.String(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("relative_path", name="uq_sources_relative_path"),
        sa.UniqueConstraint("source_id", name="uq_sources_source_id"),
        sa.CheckConstraint("size_bytes >= 0", name="source_size_non_negative"),
        # Closed vocabulary, mirroring events.type. Without it the pairing
        # below is one-sided: 'unreadable' with no disclosure would sail
        # through and ADR-0004 A7 would not be enforced by the database.
        sa.CheckConstraint(
            "kind IN ('pdf', 'markdown', 'text', 'csv', 'xlsx', 'other')",
            name="source_kind_vocabulary",
        ),
        sa.CheckConstraint(
            "readability IN ('readable', 'unreadable_no_ocr')",
            name="source_readability_vocabulary",
        ),
        sa.CheckConstraint(
            "(readability = 'unreadable_no_ocr') = (readability_disclosure IS NOT NULL)",
            name="source_disclosure_paired",
        ),
        # Paired is not the same as meaningful.
        sa.CheckConstraint(
            "readability_disclosure IS NULL OR length(trim(readability_disclosure)) > 0",
            name="source_disclosure_non_empty",
        ),
        # Defence in depth behind require_workspace_relative, not a second
        # implementation of it: refuses absolute, parent-escaping, Windows
        # separator and '.' segment shapes if a row bypasses the validator.
        sa.CheckConstraint(
            "relative_path NOT GLOB '/*' AND relative_path NOT GLOB '*\\*' "
            "AND relative_path NOT GLOB '../*' AND relative_path NOT GLOB '*/../*' "
            "AND relative_path NOT GLOB '*/..' AND relative_path <> '..' "
            "AND relative_path NOT GLOB './*' AND relative_path NOT GLOB '*/./*' "
            "AND relative_path NOT GLOB '*/.' AND relative_path <> '.' "
            "AND length(trim(relative_path)) > 0",
            name="source_relative_path_workspace_relative",
        ),
        sa.CheckConstraint(
            "length(content_sha256) = 64 AND content_sha256 NOT GLOB '*[^0-9a-f]*'",
            name="source_content_sha256_shape",
        ),
        sa.CheckConstraint("length(trim(display_name)) > 0", name="source_display_name_non_empty"),
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
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_content_sha256",
            "extraction_version",
            "locator_key",
            name="uq_source_texts_address",
        ),
        # Closed vocabulary. Every shape check below is an implication keyed on
        # locator_kind, so an unrecognised kind satisfies all of them
        # vacuously with every typed column NULL.
        sa.CheckConstraint(
            "locator_kind IN ('pdf', 'text', 'csv', 'xlsx')",
            name="source_texts_kind_vocabulary",
        ),
        # Exhaustive: each names every column, not just the ones its kind uses.
        # An earlier draft constrained only those, so a row could claim to be a
        # text locator and a PDF page and a CSV cell at once.
        sa.CheckConstraint(
            "locator_kind <> 'pdf' OR (page IS NOT NULL AND line_start IS NULL "
            "AND line_end IS NULL AND section IS NULL AND row_number IS NULL "
            "AND column_name IS NULL AND sheet_name IS NULL AND cell_ref IS NULL)",
            name="source_texts_pdf_shape",
        ),
        sa.CheckConstraint(
            "locator_kind <> 'text' OR (line_start IS NOT NULL AND page IS NULL "
            "AND row_number IS NULL AND column_name IS NULL AND sheet_name IS NULL "
            "AND cell_ref IS NULL)",
            name="source_texts_text_shape",
        ),
        sa.CheckConstraint(
            "locator_kind <> 'csv' OR (row_number IS NOT NULL AND column_name IS NOT NULL "
            "AND page IS NULL AND line_start IS NULL AND line_end IS NULL "
            "AND section IS NULL AND sheet_name IS NULL AND cell_ref IS NULL)",
            name="source_texts_csv_shape",
        ),
        sa.CheckConstraint(
            "locator_kind <> 'xlsx' OR (sheet_name IS NOT NULL AND cell_ref IS NOT NULL "
            "AND page IS NULL AND line_start IS NULL AND line_end IS NULL "
            "AND section IS NULL AND row_number IS NULL AND column_name IS NULL)",
            name="source_texts_xlsx_shape",
        ),
        # Only text may carry a line range or a section.
        sa.CheckConstraint(
            "line_end IS NULL OR locator_kind = 'text'",
            name="source_texts_line_end_is_text",
        ),
        sa.CheckConstraint(
            "section IS NULL OR locator_kind = 'text'",
            name="source_texts_section_is_text",
        ),
        sa.CheckConstraint(
            "length(trim(locator_key)) > 0 AND length(trim(extraction_version)) > 0",
            name="source_texts_key_non_empty",
        ),
        sa.CheckConstraint(
            "length(text_sha256) = 64 AND text_sha256 NOT GLOB '*[^0-9a-f]*'",
            name="source_texts_text_sha256_shape",
        ),
        # Bounded by what a consumer can accept: UntrustedText refuses above
        # two million characters, so a longer row could never be read back
        # through the only sanctioned path.
        sa.CheckConstraint("length(text) <= 2000000", name="source_texts_text_length"),
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
