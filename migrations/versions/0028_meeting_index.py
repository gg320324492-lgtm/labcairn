"""the multi-source index: meeting text, searchable

Revision ID: 0028
Revises: 0027
Create Date: 2026-11-24

Phase 4 (P4-MS), execution plan §8.4, third source: meeting material that
already exists as text -- a transcript someone else produced (SRT,
WebVTT) or notes someone organised by hand (TXT, Markdown). Automatic
transcription is explicitly not a first-version condition. §8.3's rule
carries over: every extraction result keeps the source version, the
position -- for a transcript the timestamp or entry number, for organised
text the paragraph -- and the source fingerprint -- and §8.5's is that a
hit points back at the correct entry or paragraph. One table holds the
records with that provenance; one FTS5 index makes them searchable; the
application layer writes both in one transaction, the way the deck index
does.

Two tables, following the deck index's precedent (0026):

``meeting_index_rows``
    One row per extracted record. The ``record_format`` names which shape
    of meeting text the row holds -- a transcript ``entry`` or an
    organised ``paragraph`` -- and every row carries the **record's
    1-based index within the file, the container's timestamp when the
    record has one, and the source fingerprint** the extraction recorded,
    so a hit says not only what the meeting text says but which entry or
    paragraph says it.

    The primary key is **derived** (the application layer hashes the
    project, the source file's content hash and the record's fingerprint),
    so re-ingesting the same file is the same rows: an index that grew a
    second copy of a transcript on every re-read would be a record of
    ingestions, not of the meeting.

    ``project_id`` names the paper project the meeting text belongs to.
    The deck index's rows hang off the project the same way, and meeting
    text whose project is deleted goes with it -- ``ON DELETE CASCADE``,
    the same rule the deck rows follow.

``meeting_fts``
    The FTS5 index over each record's text, on the **trigram** tokenizer
    for the same measured reason 0006 rebuilt ``evidence_fts`` and 0025
    reused: transcript and note text runs words together, and only a
    substring tokenizer finds them. Standalone rather than
    external-content, the id column ``UNINDEXED``, no triggers -- the
    application writes both tables in one transaction, the way the deck
    index's write does.

Direct DDL against ``sa`` types, for the reason 0007, 0012, 0021, 0023,
0024, 0025, 0026 and 0027 record: a frozen revision must not import
today's ``labcairn.db.models``, or the schema it installs drifts with the
code around it. Datetime columns are ``sa.String()`` for the same reason
earlier revisions spell them so: the models' ``UtcDateTime`` is a
``TypeDecorator`` whose rendered type is the platform's text type, and a
revision that says ``sa.DateTime()`` would install a column the models do
not recognise.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "meeting_index_rows",
        sa.Column("record_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        # The file's own identity: the content hash of the file the records
        # were read from. Two files with the same words are two files, and
        # the hash is what says so.
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        # Which shape of record: 'entry' -- a timestamped transcript cue --
        # or 'paragraph' -- a block of manually organised text. The closed
        # vocabulary, because a row that is neither is a row nobody can
        # render.
        sa.Column("record_format", sa.String(length=16), nullable=False),
        # The record's 1-based index within the file -- the cue's order in
        # the transcript, or the paragraph's order in the notes. Together
        # with the format it is the address §8.5 asks a hit to point at.
        sa.Column("record_index", sa.Integer(), nullable=False),
        # The container's timestamp for a transcript entry, as the file
        # spells it, or NULL for a paragraph -- a paragraph has no time,
        # and inventing one would be a conclusion the bytes do not carry.
        sa.Column("timestamp_label", sa.Text(), nullable=True),
        # The record's own fingerprint, as the extraction recorded it: the
        # file's hash, the record's shape, index and timestamp, folded.
        # Re-reading the same file yields the same fingerprint, which is
        # what makes the derived id stable across re-ingestions.
        sa.Column("record_fingerprint", sa.Text(), nullable=False),
        # What the record says. Never empty: a record with no words is not
        # a row, it is nothing.
        sa.Column("text", sa.Text(), nullable=False),
        # The structured locator, as JSON -- the MeetingTextLocator's
        # fields -- so a hit can hand back the address without
        # re-deriving it.
        sa.Column("locator_json", sa.Text(), nullable=False),
        # When the record was indexed.
        sa.Column("ingested_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["paper_projects.project_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("record_id"),
        sa.CheckConstraint(
            "record_format IN ('entry', 'paragraph')",
            name="meeting_index_format_vocabulary",
        ),
        sa.CheckConstraint(
            "record_index >= 1",
            name="meeting_index_positions_positive",
        ),
        sa.CheckConstraint(
            "record_format != 'entry' OR timestamp_label IS NOT NULL",
            name="meeting_index_entry_is_timed",
        ),
        sa.CheckConstraint(
            "record_format != 'paragraph' OR timestamp_label IS NULL",
            name="meeting_index_paragraph_is_untimed",
        ),
        sa.CheckConstraint(
            "length(record_id) > 0 AND length(project_id) > 0",
            name="meeting_index_ids_present",
        ),
        sa.CheckConstraint(
            "length(trim(text)) > 0",
            name="meeting_index_text_present",
        ),
        sa.CheckConstraint(
            "length(source_sha256) = 64 AND source_sha256 NOT GLOB '*[^0-9a-f]*'",
            name="meeting_index_source_sha256_well_formed",
        ),
        sa.CheckConstraint(
            "length(trim(record_fingerprint)) > 0 AND length(trim(locator_json)) > 0",
            name="meeting_index_address_present",
        ),
    )
    op.create_index("ix_meeting_index_project", "meeting_index_rows", ["project_id"])
    op.create_index("ix_meeting_index_source", "meeting_index_rows", ["source_sha256"])

    # Standalone FTS5, trigram-tokenized, for the reason 0006 measured and
    # 0025/0026 reused: transcript and note text arrives with words run
    # together, and a substring tokenizer is the only thing that answers a
    # substring question over it. The id is UNINDEXED -- stored, not
    # searchable -- so the FTS row carries the key the index rows are
    # found by, and nothing else.
    op.execute(
        """
        CREATE VIRTUAL TABLE meeting_fts USING fts5(
            text,
            record_id UNINDEXED,
            tokenize = 'trigram'
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS meeting_fts")
    op.drop_index("ix_meeting_index_source", table_name="meeting_index_rows")
    op.drop_index("ix_meeting_index_project", table_name="meeting_index_rows")
    op.drop_table("meeting_index_rows")
