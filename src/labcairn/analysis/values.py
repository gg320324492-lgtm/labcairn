"""What one cell of a table is, once it has been read.

Four things can be true of a cell, and they are four different facts:

* it holds a **quantity** -- one number and at most one unit token, read by
  the project's single quantity reader
  (:mod:`labcairn.sources.quantity`);
* it holds **no text** -- the cell is there and the author left it blank;
* it holds **text that is not a quantity** -- a word, a date, a stray symbol;
* it **does not exist** -- nothing was recorded at that address.

The last two are the ones that get confused, and the confusion is the whole
reason this module exists. A cell that does not exist and a cell that is
blank are indistinguishable *in a spreadsheet*, because the spreadsheet
adapter does not extract an empty cell — but they are not the same fact, and
a statistic that treated them the same would report a number it cannot
account for.

Which is why a cell source has to say whether it can see a blank cell at all.
:func:`records_blank_cells` is that statement, and it is a fact about the two
adapters rather than about the analysis: the delimited adapter writes a unit
for every cell it read, empty ones included, and the spreadsheet adapter
writes a unit only for a cell that holds something.

**So the count of addresses with no recorded value is known in both formats,
and the count of cells the author actually left blank is not knowable in a
spreadsheet.** That is a fact about the ledger, and it is the reason the
selection carries the answer alongside the numbers: a report that says "no
blank cells" is making a claim the ledger can support for a CSV and cannot
support for a spreadsheet.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from labcairn.sources.primitives import NonEmptyText
from labcairn.sources.quantity import NumericReading, read_number
from labcairn.sources.source import SourceKind

__all__ = [
    "CellAddress",
    "CellOutcome",
    "ResolvedCell",
    "ValueSource",
    "read_cell",
    "records_blank_cells",
]


class CellOutcome(StrEnum):
    """What a cell turned out to be.

    The vocabulary is closed because a caller has to be able to tell the four
    apart. A cell source that could not distinguish "blank" from "absent"
    would have to collapse them, and the collapse is the imputation this
    project refuses.
    """

    #: The cell holds a quantity, and the reading is in ``ResolvedCell.reading``.
    VALUE = "value"
    #: The cell is there and holds no text. The author left it blank.
    EMPTY = "empty"
    #: Nothing was recorded at that address.
    ABSENT = "absent"
    #: The cell holds text that is not a single quantity.
    NOT_A_QUANTITY = "not_a_quantity"


@dataclass(frozen=True, slots=True)
class CellAddress:
    """Where a cell is: its physical row, and its column's header text.

    The row is the **physical** row of the file, header included — the same
    coordinate ``CsvLocator.row`` and ``XlsxLocator``'s reference carry. The
    column is the **header text**, never an index, because a ledger that cites
    "column 4" is unreadable to the person who has to check it.

    Both formats address a cell this way, which is what makes a CSV and a
    spreadsheet comparable: a selection can name the same address in each.
    """

    row: int
    column: NonEmptyText

    def __post_init__(self) -> None:
        if self.row < 1:
            raise ValueError(
                f"row {self.row} is not a row. Rows are counted from 1 and the "
                f"header is row 1, so row 0 does not exist."
            )


class ValueSource(Protocol):
    """Where a selection's cells come from.

    Deliberately narrow, and the narrowness is the design: a selection is a
    **description**, and resolving it against the ledger is the run path's job
    (LC-P1-10 T09). Keeping the two apart is what lets the selection's
    behaviour be tested against synthetic cells *and* against the real
    adapters without a database in the middle.

    ``text_at`` returns ``None`` for an address where nothing was recorded,
    and the empty string for a cell that was recorded and holds no text. The
    difference is the whole point, so the protocol states it in words rather
    than leaving it to the implementation.
    """

    def text_at(self, address: CellAddress) -> str | None:
        """The text at *address*, or ``None`` when no cell was recorded there."""
        ...

    def rows(self) -> tuple[int, ...]:
        """The physical rows this source has cells in, ascending."""
        ...

    @property
    def records_blank_cells(self) -> bool:
        """Whether a cell the author left blank is visible to this source.

        ``False`` means a blank cell and a cell that was never there are the
        same observation, and the number of blanks is not knowable.
        """
        ...


@dataclass(frozen=True, slots=True)
class ResolvedCell:
    """One addressed cell, and what it turned out to be."""

    address: CellAddress
    outcome: CellOutcome
    #: The text as recorded, or ``None`` when nothing was recorded.
    text: str | None
    #: The reading, when the cell is a quantity.
    reading: NumericReading | None

    @property
    def value(self) -> float | None:
        """The cell's number, when it has one."""
        return self.reading.value if self.reading is not None else None

    @property
    def unit(self) -> str | None:
        """The cell's unit token, when it has one."""
        return self.reading.unit if self.reading is not None else None


def read_cell(source: ValueSource, address: CellAddress) -> ResolvedCell:
    """Read one addressed cell and say what it is.

    The order of the questions matters. *Is there a cell here?* comes before
    *is it empty?*, which comes before *is it a number?* — because a cell that
    is not there has no text to be empty, and a cell that is empty has no
    number to read.
    """
    text = source.text_at(address)
    if text is None:
        return ResolvedCell(address=address, outcome=CellOutcome.ABSENT, text=None, reading=None)
    if not text.strip():
        return ResolvedCell(address=address, outcome=CellOutcome.EMPTY, text=text, reading=None)
    reading = read_number(text)
    if reading.value is None:
        return ResolvedCell(
            address=address, outcome=CellOutcome.NOT_A_QUANTITY, text=text, reading=reading
        )
    return ResolvedCell(address=address, outcome=CellOutcome.VALUE, text=text, reading=reading)


def records_blank_cells(kind: SourceKind) -> bool:
    """Whether a source of this kind records a cell the author left blank.

    **Measured against the two adapters**, and kept honest by
    ``test_the_blank_cell_fact_matches_the_adapters``: the delimited adapter
    writes a unit for every cell it read, empty ones included, so
    ``basic.csv``'s blank cell is in the ledger; the spreadsheet adapter writes
    a unit only for a cell that holds something, so the same blank cell in
    ``holes.xlsx`` is not.

    The fact is here rather than on the adapters because the analysis layer is
    where it is needed, and because the code that needs it does not *branch* on
    it — it carries it. A fact that changes behaviour belongs with the
    behaviour; a fact that is carried belongs with the carrier.
    """
    return kind is SourceKind.CSV
