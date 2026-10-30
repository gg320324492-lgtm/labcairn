"""The bridge between the consent layer and the provider layer.

**What this module is.** LC-P2-01 T01: the call site that turns "a model
may be asked" into an actual ask, under the gates the repository already
has. **It builds no gate and spends no approval of its own** — the
material-purpose grant is consulted through
:func:`labcairn.application.model_transmit.transmit_request`, whose
order is the property this path inherits rather than re-implements:
**the transmit check runs first, and only a permitted request consumes
the approval.** A request refused for want of a grant leaves the
approval unspent, and a request refused for want of an approval sends
nothing.

**And this is not a second consent path.** The approval's digest is
recomputed at the moment of use over the capability's canonical
arguments, exactly as the consent layer has always done it; this module
hands the caller's :class:`ApprovalUse` straight through and adds
nothing. A bridge that minted its own approval, or widened one, would
be an authorisation bypass wearing a convenience's clothes.

**What this module does not do.** It does not build a provider, read a
configuration, or decide what the model is asked — the caller's
``send`` is the invocation, and LC-P2-01 T02 is where the product's own
provider construction fills it in. The roles (LC-P2-12) call *this*
path, not the consent layer and not the provider layer directly.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from labcairn.application.approvals import ApprovalUse
from labcairn.application.context import ApplicationContext
from labcairn.application.model_transmit import TransmitCheck, transmit_request
from labcairn.core.ids import ApprovalId
from labcairn.security.permissions import Grant


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
    send: Callable[[], str],
) -> ModelAnswer:
    """Ask the model, under the two gates, in their order.

    The material gate runs first; only a permitted request consumes the
    approval; and the caller's ``send`` — the provider invocation — is
    the only thing that reaches the wire, reached at all only after both
    gates have permitted.

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
    return ModelAnswer(answer=send(), check=check, destination=destination)
