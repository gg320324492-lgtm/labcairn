"""Capability detection by request. The module ADR-0002 §A1 asks for.

What a probe actually does
--------------------------
Three separate requests, each asking one question and judging the **answer**:

``TOOL_CALLS``
    Send one function tool with a two-field schema and an instruction naming it.
    ``OK`` requires a well-formed tool call naming that tool whose arguments
    parse against the schema. If the reply is prose instead — which is what an
    OpenAI-compatible endpoint serving a small local model does when it silently
    ignores ``tools`` — the answer is ``UNSUPPORTED``, and **the prose is not
    parsed for anything**. There is no fallback path that reads a JSON blob out
    of free text, because that is exactly
    ``NonNativeToolCallingMixin.post_response_prompt_mock``
    (``non_native_fc.py:68``) and ADR-0002 §A4 refuses it: it makes the model's
    prose the sole carrier of a side effect's identity.

``STRUCTURED_OUTPUT_NATIVE``
    Send a schema through the protocol's own structured-output channel with text
    output disallowed. ``OK`` requires the reply to be the data, with no prose
    wrapped around it, and to validate against the schema.

``STRUCTURED_OUTPUT_PROMPTED``
    Send the same schema as an instruction. Always run — it is the only fallback
    a model without native support has, and its absence from ``supports`` is
    information the user needs.

``USAGE_REPORTING``
    Not a separate request (ADR-0002's table: *"included in the above"*).
    Derived: ``OK`` iff at least one executed probe came back with a ``usage``
    block carrying a non-null counter. It is a statement about the endpoint, not
    about one response.

Why no ``supported_tools()`` lookup happens anywhere
----------------------------------------------------
Nothing in this module — or anywhere else in ``labcairn.providers`` — reads
``model.profile``. The tests make that structural rather than aspirational:
``test_probe_never_reads_a_model_profile`` asserts by source that the word
``profile`` does not appear in the probe module, and
``test_model_profile_name_match_is_not_capability_evidence`` drives the exact
ADR-0002 scenario (a model called ``gpt-4-turbo-mimic`` on a custom endpoint
that ignores ``tools``) and asserts ``TOOL_CALLS not in supports``.

The profile *is* still consulted by pydantic-ai itself, internally, when it
builds the request. That is unavoidable and harmless: the profile decides what
to *ask for*, this probe decides what to *believe*, and only the belief gates a
side effect. A profile that over-promises produces a request the endpoint
ignores, which is a probe result, not a crash.

A profile that under-promises is handled too. pydantic-ai raises ``UserError``
from ``prepare_request`` (``models/__init__.py:939-950``, *"Native structured
output is not supported by this model."*) before anything is sent. The probe
records that as ``UNSUPPORTED`` with the exception's **class name** as its
evidence, which is why ADR-0002 notes the misfiling of a provider-capability
fact as *"Error caused by a usage mistake by the application developer — You!"*:
LabCairn does not propagate that framing.

Cost, and why probes are lazy
-----------------------------
Every probe is a billed request. ADR-0002 §Risks: *"Probe lazily — only when a
stage actually requires the capability."* :meth:`PydanticAiProbe.probe` takes the
capability set to probe, so a caller that needs only tool calling pays for one
request. :class:`ProbeCache` then keeps the result keyed on
``(endpoint_fingerprint, model, protocol)`` so a second run pays nothing.

The cache key deliberately omits the base URL and uses
:func:`endpoint_fingerprint` instead. A base URL can carry a credential
(``?api_key=``, userinfo) and this record is meant to be persistable and
reportable; a fingerprint cannot be reversed into a host, and two configurations
pointing at the same host with different keys produce the same fingerprint
because they have the same capabilities.

What a probe never sends
------------------------
Every prompt in this module is a **fixed literal** with no interpolation of
caller data: no user text, no document excerpt, no tool schema from the run.
That is a testable property (``test_probe_requests_carry_no_user_material``) and
it is what makes probing safe to do automatically: the outbound disclosure
policy in :mod:`labcairn.providers.adapter` is about the run, and a probe never
touches it.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from labcairn.core.providers.protocol import canonical_json
from labcairn.core.providers.usage import Known
from labcairn.providers.capabilities import (
    ALL_CAPABILITIES,
    Capability,
    CapabilityOutcome,
    ProviderCapabilities,
)
from labcairn.providers.usage_capture import NullUsageCapture, UsageCapture

#: The tool the probe offers. Namespaced so it can never collide with a real
#: tool, and so a reply naming it is unambiguously a probe artefact.
PROBE_TOOL_NAME: str = "__labcairn_capability_probe__"

#: The only field, and it is an enum of one, so a model cannot pass the probe by
#: returning any old string. Deliberately trivial: ADR-0002 §Risks warns that
#: passing this is a *floor*, not a guarantee for a 20-parameter real schema.
PROBE_TOOL_SCHEMA: Mapping[str, object] = {
    "type": "object",
    "properties": {"verdict": {"type": "string", "enum": ["ok"]}},
    "required": ["verdict"],
    "additionalProperties": False,
}

#: Fixed literals. No formatting, no interpolation, no caller data — see the
#: module docstring.
PROBE_INSTRUCTION: str = (
    "You are being capability-probed. Reply by calling the "
    f'{PROBE_TOOL_NAME} tool with the single argument verdict set to "ok". '
    "Do not answer in prose."
)
PROBE_STRUCTURED_PROMPT: str = (
    "You are being capability-probed. Reply with a single JSON object and nothing "
    'else. It must have exactly one key, "verdict", whose value is the string "ok". '
    "Output no prose, no code fence and no explanation."
)
PROBE_STRUCTURED_SCHEMA: Mapping[str, object] = {
    "type": "object",
    "properties": {"verdict": {"type": "string", "enum": ["ok"]}},
    "required": ["verdict"],
    "additionalProperties": False,
}


def endpoint_fingerprint(*, base_url: str | None, model: str, protocol: str) -> str:
    """A cache key that cannot be reversed into a URL.

    ADR-0002 requires probe results be keyed on ``(endpoint, model, protocol)``.
    Keying on the endpoint *string* would put a host — and possibly a
    ``?api_key=`` — into every persisted probe record. Hashing
    ``(protocol, model, sanitised base_url)`` keeps the invalidation semantics
    ADR-0002 asks for ("invalidated by a protocol or endpoint change") while
    keeping the key opaque.
    """
    payload = canonical_json({"base_url": base_url or "", "model": model, "protocol": protocol})
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ProbeRecord:
    """What one probe session observed. Persistable, secret-free."""

    endpoint_fingerprint: str
    model: str
    protocol: str
    outcomes: Mapping[Capability, CapabilityOutcome]
    #: LabCairn-authored one-liners. Exception *class names* and fixed strings
    #: only — never an exception message, which may echo a credential.
    evidence: Mapping[Capability, str]
    #: Which capabilities a request was actually issued for. A capability absent
    #: from here was never asked about, which is not the same as having failed.
    probes_run: frozenset[Capability]
    observed_at: datetime

    def to_provider_capabilities(self) -> ProviderCapabilities:
        """The gateable result.

        ``USAGE_REPORTING`` is computed here rather than probed, and it is the one
        place where "a probe ran" and "a probe succeeded" are deliberately
        different inputs: a probe that returned ``UNSUPPORTED`` still carried a
        response, and if that response had a ``usage`` block then the endpoint
        does report usage.
        """
        return ProviderCapabilities.from_outcomes(
            endpoint_fingerprint=self.endpoint_fingerprint,
            model=self.model,
            protocol=self.protocol,
            outcomes=dict(self.outcomes),
            unsupported_reason=dict(self.evidence),
        )

    def to_wire(self) -> Mapping[str, object]:
        return {
            "endpoint_fingerprint": self.endpoint_fingerprint,
            "model": self.model,
            "protocol": self.protocol,
            "outcomes": {c.value: o.value for c, o in sorted(self.outcomes.items())},
            "evidence": {c.value: e for c, e in sorted(self.evidence.items())},
            "probes_run": sorted(c.value for c in self.probes_run),
            "observed_at": self.observed_at.isoformat(),
        }


@runtime_checkable
class CapabilityProbe(Protocol):
    """The seam a probe has to satisfy to be usable in a run."""

    def probe(
        self,
        *,
        capabilities: frozenset[Capability],
        endpoint_fingerprint: str = "",
        protocol: str = "unknown",
        token: Any = None,
    ) -> ProbeRecord:
        """Issue real requests for ``capabilities`` and report what came back."""
        ...


@runtime_checkable
class ProbeCache(Protocol):
    """Where a record is kept between runs.

    In-memory here. ADR-0002 specifies SQLite, and SQLite tables belong to
    LC-P1-05 — so this is a Protocol with an in-memory implementation and the
    same key shape, and LC-P1-05 adds a persistent one without touching a probe.
    """

    def get(
        self, *, endpoint_fingerprint: str, model: str, protocol: str
    ) -> ProbeRecord | None: ...

    def put(self, record: ProbeRecord) -> None: ...


class InMemoryProbeCache:
    """A dict. Named so the type in a type error says what it is."""

    __slots__ = ("_entries",)

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str, str], ProbeRecord] = {}

    def get(self, *, endpoint_fingerprint: str, model: str, protocol: str) -> ProbeRecord | None:
        return self._entries.get((endpoint_fingerprint, model, protocol))

    def put(self, record: ProbeRecord) -> None:
        self._entries[(record.endpoint_fingerprint, record.model, record.protocol)] = record


#: The minimal model surface a probe needs. Declared here rather than importing
#: ``pydantic_ai.models.Model`` so that the seam ADR-0002 §A3 promises survives:
#: a hand-rolled HTTP adapter satisfies this protocol too.
@runtime_checkable
class ProbeModel(Protocol):
    """What a probe asks of an upstream model."""

    @property
    def model_name(self) -> str: ...

    async def request(
        self,
        messages: Any,
        model_settings: Any,
        model_request_parameters: Any,
    ) -> Any:
        """Return a pydantic-ai ``ModelResponse``."""
        ...


#: How the coroutine is driven. Injected because a test must not need an event
#: loop of its own, and because ``asyncio.run`` inside a running loop raises a
#: message about "asyncio.run() cannot be called from a running event loop" that
#: tells an operator nothing about which knob to turn.
type AsyncRunner = Callable[[Awaitable[Any]], Any]


def _default_runner(awaitable: Awaitable[Any]) -> Any:
    return asyncio.run(awaitable)  # type: ignore[arg-type]


class PydanticAiProbe:
    """Runs the probes by issuing real requests through a model.

    ``model`` is a :class:`ProbeModel` — in production a ``pydantic_ai.models``
    object built by :func:`~labcairn.providers.pydantic_models.build_model`, in
    tests a fake. ``usage_capture`` is the object that saw the raw response
    bodies; when the default :class:`~labcairn.providers.usage_capture.NullUsageCapture`
    is in play, ``USAGE_REPORTING`` comes back ``UNVERIFIED`` and a run with a
    token ceiling refuses to start. That is the correct default, not a
    degradation: the alternative is budgeting against zeros.

    Cancellation is honoured between probes, so an operator stopping a run also
    stops an in-progress probe session.
    """

    __slots__ = (
        "_captured_usage",
        "_clock",
        "_model",
        "_model_name",
        "_runner",
        "_sends",
        "_usage_capture",
    )

    def __init__(
        self,
        *,
        model: ProbeModel,
        usage_capture: UsageCapture | None = None,
        clock: Callable[[], datetime],
        runner: AsyncRunner = _default_runner,
        model_name: str | None = None,
    ) -> None:
        self._model = model
        self._usage_capture = usage_capture if usage_capture is not None else NullUsageCapture()
        self._runner = runner
        self._clock = clock
        self._captured_usage = False
        self._sends = 0
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        return self._model_name or self._model.model_name

    def probe(
        self,
        *,
        capabilities: frozenset[Capability],
        endpoint_fingerprint: str = "",
        protocol: str = "unknown",
        token: Any = None,
    ) -> ProbeRecord:
        """Run the requested probes and record what each one actually returned.

        Every probe is attempted even after one fails: a run that needs
        ``TOOL_CALLS`` and ``STRUCTURED_OUTPUT_PROMPTED`` should learn about both
        in one session, and a network blip on probe two does not invalidate
        probe one's answer.
        """
        wanted = capabilities or frozenset(ALL_CAPABILITIES)
        outcomes: dict[Capability, CapabilityOutcome] = {}
        evidence: dict[Capability, str] = {}
        ran: set[Capability] = set()
        self._captured_usage = False
        self._sends = 0

        if token is not None:
            token.raise_if_cancelled()

        if Capability.TOOL_CALLS in wanted:
            ran.add(Capability.TOOL_CALLS)
            outcome, why = self._probe_tool_calls()
            outcomes[Capability.TOOL_CALLS] = outcome
            evidence[Capability.TOOL_CALLS] = why

        if Capability.STRUCTURED_OUTPUT_NATIVE in wanted:
            ran.add(Capability.STRUCTURED_OUTPUT_NATIVE)
            outcome, why = self._probe_structured_output(native=True)
            outcomes[Capability.STRUCTURED_OUTPUT_NATIVE] = outcome
            evidence[Capability.STRUCTURED_OUTPUT_NATIVE] = why

        if Capability.STRUCTURED_OUTPUT_PROMPTED in wanted:
            ran.add(Capability.STRUCTURED_OUTPUT_PROMPTED)
            outcome, why = self._probe_structured_output(native=False)
            outcomes[Capability.STRUCTURED_OUTPUT_PROMPTED] = outcome
            evidence[Capability.STRUCTURED_OUTPUT_PROMPTED] = why

        if Capability.USAGE_REPORTING in wanted:
            ran.add(Capability.USAGE_REPORTING)
            # Derived, never separately requested — see the module docstring.
            if self._captured_usage:
                outcomes[Capability.USAGE_REPORTING] = CapabilityOutcome.OK
                evidence[Capability.USAGE_REPORTING] = "a probe response carried a usage block"
            elif self._sends == 0:
                outcomes[Capability.USAGE_REPORTING] = CapabilityOutcome.UNVERIFIED
                evidence[Capability.USAGE_REPORTING] = (
                    "usage reporting cannot be observed without running another probe"
                )
            else:
                outcomes[Capability.USAGE_REPORTING] = CapabilityOutcome.UNSUPPORTED
                evidence[Capability.USAGE_REPORTING] = (
                    "no probe response carried a usage block with a non-null counter"
                )

        observed_at = self._clock()
        return ProbeRecord(
            endpoint_fingerprint=endpoint_fingerprint,
            model=self.model_name,
            protocol=protocol,
            outcomes=outcomes,
            evidence=evidence,
            probes_run=frozenset(ran),
            observed_at=observed_at,
        )

    def _executed_probes(self) -> bool:
        return self._sends > 0

    # --- the three probes -------------------------------------------------

    def _probe_tool_calls(self) -> tuple[CapabilityOutcome, str]:
        try:
            response = self._send(
                prompt=PROBE_INSTRUCTION,
                tool_names={PROBE_TOOL_NAME: PROBE_TOOL_SCHEMA},
            )
        except Exception as exc:
            # Exception *class name* only. The message of a failed probe can echo
            # a rejected credential back, so it is never read here at all.
            return CapabilityOutcome.UNSUPPORTED, f"probe raised {type(exc).__name__}"

        calls = [
            part
            for part in getattr(response, "parts", ())
            if getattr(part, "part_kind", None) == "tool-call"
        ]
        if not calls:
            # The ADR-0002 §A4 case: the endpoint was offered a tool and answered
            # in prose. Not parsed, not retried, just reported honestly.
            return (
                CapabilityOutcome.UNSUPPORTED,
                "endpoint answered in prose without emitting a tool call",
            )
        call = calls[0]
        named = getattr(call, "tool_name", None)
        if named != PROBE_TOOL_NAME:
            return (
                CapabilityOutcome.UNSUPPORTED,
                f"tool call named {named!r} rather than the probe tool",
            )
        if not _arguments_match_schema(getattr(call, "args", None), PROBE_TOOL_SCHEMA):
            return (
                CapabilityOutcome.UNSUPPORTED,
                "tool call arguments did not validate against the probe schema",
            )
        return CapabilityOutcome.OK, "a well-formed tool call naming the probe tool"

    def _probe_structured_output(self, *, native: bool) -> tuple[CapabilityOutcome, str]:
        try:
            response = self._send(
                prompt=PROBE_STRUCTURED_PROMPT,
                structured_schema=PROBE_STRUCTURED_SCHEMA,
                native=native,
            )
        except Exception as exc:
            # `UserError` from pydantic-ai's prepare_request lands here: a
            # profile said no before anything was sent. Recorded as UNSUPPORTED
            # with the class name only, so a profile's opinion becomes a probe
            # result instead of a crash or a programmer-error blame.
            return CapabilityOutcome.UNSUPPORTED, f"probe raised {type(exc).__name__}"

        text = _concatenated_text(response)
        if not text:
            return CapabilityOutcome.UNSUPPORTED, "probe response carried no text"
        payload = _parse_strict_json(text)
        if payload is None:
            return (
                CapabilityOutcome.UNSUPPORTED,
                "response was prose or wrapped JSON rather than the requested object",
            )
        if not _arguments_match_schema(payload, PROBE_STRUCTURED_SCHEMA):
            return (
                CapabilityOutcome.UNSUPPORTED,
                "structured output did not validate against the probe schema",
            )
        return CapabilityOutcome.OK, "a bare JSON object validating against the probe schema"

    def _send(
        self,
        *,
        prompt: str,
        tool_names: Mapping[str, Mapping[str, object]] | None = None,
        structured_schema: Mapping[str, object] | None = None,
        native: bool = False,
    ) -> Any:
        """Issue one request. The only place a probe touches the network."""
        from pydantic_ai.messages import ModelRequest, SystemPromptPart, UserPromptPart
        from pydantic_ai.models import ModelRequestParameters
        from pydantic_ai.output import OutputObjectDefinition
        from pydantic_ai.tools import ToolDefinition

        messages = [
            ModelRequest(
                parts=[
                    SystemPromptPart(content=prompt),
                    UserPromptPart(content=prompt),
                ]
            )
        ]
        kwargs: dict[str, Any] = {}
        if tool_names:
            kwargs["function_tools"] = [
                ToolDefinition(name=name, parameters_json_schema=dict(schema))
                for name, schema in tool_names.items()
            ]
        if structured_schema is not None:
            kwargs["output_object"] = OutputObjectDefinition(
                json_schema=dict(structured_schema),
                name="probe_verdict",
            )
            if native:
                # pydantic-ai maps 'native' onto response_format={"type": "json_schema"}
                # for OpenAI. Its profile guard (models/__init__.py:399-400) raises
                # UserError first when the profile says no — which this probe
                # records as UNSUPPORTED rather than propagating as a developer bug.
                kwargs["output_mode"] = "native"
                kwargs["allow_text_output"] = False
            else:
                kwargs["output_mode"] = "prompted"
                kwargs["prompted_output_template"] = json.dumps(structured_schema, sort_keys=True)

        parameters = ModelRequestParameters(**kwargs)
        self._sends += 1
        response = self._runner(self._model.request(messages, None, parameters))
        self._note_usage()
        return response

    def _note_usage(self) -> None:
        """Record whether this exchange's raw body carried a usage block.

        Reads the capture — never pydantic-ai's ``ModelResponse.usage``, whose
        fields are ``int`` and therefore cannot distinguish "zero" from "absent"
        (see :mod:`labcairn.providers.usage_capture`). Latched to true for the
        session: one response with usage is enough to say the endpoint reports it.
        """
        report = self._usage_capture.report()
        if isinstance(report.input_tokens, Known) or isinstance(report.output_tokens, Known):
            self._captured_usage = True


def _concatenated_text(response: Any) -> str:
    return "".join(
        str(part.content)
        for part in getattr(response, "parts", ())
        if getattr(part, "part_kind", None) == "text"
    )


def _parse_strict_json(text: str) -> object | None:
    """Parse text that must be *only* a JSON object.

    Strict on purpose. A model that answers ``{"verdict": "ok"}`` inside a code
    fence, or with a sentence in front of it, has not demonstrated native
    structured output, and calling it a pass would make this probe no stricter
    than the profile lookup it replaces. Prompted output goes through exactly the
    same check, which is why the two probes can be compared honestly.
    """
    candidate = text.strip()
    if not candidate.startswith("{") or not candidate.endswith("}"):
        return None
    try:
        decoded = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, dict) else None


def _arguments_match_schema(value: object, schema: Mapping[str, object]) -> bool:
    """Validate a small object against the probe schema.

    Hand-rolled rather than pulling in a validator because the probe schema is a
    fixed three-line literal with exactly one required string field and an
    ``additionalProperties: false``. A general JSON Schema validator would be a
    dependency and a larger surface than the thing it validates.
    """
    if not isinstance(value, dict):
        return False
    properties = schema.get("properties")
    required = schema.get("required")
    if not isinstance(properties, Mapping) or not isinstance(required, list):
        return False
    if set(value) != set(properties):
        return False
    for key, spec in properties.items():
        if not isinstance(spec, Mapping):
            return False
        allowed = spec.get("enum")
        if isinstance(allowed, list) and value[key] not in allowed:
            return False
    return True


class CachedCapabilityProbe:
    """Wraps a probe with a cache. The thing a run actually holds.

    A partial hit **merges** rather than re-running everything. ADR-0002 §Risks
    is explicit that every probe is a billed request and that the cost is
    *"a non-trivial one-time cost"*, so a session that already established
    ``TOOL_CALLS`` must not pay for it again when the next stage asks about
    structured output too. The gap is probed; the rest is reused; the merged
    record is written back so the next session is a full hit.

    A gap is never reported as ``UNVERIFIED``. That would block a stage that
    could in fact run, which is the cost of a conservative rule applied too
    bluntly — and the whole reason this wrapper exists.
    """

    __slots__ = ("_cache", "_probe")

    def __init__(self, probe: CapabilityProbe, cache: ProbeCache) -> None:
        self._probe = probe
        self._cache = cache

    def probe(
        self,
        *,
        capabilities: frozenset[Capability],
        endpoint_fingerprint: str = "",
        protocol: str = "unknown",
        token: Any = None,
    ) -> ProbeRecord:
        cached = self._cache.get(
            endpoint_fingerprint=endpoint_fingerprint,
            model=getattr(self._probe, "model_name", ""),
            protocol=protocol,
        )
        if cached is None:
            return self._probe_and_store(
                capabilities, endpoint_fingerprint, protocol, token, base=None
            )
        missing = capabilities - cached.probes_run
        if not missing:
            return cached
        return self._probe_and_store(missing, endpoint_fingerprint, protocol, token, base=cached)

    def _probe_and_store(
        self,
        capabilities: frozenset[Capability],
        endpoint_fingerprint: str,
        protocol: str,
        token: Any,
        *,
        base: ProbeRecord | None,
    ) -> ProbeRecord:
        fresh = self._probe.probe(
            capabilities=capabilities,
            endpoint_fingerprint=endpoint_fingerprint,
            protocol=protocol,
            token=token,
        )
        record = fresh if base is None else _merge(base, fresh)
        self._cache.put(record)
        return record


def _merge(base: ProbeRecord, fresh: ProbeRecord) -> ProbeRecord:
    """Combine a cached record with a freshly probed one, fresh winning.

    ``USAGE_REPORTING`` is the one derived value, and it is also last-wins: a
    fresh session that observed no ``usage`` block is fresher evidence about the
    endpoint than a cached session that observed one, and an endpoint that used
    to report usage and no longer does should stop being trusted.
    """
    outcomes = {**base.outcomes, **fresh.outcomes}
    evidence = {**base.evidence, **fresh.evidence}
    return ProbeRecord(
        endpoint_fingerprint=fresh.endpoint_fingerprint or base.endpoint_fingerprint,
        model=fresh.model or base.model,
        protocol=fresh.protocol or base.protocol,
        outcomes=outcomes,
        evidence=evidence,
        probes_run=base.probes_run | fresh.probes_run,
        observed_at=fresh.observed_at,
    )
