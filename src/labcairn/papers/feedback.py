"""The feedback row: a comment found in a manuscript, with both addresses.

**What a feedback event is.** *A comment that a person wrote.* Not a claim
about the manuscript — a fact about the file's history, made by somebody.
That is why the chain has a table of its own rather than borrowing the
evidence ledger's vocabulary: a comment is not citable, and putting one
into the same denominator as a verified number would be a kind of lie.

**Two addresses, because two questions.** ``comment_locator`` names the
comment element in ``word/comments.xml`` — *what was written* — and the
anchor names the place in the body — *where it was written about*. A row
that kept only one would answer only one of them.

**And the anchor's offsets are into the baseline's text**, which is the
manuscript as it read *before* the revisions. The row therefore carries
the anchored text and its hash: the text and the offsets agree by
construction, and the hash is what makes a drifted anchor detectable.

**A comment that cannot be placed is still written.** Its body, its
author and the reason it could not be placed are all recorded, because a
comment the reader could not place is a comment a person still wrote.

**And a model may not write one.** A row read out of the file is
``observed`` and carries the locator the reader read. A row nobody read
is a candidate, and the chain refuses to let a candidate wear the
advisor's words.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from labcairn.application import consent
from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import chain_refused
from labcairn.db.models import FeedbackEventRow, PaperVersionRow
from labcairn.material.ooxml import read_document
from labcairn.papers.chain import (
    ChainRefusal,
    feedback_row,
    material_relative_path,
    material_source,
    project_row,
    project_version_rows,
    version_row,
)
from labcairn.security.capabilities import CapabilityId
from labcairn.security.paths import CanonicalPath
from labcairn.sources.locators import DocxLocator

#: The ceiling on a manuscript this operation will read. **A ceiling, and
#: not a hope**: the file's size is measured before the bytes are read, so
#: a file that is too large is refused rather than read and then refused.
MAX_MANUSCRIPT_BYTES = 64_000_000

#: The grades a feedback row may carry.
#:
#: **``observed`` is what the reader writes** and it is the only grade
#: this module produces. ``inferred`` and ``human_verified`` are the
#: other two of ADR-0014 D2's levels, and the schema knows them — but a
#: comment is a fact about a file, so only the reader may write one.
FEEDBACK_GRADES: frozenset[str] = frozenset({"observed", "inferred", "human_verified"})


@dataclass(frozen=True, slots=True)
class FeedbackEvent:
    """One comment, as the chain records it.

    **A fact about a file, and never a claim about the manuscript.** Every
    field here is something the reader saw or something the reader could
    not see — and "could not see" is recorded as an unknown with a reason,
    never as a guess.
    """

    feedback_id: str
    project_id: str
    version_id: str
    #: The comment's own address, or ``None`` on a row nobody read.
    comment_locator: DocxLocator | None
    anchor_paragraph: int | None
    anchor_start: int | None
    anchor_end: int | None
    anchor_status: str
    anchor_reason: str | None
    anchor_text: str
    anchor_text_sha256: str
    comment_text: str
    comment_text_sha256: str
    author: str | None
    author_unknown_reason: str | None
    commented_at: datetime | None
    date_unknown_reason: str | None
    grade: str
    issue_key: str | None


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _feedback_id(version_id: str, comment_id: str) -> str:
    """The id of the comment *comment_id* in the version *version_id*.

    **Derived, so recording the same comment twice is the same row.**
    The reader's own comment id is only unique inside one document, so
    the version is part of the key — and two rounds of the same manuscript
    hold two different comments with the same id.
    """
    digest = hashlib.sha256(f"{version_id}\x00{comment_id}".encode()).hexdigest()
    return f"fb-{digest[:16]}"


def _locator_json(locator: DocxLocator) -> str:
    """The locator as canonical JSON.

    **Canonical, so two readings of the same address produce the same
    bytes** — and so a row can be compared with another row without
    asking how each was spelled.
    """
    return json.dumps(locator.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def _locator_from_json(raw: str | None) -> DocxLocator | None:
    """The locator a row carries, or ``None`` when it carries none."""
    if raw is None:
        return None
    return DocxLocator.model_validate(json.loads(raw))


def event_from_row(row: FeedbackEventRow) -> FeedbackEvent:
    """The record a row is.

    **Public, because the response listing names the comments it found.**
    A listing that reported a row where the rest of the layer reports a
    record would be a listing that could not be compared with anything.
    """
    return FeedbackEvent(
        feedback_id=row.feedback_id,
        project_id=row.project_id,
        version_id=row.version_id,
        comment_locator=_locator_from_json(row.comment_locator),
        anchor_paragraph=row.anchor_paragraph,
        anchor_start=row.anchor_start,
        anchor_end=row.anchor_end,
        anchor_status=row.anchor_status,
        anchor_reason=row.anchor_reason,
        anchor_text=row.anchor_text,
        anchor_text_sha256=row.anchor_text_sha256,
        comment_text=row.comment_text,
        comment_text_sha256=row.comment_text_sha256,
        author=row.author,
        author_unknown_reason=row.author_unknown_reason,
        commented_at=row.commented_at,
        date_unknown_reason=row.date_unknown_reason,
        grade=row.grade,
        issue_key=row.issue_key,
    )


def _require_version(
    context: ApplicationContext, project_id: str, version_id: str
) -> PaperVersionRow:
    """The version the comment was written against, or a refusal.

    :raises ApplicationRefusedError: no such version, or no such project.
    """
    session = context.store.session
    if project_row(session, project_id) is None:
        raise chain_refused(
            ChainRefusal.PROJECT_NOT_FOUND,
            f"the store holds no paper project with the id {project_id!r}. A comment "
            "belongs to a manuscript, and a comment about a manuscript nobody holds is "
            "a comment about nothing.",
        )
    version = version_row(session, version_id)
    if version is None:
        raise chain_refused(
            ChainRefusal.VERSION_NOT_FOUND,
            f"the store holds no manuscript version with the id {version_id!r}. A "
            "feedback row names the version it was written against, because a comment "
            "that names no manuscript state cannot be said to have been answered by "
            "any change: there is no 'before' to have been answered against.",
        )
    if version.project_id != project_id:
        raise chain_refused(
            ChainRefusal.VERSION_NOT_FOUND,
            f"the manuscript version {version_id!r} belongs to the project "
            f"{version.project_id!r}, not to {project_id!r}. A comment is recorded "
            "against the project its manuscript belongs to.",
        )
    return version


def _material_of(context: ApplicationContext, version_id: str) -> CanonicalPath:
    """The material a version was made from, as a resource.

    :raises ApplicationRefusedError: the version names material the ledger
        does not hold, or the path is not admitted into the workspace.
    """
    relative_path = material_relative_path(context.store.session, version_id)
    if relative_path is None:
        raise chain_refused(
            ChainRefusal.SOURCE_NOT_FOUND,
            f"the manuscript version {version_id!r} names material the ledger does "
            "not hold. A chain that points at a file nobody has is a chain about "
            "nothing.",
        )
    return context.resource_for(relative_path)


def _read_material(context: ApplicationContext, version_id: str) -> bytes:
    """The bytes of the manuscript a version was made from.

    **And the bytes are checked against the version's own hash.** The
    version names a manuscript, and a manuscript whose bytes have changed
    under the name is not the one the coordinates would name.
    """
    resource = _material_of(context, version_id)
    try:
        size = resource.real_path.stat().st_size
    except OSError as error:
        raise chain_refused(
            ChainRefusal.MATERIAL_UNREADABLE,
            f"the manuscript {resource.resolved_key!r} could not be read: {error}. "
            "Unreadable is not the same as empty: a comment in a file nobody can open "
            "is not a comment the chain can claim to have found.",
        ) from error
    if size > MAX_MANUSCRIPT_BYTES:
        raise chain_refused(
            ChainRefusal.MATERIAL_UNREADABLE,
            f"the manuscript {resource.resolved_key!r} is {size} bytes, and this "
            f"operation reads at most {MAX_MANUSCRIPT_BYTES}. The file is measured "
            "before it is read, so a manuscript too large to read is refused rather "
            "than read and then refused.",
        )
    try:
        data = resource.real_path.read_bytes()
    except OSError as error:
        raise chain_refused(
            ChainRefusal.MATERIAL_UNREADABLE,
            f"the manuscript {resource.resolved_key!r} could not be read: {error}. "
            "Unreadable is not the same as empty.",
        ) from error
    source = material_source(context.store.session, version_id)
    assert source is not None  # the material was resolved above
    if _sha256_bytes(data) != source.content_sha256:
        raise chain_refused(
            ChainRefusal.MATERIAL_DRIFTED,
            f"the bytes now at {resource.resolved_key!r} are not the bytes the "
            f"version {version_id!r} was made from. The version names a manuscript, "
            "and a manuscript that has changed under the name is not the one the "
            "coordinates would name; nothing was recorded against it.",
        )
    return data


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def record_feedback(
    context: ApplicationContext,
    *,
    project_id: str,
    version_id: str,
    now: datetime,
) -> tuple[FeedbackEvent, ...]:
    """Read the manuscript a version was made from, and record its comments.

    **One row per comment, including the ones that cannot be placed.** A
    comment the reader could not anchor is still a comment a person wrote,
    and it is recorded with its body, its author and the reason its
    anchor is unknown.

    **And recording the same version twice is the same rows.** The ids are
    derived from the version and the comment's own id, so a second reading
    of the same bytes finds the rows that are already there. **A row
    whose anchor no longer matches is a stale anchor, and it is refused
    rather than silently re-pointed** — the manuscript's bytes changed
    under the anchor, and re-pointing it would make the record say
    something the file does not say.

    :raises ApplicationRefusedError: the project or the version is not
        there; the material is missing, unreadable or drifted; the policy
        denied reading it; or an anchor is stale.
    """
    session = context.store.session
    _require_version(context, project_id, version_id)
    resource = _material_of(context, version_id)
    consent.evaluate(
        context,
        capability=CapabilityId.SOURCE_READ,
        arguments={"max_bytes": MAX_MANUSCRIPT_BYTES},
        resource=resource,
    )
    data = _read_material(context, version_id)
    document = read_document(data)

    recorded: list[FeedbackEvent] = []
    for event in document.comments:
        anchor = event.anchor
        row_id = _feedback_id(version_id, event.comment_id)
        anchor_text = anchor.text
        anchor_hash = _sha256(anchor_text)
        existing = feedback_row(session, row_id)
        if existing is not None:
            if existing.anchor_text_sha256 != anchor_hash:
                raise chain_refused(
                    ChainRefusal.ANCHOR_STALE,
                    f"the feedback {row_id!r} was recorded against text hashing to "
                    f"{existing.anchor_text_sha256}, and the manuscript now reads "
                    f"differently. The anchor is stale, and a stale anchor is "
                    "reported as stale rather than silently re-pointed.",
                )
            recorded.append(event_from_row(existing))
            continue
        row = FeedbackEventRow(
            feedback_id=row_id,
            project_id=project_id,
            version_id=version_id,
            comment_locator=_locator_json(event.locator),
            anchor_paragraph=anchor.paragraph,
            anchor_start=anchor.start,
            anchor_end=anchor.end,
            anchor_status=anchor.status,
            anchor_reason=anchor.reason,
            anchor_text=anchor_text,
            anchor_text_sha256=anchor_hash,
            comment_text=event.text,
            comment_text_sha256=event.text_sha256,
            author=event.author,
            author_unknown_reason=(
                None if event.author is not None else "the comment records no author"
            ),
            commented_at=event.date,
            date_unknown_reason=(None if event.date is not None else "the comment records no date"),
            grade="observed",
            issue_key=None,
            created_at=now,
        )
        session.add(row)
        recorded.append(event_from_row(row))
    session.commit()
    return tuple(recorded)


def list_feedback_events(
    context: ApplicationContext,
    *,
    project_id: str,
    version_id: str | None = None,
) -> tuple[FeedbackEvent, ...]:
    """The comments the chain holds about a project, or about one version.

    **Denied material is dropped, not refused.** ADR-0003 C5 asks a bulk
    listing to filter denied entries out of its results rather than
    refusing the call, because refusing the whole listing discloses that
    something is there and denies work the operator wanted allowed.

    **And the rows come back in the order they were written**, which is
    the order the reader found the comments in — the order a person
    reading the manuscript would meet them.

    :raises ApplicationRefusedError: the project is not there, or the
        arguments are not usable.
    """
    session = context.store.session
    if project_row(session, project_id) is None:
        raise chain_refused(
            ChainRefusal.PROJECT_NOT_FOUND,
            f"the store holds no paper project with the id {project_id!r}.",
        )
    versions = project_version_rows(session, project_id)
    if version_id is not None:
        versions = tuple(version for version in versions if version.version_id == version_id)
        if not versions:
            raise chain_refused(
                ChainRefusal.VERSION_NOT_FOUND,
                f"the store holds no manuscript version with the id {version_id!r} in "
                f"the project {project_id!r}.",
            )
    resources = tuple(
        context.resource_for(path)
        for path in (material_relative_path(session, version.version_id) for version in versions)
        if path is not None
    )
    permitted = consent.evaluate_each(
        context,
        capability=CapabilityId.SOURCE_INVENTORY,
        arguments={},
        resources=resources,
    )
    allowed = {resource.resolved_key for resource in permitted}
    wanted = {
        version.version_id
        for version in versions
        if (path := material_relative_path(session, version.version_id)) is not None
        and context.resource_for(path).resolved_key in allowed
    }
    rows = session.scalars(
        select(FeedbackEventRow)
        .where(FeedbackEventRow.project_id == project_id)
        .order_by(FeedbackEventRow.created_at, FeedbackEventRow.feedback_id)
    )
    return tuple(event_from_row(row) for row in rows if row.version_id in wanted)


def set_issue_key(
    context: ApplicationContext,
    *,
    feedback_id: str,
    issue_key: str,
    now: datetime,
) -> FeedbackEvent:
    """Give a comment the key of the issue it is about.

    **The key is a person's judgement, and this operation takes one.** The
    same wording is not the same issue and the same issue is not the same
    wording, so a key is never derived from the text: ADR-0014's alignment
    already refused to decide an order by similarity, and a recurrence is
    recorded rather than inferred for the same reason.

    **And a key already given is not replaced.** A key that changes is a
    correction, and the project's rule is that a correction produces a new
    version rather than silently replacing what was there.

    :raises ApplicationRefusedError: the comment is not there, no key was
        given, or the comment already carries a different key.
    """
    session = context.store.session
    row = feedback_row(session, feedback_id)
    if row is None:
        raise chain_refused(
            ChainRefusal.FEEDBACK_NOT_FOUND,
            f"the store holds no feedback event with the id {feedback_id!r}.",
        )
    key = issue_key.strip()
    if not key:
        raise chain_refused(
            ChainRefusal.ISSUE_KEY_MAY_NOT_BE_INFERRED,
            f"no issue key was given for the feedback {feedback_id!r}. A key is a "
            "person's judgement about what the same problem is, and this operation "
            "never derives one: an uncategorised comment is a comment whose issue "
            "nobody has named yet.",
        )
    if row.issue_key is not None and row.issue_key != key:
        raise chain_refused(
            ChainRefusal.ISSUE_KEY_MAY_NOT_BE_INFERRED,
            f"the feedback {feedback_id!r} already carries the issue key "
            f"{row.issue_key!r}, and a key is not replaced silently: a change of "
            "judgement is a correction, and a correction is a new record rather "
            "than an overwrite of this one.",
        )
    row.issue_key = key
    session.commit()
    return event_from_row(row)


def anchor_state(
    context: ApplicationContext,
    *,
    feedback_id: str,
    now: datetime,
) -> str:
    """Whether a comment's anchor still names the text it named: ``fresh``,
    ``stale`` or ``unanchored``.

    **The hash is what makes drift detectable.** The row carries the
    anchored text and its hash; re-reading the manuscript and comparing
    the hash says whether the address still holds the same words. A
    stale anchor is **reported** as stale rather than silently
    re-pointed, because a re-pointed anchor is an address that now names
    something nobody wrote about.

    :raises ApplicationRefusedError: the comment is not there, or the
        material cannot be read.
    """
    session = context.store.session
    row = feedback_row(session, feedback_id)
    if row is None:
        raise chain_refused(
            ChainRefusal.FEEDBACK_NOT_FOUND,
            f"the store holds no feedback event with the id {feedback_id!r}.",
        )
    if row.anchor_status != "resolved":
        return "unanchored"
    data = _read_material(context, row.version_id)
    document = read_document(data)
    for event in document.comments:
        if _feedback_id(row.version_id, event.comment_id) != feedback_id:
            continue
        return "fresh" if _sha256(event.anchor.text) == row.anchor_text_sha256 else "stale"
    return "stale"


__all__ = [
    "FEEDBACK_GRADES",
    "MAX_MANUSCRIPT_BYTES",
    "FeedbackEvent",
    "anchor_state",
    "event_from_row",
    "list_feedback_events",
    "record_feedback",
    "set_issue_key",
]
