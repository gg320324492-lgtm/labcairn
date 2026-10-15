"""T09 — the determinism half: the same transcript must produce the same bytes, forever.

Two of these are **binding test names** from
``docs/plans/LC-P1-01-task-breakdown.md`` §T09:

* ``test_fake_provider_transcript_run_is_byte_identical_across_runs``
* ``test_fake_provider_transcript_run_is_byte_identical_across_processes``

Both compare raw bytes rather than comparing objects that happen to be equal.
The provider renders every run through one canonical encoder (``sort_keys=True``,
no incidental whitespace), so "the output is identical" is a statement about a
concrete string a reviewer can read in a failing diff.

What could break determinism, and which test notices
----------------------------------------------------
============================  ==================================================
threat                        test
============================  ==================================================
wall clock                    ``frozen_now`` is the only clock in the package;
                              ``tests/test_fake_provider_isolation.py`` proves no
                              other exists in the source
hash-order dependence         the cross-process test runs the two interpreters
                              with **different** ``PYTHONHASHSEED`` values
ambient environment           the cross-process test scrubs the environment
                              down to three variables
randomness / unseeded UUIDs   no ``random``/``uuid``/``secrets`` anywhere; same
                              isolation test
transcript mutated mid-run    ``Transcript`` and everything in it are frozen
                              dataclasses; ``test_transcript_is_immutable``
============================  ==================================================
"""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from labcairn.core.providers import (
    FakeProvider,
    ModelRequest,
    Transcript,
    TranscriptExhaustedError,
    TranscriptStep,
)
from labcairn.core.providers.transcripts import ALL_TRANSCRIPTS, TOOL_THEN_TEXT, USAGE_ABSENT

#: The program the cross-process test runs. Sweeps *every* transcript rather
#: than one, so a transcript added later cannot skip the determinism check —
#: this snippet picks it up automatically.
_REPLAY_PROGRAM = """
import sys
from datetime import UTC, datetime
from labcairn.core.providers import FakeProvider
from labcairn.core.providers.transcripts import ALL_TRANSCRIPTS

frozen = datetime(2026, 1, 1, tzinfo=UTC)
chunks = []
for transcript in ALL_TRANSCRIPTS:
    provider = FakeProvider(transcript, clock=lambda: frozen)
    provider.run()
    chunks.append(transcript.name + ":" + provider.digest())
    chunks.append(provider.render())
sys.stdout.write("\\n".join(chunks) + "\\n")
"""


def _replay_in_process() -> str:
    """Replay every transcript here, emitting exactly what ``_REPLAY_PROGRAM`` emits."""
    chunks: list[str] = []
    for transcript in ALL_TRANSCRIPTS:
        provider = FakeProvider(transcript, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC))
        provider.run()
        chunks.append(transcript.name + ":" + provider.digest())
        chunks.append(provider.render())
    return "\n".join(chunks) + "\n"


def _replay_in_subprocess(repo_root: Path, *, hash_seed: str) -> str:
    """Run the replay program with no inherited environment beyond the essentials."""
    completed = subprocess.run(
        [sys.executable, "-I", "-c", _REPLAY_PROGRAM],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=repo_root,
        env={
            "PYTHONHASHSEED": hash_seed,
            # Without this the child's stdout encoding follows the host locale,
            # and a Windows console codepage would make the byte comparison a lie.
            "PYTHONIOENCODING": "utf-8",
            # Python resolves the venv from ``sys.executable``, not from PATH,
            # so nothing else has to be present — which is the point: no HOME,
            # no locale, no API key, no proxy, no network configuration.
            "SYSTEMROOT": "C:\\Windows",
        },
        check=False,
        timeout=120,
    )
    assert completed.returncode == 0, (
        f"replay failed (PYTHONHASHSEED={hash_seed}):\n{completed.stderr}"
    )
    return completed.stdout


# ---------------------------------------------------------------------------
# In-process
# ---------------------------------------------------------------------------


def test_fake_provider_transcript_run_is_byte_identical_across_runs(frozen_now: datetime) -> None:
    """Same transcript, same frozen clock, two fresh providers — identical bytes."""
    first = FakeProvider(TOOL_THEN_TEXT, clock=lambda: frozen_now)
    first.run()

    second = FakeProvider(TOOL_THEN_TEXT, clock=lambda: frozen_now)
    second.run()

    assert first.render().encode("utf-8") == second.render().encode("utf-8")
    assert first.digest() == second.digest()
    assert first.transcript.digest() == second.transcript.digest()
    assert first.render() != ""


def test_every_transcript_replays_identically(frozen_now: datetime) -> None:
    """Sweep the whole fixture set, so a new transcript inherits the guarantee."""
    for transcript in ALL_TRANSCRIPTS:
        digests = set()
        for _ in range(2):
            provider = FakeProvider(transcript, clock=lambda: frozen_now)
            provider.run()
            digests.add(provider.digest())
        assert len(digests) == 1, f"{transcript.name} is not deterministic"


def test_a_provider_instance_advances_and_does_not_rewind(frozen_now: datetime) -> None:
    """Replaying means constructing a new one; a rewound cursor is not testable."""
    provider = FakeProvider(TOOL_THEN_TEXT, clock=lambda: frozen_now)
    assert provider.remaining == 2

    provider.run()
    assert provider.remaining == 0

    with pytest.raises(TranscriptExhaustedError):
        provider.run()

    # The transcript itself is untouched and still replayable from scratch.
    assert len(provider.transcript.steps) == 2
    fresh = FakeProvider(provider.transcript, clock=lambda: frozen_now)
    assert fresh.run()[0].transcript_step == "tool_then_text.step1"


# ---------------------------------------------------------------------------
# Across processes
# ---------------------------------------------------------------------------


def test_fake_provider_transcript_run_is_byte_identical_across_processes(
    repo_root: Path,
) -> None:
    """Two fresh interpreters, scrubbed environment, **different hash seeds** — same bytes.

    ``PYTHONHASHSEED`` differs on purpose. §5.2 of the task breakdown requires
    "no hash-order dependence", and the only way to demonstrate it is to change
    the seed and show nothing moved. An identical seed would prove nothing
    beyond "the same thing happened twice".

    The two are also compared against *this* interpreter's output, so agreement
    is not merely "the children agree with each other".
    """
    outputs = [_replay_in_subprocess(repo_root, hash_seed=seed) for seed in ("0", "1")]

    assert outputs[0].encode("utf-8") == outputs[1].encode("utf-8")
    assert outputs[0] == _replay_in_process()
    assert outputs[0] != ""

    # Every transcript is represented, so a silent skip cannot pass as success.
    for transcript in ALL_TRANSCRIPTS:
        assert transcript.name in outputs[0]


# ---------------------------------------------------------------------------
# Immutability — what makes the above a property of values, not of timing
# ---------------------------------------------------------------------------


def test_transcript_is_immutable(frozen_now: datetime) -> None:
    """A transcript is a value; mutating it mid-replay would break determinism silently."""
    transcript = TOOL_THEN_TEXT

    with pytest.raises(AttributeError):
        transcript.name = "renamed"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        transcript.steps[0].wire_json = "{}"  # type: ignore[misc]

    provider = FakeProvider(transcript, clock=lambda: frozen_now)
    before = provider.transcript.digest()
    provider.run()
    assert provider.transcript.digest() == before


def test_observed_timestamp_comes_from_the_injected_clock(frozen_now: datetime) -> None:
    """The response time is the fixture's, never the system's."""
    response = FakeProvider(USAGE_ABSENT, clock=lambda: frozen_now).run()[0]
    assert response.observed_at == frozen_now
    assert response.observed_at == datetime(2026, 1, 1, tzinfo=UTC)


def test_rendered_output_carries_the_untangled_wire_form(frozen_now: datetime) -> None:
    """A rendered run shows ``{"unknown": ...}``, never a bare number standing for it.

    Determinism and truthfulness meet here: the byte-stable rendering is also
    the one that cannot serialise "unknown" as ``0``. The measured half is
    present as a real number, so the negative half is a genuine assertion and
    not an artefact of an encoder that dropped the field.
    """
    transcript = Transcript.of(
        "render_check",
        [
            TranscriptStep.of(
                "render_check",
                ModelRequest(prompt="p"),
                {"text": "t", "tool_calls": [], "usage": {"input_tokens": 3}},
            )
        ],
    )
    provider = FakeProvider(transcript, clock=lambda: frozen_now)
    provider.run()
    rendered = provider.render()

    # Measured field -> a number. Unmeasured field -> a tag, never 0.
    assert '"input_tokens":{"known":3}' in rendered
    assert '"output_tokens":{"unknown":"provider_omitted"}' in rendered
    assert '"output_tokens":{"known":0}' not in rendered
