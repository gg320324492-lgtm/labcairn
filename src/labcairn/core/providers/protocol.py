"""The provider seam and the minimal request/response shapes LC-P1-01 needs.

``ModelProvider`` is the seam ADR-0002 §A3 requires:

    *"the contracts below are deliberately shaped so a hand-rolled adapter can
    be dropped in behind ``ModelProvider`` without changing callers."*

What is on it, and what is deliberately not
-------------------------------------------
The Protocol declares exactly two members, and both are real today:

``name``
    An identifier recorded alongside every exchange. Stable, not secret. This
    is also the extension point a future adapter overrides to say "this is
    ``anthropic:claude-opus-5``", which is how LC-P1-03 will key its persisted
    capability-probe cache off ``(endpoint, model, protocol)``.

``send``
    One request in, one response out. Synchronous. The fake returns the same
    thing twice for the same request, forever.

Not on it, and why: LC-P1-01 has no capability probe, no budget and no
cancellation (amendment C-3). A Protocol member nobody implements is a contract
the fake would have to fake too — and a faked ``probe_capabilities()`` returning
"looks fine" is exactly the dishonest detection ADR-0002 §A1 rejects in
pydantic-ai's ``ModelProfile``. So LC-P1-03 will *add* members to this Protocol
and *add* them to its adapters; it will not have to reshape it, and no caller
that only calls :meth:`~ModelProvider.send` changes. Adding to a Protocol is
source-compatible for structural subtyping in the direction that matters here:
new members restrict who can satisfy it, so LC-P1-03 lands them together.

The one semantic decision worth naming: **``Unknown`` is for quantities, not for
responses.** A response whose ``text`` is missing or is not a string raises
:class:`MalformedResponseError` rather than degrading to ``""`` — there is no
honest reading of "the provider returned something we could not parse" as "the
provider said nothing", and silently substituting an empty string would let a
broken adapter look like a quiet one. Only usage *fields* are tri-state.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Protocol, Self, runtime_checkable

from labcairn.core.providers.usage import (
    Known,
    Unknown,
    UnknownReason,
    UsageValue,
    merge,
)

#: Usage fields a provider response may carry. Closed: an unlisted key in a
#: ``usage`` block is ignored rather than guessed at, so a new upstream field
#: cannot be mistaken for one of ours.
USAGE_FIELDS: Final[tuple[str, ...]] = ("input_tokens", "output_tokens")


class MalformedResponseError(ValueError):
    """A provider payload that is not a response at all.

    Distinct from :class:`~labcairn.core.providers.usage.UnmeasuredQuantityError`:
    that one means "we could not measure this number", this one means "we
    could not read what came back". Neither is ever reported as a zero.
    """


@dataclass(frozen=True, slots=True)
class ModelRequest:
    """One model request. Minimal on purpose.

    ``prompt`` and the names of the ``tools`` offered are all LC-P1-01 needs to
    make replay meaningful. LC-P1-03 grows this into a full message list, and
    that growth does not disturb :meth:`~ModelProvider.send`'s signature because
    the protocol dispatches on the type, not on the field count.
    """

    prompt: str
    tools: tuple[str, ...] = ()

    def to_wire(self) -> Mapping[str, object]:
        return {"prompt": self.prompt, "tools": list(self.tools)}


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A tool call the model asked for.

    ``arguments_json`` is the canonical JSON *text* of the arguments rather than
    a ``Mapping``. A frozen dataclass holding a mutable dict is a hashing
    accident waiting to happen, and a canonical string is both hashable and
    byte-comparable — which is what the byte-identity test needs.
    """

    name: str
    arguments_json: str

    @classmethod
    def from_wire(cls, payload: object) -> ToolCall:
        entry = _require_mapping(payload, "tool_calls[]")
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise MalformedResponseError(f"tool call has no usable name: {payload!r}")
        return cls(name=name, arguments_json=canonical_json(entry.get("arguments", {})))

    def to_wire(self) -> Mapping[str, object]:
        return {"name": self.name, "arguments": json.loads(self.arguments_json)}


@dataclass(frozen=True, slots=True)
class UsageReport:
    """The usage fields of one response, each independently tri-state.

    Per-field rather than whole-block: a provider may well report
    ``input_tokens`` and omit ``output_tokens``. Collapsing that to one verdict
    for the block would throw away real measurements.
    """

    input_tokens: UsageValue
    output_tokens: UsageValue

    @property
    def total_tokens(self) -> UsageValue:
        """Total across the fields, via :func:`~labcairn.core.providers.usage.merge`.

        Uses ``merge``, not ``+``: a half-measured response yields an unknown
        total rather than the measured half dressed up as the whole.
        """
        return merge(self.input_tokens, self.output_tokens)

    @classmethod
    def from_wire(cls, payload: Mapping[str, object]) -> UsageReport:
        """Parse the ``usage`` block of a provider payload.

        Two failure kinds, deliberately distinct (see
        :class:`~labcairn.core.providers.usage.UnknownReason`):

        * block absent, ``null``, or not an object ⇒ every field
          ``Unknown(PROVIDER_OMITTED)``. This is the row ADR-0002 cares about:
          upstream turns this into all-zeros.
        * field absent or ``null`` inside a present block ⇒ that field alone is
          ``Unknown(PROVIDER_OMITTED)``; its siblings keep their measurements.
        * field present but not a usable non-negative integer (``"12"``,
          ``True``, ``-3``, an object) ⇒ ``Unknown(EXTRACTION_FAILED)``.

        The non-negative check lives here and not on :class:`~labcairn.core.providers.usage.Known`
        because "a provider's token count is a non-negative integer" is a true
        statement about the *wire format*. Whether some other quantity may be
        signed is LC-P1-03's business.
        """
        block = payload.get("usage")
        if not isinstance(block, Mapping):
            omitted = Unknown(reason=UnknownReason.PROVIDER_OMITTED)
            return cls(input_tokens=omitted, output_tokens=omitted)
        values: dict[str, UsageValue] = {}
        for field in USAGE_FIELDS:
            raw = block.get(field)
            if raw is None:
                # Absent and explicit null are the same fact: nothing came back.
                values[field] = Unknown(reason=UnknownReason.PROVIDER_OMITTED)
            elif isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
                # bool is an int subclass; a provider saying `true` for a token
                # count is malformed, not a measurement of 1.
                values[field] = Unknown(reason=UnknownReason.EXTRACTION_FAILED)
            else:
                values[field] = Known(raw)
        return cls(
            input_tokens=values["input_tokens"],
            output_tokens=values["output_tokens"],
        )

    def to_wire(self) -> Mapping[str, object]:
        return {field: getattr(self, field).to_wire() for field in USAGE_FIELDS}


@dataclass(frozen=True, slots=True)
class ModelResponse:
    """One model response, plus when the provider observed it.

    ``observed_at`` is injected by the provider, never read from the system
    clock here, which is what lets :class:`~labcairn.core.providers.fake.FakeProvider`
    replay byte-identically under a frozen clock.
    """

    text: str
    tool_calls: tuple[ToolCall, ...]
    usage: UsageReport
    observed_at: datetime
    transcript_step: str

    @classmethod
    def from_wire(
        cls, payload: Mapping[str, object], *, transcript_step: str, observed_at: datetime
    ) -> Self:
        """Build a response from a raw provider payload.

        This is the same parsing a real adapter performs; the fake uses it so a
        scripted transcript exercises the production code path rather than a
        shortcut around it.
        """
        text = payload.get("text")
        if not isinstance(text, str):
            raise MalformedResponseError(f"response text is missing or not a string: {payload!r}")
        raw_calls = payload.get("tool_calls", [])
        if not isinstance(raw_calls, list):
            raise MalformedResponseError(f"tool_calls is not a list: {payload!r}")
        return cls(
            text=text,
            tool_calls=tuple(ToolCall.from_wire(item) for item in raw_calls),
            usage=UsageReport.from_wire(payload),
            observed_at=observed_at,
            transcript_step=transcript_step,
        )

    def to_wire(self) -> Mapping[str, object]:
        return {
            "text": self.text,
            "tool_calls": [call.to_wire() for call in self.tool_calls],
            "usage": self.usage.to_wire(),
            "observed_at": self.observed_at.isoformat(),
            "transcript_step": self.transcript_step,
        }


@runtime_checkable
class ModelProvider(Protocol):
    """The seam. See the module docstring for what is deliberately absent.

    :class:`~labcairn.core.providers.fake.FakeProvider` satisfies it structurally;
    ``tests/test_fake_provider_isolation.py`` asserts that rather than trusting
    it, so a signature drift shows up as a test failure and not as a silent
    ``NotImplementedError`` at LC-P1-03's first real call.
    """

    @property
    def name(self) -> str:
        """Stable, non-secret identifier recorded with every exchange."""
        ...

    def send(self, request: ModelRequest) -> ModelResponse:
        """One request, one response. Deterministic for a given implementation."""
        ...


def canonical_json(value: object) -> str:
    """The project's canonical JSON form: sorted keys, no incidental whitespace.

    Used both for hashing and for the byte-identity comparison, so "the same
    transcript renders the same bytes" is a single well-defined statement rather
    than a property of ``json.dumps`` defaults.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _require_mapping(payload: object, where: str) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise MalformedResponseError(f"{where} is not an object: {payload!r}")
    return payload
