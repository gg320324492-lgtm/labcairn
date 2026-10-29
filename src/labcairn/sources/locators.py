"""Locators: the closed set of ways a :class:`~labcairn.sources.source.SourceAnchor`
can point at a byte range of material.

Why locators are a **discriminated union and not one wide model**
----------------------------------------------------------------
``docs/ARCHITECTURE.md`` requires that "SourceAnchor precisely locates source
material with a content hash", and LC-P1-08 requires that "fixtures validate
page, row, column and spreadsheet cell anchors **exactly**". A single model with
``page``/``row``/``sheet_name``/``cell_ref`` all optional cannot express that:
every field would need a hand-written "this combination makes sense" rule, and
every new field would silently widen what a locator may claim.

So each locator kind is its own model with ``extra="forbid"``, and the union is
keyed on a ``locator_kind`` discriminator. Two consequences, both tested:

* a payload that puts ``page`` on a CSV locator is rejected as an unknown field,
  not silently accepted with the page dropped;
* a payload naming ``locator_kind: "banana"`` does not reach any member and
  is rejected — the set is closed. (``"docx"`` was in this position until
  LC-P2-07, which gave it an ingest path to be produced by.)

The five kinds are exactly what Phase 1 needs and nothing more. **DOCX was
deliberately absent**: LC-P1-11 owns document export and Markdown/HTML preview
lands there. Adding a locator kind for a format no ingest path produces would be
a promise the contract cannot keep.

**LC-P2-07 added DOCX, and the reason it could be added is that an ingest
path now produces it.** :mod:`labcairn.material.ooxml` reads a Word
document's revision history, so a DOCX is now addressable material rather
than an absent format. The rule the paragraph above states still holds: the
kind exists because something produces it, not because it might be useful
someday.

A1 of ADR-0004 is the reason there is no free-text locator
------------------------------------------------------------
ADR-0004 rejects PaperQA2 in part because its locators are display strings
(``Text.name = f"{doc.docname} pages {name}"``) rather than re-derivable
addresses. That failure mode is prevented here structurally rather than by
convention: :class:`~labcairn.sources.source.SourceAnchor` has **no** free-text
label field. The only rendering is :func:`describe_locator`, which computes a
string *from* the structured fields and therefore cannot drift from them.

The rule this encodes: when a locator does not resolve, the answer is
``fail`` — never "cite the nearest page". There is nothing to fall back *to*,
because there is no prose to trim.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StringConstraints, model_validator

from labcairn.sources.primitives import (
    ContentHash,
    NonEmptyText,
    StrictNonNegInt,
    StrictPosInt,
)

#: A1-style cell reference, **uppercase column letters, no ``$`` anchors**.
#: Lowercase is rejected rather than upcased: ``b12`` and ``B12`` naming the
#: same cell is fine inside a spreadsheet, but a ledger that stores both
#: spellings makes ``seen_cells()`` lie.
#:
#: Public because Pydantic resolves annotation aliases through the defining
#: module's namespace at class-build time; a private alias there is not
#: resolvable and the model fails to build.
XlsxCellRef = Annotated[str, StringConstraints(pattern=r"^[A-Z]{1,3}[1-9][0-9]{0,6}$")]


class LocatorKind(StrEnum):
    """Which material a locator addresses. Closed — see the module docstring."""

    #: Text PDF, addressed by 1-based page and optional character span.
    PDF = "pdf"
    #: Plain text or Markdown, addressed by 1-based line and optional section.
    TEXT = "text"
    #: Delimited text, addressed by 1-based row and column header.
    CSV = "csv"
    #: Spreadsheet, addressed by sheet name and A1-style cell.
    XLSX = "xlsx"
    #: A Word document, addressed by package part, element path and
    #: character range. See :class:`DocxLocator`.
    DOCX = "docx"
    #: A derived number, addressed by the operator that produced it.
    COMPUTATION = "computation"


class _LocatorBase(BaseModel):
    """Shared config. ``frozen`` because a locator is a persisted address.

    A mutable locator would let a record's evidence silently change underneath
    its ``verification_log``; the log records what was checked against a
    particular address, and the address has to still be that address.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


class PdfLocator(_LocatorBase):
    """PDF → document + page + text span.

    ``page`` is **1-based**. Page 0 does not exist in any viewer, and accepting
    it would push a zero-indexing bug to the failure surface, where it reads as
    "one page off" rather than "wrong convention".

    ``char_start``/``char_end`` are a half-open ``[start, end)`` span within the
    page's extracted text, and are optional because LC-P1-09's C2 must also be
    able to check a whole-page quote. Both or neither — a one-ended span has no
    meaning, and inferring the missing end would be exactly the silent
    correction LC-P1-02 forbids.
    """

    locator_kind: Literal[LocatorKind.PDF] = LocatorKind.PDF
    page: StrictPosInt
    char_start: StrictNonNegInt | None = None
    char_end: StrictNonNegInt | None = None

    @model_validator(mode="after")
    def _span_is_well_formed(self) -> Self:
        if (self.char_start is None) != (self.char_end is None):
            raise ValueError(
                "char_start and char_end are both set or both omitted; a half-open "
                "span with one endpoint cannot be located. Omit both to address "
                "the whole page."
            )
        if (
            self.char_start is not None
            and self.char_end is not None
            and self.char_end <= self.char_start
        ):
            raise ValueError(
                f"char_end ({self.char_end}) must be greater than char_start "
                f"({self.char_start}); the span is half-open [start, end) and an "
                f"empty one addresses no text."
            )
        return self


class TextLocator(_LocatorBase):
    """Plain text / Markdown → file + line (+ section heading).

    ``line`` is 1-based, matching every editor a user will check it in, and
    ``line_end`` (inclusive) exists so a multi-line quote is one address rather
    than N adjacent ones that could drift apart.
    """

    locator_kind: Literal[LocatorKind.TEXT] = LocatorKind.TEXT
    line: StrictPosInt
    line_end: StrictPosInt | None = None
    section: NonEmptyText | None = None

    @model_validator(mode="after")
    def _range_is_ordered(self) -> Self:
        if self.line_end is not None and self.line_end < self.line:
            raise ValueError(
                f"line_end ({self.line_end}) precedes line ({self.line}); the range "
                f"is inclusive of both endpoints."
            )
        return self


class CsvLocator(_LocatorBase):
    """CSV → file + row + column.

    ``row`` is 1-based and counts the **physical** row of the file, header
    included. ``column`` is the header text, not an index: a ledger that cites
    ``column 4`` is unreadable to the person who has to check it, and a ledger
    that cites ``"yield_pct"`` is not.

    Which physical row a record number occupies depends on the delimiter, the
    quoting and whether the header is present. Resolving that is LC-P1-08's
    ingest job; this contract only fixes the coordinate that gets resolved.
    """

    locator_kind: Literal[LocatorKind.CSV] = LocatorKind.CSV
    row: StrictPosInt
    column: NonEmptyText


class XlsxLocator(_LocatorBase):
    """XLSX → file + sheet + cell.

    ``cell_ref`` is canonical A1 form: uppercase column, no ``$`` anchors. See
    :data:`XlsxCellRef` for why the spelling is enforced rather than normalised.
    """

    locator_kind: Literal[LocatorKind.XLSX] = LocatorKind.XLSX
    sheet_name: NonEmptyText
    cell_ref: XlsxCellRef


class DocxLocator(_LocatorBase):
    """DOCX → package part + element path + character range, in a named view.

    **A Word document has two texts, and an address must say which one.**

    A `.docx` with tracked changes holds the original and the edited text at
    the same time, in one file. ADR-0014 D4 names the two views: *accepted*
    is the text as if every revision were accepted, *rejected* is the text as
    if every revision were rejected. A character range means different
    characters in each, so **the view is part of the address** and is a
    field rather than a convention. Two locators for the same element in
    different views are different addresses, and they resolve to different
    text — which is correct, because they *are* different text.

    The rules, in one place:

    - ``part`` is the package part's name, e.g. ``word/document.xml``.
    - ``element_path`` locates an element inside that part. The format is
      ``/w:document/w:body/w:p[3]/w:ins[1]``: a ``/``-separated list of
      steps, each ``tag[n]`` where ``n`` is the 1-based index among the
      siblings that share that tag. It is derived from the tree, so it is
      re-derivable from the same tree — which is what ADR-0004 A1 asks of an
      address.
    - ``char_start``/``char_end`` is a half-open ``[start, end)`` span
      within **the addressed element's text in the named view**. Both are set
      or neither is; a one-ended span cannot be located. A zero-length span
      is a *point* in the text, which is how a comment anchored on an
      inserted passage is addressed in the rejected view — where that
      passage is not there.

    **The same rule covers every element.** A paragraph's text in the
    accepted view is the paragraph as it now reads; a ``w:del`` element's
    text in the rejected view is the deleted text; a ``w:ins`` element's
    text in the accepted view is the inserted text. One rule, and the
    deleted text has an address — which is the whole of LC-P2-07, since the
    deleted text is not in the accepted view at all and a range there could
    not name it.
    """

    locator_kind: Literal[LocatorKind.DOCX] = LocatorKind.DOCX
    part: NonEmptyText
    element_path: NonEmptyText
    view: Literal["accepted", "rejected"] = "accepted"
    char_start: StrictNonNegInt | None = None
    char_end: StrictNonNegInt | None = None

    @model_validator(mode="after")
    def _span_is_well_formed(self) -> Self:
        if (self.char_start is None) != (self.char_end is None):
            raise ValueError(
                "char_start and char_end are both set or both omitted; a half-open "
                "span with one endpoint cannot be located. Omit both to address the "
                "whole element."
            )
        if (
            self.char_start is not None
            and self.char_end is not None
            and self.char_end < self.char_start
        ):
            raise ValueError(
                f"char_end ({self.char_end}) precedes char_start ({self.char_start}); "
                f"the span is half-open [start, end)."
            )
        return self


class ComputationLocator(_LocatorBase):
    """A derived number → input hashes + operator + parameters.

    This is the locator for the claim "3.14 came out of this", and it is the
    reason LC-P1-10's reproducibility manifest and ADR-0004's evidence model can
    share one hash lineage (ADR-0004 "Re-evaluation trigger" 3).

    ``input_hashes`` is required non-empty and required **sorted and
    duplicate-free**. Both rules are canonicalisation, not validation: the point
    is that two runs over the same inputs produce byte-identical locators, which
    is what lets a receipt be compared rather than eyeballed. Reordering is not
    rejected for being wrong — it is rejected because two spellings of the same
    run is one too many ways for the comparison to disagree with itself.

    ``parameters`` are canonical JSON with no timestamps, random values or
    counters in them, for the same reason ADR-0003 §C4 keeps them out of an
    approval digest.
    """

    locator_kind: Literal[LocatorKind.COMPUTATION] = LocatorKind.COMPUTATION
    operator_id: NonEmptyText
    operator_version: NonEmptyText
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    input_hashes: Annotated[tuple[ContentHash, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def _inputs_are_canonical(self) -> Self:
        ordered = tuple(sorted(self.input_hashes))
        if len(set(ordered)) != len(ordered):
            raise ValueError(
                f"input_hashes contains duplicates: {list(self.input_hashes)}. The same "
                f"file hashed twice is one input; listing it twice makes two runs "
                f"compare unequal for no reason."
            )
        if ordered != self.input_hashes:
            raise ValueError(
                f"input_hashes is not in canonical sorted order: "
                f"{list(self.input_hashes)}. Sort on write rather than normalising "
                f"on read — a locator that renders two ways cannot be compared."
            )
        return self


#: The locator union, discriminated on ``locator_kind``.
#:
#: Consumers narrow with ``isinstance`` after validation, or read
#: :attr:`locator_kind` when the kind alone is enough.
SourceLocator = Annotated[
    PdfLocator | TextLocator | CsvLocator | XlsxLocator | DocxLocator | ComputationLocator,
    Field(discriminator="locator_kind"),
]

#: Every locator model, for exhaustive tests and schema generation.
LOCATOR_MODELS: tuple[type[_LocatorBase], ...] = (
    PdfLocator,
    TextLocator,
    CsvLocator,
    XlsxLocator,
    DocxLocator,
    ComputationLocator,
)


def describe_locator(locator: SourceLocator) -> str:
    """Render a locator for a human, **computed from its structured fields**.

    Presentation only, and the only rendering path there is — a locator has no
    label field to fall out of sync with it (see the module docstring).

    This is deliberately *not* a fallback: nothing in the cite-support contract
    calls this to decide where something is. It renders an address that already
    resolved. When an address does not resolve, the verdict is ``fail`` and no
    string is produced, because ADR-0004 A1 requires the report to cite nothing
    rather than fall back to the nearest page.
    """
    match locator:
        case PdfLocator(page=page, char_start=start, char_end=end):
            span = f", chars {start}-{end}" if start is not None and end is not None else ""
            return f"pdf: page {page}{span}"
        case TextLocator(line=line, line_end=end, section=section):
            span = f"-{end}" if end is not None and end != line else ""
            heading = f', section "{section}"' if section is not None else ""
            return f"text: line {line}{span}{heading}"
        case CsvLocator(row=row, column=column):
            return f"csv: row {row}, column {column!r}"
        case XlsxLocator(sheet_name=sheet, cell_ref=cell):
            return f"xlsx: {sheet}!{cell}"
        case DocxLocator(part=part, element_path=path, view=view, char_start=start, char_end=end):
            span = f", chars {start}-{end}" if start is not None and end is not None else ""
            return f"docx: {part} {path} ({view}){span}"
        case ComputationLocator(operator_id=op, operator_version=version, input_hashes=hashes):
            plural = "" if len(hashes) == 1 else "s"
            return f"computation: {op}@{version} over {len(hashes)} input{plural}"
