"""``research-report`` — the declared first-party skill and its supervision.

This package owns the **contract and the orchestration**, and nothing else. The
science is not here: material parsing is LC-P1-08, retrieval LC-P1-09, evidence
checking and analysis LC-P1-09/10, report rendering LC-P1-11. What is here is
the set of rules that make a result checkable, expressed once:

:mod:`~labcairn.skills.artifacts`
    Typed artifacts and the ``derived_from`` field that makes them a lineage.
:mod:`~labcairn.skills.quality`
    What counts as a placeholder, and the reference-closure rules per stage.
:mod:`~labcairn.skills.ledger`
    Digests, provenance at write time, integrity at read time.
:mod:`~labcairn.skills.declaration`
    The stage graph, its typed ports and its dependency edges, as data.
:mod:`~labcairn.skills.approval`
    The checkpoint between ``propose`` and ``draft``.
:mod:`~labcairn.skills.plan`
    A derived, disposable plan — never a second source of truth.
:mod:`~labcairn.skills.execution`
    The orchestrator that runs the graph and refuses what fails.

Recovery, resume and reconciliation are **not** here — LC-P1-06 owns them. What
this package emits for that purpose is a :class:`~labcairn.skills.execution.StageCheckpoint`
per stage boundary: data about what was true, with no opinion about what may be
done with it.
"""

from __future__ import annotations

from labcairn.skills.approval import (
    ApprovalDecision,
    ApprovalGate,
    GateVerdict,
    gate_request,
    require_approval,
)
from labcairn.skills.artifacts import (
    ARTIFACT_TYPES,
    AnchorRef,
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
    ProposalItem,
    ReportDraft,
    ResearchObjective,
    ResearchProposal,
    RetrievedExcerpt,
    RetrievedExcerpts,
    Severity,
    SourceInventory,
    StageName,
    ValidationFinding,
    ValidationReport,
    ValidationVerdict,
    artifact_type,
)
from labcairn.skills.declaration import (
    DEFAULT_BUDGET,
    RESEARCH_REPORT_SKILL_ID,
    SkillDeclaration,
    StageBudget,
    StageSpec,
    research_report_skill,
)
from labcairn.skills.errors import (
    ApprovalRequiredError,
    ArtifactSubstitutedError,
    ArtifactTypeError,
    DerivationClosureError,
    LineageError,
    PlaceholderError,
    SkillBudgetError,
    SkillDeclarationError,
    SkillError,
    StageContractError,
    StaleApprovalError,
)
from labcairn.skills.execution import (
    BudgetView,
    Orchestrator,
    RunControl,
    RunOutcome,
    StageBlockedError,
    StageCheckpoint,
    StageContext,
    StageFailedError,
    StageHandler,
    WorkflowStop,
)
from labcairn.skills.ledger import (
    ArtifactLedger,
    RecordedArtifact,
    artifact_digest,
)
from labcairn.skills.plan import PlanStep, ResearchPlan, build_plan, rebuild_plan
from labcairn.skills.quality import (
    Upstream,
    UpstreamArtifact,
    require_closure,
    require_substance,
)

#: The declared skill, ready to hand to :class:`~labcairn.skills.execution.Orchestrator`
#: once stage bodies are supplied. A module-level instance so that two callers
#: passing the same skill really do get the same graph — and so the skill digest
#: quoted in a plan has one referent.
RESEARCH_REPORT: SkillDeclaration = research_report_skill()

__all__ = [
    "ARTIFACT_TYPES",
    "DEFAULT_BUDGET",
    "RESEARCH_REPORT",
    "RESEARCH_REPORT_SKILL_ID",
    "AnchorRef",
    "ApprovalDecision",
    "ApprovalGate",
    "ApprovalRequiredError",
    "ArtifactKind",
    "ArtifactLedger",
    "ArtifactSubstitutedError",
    "ArtifactTypeError",
    "BudgetView",
    "DeclaredMaterial",
    "DeliveredManifestEntry",
    "DeliveredReport",
    "DerivationClosureError",
    "DraftSection",
    "EvidenceClaim",
    "EvidenceLedgerView",
    "GateVerdict",
    "GoalChange",
    "InventoryAnchor",
    "InventoryMaterial",
    "LineageError",
    "Materiality",
    "Orchestrator",
    "PlaceholderError",
    "PlanStep",
    "ProposalItem",
    "RecordedArtifact",
    "ReportDraft",
    "ResearchObjective",
    "ResearchPlan",
    "ResearchProposal",
    "RetrievedExcerpt",
    "RetrievedExcerpts",
    "RunControl",
    "RunOutcome",
    "Severity",
    "SkillBudgetError",
    "SkillDeclaration",
    "SkillDeclarationError",
    "SkillError",
    "SourceInventory",
    "StageBlockedError",
    "StageBudget",
    "StageCheckpoint",
    "StageContext",
    "StageContractError",
    "StageFailedError",
    "StageHandler",
    "StageName",
    "StageSpec",
    "StaleApprovalError",
    "Upstream",
    "UpstreamArtifact",
    "ValidationFinding",
    "ValidationReport",
    "ValidationVerdict",
    "WorkflowStop",
    "artifact_digest",
    "artifact_type",
    "build_plan",
    "gate_request",
    "rebuild_plan",
    "require_approval",
    "require_closure",
    "require_substance",
    "research_report_skill",
]
