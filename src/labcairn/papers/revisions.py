"""The revision events: what a manuscript's file records, written down.

**What this module is.** ADR-0014's third table, and the seam that was
never closed. ``docs/acceptance/LC-P2-08-acceptance.md`` records the debt
in the work order's own words: *"LC-P2-07's reader produces the revision
events these tables are meant to hold, and nobody has written them into
the store — the reader exists, the store exists, and the seam between the
two is not connected, so the version graph is hand-fed today."* This
module is the other half of that seam: it reads a marked-up manuscript's
bytes and writes one row per tracked change.

**These are manuscript revisions, not report revisions.**
``labcairn.reports.revisions`` holds ``ReportRevision`` — a re-render of a
generated document with a staleness chain — and ADR-0014 D8's rule is that
a table where "revision 3" means two things is a table nobody can read.
So the table here is ``revision_events`` and the type is
:class:`RevisionRecord`, and neither shares a name with the report's.

**Why this is not the chain's ``edit_actions``.** The chain's four tables
are a *judgement* layer: a comment, a change made in answer to it, the
judgement that it answered, a later assessment. ``edit_actions`` is
content-free by design — it names an edge and an actor, and the content
belongs to the document model, which is ADR-0014's. A marked-up manuscript
holds hundreds of changes, each with its own address and its own text; a
version holds one file.

**Why the reason is not here.** A revision event says **what** changed,
**where**, and **who** changed it. It says nothing about **why**, and it
cannot: there is no column for a reason and no link to the comment that
would have carried one. A marked-up manuscript with no comments in it
holds hundreds of changes and **not one statement about why** — and the
schema is what makes that shape inexpressible rather than merely
discouraged. ADR-0016 D9 calls the agreement between a system and an
advisor's wording a *risk metric*; this is the structure that keeps a
reviewer's silence from being distilled into a rule.

**And the bytes are checked before anything is written.** The version
names the file *and* the bytes it was recorded with, and the file on disk
is compared against those bytes before it is parsed. A manuscript that has
changed under the name is not the one the coordinates would name, so
nothing is recorded against it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from labcairn.application import consent
from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import chain_refused
from labcairn.db.models import RevisionEventRow
from labcairn.material.ooxml import RevisionEvent as ReadRevision
from labcairn.material.ooxml import read_document
from labcairn.material.units import adapter_for
from labcairn.material.version import derive_extraction_version
from labcairn.papers.chain import (
    ChainRefusal,
    material_relative_path,
    project_row,
    version_row,
)
from labcairn.security.capabilities import CapabilityId
from labcairn.security.paths import CanonicalPath
from labcairn.sources.source import SourceKind

#: The kinds of tracked change the reader reports. **Four, and the fourth
#: pair is why the view is a column**: a move has a source and a
#: destination, and Word's ``w:id`` is what pairs them.
REVISION_KINDS: frozenset[str] = frozenset({"ins", "del", "moveFrom", "moveTo"})

#: The grades ADR-0014 D2 names. ``observed`` is what the reader writes and
#: it is the only grade this module produces: the other two are the
#: schema's to know about, and a row that read no file quotes nobody.
REVISION_GRADES: frozenset[str] = frozenset({"observed", "inferred", "human_verified"})

#: The ceiling on a manuscript this operation will read. **A ceiling, and
#: not a hope**: the file's size is measured before the bytes are read, so
#: a file that is too large is refused rather than read and then refused.
MAX_MANUSCRIPT_BYTES = 64_000_000

#: The reason a revision carries no author.
_NO_AUTHOR = "the revision records no author"

#: The reason a revision carries no timestamp.
_NO_DATE = "the revision records no date"


@dataclass(frozen=True, slots=True)
class RevisionRecord:
    """One tracked change, as the store holds it.

    **The address is the point.** ``part``, ``element_path``, ``view`` and
    the character range say *where* the change is; ``text`` and
    ``text_sha256`` say *what* it is, and the hash is what makes a stale
    anchor detectable rather than silently re-pointed.
    """

    revision_event_id: str
    version_id: str
    kind: str
    text: str
    text_sha256: str
    part: str | None
    element_path: str | None
    view: str | None
    char_start: int | None
    char_end: int | None
    paragraph: int | None
    baseline_start: int | None
    baseline_end: int | None
    author: str | None
    author_unknown_reason: str | None
    occurred_at: datetime | None
    date_unknown_reason: str | None
    element_id: str | None
    nested: bool
    parser_version: str
    grade: str


def _sha256(text: str) -> str:
    """The hash of a text, as the chain hashes its anchor text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _revision_event_id(version_id: str, part: str, element_path: str) -> str:
    """The id of one tracked change, derived.

    **Derived, so recording the same manuscript twice is the same rows.**
    The element's path is unique inside a part, and the part and the path
    together are unique inside a document — so the version and the path
    name one change for ever, and identity does not depend on insertion
    order.
    """
    digest = hashlib.sha256(f"{version_id}\x00{part}\x00{element_path}".encode()).hexdigest()
    return f"rv-{digest[:16]}"


def _parser_version() -> str:
    """The extraction version of the reader that produces these events.

    **Derived from the reader's own source**, exactly as
    :func:`labcairn.material.version.derive_extraction_version` is
    designed for, so changing the reader changes the version without
    anybody remembering to bump a constant.
    """
    adapter = adapter_for(SourceKind.DOCX)
    return derive_extraction_version(adapter.source_modules(), adapter.libraries())


def _record_from_row(row: RevisionEventRow) -> RevisionRecord:
    """The record a row is."""
    return RevisionRecord(
        revision_event_id=row.revision_event_id,
        version_id=row.version_id,
        kind=row.kind,
        text=row.text,
        text_sha256=row.text_sha256,
        part=row.part,
        element_path=row.element_path,
        view=row.view,
        char_start=row.char_start,
        char_end=row.char_end,
        paragraph=row.paragraph,
        baseline_start=row.baseline_start,
        baseline_end=row.baseline_end,
        author=row.author,
        author_unknown_reason=row.author_unknown_reason,
        occurred_at=row.occurred_at,
        date_unknown_reason=row.date_unknown_reason,
        element_id=row.element_id,
        nested=bool(row.nested),
        parser_version=row.parser_version,
        grade=row.grade,
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
            "not hold. A revision event is a change in a manuscript, and a change "
            "in a manuscript nobody holds is a change about nothing.",
        )
    return context.resource_for(relative_path)


def _read_material(context: ApplicationContext, version_id: str) -> bytes:
    """The bytes of the manuscript a version was made from.

    **And the bytes are checked against the version's own hash.** The
    version names the file *and* the bytes it was recorded with, and the
    file on disk is compared against those bytes before it is parsed. A
    manuscript that has changed under the name is not the one the
    coordinates would name, so nothing is recorded against it.
    """
    resource = _material(context, version_id)
    try:
        size = resource.real_path.stat().st_size
    except OSError as error:
        raise chain_refused(
            ChainRefusal.MATERIAL_UNREADABLE,
            f"the manuscript {resource.resolved_key!r} could not be read: {error}. "
            "Unreadable is not the same as empty: a change in a file nobody can open "
            "is not a change the chain can claim to have found.",
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
    version = version_row(context.store.session, version_id)
    assert version is not None  # the material was resolved above
    expected = version.source_content_sha256
    if expected is None:
        raise chain_refused(
            ChainRefusal.MATERIAL_DRIFTED,
            f"the manuscript version {version_id!r} names no bytes. A version is the "
            "set of bytes it was recorded with, and an event read from bytes nobody "
            "recorded would be an event about a document that cannot be named.",
        )
    if _sha256_bytes(data) != expected:
        raise chain_refused(
            ChainRefusal.MATERIAL_DRIFTED,
            f"the bytes now at {resource.resolved_key!r} are not the bytes the "
            f"version {version_id!r} was made from. The version names a manuscript, "
            "and a manuscript that has changed under the name is not the one the "
            "coordinates would name; nothing was recorded against it.",
        )
    return data


def _sha256_bytes(data: bytes) -> str:
    """The hash of a file's bytes, as the ledger records it."""
    return hashlib.sha256(data).hexdigest()


def _row_for(
    version_id: str,
    event: ReadRevision,
    *,
    parser_version: str,
    now: datetime,
) -> RevisionEventRow:
    """The row one read event becomes.

    **The author and the date come as they were found.** A missing one is
    ``None`` plus a named reason, never a guess — ADR-0014 D3 — and an
    *empty* author is not a missing one, so the empty string is kept as it
    was found and the reason stays absent.
    """
    part = event.locator.part
    element_path = event.locator.element_path
    return RevisionEventRow(
        revision_event_id=_revision_event_id(version_id, part, element_path),
        version_id=version_id,
        kind=event.kind,
        text=event.text,
        text_sha256=event.text_sha256,
        part=part,
        element_path=element_path,
        view=event.locator.view,
        char_start=event.locator.char_start,
        char_end=event.locator.char_end,
        paragraph=event.paragraph,
        baseline_start=event.baseline_start,
        baseline_end=event.baseline_end,
        author=event.author,
        author_unknown_reason=None if event.author is not None else _NO_AUTHOR,
        occurred_at=event.date,
        date_unknown_reason=None if event.date is not None else _NO_DATE,
        element_id=event.element_id,
        nested=event.nested,
        parser_version=parser_version,
        grade="observed",
        created_at=now,
    )


def record_revision_events(
    context: ApplicationContext,
    *,
    project_id: str,
    version_id: str,
    now: datetime,
) -> tuple[RevisionRecord, ...]:
    """Read the manuscript a version was made from, and record its changes.

    **One row per tracked change, including the ones that carry no
    explanation.** A marked-up manuscript is a fact about a file, and the
    fact is that somebody changed these words — whether or not anybody
    wrote down why. The rows say what changed, where, and who changed it;
    **they say nothing about why, because the file says nothing about why**
    and the table has nowhere to put it.

    **And recording the same version twice is the same rows.** The ids are
    derived from the version and the element's path, so a second reading
    of the same bytes finds the rows that are already there. **A row whose
    text no longer matches is a stale anchor, and it is refused** rather
    than silently re-pointed — the manuscript's bytes changed under the
    address, and re-pointing it would make the record say something the
    file does not say.

    :raises ApplicationRefusedError: the project or the version is not
        there; the material is missing, unreadable or drifted; the policy
        denied reading it; or an anchor is stale.
    """
    session = context.store.session
    if project_row(session, project_id) is None:
        raise chain_refused(
            ChainRefusal.PROJECT_NOT_FOUND,
            f"the store holds no paper project with the id {project_id!r}. A change "
            "belongs to a manuscript, and a change in a manuscript nobody holds is a "
            "change about nothing.",
        )
    version = version_row(session, version_id)
    if version is None:
        raise chain_refused(
            ChainRefusal.VERSION_NOT_FOUND,
            f"the store holds no manuscript version with the id {version_id!r}. A "
            "revision event is a change in a document, and a change in a document "
            "nobody holds is a change about nothing.",
        )
    if version.project_id != project_id:
        raise chain_refused(
            ChainRefusal.VERSION_NOT_FOUND,
            f"the manuscript version {version_id!r} belongs to the project "
            f"{version.project_id!r}, not to {project_id!r}. A change is recorded "
            "against the project its manuscript belongs to.",
        )
    resource = _material(context, version_id)
    consent.evaluate(
        context,
        capability=CapabilityId.SOURCE_READ,
        arguments={"max_bytes": MAX_MANUSCRIPT_BYTES},
        resource=resource,
    )
    data = _read_material(context, version_id)
    document = read_document(data)
    parser_version = _parser_version()

    recorded: list[RevisionRecord] = []
    fresh: list[RevisionEventRow] = []
    for event in document.revisions:
        row = _row_for(version_id, event, parser_version=parser_version, now=now)
        existing = session.get(RevisionEventRow, row.revision_event_id)
        if existing is not None:
            if existing.text_sha256 != row.text_sha256:
                raise chain_refused(
                    ChainRefusal.ANCHOR_STALE,
                    f"the revision event {row.revision_event_id!r} was recorded against "
                    f"text hashing to {existing.text_sha256}, and the manuscript now "
                    "reads differently. The anchor is stale, and a stale anchor is "
                    "reported as stale rather than silently re-pointed.",
                )
            recorded.append(_record_from_row(existing))
            continue
        session.add(row)
        fresh.append(row)
        recorded.append(_record_from_row(row))
    if fresh:
        # **The rows land together.** A revision event is written in one
        # transaction, so a manuscript half-recorded is a manuscript nobody
        # can count.
        session.commit()
    return tuple(recorded)


def list_revision_events(
    context: ApplicationContext,
    *,
    version_ids: tuple[str, ...] | None = None,
) -> tuple[RevisionRecord, ...]:
    """The changes the store holds, for the versions named.

    **Denied material is dropped, not refused** — ADR-0003 C5's rule for a
    bulk listing.

    :raises ApplicationRefusedError: the arguments are not usable.
    """
    session = context.store.session
    statement = select(RevisionEventRow).order_by(
        RevisionEventRow.version_id, RevisionEventRow.revision_event_id
    )
    if version_ids is not None:
        wanted = tuple(version_id for version_id in version_ids if version_id)
        if not wanted:
            return ()
        statement = statement.where(RevisionEventRow.version_id.in_(wanted))
    rows = tuple(session.scalars(statement))
    if not rows:
        return ()

    # **Denied material is dropped, not refused.** A version whose material
    # the ledger does not hold takes its events with it: there is nothing
    # to show and nothing to refuse.
    materials: dict[str, CanonicalPath | None] = {}
    for row in rows:
        if row.version_id in materials:
            continue
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
    return tuple(_record_from_row(row) for row in kept)


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
    "REVISION_GRADES",
    "REVISION_KINDS",
    "RevisionRecord",
    "list_revision_events",
    "record_revision_events",
]
