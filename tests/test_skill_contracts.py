"""The contracts themselves: the stage graph and the typed artifacts.

The stage-graph tests are the ones worth reading first. ``docs/ARCHITECTURE.md``
"Stage workflow (Phase 1)" fixes the sequence
``intake -> inventory -> retrieve -> evidence -> propose -> [approval] -> draft
-> validate -> deliver``, and that specification is asserted literally rather
than by reading the code and agreeing with it — a reordering that still passed
every other test would still be a spec violation.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from test_skill_support import (
    DEFAULT_CRITERION,
    FOREIGN_SHA,
    PAPER_SHA,
    make_orchestrator,
    make_task_id,
)

from labcairn.evidence.states import VerificationStatus
from labcairn.skills import (
    RESEARCH_REPORT,
    AnchorRef,
    ArtifactKind,
    DeclaredMaterial,
    DraftSection,
    EvidenceClaim,
    GoalChange,
    Materiality,
    Orchestrator,
    Severity,
    SkillDeclaration,
    SkillDeclarationError,
    StageBudget,
    StageName,
    StageSpec,
    ValidationFinding,
    ValidationReport,
    ValidationVerdict,
    research_report_skill,
)
from labcairn.skills.artifacts import DeliveredManifestEntry, DeliveredReport
from labcairn.skills.quality import CONTRACT_MODELS

pytestmark = pytest.mark.unit

#: The sequence as written in docs/ARCHITECTURE.md. Spelled out here rather than
#: imported from anywhere, because the point is to compare the code against the
#: document, and importing both from one place would make that comparison vacuous.
ARCHITECTURE_SEQUENCE = (
    "intake",
    "inventory",
    "retrieve",
    "evidence",
    "propose",
    "draft",
    "validate",
    "deliver",
)


class TestStageGraph:
    def test_the_graph_is_the_architecture_sequence(self) -> None:
        assert tuple(s.value for s in RESEARCH_REPORT.order()) == ARCHITECTURE_SEQUENCE

    def test_the_declaration_is_named_after_the_work_order(self) -> None:
        assert RESEARCH_REPORT.skill_id == "labcairn.research-report.v1"

    def test_exactly_one_stage_is_guarded_and_it_is_draft(self) -> None:
        guarded = [spec.stage for spec in RESEARCH_REPORT.stages if spec.guarded]
        assert guarded == [StageName.DRAFT]

    def test_every_input_is_produced_by_an_earlier_stage(self) -> None:
        seen: list[StageName] = []
        for spec in RESEARCH_REPORT.stages:
            for dependency in spec.consumes:
                assert dependency in seen, f"{spec.stage} consumes {dependency} before it runs"
            seen.append(spec.stage)

    def test_every_artifact_kind_is_produced_exactly_once(self) -> None:
        produced = [spec.produces for spec in RESEARCH_REPORT.stages]
        assert len(produced) == len(set(produced))
        assert set(produced) == set(ArtifactKind)

    def test_the_first_stage_has_no_input(self) -> None:
        assert RESEARCH_REPORT.spec(StageName.INTAKE).consumes == ()

    def test_draft_consumes_the_proposal_it_was_approved_from(self) -> None:
        """``draft`` takes ``propose`` *and* ``evidence``.

        Prose that does not receive the proposal cannot be shown to follow the
        approved direction, and prose that does not receive the ledger cannot cite
        anything. Both edges are required, and this test is what keeps someone
        from "simplifying" it to one.
        """
        assert set(RESEARCH_REPORT.spec(StageName.DRAFT).consumes) == {
            StageName.PROPOSE,
            StageName.EVIDENCE,
        }

    def test_the_skill_digest_changes_when_the_graph_changes(self) -> None:
        altered = SkillDeclaration(
            skill_id=RESEARCH_REPORT.skill_id,
            title=RESEARCH_REPORT.title,
            budget=StageBudget(),
            stages=RESEARCH_REPORT.stages[:-1],
        )
        assert altered.digest() != RESEARCH_REPORT.digest()

    def test_the_skill_digest_is_stable_across_constructions(self) -> None:
        assert research_report_skill().digest() == RESEARCH_REPORT.digest()

    def test_the_budget_changes_the_skill_digest(self) -> None:
        """A plan names the skill it was built for; a budget change is a skill change."""
        assert research_report_skill(StageBudget(max_attempts_per_stage=2)).digest() != (
            RESEARCH_REPORT.digest()
        )


class TestDeclarationRefusesInconsistency:
    """A malformed skill is refused at registration, not halfway through a run."""

    def _spec(self, stage: StageName, **kwargs: object) -> StageSpec:
        """A minimal legal stage spec, for building graphs that should be refused."""
        kwargs.setdefault("consumes", ())
        return StageSpec(stage=stage, produces=ArtifactKind.RESEARCH_OBJECTIVE, **kwargs)  # type: ignore[arg-type]

    def test_a_stage_may_not_consume_itself(self) -> None:
        with pytest.raises(SkillDeclarationError, match="feeds itself"):
            StageSpec(
                stage=StageName.EVIDENCE,
                consumes=(StageName.EVIDENCE,),
                produces=ArtifactKind.EVIDENCE_LEDGER,
            )

    def test_a_stage_may_not_list_a_duplicate_input(self) -> None:
        with pytest.raises(SkillDeclarationError, match="duplicate input"):
            StageSpec(
                stage=StageName.DRAFT,
                consumes=(StageName.PROPOSE, StageName.PROPOSE),
                produces=ArtifactKind.REPORT_DRAFT,
            )

    def test_a_forward_edge_is_refused(self) -> None:
        declaration = SkillDeclaration(
            skill_id="x",
            title="x",
            stages=(
                self._spec(StageName.INTAKE),
                StageSpec(
                    stage=StageName.INVENTORY,
                    consumes=(StageName.RETRIEVE,),
                    produces=ArtifactKind.SOURCE_INVENTORY,
                ),
            ),
        )
        with pytest.raises(SkillDeclarationError, match="declared later"):
            declaration.validate()

    def test_an_undeclared_input_is_refused(self) -> None:
        """Consuming a stage the skill does not contain at all."""
        declaration = SkillDeclaration(
            skill_id="x",
            title="x",
            stages=(
                self._spec(StageName.INTAKE),
                StageSpec(
                    stage=StageName.EVIDENCE,
                    consumes=(StageName.RETRIEVE,),
                    produces=ArtifactKind.EVIDENCE_LEDGER,
                ),
                StageSpec(
                    stage=StageName.DRAFT,
                    consumes=(StageName.EVIDENCE,),
                    produces=ArtifactKind.REPORT_DRAFT,
                    guarded=True,
                ),
            ),
        )
        with pytest.raises(SkillDeclarationError, match=r"declared later|not declared"):
            declaration.validate()

    def test_two_stages_may_not_produce_the_same_port(self) -> None:
        declaration = SkillDeclaration(
            skill_id="x",
            title="x",
            stages=(
                self._spec(StageName.INTAKE),
                self._spec(StageName.INVENTORY),
            ),
        )
        with pytest.raises(SkillDeclarationError, match="produced twice"):
            declaration.validate()

    def test_a_first_stage_with_an_input_is_refused(self) -> None:
        declaration = SkillDeclaration(
            skill_id="x",
            title="x",
            stages=(
                StageSpec(
                    stage=StageName.INTAKE,
                    consumes=(StageName.INVENTORY,),
                    produces=ArtifactKind.RESEARCH_OBJECTIVE,
                ),
            ),
        )
        with pytest.raises(SkillDeclarationError, match=r"declared later|not declared"):
            declaration.validate()

    def test_zero_guarded_stages_is_refused(self) -> None:
        declaration = SkillDeclaration(
            skill_id="x",
            title="x",
            stages=(self._spec(StageName.INTAKE),),
        )
        with pytest.raises(SkillDeclarationError, match="exactly one stage must be guarded"):
            declaration.validate()

    def test_two_guarded_stages_is_refused(self) -> None:
        declaration = SkillDeclaration(
            skill_id="x",
            title="x",
            stages=(
                self._spec(StageName.INTAKE),
                StageSpec(
                    stage=StageName.INVENTORY,
                    consumes=(StageName.INTAKE,),
                    produces=ArtifactKind.SOURCE_INVENTORY,
                    guarded=True,
                ),
                StageSpec(
                    stage=StageName.RETRIEVE,
                    consumes=(StageName.INVENTORY,),
                    produces=ArtifactKind.RETRIEVED_EXCERPTS,
                    guarded=True,
                ),
            ),
        )
        with pytest.raises(SkillDeclarationError, match="exactly one stage must be guarded"):
            declaration.validate()

    def test_a_skill_with_no_stages_is_refused(self) -> None:
        with pytest.raises(SkillDeclarationError, match="no stages"):
            SkillDeclaration(skill_id="x", title="x", stages=()).validate()

    def test_an_orchestrator_without_handlers_is_refused_at_construction(self) -> None:
        """A missing stage body is a wiring mistake, not a mid-run KeyError."""
        from test_skill_support import make_run_id

        with pytest.raises(SkillDeclarationError, match="has no handler"):
            Orchestrator(
                RESEARCH_REPORT,
                {},
                task_id=make_task_id(),
                run_id=make_run_id(),
            )


class TestArtifactInvariants:
    def test_a_material_declared_twice_is_refused(self) -> None:
        """Same file, two names: one input, not two."""
        from labcairn.skills import ResearchObjective

        material = DeclaredMaterial(
            display_name="paper.pdf", content_sha256=PAPER_SHA, size_bytes=1
        )
        with pytest.raises(ValidationError, match="duplicate material"):
            ResearchObjective(
                task_id="t",
                objective="o",
                success_criterion="s",
                declared_materials=(
                    material,
                    material.model_copy(update={"display_name": "p2.pdf"}),
                ),
            )

    def test_an_objective_requires_at_least_one_material(self) -> None:
        from labcairn.skills import ResearchObjective

        with pytest.raises(ValidationError):
            ResearchObjective(
                task_id="t", objective="o", success_criterion="s", declared_materials=()
            )

    def test_an_unreadable_material_must_say_why(self) -> None:
        from labcairn.skills import InventoryMaterial

        with pytest.raises(ValidationError, match="unreadable and"):
            InventoryMaterial(
                display_name="scan.pdf",
                content_sha256="a" * 64,
                size_bytes=1,
                readable=False,
            )

    def test_a_readable_material_may_not_carry_a_caveat(self) -> None:
        from labcairn.skills import InventoryMaterial

        with pytest.raises(ValidationError, match="readable and carries the note"):
            InventoryMaterial(
                display_name="paper.pdf",
                content_sha256="a" * 64,
                size_bytes=1,
                readable=True,
                note="parsed with warnings",
            )

    def test_a_claim_past_planned_must_cite_an_anchor(self) -> None:
        """The placeholder shape the whole evidence model exists to exclude."""
        with pytest.raises(ValidationError, match="cites no anchor"):
            EvidenceClaim(
                claim_id="c-1",
                statement="The yield fell with increasing loading.",
                status=VerificationStatus.VERIFIED_BY_RULE,
            )

    def test_a_planned_claim_may_exist_without_an_anchor(self) -> None:
        claim = EvidenceClaim(claim_id="c-1", statement="The yield fell with loading.")
        assert claim.status is VerificationStatus.PLANNED
        assert claim.anchor_refs == ()

    def test_a_claim_may_not_cite_the_same_anchor_twice(self) -> None:
        with pytest.raises(ValidationError, match="more than once"):
            EvidenceClaim(
                claim_id="c-1",
                statement="The yield fell with increasing loading in the trials.",
                anchor_refs=(
                    AnchorRef(anchor_id="a-1", material_sha256=PAPER_SHA),
                    AnchorRef(anchor_id="a-1", material_sha256=PAPER_SHA),
                ),
                status=VerificationStatus.EXTRACTED,
            )

    def test_a_draft_section_must_cite_a_claim(self) -> None:
        with pytest.raises(ValidationError):
            DraftSection(
                section_id="s-1",
                heading="Result",
                body="The yield fell to 61.4 percent at the highest loading tested.",
                evidence_refs=(),
            )

    def test_a_goal_change_that_changes_nothing_is_refused(self) -> None:
        """A no-op that still consumes an approval trains rubber-stamping."""
        with pytest.raises(ValidationError, match=r"sets .* to the value it already had"):
            GoalChange(
                change_id="g-1",
                target="objective",
                old_value=DEFAULT_CRITERION,
                new_value=DEFAULT_CRITERION,
                reason="The reviewer asked for a bounded interval beside the point value.",
            )

    def test_a_pass_with_an_error_finding_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="error finding"):
            ValidationReport(
                task_id="t",
                findings=(
                    ValidationFinding(
                        finding_id="f-1",
                        severity=Severity.ERROR,
                        target_section_id="s-1",
                        message="The reported value does not reconcile with the cell.",
                    ),
                ),
                checked_sections=("s-1",),
                verdict=ValidationVerdict.PASS,
                derived_from=("a" * 64,),
            )

    def test_a_failure_with_no_error_finding_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="no error finding"):
            ValidationReport(
                task_id="t",
                findings=(
                    ValidationFinding(
                        finding_id="f-1",
                        severity=Severity.INFO,
                        target_section_id="s-1",
                        message="Everything checked out against the ledger of this run.",
                    ),
                ),
                checked_sections=("s-1",),
                verdict=ValidationVerdict.FAIL,
                derived_from=("a" * 64,),
            )

    def test_a_warning_alone_still_passes(self) -> None:
        """``WARNING`` is a note to the reader, not a stop."""
        report = ValidationReport(
            task_id="t",
            findings=(
                ValidationFinding(
                    finding_id="f-1",
                    severity=Severity.WARNING,
                    target_section_id="s-1",
                    message="One section has no quantitative claim, which is allowed.",
                ),
            ),
            checked_sections=("s-1",),
            verdict=ValidationVerdict.PASS,
            derived_from=("a" * 64,),
        )
        assert report.verdict is ValidationVerdict.PASS

    def test_a_delivered_report_requires_a_manifest(self) -> None:
        with pytest.raises(ValidationError):
            DeliveredReport(
                task_id="t",
                draft_digest="a" * 64,
                validation_verdict=ValidationVerdict.PASS,
                manifest=(),
                derived_from=("b" * 64,),
            )

    def test_a_manifest_entry_is_a_hash_and_a_relative_path(self) -> None:
        DeliveredManifestEntry(relative_path="report.md", content_sha256="c" * 64)


class TestMateriality:
    @pytest.mark.parametrize(
        ("materiality", "required"),
        [
            (Materiality.ROUTINE, False),
            (Materiality.IMPORTANT_SCIENTIFIC_DIRECTION, True),
            (Materiality.MAJOR_GOAL_OR_CLAIM_CHANGE, True),
        ],
    )
    def test_only_the_two_significant_levels_require_approval(
        self, materiality: Materiality, required: bool
    ) -> None:
        assert materiality.requires_approval is required

    def test_the_enum_has_exactly_three_levels(self) -> None:
        """Adding one is a reviewed change with a decided approval semantic."""
        assert set(Materiality) == {
            Materiality.ROUTINE,
            Materiality.IMPORTANT_SCIENTIFIC_DIRECTION,
            Materiality.MAJOR_GOAL_OR_CLAIM_CHANGE,
        }


class TestContractTable:
    def test_every_artifact_kind_has_a_model(self) -> None:
        from labcairn.skills import artifact_type

        for kind in ArtifactKind:
            assert issubclass(artifact_type(kind), object)
            assert artifact_type(kind) in CONTRACT_MODELS

    def test_the_contract_table_and_the_kind_table_agree_in_size(self) -> None:
        assert len(CONTRACT_MODELS) == len(ArtifactKind)


def test_the_support_handlers_satisfy_the_contract() -> None:
    """A guard set that cannot accept a well-behaved run proves nothing."""
    orchestrator = make_orchestrator()
    from test_skill_support import make_objective

    outcome = orchestrator.run(make_objective(str(orchestrator.task_id)))
    assert outcome.stop.value == "completed"
    assert len(outcome.completed_stages) == len(ARCHITECTURE_SEQUENCE)
    assert FOREIGN_SHA not in str(outcome.reason)
