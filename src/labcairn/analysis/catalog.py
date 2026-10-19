"""The registered analysis operators.

**Code, not a table.** This catalogue is built *from* the operator modules'
own constants, and the reason is the one
:mod:`labcairn.evidence.catalog` gives: *one id has one spelling*. A set
written out here would be a second spelling of a closed set, which is exactly
what ADR-0009's canonical ``locator_key`` was written to stop — and the
manifest quotes an operator by name, so two spellings of one operator would
be two manifests that do not compare equal.

The cost is that an operator cannot be registered at runtime, and the benefit
is that a run can only ever name an operator this build actually implements.

**The catalogue and the operators it registers are one thing.** They cannot
be separated: a catalogue listing operators with no implementation behind it
is the same defect as a rule id that names no shipped check, and it is the
reason this catalogue is created *with* :mod:`labcairn.analysis.operators.descriptive`
rather than before it. LC-P1-09 has the precedent: the evidence catalogue was
created in T08, after the checks it registers existed.
"""

from __future__ import annotations

from typing import Any, Final

from labcairn.analysis.operators import RegisteredOperator
from labcairn.analysis.operators.descriptive import (
    COUNT,
    MAX,
    MEAN,
    MEDIAN,
    MIN,
    STDEV,
    SUM,
)
from labcairn.analysis.operators.grouped import AGGREGATE

__all__ = [
    "OPERATORS",
    "is_registered_operator",
    "operator_for",
    "operator_version",
]


def is_registered_operator(operator_id: str) -> bool:
    """Is *operator_id* the id of an operator this build actually implements?"""
    return operator_for(operator_id) is not None


def operator_for(operator_id: str) -> RegisteredOperator[Any, Any] | None:
    """The operator *operator_id* names, or ``None`` when it names none.

    A miss rather than an exception, because a caller asking "is this
    registered?" and a caller asking "run it" want different things from the
    same question.
    """
    for registered in OPERATORS:
        if registered.operator.operator_id == operator_id:
            return registered
    return None


def operator_version(operator_id: str) -> str | None:
    """The version of the operator *operator_id* names.

    This is the version the catalogue holds **now**, which is not the same
    fact as the version a past run used — that one is in the run's manifest.
    """
    registered = operator_for(operator_id)
    if registered is None:
        return None
    return registered.operator.operator_version


def _shipped_operators() -> frozenset[RegisteredOperator[Any, Any]]:
    """Every operator this build implements.

    The type parameters are erased, and deliberately so: the catalogue holds
    operators with **different** argument models, and the place a caller's
    parameters lose their type is the capability's own boundary, where
    ``analysis.run`` carries them as an untyped mapping and the operator's
    argument model validates them.

    The **chart operator** is imported here rather than at the top of the
    module, and the reason is an import cycle that no arrangement of
    module-level imports can break: the chart package's own initialiser
    imports the recipe module, the recipe module imports *this* module for
    ``operator_for``, and the catalogue holds the chart operator. So the
    chart operator's module can only be imported once this module is
    otherwise complete -- which is what this function's place at the bottom
    of the file buys, and why the set is built by a call rather than by a
    literal at the top.

    The constant still has exactly one home: the chart operator's own
    module. The catalogue quotes it; it does not spell it out.
    """
    from labcairn.analysis.chart.render import CHART

    return frozenset({AGGREGATE, CHART, COUNT, MAX, MEAN, MEDIAN, MIN, STDEV, SUM})


#: Every operator this build implements.
OPERATORS: Final[frozenset[RegisteredOperator[Any, Any]]] = _shipped_operators()
