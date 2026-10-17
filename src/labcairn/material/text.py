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
import unicodedata
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
#: what a BOM-less UTF-16 or UTF-32 file looks like after a UTF-8 decode,
#: each with the minimum share of NUL bytes that reading implies.
#:
#: The threshold is the whole safety property, and it exists because a naive
#: "try the other encodings" fallback fabricates. Measured: a BOM-less UTF-16
#: run is ~50% NUL and UTF-32 is ~75%, while a genuine UTF-8 file carrying
#: one embedded NUL is under 12%. Below the threshold the fallback does not
#: run at all and the file is refused, which is what round 1 did safely and
#: what an earlier attempt here stopped doing -- it turned
#: ``b"alpha\\x00bravo"`` into CJK, and only because the file had an even
#: byte count.
_NUL_SUSPECTS: tuple[tuple[str, float], ...] = (
    ("utf-32-le", 0.70),
    ("utf-32-be", 0.70),
    ("utf-16-le", 0.40),
    ("utf-16-be", 0.40),
)

#: Control characters that never occur in a real text file, and so are
#: evidence of a misreading in the same way a NUL is. Excludes tab, newline,
#: vertical tab, form feed and carriage return, which do occur.
_REFUSED_CONTROLS = frozenset(list(range(0x09)) + list(range(0x0E, 0x20)) + [0x7F])

#: Above this fraction of non-ASCII characters a decoding is treated as a
#: misreading rather than as text. Material this project ingests is
#: overwhelmingly ASCII and Latin; ``b"H\\x00e\\x00..."`` read as UTF-16-LE
#: yields CJK, and that is the tell that the other byte order was meant.
_MAX_NON_LATIN = 0.20

#: Line terminators this project recognises. Deliberately *not*
#: ``str.splitlines``, which also breaks on vertical tab, form feed, the
#: Unicode record separators, NEL, LINE SEPARATOR and PARAGRAPH SEPARATOR.
#: A form feed is a page separator in every format that has one, and turning
#: one into a phantom ``line=N`` invents an address no author wrote.
_LINE_RE = re.compile(r"\r\n|\r|\n")

#: Characters ``splitlines`` would have broken on, and which are still kept
#: inside a line rather than treated as corruption. Vertical tab, form feed
#: and NEL occur in real files; the record separators (U+001C-U+001E) and the
#: unit separator do not, and are in :data:`_REFUSED_CONTROLS` instead -- a
#: character cannot both be evidence of a misreading and a line break we
#: choose to keep.
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

    # Control characters are the evidence, not NUL specifically. A NUL is only
    # a *proxy* for "this is UTF-16", and the proxy holds only for UTF-16 that
    # contains ASCII -- because ASCII is what produces the NULs. A UTF-16 file
    # with no ASCII at all has none, decodes cleanly as UTF-8, and would
    # otherwise be certified readable with nothing disclosed:
    #
    #     U+0420 encoded as utf-16-le   ->  " \x04"
    #
    # -- one letter in, two characters out, one of them EOT.
    #
    # Tab, newline, vertical tab, form feed and carriage return are excluded
    # because they occur in real text files; form feed especially, since it is
    # a page separator in every format that has one and is already reported
    # by :func:`split_lines` rather than treated as corruption.
    forbidden = sorted({char for char in text if ord(char) in _REFUSED_CONTROLS})
    if not forbidden:
        return text, ()

    # Valid UTF-8 containing control characters. Two gates, both load-bearing:
    # density decides *whether* to read the file as UTF-16/32 at all, and a
    # plausibility check decides *which* byte order. Density alone cannot
    # separate little-endian from big-endian -- both are 50% NUL -- and
    # picking the first that decodes cleanly turned "Hello".encode(
    # "utf-16-be") into CJK while reporting a successful inference.
    density = text.count("\x00") / len(text)
    candidates: list[tuple[str, str]] = []
    for encoding, threshold in _NUL_SUSPECTS:
        if density < threshold:
            continue
        try:
            redecoded = body.decode(encoding)
        except UnicodeDecodeError:
            continue
        if "\x00" in redecoded:
            continue
        candidates.append((encoding, redecoded))

    if not candidates:
        return None, (
            ExtractionProblem(
                code="text_contains_nul" if "\x00" in text else "text_contains_control",
                detail=(
                    "the bytes decode as UTF-8 but contain "
                    + (
                        f"NUL characters at {density:.0%}"
                        if "\x00" in text
                        else "control characters "
                        + ", ".join(f"U+{ord(c):04X}" for c in forbidden[:6])
                    )
                    + ", which is not what a text file contains, and no UTF-16 or "
                    f"UTF-32 reading of them (density {density:.0%}) is plausible "
                    f"either. Nothing is extracted, because guessing here puts "
                    f"characters in the record that the file does not contain."
                ),
            ),
        )

    plausible = [c for c in candidates if _is_plausible_text(c[1])]
    if len(plausible) != 1:
        # Zero plausible readings, or several -- an ambiguous file is
        # refused rather than guessed, and the refusal says what was tried.
        tried = ", ".join(sorted({encoding for encoding, _ in candidates}))
        return None, (
            ExtractionProblem(
                code="text_encoding_ambiguous",
                detail=(
                    f"the bytes decode as UTF-8 with NUL characters at {density:.0%}, "
                    f"which suggests UTF-16 or UTF-32 without a byte-order mark, but "
                    f"the readings tried ({tried or 'none'}) do not settle on one "
                    f"plausible text. Nothing is extracted, because picking one would "
                    f"be a guess about every character."
                ),
            ),
        )

    encoding, chosen = plausible[0]
    return chosen, (
        ExtractionProblem(
            code="bom_missing_encoding_inferred",
            detail=(
                f"the bytes decode as UTF-8 but contain NUL characters at {density:.0%}, "
                f"which is what UTF-16 or UTF-32 without a byte-order mark looks like. "
                f"Read as {encoding} instead. Confirm from the text below that this is "
                f"the right reading."
            ),
        ),
    )


def _is_plausible_text(text: str) -> bool:
    """Whether a decoding looks like the material this project ingests.

    Not a language test and not a claim about what researchers write. It is
    a single check that a misreading usually fails: bytes read with the
    wrong endianness land in CJK, Hangul or private-use ranges, while text
    that came out right is overwhelmingly ASCII and Latin. When several
    readings pass, or none do, the caller refuses rather than choosing.
    """
    visible = [char for char in text if not char.isspace()]
    if not visible:
        return False
    if any(unicodedata.category(char) in {"Cc", "Cf", "Co", "Cs", "Cn"} for char in visible):
        return False
    non_latin = sum(1 for char in visible if ord(char) > 0x24F)
    return (non_latin / len(visible)) <= _MAX_NON_LATIN


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


def _fence_marker(line: str) -> str | None:
    """The fence run this line opens or closes, or None.

    CommonMark allows 0-3 spaces of indent before a fence; 4 or more makes
    it indented code instead, which is also not a heading.

    The **whole run** is returned, not just its first three characters: a
    three-backtick line does not close a four-backtick fence, and treating
    them as interchangeable let a heading inside a nested block become a
    section again.
    """
    stripped = line.rstrip()
    indent = len(stripped) - len(stripped.lstrip(" "))
    if indent > 3:
        return None
    rest = stripped.lstrip(" ")
    for marker in ("```", "~~~"):
        run = len(rest) - len(rest.lstrip(marker[0]))
        if (
            run >= 3
            and rest[run - 1 if run else 0] in ("`", "~")
            and rest.startswith(marker[0] * run)
        ):
            return marker[0] * run
    return None


def _markdown_section(line: str, current: str | None) -> str | None:
    """The ATX heading this line opens, or the one it is already under.

    ``#`` through ``######``, optionally closed, with at most three spaces
    of indent -- four or more is an indented code block in CommonMark, and
    ``    # indented code`` is a code sample, not a heading.

    Setext underlines are not recognised: they are ambiguous with a line of
    dashes, and a wrong section is worse than no section -- the line number
    still resolves.
    """
    stripped = line.lstrip(" ")
    indent = len(line) - len(stripped)
    if indent > 3:
        return current
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
        fence: str | None = None
        for number, line in enumerate(lines, start=1):
            marker = _fence_marker(line)
            if marker is not None:
                # A fenced block holds code, not structure. Without this, a
                # Python comment inside ```python became the section for
                # every line after it -- including the real prose -- and the
                # section is part of the address, so those citations would
                # resolve to nothing.
                if fence is not None and marker[0] == fence[0] and len(marker) >= len(fence):
                    fence = None
                elif fence is None:
                    fence = marker
                units.append(
                    ExtractedUnit(locator=TextLocator(line=number, section=section), text=line)
                )
                continue
            if fence is None:
                section = _markdown_section(line, section)
            units.append(
                ExtractedUnit(locator=TextLocator(line=number, section=section), text=line)
            )
        return ExtractionResult(units=tuple(units), problems=problems + split_problems)
