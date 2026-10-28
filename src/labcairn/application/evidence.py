"""Recording a claim that rests on the material a task holds.

The evidence ledger's writers lived in :mod:`labcairn.evidence.store` and
:mod:`labcairn.db.materials`, and **no layer operation called either**. So a
material could be ingested and bound to a task, and the task still could not
carry a claim: the only path that ended with a report was the outsider walk,
which wrote the claim's own address and record itself. This module is that
gap closed — the surfaces' one way to say "the material says this".

Two operations, and they are deliberately different questions
-------------------------------------------------------------

:func:`list_source_addresses` answers *what can be cited here*. It reads the
ledger's extracted text for one material and reports each address the
ingestion produced. It is an inventory question, asked of any source the
policy lets the task see — the same posture :func:`~labcairn.application.
sources.inspect_source` takes.

:func:`record_claim` answers *the material says this, here*. It writes an
anchor and an evidence record, and it has three more requirements than the
listing, each because a record outlives the moment it was written:

* **the task must hold the material.** A report's builder refuses an anchor
  whose source the report does not carry, so a claim on unbound material
  would be a record that poisons every later report of the task. The write is
  refused where the mistake is made.
* **the material must be readable.** ADR-0004 A7: unreadable material is
  neither analysed nor cited.
* **the address must resolve, now.** The anchor is bound to the source's
  current hash, and the text at the address must exist in those bytes. An
  anchor at an address nothing answers is an anchor to nothing.

What the operation does not do
------------------------------

**It does not run a check.** The record it writes is ``extracted``: located,
copied out, and no more. C1, C2 and C3 are separate acts with their own audit
rows (:func:`~labcairn.evidence.store.advance`), and a writer that claimed a
pass would be the verification it is supposed to make possible.

**It does not accept a model's proposal.** ``created_by`` is ``user`` and the
id is the local user's: in a single-user local application the actor of a
surface operation is the person at the surface. The vocabulary's
``model_proposal`` exists so a future proposal path is expressible; it is not
reachable here, because *proposing is not recording*.

**It does not re-read the material's bytes.** The text comes from
``source_texts`` under the source's current hash — the ledger's own account
of what the ingestion read. Reading the file again would give the material a
second way in, and the capability registry already bounds the first
(``source.read``'s ``max_bytes``).

The capability is ``source.inventory``
--------------------------------------

The resource the consent is about is the material, and the operation reads
and writes *about* it rather than drawing bytes out of it. The ingestion
writes the ledger's rows under ``source.inventory`` for the same reason: the
capability bounds what may be done with a source, and the policy's verdict on
that source is the question. A second capability for "write a record about
this material" would be a second spelling of the same decision.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from labcairn.application import consent
from labcairn.application.context import ApplicationContext, store_refusals
from labcairn.application.models import Result
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.core.ids import new_id
from labcairn.db.materials import current_texts, put_anchor
from labcairn.db.models import LOCAL_USER_ID
from labcairn.db.repository import load_source, load_task
from labcairn.evidence.cite_support import LocationResolution
from labcairn.evidence.index import LabCairnIndex, locator_from_key
from labcairn.evidence.record import EvidenceRecord
from labcairn.evidence.states import EvidenceCreator, EvidenceKind, VerificationStatus
from labcairn.evidence.store import append_record, record_for_span
from labcairn.material.addressing import LocatorKeyError
from labcairn.security.capabilities import CapabilityId
from labcairn.sources.source import (
    AnchorKind,
    Source,
    SourceAnchor,
    SourceReadability,
)

__all__ = [
    "ClaimRecorded",
    "ClaimRequest",
    "SourceAddress",
    "list_source_addresses",
    "record_claim",
]

#: The kinds a claim can carry. A ``result`` is this project's own analysis
#: outcome, written by the analysis path against the operator that produced
#: it — not a statement read out of a material, which is what this operation
#: addresses.
_CLAIMABLE: frozenset[EvidenceKind] = frozenset({EvidenceKind.CLAIM, EvidenceKind.NUMERIC})

#: The anchor kind each claim kind is about. A number is what C3 is for, and
#: a sentence is what C2 is for; the vocabulary's other members (``structural``,
#: ``absence_scan``) name an address with no value and no quotation, and no
#: operation here writes one yet.
_ANCHOR_KINDS: dict[EvidenceKind, AnchorKind] = {
    EvidenceKind.CLAIM: AnchorKind.QUOTATION,
    EvidenceKind.NUMERIC: AnchorKind.NUMERIC,
}


class SourceAddress(Result):
    """One address the ledger holds text for, inside one material.

    ``text`` is the **stored** text — what the adapter produced and the ledger
    recorded — never the file re-read. A caller choosing a quotation reads it
    from here, and the record it writes carries the same bytes the check will
    compare against.

    ``extraction_version`` names which extraction the row came from. The
    ledger may hold more than one extraction of the same bytes, and the
    address reports the newest, which is the one
    :func:`~labcairn.evidence.index.locate_anchor` resolves.
    """

    source_id: str
    locator_key: str
    locator_kind: str
    extraction_version: str
    text: str


class ClaimRequest(Result):
    """What a claim says, and where in the material it says it.

    ``span`` is the literal text copied out of the material. When it is
    omitted the whole address's text is the span, which is honest for a table
    cell and rarely what a page of a paper wants — a caller quoting a passage
    of a page passes the passage.

    The fields are the record's own vocabularies rather than strings, so an
    unknown kind or a missing unit is refused by the model before this
    operation looks at the material. ``text``, ``value``, ``unit`` and
    ``tolerance`` belong to different kinds, and which is required is the
    record model's rule rather than a second one stated here.
    """

    source_id: str
    locator_key: str
    kind: EvidenceKind = EvidenceKind.CLAIM
    text: str | None = None
    span: str | None = None
    value: float | None = None
    unit: str | None = None
    tolerance: float | None = None


class ClaimRecorded(Result):
    """The record the ledger now holds, and the anchor it rests on.

    The record is returned whole rather than by id so a caller does not have
    to read the ledger back to know what it wrote — and so the CLI's ``--json``
    and the API's body are the record the store holds.
    """

    record: EvidenceRecord
    anchor_id: str


def list_source_addresses(context: ApplicationContext, source_id: str) -> tuple[SourceAddress, ...]:
    """Every address the ledger holds text for in one material.

    Ordered by ``locator_key``, like the reader it comes from, so two calls
    report the same order.

    :raises ApplicationRefusedError: the ledger holds no such source, or the
        policy denied the inventory.
    """
    with store_refusals():
        source = load_source(context.store.session, str(source_id))
    if source is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.SOURCE_NOT_FOUND,
            f"the ledger holds no source with the id {source_id!r}.",
        )
    _require_inventory(context, source)

    rows = current_texts(context.store.session, source_content_sha256=source.content_sha256)
    return tuple(
        SourceAddress(
            source_id=source.source_id,
            locator_key=row.locator_key,
            locator_kind=row.locator_kind,
            extraction_version=row.extraction_version,
            text=row.text,
        )
        for row in rows
    )


def record_claim(
    context: ApplicationContext,
    request: ClaimRequest,
    *,
    now: datetime | None = None,
) -> ClaimRecorded:
    """Write an anchor and an ``extracted`` record for *request*.

    The anchor is bound to the source's **current** hash and to the text at
    the address in those bytes; the record names the anchor, the span it
    copied out, the span's hash and the same source hash. Locating the record
    is therefore a fact of the write, and C1's later question — "is the
    material still the bytes this was written against?" — has an answer.

    The anchor and the record commit together. A half-write would be an
    anchor no record cites or a record citing an anchor nothing holds, and
    neither is a state a reader could interpret.

    :param now: the moment the anchor and record are dated with. Passed in
        rather than read, so a caller that records a set of claims gets one
        moment for all of them.
    :raises ApplicationRefusedError: the source is unknown, denied, unbound
        or unreadable; the address does not resolve; the arguments do not
        make a record; or the task already holds a record for this span.
    """
    moment = now if now is not None else datetime.now(UTC)

    with store_refusals():
        source = load_source(context.store.session, request.source_id)
        task = load_task(context.store.session, context.task_id)
    if source is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.SOURCE_NOT_FOUND,
            f"the ledger holds no source with the id {request.source_id!r}.",
        )

    # The task's authority over the material and the material's readability
    # are facts the capability cannot grant: a policy cannot let a task cite
    # material it does not hold, so these are checked before the policy is
    # asked. A source the task does not hold may not even be addressable in
    # this workspace's roots, and asking the policy about a resource it cannot
    # name would report a denial where the honest answer is "not held".
    if source.source_id not in {str(bound) for bound in task.bound_source_ids}:
        raise ApplicationRefusedError(
            ApplicationRefusal.SOURCE_NOT_BOUND,
            f"the task holds no source with the id {source.source_id!r}. A claim "
            "rests on a citation, and a citation points into material the task "
            "holds; a report built over this task refuses an anchor whose source "
            "the report does not carry, so the record would make every later "
            "report refuse. Bind the material to the task before recording a "
            "claim about it.",
        )
    if source.readability is not SourceReadability.READABLE:
        raise ApplicationRefusedError(
            ApplicationRefusal.SOURCE_UNREADABLE,
            f"the source {source.source_id!r} is {source.readability.value}: "
            f"{source.readability_disclosure}. ADR-0004 A7: unreadable material is "
            "neither analysed nor cited, so there is nothing here to record a "
            "claim about.",
        )
    if request.kind not in _CLAIMABLE:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"a {request.kind.value!r} record is not a claim read out of material. "
            "A result is the analysis path's own record, written against the "
            "operator that produced it; the kinds this operation writes are "
            + ", ".join(sorted(kind.value for kind in _CLAIMABLE))
            + ".",
        )

    _require_inventory(context, source)

    try:
        locator = locator_from_key(request.locator_key)
    except LocatorKeyError as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the address {request.locator_key!r} is not one this build can rebuild: {error}",
        ) from error

    anchor_id = str(new_id())
    provisional = SourceAnchor(
        anchor_id=anchor_id,
        source_id=source.source_id,
        kind=_ANCHOR_KINDS[request.kind],
        locator=locator,
        bound_source_sha256=source.content_sha256,
        created_at=moment,
    )
    located = LabCairnIndex(context.store.session.connection()).locate(provisional)
    if located is None or located.resolution is not LocationResolution.RESOLVED:
        resolution = "unaddressable" if located is None else located.resolution.value
        raise ApplicationRefusedError(
            ApplicationRefusal.ADDRESS_NOT_FOUND,
            f"the ledger holds no text at {request.locator_key!r} in the bytes "
            f"{source.source_id!r} currently holds: the address is "
            f"{resolution}. An anchor at an address nothing answers "
            "is an anchor to nothing; nothing was written.",
        )
    address_text = located.text or ""
    anchor = provisional.model_copy(update={"excerpt_sha256": _sha256(address_text)})

    span = request.span if request.span is not None else address_text
    span_sha256 = _sha256(span)
    record = _the_record(
        context,
        request,
        anchor=anchor,
        span=span,
        span_sha256=span_sha256,
        source=source,
        moment=moment,
    )

    session = context.store.session
    existing = record_for_span(session.connection(), str(context.task_id), span_sha256)
    if existing is not None:
        raise ApplicationRefusedError(
            ApplicationRefusal.CLAIM_ALREADY_RECORDED,
            f"the task already holds the record {existing!r}, whose extracted span "
            f"hashes to {span_sha256}. uq_evidence_task_span permits one record per "
            "span per task, so the same words are one claim; to record a different "
            "statement about this address, state it — the span is the record's own "
            "quotation, not the address's.",
        )

    try:
        put_anchor(session, anchor)
        append_record(session.connection(), record)
        session.commit()
    except IntegrityError as error:
        # Two writers can pass the duplicate check above at once; the unique
        # index is what settles it. Re-ask after the rollback, so the refusal
        # names the record that won rather than a constraint error.
        session.rollback()
        existing = record_for_span(session.connection(), str(context.task_id), span_sha256)
        if existing is not None:
            raise ApplicationRefusedError(
                ApplicationRefusal.CLAIM_ALREADY_RECORDED,
                f"the task already holds the record {existing!r}, whose extracted "
                f"span hashes to {span_sha256}.",
            ) from error
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the ledger refused the claim: {error.orig}. Nothing was written.",
        ) from error

    return ClaimRecorded(record=record, anchor_id=anchor_id)


def _require_inventory(context: ApplicationContext, source: Source) -> None:
    """Ask the policy about this source, and refuse a denial."""
    resource = context.resource_for(source.relative_path)
    consent.evaluate(
        context,
        capability=CapabilityId.SOURCE_INVENTORY,
        arguments={},
        resource=resource,
    )


def _the_record(
    context: ApplicationContext,
    request: ClaimRequest,
    *,
    anchor: SourceAnchor,
    span: str,
    span_sha256: str,
    source: Source,
    moment: datetime,
) -> EvidenceRecord:
    """The record model for this write, or a refusal naming what is unusable.

    Built through the model's validators rather than around them: which
    fields a kind requires, whether the span and its hash are both present,
    and whether a claim carries a number are ADR-0004 Contract 1's rules, and
    a second statement of them here would be a second thing to keep in step.
    """
    try:
        return EvidenceRecord.model_validate(
            {
                "evidence_id": str(new_id()),
                "task_id": str(context.task_id),
                "kind": request.kind,
                "text": request.text,
                "value": request.value,
                "unit": request.unit,
                "tolerance": request.tolerance,
                "anchor_ids": (anchor.anchor_id,),
                "extracted_span": span,
                "extracted_span_sha256": span_sha256,
                "status": VerificationStatus.EXTRACTED,
                "created_by": EvidenceCreator.USER,
                "created_by_id": LOCAL_USER_ID,
                "source_content_hash": source.content_sha256,
                "created_at": moment,
            }
        )
    except ValidationError as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the claim does not make a {request.kind.value!r} record: {error}. "
            "Nothing was written.",
        ) from error


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
