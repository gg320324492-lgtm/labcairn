"""The two standard-library adapters, and the disclosures they are required to make.

ADR-0004 A7 is the rule under test throughout: *"we could not look" is not
"there was nothing there"*, and *"no evidence found" is not "we never
looked"*. Every test here is one of the two being told apart.
"""

from __future__ import annotations

import pytest

from labcairn.material.delimited import sniff_delimiter
from labcairn.material.units import (
    ExtractedUnit,
    ExtractionResult,
    adapter_for,
    registered_kinds,
)
from labcairn.sources.locators import CsvLocator, TextLocator
from labcairn.sources.source import SourceKind


def _line_of(unit: ExtractedUnit) -> TextLocator:
    """Narrow rather than ``ignore``: the union has five members and only one
    of them has ``.section``."""
    assert isinstance(unit.locator, TextLocator), f"expected a text locator, got {unit.locator}"
    return unit.locator


def _cell_of(unit: ExtractedUnit) -> CsvLocator:
    assert isinstance(unit.locator, CsvLocator), f"expected a csv locator, got {unit.locator}"
    return unit.locator


def _text_result(data: bytes) -> ExtractionResult:
    return adapter_for(SourceKind.TEXT).extract(data)


def _md_result(data: bytes) -> ExtractionResult:
    return adapter_for(SourceKind.MARKDOWN).extract(data)


def _csv_result(data: bytes) -> ExtractionResult:
    return adapter_for(SourceKind.CSV).extract(data)


def _codes(result: ExtractionResult) -> set[str]:
    return {p.code for p in result.problems}


def _substantive(result: ExtractionResult) -> set[str]:
    """Codes other than the always-present delimiter announcement."""
    return _codes(result) - {"delimiter_used"}


# --------------------------------------------------------------------------
# registration
# --------------------------------------------------------------------------


def test_the_standard_library_adapters_register_on_import() -> None:
    kinds = registered_kinds()
    assert SourceKind.TEXT in kinds
    assert SourceKind.MARKDOWN in kinds
    assert SourceKind.CSV in kinds
    assert SourceKind.PDF not in kinds, "the PDF adapter is not written yet"


def test_pdf_has_no_adapter_yet_and_says_so() -> None:
    from labcairn.material.units import UnknownAdapterError

    with pytest.raises(UnknownAdapterError, match="recorded and hashed"):
        adapter_for(SourceKind.PDF)


# --------------------------------------------------------------------------
# plain text
# --------------------------------------------------------------------------


def test_one_unit_per_line_numbered_from_one() -> None:
    result = _text_result(b"alpha\nbravo\ncharlie\n")
    assert [u.locator for u in result.units] == [
        TextLocator(line=1),
        TextLocator(line=2),
        TextLocator(line=3),
    ]
    assert [u.text for u in result.units] == ["alpha", "bravo", "charlie"]


def test_a_blank_line_is_a_line() -> None:
    """Dropping it would be an omission that leaves no trace."""
    result = _text_result(b"alpha\n\nbravo\n")
    assert [u.text for u in result.units] == ["alpha", "", "bravo"]
    assert result.units[1].locator == TextLocator(line=2)


def test_a_trailing_newline_does_not_invent_a_line() -> None:
    assert len(_text_result(b"alpha\n").units) == 1


def test_spaces_inside_a_line_are_preserved_exactly() -> None:
    """ADR-0008 constraint: the author's words, with spaces.

    ``primitives._reject_blank`` says trimming "would change what was
    extracted", and the same applies here: a leading space is content.
    """
    result = _text_result(b"  indented\tand tabbed  \n")
    assert result.units[0].text == "  indented\tand tabbed  "


def test_undecodable_bytes_are_disclosed_and_nothing_is_invented() -> None:
    result = _text_result(b"good line\n\xff\xfe\xfd bad bytes\n")
    assert result.units == ()
    assert "text_not_decodable" in _codes(result)
    assert "not guessed" in result.problems[0].detail


def test_a_utf8_bom_is_stripped_rather_than_kept_as_a_character() -> None:
    result = _text_result(b"\xef\xbb\xbfalpha\n")
    assert result.units[0].text == "alpha"


def test_utf32_is_detected_before_utf16() -> None:
    """The UTF-32-LE BOM starts with the UTF-16-LE BOM."""
    import codecs

    result = _text_result(codecs.BOM_UTF32_LE + "alpha\n".encode("utf-32-le"))
    assert [u.text for u in result.units] == ["alpha"]


def test_empty_input_yields_no_units_and_no_complaint() -> None:
    result = _text_result(b"")
    assert result.units == ()
    assert result.problems == ()


# --------------------------------------------------------------------------
# markdown
# --------------------------------------------------------------------------


def test_a_line_carries_the_heading_it_is_under() -> None:
    result = _md_result(b"# Title\nbody\n## Methods\nmore body\n")
    sections = [_line_of(u).section for u in result.units]
    # The heading line sits under its own heading, per the adapter's rule.
    assert sections == ["Title", "Title", "Methods", "Methods"]


def test_a_heading_line_keeps_itself_as_its_own_section() -> None:
    result = _md_result(b"## Methods\nbody\n")
    assert _line_of(result.units[0]).section == "Methods"
    assert _line_of(result.units[1]).section == "Methods"


def test_a_hash_that_is_not_a_heading_is_left_alone() -> None:
    """``#notaheading`` has no space after the hashes."""
    result = _md_result(b"intro\n#notaheading\nmore\n")
    assert _line_of(result.units[1]).section is None


def test_seven_hashes_is_not_a_heading() -> None:
    result = _md_result(b"####### too deep\n")
    assert _line_of(result.units[0]).section is None


def test_plain_text_never_reports_a_section() -> None:
    result = _text_result(b"# not markdown here\n")
    assert _line_of(result.units[0]).section is None


# --------------------------------------------------------------------------
# csv
# --------------------------------------------------------------------------


def test_the_header_is_row_one_and_data_starts_at_two() -> None:
    result = _csv_result(b"trial,mean,n\nalpha,3.0,10\n")
    by_key = {(_cell_of(u).row, _cell_of(u).column): u.text for u in result.units}
    assert by_key[(2, "mean")] == "3.0"
    assert by_key[(2, "n")] == "10"
    assert _substantive(result) == set()


def test_an_empty_cell_is_a_value_not_a_gap() -> None:
    """A blank measurement and an absent measurement are different claims."""
    result = _csv_result(b"trial,mean\nalpha,\n")
    by_key = {(_cell_of(u).row, _cell_of(u).column): u.text for u in result.units}
    assert by_key[(2, "mean")] == ""


def test_duplicate_headers_are_disclosed_and_not_addressed() -> None:
    """A locator naming an ambiguous header would route a citation at random."""
    result = _csv_result(b"trial,mean,mean\nalpha,3.0,4.0\n")
    assert "csv_duplicate_header" in _codes(result)
    assert all(_cell_of(u).column != "mean" for u in result.units)
    assert [u.text for u in result.units] == ["alpha"]


def test_a_ragged_short_row_is_reported_and_its_fields_kept() -> None:
    result = _csv_result(b"trial,mean,n\nalpha,3.0\n")
    assert "csv_ragged_row" in _codes(result)
    by_key = {(_cell_of(u).row, _cell_of(u).column): u.text for u in result.units}
    assert by_key == {(2, "trial"): "alpha", (2, "mean"): "3.0"}
    assert "not filled in" in next(p.detail for p in result.problems if p.code == "csv_ragged_row")


def test_a_ragged_long_row_reports_the_unnameable_field() -> None:
    result = _csv_result(b"trial,mean\nalpha,3.0,surplus\n")
    assert "csv_cell_without_header" in _codes(result)
    assert {_cell_of(u).column for u in result.units} == {"trial", "mean"}


def test_an_embedded_newline_stays_inside_its_cell() -> None:
    """A quoted newline is part of the value, not a row boundary."""
    result = _csv_result(b'trial,note\nalpha,"line one\nline two"\n')
    by_key = {(_cell_of(u).row, _cell_of(u).column): u.text for u in result.units}
    assert by_key[(2, "note")] == "line one\nline two"


def test_an_empty_file_is_empty_and_says_so() -> None:
    result = _csv_result(b"")
    assert result.units == ()
    assert "csv_empty" in _codes(result)


def test_a_header_only_file_has_no_data_rows() -> None:
    result = _csv_result(b"trial,mean\n")
    assert result.units == ()
    assert _substantive(result) == set()


def test_undecodable_bytes_never_become_cells() -> None:
    result = _csv_result(b"trial,mean\nalpha,\xff\n")
    assert result.units == ()
    assert "text_not_decodable" in _codes(result)


# --------------------------------------------------------------------------
# delimiter sniffing -- a guess, so it is disclosed
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("a,b,c\n1,2,3\n", ","),
        ("a;b;c\n1;2;3\n", ";"),
        ("a\tb\tc\n1\t2\t3\n", "\t"),
        ("a,b\n1,2\n", ","),
        ("single\n", ","),
        ("", ","),
    ],
)
def test_the_delimiter_is_chosen_deterministically(text: str, expected: str) -> None:
    assert sniff_delimiter(text) == expected
    assert sniff_delimiter(text) == sniff_delimiter(text)


def test_a_non_comma_delimiter_is_disclosed() -> None:
    result = _csv_result(b"trial;mean\nalpha;3.0\n")
    assert "delimiter_used" in _codes(result)
    by_key = {(_cell_of(u).row, _cell_of(u).column): u.text for u in result.units}
    assert by_key[(2, "mean")] == "3.0"


def test_a_comma_file_is_not_announced_as_inferred() -> None:
    assert "delimiter_inferred" not in _codes(_csv_result(b"a,b\n1,2\n"))


# --------------------------------------------------------------------------
# what every adapter must share
# --------------------------------------------------------------------------


@pytest.mark.parametrize("kind", [SourceKind.TEXT, SourceKind.MARKDOWN, SourceKind.CSV])
def test_no_adapter_reports_a_library_dependency_it_does_not_have(kind: SourceKind) -> None:
    """Both standard-library adapters. A false entry would fork the version."""
    assert adapter_for(kind).libraries() == {}


@pytest.mark.parametrize("kind", [SourceKind.TEXT, SourceKind.MARKDOWN, SourceKind.CSV])
def test_no_adapter_raises_on_hostile_input(kind: SourceKind) -> None:
    adapter = adapter_for(kind)
    for payload in (b"", b"\x00\x01\x02", b"a" * 100_000, bytes(range(256))):
        adapter.extract(payload)  # must not raise


@pytest.mark.parametrize("kind", [SourceKind.TEXT, SourceKind.MARKDOWN, SourceKind.CSV])
def test_every_unit_addresses_exactly_one_place(kind: SourceKind) -> None:
    adapter = adapter_for(kind)
    result = adapter.extract(
        b"# T\nbody\n"
        if kind is SourceKind.MARKDOWN
        else b"trial,mean\nalpha,3.0\n"
        if kind is SourceKind.CSV
        else b"alpha\nbravo\n"
    )
    keys = [(u.locator.locator_kind, str(u.locator).replace(" ", "")) for u in result.units]
    assert len(keys) == len(set(keys)), "two units share one address"
