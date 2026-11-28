"""The shapes this service speaks: the refusal body, the request bodies, and
the one panel it composes out of the layer's own objects.

The *response* models are not here, and that is the point. They are the
application layer's own models — ``TaskState``, ``TaskPlan``, ``SourceView``,
``ArtifactView`` and the rest — because §1.4.2's decision is that the CLI and
the API serve the same bytes: *"one serialization, two surfaces"*. A model
defined in this package for the API's convenience would be a second spelling
of what the CLI prints, and the CLI's ``--json`` and this API's body would
drift apart the first time one of them changed.

So the only models here are the ones the API owns outright:

* :class:`RefusalBody` — how a refusal is rendered. It carries exactly the
  two fields the layer's :meth:`~labcairn.application.refusal.ApplicationRefusedError.to_payload`
  produces, so the two refusals — the layer's and a guard's — are the same
  shape on the wire and a script branches on one field either way;
* the request bodies, which are the API's own because the CLI has no request
  bodies to share;
* :class:`SessionInfo` and :class:`Health`, which describe **the service**
  — the token it minted and the address it listens on — and there is no
  layer operation that produces either;
* :class:`Trajectory` and :class:`CommentResponses`, which **compose** the
  layer's own objects into the one panel a workbench draws;
* :class:`IssueKeys`, which **names the scope of a list of names** — the
  chain's issue keys, and the project they are the project's.

The composed shapes are not a second model
------------------------------------------

:class:`Trajectory` is a bundle, and **every member of it is the layer's own
object**: the comments are ``application.chain``'s, the edits are its, and
the states of the judgements are its. The bundle adds no field of its own
except the one that ties a state to the comment it is about — and that tie
is a *fact the layer's own read does not spell out*, so the API states it
once, in one place, rather than every reader guessing it.

**A composed shape that re-spelled a member would be the defect this module
exists to prevent.** So a member is carried as the layer carries it, and
the composition is the only thing this package adds.

The refusal body is not a copy of the layer's payload
------------------------------------------------------

It is a *model* of a payload the layer already defines, and the test asserts
the two agree: the body of a refusal response equals the layer's
``to_payload()`` exactly. The layer remains the authority on what a refusal
says; this model is only the schema the OpenAPI document can describe.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from labcairn.application import ChainComment, ChainEdit
from labcairn.application.model_suggestions import SuggestionRequestEntry
from labcairn.application.models import Result
from labcairn.core.ids import ApprovalId, RunId
from labcairn.evidence.states import CheckKind, EvidenceKind
from labcairn.security.capabilities import CapabilityId


class RefusalBody(Result):
    """A refusal, as the two fields every refusal has.

    ``reason`` is the machine-readable half — the thing a script branches on —
    and ``message`` is the human half, which names what was wrong. The pair
    is the layer's own, so the API's error body and the CLI's error body are
    the same bytes.
    """

    reason: str
    message: str


class ApprovalBody(Result):
    """A request for consent, as the API accepts it.

    The shape is the application layer's :class:`~labcairn.application.approvals.ApprovalRequest`
    flattened for the wire: what it covers (``capability``, ``arguments``,
    ``root_id``, ``resource_key``, ``depends_on``) and when it lapses
    (``expires_at``), plus where the operation lives (``run_id``,
    ``stage_name``).
    """

    capability: CapabilityId
    arguments: dict[str, Any] = Field(default_factory=dict)
    root_id: str
    resource_key: str
    depends_on: tuple[str, ...] = ()
    expires_at: datetime
    run_id: RunId | None = None
    stage_name: str = "approval"


class ApprovalUseBody(Result):
    """What an approval is spent on, as the API accepts it.

    The same fields as :class:`ApprovalBody` without the expiry: an approval
    was issued for one moment and is spent on one request, and the moment it
    was issued for is the ledger's business rather than the caller's.
    """

    capability: CapabilityId
    arguments: dict[str, Any] = Field(default_factory=dict)
    root_id: str
    resource_key: str
    depends_on: tuple[str, ...] = ()


class StageBody(Result):
    """A stage run, as the API accepts it.

    The application layer's :class:`~labcairn.application.stages.StageRequest`
    without the work: the *effect* a stage performs belongs to the package
    that owns that effect, and a web request cannot supply one.
    """

    stage_name: str
    capability: CapabilityId
    arguments: dict[str, Any] = Field(default_factory=dict)
    root_id: str
    resource_key: str
    run_id: RunId | None = None
    approval_id: ApprovalId | None = None
    depends_on: tuple[str, ...] = ()


class AnalysisBody(Result):
    """One figure run, as the API accepts it.

    The six fields are the layer's own request, and all of them are required
    except the operator's parameters: the material's root and key, the
    registered operator, the chart recipe, and **the approval that covers exactly
    this set**. The approval is not inferred and not created here — the service
    has `POST /approvals` for asking and `/approvals/{id}/grant` for answering,
    and a run that could mint its own consent would not be a consented run.
    """

    root_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    operator_id: str = Field(min_length=1)
    recipe: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    approval_id: ApprovalId


class ReportBody(Result):
    """A report render, as the API accepts it.

    The application layer's :class:`~labcairn.application.reports.ReportRequest`,
    field for field, and both are required: **the service takes no default for
    either.** Which key the report lives under and which template it is drawn
    from are the caller's claims, and a default here would be the service making
    them — the same reasoning that keeps a stage's effect out of a web request.
    """

    path: str = Field(min_length=1)
    template_id: str = Field(min_length=1)


class ClaimBody(Result):
    """A claim to record, as the API accepts it.

    The application layer's :class:`~labcairn.application.evidence.ClaimRequest`,
    field for field. ``kind`` is the ledger's own vocabulary rather than a
    string this package translates, so an unknown kind is refused by the model
    that defines the kinds; which fields a kind requires is the record model's
    rule, and the service states it nowhere a second time.
    """

    source_id: str = Field(min_length=1)
    locator_key: str = Field(min_length=1)
    kind: EvidenceKind = EvidenceKind.CLAIM
    text: str | None = None
    span: str | None = None
    value: float | None = None
    unit: str | None = None
    tolerance: float | None = None


class RecordVerificationBody(Result):
    """Which rule to run against a record, as the API accepts it.

    The check is the ledger's own closed vocabulary rather than a string this
    package translates, so an unknown check is refused by the model that
    defines the checks. Which of them can verify a claim — C1, C2 and C3, and
    never C4 — is the store's own set, and the layer holds that rule.
    """

    check: CheckKind


class TaskSelectBody(Result):
    """Which task the service should be bound to, as the API accepts it.

    The id is a string and not a parsed id type here, because the refusal for
    a malformed id belongs to the same vocabulary as the refusal for an id the
    store does not hold — and the layer is where that vocabulary lives.
    """

    task_id: str = Field(min_length=1)


class ClaimExtractionBody(Result):
    """An extraction, as the API accepts it.

    **The body names where to read and what to ask; it does not carry the
    claim.** The text comes from the ledger's stored address and the claim
    comes from the model, so a caller cannot put words in either. The
    proposal the route writes says ``created_by=model_proposal`` and names the
    model that answered; the person's act is acceptance, and it is a
    different route.

    ``user_id`` is a **self-reported string** — the CLI's trust level. The
    product keeps no accounts and performs no authentication, so this names
    who started the operation without proving it. It is not written as the
    proposal's author: a model wrote the proposal, and the record says so.

    ``approval_id`` is the consent the model call is spent against. It is
    optional in the shape so the layer can give its own refusal
    (``approval_missing``) rather than FastAPI's validation error: "you did
    not ask" and "your request was malformed" are different remedies.
    """

    source_id: str = Field(min_length=1)
    locator_key: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    subject_ref: str = Field(min_length=1)
    purpose: str = Field(default="claim_extraction", min_length=1)
    approval_id: str | None = None


class ProposalAcceptanceBody(Result):
    """A person's answer to a model's proposal, as the API accepts it.

    ``verdict`` is the closed pair the application layer publishes; it is a
    plain string here so an unknown word is refused by the layer's own
    vocabulary rather than by FastAPI's validation. ``note`` is required for
    a dispute and refused for a confirmation — the layer enforces both, and
    this body only carries what the caller said.

    **``user_id`` is a self-reported string.** No account stands behind it and
    none is checked; the record says it was reported, not proven.
    """

    user_id: str = Field(min_length=1)
    verdict: str = Field(min_length=1)
    note: str = ""


class GuidanceRuleVerdictBody(Result):
    """A person's verdict on a rule, as the API accepts it.

    **The verdict is closed, and the contract says which words are in it.** A
    rule is confirmed or disputed — a person either stands behind it or says
    why it does not hold — and *"the person had a look"* is not a verdict a
    rule can carry. **The vocabulary is in the type rather than in the
    handler**, so the workbench's own types carry it as well: a view that
    drew a button for a verdict the service does not accept would be
    offering a door that is not there.

    **The reason is the dispute's, and the memory refuses it if it is not
    one.** A dispute without a reason is a shrug, so the body carries what
    the person said and the rule memory decides whether it is a reason — the
    refusal for a shrug is the memory's, and it is named.

    **And the person is named**, because a confirmation nobody signs is not
    a confirmation.
    """

    verdict: Literal["confirmed", "disputed"]
    user_id: str = Field(min_length=1)
    reason: str = ""


class GuidanceRulePublishBody(Result):
    """A mentor's publication of a rule to the group, as the API accepts it.

    **Only a confirmed rule may be published, and only by a second
    reader.** The body names the mentor whose word the publication is —
    the proposer cannot be that person, which the application layer
    refuses by the same second-reader rule the confirmation carries
    (Phase 4 §8.5 / P4-G3).
    """

    user_id: str = Field(min_length=1)


class SessionInfo(Result):
    """The session the caller is in, and the token that proves it.

    **This is the one response that carries the token.** The plan's §1.4.4
    records the owner's decision that *"the UI obtains the token through a
    same-origin request"*, and this is that request. The guard that lets it
    through is the origin check, so a page on another site cannot read it: a
    cross-origin read is blocked by the browser, and a cross-origin *request*
    is refused here with ``origin_refused``.

    Everywhere else the token stays out of the response, out of the events and
    out of the log, and the tests assert it.
    """

    token: str
    #: Where the token was written, so the CLI can tell the user where it is.
    path: str


class Health(Result):
    """What the service says about itself, without saying anything secret.

    Deliberately dull: the address it listens on, the origins it answers to
    and the task it is about. It is the one response a person may read aloud,
    so it carries no token and no credential of any kind.
    """

    status: str
    host: str
    port: int
    origins: tuple[str, ...]
    task_id: str


class CommentResponses(Result):
    """The judgements on one comment, and the states they hold.

    **The states belong to the comment they are about.** The layer's read
    answers with the states themselves, so a caller that wanted to know
    which comment a state belonged to would have to ask again — and asking
    again is how a reader ends up with two answers to one question.
    """

    feedback_id: str
    states: tuple[str, ...]


class Trajectory(Result):
    """The advisor's comments, the edits that answer them, and the responses.

    **Every member is the application layer's own object.** The comments are
    :class:`~labcairn.application.chain.ChainComment`, the edits are
    :class:`~labcairn.application.chain.ChainEdit`, and the states are the
    layer's own — so a workbench that draws this panel draws the chain, and
    not a second spelling of it.
    """

    comments: tuple[ChainComment, ...]
    edits: tuple[ChainEdit, ...]
    responses: tuple[CommentResponses, ...]


class IssueKeys(Result):
    """The issue keys the chain holds for one project.

    **The keys are names, and the names are all this carries.** A key says
    *which problem* the advisor raised, not *what the advisor wrote*: no
    comment's words, no anchored text, no author, no date and no grade
    travel with it. **A panel that draws this draws names**, and a reader
    who wants the words asks for the comments under the key — which is a
    different route and a different answer.

    **The order is the service's, and the service says so.** The chain's
    rows carry no time and no sequence, so the list is sorted rather than
    chronological, and a panel draws it in the order the service answered
    rather than inventing an order of its own. **The keys are the whole
    body**, so a panel cannot show a fact about the chain that the contract
    does not carry — there is nowhere else for one to come from.

    **And the project is named, because a list of names says nothing about
    whose names they are.** The layer refuses a project the chain does not
    hold, so the project in this body is one the chain holds.
    """

    project_id: str
    #: The keys, in the order the service answers them.
    issue_keys: tuple[str, ...]


class ReviewOpinionsQuery(Result):
    """Which review round to read, as the API accepts it.

    **A project and a version, and nothing else.** The opinions, their
    suggestions and their decisions are the round's own; the response is the
    application layer's :class:`~labcairn.application.review.ReviewOpinions`.
    """

    project_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)


class TrajectorySearchQuery(Result):
    """Which trajectory to search, as the API accepts it.

    **A query, and optionally a project.** Without the project the search
    answers over every indexed trajectory; with it, the hits narrow to the
    one project's history. The response is the application layer's
    :class:`~labcairn.application.trajectory.TrajectoryHit` records.
    """

    q: str = Field(min_length=1)
    project_id: str | None = None
    limit: int = Field(default=20, ge=1, le=200)


class PptIngestBody(Result):
    """Which deck to index, as the API accepts it.

    **The body names where to read; it does not carry the deck.** The
    project the deck belongs to, the root the file sits in, and the key it
    has in that root -- the same spelling every other request body that
    names a resource uses. The bytes come from the workspace, through the
    ``source.read`` gate, never from the request.
    """

    project_id: str = Field(min_length=1)
    root_id: str = Field(min_length=1)
    resource_key: str = Field(min_length=1)


class MeetingIngestBody(Result):
    """Which meeting-text file to index, as the API accepts it.

    **The body names where to read; it does not carry the text.** The
    project the file belongs to, the root the file sits in, and the key it
    has in that root -- the same spelling every other request body that
    names a resource uses. The bytes come from the workspace, through the
    ``source.read`` gate, never from the request.
    """

    project_id: str = Field(min_length=1)
    root_id: str = Field(min_length=1)
    resource_key: str = Field(min_length=1)


class TrajectoryIngestBody(Result):
    """Which paper project's revision trajectory to index, as the API accepts it.

    **The body names the project and nothing else.** A trajectory is a
    project's revision history, and the chain's own rows are where it is
    read from -- the request carries no material and no version list. The
    optional ``ingested_at`` stamps the entries; the ingest supplies the
    current moment when it is absent, the way every other ingest does.
    """

    project_id: str = Field(min_length=1)
    ingested_at: datetime | None = None


class UsableGuidanceQuery(Result):
    """Which rules a card may cite, as the API accepts it.

    **A scope, and a project, optionally.** Without the scope the listing
    serves every standing confirmed rule; with it, the rules whose scope
    mentions the text. Without the project the listing serves every rule;
    with it, the rules the project may be served — its own, plus the ones
    a mentor has published to the group (Phase 4 §8.5 / P4-G3). The
    response is the application layer's
    :class:`~labcairn.application.trajectory.UsableRule` records — and a
    candidate is never among them (§8.5).
    """

    scope: str | None = None
    project_id: str | None = None
    limit: int = Field(default=20, ge=1, le=200)


class ReviewManuscriptQuery(Result):
    """Which manuscript to read, as the API accepts it."""

    project_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)


class ReviewSuggestionBody(Result):
    """One suggestion the model proposed, as the API accepts it.

    **A proposal is a record, not a decision.** The body carries the seam's
    own units — one whole plain run of one paragraph — and nothing that
    looks like a verdict: writing a suggestion grants nothing and applies
    nothing. The verdict is :class:`ReviewDecisionBody`'s to take.
    """

    project_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)
    feedback_id: str = Field(min_length=1)
    part: str = Field(min_length=1)
    paragraph: int = Field(ge=1)
    old_text: str
    new_text: str
    author: str = Field(min_length=1)


class ReviewDecisionBody(Result):
    """The reviewer's verdict, as the API accepts it.

    **The vocabulary is in the type rather than in the handler**, the way
    :class:`GuidanceRuleVerdictBody` puts it: the four words are execution
    plan §4's own statuses, and the application layer refuses a fifth. The
    body carries no ``decided_by`` — every decision this route takes is a
    person's, and the chain's word for that is ``user`` — and the
    reviewer's own handle travels in ``operator``.
    """

    project_id: str = Field(min_length=1)
    feedback_id: str = Field(min_length=1)
    verdict: Literal["accepted", "partly_accepted", "rejected", "pending"]
    operator: str = Field(min_length=1)
    needs_evidence: bool = False


class IssueRecordBody(Result):
    """One problem the trial met, as the API accepts it (P4-PILOT §9.4).

    **The record is about something.** The project is required; the task,
    the version and the opinion are named when the trial can name them.
    The two vocabularies -- severity and type -- are closed here, in the
    type rather than in the handler, the way
    :class:`GuidanceRuleVerdictBody` puts it: a workbench that drew a tag
    the service does not accept would be offering a door that is not
    there, and a tag outside the closed list is refused at the wire with
    the same 422 every other closed vocabulary answers with.

    **The status is not in the body.** A recorded issue is ``open``; the
    states after that are ``PATCH /issues/{issue_id}/status``'s to move
    along, and a body that set ``fixed`` outright would be recording a
    confirmation nobody made.
    """

    issue_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    task_id: str | None = None
    version_id: str | None = None
    feedback_id: str | None = None
    step: str = Field(min_length=1)
    error_text: str = Field(min_length=1)
    duration_seconds: float | None = None
    retry_count: int | None = Field(default=None, ge=0)
    severity: Literal["blocker", "serious", "minor", "suggestion"]
    category: Literal["function", "interface", "performance", "model", "documentation"]
    reported_by: str = Field(min_length=1)


class IssueListQuery(Result):
    """Which issues to list, as the API accepts it.

    **A filter narrows; it does not refuse.** Both filters are optional,
    and an empty answer is a fact about the trial, not an error. A filter
    that names a word outside the closed vocabulary is refused at the wire
    -- the same 422 the record path answers with -- because it is a
    question the record cannot understand, not an answer of "none".
    """

    project_id: str = Field(min_length=1)
    status: Literal["open", "confirmed", "fixed", "wontfix"] | None = None
    severity: Literal["blocker", "serious", "minor", "suggestion"] | None = None


class IssueStatusBody(Result):
    """The next state of one issue, as the API accepts it.

    **The states are walked, not set**, and the walk lives in the
    application layer; this body names the target. A ``fixed`` move names
    the version that fixed it -- the field is required by the layer for
    that one move, and a caller that marked a problem fixed without
    naming the fix would be making a claim the next regression cannot
    check. The ``regression_note`` travels with the fix: what to watch,
    in the words the team agreed on.
    """

    project_id: str = Field(min_length=1)
    status: Literal["confirmed", "fixed", "wontfix"]
    fix_version: str | None = None
    regression_note: str | None = None


class ReviewSuggestBody(Result):
    """One suggestion-loop run, as the API asks for it.

    **The mode is the whole difference between the two runs.** ``real``
    asks the authorised model and spends one approval per opinion;
    ``substitute`` asks the local stand-in and spends nothing, because
    nothing leaves the machine. The approvals are named per opinion —
    ``approval_ids`` maps the chain's ``feedback_id`` to the approval the
    caller holds for it — because ADR-0006's consent is per request, and a
    batch of opinions is a batch of requests, not one.

    The budget fields are the authorisation record's own numbers (G0 §5).
    An absent field is unbounded for a substitute run and the caller's
    responsibility for a real one; the loop records what it spent either
    way.
    """

    project_id: str = Field(min_length=1)
    version_id: str = Field(min_length=1)
    mode: Literal["real", "substitute"] = "substitute"
    #: Per-opinion approvals: the chain's ``feedback_id`` to the approval id
    #: that covers that opinion's request. A real run spends one per
    #: opinion; a substitute run needs none.
    approval_ids: dict[str, str] = Field(default_factory=dict)
    max_requests: int | None = Field(default=None, ge=1)
    max_tokens: int | None = Field(default=None, ge=1)
    max_consecutive_failures: int = Field(default=3, ge=1, le=100)
    retry_attempts: int = Field(default=2, ge=0, le=10)


class ReviewSuggestRun(Result):
    """One suggestion-loop run's account, as the API returns it.

    The application layer's own
    :class:`~labcairn.application.model_suggestions.ModelSuggestionRunData`
    is the model; this is the same fields, validated the same way. The run
    row it mirrors is the budget's account — a reader answers "what did
    this run cost, what did it produce, and why did it stop" from this one
    object, without reading the suggestion rows.

    **The same account is returned twice, and that is the point.** The run
    writes its own record, and ``GET /review/suggest/runs/{run_id}`` reads
    it back — so a gate that wants the evidence of a run *after* the run
    has finished has something to read, rather than a slot it can only
    record as unknown.

    **The per-request entries carry the durations and the approvals.** One
    entry per request the run made: which opinion, which model answered,
    what happened, how long it took and what it cost. **No prose** — the
    request text and the model's answer are not here, and never were.
    """

    run_id: str
    project_id: str
    version_id: str
    mode: str
    model_id: str
    requests_made: int
    tokens_estimated: int
    stopped_reason: str | None
    suggestions_recorded: int
    opinions_skipped: int
    started_at: str
    finished_at: str
    #: How long the run took, in seconds — the run's own two timestamps,
    #: subtracted, so the backoff between retries counts too.
    duration_seconds: float
    #: One entry per request the run made, in the order it made them.
    requests: tuple[SuggestionRequestEntry, ...] = ()


class ApplyReviewBody(Result):
    """What the apply step needs, as the API accepts it.

    The application layer's own :class:`~labcairn.application.review.ApplyReviewRequest`
    is the model; this body exists because the request body is the API's
    own — and it is the same fields, validated the same way, so the two
    do not drift. The preview route takes the same body, because the
    preview answers the same question about the same round — what this
    request's addresses name — and it needs nothing the apply does not.
    """

    project_id: str = Field(min_length=1)
    input_version_id: str = Field(min_length=1)
    source_root_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    output_label: str = Field(min_length=1)
    window_end: str = Field(min_length=1)


class ReviewApplyCancelBody(Result):
    """What a cancellation request names, as the API accepts it.

    The round is addressed by the project it belongs to, the same name the
    apply body carries. **A cancellation is asked for, not asserted**: the
    body carries the project and the reason the operator gave, and the
    service sets an in-process flag that the running apply round reads at
    its next :class:`~labcairn.papers.binding.CancelCheck` point.

    **The flag is in-process and deliberate.** A flag that crossed a process
    or a restart would be a flag nobody set: the apply runs in this service,
    and the cancellation is answered by this service, before the next
    publication. When no apply round is running for the project, the cancel
    route refuses with ``apply_cancelled``'s sibling -- there is nothing to
    cancel -- rather than planting a flag for a round that will never start.
    """

    project_id: str = Field(min_length=1)
    #: The operator's own words, carried verbatim into the round's refusal --
    #: the record says where the round stopped and why the operator stopped it.
    reason: str = Field(min_length=1)


class ReviewApplyCancelled(Result):
    """What a cancellation request did, as the API answers it.

    The answer is the flag's own account: the project whose apply was asked
    to stop, and the reason the operator gave. **It does not say the round
    has stopped** -- the round stops at its next publication checkpoint,
    which may be a moment away -- and the message says so, so a reader of
    the answer is not told a round is over before the binding has said so.
    """

    project_id: str
    reason: str
    #: Whether a round was running and read the flag. ``False`` means the
    #: service had no apply round in flight for this project, and the route
    #: refused rather than planting a flag for a round that will never ask.
    accepted: bool


class InterruptedResolveBody(Result):
    """The prediction a probe resolves an interrupted publication against.

    **The hash is stated, not looked up.** The store keeps only the digest of
    the operation's arguments, so the bytes' hash is not recoverable from the
    record — the caller states it from the round's own record, and a wrong
    statement is a ``conflict`` verdict rather than a silent overwrite.
    """

    expected_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")


class InterruptedReplayBody(Result):
    """What replaying an interrupted publication needs, as the API accepts it.

    **The bytes travel base64-encoded**, the way every other byte-carrying
    body here travels: a draft is a zip and a zip is not text. The approval
    is named in the body rather than inferred, because a replay is a fresh
    attempt — the interrupted one's consent was bound to its own operation's
    digest, and one consent, one effect stands.
    """

    edited_base64: str = Field(min_length=1)
    approval_id: str = Field(min_length=1)


class InterruptedResolutionWire(Result):
    """What a probe answered about one interrupted publication, on the wire.

    The layer's :class:`~labcairn.recovery.contracts.ReconciliationOutcome`
    is a frozen dataclass, not a pydantic model, so it has no JSON-schema
    spelling of its own; this is the same fields, validated, and nothing
    more — re-spelling a field here would be a second place for the probe's
    answer to drift.
    """

    operation_id: str
    resolution: str
    resulting_state: str
    replay_permitted: bool
    expected_sha256: str
    observed_sha256: str | None
    resource_key: str
    detail: str


class DeliverableFileWire(Result):
    """One deliverable on the wire: its bytes, base64-encoded.

    The layer's :class:`~labcairn.application.review.DeliverableFile`
    carries raw bytes, because a caller that saves a deliverable writes
    bytes to disk. A JSON body cannot carry raw bytes — a DOCX is a zip,
    and a zip is not text — so the API's encoding of one is the bytes'
    base64. A client decodes it and hashes the decoded bytes; the sha256
    field is over the decoded bytes, the same digest the receipt and the
    manifest bind.
    """

    kind: str
    relative_path: str
    content_base64: str
    sha256: str
    size_bytes: int


class DeliverablesExportWire(Result):
    """The four deliverables of one closed binding, as the wire carries them.

    The ids are the layer's own, unchanged — the export's whole claim is
    that these four files bind to one round, and the wire shape exists only
    to carry their bytes; re-spelling an id here would be a second place
    for the binding to drift.
    """

    project_id: str
    dossier_artifact_id: str
    task_id: str
    input_version_id: str
    output_version_id: str
    marked_receipt_id: str
    clean_receipt_id: str
    edge_id: str
    deliverables: tuple[DeliverableFileWire, ...]


class RoleRunBody(Result):
    """One role-loop request, as the API accepts it.

    The application layer's :class:`~labcairn.application.roles_run.RoleRunRequest`
    is the model for the work part of this body, and its
    :class:`~labcairn.application.roles_run.ModelCallPlan` is the model for
    the plan part: the loop is the layer's own operation, and this body
    exists only because the request body is the API's own. The fields are
    the same fields, validated the same way, so the wire and the CLI's
    options do not drift.

    **The plan is stated, and the loop checks it.** The material the run
    would send is read from the chain and compared against
    ``root_id``/``resource_key``/``material_ref``; a declaration that does
    not match is refused by name rather than replaced. The plan is required
    whenever a judgement is missing, because a missing judgement is a model
    call and a model call needs to know who to ask and where the material
    is; a request whose judgements are all supplied needs no plan at all.

    **A supplied judgement is the caller's own, and it travels as the shape
    the role takes** -- the same fields
    :class:`~labcairn.application.roles_run.TrajectoryJudgement` and its
    siblings take. A caller that has every judgement spends nothing and
    reaches no wire; the loop still refuses an alignment outside the role's
    vocabulary, because the roles' own checks are the architecture's.
    """

    roles: tuple[str, ...] = Field(min_length=1)
    project_id: str = Field(min_length=1)
    issue_key: str = Field(min_length=1)
    version_ids: tuple[str, ...] = ()
    rule_id: str | None = None
    evidence_refs: tuple[str, ...] | None = None
    #: The judgements the caller supplies outright. A role named without one
    #: is answered by the model -- which is the part of the run that spends
    #: consent -- and one supplied for a role nobody named is simply unused.
    trajectory: RoleTrajectoryJudgement | None = None
    guidance: RoleGuidanceJudgement | None = None
    critique: RoleCritiqueJudgement | None = None
    #: Who to ask, and where the material is. Required exactly when a
    #: judgement is missing, because that is when the run asks the model.
    provider: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    root_id: str | None = Field(default=None, min_length=1)
    resource_key: str | None = Field(default=None, min_length=1)
    material_ref: str | None = Field(default=None, min_length=1)
    purpose: str | None = Field(default=None, min_length=1)
    destination: str | None = Field(default=None, min_length=1)
    subject_ref: str | None = Field(default=None, min_length=1)
    #: When the consent the run will spend lapses. A run that needs a model
    #: judgement asks for its approval with this expiry; a run that needs
    #: none never reads it.
    expires_at: datetime | None = None
    #: The granted approval the run spends, on the run route. The ask mints
    #: it pending; a person grants it over the approval door; the run
    #: presents it here. A run whose judgements are all supplied needs none,
    #: and never reads it.
    approval_id: str | None = Field(default=None, min_length=1)


class RoleTrajectoryJudgement(Result):
    """Role A's judgement, as the API accepts it. The role checks the values."""

    issue_type: str
    alignment: str
    advisor_quote: str
    note: str
    edit_action_id: str | None = None


class RoleGuidanceJudgement(Result):
    """Role B's judgement, as the API accepts it. The role checks the values."""

    issue_type: str
    severity: str
    reason: str
    suggested_next_action: str
    uncertainty_kind: str
    what_is_uncertain: str
    claims: tuple[RoleClaimJudgement, ...] = ()
    style_notes: tuple[str, ...] = ()


class RoleClaimJudgement(Result):
    """One claim inside role B's judgement, as the API accepts it."""

    text: str
    kind: str
    evidence_ref: str | None = None
    issue_key: str | None = None
    advisor_quote: str | None = None


class RoleCritiqueJudgement(Result):
    """Role C's judgement, as the API accepts it. The role checks the values."""

    verdict: str
    repair_advice: str
    handover_reason: str | None = None


__all__ = [
    "AnalysisBody",
    "ApplyReviewBody",
    "ApprovalBody",
    "ApprovalUseBody",
    "ClaimBody",
    "CommentResponses",
    "DeliverableFileWire",
    "DeliverablesExportWire",
    "GuidanceRulePublishBody",
    "GuidanceRuleVerdictBody",
    "Health",
    "InterruptedReplayBody",
    "InterruptedResolutionWire",
    "InterruptedResolveBody",
    "IssueKeys",
    "IssueListQuery",
    "IssueRecordBody",
    "IssueStatusBody",
    "MeetingIngestBody",
    "PptIngestBody",
    "RefusalBody",
    "ReportBody",
    "ReviewApplyCancelBody",
    "ReviewApplyCancelled",
    "ReviewDecisionBody",
    "ReviewManuscriptQuery",
    "ReviewOpinionsQuery",
    "ReviewSuggestBody",
    "ReviewSuggestRun",
    "ReviewSuggestionBody",
    "RoleClaimJudgement",
    "RoleCritiqueJudgement",
    "RoleGuidanceJudgement",
    "RoleRunBody",
    "RoleTrajectoryJudgement",
    "SessionInfo",
    "StageBody",
    "Trajectory",
    "TrajectorySearchQuery",
    "UsableGuidanceQuery",
]
