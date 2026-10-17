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
source of truth: ADR-0004 rejects prose locators precisely because they cannot
be re-derived from anything, and this one is re-derivable from typed columns
that can be.

**Closed vocabularies.** ``locator_kind``, ``sources.kind`` and
``sources.readability`` are all constrained. Every shape check below is an
implication keyed on ``locator_kind``, so without a vocabulary an unrecognised
kind satisfies all of them vacuously with every typed column NULL — and the
readability pairing would be one-sided, letting ``'unreadable'`` through with
no disclosure and leaving ADR-0004 A7 unenforced by the database.

**``typeof()`` checks on the INTEGER columns.** SQLite will store the string
``'abc'`` in a declared INTEGER column and silently convert ``'1e3'`` to
1000. Comparisons do not catch it: INTEGER sorts before TEXT, so ``'abc' >= 1``
is TRUE and every ``>= 1`` constraint here is bypassable with a string.
``primitives.py`` names the conversion as exactly what this project exists to
prevent — a payload written where a string belonged is accepted, silently
rewritten, and nothing downstream can tell.

Stated because it is a real consequence: **this table holds text extracted
from the user's research material.** It is derived content, not the original
— the originals are read and never written — but deleting a source file does
not delete its text. Phase 1 has no "forget this material" operation, and
ADR-0009 records that as a gap rather than assuming it is someone else's
problem.

Direct DDL, not ``batch_alter_table``, for the reason 0002 records: batch mode
reflects the live schema and silently did nothing there. These are plain
CREATE TABLE statements, so there is nothing to reflect.

Every constraint here is mirrored in ``src/labcairn/db/models.py``, and
``test_the_migrated_schema_matches_the_orm_models`` compares the two on
column types, nullability, unique constraints and CHECK bodies — not just
column names. An earlier draft of this revision used ``sa.Text`` where the
models use ``sa.String`` for two ``UtcDateTime`` columns; SQLite treats them
alike so nothing failed, and the name-only guard could not see it.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: Exactly the code points str.strip() removes, verified against
#: str.isspace() by tests/test_material_schema.py. A comment in an earlier
#: draft said the remaining Unicode whitespace "cannot be expressed in a
#: CHECK" -- false, and worse than the bug it documented because it tells the
#: next reader to stop looking. A GLOB character class is one pattern term
#: however many characters it holds.
_NON_WHITESPACE_CODEPOINTS = (
    0x0009, 0x000A, 0x000B, 0x000C, 0x000D, 0x001C, 0x001D, 0x001E, 0x001F,
    0x0020, 0x0085, 0x00A0, 0x1680,
    0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006, 0x2007, 0x2008,
    0x2009, 0x200A, 0x2028, 0x2029, 0x202F, 0x205F, 0x3000,
)  # fmt: skip


def _whitespace_class() -> str:
    return "[" + "".join(chr(code) for code in _NON_WHITESPACE_CODEPOINTS) + "]"


def _has_content(column: str) -> str:
    """SQL for "this column holds at least one non-whitespace character"."""
    negated = "[" + chr(94) + _whitespace_class()[1:]
    return f"{column} GLOB '*{negated}*'"


def _no_edge_whitespace(column: str) -> str:
    """SQL for "this column neither begins nor ends with whitespace"."""
    cls = _whitespace_class()
    return f"{column} NOT GLOB '{cls}*' AND {column} NOT GLOB '*{cls}'"


def _a1_glob_check(column: str) -> str:
    """XlsxCellRef's ``^[A-Z]{1,3}[1-9][0-9]{0,6}$`` as GLOB alternatives.

    GLOB has no bounded repetition, so this expands to one alternative per
    (letters, digits) pair. Kept local rather than imported: a frozen
    migration must not depend on the live package.
    """
    alternatives = [
        f"{column} GLOB '{'[A-Z]' * letters}{'[1-9]' + '[0-9]' * (digits - 1)}'"
        for letters in range(1, 4)
        for digits in range(1, 8)
    ]
    return " OR ".join(alternatives)


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
        # sa.String for the same columns.
        sa.Column("ingested_at", sa.String(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("relative_path", name="uq_sources_relative_path"),
        sa.UniqueConstraint("source_id", name="uq_sources_source_id"),
        sa.CheckConstraint("size_bytes >= 0", name="source_size_non_negative"),
        sa.CheckConstraint(
            "kind IN ('pdf', 'markdown', 'text', 'csv', 'xlsx', 'other')",
            name="source_kind_vocabulary",
        ),
        sa.CheckConstraint(
            "readability IN ('readable', 'unreadable_no_ocr')",
            name="source_readability_vocabulary",
        ),
        # ADR-0004 A7: "we could not look" is not "there was nothing there".
        sa.CheckConstraint(
            "(readability = 'unreadable_no_ocr') = (readability_disclosure IS NOT NULL)",
            name="source_disclosure_paired",
        ),
        sa.CheckConstraint(
            "readability_disclosure IS NULL OR " + _has_content("readability_disclosure"),
            name="source_disclosure_non_empty",
        ),
        # Defence in depth behind require_workspace_relative, not a copy of it.
        sa.CheckConstraint(
            "relative_path NOT GLOB '/*' AND relative_path NOT GLOB '*\\*' "
            "AND relative_path NOT GLOB '../*' AND relative_path NOT GLOB '*/../*' "
            "AND relative_path NOT GLOB '*/..' AND relative_path <> '..' "
            "AND relative_path NOT GLOB './*' AND relative_path NOT GLOB '*/./*' "
            "AND relative_path NOT GLOB '*/.' AND relative_path <> '.' "
            "AND " + _has_content("relative_path"),
            name="source_relative_path_workspace_relative",
        ),
        # Also refused: a drive letter written with forward slashes, an empty
        # path segment, and surrounding whitespace.
        sa.CheckConstraint(
            "relative_path NOT GLOB '[A-Za-z]:*' "
            "AND relative_path NOT LIKE '%/' AND relative_path NOT LIKE '%//%' "
            "AND " + _no_edge_whitespace("relative_path"),
            name="source_relative_path_no_empty_segment",
        ),
        sa.CheckConstraint(
            "length(content_sha256) = 64 AND content_sha256 NOT GLOB '*[^0-9a-f]*'",
            name="source_content_sha256_shape",
        ),
        sa.CheckConstraint(_has_content("display_name"), name="source_display_name_non_empty"),
        sa.CheckConstraint(_has_content("source_id"), name="source_id_non_empty"),
        sa.CheckConstraint(_has_content("owner_id"), name="source_owner_id_non_empty"),
        sa.CheckConstraint("typeof(size_bytes) = 'integer'", name="source_size_bytes_is_integer"),
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
        # Implied by the exhaustive shape checks above; kept for readability,
        # not because they constrain anything a shape check does not.
        sa.CheckConstraint(
            "line_end IS NULL OR locator_kind = 'text'",
            name="source_texts_line_end_is_text",
        ),
        sa.CheckConstraint(
            "section IS NULL OR locator_kind = 'text'",
            name="source_texts_section_is_text",
        ),
        sa.CheckConstraint(
            "section IS NULL OR " + _has_content("section"),
            name="source_texts_section_non_empty",
        ),
        sa.CheckConstraint(
            "column_name IS NULL OR " + _has_content("column_name"),
            name="source_texts_column_name_non_empty",
        ),
        sa.CheckConstraint(
            "sheet_name IS NULL OR " + _has_content("sheet_name"),
            name="source_texts_sheet_name_non_empty",
        ),
        # The key column of the key table. It had no shape constraint at all,
        # so '', 'not-a-hash' and '../../etc/passwd' were storable -- and since
        # the UNIQUE is (sha, version, locator_key), two rows with '' and
        # different versions coexist as "the same content".
        sa.CheckConstraint(
            "length(source_content_sha256) = 64 AND source_content_sha256 NOT GLOB '*[^0-9a-f]*'",
            name="source_texts_content_sha256_shape",
        ),
        # SQLite stores 'abc' in a declared INTEGER column and converts '1e3'
        # to 1000 silently; INTEGER sorts before TEXT so 'abc' >= 1 is TRUE.
        sa.CheckConstraint(
            "(page IS NULL) OR typeof(page) = 'integer'",
            name="source_texts_page_is_integer",
        ),
        sa.CheckConstraint(
            "(line_start IS NULL) OR typeof(line_start) = 'integer'",
            name="source_texts_line_start_is_integer",
        ),
        sa.CheckConstraint(
            "(line_end IS NULL) OR typeof(line_end) = 'integer'",
            name="source_texts_line_end_is_integer",
        ),
        sa.CheckConstraint(
            "(row_number IS NULL) OR typeof(row_number) = 'integer'",
            name="source_texts_row_number_is_integer",
        ),
        sa.CheckConstraint(_a1_glob_check("cell_ref"), name="source_texts_cell_ref_a1"),
        sa.CheckConstraint(
            _has_content("locator_key") + " AND " + _has_content("extraction_version"),
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
