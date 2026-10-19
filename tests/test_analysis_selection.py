"""The selection: which cells, and what to do about the ones that cannot be used.

LC-P1-10's corpus is this file's fixture. That is the point of T01: the
expected values say what each fixture contains and what the numbers over it
are, so a selection can be checked against **the same statement** the
operators will be checked against. If the selection resolves a cell
differently from the way the corpus describes it, one of the two is wrong and
the test says which.

Four things are under test here, and the last two are the ones that are easy
to get wrong:

* the **inventory** — which cells are absent, which are empty, which hold
  something that is not a number, and which hold a quantity;
* the **counts** that a statistic will be computed over;
* the **missing-value policy**, which is declared and not defaulted, and which
  refuses rather than degrading;
* the **format asymmetry** — a spreadsheet does not record a cell the author
  left blank, and a selection that reported "no blank cells" for a
  spreadsheet would be reporting something the ledger cannot support.

The quantity reader is not tested here, because it is not this file's: it
lives in :mod:`labcairn.sources.quantity` and C3's own tests cover it. What
is tested here is that **the analysis and the ledger use the same one** — a
second reader of "is this a number" would be a second answer to it, and the
disagreement would not crash.
"""

from __future__ import annotations

import pytest
from analysis_fixtures import (
    FIXTURE_NAMES,
    corpus_cells,
    corpus_selection,
    load_expected,
    row_numbers,
)

from labcairn.analysis.selection import (
    FilterOp,
    MissingPolicy,
    RowFilter,
    RowRange,
    RowSelection,
    RowSet,
    Selection,
    SelectionRefusedError,
    resolve_selection,
)
from labcairn.analysis.units import UnitDisagreementError, declared_unit_for
from labcairn.analysis.values import (
    CellAddress,
    CellOutcome,
    read_cell,
    records_blank_cells,
)
from labcairn.sources.source import SourceKind

HASH = "a" * 64


class _CorpusSource:
    """A cell source over one corpus fixture, read through the real adapters."""

    def __init__(self, fixture: str) -> None:
        self._cells = corpus_cells(fixture)
        self._rows = tuple(sorted({row for row, _ in self._cells}))
        kind = SourceKind.CSV if fixture.endswith(".csv") else SourceKind.XLSX
        self._records_blank = records_blank_cells(kind)

    def text_at(self, address: CellAddress) -> str | None:
        return self._cells.get((address.row, address.column))

    def rows(self) -> tuple[int, ...]:
        return self._rows

    @property
    def records_blank_cells(self) -> bool:
        return self._records_blank


def _selection(
    fixture: str,
    selection: dict[str, object],
    *,
    missing: MissingPolicy = MissingPolicy.EXCLUDE,
) -> Selection:
    """The selection an expected file describes."""
    rows = row_numbers(selection["rows"])
    return Selection(
        source_id=fixture,
        content_sha256=HASH,
        columns=tuple(selection["columns"]),  # type: ignore[arg-type]
        rows=RowRange(rows[0], rows[-1]) if len(rows) > 1 else RowSet(tuple(rows)),
        missing=missing,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "fixture", ["basic.csv", "groups.csv", "units.csv", "missing.csv", "holes.csv", "typed.csv"]
)
def test_a_selection_resolves_the_cells_the_corpus_describes(fixture: str) -> None:
    """The inventory matches the corpus's, cell for cell.

    Absent, empty and not-a-number are three different facts, and the corpus
    keeps them apart. A selection that collapsed them would let "the row was
    short" read as "the value was zero" — the imputation the acceptance
    clause forbids.
    """
    payload = load_expected(fixture)
    source = _CorpusSource(fixture)
    for described in payload["selections"]:
        expect = described["expect"]
        if expect["outcome"] == "refused":
            continue
        selection = _selection(fixture, described)
        result = resolve_selection(selection, source)
        got = {
            "absent": [
                [c.address.row, c.address.column]
                for c in result.cells
                if c.outcome is CellOutcome.ABSENT
            ],
            "empty": [
                [c.address.row, c.address.column]
                for c in result.cells
                if c.outcome is CellOutcome.EMPTY
            ],
            "not_a_quantity": [
                [c.address.row, c.address.column]
                for c in result.cells
                if c.outcome is CellOutcome.NOT_A_QUANTITY
            ],
        }
        for key, value in got.items():
            assert value == [list(p) for p in expect[key]], (
                f"{fixture}, selection {described['name']!r}: the {key} cells are "
                f"{value!r}, the corpus says {expect[key]!r}"
            )


@pytest.mark.unit
@pytest.mark.parametrize(
    "fixture", ["basic.csv", "groups.csv", "missing.csv", "holes.csv", "single.csv"]
)
def test_a_selection_counts_what_it_used_and_what_it_could_not(fixture: str) -> None:
    """The counts a statistic will be computed over, and the disclosure of the rest.

    ``n_used`` and ``n_without_value`` are what an operator needs; the three
    inventories are what a reader needs to know why the two differ. The corpus
    states the inventories, so the used count follows from them — and the two
    must add up to the number of cells the selection addressed.
    """
    payload = load_expected(fixture)
    source = _CorpusSource(fixture)
    described = payload["selections"][0]
    result = resolve_selection(_selection(fixture, described), source)
    expect = described["expect"]
    unusable = len(expect["absent"]) + len(expect["empty"]) + len(expect["not_a_quantity"])
    assert result.n_without_value == unusable
    assert result.n_used + result.n_without_value == len(result.cells)
    assert result.n_used == len(result.cells) - unusable


@pytest.mark.unit
def test_a_selection_reports_the_units_its_cells_carry() -> None:
    """The unit tokens are reported, and comparing them is the operator's job.

    C3's discipline — units are compared as written and never converted — is
    applied by the operator, not here. A selection that refused mixed units
    itself would be deciding a question the work order assigned elsewhere.
    """
    payload = load_expected("units.csv")
    source = _CorpusSource("units.csv")
    described = payload["selections"][1]
    result = resolve_selection(_selection("units.csv", described), source)
    assert result.units == ("kg",)
    assert result.n_used == 4


@pytest.mark.unit
def test_a_refused_selection_raises_rather_than_returning_a_partial_answer() -> None:
    """``REFUSE`` refuses. It does not return a result carrying a flag.

    A caller handed a partial set and a ``refused=True`` is a caller that can
    use the partial set, and the refusal becomes a suggestion.

    Note which refusal this is: the policy here is about a cell that yields
    **no quantity**. The corpus's ``units.csv`` refusal is a different one —
    the *operator* refusing a selection that carries two unit tokens — and it
    belongs to LC-P1-10 T04, not to the selection.
    """
    payload = load_expected("missing.csv")
    source = _CorpusSource("missing.csv")
    described = payload["selections"][0]
    with pytest.raises(SelectionRefusedError) as raised:
        resolve_selection(
            _selection("missing.csv", described, missing=MissingPolicy.REFUSE), source
        )
    assert raised.value.unusable
    assert "refuse" in str(raised.value)


@pytest.mark.unit
def test_an_excluded_selection_reports_what_it_skipped() -> None:
    """``EXCLUDE`` uses what it can and says what it left out."""
    source = _CorpusSource("missing.csv")
    payload = load_expected("missing.csv")
    described = payload["selections"][0]
    result = resolve_selection(_selection("missing.csv", described), source)
    assert result.n_used == 3
    assert result.n_empty == 1
    assert result.n_invalid == 1
    assert result.n_absent == 1
    assert result.n_without_value == 3


@pytest.mark.unit
def test_a_range_names_its_rows_literally() -> None:
    """A row the source has no cells in is still a row the selection named.

    The addresses under it are reported as absent rather than quietly dropped.
    A selection that clipped to the source's extent would make "the row was
    short" invisible.
    """
    source = _CorpusSource("missing.csv")
    selection = Selection(
        source_id="missing.csv",
        content_sha256=HASH,
        columns=("value",),
        rows=RowRange(2, 7),
        missing=MissingPolicy.EXCLUDE,
    )
    result = resolve_selection(selection, source)
    assert result.n_absent == 1
    assert (7, "value") in {
        (c.address.row, c.address.column) for c in result.cells if c.outcome is CellOutcome.ABSENT
    }


class _ShortRowSource:
    """A source where one row has a cell in one column and none in another.

    The corpus has no such fixture, and the reason is worth knowing: a ragged
    CSV row is short at the **end**, and a trailing blank line has no cells at
    all, so no row in the corpus exists in one column and not another. The
    rule is still worth holding, so it is stated here against a source built
    for it.
    """

    def __init__(self) -> None:
        self._cells = {(2, "group"): "A", (2, "value"): "1.0", (3, "group"): "B"}

    def text_at(self, address: CellAddress) -> str | None:
        return self._cells.get((address.row, address.column))

    def rows(self) -> tuple[int, ...]:
        return (2, 3)

    @property
    def records_blank_cells(self) -> bool:
        return True


@pytest.mark.unit
def test_a_filter_never_admits_a_row_whose_cell_does_not_exist() -> None:
    """A cell that was never recorded matches nothing, not even ``NE``.

    There is nothing to compare, and a row admitted for the sake of a
    comparison that could not be made would be a row nobody asked for.
    """
    selection = Selection(
        source_id="short.csv",
        content_sha256=HASH,
        columns=("value",),
        rows=RowFilter(column="value", op=FilterOp.EQ, value="1.0"),
        missing=MissingPolicy.EXCLUDE,
    )
    result = resolve_selection(selection, _ShortRowSource())
    assert len(result.cells) == 1
    assert result.n_used == 1


@pytest.mark.unit
def test_a_filter_never_compares_prose_as_if_it_were_a_number() -> None:
    """A cell that holds a word is not a number, and is not compared as one.

    Comparing prose as if it were ``0.0`` would admit the row into a
    selection on the strength of a comparison nobody could make.
    """
    source = _CorpusSource("missing.csv")
    selection = Selection(
        source_id="missing.csv",
        content_sha256=HASH,
        columns=("value",),
        rows=RowFilter(column="value", op=FilterOp.GE, value="0"),
        missing=MissingPolicy.EXCLUDE,
    )
    result = resolve_selection(selection, source)
    assert len(result.cells) == 3
    assert result.n_used == 3


@pytest.mark.unit
def test_a_filter_selects_the_rows_that_match() -> None:
    """A filter over a column narrows the selection to the rows that match."""
    source = _CorpusSource("basic.csv")
    selection = Selection(
        source_id="basic.csv",
        content_sha256=HASH,
        columns=("value",),
        rows=RowFilter(column="group", op=FilterOp.EQ, value="A"),
        missing=MissingPolicy.EXCLUDE,
    )
    result = resolve_selection(selection, source)
    assert result.n_used == 5
    assert result.n_without_value == 0


@pytest.mark.unit
@pytest.mark.unit
def test_a_filter_that_orders_needs_a_quantity() -> None:
    """An ordering comparison against prose would have to guess what it means."""
    with pytest.raises(ValueError):
        RowFilter(column="group", op=FilterOp.GT, value="A")


@pytest.mark.unit
def test_a_selection_needs_columns() -> None:
    """A selection over no columns is a statistic over nothing."""
    with pytest.raises(ValueError):
        Selection(
            source_id="basic.csv",
            content_sha256=HASH,
            columns=(),
            rows=RowRange(2, 11),
            missing=MissingPolicy.EXCLUDE,
        )


@pytest.mark.unit
def test_a_selection_may_not_repeat_a_column() -> None:
    """One column twice is one column, and its cells would be counted twice."""
    with pytest.raises(ValueError):
        Selection(
            source_id="basic.csv",
            content_sha256=HASH,
            columns=("value", "value"),
            rows=RowRange(2, 11),
            missing=MissingPolicy.EXCLUDE,
        )


@pytest.mark.unit
def test_the_blank_cell_fact_matches_the_adapters() -> None:
    """The fact the analysis carries is the adapters' behaviour, not a guess.

    A delimited source records a cell the author left blank; a spreadsheet
    does not, because its adapter writes a unit only for a cell that holds
    something. So the same blank cell is visible in one and invisible in the
    other, and a spreadsheet's "no blank cells" is not a statement the ledger
    can support.
    """
    assert records_blank_cells(SourceKind.CSV) is True
    assert records_blank_cells(SourceKind.XLSX) is False

    csv_source = _CorpusSource("holes.csv")
    sheet_source = _CorpusSource("holes.xlsx")
    address = CellAddress(row=4, column="value")

    csv_cell = read_cell(csv_source, address)
    assert csv_cell.outcome is CellOutcome.EMPTY
    assert csv_source.records_blank_cells is True

    sheet_cell = read_cell(sheet_source, address)
    assert sheet_cell.outcome is CellOutcome.ABSENT
    assert sheet_source.records_blank_cells is False


@pytest.mark.unit
def test_the_analysis_and_the_ledger_read_a_quantity_the_same_way() -> None:
    """One reader of "is this a number", so the two layers cannot disagree.

    A ledger that calls ``"3.5 kg"`` a quantity and an analysis that calls it
    prose would not crash; it would produce a number nobody checked twice.
    """
    from labcairn.evidence.checks.c3 import read_number as ledger_reader
    from labcairn.sources.quantity import read_number as shared_reader

    assert ledger_reader is shared_reader
    for text in ("3.50", "3.5 kg", "not-a-number", "", "1,234", "12%"):
        assert ledger_reader(text) == shared_reader(text)


# ---------------------------------------------------------------------------
# A column's declared unit, and the data under it
# ---------------------------------------------------------------------------


class _CellsSource:
    """A cell source over a table written out in the test.

    The corpus is the fixture for what a real table looks like. This is for
    the cases the corpus cannot hold, because the case is about the *check*
    and not about a table anyone would keep.
    """

    def __init__(self, cells: dict[tuple[int, str], str]) -> None:
        self._cells = cells
        self._rows = tuple(sorted({row for row, _ in cells}))

    def text_at(self, address: CellAddress) -> str | None:
        return self._cells.get((address.row, address.column))

    def rows(self) -> tuple[int, ...]:
        return self._rows

    @property
    def records_blank_cells(self) -> bool:
        return True


#: The one row the synthetic tables below hold. A module-level singleton, so
#: that it is a value rather than a call in an argument default.
_ONE_ROW: RowSelection = RowRange(2, 2)


def _synthetic(columns: tuple[str, ...], rows: RowSelection = _ONE_ROW) -> Selection:
    """A selection over a synthetic table."""
    return Selection(
        source_id="synthetic.csv",
        content_sha256=HASH,
        columns=columns,
        rows=rows,
        missing=MissingPolicy.EXCLUDE,
    )


@pytest.mark.unit
def test_a_header_that_declares_a_unit_the_cells_contradict_is_refused() -> None:
    """The one case the corpus's other fixtures cannot hold.

    Every cell of the column says ``m`` and the header says ``cm``, so the
    cells agree with *each other* and a check that compared the cells only
    with each other would have nothing to say and would pass. This is the
    case the check exists for, and the reason a check that only ever looked
    at cell text would have been vacuous.

    The refusal happens in the **selection**, not in an operator, because the
    conflict is about the column: the selection is what names a column and
    resolves its cells, so every operator inherits the check rather than each
    one repeating it.
    """
    source = _CorpusSource("declared.csv")
    selection = corpus_selection("declared.csv", {"rows": "2-5", "columns": ["length (cm)"]})
    with pytest.raises(UnitDisagreementError):
        resolve_selection(selection, source)


@pytest.mark.unit
def test_the_refusal_names_both_tokens() -> None:
    """A reader told only that the units differ cannot tell a typo from a
    real second unit, so the refusal names **both** of them.

    The quotes are load-bearing. The column's own name contains ``cm``, so a
    bare substring would be satisfied by the name alone, and a message that
    named neither token would pass. Only a quoted token is a token.
    """
    source = _CorpusSource("declared.csv")
    selection = corpus_selection("declared.csv", {"rows": "2-5", "columns": ["length (cm)"]})
    with pytest.raises(UnitDisagreementError) as raised:
        resolve_selection(selection, source)
    message = str(raised.value)
    assert "'cm'" in message
    assert "'m'" in message


@pytest.mark.unit
def test_a_column_that_declares_a_unit_the_cells_agree_with_is_not_refused() -> None:
    """A declaration the data confirms is not a conflict.

    A refusal that fired on a confirmed declaration would be a check nobody
    could satisfy, which is the other way a check stops being one.
    """
    source = _CorpusSource("declared.csv")
    selection = corpus_selection("declared.csv", {"rows": "2-5", "columns": ["mass (kg)"]})
    result = resolve_selection(selection, source)
    assert result.units == ("kg",)
    assert result.n_used == 4


@pytest.mark.unit
def test_a_declared_unit_no_cell_corroborates_is_unverified_and_nothing_is_refused() -> None:
    """A cell with no token leaves the declared unit unverified.

    The asymmetry C3 keeps: a bare numeric cell has no unit to contradict, so
    the header's claim is neither confirmed nor denied and nothing is
    refused. ``typed.csv`` is exactly that case, and a column the source does
    not have at all is the same case with no cells in it.
    """
    source = _CorpusSource("typed.csv")
    selection = corpus_selection("typed.csv", {"rows": "2-4", "columns": ["mass (kg)"]})
    result = resolve_selection(selection, source)
    assert result.units == ()
    assert result.n_used == 3

    absent = _CellsSource({(2, "other"): "1.0"})
    empty = resolve_selection(_synthetic(("mass (kg)",)), absent)
    assert empty.n_absent == 1
    assert empty.units == ()


@pytest.mark.unit
def test_a_header_that_declares_nothing_is_not_compared_with_the_cells() -> None:
    """A header that declares nothing has no claim to check.

    Two shapes, and the second is the one C3's own docstring names: prose in
    parentheses is not a unit, and a cell carrying a unit under such a header
    is not a conflict, because there is nothing to disagree with.
    """
    source = _CorpusSource("declared.csv")
    selection = corpus_selection(
        "declared.csv", {"rows": "2-5", "columns": ["total (see table 2)"]}
    )
    result = resolve_selection(selection, source)
    assert result.units == ("kg",)

    plain = _CellsSource({(2, "value"): "3.5 kg"})
    assert resolve_selection(_synthetic(("value",)), plain).units == ("kg",)


@pytest.mark.unit
def test_the_declaration_is_checked_against_the_columns_own_cells_only() -> None:
    """A declaration is a claim about one column, and only that column answers it.

    ``mass (kg)`` says kg and its own cells say kg, so it is not a conflict
    however many other columns of the same selection carry something else.
    The other columns' units are a different problem with a different owner:
    a selection whose cells disagree with each other is refused by the
    operator, and that check is not this one.
    """
    source = _CellsSource({(2, "mass (kg)"): "1.0 kg", (2, "other"): "2.0 g"})
    result = resolve_selection(_synthetic(("mass (kg)", "other")), source)
    assert result.units == ("g", "kg")


@pytest.mark.unit
def test_two_unit_tokens_in_a_column_are_the_operator_s_refusal_and_not_this_one() -> None:
    """Two different problems, two different owners.

    ``units.csv``'s column declares nothing and its cells carry two tokens.
    The selection resolves it — the cells are readable — and the *operator*
    refuses, because a selection whose cells disagree with each other is not
    a statistic over anything. The refusal in this file is the other one: a
    column whose header contradicts its own data.
    """
    payload = load_expected("units.csv")
    source = _CorpusSource("units.csv")
    described = payload["selections"][0]
    rows = row_numbers(described["rows"])
    selection = Selection(
        source_id="units.csv",
        content_sha256=HASH,
        columns=("value",),
        rows=RowRange(rows[0], rows[-1]),
        missing=MissingPolicy.EXCLUDE,
    )
    result = resolve_selection(selection, source)
    assert result.units == ("g", "kg")


@pytest.mark.unit
def test_a_narrowed_selection_inherits_the_check() -> None:
    """The check travels with the selection, so a narrowed one is checked too.

    A grouped aggregate narrows a selection to the column it measures and
    resolves that. The check is where the narrowing happens, so the narrowed
    selection is refused for the same reason the whole one is — which is the
    reason the check is in the selection and not in each operator.
    """
    source = _CorpusSource("declared.csv")
    selection = Selection(
        source_id="declared.csv",
        content_sha256=HASH,
        columns=("length (cm)",),
        rows=RowSet((2, 3)),
        missing=MissingPolicy.EXCLUDE,
    )
    with pytest.raises(UnitDisagreementError):
        resolve_selection(selection, source)


@pytest.mark.unit
def test_an_incomplete_and_conflicting_selection_is_refused_for_the_incompleteness() -> None:
    """The caller's declared policy is honoured before the analysis-level refusal.

    A selection that cannot be resolved under ``REFUSE`` does not exist as
    asked, so there is nothing yet to say about what its column means. The
    conflict is still waiting once the holes are filled, and which of the two
    refusals comes first is stated here rather than left to whichever was
    written first.
    """
    source = _CellsSource({(2, "mass (kg)"): "1.0 g", (3, "mass (kg)"): ""})
    selection = Selection(
        source_id="synthetic.csv",
        content_sha256=HASH,
        columns=("mass (kg)",),
        rows=RowRange(2, 3),
        missing=MissingPolicy.REFUSE,
    )
    with pytest.raises(SelectionRefusedError):
        resolve_selection(selection, source)


@pytest.mark.unit
def test_every_fixture_records_the_declarations_its_headers_make() -> None:
    """The corpus's record of what a header declares is the record the code produces.

    A corpus that says a header declares a unit it does not declare — or
    that forgot to record one it does — misstates the very thing the check
    is about, and a reader of the corpus would be misled about which columns
    the check has something to say on.
    """
    for name in FIXTURE_NAMES:
        payload = load_expected(name)
        declared = {
            header: unit
            for header in payload["columns"]
            if (unit := declared_unit_for(header)) is not None
        }
        assert payload["declared_units"] == declared, (
            f"{name} records the declarations {payload['declared_units']!r}, and "
            f"its headers declare {declared!r}"
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("header", "declared", "carried"),
    [
        ("mass (kg)", "kg", "g"),
        ("mass (KG)", "KG", "kg"),
        ("mass (kg)", "kg", "kilograms"),
    ],
)
def test_units_are_compared_as_written_and_never_converted(
    header: str, declared: str, carried: str
) -> None:
    """``kg`` against ``g`` is a disagreement, and it stays one.

    The same quantity written two ways is still two tokens, and the owner's
    decision is that the two are not reconciled: a conversion table is a unit
    algebra, and the arithmetic of that algebra would need an evidence
    standard this ledger does not have in Phase 1. The tokens are also
    compared case-sensitively, because they are compared *as written*.
    """
    source = _CellsSource({(2, header): f"1.0 {carried}"})
    with pytest.raises(UnitDisagreementError) as raised:
        resolve_selection(_synthetic((header,)), source)
    message = str(raised.value)
    assert f"'{declared}'" in message
    assert f"'{carried}'" in message
