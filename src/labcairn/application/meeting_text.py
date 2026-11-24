"""The multi-source learning index: meeting text, searchable.

**What this module is.** Phase 4's P4-MS line, third source (execution
plan §8.4): meeting material that already exists as text -- a transcript
someone else produced (SRT, WebVTT) or notes someone organised by hand
(TXT, Markdown). The meeting-text reader turns the file's bytes into
located records -- timestamped transcript entries or organised
paragraphs, each carrying its record index, its timestamp when it has
one, and a fingerprint -- and this module writes those records into
**one searchable index** whose every row points back at the entry or
paragraph it came from, the way §8.3 requires and §8.5's acceptance asks
a hit to demonstrate.

**One operation to index a file, one to search it.** The ingest reads the
file's bytes through the same gate every other reader of supplied
material walks -- the capability is asked where the material is named,
the file is measured before it is read, and the bytes are checked against
the hash the source was ingested with -- and writes the index and its FTS
rows in one transaction. The search answers from the index alone, with
each hit carrying the text, the record's position, the locator and the
fingerprint.

**The index is rebuilt per file, not appended to.** The ids are derived
from the project, the file's content hash and the record's own
fingerprint, so re-ingesting the same file is the same rows -- the same
rule the deck index applies to re-reading a deck. An index that appended
a second copy of every cue on every read would be a record of
ingestions, not of the meeting.

**And a file that cannot be read is a file with recorded problems.** A
cue with no timing line, a paragraph that is empty -- each is an
``ExtractionProblem``, and the ingest reports how many limitations it
recorded. **None of them becomes content**: §8.3's rule is that
unreadable input is recorded, never fabricated.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Final

from sqlalchemy import select
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from labcairn.application import consent
from labcairn.application.context import ApplicationContext
from labcairn.application.models import Result
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.db.models import MeetingIndexRow
from labcairn.evidence.index import build_match_expression
from labcairn.material.meetingtext import MeetingRecord, read_meeting_text
from labcairn.papers.chain import project_row
from labcairn.security.capabilities import MAX_SOURCE_READ_BYTES, CapabilityId
from labcairn.security.paths import CanonicalPath

#: The default result size, for the same reason the deck retrieval pins
#: one: a query nobody narrowed cannot stream the whole index into a card.
DEFAULT_LIMIT: Final[int] = 20

#: The closed vocabulary of record shapes, as the schema's CHECK spells it
#: and the reader emits it. A row whose shape is neither of these is a row
#: nobody can render.
RECORD_FORMATS: Final[tuple[str, ...]] = ("entry", "paragraph")

#: The id prefix. Derived ids carry it, the way the deck index's do.
_ID_PREFIX: Final[str] = "mtg-"

#: Which container each supported extension is read as. The transcript
#: containers are named by their extensions; organised text arrives as
#: ``.txt`` and ``.md`` -- extensions the plain-text and Markdown adapters
#: already own at the inventory level, so the meeting ingest claims them
#: by content, at this layer, rather than by re-mapping the extension
#: table.
_CONTAINERS: Final[dict[str, str]] = {
    ".srt": "srt",
    ".vtt": "vtt",
    ".txt": "paragraphs",
    ".md": "paragraphs",
    ".markdown": "paragraphs",
}


# -- the results ------------------------------------------------------------ #


class MeetingRecordIndexed(Result):
    """One indexed record, as the ingest recorded it."""

    record_id: str
    project_id: str
    source_sha256: str
    record_format: str
    record_index: int
    timestamp_label: str | None
    record_fingerprint: str
    text: str
    locator_json: str
    ingested_at: str


class MeetingTextIngested(Result):
    """What one ingest pass indexed, and what it honestly could not.

    ``limitations_recorded`` counts the ``ExtractionProblem``s the reader
    reported -- a cue with no timing line, a block that is empty. **The
    count is the §8.3 disclosure**: a transcript whose untimed blocks were
    not indexed says so, rather than quietly returning entries that look
    complete.
    """

    project_id: str
    source_sha256: str
    records_indexed: int
    entry_records: int
    paragraph_records: int
    limitations_recorded: int
    ingested_at: str


class MeetingHit(Result):
    """One search hit: the record, with the provenance it was ingested with.

    A hit says **what the meeting text says and where it says it**: the
    text, the record's shape and index, the container's timestamp when it
    has one, the structured locator, and the source fingerprint that ties
    the hit to the file it was read from. That is §8.5's acceptance --
    meeting text is findable *and* points at the correct entry or
    paragraph.
    """

    record_id: str
    project_id: str
    source_sha256: str
    record_format: str
    record_index: int
    timestamp_label: str | None
    record_fingerprint: str
    text: str
    locator_json: str
    ingested_at: str


# -- the ingest ------------------------------------------------------------- #


def ingest_meeting_text(
    context: ApplicationContext,
    *,
    project_id: str,
    root_id: str,
    resource_key: str,
    ingested_at: datetime | None = None,
) -> MeetingTextIngested:
    """Index one meeting-text file's records, and report the counts.

    **The material goes through the gate where it is named.** The resource
    is admitted by root and key, the ``source.read`` capability is asked
    about it, the file is measured before it is read, and the bytes are
    checked against the hash the source was ingested with -- so a drifted
    file is refused rather than indexed under a name it no longer
    describes.

    :raises ApplicationRefusedError: the project is not there, the
        resource is not admitted, the policy denied the read, the bytes
        have drifted from the source's hash, or the file's extension is
        not one this ingest reads.
    """
    moment = ingested_at if ingested_at is not None else datetime.now(UTC)
    session = context.store.session
    if project_row(session, project_id) is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.PAPER_PROJECT_NOT_FOUND,
            f"the store holds no paper project with the id {project_id!r}. A "
            "meeting file is indexed for a project, and a file indexed for a "
            "project nobody holds is a file indexed for nothing.",
        )

    resource = context.resource_in(root_id, resource_key)
    consent.evaluate(
        context,
        capability=CapabilityId.SOURCE_READ,
        arguments={"max_bytes": MAX_SOURCE_READ_BYTES},
        resource=resource,
    )
    data, source_sha256 = _read_meeting_bytes(context, resource)

    container = _container_for(resource_key)
    meeting = read_meeting_text(data, container=container)

    entries = 0
    paragraphs = 0
    indexed = 0
    for record in meeting.records:
        _write_record(session, project_id, source_sha256, record, moment)
        if record.record_format == "entry":
            entries += 1
        else:
            paragraphs += 1
        indexed += 1

    session.commit()
    return MeetingTextIngested(
        project_id=project_id,
        source_sha256=source_sha256,
        records_indexed=indexed,
        entry_records=entries,
        paragraph_records=paragraphs,
        limitations_recorded=len(meeting.problems),
        ingested_at=moment.isoformat(),
    )


def _container_for(resource_key: str) -> str:
    """Which container the file is read as, from its extension.

    **Extension, not content sniffing**, for the reason ``kind_for_path``
    records: a sniffed-but-wrong label is a silent misreading, while a
    mislabelled file is reported by the reader that cannot read it. An
    extension this ingest does not read is a refusal, not a guess.
    """
    suffix = PurePosixPath(resource_key).suffix.lower()
    container = _CONTAINERS.get(suffix)
    if container is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.SOURCE_UNREADABLE,
            f"the meeting file {resource_key!r} has the extension {suffix!r}, and "
            f"this ingest reads {sorted(_CONTAINERS)}: a transcript (.srt, .vtt) "
            "or organised text (.txt, .md). A file whose container is not named "
            "is refused rather than guessed at.",
        )
    return container


def _read_meeting_bytes(context: ApplicationContext, resource: CanonicalPath) -> tuple[bytes, str]:
    """The file's bytes, measured, read and checked against the source's hash.

    **The file is measured before it is read** -- a file too large to read
    is refused rather than read and then refused -- and the bytes are
    compared with the hash the source was ingested under, because a file
    whose bytes have changed under its name is not the file the index
    would claim to describe.
    """
    try:
        size = resource.real_path.stat().st_size
    except OSError as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.SOURCE_UNREADABLE,
            f"the meeting file {resource.resolved_key!r} could not be read: {error}. "
            "Unreadable is not the same as empty: a cue in a file nobody can "
            "open is not a cue the index can claim to have found.",
        ) from error
    if size > MAX_SOURCE_READ_BYTES:
        raise ApplicationRefusedError(
            ApplicationRefusal.SOURCE_UNREADABLE,
            f"the meeting file {resource.resolved_key!r} is {size} bytes, and this "
            f"operation reads at most {MAX_SOURCE_READ_BYTES}. The file is "
            "measured before it is read, so a file too large to read is refused "
            "rather than read and then refused.",
        )
    try:
        data = resource.real_path.read_bytes()
    except OSError as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.SOURCE_UNREADABLE,
            f"the meeting file {resource.resolved_key!r} could not be read: {error}. "
            "Unreadable is not the same as empty.",
        ) from error

    source_sha256 = hashlib.sha256(data).hexdigest()
    return data, source_sha256


def _record_id(project_id: str, source_sha256: str, fingerprint: str) -> str:
    """The derived id of one index row, stable across re-ingestions.

    **The id names the record, not the moment it was written.** The digest
    folds the project, the file's content hash and the record's own
    fingerprint, so ingesting the same file twice finds the same rows --
    the rule the deck index's derived ids apply to re-reading a deck.
    """
    digest = hashlib.sha256(
        f"{project_id}\x00{source_sha256}\x00{fingerprint}".encode()
    ).hexdigest()
    return f"{_ID_PREFIX}{digest[:32]}"


def _write_record(
    session: Session,
    project_id: str,
    source_sha256: str,
    record: MeetingRecord,
    moment: datetime,
) -> None:
    """Write one record and its FTS row, replacing whatever stood before."""
    record_id = _record_id(project_id, source_sha256, record.fingerprint)
    locator_json = json.dumps(
        {
            "locator_kind": "meeting",
            "record_format": record.record_format,
            "record_index": record.record_index,
            "timestamp": record.timestamp,
        },
        sort_keys=True,
    )
    row = session.get(MeetingIndexRow, record_id)
    if row is None:
        row = MeetingIndexRow(record_id=record_id)
        session.add(row)
    row.project_id = project_id
    row.source_sha256 = source_sha256
    row.record_format = record.record_format
    row.record_index = record.record_index
    row.timestamp_label = record.timestamp
    row.record_fingerprint = record.fingerprint
    row.text = record.text
    row.locator_json = locator_json
    row.ingested_at = moment

    session.execute(
        sql_text("DELETE FROM meeting_fts WHERE record_id = :rid"),
        {"rid": record_id},
    )
    session.execute(
        sql_text("INSERT INTO meeting_fts (text, record_id) VALUES (:body, :rid)"),
        {"body": record.text, "rid": record_id},
    )


# -- the retrieval ---------------------------------------------------------- #


def search_meeting_text(
    context: ApplicationContext,
    *,
    query: str,
    project_id: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> tuple[MeetingHit, ...]:
    """The meeting records whose text matches *query*, best first.

    **A hit carries the whole record**, not a snippet: the caller learns
    what the meeting text says **and** which entry or paragraph says it,
    which is the point of keeping the provenance in the index.

    **The match is the evidence index's own expression builder**, on the
    same trigram tokenizer, so the indexes answer the same query the same
    way and the match semantics are written once. An empty query answers
    nothing: there is nothing to match.
    """
    if limit < 1:
        return ()
    expression = build_match_expression(query)
    if expression is None:
        return ()
    session = context.store.session
    rows = session.execute(
        sql_text(
            "SELECT r.record_id FROM meeting_fts AS f "
            "JOIN meeting_index_rows AS r ON r.record_id = f.record_id "
            "WHERE meeting_fts MATCH :expression "
            "AND (:project_id IS NULL OR r.project_id = :project_id) "
            "ORDER BY rank LIMIT :limit"
        ),
        {"expression": expression, "project_id": project_id, "limit": limit},
    ).fetchall()
    hits: list[MeetingHit] = []
    for (record_id,) in rows:
        row = session.get(MeetingIndexRow, str(record_id))
        if row is not None:
            hits.append(_the_hit(row))
    return tuple(hits)


def list_meeting_records(
    context: ApplicationContext,
    *,
    project_id: str,
    source_sha256: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> tuple[MeetingRecordIndexed, ...]:
    """One project's (or one file's) indexed records, in record order.

    **The listing is how a caller checks what an ingest wrote** without
    guessing at the FTS table: record by record, each with the provenance
    it was indexed under.
    """
    if limit < 1:
        return ()
    session = context.store.session
    statement = (
        select(MeetingIndexRow)
        .where(MeetingIndexRow.project_id == project_id)
        .order_by(MeetingIndexRow.record_index)
        .limit(limit)
    )
    if source_sha256 is not None:
        statement = statement.where(MeetingIndexRow.source_sha256 == source_sha256)
    return tuple(
        MeetingRecordIndexed(
            record_id=row.record_id,
            project_id=row.project_id,
            source_sha256=row.source_sha256,
            record_format=row.record_format,
            record_index=row.record_index,
            timestamp_label=row.timestamp_label,
            record_fingerprint=row.record_fingerprint,
            text=row.text,
            locator_json=row.locator_json,
            ingested_at=row.ingested_at.isoformat(),
        )
        for row in session.scalars(statement)
    )


def _the_hit(row: MeetingIndexRow) -> MeetingHit:
    """The hit one row answers with: the record and its provenance."""
    return MeetingHit(
        record_id=row.record_id,
        project_id=row.project_id,
        source_sha256=row.source_sha256,
        record_format=row.record_format,
        record_index=row.record_index,
        timestamp_label=row.timestamp_label,
        record_fingerprint=row.record_fingerprint,
        text=row.text,
        locator_json=row.locator_json,
        ingested_at=row.ingested_at.isoformat(),
    )
