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

import importlib.util
import json
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any, cast
from uuid import UUID

import pytest
from evaluation import blind_rating_closeout as closeout
from evaluation import blind_runner
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

from labcairn.core.providers.protocol import ModelRequest, UsageReport
from labcairn.core.providers.usage import Known
from labcairn.providers.budget import RunBudget
from labcairn.providers.credentials import Protocol, ProviderSettings

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


@lru_cache(maxsize=1)
def _cli_module() -> ModuleType:
    """The executable entry point, loaded once for the command-line witnesses."""
    path = Path(__file__).resolve().parent.parent / "scripts" / "run_blind_evaluation.py"
    spec = importlib.util.spec_from_file_location("run_blind_evaluation_for_tests", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_case_set(directory: Path) -> Path:
    """Write the dry run's synthetic case set as a real-mode input file."""
    path = directory / "cases.json"
    document = {"cases": [case.to_document() for case in blind_runner.synthetic_cases()]}
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _write_approvals(directory: Path, *, count: int) -> Path:
    """Write owner approval records, one per request."""
    path = directory / "approvals.json"
    document = {
        "approvals": [
            {
                "approval_id": str(UUID(int=index + 1)),
                "capability": "model.request",
                "root_id": "task",
                "resource_key": "output",
                "arguments": {},
            }
            for index in range(count)
        ]
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _provider_settings() -> ProviderSettings:
    """Settings that construct without I/O; no credential is read until build_model."""
    return ProviderSettings(protocol=Protocol.OPENAI, model="test-model, params fixed")


class _Consent:
    """A consent port that grants everything, for the refusal tests.

    The tests that use it stop before a provider is built, so nothing is sent.
    """

    def require(self, request: ModelRequest) -> None:
        return None


class _Capture:
    """A usage capture that reports a measured count, for the refusal tests."""

    def observe(self, body: Mapping[str, object]) -> None:
        return None

    def report(self) -> UsageReport:
        return UsageReport(input_tokens=Known(1), output_tokens=Known(1))


class TestTheRunDriver:
    """The driver's two modes, and the line between them.

    The dry run's witnesses hold three things at once: the whole pipeline runs,
    every request lands on the stub, and the record claims no model. The real
    witnesses hold the boundary that makes a real run the owner's: no consent,
    no ceiling, no capture, no provider — and a real run that has finished its
    requests **stops at awaiting ratings** rather than inventing a comparison.
    """

    def test_a_dry_run_never_constructs_a_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Every request lands on the stub; the real-provider path is never entered."""

        def explode(*args: Any, **kwargs: Any) -> None:
            raise AssertionError("the dry run tried to construct a real provider")

        monkeypatch.setattr(blind_runner, "build_real_provider", explode)
        summary = blind_runner.run_dry(out_dir=tmp_path)
        assert summary.provider_calls == 0
        assert summary.stub_calls == 5 * blind_runner.DRY_RUN_CASE_COUNT
        assert {artifact.provider for artifact in summary.artifacts} == {
            blind_runner.DRY_RUN_PROVIDER
        }
        assert summary.model == ""

    def test_a_dry_run_writes_the_shapes_the_scoring_stage_reads(self, tmp_path: Path) -> None:
        """Artefacts, packet, sheets and verdicts all have the shapes they claim."""
        summary = blind_runner.run_dry(out_dir=tmp_path)
        assert len(summary.artifacts) == 5 * blind_runner.DRY_RUN_CASE_COUNT
        artifact_files = sorted((tmp_path / "artifacts").glob("*.json"))
        assert len(artifact_files) == 5 * blind_runner.DRY_RUN_CASE_COUNT

        packet = json.loads((tmp_path / "blind_packet.json").read_text(encoding="utf-8"))
        assert len(packet["items"]) == 5 * blind_runner.DRY_RUN_CASE_COUNT
        expected_item_ids = [item["item_id"] for item in packet["items"]]
        for item in packet["items"]:
            assert not set(ARM_KEY_VARIANTS) & set(item)
            assert item["output"].startswith("[dry-run synthetic output]")

        for name in ("rater-a.json", "rater-b.json"):
            sheet = load_blind_sheet(
                json.loads((tmp_path / "ratings" / name).read_text(encoding="utf-8")),
                expected_item_ids,
            )
            assert len(sheet.items) == 5 * blind_runner.DRY_RUN_CASE_COUNT

        record = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
        assert record["model"] == ""
        assert record["provider_calls"] == 0
        assert record["stub_calls"] == 5 * blind_runner.DRY_RUN_CASE_COUNT
        assert record["status"] == blind_runner.STATUS_DRY_RUN_COMPLETE
        assert "stub" in record["limitations"]
        assert record["significance"]["synthetic"] is True
        assert len(record["significance"]["contrasts"]) == 2
        for contrast in record["significance"]["contrasts"]:
            assert len(contrast["rows"]) == len(DIMENSIONS)
            for row in contrast["rows"]:
                assert row["significant"] is False
                assert row["p_value"] is None
                assert row["ties"] == blind_runner.DRY_RUN_CASE_COUNT

        report = (tmp_path / "report.md").read_text(encoding="utf-8")
        assert "DRY RUN" in report
        assert "measurement of a model" in report.lower()

    def test_scoring_a_completed_run_uses_the_production_loader(self, tmp_path: Path) -> None:
        """The score mode loads real sheets, unblinds, and judges both contrasts."""
        run_dir = tmp_path / "run"
        blind_runner.run_dry(out_dir=run_dir)
        scored = blind_runner.run_score(
            run_dir=run_dir,
            rater_a=run_dir / "ratings" / "rater-a.json",
            rater_b=run_dir / "ratings" / "rater-b.json",
            arbiter=run_dir / "ratings" / "arbiter.json",
            out_dir=tmp_path / "scored",
        )
        assert scored.status == blind_runner.STATUS_EVALUATED
        assert len(scored.contrasts) == 2
        for report in scored.contrasts:
            for row in report.rows:
                assert row.verdict.significant is False
                assert row.verdict.p_value is None
        record = json.loads((tmp_path / "scored" / "run.json").read_text(encoding="utf-8"))
        assert record["mode"] == blind_runner.MODE_SCORE
        assert record["status"] == blind_runner.STATUS_EVALUATED
        assert record["significance"]["synthetic"] is False

    def test_a_real_run_stops_before_it_claims_a_comparison(self, tmp_path: Path) -> None:
        """A finished real run is AWAITING RATINGS, and its record says NOT RUN."""
        summary = blind_runner.run_real(
            provider=blind_runner.DryRunProvider(),
            out_dir=tmp_path,
            model="test-model, params fixed",
            budget="max_model_requests=80",
            cases=blind_runner.synthetic_cases(),
        )
        assert summary.status == blind_runner.STATUS_AWAITING_RATINGS
        assert summary.provider_calls == 5 * blind_runner.DRY_RUN_CASE_COUNT
        record = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
        assert record["status"] == blind_runner.STATUS_AWAITING_RATINGS
        assert record["significance"]["status"] == "NOT RUN"
        assert record["significance"]["reason"]
        report = (tmp_path / "report.md").read_text(encoding="utf-8")
        assert "AWAITING RATINGS" in report
        assert "significance was not computed" in report.lower()

    def test_a_real_provider_cannot_be_built_without_consent(self) -> None:
        """ADR-0006's port is a constructor argument, and this driver keeps it so."""
        with pytest.raises(blind_runner.RealRunRefusedError, match="outbound consent"):
            blind_runner.build_real_provider(
                _provider_settings(),
                consent=None,
                budget=RunBudget(max_total_tokens=Known(100)),
                usage_capture=_Capture(),
            )

    def test_a_real_provider_cannot_be_built_without_a_budget_ceiling(self) -> None:
        """An unbounded budget is not an authorisation to spend."""
        for budget in (None, RunBudget()):
            with pytest.raises(blind_runner.RealRunRefusedError, match="budget ceiling"):
                blind_runner.build_real_provider(
                    _provider_settings(),
                    consent=_Consent(),
                    budget=budget,
                    usage_capture=_Capture(),
                )

    def test_a_real_provider_cannot_be_built_without_a_usage_capture(self) -> None:
        """Without a capture every token is Unknown and the first ceiling refuses."""
        with pytest.raises(blind_runner.RealRunRefusedError, match="usage capture"):
            blind_runner.build_real_provider(
                _provider_settings(),
                consent=_Consent(),
                budget=RunBudget(max_total_tokens=Known(100)),
                usage_capture=None,
            )

    def test_missing_real_requirements_names_every_missing_piece(self) -> None:
        """The command can explain everything that is missing in one refusal."""
        problems = blind_runner.missing_real_requirements(
            approvals=None,
            budget=None,
            model="",
            usage_capture=None,
        )
        assert len(problems) == 4
        text = " ".join(problems)
        assert "owner approval" in text
        assert "budget ceiling" in text
        assert "no model" in text
        assert "usage capture" in text

    def test_an_empty_approval_grant_list_is_refused_at_construction(self) -> None:
        """The consent port itself refuses a run with no approvals.

        An independent review mutated the ``if not grants`` branch and this
        witness did not exist, so the mutation survived. The CLI test below it
        only exercised the argument-level refusal, which returns before the
        port is constructed.
        """
        with pytest.raises(blind_runner.RealRunRefusedError, match="at least one owner approval"):
            blind_runner.ConsumingApprovals(cast(Any, None), [])


class TestTheRunDriverCommand:
    """The executable entry point: it runs the dry run and refuses the real one."""

    def test_the_command_runs_a_dry_run(self, tmp_path: Path) -> None:
        """The default mode completes and leaves a run record behind."""
        module = _cli_module()
        assert module.main(["--mode", "dry-run", "--out", str(tmp_path)]) == 0
        assert (tmp_path / "run.json").exists()

    def test_a_real_run_without_approvals_is_refused_before_a_provider(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """No owner approval means no provider is constructed at all."""
        cases = _write_case_set(tmp_path)

        def explode(*args: Any, **kwargs: Any) -> None:
            raise AssertionError("the command constructed a provider without an approval")

        monkeypatch.setattr(blind_runner, "build_real_provider", explode)
        code = _cli_module().main(
            [
                "--mode",
                "real",
                "--cases",
                str(cases),
                "--workspace-root",
                str(tmp_path),
                "--task",
                "task-1",
                "--model",
                "test-model",
            ]
        )
        assert code == 2
        assert "approval" in capsys.readouterr().err.lower()

    def test_a_real_run_without_a_budget_is_refused_before_a_provider(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Approvals are not enough: the run also needs a ceiling."""
        cases = _write_case_set(tmp_path)
        approvals = _write_approvals(tmp_path, count=5 * blind_runner.DRY_RUN_CASE_COUNT)

        def explode(*args: Any, **kwargs: Any) -> None:
            raise AssertionError("the command constructed a provider without a budget")

        monkeypatch.setattr(blind_runner, "build_real_provider", explode)
        code = _cli_module().main(
            [
                "--mode",
                "real",
                "--cases",
                str(cases),
                "--workspace-root",
                str(tmp_path),
                "--task",
                "task-1",
                "--model",
                "test-model",
                "--approvals",
                str(approvals),
            ]
        )
        assert code == 2
        assert "budget ceiling" in capsys.readouterr().err

    def test_the_real_run_parses_the_task_id_as_a_uuid(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The approval ledger stores a UUID task id, not the CLI's raw string.

        Real material exposed this: ``TaskId`` is a NewType, so
        ``TaskId(args.task)`` keeps the command-line string at runtime, and
        every granted approval fails with ``task_scope_mismatch`` before any
        request leaves. A real run must parse it, as the CLI's other entry
        points do. The witness monkeypatches the context manager to capture
        the id the command hands the application layer.
        """
        module = _cli_module()
        cases = _write_case_set(tmp_path)
        approvals = _write_approvals(tmp_path, count=5 * blind_runner.DRY_RUN_CASE_COUNT)
        #: A config file is all ``read_config`` needs before the context opens;
        #: the witness stops there, so no database and no provider are built.
        (tmp_path / ".labcairn").mkdir(exist_ok=True)
        (tmp_path / ".labcairn" / "workspace.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "database": "labcairn.db",
                    "source_dirs": [],
                    "current_task": None,
                }
            ),
            encoding="utf-8",
        )
        task_id = UUID("01a1a5ed-c2ee-73dc-92d2-c98e8e0f6c37")
        seen: list[Any] = []

        @contextmanager
        def capture(location: Any, config: Any, tid: Any, **kwargs: Any) -> Any:
            seen.append(tid)
            raise RuntimeError("the witness stops before a workspace is opened")

        monkeypatch.setattr(module, "application_context", capture)
        monkeypatch.setattr(module, "build_http_client", lambda *a, **k: object())
        code = module.main(
            [
                "--mode",
                "real",
                "--cases",
                str(cases),
                "--out",
                str(tmp_path / "out"),
                "--workspace-root",
                str(tmp_path),
                "--task",
                str(task_id),
                "--model",
                "test-model",
                "--approvals",
                str(approvals),
                "--budget-max-model-requests",
                "5",
            ]
        )
        assert code == 2, "the witness's own stop is a refusal, not a sent request"
        assert seen == [task_id], (
            "the real run handed the application layer something other than the "
            "parsed UUID; an approval bound to a UUID cannot match a string"
        )

    def test_the_real_run_hands_its_timeout_to_the_provider_settings(
        self,
        tmp_path: Path,
    ) -> None:
        """A long review must not be cut off by the library's 60s default.

        Real material exposed this: a full case prompt made the endpoint's
        generation exceed the default, and the CLI had no way to raise it. The
        witness asks for 240 seconds and reads the setting the command builds;
        the assertion is on the settings object, not on a promise in a docstring.
        """
        module = _cli_module()
        args = module._parser().parse_args(
            ["--mode", "real", "--timeout-s", "240", "--model", "test-model"]
        )
        settings = module._provider_settings(args)
        assert settings.timeout_s == 240.0
        assert (
            module._provider_settings(
                module._parser().parse_args(["--mode", "real", "--model", "test-model"])
            ).timeout_s
            == 60.0
        )

    def test_a_real_run_refuses_a_task_id_that_is_not_a_uuid(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A task id that cannot be parsed never reaches the consent bridge."""
        cases = _write_case_set(tmp_path)
        approvals = _write_approvals(tmp_path, count=5 * blind_runner.DRY_RUN_CASE_COUNT)
        code = _cli_module().main(
            [
                "--mode",
                "real",
                "--cases",
                str(cases),
                "--workspace-root",
                str(tmp_path),
                "--task",
                "task-1",
                "--model",
                "test-model",
                "--approvals",
                str(approvals),
                "--budget-max-model-requests",
                "5",
            ]
        )
        assert code == 2
        assert "--task must be a UUID" in capsys.readouterr().err

    def test_a_real_run_with_an_empty_approvals_file_is_refused_before_a_provider(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An approvals document that parses to no grants reaches the refusal path.

        This is the real-mode shape the review found unwitnessed: the file
        exists, so the argument-level "no --approvals" check is passed, and the
        run must still stop before a provider. It also holds the loader to
        treating an empty list as a refusal rather than a malformed document.
        """
        cases = _write_case_set(tmp_path)
        empty = tmp_path / "approvals-empty.json"
        empty.write_text(json.dumps({"approvals": []}), encoding="utf-8")

        def explode(*args: Any, **kwargs: Any) -> None:
            raise AssertionError("the command constructed a provider from an empty approval list")

        monkeypatch.setattr(blind_runner, "build_real_provider", explode)
        code = _cli_module().main(
            [
                "--mode",
                "real",
                "--cases",
                str(cases),
                "--workspace-root",
                str(tmp_path),
                "--task",
                "task-1",
                "--model",
                "test-model",
                "--approvals",
                str(empty),
            ]
        )
        assert code == 2
        assert "0 approvals" in capsys.readouterr().err


# -- human rating close-out --------------------------------------------------


def _closeout_rows() -> tuple[list[dict[str, Any]], dict[str, str]]:
    """84 invented call rows and their answer bodies, in the run's own shape.

    The bodies are English fixture sentences, not material or a real answer.
    The two arrangement variants share the letter ``B`` and are separated by
    their roles, exactly as the scaled run's measurements record them.
    """
    rows: list[dict[str, Any]] = []
    bodies: dict[str, str] = {}
    schedule: list[tuple[str, str, str, list[str]]] = [
        ("five_arm", arm, f"b5-{case:02d}", ["guidance"])
        for arm in ("A", "B", "C", "D", "E")
        for case in range(1, 13)
    ]
    schedule += [("arrangement_pair", "B", f"b5-{case:02d}", ["guidance"]) for case in range(1, 13)]
    schedule += [
        ("arrangement_pair", "B", f"b5-{case:02d}", ["guidance", "independent_critique"])
        for case in range(1, 13)
    ]
    assert len(schedule) == 84
    for call, (group, arm, case, roles) in enumerate(schedule, start=1):
        name = f"call-{call:03d}-{group}-{arm}-{case}.txt"
        rows.append(
            {
                "call": call,
                "group": group,
                "arm": arm,
                "case": case,
                "roles": roles,
                "status": "ok",
                "answer_file": name,
            }
        )
        bodies[name] = f"[synthetic answer volume {call}]"
    return rows, bodies


def _closeout_volumes() -> tuple[closeout.AnswerVolume, ...]:
    """The 84 volumes as the close-out reader parses them."""
    rows, bodies = _closeout_rows()
    return closeout.build_volumes(rows, bodies)


def _assembled() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Two anonymous sheets and their withheld map over the synthetic volumes."""
    return closeout.assemble_rating_sheets(_closeout_volumes())


def _item_ids(sheet: Mapping[str, Any]) -> list[str]:
    """The item ids in the order a rater received them."""
    items = sheet["items"]
    assert isinstance(items, list)
    return [str(item["item_id"]) for item in items if isinstance(item, Mapping)]


def _completed_sheet(sheet: Mapping[str, Any], *, rater: str, rated: bool = True) -> dict[str, Any]:
    """A human has considered and confirmed every one of the five labels."""
    return {"sheet_id": sheet["sheet_id"], "rater": rater, "rated": rated, "items": sheet["items"]}


@dataclass(frozen=True, slots=True)
class _CloseoutInputs:
    """One completed close-out's machine inputs, named rather than positional."""

    sheet_a: dict[str, Any]
    sheet_b: dict[str, Any]
    arbiter: dict[str, Any]
    unblinding: dict[str, Any]
    denominators: dict[str, Any]


def _complete_inputs(*, disagreements: Sequence[tuple[str, str]] = ()) -> _CloseoutInputs:
    """Two completed sheets, a third reader, the withheld map and denominators."""
    sheet_a, sheet_b, unblinding = _assembled()
    documents = (
        _completed_sheet(sheet_a, rater=closeout.RATER_A),
        _completed_sheet(sheet_b, rater=closeout.RATER_B),
    )
    for item_id, dimension in disagreements:
        for document in documents:
            items = document["items"]
            assert isinstance(items, list)
            for item in items:
                assert isinstance(item, Mapping)
                if item["item_id"] == item_id:
                    ratings = item["ratings"]
                    assert isinstance(ratings, dict)
                    ratings[dimension] = "yes" if document["rater"] == closeout.RATER_A else "no"
    decisions = [
        {"item_id": item_id, "dimension": dimension, "label": "yes"}
        for item_id, dimension in disagreements
    ]
    all_cases = sorted({str(entry["case"]) for entry in unblinding["items"].values()})
    return _CloseoutInputs(
        sheet_a=documents[0],
        sheet_b=documents[1],
        arbiter={"reader": "third-reader", "arbitrations": decisions},
        unblinding=unblinding,
        denominators={closeout.DENOMINATOR_FIELD: dict.fromkeys(DIMENSIONS, all_cases)},
    )


def _all_denominators(unblinding: Mapping[str, Any]) -> dict[str, Any]:
    """The widest legal denominator mask, for witnesses that do not narrow it."""
    all_cases = sorted({str(entry["case"]) for entry in unblinding["items"].values()})
    return {closeout.DENOMINATOR_FIELD: dict.fromkeys(DIMENSIONS, all_cases)}


class TestHumanRatingCloseout:
    """The close-out's anonymity, independence, refusals and verdict words."""

    def test_the_leak_vocabulary_carries_no_routes_to_the_answer(self) -> None:
        """The consistency check's input has no id paired with an arm or case."""
        _, _, unblinding = _assembled()
        vocabulary = closeout.make_leak_vocabulary(unblinding)
        assert set(vocabulary) == {
            "item_ids",
            "forbidden_values",
            "source_ids",
            "case_ids",
            "notice",
        }
        assert "items" not in vocabulary
        assert len(vocabulary["item_ids"]) == 84
        assert set(vocabulary["item_ids"]) == set(unblinding["items"])
        for entry in unblinding["items"].values():
            assert isinstance(entry, Mapping)
            for value in (entry["arm"], entry["case"], entry["source_id"]):
                assert value in vocabulary["forbidden_values"]
        with pytest.raises(closeout.RatingRefusedError, match="unblinding map itself"):
            closeout.assert_anonymous_sheets(*_assembled())

    def test_the_84_volumes_are_anonymous_and_carry_no_route_to_the_answer(self) -> None:
        """Every withheld value is absent from both sheets' structural fields."""
        sheet_a, sheet_b, unblinding = _assembled()
        vocabulary = closeout.make_leak_vocabulary(unblinding)
        assert len(_item_ids(sheet_a)) == len(_item_ids(sheet_b)) == 84
        assert set(sheet_a) == closeout.BLIND_SHEET_KEYS
        assert set(sheet_b) == closeout.BLIND_SHEET_KEYS
        for sheet in (sheet_a, sheet_b):
            items = sheet["items"]
            assert isinstance(items, list)
            for item in items:
                assert isinstance(item, Mapping)
                assert set(item) == closeout.BLIND_ITEM_KEYS
                assert set(item["ratings"]) == set(DIMENSIONS)
                assert "arm" not in item
                assert "case" not in item
                assert "issue_key" not in item
                assert "annotator_id" not in item
        closeout.assert_anonymous_sheets(sheet_a, sheet_b, vocabulary)
        for sheet in (sheet_a, sheet_b):
            for entry in unblinding["items"].values():
                assert isinstance(entry, Mapping)
                for value in entry.values():
                    rendered = json.dumps(
                        {
                            "sheet_id": sheet["sheet_id"],
                            "rater": sheet["rater"],
                            "items": [
                                {"item_id": item["item_id"], "ratings": item["ratings"]}
                                for item in sheet["items"]
                            ],
                        },
                        ensure_ascii=False,
                    )
                    assert str(value) not in rendered

    def test_answer_routes_in_answer_bodies_are_redacted_before_rating(self) -> None:
        """A quoted case key or source id cannot travel with the answer body."""
        rows, bodies = _closeout_rows()
        rows[0]["case"] = "b5-01"
        bodies[rows[0]["answer_file"]] = (
            f"synthetic answer quoting b5-02 and {rows[1]['answer_file'].removesuffix('.txt')}"
        )
        volumes = closeout.build_volumes(rows, bodies)
        assert volumes[0].answer == (
            "synthetic answer quoting [case-key redacted] and [source-id redacted]"
        )

    def test_a_mapping_value_in_the_blind_sheet_is_refused(self) -> None:
        """An arm smuggled into a sheet field is a leak, not a field to strip."""
        sheet_a, sheet_b, unblinding = _assembled()
        vocabulary = closeout.make_leak_vocabulary(unblinding)
        items = sheet_a["items"]
        assert isinstance(items, list)
        first = items[0]
        assert isinstance(first, dict)
        first["arm"] = "D"
        with pytest.raises(closeout.RatingRefusedError, match="anonymous schema"):
            closeout.assert_anonymous_sheets(sheet_a, sheet_b, vocabulary)
        first.pop("arm")
        first["answer_route"] = "call-001-five_arm-D-b5-01"
        with pytest.raises(closeout.RatingRefusedError, match="anonymous schema"):
            closeout.assert_anonymous_sheets(sheet_a, sheet_b, vocabulary)

    def test_a_withheld_value_in_an_answer_body_is_refused(self) -> None:
        """A source id pasted into an answer is a route back to the answer."""
        sheet_a, sheet_b, unblinding = _assembled()
        vocabulary = closeout.make_leak_vocabulary(unblinding)
        source = next(iter(unblinding["items"].values()))["source_id"]
        items = sheet_a["items"]
        assert isinstance(items, list)
        first = items[0]
        assert isinstance(first, dict)
        first["answer"] = str(source)
        with pytest.raises(closeout.RatingRefusedError, match="source id"):
            closeout.assert_anonymous_sheets(sheet_a, sheet_b, vocabulary)

    def test_a_case_key_in_an_answer_body_is_refused(self) -> None:
        """A case key in an answer body is a route to the case and answer."""
        sheet_a, sheet_b, unblinding = _assembled()
        vocabulary = closeout.make_leak_vocabulary(unblinding)
        case = next(iter(unblinding["items"].values()))["case"]
        items = sheet_a["items"]
        assert isinstance(items, list)
        first = items[0]
        assert isinstance(first, dict)
        first["answer"] = f"synthetic answer for {case}"
        with pytest.raises(closeout.RatingRefusedError, match="case key"):
            closeout.assert_anonymous_sheets(sheet_a, sheet_b, vocabulary)

    def test_a_withheld_value_in_a_structural_field_is_refused(self) -> None:
        """A case or source value hidden under a legal field name is a leak."""
        sheet_a, sheet_b, unblinding = _assembled()
        vocabulary = closeout.make_leak_vocabulary(unblinding)
        case = next(iter(unblinding["items"].values()))["case"]
        items = sheet_a["items"]
        assert isinstance(items, list)
        first = items[0]
        assert isinstance(first, dict)
        ratings = first["ratings"]
        assert isinstance(ratings, dict)
        ratings[str(case)] = "unknown"
        with pytest.raises(closeout.RatingRefusedError, match="five rating columns"):
            closeout.assert_anonymous_sheets(sheet_a, sheet_b, vocabulary)
        ratings.pop(str(case))
        first["sheet_id"] = str(case)
        with pytest.raises(closeout.RatingRefusedError, match="anonymous schema"):
            closeout.assert_anonymous_sheets(sheet_a, sheet_b, vocabulary)
        first.pop("sheet_id")
        hidden = dict(sheet_a)
        hidden["rater"] = str(case)
        with pytest.raises(closeout.RatingRefusedError, match="leaks a withheld value"):
            closeout.assert_anonymous_sheets(hidden, sheet_b, vocabulary)

    def test_the_two_raters_receive_different_orders(self) -> None:
        """The same seed is not two independent readings."""
        sheet_a, sheet_b, unblinding = _assembled()
        vocabulary = closeout.make_leak_vocabulary(unblinding)
        assert _item_ids(sheet_a) != _item_ids(sheet_b)
        assert set(_item_ids(sheet_a)) == set(_item_ids(sheet_b))
        with pytest.raises(closeout.RatingRefusedError, match="same volume order"):
            closeout.assemble_rating_sheets(
                _closeout_volumes(),
                seed_a=closeout.SEED_A,
                seed_b=closeout.SEED_A,
            )
        second = dict(sheet_b)
        second["items"] = sheet_a["items"]
        with pytest.raises(closeout.RatingRefusedError, match="same volume order"):
            closeout.assert_anonymous_sheets(sheet_a, second, vocabulary)

    def test_the_two_sheets_carry_the_same_answer_bodies(self) -> None:
        """Two readings of different texts would be an agreement about nothing."""
        inputs = _complete_inputs()
        items = inputs.sheet_b["items"]
        assert isinstance(items, list)
        first = items[0]
        assert isinstance(first, dict)
        first["answer"] = f"{first['answer']} (edited)"
        with pytest.raises(
            closeout.RatingRefusedError, match="do not carry the same answer bodies"
        ):
            closeout.consistency_check(inputs.sheet_a, inputs.sheet_b)

    def test_an_unrated_sheet_is_refused_instead_of_defaulting_to_a_score(self) -> None:
        """Assembly's unknown labels are not human ratings until confirmed."""
        sheet_a, _, _ = _assembled()
        with pytest.raises(closeout.RatingRefusedError, match="not confirmed as rated"):
            closeout.load_rating_sheet(
                _completed_sheet(sheet_a, rater=closeout.RATER_A, rated=False),
                _item_ids(sheet_a),
                rater=closeout.RATER_A,
            )
        completed = _completed_sheet(sheet_a, rater=closeout.RATER_A)
        items = completed["items"]
        assert isinstance(items, list)
        first = items[0]
        assert isinstance(first, dict)
        ratings = first["ratings"]
        assert isinstance(ratings, dict)
        ratings.pop("abstention")
        with pytest.raises(closeout.RatingRefusedError, match="without five ratings"):
            closeout.load_rating_sheet(completed, _item_ids(sheet_a), rater=closeout.RATER_A)

    def test_a_missing_arbitration_is_refused_not_counted_as_agreement(self) -> None:
        """An unresolved disagreement never silently becomes a settled label."""
        _, _, unblinding = _assembled()
        disagreement = (sorted(unblinding["items"])[0], "evidence_support")
        inputs = _complete_inputs(disagreements=[disagreement])
        empty = {"reader": "third-reader", "arbitrations": []}
        empty_denominators: dict[str, Any] = {
            closeout.DENOMINATOR_FIELD: {dimension: [] for dimension in DIMENSIONS}
        }
        with pytest.raises(closeout.RatingRefusedError, match="no third-reader arbitration"):
            closeout.close_out(
                inputs.sheet_a,
                inputs.sheet_b,
                empty,
                inputs.unblinding,
                empty_denominators,
            )
        with pytest.raises(closeout.RatingRefusedError, match="no third-reader arbitration"):
            closeout.load_arbitrations(empty, [disagreement])
        rater_as_arbiter = {"reader": closeout.RATER_A, "arbitrations": []}
        with pytest.raises(closeout.RatingRefusedError, match="third reader, not a rater"):
            closeout.load_arbitrations(rater_as_arbiter, [disagreement])

    def test_the_arbitration_packet_carries_no_route_to_the_answer(self) -> None:
        """The third reader sees two labels and the answer, never a placement."""
        _, _, unblinding = _assembled()
        disagreement = (sorted(unblinding["items"])[0], "evidence_support")
        inputs = _complete_inputs(disagreements=[disagreement])
        agreement, _, _ = closeout.consistency_check(inputs.sheet_a, inputs.sheet_b)
        packet = closeout.build_arbitration_packet(agreement, inputs.sheet_a, inputs.sheet_b)
        assert set(packet) == {"reader", "items"}
        assert packet["reader"] == "third-reader"
        assert len(packet["items"]) == 1
        item = packet["items"][0]
        assert set(item) == {"item_id", "dimension", "answer", "labels"}
        assert item["item_id"] == disagreement[0]
        assert item["dimension"] == disagreement[1]
        assert item["labels"] == ["no", "yes"]
        rendered = json.dumps(packet, ensure_ascii=False, sort_keys=True)
        for entry in unblinding["items"].values():
            assert isinstance(entry, Mapping)
            for value in entry.values():
                assert str(value) not in rendered
        for forbidden in ("rater-a", "rater-b", "arm", "case", "source_id"):
            assert f'"{forbidden}"' not in rendered

    def test_a_not_significant_result_is_reported_as_not_significant(self) -> None:
        """All ties are a first-class result, not a win, a zero or an exception."""
        inputs = _complete_inputs()
        report = closeout.close_out(
            inputs.sheet_a,
            inputs.sheet_b,
            inputs.arbiter,
            inputs.unblinding,
            inputs.denominators,
        )
        rendered = report.render()
        assert len(report.reports) == 3
        assert "NOT SIGNIFICANT" in rendered
        assert not rendered.startswith("SIGNIFICANT") and "\nSIGNIFICANT" not in rendered
        assert not any(
            line.startswith("SIGNIFICANT") for line in closeout.summarise_verdicts(report.reports)
        )
        assert rendered.count("not significant: every one of 12 paired cases tied") == 15
        for contrast in report.reports:
            assert all(not row.verdict.significant for row in contrast.rows)
            assert all(row.verdict.counts.ties == 12 for row in contrast.rows)
            for line in closeout.summarise_verdicts((contrast,)):
                assert "NOT SIGNIFICANT" in line
                assert "wins=0, losses=0, ties=12" in line

    def test_a_significant_verdict_is_not_rounded_into_a_not_significant_one(self) -> None:
        """The verdict words come from the exact sign test, in both directions."""
        counts = PairedCounts(wins=11, losses=0, ties=1)
        verdict = assess_significance("D vs C", "evidence_support", counts)
        assert verdict.significant is True
        assert closeout.verdict_word(verdict.significant) == "SIGNIFICANT"
        assert closeout.verdict_word(False) == "NOT SIGNIFICANT"
        assert "NOT SIGNIFICANT" in render_verdict(
            assess_significance("D vs C", "evidence_support", PairedCounts(3, 1, 8))
        )

    def test_the_end_to_end_closeout_pairs_twelve_cases_on_each_contrast(self) -> None:
        """Three contrasts, five dimensions, 12 paired cases each, no exclusions."""
        inputs = _complete_inputs()
        report = closeout.close_out(
            inputs.sheet_a,
            inputs.sheet_b,
            inputs.arbiter,
            inputs.unblinding,
            inputs.denominators,
        )
        assert tuple(one.contrast for one in report.reports) == (
            "D vs C",
            "E vs D",
            "B+C vs B-only",
        )
        assert len(report.resolved) == 84 * len(DIMENSIONS)
        assert report.excluded == ()
        for contrast in report.reports:
            assert len(contrast.rows) == len(DIMENSIONS)
            assert all(row.verdict.counts.cases == 12 for row in contrast.rows)

    def test_the_arrangement_contrast_is_measured_not_hardwired(self) -> None:
        """The arrangement pair's verdict comes from the ratings, not from a rule.

        Every ``B+critique`` volume is rated ``yes`` on the four dimensions
        whose beneficial label is ``yes``, by both raters identically, while
        every ``B-only`` volume stays ``unknown``. The arrangement contrast
        then wins on those four dimensions and goes significant, while the
        work order's two contrasts — whose volumes nobody touched — stay all
        ties. Hallucination is the control on the control: its beneficial
        label is ``no``, so identical ``yes`` ratings tie there, and the
        dimension's own denominator rule is what shows in the verdict.
        """
        inputs = _complete_inputs()
        critique_ids = {
            item_id
            for item_id, entry in inputs.unblinding["items"].items()
            if entry["arm"] == "B+critique"
        }
        assert len(critique_ids) == 12
        for document in (inputs.sheet_a, inputs.sheet_b):
            items = document["items"]
            assert isinstance(items, list)
            for item in items:
                assert isinstance(item, Mapping)
                if item["item_id"] in critique_ids:
                    ratings = item["ratings"]
                    assert isinstance(ratings, dict)
                    ratings.update(dict.fromkeys(DIMENSIONS, "yes"))
        report = closeout.close_out(
            inputs.sheet_a,
            inputs.sheet_b,
            inputs.arbiter,
            inputs.unblinding,
            inputs.denominators,
        )
        by_contrast = {one.contrast: one for one in report.reports}
        arrangement = by_contrast["B+C vs B-only"]
        for row in arrangement.rows:
            if row.dimension == closeout.HALLUCINATION_DIMENSION:
                assert not row.verdict.significant
                assert row.verdict.counts.ties == 12
            else:
                assert row.verdict.significant
                assert row.verdict.counts == PairedCounts(wins=12, losses=0, ties=0)
        for contrast in ("D vs C", "E vs D"):
            assert all(not row.verdict.significant for row in by_contrast[contrast].rows)
        rendered = report.render()
        assert rendered.count(": SIGNIFICANT;") == 4
        assert rendered.count(": NOT SIGNIFICANT;") == 11
        assert rendered.count("Contrast B+C vs B-only:") == 1

    def test_the_arrangement_contrast_refuses_an_unpaired_case(self) -> None:
        """A case one arrangement arm covers and the other does not is refused.

        The two arrangement variants share the letter ``B``; the pairing reads
        the arm key the assembly cast from the roles. Moving one volume's arm
        in the withheld map — which the blind sheets cannot see — leaves that
        case with two ``B+critique`` ratings and none for ``B-only``, a
        denominator that would move without anyone seeing it move.
        """
        inputs = _complete_inputs()
        items = inputs.unblinding["items"]
        assert isinstance(items, dict)
        b_only = sorted(item_id for item_id, e in items.items() if e["arm"] == "B-only")
        items[b_only[0]]["arm"] = "B+critique"
        with pytest.raises(ValueError, match="unpaired on 1 case"):
            closeout.close_out(
                inputs.sheet_a,
                inputs.sheet_b,
                inputs.arbiter,
                inputs.unblinding,
                inputs.denominators,
            )

    def test_the_denominators_are_refused_rather_than_defaulted(self) -> None:
        """A missing, unknown or partial hallucination denominator is refused."""
        inputs = _complete_inputs()
        cases = sorted({str(entry["case"]) for entry in inputs.unblinding["items"].values()})
        with pytest.raises(closeout.RatingRefusedError, match="no denominators mapping"):
            closeout.close_out(
                inputs.sheet_a,
                inputs.sheet_b,
                inputs.arbiter,
                inputs.unblinding,
                {},
            )
        unknown = dict.fromkeys(DIMENSIONS, cases)
        unknown["abstention"] = [*cases, "b5-99"]
        with pytest.raises(closeout.RatingRefusedError, match="outside the run"):
            closeout.read_denominators({closeout.DENOMINATOR_FIELD: unknown}, cases)
        partial = dict.fromkeys(DIMENSIONS, cases)
        partial[closeout.HALLUCINATION_DIMENSION] = cases[:-1]
        with pytest.raises(closeout.RatingRefusedError, match="must cover every case"):
            closeout.read_denominators({closeout.DENOMINATOR_FIELD: partial}, cases)

    def test_each_dimension_uses_its_own_denominator(self) -> None:
        """An evidence-bounded dimension is not silently widened to every case."""
        inputs = _complete_inputs()
        cases = sorted({str(entry["case"]) for entry in inputs.unblinding["items"].values()})
        denominators = dict.fromkeys(DIMENSIONS, cases)
        denominators["problem_identification"] = cases[:5]
        denominators["evidence_support"] = cases[3:]
        report = closeout.close_out(
            inputs.sheet_a,
            inputs.sheet_b,
            inputs.arbiter,
            inputs.unblinding,
            {closeout.DENOMINATOR_FIELD: denominators},
        )
        by_dimension = {row.dimension: row for contrast in report.reports for row in contrast.rows}
        assert by_dimension["problem_identification"].verdict.counts.cases == 5
        assert by_dimension["evidence_support"].verdict.counts.cases == 9
        assert by_dimension[closeout.HALLUCINATION_DIMENSION].verdict.counts.cases == 12
        assert by_dimension["abstention"].verdict.counts.cases == 12


# -- the second paper's assembly ---------------------------------------------


def _unseen2_rows() -> tuple[list[dict[str, Any]], dict[str, str]]:
    """91 invented call rows in the second paper's shape, and their bodies.

    These rows name their answers by the run's own item id instead of by a
    file name, and they record the scope the driver ran them under. The five
    calibration calls record no group at all: the scope says which group they
    belong to. The bodies are English fixture sentences, not material and not
    a real answer.
    """
    rows: list[dict[str, Any]] = []
    bodies: dict[str, str] = {}
    schedule: list[tuple[str, str, str, list[str], bool]] = []
    for arm in ("A", "B", "C", "D", "E"):
        schedule.append(("five_arm", arm, "b6-01", ["guidance"], False))
    for case_number in range(2, 14):
        for arm in ("A", "B", "C", "D", "E"):
            schedule.append(("five_arm", arm, f"b6-{case_number:02d}", ["guidance"], True))
    for case_number in range(1, 14):
        schedule.append(("arrangement_pair", "B", f"b6-{case_number:02d}", ["guidance"], True))
        schedule.append(
            (
                "arrangement_pair",
                "B",
                f"b6-{case_number:02d}",
                ["guidance", "independent_critique"],
                True,
            )
        )
    assert len(schedule) == 91
    scopes = {"five_arm": "five_arm_unseen2", "arrangement_pair": "arrangement_pair_unseen2"}
    for call, (group, arm, case_key, roles, carries_group) in enumerate(schedule, start=1):
        item_id = f"item-{call:016x}"
        row: dict[str, Any] = {
            "call": call,
            "arm": arm,
            "case": case_key,
            "roles": roles,
            "status": "ok",
            "item_id": item_id,
            "run_scope": scopes[group],
        }
        if carries_group:
            row["group"] = group
        rows.append(row)
        bodies[item_id] = f"[synthetic answer volume {call}]"
    return rows, bodies


def _unseen2_volumes() -> tuple[closeout.AnswerVolume, ...]:
    """The 91 volumes as the close-out reader parses them."""
    rows, bodies = _unseen2_rows()
    return closeout.build_volumes(rows, bodies)


def _rated_sheet(sheet: Mapping[str, Any], *, rater: str) -> dict[str, Any]:
    """One rater's sheet with every label set to the same considered value."""
    items: list[dict[str, Any]] = []
    for item in sheet["items"]:
        assert isinstance(item, Mapping)
        items.append(
            {
                "item_id": item["item_id"],
                "answer": item["answer"],
                "ratings": dict.fromkeys(DIMENSIONS, "yes"),
            }
        )
    return {"sheet_id": sheet["sheet_id"], "rater": rater, "rated": True, "items": items}


class TestTheSecondPapersAssembly:
    """The second paper's 91 answers: two scopes, one anonymous shape."""

    def test_the_ninety_one_volumes_assemble_into_two_anonymous_sheets(self) -> None:
        """Every answer of the second paper is rated, and none of them leaks."""
        volumes = _unseen2_volumes()
        assert len(volumes) == 91
        arms: dict[str, int] = {}
        for volume in volumes:
            arms[volume.arm] = arms.get(volume.arm, 0) + 1
        assert arms == {
            "A": 13,
            "B": 13,
            "C": 13,
            "D": 13,
            "E": 13,
            "B-only": 13,
            "B+critique": 13,
        }
        sheet_a, sheet_b, unblinding = closeout.assemble_rating_sheets(volumes)
        assert len(unblinding["items"]) == 91
        assert set(_item_ids(sheet_a)) == set(unblinding["items"])
        assert set(_item_ids(sheet_b)) == set(unblinding["items"])
        assert all(item_id.startswith("volume-") for item_id in unblinding["items"])
        run_ids = {volume.source_id for volume in volumes}
        assert run_ids.isdisjoint(unblinding["items"])
        assert _item_ids(sheet_a) != _item_ids(sheet_b)
        closeout.assert_anonymous_sheets(
            sheet_a, sheet_b, closeout.make_leak_vocabulary(unblinding)
        )

    def test_the_runs_own_item_id_is_not_an_anonymous_id(self) -> None:
        """The gap the second paper's rating table had: its ids were item-."""
        rows, _ = _unseen2_rows()
        run_item_id = str(rows[0]["item_id"])
        assert run_item_id.startswith("item-")
        with pytest.raises(closeout.RatingRefusedError, match="non-anonymous item id"):
            closeout.read_unblinding({"items": {run_item_id: {"arm": "A", "case": "b6-01"}}})

    def test_the_group_is_read_from_the_run_scope_when_the_row_records_none(self) -> None:
        """A row that records no group still belongs to the group its scope names."""
        rows, bodies = _unseen2_rows()
        calibration = next(row for row in rows if "group" not in row)
        assert calibration["run_scope"] == "five_arm_unseen2"
        volumes = closeout.build_volumes(rows, bodies)
        by_source = {volume.source_id: volume for volume in volumes}
        assert by_source[str(calibration["item_id"])].arm == str(calibration["arm"])

        without_group = [dict(row) for row in rows]
        for row in without_group:
            row.pop("group", None)
        volumes = closeout.build_volumes(without_group, bodies)
        arrangement = [volume for volume in volumes if volume.arm in {"B-only", "B+critique"}]
        assert len(arrangement) == 26

    def test_a_row_whose_scope_contradicts_its_group_is_refused(self) -> None:
        """A scope that says another group is not read past the row that says it."""
        rows, bodies = _unseen2_rows()
        contradicted = [dict(row) for row in rows]
        target = next(row for row in contradicted if row.get("group") == "five_arm")
        target["run_scope"] = "arrangement_pair_unseen2"
        with pytest.raises(closeout.RatingRefusedError, match="names the group"):
            closeout.build_volumes(contradicted, bodies)

    def test_a_run_scope_that_names_no_group_is_refused(self) -> None:
        """A scope that names no protocol group is not guessed at."""
        rows, bodies = _unseen2_rows()
        unknown = [dict(row) for row in rows]
        target = next(row for row in unknown if "group" not in row)
        target["run_scope"] = "pilot_unseen2"
        with pytest.raises(
            closeout.RatingRefusedError, match="carries no group and no run scope naming one"
        ):
            closeout.build_volumes(unknown, bodies)

    def test_one_answer_cannot_be_claimed_by_two_run_scopes(self) -> None:
        """One answer under two scopes would be rated twice, under two arms."""
        rows, bodies = _unseen2_rows()
        collided = [dict(row) for row in rows]
        five_arm_row = next(row for row in collided if row.get("group") == "five_arm")
        arrangement_row = next(row for row in collided if row.get("group") == "arrangement_pair")
        arrangement_row["item_id"] = five_arm_row["item_id"]
        with pytest.raises(closeout.RatingRefusedError, match="claimed by two run scopes"):
            closeout.build_volumes(collided, bodies)

    def test_the_first_paper_is_unaffected_by_the_second_papers_shape(self) -> None:
        """The first paper's 84 volumes read exactly as they did before."""
        volumes = _closeout_volumes()
        assert len(volumes) == 84
        arms: dict[str, int] = {}
        for volume in volumes:
            arms[volume.arm] = arms.get(volume.arm, 0) + 1
        assert arms == {
            "A": 12,
            "B": 12,
            "C": 12,
            "D": 12,
            "E": 12,
            "B-only": 12,
            "B+critique": 12,
        }
        sheet_a, sheet_b, unblinding = closeout.assemble_rating_sheets(volumes)
        assert len(unblinding["items"]) == 84
        assert all(item_id.startswith("volume-") for item_id in unblinding["items"])
        assert _item_ids(sheet_a) != _item_ids(sheet_b)

    def test_the_third_contrast_is_computable_once_the_arrangement_volumes_are_in_the_table(
        self,
    ) -> None:
        """With all 91 volumes rated, the arrangement pair is one of three."""
        volumes = _unseen2_volumes()
        sheet_a, sheet_b, unblinding = closeout.assemble_rating_sheets(volumes)
        report = closeout.close_out(
            _rated_sheet(sheet_a, rater=closeout.RATER_A),
            _rated_sheet(sheet_b, rater=closeout.RATER_B),
            {"reader": "third-reader", "arbitrations": []},
            unblinding,
            _all_denominators(unblinding),
        )
        assert [contrast.contrast for contrast in report.reports] == [
            "D vs C",
            "E vs D",
            "B+C vs B-only",
        ]
        for contrast in report.reports:
            assert len(contrast.rows) == len(DIMENSIONS)
            for row in contrast.rows:
                verdict = row.verdict
                assert verdict.counts.wins == 0
                assert verdict.counts.losses == 0
                assert verdict.counts.ties == 13
                assert verdict.significant is False
        assert closeout.verdict_word(False) == "NOT SIGNIFICANT"
