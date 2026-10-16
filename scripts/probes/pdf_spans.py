"""Reproduce the measurements behind ADR-0008's constraints on PDF ingestion.

Run with pdfplumber available but NOT installed into the project::

    uv run --with pdfplumber python scripts/probes/pdf_spans.py

Deliberately not wired into CI: it needs pdfplumber, which is not yet a
dependency. LC-P1-08 turns each measurement into a real test when it
adopts the library.

Every PDF here is built by hand -- computed xref, no library -- because a
fixture from a PDF generator would bring its own layout decisions into
the measurement. Each check prints its numbers and the script exits
non-zero if any expectation fails, so this is a check and not a printout.

Five constraints are measured, matching the five numbered constraints in
``docs/adr/ADR-0008-pdf-ingestion-library.md``:

  1. page-wide grouping on (fontname, size) merges separate lines
  2. baseline clustering merges columns
  3. page.chars carries no synthesised whitespace in a kerned PDF
  4. no single gutter threshold satisfies both a two-column page and a
     column containing one wide intra-column gap
  5. (fontname, size) is not a valid key for rotated text
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

TITLE = "Efficacy of Widgets in Field Trials"
ORDINALS = ["one", "two", "three", "four", "five"]
BASELINES = [660, 650, 640, 630, 620]

# Fixtures are written to a temporary directory, never the working tree, so
# running this cannot leave probe_*.pdf in the repository.
WORKDIR = Path(tempfile.mkdtemp(prefix="labcairn-probe-"))


def _pdf(content: bytes) -> bytes:
    """Assemble a one-page PDF around a content stream, with a real xref."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman >>",
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
    trailer = f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n"
    out += trailer.encode()
    return bytes(out)


def _save(data: bytes, path: str) -> str:
    target = WORKDIR / path
    with target.open("wb") as handle:
        handle.write(data)
    return str(target)


def _open(pdfplumber: Any, data: bytes, path: str) -> Any:
    return pdfplumber.open(_save(data, path))


def _bands(chars: list[dict], min_gap: float) -> list[list[float]]:
    """Merge glyph x-extents, splitting wherever the gap exceeds min_gap."""
    edges = sorted((c["x0"], c["x1"]) for c in chars)
    merged = [list(edges[0])]
    for x0, x1 in edges[1:]:
        if x0 - merged[-1][1] <= min_gap:
            merged[-1][1] = max(merged[-1][1], x1)
        else:
            merged.append([x0, x1])
    return merged


def _groups(chars: list[dict]) -> dict[tuple[str, float], list[dict]]:
    out: dict[tuple[str, float], list[dict]] = {}
    for char in chars:
        out.setdefault((char["fontname"], round(char["size"], 2)), []).append(char)
    return out


def _columns_pdf() -> bytes:
    """A title spanning the full width, over two columns of body text."""
    parts = [b"BT /F1 14 Tf 72 720 Td (Efficacy of Widgets in Field Trials) Tj ET\n"]
    for word, y in zip(ORDINALS, BASELINES, strict=True):
        run = word.encode()
        parts.append(
            b"BT /F1 9 Tf 72 " + str(y).encode() + b" Td (Left column line " + run + b".) Tj ET\n"
        )
        parts.append(
            b"BT /F1 9 Tf 320 " + str(y).encode() + b" Td (Right column line " + run + b".) Tj ET\n"
        )
    return _pdf(b"".join(parts))


# --------------------------------------------------------------------------
# Constraint 1 -- page-wide grouping on (fontname, size) merges lines
# --------------------------------------------------------------------------


def constraint_1_page_wide_grouping(pdfplumber: Any) -> bool:
    content = (
        b"BT /F1 12 Tf 72 720 Td (Group A mean was 3.0) Tj ET\n"
        b"BT /F2 8 Tf 72 700 Td (smaller footnote text) Tj ET\n"
        b"BT /F1 12 Tf 72 680 Td (Group B mean was 5.0) Tj ET\n"
    )
    with _open(pdfplumber, _pdf(content), "probe_c1.pdf") as pdf:
        chars = pdf.pages[0].chars

    groups = _groups(chars)
    print(f"  groups under (fontname, size): {len(groups)}")
    merged = False
    for (font, size), members in sorted(groups.items()):
        text = "".join(m["text"] for m in members)
        top = min(m["top"] for m in members)
        bottom = max(m["bottom"] for m in members)
        print(f"    {font:<22} {size:>5}pt  top={top:6.2f} bottom={bottom:6.2f}  {text!r}")
        if "Group A" in text and "Group B" in text:
            merged = True

    print(f"  one span containing text from two separate lines: {merged}")
    return merged


# --------------------------------------------------------------------------
# Constraint 2 -- baseline clustering merges columns
# --------------------------------------------------------------------------


def constraint_2_columns(pdfplumber: Any) -> bool:
    with _open(pdfplumber, _columns_pdf(), "probe_c2.pdf") as pdf:
        lines = pdf.pages[0].extract_text_lines()

    for line in lines:
        print(
            f"    top={line['top']:7.2f} x0={line['x0']:6.2f} "
            f"x1={line['x1']:6.2f}  {line['text']!r}"
        )
    interleaved = [ln for ln in lines if "Left" in ln["text"] and "Right" in ln["text"]]
    print(f"  lines containing both columns: {len(interleaved)}")
    return bool(interleaved)


# --------------------------------------------------------------------------
# Constraint 3 -- page.chars carries no synthesised whitespace
# --------------------------------------------------------------------------


def constraint_3_whitespace(pdfplumber: Any) -> bool:
    words = TITLE.split()
    literal = _pdf(b"BT /F1 14 Tf 72 720 Td (" + TITLE.encode() + b") Tj ET\n")

    pieces = [b"(" + w.encode() + b")" for w in words]
    array = (
        b"["
        + b" ".join((b"" if i == 0 else b"-278 ") + piece for i, piece in enumerate(pieces))
        + b"]"
    )
    kerned = _pdf(b"BT /F1 14 Tf 72 720 Td " + array + b" TJ ET\n")

    print(f"  source string: {TITLE!r}  ({len(TITLE)} chars, {len(words)} spaces)")
    print(f"  {'built as':<28} {'chars':>6} {'space glyphs':>14}  joining chars yields")
    for label, data in (("literal 0x20 bytes", literal), ("TJ offsets, no glyph", kerned)):
        with _open(pdfplumber, data, "probe_c3.pdf") as pdf:
            chars = pdf.pages[0].chars
        spaces = sum(1 for c in chars if c["text"] == " ")
        joined = "".join(c["text"] for c in chars)
        print(f"  {label:<28} {len(chars):>6} {spaces:>14}  {joined!r}")
        if label.startswith("TJ"):
            lost = spaces == 0 and joined != TITLE

    print(f"  a kerned PDF yields no space glyph and does not rejoin: {lost}")
    return lost


# --------------------------------------------------------------------------
# Constraint 4 -- no single gutter threshold works
# --------------------------------------------------------------------------


def constraint_4_threshold(pdfplumber: Any) -> bool:
    wide_gap = (
        b"BT /F1 9 Tf 72 660 Td (Results were) Tj ET\n"
        b"BT /F1 9 Tf 200 660 Td (significant at p < 0.05.) Tj ET\n"
        b"BT /F1 9 Tf 72 650 Td (Ordinary spacing line.) Tj ET\n"
    )
    sweep = [5, 10, 20, 30, 40, 50, 70, 100, 140, 200]
    ok_by_fixture: dict[str, set[float]] = {}

    for label, content, expected in (
        ("two-column page", _columns_pdf(), 2),
        ("column with a wide gap", _pdf(wide_gap), 1),
    ):
        with _open(pdfplumber, content, "probe_c4.pdf") as pdf:
            chars = pdf.pages[0].chars
        counts = {g: len(_bands(chars, g)) for g in sweep}
        ok_by_fixture[label] = {g for g, n in counts.items() if n == expected}
        cells = "  ".join(
            f"{g}:{counts[g]}" + ("*" if counts[g] == expected else " ") for g in sweep
        )
        print(f"    {label:<24} expected {expected} column(s)   {cells}")

    two_ok = ok_by_fixture["two-column page"]
    gap_ok = ok_by_fixture["column with a wide gap"]
    print(f"  correct for two-column page : {sorted(two_ok)}")
    print(f"  correct for wide-gap column  : {sorted(gap_ok)}")
    print(f"  overlap                      : {sorted(two_ok & gap_ok)}")
    return not (two_ok & gap_ok)


# --------------------------------------------------------------------------
# Constraint 5 -- (fontname, size) is not a valid key for rotated text
# --------------------------------------------------------------------------


def constraint_5_rotated(pdfplumber: Any) -> bool:
    content = b"BT /F1 10 Tf 0 1 -1 0 200 400 Tm (Rotated label) Tj ET\n"
    with _open(pdfplumber, _pdf(content), "probe_c5.pdf") as pdf:
        chars = pdf.pages[0].chars
        upright = {c["upright"] for c in chars}
        sizes = sorted({round(c["size"], 2) for c in chars})

    print("    source: 'Rotated label' (13 chars, one 10pt run)")
    print(f"    chars: {len(chars)}   upright flags: {upright}   distinct sizes: {sizes}")
    groups = _groups(chars)
    for (_, size), members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        text = "".join(m["text"] for m in members)
        print(f"      size={size:>5}  n={len(members):>2}  {text!r}")

    shredded = len(groups) > 1
    print(f"  one run fragmented into {len(groups)} groups: {shredded}")
    return shredded


CHECKS = (
    ("1. page-wide (fontname, size) merges separate lines", constraint_1_page_wide_grouping),
    ("2. baseline clustering merges columns", constraint_2_columns),
    ("3. page.chars carries no synthesised whitespace", constraint_3_whitespace),
    ("4. no single gutter threshold works", constraint_4_threshold),
    ("5. (fontname, size) is not valid for rotated text", constraint_5_rotated),
)


def main() -> int:
    try:
        import pdfplumber
    except ImportError:
        print("pdfplumber is not installed.")
        print("Run: uv run --with pdfplumber python scripts/probes/pdf_spans.py")
        return 2

    print(f"pdfplumber {pdfplumber.__version__}")
    print(f"fixtures in {WORKDIR}")
    print("Each PDF is built by hand; no PDF generator is involved.\n")

    failures = []
    for title, check in CHECKS:
        print(f"--- {title} ---")
        try:
            ok = bool(check(pdfplumber))
        except Exception as exc:  # a probe that cannot run is not a pass
            print(f"  ERROR: {type(exc).__name__}: {exc}")
            ok = False
        if not ok:
            failures.append(title)
        print(f"  => {'CONFIRMED' if ok else 'NOT REPRODUCED'}\n")

    if failures:
        print("NOT reproduced:")
        for title in failures:
            print(f"  - {title}")
        print("\nADR-0008 cites these as measured. If one no longer reproduces,")
        print("the ADR is wrong, not the probe.")
        return 1

    print(f"All {len(CHECKS)} constraints reproduced.")
    print("ADR-0008's measurements stand.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
