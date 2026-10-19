"""What a vetted analysis operator is, and the one way it is named.

This module is the **contract**; the catalogue that holds the shipped
operators lands with the operators themselves, for a reason worth stating
because it is the reason this project's evidence catalogue was written the way
it was.

``labcairn.evidence.catalog`` is built *from* the check modules' own id
constants rather than spelled out in a list, and the reason is in its
docstring: *"one id has one spelling"*. A frozenset written out beside the
implementations would be a second spelling of a closed set, which is exactly
what ADR-0009's canonical ``locator_key`` was written to stop. The same
discipline applies here, so **the catalogue cannot exist before the operators
do** — there would be nothing for it to be built from, and a catalogue
listing operators with no implementation behind it is the same defect as a
rule id that names no shipped check.

So this module holds everything that does not depend on a particular operator
existing: the shape of one, the grammar its name follows, the reference
spelling the manifest and the artifact receipt quote, and the closed argument
model every operator's parameters are built on.

The name
--------
An operator is named ``labcairn.analysis.<name>`` and versioned
``MAJOR.MINOR.PATCH``. The two are quoted together, as
``labcairn.analysis.mean@1.0.0``, and that joined form is the **only**
spelling that appears in a manifest or in an artifact's ``producer_id`` — the
same spelling ``labcairn.reports.receipt`` uses in its own docstring.

Why the version is quoted with the id and not looked up
------------------------------------------------------
A manifest that says ``mean`` and a manifest that says ``mean@1.0.0`` are
different claims about the same run, and only the second one can be compared
to another run. The catalogue knows which version is current; the manifest
records which version **ran**. Those are different facts, and a record of the
one is useless without the other.

The closed argument model
-------------------------
Every operator's parameters are a Pydantic model with ``extra="forbid"`` and
``frozen=True``, for the reasons ``labcairn.security.capabilities`` already
gives: an unrecognised key is either a typo or a newer caller, and both
deserve to be loud, and a model that could mutate its own arguments between
the digest being computed and the operation running would make the digest
decorative.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from pydantic import BaseModel, ConfigDict

from labcairn.sources.locators import LocatorKind

__all__ = [
    "OPERATOR_ID_PATTERN",
    "OPERATOR_VERSION_PATTERN",
    "Operator",
    "OperatorArgs",
    "OperatorIdError",
    "operator_reference",
    "parse_operator_reference",
]

#: An operator's name. The package part is fixed, so an id from another
#: package cannot be passed off as one of ours.
OPERATOR_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^labcairn\.analysis\.[a-z][a-z0-9_]*$")

#: A version, and it is three numbers because a version that says "1.0" cannot
#: say what changed.
OPERATOR_VERSION_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\d+\.\d+\.\d+$")

#: The locator kinds an operator may read. Only tabular material: the work
#: order says CSV and XLSX, and an operator that could read a PDF would have
#: to answer for a layout nobody reconstructed.
TABULAR_LOCATOR_KINDS: Final[frozenset[LocatorKind]] = frozenset(
    {LocatorKind.CSV, LocatorKind.XLSX}
)


class OperatorIdError(ValueError):
    """An operator id or reference that is not well formed.

    A shape check, not a guarantee: an id that is well formed may still name
    no shipped operator, and the catalogue is what answers that.
    """


class OperatorArgs(BaseModel):
    """The base every operator's argument model inherits.

    ``extra="forbid"`` and ``frozen=True``, for the reasons in
    :mod:`labcairn.security.capabilities`: a closed model is what lets an
    argument digest mean something, and a frozen one is what stops the model
    changing between the digest and the operation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


@dataclass(frozen=True, slots=True)
class Operator:
    """One vetted analysis operation, and everything a caller needs to run it.

    ``args_model`` and ``result_model`` are the *classes*, not instances: an
    operator validates its arguments and shapes its result, and a caller
    needs to know which shapes those are before it has run anything.
    """

    operator_id: str
    operator_version: str
    args_model: type[OperatorArgs]
    result_model: type[BaseModel]
    #: The locator kinds this operator may read. An operator that could read
    #: anything would be an operator nobody could reason about.
    accepted_locator_kinds: frozenset[LocatorKind]
    #: One line, for a human reading an approval prompt. Rendered from the
    #: declared fields and never from imported content, because this string
    #: ends up in front of the person whose consent it is.
    summary: str

    def __post_init__(self) -> None:
        if OPERATOR_ID_PATTERN.match(self.operator_id) is None:
            raise OperatorIdError(
                f"operator id {self.operator_id!r} is not well formed. An id is "
                f"'labcairn.analysis.<name>', in lower case, with the name in "
                f"snake_case."
            )
        if OPERATOR_VERSION_PATTERN.match(self.operator_version) is None:
            raise OperatorIdError(
                f"operator version {self.operator_version!r} is not well formed. A "
                f"version is three numbers: MAJOR.MINOR.PATCH."
            )
        if not self.accepted_locator_kinds <= TABULAR_LOCATOR_KINDS:
            raise OperatorIdError(
                f"operator {self.operator_id!r} accepts "
                f"{sorted(k.value for k in self.accepted_locator_kinds)}, and the "
                f"tabular kinds are {sorted(k.value for k in TABULAR_LOCATOR_KINDS)}."
            )
        if not self.accepted_locator_kinds:
            raise OperatorIdError(
                f"operator {self.operator_id!r} accepts no locator kind, so it can "
                f"never read anything."
            )
        if not self.summary.strip():
            raise OperatorIdError(
                f"operator {self.operator_id!r} has an empty summary. The summary "
                f"is what a person reads when deciding whether to allow the run."
            )

    @property
    def reference(self) -> str:
        """The operator's name and version, as one quoted string."""
        return operator_reference(self)


def operator_reference(operator: Operator) -> str:
    """``labcairn.analysis.mean@1.0.0`` — the one spelling a manifest quotes."""
    return f"{operator.operator_id}@{operator.operator_version}"


def parse_operator_reference(reference: str) -> tuple[str, str]:
    """The id and version a reference names.

    Split at the **last** ``@``, so a reference whose name contained one would
    still parse. The grammar rejects such a name anyway -- an operator id
    matches ``labcairn.analysis.[a-z][a-z0-9_]*`` and nothing else -- but
    splitting at the last separator is the rule that does not depend on that.
    """
    identifier, separator, version = reference.rpartition("@")
    if not separator:
        raise OperatorIdError(
            f"{reference!r} is not an operator reference. The form is "
            f"'<operator id>@<version>', for example "
            f"'labcairn.analysis.mean@1.0.0'."
        )
    if OPERATOR_ID_PATTERN.match(identifier) is None:
        raise OperatorIdError(f"{identifier!r} is not a well-formed operator id.")
    if OPERATOR_VERSION_PATTERN.match(version) is None:
        raise OperatorIdError(f"{version!r} is not a well-formed operator version.")
    return identifier, version
