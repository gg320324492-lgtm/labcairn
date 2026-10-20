"""The HTML form: the preview form, and one self-contained file.

ADR-0013 measured the two template engines it rejected and the reason it
rejected them is the reason this module exists. Jinja2's and Mako's
``autoescape`` are **off by default**: both template engines tested emitted
``CPU <script>alert("xss")</script> & "quotes" 'apos'`` **unescaped**. The
safety in a template engine is a flag at each interpolation site, and a
report whose author forgets one site ships an injection, and the failure is
silent. ``html.escape`` is called here at the point where a text value
enters the document, and a writer that emits structure and text from
different branches cannot forget it, because the text branch *is* the
escaping branch.

**The escaping is total and has no exceptions.** Every text value that
reaches the file goes through :func:`html.escape` — the report renders
retrieved text, evidence claims and group names, all of it imported, and
imported text is data and never instructions. There is no path in this
module that writes a text value unescaped, and the test that proves it uses
a caption containing ``<script>``, because a test whose subject is escaping
and whose subject is pure ASCII proves nothing about escaping.

**The file is self-contained.** One file, with no external asset, no script
and no network reference. A local-first tool whose preview fetches something
is not a local-first preview, and an own writer makes that a property of the
code rather than a configuration somebody has to remember. The style sheet
is inline and names no font file: the reader's own fonts are used, so the
preview looks the same on a machine with no network and no fonts installed
beside the ones the operating system has.

**The bytes are reproducible.** The writer is a pure function of the model:
it reads the document and writes text, and nothing in it depends on the
clock, the environment, or the order the document was built in.

The module is named after the form it writes, so ``from html import escape``
below is the standard library's module: Python 3 imports absolutely, and the
standard library precedes site-packages on the path.
"""

from __future__ import annotations

from html import escape

from labcairn.reports.model import BlockKind, ReportDocument
from labcairn.reports.render.constants import (
    FIRST_PASS_NOTICE,
    REPRODUCIBILITY_NOTICE,
)
from labcairn.reports.render.resolve import (
    ReportItem,
    resolve,
    with_interpretation_marker,
)

__all__ = ["render_html"]

#: The inline style sheet.
#:
#: Inline, and naming no file: the report is one file that a reader can
#: open offline, and a stylesheet reference would be exactly the external
#: asset the form is not allowed to have. No font is named either, so the
#: preview takes the reader's own fonts and the file stays portable.
_STYLE = """\
body {
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  line-height: 1.5;
  max-width: 46rem;
  margin: 2rem auto;
  padding: 0 1rem;
}
h1 { font-size: 1.6rem; }
h2 { font-size: 1.25rem; margin-top: 2.5rem; }
h3 { font-size: 1.05rem; margin-top: 1.5rem; }
.notice {
  background: #fff8e1;
  border-left: 4px solid #d9a400;
  padding: 0.6rem 0.9rem;
  margin: 0.6rem 0;
}
.snapshot { color: #555; font-size: 0.9rem; }
.interpretation { border-left: 3px solid #d9a400; padding-left: 0.8rem; }
.artefact { color: #555; font-size: 0.85rem; }
code { font-family: ui-monospace, "Cascadia Mono", Consolas, monospace; }
figcaption { font-style: italic; }
"""


def render_html(document: ReportDocument) -> bytes:
    """The report as one self-contained HTML file.

    :param document: the report's model, frozen at one moment.
    :returns: the HTML, UTF-8, and a pure function of the model: the same
        document gives the same bytes, every time.
    """
    report = resolve(document)
    lines: list[str] = []

    lines.append("<!DOCTYPE html>")
    lines.append('<html lang="en">')
    lines.append("<head>")
    lines.append('<meta charset="utf-8">')
    lines.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    lines.append(f"<title>{escape(report.title)}</title>")
    lines.append("<style>")
    lines.append(_STYLE.rstrip("\n"))
    lines.append("</style>")
    lines.append("</head>")
    lines.append("<body>")
    lines.append(f"<h1>{escape(report.title)}</h1>")
    lines.append(f'<p class="notice">{escape(FIRST_PASS_NOTICE)}</p>')
    lines.append(f'<p class="notice">{escape(REPRODUCIBILITY_NOTICE)}</p>')
    lines.append(f'<p class="snapshot">Snapshot: {escape(report.as_of.isoformat())}</p>')
    if report.record_ids:
        records = ", ".join(escape(record_id) for record_id in report.record_ids)
        lines.append(f'<p class="snapshot">Records: {records}</p>')
    lines.append("")

    for section in report.sections:
        lines.append("<section>")
        lines.append(f"<h2>{escape(section.heading)}</h2>")
        for item in section.items:
            lines.extend(_draw_item(item))
        lines.append("</section>")

    if report.unplaced_figures or report.unplaced_tables:
        lines.append("<section>")
        lines.append("<h2>Artefacts not placed in a section</h2>")
        unplaced: tuple[ReportItem, ...] = (*report.unplaced_figures, *report.unplaced_tables)
        for item in unplaced:
            lines.extend(_draw_item(item))
        lines.append("</section>")

    lines.append("<section>")
    lines.append("<h2>Provenance</h2>")
    lines.append("<ul>")
    for footnote in report.footnotes:
        for line in footnote.lines:
            lines.append(f"<li>{escape(line)}</li>")
    lines.append("</ul>")
    lines.append("</section>")
    lines.append("</body>")
    lines.append("</html>")

    return ("\n".join(lines).rstrip("\n") + "\n").encode("utf-8")


def _draw_item(item: ReportItem) -> list[str]:
    """The HTML for one resolved block.

    Every text value is escaped on the way in, and the interpretation
    marker is appended after the escaping, so that it appears in the file
    exactly as the product spells it. The shape is decided on the item's
    *kind*, which is the model's own spelling of what the block is.
    """
    lines = with_interpretation_marker(
        [escape(line) for line in item.lines], item.is_interpretation
    )
    if item.kind in (BlockKind.FIGURE, BlockKind.TABLE):
        return [
            "<figure>",
            f"<figcaption>{lines[0]}</figcaption>",
            f'<p class="artefact">{lines[1]}</p>',
            "</figure>",
        ]
    return [f'<p class="{item.kind.value}">{line}</p>' for line in lines]
