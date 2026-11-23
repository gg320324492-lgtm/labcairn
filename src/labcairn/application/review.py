"""The review workbench's reads and writes, through the layer.

**What this module is.** The workbench's three columns all read the same
round: the advisor's opinions (the left column's navigation), the
manuscript they sit in (the middle column's text), and the suggestion each
opinion carries with the verdict a reviewer has given it (the right
column's work). Phase 3 built each of those as a loop stage; the workbench
needs them **between** stages, as reads that do not run anything, and it
needs the reviewer's verdict to **persist** — a verdict that lives only in
the request that made it would be forgotten by the next render, and an
apply step that reads the approved set would have nothing to read.

So this module is the seam for that work:

* :func:`read_review_opinions` — every opinion the chain holds, with its
  stored suggestion, its stored decision and the chain's response states,
  in the shape the contract
  ``docs/plans/LC-P4-CAP-review-api-contract.md`` names. A suggestion and
  its decision are **separate fields, never merged** (ADR-0016's rule, at
  the API's surface).
* :func:`read_review_manuscript` — the version's own paragraphs, in
  document order, read under the same bound the feedback path uses.
* :func:`record_review_suggestion` — store what the model proposed, verbatim
  in the seam's vocabulary. **A proposal is a record, not a decision.**
* :func:`record_review_decision` — store the reviewer's verdict, refusing a
  verdict on nothing: an opinion the chain does not hold, or an acceptance
  with no suggestion to accept, is refused rather than recorded.
* :func:`apply_review` — run the stored, approved set through the binding's
  :func:`~labcairn.papers.binding.apply_approved_edits`, which carries the
  loop's own duplicate, staleness and consent guards. This module adds no
  guard of its own: a second spelling of the loop's guards would be a
  weaker record, not a cheaper path.

**The permission posture is the chain's.** These reads and writes reach rows
that name no resource of their own — a comment, a verdict, a suggestion are
facts about a manuscript, and the permission that governs them is the
permission on the material. So the material permission is asked where the
material is named, exactly as :mod:`labcairn.application.chain` does, and a
write whose project names no grant is refused by the same absence that
refuses the chain's writers.

**The binding's vocabulary is imported lazily.** :mod:`labcairn.papers.binding`
imports this package on its own way in, so this module imports it inside the
functions that need it — the same courtesy :mod:`labcairn.papers.binding`
extends to the store's writers.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from labcairn.application import consent
from labcairn.application.context import ApplicationContext
from labcairn.application.models import Result
from labcairn.application.refusal import (
    ApplicationRefusal,
    ApplicationRefusedError,
    chain_refused,
)
from labcairn.db.models import (
    FeedbackEventRow,
    PaperVersionRow,
    ReviewDecisionRow,
    ReviewSuggestionRow,
)
from labcairn.papers.chain import ChainRefusal, feedback_row, project_row
from labcairn.papers.feedback import MAX_MANUSCRIPT_BYTES, list_feedback_events
from labcairn.security.capabilities import CapabilityId

if TYPE_CHECKING:
    from labcairn.papers.binding import BindingOpened, CancelCheck

__all__ = [
    "ApplyReviewRequest",
    "CancelCheck",
    "DeliverableFile",
    "DeliverablesExport",
    "ExportDeliverablesRequest",
    "PreviewEditSummary",
    "ReviewApplyResult",
    "ReviewDecisionData",
    "ReviewHandover",
    "ReviewManuscript",
    "ReviewOpinion",
    "ReviewOpinions",
    "ReviewParagraph",
    "ReviewPreview",
    "ReviewSuggestionData",
    "ReviewUnresolved",
    "apply_review",
    "export_deliverables",
    "preview_review_apply",
    "read_review_manuscript",
    "read_review_opinions",
    "record_review_decision",
    "record_review_suggestion",
]


class ReviewSuggestionData(Result):
    """One stored suggestion, as the workbench reads it.

    The seam's own vocabulary, verbatim: one whole plain run of one
    paragraph. The workbench shows ``old_text`` and ``new_text`` side by
    side; the apply step hands the pair to the seam unchanged.
    """

    part: str
    paragraph: int
    old_text: str
    new_text: str
    author: str
    proposed_at: str


class ReviewDecisionData(Result):
    """One stored verdict, as the workbench reads it.

    ``decided_by`` is not here because it is not variable: every row is a
    person's review, and the chain's word for that is ``user``. The
    reviewer's own handle is ``operator``.
    """

    verdict: str
    needs_evidence: bool
    operator: str
    decided_at: str


class ReviewOpinion(Result):
    """One opinion, with its suggestion and its decision — never merged.

    **Separate facts about one opinion.** The comment and its anchor are
    the chain's facts; the suggestion is what the model proposed; the
    decision is what the reviewer did with the proposal; the response
    states are the chain's own judgements over the applied edits. A reader
    who wants the model's words reads ``suggestion``; a reader who wants
    the reviewer's reads ``decision``; neither field's presence says
    anything about the other.
    """

    feedback_id: str
    issue_key: str
    version_id: str
    comment_text: str
    author: str | None
    anchor_status: str
    anchor_reason: str | None
    anchor_paragraph: int | None
    anchor_start: int | None
    anchor_end: int | None
    anchor_text: str | None
    comment_locator: dict[str, object] | None
    location_state: str
    suggestion: ReviewSuggestionData | None
    decision: ReviewDecisionData | None
    response_states: tuple[str, ...]


class ReviewOpinions(Result):
    """The opinion list one project/version's review round holds."""

    project_id: str
    version_id: str
    opinions: tuple[ReviewOpinion, ...]


class ReviewParagraph(Result):
    """One paragraph of the manuscript, 1-based, in document order.

    ``index`` is the number the feedback anchors and the suggestions'
    ``paragraph`` field name — the same numbering, so the workbench's
    scroll-sync is an equality test rather than a lookup.
    """

    index: int
    text: str


class ReviewManuscript(Result):
    """The manuscript's paragraphs, as the middle column renders them."""

    project_id: str
    version_id: str
    sha256: str
    paragraphs: tuple[ReviewParagraph, ...]


class ReviewHandover(Result):
    """One edit the seam refused, as the apply result carries it."""

    feedback_id: str
    reason: str
    detail: str
    handover: str


class ReviewUnresolved(Result):
    """One opinion the round leaves unresolved, as the apply result carries it."""

    feedback_id: str
    reason: str
    detail: str


class ReviewApplyResult(Result):
    """What one apply round produced, flattened from the binding's close.

    **The ids are the deliverables' bindings.** The marked and the clean
    draft each name their publication receipt and their bytes' hash; the
    output version and the edge name the version-graph rows; the dossier
    artifact is the manifest that ties all of it to the input version. A
    reader who wants to know whether the response table belongs to this
    round reads the dossier and compares these ids — the same discipline
    the binding's own witnesses apply.
    """

    project_id: str
    input_version_id: str
    output_version_id: str
    edge_id: str
    marked_receipt_id: str
    marked_sha256: str
    clean_receipt_id: str
    clean_sha256: str
    dossier_artifact_id: str
    applied: tuple[str, ...]
    handovers: tuple[ReviewHandover, ...]
    unresolved: tuple[ReviewUnresolved, ...]


class ApplyReviewRequest(BaseModel):
    """What the apply step needs, addressed the way the binding names things.

    ``model_config`` is frozen because a request is a statement about a
    moment; the extra-forbid rule is the layer's own.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str
    input_version_id: str
    source_root_id: str
    source_key: str
    output_label: str
    window_end: str


class PreviewEditSummary(Result):
    """One approved suggestion's old→new pair, as the preview names it.

    The seam's own units, verbatim: one whole plain run of one paragraph.
    The workbench shows the pair side by side; the apply step hands the
    same pair to the seam. ``old_text`` is the run's text as the manuscript
    holds it now, and ``new_text`` is what the seam would write in its
    place — the same fields :class:`ReviewSuggestionData` carries, so the
    preview's summaries and the right column's suggestions cannot disagree.
    """

    feedback_id: str
    part: str
    paragraph: int
    old_text: str
    new_text: str
    author: str


class ReviewPreview(Result):
    """What one apply round would do, measured without doing it.

    **The counts and the digests are measured, not asserted.** ``applied``,
    ``pending`` and ``rejected`` are counts over the stored decisions, read
    the way the apply step reads them; ``affected_paragraphs`` is the set
    the approved suggestions name, in ascending order; and the two digests
    are the sha256 of the drafts the seam's own fold produces — the apply
    step's very loop, run onto pure copies. A reader who wants to know
    whether the preview told the truth applies the round and compares the
    digests; :mod:`tests.test_review_api` is the witness that they match.
    """

    project_id: str
    input_version_id: str
    #: How many stored suggestions the reviewer's verdicts would let through.
    applied: int
    #: Verdicts that hold the suggestions back — the model deciding would be
    #: the failure the separation exists to prevent.
    pending: int
    rejected: int
    #: The 1-based paragraph ordinals the approved edits name, ascending.
    affected_paragraphs: tuple[int, ...]
    #: One summary per approved suggestion, in approval order.
    edits: tuple[PreviewEditSummary, ...]
    marked_sha256: str
    marked_size_bytes: int
    clean_sha256: str
    clean_size_bytes: int
    original_sha256: str
    original_size_bytes: int


class ExportDeliverablesRequest(BaseModel):
    """What the export step needs: which dossier, and nothing else.

    The dossier manifest is the binding's own record; naming it names the
    whole round — its task, its input version, its output version and the
    four deliverables. ``model_config`` is frozen for the same reason
    :class:`ApplyReviewRequest`'s is.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str
    dossier_artifact_id: str


class DeliverableFile(Result):
    """One deliverable's bytes, with the digest a reader checks them against.

    ``kind`` is the deliverable's own name in execution plan §3.2's
    vocabulary — ``marked``, ``clean``, ``response_table`` or
    ``quality_report`` — and ``content`` is the bytes exactly as a reader
    would write them to disk. The sha256 is over those bytes, so a reader
    who hashes what they received compares it against a hash of the same
    thing.
    """

    kind: str
    relative_path: str
    content: bytes
    sha256: str
    size_bytes: int


class DeliverablesExport(Result):
    """The four deliverables of one closed binding, and what they bind to.

    **The four are one export because they are one round.** The manifest's
    ids are carried through unchanged — the same task, the same input
    version, the same output version, the same receipts — so a reader who
    wants to know whether the table they are holding belongs to the draft
    beside it compares the ids, and the export is the record that says what
    belongs together.
    """

    project_id: str
    dossier_artifact_id: str
    task_id: str
    input_version_id: str
    output_version_id: str
    marked_receipt_id: str
    clean_receipt_id: str
    edge_id: str
    deliverables: tuple[DeliverableFile, ...]


def _require_project(context: ApplicationContext, project_id: str) -> None:
    if project_row(context.store.session, project_id) is None:
        raise chain_refused(
            ChainRefusal.PROJECT_NOT_FOUND,
            f"the store holds no paper project with the id {project_id!r}.",
        )


def _require_version(
    context: ApplicationContext, project_id: str, version_id: str
) -> PaperVersionRow:
    row = context.store.session.get(PaperVersionRow, version_id)
    if row is None:
        raise chain_refused(
            ChainRefusal.VERSION_NOT_FOUND,
            f"the store holds no manuscript version with the id {version_id!r}.",
        )
    if row.project_id != project_id:
        raise chain_refused(
            ChainRefusal.VERSION_NOT_FOUND,
            f"the manuscript version {version_id!r} belongs to the project "
            f"{row.project_id!r}, not to {project_id!r}.",
        )
    return row


def read_review_opinions(
    context: ApplicationContext,
    *,
    project_id: str,
    version_id: str,
) -> ReviewOpinions:
    """Every opinion the chain holds, with its suggestion and its decision.

    **One read, three sources, no join through a fourth.** The comments come
    from the chain's read (which already applies the material permission and
    drops denied entries rather than refusing the listing); the suggestions
    and the decisions come from this module's own tables, read under the same
    ``feedback_id`` the comments carry; the response states are the chain's
    own. An opinion with no stored suggestion carries ``suggestion=None``; an
    opinion with no stored verdict carries ``decision=None`` — and neither
    absence is invented into a value.
    """
    from labcairn.application.chain import read_response_states
    from labcairn.papers.binding import LocationState

    _require_project(context, project_id)
    _require_version(context, project_id, version_id)
    events = list_feedback_events(context, project_id=project_id, version_id=version_id)
    if not events:
        return ReviewOpinions(project_id=project_id, version_id=version_id, opinions=())

    ids = tuple(event.feedback_id for event in events)
    session = context.store.session
    suggestion_rows = {
        row.feedback_id: row
        for row in session.scalars(
            select(ReviewSuggestionRow).where(ReviewSuggestionRow.feedback_id.in_(ids))
        ).all()
    }
    decision_rows = {
        row.feedback_id: row
        for row in session.scalars(
            select(ReviewDecisionRow).where(ReviewDecisionRow.feedback_id.in_(ids))
        ).all()
    }
    states = dict(
        zip(
            ids,
            read_response_states(context, feedback_ids=ids),
            strict=False,
        )
    )

    # **The binding's own classification, restated from the same fields.**
    # The location state is the binding's vocabulary; the mapping — a
    # resolved anchor is located, anything else is an uncertain location —
    # is the one ``binding._locate_opinions`` applies, kept in step with it
    # by reading the same anchor statuses.
    opinions: list[ReviewOpinion] = []
    for event in events:
        suggestion_row = suggestion_rows.get(event.feedback_id)
        decision_row = decision_rows.get(event.feedback_id)
        opinions.append(
            ReviewOpinion(
                feedback_id=event.feedback_id,
                issue_key=event.issue_key or "",
                version_id=event.version_id,
                comment_text=event.comment_text,
                author=event.author,
                anchor_status=event.anchor_status,
                anchor_reason=event.anchor_reason,
                anchor_paragraph=event.anchor_paragraph,
                anchor_start=event.anchor_start,
                anchor_end=event.anchor_end,
                anchor_text=event.anchor_text,
                comment_locator=(
                    event.comment_locator.model_dump(mode="json")
                    if event.comment_locator is not None
                    else None
                ),
                location_state=(
                    LocationState.LOCATED.value
                    if event.anchor_status == "resolved"
                    else LocationState.UNCERTAIN_LOCATION.value
                ),
                suggestion=(
                    ReviewSuggestionData(
                        part=suggestion_row.part,
                        paragraph=suggestion_row.paragraph,
                        old_text=suggestion_row.old_text,
                        new_text=suggestion_row.new_text,
                        author=suggestion_row.author,
                        proposed_at=suggestion_row.proposed_at.isoformat(),
                    )
                    if suggestion_row is not None
                    else None
                ),
                decision=(
                    ReviewDecisionData(
                        verdict=decision_row.verdict,
                        needs_evidence=decision_row.needs_evidence,
                        operator=decision_row.operator,
                        decided_at=decision_row.decided_at.isoformat(),
                    )
                    if decision_row is not None
                    else None
                ),
                response_states=tuple(states.get(event.feedback_id, ())),
            )
        )
    return ReviewOpinions(project_id=project_id, version_id=version_id, opinions=tuple(opinions))


def read_review_manuscript(
    context: ApplicationContext,
    *,
    project_id: str,
    version_id: str,
) -> ReviewManuscript:
    """The manuscript's paragraphs, in document order, in the accepted view.

    **The accepted view is the workbench's view.** The middle column shows
    the text as if every tracked change were accepted — the same view the
    feedback reader anchors into, so an anchor's offsets name the text this
    read returns.

    :raises ApplicationRefusedError: the project or the version is not
        there, the policy denied reading the material, or the bytes have
        drifted from the version's hash.
    """
    # **The feedback path's own readers, reused rather than re-spelled.**
    # ``_material_of`` admits the version's material and ``_read_material``
    # measures, reads and hash-checks it against the version — the same
    # door ``record_feedback`` walks, so a drift refusal here is the same
    # refusal the chain's writer would raise.
    from labcairn.material.ooxml import read_document
    from labcairn.papers.feedback import _material_of, _read_material

    _require_project(context, project_id)
    version = _require_version(context, project_id, version_id)
    resource = _material_of(context, version_id)
    consent.evaluate(
        context,
        capability=CapabilityId.SOURCE_READ,
        arguments={"max_bytes": MAX_MANUSCRIPT_BYTES},
        resource=resource,
    )
    data = _read_material(context, version_id)

    document = read_document(data)
    return ReviewManuscript(
        project_id=project_id,
        version_id=version_id,
        sha256=version.source_content_sha256 or "",
        paragraphs=tuple(
            ReviewParagraph(index=index, text=text)
            for index, text in enumerate(document.paragraphs, start=1)
        ),
    )


def record_review_suggestion(
    context: ApplicationContext,
    *,
    project_id: str,
    version_id: str,
    feedback_id: str,
    part: str,
    paragraph: int,
    old_text: str,
    new_text: str,
    author: str,
    proposed_at: datetime | None = None,
) -> ReviewSuggestionData:
    """Store one suggestion the model proposed, verbatim in the seam's units.

    **A proposal is a record, not a decision.** Writing one grants nothing,
    changes nothing, and applies nothing; the verdict is
    :func:`record_review_decision`'s to take. **One suggestion per opinion**:
    a second insert under the same ``feedback_id`` refreshes the proposal,
    and the row the store holds is the proposal that stands — the same rule
    the chain's derived ids apply to re-reading a comment.

    :raises ApplicationRefusedError: the opinion is not in the chain, or the
        proposal's fields are unusable.
    """
    moment = proposed_at if proposed_at is not None else datetime.now(UTC)
    _require_project(context, project_id)
    _require_version(context, project_id, version_id)
    if feedback_row(context.store.session, feedback_id) is None:
        raise chain_refused(
            ChainRefusal.FEEDBACK_NOT_FOUND,
            f"the chain holds no comment with the id {feedback_id!r}. A suggestion "
            "answers an opinion, and a suggestion about an opinion nobody holds is "
            "a proposal about nothing.",
        )
    if paragraph < 1:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the paragraph ordinal must be 1-based and positive, not {paragraph}.",
        )
    if not part or not author:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            "a suggestion names the part it edits and who proposed it; both were empty.",
        )

    now = datetime.now(UTC)
    existing = context.store.session.get(ReviewSuggestionRow, feedback_id)
    if existing is not None:
        # **A refreshed proposal is the same row.** The fields move; the id
        # does not, and neither does the fact that this is one opinion's
        # one standing proposal.
        existing.part = part
        existing.paragraph = paragraph
        existing.old_text = old_text
        existing.new_text = new_text
        existing.author = author
        existing.proposed_at = moment
        existing.version_id = version_id
        context.store.session.commit()
        row = existing
    else:
        row = ReviewSuggestionRow(
            feedback_id=feedback_id,
            project_id=project_id,
            version_id=version_id,
            part=part,
            paragraph=paragraph,
            old_text=old_text,
            new_text=new_text,
            author=author,
            proposed_at=moment,
            created_at=now,
        )
        context.store.session.add(row)
        context.store.session.commit()
    return ReviewSuggestionData(
        part=row.part,
        paragraph=row.paragraph,
        old_text=row.old_text,
        new_text=row.new_text,
        author=row.author,
        proposed_at=row.proposed_at.isoformat(),
    )


def record_review_decision(
    context: ApplicationContext,
    *,
    project_id: str,
    feedback_id: str,
    verdict: str,
    operator: str,
    needs_evidence: bool = False,
    decided_at: datetime | None = None,
) -> ReviewDecisionData:
    """Store the reviewer's verdict on one opinion's suggestion.

    **A verdict on nothing is refused.** The opinion must be in the chain,
    and an ``accepted`` or ``partly_accepted`` verdict must have a stored
    suggestion to accept — a reviewer who approves a proposal nobody made
    would be approval theatre, and the record would say a decision was made
    that was not.

    **A verdict that stands is one row.** A reviewer who revises their own
    verdict writes the row again under the same id; the store holds the
    verdict that stands, and the apply step reads it from here.

    :raises ApplicationRefusedError: the opinion is not in the chain, the
        verdict accepts a suggestion that does not exist, the verdict is
        not one of the four, or the operator handle is empty.
    """
    from labcairn.papers.binding import APPLIED_VERDICTS, ReviewVerdict

    moment = decided_at if decided_at is not None else datetime.now(UTC)
    _require_project(context, project_id)
    if not operator:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            "a decision names the reviewer; the operator handle was empty.",
        )
    try:
        parsed_verdict = ReviewVerdict(verdict)
    except ValueError as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"{verdict!r} is not one of the four review verdicts "
            f"({', '.join(member.value for member in ReviewVerdict)}).",
        ) from error
    event_row = feedback_row(context.store.session, feedback_id)
    if event_row is None:
        raise chain_refused(
            ChainRefusal.FEEDBACK_NOT_FOUND,
            f"the chain holds no comment with the id {feedback_id!r}. A verdict is "
            "about an opinion, and a verdict about an opinion nobody holds decides "
            "nothing.",
        )
    version_id = event_row.version_id
    if parsed_verdict in APPLIED_VERDICTS:
        suggestion = context.store.session.get(ReviewSuggestionRow, feedback_id)
        if suggestion is None:
            raise ApplicationRefusedError(
                ApplicationRefusal.ARGUMENTS_INVALID,
                f"the opinion {feedback_id!r} carries no stored suggestion, so there "
                f"is nothing for the verdict {parsed_verdict.value!r} to accept. "
                "Reviewing a proposal nobody made would be a decision about nothing.",
            )

    now = datetime.now(UTC)
    existing = context.store.session.get(ReviewDecisionRow, feedback_id)
    if existing is not None:
        existing.verdict = parsed_verdict.value
        existing.needs_evidence = needs_evidence
        existing.operator = operator
        existing.decided_at = moment
        existing.version_id = version_id
        context.store.session.commit()
        row = existing
    else:
        row = ReviewDecisionRow(
            feedback_id=feedback_id,
            project_id=project_id,
            version_id=version_id,
            verdict=parsed_verdict.value,
            needs_evidence=needs_evidence,
            operator=operator,
            decided_at=moment,
            created_at=now,
        )
        context.store.session.add(row)
        context.store.session.commit()
    return ReviewDecisionData(
        verdict=row.verdict,
        needs_evidence=row.needs_evidence,
        operator=row.operator,
        decided_at=row.decided_at.isoformat(),
    )


def apply_review(
    context: ApplicationContext,
    request: ApplyReviewRequest,
    *,
    cancel_check: CancelCheck | None = None,
) -> ReviewApplyResult:
    """Run the stored, approved set through the binding and close the round.

    **The decisions are read from the store, not from the request.** The
    workbench does not send verdicts with the apply call; the apply step
    reads what the reviewer wrote, which is what makes the applied set
    auditable after the fact — the store, not the request body, is the
    record of what was approved.

    **The binding's guards are the guards.** Duplicate publications,
    stale approvals, consent and the loop's own receipt discipline are
    :func:`labcairn.papers.binding.apply_approved_edits`'s, unchanged; this
    module adds none. The cancellation hook is passed through untouched: a
    surface that can ask its operator "stop this round?" names the answer as
    a :class:`CancelCheck`, and the binding asks it before each publication.

    :param cancel_check: the binding's cancellation injection, verbatim.
    :raises ApplicationRefusedError: nothing has been decided yet (there is
        no approved set and no operator to name), the round was cancelled
        (``apply_cancelled``), or the binding refused the round for the reason
        it names.
    """
    from labcairn.papers.binding import ReviewDecision, ReviewVerdict, apply_approved_edits

    _require_project(context, request.project_id)
    session = context.store.session
    decision_rows = session.scalars(
        select(ReviewDecisionRow).where(ReviewDecisionRow.project_id == request.project_id)
    ).all()
    decisions: list[ReviewDecision] = []
    for row in decision_rows:
        event_row = session.get(FeedbackEventRow, row.feedback_id)
        if event_row is None:
            continue
        decisions.append(
            ReviewDecision(
                feedback_id=row.feedback_id,
                verdict=ReviewVerdict(row.verdict),
                operator=row.operator,
                decided_at=row.decided_at,
                needs_evidence=row.needs_evidence,
            )
        )
    if not decisions:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the project {request.project_id!r} holds no review decision, so "
            "there is no approved set to apply. Applying nothing would publish a "
            "version nobody reviewed.",
        )
    opened = _open_binding_from_store(context, request)
    closed = apply_approved_edits(
        context,
        project_id=request.project_id,
        input_version_id=request.input_version_id,
        opened=opened,
        decisions=decisions,
        source_root_id=request.source_root_id,
        source_key=request.source_key,
        output_label=request.output_label,
        cancel_check=cancel_check,
        window_end=datetime.fromisoformat(request.window_end),
    )
    return ReviewApplyResult(
        project_id=request.project_id,
        input_version_id=request.input_version_id,
        output_version_id=closed.output_version.version_id,
        edge_id=closed.edge.edge_id,
        marked_receipt_id=closed.marked_publication.publication.receipt_id,
        marked_sha256=closed.marked_publication.publication_sha256,
        clean_receipt_id=closed.clean_publication.publication.receipt_id,
        clean_sha256=closed.clean_publication.publication_sha256,
        dossier_artifact_id=closed.dossier_artifact_id,
        applied=tuple(edit.feedback_id for edit in closed.edits),
        handovers=tuple(
            ReviewHandover(
                feedback_id=handover.feedback_id,
                reason=handover.reason,
                detail=handover.detail,
                handover=handover.handover,
            )
            for handover in closed.handovers
        ),
        unresolved=tuple(
            ReviewUnresolved(
                feedback_id=task.feedback_id,
                reason=task.reason,
                detail=task.detail,
            )
            for task in closed.unresolved
        ),
    )


def preview_review_apply(
    context: ApplicationContext,
    request: ApplyReviewRequest,
) -> ReviewPreview:
    """Measure what one apply round would do, without doing any of it.

    **The preview runs the apply step's own pieces, and writes nothing.**
    The opinions are classified by the binding's own reader, the approved
    set is selected by the binding's own filter, and the drafts are folded
    by the apply step's own rewrite loop — extracted into
    :func:`labcairn.papers.binding.fold_approved_edits` so the preview and
    the apply cannot drift into two spellings of one step. What the preview
    adds is the discipline of the dry run: no file is written, no store row
    is written, and :func:`labcairn.papers.binding.apply_approved_edits` is
    never called — a preview that published would be the apply step wearing
    a preview's name.

    **The digests are the apply's digests, on purpose.** The same original
    bytes, read through the same permitted read and folded in the same
    order, give the sha256 the apply's publications will carry. A caller
    applies the round and compares; the equality is the witness that the
    preview did not lie, and :mod:`tests.test_review_api` is where it is
    witnessed.

    **A suggestion the reviewer has not decided is counted, not applied.**
    ``pending`` and ``rejected`` name the suggestions the verdicts hold
    back — applying either would be the model deciding, which is the
    failure the separation exists to prevent — and neither appears in
    ``affected_paragraphs`` nor in ``edits``.

    :raises ApplicationRefusedError: the project or the version is not
        there, the material is denied or unreadable, or the stored
        suggestions cannot be read.
    """
    from labcairn.editing.drafts import ApprovedEdit
    from labcairn.papers.binding import (
        LocationState,
        ModelSuggestion,
        ReviewDecision,
        ReviewVerdict,
        _approved_suggestions,
        _locate_opinions,
        fold_approved_edits,
    )
    from labcairn.security.capabilities import CapabilityId
    from labcairn.workspace.readonly import SourceMaterial

    _require_project(context, request.project_id)
    _require_version(context, request.project_id, request.input_version_id)
    session = context.store.session
    decision_rows = session.scalars(
        select(ReviewDecisionRow).where(ReviewDecisionRow.project_id == request.project_id)
    ).all()
    decisions: list[ReviewDecision] = []
    for row in decision_rows:
        event_row = session.get(FeedbackEventRow, row.feedback_id)
        if event_row is None:
            continue
        decisions.append(
            ReviewDecision(
                feedback_id=row.feedback_id,
                verdict=ReviewVerdict(row.verdict),
                operator=row.operator,
                decided_at=row.decided_at,
                needs_evidence=row.needs_evidence,
            )
        )
    if not decisions:
        # **The apply's own guard, mirrored.** A round nobody reviewed has no
        # approved set, and the apply refuses it rather than publishing an
        # unreviewed version. The preview shows the same refusal, because a
        # preview that answered "nothing will change, you are clear to apply"
        # about a round the apply would refuse would be a preview that lied
        # by omission.
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the project {request.project_id!r} holds no review decision, so "
            "there is no approved set to preview. Applying nothing would publish a "
            "version nobody reviewed.",
        )
    verdict_by_id = {decision.feedback_id: decision for decision in decisions}

    # **The suggestions are the stored ones, read the way the apply reads
    # them.** The apply's suggestion source reads this module's own table
    # for the located opinions; the preview reads the same rows under the
    # same filter, so the two candidate sets are the same set in the same
    # order — which is what makes the folded digests comparable.
    suggestions: list[ModelSuggestion] = []
    for binding in _locate_opinions(
        context, project_id=request.project_id, version_id=request.input_version_id
    ):
        if binding.location_state is not LocationState.LOCATED:
            continue
        suggestion_row = session.get(ReviewSuggestionRow, binding.feedback_id)
        if suggestion_row is None:
            continue
        suggestions.append(
            ModelSuggestion(
                feedback_id=binding.feedback_id,
                edit=ApprovedEdit(
                    part=suggestion_row.part,
                    paragraph=suggestion_row.paragraph,
                    old_text=suggestion_row.old_text,
                    new_text=suggestion_row.new_text,
                    author=suggestion_row.author,
                    date=suggestion_row.proposed_at.isoformat(),
                ),
            )
        )

    pending = 0
    rejected = 0
    for suggestion in suggestions:
        decision = verdict_by_id.get(suggestion.feedback_id)
        if decision is None or decision.verdict == ReviewVerdict.PENDING:
            pending += 1
        elif decision.verdict == ReviewVerdict.REJECTED:
            rejected += 1

    material = SourceMaterial(context.workspace, context.policy)
    original_bytes = material.read_permitted(
        request.source_key,
        root_id=request.source_root_id,
        capability=CapabilityId.SOURCE_READ.value,
    )
    approved = _approved_suggestions(suggestions, verdict_by_id)
    folded = fold_approved_edits(original_bytes, approved)
    return ReviewPreview(
        project_id=request.project_id,
        input_version_id=request.input_version_id,
        applied=len(folded.applied),
        pending=pending,
        rejected=rejected,
        affected_paragraphs=tuple(sorted({s.edit.paragraph for s in folded.applied})),
        edits=tuple(
            PreviewEditSummary(
                feedback_id=suggestion.feedback_id,
                part=suggestion.edit.part,
                paragraph=suggestion.edit.paragraph,
                old_text=suggestion.edit.old_text,
                new_text=suggestion.edit.new_text,
                author=suggestion.edit.author,
            )
            for suggestion in folded.applied
        ),
        marked_sha256=hashlib.sha256(folded.marked_bytes).hexdigest(),
        marked_size_bytes=len(folded.marked_bytes),
        clean_sha256=hashlib.sha256(folded.clean_bytes).hexdigest(),
        clean_size_bytes=len(folded.clean_bytes),
        original_sha256=hashlib.sha256(original_bytes).hexdigest(),
        original_size_bytes=len(original_bytes),
    )


def export_deliverables(
    context: ApplicationContext,
    request: ExportDeliverablesRequest,
    *,
    resume: bool = False,
) -> DeliverablesExport:
    """The four deliverables of one closed binding, read from its manifest.

    **The manifest is the export's authority.** The dossier names the task,
    the input version, the output version and the two publication receipts;
    the drafts' bytes are read back through the artefact layer under the
    policy's own verdict, and each is hash-checked against the digest the
    manifest binds — an export whose bytes had drifted from the binding
    would carry a deliverable nobody signed for (execution plan §7.3's
    digest check, at the export's door).

    **The response table and the quality report are rendered from the
    manifest, not re-derived.** The renderers are the deliverables' own
    (LC-P3-04's), and they take the manifest's own JSON — the same bytes
    the binding wrote — so a report that says a change landed says it
    because the chain recorded it, not because the export re-counted.

    **A resumed export lands the files it completes, and re-lands the ones
    it cannot trust.** ``resume`` writes each deliverable into the task
    output area under the relative path the export names, but only after
    checking what is already there: a file whose bytes hash to the
    deliverable's own digest is left untouched, and a file that is missing,
    short, or hashes differently is written again whole. An interruption
    between two writes therefore costs one re-export, not a corrupt
    deliverable — the check is the manifest's own binding, so "already done"
    means "byte-identical to what the binding recorded", never "the file
    happens to exist". The four files land through the one atomic write
    point, so a crash mid-write leaves the old file or the new one, never a
    half-written deliverable.

    :param resume: write the deliverables into the task output area,
        skipping the ones already complete and re-exporting the rest.
    :raises ApplicationRefusedError: the project is not there, the dossier
        artefact is not there or is not a manifest, the manifest binds
        another project, or a draft's bytes no longer hash to what the
        manifest binds.
    """
    from pathlib import PurePosixPath

    from labcairn.application.artifacts import read_artifact
    from labcairn.papers.binding import DossierManifest
    from labcairn.reports.quality_report import render_quality_report_markdown
    from labcairn.reports.receipt import ArtifactKind
    from labcairn.reports.response_table import render_response_table_markdown

    _require_project(context, request.project_id)
    dossier = read_artifact(context, request.dossier_artifact_id)
    if dossier.receipt.kind is not ArtifactKind.MANIFEST:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the artefact {request.dossier_artifact_id!r} is a "
            f"{dossier.receipt.kind.value!r} receipt, not a dossier manifest. "
            "The deliverables export reads the binding's own manifest, and "
            "another artefact names no binding to export.",
        )
    manifest = DossierManifest.model_validate_json(dossier.content.decode("utf-8"))
    if manifest.project_id != request.project_id:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the dossier {request.dossier_artifact_id!r} binds the project "
            f"{manifest.project_id!r}, not {request.project_id!r}. A dossier "
            "is exported to the project it binds, or not at all.",
        )

    marked = read_artifact(context, manifest.marked_receipt_id)
    clean = read_artifact(context, manifest.clean_receipt_id)
    marked_sha256 = hashlib.sha256(marked.content).hexdigest()
    clean_sha256 = hashlib.sha256(clean.content).hexdigest()
    if marked_sha256 != manifest.marked_sha256:
        raise ApplicationRefusedError(
            ApplicationRefusal.SOURCE_DRIFTED,
            f"the marked draft {manifest.marked_receipt_id!r} hashes to "
            f"{marked_sha256}, but the dossier binds {manifest.marked_sha256}. "
            "The bytes on disk are not the bytes the binding recorded, and an "
            "export of them would carry a deliverable nobody bound.",
        )
    if clean_sha256 != manifest.clean_sha256:
        raise ApplicationRefusedError(
            ApplicationRefusal.SOURCE_DRIFTED,
            f"the clean draft {manifest.clean_receipt_id!r} hashes to "
            f"{clean_sha256}, but the dossier binds {manifest.clean_sha256}. "
            "The bytes on disk are not the bytes the binding recorded, and an "
            "export of them would carry a deliverable nobody bound.",
        )

    manifest_json = dossier.content.decode("utf-8")
    response_table = render_response_table_markdown(manifest_json)
    quality_report = render_quality_report_markdown(manifest_json)
    # **The rendered deliverables are named beside the drafts they answer.**
    # They are rendered, not written — the caller decides where they land —
    # and the suggested name is the dossier's own directory, so one
    # revision's four deliverables sit together on the reader's disk too.
    base = PurePosixPath(dossier.receipt.relative_path).parent
    deliverables = (
        DeliverableFile(
            kind="marked",
            relative_path=marked.receipt.relative_path,
            content=marked.content,
            sha256=marked_sha256,
            size_bytes=len(marked.content),
        ),
        DeliverableFile(
            kind="clean",
            relative_path=clean.receipt.relative_path,
            content=clean.content,
            sha256=clean_sha256,
            size_bytes=len(clean.content),
        ),
        DeliverableFile(
            kind="response_table",
            relative_path=(base / "response-table.md").as_posix(),
            content=response_table,
            sha256=hashlib.sha256(response_table).hexdigest(),
            size_bytes=len(response_table),
        ),
        DeliverableFile(
            kind="quality_report",
            relative_path=(base / "quality-report.md").as_posix(),
            content=quality_report,
            sha256=hashlib.sha256(quality_report).hexdigest(),
            size_bytes=len(quality_report),
        ),
    )
    if resume:
        _resume_deliverable_writes(context, deliverables)
    return DeliverablesExport(
        project_id=request.project_id,
        dossier_artifact_id=request.dossier_artifact_id,
        task_id=manifest.task_id,
        input_version_id=manifest.input_version_id,
        output_version_id=manifest.output_version_id,
        marked_receipt_id=manifest.marked_receipt_id,
        clean_receipt_id=manifest.clean_receipt_id,
        edge_id=manifest.edge_id,
        deliverables=deliverables,
    )


def _resume_deliverable_writes(
    context: ApplicationContext,
    deliverables: tuple[DeliverableFile, ...],
) -> None:
    """Land each deliverable that is not already complete, through the write point.

    **"Already complete" is a hash comparison, not a presence check.** A file
    left behind by an interrupted export is trusted only when its bytes hash
    to the digest the binding recorded; everything else — missing, truncated,
    or carrying bytes nobody bound — is written again whole. One write point,
    one atomic replace per file: the resumed export either leaves the old
    bytes or the bound bytes, never a half-written deliverable.
    """
    from labcairn.workspace.outputs import TaskOutputArea

    area = TaskOutputArea(context.workspace)
    for deliverable in deliverables:
        path = context.workspace.path_in(
            deliverable.relative_path, context.workspace.output_root.root_id
        ).real_path
        if path.is_file():
            try:
                if hashlib.sha256(path.read_bytes()).hexdigest() == deliverable.sha256:
                    continue
            except OSError:
                pass  # unreadable is not complete: fall through and rewrite it
        area.write(deliverable.relative_path, deliverable.content)


def _open_binding_from_store(
    context: ApplicationContext, request: ApplyReviewRequest
) -> BindingOpened:
    """Open the binding, with the stored suggestions as the suggestion source.

    **The suggestions come from the store, and the store only.** The
    binding's suggestion source is a function; here it reads this module's
    own table, so what the apply step applies is what the workbench showed
    the reviewer — the same bytes, not a re-derivation.
    """
    from labcairn.editing.drafts import ApprovedEdit
    from labcairn.papers.binding import open_binding
    from labcairn.papers.feedback import FeedbackEvent

    session = context.store.session

    def stored_suggestions(event: FeedbackEvent) -> ApprovedEdit | None:
        row = session.get(ReviewSuggestionRow, event.feedback_id)
        if row is None:
            return None
        return ApprovedEdit(
            part=row.part,
            paragraph=row.paragraph,
            old_text=row.old_text,
            new_text=row.new_text,
            author=row.author,
            date=row.proposed_at.isoformat(),
        )

    return open_binding(
        context,
        project_id=request.project_id,
        version_id=request.input_version_id,
        source_root_id=request.source_root_id,
        source_key=request.source_key,
        suggest=stored_suggestions,
    )
