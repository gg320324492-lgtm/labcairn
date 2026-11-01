"""the reply: one party's answer to another's objection

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-01

**The chain holds the mentor's exchange, and a reply is not that
exchange.** ``feedback_events`` (a comment somebody wrote),
``edit_actions`` (a change made in answer to it), ``response_links`` (the
judgement that the change answered the comment) and
``followup_assessments`` are the mentor's line with a student. This
revision writes a fifth thing the work order's material holds and the
chain does not: **a reviewer's objection paired with the authors'
answer**, read out of a response document.

**Why a table and not columns on another.** ``feedback_events`` is the
wrong home: a reply's objection is not a comment the chain holds -- it
names no version, and the place it points at is a line in a rendering the
corpus does not hold -- and the reply's *answer* is not a comment at all.
``paper_versions`` is the wrong home: a version is one file, and a
response letter holds several exchanges, each with its own two words and
its own two addresses. **And ``response_links`` is the wrong home because
a reply is not a judgement**: it has no state, no decider and no
evidence, and giving it those columns would let a record of what was said
be read as a verdict on a change.

**One row holds both halves, and that is what lets the schema enforce
it.** A reply without its objection is not a reply, and a reply without
its answer is not a reply either. Two tables, one half each, could not
say so: a CHECK constraint sees one row and never another.

**And the parties are the reply's own.** The vocabulary is ``reviewer``
and ``author``, and it is not the chain's ``actor_kind``: that one
answers "who acted in the mentor's chain", and a peer reviewer of a
submitted manuscript is neither the mentor nor the student. A value
coerced into it would be a wrong value, and ``human`` on both halves
would be worse than wrong -- it would say "two people spoke" and be
unable to say which was which.

**``pairing_grade`` grades the pairing and not the words.** The words are
always the document's; what varies is how the pairing was established --
by the document's own structure, by the system's proposal, or by a person
who confirmed it.

**And the row carries no address into the manuscript under review,
because there is none to carry.** The objections in this family address
lines in a rendering the corpus does not hold, and a row that named one
would be inventing an address the file does not have. The place the
objection points at lives in the objection's own words.

**What this revision does not do.** It adds no event type, so a reply is
**not replayable from the event stream**; the chain's four objects are on
the stream and this is a fifth waiting for a fifth event. And it does
not put the reply in the mentor's chain: the chain's issue keys, its
``set_issue_key`` and its judgements do not reach it, because a reply is
a different kind of speech act.

**On ``Revises:``.** This revision was written while ``0018`` had not
landed, and it chained to the head that was there -- ``0017``. **``0018``
has since landed, and this revision chains to it**: a migration that
chains to a revision that does not exist breaks the chain, and one that
chains to a revision that is not its parent leaves two heads.

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

revision: str = "0019"
down_revision: str | None = "0018"
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
        "replies",
        # Derived rather than caller-minted: a function of the version and
        # the two paragraphs the exchange was read from, so recording the
        # same document twice finds the rows that are already there.
        sa.Column("reply_id", sa.Text(), nullable=False),
        sa.Column(
            "project_id",
            sa.Text(),
            sa.ForeignKey("paper_projects.project_id", ondelete="CASCADE"),
            nullable=False,
        ),
        # The version whose material the reply was read from -- the response
        # document, not the manuscript under review.
        sa.Column(
            "version_id",
            sa.Text(),
            sa.ForeignKey("paper_versions.version_id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Who wrote each half. The reply's own vocabulary.
        sa.Column("objection_party", sa.String(32), nullable=False),
        sa.Column("objection_text", sa.Text(), nullable=False),
        sa.Column("objection_text_sha256", sa.String(64), nullable=False),
        # The reader's own coordinate in the response document. Not a place
        # in the manuscript under review, which the material does not have.
        sa.Column("objection_paragraph", sa.Integer(), nullable=False),
        sa.Column("answer_party", sa.String(32), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=False),
        sa.Column("answer_text_sha256", sa.String(64), nullable=False),
        sa.Column("answer_paragraph", sa.Integer(), nullable=False),
        # How the pairing was established. The words are the document's in
        # all three; only the pairing is graded.
        sa.Column("pairing_grade", sa.String(32), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("reply_id", name="pk_replies"),
        sa.CheckConstraint(
            "length(reply_id) > 0 AND length(project_id) > 0 AND length(version_id) > 0",
            name="replies_ids_present",
        ),
        sa.CheckConstraint(
            "objection_party IN ('reviewer', 'author')",
            name="replies_objection_party_vocabulary",
        ),
        sa.CheckConstraint(
            "answer_party IN ('reviewer', 'author')",
            name="replies_answer_party_vocabulary",
        ),
        sa.CheckConstraint(
            "objection_party <> answer_party",
            name="replies_the_two_halves_are_two_parties",
        ),
        sa.CheckConstraint(
            "pairing_grade IN ('observed', 'inferred', 'human_verified')",
            name="replies_pairing_grade_vocabulary",
        ),
        sa.CheckConstraint(
            "objection_paragraph >= 0 AND answer_paragraph > objection_paragraph",
            name="replies_the_paragraphs_are_ordered",
        ),
        sa.CheckConstraint(
            "length(objection_text_sha256) = 64 AND objection_text_sha256 NOT GLOB '*[^0-9a-f]*' "
            "AND length(answer_text_sha256) = 64 AND answer_text_sha256 NOT GLOB '*[^0-9a-f]*'",
            name="replies_the_hash_shape",
        ),
        # A reply holds both halves or it is not a reply.
        sa.CheckConstraint(
            _has_content("objection_text") + " AND " + _has_content("answer_text"),
            name="replies_both_halves_are_present",
        ),
    )
    op.create_index("ix_replies_version", "replies", ["version_id"])
    op.create_index("ix_replies_project", "replies", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_replies_project", table_name="replies")
    op.drop_index("ix_replies_version", table_name="replies")
    op.drop_table("replies")
