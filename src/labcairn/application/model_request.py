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

from pydantic import ValidationError

from labcairn.application.approvals import ApprovalUse
from labcairn.application.context import ApplicationContext
from labcairn.application.model_transmit import TransmitCheck, transmit_request
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.core.ids import ApprovalId
from labcairn.core.schema import LabCairnModel
from labcairn.providers.budget import RunBudget, preflight_check
from labcairn.providers.capabilities import (
    Capability,
    CapabilityOutcome,
    ProviderCapabilities,
)
from labcairn.providers.ledger import LedgerSnapshot
from labcairn.runtime.model_exchange import emit_model_exchanged
from labcairn.security.permissions import Grant


@dataclass(frozen=True)
class ModelInvocation:
    """One call's answer, and the record a reader will be shown.

    The exchanges are the provider layer's wire records — what was sent
    as a digest, what came back as usage — and they are the *only*
    thing this path persists about the call's contents. A plaintext key
    has no field to live in, and the payload's shape is the proof.

    ``structured`` is what came back in a schema's shape, when the call
    was asked for one — the document the provider returned, before this
    path has judged it. It is **not** the answer: until it decodes, it
    is nothing the system will state.
    """

    answer: str
    provider: str
    model: str
    exchanges: tuple[Mapping[str, object], ...]
    credential_fingerprint: str
    cost_micros: int | None = None
    structured: Mapping[str, object] | None = None


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


#: The two channels a schema's output can arrive through. Either one
#: licensed is enough; neither licensed is a refusal.
_STRUCTURED_CHANNELS: tuple[Capability, ...] = (
    Capability.STRUCTURED_OUTPUT_NATIVE,
    Capability.STRUCTURED_OUTPUT_PROMPTED,
)


def _require_schema_ability(capabilities: ProviderCapabilities | None) -> None:
    """Refuse a schema request the provider's probe does not license.

    **Before the gate and before the wire.** A provider that cannot
    produce a schema's output is blocked from that request, rather than
    being asked to try — so the check runs where its refusal costs the
    person nothing: no approval is consumed and no request is sent.

    The two reasons are distinguished because their remedies differ. A
    channel whose outcome is ``UNVERIFIED`` was never asked — the remedy
    is a probe, which is cheap and changes the decision for free — so it
    is ``MODEL_SCHEMA_UNPROBED``. A channel the probe asked and saw fail
    is ``MODEL_SCHEMA_UNSUPPORTED``, and the remedy is a different
    provider or a different output shape. This is the providers layer's
    own reading of ``UNVERIFIED`` — treated as not licensed — kept, with
    the *naming* of the difference this layer's vocabulary is for.
    """
    if capabilities is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.MODEL_SCHEMA_UNPROBED,
            "no capability probe has run for this provider; a schema request"
            " is refused rather than sent on the chance the schema comes back",
        )
    outcomes = {
        capability: capabilities.outcome_for(capability) for capability in _STRUCTURED_CHANNELS
    }
    if any(outcome.usable for outcome in outcomes.values()):
        return
    why = "; ".join(
        f"{capability.value}: {capabilities.unsupported_reason.get(capability, outcome.value)}"
        for capability, outcome in outcomes.items()
    )
    if any(outcome is CapabilityOutcome.UNVERIFIED for outcome in outcomes.values()):
        raise ApplicationRefusedError(
            ApplicationRefusal.MODEL_SCHEMA_UNPROBED,
            f"no probe has licensed a structured-output channel for this provider ({why})",
        )
    raise ApplicationRefusedError(
        ApplicationRefusal.MODEL_SCHEMA_UNSUPPORTED,
        f"the probe licensed neither structured-output channel ({why})",
    )


def _decode(
    invocation: ModelInvocation, output_schema: type[LabCairnModel]
) -> Mapping[str, object]:
    """Judge what came back against the schema it was asked for.

    An empty result is not a result, and an output that cannot be
    decoded is a refusal **naming what was expected** — never silently
    turned into an answer. The call's own record has already landed; a
    refusal here unstates nothing about the wire.
    """
    structured = invocation.structured
    if structured is None or not structured:
        raise ApplicationRefusedError(
            ApplicationRefusal.MODEL_ANSWER_EMPTY,
            "the call came back with nothing in the schema's shape;"
            " an empty result is not a result",
        )
    try:
        output_schema.model_validate(dict(structured))
    except ValidationError as error:
        failure = error.errors()[0]
        location = ".".join(str(part) for part in failure.get("loc", ())) or "the document"
        raise ApplicationRefusedError(
            ApplicationRefusal.MODEL_ANSWER_UNDECODABLE,
            f"expected a {output_schema.__name__} and the answer is not one:"
            f" {location} — {failure['msg']}",
        ) from error
    return structured


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
    budget: RunBudget | None = None,
    ledger: LedgerSnapshot | None = None,
    capabilities: ProviderCapabilities | None = None,
    output_schema: type[LabCairnModel] | None = None,
) -> ModelAnswer:
    """Ask the model, under the two gates, in their order, and record the call.

    The budget's preflight runs first, because a ceiling that cannot be
    measured fails closed and neither failure should cost the person
    their approval; **a schema request the provider's probe does not
    license is refused next, at the same price — nothing**; the material
    gate runs next, and only a permitted request consumes the approval;
    the caller's ``send`` — the provider invocation — is the only thing
    that reaches the wire, reached at all only after every gate has
    permitted; and the exchange record lands in the event log in the
    same unit of work, so the fact and its record cannot come apart.

    **What came back is judged, not accepted.** When an
    ``output_schema`` was asked for, the answer is validated against it:
    an empty result is not a result, and an output that cannot be
    decoded is a refusal whose message names what was expected. The
    refusal does not unstate the call — the wire carried the request,
    the approval is spent, and the exchange record stays — but nothing
    undecodable becomes an answer, and illegal output is never silently
    turned into evidence.

    A call that was sent and did not answer raises the provider's own
    error and **records nothing as success**: no exchange event is
    written, the approval stays spent — the wire may have carried the
    request — and the doubt is a person's to reconcile, not the path's
    to paper over.

    :raises ApplicationRefusedError: the grant does not cover the
        material, the destination or the purpose (and the approval stays
        unspent), the approval cannot be consumed, or the answer does
        not satisfy the schema it was asked for.
    :raises BudgetEnforcementUnavailableError: a set ceiling cannot be
        measured against this call — an unpriced model under a cost
        ceiling, a provider that reports no usage under a token one.
    """
    if budget is not None:
        preflight_check(budget, ledger if ledger is not None else LedgerSnapshot())
    if output_schema is not None:
        _require_schema_ability(capabilities)
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
    if output_schema is not None:
        _decode(invocation, output_schema)
    return ModelAnswer(
        answer=invocation.answer,
        check=check,
        destination=destination,
        provider=invocation.provider,
        model=invocation.model,
        exchange_event_id=str(event.event_id),
    )
