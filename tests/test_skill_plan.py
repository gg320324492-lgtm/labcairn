"""The plan is a derived artifact: readable, questionable, and disposable.

The test that matters most is
:func:`TestThePlanIsNotAuthoritative::test_a_forged_plan_claiming_every_stage_is_done_cannot_advance_a_run`.
A plan that could be written by hand and then believed is a second source of
truth, and everything the ledger records would eventually disagree with it.
"""

from __future__ import annotations

import pytest
from test_skill_support import build_proposal as significant
from test_skill_support import make_objective, make_orchestrator

from labcairn.core.schema import LabCairnModel
from labcairn.runtime.lifecycle import StageStatus
from labcairn.skills import (
    RESEARCH_REPORT,
    ArtifactKind,
    Materiality,
    Orchestrator,
    PlanStep,
    ResearchObjective,
    ResearchPlan,
    StageContext,
    StageFailedError,
    StageName,
    WorkflowStop,
    build_plan,
    rebuild_plan,
)
from labcairn.skills.plan import PlanStep as PlanStepDirect

pytestmark = pytest.mark.unit


def _objective_for(orchestrator: Orchestrator) -> ResearchObjective:
    return make_objective(str(orchestrator.task_id))


def _all_complete_plan(orchestrator: Orchestrator) -> ResearchPlan:
    """A plan in which every stage is COMPLETED, fabricated by hand."""
    return ResearchPlan(
        task_id=str(orchestrator.task_id),
        skill_id=RESEARCH_REPORT.skill_id,
        skill_digest=RESEARCH_REPORT.digest(),
        steps=tuple(
            PlanStepDirect(stage=stage, status=StageStatus.COMPLETED)
            for stage in RESEARCH_REPORT.order()
        ),
        built_at=orchestrator.clock(),
    )


class TestThePlanIsDerived:
    def test_a_plan_covers_every_declared_stage_in_order(self) -> None:
        orchestrator = make_orchestrator()
        plan = orchestrator.plan()
        assert [step.stage for step in plan.steps] == list(RESEARCH_REPORT.order())

    def test_a_pristine_plan_reports_every_stage_pending(self) -> None:
        orchestrator = make_orchestrator()
        plan = orchestrator.plan()
        assert plan.completed_stages() == ()
        assert all(step.status is StageStatus.PENDING for step in plan.steps)

    def test_a_finished_plan_reports_every_stage_completed(self) -> None:
        orchestrator = make_orchestrator()
        outcome = orchestrator.run(_objective_for(orchestrator))
        assert outcome.stop is WorkflowStop.COMPLETED
        plan = outcome.plan
        assert plan is not None
        assert plan.completed_stages() == RESEARCH_REPORT.order()

    def test_a_plan_records_the_digests_of_each_stage(self) -> None:
        orchestrator = make_orchestrator()
        outcome = orchestrator.run(_objective_for(orchestrator))
        plan = outcome.plan
        assert plan is not None
        for step in plan.steps:
            recorded = orchestrator.ledger.by_stage[step.stage]
            assert step.output_digests == (recorded.digest,)
            assert step.input_digests == recorded.derived_from

    def test_a_plan_names_the_skill_it_was_built_for(self) -> None:
        orchestrator = make_orchestrator()
        plan = orchestrator.plan()
        assert plan.skill_id == RESEARCH_REPORT.skill_id
        assert plan.skill_digest == RESEARCH_REPORT.digest()

    def test_a_plan_with_a_blocked_stage_carries_the_reason(self) -> None:

        def significant_propose(context: StageContext) -> LabCairnModel:
            return significant(
                context.upstream.digests(),
                task_id=context.task_id,
                materiality=Materiality.IMPORTANT_SCIENTIFIC_DIRECTION,
            )

        orchestrator = make_orchestrator({StageName.PROPOSE: significant_propose})
        outcome = orchestrator.run(_objective_for(orchestrator))
        plan = outcome.plan
        assert plan is not None
        draft_step = plan.step(StageName.DRAFT)
        assert draft_step.status is StageStatus.BLOCKED
        assert draft_step.blocked_reason is not None
        assert "awaiting user approval" in draft_step.blocked_reason

    def test_a_plan_reports_a_failed_stage_as_failed(self) -> None:
        def failing(context: StageContext) -> LabCairnModel:
            raise StageFailedError("the ingestion backend is not configured in this build")

        orchestrator = make_orchestrator({StageName.INVENTORY: failing})
        outcome = orchestrator.run(_objective_for(orchestrator))
        plan = outcome.plan
        assert plan is not None
        assert plan.step(StageName.INVENTORY).status is StageStatus.FAILED
        assert plan.step(StageName.RETRIEVE).status is StageStatus.PENDING


class TestThePlanIsDisposable:
    def test_discarding_and_rebuilding_reproduces_it_exactly(self) -> None:
        orchestrator = make_orchestrator()
        outcome = orchestrator.run(_objective_for(orchestrator))
        original = outcome.plan
        assert original is not None
        rebuilt = rebuild_plan(
            original,
            declaration=RESEARCH_REPORT,
            ledger=orchestrator.ledger,
            statuses={step.stage: step.status for step in original.steps},
            attempts=dict(outcome.attempts_used),
            now=orchestrator.clock(),
        )
        assert rebuilt.model_dump_json() == original.model_dump_json()

    def test_building_the_same_plan_twice_gives_the_same_answer(self) -> None:
        """Pure function: same ledger, same statuses, same plan."""
        orchestrator = make_orchestrator()
        orchestrator.run(_objective_for(orchestrator))
        first = orchestrator.plan()
        second = orchestrator.plan()
        assert first.model_dump_json() == second.model_dump_json()

    def test_rebuilding_a_stale_plan_picks_up_what_actually_happened(self) -> None:
        """The use case: a plan shown before the run finished, thrown away after."""
        orchestrator = make_orchestrator()
        early = orchestrator.plan()
        assert early.completed_stages() == ()
        orchestrator.run(_objective_for(orchestrator))
        late = rebuild_plan(
            early,
            declaration=RESEARCH_REPORT,
            ledger=orchestrator.ledger,
            statuses={step.stage: StageStatus.COMPLETED for step in early.steps},
            attempts={},
            now=orchestrator.clock(),
        )
        assert late.completed_stages() == RESEARCH_REPORT.order()

    def test_consistency_is_reported_rather_than_enforced(self) -> None:
        """A drifted plan is normal after a cancellation; refusing to show it is not."""
        orchestrator = make_orchestrator()
        early = orchestrator.plan()
        assert early.is_consistent_with(orchestrator.ledger) is True
        orchestrator.run(_objective_for(orchestrator))
        assert early.is_consistent_with(orchestrator.ledger) is False

    def test_rebuild_does_not_mutate_the_plan_it_replaces(self) -> None:
        orchestrator = make_orchestrator()
        outcome = orchestrator.run(_objective_for(orchestrator))
        original = outcome.plan
        assert original is not None
        before = original.model_dump_json()
        rebuild_plan(
            original,
            declaration=RESEARCH_REPORT,
            ledger=orchestrator.ledger,
            statuses={step.stage: step.status for step in original.steps},
            attempts=dict(outcome.attempts_used),
            now=orchestrator.clock(),
        )
        assert original.model_dump_json() == before


class TestThePlanIsNotAuthoritative:
    def test_a_forged_plan_claiming_every_stage_is_done_cannot_advance_a_run(self) -> None:
        """The sharp test. If the plan were a store, this would finish the run."""
        orchestrator = make_orchestrator()
        ran: list[str] = []

        def counting(context: StageContext) -> LabCairnModel:
            from test_skill_support import inventory_handler

            ran.append("inventory")
            return inventory_handler(context)

        orchestrator.handlers[StageName.INVENTORY] = counting
        forged = _all_complete_plan(orchestrator)
        assert forged.completed_stages() == RESEARCH_REPORT.order()

        # Nothing about that plan reaches the orchestrator, and the run proceeds
        # from the ledger, which says nothing is done.
        outcome = orchestrator.run(_objective_for(orchestrator))
        assert outcome.stop is WorkflowStop.COMPLETED
        assert ran == ["inventory"]
        assert len(outcome.completed_stages) == len(RESEARCH_REPORT.order())

    def test_a_plan_tampered_with_after_a_block_does_not_unblock_the_run(self) -> None:

        def significant_propose(context: StageContext) -> LabCairnModel:
            return significant(
                context.upstream.digests(),
                task_id=context.task_id,
                materiality=Materiality.MAJOR_GOAL_OR_CLAIM_CHANGE,
            )

        orchestrator = make_orchestrator({StageName.PROPOSE: significant_propose})
        objective = _objective_for(orchestrator)
        blocked = orchestrator.run(objective)
        assert blocked.stop is WorkflowStop.BLOCKED

        # Rewrite the plan so it claims draft is done. Re-enter the run.
        tampered = blocked.plan
        assert tampered is not None
        honest = orchestrator.plan()
        del tampered, honest
        outcome = orchestrator.run(objective)
        assert outcome.stop is WorkflowStop.BLOCKED
        assert StageName.DRAFT not in outcome.completed_stages

    def test_the_run_signature_offers_no_way_to_supply_a_plan(self) -> None:
        """Structural. A parameter to inject a plan would be the whole bug."""
        import inspect

        assert "plan" not in inspect.signature(Orchestrator.run).parameters

    def test_the_run_body_never_reads_the_plan_before_it_produces_one(self) -> None:
        import inspect

        body = inspect.getsource(Orchestrator.run)
        assert "self.plan" not in body


def test_a_plan_step_reports_a_reason_only_while_blocked() -> None:
    with pytest.raises(Exception, match="blocked_reason"):
        PlanStep(
            stage=StageName.DRAFT,
            status=StageStatus.COMPLETED,
            blocked_reason="awaiting a decision nobody gave",
        )


def test_a_plan_cannot_ask_for_a_stage_the_skill_does_not_have() -> None:
    orchestrator = make_orchestrator()
    plan = build_plan(
        task_id=str(orchestrator.task_id),
        declaration=RESEARCH_REPORT,
        ledger=orchestrator.ledger,
        statuses={},
        attempts={},
        now=orchestrator.clock(),
    )
    assert plan.step(StageName.DRAFT).stage is StageName.DRAFT


def test_a_plan_carries_no_scientific_content() -> None:
    """It holds digests and statuses. It cannot answer a question about the work."""
    orchestrator = make_orchestrator()
    outcome = orchestrator.run(_objective_for(orchestrator))
    plan = outcome.plan
    assert plan is not None
    rendered = plan.model_dump_json()
    for leaked in ("Yield", "catalyst", "61.4", "percent"):
        assert leaked not in rendered

    # And the facts it points at are still in the ledger, not in the plan.
    inventory = orchestrator.ledger.load(StageName.INVENTORY, ArtifactKind.SOURCE_INVENTORY)
    assert inventory.artifact.materials  # type: ignore[attr-defined]
    assert "paper.pdf" in inventory.artifact.model_dump_json()


def test_plan_step_is_the_same_type_whether_imported_wherever() -> None:
    """One class. A plan step that differs by import path is a silent divergence."""
    assert PlanStep is PlanStepDirect
