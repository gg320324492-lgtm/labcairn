"""The comment-to-revision binding: opinion, approved edit, response, receipt.

**What this module is.** LC-P3-04's deliverable is not any of its parts — the
feedback chain's rows (:mod:`labcairn.papers.feedback`,
:mod:`labcairn.papers.edits`, :mod:`labcairn.papers.responses`), the edit seam
(:mod:`labcairn.editing.drafts`) and the revision loop
(:mod:`labcairn.application.revision_loop`) all existed before this module.
What did not exist is **one loop that binds them**: an opinion is located or
explicitly marked as a location failure, a model suggestion is put forward as
a separate record from the person's confirmation, the approved edits go
through the seam onto the loop's copies, the drafts are published under
receipts, the output version is registered with its edge, and the chain's
rings are filled from the published bytes — with the opinions that need
evidence or sit at an uncertain location left **unresolved as explicit
tasks**, named in the dossier rather than dropped.

The binding's five effects, and what each one is
-----------------------------------------------

* **open** imports the original through LC-P3-03's loop and reads the input
  version's comments into the chain (:func:`open_binding`). The import
  receipt's hash is what every later derivation names, exactly as in 03.
* **locate** classifies every recorded opinion into the states execution
  plan §4 names: located, or an explicit location failure. A comment the
  reader could not anchor is **a location failure with a name**, not a
  silent skip.
* **suggest** takes the injected suggestion source — the substitute model in
  this phase, the real one is LC-P3-08's — and holds what it proposes as
  **separate records** from anything a person says.
* **apply** runs the reviewed-approved suggestions through the edit seam and
  publishes each draft through its own LC-P3-03 loop — one import, one copy,
  one publication, one receipt each — then registers the marked draft as the
  output version, writes the edge from the input version, and fills the
  chain's second and third rings from the published bytes.
* **close** writes the dossier manifest — the four deliverables' shared
  binding to one task, one input version and one output version — as an
  artefact row beside the drafts.

What this module does not do
----------------------------

It does not widen the support matrix: a structure the seam refuses is
**handed to a person** with the refusal's own words (:class:`Handover`), and
the handover is an explicit task in the dossier. It does not call a provider:
the suggestion source is injected. And it does not decide whether the science
is right — the responses it records are process facts, at the grades and by
the deciders :mod:`labcairn.papers.responses` already governs.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Final

from labcairn.application import grant_approval
from labcairn.application.context import ApplicationContext, store_refusals
from labcairn.application.models import Result
from labcairn.application.refusal import (
    ApplicationRefusal,
    ApplicationRefusedError,
    consent_refusal_name,
)
from labcairn.application.revision_loop import (
    COPY_STAGE_NAME,
    PUBLICATION_STAGE_NAME,
    LoopOpened,
    RevisionPublished,
    open_loop,
    publish_revision,
    request_loop_approval,
    stage_copy,
)
from labcairn.core.ids import new_id
from labcairn.db.materials import put_source
from labcairn.db.repository import list_access_grants, load_paper_project
from labcairn.editing.drafts import (
    ApprovedEdit,
    DraftForm,
    EditRefusedError,
    surgical_bytes,
)
from labcairn.material.ingest import ingest_bytes
from labcairn.papers.chain import feedback_row
from labcairn.db.models import EditActionRow
from labcairn.papers.edits import ACTOR_KINDS
from labcairn.papers.feedback import (
    FeedbackEvent,
    event_from_row,
    list_feedback_events,
    record_feedback,
)
from labcairn.papers.responses import (
    AnswerProposal,
    ResponseLink,
    propose_responses,
    record_response,
)
from labcairn.papers.versions import EdgeSource, PaperVersion, VersionEdge, VersionStatus
from labcairn.reports.receipt import (
    ArtifactKind,
    ArtifactProducerKind,
    ArtifactReceipt,
    DerivationRef,
    DerivationTargetKind,
)
from labcairn.security.capabilities import CapabilityId
from labcairn.workspace.outputs import TaskOutputArea
from labcairn.workspace.readonly import SourceMaterial

__all__ = [
    "BINDING_PRODUCER_ID",
    "REVIEW_DECIDER",
    "BindingClosed",
    "BindingOpened",
    "DossierManifest",
    "Handover",
    "LocationState",
    "ModelSuggestion",
    "OpinionBinding",
    "ReviewDecision",
    "ReviewVerdict",
    "UnresolvedOpinion",
    "VERDICT_RESPONSE_STATES",
    "apply_approved_edits",
    "close_binding",
    "open_binding",
]


#: The producer the binding's own receipts name. A receipt whose producer is a
#: bare "tool" names nobody; this names the module that wrote the dossier.
BINDING_PRODUCER_ID: Final[str] = "labcairn.papers.binding"

#: The decider the chain requires for a judgement a person made. The chain's
#: vocabulary has two deciders — ``rule`` and ``user`` — and a person's
#: per-item review is the second.
REVIEW_DECIDER: Final[str] = "user"


class LocationState(StrEnum):
    """Where an opinion sits, in execution plan §4's own vocabulary.

    ``LOCATED`` is the directly-editable case; ``NEEDS_EVIDENCE`` is the case
    a reviewer marks when the opinion asks for an experiment or data the
    manuscript does not carry; ``UNCERTAIN_LOCATION`` is the case the reader
    could not place — an unknown anchor, or a position anchor with no passage
    for the seam to rewrite.
    """

    LOCATED = "located"
    NEEDS_EVIDENCE = "needs_evidence"
    UNCERTAIN_LOCATION = "uncertain_location"


class ReviewVerdict(StrEnum):
    """What the per-item review decided about one opinion's suggestion.

    These are execution plan §4's four statuses — accepted, partly accepted,
    rejected, pending — **and they are the operator's words, not the
    chain's**. The chain's four states say whether a *change* answered a
    comment; this vocabulary says what the reviewer did with the
    *suggestion*. The mapping between the two is written down once, in
    :data:`VERDICT_RESPONSE_STATES`, so the response table cannot invent one.
    """

    ACCEPTED = "accepted"
    PARTLY_ACCEPTED = "partly_accepted"
    REJECTED = "rejected"
    PENDING = "pending"


#: The chain state each review verdict lands in, once the edits have been
#: applied and the chain's rows exist. ``PENDING`` maps to itself: an opinion
#: the reviewer has not decided is a link nobody has judged.
VERDICT_RESPONSE_STATES: Final[Mapping[ReviewVerdict, str]] = {
    ReviewVerdict.ACCEPTED: "addressed",
    ReviewVerdict.PARTLY_ACCEPTED: "partially_addressed",
    ReviewVerdict.REJECTED: "not_addressed",
    ReviewVerdict.PENDING: "pending",
}

#: The verdicts whose suggestions the binding applies. **A rejected or
#: pending suggestion is not applied** — applying it would be the review
#: saying one thing and the binding doing another.
APPLIED_VERDICTS: Final[frozenset[ReviewVerdict]] = frozenset(
    {ReviewVerdict.ACCEPTED, ReviewVerdict.PARTLY_ACCEPTED}
)


@dataclass(frozen=True, slots=True)
class OpinionBinding:
    """One opinion's place in the binding: located, or explicitly not.

    **Every supported opinion appears here**, whatever its state — an
    opinion absent from the binding is an opinion silently dropped, which is
    the one outcome this ticket exists to make impossible.
    """

    feedback_id: str
    version_id: str
    location_state: LocationState
    #: The reader's own anchor status for the comment: ``resolved``,
    #: ``unknown`` or ``position``.
    anchor_status: str
    anchor_paragraph: int | None


@dataclass(frozen=True, slots=True)
class ModelSuggestion:
    """One edit the suggestion source proposed, **and nothing more**.

    **A suggestion is a record of what the model proposed, and not a
    decision.** It carries no verdict, no approval and no state; the
    reviewer's decision is a separate record (:class:`ReviewDecision`), and
    the two are never merged — that is ADR-0016's rule, restated at the
    binding's own level.
    """

    feedback_id: str
    edit: ApprovedEdit


@dataclass(frozen=True, slots=True)
class ReviewDecision:
    """One person's verdict on one opinion's suggestion, made in the open.

    ``decided_by`` is the chain's own decider word — a person's review is
    ``user`` — and ``operator`` is the operator's own handle, the name the
    edge's acceptance and the manifest's decision entry carry. **The two are
    different fields on purpose**: the chain's vocabulary is closed, and the
    operator's name is not one of its members.
    """

    feedback_id: str
    verdict: ReviewVerdict
    operator: str
    decided_at: datetime
    #: Set when the opinion asks for evidence the manuscript does not carry.
    #: This is the flag that turns an opinion into an explicit unresolved
    #: task, whatever the verdict was.
    needs_evidence: bool = False


@dataclass(frozen=True, slots=True)
class UnresolvedOpinion:
    """An opinion the binding cannot close, kept **as an explicit task**.

    **Unresolved is a deliverable state, not a failure.** The vocabulary is
    execution plan §4's own: an opinion needing an experiment or missing
    evidence stays unresolved, with its reason named, so the next round knows
    exactly what is owed.
    """

    feedback_id: str
    #: ``needs_evidence`` or ``uncertain_location``.
    reason: str
    detail: str


@dataclass(frozen=True, slots=True)
class Handover:
    """An edit the seam refused, handed to a person with its own words.

    **The refusal is LC-P3-02's, not a new one.** The seam's refusal carries
    a reason, a detail and the next sentence a person acts on; the binding
    adds none of its own, because a second spelling of a refusal is a
    refusal nobody can branch on.
    """

    feedback_id: str
    reason: str
    detail: str
    handover: str


@dataclass(frozen=True, slots=True)
class BindingOpened:
    """The binding's first stage: the loop is open and the opinions are placed.

    ``suggestions`` holds what the suggestion source proposed for the
    located opinions — records of what the model said, each paired with the
    opinion it answers and nothing else.
    """

    loop: LoopOpened
    original_bytes: bytes
    opinions: tuple[OpinionBinding, ...]
    suggestions: tuple[ModelSuggestion, ...]


@dataclass(frozen=True, slots=True)
class ResponseBoundEdit:
    """One applied edit, and the chain row it produced.

    ``edit_action_id`` is the chain's own row for the change, minted from
    the approval record the edit carries: the suggestion source's proposal,
    the reviewer's verdict and the publication receipts are together the
    fact the row records.
    """

    feedback_id: str
    edit_action_id: str


@dataclass(frozen=True, slots=True)
class BindingClosed:
    """The binding's last stage: every deliverable, and what it binds to.

    The four deliverables — marked draft, clean draft, response table and
    quality report — all name one task (the loop's own), one input version
    and one output version. The dossier manifest is the row that says so,
    and the witness reads it rather than trusting this record.
    """

    marked_publication: RevisionPublished
    clean_publication: RevisionPublished
    output_version: PaperVersion
    edge: VersionEdge
    suggestions: tuple[ModelSuggestion, ...]
    decisions: tuple[ReviewDecision, ...]
    edits: tuple[ResponseBoundEdit, ...]
    responses: tuple[ResponseLink, ...]
    unresolved: tuple[UnresolvedOpinion, ...]
    handovers: tuple[Handover, ...]
    dossier_key: str
    dossier_artifact_id: str


class DossierManifest(Result):
    """What the binding produced, and what each piece binds to.

    **The manifest is the deliverables' shared record.** A reader who wants
    to know whether the response table really belongs to the output version
    it prints reads this manifest's ids and compares them with the receipts
    — the same discipline LC-P3-03's import receipt set.
    """

    task_id: str
    project_id: str
    input_version_id: str
    output_version_id: str
    marked_receipt_id: str
    marked_sha256: str
    clean_receipt_id: str
    clean_sha256: str
    edge_id: str
    opinions: tuple[OpinionEntry, ...]
    suggestions: tuple[SuggestionEntry, ...]
    decisions: tuple[DecisionEntry, ...]
    responses: tuple[ResponseEntry, ...]
    unresolved: tuple[UnresolvedEntry, ...]
    handovers: tuple[HandoverEntry, ...]
    closed_at: datetime


class OpinionEntry(Result):
    """One opinion's binding, as the manifest carries it."""

    feedback_id: str
    location_state: str
    anchor_status: str
    anchor_paragraph: int | None


class SuggestionEntry(Result):
    """One model suggestion, as the manifest carries it."""

    feedback_id: str
    paragraph: int
    author: str


class DecisionEntry(Result):
    """One reviewer verdict, as the manifest carries it.

    ``operator`` is the reviewer's own handle; the chain's decider word is
    ``user`` for every one of these, and it is not repeated here.
    """

    feedback_id: str
    verdict: str
    operator: str
    needs_evidence: bool


class ResponseEntry(Result):
    """One chain judgement, as the manifest carries it."""

    response_link_id: str
    feedback_id: str
    edit_action_id: str
    state: str


class UnresolvedEntry(Result):
    """One explicit unresolved task, as the manifest carries it."""

    feedback_id: str
    reason: str
    detail: str


class HandoverEntry(Result):
    """One seam refusal handed to a person, as the manifest carries it."""

    feedback_id: str
    reason: str
    detail: str
    handover: str


#: The suggestion source the caller injects. The substitute model behind this
#: phase's provider gate implements this shape; the real model is LC-P3-08's
#: deliverable. Returning ``None`` says the source has no suggestion for this
#: opinion — an honest answer, not a failure.
SuggestionSource = Callable[[FeedbackEvent], ApprovedEdit | None]


def open_binding(
    context: ApplicationContext,
    *,
    project_id: str,
    version_id: str,
    source_root_id: str,
    source_key: str,
    suggest: SuggestionSource,
    now: datetime | None = None,
) -> BindingOpened:
    """Import the original, record its comments, and place every opinion.

    The import is LC-P3-03's :func:`open_loop` — the read-only door, the
    import receipt and the hash binding all belong to it. The comments are
    read through :func:`labcairn.papers.feedback.record_feedback`, which the
    input version's own hash guards. Every opinion the chain then holds is
    classified and carried into :attr:`BindingOpened.opinions`, whatever its
    state: an opinion the reader could not anchor is a location failure with
    a name, never an absence.

    :raises ApplicationRefusedError: the loop refused the import, the
        comments could not be read, or the policy denied the material.
    """
    moment = now if now is not None else datetime.now(UTC)
    loop = open_loop(
        context,
        source_root_id=source_root_id,
        source_key=source_key,
        now=moment,
    )

    material = SourceMaterial(context.workspace, context.policy)
    original_bytes = material.read_permitted(
        source_key,
        root_id=source_root_id,
        capability=CapabilityId.SOURCE_READ.value,
    )

    record_feedback(
        context,
        project_id=project_id,
        version_id=version_id,
        now=moment,
    )

    opinions = _locate_opinions(context, project_id=project_id, version_id=version_id)
    suggestions = _suggest_for_located(context, opinions, suggest=suggest)
    return BindingOpened(
        loop=loop,
        original_bytes=original_bytes,
        opinions=opinions,
        suggestions=suggestions,
    )


def _locate_opinions(
    context: ApplicationContext,
    *,
    project_id: str,
    version_id: str,
) -> tuple[OpinionBinding, ...]:
    """Classify every opinion the chain holds about the input version.

    **The classification is the reader's own facts, restated.** A comment
    whose anchor resolved with text is located; a comment whose anchor is
    unknown — including a position anchor, which names a place but covers no
    passage the seam could rewrite — is an uncertain location. **No opinion
    is left out**: the rows are read back from the chain, so what the chain
    holds is what the binding places.
    """
    bindings: list[OpinionBinding] = []
    for event in list_feedback_events(context, project_id=project_id, version_id=version_id):
        if event.anchor_status == "resolved":
            state = LocationState.LOCATED
        else:
            state = LocationState.UNCERTAIN_LOCATION
        bindings.append(
            OpinionBinding(
                feedback_id=event.feedback_id,
                version_id=event.version_id,
                location_state=state,
                anchor_status=event.anchor_status,
                anchor_paragraph=event.anchor_paragraph,
            )
        )
    return tuple(bindings)


def _suggest_for_located(
    context: ApplicationContext,
    opinions: Sequence[OpinionBinding],
    *,
    suggest: SuggestionSource,
) -> tuple[ModelSuggestion, ...]:
    """Ask the injected source about the located opinions, and hold its answers.

    **Only located opinions are asked.** An opinion at an uncertain location
    has no passage for an edit to rewrite, so asking the source about it
    would be asking it to invent an address — and an invented address is the
    fabrication the anchor vocabulary exists to prevent.

    **A suggestion that does not parse as an edit is refused, not dropped.**
    The source returns whole :class:`ApprovedEdit` values or ``None``; there
    is no third shape to catch, because a partially-formed suggestion would
    put the binding in the business of completing the model's words.
    """
    suggestions: list[ModelSuggestion] = []
    for binding in opinions:
        if binding.location_state is not LocationState.LOCATED:
            continue
        event = _feedback_event(context, binding.feedback_id)
        if event is None:
            continue
        proposed = suggest(event)
        if proposed is None:
            continue
        suggestions.append(ModelSuggestion(feedback_id=binding.feedback_id, edit=proposed))
    return tuple(suggestions)


def _feedback_event(context: ApplicationContext, feedback_id: str) -> FeedbackEvent | None:
    """One opinion, as the chain holds it, or ``None`` when it holds none."""
    row = feedback_row(context.store.session, feedback_id)
    if row is None:
        return None
    return event_from_row(row)


def apply_approved_edits(
    context: ApplicationContext,
    *,
    project_id: str,
    input_version_id: str,
    opened: BindingOpened,
    decisions: Sequence[ReviewDecision],
    source_root_id: str,
    source_key: str,
    output_label: str,
    window_end: datetime,
    now: datetime | None = None,
) -> BindingClosed:
    """Run the reviewed-approved edits through the seam and close the binding.

    **The reviewer's verdicts select the approved set, and nothing else
    does.** A suggestion whose opinion carries no accepted or partly-accepted
    verdict is not applied, whatever the source proposed. A suggestion whose
    opinion was never reviewed is likewise left unapplied — applying an
    unreviewed suggestion would be the model deciding.

    **Each draft is published through its own LC-P3-03 loop** — one import,
    one copy, one publication, one receipt each — so every write rides the
    transaction and the receipt the loop issues, and the loop's duplicate and
    staleness guards stand for the binding's writes as they stand for 03's.

    **The seam's refusals are handovers, not failures.** An edit the seam
    refuses is recorded with the refusal's own words and the rest of the
    approved set still applies: one unsupported structure must not hold the
    whole revision hostage, and a handover is an explicit task, not a drop.

    :raises ApplicationRefusedError: the loop refused a copy or a
        publication, the version graph refused the output row, or the chain
        refused a response.
    """
    moment = now if now is not None else datetime.now(UTC)
    # **The operator is resolved before anything is written.** The edge the
    # output registration names records whose approval made it, and a binding
    # with no decisions at all has nobody to name — refused here, before a
    # single byte lands, rather than after two publications nobody approved.
    operator = _operator_of(decisions)
    verdicts = {decision.feedback_id: decision for decision in decisions}
    approved = _approved_suggestions(opened.suggestions, verdicts)

    handovers: list[Handover] = []
    applied: list[ModelSuggestion] = []
    marked_bytes = opened.original_bytes
    clean_bytes = opened.original_bytes
    for suggestion in approved:
        try:
            marked_bytes = surgical_bytes(marked_bytes, suggestion.edit, DraftForm.MARKED)
            clean_bytes = surgical_bytes(clean_bytes, suggestion.edit, DraftForm.CLEAN)
        except EditRefusedError as error:
            handovers.append(
                Handover(
                    feedback_id=suggestion.feedback_id,
                    reason=error.refusal.reason,
                    detail=error.refusal.detail,
                    handover=error.refusal.handover,
                )
            )
            continue
        applied.append(suggestion)

    # One loop per draft: 03's own rule is that a further publication is a
    # further loop, so the marked and the clean draft each carry their own
    # import receipt, their own copy and their own publication receipt.
    marked_publication = _publish_draft(
        context,
        data=marked_bytes,
        source_root_id=source_root_id,
        source_key=source_key,
        window_end=window_end,
        now=moment,
    )
    clean_publication = _publish_draft(
        context,
        data=clean_bytes,
        source_root_id=source_root_id,
        source_key=source_key,
        window_end=window_end,
        now=moment,
    )

    output_version, edge = _register_output(
        context,
        project_id=project_id,
        input_version_id=input_version_id,
        marked_publication=marked_publication.publication,
        marked_bytes=marked_bytes,
        output_label=output_label,
        operator=operator,
        now=moment,
    )

    edits = _fill_chain(
        context,
        edge_id=edge.edge_id,
        applied=applied,
        now=moment,
    )

    responses = _record_judgements(
        context,
        edits=edits,
        verdicts=verdicts,
        evidence_refs=(
            marked_publication.publication.receipt_id,
            clean_publication.publication.receipt_id,
        ),
        now=moment,
    )

    closed = BindingClosed(
        marked_publication=marked_publication,
        clean_publication=clean_publication,
        output_version=output_version,
        edge=edge,
        suggestions=tuple(applied),
        decisions=tuple(decisions),
        edits=edits,
        responses=responses,
        unresolved=_unresolved_tasks(opinions=opened.opinions, decisions=decisions),
        handovers=tuple(handovers),
        dossier_key="",
        dossier_artifact_id="",
    )
    return close_binding(
        context,
        closed,
        project_id=project_id,
        input_version_id=input_version_id,
        now=moment,
    )


def _publish_draft(
    context: ApplicationContext,
    *,
    data: bytes,
    source_root_id: str,
    source_key: str,
    window_end: datetime,
    now: datetime,
) -> RevisionPublished:
    """Import, copy and publish one draft, with an approval at each effect.

    The loop is LC-P3-03's whole path, unchanged: the import receipt binds
    the hash, the copy re-hashes the original inside the authorised effect,
    and the publication receipt derives from both. The binding adds no
    write of its own — every byte lands through :func:`publish_revision`.
    """
    loop = open_loop(
        context,
        source_root_id=source_root_id,
        source_key=source_key,
        now=now,
    )
    copy_requested = request_loop_approval(
        context,
        loop,
        stage_name=COPY_STAGE_NAME,
        expires_at=window_end,
        now=now,
    )
    copy_granted = grant_approval(context, copy_requested.approval.approval_id, now=now)
    stage_copy(
        context,
        loop,
        approval_id=copy_granted.approval.approval_id,
        now=now,
    )
    publication_requested = request_loop_approval(
        context,
        loop,
        stage_name=PUBLICATION_STAGE_NAME,
        expires_at=window_end,
        now=now,
    )
    publication_granted = grant_approval(
        context, publication_requested.approval.approval_id, now=now
    )
    return publish_revision(
        context,
        loop,
        approval_id=publication_granted.approval.approval_id,
        edited_bytes=data,
        now=now,
    )


def _approved_suggestions(
    suggestions: Sequence[ModelSuggestion],
    verdicts: Mapping[str, ReviewDecision],
) -> tuple[ModelSuggestion, ...]:
    """The suggestions whose opinions the reviewer accepted or partly accepted.

    **A partly-accepted suggestion is applied whole.** The seam's unit is one
    run's text; there is no partial edit to construct, and inventing one
    would put words in the reviewer's mouth. What partial acceptance does is
    leave the opinion's remainder as an explicit unresolved task — which is
    the reviewer's ``needs_evidence`` flag's own work.
    """
    approved: list[ModelSuggestion] = []
    for suggestion in suggestions:
        decision = verdicts.get(suggestion.feedback_id)
        if decision is None:
            continue
        if decision.verdict in APPLIED_VERDICTS:
            approved.append(suggestion)
    return tuple(approved)


def _register_output(
    context: ApplicationContext,
    *,
    project_id: str,
    input_version_id: str,
    marked_publication: ArtifactReceipt,
    marked_bytes: bytes,
    output_label: str,
    operator: str,
    now: datetime,
) -> tuple[PaperVersion, VersionEdge]:
    """Register the marked draft as the output version, and write its edge.

    **The version names the bytes it was made from, through the ledger.**
    The published bytes are ingested as a source of their own — the
    publication's path is unique, so the source id the ledger derives is
    stable — and the version row carries that source's content hash, so a
    version that claims to be the published draft cannot be anything else.

    **Why the rows are written through the store's own writers and not
    through :func:`labcairn.application.papers.record_version`.** That
    operation asks ``source.inventory`` about the version's material, and
    the capability declares source roots only — a published draft lives in
    the task's output area, which the registry refuses *before any policy is
    asked*. That refusal is the product's own boundary and it stands; what
    the binding does instead is keep every check that refusal was protecting
    and drop none: the row is built through the same frozen model (whose
    validators refuse an empty id and a malformed hash, on the way in and on
    the way out), the grant check is asked explicitly, and the bytes are the
    publication receipt's own. A short-circuit that dropped a check would be
    a weaker record, not a cheaper one.

    **The edge is the reviewer's own act.** The relationship input → output
    was established by the person who approved the edits, so the edge names
    ``human`` as its source and the operator as its acceptor: a model
    suggested the words, and a person made them the manuscript's next version.
    """
    ingested = ingest_bytes(
        marked_bytes,
        relative_path=marked_publication.relative_path,
        display_name=marked_publication.relative_path.rsplit("/", 1)[-1],
        ingested_at=now,
    )
    put_source(context.store.session, ingested.source)
    context.store.session.commit()

    _require_the_named_grant(context, project_id, at=now)

    version = PaperVersion(
        version_id=f"pv-{str(new_id())[:16]}",
        project_id=project_id,
        source_content_sha256=ingested.source.content_sha256,
        version_label_raw=output_label,
        status=VersionStatus.UNRESOLVED,
    )
    from labcairn.db.repository import put_paper_version, put_version_edge

    with store_refusals():
        put_paper_version(
            context.store.session,
            version,
            source_id=ingested.source.source_id,
            created_at=now,
        )
        edge = VersionEdge(
            edge_id=f"ve-{str(new_id())[:16]}",
            project_id=project_id,
            parent_version_id=input_version_id,
            child_version_id=version.version_id,
            source=EdgeSource.HUMAN,
            confidence=1.0,
            accepted_by=operator,
            accepted_at=now,
        )
        put_version_edge(context.store.session, edge, created_at=now)
        context.store.session.commit()
    return version, edge


def _require_the_named_grant(
    context: ApplicationContext,
    project_id: str,
    *,
    at: datetime,
) -> None:
    """Ask LC-P2-06's check whether a grant covers this project's material.

    The same check :func:`labcairn.application.papers.record_version` runs,
    asked here because the binding writes the output rows through the store's
    own writers — see :func:`_register_output` for why. **A binding whose
    project names no grant is refused**, whatever the policy says about the
    paths: the permission is denied by the absence of a row, not by a flag.
    """
    from labcairn.security.permissions import may_use

    with store_refusals():
        grants = list_access_grants(context.store.session)
    project = load_paper_project(context.store.session, project_id)
    consent_ref = project.consent_ref
    named = [
        grant for grant in grants if consent_ref is not None and grant.grant_id == consent_ref
    ]
    decision = may_use(
        named,
        permission="store_read",
        purpose="read",
        subject_ref=project_id,
        at=at,
    )
    if not decision.allowed:
        reason = decision.reason
        assert reason is not None  # a refused check always carries a reason
        raise ApplicationRefusedError(consent_refusal_name(reason), decision.detail)


def _fill_chain(
    context: ApplicationContext,
    *,
    edge_id: str,
    applied: Sequence[ModelSuggestion],
    now: datetime,
) -> tuple[ResponseBoundEdit, ...]:
    """Mint the chain's edit rows from the approval records, one per applied edit.

    **The row is minted from the approval record, and not from the published
    bytes.** The chain's own mint-from-the-file path
    (:func:`labcairn.papers.edits.record_edits_from_revisions`) reads the
    child version's material through ``source.inventory`` — a capability the
    registry declares for source roots only, and a published draft lives in
    the task's output area, which the policy refuses before any rule is
    asked. That refusal is the product's own boundary and it stands; what
    the binding mints instead is a row **whose fact is the approval record
    itself**: the suggestion the source proposed, the verdict the reviewer
    gave, and the two publication receipts the bytes landed under are
    together what the row records. The actor is ``model`` — the suggestion
    source drafted the change — and the grade is ``human_verified``, because
    a person approved exactly this change: the two facts stay separate
    fields, as the table's own column layout requires.

    **And the id is derived, as the chain derives ids.** The same
    correspondence proposed twice would mint the same row, so a retried
    binding cannot double-record a change.
    """
    import hashlib

    bound: list[ResponseBoundEdit] = []
    for suggestion in applied:
        digest = hashlib.sha256(
            f"{suggestion.feedback_id}\x00{suggestion.edit.part}\x00"
            f"{suggestion.edit.paragraph}\x00{suggestion.edit.old_text}\x00"
            f"{suggestion.edit.new_text}".encode()
        ).hexdigest()
        edit_action_id = f"ea-{digest[:16]}"
        # The vocabulary checks :func:`record_edit` runs, run here because the
        # row is written through the store's own writer (see above). An actor
        # kind outside the four, or a model row carrying a person's id, is the
        # same refusal here that it is there.
        if "model" not in ACTOR_KINDS:
            raise ApplicationRefusedError(
                ApplicationRefusal.ARGUMENTS_INVALID,
                "'model' is not a kind of actor the chain knows. The binding "
                "records a model's change, and a vocabulary that has lost the "
                "model is a vocabulary the binding cannot speak.",
            )
        with store_refusals():
            context.store.session.add(
                EditActionRow(
                    edit_action_id=edit_action_id,
                    feedback_id=suggestion.feedback_id,
                    version_edge_id=edge_id,
                    actor_kind="model",
                    actor_id=None,
                    grade="human_verified",
                    created_at=now,
                )
            )
            context.store.session.commit()
        bound.append(
            ResponseBoundEdit(
                feedback_id=suggestion.feedback_id,
                edit_action_id=edit_action_id,
            )
        )
    return tuple(bound)


def _record_judgements(
    context: ApplicationContext,
    *,
    edits: Sequence[ResponseBoundEdit],
    verdicts: Mapping[str, ReviewDecision],
    evidence_refs: tuple[str, ...],
    now: datetime,
) -> tuple[ResponseLink, ...]:
    """Put the chain's proposals forward, then record the reviewer's verdicts.

    **The model's proposal and the person's judgement are two writes, under
    two ids.** The proposals go forward at grade ``inferred`` with the
    suggestion source named as the one who put them forward; the verdicts
    are recorded under ids of their own — the derivation carries the verdict
    as well as the pair — because the chain's response table is write-once:
    a row that was put forward as a candidate stays what it was, and the
    judgement is a second row beside it. That is the same separation the
    chain's own tests hold, and it is why a model's proposal is never
    promoted in place to a person's word.

    Only the applied edits reach the chain: a suggestion the reviewer
    rejected produced no change, so there is no edit row for a link to name,
    and the rejection's record is the manifest's decision entry and the
    response table's own row — not a link to a change that does not exist.

    :raises ApplicationRefusedError: the chain refused a proposal or a
        judgement.
    """
    if not edits:
        return ()
    proposals = [
        AnswerProposal(feedback_id=edit.feedback_id, edit_action_id=edit.edit_action_id)
        for edit in edits
    ]
    propose_responses(
        context,
        proposals=proposals,
        proposed_by="model",
        now=now,
    )
    recorded: list[ResponseLink] = []
    for edit in edits:
        decision = verdicts.get(edit.feedback_id)
        if decision is None:
            continue
        state = VERDICT_RESPONSE_STATES[decision.verdict]
        recorded.append(
            record_response(
                context,
                response_link_id=_judgement_id(edit.feedback_id, edit.edit_action_id, decision),
                feedback_id=edit.feedback_id,
                edit_action_id=edit.edit_action_id,
                state=state,
                grade="human_verified",
                decided_by=REVIEW_DECIDER,
                decided_at=decision.decided_at,
                evidence_refs=evidence_refs,
                now=now,
            )
        )
    return tuple(recorded)


def _judgement_id(
    feedback_id: str,
    edit_action_id: str,
    decision: ReviewDecision,
) -> str:
    """The id one judgement takes, derived from the triple it decided.

    **Derived, so the same judgement twice is the same row** — and different
    from the proposal's id, because a judgement is not the proposal it
    answers. The derivation carries the verdict, so a changed verdict under
    the same pair is a different row rather than a silent overwrite.
    """
    import hashlib

    seed = f"{feedback_id}\x00{edit_action_id}\x00{decision.verdict.value}"
    digest = hashlib.sha256(seed.encode()).hexdigest()
    return f"rl-{digest[:16]}"


def _unresolved_tasks(
    *,
    opinions: Sequence[OpinionBinding],
    decisions: Sequence[ReviewDecision],
) -> tuple[UnresolvedOpinion, ...]:
    """The opinions the binding leaves unresolved, each as an explicit task.

    **Two sources, one list.** An opinion the reviewer flagged as needing
    evidence is unresolved because the science asks for something the
    manuscript does not carry; an opinion at an uncertain location is
    unresolved because no passage can be rewritten. **The list is derived
    from the decisions, not carried forward** — so a change in what the
    reviewer decided changes this list, and a stale list is not a list
    anybody reads.
    """
    tasks: list[UnresolvedOpinion] = []
    for decision in decisions:
        if decision.needs_evidence:
            tasks.append(
                UnresolvedOpinion(
                    feedback_id=decision.feedback_id,
                    reason=LocationState.NEEDS_EVIDENCE.value,
                    detail=(
                        "the reviewer marked this opinion as needing further "
                        "evidence: the manuscript does not carry what the opinion "
                        "asks for, and no edit can supply it"
                    ),
                )
            )
    for opinion in opinions:
        if opinion.location_state is LocationState.UNCERTAIN_LOCATION:
            tasks.append(
                UnresolvedOpinion(
                    feedback_id=opinion.feedback_id,
                    reason=LocationState.UNCERTAIN_LOCATION.value,
                    detail=(
                        f"the comment's anchor is {opinion.anchor_status!r} and names "
                        "no passage the seam could rewrite; the opinion stays "
                        "unresolved until a person places it"
                    ),
                )
            )
    return tuple(tasks)


def close_binding(
    context: ApplicationContext,
    closed: BindingClosed,
    *,
    project_id: str,
    input_version_id: str,
    now: datetime | None = None,
) -> BindingClosed:
    """Write the dossier manifest, and return the binding with its address.

    **The manifest is an artefact row, not a file that happens to exist.**
    The row is what a reader audits — its derivation names the marked
    draft's receipt — and the manifest's own bytes are what the response
    table and the quality report are built from.
    """
    moment = now if now is not None else datetime.now(UTC)
    opinions = _opinions_for_manifest(context, project_id=project_id, version_id=input_version_id)
    manifest = DossierManifest(
        task_id=str(context.task_id),
        project_id=project_id,
        input_version_id=input_version_id,
        output_version_id=closed.output_version.version_id,
        marked_receipt_id=closed.marked_publication.publication.receipt_id,
        marked_sha256=closed.marked_publication.publication_sha256,
        clean_receipt_id=closed.clean_publication.publication.receipt_id,
        clean_sha256=closed.clean_publication.publication_sha256,
        edge_id=closed.edge.edge_id,
        opinions=tuple(
            OpinionEntry(
                feedback_id=opinion.feedback_id,
                location_state=opinion.location_state.value,
                anchor_status=opinion.anchor_status,
                anchor_paragraph=opinion.anchor_paragraph,
            )
            for opinion in opinions
        ),
        suggestions=tuple(
            SuggestionEntry(
                feedback_id=suggestion.feedback_id,
                paragraph=suggestion.edit.paragraph,
                author=suggestion.edit.author,
            )
            for suggestion in closed.suggestions
        ),
        decisions=tuple(
            DecisionEntry(
                feedback_id=decision.feedback_id,
                verdict=decision.verdict.value,
                operator=decision.operator,
                needs_evidence=decision.needs_evidence,
            )
            for decision in closed.decisions
        ),
        responses=tuple(
            ResponseEntry(
                response_link_id=response.response_link_id,
                feedback_id=response.feedback_id,
                edit_action_id=response.edit_action_id,
                state=response.state,
            )
            for response in closed.responses
        ),
        unresolved=tuple(
            UnresolvedEntry(feedback_id=task.feedback_id, reason=task.reason, detail=task.detail)
            for task in closed.unresolved
        ),
        handovers=tuple(
            HandoverEntry(
                feedback_id=handover.feedback_id,
                reason=handover.reason,
                detail=handover.detail,
                handover=handover.handover,
            )
            for handover in closed.handovers
        ),
        closed_at=moment,
    )
    dossier_key = _dossier_key(closed)
    manifest_bytes = json.dumps(
        manifest.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, indent=2
    ).encode()
    written = TaskOutputArea(context.workspace).write(dossier_key, manifest_bytes)
    receipt = ArtifactReceipt(
        receipt_id=str(new_id()),
        task_id=str(context.task_id),
        kind=ArtifactKind.MANIFEST,
        relative_path=written.absolute_path.relative_to(
            context.workspace.selected_root
        ).as_posix(),
        content_sha256=written.content_hash,
        size_bytes=written.size_bytes,
        produced_by=ArtifactProducerKind.STAGE,
        producer_id=BINDING_PRODUCER_ID,
        derived_from=(
            DerivationRef(
                target_kind=DerivationTargetKind.ARTIFACT,
                target_id=closed.marked_publication.publication.receipt_id,
                content_sha256=closed.marked_publication.publication_sha256,
            ),
        ),
        media_type="application/json",
        created_at=moment,
    )
    with context.store.unit(context.task_id) as work_unit:
        work_unit.put_artifact(receipt)
    return BindingClosed(
        marked_publication=closed.marked_publication,
        clean_publication=closed.clean_publication,
        output_version=closed.output_version,
        edge=closed.edge,
        suggestions=closed.suggestions,
        decisions=closed.decisions,
        edits=closed.edits,
        responses=closed.responses,
        unresolved=closed.unresolved,
        handovers=closed.handovers,
        dossier_key=dossier_key,
        dossier_artifact_id=receipt.receipt_id,
    )


def _opinions_for_manifest(
    context: ApplicationContext,
    *,
    project_id: str,
    version_id: str,
) -> tuple[OpinionBinding, ...]:
    """The opinions the manifest carries: the chain's rows, read back.

    The binding's own ``opinions`` field is not carried on
    :class:`BindingClosed` — the chain is the record, and the manifest reads
    the chain rather than a copy of an earlier read.
    """
    events = list_feedback_events(context, project_id=project_id, version_id=version_id)
    bindings: list[OpinionBinding] = []
    for event in events:
        if event.anchor_status == "resolved":
            state = LocationState.LOCATED
        else:
            state = LocationState.UNCERTAIN_LOCATION
        bindings.append(
            OpinionBinding(
                feedback_id=event.feedback_id,
                version_id=event.version_id,
                location_state=state,
                anchor_status=event.anchor_status,
                anchor_paragraph=event.anchor_paragraph,
            )
        )
    return tuple(bindings)


def _dossier_key(closed: BindingClosed) -> str:
    """The dossier's key, inside the marked loop's own directory.

    The binding's manifest lives beside the drafts it binds, so one
    directory holds one revision's whole story: the copy, the two drafts and
    the manifest that ties them to the chain. The directory's name is the
    import receipt's id, which is how LC-P3-03's own keys are spelled.
    """
    receipt_id = closed.marked_publication.publication.receipt_id
    return f"revisions/{receipt_id}/binding-dossier.json"


def _operator_of(decisions: Sequence[ReviewDecision]) -> str:
    """The operator the edge's acceptance names, from the decisions.

    **One binding, one operator.** The per-item review is one person's
    sitting, and the edge records whose sitting it was: the first decision's
    operator stands for the batch, because the verdicts were given together
    and a mixed batch would be two bindings. A binding applied with no
    decisions at all has no operator to name, and the edge is refused by the
    version graph's own contract rather than invented here.
    """
    if not decisions:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            "the binding closes with no review decision at all. The edge from the "
            "input version to the output version records whose approval made it, "
            "and an edge nobody approved is a version nobody made.",
        )
    return decisions[0].operator
