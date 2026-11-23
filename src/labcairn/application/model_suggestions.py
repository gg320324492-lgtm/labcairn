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
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from labcairn.application.approvals import ApprovalUse
from labcairn.application.context import ApplicationContext
from labcairn.application.model_transmit import transmit_request
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.application.review import record_review_suggestion
from labcairn.core.ids import ApprovalId
from labcairn.core.providers.protocol import ModelRequest
from labcairn.db.models import ModelSuggestionRunRow, PaperVersionRow, SourceRow
from labcairn.editing.drafts import ApprovedEdit
from labcairn.papers.feedback import FeedbackEvent, list_feedback_events
from labcairn.providers.errors import classify_exception
from labcairn.providers.redaction import Redactor
from labcairn.security.capabilities import CapabilityId, ModelRequestArgs
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
    "StopReason",
    "SubstituteSuggestionSource",
    "SubstituteTransport",
    "SuggestionLoopConfig",
    "desensitised_prompt",
    "suggest_for_version",
    "suggestion_approval_use",
]

#: The two modes a suggestion run may take. ``real`` asks the authorised
#: model and spends one digest-bound approval per request; ``substitute``
#: asks the local stand-in and spends nothing, because nothing leaves the
#: machine.
MODEL_SUGGESTION_MODE_REAL: str = "real"
MODEL_SUGGESTION_MODE_SUBSTITUTE: str = "substitute"

#: The material-purpose every suggestion request is judged under.
MODEL_SUGGESTION_PURPOSE: str = "suggestion_draft"

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
    None` — with the two members the loop's accounting needs: the model id
    the source answers as, and the counter its calls accumulate into.
    Returning ``None`` says the source has no suggestion for this opinion —
    an honest answer, not a failure. A transport failure raises.
    """

    model_id: str
    accounting: SourceAccounting

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
        """
        assert event.anchor_text is not None
        text = answer.strip()
        if not text or text == event.anchor_text.strip():
            return None
        return ApprovedEdit(
            part=_DOCUMENT_PART,
            paragraph=event.anchor_paragraph or 1,
            old_text=event.anchor_text,
            new_text=text,
            author=f"{REAL_AUTHOR_PREFIX}{self.model_id}",
            date=self._clock().isoformat(),
        )


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

    def __call__(self, event: FeedbackEvent) -> ApprovedEdit | None:
        """One deterministic suggestion from the opinion's own texts."""
        if not event.comment_text.strip():
            return None
        assert event.anchor_text is not None
        if not event.anchor_text.strip():
            return None
        self.accounting.requests_made += 1
        comment = event.comment_text.strip()
        new_text = (
            f"{event.anchor_text.strip()} "
            f"(revised to address the comment: {comment[:120]})"
        )
        self.accounting.tokens_estimated += _estimate_tokens(new_text)
        return ApprovedEdit(
            part=_DOCUMENT_PART,
            paragraph=event.anchor_paragraph or 1,
            old_text=event.anchor_text,
            new_text=new_text,
            author=SUBSTITUTE_AUTHOR,
            date=self._clock().isoformat(),
        )


#: Why a loop run stopped before the opinions ran out. The closed
#: vocabulary the run row's ``stopped_reason`` holds; ``None`` on the row
#: means the walk finished because the opinions ran out.
StopReason = str

_STOP_REQUEST_BUDGET: StopReason = "request_budget"
_STOP_TOKEN_BUDGET: StopReason = "token_budget"
_STOP_CONSECUTIVE_FAILURES: StopReason = "consecutive_failures"
_STOP_CANCELLED: StopReason = "cancelled"


@dataclass(frozen=True, slots=True)
class SuggestionLoopConfig:
    """The ceilings and stops one loop run is bounded by.

    The numbers are the authorisation record's own (G0 §5). Every ceiling
    is optional; a run with no ceiling at all is not refused here — the
    *route* decides what a mode without a budget may ask for — but a real
    run the owner authorised carries the owner's numbers.
    """

    #: LabCairn-issued transport calls, counted per attempt: a retry is a
    #: request and costs a request.
    max_requests: int | None = None
    #: The token estimate ceiling. Checked against the counters after each
    #: call; the call that crosses it is the last one.
    max_tokens: int | None = None
    #: Consecutive failed or refused opinions after which the run stops.
    max_consecutive_failures: int = 3
    #: Transport retries per opinion for a retryable failure.
    retry_attempts: int = 2
    #: Bounded backoff base, in seconds: the delay before retry *n* is
    #: ``backoff_base_s * n``. Zero in tests and in substitute runs.
    backoff_base_s: float = 0.0


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
    prompt = desensitised_prompt(
        event, redactor=redactor if redactor is not None else Redactor()
    )
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


def _version_resource(context: ApplicationContext, version_id: str):
    """The material resource one manuscript version was made from.

    The approval names the material by its path in its root, the way
    extraction names a source — the locator names a place *inside* the
    file and is not a resource key.
    """
    version = context.store.session.get(PaperVersionRow, version_id)
    if version is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.TASK_NOT_FOUND,
            f"the store holds no manuscript version with the id {version_id!r}.",
        )
    source = context.store.session.get(SourceRow, version.source_id)
    if source is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.SOURCE_NOT_FOUND,
            f"the version {version_id!r} names the source {version.source_id!r}, "
            "which the ledger does not hold.",
        )
    return context.resource_for(source.relative_path)


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
        real_transport: ModelSuggestionTransport | None = None,
        grants: Sequence[Grant] = (),
        destination: str = "",
    ) -> None:
        self.real_transport = real_transport
        self.grants = grants
        self.destination = destination


class SuggestionLoop:
    """One loop run: the opinions of one version, one budget, one account.

    **The loop owns the gates, the retries, the stops and the account; the
    source owns one attempt.** A real run spends one digest-bound approval
    per opinion before its first attempt — the same order claim extraction
    holds, at the opinion's granularity — and classifies every transport
    failure at the boundary: retryable failures back off and retry within
    the budget, non-retryable ones are recorded and not retried, and a run
    whose consecutive failures reach the ceiling stops, naming the reason.
    """

    def __init__(
        self,
        context: ApplicationContext,
        *,
        run_id: str,
        project_id: str,
        version_id: str,
        mode: str,
        source: ModelSuggestionSource,
        substitute: ModelSuggestionSource | None = None,
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
        self._source = source
        self._substitute = substitute
        self._config = config if config is not None else SuggestionLoopConfig()
        self._redactor = redactor if redactor is not None else Redactor()
        self._approvals = approvals if approvals is not None else {}
        self._grants = list(grants)
        self._destination = destination
        self._subject_ref = subject_ref or project_id
        self._consecutive_failures = 0
        self._stopped_reason: str | None = None
        self._suggestions_recorded = 0
        self._opinions_skipped = 0
        self._entries: list[dict[str, object]] = []
        self._model_id = source.model_id
        self._started_at = datetime.now(UTC)

    # --- the run ----------------------------------------------------------

    def run(self) -> ModelSuggestionRunData:
        """Generate suggestions for every locatable opinion, under the ceilings.

        The opinions are read through the chain's own listing (which applies
        the material permission), filtered to the ones a suggestion can be
        asked for — a comment with text, anchored to a passage — and walked
        in the order the reader found them. The first stop condition to
        fire ends the walk, and the reason is written on the run row.
        """
        events = list_feedback_events(
            self._context, project_id=self._project_id, version_id=self._version_id
        )
        for event in events:
            if not _locatable(event):
                continue
            if self._stopped_reason is not None:
                self._opinions_skipped += 1
                continue
            self._run_one(event)
        return self._finish()

    # --- one opinion ------------------------------------------------------

    def _run_one(self, event: FeedbackEvent) -> None:
        """Ask, retry, fall back, record — for one opinion."""
        if self._mode == MODEL_SUGGESTION_MODE_REAL:
            if not self._spend_approval(event):
                return
        if not self._within_request_budget():
            return
        attempts = self._config.retry_attempts + 1
        for attempt in range(1, attempts + 1):
            if self._stopped_reason is not None:
                return
            outcome = self._attempt(event, attempt)
            if outcome:
                return
        # The retries are spent. The substitute answers next, if there is
        # one — and once the run has fallen back, it stays fallen back.
        self._consecutive_failures += 1
        self._entries.append(
            _entry(event, source=self._source.model_id, outcome="exhausted", attempts=attempts)
        )
        if self._consecutive_failures >= self._config.max_consecutive_failures:
            self._stopped_reason = _STOP_CONSECUTIVE_FAILURES
            return
        self._fall_back(event)

    def _attempt(self, event: FeedbackEvent, attempt: int) -> bool:
        """One attempt, classified and recorded. ``True`` when the opinion is done.

        A retryable transport failure returns ``False`` after recording, and
        the caller backs off and tries again; every other outcome — an
        edit, an honest empty set, a non-retryable failure — finishes the
        opinion here.
        """
        source = self._source
        started = time.monotonic()
        before = source.accounting.requests_made
        try:
            edit = source(event)
        except Exception as error:  # noqa: BLE001 - the loop classifies, not crashes
            elapsed = time.monotonic() - started
            failure = classify_exception(error, redactor=self._redactor)
            self._entries.append(
                _entry(
                    event,
                    source=source.model_id,
                    outcome="failed",
                    attempts=attempt,
                    elapsed_s=elapsed,
                    tokens=self._tokens_since(before),
                    detail=failure.kind.value,
                    retryable=failure.retryable,
                )
            )
            if not failure.retryable:
                # Auth, policy, refusal: the same request would be refused
                # again. Recorded, not retried, and counted toward the stop.
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._config.max_consecutive_failures:
                    self._stopped_reason = _STOP_CONSECUTIVE_FAILURES
                return True
            return False
        elapsed = time.monotonic() - started
        tokens = self._tokens_since(before)
        self._entries.append(
            _entry(
                event,
                source=source.model_id,
                outcome="empty" if edit is None else "answered",
                attempts=attempt,
                elapsed_s=elapsed,
                tokens=tokens,
            )
        )
        if edit is not None:
            # A suggestion is a record, not a decision: written under the
            # source's own author, applied by nobody until the reviewer says.
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
            self._consecutive_failures = 0
        if self._over_token_budget():
            self._stopped_reason = _STOP_TOKEN_BUDGET
        return True

    def _fall_back(self, event: FeedbackEvent) -> None:
        """Let the substitute answer an opinion the real model could not.

        **The substitute is labelled twice** — on the run row, whose model
        id becomes the substitute's from here on, and on the suggestion
        row, whose author is the substitute's. Neither surface can be read
        as the real model's answer.
        """
        if self._substitute is None:
            return
        self._source = self._substitute
        self._model_id = self._substitute.model_id
        started = time.monotonic()
        before = self._substitute.accounting.requests_made
        try:
            edit = self._substitute(event)
        except Exception as error:  # noqa: BLE001 - the fallback is best-effort
            self._entries.append(
                _entry(
                    event,
                    source=self._substitute.model_id,
                    outcome="failed",
                    attempts=1,
                    elapsed_s=time.monotonic() - started,
                    detail=type(error).__name__,
                )
            )
            return
        self._entries.append(
            _entry(
                event,
                source=self._substitute.model_id,
                outcome="empty" if edit is None else "answered",
                attempts=1,
                elapsed_s=time.monotonic() - started,
                tokens=self._substitute.accounting.tokens_estimated - before,
            )
        )
        if edit is not None:
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
            self._consecutive_failures = 0

    # --- the gates --------------------------------------------------------

    def _spend_approval(self, event: FeedbackEvent) -> bool:
        """Run the transmit gate for one real request, and spend its approval.

        **No approval, no request.** An opinion whose approval is missing
        is recorded as unauthorised and skipped — the loop does not ask a
        model about an opinion nobody authorised. A gate refusal (the grant
        does not cover this material, this destination, this purpose) is a
        refusal, not a retry: the approval stays unspent for the remedy a
        person applies, and the opinion is recorded as refused.
        """
        approval_id = self._approvals.get(event.feedback_id)
        if approval_id is None:
            self._entries.append(
                _entry(event, source=self._source.model_id, outcome="unauthorised")
            )
            self._opinions_skipped += 1
            return False
        use = suggestion_approval_use(
            self._context,
            event,
            provider=self._mode,
            model=self._source.model_id,
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
                    source=self._source.model_id,
                    outcome="refused",
                    detail=error.reason.value,
                )
            )
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._config.max_consecutive_failures:
                self._stopped_reason = _STOP_CONSECUTIVE_FAILURES
            return False
        return True

    def _within_request_budget(self) -> bool:
        """The request ceiling, checked before the call it bounds.

        A ceiling checked only afterwards bounds nothing — the overshoot
        would already be paid. Crossing it stops the run before the request
        exists, which is why the overshoot is zero requests.
        """
        ceiling = self._config.max_requests
        if ceiling is not None and self._source.accounting.requests_made >= ceiling:
            self._stopped_reason = _STOP_REQUEST_BUDGET
            return False
        return True

    def _over_token_budget(self) -> bool:
        """Whether the token estimate has crossed its ceiling."""
        ceiling = self._config.max_tokens
        return ceiling is not None and self._source.accounting.tokens_estimated > ceiling

    def _tokens_since(self, before: int) -> int:
        """The tokens the last attempt added, for the entry's figure."""
        return max(0, self._source.accounting.tokens_estimated - before)

    # --- the record -------------------------------------------------------

    def _finish(self) -> ModelSuggestionRunData:
        """Write the run row and return the caller's reading of it.

        The row carries the mode, the model id that was in force at the end
        (the substitute's, if the run fell back), the counts, the stop that
        fired, and the per-opinion request entries as JSON — counts and
        class names, never request text.
        """
        finished_at = datetime.now(UTC)
        row = ModelSuggestionRunRow(
            run_id=self._run_id,
            project_id=self._project_id,
            version_id=self._version_id,
            mode=self._mode,
            model_id=self._model_id,
            requests_made=self._source.accounting.requests_made,
            tokens_estimated=self._source.accounting.tokens_estimated,
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
            model_id=self._model_id,
            requests_made=self._source.accounting.requests_made,
            tokens_estimated=self._source.accounting.tokens_estimated,
            stopped_reason=self._stopped_reason,
            suggestions_recorded=self._suggestions_recorded,
            opinions_skipped=self._opinions_skipped,
            started_at=self._started_at,
            finished_at=finished_at,
        )


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
) -> dict[str, object]:
    """One request entry: counts, class names, and the opinion's id.

    The request text is never here. The entry answers "what happened to
    this opinion, at what cost" and nothing about what was said.
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
    return record


def suggest_for_version(
    context: ApplicationContext,
    *,
    run_id: str,
    project_id: str,
    version_id: str,
    mode: str,
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
        source: ModelSuggestionSource = SubstituteSuggestionSource()
        substitute: ModelSuggestionSource | None = None
    elif mode == MODEL_SUGGESTION_MODE_REAL:
        if transport is None:
            raise ApplicationRefusedError(
                ApplicationRefusal.MODEL_SUGGESTION_NO_PROVIDER,
                "no real-model transport is wired into this service, so there is "
                "nothing to ask. A real run is refused rather than simulated: an "
                "invented suggestion would put words in a model's mouth that no "
                "model said.",
            )
        source = ProviderSuggestionSource(transport, redactor=redactor)
        substitute = SubstituteSuggestionSource()
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
        source=source,
        substitute=substitute,
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
