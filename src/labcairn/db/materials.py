"""Writing materials and their extracted text.

Separate from :mod:`labcairn.db.repository` because materials are **workspace
state, not Task state**. ADR-0009 decided that deliberately: a material
belongs to the workspace and must outlive the Tasks that cite it, so it
carries no ``task_id`` and takes no part in the event-sourced Task log. That
is why this is its own module rather than another ``UnitOfWork.put_*``.

It is here rather than in :mod:`labcairn.material` so that the dependency
runs one way. The material package knows about locators and adapters; this
module knows about rows and takes **plain values**, so the database layer
never imports the layer above it.

**Idempotence is explicit, not delegated to the database.** Re-ingesting an
unchanged file must write nothing, because ADR-0009's key makes the same
bytes plus the same extractor the same row. The obvious implementation --
``INSERT OR IGNORE`` -- is rejected: it would also swallow a malformed
``cell_ref`` or a blank ``locator_key``, reporting a row that was refused as
a row that was already there. Existence is therefore checked, and only a
genuine duplicate is skipped; every other constraint violation still raises.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from labcairn.db.models import (
    LOCAL_USER_ID,
    SourceAnchorRow,
    SourceProblemRow,
    SourceRow,
    SourceTextRow,
)
from labcairn.material.addressing import render_locator_key
from labcairn.sources.source import Source, SourceAnchor

__all__ = [
    "ExtractedTextRow",
    "current_texts",
    "put_anchor",
    "put_source",
    "put_source_problems",
    "put_source_texts",
    "text_at",
]

#: Stands in for a null location. SQLite compares NULLs as distinct inside a
#: UNIQUE index, so a nullable location would make "the same whole-file
#: problem, once per run" a success.
WHOLE_FILE = chr(0) + "whole-file"


class ExtractedTextRow:
    """One extracted string on its way to the table.

    A plain data holder rather than a model instance so this module does not
    need to know where the adapter came from. The fields mirror
    :class:`~labcairn.db.models.SourceTextRow`; the adapter-facing type is
    :class:`labcairn.material.ingest.IngestedText`, which converts.
    """

    __slots__ = (
        "cell_ref",
        "column_name",
        "created_at",
        "docx_char_end",
        "docx_char_start",
        "docx_element_path",
        "docx_part",
        "docx_view",
        "line_end",
        "line_start",
        "locator_key",
        "locator_kind",
        "page",
        "row_number",
        "section",
        "sheet_name",
        "text",
        "text_sha256",
    )

    def __init__(
        self,
        *,
        locator_kind: str,
        locator_key: str,
        text: str,
        text_sha256: str,
        created_at: datetime,
        page: int | None = None,
        line_start: int | None = None,
        line_end: int | None = None,
        section: str | None = None,
        row_number: int | None = None,
        column_name: str | None = None,
        sheet_name: str | None = None,
        cell_ref: str | None = None,
        docx_part: str | None = None,
        docx_element_path: str | None = None,
        docx_view: str | None = None,
        docx_char_start: int | None = None,
        docx_char_end: int | None = None,
    ) -> None:
        self.locator_kind = locator_kind
        self.locator_key = locator_key
        self.text = text
        self.text_sha256 = text_sha256
        self.created_at = created_at
        self.page = page
        self.line_start = line_start
        self.line_end = line_end
        self.section = section
        self.row_number = row_number
        self.column_name = column_name
        self.sheet_name = sheet_name
        self.cell_ref = cell_ref
        self.docx_part = docx_part
        self.docx_element_path = docx_element_path
        self.docx_view = docx_view
        self.docx_char_start = docx_char_start
        self.docx_char_end = docx_char_end

    def _values(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__slots__}


def put_source(session: Session, source: Source) -> SourceRow:
    """Insert or refresh the row for ``source``. Idempotent by ``source_id``.

    The refresh is deliberate and not merely convenient: re-ingesting a file
    whose bytes changed must move the recorded hash, or ADR-0004 A2's drift
    detection has nothing to detect against.
    """
    existing = session.scalar(select(SourceRow).where(SourceRow.source_id == source.source_id))
    if existing is None:
        row = SourceRow(
            source_id=source.source_id,
            # ``Source`` has no owner field -- ownership is a store concern.
            # See :data:`labcairn.db.models.LOCAL_USER_ID`: Phase 1 is a local,
            # single-user application and the column exists so a future
            # multi-user migration has something to populate.
            owner_id=LOCAL_USER_ID,
            kind=source.kind.value,
            display_name=source.display_name,
            relative_path=source.relative_path,
            content_sha256=source.content_sha256,
            size_bytes=source.size_bytes,
            readability=source.readability.value,
            readability_disclosure=source.readability_disclosure,
            identifiers=[item.model_dump(mode="json") for item in source.identifiers],
            ingested_at=source.ingested_at,
            schema_version=source.schema_version,
        )
        session.add(row)
        return row

    # Idempotent for an unchanged file. A refresh is only warranted when the
    # bytes actually moved: ADR-0004 A2's drift detection compares the
    # recorded hash, and rewriting eight columns on every re-ingest -- including
    # ``ingested_at``, so the row's own history is rewritten by a read -- made
    # "re-ingesting an unchanged file writes nothing" false for this table even
    # though it held for ``source_texts``.
    if existing.content_sha256 == source.content_sha256:
        return existing

    existing.display_name = source.display_name
    existing.kind = source.kind.value
    existing.content_sha256 = source.content_sha256
    existing.size_bytes = source.size_bytes
    existing.readability = source.readability.value
    existing.readability_disclosure = source.readability_disclosure
    existing.identifiers = [item.model_dump(mode="json") for item in source.identifiers]
    existing.ingested_at = source.ingested_at
    return existing


def put_source_texts(
    session: Session,
    *,
    source_content_sha256: str,
    extraction_version: str,
    rows: Iterable[ExtractedTextRow],
) -> tuple[int, int]:
    """Insert extracted text, skipping only rows already stored.

    Returns ``(written, already_present)``. A duplicate is a *fact about
    re-ingesting an unchanged file*, so it is counted rather than hidden --
    and it is counted by an explicit lookup so that a row the constraints
    reject is still an error instead of looking like a duplicate.
    """
    written = 0
    present = 0
    for row in rows:
        exists = session.scalar(
            select(SourceTextRow.id).where(
                SourceTextRow.source_content_sha256 == source_content_sha256,
                SourceTextRow.extraction_version == extraction_version,
                SourceTextRow.locator_key == row.locator_key,
            )
        )
        if exists is not None:
            present += 1
            continue
        values = row._values()
        session.add(
            SourceTextRow(
                source_content_sha256=source_content_sha256,
                extraction_version=extraction_version,
                **values,
            )
        )
        written += 1
    return written, present


def text_at(
    session: Session,
    *,
    source_content_sha256: str,
    extraction_version: str,
    locator_key: str,
) -> str | None:
    """The text at one address, or ``None`` if it was never extracted."""
    return session.scalar(
        select(SourceTextRow.text).where(
            SourceTextRow.source_content_sha256 == source_content_sha256,
            SourceTextRow.extraction_version == extraction_version,
            SourceTextRow.locator_key == locator_key,
        )
    )


def texts_for(
    session: Session, *, source_content_sha256: str, extraction_version: str
) -> Sequence[SourceTextRow]:
    """Every extracted row for one material under one extraction."""
    return tuple(
        session.scalars(
            select(SourceTextRow)
            .where(
                SourceTextRow.source_content_sha256 == source_content_sha256,
                SourceTextRow.extraction_version == extraction_version,
            )
            .order_by(SourceTextRow.id)
        )
    )


def current_texts(session: Session, *, source_content_sha256: str) -> Sequence[SourceTextRow]:
    """The current extraction of every address in one material.

    **"Current" is the newest row for an address** -- ``created_at DESC,
    id DESC`` -- which is the rule
    :func:`labcairn.evidence.index.locate_anchor` already applies when it
    resolves one anchor. That reader keeps its own copy of the ordering,
    because it resolves one address at a time from a raw connection and
    cannot be asked for a whole material at once; a test asks both readers
    which row is current and requires them to answer alike, which is what
    holds them in step. The ledger may hold more than one extraction of the
    same bytes: an adapter's code changed and the material was re-ingested
    without the file changing. A reader that took the first row it happened to
    find would read whichever extraction the database returned first, and the
    answer would depend on the order of an unordered query -- which is the
    kind of bug that looks like a data problem and is not one.

    Unlike :func:`text_at` and :func:`texts_for`, this reader takes **no
    extraction version**, and that is the whole point of it: the versions are
    what it chooses between. A reader that filtered by version would have to
    be *told* which version is current, which is the question this answers.

    The rows come back ordered by ``locator_key``, so the result is the same
    whichever order the rows were written in.
    """
    rows = session.scalars(
        select(SourceTextRow)
        .where(SourceTextRow.source_content_sha256 == source_content_sha256)
        .order_by(
            SourceTextRow.locator_key,
            SourceTextRow.created_at.desc(),
            SourceTextRow.id.desc(),
        )
    ).all()
    current: dict[str, SourceTextRow] = {}
    for row in rows:
        current.setdefault(row.locator_key, row)
    return tuple(current.values())


def put_anchor(session: Session, anchor: SourceAnchor) -> SourceAnchorRow:
    """Insert the row for ``anchor``.

    **The locator is rendered here, by the one function allowed to render
    it.** An anchor's row holds the canonical key and nothing else, so a
    caller that built a key by hand would put an address in the registry that
    :func:`~labcairn.evidence.index.load_anchor` either cannot rebuild or
    rebuilds into a different place. The rendering is not a caller's choice.

    No duplicate is skipped: an anchor id names one address in one version of
    one material, and the layer mints a fresh id per claim. A repeated id is a
    collision rather than a re-statement, and the primary key refuses it.
    """
    row = SourceAnchorRow(
        anchor_id=anchor.anchor_id,
        source_id=anchor.source_id,
        kind=anchor.kind.value,
        locator_key=render_locator_key(anchor.locator),
        bound_source_sha256=anchor.bound_source_sha256,
        excerpt_sha256=anchor.excerpt_sha256,
        created_at=anchor.created_at,
    )
    session.add(row)
    return row


def put_source_problems(
    session: Session,
    *,
    source_id: str,
    extraction_version: str,
    problems: Iterable[tuple[str, str, str | None]],
    created_at: datetime,
) -> tuple[int, int]:
    """Store disclosures about one material. Returns ``(written, present)``.

    Same shape and same reason as :func:`put_source_texts`: existence is
    checked rather than delegated to ``INSERT OR IGNORE``, because a blank
    ``detail`` refused by the CHECK is a different fact from one already
    stored, and only one of them is a duplicate.
    """
    written = 0
    present = 0
    for code, detail, location in problems:
        where = location if location is not None else WHOLE_FILE
        exists = session.scalar(
            select(SourceProblemRow.id).where(
                SourceProblemRow.source_id == source_id,
                SourceProblemRow.extraction_version == extraction_version,
                SourceProblemRow.code == code,
                SourceProblemRow.location == where,
            )
        )
        if exists is not None:
            present += 1
            continue
        session.add(
            SourceProblemRow(
                source_id=source_id,
                extraction_version=extraction_version,
                code=code,
                detail=detail,
                location=where,
                created_at=created_at,
            )
        )
        written += 1
    return written, present


def problems_for(session: Session, *, source_id: str) -> tuple[SourceProblemRow, ...]:
    """Every disclosure recorded for one material."""
    return tuple(
        session.scalars(
            select(SourceProblemRow)
            .where(SourceProblemRow.source_id == source_id)
            .order_by(SourceProblemRow.id)
        )
    )
