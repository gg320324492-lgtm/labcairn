"""the guidance memory: rules that carry their sources, and the cases against them

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-31

LC-P2-11. The mentor line's rule memory: one row per version of a rule,
one per binding to the chain material it was learned from, and one per
case where the rule does not hold.

**One migration, three tables**, for the reason 0013 records: they are one
design -- a rule, its sources, and its counterexamples -- and splitting
them would mean three migrations for one decision.

**The three decisions the schema holds, and each is a refusal.**

**A rule is a record, not an opinion.** The work order's "must not" is
*"an advisor prefers this style"*, and the schema refuses exactly that: a
rule carries a problem from the closed vocabulary, a statement, a context,
a scope, an example it was derived from, and a proposer. A row with an
empty field in any of those is not stored.

**The state machine is closed, and each state has its evidence.** A
``confirmed`` row names its confirmer -- who may not be the proposer,
which the API refuses and this schema cannot see across rows. A
``disputed`` or ``withdrawn`` row carries its reason, and a ``candidate``
row carries neither a confirmation nor a reason: a candidate carrying a
confirmation is a record pretending it was confirmed before it was.

**And a new statement is a new row.** The primary key of a rule is the
pair of its id and its version; the sources and the counterexamples bind
to the pair, because a new statement may rest on new cases. Retrieval
serves each rule's highest version and nothing else.

Direct DDL, for the reason 0007 records: a frozen revision must not import
today's ``labcairn.db.models``, or editing that class would silently
rewrite what this revision meant to create.
``tests/test_store_migrations.py``'s parity test holds the two together,
and the rows this revision must refuse are witnessed again by writing
them -- a text comparison cannot catch a migration and a model wrong
together.

**What the database cannot say.** *A rule carries at least one source* is
true and enforced, but not here: a cross-table ``CHECK`` is not SQLite's
to give. The API that proposes rules refuses a sourceless one, and the
witness writes the refusal at that layer.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "guidance_rules",
        # Caller-minted, so a rule may be cited before the row that
        # carries it is written.
        sa.Column("rule_id", sa.Text(), nullable=False),
        # The rule's version, from one. A new statement is a new row.
        sa.Column("version", sa.Integer(), nullable=False),
        # What problem the rule addresses, from the closed vocabulary.
        sa.Column("issue_type", sa.String(64), nullable=False),
        # What the rule says. A rule without a statement is a preference.
        sa.Column("statement", sa.Text(), nullable=False),
        # When the rule applies: the situation a reader would recognise.
        sa.Column("context", sa.Text(), nullable=False),
        # The domain and situation it applies in.
        sa.Column("scope", sa.Text(), nullable=False),
        # A case the rule was derived from, not invented to illustrate it.
        sa.Column("example", sa.Text(), nullable=False),
        # candidate | confirmed | disputed | withdrawn (ADR-0016 D8).
        sa.Column("state", sa.String(32), nullable=False),
        # Who proposed the rule: a person, or a distillation run whose
        # proposal lands here as a candidate.
        sa.Column("proposed_by", sa.Text(), nullable=False),
        # When it was proposed.
        sa.Column("proposed_at", sa.String(), nullable=False),
        # Who confirmed it -- a second reader; the API refuses the
        # proposer -- and when. Null on a candidate.
        sa.Column("confirmed_by", sa.Text(), nullable=True),
        sa.Column("confirmed_at", sa.String(), nullable=True),
        # Why the rule was disputed or withdrawn. Null on a live rule.
        sa.Column("resolution_reason", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("rule_id", "version"),
        # **The problem comes from the closed vocabulary.** The thirteen
        # labels LC-P2-10 defines; a fourteenth arrives by a migration.
        sa.CheckConstraint(
            "issue_type IN ('research_question_and_motivation',"
            "'novelty_and_contribution','introduction_and_storyline',"
            "'method_and_hypothesis','data_quality','controls_and_ablation',"
            "'statistical_conclusion','figures','sources','review_response',"
            "'language_and_format','other','unknown')",
            name="guidance_rules_the_problem_is_from_the_vocabulary",
        ),
        # **No field of a rule is empty.** Empty means blank as well as
        # absent: SQLite's ``length`` counts the spaces a shrug is made
        # of, so the check trims before it counts.
        sa.CheckConstraint(
            "length(trim(statement)) > 0 AND length(trim(context)) > 0"
            " AND length(trim(scope)) > 0 AND length(trim(example)) > 0"
            " AND length(trim(proposed_by)) > 0",
            name="guidance_rules_no_field_of_a_rule_is_empty",
        ),
        # **The state machine is closed.**
        sa.CheckConstraint(
            "state IN ('candidate','confirmed','disputed','withdrawn')",
            name="guidance_rules_the_state_machine_is_closed",
        ),
        # **A confirmed rule names its confirmer.**
        sa.CheckConstraint(
            "state != 'confirmed' OR (confirmed_by IS NOT NULL"
            " AND length(trim(confirmed_by)) > 0 AND confirmed_at IS NOT NULL)",
            name="guidance_rules_a_confirmed_rule_names_its_confirmer",
        ),
        # **A candidate names nobody.**
        sa.CheckConstraint(
            "state != 'candidate' OR (confirmed_by IS NULL AND confirmed_at IS NULL)",
            name="guidance_rules_a_candidate_names_nobody",
        ),
        # **A disputed or withdrawn rule carries its reason.**
        sa.CheckConstraint(
            "state NOT IN ('disputed','withdrawn')"
            " OR (resolution_reason IS NOT NULL AND length(trim(resolution_reason)) > 0)",
            name="guidance_rules_a_resolution_carries_its_reason",
        ),
        # **And a resolution names nothing on a live rule.**
        sa.CheckConstraint(
            "state IN ('disputed','withdrawn') OR resolution_reason IS NULL",
            name="guidance_rules_a_live_rule_carries_no_resolution",
        ),
    )
    op.create_table(
        "guidance_rule_sources",
        # Table-wide identity, never used for ordering.
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        # The rule and the version the source belongs to. A source is
        # bound to a version because a new statement may rest on new
        # cases.
        sa.Column("rule_id", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        # The chain's own key for the material the rule was learned from.
        sa.Column("issue_key", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["rule_id", "version"],
            ["guidance_rules.rule_id", "guidance_rules.version"],
            ondelete="CASCADE",
        ),
        # **A source that names nothing is not a source.**
        sa.CheckConstraint(
            "length(trim(issue_key)) > 0",
            name="guidance_rule_sources_a_source_names_its_material",
        ),
        # **And the same material is bound to a version once.**
        sa.UniqueConstraint(
            "rule_id",
            "version",
            "issue_key",
            name="guidance_rule_sources_one_binding_per_material",
        ),
    )
    op.create_table(
        "guidance_rule_counterexamples",
        # Table-wide identity, never used for ordering.
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        # The rule and the version the counterexample challenges.
        sa.Column("rule_id", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        # The case: what was done, what the rule would have said, and
        # what actually held.
        sa.Column("statement", sa.Text(), nullable=False),
        # The chain material the counterexample came from, when it has
        # one. A counterexample recorded from a conversation has none,
        # and refusing to record it would lose the one case that stops
        # the rule.
        sa.Column("issue_key", sa.Text(), nullable=True),
        # Who recorded it, and when. **A counterexample is somebody's
        # reading, and the record says whose.**
        sa.Column("recorded_by", sa.Text(), nullable=False),
        sa.Column("recorded_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["rule_id", "version"],
            ["guidance_rules.rule_id", "guidance_rules.version"],
            ondelete="CASCADE",
        ),
        # **A counterexample with no case in it challenges nothing.**
        sa.CheckConstraint(
            "length(trim(statement)) > 0 AND length(trim(recorded_by)) > 0",
            name="guidance_rule_counterexamples_a_counterexample_carries_its_case",
        ),
    )


def downgrade() -> None:
    op.drop_table("guidance_rule_counterexamples")
    op.drop_table("guidance_rule_sources")
    op.drop_table("guidance_rules")
