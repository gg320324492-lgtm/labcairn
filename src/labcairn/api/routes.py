"""The routes: parse, call the layer, render.

Every handler here is three lines of work. It reads what it needs from the
request, calls one operation of :mod:`labcairn.application`, and returns what
that operation returned. A handler that reached past the layer would be a
handler that could grant itself a permission the CLI would not — the seam
exists so that a guard applied to an operation reaches every caller, and a
route that reads the store itself is a caller the guard does not reach.

**The response models are the layer's models.** Not copies of them: the same
classes. §1.4.2's decision is that the CLI and the API serve the same bytes,
and the way to keep that true is for there to be one model rather than two
that agree until somebody changes one of them. A route that returned a
bespoke "API view" of a task would be the second spelling the plan warns
about, and the web app would then be showing the API's idea of a task rather
than the task.

The request bodies are the exception, and they are the API's own because the
CLI has no request bodies to share: a web request has to say what it wants in
a shape the wire can carry.

The refusals
------------

A handler does not catch a refusal. :class:`~labcairn.application.refusal.ApplicationRefusedError`
is turned into a response by the application's own handler, so every refusal
from every route is the same status code and the same two fields — and a
handler that caught one and re-rendered it would be a second spelling of the
refusal as well.
"""

from __future__ import annotations

import base64
import time
import uuid
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse

from labcairn.api.contracts import (
    AnalysisBody,
    ApplyReviewBody,
    ApprovalBody,
    ApprovalUseBody,
    ClaimBody,
    ClaimExtractionBody,
    CommentResponses,
    DeliverableFileWire,
    DeliverablesExportWire,
    GuidanceRulePublishBody,
    GuidanceRuleVerdictBody,
    Health,
    IssueKeys,
    IssueRecordBody,
    IssueStatusBody,
    MeetingIngestBody,
    PptIngestBody,
    ProposalAcceptanceBody,
    ReportBody,
    ReviewDecisionBody,
    ReviewSuggestBody,
    ReviewSuggestionBody,
    ReviewSuggestRun,
    SessionInfo,
    StageBody,
    TaskSelectBody,
    Trajectory,
)
from labcairn.api.events import EventSource, UnwiredEventSource, sse_frame, unwired_refusal
from labcairn.api.guards import OriginPolicy
from labcairn.api.selection import TaskSelector
from labcairn.api.session import SessionToken
from labcairn.application import (
    ApplicationContext,
    ApprovalConsumed,
    ApprovalGranted,
    ApprovalRequested,
    ArtifactView,
    ClaimExtractionBackend,
    ClaimRecorded,
    ClaimRequest,
    ExtractClaimRequest,
    FigureRequest,
    FigureRun,
    ProjectGraph,
    ProposalSettled,
    ReportRendered,
    ReportRequest,
    SourceAddress,
    SourceView,
    StageRun,
    TaskPlan,
    TaskState,
    TaskStep,
    confirm_proposal,
    consume_approval,
    extract_claim,
    grant_approval,
    inspect_source,
    list_artifacts,
    list_source_addresses,
    list_sources,
    list_task_records,
    list_tasks,
    read_artifact,
    read_comments,
    read_edits,
    read_guidance_rule,
    read_guidance_rules,
    read_plan,
    read_project_graph,
    read_response_states,
    read_steps,
    read_task_state,
    record_claim,
    render_report,
    request_approval,
    run_figure,
    run_stage,
)
from labcairn.application.approvals import ApprovalRequest, ApprovalUse
from labcairn.application.chain import read_issue_keys
from labcairn.application.context import approval_ledger_for
from labcairn.application.issues import (
    IssueData,
    IssueStatusUpdate,
    list_issues,
    record_issue,
    update_issue_status,
)
from labcairn.application.meeting_text import (
    MeetingHit,
    MeetingTextIngested,
    ingest_meeting_text,
    search_meeting_text,
)
from labcairn.application.model_suggestions import (
    MODEL_SUGGESTION_MODE_REAL,
    ModelSuggestionBackend,
    SuggestionLoopConfig,
    parse_approval_ids,
    suggest_for_version,
)
from labcairn.application.ppt_deck import PptDeckIngested, PptHit, ingest_ppt_deck, search_ppt_deck
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.application.review import (
    ApplyReviewRequest,
    ExportDeliverablesRequest,
    ReviewApplyResult,
    ReviewDecisionData,
    ReviewManuscript,
    ReviewOpinions,
    ReviewPreview,
    ReviewSuggestionData,
    apply_review,
    export_deliverables,
    preview_review_apply,
    read_review_manuscript,
    read_review_opinions,
    record_review_decision,
    record_review_suggestion,
)
from labcairn.application.stages import StageRequest, StageWork
from labcairn.application.trajectory import (
    TrajectoryHit,
    UsableRule,
    search_trajectory,
    usable_guidance,
)
from labcairn.core.ids import ApprovalId, TaskId, is_uuid7, new_id
from labcairn.evidence.record import EvidenceRecord
from labcairn.guidance.models import GuidanceRule
from labcairn.guidance.rules import (
    confirm_rule,
    dispute_rule,
    publish_rule_to_group,
    retract_rule_from_group,
)
from labcairn.runtime.event import EventStreamPage, EventStreamRequest
from labcairn.runtime.lifecycle import Task

#: The routes of the local API. A router rather than a set of decorators on
#: one app, so that the contract can be read from an app that carries the
#: routes and none of the state.
router = APIRouter()


def _context(request: Request) -> Iterator[ApplicationContext]:
    """The application context this request is about.

    Read from the app's state rather than closed over, so that the same
    router serves the running service and the contract document.

    **A request owns its session, and this is where that ownership starts and
    ends.** The context the app holds is the request-independent part — the
    workspace, the policy, the ledger and the task id — and the store it
    carries is one session, which is exactly what must not be shared: a
    SQLAlchemy ``Session`` is not thread-safe, every handler here is a plain
    ``def``, and so FastAPI runs them in a threadpool, at the same time, on
    the same session. One thread's rollback then discards another thread's
    reads — a request is answered "no such task" for a task that is there —
    and the SQLite driver, called from two threads at once, can take the
    whole process down.

    So the request forks the store onto a session of its own and closes it
    when the request is over. Closing and not committing: a unit of work that
    was not committed is one ADR-0003 C3 says rolls back, and a commit would
    write anything left pending. Every write commits inside
    :meth:`~labcairn.db.repository.TaskStore.unit`, so by the time the
    request is over there is nothing pending and the close discards nothing.

    The teardown runs **after the response has been sent** — FastAPI closes a
    dependency's generator once the response is done, not when the handler
    returns — so a streamed body holds its session for as long as it streams.
    """
    base = cast(ApplicationContext, request.app.state.context)
    forked = base.store.fork()
    context = replace(base, store=forked, ledger=approval_ledger_for(forked))
    try:
        yield context
    finally:
        context.store.session.close()


def _event_source(request: Request) -> EventSource:
    """Where the event stream reads from."""
    return cast(EventSource, request.app.state.event_source)


# --------------------------------------------------------------------------- #
# the service
# --------------------------------------------------------------------------- #


@router.get("/health", response_model=Health, tags=["service"])
def get_health(request: Request) -> Health:
    """What the service is, and where it listens.

    Dull on purpose: it is the one response a person may read aloud, so it
    carries the address and the origins and the task, and no token.
    """
    state = request.app.state
    context = cast(ApplicationContext, state.context)
    origins = cast(OriginPolicy, state.origins)
    return Health(
        status="ok",
        host=cast(str, state.host),
        port=cast(int, state.port),
        origins=tuple(sorted(origins.allowed)),
        task_id=str(context.task_id),
    )


@router.get("/session", response_model=SessionInfo, tags=["service"])
def get_session(request: Request, response: Response) -> SessionInfo:
    """The token a client presents, and where the token was written.

    **The one response that carries the token**, and its safety rests on two
    things this service does *not* do — so they are named here rather than
    left to the reader to work out:

    * it sends no ``Access-Control-Allow-Origin``, so the browser's
      cross-origin read rule applies and a page on another site cannot read
      this response; and
    * the response is ``application/json``, which a browser refuses to run
      as a classic script, so ``<script src=".../session">`` in another
      page executes nothing.

    ``X-Content-Type-Options: nosniff`` is the third: the browser must not
    decide that the bytes are something else and run them.

    The origin guard is the fourth, and it is the one that refuses a request
    outright: a request that *carries* a foreign origin never reaches this
    handler. The absences above cover the request that carries none — a
    subresource load, which the browser does not put an origin on; the
    fetch-metadata rule is what refuses that one.

    All of it is absences, and an absence is not a property until something
    watches it, which is why ``tests/test_api.py`` has a test for each.
    """
    response.headers["X-Content-Type-Options"] = "nosniff"
    token = cast(SessionToken, request.app.state.session)
    return SessionInfo(token=token.value, path=str(token.path))


# --------------------------------------------------------------------------- #
# the task
# --------------------------------------------------------------------------- #


@router.get("/tasks", response_model=list[Task], tags=["task"])
def get_tasks(context: Annotated[ApplicationContext, Depends(_context)]) -> list[Task]:
    """Every task in this workspace's store, oldest first."""
    return list(list_tasks(context))


@router.get("/task", response_model=TaskState, tags=["task"])
def get_task_state(context: Annotated[ApplicationContext, Depends(_context)]) -> TaskState:
    """The task, its runs, its stages, its artefacts and its approvals.

    One value, one read — the layer's :class:`~labcairn.application.tasks.TaskState`,
    which is the same value the CLI's ``task status --json`` prints.
    """
    return read_task_state(context)


def _selected_task_id(raw: str) -> TaskId:
    """The task id a selection names, or the layer's refusal.

    The same validation the CLI's ``--task`` does, in the same vocabulary: a
    malformed id is ``arguments_invalid`` and not a schema error, because a
    caller that branches on the service's reasons should not have to branch
    on a second shape for the one field it supplied.
    """
    try:
        parsed = uuid.UUID(raw)
    except ValueError as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"{raw!r} is not a task id: task ids are UUIDv7.",
        ) from error
    if not is_uuid7(parsed):
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"{raw!r} is not a task id: task ids are UUIDv7.",
        )
    return TaskId(parsed)


@router.post("/task/select", response_model=Health, tags=["task"])
def post_task_select(
    body: TaskSelectBody,
    request: Request,
    context: Annotated[ApplicationContext, Depends(_context)],
) -> Health:
    """Bind the service to another task in this workspace, and return the binding.

    **This is a change, so it presents the session token** — the guard asks
    for it on every method that is not a read, and this route is a POST for
    exactly that reason. What it changes is the workspace's selection, not the
    store: the task's own rows are left alone, and the next request is about
    the task this one named.

    **A task the store does not hold is refused before anything moves.** The
    selector validates through the request's own session, and only then
    persists the selection, so a typo cannot leave the workspace pointing at
    a task that does not exist.

    **Already-open streams are not re-bound.** Each stream reads the task it
    was opened for; a selection decides what requests made after it are about.
    """
    selector = cast(TaskSelector, request.app.state.select_task)
    base = cast(ApplicationContext, request.app.state.context)
    request.app.state.context = selector(base, context, _selected_task_id(body.task_id))
    return get_health(request)


@router.get("/plan", response_model=TaskPlan, tags=["task"])
def get_plan(context: Annotated[ApplicationContext, Depends(_context)]) -> TaskPlan:
    """The declared workflow and how far this task has got through it."""
    return read_plan(context)


@router.get("/steps", response_model=list[TaskStep], tags=["task"])
def get_steps(context: Annotated[ApplicationContext, Depends(_context)]) -> list[TaskStep]:
    """The runtime stages the store holds, with the run each belonged to."""
    return list(read_steps(context))


# --------------------------------------------------------------------------- #
# the material
# --------------------------------------------------------------------------- #


@router.get("/sources", response_model=list[SourceView], tags=["source"])
def get_sources(context: Annotated[ApplicationContext, Depends(_context)]) -> list[SourceView]:
    """The material this task is bound to, in the order it bound them."""
    return list(list_sources(context))


@router.get("/sources/{source_id}", response_model=SourceView, tags=["source"])
def get_source(
    source_id: str, context: Annotated[ApplicationContext, Depends(_context)]
) -> SourceView:
    """One material, as the ledger holds it."""
    return inspect_source(context, source_id)


@router.get(
    "/sources/{source_id}/addresses",
    response_model=list[SourceAddress],
    tags=["source"],
)
def get_source_addresses(
    source_id: str, context: Annotated[ApplicationContext, Depends(_context)]
) -> list[SourceAddress]:
    """Every address the ledger holds text for in one material.

    What a claim can be recorded at. Each address's text is the ledger's
    stored text, not the file re-read, and its key is the one ``POST /claims``
    accepts.
    """
    return list(list_source_addresses(context, source_id))


# --------------------------------------------------------------------------- #
# the evidence
# --------------------------------------------------------------------------- #


@router.post("/claims", response_model=ClaimRecorded, status_code=201, tags=["evidence"])
def post_claim(
    body: ClaimBody, context: Annotated[ApplicationContext, Depends(_context)]
) -> ClaimRecorded:
    """Record a claim the material supports, at an address it answers.

    The layer's own operation and the layer's own result, so the record this
    service writes is the record the CLI's ``task claim`` writes. The record is
    ``extracted``: recording is not verifying, and the checks that can confirm
    it are separate acts.

    Nothing is written when the claim is refused: the task must hold the
    material, the material must be readable, and the address must resolve in
    the bytes the ledger holds now.
    """
    return record_claim(
        context,
        ClaimRequest(
            source_id=body.source_id,
            locator_key=body.locator_key,
            kind=body.kind,
            text=body.text,
            span=body.span,
            value=body.value,
            unit=body.unit,
            tolerance=body.tolerance,
        ),
    )


def _parsed_approval_id(value: str) -> ApprovalId:
    """The approval id a caller presented, or the layer's refusal naming why not.

    A malformed id and an id the store does not hold are different refusals
    with different remedies, and both belong to the layer's vocabulary rather
    than to FastAPI's validation error.
    """
    try:
        return ApprovalId(uuid.UUID(value))
    except ValueError as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"{value!r} is not an approval id: approval ids are UUIDs.",
        ) from error


@router.post("/claims/extract", response_model=ClaimRecorded, status_code=201, tags=["evidence"])
def post_claim_extraction(
    body: ClaimExtractionBody,
    request: Request,
    context: Annotated[ApplicationContext, Depends(_context)],
) -> ClaimRecorded:
    """Ask a model for one claim, and record its answer as a proposal.

    **The route writes a proposal and never a person's claim**, even though a
    person pressed the button. The person's act is acceptance, which is a
    different route; keeping the two apart is what lets the ledger say whose
    words each record carries.

    **A service with no provider invocation refuses and writes nothing.** The
    refusal is ``claim_extraction_no_provider`` and it is the honest answer to
    a request this service cannot serve: an empty or invented proposal would
    put words in a model's mouth that no model said. The same rule makes a
    missing approval a refusal before anything leaves the machine.

    The proposal is bound to the locator it names, and the model's quotation
    is checked against the ledger's stored text before the record is written;
    a quotation the material does not contain is refused with
    ``claim_extraction_not_grounded``.
    """
    backend = cast(ClaimExtractionBackend | None, request.app.state.claim_extraction)
    return extract_claim(
        context,
        ExtractClaimRequest(
            source_id=body.source_id,
            locator_key=body.locator_key,
            user_id=body.user_id,
            provider=body.provider,
            model=body.model,
            destination=body.destination,
            subject_ref=body.subject_ref,
            purpose=body.purpose,
        ),
        approval_id=_parsed_approval_id(body.approval_id) if body.approval_id else None,
        grants=() if backend is None else backend.grants,
        send=None if backend is None else backend.send,
        capabilities=None if backend is None else backend.capabilities,
    )


@router.post(
    "/records/{evidence_id}/accept",
    response_model=ProposalSettled,
    tags=["evidence"],
)
def post_record_acceptance(
    evidence_id: str,
    body: ProposalAcceptanceBody,
    context: Annotated[ApplicationContext, Depends(_context)],
) -> ProposalSettled:
    """A person confirms or disputes a model's proposal.

    The layer's own operation and the layer's own result, so the record this
    route writes is the record the CLI's ``task proposal-confirm`` writes.
    **The proposal is not promoted**: the person's own record is written at the
    same address, carrying the proposal's words unchanged (acceptance is
    as-is), and the proposal is superseded and kept.

    ``note`` is required for a dispute and refused for a confirmation; the
    layer enforces both, and the refusal it gives is the one this route
    renders. ``user_id`` is a self-reported string — no account is checked.
    """
    return confirm_proposal(
        context,
        evidence_id,
        user_id=body.user_id,
        verdict=body.verdict,
        note=body.note,
    )


@router.get("/records", response_model=list[EvidenceRecord], tags=["evidence"])
def get_records(context: Annotated[ApplicationContext, Depends(_context)]) -> list[EvidenceRecord]:
    """Every record the ledger holds for this task, and whose words each one is.

    **The record says who wrote it.** ``created_by`` says whether a person
    or a model wrote it and ``created_by_id`` says which, and the
    verification log says who stood behind it — so a workbench can lay a
    model's proposal beside a person's attestation and keep the two apart,
    which is the whole point of the proposals panel and the reason a merged
    view that blurred them would be a lie.

    **And the read is guarded as a read of the task's own rows.** The
    records belong to the task, so the layer asks the policy about the
    task's own area, exactly as it does for the task's state. A record
    names no path of its own and the material it was taken from is not
    named by the record either, so the task's own area is what stands
    between a reader and another task's records.
    """
    return list(list_task_records(context))


# --------------------------------------------------------------------------- #
# the products
# --------------------------------------------------------------------------- #


@router.get("/artifacts", response_model=list[ArtifactView], tags=["artifact"])
def get_artifacts(context: Annotated[ApplicationContext, Depends(_context)]) -> list[ArtifactView]:
    """The artefacts this task has produced, oldest revision first."""
    return list(list_artifacts(context))


@router.get("/artifacts/{artifact_id}", response_model=ArtifactView, tags=["artifact"])
def get_artifact(
    artifact_id: str, context: Annotated[ApplicationContext, Depends(_context)]
) -> ArtifactView:
    """One artefact's receipt: what it is, its hash, its lineage, its staleness."""
    for view in list_artifacts(context):
        if view.receipt.receipt_id == artifact_id:
            return view
    raise ApplicationRefusedError(
        ApplicationRefusal.ARTIFACT_NOT_FOUND,
        f"the store holds no artefact with the id {artifact_id!r} for this task.",
    )


@router.get("/artifacts/{artifact_id}/content", response_class=Response, tags=["artifact"])
def get_artifact_content(
    artifact_id: str, context: Annotated[ApplicationContext, Depends(_context)]
) -> Response:
    """An artefact's bytes, exactly as they are on disk.

    The same bytes the CLI writes and the report's manifest hashes — §1.4.2's
    *"the API serves the same bytes"*. The receipt is at
    ``/artifacts/{id}``; this route is the content and nothing else, so a
    caller that wants to know whether the file still matches the receipt can
    compare the two.

    **The content type is the receipt's own**, never guessed from the file's
    name. A route that guessed would turn a ``.html`` artefact into a
    document, and a document loaded in a frame runs *in this service's
    origin* — where every guard passes and ``/session`` is readable.

    Which is why the response carries ``Content-Security-Policy: sandbox``:
    the document is put in an opaque origin, so it cannot read this
    service's origin, cannot script it and cannot reach the token. The bytes
    are unchanged — the header is on the response, not in the content — so
    the report's own HTML form, which is self-contained with no scripts and
    no external assets, renders exactly as it did.

    ``X-Content-Type-Options: nosniff`` is here for the same reason the
    session response carries it: a browser must not decide that the bytes
    are something else.
    """
    content = read_artifact(context, artifact_id)
    media_type = content.receipt.media_type or "application/octet-stream"
    return Response(
        content=content.content,
        media_type=media_type,
        headers={
            "Content-Security-Policy": "sandbox",
            "X-Content-Type-Options": "nosniff",
        },
    )


# --------------------------------------------------------------------------- #
# consent
# --------------------------------------------------------------------------- #


@router.post(
    "/approvals",
    response_model=ApprovalRequested,
    status_code=201,
    tags=["approval"],
)
def post_approval(
    body: ApprovalBody, context: Annotated[ApplicationContext, Depends(_context)]
) -> ApprovalRequested:
    """Ask for consent, and record the question."""
    return request_approval(
        context,
        ApprovalRequest(
            use=ApprovalUse(
                capability=body.capability,
                arguments=body.arguments,
                root_id=body.root_id,
                resource_key=body.resource_key,
                depends_on=body.depends_on,
            ),
            expires_at=body.expires_at,
            run_id=body.run_id,
            stage_name=body.stage_name,
        ),
    )


@router.post("/approvals/{approval_id}/grant", response_model=ApprovalGranted, tags=["approval"])
def post_approval_grant(
    approval_id: ApprovalId, context: Annotated[ApplicationContext, Depends(_context)]
) -> ApprovalGranted:
    """Record the human's answer to the question."""
    return grant_approval(context, approval_id)


@router.post(
    "/approvals/{approval_id}/consume",
    response_model=ApprovalConsumed,
    tags=["approval"],
)
def post_approval_consume(
    approval_id: ApprovalId,
    body: ApprovalUseBody,
    context: Annotated[ApplicationContext, Depends(_context)],
) -> ApprovalConsumed:
    """Spend a granted approval on one request."""
    return consume_approval(
        context,
        approval_id,
        ApprovalUse(
            capability=body.capability,
            arguments=body.arguments,
            root_id=body.root_id,
            resource_key=body.resource_key,
            depends_on=body.depends_on,
        ),
    )


# --------------------------------------------------------------------------- #
# the work
# --------------------------------------------------------------------------- #


@router.post("/stages", response_model=StageRun, tags=["stage"])
def post_stage(
    request: Request, body: StageBody, context: Annotated[ApplicationContext, Depends(_context)]
) -> StageRun:
    """Run one stage: consent, bookkeeping, the effect, the record.

    The *effect* is not something a web request can supply — the stage bodies
    belong to the packages that own them — so it is the host's, and the
    layer calls it only after the policy has allowed the capability and any
    approval has been consumed.
    """
    return run_stage(
        context,
        StageRequest(
            stage_name=body.stage_name,
            capability=body.capability,
            arguments=body.arguments,
            root_id=body.root_id,
            resource_key=body.resource_key,
            run_id=body.run_id,
            approval_id=body.approval_id,
            depends_on=body.depends_on,
        ),
        _stage_work(request),
    )


def _stage_work(request: Request) -> StageWork:
    """The stage work this service was given, or a refusal.

    There is no default, and there is deliberately no placeholder that does
    nothing: a stage that "ran" and produced nothing would be recorded as a
    stage that ran, and the record would be a lie.
    """
    work = cast(StageWork | None, request.app.state.stage_work)
    if work is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.NOT_IMPLEMENTED,
            "this service was not given a stage work to perform. The effect a "
            "stage performs belongs to the package that owns it, and a web "
            "request cannot supply one; the host that starts the service is "
            "given the work when it starts.",
        )
    return work


# --------------------------------------------------------------------------- #
# the report
# --------------------------------------------------------------------------- #


@router.post("/report", response_model=ReportRendered, tags=["report"])
def post_report(
    body: ReportBody, context: Annotated[ApplicationContext, Depends(_context)]
) -> ReportRendered:
    """Render the task's report, write it as a revision, and record it.

    The layer's own operation and the layer's own result model, so the bytes a
    CLI writes and the bytes this service serves are the same bytes — which is
    G4's exit test, and the reason this route returns
    :class:`~labcairn.application.reports.ReportRendered` rather than a
    service-shaped copy of it.

    **Nothing is written when the report is refused.** The content checks run
    before the first byte of any form is rendered, so a report the material does
    not support leaves no file behind and the caller gets
    ``report_content_refused`` with the check that refused it.
    """
    return render_report(
        context,
        ReportRequest(path=body.path, template_id=body.template_id),
    )


# --------------------------------------------------------------------------- #
# the analysis
# --------------------------------------------------------------------------- #


@router.post(
    "/analysis",
    response_model=FigureRun,
    response_model_by_alias=False,
    tags=["analysis"],
)
def post_analysis(
    body: AnalysisBody, context: Annotated[ApplicationContext, Depends(_context)]
) -> FigureRun:
    """Run one vetted operator and draw the figure its recipe describes.

    The layer's own operation, so the policy is asked about the run on the
    material **and** on the recipe, and the approval is spent by the run path in
    the order that makes a refusal free: a run that cannot resolve its material
    never reaches the consent. The renderer belongs to the analysis package and
    the seam builds it — a web request cannot supply a drawing capability, any
    more than it can supply a stage's effect.
    """
    return run_figure(
        context,
        FigureRequest(
            root_id=body.root_id,
            path=body.path,
            operator_id=body.operator_id,
            recipe=body.recipe,
            parameters=body.parameters,
            approval_id=body.approval_id,
        ),
    )


# --------------------------------------------------------------------------- #
# the events
# --------------------------------------------------------------------------- #


@router.get("/events", response_model=EventStreamPage, tags=["events"])
def get_events(
    request: Request,
    context: Annotated[ApplicationContext, Depends(_context)],
    after_seq: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=5000),
) -> EventStreamPage:
    """A page of the task's events, and the cursor to resume from.

    The page is the runtime's own
    :class:`~labcairn.runtime.event.EventStreamPage`, and every event in it is
    an :class:`~labcairn.runtime.event.Event` — a fact about what happened.
    There is no field in the page that could carry a command, which is what
    makes a reconnecting browser safe: it can ask for what it missed and
    cannot ask for anything to be done.

    The read is on **this request's** session, and so on this request's
    transaction: the page cannot be a partial view of another request's
    work, and this request cannot see another request's uncommitted state.
    """
    return _event_source(request).page(
        context.store.session,
        EventStreamRequest(task_id=context.task_id, after_seq=after_seq, limit=limit),
    )


@router.get("/events/stream", tags=["events"])
def get_event_stream(
    request: Request,
    context: Annotated[ApplicationContext, Depends(_context)],
    after_seq: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=5000),
    follow: bool = Query(True),
    poll_seconds: float = Query(0.25, ge=0.01, le=5.0),
) -> Response:
    """The same page, delivered as a server-sent event stream.

    ``follow=false`` sends what there is and closes; ``follow=true`` keeps
    reading until the client goes away. The frames are the same page the JSON
    endpoint returns, serialised by the same model, so a client that
    reconnects reads the same cursor either way.

    **An unwired stream is refused here, before any response starts.** The
    refusal is the same 403 and the same two fields ``GET /events`` answers
    with, and it is raised while the request still has an answer it can be
    given. It used to be raised inside ``frames()``, which runs after the
    ``200`` and ``text/event-stream`` headers have been sent: at that point a
    refusal cannot become a response, and what the service wrote instead was a
    traceback — 6,205 bytes for one short stream, measured — into whatever the
    caller had attached to the service's output. A caller that captures that
    output in a pipe it does not read has a pipe with a capacity (8,192 bytes
    on Windows, measured), and a writer that blocks on a full pipe is an
    event loop that stops serving: the service answered nothing after one such
    stream, and answered everything again once someone started reading. That
    is O6, and it is recorded in
    ``docs/acceptance/o6-event-stream-stall-2026-11-10.md``. Refusing at the
    entry is what removes the service's half of it; the other half — do not
    hand the service a sink nobody drains — is the harness's rule, and
    ``tests/workbench_serve_support.py`` already keeps it by writing the
    service's log to a file.
    """
    source = _event_source(request)
    if isinstance(source, UnwiredEventSource):
        raise unwired_refusal()

    def frames() -> Iterator[str]:
        """The stream's own session, for the life of the stream.

        **The stream opens a session when it starts and closes it when it
        ends**, and it holds a transaction only while it is reading. The
        store's engine opens every transaction with ``BEGIN IMMEDIATE``, so a
        session that is still in a transaction holds SQLite's *write* lock —
        and a stream that held it between its polls would refuse every other
        request in the service, for as long as the client stayed connected.
        So each poll ends its transaction before the next one begins, and the
        lock is let go between them.

        The session is the stream's own and not the request's: the request's
        session belongs to the request, and the stream's session to the
        stream. Each is closed by whoever opened it, at the moment that
        thing ended.
        """
        session = context.store.fork().session
        try:
            cursor = after_seq
            while True:
                page = source.page(
                    session,
                    EventStreamRequest(task_id=context.task_id, after_seq=cursor, limit=limit),
                )
                # The read is over; let the write lock go before the next poll
                # and before the frame is sent.
                session.rollback()
                if page.events:
                    cursor = page.next_after_seq
                    yield sse_frame(page)
                if not follow:
                    return
                if not page.events:
                    time.sleep(poll_seconds)
        finally:
            session.close()

    return StreamingResponse(
        frames(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --------------------------------------------------------------------------- #
# the mentor line
# --------------------------------------------------------------------------- #


@router.get("/trajectory", response_model=Trajectory, tags=["mentor"])
def get_trajectory(
    context: Annotated[ApplicationContext, Depends(_context)],
    issue_key: Annotated[list[str], Query(default_factory=list)],
) -> Trajectory:
    """The advisor's comments, the edits that answer them, and the responses.

    **The chain's own facts, read through the layer.** The comments are
    ``application.chain``'s, the edits are its, and the states of the
    judgements are its too — so the route spells none of them a second
    time, and a workbench that draws this panel draws the chain.

    **A state is attached to the comment it is about.** The layer answers
    with the states themselves, so the route asks once per comment: a
    reader that had to guess which state belonged to which comment would
    be guessing.

    **And no capability is asked of the task's area.** The chain's rows
    belong to a paper project and name no path of their own, so the
    permission that governs what a reader may be shown is the permission on
    the material, and it is asked where the material is named (ADR-0003 C5).
    """
    comments = read_comments(context, issue_keys=tuple(issue_key))
    edits = read_edits(context, feedback_ids=tuple(comment.feedback_id for comment in comments))
    responses = tuple(
        CommentResponses(
            feedback_id=comment.feedback_id,
            states=read_response_states(context, feedback_ids=(comment.feedback_id,)),
        )
        for comment in comments
    )
    return Trajectory(comments=tuple(comments), edits=edits, responses=responses)


@router.get("/trajectory/issue-keys", response_model=IssueKeys, tags=["mentor"])
def get_trajectory_issue_keys(
    context: Annotated[ApplicationContext, Depends(_context)],
    project_id: Annotated[str, Query(min_length=1)],
    version_id: Annotated[list[str], Query(default_factory=list)],
) -> IssueKeys:
    """The issue keys the chain holds for a project.

    **The outlet the trajectory panel needed and did not have.** The
    chain holds its comments under keys a person gave, and until this route
    the contract could ask for the comments under a key the caller already
    knew — **so a panel could draw one issue and could not say what there
    was to look at.** This route is that list.

    **The list is names, and the names are all it carries.** A key says
    *which problem*, not *what the advisor wrote*: the comments' words, the
    anchored text, the author and the date are **not** in this body. A
    panel that draws this draws names, and a reader who wants the words
    asks for the trajectory under the key.

    **The order is the service's, and the service's is stable.** The
    chain's rows carry no time and no sequence, so the layer sorts the keys
    rather than inventing a chronology, and the panel draws them in the
    order the service answered.

    **And the project is named, and the versions may narrow it.** A
    project the chain does not hold is refused by name — **an empty list
    would say the project has no issues, which is a different fact from
    "there is no such project"** — and a version that does not belong to
    the project is refused rather than ignored, because it would answer
    about a chain that is not this one. Naming no version means the
    project's whole chain.
    """
    return IssueKeys(
        project_id=project_id,
        issue_keys=read_issue_keys(
            context,
            project_id=project_id,
            version_ids=tuple(version_id),
        ),
    )


@router.get("/trajectory/graph", response_model=ProjectGraph, tags=["mentor"])
def get_trajectory_graph(
    context: Annotated[ApplicationContext, Depends(_context)],
    project_id: Annotated[str, Query(min_length=1)],
    version_id: Annotated[list[str], Query(default_factory=list)],
) -> ProjectGraph:
    """The project's versions, and the accepted edges between them.

    **Only accepted edges are here.** An edge nobody accepted is a
    proposal, and a proposal may not decide an order — so the graph a
    reader draws is the one the chain's accepted edges describe. And a
    version the project does not hold is **absent** rather than present: a
    missing round is not a round.

    **The versions are a set, not an order.** The layer answers with the
    versions the project holds among the ones named, and the order is the
    edges' business — a reader that wants the order walks the accepted
    edges, which is the only thing that may decide one.
    """
    return read_project_graph(context, project_id=project_id, version_ids=tuple(version_id))


@router.get("/guidance/rules", response_model=list[GuidanceRule], tags=["mentor"])
def get_guidance_rules(
    context: Annotated[ApplicationContext, Depends(_context)],
) -> list[GuidanceRule]:
    """Every rule the memory holds, each at its highest version.

    **The cases come with the rule.** A counterexample is part of the
    answer and not a footnote beside it, and the layer's read returns both
    in one go — so a workbench that shows a rule shows what it does not
    hold too, and it cannot show the rule without them.
    """
    return list(read_guidance_rules(context))


@router.get("/guidance/rules/{rule_id}", response_model=GuidanceRule, tags=["mentor"])
def get_guidance_rule(
    rule_id: str, context: Annotated[ApplicationContext, Depends(_context)]
) -> GuidanceRule:
    """One rule, with its scope, its source bindings and its counterexamples.

    **A rule that is not there is refused, by name.** The layer refuses it
    and the service renders that refusal the way it renders every other
    one — so a caller that asked for a rule which does not exist learns
    that, and not an empty rule that looks like a rule.
    """
    return read_guidance_rule(context, rule_id=rule_id)


@router.post("/guidance/rules/{rule_id}/confirm", response_model=GuidanceRule, tags=["mentor"])
def post_guidance_rule_confirmation(
    rule_id: str,
    body: GuidanceRuleVerdictBody,
    context: Annotated[ApplicationContext, Depends(_context)],
) -> GuidanceRule:
    """A person confirms or disputes a rule, and the rule says so afterwards.

    **The second-reader rule is the memory's, and this route asks it rather
    than restating it.** Whoever proposed a rule cannot be the one who
    confirms it — one person reading twice is one person reading once with
    extra steps — so a proposer who tries is refused by name, with the
    memory's own reason, and the refusal says who was missing.

    **The answer is the rule itself.** The layer's own
    :class:`~labcairn.guidance.models.GuidanceRule`, carrying the state the
    person's word moved it to and the person who moved it — so a workbench
    that draws the answer draws the rule, and not a second spelling of it.

    **And a dispute carries its reason.** A dispute without a reason is a
    shrug, and the memory refuses one by name rather than storing it. **A
    reason belongs to a dispute**, too: a confirmed rule carries none — the
    schema says so — so a reason given with a confirmation is refused
    rather than quietly dropped.

    **Nothing is written when the door is refused.** The write happens
    inside the store's own unit of work, so a refusal rolls the transaction
    back and the rule keeps the state it had.
    """
    if not body.user_id.strip():
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            "a confirmation nobody signs is not a confirmation. Name the person whose word it is.",
        )
    if body.verdict == "confirmed" and body.reason.strip():
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            "a reason belongs to a dispute, and a confirmed rule carries none: the "
            "memory holds no reason on a rule that stands. Dispute the rule with "
            "the reason instead.",
        )
    return _settle_the_rule(context, rule_id=rule_id, body=body)


def _settle_the_rule(
    context: ApplicationContext,
    *,
    rule_id: str,
    body: GuidanceRuleVerdictBody,
) -> GuidanceRule:
    """The rule, settled by the person's verdict, in one transaction.

    **The transaction is opened here, and not by the handler, because the
    request's session is closed without a commit.** Every write this service
    makes commits inside a unit of work, and the rule memory's own write
    flushes rather than commits — so a rule confirmed through this route
    would be gone the moment the request ended. The unit is the store's own
    boundary: it commits on a clean exit and rolls back on a refusal, so a
    door that says no writes nothing.

    **And the verdict chooses the operation; the operations are the memory's.**
    ``confirmed`` asks the memory to confirm the rule and ``disputed`` asks
    it to dispute the rule — and the second-reader rule, the reason a
    dispute must carry and the closed state machine are all the memory's,
    so a rule the service would have allowed is refused here too.

    **The moment is the wall clock's, the way the ledger's own door takes
    it.** A person's act happens now, and the route says so the same way
    the console does.
    """
    moment = datetime.now(UTC)
    with context.store.unit(context.task_id):
        if body.verdict == "confirmed":
            return confirm_rule(
                context,
                rule_id=rule_id,
                confirmed_by=body.user_id,
                now=moment,
            )
        return dispute_rule(
            context,
            rule_id=rule_id,
            reason=body.reason,
            disputed_by=body.user_id,
            now=moment,
        )


__all__ = ["router"]


# --------------------------------------------------------------------------- #
# the review workbench
# --------------------------------------------------------------------------- #


@router.get("/review/opinions", response_model=ReviewOpinions, tags=["review"])
def get_review_opinions(
    context: Annotated[ApplicationContext, Depends(_context)],
    project_id: Annotated[str, Query(min_length=1)],
    version_id: Annotated[str, Query(min_length=1)],
) -> ReviewOpinions:
    """The opinions one review round holds, with their suggestions and verdicts.

    **One read, three separate facts.** The comment and its anchor are the
    chain's; the suggestion is what the model proposed; the decision is what
    the reviewer did with it — and the two stored records are never merged
    into one (ADR-0016's rule, at the surface).
    """
    return read_review_opinions(context, project_id=project_id, version_id=version_id)


@router.get("/review/manuscript", response_model=ReviewManuscript, tags=["review"])
def get_review_manuscript(
    context: Annotated[ApplicationContext, Depends(_context)],
    project_id: Annotated[str, Query(min_length=1)],
    version_id: Annotated[str, Query(min_length=1)],
) -> ReviewManuscript:
    """The manuscript's paragraphs, in document order, in the accepted view.

    The middle column's text. The paragraph numbering is the feedback
    anchors' own — 1-based, document order — so the workbench's scroll-sync
    is an equality test rather than a lookup.
    """
    return read_review_manuscript(context, project_id=project_id, version_id=version_id)


@router.post(
    "/review/suggestion", response_model=ReviewSuggestionData, status_code=201, tags=["review"]
)
def post_review_suggestion(
    body: ReviewSuggestionBody,
    context: Annotated[ApplicationContext, Depends(_context)],
) -> ReviewSuggestionData:
    """Store one suggestion the model proposed, verbatim in the seam's units.

    **A proposal is a record, not a decision.** This grants nothing, changes
    nothing, and applies nothing; the verdict is ``POST /review/decision``'s
    to take.
    """
    return record_review_suggestion(
        context,
        project_id=body.project_id,
        version_id=body.version_id,
        feedback_id=body.feedback_id,
        part=body.part,
        paragraph=body.paragraph,
        old_text=body.old_text,
        new_text=body.new_text,
        author=body.author,
    )


@router.post("/review/suggest", response_model=ReviewSuggestRun, status_code=201, tags=["review"])
def post_review_suggest(
    body: ReviewSuggestBody,
    request: Request,
    context: Annotated[ApplicationContext, Depends(_context)],
) -> ReviewSuggestRun:
    """Run the suggestion loop over one version's pending opinions.

    **The mode names who answers.** ``substitute`` asks the local stand-in
    and spends nothing — nothing leaves the machine, so nothing needs an
    approval. ``real`` asks the authorised model and spends one
    digest-bound approval per opinion: the caller presents
    ``approval_ids``, one per opinion it holds consent for, and an opinion
    without one is recorded as unauthorised and skipped, not asked.

    **The response is the account, not the suggestions.** The suggestions
    land in the store under their own route's read
    (``GET /review/opinions``); this response says what the run cost, what
    it produced, and why it stopped — the budget's own record (G0 §5).
    """
    backend = cast(ModelSuggestionBackend | None, request.app.state.model_suggestions)
    if body.mode == MODEL_SUGGESTION_MODE_REAL and backend is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.MODEL_SUGGESTION_NO_PROVIDER,
            "no real-model transport is wired into this service, so there is "
            "nothing to ask. A real run is refused rather than simulated: an "
            "invented suggestion would put words in a model's mouth that no "
            "model said.",
        )
    run = suggest_for_version(
        context,
        run_id=str(new_id()),
        project_id=body.project_id,
        version_id=body.version_id,
        mode=body.mode,
        provider="" if backend is None else backend.provider,
        transport=None if backend is None else backend.real_transport,
        approvals=parse_approval_ids(body.approval_ids),
        grants=() if backend is None else backend.grants,
        destination="" if backend is None else backend.destination,
        subject_ref=body.project_id,
        config=SuggestionLoopConfig(
            max_requests=body.max_requests,
            max_tokens=body.max_tokens,
            max_consecutive_failures=body.max_consecutive_failures,
            retry_attempts=body.retry_attempts,
        ),
    )
    return ReviewSuggestRun(
        run_id=run.run_id,
        project_id=run.project_id,
        version_id=run.version_id,
        mode=run.mode,
        model_id=run.model_id,
        requests_made=run.requests_made,
        tokens_estimated=run.tokens_estimated,
        stopped_reason=run.stopped_reason,
        suggestions_recorded=run.suggestions_recorded,
        opinions_skipped=run.opinions_skipped,
        started_at=run.started_at.isoformat(),
        finished_at=run.finished_at.isoformat(),
    )


@router.post("/review/decision", response_model=ReviewDecisionData, tags=["review"])
def post_review_decision(
    body: ReviewDecisionBody,
    context: Annotated[ApplicationContext, Depends(_context)],
) -> ReviewDecisionData:
    """Store the reviewer's verdict on one opinion's suggestion.

    **The verdict is the reviewer's word, written once.** A revised verdict
    overwrites the standing one under the same id; the apply step reads the
    verdicts from the store, never from the request that applies them.
    """
    return record_review_decision(
        context,
        project_id=body.project_id,
        feedback_id=body.feedback_id,
        verdict=body.verdict,
        operator=body.operator,
        needs_evidence=body.needs_evidence,
    )


@router.post("/review/apply", response_model=ReviewApplyResult, tags=["review"])
def post_review_apply(
    body: ApplyReviewBody,
    context: Annotated[ApplicationContext, Depends(_context)],
) -> ReviewApplyResult:
    """Run the stored, approved set through the binding and close the round.

    **The decisions come from the store.** The workbench does not send
    verdicts with the apply call; the binding reads what the reviewer wrote,
    which is what makes the applied set auditable after the fact. The
    binding's own duplicate, staleness and consent guards are the guards —
    this route adds none.
    """
    return apply_review(
        context,
        ApplyReviewRequest(
            project_id=body.project_id,
            input_version_id=body.input_version_id,
            source_root_id=body.source_root_id,
            source_key=body.source_key,
            output_label=body.output_label,
            window_end=body.window_end,
        ),
    )


@router.post("/review/preview", response_model=ReviewPreview, tags=["review"])
def post_review_preview(
    body: ApplyReviewBody,
    context: Annotated[ApplicationContext, Depends(_context)],
) -> ReviewPreview:
    """Measure what the apply round would do, before anything is written.

    **The preview is the dry run the workbench shows before the operator
    commits** (execution plan §3.2: *应用修改前必须预览修改数量、影响段落和
    输出变化摘要*). It takes the same body the apply route takes, because
    it answers the apply's question about the same round; it writes
    nothing — no file, no store row — and the digests it returns are the
    sha256 of the drafts the apply would publish. A caller applies the
    round and compares; the equality is the preview's own witness.
    """
    return preview_review_apply(
        context,
        ApplyReviewRequest(
            project_id=body.project_id,
            input_version_id=body.input_version_id,
            source_root_id=body.source_root_id,
            source_key=body.source_key,
            output_label=body.output_label,
            window_end=body.window_end,
        ),
    )


@router.get("/review/deliverables", response_model=DeliverablesExportWire, tags=["review"])
def get_review_deliverables(
    context: Annotated[ApplicationContext, Depends(_context)],
    project_id: Annotated[str, Query(min_length=1)],
    dossier_artifact_id: Annotated[str, Query(min_length=1)],
) -> DeliverablesExportWire:
    """The four deliverables of one closed binding, in one export.

    **One round, four files, one manifest.** The dossier names the binding;
    the marked and the clean drafts are read back and hash-checked against
    it, and the response table and the quality report are rendered from the
    manifest's own JSON. The bytes travel base64-encoded, because a DOCX is
    a zip and a zip is not text; the sha256 beside each is over the decoded
    bytes, so a client decodes, saves and verifies against the same digest
    the binding recorded (execution plan §7.1's step 9, at the surface).
    """
    export = export_deliverables(
        context,
        ExportDeliverablesRequest(project_id=project_id, dossier_artifact_id=dossier_artifact_id),
    )
    return DeliverablesExportWire(
        project_id=export.project_id,
        dossier_artifact_id=export.dossier_artifact_id,
        task_id=export.task_id,
        input_version_id=export.input_version_id,
        output_version_id=export.output_version_id,
        marked_receipt_id=export.marked_receipt_id,
        clean_receipt_id=export.clean_receipt_id,
        edge_id=export.edge_id,
        deliverables=tuple(
            DeliverableFileWire(
                kind=file.kind,
                relative_path=file.relative_path,
                content_base64=base64.b64encode(file.content).decode("ascii"),
                sha256=file.sha256,
                size_bytes=file.size_bytes,
            )
            for file in export.deliverables
        ),
    )


# --------------------------------------------------------------------------- #
# the pilot's in-system issue record (P4-PILOT §9.4)
# --------------------------------------------------------------------------- #


@router.post("/issues", response_model=IssueData, status_code=201, tags=["review"])
def post_issue(
    body: IssueRecordBody,
    context: Annotated[ApplicationContext, Depends(_context)],
) -> IssueData:
    """Record one problem the trial met, in the system's own record.

    **The record is about something, and it is recorded as seen.** The
    step, the error text and the severity are the trial's own words; the
    two vocabularies -- severity and type -- are closed, and a word
    outside either is refused (422 at the wire, from the body's own
    ``Literal``; by name from the layer, for a caller that reached past
    it). A recorded issue is ``open``; the states after that are
    ``PATCH /issues/{issue_id}/status``'s to walk.
    """
    return record_issue(
        context,
        issue_id=body.issue_id,
        project_id=body.project_id,
        task_id=body.task_id,
        version_id=body.version_id,
        feedback_id=body.feedback_id,
        step=body.step,
        error_text=body.error_text,
        duration_seconds=body.duration_seconds,
        retry_count=body.retry_count,
        severity=body.severity,
        category=body.category,
        reported_by=body.reported_by,
    )


@router.get("/issues", response_model=list[IssueData], tags=["review"])
def get_issues(
    context: Annotated[ApplicationContext, Depends(_context)],
    project_id: Annotated[str, Query(min_length=1)],
    status: Annotated[str | None, Query()] = None,
    severity: Annotated[str | None, Query()] = None,
) -> list[IssueData]:
    """The project's issues, newest first, narrowed by what is asked for.

    **A filter narrows; it does not refuse.** An empty answer is a fact
    about the trial -- "no blocker has been recorded" -- and not an error.
    A filter that names a word outside the closed vocabulary is refused by
    name from the layer, because a question the record cannot understand
    is not the same as an answer of "none recorded".
    """
    return list(list_issues(context, project_id=project_id, status=status, severity=severity))


@router.patch("/issues/{issue_id}/status", response_model=IssueStatusUpdate, tags=["review"])
def patch_issue_status(
    issue_id: str,
    body: IssueStatusBody,
    context: Annotated[ApplicationContext, Depends(_context)],
) -> IssueStatusUpdate:
    """Move an issue along the four states, refusing a move that skips one.

    **The states are walked, not set.** ``open`` is confirmed;
    ``confirmed`` is fixed -- naming the version that fixed it -- or
    wontfix. A closed issue moves nowhere: reopening it is a new record,
    not an edit of the first. The layer carries the walk, so a caller that
    reached past the wire meets the same refusal by name.
    """
    return update_issue_status(
        context,
        project_id=body.project_id,
        issue_id=issue_id,
        status=body.status,
        fix_version=body.fix_version,
        regression_note=body.regression_note,
    )


# --------------------------------------------------------------------------- #
# multi-source learning: the trajectory index and the usable rules (P4-MS)
# --------------------------------------------------------------------------- #


@router.get("/guidance/usable", response_model=list[UsableRule], tags=["mentor"])
def get_usable_guidance(
    context: Annotated[ApplicationContext, Depends(_context)],
    scope: Annotated[str | None, Query()] = None,
    project_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
) -> list[UsableRule]:
    """The rules a card may cite: mentor-confirmed, still standing, in scope.

    **A candidate is never here.** The listing serves confirmed rules only —
    a proposal reaching a card would be a proposal dressed as a record, and
    the plan's §8.5 makes that a hard line: *unreviewed experience is a
    candidate, not a code of conduct*. A withdrawn rule is not here either;
    the retrieval resolves each rule's sources against the chain at query
    time, so what comes back is what stands for this reader, now.

    **A project narrows the answer without widening it.** With
    ``project_id``, the listing serves the rules learned from that
    project's chain material plus the rules a mentor has published to the
    group (Phase 4 §8.5 / P4-G3); a private rule learned in another
    project is not served. A shared rule's sources still go through the
    permission layer, so a source this reader may not reach is dropped,
    never widened.
    """
    return list(usable_guidance(context, scope=scope, project_id=project_id, limit=limit))


@router.get("/trajectory/search", response_model=list[TrajectoryHit], tags=["review"])
def search_trajectory_route(
    context: Annotated[ApplicationContext, Depends(_context)],
    q: Annotated[str, Query(min_length=1)],
    project_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
) -> list[TrajectoryHit]:
    """Search a paper's revision trajectory, and answer with its provenance.

    **A hit says what was said or changed, and where it came from**: the
    source version, the locator within it, and the content hash. That is
    §8.5's acceptance — a trajectory entry is findable *and* points at the
    opinion and revision position it came from — served from the index the
    ingest wrote.
    """
    return list(search_trajectory(context, query=q, project_id=project_id, limit=limit))


# --------------------------------------------------------------------------- #
# multi-source learning: the deck index (P4-MS, §8.3)
# --------------------------------------------------------------------------- #


@router.get("/ppt/search", response_model=list[PptHit], tags=["review"])
def search_ppt_deck_route(
    context: Annotated[ApplicationContext, Depends(_context)],
    q: Annotated[str, Query(min_length=1)],
    project_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
) -> list[PptHit]:
    """Search a deck's indexed objects, and answer with their provenance.

    **A hit says what the deck says, and which slide and object say it**:
    the text, the 1-based slide number, the object's position and kind, the
    structured locator, and the source fingerprint that ties the hit to the
    file it was read from. That is §8.5's acceptance — a deck's words,
    notes, tables and images are findable *and* point at the correct slide
    or object — served from the index the ingest wrote.
    """
    return list(search_ppt_deck(context, query=q, project_id=project_id, limit=limit))


@router.post("/ppt/ingest", response_model=PptDeckIngested, status_code=201, tags=["review"])
def post_ppt_ingest(
    body: PptIngestBody,
    context: Annotated[ApplicationContext, Depends(_context)],
) -> PptDeckIngested:
    """Index one deck's objects, and report the count and the limitations.

    **The body names where to read; the bytes come from the workspace.**
    The deck is read through the ``source.read`` gate the same way every
    other reader of supplied material reads, and the ingest reports both
    what it indexed and what it honestly could not: ``limitations_recorded``
    counts the extraction problems — a chart this reader does not parse, a
    slide whose part is missing — because §8.3's rule is that an
    unparseable object is a recorded limitation, never an invented
    conclusion.
    """
    return ingest_ppt_deck(
        context,
        project_id=body.project_id,
        root_id=body.root_id,
        resource_key=body.resource_key,
    )


# --------------------------------------------------------------------------- #
# multi-source learning: the meeting-text index (P4-MS, §8.4)
# --------------------------------------------------------------------------- #


@router.get("/meeting/search", response_model=list[MeetingHit], tags=["review"])
def search_meeting_text_route(
    context: Annotated[ApplicationContext, Depends(_context)],
    q: Annotated[str, Query(min_length=1)],
    project_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
) -> list[MeetingHit]:
    """Search indexed meeting text, and answer with its provenance.

    **A hit says what the meeting text says, and which entry or paragraph
    says it**: the text, the record's shape and index, the container's
    timestamp when it has one, the structured locator, and the source
    fingerprint that ties the hit to the file it was read from. That is
    §8.5's acceptance — meeting text is findable *and* points at the
    correct entry or paragraph — served from the index the ingest wrote.
    """
    return list(search_meeting_text(context, query=q, project_id=project_id, limit=limit))


@router.post(
    "/meeting/ingest", response_model=MeetingTextIngested, status_code=201, tags=["review"]
)
def post_meeting_ingest(
    body: MeetingIngestBody,
    context: Annotated[ApplicationContext, Depends(_context)],
) -> MeetingTextIngested:
    """Index one meeting-text file's records, and report the counts.

    **The body names where to read; the bytes come from the workspace.**
    The file is read through the ``source.read`` gate the same way every
    other reader of supplied material reads, and the ingest reports both
    what it indexed and what it honestly could not:
    ``limitations_recorded`` counts the extraction problems — a cue with
    no timing line, a block that is empty — because §8.3's rule is that
    unreadable input is recorded, never fabricated.
    """
    return ingest_meeting_text(
        context,
        project_id=body.project_id,
        root_id=body.root_id,
        resource_key=body.resource_key,
    )


# --------------------------------------------------------------------------- #
# the group sharing of a confirmed rule (Phase 4 §8.5 / P4-G3)
# --------------------------------------------------------------------------- #


@router.post("/guidance/rules/{rule_id}/publish", response_model=GuidanceRule, tags=["mentor"])
def post_guidance_rule_publication(
    rule_id: str,
    body: GuidanceRulePublishBody,
    context: Annotated[ApplicationContext, Depends(_context)],
) -> GuidanceRule:
    """A mentor publishes a confirmed rule to the whole group.

    **Only a rule that stands is shared.** A candidate is unreviewed
    experience and a disputed or withdrawn rule is not standing — the
    layer refuses each by name, because a rule the group may cite is a
    rule a second reader has stood behind (Phase 4 §8.5 / P4-G3).

    **And the publisher is a second reader.** Whoever proposed the rule
    cannot be the one who publishes it — the same rule the confirmation
    carries, asked here rather than restated.

    **Nothing is written when the door is refused.** The write happens
    inside the store's own unit of work, so a refusal rolls the
    transaction back and the rule keeps the scope it had.
    """
    if not body.user_id.strip():
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            "a publication nobody signs is not a publication. Name the mentor whose word it is.",
        )
    moment = datetime.now(UTC)
    with context.store.unit(context.task_id):
        return publish_rule_to_group(
            context, rule_id=rule_id, published_by=body.user_id, now=moment
        )


@router.post("/guidance/rules/{rule_id}/retract", response_model=GuidanceRule, tags=["mentor"])
def post_guidance_rule_retraction(
    rule_id: str,
    context: Annotated[ApplicationContext, Depends(_context)],
) -> GuidanceRule:
    """Retract a rule from the group's reach, leaving the rule itself standing.

    **A retraction of the sharing is not a withdrawal of the rule.** The
    rule's own state is untouched: the group stops seeing a rule its own
    project may still cite. The state machine's ``withdrawn`` keeps its
    meaning — *this stopped being true* — and this door says only *this
    stopped being shared*.

    **Nothing is written when the door is refused.** The write happens
    inside the store's own unit of work, so a refusal rolls the
    transaction back and the rule keeps the scope it had.
    """
    with context.store.unit(context.task_id):
        return retract_rule_from_group(context, rule_id=rule_id)
