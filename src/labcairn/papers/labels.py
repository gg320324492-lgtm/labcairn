"""The label set: the closed vocabulary an annotator chooses from.

**What this module is.** LC-P2-10's label set, as one value the annotation
guide, the gold manifest, the harness and the later work orders all import.
**Three axes, and one answer that belongs to every axis:**

- the **issue kind** — *what problem the advisor pointed at*;
- the **response state** — *whether anything answered it*;
- the **assessment outcome** — *whether the advice turned out to hold*.

**And the issue kinds are this project's own.** The upstream study
(``docs/research/upstream-study/arXivEdits.md``) records that the arXivEdits
taxonomy describes *what kind of text edit was made*, which is a different
axis from *what problem the advisor pointed at*: a rewrite can be motivated by
an evidence gap and be implemented as a paraphrase, so the two labels answer
different questions. **These twelve are the design's own label set** — the
research question, the novelty, the method, the data, the controls, the
statistical conclusion, the figures, the sources, the review response, the
language and format — and they are named here rather than imported, because a
renamed external class would claim a comparability that does not exist.

**The other two axes are the chain's own, and they are imported rather than
retyped.** The response states come from
:data:`labcairn.papers.responses.RESPONSE_STATES` and the assessment
outcomes from :data:`labcairn.papers.assessments.ASSESSMENT_OUTCOMES`,
because **a second spelling of "what a response state is" would be a second
vocabulary for the same rows** — and a gold set scored against one spelling
while the chain stores another is a gold set that measures nothing. The
import is the guarantee: the two cannot drift apart, because there is only
one of them.

**And ``UNKNOWN`` is an answer, not a missing value.** A comment whose
anchor does not pair, an assessment whose evidence is insufficient, a
response nobody made — each has an honest answer that is neither
"addressed" nor "not addressed". ``UNKNOWN`` is what the annotator says in
those cases, and **it is scored as an answer**. A gold set that cannot say
"we do not know" is a gold set that forces a guess, and a guess is the thing
the chain exists to refuse.

**``OTHER`` and ``UNKNOWN`` are not the same thing, and the difference is
the point.** ``other`` says the advisor pointed at a problem that is real and
that none of the twelve names: the annotator knows, and the taxonomy does
not. ``unknown`` says the annotator cannot tell. Collapsing them would
count a gap in the taxonomy as a gap in the reading.

**A label outside the set is refused by name.** Not by a comparison of two
lists, and not with a message that says only "invalid": the refusal names
the word that was wrong, so the person who wrote it can see which one it
was.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from labcairn.papers.assessments import ASSESSMENT_OUTCOMES as CHAIN_ASSESSMENT_OUTCOMES
from labcairn.papers.responses import RESPONSE_STATES as CHAIN_RESPONSE_STATES


class IssueKind(StrEnum):
    """What problem the advisor pointed at.

    **The axis is the advisor's problem, not the editor's edit.** Each
    member names a thing a reader of the manuscript could disagree with, and
    not a transformation of the text. A comment that asks for a control
    experiment is :attr:`CONTROLS_AND_ABLATION` whether the student adds a
    paragraph or rewrites one.
    """

    #: The research question itself, or the motivation for it. **"Why is this
    #: worth doing" and "what exactly is being asked."**
    RESEARCH_QUESTION_AND_MOTIVATION = "research_question_and_motivation"
    #: What the work claims that is new, and whether the claim holds up.
    NOVELTY_AND_CONTRIBUTION = "novelty_and_contribution"
    #: How the paper is laid out and how its argument is told.
    INTRODUCTION_AND_STORYLINE = "introduction_and_storyline"
    #: The design, the hypothesis, and the method as described.
    METHOD_AND_HYPOTHESIS = "method_and_hypothesis"
    #: The data itself: whether it is sound, adequate, and what it supports.
    DATA_QUALITY = "data_quality"
    #: The comparison that makes the claim stand up — baselines, controls,
    #: ablations.
    CONTROLS_AND_ABLATION = "controls_and_ablation"
    #: What the numbers are permitted to conclude.
    STATISTICAL_CONCLUSION = "statistical_conclusion"
    #: The figures: whether they show what the text says they show.
    FIGURES = "figures"
    #: The references: whether the claims rest on them, and whether they are
    #: cited correctly.
    SOURCES = "sources"
    #: An answer to a reviewer, and what was done with it.
    REVIEW_RESPONSE = "review_response"
    #: The writing and the presentation that is neither of the above.
    LANGUAGE_AND_FORMAT = "language_and_format"
    #: The advisor pointed at something real that none of the twelve names.
    #: **Not a shrug**: it says the reading was complete and the taxonomy
    #: was not enough. :data:`UNKNOWN` says the opposite.
    OTHER = "other"


class AnnotationAxis(StrEnum):
    """The three axes a label may sit on.

    **Three, and not one, because they answer three different questions.**
    What the advisor was pointing at; whether anything answered it; and
    whether the advice held. One label per comment would have had to choose
    which of those it was talking about.
    """

    #: What problem the advisor pointed at.
    ISSUE_KIND = "issue_kind"
    #: Whether anything answered it.
    RESPONSE_STATE = "response_state"
    #: Whether the advice turned out to hold.
    ASSESSMENT_OUTCOME = "assessment_outcome"


#: The answer that means "the annotator cannot tell".
#:
#: **A member of every axis, and never a null.** It is a value the
#: annotator chose, it is scored as an answer, and it is in the
#: distribution rather than filtered out of it.
UNKNOWN: Final[str] = "unknown"

#: The issue kinds, as the plain strings a manifest carries.
ISSUE_KINDS: Final[frozenset[str]] = frozenset(kind.value for kind in IssueKind)

#: The labels the issue-kind axis accepts: the twelve kinds and ``UNKNOWN``.
ISSUE_LABELS: Final[frozenset[str]] = ISSUE_KINDS | {UNKNOWN}

#: The labels the response-state axis accepts.
#:
#: **The chain's states, imported.** See the module docstring: a second
#: spelling would be a second vocabulary for the same rows. The imported
#: set is public under its own name — :data:`CHAIN_RESPONSE_STATES` — so
#: that a reader can check **identity** against the chain's module rather
#: than equality, and see that the words here are the chain's object and
#: not a copy of it.
RESPONSE_LABELS: Final[frozenset[str]] = frozenset(CHAIN_RESPONSE_STATES) | {UNKNOWN}

#: The labels the assessment-outcome axis accepts.
ASSESSMENT_LABELS: Final[frozenset[str]] = frozenset(CHAIN_ASSESSMENT_OUTCOMES) | {UNKNOWN}

#: Every axis and the labels it accepts.
LABELS_BY_AXIS: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    {
        AnnotationAxis.ISSUE_KIND: ISSUE_LABELS,
        AnnotationAxis.RESPONSE_STATE: RESPONSE_LABELS,
        AnnotationAxis.ASSESSMENT_OUTCOME: ASSESSMENT_LABELS,
    }
)

#: What each axis asks, in one sentence.
#:
#: **Here, so that the guide and the manifest cannot drift apart.** The
#: guide explains each axis at length; the axis's question is the one
#: sentence both must say the same way.
AXIS_QUESTIONS: Final[Mapping[str, str]] = MappingProxyType(
    {
        AnnotationAxis.ISSUE_KIND: ("What problem did the advisor point at?"),
        AnnotationAxis.RESPONSE_STATE: ("Did anything in the manuscript answer it?"),
        AnnotationAxis.ASSESSMENT_OUTCOME: ("Did the advice turn out to hold?"),
    }
)


def labels_for(axis: str) -> frozenset[str]:
    """The labels the axis *axis* accepts.

    :raises ValueError: when there is no such axis. **The refusal names the
        axis**, because an axis that does not exist is a different mistake
        from a label that does not belong to one.
    """
    try:
        return LABELS_BY_AXIS[axis]
    except KeyError:
        raise ValueError(
            f"{axis} is not an annotation axis. The axes are: "
            f"{', '.join(sorted(LABELS_BY_AXIS))}. An axis is what a label is "
            "an answer to, and an answer to nothing is not an annotation."
        ) from None


def is_label(axis: str, label: str) -> bool:
    """Whether *label* is a label the axis *axis* accepts.

    **A question, and never a refusal.** A caller that only wants to know
    does not have to catch anything.
    """
    return label in LABELS_BY_AXIS.get(axis, frozenset())


def check_label(axis: str, label: str) -> str:
    """The label *label*, if the axis *axis* accepts it.

    :raises ValueError: when the axis does not exist, or when the label is
        outside it. **The refusal names the label that was wrong** and
        lists the labels that would have been accepted, so the person who
        wrote it can see which word it was — a refusal that says only
        "invalid" leaves them to guess.
    """
    accepted = labels_for(axis)
    if label in accepted:
        return label
    raise ValueError(
        f"{label!r} is not a label on the {axis} axis. The labels are: "
        f"{', '.join(sorted(accepted))}. The set is closed on purpose: a "
        "label outside it would be a second vocabulary for the same rows, "
        "and a gold set scored against two vocabularies measures nothing."
    )


def describe_axis(axis: str) -> str:
    """The question the axis *axis* asks, in one sentence.

    :raises ValueError: when there is no such axis, by the same rule
        :func:`labels_for` refuses one.
    """
    labels_for(axis)
    return AXIS_QUESTIONS[axis]


__all__ = [
    "ASSESSMENT_LABELS",
    "AXIS_QUESTIONS",
    "CHAIN_ASSESSMENT_OUTCOMES",
    "CHAIN_RESPONSE_STATES",
    "ISSUE_KINDS",
    "ISSUE_LABELS",
    "LABELS_BY_AXIS",
    "RESPONSE_LABELS",
    "UNKNOWN",
    "AnnotationAxis",
    "IssueKind",
    "check_label",
    "describe_axis",
    "is_label",
    "labels_for",
]
