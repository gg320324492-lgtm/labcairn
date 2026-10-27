"""T09 — ``test_provider_omitting_usage_field_yields_unknown_not_zero``, the ADR's sharpest test.

This is the third binding test name from
``docs/adr/ADR-0002-model-and-tool-execution-boundary.md`` §"Contracts and
acceptance tests", and the one the LC-P1-01 work order is really about. It runs
against :mod:`labcairn.core.providers.transcripts`, so it lives beside the fixtures
rather than in ``test_fake_provider_usage.py``, which stays a pure value-type
unit test.

What it asserts, per §5.4 of the task breakdown:

=================================  ==============================  ==========================
``usage`` block                   pydantic-ai (``usage.py:89-93``)  LabCairn
=================================  ==============================  ==========================
absent                            ``0``                           ``Unknown(PROVIDER_OMITTED)``
``{}``                            ``0``                           ``Unknown(PROVIDER_OMITTED)``
``{"input_tokens": 0}``           ``0``                           ``Known(0)``
``{"input_tokens": 12}``          ``12``                          ``Known(12)``
=================================  ==============================  ==========================

The upstream contrast is exact. ``tests/test_usage_limits.py:1162``
(``test_usage_unknown_provider``) asserts that an unrecognised provider yields
``RequestUsage()`` — every counter zero — and the docstring of
``tests/test_usage_limits.py:1166`` records that upstream deliberately does
*not* have a ``None``-means-unknown convention for tokens. Row three is what
makes this test worth writing rather than a trivial "absent means unknown": it
proves the fake is not simply reporting unknown whenever anything is missing,
and it pins ADR-0002's ``Known.coerce`` contract in both directions.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from labcairn.core.providers import (
    FakeProvider,
    Known,
    MalformedResponseError,
    ModelRequest,
    ScriptDeviationError,
    Transcript,
    TranscriptExhaustedError,
    TranscriptStep,
    Unknown,
    UnknownReason,
    UsageReport,
    require_known,
)
from labcairn.core.providers.transcripts import (
    TOOL_CALL_IGNORED,
    TOOL_CALL_OK,
    TOOL_THEN_TEXT,
    USAGE_ABSENT,
    USAGE_EMPTY,
    USAGE_MALFORMED,
    USAGE_PRESENT,
    USAGE_ZERO,
)

pytestmark = pytest.mark.unit

_TOOL_REQUEST = ModelRequest(
    prompt="How many rows does results.csv have?",
    tools=("read_csv", "count_rows"),
)


def _run(transcript: Transcript, frozen_now: datetime) -> UsageReport:
    """Replay a one-step transcript and hand back the usage block."""
    responses = FakeProvider(transcript, clock=lambda: frozen_now).run()
    assert len(responses) == 1
    return responses[0].usage


# ---------------------------------------------------------------------------
# The binding test
# ---------------------------------------------------------------------------


def test_provider_omitting_usage_field_yields_unknown_not_zero(frozen_now: datetime) -> None:
    """ADR-0002 binding name. Four transcripts, four verdicts, none of them a default."""
    absent = _run(USAGE_ABSENT, frozen_now)
    empty = _run(USAGE_EMPTY, frozen_now)
    zero = _run(USAGE_ZERO, frozen_now)
    present = _run(USAGE_PRESENT, frozen_now)

    # Row 1 — no ``usage`` block at all. Upstream: every counter 0.
    assert absent.input_tokens == Unknown(UnknownReason.PROVIDER_OMITTED)
    assert absent.output_tokens == Unknown(UnknownReason.PROVIDER_OMITTED)

    # Row 2 — the block is present and empty. Upstream: still every counter 0.
    # An empty object is an absent measurement wearing a present one's clothes.
    assert empty.input_tokens == Unknown(UnknownReason.PROVIDER_OMITTED)
    assert empty.output_tokens == Unknown(UnknownReason.PROVIDER_OMITTED)

    # Row 3 — an explicit zero. Upstream also reports 0, and LabCairn reports
    # 0 too — but as ``Known(0)``, a *measurement*, which is a different state.
    assert zero.input_tokens == Known(0)
    assert zero.output_tokens == Known(0)
    assert isinstance(zero.input_tokens, Known)
    assert require_known(zero.input_tokens) == 0

    # Row 4 — ordinary numbers.
    assert present.input_tokens == Known(12)
    assert present.output_tokens == Known(34)

    # The four verdicts are not interchangeable. Row 3 (`Known(0)`) is the one
    # that must not collapse into rows 1 and 2 (`Unknown`): upstream reports the
    # same 0 for both, which is the entire defect. mypy flags the first line as
    # a non-overlapping comparison — the type disjointness showing through.
    assert zero.input_tokens != absent.input_tokens  # type: ignore[comparison-overlap]
    assert zero.input_tokens != present.input_tokens
    assert absent.input_tokens == empty.input_tokens  # both are "nothing came back"


# ---------------------------------------------------------------------------
# The rows that are not in the table: partial blocks, malformed values
# ---------------------------------------------------------------------------


def test_partial_usage_block_keeps_the_measurements_it_does_have(frozen_now: datetime) -> None:
    """A provider may report input tokens and omit output. Collapsing to one verdict loses data."""
    transcript = Transcript.of(
        "partial",
        [
            TranscriptStep.of(
                "partial",
                ModelRequest(prompt="p"),
                {"text": "t", "tool_calls": [], "usage": {"input_tokens": 7}},
            )
        ],
    )
    usage = _run(transcript, frozen_now)

    assert usage.input_tokens == Known(7)
    assert usage.output_tokens == Unknown(UnknownReason.PROVIDER_OMITTED)

    # And therefore the total is unknown, not 7 — the measured half is not the whole.
    assert usage.total_tokens == Unknown(UnknownReason.PROVIDER_OMITTED)


def test_malformed_usage_values_are_unknown_extraction_failed(frozen_now: datetime) -> None:
    """Data that arrived but could not be read is a distinct fact from data that never came."""
    usage = _run(USAGE_MALFORMED, frozen_now)

    # "12" is a string, -3 is negative. Neither is a token count.
    assert usage.input_tokens == Unknown(UnknownReason.EXTRACTION_FAILED)
    assert usage.output_tokens == Unknown(UnknownReason.EXTRACTION_FAILED)


def test_usage_null_and_missing_are_both_provider_omitted(frozen_now: datetime) -> None:
    """``"usage": null`` is the same fact as no ``usage`` key: nothing came back."""
    # ``None`` is an explicit JSON null; ``{}`` is a present-but-empty block.
    # Both say "no fields", and neither may be read as "all fields are zero".
    empty_blocks: tuple[object, ...] = (None, {})

    for index, block in enumerate(empty_blocks):
        transcript = Transcript.of(
            f"empty_usage_{index}",
            [
                TranscriptStep.of(
                    "empty_usage",
                    ModelRequest(prompt="p"),
                    {"text": "t", "tool_calls": [], "usage": block},
                )
            ],
        )
        usage = _run(transcript, frozen_now)
        assert usage.input_tokens == Unknown(UnknownReason.PROVIDER_OMITTED)
        assert usage.output_tokens == Unknown(UnknownReason.PROVIDER_OMITTED)


def test_boolean_usage_value_is_not_read_as_the_integer_one(frozen_now: datetime) -> None:
    """``bool`` is an ``int`` subclass; ``true`` for a token count is malformed, not 1."""
    transcript = Transcript.of(
        "bool_usage",
        [
            TranscriptStep.of(
                "bool_usage",
                ModelRequest(prompt="p"),
                {"text": "t", "tool_calls": [], "usage": {"input_tokens": True}},
            )
        ],
    )
    assert _run(transcript, frozen_now).input_tokens == Unknown(UnknownReason.EXTRACTION_FAILED)


# ---------------------------------------------------------------------------
# Unknown is for quantities, not for responses
# ---------------------------------------------------------------------------


def test_unreadable_response_raises_rather_than_degrading_to_empty_text() -> None:
    """A response we cannot parse is not the same as a response that said nothing.

    ``Unknown`` means "we could not measure this number". Using it for "the
    model said nothing" would let a broken adapter look like a quiet one.
    """
    transcript = Transcript.of(
        "no_text",
        [TranscriptStep.of("no_text", ModelRequest(prompt="p"), {"tool_calls": []})],
    )
    clock = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(MalformedResponseError):
        FakeProvider(transcript, clock=lambda: clock).run()


# ---------------------------------------------------------------------------
# Tool calling: the ADR-0002 §A4 fixture, staged without a probe
# ---------------------------------------------------------------------------


def test_provider_that_ignores_tools_yields_no_tool_call(frozen_now: datetime) -> None:
    """Prose that *describes* a tool call is not a tool call.

    OpenHands' ``NonNativeToolCallingMixin.post_response_non_fc`` parses intent
    back out of model prose; ADR-0002 §A4 refuses it because that makes the
    model's own prose the sole carrier of a side effect's identity and
    arguments. There is no probe in LC-P1-01 (amendment C-3), but the property
    is assertable today and the fixture is what LC-P1-03 will gate on.
    """
    response = FakeProvider(TOOL_CALL_IGNORED, clock=lambda: frozen_now).run()[0]

    assert response.tool_calls == ()
    assert "read_csv" in response.text  # the prose really does name a tool
    # …and nothing was extracted from it.


def test_provider_that_honours_tools_yields_exactly_the_scripted_call(frozen_now: datetime) -> None:
    """The control: a real ``tool_calls`` block produces exactly one parsed call."""
    response = FakeProvider(TOOL_CALL_OK, clock=lambda: frozen_now).run()[0]

    assert len(response.tool_calls) == 1
    call = response.tool_calls[0]
    assert call.name == "count_rows"
    assert call.arguments_json == '{"path":"results.csv"}'


def test_multi_step_transcript_replays_in_order(frozen_now: datetime) -> None:
    """A sequence, not a lookup — one-step transcripts cannot tell the two apart."""
    provider = FakeProvider(TOOL_THEN_TEXT, clock=lambda: frozen_now)
    responses = provider.run()

    steps = [r.transcript_step for r in responses]
    assert steps == ["tool_then_text.step1", "tool_then_text.step2"]
    assert len(responses[0].tool_calls) == 1
    assert responses[1].tool_calls == ()
    assert provider.remaining == 0


def test_replay_is_strict_about_the_request(frozen_now: datetime) -> None:
    """A fake that answers an un-asked question is decorating the test, not testing it."""
    provider = FakeProvider(TOOL_CALL_OK, clock=lambda: frozen_now)

    with pytest.raises(ScriptDeviationError, match="expected"):
        provider.send(ModelRequest(prompt="something else entirely"))


def test_replay_raises_when_the_script_runs_out(frozen_now: datetime) -> None:
    """Asking for more exchanges than the transcript records fails; it does not invent one."""
    provider = FakeProvider(TOOL_CALL_OK, clock=lambda: frozen_now)
    provider.run()

    with pytest.raises(TranscriptExhaustedError):
        provider.send(_TOOL_REQUEST)
