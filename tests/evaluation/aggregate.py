"""Turning outcomes into the report's rows.

**The three rules this module exists to enforce.**

1. **Every number carries its denominator.** A class's row says how many
   cases were *collected* and how many *passed*, and a metric's row says
   what its numerator and its denominator count. A rate over no cases is
   ``None``, never ``0.0``: zero says "every case failed", and no cases is
   not that.

2. **A failure is listed, not averaged away.** Every class carries its
   failure cases, and the report prints them. A rate that hides which cases
   failed is a rate that cannot be acted on.

3. **A skipped witness is a failed witness.** The protocol's sixth Phase 1
   blocker names *"Required CI tests [that] are skipped, ignored or only
   pass by mocking"*. So a blocker whose witness did not run is a blocker
   that did not hold — and a blocker whose witness was **skipped** is a
   blocker that did not hold, even though nothing failed. The distinction
   that matters is between *not run* and *passed*, and the harness keeps
   it everywhere.

**What a metric's value is, and what its witnesses are.** These are two
different numbers and the report keeps them apart. The *value* is what the
protocol asks for — the rate over a corpus, a sample, or a run. The
*witness score* is how many of the tests that check that property passed.
A witness score is **not** the metric's value, and a row that only carried
one of them would be a row whose number means something the protocol did
not ask for.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final

from . import manifest
from .corpus import CorpusMeasurement
from .model import (
    BlockerResult,
    ClassResult,
    FailureCase,
    Measurement,
    MetricRow,
    TestOutcome,
)
from .protocol import GateClass, Metric, Protocol
from .runner import ClassRun

#: The file whose cases are the fault-injection scenarios, one case per
#: scenario.
CRASH_MATRIX_FILE: Final = "test_recovery_crash_matrix.py"

#: Why each metric's value could not be produced, where it could not be.
#:
#: Each reason says **what is missing**, not "not implemented". A reason
#: that named a missing feature would be a promise; a reason that names a
#: missing input is a fact about the tree the run was made against.
NOT_MEASURED_REASONS: Final[dict[str, str]] = {
    "end-to-end-task-success": (
        "the protocol's metric counts successful verified deliveries over "
        "attempted tasks; this run counts test cases, and the tree holds no "
        "corpus of attempted tasks with verified deliveries. The public "
        "fixtures that would be that corpus are LC-P1-13 T00's deliverable "
        "and are not in this tree."
    ),
    "evidence-locator-validity": (
        "the protocol asks for a human-checked sample; the tree records none, "
        "and a machine count is not a substitute for one. The retrieval "
        "ground truth's observed column is a human reading of three papers, "
        "and it is not a citation-support sample over produced reports."
    ),
    "unsupported-claim-detection": (
        "the protocol's metric is about abstention, and abstention only shows "
        "up where the answer is not there; the tree holds no no-evidence "
        "fixture to abstain over, so the numerator would count nothing."
    ),
    "revision-consistency": (
        "the protocol's metric is the rate over source changes; this run "
        "counts the tests that check the property, and the tree records no "
        "corpus of source-change runs with their outcomes."
    ),
}


@dataclass(frozen=True, slots=True)
class OutcomeIndex:
    """Every outcome of the run, filed by the file it came from.

    **Keyed by the bare file name.** The manifest names the repository's
    test files by their bare names, and pytest's JUnit XML names them by a
    path relative to the root directory. Keying the index by the bare name
    makes the two agree whatever pytest writes — and the repository's test
    files are flat in ``tests/``, so a bare name identifies one.
    """

    by_file: Mapping[str, tuple[TestOutcome, ...]]
    files_run: frozenset[str]

    def of(self, files: tuple[str, ...]) -> tuple[TestOutcome, ...]:
        """The outcomes of these files, in the order the files are given."""
        outcomes: list[TestOutcome] = []
        for name in files:
            outcomes.extend(self.by_file.get(name, ()))
        return tuple(outcomes)

    def not_run(self, files: tuple[str, ...]) -> tuple[str, ...]:
        """The files that were not part of the run."""
        return tuple(name for name in files if name not in self.files_run)


def index_outcomes(runs: tuple[ClassRun, ...]) -> OutcomeIndex:
    """File every outcome of the run by its file."""
    by_file: dict[str, list[TestOutcome]] = {}
    files_run: set[str] = set()
    for run in runs:
        for outcome in run.outcomes:
            name = PurePosixPath(outcome.file).name
            by_file.setdefault(name, []).append(outcome)
            files_run.add(name)
    return OutcomeIndex(
        by_file={name: tuple(outcomes) for name, outcomes in by_file.items()},
        files_run=frozenset(files_run),
    )


def class_result(gate_class: GateClass, run: ClassRun, *, selected: bool = True) -> ClassResult:
    """One class's row."""
    return ClassResult(
        key=gate_class.key,
        title=gate_class.label,
        definition=gate_class.definition,
        files=run.files,
        outcomes=run.outcomes,
        duration_seconds=run.duration_seconds,
        ran=run.ran,
        selected=selected,
        not_run_reason=run.error,
    )


def blocker_results(protocol: Protocol, index: OutcomeIndex) -> tuple[BlockerResult, ...]:
    """One row per Phase 1 blocker.

    **The rule.** A blocker is held when every one of its witnesses was
    collected **and passed**. A witness that was skipped is a witness that
    did not hold: the protocol's sixth blocker is exactly about required
    tests that do not run, and a witness that is skipped is a required test
    that did not run. A witness that was not part of the run at all cannot
    be evaluated, and a blocker that could not be evaluated has not held.
    """
    results: list[BlockerResult] = []
    for blocker in protocol.blockers:
        witnesses = manifest.BLOCKER_WITNESSES.get(blocker.key, ())
        if not witnesses:
            results.append(
                BlockerResult(
                    key=blocker.key,
                    text=blocker.text,
                    witnesses=(),
                    status="NOT_EVALUATED",
                    reason=(
                        "no test file witnesses this blocker, so the blocker "
                        "is unwatched and the run cannot say whether it holds"
                    ),
                )
            )
            continue
        missing = index.not_run(witnesses)
        outcomes = index.of(witnesses)
        failures = tuple(
            FailureCase(
                node_id=outcome.node_id,
                file=outcome.file,
                status=outcome.status,
                message=outcome.message,
            )
            for outcome in outcomes
            if not outcome.passed
        )
        if missing:
            results.append(
                BlockerResult(
                    key=blocker.key,
                    text=blocker.text,
                    witnesses=witnesses,
                    status="NOT_EVALUATED",
                    failures=failures,
                    reason=(
                        "these witness files were not part of this run, so the "
                        "blocker could not be evaluated: " + ", ".join(missing)
                    ),
                )
            )
            continue
        if failures:
            results.append(
                BlockerResult(
                    key=blocker.key,
                    text=blocker.text,
                    witnesses=witnesses,
                    status="FAILED",
                    failures=failures,
                    reason=(
                        f"{len(failures)} of {len(outcomes)} witness cases did "
                        "not pass; a skipped witness counts against the blocker"
                    ),
                )
            )
            continue
        results.append(
            BlockerResult(
                key=blocker.key,
                text=blocker.text,
                witnesses=witnesses,
                status="HELD",
            )
        )
    return tuple(results)


def _witness_score(index: OutcomeIndex, witnesses: tuple[str, ...]) -> Measurement:
    """The witnesses' own score: passed over collected."""
    outcomes = index.of(witnesses)
    if not outcomes:
        return Measurement(
            status="NOT_MEASURED",
            reason="none of this metric's witness files were part of the run",
        )
    passed = sum(1 for outcome in outcomes if outcome.passed)
    return Measurement(
        status="MEASURED",
        numerator=passed,
        denominator=len(outcomes),
        how=(
            "the test cases in this metric's witness files that passed, over "
            "the test cases collected in them"
        ),
    )


def _witness_failures(index: OutcomeIndex, witnesses: tuple[str, ...]) -> tuple[FailureCase, ...]:
    """The witness cases that did not pass."""
    return tuple(
        FailureCase(
            node_id=outcome.node_id,
            file=outcome.file,
            status=outcome.status,
            message=outcome.message,
        )
        for outcome in index.of(witnesses)
        if not outcome.passed
    )


def _recovery_measurement(index: OutcomeIndex) -> Measurement:
    """The fault-injection measurement.

    The crash matrix's cases are the scenarios: one case per injected
    fault. So the denominator is the number of fault-injection scenarios
    the matrix ran, and the numerator is the number of them that ended
    with the behaviour the matrix specifies — which for AT2 is the
    *blocking* of the replay, not the replay's success.
    """
    outcomes = index.by_file.get(CRASH_MATRIX_FILE, ())
    if not outcomes:
        return Measurement(
            status="NOT_MEASURED",
            reason=(
                f"the crash matrix file ({CRASH_MATRIX_FILE}) was not part of "
                "this run, so no fault-injection scenario was measured"
            ),
        )
    passed = sum(1 for outcome in outcomes if outcome.passed)
    return Measurement(
        status="MEASURED",
        numerator=passed,
        denominator=len(outcomes),
        how=(
            "the fault-injection scenarios the crash matrix ran, over the "
            "scenarios it holds; one collected test case is one injected "
            "fault, and a scenario counts as correct when the matrix's own "
            "expected behaviour is what happened"
        ),
    )


def _latency_measurement(
    index: OutcomeIndex,
    classes: tuple[ClassResult, ...],
    total_seconds: float,
) -> Measurement:
    """The latency measurement.

    **What this is.** The wall-clock the harness's own gate-class runs took,
    over the test cases they collected — a mean per case.

    **What this is not.** It is not the protocol's task latency, which
    needs a corpus of tasks and a provider that answers them. The report
    says so in the metric's own row, and the cost — the other half of the
    protocol's bullet — is recorded as not measured, because no real
    provider ran.
    """
    collected = sum(result.collected for result in classes)
    if collected == 0:
        return Measurement(
            status="NOT_MEASURED",
            reason="no test case was collected, so there is no latency to report",
        )
    milliseconds = round(total_seconds * 1000)
    return Measurement(
        status="MEASURED",
        numerator=milliseconds,
        denominator=collected,
        how=(
            "the wall-clock milliseconds the harness's own gate-class runs "
            "took, over the test cases they collected — a mean per case, and "
            "not the protocol's task latency, which needs a task corpus and "
            "a provider that answers it"
        ),
    )


def _metric_value(
    metric: Metric,
    index: OutcomeIndex,
    corpus: CorpusMeasurement | None,
    classes: tuple[ClassResult, ...],
    total_seconds: float,
) -> tuple[Measurement, tuple[Measurement, ...], tuple[str, ...]]:
    """A metric's own value, its further measurements, and its context."""
    context: list[str] = []

    if metric.key == "numeric-extraction-exactness":
        if corpus is None:
            value = Measurement(
                status="NOT_MEASURED",
                reason="the committed corpus could not be read in this run",
            )
            return value, (), tuple(context)
        return (
            corpus.exactness,
            (corpus.quantity_extraction, corpus.unit_consistency),
            tuple(context),
        )

    if metric.key == "recovery-correctness":
        return _recovery_measurement(index), (), tuple(context)

    if metric.key == "latency-usage-cost":
        value = _latency_measurement(index, classes, total_seconds)
        context.append(
            "cost: NOT MEASURED — no real provider ran, so there is no cost to "
            "report. The protocol says mock-only success is insufficient, so "
            "this is stated rather than filled in."
        )
        context.append(
            "model name: NOT MEASURED for a real provider — the offline run "
            "used the deterministic FakeProvider, which is not a declared "
            "model, version and parameter set."
        )
        return value, (), tuple(context)

    reason = NOT_MEASURED_REASONS.get(metric.key)
    if reason is None:  # pragma: no cover - every metric has a reason
        reason = (
            "this metric has no measurement in this harness; the witness "
            "score below is what the run can say about it"
        )
    value = Measurement(status="NOT_MEASURED", reason=reason)
    return value, (), tuple(context)


def metric_rows(
    protocol: Protocol,
    index: OutcomeIndex,
    classes: tuple[ClassResult, ...],
    corpus: CorpusMeasurement | None,
    total_seconds: float,
    context: tuple[str, ...] = (),
) -> tuple[MetricRow, ...]:
    """One row per protocol metric."""
    rows: list[MetricRow] = []
    for metric in protocol.metrics:
        witnesses = manifest.METRIC_WITNESSES.get(metric.key, ())
        value, also, metric_context = _metric_value(metric, index, corpus, classes, total_seconds)
        rows.append(
            MetricRow(
                key=metric.key,
                text=metric.text,
                value=value,
                witnesses=witnesses,
                witness_score=_witness_score(index, witnesses),
                failures=_witness_failures(index, witnesses),
                also=also,
                context=(*metric_context, *context),
            )
        )
    return tuple(rows)
