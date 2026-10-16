"""event payload and document split

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-16 22:10:00.000000

ADR-0007. Revision 0001 created an ``events.payload`` column holding the whole
frozen ``Event`` document. ADR-0003 C1 reserves the name ``payload`` for the
**type-specific** content an event carries, validated against that type's model.
Two different things sharing one name is how a reader comes to believe the store
keeps the C1 payload when it keeps something else.

So: the existing column is renamed to ``document``, and a new ``payload`` column
is added for what C1 actually specifies.

**Direct DDL rather than ``op.batch_alter_table``.** Batch mode chooses between
ALTER TABLE and a table rewrite by reflecting the live schema, and it silently
did nothing here: the revision stamped as applied while the column kept its old
name, twice — once under the default and once with ``recreate="always"``. The
same call works on a hand-made table, so the reflection is what fails, most
likely on the ``UtcDateTime`` column type the ORM uses and 0001 renders as
``sa.Text()``. A migration that reports success and changes nothing is the worst
of the available failures, so this revision issues the statements it means.

SQLite supports ``ALTER TABLE ... RENAME COLUMN`` since 3.25, and the minimum
Python this project targets ships far newer.

Downgrade undoes each statement in reverse, so a rollback is the same shape.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE events RENAME COLUMN payload TO document")
    op.add_column(
        "events",
        sa.Column("payload", sa.Text(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("events", "payload")
    op.execute("ALTER TABLE events RENAME COLUMN document TO payload")
