"""The approval-backed outbound consent port.

ADR-0006 §Decision, statement 2: before a request leaves the process,
``CapabilityId.MODEL_REQUEST`` must be evaluated, and the provider layer must
be handed the result. :class:`OutboundApproval` is that hand-off: the object a
caller passes to
:class:`~labcairn.providers.adapter.PydanticAiModelProvider` as its
:class:`~labcairn.providers.consent.OutboundConsent` port, bound to **one**
granted approval.

**A capability probe is one of these callers too.** ADR-0006 statement 3 says
a probe sends requests, so a probe requires consent "in the same way, and for
the same reason, as any other outbound request". :func:`probe_use` is that
request's use and :class:`ProbeConsent` is the port a probe session is handed;
both are here rather than in a second module, because there is one gate.

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

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from labcairn.application import consent
from labcairn.application.approvals import ApprovalUse, consume_approval
from labcairn.application.context import TASK_AREA_ROOT, ApplicationContext
from labcairn.application.refusal import ApplicationRefusedError
from labcairn.core.ids import ApprovalId
from labcairn.core.providers.protocol import ModelRequest
from labcairn.db.repository import list_approvals
from labcairn.providers.capabilities import Capability
from labcairn.providers.errors import OutboundRefusedError
from labcairn.providers.probe import ProbeRequest
from labcairn.runtime.operation import ApprovalState, compute_args_digest
from labcairn.security.capabilities import CapabilityId, ModelRequestArgs


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


# --------------------------------------------------------------------------- #
# the probe's use
# --------------------------------------------------------------------------- #

#: The resource key a capability probe's request addresses.
#:
#: **A synthetic key in the task's own area, and that is the point.** A probe
#: addresses no source file — the material it sends is its own prompt — so it
#: must not borrow a file it does not read: naming one would tell the policy
#: that the probe reads the user's material, and would let a rule written about
#: one source file cover a probe of an endpoint. The key is the probe's own, in
#: the output root, and a policy that wants to say something about probing can
#: name it.
PROBE_RESOURCE_KEY: str = "probes/capability"

#: The purpose a probe's request states: what the request is for.
PROBE_PURPOSE: str = "capability.probe"


def probe_use(
    context: ApplicationContext,
    *,
    provider: str,
    model: str,
    request: ProbeRequest,
) -> ApprovalUse:
    """What a probe's approval is spent on.

    **A probe's use is an ordinary ``model.request`` use.** ADR-0006 statement
    3 says a probe requires consent "in the same way, and for the same reason,
    as any other outbound request", so the capability is the one every
    outbound request uses, the argument model is the same closed one, and the
    spend is the same :func:`~labcairn.application.approvals.consume_approval`.
    What differs is only *what is transmitted*, and that is spelled here:

    * the **excerpts** are the probe's own prompt — the fixed literal the probe
      sends. A probe carries no user material, and the digest covers these
      words, so the approval is a consent to send *these* words to *this*
      endpoint, and not a consent to send anything to it;
    * the **purpose** says what the request is for: a capability probe;
    * the **resource** is :data:`PROBE_RESOURCE_KEY`, in the task's own area.

    The argument digest therefore binds the provider, the model, the words and
    the purpose. An approval for one endpoint's probe does not authorise
    another's, and an approval for one probe's words does not authorise
    another's.
    """
    resource = context.resource_in(TASK_AREA_ROOT, PROBE_RESOURCE_KEY)
    return ApprovalUse(
        capability=CapabilityId.MODEL_REQUEST,
        arguments=ModelRequestArgs(
            provider=provider,
            model=model,
            path=resource.declared_key,
            excerpts=(request.text,),
            purpose=PROBE_PURPOSE,
        ).model_dump(),
        root_id=TASK_AREA_ROOT,
        resource_key=PROBE_RESOURCE_KEY,
    )


def _the_digest(context: ApplicationContext, use: ApprovalUse) -> str:
    """The digest an approval covering this use must carry.

    **Computed the way the grant computed it.** :func:`request_approval`
    evaluates the use, takes the validated arguments' canonical form, and
    digests them with the resource's resolved key; this does the same, so an
    approval is recognised by the digest it was granted with rather than by
    anything it says about itself.

    :raises labcairn.application.refusal.ApplicationRefusedError: the policy
        denied the request, so there is nothing to cover.
    """
    resource = context.resource_in(use.root_id, use.resource_key)
    authorisation = consent.evaluate(
        context,
        capability=use.capability,
        arguments=use.arguments,
        resource=resource,
    )
    return compute_args_digest(
        task_id=context.task_id,
        capability=use.capability.value,
        resource_key=resource.resolved_key,
        args=authorisation.digest_arguments(),
        depends_on=use.depends_on,
    )


class ProbeConsent:
    """The approvals one probe session spends, one per request it makes.

    **A probe session is several requests and the ledger is single-use.** The
    approval a request names is spent on it, so one approval cannot cover a
    session: a probe of three capabilities needs three approvals. This port
    holds one approval per request and spends each on the request it covers.

    **The binding is by the words the request carries.** An approval covers a
    request whose prompt is the text its use names, and the ledger then checks
    the approval's own digest against the arguments as they are now — so a
    grant for one text cannot be spent on another, and the refusal names the
    approval rather than the text.

    This is the same port the provider layer is handed for a run
    (:class:`~labcairn.providers.consent.OutboundConsent`), and the refusal is
    the same error
    (:class:`~labcairn.providers.errors.OutboundRefusedError`) with the same
    vocabulary.
    """

    __slots__ = ("_pending",)

    def __init__(
        self,
        entries: Sequence[tuple[Capability, ApprovalUse, OutboundApproval | None]],
    ) -> None:
        """``(capability, use, approval)`` for each request, in the order made.

        An approval of ``None`` is a request nobody has agreed to: the port
        refuses it by name, so the operator is told which probe was not
        allowed rather than that a request failed.
        """
        pending: dict[str, list[_PendingRequest]] = {}
        for capability, use, approval in entries:
            pending.setdefault(_the_text(use), []).append(
                _PendingRequest(capability=capability, use=use, approval=approval)
            )
        self._pending = pending

    def require(self, request: ModelRequest) -> None:
        """Spend the approval that covers this request, or refuse the transmission.

        **A request nobody has agreed to is refused by the port; a request
        whose approval has been spent is refused by the ledger.** The second
        case is not the port's to decide — the ledger holds the single-use
        rule, and its refusal names the approval.

        :raises labcairn.providers.errors.OutboundRefusedError: no approval
            covers this request, or the one that does has been spent, expired,
            or does not cover this use. The refusal happens before the request
            is built, so the transport is never reached.
        """
        bucket = self._pending.get(request.prompt)
        if not bucket:
            raise OutboundRefusedError(
                "no approval covers this probe request. The remedy is an approval "
                "for the probe of this endpoint: one per request the probe makes."
            )
        entry = next((item for item in bucket if not item.spent), bucket[0])
        if entry.approval is None:
            raise OutboundRefusedError(
                f"no approval covers the {entry.capability.value} probe of "
                f"{_the_endpoint(entry.use)}. The remedy is an approval for it: "
                f"{entry.use.capability.value} on "
                f"{entry.use.root_id}:{entry.use.resource_key}, one per request the "
                "probe makes."
            )
        entry.spent = True
        try:
            entry.approval.require(request)
        except OutboundRefusedError as error:
            raise OutboundRefusedError(
                f"the approval for the {entry.capability.value} probe was refused: {error.reason}"
            ) from error

    def missing(self) -> tuple[tuple[Capability, ApprovalUse], ...]:
        """The requests of this session that no approval covers.

        **What the operator has to grant.** A caller that renders a remedy can
        read it here rather than parsing a refusal message: the capability is
        the request's own, and the use is what the approval has to be asked
        for.
        """
        return tuple(
            (entry.capability, entry.use)
            for bucket in self._pending.values()
            for entry in bucket
            if entry.approval is None
        )


@dataclass
class _PendingRequest:
    """One request of a probe session, and the approval that covers it."""

    capability: Capability
    use: ApprovalUse
    approval: OutboundApproval | None
    #: Whether this request has already been answered. A second request for
    #: the same words finds the spent one, and the ledger refuses it.
    spent: bool = False


def _the_text(use: ApprovalUse) -> str:
    """The words a use names — the material its request carries.

    :raises ValueError: the use does not name exactly one piece of text. A
        probe's use always does: the probe sends one fixed instruction, and the
        approval that covers it is bound to those words.
    """
    excerpts = use.arguments.get("excerpts")
    if not isinstance(excerpts, (list, tuple)) or len(excerpts) != 1:
        raise ValueError("a probe's approval must name exactly one excerpt")
    only = excerpts[0]
    if not isinstance(only, str):
        raise ValueError("a probe's excerpt must be text")
    return only


def _the_endpoint(use: ApprovalUse) -> str:
    """The endpoint a use names, as ``provider:model``."""
    provider = use.arguments.get("provider")
    model = use.arguments.get("model")
    return f"{provider}:{model}"


def probe_consent(
    context: ApplicationContext,
    *,
    provider: str,
    model: str,
    requests: Sequence[ProbeRequest],
    now: datetime,
) -> ProbeConsent:
    """The consent port for one probe session, holding the approvals that cover it.

    **The approvals are found by their digest, not by their ids.** The store
    keeps an approval's digest of the arguments, not the arguments themselves,
    so an approval is recognised by recomputing the digest of the use it
    should cover and comparing. That is the same comparison the spend makes,
    so an approval that covers nothing is not handed to the probe as though it
    did.

    **One row covers one request.** Two of a session's requests can share a
    use — the two structured-output probes send the same instruction — and
    they still need two grants, because a grant is spent on the request that
    names it. So a row is handed to one request only.

    **Only granted, unspent approvals are handed over.** The ledger refuses
    the others, and a session that cannot spend its approval should say so
    before it sends anything.

    :raises labcairn.application.refusal.ApplicationRefusedError: the policy
        denied the request, so there is nothing to cover.
    """
    granted = list_approvals(context.store.session, context.task_id)
    entries: list[tuple[Capability, ApprovalUse, OutboundApproval | None]] = []
    spent: set[ApprovalId] = set()
    for request in requests:
        use = probe_use(context, provider=provider, model=model, request=request)
        digest = _the_digest(context, use)
        match = next(
            (
                approval
                for approval in granted
                if approval.approval_id not in spent
                and approval.state is ApprovalState.GRANTED
                and approval.args_digest == digest
            ),
            None,
        )
        if match is not None:
            spent.add(match.approval_id)
        entries.append(
            (
                request.capability,
                use,
                None
                if match is None
                else OutboundApproval(context, match.approval_id, use, at=now),
            )
        )
    return ProbeConsent(entries)
