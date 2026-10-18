"""Turning material into rows: kind, hash, extraction, address, disclosure.

ADR-0009 decides *what* is persisted and under which key. This module is the
part between the bytes and those rows, and it is where the four constraints
from ADR-0008 that are about text rather than schema actually bind:

* a character range resolves to exactly what was quoted -- which needs the
  text to be fixed for the file, and the address to be the one the locator
  names;
* the text is the author's words, with spaces -- which is the adapter's
  problem, and is disclosed here when it cannot be met;
* reading order is **not** column-aware. A PDF page that reads as two columns
  is refused and disclosed rather than extracted, because splicing the columns
  stores sentences the author never wrote; rotated text is likewise not
  detected, so a rotated page would extract in the wrong order and nothing
  would say so;
* the extraction version is recorded, so a library upgrade is attributable.

Two things this deliberately does **not** do.

It does not read the workspace. Bytes arrive from
:class:`~labcairn.workspace.readonly.SourceMaterial`, which is where
LC-P1-04's promise that the original material is never written is enforced.
Reaching past that would make the promise depend on every future caller.

It does not decide that a material with no adapter is an error. A format
Phase 1 cannot address is inventoried, hashed and recorded with no text --
which is a *recorded fact about the format*, distinct from a material that
was read and contained nothing.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
from types import ModuleType
from typing import TYPE_CHECKING, Any, Final

from labcairn.material.addressing import render_locator_key
from labcairn.material.units import (
    Adapter,
    ExtractionProblem,
    ExtractionResult,
    UnknownAdapterError,
    adapter_for,
)
from labcairn.material.version import derive_extraction_version
from labcairn.security.untrusted import UntrustedOrigin, UntrustedText
from labcairn.sources.locators import SourceLocator
from labcairn.sources.source import Source, SourceKind, SourceReadability

if TYPE_CHECKING:
    from labcairn.db.materials import ExtractedTextRow

#: Problems meaning the material could not be opened at all, as opposed to
#: opened and found wanting. These are what make a source UNPARSEABLE.
_UNOPENABLE: Final[frozenset[str]] = frozenset(
    {
        "no_adapter_for_kind",
        "text_not_decodable",
        "xlsx_unreadable",
        "xlsx_unparseable",
        "pdf_unreadable",
        "pdf_extraction_failed",
        "pdf_multicolumn_unsupported",
    }
)

#: Problems meaning the material is intact and carries no text layer, which is
#: a different fact from a container we could not open. These are what make a
#: source UNREADABLE_NO_OCR, and that member is not decorative: it exists in
#: ADR-0010's vocabulary, in the schema's CHECK constraint and in the
#: disclosure's non-null requirement, and before this set was split out no code
#: path in ``src/`` produced it at all -- a scanned PDF came out ``READABLE``
#: and therefore citable, which is the opposite of what the state is for.
_NO_TEXT_LAYER: Final[frozenset[str]] = frozenset({"pdf_no_text_layer"})

#: ``readability_disclosure`` is free text a user reads; a wall of every
#: problem would be unreadable, and its point is to be read.
_DISCLOSURE_LIMIT: Final[int] = 500

__all__ = [
    "IngestOutcome",
    "IngestedMaterial",
    "IngestedText",
    "ingest_bytes",
    "ingest_into_store",
    "kind_for_path",
    "to_text_row",
]

#: Extension to :class:`SourceKind`. A format with no adapter still gets a
#: kind -- ``OTHER`` -- so "we saw this file and cannot use it" is a row
#: rather than an omission.
_KINDS: Final[dict[str, SourceKind]] = {
    ".pdf": SourceKind.PDF,
    ".md": SourceKind.MARKDOWN,
    ".markdown": SourceKind.MARKDOWN,
    ".txt": SourceKind.TEXT,
    ".text": SourceKind.TEXT,
    ".csv": SourceKind.CSV,
    ".tsv": SourceKind.CSV,
    ".xlsx": SourceKind.XLSX,
}


def kind_for_path(relative_path: str) -> SourceKind:
    """The material's kind from its extension, or ``OTHER``.

    Extension, not content sniffing: sniffing guesses, and a guess here
    would decide which adapter reads the bytes. A mislabelled file is then
    reported by the adapter that cannot read it, which is a fact; a
    sniffed-but-wrong label is a silent misreading.
    """
    return _KINDS.get(PurePosixPath(relative_path).suffix.lower(), SourceKind.OTHER)


@dataclass(frozen=True)
class IngestedText:
    """One extracted cell/line/page, addressed and hashed, not yet stored."""

    locator: SourceLocator
    #: Canonical key. The store's UNIQUE is on this, so it is computed here
    #: once, by the one function allowed to compute one.
    locator_key: str
    text: str
    text_sha256: str


@dataclass(frozen=True)
class IngestedMaterial:
    """A material and everything read from it."""

    source: Source
    texts: tuple[IngestedText, ...]
    problems: tuple[ExtractionProblem, ...]
    extraction_version: str

    def as_untrusted(self, text: IngestedText) -> UntrustedText:
        """Wrap one extracted string for a consumer.

        Done on the way **out**, not on the way in. ADR-0003 C6's guarantee
        is structural and consumer-side -- "the decision function's
        parameters have these types" -- so the boundary that matters is the
        one a consumer crosses to get characters. Wrapping at ingestion would
        put a dataclass through every internal step, and a `TEXT` column
        cannot hold one.
        """
        return UntrustedText(
            value=text.text,
            origin=UntrustedOrigin.SOURCE_DOCUMENT,
            locator=text.locator_key,
        )


def _content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _adapter_version(adapter: Adapter) -> str:
    return derive_extraction_version(adapter.source_modules(), adapter.libraries())


def _id_for_path(relative_path: str) -> str:
    """A source id that identifies a *location*, not a version of its bytes.

    Deriving it from the content hash instead -- which this did -- makes every
    edit a new material. Two things then break, and neither announces itself.
    ``sources.relative_path`` is UNIQUE, so re-ingesting an edited file raised
    ``IntegrityError``; and because this function opens no transaction of its
    own and rolls nothing back, the caller's session stayed poisoned, failing
    every later call with ``PendingRollbackError`` even for unrelated files.

    ``walk.py`` passed an explicit location-derived id and so never hit either,
    which is why 508 material tests stayed green against a public API that
    could not be called twice on an edited file.
    """
    return f"src-{hashlib.sha256(relative_path.encode('utf-8')).hexdigest()[:16]}"


def ingest_bytes(
    data: bytes,
    *,
    relative_path: str,
    display_name: str,
    ingested_at: datetime,
    source_id: str | None = None,
) -> IngestedMaterial:
    """Read one material and produce the rows that describe it.

    ``source_id`` is accepted so a caller can keep a stable identity across
    re-ingests of the same path. When omitted it is derived from the path
    alone -- *not* from the bytes -- so two machines ingesting the same
    workspace agree on it, and **editing a file does not make it a new
    material**. That second half is the point: a content-derived id turns
    every edit into a different source, and ``sources.relative_path`` is
    UNIQUE, so the second ingest of an edited file cannot be stored at all.
    See :func:`_id_for_path`.
    """
    kind = kind_for_path(relative_path)
    digest = _content_hash(data)

    problems: list[ExtractionProblem] = []
    texts: tuple[IngestedText, ...] = ()
    version = "no-adapter"

    try:
        adapter = adapter_for(kind)
    except UnknownAdapterError as exc:
        problems.append(ExtractionProblem(code="no_adapter_for_kind", detail=str(exc)))
    else:
        version = _adapter_version(adapter)
        result: ExtractionResult = adapter.extract(data)
        problems.extend(result.problems)
        texts = tuple(
            IngestedText(
                locator=unit.locator,
                locator_key=render_locator_key(unit.locator),
                text=unit.text,
                text_sha256=_text_hash(unit.text),
            )
            for unit in result.units
        )

    # Readability, which is a claim about the bytes rather than about the
    # parse. Three states, and picking the wrong one puts a falsehood in the
    # one field that decides citability.
    #
    # ``READABLE`` asserts the source "may be indexed and cited", which is
    # false of anything this pass produced no text for. ``UNREADABLE_NO_OCR``
    # asserts *no text layer*, which is true of a scan and false of a broken
    # container -- and false, in the other direction, of a two-column page we
    # declined to read. ``UNPARSEABLE`` is the remaining bucket: we did not
    # obtain usable text, and the disclosure says which of those it was.
    unopenable = _UNOPENABLE & {p.code for p in problems}
    no_text_layer = _NO_TEXT_LAYER & {p.code for p in problems}
    if no_text_layer:
        readability = SourceReadability.UNREADABLE_NO_OCR
        disclosure = "; ".join(p.detail for p in problems if p.code in no_text_layer)[
            :_DISCLOSURE_LIMIT
        ]
    elif unopenable:
        readability = SourceReadability.UNPARSEABLE
        disclosure = "; ".join(p.detail for p in problems if p.code in unopenable)[
            :_DISCLOSURE_LIMIT
        ]
    else:
        readability = SourceReadability.READABLE
        disclosure = None
        # A material that produced no text and no explanation is the one case
        # that must not pass silently. A readable file with genuinely nothing
        # in it is a fact; a readable file we failed to read is a bug, and
        # ADR-0004 A7 says the two must not be confused.
        if not texts and not problems:
            problems.append(
                ExtractionProblem(
                    code="extracted_nothing_and_said_nothing",
                    detail=(
                        "the material was read and produced neither text nor an "
                        "explanation. Recorded rather than passed off as an empty file."
                    ),
                )
            )

    source = Source(
        source_id=source_id or _id_for_path(relative_path),
        kind=kind,
        display_name=display_name,
        relative_path=relative_path,
        content_sha256=digest,
        size_bytes=len(data),
        readability=readability,
        readability_disclosure=disclosure,
        identifiers=(),
        ingested_at=ingested_at,
    )
    return IngestedMaterial(
        source=source,
        texts=texts,
        problems=tuple(problems),
        extraction_version=version,
    )


def adapter_source_modules(kind: SourceKind) -> tuple[ModuleType, ...]:
    """The modules whose source defines this kind's extraction.

    Exposed so a caller can record which code produced a set of rows
    without running an extraction.
    """
    return adapter_for(kind).source_modules()


def to_text_row(text: IngestedText, *, created_at: datetime) -> ExtractedTextRow:
    """Flatten one extracted unit into the writer's row shape.

    Lives here rather than in :mod:`labcairn.db.materials` because reading a
    concrete locator's fields is the material layer's knowledge: a
    ``CsvLocator`` has no ``page`` and an ``XlsxLocator`` has no ``line``.

    Dispatched by concrete type rather than by ``getattr``. A ``getattr``
    default of ``None`` silently turned a wrong field name into a missing
    one: ``TextLocator.line`` read as ``line_start`` yielded ``None``, every
    Markdown line failed the ``text_shape`` CHECK, and the failure surfaced
    as a store error on a file whose extraction was correct. An explicit
    ``else: raise`` turns the same mistake into a loud one.
    """
    from labcairn.db.materials import ExtractedTextRow
    from labcairn.sources.locators import CsvLocator, PdfLocator, TextLocator, XlsxLocator

    locator = text.locator
    if isinstance(locator, PdfLocator):
        return ExtractedTextRow(
            locator_kind=locator.locator_kind.value,
            locator_key=text.locator_key,
            text=text.text,
            text_sha256=text.text_sha256,
            created_at=created_at,
            page=locator.page,
        )
    if isinstance(locator, TextLocator):
        return ExtractedTextRow(
            locator_kind=locator.locator_kind.value,
            locator_key=text.locator_key,
            text=text.text,
            text_sha256=text.text_sha256,
            created_at=created_at,
            line_start=locator.line,
            line_end=locator.line_end,
            section=locator.section,
        )
    if isinstance(locator, CsvLocator):
        return ExtractedTextRow(
            locator_kind=locator.locator_kind.value,
            locator_key=text.locator_key,
            text=text.text,
            text_sha256=text.text_sha256,
            created_at=created_at,
            row_number=locator.row,
            column_name=locator.column,
        )
    if isinstance(locator, XlsxLocator):
        return ExtractedTextRow(
            locator_kind=locator.locator_kind.value,
            locator_key=text.locator_key,
            text=text.text,
            text_sha256=text.text_sha256,
            created_at=created_at,
            sheet_name=locator.sheet_name,
            cell_ref=locator.cell_ref,
        )
    raise TypeError(f"no row shape for {type(locator).__name__}")


@dataclass(frozen=True)
class IngestOutcome:
    """What one ingest wrote. Counts are reported, not predicted."""

    material: IngestedMaterial
    source_rows: int
    text_rows_written: int
    text_rows_present: int
    problem_rows_written: int
    problem_rows_present: int


def ingest_into_store(
    session: Any,
    data: bytes,
    *,
    relative_path: str,
    display_name: str,
    ingested_at: datetime,
    source_id: str | None = None,
) -> IngestOutcome:
    """Ingest one material and persist everything it produced.

    This is the wiring the pieces were waiting for. ``ingest_bytes`` stops
    at a return value and ``put_source_problems`` waits for a caller, so a
    disclosure had a table and no way to reach it -- which is the same
    "a disclosure with no destination" problem ADR-0010 set out to close,
    one layer further out than the fix went.

    One transaction. A material whose texts fail the constraints leaves no
    partial ``sources`` row, because the counts below are what survived the
    commit rather than what the loops intended to write.
    """
    from labcairn.db.materials import (
        put_source,
        put_source_problems,
        put_source_texts,
    )

    material = ingest_bytes(
        data,
        relative_path=relative_path,
        display_name=display_name,
        ingested_at=ingested_at,
        source_id=source_id,
    )
    put_source(session, material.source)
    texts_written, texts_present = put_source_texts(
        session,
        source_content_sha256=material.source.content_sha256,
        extraction_version=material.extraction_version,
        rows=[to_text_row(t, created_at=ingested_at) for t in material.texts],
    )
    problems_written, problems_present = put_source_problems(
        session,
        source_id=material.source.source_id,
        extraction_version=material.extraction_version,
        problems=[(p.code, p.detail, p.location) for p in material.problems],
        created_at=ingested_at,
    )
    session.commit()
    return IngestOutcome(
        material=material,
        source_rows=1,
        text_rows_written=texts_written,
        text_rows_present=texts_present,
        problem_rows_written=problems_written,
        problem_rows_present=problems_present,
    )
