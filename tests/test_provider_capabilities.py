"""Capability detection: the tests that prove a request was sent.

The three claims these file exists to defend
--------------------------------------------
1. **A probe is a request.** Every outcome asserted here comes from a
   :class:`~tests.provider_fakes.FakeEndpoint` that recorded the call. No test
   passes by consulting a profile, because the code under test has no way to.
2. **A name is not evidence.** ADR-0002 §A1 measured that pydantic-ai resolves
   capabilities by *model name*, with ``'supports_tools': True`` as the OpenAI
   family default (``profiles/__init__.py:360``). A custom endpoint serving
   ``gpt-4-turbo-mimic`` therefore inherits a promise it never made.
   ``test_model_profile_name_match_is_not_capability_evidence`` reproduces that
   exact scenario.
3. **Unprobed is not supported.** ``UNVERIFIED`` and ``UNSUPPORTED`` stay
   distinguishable in a report and identical in enforcement.

Test names track ADR-0002 §Contracts where one exists, so a future reader can
check the implementation against the ADR without a mapping table.
"""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest
from provider_fakes import FakeEndpoint, Reply, sync_runner

from labcairn.providers.capabilities import (
    ALL_CAPABILITIES,
    Capability,
    CapabilityOutcome,
    ProviderCapabilities,
)
from labcairn.providers.errors import UnsupportedCapabilityError
from labcairn.providers.probe import (
    PROBE_INSTRUCTION,
    PROBE_STRUCTURED_PROMPT,
    PROBE_TOOL_NAME,
    CachedCapabilityProbe,
    InMemoryProbeCache,
    ProbeRecord,
    PydanticAiProbe,
    endpoint_fingerprint,
)

_FINGERPRINT = endpoint_fingerprint(
    base_url="https://gateway.internal/v1", model="gpt-4-turbo-mimic", protocol="openai_compatible"
)

_PROBE_REPLY_WITH_TOOL = Reply(
    name="tool-call",
    tool_calls=((PROBE_TOOL_NAME, {"verdict": "ok"}),),
    usage_body={"input_tokens": 31, "output_tokens": 7},
)
#: The ADR-0002 §A4 endpoint: offered a tool, answered in prose that *contains*
#: something that looks like a tool call. The ``looks_like`` field is the trap —
#: if anything in LabCairn parsed prose for tool calls, it would find it.
_PROSE_REPLY = Reply(
    name="prose",
    text='Sure! {"tool": "__labcairn_capability_probe__", "arguments": {"verdict": "ok"}}',
    usage_body={"input_tokens": 12},
)
_NATIVE_JSON_REPLY = Reply(
    name="native-json",
    text='{"verdict": "ok"}',
    usage_body={"input_tokens": 9, "output_tokens": 5},
)
_WRAPPED_JSON_REPLY = Reply(
    name="wrapped",
    text='Here you go:\n```json\n{"verdict": "ok"}\n```',
    usage_body={"input_tokens": 9},
)


def _run(
    endpoint: FakeEndpoint,
    *,
    capabilities: frozenset[Capability] | None = None,
) -> ProbeRecord:
    probe = PydanticAiProbe(
        model=endpoint,
        usage_capture=endpoint.capture,
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        runner=sync_runner,
    )
    return probe.probe(
        capabilities=capabilities if capabilities is not None else frozenset(ALL_CAPABILITIES),
        endpoint_fingerprint=_FINGERPRINT,
        protocol="openai_compatible",
    )


# --- the ADR-0002 §A1 scenario ---------------------------------------------


@pytest.mark.unit
def test_model_profile_name_match_is_not_capability_evidence() -> None:
    """A model named like an OpenAI one, on an endpoint that ignores ``tools``.

    ADR-0002 §A1: an OpenAI-compatible endpoint whose model name matches nothing
    in ``profiles/`` falls into the OpenAI family default and is *told* it
    supports tools. The probe issues the request, gets prose, and records the
    opposite.
    """
    endpoint = FakeEndpoint(model_name="gpt-4-turbo-mimic", replies=(_PROSE_REPLY,))
    record = _run(endpoint, capabilities=frozenset({Capability.TOOL_CALLS}))
    capabilities = record.to_provider_capabilities()

    assert capabilities.outcome_for(Capability.TOOL_CALLS) is CapabilityOutcome.UNSUPPORTED
    assert Capability.TOOL_CALLS not in capabilities.supports
    # And the request really was made — this is the difference from a lookup.
    assert endpoint.call_count == 1
    assert endpoint.calls[0].tool_names == (PROBE_TOOL_NAME,)


@pytest.mark.unit
def test_probe_never_reads_a_model_profile() -> None:
    """Structural: the word cannot appear in the probe module.

    A behavioural test would have to trust that no future edit adds a profile
    read on a code path today's scenarios do not exercise. An AST assertion does
    not: it fails the moment the word appears, whatever route it takes.
    """
    source = Path(__file__).resolve().parents[1] / "src" / "labcairn" / "providers" / "probe.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    identifiers = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)} | {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }
    assert "profile" not in identifiers, (
        "capability detection must come from an issued request, not from "
        "pydantic-ai's ModelProfile (ADR-0002 §A1)"
    )


@pytest.mark.unit
def test_probe_requests_carry_no_user_material() -> None:
    """A probe prompt is a fixed literal, so probing cannot disclose anything.

    This is what makes ADR-0002's "probe lazily" safe to automate: a probe costs
    money but leaks nothing, because nothing of the caller's is in it.
    """
    endpoint = FakeEndpoint(
        replies=(_PROBE_REPLY_WITH_TOOL, _NATIVE_JSON_REPLY, _NATIVE_JSON_REPLY)
    )
    _run(endpoint, capabilities=frozenset(ALL_CAPABILITIES))

    assert endpoint.call_count == 3
    for call in endpoint.calls:
        rendered = call.rendered()
        # Every prompt is one of this module's two fixed literals, verbatim.
        assert call.prompt_text in {PROBE_INSTRUCTION, PROBE_STRUCTURED_PROMPT}
        assert call.system_text in {PROBE_INSTRUCTION, PROBE_STRUCTURED_PROMPT}
        # And nothing from a retrieval step could have reached it.
        assert "excerpt" not in rendered.lower()
        assert "retrieved" not in rendered.lower()


# --- tool calling ----------------------------------------------------------


@pytest.mark.unit
def test_probe_unsupported_tool_calling_fails_closed_without_text_parsing() -> None:
    """Prose that *contains* a tool call is still not a tool call.

    Regression against ``NonNativeToolCallingMixin.post_response_prompt_mock``
    (``non_native_fc.py:68``), which rewrites the request into prose and then
    parses the model's free text back into structured calls. ADR-0002 §A4 refuses
    it because it makes the model's prose the sole carrier of a side effect's
    identity — and ``_PROSE_REPLY`` is built to be exactly that attractive.
    """
    endpoint = FakeEndpoint(replies=(_PROSE_REPLY,))
    record = _run(endpoint, capabilities=frozenset({Capability.TOOL_CALLS}))
    capabilities = record.to_provider_capabilities()

    assert capabilities.outcome_for(Capability.TOOL_CALLS) is CapabilityOutcome.UNSUPPORTED
    # The prose contained a parseable tool call. Nothing parsed it.
    assert PROBE_TOOL_NAME in _PROSE_REPLY.text
    with pytest.raises(UnsupportedCapabilityError) as raised:
        capabilities.require(Capability.TOOL_CALLS)
    assert raised.value.failure.kind.value == "capability_unavailable"


@pytest.mark.unit
def test_probe_passes_only_on_a_well_formed_tool_call() -> None:
    endpoint = FakeEndpoint(replies=(_PROBE_REPLY_WITH_TOOL,))
    record = _run(endpoint, capabilities=frozenset({Capability.TOOL_CALLS}))
    capabilities = record.to_provider_capabilities()

    assert capabilities.outcome_for(Capability.TOOL_CALLS) is CapabilityOutcome.OK
    assert Capability.TOOL_CALLS in capabilities.supports


@pytest.mark.unit
def test_tool_call_with_arguments_that_fail_the_schema_is_unsupported() -> None:
    """A right-named call with the wrong shape is still a failed probe.

    ``additionalProperties: false`` and a single required field, so an endpoint
    that emits ``{}`` or an extra key is caught here rather than in production
    where the schema is twenty parameters wide.
    """
    endpoint = FakeEndpoint(replies=(Reply(name="bad-args", tool_calls=((PROBE_TOOL_NAME, {}),)),))
    record = _run(endpoint, capabilities=frozenset({Capability.TOOL_CALLS}))

    assert record.outcomes[Capability.TOOL_CALLS] is CapabilityOutcome.UNSUPPORTED


@pytest.mark.unit
def test_tool_call_naming_a_different_tool_is_unsupported() -> None:
    """An endpoint that hallucinated a call is not evidence of tool support."""
    endpoint = FakeEndpoint(
        replies=(Reply(name="wrong", tool_calls=(("write_file", {"path": "/etc/x"}),)),)
    )
    record = _run(endpoint, capabilities=frozenset({Capability.TOOL_CALLS}))

    assert record.outcomes[Capability.TOOL_CALLS] is CapabilityOutcome.UNSUPPORTED


# --- structured output: native vs prompted ---------------------------------


@pytest.mark.unit
def test_structured_output_probe_distinguishes_native_from_prompted() -> None:
    """ADR-0002 §Contracts: native-capable and prose-only endpoints differ.

    Driven through the same probe code with the same schema, so a difference in
    the resulting capability set is attributable to the endpoint and nothing
    else.
    """
    native = FakeEndpoint(replies=(_NATIVE_JSON_REPLY,))
    prompted_only = FakeEndpoint(replies=(_WRAPPED_JSON_REPLY,))

    native_record = _run(native, capabilities=frozenset({Capability.STRUCTURED_OUTPUT_NATIVE}))
    prompted_record = _run(
        prompted_only, capabilities=frozenset({Capability.STRUCTURED_OUTPUT_NATIVE})
    )

    assert native_record.outcomes[Capability.STRUCTURED_OUTPUT_NATIVE] is CapabilityOutcome.OK
    assert (
        prompted_record.outcomes[Capability.STRUCTURED_OUTPUT_NATIVE]
        is CapabilityOutcome.UNSUPPORTED
    )
    # The failure was prose-wrapped JSON, not a missing field — said plainly, so
    # an operator knows the endpoint *almost* works.
    assert "prose" in str(prompted_record.evidence[Capability.STRUCTURED_OUTPUT_NATIVE])


@pytest.mark.unit
def test_native_probe_sends_the_schema_through_the_protocol_channel() -> None:
    """The native probe must use the protocol's structured-output channel.

    Asserting this matters because "native" and "prompted" are two different
    requests; a probe that quietly used the prompt for both would report the same
    answer twice and learn nothing.
    """
    endpoint = FakeEndpoint(replies=(_NATIVE_JSON_REPLY,))
    _run(endpoint, capabilities=frozenset({Capability.STRUCTURED_OUTPUT_NATIVE}))

    call = endpoint.calls[0]
    assert call.output_mode == "native"
    assert call.allow_text_output is False
    assert call.output_object_schema is not None
    assert call.output_object_schema["properties"] == {
        "verdict": {"type": "string", "enum": ["ok"]}
    }


@pytest.mark.unit
def test_prompted_probe_is_always_available_as_a_fallback() -> None:
    """ADR-0002's table: ``STRUCTURED_OUTPUT_PROMPTED`` is *"always probed"*.

    It is the only structured-output path a model without native support has, so
    a probe session that omits it leaves the user with nothing to fall back to.
    """
    endpoint = FakeEndpoint(replies=(_NATIVE_JSON_REPLY,))
    record = _run(endpoint, capabilities=frozenset({Capability.STRUCTURED_OUTPUT_PROMPTED}))

    assert record.probes_run == frozenset({Capability.STRUCTURED_OUTPUT_PROMPTED})
    call = endpoint.calls[0]
    assert call.output_mode == "prompted"
    assert call.prompted_output_template is not None
    assert PROBE_STRUCTURED_PROMPT in call.prompt_text


# --- usage reporting -------------------------------------------------------


@pytest.mark.unit
def test_usage_reporting_is_derived_from_a_real_response() -> None:
    endpoint = FakeEndpoint(replies=(_PROBE_REPLY_WITH_TOOL,))
    record = _run(
        endpoint,
        capabilities=frozenset({Capability.TOOL_CALLS, Capability.USAGE_REPORTING}),
    )

    assert record.outcomes[Capability.USAGE_REPORTING] is CapabilityOutcome.OK


@pytest.mark.unit
def test_usage_reporting_is_unsupported_when_no_probe_response_carried_usage() -> None:
    endpoint = FakeEndpoint(
        replies=(Reply(name="no-usage", tool_calls=((PROBE_TOOL_NAME, {"verdict": "ok"}),)),)
    )
    record = _run(
        endpoint,
        capabilities=frozenset({Capability.TOOL_CALLS, Capability.USAGE_REPORTING}),
    )

    assert record.outcomes[Capability.USAGE_REPORTING] is CapabilityOutcome.UNSUPPORTED


@pytest.mark.unit
def test_usage_reporting_is_unverified_when_no_probe_ran() -> None:
    """Asking about usage reporting alone cannot be answered from nothing."""
    endpoint = FakeEndpoint(replies=())
    record = _run(endpoint, capabilities=frozenset({Capability.USAGE_REPORTING}))

    assert record.outcomes[Capability.USAGE_REPORTING] is CapabilityOutcome.UNVERIFIED
    assert endpoint.call_count == 0


# --- failures during probing ----------------------------------------------


@pytest.mark.unit
def test_a_transport_failure_records_the_exception_class_and_never_its_message() -> None:
    """A probe failure's evidence is the class name, not the text.

    The message of a rejected request routinely echoes the credential
    (``"Incorrect API key provided: sk-ant-..."``), and a ``ProbeRecord`` is meant
    to be persistable and reportable.
    """
    secret_echo = RuntimeError("Incorrect API key provided: sk-ant-not-a-real-key-0000")
    endpoint = FakeEndpoint(replies=(), always_raises=secret_echo)
    record = _run(endpoint, capabilities=frozenset({Capability.TOOL_CALLS}))

    evidence = record.evidence[Capability.TOOL_CALLS]
    assert evidence == "probe raised RuntimeError"
    assert "sk-ant" not in evidence
    assert "Incorrect API key" not in str(record.to_wire())


@pytest.mark.unit
def test_one_failed_probe_does_not_invalidate_the_others() -> None:
    """A session learns everything it can, not everything up to the first error."""
    endpoint = FakeEndpoint(replies=(_PROSE_REPLY, _NATIVE_JSON_REPLY))
    record = _run(
        endpoint,
        capabilities=frozenset({Capability.TOOL_CALLS, Capability.STRUCTURED_OUTPUT_NATIVE}),
    )

    assert record.outcomes[Capability.TOOL_CALLS] is CapabilityOutcome.UNSUPPORTED
    assert record.outcomes[Capability.STRUCTURED_OUTPUT_NATIVE] is CapabilityOutcome.OK


# --- the cached probe ------------------------------------------------------


@pytest.mark.unit
def test_probe_cache_returns_the_record_without_a_second_round_of_requests() -> None:
    endpoint = FakeEndpoint(replies=(_PROSE_REPLY,))
    cache = InMemoryProbeCache()
    probe = CachedCapabilityProbe(
        PydanticAiProbe(
            model=endpoint,
            usage_capture=endpoint.capture,
            clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
            runner=sync_runner,
        ),
        cache,
    )
    # Two calls with the same fingerprint and the same capability set.
    for _ in range(2):
        probe.probe(
            capabilities=frozenset({Capability.TOOL_CALLS}),
            endpoint_fingerprint=_FINGERPRINT,
            protocol="openai_compatible",
        )
    assert endpoint.call_count == 1, "a cache hit must not spend another request"


@pytest.mark.unit
def test_a_partial_cache_hit_probes_only_the_gap() -> None:
    """Yesterday's answer about tool calls does not answer today's about JSON.

    The gap is probed and the known answer reused. Reporting ``UNVERIFIED`` for
    the gap would block a stage that could run; re-probing the whole set would
    spend a second billed request on an answer already held, which ADR-0002
    §Risks calls out by name.
    """
    endpoint = FakeEndpoint(replies=(_PROSE_REPLY, _NATIVE_JSON_REPLY))
    probe = CachedCapabilityProbe(
        PydanticAiProbe(
            model=endpoint,
            usage_capture=endpoint.capture,
            clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
            runner=sync_runner,
        ),
        InMemoryProbeCache(),
    )
    probe.probe(
        capabilities=frozenset({Capability.TOOL_CALLS}),
        endpoint_fingerprint=_FINGERPRINT,
        protocol="openai_compatible",
    )
    second = probe.probe(
        capabilities=frozenset({Capability.TOOL_CALLS, Capability.STRUCTURED_OUTPUT_NATIVE}),
        endpoint_fingerprint=_FINGERPRINT,
        protocol="openai_compatible",
    )
    # One request for the gap, not two for the whole set again.
    assert endpoint.call_count == 2
    assert Capability.STRUCTURED_OUTPUT_NATIVE in second.probes_run
    assert Capability.TOOL_CALLS in second.outcomes
    assert second.outcomes[Capability.TOOL_CALLS] is CapabilityOutcome.UNSUPPORTED


# --- the gate --------------------------------------------------------------


@pytest.mark.unit
def test_capability_unverified_behaves_as_unsupported() -> None:
    """Mirrors OpenHands' ``SecurityRisk.UNKNOWN`` being un-orderable.

    ADR-0002 §4: ``UNVERIFIED`` *"deliberately shares UNSUPPORTED handling"*.
    Asserted three ways — the outcome, the raise, and the absence from
    ``supports`` — because a rule that holds in one of them but not the others is
    the failure this exists to catch.
    """
    capabilities = ProviderCapabilities.unverified(
        endpoint_fingerprint=_FINGERPRINT, model="gpt-4-turbo-mimic", protocol="openai_compatible"
    )

    assert capabilities.outcome_for(Capability.TOOL_CALLS) is CapabilityOutcome.UNVERIFIED
    assert Capability.TOOL_CALLS not in capabilities.supports
    with pytest.raises(UnsupportedCapabilityError):
        capabilities.require(Capability.TOOL_CALLS)


@pytest.mark.unit
def test_capability_enforcement_ignores_the_difference_between_unsupported_and_unverified() -> None:
    """The two outcomes are told apart in a report and treated alike in a gate."""
    unsupported = ProviderCapabilities.from_outcomes(
        endpoint_fingerprint=_FINGERPRINT,
        model="m",
        protocol="p",
        outcomes=dict.fromkeys(ALL_CAPABILITIES, CapabilityOutcome.UNSUPPORTED),
        unsupported_reason=dict.fromkeys(ALL_CAPABILITIES, "probe said no"),
    )
    unverified = ProviderCapabilities.unverified(
        endpoint_fingerprint=_FINGERPRINT, model="m", protocol="p"
    )

    for capability in ALL_CAPABILITIES:
        assert unsupported.outcome_for(capability).enforcement_class == (
            unverified.outcome_for(capability).enforcement_class
        )
        assert unsupported.outcome_for(capability).enforcement_class == "blocked"


@pytest.mark.unit
def test_every_blocked_capability_carries_a_reason() -> None:
    """ADR-0002: ``unsupported_reason`` is required for every capability not supported.

    Checked on a capabilities object built with an *empty* reason map, so the
    constructor's fill-in is what is under test rather than a test's diligence.
    """
    capabilities = ProviderCapabilities.from_outcomes(
        endpoint_fingerprint=_FINGERPRINT,
        model="m",
        protocol="p",
        outcomes=dict.fromkeys(ALL_CAPABILITIES, CapabilityOutcome.UNSUPPORTED),
        unsupported_reason={},
    )
    assert set(capabilities.unsupported_reason) == set(ALL_CAPABILITIES)
    assert all(reason.strip() for reason in capabilities.unsupported_reason.values())


@pytest.mark.unit
def test_require_all_reports_the_first_missing_capability_in_declaration_order() -> None:
    """The reason a user is shown must not depend on argument order."""
    capabilities = ProviderCapabilities.from_outcomes(
        endpoint_fingerprint=_FINGERPRINT,
        model="m",
        protocol="p",
        outcomes={Capability.USAGE_REPORTING: CapabilityOutcome.OK},
        unsupported_reason={},
    )
    with pytest.raises(UnsupportedCapabilityError) as raised:
        capabilities.require_all({Capability.STRUCTURED_OUTPUT_PROMPTED, Capability.TOOL_CALLS})
    assert raised.value.capability == Capability.TOOL_CALLS.value


@pytest.mark.unit
def test_endpoint_fingerprint_cannot_be_reversed_into_a_url() -> None:
    """A base URL can carry a credential; the cache key must not.

    ``?api_key=`` on a self-hosted gateway is a common deployment, not a user
    error, and ADR-0002 requires probe results be keyed on the endpoint. The
    fingerprint satisfies the invalidation semantics without putting the host —
    or the key — into every persisted probe record.
    """
    with_secret = endpoint_fingerprint(
        base_url="https://gateway.internal/v1?api_key=sk-not-real-1234567890",
        model="m",
        protocol="openai_compatible",
    )
    without_secret = endpoint_fingerprint(
        base_url="https://gateway.internal/v1", model="m", protocol="openai_compatible"
    )
    assert "sk-not-real" not in with_secret
    assert "gateway.internal" not in without_secret


@pytest.mark.unit
def test_endpoint_fingerprint_changes_when_protocol_model_or_endpoint_changes() -> None:
    """ADR-0002: results are *"invalidated by a protocol or endpoint change"*."""
    base = endpoint_fingerprint(base_url="https://a/v1", model="m", protocol="openai")
    assert base != endpoint_fingerprint(base_url="https://a/v1", model="m", protocol="anthropic")
    assert base != endpoint_fingerprint(base_url="https://a/v1", model="m2", protocol="openai")
    assert base != endpoint_fingerprint(base_url="https://b/v1", model="m", protocol="openai")


# --- the real-wire forms the first smoke found (2026-10-31, MiniMax) -------


@pytest.mark.unit
def test_a_string_shaped_tool_call_argument_is_decoded() -> None:
    """The OpenAI wire form keeps ``arguments`` as a JSON *string*.

    The first real smoke answered the tool probe with exactly this shape and
    was recorded ``unsupported`` because the string went to the schema
    comparison undecoded. Decoding the protocol's own field is not the prose
    fallback ADR-0002 refuses: a prose answer is still never parsed.
    """
    endpoint = FakeEndpoint(
        replies=(Reply(name="wire-form", tool_calls=((PROBE_TOOL_NAME, '{"verdict": "ok"}'),)),)
    )
    record = _run(endpoint, capabilities=frozenset({Capability.TOOL_CALLS}))

    assert record.outcomes[Capability.TOOL_CALLS] is CapabilityOutcome.OK


@pytest.mark.unit
def test_an_unparseable_string_argument_is_refused() -> None:
    """A string that is not JSON is a protocol failure, and it is named as one."""
    endpoint = FakeEndpoint(
        replies=(Reply(name="wire-form-broken", tool_calls=((PROBE_TOOL_NAME, "not json"),)),)
    )
    record = _run(endpoint, capabilities=frozenset({Capability.TOOL_CALLS}))

    assert record.outcomes[Capability.TOOL_CALLS] is CapabilityOutcome.UNSUPPORTED
    assert record.evidence[Capability.TOOL_CALLS] == ("tool call arguments were not parseable JSON")


@pytest.mark.unit
def test_the_prompted_template_is_a_literal_with_a_schema_placeholder() -> None:
    """pydantic-ai renders the prompted template with ``str.format``.

    A template that *is* the schema JSON — as the first probe version
    shipped — has every schema brace read as a format field, and the request
    dies with ``KeyError`` before it is sent. The probe ships a fixed literal
    carrying ``{schema}``, so the placeholder is the only brace format reads.
    """
    endpoint = FakeEndpoint(replies=(_NATIVE_JSON_REPLY,))
    record = _run(endpoint, capabilities=frozenset({Capability.STRUCTURED_OUTPUT_PROMPTED}))

    assert record.outcomes[Capability.STRUCTURED_OUTPUT_PROMPTED] is CapabilityOutcome.OK
    template = endpoint.calls[0].prompted_output_template
    assert template is not None
    assert "{schema}" in template
    # The template is an instruction, not the schema itself.
    assert '"additionalProperties"' not in template


@pytest.mark.unit
def test_one_session_is_one_runner_call() -> None:
    """All probes of a session run on one event loop, through one runner call.

    A real model holds one httpx client whose transport pools connections; a
    runner call per probe made probe two inherit probe one's keep-alive
    connection from a closed loop and die with ``RuntimeError: Event loop is
    closed`` — recorded by the first real smoke as an unsupported capability
    the endpoint had never been asked about. One runner call is the property
    that keeps every request of a session on one loop.
    """
    runner_calls: list[object] = []

    def counting_runner(awaitable: object) -> object:
        runner_calls.append(awaitable)
        return sync_runner(awaitable)

    endpoint = FakeEndpoint(
        replies=(_PROBE_REPLY_WITH_TOOL, _NATIVE_JSON_REPLY, _NATIVE_JSON_REPLY)
    )
    probe = PydanticAiProbe(
        model=endpoint,
        usage_capture=endpoint.capture,
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        runner=counting_runner,
    )
    probe.probe(
        capabilities=frozenset(ALL_CAPABILITIES),
        endpoint_fingerprint=_FINGERPRINT,
        protocol="openai_compatible",
    )

    assert len(runner_calls) == 1
    assert len(endpoint.calls) == 3


@pytest.mark.unit
def test_usage_reporting_reads_the_openai_wire_names() -> None:
    """A usage block in OpenAI's wire names is measured, not omitted.

    The first real smoke answered with a complete block
    (``prompt_tokens``/``completion_tokens``) and was still recorded
    ``usage_reporting: unsupported``, because the block went to the parser
    un-renamed. The capture renames at the observe point, so a real
    OpenAI-compatible body reaches ``USAGE_REPORTING`` as OK.
    """
    openai_form: dict[str, object] = {
        "total_tokens": 210,
        "prompt_tokens": 207,
        "completion_tokens": 3,
    }
    endpoint = FakeEndpoint(
        replies=(
            Reply(
                name="openai-wire",
                tool_calls=((PROBE_TOOL_NAME, {"verdict": "ok"}),),
                usage_body=openai_form,
            ),
        )
    )
    record = _run(
        endpoint,
        capabilities=frozenset({Capability.TOOL_CALLS, Capability.USAGE_REPORTING}),
    )

    assert record.outcomes[Capability.USAGE_REPORTING] is CapabilityOutcome.OK
