"""Descriptive statistics over a selection, and the operators that compute them.

Seven operations, each registered, each with a closed argument model and a
version. They are the first thing LC-P1-10 builds that is a **number this
project computed** rather than a number it read, and the difference is the
whole reason the manifest exists.

Three rules hold across all seven.

**The statistic is over the values that could be used, and the ones that
could not are counted.** Every result carries ``n_used``, ``n_empty``,
``n_absent`` and ``n_invalid``, so a reader can see how much of the selection
the number is about. A mean over nine of ten cells is a different claim from
a mean over ten, and a result that did not say which it was would be a
number with a hidden denominator.

**An undefined statistic is undefined, not zero.** The mean of an empty
selection and the sample standard deviation of one value have no answer, and
the result says so with a ``None`` and a reason. The *population* standard
deviation of one value, on the other hand, is 0 — a real zero, computed from
a real formula — and the result says 0. ADR-0004 A8 is about exactly this
distinction, and it is why ``stdev`` takes the degrees of freedom as a
**required** argument rather than defaulting one: an absent choice is not a
choice, and a default would be a silent claim about which population was
meant.

**Units are compared as written.** A selection whose cells carry two unit
tokens is **refused**, not reconciled — see :mod:`labcairn.analysis.units`. A
column whose header declares a unit the cells contradict is refused earlier
still, by the selection, because the declaration is a claim about the column
and the column's own cells are the only evidence that can check it.

Every result is a **derivation**, not a fact about a cell. It carries the
selection it came from rather than the list of cells, because the list is
recoverable from the source's hash and the selection, and storing it would be
a second copy of a fact with its own staleness.
"""

from __future__ import annotations

import math
import statistics
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from labcairn.analysis.operators import Operator, OperatorArgs, RegisteredOperator
from labcairn.analysis.selection import Selection, SelectionResult, resolve_selection
from labcairn.analysis.units import UnitDisagreementError, unit_disagreement
from labcairn.analysis.values import ValueSource
from labcairn.sources.locators import LocatorKind

__all__ = [
    "COUNT",
    "MAX",
    "MEAN",
    "MEDIAN",
    "MIN",
    "STDEV",
    "SUM",
    "DescriptiveArgs",
    "StatisticResult",
    "StdevArgs",
]


class DescriptiveArgs(OperatorArgs):
    """What every descriptive operator takes: a selection.

    The selection is the *description* — which source, which columns, which
    rows, and what to do about the cells that cannot be used — and the
    operator resolves it against the cell source it is given. Keeping the two
    apart is what lets the operators be checked against synthetic cells and
    against the real adapters without a database in the middle.
    """

    selection: Selection


class StdevArgs(DescriptiveArgs):
    """A standard deviation, and which population it is over.

    ``ddof`` is **required**. A default would be a silent claim about which
    population was meant, and the two differ by a factor of ``n/(n-1)`` —
    which is a number nobody chose.
    """

    ddof: Literal[0, 1]


class StatisticResult(BaseModel):
    """One statistic, and everything a reader needs to judge it.

    ``value`` is ``None`` **exactly** when ``undefined_reason`` is set, and
    the model refuses the other two combinations: a value with no reason
    hides an unknown, and a reason with no value says nothing.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    operator_id: str
    operator_version: str
    #: The statistic, or ``None`` when it is undefined.
    value: float | None
    #: Why the statistic is undefined. Required when ``value`` is ``None``.
    undefined_reason: str | None = None
    #: The cells the statistic was computed over.
    n_used: int
    #: The cells that were recorded and hold no text.
    n_empty: int
    #: The addresses where no cell was recorded.
    n_absent: int
    #: The cells that hold text which is not a quantity.
    n_invalid: int
    #: The unit the used cells carry, when they carry one.
    unit: str | None = None
    #: The selection the statistic came from.
    selection: Selection

    @model_validator(mode="after")
    def _a_value_and_a_reason_come_together(self) -> StatisticResult:
        if (self.value is None) != (self.undefined_reason is not None):
            raise ValueError(
                f"a statistic is either a value or undefined with a reason, and "
                f"{self.operator_id!r} was given value={self.value!r} with "
                f"reason={self.undefined_reason!r}. A value with no reason hides "
                f"an unknown, and a reason with no value says nothing."
            )
        return self


def _measured(
    args: DescriptiveArgs, source: ValueSource
) -> tuple[tuple[float, ...], SelectionResult, str | None]:
    """The values a statistic may be computed over, and what the selection cost.

    The check between the cells' own unit tokens happens here rather than in
    each operator, because a selection that carries two unit tokens is
    refused whatever is being computed over it. A column's *declared* unit
    is checked earlier still, by the selection, because that conflict is
    about the column and not about what is computed over it.
    """
    result = resolve_selection(args.selection, source)
    disagreement = unit_disagreement(result.units)
    if disagreement is not None:
        raise UnitDisagreementError(disagreement)
    values = tuple(cell.value for cell in result.quantities if cell.value is not None)
    unit = result.units[0] if result.units else None
    return values, result, unit


def _result(
    operator: Operator[Any, Any],
    args: DescriptiveArgs,
    result: SelectionResult,
    unit: str | None,
    value: float | None,
    undefined_reason: str | None = None,
) -> StatisticResult:
    return StatisticResult(
        operator_id=operator.operator_id,
        operator_version=operator.operator_version,
        value=value,
        undefined_reason=undefined_reason,
        n_used=result.n_used,
        n_empty=result.n_empty,
        n_absent=result.n_absent,
        n_invalid=result.n_invalid,
        unit=unit,
        selection=args.selection,
    )


def _undefined(
    operator: Operator[Any, Any],
    args: DescriptiveArgs,
    result: SelectionResult,
    unit: str | None,
    reason: str,
) -> StatisticResult:
    return _result(operator, args, result, unit, None, reason)


def mean(args: DescriptiveArgs, source: ValueSource) -> StatisticResult:
    """The arithmetic mean of the values the selection can use."""
    values, result, unit = _measured(args, source)
    if not values:
        return _undefined(
            _MEAN_OPERATOR,
            args,
            result,
            unit,
            "the selection holds no value to take a mean of",
        )
    return _result(_MEAN_OPERATOR, args, result, unit, statistics.fmean(values))


def sum_(args: DescriptiveArgs, source: ValueSource) -> StatisticResult:
    """The total of the values the selection can use.

    Summed with :func:`math.fsum`, which is correctly rounded, so the total
    does not depend on the order the cells were read in.
    """
    values, result, unit = _measured(args, source)
    if not values:
        return _undefined(
            _SUM_OPERATOR,
            args,
            result,
            unit,
            "the selection holds no value to add up",
        )
    return _result(_SUM_OPERATOR, args, result, unit, math.fsum(values))


def minimum(args: DescriptiveArgs, source: ValueSource) -> StatisticResult:
    """The smallest of the values the selection can use."""
    values, result, unit = _measured(args, source)
    if not values:
        return _undefined(
            _MIN_OPERATOR,
            args,
            result,
            unit,
            "the selection holds no value to take a minimum of",
        )
    return _result(_MIN_OPERATOR, args, result, unit, min(values))


def maximum(args: DescriptiveArgs, source: ValueSource) -> StatisticResult:
    """The largest of the values the selection can use."""
    values, result, unit = _measured(args, source)
    if not values:
        return _undefined(
            _MAX_OPERATOR,
            args,
            result,
            unit,
            "the selection holds no value to take a maximum of",
        )
    return _result(_MAX_OPERATOR, args, result, unit, max(values))


def median(args: DescriptiveArgs, source: ValueSource) -> StatisticResult:
    """The median of the values the selection can use."""
    values, result, unit = _measured(args, source)
    if not values:
        return _undefined(
            _MEDIAN_OPERATOR,
            args,
            result,
            unit,
            "the selection holds no value to take a median of",
        )
    return _result(_MEDIAN_OPERATOR, args, result, unit, statistics.median(values))


def stdev(args: StdevArgs, source: ValueSource) -> StatisticResult:
    """The standard deviation of the values the selection can use.

    The population (``ddof=0``) and the sample (``ddof=1``) deviations differ
    by a factor of ``n/(n-1)``, so the argument is required and the result
    records which was used. The sample deviation of a single value is
    **undefined**, and the population deviation of it is **0** — a real zero,
    from a real formula, and not the same thing as the sample one.
    """
    values, result, unit = _measured(args, source)
    if not values:
        return _undefined(
            _STDEV_OPERATOR,
            args,
            result,
            unit,
            "the selection holds no value to take a standard deviation of",
        )
    if args.ddof == 1 and len(values) < 2:
        return _undefined(
            _STDEV_OPERATOR,
            args,
            result,
            unit,
            f"a sample standard deviation over {len(values)} value(s) is undefined: "
            f"it divides by n-1, and n-1 is {len(values) - 1}",
        )
    value = statistics.pstdev(values) if args.ddof == 0 else statistics.stdev(values)
    return _result(_STDEV_OPERATOR, args, result, unit, value)


def count(args: DescriptiveArgs, source: ValueSource) -> StatisticResult:
    """How many values the selection can use.

    Every other result carries the same number in ``n_used``, so this
    operator exists for the caller that wants the count and nothing else. It
    is the one statistic that is never undefined: a count of nothing is 0,
    which is a fact and not an unknown.
    """
    _values, result, unit = _measured(args, source)
    return _result(_COUNT_OPERATOR, args, result, unit, float(result.n_used))


_TABULAR: Final[frozenset[LocatorKind]] = frozenset({LocatorKind.CSV, LocatorKind.XLSX})

_MEAN_OPERATOR: Final[Operator[DescriptiveArgs, StatisticResult]] = Operator(
    operator_id="labcairn.analysis.mean",
    operator_version="1.0.0",
    args_model=DescriptiveArgs,
    result_model=StatisticResult,
    accepted_locator_kinds=_TABULAR,
    summary="the arithmetic mean of the values a selection can use",
)
_SUM_OPERATOR: Final[Operator[DescriptiveArgs, StatisticResult]] = Operator(
    operator_id="labcairn.analysis.sum",
    operator_version="1.0.0",
    args_model=DescriptiveArgs,
    result_model=StatisticResult,
    accepted_locator_kinds=_TABULAR,
    summary="the total of the values a selection can use",
)
_MIN_OPERATOR: Final[Operator[DescriptiveArgs, StatisticResult]] = Operator(
    operator_id="labcairn.analysis.min",
    operator_version="1.0.0",
    args_model=DescriptiveArgs,
    result_model=StatisticResult,
    accepted_locator_kinds=_TABULAR,
    summary="the smallest of the values a selection can use",
)
_MAX_OPERATOR: Final[Operator[DescriptiveArgs, StatisticResult]] = Operator(
    operator_id="labcairn.analysis.max",
    operator_version="1.0.0",
    args_model=DescriptiveArgs,
    result_model=StatisticResult,
    accepted_locator_kinds=_TABULAR,
    summary="the largest of the values a selection can use",
)
_MEDIAN_OPERATOR: Final[Operator[DescriptiveArgs, StatisticResult]] = Operator(
    operator_id="labcairn.analysis.median",
    operator_version="1.0.0",
    args_model=DescriptiveArgs,
    result_model=StatisticResult,
    accepted_locator_kinds=_TABULAR,
    summary="the median of the values a selection can use",
)
_STDEV_OPERATOR: Final[Operator[StdevArgs, StatisticResult]] = Operator(
    operator_id="labcairn.analysis.stdev",
    operator_version="1.0.0",
    args_model=StdevArgs,
    result_model=StatisticResult,
    accepted_locator_kinds=_TABULAR,
    summary="the standard deviation of the values a selection can use",
)
_COUNT_OPERATOR: Final[Operator[DescriptiveArgs, StatisticResult]] = Operator(
    operator_id="labcairn.analysis.count",
    operator_version="1.0.0",
    args_model=DescriptiveArgs,
    result_model=StatisticResult,
    accepted_locator_kinds=_TABULAR,
    summary="how many values a selection can use",
)

MEAN: Final[RegisteredOperator[DescriptiveArgs, StatisticResult]] = RegisteredOperator(
    operator=_MEAN_OPERATOR, run=mean
)
SUM: Final[RegisteredOperator[DescriptiveArgs, StatisticResult]] = RegisteredOperator(
    operator=_SUM_OPERATOR, run=sum_
)
MIN: Final[RegisteredOperator[DescriptiveArgs, StatisticResult]] = RegisteredOperator(
    operator=_MIN_OPERATOR, run=minimum
)
MAX: Final[RegisteredOperator[DescriptiveArgs, StatisticResult]] = RegisteredOperator(
    operator=_MAX_OPERATOR, run=maximum
)
MEDIAN: Final[RegisteredOperator[DescriptiveArgs, StatisticResult]] = RegisteredOperator(
    operator=_MEDIAN_OPERATOR, run=median
)
STDEV: Final[RegisteredOperator[StdevArgs, StatisticResult]] = RegisteredOperator(
    operator=_STDEV_OPERATOR, run=stdev
)
COUNT: Final[RegisteredOperator[DescriptiveArgs, StatisticResult]] = RegisteredOperator(
    operator=_COUNT_OPERATOR, run=count
)
