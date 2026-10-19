"""A selection: which cells of a source, and what to do about the ones that
cannot be used.

The selection is a **description**, and it is deliberately separate from
resolving it against the ledger. That separation is what lets the same code
be checked against synthetic cells and against the real adapters, and it
keeps the store out of a module whose job is to say what a set of cells
means.

Four decisions are baked in here, and each of them is a decision the work
order had to make:

**The columns are named, never numbered.** A selection that says "column 4" is
unreadable to the person who has to check it, and the same is true of the
ledger: ``CsvLocator.column`` is the header text for exactly that reason.

**The rows are named in one of three closed ways** — a contiguous range, an
explicit set, or a filter over one column. There is no expression language,
because an expression language is a program and LC-P1-10 has no program
execution surface at all.

**The missing-value policy is declared, not defaulted.** A default would be a
silent decision about the data: a statistic over a selection with holes is a
statistic over something the caller did not ask for, unless the caller said
so. ``EXCLUDE`` says "use what you can and tell me what you skipped";
``REFUSE`` says "do not proceed on a partial selection".

**A filter only considers cells that exist.** A cell that was never recorded
matches no operator, including ``NE``: there is nothing to compare, and
admitting it would put a row in the selection for no stated reason.

What is decided here, and what is not
-------------------------------------
**A column's declared unit is checked against that column's own cells.** A
header of the form ``mass (kg)`` declares a unit, and the cells under it are
the only evidence that can check the claim: a real table almost never puts
units in its cells, so a check that only ever looked at cell text would find
no unit to check and pass vacuously. A cell carrying a token the header does
not declare is a **conflict**, and it is refused here rather than in each
operator, because the conflict is about the column — which the selection is
what names and resolves.

**The cells' unit tokens are not compared with each other here.** Whether the
tokens in a selection agree with one another is the operator's business
(LC-P1-10 T04), because C3's discipline — units are compared as written and
never converted — is the operator's to apply, not the selection's to
anticipate.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from labcairn.analysis.units import UnitDisagreementError, declaration_disagreement
from labcairn.analysis.values import (
    CellAddress,
    CellOutcome,
    ResolvedCell,
    ValueSource,
    read_cell,
)
from labcairn.sources.primitives import ContentHash, NonEmptyText
from labcairn.sources.quantity import read_number

__all__ = [
    "FilterOp",
    "MissingPolicy",
    "RowFilter",
    "RowRange",
    "RowSelection",
    "RowSet",
    "Selection",
    "SelectionRefusedError",
    "SelectionResult",
    "resolve_selection",
]


class MissingPolicy(StrEnum):
    """What to do about a cell that yields no quantity."""

    #: Use the cells that can be used, and report the ones that could not.
    EXCLUDE = "exclude"
    #: Refuse the whole selection. A statistic over a selection with holes is
    #: a statistic over something the caller did not ask for.
    REFUSE = "refuse"


class FilterOp(StrEnum):
    """The comparisons a row filter may make.

    Closed, because a filter that could express anything would be a program.
    """

    #: The cell's text, exactly as recorded.
    EQ = "eq"
    NE = "ne"
    #: The cell's quantity, against the filter's quantity.
    GT = "gt"
    GE = "ge"
    LT = "lt"
    LE = "le"


#: The operators that compare quantities rather than text.
_ORDERING_OPS: Final[frozenset[FilterOp]] = frozenset(
    {FilterOp.GT, FilterOp.GE, FilterOp.LT, FilterOp.LE}
)


@dataclass(frozen=True, slots=True)
class RowRange:
    """A contiguous run of physical rows, inclusive at both ends."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 1:
            raise ValueError(f"row range starts at {self.start}, and row 0 does not exist.")
        if self.end < self.start:
            raise ValueError(f"row range {self.start}..{self.end} ends before it starts.")


@dataclass(frozen=True, slots=True)
class RowSet:
    """An explicit set of physical rows."""

    rows: tuple[int, ...]

    def __post_init__(self) -> None:
        if any(row < 1 for row in self.rows):
            raise ValueError("every row must be at least 1, and row 0 does not exist.")
        if len(set(self.rows)) != len(self.rows):
            raise ValueError(
                f"the row set repeats a row: {list(self.rows)}. One row twice is "
                f"one row, and a cell that appears twice would be counted twice."
            )


@dataclass(frozen=True, slots=True)
class RowFilter:
    """The rows whose value in one column satisfies a comparison.

    ``EQ`` and ``NE`` compare the cell's **text**, exactly as recorded. The
    ordering operators compare the cell's **quantity**, and a cell that is not
    a quantity never matches — silently comparing prose as if it were a
    number is the fabrication this project has been bitten by before.
    """

    column: NonEmptyText
    op: FilterOp
    value: str

    def __post_init__(self) -> None:
        if self.op in _ORDERING_OPS:
            reading = read_number(self.value)
            if reading.value is None:
                raise ValueError(
                    f"the filter compares with {self.op.value!r}, which is an "
                    f"ordering comparison, and {self.value!r} is not a quantity. "
                    f"A comparison against prose would have to guess what it "
                    f"means, and a guess here is a number nobody chose."
                )

    @property
    def quantity(self) -> float:
        """The filter's own value, as a number. Only for the ordering operators."""
        reading = read_number(self.value)
        if reading.value is None:  # pragma: no cover - the constructor refuses it
            raise ValueError(f"{self.value!r} is not a quantity.")
        return reading.value


#: The three ways a selection can name its rows.
RowSelection = RowRange | RowSet | RowFilter


@dataclass(frozen=True, slots=True)
class Selection:
    """Which cells of which source, and what to do about the ones that cannot
    be used.

    ``content_sha256`` is the source's content hash, so the selection is bound
    to a particular version of a particular file. A selection that named only
    a source would still be answering a question about a file whose bytes
    might have changed since the question was written down.
    """

    source_id: NonEmptyText
    content_sha256: ContentHash
    columns: tuple[NonEmptyText, ...]
    rows: RowSelection
    #: No default. A default is a silent decision about the data.
    missing: MissingPolicy

    def __post_init__(self) -> None:
        if not self.columns:
            raise ValueError(
                "a selection names no columns. A selection over no columns is "
                "a statistic over nothing."
            )
        if len(set(self.columns)) != len(self.columns):
            raise ValueError(
                f"the columns repeat: {list(self.columns)}. One column twice is "
                f"one column, and its cells would be counted twice."
            )


class SelectionRefusedError(RuntimeError):
    """The selection could not be resolved under the missing-value policy.

    A refusal, not a flag. The caller asked for a statistic over a set of
    cells, and the answer is that the set does not exist as asked; a result
    carrying ``refused=True`` and a partial set beside it is a shape that
    invites the caller to use the partial set anyway.
    """

    def __init__(self, *, selection: Selection, unusable: tuple[ResolvedCell, ...]) -> None:
        self.selection = selection
        self.unusable = unusable
        super().__init__(
            f"the selection over {selection.source_id!r} names "
            f"{len(unusable)} cell(s) that yield no quantity, and the policy is "
            f"{selection.missing.value!r}. The first is "
            f"{unusable[0].address.row}:{unusable[0].address.column!r}."
        )


@dataclass(frozen=True, slots=True)
class SelectionResult:
    """Every addressed cell, and what each of them turned out to be."""

    selection: Selection
    cells: tuple[ResolvedCell, ...]
    #: Whether this source records a cell the author left blank. ``False``
    #: means a blank cell and a cell that was never there are the same
    #: observation, and the number of blanks is not knowable.
    records_blank_cells: bool

    @property
    def n_used(self) -> int:
        """The cells that yielded a quantity."""
        return sum(1 for cell in self.cells if cell.outcome is CellOutcome.VALUE)

    @property
    def n_empty(self) -> int:
        """The cells that were recorded and hold no text."""
        return sum(1 for cell in self.cells if cell.outcome is CellOutcome.EMPTY)

    @property
    def n_absent(self) -> int:
        """The addresses where no cell was recorded."""
        return sum(1 for cell in self.cells if cell.outcome is CellOutcome.ABSENT)

    @property
    def n_invalid(self) -> int:
        """The cells that hold text which is not a quantity."""
        return sum(1 for cell in self.cells if cell.outcome is CellOutcome.NOT_A_QUANTITY)

    @property
    def n_without_value(self) -> int:
        """Every cell that yielded no quantity, of any kind."""
        return len(self.cells) - self.n_used

    @property
    def quantities(self) -> tuple[ResolvedCell, ...]:
        """The cells that yielded a quantity, in the order they were read."""
        return tuple(cell for cell in self.cells if cell.outcome is CellOutcome.VALUE)

    @property
    def units(self) -> tuple[str, ...]:
        """The distinct unit tokens the used cells carry, sorted.

        A tuple rather than a set, so that two runs over the same cells
        produce the same value in the same order — a manifest compares bytes.
        """
        return tuple(sorted({cell.unit for cell in self.quantities if cell.unit is not None}))

    @property
    def unusable(self) -> tuple[ResolvedCell, ...]:
        """The cells that yielded no quantity, of any kind."""
        return tuple(cell for cell in self.cells if cell.outcome is not CellOutcome.VALUE)


def resolve_selection(selection: Selection, source: ValueSource) -> SelectionResult:
    """Read every cell the selection names and say what each of them is.

    Under the ``REFUSE`` policy, a selection with any unusable cell raises
    rather than returning a partial answer. Under ``EXCLUDE`` the unusable
    cells are counted and left out, and the counts are the disclosure.

    A column whose header declares a unit the cells contradict is refused
    here as well, and not in each operator. The check is about the column,
    and a selection is what names a column and resolves its cells — so every
    operator that resolves a selection inherits the check, and a grouped
    aggregate inherits it through the narrowed selection it resolves.
    """
    rows = _rows_for(selection.rows, source)
    cells = tuple(
        read_cell(source, CellAddress(row=row, column=column))
        for row in rows
        for column in selection.columns
    )
    result = SelectionResult(
        selection=selection,
        cells=cells,
        records_blank_cells=source.records_blank_cells,
    )
    if selection.missing is MissingPolicy.REFUSE and result.unusable:
        raise SelectionRefusedError(selection=selection, unusable=result.unusable)
    conflict = _declaration_conflict(selection, result)
    if conflict is not None:
        raise UnitDisagreementError(conflict)
    return result


def _declaration_conflict(selection: Selection, result: SelectionResult) -> str | None:
    """The reason a column's declared unit disagrees with its cells, or ``None``.

    The check is **per column**. A declaration is a claim about one column,
    so it is checked against that column's own cells and not against the
    units the selection's other columns happen to carry: a column that
    agrees with its own header would otherwise be refused because of a
    column somewhere else in the same selection, which is a different
    problem with a different owner.
    """
    tokens_by_column: dict[str, set[str]] = {}
    for cell in result.quantities:
        unit = cell.unit
        if unit is None:
            continue
        tokens_by_column.setdefault(cell.address.column, set()).add(unit)
    for column in selection.columns:
        reason = declaration_disagreement(column, tokens_by_column.get(column, set()))
        if reason is not None:
            return reason
    return None


def _rows_for(spec: RowSelection, source: ValueSource) -> tuple[int, ...]:
    """The physical rows a row selection names.

    A range and an explicit set name their rows **literally**: a row the
    source has no cells in is still a row the selection named, and the
    addresses under it are reported as absent rather than quietly dropped. A
    filter, on the other hand, can only name rows the source has, because it
    has to look at them to decide.
    """
    if isinstance(spec, RowRange):
        return tuple(range(spec.start, spec.end + 1))
    if isinstance(spec, RowSet):
        return spec.rows
    return tuple(
        row
        for row in source.rows()
        if _matches(read_cell(source, CellAddress(row=row, column=spec.column)), spec)
    )


def _matches(cell: ResolvedCell, spec: RowFilter) -> bool:
    """Whether one cell satisfies a filter.

    A cell that was never recorded matches nothing, including ``NE``: there
    is nothing to compare, and a row admitted for the sake of a comparison
    that could not be made would be a row nobody asked for.
    """
    if cell.text is None:
        return False
    if spec.op is FilterOp.EQ:
        return cell.text == spec.value
    if spec.op is FilterOp.NE:
        return cell.text != spec.value
    value = cell.value
    if value is None:
        return False
    target = spec.quantity
    if spec.op is FilterOp.GT:
        return value > target
    if spec.op is FilterOp.GE:
        return value >= target
    if spec.op is FilterOp.LT:
        return value < target
    return value <= target
