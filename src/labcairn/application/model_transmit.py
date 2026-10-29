"""The two gates a model request has to pass, and the order they run in.

**What this module is.** LC-P2-06 T02: the path a request to a model
takes, and the two independent checks it has to pass.

**The two gates, and why there are two.** A model request carries
material. Therefore **two** independent checks run, and passing one does
not imply the other (ADR-0015 D3):

1. **The operation approval** for ``model.request`` — the existing
   machinery, the existing single-use guarantee, unchanged. It says *this
   operation may run once, now*.
2. **The ``external_transmit`` grant** for the material in the request —
   the new check, and the one that names the **destination**. It says
   *this material may go to this place, for this purpose*.

**The gate is one, the other is the other.** Merging them would make the
design's default-deny for transmission and training unrepresentable: a
single approval could not tell "you may run this operation" from "you may
send this material anywhere".

**And the order is load-bearing.** **The transmit check runs *before* the
approval is consumed.** A request refused for want of a grant therefore
leaves the approval **unspent**, and a person can fix the grant and try
again. Asking is not spending — the existing consent layer already holds
to that, and a refusal here has to hold to it too, or a person would have
to ask for a new approval every time the grant was missing.

**Why this is a separate module from the permission check.** The
permission check lives in :mod:`labcairn.security.permissions` and answers one
question about one material. **This module is the path**, and the path is
what the application's operations call: it names the gate, it names the
order, and it carries the destination. Keeping the two apart is what stops
the path from growing a second copy of the permission logic.

**What this module does not do.** It does not call a model, spend money,
or decide who may be granted what. **The policy of granting is a person's**;
this is the mechanism that enforces it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from labcairn.security.permissions import ConsentDecision, Grant, may_use

__all__ = [
    "TransmitCheck",
    "check_transmit",
    "transmit_refusal_for",
]


@dataclass(frozen=True)
class TransmitCheck:
    """The result of the transmit gate.

    **``decision`` is the consent layer's own answer**, not a
    re-derivation of it, so the two gates cannot disagree about why.

    **``reason`` is the consent layer's own string**, because a refusal
    reason is not re-spelled at every call site: that is how one
    vocabulary becomes two.
    """

    #: Whether the material may go to this destination.
    permitted: bool
    #: The consent layer's decision, whole.
    decision: ConsentDecision
    #: The destination that was asked for.
    destination: str
    #: The subject the material belongs to.
    subject_ref: str
    #: A sentence for a person, naming the fault and the remedy.
    detail: str

    @property
    def reason(self) -> str | None:
        """The machine-readable reason, or ``None`` when permitted."""
        if self.decision.reason is None:
            return None
        return self.decision.reason.value


def check_transmit(
    grants: list[Grant],
    *,
    subject_ref: str,
    destination: str,
    material_ref: str | None = None,
    purpose: str = "transmit",
    at: datetime,
) -> TransmitCheck:
    """Check whether material may go to a destination, before anything spends.

    **This is the first gate, and it is the one that runs first.** It asks
    the consent layer the question ADR-0015 D3 states: *"is this material
    permitted to leave the machine, for this purpose, to this
    destination?"*

    **And it names the destination in the refusal**, because "the material
    is not permitted" is true and unhelpful, while "the grant names
    provider A and you asked for provider B" is an answer a person can act
    on.
    """
    decision = may_use(
        grants,
        permission="external_transmit",
        purpose=purpose,
        subject_ref=subject_ref,
        material_ref=material_ref,
        destination=destination,
        at=at,
    )
    return TransmitCheck(
        permitted=decision.allowed,
        decision=decision,
        destination=destination,
        subject_ref=subject_ref,
        detail=decision.detail,
    )


def transmit_refusal_for(check: TransmitCheck) -> str | None:
    """The machine-readable reason a request was refused, or ``None``.

    **A thin function with a purpose**: the caller wants one string it can
    branch on, and it must be **the same string** the consent layer uses —
    so that a refusal reason is not re-spelled at every call site.
    """
    return check.reason
