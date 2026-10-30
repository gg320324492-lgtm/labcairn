"""the DOCX locator: a package part, an element path, a view and a range

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-29

LC-P2-07. Revision 0007 created the anchor registry, and its ``locator_key``
CHECK admits four kinds -- ``pdf``, ``text``, ``csv``, ``xlsx``. A Word
document had no kind, so a ``.docx`` was inventoried and hashed as
``SourceKind.OTHER`` and could not be cited at all.

**The gap was the format, and the format is unusual.** Every other kind
addresses a place by a coordinate the format itself provides: a page, a
line, a row and column, a sheet and cell. A Word document has none of
those. Its addressable structure is **XML**: a package part, an element in
it, and a character range within that element's text. So the kind is
additive rather than a widening -- a fifth kind with its own columns -- and
this revision gives the table those columns.

**Why the view is a column and not a convention.** A ``.docx`` with
tracked changes holds two texts at once, and ADR-0014 D4 names them: the
*accepted* text and the *rejected* text. The same character range means
different characters in each. An address that could mean either is not an
address, so the view is part of the address and therefore part of the key.
Two locators for the same element in different views are different
addresses, and they resolve to different text -- which is correct, because
they *are* different text.

**The deleted text is the reason the range exists.** The text an advisor
deleted is not in the accepted view at all, so no range there could name
it. It is in the *rejected* view, and a ``w:del`` element's text in the
rejected view is exactly that text. A DOCX address therefore reaches the
deleted text, which is the whole of the phase's thesis: for a project
whose subject is *how a paper was corrected*, the correction is the signal
and the signal must be addressable.

**The four existing shape checks were widened, and that widening is
load-bearing.** Each shape check asserts that a row of one kind carries
exactly that kind's columns and none of another's. They are exhaustive on
purpose: an earlier draft constrained only the columns a kind *uses*, so a
row could claim to be a text locator and a PDF page and a CSV cell at once
-- a row no conforming code can produce and none can consume. Adding five
columns without widening the four checks would have reopened exactly that
hole, so every one of them now also says the DOCX columns are NULL, and
the DOCX check says the other eight are.

**Direct DDL, for the reason 0007 records.** A frozen revision must not
import today's ``labcairn.db.models``, or editing that class would
silently rewrite what this revision meant to create.
``tests/test_store_migrations.py``'s parity test is what holds the two
together, and the rows this revision must refuse are witnessed again by
writing them -- a text comparison cannot catch a migration and a model
wrong together.

**SQLite cannot ALTER a CHECK constraint**, so both tables are rebuilt in
batch mode -- copy, drop, recreate, copy back. That is Alembic's
``batch_alter_table`` doing the copy-and-drop dance the environment's
``render_as_batch = True`` exists for.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: The locator kinds the store can resolve, in the order the checks name
#: them. Generated from each kind's spelling length, because the length
#: prefix is not constant -- see the module docstring.
_KINDS: tuple[str, ...] = ("pdf", "text", "csv", "xlsx", "docx")


def _locator_kind_glob_check() -> str:
    """The GLOB on ``locator_key``'s leading ``k=`` component.

    **No ``?`` wildcard.** SQLAlchemy reads ``:csv`` as a bind parameter,
    so a pattern with one compiled to a literal that matched nothing, and
    the parity test passed straight through it because the migration and
    the ORM were mangled identically. Only writing a row that must be
    refused catches that, and ``tests/test_material_schema.py`` writes one.
    """
    return " OR ".join(f"locator_key GLOB 'k={len(kind)}:{kind}|*'" for kind in _KINDS)


def _docx_null_clause() -> str:
    """The clause that pins the DOCX columns to NULL for the other kinds."""
    return (
        "AND docx_part IS NULL AND docx_element_path IS NULL AND docx_view IS NULL "
        "AND docx_char_start IS NULL AND docx_char_end IS NULL"
    )


def upgrade() -> None:
    with op.batch_alter_table("source_texts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("docx_part", sa.String(200), nullable=True))
        batch_op.add_column(sa.Column("docx_element_path", sa.String(2000), nullable=True))
        batch_op.add_column(sa.Column("docx_view", sa.String(16), nullable=True))
        batch_op.add_column(sa.Column("docx_char_start", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("docx_char_end", sa.Integer(), nullable=True))

        # The kind vocabulary widens by one.
        batch_op.drop_constraint("source_texts_kind_vocabulary", type_="check")
        batch_op.create_check_constraint(
            "source_texts_kind_vocabulary",
            "locator_kind IN ('pdf', 'text', 'csv', 'xlsx', 'docx')",
        )

        # The four shape checks widen: each now also says the DOCX columns
        # are NULL, so a row cannot claim to be two kinds at once.
        batch_op.drop_constraint("source_texts_pdf_shape", type_="check")
        batch_op.create_check_constraint(
            "source_texts_pdf_shape",
            "locator_kind <> 'pdf' OR (page IS NOT NULL AND line_start IS NULL "
            "AND line_end IS NULL AND section IS NULL AND row_number IS NULL "
            "AND column_name IS NULL AND sheet_name IS NULL AND cell_ref IS NULL "
            + _docx_null_clause()
            + ")",
        )

        batch_op.drop_constraint("source_texts_text_shape", type_="check")
        batch_op.create_check_constraint(
            "source_texts_text_shape",
            "locator_kind <> 'text' OR (line_start IS NOT NULL AND page IS NULL "
            "AND row_number IS NULL AND column_name IS NULL AND sheet_name IS NULL "
            "AND cell_ref IS NULL " + _docx_null_clause() + ")",
        )

        batch_op.drop_constraint("source_texts_csv_shape", type_="check")
        batch_op.create_check_constraint(
            "source_texts_csv_shape",
            "locator_kind <> 'csv' OR (row_number IS NOT NULL AND column_name IS NOT NULL "
            "AND page IS NULL AND line_start IS NULL AND line_end IS NULL "
            "AND section IS NULL AND sheet_name IS NULL AND cell_ref IS NULL "
            + _docx_null_clause()
            + ")",
        )

        batch_op.drop_constraint("source_texts_xlsx_shape", type_="check")
        batch_op.create_check_constraint(
            "source_texts_xlsx_shape",
            "locator_kind <> 'xlsx' OR (sheet_name IS NOT NULL AND cell_ref IS NOT NULL "
            "AND page IS NULL AND line_start IS NULL AND line_end IS NULL "
            "AND section IS NULL AND row_number IS NULL AND column_name IS NULL "
            + _docx_null_clause()
            + ")",
        )

        # And the DOCX shape says the other eight are NULL, that the view
        # is one of the two ADR-0014 D4 views, and that the range's
        # endpoints are both set or neither.
        batch_op.create_check_constraint(
            "source_texts_docx_shape",
            "locator_kind <> 'docx' OR (docx_part IS NOT NULL "
            "AND docx_element_path IS NOT NULL AND docx_view IS NOT NULL "
            "AND docx_view IN ('accepted', 'rejected') "
            "AND ((docx_char_start IS NULL AND docx_char_end IS NULL) "
            "OR (docx_char_start IS NOT NULL AND docx_char_end IS NOT NULL "
            "AND docx_char_end >= docx_char_start)) "
            "AND page IS NULL AND line_start IS NULL AND line_end IS NULL "
            "AND section IS NULL AND row_number IS NULL AND column_name IS NULL "
            "AND sheet_name IS NULL AND cell_ref IS NULL)",
        )

    with op.batch_alter_table("source_anchors", schema=None) as batch_op:
        batch_op.drop_constraint("source_anchors_locator_key_vocabulary", type_="check")
        batch_op.create_check_constraint(
            "source_anchors_locator_key_vocabulary",
            _locator_kind_glob_check(),
        )


def downgrade() -> None:
    with op.batch_alter_table("source_anchors", schema=None) as batch_op:
        batch_op.drop_constraint("source_anchors_locator_key_vocabulary", type_="check")
        batch_op.create_check_constraint(
            "source_anchors_locator_key_vocabulary",
            " OR ".join(
                f"locator_key GLOB 'k={len(kind)}:{kind}|*'"
                for kind in ("pdf", "text", "csv", "xlsx")
            ),
        )

    with op.batch_alter_table("source_texts", schema=None) as batch_op:
        batch_op.drop_constraint("source_texts_docx_shape", type_="check")
        batch_op.drop_constraint("source_texts_xlsx_shape", type_="check")
        batch_op.create_check_constraint(
            "source_texts_xlsx_shape",
            "locator_kind <> 'xlsx' OR (sheet_name IS NOT NULL AND cell_ref IS NOT NULL "
            "AND page IS NULL AND line_start IS NULL AND line_end IS NULL "
            "AND section IS NULL AND row_number IS NULL AND column_name IS NULL)",
        )
        batch_op.drop_constraint("source_texts_csv_shape", type_="check")
        batch_op.create_check_constraint(
            "source_texts_csv_shape",
            "locator_kind <> 'csv' OR (row_number IS NOT NULL AND column_name IS NOT NULL "
            "AND page IS NULL AND line_start IS NULL AND line_end IS NULL "
            "AND section IS NULL AND sheet_name IS NULL AND cell_ref IS NULL)",
        )
        batch_op.drop_constraint("source_texts_text_shape", type_="check")
        batch_op.create_check_constraint(
            "source_texts_text_shape",
            "locator_kind <> 'text' OR (line_start IS NOT NULL AND page IS NULL "
            "AND row_number IS NULL AND column_name IS NULL AND sheet_name IS NULL "
            "AND cell_ref IS NULL)",
        )
        batch_op.drop_constraint("source_texts_pdf_shape", type_="check")
        batch_op.create_check_constraint(
            "source_texts_pdf_shape",
            "locator_kind <> 'pdf' OR (page IS NOT NULL AND line_start IS NULL "
            "AND line_end IS NULL AND section IS NULL AND row_number IS NULL "
            "AND column_name IS NULL AND sheet_name IS NULL AND cell_ref IS NULL)",
        )
        batch_op.drop_constraint("source_texts_kind_vocabulary", type_="check")
        batch_op.create_check_constraint(
            "source_texts_kind_vocabulary",
            "locator_kind IN ('pdf', 'text', 'csv', 'xlsx')",
        )

        batch_op.drop_column("docx_char_end")
        batch_op.drop_column("docx_char_start")
        batch_op.drop_column("docx_view")
        batch_op.drop_column("docx_element_path")
        batch_op.drop_column("docx_part")
