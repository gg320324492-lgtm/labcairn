"""Turning material into rows: kind, hash, extraction, address, disclosure.

ADR-0009 decides *what* is persisted and under which key. This module is the
part between the bytes and those rows, and it is where the four constraints
from ADR-0008 that are about text rather than schema actually bind:

* a character range resolves to exactly what was quoted -- which needs the
  text to be fixed for the file, and the address to be the one the locator
  names;
* the text is the author's words, with spaces -- which is the adapter's
  problem, and is disclosed here when it cannot be met;
* reading order is column-aware, and rotated text is handled or reported;
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
from typing import TYPE_CHECKING, Final

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
    {"no_adapter_for_kind", "text_not_decodable", "xlsx_unreadable", "xlsx_unparseable"}
)

#: ``readability_disclosure`` is free text a user reads; a wall of every
#: problem would be unreadable, and its point is to be read.
_DISCLOSURE_LIMIT: Final[int] = 500

__all__ = [
    "IngestedMaterial",
    "IngestedText",
    "ingest_bytes",
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
    re-ingests of the same path; one is derived from the path's SHA-256 when
    omitted, so the same bytes at the same path produce the same id on two
    machines without a shared database.
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
    # parse. Three states, and the two easy ones are both wrong for material
    # we could not open: ``READABLE`` asserts the source "may be indexed and
    # cited", which is false of it, and ``UNREADABLE_NO_OCR`` asserts *no
    # text layer*, which is a different and equally false claim about a file
    # whose container is broken. ``UNPARSEABLE`` says the third thing --
    # we could not read it, and we say why.
    unopenable = _UNOPENABLE & {p.code for p in problems}
    if unopenable:
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
        source_id=source_id or f"src-{digest[:16]}",
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
    ``CsvLocator`` has no ``page`` and an ``XlsxLocator`` has no
    ``line_start``, and the union type cannot be asked for either.
    """
    from labcairn.db.materials import ExtractedTextRow

    locator = text.locator
    return ExtractedTextRow(
        locator_kind=locator.locator_kind.value,
        locator_key=text.locator_key,
        text=text.text,
        text_sha256=text.text_sha256,
        created_at=created_at,
        page=getattr(locator, "page", None),
        line_start=getattr(locator, "line_start", None),
        line_end=getattr(locator, "line_end", None),
        section=getattr(locator, "section", None),
        row_number=getattr(locator, "row", None),
        column_name=getattr(locator, "column", None),
        sheet_name=getattr(locator, "sheet_name", None),
        cell_ref=getattr(locator, "cell_ref", None),
    )
