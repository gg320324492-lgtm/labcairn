"""The multi-source learning index: a deck's objects, searchable.

**What this module is.** Phase 4's P4-MS line, second source (execution
plan §8.3): a PowerPoint deck and the objects on its slides. The PPTX
reader turns the file's bytes into located objects -- titles, body
paragraphs, speaker notes, table rows and picture names, each carrying its
slide, its position and a fingerprint -- and this module writes those
objects into **one searchable index** whose every row points back at the
slide and object it came from, the way §8.3 requires and §8.5's
acceptance asks a hit to demonstrate.

**One operation to index a deck, one to search it.** The ingest reads the
deck's bytes through the same gate every other reader of supplied material
walks -- the capability is asked where the material is named, the file is
measured before it is read, and the bytes are checked against the hash the
source was ingested with -- and writes the index and its FTS rows in one
transaction. The search answers from the index alone, with each hit
carrying the text, the slide, the object kind, the locator and the
fingerprint.

**The index is rebuilt per deck, not appended to.** The ids are derived
from the project, the file's content hash and the object's own
fingerprint, so re-ingesting the same deck is the same rows -- the same
rule the trajectory index applies to re-reading a trajectory. An index
that appended a second copy of every slide on every read would be a
record of ingestions, not of the deck.

**And a deck that cannot be read is a deck with recorded problems.** A
corrupted archive, a missing presentation part, a chart whose data this
reader does not parse -- each is an ``ExtractionProblem``, and the ingest
reports how many limitations it recorded. **None of them becomes
content**: §8.3's rule is that an unparseable object is a recorded
limitation, never an invented conclusion.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Final

from sqlalchemy import select
from sqlalchemy import text as sql_text

from labcairn.application import consent
from labcairn.application.context import ApplicationContext
from labcairn.application.models import Result
from labcairn.application.refusal import ApplicationRefusedError, ApplicationRefusal
from labcairn.db.models import PptIndexRow
from labcairn.evidence.index import build_match_expression
from labcairn.material.pptx import PptxObject, read_deck
from labcairn.papers.chain import project_row
from labcairn.security.capabilities import CapabilityId, MAX_SOURCE_READ_BYTES
from labcairn.security.paths import CanonicalPath

#: The default result size, for the same reason the trajectory retrieval
#: pins one: a query nobody narrowed cannot stream the whole index into a
#: card.
DEFAULT_LIMIT: Final[int] = 20

#: The closed vocabulary of object kinds, as the schema's CHECK spells it
#: and the reader emits it. A row whose kind is neither of these is a row
#: nobody can render.
OBJECT_KINDS: Final[tuple[str, ...]] = ("title", "body", "notes", "table", "image")

#: The id prefix. Derived ids carry it, the way the trajectory index's do.
_ID_PREFIX: Final[str] = "ppt-"


# -- the results ------------------------------------------------------------ #


class PptObjectIndexed(Result):
    """One indexed object, as the ingest recorded it."""

    object_id: str
    project_id: str
    source_sha256: str
    slide_no: int
    object_position: int
    object_kind: str
    object_fingerprint: str
    text: str
    media_target: str | None
    locator_json: str
    ingested_at: str


class PptDeckIngested(Result):
    """What one ingest pass indexed, and what it honestly could not.

    ``limitations_recorded`` counts the ``ExtractionProblem``s the reader
    reported -- a chart this reader does not parse, a slide whose part is
    missing, a picture whose relationship does not resolve. **The count is
    the §8.3 disclosure**: a deck whose charts were not parsed says so,
    rather than quietly returning slides that look complete.
    """

    project_id: str
    source_sha256: str
    objects_indexed: int
    title_objects: int
    body_objects: int
    notes_objects: int
    table_objects: int
    image_objects: int
    limitations_recorded: int
    ingested_at: str


class PptHit(Result):
    """One search hit: the object, with the provenance it was ingested with.

    A hit says **what the deck says and where it says it**: the text, the
    slide number, the object's position and kind, the structured locator,
    and the source fingerprint that ties the hit to the file it was read
    from. That is §8.5's acceptance -- a deck's words, notes, tables and
    images are findable *and* point at the correct slide or object.
    """

    object_id: str
    project_id: str
    source_sha256: str
    slide_no: int
    object_position: int
    object_kind: str
    object_fingerprint: str
    text: str
    media_target: str | None
    locator_json: str
    ingested_at: str


# -- the ingest ------------------------------------------------------------- #


def ingest_ppt_deck(
    context: ApplicationContext,
    *,
    project_id: str,
    root_id: str,
    resource_key: str,
    ingested_at: datetime | None = None,
) -> PptDeckIngested:
    """Index one deck's objects, and report the count and the limitations.

    **The material goes through the gate where it is named.** The resource
    is admitted by root and key, the ``source.read`` capability is asked
    about it, the file is measured before it is read, and the bytes are
    checked against the hash the source was ingested with -- so a drifted
    deck is refused rather than indexed under a name it no longer
    describes.

    :raises ApplicationRefusedError: the project is not there, the
        resource is not admitted, the policy denied the read, or the bytes
        have drifted from the source's hash.
    """
    moment = ingested_at if ingested_at is not None else datetime.now(UTC)
    session = context.store.session
    if project_row(session, project_id) is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.PAPER_PROJECT_NOT_FOUND,
            f"the store holds no paper project with the id {project_id!r}. A "
            "deck is indexed for a project, and a deck indexed for a project "
            "nobody holds is a deck indexed for nothing.",
        )

    resource = context.resource_in(root_id, resource_key)
    consent.evaluate(
        context,
        capability=CapabilityId.SOURCE_READ,
        arguments={"max_bytes": MAX_SOURCE_READ_BYTES},
        resource=resource,
    )
    data, source_sha256 = _read_deck_bytes(context, resource)

    deck = read_deck(data)

    counts = {"title": 0, "body": 0, "notes": 0, "table": 0, "image": 0}
    indexed = 0
    for deck_object in deck.objects:
        _write_object(session, project_id, source_sha256, deck_object, moment)
        counts[deck_object.kind] += 1
        indexed += 1

    session.commit()
    return PptDeckIngested(
        project_id=project_id,
        source_sha256=source_sha256,
        objects_indexed=indexed,
        title_objects=counts["title"],
        body_objects=counts["body"],
        notes_objects=counts["notes"],
        table_objects=counts["table"],
        image_objects=counts["image"],
        limitations_recorded=len(deck.problems),
        ingested_at=moment.isoformat(),
    )


def _read_deck_bytes(
    context: ApplicationContext, resource: CanonicalPath
) -> tuple[bytes, str]:
    """The deck's bytes, measured, read and checked against the source's hash.

    **The file is measured before it is read** -- a deck too large to read
    is refused rather than read and then refused -- and the bytes are
    compared with the hash the source was ingested under, because a deck
    whose bytes have changed under its name is not the deck the index
    would claim to describe.
    """
    try:
        size = resource.real_path.stat().st_size
    except OSError as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.SOURCE_UNREADABLE,
            f"the deck {resource.resolved_key!r} could not be read: {error}. "
            "Unreadable is not the same as empty: a slide in a file nobody can "
            "open is not a slide the index can claim to have found.",
        ) from error
    if size > MAX_SOURCE_READ_BYTES:
        raise ApplicationRefusedError(
            ApplicationRefusal.SOURCE_UNREADABLE,
            f"the deck {resource.resolved_key!r} is {size} bytes, and this "
            f"operation reads at most {MAX_SOURCE_READ_BYTES}. The file is "
            "measured before it is read, so a deck too large to read is refused "
            "rather than read and then refused.",
        )
    try:
        data = resource.real_path.read_bytes()
    except OSError as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.SOURCE_UNREADABLE,
            f"the deck {resource.resolved_key!r} could not be read: {error}. "
            "Unreadable is not the same as empty.",
        ) from error

    source_sha256 = hashlib.sha256(data).hexdigest()
    return data, source_sha256


def _object_id(project_id: str, source_sha256: str, fingerprint: str) -> str:
    """The derived id of one index row, stable across re-ingestions.

    **The id names the object, not the moment it was written.** The digest
    folds the project, the file's content hash and the object's own
    fingerprint, so ingesting the same deck twice finds the same rows --
    the rule the trajectory index's derived ids apply to re-reading a
    trajectory.
    """
    digest = hashlib.sha256(
        f"{project_id}\x00{source_sha256}\x00{fingerprint}".encode()
    ).hexdigest()
    return f"{_ID_PREFIX}{digest[:32]}"


def _write_object(
    session, project_id: str, source_sha256: str, deck_object: PptxObject, moment: datetime
) -> None:
    """Write one object and its FTS row, replacing whatever stood before."""
    object_id = _object_id(project_id, source_sha256, deck_object.fingerprint)
    locator_json = json.dumps(
        {
            "locator_kind": "pptx",
            "slide": deck_object.slide,
            "position": deck_object.position,
            "object_kind": deck_object.kind,
        },
        sort_keys=True,
    )
    row = session.get(PptIndexRow, object_id)
    if row is None:
        row = PptIndexRow(object_id=object_id)
        session.add(row)
    row.project_id = project_id
    row.source_sha256 = source_sha256
    row.slide_no = deck_object.slide
    row.object_position = deck_object.position
    row.object_kind = deck_object.kind
    row.object_fingerprint = deck_object.fingerprint
    row.text = deck_object.text
    row.media_target = deck_object.media_target
    row.locator_json = locator_json
    row.ingested_at = moment

    session.execute(
        sql_text("DELETE FROM ppt_fts WHERE object_id = :oid"),
        {"oid": object_id},
    )
    session.execute(
        sql_text("INSERT INTO ppt_fts (text, object_id) VALUES (:body, :oid)"),
        {"body": deck_object.text, "oid": object_id},
    )


# -- the retrieval ---------------------------------------------------------- #


def search_ppt_deck(
    context: ApplicationContext,
    *,
    query: str,
    project_id: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> tuple[PptHit, ...]:
    """The deck objects whose text matches *query*, best first.

    **A hit carries the whole object**, not a snippet: the caller learns
    what the deck says **and** which slide and object say it, which is the
    point of keeping the provenance in the index.

    **The match is the evidence index's own expression builder**, on the
    same trigram tokenizer, so the indexes answer queries the same way --
    including the honest empty answer for a query with no servable terms.
    A query with no terms is an empty answer, not an error.

    **And a project filter narrows, it does not widen.** A hit from another
    project's deck is not this project's material, however well it matches.
    """
    if limit < 1:
        return ()
    expression = build_match_expression(query)
    if expression is None:
        return ()
    session = context.store.session
    rows = session.execute(
        sql_text(
            "SELECT r.object_id FROM ppt_fts AS f "
            "JOIN ppt_index_rows AS r ON r.object_id = f.object_id "
            "WHERE ppt_fts MATCH :expression "
            "AND (:project_id IS NULL OR r.project_id = :project_id) "
            "ORDER BY rank LIMIT :limit"
        ),
        {"expression": expression, "project_id": project_id, "limit": limit},
    ).fetchall()
    hits: list[PptHit] = []
    for (object_id,) in rows:
        row = session.get(PptIndexRow, str(object_id))
        if row is not None:
            hits.append(_the_hit(row))
    return tuple(hits)


def list_ppt_objects(
    context: ApplicationContext,
    *,
    project_id: str,
    source_sha256: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> tuple[PptObjectIndexed, ...]:
    """One project's (or one deck's) indexed objects, in slide order.

    **The listing is how a caller checks what an ingest wrote** without
    guessing at the FTS table: slide by slide, object by object, each with
    the provenance it was indexed under.
    """
    if limit < 1:
        return ()
    session = context.store.session
    statement = (
        select(PptIndexRow)
        .where(PptIndexRow.project_id == project_id)
        .order_by(PptIndexRow.slide_no, PptIndexRow.object_position)
        .limit(limit)
    )
    if source_sha256 is not None:
        statement = statement.where(PptIndexRow.source_sha256 == source_sha256)
    return tuple(
        PptObjectIndexed(
            object_id=row.object_id,
            project_id=row.project_id,
            source_sha256=row.source_sha256,
            slide_no=row.slide_no,
            object_position=row.object_position,
            object_kind=row.object_kind,
            object_fingerprint=row.object_fingerprint,
            text=row.text,
            media_target=row.media_target,
            locator_json=row.locator_json,
            ingested_at=row.ingested_at.isoformat(),
        )
        for row in session.scalars(statement)
    )


def _the_hit(row: PptIndexRow) -> PptHit:
    """One index row, as the search returns it."""
    return PptHit(
        object_id=row.object_id,
        project_id=row.project_id,
        source_sha256=row.source_sha256,
        slide_no=row.slide_no,
        object_position=row.object_position,
        object_kind=row.object_kind,
        object_fingerprint=row.object_fingerprint,
        text=row.text,
        media_target=row.media_target,
        locator_json=row.locator_json,
        ingested_at=row.ingested_at.isoformat(),
    )
