"""``labcairn.sources`` — the provenance address: what was read, and where.

Two models, one job: make every scientific statement traceable to a **located**
piece of material with a content hash behind it
(``docs/ARCHITECTURE.md``, "Identity and authority").

* :class:`~labcairn.sources.source.Source` — one ingested file.
* :class:`~labcairn.sources.source.SourceAnchor` — one address inside it.
* :mod:`~labcairn.sources.locators` — the closed union of addresses, one model
  per material kind, discriminated and ``extra="forbid"``.
* :mod:`~labcairn.sources.primitives` — the domain-free pieces the other two
  contract packages share (content hash, non-empty text, workspace-relative
  path, schema-version gate).

What is deliberately **not** here: parsing anything. Reading a PDF page, opening
a CSV, decoding a spreadsheet cell is LC-P1-08. This package defines the address
such a reader would produce; it does not read.

The one thing this package is opinionated about is precision. An address is
structured, frozen and closed, because the alternative — a prose string like
``"paper.pdf pages 1-3"`` — is what ADR-0004 rejects when it rejects PaperQA2:
a locator you cannot re-derive cannot be checked, and an uncheckable locator
becomes an unciteable citation.
"""

from __future__ import annotations

from labcairn.sources.locators import (
    LOCATOR_MODELS,
    ComputationLocator,
    CsvLocator,
    LocatorKind,
    PdfLocator,
    SourceLocator,
    TextLocator,
    XlsxLocator,
    describe_locator,
)
from labcairn.sources.primitives import (
    ContentHash,
    NonEmptyText,
    WorkspaceRelativePath,
    require_schema_version,
    require_workspace_relative,
)
from labcairn.sources.source import (
    SOURCE_SCHEMA_VERSION,
    AnchorKind,
    Source,
    SourceAnchor,
    SourceIdentifier,
    SourceIdentifierKind,
    SourceKind,
    SourceReadability,
)

__all__ = [
    "LOCATOR_MODELS",
    "SOURCE_SCHEMA_VERSION",
    "AnchorKind",
    "ComputationLocator",
    "ContentHash",
    "CsvLocator",
    "LocatorKind",
    "NonEmptyText",
    "PdfLocator",
    "Source",
    "SourceAnchor",
    "SourceIdentifier",
    "SourceIdentifierKind",
    "SourceKind",
    "SourceLocator",
    "SourceReadability",
    "TextLocator",
    "WorkspaceRelativePath",
    "XlsxLocator",
    "describe_locator",
    "require_schema_version",
    "require_workspace_relative",
]
