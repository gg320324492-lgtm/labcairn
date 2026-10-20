"""The Markdown form: the reference form, and LabCairn's own writer.

ADR-0013 decided this one carefully, and the reasoning is worth repeating
because it decided *against* the obvious choice. The report needs
model → Markdown, and no mainstream library does that: ``markdown-it-py``
and ``mistune`` are parsers, and a parser cannot be turned around by
wishing. So the writer is here, in the tree, and it costs nothing to
install.

**The HTML is not made from this Markdown.** Both forms walk the model
separately. Producing the HTML by parsing the Markdown would need a
parser — the wrong direction ADR-0013 rejected — and would make the HTML a
rendering of a rendering, with two escaping layers instead of one.

**The escaping is a table, and the table is here.** The report renders
retrieved text, and retrieved text is data and never instructions: a caption
that says ``# Not a heading`` must not become a heading, and a caption that
says ``[click](javascript:...)`` must not become a link. So every text value
that reaches the Markdown is escaped, and the set of characters that are
escaped is **one table in one module** — the CommonMark ASCII punctuation
that can open a span or a block, plus ``&``, ``<`` and ``>`` so the Markdown
is also safe where it is embedded in HTML. A table rather than a regular
expression, because the set is a set: a regular expression for "characters
that can open a span or a block" is a regular expression for a parser's
opinion, and the opinion changes with the parser.

**Two characters are not escaped in one situation, and the situation is
the number.** A full stop between two digits is a decimal point, and a sign
immediately before a digit is a sign; in both cases the character cannot be
a list marker, because a list marker is a digit run, a marker and a space.
Escaping them would write ``4\\.253`` where the ledger says ``4.253``, and a
report that says 4.25 where the ledger says 4.253 is a different claim about
the same quantity. The numbers are the one thing the acceptance clause
compares, so they are drawn as the ledger spells them.

**The result is byte-reproducible.** The writer is a pure function of the
model: it reads the document, it writes text, and nothing in it depends on
the clock, the environment or the order the document was built in. Two
renders of one model are the same bytes, and the same is true of the HTML.

**The product's own words are written literally.** The first-pass notice
and the interpretation marker are constants, not text that came from a
source, so they are not escaped: they are the product's sentences, and
there is one spelling of each in the tree. Everything the model holds is
escaped, including the report's own title and headings.
"""

from __future__ import annotations

from typing import Final

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

__all__ = ["MARKDOWN_ESCAPE_TABLE", "escape_markdown", "render_markdown"]

#: The characters the Markdown writer escapes, and what they become.
#:
#: One table, and the reason for every entry is the same: each of them can
#: open a span or a block in CommonMark, and text that came from a source
#: is not allowed to open anything. The groups are:
#:
#: * the escape character itself — a literal ``\`` in the text would
#:   otherwise be read as the start of an escape sequence, and the reader
#:   would see a character the text never had;
#: * the span and link characters — `` ` ``, ``*``, ``_``, ``[``, ``]``,
#:   ``!``, ``(``, ``)`` and ``~`` — so that no emphasis, code span, link,
#:   image, link destination or strikethrough can be opened or closed by
#:   the text;
#: * the raw-HTML and entity characters — ``<``, ``>`` and ``&`` — so that
#:   the Markdown is also safe where a reader embeds it in HTML;
#: * the block characters — ``#``, ``>``, ``+``, ``-``, ``=``, ``.`` and
#:   ``)`` — so that no heading, quote, bullet, ordered list, thematic
#:   break or setext underline can be opened by the text. The last two are
#:   here because an ordered list is opened by a digit run, a marker and
#:   a space, and the marker is punctuation; ``=`` is here because it
#:   underlines a heading.
MARKDOWN_ESCAPE_TABLE: Final[dict[str, str]] = {
    "\\": "\\\\",
    "`": "\\`",
    "*": "\\*",
    "_": "\\_",
    "[": "\\[",
    "]": "\\]",
    "!": "\\!",
    "(": "\\(",
    ")": "\\)",
    "<": "\\<",
    ">": "\\>",
    "&": "\\&",
    "#": "\\#",
    "+": "\\+",
    "-": "\\-",
    "=": "\\=",
    ".": "\\.",
    "~": "\\~",
}

#: The characters that count as a digit for the number exceptions.
#:
#: ASCII only, deliberately: the rule the exceptions serve is about a
#: decimal point in a number the ledger holds, and the ledger's numbers are
#: ASCII. A character that is a digit in some other script is not a digit
#: here, so the rule stays decidable by looking at the text.
_ASCII_DIGITS: Final[str] = "0123456789"


def escape_markdown(text: str) -> str:
    """Escape one text value, so that it cannot become Markdown structure.

    :param text: the value, exactly as the model holds it.
    :returns: the value with every character in
        :data:`MARKDOWN_ESCAPE_TABLE` backslash-escaped, except where the
        character is part of a number and therefore cannot be a list marker.
    """
    out: list[str] = []
    length = len(text)
    for index, character in enumerate(text):
        previous = text[index - 1] if index else ""
        following = text[index + 1] if index + 1 < length else ""
        if character == "." and _is_digit(previous) and _is_digit(following):
            out.append(character)
            continue
        if character in ("-", "+") and _is_digit(following):
            out.append(character)
            continue
        out.append(MARKDOWN_ESCAPE_TABLE.get(character, character))
    return "".join(out)


def _is_digit(character: str) -> bool:
    """Whether *character* is one of the ASCII digits.

    The empty string is not a digit, and the test says so: ``"" in
    "0123456789"`` is true, and a rule that treated the character before
    or after the first character of a string as a digit would leave that
    character unescaped.
    """
    return len(character) == 1 and character in _ASCII_DIGITS


def render_markdown(document: ReportDocument) -> bytes:
    """The report as Markdown.

    :param document: the report's model, frozen at one moment.
    :returns: the Markdown, UTF-8, and a pure function of the model: the
        same document gives the same bytes, every time.
    """
    report = resolve(document)
    lines: list[str] = []

    lines.append(f"# {escape_markdown(report.title)}")
    lines.append("")
    lines.append(f"> {FIRST_PASS_NOTICE}")
    lines.append(">")
    lines.append(f"> {REPRODUCIBILITY_NOTICE}")
    lines.append("")
    lines.append(f"Snapshot: {report.as_of.isoformat()}")
    lines.append("")
    if report.record_ids:
        lines.append(f"Records: {', '.join(escape_markdown(r) for r in report.record_ids)}")
        lines.append("")

    for section in report.sections:
        lines.append(f"## {escape_markdown(section.heading)}")
        lines.append("")
        for item in section.items:
            lines.extend(_draw_item(item))
            lines.append("")

    if report.unplaced_figures or report.unplaced_tables:
        lines.append("## Artefacts not placed in a section")
        lines.append("")
        unplaced: tuple[ReportItem, ...] = (*report.unplaced_figures, *report.unplaced_tables)
        for item in unplaced:
            lines.extend(_draw_item(item))
            lines.append("")

    lines.append("## Provenance")
    lines.append("")
    for footnote in report.footnotes:
        for line in footnote.lines:
            lines.append(f"- {escape_markdown(line)}")
    lines.append("")

    return ("\n".join(lines).rstrip("\n") + "\n").encode("utf-8")


def _draw_item(item: ReportItem) -> list[str]:
    """The Markdown for one resolved block.

    The wording comes from the item and is escaped here; the shape — a
    bullet, a paragraph, or a block with its artefact under it — is the
    renderer's business, and it is decided on the item's *kind*, which is
    the model's own spelling of what the block is.

    The interpretation marker is the one piece of the product's own words
    that appears inside a line, and it is appended **after** the escaping,
    so that it appears in the file exactly as the product spells it.
    """
    lines = with_interpretation_marker(
        [escape_markdown(line) for line in item.lines], item.is_interpretation
    )
    if item.kind in (BlockKind.CLAIM, BlockKind.UNRESOLVED):
        return [f"- {line}" for line in lines]
    if item.kind in (BlockKind.FIGURE, BlockKind.TABLE):
        return [lines[0], "", lines[1]]
    return lines
