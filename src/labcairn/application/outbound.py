"""The approval-backed outbound consent port.

ADR-0006 §Decision, statement 2: before a request leaves the process,
``CapabilityId.MODEL_REQUEST`` must be evaluated, and the provider layer must
be handed the result. :class:`OutboundApproval` is that hand-off: the object a
caller passes to
:class:`~labcairn.providers.adapter.PydanticAiModelProvider` as its
:class:`~labcairn.providers.consent.OutboundConsent` port, bound to **one**
granted approval.

**It adds no second consent path.** :func:`~labcairn.application.approvals.consume_approval`
is the one function that spends an approval, and it already does the whole of
the work: the capability's arguments are validated against the closed model,
the policy is asked about the resource, the approval's digest is recomputed
from the arguments **as they are right now**, and the ledger moves the row to
``CONSUMED``. This module changes only the shape of the answer — an
:class:`~labcairn.providers.errors.OutboundRefusedError` rather than an
:class:`~labcairn.application.refusal.ApplicationRefusedError` — because the
port belongs to the provider layer, and a caller of ``send`` should not have to
import the application layer's refusal vocabulary to tell a refusal from a
fault.

**Single use is the ledger's, not this object's.** A second ``require``
re-reads the row, sees ``CONSUMED``, and refuses with the layer's own reason.
An expired row is refused by the same check; so is one that was never granted.

**What this module does not do.** It does not ask for an approval, decide what
the approval is for, or send anything. ``use`` is the caller's — for a role run
it is the question's :class:`~labcairn.application.approvals.ApprovalUse` — and
this module never widens it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from labcairn.application.approvals import ApprovalUse, consume_approval
from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import ApplicationRefusedError
from labcairn.core.ids import ApprovalId
from labcairn.core.providers.protocol import ModelRequest
from labcairn.providers.errors import OutboundRefusedError


@dataclass(frozen=True, slots=True)
class OutboundApproval:
    """One granted approval, handed to the provider as its consent port.

    Construct one per request: the approval it names is spent on the first
    :meth:`require`, and the second is refused by the ledger. A caller that
    wants to send twice asks for two approvals; that is the single-use
    guarantee, not a limitation to work around.

    ``at`` is the moment the decision is made, passed rather than read from the
    wall clock so a run is replayable and a test is exact.
    """

    context: ApplicationContext
    approval_id: ApprovalId
    use: ApprovalUse
    at: datetime

    def require(self, request: ModelRequest) -> None:
        """Spend the approval on this request, or refuse the transmission.

        The approval binds the ``use`` — capability, resource and argument
        digest — not the prompt text: what material may leave is the
        application layer's question, and that question is already answered by
        the approval. ``request`` is accepted so the port has the provider's
        own shape; the refusal message names the approval, never the prompt.

        :raises labcairn.providers.errors.OutboundRefusedError: the approval is
            missing, expired, already spent, or does not cover this use. The
            provider raises it before the transport is reached.
        """
        try:
            consume_approval(self.context, self.approval_id, self.use, now=self.at)
        except ApplicationRefusedError as error:
            raise OutboundRefusedError(str(error)) from error
