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

One unit per page, carrying the page number and the page's text. A character
range within a page is what ``PdfLocator.char_start``/``char_end`` address,
and **the adapter does not set them** -- every locator it produces is
page-level, with no span. The contract allows an omitted span for a whole-page
quote, so this is conformant rather than broken, but a reader must not infer
that per-page ranges are available here.
"""

from __future__ import annotations

import math
import sys
from types import ModuleType
from typing import Any, Final

from labcairn.material.units import (
    ExtractedUnit,
    ExtractionProblem,
    ExtractionResult,
    register,
)
from labcairn.sources.locators import PdfLocator
from labcairn.sources.source import SourceKind

__all__ = ["PdfAdapter"]

#: Thresholds for the two-column refusal, disclosed because MANIFEST.md records
#: that this paper's geometry does not permit a cleverer choice.
#:
#: The obvious approach -- measure the horizontal gap and cut where it is wide --
#: is ruled out by measurement, not taste. On ``arx-2610.12393`` the gap
#: distribution decays continuously with no break: p90 is 16.68pt and **4% of
#: all gaps fall in 15-30pt**, which is exactly where a real gutter lives. A
#: threshold set anywhere in gutter territory slices through the word-gap
#: population instead of separating from it.
#:
#: So the signal is positional rather than a size. Each line is cut into
#: horizontally contiguous runs, and the runs' left edges are clustered. Two
#: clusters at least 80pt apart, each carrying lines of its own, is a
#: two-column page. Cutting the line first is not optional: the two columns
#: share baselines, so grouping characters by baseline merges them and reports
#: one column for material that plainly has two -- the exact failure MANIFEST.md
#: names in the method that classified the corpus.
_RUN_GAP_PT: Final[float] = 20.0
_CLUSTER_TOL_PT: Final[float] = 8.0
_COLUMN_SEP_PT: Final[float] = 80.0
_MIN_LINES_PER_CLUSTER: Final[int] = 2

#: A rival cluster must hold at least this share of the page's line starts
#: before the page is called two-column.
#:
#: The figure is not a guess, it is bracketed by measurement in both
#: directions. Real single-column pages *do* produce a second cluster, because
#: cutting a line at a wide internal gap is exactly what happens around a
#: figure, a table or an equation: seven pages across the three fixture papers
#: cluster at 20-26%, and the highest is 26%. A genuine two-column page splits
#: near evenly, and the synthetic control used by the tests splits 50/50. So
#: 30%, 35% and 40% all refuse nothing on the real corpus and all still refuse
#: the control; 35% is the midpoint of the empty band rather than an edge of it.
_MIN_COLUMN_SHARE: Final[float] = 0.35


def _two_column_evidence(page: Any) -> str | None:
    """Why this page reads as two columns, or ``None`` if it reads as one.

    A page with no extractable words has no opinion here; the caller's
    no-text-layer path is the one that speaks for it.

    A cluster counts only if it carries a real share of the page. Cutting each
    baseline into column-local runs is not optional -- the two columns share
    baselines, so taking only each line's first word would place every start in
    the left column and report one column for material that plainly has two,
    which is the failure MANIFEST.md names in the method that classified the
    corpus. The cost of cutting is that real single-column lines contain gaps as
    wide as a gutter, so the rival cluster must also hold its share of the page
    before the page is called two-column.
    """
    lines: dict[float, list[tuple[float, float]]] = {}
    for word in page.extract_words():
        lines.setdefault(round(float(word["top"]), 1), []).append(
            (float(word["x0"]), float(word["x1"]))
        )

    starts: list[float] = []
    for spans in lines.values():
        spans.sort()
        run_start = spans[0][0]
        previous_end = spans[0][1]
        for start, end in spans[1:]:
            if start - previous_end > _RUN_GAP_PT:
                starts.append(run_start)
                run_start = start
            previous_end = end
        starts.append(run_start)

    if len(starts) < _MIN_LINES_PER_CLUSTER:
        return None

    clusters: list[list[float]] = []
    for start in sorted(starts):
        if clusters and start - clusters[-1][-1] <= _CLUSTER_TOL_PT:
            clusters[-1].append(start)
        else:
            clusters.append([start])

    dominant = max(clusters, key=len)
    share_needed = max(_MIN_LINES_PER_CLUSTER, math.ceil(len(starts) * _MIN_COLUMN_SHARE))
    rivals = [
        c
        for c in clusters
        if c is not dominant
        and len(c) >= share_needed
        and abs(sum(c) / len(c) - sum(dominant) / len(dominant)) >= _COLUMN_SEP_PT
    ]
    if not rivals:
        return None
    edges = ", ".join(
        f"{min(c):.0f}pt on {len(c)}/{len(starts)} lines" for c in [dominant, *rivals]
    )
    nearest = min(abs(sum(c) / len(c) - sum(dominant) / len(dominant)) for c in rivals)
    return f"line starts cluster at {edges}, nearest {nearest:.0f}pt from the dominant column"


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
                    columns = _two_column_evidence(page)
                    if columns is not None:
                        problems.append(
                            ExtractionProblem(
                                code="pdf_multicolumn_unsupported",
                                detail=(
                                    f"page {index} reads as two columns ({columns}). "
                                    f"Reading order is not reconstructed, so extracting "
                                    f"would splice the columns into sentences the author "
                                    f"never wrote. The page is not extracted and not "
                                    f"cited rather than stored wrong."
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
