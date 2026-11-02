"""Recording a scholarly identifier, and answering a request to resolve one.

LC-P1-09's acceptance review named the gap structurally: no record could
carry an identifier, nothing resolved one, and ingestion recorded none. This
module is the layer's one way into the shelf the identifiers live on, and the
operations are deliberately three, not one:

:func:`record_identifier` answers *this material, this task, names this
identifier, and here is who says so*. Provenance is data, not a mode: an
identifier the ingestion machinery found, one a person typed and one a model
proposed land as the same kind of row with different ``supplied_by`` values,
because what the reader needs is the attribution, not a different door per
supplier.

:func:`request_outbound_resolution` answers *resolve this* -- and its answer
in this build is **recorded, not sent**. Resolving a scholarly identifier
means contacting an external service; the closed capability registry
(:class:`~labcairn.security.capabilities.CapabilityId`) defines exactly one
network-effect capability, ``model.request``, which is consent to prompt a
provider and consent to nothing else; and the bridge ADR-0006 describes
between the two capability vocabularies is unbuilt. So a request that cannot
be consented is recorded as ``not_attempted``, with the boundary's own reason
appended to the row. **Nothing here reaches the network**: the function has
no parameter that could hold a response, and the test suite runs it with a
socket guard to keep the honest path honest.

:func:`confirm_identifier_resolution` answers *a person checked it, by hand*,
and it is the only door to ``resolved``. The resolver signs, because
``resolved_by`` is what a reader audits and an unsigned row gives them
nothing to audit. **And resolving is not a citation check**: the function
takes no record id and writes no ``verification_log`` entry, so no sequence
of identifier events -- not even a person's confirmation of a model's
proposal -- can mark a citation as checked. That is the work order's other
half, and it is structural here rather than merely documented.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel

from labcairn.application.consent import evaluate as consent_evaluate
from labcairn.application.context import ApplicationContext, store_refusals
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.core.ids import new_id
from labcairn.db.models import LOCAL_USER_ID
from labcairn.evidence.identifiers import (
    IdentifierError,
    IdentifierNotFoundError,
    IdentifierProvenance,
    IdentifierScheme,
    ResolutionState,
    ScholarlyIdentifier,
    confirm_resolution,
    load_identifier,
    load_task_identifiers,
    put_identifier,
    request_resolution,
)
from labcairn.security.capabilities import CapabilityId
from labcairn.security.policy import Permission

__all__ = [
    "IdentifierRecorded",
    "IdentifierRequest",
    "confirm_identifier_resolution",
    "list_task_identifiers",
    "record_identifier",
    "request_outbound_resolution",
]


class IdentifierRequest(BaseModel):
    """What is being recorded: the identifier, and who supplied it.

    ``scheme`` and ``supplied_by`` are the vocabularies themselves rather
    than strings, so an unknown scheme or supplier is refused by the model
    before this operation looks at the store.
    """

    scheme: IdentifierScheme
    value: str
    supplied_by: IdentifierProvenance
    #: Who said so, exactly: the person's id, the ingestion run's id or the
    #: model run's id. A default only exists for the local single-user Phase 1;
    #: a model's identifier names its run, and this field is where.
    supplied_by_id: str = LOCAL_USER_ID


class IdentifierRecorded(BaseModel):
    """The identifier as it now stands, with the state it was written in."""

    identifier: ScholarlyIdentifier


def _require_task_area(context: ApplicationContext, capability: CapabilityId) -> None:
    """Ask the policy about the task's own area, and refuse a question.

    The identifiers are the task's own data -- a claim cites what its task
    holds -- so writing or reading them is the task area's business, the same
    resource and the same question
    :func:`labcairn.application.papers._require_task_area` asks for the
    project row.
    """
    resource = context.task_area()
    authorisation = consent_evaluate(
        context,
        capability=capability,
        arguments={},
        resource=resource,
    )
    if authorisation.permission is Permission.ASK:
        raise ApplicationRefusedError(
            ApplicationRefusal.PERMISSION_DENIED,
            f"the policy asked about {capability.value} on the task's area, and "
            "an operation that cannot be answered may not half-run. Record the "
            "allow rule and run this again.",
        )


def _load_owned_identifier(context: ApplicationContext, identifier_id: str) -> ScholarlyIdentifier:
    """The identifier, provided this task is the task that holds it.

    A task resolving another task's identifier would write a state change
    into a row the context's policy was never asked about -- the same reason
    a claim cannot cite another task's material. The load is the ownership
    check, and every operation that changes an identifier's state goes
    through it.
    """
    with store_refusals():
        identifier = load_identifier(context.store.session.connection(), identifier_id)
    if identifier is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.IDENTIFIER_NOT_FOUND,
            f"the ledger holds no identifier with the id {identifier_id!r}.",
        )
    if identifier.task_id != str(context.task_id):
        raise ApplicationRefusedError(
            ApplicationRefusal.IDENTIFIER_NOT_FOUND,
            f"the identifier {identifier_id!r} belongs to task"
            f" {identifier.task_id!r}, not to this task"
            f" {context.task_id!r}. A task moves what it holds; it does not"
            " reach into another task's shelf.",
        )
    return identifier


def record_identifier(
    context: ApplicationContext,
    request: IdentifierRequest,
    *,
    now: datetime | None = None,
) -> IdentifierRecorded:
    """Record an identifier on this task's shelf, whole, or not at all.

    The identifier is written ``unresolved`` and stays that way until someone
    resolves it: recording where a citation points is not resolving it, and a
    row that arrived as "resolved" would be a resolution nobody made. The
    provenance travels with the row -- ``ingestion``, a person, or a model --
    because a model's proposal is data of the same shape and a different
    authority, and that difference is the one the work order exists to make
    readable.

    :param now: the moment the identifier is dated with. Passed in rather
        than read, so a caller that records a set of identifiers gets one
        moment for all of them.
    :raises ApplicationRefusedError: the policy denied the write, the task
        already holds this identifier, or the arguments do not make one.
    """
    moment = now if now is not None else datetime.now(UTC)
    _require_task_area(context, CapabilityId.FS_WRITE)
    identifier = ScholarlyIdentifier(
        identifier_id=str(new_id()),
        task_id=str(context.task_id),
        scheme=request.scheme,
        value=request.value,
        supplied_by=request.supplied_by,
        supplied_by_id=request.supplied_by_id,
        resolution_state=ResolutionState.UNRESOLVED,
        created_at=moment,
    )
    with store_refusals():
        try:
            put_identifier(context.store.session.connection(), identifier)
        except IdentifierError as error:
            raise ApplicationRefusedError(
                ApplicationRefusal.ARGUMENTS_INVALID,
                f"the ledger refused the identifier: {error} Nothing was written.",
            ) from error
    return IdentifierRecorded(identifier=identifier)


def request_outbound_resolution(
    context: ApplicationContext,
    identifier_id: str,
    *,
    reason: str = "a resolution was requested",
    now: datetime | None = None,
) -> IdentifierRecorded:
    """Ask for a resolution, and record the honest answer: **not attempted**.

    This is the operation the work order's outbound boundary is about, and
    its shape is the point: the request is real, the refusal to go out is
    real, and the row records both rather than dropping the request silently
    or reaching the network silently. The reason a caller asked is kept, and
    the boundary's own reason is appended to it, so the row a reader finds
    names the rule and not merely the caller's wish.

    **The function performs no lookup and holds no response.** Resolving a
    scholarly identifier means contacting an external service; this build
    cannot consent an outbound lookup; and a future resolver must arrive
    through the consent layer with a capability that exists in the closed
    registry. Until then, ``not_attempted`` is not a failure state -- it is
    the truthful state of the world, queryable and reported like any other.

    :raises ApplicationRefusedError: the policy denied the write, or no such
        identifier exists on this task.
    """
    moment = now if now is not None else datetime.now(UTC)
    _require_task_area(context, CapabilityId.FS_WRITE)
    identifier = _load_owned_identifier(context, identifier_id)
    with store_refusals():
        try:
            resolved = request_resolution(
                context.store.session.connection(),
                identifier.identifier_id,
                detail=reason,
                requested_at=moment,
            )
        except IdentifierNotFoundError as error:
            raise ApplicationRefusedError(
                ApplicationRefusal.IDENTIFIER_NOT_FOUND,
                str(error),
            ) from error
    return IdentifierRecorded(identifier=resolved)


def confirm_identifier_resolution(
    context: ApplicationContext,
    identifier_id: str,
    *,
    resolved_by: str,
    detail: str,
    now: datetime | None = None,
) -> IdentifierRecorded:
    """Record a person's resolution of an identifier, signed.

    The person checked the identifier by hand -- looked it up on their own
    recognisance, outside the machine -- and this operation writes down what
    they found and who they are. It is the only door to ``resolved``.

    **And it stops there.** The function takes no evidence-record id and
    writes nothing to any record's ``verification_log``: resolving an
    identifier is not a citation check, and a model-supplied identifier
    confirmed by a person is still not one. A record's verification state
    moves only through the checks and attestations ADR-0004 already names,
    and this operation is neither.

    :raises ApplicationRefusedError: the resolver is unnamed, the policy
        denied the write, or no such identifier exists on this task.
    """
    moment = now if now is not None else datetime.now(UTC)
    if not resolved_by.strip():
        raise ApplicationRefusedError(
            ApplicationRefusal.RESOLUTION_IDENTITY_EMPTY,
            "a resolution names nobody. Confirming an identifier is a person "
            "standing behind a fact, and ``resolved_by`` is what a reader "
            "audits -- an unsigned confirmation is the one thing worse than "
            "an unresolved identifier, because it looks like one.",
        )
    _require_task_area(context, CapabilityId.FS_WRITE)
    identifier = _load_owned_identifier(context, identifier_id)
    with store_refusals():
        try:
            resolved = confirm_resolution(
                context.store.session.connection(),
                identifier.identifier_id,
                resolved_by=resolved_by,
                detail=detail,
                resolved_at=moment,
            )
        except IdentifierNotFoundError as error:
            raise ApplicationRefusedError(
                ApplicationRefusal.IDENTIFIER_NOT_FOUND,
                str(error),
            ) from error
    return IdentifierRecorded(identifier=resolved)


def list_task_identifiers(context: ApplicationContext) -> tuple[ScholarlyIdentifier, ...]:
    """Every identifier this task holds, with its provenance and its state.

    The query the work order's third clause asks for: a verified identifier
    and an unverified one are different things, and this is where the
    difference is read. Ordered by creation time and then by id -- the
    ledger's own order, a stable rendering and not a ranking.

    :raises ApplicationRefusedError: the policy denied reading the task's area.
    """
    _require_task_area(context, CapabilityId.FS_READ)
    with store_refusals():
        return load_task_identifiers(context.store.session.connection(), str(context.task_id))
