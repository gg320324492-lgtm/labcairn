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

import time
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse

from labcairn.api.contracts import (
    AnalysisBody,
    ApprovalBody,
    ApprovalUseBody,
    ClaimBody,
    CommentResponses,
    GuidanceRuleVerdictBody,
    Health,
    ReportBody,
    SessionInfo,
    StageBody,
    Trajectory,
)
from labcairn.api.events import EventSource, sse_frame
from labcairn.api.guards import OriginPolicy
from labcairn.api.session import SessionToken
from labcairn.application import (
    ApplicationContext,
    ApprovalConsumed,
    ApprovalGranted,
    ApprovalRequested,
    ArtifactView,
    ClaimRecorded,
    ClaimRequest,
    FigureRequest,
    FigureRun,
    ProjectGraph,
    ReportRendered,
    ReportRequest,
    SourceAddress,
    SourceView,
    StageRun,
    TaskPlan,
    TaskState,
    TaskStep,
    consume_approval,
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
from labcairn.application.context import approval_ledger_for
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.application.stages import StageRequest, StageWork
from labcairn.core.ids import ApprovalId
from labcairn.evidence.record import EvidenceRecord
from labcairn.guidance.models import GuidanceRule
from labcairn.guidance.rules import confirm_rule, dispute_rule
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
    """
    source = _event_source(request)

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
