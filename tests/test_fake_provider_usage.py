"""T09 — the truthfulness half: a measured zero and an absent measurement are different facts.

Two of the test names in this file are **binding test names** copied verbatim
from ``docs/adr/ADR-0002-model-and-tool-execution-boundary.md`` §"Contracts and
acceptance tests":

* ``test_usage_value_preserves_distinguishes_zero_from_unknown``
* ``test_usage_merge_is_not_sum_when_any_unknown``

ADR-0002 assigns the third of its usage tests
(``test_provider_omitting_usage_field_yields_unknown_not_zero``) to the
FakeProvider path; it lives in ``tests/test_fake_provider_usage_transcripts.py``
next to the fixtures it consumes rather than here, so this file stays a unit
test of the value types with no provider in it.

The contrast being guarded, from ADR-0002 §A2 and its pydantic-ai observation 1:

    MetricsSnapshot.accumulated_cost: float = Field(default=0.0, ge=0.0)
    cost = combined_metrics.accumulated_cost or 0.0
    # -> an unmeasured cost reads as $0 and the budget never trips.

    UsageBase.input_tokens: int = 0
    # -> tokens have no unknown state at all upstream

Each test below fails if someone "simplifies" ``Unknown`` into a zero.
"""

from __future__ import annotations

import pytest

from labcairn.core.providers import (
    Known,
    Unknown,
    UnknownReason,
    UnmeasuredQuantityError,
    format_usage,
    merge,
    require_known,
    usage_from_wire,
)

# ---------------------------------------------------------------------------
# The two states are distinct
# ---------------------------------------------------------------------------


def test_usage_value_preserves_distinguishes_zero_from_unknown() -> None:
    """ADR-0002 binding name. ``Known(0) != Unknown(...)``; ``Unknown`` has no ``__int__``."""
    zero = Known(0)
    absent = Unknown(UnknownReason.PROVIDER_OMITTED)

    # Unequal as values, unequal under ``==``, unequal as set members.
    # mypy calls this a non-overlapping comparison, which is the type system
    # independently asserting that ``Known`` and ``Unknown`` are disjoint —
    # the static half of the guarantee this test pins at runtime.
    assert zero != absent  # type: ignore[comparison-overlap]
    assert len({zero, absent}) == 2

    # ``Unknown`` carries no number. Both coercions a caller might reach for
    # fail loudly instead of producing a value.
    assert not hasattr(absent, "__int__")
    assert not hasattr(absent, "__float__")
    assert not hasattr(absent, "__index__")
    with pytest.raises(TypeError):
        int(absent)  # type: ignore[call-overload]
    with pytest.raises(TypeError):
        float(absent)  # type: ignore[arg-type]

    # And the zero really is a measurement: it converts, and it is zero.
    assert int(zero) == 0
    assert require_known(zero) == 0

    # Truthiness carries no magnitude information on *either* side. ``bool`` is
    # resolved via ``__bool__``/``__len__``, never ``__int__``, and neither type
    # defines those — so `if usage:` cannot be mistaken for `if usage > 0:`.
    assert bool(zero) is True
    assert bool(absent) is True


def test_known_zero_and_unknown_render_differently() -> None:
    """A report built from ``format_usage`` cannot show "unknown" as "0"."""
    assert format_usage(Known(0)) == "0"
    assert format_usage(Unknown(UnknownReason.PROVIDER_OMITTED)) == "unknown(provider_omitted)"
    assert format_usage(Known(12)) == "12"


def test_unknown_wire_form_never_yields_a_bare_integer() -> None:
    """``to_wire`` is a one-key tagged object, so no consumer can index a number out of it.

    This is the serialised half of the same guarantee: even code that never sees
    the classes — a JSON report, a SQLite column, a subprocess boundary — meets
    a *tagged* value, and the tag has to be read before a number exists.
    """
    known = Known(12).to_wire()
    unknown = Unknown(UnknownReason.UNPRICED).to_wire()

    assert known == {"known": 12}
    assert unknown == {"unknown": "unpriced"}

    # Mutually exclusive, single-key, and the wrong key is absent rather than None.
    assert set(known).isdisjoint(unknown)
    with pytest.raises(KeyError):
        _ = known["unknown"]
    with pytest.raises(KeyError):
        _ = unknown["known"]

    # Round-trips exactly.
    assert usage_from_wire(known) == Known(12)
    assert usage_from_wire(unknown) == Unknown(UnknownReason.UNPRICED)


# ---------------------------------------------------------------------------
# Merging never under-reports
# ---------------------------------------------------------------------------


def test_usage_merge_is_not_sum_when_any_unknown() -> None:
    """ADR-0002 binding name. An unknown operand poisons the total.

    The forbidden alternative is summing the known parts and reporting that as
    the total: ``merge(Known(5), Unknown(...)) == Known(5)`` would claim a run
    cost 5 tokens when one of the two numbers was never measured. Reporting a
    partial total is the same lie as reporting zero.
    """
    absent = Unknown(UnknownReason.PROVIDER_OMITTED)

    assert merge(Known(5), absent) == absent
    assert merge(absent, Known(5)) == absent
    assert isinstance(merge(Known(5), absent), Unknown)
    assert not isinstance(merge(Known(5), absent), Known)

    # Both known: an ordinary sum.
    assert merge(Known(5), Known(7)) == Known(12)

    # Zero is known, so zero + zero is a measured zero, not an unknown.
    assert merge(Known(0), Known(0)) == Known(0)


def test_usage_merge_is_commutative_and_associative() -> None:
    """Totals do not depend on the order the run happened to accumulate its steps in.

    Byte-identical replay depends on this: if ``merge`` were order-sensitive,
    two processes walking the same exchanges in the same order would still
    agree, but any future concurrent aggregation would not.
    """
    a, b = Known(5), Known(7)
    omitted = Unknown(UnknownReason.PROVIDER_OMITTED)
    unpriced = Unknown(UnknownReason.UNPRICED)

    assert merge(a, b) == merge(b, a)
    assert merge(omitted, unpriced) == merge(unpriced, omitted)

    # Associativity over a mixed triple.
    for left, middle, right in ((a, b, omitted), (omitted, unpriced, b), (a, omitted, b)):
        assert merge(merge(left, middle), right) == merge(left, merge(middle, right))


def test_usage_merge_unknown_reason_precedence_is_total_and_documented() -> None:
    """When both sides are unknown, the winner follows a declared order, not luck.

    Ordering the reasons is a LabCairn-owned decision — neither upstream has an
    equivalent to rank. The ranking below is stated in ``usage.py``; this test
    exists so that changing the ranking is a deliberate act that fails loudly
    rather than a silent reordering of what users are told.
    """
    omitted = Unknown(UnknownReason.PROVIDER_OMITTED)
    malformed = Unknown(UnknownReason.EXTRACTION_FAILED)
    unpriced = Unknown(UnknownReason.UNPRICED)

    # Least information wins: "no data at all" outranks "we could not read it",
    # which outranks "we have the number but cannot price it".
    assert merge(omitted, malformed) == omitted
    assert merge(malformed, unpriced) == malformed
    assert merge(omitted, unpriced) == omitted


# ---------------------------------------------------------------------------
# The single sanctioned exit to a number
# ---------------------------------------------------------------------------


def test_require_known_refuses_unknown_instead_of_substituting_zero() -> None:
    """``require_known`` is the only supported way to a number, and it fails closed."""
    for reason in UnknownReason:
        with pytest.raises(UnmeasuredQuantityError) as caught:
            require_known(Unknown(reason))
        assert caught.value.reason is reason
        # The message says what is wrong rather than what it would otherwise be.
        assert reason.value in str(caught.value)

    # It is a TypeError so that a handler written for `int(unknown)` catches it
    # too — nothing can tell the two apart and let one through as a zero.
    assert issubclass(UnmeasuredQuantityError, TypeError)


def test_arithmetic_over_unknown_raises_rather_than_treating_it_as_zero() -> None:
    """The three idioms that turn a missing measurement into a zero, all of which fail."""
    values: list[Known | Unknown] = [Known(3), Unknown(UnknownReason.PROVIDER_OMITTED)]

    # Each ``type: ignore`` below marks a line mypy **rejects**. That rejection
    # is half of what this test demonstrates: `strict` mode will not let the
    # fold be written at all. The `pytest.raises` is the other half — the
    # runtime agreeing with the type checker.
    with pytest.raises(TypeError):
        sum(values)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Known(3) + Unknown(UnknownReason.PROVIDER_OMITTED)  # type: ignore[operator]
    with pytest.raises(TypeError):
        sum([Unknown(UnknownReason.PROVIDER_OMITTED)])  # type: ignore[list-item]

    # And the OpenHands coercion, `cost or 0.0`, is not expressible either:
    # an Unknown instance is truthy, so it survives the `or` as itself rather
    # than yielding 0.0 and moving the lie somewhere downstream.
    coerced = Unknown(UnknownReason.PROVIDER_OMITTED) or 0.0
    assert isinstance(coerced, Unknown)
    assert coerced != 0.0  # type: ignore[comparison-overlap]


# ---------------------------------------------------------------------------
# coerce: the wire boundary contract from ADR-0002
# ---------------------------------------------------------------------------


def test_coerce_keeps_zero_known_and_maps_only_none_to_unknown() -> None:
    """``0`` stays ``Known(0)`` — a zero is a measurement. ADR-0002 §contracts 1."""
    reason = UnknownReason.EXTRACTION_FAILED

    assert Known.coerce(None, reason=reason) == Unknown(reason)
    assert Unknown.coerce(None, reason=reason) == Unknown(reason)

    for raw in (0, 1, 12, 10**9):
        assert Known.coerce(raw, reason=reason) == Known(raw)
        assert isinstance(Known.coerce(raw, reason=reason), Known)
        assert isinstance(Unknown.coerce(raw, reason=reason), Known)


def test_usage_from_wire_treats_unreadable_payloads_as_unknown_not_zero() -> None:
    """A payload we cannot read is a quantity we could not measure.

    Never a zero, and never a raise: a persisted record from a future provider
    version must still load, with the loss recorded rather than fabricated.
    """
    bad_payloads: tuple[object, ...] = (
        None,
        {},
        {"known": None},
        {"unknown": "not_a_real_reason"},
        {"known": True},
        [],
    )
    for payload in bad_payloads:
        restored = usage_from_wire(payload)
        assert isinstance(restored, Unknown)
        assert restored == Unknown(UnknownReason.EXTRACTION_FAILED)


def test_unknown_rejects_a_free_form_reason_string() -> None:
    """The closed set must be closed, not merely documented.

    `UnknownReason` claims "no free-form strings" in its docstring, but
    dataclasses do not coerce: `Unknown("unpriced")` used to construct fine,
    compared and hashed equal to the real member, and then raised
    `AttributeError: 'str' object has no attribute 'value'` at serialisation —
    far from the cause. Unreachable from product code today; cheap to close
    before LC-P1-03 puts budgets on top of it.
    """
    with pytest.raises(TypeError, match="UnknownReason"):
        Unknown("unpriced")  # type: ignore[arg-type]

    # And the closed set must remain closed to every wrong type, not just str.
    for wrong in (None, 0, 1.0, object()):
        with pytest.raises(TypeError):
            Unknown(wrong)  # type: ignore[arg-type]

    # A real member still constructs and behaves identically.
    ok = Unknown(UnknownReason.UNPRICED)
    assert ok == Unknown(UnknownReason.UNPRICED)
    assert ok.to_wire() == {"unknown": "unpriced"}
