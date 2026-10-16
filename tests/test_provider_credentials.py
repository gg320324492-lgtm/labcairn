"""Credentials and provider configuration.

The repository forbids real credentials anywhere, including fixtures, so nothing
in this file reads the ambient environment. Every test passes an explicit
``environ`` mapping — which is also why
:func:`~labcairn.providers.credentials.load_credential` takes ``environ`` as a
parameter rather than reaching for :data:`os.environ`: a test that *could*
inherit a developer's real key is a test that eventually prints one.

The synthetic key used throughout is obviously not a real credential.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from labcairn.providers.credentials import (
    DEFAULT_BASE_URLS,
    Credential,
    MissingCredentialError,
    Protocol,
    ProviderSettings,
    UnknownProviderError,
    load_credential,
    load_providers_config,
)
from labcairn.providers.pydantic_models import auth_header_name

FAKE_KEY = "sk-ant-not-a-real-key-abcdef0123456789"


def _settings(**overrides: object) -> ProviderSettings:
    base: dict[str, object] = {
        "protocol": Protocol.OPENAI,
        "model": "claude-sonnet-5",
        "credential_env": "LABCAIRN_TEST_ONLY_KEY",
    }
    base.update(overrides)
    return ProviderSettings(**base)  # type: ignore[arg-type]


# --- sources ---------------------------------------------------------------


@pytest.mark.unit
def test_a_credential_is_read_from_the_named_environment_variable() -> None:
    credential = load_credential(_settings(), environ={"LABCAIRN_TEST_ONLY_KEY": FAKE_KEY})
    assert credential.reveal() == FAKE_KEY
    assert credential.source == "env:LABCAIRN_TEST_ONLY_KEY"


@pytest.mark.unit
def test_surrounding_whitespace_is_stripped_because_every_editor_adds_it() -> None:
    """A trailing newline in an ``Authorization`` header is a 401 that looks
    like a wrong key — the single most common self-inflicted config bug."""
    credential = load_credential(_settings(), environ={"LABCAIRN_TEST_ONLY_KEY": f"  {FAKE_KEY}\n"})
    assert credential.reveal() == FAKE_KEY


@pytest.mark.unit
def test_a_configured_file_is_the_second_source(tmp_path: Path) -> None:
    key_file = tmp_path / "provider.key"
    key_file.write_text(FAKE_KEY + "\n", encoding="utf-8")

    credential = load_credential(_settings(credential_file=key_file), environ={})
    assert credential.reveal() == FAKE_KEY
    assert credential.source.startswith("file:")


@pytest.mark.unit
def test_the_environment_wins_over_a_file(tmp_path: Path) -> None:
    key_file = tmp_path / "other.key"
    key_file.write_text("sk-ant-from-the-file-000000000", encoding="utf-8")

    credential = load_credential(
        _settings(credential_file=key_file), environ={"LABCAIRN_TEST_ONLY_KEY": FAKE_KEY}
    )
    assert credential.reveal() == FAKE_KEY


@pytest.mark.unit
def test_no_credential_anywhere_says_where_it_looked() -> None:
    """The error names the *variable*, never a value, and never invents a source."""
    with pytest.raises(MissingCredentialError) as raised:
        load_credential(_settings(), environ={})
    assert "LABCAIRN_TEST_ONLY_KEY" in str(raised.value)

    with pytest.raises(MissingCredentialError) as raised:
        load_credential(_settings(credential_env=None, credential_file=None), environ={})
    assert "none configured" in str(raised.value)


@pytest.mark.unit
def test_a_missing_credential_file_is_an_error_not_an_empty_credential() -> None:
    """Silently continuing with an empty key would produce a 401 that reads as
    "the provider is down"."""
    with pytest.raises(MissingCredentialError) as raised:
        load_credential(
            _settings(credential_env=None, credential_file=Path("does-not-exist.key")), environ={}
        )
    assert "does not exist" in str(raised.value)


@pytest.mark.unit
def test_an_empty_credential_is_refused() -> None:
    with pytest.raises(MissingCredentialError):
        Credential.of("   ", source="env:X")
    with pytest.raises(MissingCredentialError):
        load_credential(_settings(), environ={"LABCAIRN_TEST_ONLY_KEY": ""})


# --- the three protocols ---------------------------------------------------


@pytest.mark.unit
def test_the_three_required_protocols_are_configurable() -> None:
    """At least OpenAI, Anthropic, and one OpenAI-compatible custom endpoint."""
    openai = _settings(protocol=Protocol.OPENAI)
    anthropic = _settings(protocol=Protocol.ANTHROPIC)
    compatible = _settings(
        protocol=Protocol.OPENAI_COMPATIBLE,
        model="qwen2.5-7b-instruct",
        base_url="https://gateway.internal/v1",
    )

    assert openai.effective_base_url == DEFAULT_BASE_URLS[Protocol.OPENAI]
    assert anthropic.effective_base_url == DEFAULT_BASE_URLS[Protocol.ANTHROPIC]
    assert compatible.effective_base_url == "https://gateway.internal/v1"
    assert auth_header_name(Protocol.ANTHROPIC) == "x-api-key"
    assert auth_header_name(Protocol.OPENAI_COMPATIBLE) == "Authorization"


@pytest.mark.unit
def test_an_openai_compatible_endpoint_must_name_its_own_base_url() -> None:
    """There is no default for a host the project does not know.

    Silently falling back to ``api.openai.com`` would send a user's self-hosted
    gateway traffic to a third party — the exact disclosure failure the work
    order's acceptance line is about.
    """
    with pytest.raises(ValueError, match="must name a base_url"):
        _settings(protocol=Protocol.OPENAI_COMPATIBLE)
    # And with one, it is honoured verbatim.
    settings = _settings(protocol=Protocol.OPENAI_COMPATIBLE, base_url="http://localhost:8080/v1")
    assert settings.effective_base_url == "http://localhost:8080/v1"


@pytest.mark.unit
def test_a_base_url_that_carries_a_credential_is_sanitised_for_the_fingerprint() -> None:
    """``?api_key=`` on a self-hosted gateway is a common deployment, not an error."""
    settings = _settings(
        protocol=Protocol.OPENAI_COMPATIBLE,
        base_url="https://user:secret@gateway.internal/v1?api_key=sk-leaked-in-a-url",
    )
    sanitised = settings.sanitised_base_url()

    assert sanitised == "https://gateway.internal/v1"
    assert "secret" not in sanitised
    assert "sk-leaked" not in sanitised
    assert "@" not in sanitised


@pytest.mark.unit
@pytest.mark.parametrize(
    "overrides",
    [
        {"model": "  "},
        {"timeout_s": 0},
        {"timeout_s": -1},
    ],
)
def test_nonsensical_settings_are_refused(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        _settings(**overrides)


# --- the config file -------------------------------------------------------


@pytest.mark.unit
def test_a_providers_config_file_is_parsed_strictly(tmp_path: Path) -> None:
    config = tmp_path / "providers.json"
    config.write_text(
        json.dumps(
            {
                "providers": {
                    "local": {
                        "protocol": "openai_compatible",
                        "model": "qwen2.5-7b-instruct",
                        "base_url": "http://localhost:8080/v1",
                        "credential_env": "LOCAL_KEY",
                        "timeout_s": 30,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    providers = load_providers_config(config)
    local = providers["local"]
    assert local.protocol is Protocol.OPENAI_COMPATIBLE
    assert local.model == "qwen2.5-7b-instruct"
    assert local.timeout_s == 30.0


@pytest.mark.unit
def test_a_misspelled_config_key_is_an_error_rather_than_a_silent_default() -> None:
    """``base_ur1`` would otherwise leave ``base_url`` unset and send the
    request to the wrong place."""
    with pytest.raises(ValueError, match="unknown provider settings key"):
        ProviderSettings.from_mapping(
            {
                "protocol": "openai_compatible",
                "model": "m",
                "base_ur1": "http://localhost:8080/v1",
            }
        )


@pytest.mark.unit
def test_an_unrecognised_protocol_names_the_there_are_ones() -> None:
    with pytest.raises(UnknownProviderError) as raised:
        ProviderSettings.from_mapping({"protocol": "llama-cpp-server", "model": "m"})
    assert "openai" in str(raised.value)
    assert "anthropic" in str(raised.value)
    assert "openai_compatible" in str(raised.value)


@pytest.mark.unit
def test_a_malformed_config_file_is_reported_as_such(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    with pytest.raises(MissingCredentialError):
        load_providers_config(missing)

    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        load_providers_config(broken)

    wrong_shape = tmp_path / "wrong.json"
    wrong_shape.write_text('{"models": {}}', encoding="utf-8")
    with pytest.raises(ValueError, match='top-level "providers"'):
        load_providers_config(wrong_shape)


# --- the real-provider wiring -----------------------------------------------


@pytest.mark.unit
def test_the_usage_sniffer_is_the_clients_transport_not_a_side_channel() -> None:
    """The sniffer must be *in* the request path, or it observes nothing.

    Asserted structurally rather than by making a request: the point is the
    wiring, and a test that issued a live call to check it would be exactly the
    thing this work order may not do.
    """
    import httpx

    from labcairn.providers.pydantic_models import build_http_client, make_sniffer

    sniffer = make_sniffer()
    client = build_http_client(_settings(), sniffer=sniffer)

    assert client._transport is sniffer
    assert isinstance(client, httpx.AsyncClient)
    assert sniffer.inner is not None, "a sniffer with no inner transport forwards to nothing"
    asyncio.run(client.aclose())


@pytest.mark.unit
def test_a_client_without_a_sniffer_is_still_constructible_and_still_safe() -> None:
    """Omitting the sniffer must not crash — it must simply measure nothing."""
    from labcairn.providers.pydantic_models import build_http_client

    client = build_http_client(_settings())
    assert client._transport is not None
    asyncio.run(client.aclose())


@pytest.mark.requires_provider
@pytest.mark.skip(
    reason=(
        "NOT RUN. Requires the project owner's explicit authorisation to spend money and a "
        "credential they supplied for that purpose. LC-P1-03 must not use a credential found "
        "in this machine's environment."
    )
)
def test_real_provider_smoke_records_capabilities_and_usage() -> None:
    """One live call per supported protocol. **Not executed by this work order.**

    The procedure is :func:`~labcairn.providers.pydantic_models.smoke_test`, so
    running this is a matter of supplying ``LABCAIRN_PROVIDER_SMOKE_*`` and
    removing the skip — not of writing new code. Recorded here, skipped, so the
    gap is visible in the suite rather than in a handover note somebody has to
    remember to read.

    What it asserts when it does run: probe results are recorded per protocol,
    and usage is ``Known`` or explicitly ``Unknown`` — never silently
    ``Known(0)``, which is the whole point of the exercise.
    """
    from labcairn.providers.pydantic_models import smoke_test

    result = smoke_test(
        _settings(protocol=Protocol.ANTHROPIC, credential_env="LABCAIRN_PROVIDER_SMOKE_KEY"),
        environ={},
    )
    outcomes = result["outcomes"]
    assert isinstance(outcomes, dict)
    assert outcomes
    for outcome in outcomes.values():
        assert outcome in {"ok", "unsupported", "unverified", "refused"}
