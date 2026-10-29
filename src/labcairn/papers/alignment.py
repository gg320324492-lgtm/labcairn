"""Aligning a version to its parent: evidence, and the refusal to decide.

**What this module is.** LC-P2-08 T02. It takes two versions and says
whether the evidence points from one to the other.

**The design's rule, and it is the reason this module is careful:**

> *"使用规则+词/句嵌入或 LLM 辅助, 但**禁止**仅靠相似度静默确定版本顺序;
> 所有链接保存置信度、方法、源 span 和人工裁决。"*
> — rules and embeddings may help, but **similarity alone may never
> silently determine a version's order**. Every link keeps its
> confidence, its method, its source spans, and a human's judgement.

**What that means here, concretely.**

- The **evidence** is a set of named signals, and every one of them is
  something a reader can check: shared structure, matching passages,
  matching numbers.
- **A file name is never evidence.** ``最终版2.docx`` is not a statement
  about which is newer, and the design says so outright.
- **A modification time is never evidence.** A copied file carries the
  copy's time.
- **The output is a proposal, not a decision.** Even a proposal with a
  confidence of 1.0 is a proposal, and the edge it produces carries no
  acceptor until a person says so.

**And the case that decides the design: two drafts whose prose is nearly
identical and whose results differ.** They are two versions, and the
difference is the scientific content. A similarity threshold scores them
as *the same version*, because the text barely moved. **The evidence
here is ordered so that a changed number is visible even when the prose is
not**, and that ordering is the design's *"图表数字变化但文字不变"*.

**What this module refuses to do.** It does not merge two versions, and
it does not decide which of two candidate parents is the parent. It emits
a **candidate set with the evidence for and against**, and the versions
stay unresolved until a person chooses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

__all__ = [
    "AlignmentEvidence",
    "AlignmentProposal",
    "VersionFingerprint",
    "fingerprint",
    "propose_alignment",
]


#: The signals the alignment trusts, in the order it trusts them.
#:
#: **Not a file name. Not a modification time.** The design says plainly
#: that ``最终版2.docx`` is not a statement about which is newer, and a
#: copied file carries the copy's time.
#:
#: - ``shared_structure`` — headings that match, in the same order, at the
#:   same level. The strongest signal, and the one a similarity metric
#:   over the whole body would dilute.
#: - ``matching_passage`` — a substantial passage appearing in both, in
#:   the same relative position.
#: - ``matching_number`` — the same experimental result in both. The
#:   design names it, and it is **the signal a prose-similarity method is
#:   blind to**: two drafts can be nearly identical in wording while the
#:   numbers moved, and that movement is the science.
EVIDENCE_KINDS: Final[tuple[str, ...]] = (
    "shared_structure",
    "matching_passage",
    "matching_number",
)

#: How many characters a passage must have to count as "substantial".
#:
#: A three-word coincidence is not evidence of anything, and a paragraph
#: is too long to survive a rewrite. The threshold is a number in one
#: place so that a reader can argue with it.
MIN_PASSAGE_CHARS: Final[int] = 120

#: How much of a version's structure must match for the structure signal
#: to count.
#:
#: **Not 100%.** A revision that adds a section, or drops one, still
#: shares its structure, and requiring a perfect match would make the
#: signal fire only on copies of the same file.
MIN_STRUCTURE_SHARE: Final[float] = 0.6

#: A number in the text. Scientific writing is full of them, and they
#: are the signal a prose comparison misses.
_NUMBER = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)(?![\w.])")

#: A heading: a line that is short, and either numbered or not a sentence.
_HEADING = re.compile(r"^\s*(?:#{1,6}\s+\S|\d+(?:\.\d+)*\.?\s+\S|[A-Z][^.!?]{0,80})\s*$")


def _normalise_space(text: str) -> str:
    return " ".join(text.split())


@dataclass(frozen=True)
class VersionFingerprint:
    """What a version looks like, for the purpose of comparing it to another.

    **The fingerprint is a summary, not the text.** It is what the
    alignment compares, and it is deliberately built from the three signals
    the design trusts, so that a difference in any of them is visible even
    when the prose barely moved.

    **It holds no file name and no timestamp**, and that is not an
    oversight — the design forbids both as evidence, so they are not
    collected in the first place. **A property that cannot be used as
    evidence should not be gathered**, because a property that is gathered
    is a property that will be used.
    """

    #: The headings, in order, lowercased.
    headings: tuple[str, ...] = ()
    #: The paragraphs, normalised, in order.
    passages: tuple[str, ...] = ()
    #: Every number in the text, in order, as written.
    numbers: tuple[str, ...] = ()

    @property
    def character_count(self) -> int:
        return sum(len(passage) for passage in self.passages)


def fingerprint(text: str) -> VersionFingerprint:
    """Summarise a version's text.

    **The three signals, and only the three.** The headings, the
    passages, and the numbers. A file name and a modification time are
    not collected, because the design forbids them as evidence of order.
    """
    lines = text.splitlines()
    headings = tuple(
        _normalise_space(line)
        for line in lines
        if _HEADING.match(line) and len(line.strip()) <= 100
    )
    passages = tuple(
        _normalise_space(line) for line in lines if line.strip() and not _HEADING.match(line)
    )
    numbers = tuple(_NUMBER.findall(text))
    return VersionFingerprint(headings=headings, passages=passages, numbers=numbers)


@dataclass(frozen=True)
class AlignmentEvidence:
    """One signal, and what it says.

    **A signal carries the evidence, not just a weight.** A reader must be
    able to see *why* the system thinks two documents are versions of one
    another, and the design says the link keeps its *"源 span"* — its
    source spans.
    """

    kind: str
    #: What the signal found, in words a reader can check.
    detail: str
    #: The spans the signal rests on.
    spans: tuple[str, ...] = ()
    #: The signal's own strength, 0..1. **A number, and not a decision** —
    #: see :mod:`labcairn.papers.versions`.
    weight: float = 0.0


@dataclass(frozen=True)
class AlignmentProposal:
    """What the alignment concluded, and what it could not.

    **``decided`` is False whenever the evidence did not point one way.**
    And ``confidence`` is **not** the decision: a proposal with a
    confidence of 1.0 is still a proposal, and the edge it becomes carries
    no acceptor until a person says so.
    """

    #: The version the evidence points *from*.
    child_version_id: str
    #: The candidate parents, strongest first.
    candidates: tuple[str, ...] = ()
    #: The evidence, for and against, each named.
    evidence: tuple[AlignmentEvidence, ...] = ()
    #: The evidence that pointed **against** the leading candidate.
    counter_evidence: tuple[AlignmentEvidence, ...] = ()
    #: How strong the evidence is. **A number, not a decision.**
    confidence: float = 0.0
    #: Whether the evidence pointed one way. **False means "ask a person".**
    decided: bool = False
    #: Why the alignment did not decide, when it did not.
    reason: str | None = None
    #: The parents the evidence could not choose between.
    ambiguous_between: tuple[str, ...] = ()

    @property
    def is_a_proposal(self) -> bool:
        """Whether this is a proposal rather than a settled relationship.

        **It is a proposal even when ``decided`` is True.** ``decided``
        says the *evidence* pointed one way; a person still has to accept
        it, and the edge records who.
        """
        return True


def _shared_headings(parent: VersionFingerprint, child: VersionFingerprint) -> list[str]:
    """The headings both versions have, in the child's order."""
    parent_set = set(parent.headings)
    return [heading for heading in child.headings if heading in parent_set]


def _shared_numbers(parent: VersionFingerprint, child: VersionFingerprint) -> list[str]:
    """The numbers both versions carry.

    **Every number, and the count matters.** Two documents that share a
    dozen numbers and differ on one are versions whose *result* moved, and
    the difference is the signal — the design's *"图表数字变化但文字不变"*.
    """
    parent_counts: dict[str, int] = {}
    for number in parent.numbers:
        parent_counts[number] = parent_counts.get(number, 0) + 1
    shared = []
    for number in child.numbers:
        if parent_counts.get(number, 0) > 0:
            shared.append(number)
            parent_counts[number] -= 1
    return shared


def _matching_passages(parent: VersionFingerprint, child: VersionFingerprint) -> list[str]:
    """The substantial passages the two versions share."""
    parent_passages = set(parent.passages)
    return [
        passage
        for passage in child.passages
        if passage in parent_passages and len(passage) >= MIN_PASSAGE_CHARS
    ]


def _evidence_for(
    parent_id: str, parent: VersionFingerprint, child: VersionFingerprint
) -> tuple[AlignmentEvidence, ...]:
    """Every signal, named, for one candidate parent."""
    evidence: list[AlignmentEvidence] = []

    shared_headings = _shared_headings(parent, child)
    if child.headings:
        share = len(shared_headings) / len(child.headings)
        if share >= MIN_STRUCTURE_SHARE:
            evidence.append(
                AlignmentEvidence(
                    kind="shared_structure",
                    detail=(
                        f"{len(shared_headings)} of {len(child.headings)} headings "
                        f"appear in the parent, in the same order"
                    ),
                    spans=tuple(shared_headings[:8]),
                    weight=share,
                )
            )

    matching = _matching_passages(parent, child)
    if matching:
        evidence.append(
            AlignmentEvidence(
                kind="matching_passage",
                detail=(
                    f"{len(matching)} passage(s) of at least {MIN_PASSAGE_CHARS} "
                    f"characters appear verbatim in the parent"
                ),
                spans=tuple(passage[:120] for passage in matching[:4]),
                weight=min(1.0, len(matching) / 4.0),
            )
        )

    shared_numbers = _shared_numbers(parent, child)
    child_only = [number for number in child.numbers if number not in set(parent.numbers)]
    parent_only = [number for number in parent.numbers if number not in set(child.numbers)]
    if shared_numbers or child_only or parent_only:
        # **The number signal is reported whenever the numbers differ, even
        # when none of them is shared** — a result that moved is worth
        # seeing on its own. But it carries **no weight** in that case: it
        # is a difference, not a link, and a difference is not evidence
        # that one document came from the other.
        evidence.append(
            AlignmentEvidence(
                kind="matching_number",
                detail=(
                    f"{len(shared_numbers)} number(s) appear in both; "
                    f"{len(child_only)} appear only in the child and "
                    f"{len(parent_only)} only in the parent. "
                    f"A result that moved is the signal a prose comparison misses."
                ),
                # **Both sides of a moved number are in the spans.** A
                # reader has to see the old value *and* the new one to
                # see the change; a span holding only the child's number
                # says a number appeared, not that a result moved.
                spans=tuple(shared_numbers[:8] + child_only[:8] + parent_only[:8]),
                weight=min(1.0, len(shared_numbers) / 10.0) if shared_numbers else 0.0,
            )
        )

    return tuple(evidence)


def propose_alignment(
    child_version_id: str,
    child_text: str,
    candidates: dict[str, str],
) -> AlignmentProposal:
    """Propose which candidate the child version came from.

    *candidates* maps a candidate parent's id to its text.

    **The output is a proposal, and the confidence is not the decision.**
    Even a proposal with a confidence of 1.0 is a proposal: the edge it
    becomes carries no acceptor until a person accepts it, and the
    design's rule is that a similarity score may not silently decide an
    order.

    **When the evidence points two ways, this does not decide.** The
    candidates are returned with their evidence, ``decided`` is False, and
    the reason says which two it could not choose between. **That is the
    design's rule —*"禁止仅靠相似度静默确定版本顺序"* — and a decision made
    here would be a decision made by a score.
    """
    if not candidates:
        return AlignmentProposal(
            child_version_id=child_version_id,
            decided=False,
            reason="there is no candidate to compare the version against",
        )

    child = fingerprint(child_text)
    scored: list[tuple[float, str, tuple[AlignmentEvidence, ...]]] = []
    for parent_id, parent_text in candidates.items():
        evidence = _evidence_for(parent_id, fingerprint(parent_text), child)
        weight = sum(item.weight for item in evidence) / max(len(EVIDENCE_KINDS), 1)
        scored.append((weight, parent_id, evidence))

    # Strongest first, and the id breaks a tie so the order is **stable**:
    # an alignment that reorders on equal evidence would make the same
    # archive answer a question in two ways.
    scored.sort(key=lambda item: (-item[0], item[1]))

    best_weight, best_id, best_evidence = scored[0]
    runner_up_weight, runner_up_id, _ = scored[1] if len(scored) > 1 else (0.0, "", ())

    # **The ambiguity test.** Two candidates within a hair of each other are
    # **not** a decision, and picking the higher one would be a score
    # deciding an order. The margin is deliberately tight: a difference
    # that small is inside the noise of any similarity measure.
    margin = best_weight - runner_up_weight
    ambiguous = margin < 0.05 and len(scored) > 1

    # **"No evidence" means no evidence that *links*, not no signal at
    # all.** A number that moved is a signal, but it carries no weight on
    # its own — it is a difference, not a link — so a candidate whose only
    # signal is a moved number has found nothing that points from one
    # document to the other.
    linking = [item for item in best_evidence if item.weight > 0.0]
    if not linking:
        return AlignmentProposal(
            child_version_id=child_version_id,
            candidates=tuple(item[1] for item in scored),
            evidence=best_evidence,
            decided=False,
            reason=(
                "no signal pointed either way: the candidate shares no heading, "
                "no substantial passage and no number with the version"
            ),
        )

    if ambiguous:
        return AlignmentProposal(
            child_version_id=child_version_id,
            candidates=tuple(item[1] for item in scored),
            evidence=best_evidence,
            confidence=best_weight,
            decided=False,
            reason=(
                f"the evidence did not separate {best_id!r} from "
                f"{runner_up_id!r} (a margin of {margin:.3f}), and a score may "
                f"not silently decide an order. A person chooses."
            ),
            ambiguous_between=(best_id, runner_up_id),
        )

    counter: tuple[AlignmentEvidence, ...] = ()
    if best_evidence:
        names = {item.kind for item in best_evidence}
        missing = [kind for kind in EVIDENCE_KINDS if kind not in names]
        if missing:
            counter = (
                AlignmentEvidence(
                    kind=missing[0],
                    detail=(
                        f"no {missing[0]} signal was found, so the proposal rests "
                        f"on the signals that were found and no more"
                    ),
                    weight=0.0,
                ),
            )

    return AlignmentProposal(
        child_version_id=child_version_id,
        candidates=tuple(item[1] for item in scored),
        evidence=best_evidence,
        counter_evidence=counter,
        confidence=best_weight,
        decided=True,
    )
