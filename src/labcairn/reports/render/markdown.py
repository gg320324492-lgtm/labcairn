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

**A paragraph that starts with four spaces is not allowed to become a
code block.** CommonMark opens an indented code block with four spaces
or a tab at the start of a line, and the narrative and the
interpretation are written at the start of a line. Their leading indent
is written as a character reference, which the reader decodes back to
the same spaces: the text is unchanged and the paragraph stays a
paragraph, so the export's structure is a function of the model rather
than of where the text happens to begin.
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

#: The character reference each whitespace character is written as, when
#: it would otherwise open an indented code block.
#:
#: A character reference is the one way to write a space at the start of a
#: line without starting a code block: the block structure is decided on
#: the raw line, and the reference is decoded afterwards, so the reader
#: sees the same space and the paragraph stays a paragraph.
_WHITESPACE_REFERENCES: Final[dict[str, str]] = {" ": "&#32;", "\t": "&#9;"}


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


def _protect_leading_indent(text: str) -> str:
    """A paragraph that would open a code block, written so that it does not.

    CommonMark opens an **indented code block** with four spaces or a tab
    at the start of a line, so a paragraph whose text begins that way is
    drawn as code rather than as prose. The narrative and the
    interpretation are the report's own prose and are written at the
    start of a line, so they are the two blocks where this can happen;
    a caption, a claim and a citation are all prefixed by the writer and
    cannot open one.

    The leading whitespace is written as a character reference instead.
    The text the reader sees is unchanged — the same spaces, in the same
    place — and the paragraph stays a paragraph, so the export's
    structure is a function of the model and not of where the text
    happens to start.

    :param text: the escaped text of one paragraph.
    :returns: the text, with a leading indent written as references when
        that indent would open a code block.
    """
    indent = text[: len(text) - len(text.lstrip(" \t"))]
    if not indent:
        return text
    if "\t" not in indent and len(indent) < 4:
        return text
    reference = "".join(_WHITESPACE_REFERENCES[character] for character in indent)
    return reference + text[len(indent) :]


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

    A narrative and an interpretation are written at the start of a line,
    so they are the two kinds whose leading indent could open a code
    block, and their leading indent is protected. A caption, a claim and
    a citation are prefixed by the writer and cannot open one.
    """
    lines = with_interpretation_marker(
        [escape_markdown(line) for line in item.lines], item.is_interpretation
    )
    if item.kind in (BlockKind.CLAIM, BlockKind.UNRESOLVED):
        return [f"- {line}" for line in lines]
    if item.kind in (BlockKind.FIGURE, BlockKind.TABLE):
        return [lines[0], "", lines[1]]
    if item.kind in (BlockKind.NARRATIVE, BlockKind.INTERPRETATION):
        return [_protect_leading_indent(line) for line in lines]
    return lines
