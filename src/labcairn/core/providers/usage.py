"""Tri-state quantities: **a measured number, or a recorded reason it is not known.**

This module is the whole of LC-P1-01's honesty contract, and it is deliberately
small. Amendment C-3 to LC-P1-01 allows exactly four names — ``UnknownReason``,
``Known``, ``Unknown``, ``UsageValue`` — plus the helpers that keep them apart.
Nothing here performs I/O, reads a clock, or knows what a provider is.

Why this exists
---------------
``docs/adr/ADR-0002-model-and-tool-execution-boundary.md`` §A2 records the
concrete upstream failure this type is written against:

    MetricsSnapshot.accumulated_cost: float = Field(default=0.0, ge=0.0)
    cost = combined_metrics.accumulated_cost or 0.0      # visualizer/default.py:447
    # _budget_exceeded_detail (local_conversation.py:727-741) then compares
    #   spent < self.max_budget_per_run  -- an unknown cost reads as $0 and
    #   the budget never trips.

pydantic-ai has the same hole on the other side of the coin
(``tests/test_usage_limits.py:1162``, ``test_usage_unknown_provider``: an
unrecognised provider yields ``RequestUsage()``, every counter zero,
indistinguishable from a genuinely free request). Neither upstream lets you
write the bug on purpose, which is the standard both of them miss.

The shape that does
-------------------
Three properties, each structural rather than documentary:

1. ``Unknown`` defines no ``__int__``, ``__float__``, ``__index__`` and no
   arithmetic dunders. ``int(unknown)``, ``float(unknown)`` and ``sum(...)``
   over a list containing one therefore raise ``TypeError`` **at the call
   site**. There is no ``__int__`` to reach for by accident, so there is no
   "temporary" coercion that survives review.
2. ``merge()`` is the only way to total two quantities and it returns
   ``Unknown`` whenever either side is ``Unknown``. Under-reporting a total
   that is partly unmeasurable is the same lie as reporting zero.
3. ``to_wire()`` serialises to ``{"known": 12}`` or ``{"unknown": "..."}`` —
   a one-key object with mutually exclusive discriminators. A consumer that
   indexes the payload for a number gets a ``KeyError`` on the unknown form,
   never a bare integer standing in for "we could not measure this".

What is *not* here, and why the boundary is drawn here
------------------------------------------------------
No budget. No ceiling. No provider probe. No cancel/timeout. Amendment C-3
assigns those to LC-P1-03, and this module is shaped so LC-P1-03 can build on
it rather than around it:

* ``merge`` and ``require_known`` are total and side-effect-free, so a budget
  check is a pure comparison layered on top — no rewrite needed.
* ``UnknownReason`` is a closed ``StrEnum``. LC-P1-03's ``BudgetEnforcementUnavailable``
  can name a reason without inventing a new vocabulary, and a persisted reason
  stays stable across releases because the wire values are frozen strings.
* Nothing validates *semantics* (is this a plausible token count? is it
  negative?). LC-P1-03 knows the answer; this layer does not and must not
  guess. Wire-shape validation lives at the parse boundary in
  :mod:`labcairn.core.providers.protocol`, where "a provider's token count is a
  non-negative integer" is actually a true statement.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class UnknownReason(StrEnum):
    """Why a quantity could not be measured. Closed set: no free-form strings.

    The four members are the exact set ADR-0002 §"LabCairn's own contracts"
    item 1 names (``ProviderOmitted | ExtractionFailed | NotApplicable |
    Unpriced``). They are deliberately distinct rather than one generic
    ``UNKNOWN`` because a report that says *why* it cannot price a run is the
    difference between a user raising a ceiling and a user filing a bug.
    """

    #: The provider returned no ``usage`` block, or the field inside it was
    #: absent or ``null``. Nothing was measured. Upstream reports this as 0.
    PROVIDER_OMITTED = "provider_omitted"
    #: A value was present but not a usable number of the expected kind
    #: (``"12"``, ``True``, ``-3``, a nested object). Data arrived; it did not parse.
    EXTRACTION_FAILED = "extraction_failed"
    #: The quantity has no meaning for this call at all (e.g. a cache-write
    #: counter on a run that never hit the cache). Still *not* zero.
    NOT_APPLICABLE = "not_applicable"
    #: The measurement is fine but no price is known for this model/endpoint,
    #: so a money figure cannot be derived. LC-P1-03 fails closed on this one.
    UNPRICED = "unpriced"


#: Precedence used when two ``Unknown`` sides are merged.
#:
#: Lowest index wins. ``merge`` is commutative and associative under this
#: order, which is what keeps a run total independent of the order the run
#: happened to accumulate its steps in — a determinism property the byte-identity
#: test depends on.
#:
#: The ranking is a LabCairn-owned judgement; neither upstream has an
#: equivalent to rank. It answers "which reason is the most informative thing to
#: tell the user?" — a total absence of data outranks a parse failure, which
#: outranks "we have the number but no price for it", which outranks "this
#: field was never applicable anyway".
_UNKNOWN_PRECEDENCE: Final[tuple[UnknownReason, ...]] = (
    UnknownReason.PROVIDER_OMITTED,
    UnknownReason.EXTRACTION_FAILED,
    UnknownReason.UNPRICED,
    UnknownReason.NOT_APPLICABLE,
)


@dataclass(frozen=True, slots=True)
class Known:
    """A measured quantity.

    ``Known(0)`` is a real, load-bearing state: the provider told us zero and we
    believed it. It is not the absence of a measurement, and the two never
    compare equal, hash alike, or serialise the same way.

    Note what is **absent**: there is no ``__bool__``. Python resolves
    ``bool(x)`` via ``__bool__`` then ``__len__`` and never via ``__int__``, so
    both ``Known`` and ``Unknown`` instances are truthy. Truthiness therefore
    carries *no* magnitude information and cannot be mistaken for a comparison
    against zero. The only supported questions are ``isinstance(v, Known)`` and
    :func:`require_known`.
    """

    #: The measured value. This type does not range-check: whether a negative
    #: or absurd number is legal depends on the quantity, and LC-P1-03 owns that
    #: question. Range rules live at the wire boundary instead.
    value: int

    def __int__(self) -> int:
        return self.value

    def to_wire(self) -> Mapping[str, object]:
        """Serialise as a one-key object, never as a bare integer.

        The point of the wrapper is that ``{"known": 0}`` and
        ``{"unknown": "provider_omitted"}`` cannot be confused by a consumer
        that forgets to branch. See :func:`usage_from_wire` for the inverse.
        """
        return {"known": self.value}

    @classmethod
    def coerce(cls, raw: int | None, *, reason: UnknownReason) -> UsageValue:
        """``None`` in, ``Unknown`` out. ``0`` stays ``Known(0)`` — a zero is a measurement.

        The single entry point for "the provider may or may not have given us a
        number". Both classes expose it so call sites read as
        ``Known.coerce(...)`` at the wire boundary without importing ``Unknown``
        first.
        """
        return Unknown(reason=reason) if raw is None else cls(raw)


@dataclass(frozen=True, slots=True)
class Unknown:
    """A quantity that was **not** measured, and why.

    There is no numeric value here and no ``__int__``. That is the feature: the
    two ways one might be tempted to turn this into a number — ``int(u)`` and
    ``u or 0`` — both fail loudly, the first with ``TypeError`` and the second
    because a bare instance is truthy and therefore keeps its own truthiness
    instead of silently yielding a number downstream.
    """

    reason: UnknownReason

    def to_wire(self) -> Mapping[str, object]:
        return {"unknown": self.reason.value}

    @classmethod
    def coerce(cls, raw: int | None, *, reason: UnknownReason) -> UsageValue:
        """See :meth:`Known.coerce`. Identical contract, mirrored for readability."""
        return cls(reason=reason) if raw is None else Known(raw)


#: A quantity is either measured or explicitly not. Never ``None``, never a
#: sentinel, never a float that might be a stand-in for a missing number.
type UsageValue = Known | Unknown


class UnmeasuredQuantityError(TypeError):
    """Raised when a caller demands a number from a quantity that has none.

    Subclasses ``TypeError`` on purpose. ``int(unknown)`` raises ``TypeError``
    and :func:`require_known` should be indistinguishable from that to any
    generic handler, so a call site cannot accidentally special-case one and let
    the other through to a ``0``.
    """

    def __init__(self, reason: UnknownReason) -> None:
        super().__init__(f"quantity is unknown ({reason.value}); refusing to substitute a number")
        self.reason = reason


def require_known(value: UsageValue) -> int:
    """The **only** sanctioned exit from a :data:`UsageValue` to a number.

    Deliberately not named ``int``, ``get``, ``unwrap`` or ``value``: the name
    should read as an assertion at the call site. If you reach for this, you are
    telling the reader that the measurement exists — when it does not, this
    raises :class:`UnmeasuredQuantityError` rather than producing a zero.
    """
    if isinstance(value, Known):
        return value.value
    raise UnmeasuredQuantityError(value.reason)


def merge(a: UsageValue, b: UsageValue) -> UsageValue:
    """Total two quantities. ``Known`` + ``Known`` adds; anything else stays ``Unknown``.

    This is the "total()" helper ADR-0002 §Risks promises. The asymmetric
    alternative — summing the known parts and reporting that as the total — is
    precisely the lie the work order forbids, so it is not offered.
    """
    if isinstance(a, Known) and isinstance(b, Known):
        return Known(a.value + b.value)
    reasons = [side.reason for side in (a, b) if isinstance(side, Unknown)]
    # `min` over the declared order: index 0 is the most informative reason, so
    # the lowest index has to win. `max` here would invert the whole ranking and
    # report "not applicable" where the truth was "nothing came back at all".
    return Unknown(reason=min(reasons, key=_UNKNOWN_PRECEDENCE.index))


def format_usage(value: UsageValue) -> str:
    """Render for display. The sanctioned way to put a quantity in front of a user.

    Never returns a bare number for an unknown value: the rendered string says
    ``unknown(<reason>)``, so a transcript diff cannot mistake "we could not
    measure this" for "this was zero".
    """
    return str(value.value) if isinstance(value, Known) else f"unknown({value.reason.value})"


def usage_from_wire(payload: object) -> UsageValue:
    """Rebuild a :data:`UsageValue` from its :meth:`~Known.to_wire` form.

    Returns ``Unknown`` rather than raising on an unrecognised payload: a record
    that cannot be understood is a quantity we could not measure, and saying so
    is exactly the behaviour under test.
    """
    if isinstance(payload, Mapping) and len(payload) == 1:
        known, unknown = payload.get("known"), payload.get("unknown")
        if isinstance(known, int) and not isinstance(known, bool):
            return Known(known)
        if isinstance(unknown, str):
            try:
                return Unknown(reason=UnknownReason(unknown))
            except ValueError:
                return Unknown(reason=UnknownReason.EXTRACTION_FAILED)
    return Unknown(reason=UnknownReason.EXTRACTION_FAILED)


def usage_to_json(value: UsageValue) -> str:
    """Canonical single-line JSON for :data:`UsageValue`. Keys sorted, no whitespace."""
    return json.dumps(value.to_wire(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
