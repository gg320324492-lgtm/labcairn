"""scholarly identifiers: a record can carry one, and resolution is a state

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-02

**The half of LC-P1-09's acceptance clause that was never built.** Its review
was explicit about the shape of the gap: *no record can carry an identifier,
nothing resolves one, and ingestion records none*. A claim whose support
named a DOI had nowhere to put the DOI, and a reader was never told whether
anyone had resolved it. This revision writes the shelf and the state that
lives on it.

**``identifier_records`` is a registry, not a decoration.** Three closed
vocabularies -- what kind of identifier, who supplied it, whether anyone has
resolved it -- and the provenance is the one the work order is about: a model
may propose an identifier, and **proposing is not checking**, the same rule
``EvidenceCreator.MODEL_PROPOSAL`` already applies to a proposed record. The
column that carries who supplied it is the thing that makes the difference
readable; nothing else has to remember it.

**Resolution is a state, not a failure.** ``unresolved`` is what a freshly
recorded identifier holds and a first-class answer, not an error to be
swallowed. ``not_attempted`` is what a resolution *request* records in this
build, because resolving a scholarly identifier means contacting an external
service and this build cannot consent an outbound lookup: the closed
capability registry (ADR-0006) defines exactly one network-effect capability,
``model.request``, which is consent to prompt a provider and consent to
nothing else, and the bridge between the two vocabularies is unbuilt. A
request that cannot be consented is **recorded rather than silently sent or
silently dropped** -- that is what ``not_attempted`` is for, and the reason it
is a member of the vocabulary rather than an exit code.

**A resolution state carries the evidence of what it names.** The three
CHECK constraints below are one idea in three rows. ``unresolved`` carries no
detail, no resolver and no time, because nothing has happened yet;
``not_attempted`` carries the reason it did not happen and nothing else, so a
resolver's name cannot ride on a lookup that never ran; ``resolved`` carries
who answered, what they found and when, because a resolution without its
detail is a "verified" nobody can audit. A state whose fields disagree with
it is not a state, so the schema refuses the row rather than storing it for a
reader to trip over.

**One identifier, one row per task.** ``UNIQUE(task_id, scheme, value)``: a
second row for the same identifier would make "is it resolved" answerable two
ways, and two rows that disagree would let a report pick the friendlier one.

**What this revision does not do.** It adds no resolver. Nothing here opens a
socket, and nothing in the tree does either: a future resolver must arrive
through the consent layer with a capability that exists, and until then a
request lands as ``not_attempted``. And it changes no existing table, so a
database at 0020 upgrades without rewriting a single row.

Direct DDL, for the reason 0007 records: a frozen revision must not import
today's ``labcairn.db.models``, or editing that class would silently rewrite
what this revision meant to create. The rows this revision must refuse are
witnessed by writing them in ``tests/test_identifier_records.py`` and watching
the database refuse each one.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: The three vocabularies, spelled out rather than imported, for the same
#: reason every frozen revision spells its own law out: this file is the
#: record of what the schema said at the moment it was frozen. **Sorted, not
#: declared-order**: the ORM metadata renders these constraints through
#: ``sql_string_list``, which sorts, and the parity test compares the texts
#: -- so the frozen file spells the same order the live helper produces.
_SCHEMES: Final[tuple[str, ...]] = ("arxiv", "doi")
_PROVENANCES: Final[tuple[str, ...]] = ("ingestion", "model", "person")
_RESOLUTION_STATES: Final[tuple[str, ...]] = ("not_attempted", "resolved", "unresolved")


def _vocabulary(values: tuple[str, ...]) -> str:
    return "(" + ", ".join(f"'{value}'" for value in values) + ")"


def upgrade() -> None:
    op.create_table(
        "identifier_records",
        sa.Column("identifier_id", sa.String(length=200), nullable=False),
        sa.Column("task_id", sa.String(length=200), nullable=False),
        sa.Column("scheme", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("supplied_by", sa.String(length=32), nullable=False),
        sa.Column("supplied_by_id", sa.String(length=200), nullable=False),
        sa.Column("resolution_state", sa.String(length=32), nullable=False),
        # Nullable because a state must *say* it carries nothing rather than
        # omitting it -- the empty string would read as a detail that is empty,
        # and NULL reads as one that was never written. The CHECK constraints
        # below are what make the difference enforced.
        sa.Column("resolution_detail", sa.Text(), nullable=True),
        sa.Column("resolved_by", sa.String(length=200), nullable=True),
        sa.Column("resolved_at", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("identifier_id"),
        sa.UniqueConstraint("task_id", "scheme", "value", name="uq_identifier_task_scheme_value"),
        sa.CheckConstraint(
            f"scheme IN {_vocabulary(_SCHEMES)}", name="identifier_scheme_vocabulary"
        ),
        sa.CheckConstraint(
            f"supplied_by IN {_vocabulary(_PROVENANCES)}",
            name="identifier_provenance_vocabulary",
        ),
        sa.CheckConstraint(
            f"resolution_state IN {_vocabulary(_RESOLUTION_STATES)}",
            name="identifier_resolution_vocabulary",
        ),
        sa.CheckConstraint(
            "length(identifier_id) > 0 AND length(task_id) > 0"
            " AND length(value) > 0 AND length(supplied_by_id) > 0",
            name="identifier_fields_present",
        ),
        sa.CheckConstraint(
            "resolution_state != 'unresolved' OR (resolution_detail IS NULL"
            " AND resolved_by IS NULL AND resolved_at IS NULL)",
            name="identifier_unresolved_carries_nothing",
        ),
        sa.CheckConstraint(
            "resolution_state != 'not_attempted' OR (resolution_detail IS NOT NULL"
            " AND resolved_by IS NULL AND resolved_at IS NULL)",
            name="identifier_not_attempted_says_why",
        ),
        sa.CheckConstraint(
            "resolution_state != 'resolved' OR (resolution_detail IS NOT NULL"
            " AND resolved_by IS NOT NULL AND resolved_at IS NOT NULL)",
            name="identifier_resolved_says_who",
        ),
    )
    op.create_index("ix_identifier_records_task", "identifier_records", ["task_id"])

    op.create_table(
        "evidence_identifiers",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("evidence_id", sa.String(length=200), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("identifier_id", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        # Not a foreign key to ``identifier_records``, for the same reason
        # ``evidence_anchors`` carries none to ``source_anchors``: an
        # identifier id naming nothing is a finding for the ledger's checks to
        # report, not a constraint error to replace them. A foreign key would
        # make the row unstorable instead, turning a checkable failure into a
        # constraint error no caller can read.
        sa.UniqueConstraint("evidence_id", "position", name="uq_evidence_identifiers_position"),
        sa.UniqueConstraint(
            "evidence_id", "identifier_id", name="uq_evidence_identifiers_identifier"
        ),
        sa.CheckConstraint("position >= 0", name="evidence_identifiers_position_non_negative"),
        sa.CheckConstraint(
            "length(identifier_id) > 0 AND length(evidence_id) > 0",
            name="evidence_identifiers_ids_present",
        ),
    )
    op.create_index("ix_evidence_identifiers_identifier", "evidence_identifiers", ["identifier_id"])


def downgrade() -> None:
    op.drop_index("ix_evidence_identifiers_identifier", table_name="evidence_identifiers")
    op.drop_table("evidence_identifiers")
    op.drop_index("ix_identifier_records_task", table_name="identifier_records")
    op.drop_table("identifier_records")
