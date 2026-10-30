"""the approval carries what the policy said, and what it was bound to

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-30

LC-P2-02 T00. ADR-0003 C4 binds an approval to the capability, the resource
key and the arguments digest, and requires that **the policy snapshot still
equals current policy** when the approval is spent. The row carried none of
that: `consume` took the policy digest and the bound sources **as arguments**,
so a caller could present a digest nobody had recorded and the store had
nothing to compare it with.

**Two facts, and both are about the moment of the grant.**

- `grant_policy_digest` is what the policy said **when the approval was
  granted**. It is null until granted, because a pending approval was decided
  by nobody and the digest of a policy that has not yet answered a question is
  not evidence about the answer. The spend compares it with the digest
  recomputed at the moment of use, so **a policy that changed between the two
  does not satisfy the old approval**.
- `bound_sources` is the material the consent covered, and the hash each file
  had then. **Empty is a fact** — the grant covered no source file — rather
  than an absence waiting to be filled in. A caller that could hand the
  binding over at the moment of use could hand over any binding at all.

**The columns are added directly rather than through the models.** The reason
is revision 0007's, recorded in every migration since: a frozen revision must
not import today's ORM, or editing that class would silently rewrite what the
revision meant to create. `tests/test_store_migrations.py` is the parity test
that holds this revision and the ORM together.

**Rows that exist get the honest answer.** A granted row with no recorded
digest is a row from before this revision; `grant_policy_digest` stays null,
and the spend refuses it rather than inventing a digest for it — an approval
whose policy answer nobody wrote down is not one the store can say still
holds.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "approvals",
        sa.Column("grant_policy_digest", sa.String(64), nullable=True),
    )
    # A NOT NULL column on a table that already holds rows needs a default,
    # and the default is the fact rather than a placeholder: no row was bound
    # to a source before this revision, and "none" is what that means.
    op.add_column(
        "approvals",
        sa.Column("bound_sources", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )


def downgrade() -> None:
    op.drop_column("approvals", "bound_sources")
    op.drop_column("approvals", "grant_policy_digest")
