"""the judgement that an author's answer settled a reviewer's point

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-01

**The reply is a record, and the settlement is the judgement over it.**
``replies`` holds what a reviewer objected to and what the authors said in
answer, and holds no verdict -- that absence is the design, and it stays.
But a record of what was said is not yet an answer to the question the
chain is for: *did the authors' answer settle the point*. This revision
writes the table that judges it, and the judgement goes through the same
door as ``response_links``: a state other than ``pending`` needs a decider
and the evidence behind it, and a model may put a settlement forward but
may not decide one. **A status anybody can set is not a status, so the
schema refuses one.**

**Why a table and not columns on ``replies``.** A verdict bolted onto the
row that holds the words would let a record of what was said be read as a
ruling. The reply stays a record; the settlement is a row of its own,
pointing at the reply it judges.

**The four states are not four labels for one thing.**

- ``pending`` -- somebody put a settlement forward and nobody has judged
  it. It is the only state a row may hold without a decider, and it is
  **listed as unanswered**: an answer that was never judged does not make
  the point answered.
- ``settled`` -- the answer settled the point, and the row says on what:
  the ``claim_terms`` the answer claims the manuscript contains, checked
  against the manuscript's accepted text before the row was written, and
  the ``resolved`` address of the change they live at. **A settled
  settlement that names neither is refused by the schema.** And what
  ``settled`` says is narrow by design: the claimed thing is findable in
  the manuscript. **It does not say the science was right**, and no
  column in this table can carry that.
- ``held`` -- the claim could not be found, and the row says what it is
  holding for. **A hold names what it holds**, because a hold that says
  only "held" is a hold nobody can lift.
- ``unresolved`` -- the judgement went the other way: the answer did not
  settle the point.

**``reply_id`` is unique.** A judgement is a fact, and a second judgement
over the same reply is a revision of a fact, which the store does not
hold. One point, one judgement.

**And the address is a value, never a guess.** ``anchor_status`` is
``resolved`` -- the change was placed, and ``change_version_id`` and
``change_paragraph`` say where -- or ``unknown``, and the two agree in
both directions by CHECK constraint. The reply names a place in the
response document only; **a place in the manuscript is this judgement's
to give**, and a judgement that cannot give one says ``unknown`` rather
than guessing.

**And the correspondence with the chain's own comment is part of the
judgement.** ``feedback_id`` names the comment the decider judged this
reply to be about -- on the evidence the row names, said by the decider,
and never inferred: the reply carries no issue key and nobody derived
one. **A product that reported only the newer of the chain's judgement
and the settlement would be deciding a disagreement by recency**, and the
reader gets both sides instead.

**What this revision does not do.** It adds no event type, so a
settlement is **not replayable from the event stream**, for the same
reason and in the same debt as 0019 records for the reply.

Direct DDL, for the reason 0007 records: a frozen revision must not import
today's ``labcairn.db.models``, or editing that class would silently
rewrite what this revision meant to create. The whitespace class below is
a copy of the one in that file for the same reason, and
``tests/test_store_migrations.py``'s parity test holds the two together --
and the rows this revision must refuse are witnessed again by writing
them, because a text comparison cannot catch a migration and a model
wrong together.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: The code points ``str.strip()`` removes. **A copy of the class in
#: ``labcairn.db.models``, and it has to be one**: a frozen revision must
#: not import the live package, or editing that class would silently
#: rewrite what this revision meant to create. The parity test holds the
#: two together.
_NON_WHITESPACE_CODEPOINTS: Final[tuple[int, ...]] = (
    0x0009, 0x000A, 0x000B, 0x000C, 0x000D, 0x001C, 0x001D, 0x001E, 0x001F,
    0x0020, 0x0085, 0x00A0, 0x1680,
    0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006, 0x2007, 0x2008,
    0x2009, 0x200A, 0x2028, 0x2029, 0x202F, 0x205F, 0x3000,
)  # fmt: skip


def _has_content(column: str) -> str:
    """SQL for "this column holds at least one non-whitespace character"."""
    negated = "[" + chr(94) + "".join(chr(code) for code in _NON_WHITESPACE_CODEPOINTS) + "]"
    return f"{column} GLOB '*{negated}*'"


def upgrade() -> None:
    op.create_table(
        "reply_settlements",
        # Caller-minted, so a settlement may be cited from an earlier run.
        sa.Column("settlement_id", sa.Text(), nullable=False),
        # The exchange the judgement is over. Unique: one point, one
        # judgement, and a judgement is not revised in place.
        sa.Column(
            "reply_id",
            sa.Text(),
            sa.ForeignKey("replies.reply_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("grade", sa.String(32), nullable=False),
        sa.Column("decided_by", sa.String(32), nullable=True),
        sa.Column("decided_at", sa.String(), nullable=True),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        # The words a settled judgement vouches for, each checked against
        # the manuscript's accepted text before the row was written.
        sa.Column("claim_terms", sa.JSON(), nullable=False),
        # Where the change the answer claims lives. The reply names a
        # place in the response document only; a place in the manuscript
        # is this judgement's to give.
        sa.Column(
            "change_version_id",
            sa.Text(),
            sa.ForeignKey("paper_versions.version_id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("change_paragraph", sa.Integer(), nullable=True),
        # ``resolved`` or ``unknown`` -- and the address agrees with it in
        # both directions. A missing address is a value, never a guess.
        sa.Column("anchor_status", sa.String(32), nullable=False),
        # The chain comment the decider judged this reply to be about,
        # said by the decider and never inferred.
        sa.Column(
            "feedback_id",
            sa.Text(),
            sa.ForeignKey("feedback_events.feedback_id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("hold_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("settlement_id", name="pk_reply_settlements"),
        sa.UniqueConstraint("reply_id", name="uq_reply_settlements_reply"),
        sa.CheckConstraint(
            "length(settlement_id) > 0 AND length(reply_id) > 0",
            name="reply_settlements_ids_present",
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'settled', 'held', 'unresolved')",
            name="reply_settlements_state_vocabulary",
        ),
        sa.CheckConstraint(
            "grade IN ('observed', 'human_verified', 'inferred')",
            name="reply_settlements_grade_vocabulary",
        ),
        sa.CheckConstraint(
            "decided_by IS NULL OR decided_by IN ('rule', 'user', 'model')",
            name="reply_settlements_decider_vocabulary",
        ),
        # A pending settlement carries no decision.
        sa.CheckConstraint(
            "state <> 'pending' OR (decided_at IS NULL AND json_array_length(evidence_refs) = 0)",
            name="reply_settlements_a_pending_settlement_carries_no_decision",
        ),
        # A judged settlement names its decider and its evidence. The
        # decider is compared with IS NOT NULL as well, because SQLite
        # treats a constraint expression that is NULL as satisfied.
        sa.CheckConstraint(
            "state = 'pending' OR (decided_by IS NOT NULL"
            " AND decided_by IN ('rule', 'user') AND decided_at IS NOT NULL"
            " AND json_array_length(evidence_refs) > 0)",
            name="reply_settlements_a_judgement_names_its_decider_and_its_evidence",
        ),
        # A model may not settle a point.
        sa.CheckConstraint(
            "state = 'pending' OR decided_by <> 'model'",
            name="reply_settlements_a_model_may_not_settle",
        ),
        # An inferred settlement is a model's candidate: the grade and the
        # proposer agree, or the row does not hold.
        sa.CheckConstraint(
            "(COALESCE(decided_by, 'none') <> 'model' AND grade <> 'inferred')"
            " OR (COALESCE(decided_by, 'none') = 'model' AND grade = 'inferred')",
            name="reply_settlements_an_inferred_settlement_is_a_candidates",
        ),
        sa.CheckConstraint(
            "anchor_status IN ('resolved', 'unknown')",
            name="reply_settlements_anchor_status_vocabulary",
        ),
        # An address is a value, never a guess: resolved and the two
        # address columns agree in both directions.
        sa.CheckConstraint(
            "(anchor_status = 'resolved') = (change_version_id IS NOT NULL"
            " AND change_paragraph IS NOT NULL)",
            name="reply_settlements_an_address_is_a_value_not_a_guess",
        ),
        # A settled judgement points at the manuscript.
        sa.CheckConstraint(
            "state <> 'settled' OR anchor_status = 'resolved'",
            name="reply_settlements_a_settled_judgement_points_at_the_manuscript",
        ),
        # A settled judgement names what it found.
        sa.CheckConstraint(
            "state <> 'settled' OR json_array_length(claim_terms) > 0",
            name="reply_settlements_a_settled_judgement_names_what_it_found",
        ),
        # A hold names what it holds.
        sa.CheckConstraint(
            "(state = 'held') = (hold_reason IS NOT NULL AND length(trim(hold_reason)) > 0)",
            name="reply_settlements_a_hold_names_what_it_holds",
        ),
    )
    op.create_index(
        "ix_reply_settlements_feedback",
        "reply_settlements",
        ["feedback_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_reply_settlements_feedback", table_name="reply_settlements")
    op.drop_table("reply_settlements")
