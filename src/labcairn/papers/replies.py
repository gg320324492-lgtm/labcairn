"""The reply: one party's answer to another's objection, read out of a document.

**What this module is.** The product's side of the fourth body of material
the feedback chain was given: a **reviewer's objection paired with the
authors' answer**, read out of a response document. The chain holds the
mentor's exchange -- a comment, the change made in answer to it, the
judgement that the change answered it, a later assessment -- and it holds
**none** of this. **Nothing in the product answered "what did the author
say, and why"**, and the answer is the half that carries the reasoning.

**A reply is a record of what was said, and not a judgement.** So this
module writes no state, no decider and no evidence: those belong to
``labcairn.papers.responses``, which answers the other question -- *did
the change answer the comment* -- and answers it with a verdict that
needs evidence behind it. **A reply has no verdict.** Two parties said
two things, and the table holds them.

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
from labcairn.db.models import ReplyRow
from labcairn.material.ooxml import read_document
from labcairn.papers.chain import (
    ChainRefusal,
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
MAX_MANUSCRIPT_BYTES = 64_000_000


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


__all__ = [
    "MAX_MANUSCRIPT_BYTES",
    "PAIRING_GRADES",
    "REPLY_PARTIES",
    "Reply",
    "ReplyExchange",
    "list_replies",
    "record_replies",
]
