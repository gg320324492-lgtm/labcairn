"""the feedback chain: a comment, the change it prompted, and what decided it

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-30

LC-P2-09. The mentor-trajectory line's four tables: one row per comment
found in a manuscript, one per change made in answer to it, one per
judgement that the change answered the comment, and one per later
assessment of the issue.

**One migration, four tables.** They are one design -- a question, an
edit, a response, and a later assessment -- and splitting them would mean
four migrations for one decision. The work order's file-ownership map
says the same thing: the migration subtasks write ``db/models.py`` in one
pass.

**The three decisions the schema holds, and each is a refusal.**

**A comment is an observation with two addresses.** A feedback row carries
the comment's own locator in ``word/comments.xml`` and the body-side
anchor, because "what did the advisor write" and "where did they write
it" are two questions. A row that kept only one would answer one of them.

**A candidate is not a comment.** A row read out of the file is
``observed`` and carries the locator the reader read; a row nobody read is
``inferred`` and carries **no** locator and **no** words. A row carrying
a locator nobody read *is* the advisor being claimed to have said
something, and the schema refuses one.

**Who made the change is a first-class fact.** ADR-0016 names *model ->
accepted change* as a promotion path, and the ``actor_kind`` column is
what makes a forged signature impossible to write by accident. A ``model``
row may not carry a person's id, and there is no default actor, because a
default is how a model's change becomes the advisor's.

**And a judgement is a judgement with evidence behind it.** The response
state is not a free choice: ``pending`` is the only state a row may hold
without a decision, and the other three require a decider and the
evidence. A status anybody can set is not a status.

**And the acceptance of a change is not an answer.** An assessment carries
its own evidence and rests on a closed vocabulary of bases that has **no
member meaning "the change was accepted"** -- the change being accepted
says the process went on, not that the advice was right.

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

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feedback_events",
        # Caller-minted, so a comment may be cited from an earlier run.
        sa.Column("feedback_id", sa.Text(), nullable=False),
        sa.Column(
            "project_id",
            sa.Text(),
            sa.ForeignKey("paper_projects.project_id", ondelete="CASCADE"),
            nullable=False,
        ),
        # The version the comment was written against. A feedback row
        # without one is refused: there is no "before" to answer against.
        sa.Column(
            "version_id",
            sa.Text(),
            sa.ForeignKey("paper_versions.version_id", ondelete="CASCADE"),
            nullable=False,
        ),
        # The comment's own address, as a JSON DocxLocator. Null only on an
        # inferred row, which read no comment of its own.
        sa.Column("comment_locator", sa.Text(), nullable=True),
        sa.Column("anchor_paragraph", sa.Integer(), nullable=True),
        sa.Column("anchor_start", sa.Integer(), nullable=True),
        sa.Column("anchor_end", sa.Integer(), nullable=True),
        sa.Column("anchor_status", sa.String(32), nullable=False),
        sa.Column("anchor_reason", sa.Text(), nullable=True),
        # The text the anchor covers, and its hash. The hash is what makes
        # drift detectable.
        sa.Column("anchor_text", sa.Text(), nullable=False),
        sa.Column("anchor_text_sha256", sa.String(64), nullable=False),
        sa.Column("comment_text", sa.Text(), nullable=False),
        sa.Column("comment_text_sha256", sa.String(64), nullable=False),
        # Unknown is None plus a named reason, never a guess.
        sa.Column("author", sa.String(200), nullable=True),
        sa.Column("author_unknown_reason", sa.Text(), nullable=True),
        sa.Column("commented_at", sa.String(), nullable=True),
        sa.Column("date_unknown_reason", sa.Text(), nullable=True),
        sa.Column("grade", sa.String(32), nullable=False),
        # A person-given key for "the same problem". Never inferred.
        sa.Column("issue_key", sa.String(200), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("feedback_id", name="pk_feedback_events"),
        sa.CheckConstraint(
            "length(feedback_id) > 0 AND length(project_id) > 0 AND length(version_id) > 0 "
            "AND length(comment_text_sha256) > 0 AND length(anchor_text_sha256) > 0",
            name="feedback_events_ids_present",
        ),
        sa.CheckConstraint(
            "grade IN ('observed', 'inferred', 'human_verified')",
            name="feedback_events_grade_vocabulary",
        ),
        sa.CheckConstraint(
            "anchor_status IN ('resolved', 'unknown')",
            name="feedback_events_anchor_status_vocabulary",
        ),
        # A resolved anchor names a place; an unknown one names a reason.
        sa.CheckConstraint(
            "(anchor_status = 'resolved' AND anchor_paragraph IS NOT NULL "
            "AND anchor_start IS NOT NULL AND anchor_end IS NOT NULL "
            "AND anchor_reason IS NULL) OR "
            "(anchor_status = 'unknown' AND anchor_reason IS NOT NULL "
            "AND length(anchor_reason) > 0 AND anchor_start IS NULL AND anchor_end IS NULL)",
            name="feedback_events_anchor_is_resolved_or_named",
        ),
        # The locator belongs to a read.
        sa.CheckConstraint(
            "(grade = 'inferred' AND comment_locator IS NULL) OR "
            "(grade <> 'inferred' AND comment_locator IS NOT NULL)",
            name="feedback_events_the_locator_belongs_to_a_read",
        ),
        # And an inferred row carries no words either.
        sa.CheckConstraint(
            "grade <> 'inferred' OR comment_text = ''",
            name="feedback_events_an_inferred_row_carries_no_words",
        ),
        # An issue key is a key or it is nothing.
        sa.CheckConstraint(
            "issue_key IS NULL OR length(issue_key) > 0",
            name="feedback_events_issue_key_is_present",
        ),
    )
    op.create_index("ix_feedback_events_version", "feedback_events", ["version_id"])
    op.create_index("ix_feedback_events_project", "feedback_events", ["project_id"])
    op.create_index("ix_feedback_events_issue_key", "feedback_events", ["issue_key"])

    op.create_table(
        "edit_actions",
        sa.Column("edit_action_id", sa.Text(), nullable=False),
        # Nullable: a change may answer nothing.
        sa.Column(
            "feedback_id",
            sa.Text(),
            sa.ForeignKey("feedback_events.feedback_id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "version_edge_id",
            sa.Text(),
            sa.ForeignKey("version_edges.edge_id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Who made it. There is no default actor.
        sa.Column("actor_kind", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.String(200), nullable=True),
        sa.Column("grade", sa.String(32), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("edit_action_id", name="pk_edit_actions"),
        sa.CheckConstraint(
            "length(edit_action_id) > 0 AND length(version_edge_id) > 0",
            name="edit_actions_ids_present",
        ),
        sa.CheckConstraint(
            "actor_kind IN ('student', 'advisor', 'model', 'human')",
            name="edit_actions_actor_kind_vocabulary",
        ),
        sa.CheckConstraint(
            "grade IN ('observed', 'inferred', 'human_verified')",
            name="edit_actions_grade_vocabulary",
        ),
        # A model is not a person and may not wear a person's id.
        sa.CheckConstraint(
            "(actor_kind = 'model' AND actor_id IS NULL) OR (actor_kind <> 'model')",
            name="edit_actions_a_model_names_no_person",
        ),
    )
    op.create_index("ix_edit_actions_feedback", "edit_actions", ["feedback_id"])
    op.create_index("ix_edit_actions_edge", "edit_actions", ["version_edge_id"])

    op.create_table(
        "response_links",
        sa.Column("response_link_id", sa.Text(), nullable=False),
        sa.Column(
            "feedback_id",
            sa.Text(),
            sa.ForeignKey("feedback_events.feedback_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "edit_action_id",
            sa.Text(),
            sa.ForeignKey("edit_actions.edit_action_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("grade", sa.String(32), nullable=False),
        sa.Column("decided_by", sa.String(32), nullable=True),
        sa.Column("decided_at", sa.String(), nullable=True),
        # What decided it. Empty only while the link is pending.
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("response_link_id", name="pk_response_links"),
        sa.CheckConstraint(
            "length(response_link_id) > 0 AND length(feedback_id) > 0 "
            "AND length(edit_action_id) > 0",
            name="response_links_ids_present",
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'addressed', 'partially_addressed', 'not_addressed')",
            name="response_links_state_vocabulary",
        ),
        sa.CheckConstraint(
            "grade IN ('observed', 'human_verified', 'inferred')",
            name="response_links_grade_vocabulary",
        ),
        sa.CheckConstraint(
            "decided_by IS NULL OR decided_by IN ('rule', 'user', 'model')",
            name="response_links_decided_by_vocabulary",
        ),
        # A pending link carries no decision.
        sa.CheckConstraint(
            "state <> 'pending' OR (decided_at IS NULL AND json_array_length(evidence_refs) = 0)",
            name="response_links_a_pending_link_carries_no_decision",
        ),
        # And a decided link names its decider and its evidence.
        sa.CheckConstraint(
            "state = 'pending' OR "
            "(decided_by IS NOT NULL AND decided_by IN ('rule', 'user') "
            "AND decided_at IS NOT NULL AND json_array_length(evidence_refs) > 0)",
            name="response_links_a_judgement_needs_a_decider_and_its_evidence",
        ),
        # A model's link is a candidate and never a decision. COALESCE
        # rather than a plain comparison: SQLite treats a constraint
        # expression that is NULL as satisfied.
        sa.CheckConstraint(
            "(COALESCE(decided_by, 'none') <> 'model' AND grade <> 'inferred') OR "
            "(COALESCE(decided_by, 'none') = 'model' AND grade = 'inferred')",
            name="response_links_an_inferred_link_is_a_models_candidate",
        ),
    )
    op.create_index("ix_response_links_feedback", "response_links", ["feedback_id"])
    op.create_index("ix_response_links_edit", "response_links", ["edit_action_id"])

    op.create_table(
        "followup_assessments",
        sa.Column("assessment_id", sa.Text(), nullable=False),
        sa.Column(
            "project_id",
            sa.Text(),
            sa.ForeignKey("paper_projects.project_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "feedback_id",
            sa.Text(),
            sa.ForeignKey("feedback_events.feedback_id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("issue_key", sa.String(200), nullable=True),
        sa.Column("assessment", sa.Text(), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        # What the assessment rests on. No member means "the change was
        # accepted".
        sa.Column("basis", sa.String(32), nullable=False),
        sa.Column("assessor_kind", sa.String(32), nullable=False),
        sa.Column("grade", sa.String(32), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("assessment_id", name="pk_followup_assessments"),
        sa.CheckConstraint(
            "length(assessment_id) > 0 AND length(project_id) > 0 AND length(assessment) > 0",
            name="followup_assessments_ids_present",
        ),
        sa.CheckConstraint(
            "outcome IN ('established', 'not_established', 'conflicted')",
            name="followup_assessments_outcome_vocabulary",
        ),
        sa.CheckConstraint(
            "basis IN ('advisor_evidence', 'revised_manuscript', "
            "'independent_check', 'human_attestation')",
            name="followup_assessments_basis_vocabulary",
        ),
        sa.CheckConstraint(
            "assessor_kind IN ('advisor', 'student', 'model', 'human', 'rule')",
            name="followup_assessments_assessor_kind_vocabulary",
        ),
        sa.CheckConstraint(
            "grade IN ('observed', 'inferred', 'human_verified')",
            name="followup_assessments_grade_vocabulary",
        ),
        # It names a feedback or an issue.
        sa.CheckConstraint(
            "feedback_id IS NOT NULL OR (issue_key IS NOT NULL AND length(issue_key) > 0)",
            name="followup_assessments_it_names_an_issue",
        ),
        # And it carries its own evidence.
        sa.CheckConstraint(
            "json_array_length(evidence_refs) > 0",
            name="followup_assessments_an_assessment_carries_its_evidence",
        ),
    )
    op.create_index("ix_followup_assessments_project", "followup_assessments", ["project_id"])
    op.create_index("ix_followup_assessments_feedback", "followup_assessments", ["feedback_id"])
    op.create_index("ix_followup_assessments_issue_key", "followup_assessments", ["issue_key"])


def downgrade() -> None:
    op.drop_index("ix_followup_assessments_issue_key", table_name="followup_assessments")
    op.drop_index("ix_followup_assessments_feedback", table_name="followup_assessments")
    op.drop_index("ix_followup_assessments_project", table_name="followup_assessments")
    op.drop_table("followup_assessments")
    op.drop_index("ix_response_links_edit", table_name="response_links")
    op.drop_index("ix_response_links_feedback", table_name="response_links")
    op.drop_table("response_links")
    op.drop_index("ix_edit_actions_edge", table_name="edit_actions")
    op.drop_index("ix_edit_actions_feedback", table_name="edit_actions")
    op.drop_table("edit_actions")
    op.drop_index("ix_feedback_events_issue_key", table_name="feedback_events")
    op.drop_index("ix_feedback_events_project", table_name="feedback_events")
    op.drop_index("ix_feedback_events_version", table_name="feedback_events")
    op.drop_table("feedback_events")
