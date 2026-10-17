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

The adapters themselves follow in the next slice.
"""

from labcairn.material.addressing import (
    LocatorKeyError,
    render_locator_key,
    split_locator_key,
)
from labcairn.material.version import (
    ExtractionVersionError,
    assert_version_tracks_source,
    derive_extraction_version,
    library_versions,
)

__all__ = [
    "ExtractionVersionError",
    "LocatorKeyError",
    "assert_version_tracks_source",
    "derive_extraction_version",
    "library_versions",
    "render_locator_key",
    "split_locator_key",
]
