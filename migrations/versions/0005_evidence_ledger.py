"""the evidence ledger: records, anchors, verification log, and the index

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-18

LC-P1-09. ADR-0004 Contract 1 types the evidence records in Pydantic and every
invariant on them is already a validator there. What was missing was anywhere
to put them -- the same defect revision 0004 records for extraction problems:
records were produced, returned to a caller, and dropped.

The ledger is also the first thing in this schema that must answer a question
about **absence**. C1, C2 and C3 currently raise
``CiteSupportNotImplementedError`` because deciding whether a quotation is
verbatim needs a real index and deciding whether a number agrees needs the
parsed cell behind the anchor. This revision creates the storage both need --
and deliberately does not implement them, because a check that answers from an
empty index cannot be told apart from one that passed.

**The FTS5 table is standalone, not external-content.** External content
(``content=``) makes the content table authoritative and turns a stale index
into a corruption rather than a rebuild; the text would then be indexed by
reference and a wrong ``content_rowid`` reads a neighbouring row silently.
Standalone duplicates the normalised text, which is acceptable because the text
here is an index-side *copy*: ``source_texts`` remains the only authority, and
LC-P1-09's T02 writes the normalised copy without ever mutating it. The
identity columns are carried UNINDEXED so a hit can name the exact locator it
came from -- a hit that cannot name its address is not a citation.

**The FTS5 table is deliberately absent from the ORM metadata.** SQLAlchemy has
no first-class model for an FTS5 virtual table, and inventing one would make
``test_the_migrated_schema_matches_the_orm_models`` compare a virtual table
against a DDL string. It is created here by raw DDL and owned by LC-P1-09's
T03, and it is the one object in this schema whose absence from ``Base`` is
intentional.

**If FTS5 is unavailable this migration fails.** It does not fall back to a
plain table. A database that upgraded cleanly but cannot retrieve would report
itself as migrated, and every downstream query would return an empty result
that reads exactly like "the material does not say that". That is the failure
this project keeps having to unpick, in the one place an index failure is
indistinguishable from a negative finding.

Direct DDL, for the reason 0002 records: a frozen revision must not depend on
today's source, and ``test_the_migration_does_not_import_labcairn`` enforces
it. The CHECK bodies below are written out in full and must stay textually
identical to the ORM metadata modulo whitespace, because that test compares
them rather than trusting a hand-maintained copy.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: An evidence record past ``planned`` carries at least this many anchors. A
#: CHECK cannot read a join table, so the ORM keeps a canonical, re-derivable
#: rendering of the anchors beside the record and the constraint reads that --
#: the trade ``source_texts.locator_key`` already makes for the same reason.
#: An empty anchor set renders as this, and nothing else.
EMPTY_ANCHOR_KEY = "[]"


def upgrade() -> None:
    op.create_table(
        "evidence_anchors",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("evidence_id", sa.String(length=200), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("anchor_id", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        # Not a foreign key to the anchor table: an anchor id naming nothing is
        # a fabricated source, and C1 is what must catch that as a verdict.
        # A foreign key would make the row unstorable instead, turning a
        # checkable failure into a constraint error no caller can read.
        sa.UniqueConstraint("evidence_id", "position", name="uq_evidence_anchors_position"),
        sa.UniqueConstraint("evidence_id", "anchor_id", name="uq_evidence_anchors_anchor"),
        sa.CheckConstraint("position >= 0", name="evidence_anchors_position_non_negative"),
        sa.CheckConstraint(
            "length(anchor_id) > 0 AND length(evidence_id) > 0",
            name="evidence_anchors_ids_present",
        ),
    )
    op.create_index("ix_evidence_anchors_anchor", "evidence_anchors", ["anchor_id"])

    op.create_table(
        "evidence_records",
        sa.Column("evidence_id", sa.String(length=200), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        # Nullable because a numeric record must say "no text" rather than
        # omitting it -- and in a row every column is present by construction,
        # so nullable is the faithful shape of that rule.
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("unit", sa.String(length=200), nullable=True),
        sa.Column("tolerance", sa.Float(), nullable=True),
        sa.Column("anchor_key", sa.Text(), nullable=False),
        sa.Column("extracted_span", sa.Text(), nullable=True),
        sa.Column("extracted_span_sha256", sa.String(length=64), nullable=True),
        sa.Column("source_content_hash", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=32), nullable=False),
        sa.Column("created_by_id", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("superseded_by", sa.String(length=200), nullable=True),
        sa.PrimaryKeyConstraint("evidence_id"),
        sa.UniqueConstraint("task_id", "extracted_span_sha256", name="uq_evidence_task_span"),
        sa.CheckConstraint(
            "kind IN ('claim', 'numeric', 'result')", name="evidence_records_kind_vocabulary"
        ),
        sa.CheckConstraint(
            "status IN ('conflicted', 'extracted', 'planned', 'unsupported', "
            "'user_attested', 'verified_by_rule')",
            name="evidence_records_status_vocabulary",
        ),
        sa.CheckConstraint(
            "created_by IN ('model_proposal', 'rule', 'user')",
            name="evidence_records_creator_vocabulary",
        ),
        # A sentence attached to a number is a second claim no check will ever
        # look at, so the two are mutually exclusive rather than discouraged.
        sa.CheckConstraint(
            "(kind <> 'numeric' OR (text IS NULL AND value IS NOT NULL AND unit IS NOT NULL)) "
            "AND (kind = 'numeric' OR (text IS NOT NULL AND value IS NULL "
            "AND unit IS NULL AND tolerance IS NULL))",
            name="evidence_records_kind_fields",
        ),
        # Quoted text without its hash cannot be checked for drift; a hash
        # without the text cannot be shown to anyone.
        sa.CheckConstraint(
            "(extracted_span IS NULL) = (extracted_span_sha256 IS NULL)",
            name="evidence_records_span_all_or_nothing",
        ),
        # Everything past ``planned`` claims to have been located, so it must
        # carry what a location is made against. Whether the anchor *resolves*
        # is C1's call and deliberately not this constraint's.
        sa.CheckConstraint(
            "status = 'planned' OR (extracted_span IS NOT NULL "
            "AND extracted_span_sha256 IS NOT NULL AND source_content_hash IS NOT NULL "
            f"AND anchor_key <> '{EMPTY_ANCHOR_KEY}')",
            name="evidence_records_located_past_planned",
        ),
        sa.CheckConstraint(
            "length(evidence_id) > 0 AND length(task_id) > 0 AND length(created_by_id) > 0",
            name="evidence_records_ids_present",
        ),
        sa.CheckConstraint(
            "(extracted_span_sha256 IS NULL OR (length(extracted_span_sha256) = 64 "
            "AND extracted_span_sha256 NOT GLOB '*[^0-9a-f]*')) "
            "AND (source_content_hash IS NULL OR (length(source_content_hash) = 64 "
            "AND source_content_hash NOT GLOB '*[^0-9a-f]*'))",
            name="evidence_records_hash_shape",
        ),
        # A tolerance is a declared comparison width; a negative one would be a
        # comparison no number could satisfy.
        sa.CheckConstraint(
            "tolerance IS NULL OR tolerance >= 0", name="evidence_records_tolerance"
        ),
    )
    op.create_index("ix_evidence_records_status", "evidence_records", ["status"])
    op.create_index("ix_evidence_records_task", "evidence_records", ["task_id"])

    op.create_table(
        "verification_records",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("evidence_id", sa.String(length=200), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("check_kind", sa.String(length=8), nullable=False),
        sa.Column("checker_id", sa.String(length=200), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("checked_at", sa.String(), nullable=False),
        sa.Column("normalization_profile", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        # Dense from 1: a gap in an audit trail is a defect, and a UNIQUE key
        # over (evidence_id, seq) is what makes an append-only sequence
        # enforceable rather than merely intended.
        sa.UniqueConstraint("evidence_id", "seq", name="uq_verification_records_seq"),
        sa.CheckConstraint(
            "check_kind IN ('c1', 'c2', 'c3', 'c4')", name="verification_records_check_vocabulary"
        ),
        sa.CheckConstraint(
            "outcome IN ('fail', 'indeterminate', 'not_checked', 'pass')",
            name="verification_records_outcome_vocabulary",
        ),
        # ADR-0004 I2: there is no seventh state that could hold a C4 pass, so
        # the combination is unrepresentable rather than discouraged.
        sa.CheckConstraint(
            "check_kind <> 'c4' OR outcome = 'not_checked'",
            name="verification_records_c4_never_passes",
        ),
        # "How lenient was this comparison" must be answerable by a reader of
        # the log. An absent profile on C2 answers "unknown", which is not
        # "exact"; a profile on a check that compares no text is a claim about
        # a comparison that did not happen.
        sa.CheckConstraint(
            "(check_kind = 'c2') = (normalization_profile IS NOT NULL)",
            name="verification_records_profile_belongs_to_c2",
        ),
        sa.CheckConstraint(
            "normalization_profile IS NULL OR normalization_profile IN "
            "('exact', 'nfkc_whitespace_collapsed', 'nfkc_whitespace_collapsed_ligatures')",
            name="verification_records_profile_vocabulary",
        ),
        sa.CheckConstraint("seq >= 1", name="verification_records_seq_positive"),
        sa.CheckConstraint(
            "length(evidence_id) > 0 AND length(checker_id) > 0 AND length(detail) > 0",
            name="verification_records_ids_present",
        ),
    )
    op.create_index("ix_verification_records_evidence", "verification_records", ["evidence_id"])

    # The one object in this schema deliberately absent from Base.metadata.
    #
    # Standalone rather than external-content: see the module docstring. The
    # identity columns are UNINDEXED -- stored, not searchable -- because a hit
    # must be able to name the locator it came from, and because making them
    # searchable would let a query for a hash match the wrong excerpt.
    #
    # No triggers. Triggers would keep the index in step with writes by the
    # application, and silently miss every write by anything else -- a restored
    # backup, a migration, psql. LC-P1-09's T04 owns the rebuild and its
    # idempotence test, which is checkable; a trigger firing correctly is not.
    op.execute(
        """
        CREATE VIRTUAL TABLE evidence_fts USING fts5(
            normalized_text,
            source_content_sha256 UNINDEXED,
            extraction_version UNINDEXED,
            locator_key UNINDEXED,
            source_text_id UNINDEXED,
            tokenize = 'unicode61'
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS evidence_fts")
    op.drop_index("ix_verification_records_evidence", table_name="verification_records")
    op.drop_table("verification_records")
    op.drop_index("ix_evidence_records_task", table_name="evidence_records")
    op.drop_index("ix_evidence_records_status", table_name="evidence_records")
    op.drop_table("evidence_records")
    op.drop_index("ix_evidence_anchors_anchor", table_name="evidence_anchors")
    op.drop_table("evidence_anchors")
