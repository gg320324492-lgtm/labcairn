"""The grouped aggregate, and the table it produces.

LC-P1-10's corpus is this file's fixture, and it is the same statement the
operators are checked against: the expected values say what each fixture
contains and what the numbers over it are, so an operator that computes
something else is caught against data rather than against a golden file the
operator could have written.

Six things are under test, and the last two are the ones that are easiest to
get wrong:

* the **numbers** — each group's statistic is the corpus's statistic;
* the **table** — one row per group, sorted, with the group key as written;
* the **undefined** — a group with no quantity has no statistic, and it is
  never ``0``;
* the **units** — checked per group, so a file that holds two unit tokens
  across its groups is fine, and a group that holds two is refused;
* the **disclosure** — the rows the filter removed and the rows the
  missing-value policy removed are both reported;
* the **composition** — the grouped statistic is the scalar operator's
  statistic over that group's rows, and not a reimplementation of it.

The refusals are here too, because a refusal that names what is wrong is half
of what this operator is for.
"""

from __future__ import annotations

from typing import Any, Final

import pytest
from analysis_fixtures import corpus_selection, corpus_source, load_expected, row_numbers
from pydantic import BaseModel, ConfigDict, ValidationError

from labcairn.analysis import catalog
from labcairn.analysis.catalog import is_registered_operator, operator_for, operator_version
from labcairn.analysis.operators import Operator, RegisteredOperator
from labcairn.analysis.operators.descriptive import DescriptiveArgs, StatisticResult, mean
from labcairn.analysis.operators.grouped import (
    AGGREGATE,
    GroupAggregate,
    GroupedArgs,
    GroupedRefusedError,
    GroupedResult,
    aggregate,
)
from labcairn.analysis.selection import (
    FilterOp,
    MissingPolicy,
    RowFilter,
    RowSelection,
    RowSet,
    Selection,
    SelectionRefusedError,
)
from labcairn.analysis.units import UnitDisagreementError
from labcairn.analysis.values import CellAddress, ValueSource
from labcairn.sources.locators import LocatorKind

#: Every fixture the corpus gives a grouped section for.
GROUPED_FIXTURES: Final[tuple[str, ...]] = (
    "basic.csv",
    "empty.csv",
    "groups.csv",
    "holes.csv",
    "holes.xlsx",
    "missing.csv",
    "numeric.xlsx",
    "single.csv",
    "typed.csv",
    "units.csv",
)

#: The aggregates, and the corpus's name for the statistic each one computes.
#:
#: ``stdev`` appears twice because the corpus states both deviations, and
#: because which population is meant is a choice the caller has to make rather
#: than a default the operator may pick.
AGGREGATES: Final[tuple[tuple[str, dict[str, int], str], ...]] = (
    ("labcairn.analysis.sum@1.0.0", {}, "sum"),
    ("labcairn.analysis.min@1.0.0", {}, "min"),
    ("labcairn.analysis.max@1.0.0", {}, "max"),
    ("labcairn.analysis.mean@1.0.0", {}, "mean"),
    ("labcairn.analysis.median@1.0.0", {}, "median"),
    ("labcairn.analysis.stdev@1.0.0", {"ddof": 0}, "stdev_population"),
    ("labcairn.analysis.stdev@1.0.0", {"ddof": 1}, "stdev_sample"),
)


def _grouped_selection(
    fixture: str, payload: dict[str, Any], described: dict[str, Any]
) -> Selection:
    """The selection a grouped section describes.

    The corpus's own reader builds a selection over the columns a *selection*
    names, and a grouped aggregate needs two of them: the column the groups
    are named by and the column the statistic is computed over. The rows are
    the ones the fixture's first selection names, because that is the run of
    rows the corpus's grouped section describes.
    """
    selection: Selection = corpus_selection(
        fixture, {"rows": described["rows"], "columns": payload["columns"]}
    )
    return selection


def _args(
    fixture: str,
    payload: dict[str, Any],
    described: dict[str, Any],
    reference: str,
    parameters: dict[str, int],
) -> GroupedArgs:
    selection = _grouped_selection(fixture, payload, described)
    return GroupedArgs(
        selection=selection,
        aggregate=reference,
        by=payload["grouped"]["by"],
        of=payload["grouped"]["of"],
        aggregate_parameters=dict(parameters),
    )


class _InlineSource:
    """A cell source over a table written out in the test.

    The corpus holds the data cases; these are the cases that are about the
    *selection* rather than about a table -- a row filter that empties a
    group, a group key that is the empty string, a group whose own cells
    carry two unit tokens. A fixture could hold them, but then the fixture
    would be about the selection and not about the data, and the corpus's
    promise is that every fixture's expected values were computed by hand.
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


def _inline_selection(
    columns: tuple[str, ...],
    rows: RowSelection,
    missing: MissingPolicy = MissingPolicy.EXCLUDE,
) -> Selection:
    return Selection(
        source_id="inline.csv",
        content_sha256="a" * 64,
        columns=columns,
        rows=rows,
        missing=missing,
    )


@pytest.mark.unit
@pytest.mark.parametrize("fixture", GROUPED_FIXTURES)
@pytest.mark.parametrize(
    ("reference", "parameters", "statistic"), AGGREGATES, ids=[a[2] for a in AGGREGATES]
)
def test_the_grouped_aggregate_computes_what_the_corpus_says(
    fixture: str,
    reference: str,
    parameters: dict[str, int],
    statistic: str,
) -> None:
    """Every group's statistic is the corpus's statistic.

    The corpus's numbers were computed by Python's :mod:`statistics`, which is
    not LabCairn's code, so this is a comparison and not an echo.
    """
    payload = load_expected(fixture)
    described = payload["selections"][0]
    expected = payload["grouped"]
    result = aggregate(
        _args(fixture, payload, described, reference, parameters), corpus_source(fixture)
    )

    assert [group.key for group in result.groups] == [group["key"] for group in expected["groups"]]
    by_key = {group.key: group for group in result.groups}
    for stated in expected["groups"]:
        assert stated["outcome"] == "ok"
        group = by_key[stated["key"]]
        assert group.rows == tuple(row_numbers(stated["rows"]))
        assert group.n_absent == len(stated["absent"])
        assert group.n_empty == len(stated["empty"])
        assert group.n_invalid == len(stated["not_a_quantity"])
        assert group.unit == stated["unit"]
        stated_value = (stated["statistics"] or {}).get(statistic)
        if stated_value is None:
            assert group.value is None
            assert group.undefined_reason
        else:
            assert group.value == pytest.approx(stated_value)
            assert group.undefined_reason is None


@pytest.mark.unit
def test_the_grouped_aggregate_composes_the_scalar_operator() -> None:
    """The grouped statistic is the scalar operator's statistic over that group.

    The grouped operator does not have its own arithmetic: it runs a
    registered operator over each group's rows. So the two must agree exactly,
    and a reimplementation -- a mean of means, or a mean over the group's rows
    rather than over its values -- would show up here as a disagreement.
    """
    payload = load_expected("groups.csv")
    described = payload["selections"][0]
    source = corpus_source("groups.csv")
    result = aggregate(
        _args("groups.csv", payload, described, "labcairn.analysis.mean@1.0.0", {}), source
    )

    for stated in payload["grouped"]["groups"]:
        rows = tuple(row_numbers(stated["rows"]))
        scalar = mean(
            DescriptiveArgs(
                selection=_inline_selection(("value",), RowSet(rows)),
            ),
            source,
        )
        group = next(g for g in result.groups if g.key == stated["key"])
        assert group.value == scalar.value
        assert group.n_used == scalar.n_used


@pytest.mark.unit
def test_a_group_key_is_the_text_as_written() -> None:
    """Keys are compared as written, and the table is sorted by them.

    No case folding, no trimming, and no reading ``10`` as a number: ``a`` and
    ``A`` are two groups, ``" A"`` and ``"A"`` are two groups, and ``10``
    sorts before ``9`` because that is where its characters put it.
    """
    source = _InlineSource(
        {
            (2, "group"): "9",
            (2, "value"): "1",
            (3, "group"): "10",
            (3, "value"): "2",
            (4, "group"): "A",
            (4, "value"): "3",
            (5, "group"): "a",
            (5, "value"): "4",
            (6, "group"): " A",
            (6, "value"): "5",
        }
    )
    result = aggregate(
        GroupedArgs(
            selection=_inline_selection(("group", "value"), RowSet((2, 3, 4, 5, 6))),
            aggregate="labcairn.analysis.mean@1.0.0",
            by="group",
            of="value",
        ),
        source,
    )
    assert [group.key for group in result.groups] == [" A", "10", "9", "A", "a"]
    assert {group.key: group.n_used for group in result.groups} == {
        " A": 1,
        "10": 1,
        "9": 1,
        "A": 1,
        "a": 1,
    }


@pytest.mark.unit
def test_the_empty_key_is_a_group() -> None:
    """A cell that was recorded and holds no text names the empty group.

    Dropping it would change the shape of the answer without saying so, and a
    group the author left unnamed is still a group of the table.
    """
    source = _InlineSource(
        {
            (2, "group"): "",
            (2, "value"): "1",
            (3, "group"): "A",
            (3, "value"): "2",
        }
    )
    result = aggregate(
        GroupedArgs(
            selection=_inline_selection(("group", "value"), RowSet((2, 3))),
            aggregate="labcairn.analysis.mean@1.0.0",
            by="group",
            of="value",
        ),
        source,
    )
    assert [group.key for group in result.groups] == ["", "A"]
    empty = result.groups[0]
    assert empty.rows == (2,)
    assert empty.n_used == 1
    assert empty.value == pytest.approx(1.0)


@pytest.mark.unit
def test_an_empty_group_is_not_representable() -> None:
    """A group exists because a row put it there.

    A filter that removes every row of a group removes the group, and there
    is no way to get a group of nothing back.
    """
    source = _InlineSource(
        {
            (2, "group"): "A",
            (2, "value"): "1",
            (3, "group"): "B",
            (3, "value"): "10",
        }
    )
    result = aggregate(
        GroupedArgs(
            selection=_inline_selection(
                ("group", "value"),
                RowFilter(column="value", op=FilterOp.GT, value="5"),
            ),
            aggregate="labcairn.analysis.mean@1.0.0",
            by="group",
            of="value",
        ),
        source,
    )
    assert [group.key for group in result.groups] == ["B"]
    assert result.n_rows_selected == 1
    assert result.n_rows_filtered == 1


@pytest.mark.unit
def test_a_group_with_no_quantity_has_no_statistic() -> None:
    """It is undefined, and it is not zero.

    The corpus's ``missing.csv`` holds the case: group ``B`` has an empty cell
    and a word in it, so it has no statistic at all, while group ``A`` has one.
    ADR-0004 A8 is about exactly this distinction.
    """
    payload = load_expected("missing.csv")
    described = payload["selections"][0]
    result = aggregate(
        _args("missing.csv", payload, described, "labcairn.analysis.mean@1.0.0", {}),
        corpus_source("missing.csv"),
    )
    by_key = {group.key: group for group in result.groups}
    assert by_key["A"].value == pytest.approx(3.0)
    assert by_key["A"].undefined_reason is None

    empty = by_key["B"]
    assert empty.value is None
    assert empty.undefined_reason
    assert empty.n_used == 0
    assert empty.n_empty == 1
    assert empty.n_invalid == 1
    assert empty.rows == (3, 5)


@pytest.mark.unit
def test_an_undefined_group_blames_the_group_and_not_the_selection() -> None:
    """The reason names the group it is about.

    The aggregate's own reason says "the selection holds no value", and in a
    table of groups "the selection" is the wrong thing to blame: it is *this
    group* that holds no value, and the other groups may hold plenty. A
    reader told the selection was empty would be told something false about
    the selection, and the group that is actually empty would go unnamed.
    """
    payload = load_expected("missing.csv")
    described = payload["selections"][0]
    result = aggregate(
        _args("missing.csv", payload, described, "labcairn.analysis.mean@1.0.0", {}),
        corpus_source("missing.csv"),
    )
    by_key = {group.key: group for group in result.groups}
    reason = by_key["B"].undefined_reason
    assert reason is not None
    assert "B" in reason
    assert "selection" not in reason


@pytest.mark.unit
def test_the_result_reports_the_rows_it_filtered_and_the_rows_it_excluded() -> None:
    """A table of statistics is a claim about a set of rows, and says which.

    The rows the filter removed, the rows the missing-value policy removed,
    and the rows that carried no group key are three different facts, and the
    result says all three.
    """
    payload = load_expected("missing.csv")
    described = payload["selections"][0]
    result = aggregate(
        _args("missing.csv", payload, described, "labcairn.analysis.mean@1.0.0", {}),
        corpus_source("missing.csv"),
    )
    # Six rows are named. Row 7 of the fixture is a blank line with no fields
    # at all, so it carries no group key and is not in any group; rows 3 and 5
    # are in group B but yield no quantity.
    assert result.n_rows_selected == 6
    assert result.n_rows_filtered == 0
    assert result.n_rows_excluded == 2
    assert result.n_rows_ungrouped == 1


@pytest.mark.unit
def test_units_are_checked_per_group_and_not_across_the_selection() -> None:
    """Each group is its own measurement.

    The corpus's ``units.csv`` holds four rows carrying ``kg``, one carrying
    ``g`` and one carrying none. A selection over the whole file is refused by
    the scalar operators, and every group on its own is fine -- the refusal is
    a property of the selection, not of the file.
    """
    payload = load_expected("units.csv")
    described = payload["selections"][0]
    assert described["expect"]["outcome"] == "refused"

    result = aggregate(
        _args("units.csv", payload, described, "labcairn.analysis.mean@1.0.0", {}),
        corpus_source("units.csv"),
    )
    by_key = {group.key: group for group in result.groups}
    assert by_key["A"].unit == "kg"
    assert by_key["B"].unit == "kg"
    assert by_key["C"].unit == "g"
    assert by_key["D"].unit is None
    assert by_key["C"].value == pytest.approx(3500.0)


@pytest.mark.unit
def test_a_group_with_two_unit_tokens_is_refused() -> None:
    """A group's own cells must agree about their unit.

    Units are compared as written and never converted, so a group that would
    need a unit algebra to be reconciled is one this build cannot compute, and
    the refusal names both tokens so the reader can see what the check did not
    do.
    """
    source = _InlineSource(
        {
            (2, "group"): "A",
            (2, "value"): "1 kg",
            (3, "group"): "A",
            (3, "value"): "2 g",
        }
    )
    with pytest.raises(UnitDisagreementError) as raised:
        aggregate(
            GroupedArgs(
                selection=_inline_selection(("group", "value"), RowSet((2, 3))),
                aggregate="labcairn.analysis.mean@1.0.0",
                by="group",
                of="value",
            ),
            source,
        )
    assert "kg" in str(raised.value)
    assert "g" in str(raised.value)


@pytest.mark.unit
def test_an_aggregate_that_names_no_registered_operator_is_refused() -> None:
    """The catalogue is how the aggregate is looked up.

    An aggregate this build does not implement cannot be run, and it cannot
    quietly become one that it can.
    """
    with pytest.raises(GroupedRefusedError) as raised:
        aggregate(
            GroupedArgs(
                selection=_inline_selection(("group", "value"), RowSet((2,))),
                aggregate="labcairn.analysis.median_of_a_median@1.0.0",
                by="group",
                of="value",
            ),
            _InlineSource({(2, "group"): "A", (2, "value"): "1"}),
        )
    assert "labcairn.analysis.median_of_a_median" in str(raised.value)


@pytest.mark.unit
def test_an_aggregate_that_is_not_an_operator_reference_is_refused() -> None:
    """A bare name is not a reference, and a reference is what the manifest quotes."""
    with pytest.raises(GroupedRefusedError) as raised:
        aggregate(
            GroupedArgs(
                selection=_inline_selection(("group", "value"), RowSet((2,))),
                aggregate="mean",
                by="group",
                of="value",
            ),
            _InlineSource({(2, "group"): "A", (2, "value"): "1"}),
        )
    assert "labcairn.analysis.mean@1.0.0" in str(raised.value)


@pytest.mark.unit
def test_an_aggregate_whose_version_the_catalogue_does_not_hold_is_refused() -> None:
    """A reference that names a version this build does not have is refused.

    The catalogue knows which version is current; a manifest records which
    version ran. Running ``mean@2.0.0`` against ``mean@1.0.0`` would make the
    manifest a false claim.
    """
    with pytest.raises(GroupedRefusedError) as raised:
        aggregate(
            GroupedArgs(
                selection=_inline_selection(("group", "value"), RowSet((2,))),
                aggregate="labcairn.analysis.mean@2.0.0",
                by="group",
                of="value",
            ),
            _InlineSource({(2, "group"): "A", (2, "value"): "1"}),
        )
    assert "2.0.0" in str(raised.value)
    assert "1.0.0" in str(raised.value)


@pytest.mark.unit
def test_an_aggregate_that_is_not_an_operator_over_a_selection_is_refused() -> None:
    """The grouped operator cannot be its own aggregate.

    It is registered, and it is not an operator over a selection, so naming
    it is a refusal rather than a recursion.
    """
    with pytest.raises(GroupedRefusedError) as raised:
        aggregate(
            GroupedArgs(
                selection=_inline_selection(("group", "value"), RowSet((2,))),
                aggregate="labcairn.analysis.grouped_aggregate@1.0.0",
                by="group",
                of="value",
            ),
            _InlineSource({(2, "group"): "A", (2, "value"): "1"}),
        )
    assert "not an operator over a selection" in str(raised.value)


@pytest.mark.unit
def test_an_aggregate_with_a_parameter_it_does_not_take_is_refused() -> None:
    """The aggregate's own argument model is the only place its shape is written.

    A parameter it does not take is a refusal, not a silently ignored key, and
    a parameter it needs and did not get is a refusal too: ``stdev`` divides
    by ``n-1``, and a run that did not say which population it meant would be
    making that choice silently.
    """
    source = _InlineSource({(2, "group"): "A", (2, "value"): "1"})
    with pytest.raises(GroupedRefusedError) as raised:
        aggregate(
            GroupedArgs(
                selection=_inline_selection(("group", "value"), RowSet((2,))),
                aggregate="labcairn.analysis.mean@1.0.0",
                by="group",
                of="value",
                aggregate_parameters={"ddof": 0},
            ),
            source,
        )
    assert "ddof" in str(raised.value)

    with pytest.raises(GroupedRefusedError) as raised:
        aggregate(
            GroupedArgs(
                selection=_inline_selection(("group", "value"), RowSet((2,))),
                aggregate="labcairn.analysis.stdev@1.0.0",
                by="group",
                of="value",
            ),
            source,
        )
    assert "ddof" in str(raised.value)


@pytest.mark.unit
def test_an_aggregate_with_a_bad_parameter_is_refused_even_when_the_table_is_empty() -> None:
    """The arguments are checked before the table, not after it.

    A table with no groups would otherwise never reach the check, and the
    request would be accepted silently.
    """
    payload = load_expected("empty.csv")
    described = payload["selections"][0]
    with pytest.raises(GroupedRefusedError):
        aggregate(
            _args("empty.csv", payload, described, "labcairn.analysis.stdev@1.0.0", {}),
            corpus_source("empty.csv"),
        )


@pytest.mark.unit
def test_an_aggregate_that_does_not_produce_a_statistic_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The catalogue is code, and this is what an entry that lies looks like.

    An operator whose declared result model is a statistic but whose run
    returns something else cannot be read as a statistic, and the refusal
    says so rather than raising something a caller cannot act on.
    """

    class _NotAStatistic(BaseModel):
        model_config = ConfigDict(extra="forbid", frozen=True)

        value: float

    def _run(args: DescriptiveArgs, source: ValueSource) -> _NotAStatistic:
        return _NotAStatistic(value=1.0)

    liar = RegisteredOperator[Any, Any](
        operator=Operator[Any, Any](
            operator_id="labcairn.analysis.liar",
            operator_version="1.0.0",
            args_model=DescriptiveArgs,
            result_model=StatisticResult,
            accepted_locator_kinds=frozenset({LocatorKind.CSV}),
            summary="an operator that does not do what it declares",
        ),
        run=_run,
    )
    monkeypatch.setattr(catalog, "OPERATORS", frozenset({liar}))

    with pytest.raises(GroupedRefusedError) as raised:
        aggregate(
            GroupedArgs(
                selection=_inline_selection(("group", "value"), RowSet((2,))),
                aggregate="labcairn.analysis.liar@1.0.0",
                by="group",
                of="value",
            ),
            _InlineSource({(2, "group"): "A", (2, "value"): "1"}),
        )
    assert "rather than a statistic" in str(raised.value)


@pytest.mark.unit
def test_a_refused_selection_refuses_the_grouped_aggregate() -> None:
    """The missing-value policy is the caller's, and it bites.

    A cell that yields no quantity is a hole, and under the ``REFUSE`` policy
    a statistic over a selection with holes is a statistic over something the
    caller did not ask for.
    """
    selection = Selection(
        source_id="missing.csv",
        content_sha256="a" * 64,
        columns=("group", "value"),
        rows=RowSet((2, 3, 4, 5, 6)),
        missing=MissingPolicy.REFUSE,
    )
    with pytest.raises(SelectionRefusedError):
        aggregate(
            GroupedArgs(
                selection=selection,
                aggregate="labcairn.analysis.mean@1.0.0",
                by="group",
                of="value",
            ),
            corpus_source("missing.csv"),
        )


@pytest.mark.unit
def test_a_refused_selection_refuses_the_grouped_aggregate_even_for_an_ungrouped_row() -> None:
    """The policy reaches every named row's value cell.

    A row that carries no group key is in no group, so no group's own resolve
    covers it. The policy still has to reach it, or a hole in the measured
    column would slip through a ``REFUSE`` selection without a word.
    """
    source = _InlineSource(
        {
            (2, "group"): "A",
            (2, "value"): "1",
            (3, "value"): "",
        }
    )
    with pytest.raises(SelectionRefusedError):
        aggregate(
            GroupedArgs(
                selection=_inline_selection(
                    ("group", "value"), RowSet((2, 3)), missing=MissingPolicy.REFUSE
                ),
                aggregate="labcairn.analysis.mean@1.0.0",
                by="group",
                of="value",
            ),
            source,
        )


@pytest.mark.unit
def test_a_row_with_no_group_key_is_ungrouped_rather_than_refused() -> None:
    """The missing-value policy is about quantities, and a group key is not one.

    The cost of that reading is stated here rather than hidden: a ``REFUSE``
    selection can still leave rows out of the table, and the result says how
    many in ``n_rows_ungrouped``.
    """
    source = _InlineSource(
        {
            (2, "group"): "A",
            (2, "value"): "1",
            (3, "value"): "2",
        }
    )
    result = aggregate(
        GroupedArgs(
            selection=_inline_selection(
                ("group", "value"), RowSet((2, 3)), missing=MissingPolicy.REFUSE
            ),
            aggregate="labcairn.analysis.mean@1.0.0",
            by="group",
            of="value",
        ),
        source,
    )
    assert [group.key for group in result.groups] == ["A"]
    assert result.n_rows_selected == 2
    assert result.n_rows_ungrouped == 1


@pytest.mark.unit
def test_the_grouped_operator_refuses_a_column_the_selection_does_not_name() -> None:
    """Both columns are named by the selection, and neither by index."""
    with pytest.raises(ValidationError) as raised:
        GroupedArgs(
            selection=_inline_selection(("value",), RowSet((2,))),
            aggregate="labcairn.analysis.mean@1.0.0",
            by="group",
            of="value",
        )
    assert "group" in str(raised.value)


@pytest.mark.unit
def test_the_grouped_operator_refuses_grouping_by_the_column_it_measures() -> None:
    """A group cannot be its own measurement."""
    with pytest.raises(ValidationError) as raised:
        GroupedArgs(
            selection=_inline_selection(("value",), RowSet((2,))),
            aggregate="labcairn.analysis.mean@1.0.0",
            by="value",
            of="value",
        )
    assert "same column" in str(raised.value)


@pytest.mark.unit
def test_the_aggregate_parameters_may_not_carry_a_selection() -> None:
    """A parameter that replaced the selection would measure something else."""
    with pytest.raises(ValidationError) as raised:
        GroupedArgs(
            selection=_inline_selection(("group", "value"), RowSet((2,))),
            aggregate="labcairn.analysis.mean@1.0.0",
            by="group",
            of="value",
            aggregate_parameters={"selection": "elsewhere"},
        )
    assert "selection" in str(raised.value)


@pytest.mark.unit
def test_a_group_is_either_a_value_or_undefined_with_a_reason() -> None:
    """The two are not separable, and the model says so.

    A value with no reason hides an unknown, and a reason with no value says
    nothing.
    """
    with pytest.raises(ValidationError):
        GroupAggregate(
            key="A",
            rows=(2,),
            n_used=0,
            n_empty=0,
            n_absent=0,
            n_invalid=0,
            value=None,
            undefined_reason=None,
            unit=None,
        )


@pytest.mark.unit
def test_the_counts_and_the_table_must_agree() -> None:
    """A result cannot say one thing and show another.

    The disclosure and the table are the same fact, and the model refuses a
    result in which they are not.
    """
    with pytest.raises(ValidationError) as raised:
        GroupedResult(
            operator_id="labcairn.analysis.grouped_aggregate",
            operator_version="1.0.0",
            aggregate="labcairn.analysis.mean@1.0.0",
            by="group",
            of="value",
            groups=(
                GroupAggregate(
                    key="A",
                    rows=(2,),
                    n_used=1,
                    n_empty=0,
                    n_absent=0,
                    n_invalid=0,
                    value=1.0,
                    undefined_reason=None,
                    unit=None,
                ),
            ),
            n_rows_selected=5,
            n_rows_filtered=0,
            n_rows_excluded=0,
            n_rows_ungrouped=0,
            selection=_inline_selection(("group", "value"), RowSet((2,))),
        )
    assert "counted exactly once" in str(raised.value)


@pytest.mark.unit
def test_the_groups_must_be_sorted_and_distinct() -> None:
    """Two runs over the same rows must produce the same table in the same order.

    The model refuses a result whose groups are not sorted, and a key that
    appears twice is one group written down twice.
    """
    group = GroupAggregate(
        key="A",
        rows=(2,),
        n_used=1,
        n_empty=0,
        n_absent=0,
        n_invalid=0,
        value=1.0,
        undefined_reason=None,
        unit=None,
    )
    with pytest.raises(ValidationError) as raised:
        GroupedResult(
            operator_id="labcairn.analysis.grouped_aggregate",
            operator_version="1.0.0",
            aggregate="labcairn.analysis.mean@1.0.0",
            by="group",
            of="value",
            groups=(group, group),
            n_rows_selected=1,
            n_rows_filtered=0,
            n_rows_excluded=0,
            n_rows_ungrouped=0,
            selection=_inline_selection(("group", "value"), RowSet((2,))),
        )
    assert "neither sorted nor free of repeats" in str(raised.value)


@pytest.mark.unit
def test_the_result_carries_its_operator_and_version_and_selection() -> None:
    """A result says which operator produced it, and what it ran over.

    A manifest quotes the operator by name, and a result that did not say its
    own version could not be compared with the manifest beside it.
    """
    payload = load_expected("basic.csv")
    described = payload["selections"][0]
    args = _args("basic.csv", payload, described, "labcairn.analysis.mean@1.0.0", {})
    result = aggregate(args, corpus_source("basic.csv"))
    assert result.operator_id == "labcairn.analysis.grouped_aggregate"
    assert result.operator_version == "1.0.0"
    assert result.aggregate == "labcairn.analysis.mean@1.0.0"
    assert result.by == "group"
    assert result.of == "value"
    assert result.selection == args.selection


@pytest.mark.unit
def test_the_grouped_aggregate_is_registered() -> None:
    """The catalogue holds the operator this build implements.

    A run can only ever name an operator the catalogue holds, and the
    catalogue is built from the operator modules' own constants, so this
    cannot drift from the implementation.
    """
    assert is_registered_operator("labcairn.analysis.grouped_aggregate") is True
    assert operator_for("labcairn.analysis.grouped_aggregate") is AGGREGATE
    assert operator_version("labcairn.analysis.grouped_aggregate") == "1.0.0"
    assert AGGREGATE.operator.args_model is GroupedArgs
    assert AGGREGATE.operator.result_model is GroupedResult
    assert AGGREGATE.operator.accepted_locator_kinds
    assert AGGREGATE.operator.summary
