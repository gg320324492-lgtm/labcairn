"""Logs, failures and events must not carry a key or a document excerpt.

What is asserted, and why each is a separate test
-------------------------------------------------
The three leaks have different sources and different fixes, so testing them as
one "no secrets in logs" case would let a fix for one mask a regression in
another:

1. **The credential itself** — LabCairn holds it, so it can be removed from any
   string it passes through (:mod:`labcairn.providers.redaction`).
2. **The credential echoed by a provider** — a 4xx body routinely says
   ``"Incorrect API key provided: sk-ant-..."``. LabCairn never held that string,
   so it is attacked by shape rather than by value.
3. **The failure's own text** — third-party text is classified locally and
   **discarded**; only a digest of the *scrubbed* form survives
   (:mod:`labcairn.providers.errors`), following OpenHands'
   ``test_error_classification.py:44`` which asserts ``detail not in
   model_dump_json()`` for fourteen triples including one that echoes a key.

The key used here is synthetic and obviously fake. The repository forbids real
credentials anywhere, including in a test fixture, and this string is not one.

What is *not* claimed
---------------------
A retrieved document excerpt is, to this layer, just text. See
:mod:`labcairn.providers.adapter` — the control for excerpts lives in the
retrieval layer (LC-P1-09), and
``test_provider_adapter.py::test_phase_1_outbound_policy_forbids_excerpts``
asserts the declaration rather than pretending to enforce it.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from labcairn.core.providers.usage import Known, Unknown, UnknownReason
from labcairn.providers.adapter import PydanticAiModelProvider, prompt_digest
from labcairn.providers.capabilities import (
    ALL_CAPABILITIES,
    CapabilityOutcome,
    ProviderCapabilities,
)
from labcairn.providers.credentials import Credential, Protocol, ProviderSettings, load_credential
from labcairn.providers.errors import (
    FailureKind,
    ProviderError,
    ProviderFailure,
    classify_exception,
)
from labcairn.providers.redaction import PLACEHOLDER, Redactor

#: Synthetic, obviously not a real credential.
FAKE_KEY = "sk-ant-not-a-real-key-abcdef0123456789"

#: A file excerpt shaped like something a retrieval step would produce.
FAKE_EXCERPT = (
    "Section 3.2 reports a yield of 87.4 mg/L at 240 C, which the authors "
    "attribute to the novel catalyst (doi:10.0000/notreal)."
)


def _capabilities() -> ProviderCapabilities:
    return ProviderCapabilities.from_outcomes(
        endpoint_fingerprint="fp",
        model="m",
        protocol="p",
        outcomes=dict.fromkeys(ALL_CAPABILITIES, CapabilityOutcome.OK),
        unsupported_reason={},
    )


class _Response:
    """The minimum an httpx response exposes to the sniffer."""

    def __init__(self, content: bytes) -> None:
        self.content = content


class _FakeTransport:
    """Records the request and returns a canned response. No socket."""

    def __init__(self, content: bytes) -> None:
        self.content = content
        self.requests: list[object] = []

    async def handle_async_request(self, request: object) -> _Response:
        self.requests.append(request)
        return _Response(self.content)


# --- 1. the credential -----------------------------------------------------


@pytest.mark.unit
def test_a_registered_secret_is_removed_from_any_string() -> None:
    redactor = Redactor([FAKE_KEY])
    text = f"401 from https://api.anthropic.com/v1 with Authorization Bearer {FAKE_KEY}"

    scrubbed = redactor.scrub(text)
    assert FAKE_KEY not in scrubbed
    assert PLACEHOLDER in scrubbed
    assert redactor.contains_secret(text) is True
    assert redactor.contains_secret(scrubbed) is False


@pytest.mark.unit
def test_secret_removal_is_longest_first_so_no_dangling_tail_survives() -> None:
    """A secret that contains another secret as a substring is removed whole.

    Without the ordering, the short one is removed first and the long one is left
    with a fragment — which is still enough to be a problem in a log.
    """
    redactor = Redactor(["abcd1234", "abcd1234efgh5678"])
    assert redactor.scrub("value=abcd1234efgh5678") == f"value={PLACEHOLDER}"
    assert redactor.scrub("value=abcd1234") == f"value={PLACEHOLDER}"


@pytest.mark.unit
def test_short_values_are_refused_as_secrets() -> None:
    """Registering a 3-character secret would redact half of every log line."""
    redactor = Redactor(["abc"])
    assert redactor.registered_count == 0
    assert redactor.register("abcdefgh") is True
    assert redactor.register("abcdefgh") is True, "registering twice is idempotent"
    assert redactor.registered_count == 1


@pytest.mark.unit
def test_the_redactor_repr_names_a_count_and_never_a_value() -> None:
    """A redactor in a traceback or a debugger transcript is not a credential oracle."""
    redactor = Redactor([FAKE_KEY])
    assert FAKE_KEY not in repr(redactor)
    assert "registered=1" in repr(redactor)


# --- 2. credential shapes LabCairn never held ------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "text",
    [
        "Incorrect API key provided: sk-ant-api03-REALLOOKING-9999",
        '{"x-api-key": "sk-proj-abc123def456ghi"}',
        "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9abcdefgh",
        "GET /v1/models?api_key=sk-abcdefghijklmnop",
        "access_token=qwertyuiop123456",
    ],
)
def test_credential_shapes_are_scrubbed_without_being_registered(text: str) -> None:
    """An empty redactor still removes an echoed credential.

    This is the case where LabCairn never held the string: the provider made it
    up in a 4xx body, so value-matching cannot help and shape-matching must.
    """
    scrubbed = Redactor().scrub(text)
    assert PLACEHOLDER in scrubbed
    for fragment in ("sk-ant-api03", "sk-proj-abc", "eyJhbGciOi", "qwertyuiop"):
        assert fragment not in scrubbed


@pytest.mark.unit
def test_shape_rules_do_not_eat_ordinary_documentation() -> None:
    """A redaction rule that mangles prose costs more diagnosability than it returns.

    The word "token" in an explanatory sentence is not a credential; redacting it
    would hide the very messages an operator needs when a ceiling misbehaves.
    """
    text = "the token ceiling could not be enforced because the provider reported none"
    assert Redactor().scrub(text) == text


# --- 3. third-party failure text is discarded, not escaped ------------------


@pytest.mark.unit
def test_a_classified_failure_carries_no_field_that_can_hold_third_party_text() -> None:
    """The guarantee is structural: there is no ``detail`` field to fill in.

    Upstream's equivalent test asserts ``detail not in model_dump_json()`` for
    fourteen triples. Here there is nothing to omit, which is stronger — but it
    is also the thing a future contributor will notice and "helpfully" fix, so it
    is worth a test that says so.
    """
    fields = set(ProviderFailure.__dataclass_fields__)
    assert fields == {"kind", "retryable", "user_action", "detail_digest"}
    assert "detail" not in fields
    assert "message" not in fields, "the human sentence is a property, not stored text"


@pytest.mark.unit
def test_classification_uses_the_status_code_and_discards_the_body() -> None:
    """A body echoing the credential is digested; the digest is of the *scrubbed* text.

    The important property is the second half: a digest of the *raw* text would
    be a hash of the secret, which for a low-entropy key is the secret with extra
    steps. Two different secrets must therefore produce two different digests,
    but the same secret must produce the same one.
    """

    class _Response:
        status_code = 401

    class _HTTPStatusError(Exception):
        response = _Response()

    redactor = Redactor([FAKE_KEY])
    failure = classify_exception(
        _HTTPStatusError(f"Incorrect API key provided: {FAKE_KEY}"), redactor=redactor
    )

    assert failure.kind is FailureKind.PROVIDER_AUTH
    assert failure.retryable is False
    assert failure.user_action == "settings"
    assert len(failure.detail_digest) == 64
    assert FAKE_KEY not in failure.detail_digest
    # The message is our template, not the provider's sentence.
    assert FAKE_KEY not in failure.message
    assert "Incorrect API key provided" not in failure.message

    # Stable for the same failure.
    again = classify_exception(
        _HTTPStatusError(f"Incorrect API key provided: {FAKE_KEY}"), redactor=redactor
    )
    assert again.detail_digest == failure.detail_digest

    # And identical for a *different* leaked key, because both scrubbed to the
    # same placeholder. That is the property that proves the digest is a function
    # of the scrubbed text: had it hashed the raw body it would differ here, and
    # differing would mean it is a hash of the credential.
    other = classify_exception(
        _HTTPStatusError("Incorrect API key provided: sk-ant-a-different-fake-key-0000"),
        redactor=redactor,
    )
    assert other.detail_digest == failure.detail_digest

    # A failure whose text differs beyond the credential still digests apart.
    different = classify_exception(
        _HTTPStatusError("Rate limit exceeded for this organization"), redactor=redactor
    )
    assert different.detail_digest != failure.detail_digest


@pytest.mark.unit
def test_every_failure_kind_is_reachable_and_classified() -> None:
    """No member of the closed vocabulary is left without retry semantics.

    A member with no classification is a member that will eventually be raised by
    accident, so this is a completeness check on the table, not on the mapping.
    """
    for kind in FailureKind:
        failure = ProviderFailure.of(kind)
        assert failure.kind is kind
        assert isinstance(failure.retryable, bool)
        assert failure.user_action in {"none", "retry", "settings", "await_approval"}
        assert failure.message.strip()


@pytest.mark.unit
def test_the_only_terminal_failures_are_terminal() -> None:
    """A cancellation is not retried; a timeout is. Conflating them hides who stopped a run."""
    assert ProviderFailure.of(FailureKind.CANCELLED).retryable is False
    assert ProviderFailure.of(FailureKind.TIMEOUT).retryable is True
    assert ProviderFailure.of(FailureKind.BUDGET_EXHAUSTED).retryable is False
    assert ProviderFailure.of(FailureKind.BUDGET_ENFORCEMENT_UNAVAILABLE).retryable is False
    assert ProviderFailure.of(FailureKind.CAPABILITY_UNAVAILABLE).retryable is False


# --- 4. credentials in configuration ---------------------------------------


@pytest.mark.unit
def test_a_credential_cannot_be_printed_accidentally() -> None:
    """Every accidental path: ``repr``, ``str``, and an f-string.

    ``f"{cred}"`` goes through ``__str__`` and an f-string in a log call goes
    through ``repr``; covering both is what makes "we checked" mean something.
    """
    credential = Credential.of(FAKE_KEY, source="env:FAKE")

    assert FAKE_KEY not in repr(credential)
    assert FAKE_KEY not in str(credential)
    assert FAKE_KEY not in f"{credential}"
    assert FAKE_KEY not in f"{credential!r}"
    assert "withheld" in repr(credential)


@pytest.mark.unit
def test_a_credential_is_revealed_only_by_an_explicit_call() -> None:
    credential = Credential.of(FAKE_KEY, source="env:FAKE")
    assert credential.reveal() == FAKE_KEY
    # No attribute, index or iteration path to it.
    assert not hasattr(credential, "value")
    assert not hasattr(credential, "api_key")
    assert "key" not in dir(credential) or "reveal" in dir(credential)


@pytest.mark.unit
def test_the_fingerprint_identifies_a_key_without_revealing_it() -> None:
    """A stable identifier is safe in a report; the value is not."""
    first = Credential.of(FAKE_KEY, source="env:A")
    same = Credential.of(FAKE_KEY, source="env:B")
    other = Credential.of("sk-ant-a-completely-different-fake-key-11", source="env:A")

    assert first.fingerprint == same.fingerprint, "the same key must be recognisable"
    assert first.fingerprint != other.fingerprint
    assert FAKE_KEY not in first.fingerprint
    assert first == same and first != other
    assert len({first, same, other}) == 2, "hashing on the fingerprint, not the value"


@pytest.mark.unit
def test_reveal_call_sites_are_exhaustive() -> None:
    """There is exactly one way the secret leaves, and grep finds it.

    ADR-0002 §"No secrets in the record" is only as good as the number of places
    the value can travel. Three call sites, all of them the provider factory or a
    test, and a new one has to show up here.
    """
    package = Path(__file__).resolve().parents[1] / "src" / "labcairn" / "providers"
    product_sites: list[str] = []
    for source in sorted(package.glob("*.py")):
        for line in source.read_text(encoding="utf-8").splitlines():
            if ".reveal()" in line:
                product_sites.append(source.name)
    assert product_sites == ["pydantic_models.py"], (
        "the credential must reach a provider SDK through exactly one expression, in the "
        f"provider factory; found {product_sites}"
    )


@pytest.mark.unit
def test_the_environment_credential_is_read_by_name_not_hardcoded() -> None:
    settings = ProviderSettings(
        protocol=Protocol.OPENAI,
        model="m",
        credential_env="LABCAIRN_TEST_ONLY_KEY",
    )
    credential = load_credential(settings, environ={"LABCAIRN_TEST_ONLY_KEY": FAKE_KEY})

    assert credential.source == "env:LABCAIRN_TEST_ONLY_KEY"
    assert FAKE_KEY not in repr(credential)


# --- 5. the real log path --------------------------------------------------


@pytest.mark.unit
def test_no_log_record_from_a_failing_call_contains_a_key_or_a_prompt(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The end-to-end assertion: drive a failing call and search every log line.

    Driven through the adapter rather than the redactor so the whole chain —
    classify, log, format — is exercised. The prompt is a synthetic stand-in for
    research material; a real one would be a document excerpt, and the test
    asserts the same thing about both.
    """
    from provider_fakes import FakeEndpoint

    secret_in_prompt = f"[EXCERPT] {FAKE_EXCERPT}"

    class _Response:
        status_code = 401

    class _HTTPStatusError(Exception):
        response = _Response()

    endpoint = FakeEndpoint(
        always_raises=_HTTPStatusError(f"Incorrect API key provided: {FAKE_KEY}")
    )
    redactor = Redactor([FAKE_KEY])
    provider = PydanticAiModelProvider(
        model=endpoint,
        usage_capture=endpoint.capture,
        redactor=redactor,
        runner=lambda awaitable: __import__("asyncio").run(awaitable),
        capabilities=_capabilities(),
    )

    from labcairn.core.providers.protocol import ModelRequest

    with caplog.at_level(logging.DEBUG), pytest.raises(ProviderError) as raised:
        provider.send(ModelRequest(prompt=secret_in_prompt))

    # The failure was classified, not merely raised.
    assert raised.value.failure.kind is FailureKind.PROVIDER_AUTH
    rendered = "\n".join(record.getMessage() for record in caplog.records)
    assert rendered, "the adapter must log something; an empty log proves nothing"
    assert FAKE_KEY not in rendered
    assert "sk-ant" not in rendered
    assert "10.0000/notreal" not in rendered, "an excerpt must not reach a log line"
    assert "87.4 mg/L" not in rendered
    # What *is* there is the classification and the digest.
    assert "provider_auth" in rendered
    assert prompt_digest(secret_in_prompt) in rendered
    assert redactor.contains_secret(rendered) is False


@pytest.mark.unit
def test_a_successful_call_logs_a_digest_and_never_the_prompt(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The happy path has the same obligation: provenance, not content."""
    import asyncio

    from provider_fakes import FakeEndpoint, Reply

    from labcairn.core.providers.protocol import ModelRequest

    endpoint = FakeEndpoint(
        replies=(Reply(name="ok", text="done", usage_body={"input_tokens": 4, "output_tokens": 2}),)
    )
    provider = PydanticAiModelProvider(
        model=endpoint,
        usage_capture=endpoint.capture,
        runner=asyncio.run,
        capabilities=_capabilities(),
    )

    with caplog.at_level(logging.DEBUG):
        provider.send(ModelRequest(prompt=f"analyse {FAKE_EXCERPT}"))

    rendered = "\n".join(record.getMessage() for record in caplog.records)
    assert rendered
    assert "87.4 mg/L" not in rendered
    assert "10.0000/notreal" not in rendered
    assert prompt_digest(f"analyse {FAKE_EXCERPT}") in rendered


@pytest.mark.unit
def test_an_exchange_record_is_safe_to_export_verbatim() -> None:
    """The record a task stores contains no text to disclose.

    Asserted by rendering the whole thing, because the risk is in the field
    nobody thought of adding.
    """
    import asyncio

    from provider_fakes import FakeEndpoint, Reply

    from labcairn.core.providers.protocol import ModelRequest

    endpoint = FakeEndpoint(
        replies=(
            Reply(
                name="ok",
                text="the answer",
                usage_body={"input_tokens": 4, "output_tokens": 2},
            ),
        )
    )
    provider = PydanticAiModelProvider(
        model=endpoint,
        usage_capture=endpoint.capture,
        runner=asyncio.run,
        capabilities=_capabilities(),
    )
    provider.send(ModelRequest(prompt=f"analyse {FAKE_EXCERPT}", tools=("read_file",)))

    (exchange,) = provider.exchanges()
    wire = json.dumps(exchange.to_wire())
    assert FAKE_EXCERPT not in wire
    assert "the answer" not in wire, "a completion body is also a disclosure surface"
    assert "read_file" in wire, "tool names are declared material and are recorded"
    assert exchange.outbound.sends_document_excerpts is False


# --- 6. the raw-body sniffer -----------------------------------------------


@pytest.mark.unit
def test_the_sniffer_keeps_only_the_usage_key_of_a_response_body() -> None:
    """The sniffer must not become a document cache.

    A completion body carries the model's text, which after one retrieval step is
    an excerpt. Keeping the whole body — even briefly — would put a document in a
    class whose retention is nobody's job to reason about.
    """
    import asyncio

    from labcairn.providers.usage_capture import HttpxUsageSniffer

    body = json.dumps(
        {"choices": [{"message": {"content": FAKE_EXCERPT}}], "usage": {"input_tokens": 11}}
    ).encode()
    sniffer = HttpxUsageSniffer(_FakeTransport(body))

    asyncio.run(sniffer.handle_async_request(object()))

    assert sniffer.report().input_tokens == Known(11)
    for fragment in ("87.4 mg/L", "choices", "notreal"):
        assert fragment not in repr(sniffer.report())
    assert sniffer.report().output_tokens == Unknown(reason=UnknownReason.PROVIDER_OMITTED)


@pytest.mark.unit
def test_the_sniffer_reports_unknown_for_a_non_json_body() -> None:
    """An HTML error page is a normal provider failure, and it measures nothing."""
    import asyncio

    from labcairn.providers.usage_capture import HttpxUsageSniffer

    sniffer = HttpxUsageSniffer(_FakeTransport(b"<html>502 Bad Gateway</html>"))
    asyncio.run(sniffer.handle_async_request(object()))

    report = sniffer.report()
    assert report.input_tokens == Unknown(reason=UnknownReason.PROVIDER_OMITTED)
    assert report.output_tokens == Unknown(reason=UnknownReason.PROVIDER_OMITTED)


@pytest.mark.unit
def test_the_sniffer_forwards_the_response_untouched() -> None:
    """It observes; it does not interfere. A wrapper that altered the response
    would be a second, invisible transformation in the transport path."""
    import asyncio

    from labcairn.providers.usage_capture import HttpxUsageSniffer

    transport = _FakeTransport(b'{"usage": {"input_tokens": 1}}')
    sniffer = HttpxUsageSniffer(transport)
    response = asyncio.run(sniffer.handle_async_request("request-object"))

    assert transport.requests == ["request-object"]
    assert response.content == b'{"usage": {"input_tokens": 1}}'
