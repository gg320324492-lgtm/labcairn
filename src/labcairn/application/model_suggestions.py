"""The real-model suggestion loop, behind the same seams the substitute runs.

**What this module is.** Phase 4 execution plan §7.2: one product operation
that takes a version's pending opinions, asks a declared model for one
suggested edit each, and records what came back — under the consent gates
the repository already has, bounded by the budget and stop conditions G0
§5 names, with retries classified at the boundary, and with the substitute
path one switch away.

**The shape is the binding's own.** :func:`labcairn.papers.binding.open_binding`
takes an injected ``SuggestionSource`` — a callable from a
:class:`~labcairn.papers.feedback.FeedbackEvent` to an
:class:`~labcairn.editing.drafts.ApprovedEdit | None` — and this module
builds sources of that shape. A provider-driven source and the substitute
source are interchangeable behind it, so the apply step cannot tell which
answered and never needs to.

**The transport is injected; the loop owns the gates.** A
:class:`ModelSuggestionTransport` is the seam a real provider adapter and a
scripted stub both satisfy — one desensitised :class:`ModelRequest` in, one
answer string out. This module decides nothing about credentials, endpoints
or SDKs. What it owns is the loop: what is sent, what each call costs,
when it stops, and what a reader can distinguish afterwards.

The properties this module exists to hold
-----------------------------------------

1. **Desensitised requests.** A request body carries the comment text and
   the anchor's baseline text, scrubbed, and nothing else — no author name,
   no affiliation, no project number, no locator internals. The record
   names a request by counts and class names, never by text.

2. **Accounting per call.** Every transport call lands in the
   ``model_suggestion_runs`` row — request count, token estimate, duration,
   outcome, which opinion it was for — so a budget is a budget and not a
   hope. A call nobody can account for is a call that did not happen
   honestly.

3. **The stop conditions fire and are named.** The loop stops on a request
   ceiling, a token ceiling, or a ceiling on consecutive failures — and the
   reason lands on the run row, so a reader knows which stop fired and
   which opinions it cut off.

4. **The substitute is labelled, never disguised.** A run that fell back to
   the substitute carries the substitute's model id on the run row and the
   substitute author on every suggestion it recorded. A substitute output
   that could pass for the real model's is the defect this module exists to
   make impossible.

5. **A timeout is a classified failure, not a refusal.** A call that runs
   out of time is classified by the provider layer — retryable, with the
   action "ask again" — and the per-call entry on the run row names it as
   the timeout it was. The loop retries it inside the run's budget and then
   offers the substitute, labelled; **nothing refuses, because nothing is
   declined**: the material is unchanged, no decision was recorded, and
   asking again is safe. A refusal vocabulary that named a timeout would
   promise an outcome this path does not have.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, Protocol, runtime_checkable

from labcairn.application import consent
from labcairn.application.approvals import ApprovalUse
from labcairn.application.context import ApplicationContext, store_refusals
from labcairn.application.model_transmit import transmit_request
from labcairn.application.models import Result
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.application.review import record_review_suggestion
from labcairn.core.ids import ApprovalId
from labcairn.core.providers.protocol import ModelRequest
from labcairn.db.models import ModelSuggestionRunRow
from labcairn.editing.drafts import ApprovedEdit
from labcairn.papers.feedback import FeedbackEvent, list_feedback_events
from labcairn.providers.errors import classify_exception
from labcairn.providers.redaction import Redactor
from labcairn.security.capabilities import CapabilityId, ModelRequestArgs
from labcairn.security.paths import CanonicalPath
from labcairn.security.permissions import Grant

__all__ = [
    "MODEL_SUGGESTION_MODE_REAL",
    "MODEL_SUGGESTION_MODE_SUBSTITUTE",
    "MODEL_SUGGESTION_PURPOSE",
    "REAL_AUTHOR_PREFIX",
    "SUBSTITUTE_AUTHOR",
    "ModelSuggestionBackend",
    "ModelSuggestionRunData",
    "ModelSuggestionSource",
    "ModelSuggestionTransport",
    "ProviderSuggestionSource",
    "SourceAccounting",
    "SubstituteSuggestionSource",
    "SubstituteTransport",
    "SuggestionLoopConfig",
    "SuggestionRequestEntry",
    "desensitised_prompt",
    "read_suggestion_run",
    "suggest_for_version",
    "suggestion_approval_use",
]

#: The two modes a suggestion run may take. ``real`` asks the authorised
#: model and spends one digest-bound approval per request; ``substitute``
#: asks the local stand-in and spends nothing, because nothing leaves the
#: machine.
MODEL_SUGGESTION_MODE_REAL: str = "real"
MODEL_SUGGESTION_MODE_SUBSTITUTE: str = "substitute"

#: The material-purpose every suggestion request is judged under. The
#: consent layer's purposes are a closed five (``read``, ``annotate``,
#: ``retrieve``, ``transmit``, ``train``), and a model request that sends
#: material out is a ``transmit`` — the same purpose every other model
#: path names, so one grant covers them all and none of them invents a
#: sixth word the vocabulary would have to reject.
MODEL_SUGGESTION_PURPOSE: str = "transmit"

#: The author prefix a real-model suggestion carries, followed by the
#: transport's model id — ``model:<id>`` — so a reader can tell which model
#: said what.
REAL_AUTHOR_PREFIX: str = "model:"

#: The author a substitute suggestion carries, on the suggestion row and on
#: the run row. **A substitute is never recorded as the real model's
#: answer** — that is G0 §5's fallback rule, and this constant is where it
#: is enforced.
SUBSTITUTE_AUTHOR: str = "substitute-model"

#: The package part a suggestion edits. The seam rewrites plain runs of
#: document paragraphs, and every part the binding's own sample and the
#: feedback reader address is this one.
_DOCUMENT_PART: str = "word/document.xml"


def _estimate_tokens(text: str) -> int:
    """A conservative token estimate: characters over four, at least one.

    The transport seam returns text, not usage, so the loop's token figure
    is an *estimate* — named as one on the run row, never dressed up as a
    measurement. A ceiling checked against this estimate is checked
    against the same number every time, which is what a budget needs.
    """
    return max(1, len(text) // 4)


def desensitised_prompt(event: FeedbackEvent, *, redactor: Redactor) -> str:
    """The request body: the comment and the anchor text, scrubbed.

    **No author, no locator, no metadata.** The prompt is built from the
    two texts a suggestion needs — what the comment said and what passage
    it is about — and scrubbed through the redactor, so a credential-shaped
    run or a registered secret cannot leave even if a caller passed one in.
    The comment's author is a field this function never reads; the
    desensitisation witness asserts the name's absence from the captured
    request.

    This is the one spelling of the request body, shared by the approval
    derivation and the source: an approval whose digest covered different
    bytes than the request sent would be an approval that authorised
    something else.
    """
    assert event.anchor_text is not None
    raw = (
        "You are suggesting one replacement for a manuscript passage.\n"
        "Reviewer comment:\n"
        f"{event.comment_text}\n"
        "Anchored passage:\n"
        f"{event.anchor_text}\n"
        "Reply with the replacement text for the passage, and nothing else."
    )
    return redactor.scrub(raw)


@dataclass(slots=True)
class SourceAccounting:
    """What one source has spent, read by the loop after every call.

    The counting lives on the source because the transport call happens
    there; the loop reads the counters before and after each attempt, so
    the run row's figures cover retries and fallbacks as well as first
    tries.
    """

    requests_made: int = 0
    tokens_estimated: int = 0


@runtime_checkable
class ModelSuggestionTransport(Protocol):
    """The one seam between the loop and whatever answers.

    **A transport, not a provider.** The provider layer's own protocol is
    the seam a real adapter is built behind; this is the application
    layer's *use* of one. The source hands over the desensitised
    :class:`ModelRequest` and receives the answer text. A caller that
    wants to drive the loop with a scripted transport can, without
    touching the gates — and the window that wires a real paid provider
    changes this object, not the loop.
    """

    model_id: str

    def send(self, request: ModelRequest) -> str:
        """One request out, one answer back. Raises on failure."""
        ...


class SubstituteTransport:
    """The transport a substitute run drives — deterministic, and local.

    **The substitute is a stand-in, not a second model.** It renders a
    plausible suggestion from the desensitised request alone, so the loop's
    downstream path (record, review, apply) is exercised end to end when
    the real model is unavailable or its retries are spent. It reads only
    the request text it is handed, holds no credential, and carries the
    substitute model id.
    """

    def __init__(self, *, model_id: str = SUBSTITUTE_AUTHOR) -> None:
        self.model_id = model_id

    def send(self, request: ModelRequest) -> str:
        """Render one suggestion from the request's own text.

        It never invents material the request did not carry: the answer
        names the comment it was given and asks for the passage to be
        rewritten around it.
        """
        return (
            "Rewrite the anchored passage so it addresses the comment. "
            f"Comment under review: {request.prompt[:200]}"
        )


@runtime_checkable
class ModelSuggestionSource(Protocol):
    """One suggestion source, in the binding's own shape.

    Same contract as :data:`labcairn.papers.binding.SuggestionSource` — a
    callable from a :class:`FeedbackEvent` to an :class:`ApprovedEdit |
    None` — with the members the loop's accounting and the seam's units
    need: the model id the source answers as, the counter its calls
    accumulate into, and the manuscript paragraphs the loop hands in before
    the walk. Returning ``None`` says the source has no suggestion for this
    opinion — an honest answer, not a failure. A transport failure raises.
    """

    model_id: str
    accounting: SourceAccounting

    def bind_paragraphs(self, paragraphs: Sequence[str]) -> None:
        """Hand the source the manuscript's paragraphs, in document order.

        The seam rewrites **one whole plain run of one paragraph**, so an
        edit's ``old_text`` is the whole paragraph and not the anchor's
        substring. The loop reads the paragraphs once and hands them to
        every source before the walk; a source that answered from the
        anchor's substring alone would propose an edit the seam could not
        locate.
        """
        ...

    def __call__(self, event: FeedbackEvent) -> ApprovedEdit | None:
        """One opinion in, one edit out — or ``None`` for no suggestion."""
        ...


class ProviderSuggestionSource:
    """The source a transport drives: desensitise, ask, wrap, or honestly none.

    **One call is one attempt.** The loop retries and falls back; this
    class does neither. It builds the desensitised prompt, spends one
    transport call, and wraps the answer into the seam's own units —
    ``part``/``paragraph``/``old_text``/``new_text``, author
    ``model:<id>``, date the proposed-at moment. An answer that is empty,
    or that would leave the passage unchanged, is no suggestion at all:
    ``None``, and the loop records an honest empty set rather than a
    failure.
    """

    def __init__(
        self,
        transport: ModelSuggestionTransport,
        *,
        redactor: Redactor | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._transport = transport
        self._redactor = redactor if redactor is not None else Redactor()
        self._clock = clock if clock is not None else (lambda: datetime.now(UTC))
        self.model_id = transport.model_id
        self.accounting = SourceAccounting()
        self._paragraphs: tuple[str, ...] = ()

    def bind_paragraphs(self, paragraphs: Sequence[str]) -> None:
        """Take the manuscript's paragraphs, in document order."""
        self._paragraphs = tuple(paragraphs)

    def __call__(self, event: FeedbackEvent) -> ApprovedEdit | None:
        """Ask the transport for one suggestion, and wrap what came back."""
        if not event.comment_text.strip():
            return None
        assert event.anchor_text is not None
        if not event.anchor_text.strip():
            return None
        prompt = desensitised_prompt(event, redactor=self._redactor)
        self.accounting.requests_made += 1
        self.accounting.tokens_estimated += _estimate_tokens(prompt)
        answer = self._transport.send(ModelRequest(prompt=prompt))
        self.accounting.tokens_estimated += _estimate_tokens(answer)
        return self._wrap(event, answer)

    def _wrap(self, event: FeedbackEvent, answer: str) -> ApprovedEdit | None:
        """The answer as an edit, or ``None`` when it proposes nothing.

        An empty answer is not a suggestion; neither is an answer that
        returns the passage verbatim. Both are the model's honest "I have
        nothing to change here", and both are recorded as an empty set —
        never as a failure and never as a no-op edit.

        ``old_text`` is the **whole paragraph** the anchor sits in, the
        unit the seam rewrites — never the anchor's substring, which is an
        address and not an editable run.
        """
        assert event.anchor_text is not None
        text = answer.strip()
        if not text or text == event.anchor_text.strip():
            return None
        paragraph = event.anchor_paragraph or 1
        old_text = self._paragraph_text(paragraph, fallback=event.anchor_text)
        return ApprovedEdit(
            part=_DOCUMENT_PART,
            paragraph=paragraph,
            old_text=old_text,
            new_text=text,
            author=f"{REAL_AUTHOR_PREFIX}{self.model_id}",
            date=self._clock().isoformat(),
        )

    def _paragraph_text(self, paragraph: int, *, fallback: str) -> str:
        """The whole text of one 1-based paragraph, or the anchor when unknown.

        The loop hands the paragraphs in before the walk, so the lookup is
        an index — but an index past the manuscript's end is answered with
        the anchor rather than trusted, because an edit whose ``old_text``
        does not match the file is an edit the seam refuses at apply time.
        """
        if 1 <= paragraph <= len(self._paragraphs):
            return self._paragraphs[paragraph - 1]
        return fallback


class SubstituteSuggestionSource:
    """The fallback source: deterministic, local, and labelled as substitute.

    **It answers in the same shape and under a different name.** Every edit
    it returns carries ``substitute-model`` as its author, so a stored
    suggestion can never be mistaken for the authorised model's answer.
    It consumes no approval and sends nothing out of the machine.
    """

    def __init__(
        self,
        *,
        model_id: str = SUBSTITUTE_AUTHOR,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.model_id = model_id
        self.accounting = SourceAccounting()
        self._clock = clock if clock is not None else (lambda: datetime.now(UTC))
        self._paragraphs: tuple[str, ...] = ()

    def bind_paragraphs(self, paragraphs: Sequence[str]) -> None:
        """Take the manuscript's paragraphs, in document order."""
        self._paragraphs = tuple(paragraphs)

    def __call__(self, event: FeedbackEvent) -> ApprovedEdit | None:
        """One deterministic suggestion from the opinion's own texts.

        The suggestion rewrites the **whole paragraph** the anchor sits
        in — the seam's unit — and names the comment it addresses, so the
        downstream reviewer can see what the substitute answered.
        """
        if not event.comment_text.strip():
            return None
        assert event.anchor_text is not None
        if not event.anchor_text.strip():
            return None
        self.accounting.requests_made += 1
        paragraph = event.anchor_paragraph or 1
        old_text = (
            self._paragraphs[paragraph - 1]
            if 1 <= paragraph <= len(self._paragraphs)
            else event.anchor_text
        )
        comment = event.comment_text.strip()
        new_text = f"{old_text} (revised to address the comment: {comment[:120]})"
        self.accounting.tokens_estimated += _estimate_tokens(new_text)
        return ApprovedEdit(
            part=_DOCUMENT_PART,
            paragraph=paragraph,
            old_text=old_text,
            new_text=new_text,
            author=SUBSTITUTE_AUTHOR,
            date=self._clock().isoformat(),
        )


@dataclass(frozen=True, slots=True)
class SuggestionLoopConfig:
    """The ceilings and stops one loop run is bounded by.

    The numbers are the authorisation record's own (G0 §5). Every ceiling
    is optional; a run with no ceiling at all is not refused here — the
    *route* decides what a mode without a budget may ask for — but a real
    run the owner authorised carries the owner's numbers.
    """

    #: LabCairn-issued transport calls to the **real** model, counted per
    #: attempt: a retry is a request and costs a request. The substitute's
    #: local calls are free and are not bounded by this ceiling.
    max_requests: int | None = None
    #: The token-estimate ceiling, over both sources' estimates. Checked
    #: after each call; the call that crosses it is the last one.
    max_tokens: int | None = None
    #: Consecutive failed or refused opinions after which the run stops.
    max_consecutive_failures: int = 3
    #: Transport retries per opinion for a retryable failure.
    retry_attempts: int = 2
    #: Bounded backoff base, in seconds: the delay before retry *n* is
    #: ``backoff_base_s * n``. Zero in tests and in substitute runs.
    backoff_base_s: float = 0.0


class SuggestionRequestEntry(Result):
    """One opinion's request, as the run recorded it.

    **The boundary holds on the way back too.** An entry names the opinion,
    the model that answered, what happened, how long it took and what it
    cost — and never what was said. The request text and the model's
    answer are not here; the request is not here either, only the
    identifiers and the counts.

    ``approval_spent`` says whether an approval was consumed for this
    opinion's request, and ``approval_id`` names the one that was, when the
    run recorded it. **The two are different facts and neither is inferred
    from the other**: a run written before the approval id was recorded
    still says whether an approval was spent, and a run that spent one
    names it.

    **This is the layer's own model, and the service serves it as it is.**
    It is not a dataclass beside a twin: a second spelling of one
    request's account is a spelling that drifts.
    """

    feedback_id: str
    #: The model that answered — the run's primary or its substitute.
    source: str
    #: What happened to this opinion. The closed vocabulary the run writes.
    outcome: str
    attempts: int
    elapsed_s: float
    tokens_estimated: int
    #: A class name, never prose: the refusal's reason or the failure's kind.
    detail: str
    retryable: bool | None
    #: The approval this request spent, when the run recorded which.
    approval_id: str | None
    #: Whether an approval was consumed for this opinion's request.
    approval_spent: bool


@dataclass(frozen=True, slots=True)
class ModelSuggestionRunData:
    """One loop run's accounting, as the caller reads it back."""

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
    started_at: datetime
    finished_at: datetime
    #: One entry per request the run made, in the order it made them.
    requests: tuple[SuggestionRequestEntry, ...] = ()

    @property
    def duration_seconds(self) -> float:
        """How long the run took, in seconds.

        **The run's own two timestamps, subtracted.** Not a sum of the
        requests' durations: the run spent time that was not a request's —
        the backoff between retries, the write of its own row — and a
        duration that added up only the requests would say the run was
        shorter than it was.
        """
        return (self.finished_at - self.started_at).total_seconds()


#: The outcomes that mean a request was made — and therefore, in a real run,
#: that an approval was consumed to make it. The gate consumes the approval
#: *before* the model is asked (ADR-0015 D3's order), so a request that
#: happened is a request an approval paid for.
_TRANSPORT_OUTCOMES: Final[frozenset[str]] = frozenset({"answered", "empty", "failed", "exhausted"})


def _approval_spent(mode: str, outcome: str, approval_id: object) -> bool:
    """Whether an approval was consumed for one opinion's request.

    **The recorded id settles it; the outcome settles it for the runs that
    predate the id.** A run that recorded which approval it spent needs no
    inference: the id is there. A run written before the id was recorded
    still says, from the outcome, whether the request happened — and in a
    real run a request that happened is a request an approval paid for. A
    substitute run spent nothing at all, whatever the outcome says, because
    nothing left the machine.
    """
    if approval_id is not None:
        return True
    if mode != MODEL_SUGGESTION_MODE_REAL:
        return False
    return outcome in _TRANSPORT_OUTCOMES


def _measured_int(record: Mapping[str, object], field: str) -> int:
    """One measured count, read back — or refused.

    **A missing field is not a zero.** The run writes these three values
    itself and always writes them, so a record without one is a record
    that was not written by this writer — and reading it as a zero would
    turn "nobody measured it" into "it measured nothing". The repository's
    own negative control watches for exactly that fold
    (`tests/test_fake_provider_invariants.py`), so this reads the value it
    was given and refuses a record that does not carry one.
    """
    value = record.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the stored request record's {field!r} is not a measured count: {value!r}.",
        )
    return value


def _measured_seconds(record: Mapping[str, object], field: str) -> float:
    """One measured duration, read back — or refused. See :func:`_measured_int`."""
    value = record.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the stored request record's {field!r} is not a measured duration: {value!r}.",
        )
    return float(value)


def _entry_from_record(record: Mapping[str, object], *, mode: str) -> SuggestionRequestEntry:
    """One stored request entry, read back as the layer's own shape."""
    outcome = str(record.get("outcome", ""))
    approval_id = record.get("approval_id")
    retryable = record.get("retryable")
    return SuggestionRequestEntry(
        feedback_id=str(record.get("feedback_id", "")),
        source=str(record.get("source", "")),
        outcome=outcome,
        attempts=_measured_int(record, "attempts"),
        elapsed_s=_measured_seconds(record, "elapsed_s"),
        tokens_estimated=_measured_int(record, "tokens_estimated"),
        detail=str(record.get("detail", "")),
        retryable=None if retryable is None else bool(retryable),
        approval_id=None if approval_id is None else str(approval_id),
        approval_spent=_approval_spent(mode, outcome, approval_id),
    )


def read_suggestion_run(context: ApplicationContext, run_id: str) -> ModelSuggestionRunData:
    """One run's account, read back after the run has finished.

    **The run writes its own record, and this is the read of it.** The
    ``POST /review/suggest`` answer is the account of the run that answer
    arrived with, and it is gone the moment the caller lets it go: a gate
    that wants the evidence of a run *after* the run has finished had
    nothing to read, and recorded the slot as unknown for exactly that
    reason. The row is the durable half of the answer, and this operation
    is what makes it readable.

    **The same shape comes back.** The read returns the very
    :class:`ModelSuggestionRunData` the run returned, so there is one
    spelling of a run's account and not two that agree until somebody
    changes one of them.

    **The permission is asked for the task's own area.** The account is the
    task's own record, and reading it is reading the task's area — the same
    question :func:`labcairn.application.events.read_events` asks of the
    event log, because both are the task's own facts.

    :raises ApplicationRefusedError: the store holds no run with that id, or
        the policy denied reading the task's area.
    """
    area = context.task_area()
    consent.evaluate(
        context,
        capability=CapabilityId.FS_READ,
        arguments={"path": area.declared_key},
        resource=area,
    )
    with store_refusals():
        row = context.store.session.get(ModelSuggestionRunRow, run_id)
    if row is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the store holds no suggestion run with the id {run_id!r}.",
        )
    return ModelSuggestionRunData(
        run_id=row.run_id,
        project_id=row.project_id,
        version_id=row.version_id,
        mode=row.mode,
        model_id=row.model_id,
        requests_made=row.requests_made,
        tokens_estimated=row.tokens_estimated,
        stopped_reason=row.stopped_reason,
        suggestions_recorded=row.suggestions_recorded,
        opinions_skipped=row.opinions_skipped,
        started_at=row.started_at,
        finished_at=row.finished_at,
        requests=tuple(_entry_from_record(record, mode=row.mode) for record in row.requests_json),
    )


def suggestion_approval_use(
    context: ApplicationContext,
    event: FeedbackEvent,
    *,
    provider: str,
    model: str,
    redactor: Redactor | None = None,
    purpose: str = MODEL_SUGGESTION_PURPOSE,
) -> ApprovalUse:
    """What an approval for one opinion's suggestion request covers.

    **This is the one derivation**, the way claim extraction's
    ``claim_extraction_use`` is: a caller asks for consent with it and the
    loop spends the approval with it, so the question the person answered
    and the request that is made are the same request. The digest covers
    the desensitised prompt — the same bytes :class:`ProviderSuggestionSource`
    sends — so an approval for one opinion's request does not authorise
    another's.
    """
    resource = _version_resource(context, event.version_id)
    prompt = desensitised_prompt(event, redactor=redactor if redactor is not None else Redactor())
    return ApprovalUse(
        capability=CapabilityId.MODEL_REQUEST,
        arguments=ModelRequestArgs(
            provider=provider,
            model=model,
            path=resource.declared_key,
            excerpts=(prompt,),
            purpose=purpose,
        ).model_dump(),
        root_id=resource.root_id,
        resource_key=resource.declared_key,
    )


def _version_resource(context: ApplicationContext, version_id: str) -> CanonicalPath:
    """The material resource one manuscript version was made from.

    The approval names the material by its path in its root, the way
    extraction names a source — the locator names a place *inside* the
    file and is not a resource key.
    """
    from labcairn.papers.chain import material_relative_path

    relative_path = material_relative_path(context.store.session, version_id)
    if relative_path is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.SOURCE_NOT_FOUND,
            f"the manuscript version {version_id!r} names material the ledger "
            "does not hold. An approval about a file nobody has is an "
            "approval about nothing.",
        )
    return context.resource_for(relative_path)


class ModelSuggestionBackend:
    """The service's assembly point for a real-model suggestion run.

    **This is the service's wiring, not a consent of its own** — the same
    shape claim extraction's backend holds. A service that carries no
    backend, or one whose real transport is absent, refuses a ``real`` run
    with ``model_suggestion_no_provider``; a service that carries one still
    spends only approvals the caller presented, and still sends nothing the
    transmit gate did not permit. ``grants`` are the material-purpose
    grants the requests are judged against, and ``destination`` is the
    destination they name.
    """

    def __init__(
        self,
        *,
        provider: str,
        real_transport: ModelSuggestionTransport | None = None,
        grants: Sequence[Grant] = (),
        destination: str = "",
    ) -> None:
        self.provider = provider
        self.real_transport = real_transport
        self.grants = grants
        self.destination = destination


class SuggestionLoop:
    """One loop run: the opinions of one version, one budget, one account.

    **The loop owns the gates, the retries, the stops and the account; a
    source owns one attempt.** A real run checks the request ceiling, then
    spends one digest-bound approval per opinion — the same order claim
    extraction holds, at the opinion's granularity — and classifies every
    transport failure at the boundary: retryable failures back off and
    retry within the budget, non-retryable ones are recorded and not
    retried, and a run whose consecutive failures reach the ceiling stops,
    naming the reason. Once one opinion's retries are spent the run falls
    back to the substitute, and **stays** fallen back: an authorised model
    that could not answer one opinion is not asked again about the next.
    """

    def __init__(
        self,
        context: ApplicationContext,
        *,
        run_id: str,
        project_id: str,
        version_id: str,
        mode: str,
        primary: ModelSuggestionSource,
        fallback: ModelSuggestionSource | None,
        provider: str,
        config: SuggestionLoopConfig | None = None,
        redactor: Redactor | None = None,
        approvals: Mapping[str, ApprovalId] | None = None,
        grants: Sequence[Grant] = (),
        destination: str = "",
        subject_ref: str = "",
    ) -> None:
        self._context = context
        self._run_id = run_id
        self._project_id = project_id
        self._version_id = version_id
        self._mode = mode
        self._primary = primary
        self._fallback = fallback
        self._provider = provider
        self._config = config if config is not None else SuggestionLoopConfig()
        self._redactor = redactor if redactor is not None else Redactor()
        self._approvals = approvals if approvals is not None else {}
        self._grants = list(grants)
        self._destination = destination
        self._subject_ref = subject_ref or project_id
        self._exhausted = False
        self._consecutive_failures = 0
        self._stopped_reason: str | None = None
        self._suggestions_recorded = 0
        self._opinions_skipped = 0
        self._entries: list[dict[str, object]] = []
        self._started_at = datetime.now(UTC)

    # --- the run ----------------------------------------------------------

    def run(self) -> ModelSuggestionRunData:
        """Generate suggestions for every locatable opinion, under the ceilings.

        The opinions are read through the chain's own listing (which applies
        the material permission), filtered to the ones a suggestion can be
        asked for — a comment with text, anchored to a passage — and walked
        in the order the reader found them. The manuscript's paragraphs are
        read once and handed to every source, so each source can wrap its
        answer in the seam's own units. The first stop condition to fire
        ends the walk, and the reason is written on the run row.
        """
        events = list_feedback_events(
            self._context, project_id=self._project_id, version_id=self._version_id
        )
        paragraphs = self._read_paragraphs()
        self._primary.bind_paragraphs(paragraphs)
        if self._fallback is not None:
            self._fallback.bind_paragraphs(paragraphs)
        for event in events:
            if not _locatable(event):
                continue
            if self._stopped_reason is not None:
                self._opinions_skipped += 1
                continue
            self._run_one(event)
        return self._finish()

    def _read_paragraphs(self) -> tuple[str, ...]:
        """The manuscript's paragraphs, in document order, in the accepted view.

        The read is the workbench's own — the same function the middle
        column calls — so the paragraphs a source rewrites are the
        paragraphs a reviewer sees, numbered the same way. A read the
        policy refuses leaves the sources with no paragraphs, and every
        edit they propose then carries the anchor's own text, which the
        apply step can still locate.
        """
        from labcairn.application.review import read_review_manuscript

        try:
            manuscript = read_review_manuscript(
                self._context, project_id=self._project_id, version_id=self._version_id
            )
        except ApplicationRefusedError:
            return ()
        return tuple(paragraph.text for paragraph in manuscript.paragraphs)

    # --- one opinion ------------------------------------------------------

    def _run_one(self, event: FeedbackEvent) -> None:
        """Ask, retry, fall back, record — for one opinion."""
        if not self._within_request_budget(event):
            return
        if self._fallback is not None and not self._exhausted:
            # The real path: consent, then bounded retries.
            approval_id = self._spend_approval(event)
            if approval_id is None:
                return
            attempts = self._config.retry_attempts + 1
            status = _RETRY
            for attempt in range(1, attempts + 1):
                if self._stopped_reason is not None:
                    return
                status = self._attempt_with(
                    self._primary, event, attempts=attempt, approval_id=approval_id
                )
                if status != _RETRY:
                    break
                if attempt < attempts and self._config.backoff_base_s > 0:
                    time.sleep(self._config.backoff_base_s * attempt)
            if status == _ANSWERED:
                return
            # The real model gave no answer — the retries were spent, or the
            # failure was one retrying cannot fix. The run falls back to the
            # substitute, and stays fallen back.
            self._exhausted = True
            if status == _RETRY:
                self._entries.append(
                    _entry(
                        event,
                        source=self._primary.model_id,
                        outcome="exhausted",
                        attempts=attempts,
                    )
                )
            self._count_failure()
            if self._stopped_reason is not None:
                return
            self._fall_back(event)
            return
        # The substitute path: a substitute run's own source, or a real run
        # that has already fallen back.
        source = self._fallback if self._exhausted and self._fallback is not None else self._primary
        self._attempt_with(source, event, attempts=1)

    def _attempt_with(
        self,
        source: ModelSuggestionSource,
        event: FeedbackEvent,
        *,
        attempts: int,
        approval_id: str | None = None,
    ) -> str:
        """One attempt, classified and recorded.

        Returns ``_ANSWERED`` when the opinion is finished — an edit, or an
        honest empty set; ``_GIVE_UP`` when the failure is one retrying
        cannot fix (auth, policy, refusal) and the caller should fall back
        rather than try again; ``_RETRY`` when the failure is retryable and
        the caller may back off and ask again.

        **``approval_id`` is the approval the request spent, if it spent
        one.** The real path has already consumed it by the time the model
        is asked, and the entry records it so a reader can say which
        approval paid for which opinion's request. The substitute path
        spends none, and says so by recording none.
        """
        started = time.monotonic()
        tokens_before = source.accounting.tokens_estimated
        try:
            edit = source(event)
        except Exception as error:
            elapsed = time.monotonic() - started
            failure = classify_exception(error, redactor=self._redactor)
            self._entries.append(
                _entry(
                    event,
                    source=source.model_id,
                    outcome="failed",
                    attempts=attempts,
                    elapsed_s=elapsed,
                    tokens=source.accounting.tokens_estimated - tokens_before,
                    detail=failure.kind.value,
                    retryable=failure.retryable,
                    approval_id=approval_id,
                )
            )
            return _RETRY if failure.retryable else _GIVE_UP
        elapsed = time.monotonic() - started
        self._entries.append(
            _entry(
                event,
                source=source.model_id,
                outcome="empty" if edit is None else "answered",
                attempts=attempts,
                elapsed_s=elapsed,
                tokens=source.accounting.tokens_estimated - tokens_before,
                approval_id=approval_id,
            )
        )
        if edit is not None:
            # A suggestion is a record, not a decision: written under the
            # source's own author, applied by nobody until the reviewer says.
            self._store_suggestion(event, edit)
            self._consecutive_failures = 0
        self._check_token_budget()
        return _ANSWERED

    def _fall_back(self, event: FeedbackEvent) -> None:
        """Let the substitute answer an opinion the real model could not.

        **The substitute is labelled twice** — on the run row, whose model
        id becomes the substitute's from here on, and on the suggestion
        row, whose author is the substitute's. Neither surface can be read
        as the real model's answer.
        """
        assert self._fallback is not None
        self._attempt_with(self._fallback, event, attempts=1)

    # --- the gates --------------------------------------------------------

    def _spend_approval(self, event: FeedbackEvent) -> str | None:
        """Run the transmit gate for one real request, and spend its approval.

        **No approval, no request.** An opinion whose approval is missing
        is recorded as unauthorised and skipped — the loop does not ask a
        model about an opinion nobody authorised. A gate refusal (the grant
        does not cover this material, this destination, this purpose) is a
        refusal, not a retry: the approval stays unspent for the remedy a
        person applies, and the opinion is recorded as refused.

        **The id of the approval that was spent is what this returns**, and
        ``None`` means no approval was spent: none was presented, or the
        gate refused and left it unspent. The caller records it on the
        request's own entry, so a reader of the run can say which approval
        paid for which opinion.
        """
        approval_id = self._approvals.get(event.feedback_id)
        if approval_id is None:
            self._entries.append(
                _entry(event, source=self._primary.model_id, outcome="unauthorised")
            )
            self._opinions_skipped += 1
            return None
        use = suggestion_approval_use(
            self._context,
            event,
            provider=self._provider,
            model=self._primary.model_id,
            redactor=self._redactor,
        )
        try:
            transmit_request(
                self._context,
                approval_id,
                self._grants,
                use=use,
                subject_ref=self._subject_ref,
                destination=self._destination,
                purpose=MODEL_SUGGESTION_PURPOSE,
                at=datetime.now(UTC),
            )
        except ApplicationRefusedError as error:
            self._entries.append(
                _entry(
                    event,
                    source=self._primary.model_id,
                    outcome="refused",
                    detail=error.reason.value,
                )
            )
            self._count_failure()
            return None
        return str(approval_id)

    def _within_request_budget(self, event: FeedbackEvent) -> bool:
        """The request ceiling, checked before the call it bounds.

        A ceiling checked only afterwards bounds nothing — the overshoot
        would already be paid. Crossing it stops the run before the request
        exists, which is why the overshoot is zero requests. The ceiling
        bounds the **real** model's calls; the substitute's are local and
        free, and asking them would only pad the account.
        """
        ceiling = self._config.max_requests
        if ceiling is not None and self._primary.accounting.requests_made >= ceiling:
            self._stopped_reason = _STOP_REQUEST_BUDGET
            self._entries.append(
                _entry(event, source=self._primary.model_id, outcome="budget_stop")
            )
            self._opinions_skipped += 1
            return False
        return True

    def _check_token_budget(self) -> None:
        """The token-estimate ceiling, checked after the call it bounds.

        The estimate is the only figure the transport seam offers, and it
        is recorded as an estimate. The call that crosses the ceiling is
        the last one: the next opinion is skipped, and the row says which
        stop fired.
        """
        ceiling = self._config.max_tokens
        if ceiling is not None and self._tokens_total() > ceiling:
            self._stopped_reason = _STOP_TOKEN_BUDGET

    def _count_failure(self) -> None:
        """One more failed or refused opinion, and the stop it may fire."""
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._config.max_consecutive_failures:
            self._stopped_reason = _STOP_CONSECUTIVE_FAILURES

    # --- the record -------------------------------------------------------

    def _store_suggestion(self, event: FeedbackEvent, edit: ApprovedEdit) -> None:
        """Write one suggestion, verbatim in the seam's units, under its author."""
        record_review_suggestion(
            self._context,
            project_id=self._project_id,
            version_id=self._version_id,
            feedback_id=event.feedback_id,
            part=edit.part,
            paragraph=edit.paragraph,
            old_text=edit.old_text,
            new_text=edit.new_text,
            author=edit.author,
            proposed_at=datetime.fromisoformat(edit.date),
        )
        self._suggestions_recorded += 1

    def _tokens_total(self) -> int:
        """Both sources' estimates, together. The run's own figure."""
        total = self._primary.accounting.tokens_estimated
        if self._fallback is not None:
            total += self._fallback.accounting.tokens_estimated
        return total

    def _requests_total(self) -> int:
        """Both sources' calls, together. The run's own figure."""
        total = self._primary.accounting.requests_made
        if self._fallback is not None:
            total += self._fallback.accounting.requests_made
        return total

    def _finish(self) -> ModelSuggestionRunData:
        """Write the run row and return the caller's reading of it.

        The row carries the mode, the model id that was in force at the end
        (the substitute's, if the run fell back), the counts, the stop that
        fired, and the per-opinion request entries as JSON — counts and
        class names, never request text.
        """
        finished_at = datetime.now(UTC)
        model_id = (
            self._fallback.model_id
            if self._exhausted and self._fallback is not None
            else self._primary.model_id
        )
        row = ModelSuggestionRunRow(
            run_id=self._run_id,
            project_id=self._project_id,
            version_id=self._version_id,
            mode=self._mode,
            model_id=model_id,
            requests_made=self._requests_total(),
            tokens_estimated=self._tokens_total(),
            stopped_reason=self._stopped_reason,
            suggestions_recorded=self._suggestions_recorded,
            opinions_skipped=self._opinions_skipped,
            requests_json=self._entries,
            started_at=self._started_at,
            finished_at=finished_at,
        )
        session = self._context.store.session
        session.add(row)
        session.commit()
        return ModelSuggestionRunData(
            run_id=self._run_id,
            project_id=self._project_id,
            version_id=self._version_id,
            mode=self._mode,
            model_id=model_id,
            requests_made=self._requests_total(),
            tokens_estimated=self._tokens_total(),
            stopped_reason=self._stopped_reason,
            suggestions_recorded=self._suggestions_recorded,
            opinions_skipped=self._opinions_skipped,
            started_at=self._started_at,
            finished_at=finished_at,
            requests=tuple(_entry_from_record(record, mode=self._mode) for record in self._entries),
        )


#: Why a loop run stopped before the opinions ran out. The closed
#: vocabulary the run row's ``stopped_reason`` holds; ``None`` on the row
#: means the walk finished because the opinions ran out.
StopReason = str

_STOP_REQUEST_BUDGET: StopReason = "request_budget"
_STOP_TOKEN_BUDGET: StopReason = "token_budget"
_STOP_CONSECUTIVE_FAILURES: StopReason = "consecutive_failures"

#: What one attempt came to, in the loop's own control flow.
_ANSWERED: str = "answered"
_GIVE_UP: str = "give_up"
_RETRY: str = "retry"


def _locatable(event: FeedbackEvent) -> bool:
    """Whether a suggestion can be asked for this opinion at all.

    A comment with no text, or one whose anchor covers no passage, has
    nothing for a model to rewrite. Asking anyway would be a request about
    nothing; the opinion is left out of the walk rather than pretended
    handled.
    """
    if not event.comment_text.strip():
        return False
    return event.anchor_text is not None and bool(event.anchor_text.strip())


def _entry(
    event: FeedbackEvent,
    *,
    source: str,
    outcome: str,
    attempts: int = 0,
    elapsed_s: float = 0.0,
    tokens: int = 0,
    detail: str = "",
    retryable: bool | None = None,
    approval_id: str | None = None,
) -> dict[str, object]:
    """One request entry: counts, class names, and the opinion's id.

    The request text is never here. The entry answers "what happened to
    this opinion, at what cost" and nothing about what was said.

    **``approval_id`` is the approval that was spent on this request, and
    only that.** The transmit gate consumes the approval before the model
    is asked, so an entry that carries an id is an entry whose approval is
    gone, and an entry without one is an entry where no approval was
    consumed — the caller presented none, or the gate refused and left it
    unspent. It is an id, never a digest of the request and never the
    request itself.
    """
    record: dict[str, object] = {
        "feedback_id": event.feedback_id,
        "source": source,
        "outcome": outcome,
        "attempts": attempts,
        "elapsed_s": round(elapsed_s, 6),
        "tokens_estimated": tokens,
        "detail": detail,
    }
    if retryable is not None:
        record["retryable"] = retryable
    if approval_id is not None:
        record["approval_id"] = approval_id
    return record


def suggest_for_version(
    context: ApplicationContext,
    *,
    run_id: str,
    project_id: str,
    version_id: str,
    mode: str,
    provider: str = "",
    transport: ModelSuggestionTransport | None = None,
    approvals: Mapping[str, ApprovalId] | None = None,
    grants: Sequence[Grant] = (),
    destination: str = "",
    subject_ref: str = "",
    config: SuggestionLoopConfig | None = None,
    redactor: Redactor | None = None,
) -> ModelSuggestionRunData:
    """Run the suggestion loop over one version's pending opinions.

    **The entry point the route calls.** ``mode="substitute"`` drives the
    local stand-in and needs no consent, because nothing leaves the
    machine. ``mode="real"`` drives the transport the service was wired
    with and spends one digest-bound approval per opinion; a service with
    no real transport refuses rather than simulates, because an invented
    suggestion would put words in a model's mouth that no model said.

    :raises ApplicationRefusedError: a real run was asked of a service with
        no real transport, or the mode is not one of the two.
    """
    if mode == MODEL_SUGGESTION_MODE_SUBSTITUTE:
        primary: ModelSuggestionSource = SubstituteSuggestionSource()
        fallback: ModelSuggestionSource | None = None
    elif mode == MODEL_SUGGESTION_MODE_REAL:
        if transport is None:
            raise ApplicationRefusedError(
                ApplicationRefusal.MODEL_SUGGESTION_NO_PROVIDER,
                "no real-model transport is wired into this service, so there is "
                "nothing to ask. A real run is refused rather than simulated: an "
                "invented suggestion would put words in a model's mouth that no "
                "model said.",
            )
        primary = ProviderSuggestionSource(transport, redactor=redactor)
        fallback = SubstituteSuggestionSource()
    else:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the mode must be {MODEL_SUGGESTION_MODE_REAL!r} or "
            f"{MODEL_SUGGESTION_MODE_SUBSTITUTE!r}, not {mode!r}.",
        )
    loop = SuggestionLoop(
        context,
        run_id=run_id,
        project_id=project_id,
        version_id=version_id,
        mode=mode,
        primary=primary,
        fallback=fallback,
        provider=provider,
        config=config,
        redactor=redactor,
        approvals=approvals,
        grants=grants,
        destination=destination,
        subject_ref=subject_ref,
    )
    return loop.run()


def parse_approval_ids(raw: Mapping[str, str]) -> dict[str, ApprovalId]:
    """The approvals a suggest request presented, parsed into the ledger's ids.

    A malformed id and a well-formed one are separated here, so the route
    refuses the malformed before anything runs rather than discovering the
    mistake at the first opinion that needs it.
    """
    parsed: dict[str, ApprovalId] = {}
    for feedback_id, value in raw.items():
        try:
            parsed[feedback_id] = ApprovalId(uuid.UUID(value))
        except ValueError as error:
            raise ApplicationRefusedError(
                ApplicationRefusal.ARGUMENTS_INVALID,
                f"the approval id for the opinion {feedback_id!r} is not a "
                f"usable approval id: {value!r}.",
            ) from error
    return parsed
