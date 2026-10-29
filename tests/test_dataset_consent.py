"""Whether a use is permitted, and what the refusal says.

**What is under test.** LC-P2-06 T01: the permission check, and the six
refusals it can return.

**The property at the centre.** ADR-0015 D2: *"Not 'denied until granted'
as a UI default — **denied in the model**. There is no row, so there is
nothing to check, so the path cannot proceed."* So a use with no grant is
refused, and **the refusal is a normal answer on this path rather than an
exception** — a model request with no transmit grant must be refused *with
a reason*, not crash.

**And the property that makes the refusal useful.** A refusal that says
only "no" is true and useless. *"You have a read grant but not a transmit
grant"* is an answer a person can act on, so **the reason names the closest
grant**, and the closest grant is the one that got the furthest.

**And the distinction between two refusals.** A grant that was
**withdrawn** is not a grant that was **never made**, and only the first is
a question about a person.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from labcairn.security.permissions import (
    ConsentDecision,
    ConsentRefusal,
    Grant,
    may_use,
)

NOW = datetime(2026, 3, 2, 9, 15, tzinfo=UTC)


def _grant(
    grant_id: str = "g1",
    *,
    subject_ref: str = "proj-1",
    permission: str = "store_read",
    purpose: str = "read",
    scope: str = "proj-1",
    destination: str | None = None,
    granted_by: str = "Dr. Chen",
    granted_at: datetime = NOW,
    expires_at: datetime | None = None,
    state: str = "active",
    withdrawn_at: datetime | None = None,
    withdrawn_by: str | None = None,
    withdrawal_reason: str | None = None,
) -> Grant:
    return Grant(
        grant_id=grant_id,
        subject_ref=subject_ref,
        permission=permission,
        purpose=purpose,
        scope=scope,
        destination=destination,
        granted_by=granted_by,
        granted_at=granted_at,
        expires_at=expires_at,
        state=state,
        withdrawn_at=withdrawn_at,
        withdrawn_by=withdrawn_by,
        withdrawal_reason=withdrawal_reason,
    )


def _decide(grants: list[Grant], **overrides: object) -> ConsentDecision:
    arguments = {
        "permission": "store_read",
        "purpose": "read",
        "subject_ref": "proj-1",
        "at": NOW,
    }
    arguments.update(overrides)
    return may_use(grants, **arguments)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# the permission
# --------------------------------------------------------------------------- #


def test_a_grant_in_force_permits_the_use() -> None:
    """The ordinary case, and the receipt that goes with it.

    **What breaks it:** a decision that says "allowed" without naming the
    grant. The answer would be true and untraceable — and a withdrawal
    could not find the uses that were permitted under the grant it
    revokes.
    """
    grant = _grant()
    decision = _decide([grant])

    assert decision.allowed is True
    assert decision.grant_id == "g1"
    assert decision.reason is None
    assert "g1" in decision.detail
    assert "Dr. Chen" in decision.detail


def test_no_grant_is_a_refusal_and_not_an_exception() -> None:
    """**The absence of a row is the refusal.**

    **What breaks it:** a default-permitted path, or a raised exception.
    Both are wrong in the same way: a caller would have to catch an
    exception to learn that it may not do something, and a default-permitted
    path would make the missing grant invisible.
    """
    decision = _decide([])

    assert decision.allowed is False
    assert decision.reason is ConsentRefusal.NO_GRANT
    assert decision.grant_id is None
    assert "no grant" in decision.detail.lower()


def test_a_permission_with_no_row_is_denied_by_absence() -> None:
    """The four permissions are four grant kinds, and each is absent on
    its own.

    **What breaks it:** a grant for one permission standing in for another.
    A read grant is not a transmit grant.

    **And the refusal names the closest grant, which is the read one** --
    so the reason is *purpose*, not *permission*: the grant covers a
    permission and not the purpose. That is the more useful answer, and it
    is the difference between "you have nothing" and "you have the wrong
    thing".
    """
    read_only = [_grant(permission="store_read", purpose="read")]

    decision = _decide(
        read_only,
        permission="external_transmit",
        purpose="transmit",
        destination="api.minimax.cn",
    )

    assert decision.allowed is False
    assert decision.reason is ConsentRefusal.PURPOSE_NOT_GRANTED
    assert decision.closest is not None
    assert decision.closest.permission == "store_read"


# --------------------------------------------------------------------------- #
# the refusals, and what they say
# --------------------------------------------------------------------------- #


def test_a_refusal_names_what_would_satisfy_it() -> None:
    """**A refusal that says only "no" is true and useless.**

    **What breaks it:** a detail that names the fault but not the remedy.
    The remedy is the part the person needs, and the project's own rule for
    a refusal is that it names the fault — and the remedy is part of the
    fault.
    """
    grant = _grant(permission="store_read", purpose="read")
    decision = _decide(
        [grant],
        permission="external_transmit",
        purpose="transmit",
        destination="api.minimax.cn",
    )

    assert decision.allowed is False
    assert decision.reason is ConsentRefusal.PURPOSE_NOT_GRANTED
    assert "grant" in decision.detail
    assert "remedy" in decision.detail
    # The closest grant is named, so the reader knows which one to look at.
    assert decision.closest is not None
    assert decision.closest.grant_id == "g1"


def test_a_grant_for_another_purpose_is_refused_by_purpose() -> None:
    """The purpose is a separate axis from the permission.

    **What breaks it:** a check that looks only at the permission. The
    design's four purposes are narrower than the permissions, and "the
    permission is right but the purpose is wrong" is the case the separate
    axis exists for.
    """
    grant = _grant(permission="store_read", purpose="read")
    decision = _decide([grant], purpose="retrieve")

    assert decision.allowed is False
    assert decision.reason is ConsentRefusal.PURPOSE_NOT_GRANTED
    assert "retrieve" in decision.detail


def test_a_grant_for_one_destination_does_not_authorise_another() -> None:
    """**ADR-0015 D3's rule, and the reason the destination is a field.**

    **What breaks it:** a check that treats any transmit grant as a
    transmit grant. A grant naming provider A must not authorise provider
    B, and the refusal has to name both.
    """
    grant = _grant(
        permission="external_transmit",
        purpose="transmit",
        destination="api.minimax.cn",
    )

    refused = _decide(
        [grant],
        permission="external_transmit",
        purpose="transmit",
        destination="api.openai.com",
    )

    assert refused.allowed is False
    assert refused.reason is ConsentRefusal.DESTINATION_NOT_GRANTED
    assert "api.minimax.cn" in refused.detail
    assert "api.openai.com" in refused.detail

    # And the granted destination is permitted.
    permitted = _decide(
        [grant],
        permission="external_transmit",
        purpose="transmit",
        destination="api.minimax.cn",
    )
    assert permitted.allowed is True


def test_a_withdrawn_grant_is_refused_as_withdrawn() -> None:
    """**A withdrawn grant is not a grant that was never made.**

    **What breaks it:** reporting a withdrawal as "no grant". The two are
    true in the same moment and different in every other: *"was this
    permitted once and then taken back?"* is a question about a person, and
    only the first can answer it.
    """
    grant = _grant(
        state="withdrawn",
        withdrawn_by="Dr. Chen",
        withdrawn_at=NOW,
        withdrawal_reason="the material left the lab",
    )
    decision = _decide([grant])

    assert decision.allowed is False
    assert decision.reason is ConsentRefusal.GRANT_WITHDRAWN
    assert "Dr. Chen" in decision.detail
    assert "withdrawn" in decision.detail.lower()


def test_an_expired_grant_is_refused_as_expired() -> None:
    """A grant that has run out is refused, and says so.

    **What breaks it:** a check that compares only the state. A grant whose
    expiry has passed is still ``active`` by state until the clock says
    otherwise.
    """
    grant = _grant(expires_at=NOW - timedelta(days=1))
    decision = _decide([grant])

    assert decision.allowed is False
    assert decision.reason is ConsentRefusal.GRANT_EXPIRED
    assert "run out" in decision.detail


def test_a_grant_that_has_not_opened_yet_is_refused_as_such() -> None:
    """**Both ends of the window.**

    **What breaks it:** a check that only looks at the expiry. A grant
    recorded for a future window is not yet in force, and the refusal is
    different from an expired one: the remedy is to wait, not to grant.
    """
    grant = _grant(granted_at=NOW + timedelta(days=1))
    decision = _decide([grant], at=NOW)

    assert decision.allowed is False
    assert decision.reason is ConsentRefusal.GRANT_NOT_YET_ACTIVE
    assert "wait" in decision.detail


def test_a_grant_whose_scope_does_not_reach_the_material_is_refused() -> None:
    """The scope is what the grant covers, and it is narrow.

    **What breaks it:** a scope check that treats a prefix as a wildcard.
    A grant that says "this paper" and is read as "this paper and anything
    else" is a grant that has been widened by a guess, and it is the
    narrow reading that is safe.
    """
    # **The grant belongs to this project** -- otherwise the refusal would
    # be "no grant", which is a different fact.
    grant = _grant(scope="proj-1/drafts/**")
    decision = _decide([grant], material_ref="proj-1/final/submission.docx")

    assert decision.allowed is False
    assert decision.reason is ConsentRefusal.SCOPE_NOT_COVERED
    assert "scope" in decision.detail


# --------------------------------------------------------------------------- #
# the scope rules
# --------------------------------------------------------------------------- #


def test_a_wildcard_scope_covers_what_is_under_it() -> None:
    """``proj-1/**`` covers ``proj-1`` and everything under it.

    **What breaks it:** a scope that matched nothing, which would make
    every broad grant useless and push people towards narrow ones.
    """
    grant = _grant(scope="proj-1/**", subject_ref="proj-1")

    assert _decide([grant]).allowed is True
    # **The material is a separate question from the subject**: the grant
    # belongs to proj-1, and its scope reaches into it.
    assert _decide([grant], material_ref="proj-1/drafts/v2.docx").allowed is True


def test_a_wildcard_scope_does_not_cover_a_sibling() -> None:
    """``proj-1/**`` does not cover ``proj-10``.

    **What breaks it:** a prefix match without the separator. ``proj-10``
    starts with ``proj-1``, and a scope that covered it would let a grant
    for one manuscript reach another — which is the cross-project
    failure the version graph already refuses.
    """
    grant = _grant(scope="proj-1/**", subject_ref="proj-1")
    decision = _decide([grant], subject_ref="proj-10")

    assert decision.allowed is False
    # And the scope does not reach a sibling's material either.
    sibling = _decide([grant], material_ref="proj-10/drafts/v1.docx")
    assert sibling.allowed is False


# --------------------------------------------------------------------------- #
# the vocabulary
# --------------------------------------------------------------------------- #


def test_a_permission_outside_the_vocabulary_is_refused() -> None:
    """**A permission that could hold any string is a permission nobody
    holds.**

    **What breaks it:** widening the vocabulary. A typo would sail
    through and be indistinguishable from a real permission.
    """
    with pytest.raises(ValueError) as refused:
        _decide([], permission="transmit")
    assert "four permissions" in str(refused.value)


def test_a_purpose_outside_the_vocabulary_is_refused() -> None:
    """The five purposes are closed, on the same standard."""
    with pytest.raises(ValueError) as refused:
        _decide([], purpose="read_it")
    assert "five purposes" in str(refused.value)


def test_a_grant_for_another_subject_does_not_answer_for_this_one() -> None:
    """A grant covers one subject.

    **What breaks it:** a check that ignores the subject. A grant for one
    manuscript would permit a use of another, and the cross-project
    refusal the version graph holds would not hold here.
    """
    grant = _grant(subject_ref="proj-2")
    decision = _decide([grant])

    assert decision.allowed is False
    assert decision.reason is ConsentRefusal.NO_GRANT


def test_the_decision_is_frozen() -> None:
    """A decision is a record, and a record does not change.

    **What breaks it:** a mutable decision. The decision says a use was
    permitted on the strength of a grant, and a decision that could be
    edited in place is not the receipt it claims to be.
    """
    decision = _decide([_grant()])
    with pytest.raises((AttributeError, TypeError)):
        decision.allowed = False  # type: ignore[misc]
