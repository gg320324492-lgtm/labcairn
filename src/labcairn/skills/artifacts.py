"""The typed artifacts that cross a stage boundary, and the one field that
makes them a lineage rather than a stack of objects.

What this module is, and is not
-------------------------------
These are **contracts**, not implementations. LC-P1-07 owns the shape a stage's
output must have so the orchestrator can verify it; it does not own the science.
Material parsing is LC-P1-08, retrieval is LC-P1-09, evidence checking and
analysis are LC-P1-09/10, report rendering is LC-P1-11. Nothing here parses a
PDF, matches a quotation or renders a figure, and nothing here should be read as
a claim that any of those work.

Why every artifact carries ``derived_from``
-------------------------------------------
The acceptance rule is *"every stage consumes actual previous artifacts"*. The
obvious implementation — check that the input argument is not ``None`` — is
satisfied by a stage that receives ``{}`` and does nothing, so it proves nothing.
This module instead makes lineage a **required, typed field** on every artifact
except the root:

* the orchestrator hands a stage exactly the artifacts its declaration names,
  and computes their digests;
* the stage must write those digests, in order, into its output's
  ``derived_from``;
* the orchestrator compares the two and refuses on any difference.

The three properties fall out of that and are not separately bolted on. A stage
that ignores an input cannot name its digest. An artifact built from a different
run's inputs names digests that were not handed to it. And an artifact a caller
wants to inject after the fact must lie about its ancestors, which the
orchestrator can check because it knows what it actually handed over.

``derived_from`` participates in the artifact's own digest
----------------------------------------------------------
A canonical digest is taken over the whole canonical payload, ``derived_from``
included. That makes the lineage self-describing: two runs that produced the
same content from different inputs are *different artifacts*, which is the point
—"this claim rests on these bytes" is part of what the claim is.

What the type system buys
-------------------------
:class:`AnchorRef` and :class:`~labcairn.evidence.states.VerificationStatus`
are imported rather than redefined. The evidence vocabulary is ADR-0004's and is
frozen; a skill that spelled its own would be free to drift from the ledger it
is supposed to describe, and a skill that passes a string where a
``VerificationStatus`` belongs is caught by the checker rather than by a run
that fails much later.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, field_validator, model_validator

from labcairn.core.primitives import StrictPosInt
from labcairn.core.schema import LabCairnModel
from labcairn.evidence.states import VerificationStatus
from labcairn.sources.primitives import ContentHash, NonEmptyText


#: One stage of the research-report skill. Closed — the phase sequence in
#: ``docs/ARCHITECTURE.md`` "Stage workflow (Phase 1)" is a specification, and a
#: stage name that is not in this set is a typo rather than a variant.
class StageName(StrEnum):
    INTAKE = "intake"
    INVENTORY = "inventory"
    RETRIEVE = "retrieve"
    EVIDENCE = "evidence"
    PROPOSE = "propose"
    DRAFT = "draft"
    VALIDATE = "validate"
    DELIVER = "deliver"


class ArtifactKind(StrEnum):
    """What an artifact *is*, independent of the stage that made it.

    The kind is the port name. A stage declares which kinds it consumes and
    which it produces, and :data:`ARTIFACT_TYPES` maps each kind to exactly one
    model, so "port ``evidence_ledger`` receives something else" is a type error
    rather than an ``AttributeError`` three stages later.
    """

    RESEARCH_OBJECTIVE = "research_objective"
    SOURCE_INVENTORY = "source_inventory"
    RETRIEVED_EXCERPTS = "retrieved_excerpts"
    EVIDENCE_LEDGER = "evidence_ledger"
    RESEARCH_PROPOSAL = "research_proposal"
    REPORT_DRAFT = "report_draft"
    VALIDATION_REPORT = "validation_report"
    DELIVERED_REPORT = "delivered_report"


class Materiality(StrEnum):
    """How much of a human's attention a proposal item deserves.

    The two upper members are what make the approval checkpoint *required*
    rather than advisory, and the boundary is drawn where the ADR-0004 lineage
    stops being able to answer the question by itself: a claim's support can be
    checked, but whether the report should be *going in this direction at all* is
    a scientific judgement that no C1-C3 verdict covers — the same reason C4 is
    permanently ``not_checked``.
    """

    #: Implementation detail inside an already-approved direction.
    ROUTINE = "routine"
    #: A finding that steers the research; supported, but the choice of where to
    #: follow it is the researcher's.
    IMPORTANT_SCIENTIFIC_DIRECTION = "important_scientific_direction"
    #: Changes the objective, the success criterion, or a claim the report will
    #: stand behind. Never auto-approved, regardless of evidence support.
    MAJOR_GOAL_OR_CLAIM_CHANGE = "major_goal_or_claim_change"

    @property
    def requires_approval(self) -> bool:
        """Whether :class:`~labcairn.skills.approval.ApprovalGate` must have a grant.

        A property rather than a set lookup so that adding a member without
        deciding its approval semantics is not possible to do quietly: the
        ``else`` below makes the missing case a runtime failure.
        """
        if self is Materiality.ROUTINE:
            return False
        if self in (
            Materiality.IMPORTANT_SCIENTIFIC_DIRECTION,
            Materiality.MAJOR_GOAL_OR_CLAIM_CHANGE,
        ):
            return True
        raise AssertionError(f"unhandled materiality: {self!r}")


class _Lineage(LabCairnModel):
    """Shared ``derived_from`` field and its rule.

    Every artifact inherits this. The root artifact overrides the minimum to 0,
    because it is the one artifact with no ancestor; everything else must name
    at least one, because an artifact that descends from nothing has not been
    built from this run's work.
    """

    #: Canonical sha256 digests of the artifacts this one was built from, in the
    #: order the orchestrator handed them over. Filled in by the **stage**, and
    #: verified against the orchestrator's own record by
    #: :mod:`labcairn.skills.execution`.
    derived_from: Annotated[tuple[ContentHash, ...], Field(min_length=1)]


class _RootLineage(LabCairnModel):
    """Lineage for the root artifact, which legitimately has no ancestor."""

    derived_from: tuple[ContentHash, ...] = ()


# ---------------------------------------------------------------------------
# intake
# ---------------------------------------------------------------------------


class DeclaredMaterial(LabCairnModel):
    """One material the researcher says the task is about, bound by content.

    ``content_sha256`` rather than a path, for the reason
    :class:`~labcairn.runtime.lifecycle.Task` gives for ``bound_source_ids``: a
    path moves, and binding by path is how a task ends up describing a different
    file than it started with.
    """

    display_name: NonEmptyText
    content_sha256: ContentHash
    size_bytes: Annotated[int, Field(strict=True, ge=0)]


class ResearchObjective(_RootLineage):
    """``intake`` output: what the researcher wants established, and over what.

    The root of the lineage. ``derived_from`` is empty and stays empty — this is
    the one artifact the run starts from, and its authority is the person who
    typed the objective, not any upstream stage.
    """

    task_id: NonEmptyText
    objective: NonEmptyText
    success_criterion: NonEmptyText
    declared_materials: Annotated[tuple[DeclaredMaterial, ...], Field(min_length=1)]

    @field_validator("declared_materials")
    @classmethod
    def _materials_are_unique_by_content(
        cls, value: tuple[DeclaredMaterial, ...]
    ) -> tuple[DeclaredMaterial, ...]:
        """Two rows for one file is one material.

        Compared by content hash, not by name: the same paper arriving as
        ``paper.pdf`` and ``paper (1).pdf`` is one input, and a report that
        counts it twice overstates what was consulted.
        """
        seen: set[str] = set()
        for material in value:
            if material.content_sha256 in seen:
                raise ValueError(
                    f"duplicate material: {material.display_name!r} hashes to "
                    f"{material.content_sha256}, which is already declared. One file "
                    f"listed twice reads as two independent inputs when it is one."
                )
            seen.add(material.content_sha256)
        return value

    def content_hashes(self) -> tuple[str, ...]:
        """The declared material hashes, sorted — the set ``inventory`` must reproduce."""
        return tuple(sorted(m.content_sha256 for m in self.declared_materials))


# ---------------------------------------------------------------------------
# inventory
# ---------------------------------------------------------------------------


class InventoryMaterial(LabCairnModel):
    """One material as actually found, readable or not.

    ``note`` is paired with ``readable=False`` the same way
    :class:`~labcairn.sources.source.Source` pairs
    ``readability_disclosure`` with ``UNREADABLE_NO_OCR``: an unreadable asset
    that carries no note is a silent gap, and "we could not look" is not "there
    was nothing there".
    """

    display_name: NonEmptyText
    content_sha256: ContentHash
    size_bytes: Annotated[int, Field(strict=True, ge=0)]
    readable: bool
    note: NonEmptyText | None = None

    @model_validator(mode="after")
    def _unreadable_materials_explain_themselves(self) -> Self:
        if not self.readable and self.note is None:
            raise ValueError(
                f"material {self.display_name!r} is recorded as unreadable and "
                f"carries no note. A material we could not read is a recorded "
                f"absence with a reason attached; without the reason a reader "
                f"cannot tell a failed ingest from a file that was never there."
            )
        if self.readable and self.note is not None:
            raise ValueError(
                f"material {self.display_name!r} is readable and carries the note "
                f"{self.note!r}. A caveat attached to a material that parsed is a "
                f"claim about something that did not happen."
            )
        return self


class InventoryAnchor(LabCairnModel):
    """One addressable place inside an inventoried material.

    Carries the material's content hash as well as its own id, so a downstream
    stage that cites an anchor is citing *a hash it read the inventory for*, not
    just a string that happens to look like an id. An id is forgeable; an id plus
    the hash it was minted against is a claim about a specific pair of bytes.
    """

    anchor_id: NonEmptyText
    material_sha256: ContentHash
    locator_description: NonEmptyText


class SourceInventory(_Lineage):
    """``inventory`` output: what material exists, and where inside it one can look.

    Non-empty on both collections, and that is not a formality — a stage that
    returns an inventory with no materials has found nothing and should say so
    as a finding, not as an empty object that downstream stages would happily
    treat as "the work is done, there was simply nothing".

    :attr:`materials` must reproduce :attr:`ResearchObjective.content_hashes`
    exactly. That equality is checked by the orchestrator, not by this model,
    because it needs the previous artifact to compare against.
    """

    task_id: NonEmptyText
    materials: Annotated[tuple[InventoryMaterial, ...], Field(min_length=1)]
    anchors: Annotated[tuple[InventoryAnchor, ...], Field(min_length=1)]

    def anchor_index(self) -> dict[str, str]:
        """``anchor_id -> material_sha256``, for downstream reference checks."""
        return {anchor.anchor_id: anchor.material_sha256 for anchor in self.anchors}

    def material_hashes(self) -> tuple[str, ...]:
        """The inventoried material hashes, sorted — compared against ``intake``."""
        return tuple(sorted(m.content_sha256 for m in self.materials))


# ---------------------------------------------------------------------------
# retrieve
# ---------------------------------------------------------------------------


class RetrievedExcerpt(LabCairnModel):
    """One passage the retriever surfaced, bound to the anchor it came from.

    ``rank`` is 1-based and unique within the set (enforced below), so "the third
    hit" is an addressable thing and two hits cannot both claim to be it.
    """

    anchor_id: NonEmptyText
    material_sha256: ContentHash
    rank: StrictPosInt
    excerpt: NonEmptyText
    retrieval_method: NonEmptyText


class RetrievedExcerpts(_Lineage):
    """``retrieve`` output: passages, each bound to an inventory anchor.

    Every excerpt must name an anchor that ``inventory`` actually emitted with
    the same material hash. Checked by the orchestrator — the model cannot see
    the inventory — and that check is what makes "the retrieval stage consumed
    the inventory" a fact about content rather than about an argument being
    present.
    """

    task_id: NonEmptyText
    excerpts: Annotated[tuple[RetrievedExcerpt, ...], Field(min_length=1)]

    @field_validator("excerpts")
    @classmethod
    def _ranks_are_unique(cls, value: tuple[RetrievedExcerpt, ...]) -> tuple[RetrievedExcerpt, ...]:
        ranks = [excerpt.rank for excerpt in value]
        if len(set(ranks)) != len(ranks):
            raise ValueError(
                f"duplicate rank in {sorted(ranks)}. Rank is a position in the "
                f"result order; two passages claiming the same position make "
                f"'which one was better' unanswerable."
            )
        return value

    def excerpt_index(self) -> dict[str, str]:
        """``anchor_id -> material_sha256``, restricted to anchors actually retrieved."""
        return {excerpt.anchor_id: excerpt.material_sha256 for excerpt in self.excerpts}


# ---------------------------------------------------------------------------
# evidence
# ---------------------------------------------------------------------------


class AnchorRef(LabCairnModel):
    """A citation: which anchor, and which bytes of which material."""

    anchor_id: NonEmptyText
    material_sha256: ContentHash


class EvidenceClaim(LabCairnModel):
    """One claim with the anchors that locate it.

    ``status`` is ADR-0004's :class:`~labcairn.evidence.states.VerificationStatus`,
    imported. The skill does not get to have its own opinion about what counts
    as verified — a workflow that could mark a claim ``verified_by_rule`` by
    assertion would be a way around the ledger entirely.

    ``status != planned`` requires at least one anchor. That mirrors
    :meth:`~labcairn.evidence.record.EvidenceRecord._is_located`: a claim that
    claims to have been checked against nothing is the placeholder this whole
    acceptance rule is about.
    """

    claim_id: NonEmptyText
    statement: NonEmptyText
    anchor_refs: tuple[AnchorRef, ...] = ()
    status: VerificationStatus = VerificationStatus.PLANNED
    note: NonEmptyText | None = None

    @model_validator(mode="after")
    def _a_non_planned_claim_is_located(self) -> Self:
        if self.status is not VerificationStatus.PLANNED and not self.anchor_refs:
            raise ValueError(
                f"claim {self.claim_id!r} has status="
                f"{self.status.value!r} and cites no anchor. A claim that reports "
                f"it was checked, against nothing, is the failure mode ADR-0004's "
                f"state machine exists to make impossible."
            )
        if len({ref.anchor_id for ref in self.anchor_refs}) != len(self.anchor_refs):
            raise ValueError(
                f"claim {self.claim_id!r} cites the same anchor more than once. One "
                f"address cited twice is one anchor; two rows for it make 'how many "
                f"sources back this' answerable two ways."
            )
        return self


class EvidenceLedgerView(_Lineage):
    """``evidence`` output: the claims this run will be allowed to stand behind.

    A **view**, deliberately named as one. It is not
    :class:`~labcairn.evidence.record.EvidenceRecord` and does not replace it:
    the authoritative ledger lives in the frozen store at LC-P1-05/09. This is
    the slice of it a stage is *handed*, so that a draft stage cannot read
    claims that were never admitted into this run's view.
    """

    task_id: NonEmptyText
    claims: Annotated[tuple[EvidenceClaim, ...], Field(min_length=1)]

    def claim_ids(self) -> tuple[str, ...]:
        """The ids this view admits, for downstream reference-closure checks."""
        return tuple(claim.claim_id for claim in self.claims)

    @field_validator("claims")
    @classmethod
    def _claim_ids_are_unique(cls, value: tuple[EvidenceClaim, ...]) -> tuple[EvidenceClaim, ...]:
        ids = [claim.claim_id for claim in value]
        if len(set(ids)) != len(ids):
            raise ValueError(
                f"duplicate claim_id in {sorted(ids)}. Two claims sharing an id make "
                f"every downstream citation of that id ambiguous, and a report that "
                f"cites one of them is citing a coin toss."
            )
        return value


# ---------------------------------------------------------------------------
# propose
# ---------------------------------------------------------------------------


class ProposalItem(LabCairnModel):
    """One thing the run proposes to do, and how significant it is.

    ``materiality`` is set **by the stage**, and the approval gate reads it
    rather than deciding significance itself: the gate's job is to enforce the
    rule, and a gate that also decides which items are important can be tuned
    into agreeing with whatever the run wanted to do.
    """

    item_id: NonEmptyText
    statement: NonEmptyText
    materiality: Materiality
    rationale: NonEmptyText
    evidence_refs: tuple[NonEmptyText, ...] = ()


class GoalChange(LabCairnModel):
    """A proposed change to the objective or the success criterion.

    Always significant. Editing the thing a run is judged against is the largest
    change available, and it is exactly the change a user approves without
    reading carefully because the run asked for it.
    """

    change_id: NonEmptyText
    target: Annotated[str, Field(pattern=r"^(objective|success_criterion)$")]
    old_value: NonEmptyText
    new_value: NonEmptyText
    reason: NonEmptyText

    @model_validator(mode="after")
    def _a_change_changes_something(self) -> Self:
        if self.old_value.strip() == self.new_value.strip():
            raise ValueError(
                f"goal change {self.change_id!r} sets {self.target!r} to the value it "
                f"already had. A no-op change that still consumes an approval trains "
                f"people to approve the form without reading the content."
            )
        return self


class ResearchProposal(_Lineage):
    """``propose`` output: the scientific direction, and what it rests on."""

    task_id: NonEmptyText
    direction: NonEmptyText
    items: Annotated[tuple[ProposalItem, ...], Field(min_length=1)]
    goal_changes: tuple[GoalChange, ...] = ()

    def significant_items(self) -> tuple[ProposalItem, ...]:
        """Items the approval gate must cover, in declaration order."""
        return tuple(item for item in self.items if item.materiality.requires_approval)

    @field_validator("items")
    @classmethod
    def _item_ids_are_unique(cls, value: tuple[ProposalItem, ...]) -> tuple[ProposalItem, ...]:
        ids = [item.item_id for item in value]
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate proposal item_id in {sorted(ids)}")
        return value


# ---------------------------------------------------------------------------
# draft / validate / deliver
# ---------------------------------------------------------------------------


class DraftSection(LabCairnModel):
    """One section of the draft, with the claims it rests on.

    ``evidence_refs`` is **required to be non-empty**. A section that asserts
    something and cites nothing is the single most common shape of a hollow
    report, and making it unrepresentable is cheaper than detecting it later.
    """

    section_id: NonEmptyText
    heading: NonEmptyText
    body: NonEmptyText
    evidence_refs: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)]


class ReportDraft(_Lineage):
    """``draft`` output. Reachable only through an approval the gate accepts."""

    task_id: NonEmptyText
    sections: Annotated[tuple[DraftSection, ...], Field(min_length=1)]

    def section_ids(self) -> tuple[str, ...]:
        """The ids this draft contains, for the validator's closure check."""
        return tuple(section.section_id for section in self.sections)

    @field_validator("sections")
    @classmethod
    def _section_ids_are_unique(cls, value: tuple[DraftSection, ...]) -> tuple[DraftSection, ...]:
        ids = [section.section_id for section in value]
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate draft section_id in {sorted(ids)}")
        return value


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    #: The only severity that can fail a run. ``WARNING`` is a note to the
    #: reader, not a stop.
    ERROR = "error"


class ValidationFinding(LabCairnModel):
    """One thing validation noticed about one section."""

    finding_id: NonEmptyText
    severity: Severity
    target_section_id: NonEmptyText
    message: NonEmptyText


class ValidationVerdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"


class ValidationReport(_Lineage):
    """``validate`` output: a verdict, and the findings behind it.

    ``checked_sections`` must cover every section of the draft. A validation
    report that passed three of five sections has not validated the draft, and
    the verdict it carries says nothing about the two it skipped; the closure
    check makes that unrepresentable rather than merely discouraged.
    """

    task_id: NonEmptyText
    findings: Annotated[tuple[ValidationFinding, ...], Field(min_length=1)]
    checked_sections: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)]
    verdict: ValidationVerdict

    @model_validator(mode="after")
    def _the_verdict_follows_from_the_findings(self) -> Self:
        """A ``pass`` with an error finding is not a pass, and vice versa."""
        errors = [f for f in self.findings if f.severity is Severity.ERROR]
        if errors and self.verdict is not ValidationVerdict.FAIL:
            raise ValueError(
                f"verdict={self.verdict.value!r} with {len(errors)} error finding(s): "
                f"{[f.finding_id for f in errors]}. The verdict is not a separate "
                f"judgement from the findings — allowing them to disagree is how a "
                f"failed validation reports success."
            )
        if not errors and self.verdict is not ValidationVerdict.PASS:
            raise ValueError(
                f"verdict={self.verdict.value!r} with no error finding. A failure "
                f"nobody can name is not a finding; either record what failed or "
                f"pass the run."
            )
        return self


class DeliveredManifestEntry(LabCairnModel):
    """One file the delivery claims to contain."""

    relative_path: NonEmptyText
    content_sha256: ContentHash


class DeliveredReport(_Lineage):
    """``deliver`` output: the deliverable and what it was made from.

    ``draft_digest`` is not decorative bookkeeping. The orchestrator compares it
    against the digest of the draft artifact it actually handed in, so a
    delivery that names a different draft is refused — that is the last point at
    which "this report is about the thing we verified" can still be checked,
    because after this the report is an opaque set of bytes.
    """

    task_id: NonEmptyText
    draft_digest: ContentHash
    validation_verdict: ValidationVerdict
    manifest: Annotated[tuple[DeliveredManifestEntry, ...], Field(min_length=1)]


#: Port name to model. The single place a stage's declared output type is
#: looked up, so "which type is ``evidence_ledger``" has one answer.
ARTIFACT_TYPES: dict[ArtifactKind, type[LabCairnModel]] = {
    ArtifactKind.RESEARCH_OBJECTIVE: ResearchObjective,
    ArtifactKind.SOURCE_INVENTORY: SourceInventory,
    ArtifactKind.RETRIEVED_EXCERPTS: RetrievedExcerpts,
    ArtifactKind.EVIDENCE_LEDGER: EvidenceLedgerView,
    ArtifactKind.RESEARCH_PROPOSAL: ResearchProposal,
    ArtifactKind.REPORT_DRAFT: ReportDraft,
    ArtifactKind.VALIDATION_REPORT: ValidationReport,
    ArtifactKind.DELIVERED_REPORT: DeliveredReport,
}


def artifact_type(kind: ArtifactKind) -> type[LabCairnModel]:
    """The model for *kind*. One lookup; callers do not index the dict directly."""
    return ARTIFACT_TYPES[kind]


__all__ = [
    "ARTIFACT_TYPES",
    "AnchorRef",
    "ArtifactKind",
    "DeclaredMaterial",
    "DeliveredManifestEntry",
    "DeliveredReport",
    "DraftSection",
    "EvidenceClaim",
    "EvidenceLedgerView",
    "GoalChange",
    "InventoryAnchor",
    "InventoryMaterial",
    "Materiality",
    "ProposalItem",
    "ReportDraft",
    "ResearchObjective",
    "ResearchProposal",
    "RetrievedExcerpt",
    "RetrievedExcerpts",
    "Severity",
    "SourceInventory",
    "StageName",
    "ValidationFinding",
    "ValidationReport",
    "ValidationVerdict",
    "artifact_type",
]
