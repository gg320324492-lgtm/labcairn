"""The reply: one party's answer to another's objection, read out of a document.

**What this module is.** The product's side of the fourth body of material
the feedback chain was given: a **reviewer's objection paired with the
authors' answer**, read out of a response document. The chain holds the
mentor's exchange -- a comment, the change made in answer to it, the
judgement that the change answered it, a later assessment -- and it holds
**none** of this. **Nothing in the product answered "what did the author
say, and why"**, and the answer is the half that carries the reasoning.

**A reply is a record of what was said, and not a judgement.** So the
reply row itself writes no state, no decider and no evidence: **a verdict
bolted onto the row that holds the words would let a record of what was
said be read as a ruling.** What the record still needed was the
*judgement over it* -- did the authors' answer settle the reviewer's
point, and on what evidence -- and that judgement lives here too, behind
its own table and its own door (:func:`settle_reply`,
:func:`list_reply_settlements`, :func:`list_unsettled_replies`). The
door is the same one ``labcairn.papers.responses`` opens for the chain's
own judgement: a state other than ``pending`` needs a decider and the
evidence behind it, and a model may put a settlement forward but may not
decide one. A settled settlement says only what the schema can check --
that the answer's claimed terms are findable in the manuscript's
accepted text -- and **never says the science was right**, because that
is a claim no row in the store can carry.

**And a reply is neither the mentor's exchange nor the student's.** The
two halves are a *reviewer* and *the authors*, and they are the paper's
own review history. **So the permission that governs a reply is the
permission on the material the reply was read from** -- the response
document the version names -- and it is asked here, where that material is
named, exactly as ``record_feedback`` asks it.

**The pairing is the caller's, and the words are the document's.**
Deciding that one paragraph answers another is a judgement, and the
project's rule is that a judgement names its decider; the product has
no business guessing it. So :func:`record_replies` takes **where** the
two halves were read and reads the words itself: **a caller never types
a reply's text.** The exchange is named by two paragraph numbers, and the
product supplies the objection, the answer and their hashes.

**And the objection is a copy, not a reference.** The chain already holds
comments, and an objection is a kind of comment -- so the obvious design
would be a foreign key to ``feedback_events``. It is not one, because a
comment the chain holds is the *advisor's* remark *in a manuscript*: it
names the version it was written against, and a row that was read carries
the locator the reader read. **A reviewer's objection in a response
letter names no version**, and the place it points at is a line in a
rendering the corpus does not hold. Pointing at a comment would mean
inventing a version and an address the material does not have.

**What that costs.** The objection's words are held here, and in other
cases they are held in the chain's comment table as well: a second
spelling of something the chain may also hold. The price is paid
knowingly, and it is these three: the reply cannot be joined to
``feedback_events`` to say "this reply answers that comment"; it carries
no issue key; and the chain's ``set_issue_key`` does not reach it.

**And the row carries no address into the manuscript under review,
because there is none to carry.** The objections in this family address
lines in a rendering the corpus does not hold. **The place the objection
points at lives in the objection's own words and nowhere else**, and a
row that named a place there would be inventing an address the file does
not have.

**The parties are the reply's own.** ``reviewer`` and ``author``, and not
the chain's ``actor_kind``: that vocabulary answers "who acted in the
mentor's chain", and a peer reviewer of a submitted manuscript is neither
the mentor nor the student. **A value coerced into it would be a wrong
value**, and ``human`` on both halves would be worse than wrong: it would
say "two people spoke" and be unable to say which was which.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from labcairn.application import consent
from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import (
    ApplicationRefusal,
    ApplicationRefusedError,
    chain_refused,
)
from labcairn.db.models import ReplyRow, ReplySettlementRow, ResponseLinkRow
from labcairn.material.ooxml import read_document
from labcairn.papers.chain import (
    ChainRefusal,
    feedback_row,
    material_relative_path,
    project_row,
    version_row,
)
from labcairn.security.capabilities import CapabilityId
from labcairn.security.paths import CanonicalPath

#: **The two parties a reply has.** A closed vocabulary, and it is the
#: reply's own: the chain's ``actor_kind`` answers "who acted in the
#: mentor's chain", and neither of these two is the mentor. **The row
#: says which party said which half**, because a row that said only "two
#: people spoke" would throw away the whole content of a reply.
REPLY_PARTIES: frozenset[str] = frozenset({"reviewer", "author"})

#: **How a pairing was established.** ``observed`` is the document's own
#: structure saying so, ``inferred`` is the system's proposal, and
#: ``human_verified`` is a person who confirmed it.
#:
#: **It grades the pairing and not the words.** The words are always the
#: document's -- this module has no other source for them -- so the
#: chain's ``grade``, which says how a row's *content* was obtained, has
#: nothing to grade here. What varies is how the pairing was established.
PAIRING_GRADES: frozenset[str] = frozenset({"observed", "inferred", "human_verified"})

#: The ceiling on a document this operation will read. **A ceiling, and
#: not a hope**: the file's size is measured before the bytes are read, so
#: a file that is too large is refused rather than read and then refused.
#:
#: **Raised from 64 MB on 2026-11-03**, with :mod:`labcairn.papers.feedback`:
#: the third pilot's late drafts are 71.4 MB, and the old ceiling refused
#: seven versions of one real manuscript. See that module's constant for
#: the measurement and the reasoning; the two ceilings are the same number
#: deliberately.
MAX_MANUSCRIPT_BYTES = 96_000_000


@dataclass(frozen=True, slots=True)
class ReplyExchange:
    """One exchange, named by the two places in the document it was read from.

    **The two numbers are the whole of the caller's contribution to the
    words.** The objection and the answer are read out of the document
    itself, so a caller never types them and cannot type them wrongly.

    **And the parties are named, because a reply is an exchange between
    two of them.** The caller says which party wrote which half, and the
    schema refuses a row whose two halves are the same party.
    """

    #: The paragraph the objection was read from, in the document's own
    #: order. **Not a place in the manuscript under review** -- the
    #: material does not have one.
    objection_paragraph: int
    #: Who wrote the objection: ``reviewer`` or ``author``.
    objection_party: str
    #: The paragraph the answer was read from.
    answer_paragraph: int
    #: Who wrote the answer: ``reviewer`` or ``author``.
    answer_party: str
    #: How this pairing was established.
    pairing_grade: str = "observed"


@dataclass(frozen=True, slots=True)
class Reply:
    """One exchange, as the store holds it.

    **Both halves travel together**, and so do the parties that wrote
    them: a reader asking what the authors said in answer to a reviewer
    wants the objection, the answer and who said which, and a row that
    kept one half would be half an answer to the question.
    """

    reply_id: str
    project_id: str
    version_id: str
    objection_party: str
    objection_text: str
    objection_text_sha256: str
    objection_paragraph: int
    answer_party: str
    answer_text: str
    answer_text_sha256: str
    answer_paragraph: int
    pairing_grade: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class _Planned:
    """One exchange, read out of the document and checked against the rows.

    **The whole plan is made before anything is written.** The words are
    read, the rows already there are looked up, and every conflict is
    found -- and only then is a row added. **So a document half-recorded
    is a document nobody can count**, and a refusal leaves nothing behind
    for a later commit to pick up.
    """

    exchange: ReplyExchange
    reply_id: str
    objection: str
    objection_hash: str
    answer: str
    answer_hash: str
    #: The row that is already there, or ``None`` when there is none.
    existing: ReplyRow | None


def _sha256(text: str) -> str:
    """The hash of a text, as the chain hashes its words."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _reply_id(version_id: str, objection_paragraph: int, answer_paragraph: int) -> str:
    """The id of one exchange, derived.

    **Derived, so recording the same document twice is the same rows.**
    The two paragraphs name one exchange inside one document, and a
    version is a fixed set of bytes -- so the name is stable for ever,
    and it does not depend on the order the exchanges were read in.
    """
    digest = hashlib.sha256(
        f"{version_id}\x00{objection_paragraph}\x00{answer_paragraph}".encode()
    ).hexdigest()
    return f"rp-{digest[:16]}"


def _reply_from_row(row: ReplyRow) -> Reply:
    """The record a row is."""
    return Reply(
        reply_id=row.reply_id,
        project_id=row.project_id,
        version_id=row.version_id,
        objection_party=row.objection_party,
        objection_text=row.objection_text,
        objection_text_sha256=row.objection_text_sha256,
        objection_paragraph=row.objection_paragraph,
        answer_party=row.answer_party,
        answer_text=row.answer_text,
        answer_text_sha256=row.answer_text_sha256,
        answer_paragraph=row.answer_paragraph,
        pairing_grade=row.pairing_grade,
        created_at=row.created_at,
    )


def _require_version(context: ApplicationContext, project_id: str, version_id: str) -> None:
    """Refuse a version that is not there, or is not this project's.

    :raises ApplicationRefusedError: no such project, no such version, or
        a version that belongs to another project.
    """
    session = context.store.session
    if project_row(session, project_id) is None:
        raise chain_refused(
            ChainRefusal.PROJECT_NOT_FOUND,
            f"the store holds no paper project with the id {project_id!r}. A reply "
            "belongs to a manuscript, and a reply about a manuscript nobody holds is "
            "a reply about nothing.",
        )
    version = version_row(session, version_id)
    if version is None:
        raise chain_refused(
            ChainRefusal.VERSION_NOT_FOUND,
            f"the store holds no manuscript version with the id {version_id!r}. A "
            "reply is read out of a document, and a reply read out of a document "
            "nobody holds is a reply about nothing.",
        )
    if version.project_id != project_id:
        raise chain_refused(
            ChainRefusal.VERSION_NOT_FOUND,
            f"the manuscript version {version_id!r} belongs to the project "
            f"{version.project_id!r}, not to {project_id!r}. A reply is recorded "
            "against the project its document belongs to.",
        )


def _material(context: ApplicationContext, version_id: str) -> CanonicalPath:
    """The material a version was made from, as a resource.

    :raises ApplicationRefusedError: the version names material the ledger
        does not hold.
    """
    relative_path = material_relative_path(context.store.session, version_id)
    if relative_path is None:
        raise chain_refused(
            ChainRefusal.SOURCE_NOT_FOUND,
            f"the manuscript version {version_id!r} names material the ledger does "
            "not hold. A reply is read out of a document, and a reply read out of a "
            "document nobody has is a reply about nothing.",
        )
    return context.resource_for(relative_path)


def _read_material(context: ApplicationContext, version_id: str) -> bytes:
    """The bytes of the document a version was made from.

    **And the bytes are checked against the version's own hash.** The
    version names a document *and* the bytes it was recorded with, and a
    document whose bytes have changed under the name is not the one the
    paragraph numbers would name.
    """
    resource = _material(context, version_id)
    try:
        size = resource.real_path.stat().st_size
    except OSError as error:
        raise chain_refused(
            ChainRefusal.MATERIAL_UNREADABLE,
            f"the document {resource.resolved_key!r} could not be read: {error}. "
            "Unreadable is not the same as empty: a reply in a file nobody can open "
            "is not a reply the chain can claim to have found.",
        ) from error
    if size > MAX_MANUSCRIPT_BYTES:
        raise chain_refused(
            ChainRefusal.MATERIAL_UNREADABLE,
            f"the document {resource.resolved_key!r} is {size} bytes, and this "
            f"operation reads at most {MAX_MANUSCRIPT_BYTES}. The file is measured "
            "before it is read, so a document too large to read is refused rather "
            "than read and then refused.",
        )
    try:
        data = resource.real_path.read_bytes()
    except OSError as error:
        raise chain_refused(
            ChainRefusal.MATERIAL_UNREADABLE,
            f"the document {resource.resolved_key!r} could not be read: {error}. "
            "Unreadable is not the same as empty.",
        ) from error
    version = version_row(context.store.session, version_id)
    assert version is not None  # the version was resolved above
    expected = version.source_content_sha256
    if expected is None:
        raise chain_refused(
            ChainRefusal.MATERIAL_DRIFTED,
            f"the manuscript version {version_id!r} names no bytes. A version is the "
            "set of bytes it was recorded with, and an exchange read out of bytes "
            "nobody recorded would be an exchange about a document that cannot be "
            "named.",
        )
    if hashlib.sha256(data).hexdigest() != expected:
        raise chain_refused(
            ChainRefusal.MATERIAL_DRIFTED,
            f"the bytes now at {resource.resolved_key!r} are not the bytes the "
            f"version {version_id!r} was made from. The version names a document, "
            "and a document that has changed under the name is not the one the "
            "paragraph numbers would name; nothing was recorded against it.",
        )
    return data


def _check_exchange(exchange: ReplyExchange) -> None:
    """Refuse an exchange that names something a reply may not be.

    :raises ApplicationRefusedError: a party outside the vocabulary, a
        pairing grade outside the vocabulary, or two halves in the wrong
        order.
    """
    for party in (exchange.objection_party, exchange.answer_party):
        if party not in REPLY_PARTIES:
            raise ApplicationRefusedError(
                ApplicationRefusal.ARGUMENTS_INVALID,
                f"{party!r} is not a party a reply may hold. A reply is an exchange "
                "between a reviewer and the authors, and the chain's own vocabulary "
                "cannot say what these two are: it answers 'who acted in the "
                "mentor's chain', and a peer reviewer of a submitted manuscript is "
                "neither the mentor nor the student.",
            )
    if exchange.pairing_grade not in PAIRING_GRADES:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"{exchange.pairing_grade!r} is not a way a pairing may be established. "
            "A pairing is observed when the document states it, inferred when the "
            "system proposed it, and human-verified when a person confirmed it.",
        )
    if exchange.objection_paragraph < 0 or exchange.answer_paragraph < 0:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"a paragraph number may not be negative (the exchange names "
            f"{exchange.objection_paragraph!r} and {exchange.answer_paragraph!r}).",
        )
    if exchange.objection_paragraph >= exchange.answer_paragraph:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the objection is in paragraph {exchange.objection_paragraph!r} and the "
            f"answer in paragraph {exchange.answer_paragraph!r}. An exchange is read "
            "in the order the document has it: the objection comes before the "
            "answer.",
        )


def record_replies(
    context: ApplicationContext,
    *,
    project_id: str,
    version_id: str,
    exchanges: Sequence[ReplyExchange],
    now: datetime,
) -> tuple[Reply, ...]:
    """Read the document a version was made from, and record its exchanges.

    **The caller names the two places and the product reads the words.**
    That split is the point: the pairing is a judgement and the caller
    makes it, and the words are a fact about the file and the product
    supplies them. **So a caller never types a reply's text.**

    **One row per exchange, and recording the same version twice is the
    same rows.** The ids are derived from the version and the two
    paragraphs, so a second reading of the same bytes finds the rows that
    are already there. **A row whose words no longer match is a stale
    anchor, and it is refused** rather than silently re-pointed -- the
    document's bytes changed under it, and re-pointing it would make the
    record say something the file does not say.

    :raises ApplicationRefusedError: the project or the version is not
        there; the material is missing, unreadable or drifted; the policy
        denied reading it; an exchange names something a reply may not be;
        or an anchor is stale.
    """
    session = context.store.session
    _require_version(context, project_id, version_id)
    for exchange in exchanges:
        _check_exchange(exchange)
    resource = _material(context, version_id)
    consent.evaluate(
        context,
        capability=CapabilityId.SOURCE_READ,
        arguments={"max_bytes": MAX_MANUSCRIPT_BYTES},
        resource=resource,
    )
    data = _read_material(context, version_id)
    paragraphs = read_document(data).paragraphs

    # **Everything that can be refused is refused before anything is
    # written.** The words are read and the rows already there are checked
    # in one pass, so a document half-recorded is a document nobody can
    # count -- and a refusal leaves nothing behind for a later commit to
    # pick up.
    planned: list[_Planned] = []
    seen: set[str] = set()
    for exchange in exchanges:
        objection = _paragraph_at(paragraphs, exchange.objection_paragraph)
        answer = _paragraph_at(paragraphs, exchange.answer_paragraph)
        objection_hash = _sha256(objection)
        answer_hash = _sha256(answer)
        reply_id = _reply_id(version_id, exchange.objection_paragraph, exchange.answer_paragraph)
        if reply_id in seen:
            raise ApplicationRefusedError(
                ApplicationRefusal.ARGUMENTS_INVALID,
                f"the exchange between paragraphs {exchange.objection_paragraph!r} and "
                f"{exchange.answer_paragraph!r} is named twice. One exchange is one "
                "row, and a caller that means to record it twice is answered by the "
                "second call finding the row the first one wrote.",
            )
        seen.add(reply_id)
        existing = session.get(ReplyRow, reply_id)
        if existing is not None:
            if (
                existing.objection_text_sha256 != objection_hash
                or existing.answer_text_sha256 != answer_hash
            ):
                raise chain_refused(
                    ChainRefusal.ANCHOR_STALE,
                    f"the reply {reply_id!r} was recorded against words hashing to "
                    f"{existing.objection_text_sha256} and {existing.answer_text_sha256}, "
                    "and the document now reads differently. The anchor is stale, and a "
                    "stale anchor is reported as stale rather than silently "
                    "re-pointed.",
                )
            if existing.pairing_grade != exchange.pairing_grade:
                raise ApplicationRefusedError(
                    ApplicationRefusal.ARGUMENTS_INVALID,
                    f"the reply {reply_id!r} was recorded with the pairing graded "
                    f"{existing.pairing_grade!r}, and it is now offered as "
                    f"{exchange.pairing_grade!r}. A pairing's grade is a fact about "
                    "how it was established, and a change of it is a correction: this "
                    "table holds one version of a reply, and a confirmation is a new "
                    "record that it has nowhere to put.",
                )
        planned.append(
            _Planned(
                exchange=exchange,
                reply_id=reply_id,
                objection=objection,
                objection_hash=objection_hash,
                answer=answer,
                answer_hash=answer_hash,
                existing=existing,
            )
        )

    recorded: list[Reply] = []
    fresh: list[ReplyRow] = []
    for plan in planned:
        if plan.existing is not None:
            recorded.append(_reply_from_row(plan.existing))
            continue
        exchange = plan.exchange
        row = ReplyRow(
            reply_id=plan.reply_id,
            project_id=project_id,
            version_id=version_id,
            objection_party=exchange.objection_party,
            objection_text=plan.objection,
            objection_text_sha256=plan.objection_hash,
            objection_paragraph=exchange.objection_paragraph,
            answer_party=exchange.answer_party,
            answer_text=plan.answer,
            answer_text_sha256=plan.answer_hash,
            answer_paragraph=exchange.answer_paragraph,
            pairing_grade=exchange.pairing_grade,
            created_at=now,
        )
        session.add(row)
        fresh.append(row)
        recorded.append(_reply_from_row(row))
    if fresh:
        # **The rows land together.** A document half-recorded is a document
        # nobody can count.
        session.commit()
    return tuple(recorded)


def _paragraph_at(paragraphs: tuple[str, ...], index: int) -> str:
    """The text of one paragraph of the document, as the reader reports it.

    :raises ApplicationRefusedError: the document has no such paragraph.
    """
    if index >= len(paragraphs):
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the document has {len(paragraphs)} paragraph(s) and the exchange names "
            f"paragraph {index!r}. The paragraph numbers name places in the document "
            "as it reads, and a place the document does not have is not a place.",
        )
    return paragraphs[index]


def list_replies(
    context: ApplicationContext,
    *,
    project_id: str,
    version_id: str | None = None,
) -> tuple[Reply, ...]:
    """The exchanges the chain holds about a project, or about one version.

    **Denied material is dropped, not refused.** ADR-0003 C5 asks a bulk
    listing to filter denied entries out of its results rather than
    refusing the call, because refusing the whole listing discloses that
    something is there and denies work the operator wanted allowed.

    **And the rows come back in the order the document has them** --
    ordered by the paragraph the objection was read from and then by the
    paragraph the answer was read from, which is the order a person
    reading the document would meet them in. **The second key is not
    decoration**: two exchanges may answer the same objection, and an
    order that stopped at the objection would leave their order to the
    storage engine's.

    :raises ApplicationRefusedError: the project is not there, or the
        arguments are not usable.
    """
    session = context.store.session
    if project_row(session, project_id) is None:
        raise chain_refused(
            ChainRefusal.PROJECT_NOT_FOUND,
            f"the store holds no paper project with the id {project_id!r}.",
        )
    statement = select(ReplyRow).where(ReplyRow.project_id == project_id)
    if version_id is not None:
        statement = statement.where(ReplyRow.version_id == version_id)
    rows = tuple(
        session.scalars(
            statement.order_by(
                ReplyRow.version_id,
                ReplyRow.objection_paragraph,
                ReplyRow.answer_paragraph,
            )
        )
    )
    if not rows:
        return ()
    materials: dict[str, CanonicalPath | None] = {}
    for row in rows:
        if row.version_id not in materials:
            materials[row.version_id] = _material_or_none(context, row.version_id)
    present = tuple(resource for resource in materials.values() if resource is not None)
    permitted = consent.evaluate_each(
        context,
        capability=CapabilityId.SOURCE_INVENTORY,
        arguments={},
        resources=present,
    )
    allowed = {resource.resolved_key for resource in permitted}
    kept = [
        row
        for row in rows
        for resource in (materials[row.version_id],)
        if resource is not None and resource.resolved_key in allowed
    ]
    return tuple(_reply_from_row(row) for row in kept)


def _material_or_none(context: ApplicationContext, version_id: str) -> CanonicalPath | None:
    """The material a version was made from, or ``None`` when there is none.

    **``None`` rather than a refusal**, because a listing asks "what does
    the chain hold" and a version whose file the ledger does not hold has
    nothing to show. The refusal belongs to the operation that *writes*.
    """
    relative_path = material_relative_path(context.store.session, version_id)
    if relative_path is None:
        return None
    return context.resource_for(relative_path)


# --------------------------------------------------------------------------- #
# The settlement: the judgement that an answer settled a reviewer's point     #
#                                                                             #
# **The reply is a record, and the settlement is a judgement.** The row       #
# above holds what two parties said and holds no verdict -- that absence is   #
# the design, and it stays. What a reader still cannot ask the store is       #
# *did the authors' answer settle the point*, and this is the judgement       #
# that answers it. It goes through the same door as ``record_response``:      #
# a state other than ``pending`` needs a decider and the evidence behind      #
# it, and a model may put a settlement forward but may not decide one.        #
# **The verdict lives in its own table, never on the row that holds the       #
# words.**                                                                    #
# --------------------------------------------------------------------------- #

#: The four states a settlement may hold. **Only ``pending`` says nobody
#: has judged.** ``settled`` says the answer settled the point and the
#: manuscript holds what the answer claims; ``held`` says the claim could
#: not be found and names what it is holding for; ``unresolved`` says the
#: judgement went the other way. **``settled`` does not say the science
#: was right** -- it says the claimed thing is findable in the
#: manuscript's accepted text, and no wider a claim than that.
SETTLEMENT_STATES: frozenset[str] = frozenset({"pending", "settled", "held", "unresolved"})

#: Who may decide a settlement. **A model may not**: a rule or a person
#: settles whether an author's answer settled a reviewer's point.
SETTLEMENT_DECIDERS: frozenset[str] = frozenset({"rule", "user"})

#: Who may **put a settlement forward**. A model's candidate is
#: ``pending`` at grade ``inferred`` -- a claim about what the model
#: proposed, and not a judgement.
SETTLEMENT_PROPOSERS: frozenset[str] = frozenset({"model", "user"})

#: The grades a settlement may carry.
SETTLEMENT_GRADES: frozenset[str] = frozenset({"observed", "human_verified", "inferred"})

#: Whether the change the answer claims has been placed in the
#: manuscript. **A missing address is a value, never a guess**: a
#: settlement that could not place the change says ``unknown``, and the
#: schema holds the two address columns to agree with it in both
#: directions.
ANCHOR_STATUSES: frozenset[str] = frozenset({"resolved", "unknown"})

#: Why a reply is on the unsettled listing. **A reply the chain holds no
#: settlement for is listed as ``unjudged``** -- an answer that was never
#: judged does not make the point answered -- and a reply whose settlement
#: is pending, held or unresolved is listed for the state it is in. Only
#: ``settled`` keeps a reply off the listing.
UNSETTLED_REASONS: frozenset[str] = frozenset({"unjudged", "pending", "held", "unresolved"})


@dataclass(frozen=True, slots=True)
class ReplySettlement:
    """One judgement about one exchange, as the store records it.

    **And the chain's own side travels with it when the two are about the
    same point.** ``chain_states`` holds the states of every response link
    the chain holds for the comment this settlement says the reply is
    about -- **all of them**, because a disagreement between the mentor's
    judgement and this one is shown as two sides, and a product that kept
    only the newer of the two would be deciding a disagreement by recency.
    It is a read-side join and not a column: the correspondence is part of
    the judgement, the chain's verdicts are the chain's, and neither is
    stored in the other's table.
    """

    settlement_id: str
    reply_id: str
    state: str
    grade: str
    decided_by: str | None
    decided_at: datetime | None
    evidence_refs: tuple[str, ...]
    #: The words a settled judgement vouches for, each of which the
    #: operation found in the manuscript's accepted text before the row
    #: was written.
    claim_terms: tuple[str, ...]
    change_version_id: str | None
    change_paragraph: int | None
    anchor_status: str
    feedback_id: str | None
    hold_reason: str | None
    created_at: datetime
    chain_states: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class UnsettledReply:
    """A reply whose point is not settled, and why it is listed.

    **The reason is part of the answer.** A reply the store holds no
    settlement for, a settlement nobody has judged, a hold, and a
    judgement that went the other way are four different situations, and
    a reader asking "what has not been settled?" wants to tell them
    apart.
    """

    reply: Reply
    reason: str


def _settlement_from_row(
    row: ReplySettlementRow, chain_states: tuple[str, ...] = ()
) -> ReplySettlement:
    """The record a row is."""
    return ReplySettlement(
        settlement_id=row.settlement_id,
        reply_id=row.reply_id,
        state=row.state,
        grade=row.grade,
        decided_by=row.decided_by,
        decided_at=row.decided_at,
        evidence_refs=tuple(row.evidence_refs),
        claim_terms=tuple(row.claim_terms),
        change_version_id=row.change_version_id,
        change_paragraph=row.change_paragraph,
        anchor_status=row.anchor_status,
        feedback_id=row.feedback_id,
        hold_reason=row.hold_reason,
        created_at=row.created_at,
        chain_states=chain_states,
    )


def _manuscript_paragraphs(context: ApplicationContext, version_id: str) -> tuple[str, ...]:
    """The paragraphs of the manuscript a version names, after the gate.

    **The bytes are checked against the version's own hash** -- the
    version names a manuscript *and* the bytes it was recorded with, and
    a manuscript whose bytes have changed under the name is not the one
    the coordinates would name.

    :raises ApplicationRefusedError: the version names material the
        ledger does not hold, the policy denied reading it, the material
        is unreadable, or the bytes have drifted.
    """
    resource = _material(context, version_id)
    consent.evaluate(
        context,
        capability=CapabilityId.SOURCE_READ,
        arguments={"max_bytes": MAX_MANUSCRIPT_BYTES},
        resource=resource,
    )
    return read_document(_read_material(context, version_id)).paragraphs


def _claims_not_found(paragraphs: tuple[str, ...], claim_terms: Sequence[str]) -> tuple[str, ...]:
    """The claim terms the manuscript's accepted text does not hold.

    **A term is found when its words appear in the text**, matched
    case-insensitively and without a guess at morphology: a claim of "we
    ran the Gibbs sampler" is answered by the sampler being named in the
    manuscript, and a manuscript that names no such thing settles
    nothing.
    """
    text = "\n".join(paragraphs).casefold()
    return tuple(term for term in claim_terms if term.casefold() not in text)


def _verify_change_address(
    context: ApplicationContext,
    *,
    change_version_id: str,
    change_paragraph: int,
) -> tuple[str, ...]:
    """The paragraphs of the manuscript, after the named place is checked.

    **A place in the manuscript is this judgement's to give, and a place
    the manuscript does not have is not a place.**

    :raises ApplicationRefusedError: the manuscript could not be read, or
        names no such paragraph.
    """
    paragraphs = _manuscript_paragraphs(context, change_version_id)
    if change_paragraph < 0 or change_paragraph >= len(paragraphs):
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the manuscript has {len(paragraphs)} paragraph(s) and the settlement "
            f"places the change at paragraph {change_paragraph!r}. A missing address "
            "is a value -- anchor_status 'unknown' -- and an address that names no "
            "place is not an address.",
        )
    return paragraphs


def settle_reply(
    context: ApplicationContext,
    *,
    settlement_id: str,
    reply_id: str,
    state: str,
    grade: str = "observed",
    decided_by: str | None = None,
    decided_at: datetime | None = None,
    evidence_refs: tuple[str, ...] = (),
    claim_terms: tuple[str, ...] = (),
    change_version_id: str | None = None,
    change_paragraph: int | None = None,
    anchor_status: str = "unknown",
    feedback_id: str | None = None,
    hold_reason: str | None = None,
    now: datetime,
) -> ReplySettlement:
    """Record the judgement that an author's answer settled a review point.

    **A settlement is a judgement, and it goes through the same door as
    ``record_response``.** A state other than ``pending`` needs a decider
    and the evidence behind it, and a model may put a settlement forward
    -- ``state='pending'``, ``grade='inferred'``, ``decided_by='model'``
    -- but may not decide one. A status anybody can set is not a status.

    **And a point is judged once.** A reply that has already been judged
    is refused rather than judged again: a judgement is a fact, and a
    second judgement over the same reply is a revision of a fact, which
    the store does not hold. A pending settlement is completed by the
    judgement that decides it.

    **And a settled judgement has found what the answer claims.** The
    whole point of settling is that what the answer claims can be found
    in the manuscript's accepted text: a settled settlement names its
    ``claim_terms``, and the operation reads the manuscript and checks
    every one of them before the row is written. **A claim the manuscript
    does not hold is refused, by name** -- the refusal says which term
    was not found -- and never silently accepted. The caller's honest
    path past that refusal is ``held``: state the claim is not found, and
    name what the hold is holding for. **And what ``settled`` says is
    narrow by design: the claimed thing is findable in the manuscript.
    It does not say the science was right, and nothing in the settlement
    carries that.**

    **And the place of the change is a value, never a guess.** A
    settlement either places the change -- ``anchor_status='resolved'``,
    with the version and the paragraph of the manuscript it lives in --
    or says ``unknown``, and the two address columns are held to agree
    with the status in both directions.

    **And the correspondence with the chain's own comment is part of the
    judgement.** ``feedback_id`` names the comment the decider judged
    this reply to be about; the reply carries no issue key and nobody
    derived one. A reader asking whether the chain and the settlement
    agree gets both sides -- the listing joins the chain's verdicts in,
    and reports a disagreement rather than resolving it.

    :raises ApplicationRefusedError: the reply, the chain comment or the
        manuscript version is not there; the state, the grade, the
        decider or the anchor status is outside its vocabulary; a decided
        settlement has no evidence behind it; a model tried to decide;
        the reply has already been judged; a settled settlement's claim
        is not in the manuscript's accepted text; the change is placed at
        a paragraph the manuscript does not have; or the policy denied
        reading the manuscript.
    """
    session = context.store.session
    if state not in SETTLEMENT_STATES:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"{state!r} is not a state a settlement may hold. A settlement is "
            "pending, settled, held or unresolved, and a state outside those four "
            "says nothing about whether the answer settled the point.",
        )
    if grade not in SETTLEMENT_GRADES:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"{grade!r} is not a grade. A judgement is observed, confirmed by a "
            "person, or the system's own inference.",
        )
    if anchor_status not in ANCHOR_STATUSES:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"{anchor_status!r} is not an anchor status. A settlement either places "
            "the change -- 'resolved', with the version and the paragraph of the "
            "manuscript it lives in -- or says 'unknown' that it could not.",
        )
    if decided_by is not None and decided_by not in (SETTLEMENT_DECIDERS | SETTLEMENT_PROPOSERS):
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"{decided_by!r} is not a decider. A settlement is decided by a rule, "
            "by a person, or put forward by a model.",
        )
    reply = session.get(ReplyRow, reply_id)
    if reply is None:
        raise chain_refused(
            ChainRefusal.REPLY_NOT_FOUND,
            f"the store holds no reply with the id {reply_id!r}. A settlement "
            "judges an exchange, and a settlement of an exchange nobody holds is "
            "a settlement about nothing.",
        )
    if feedback_id is not None and feedback_row(session, feedback_id) is None:
        raise chain_refused(
            ChainRefusal.FEEDBACK_NOT_FOUND,
            f"the store holds no feedback event with the id {feedback_id!r}. The "
            "correspondence between a reply and a chain comment is part of the "
            "judgement, and a correspondence with a comment nobody holds is a "
            "correspondence with nothing.",
        )
    if change_version_id is not None:
        change_version = version_row(session, change_version_id)
        if change_version is None:
            raise chain_refused(
                ChainRefusal.VERSION_NOT_FOUND,
                f"the store holds no manuscript version with the id "
                f"{change_version_id!r}. A settlement that places the change names "
                "the manuscript the change lives in, and a place in a manuscript "
                "nobody holds is a place about nothing.",
            )
        if change_version.project_id != reply.project_id:
            raise chain_refused(
                ChainRefusal.VERSION_NOT_FOUND,
                f"the manuscript version {change_version_id!r} belongs to the "
                f"project {change_version.project_id!r}, not to "
                f"{reply.project_id!r}. The change an answer claims lives in the "
                "manuscript the reply's project is about.",
            )
    existing = session.scalar(
        select(ReplySettlementRow).where(ReplySettlementRow.reply_id == reply_id)
    )
    if existing is not None and existing.state != "pending":
        raise chain_refused(
            ChainRefusal.SETTLEMENT_ALREADY_DECIDED,
            f"the reply {reply_id!r} was judged on {existing.decided_at} by "
            f"{existing.decided_by!r} and stands at {existing.state!r}. A judgement "
            "is a fact, and a second judgement over the same reply is a revision of "
            "a fact, which the store does not hold.",
        )
    if existing is not None and settlement_id != existing.settlement_id:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the reply {reply_id!r} has a settlement on the record as "
            f"{existing.settlement_id!r}. Judging it completes that settlement; it "
            "does not rename it.",
        )
    if state == "pending":
        if decided_by == "model" and grade != "inferred":
            raise ApplicationRefusedError(
                ApplicationRefusal.ARGUMENTS_INVALID,
                f"the settlement {settlement_id!r} is put forward by a model and "
                "graded "
                f"{grade!r}. A model's candidate is a proposal, and a proposal is "
                "graded 'inferred'; a settlement graded otherwise was not put "
                "forward by a model.",
            )
        if decided_by == "user" and grade == "inferred":
            raise ApplicationRefusedError(
                ApplicationRefusal.ARGUMENTS_INVALID,
                f"the settlement {settlement_id!r} is put forward by a person and "
                "graded 'inferred'. A person's proposal is 'observed'; 'inferred' "
                "is the system's grade.",
            )
        if decided_at is not None or evidence_refs or claim_terms:
            raise ApplicationRefusedError(
                ApplicationRefusal.ARGUMENTS_INVALID,
                f"the settlement {settlement_id!r} is pending and carries a "
                "decision's trappings. A pending settlement is a question somebody "
                "put forward: it has no moment, no evidence and no claim it has "
                "checked, because nothing has been decided yet.",
            )
        if hold_reason is not None:
            raise ApplicationRefusedError(
                ApplicationRefusal.ARGUMENTS_INVALID,
                f"the settlement {settlement_id!r} is pending and carries a hold "
                "reason. A hold is a judgement, and a pending settlement is not "
                "one yet.",
            )
    else:
        if decided_by == "model":
            raise chain_refused(
                ChainRefusal.SETTLEMENT_MAY_NOT_BE_DECIDED_BY_A_MODEL,
                f"the settlement {settlement_id!r} is decided by a model. A model "
                "may put a settlement forward -- that is a candidate, at grade "
                "'inferred' -- but only a rule or a person settles whether an "
                "author's answer settled a reviewer's point.",
            )
        if decided_by is None or decided_at is None or not evidence_refs:
            raise chain_refused(
                ChainRefusal.SETTLEMENT_NEEDS_EVIDENCE,
                f"the settlement {settlement_id!r} is {state!r} and names no "
                "decision, no moment and no evidence. A status anybody can set is "
                "not a status: a settlement that is not pending must say who "
                "decided it, when, and on what.",
            )
        if grade == "inferred":
            raise ApplicationRefusedError(
                ApplicationRefusal.ARGUMENTS_INVALID,
                f"the settlement {settlement_id!r} is decided by {decided_by!r} and "
                "graded 'inferred'. A judgement the system inferred and a judgement "
                "a person made are two different records, and one row cannot be "
                "both.",
            )
    if anchor_status == "resolved":
        if change_version_id is None or change_paragraph is None:
            raise ApplicationRefusedError(
                ApplicationRefusal.ARGUMENTS_INVALID,
                f"the settlement {settlement_id!r} says the change is resolved and "
                "names no place for it. An address is a value, never a guess: a "
                "settlement that could not place the change says 'unknown', and one "
                "that says 'resolved' names the version and the paragraph.",
            )
        assert change_paragraph is not None  # resolved was checked above
        paragraphs = _verify_change_address(
            context,
            change_version_id=change_version_id,
            change_paragraph=change_paragraph,
        )
    else:
        if change_version_id is not None or change_paragraph is not None:
            raise ApplicationRefusedError(
                ApplicationRefusal.ARGUMENTS_INVALID,
                f"the settlement {settlement_id!r} says the change could not be "
                "placed and names a place for it anyway. The status and the address "
                "agree in both directions, or the row does not hold.",
            )
        paragraphs = None
    if state == "settled":
        if not claim_terms or any(not term.strip() for term in claim_terms):
            raise ApplicationRefusedError(
                ApplicationRefusal.ARGUMENTS_INVALID,
                f"the settlement {settlement_id!r} is settled and names no claim. "
                "The whole point of settling is that what the answer claims can be "
                "found in the manuscript's accepted text, and a settled settlement "
                "that checked nothing has no check behind it.",
            )
        assert paragraphs is not None  # a settled settlement is resolved
        missing = _claims_not_found(paragraphs, claim_terms)
        if missing:
            raise chain_refused(
                ChainRefusal.CLAIM_NOT_IN_MANUSCRIPT,
                f"the settlement {settlement_id!r} claims the manuscript holds "
                f"{', '.join(repr(term) for term in claim_terms)}, and the "
                f"manuscript's accepted text holds none of "
                f"{', '.join(repr(term) for term in missing)}. An answer whose "
                "claim the manuscript does not bear out is not settled by this "
                "product: record it as held, and name what the hold is holding "
                "for.",
            )
    if state == "held" and (hold_reason is None or not hold_reason.strip()):
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the settlement {settlement_id!r} is held and names no reason. A hold "
            "that says only 'held' is a hold nobody can lift: it names the claim "
            "that could not be found, and what a later reader should look for.",
        )
    if existing is not None:
        row = existing
    else:
        row = ReplySettlementRow(
            settlement_id=settlement_id,
            reply_id=reply_id,
            created_at=now,
        )
        session.add(row)
    row.state = state
    row.grade = grade
    row.decided_by = decided_by
    row.decided_at = decided_at
    row.evidence_refs = list(evidence_refs)
    row.claim_terms = list(claim_terms)
    row.change_version_id = change_version_id
    row.change_paragraph = change_paragraph
    row.anchor_status = anchor_status
    row.feedback_id = feedback_id
    row.hold_reason = hold_reason
    session.commit()
    return _settlement_from_row(row)


def list_reply_settlements(
    context: ApplicationContext,
    *,
    project_id: str,
    version_id: str | None = None,
) -> tuple[ReplySettlement, ...]:
    """The settlements the chain holds about a project, or about one version.

    **And the chain's own verdicts travel with them.** A settlement that
    names a chain comment arrives carrying every state the chain holds
    for that comment, because a disagreement between the mentor's
    judgement and the settlement is shown as two sides -- **a product
    that kept only the newer of the two would be deciding a disagreement
    by recency, and that is a judgement the listing does not make.**

    **Denied material is dropped, not refused.** A settlement's
    visibility is the visibility of the reply it judges, and the reply's
    is the visibility of the document it was read from: ADR-0003 C5 asks
    a bulk listing to filter denied entries out of its results rather
    than refusing the call.

    :raises ApplicationRefusedError: the project is not there, or the
        arguments are not usable.
    """
    session = context.store.session
    if project_row(session, project_id) is None:
        raise chain_refused(
            ChainRefusal.PROJECT_NOT_FOUND,
            f"the store holds no paper project with the id {project_id!r}.",
        )
    statement = (
        select(ReplySettlementRow)
        .join(ReplyRow, ReplySettlementRow.reply_id == ReplyRow.reply_id)
        .where(ReplyRow.project_id == project_id)
    )
    if version_id is not None:
        statement = statement.where(ReplyRow.version_id == version_id)
    rows = tuple(session.scalars(statement.order_by(ReplySettlementRow.settlement_id)))
    if not rows:
        return ()
    materials: dict[str, CanonicalPath | None] = {}
    for row in rows:
        reply = session.get(ReplyRow, row.reply_id)
        assert reply is not None  # the settlement's reply_id is on the record
        if reply.version_id not in materials:
            materials[reply.version_id] = _material_or_none(context, reply.version_id)
    present = tuple(resource for resource in materials.values() if resource is not None)
    permitted = consent.evaluate_each(
        context,
        capability=CapabilityId.SOURCE_INVENTORY,
        arguments={},
        resources=present,
    )
    allowed = {resource.resolved_key for resource in permitted}
    kept = []
    for row in rows:
        reply = session.get(ReplyRow, row.reply_id)
        assert reply is not None  # the settlement's reply_id is on the record
        resource = materials[reply.version_id]
        if resource is not None and resource.resolved_key in allowed:
            kept.append(row)
    feedback_ids = {row.feedback_id for row in kept if row.feedback_id is not None}
    chain: dict[str, list[str]] = {}
    if feedback_ids:
        for link in session.scalars(
            select(ResponseLinkRow)
            .where(ResponseLinkRow.feedback_id.in_(feedback_ids))
            .order_by(ResponseLinkRow.response_link_id)
        ):
            chain.setdefault(link.feedback_id, []).append(link.state)
    return tuple(
        _settlement_from_row(
            row,
            chain_states=(tuple(chain[row.feedback_id]) if row.feedback_id is not None else ()),
        )
        for row in kept
    )


def list_unsettled_replies(
    context: ApplicationContext,
    *,
    project_id: str,
    version_id: str | None = None,
) -> tuple[UnsettledReply, ...]:
    """The replies whose points are not settled, and why each is listed.

    **An answer that was never judged does not make the point answered.**
    A reply the store holds no settlement for is listed as ``unjudged``,
    and a reply whose settlement is pending is listed as ``pending`` --
    the answer's words are on the record, and the question is still open.
    A hold and a judgement that went the other way are listed for the
    state they are in. **Only a settled settlement keeps a reply off this
    listing.**

    :raises ApplicationRefusedError: the project is not there, or the
        arguments are not usable.
    """
    session = context.store.session
    if project_row(session, project_id) is None:
        raise chain_refused(
            ChainRefusal.PROJECT_NOT_FOUND,
            f"the store holds no paper project with the id {project_id!r}.",
        )
    reply_statement = select(ReplyRow).where(ReplyRow.project_id == project_id)
    if version_id is not None:
        reply_statement = reply_statement.where(ReplyRow.version_id == version_id)
    replies = tuple(
        session.scalars(
            reply_statement.order_by(
                ReplyRow.version_id,
                ReplyRow.objection_paragraph,
                ReplyRow.answer_paragraph,
            )
        )
    )
    if not replies:
        return ()
    materials: dict[str, CanonicalPath | None] = {}
    for reply in replies:
        if reply.version_id not in materials:
            materials[reply.version_id] = _material_or_none(context, reply.version_id)
    present = tuple(resource for resource in materials.values() if resource is not None)
    permitted = consent.evaluate_each(
        context,
        capability=CapabilityId.SOURCE_INVENTORY,
        arguments={},
        resources=present,
    )
    allowed = {resource.resolved_key for resource in permitted}
    settlements = {row.reply_id: row for row in session.scalars(select(ReplySettlementRow))}
    listed: list[UnsettledReply] = []
    for reply in replies:
        resource = materials[reply.version_id]
        if resource is None or resource.resolved_key not in allowed:
            continue
        settlement = settlements.get(reply.reply_id)
        if settlement is None:
            listed.append(UnsettledReply(reply=_reply_from_row(reply), reason="unjudged"))
            continue
        if settlement.state in ("held", "unresolved", "pending"):
            listed.append(UnsettledReply(reply=_reply_from_row(reply), reason=settlement.state))
    return tuple(listed)


__all__ = [
    "ANCHOR_STATUSES",
    "MAX_MANUSCRIPT_BYTES",
    "PAIRING_GRADES",
    "REPLY_PARTIES",
    "SETTLEMENT_DECIDERS",
    "SETTLEMENT_GRADES",
    "SETTLEMENT_PROPOSERS",
    "SETTLEMENT_STATES",
    "UNSETTLED_REASONS",
    "Reply",
    "ReplyExchange",
    "ReplySettlement",
    "UnsettledReply",
    "list_replies",
    "list_reply_settlements",
    "list_unsettled_replies",
    "record_replies",
    "settle_reply",
]
