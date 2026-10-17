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


def decode_text(data: bytes) -> tuple[str | None, tuple[ExtractionProblem, ...]]:
    """Decode ``data`` as text, or explain why not.

    Returns ``(text, ())`` on success and ``(None, problems)`` on failure.
    UTF-32 is checked before UTF-16 because the UTF-32-LE BOM starts with the
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
        return body.decode(encoding), ()
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
        return ExtractionResult(
            units=tuple(
                ExtractedUnit(locator=TextLocator(line=number), text=line)
                for number, line in enumerate(text.splitlines(), start=1)
            ),
            problems=problems,
        )

    def libraries(self) -> dict[str, str]:
        return {}

    def source(self) -> ModuleType:
        return __import__(__name__)


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

        units: list[ExtractedUnit] = []
        section: str | None = None
        for number, line in enumerate(text.splitlines(), start=1):
            section = _markdown_section(line, section)
            units.append(
                ExtractedUnit(locator=TextLocator(line=number, section=section), text=line)
            )
        return ExtractionResult(units=tuple(units), problems=problems)
