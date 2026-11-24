"""a rule may be shared with the group, or kept private

Revision ID: 0030
Revises: 0029
Create Date: 2026-11-24

Phase 4 §8.5 / P4-G3. A mentor-confirmed rule so far served only the project
it was learned from. This revision gives every rule version a sharing scope
so a confirmed rule can be **published to the group** -- the whole research
group's other projects -- and retracted again, without touching the rule's
own state machine.

**Why columns on the rule and not a publication table.** Sharing is a
*property of the version the way its state is*: a rule version is either
private to its project or shared with the group, and the retrieval's filter
is one ``WHERE`` over the rule row rather than a join against a second
table whose newest row per rule would have to be derived. The versioned
primary key ``(rule_id, version)`` already isolates a rule's history: an
older version keeps the scope it was published at, and the retrieval serves
the highest version only. **A publication event log is a record about the
sharing; these columns are the sharing itself** -- the thing the retrieval
must ask at serve time, the way it asks the state.

**The columns.**

- ``shared_scope`` is ``private`` or ``group``. ``private`` is the default
  and the existing rows' answer: every rule that predates this revision was
  serving its own project only, so its scope is ``private`` -- the default
  is the fact, the way ``bound_sources``' ``'[]'`` was in revision 0014.
- ``published_by`` names the mentor who published the rule to the group.
  It is null until published, and the application layer refuses a publisher
  who is the rule's proposer -- the same second-reader rule the
  confirmation already carries.
- ``published_at`` is when it was published. The columns travel together,
  and the CHECK refuses a row that carries one without the other: a
  publication nobody signed and a signature with no moment are both
  half-facts.

**Retraction is not withdrawal.** Withdrawing a rule is the state
machine's move (``withdrawn``, with a reason, and the rule stops being
served everywhere). Retracting a *sharing* only narrows who may see it:
the row's ``shared_scope`` goes back to ``private`` and the publication
columns are cleared. A rule the group may not see any more may still be
the rule its own project cites.

**Direct DDL against ``sa`` types**, for the reason 0007, 0012, 0014,
0021, 0023, 0024, 0025, 0027 and 0029 record: a frozen revision must not
import today's ``labcairn.db.models``, or the schema it installs drifts
with the code around it. Datetime columns are ``sa.String()`` because the
models' ``UtcDateTime`` is a ``TypeDecorator`` over ``String`` and the
parity witness compares compiled types.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ``private`` is the fact for every row that predates this revision:
    # nothing was shared before there was a sharing to record.
    op.add_column(
        "guidance_rules",
        sa.Column(
            "shared_scope",
            sa.String(length=16),
            nullable=False,
            server_default="private",
        ),
    )
    op.add_column("guidance_rules", sa.Column("published_by", sa.Text(), nullable=True))
    op.add_column("guidance_rules", sa.Column("published_at", sa.String(), nullable=True))
    # SQLite has no ``ALTER TABLE ... ADD CONSTRAINT``, so the checks are
    # added through the batch path (the reason 0001's own alterations are
    # batched): the table is rebuilt with the constraints in place.
    with op.batch_alter_table("guidance_rules", schema=None) as batch_op:
        batch_op.create_check_constraint(
            "guidance_rules_sharing_vocabulary",
            "shared_scope IN ('private', 'group')",
        )
        batch_op.create_check_constraint(
            "guidance_rules_a_publication_carries_its_publisher_and_moment",
            "(shared_scope = 'group') = "
            "(published_by IS NOT NULL AND length(trim(published_by)) > 0 "
            "AND published_at IS NOT NULL)",
        )


def downgrade() -> None:
    with op.batch_alter_table("guidance_rules", schema=None) as batch_op:
        batch_op.drop_constraint(
            "guidance_rules_a_publication_carries_its_publisher_and_moment",
            type_="check",
        )
        batch_op.drop_constraint(
            "guidance_rules_sharing_vocabulary",
            type_="check",
        )
    op.drop_column("guidance_rules", "published_at")
    op.drop_column("guidance_rules", "published_by")
    op.drop_column("guidance_rules", "shared_scope")
