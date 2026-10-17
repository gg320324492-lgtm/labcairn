"""Text PDFs, extracted a whole page at a time. Two columns are a known gap.

**Scope.** This adapter reads a page's text as pdfplumber renders it and does
not attempt to reconstruct reading order across columns. That is a decision
with a measured cost, recorded below rather than buried.

**Why no column detection.** Two rounds of measurement on the repository's
three CC-BY single-column fixtures killed the obvious approach. Body-line
width does not identify a column: these papers are LaTeX single-column with
wide side margins, so a genuine body line spans only 0.10-0.65 of the page.
Twenty-one of sixty-eight measured pages -- all confirmed single-column --
have fewer than half their body lines crossing the page's midpoint, because
those pages carry a full-width figure over a single-column body. Any width- or
midpoint-based rule separates them from two-column pages by coincidence, not
by geometry. Building the extraction on an uncalibrated rule is what ADR-0008
warns against, so there is no such rule here.

**What this costs, stated plainly.** For a page laid out in two columns of
running text, ``extract_text`` emits the lines ordered top to bottom, which
puts a left-column line and the right-column line at the same height next to
each other. The result is not what the paper says, and a citation built on it
would not resolve to the author's words. This adapter cannot detect that page
and does not pretend to. It is recorded in ADR-0011 and in the work-order
status, because a reader who cannot see a gap cannot price it.

**What is delivered and tested.** Everything that does not depend on column
reconstruction: UTF-8/encoding discipline reused from :mod:`.text`, an
extraction version that moves when pdfplumber's moves, no locale in any value,
scanned pages recorded as unreadable rather than empty, and no exception
escaping for any input.

One unit per page. A character range within a page is what
``PdfLocator.char_start``/``char_end`` address, computed against this page's
stored text -- so a page of the right length yields a range that means what it
says.
"""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any

from labcairn.material.units import (
    ExtractedUnit,
    ExtractionProblem,
    ExtractionResult,
    register,
)
from labcairn.sources.locators import PdfLocator
from labcairn.sources.source import SourceKind

__all__ = ["PdfAdapter"]


@register
class PdfAdapter:
    """One unit per page: its 1-based page number and the page's text."""

    kind = SourceKind.PDF

    def extract(self, data: bytes) -> ExtractionResult:
        pdfplumber = _pdfplumber()
        problems: list[ExtractionProblem] = []

        try:
            document = pdfplumber.open(_as_stream(data))
        except Exception as exc:  # any library failure is a disclosure, not a raise
            return ExtractionResult(
                problems=(
                    ExtractionProblem(
                        code="pdf_unreadable",
                        detail=(
                            f"the bytes are not a PDF this reader can open: "
                            f"{type(exc).__name__}: {exc}. It is inventoried and "
                            f"hashed; no text is extracted, because text we could "
                            f"not read is not empty text."
                        ),
                    ),
                )
            )

        units: list[ExtractedUnit] = []
        try:
            with document:
                for index, page in enumerate(document.pages, start=1):
                    if not page.chars:
                        problems.append(
                            ExtractionProblem(
                                code="pdf_no_text_layer",
                                detail=(
                                    f"page {index} holds no text. This may be a scan; "
                                    f"OCR is not available in this phase, so the page "
                                    f"is recorded as unreadable rather than cited as "
                                    f"empty."
                                ),
                                location=f"page {index}",
                            )
                        )
                        continue
                    text = _normalise(page.extract_text() or "")
                    if not text:
                        continue
                    units.append(ExtractedUnit(locator=PdfLocator(page=index), text=text))
        except Exception as exc:
            problems.append(
                ExtractionProblem(
                    code="pdf_extraction_failed",
                    detail=(
                        f"reading stopped part-way: {type(exc).__name__}: {exc}. "
                        f"{len(units)} page(s) were read before it did and are kept; "
                        f"the rest were not read and are not claimed to be empty."
                    ),
                )
            )

        if not units and not problems:
            problems.append(
                ExtractionProblem(
                    code="pdf_extracted_nothing_and_said_nothing",
                    detail=(
                        "the PDF opened and produced neither text nor an explanation. "
                        "Recorded rather than passed off as an empty document."
                    ),
                )
            )

        return ExtractionResult(units=tuple(units), problems=tuple(problems))

    def libraries(self) -> dict[str, str]:
        """pdfplumber's version belongs in the extraction version.

        It reads the container and the content stream, so a dependency
        upgrade can change what a page yields exactly as a change to our own
        adapter can.
        """
        version = getattr(_pdfplumber(), "__version__", None)
        return {"pdfplumber": version} if isinstance(version, str) and version else {}

    def source_modules(self) -> tuple[ModuleType, ...]:
        return (sys.modules[__name__],)


def _pdfplumber() -> Any:
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover - the dependency is declared
        raise RuntimeError(
            "pdfplumber is required to read PDFs; it is a declared dependency"
        ) from exc
    return pdfplumber


def _as_stream(data: bytes) -> Any:
    import io

    return io.BytesIO(data)


def _normalise(text: str) -> str:
    """Strip only what pdfplumber's extraction introduces at a page boundary.

    A PDF page often ends in a stray form feed, an artefact of the page
    boundary and not text the author wrote. Trailing whitespace is trimmed;
    interior spacing is left exactly as it was, because that spacing is what
    a quotation has to match.
    """
    return text.rstrip(" \t\n\r\x0c\x0b\x0e\x0f").strip("\n")
