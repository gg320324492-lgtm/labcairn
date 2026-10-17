"""Markdown and plain text: one addressable unit per line.

The simplest adapter, and the one every other adapter is measured against.

Three decisions worth naming, because each is a place where a plausible
implementation would quietly do something else.

**Decode or disclose, never guess.** Bytes are decoded UTF-8 strictly, after
a BOM check. A failure produces a problem record and *no* units -- not a
replacement-character decode, which would put characters in the evidence that
no author wrote. Guessing cp1252 would be right perhaps half the time, and
being wrong half the time in a citation is worse than having no citation.

**Every line, including blank ones.** A blank line is a line. Dropping them
would be an omission that leaves no trace, and the numbering here is absolute
so nothing shifts either way. The cost is a row per blank line; the benefit
is that "line 12 is blank" is answerable.

**A multi-line quotation is a read-side operation.** Each unit addresses one
line, so ``TextLocator(line_end=...)`` is not stored. It is constructed by
whatever needs the range, from the rows for lines 5 through 7. Storing every
contiguous range as its own row would multiply the table by the square of
the line count for no gain.
"""

from __future__ import annotations

import codecs
import re
import sys
from types import ModuleType

from labcairn.material.units import (
    ExtractedUnit,
    ExtractionProblem,
    ExtractionResult,
    register,
)
from labcairn.sources.locators import TextLocator
from labcairn.sources.source import SourceKind

__all__ = ["MarkdownAdapter", "PlainTextAdapter", "decode_text"]

_BOMS: tuple[tuple[bytes, str], ...] = (
    (codecs.BOM_UTF8, "utf-8"),
    (codecs.BOM_UTF32_LE, "utf-32-le"),
    (codecs.BOM_UTF32_BE, "utf-32-be"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
)


#: Encodings tried when the bytes decode as UTF-8 but contain NULs, which is
#: what a BOM-less UTF-16 or UTF-32 file looks like after a UTF-8 decode.
_NUL_SUSPECTS: tuple[str, ...] = ("utf-32-le", "utf-32-be", "utf-16-le", "utf-16-be")

#: Line terminators this project recognises. Deliberately *not*
#: ``str.splitlines``, which also breaks on vertical tab, form feed, the
#: Unicode record separators, NEL, LINE SEPARATOR and PARAGRAPH SEPARATOR.
#: A form feed is a page separator in every format that has one, and turning
#: one into a phantom ``line=N`` invents an address no author wrote.
_LINE_RE = re.compile(r"\r\n|\r|\n")

#: Characters ``splitlines`` would have broken on. Their presence is reported
#: rather than acted on, because silently merging lines that a reader counts
#: differently is the other half of the same mistake.
_EXOTIC_BREAKS = "".join(chr(code) for code in (0x0B, 0x0C, 0x1C, 0x1D, 0x1E, 0x85, 0x2028, 0x2029))


def decode_text(data: bytes) -> tuple[str | None, tuple[ExtractionProblem, ...]]:
    """Decode ``data`` as text, or explain why not.

    Returns ``(text, ())`` on success and ``(None, problems)`` on failure.

    Three passes, because strict UTF-8 alone is not strict enough. UTF-16 and
    UTF-32 without a BOM are *valid UTF-8* -- every ASCII character followed
    by a NUL -- so a plain strict decode succeeds and returns text with NUL
    characters wedged between the letters. That is the one input class that
    defeats "decode strictly or disclose": the decode does not fail, and the
    output is a string no author wrote. So a NUL in a successful decode is
    itself the evidence, and the file is re-read as UTF-16 or UTF-32 -- with
    the missing BOM reported, because a file whose encoding had to be
    inferred is a file a reader should know about.

    UTF-32 is tried before UTF-16 because the UTF-32-LE BOM starts with the
    UTF-16-LE BOM, and checking in the other order decodes every UTF-32 file
    as UTF-16 with a NUL wedged in front.
    """
    encoding = "utf-8"
    body = data
    for bom, name in _BOMS:
        if data.startswith(bom):
            encoding, body = name, data[len(bom) :]
            break

    try:
        text = body.decode(encoding)
    except UnicodeDecodeError as exc:
        return None, (
            ExtractionProblem(
                code="text_not_decodable",
                detail=(
                    f"the bytes are not valid {encoding} "
                    f"(byte offset {exc.start}: {exc.reason}). The text is not "
                    f"guessed at a different encoding, because a guess that is "
                    f"wrong puts words in the record that the file does not contain."
                ),
            ),
        )

    if "\x00" not in text:
        return text, ()

    # Valid UTF-8 containing NULs: almost certainly UTF-16 or UTF-32 without
    # its BOM. Try, and say so either way.
    for candidate in _NUL_SUSPECTS:
        try:
            redecoded = body.decode(candidate)
        except UnicodeDecodeError:
            continue
        if "\x00" in redecoded:
            continue
        return redecoded, (
            ExtractionProblem(
                code="bom_missing_encoding_inferred",
                detail=(
                    f"the bytes decode as UTF-8 but contain NUL characters, which is "
                    f"what UTF-16 or UTF-32 without a byte-order mark looks like. Read "
                    f"as {candidate} instead. Confirm from the text below that this is "
                    f"the right reading."
                ),
            ),
        )

    return None, (
        ExtractionProblem(
            code="text_contains_nul",
            detail=(
                "the bytes decode as UTF-8 and contain NUL characters, but no UTF-16 "
                "or UTF-32 reading of them is clean either. The text is not extracted, "
                "because NUL-separated letters are not what the file says."
            ),
        ),
    )


def split_lines(text: str) -> tuple[list[str], tuple[ExtractionProblem, ...]]:
    """Split on CRLF, CR and LF only, and report the characters left inside a line.

    Returns ``(lines, problems)``.

    The trailing element is dropped when the text ends with a terminator,
    matching ``str.splitlines``: ``"a\\n"`` is one line, not two, and ``""`` is
    no lines at all rather than one empty one. Getting that wrong would make
    every file one line longer than a reader counts it, and would turn an
    empty file into a citation pointing at line 1 of nothing.
    """
    if not text:
        return [], ()
    lines = _LINE_RE.split(text)
    if lines and lines[-1] == "" and text[-1:] in ("\n", "\r"):
        lines.pop()

    found = sorted({char for char in text if char in _EXOTIC_BREAKS})
    problems: tuple[ExtractionProblem, ...] = ()
    if found:
        shown = ", ".join(f"U+{ord(c):04X}" for c in found)
        problems = (
            ExtractionProblem(
                code="exotic_line_break_present",
                detail=(
                    f"the text contains {shown}, which some tools treat as a line "
                    f"break and this extractor does not. They are kept inside the line "
                    f"they were found in, so a line number here may not match a line "
                    f"number in a viewer that splits on them."
                ),
            ),
        )
    return lines, problems


def _markdown_section(line: str, current: str | None) -> str | None:
    """The ATX heading this line opens, or the one it is already under.

    ``#`` through ``######``, optionally closed. Setext underlines are not
    recognised: they are ambiguous with a line of dashes, and a wrong section
    is worse than no section -- the line number still resolves.
    """
    stripped = line.lstrip(" ")
    if not stripped.startswith("#"):
        return current
    hashes = len(stripped) - len(stripped.lstrip("#"))
    if not 1 <= hashes <= 6:
        return current
    rest = stripped[hashes:]
    if rest and not rest.startswith((" ", "\t")):
        return current
    title = rest.strip().rstrip("#").strip()
    return title or None


@register
class PlainTextAdapter:
    """One unit per line, no sections. The reference behaviour."""

    kind = SourceKind.TEXT

    def extract(self, data: bytes) -> ExtractionResult:
        text, problems = decode_text(data)
        if text is None:
            return ExtractionResult(problems=problems)
        lines, split_problems = split_lines(text)
        return ExtractionResult(
            units=tuple(
                ExtractedUnit(locator=TextLocator(line=number), text=line)
                for number, line in enumerate(lines, start=1)
            ),
            problems=problems + split_problems,
        )

    def libraries(self) -> dict[str, str]:
        return {}

    def source_modules(self) -> tuple[ModuleType, ...]:
        return (sys.modules[__name__],)


@register
class MarkdownAdapter(PlainTextAdapter):
    """As above, with the enclosing ATX heading carried on each line.

    A line that *is* a heading keeps it as its own section, so
    ``TextLocator(line=4, section="Methods")`` on the heading line itself and
    on the body below it both say what a reader would expect.
    """

    kind = SourceKind.MARKDOWN

    def extract(self, data: bytes) -> ExtractionResult:
        text, problems = decode_text(data)
        if text is None:
            return ExtractionResult(problems=problems)
        lines, split_problems = split_lines(text)

        units: list[ExtractedUnit] = []
        section: str | None = None
        for number, line in enumerate(lines, start=1):
            section = _markdown_section(line, section)
            units.append(
                ExtractedUnit(locator=TextLocator(line=number, section=section), text=line)
            )
        return ExtractionResult(units=tuple(units), problems=problems + split_problems)
