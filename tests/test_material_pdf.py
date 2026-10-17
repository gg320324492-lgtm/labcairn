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
from labcairn.sources.source import SourceKind

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
            env={**__import__("os").environ, "PYTHONHASHSEED": seed},
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
    """A scan has no text layer; OCR is not available, so it is disclosed."""
    result = _adapter().extract(b"%PDF-1.4\n")
    assert "pdf_unreadable" in _codes(result) or "pdf_no_text_layer" in _codes(result)


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
