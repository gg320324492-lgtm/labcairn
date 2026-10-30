"""The label set is closed, is the chain's own, and says ``UNKNOWN`` out loud.

**What this file watches.** LC-P2-10's T00 put the annotation vocabulary in
one module so that the guide, the manifest, the harness and the later work
orders could not each spell a label their own way. A file that says a label
is valid does not hold that property — **a file that refuses a label the
set does not contain does.**

The three things under test are:

- **the set is closed**, and a label outside it is refused *by name*;
- **the vocabulary is the chain's own**, and not an imported taxonomy that
  answers a different question;
- **``UNKNOWN`` is an answer**, and not a hole where an answer should be.

**Why the issue kinds are tied to a document in the tree.** The twelve kinds
are the design's own label set, and the design's own words for them are
quoted in ``docs/research/upstream-study/arXivEdits.md`` — the study that
says why arXivEdits' classes cannot be reused. Tying the set to that
document means **a change to the set without a change to the design's
record fails here**, which is the point of a witness: it is not enough for
the vocabulary to look right, it has to still be the vocabulary the record
names.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import labcairn.papers.assessments as assessments_module
import labcairn.papers.labels as labels_module
import labcairn.papers.responses as responses_module
from labcairn.papers.assessments import ASSESSMENT_OUTCOMES
from labcairn.papers.labels import (
    ASSESSMENT_LABELS,
    AXIS_QUESTIONS,
    ISSUE_KINDS,
    ISSUE_LABELS,
    LABELS_BY_AXIS,
    RESPONSE_LABELS,
    UNKNOWN,
    AnnotationAxis,
    IssueKind,
    check_label,
    describe_axis,
    is_label,
    labels_for,
)
from labcairn.papers.responses import RESPONSE_STATES

pytestmark = pytest.mark.unit

#: The study that says why arXivEdits' classes are not Phase 2's, and that
#: quotes the design's own label set.
_UPSTREAM_STUDY = Path("docs") / "research" / "upstream-study" / "arXivEdits.md"

#: The design's label set as the study quotes it, and the section the quote
#: is in.
_DESIGN_SET = re.compile(r"label set \(([^)]*)\)", re.DOTALL)


def _design_kinds() -> tuple[str, ...]:
    """The design's own kinds, read out of the study that quotes them.

    **Read, not transcribed.** A transcribed list is a second copy of the
    record, and a second copy drifts; the file in the tree is the record.
    """
    text = _UPSTREAM_STUDY.read_text(encoding="utf-8")
    match = _DESIGN_SET.search(text)
    assert match is not None, (
        f"{_UPSTREAM_STUDY} no longer quotes the design's LC-P2-10 label set. The "
        "issue kinds are the design's own, and the record that says so has to be "
        "in the tree for the set to be more than a list somebody remembers."
    )
    quoted = match.group(1)
    return tuple(
        part.strip().strip('"').replace(" ", "_") for part in quoted.split(",") if part.strip()
    )


def test_a_label_outside_the_set_is_refused() -> None:
    """A1: the set is closed, and the refusal names the label.

    **The refusal has to name the word.** A message that says only
    "invalid" leaves the person who wrote the label to guess which of
    three words it was, and a witness that only checked that *something*
    was raised would pass on a message that helps nobody.
    """
    with pytest.raises(ValueError) as refusal:
        check_label(AnnotationAxis.ISSUE_KIND, "edit_intent")

    message = str(refusal.value)
    assert "edit_intent" in message, (
        f"the refusal does not name the label that was wrong: {message!r}. A "
        "refusal that does not name it leaves the person who wrote it to guess."
    )
    assert AnnotationAxis.ISSUE_KIND in message, (
        f"the refusal does not name the axis: {message!r}. A label is an answer "
        "to an axis, and a refusal that does not say which one leaves the same "
        "guess open."
    )
    for accepted in sorted(ISSUE_LABELS):
        assert accepted in message, (
            f"the refusal does not list the accepted labels, so {accepted!r} is "
            f"missing from it: {message!r}. The set is closed, and a closed set "
            "that cannot be read cannot be used to fix a label."
        )


def test_the_refusal_lists_every_label_of_the_axis_it_refused() -> None:
    """A refused label names the axis, and the axis's own labels come with it.

    **The three axes have different vocabularies**, so a refusal that
    listed the wrong axis's labels would be worse than no list at all.
    """
    with pytest.raises(ValueError) as refusal:
        check_label(AnnotationAxis.RESPONSE_STATE, "data_quality")

    message = str(refusal.value)
    assert "data_quality" in message
    for accepted in sorted(RESPONSE_LABELS):
        assert accepted in message


def test_unknown_is_a_label_and_not_a_missing_value() -> None:
    """A2: ``UNKNOWN`` is an answer, and it is scored as one.

    **On every axis, and not as a null.** ``UNKNOWN`` means "the annotator
    cannot tell", which is a different fact from "no answer was recorded",
    and a gold set that cannot say "we do not know" is a gold set that
    forces a guess.
    """
    for axis in AnnotationAxis:
        assert UNKNOWN in labels_for(axis), (
            f"{axis.value!r} does not accept {UNKNOWN!r}. An annotation that "
            "cannot record a doubt is an annotation that forces a guess."
        )
        assert is_label(axis, UNKNOWN)
        assert check_label(axis, UNKNOWN) == UNKNOWN


def test_unknown_is_spelled_unknown() -> None:
    """The label is the word ``unknown``, in the set and in every manifest.

    **The spelling is the contract.** A manifest carries the word, so a
    constant whose value changed would leave every manifest's ``unknown``
    outside the set meant to accept it — **and the witness above would
    still be green**, because it compared the constant with itself. That
    is exactly the kind of witness that watches nothing: the check has to
    be against the word the record uses.
    """
    assert UNKNOWN == "unknown", (
        f"the unknown label is spelled {UNKNOWN!r}, not 'unknown'. The manifest "
        "carries the word, and a set that accepts a different spelling accepts "
        "none of the manifests."
    )
    for axis in AnnotationAxis:
        assert "unknown" in labels_for(axis), (
            f"{axis.value!r} does not accept the word 'unknown'. The manifest "
            "writes that word, and this set does not take it."
        )


def test_other_and_unknown_are_not_the_same_answer() -> None:
    """``other`` is a complete reading; ``unknown`` is an incomplete one.

    **The difference is the point of having both.** ``other`` says the
    advisor pointed at something real that the taxonomy does not name;
    ``unknown`` says the annotator could not tell what it was. Counting
    them as one would score a gap in the taxonomy as a gap in the reading.
    """
    assert IssueKind.OTHER.value in ISSUE_LABELS
    assert IssueKind.OTHER.value != UNKNOWN
    assert UNKNOWN not in ISSUE_KINDS, (
        f"{UNKNOWN!r} is in the issue kinds, so a reader could not tell a "
        "complete reading of an unnamed problem from an incomplete one."
    )


def test_the_labels_are_the_chains_own_vocabulary() -> None:
    """A8: the vocabulary is the chain's own, and not an imported taxonomy.

    **Three parts, and each one is load-bearing.**

    1. The response states and the assessment outcomes are the chain's,
       element for element — a second spelling of either would be a second
       vocabulary for the same rows.
    2. The three axes do not share a vocabulary. If the issue kinds were
       the chain's words reused, the axes would be one axis spelled three
       ways.
    3. The issue kinds are the design's own set, read out of the tree, and
       they do not overlap the taxonomy the upstream study says cannot be
       reused.
    """
    assert RESPONSE_LABELS - {UNKNOWN} == RESPONSE_STATES, (
        "the response labels are not the chain's response states. The chain "
        f"holds {sorted(RESPONSE_STATES)} and the label set holds "
        f"{sorted(RESPONSE_LABELS - {UNKNOWN})}. A gold set scored against one "
        "spelling while the chain stores another measures nothing."
    )
    assert ASSESSMENT_LABELS - {UNKNOWN} == ASSESSMENT_OUTCOMES, (
        "the assessment labels are not the chain's assessment outcomes. The "
        f"chain holds {sorted(ASSESSMENT_OUTCOMES)} and the label set holds "
        f"{sorted(ASSESSMENT_LABELS - {UNKNOWN})}."
    )

    issue_without_unknown = ISSUE_LABELS - {UNKNOWN}
    assert not issue_without_unknown & RESPONSE_STATES, (
        f"the issue kinds reuse the chain's response states: "
        f"{sorted(issue_without_unknown & RESPONSE_STATES)}. The axes answer "
        "different questions, and an axis that borrows another's words cannot "
        "be read."
    )
    assert not issue_without_unknown & ASSESSMENT_OUTCOMES, (
        f"the issue kinds reuse the chain's assessment outcomes: "
        f"{sorted(issue_without_unknown & ASSESSMENT_OUTCOMES)}."
    )

    design = _design_kinds()
    assert design, "the design's label set is empty, so there is nothing to tie to."
    for kind in design:
        if kind == "other/unknown":
            # The design writes "other/unknown" as one entry; the label set
            # separates them, because they are two different answers.
            assert IssueKind.OTHER.value in ISSUE_LABELS
            assert UNKNOWN in ISSUE_LABELS
            continue
        assert kind in ISSUE_LABELS, (
            f"{kind!r} is in the design's label set and not in the label set: "
            f"{sorted(ISSUE_LABELS)}. The kinds are the design's own, so a kind "
            "that the design names and the tree does not is a change nobody "
            "recorded."
        )


def test_the_label_module_holds_the_chains_words_and_not_a_copy_of_them() -> None:
    """A8's source half: the words are the chain's object, not a copy of it.

    **Why the equality in the witness above is not enough.** It says the
    two sets *agree*. It cannot say the label set **is** the chain's set
    rather than a copy of it, because a copy that is in step today agrees
    today — and the module's whole claim is that there is no second
    spelling to fall out of step.

    **Identity is the evidence, and only identity.** A copy is a different
    object however equal it is, so the check is that the label module's
    set *is* the chain's set — the same object, out of the chain's own
    module — and that an axis's labels are that object plus ``UNKNOWN``.
    """
    assert labels_module.CHAIN_RESPONSE_STATES is responses_module.RESPONSE_STATES, (
        "the label module's response states are not the chain's own object. A "
        "copy that agrees today can fall out of step tomorrow, and a second "
        "spelling of the chain's words is exactly what this module says it "
        "does not have."
    )
    assert labels_module.CHAIN_ASSESSMENT_OUTCOMES is assessments_module.ASSESSMENT_OUTCOMES, (
        "the label module's assessment outcomes are not the chain's own "
        "object, for the same reason the response states have to be the "
        "chain's."
    )
    assert labels_module.CHAIN_RESPONSE_STATES | {UNKNOWN} == labels_module.RESPONSE_LABELS, (
        "the response labels are not the chain's states plus UNKNOWN, so the "
        "axis has drifted from the vocabulary it is supposed to be the label "
        "set of."
    )
    assert labels_module.CHAIN_ASSESSMENT_OUTCOMES | {UNKNOWN} == labels_module.ASSESSMENT_LABELS, (
        "the assessment labels are not the chain's outcomes plus UNKNOWN, for "
        "the same reason the response labels have to be."
    )


def test_every_axis_is_closed_and_its_labels_are_a_finite_set() -> None:
    """Every axis names a finite set, and the table holds all of them.

    **A witness that the table is complete.** If an axis were added to
    :data:`LABELS_BY_AXIS` without a question, or a question without an
    axis, the two would drift — and the drift would be invisible to a
    caller that only ever uses the axes it knows.
    """
    assert set(LABELS_BY_AXIS) == set(AXIS_QUESTIONS), (
        "the axes and their questions are not the same set: "
        f"{sorted(set(LABELS_BY_AXIS) ^ set(AXIS_QUESTIONS))}. A question with "
        "no axis is asked of nothing, and an axis with no question is answered "
        "at random."
    )
    for axis, labels in LABELS_BY_AXIS.items():
        assert labels, f"{axis!r} accepts no label at all."
        assert UNKNOWN in labels
        assert labels == labels_for(axis)
        assert describe_axis(axis)


def test_an_axis_that_does_not_exist_is_refused_by_name() -> None:
    """An unknown axis is refused, and it is not the same refusal as a bad label.

    **Two different mistakes.** A label outside an axis is a word that is
    not in the vocabulary; an axis that does not exist is a question that
    was never asked. Collapsing them would make a caller's typo look like
    a data problem.
    """
    with pytest.raises(ValueError) as refusal:
        labels_for("sentiment")

    message = str(refusal.value)
    assert "sentiment" in message
    assert AnnotationAxis.ISSUE_KIND in message, (
        "the refusal does not list the axes that do exist, so there is nothing "
        f"in it to correct the mistake with: {message!r}"
    )


def test_is_label_answers_without_raising() -> None:
    """The question and the refusal are two functions, and the question raises nothing.

    **A caller that only wants to know should not have to catch
    anything** — and an axis that does not exist is not a label of it.
    """
    assert is_label(AnnotationAxis.ISSUE_KIND, IssueKind.DATA_QUALITY.value)
    assert not is_label(AnnotationAxis.ISSUE_KIND, "not_a_kind")
    assert not is_label("not_an_axis", IssueKind.DATA_QUALITY.value)


def test_the_accepted_label_is_returned_unchanged() -> None:
    """An accepted label comes back as it went in.

    **No normalisation.** A function that quietly rewrote a label would
    make the manifest's contents differ from the annotator's words, and
    the difference would be invisible in the counts.
    """
    for axis in AnnotationAxis:
        for label in sorted(labels_for(axis)):
            assert check_label(axis, label) == label
