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
from labcairn.material.units import Adapter, ExtractedUnit, ExtractionResult, register
from labcairn.material.units import register as _register
from labcairn.material.version import derive_extraction_version
from labcairn.sources.locators import CsvLocator, TextLocator
from labcairn.sources.source import SourceKind

#: Spelled out rather than escaped: a NUL or a newline written as a
#: backslash sequence inside a generated test file is the kind of thing
#: that survives a copy and breaks the file.
NL = chr(10)
BT = chr(96)
NUL = chr(0)


def _text(data: bytes) -> ExtractionResult:
    from labcairn.material.units import adapter_for

    return adapter_for(SourceKind.TEXT).extract(data)


def _md(data: bytes) -> ExtractionResult:
    from labcairn.material.units import adapter_for

    return adapter_for(SourceKind.MARKDOWN).extract(data)


def _csv(data: bytes) -> ExtractionResult:
    from labcairn.material.units import adapter_for

    return adapter_for(SourceKind.CSV).extract(data)


def _line_of(unit: ExtractedUnit) -> TextLocator:
    assert isinstance(unit.locator, TextLocator), unit.locator
    return unit.locator


def _cell_of(unit: object) -> CsvLocator:
    assert isinstance(unit.locator, CsvLocator)  # type: ignore[attr-defined]
    return unit.locator  # type: ignore[attr-defined]


def _codes(result: object) -> set[str]:
    return {p.code for p in result.problems}  # type: ignore[attr-defined]


# --------------------------------------------------------------------------
# BOM-less UTF-16 was accepted as readable, with NULs no author wrote
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "encoding",
    ["utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be"],
)
def test_bom_less_utf16_reads_back_as_the_original_text(encoding: str) -> None:
    """Strict UTF-8 accepts these: every ASCII char followed by a NUL.

    That is the one input class that defeated "decode strictly or
    disclose" -- the decode *succeeds*, and the output is a string no
    author wrote.

    The assertion is the **exact text**, not the absence of a NUL. A
    weaker form of this test was green over a regression that turned
    "Hello" into CJK: the garbage contains no NUL either.
    """
    result = _text("Hello".encode(encoding))
    assert result.units, result.problems
    assert result.units[0].text == "Hello", f"{encoding} produced {result.units[0].text!r}"
    assert "bom_missing_encoding_inferred" in _codes(result), (
        "the encoding was inferred and must be said so"
    )


@pytest.mark.parametrize(
    ("left", "right", "tail"),
    [
        ("alpha", "bravo", chr(10)),  # even byte count
        ("key", "value", ""),  # odd byte count
        ("RECORD", "", ""),
        ("one", "two", "three"),
    ],
    ids=["even", "odd", "mostly-nul", "two-nuls"],
)
def test_a_utf8_file_with_an_embedded_nul_is_refused_not_transcribed(
    left: str, right: str, tail: str
) -> None:
    """Real UTF-8 carrying a NUL is a different thing from UTF-16.

    An earlier attempt at the fallback tried every encoding and took the
    first that decoded without NULs, which turned this into CJK whenever
    the byte count happened to be even -- so whether your data survived
    depended on its length. Density is the gate: a UTF-16 run is ~50% NUL
    and UTF-32 ~75%, while this is well under 12%.
    """
    nul = chr(0)
    payload = (left + nul + right + tail).encode()
    result = _text(payload)
    assert result.units == (), [u.text for u in result.units]
    assert "text_contains_nul" in _codes(result)


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


# --------------------------------------------------------------------------
# a title row silently became the header
# --------------------------------------------------------------------------


def test_a_title_row_being_taken_as_the_header_is_announced() -> None:
    """Instrument exports and Excel put a title above the real header.

    Taking it silently produced a record where the column ``mean`` appears
    nowhere and the measurement ``3.0`` sits at ``column=" 2024"`` -- an
    address no reader can resolve. The announcement must show the names
    it chose, or it diagnoses nothing.
    """
    payload = ("Study Results, 2024" + NL + "trial,mean" + NL + "alpha,3.0" + NL).encode()
    result = _csv(payload)
    assert "csv_header_row" in _codes(result)
    detail = next(p.detail for p in result.problems if p.code == "csv_header_row")
    assert "Study Results" in detail


def test_a_leading_blank_row_is_diagnosable_rather_than_merely_dropped() -> None:
    """Everything was dropped, and the problems blamed raggedness."""
    payload = (NL + "Study Results 2024" + NL + "trial,mean" + NL + "alpha,3.0" + NL).encode()
    result = _csv(payload)
    assert result.units == ()
    assert "csv_header_row" in _codes(result)
    assert "csv_later_row_wider_than_header" in _codes(result)


def test_an_ordinary_csv_still_extracts() -> None:
    """The header announcement is not a refusal."""
    payload = ("trial,mean" + NL + "alpha,3.0" + NL).encode()
    result = _csv(payload)
    cells = {(_cell_of(u).row, _cell_of(u).column): u.text for u in result.units}
    assert cells == {(2, "trial"): "alpha", (2, "mean"): "3.0"}


# --------------------------------------------------------------------------
# the delimiter announcement must carry evidence, not only a verdict
# --------------------------------------------------------------------------


def test_a_tied_delimiter_choice_says_it_was_a_tie() -> None:
    """ "The header below is the check" fails when the header looks fine.

    ``note;mean`` is a plausible column name and ``a,b;3.0`` a plausible
    value, so the stated check cannot catch the case it was written for.
    The column counts can, because they show two candidates level.
    """
    payload = ("trial,note;mean" + NL + 'alpha,"a,b";3.0' + NL).encode()
    result = _csv(payload)
    detail = next(p.detail for p in result.problems if p.code == "delimiter_used")
    assert "tie" in detail.lower(), detail
    assert ":" in detail, "the counts themselves must be shown"


# --------------------------------------------------------------------------
# markdown structure inside code
# --------------------------------------------------------------------------


def test_a_hash_inside_a_fence_is_not_a_section() -> None:
    """A Python comment in a fenced block is not a heading.

    It set the section for every line after it -- including the real prose
    -- and ``section`` is part of the address, so those citations resolved
    to nothing.
    """
    fence = BT * 3
    payload = (
        "# Methods"
        + NL
        + NL
        + fence
        + "python"
        + NL
        + "# a comment, not a heading"
        + NL
        + "x = 1"
        + NL
        + fence
        + NL
        + NL
        + "real body"
        + NL
    ).encode()
    sections = {_line_of(u).section for u in _md(payload).units}
    assert "a comment, not a heading" not in sections
    assert sections == {"Methods"}


def test_four_spaces_of_indent_is_code_not_a_heading() -> None:
    """CommonMark allows 0-3 spaces before an ATX heading; 4 is code."""
    payload = ("# T" + NL + "    # indented code" + NL + "body" + NL).encode()
    assert {_line_of(u).section for u in _md(payload).units} == {"T"}


def test_three_spaces_of_indent_is_still_a_heading() -> None:
    payload = ("# T" + NL + "   # shallow" + NL + "body" + NL).encode()
    assert {_line_of(u).section for u in _md(payload).units} == {"T", "shallow"}


# --------------------------------------------------------------------------
# R1 -- a NUL is only a proxy, and the proxy fails on non-Latin UTF-16
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["Р", "Привет", "ā", "áção", "مرحبا", "数据表"],  # noqa: RUF001 - the point is that these are non-Latin
)
def test_bom_less_utf16_with_no_ascii_is_refused_not_transcribed(text: str) -> None:
    """A NUL is a proxy for UTF-16 and the proxy only holds when the file
    contains ASCII -- because ASCII is what produces the NULs.

    A UTF-16 file with no ASCII has no NULs, decodes cleanly as UTF-8, and
    was certified readable with **nothing disclosed**: one letter in, two
    characters out, one of them EOT.

    Control characters are the general evidence, so they are the gate. Tab,
    newline, vertical tab, form feed and carriage return are excluded
    because they occur in real text files -- form feed especially, since it
    is a page separator in every format that has one.
    """
    result = _text(text.encode("utf-16-le"))
    assert result.units == (), [u.text for u in result.units]
    # Which refusal fires depends on where the evidence shows up: bytes
    # that are not valid UTF-8 fail the strict decode, and only bytes that
    # *are* valid UTF-8 reach the control-character gate. Both are
    # refusals, which is the property being asserted.
    assert _codes(result) & {
        "text_contains_control",
        "text_contains_nul",
        "text_not_decodable",
    }, result.problems


@pytest.mark.parametrize(
    ("payload", "label", "expected_first_line"),
    [
        (b"plain text", "ascii", "plain text"),
        ((chr(97) + chr(12) + chr(98)).encode(), "form feed", chr(97) + chr(12) + chr(98)),
        (
            (chr(97) + chr(9) + chr(98) + chr(10) + chr(99)).encode(),
            "tab and newline",
            chr(97) + chr(9) + chr(98),
        ),
        ((chr(97) + chr(13) + chr(10) + chr(98)).encode(), "crlf", chr(97)),
        ("café über".encode(), "latin", "café über"),
        ("数据".encode(), "cjk", "数据"),
    ],
)
def test_ordinary_text_with_legal_control_characters_is_not_refused(
    payload: bytes, label: str, expected_first_line: str
) -> None:
    """The gate must not refuse text that legitimately carries them.

    Compared against the first *line*, because a payload containing a
    newline is several lines and only the first is one unit.
    """
    result = _text(payload)
    assert result.units, f"{label}: nothing extracted"
    assert not (_codes(result) & {"text_contains_nul", "text_contains_control"}), (
        f"{label}: refused with {list(_codes(result))}"
    )
    # The expectation is passed in rather than computed: str.splitlines()
    # splits on the form feed, which this extractor deliberately does not,
    # so using it here would assert the very behaviour under question.
    assert result.units[0].text == expected_first_line, label


def test_utf16_still_works_when_it_contains_ascii() -> None:
    """The control gate must not have cost us the case we fixed last round."""
    for encoding in ("utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be"):
        result = _text("Results 2024".encode(encoding))
        assert result.units[0].text == "Results 2024", encoding


# --------------------------------------------------------------------------
# the equal-width title row, which a width rule cannot see
# --------------------------------------------------------------------------


def test_an_equal_width_title_row_is_suspected() -> None:
    """Two-column title over two-column header: same width, so the width
    rule structurally cannot see it."""
    payload = ("Study Results, 2024" + NL + "trial,mean" + NL + "alpha,3.0" + NL).encode()
    result = _csv(payload)
    assert "csv_title_row_suspected" in _codes(result)
    detail = next(p.detail for p in result.problems if p.code == "csv_title_row_suspected")
    assert "Study Results" in detail


def test_an_ordinary_csv_is_not_accused_of_having_a_title() -> None:
    payload = ("trial,mean" + NL + "alpha,3.0" + NL).encode()
    assert "csv_title_row_suspected" not in _codes(_csv(payload))


def test_the_header_announcement_states_rather_than_advises() -> None:
    """It fires on every CSV, so advice about a file you may not be looking
    at is noise. The advisory moved to the targeted signal."""
    payload = ("trial,mean" + NL + "alpha,3.0" + NL).encode()
    detail = next(p.detail for p in _csv(payload).problems if p.code == "csv_header_row")
    assert "row 1" in detail
    assert "if the file opens with a title" not in detail.lower()


# --------------------------------------------------------------------------
# nested fences
# --------------------------------------------------------------------------


def test_a_three_backtick_run_does_not_close_a_four_backtick_fence() -> None:
    fence3, fence4 = BT * 3, BT * 4
    payload = (
        "# M"
        + NL
        + fence4
        + NL
        + fence3
        + NL
        + "# inner"
        + NL
        + fence3
        + NL
        + fence4
        + NL
        + "body"
        + NL
    ).encode()
    sections = {_line_of(u).section for u in _md(payload).units}
    assert "inner" not in sections
    assert sections == {"M"}


# --------------------------------------------------------------------------
# the record separators are kept, like every other exotic break
# --------------------------------------------------------------------------


@pytest.mark.parametrize("code", [0x1C, 0x1D, 0x1E])
def test_record_separators_are_kept_like_every_other_exotic_break(code: int) -> None:
    """Refusing these was a wrong refusal, and it cost data for no safety.

    ``csv.reader`` treats FS/GS/RS exactly as it treats VT and FF: none is
    a record terminator, all are kept inside the field. The argument that
    motivated refusing them -- "a character cannot be both evidence of a
    misreading and a line break we keep" -- does not apply, because the
    control gate inspects the whole file *before* ``split_lines`` sees the
    character. The two checks are ordered and never overlap.
    """
    payload = (chr(97) + chr(code) + chr(98) + NL).encode()
    result = _text(payload)
    assert result.units, [p.code for p in result.problems]
    assert result.units[0].text == chr(97) + chr(code) + chr(98)
    assert "text_contains_control" not in _codes(result)


def test_a_non_latin_utf16_file_is_still_refused_after_that_revert() -> None:
    """The revert must not have reopened the round-three hole."""
    for text in ("Р", "Привет", "ā"):  # noqa: RUF001 - non-Latin is the point
        result = _text(text.encode("utf-16-le"))
        assert result.units == (), text
        assert _codes(result) & {"text_contains_control", "text_contains_nul"}, text


# --------------------------------------------------------------------------
# delimiter evidence must describe a record, not a fragment
# --------------------------------------------------------------------------


def test_a_quoted_header_field_spanning_a_newline_still_sniffs_correctly() -> None:
    """Measuring the first *line* measured the fragment ``"a``.

    Every candidate then scored one column, the comma default won, and the
    header shown agreed with the counts and with the wrong answer -- so the
    disclosure added two rounds ago could not be used to falsify anything.
    """
    from labcairn.material.delimited import delimiter_evidence, sniff_delimiter

    payload = '"a' + NL + 'b";c' + NL + "1;2" + NL
    assert sniff_delimiter(payload) == ";"
    evidence = delimiter_evidence(payload)
    assert evidence[";"] > evidence[","], evidence

    result = _csv(payload.encode())
    columns = {_cell_of(u).column for u in result.units}
    assert columns == {"a" + NL + "b", "c"}, columns
