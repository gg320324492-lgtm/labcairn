"""The operator contract: what a vetted analysis operation is, and its name.

LC-P1-10 T02 is the contract half of the operator catalogue. The catalogue
itself — the set of shipped operators — lands with the operators, because it
has to be **built from their own id constants** for the same reason
``labcairn.evidence.catalog`` is: one id, one spelling. A catalogue written
out beside the implementations would be a second spelling of a closed set,
which is exactly what ADR-0009's canonical ``locator_key`` was written to
stop.

What is tested here is the shape every operator will have, and the grammar
its name follows. The grammar is the part worth testing: a name that can be
spelled two ways is a name two manifests can disagree about, and the
disagreement would not crash — it would be two records of the same run that
do not compare equal.

The argument model is tested too, because it is the other half of what makes
an operator *vetted*: a closed, frozen model means an unrecognised parameter
is an error rather than a silently ignored key, and the digest of the
parameters means something.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from labcairn.analysis.operators import (
    Operator,
    OperatorArgs,
    OperatorIdError,
    operator_reference,
    parse_operator_reference,
)
from labcairn.sources.locators import LocatorKind


class _Args(OperatorArgs):
    column: str


class _Result(BaseModel):
    model_config = ConfigDict(frozen=True)
    value: float


def _operator(
    *,
    operator_id: str = "labcairn.analysis.mean",
    operator_version: str = "1.0.0",
    accepted_locator_kinds: frozenset[LocatorKind] = frozenset({LocatorKind.CSV}),
    summary: str = "the arithmetic mean of a numeric column",
) -> Operator[_Args, _Result]:
    return Operator(
        operator_id=operator_id,
        operator_version=operator_version,
        args_model=_Args,
        result_model=_Result,
        accepted_locator_kinds=accepted_locator_kinds,
        summary=summary,
    )


@pytest.mark.unit
def test_an_operator_is_named_the_one_way() -> None:
    """The reference is the id and the version, quoted together.

    A manifest that says ``mean`` and one that says ``mean@1.0.0`` are
    different claims about the same run, and only the second can be compared
    to another run.
    """
    operator = _operator()
    assert operator_reference(operator) == "labcairn.analysis.mean@1.0.0"
    assert operator.reference == "labcairn.analysis.mean@1.0.0"


@pytest.mark.unit
def test_a_reference_round_trips() -> None:
    """Parsing a reference gives back the id and the version it names."""
    identifier, version = parse_operator_reference("labcairn.analysis.mean@1.0.0")
    assert identifier == "labcairn.analysis.mean"
    assert version == "1.0.0"


@pytest.mark.unit
def test_a_reference_is_split_at_the_last_separator() -> None:
    """The split does not depend on the name being free of separators.

    The grammar rejects such a name anyway — an operator id matches
    ``labcairn.analysis.[a-z][a-z0-9_]*`` and nothing else — but a rule that
    depends on a second rule is a rule that can be broken by the second rule
    changing.
    """
    identifier, version = parse_operator_reference("labcairn.analysis.mean@1.0.0")
    assert "@" not in identifier
    assert version == "1.0.0"


@pytest.mark.unit
@pytest.mark.parametrize(
    "reference",
    [
        "labcairn.analysis.mean",
        "mean@1.0.0",
        "labcairn.analysis.mean@1.0",
        "labcairn.analysis.mean@1.0.0.0",
        "labcairn.analysis.mean@v1.0.0",
        "labcairn.evidence.mean@1.0.0",
        "labcairn.analysis.Mean@1.0.0",
    ],
)
def test_a_malformed_reference_is_refused(reference: str) -> None:
    """A reference that is not well formed is refused, and says why.

    A shape check, not a guarantee: an id that is well formed may still name
    no shipped operator, and the catalogue is what answers that.
    """
    with pytest.raises(OperatorIdError):
        parse_operator_reference(reference)


@pytest.mark.unit
@pytest.mark.parametrize(
    "operator_id",
    ["mean", "labcairn.analysis", "labcairn.evidence.mean", "labcairn.analysis.Mean", ""],
)
def test_a_malformed_operator_id_is_refused(operator_id: str) -> None:
    """An id from another package cannot be passed off as one of ours."""
    with pytest.raises(OperatorIdError):
        _operator(operator_id=operator_id)


@pytest.mark.unit
@pytest.mark.parametrize("version", ["1.0", "1", "v1.0.0", "1.0.0-rc1", ""])
def test_a_malformed_version_is_refused(version: str) -> None:
    """A version that says "1.0" cannot say what changed."""
    with pytest.raises(OperatorIdError):
        _operator(operator_version=version)


@pytest.mark.unit
def test_an_operator_may_only_read_tabular_material() -> None:
    """The accepted locator kinds are the tabular ones, and there is at least one.

    An operator that could read a PDF would have to answer for a layout
    nobody reconstructed, and an operator that accepts nothing can never run.
    """
    with pytest.raises(OperatorIdError):
        _operator(accepted_locator_kinds=frozenset({LocatorKind.PDF}))
    with pytest.raises(OperatorIdError):
        _operator(accepted_locator_kinds=frozenset())


@pytest.mark.unit
def test_an_operator_needs_a_summary_for_the_person_who_consents() -> None:
    """The summary is what a human reads when deciding whether to allow the run.

    An empty one is refused rather than rendered as nothing, because a blank
    prompt is a prompt that reads as an oversight.
    """
    with pytest.raises(OperatorIdError):
        _operator(summary="   ")


@pytest.mark.unit
def test_an_operator_argument_model_is_closed() -> None:
    """An unrecognised parameter is an error, not a silently ignored key.

    It is either a typo or a newer caller, and both deserve to be loud.
    """
    with pytest.raises(ValidationError):
        _Args.model_validate({"column": "value", "typo": "value"})


@pytest.mark.unit
def test_an_operator_argument_model_is_frozen() -> None:
    """A model that could change between the digest and the operation makes
    the digest decorative."""
    args = _Args(column="value")
    with pytest.raises(ValidationError):
        args.column = "other"
