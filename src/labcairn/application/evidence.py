"""Recording a claim that rests on the material a task holds.

The evidence ledger's writers lived in :mod:`labcairn.evidence.store` and
:mod:`labcairn.db.materials`, and **no layer operation called either**. So a
material could be ingested and bound to a task, and the task still could not
carry a claim: the only path that ended with a report was the outsider walk,
which wrote the claim's own address and record itself. This module is that
gap closed — the surfaces' one way to say "the material says this".

The operations, and the questions they are deliberately different
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

And one operation reads what the ledger holds back
---------------------------------------------------

:func:`list_task_records` answers *what has been claimed here*. The other
operations write records or enumerate the addresses they may be written at;
this one reads the task's own records back, so a surface can show a person
what is on the ledger — the model's proposals and the person's attestations
side by side, each carrying whose words it is.

**It is a read of the task's own rows, and it is guarded as one.** The
records belong to the task, so the capability asked is ``fs.read`` on the
task area — the same resource and the same question
:func:`~labcairn.application.tasks.read_task_state` asks. That is the
distinction this module rests on: the *material* is guarded by
``source.inventory`` where it is named, and the *task's own records* are
guarded by the task's own area, because a record is not a path and the
material it was taken from is not named by the record itself.

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
from typing import Final

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
from labcairn.evidence.index import LabCairnIndex, load_anchor, locator_from_key
from labcairn.evidence.record import EvidenceRecord
from labcairn.evidence.states import (
    EvidenceCreator,
    EvidenceKind,
    VerificationStatus,
)
from labcairn.evidence.store import (
    LedgerError,
    append_record,
    attest,
    load_record,
    load_task_records,
    record_for_span,
    supersede_record,
)
from labcairn.material.addressing import LocatorKeyError, render_locator_key
from labcairn.security.capabilities import CapabilityId
from labcairn.sources.source import (
    AnchorKind,
    Source,
    SourceAnchor,
    SourceReadability,
)

__all__ = [
    "PROPOSAL_VERDICTS",
    "ClaimAttested",
    "ClaimRecorded",
    "ClaimRequest",
    "ProposalSettled",
    "SourceAddress",
    "attest_claim",
    "confirm_proposal",
    "list_source_addresses",
    "list_task_records",
    "record_claim",
    "record_model_proposal",
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


def list_task_records(context: ApplicationContext) -> tuple[EvidenceRecord, ...]:
    """Every record the ledger holds for this task, in the ledger's own order.

    **These are the task's own rows, so the task's own area is what guards
    them.** A record is a statement about material the task holds, and this
    is a read of the task's state — so the capability asked is ``fs.read``
    on the task area, the **same resource and the same question** that
    :func:`~labcairn.application.tasks.read_task_state` asks. Two spellings
    of "the task's area" would be two things for a policy rule to match, and
    a rule written against one of them would silently not cover the other.

    **The order is the ledger's, and it is not a ranking.** The ledger
    orders its records by creation time and then by id, and ADR-0004 A5 says
    a conflict is not settled by taking the newer row — so this order is
    for a reader that renders a list, and it decides nothing.

    **And every record says whose words it is.** ``created_by`` says whether
    a person or a model wrote it, ``created_by_id`` says which, and the
    verification log says who stood behind it. So a reader can tell a
    model's proposal from a person's attestation without this operation
    having to say so a second way — and a surface that blurred the two would
    be the "second spelling" the work order exists to avoid.

    :raises ApplicationRefusedError: the policy denied reading the task's area.
    """
    area = context.task_area()
    consent.evaluate(
        context,
        capability=CapabilityId.FS_READ,
        arguments={"path": area.declared_key},
        resource=area,
    )
    with store_refusals():
        return load_task_records(context.store.session.connection(), str(context.task_id))


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
    return _record_against_material(
        context,
        request,
        now=now,
        creator=EvidenceCreator.USER,
        status=VerificationStatus.EXTRACTED,
    )


def record_model_proposal(
    context: ApplicationContext,
    request: ClaimRequest,
    *,
    now: datetime | None = None,
) -> ClaimRecorded:
    """Record a model's answer as a proposal, bound to the locator it names.

    ADR-0016's rule: what a model says is a ``model_proposal`` -- it
    reaches ``planned`` and no further without a verification entry --
    and any claim the model makes is **bound to a locator** before it
    can reach a report. So the locator is an argument of the write, not
    something parsed out of the answer afterwards: the anchor lands with
    the record, and the record enters the ledger already pinned to the
    material it claims to speak for.

    The constructor, not this path, holds the line the proposal cannot
    cross: the record is built through ``EvidenceRecord``'s validators,
    which refuse ``user_attested`` without a ``USER`` creator and
    ``verified_by_rule`` without a check log. Nothing here writes the
    creator field around them, because the creator field is exactly
    what the validators are watching.

    The flow below the two entry points is one flow: the material must
    be held, readable and addressable, and the anchor and the record
    commit together, exactly as ``record_claim``'s do. What differs is
    what the record says about its own author.
    """
    return _record_against_material(
        context,
        request,
        now=now,
        creator=EvidenceCreator.MODEL_PROPOSAL,
        status=VerificationStatus.PLANNED,
    )


#: The two things a person can say about a model's proposal. **Closed**, because
#: "the person had a look" is not a verdict a record can carry, and a
#: vocabulary of one would make every word a synonym for "yes".
PROPOSAL_VERDICTS: Final[tuple[str, ...]] = ("confirmed", "disputed")


class ClaimAttested(Result):
    """The claim as it now stands, and the person who stands behind it.

    **The person is returned by name**, because the record's own creator
    field says "a person" and this says *which* one: the ledger keeps the
    two apart, and a reader who is told only that "a person" signed is told
    nothing.
    """

    record: EvidenceRecord
    user_id: str
    note: str


class ProposalSettled(Result):
    """A model's proposal, and the person's word about it.

    **Both records are returned**, because the history is part of the
    answer: the proposal is kept and marked, and the thing a report may
    cite is the person's own record.
    """

    proposal: EvidenceRecord
    confirmation: EvidenceRecord
    verdict: str
    user_id: str


def attest_claim(
    context: ApplicationContext,
    evidence_id: str,
    *,
    user_id: str,
    note: str,
    now: datetime | None = None,
) -> ClaimAttested:
    """A person stands behind **their own** claim.

    The claim must be theirs. The store's ``attest`` refuses any record
    whose creator is not a person, and that refusal is ADR-0016 D2's rule
    rather than an oversight — *"an attestation is something a person did"*.
    **A model's proposal is not attested here**: a person settles one with
    :func:`confirm_proposal`, which is the route the schema leaves open.

    The attestation is logged as a **C4** entry — the check whose only
    verdict is ``not_checked`` — so the entry says *no machine checked this,
    and a person is standing behind it*, and it carries **that person's
    id**, which is what keeps an attestation distinguishable from a rule's
    pass.

    :raises ApplicationRefusedError: no such record; the record is not the
        person's own; the person signed nothing; or the ledger refused the
        move.
    """
    moment = now if now is not None else datetime.now(UTC)
    if not user_id.strip():
        raise ApplicationRefusedError(
            ApplicationRefusal.ATTESTATION_IDENTITY_EMPTY,
            "an attestation nobody signs is not an attestation. Name the person whose word it is.",
        )
    session = context.store.session
    connection = session.connection()
    record = load_record(connection, evidence_id)
    if record is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.EVIDENCE_NOT_FOUND,
            f"the ledger holds no record with the id {evidence_id!r}.",
        )
    if record.created_by is not EvidenceCreator.USER:
        raise ApplicationRefusedError(
            ApplicationRefusal.ATTESTATION_NOT_THE_AUTHOR,
            f"the record {evidence_id!r} was written by {record.created_by.value!r}, "
            "and an attestation is of a person's own claim. A model's proposal is "
            "settled by a person writing their own word about the same material, "
            "which supersedes the proposal — that is confirm_proposal's route, and "
            "it is the only one the schema leaves.",
        )
    try:
        attested = attest(
            connection,
            evidence_id,
            user_id=user_id,
            note=note,
            checked_at=moment,
        )
    except LedgerError as error:
        session.rollback()
        raise ApplicationRefusedError(
            ApplicationRefusal.ATTESTATION_REFUSED,
            f"the ledger refused the attestation: {error}. Nothing was written.",
        ) from error
    session.commit()
    return ClaimAttested(record=attested, user_id=user_id, note=note)


def confirm_proposal(
    context: ApplicationContext,
    proposal_id: str,
    *,
    user_id: str,
    verdict: str,
    note: str,
    now: datetime | None = None,
) -> ProposalSettled:
    """A person confirms or disputes a model's proposal.

    **The proposal is not promoted; the person's own word replaces it.**

    ADR-0016 D2 holds that a model proposal never becomes
    ``user_attested`` — the record model refuses it at construction, in
    every path, including a hand-written file — and the store's own exit
    for a record nobody may promote is **supersession**: *"a person writes
    their own record, and the rule's is kept and marked."* So this
    operation does three things, and one transaction:

    1. **the person's own record** is written at the same address, carrying
       their words as its span — a confirmation is a claim in its own right,
       and ``uq_evidence_task_span`` holds that the same words are one
       claim.
    2. **the proposal is superseded** by it. The old row is kept, not
       deleted: its history is the evidence of what was claimed and when.
    3. **the settlement is attested on the person's own record**, and the
       attestation's entry carries their id, their verdict and their note.
       **Not on the proposal's log** — the store's own design is that the
       old row is *marked* and the new one carries the attestation, and a
       product module writing the ledger's verification row is what the
       threat model's C14 forbids.

    **The proposal's status and its creator are untouched throughout**,
    because a model's say-so never becomes a person's.

    The person's record is then attested, so **the thing a report may cite
    is a person's word and not a model's** — which is the whole point of
    the route.

    :raises ApplicationRefusedError: no such record; the record is not a
        model's proposal; the proposal has already been settled; the verdict
        is outside the vocabulary; the person signed nothing; or the ledger
        refused the move.
    """
    moment = now if now is not None else datetime.now(UTC)
    if verdict not in PROPOSAL_VERDICTS:
        raise ApplicationRefusedError(
            ApplicationRefusal.PROPOSAL_VERDICT_UNKNOWN,
            f"{verdict!r} is not a verdict a person can return about a proposal. "
            "The verdicts are " + ", ".join(PROPOSAL_VERDICTS) + ".",
        )
    if not user_id.strip():
        raise ApplicationRefusedError(
            ApplicationRefusal.ATTESTATION_IDENTITY_EMPTY,
            "an attestation nobody signs is not an attestation. Name the person whose word it is.",
        )
    session = context.store.session
    connection = session.connection()
    proposal = load_record(connection, proposal_id)
    if proposal is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.EVIDENCE_NOT_FOUND,
            f"the ledger holds no record with the id {proposal_id!r}.",
        )
    if proposal.created_by is not EvidenceCreator.MODEL_PROPOSAL:
        raise ApplicationRefusedError(
            ApplicationRefusal.PROPOSAL_NOT_A_PROPOSAL,
            f"the record {proposal_id!r} was written by {proposal.created_by.value!r}, "
            "and there is nothing to settle: a proposal is a model's, and a "
            "person's own claim is attested with attest_claim.",
        )
    if proposal.superseded_by is not None:
        raise ApplicationRefusedError(
            ApplicationRefusal.PROPOSAL_ALREADY_SETTLED,
            f"the proposal {proposal_id!r} was already settled by "
            f"{proposal.superseded_by!r}. A proposal is settled once: a second "
            "confirmation would be a second answer to a question that has one.",
        )
    if not proposal.anchor_ids:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the proposal {proposal_id!r} names no address, so there is nothing "
            "a person's word could be about.",
        )
    anchor = load_anchor(connection, proposal.anchor_ids[0])
    if anchor is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.ADDRESS_NOT_FOUND,
            f"the proposal {proposal_id!r} names an anchor the ledger does not "
            "hold, so there is nothing a person's word could be about.",
        )
    with store_refusals():
        source = load_source(session, anchor.source_id)
    if source is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.SOURCE_NOT_FOUND,
            f"the ledger holds no source with the id {anchor.source_id!r}.",
        )
    _require_inventory(context, source)

    span = note
    span_sha256 = _sha256(span)
    existing = record_for_span(connection, str(context.task_id), span_sha256)
    if existing is not None:
        raise ApplicationRefusedError(
            ApplicationRefusal.CLAIM_ALREADY_RECORDED,
            f"the task already holds the record {existing!r}, whose extracted span "
            f"hashes to {span_sha256}. uq_evidence_task_span permits one record "
            "per span per task, so the same words are one claim; a person's word "
            "about the same material has to be their own words.",
        )

    request = ClaimRequest(
        source_id=anchor.source_id,
        locator_key=render_locator_key(anchor.locator),
        kind=EvidenceKind.CLAIM,
        text=note,
        span=span,
    )
    record = _the_record(
        context,
        request,
        anchor=anchor,
        span=span,
        span_sha256=span_sha256,
        source=source,
        moment=moment,
        creator=EvidenceCreator.USER,
        status=VerificationStatus.EXTRACTED,
        creator_id=user_id,
    )
    try:
        # The replacement is inserted by ``supersede_record`` itself — the
        # store's exit writes the new row and marks the old one, and doing
        # it here as well would write the same record twice.
        #
        # **And the settlement is logged on the person's own record, not on
        # the proposal's.** The store's design says so: *"a person writes
        # their own record, and the rule's is kept and marked"* — the old
        # row is marked, and the attestation is the new row's own history.
        # Writing the verdict on the proposal's log would be a second
        # spelling of the settlement, and it would put a product module
        # behind the ledger's verification write — which the threat model's
        # C14 forbids for anything but the checks themselves.
        superseded = supersede_record(connection, proposal_id, record)
        attested = attest(
            connection,
            record.evidence_id,
            user_id=user_id,
            note=f"{verdict}. {note}",
            checked_at=moment,
        )
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the ledger refused the settlement: {error.orig}. Nothing was written.",
        ) from error
    except LedgerError as error:
        session.rollback()
        raise ApplicationRefusedError(
            ApplicationRefusal.ATTESTATION_REFUSED,
            f"the ledger refused the settlement: {error}. Nothing was written.",
        ) from error
    return ProposalSettled(
        proposal=superseded,
        confirmation=attested,
        verdict=verdict,
        user_id=user_id,
    )


def _record_against_material(
    context: ApplicationContext,
    request: ClaimRequest,
    *,
    now: datetime | None,
    creator: EvidenceCreator,
    status: VerificationStatus,
) -> ClaimRecorded:
    """The one flow both writes run: check, anchor, locate, judge, commit.

    The two entry points differ in the record's ``creator`` and
    ``status`` -- the reader wrote this, located and read out; or a
    model proposed this, located and waiting to be checked -- and in
    nothing else.
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
        creator=creator,
        status=status,
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
    creator: EvidenceCreator,
    status: VerificationStatus,
    creator_id: str = LOCAL_USER_ID,
) -> EvidenceRecord:
    """The record model for this write, or a refusal naming what is unusable.

    Built through the model's validators rather than around them: which
    fields a kind requires, whether the span and its hash are both present,
    and whether a claim carries a number are ADR-0004 Contract 1's rules, and
    a second statement of them here would be a second thing to keep in step.

    ``creator_id`` is **who** wrote it, and it is an argument rather than a
    constant because a person's record must name that person: the creator
    field says "a person" and this says which one, and a ledger that kept
    only the first would be a ledger that could not say who stood behind
    anything.
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
                "status": status,
                "created_by": creator,
                "created_by_id": creator_id,
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
