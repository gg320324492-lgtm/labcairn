"""The catalogue of registered analysis operators.

The catalogue is built from the operator modules' own constants, so the thing
worth testing is that **one id has one spelling**: the catalogue's entry for
an operator must carry exactly the id and version the implementation declares,
and a second spelling of the same operator must not be reachable.

That is the property ADR-0009's canonical ``locator_key`` was written to
protect, and it is the reason the catalogue is code rather than a table. A
frozenset written out beside the implementations would be a second spelling of
a closed set, and a manifest quotes an operator by name — so two spellings
would be two manifests that do not compare equal.

The other thing tested here is that the catalogue holds **implementations**,
not just names. An operator id that names no shipped implementation is the
same defect as a rule id that names no shipped check: a run would be able to
ask for something that does not exist, and the failure would be a missing
result rather than a refusal.
"""

from __future__ import annotations

import pytest

from labcairn.analysis.catalog import (
    OPERATORS,
    is_registered_operator,
    operator_for,
    operator_version,
)
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

DESCRIPTIVE = (MEAN, SUM, MIN, MAX, MEDIAN, STDEV, COUNT)

#: Every operator this build ships. The catalogue is compared against the
#: modules' own constants, so an operator that is shipped but not registered
#: -- or registered but not shipped -- is caught here.
SHIPPED = (*DESCRIPTIVE, AGGREGATE)


@pytest.mark.unit
def test_the_catalogue_holds_every_shipped_operator() -> None:
    """The catalogue is the set of operators this build implements.

    And the set is compared against the modules' own constants, so an
    operator that is shipped but not registered — or registered but not
    shipped — is caught here rather than at the first run that asks for it.
    """
    assert frozenset(SHIPPED) == OPERATORS


@pytest.mark.unit
def test_the_catalogue_is_a_frozenset() -> None:
    """It cannot be added to at run time.

    A registry that accepts a new entry is a registry whose contents depend on
    what happened to run first, and the whole point of the catalogue is that
    a run can only ever name an operator this build implements.
    """
    assert isinstance(OPERATORS, frozenset)


@pytest.mark.unit
@pytest.mark.parametrize("registered", DESCRIPTIVE, ids=lambda r: r.operator.operator_id)
def test_a_registered_operator_carries_the_id_its_implementation_declares(
    registered: object,
) -> None:
    """One id, one spelling.

    The catalogue's entry and the implementation's own constant are the same
    object, so they cannot drift: there is no second place for the name to be
    written down.
    """
    operator_id = registered.operator.operator_id  # type: ignore[attr-defined]
    found = operator_for(operator_id)
    assert found is not None
    assert found.operator.operator_id == operator_id
    assert found.operator.operator_version == registered.operator.operator_version  # type: ignore[attr-defined]


@pytest.mark.unit
def test_a_registered_operator_can_be_looked_up_by_its_id() -> None:
    """The catalogue answers the two questions a run asks of it."""
    assert is_registered_operator("labcairn.analysis.mean") is True
    assert operator_version("labcairn.analysis.mean") == "1.0.0"
    assert operator_for("labcairn.analysis.mean") is MEAN


@pytest.mark.unit
def test_an_id_that_names_no_operator_is_a_miss() -> None:
    """Not an exception, and not a false.

    A caller asking "is this registered?" and a caller asking "run it" want
    different things from the same question, and the first one must not be
    answered by a crash.
    """
    assert is_registered_operator("labcairn.analysis.median_of_a_median") is False
    assert operator_for("labcairn.analysis.median_of_a_median") is None
    assert operator_version("labcairn.analysis.median_of_a_median") is None
    assert is_registered_operator("") is False


@pytest.mark.unit
def test_every_registered_operator_declares_what_it_needs() -> None:
    """Each one names its argument model, its result model, its formats and
    what it does."""
    for registered in OPERATORS:
        operator = registered.operator
        assert operator.operator_id.startswith("labcairn.analysis.")
        assert operator.operator_version
        assert operator.args_model is not None
        assert operator.result_model is not None
        assert operator.accepted_locator_kinds
        assert operator.summary
        assert callable(registered.run)
