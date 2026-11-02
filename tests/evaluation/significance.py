"""The two contrasts, computed, and free to come out not significant.

**The clause this module exists to protect.** The protocol's honesty rule:
**a gain that is not significant is reported as not significant**. The
phase's exit experiment is the one place in the project where the
temptation to round a near-miss up to a win is structural — the gate asks
for a measured capability gain — and so the machinery is built to make the
not-significant verdict a *first-class outcome*: rendered, carrying its
numbers, saying in words what it means. A not-significant result that
renders as a silent zero, or as an exception, or as a row the report skips
is the failure mode this module is shaped against.

**The test.** The per-dimension contrast is paired: for each case, the
treatment arm's settled label against the control arm's, and a case counts
as a win, a loss or a tie. The significance test is the sign test — exact,
two-tailed, computed from ``math.comb`` and nothing else, so the
preparation carries no dependency it did not measure. With fewer wins than
the protocol's smallest honest denominator, or with every case tied, the
verdict is not significant **by rule**, not by the test's arithmetic,
because a sign test over three pairs can come out "significant" at p=0.25
and that word would still mean nothing over three pairs.

**What pairs, and what refuses to.** The two arms are paired by case, and
the pairing refuses rather than repairs: an arm with two items for one
case, a case one arm covers and the other does not, an item that maps to
no case — each is a denominator that would move without anyone seeing it
move, so each is refused, by name.

**How a label becomes a win.** Each dimension names the label that is
*beneficial* on it — ``yes`` for the four dimensions of the form "did it
do the thing", ``no`` for hallucination and mis-citation, where not doing
it is the point. A case is a win when exactly one arm's label is the
beneficial one. **No ordering is claimed between ``no`` and ``unknown``**:
the protocol says ``unknown`` is a label, not a failure, and a rule that
ranked "the evidence does not settle this" above or below "confirmed not
done" would be inventing a measurement the raters did not make. So a case
where neither arm reaches the beneficial label is a tie, and says so.

**And one more sentence the report always carries.** The protocol's §5:
a significant difference in one dimension is not a phase gate. The
renderer puts that sentence on every significant row, because a headline
that carries only the significant dimension is exactly the inflation the
protocol exists to stop.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from .blind_sheet import (
    DIMENSIONS,
    LABEL_NO,
    LABEL_YES,
    ExcludedRating,
    ResolvedRating,
)

#: The label that counts as the good outcome, per dimension. Four
#: dimensions ask "did it do the thing" and ``yes`` is the good outcome;
#: hallucination and mis-citation asks "did it invent" and ``no`` is.
DIMENSION_BENEFICIAL_LABEL: Final[dict[str, str]] = {
    "problem_identification": LABEL_YES,
    "evidence_support": LABEL_YES,
    "advisor_comprehension": LABEL_YES,
    "hallucination_mis_citation": LABEL_NO,
    "abstention": LABEL_YES,
}

#: The smallest denominator a significant verdict may rest on. A sign test
#: over fewer pairs than this can produce a small p from a small sample,
#: and the protocol's whole discipline is that a rate over too few cases
#: does not mean much on its own.
MIN_PAIRS: Final = 10

#: The two-tailed alpha for the sign test.
ALPHA: Final = 0.05

#: How a settled label was reached, for the report's denominator rows.
BASIS_AGREEMENT: Final = "agreement"
BASIS_ARBITRATED: Final = "arbitrated"


@dataclass(frozen=True, slots=True)
class PairedCounts:
    """The paired outcome of one contrast on one dimension."""

    #: Cases where the treatment arm's label was the beneficial one and
    #: the control arm's was not.
    wins: int
    #: Cases where the control arm's label was the beneficial one and the
    #: treatment arm's was not.
    losses: int
    #: Cases where neither arm reached the beneficial label, or both did.
    ties: int

    @property
    def cases(self) -> int:
        """The denominator: every paired case, ties included."""
        return self.wins + self.losses + self.ties


@dataclass(frozen=True, slots=True)
class SignificanceVerdict:
    """One contrast on one dimension, judged, with the judgment's words.

    A verdict always carries its numbers and always carries a reason: the
    not-significant path is a first-class outcome, and a first-class
    outcome explains itself rather than arriving as a zero the reader has
    to interpret.
    """

    #: The contrast, as the protocol names it: ``D vs C`` or ``E vs D``.
    contrast: str
    #: The dimension the contrast was measured on.
    dimension: str
    #: The paired counts.
    counts: PairedCounts
    #: Whether the difference is significant — and when it is not, the
    #: verdict is the report's conclusion, not an absence in it.
    significant: bool
    #: The p-value of the two-tailed sign test, when one was computed.
    #: ``None`` when the verdict fell to a rule before any test ran — a
    #: too-small denominator has no p-value, and inventing one would be
    #: the inflation the protocol forbids.
    p_value: float | None
    #: Why the verdict is what it is, in words a reader can check the
    #: numbers against.
    reason: str

    @property
    def difference(self) -> float:
        """The net win difference per paired case, ties in the denominator."""
        return (self.counts.wins - self.counts.losses) / self.counts.cases


def _binomial_two_tail(wins: int, losses: int) -> float:
    """The two-tailed sign test p-value, exactly, from the binomial."""
    n = wins + losses
    k = max(wins, losses)
    tail: float = sum(math.comb(n, i) for i in range(k, n + 1)) / (2**n)
    return min(1.0, 2.0 * tail)


def pair_by_case(
    resolved: Sequence[ResolvedRating],
    item_arms: Mapping[str, str],
    item_cases: Mapping[str, str],
    dimension: str,
    treatment: str,
    control: str,
) -> PairedCounts:
    """Pair the two arms' settled labels by case, refusing a broken pairing.

    Every resolved rating for the dimension is placed by its item's arm
    and case. The refusals, each by name:

    * an item with no arm in the unblinding map — an item the contrast
      cannot place is refused, not dropped;
    * an arm with two settled labels for one case — a case that an arm
      answered twice has no single label to pair against;
    * a case one arm covers and the other does not — the denominator is
      the paired cases, and a case counted on one side only would move it
      without saying so.
    """
    labels: dict[tuple[str, str], str] = {}
    for rating in resolved:
        if rating.dimension != dimension:
            continue
        arm = item_arms.get(rating.item_id)
        if arm is None:
            msg = (
                f"item {rating.item_id} carries no arm in the unblinding map, "
                f"so the contrast {treatment} vs {control} cannot place it"
            )
            raise ValueError(msg)
        case_id = item_cases.get(rating.item_id)
        if case_id is None:
            msg = f"item {rating.item_id} maps to no case, so it cannot be paired"
            raise ValueError(msg)
        key = (arm, case_id)
        if key in labels and labels[key] != rating.label:
            msg = (
                f"arm {arm} has two settled labels for case {case_id} on "
                f"{dimension} ({labels[key]!r} and {rating.label!r}); a case "
                "with no single label cannot be paired"
            )
            raise ValueError(msg)
        labels[key] = rating.label
    treatment_cases = {case_id for (arm, case_id), _ in labels.items() if arm == treatment}
    control_cases = {case_id for (arm, case_id), _ in labels.items() if arm == control}
    missing = sorted(treatment_cases ^ control_cases)
    if missing:
        msg = (
            f"the contrast {treatment} vs {control} is unpaired on "
            f"{len(missing)} case(s): {', '.join(missing)}; the denominator is "
            "the paired cases, and these have no pair"
        )
        raise ValueError(msg)
    beneficial = DIMENSION_BENEFICIAL_LABEL[dimension]
    wins = losses = ties = 0
    for case_id in sorted(treatment_cases):
        treat_label = labels[(treatment, case_id)]
        control_label = labels[(control, case_id)]
        treat_good = treat_label == beneficial
        control_good = control_label == beneficial
        if treat_good == control_good:
            ties += 1
        elif treat_good:
            wins += 1
        else:
            losses += 1
    return PairedCounts(wins=wins, losses=losses, ties=ties)


def assess_significance(contrast: str, dimension: str, counts: PairedCounts) -> SignificanceVerdict:
    """Judge one contrast on one dimension, and never round a near-miss up.

    The verdict paths, in the order they are met:

    * fewer paired cases than :data:`MIN_PAIRS` — not significant, by
      rule, before any test runs; a sign test over a handful of pairs
      produces p-values that mean nothing, so none is computed;
    * every case tied — not significant, with the reason saying so; the
      difference is zero and the reason explains that the zero is "no
      evidence either way", not a measured absence of effect;
    * the two-tailed sign test at or above :data:`ALPHA` — not
      significant, with the p-value and the numbers in the reason;
    * below alpha — significant, and the reason still carries the
      numbers, because a significant row without its denominator is the
      number-without-a-meaning the protocol names.
    """
    if counts.cases < MIN_PAIRS:
        return SignificanceVerdict(
            contrast=contrast,
            dimension=dimension,
            counts=counts,
            significant=False,
            p_value=None,
            reason=(
                f"not significant by rule: {counts.cases} paired cases is below "
                f"the smallest denominator ({MIN_PAIRS}) a verdict may rest on, "
                "so no test was computed"
            ),
        )
    if counts.wins + counts.losses == 0:
        return SignificanceVerdict(
            contrast=contrast,
            dimension=dimension,
            counts=counts,
            significant=False,
            p_value=None,
            reason=(
                f"not significant: every one of {counts.cases} paired cases "
                "tied, so there is no evidence either way"
            ),
        )
    p_value = _binomial_two_tail(counts.wins, counts.losses)
    if p_value >= ALPHA:
        return SignificanceVerdict(
            contrast=contrast,
            dimension=dimension,
            counts=counts,
            significant=False,
            p_value=p_value,
            reason=(
                f"not significant: the sign test over {counts.cases} paired "
                f"cases ({counts.wins} wins, {counts.losses} losses, "
                f"{counts.ties} ties) gives p={p_value:.4f}, at or above "
                f"alpha={ALPHA}"
            ),
        )
    return SignificanceVerdict(
        contrast=contrast,
        dimension=dimension,
        counts=counts,
        significant=True,
        p_value=p_value,
        reason=(
            f"significant: the sign test over {counts.cases} paired cases "
            f"({counts.wins} wins, {counts.losses} losses, {counts.ties} ties) "
            f"gives p={p_value:.4f}, below alpha={ALPHA}"
        ),
    )


def render_verdict(verdict: SignificanceVerdict) -> str:
    """Render one verdict as the report will print it.

    The not-significant path renders as words, not as a zero: the
    ``NOT SIGNIFICANT`` verdict, the contrast and dimension it belongs to,
    the numbers, and the protocol's own sentence about what such a result
    is. A witness holds that this path renders — an exception here, or a
    silently skipped row, would be the fudge the protocol's honesty clause
    names.
    """
    head = (
        f"{verdict.contrast} on {verdict.dimension}: "
        f"{verdict.counts.cases} paired cases, "
        f"{verdict.counts.wins} wins, {verdict.counts.losses} losses, "
        f"{verdict.counts.ties} ties, difference {verdict.difference:+.3f}"
    )
    if verdict.significant:
        return (
            f"SIGNIFICANT — {head}; {verdict.reason}. "
            "A significant difference in one dimension is not a phase gate."
        )
    return (
        f"NOT SIGNIFICANT — {head}; {verdict.reason}. "
        "A gain that is not significant is reported as not significant."
    )


@dataclass(frozen=True, slots=True)
class DimensionRow:
    """One dimension's verdict, with the resolution's own denominator."""

    #: The dimension the row reports.
    dimension: str
    #: The verdict on the contrast for this dimension.
    verdict: SignificanceVerdict
    #: How many settled labels the two raters agreed on, for this dimension.
    agreed: int
    #: How many the arbiter settled.
    arbitrated: int
    #: How many were excluded — disagreed with no arbiter over them. The
    #: number is in the report because the agreement rate without it is a
    #: number without a meaning.
    excluded: int


@dataclass(frozen=True, slots=True)
class ContrastReport:
    """One contrast, across the five dimensions, each row carrying its own denominator."""

    #: The contrast, as the protocol names it.
    contrast: str
    #: The rows, in the protocol's dimension order.
    rows: tuple[DimensionRow, ...]


def build_report(
    contrast: str,
    resolved: Sequence[ResolvedRating],
    excluded: Sequence[ExcludedRating],
    item_arms: Mapping[str, str],
    item_cases: Mapping[str, str],
    treatment: str,
    control: str,
) -> ContrastReport:
    """Build one contrast's report: every dimension, every denominator.

    Each row pairs the two arms on its dimension and judges the pairing.
    The resolution's own denominators — agreed, arbitrated, excluded —
    ride on the row, so a reader can see how much of each dimension's
    verdict rests on the raters' agreement and how much on the arbiter,
    and how many cases dropped off the resolution without a settled label.
    """
    rows: list[DimensionRow] = []
    for dimension in DIMENSIONS:
        agreed = sum(
            1
            for rating in resolved
            if rating.dimension == dimension and rating.basis == BASIS_AGREEMENT
        )
        arbitrated = sum(
            1
            for rating in resolved
            if rating.dimension == dimension and rating.basis == BASIS_ARBITRATED
        )
        excluded_count = sum(1 for rating in excluded if rating.dimension == dimension)
        counts = pair_by_case(resolved, item_arms, item_cases, dimension, treatment, control)
        verdict = assess_significance(contrast, dimension, counts)
        rows.append(
            DimensionRow(
                dimension=dimension,
                verdict=verdict,
                agreed=agreed,
                arbitrated=arbitrated,
                excluded=excluded_count,
            )
        )
    return ContrastReport(contrast=contrast, rows=tuple(rows))


def render_report(report: ContrastReport) -> str:
    """Render a whole contrast's report, every row, significant or not."""
    lines = [f"Contrast {report.contrast}:"]
    lines.extend(f"  {render_verdict(row.verdict)}" for row in report.rows)
    return "\n".join(lines)
