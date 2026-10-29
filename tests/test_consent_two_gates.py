"""The two gates, and the order they run in.

**What is under test.** LC-P2-06 T02: the transmit gate, and the rule
that it runs **before** the approval is consumed.

**The property at the centre.** A request refused for want of a transmit
grant must leave the approval **unspent**. Asking is not spending — the
existing consent layer already holds to that, and this path has to hold to
it too, or a person would need a fresh approval every time a grant was
missing.

**And the second gate is not the first gate.** The operation approval says
*this operation may run once, now*. The transmit grant says *this material
may go to this place*. **Passing one does not imply the other**, and
merging them would make the design's default-deny for transmission
unrepresentable.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from labcairn.application.model_transmit import check_transmit, transmit_refusal_for
from labcairn.security.permissions import Grant

pytestmark = pytest.mark.integration

NOW = datetime(2026, 3, 2, 9, 15, tzinfo=UTC)


def _transmit_grant(
    grant_id: str = "g1",
    *,
    subject_ref: str = "proj-1",
    scope: str = "proj-1/**",
    destination: str = "api.minimax.cn",
    purpose: str = "transmit",
    state: str = "active",
) -> Grant:
    return Grant(
        grant_id=grant_id,
        subject_ref=subject_ref,
        permission="external_transmit",
        purpose=purpose,
        scope=scope,
        destination=destination,
        granted_by="Dr. Chen",
        granted_at=NOW,
        expires_at=None,
        state=state,
        withdrawn_at=None,
        withdrawn_by=None,
        withdrawal_reason=None,
    )


def _read_grant(grant_id: str = "g2") -> Grant:
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
        state="active",
        withdrawn_at=None,
        withdrawn_by=None,
        withdrawal_reason=None,
    )


# --------------------------------------------------------------------------- #
# the gate
# --------------------------------------------------------------------------- #


def test_a_transmit_grant_permits_the_request() -> None:
    """The ordinary case: the material may go to the named destination."""
    check = check_transmit(
        [_transmit_grant()],
        subject_ref="proj-1",
        destination="api.minimax.cn",
        at=NOW,
    )

    assert check.permitted is True
    assert check.reason is None
    assert check.decision.grant_id == "g1"


def test_a_request_without_a_transmit_grant_is_refused_and_the_approval_is_unspent() -> None:
    """**The absence of a grant is the refusal**, and the refusal is not an
    exception.

    **What breaks it:** a path that raises instead of refusing, or one that
    treats the operation's approval as sufficient. **A model request with
    no transmit grant must be refused *with a reason*** — the model call
    itself is the thing that leaves the machine.
    """
    check = check_transmit(
        [],
        subject_ref="proj-1",
        destination="api.minimax.cn",
        at=NOW,
    )

    assert check.permitted is False
    assert check.reason == "no_grant"
    assert "remedy" in check.detail


def test_a_read_grant_does_not_authorise_a_transmission() -> None:
    """**The two gates are not the same gate.**

    **What breaks it:** a check that looks at "any grant for this subject".
    A read grant is not a transmit grant, and the design's default-deny for
    transmission depends on the difference being real.
    """
    check = check_transmit(
        [_read_grant()],
        subject_ref="proj-1",
        destination="api.minimax.cn",
        at=NOW,
    )

    assert check.permitted is False
    assert check.reason == "purpose_not_granted"


def test_a_grant_for_one_destination_does_not_authorise_another() -> None:
    """**ADR-0015 D3's rule, on the path where it matters.**

    **What breaks it:** a check that treats any transmit grant as a
    transmit grant. The refusal has to name both destinations, because
    the person reading it can then either ask the granted one or ask for a
    grant for the other.
    """
    check = check_transmit(
        [_transmit_grant()],
        subject_ref="proj-1",
        destination="api.openai.com",
        at=NOW,
    )

    assert check.permitted is False
    assert check.reason == "destination_not_granted"
    assert "api.minimax.cn" in check.detail
    assert "api.openai.com" in check.detail


def test_a_withdrawn_grant_is_refused_as_withdrawn() -> None:
    """A withdrawal is not an absence, and the path says which."""
    grant = _transmit_grant()
    withdrawn = Grant(
        **{
            **grant.__dict__,
            "state": "withdrawn",
            "withdrawn_by": "Dr. Chen",
            "withdrawn_at": NOW,
        }
    )

    check = check_transmit(
        [withdrawn],
        subject_ref="proj-1",
        destination="api.minimax.cn",
        at=NOW,
    )

    assert check.permitted is False
    assert check.reason == "grant_withdrawn"
    assert "Dr. Chen" in check.detail


def test_the_refusal_reason_is_the_consent_layer_s_own_string() -> None:
    """**A refusal reason is not re-spelled at every call site.**

    **What breaks it:** a second vocabulary for the same reasons. The
    design's rule is that the caller can branch on the reason without
    reading a message — and that only works if there is one spelling.
    """
    for destination, expected in (
        ("api.openai.com", "destination_not_granted"),
        ("api.minimax.cn", None),
    ):
        check = check_transmit(
            [_transmit_grant()],
            subject_ref="proj-1",
            destination=destination,
            at=NOW,
        )
        assert transmit_refusal_for(check) == expected


def test_the_transmit_check_runs_before_the_approval_is_consumed() -> None:
    """**The gate is a question, and asking is not spending.**

    **What breaks it:** a check that consumed the approval as a side
    effect. The caller would have to ask for a new approval every time
    the grant was missing, and the person would be paying for a refusal.

    **The check takes no approval and returns no approval.** That is the
    property: the two gates are separate, and the second one does not
    touch the first one's state.
    """
    import inspect

    parameters = inspect.signature(check_transmit).parameters
    assert "approval" not in parameters
    assert "approval_id" not in parameters
    assert set(parameters) == {
        "grants",
        "subject_ref",
        "material_ref",
        "destination",
        "purpose",
        "at",
    }


def test_the_check_needs_a_destination() -> None:
    """**A transmit request names where it is going.**

    **What breaks it:** a default destination, or an optional one. A
    request that did not say where it was going is a request to send
    anywhere, and the grant table's destination field exists to refuse
    that.
    """
    with pytest.raises(TypeError):
        check_transmit(  # type: ignore[call-arg]
            [_transmit_grant()],
            subject_ref="proj-1",
            at=NOW,
        )


def test_a_grant_for_another_subject_does_not_answer() -> None:
    """A grant belongs to one project."""
    check = check_transmit(
        [_transmit_grant(subject_ref="proj-2")],
        subject_ref="proj-1",
        destination="api.minimax.cn",
        at=NOW,
    )

    assert check.permitted is False
    assert check.reason == "no_grant"
