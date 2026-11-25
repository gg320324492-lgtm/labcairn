"""the capability probe's record of what one endpoint can do

Revision ID: 0031
Revises: 0030
Create Date: 2026-11-25

ADR-0002 §Contracts promised that "Probe results are cached per
``(endpoint, model, protocol)`` in SQLite with a timestamp and are
invalidated by a protocol or endpoint change", and that "a ``doctor --probe``
[exists] so users opt in". Neither half was there: the only cache was a
dict in memory that no product code read, so a probe result was a thing a
document could record and the product could not. A real capability probe
was run against the signed authorisation's endpoint on 2026-11-25
(``docs/acceptance/LC-P4-PILOT-capability-probe-2026-11-25.md``) and its
reading lived only in that document; ``doctor`` on the same workspace still
said every capability was unverified, and the capability gate had nothing to
read.

**The row is the measurement the product keeps.** One row per
``(endpoint, model, protocol)``, carrying the outcome of each capability,
the one-liner that explains it, the capabilities a request was actually
issued for, and the UTC instant the probe ran.

**Why the endpoint is a fingerprint and not a URL.** A base URL can carry a
credential -- ``?api_key=``, or userinfo -- and this row is meant to be
readable, reportable and shareable. The fingerprint cannot be reversed into
a host, and two configurations pointing at the same host with different keys
produce the same fingerprint, because they have the same capabilities.

**Why the key is a unique constraint and not a primary key.** The key *is*
the identity of the observation, so "invalidated by a protocol or endpoint
change" is exactly the statement that a record for a different protocol is a
*different row*. A primary key on the triple would have said the same thing
but left no room for the row identity every other table in this store
carries; the unique constraint says it and keeps ``id`` free.

Direct DDL against ``sa`` types, for the reason 0007, 0012, 0021, 0023,
0024, 0025 and 0027 record: a frozen revision must not import today's
``labcairn.db.models``, or the schema it installs drifts with the code
around it. Datetime columns are ``sa.String()`` for the same reason
earlier revisions spell them so: the models' ``UtcDateTime`` is a
``TypeDecorator`` over ``String``, and the parity witness compares
compiled types.

**The row holds class names, never text.** The evidence strings are
LabCairn-authored one-liners -- an exception's class name, or a fixed
phrase -- and never an exception message, which may echo a credential.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "probe_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # The opaque endpoint key: a sha256 hex digest, 64 characters. A
        # URL would carry a credential.
        sa.Column("endpoint_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("protocol", sa.String(length=64), nullable=False),
        # Capability value -> outcome value. The four capabilities and the
        # four outcomes are closed vocabularies.
        sa.Column("outcomes", sa.JSON(), nullable=False),
        # Capability value -> the LabCairn-authored one-liner that explains
        # it. An exception's class name or a fixed phrase, never a message.
        sa.Column("evidence", sa.JSON(), nullable=False),
        # The capabilities a request was actually issued for. A capability
        # absent from here was never asked about, which is not the same as
        # having failed.
        sa.Column("probes_run", sa.JSON(), nullable=False),
        # When the probe ran. UTC.
        sa.Column("observed_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        # The key is the observation's identity, so a record for a
        # different protocol or endpoint is a different row rather than an
        # overwrite of this one.
        sa.UniqueConstraint(
            "endpoint_fingerprint",
            "model",
            "protocol",
            name="uq_probe_records_key",
        ),
        sa.CheckConstraint(
            "length(endpoint_fingerprint) > 0 AND length(model) > 0 AND length(protocol) > 0",
            name="probe_records_key_present",
        ),
    )


def downgrade() -> None:
    op.drop_table("probe_records")
