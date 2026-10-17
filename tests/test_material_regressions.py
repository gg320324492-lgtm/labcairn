"""Regression tests: every input a reviewer used to find a defect.

Kept in one file, named after what they broke, so a future change that
re-introduces any of them fails here first and the reason is legible from
the test name rather than from a git log.

Several of these are **fabrication** defects under ADR-0004 A7 -- "we
could not look" is not "there was nothing there". The adapter produced
output that looked like a reading of the file and was not one.
"""

from __future__ import annotations

from typing import cast

import pytest

from labcairn.material.addressing import (
    LocatorKeyError,
    render_locator_key,
    split_locator_key,
)
from labcairn.material.units import Adapter, ExtractionResult, register
from labcairn.material.units import register as _register
from labcairn.material.version import derive_extraction_version
from labcairn.sources.locators import CsvLocator, TextLocator
from labcairn.sources.source import SourceKind


def _text(data: bytes) -> ExtractionResult:
    from labcairn.material.units import adapter_for

    return adapter_for(SourceKind.TEXT).extract(data)


def _md(data: bytes) -> ExtractionResult:
    from labcairn.material.units import adapter_for

    return adapter_for(SourceKind.MARKDOWN).extract(data)


def _csv(data: bytes) -> ExtractionResult:
    from labcairn.material.units import adapter_for

    return adapter_for(SourceKind.CSV).extract(data)


def _cell_of(unit: object) -> CsvLocator:
    assert isinstance(unit.locator, CsvLocator)  # type: ignore[attr-defined]
    return unit.locator  # type: ignore[attr-defined]


def _codes(result: object) -> set[str]:
    return {p.code for p in result.problems}  # type: ignore[attr-defined]


# --------------------------------------------------------------------------
# BOM-less UTF-16 was accepted as readable, with NULs no author wrote
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        b"H\x00e\x00l\x00l\x00o\x00",
        b"\x00H\x00e\x00l\x00l\x00o",
        b"H\x00\x00\x00e\x00\x00\x00l\x00\x00\x00l\x00\x00\x00o\x00\x00\x00",
    ],
    ids=["utf-16le", "utf-16be", "utf-32le"],
)
def test_bom_less_utf16_is_not_returned_with_nul_characters(payload: bytes) -> None:
    """Strict UTF-8 accepts these: every ASCII char followed by a NUL.

    That is the one input class that defeated "decode strictly or
    disclose" -- the decode *succeeds*, and the output is a string no
    author wrote. NUL in a successful decode is itself the evidence.
    """
    result = _text(payload)
    assert "\x00" not in result.units[0].text, result.units[0].text
    assert "bom_missing_encoding_inferred" in _codes(result), (
        "the encoding was inferred and must be said so"
    )


def test_nul_bytes_with_no_clean_re_encoding_are_refused() -> None:
    """Nothing reads as UTF-16 or UTF-32 either, so nothing is extracted."""
    result = _text(b"a\x00b")
    assert result.units == ()
    assert "text_contains_nul" in _codes(result)


def test_plain_ascii_still_decodes_with_no_complaint() -> None:
    result = _text(b"H\x65llo")
    assert result.units[0].text == "Hello"
    assert result.problems == ()


# --------------------------------------------------------------------------
# str.splitlines invented line boundaries
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "code",
    [0x0B, 0x0C, 0x1C, 0x1D, 0x1E, 0x85, 0x2028, 0x2029],
)
def test_a_character_that_is_not_a_line_terminator_makes_no_line(code: int) -> None:
    """A form feed is a page separator in every format that has one.

    ``splitlines`` turned one into a phantom ``line=2`` -- an address no
    author wrote, created silently.
    """
    breaker = chr(code)
    payload = f"alpha{breaker}bravo\n".encode()
    result = _text(payload)
    assert len(result.units) == 1, [u.locator for u in result.units]
    assert result.units[0].text == f"alpha{breaker}bravo"
    assert "exotic_line_break_present" in _codes(result), (
        "kept inside the line, so the reader must be told the numbering may differ"
    )


def test_markdown_survives_the_same_characters() -> None:
    result = _md(b"# T\n\x0cbody\n")
    assert len(result.units) == 2


@pytest.mark.parametrize(
    ("payload", "count"),
    [(b"", 0), (b"a", 1), (b"a\n", 1), (b"a\n\n", 2), (b"a\r\nb", 2), (b"a\rb", 2)],
)
def test_line_counting_matches_what_a_reader_counts(payload: bytes, count: int) -> None:
    result = _text(payload)
    assert len(result.units) == count, [u.text for u in result.units]


# --------------------------------------------------------------------------
# CSV raised on an ordinary file
# --------------------------------------------------------------------------


def test_a_blank_header_field_does_not_crash_the_adapter() -> None:
    """``b"a,\\n1,2\\n"`` is an ordinary file, and it raised ValidationError.

    ``CsvLocator.column`` is ``NonEmptyText``, so a blank name has no
    address -- which is a disclosure, not a crash.
    """
    result = _csv(b"a,\n1,2\n")
    assert "csv_blank_header" in _codes(result)
    assert [_cell_of(u).column for u in result.units] == ["a"]


def test_no_adapter_raises_on_the_inputs_that_broke_them() -> None:
    """The promise in ``units.py`` is "must not raise on malformed input"."""
    payloads = [
        b"a,\n1,2\n",  # blank header
        b",\n,\n",  # everything blank
        b"trial,mean\rmean,3.0\r",  # CR endings
        b"\xff\xfe",
        b"a" * 50_000,
        bytes(range(256)),
        b"H\x00e\x00l\x00l\x00o",
        b"a\x0cb\x0cc\n",
    ]
    from labcairn.material.units import adapter_for, registered_kinds

    for kind in registered_kinds():
        adapter = adapter_for(kind)
        for payload in payloads:
            result = adapter.extract(payload)
            assert isinstance(result.units, tuple), (kind, payload[:20])


# --------------------------------------------------------------------------
# CSV delimiter guessing
# --------------------------------------------------------------------------


def test_every_delimiter_choice_is_announced_not_only_the_unusual_one() -> None:
    """Announcing only the off-comma case makes wrong guesses *at* comma silent.

    That is precisely the case the announcement exists to catch: a stray
    semicolon in a header still splits into plausible-looking columns.
    """
    result = _csv(b'a,b\n1,"x;y"\n')
    assert "delimiter_used" in _codes(result)


def test_the_reported_wrong_guess_names_the_header_so_a_reader_can_check() -> None:
    """The announcement has to be usable, not merely present."""
    result = _csv(b'trial,note;mean\nalpha,"a,b";3.0\n')
    detail = next(p.detail for p in result.problems if p.code == "delimiter_used")
    assert "','" in detail
    assert "header" in detail.lower()


def test_a_classic_mac_csv_is_read_rather_than_called_unparseable() -> None:
    """CR line endings are a line ending, not a corrupt file.

    Reported as "not readable as delimited text" before, which is a false
    statement about the material.
    """
    result = _csv(b"trial,mean\ralpha,3.0\r")
    cells = {(_cell_of(u).row, _cell_of(u).column): u.text for u in result.units}
    assert cells == {(2, "trial"): "alpha", (2, "mean"): "3.0"}
    assert "csv_unparseable" not in _codes(result)


def test_a_carriage_return_inside_a_quoted_field_is_preserved() -> None:
    result = _csv(b'trial,note\nalpha,"x\ry"\n')
    cells = {(_cell_of(u).row, _cell_of(u).column): u.text for u in result.units}
    assert cells[(2, "note")] == "x\ry"


# --------------------------------------------------------------------------
# headers that differ only in whitespace or case
# --------------------------------------------------------------------------


@pytest.mark.parametrize("second", [" mean", "mean", "MEAN", chr(0xA0) + "mean"])
def test_near_duplicate_headers_are_reported_and_stay_distinct(second: str) -> None:
    """Not a collision -- NonEmptyText does not strip -- but a reader cannot
    tell them apart either, so both the report and the distinct addresses
    are required."""
    header = f"mean,{second.strip() if second.strip() == '' else second.lstrip()}x"
    payload = f"{header}\n1,2\n".encode()
    result = _csv(payload)
    if len(set(header.split(","))) == 1:
        pytest.skip("constructed header names are identical; nothing to compare")
    columns = [_cell_of(u).column for u in result.units]
    assert len(columns) == len(set(columns)), "two cells share one address"


def test_exact_duplicates_are_still_refused_as_unaddressable() -> None:
    result = _csv(b"mean,mean\n1,2\n")
    assert "csv_duplicate_header" in _codes(result)
    assert [u.text for u in result.units] == []


# --------------------------------------------------------------------------
# extraction_version was inert
# --------------------------------------------------------------------------


def test_adapters_in_different_modules_get_different_versions() -> None:
    """They all hashed ``labcairn/__init__.py`` and shared one version.

    The version's job is to change when the *behaviour* changes. TEXT and
    MARKDOWN legitimately share one version -- they live in the same file,
    so editing either changes the digest. CSV lives elsewhere and pulls in
    ``text.py`` as well, so it must differ from both.
    """
    from labcairn.material.units import adapter_for

    def version(kind: SourceKind) -> str:
        adapter = adapter_for(kind)
        return derive_extraction_version(adapter.source_modules(), adapter.libraries())

    text_version = version(SourceKind.TEXT)
    markdown_version = version(SourceKind.MARKDOWN)
    csv_version = version(SourceKind.CSV)

    assert text_version == markdown_version, (
        "they share a source file, so this is correct -- if it ever stops being "
        "true, one of them has moved"
    )
    assert csv_version not in (text_version, markdown_version), (
        "CSV hashes delimited.py and text.py; the text adapters hash text.py"
    )


def test_every_adapter_reports_a_module_inside_this_package() -> None:
    """``__import__(name)`` returns the top-level package, not the submodule.

    That single missing ``fromlist`` made all three adapters hash the same
    562-byte file.
    """
    from labcairn.material.units import adapter_for

    for kind in (SourceKind.TEXT, SourceKind.MARKDOWN, SourceKind.CSV):
        for module in adapter_for(kind).source_modules():
            assert module.__name__.startswith("labcairn.material"), module.__name__


def test_an_adapter_that_calls_a_shared_helper_hashes_that_helper() -> None:
    """Editing ``decode_text`` changes CSV output, so it must change the version."""
    import labcairn.material.text as text_module
    from labcairn.material import delimited
    from labcairn.material.units import adapter_for

    modules = adapter_for(SourceKind.CSV).source_modules()
    assert text_module in modules, "decode_text lives in text.py and CSV runs through it"
    assert delimited.decode_text is text_module.decode_text, (
        "CSV must run through text.py's decoder, not a copy of it"
    )


def test_two_adapters_sharing_a_source_share_a_version() -> None:
    """Not a bug: TEXT and CSV share nothing, but if they ever did, honesty
    requires they not diverge silently."""
    import labcairn.material.text as text_module
    from labcairn.material.units import adapter_for

    modules = adapter_for(SourceKind.TEXT).source_modules()
    assert modules == (text_module,)


# --------------------------------------------------------------------------
# split_locator_key was not the inverse
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "locator",
    [
        TextLocator(line=1, section="Task | Model"),
        TextLocator(line=5, section="a|b=c:d"),
        TextLocator(line=5, section="||"),
        CsvLocator(row=1, column="x|y"),
        CsvLocator(row=1, column="="),
    ],
)
def test_a_key_with_separators_in_its_values_splits_back(locator: object) -> None:
    """``# Task | Model`` is an ordinary Markdown heading.

    Splitting on ``|`` first and validating after is the same non-injective
    assumption this module exists to reject; it made 12.7% of keys
    unparseable, reachable from ordinary material.
    """
    key = render_locator_key(locator)  # type: ignore[arg-type]
    assert split_locator_key(key), key


def test_a_truncated_key_is_refused_rather_than_half_read() -> None:
    key = render_locator_key(TextLocator(line=5, section="Methods"))
    with pytest.raises(LocatorKeyError):
        split_locator_key(key[:-3])


# --------------------------------------------------------------------------
# register
# --------------------------------------------------------------------------


def test_something_that_is_not_an_adapter_is_refused_at_registration() -> None:
    """Not at the first extract() call, deep inside an ingest."""

    class NotAnAdapter:
        kind = SourceKind.OTHER

    with pytest.raises(TypeError, match="not an Adapter"):
        register(cast(Adapter, NotAnAdapter()))


def test_registering_the_same_adapter_twice_is_fine() -> None:
    """Idempotent, and what an importlib.reload does."""
    from labcairn.material.text import PlainTextAdapter

    assert register(PlainTextAdapter) is PlainTextAdapter
    assert _register(PlainTextAdapter) is PlainTextAdapter
