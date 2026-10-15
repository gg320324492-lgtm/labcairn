"""The provider adapter: one request in, one honest response out, through a gate.

Order of operations, and why it is this order
---------------------------------------------
:meth:`PydanticAiModelProvider.send` runs four checks before a request exists,
in this sequence:

1. **Cancellation** — cheapest, and an operator pressing stop should not wait on
   a capability lookup.
2. **Capability gate** — ADR-0002 §5: ``CAPABILITY_UNAVAILABLE`` is *"decided
   before the request"*, never after a ``UserError`` from inside
   ``prepare_request`` (``models/__init__.py:399-400``). A blocked stage makes
   zero HTTP calls, which is what
   ``test_capability_failure_decided_before_request_not_after`` asserts.
3. **Budget pre-flight** — ADR-0002 §OpenHands obs 13 and pydantic-ai's
   ``check_before_request`` (``usage.py:568``) agree: a ceiling checked only
   afterwards bounds nothing, because the overshoot is already paid.
4. **The call itself**, bounded by a timeout.

Then usage is folded into the ledger, an exchange record is appended, and the
budget is checked **again** — so a single response that overshoots stops the run
there rather than at the start of the next stage.

Where usage comes from
----------------------
From :class:`~labcairn.providers.usage_capture.UsageCapture` — the raw
``usage`` block — and **never** from ``pydantic_ai.messages.ModelResponse.usage``,
whose fields are ``int`` and cannot represent "the provider did not say"
(``test_usage_limits.py:1166``, ``test_usage_unknown_provider``). The full
argument is in :mod:`labcairn.providers.usage_capture`; the short version is
that the framework has already destroyed the distinction by the time LabCairn
sees the object, and ADR-0005's consequence 1 says it cannot be recovered
afterwards.

Reconstruction is lossless in both directions: a ``Known`` token becomes a bare
integer in the wire mapping and an ``Unknown`` token has its key **omitted**, so
:meth:`~labcairn.core.providers.protocol.UsageReport.from_wire` maps it back to
``Unknown(PROVIDER_OMITTED)`` — exactly where it came from. No second
representation, so no second code path to keep honest.

Outbound material disclosure
----------------------------
The work order asks for a *"clear outbound-material disclosure policy"*. What
LabCairn can honestly promise is narrower than "nothing but the prompt leaves",
so here is the whole of it:

:class:`OutboundDisclosure` / :data:`PHASE_1_OUTBOUND_POLICY`
    Per call, the record of what this layer declares it put on the wire: the
    prompt, the tool names (and, unavoidably, their schemas), and whether
    excerpts were included.

What it is **not**, stated plainly: this layer cannot tell a document excerpt from
ordinary user text. A prompt containing a retrieved passage is indistinguishable,
here, from one that does not, and no regex settles that. The real control is
upstream — LC-P1-09's retrieval layer must not place excerpts in a prompt without
recording a user-visible disclosure — and that is its work order, not this one.
What this layer contributes is making the omission *explicit and asserted*
(``test_phase_1_outbound_policy_forbids_excerpts``) rather than an unstated
convention, and making each exchange record its disclosure so a report can
render it.

Provenance without content
---------------------------
:attr:`ExchangeRecord` holds digests and counts, never text:
:attr:`prompt_digest` and :attr:`tool_names`. Enough to answer "was this the same
prompt as the one that produced the bad result?", not enough to reconstruct a
document from a log. The whole record is safe to export without a disclosure
review, because there is nothing in it to disclose — which is the property the
record exists to have.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections.abc import Callable, Coroutine, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from labcairn.core.providers.protocol import (
    MalformedResponseError,
    ModelRequest,
    ModelResponse,
    UsageReport,
)
from labcairn.core.providers.usage import Known, UsageValue
from labcairn.providers.budget import BudgetGuard, RunBudget
from labcairn.providers.cancel import CancellationToken
from labcairn.providers.capabilities import Capability, ProviderCapabilities
from labcairn.providers.errors import (
    FailureKind,
    ProviderError,
    ProviderFailure,
    ProviderMalformedResponseError,
    ProviderTimeoutError,
    UnsupportedCapabilityError,
    classify_exception,
)
from labcairn.providers.ledger import LedgerSnapshot, RunLedger
from labcairn.providers.redaction import Redactor
from labcairn.providers.usage_capture import NullUsageCapture, UsageCapture

#: Product code logs; it never prints (ruff T20).
logger = logging.getLogger(__name__)

#: Used when an upstream response carries no timestamp of its own. A fixed epoch
#: rather than the wall clock: this module is on the path of a determinism test.
_EPOCH = datetime.fromtimestamp(0, tz=UTC)


@dataclass(frozen=True, slots=True)
class OutboundDisclosure:
    """What this layer declares it is sending, per call.

    A value rather than a comment, so a report can render it and a test can
    assert it. The two fields that are ``False`` are the ones a future work order
    has to change consciously.
    """

    #: The system instruction and the user prompt the caller supplied.
    sends_prompt: bool = True
    #: Tool **names** only as a category — the JSON schemas travel with them, so
    #: a tool description is disclosed material too and is not separable here.
    sends_tool_names: bool = False
    #: Tool arguments from earlier turns. Phase 1 permits these, because refusing
    #: them would make any multi-turn run useless — but it means a caller that
    #: puts a file's *contents* into an argument has sent those contents.
    sends_tool_arguments: bool = True
    #: Retrieved document excerpts. **False in Phase 1**, declared and asserted.
    #: The control that makes it true lives in the retrieval layer; see the module
    #: docstring for why this is a declaration and not a guarantee.
    sends_document_excerpts: bool = False
    #: Capability-probe prompts. Fixed literals with no caller data.
    sends_probe_prompts: bool = True

    def reveal_for(self, request: ModelRequest) -> OutboundDisclosure:
        """Narrow to what this particular call carried.

        Per-call rather than per-provider so that "nothing left the machine beyond
        the prompt" is a checkable statement about one exchange, rather than an
        assumption about the whole session.
        """
        return replace(self, sends_tool_names=bool(request.tools))

    def as_sent(self) -> Mapping[str, object]:
        return {
            "prompt": self.sends_prompt,
            "tool_names": self.sends_tool_names,
            "tool_arguments": self.sends_tool_arguments,
            "document_excerpts": self.sends_document_excerpts,
            "probe_prompts": self.sends_probe_prompts,
        }


#: What Phase 1 does. Named so a report can cite it and a diff shows when it moves.
PHASE_1_OUTBOUND_POLICY: OutboundDisclosure = OutboundDisclosure()


@dataclass(frozen=True, slots=True)
class ExchangeRecord:
    """What one call looked like, minus what it contained.

    Digests and counts, never text — so the whole record is safe to persist,
    export and attach to a bug report without a disclosure review.
    """

    provider: str
    model: str
    transcript_step: str
    prompt_digest: str
    tool_names: tuple[str, ...]
    outbound: OutboundDisclosure
    provider_attempts: int
    observed_at: datetime
    usage_input: UsageValue
    usage_output: UsageValue

    def to_wire(self) -> Mapping[str, object]:
        return {
            "provider": self.provider,
            "model": self.model,
            "transcript_step": self.transcript_step,
            "prompt_digest": self.prompt_digest,
            "tool_names": list(self.tool_names),
            "outbound": self.outbound.as_sent(),
            "provider_attempts": self.provider_attempts,
            "observed_at": self.observed_at.isoformat(),
            "usage_input": self.usage_input.to_wire(),
            "usage_output": self.usage_output.to_wire(),
        }


def prompt_digest(prompt: str) -> str:
    """SHA-256 of a prompt, domain-separated.

    Lets a report answer "was this the same prompt?" without keeping the prompt.
    Not a secrecy measure: a digest of a short, guessable prompt is guessable. It
    is a *provenance* measure, and it is safe to persist because it is paired with
    the redaction discipline rather than standing in for it.
    """
    return hashlib.sha256(b"labcairn.provider.prompt.v1\x00" + prompt.encode("utf-8")).hexdigest()


@runtime_checkable
class UpstreamModel(Protocol):
    """The model surface this adapter needs.

    A structural subset of ``pydantic_ai.models.Model``, declared here rather than
    imported so that ADR-0002 §A3's *"a hand-rolled adapter can be dropped in
    behind ``ModelProvider`` without changing callers"* is a property of the code
    rather than a hope.
    """

    @property
    def model_name(self) -> str: ...

    async def request(
        self, messages: Any, model_settings: Any, model_request_parameters: Any
    ) -> Any:
        """Return a pydantic-ai ``ModelResponse``."""
        ...


#: Tool name -> JSON schema. The frozen seam (:class:`ModelRequest`) carries names
#: only, so the schemas live here on the adapter.
type ToolSchemas = Mapping[str, Mapping[str, object]]

#: How an awaitable is driven. Injected so a test needs no event loop of its own,
#: and so the "called from inside a running loop" case produces a message about
#: the knob rather than asyncio's.
type AsyncRunner = Callable[[Coroutine[Any, Any, Any]], Any]


def default_runner(awaitable: Coroutine[Any, Any, Any]) -> Any:
    """Drive ``awaitable`` on a fresh event loop.

    ``asyncio.run`` raises its own ``RuntimeError`` when called from inside a
    running loop, which is an accurate message about asyncio and useless to
    someone who only wants to know why their run failed. The check is kept and
    the diagnosis supplied here instead.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)
    # Close it before raising. An un-awaited coroutine is a leaked frame that
    # Python reports as "coroutine ... was never awaited" at an arbitrary later
    # point, which points the reader at the wrong line entirely.
    awaitable.close()
    raise ProviderError(
        ProviderFailure.of(FailureKind.INTERNAL),
        hint=(
            "send() was called from inside a running event loop; use an async caller "
            "or inject runner="
        ),
    )


def translate_response(
    upstream: Any,
    *,
    usage: UsageReport,
    transcript_step: str,
) -> ModelResponse:
    """pydantic-ai ``ModelResponse`` → LabCairn ``ModelResponse``.

    ``usage`` is the capture's report, *not* ``upstream.usage``. The wire mapping
    is rebuilt so LC-P1-01's ``from_wire`` parses it — omitting unknown keys
    entirely rather than inventing a sentinel, so the round trip is exact.
    """
    parts = getattr(upstream, "parts", ())
    text = "".join(
        str(part.content) for part in parts if getattr(part, "part_kind", None) == "text"
    )
    raw_calls: list[dict[str, object]] = []
    for part in parts:
        if getattr(part, "part_kind", None) != "tool-call":
            continue
        args = getattr(part, "args", None)
        raw_calls.append(
            {
                "name": getattr(part, "tool_name", None),
                "arguments": args if isinstance(args, dict) else {},
            }
        )

    raw_usage: dict[str, object] = {}
    if isinstance(usage.input_tokens, Known):
        raw_usage["input_tokens"] = usage.input_tokens.value
    if isinstance(usage.output_tokens, Known):
        raw_usage["output_tokens"] = usage.output_tokens.value

    payload: dict[str, object] = {"text": text, "tool_calls": raw_calls, "usage": raw_usage}
    observed_at = getattr(upstream, "timestamp", None)
    if not isinstance(observed_at, datetime):
        observed_at = _EPOCH
    try:
        return ModelResponse.from_wire(
            payload, transcript_step=transcript_step, observed_at=observed_at
        )
    except MalformedResponseError as exc:
        # The parse failure's own text is derived from the payload, which is the
        # model's output — never recorded. A digest of it is enough to tell two
        # malformed replies apart in a bug report.
        raise ProviderMalformedResponseError(
            detail_digest=hashlib.sha256(exc.args[0].encode("utf-8")).hexdigest()
        ) from None


class PydanticAiModelProvider:
    """A :class:`~labcairn.core.providers.protocol.ModelProvider` with a gate in front.

    **Construction order is the fail-safe.** Built without ``usage_capture``, every
    token count comes back ``Unknown``, so a run with ``max_total_tokens`` refuses
    to start. A caller opts *in* to trustworthy usage by wiring a real capture.
    The reverse mistake — budgeting against zeros — is the one both upstreams make
    by default (ADR-0002 §A1), so it is the one that is not reachable by omission
    here.

    ``required_capabilities=None`` disables the capability gate entirely; that is
    the honest state for a caller that genuinely needs none. Pass an empty
    ``frozenset()`` and the gate is *active* but permits everything, keeping
    "gated on nothing" distinguishable from "not gated".
    """

    __slots__ = (
        "_budget",
        "_capabilities",
        "_exchanges",
        "_label",
        "_ledger",
        "_model",
        "_name",
        "_outbound",
        "_redactor",
        "_required",
        "_runner",
        "_step",
        "_timeout_s",
        "_token",
        "_tool_schemas",
        "_usage_capture",
    )

    def __init__(
        self,
        *,
        model: UpstreamModel,
        usage_capture: UsageCapture | None = None,
        ledger: RunLedger | None = None,
        budget: RunBudget | None = None,
        capabilities: ProviderCapabilities | None = None,
        required_capabilities: frozenset[Capability] | None = None,
        token: CancellationToken | None = None,
        redactor: Redactor | None = None,
        timeout_s: float | None = None,
        tool_schemas: ToolSchemas | None = None,
        provider_label: str = "pydantic-ai",
        outbound: OutboundDisclosure = PHASE_1_OUTBOUND_POLICY,
        clock: Callable[[], float] | None = None,
        runner: AsyncRunner | None = None,
        priced: bool = False,
    ) -> None:
        self._model = model
        self._usage_capture = usage_capture if usage_capture is not None else NullUsageCapture()
        self._redactor = redactor if redactor is not None else Redactor()
        self._token = token if token is not None else CancellationToken()
        self._runner = runner if runner is not None else default_runner
        self._tool_schemas = dict(tool_schemas or {})
        self._name = f"{provider_label}:{model.model_name}"
        self._label = model.model_name
        self._required = required_capabilities
        self._capabilities = capabilities
        self._outbound = outbound
        self._timeout_s = timeout_s
        self._budget = BudgetGuard(
            budget if budget is not None else RunBudget.unbounded(), capabilities=capabilities
        )
        self._ledger = (
            ledger if ledger is not None else _new_ledger(clock, capabilities, priced=priced)
        )
        self._exchanges: list[ExchangeRecord] = []
        self._step = 0

    # --- the seam ---------------------------------------------------------

    @property
    def name(self) -> str:
        return self._name

    @property
    def capabilities(self) -> ProviderCapabilities | None:
        return self._capabilities

    def set_capabilities(self, capabilities: ProviderCapabilities) -> None:
        """Attach a probe result. After this the capability gate is live."""
        self._capabilities = capabilities
        self._budget.set_capabilities(capabilities)
        self._ledger.set_capabilities(capabilities)

    def ledger_snapshot(self) -> LedgerSnapshot:
        return self._ledger.snapshot()

    def exchanges(self) -> tuple[ExchangeRecord, ...]:
        return tuple(self._exchanges)

    def record_transport_attempt(self) -> None:
        """One HTTP attempt LabCairn did not ask for — a transport-level retry.

        Called by the transport, not by :meth:`send`. It raises
        ``provider_attempts`` only; ``labcairn_requests`` stays put. That
        separation is ADR-0002's ``test_provider_retry_does_not_consume_model_request_budget``,
        grounded in pydantic-ai's own admission that ``RunUsage.requests``
        *"isn't counted"* for transport retries (``usage.py:377-387``).
        """
        self._ledger.record_transport_attempt()

    def record_tool_attempt(self) -> None:
        """Count one tool-call **attempt** against ``max_tool_calls``.

        Called by the tool loop, not by :meth:`send`, because a tool call happens
        between two model requests. Counting attempts rather than successes is
        ADR-0002 §"RunBudget" divergence 2: upstream counts successes, so a
        failing-tool loop is bounded by nothing
        (``test_failed_tool_calls_not_counted``, ``test_usage_limits.py:1012``).
        """
        self._ledger.record_tool_attempt()

    def check_budget(self) -> None:
        """Budget check, public so a stage can gate before building a request."""
        self._budget.require(self._ledger.snapshot())

    def send(self, request: ModelRequest) -> ModelResponse:
        """One gated call. See the module docstring for the order of operations."""
        self._token.check()
        self._gate_capabilities()
        # `pending_requests=1`: the call about to be made counts against the
        # ceiling now, so the overshoot is zero requests rather than one.
        self._budget.require(self._ledger.snapshot(), pending_requests=1)
        return self._send_ungated(request)

    # --- the gate ---------------------------------------------------------

    def _gate_capabilities(self) -> None:
        if self._required is None:
            return
        capabilities = self._capabilities
        if capabilities is None:
            # No probe record, so every required capability is UNVERIFIED — which
            # is blocked. `test_capability_unverified_behaves_as_unsupported`
            # reaching a real gate rather than only the enum.
            raise UnsupportedCapabilityError(
                Capability.TOOL_CALLS.value,
                "no capability probe has run for this provider",
            )
        capabilities.require_all(self._required)
        # A ceiling that cannot be checked blocks before the request too.
        self._budget.require_capability_for_ceilings(capabilities)

    # --- the call ---------------------------------------------------------

    def _send_ungated(self, request: ModelRequest) -> ModelResponse:
        self._step += 1
        step = f"call-{self._step:04d}"
        self._ledger.record_request()
        digest = prompt_digest(request.prompt)
        outbound = self._outbound.reveal_for(request)

        logger.info(
            "provider call %s to %s (tools=%s prompt_digest=%s)",
            step,
            self._name,
            ",".join(request.tools) or "-",
            digest,
        )

        try:
            upstream = self._dispatch(request)
        except (ProviderError, asyncio.CancelledError):
            raise
        except Exception as exc:
            failure = classify_exception(exc, redactor=self._redactor)
            # The log line names the *kind* and a digest. It never interpolates the
            # exception, which may echo a rejected credential or a file excerpt.
            logger.warning(
                "provider call %s to %s failed: kind=%s detail_digest=%s",
                step,
                self._name,
                failure.kind.value,
                failure.detail_digest,
            )
            raise ProviderError(failure) from None

        usage = self._usage_capture.report()
        response = translate_response(upstream, usage=usage, transcript_step=step)
        self._ledger.record_usage(
            input_tokens=usage.input_tokens, output_tokens=usage.output_tokens
        )
        self._exchanges.append(
            ExchangeRecord(
                provider=self._name,
                model=self._label,
                transcript_step=step,
                prompt_digest=digest,
                tool_names=request.tools,
                outbound=outbound,
                provider_attempts=self._ledger.snapshot().provider_attempts,
                observed_at=response.observed_at,
                usage_input=usage.input_tokens,
                usage_output=usage.output_tokens,
            )
        )
        self._budget.require(self._ledger.snapshot())
        return response

    def _dispatch(self, request: ModelRequest) -> Any:
        from pydantic_ai.messages import ModelRequest as UpstreamRequest
        from pydantic_ai.messages import UserPromptPart
        from pydantic_ai.models import ModelRequestParameters
        from pydantic_ai.tools import ToolDefinition

        messages = [UpstreamRequest(parts=[UserPromptPart(content=request.prompt)])]
        parameters = ModelRequestParameters(
            function_tools=[
                ToolDefinition(
                    name=name, parameters_json_schema=dict(self._tool_schemas.get(name, {}))
                )
                for name in request.tools
            ]
        )
        awaitable = self._model.request(messages, None, parameters)
        if self._timeout_s is not None:
            awaitable = asyncio.wait_for(awaitable, timeout=self._timeout_s)
        try:
            return self._runner(awaitable)
        except TimeoutError as exc:
            raise ProviderTimeoutError(
                self._timeout_s if self._timeout_s is not None else 0.0
            ) from exc


def _new_ledger(
    clock: Callable[[], float] | None,
    capabilities: ProviderCapabilities | None,
    *,
    priced: bool,
) -> RunLedger:
    """The ledger a run gets when the caller did not supply one.

    ``priced`` defaults to ``False`` in :meth:`PydanticAiModelProvider.__init__`
    because Phase 1 has no price table: every model is unpriced, so every run's
    cost is ``Unknown(UNPRICED)`` and a ``max_cost_usd`` ceiling fails closed from
    the first request. That is the honest Phase-1 state rather than a temporary
    one — ADR-0002 §Risks makes ``max_cost_usd`` fail closed exactly when no
    price is known, and defaulting to ``True`` would silently start "billing"
    runs against nothing.
    """
    return RunLedger(
        clock=clock if clock is not None else time.monotonic,
        capabilities=capabilities,
        priced=priced,
    )
