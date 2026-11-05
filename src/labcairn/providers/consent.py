"""The outbound consent port: the permission decision the provider is handed.

ADR-0006 §Decision, statement 2:

    *Before a request leaves the process, ``CapabilityId.MODEL_REQUEST`` must
    be evaluated. The evaluation belongs to the permission layer; what the
    provider layer owes is that it cannot send without having been handed the
    result.*

This module is that "handed the result", as a type. It imports nothing from
:mod:`labcairn.security` and names no permission capability: the provider layer
asks one question — *may this request leave?* — and the answer is carried by an
object it did not construct. The two vocabularies stay disjoint (ADR-0006
statement 1); what crosses the boundary is a decision, not a vocabulary.

The refusal is the provider layer's own
:class:`~labcairn.providers.errors.OutboundRefusedError`
(``FailureKind.OUTBOUND_REFUSED`` — *decided before the request goes out*), so
a caller handles an ungranted request like any other pre-flight refusal, and
the transport is never reached.

Why the port is a required constructor argument
-----------------------------------------------
A defaulted port would be a defaulted permission: ``consent=None`` means the
provider sends without a decision, which is exactly the defect ADR-0006
describes. :class:`~labcairn.providers.adapter.PydanticAiModelProvider` is
therefore unbuildable without one, and a caller that has no approval to hand
over has no provider to send with.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from labcairn.core.providers.protocol import ModelRequest


@runtime_checkable
class WireAuthorizedConsent(Protocol):
    """A consent port whose single-use approval is spent at the wire.

    The ordinary :class:`OutboundConsent` is asked immediately before the
    provider builds its request and spends the approval there. A transport
    fault after that point has already consumed it even though nothing left
    the process. A port implementing this protocol keeps the approval granted
    until a measurable provider response comes back. The wire sniffer then
    calls :meth:`authorize_wire`, and the provider checks that the callback
    really ran before it accepts the response. A response without a spent
    approval is refused, so no unverifiable call can become an artefact.
    """

    def require(self, request: ModelRequest) -> None:
        """Verify and reserve the approved decision before the request."""
        ...

    def authorize_wire(self) -> None:
        """Spend the approval only after a measurable response came back.

        :raises labcairn.providers.errors.OutboundRefusedError: the approval is
            missing, refused, expired or already spent. No unverified response
            may become a run artefact.
        """
        ...

    def release_wire(self) -> None:
        """Release a reservation whose request never reached the wire."""
        ...


@runtime_checkable
class OutboundConsent(Protocol):
    """What the provider layer is handed before a request may leave.

    An implementation is supplied by the layer that owns the permission
    decision — :class:`labcairn.application.outbound.OutboundApproval` is the
    approval-backed one — and is called by
    :meth:`~labcairn.providers.adapter.PydanticAiModelProvider.send` **after**
    the local pre-flights and **immediately before** the transport call.
    """

    def require(self, request: ModelRequest) -> None:
        """Return if *request* may leave the process.

        :raises labcairn.providers.errors.OutboundRefusedError: the permission
            decision is missing, refused, expired or already spent. The
            request did not leave.
        """
        ...
