"""The PDF form: the fixed form, and reportlab's writer over the model.

ADR-0013 chose reportlab for this form, and the reasons are the ones a
local-first tool cares about. It is BSD 3-clause, needs no system library
and no external binary, and it is the only PDF writer measured that did
not drag copyleft into the tree. WeasyPrint was refused because it cannot
run without GTK and Pango; xhtml2pdf because it brings svglib under the
LGPL; fpdf2 because of the licence line itself.

**The library is imported lazily** (ADR-0013's constraint 2), so a report
exported only as Markdown does not load reportlab.

**The bytes are not reproducible, and the exporter does not pretend
otherwise.** A PDF carries a creation date and a document id, and by
default reportlab fills both with the current time: two renders of one
model differ in two places. The owner decided on 2026-10-20 (the
breakdown's §1.4.3, Option A) that the report's reproducible forms are
Markdown and HTML, and that the PDF's bytes are recorded but not claimed
reproducible. So this exporter **does not set reportlab's ``invariant``**
switch, even though the switch exists and would make two renders
byte-identical: a PDF with a fixed creation date is lying about when it
was made, which is exactly the cost the owner declined to pay.

**No font is embedded.** The 14 core Type 1 faces are *referenced*, not
embedded, so the produced PDF carries no ``/FontFile`` and the reader's
viewer supplies the glyphs (ADR-0013's constraint 8, and the reason the
report's appearance in a PDF is not portable). A registered TrueType font
would be embedded, and would carry its licence into the artefact, so none
is registered.

**Nothing is fetched.** reportlab ships a URL reader that can pull a
figure over HTTP, and it is default-deny as shipped. A local-first tool
that fetches a figure from the network is not local-first, so no path is
ever handed to reportlab — and in any case the figure's bytes are not in
the model, so the export names the artefact rather than embedding it.

**The text is escaped for reportlab's markup, and a character reportlab
cannot draw is refused rather than mangled.** reportlab's ``Paragraph`` is
a small markup language, so ``&`` and ``<`` are escaped the way the
library's own parser expects. The faces are WinAnsi-encoded, and a
character outside that encoding is **refused by name**: reportlab
substitutes a placeholder silently, and a report that says one thing and
prints another is worse than a report that refuses to be printed.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, Final

from labcairn.reports.model import BlockKind, ReportDocument
from labcairn.reports.render.constants import (
    FIRST_PASS_NOTICE,
    REPRODUCIBILITY_NOTICE,
)
from labcairn.reports.render.resolve import (
    ReportItem,
    ReportRenderError,
    resolve,
    with_interpretation_marker,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Flowable

__all__ = ["PDF_TEXT_ENCODING", "PdfTextRefusedError", "render_pdf"]

#: The encoding the PDF form's faces use.
#:
#: The core Type 1 faces are WinAnsi-encoded, and WinAnsi is cp1252 for
#: every character the report can hold: the probe that established this
#: wrote every cp1252 character through reportlab and read every one of
#: them back unchanged, and wrote a character outside cp1252 and read back
#: a placeholder. So this is the boundary reportlab actually draws at, and
#: the check below is a check against the library's real behaviour rather
#: than an assumption about it.
PDF_TEXT_ENCODING: Final[str] = "cp1252"

#: The bullet the list items are drawn with.
#:
#: A character in the encoding above, and one the faces have.
_BULLET: Final[str] = "•"


class PdfTextRefusedError(ReportRenderError):
    """A character the PDF form cannot draw.

    A refusal, and not a substitution: reportlab draws a character outside
    the faces' encoding as a placeholder, silently, and a report whose
    PDF says one thing and prints another is a report that lies about its
    own content. The error names the character, so that the author can
    find it.
    """


def render_pdf(document: ReportDocument) -> bytes:
    """The report as a PDF.

    :param document: the report's model, frozen at one moment.
    :returns: the PDF's bytes. They are **not** byte-reproducible: a PDF
        carries a creation date and a document id, and this exporter does
        not pin them.
    """
    try:
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate
    except ImportError as exc:  # pragma: no cover - the dependency is declared
        raise RuntimeError(
            "reportlab is required to write a PDF; it is a declared dependency"
        ) from exc

    report = resolve(document)
    styles = getSampleStyleSheet()
    story: list[Flowable] = []

    story.append(_paragraph(styles, report.title, style="Title"))
    story.append(_paragraph(styles, FIRST_PASS_NOTICE))
    story.append(_paragraph(styles, REPRODUCIBILITY_NOTICE))
    story.append(_paragraph(styles, f"Snapshot: {report.as_of.isoformat()}"))
    if report.record_ids:
        records = ", ".join(report.record_ids)
        story.append(_paragraph(styles, f"Records: {records}"))

    for section in report.sections:
        story.append(_paragraph(styles, section.heading, style="Heading1"))
        for item in section.items:
            story.extend(_draw_item(styles, item))

    if report.unplaced_figures or report.unplaced_tables:
        story.append(_paragraph(styles, "Artefacts not placed in a section", style="Heading1"))
        unplaced: tuple[ReportItem, ...] = (*report.unplaced_figures, *report.unplaced_tables)
        for item in unplaced:
            story.extend(_draw_item(styles, item))

    story.append(_paragraph(styles, "Provenance", style="Heading1"))
    for footnote in report.footnotes:
        for line in footnote.lines:
            story.append(_paragraph(styles, line, bullet=True))

    buffer = io.BytesIO()
    document_template = SimpleDocTemplate(
        buffer,
        title=report.title,
        author="LabCairn",
        subject=FIRST_PASS_NOTICE,
    )
    document_template.build(story)
    return buffer.getvalue()


def _draw_item(styles: Mapping[str, ParagraphStyle], item: ReportItem) -> list[Flowable]:
    """The PDF paragraphs for one resolved block.

    The wording is the item's own, so the PDF says what the Markdown and
    the HTML and the DOCX say. A finding and a disclosure are drawn as
    bullets, because they are entries in a list.
    """
    lines = with_interpretation_marker(
        [_escape(line) for line in item.lines], item.is_interpretation
    )
    bullet = item.kind in (BlockKind.CLAIM, BlockKind.UNRESOLVED)
    return [_paragraph(styles, line, bullet=bullet) for line in lines]


def _paragraph(
    styles: Mapping[str, ParagraphStyle],
    text: str,
    *,
    style: str = "BodyText",
    bullet: bool = False,
) -> Flowable:
    """One paragraph, with the text escaped for reportlab's markup."""
    from reportlab.platypus import Paragraph

    if bullet:
        return Paragraph(_escape(text), styles[style], bulletText=_BULLET)
    return Paragraph(_escape(text), styles[style])


def _escape(text: str) -> str:
    """Escape one text value for reportlab's paragraph markup.

    reportlab's ``Paragraph`` is a small markup language: ``<`` opens a
    tag and ``&`` opens an entity. The report renders retrieved text, and
    retrieved text is data and never instructions, so both are escaped —
    and the ampersand first, so that the escapes this function writes are
    not themselves escaped.

    :raises PdfTextRefusedError: when the text holds a character the
        faces cannot draw.
    """
    for character in text:
        try:
            character.encode(PDF_TEXT_ENCODING)
        except UnicodeEncodeError as exc:
            raise PdfTextRefusedError(
                f"the PDF form cannot draw the character {character!r} "
                f"(U+{ord(character):04X}), which is outside the "
                f"{PDF_TEXT_ENCODING} encoding the PDF's faces use. The report "
                "is refused rather than printed with a placeholder in place of "
                "the character."
            ) from exc
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
