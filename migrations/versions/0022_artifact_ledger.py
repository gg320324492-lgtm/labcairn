"""the artifact ledger becomes durable: what a run produced outlives the run

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-02

**The debt is G2's, not a new feature.** ``ArtifactLedger`` has answered *"is
this artifact the one the run made?"* by re-hashing on every read since
LC-P1-07, but it kept the entries in a list in the process that made them. A
restart lost the record, a second reader saw nothing, and the two properties the
ledger exists for -- provenance at write time, integrity at read time -- only
held for as long as nobody closed the window. G2's acceptance recorded the gap;
this revision writes the shelf the entries live on.

**The table is history, not a current view.** A stage that runs twice adds a
second row; no row is ever updated. ``by_stage`` is derived by taking the latest
entry per stage in ``entry_id`` order, so the current answer and the history
cannot disagree -- there is only one record, read two ways.

**``payload`` is the canonical JSON the digest is over.** The digest is not
recomputed from a re-serialisation of a parsed model: the stored bytes are the
bytes ``artifact_digest`` hashed, and a reader re-hashes exactly those bytes
after validating that they parse as the declared kind. ``digest_algorithm``
rides beside the digest because a stored digest is only comparable with another
digest from the same algorithm, and a row written by an older release must be
refused rather than silently compared.

**``ledger_id`` keeps two runs in one database apart.** Nothing in the ledger
was ever global; the orchestrator's contract is one ledger per run. Making the
ledger durable without that column would have made "the ledger" mean "the
database", which is the opposite of what the orchestrator promises.

**There is no UNIQUE on ``stage``.** A re-run is a fact to keep, not a conflict
to refuse. The write-time and read-time checks decide whether an entry is
trustworthy; the schema's job is to keep every entry it accepted.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: The two closed vocabularies, spelled out and **sorted**, for the reason
#: revision 0021 records: the ORM renders CHECK bodies through
#: ``sql_string_list``, which sorts, and the parity test compares the texts.
_KINDS: Final[tuple[str, ...]] = (
    "delivered_report",
    "evidence_ledger",
    "report_draft",
    "research_objective",
    "research_proposal",
    "retrieved_excerpts",
    "source_inventory",
    "validation_report",
)
_STAGES: Final[tuple[str, ...]] = (
    "deliver",
    "draft",
    "evidence",
    "intake",
    "inventory",
    "propose",
    "retrieve",
    "validate",
)


def _vocabulary(values: tuple[str, ...]) -> str:
    return "(" + ", ".join(f"'{value}'" for value in values) + ")"


def upgrade() -> None:
    op.create_table(
        "artifact_ledger_entries",
        # Local insertion order. It is not an artifact identity; it is what
        # makes "oldest first" and "latest per stage" answerable later.
        sa.Column("entry_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ledger_id", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        # The canonical JSON ``artifact_digest`` hashed, byte for byte.
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("digest_algorithm", sa.String(length=64), nullable=False),
        # NULL means the artifact was installed by ``adopt_artifact`` rather
        # than produced by a stage. The difference is kept, not erased.
        sa.Column("produced_by", sa.String(length=32), nullable=True),
        sa.Column("recorded_at", sa.String(), nullable=False),
        sa.CheckConstraint(
            f"kind IN {_vocabulary(_KINDS)}",
            name="artifact_ledger_entry_kind_vocabulary",
        ),
        sa.CheckConstraint(
            f"stage IN {_vocabulary(_STAGES)}",
            name="artifact_ledger_entry_stage_vocabulary",
        ),
        sa.CheckConstraint(
            f"produced_by IS NULL OR produced_by IN {_vocabulary(_STAGES)}",
            name="artifact_ledger_entry_producer_vocabulary",
        ),
        sa.CheckConstraint("length(ledger_id) > 0", name="artifact_ledger_entry_ledger_id_present"),
        sa.CheckConstraint("length(payload) > 0", name="artifact_ledger_entry_payload_present"),
        sa.CheckConstraint("length(digest) = 64", name="artifact_ledger_entry_digest_length"),
        sa.CheckConstraint(
            "length(digest_algorithm) > 0",
            name="artifact_ledger_entry_algorithm_present",
        ),
    )
    op.create_index(
        "ix_artifact_ledger_entries_ledger",
        "artifact_ledger_entries",
        ["ledger_id", "entry_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_artifact_ledger_entries_ledger", table_name="artifact_ledger_entries")
    op.drop_table("artifact_ledger_entries")
