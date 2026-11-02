"""The by-paper split, and the leak check that is a test, not a promise.

**The rule the protocol is built on.** The phase's exit experiment runs on
papers the system has never seen, and the protocol's hard rule is that the
unseen-paper split is **by paper**: every version of a paper, every comment
on it, every rule distilled from it and every assessment of it sit in **one**
partition. A test case is never a version and never an event.

**Why a checker and not a promise.** The protocol says it plainly — "the
leak check is a test, not a promise". A promise is a sentence in a plan
that a merge can outlive; a checker over the split's own shape is a thing
that goes red. So this module takes the split as data — the assignments,
the corpus entries, the cases' retrievable corpora — and reports every leak
it can name, each leak carrying the shape that produced it and the entry
that committed it.

**What the check runs over.** The retrievable corpus of each case, not the
database: the retrievable corpus is what the system can reach, and a
database that is clean while an index hands a case the paper's final
version is a leak the database never saw. So the checker's second half is
per-case: a case that asks about a paper's first draft must not be able to
reach a later version of that paper, a case must target a paper on its own
side, and a rule in reach of an evaluation case must not have been
distilled from an evaluated paper.

**And against the arms themselves.** The protocol adds one more check: an
arm that differs from another **only** because it can see more of the same
paper's history is a leak. The shape that carries that is the declared
version cap — per paper, the latest version an arm's configuration lets it
reach — and every version entry in the arm's actual corpus must sit at or
under it. An entry beyond the cap is the arm seeing history its letter
does not name.

**Every leak shape here is one a witness catches.** A checker that has
never caught a leak is not a checker; the witnesses are the caught leaks.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

#: The two sides of the split, in the protocol's words: the papers the
#: system may learn from, and the papers it is evaluated on.
DEVELOPMENT: Final = "development"
EVALUATION: Final = "evaluation"
SIDES: Final[tuple[str, ...]] = (DEVELOPMENT, EVALUATION)

#: The kinds of corpus entry the split holds. The protocol's §2 names the
#: material: every version, every comment, every rule distilled from it,
#: every assessment of it.
KIND_VERSION: Final = "version"
KIND_COMMENT: Final = "comment"
KIND_RULE: Final = "rule"
KIND_ASSESSMENT: Final = "assessment"


@dataclass(frozen=True, slots=True)
class CorpusEntry:
    """One piece of material the split holds, with the paper it belongs to.

    The unit is the paper, so every entry carries its ``paper_id`` and the
    side it is filed on. A version entry carries its ``version_id``; a
    rule carries the paper it was distilled from — which is the paper the
    rule's memory is built on, and the paper the leak check holds it to.
    """

    #: The paper the material belongs to. Every version, comment, rule and
    #: assessment of one paper carries the same id.
    paper_id: str
    #: One of the four kinds above.
    kind: str
    #: Which side of the split this entry is filed on.
    side: str
    #: The version this entry is a version of, for ``version`` entries.
    version_id: str = ""


@dataclass(frozen=True, slots=True)
class Leak:
    """One leak, named by the shape that produced it."""

    #: The leak shape, one of the names the checker's docstring lists.
    shape: str
    #: What committed the leak, naming the paper, the entry or the case.
    detail: str


@dataclass(frozen=True, slots=True)
class LeakReport:
    """Every leak one check found, and whether the split is clean."""

    #: The leaks, in the order the shapes are checked.
    leaks: tuple[Leak, ...]

    @property
    def clean(self) -> bool:
        """Whether the check found nothing."""
        return not self.leaks


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    """One case: the paper and version it asks about, and what it can reach.

    The case's ``target_paper_id`` and ``target_version_id`` name the
    question — "what should the first draft of this paper say". The
    ``retrievable`` tuple is what the system can reach while answering:
    the retrieval index's contents, the distilled rules in scope, the
    case's own history. The check runs over exactly this, because this is
    what the system can reach.
    """

    #: The paper the case asks about.
    target_paper_id: str
    #: The version the case asks about — the first draft, usually.
    target_version_id: str
    #: The side of the split this case runs on, as the run declares it. A
    #: carried side can drift from the assignments, which is exactly why
    #: the check compares the two instead of trusting either.
    side: str
    #: Everything the case can reach while answering.
    retrievable: tuple[CorpusEntry, ...]


def _version_number(version_id: str) -> int:
    """The integer in a version id, for ordering versions of one paper.

    Versions are ``v1``, ``v2``, …; a version id that is not that is a
    split the checker refuses to guess about.
    """
    stripped = version_id.strip().lower()
    if not stripped.startswith("v") or not stripped[1:].isdigit():
        msg = f"version id {version_id!r} is not v<number>"
        raise ValueError(msg)
    return int(stripped[1:])


def check_split(assignments: Mapping[str, str], entries: Sequence[CorpusEntry]) -> LeakReport:
    """Check the split's own coherence, over the whole corpus.

    Three leak shapes live here:

    * ``paper-on-both-sides`` — one paper whose material sits on both
      sides: two entries of one paper whose sides disagree. The unit is
      the paper; material split across the two partitions is two units
      and neither. (The assignments mapping cannot promise two sides for
      one paper, so the check runs over the material itself.)
    * ``entry-unassigned`` — an entry whose paper has no side at all. The
      split must cover every entry it holds; an unassigned entry is
      material whose side nobody promised.
    * ``entry-on-wrong-side`` — an entry filed on a side its paper is not
      assigned to. This is the shape that catches "a version of a split
      paper on the wrong side" and "a rule memory built on a paper the
      evaluation arm reads" alike: the rule's kind does not matter, the
      side it is filed on does.
    * ``rule-built-on-evaluated-paper`` — a rule whose source paper is on
      the evaluation side. Rules are distilled from the development side;
      a rule built on a paper the evaluation arm reads is the leak the
      protocol names, wherever it is filed.
    """
    leaks: list[Leak] = []
    for paper_id, side in sorted(assignments.items()):
        if side not in SIDES:
            leaks.append(
                Leak(
                    shape="side-unrecognized",
                    detail=f"paper {paper_id} is assigned to {side!r}, "
                    f"which is not one of {', '.join(SIDES)}",
                )
            )
    seen: dict[str, set[str]] = {}
    for paper_id, side in assignments.items():
        seen.setdefault(paper_id, set()).add(side)
    for paper_id, sides in sorted(seen.items()):
        if len(sides) > 1:
            leaks.append(
                Leak(
                    shape="paper-on-both-sides",
                    detail=f"paper {paper_id} is assigned to both "
                    f"{', '.join(sorted(sides))}; the unit is the paper",
                )
            )
    # The promise is one side per paper, so a paper cannot be assigned to
    # both through this mapping; the material can still sit on both sides,
    # and that is what this check is for: two entries of one paper whose
    # sides disagree are the paper split in two, whatever was promised.
    material_sides: dict[str, set[str]] = {}
    for entry in entries:
        material_sides.setdefault(entry.paper_id, set()).add(entry.side)
    for paper_id, sides in sorted(material_sides.items()):
        if len(sides) > 1:
            leaks.append(
                Leak(
                    shape="paper-on-both-sides",
                    detail=f"paper {paper_id} has material filed on both "
                    f"{', '.join(sorted(sides))}; the unit is the paper, "
                    "and these entries split it in two",
                )
            )
    for entry in entries:
        assigned = assignments.get(entry.paper_id)
        if assigned is None:
            leaks.append(
                Leak(
                    shape="entry-unassigned",
                    detail=f"{entry.kind} of paper {entry.paper_id} has no side in the split",
                )
            )
            continue
        if entry.side != assigned:
            leaks.append(
                Leak(
                    shape="entry-on-wrong-side",
                    detail=f"{entry.kind} of paper {entry.paper_id} is filed on "
                    f"{entry.side} but the paper is assigned to {assigned}",
                )
            )
        if entry.kind == KIND_RULE and assigned == EVALUATION:
            leaks.append(
                Leak(
                    shape="rule-built-on-evaluated-paper",
                    detail=f"a rule is distilled from paper {entry.paper_id}, "
                    "which is on the evaluation side",
                )
            )
    return LeakReport(leaks=tuple(leaks))


def check_case(case: EvaluationCase, assignments: Mapping[str, str]) -> LeakReport:
    """Check one case's retrievable corpus for what the case must not reach.

    Three leak shapes live here:

    * ``unseen-version-reachable`` — the corpus holds a version of the
      target paper later than the one the case asks about. The final
      version may not be reachable from the case that asks about the first
      draft, not through the index, not through a rule, not through the
      case's own history.
    * ``case-targets-wrong-side`` — the case asks about a paper assigned to
      the other side. An evaluation case over a development paper is the
      split not holding; a development case over an evaluation paper is
      the split leaking before the run starts.
    * ``rule-from-evaluation-reachable`` — the corpus holds a rule distilled
      from an evaluation paper, in reach of any case. A rule memory built
      on a paper the evaluation arm reads is a leak, and reachability is
      what makes it live.
    """
    leaks: list[Leak] = []
    if case.side not in SIDES:
        leaks.append(
            Leak(
                shape="side-unrecognized",
                detail=f"the case runs on {case.side!r}, which is not one of {', '.join(SIDES)}",
            )
        )
    assigned = assignments.get(case.target_paper_id)
    if assigned is None:
        leaks.append(
            Leak(
                shape="entry-unassigned",
                detail=f"the case targets paper {case.target_paper_id}, which has "
                "no side in the split",
            )
        )
    elif assigned != DEVELOPMENT and assigned != EVALUATION:
        leaks.append(
            Leak(
                shape="side-unrecognized",
                detail=f"the case targets paper {case.target_paper_id}, assigned to {assigned!r}",
            )
        )
    elif assigned != case.side:
        leaks.append(
            Leak(
                shape="case-targets-wrong-side",
                detail=f"the case targets paper {case.target_paper_id}, assigned "
                f"to {assigned}, but the case runs on {case.side}",
            )
        )
    target_number = _version_number(case.target_version_id)
    for entry in case.retrievable:
        if (
            entry.kind == KIND_VERSION
            and entry.paper_id == case.target_paper_id
            and _version_number(entry.version_id) > target_number
        ):
            leaks.append(
                Leak(
                    shape="unseen-version-reachable",
                    detail=f"version {entry.version_id} of paper "
                    f"{case.target_paper_id} is reachable from a case that asks "
                    f"about {case.target_version_id}",
                )
            )
        if entry.kind == KIND_RULE and assignments.get(entry.paper_id) == EVALUATION:
            leaks.append(
                Leak(
                    shape="rule-from-evaluation-reachable",
                    detail=f"a rule distilled from paper {entry.paper_id} is "
                    "reachable from this case",
                )
            )
    return LeakReport(leaks=tuple(leaks))


def check_arm_exposure(declared_caps: Mapping[str, str], case: EvaluationCase) -> LeakReport:
    """Check an arm's actual corpus against the versions its letter names.

    The protocol's arm-level check: an arm that differs from another only
    because it can see more of the same paper's history is a leak. The
    declared cap is, per paper, the latest version the arm's configuration
    lets it reach; a version entry beyond the cap is the arm seeing
    history its letter does not name — the leak, whatever the index that
    handed it over calls itself.

    One leak shape lives here: ``version-beyond-declared-cap``.
    """
    leaks: list[Leak] = []
    for entry in case.retrievable:
        if entry.kind != KIND_VERSION:
            continue
        cap = declared_caps.get(entry.paper_id)
        if cap is None:
            leaks.append(
                Leak(
                    shape="version-beyond-declared-cap",
                    detail=f"version {entry.version_id} of paper {entry.paper_id} "
                    "is reachable, but the arm declares no cap for that paper",
                )
            )
        elif _version_number(entry.version_id) > _version_number(cap):
            leaks.append(
                Leak(
                    shape="version-beyond-declared-cap",
                    detail=f"version {entry.version_id} of paper {entry.paper_id} "
                    f"is reachable, but the arm's cap is {cap}",
                )
            )
    return LeakReport(leaks=tuple(leaks))
