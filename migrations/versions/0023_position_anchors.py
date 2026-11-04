"""the anchor that covers no text is stored as covering no text

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-04

**A position is a place, and it is not an unknown.** The reader reports a
comment whose range closes where it opens -- a comment on *the place*
rather than on words -- and the schema had only two words for an anchor:
``resolved`` or ``unknown``. ``resolved`` would claim a passage was found
and no passage exists; ``unknown`` would claim the reader could not place
the comment when the reader did place it. So the vocabulary widens by one:
``position`` is the third anchor status, and it is the only one that may
hold a paragraph and an offset while holding no text. That is the point of
the third word -- a position keeps the place the file records, and a row
that could not keep both the place and the emptiness was forced to throw
one of the two away.

**A row whose anchor covers no text carries no digest.** The digest of a
passage is the integrity value of that passage: it is what lets a later
read tell whether the same address still holds the same words. A row that
covers no text has no passage whose sameness any digest could guard, and
the old shape forced it to carry the digest of the empty string anyway --
a value that reads as an integrity check and guards nothing, which is how
sixteen resolved rows over no text passed the old ``ids_present`` check on
their way into the pilot store. ``anchor_text`` and ``anchor_text_sha256``
are therefore nullable, and the shape check pins them to ``NULL`` for
``unknown`` and ``position`` rows: **the digest of the empty string has no
legal path left**. A ``position`` row that carries one is refused, an
``unknown`` row that carries one is refused, and a ``resolved`` row must
carry real text, so a digest of nothing cannot be minted by any writer.

**The placeholder is cleaned, not kept.** The old shape forced every
``unknown`` row to carry the empty string and its digest; this revision
sets those two columns to ``NULL`` on the rows the old check forced to lie.
It is the same shape of change revision 0012 made when it backfilled the
bytes hash: the data move is what makes the new constraint installable, it
touches only the columns the old shape invented values for, and it leaves
every other column -- and every ``resolved`` row -- exactly as it was.

**What this revision deliberately does not touch.** A store may also hold
``resolved`` rows whose anchored text is the empty string: rows written
before the reader stopped resolving zero-width ranges, whose real shape is
a question for the store's data correction, not for a schema revision --
the new shape check refuses them, so a store that carries one is upgraded
only after those rows are re-cast. And a store's ``unknown`` rows whose
reason names a position keep their status and their reason: re-casting
them as ``position`` rows is the data correction's decision too. This
revision changes the shape, cleans the forced placeholder, and nothing
else.

Direct DDL against ``sa`` types, for the reason 0007 and 0012 record: a
frozen revision must not import today's ``labcairn.db.models``, or the
schema it installs drifts with the code around it.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: The digest of the empty string, which rows whose anchor covers no text
#: were forced to carry as an integrity value. The upgrade writes ``NULL``
#: over it; the downgrade writes it back, because the shape it returns to
#: refuses a row without one.
_EMPTY_TEXT_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

#: The reason the reader named for a position anchor while the vocabulary
#: had only two words. The downgrade writes it back onto the rows this
#: revision's vocabulary calls positions, because that is what they were
#: called before the third word existed. **The apostrophe is doubled, not
#: escaped**: this is SQL text, and a backslash means nothing to SQLite.
_POSITION_REASON_SQL = "'the comment''s range is a position, not a passage of text'"


def _ids_present() -> str:
    """The ids a row must carry. The anchored-text digest is not among
    them: it belongs to the shape check, which pins it by status."""
    return (
        "length(feedback_id) > 0 AND length(project_id) > 0 AND length(version_id) > 0 "
        "AND length(comment_text_sha256) > 0"
    )


def _anchor_shape() -> str:
    """The anchor's columns say what its status says.

    Written out here rather than imported from the models, for the reason
    the module docstring records.
    """
    return (
        "(anchor_status = 'resolved' AND anchor_paragraph IS NOT NULL "
        "AND anchor_start IS NOT NULL AND anchor_end IS NOT NULL "
        "AND anchor_reason IS NULL "
        "AND anchor_text IS NOT NULL AND length(anchor_text) > 0 "
        "AND anchor_text_sha256 IS NOT NULL AND length(anchor_text_sha256) > 0) OR "
        "(anchor_status = 'unknown' AND anchor_reason IS NOT NULL "
        "AND length(anchor_reason) > 0 AND anchor_start IS NULL AND anchor_end IS NULL "
        "AND anchor_text IS NULL AND anchor_text_sha256 IS NULL) OR "
        "(anchor_status = 'position' AND anchor_paragraph IS NOT NULL "
        "AND anchor_start IS NOT NULL AND anchor_end IS NOT NULL "
        "AND anchor_start = anchor_end "
        "AND anchor_reason IS NULL "
        "AND anchor_text IS NULL AND anchor_text_sha256 IS NULL)"
    )


def upgrade() -> None:
    # The two columns widen first, and the three checks the new shape
    # replaces go -- the placeholder cannot be cleaned while a check still
    # demands it.
    with op.batch_alter_table("feedback_events", schema=None) as batch_op:
        batch_op.alter_column("anchor_text", existing_type=sa.Text(), nullable=True)
        batch_op.alter_column("anchor_text_sha256", existing_type=sa.String(64), nullable=True)
        batch_op.drop_constraint("feedback_events_ids_present", type_="check")
        batch_op.drop_constraint("feedback_events_anchor_status_vocabulary", type_="check")
        batch_op.drop_constraint("feedback_events_anchor_is_resolved_or_named", type_="check")
    # The placeholder the old shape forced every unknown row to carry: no
    # text, and a digest of nothing standing as its integrity value. Both
    # go, and nothing else about the row moves.
    op.execute(
        "UPDATE feedback_events SET anchor_text = NULL, anchor_text_sha256 = NULL "
        "WHERE anchor_status = 'unknown'"
    )
    with op.batch_alter_table("feedback_events", schema=None) as batch_op:
        batch_op.create_check_constraint("feedback_events_ids_present", _ids_present())
        batch_op.create_check_constraint(
            "feedback_events_anchor_status_vocabulary",
            "anchor_status IN ('resolved', 'unknown', 'position')",
        )
        batch_op.create_check_constraint(
            "feedback_events_anchor_shape_matches_status", _anchor_shape()
        )


def downgrade() -> None:
    # The shape checks go first, because every row this shape permits
    # denies the shape it returns to: a position row holds an offset the
    # two-word vocabulary calls unknown-and-unplaced, and an unknown row
    # carries no digest where the old ``ids_present`` demanded one. With
    # the checks down, the rows are re-spelled in single statements --
    # each row's end state, not its intermediate one, is what the
    # restored checks will meet.
    with op.batch_alter_table("feedback_events", schema=None) as batch_op:
        batch_op.drop_constraint("feedback_events_anchor_shape_matches_status", type_="check")
        batch_op.drop_constraint("feedback_events_anchor_status_vocabulary", type_="check")
        batch_op.drop_constraint("feedback_events_ids_present", type_="check")
    # The vocabulary narrows back to two words, so a position row must be
    # called what it was called before: an unknown anchor, with the reason
    # the reader used to name it. The offsets go with the status -- an
    # unknown anchor is unplaced, and keeping them would deny the shape
    # the old check restores.
    op.execute(
        "UPDATE feedback_events SET anchor_status = 'unknown', anchor_reason = "
        + _POSITION_REASON_SQL
        + ", anchor_start = NULL, anchor_end = NULL WHERE anchor_status = 'position'"
    )
    # And the shape this revision returns to refuses a row whose anchor
    # covers no text but carries no digest, so the placeholder goes back.
    op.execute(
        "UPDATE feedback_events SET anchor_text = '', anchor_text_sha256 = '"
        + _EMPTY_TEXT_SHA256
        + "' WHERE anchor_status = 'unknown'"
    )
    with op.batch_alter_table("feedback_events", schema=None) as batch_op:
        batch_op.create_check_constraint(
            "feedback_events_ids_present",
            "length(feedback_id) > 0 AND length(project_id) > 0 AND length(version_id) > 0 "
            "AND length(comment_text_sha256) > 0 AND length(anchor_text_sha256) > 0",
        )
        batch_op.create_check_constraint(
            "feedback_events_anchor_status_vocabulary",
            "anchor_status IN ('resolved', 'unknown')",
        )
        batch_op.create_check_constraint(
            "feedback_events_anchor_is_resolved_or_named",
            "(anchor_status = 'resolved' AND anchor_paragraph IS NOT NULL "
            "AND anchor_start IS NOT NULL AND anchor_end IS NOT NULL "
            "AND anchor_reason IS NULL) OR "
            "(anchor_status = 'unknown' AND anchor_reason IS NOT NULL "
            "AND length(anchor_reason) > 0 AND anchor_start IS NULL AND anchor_end IS NULL)",
        )
        batch_op.alter_column("anchor_text", existing_type=sa.Text(), nullable=False)
        batch_op.alter_column("anchor_text_sha256", existing_type=sa.String(64), nullable=False)
