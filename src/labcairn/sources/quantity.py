"""What a quantity is, read out of a cell's text.

This module was moved out of ``labcairn.evidence.checks.c3`` and into
``labcairn.sources`` for one reason: **the ledger and the analysis layer must
not disagree about what a number is.**

C3 answers "does the number in this record agree with the number in this
cell", and LC-P1-10's operators answer "what is the mean of this column".
Both of those questions start by asking the same thing of the same text — *is
this a quantity, and what is it?* — and two readers of that question would be
two answers to it. The failure would not be a crash: it would be a ledger that
calls ``"3.5 kg"`` a quantity and an analysis that calls it prose, and a
disagreement between them that only shows up in a number nobody checked twice.

So there is one reader, here, and both layers use it.

The rule it implements
----------------------
A segment is a quantity only when it is **one number and at most one token**.
That is deliberately narrow, and the narrowness is measured rather than
preferred. Scanning the fixture corpus for a number followed by a trailing
token returns, among the most frequent "units": ``%``, ``m``, ``r``,
``introduction``, ``e``, ``conclusion``, ``t``, ``j``, ``ij``, ``on``, ``as``.
Half of those are prose. Any rule that reads the word after a number as its
unit will invent units that do not exist, and an invented unit is a confident
wrong answer — the thing this ledger exists to prevent.

The consequences are the ones C3 has always had:

* a page of prose containing a number is **not** a cell, and C3 says so rather
  than picking a figure out of it;
* ``1,234`` is read as the number 1 followed by a token, and the token is not
  a unit, so the segment is refused as ambiguous rather than guessed at;
* a bare currency symbol is part of the value's unit, not noise.

**Units are compared, never converted.** ``1 kg`` against a record claiming
``1000 g`` is the same quantity and a contradiction as a record. C3 reports the
contradiction. Building a unit algebra inside a read would mean the arithmetic
of that algebra itself needed the evidence standard this ledger enforces, and
Phase 1 has no such standard.

The known cost is stated rather than hidden: ``kilograms`` and ``kg`` are one
unit spelled two ways, and a comparison of the two fails. That is a false
negative, which is exactly what ADR-0004 R2 warns about, and the detail names
both tokens so the reader can see what the check did not do.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

__all__ = ["NumericReading", "read_number"]

#: One number, optionally signed. No thousands separators: ``1,234`` is read as
#: the number 1 followed by a token, and the token is not a unit, so the segment
#: is refused as ambiguous rather than guessed.
_NUMBER: Final[re.Pattern[str]] = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")

#: A unit token: letters, or a bare symbol, optionally with a slash. ``%`` alone
#: counts -- an earlier draft required a letter and so refused "12%", turning a
#: legitimate percentage into "not a quantity". There is no length cap: a segment
#: qualifies only when it is a number and at most one token, so prose is refused
#: by shape rather than by an arbitrary limit. Scanning the fixture corpus shows
#: why a cap is the wrong tool -- the words following numbers there include
#: "introduction", "conclusion" and "ij", but each sits inside a multi-token line,
#: which the shape rule already rejects.
_UNIT: Final[re.Pattern[str]] = re.compile(r"(?:°?[A-Za-z]+|%|°|²|³)(?:/[A-Za-z]+)?")

#: A leading currency symbol is part of the value's unit, not noise.
_CURRENCY: Final[str] = "$€£"


@dataclass(frozen=True, slots=True)
class NumericReading:
    """What one anchored segment says numerically, and whether it says a unit.

    ``value`` is ``None`` when the segment is not a clean quantity. ``unit`` is
    ``None`` when the number stands alone, which is the ordinary case for a cell
    in a table and the reason most declared units cannot be verified.
    """

    value: float | None
    unit: str | None
    raw: str


def read_number(text: str) -> NumericReading:
    """Parse one anchored segment into a number and an optional unit.

    Strict on purpose. A segment qualifies if it is a number, optionally preceded
    by a currency symbol and optionally followed by one unit token, and nothing
    else. Everything else -- prose, two figures, a thousands separator -- is
    reported as having no readable quantity, which C3 answers ``indeterminate``
    and the analysis layer counts as unusable. That is the honest answer: the
    data is present and the comparison is not possible, which is a different
    fact from the data contradicting the record.
    """
    stripped = text.strip()
    if not stripped:
        return NumericReading(value=None, unit=None, raw=stripped)

    body = stripped
    leading = ""
    if body[0] in _CURRENCY:
        leading, body = body[0], body[1:].strip()

    number_part = _NUMBER.match(body)
    if number_part is None:
        return NumericReading(value=None, unit=None, raw=stripped)

    # ``fullmatch`` on the number alone means the segment is nothing but a
    # number. Anything left over must be exactly one unit token, or the segment
    # is not a quantity.
    rest = body[number_part.end() :].strip()

    if not rest:
        return NumericReading(value=float(number_part.group(0)), unit=leading or None, raw=stripped)

    unit_match = _UNIT.fullmatch(rest)
    if unit_match is None:
        return NumericReading(value=None, unit=None, raw=stripped)

    return NumericReading(
        value=float(number_part.group(0)),
        unit=leading + rest,
        raw=stripped,
    )
