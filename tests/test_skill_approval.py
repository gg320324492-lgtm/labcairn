"""The approval checkpoint, exercised directly rather than only through a run.

The orchestrator tests cover the end-to-end behaviour — a blocked run, a resumed
run. This file covers the gate's *rules*, because the gate is where the work
order's "required for important scientific direction and major goal or claim
changes" is actually decided, and a rule that is only tested through a run is a
rule whose edge cases are untested.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from pydantic import ValidationError
from test_skill_support import (
    SKILL_NOW,
    build_proposal,
    grant_approval,
    later_clock,
)

from labcairn.core.schema import LabCairnModel
from labcairn.skills import (
    ApprovalDecision,
    ApprovalGate,
    Materiality,
    ProposalItem,
    ResearchProposal,
    StaleApprovalError,
    artifact_digest,
    gate_request,
    require_approval,
)

pytestmark = pytest.mark.unit

UPSTREAM = ("a" * 64,)
TASK = "task-1"


def _proposal(**kwargs: object) -> ResearchProposal:
    return build_proposal(UPSTREAM, task_id=TASK, **kwargs)  # type: ignore[arg-type]


class TestWhenTheGateApplies:
    def test_a_routine_proposal_needs_no_approval(self) -> None:
        proposal = _proposal()
        digest = artifact_digest(proposal)
        verdict = ApprovalGate().evaluate(proposal, digest, None, now=SKILL_NOW)
        assert verdict.approved is True
        assert verdict.required is False
        assert verdict.awaiting_user is False

    @pytest.mark.parametrize(
        "materiality",
        [
            Materiality.IMPORTANT_SCIENTIFIC_DIRECTION,
            Materiality.MAJOR_GOAL_OR_CLAIM_CHANGE,
        ],
    )
    def test_either_significant_level_requires_approval(self, materiality: Materiality) -> None:
        proposal = _proposal(materiality=materiality)
        digest = artifact_digest(proposal)
        verdict = ApprovalGate().evaluate(proposal, digest, None, now=SKILL_NOW)
        assert verdict.required is True
        assert verdict.approved is False
        assert verdict.awaiting_user is True

    def test_a_goal_change_requires_approval_on_its_own(self) -> None:
        """Even with no significant items, changing the goal is significant."""
        proposal = _proposal(materiality=Materiality.ROUTINE, with_goal_change=True)
        digest = artifact_digest(proposal)
        verdict = ApprovalGate().evaluate(proposal, digest, None, now=SKILL_NOW)
        assert verdict.required is True
        assert verdict.approved is False

    def test_the_request_names_what_is_being_approved(self) -> None:
        proposal = _proposal(
            materiality=Materiality.IMPORTANT_SCIENTIFIC_DIRECTION, with_goal_change=True
        )
        request = gate_request(proposal)
        assert "p-1" in request
        assert "important_scientific_direction" in request
        assert "g-1" in request
        assert "success_criterion" in request

    def test_a_routine_proposal_produces_an_empty_request(self) -> None:
        assert gate_request(_proposal()) == ""


class TestWhatTheGateAccepts:
    def test_a_live_decision_covering_everything_is_accepted(self) -> None:
        proposal = _proposal(materiality=Materiality.IMPORTANT_SCIENTIFIC_DIRECTION)
        digest = artifact_digest(proposal)
        decision = grant_approval(proposal, digest, task_id=TASK)
        verdict = ApprovalGate().evaluate(proposal, digest, decision, now=SKILL_NOW)
        assert verdict.approved is True
        assert verdict.awaiting_user is False
        assert verdict.covered_items == ("p-1",)

    def test_the_window_is_half_open_at_the_start(self) -> None:
        proposal = _proposal(materiality=Materiality.IMPORTANT_SCIENTIFIC_DIRECTION)
        digest = artifact_digest(proposal)
        decision = grant_approval(proposal, digest, task_id=TASK)
        assert decision.is_live(decision.granted_at) is True
        assert decision.is_live(decision.granted_at - timedelta(microseconds=1)) is False

    def test_the_window_is_half_open_at_the_end(self) -> None:
        proposal = _proposal(materiality=Materiality.IMPORTANT_SCIENTIFIC_DIRECTION)
        digest = artifact_digest(proposal)
        decision = grant_approval(proposal, digest, task_id=TASK)
        assert decision.is_live(decision.expires_at) is False
        assert decision.is_live(decision.expires_at - timedelta(microseconds=1)) is True


class TestWhatTheGateRefuses:
    def _refuse(self, proposal: ResearchProposal, decision: ApprovalDecision | None) -> str:
        verdict = ApprovalGate().evaluate(
            proposal, artifact_digest(proposal), decision, now=SKILL_NOW
        )
        assert verdict.approved is False
        return verdict.reason

    def test_no_decision_at_all(self) -> None:
        reason = self._refuse(
            _proposal(materiality=Materiality.IMPORTANT_SCIENTIFIC_DIRECTION), None
        )
        assert "awaiting user approval" in reason

    def test_a_decision_for_a_different_proposal(self) -> None:
        proposal = _proposal(materiality=Materiality.IMPORTANT_SCIENTIFIC_DIRECTION)
        decision = grant_approval(proposal, "0" * 64, task_id=TASK)
        reason = self._refuse(proposal, decision)
        assert "the proposal now hashes to" in reason

    def test_an_expired_decision(self) -> None:
        proposal = _proposal(materiality=Materiality.IMPORTANT_SCIENTIFIC_DIRECTION)
        decision = grant_approval(
            proposal,
            artifact_digest(proposal),
            task_id=TASK,
            granted_at=SKILL_NOW - timedelta(hours=6),
            expires_at=SKILL_NOW - timedelta(hours=1),
        )
        assert "is not live" in self._refuse(proposal, decision)

    def test_a_decision_that_covers_some_items_but_not_all(self) -> None:
        proposal = _proposal(
            materiality=Materiality.IMPORTANT_SCIENTIFIC_DIRECTION,
        )
        decision = grant_approval(proposal, artifact_digest(proposal), task_id=TASK)
        decision = decision.model_copy(update={"covered_item_ids": ("p-elsewhere",)})
        assert "does not cover proposal item" in self._refuse(proposal, decision)

    def test_a_decision_that_ignores_a_goal_change(self) -> None:
        """A goal change is never covered by an item's id appearing in a list."""
        proposal = _proposal(with_goal_change=True)
        decision = grant_approval(
            proposal,
            artifact_digest(proposal),
            task_id=TASK,
            item_ids=("p-1",),
            goal_change_ids=(),
        )
        assert "does not cover goal change" in self._refuse(proposal, decision)

    def test_a_goal_change_arriving_after_the_decision_is_refused(self) -> None:
        """The digest binding is what catches this.

        The user approved a proposal; the run then produced a proposal that also
        changes the success criterion. The decision names the old digest, so it
        does not apply — which is the whole point of binding to the digest rather
        than to the item ids alone.
        """
        before = _proposal(materiality=Materiality.IMPORTANT_SCIENTIFIC_DIRECTION)
        decision = grant_approval(before, artifact_digest(before), task_id=TASK)
        after = _proposal(
            materiality=Materiality.IMPORTANT_SCIENTIFIC_DIRECTION, with_goal_change=True
        )
        assert artifact_digest(after) != artifact_digest(before)
        assert "the proposal now hashes to" in self._refuse(after, decision)

    def test_refusal_is_never_an_exception(self) -> None:
        """A missing approval is routine; raising would make it look like a crash."""
        proposal = _proposal(materiality=Materiality.MAJOR_GOAL_OR_CLAIM_CHANGE)
        verdict = ApprovalGate().evaluate(proposal, artifact_digest(proposal), None, now=SKILL_NOW)
        assert verdict.reason
        assert verdict.approved is False


class TestTheDirectEntryRefusal:
    def test_entering_the_guarded_stage_without_a_decision_raises(self) -> None:
        proposal = _proposal(materiality=Materiality.IMPORTANT_SCIENTIFIC_DIRECTION)
        with pytest.raises(StaleApprovalError, match="awaiting user approval"):
            require_approval(proposal, artifact_digest(proposal), None, now=SKILL_NOW)

    def test_entering_it_with_a_live_decision_returns_that_decision(self) -> None:
        proposal = _proposal(materiality=Materiality.IMPORTANT_SCIENTIFIC_DIRECTION)
        digest = artifact_digest(proposal)
        decision = grant_approval(proposal, digest, task_id=TASK)
        assert require_approval(proposal, digest, decision, now=SKILL_NOW) is decision

    def test_entering_it_with_a_stale_decision_raises(self) -> None:
        proposal = _proposal(materiality=Materiality.IMPORTANT_SCIENTIFIC_DIRECTION)
        decision = grant_approval(proposal, "0" * 64, task_id=TASK)
        with pytest.raises(StaleApprovalError, match="hashes to"):
            require_approval(proposal, artifact_digest(proposal), decision, now=SKILL_NOW)

    def test_a_routine_proposal_needs_no_decision_at_all(self) -> None:
        """A checkpoint that demanded an unneeded grant would be rubber-stamped."""
        proposal = _proposal()
        assert require_approval(proposal, artifact_digest(proposal), None, now=SKILL_NOW) is None


class TestDecisionInvariants:
    def test_a_window_that_ends_before_it_starts_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="not after granted_at"):
            ApprovalDecision(
                decision_id="d-1",
                task_id=TASK,
                approved_proposal_digest="a" * 64,
                covered_item_ids=("p-1",),
                granted_by="the researcher",
                granted_at=SKILL_NOW,
                expires_at=SKILL_NOW,
            )

    def test_a_decision_covering_nothing_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            ApprovalDecision(
                decision_id="d-1",
                task_id=TASK,
                approved_proposal_digest="a" * 64,
                covered_item_ids=(),
                granted_by="the researcher",
                granted_at=SKILL_NOW,
                expires_at=later_clock(),
            )

    def test_duplicate_coverage_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="duplicates"):
            ApprovalDecision(
                decision_id="d-1",
                task_id=TASK,
                approved_proposal_digest="a" * 64,
                covered_item_ids=("p-1", "p-1"),
                granted_by="the researcher",
                granted_at=SKILL_NOW,
                expires_at=later_clock(),
            )

    def test_a_decision_is_frozen(self) -> None:
        """An approval is a statement about a moment. Changing it means a new one."""
        proposal = _proposal(materiality=Materiality.IMPORTANT_SCIENTIFIC_DIRECTION)
        decision = grant_approval(proposal, artifact_digest(proposal), task_id=TASK)
        with pytest.raises(ValidationError, match="frozen"):
            decision.covered_item_ids = ("p-elsewhere",)


def test_a_gate_reads_only_its_arguments() -> None:
    """Stateless, so the same question asked twice gets the same answer."""
    gate = ApprovalGate()
    proposal = _proposal(materiality=Materiality.IMPORTANT_SCIENTIFIC_DIRECTION)
    digest = artifact_digest(proposal)
    first = gate.evaluate(proposal, digest, None, now=SKILL_NOW)
    second = gate.evaluate(proposal, digest, None, now=SKILL_NOW)
    assert first == second

    decision = grant_approval(proposal, digest, task_id=TASK)
    assert gate.evaluate(proposal, digest, decision, now=SKILL_NOW).approved is True
    # And the earlier answer is unchanged: consuming nothing, remembering nothing.
    assert gate.evaluate(proposal, digest, None, now=SKILL_NOW).approved is False


def test_materiality_is_set_by_the_stage_and_read_by_the_gate() -> None:
    """The gate enforces the rule; it does not decide which items are important.

    A gate that also judged significance could be tuned into agreeing with
    whatever the run wanted to do, which would make the checkpoint decorative.
    """
    proposal = ResearchProposal(
        task_id=TASK,
        direction="A direction chosen by the run, not by the gate.",
        items=(
            ProposalItem(
                item_id="p-1",
                statement="Abandon the located-quantity approach entirely.",
                materiality=Materiality.MAJOR_GOAL_OR_CLAIM_CHANGE,
                rationale="The reviewer objected to the framing of the result section.",
                evidence_refs=("c-1",),
            ),
        ),
        derived_from=UPSTREAM,
    )
    verdict = ApprovalGate().evaluate(proposal, artifact_digest(proposal), None, now=SKILL_NOW)
    assert verdict.required is True
    assert "p-1" in verdict.covered_items


def test_a_gate_constructed_twice_agrees() -> None:
    """No shared state to drift between, say, a CLI and a web surface."""
    proposal = _proposal(materiality=Materiality.IMPORTANT_SCIENTIFIC_DIRECTION)
    digest = artifact_digest(proposal)
    a = ApprovalGate().evaluate(proposal, digest, None, now=SKILL_NOW)
    b = ApprovalGate().evaluate(proposal, digest, None, now=SKILL_NOW)
    assert a.reason == b.reason


def test_the_gate_does_not_mutate_the_proposal_it_reads() -> None:
    proposal = _proposal(materiality=Materiality.IMPORTANT_SCIENTIFIC_DIRECTION)
    before = proposal.model_dump_json()
    ApprovalGate().evaluate(proposal, artifact_digest(proposal), None, now=SKILL_NOW)
    assert proposal.model_dump_json() == before


def test_the_artifact_models_stay_importable_from_one_place() -> None:
    """The gate's inputs are the same types the orchestrator records."""
    assert issubclass(ResearchProposal, LabCairnModel)
