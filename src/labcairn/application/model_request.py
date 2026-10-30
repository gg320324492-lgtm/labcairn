"""The bridge between the consent layer and the provider layer.

**What this module is.** LC-P2-01 T01/T02: the call site that turns "a
model may be asked" into an actual ask, under the gates the repository
already has, and records what came back. **It builds no gate and spends
no approval of its own** — the material-purpose grant is consulted
through :func:`labcairn.application.model_transmit.transmit_request`,
whose order is the property this path inherits rather than
re-implements: **the transmit check runs first, and only a permitted
request consumes the approval.** A request refused for want of a grant
leaves the approval unspent, and a request refused for want of an
approval sends nothing.

**And this is not a second consent path.** The approval's digest is
recomputed at the moment of use over the capability's canonical
arguments, exactly as the consent layer has always done it; this module
hands the caller's :class:`ApprovalUse` straight through and adds
nothing. A bridge that minted its own approval, or widened one, would
be an authorisation bypass wearing a convenience's clothes.

**What came back is recorded, in the provider layer's own words.** The
invocation's exchange records are the wire form the provider layer
already shapes — digests and counts, no text — and they land in the
event log beside the fact of the call, in one transaction. The
credential is named by its fingerprint and by nothing else: there is no
field in the record a plaintext key could occupy.

**What this module does not do.** It does not build a provider, read a
configuration, or decide what the model is asked — the caller's
``send`` is the invocation, and it answers with a
:class:`ModelInvocation` because a call whose shape nobody recorded is
a call nobody can audit. The roles (LC-P2-12) call *this* path, not
the consent layer and not the provider layer directly.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from labcairn.application.approvals import ApprovalUse
from labcairn.application.context import ApplicationContext
from labcairn.application.model_transmit import TransmitCheck, transmit_request
from labcairn.core.ids import ApprovalId
from labcairn.runtime.model_exchange import emit_model_exchanged
from labcairn.security.permissions import Grant


@dataclass(frozen=True)
class ModelInvocation:
    """One call's answer, and the record a reader will be shown.

    The exchanges are the provider layer's wire records — what was sent
    as a digest, what came back as usage — and they are the *only*
    thing this path persists about the call's contents. A plaintext key
    has no field to live in, and the payload's shape is the proof.
    """

    answer: str
    provider: str
    model: str
    exchanges: tuple[Mapping[str, object], ...]
    credential_fingerprint: str
    cost_micros: int | None = None


@dataclass(frozen=True)
class ModelAnswer:
    """What came back, with the consent it came back under.

    ``check`` is the transmit gate's own record — the decision that
    permitted the material to leave, carried beside the answer so a
    reader can see both without re-deriving either.
    """

    answer: str
    check: TransmitCheck
    destination: str
    provider: str
    model: str
    exchange_event_id: str


def request_model(
    context: ApplicationContext,
    approval_id: ApprovalId,
    grants: Sequence[Grant],
    *,
    use: ApprovalUse,
    subject_ref: str,
    destination: str,
    material_ref: str | None = None,
    purpose: str = "transmit",
    at: datetime,
    send: Callable[[], ModelInvocation],
) -> ModelAnswer:
    """Ask the model, under the two gates, in their order, and record the call.

    The material gate runs first; only a permitted request consumes the
    approval; the caller's ``send`` — the provider invocation — is the
    only thing that reaches the wire, reached at all only after both
    gates have permitted; and the exchange record lands in the event
    log in the same unit of work, so the fact and its record cannot
    come apart.

    :raises ApplicationRefusedError: the grant does not cover the
        material, the destination or the purpose (and the approval stays
        unspent), or the approval cannot be consumed.
    """
    check = transmit_request(
        context,
        approval_id,
        list(grants),
        use=use,
        subject_ref=subject_ref,
        destination=destination,
        material_ref=material_ref,
        purpose=purpose,
        at=at,
    )
    invocation = send()
    with context.store.unit(context.task_id) as work:
        event = emit_model_exchanged(
            work,
            provider=invocation.provider,
            model=invocation.model,
            destination=destination,
            exchanges=[dict(exchange) for exchange in invocation.exchanges],
            credential_fingerprint=invocation.credential_fingerprint,
            cost_micros=invocation.cost_micros,
        )
    return ModelAnswer(
        answer=invocation.answer,
        check=check,
        destination=destination,
        provider=invocation.provider,
        model=invocation.model,
        exchange_event_id=str(event.event_id),
    )
