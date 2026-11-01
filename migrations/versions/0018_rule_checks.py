"""the guidance memory: the checks that decide the rules, and the binding

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-01

LC-P2-11's next piece. The memory holds rules -- what the advisor demands,
recovered from where their hand went -- and it now holds **checks**: the
questions a reader can run against a manuscript and answer yes or no. The
two tables this revision writes are the check and the binding, and the
binding is the one that makes them one thing rather than two documents.

**One migration, two tables**, for the reason 0015 records: they are one
design -- a check, and the rule it decides -- and splitting them would
mean two migrations for one decision.

**A check is two fields, and the two are not the same field.** The
``question`` is what a reader asks of the manuscript; the
``pass_criterion`` is the condition under which the answer is yes. A
question with no criterion cannot be answered, and a criterion with no
question decides nothing, so the schema refuses a row that is missing
either.

**The check is a norm, and a norm lives beside the rules it decides.** It
is not in the chain: the chain is the mentor's material, and a checklist
written down in advance is not the mentor's material. It is not a
counterexample either: a counterexample is a case *against* a rule, and a
check is a test *for* one.

**The binding is to the version, not to the rule.** A rule is a versioned
row and a new statement is a new row, so the check that decides version
1's words is not automatically the check that decides version 2's words --
and the binding names the pair for that reason. Both foreign keys are the
schema's own witnesses: a binding to a check that does not exist, or to a
version of a rule that does not exist, cannot be written.

**What the database cannot say.** *A rule may name only a confirmed
check* is true and enforced, but not here: it is a fact about two rows,
and a cross-table ``CHECK`` is not SQLite's to give. The API refuses it,
and the witness writes the refusal at that layer. *A rule names a check
only while it is a candidate*, and *a withdrawn rule names no check*, are
the same kind of fact.

Direct DDL, for the reason 0007 records: a frozen revision must not import
today's ``labcairn.db.models``, or editing that class would silently
rewrite what this revision meant to create.
``tests/test_store_migrations.py``'s parity test holds the two together,
and the rows this revision must refuse are witnessed again by writing
them -- a text comparison cannot catch a migration and a model wrong
together.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "guidance_checks",
        # The check's identity, derived from what it says and who said it.
        sa.Column("check_id", sa.Text(), nullable=False),
        # What the reader asks of the manuscript.
        sa.Column("question", sa.Text(), nullable=False),
        # The condition under which the answer is yes. Different from the
        # question, and required with it.
        sa.Column("pass_criterion", sa.Text(), nullable=False),
        # candidate | confirmed | withdrawn.
        sa.Column("state", sa.String(32), nullable=False),
        # Who proposed the check: a person, or a run whose proposal lands
        # here as a candidate.
        sa.Column("proposed_by", sa.Text(), nullable=False),
        sa.Column("proposed_at", sa.String(), nullable=False),
        # Who confirmed it -- a second reader; the API refuses the proposer
        # -- and when. Null on a candidate.
        sa.Column("confirmed_by", sa.Text(), nullable=True),
        sa.Column("confirmed_at", sa.String(), nullable=True),
        # Why the check was withdrawn. Null on a live check.
        sa.Column("resolution_reason", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("check_id", name="pk_guidance_checks"),
        # **A check carries its question and its criterion, and neither may
        # be empty.** Empty means blank as well as absent, so the check
        # trims before it counts.
        sa.CheckConstraint(
            "length(trim(question)) > 0 AND length(trim(pass_criterion)) > 0"
            " AND length(trim(proposed_by)) > 0",
            name="guidance_checks_a_check_carries_its_question_and_its_criterion",
        ),
        # **The state machine is closed.**
        sa.CheckConstraint(
            "state IN ('candidate','confirmed','withdrawn')",
            name="guidance_checks_the_state_machine_is_closed",
        ),
        # **A confirmed check names its confirmer.**
        sa.CheckConstraint(
            "state != 'confirmed' OR (confirmed_by IS NOT NULL"
            " AND length(trim(confirmed_by)) > 0 AND confirmed_at IS NOT NULL)",
            name="guidance_checks_a_confirmed_check_names_its_confirmer",
        ),
        # **A candidate names nobody.**
        sa.CheckConstraint(
            "state != 'candidate' OR (confirmed_by IS NULL AND confirmed_at IS NULL)",
            name="guidance_checks_a_candidate_names_nobody",
        ),
        # **A withdrawn check carries its reason.**
        sa.CheckConstraint(
            "state != 'withdrawn' OR (resolution_reason IS NOT NULL"
            " AND length(trim(resolution_reason)) > 0)",
            name="guidance_checks_a_withdrawal_carries_its_reason",
        ),
        # **And a live check carries no resolution.**
        sa.CheckConstraint(
            "state = 'withdrawn' OR resolution_reason IS NULL",
            name="guidance_checks_a_live_check_carries_no_resolution",
        ),
    )
    op.create_table(
        "guidance_rule_checks",
        # Table-wide identity, never used for ordering.
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        # The rule and the version the binding belongs to. A binding is to a
        # version because a new statement may be decided by a different
        # check.
        sa.Column("rule_id", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        # The check that decides the rule at that version.
        sa.Column("check_id", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["rule_id", "version"],
            ["guidance_rules.rule_id", "guidance_rules.version"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["check_id"],
            ["guidance_checks.check_id"],
            ondelete="CASCADE",
        ),
        # **And the same check is bound to a version once.** Two rules may
        # name the same check; one rule names one check once.
        sa.UniqueConstraint(
            "rule_id",
            "version",
            "check_id",
            name="guidance_rule_checks_one_binding_per_check",
        ),
    )
    op.create_index("ix_guidance_rule_checks_check", "guidance_rule_checks", ["check_id"])


def downgrade() -> None:
    op.drop_index("ix_guidance_rule_checks_check", table_name="guidance_rule_checks")
    op.drop_table("guidance_rule_checks")
    op.drop_table("guidance_checks")
