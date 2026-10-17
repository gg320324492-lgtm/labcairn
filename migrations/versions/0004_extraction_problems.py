"""extraction problems, and a third readability state

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-17

LC-P1-08, prompted by a review finding. Every adapter in
``labcairn.material`` produces ``ExtractionProblem`` records -- why a
workbook would not open, why a cell holds a formula whose result is not
stored, why a sheet is empty -- and until this revision **nothing wrote
them anywhere**. They were returned to a caller and dropped.

That is worse than not having them. ``sources.readability_disclosure``
cannot hold them: the contract requires a disclosure exactly when a
source is *not* readable and forbids one when it is, so a file that
opened perfectly and produced three disclosures had nowhere to put any
of them. A disclosure with no destination is not a disclosure -- the
argument ``db/models.py`` already makes about ``readability_disclosure``
itself, that a disclosure nobody has to write is a disclosure nobody
writes.

The key is ``(source_id, extraction_version, code, location)`` so
re-ingesting an unchanged file writes nothing. Location is a **not-null
sentinel** rather than a nullable column, because SQLite compares NULLs
as distinct inside a UNIQUE index: a nullable location would make "the
same whole-file problem, once per run" a success.

This revision also adds ``readability = 'unparseable'``. ADR-0010
explains why: the two-member vocabulary from LC-P1-02 had no honest
answer for material this project cannot read, and both available answers
were false.

SQLite cannot ALTER a CHECK constraint, so ``sources`` is rebuilt with
the widened vocabulary. The table is written out in full rather than
patched, and the index is recreated because dropping a table drops its
indexes -- a schema that lost one silently would not fail anything.
``test_the_migrated_schema_matches_the_orm_models`` compares types,
nullability, unique constraints and CHECK bodies, so a divergence here is
a test failure rather than a discovery.

Direct DDL, for the reason 0002 records. The helpers below are copied
from 0003, not imported: a frozen revision must not depend on today's
source.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Written in place of a null location so the unique key works at all.
WHOLE_FILE = chr(0) + "whole-file"


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


def upgrade() -> None:
    op.create_table(
        "sources_rebuilt",
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
            "readability IN ('readable', 'unreadable_no_ocr', 'unparseable')",
            name="source_readability_vocabulary",
        ),
        # ADR-0004 A7. Any non-readable state owes a reason; a readable one
        # must not carry one, because a disclosure about something that did
        # not happen is itself a false claim.
        sa.CheckConstraint(
            "(readability <> 'readable') = (readability_disclosure IS NOT NULL)",
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
    op.execute(
        "INSERT INTO sources_rebuilt SELECT id, source_id, owner_id, kind, display_name, "
        "relative_path, content_sha256, size_bytes, readability, readability_disclosure, "
        "identifiers, ingested_at, schema_version FROM sources"
    )
    op.drop_index("ix_sources_content_sha256", table_name="sources")
    op.drop_table("sources")
    op.rename_table("sources_rebuilt", "sources")
    op.create_index("ix_sources_content_sha256", "sources", ["content_sha256"])

    op.create_table(
        "source_problems",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("extraction_version", sa.String(length=64), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("location", sa.String(length=2000), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id", "extraction_version", "code", "location", name="uq_source_problems"
        ),
        # A disclosure with no detail is not a disclosure.
        sa.CheckConstraint("length(trim(detail)) > 0", name="source_problem_detail_non_empty"),
    )
    op.create_index("ix_source_problems_source_id", "source_problems", ["source_id"])


def downgrade() -> None:
    op.drop_index("ix_source_problems_source_id", table_name="source_problems")
    op.drop_table("source_problems")
    # ``sources`` keeps the three-member vocabulary. Narrowing it back would
    # refuse a database legitimately holding an UNPARSEABLE row, and refusing
    # a downgrade that would lose a truthful record is worse than a schema
    # that stayed wider than its predecessor.
