"""The approval checkpoint between ``propose`` and ``draft``.

Why this is a separate module and not an ``if`` in the orchestrator
------------------------------------------------------------------
The acceptance rule is that the checkpoint is *required* for important scientific
direction and major goal or claim changes. A conditional in the orchestrator is
exactly the shape a future edit erases — one refactor that moves a line, and the
requirement silently becomes advisory. Here the requirement is a gate object
with one entry point, the guarded stage's name comes from the declaration rather
than from a literal in the loop, and a stage cannot be entered without going
through :meth:`ApprovalGate.evaluate`.

What the approval is bound to
-----------------------------
:attr:`ApprovalDecision.approved_proposal_digest` is the digest of the proposal
artifact **as it was when the user read it**. The gate recomputes that digest and
compares. Three consequences, each a case the work order names:

* a user who approved a direction cannot have it changed underneath them by a
  later stage and be treated as having approved the new one;
* an approval for a routine item does not extend to an item that later becomes
  ``MAJOR_GOAL_OR_CLAIM_CHANGE`` — the coverage set is explicit and checked;
* an approval cannot outlive its window, and the window is on the decision rather
  than in whatever the caller remembers.

Single use is **not** enforced here, and that is a boundary rather than an
oversight. ADR-0003 §C4's single-use accounting lives in
:class:`labcairn.security.approval.ApprovalLedger` and is bound to a capability,
a resource and an argument digest. This gate decides whether a *scientific
direction* may proceed; reusing it is a policy question that belongs to whoever
owns the approval ledger, and inventing a second consumption rule here would
produce two implementations of one rule that could disagree — the failure mode
:mod:`labcairn.security.approval` explicitly documents and avoids.

What is refused, and how loudly
-------------------------------
A missing approval is not an error: the stage is parked as ``BLOCKED`` and the
run returns, which is the graceful behaviour the work order asks for. A *stale*
approval — one that exists but no longer covers the proposal — is refused by name,
because "we have an approval" is the belief that most needs correcting at that
point.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Self

from pydantic import AwareDatetime, Field, model_validator

from labcairn.core.schema import LabCairnModel
from labcairn.skills.artifacts import ResearchProposal
from labcairn.skills.errors import StaleApprovalError
from labcairn.sources.primitives import ContentHash, NonEmptyText


class ApprovalDecision(LabCairnModel):
    """A human's grant to proceed with a named scientific direction.

    Frozen. An approval is a statement about a moment; if what it covers has to
    change, a new decision is issued and the old one stays readable, which is the
    same append-only reasoning the evidence ledger uses for its audit trail.
    """

    decision_id: NonEmptyText
    task_id: NonEmptyText
    #: Digest of the proposal the human was shown. Recomputed and compared at
    #: gate time; see the module docstring.
    approved_proposal_digest: ContentHash
    #: The significant proposal items this grant covers. Must be non-empty: a
    #: grant that covers nothing is a grant nobody made.
    covered_item_ids: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)]
    #: Goal changes this grant covers. Separate from items because a goal change
    #: is not an item and must never be covered by an item's id appearing in a
    #: list.
    covered_goal_change_ids: tuple[NonEmptyText, ...] = ()
    granted_by: NonEmptyText
    granted_at: AwareDatetime
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def _the_window_is_a_window(self) -> Self:
        if self.expires_at <= self.granted_at:
            raise ValueError(
                f"expires_at ({self.expires_at}) is not after granted_at "
                f"({self.granted_at}). An approval that is already expired when it is "
                f"written is a record of a decision nobody made."
            )
        return self

    @model_validator(mode="after")
    def _coverage_has_no_duplicates(self) -> Self:
        for name in ("covered_item_ids", "covered_goal_change_ids"):
            values = getattr(self, name)
            if len(set(values)) != len(values):
                raise ValueError(
                    f"{name} contains duplicates: {list(values)}. One decision covering "
                    f"an id twice is one cover, and a count of covers is not a thing."
                )
        return self

    def is_live(self, now: datetime) -> bool:
        """Whether *now* is inside the grant's window.

        Half-open ``[granted_at, expires_at)``: an approval is not live one
        microsecond before it was granted, and stops being live the instant it
        expires.
        """
        return self.granted_at <= now < self.expires_at


@dataclass(frozen=True, slots=True)
class GateVerdict:
    """The gate's answer, and — when it is no — what a person is being asked.

    Returned rather than raised because *blocked* is a normal outcome, not an
    exception: the orchestrator parks the stage and returns. :attr:`reason` is
    written for the person who has to decide, not for a log reader.
    """

    approved: bool
    required: bool
    reason: str
    covered_items: tuple[str, ...] = ()
    covered_goal_changes: tuple[str, ...] = ()

    @property
    def awaiting_user(self) -> bool:
        """Blocked specifically on a human, as opposed to failed for any reason."""
        return self.required and not self.approved


def gate_request(proposal: ResearchProposal) -> str:
    """The question to put to the user, naming what they are approving.

    Built from the proposal, so it cannot describe a different proposal from the
    one the digest covers — the same reason the binding is a digest.
    """
    parts: list[str] = []
    significant = proposal.significant_items()
    if significant:
        parts.append(
            "items requiring approval: "
            + "; ".join(
                f"{item.item_id} ({item.materiality.value}) {item.statement}"
                for item in significant
            )
        )
    if proposal.goal_changes:
        parts.append(
            "goal changes requiring approval: "
            + "; ".join(
                f"{change.change_id} {change.target}: {change.old_value!r} -> {change.new_value!r}"
                for change in proposal.goal_changes
            )
        )
    return " | ".join(parts)


class ApprovalGate:
    """Decides whether a proposal may become prose.

    Stateless on purpose. It reads a proposal, an optional decision and the clock,
    and returns an answer. Nothing is consumed and nothing is remembered, so the
    same gate can be asked the same question twice and give the same answer —
    which is what lets the orchestrator re-enter a blocked run without having to
    reason about what it did last time.
    """

    def evaluate(
        self,
        proposal: ResearchProposal,
        proposal_digest: str,
        decision: ApprovalDecision | None,
        *,
        now: datetime,
    ) -> GateVerdict:
        """Whether *proposal* may proceed under *decision*.

        :param proposal: the artifact about to be drafted from.
        :param proposal_digest: its canonical digest, recomputed by the caller
            from the artifact rather than read off the decision.
        :param decision: the grant, or ``None`` when the user has not answered.
        :param now: the current time, injected so tests do not read a wall clock.
        :raises StaleApprovalError: never. A grant that does not cover the
            proposal yields ``approved=False`` with a reason naming the mismatch;
            the caller decides whether that is a park or a stop. Raising here
            would make "the user has not approved this yet" and "the user approved
            something else" the same exception, and the first is routine.
        """
        required_items = tuple(item.item_id for item in proposal.significant_items())
        required_changes = tuple(change.change_id for change in proposal.goal_changes)
        required = bool(required_items) or bool(required_changes)

        if not required:
            return GateVerdict(
                approved=True,
                required=False,
                reason="the proposal contains no important scientific direction and no "
                "goal or claim change, so the checkpoint does not apply",
            )

        request = gate_request(proposal)

        if decision is None:
            return GateVerdict(
                approved=False,
                required=True,
                reason=(
                    "awaiting user approval for the scientific direction: " + request
                    if request
                    else "awaiting user approval"
                ),
                covered_items=required_items,
                covered_goal_changes=required_changes,
            )

        if not decision.is_live(now):
            return GateVerdict(
                approved=False,
                required=True,
                reason=(
                    f"decision {decision.decision_id!r} is not live at {now.isoformat()}: "
                    f"granted {decision.granted_at.isoformat()}, expires "
                    f"{decision.expires_at.isoformat()}. An expired approval is not "
                    f"reused; it is re-asked."
                ),
                covered_items=required_items,
                covered_goal_changes=required_changes,
            )

        if decision.approved_proposal_digest != proposal_digest:
            return GateVerdict(
                approved=False,
                required=True,
                reason=(
                    f"decision {decision.decision_id!r} approves proposal digest "
                    f"{decision.approved_proposal_digest[:12]}… but the proposal now "
                    f"hashes to {proposal_digest[:12]}…. The proposal changed after it "
                    f"was approved; the earlier answer was about a different direction."
                ),
                covered_items=required_items,
                covered_goal_changes=required_changes,
            )

        missing_items = sorted(set(required_items) - set(decision.covered_item_ids))
        if missing_items:
            return GateVerdict(
                approved=False,
                required=True,
                reason=(
                    f"decision {decision.decision_id!r} does not cover proposal "
                    f"item(s) {missing_items}. Approving some of a direction and not "
                    f"the rest is a decision about part of the work, not about the "
                    f"checkpoint."
                ),
                covered_items=required_items,
                covered_goal_changes=required_changes,
            )

        missing_changes = sorted(set(required_changes) - set(decision.covered_goal_change_ids))
        if missing_changes:
            return GateVerdict(
                approved=False,
                required=True,
                reason=(
                    f"decision {decision.decision_id!r} does not cover goal change(s) "
                    f"{missing_changes}. Changing the objective or the success "
                    f"criterion is the largest change a run can make to itself."
                ),
                covered_items=required_items,
                covered_goal_changes=required_changes,
            )

        return GateVerdict(
            approved=True,
            required=True,
            reason=(
                f"decision {decision.decision_id!r} by {decision.granted_by!r} covers "
                f"items {list(required_items)}"
                + (f" and goal changes {list(required_changes)}" if required_changes else "")
            ),
            covered_items=required_items,
            covered_goal_changes=required_changes,
        )


def require_approval(
    proposal: ResearchProposal,
    proposal_digest: str,
    decision: ApprovalDecision | None,
    *,
    now: datetime,
) -> ApprovalDecision | None:
    """Gate for a caller entering the guarded stage by some route other than the orchestrator.

    The direct-entry counterpart to :meth:`ApprovalGate.evaluate`, which is for
    the orchestrator's use — the orchestrator *parks* rather than raises. Anyone
    else entering the guarded stage calls this and is refused.

    :returns: the decision that authorises the draft, or ``None`` when the gate
        says no decision was needed. Returning ``None`` rather than raising for a
        routine proposal is the point: a checkpoint that demanded a grant nobody
        needed would be a checkpoint people learn to satisfy without reading.
    :raises StaleApprovalError: with the gate's reason, when a decision *was*
        required and was not validly granted.
    """
    verdict = ApprovalGate().evaluate(proposal, proposal_digest, decision, now=now)
    if not verdict.approved:
        raise StaleApprovalError(verdict.reason)
    if not verdict.required:
        return None
    if decision is None:  # pragma: no cover - approved and required implies a decision
        raise StaleApprovalError("the gate approved a direction it found no decision for")
    return decision


__all__ = [
    "ApprovalDecision",
    "ApprovalGate",
    "GateVerdict",
    "gate_request",
    "require_approval",
]
