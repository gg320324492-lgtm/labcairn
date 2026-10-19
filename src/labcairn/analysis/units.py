"""Units, in the analysis layer: compared as written, and never converted.

C3's discipline, inherited rather than reinvented. Three rules, and the
third is the one that costs something.

**A unit token is compared as written.** ``kg`` against ``g`` is a
disagreement, not a conversion, and a disagreement is reported. Building a
unit algebra inside a read would mean the arithmetic of that algebra needed
the evidence standard this ledger enforces, and Phase 1 has no such
standard.

**The known cost is stated rather than hidden.** ``kilograms`` and ``kg`` are
one unit spelled two ways, and a selection holding both is refused. That is a
false negative, which is exactly what ADR-0004 R2 warns about, and the
refusal names both tokens so the reader can see what the check did not do.

**A header may declare a unit, and only a narrow shape counts.** A column
called ``mass (kg)`` declares ``kg``. A column called ``result (see table
2)`` declares **nothing**, because the parenthesised text is not a unit and
treating the words after a number as a unit is the mistake C3's own
docstring refuses to make — half the words that follow a number in a real
corpus are prose.

The declared unit is a property of the **column's name**, so it is a pure
function of that name and needs no access to the material. That is what makes
it checkable against a header the ledger holds and against one it does not.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

__all__ = ["UnitDisagreementError", "declared_unit_for", "unit_disagreement"]

#: A column header that declares a unit: a name, then a parenthesised token
#: with no whitespace in it. The whitespace rule is the whole rule — it is
#: what keeps "see table 2" from being read as a unit.
_DECLARING_HEADER = re.compile(r"^(?P<name>[^()]+?)\s*\((?P<unit>[^\s()]+)\)$")


def declared_unit_for(column: str) -> str | None:
    """The unit a column's header declares, or ``None`` when it declares none.

    ``"mass (kg)"`` declares ``"kg"``. ``"value"`` declares nothing, and
    neither does ``"result (see table 2)"`` — the parenthesised text has
    whitespace in it, and prose is not a unit.
    """
    matched = _DECLARING_HEADER.match(column.strip())
    if matched is None:
        return None
    return matched.group("unit")


class UnitDisagreementError(RuntimeError):
    """The cells of a selection carry more than one unit token.

    A refusal, not a flag. Units are compared as written and never converted,
    so a selection that would need a unit algebra to be reconciled is one this
    build cannot compute, and saying so is the honest outcome.
    """


def unit_disagreement(tokens: Iterable[str]) -> str | None:
    """The reason the unit tokens disagree, or ``None`` when they do not.

    The reason is returned rather than a bare boolean because the refusal has
    to **name both tokens**: a reader who is told only that the units differ
    cannot tell a typo from a real second unit, and the two have different
    repairs.
    """
    distinct = sorted(set(tokens))
    if len(distinct) <= 1:
        return None
    listed = ", ".join(repr(token) for token in distinct)
    return (
        f"the cells carry {len(distinct)} different unit tokens: {listed}. "
        f"Units are compared as written and never converted, so this selection "
        f"is refused rather than reconciled."
    )
