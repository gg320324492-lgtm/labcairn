"""the access grant table and the copies derived from material

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-29

LC-P2-06. The mentor-trajectory line's consent machinery: a row is a
permission somebody granted, and **the absence of a row is the refusal**.

**The table holds only grants.** There is no row shape that means "denied"
and no ``permitted`` column, because ADR-0015 D2 says the permission is
*denied in the model*: "There is no row, so there is nothing to check, so
the path cannot proceed." A column that could hold ``False`` could also be
flipped to ``True`` by an update nobody audited.

**And the four permissions are four grant kinds**, each independently
absent, independently withdrawn, independently expiring -- not one row with
four flags, because that is the shape that lets one withdrawal quietly leave
the other three standing.

**A transmit grant names one destination, and the other three name none.**
A transmit grant with no destination is a grant to send anywhere, which is
the thing ADR-0015 D3 exists to prevent.

**The second table is the propagation.** ``derived_copies`` records the
grant a copy was made under, so a withdrawal can reach it: the design asks
whether historical embeddings, caches and training queues expire when
consent is withdrawn, and the answer has to be a fact rather than a
promise. It makes the *next* use impossible -- it cannot undo a copy that
has already been used, and the record says so.

Direct DDL, for the reason 0007 records: a frozen revision must not import
today's ``labcairn.db.models``, or editing that class would silently
rewrite what this revision meant to create.
``tests/test_store_migrations.py``'s parity test holds the two together, and
the rows this revision must refuse are witnessed again by writing them -- a
text comparison cannot catch a migration and a model wrong together.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "access_grants",
        # Caller-minted: a grant is cited from an earlier run and from a
        # decision record, so identity cannot depend on insertion order.
        sa.Column("grant_id", sa.Text(), nullable=False),
        sa.Column("subject_ref", sa.Text(), nullable=False),
        # What the grant IS. One of the four.
        sa.Column("permission", sa.String(32), nullable=False),
        # What the grant is FOR. The narrow axis: the same permission can
        # be granted for reading and refused for training.
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("scope", sa.String(2000), nullable=False),
        # Where the material may go. Required for external_transmit and
        # forbidden for the other three.
        sa.Column("destination", sa.String(200), nullable=True),
        sa.Column("granted_by", sa.String(200), nullable=False),
        # sa.String(), not sa.DateTime: the models use UtcDateTime, a
        # TypeDecorator whose impl is String because SQLite has no timestamp
        # type and SQLAlchemy's DateTime drops the offset.
        sa.Column("granted_at", sa.String(), nullable=False),
        sa.Column("expires_at", sa.String(), nullable=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("withdrawn_at", sa.String(), nullable=True),
        sa.Column("withdrawn_by", sa.String(200), nullable=True),
        sa.Column("withdrawal_reason", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("grant_id", name="pk_access_grants"),
        sa.CheckConstraint(
            "length(grant_id) > 0 AND length(subject_ref) > 0 AND length(scope) > 0 "
            "AND length(granted_by) > 0",
            name="access_grants_ids_present",
        ),
        # The four permissions, closed. A typo must not sail through as a
        # permission nobody holds.
        sa.CheckConstraint(
            "permission IN ('store_read', 'parse_annotate', 'external_transmit', 'train_reuse')",
            name="access_grants_permission_vocabulary",
        ),
        # The five purposes, closed, on the same standard.
        sa.CheckConstraint(
            "purpose IN ('read', 'annotate', 'retrieve', 'transmit', 'train')",
            name="access_grants_purpose_vocabulary",
        ),
        sa.CheckConstraint(
            "state IN ('active', 'withdrawn', 'expired')",
            name="access_grants_state_vocabulary",
        ),
        # A transmit grant names one destination, and the other three name
        # none.
        sa.CheckConstraint(
            "(permission = 'external_transmit' AND destination IS NOT NULL "
            "AND length(destination) > 0) OR "
            "(permission <> 'external_transmit' AND destination IS NULL)",
            name="access_grants_destination_belongs_to_transmit",
        ),
        # A withdrawal names who and when.
        sa.CheckConstraint(
            "(state = 'withdrawn' AND withdrawn_by IS NOT NULL "
            "AND length(withdrawn_by) > 0 AND withdrawn_at IS NOT NULL) OR "
            "(state <> 'withdrawn' AND withdrawn_by IS NULL AND withdrawn_at IS NULL)",
            name="access_grants_withdrawal_names_who_and_when",
        ),
    )
    op.create_index("ix_access_grants_subject", "access_grants", ["subject_ref"])
    op.create_index("ix_access_grants_permission", "access_grants", ["permission"])

    op.create_table(
        "derived_copies",
        sa.Column("copy_id", sa.Text(), nullable=False),
        # The provenance. The whole reason the row exists.
        sa.Column(
            "grant_id",
            sa.Text(),
            sa.ForeignKey("access_grants.grant_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("location", sa.String(2000), nullable=False),
        sa.Column("subject_ref", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("copy_id", name="pk_derived_copies"),
        sa.CheckConstraint(
            "length(copy_id) > 0 AND length(grant_id) > 0 AND length(kind) > 0 "
            "AND length(location) > 0 AND length(subject_ref) > 0",
            name="derived_copies_ids_present",
        ),
        sa.CheckConstraint(
            "kind IN ('index_entry', 'embedding', 'queued_run', 'cached_transcript', "
            "'distilled_rule')",
            name="derived_copies_kind_vocabulary",
        ),
    )
    op.create_index("ix_derived_copies_grant", "derived_copies", ["grant_id"])


def downgrade() -> None:
    op.drop_index("ix_derived_copies_grant", table_name="derived_copies")
    op.drop_table("derived_copies")
    op.drop_index("ix_access_grants_permission", table_name="access_grants")
    op.drop_index("ix_access_grants_subject", table_name="access_grants")
    op.drop_table("access_grants")
