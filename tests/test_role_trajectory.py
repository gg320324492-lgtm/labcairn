"""Role A: the trajectory's candidates, and the two rules that shape them.

**What is under test.** LC-P2-12 T01: ``roles.trajectory`` — the chain
read as facts, the versions ordered by the accepted edges, and the
candidate a role proposes about how a comment was answered.

====================================================  =========================
     a candidate is a judgement, never a fact            no locator field, no
                                                          words the advisor did
                                                          not write, and the
                                                          contract's version on
                                                          every output
     the order is the graph's                            a file name is not
                                                          evidence, a missing
                                                          round is not a present
                                                          one, and a fork the
                                                          accepted edges do not
                                                          settle is refused
     the read is the chain's facts                        the comments and the
                                                          edits, and nothing the
                                                          model said
====================================================  =========================
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import UTC, datetime
from pathlib import Path

import pytest
from feedback_chain_fixtures import ChainEnv, a_comment, build_chain
from test_store_support import StoreEnv
from test_store_support import env as _shared_env

from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import ApplicationRefusedError
from labcairn.db.models import EditActionRow, PaperVersionRow, VersionEdgeRow
from labcairn.papers.feedback import FeedbackEvent, record_feedback, set_issue_key
from labcairn.papers.labels import ISSUE_LABELS
from labcairn.roles.refusals import RoleRefusal
from labcairn.roles.spec import FORBIDDEN_ACTIONS, AgentRoleSpec, define_role_spec
from labcairn.roles.trajectory import (
    ALIGNMENT_STATES,
    TrajectoryCandidate,
    TrajectoryInput,
    order_versions,
    propose_candidate,
    read_trajectory,
)
from labcairn.security.capabilities import CapabilityId

pytestmark = pytest.mark.integration

env = _shared_env

MOMENT = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)

KEY = "iss-gold-a-r1"


@dataclass(frozen=True)
class Trajectory:
    """The context, the comment under its key, and the edit that answers it."""

    context: ApplicationContext
    chain: ChainEnv
    key: str
    event: FeedbackEvent
    edit_action_id: str
    spec: AgentRoleSpec


def _refusal(call: object) -> RoleRefusal:
    """The contract's refusal an expected error carries, so the test fails loudly."""
    assert isinstance(call, ApplicationRefusedError), f"expected a refusal, saw {call!r}"
    return RoleRefusal(call.reason.value.removeprefix("role_"))


@pytest.fixture()
def trajectory(env: StoreEnv, tmp_path: Path) -> Trajectory:
    """A chain with one keyed comment, its edit, and a graph with a fork in it.

    **The graph's order and its names disagree on purpose.** The versions
    are ``ver-1``, ``ver-2``, ``ver-10`` and ``ver-2b`` — every dictionary
    order of those names is wrong, and only the accepted edges know the
    order. ``ver-2b`` hangs a second accepted branch off ``ver-1``, so the
    accepted edges leave the pair ``ver-2``/``ver-2b`` in no order at all.
    """
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    store = env.store()
    chain = build_chain(store, workspace_root, comments=(a_comment("201"),))
    (event,) = record_feedback(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.version_id,
        now=MOMENT,
    )
    keyed = set_issue_key(chain.context, feedback_id=event.feedback_id, issue_key=KEY, now=MOMENT)
    session = chain.context.store.session
    edit_action_id = "edit-201"
    session.add(
        EditActionRow(
            edit_action_id=edit_action_id,
            feedback_id=event.feedback_id,
            version_edge_id=chain.edge_id,
            actor_kind="student",
            grade="observed",
            created_at=MOMENT,
        )
    )
    held_source = session.get(PaperVersionRow, chain.version_id)
    assert held_source is not None, "the fixture's first version is in the graph"
    source_id = held_source.source_id
    session.add(
        PaperVersionRow(
            version_id="ver-10",
            project_id=chain.project_id,
            source_id=source_id,
            version_label_raw="manuscript-10.docx",
            stage_candidate="draft",
            status="resolved",
            created_at=MOMENT,
        )
    )
    session.add(
        PaperVersionRow(
            version_id="ver-2b",
            project_id=chain.project_id,
            source_id=source_id,
            version_label_raw="manuscript-2b.docx",
            stage_candidate="draft",
            status="resolved",
            created_at=MOMENT,
        )
    )
    session.add(
        VersionEdgeRow(
            edge_id="edge-2",
            project_id=chain.project_id,
            parent_version_id="ver-2",
            child_version_id="ver-10",
            source="human",
            confidence=1.0,
            evidence_spans=[],
            accepted_by="Dr. Chen",
            accepted_at=MOMENT,
            edge_version=1,
            superseded_by=None,
            created_at=MOMENT,
        )
    )
    session.add(
        VersionEdgeRow(
            edge_id="edge-branch",
            project_id=chain.project_id,
            parent_version_id="ver-1",
            child_version_id="ver-2b",
            source="human",
            confidence=1.0,
            evidence_spans=[],
            accepted_by="Dr. Chen",
            accepted_at=MOMENT,
            edge_version=1,
            superseded_by=None,
            created_at=MOMENT,
        )
    )
    session.flush()
    spec = define_role_spec(
        chain.context,
        role_id="trajectory",
        role_version=1,
        objective="Align the advisor's comments with the edits actually made.",
        input_schema="TrajectoryInput",
        output_schema="TrajectoryCandidate",
        allowed_capabilities=(CapabilityId.SOURCE_READ,),
        forbidden_actions=FORBIDDEN_ACTIONS,
        allowed_data_purposes=("guidance_review",),
        provider_routing_policy="none",
        cost_budget=None,
        token_budget=1,
        timeout_seconds=60,
        retry_policy="no-retry",
        fallback_policy="abstain",
        abstain_conditions=("material_under_two_comments",),
        escalation_conditions=("a_fork_in_the_graph",),
        prompt_template_version="trajectory-v1",
        model_config_ref="configs/model.json",
        now=MOMENT,
    )
    return Trajectory(
        context=chain.context,
        chain=chain,
        key=KEY,
        event=keyed,
        edit_action_id=edit_action_id,
        spec=spec,
    )


def test_role_a_proposes_judgements_and_never_facts(trajectory: Trajectory) -> None:
    """A candidate points at a comment, quotes it verbatim, and wears its contract.

    **The type has no locator field** — the pretending is not a mistake a
    caller can make, it is a shape the vocabulary does not have — and a
    quote that is not the comment's words is refused by name.
    """
    assert "comment_locator" not in {field.name for field in fields(TrajectoryCandidate)}
    quote = trajectory.event.comment_text[:24]
    candidate = propose_candidate(
        trajectory.context,
        spec=trajectory.spec,
        issue_key=trajectory.key,
        issue_type="method_and_hypothesis",
        alignment="partial",
        advisor_quote=quote,
        note="the change addresses the wording, not the missing interval.",
        edit_action_id=trajectory.edit_action_id,
    )
    assert (candidate.role_id, candidate.role_version) == ("trajectory", 1)
    assert candidate.advisor_quote in trajectory.event.comment_text
    assert candidate.alignment in ALIGNMENT_STATES
    assert candidate.issue_type in ISSUE_LABELS

    refused = _refusal(
        _capture(
            lambda: propose_candidate(
                trajectory.context,
                spec=trajectory.spec,
                issue_key=trajectory.key,
                issue_type="method_and_hypothesis",
                alignment="partial",
                advisor_quote=quote + " — and the advisor said more than that",
                note="a paraphrase offered as a quotation",
                edit_action_id=trajectory.edit_action_id,
            )
        )
    )
    assert refused is RoleRefusal.QUOTE_NOT_IN_THE_CHAIN
    refused = _refusal(
        _capture(
            lambda: propose_candidate(
                trajectory.context,
                spec=trajectory.spec,
                issue_key="iss-nowhere",
                issue_type="method_and_hypothesis",
                alignment="partial",
                advisor_quote=quote,
                note="a judgement about a comment that is not there",
            )
        )
    )
    assert refused is RoleRefusal.COMMENT_NOT_IN_THE_CHAIN
    refused = _refusal(
        _capture(
            lambda: propose_candidate(
                trajectory.context,
                spec=trajectory.spec,
                issue_key=trajectory.key,
                issue_type="method_and_hypothesis",
                alignment="maybe",
                advisor_quote=quote,
                note="a fifth state is not one the vocabulary closes",
            )
        )
    )
    assert refused is RoleRefusal.ALIGNMENT_STATE_UNKNOWN
    refused = _refusal(
        _capture(
            lambda: propose_candidate(
                trajectory.context,
                spec=trajectory.spec,
                issue_key=trajectory.key,
                issue_type="mood",
                alignment="partial",
                advisor_quote=quote,
                note="a problem outside the closed vocabulary",
            )
        )
    )
    assert refused is RoleRefusal.CANDIDATE_ISSUE_TYPE_UNKNOWN
    refused = _refusal(
        _capture(
            lambda: propose_candidate(
                trajectory.context,
                spec=trajectory.spec,
                issue_key=trajectory.key,
                issue_type="method_and_hypothesis",
                alignment="partial",
                advisor_quote=quote,
                note="an edit that answers nothing is an alignment to nothing",
                edit_action_id="edit-elsewhere",
            )
        )
    )
    assert refused is RoleRefusal.EDIT_DOES_NOT_ANSWER_THE_COMMENT


def test_role_a_does_not_order_versions_by_name_or_invent_a_round(
    trajectory: Trajectory,
) -> None:
    """The order is the accepted edges', or there is no order.

    **Every dictionary order of the names is wrong here** — the ids sort
    ``ver-1, ver-10, ver-2, ver-2b`` and the file names sort the same way
    — so a returned order that matches a dictionary order is a returned
    order the file names supplied.
    """
    ordered = order_versions(
        trajectory.context,
        project_id=trajectory.chain.project_id,
        version_ids=("ver-1", "ver-2", "ver-10"),
    )
    assert ordered == ("ver-1", "ver-2", "ver-10"), (
        "the accepted edges know the order; the names do not"
    )
    assert ordered != tuple(sorted(ordered)), "that order is the dictionary's"

    refused = _refusal(
        _capture(
            lambda: order_versions(
                trajectory.context,
                project_id=trajectory.chain.project_id,
                version_ids=("ver-1", "ver-99"),
            )
        )
    )
    assert refused is RoleRefusal.VERSION_OUTSIDE_THE_GRAPH

    refused = _refusal(
        _capture(
            lambda: order_versions(
                trajectory.context,
                project_id=trajectory.chain.project_id,
                version_ids=("ver-1", "ver-2", "ver-2b"),
            )
        )
    )
    assert refused is RoleRefusal.VERSION_ORDER_AMBIGUOUS


def test_the_trajectory_read_is_the_chain_s_facts(trajectory: Trajectory) -> None:
    """What the role reads is what the chain holds, in the graph's order."""
    material = read_trajectory(
        trajectory.context,
        trajectory_input=TrajectoryInput(
            project_id=trajectory.chain.project_id,
            version_ids=("ver-1", "ver-2"),
            issue_keys=(trajectory.key,),
        ),
    )
    assert material.ordered_version_ids == ("ver-1", "ver-2")
    assert [comment.issue_key for comment in material.comments] == [trajectory.key]
    assert material.comments[0].comment_text == trajectory.event.comment_text
    assert trajectory.edit_action_id in {edit.edit_action_id for edit in material.edits}
    refused = _refusal(
        _capture(
            lambda: read_trajectory(
                trajectory.context,
                trajectory_input=TrajectoryInput(
                    project_id=trajectory.chain.project_id,
                    version_ids=("ver-1", "ver-2"),
                    issue_keys=("iss-nowhere",),
                ),
            )
        )
    )
    assert refused is RoleRefusal.COMMENT_NOT_IN_THE_CHAIN


def _capture(call: object) -> ApplicationRefusedError:
    """The refusal a call that must raise carries."""
    assert callable(call)
    try:
        call()
    except ApplicationRefusedError as refused:
        return refused
    raise AssertionError("the call was expected to refuse, and it did not")
