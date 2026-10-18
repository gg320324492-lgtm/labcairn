"""rebuild the index on a trigram tokenizer, so sub-words are findable

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-18

LC-P1-09 T03. Revision 0005 built ``evidence_fts`` on FTS5's default
``unicode61`` tokenizer, which matches **whole tokens**. On this repository's
own papers that finds almost nothing, and the reason is measured rather than
guessed.

ADR-0008's third constraint records that these PDFs space words by
positioning: space glyphs are 0.03%-1.08% of the characters, so extracted
body text arrives with words run together. On page 4 of ``arx-2610.12393`` the
stored text contains::

    red and unique factors(q ,q ),anirreduciblesynergisticgapI(Y;q |q ,q )>0

``irreducible`` is not a token there. It is a fragment of the single token
``anirreduciblesynergisticgapI`` -- the word is glued to an article on one
side and to a math symbol on the other, with **no separator of any kind
between them**. Measured against ``unicode61``, queries for ``irreducible``,
``synergistic`` and ``irreduciblesynergisticgap`` return **zero** hits on a
page that visibly contains all three.

No change of separator characters recovers this, because the boundary
information is not in the text: there is nothing for a tokenizer to split on.
The only thing that answers a substring question over text like this is a
tokenizer built on substrings, which is what ``trigram`` is.

**This revision drops and recreates the table rather than altering it.** An
FTS5 virtual table's tokenizer is part of its definition, not a column; SQLite
cannot change one in place. The rows are the index's own, and the index is
derived -- ``source_texts`` is the authority and is untouched here. Nothing has
built an index from the walk yet, so in practice there is nothing to lose; that
is luck, not design, and a future change to the tokenizer will cost a rebuild.

**What this costs, measured and not assumed.** Trigram stores overlapping
three-character sequences, so the index is larger than the text it indexes --
roughly three times, in the worst case. And a term shorter than three
characters cannot be matched by a trigram table at all. That is a property of
the tokenizer, not a choice made here, and it is why ``search`` now decides
what to do about such a query rather than letting SQLite answer.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: The columns, unchanged from 0005. Only the tokenizer differs, and a comment
#: in the migration says why that is still a rebuild.
_COLUMNS = """
    normalized_text,
    source_content_sha256 UNINDEXED,
    extraction_version UNINDEXED,
    locator_key UNINDEXED,
    source_text_id UNINDEXED
"""


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS evidence_fts")
    op.execute(f"CREATE VIRTUAL TABLE evidence_fts USING fts5({_COLUMNS}, tokenize = 'trigram')")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS evidence_fts")
    op.execute(f"CREATE VIRTUAL TABLE evidence_fts USING fts5({_COLUMNS}, tokenize = 'unicode61')")
