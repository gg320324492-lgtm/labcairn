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
that reaches the Markdown is escaped, and the set of **punctuation** that is
escaped is **one table in one module** — the CommonMark ASCII punctuation
that can open a span or a block, plus ``&``, ``<`` and ``>`` so the Markdown
is also safe where it is embedded in HTML. A table rather than a regular
expression, because the set is a set: a regular expression for "characters
that can open a span or a block" is a regular expression for a parser's
opinion, and the opinion changes with the parser.

**Whitespace is not punctuation, and it is not in the table.** It has its
own rule, and it is at the end of this list.

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

**No line of the file may open a code block.** CommonMark opens an
indented code block with four spaces or a tab at the start of a line,
and only where a blank line comes before it. The escape table covers the
punctuation that can open a span or a block, and **whitespace is not
punctuation** — so the whitespace is handled here as well, and it is
handled for **every line** of a text value rather than for the first one
alone.

That "every line" is the whole of it. A text value may carry a line
break, and a line break in the value is a line break in the file: the
writer's prefix — ``Figure 1. ``, ``- `` — protects the **first** line of
a value and no other. So a caption that carries a blank line and four
spaces puts four spaces at the start of a line of the file, with a blank
line before it, and a reader would be shown the caption as code. The
leading whitespace of every line is therefore written as a character
reference, which the reader decodes back to the same spaces: the text is
unchanged and the paragraph stays a paragraph, so the export's structure
is a function of the model rather than of where the text happens to
begin.
"""

from __future__ import annotations

import re
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

#: The number of spaces that opens an indented code block.
#:
#: CommonMark's threshold, and the smaller of the two thresholds the
#: writer has to satisfy: a claim is written as a bullet, and a bullet's
#: content is indented by two, so a claim needs six spaces where a
#: paragraph needs four. Four therefore covers every place the writer
#: puts a text value.
_CODE_BLOCK_INDENT: Final[int] = 4

#: The three ways CommonMark ends a line.
#:
#: LF, CR and CRLF are all line endings, and a text value that came out
#: of a PDF or a CSV may hold any of them. A line break is what puts the
#: rest of a text value at the start of a line of the file, so the writer
#: has to know where the lines are — and the reader's idea of a line is
#: the one here, not the writer's.
_LINE_BREAK: Final[re.Pattern[str]] = re.compile(r"\r\n|\r|\n")


def escape_markdown(text: str) -> str:
    """Escape one text value, so that it cannot become Markdown structure.

    Two things are done to the value, and both are about structure.

    **The punctuation is backslash-escaped**, by the one table in
    :data:`MARKDOWN_ESCAPE_TABLE`, except where the character is part of
    a number and therefore cannot be a list marker.

    **The leading whitespace of every line is written as a character
    reference**, where that whitespace would open an indented code block.
    This is not a small addition: a text value may carry a line break,
    and a line break in the value is a line break in the file. The
    writer's prefix — "Figure 1. ", "- " — protects the **first** line
    of a value and no other, so a caption that carries a blank line and
    four spaces puts four spaces at the start of a line of the file, and
    a reader would be shown the caption as code.

    :param text: the value, exactly as the model holds it.
    :returns: the value with every character in
        :data:`MARKDOWN_ESCAPE_TABLE` backslash-escaped, except where the
        character is part of a number, and with the leading whitespace of
        every line written as a character reference where that whitespace
        would open a code block.
    """
    return _protect_line_indents(_escape_punctuation(text))


def _escape_punctuation(text: str) -> str:
    """The value with the table's punctuation backslash-escaped.

    The numbers are the exception: a full stop between two digits is a
    decimal point and a sign immediately before a digit is a sign, and in
    both cases the character cannot be a list marker.
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


def _protect_line_indents(text: str) -> str:
    """Every line's leading indent, written so that it cannot open a block.

    CommonMark opens an **indented code block** with four spaces or a tab
    at the start of a line, and only where a blank line comes before it:
    an indented line that follows a paragraph is a continuation of that
    paragraph and opens nothing. So the danger is an indent at the start
    of a line that follows a blank one — and the writer's own prefix
    makes the threshold different in different places, which is why the
    rule is written for the **file's** lines rather than for the text
    value's.

    The rule is the same everywhere: a leading run of whitespace is
    written as a character reference when it is four spaces or more, or
    when it holds a tab. Four is the smaller of the two thresholds, so
    the rule holds in every place the writer puts a text value — the
    title, a heading, a caption, an interpretation, a claim's own words,
    a citation, and the report's own prose.

    A line of nothing but whitespace is left alone: it is a blank line,
    and a blank line is a blank line however it is written.
    """
    pieces: list[str] = []
    position = 0
    for match in _LINE_BREAK.finditer(text):
        pieces.append(_protect_one_indent(text[position : match.start()]))
        pieces.append(match.group(0))
        position = match.end()
    pieces.append(_protect_one_indent(text[position:]))
    return "".join(pieces)


def _protect_one_indent(line: str) -> str:
    """One line's leading indent, written as references where it is a risk.

    :param line: one line of the escaped text, without its line ending.
    :returns: the line, with its leading indent written as character
        references when that indent is four spaces or more, or holds a tab.
    """
    body = line.lstrip(" \t")
    if not body:
        return line
    indent = line[: len(line) - len(body)]
    if "\t" not in indent and len(indent) < _CODE_BLOCK_INDENT:
        return line
    reference = "".join(_WHITESPACE_REFERENCES[character] for character in indent)
    return reference + body


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

    **No kind is exempt from the whitespace rule.** The writer's prefix —
    "Figure 1. ", "- " — covers the **first** line of a value and no
    other, so a caption, a claim and a citation are no more protected
    against an indented code block than a narrative is: a value that
    carries a line break puts the rest of itself at the start of a line
    of the file. The protection is therefore in
    :func:`escape_markdown`, where it covers every line of every value.
    """
    lines = with_interpretation_marker(
        [escape_markdown(line) for line in item.lines], item.is_interpretation
    )
    if item.kind in (BlockKind.CLAIM, BlockKind.UNRESOLVED):
        return [f"- {line}" for line in lines]
    if item.kind in (BlockKind.FIGURE, BlockKind.TABLE):
        return [lines[0], "", lines[1]]
    return lines
