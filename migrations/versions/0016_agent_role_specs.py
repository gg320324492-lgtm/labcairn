"""the role contract, as data: one row per version of a role's terms

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-31

LC-P2-12 T00. The three roles of the guidance loop work under contracts
that are rows, not prompts (ADR-0018 D1): the objective, the typed input
and output schemas, the capabilities the role may exercise, the actions
it may not take, the purposes it may read material for, the budgets and
the routing, and the conditions under which it abstains and under which
it hands the work to a person.

**One table.** The contract's list clauses are JSON arrays in text
columns, for the reason the docstring records: a second table per list
would be four tables to read one contract. What the database can say
about a JSON column is ``json_valid`` and ``json_array_length``; what it
cannot say -- that every capability named is one the security layer has
registered, that every forbidden action is one of the five the
architecture closes -- the API refuses by name, and this revision's
docstring says so rather than pretending a text check said it.

**A new contract is a new row.** The primary key is the pair of the
role's id and the contract's version; editing a role's terms defines the
next version, and the old row keeps the terms it had.

Direct DDL, for the reason 0007 records: a frozen revision must not
import today's ``labcairn.db.models``, or editing that class would
silently rewrite what this revision meant to create.
``tests/test_store_migrations.py``'s parity test holds the two together,
and the rows this revision must refuse are witnessed by writing them.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_role_specs",
        # Caller-minted, so a role may be named before the row that
        # defines it is written.
        sa.Column("role_id", sa.Text(), nullable=False),
        # The contract's version, from one. A new contract is a new row.
        sa.Column("role_version", sa.Integer(), nullable=False),
        # What the role is for, in one sentence a reader can check the
        # role's outputs against.
        sa.Column("objective", sa.Text(), nullable=False),
        # The typed input and output models, as names in the code.
        sa.Column("input_schema", sa.Text(), nullable=False),
        sa.Column("output_schema", sa.Text(), nullable=False),
        # JSON arrays: the capabilities, the forbidden actions, the data
        # purposes. The vocabularies are the API's to check.
        sa.Column("allowed_capabilities", sa.Text(), nullable=False),
        sa.Column("forbidden_actions", sa.Text(), nullable=False),
        sa.Column("allowed_data_purposes", sa.Text(), nullable=False),
        # The routing policy's reference -- never a model id, never an
        # endpoint; the tree carries no supplier's name.
        sa.Column("provider_routing_policy", sa.Text(), nullable=False),
        # The cost ceiling, when one is priced. Null means no real call
        # is priced for this role yet, not unbounded.
        sa.Column("cost_budget", sa.Float(), nullable=True),
        # The ceilings a role always works under.
        sa.Column("token_budget", sa.Integer(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        # How failures are retried, and what happens when they are spent.
        sa.Column("retry_policy", sa.Text(), nullable=False),
        sa.Column("fallback_policy", sa.Text(), nullable=False),
        # JSON arrays: when the role abstains, and when it hands the work
        # to a person.
        sa.Column("abstain_conditions", sa.Text(), nullable=False),
        sa.Column("escalation_conditions", sa.Text(), nullable=False),
        # The prompt template's version -- a field of the contract, and
        # the least load-bearing one.
        sa.Column("prompt_template_version", sa.Text(), nullable=False),
        # A reference to a model configuration, not a model id.
        sa.Column("model_config_ref", sa.Text(), nullable=False),
        # When the contract was defined.
        sa.Column("defined_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("role_id", "role_version"),
        # **A contract binds from version one.**
        sa.CheckConstraint(
            "role_version >= 1",
            name="agent_role_specs_a_contract_binds_from_version_one",
        ),
        # **A contract with nothing in it binds nobody.** SQLite's
        # ``length`` counts the spaces a shrug is made of, so the check
        # trims before it counts.
        sa.CheckConstraint(
            "length(trim(objective)) > 0 AND length(trim(input_schema)) > 0"
            " AND length(trim(output_schema)) > 0"
            " AND length(trim(provider_routing_policy)) > 0"
            " AND length(trim(retry_policy)) > 0 AND length(trim(fallback_policy)) > 0"
            " AND length(trim(prompt_template_version)) > 0"
            " AND length(trim(model_config_ref)) > 0",
            name="agent_role_specs_a_contract_carries_its_terms",
        ),
        # **Every list column is a well-formed JSON array, and the lists
        # that cannot be empty are not.**
        sa.CheckConstraint(
            "json_valid(allowed_capabilities) AND json_valid(forbidden_actions)"
            " AND json_valid(allowed_data_purposes) AND json_valid(abstain_conditions)"
            " AND json_valid(escalation_conditions)",
            name="agent_role_specs_list_columns_hold_json_arrays",
        ),
        sa.CheckConstraint(
            "json_array_length(allowed_capabilities) > 0"
            " AND json_array_length(allowed_data_purposes) > 0"
            " AND json_array_length(abstain_conditions) > 0",
            name="agent_role_specs_a_role_may_work_read_for_a_purpose_and_abstain",
        ),
        # **A role always has a ceiling.**
        sa.CheckConstraint(
            "token_budget > 0 AND timeout_seconds > 0",
            name="agent_role_specs_a_role_works_under_a_ceiling",
        ),
    )


def downgrade() -> None:
    op.drop_table("agent_role_specs")
