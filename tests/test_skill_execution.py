"""The acceptance rules, end to end, plus the mutation cases they exist to catch.

Every test drives the real :class:`~labcairn.skills.execution.Orchestrator`
through the real declaration. The misbehaving handlers are written to be as
plausible as the failure modes are common: a stage that ignores its inputs, a
stage that returns a shell, a stage that returns the same thing forever, a stage
that tries to route around the approval checkpoint.

Organised as one class per acceptance rule, so a reader can find the test for
the clause they care about without reading the rest.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from test_skill_support import (
    FOREIGN_SHA,
    PAPER_SHA,
    build_inventory,
    build_proposal,
    build_retrieved,
    grant_approval,
    make_anchor,
    make_objective,
    make_orchestrator,
)

from labcairn.core.schema import LabCairnModel
from labcairn.evidence.states import VerificationStatus
from labcairn.skills import (
    RESEARCH_REPORT,
    AnchorRef,
    ApprovalDecision,
    ApprovalRequiredError,
    ArtifactKind,
    ArtifactSubstitutedError,
    ArtifactTypeError,
    DraftSection,
    EvidenceClaim,
    EvidenceLedgerView,
    Materiality,
    ProposalItem,
    ReportDraft,
    ResearchObjective,
    ResearchProposal,
    RetrievedExcerpts,
    RunControl,
    SkillBudgetError,
    SourceInventory,
    StageBlockedError,
    StageBudget,
    StageContext,
    StageFailedError,
    StageName,
    WorkflowStop,
    build_plan,
    require_approval,
    research_report_skill,
)

pytestmark = pytest.mark.unit


def _objective_for(orchestrator: object) -> ResearchObjective:
    return make_objective(str(orchestrator.task_id))  # type: ignore[attr-defined]


# ===========================================================================
# The happy path, because a guard set that rejects everything proves nothing
# ===========================================================================


class TestACorrectRunCompletes:
    def test_every_stage_produces_a_verified_artifact(self) -> None:
        orchestrator = make_orchestrator()
        outcome = orchestrator.run(_objective_for(orchestrator))
        assert outcome.stop is WorkflowStop.COMPLETED
        assert tuple(stage.value for stage in outcome.completed_stages) == (
            "intake",
            "inventory",
            "retrieve",
            "evidence",
            "propose",
            "draft",
            "validate",
            "deliver",
        )

    def test_every_stage_left_a_checkpoint(self) -> None:
        orchestrator = make_orchestrator()
        outcome = orchestrator.run(_objective_for(orchestrator))
        assert [cp.stage for cp in outcome.checkpoints] == list(StageName)
        assert all(cp.status.value == "completed" for cp in outcome.checkpoints)

    def test_each_checkpoint_names_its_own_inputs_and_outputs(self) -> None:
        orchestrator = make_orchestrator()
        outcome = orchestrator.run(_objective_for(orchestrator))
        by_stage = {cp.stage: cp for cp in outcome.checkpoints}
        assert by_stage[StageName.INTAKE].input_digests == ()
        assert (
            by_stage[StageName.INVENTORY].input_digests == by_stage[StageName.INTAKE].output_digests
        )
        assert by_stage[StageName.DRAFT].input_digests == (
            by_stage[StageName.PROPOSE].output_digests[0],
            by_stage[StageName.EVIDENCE].output_digests[0],
        )

    def test_a_runtime_stage_row_exists_for_each_stage(self) -> None:
        """Emitted so LC-P1-05's repository has something to persist."""
        orchestrator = make_orchestrator()
        outcome = orchestrator.run(_objective_for(orchestrator))
        assert {stage.name for stage in outcome.stages} == {s.value for s in StageName}
        assert all(stage.status.value == "completed" for stage in outcome.stages)

    def test_the_delivery_names_the_draft_this_run_produced(self) -> None:
        orchestrator = make_orchestrator()
        orchestrator.run(_objective_for(orchestrator))
        delivery = orchestrator.ledger.load(StageName.DELIVER, ArtifactKind.DELIVERED_REPORT)
        draft = orchestrator.ledger.load(StageName.DRAFT, ArtifactKind.REPORT_DRAFT)
        assert delivery.artifact.draft_digest == draft.digest  # type: ignore[attr-defined]

    def test_rerunning_a_finished_run_is_a_no_op(self) -> None:
        """Re-entrant: nothing is re-run and nothing is lost."""
        orchestrator = make_orchestrator()
        first = orchestrator.run(_objective_for(orchestrator))
        second = orchestrator.run(_objective_for(orchestrator))
        assert second.executions == first.executions == 7
        assert second.completed_stages == first.completed_stages


# ===========================================================================
# Acceptance 1: every stage consumes *actual* previous artifacts
# ===========================================================================


class TestForgedUpstreamArtifactsAreRefused:
    """The check that must not be ``input is not None``.

    Each test below installs a forged upstream artifact that is schema-valid,
    non-empty and internally consistent. None of them is ``None``. If any passes,
    the orchestrator is checking the wrong thing.
    """

    def test_a_stage_that_ignores_its_inputs_is_refused(self) -> None:
        """Returns a perfect artifact naming digests it was never handed."""

        def ignoring_inventory(context: StageContext) -> LabCairnModel:
            return build_inventory(("f" * 64,), task_id=context.task_id)

        orchestrator = make_orchestrator({StageName.INVENTORY: ignoring_inventory})
        outcome = orchestrator.run(_objective_for(orchestrator))
        assert outcome.stop is WorkflowStop.FAILED
        assert outcome.stopped_at is StageName.INVENTORY
        assert "first refusal" in outcome.reason
        assert "derived_from is" in outcome.reason
        assert "did not read them" in outcome.reason

    def test_a_stage_that_names_a_partial_lineage_is_refused(self) -> None:
        """Right digest for one input, missing the other.

        ``evidence`` takes ``retrieve`` *and* ``inventory``; naming only one is
        still not naming what it was handed.
        """

        def partial_evidence(context: StageContext) -> LabCairnModel:
            ledger = context.inputs[ArtifactKind.RETRIEVED_EXCERPTS]
            assert isinstance(ledger, RetrievedExcerpts)
            return EvidenceLedgerView(
                task_id=context.task_id,
                claims=(
                    EvidenceClaim(
                        claim_id="c-1",
                        statement="A claim that names only one of its two declared inputs.",
                        anchor_refs=(AnchorRef(anchor_id="a-1", material_sha256=PAPER_SHA),),
                        status=VerificationStatus.EXTRACTED,
                    ),
                ),
                derived_from=(context.upstream.digests()[0],),
            )

        orchestrator = make_orchestrator({StageName.EVIDENCE: partial_evidence})
        outcome = orchestrator.run(_objective_for(orchestrator))
        assert outcome.stop is WorkflowStop.FAILED
        assert outcome.stopped_at is StageName.EVIDENCE
        assert "derived_from is" in outcome.reason

    def test_a_forged_inventory_the_task_was_never_bound_to_is_refused(self) -> None:
        """Right lineage, materials that intake never declared.

        This is the forgery a digest comparison alone cannot catch, which is why
        the closure rules exist alongside it.
        """

        def fabricating_inventory(context: StageContext) -> LabCairnModel:
            return build_inventory(
                context.upstream.digests(),
                task_id=context.task_id,
                materials=(("something-else.pdf", FOREIGN_SHA, True),),
                anchors=(make_anchor("a-fabricated", FOREIGN_SHA),),
            )

        orchestrator = make_orchestrator({StageName.INVENTORY: fabricating_inventory})
        outcome = orchestrator.run(_objective_for(orchestrator))
        assert outcome.stop is WorkflowStop.FAILED
        assert outcome.stopped_at is StageName.INVENTORY
        assert "not inventoried" in outcome.reason
        assert "inventoried but never bound" in outcome.reason

    def test_a_stage_returning_the_wrong_model_is_refused(self) -> None:
        def confused_evidence(context: StageContext) -> LabCairnModel:
            return build_retrieved(context.upstream.digests(), task_id=context.task_id)

        orchestrator = make_orchestrator({StageName.EVIDENCE: confused_evidence})
        outcome = orchestrator.run(_objective_for(orchestrator))
        assert outcome.stop is WorkflowStop.FAILED
        assert "declares EvidenceLedgerView" in outcome.reason

    def test_an_unverifiable_payload_is_refused_with_the_validation_error(self) -> None:
        def malformed_evidence(context: StageContext) -> LabCairnModel:
            return EvidenceLedgerView.model_construct(
                task_id=context.task_id,
                claims=(),
                derived_from=context.upstream.digests(),
            )

        orchestrator = make_orchestrator({StageName.EVIDENCE: malformed_evidence})
        outcome = orchestrator.run(_objective_for(orchestrator))
        assert outcome.stop is WorkflowStop.FAILED
        assert outcome.stopped_at is StageName.EVIDENCE

    def test_a_substituted_upstream_artifact_is_caught_when_the_next_stage_reads_it(
        self,
    ) -> None:
        """The read-time guard, reached through the orchestrator rather than directly."""
        import dataclasses

        orchestrator = make_orchestrator()
        seen: list[str] = []

        def peeking_evidence(context: StageContext) -> LabCairnModel:
            seen.append("reached evidence")
            from test_skill_support import evidence_handler

            return evidence_handler(context)

        orchestrator.handlers[StageName.EVIDENCE] = peeking_evidence
        # Park the run at ``retrieve`` so the swap happens before ``evidence`` runs.
        objective = _objective_for(orchestrator)

        def blocking_validate(context: StageContext) -> LabCairnModel:
            raise StageBlockedError("park here so the ledger can be inspected")

        orchestrator.handlers[StageName.VALIDATE] = blocking_validate
        outcome = orchestrator.run(objective)
        assert outcome.stop is WorkflowStop.BLOCKED
        assert seen == ["reached evidence"]

        # Swap the retrieve output the way an attacker with ledger access would.
        recorded = orchestrator.ledger.by_stage[StageName.RETRIEVE]
        orchestrator.ledger.by_stage[StageName.RETRIEVE] = dataclasses.replace(
            recorded, artifact=build_retrieved(("9" * 64,))
        )
        with pytest.raises(ArtifactSubstitutedError, match="substituted after"):
            orchestrator.ledger.digests((StageName.RETRIEVE,))

    def test_an_orchestrator_never_takes_an_input_from_its_caller(self) -> None:
        """Structural: ``run`` takes an objective and a decision, nothing else.

        Asserted by signature so a future parameter that smuggles an artifact in
        cannot be added without this test failing.
        """
        import inspect

        from labcairn.skills import Orchestrator

        parameters = set(inspect.signature(Orchestrator.run).parameters)
        assert parameters == {"self", "objective", "decision", "control"}


# ===========================================================================
# Acceptance 2: no empty placeholder passes
# ===========================================================================


class TestPlaceholderOutputIsRefused:
    def test_a_stage_returning_a_placeholder_shell_is_refused_and_retried(self) -> None:
        """Every field right, nothing said."""
        attempts: list[int] = []

        def shell_draft(context: StageContext) -> LabCairnModel:
            attempts.append(context.attempt)
            return ReportDraft(
                task_id=context.task_id,
                sections=(
                    DraftSection(
                        section_id="s-1",
                        heading="TODO",
                        body="TBD",
                        evidence_refs=("c-1",),
                    ),
                ),
                derived_from=context.upstream.digests(),
            )

        orchestrator = make_orchestrator({StageName.DRAFT: shell_draft})
        outcome = orchestrator.run(_objective_for(orchestrator))
        assert outcome.stop is WorkflowStop.FAILED
        assert outcome.stopped_at is StageName.DRAFT
        assert "placeholder marker" in outcome.reason
        # Refused on every attempt rather than accepted on the second.
        assert attempts == [1, 2, 3]

    def test_a_draft_citing_claims_nobody_produced_is_refused(self) -> None:
        """Fluent, well-cited, entirely fictitious. The real placeholder."""

        def fabricated_draft(context: StageContext) -> LabCairnModel:
            return ReportDraft(
                task_id=context.task_id,
                sections=(
                    DraftSection(
                        section_id="s-1",
                        heading="Conclusion",
                        body=(
                            "The catalyst strongly and consistently suppresses the yield "
                            "across every loading examined in this study."
                        ),
                        evidence_refs=("c-invented", "c-also-invented"),
                    ),
                ),
                derived_from=context.upstream.digests(),
            )

        orchestrator = make_orchestrator({StageName.DRAFT: fabricated_draft})
        outcome = orchestrator.run(_objective_for(orchestrator))
        assert outcome.stop is WorkflowStop.FAILED
        assert "no earlier stage produced" in outcome.reason

    def test_a_proposal_item_with_no_substance_is_refused(self) -> None:
        def thin_proposal(context: StageContext) -> LabCairnModel:
            return ResearchProposal(
                task_id=context.task_id,
                direction="TODO",
                items=(
                    ProposalItem(
                        item_id="p-1",
                        statement="n/a",
                        materiality=Materiality.ROUTINE,
                        rationale="TBD",
                        evidence_refs=("c-1",),
                    ),
                ),
                derived_from=context.upstream.digests(),
            )

        orchestrator = make_orchestrator({StageName.PROPOSE: thin_proposal})
        outcome = orchestrator.run(_objective_for(orchestrator))
        assert outcome.stop is WorkflowStop.FAILED
        assert outcome.stopped_at is StageName.PROPOSE
        assert "placeholder marker" in outcome.reason

    def test_a_stage_that_returns_nothing_useful_is_refused(self) -> None:
        def refuses(context: StageContext) -> LabCairnModel:
            raise StageFailedError("the ingestion backend returned nothing to index")

        orchestrator = make_orchestrator({StageName.INVENTORY: refuses})
        outcome = orchestrator.run(_objective_for(orchestrator))
        assert outcome.stop is WorkflowStop.FAILED
        assert "the ingestion backend returned nothing" in outcome.reason

    def test_an_unexpected_exception_propagates_rather_than_retrying(self) -> None:
        """A bug is a bug report, not a retry. Silently retrying hides it."""

        def buggy(context: StageContext) -> LabCairnModel:
            raise ZeroDivisionError("a defect in this stage body")

        orchestrator = make_orchestrator({StageName.INVENTORY: buggy})
        with pytest.raises(ZeroDivisionError):
            orchestrator.run(_objective_for(orchestrator))


# ===========================================================================
# Acceptance 3: a blocked user decision awaits approval
# ===========================================================================


def _significant_propose(context: StageContext) -> LabCairnModel:
    return build_proposal(
        context.upstream.digests(),
        task_id=context.task_id,
        materiality=Materiality.IMPORTANT_SCIENTIFIC_DIRECTION,
    )


def _goal_changing_propose(context: StageContext) -> LabCairnModel:
    return build_proposal(
        context.upstream.digests(),
        task_id=context.task_id,
        with_goal_change=True,
    )


class TestApprovalCheckpoint:
    def test_a_routine_proposal_needs_no_approval(self) -> None:
        orchestrator = make_orchestrator()
        outcome = orchestrator.run(_objective_for(orchestrator))
        assert outcome.stop is WorkflowStop.COMPLETED
        assert outcome.gate_verdict is None or outcome.gate_verdict.required is False

    def test_an_important_scientific_direction_parks_the_run_at_draft(self) -> None:
        orchestrator = make_orchestrator({StageName.PROPOSE: _significant_propose})
        outcome = orchestrator.run(_objective_for(orchestrator))
        assert outcome.stop is WorkflowStop.BLOCKED
        assert outcome.stopped_at is StageName.DRAFT
        assert outcome.awaiting_approval is True
        assert StageName.DRAFT not in outcome.completed_stages

    def test_a_major_goal_change_parks_the_run(self) -> None:
        orchestrator = make_orchestrator({StageName.PROPOSE: _goal_changing_propose})
        outcome = orchestrator.run(_objective_for(orchestrator))
        assert outcome.stop is WorkflowStop.BLOCKED
        assert "goal change" in outcome.reason

    def test_the_run_resumes_from_draft_once_the_decision_arrives(self) -> None:
        orchestrator = make_orchestrator({StageName.PROPOSE: _significant_propose})
        objective = _objective_for(orchestrator)
        blocked = orchestrator.run(objective)
        assert blocked.stop is WorkflowStop.BLOCKED

        proposal_entry = orchestrator.ledger.load(StageName.PROPOSE, ArtifactKind.RESEARCH_PROPOSAL)
        decision = grant_approval(
            proposal_entry.artifact,  # type: ignore[arg-type]
            proposal_entry.digest,
            task_id=str(orchestrator.task_id),
        )
        resumed = orchestrator.run(objective, decision=decision)
        assert resumed.stop is WorkflowStop.COMPLETED
        assert StageName.DRAFT in resumed.completed_stages

    def test_a_direct_attempt_to_enter_the_guarded_stage_is_refused(self) -> None:
        """Bypassing the orchestrator is refused by name, not merely discouraged."""
        orchestrator = make_orchestrator({StageName.PROPOSE: _significant_propose})
        orchestrator.run(_objective_for(orchestrator))
        entry = orchestrator.ledger.load(StageName.PROPOSE, ArtifactKind.RESEARCH_PROPOSAL)
        with pytest.raises(ApprovalRequiredError, match="awaiting user approval"):
            require_approval(
                entry.artifact,  # type: ignore[arg-type]
                entry.digest,
                None,
                now=orchestrator.clock(),
            )

    def test_an_approval_for_a_different_proposal_digest_is_refused(self) -> None:
        orchestrator = make_orchestrator({StageName.PROPOSE: _significant_propose})
        orchestrator.run(_objective_for(orchestrator))
        entry = orchestrator.ledger.load(StageName.PROPOSE, ArtifactKind.RESEARCH_PROPOSAL)
        stale = grant_approval(
            entry.artifact,  # type: ignore[arg-type]
            "e" * 64,  # a digest the proposal never had
            task_id=str(orchestrator.task_id),
        )
        outcome = orchestrator.run(_objective_for(orchestrator), decision=stale)
        assert outcome.stop is WorkflowStop.BLOCKED
        assert "the proposal now hashes to" in outcome.reason

    def test_an_expired_approval_is_refused(self) -> None:
        orchestrator = make_orchestrator({StageName.PROPOSE: _significant_propose})
        objective = _objective_for(orchestrator)
        orchestrator.run(objective)
        entry = orchestrator.ledger.load(StageName.PROPOSE, ArtifactKind.RESEARCH_PROPOSAL)
        expired = ApprovalDecision(
            decision_id="d-old",
            task_id=str(orchestrator.task_id),
            approved_proposal_digest=entry.digest,
            covered_item_ids=("p-1",),
            granted_by="the researcher",
            granted_at=orchestrator.clock() - timedelta(hours=6),
            expires_at=orchestrator.clock() - timedelta(hours=1),
        )
        outcome = orchestrator.run(objective, decision=expired)
        assert outcome.stop is WorkflowStop.BLOCKED
        assert "is not live" in outcome.reason

    def test_an_approval_covering_only_part_of_the_direction_is_refused(self) -> None:
        orchestrator = make_orchestrator({StageName.PROPOSE: _significant_propose})
        objective = _objective_for(orchestrator)
        orchestrator.run(objective)
        entry = orchestrator.ledger.load(StageName.PROPOSE, ArtifactKind.RESEARCH_PROPOSAL)
        partial = grant_approval(
            entry.artifact,  # type: ignore[arg-type]
            entry.digest,
            task_id=str(orchestrator.task_id),
            item_ids=("p-some-other-item",),
        )
        outcome = orchestrator.run(objective, decision=partial)
        assert outcome.stop is WorkflowStop.BLOCKED
        assert "does not cover proposal item" in outcome.reason

    def test_a_blocked_stage_leaves_a_checkpoint_naming_what_it_is_waiting_for(self) -> None:
        orchestrator = make_orchestrator({StageName.PROPOSE: _significant_propose})
        outcome = orchestrator.run(_objective_for(orchestrator))
        final = outcome.checkpoints[-1]
        assert final.stage is StageName.DRAFT
        assert final.status.value == "blocked"
        assert final.blocked_reason is not None
        assert "awaiting user approval" in final.blocked_reason

    def test_the_runtime_stage_row_also_carries_the_block_reason(self) -> None:
        orchestrator = make_orchestrator({StageName.PROPOSE: _significant_propose})
        outcome = orchestrator.run(_objective_for(orchestrator))
        draft_row = next(stage for stage in outcome.stages if stage.name == "draft")
        assert draft_row.status.value == "blocked"
        assert draft_row.blocked_reason is not None


# ===========================================================================
# Acceptance 4: limited retries on no progress
# ===========================================================================


def _stuck_stage(context: StageContext) -> LabCairnModel:
    """Returns the identical defective artifact on every attempt.

    Type-correct and non-empty, with a lineage it was never handed. Every attempt
    therefore fails for the same reason, which is the situation "limited retries
    on no progress" exists for.
    """
    return build_inventory(("f" * 64,), task_id=context.task_id)


class TestBoundedRetries:
    def test_a_stage_that_never_varies_is_failed_after_exactly_the_declared_attempts(
        self,
    ) -> None:
        attempts: list[int] = []

        def counting(context: StageContext) -> LabCairnModel:
            attempts.append(context.attempt)
            return _stuck_stage(context)

        orchestrator = make_orchestrator(
            {StageName.INVENTORY: counting},
            declaration=research_report_skill(StageBudget(max_attempts_per_stage=3)),
        )
        outcome = orchestrator.run(_objective_for(orchestrator))
        assert outcome.stop is WorkflowStop.FAILED
        assert outcome.stopped_at is StageName.INVENTORY
        assert attempts == [1, 2, 3]
        assert outcome.attempts_used[StageName.INVENTORY] == 3
        assert "made no progress in 3 attempt(s)" in outcome.reason

    def test_the_reason_names_the_byte_identical_repetition(self) -> None:
        """Not just "it kept failing" — *why* it kept failing is in the record."""
        orchestrator = make_orchestrator({StageName.INVENTORY: _stuck_stage})
        outcome = orchestrator.run(_objective_for(orchestrator))
        assert "first refusal" in outcome.reason
        assert "the following 2 attempt(s) returned byte-identical output" in outcome.reason

    def test_the_whole_run_cap_bounds_a_run_that_has_already_spent_its_allowance(
        self,
    ) -> None:
        """The backstop, in the situation where it is actually reachable.

        A declaration is refused if the run cap is below the per-stage cap, so the
        backstop is **not** reachable while a run is pristine. It is reachable once
        earlier stages have spent most of the allowance: here ``inventory`` burns
        three of the run's six executions flailing before it finally lands, and
        ``retrieve`` — stuck from the start — is cut off by the run cap after
        three attempts instead of receiving its own five. Without the cap, a stage
        stuck late in a run is still allowed the full per-stage allowance, so a
        defect in the retry predicate is paid for once per remaining stage.
        """
        executions: list[str] = []

        def wasteful_inventory(context: StageContext) -> LabCairnModel:
            executions.append(context.stage.value)
            if context.attempt < 3:
                return build_inventory(("f" * 64,), task_id=context.task_id)
            return build_inventory(context.upstream.digests(), task_id=context.task_id)

        def stuck_retrieve(context: StageContext) -> LabCairnModel:
            executions.append(context.stage.value)
            from test_skill_support import retrieve_handler

            return retrieve_handler(context).model_copy(update={"derived_from": ("f" * 64,)})

        orchestrator = make_orchestrator(
            {
                StageName.INVENTORY: wasteful_inventory,
                StageName.RETRIEVE: stuck_retrieve,
            },
            declaration=research_report_skill(
                StageBudget(max_attempts_per_stage=5, max_total_executions=6)
            ),
        )
        with pytest.raises(SkillBudgetError, match="run budget exhausted"):
            orchestrator.run(_objective_for(orchestrator))
        # It really did reach retrieve, and was cut off by the *run* cap rather
        # than by its own five-attempt budget.
        assert executions[-1] == "retrieve"
        assert executions.count("retrieve") < 5

    def test_a_budget_whose_run_cap_is_below_its_stage_cap_is_refused(self) -> None:
        from labcairn.skills import StageBudget

        with pytest.raises(ValueError, match="below"):
            StageBudget(max_attempts_per_stage=5, max_total_executions=2)

    def test_a_stage_that_recovers_on_its_second_attempt_succeeds(self) -> None:
        """The retry budget is not a "fail once, give up" rule."""
        attempts: list[int] = []

        def flaky(context: StageContext) -> LabCairnModel:
            attempts.append(context.attempt)
            if context.attempt == 1:
                return build_inventory(  # wrong lineage on the first try
                    ("0" * 64,), task_id=context.task_id
                )
            return build_inventory(context.upstream.digests(), task_id=context.task_id)

        orchestrator = make_orchestrator({StageName.INVENTORY: flaky})
        outcome = orchestrator.run(_objective_for(orchestrator))
        assert outcome.stop is WorkflowStop.COMPLETED
        assert attempts == [1, 2]

    def test_a_handler_that_blocks_is_not_retried(self) -> None:
        """Retrying would spend the budget re-asking a question only a person can answer."""
        attempts: list[int] = []

        def blocking(context: StageContext) -> LabCairnModel:
            attempts.append(context.attempt)
            raise StageBlockedError("which corpus should the search cover")

        orchestrator = make_orchestrator({StageName.INVENTORY: blocking})
        outcome = orchestrator.run(_objective_for(orchestrator))
        assert outcome.stop is WorkflowStop.BLOCKED
        assert attempts == [1]


# ===========================================================================
# Acceptance 5: user cancels without losing previous valid work
# ===========================================================================


class TestCancellationPreservesVerifiedWork:
    def test_cancelling_before_a_stage_leaves_every_earlier_artifact_intact(self) -> None:
        control = RunControl()
        reached: list[str] = []

        def stop_after_propose(context: StageContext) -> LabCairnModel:
            reached.append(context.stage.value)
            control.cancel()
            from test_skill_support import propose_handler

            return propose_handler(context)

        orchestrator = make_orchestrator({StageName.PROPOSE: stop_after_propose})
        outcome = orchestrator.run(_objective_for(orchestrator), control=control)
        assert outcome.stop is WorkflowStop.CANCELLED
        assert outcome.stopped_at is StageName.DRAFT
        assert reached[-1] == "propose"

    def test_every_verified_artifact_survives_a_cancellation(self) -> None:
        control = RunControl()

        def stop_after_propose(context: StageContext) -> LabCairnModel:
            control.cancel()
            from test_skill_support import propose_handler

            return propose_handler(context)

        orchestrator = make_orchestrator({StageName.PROPOSE: stop_after_propose})
        objective = _objective_for(orchestrator)
        outcome = orchestrator.run(objective, control=control)
        expected = (
            ArtifactKind.RESEARCH_OBJECTIVE,
            ArtifactKind.SOURCE_INVENTORY,
            ArtifactKind.RETRIEVED_EXCERPTS,
            ArtifactKind.EVIDENCE_LEDGER,
            ArtifactKind.RESEARCH_PROPOSAL,
        )
        for kind in expected:
            stage = RESEARCH_REPORT.stage_for(kind)
            recorded = orchestrator.ledger.load(stage, kind)
            assert recorded.digest  # still there, still hashable

        # And the digests are unchanged by the cancellation.
        resumed = orchestrator.run(objective)
        assert resumed.completed_stages[:5] == outcome.completed_stages

    def test_a_stage_in_flight_when_cancellation_arrives_still_has_its_artifact_kept(
        self,
    ) -> None:
        """The check is placed *before* entering a stage, and that placement matters.

        A stage that has produced verified work has done the work. Discarding it
        because the user pressed cancel during it is precisely the loss this rule
        exists to prevent.
        """
        control = RunControl()

        def cancelling_validate(context: StageContext) -> LabCairnModel:
            control.cancel()
            from test_skill_support import validate_handler

            return validate_handler(context)

        orchestrator = make_orchestrator({StageName.VALIDATE: cancelling_validate})
        outcome = orchestrator.run(_objective_for(orchestrator), control=control)
        assert outcome.stop is WorkflowStop.CANCELLED
        assert outcome.stopped_at is StageName.DELIVER
        assert StageName.VALIDATE in outcome.completed_stages

    def test_every_completed_stage_has_a_checkpoint_after_a_cancellation(self) -> None:
        control = RunControl()

        def stop_after_propose(context: StageContext) -> LabCairnModel:
            control.cancel()
            from test_skill_support import propose_handler

            return propose_handler(context)

        orchestrator = make_orchestrator({StageName.PROPOSE: stop_after_propose})
        outcome = orchestrator.run(_objective_for(orchestrator), control=control)
        checkpointed = [cp.stage for cp in outcome.checkpoints]
        assert checkpointed == list(outcome.completed_stages)

    def test_the_checkpoints_describe_the_boundaries_for_whoever_recovers_the_run(
        self,
    ) -> None:
        """Data an LC-P1-06 recovering process can read. Not a resume mechanism."""
        control = RunControl()

        def stop_after_propose(context: StageContext) -> LabCairnModel:
            control.cancel()
            from test_skill_support import propose_handler

            return propose_handler(context)

        orchestrator = make_orchestrator({StageName.PROPOSE: stop_after_propose})
        outcome = orchestrator.run(_objective_for(orchestrator), control=control)
        for checkpoint in outcome.checkpoints:
            assert checkpoint.task_id == str(orchestrator.task_id)
            assert checkpoint.run_id == str(orchestrator.run_id)
            assert len(checkpoint.input_digests) == len(
                RESEARCH_REPORT.spec(checkpoint.stage).consumes
            )
            assert len(checkpoint.output_digests) == 1

    def test_a_cancelled_run_can_be_re_entered_and_finishes(self) -> None:
        control = RunControl()

        def stop_after_propose(context: StageContext) -> LabCairnModel:
            control.cancel()
            from test_skill_support import propose_handler

            return propose_handler(context)

        orchestrator = make_orchestrator({StageName.PROPOSE: stop_after_propose})
        objective = _objective_for(orchestrator)
        assert orchestrator.run(objective, control=control).stop is WorkflowStop.CANCELLED
        assert orchestrator.run(objective).stop is WorkflowStop.COMPLETED


# ===========================================================================
# Plan is an artifact, not an authoritative store
# ===========================================================================


class TestPlanIsDerivedNotAuthoritative:
    def test_a_forged_plan_claiming_everything_is_done_does_not_advance_the_run(self) -> None:
        """The sharp test. If the plan were a store, this would finish the run."""
        orchestrator = make_orchestrator()
        runs: list[str] = []

        def counting_inventory(context: StageContext) -> LabCairnModel:
            runs.append("inventory")
            from test_skill_support import inventory_handler

            return inventory_handler(context)

        orchestrator.handlers[StageName.INVENTORY] = counting_inventory
        objective = _objective_for(orchestrator)

        # A plan in which every stage is COMPLETED, fabricated by hand.
        from labcairn.runtime.lifecycle import StageStatus
        from labcairn.skills import PlanStep, ResearchPlan

        forged = ResearchPlan(
            task_id=str(orchestrator.task_id),
            skill_id=RESEARCH_REPORT.skill_id,
            skill_digest=RESEARCH_REPORT.digest(),
            steps=tuple(
                PlanStep(stage=stage, status=StageStatus.COMPLETED)
                for stage in RESEARCH_REPORT.order()
            ),
            built_at=orchestrator.clock(),
        )
        assert forged.completed_stages() == RESEARCH_REPORT.order()

        # Nothing about that plan reaches the orchestrator, and the run proceeds.
        outcome = orchestrator.run(objective)
        assert outcome.stop is WorkflowStop.COMPLETED
        assert runs == ["inventory"]

    def test_the_plan_is_rebuilt_from_the_ledger_not_reused(self) -> None:
        orchestrator = make_orchestrator()
        first = orchestrator.run(_objective_for(orchestrator))
        again = orchestrator.plan()
        assert first.plan is not None
        assert again.steps == first.plan.steps
        assert again.skill_digest == first.plan.skill_digest

    def test_a_plan_carries_digests_not_content(self) -> None:
        """Pointers, not facts. A plan cannot answer a scientific question."""
        orchestrator = make_orchestrator()
        outcome = orchestrator.run(_objective_for(orchestrator))
        assert outcome.plan is not None
        rendered = outcome.plan.model_dump_json()
        assert "Yield fell to" not in rendered
        assert "catalyst" not in rendered.lower()

    def test_the_run_never_reads_the_plan(self) -> None:
        """Structural: ``run`` does not accept or return a plan as an input."""
        import inspect

        from labcairn.skills import Orchestrator

        source = inspect.getsource(Orchestrator.run)
        assert "self.plan" not in source.split("return self._outcome")[0]


def test_build_plan_reports_a_pending_stage_as_pending() -> None:
    from labcairn.runtime.lifecycle import StageStatus

    orchestrator = make_orchestrator()
    plan = build_plan(
        task_id=str(orchestrator.task_id),
        declaration=RESEARCH_REPORT,
        ledger=orchestrator.ledger,
        statuses=dict.fromkeys(RESEARCH_REPORT.order(), StageStatus.PENDING),
        attempts={},
        now=orchestrator.clock(),
    )
    assert plan.completed_stages() == ()
    assert all(step.output_digests == () for step in plan.steps)


def test_an_artifact_type_mismatch_on_adoption_is_a_typed_error() -> None:
    """The seam reports the port type rather than a ``KeyError`` three stages later."""
    from test_skill_support import make_objective as objective_for_task

    from labcairn.skills import StageBlockedError as Blocked

    def blocking(context: StageContext) -> LabCairnModel:
        raise Blocked("park the run here")

    orchestrator = make_orchestrator({StageName.INVENTORY: blocking})
    orchestrator.run(objective_for_task(str(orchestrator.task_id)))
    with pytest.raises(ArtifactTypeError):
        orchestrator.adopt_artifact(
            StageName.INVENTORY, objective_for_task(str(orchestrator.task_id))
        )


def test_the_happy_path_leaves_no_substitutions_behind() -> None:
    """Belt and braces: a clean run's ledger verifies end to end."""
    orchestrator = make_orchestrator()
    orchestrator.run(_objective_for(orchestrator))
    assert orchestrator.ledger.verify_all() == ()
    assert len(orchestrator.ledger.history) == len(StageName)


def test_the_objective_must_belong_to_this_run_s_task() -> None:
    from test_skill_support import make_objective as objective_for_task

    from labcairn.skills import StageContractError

    orchestrator = make_orchestrator()
    with pytest.raises(StageContractError, match="belongs to task"):
        orchestrator.run(objective_for_task("some-other-task"))


def test_an_adopted_artifact_is_marked_as_externally_asserted() -> None:
    """Kept distinct from "this run made it", because an audit log needs both."""
    from test_skill_support import make_objective as objective_for_task

    from labcairn.skills import StageBlockedError as Blocked

    def blocking(context: StageContext) -> LabCairnModel:
        raise Blocked("park the run here")

    orchestrator = make_orchestrator({StageName.INVENTORY: blocking})
    objective = objective_for_task(str(orchestrator.task_id))
    orchestrator.run(objective)
    intake = orchestrator.ledger.load(StageName.INTAKE, ArtifactKind.RESEARCH_OBJECTIVE)
    orchestrator.adopt_artifact(
        StageName.INVENTORY, build_inventory((intake.digest,), task_id=str(orchestrator.task_id))
    )
    recorded = orchestrator.ledger.load(StageName.INVENTORY, ArtifactKind.SOURCE_INVENTORY)
    assert recorded.externally_asserted is True
    assert recorded.produced_by is None


def test_the_inventory_really_is_what_downstream_stages_see() -> None:
    """The acceptance rule stated as a fact about the objects, not about a log line."""
    orchestrator = make_orchestrator()
    orchestrator.run(_objective_for(orchestrator))
    inventory = orchestrator.ledger.load(StageName.INVENTORY, ArtifactKind.SOURCE_INVENTORY)
    assert isinstance(inventory.artifact, SourceInventory)
    assert set(inventory.artifact.material_hashes()) == {
        material.content_sha256 for material in _objective_for(orchestrator).declared_materials
    }
    assert PAPER_SHA in inventory.artifact.anchor_index().values()
    assert FOREIGN_SHA not in inventory.artifact.anchor_index().values()


def test_evidence_really_only_cites_what_retrieval_returned() -> None:
    orchestrator = make_orchestrator()
    orchestrator.run(_objective_for(orchestrator))
    retrieved = orchestrator.ledger.load(StageName.RETRIEVE, ArtifactKind.RETRIEVED_EXCERPTS)
    ledger = orchestrator.ledger.load(StageName.EVIDENCE, ArtifactKind.EVIDENCE_LEDGER)
    assert isinstance(retrieved.artifact, RetrievedExcerpts)
    assert isinstance(ledger.artifact, EvidenceLedgerView)
    known = retrieved.artifact.excerpt_index()
    for claim in ledger.artifact.claims:
        assert claim.anchor_refs
        for ref in claim.anchor_refs:
            assert known[ref.anchor_id] == ref.material_sha256
