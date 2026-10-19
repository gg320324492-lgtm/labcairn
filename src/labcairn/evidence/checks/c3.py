"""C3 — does the number agree with the anchored data?

ADR-0004 Contract 3, verbatim:

    Re-read the anchored cell/segment and compare to ``record.value`` under the
    declared unit and tolerance. ``fail`` on unit mismatch or on a difference
    exceeding tolerance. ``indeterminate`` when the segment is non-numeric or the
    declared tolerance is absent -- an undeclared tolerance is never 0.

The quantity reader now lives elsewhere
---------------------------------------
``read_number`` and ``NumericReading`` moved to
:mod:`labcairn.sources.quantity` in LC-P1-10, and are re-exported here, so
``from labcairn.evidence.checks.c3 import read_number`` and
``from labcairn.evidence.checks import read_number`` both still work and C3's
tests are untouched.

The move was for one reason: **the ledger and the analysis layer must not
disagree about what a number is.** C3 asks "does the number in this record
agree with the number in this cell" and LC-P1-10's operators ask "what is the
mean of this column", and both start by asking the same question of the same
text. Two readers of that question would be two answers to it, and the
disagreement would not crash — it would be a ledger that calls ``"3.5 kg"`` a
quantity and an analysis that calls it prose, and a number nobody checked
twice.

What the contract assumes, and what the store actually has
----------------------------------------------------------
C3 speaks of "the anchored cell" as if a cell carries a unit. It does not.
:class:`~labcairn.evidence.cite_support.LocatedContent` has ``text`` and a
``numeric_value``, and ``source_texts`` stores exactly the string the file held.
The only unit available is one written next to the number in that string --
"3.50 kg" has one, "3.50" does not.

That has a consequence worth stating before the code, because it is measured
rather than assumed. Scanning the fixture corpus for a number followed by a
trailing token returns, among the most frequent "units": ``%``, ``m``, ``r``,
``introduction``, ``e``, ``conclusion``, ``t``, ``j``, ``ij``, ``on``, ``as``.
Half of those are prose. Any rule that reads the word after a number as its unit
will invent units that do not exist, and an invented unit is a confident wrong
answer -- the thing this ledger exists to prevent.

So :func:`read_number` is deliberately narrow: a segment is a quantity only when
it is one number and at most one token. A page of prose containing a number is
not a cell, and C3 says so rather than picking a figure out of it.

The parsed value, not the display string
---------------------------------------
``locate_anchor``'s ``numeric_value`` reads the whole cell as a float, so
"3.50 kg" yields ``None`` and C3 would report "non-numeric" for a cell that
plainly contains a number. C3 reads the text instead.

Units are compared, never converted
-----------------------------------
``1 kg`` against a record claiming ``1000 g`` is the same quantity and a
contradiction as a record. C3 reports the contradiction. Building a unit algebra
inside a cite-support check would mean the arithmetic of that algebra itself
needed the evidence standard this ledger enforces, and Phase 1 has no such
standard.

The known cost is stated rather than hidden: ``kilograms`` and ``kg`` are one
unit spelled two ways, and C3 fails that. It is a false negative, which is
exactly what ADR-0004 R2 warns about, and the detail names both tokens so the
reader can see what the check did not do.

Tolerance is never a silent zero
--------------------------------
``record.tolerance`` defaults to ``None``, and ``None`` means *no comparison was
specified*, not *exact equality required*. Treating an absent tolerance as ``0.0``
would make every float whose last digit differs a failure, and would be a claim
about precision nobody chose. A declared ``0.0`` is a different thing: it is a
decision, and it bites.
"""

from __future__ import annotations

import math
from typing import Final

from labcairn.evidence.cite_support import LocationResolution, SourceIndex, Verdict
from labcairn.evidence.record import EvidenceRecord
from labcairn.evidence.states import CheckKind, CheckOutcome, EvidenceKind
from labcairn.sources.locators import describe_locator
from labcairn.sources.quantity import NumericReading, read_number

__all__ = ["C3_CHECKER_ID", "NumericReading", "check_numeric_consistency", "read_number"]

C3_CHECKER_ID: Final = "c3.numeric_consistency"


def check_numeric_consistency(record: EvidenceRecord, *, index: SourceIndex) -> Verdict:
    """Run C3 over every anchor a numeric record cites.

    ``pass`` only when a clean quantity was read at every cited anchor, no unit
    the source states contradicts the declared one, and the difference is within
    the declared tolerance. ``fail`` on a unit mismatch or a difference exceeding
    tolerance. ``indeterminate`` on a segment that is not a quantity, an
    undeclared tolerance, or a record carrying no number at all.
    """
    if record.kind is not EvidenceKind.NUMERIC:
        return _verdict(
            CheckOutcome.INDETERMINATE,
            f"the record is kind={record.kind.value!r}, which carries a statement "
            f"rather than a quantity. C3 has no number to reconcile, and reporting "
            f"a verdict here would answer a question the record did not ask",
        )

    if record.value is None:
        return _verdict(
            CheckOutcome.INDETERMINATE,
            "a numeric record with no value has nothing to compare against",
        )

    value = record.value
    if not math.isfinite(value):
        return _verdict(
            CheckOutcome.INDETERMINATE,
            f"the record's value is {value}, which is not finite. No comparison "
            f"against it is meaningful",
        )

    if not record.anchor_ids:
        return _verdict(
            CheckOutcome.INDETERMINATE,
            "the record cites no anchors, so there is no cell to re-read. A number "
            "with no address is not thereby inconsistent",
        )

    readings = [
        _read_one(anchor_id, index, value, record.unit, record.tolerance)
        for anchor_id in record.anchor_ids
    ]

    failures = [detail for outcome, detail in readings if outcome is CheckOutcome.FAIL]
    if failures:
        return _verdict(
            CheckOutcome.FAIL,
            f"{len(failures)} of {len(record.anchor_ids)} cited anchor(s) do not "
            f"agree with the record's value: {'; '.join(failures)}",
        )

    unclear = [detail for outcome, detail in readings if outcome is CheckOutcome.INDETERMINATE]
    if unclear:
        return _verdict(
            CheckOutcome.INDETERMINATE,
            f"the number could not be reconciled at {len(unclear)} of "
            f"{len(record.anchor_ids)} anchor(s): {'; '.join(unclear)}",
        )

    return _verdict(
        CheckOutcome.PASS,
        f"value {value} matches every cited anchor within the declared tolerance "
        f"of {record.tolerance}",
    )


def _read_one(
    anchor_id: str,
    index: SourceIndex,
    value: float,
    declared_unit: str | None,
    tolerance: float | None,
) -> tuple[CheckOutcome, str]:
    """C3's whole decision for one anchor id.

    ``value`` and ``declared_unit`` are passed rather than read from the record
    inside each branch: the caller has already established the value is present
    and finite, and re-testing that in every path would duplicate a guard that
    belongs in one place.
    """
    anchor = index.load_anchor(anchor_id)
    if anchor is None:
        return (
            CheckOutcome.FAIL,
            f"anchor {anchor_id!r} is not registered, so the quantity it is "
            f"supposed to carry has no source",
        )

    content = index.locate(anchor)
    if content is None:
        return (
            CheckOutcome.FAIL,
            f"anchor {anchor_id!r} is registered but yields no content",
        )

    if content.resolution is LocationResolution.UNRESOLVABLE:
        return (
            CheckOutcome.FAIL,
            f"anchor {anchor_id!r} points at {describe_locator(anchor.locator)}, "
            f"which is not in the material. The number has no address, and nothing "
            f"is read in its place",
        )

    if content.resolution is LocationResolution.UNADDRESSABLE:
        return (
            CheckOutcome.INDETERMINATE,
            f"anchor {anchor_id!r} points at material that cannot be read, so the "
            f"cell behind the number is unknown. That is not a disagreement; it is "
            f"a comparison that could not be made",
        )

    return _compare(content.text or "", anchor_id, value, declared_unit, tolerance)


def _compare(
    text: str,
    anchor_id: str,
    value: float,
    declared_unit: str | None,
    tolerance: float | None,
) -> tuple[CheckOutcome, str]:
    """Compare one anchored segment against the record's value."""
    reading = read_number(text)
    if reading.value is None:
        return (
            CheckOutcome.INDETERMINATE,
            f"anchor {anchor_id!r} holds {reading.raw!r}, which is not a single "
            f"quantity C3 can read. Nothing contradicts the record; the comparison "
            f"is simply not available at this address",
        )

    unit_verdict = _compare_units(declared_unit, reading, anchor_id)
    if unit_verdict is not None:
        return unit_verdict

    if tolerance is None:
        return (
            CheckOutcome.INDETERMINATE,
            f"anchor {anchor_id!r} reads {reading.value} and the record claims "
            f"{value}. No tolerance was declared, so C3 will not assert exact "
            f"equality on a comparison nobody specified",
        )

    difference = abs(reading.value - value)
    if difference <= tolerance:
        return (
            CheckOutcome.PASS,
            f"anchor {anchor_id!r} reads {reading.value}; the record claims "
            f"{value}, a difference of {difference} within the declared tolerance "
            f"of {tolerance}",
        )
    return (
        CheckOutcome.FAIL,
        f"anchor {anchor_id!r} reads {reading.value} but the record claims "
        f"{value}: a difference of {difference} exceeds the declared tolerance of "
        f"{tolerance}",
    )


def _compare_units(
    declared: str | None, reading: NumericReading, anchor_id: str
) -> tuple[CheckOutcome, str] | None:
    """Adjudicate the declared unit against the one the source states.

    ``None`` means "no contradiction found; proceed to the tolerance test".

    The rule is bounded, and the bound is the point: C3 compares unit *tokens*
    as written, lowercased. It does not convert and it does not know that
    ``kilograms`` and ``kg`` name the same unit -- see the module docstring for
    why an alias table would be a second implementation of unit semantics.

    Two consequences follow, and both are tested rather than asserted:

    * ``kg`` against ``g`` fails. Those are different tokens, and reading them as
      the same thing would be a silent conversion.
    * ``kg`` against ``kilograms`` fails too. That is a false negative, and it is
      the trade this module makes knowingly: a check that never passes an
      unrecognised unit is conservative, and the detail names both tokens so the
      reader can correct the record rather than guess why it failed.

    When the source states no unit at all there is nothing to contradict, and the
    record's declared unit is left unverified. That is the ordinary case for a
    bare numeric cell, and C3 passes on magnitude while saying so.
    """
    if reading.unit is None:
        return None

    observed = reading.unit.strip().lower()
    wanted = (declared or "").strip().lower()
    if wanted == observed:
        return None

    return (
        CheckOutcome.FAIL,
        f"anchor {anchor_id!r} reads {reading.raw!r}, whose unit is {observed!r}, "
        f"but the record declares {wanted!r}. C3 compares unit tokens as written "
        f"and does not convert between units",
    )


def _verdict(outcome: CheckOutcome, detail: str) -> Verdict:
    return Verdict(
        check=CheckKind.C3,
        outcome=outcome,
        checker_id=C3_CHECKER_ID,
        detail=detail,
    )
