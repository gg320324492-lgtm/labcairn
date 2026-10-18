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

from labcairn.material.text import decode_text, split_lines
from labcairn.material.units import (
    ExtractedUnit,
    ExtractionProblem,
    ExtractionResult,
    register,
)
from labcairn.sources.locators import CsvLocator
from labcairn.sources.source import SourceKind

__all__ = [
    "CsvAdapter",
    "decode_text",
    "delimiter_evidence",
    "sniff_delimiter",
]


def _fold(name: str) -> str:
    """Whitespace- and case-insensitive form, for the ambiguity report only."""
    return " ".join(name.split()).casefold()


#: Ordered so a tie goes to the first, and the first is the ordinary one.
_CANDIDATES = (",", ";", "\t", "|")


def _first_record_width(text: str, delimiter: str) -> int:
    """Columns in the first record, read the way ``csv.reader`` will read it.

    Measuring on the first *line* instead is what made the evidence
    unfalsifiable. For ``b'"a\nb";c\n1;2\n'`` the first line is the
    fragment ``"a`` -- an unterminated quote -- so every candidate scores 1,
    the comma default wins, and the header shown is ``['a\nb;c']``: the
    counts and the header both agree with the wrong answer, and nothing a
    reader could check contradicts the guess.
    """
    try:
        return len(next(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)))
    except (csv.Error, StopIteration):
        return 0


def _has_content(text: str) -> bool:
    return any(line.strip() for line in split_lines(text)[0])


def delimiter_evidence(text: str) -> dict[str, int]:
    """How many columns each candidate delimiter would produce.

    Reported alongside the choice, because a tie is a coin flip and saying
    so is the difference between a guess a reader can check and one they
    cannot. In the case this exists for -- ``trial,note;mean`` with
    ``a,b;3.0`` -- the guessed header ``note;mean`` is entirely plausible,
    so "the header below is the check" fails for exactly the input it was
    written for. The counts do not fail: they show two candidates tied.
    """
    if not _has_content(text):
        return dict.fromkeys(_CANDIDATES, 1)
    return {candidate: _first_record_width(text, candidate) for candidate in _CANDIDATES}


def sniff_delimiter(text: str) -> str:
    """The delimiter producing the most columns in the first record.

    Deterministic by construction: same text in, same delimiter out. A
    one-column file has no evidence either way and gets the ordinary comma,
    which is a no-op for a file that really has one column. Ties go to the
    earliest candidate, and comma is first.

    Reads a *record* rather than a line, so a quoted field containing a
    newline cannot shrink the sample into a fragment.
    """
    if not _has_content(text):
        return ","
    best = ","
    best_width = -1
    for candidate in _CANDIDATES:
        width = _first_record_width(text, candidate)
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
        evidence = delimiter_evidence(text)
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
                    f"read with {delimiter!r}. Column counts on the first populated "
                    f"line were "
                    + ", ".join(f"{k!r}:{v}" for k, v in evidence.items())
                    + f"; {delimiter!r} won. "
                    + (
                        "That is a tie, so this was a coin flip and the header below "
                        "should be read before anything is cited from it."
                        if sum(1 for v in evidence.values() if v == max(evidence.values())) > 1
                        else "The header below is the check: if it looks wrong, this "
                        "is where it went wrong."
                    )
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
            reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
            records: list[list[str]] = []
            # The physical line each record *begins* on. ``CsvLocator`` promises
            # the physical row "header included", and a record number is not
            # one: a quoted field holding a newline makes record N start on
            # line N+k, so a locator built from the record index points at the
            # wrong line of the file and nobody checking it would see why.
            starts: list[int] = []
            previous_end = 0
            for record in reader:
                starts.append(previous_end + 1)
                records.append(record)
                previous_end = reader.line_num
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
        # Always say which row became the header. Instrument exports, write.csv
        # with row names, and "Save as CSV" from Excel all put a title row
        # above the real one, and taking it silently produced a record where
        # the column "mean" appears nowhere and the measurement 3.0 is
        # addressed at column " 2024" -- an address no reader can resolve.
        header_preview = ", ".join(repr(name) for name in header[:6]) or "(empty)"
        extra_problems.append(
            ExtractionProblem(
                code="csv_header_row",
                # Stated, not advised. This fires on every CSV, and a message
                # that always fires with the same wording becomes noise at
                # volume -- it was carrying advice about a file the reader may
                # not be looking at. The advisory moved to
                # csv_title_row_suspected, which fires only when there is
                # something to advise about.
                detail=(f"row 1 is taken as the header, giving column names {header_preview}."),
                location="row 1",
            )
        )
        # Two signals, because width alone misses the commonest shape: a
        # two-column title over a two-column header is the *same* width, and
        # was exactly the case a width-only rule could not see.
        if len(records) > 1 and len(records[1]) > len(header):
            extra_problems.append(
                ExtractionProblem(
                    code="csv_later_row_wider_than_header",
                    detail=(
                        f"row 2 has {len(records[1])} field(s) and row 1 has "
                        f"{len(header)}, so row 1 may not be the header at all."
                    ),
                    location="row 2",
                )
            )
        if len(records) > 1 and any(" " in name.strip() for name in header):
            extra_problems.append(
                ExtractionProblem(
                    code="csv_title_row_suspected",
                    detail=(
                        f"row 1 contains {header_preview} -- a header name with a space "
                        f"in it is ordinary, but titles and preambles look the same "
                        f"shape. Confirm row 1 is the header before citing from it."
                    ),
                    location="row 1",
                )
            )
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
        for index, record in enumerate(records[1:], start=1):
            row_number = starts[index]
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
