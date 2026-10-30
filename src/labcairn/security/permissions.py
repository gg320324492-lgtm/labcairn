"""Whether this material may be used for this purpose, in this place.

**What this module answers.** One question: *may this material be used for
this purpose, by this caller, to this destination?* And the answer is
recorded — **which grant permitted it**, so the answer can be audited, or
**why it was refused**, so a person can act on it.

**The refusal is the default, and it is the default *in the model*.**
ADR-0015 D2 says it without hedging: *"Not 'denied until granted' as a UI
default — **denied in the model**. There is no row, so there is nothing to
check, so the path cannot proceed."*

**So this module has no "allow" flag and no default-permitted path.** It
reads the grants that exist and answers from them. A material with no
grant, for a permission with no grant, is refused — and the refusal names
what is missing.

**What the refusal names is the useful half.** *"No grant"* is true and
unhelpful. *"You have a read grant but not a transmit grant"* is an answer a
person can act on. So when several grants exist and none covers the use,
the reason names the **closest** one — the grant that covers the
permission but not the purpose, or the purpose but not the destination.

**And the distinction that matters between two of the refusals.** A grant
that was **withdrawn** is not the same as a grant that was **never made**,
and the two are told apart because the question "was this permitted once
and then taken back?" has a different answer from "was this ever
permitted?" — and only the first is a question about a person.

**And an expiry is a clock fact, not a state.** Nothing in the product
ever writes ``expired`` on an access grant: **a grant whose window has
closed is still ``active`` in the row**, and the only thing that says it
has run out is the clock. So every question of the form *"is this grant
still holding?"* is asked **of the grant, at a moment** — never by reading
a column — and the grant is asked through
:meth:`Grant.is_in_force`, which tests **both ends** of the window.

**What this module does not do.** It does not spend an approval, call a
model, or decide who may be granted what. **The policy of granting is a
person's**; this is the mechanism that enforces it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final

__all__ = [
    "ConsentDecision",
    "ConsentRefusal",
    "Grant",
    "may_use",
]


class ConsentRefusal(StrEnum):
    """Why a use was not permitted.

    **Each one says what is missing**, because a refusal that only says "no"
    is a refusal nobody can act on. The project's own rule for a refusal is
    that it names the fault, and the remedy is part of the fault.

    - ``NO_GRANT`` — nothing covers this permission for this subject. **The
      remedy is a grant.**
    - ``PURPOSE_NOT_GRANTED`` — a grant covers this permission, but for
      another purpose. **The remedy is a grant for this purpose.**
    - ``DESTINATION_NOT_GRANTED`` — a grant covers this permission and this
      purpose, but names another destination. **The remedy is a grant for
      this destination**, or a request to the granted one.
    - ``GRANT_WITHDRAWN`` — the grant that would have covered it was
      withdrawn, by somebody, on a day. **The remedy is a new grant.**
    - ``GRANT_EXPIRED`` — the grant existed and has run out.
    - ``GRANT_NOT_YET_ACTIVE`` — the grant is recorded but its window has
      not opened.
    - ``SCOPE_NOT_COVERED`` — a grant exists for this subject, permission
      and purpose, but its scope does not reach this material.
    """

    NO_GRANT = "no_grant"
    PURPOSE_NOT_GRANTED = "purpose_not_granted"
    DESTINATION_NOT_GRANTED = "destination_not_granted"
    GRANT_WITHDRAWN = "grant_withdrawn"
    GRANT_EXPIRED = "grant_expired"
    GRANT_NOT_YET_ACTIVE = "grant_not_yet_active"
    SCOPE_NOT_COVERED = "scope_not_covered"


#: The four permissions. A closed set, because a permission that could hold
#: any string is a permission nobody holds.
PERMISSIONS: Final[tuple[str, ...]] = (
    "store_read",
    "parse_annotate",
    "external_transmit",
    "train_reuse",
)

#: The five purposes. A closed set on the same standard.
PURPOSES: Final[tuple[str, ...]] = (
    "read",
    "annotate",
    "retrieve",
    "transmit",
    "train",
)


@dataclass(frozen=True)
class Grant:
    """One grant, as the check reads it.

    **A value, not a row.** The check does not read the database; it reads
    grants, and the caller fetches them. **That is what makes the check
    testable without a store**, and it is why the "no row means no
    permission" rule lives here rather than in a query that might return an
    empty set for the wrong reason.
    """

    grant_id: str
    subject_ref: str
    permission: str
    purpose: str
    scope: str
    destination: str | None
    granted_by: str
    granted_at: datetime
    expires_at: datetime | None
    state: str
    withdrawn_at: datetime | None
    withdrawn_by: str | None
    withdrawal_reason: str | None

    def is_in_force(self, at: datetime) -> bool:
        """Whether the grant is in force **at a moment**.

        **The window is both ends.** A grant with an expiry in the past has
        run out; a grant whose window has not opened is not yet in force.
        **And a withdrawn grant is never in force**, whatever the clock says.

        **The lower bound is the one that is easy to leave out.** A check
        that asks only "has it expired?" lets a grant for a *future* window
        permit a use today, which is a grant that says yes before it says
        yes.
        """
        if self.state in ("withdrawn", "expired"):
            return False
        if at < self.granted_at:
            return False
        return self.expires_at is None or at < self.expires_at


@dataclass(frozen=True)
class ConsentDecision:
    """The answer, and the receipt for it.

    **``grant_id`` is the receipt.** When a use is allowed, the decision
    names the grant that permitted it, so the use can be traced to a
    decision a person made — and so a withdrawal can find everything that
    was permitted under it.

    **``reason`` is the answer when it is refused.** It names the missing
    thing and, where there is one, the grant that came closest.
    """

    allowed: bool
    #: Which grant permitted it, or ``None``.
    grant_id: str | None
    #: Why it was refused, or ``None``.
    reason: ConsentRefusal | None
    #: The grant that came closest, so the refusal can be acted on.
    closest: Grant | None
    #: A sentence for a person, naming the fault and the remedy.
    detail: str

    @property
    def is_permitted(self) -> bool:
        return self.allowed


def _scope_covers(scope: str, material_ref: str) -> bool:
    """Whether a grant's scope reaches a material.

    **The scope and the material are in the same coordinate system.** A
    grant's scope names the material paths it reaches, and a material is
    named the same way, so the comparison is between two paths in one
    system — and **the scope's own prefix is the project's**, which is why
    a grant on ``proj-1`` carries a scope like ``proj-1/**``.

    **A prefix match, and the prefix is explicit.** ``proj-1/**`` covers
    ``proj-1`` and everything under it; ``proj-1`` covers only itself. **A
    scope that does not end in ``/**`` is a scope of one thing**, which is
    the narrow reading and the safe one: a grant that says "this paper" and
    is read as "this paper and anything else" is a grant that has been
    widened by a guess.

    **And a sibling that merely shares a prefix is not under the scope**:
    ``proj-1-secrets`` does not begin with ``proj-1/``, so it is not
    covered by ``proj-1/**``.
    """
    if scope.endswith("/**"):
        prefix = scope[:-3]
        return material_ref == prefix or material_ref.startswith(prefix + "/")
    return scope == material_ref


def _refusal_for(
    grant: Grant,
    *,
    permission: str,
    purpose: str,
    material_ref: str,
    destination: str | None,
) -> ConsentRefusal:
    """The reason a grant does not cover a use.

    **The order is the order of how far the grant got.** A grant for the
    right permission but the wrong purpose is closer than one for the wrong
    permission, because the remedy is narrower.
    """
    if not _scope_covers(grant.scope, material_ref):
        return ConsentRefusal.SCOPE_NOT_COVERED
    if grant.purpose != purpose:
        return ConsentRefusal.PURPOSE_NOT_GRANTED
    if grant.permission != permission:
        return ConsentRefusal.NO_GRANT
    if permission == "external_transmit" and grant.destination != destination:
        return ConsentRefusal.DESTINATION_NOT_GRANTED
    return ConsentRefusal.NO_GRANT


def may_use(
    grants: list[Grant],
    *,
    permission: str,
    purpose: str,
    subject_ref: str,
    material_ref: str | None = None,
    destination: str | None = None,
    at: datetime,
) -> ConsentDecision:
    """Decide whether a use is permitted, and say why.

    *grants* is every grant that could bear on the question — the caller
    fetches them. **The absence of a row is the refusal**, and this
    function is where that absence becomes an answer.

    **``subject_ref`` and ``material_ref`` are two questions.** The subject
    is *whose project this is*, and the material is *which of its files is
    being used*. A grant belongs to one subject and reaches a set of
    materials, so both are asked: a grant for another project does not
    answer, and a grant whose scope does not reach the material refuses.
    **``material_ref`` defaults to the subject**, which is the common case
    where a grant covers the whole project.

    **The rules, in the order they are applied.**

    1. **A grant in force covers the use**, when its scope reaches the
       subject, its purpose is this one, and — for a transmit — its
       destination is this one. The decision names it.
    2. **Otherwise the refusal names the closest grant**, so the answer is
       actionable rather than merely true.
    3. **A withdrawn grant is reported as withdrawn**, and an expired one
       as expired, **even when another grant would have covered the use**,
       because the question "was this permitted once and then taken back?"
       is a different question from "is it permitted now?".

    **A refusal is not an exception.** Not being permitted is a normal
    answer on this path — a model request with no transmit grant must be
    refused *with a reason*, not crash — so this returns a decision rather
    than raising.
    """
    if permission not in PERMISSIONS:
        raise ValueError(
            f"{permission!r} is not one of the four permissions "
            f"{list(PERMISSIONS)}. A permission that could hold any string is "
            f"a permission nobody holds."
        )
    if purpose not in PURPOSES:
        raise ValueError(f"{purpose!r} is not one of the five purposes {list(PURPOSES)}.")

    # **Two different axes, and they are not the same question.**
    # ``subject_ref`` is *which project the grant belongs to*; ``scope`` is
    # *which material inside that project it covers*. A grant belongs to
    # exactly one project, and its scope is a path inside it. So the
    # subject is an identity test and the scope is a reach test, and
    # **neither substitutes for the other** -- which is why a grant for
    # one project cannot answer for another, and why a grant whose scope
    # does not reach the material refuses rather than permits.
    candidates = [grant for grant in grants if grant.subject_ref == subject_ref]
    if not candidates:
        return ConsentDecision(
            allowed=False,
            grant_id=None,
            reason=ConsentRefusal.NO_GRANT,
            closest=None,
            detail=(
                f"no grant covers {permission!r} for {subject_ref!r}. The "
                f"remedy is a grant: the permission is denied by the absence "
                f"of a row, not by a flag."
            ),
        )

    material = material_ref if material_ref is not None else subject_ref
    covering = [
        grant
        for grant in candidates
        if grant.permission == permission
        and grant.purpose == purpose
        and _scope_covers(grant.scope, material)
        and (permission != "external_transmit" or grant.destination == destination)
    ]

    in_force = [grant for grant in covering if grant.is_in_force(at)]
    if in_force:
        grant = in_force[0]
        return ConsentDecision(
            allowed=True,
            grant_id=grant.grant_id,
            reason=None,
            closest=grant,
            detail=(
                f"permitted by grant {grant.grant_id!r}, granted by "
                f"{grant.granted_by!r} on {grant.granted_at.isoformat()}."
            ),
        )

    # No grant in force covers it. **The reason depends on what happened to
    # the closest one** -- withdrawn, expired, not yet active, or simply
    # not covering this purpose or destination.
    withdrawn = [grant for grant in covering if grant.state == "withdrawn"]
    if withdrawn:
        grant = withdrawn[0]
        who = grant.withdrawn_by or "somebody"
        when = grant.withdrawn_at.isoformat() if grant.withdrawn_at else "an unrecorded day"
        return ConsentDecision(
            allowed=False,
            grant_id=None,
            reason=ConsentRefusal.GRANT_WITHDRAWN,
            closest=grant,
            detail=(
                f"grant {grant.grant_id!r} would have covered this use, and it "
                f"was withdrawn by {who} on {when}. The remedy is a new grant."
            ),
        )

    # **A grant that has run out is reported as expired**, and it is found
    # by its *own* condition rather than by the closest-grant ranking --
    # a grant whose expiry has passed is still ``active`` by state, so the
    # ranking would call it "no grant" and lose the reason.
    expired = [
        grant
        for grant in covering
        if grant.state == "expired" or (grant.expires_at is not None and at >= grant.expires_at)
    ]
    if expired:
        grant = expired[0]
        return ConsentDecision(
            allowed=False,
            grant_id=None,
            reason=ConsentRefusal.GRANT_EXPIRED,
            closest=grant,
            detail=(
                f"grant {grant.grant_id!r} covered this use and has run out. "
                f"The remedy is a new grant."
            ),
        )

    not_yet = [grant for grant in covering if at < grant.granted_at]
    if not_yet:
        grant = not_yet[0]
        return ConsentDecision(
            allowed=False,
            grant_id=None,
            reason=ConsentRefusal.GRANT_NOT_YET_ACTIVE,
            closest=grant,
            detail=(
                f"grant {grant.grant_id!r} covers this use but its window has "
                f"not opened. The remedy is to wait, or to grant it now."
            ),
        )

    # **The closest grant is the one that got the furthest.** The order is
    # the order of the remedy's narrowness: a grant for the right
    # permission and the wrong purpose is closer than one for the wrong
    # permission, because the remedy is narrower.
    ranked = sorted(
        candidates,
        key=lambda grant: (
            grant.permission != permission,
            grant.purpose != purpose,
            grant.scope != material,
        ),
    )
    closest = ranked[0]
    reason = _refusal_for(
        closest,
        permission=permission,
        purpose=purpose,
        material_ref=material,
        destination=destination,
    )
    return ConsentDecision(
        allowed=False,
        grant_id=None,
        reason=reason,
        closest=closest,
        detail=_detail_for(
            reason,
            closest=closest,
            permission=permission,
            purpose=purpose,
            material_ref=material,
            destination=destination,
        ),
    )


def _detail_for(
    reason: ConsentRefusal,
    *,
    closest: Grant,
    permission: str,
    purpose: str,
    material_ref: str,
    destination: str | None,
) -> str:
    """The sentence a person reads when a use is refused.

    **Every one names the remedy.** A refusal that says what is wrong and
    not what would fix it is half a refusal, and the half it leaves out is
    the half the person needs.
    """
    match reason:
        case ConsentRefusal.PURPOSE_NOT_GRANTED:
            return (
                f"grant {closest.grant_id!r} covers {permission!r} but for the "
                f"purpose {closest.purpose!r}, not {purpose!r}. The remedy is a "
                f"grant for {purpose!r}."
            )
        case ConsentRefusal.DESTINATION_NOT_GRANTED:
            return (
                f"grant {closest.grant_id!r} covers {permission!r} for "
                f"{purpose!r}, but names the destination {closest.destination!r} "
                f"and not {destination!r}. The remedy is a grant for "
                f"{destination!r}, or a request to {closest.destination!r}."
            )
        case ConsentRefusal.SCOPE_NOT_COVERED:
            return (
                f"grant {closest.grant_id!r} covers {material_ref!r} for "
                f"{permission!r}, but its scope {closest.scope!r} does not reach "
                f"this material. The remedy is a grant whose scope covers it."
            )
        case _:
            return (
                f"grant {closest.grant_id!r} does not cover {permission!r} for "
                f"{purpose!r}. The remedy is a grant."
            )


# --------------------------------------------------------------------------- #
# T03: withdrawal, and the propagation that is checkable
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class DerivedCopy:
    """Something made **from** material, and the grant it came from.

    **The provenance is the whole reason the row exists.** ADR-0015 D4:
    *"Withdrawing a grant must invalidate what depended on it: derived
    embeddings, index entries built from the material, queued training
    runs, cached model transcripts, and any guidance rule distilled from
    it."*

    **And the design asks the question precisely** — *"撤回同意后历史
    embedding/缓存/训练队列是否失效"* — so the answer has to be a fact and
    not a promise. **A copy records the grant it came from**, and a check
    asks whether that grant is still in force.
    """

    copy_id: str
    #: The grant this copy was made under.
    grant_id: str
    #: What kind of copy: an index entry, an embedding, a queued run, a
    #: cached transcript, a distilled rule.
    kind: str
    #: Where the copy lives, so a withdrawal can find it.
    location: str
    #: The material the copy was made from.
    subject_ref: str


def withdraw_grant(
    grant: Grant,
    *,
    withdrawn_by: str,
    at: datetime,
    reason: str = "",
) -> Grant:
    """Withdraw a grant, and say who and when and why.

    **The row is not deleted.** A permission check that cannot say *"this
    was withdrawn by the advisor on 2026-03-02"* cannot answer the question
    a person will ask, and **the record of a grant that was withdrawn is
    itself a record**.

    **And the state moves to ``withdrawn``, not to something softer.** A
    grant that was taken back is not a grant that lapsed and not a grant
    that was never made, and the check tells the three apart.
    """
    if not withdrawn_by.strip():
        raise ValueError(
            "a withdrawal is a person's decision and it must name them: withdrawn_by is empty."
        )
    if grant.state == "withdrawn":
        raise ValueError(
            f"grant {grant.grant_id!r} was already withdrawn by "
            f"{grant.withdrawn_by!r}. Withdrawing it twice would make the "
            f"record say two things about one decision."
        )
    return Grant(
        grant_id=grant.grant_id,
        subject_ref=grant.subject_ref,
        permission=grant.permission,
        purpose=grant.purpose,
        scope=grant.scope,
        destination=grant.destination,
        granted_by=grant.granted_by,
        granted_at=grant.granted_at,
        expires_at=grant.expires_at,
        state="withdrawn",
        withdrawn_at=at,
        withdrawn_by=withdrawn_by,
        withdrawal_reason=reason,
    )


def is_copy_stale(copy: DerivedCopy, grants: list[Grant], *, at: datetime) -> bool:
    """Whether a derived copy has outlived the grant that produced it.

    **This is the question the design asks**: *"撤回同意后历史
    embedding/缓存/训练队列是否失效"*. The answer is **yes**, and it is a
    fact rather than a promise because the copy records its provenance and
    this checks it.

    **And a copy whose grant is not on the record is stale.** A copy with
    no findable grant has no provenance to check, and treating "I cannot
    find the grant" as "the grant is fine" would be the wrong direction of
    error: it would keep a copy alive on the strength of a missing row.

    **And a grant whose window has closed is not a live grant either.**
    The question is asked **of the grant, at a moment**: ``at`` says when,
    and the grant is asked whether it is in force *then*. **The state
    column is not the answer**, because **nothing in the product ever
    writes ``expired``** — an expiry is a clock fact, and a grant whose
    ``expires_at`` has passed is still ``active`` by state. So the check
    asks the grant itself, through :meth:`Grant.is_in_force`, which tests
    **both ends** of the window and refuses a withdrawn grant.

    **Which means the copy check and the permission check ask the same
    question of the same grant at the same moment.** A grant that refuses
    a use refuses the copy made under it, and a grant that permits a use
    keeps its copy alive — **one rule, asked once**, rather than two rules
    that can disagree.
    """
    grant = next(
        (candidate for candidate in grants if candidate.grant_id == copy.grant_id),
        None,
    )
    if grant is None:
        return True
    return not grant.is_in_force(at)


def stale_copies(
    copies: list[DerivedCopy],
    grants: list[Grant],
    *,
    at: datetime,
) -> tuple[DerivedCopy, ...]:
    """Every copy that has outlived its grant.

    **The list is what a withdrawal has to act on**, and it is a list
    rather than a promise because a promise about derived copies is exactly
    the kind of claim that cannot be checked later.

    **And the list is asked at a moment.** ``at`` is the same clock the
    permission check is asked at, so the copies that have to be acted on
    are the ones whose grant no longer holds *then* — **including the
    ones whose grant has merely run out**, which is the half of the
    propagation that a state column cannot see.
    """
    return tuple(copy for copy in copies if is_copy_stale(copy, grants, at=at))
