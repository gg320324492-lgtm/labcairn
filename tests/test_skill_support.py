"""Shared fixtures and honest stage bodies for the ``research-report`` tests.

These handlers are **not** implementations of LC-P1-08 through LC-P1-11. They
are the smallest bodies that satisfy the contract, written so each one reads its
declared inputs and reflects them into its output. That is deliberate: the
orchestrator's guards exist to catch a stage that does *not* do that, and a test
double that skipped the work would leave them untestable.

Everything is deterministic: fixed clock, fixed ids, fixed hashes. No wall clock,
no ``uuid4`` inside a fixture, per the repository rule in ``conftest.py``.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Final

from labcairn.core.ids import RunId, TaskId, new_id
from labcairn.evidence.states import VerificationStatus
from labcairn.skills import (
    RESEARCH_REPORT,
    AnchorRef,
    ApprovalDecision,
    ArtifactKind,
    DeclaredMaterial,
    DeliveredManifestEntry,
    DeliveredReport,
    DraftSection,
    EvidenceClaim,
    EvidenceLedgerView,
    GoalChange,
    InventoryAnchor,
    InventoryMaterial,
    Materiality,
    Orchestrator,
    ProposalItem,
    ReportDraft,
    ResearchObjective,
    ResearchProposal,
    RetrievedExcerpt,
    RetrievedExcerpts,
    Severity,
    SkillDeclaration,
    SourceInventory,
    StageBlockedError,
    StageContext,
    StageName,
    ValidationFinding,
    ValidationReport,
    ValidationVerdict,
)
import pytest

pytestmark = pytest.mark.unit

#: The clock every orchestrator under test reads. Later than the repository-wide
#: ``FROZEN_NOW`` so a test using both does not trip a "modified at" check.
SKILL_NOW: Final = datetime(2026, 3, 1, 12, 0, 0, tzinfo=UTC)

#: Real sha256 digests of their own names: stable, shape-valid, and readable.
PAPER_SHA: Final = hashlib.sha256(b"paper.pdf").hexdigest()
DATA_SHA: Final = hashlib.sha256(b"data.csv").hexdigest()

#: Material and anchor this task was **never** bound to. Used to build forgeries:
#: schema-valid, internally consistent, and about something else entirely.
FOREIGN_SHA: Final = hashlib.sha256(b"unrelated.pdf").hexdigest()
FOREIGN_ANCHOR: Final = "a-foreign"

DEFAULT_OBJECTIVE: Final = "Establish whether the catalyst loading affects the yield"
DEFAULT_CRITERION: Final = "Report the effect with every number located in a bound material"


def fixed_clock() -> datetime:
    """The clock handed to orchestrators under test."""
    return SKILL_NOW


def later_clock(delta: timedelta = timedelta(hours=1)) -> datetime:
    """A time after :data:`SKILL_NOW`, for approval-window tests."""
    return SKILL_NOW + delta


# ---------------------------------------------------------------------------
# Artifact builders. Each takes the upstream digests it must declare, so a test
# can build a *correct* artifact for a wrong lineage and watch it be refused.
# ---------------------------------------------------------------------------


def make_task_id() -> TaskId:
    """A fresh Task id. Minted per call so tests stay isolated."""
    return TaskId(new_id())


def make_run_id() -> RunId:
    """A fresh Run id."""
    return RunId(new_id())


def make_objective(
    task_id: str,
    *,
    objective: str = DEFAULT_OBJECTIVE,
    success_criterion: str = DEFAULT_CRITERION,
    materials: tuple[tuple[str, str], ...] = (("paper.pdf", PAPER_SHA), ("data.csv", DATA_SHA)),
) -> ResearchObjective:
    """A root artifact bound to *materials* as ``(display_name, content_sha256)``."""
    return ResearchObjective(
        task_id=task_id,
        objective=objective,
        success_criterion=success_criterion,
        declared_materials=tuple(
            DeclaredMaterial(display_name=name, content_sha256=sha, size_bytes=1024)
            for name, sha in materials
        ),
    )


def make_anchor(anchor_id: str, material_sha: str) -> InventoryAnchor:
    """One inventory anchor with a computed, human-readable locator."""
    return InventoryAnchor(
        anchor_id=anchor_id,
        material_sha256=material_sha,
        locator_description=f"page 3 of the material with hash {material_sha[:8]}",
    )


def build_inventory(
    upstream: tuple[str, ...],
    *,
    task_id: str = "task",
    materials: tuple[tuple[str, str, bool], ...] | None = None,
    anchors: tuple[InventoryAnchor, ...] | None = None,
) -> SourceInventory:
    """A well-formed inventory.

    *materials* is ``(display_name, content_sha256, readable)``; the default is
    the two materials :func:`make_objective` declares. *anchors* defaults to one
    anchor per material.
    """
    chosen = (
        materials
        if materials is not None
        else (
            ("paper.pdf", PAPER_SHA, True),
            ("data.csv", DATA_SHA, True),
        )
    )
    built = tuple(
        InventoryMaterial(
            display_name=name,
            content_sha256=sha,
            size_bytes=1024,
            readable=readable,
            note=None if readable else "No text layer was present and OCR is not available.",
        )
        for name, sha, readable in chosen
    )
    built_anchors = (
        anchors
        if anchors is not None
        else tuple(
            make_anchor(f"a-{index}", sha) for index, (_n, sha, _r) in enumerate(chosen, start=1)
        )
    )
    return SourceInventory(
        task_id=task_id, materials=built, anchors=built_anchors, derived_from=upstream
    )


def build_retrieved(upstream: tuple[str, ...], *, task_id: str = "task") -> RetrievedExcerpts:
    """Two passages, each anchored in a real inventory anchor."""
    return RetrievedExcerpts(
        task_id=task_id,
        excerpts=(
            RetrievedExcerpt(
                anchor_id="a-1",
                material_sha256=PAPER_SHA,
                rank=1,
                excerpt="Catalyst loading above four weight percent reduced the yield.",
                retrieval_method="fts5 lexical over normalised excerpts",
            ),
            RetrievedExcerpt(
                anchor_id="a-2",
                material_sha256=DATA_SHA,
                rank=2,
                excerpt="Row twelve records a yield of 61.4 percent at the highest loading.",
                retrieval_method="fts5 lexical over normalised excerpts",
            ),
        ),
        derived_from=upstream,
    )


def build_ledger(
    upstream: tuple[str, ...],
    *,
    task_id: str = "task",
    claim_ids: tuple[str, ...] = ("c-1", "c-2"),
    anchors: tuple[tuple[str, str], ...] | None = None,
) -> EvidenceLedgerView:
    """One claim per id, each anchored in a retrieved passage."""
    pairs = anchors if anchors is not None else (("a-1", PAPER_SHA), ("a-2", DATA_SHA))
    claims = tuple(
        EvidenceClaim(
            claim_id=claim_id,
            statement=(f"The bound material supports finding {claim_id} about the loading effect."),
            anchor_refs=(AnchorRef(anchor_id=anchor_id, material_sha256=material),),
            status=VerificationStatus.EXTRACTED,
        )
        for index, claim_id in enumerate(claim_ids)
        for anchor_id, material in (pairs[index % len(pairs)],)
    )
    return EvidenceLedgerView(task_id=task_id, claims=claims, derived_from=upstream)


def build_proposal(
    upstream: tuple[str, ...],
    *,
    task_id: str = "task",
    materiality: Materiality = Materiality.ROUTINE,
    with_goal_change: bool = False,
    evidence_refs: tuple[str, ...] = ("c-1",),
) -> ResearchProposal:
    """A proposal whose single item rests on named claims."""
    changes = (
        (
            GoalChange(
                change_id="g-1",
                target="success_criterion",
                old_value=DEFAULT_CRITERION,
                new_value=f"{DEFAULT_CRITERION} and bounded by an interval",
                reason="The reviewer asked for a bounded interval beside the point value.",
            ),
        )
        if with_goal_change
        else ()
    )
    return ResearchProposal(
        task_id=task_id,
        direction="Report the loading-yield relationship using only located numbers.",
        items=(
            ProposalItem(
                item_id="p-1",
                statement="Lead with the measured yield at the highest catalyst loading.",
                materiality=materiality,
                rationale="It is the only number located in the tabular material.",
                evidence_refs=evidence_refs,
            ),
        ),
        goal_changes=changes,
        derived_from=upstream,
    )


def build_draft(
    upstream: tuple[str, ...],
    *,
    task_id: str = "task",
    sections: tuple[DraftSection, ...] | None = None,
) -> ReportDraft:
    """Two sections, each citing a claim that exists upstream."""
    built = (
        sections
        if sections is not None
        else (
            DraftSection(
                section_id="s-method",
                heading="Materials and method",
                body="Two bound materials were inventoried and searched locally.",
                evidence_refs=("c-1",),
            ),
            DraftSection(
                section_id="s-result",
                heading="Result",
                body="Yield fell to 61.4 percent at the highest catalyst loading tested.",
                evidence_refs=("c-2",),
            ),
        )
    )
    return ReportDraft(task_id=task_id, sections=built, derived_from=upstream)


def build_validation(
    upstream: tuple[str, ...],
    *,
    task_id: str = "task",
    section_ids: tuple[str, ...] = ("s-method", "s-result"),
    verdict: ValidationVerdict = ValidationVerdict.PASS,
) -> ValidationReport:
    """A validation that checked *section_ids* and reached *verdict*."""
    severity = Severity.ERROR if verdict is ValidationVerdict.FAIL else Severity.INFO
    findings = tuple(
        ValidationFinding(
            finding_id=f"f-{index}",
            severity=severity,
            target_section_id=section_id,
            message=f"Section {section_id} was checked against the ledger of this run.",
        )
        for index, section_id in enumerate(section_ids, start=1)
    )
    return ValidationReport(
        task_id=task_id,
        findings=findings,
        checked_sections=section_ids,
        verdict=verdict,
        derived_from=upstream,
    )


def build_delivery(
    upstream: tuple[str, ...],
    *,
    task_id: str = "task",
    draft_digest: str,
    verdict: ValidationVerdict = ValidationVerdict.PASS,
) -> DeliveredReport:
    """A delivery naming an explicit draft digest and verdict."""
    return DeliveredReport(
        task_id=task_id,
        draft_digest=draft_digest,
        validation_verdict=verdict,
        manifest=(DeliveredManifestEntry(relative_path="report.md", content_sha256="b" * 64),),
        derived_from=upstream,
    )


# ---------------------------------------------------------------------------
# Honest handlers. Each reads its declared inputs and nothing else — no side
# channel, no module state, because a handler that needed one would be a handler
# whose output the ledger could not account for.
# ---------------------------------------------------------------------------


def intake_handler(context: StageContext) -> ResearchObjective:
    """Never called.

    ``intake`` is the root: :meth:`Orchestrator.run` records the objective the
    caller supplies and skips the stage. The entry exists only so the handler
    table is complete, and it fails loudly rather than quietly if that ever
    changes.
    """
    raise AssertionError("intake has no handler; run() records the objective and skips the stage")


def inventory_handler(context: StageContext) -> SourceInventory:
    """Reproduce exactly the materials intake declared."""
    objective = context.inputs[ArtifactKind.RESEARCH_OBJECTIVE]
    assert isinstance(objective, ResearchObjective)
    return SourceInventory(
        task_id=context.task_id,
        materials=tuple(
            InventoryMaterial(
                display_name=material.display_name,
                content_sha256=material.content_sha256,
                size_bytes=material.size_bytes,
                readable=True,
            )
            for material in objective.declared_materials
        ),
        anchors=tuple(
            make_anchor(f"a-{index}", material.content_sha256)
            for index, material in enumerate(objective.declared_materials, start=1)
        ),
        derived_from=context.upstream.digests(),
    )


def retrieve_handler(context: StageContext) -> RetrievedExcerpts:
    """Anchor every excerpt in an anchor the inventory actually emitted."""
    inventory = context.inputs[ArtifactKind.SOURCE_INVENTORY]
    assert isinstance(inventory, SourceInventory)
    known = inventory.anchor_index()
    return RetrievedExcerpts(
        task_id=context.task_id,
        excerpts=tuple(
            RetrievedExcerpt(
                anchor_id=anchor_id,
                material_sha256=material_sha,
                rank=rank,
                excerpt=f"Passage {rank} was retrieved in full from anchor {anchor_id}.",
                retrieval_method="fts5 lexical over normalised excerpts",
            )
            for rank, (anchor_id, material_sha) in enumerate(known.items(), start=1)
        ),
        derived_from=context.upstream.digests(),
    )


def evidence_handler(context: StageContext) -> EvidenceLedgerView:
    """One claim per retrieved excerpt, anchored in what retrieval returned."""
    excerpts = context.inputs[ArtifactKind.RETRIEVED_EXCERPTS]
    assert isinstance(excerpts, RetrievedExcerpts)
    return EvidenceLedgerView(
        task_id=context.task_id,
        claims=tuple(
            EvidenceClaim(
                claim_id=f"c-{index}",
                statement=(
                    f"The bound material states the quantity recorded in passage "
                    f"{excerpt.rank} of anchor {excerpt.anchor_id}."
                ),
                anchor_refs=(
                    AnchorRef(anchor_id=excerpt.anchor_id, material_sha256=excerpt.material_sha256),
                ),
                status=VerificationStatus.EXTRACTED,
            )
            for index, excerpt in enumerate(excerpts.excerpts, start=1)
        ),
        derived_from=context.upstream.digests(),
    )


def propose_handler(context: StageContext) -> ResearchProposal:
    """A routine proposal citing every claim the ledger admitted."""
    ledger = context.inputs[ArtifactKind.EVIDENCE_LEDGER]
    assert isinstance(ledger, EvidenceLedgerView)
    return ResearchProposal(
        task_id=context.task_id,
        direction="Report the located quantities without extending beyond them.",
        items=(
            ProposalItem(
                item_id="p-1",
                statement="Lead with the first located quantity as the headline figure.",
                materiality=Materiality.ROUTINE,
                rationale="It is the highest-ranked passage the retriever returned.",
                evidence_refs=ledger.claim_ids(),
            ),
        ),
        derived_from=context.upstream.digests(),
    )


def draft_handler(context: StageContext) -> ReportDraft:
    """One section per claim, each citing that claim."""
    ledger = context.inputs[ArtifactKind.EVIDENCE_LEDGER]
    assert isinstance(ledger, EvidenceLedgerView)
    return ReportDraft(
        task_id=context.task_id,
        sections=tuple(
            DraftSection(
                section_id=f"s-{claim.claim_id}",
                heading=f"Finding from {claim.claim_id}",
                body=f"The located passage states: {claim.statement}",
                evidence_refs=(claim.claim_id,),
            )
            for claim in ledger.claims
        ),
        derived_from=context.upstream.digests(),
    )


def validate_handler(context: StageContext) -> ValidationReport:
    """Check every section the draft actually contains."""
    draft = context.inputs[ArtifactKind.REPORT_DRAFT]
    assert isinstance(draft, ReportDraft)
    return ValidationReport(
        task_id=context.task_id,
        findings=(
            ValidationFinding(
                finding_id="f-1",
                severity=Severity.INFO,
                target_section_id=draft.sections[0].section_id,
                message="Every section cites at least one located claim from this run.",
            ),
        ),
        checked_sections=draft.section_ids(),
        verdict=ValidationVerdict.PASS,
        derived_from=context.upstream.digests(),
    )


def deliver_handler(context: StageContext) -> DeliveredReport:
    """Name the draft this run produced and the verdict validation reached."""
    draft_entry = context.upstream.entry(ArtifactKind.REPORT_DRAFT)
    validation = context.inputs[ArtifactKind.VALIDATION_REPORT]
    assert isinstance(validation, ValidationReport)
    return DeliveredReport(
        task_id=context.task_id,
        draft_digest=draft_entry.digest,
        validation_verdict=validation.verdict,
        manifest=(DeliveredManifestEntry(relative_path="report.md", content_sha256="c" * 64),),
        derived_from=context.upstream.digests(),
    )


HANDLERS = {
    StageName.INTAKE: intake_handler,
    StageName.INVENTORY: inventory_handler,
    StageName.RETRIEVE: retrieve_handler,
    StageName.EVIDENCE: evidence_handler,
    StageName.PROPOSE: propose_handler,
    StageName.DRAFT: draft_handler,
    StageName.VALIDATE: validate_handler,
    StageName.DELIVER: deliver_handler,
}


def make_orchestrator(
    handlers: dict[StageName, object] | None = None,
    *,
    task_id: TaskId | None = None,
    run_id: RunId | None = None,
    declaration: SkillDeclaration = RESEARCH_REPORT,
) -> Orchestrator:
    """An orchestrator over the declared skill, with the honest handler set.

    *handlers* replaces entries in :data:`HANDLERS`, which is how a test
    substitutes one stage with a misbehaving body without rebuilding the other
    seven. *declaration* replaces the graph itself, which is how a test exercises
    a different budget.
    """
    merged = {**HANDLERS, **(handlers or {})}
    return Orchestrator(
        declaration,
        merged,  # type: ignore[arg-type]
        task_id=task_id or make_task_id(),
        run_id=run_id or make_run_id(),
        clock=fixed_clock,
    )


def grant_approval(
    proposal: ResearchProposal,
    proposal_digest: str,
    *,
    task_id: str,
    item_ids: tuple[str, ...] | None = None,
    goal_change_ids: tuple[str, ...] | None = None,
    granted_at: datetime = SKILL_NOW,
    expires_at: datetime | None = None,
    granted_by: str = "the researcher",
) -> ApprovalDecision:
    """An approval covering the proposal's own significant items.

    Defaults to covering everything the gate would demand, so a test that is not
    about coverage does not have to restate it. Pass ``item_ids=()`` explicitly
    to build a decision that covers nothing.
    """
    if item_ids is None:
        resolved_items_ids = tuple(item.item_id for item in proposal.significant_items())
    else:
        resolved_items_ids = tuple(item_ids)
    resolved_changes = (
        tuple(change.change_id for change in proposal.goal_changes)
        if goal_change_ids is None
        else goal_change_ids
    )
    return ApprovalDecision(
        decision_id="d-1",
        task_id=task_id,
        approved_proposal_digest=proposal_digest,
        covered_item_ids=resolved_items_ids or ("p-unused",),
        covered_goal_change_ids=resolved_changes,
        granted_by=granted_by,
        granted_at=granted_at,
        expires_at=expires_at or (granted_at + timedelta(hours=4)),
    )


__all__ = [
    "DATA_SHA",
    "DEFAULT_CRITERION",
    "DEFAULT_OBJECTIVE",
    "FOREIGN_ANCHOR",
    "FOREIGN_SHA",
    "HANDLERS",
    "PAPER_SHA",
    "SKILL_NOW",
    "StageBlockedError",
    "build_delivery",
    "build_draft",
    "build_inventory",
    "build_ledger",
    "build_proposal",
    "build_retrieved",
    "build_validation",
    "deliver_handler",
    "draft_handler",
    "evidence_handler",
    "fixed_clock",
    "grant_approval",
    "inventory_handler",
    "later_clock",
    "make_anchor",
    "make_objective",
    "make_orchestrator",
    "make_run_id",
    "make_task_id",
    "propose_handler",
    "retrieve_handler",
    "validate_handler",
]
