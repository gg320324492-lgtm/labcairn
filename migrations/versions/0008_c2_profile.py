"""widen the C2 profile vocabulary with word-boundary removal

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-19

LC-P1-09 T06. Revision 0005 closed ``normalization_profile`` to three values.
C2 needs a fourth, and the reason is measured against this repository's own
papers rather than argued.

Of the 21 (phrase, page) pairs in ``tests/fixtures/retrieval/ground_truth.json``
whose phrase a human confirmed on the page, **14 appear character-for-character
in the stored text and 7 do not**:

    p10 of arx-2610.12393  "total correlation"  stored as "total correlation"
    p3  of arx-2610.09396  "Structured Disambiguation"  stored as
                           "StructuredDisambiguationforText-to-SQL"

The second is not a typo in the fixture. These PDFs space words by positioning
(ADR-0008 constraint 3), and pdfplumber *synthesises* the space from the gap
between glyph positions: the file draws almost no space glyphs at all. Whether a
given word pair comes out with a space is a property of the extractor in that
moment, not of the document. Page 10 of arx-2610.12393 contains both "total
correlation" with its space and "alignsfusedmodalitysubsetswith" without any of
its spaces.

A quotation check that answers ``fail`` whenever the characters do not line up
exactly calls a third of the corpus's genuine quotations unsupported. That is
the failure ADR-0004 R2 names -- a matcher that generates false negatives
teaches users to turn the check off -- except here the aggressiveness would not
even be visible, because the check would not have been lenient at all.

Measured before deciding, so the cost is a number rather than a worry:

  - verbatim match:                      14/21
  - match ignoring word boundaries:      21/21
  - false positives on the four negative
    queries (phrases absent from all
    three papers, including "retrieval
    augmented generation"):               0
  - paraphrase probes ("Dijkstra is
    greedy", "algorithm always picks
    nearest"):                           0

Removing boundaries recovers every genuine quotation and admits nothing that is
not there. It does not make a paraphrase match: a paraphrase differs in letters,
not in spaces.

**Matched this way is ``indeterminate``, never ``pass``.** That is ADR-0004 A4,
and it is why the new profile has to be a named member of the vocabulary rather
than an undocumented step inside C2: a log entry recording
``nfkc_whitespace_collapsed`` for a comparison that deleted every space would be
an audit row lying about how lenient the check was.

Rebuilt rather than altered, for the reason revision 0004 records: SQLite cannot
ALTER a CHECK constraint. The rows are copied unchanged; only the constraint text
differs.

Direct DDL, for the reason 0002 records: a frozen revision must not import
today's ``labcairn.db.models``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Spelled out rather than generated from the enum, because a frozen revision
#: must not depend on code that can change underneath it. ``models.py`` derives
#: the same list from ``NormalizationProfile``, and the schema parity test
#: compares the two.
WIDENED_VOCABULARY: tuple[str, ...] = (
    "exact",
    "nfkc_whitespace_collapsed",
    "nfkc_whitespace_collapsed_ligatures",
    "word_boundaries_removed",
)

#: What revision 0005 wrote, restored by a downgrade.
ORIGINAL_VOCABULARY: tuple[str, ...] = (
    "exact",
    "nfkc_whitespace_collapsed",
    "nfkc_whitespace_collapsed_ligatures",
)


def _verification_records(name: str, profiles: tuple[str, ...]) -> sa.Table:
    """The full ``verification_records`` definition, with *profiles* as its vocabulary."""
    return sa.Table(
        name,
        sa.MetaData(),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("evidence_id", sa.String(length=200), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("check_kind", sa.String(length=8), nullable=False),
        sa.Column("checker_id", sa.String(length=200), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("checked_at", sa.String(), nullable=False),
        sa.Column("normalization_profile", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_verification_records"),
        sa.UniqueConstraint("evidence_id", "seq", name="uq_verification_records_seq"),
        sa.CheckConstraint(
            "check_kind IN ('c1', 'c2', 'c3', 'c4')", name="verification_records_check_vocabulary"
        ),
        sa.CheckConstraint(
            "outcome IN ('fail', 'indeterminate', 'not_checked', 'pass')",
            name="verification_records_outcome_vocabulary",
        ),
        sa.CheckConstraint(
            "check_kind <> 'c4' OR outcome = 'not_checked'",
            name="verification_records_c4_never_passes",
        ),
        sa.CheckConstraint(
            "(check_kind = 'c2') = (normalization_profile IS NOT NULL)",
            name="verification_records_profile_belongs_to_c2",
        ),
        sa.CheckConstraint(
            "normalization_profile IS NULL OR normalization_profile IN "
            f"({', '.join(f'{value!r}' for value in profiles)})",
            name="verification_records_profile_vocabulary",
        ),
        sa.CheckConstraint("seq >= 1", name="verification_records_seq_positive"),
        sa.CheckConstraint(
            "length(evidence_id) > 0 AND length(checker_id) > 0 AND length(detail) > 0",
            name="verification_records_ids_present",
        ),
    )


def _rebuild(target: str, profiles: tuple[str, ...]) -> None:
    """Create ``target`` with *profiles*, copy every row into it, and make it the table."""
    table = _verification_records(target, profiles)
    op.create_table(target, *list(table.columns), *list(table.constraints))
    op.execute(
        f"INSERT INTO {target} (id, evidence_id, seq, schema_version, check_kind,"
        " checker_id, outcome, detail, checked_at, normalization_profile)"
        " SELECT id, evidence_id, seq, schema_version, check_kind, checker_id, outcome,"
        " detail, checked_at, normalization_profile FROM verification_records"
    )
    op.drop_index("ix_verification_records_evidence", table_name="verification_records")
    op.drop_table("verification_records")
    op.rename_table(target, "verification_records")
    op.create_index("ix_verification_records_evidence", "verification_records", ["evidence_id"])


def upgrade() -> None:
    _rebuild("verification_records_widened", WIDENED_VOCABULARY)


def downgrade() -> None:
    _rebuild("verification_records_original", ORIGINAL_VOCABULARY)
