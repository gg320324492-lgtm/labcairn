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

__all__ = ["CsvAdapter", "sniff_delimiter"]

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
        if delimiter != ",":
            extra_problems.append(
                ExtractionProblem(
                    code="delimiter_inferred",
                    detail=(
                        f"read with {delimiter!r} rather than a comma, because that "
                        f"is what splits this file into the most columns. If that is "
                        f"wrong the header below will show it."
                    ),
                    location="row 1",
                )
            )

        try:
            records = list(csv.reader(io.StringIO(text), delimiter=delimiter))
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
        seen: dict[str, int] = {}
        for name in header:
            seen[name] = seen.get(name, 0) + 1
        duplicates = sorted(name for name, count in seen.items() if count > 1)

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
                if name in duplicates:
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

    def source(self) -> ModuleType:
        return __import__(__name__)
