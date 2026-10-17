"""Delimited text: one addressable unit per cell.

``CsvLocator`` is a row and a *column header*, not a column index, so the
header is what the address is built from and what a reader quotes back. The
header row is row 1 and data begins at row 2, matching how anyone counts a
table out loud.

Three things a plausible implementation would get quietly wrong, and what
happens here instead.

**Duplicate headers.** Two columns called ``mean`` cannot be told apart by a
locator, so the second is a problem record rather than a cell that resolves
to whichever one happened to come first. Picking one is a guess, and a guess
that routes a citation to the wrong number is the failure C3 exists to
prevent.

**Ragged rows.** A row with more fields than the header has cells with no
name, and a row with fewer has header names with no value. Neither is padded
or dropped: the row is extracted as far as it goes and the rest is reported,
because a short row that silently ended early reads exactly like a short row.

**Delimiter sniffing is a guess, so it is disclosed.** Python's ``csv``
dialect cannot be detected without choosing, and a semicolon file read as
comma produces one column with an absurd header. The delimiter is chosen
deterministically -- the candidate producing the most columns wins, ties go
to comma -- and anything other than a plain comma is reported. Guessing
silently would produce a confident, wrong answer; guessing loudly produces a
correct answer a reader can check.
"""

from __future__ import annotations

import csv
import io
import sys
from types import ModuleType

from labcairn.material.text import decode_text
from labcairn.material.units import (
    ExtractedUnit,
    ExtractionProblem,
    ExtractionResult,
    register,
)
from labcairn.sources.locators import CsvLocator
from labcairn.sources.source import SourceKind

__all__ = ["CsvAdapter", "decode_text", "sniff_delimiter"]


def _fold(name: str) -> str:
    """Whitespace- and case-insensitive form, for the ambiguity report only."""
    return " ".join(name.split()).casefold()


#: Ordered so a tie goes to the first, and the first is the ordinary one.
_CANDIDATES = (",", ";", "\t", "|")


def sniff_delimiter(text: str) -> str:
    """The delimiter producing the most columns on the first populated line.

    Deterministic by construction: same text in, same delimiter out. A
    one-column file has no evidence either way and gets the ordinary comma,
    which is a no-op for a file that really has one column.
    """
    for line in text.splitlines():
        if line.strip():
            break
    else:
        return ","
    best = ","
    best_width = -1
    for candidate in _CANDIDATES:
        try:
            width = len(next(csv.reader([line], delimiter=candidate)))
        except (csv.Error, StopIteration):
            continue
        if width > best_width:
            best, best_width = candidate, width
    return best


@register
class CsvAdapter:
    """One unit per cell, addressed by row number and header name."""

    kind = SourceKind.CSV

    def extract(self, data: bytes) -> ExtractionResult:
        text, problems = decode_text(data)
        if text is None:
            return ExtractionResult(problems=problems)

        delimiter = sniff_delimiter(text)
        extra_problems: list[ExtractionProblem] = list(problems)
        # Always announced, not only when it is off comma. Announcing only
        # the non-default case means *every wrong guess at comma* is silent by
        # construction -- and a file with a stray semicolon in a header still
        # splits into plausible columns, which is the case the announcement
        # exists to catch.
        extra_problems.append(
            ExtractionProblem(
                code="delimiter_used",
                detail=(
                    f"read with {delimiter!r}, chosen because that is what splits the "
                    f"first populated line into the most columns. The header below is "
                    f"the check: if it looks wrong, this is where it went wrong."
                ),
                location="row 1",
            )
        )

        try:
            # newline='' so csv sees the file's own line terminators. Without
            # it, a file with classic-Mac CR endings raises "new-line character
            # seen in unquoted field" and an ordinary file gets reported as
            # unparseable. It also leaves a CR *inside* a quoted field alone,
            # so nothing needs normalising and nothing can be corrupted.
            records = list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter))
        except csv.Error as exc:
            extra_problems.append(
                ExtractionProblem(
                    code="csv_unparseable",
                    detail=f"the file is not readable as delimited text: {exc}",
                )
            )
            return ExtractionResult(problems=tuple(extra_problems))

        if not records:
            return ExtractionResult(
                problems=(
                    *extra_problems,
                    ExtractionProblem(
                        code="csv_empty",
                        detail="the file contains no rows at all",
                    ),
                )
            )

        header = records[0]
        # A header field with no name has no address, and building one --
        # "column_2", or an empty string -- would be inventing a name the file
        # does not contain. It is reported and its column is left unextracted.
        for position, name in enumerate(header):
            if not name.strip():
                extra_problems.append(
                    ExtractionProblem(
                        code="csv_blank_header",
                        detail=(
                            f"field {position} of the header is blank, so the cells under "
                            f"it have no address and cannot be cited. They are not "
                            f"extracted, because a made-up column name is a name the "
                            f"file does not contain."
                        ),
                        location=f"row 1 field {position}",
                    )
                )

        seen: dict[str, int] = {}
        for name in header:
            if name.strip():
                seen[name] = seen.get(name, 0) + 1
        duplicates = sorted(name for name, count in seen.items() if count > 1)

        # Names differing only in whitespace or case are *not* collisions:
        # NonEmptyText does not strip, so they remain distinct addresses and
        # each resolves to exactly one cell. Reported anyway, because a reader
        # cannot tell "mean" from " mean" in a spreadsheet either and one of
        # them is almost always a mistake in the file.
        folded: dict[str, list[str]] = {}
        for name in header:
            if name.strip():
                folded.setdefault(_fold(name), []).append(name)
        for group in sorted(folded.values()):
            if len(group) > 1:
                shown = ", ".join(repr(n) for n in group)
                extra_problems.append(
                    ExtractionProblem(
                        code="csv_ambiguous_header",
                        detail=(
                            f"the header names {shown} differ only in whitespace or case. "
                            f"They stay distinct addresses, so nothing is misrouted, but a "
                            f"reader cannot tell them apart either."
                        ),
                        location="row 1",
                    )
                )

        units: list[ExtractedUnit] = []
        for row_number, record in enumerate(records[1:], start=2):
            if len(record) != len(header):
                extra_problems.append(
                    ExtractionProblem(
                        code="csv_ragged_row",
                        detail=(
                            f"row {row_number} has {len(record)} field(s) and the "
                            f"header has {len(header)}. The fields present are "
                            f"extracted; the rest are not filled in, because an "
                            f"invented empty cell is indistinguishable from a "
                            f"measured one."
                        ),
                        location=f"row {row_number}",
                    )
                )
            for position, value in enumerate(record):
                if position >= len(header):
                    # Beyond the header, so there is no name to address it by.
                    extra_problems.append(
                        ExtractionProblem(
                            code="csv_cell_without_header",
                            detail=(
                                f"row {row_number} field {position} has no header to "
                                f"address it by, so it cannot be cited."
                            ),
                            location=f"row {row_number} field {position}",
                        )
                    )
                    continue
                name = header[position]
                if not name.strip() or name in duplicates:
                    # Recorded once per duplicate rather than per cell, so a
                    # wide file does not repeat the same sentence 500 times.
                    continue
                units.append(
                    ExtractedUnit(locator=CsvLocator(row=row_number, column=name), text=value)
                )

        for name in duplicates:
            extra_problems.append(
                ExtractionProblem(
                    code="csv_duplicate_header",
                    detail=(
                        f"the header {name!r} appears more than once, so a locator "
                        f"naming it is ambiguous. Those cells are not addressable "
                        f"until the file has distinct header names."
                    ),
                    location="row 1",
                )
            )

        return ExtractionResult(units=tuple(units), problems=tuple(extra_problems))

    def libraries(self) -> dict[str, str]:
        return {}

    def source_modules(self) -> tuple[ModuleType, ...]:
        # text.py is here because decode_text lives there and CSV extraction
        # runs through it. Hashing only this file left a real hole: editing
        # decode_text changed the CSV output while the version stayed put --
        # the key lying ADR-0009 forbids.
        return (sys.modules[__name__], sys.modules[decode_text.__module__])
