"""``FakeProvider`` — a scripted model provider with no network, no clock, no randomness.

What this is for
----------------
LC-P1-01's Build requirement is *"A FakeProvider and deterministic demo fixtures
must run without paid APIs."* This module is that requirement, and its
interesting property is not that it fakes a model — it is that **faking a model
forces you to decide what a missing measurement looks like**, which is the
question ADR-0002 says both upstreams get wrong.

Every response is pre-recorded, so there is no API key, no socket, no rate
limit and no bill. ``send()`` is a lookup, not a call. The fake imports nothing
from the network stack; ``tests/test_fake_provider_isolation.py`` asserts that
at the AST level rather than taking it on trust.

Determinism, and what would break it
------------------------------------
Three invariants, each covered by a test that fails if the invariant is broken:

* **No system clock.** The response timestamp comes from an injected
  ``Callable[[], datetime]``. In tests that is the repository's ``frozen_now``
  fixture; in LC-P1-13 it will be a ``Clock``. Nothing here calls
  ``datetime.now()``, ``time.time()``, ``date.today()``, ``random`` or ``uuid4``
  — ``tests/test_fake_provider_isolation.py::test_provider_module_has_no_nondeterministic_source``
  asserts the absence at the source level, so a future edit cannot reintroduce one.
* **No hash-order dependence.** Every rendered mapping is emitted through
  :func:`~labcairn.core.providers.protocol.canonical_json`, which sorts keys. Two
  processes with different ``PYTHONHASHSEED`` therefore agree byte for byte.
* **No ambient environment.** No ``$HOME``, no locale, no cwd. A transcript is
  a value held in memory; there is no fixture directory to locate.

Scripted replay
---------------
A :class:`Transcript` is an ordered list of :class:`TranscriptStep`, each pairing
the request that must arrive with the raw payload the provider will return.
Replay is strict: a request that does not match the script raises
:class:`ScriptDeviationError` rather than being served anyway. A fake that quietly
answers un-asked questions is how a test suite rots into fiction.

Transcript payloads are stored as **canonical JSON text**, not as Python dicts.
That is deliberate. A raw wire payload is JSON, and parsing it back through
:func:`json.loads` exercises the same decode path a real adapter would; it also
makes each step hashable and byte-comparable without a mutable mapping hiding
inside a frozen dataclass.

Where LC-P1-03 plugs in
-----------------------
:class:`~labcairn.core.providers.protocol.ModelProvider` is the interface, and this
class satisfies it structurally. LC-P1-03 adds real adapters behind the same
Protocol, plus the members amendment C-3 kept out of here — capability probing,
budget ceilings, cancel/timeout. Nothing in this file needs to change for that:
a real adapter takes a payload from the wire and hands it to
:meth:`~labcairn.core.providers.protocol.ModelResponse.from_wire`, the same call the
fake makes, so the honest-usage parsing under test here is the parsing LC-P1-03
ships. The transcript *format* is the other reuse surface — LC-P1-03's provider
tests and LC-P1-13's e2e can build on these six fixtures instead of inventing
their own, which is why they are named for the situation they reproduce rather
than for a particular assertion.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from labcairn.core.providers.protocol import (
    MalformedResponseError,
    ModelRequest,
    ModelResponse,
    canonical_json,
)


class TranscriptExhaustedError(RuntimeError):
    """The script ran out. A replay asked for more than the transcript records.

    Not a budget and not a cancellation — just "the script said two exchanges,
    you asked for three". Failing loudly is the point; a fake that invents an
    eleventh response is a fake whose tests prove nothing.
    """


class ScriptDeviationError(RuntimeError):
    """The incoming request is not the one the transcript scripted for this step.

    Strictness is a feature, not pedantry: a transcript that serves its next
    scripted answer to *any* request is no longer testing the caller's
    behaviour, it is decorating it.
    """


@dataclass(frozen=True, slots=True)
class TranscriptStep:
    """One scripted exchange: the request that must arrive, and the raw reply."""

    name: str
    request: ModelRequest
    #: The provider payload exactly as a real endpoint would have returned it.
    #: Canonical JSON text — see the module docstring for why text and not a dict.
    wire_json: str

    @classmethod
    def of(cls, name: str, request: ModelRequest, wire: Mapping[str, object]) -> TranscriptStep:
        """Build a step from a Python mapping, canonically encoded.

        ``wire`` is kept as the source of truth for what the payload *means*;
        canonicalising here means a fixture's bytes do not depend on how the
        literal happened to be spelled in the source file.
        """
        return cls(name=name, request=request, wire_json=canonical_json(wire))


@dataclass(frozen=True, slots=True)
class Transcript:
    """An ordered, named script. Reusable across work orders."""

    name: str
    steps: tuple[TranscriptStep, ...]

    @classmethod
    def of(cls, name: str, steps: Sequence[TranscriptStep]) -> Transcript:
        return cls(name=name, steps=tuple(steps))

    def render(self) -> str:
        """The whole script as canonical JSON. Byte-stable for a given script."""
        return canonical_json(
            {
                "transcript": self.name,
                "steps": [
                    {
                        "name": step.name,
                        "request": step.request.to_wire(),
                        "wire": json.loads(step.wire_json),
                    }
                    for step in self.steps
                ],
            }
        )

    def digest(self) -> str:
        """SHA-256 of :meth:`render`. A single value to assert on for byte-identity."""
        return hashlib.sha256(self.render().encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Exchange:
    """One completed request/response pair, as the provider recorded it."""

    request: ModelRequest
    response: ModelResponse

    def to_wire(self) -> Mapping[str, object]:
        return {"request": self.request.to_wire(), "response": self.response.to_wire()}


class FakeProvider:
    """A :class:`~labcairn.core.providers.protocol.ModelProvider` that replays a script.

    Usage::

        provider = FakeProvider(TRANSCRIPT_USAGE_ABSENT, clock=lambda: frozen_now)
        response = provider.send(ModelRequest(prompt="hello"))
        assert response.usage.input_tokens == Unknown(UnknownReason.PROVIDER_OMITTED)

    One instance walks one transcript once, in order. Construct a fresh instance
    to replay again — there is no rewind, because a cursor that silently
    rewinds is a cursor whose position no test can reason about.
    """

    def __init__(self, transcript: Transcript, *, clock: Callable[[], datetime]) -> None:
        self._transcript = transcript
        self._clock = clock
        self._cursor = 0
        self._exchanges: list[Exchange] = []

    @property
    def name(self) -> str:
        return f"fake:{self._transcript.name}"

    @property
    def transcript(self) -> Transcript:
        return self._transcript

    @property
    def remaining(self) -> int:
        return len(self._transcript.steps) - self._cursor

    def send(self, request: ModelRequest) -> ModelResponse:
        """Return the scripted response for ``request``, consuming one step."""
        if self._cursor >= len(self._transcript.steps):
            raise TranscriptExhaustedError(
                f"{self.name}: transcript has {self._cursor} steps; "
                f"no answer for {request.prompt!r}"
            )
        step = self._transcript.steps[self._cursor]
        if request != step.request:
            raise ScriptDeviationError(
                f"{self.name}: step {self._cursor} ({step.name}) expected "
                f"{step.request.to_wire()!r}, got {request.to_wire()!r}"
            )
        self._cursor += 1
        response = ModelResponse.from_wire(
            _decode(step.wire_json, step.name),
            transcript_step=step.name,
            observed_at=self._clock(),
        )
        self._exchanges.append(Exchange(request=request, response=response))
        return response

    def run(self) -> tuple[ModelResponse, ...]:
        """Replay every remaining step, using each step's own scripted request.

        The convenience entry point for LC-P1-13's end-to-end path. It issues the
        request the script expects rather than inventing one, so ``run()`` and a
        manual ``send()`` loop produce identical bytes.

        Raises :class:`TranscriptExhaustedError` when there is nothing left,
        rather than returning an empty tuple. "I asked to replay and there was
        no script" is a bug in the caller, and an empty return would let a test
        that believes it ran a conversation pass without running one.
        """
        remaining = self._transcript.steps[self._cursor :]
        if not remaining:
            raise TranscriptExhaustedError(
                f"{self.name}: nothing left to replay ({self._cursor} steps consumed)"
            )
        return tuple(self.send(step.request) for step in remaining)

    def exchanges(self) -> tuple[Exchange, ...]:
        return tuple(self._exchanges)

    def render(self) -> str:
        """Everything that happened, as canonical JSON. The byte-identity target."""
        return canonical_json(
            {
                "provider": self.name,
                "transcript_digest": self._transcript.digest(),
                "exchanges": [exchange.to_wire() for exchange in self._exchanges],
            }
        )

    def digest(self) -> str:
        """SHA-256 of :meth:`render`."""
        return hashlib.sha256(self.render().encode("utf-8")).hexdigest()

    def __iter__(self) -> Iterator[Exchange]:
        return iter(self._exchanges)


def _decode(wire_json: str, step_name: str) -> Mapping[str, object]:
    """``json.loads`` narrowed to a mapping. A step's payload is an object or a bug."""
    decoded = json.loads(wire_json)
    if not isinstance(decoded, Mapping):
        raise MalformedResponseError(f"transcript step {step_name!r} payload is not a JSON object")
    return decoded


#: Provider identity used by every scripted transcript. Constant so a rendered
#: run never depends on the host, the cwd or the environment.
FAKE_PROVIDER_PROTOCOL: Final[str] = "fake"
