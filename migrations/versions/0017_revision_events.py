"""the revision events a manuscript's file records

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-01

LC-P2-08's missing seam, closed. ``docs/acceptance/LC-P2-08-acceptance.md``
records the debt in the work order's own words: *"LC-P2-07's reader produces
the revision events these tables are meant to hold, and nobody has written
them into the store -- the reader exists, the store exists, and the seam
between the two is not connected, so the version graph is hand-fed today."*
This revision is the other half of that seam.

**One table, and it is ADR-0014's.** Revision D8 of that ADR declares four
tables -- ``PaperVersion``, ``VersionEdge``, ``DocumentSpan`` and
``RevisionEvent`` -- and only the first two were ever written. This
revision writes the third: one row per tracked change a Word document
records. It is a new table and not a set of columns on the version or on
the chain's ``edit_actions``, for the reason D8 gives: *"a table where
'revision 3' means two things is a table nobody can read."*

**Why it is not the chain's ``edit_actions``.** The chain's four tables are
a judgement layer -- a comment, a change made in answer to it, the
judgement that it answered, a later assessment -- and ``edit_actions`` is
content-free by design: it names an edge and an actor, and the content
belongs to the document model, which is ADR-0014's. A marked-up manuscript
holds hundreds of changes, each with its own address and its own text; a
version holds one file.

**The address is the event.** D5 chose an XML path plus a content hash over
every alternative, and D4a made the *view* part of the address: a ``w:del``
element's text is in the rejected view, so the same element in the two views
is two addresses resolving to two different texts. The columns are that
address, flattened -- the part, the element path, the view, and the
character range inside the element's text -- together with the hash of the
anchored text, which is what makes drift detectable.

**And a row that was not read carries no address and no words.** D2's
three grades are the row's, and the rule about them is the one
``feedback_events`` already holds for the comment's locator: an
``inferred`` row read no file, so it quotes nobody and points at nothing.

**What this revision does not do.** It adds no event type, so a revision
event is **not replayable from the event stream**; ADR-0017 D8 puts the
chain's four objects on the stream, and this is a fifth object waiting for
a fifth event. And it does not write ``DocumentSpan``, ADR-0014's other
unbuilt table: D5's flat form is the floor the ADR's chosen alternative
already meets, and a span table only earns its place when two things must
share one address -- which is the reply letter's turn, not this one's.

Direct DDL, for the reason 0007 records: a frozen revision must not import
today's ``labcairn.db.models``, or editing that class would silently
rewrite what this revision meant to create.
``tests/test_store_migrations.py``'s parity test holds the two together,
and the rows this revision must refuse are witnessed again by writing
them -- a text comparison cannot catch a migration and a model wrong
together.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "revision_events",
        # Caller-minted, and derived rather than sequential: the id is a
        # function of the version and the element's path, so recording the
        # same file twice finds the rows that are already there.
        sa.Column("revision_event_id", sa.Text(), nullable=False),
        # The manuscript version whose document the event was read from.
        # The version carries the file and the bytes, so the event does
        # not repeat them.
        sa.Column(
            "version_id",
            sa.Text(),
            sa.ForeignKey("paper_versions.version_id", ondelete="CASCADE"),
            nullable=False,
        ),
        # ins | del | moveFrom | moveTo -- the four kinds the reader
        # reports.
        sa.Column("kind", sa.String(32), nullable=False),
        # The inserted or the deleted text. Empty is a real value: Word
        # records an empty tracked insertion.
        sa.Column("text", sa.Text(), nullable=False),
        # The hash of that text at the moment it was recorded (D5).
        sa.Column("text_sha256", sa.String(64), nullable=False),
        # The part the element is in, the path of the element inside it,
        # and the view the range is in (D4a, D5).
        sa.Column("part", sa.Text(), nullable=True),
        sa.Column("element_path", sa.Text(), nullable=True),
        sa.Column("view", sa.String(32), nullable=True),
        # The range inside the addressed element's text.
        sa.Column("char_start", sa.Integer(), nullable=True),
        sa.Column("char_end", sa.Integer(), nullable=True),
        # The paragraph, and the range in the paragraph's rejected text.
        sa.Column("paragraph", sa.Integer(), nullable=True),
        sa.Column("baseline_start", sa.Integer(), nullable=True),
        sa.Column("baseline_end", sa.Integer(), nullable=True),
        # The author and the timestamp, or the reason each is unknown.
        sa.Column("author", sa.String(200), nullable=True),
        sa.Column("author_unknown_reason", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.String(), nullable=True),
        sa.Column("date_unknown_reason", sa.Text(), nullable=True),
        # Word's w:id, and whether the revision is nested in another one.
        sa.Column("element_id", sa.String(200), nullable=True),
        sa.Column("nested", sa.Boolean(), nullable=False),
        # The extraction version the reader was running (D5).
        sa.Column("parser_version", sa.String(64), nullable=False),
        # observed | inferred | human_verified (D2).
        sa.Column("grade", sa.String(32), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("revision_event_id", name="pk_revision_events"),
        sa.CheckConstraint(
            "length(revision_event_id) > 0 AND length(version_id) > 0 "
            "AND length(text_sha256) = 64 AND length(parser_version) > 0",
            name="revision_events_ids_present",
        ),
        sa.CheckConstraint(
            "kind IN ('ins', 'del', 'moveFrom', 'moveTo')",
            name="revision_events_kind_vocabulary",
        ),
        sa.CheckConstraint(
            "grade IN ('observed', 'inferred', 'human_verified')",
            name="revision_events_grade_vocabulary",
        ),
        sa.CheckConstraint(
            "view IS NULL OR view IN ('accepted', 'rejected')",
            name="revision_events_view_vocabulary",
        ),
        # The address belongs to a read.
        sa.CheckConstraint(
            "(grade = 'inferred' AND part IS NULL AND element_path IS NULL "
            "AND view IS NULL) OR "
            "(grade <> 'inferred' AND part IS NOT NULL AND length(part) > 0 "
            "AND element_path IS NOT NULL AND length(element_path) > 0 "
            "AND view IS NOT NULL)",
            name="revision_events_the_address_belongs_to_a_read",
        ),
        # And an inferred row carries no words.
        sa.CheckConstraint(
            "grade <> 'inferred' OR text = ''",
            name="revision_events_an_inferred_row_carries_no_words",
        ),
        # A range is a range.
        sa.CheckConstraint(
            "(char_start IS NULL AND char_end IS NULL) OR "
            "(char_start IS NOT NULL AND char_end IS NOT NULL "
            "AND char_end >= char_start)",
            name="revision_events_the_range_is_paired",
        ),
        # And the same rule for the baseline range.
        sa.CheckConstraint(
            "(baseline_start IS NULL AND baseline_end IS NULL) OR "
            "(baseline_start IS NOT NULL AND baseline_end IS NOT NULL "
            "AND baseline_start >= 0 AND baseline_end >= baseline_start)",
            name="revision_events_the_baseline_is_a_range",
        ),
        # A missing author is unknown, and its absence is named.
        sa.CheckConstraint(
            "(author IS NULL AND author_unknown_reason IS NOT NULL "
            "AND length(trim(author_unknown_reason)) > 0) OR "
            "(author IS NOT NULL AND author_unknown_reason IS NULL)",
            name="revision_events_an_author_is_named_or_its_absence_is",
        ),
        # And the same for the timestamp.
        sa.CheckConstraint(
            "(occurred_at IS NULL AND date_unknown_reason IS NOT NULL "
            "AND length(trim(date_unknown_reason)) > 0) OR "
            "(occurred_at IS NOT NULL AND date_unknown_reason IS NULL)",
            name="revision_events_a_date_is_named_or_its_absence_is",
        ),
        # A paragraph is a place.
        sa.CheckConstraint(
            "paragraph IS NULL OR paragraph >= 0",
            name="revision_events_the_paragraph_is_a_place",
        ),
    )
    op.create_index("ix_revision_events_version", "revision_events", ["version_id"])


def downgrade() -> None:
    op.drop_index("ix_revision_events_version", table_name="revision_events")
    op.drop_table("revision_events")
