"""One model exchange, recorded — what was asked, what came back, under which consent.

**What this module is.** LC-P2-01 T02: the annotation the model-call
path leaves in the event log. The record is the provider layer's own
wire form — :class:`~labcairn.providers.adapter.ExchangeRecord`'s —
which carries digests and counts and **no text**: what was sent is a
prompt digest, what came back is a usage figure, and what left the box
is the outbound disclosure the redaction pass already shaped. A record
that is safe to persist by construction is a record nobody has to
remember to redact.

**And the credential is a fingerprint, never a value.** The payload
names the credential by its fingerprint — enough to answer "was this
the same key?" and not enough to *be* the key. A plaintext API key is
written nowhere, and the payload's own field is the proof: there is no
field to put one in.
"""

from __future__ import annotations

from pydantic import Field

from labcairn.core.schema import LabCairnModel
from labcairn.runtime.event import Event, EventType, register_payload_schema
from labcairn.runtime.trajectory import EventWriter


class ModelExchangePayload(LabCairnModel):
    """What a ``model_exchanged`` event says.

    The exchanges are the provider layer's wire records, verbatim: each
    one names its step, its prompt digest, its outbound disclosure, its
    attempt count and its usage. The destination is named because the
    consent that permitted the call names it, and a record of the call
    that omits where it went is a record of a call nobody can check.
    """

    #: The provider the call went to, as the configuration named it.
    provider: str = Field(min_length=1)
    #: The model the call asked for, as the configuration named it.
    model: str = Field(min_length=1)
    #: The destination the material gate permitted.
    destination: str = Field(min_length=1)
    #: The exchange records, in the provider layer's wire form —
    #: digests and counts, never text.
    exchanges: list[dict[str, object]] = Field(min_length=1)
    #: The credential by its fingerprint — the same key or not, and
    #: never the key itself.
    credential_fingerprint: str = Field(min_length=1)
    #: The call's cost in USD micros, when the price was known. A cost
    #: that cannot be measured is recorded as absent, not as zero —
    #: an absent cost is an open question, a zero is an answer.
    cost_micros: int | None = Field(default=None, ge=0)


register_payload_schema(EventType.MODEL_EXCHANGED, ModelExchangePayload)


def emit_model_exchanged(
    work: EventWriter,
    *,
    provider: str,
    model: str,
    destination: str,
    exchanges: list[dict[str, object]],
    credential_fingerprint: str,
    cost_micros: int | None,
) -> Event:
    """Record one model exchange, in the transaction its rows land in.

    *work* is the unit of work the call's records are written in; the
    event belongs to the same transaction, so the record and the fact
    land together or neither does.
    """
    payload = ModelExchangePayload(
        provider=provider,
        model=model,
        destination=destination,
        exchanges=exchanges,
        credential_fingerprint=credential_fingerprint,
        cost_micros=cost_micros,
    )
    return work.emit(EventType.MODEL_EXCHANGED, payload=payload.model_dump(mode="json"))
