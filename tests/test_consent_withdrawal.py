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

**And a grant is asked at a moment, not read from a column.** An expiry is
a **clock fact**: nothing in the product ever writes ``state='expired'`` on
an access grant, so a grant whose window has closed is still ``active`` in
the row. **A witness that builds the expired grant by hand writes a state
the product cannot reach**, and then it watches a branch that never runs.
So the expired grant below is built the way the product can actually
produce one — ``expires_at`` in the past and the state still ``active`` —
and the hand-written ``state='expired'`` case is kept beside it as what it
is: a second way of saying the same thing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from labcairn.security.permissions import (
    ConsentRefusal,
    DerivedCopy,
    Grant,
    is_copy_stale,
    may_use,
    stale_copies,
    withdraw_grant,
)

pytestmark = pytest.mark.integration

NOW = datetime(2026, 3, 2, 9, 15, tzinfo=UTC)


def _grant(
    grant_id: str = "g1",
    *,
    state: str = "active",
    granted_at: datetime = NOW,
    expires_at: datetime | None = None,
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
        granted_at=granted_at,
        expires_at=expires_at,
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

    assert is_copy_stale(copy, [grant], at=NOW) is False

    withdrawn = withdraw_grant(grant, withdrawn_by="Prof. Lin", at=NOW)
    assert is_copy_stale(copy, [withdrawn], at=NOW) is True


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

    assert stale_copies(copies, [withdrawn], at=NOW) == (copies[0], copies[1], copies[2])


def test_a_copy_whose_grant_is_not_on_the_record_is_stale() -> None:
    """**A missing row is not a live grant.**

    **What breaks it:** treating "I cannot find the grant" as "the grant
    is fine". That would keep a copy alive on the strength of a missing
    row — **the wrong direction of error**, because the cost of a stale
    copy that is believed live is the material having left the machine
    anyway.
    """
    copy = _copy(grant_id="g-not-on-record")

    assert is_copy_stale(copy, [], at=NOW) is True


def test_a_copy_of_a_still_live_grant_is_not_stale() -> None:
    """The ordinary case: the grant is in force, the copy is fine."""
    assert is_copy_stale(_copy(), [_grant()], at=NOW) is False


def test_a_grant_whose_window_has_closed_makes_its_copies_stale() -> None:
    """**The expiry the product can actually produce.**

    **A grant that ran out is not a live grant either**, and its copies
    are just as unauthorised as the ones a withdrawal orphaned.

    **What breaks it:** a check that reads the state column. The grant
    here has the shape every real expiry has — ``expires_at`` in the past
    and the state still ``active``, because **nothing in the product ever
    writes ``state='expired'``**. A check that asks the column instead of
    the clock keeps this copy alive on the strength of a row that says
    nothing about the window.

    **And the permission check refuses the same grant.** The two ask one
    question of one grant, so they cannot disagree: ``may_use`` reports
    ``grant_expired`` while ``is_copy_stale`` said the copy was fresh.
    """
    expired = _grant(expires_at=NOW - timedelta(days=1))

    # The state is what the product leaves behind, and it says nothing
    # about the window.
    assert expired.state == "active"
    assert expired.is_in_force(NOW) is False

    assert is_copy_stale(_copy(), [expired], at=NOW) is True


def test_the_copy_check_and_the_permission_check_do_not_disagree() -> None:
    """**One grant, one question, one answer.**

    **What breaks it:** the two checks asking the grant different
    questions. ``may_use`` refuses a grant whose window has closed, and
    the copy check used to call a copy made under the very same grant
    fresh — so the product said *"you may not use this"* and *"the
    derived copy is fine"* about one row, at one moment.

    **They are the same rule now, asked at the same moment**, and this is
    the witness that says so.
    """
    expired = _grant(expires_at=NOW - timedelta(days=1))

    decision = may_use(
        [expired],
        permission="store_read",
        purpose="read",
        subject_ref="proj-1",
        material_ref="proj-1/drafts/v1.docx",
        at=NOW,
    )

    assert decision.allowed is False
    assert decision.reason == ConsentRefusal.GRANT_EXPIRED
    assert is_copy_stale(_copy(), [expired], at=NOW) is True


def test_a_grant_marked_expired_by_hand_also_makes_its_copies_stale() -> None:
    """**The same property, said a second way.**

    A grant whose state was written to ``expired`` by hand is not a live
    grant either. **The product never writes that state**, so this case
    is not the reachable one — the clock case above is — but the check
    must still refuse it rather than pass on the strength of a vocabulary
    the product does not use.
    """
    expired = Grant(
        **{
            **_grant().__dict__,
            "state": "expired",
        }
    )
    assert is_copy_stale(_copy(), [expired], at=NOW) is True


def test_a_copy_of_a_grant_that_has_not_run_out_is_not_stale() -> None:
    """**The clock decides, and a live window is a live window.**

    **What breaks it:** a check that treats the *presence* of an expiry
    as the expiry. A grant that runs out next week is in force today, and
    its copies are in force today too — otherwise every standing grant
    would silently orphan the copies made under it.
    """
    live = _grant(expires_at=NOW + timedelta(days=1))

    assert live.is_in_force(NOW) is True
    assert is_copy_stale(_copy(), [live], at=NOW) is False


def test_a_copy_of_a_grant_that_has_not_opened_yet_is_stale() -> None:
    """**The window is both ends, for the copy as well as for the use.**

    **What breaks it:** a check that asks only "has it expired?". A grant
    whose window has not opened cannot have authorised anything yet, so
    the copy made under it is unauthorised — and the wrong direction of
    error is the expensive one.
    """
    future = _grant(granted_at=NOW + timedelta(days=1))

    assert future.is_in_force(NOW) is False
    assert is_copy_stale(_copy(), [future], at=NOW) is True


def test_the_stale_copies_include_the_ones_whose_grant_ran_out() -> None:
    """**The list has to carry the expiry half too.**

    **What breaks it:** a list that finds the withdrawn copies and misses
    the expired ones. A withdrawal has to act on the whole list, and the
    copy whose grant has merely run out is on it as much as the one whose
    grant was taken back.
    """
    expired = _grant("g-expired", expires_at=NOW - timedelta(days=1))
    live = _grant("g-live", expires_at=NOW + timedelta(days=1))
    copies = [_copy("c-expired", "g-expired"), _copy("c-live", "g-live")]

    assert stale_copies(copies, [expired, live], at=NOW) == (copies[0],)


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

    stale = stale_copies([copy], [withdrawn], at=NOW)

    assert len(stale) == 1
    assert stale[0].copy_id == copy.copy_id
    assert stale[0].location == copy.location
    assert stale[0].kind == copy.kind
