"""The message projection — derived from the event log, and disposable.

**What this is.** The projection of what the model was told and what it said,
built from a task's event log and from nothing else. It is a *reading* of the
log, not a second copy of the truth.

**Why there is a projection at all.** A reader who wants to know "what did
this task ask the model, where did it send it, and what came back?" should
not have to know the event log's wire format in order to ask. The projection
is that reader's answer, and it is worth exactly as much as the log it came
from — which is the whole of its worth, and the reason it may be thrown away.

**And why it must be disposable.** A projection that is *stored* becomes a
second authority: two records of the same thing, one of which nobody
re-derives, and the pair drifts without anybody deciding that it should. So
this one is derived on demand, holds nothing the log does not, and rebuilds
byte for byte from the log alone. The event log is the authority; this is a
view of it, and ADR-0002's ``ARCHITECTURE.md`` authority rule is what says
so.

**What it holds: digests and counts.** The provider layer's wire form, as
:class:`~labcairn.runtime.model_exchange.ModelExchangePayload` records it.
This tree holds no message list and no model text, so there is nothing here
that could hold text either — a projection that leaked the prompt would
defeat the redaction discipline the wire form exists to keep.

**The name is ADR-0002's.** The ADR calls this the *LLM message projection*;
what it projects here is the exchange record, because the exchange record is
all the tree keeps. The property the name carries — derived, discardable, and
not the task state — is the property this module is built to have.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from labcairn.core.providers.protocol import canonical_json
from labcairn.runtime.event import Event, EventType
from labcairn.runtime.model_exchange import ModelExchangePayload


@dataclass(frozen=True, slots=True)
class ProjectedCall:
    """One model call, as the projection shows it.

    Every field is a copy of something the exchange event said. Nothing here
    is computed, inferred or filled in, which is what makes the projection
    disposable: there is nothing in it that the log does not already hold.
    """

    #: The event's own sequence number: where this call sits in the log.
    seq: int
    provider: str
    model: str
    destination: str
    #: The credential by its fingerprint — never the credential.
    credential_fingerprint: str
    #: The call's cost in USD micros, when the price was known.
    cost_micros: int | None
    #: The provider's own wire records: digests and counts, never text.
    exchanges: tuple[Mapping[str, object], ...]

    def to_wire(self) -> Mapping[str, object]:
        """The projection's own form — a copy of the payload, not a rendering."""
        return {
            "seq": self.seq,
            "provider": self.provider,
            "model": self.model,
            "destination": self.destination,
            "credential_fingerprint": self.credential_fingerprint,
            "cost_micros": self.cost_micros,
            "exchanges": [dict(exchange) for exchange in self.exchanges],
        }


@dataclass(frozen=True, slots=True)
class MessageProjection:
    """A task's model calls, in order, derived from its event log.

    **This is not the task's state.** The task's state is the rows the store
    holds; this is a reading of one part of them. Nothing in the tree writes
    a projection back, and nothing may: a stored projection would be a second
    authority, and the authority rule says there is one.
    """

    task_id: str
    calls: tuple[ProjectedCall, ...]

    def to_wire(self) -> Mapping[str, object]:
        return {
            "task_id": self.task_id,
            "calls": [call.to_wire() for call in self.calls],
        }

    def canonical(self) -> str:
        """The bytes two projections are compared by.

        The same canonical form the provider layer hashes with, so "the same
        log projects to the same bytes" is one well-defined statement rather
        than a property of ``json.dumps``' defaults.
        """
        return canonical_json(self.to_wire())

    def digest(self) -> str:
        """A digest of the projection, for naming one in a report."""
        return hashlib.sha256(self.canonical().encode("utf-8")).hexdigest()


def project_messages(events: Iterable[Event]) -> MessageProjection:
    """Derive the projection from the event log.

    **Only the exchange events, and only what they say.** Every payload is
    read back through the registry's own schema
    (:class:`~labcairn.runtime.model_exchange.ModelExchangePayload`), so the
    projection cannot show a key the reader would refuse — and a payload that
    does not fit is a loud failure here rather than a quiet omission.

    **The events are the only input.** There is no cache, no store read and no
    ambient state: give this function the same events twice and it answers
    the same twice, which is the property that lets the answer be thrown away.
    """
    task_id = ""
    calls: list[ProjectedCall] = []
    for event in events:
        if not task_id:
            task_id = str(event.task_id)
        if event.type is not EventType.MODEL_EXCHANGED:
            continue
        payload = ModelExchangePayload.model_validate(event.payload)
        calls.append(
            ProjectedCall(
                seq=event.seq,
                provider=payload.provider,
                model=payload.model,
                destination=payload.destination,
                credential_fingerprint=payload.credential_fingerprint,
                cost_micros=payload.cost_micros,
                exchanges=tuple(dict(exchange) for exchange in payload.exchanges),
            )
        )
    return MessageProjection(task_id=task_id, calls=tuple(calls))
