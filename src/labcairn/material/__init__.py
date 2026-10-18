"""Ingesting material into the store: source inventory and extracted text.

ADR-0009 decides what is persisted and under which key; ADR-0008 decides
which library reads the bytes. Neither decides *how* a page's text is
produced, and this package is where that work lives.

Two pieces are here because both ADRs name them as **requirements that did
not yet have code**, and a requirement with no implementation is not a
property:

- :mod:`~labcairn.material.addressing` renders a locator into the canonical
  ``locator_key`` the store's key rests on. Review found four spellings of one
  page coexisting as four rows before this existed.
- :mod:`~labcairn.material.version` derives ``extraction_version`` from the
  adapter's own source, so changing extraction code changes the version
  without anyone remembering to bump a constant.

:mod:`~labcairn.material.units` holds what every adapter produces, and
:mod:`~labcairn.material.text` and :mod:`~labcairn.material.delimited` are
the two adapters with no dependency beyond the standard library. Importing
this package registers them, which is why the adapters are modules of it
rather than a registry somebody has to remember to populate.
"""

from labcairn.material import delimited as _delimited  # noqa: F401 - registration
from labcairn.material import pdf as _pdf  # noqa: F401 - registration
from labcairn.material import spreadsheet as _spreadsheet  # noqa: F401 - registration
from labcairn.material import text as _text  # noqa: F401 - registration
from labcairn.material.addressing import (
    LocatorKeyError,
    render_locator_key,
    split_locator_key,
)
from labcairn.material.delimited import CsvAdapter, sniff_delimiter
from labcairn.material.ingest import (
    IngestedMaterial,
    IngestedText,
    IngestOutcome,
    ingest_bytes,
    ingest_into_store,
    kind_for_path,
    to_text_row,
)
from labcairn.material.pdf import PdfAdapter
from labcairn.material.spreadsheet import SpreadsheetAdapter, render_cell
from labcairn.material.text import MarkdownAdapter, PlainTextAdapter, decode_text
from labcairn.material.units import (
    Adapter,
    ExtractedUnit,
    ExtractionProblem,
    ExtractionResult,
    UnknownAdapterError,
    adapter_for,
    register,
    registered_kinds,
)
from labcairn.material.version import (
    ExtractionVersionError,
    assert_version_tracks_source,
    derive_extraction_version,
    library_versions,
)
from labcairn.material.walk import WalkReport, ingest_workspace

__all__ = [
    "Adapter",
    "CsvAdapter",
    "ExtractedUnit",
    "ExtractionProblem",
    "ExtractionResult",
    "ExtractionVersionError",
    "IngestOutcome",
    "IngestedMaterial",
    "IngestedText",
    "LocatorKeyError",
    "MarkdownAdapter",
    "PdfAdapter",
    "PlainTextAdapter",
    "SpreadsheetAdapter",
    "UnknownAdapterError",
    "WalkReport",
    "adapter_for",
    "assert_version_tracks_source",
    "decode_text",
    "derive_extraction_version",
    "ingest_bytes",
    "ingest_into_store",
    "ingest_workspace",
    "kind_for_path",
    "library_versions",
    "register",
    "registered_kinds",
    "render_cell",
    "render_locator_key",
    "sniff_delimiter",
    "split_locator_key",
    "to_text_row",
]
