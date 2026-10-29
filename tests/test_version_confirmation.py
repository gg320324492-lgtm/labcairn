"""The human confirmation path, and the rule that a correction never overwrites.

**What is under test.** LC-P2-08 T03: what a person's decision to a
proposed relationship produces.

**The rule this file exists for.** The project's rule is that a human
revision produces a **new version** rather than silently replacing what was
there, and the design says the same of a corrected edge: *"人工修正产生新
版本而非静默覆盖"*.

**Why that matters here and not only in general.** The edge the system
proposed is **evidence about what the system got wrong**. Overwriting it
would destroy the record of the error, and an archive that cannot show
where it was wrong cannot be trusted to show where it was right. So:

- **a correction writes a second edge** and leaves the first readable;
- **a rejection writes no edge** and still records that somebody looked
  and said no — because *"a person looked at this and said no"* is
  information the archive needs.

**And the three outcomes are not the same thing**, which is why they are
three members of a closed vocabulary rather than a boolean.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from labcairn.papers.versions import (
    ConfirmationOutcome,
    EdgeSource,
    VersionEdge,
    confirm_edge,
)

NOW = datetime(2026, 3, 2, 9, 15, tzinfo=UTC)


def _proposal(**overrides: object) -> VersionEdge:
    """An edge the system proposed and nobody has accepted."""
    values: dict[str, object] = {
        "edge_id": "edge-1",
        "project_id": "proj-1",
        "parent_version_id": "v1",
        "child_version_id": "v2",
        "source": EdgeSource.EVIDENCE,
        "confidence": 0.6,
        "evidence_spans": ("Introduction", "0.12"),
    }
    values.update(overrides)
    return VersionEdge(**values)  # type: ignore[arg-type]


def _ids(prefix: str = "edge") -> Callable[[], str]:
    """An id factory for the corrected edge.

    **The first id it mints is not the proposal's id**, because the
    proposal in this file is called ``edge-1`` and a factory that started
    at ``edge-1`` would hand the correction the same name -- and the
    whole point of the correction rule is that it is a *different* edge.
    """
    counter = {"n": 0}

    def mint() -> str:
        counter["n"] += 1
        return f"{prefix}-corrected-{counter['n']}"

    return mint


# --------------------------------------------------------------------------- #
# acceptance
# --------------------------------------------------------------------------- #


def test_accepting_an_edge_names_the_person_and_keeps_the_confidence() -> None:
    """An acceptance settles the relationship and says who settled it.

    **What breaks it:** an acceptance that changes the confidence. The
    person accepted the relationship; **how strong the evidence was is
    still a fact about the evidence**, and a person who accepts on thin
    evidence has said something about the relationship, not about the
    score.
    """
    proposal = _proposal()
    decision = confirm_edge(
        proposal,
        ConfirmationOutcome.ACCEPTED,
        decided_by="Prof. Lin",
        decided_at=NOW,
        reason="the passages match; this is the same draft.",
    )

    assert decision.outcome is ConfirmationOutcome.ACCEPTED
    assert decision.edge is not None
    assert decision.edge.is_accepted is True
    assert decision.edge.accepted_by == "Prof. Lin"
    assert decision.edge.accepted_at == NOW
    assert decision.edge.source is EdgeSource.HUMAN
    assert decision.edge.confidence == pytest.approx(0.6)
    assert decision.reason


def test_an_acceptance_with_nobody_behind_it_is_refused() -> None:
    """A decision must name the person who made it.

    **What breaks it:** accepting with an empty ``decided_by``. The
    decision would settle the relationship and attribute it to nobody,
    which is the forgery the whole three-fact split exists to prevent.
    """
    with pytest.raises(ValueError) as refused:
        confirm_edge(
            _proposal(),
            ConfirmationOutcome.ACCEPTED,
            decided_by="   ",
            decided_at=NOW,
        )
    assert "must name them" in str(refused.value)


# --------------------------------------------------------------------------- #
# correction
# --------------------------------------------------------------------------- #


def test_a_correction_writes_a_new_edge_and_leaves_the_old_one_readable() -> None:
    """**The rule this file exists for.**

    **What breaks it:** writing the corrected parent over the proposal.
    The proposal is **evidence about what the system got wrong**, and
    overwriting it would destroy the record of the error — so an archive
    that cannot show where it was wrong cannot be trusted to show where it
    was right.
    """
    proposal = _proposal()
    decision = confirm_edge(
        proposal,
        ConfirmationOutcome.CORRECTED,
        decided_by="Prof. Lin",
        decided_at=NOW,
        corrected_parent_version_id="v1-real",
        edge_id_factory=_ids(),
    )

    assert decision.outcome is ConfirmationOutcome.CORRECTED
    assert decision.edge is not None
    assert decision.edge.parent_version_id == "v1-real"
    assert decision.edge.edge_id != proposal.edge_id
    assert decision.edge.edge_version == proposal.edge_version + 1
    assert decision.edge.accepted_by == "Prof. Lin"

    # **The proposal is still there**, with the edge that replaced it
    # named, and it is readable.
    assert decision.corrects is not None
    assert decision.corrects.edge_id == proposal.edge_id
    assert decision.corrects.parent_version_id == "v1"
    assert decision.corrects.superseded_by == decision.edge.edge_id
    # And it is still a proposal: the system did not accept it.
    assert decision.corrects.accepted_by is None
    assert decision.corrects.is_proposal is True


def test_a_correction_without_a_parent_is_refused() -> None:
    """A correction that does not say what the right answer is is not a
    correction.

    **What breaks it:** accepting the correction with the original parent
    still in place, which would record a decision and change nothing.
    """
    with pytest.raises(ValueError) as refused:
        confirm_edge(
            _proposal(),
            ConfirmationOutcome.CORRECTED,
            decided_by="Prof. Lin",
            decided_at=NOW,
            edge_id_factory=_ids(),
        )
    assert "must name the parent" in str(refused.value)


def test_a_correction_to_a_self_parent_is_refused() -> None:
    """A correction may not make a version its own parent.

    **What breaks it:** letting the correction through. The schema refuses
    this and so must this: a correction is the one path that changes the
    graph's shape, and it is the one path where the contradiction could
    slip in.
    """
    with pytest.raises(ValueError) as refused:
        confirm_edge(
            _proposal(),
            ConfirmationOutcome.CORRECTED,
            decided_by="Prof. Lin",
            decided_at=NOW,
            corrected_parent_version_id="v2",
            edge_id_factory=_ids(),
        )
    assert "its own parent" in str(refused.value)


def test_a_correction_of_a_settled_edge_is_refused() -> None:
    """A settled relationship is not re-read; it is decided again.

    **What breaks it:** allowing a correction of an accepted edge. The
    design says a person's revision produces a new version, and a second
    decision about a settled relationship is a **new decision** — it needs
    to start from the proposal that was made, not from the accepted edge.
    """
    proposal = _proposal()
    accepted = confirm_edge(
        proposal,
        ConfirmationOutcome.ACCEPTED,
        decided_by="Prof. Lin",
        decided_at=NOW,
    )
    assert accepted.edge is not None

    with pytest.raises(ValueError) as refused:
        confirm_edge(
            accepted.edge,
            ConfirmationOutcome.CORRECTED,
            decided_by="Dr. Chen",
            decided_at=NOW,
            corrected_parent_version_id="v1-real",
            edge_id_factory=_ids(),
        )
    assert "already accepted" in str(refused.value)


# --------------------------------------------------------------------------- #
# rejection
# --------------------------------------------------------------------------- #


def test_a_rejection_writes_no_edge_and_keeps_the_proposal() -> None:
    """A refusal is recorded, and no relationship is created.

    **What breaks it:** deleting the proposal. "A person looked at this
    and said no" is information the archive needs — otherwise the same
    wrong proposal is made again, and nobody can see that it was already
    settled.
    """
    proposal = _proposal()
    decision = confirm_edge(
        proposal,
        ConfirmationOutcome.REJECTED,
        decided_by="Prof. Lin",
        decided_at=NOW,
        reason="these are two different papers that happen to share a template.",
    )

    assert decision.outcome is ConfirmationOutcome.REJECTED
    assert decision.edge is None
    # The proposal it refused is returned, and it is unchanged.
    assert decision.corrects is not None
    assert decision.corrects.edge_id == proposal.edge_id
    assert decision.corrects.accepted_by is None
    assert decision.reason


def test_the_rejection_records_who_and_when() -> None:
    """A refusal without an author is not a record of a refusal."""
    decision = confirm_edge(
        _proposal(),
        ConfirmationOutcome.REJECTED,
        decided_by="Dr. Chen",
        decided_at=NOW,
    )

    assert decision.decided_by == "Dr. Chen"
    assert decision.decided_at == NOW


# --------------------------------------------------------------------------- #
# the shapes
# --------------------------------------------------------------------------- #


def test_the_three_outcomes_produce_three_different_shapes() -> None:
    """Accepted, corrected and rejected are not the same thing.

    **What breaks it:** collapsing them. If a rejection produced an edge
    with no acceptor, it would look like a proposal that nobody accepted —
    and the next run would propose it again, having learned nothing from
    the refusal.
    """
    accepted = confirm_edge(
        _proposal(),
        ConfirmationOutcome.ACCEPTED,
        decided_by="Prof. Lin",
        decided_at=NOW,
    )
    corrected = confirm_edge(
        _proposal(),
        ConfirmationOutcome.CORRECTED,
        decided_by="Prof. Lin",
        decided_at=NOW,
        corrected_parent_version_id="v1-real",
        edge_id_factory=_ids(),
    )
    rejected = confirm_edge(
        _proposal(),
        ConfirmationOutcome.REJECTED,
        decided_by="Prof. Lin",
        decided_at=NOW,
    )

    assert accepted.edge is not None and accepted.edge.is_accepted
    assert corrected.edge is not None and corrected.corrects is not None
    assert rejected.edge is None and rejected.corrects is not None


def test_a_confirmation_is_frozen() -> None:
    """A decision is a record, and a record does not change.

    **What breaks it:** a mutable confirmation. The decision is what the
    archive says a person did, and a decision that can be edited in place
    is the same defect the correction rule avoids.
    """
    decision = confirm_edge(
        _proposal(),
        ConfirmationOutcome.ACCEPTED,
        decided_by="Prof. Lin",
        decided_at=NOW,
    )
    with pytest.raises((AttributeError, TypeError)):
        decision.decided_by = "somebody else"  # type: ignore[misc]
