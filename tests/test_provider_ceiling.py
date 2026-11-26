"""The provider's output ceiling, and the input token count the endpoint reports.

Two properties, both of them things the pilot's first real request turned up.

**The output ceiling.** The provider's configuration now carries a
``max_output_tokens`` field beside ``timeout_s``. It is optional, it is
validated rather than coerced, and it reaches the model call as ``max_tokens``
-- so the operator can state a ceiling instead of letting the provider's own
default decide, and a truncated answer is refused rather than recorded.

**The input count.** The Anthropic protocol reports the input tokens of a
request in three fields, and only one of them is called ``input_tokens``: the
tokens the provider counted outright. The prompt-cache portions arrive under
their own names, and reading ``input_tokens`` alone is silent about them. It
was silent in the pilot's run too: ``Known(1)`` for a 1,699-character prompt.

Every test says in its docstring what would make it red.
"""

from __future__ import annotations

from typing import Any

import pytest
from provider_fakes import FakeEndpoint, PermissiveConsent, Reply, sync_runner

from labcairn.core.providers.protocol import ModelRequest
from labcairn.core.providers.usage import Known
from labcairn.providers.adapter import PydanticAiModelProvider
from labcairn.providers.credentials import Credential, Protocol, ProviderSettings
from labcairn.providers.usage_capture import RecordingUsageCapture

#: An entry with no ceiling in it. Every configuration test starts from this.
_BASE_ENTRY: dict[str, object] = {"protocol": "anthropic", "model": "a-model"}


def _settings(**overrides: object) -> ProviderSettings:
    return ProviderSettings.from_mapping({**_BASE_ENTRY, **overrides})


def _adapter(
    endpoint: FakeEndpoint,
    **kwargs: Any,
) -> PydanticAiModelProvider:
    return PydanticAiModelProvider(
        model=endpoint,
        consent=PermissiveConsent(),
        usage_capture=endpoint.capture,
        runner=sync_runner,
        **kwargs,
    )


# --- the configuration's field -------------------------------------------


def test_an_entry_that_names_no_ceiling_carries_none() -> None:
    """An entry without ``max_output_tokens`` has no ceiling.

    Red when: the field defaults to anything but ``None``. A default of, say,
    4096 would silently cap every answer the product asked for -- a ceiling
    nobody wrote down, enforced on every request.
    """
    assert _settings().max_output_tokens is None


def test_a_settings_object_built_without_a_ceiling_carries_none() -> None:
    """The same, for a settings object built directly rather than parsed.

    Red when: the dataclass default is anything but ``None``. The parsed path
    passes the value explicitly and would hide such a default; this is the
    path a caller that builds its own settings takes.
    """
    assert ProviderSettings(protocol=Protocol.ANTHROPIC, model="a-model").max_output_tokens is None


def test_the_entry_names_the_ceiling() -> None:
    """The ceiling in the file is the ceiling in the settings.

    Red when: the key is dropped on the way through -- the field would exist
    in the record and be read by nobody.
    """
    assert _settings(max_output_tokens=4096).max_output_tokens == 4096


@pytest.mark.parametrize("value", [-1, -4096])
def test_a_negative_ceiling_is_refused(value: int) -> None:
    """A negative ceiling is refused, not clamped and not carried.

    Red when: the value survives the parse. Clamping it to zero, or passing it
    through, would send a ceiling the provider cannot honour -- and the
    refusal would arrive as a provider error rather than as a refusal here.
    """
    with pytest.raises(ValueError, match="max_output_tokens"):
        _settings(max_output_tokens=value)


@pytest.mark.parametrize("value", ["4096", 4096.5, True])
def test_a_ceiling_that_is_not_an_integer_is_refused(value: object) -> None:
    """A ceiling that is not an integer is refused, not coerced.

    Red when: any of the three is turned into a number. ``"4096"`` would
    become 4096 and ``4096.5`` would become 4096, and both would then be a
    different statement from the one the operator wrote. ``True`` is an ``int``
    in Python and would become a ceiling of one token.
    """
    with pytest.raises(ValueError, match="must be an integer"):
        _settings(max_output_tokens=value)


def test_a_zero_ceiling_is_refused() -> None:
    """A ceiling of zero is refused.

    Red when: zero is accepted. It cannot produce an answer, so every request
    under it would end in a truncation refusal -- paid for, and refused.
    """
    with pytest.raises(ValueError, match="must be positive"):
        _settings(max_output_tokens=0)


def test_a_misspelled_ceiling_key_is_still_refused() -> None:
    """The key set stays closed, the new key included.

    Red when: the strictness is loosened, or the new key is spelled
    differently in the parser than in the record -- a typo that silently
    leaves the ceiling unset is the failure this whole key set exists to
    prevent.
    """
    with pytest.raises(ValueError, match="unknown provider settings key"):
        _settings(max_output_token=4096)


# --- the ceiling reaching the model call ----------------------------------


def test_the_ceiling_reaches_the_model_call() -> None:
    """The ceiling is the provider's ``max_tokens``.

    Red when: ``_dispatch`` stops setting ``max_tokens`` -- the adapter would
    then ask for an unbounded answer and the provider's own default would
    decide, which is the gap this field exists to close.
    """
    endpoint = FakeEndpoint(replies=(Reply(name="ok", text="ok"),))
    _adapter(endpoint, max_output_tokens=4096).send(ModelRequest(prompt="hello"))

    settings = endpoint.calls[0].model_settings
    assert settings is not None
    assert settings["max_tokens"] == 4096


def test_an_adapter_without_a_ceiling_sends_no_ceiling() -> None:
    """No ceiling in, no ceiling out.

    Red when: the adapter starts sending a ``max_tokens`` of its own. A
    provider entry that does not name a ceiling must behave as it did before
    the field existed.
    """
    endpoint = FakeEndpoint(replies=(Reply(name="ok", text="ok"),))
    _adapter(endpoint).send(ModelRequest(prompt="hello"))

    assert endpoint.calls[0].model_settings is None


@pytest.mark.parametrize("value", [0, -1])
def test_the_adapter_refuses_a_ceiling_that_is_not_positive(value: int) -> None:
    """The adapter refuses the ceiling as well as the configuration.

    Red when: the adapter accepts it -- this is the last place before the
    number becomes a wire argument, and a caller that builds an adapter
    directly (the pilot's driver does) must not be able to send a ceiling the
    provider cannot honour.
    """
    endpoint = FakeEndpoint(replies=(Reply(name="ok", text="ok"),))
    with pytest.raises(ValueError, match="max_output_tokens"):
        _adapter(endpoint, max_output_tokens=value)


def test_the_clis_transport_hands_the_ceiling_to_the_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The configuration's ceiling reaches the adapter the CLI builds.

    Red when: ``_suggestion_transport`` stops passing ``max_output_tokens`` --
    the field would then be read by nobody, and the product's own suggestion
    path would keep running under the provider's default ceiling, which is the
    finding the pilot recorded.
    """
    import labcairn.providers.adapter as adapter_module
    from labcairn.cli import commands

    captured: dict[str, Any] = {}
    real = adapter_module.PydanticAiModelProvider

    def recording(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(adapter_module, "PydanticAiModelProvider", recording)

    settings = _settings(max_output_tokens=4096)
    credential = Credential.of("not-a-real-key", source="test")
    commands._suggestion_transport(settings, credential)

    assert captured.get("max_output_tokens") == 4096


# --- the input token count ------------------------------------------------


def test_the_input_count_is_the_whole_input() -> None:
    """The prompt-cache portions count as input.

    Red when: the capture stops folding ``cache_read_input_tokens`` and
    ``cache_creation_input_tokens`` into ``input_tokens``. The reading would
    then be the part the provider happened to count outright, and the pilot's
    ``Known(1)`` for a 1,699-character prompt would be back.

    The numbers are the ones measured on 2026-11-26 against MiniMax's
    Anthropic-compatible endpoint: the same prompt was reported once as 378
    with 128 cached and once as 122 with 384 cached, and both readings are 506
    tokens of input.
    """
    capture = RecordingUsageCapture()
    capture.observe(
        {
            "usage": {
                "input_tokens": 1,
                "cache_read_input_tokens": 505,
                "cache_creation_input_tokens": 0,
                "output_tokens": 6089,
            }
        }
    )

    report = capture.report()
    assert report.input_tokens == Known(506)
    assert report.output_tokens == Known(6089)


def test_a_block_with_no_cache_portions_is_read_as_reported() -> None:
    """An endpoint that caches nothing is read exactly as it speaks.

    Red when: the fold changes a count it has no business changing -- an
    endpoint whose counters are already the whole input would start reporting
    a different number.
    """
    capture = RecordingUsageCapture()
    capture.observe({"usage": {"input_tokens": 209, "output_tokens": 3}})

    report = capture.report()
    assert report.input_tokens == Known(209)
    assert report.output_tokens == Known(3)


def test_an_openai_block_is_renamed_and_its_prompt_tokens_are_the_input() -> None:
    """The OpenAI spelling is renamed, and not folded.

    Red when: the OpenAI branch starts folding too -- ``prompt_tokens`` is
    already the whole input on that protocol, and a cache counter beside it
    would be counted twice.
    """
    capture = RecordingUsageCapture()
    capture.observe(
        {
            "usage": {
                "prompt_tokens": 512,
                "completion_tokens": 34,
                "cache_read_input_tokens": 100,
            }
        }
    )

    report = capture.report()
    assert report.input_tokens == Known(512)
    assert report.output_tokens == Known(34)


def test_the_exchange_record_carries_the_whole_input() -> None:
    """The reading that reaches the exchange record is the whole input.

    Red when: the fold does not survive the trip through the adapter -- the
    capture would be right and the recorded exchange would still under-read
    the traffic, and the budget would be arithmetic on the wrong number.
    """
    endpoint = FakeEndpoint(
        replies=(
            Reply(
                name="ok",
                text="ok",
                usage_body={
                    "input_tokens": 1,
                    "cache_read_input_tokens": 505,
                    "output_tokens": 42,
                },
            ),
        )
    )
    adapter = _adapter(endpoint)
    adapter.send(ModelRequest(prompt="hello"))

    exchange = adapter.exchanges()[0]
    assert exchange.usage_input == Known(506)
    assert exchange.usage_output == Known(42)
