"""``labcairn.reports.render`` — the four forms a report can be read in.

LC-P1-11's work order names four: *"Markdown/HTML preview + basic editable
DOCX and PDF"*. This package is them, and it is them **over one model**:
:mod:`labcairn.reports.model`'s ``ReportDocument`` is the report's content
as data, and the four renderers here are four drawings of it. The model's
own rule — *a renderer draws; it does not decide* — is the rule this
package is written to: a number, a caption and a label all come from the
model, and a renderer that had to compute one would be a renderer that
could disagree with the ledger.

**Two of the four are byte-reproducible and two are not, and that is the
design rather than a defect.** The owner decided on 2026-10-20 (the
breakdown's §1.4.3, Option A, and ADR-0013) that the report's reproducible
forms are Markdown and HTML, and that the DOCX and the PDF are exports
whose bytes are recorded but not claimed reproducible: a DOCX is a ZIP
whose entries carry timestamps, and a PDF carries a creation date. The
renderers here do not pretend otherwise, and :data:`REPRODUCIBILITY_NOTICE`
says so on the face of every export.

**The two writable forms are LabCairn's own code, and the standard
library's.** ADR-0013 measured the alternatives: a Markdown *parser* is the
wrong direction — the report needs model → Markdown — and both template
engines it measured escape **nothing by default**, which makes the safety
a flag somebody has to remember. ``html.escape`` puts it in one place, and
the report renders retrieved text, which is data and never instructions.

**The two container forms are libraries, imported lazily.** ``python-docx``
and ``reportlab`` are the only two runtime dependencies LC-P1-11 adds, and
neither is loaded until a report is exported in that form: a report
exported only as Markdown must not pay for lxml.
"""

from __future__ import annotations

from labcairn.reports.render.constants import (
    FIRST_PASS_NOTICE,
    INTERPRETATION_MARKER,
    REPRODUCIBILITY_NOTICE,
)
from labcairn.reports.render.docx import render_docx
from labcairn.reports.render.html import render_html
from labcairn.reports.render.markdown import MARKDOWN_ESCAPE_TABLE, escape_markdown, render_markdown
from labcairn.reports.render.pdf import PdfTextRefusedError, render_pdf
from labcairn.reports.render.resolve import (
    ReportItem,
    ReportRenderError,
    ResolvedReport,
    resolve,
)

__all__ = [
    "FIRST_PASS_NOTICE",
    "INTERPRETATION_MARKER",
    "MARKDOWN_ESCAPE_TABLE",
    "REPRODUCIBILITY_NOTICE",
    "PdfTextRefusedError",
    "ReportItem",
    "ReportRenderError",
    "ResolvedReport",
    "escape_markdown",
    "render_docx",
    "render_html",
    "render_markdown",
    "render_pdf",
    "resolve",
]
