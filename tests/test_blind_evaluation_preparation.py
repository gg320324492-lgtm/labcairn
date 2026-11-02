"""The blind evaluation's mechanical preparation, watched.

**What this file watches.** ``tests/evaluation`` gained four modules for
LC-P2-14's preparation — the five arms' run configuration, the by-paper
split's leak check, the blind score sheet, and the aggregation that can
say not significant. Each is a mechanism, and a mechanism nobody watches
can be neutered: a check deleted here leaves the tree green and the run
unprotected. So every refusal and every leak shape these modules name has
a witness, and every witness is mutated against (the mutation table is in
``docs/acceptance/LC-P2-14-preparation.md``).

**The witnesses are the caught leaks.** A leak checker that has never
caught a leak is not a checker; the split-check witnesses below feed it
every leak shape the protocol names and watch each one come back named.
"""

from __future__ import annotations

from typing import Any, cast

import pytest
from evaluation.arms import (
    ARM_IDS,
    EXPECTED_INPUTS,
    ArmConfiguration,
    arrangement_variants,
    assess_arrangement,
    assess_configuration,
)
from evaluation.blind_sheet import (
    ARM_KEY_VARIANTS,
    DIMENSIONS,
    BlindSheet,
    ExcludedRating,
    ResolvedRating,
    load_blind_sheet,
    resolve_pair,
    unblind,
)
from evaluation.significance import (
    PairedCounts,
    assess_significance,
    build_report,
    pair_by_case,
    render_report,
    render_verdict,
)
from evaluation.split_check import (
    DEVELOPMENT,
    EVALUATION,
    KIND_RULE,
    KIND_VERSION,
    CorpusEntry,
    EvaluationCase,
    check_arm_exposure,
    check_case,
    check_split,
)

pytestmark = pytest.mark.unit

#: One model and one budget, shared by every arm the protocol holds fixed.
MODEL: str = "claude-opus-5-5, params fixed"
BUDGET: str = "comparable budget, declared"


def _arm(arm_id: str, inputs: frozenset[str] | None = None) -> ArmConfiguration:
    """One arm of a configuration that is admissible by default.

    The inputs default to the protocol's own table for the letter, so a
    witness mutates exactly one property and the checker answers for it.
    """
    return ArmConfiguration(
        arm_id=arm_id,
        model=MODEL,
        budget=BUDGET,
        inputs=frozenset(inputs) if inputs is not None else EXPECTED_INPUTS[arm_id],
    )


def _clean_configuration() -> list[ArmConfiguration]:
    """The protocol's five arms, as the protocol declares them."""
    return [_arm(letter) for letter in ARM_IDS]


def _ratings_document(
    labels: dict[str, str] | None = None,
) -> dict[str, str]:
    """A full ratings mapping, ``unknown``-free unless asked."""
    base = dict.fromkeys(DIMENSIONS, "yes")
    if labels:
        base.update(labels)
    return base


def _blind_document(
    rater: str, labels_per_item: dict[str, dict[str, str]] | None = None
) -> dict[str, object]:
    """A blind sheet document over the preparation's ten items."""
    labels_per_item = labels_per_item or {}
    return {
        "sheet_id": f"sheet-{rater}",
        "rater": rater,
        "items": [
            {
                "item_id": f"it-{index:02d}",
                "ratings": _ratings_document(labels_per_item.get(f"it-{index:02d}")),
            }
            for index in range(1, 11)
        ],
    }


#: The ten items the synthetic run rates, five per arm of the D vs C contrast.
ITEM_IDS: list[str] = [f"it-{index:02d}" for index in range(1, 11)]

#: The unblinding map for the D vs C contrast: C's items first, then D's.
ITEM_ARMS: dict[str, str] = {
    **{f"it-{index:02d}": "C" for index in range(1, 6)},
    **{f"it-{index:02d}": "D" for index in range(6, 11)},
}

#: Each case is answered once per arm: C's items and D's items pair up on
#: the same five cases, because the contrast's denominator is the paired
#: cases and a case with no pair is refused, not dropped.
ITEM_CASES: dict[str, str] = {
    **{f"it-{index:02d}": f"case-{index:02d}" for index in range(1, 6)},
    **{f"it-{index + 5:02d}": f"case-{index:02d}" for index in range(1, 6)},
}


# -- the five arms' run configuration ---------------------------------------


class TestArmsConfiguration:
    """The configuration check refuses, by name, what the protocol forbids."""

    def test_the_protocols_own_five_arms_are_admissible(self) -> None:
        outcome = assess_configuration(_clean_configuration())
        assert outcome.admissible, outcome.violations

    def test_an_arm_running_a_different_model_is_refused_by_name(self) -> None:
        arms = _clean_configuration()
        arms[4] = ArmConfiguration(
            arm_id="E",
            model="another model",
            budget=BUDGET,
            inputs=arms[4].inputs,
        )
        outcome = assess_configuration(arms)
        assert not outcome.admissible
        assert any("E" in violation and "model" in violation for violation in outcome.violations)

    def test_an_arm_without_a_budget_is_refused_by_name(self) -> None:
        arms = _clean_configuration()
        arms[1] = ArmConfiguration(arm_id="B", model=MODEL, budget="", inputs=arms[1].inputs)
        outcome = assess_configuration(arms)
        assert not outcome.admissible
        assert any("B" in violation and "budget" in violation for violation in outcome.violations)

    def test_a_missing_letter_is_refused_by_name(self) -> None:
        arms = [arm for arm in _clean_configuration() if arm.arm_id != "C"]
        outcome = assess_configuration(arms)
        assert not outcome.admissible
        assert any("C" in violation and "missing" in violation for violation in outcome.violations)

    def test_a_letter_outside_the_protocol_is_refused_by_name(self) -> None:
        arms = [*_clean_configuration(), _arm("F", frozenset({"draft"}))]
        outcome = assess_configuration(arms)
        assert not outcome.admissible
        assert any("'F'" in violation for violation in outcome.violations)

    def test_a_broken_additive_chain_is_refused_by_name(self) -> None:
        arms = _clean_configuration()
        arms[4] = ArmConfiguration(
            arm_id="E",
            model=MODEL,
            budget=BUDGET,
            inputs=arms[3].inputs - {"advisor_comments"},
        )
        outcome = assess_configuration(arms)
        assert not outcome.admissible
        assert any(
            "E is missing evidence arm D declares" in violation for violation in outcome.violations
        )

    def test_a_letter_that_sees_what_its_predecessor_sees_measures_nothing(self) -> None:
        arms = _clean_configuration()
        arms[2] = ArmConfiguration(arm_id="C", model=MODEL, budget=BUDGET, inputs=arms[1].inputs)
        outcome = assess_configuration(arms)
        assert not outcome.admissible
        assert any("C measures nothing" in violation for violation in outcome.violations)

    def test_an_arm_declaring_an_input_the_protocol_does_not_name_is_refused(
        self,
    ) -> None:
        # The refusal lives in from_document, which is what a run's
        # configuration file goes through.
        raw = {
            "arm_id": "A",
            "model": MODEL,
            "budget": BUDGET,
            "inputs": ["draft", "the_future"],
        }
        with pytest.raises(ValueError, match="does not name"):
            ArmConfiguration.from_document(raw)

    def test_a_configuration_document_without_a_budget_is_refused(self) -> None:
        with pytest.raises(ValueError, match="missing budget"):
            ArmConfiguration.from_document({"arm_id": "A", "model": MODEL, "inputs": ["draft"]})

    def test_an_arm_missing_its_own_lettered_inputs_is_refused_by_name(self) -> None:
        # Arm A has no predecessor, so the additive chain cannot catch it
        # shortening its own inputs: only the letter's own table does.
        arms = _clean_configuration()
        arms[0] = ArmConfiguration(
            arm_id="A",
            model=MODEL,
            budget=BUDGET,
            inputs=frozenset({"literature"}),
        )
        outcome = assess_configuration(arms)
        assert not outcome.admissible
        assert any(
            "A is missing the inputs the protocol's letter names: draft" in violation
            for violation in outcome.violations
        )

    def test_the_contrasts_exist_in_an_admissible_configuration(self) -> None:
        # The clean configuration already carries D vs C and E vs D; a
        # witness mutation inside the checker's contrast loop must red the
        # missing-contrast refusal below.
        arms = _clean_configuration()
        arms[3] = ArmConfiguration(
            arm_id="D", model=MODEL, budget=BUDGET, inputs=frozenset({"draft"})
        )
        outcome = assess_configuration(arms)
        assert not outcome.admissible
        assert any(
            "D vs C" in violation or "E vs D" in violation for violation in outcome.violations
        )


class TestArrangementPair:
    """The arrangement comparison measures the roles and nothing else."""

    def test_the_pair_over_b_differs_only_in_roles(self) -> None:
        alone, critiqued = arrangement_variants(_arm("B"))
        outcome = assess_arrangement(alone, critiqued)
        assert outcome.admissible, outcome.violations
        assert alone.roles != critiqued.roles

    def test_a_pair_on_different_models_measures_the_models(self) -> None:
        alone, critiqued = arrangement_variants(_arm("B"))
        other = ArmConfiguration(
            arm_id="B",
            model="another model",
            budget=BUDGET,
            inputs=critiqued.inputs,
            roles=critiqued.roles,
        )
        outcome = assess_arrangement(alone, other)
        assert not outcome.admissible
        assert any("model" in violation for violation in outcome.violations)

    def test_a_pair_on_different_evidence_measures_the_evidence(self) -> None:
        alone, critiqued = arrangement_variants(_arm("B"))
        other = ArmConfiguration(
            arm_id="B",
            model=MODEL,
            budget=BUDGET,
            inputs=alone.inputs | {"version_differences"},
            roles=critiqued.roles,
        )
        outcome = assess_arrangement(alone, other)
        assert not outcome.admissible
        assert any("evidence" in violation for violation in outcome.violations)

    def test_a_pair_on_different_budgets_is_refused(self) -> None:
        alone, critiqued = arrangement_variants(_arm("B"))
        other = ArmConfiguration(
            arm_id="B",
            model=MODEL,
            budget="twice the budget",
            inputs=critiqued.inputs,
            roles=critiqued.roles,
        )
        outcome = assess_arrangement(alone, other)
        assert not outcome.admissible
        assert any("budget" in violation for violation in outcome.violations)

    def test_a_pair_running_the_same_roles_measures_no_arrangement(self) -> None:
        arm = _arm("B")
        outcome = assess_arrangement(arm, arm)
        assert not outcome.admissible
        assert any("same roles" in violation for violation in outcome.violations)


# -- the leak check ----------------------------------------------------------


class TestSplitCheck:
    """The split checker accepts a clean split and names every leak shape."""

    def _assignments(self) -> dict[str, str]:
        return {"paper-dev-1": DEVELOPMENT, "paper-eval-1": EVALUATION}

    def _clean_entries(self) -> list[CorpusEntry]:
        return [
            CorpusEntry("paper-dev-1", KIND_VERSION, DEVELOPMENT, "v1"),
            CorpusEntry("paper-dev-1", KIND_VERSION, DEVELOPMENT, "v2"),
            CorpusEntry("paper-eval-1", KIND_VERSION, EVALUATION, "v1"),
        ]

    def test_a_clean_split_is_clean(self) -> None:
        report = check_split(self._assignments(), self._clean_entries())
        assert report.clean, [leak.shape for leak in report.leaks]

    def test_a_paper_on_both_sides_is_named(self) -> None:
        # The assignments cannot promise two sides for one paper, so the
        # shape lives in the material: a second entry of the evaluation
        # paper, filed on the development side, splits the paper in two.
        entries = [
            *self._clean_entries(),
            CorpusEntry("paper-eval-1", KIND_VERSION, DEVELOPMENT, "v1"),
        ]
        report = check_split(self._assignments(), entries)
        shapes = [leak.shape for leak in report.leaks]
        assert "paper-on-both-sides" in shapes

    def test_an_entry_whose_paper_has_no_side_is_named(self) -> None:
        entries = [
            *self._clean_entries(),
            CorpusEntry("paper-ghost", KIND_VERSION, DEVELOPMENT, "v1"),
        ]
        report = check_split(self._assignments(), entries)
        shapes = [leak.shape for leak in report.leaks]
        assert "entry-unassigned" in shapes

    def test_a_version_of_a_split_paper_on_the_wrong_side_is_named(self) -> None:
        entries = [
            entry
            if entry.paper_id != "paper-eval-1"
            else CorpusEntry(entry.paper_id, entry.kind, DEVELOPMENT, entry.version_id)
            for entry in self._clean_entries()
        ]
        report = check_split(self._assignments(), entries)
        shapes = [leak.shape for leak in report.leaks]
        assert "entry-on-wrong-side" in shapes

    def test_a_rule_built_on_an_evaluated_paper_is_named(self) -> None:
        entries = [
            CorpusEntry("paper-eval-1", KIND_RULE, EVALUATION, ""),
        ]
        report = check_split(self._assignments(), entries)
        shapes = [leak.shape for leak in report.leaks]
        assert "rule-built-on-evaluated-paper" in shapes

    def test_a_side_the_checker_does_not_know_is_named(self) -> None:
        assignments = {**self._assignments(), "paper-dev-1": "training"}
        report = check_split(assignments, self._clean_entries())
        shapes = [leak.shape for leak in report.leaks]
        assert "side-unrecognized" in shapes

    def _clean_case(self) -> EvaluationCase:
        return EvaluationCase(
            target_paper_id="paper-eval-1",
            target_version_id="v1",
            side=EVALUATION,
            retrievable=(CorpusEntry("paper-eval-1", KIND_VERSION, EVALUATION, "v1"),),
        )

    def test_a_clean_case_is_clean(self) -> None:
        report = check_case(self._clean_case(), self._assignments())
        assert report.clean, [leak.shape for leak in report.leaks]

    def test_a_later_version_reachable_from_a_first_draft_case_is_named(self) -> None:
        case = EvaluationCase(
            target_paper_id="paper-eval-1",
            target_version_id="v1",
            side=EVALUATION,
            retrievable=(
                CorpusEntry("paper-eval-1", KIND_VERSION, EVALUATION, "v1"),
                CorpusEntry("paper-eval-1", KIND_VERSION, EVALUATION, "v2"),
            ),
        )
        report = check_case(case, self._assignments())
        shapes = [leak.shape for leak in report.leaks]
        assert "unseen-version-reachable" in shapes

    def test_a_case_targeting_the_other_side_is_named(self) -> None:
        case = EvaluationCase(
            target_paper_id="paper-dev-1",
            target_version_id="v1",
            side=EVALUATION,
            retrievable=(CorpusEntry("paper-dev-1", KIND_VERSION, DEVELOPMENT, "v1"),),
        )
        report = check_case(case, self._assignments())
        shapes = [leak.shape for leak in report.leaks]
        assert "case-targets-wrong-side" in shapes

    def test_a_case_whose_target_paper_has_no_side_is_named(self) -> None:
        # check_case's own refusal, separate from check_split's: a case
        # whose target paper has no side in the split cannot run at all.
        case = EvaluationCase(
            target_paper_id="paper-ghost",
            target_version_id="v1",
            side=EVALUATION,
            retrievable=(),
        )
        report = check_case(case, self._assignments())
        shapes = [leak.shape for leak in report.leaks]
        assert "entry-unassigned" in shapes
        assert any("case targets paper" in leak.detail for leak in report.leaks)

    def test_a_rule_memory_built_on_an_evaluated_paper_in_reach_is_named(self) -> None:
        case = EvaluationCase(
            target_paper_id="paper-eval-1",
            target_version_id="v1",
            side=EVALUATION,
            retrievable=(
                CorpusEntry("paper-eval-1", KIND_VERSION, EVALUATION, "v1"),
                CorpusEntry("paper-eval-1", KIND_RULE, EVALUATION, ""),
            ),
        )
        report = check_case(case, self._assignments())
        shapes = [leak.shape for leak in report.leaks]
        assert "rule-from-evaluation-reachable" in shapes

    def test_an_arm_seeing_history_beyond_its_declared_cap_is_named(self) -> None:
        case = EvaluationCase(
            target_paper_id="paper-eval-1",
            target_version_id="v1",
            side=EVALUATION,
            retrievable=(
                CorpusEntry("paper-eval-1", KIND_VERSION, EVALUATION, "v1"),
                CorpusEntry("paper-eval-1", KIND_VERSION, EVALUATION, "v2"),
            ),
        )
        report = check_arm_exposure({"paper-eval-1": "v1"}, case)
        shapes = [leak.shape for leak in report.leaks]
        assert "version-beyond-declared-cap" in shapes

    def test_a_version_under_the_cap_is_not_a_leak(self) -> None:
        case = EvaluationCase(
            target_paper_id="paper-eval-1",
            target_version_id="v1",
            side=EVALUATION,
            retrievable=(CorpusEntry("paper-eval-1", KIND_VERSION, EVALUATION, "v1"),),
        )
        report = check_arm_exposure({"paper-eval-1": "v1"}, case)
        assert report.clean, [leak.shape for leak in report.leaks]

    def test_a_reachable_version_with_no_declared_cap_is_named(self) -> None:
        case = self._clean_case()
        report = check_arm_exposure({}, case)
        shapes = [leak.shape for leak in report.leaks]
        assert "version-beyond-declared-cap" in shapes

    def test_a_version_id_that_is_not_v_number_is_refused(self) -> None:
        case = EvaluationCase(
            target_paper_id="paper-eval-1",
            target_version_id="draft-final",
            side=EVALUATION,
            retrievable=(),
        )
        with pytest.raises(ValueError, match="not v<number>"):
            check_case(case, self._assignments())


# -- the blind score sheet ---------------------------------------------------


class TestBlindSheetLoading:
    """The loader accepts an anonymous, complete sheet and refuses the rest."""

    def test_a_complete_anonymous_sheet_loads(self) -> None:
        sheet = load_blind_sheet(_blind_document("rater-a"), ITEM_IDS)
        assert sheet.rater == "rater-a"
        assert len(sheet.items) == 10

    def test_unknown_is_a_label_not_a_missing_value(self) -> None:
        document = _blind_document("rater-a", {"it-03": dict.fromkeys(DIMENSIONS, "unknown")})
        sheet = load_blind_sheet(document, ITEM_IDS)
        third = next(item for item in sheet.items if item.item_id == "it-03")
        assert all(third.ratings[d] == "unknown" for d in DIMENSIONS)

    def test_a_sheet_missing_a_rating_is_refused(self) -> None:
        document = _blind_document("rater-a")
        items = document["items"]
        assert isinstance(items, list)
        del items[2]["ratings"]["abstention"]
        with pytest.raises(ValueError, match="missing ratings for abstention"):
            load_blind_sheet(document, ITEM_IDS)

    def test_a_sheet_missing_an_item_is_refused(self) -> None:
        document = _blind_document("rater-a")
        items = cast(list[dict[str, Any]], document["items"])
        document["items"] = items[:-1]
        with pytest.raises(ValueError, match="missing 1 of the 10 expected"):
            load_blind_sheet(document, ITEM_IDS)

    def test_a_sheet_with_a_duplicate_item_is_refused(self) -> None:
        document = _blind_document("rater-a")
        items = cast(list[dict[str, Any]], document["items"])
        items.append(items[0])
        with pytest.raises(ValueError, match="twice"):
            load_blind_sheet(document, ITEM_IDS)

    def test_a_blind_item_carrying_an_arm_key_is_refused(self) -> None:
        for key in ARM_KEY_VARIANTS:
            document = _blind_document("rater-a")
            cast(list[dict[str, Any]], document["items"])[0][key] = "C"
            with pytest.raises(ValueError, match="names an arm"):
                load_blind_sheet(document, ITEM_IDS)

    def test_a_label_outside_the_vocabulary_is_refused(self) -> None:
        document = _blind_document("rater-a", {"it-05": {"abstention": "maybe"}})
        with pytest.raises(ValueError, match="not one of"):
            load_blind_sheet(document, ITEM_IDS)

    def test_a_sheet_with_no_items_is_refused(self) -> None:
        document = _blind_document("rater-a")
        document["items"] = []
        with pytest.raises(ValueError, match="no items"):
            load_blind_sheet(document, ITEM_IDS)


class TestUnblinding:
    """The arm key attaches at unblinding, and only there."""

    def test_the_blind_sheet_has_no_arm_and_the_unblinded_one_does(self) -> None:
        sheet = load_blind_sheet(_blind_document("rater-a"), ITEM_IDS)
        assert not any(hasattr(item, "arm") for item in sheet.items)
        unblinded = unblind(sheet, ITEM_ARMS, ["A", "B", "C", "D", "E"])
        arms = {item.arm for item in unblinded.items}
        assert arms == {"C", "D"}
        assert all(hasattr(item, "arm") for item in unblinded.items)

    def test_an_item_with_no_arm_in_the_map_is_refused(self) -> None:
        sheet = load_blind_sheet(_blind_document("rater-a"), ITEM_IDS)
        with pytest.raises(ValueError, match="covers no arm"):
            unblind(
                sheet,
                {k: v for k, v in ITEM_ARMS.items() if k != "it-04"},
                ["A", "B", "C", "D", "E"],
            )

    def test_an_arm_outside_the_runs_five_is_refused(self) -> None:
        sheet = load_blind_sheet(_blind_document("rater-a"), ITEM_IDS)
        broken = dict(ITEM_ARMS)
        broken["it-04"] = "F"
        with pytest.raises(ValueError, match="not one of"):
            unblind(sheet, broken, ["A", "B", "C", "D", "E"])

    def test_a_map_naming_items_the_sheet_does_not_carry_is_refused(self) -> None:
        sheet = load_blind_sheet(_blind_document("rater-a"), ITEM_IDS)
        with pytest.raises(ValueError, match="does not carry"):
            unblind(sheet, {**ITEM_ARMS, "it-99": "C"}, ["A", "B", "C", "D", "E"])


class TestResolution:
    """Two raters and an arbiter settle one label per item and dimension."""

    def _two_sheets(
        self, second_rater_labels: dict[str, dict[str, str]] | None = None
    ) -> tuple[BlindSheet, BlindSheet]:
        first = load_blind_sheet(_blind_document("rater-a"), ITEM_IDS)
        second = load_blind_sheet(_blind_document("rater-b", second_rater_labels), ITEM_IDS)
        return first, second

    def test_agreement_settles_every_label(self) -> None:
        first, second = self._two_sheets()
        resolved, excluded = resolve_pair(first, second, {})
        assert not excluded
        assert all(rating.basis == "agreement" for rating in resolved)
        assert len(resolved) == 10 * len(DIMENSIONS)

    def test_a_disagreement_the_arbiter_settles_is_arbitrated(self) -> None:
        disagreement = dict.fromkeys(DIMENSIONS, "no")
        first, second = self._two_sheets({"it-07": disagreement})
        arbiter = {("it-07", dimension): "yes" for dimension in DIMENSIONS}
        resolved, excluded = resolve_pair(first, second, arbiter)
        assert not excluded
        arbitrated = [r for r in resolved if r.item_id == "it-07"]
        assert all(r.basis == "arbitrated" for r in arbitrated)
        assert all(r.label == "yes" for r in arbitrated)

    def test_a_disagreement_no_arbiter_covers_is_excluded_and_named(self) -> None:
        disagreement = dict.fromkeys(DIMENSIONS, "no")
        first, second = self._two_sheets({"it-07": disagreement})
        resolved, excluded = resolve_pair(first, second, {})
        assert not any(r.item_id == "it-07" for r in resolved)
        assert len(excluded) == len(DIMENSIONS)
        assert all(r.item_id == "it-07" for r in excluded)

    def test_raters_who_rated_different_item_sets_are_refused(self) -> None:
        # Built directly, not through the loader: the loader refuses an
        # incomplete sheet on its own; this witness is resolve_pair's own
        # check that the two sheets it resolves cover the same items.
        from evaluation.blind_sheet import BlindSheet, BlindSheetItem

        full = BlindSheet(
            sheet_id="s1",
            rater="rater-a",
            items=tuple(
                BlindSheetItem(item_id=item_id, ratings=dict.fromkeys(DIMENSIONS, "yes"))
                for item_id in ITEM_IDS
            ),
        )
        shorter = BlindSheet(
            sheet_id="s2",
            rater="rater-b",
            items=tuple(
                BlindSheetItem(item_id=item_id, ratings=dict.fromkeys(DIMENSIONS, "yes"))
                for item_id in ITEM_IDS[:-1]
            ),
        )
        with pytest.raises(ValueError, match="same items"):
            resolve_pair(full, shorter, {})

    def test_an_arbiter_label_outside_the_vocabulary_is_refused(self) -> None:
        disagreement = dict.fromkeys(DIMENSIONS, "no")
        first, second = self._two_sheets({"it-07": disagreement})
        arbiter = {("it-07", "abstention"): "unclear"}
        with pytest.raises(ValueError, match="not one of"):
            resolve_pair(first, second, arbiter)


# -- the aggregation, and its not-significant verdict ------------------------


class TestPairing:
    """The pairing refuses a denominator that would move silently."""

    def _resolved_for(self, arms_for_items: dict[str, str]) -> list[ResolvedRating]:

        ratings: list[ResolvedRating] = []
        for item_id in ITEM_IDS:
            # C's items rate the beneficial label; D's do not, so the
            # default pairing is all losses and the witnesses flip items.
            label = "yes" if arms_for_items[item_id] == "C" else "no"
            ratings.append(
                ResolvedRating(
                    item_id=item_id,
                    dimension="abstention",
                    label=label,
                    basis="agreement",
                )
            )
        return ratings

    def test_a_clean_pairing_counts_wins_losses_and_ties(self) -> None:
        ratings = self._resolved_for(ITEM_ARMS)
        counts = pair_by_case(ratings, ITEM_ARMS, ITEM_CASES, "abstention", "D", "C")
        assert counts.wins == 0
        assert counts.losses == 5
        assert counts.ties == 0
        assert counts.cases == 5

    def test_flipping_one_paired_case_makes_a_win(self) -> None:
        # case-01 is the pair (it-01 on C, it-06 on D). Turning D's label
        # to the beneficial one and C's away makes that case a win; the
        # other four stay losses.
        ratings = self._resolved_for(ITEM_ARMS)
        ratings[0] = ResolvedRating(
            item_id="it-01", dimension="abstention", label="no", basis="agreement"
        )
        ratings[5] = ResolvedRating(
            item_id="it-06", dimension="abstention", label="yes", basis="agreement"
        )
        counts = pair_by_case(ratings, ITEM_ARMS, ITEM_CASES, "abstention", "D", "C")
        assert counts.wins == 1 and counts.losses == 4

    def test_an_item_with_no_arm_is_refused_by_name(self) -> None:

        ratings = self._resolved_for(ITEM_ARMS)
        ratings.append(
            ResolvedRating(
                item_id="it-99",
                dimension="abstention",
                label="yes",
                basis="agreement",
            )
        )
        with pytest.raises(ValueError, match="cannot place it"):
            pair_by_case(ratings, ITEM_ARMS, ITEM_CASES, "abstention", "D", "C")

    def test_an_item_that_maps_to_no_case_is_refused(self) -> None:
        ratings = self._resolved_for(ITEM_ARMS)
        with pytest.raises(ValueError, match="maps to no case"):
            pair_by_case(
                ratings,
                ITEM_ARMS,
                {k: v for k, v in ITEM_CASES.items() if k != "it-01"},
                "abstention",
                "D",
                "C",
            )

    def test_an_unpaired_case_is_refused_by_name(self) -> None:

        ratings = self._resolved_for(ITEM_ARMS)
        ratings.append(
            ResolvedRating(
                item_id="it-11",
                dimension="abstention",
                label="yes",
                basis="agreement",
            )
        )
        arms = {**ITEM_ARMS, "it-11": "D"}
        cases = {**ITEM_CASES, "it-11": "case-11"}
        with pytest.raises(ValueError, match="unpaired"):
            pair_by_case(ratings, arms, cases, "abstention", "D", "C")

    def test_two_labels_for_one_case_on_one_arm_are_refused(self) -> None:
        # A case an arm answered twice has no single label to pair against;
        # the refusal names the arm, the case and both labels.
        ratings = self._resolved_for(ITEM_ARMS)
        ratings.append(
            ResolvedRating(
                item_id="it-06",
                dimension="abstention",
                label="yes",
                basis="agreement",
            )
        )
        with pytest.raises(ValueError, match="no single label"):
            pair_by_case(ratings, ITEM_ARMS, ITEM_CASES, "abstention", "D", "C")

    def test_hallucination_counts_no_as_the_beneficial_label(self) -> None:

        ratings = [
            ResolvedRating(
                item_id=item_id,
                dimension="hallucination_mis_citation",
                label="no" if ITEM_ARMS[item_id] == "D" else "yes",
                basis="agreement",
            )
            for item_id in ITEM_IDS
        ]
        counts = pair_by_case(
            ratings, ITEM_ARMS, ITEM_CASES, "hallucination_mis_citation", "D", "C"
        )
        assert counts.wins == 5 and counts.losses == 0


class TestNotSignificant:
    """The not-significant verdict is a first-class outcome that renders."""

    def test_a_small_denominator_is_not_significant_by_rule_with_no_p_value(
        self,
    ) -> None:
        verdict = assess_significance("D vs C", "abstention", PairedCounts(9, 0, 0))
        assert not verdict.significant
        assert verdict.p_value is None
        assert "below the smallest denominator" in verdict.reason

    def test_all_ties_is_not_significant_and_says_so(self) -> None:
        verdict = assess_significance("D vs C", "abstention", PairedCounts(0, 0, 20))
        assert not verdict.significant
        assert verdict.p_value is None
        assert "no evidence either way" in verdict.reason

    def test_a_p_at_or_above_alpha_is_not_significant_with_its_numbers(
        self,
    ) -> None:
        verdict = assess_significance("D vs C", "abstention", PairedCounts(6, 4, 0))
        assert not verdict.significant
        assert verdict.p_value is not None and verdict.p_value >= 0.05
        assert "p=" in verdict.reason and "6 wins" in verdict.reason

    def test_a_landslide_is_significant_and_still_carries_its_denominator(
        self,
    ) -> None:
        verdict = assess_significance("D vs C", "abstention", PairedCounts(10, 0, 0))
        assert verdict.significant
        assert verdict.p_value is not None and verdict.p_value < 0.05
        assert "10 paired cases" in verdict.reason

    def test_the_not_significant_path_renders_as_words_not_a_zero(self) -> None:
        verdict = assess_significance("D vs C", "abstention", PairedCounts(6, 4, 0))
        rendered = render_verdict(verdict)
        assert "NOT SIGNIFICANT" in rendered
        assert "reported as not significant" in rendered
        assert "10 paired cases" in rendered
        assert "difference" in rendered

    def test_the_significant_row_carries_the_gate_sentence(self) -> None:
        verdict = assess_significance("D vs C", "abstention", PairedCounts(10, 0, 0))
        rendered = render_verdict(verdict)
        assert "SIGNIFICANT" in rendered
        assert "not a phase gate" in rendered


class TestContrastReport:
    """The report renders every dimension, carrying every denominator."""

    def _resolved_all_dimensions(self) -> list[ResolvedRating]:

        return [
            ResolvedRating(
                item_id=item_id,
                dimension=dimension,
                label="yes" if ITEM_ARMS[item_id] == "C" else "no",
                basis="agreement",
            )
            for item_id in ITEM_IDS
            for dimension in DIMENSIONS
        ]

    def test_every_dimension_gets_a_row_and_the_not_significant_path_renders(
        self,
    ) -> None:

        report = build_report(
            "D vs C",
            self._resolved_all_dimensions(),
            [],
            ITEM_ARMS,
            ITEM_CASES,
            "D",
            "C",
        )
        assert [row.dimension for row in report.rows] == list(DIMENSIONS)
        rendered = render_report(report)
        assert rendered.count("NOT SIGNIFICANT") == len(DIMENSIONS)
        assert "Contrast D vs C" in rendered

    def test_excluded_ratings_are_counted_on_the_row(self) -> None:

        excluded = [
            ExcludedRating(
                item_id="it-07",
                dimension="abstention",
                reason="the raters disagreed and no arbiter resolution covers it",
            )
        ]
        report = build_report(
            "D vs C",
            self._resolved_all_dimensions(),
            excluded,
            ITEM_ARMS,
            ITEM_CASES,
            "D",
            "C",
        )
        row = next(r for r in report.rows if r.dimension == "abstention")
        assert row.excluded == 1
        others = [r for r in report.rows if r.dimension != "abstention"]
        assert all(r.excluded == 0 for r in others)

    def test_the_significant_row_renders_inside_the_report(self) -> None:
        """A significant dimension renders with the gate sentence beside it."""
        # Twenty items over ten cases, so the denominator is large enough
        # for a verdict to reach the test at all.
        wide_ids = [f"it-{index:02d}" for index in range(1, 21)]
        wide_arms = {
            **{f"it-{index:02d}": "C" for index in range(1, 11)},
            **{f"it-{index:02d}": "D" for index in range(11, 21)},
        }
        wide_cases = {
            **{f"it-{index:02d}": f"case-{index:02d}" for index in range(1, 11)},
            **{f"it-{index:02d}": f"case-{index - 10:02d}" for index in range(11, 21)},
        }
        resolved = [
            ResolvedRating(
                item_id=item_id,
                dimension=dimension,
                # D rates the beneficial label on every case and C does not:
                # a landslide on every dimension, significant on each.
                label="yes" if wide_arms[item_id] == "D" else "no",
                basis="agreement",
            )
            for item_id in wide_ids
            for dimension in DIMENSIONS
        ]
        report = build_report("D vs C", resolved, [], wide_arms, wide_cases, "D", "C")
        rendered = render_report(report)
        assert rendered.count("SIGNIFICANT") == len(DIMENSIONS)
        assert "not a phase gate" in rendered
