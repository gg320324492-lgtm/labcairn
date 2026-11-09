"""The bounded run: a case goes out only through every gate, or not at all.

LC-P3-06 deliverables 1 and 3, substitute-first half (work orders §11 §4.8,
left column). This module is the run harness the rehearsal drives: it takes a
:class:`~labcairn.providers.deidentify.DeidentifiedCase`, walks each of the
case's outbound requests through the whole gate in the adapter's own order,
and refuses the run before any request exists when the authorisation the owner
answered (§4.9) is not in hand.

The rung order is the adapter's, restated as the ladder the rehearsal climbs:

1. **Budget preflight, fail-closed.** Q4's answer is a *number* — 20 requests
   / 50 000 tokens. ``BoundedRun`` refuses a run whose budget carries no
   ceiling at all, because an unbounded run is not a bounded run; and the
   adapter's own pre-flight refuses a ceiling it cannot evaluate. The
   rehearsal proves both refusals leave zero calls on the recording upstream.
2. **Probe-record gate.** A supplier name is not a capability. The adapter's
   capability gate refuses an endpoint with no probe record — the model name
   in a configuration is not evidence that the endpoint speaks tool calls —
   and the rehearsal proves the refusal precedes any wire.
3. **Consent bridge.** ``CapabilityId.MODEL_REQUEST`` is the only permission
   capability with ``Effect.NETWORK``, and every outbound request is ASK under
   the default policy. The adapter hands the port the request; the port spends
   one digest-bound approval per request; an excerpt request whose port is
   not bound to that excerpt's own digest is refused here, before the
   provider is even built.
4. **Capability refusal.** A probe record that says ``UNSUPPORTED`` for a
   capability the request needs is refused, again before any wire.

The harness adds the two things the adapter deliberately does not hold: the
**compound stop-loss** (Q7: three consecutive failed requests, or a per-case
proposal refusal rate above 50%) and the **run record** — digests and counts,
never text (Q3).

Why the harness is in the provider layer
----------------------------------------
It imports nothing from :mod:`labcairn.security` and none of the application
layer: the consent decision crosses as the caller-supplied
:class:`~labcairn.providers.consent.OutboundConsent` port, exactly as ADR-0006
fixes the boundary, and ``tests/test_capability_namespaces.py`` watches that
shape for the whole of ``providers/``. What the rehearsal assembles — the
approval ledger, the digest-bound approvals — lives on the application side,
in the test that drives this harness.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from labcairn.core.providers.protocol import ModelRequest
from labcairn.providers.adapter import (
    ExchangeRecord,
    PydanticAiModelProvider,
    UpstreamModel,
    prompt_digest,
)
from labcairn.providers.budget import RunBudget
from labcairn.providers.capabilities import Capability, ProviderCapabilities
from labcairn.providers.consent import OutboundConsent
from labcairn.providers.deidentify import DeidentifiedCase
from labcairn.providers.errors import FailureKind, ProviderError
from labcairn.providers.ledger import RunLedger
from labcairn.providers.usage_capture import UsageCapture

#: The owner's answered budget shape (§4.9, Q4): 20 requests / 50 000 tokens
#: per bounded run. Restated here as the rehearsal's fixture, not as
#: configuration — the tree carries no supplier route, and this is not one.
REHEARSAL_MAX_REQUESTS: int = 20
REHEARSAL_MAX_TOTAL_TOKENS: int = 50_000

#: Q7's compound stop-loss, first arm: three consecutive failed requests.
CONSECUTIVE_FAILURE_LIMIT: int = 3

#: Q7's second arm: a per-case proposal refusal rate above this stops the run.
#: 0.5 means "more than half the excerpt requests were refused".
PROPOSAL_REFUSAL_RATE_LIMIT: float = 0.5

#: The ``FailureKind`` values that mean the ladder refused *before the wire*.
#: A request ending in one of these was never issued; the recording upstream
#: proves it, and the stop-loss's second arm counts it as a refusal.
#: Everything else a :class:`~labcairn.providers.errors.ProviderError` can
#: carry is a *failure* — the request was issued and went wrong — and counts
#: toward the stop-loss's first arm.
PRE_WIRE_KINDS: frozenset[FailureKind] = frozenset(
    {
        FailureKind.CAPABILITY_UNAVAILABLE,
        FailureKind.BUDGET_EXHAUSTED,
        FailureKind.BUDGET_ENFORCEMENT_UNAVAILABLE,
        FailureKind.OUTBOUND_REFUSED,
        FailureKind.CANCELLED,
    }
)


@runtime_checkable
class DigestBoundConsent(Protocol):
    """A consent port that names the excerpt digest its approval binds.

    Q3's *per-excerpt digest-bound outbound scope*: each excerpt leaves only
    under its own approval. The approval's arguments carry the digest on the
    application side; this attribute is the provider side's view of the same
    fact, so the harness can pair a request with its port without importing
    the permission vocabulary.
    """

    bound_excerpt_digest: str


class RunNotAuthorisedError(Exception):
    """The run's authorisation is not in hand. Nothing was sent.

    Raised before any request exists — this is the fail-closed shape the
    degraded-path witnesses measure: the refusal is the whole behaviour.
    """


class StopLossTriggeredError(Exception):
    """The compound stop-loss fired. The run stops here.

    Q7's answer makes the trigger operator-watched, not automatic; the harness
    raises so the operator's loop can catch it and record. Either arm alone is
    enough, and the message names which arm fired.
    """


class RunRequestRefusedError(Exception):
    """One request inside a case was refused or failed. The case stops.

    Distinct from :class:`RunNotAuthorisedError`: a per-request refusal is the
    ladder working as designed (that is what "refusal" means in the stop-loss's
    second arm), while a run-level refusal is the authorisation being absent.
    The message carries the refusal's ``FailureKind`` and the stop-loss verdict —
    never the request text, which is Q3's discipline applied to this module's
    own error paths.
    """

    def __init__(self, *, case_id: str, where: str, kind: FailureKind, verdict: str) -> None:
        super().__init__(
            f"case {case_id!r}: {where} ended {kind.value}; the case stops. "
            f"stop-loss verdict {verdict}"
        )
        self.case_id = case_id
        self.where = where
        self.kind = kind
        self.verdict = verdict


class StopLossVerdict(StrEnum):
    """What the compound trigger says after an event is recorded."""

    HOLD = "hold"
    STOP_CONSECUTIVE_FAILURES = "stop_consecutive_failures"
    STOP_REFUSAL_RATE = "stop_refusal_rate"


@dataclass(frozen=True, slots=True)
class RunRequestRecord:
    """One request of the run, as the record may hold it.

    Digests and counts, never text (Q3): the request is named by its digest —
    the same domain-separated spelling the exchange record computes — plus the
    outcome kind it ended with.
    """

    request_digest: str
    case_id: str
    #: The excerpt's own digest, as the case carried it. Equal to
    #: ``request_digest`` for a case the pipeline minted: two paths, one number.
    excerpt_digest: str | None
    #: ``"sent"``, ``"refused"``, or ``"failed"`` — decided by
    #: :data:`PRE_WIRE_KINDS` for everything the provider raised.
    outcome: str
    kind: str | None = None


@dataclass(frozen=True, slots=True)
class RunRecord:
    """The bounded run's record. Safe to export without a disclosure review."""

    started_at: datetime
    finished_at: datetime | None
    requests_made: int
    requests_refused: int
    requests_failed: int
    cases_submitted: int
    cases_completed: int
    stop_loss: StopLossVerdict | None
    requests: tuple[RunRequestRecord, ...] = field(default=())

    def to_counts(self) -> Mapping[str, int]:
        """The counts-only view a log line or a receipt may render."""
        return {
            "requests_made": self.requests_made,
            "requests_refused": self.requests_refused,
            "requests_failed": self.requests_failed,
            "cases_submitted": self.cases_submitted,
            "cases_completed": self.cases_completed,
        }


@dataclass(frozen=True, slots=True)
class _CaseTally:
    """Per-case request accounting, for the stop-loss's second arm."""

    decided: int = 0
    refused: int = 0

    @property
    def refusal_rate(self) -> float:
        if self.decided == 0:
            return 0.0
        return self.refused / self.decided


class CompoundStopLoss:
    """Q7's trigger, watched. The operator arms it; events advance it.

    Two arms, either of which stops the run:

    * **Three consecutive failed requests** — a *failure* is a request that
      was issued and errored (timeout, transport, malformed), not a refusal.
      The adapter's ladder refuses before the wire; those refusals are the
      other arm's input. One success resets the consecutive count.
    * **Per-case proposal refusal rate above 50%** — of the requests a case
      has *decided* (issued or refused), more than half refused. The rate is
      evaluated on completion of a request, so a case whose first request is
      refused sits at rate 1.0 and stops immediately: that is the honest
      reading of "refusal rate above 50%" for a one-request case.
    """

    def __init__(
        self,
        *,
        consecutive_failure_limit: int = CONSECUTIVE_FAILURE_LIMIT,
        refusal_rate_limit: float = PROPOSAL_REFUSAL_RATE_LIMIT,
    ) -> None:
        self._failure_limit = consecutive_failure_limit
        self._rate_limit = refusal_rate_limit
        self._consecutive_failures = 0
        self._tallies: dict[str, _CaseTally] = {}
        self.verdict: StopLossVerdict | None = None

    def record_failure(self, case_id: str) -> StopLossVerdict:
        """A request was issued and failed. Advances arm one."""
        self._consecutive_failures += 1
        if self.verdict is None and self._consecutive_failures >= self._failure_limit:
            self.verdict = StopLossVerdict.STOP_CONSECUTIVE_FAILURES
        return self._verdict_or_hold()

    def record_refusal(self, case_id: str) -> StopLossVerdict:
        """A request was refused before the wire. Advances arm two only."""
        return self._record_case_event(case_id, refused=True)

    def record_success(self, case_id: str) -> StopLossVerdict:
        """A request succeeded. Resets arm one; advances arm two's denominator."""
        self._consecutive_failures = 0
        return self._record_case_event(case_id, refused=False)

    def _record_case_event(self, case_id: str, *, refused: bool) -> StopLossVerdict:
        if self.verdict is not None:
            return self.verdict
        tally = self._tallies.get(case_id, _CaseTally())
        tally = _CaseTally(
            decided=tally.decided + 1,
            refused=tally.refused + (1 if refused else 0),
        )
        self._tallies[case_id] = tally
        if tally.refusal_rate > self._rate_limit:
            self.verdict = StopLossVerdict.STOP_REFUSAL_RATE
        return self._verdict_or_hold()

    def _verdict_or_hold(self) -> StopLossVerdict:
        return self.verdict if self.verdict is not None else StopLossVerdict.HOLD

    def case_refusal_rate(self, case_id: str) -> float:
        return self._tallies.get(case_id, _CaseTally()).refusal_rate


class BoundedRun:
    """One bounded run over one provider, under the answered authorisation.

    The harness wires the adapter itself — budget, capabilities, ledger,
    capture and timeout are the run's own, not a factory the caller could
    build around. The only per-request input the caller supplies is the
    consent port, one per request, each bound to that request's excerpt
    digest (Q3).
    """

    def __init__(
        self,
        *,
        model: UpstreamModel,
        budget: RunBudget,
        ledger: RunLedger,
        capabilities: ProviderCapabilities | None = None,
        required_capabilities: frozenset[Capability] | None = None,
        usage_capture: UsageCapture | None = None,
        timeout_s: float | None = None,
        runner: Callable[[object], object] | None = None,
        stop_loss: CompoundStopLoss | None = None,
        max_requests: int = REHEARSAL_MAX_REQUESTS,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not _budget_names_a_ceiling(budget):
            raise RunNotAuthorisedError(
                "the run's budget names no ceiling; Q4's authorisation is a number "
                "(20 requests / 50 000 tokens), and a run without the number is not "
                "a bounded run"
            )
        if max_requests <= 0:
            raise RunNotAuthorisedError("max_requests must be positive; zero is not a bound")
        self._model = model
        self._budget = budget
        self._ledger = ledger
        self._capabilities = capabilities
        self._required_capabilities = required_capabilities
        self._usage_capture = usage_capture
        self._timeout_s = timeout_s
        self._runner = runner
        self._stop_loss = stop_loss if stop_loss is not None else CompoundStopLoss()
        self._max_requests = max_requests
        self._clock = clock if clock is not None else (lambda: datetime.now(UTC))
        self._requests: list[RunRequestRecord] = []
        self._exchanges: list[ExchangeRecord] = []
        self._cases_submitted = 0
        self._cases_completed = 0
        self._started_at = self._clock()
        self._finished_at: datetime | None = None

    # --- the run ----------------------------------------------------------

    def submit_case(
        self, case: DeidentifiedCase, *, consents: Sequence[OutboundConsent]
    ) -> RunRecord:
        """Walk one case through the ladder, one request per excerpt.

        The case's prompt is request 0; each excerpt is one further request.
        ``consents`` carries **one port per request** — the caller assembled
        them from per-excerpt digest-bound approvals (Q3): excerpt *i* leaves
        only under the port whose approval binds excerpt *i*'s own digest, and
        a port whose approval is spent, missing, or bound to a different
        digest refuses before the transport. Passing one port for several
        requests is refused here rather than discovered at the second request.

        Every request passes through the provider's own five-gate send; the
        harness's own checks (request ceiling, stop-loss, digest binding) run
        before the provider is built, so a run-level refusal costs nothing —
        including the single-use approval a consent port would otherwise
        spend.

        A refused or failed request stops the *case* immediately: the ladder's
        refusals are terminal for the request, and a case that cannot send its
        first excerpt does not send its second.
        """
        if self._finished_at is not None:
            raise RunNotAuthorisedError("this run has finished; open a new run for a new case")
        self._cases_submitted += 1

        payloads: tuple[str, ...] = (case.safe_prompt, *case.excerpts)
        if len(consents) != len(payloads):
            raise RunNotAuthorisedError(
                f"one consent port per request: the case carries {len(payloads)} "
                f"requests and {len(consents)} ports were handed over"
            )
        # The digest each payload is bound to: None for the prompt (its bound
        # is the approval the caller assembled for the case as a whole), the
        # excerpt's own digest for an excerpt request — Q3's per-excerpt
        # digest binding, carried so the record can prove the pairing.
        bound_digests: tuple[str | None, ...] = (None, *case.excerpt_digests)
        # All case-level bindings are checked BEFORE the first request is
        # built: an excerpt whose port is bound to the wrong digest must not
        # leave a half-sent case behind, where request 0 was already sent.
        for bound, port in zip(bound_digests, consents, strict=True):
            self._check_digest_binding(bound, port)

        for index, (text, bound, port) in enumerate(
            zip(payloads, bound_digests, consents, strict=True)
        ):
            where = "the prompt" if index == 0 else f"excerpt {index - 1}"
            self._before_request()
            self._one_request(case.case_id, where, text, bound, port)

        self._cases_completed += 1
        return self.record()

    def _before_request(self) -> None:
        """The run-level checks. Every one precedes the provider's own gates."""
        if self._stop_loss.verdict is not None:
            raise StopLossTriggeredError(
                f"the compound stop-loss fired ({self._stop_loss.verdict.value}); "
                "the run stops here"
            )
        # The ceiling bounds *issued* requests — ones that reached the wire,
        # sent or failed — matching the ledger's ``labcairn_requests``. A
        # refusal decided before the wire issued nothing and spends nothing.
        issued = sum(1 for r in self._requests if r.outcome != "refused")
        if issued >= self._max_requests:
            raise RunNotAuthorisedError(
                f"the run's request ceiling ({self._max_requests}) is spent; "
                "the request was not built and nothing was sent"
            )

    def _check_digest_binding(self, bound: str | None, port: OutboundConsent) -> None:
        """Q3's per-excerpt binding, checked for the whole case before any wire."""
        if bound is None:
            return  # the prompt's approval is bound to the case, not an excerpt
        if not isinstance(port, DigestBoundConsent):
            raise RunNotAuthorisedError(
                "an excerpt request needs a port that names the digest its "
                "approval binds; this port names none"
            )
        if port.bound_excerpt_digest != bound:
            raise RunNotAuthorisedError(
                "this port's approval is bound to a different excerpt digest; "
                "the excerpt does not leave"
            )

    def _one_request(
        self, case_id: str, where: str, text: str, bound: str | None, port: OutboundConsent
    ) -> None:
        """One request, its stop-loss event, its record line.

        The provider is built with the port this request leaves under — the
        adapter requires the port at construction (ADR-0006), so the binding
        is structural. Its gates run inside ``send``; their refusals arrive as
        :class:`~labcairn.providers.errors.ProviderError` subclasses, sorted
        into refused (before the wire) and failed (issued, went wrong) by
        :data:`PRE_WIRE_KINDS`.
        """
        digest = prompt_digest(text)
        provider = self._provider_for(port)
        try:
            provider.send(ModelRequest(prompt=text, tools=()))
        except ProviderError as error:
            pre_wire = error.kind in PRE_WIRE_KINDS
            self._requests.append(
                RunRequestRecord(
                    request_digest=digest,
                    case_id=case_id,
                    excerpt_digest=bound,
                    outcome="refused" if pre_wire else "failed",
                    kind=error.kind.value,
                )
            )
            if pre_wire:
                verdict = self._stop_loss.record_refusal(case_id)
            else:
                verdict = self._stop_loss.record_failure(case_id)
            raise RunRequestRefusedError(
                case_id=case_id, where=where, kind=error.kind, verdict=verdict.value
            ) from error
        self._stop_loss.record_success(case_id)
        self._requests.append(
            RunRequestRecord(
                request_digest=digest, case_id=case_id, excerpt_digest=bound, outcome="sent"
            )
        )
        # Exchange records accumulate on the adapter instance, and the run
        # builds one adapter per request, so the run collects them itself.
        self._exchanges.extend(provider.exchanges())

    def _provider_for(self, port: OutboundConsent) -> PydanticAiModelProvider:
        """One provider, wired with this request's port and the run's gates."""
        kwargs: dict[str, object] = {
            "model": self._model,
            "consent": port,
            "budget": self._budget,
            "ledger": self._ledger,
            "capabilities": self._capabilities,
            "required_capabilities": self._required_capabilities,
            "clock": lambda: 0.0,
        }
        if self._usage_capture is not None:
            kwargs["usage_capture"] = self._usage_capture
        if self._timeout_s is not None:
            kwargs["timeout_s"] = self._timeout_s
        if self._runner is not None:
            kwargs["runner"] = self._runner
        return PydanticAiModelProvider(**kwargs)  # type: ignore[arg-type]

    # --- the record -------------------------------------------------------

    def record(self) -> RunRecord:
        """The run's record so far. Digests and counts, never text."""
        refusals = sum(1 for r in self._requests if r.outcome == "refused")
        failures = sum(1 for r in self._requests if r.outcome == "failed")
        return RunRecord(
            started_at=self._started_at,
            finished_at=self._finished_at,
            requests_made=len(self._requests) - refusals - failures,
            requests_refused=refusals,
            requests_failed=failures,
            cases_submitted=self._cases_submitted,
            cases_completed=self._cases_completed,
            stop_loss=self._stop_loss.verdict,
            requests=tuple(self._requests),
        )

    def exchanges(self) -> tuple[ExchangeRecord, ...]:
        """Every request's exchange records — the digests-and-counts surface."""
        return tuple(self._exchanges)

    def finish(self) -> RunRecord:
        """Close the run. The record freezes; further cases are refused."""
        self._finished_at = self._clock()
        return self.record()


def _budget_names_a_ceiling(budget: RunBudget) -> bool:
    """Whether the budget names at least one ceiling. The fail-closed preflight.

    A budget with every ceiling ``None`` is the adapter's *unbounded* default,
    and that default is correct for the adapter — the guard there evaluates
    only what is set. A **bounded run** is a different claim: the owner's
    answer (Q4) is a number, and the harness refuses to open a run that does
    not carry one. This is the rehearsal's "no number → no call" rung.
    """
    return (
        budget.max_model_requests is not None
        or budget.max_total_tokens is not None
        or budget.max_cost_usd is not None
        or budget.max_wall_clock_s is not None
        or budget.max_tool_calls is not None
    )


__all__ = [
    "CONSECUTIVE_FAILURE_LIMIT",
    "PRE_WIRE_KINDS",
    "PROPOSAL_REFUSAL_RATE_LIMIT",
    "REHEARSAL_MAX_REQUESTS",
    "REHEARSAL_MAX_TOTAL_TOKENS",
    "BoundedRun",
    "CompoundStopLoss",
    "DigestBoundConsent",
    "RunNotAuthorisedError",
    "RunRecord",
    "RunRequestRecord",
    "RunRequestRefusedError",
    "StopLossTriggeredError",
    "StopLossVerdict",
]
