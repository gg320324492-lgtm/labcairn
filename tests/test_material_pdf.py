"""The PDF adapter, tested against the repository's real CC-BY papers.

Three fixtures, all single-column, all previously confirmed by
measurement. They are the reason the adapter makes no column-detection
claim: body-line width on these papers spans 0.10-0.65 of the page, so a
width rule would call genuine single-column pages two-column. The two
round-trip and idempotence tests come from ADR-0009's key; the scan and
garbage tests come from the never-raise and disclose-don't-guess rules
every adapter in this package is held to.
"""

from __future__ import annotations

import datetime as dt
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from labcairn.material import adapter_for
from labcairn.material.ingest import ingest_bytes
from labcairn.sources.source import SourceKind, SourceReadability

pytestmark = pytest.mark.unit

FIXTURES = sorted((Path(__file__).parent / "fixtures" / "papers").glob("*.pdf"))
NOW = dt.datetime(2026, 10, 17, tzinfo=dt.UTC)


def _adapter() -> Any:
    return adapter_for(SourceKind.PDF)


def _codes(result: Any) -> set[str]:
    return {p.code for p in result.problems}


def _extract_one(path: Path) -> Any:
    return _adapter().extract(path.read_bytes())


def test_the_three_real_papers_are_present() -> None:
    assert len(FIXTURES) == 3, "the fixtures these tests measure against are gone"


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_every_real_paper_yields_a_unit_per_page(path: Path) -> None:
    import pdfplumber

    result = _extract_one(path)
    with pdfplumber.open(path) as pdf:
        expected = len(pdf.pages)
    assert len(result.units) == expected, [p.code for p in result.problems]
    assert result.problems == ()


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_page_numbers_are_one_based_and_contiguous(path: Path) -> None:
    result = _extract_one(path)
    assert [u.locator.page for u in result.units] == list(range(1, len(result.units) + 1))


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_extraction_is_deterministic(path: Path) -> None:
    """The same bytes must give the same string, or a character range re-points."""
    first = [(u.locator.page, u.text) for u in _extract_one(path).units]
    second = [(u.locator.page, u.text) for u in _extract_one(path).units]
    assert first == second and first


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_extraction_is_the_same_under_hash_randomisation(path: Path) -> None:
    """pdfplumber renders into sets internally; the digest must not move."""

    script = (
        "import hashlib,sys;"
        f"sys.path.insert(0, {str(Path(__file__).parents[1] / 'src')!r});"
        "from labcairn.material import adapter_for;"
        "from labcairn.sources.source import SourceKind;"
        f"d=open({str(path)!r},'rb').read();"
        "r=adapter_for(SourceKind.PDF).extract(d);"
        "print(hashlib.sha256(''.join(u.text for u in r.units).encode()).hexdigest())"
    )
    digests = set()
    for seed in ("0", "1", "524287"):
        out = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            # The parent decodes UTF-8, so the child has to write UTF-8: the
            # child's output encoding is otherwise the machine's locale
            # encoding, and the two halves of the pipe would not agree.
            env={**__import__("os").environ, "PYTHONHASHSEED": seed, "PYTHONIOENCODING": "utf-8"},
            check=True,
        )
        digests.add(out.stdout.strip())
    assert len(digests) == 1, digests


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_page_text_keeps_interior_spacing(path: Path) -> None:
    """A quotation has to match the stored text, spacing included."""
    result = _extract_one(path)
    body = " ".join(u.text for u in result.units)
    assert "  " in body or "\n" in body, "spacing was collapsed"
    assert not any(unit.text.endswith("\x0c") for unit in result.units)


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_every_unit_has_content(path: Path) -> None:
    result = _extract_one(path)
    assert all(u.text.strip() for u in result.units)


def test_a_page_with_no_text_is_unreadable_not_empty() -> None:
    """A scan has no text layer; OCR is not available, so it is disclosed.

    Asserted on the *resulting Source*, not on the adapter's problem code. The
    previous version of this test asserted only that one of two codes appeared,
    which stayed green while ``ingest_into_store`` went on to record a scanned
    PDF as ``READABLE`` -- the state whose meaning is "may be indexed and
    cited". The code was never the claim; the stored readability is.
    """
    result = ingest_bytes(
        _one_blank_page_pdf(),
        relative_path="scan.pdf",
        display_name="scan.pdf",
        ingested_at=NOW,
    )
    assert result.source.readability is SourceReadability.UNREADABLE_NO_OCR
    assert result.source.readability_disclosure
    assert not result.texts


def test_a_broken_container_is_unparseable_rather_than_a_scan() -> None:
    """The other half of the vocabulary, and the two must not be confused.

    ``UNREADABLE_NO_OCR`` claims *no text layer*, which is false of a container
    that would not open. A reader told "this is a scan, OCR would help" about a
    truncated file has been told something actionable and wrong.
    """
    result = ingest_bytes(
        b"%PDF-1.4 truncated",
        relative_path="broken.pdf",
        display_name="broken.pdf",
        ingested_at=NOW,
    )
    assert result.source.readability is SourceReadability.UNPARSEABLE
    assert result.source.readability_disclosure
    assert not result.texts


@pytest.mark.parametrize("payload", [b"", b"not a pdf", b"%PDF-1.4 truncated", bytes(range(256))])
def test_no_hostile_input_raises(payload: bytes) -> None:
    _adapter().extract(payload)


def test_a_pdf_with_no_text_at_all_is_disclosed() -> None:
    """Build a genuinely empty PDF and confirm it is reported, not blank."""
    result = _adapter().extract(_one_blank_page_pdf())
    assert _codes(result), "a PDF with no text must say so"
    assert not result.units


def test_pdfplumber_version_is_in_the_extraction_version() -> None:
    """It reads the container and the content stream; an upgrade can move it."""
    import pdfplumber

    assert _adapter().libraries().get("pdfplumber") == pdfplumber.__version__


def test_a_two_column_page_is_refused_rather_than_spliced() -> None:
    """The defect this refusal exists for.

    Read straight through, pdfplumber interleaves two columns that share a
    baseline, and the adapter stored the result: two unrelated sentences fused
    into a line the author never wrote, with no problem recorded, in a source
    marked readable and therefore citable. A quote taken from that span would
    quote a sentence that does not exist.

    So the page is not extracted, and the refusal is recorded rather than
    passed off as an empty page.
    """
    result = _adapter().extract(_two_column_pdf())
    assert "pdf_multicolumn_unsupported" in _codes(result)
    assert not result.units, "the page was extracted anyway"
    assert all("LEFT" not in u.text and "RIGHT" not in u.text for u in result.units)


def test_a_refused_page_does_not_become_a_citable_source() -> None:
    """Same refusal, asserted where citability is actually decided.

    The adapter's problem code is not the claim; ``readability`` is, because
    that is the field ``source.py`` defines as "may be indexed and cited".
    """
    ingested = ingest_bytes(
        _two_column_pdf(),
        relative_path="two-col.pdf",
        display_name="two-col.pdf",
        ingested_at=NOW,
    )
    assert ingested.source.readability is not SourceReadability.READABLE
    assert ingested.source.readability_disclosure
    assert not ingested.texts
    assert "two columns" in ingested.source.readability_disclosure


def test_a_single_column_page_of_the_same_shape_is_extracted() -> None:
    """The control. Without it, "always refuse" would pass the test above."""
    result = _adapter().extract(_single_column_pdf())
    assert not _codes(result)
    assert len(result.units) == 1
    assert "LEFT" in result.units[0].text


def test_a_two_column_page_at_the_threshold_is_refused() -> None:
    """The edge of the band, pinned.

    The detector refuses a page whose rival column holds at least 30% of the
    line starts. 7 of 23 is 30.4%, so this page is on the refused side of the
    edge, and 35% would have put it on the other side: at 35% the required
    share is 9 starts and this page has 7, so it would be extracted with its
    columns interleaved.

    The threshold's exact value is not a property on its own -- what is a
    property is that the band is **no wider than the corpus allows**. The
    corpus's own single-column pages cluster at 20-26%, so 30% is the lowest
    share that refuses nothing real. This test is what stops the threshold
    drifting back up into the band, where it would refuse less and splice
    more.
    """
    result = _adapter().extract(_unbalanced_two_column_pdf(7, 16))

    assert "pdf_multicolumn_unsupported" in _codes(result)


def test_a_two_column_page_below_the_band_is_not_refused_and_that_is_the_residual() -> None:
    """The residual, executable rather than only described.

    6 of 22 is 27.3%, below the 30% the detector requires, so this page is
    **not** refused: it is extracted, its left-column line and its
    right-column line sit at the same height beside each other, and the
    result is text no author wrote. That is the residual, and it is a real
    one -- a reader who cannot see it cannot price it.

    The band cannot be closed with this signal: the real single-column pages
    the rule would also catch cluster at 20-26%, in the same place, so any
    threshold that caught this page would refuse seven pages of good prose.
    ADR-0008 records why the one thing that would calibrate the other
    direction -- two-column CC-licensed material -- could not be obtained.

    So the residual is pinned here instead of left to drift. If a future
    corpus makes the band closable, this test is the thing to change, and
    the change is a deletion rather than a reversal.
    """
    result = _adapter().extract(_unbalanced_two_column_pdf(6, 16))

    assert "pdf_multicolumn_unsupported" not in _codes(result)
    assert len(result.units) == 1
    text = result.units[0].text
    assert "LEFT line 0" in text and "RIGHT line 0" in text


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_no_real_paper_is_refused_as_two_column(path: Path) -> None:
    """The false-positive direction, on the only real material there is.

    Detecting two columns is only half the job, and the half that costs
    content. These papers have figures, tables and equations whose parts start
    well right of the margin, which is the same signal a second column gives:
    seven pages across the three fixtures cluster into a second column at
    20-26% of their line starts. An earlier threshold took them, and the
    detector refused 7 of 70 pages of perfectly good single-column prose.

    The corpus is all it has, and MANIFEST.md records why it is the wrong tool
    for the other direction -- there is no two-column paper here to detect. So
    this direction is what the real fixtures can police, and it is policed.
    """
    result = _extract_one(path)
    assert "pdf_multicolumn_unsupported" not in _codes(result), [
        p.detail for p in result.problems if p.code == "pdf_multicolumn_unsupported"
    ]
    assert len(result.units) == _page_count(path)


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_each_page_number_carries_that_pages_own_text(path: Path) -> None:
    """The acceptance clause's "page ... anchors exactly", actually anchored.

    Before this, nothing bound a page number to that page's content: the suite
    checked that unit count equals page count, that the numbers run 1..N, and
    that the joined text is non-blank and correctly spaced. Rotating every
    page's text by one -- so page 1 returns page 2's words -- left all 26 PDF
    tests green. Reversal was caught, but only by the ordering assertion, never
    by a content binding.

    So the binding is stated here: page 1's text must not occur on any later
    page's unit, and the last page's must not occur earlier.
    """
    import pdfplumber

    with pdfplumber.open(path) as document:
        pages = [p.extract_text() or "" for p in document.pages]
    units = _extract_one(path).units
    assert len(units) == len(pages)

    # Bind each locator to the unit's own content, checked against an
    # independent read of that page. Comparing the two page lists to each other
    # -- or checking only that the numbers run 1..N -- passes just as happily
    # when every unit carries its neighbour's text, which is what the first
    # version of this test did.
    for unit, expected in zip(units, pages, strict=True):
        assert _words(unit.text) == _words(expected), (
            f"page {unit.locator.page} does not carry that page's own text"
        )


def _words(text: str) -> list[str]:
    return text.split()


def _page_count(path: Path) -> int:
    import pdfplumber

    with pdfplumber.open(path) as document:
        return len(document.pages)


def _text_pdf(lines: list[tuple[float, float, str]]) -> bytes:
    """A one-page PDF whose text sits at the given x/y positions."""
    content = "BT /F1 11 Tf\n"
    content += "".join(f"1 0 0 1 {x} {y} Tm ({t}) Tj\n" for x, y, t in lines)
    content += "ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF".encode()
    )
    return bytes(out)


def _two_column_pdf() -> bytes:
    """Two columns of twelve lines each, sharing baselines and 248pt apart."""
    return _text_pdf(
        [
            (x, 740 - i * 14, f"{side} line {i} of the {side.lower()} column")
            for i in range(12)
            for x, side in ((72.0, "LEFT"), (320.0, "RIGHT"))
        ]
    )


def _unbalanced_two_column_pdf(left_lines: int, right_lines: int) -> bytes:
    """Two columns of unequal length, sharing baselines and 248pt apart.

    The shorter column's **share of the page's line starts** is what the
    detector weighs, so the counts are the interesting part of this fixture
    and the prose is deliberately different in each column: a reader can see
    which words are whose.
    """
    lines: list[tuple[float, float, str]] = [
        (320.0, 740 - i * 14, f"RIGHT line {i} of the right column") for i in range(right_lines)
    ]
    lines += [(72.0, 740 - i * 14, f"LEFT line {i} of the left column") for i in range(left_lines)]
    return _text_pdf(lines)


def _single_column_pdf() -> bytes:
    """The same density and the same left margin, one column."""
    return _text_pdf([(72.0, 740 - i * 14, f"LEFT line {i} of ordinary prose") for i in range(24)])


def _one_blank_page_pdf() -> bytes:
    """A minimal, valid, text-free PDF built by hand."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>",
        b"<< /Length 0 >>\nstream\n\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n"
    ).encode()
    return bytes(out)
