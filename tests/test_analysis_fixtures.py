"""The corpus itself: that the fixtures ingest to what their expected values say.

What this file is for
---------------------
LC-P1-10's operators will be tested against a corpus, and a corpus that is
wrong is worse than no corpus: every operator test would then be asserting
something false with great confidence. So this file checks the corpus before
anything is measured against it.

It checks three things, and the third is the one that matters most:

1. **Completeness.** Every fixture has expected values, and every expected
   values file names a fixture that exists. A corpus with a hole in it is a
   hole in the operators' test coverage, and nobody would notice.
2. **The contract with ingestion.** Each fixture ingests to the cells its
   expected values describe -- which cells exist, which are empty, which are
   not quantities, and which are absent altogether.
3. **The numbers.** The statistics in the expected values are the statistics
   of the data, computed here by Python's :mod:`statistics` -- an
   implementation that is **not LabCairn's**, so the expectation does not
   share a bug with the code the operators will be written against. The
   classification of a cell as a quantity uses C3's own reader, because that
   reader *is* the definition of "a quantity" this project uses, and two
   definitions of it would be two answers to one question.

Why the expected values are in data files
------------------------------------------
An expectation written inside the test can be corrupted by the same bug that
breaks the code under test. An expectation in a file beside the data cannot,
and a change to the fixtures fails a test rather than silently rewriting a
golden file. **No script in this repository regenerates the
``*.expected.json`` files**, and that is the property worth keeping.

The addressing contract this file states
----------------------------------------
The corpus is format-neutral, so the two adapters have to be brought to a
common address, and the rules are worth writing down because T03 will have
to implement them:

* A **cell** is addressed by its **physical row** and its **column's header
  text**. In a CSV the header row is row 1 and is not a set of cells; in a
  spreadsheet the header row is row 1 and *is* a set of cells, because A1 and
  B1 are cells like any other. That difference is real and the corpus
  records it rather than hiding it.
* The **data rows** of both formats are the physical rows from 2 upwards, so
  "the value column, every data row" means the same thing in each.
* A cell that **does not exist** is not the same as a cell that exists and is
  empty, and the two are counted apart.

What this file does not do
--------------------------
It does not test the operators. They do not exist yet (LC-P1-10 T04 and T05),
and this corpus is what they will be tested against. It also does not check
the adapters' *problem records* -- that is LC-P1-08's subject and its tests
already own it.
"""

from __future__ import annotations

import datetime as dt
import math
import statistics
from typing import Any

import pytest
from analysis_fixtures import (
    CORPUS_DIR,
    FIXTURE_NAMES,
    SPREADSHEET_SOURCES,
    build_spreadsheet_fixtures,
    expected_path,
    load_expected,
    read_table_csv,
    write_table_csv,
)

from labcairn.evidence.checks.c3 import read_number
from labcairn.material.ingest import ingest_bytes
from labcairn.sources.locators import CsvLocator, XlsxLocator

NOW = dt.datetime(2026, 10, 19, tzinfo=dt.UTC)

#: Every fixture the corpus holds, committed and derived.
ALL_FIXTURES: tuple[str, ...] = FIXTURE_NAMES + tuple(sorted(SPREADSHEET_SOURCES))


def _column_letter(ref: str) -> str:
    return "".join(ch for ch in ref if ch.isalpha())


def _row_number(ref: str) -> int:
    digits = "".join(ch for ch in ref if ch.isdigit())
    return int(digits)


def _ingest(name: str, data: bytes) -> dict[tuple[int, str], str]:
    """The cells of one fixture, addressed by (physical row, header text).

    This is the corpus's addressing contract, written once so that every
    assertion below reads the same way.
    """
    material = ingest_bytes(data, relative_path=name, display_name=name, ingested_at=NOW)
    cells: dict[tuple[int, str], str] = {}
    if name.endswith(".csv"):
        for text in material.texts:
            locator = text.locator
            assert isinstance(locator, CsvLocator), (
                f"{name} produced a {type(locator).__name__}, which is not a CSV locator"
            )
            cells[(locator.row, locator.column)] = text.text
        return cells

    by_ref: dict[str, tuple[int, str]] = {}
    for text in material.texts:
        locator = text.locator
        assert isinstance(locator, XlsxLocator), (
            f"{name} produced a {type(locator).__name__}, which is not a spreadsheet locator"
        )
        by_ref[locator.cell_ref] = (_row_number(locator.cell_ref), text.text)
    header_by_letter = {
        _column_letter(ref): value for ref, (row, value) in by_ref.items() if row == 1
    }
    for ref, (row, value) in by_ref.items():
        # The header row is included on purpose. A spreadsheet's A1 and B1 are
        # cells like any other, and the corpus records that as a difference
        # from the CSV rather than hiding it.
        header = header_by_letter.get(_column_letter(ref))
        if header is not None:
            cells[(row, header)] = value
    return cells


def _rows(spec: Any) -> list[int]:
    """The rows a selection names: a range string, or a list of numbers."""
    if isinstance(spec, str):
        start, _, end = spec.partition("-")
        return list(range(int(start), int(end) + 1))
    return [int(r) for r in spec]


def _classify(
    cells: dict[tuple[int, str], str], rows: list[int], columns: list[str]
) -> tuple[list[list[Any]], list[list[Any]], list[list[Any]], list[float], list[str]]:
    """Split the cells a selection names into absent, empty, unusable and used.

    Returns the three inventories and the values and units of the cells that
    do carry a quantity.
    """
    absent: list[list[Any]] = []
    empty: list[list[Any]] = []
    not_a_quantity: list[list[Any]] = []
    values: list[float] = []
    units: list[str] = []

    for row in rows:
        for column in columns:
            key = (row, column)
            if key not in cells:
                absent.append([row, column])
                continue
            text = cells[key]
            if not text.strip():
                empty.append([row, column])
                continue
            reading = read_number(text)
            if reading.value is None:
                not_a_quantity.append([row, column])
                continue
            values.append(reading.value)
            if reading.unit is not None:
                units.append(reading.unit)
    return absent, empty, not_a_quantity, values, units


def _statistics(values: list[float]) -> dict[str, Any] | None:
    """The statistics of a list of values, or ``None`` when there are none.

    Python's :mod:`statistics` throughout, and nothing from LabCairn — the
    expectation has to be computed by something that can disagree with the
    operators, or it is not an expectation at all.
    """
    if not values:
        return None
    out: dict[str, Any] = {
        "sum": math.fsum(values),
        "min": min(values),
        "max": max(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "stdev_population": statistics.pstdev(values),
    }
    try:
        out["stdev_sample"] = statistics.stdev(values)
    except statistics.StatisticsError:
        # One value has no sample standard deviation. That is UNDEFINED, and
        # it is not 0.0 — ADR-0004 A8, and the reason `single.csv` exists.
        out["stdev_sample"] = None
    return out


def _fixture_bytes(name: str) -> bytes:
    if name in SPREADSHEET_SOURCES:
        return build_spreadsheet_fixtures()[name]
    return (CORPUS_DIR / name).read_bytes()


def _assert_statistics_close(
    actual: dict[str, Any] | None, expected: dict[str, Any] | None, tolerance: float
) -> None:
    """Compare two sets of statistics, within the fixture's tolerance.

    A tolerance rather than exact equality, and the reason is worth stating:
    a mean is a division, and ``sum / n`` and ``math.fsum(values) / n`` are
    not always the same double. The operators will pick a summation; this
    corpus does not forbid one. What it forbids is a result that differs
    from the data by more than the stated tolerance.
    """
    if expected is None:
        assert actual is None, f"expected no statistics at all, got {actual!r}"
        return
    assert actual is not None, "expected statistics, got none"
    for key, wanted in expected.items():
        assert key in actual, f"the statistics have no {key!r}"
        got = actual[key]
        if wanted is None:
            assert got is None, f"{key} should be undefined, got {got!r}"
            continue
        assert got is not None, f"{key} should be {wanted!r}, got nothing"
        assert math.isclose(got, wanted, rel_tol=0.0, abs_tol=tolerance), (
            f"{key} is {got!r}, the expected values say {wanted!r}, and the "
            f"difference is larger than the tolerance {tolerance!r}"
        )


@pytest.mark.unit
def test_every_fixture_has_expected_values_and_every_expected_file_names_a_fixture() -> None:
    """The corpus has no holes in it.

    A fixture with no expected values is a fixture nothing is measured
    against, and an expected file naming a fixture that does not exist is a
    promise nothing keeps. Both are invisible until somebody counts.
    """
    for name in ALL_FIXTURES:
        path = expected_path(name)
        assert path.is_file(), (
            f"{name} has no expected values: {path} does not exist. Every "
            f"fixture needs them, because a fixture nothing is measured "
            f"against is not a fixture."
        )
        payload = load_expected(name)
        assert payload["fixture"] == name, (
            f"{path.name} says it describes {payload['fixture']!r}, not {name!r}"
        )

    for path in sorted(CORPUS_DIR.glob("*.expected.json")):
        named = path.name.removesuffix(".expected.json")
        assert named in ALL_FIXTURES, (
            f"{path.name} names {named!r}, which is not a fixture of this corpus"
        )
        payload = load_expected(named)
        assert payload["fixture"] == named, (
            f"{path.name} says it describes {payload['fixture']!r}, not {named!r}"
        )


@pytest.mark.unit
@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_a_committed_fixture_is_in_the_canonical_form(name: str) -> None:
    """A fixture is written the same way every time.

    Not cosmetic. The corpus is read by two adapters that each have their own
    rules about quoting and line endings, and a fixture that is written in a
    different shape from the others is a fixture whose behaviour nobody can
    predict. The round trip is the check, and the failure says how to fix it.
    """
    raw = (CORPUS_DIR / name).read_bytes()
    table = read_table_csv(raw)
    canonical = write_table_csv(table)
    assert raw == canonical, (
        f"{name} is not in the canonical form. It is {len(raw)} bytes and the "
        f"canonical rendering is {len(canonical)}. Write it with "
        f"analysis_fixtures.write_table_csv so that every fixture in the "
        f"corpus is written one way."
    )


@pytest.mark.unit
@pytest.mark.parametrize("name", ALL_FIXTURES)
def test_a_fixture_ingests_to_the_cells_its_expected_values_describe(name: str) -> None:
    """The cells that exist, the ones that are empty, and the ones that are absent.

    These are three different facts and the corpus keeps them apart, because
    collapsing them is how a missing measurement becomes a zero.
    """
    payload = load_expected(name)
    cells = _ingest(name, _fixture_bytes(name))
    tolerance = float(payload["tolerance"])

    header_is_addressable = any(row == 1 for row, _ in cells)
    assert header_is_addressable is bool(payload["header_cells"]), (
        f"{name}: whether the header row is a set of addressable cells is "
        f"{header_is_addressable}, the expected values say {payload['header_cells']!r}"
    )

    for selection in payload["selections"]:
        rows = _rows(selection["rows"])
        columns = list(selection["columns"])
        expect = selection["expect"]
        if expect["outcome"] == "refused":
            continue
        absent, empty, not_a_quantity, _values, _units = _classify(cells, rows, columns)
        assert absent == [list(p) for p in expect["absent"]], (
            f"{name}, selection {selection['name']!r}: the absent cells are "
            f"{absent!r}, the expected values say {expect['absent']!r}"
        )
        assert empty == [list(p) for p in expect["empty"]], (
            f"{name}, selection {selection['name']!r}: the empty cells are "
            f"{empty!r}, the expected values say {expect['empty']!r}"
        )
        assert not_a_quantity == [list(p) for p in expect["not_a_quantity"]], (
            f"{name}, selection {selection['name']!r}: the cells that are not "
            f"quantities are {not_a_quantity!r}, the expected values say "
            f"{expect['not_a_quantity']!r}"
        )
        assert tolerance > 0


@pytest.mark.unit
@pytest.mark.parametrize("name", ALL_FIXTURES)
def test_a_fixture_ingests_to_the_statistics_its_expected_values_state(name: str) -> None:
    """The numbers in the expected values are the numbers of the data.

    Computed here by Python's :mod:`statistics`, which is not LabCairn's
    code, so this is a real comparison and not an echo.
    """
    payload = load_expected(name)
    cells = _ingest(name, _fixture_bytes(name))
    tolerance = float(payload["tolerance"])

    for selection in payload["selections"]:
        expect = selection["expect"]
        if expect["outcome"] == "refused":
            continue
        rows = _rows(selection["rows"])
        columns = list(selection["columns"])
        _absent, _empty, _not_a_quantity, values, units = _classify(cells, rows, columns)
        _assert_statistics_close(_statistics(values), expect["statistics"], tolerance)
        if expect["unit"] is not None:
            assert units and set(units) == {expect["unit"]}, (
                f"{name}, selection {selection['name']!r}: the cells carry the "
                f"units {sorted(set(units))!r}, the expected values say "
                f"{expect['unit']!r}"
            )


@pytest.mark.unit
@pytest.mark.parametrize("name", ALL_FIXTURES)
def test_a_fixture_groups_the_way_its_expected_values_state(name: str) -> None:
    """The grouped aggregates are the aggregates of the groups.

    The group list is sorted, and a group whose members carry no quantity has
    **no statistics** rather than statistics of nothing.
    """
    payload = load_expected(name)
    cells = _ingest(name, _fixture_bytes(name))
    tolerance = float(payload["tolerance"])
    grouped = payload["grouped"]
    by, of = grouped["by"], grouped["of"]

    buckets: dict[str, list[int]] = {}
    for row in sorted({r[0] for r in cells if r[0] > 1}):
        key = cells.get((row, by))
        if key is None:
            continue
        buckets.setdefault(key, []).append(row)

    expected_groups = grouped["groups"]
    assert [g["key"] for g in expected_groups] == sorted(buckets), (
        f"{name}: the groups are {[g['key'] for g in expected_groups]!r}, the "
        f"data has {sorted(buckets)!r}"
    )

    for group in expected_groups:
        rows = _rows(group["rows"])
        _absent, _empty, _not_a_quantity, values, units = _classify(cells, rows, [of])
        _assert_statistics_close(_statistics(values), group["statistics"], tolerance)
        if group["statistics"] is None:
            assert group["unit"] is None, (
                f"{name}, group {group['key']!r}: a group with no statistics cannot have a unit"
            )
        elif group["unit"] is not None:
            assert units and set(units) == {group["unit"]}, (
                f"{name}, group {group['key']!r}: the cells carry the units "
                f"{sorted(set(units))!r}, the expected values say {group['unit']!r}"
            )


@pytest.mark.unit
def test_a_refused_selection_really_carries_more_than_one_unit_token() -> None:
    """The refusal is verified, not asserted.

    A corpus that says "this selection is refused" without saying *why* is a
    promise with nothing behind it, and nothing would notice if a selection
    started being refused for a different reason.
    """
    payload = load_expected("units.csv")
    cells = _ingest("units.csv", (CORPUS_DIR / "units.csv").read_bytes())

    refused = [s for s in payload["selections"] if s["expect"]["outcome"] == "refused"]
    assert refused, "units.csv is supposed to contain a refused selection"

    for selection in refused:
        rows = _rows(selection["rows"])
        columns = list(selection["columns"])
        _absent, _empty, _not_a_quantity, _values, units = _classify(cells, rows, columns)
        assert len(set(units)) > 1, (
            f"the selection {selection['name']!r} is expected to be refused "
            f"for holding more than one unit token, and it holds {sorted(set(units))!r}"
        )


@pytest.mark.unit
def test_the_spreadsheet_fixture_carries_the_same_characters_as_its_csv() -> None:
    """The two formats hold the same text, cell for cell.

    This is what makes the two paths comparable at all. The generator writes
    the CSV's own text into the spreadsheet rather than re-typing the values
    as numbers, so a difference between the two paths is the adapter's and
    not the writer's.
    """
    for name, source in SPREADSHEET_SOURCES.items():
        sheet_cells = _ingest(name, build_spreadsheet_fixtures()[name])
        csv_cells = _ingest(source, (CORPUS_DIR / source).read_bytes())
        for key, text in csv_cells.items():
            if not text.strip():
                # An empty cell is the one place the two may differ, and
                # `test_an_empty_cell_is_a_cell_in_a_csv_and_nothing_in_a_spreadsheet`
                # is what holds that difference down.
                continue
            assert sheet_cells.get(key) == text, (
                f"{name} holds {sheet_cells.get(key)!r} at {key!r} and "
                f"{source} holds {text!r}. The two fixtures are the same table "
                f"and must carry the same characters."
            )


@pytest.mark.unit
def test_an_empty_cell_is_a_cell_in_a_csv_and_nothing_in_a_spreadsheet() -> None:
    """The asymmetry the corpus was built to show, pinned in the data.

    ``holes.csv`` and ``holes.xlsx`` are the same table with one value cell
    emptied. The CSV keeps the cell and it is empty; the spreadsheet has no
    cell at all, because its adapter does not extract an empty one. The
    selection's statistics are therefore the same and the inventory is not,
    and a table's rectangular extent is not recoverable from the ledger for a
    spreadsheet.
    """
    csv_cells = _ingest("holes.csv", (CORPUS_DIR / "holes.csv").read_bytes())
    sheet_cells = _ingest("holes.xlsx", build_spreadsheet_fixtures()["holes.xlsx"])

    assert (4, "value") in csv_cells, "holes.csv should keep the emptied cell"
    assert csv_cells[(4, "value")] == "", "the CSV's emptied cell should be empty"
    assert (4, "value") not in sheet_cells, (
        "holes.xlsx should have no cell at all where the CSV has an empty one. "
        "That difference is the point of the fixture: the spreadsheet adapter "
        "does not extract an empty cell, so a spreadsheet's extent is not "
        "recoverable from the ledger."
    )
    assert (4, "group") in sheet_cells, "the row itself is still there"


@pytest.mark.unit
def test_the_header_row_is_addressable_in_a_spreadsheet_and_not_in_a_csv() -> None:
    """A second difference between the two paths, and it is a real one.

    In a spreadsheet the header is row 1 and A1 and B1 are cells like any
    other. In a CSV the header names the columns and is not itself a set of
    cells. A selection that took "the whole column" would therefore see two
    extra cells in one format and none in the other.
    """
    csv_cells = _ingest("basic.csv", (CORPUS_DIR / "basic.csv").read_bytes())
    sheet_cells = _ingest("numeric.xlsx", build_spreadsheet_fixtures()["numeric.xlsx"])

    assert not any(row == 1 for row, _ in csv_cells), (
        "the CSV's header row should not be a set of cells"
    )
    assert (1, "group") in sheet_cells, (
        "the spreadsheet's header row should be addressable, because A1 and B1 "
        "are cells like any other"
    )


@pytest.mark.unit
def test_a_column_that_declares_a_unit_declares_it() -> None:
    """``mass (kg)`` declares ``kg``, and the declaration is recorded.

    The header is the only place a real table usually states a unit, so a
    check that only ever looked at cell text would find no unit to check and
    pass vacuously.
    """
    payload = load_expected("typed.csv")
    assert payload["declared_units"] == {"mass (kg)": "kg"}, (
        f"typed.csv declares {payload['declared_units']!r}, and the header says 'mass (kg)'"
    )
    cells = _ingest("typed.csv", (CORPUS_DIR / "typed.csv").read_bytes())
    assert (2, "mass (kg)") in cells, "the column is addressed by its header text"


@pytest.mark.unit
def test_the_reference_case_matches_its_closed_forms() -> None:
    """The numbers in the reference case are checkable by hand.

    A mean of 5.5, a median of 5.5, a population standard deviation of
    sqrt(8.25) and a sample one of sqrt(82.5/9). If a program and a person
    disagree about the reference case, one of them is wrong, and this is the
    place where that is cheapest to find out.
    """
    payload = load_expected("basic.csv")
    expect = payload["selections"][0]["expect"]
    statistics_expected = expect["statistics"]
    assert statistics_expected is not None
    assert statistics_expected["mean"] == 5.5
    assert statistics_expected["median"] == 5.5
    assert math.isclose(
        statistics_expected["stdev_population"], math.sqrt(8.25), rel_tol=0.0, abs_tol=1e-12
    )
    assert math.isclose(
        statistics_expected["stdev_sample"], math.sqrt(82.5 / 9), rel_tol=0.0, abs_tol=1e-12
    )


@pytest.mark.unit
def test_a_fixture_whose_group_has_no_quantity_has_no_statistics_for_it() -> None:
    """An empty group is undefined, not zero.

    ``missing.csv``'s group B holds an empty cell and a cell that is not a
    number, and nothing else. Its aggregate is therefore undefined, and the
    expected values say so with a null rather than a zero — ADR-0004 A8, in
    the corpus rather than only in prose.
    """
    payload = load_expected("missing.csv")
    groups = {g["key"]: g for g in payload["grouped"]["groups"]}
    assert "B" in groups, "missing.csv should have a group B"
    assert groups["B"]["statistics"] is None, (
        "group B holds no quantity, so its aggregate is undefined and must be null rather than 0"
    )
    assert groups["B"]["unit"] is None, "a group with no statistics has no unit"
    assert groups["A"]["statistics"] is not None, "group A holds three quantities"
