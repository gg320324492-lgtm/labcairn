"""The descriptive operators, and the numbers they produce.

LC-P1-10's corpus is this file's fixture, and it is the same statement the
operators are checked against: the expected values say what each fixture
contains and what the numbers over it are, so an operator that computes
something else is caught against data rather than against a golden file the
operator could have written.

Three things are under test, and the third is the one that is easiest to get
wrong:

* the **values** — each operator computes what the corpus says it computes;
* the **undefined cases** — an empty selection has no mean, and a single
  value has no *sample* standard deviation, and neither of them is 0;
* the **refusals** — a selection whose cells carry two unit tokens is
  refused, not reconciled, and a statistic with a value but no reason (or a
  reason but no value) is refused by the model.

The counts travel with every result, because a mean over nine of ten cells is
a different claim from a mean over ten, and a result that did not say which
it was would be a number with a hidden denominator.
"""

from __future__ import annotations

from typing import Literal

import pytest
from analysis_fixtures import corpus_selection, corpus_source, load_expected, row_numbers
from pydantic import ValidationError

from labcairn.analysis.operators.descriptive import (
    DescriptiveArgs,
    StatisticResult,
    StdevArgs,
    count,
    maximum,
    mean,
    median,
    minimum,
    stdev,
    sum_,
)
from labcairn.analysis.units import UnitDisagreementError, declared_unit_for

#: The fixtures whose first selection is a plain numeric column.
NUMERIC_FIXTURES = ["basic.csv", "groups.csv", "missing.csv", "holes.csv", "single.csv"]


def _args(fixture: str, described: dict[str, object]) -> DescriptiveArgs:
    return DescriptiveArgs(selection=corpus_selection(fixture, described))


def _stdev_args(fixture: str, described: dict[str, object], ddof: Literal[0, 1]) -> StdevArgs:
    return StdevArgs(selection=corpus_selection(fixture, described), ddof=ddof)


@pytest.mark.unit
@pytest.mark.parametrize("fixture", NUMERIC_FIXTURES)
def test_the_operators_compute_what_the_corpus_says(fixture: str) -> None:
    """Every operator's value is the corpus's value.

    The corpus's statistics were computed by Python's :mod:`statistics`, which
    is not LabCairn's code, so this is a comparison and not an echo.
    """
    payload = load_expected(fixture)
    described = payload["selections"][0]
    expect = described["expect"]
    if expect["outcome"] == "refused":
        pytest.skip("a refused selection is checked by its own test")
    statistics_expected = expect["statistics"]
    source = corpus_source(fixture)
    args = _args(fixture, described)

    assert mean(args, source).value == pytest.approx(statistics_expected["mean"])
    assert median(args, source).value == pytest.approx(statistics_expected["median"])
    assert sum_(args, source).value == pytest.approx(statistics_expected["sum"])
    assert minimum(args, source).value == pytest.approx(statistics_expected["min"])
    assert maximum(args, source).value == pytest.approx(statistics_expected["max"])
    assert stdev(_stdev_args(fixture, described, 0), source).value == pytest.approx(
        statistics_expected["stdev_population"]
    )
    assert stdev(_stdev_args(fixture, described, 1), source).value == pytest.approx(
        statistics_expected["stdev_sample"]
    )
    # The corpus's statistics are over the cells that carry a quantity, and it
    # states which cells those are by stating the ones that do not.
    unusable = len(expect["absent"]) + len(expect["empty"]) + len(expect["not_a_quantity"])
    addressed = len(row_numbers(described["rows"])) * len(described["columns"])
    assert count(args, source).value == pytest.approx(addressed - unusable)


@pytest.mark.unit
@pytest.mark.parametrize("fixture", NUMERIC_FIXTURES)
def test_every_operator_carries_the_counts_of_the_selection_it_used(fixture: str) -> None:
    """A statistic says how much of the selection it is about.

    A mean over nine of ten cells is a different claim from a mean over ten,
    and a result that did not say which it was would be a number with a
    hidden denominator.
    """
    payload = load_expected(fixture)
    described = payload["selections"][0]
    expect = described["expect"]
    if expect["outcome"] == "refused":
        pytest.skip("a refused selection is checked by its own test")
    source = corpus_source(fixture)
    result = mean(_args(fixture, described), source)
    rows = len(row_numbers(described["rows"]))
    columns = len(described["columns"])
    unusable = len(expect["absent"]) + len(expect["empty"]) + len(expect["not_a_quantity"])

    assert result.n_empty == len(expect["empty"])
    assert result.n_absent == len(expect["absent"])
    assert result.n_invalid == len(expect["not_a_quantity"])
    assert result.n_used == rows * columns - unusable
    assert result.n_used + result.n_empty + result.n_absent + result.n_invalid == rows * columns


@pytest.mark.unit
def test_a_selection_with_no_value_has_no_mean() -> None:
    """An empty selection has no mean, and the result says so.

    Not zero. A mean of nothing is undefined, and ADR-0004 A8 is about exactly
    that distinction.
    """
    payload = load_expected("empty.csv")
    described = payload["selections"][0]
    result = mean(_args("empty.csv", described), corpus_source("empty.csv"))
    assert result.value is None
    assert result.undefined_reason
    assert result.n_used == 0


@pytest.mark.unit
def test_a_single_value_has_no_sample_standard_deviation_and_a_zero_population_one() -> None:
    """The two deviations of one value are different facts, and both are said.

    The population deviation of one value is **0**, from a real formula. The
    sample deviation divides by ``n-1`` and is **undefined**. Reporting 0 for
    the second would be reporting an unknown as a measurement.
    """
    payload = load_expected("single.csv")
    described = payload["selections"][0]
    source = corpus_source("single.csv")

    population = stdev(_stdev_args("single.csv", described, 0), source)
    assert population.value == 0.0
    assert population.undefined_reason is None

    sample = stdev(_stdev_args("single.csv", described, 1), source)
    assert sample.value is None
    assert sample.undefined_reason
    assert "undefined" in sample.undefined_reason


@pytest.mark.unit
def test_a_selection_with_two_unit_tokens_is_refused() -> None:
    """Units are compared as written, and never converted.

    ``1 kg`` against ``1000 g`` is the same quantity and a contradiction as
    a record. Reconciling them would mean the arithmetic of a unit algebra
    needed the evidence standard this ledger enforces, and Phase 1 has no
    such standard.
    """
    payload = load_expected("units.csv")
    described = payload["selections"][0]
    assert described["expect"]["outcome"] == "refused"
    with pytest.raises(UnitDisagreementError) as raised:
        mean(_args("units.csv", described), corpus_source("units.csv"))
    assert "kg" in str(raised.value)
    assert "g" in str(raised.value)


@pytest.mark.unit
def test_a_statistic_carries_its_operator_and_version() -> None:
    """A result says which operator produced it, and which version of it.

    A manifest quotes the operator by name, and a result that did not say its
    own version could not be compared with the manifest beside it.
    """
    payload = load_expected("basic.csv")
    described = payload["selections"][0]
    result = mean(_args("basic.csv", described), corpus_source("basic.csv"))
    assert result.operator_id == "labcairn.analysis.mean"
    assert result.operator_version == "1.0.0"
    assert result.selection == corpus_selection("basic.csv", described)


@pytest.mark.unit
def test_a_statistic_is_either_a_value_or_undefined_with_a_reason() -> None:
    """The two are not separable, and the model says so.

    A value with no reason hides an unknown, and a reason with no value says
    nothing.
    """
    with pytest.raises(ValidationError):
        StatisticResult(
            operator_id="labcairn.analysis.mean",
            operator_version="1.0.0",
            value=None,
            undefined_reason=None,
            n_used=0,
            n_empty=0,
            n_absent=0,
            n_invalid=0,
            unit=None,
            selection=corpus_selection("basic.csv", {"rows": "2-11", "columns": ["value"]}),
        )


@pytest.mark.unit
def test_a_standard_deviation_needs_to_be_told_which_population() -> None:
    """``ddof`` is required. A default would be a silent claim.

    The two deviations differ by a factor of ``n/(n-1)``, and an absent
    choice is not a choice.
    """
    payload = load_expected("basic.csv")
    described = payload["selections"][0]
    with pytest.raises(ValidationError):
        StdevArgs(selection=corpus_selection("basic.csv", described))  # type: ignore[call-arg]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("column", "expected"),
    [
        ("mass (kg)", "kg"),
        ("value", None),
        ("result (see table 2)", None),
        ("mass (kg per sample)", None),
        ("(kg)", None),
    ],
)
def test_a_header_declares_a_unit_only_in_a_narrow_shape(column: str, expected: str | None) -> None:
    """``mass (kg)`` declares a unit; prose in parentheses does not.

    Treating the words after a number as a unit is the mistake C3's own
    docstring refuses to make — half the words that follow a number in a real
    corpus are prose.
    """
    assert declared_unit_for(column) == expected


@pytest.mark.unit
def test_every_operator_refuses_a_column_whose_header_contradicts_its_cells() -> None:
    """The check is in the selection, so every operator inherits it.

    A check written into one operator would leave the other six computing a
    statistic over a column whose data contradicts its own header, and the
    refusal would then depend on which operator the caller happened to ask
    for. The cells of this column agree with each other — every one of them
    says ``m`` — so nothing else would have refused it.
    """
    described: dict[str, object] = {"rows": "2-5", "columns": ["length (cm)"]}
    source = corpus_source("declared.csv")
    for operator in (mean, sum_, minimum, maximum, median, count):
        with pytest.raises(UnitDisagreementError):
            operator(_args("declared.csv", described), source)
    with pytest.raises(UnitDisagreementError):
        stdev(_stdev_args("declared.csv", described, 0), source)


@pytest.mark.unit
def test_a_statistic_over_a_declared_column_carries_the_unit_the_data_carries() -> None:
    """A confirmed declaration is the data's own unit, and the result says so."""
    described: dict[str, object] = {"rows": "2-5", "columns": ["mass (kg)"]}
    result = mean(_args("declared.csv", described), corpus_source("declared.csv"))
    assert result.unit == "kg"
    assert result.value == pytest.approx(3.0)


@pytest.mark.unit
def test_a_declared_unit_no_cell_corroborates_leaves_the_result_without_a_unit() -> None:
    """An unverified declaration is not a unit, and the result does not carry one.

    The unit of a statistic is the unit of the cells it was computed over. A
    header's claim is not a measurement, and a result that reported it as one
    would be reporting a unit nobody checked — the "unknown is not zero"
    discipline applied to a unit instead of to a number.
    """
    payload = load_expected("typed.csv")
    described = payload["selections"][0]
    result = mean(_args("typed.csv", described), corpus_source("typed.csv"))
    assert result.unit is None
    assert result.value == pytest.approx(2.5)


@pytest.mark.unit
def test_two_unit_tokens_are_refused_as_the_cells_disagreeing_with_each_other() -> None:
    """Two different problems, two different words.

    ``units.csv``'s column declares nothing and its cells carry two tokens, so
    the selection resolves it and the *operator* refuses: a selection whose
    cells disagree with each other is not a statistic over anything. That is
    not the refusal a column's declaration earns, and the two are told apart
    by the words they use.
    """
    payload = load_expected("units.csv")
    described = payload["selections"][0]
    with pytest.raises(UnitDisagreementError) as raised:
        mean(_args("units.csv", described), corpus_source("units.csv"))
    message = str(raised.value)
    assert "different unit tokens" in message
    assert "declares the unit" not in message
