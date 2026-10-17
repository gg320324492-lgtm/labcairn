"""The two derivations ADR-0008 and ADR-0009 name but nothing implemented.

Both were flagged by review as *requirements*, not properties: the
extraction version had no derivation, and the locator key had no
canonical form -- four spellings of one page could coexist as four rows.
These tests exist to show the two now have the properties claimed.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import cast

import pytest

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
from labcairn.sources.locators import (
    ComputationLocator,
    CsvLocator,
    PdfLocator,
    SourceLocator,
    TextLocator,
    XlsxLocator,
)

# --------------------------------------------------------------------------
# locator_key
# --------------------------------------------------------------------------


def test_a_pdf_page_has_a_stable_key() -> None:
    assert render_locator_key(PdfLocator(page=3)) == "k=3:pdf|p=1:3"


def test_a_character_range_is_part_of_the_key() -> None:
    whole = render_locator_key(PdfLocator(page=3))
    span = render_locator_key(PdfLocator(page=3, char_start=10, char_end=20))
    assert whole != span, "a span and the whole page must not share an address"


@pytest.mark.parametrize(
    "locator",
    [
        PdfLocator(page=3),
        PdfLocator(page=3, char_start=0, char_end=1),
        TextLocator(line=5),
        TextLocator(line=5, line_end=9),
        TextLocator(line=5, section="Methods"),
        TextLocator(line=5, line_end=9, section="Methods"),
        CsvLocator(row=12, column="mean"),
        XlsxLocator(sheet_name="Sheet1", cell_ref="B2"),
    ],
)
def test_rendering_round_trips(locator: SourceLocator) -> None:
    """In ADR-0004's sense the key must be *re-derivable*, not just readable."""
    key = render_locator_key(locator)
    back = split_locator_key(key)
    assert back["k"] == locator.locator_kind.value


# Values that would collide under a naive "csv|{row}|{column}" rendering.
# A column header containing a separator is legal, and under the naive form
# it moves the boundary.
INJECTION_HEADERS = [
    "a|b",
    "a=b",
    "4:a",
    "c=1:mean",
    "x|y|z",
    "mean\n",
]


@pytest.mark.parametrize("header", INJECTION_HEADERS)
def test_a_header_cannot_shift_a_key_boundary(header: str) -> None:
    """Two locators differing only in a hostile column name stay distinct."""
    plain = render_locator_key(CsvLocator(row=1, column="mean"))
    hostile = render_locator_key(CsvLocator(row=1, column=header))
    assert plain != hostile, f"header {header!r} collided with 'mean'"


@pytest.mark.parametrize("header", ["", " ", "\t", "　"])
def test_a_blank_column_header_is_refused_by_the_contract(header: str) -> None:
    """Not this module's job: ``CsvLocator.column`` is ``NonEmptyText``.

    Worth stating because it means the key never has to represent one.
    """
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CsvLocator(row=1, column=header)


def test_two_different_locators_never_share_a_key() -> None:
    keys = {
        render_locator_key(PdfLocator(page=3)),
        render_locator_key(PdfLocator(page=3, char_start=1, char_end=2)),
        render_locator_key(TextLocator(line=3)),
        render_locator_key(CsvLocator(row=3, column="c=1:3")),
        render_locator_key(XlsxLocator(sheet_name="s|p=3", cell_ref="B2")),
    }
    assert len(keys) == 5, f"collision: {keys}"


def test_the_four_spellings_review_found_are_not_reproducible() -> None:
    """Before this module existed, these all coexisted as four rows."""
    key = render_locator_key(PdfLocator(page=2))
    for spelling in ("pdf:page=2", "pdf p2", "PDF|PAGE|2", "pdf:page=02"):
        assert key != spelling, f"{spelling!r} is still producible"


def test_a_computation_locator_has_no_address_in_source_texts() -> None:
    """A derived number is addressed by its operator, not a place in a file."""
    locator = ComputationLocator(
        operator_id="ttest", operator_version="1", input_hashes=("a" * 64,)
    )
    with pytest.raises(LocatorKeyError, match="no extracted text"):
        render_locator_key(locator)


def test_a_malformed_key_is_refused_rather_than_guessed() -> None:
    with pytest.raises(LocatorKeyError):
        split_locator_key("no-separator")
    with pytest.raises(LocatorKeyError, match="not length-prefixed"):
        split_locator_key("k=3:pdf|p=3")
    with pytest.raises(LocatorKeyError, match="declares"):
        split_locator_key("k=3:pdf|p=9:3")


# --------------------------------------------------------------------------
# extraction_version
# --------------------------------------------------------------------------


def _module_from(tmp_path: Path, name: str, body: str) -> ModuleType:
    """A throwaway module whose *source* is what the version hashes."""
    path = tmp_path / f"{name}.py"
    path.write_text(body, encoding="utf-8")
    spec = __import__("importlib.util").util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_version_is_derived_from_the_adapter_source(tmp_path: Path) -> None:
    """Change the code, change the version, with nobody remembering to."""
    before = _module_from(tmp_path, "adapter_before", "VALUE = 1\n")
    after = _module_from(tmp_path, "adapter_after", "VALUE = 2\n")
    libs = {"pdfplumber": "0.11.10"}
    assert derive_extraction_version((before,), libs) != derive_extraction_version((after,), libs)


def test_the_same_code_and_libraries_give_the_same_version(tmp_path: Path) -> None:
    """Idempotence: re-ingesting an unchanged file must not fork the key."""
    module = _module_from(tmp_path, "adapter", "VALUE = 1\n")
    libs = {"pdfplumber": "0.11.10"}
    assert derive_extraction_version((module,), libs) == derive_extraction_version((module,), libs)


def test_two_modules_with_identical_content_get_different_versions(tmp_path: Path) -> None:
    """The qualified name is hashed too, so a rename counts as a change.

    Two adapters in different files are different code even when the bytes
    match, and erring toward a distinct version is the safe direction: a
    spurious fork costs one re-extraction, a spurious match loses one.
    """
    one = _module_from(tmp_path, "one", "VALUE = 1\n")
    two = _module_from(tmp_path, "two", "VALUE = 1\n")
    libs = {"pdfplumber": "0.11.10"}
    assert derive_extraction_version((one,), libs) != derive_extraction_version((two,), libs)


def test_a_library_upgrade_changes_the_version(tmp_path: Path) -> None:
    module = _module_from(tmp_path, "adapter", "VALUE = 1\n")
    assert derive_extraction_version(
        (module,), {"pdfplumber": "0.11.10"}
    ) != derive_extraction_version((module,), {"pdfplumber": "0.12.0"})


def test_library_versions_are_ordered_so_the_digest_is_stable(tmp_path: Path) -> None:
    module = _module_from(tmp_path, "adapter", "VALUE = 1\n")
    assert derive_extraction_version((module,), {"a": "1", "b": "2"}) == derive_extraction_version(
        (module,), {"b": "2", "a": "1"}
    )


def test_a_module_with_no_source_refuses_to_produce_a_version() -> None:
    """Better to refuse than to return a version that stops tracking the code."""
    module = ModuleType("sourceless")
    module.__file__ = None
    with pytest.raises(ExtractionVersionError, match="no source file"):
        derive_extraction_version((module,), {})


def test_library_versions_skips_absent_and_versionless_modules() -> None:
    versioned = cast(ModuleType, SimpleNamespace(__name__="pdfplumber", __version__="0.11.10"))
    versionless = cast(ModuleType, SimpleNamespace(__name__="mystery"))
    assert library_versions(versioned, versionless) == {"pdfplumber": "0.11.10"}


def test_a_stale_recorded_version_is_caught(tmp_path: Path) -> None:
    module = _module_from(tmp_path, "adapter", "VALUE = 1\n")
    libs: dict[str, str] = {}
    current = derive_extraction_version((module,), libs)
    assert_version_tracks_source((module,), libs, current)
    with pytest.raises(ExtractionVersionError, match="does not match"):
        assert_version_tracks_source((module,), libs, "0" * 32)


def test_the_version_is_a_short_domain_separated_digest(tmp_path: Path) -> None:
    """Domain-separated, so it can never be mistaken for a sha256 of content.

    The throwaway module goes in ``tmp_path``. An earlier version passed
    ``Path(__file__).parent``, which wrote ``tests/domain_probe.py`` -- and
    committed it, which is the same stray-file failure the fixture guard
    catches elsewhere.
    """
    module = _module_from(tmp_path, "domain_probe", "VALUE = 1\n")
    version = derive_extraction_version((module,), {})
    assert len(version) == 32
    assert all(c in "0123456789abcdef" for c in version)
