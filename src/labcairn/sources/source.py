"""``Source`` and ``SourceAnchor`` — the two halves of the provenance address.

``Source``
    One material file, as ingested: where it is, what it hashed to, how big it
    is, and whether it can be read at all.

``SourceAnchor``
    One addressable place **inside** a source: a page and span, a line range, a
    CSV row and column, a spreadsheet cell, or the inputs and operator behind a
    computed number.

Splitting them is what makes ADR-0004 I4 (hash drift) expressible. A source's
current hash legitimately changes when a file is re-ingested; an anchor's binding
does not. A record that quoted page 3 of ``paper.pdf`` stays bound to the bytes
of ``paper.pdf`` it actually read, and the comparison between "what the file is
now" and "what the record was written against" is a check with a name rather
than a diff of two fields that mean different things.

Readability is on the Source, not the Anchor
--------------------------------------------
ADR-0004 A7 requires a scanned PDF to be ingested, disclosed as unreadable with
an explicit "OCR not available" note, excluded from the index, and refused as a
citation target. That makes ``readability`` and ``readability_disclosure`` a
**paired** field: this model rejects an unreadable source that carries no
disclosure, and a readable source that carries one. Neither state can exist
without the user-facing sentence that goes with it.

What an identifier does and does not prove
------------------------------------------
:class:`SourceIdentifier` validates the **shape** of a DOI or arXiv id. It does
not prove the work exists — a fabricated DOI is shape-valid by construction, and
that is precisely the case LC-P1-09's acceptance names. Existence is C1's job
at LC-P1-09, against a ledger row or a registry. Nothing here should be read as
"we checked the citation".
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)

from labcairn.sources.locators import SourceLocator
from labcairn.sources.primitives import (
    ContentHash,
    NonEmptyText,
    StrictNonNegInt,
    WorkspaceRelativePath,
    require_schema_version,
)

#: The source schema version this build reads. Bumped only with a migration.
SOURCE_SCHEMA_VERSION: int = 1


def _source_version(value: int) -> int:
    return require_schema_version(value, expected=SOURCE_SCHEMA_VERSION, schema="Source")


def _anchor_version(value: int) -> int:
    return require_schema_version(value, expected=SOURCE_SCHEMA_VERSION, schema="SourceAnchor")


class SourceKind(StrEnum):
    """The material format.

    ``OTHER`` is for files LC-P1-08 ingests but Phase 1 cannot address: they can
    be inventoried and hashed, just not cited. It exists so that "we saw this
    file and cannot use it" is a recorded state rather than a silent omission.
    """

    PDF = "pdf"
    MARKDOWN = "markdown"
    TEXT = "text"
    CSV = "csv"
    XLSX = "xlsx"
    OTHER = "other"


class SourceReadability(StrEnum):
    """Whether the bytes can be turned into addressable text.

    The two members exist because ADR-0004 A7 and A9 insist on a distinction
    that most systems collapse: *"we could not look"* is not *"there was nothing
    there"*. A scanned PDF is in the second state, not the first.
    """

    #: Text extractable; the source may be indexed and cited.
    READABLE = "readable"
    #: No text layer and no OCR. Ingestable and hashable, **not citable**.
    #: Requires a non-empty ``readability_disclosure``.
    UNREADABLE_NO_OCR = "unreadable_no_ocr"


class AnchorKind(StrEnum):
    """What an anchor is for.

    The vocabulary is adopted (the *idea*, not any code) from PaperSpine's
    ``{quote, figure, table, equation, absence_scan}`` split, re-expressed in
    LabCairn's terms.
    """

    #: A verbatim passage. The target of C2.
    QUOTATION = "quotation"
    #: A number. The target of C3.
    NUMERIC = "numeric"
    #: A figure, table, equation or section header: located, but with no value
    #: and no verbatim text to compare.
    STRUCTURAL = "structural"
    #: A recorded *absence* — "we searched for X in scope Y and found nothing".
    #: ADR-0004 adopts this from PaperSpine because "no evidence found" and
    #: "we never looked" are different claims and need different records.
    ABSENCE_SCAN = "absence_scan"


class SourceIdentifierKind(StrEnum):
    """Which identifier namespace a value belongs to."""

    DOI = "doi"
    ARXIV = "arxiv"
    ISBN = "isbn"
    #: A LabCairn-internal handle. Carries no external claim whatsoever.
    LOCAL = "local"


#: Shape rules per namespace. These say what a DOI *looks like*; none of them
#: can say whether the work exists (see the module docstring). ``LOCAL`` is
#: absent from this map on purpose — it has no external shape to check.
_IDENTIFIER_PATTERNS: dict[SourceIdentifierKind, str] = {
    SourceIdentifierKind.DOI: r"^10\.\d{4,9}/\S+$",
    SourceIdentifierKind.ARXIV: r"^(\d{4}\.\d{4,5}|[a-z-]+(\.[A-Z]{2})?/\d{7})(v\d+)?$",
    SourceIdentifierKind.ISBN: r"^(97[89][- ]?)?(\d[- ]?){9}[\dX]$",
}


class SourceIdentifier(BaseModel):
    """One identifier for a source, in a named namespace.

    Shape-validated, never existence-validated. A ``doi`` field that passes this
    model has told you it is formatted like a DOI, which is a much smaller claim
    than "this paper exists" — and LC-P1-09's acceptance requires exactly that
    distinction to survive.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: SourceIdentifierKind
    value: NonEmptyText

    @model_validator(mode="after")
    def _shape_matches_kind(self) -> Self:
        pattern = _IDENTIFIER_PATTERNS.get(self.kind)
        if pattern is None:
            return self
        if re.match(pattern, self.value) is None:
            raise ValueError(
                f"{self.value!r} is not a well-formed {self.kind.value} identifier. "
                f"This is a shape check only — it does not establish that the work "
                f"exists. That is cite-support check C1, against the ledger, at "
                f"LC-P1-09."
            )
        return self


class Source(BaseModel):
    """One ingested material file.

    ``relative_path`` is workspace-relative and canonical (see
    :func:`~labcairn.sources.primitives.require_workspace_relative`), so a ledger
    exported with its sources still resolves on the reader's machine — LC-P1-08's
    "keep source paths workspace-relative when exported".

    ``content_sha256`` is compared, never refreshed. ADR-0004 I4 says drift
    invalidates downstream rather than silently re-reading, and a hash that
    updates itself would make drift undetectable.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Annotated[int, AfterValidator(_source_version)] = SOURCE_SCHEMA_VERSION
    source_id: NonEmptyText
    kind: SourceKind
    display_name: NonEmptyText
    relative_path: WorkspaceRelativePath
    content_sha256: ContentHash
    size_bytes: StrictNonNegInt
    readability: SourceReadability = SourceReadability.READABLE
    #: Required non-empty when ``readability`` is ``UNREADABLE_NO_OCR``; must be
    #: absent otherwise. A disclosure nobody has to write is a disclosure nobody
    #: writes, so its absence is a schema error rather than a default.
    readability_disclosure: NonEmptyText | None = None
    identifiers: tuple[SourceIdentifier, ...] = ()
    ingested_at: AwareDatetime

    @model_validator(mode="after")
    def _disclosure_is_paired_with_readability(self) -> Self:
        unreadable = self.readability is SourceReadability.UNREADABLE_NO_OCR
        disclosed = self.readability_disclosure is not None
        if unreadable and not disclosed:
            raise ValueError(
                "an unreadable source must carry readability_disclosure. ADR-0004 A7: "
                "'OCR not available' is part of the record, not something a user has "
                "to infer from a citation that is missing."
            )
        if disclosed and not unreadable:
            raise ValueError(
                "readability_disclosure is set on a readable source. A disclosure "
                "attached to a source we could read is a claim about something that "
                "did not happen."
            )
        return self

    @field_validator("identifiers")
    @classmethod
    def _identifiers_are_unique(
        cls, value: tuple[SourceIdentifier, ...]
    ) -> tuple[SourceIdentifier, ...]:
        seen: set[tuple[SourceIdentifierKind, str]] = set()
        for identifier in value:
            key = (identifier.kind, identifier.value)
            if key in seen:
                raise ValueError(
                    f"duplicate source identifier: {identifier.value!r} "
                    f"({identifier.kind.value}). Two rows for one identifier make "
                    f"'which one did we cite' ambiguous."
                )
            seen.add(key)
        return value


class SourceAnchor(BaseModel):
    """One addressable place inside a :class:`Source`.

    ``bound_source_sha256`` is the source's content hash **as it was when this
    anchor was made**. Comparing it against the source's current
    :attr:`Source.content_sha256` is how ADR-0004 A2 ("hash drift") is detected:
    modify the file after anchoring and C1 fails, rather than the anchor quietly
    re-pointing at different bytes.

    ``excerpt_sha256`` hashes the text this address covers, as read at anchor
    time. It is the anchor's own content binding, distinct from the record-level
    ``extracted_span_sha256`` on
    :class:`~labcairn.evidence.record.EvidenceRecord`: this one says "these are
    the bytes at this place", the other says "this is the text I copied out".

    There is no label field, on purpose — see :mod:`labcairn.sources.locators`.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Annotated[int, AfterValidator(_anchor_version)] = SOURCE_SCHEMA_VERSION
    anchor_id: NonEmptyText
    source_id: NonEmptyText
    kind: AnchorKind
    locator: SourceLocator
    bound_source_sha256: ContentHash
    excerpt_sha256: ContentHash | None = None
    created_at: AwareDatetime
