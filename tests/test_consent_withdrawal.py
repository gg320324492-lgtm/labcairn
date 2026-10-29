"""Withdrawal, and the propagation that is checkable.

**What is under test.** LC-P2-06 T03: withdrawing a grant, and the
copies that depended on it.

**The question the design asks.** ADR-0015 D4: *"撤回同意后历史
embedding/缓存/训练队列是否失效"* — after consent is withdrawn, do the
historical embeddings, caches and training queues expire? **The answer has
to be a fact and not a promise**, because a promise about derived copies is
exactly the kind of claim that cannot be checked later.

**So the copy records its provenance**, and the check asks whether that
grant is still in force. A copy whose grant is **not on the record** is
stale too — treating "I cannot find the grant" as "the grant is fine"
would keep a copy alive on the strength of a missing row, which is the
wrong direction of error.

**And the withdrawal is not a deletion.** A permission check that cannot
say *"this was withdrawn by the advisor on 2026-03-02"* cannot answer the
question a person will ask, and the record of a grant that was withdrawn
is itself a record.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from labcairn.security.permissions import (
    DerivedCopy,
    Grant,
    is_copy_stale,
    stale_copies,
    withdraw_grant,
)

pytestmark = pytest.mark.integration

NOW = datetime(2026, 3, 2, 9, 15, tzinfo=UTC)


def _grant(
    grant_id: str = "g1",
    *,
    state: str = "active",
    withdrawn_by: str | None = None,
    withdrawn_at: datetime | None = None,
) -> Grant:
    return Grant(
        grant_id=grant_id,
        subject_ref="proj-1",
        permission="store_read",
        purpose="read",
        scope="proj-1/**",
        destination=None,
        granted_by="Dr. Chen",
        granted_at=NOW,
        expires_at=None,
        state=state,
        withdrawn_at=withdrawn_at,
        withdrawn_by=withdrawn_by,
        withdrawal_reason=None,
    )


def _copy(copy_id: str = "c1", grant_id: str = "g1") -> DerivedCopy:
    return DerivedCopy(
        copy_id=copy_id,
        grant_id=grant_id,
        kind="embedding",
        location=f"vectors/{copy_id}",
        subject_ref="proj-1",
    )


# --------------------------------------------------------------------------- #
# the withdrawal
# --------------------------------------------------------------------------- #


def test_a_withdrawal_records_who_and_when() -> None:
    """**A withdrawal with nobody behind it is a refusal nobody made.**

    **What breaks it:** a withdrawal that moves the state and names
    nobody. The row would say the permission was taken back and attribute
    it to no one, and a check that cannot say *who* withdrew it cannot
    answer the question a person will ask.
    """
    withdrawn = withdraw_grant(_grant(), withdrawn_by="Prof. Lin", at=NOW)

    assert withdrawn.state == "withdrawn"
    assert withdrawn.withdrawn_by == "Prof. Lin"
    assert withdrawn.withdrawn_at == NOW


def test_a_withdrawal_by_nobody_is_refused() -> None:
    """A withdrawal names the person who made it."""
    with pytest.raises(ValueError) as refused:
        withdraw_grant(_grant(), withdrawn_by="   ", at=NOW)
    assert "must name them" in str(refused.value)


def test_a_withdrawal_twice_is_refused() -> None:
    """**The record says one thing about one decision.**

    **What breaks it:** a second withdrawal overwriting the first. The row
    would name two people for one decision, and the question "who took this
    back?" would have two answers.
    """
    withdrawn = withdraw_grant(_grant(), withdrawn_by="Prof. Lin", at=NOW)

    with pytest.raises(ValueError) as refused:
        withdraw_grant(withdrawn, withdrawn_by="Dr. Chen", at=NOW)
    assert "already withdrawn" in str(refused.value)


def test_the_grant_row_is_kept_and_not_deleted() -> None:
    """**The record of a grant that was withdrawn is itself a record.**

    **What breaks it:** deleting the row on withdrawal. The permission
    check could then no longer answer *"was this ever granted?"* — and the
    difference between *"never permitted"* and *"permitted and then taken
    back"* is a question about a person.
    """
    withdrawn = withdraw_grant(_grant(), withdrawn_by="Prof. Lin", at=NOW)

    assert withdrawn.grant_id == "g1"
    assert withdrawn.granted_by == "Dr. Chen"
    assert withdrawn.granted_at == NOW
    assert withdrawn.state == "withdrawn"


# --------------------------------------------------------------------------- #
# the propagation
# --------------------------------------------------------------------------- #


def test_a_withdrawn_grant_invalidates_the_copies_derived_from_it() -> None:
    """**The question the design asks, answered as a fact.**

    **What breaks it:** a copy with no provenance, or a check that ignores
    it. Either way the copy outlives the grant, and the answer to *"do the
    historical embeddings expire when consent is withdrawn?"* would be no.
    """
    grant = _grant()
    copy = _copy()

    assert is_copy_stale(copy, [grant]) is False

    withdrawn = withdraw_grant(grant, withdrawn_by="Prof. Lin", at=NOW)
    assert is_copy_stale(copy, [withdrawn]) is True


def test_the_stale_copies_are_listed_and_not_a_promise() -> None:
    """**The list is what a withdrawal has to act on.**

    **What breaks it:** a check that returns a boolean. A boolean says
    *something* is stale and does not say *what*, and a withdrawal has to
    find the copies to act on it.

    **And all three copies are stale, for two different reasons.** ``c1``
    and ``c3`` were made under a grant that has been withdrawn; ``c2`` was
    made under a grant that **is not on the record at all**, which is
    stale by the same rule -- a missing row is not a live grant. The
    withdrawal is what reached the first two; the second was already
    unauthorised.
    """
    grants = [_grant("g1")]
    copies = [
        _copy("c1", "g1"),
        _copy("c2", "g2"),
        _copy("c3", "g1"),
    ]

    withdrawn = withdraw_grant(grants[0], withdrawn_by="Prof. Lin", at=NOW)

    assert stale_copies(copies, [withdrawn]) == (copies[0], copies[1], copies[2])


def test_a_copy_whose_grant_is_not_on_the_record_is_stale() -> None:
    """**A missing row is not a live grant.**

    **What breaks it:** treating "I cannot find the grant" as "the grant
    is fine". That would keep a copy alive on the strength of a missing
    row — **the wrong direction of error**, because the cost of a stale
    copy that is believed live is the material having left the machine
    anyway.
    """
    copy = _copy(grant_id="g-not-on-record")

    assert is_copy_stale(copy, []) is True


def test_a_copy_of_a_still_live_grant_is_not_stale() -> None:
    """The ordinary case: the grant is in force, the copy is fine."""
    assert is_copy_stale(_copy(), [_grant()]) is False


def test_an_expired_grant_also_makes_its_copies_stale() -> None:
    """A grant that ran out is not a live grant either.

    **What breaks it:** checking only the withdrawal state. A grant whose
    window closed produced the same copies, and those copies are just as
    unauthorised as the ones a withdrawal orphaned.
    """
    expired = Grant(
        **{
            **_grant().__dict__,
            "state": "expired",
        }
    )
    assert is_copy_stale(_copy(), [expired]) is True


def test_the_withdrawal_keeps_the_copies_addressable() -> None:
    """**A stale copy is still a copy.** The check says it is stale; it
    does not make it disappear.

    **What breaks it:** the check deleting the copy as a side effect. A
    withdrawal has to find the copies, and the ones it has already
    handled are still the record of what was made.
    """
    grant = _grant()
    copy = _copy()
    withdrawn = withdraw_grant(grant, withdrawn_by="Prof. Lin", at=NOW)

    stale = stale_copies([copy], [withdrawn])

    assert len(stale) == 1
    assert stale[0].copy_id == copy.copy_id
    assert stale[0].location == copy.location
    assert stale[0].kind == copy.kind
