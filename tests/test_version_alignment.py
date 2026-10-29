"""The alignment, and the cases where it must refuse to decide.

**What is under test.** LC-P2-08 T02: the alignment that proposes which
version a child came from, and the three things it must never do.

**The three refusals, and they are the design's rule made executable.**

1. **A file name never decides the order.** ``最终版2.docx`` is not a
   statement about which is newer, and the design says so outright.
2. **A modification time never decides the order.** A copied file carries
   the copy's time.
3. **When the evidence points two ways, the alignment does not decide.**
   A similarity score may propose an order; it may not settle one.

**And the case that decides the design.** Two drafts whose prose is nearly
identical and whose **results differ** are two versions, and the
difference is the scientific content. A similarity threshold scores them
as *the same version*, because the prose barely moved — which is the
design's *"图表数字变化但文字不变"* and the reason the number signal is
not optional.
"""

from __future__ import annotations

import pytest

from labcairn.papers.alignment import (
    AlignmentProposal,
    fingerprint,
    propose_alignment,
)

#: Two versions of one paper. The second adds a section and a number.
DRAFT_V1 = """Introduction
We estimate the parameter from a single observation.
Our method is evaluated on three benchmarks.

Method
The estimator is computed in closed form for each observation.

Results
The parameter is recovered with an error of 0.12 on the synthetic set.
"""

DRAFT_V2 = """Introduction
We estimate the parameter from a single observation.
Our method is evaluated on three benchmarks.

Method
The estimator is computed in closed form for each observation.

Results
The parameter is recovered with an error of 0.09 on the synthetic set.

Discussion
The improvement is consistent across every benchmark we ran.
"""


def _kinds(proposal: AlignmentProposal) -> set[str]:
    return {item.kind for item in proposal.evidence}


# --------------------------------------------------------------------------- #
# the alignment proposes
# --------------------------------------------------------------------------- #


def test_a_revised_draft_is_proposed_to_come_from_its_parent() -> None:
    """Two versions of one paper are proposed as parent and child.

    **What breaks it:** a fingerprint that collects nothing, so every
    candidate scores zero and every proposal comes back "no signal".
    """
    proposal = propose_alignment(
        "v2", DRAFT_V2, {"v1": DRAFT_V1, "other": "A completely different paper."}
    )

    assert proposal.candidates[0] == "v1"
    assert proposal.decided is True
    assert proposal.confidence > 0.0
    assert "shared_structure" in _kinds(proposal)


def test_the_evidence_is_named_and_carries_its_spans() -> None:
    """A reader must be able to see **why** the system thinks so.

    **What breaks it:** returning a score with no explanation. The design
    says every link keeps its *"源 span"* — its source spans — and a
    number with nothing behind it is a claim nobody can check.
    """
    proposal = propose_alignment("v2", DRAFT_V2, {"v1": DRAFT_V1})

    assert proposal.evidence
    for item in proposal.evidence:
        assert item.kind
        assert item.detail
        assert item.spans, f"the {item.kind} signal carries no span"


def test_a_candidate_that_shares_nothing_comes_last() -> None:
    """An unrelated document is not proposed.

    **What breaks it:** a fingerprint that is too coarse — for instance
    one that keeps only the first hundred characters, so two documents
    with a common preamble look alike.
    """
    proposal = propose_alignment(
        "v2",
        DRAFT_V2,
        {"v1": DRAFT_V1, "unrelated": "Quantum chromodynamics. Hadron spectra. Gluons."},
    )

    assert proposal.candidates[0] == "v1"


# --------------------------------------------------------------------------- #
# the three refusals
# --------------------------------------------------------------------------- #


def test_a_file_name_never_decides_the_order() -> None:
    """A name is not evidence, and the alignment does not collect one.

    **What breaks it:** reading the version's label and using it. The
    design says plainly that ``最终版2.docx`` is not a statement about
    which is newer, and a name-based rule would make ``最终版`` the parent
    of everything.

    **The property is structural.** The fingerprint has no field for a
    name, so the name cannot be used — not because the rule is checked
    somewhere, but because the thing was never gathered.
    """
    print_ = fingerprint(DRAFT_V1)

    assert not hasattr(print_, "name")
    assert not hasattr(print_, "file_name")
    assert not hasattr(print_, "label")


def test_a_modification_time_never_decides_the_order() -> None:
    """A timestamp is not evidence, and the alignment does not collect one.

    **What breaks it:** collecting an mtime and sorting by it. A copied
    file carries the copy's time, so the most recent file is often the
    least informative one about the history.
    """
    print_ = fingerprint(DRAFT_V1)

    assert not hasattr(print_, "mtime")
    assert not hasattr(print_, "modified_at")
    assert not hasattr(print_, "timestamp")


def test_the_alignment_refuses_when_the_evidence_points_two_ways() -> None:
    """Two candidates the evidence cannot separate produce **no decision**.

    **This is the design's rule in its sharpest form.** *"禁止仅靠相似度
    静默确定版本顺序"* — a similarity score may not silently determine a
    version's order. When two candidates are within the margin, the
    alignment returns both, says ``decided = False``, and names which two
    it could not choose between.

    **What breaks it:** picking the higher score. The two candidates here
    are near-identical, and the difference between them is inside the
    noise of any similarity measure — so a decision made here is a
    decision made by a number.
    """
    proposal = propose_alignment(
        "v2",
        DRAFT_V2,
        {
            "parent-a": DRAFT_V1,
            "parent-b": DRAFT_V1.replace("0.12", "0.13"),
        },
    )

    assert proposal.decided is False
    assert proposal.reason
    assert (
        "may not silently decide an order" in proposal.reason
        or "A person chooses" in proposal.reason
    )
    assert set(proposal.ambiguous_between) == {"parent-a", "parent-b"}


def test_no_evidence_at_all_produces_no_decision_and_says_why() -> None:
    """A version that matches nothing is not forced onto a parent.

    **What breaks it:** returning the only candidate anyway, with a low
    confidence. A proposal with a confidence of 0.0 and a stated reason
    is a question to a person; a proposal with a confidence of 0.0 and no
    reason looks like an answer.
    """
    proposal = propose_alignment(
        "v2",
        "Something entirely unrelated to any of these documents.",
        {"v1": DRAFT_V1},
    )

    assert proposal.decided is False
    assert proposal.reason
    assert "no signal pointed either way" in proposal.reason


def test_a_proposal_is_a_proposal_even_when_the_evidence_is_decisive() -> None:
    """Confidence is a number and not a decision.

    **What breaks it:** letting ``decided`` settle the relationship. The
    design's rule is that a score may not decide an order — and a
    ``decided`` flag that means "the evidence was clear" is exactly the
    kind of quiet decision the rule forbids. **The edge that carries the
    proposal still has no acceptor until a person accepts it.**
    """
    proposal = propose_alignment("v2", DRAFT_V2, {"v1": DRAFT_V1})

    assert proposal.decided is True
    assert proposal.confidence > 0.0
    # The proposal is still a proposal: it names no acceptor and settles
    # nothing by itself.
    assert proposal.is_a_proposal is True


# --------------------------------------------------------------------------- #
# the case that decides the design
# --------------------------------------------------------------------------- #


def test_two_drafts_that_differ_only_in_their_results_are_two_versions() -> None:
    """**The design's case: 图表数字变化但文字不变.**

    Two drafts whose prose is nearly identical and whose **results differ**
    are two versions, and the difference is the scientific content. A
    prose-similarity threshold scores them as the same version, because
    the text barely moved.

    **What breaks it:** a fingerprint with no numbers, or a signal that
    only reads the prose. The two drafts here differ in one number and one
    added paragraph — and the number is the one that matters.
    """
    changed_result = DRAFT_V1.replace("an error of 0.12", "an error of 0.09")

    proposal = propose_alignment("v2", changed_result, {"v1": DRAFT_V1})

    # The number signal is present and it says the number moved.
    numbers = [item for item in proposal.evidence if item.kind == "matching_number"]
    assert numbers, "the changed result must be visible to the alignment"
    assert "0.09" in numbers[0].spans
    assert "0.12" in numbers[0].spans


def test_the_number_signal_is_not_optional() -> None:
    """A version pair that shares no structure still shows its numbers.

    **What breaks it:** dropping the number signal from the fingerprint.
    Two documents that share a result and nothing else would then look
    unrelated, and the strongest evidence in the design's list would be
    gone.
    """
    only_numbers = "The measured value was 3.14159 under the same conditions."

    print_ = fingerprint(only_numbers)
    assert "3.14159" in print_.numbers


def test_a_version_with_a_changed_result_is_not_the_same_version() -> None:
    """The changed result keeps the two drafts apart.

    **This is the negative of the design's case, and it is the one a
    similarity threshold fails.** The prose is the same; the science is
    not. The alignment must keep them as separate candidates rather than
    reporting a high confidence that they are the same thing.

    **What the alignment does here is narrow and deliberate:** it does not
    claim the two are different versions on the strength of one number —
    that would be a decision by a score. It reports the number signal,
    with the changed value visible, and leaves the judgement where the
    design puts it.
    """
    changed_result = DRAFT_V1.replace("an error of 0.12", "an error of 0.09")

    proposal = propose_alignment("v2", changed_result, {"v1": DRAFT_V1})

    numbers = [item for item in proposal.evidence if item.kind == "matching_number"]
    assert numbers
    assert "0.09" in numbers[0].spans
    assert "0.12" in numbers[0].spans
    # And the detail says the number moved, so a reader sees the change
    # rather than inferring it.
    assert "only in the child" in numbers[0].detail
    assert "only in the parent" in numbers[0].detail


def test_the_alignment_is_stable_on_equal_evidence() -> None:
    """Equal evidence produces the same order every time.

    **What breaks it:** sorting without a tie-break. Two candidates with
    identical evidence would swap places between runs, and an archive
    that answers a question in two ways is an archive nobody can rely on.

    **The tie is broken by the id**, so the order is a function of the
    content and not of the dictionary's iteration order.
    """
    first = propose_alignment("v2", DRAFT_V2, {"a": DRAFT_V1, "b": DRAFT_V1})
    second = propose_alignment("v2", DRAFT_V2, {"b": DRAFT_V1, "a": DRAFT_V1})

    assert first.candidates == second.candidates
    assert first.candidates == ("a", "b")


def test_an_empty_candidate_set_is_refused_rather_than_guessed() -> None:
    """No candidates means no proposal, and the reason says so."""
    proposal = propose_alignment("v2", DRAFT_V2, {})

    assert proposal.decided is False
    assert proposal.reason
    assert "no candidate" in proposal.reason


@pytest.mark.parametrize(
    "text",
    ["", "   ", "\n\n\n"],
)
def test_an_empty_version_is_still_a_version(text: str) -> None:
    """Empty text is handled, not crashed on.

    **What breaks it:** an index error on an empty passage list. A version
    whose text could not be extracted is a version with no evidence, and
    it must come back as such rather than as an exception.
    """
    proposal = propose_alignment("v2", text, {"v1": DRAFT_V1})

    assert proposal.decided is False
    assert proposal.reason
