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

**And a metric's denominator counts what the sentence says it counts.** The
recovery metric used to report the number of collected test cases and call
it the number of injected faults; it was neither that nor the number of
distinct faults. So the denominator here is a **crash point** — one member
of the product's ``CrashPoint`` enumeration — and the sentence that
describes the figure says so, and the crash points the matrix does not
inject sit in the denominator rather than outside it.

**A reason that is not measured is derived from the tree.** The reasons
this module prints when a metric could not be measured name a missing
input, and a missing input is a fact about the tree the run was made
against — so the facts are read at run time and the reasons are written
from them. A copied reason goes stale silently, and this harness carried
two that were false in the very tree they were printed about.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

from . import manifest
from .corpus import CorpusMeasurement
from .faults import CRASH_MATRIX_FILE, CrashMatrixCoverage, read_crash_matrix
from .model import (
    SKIPPED,
    BlockerResult,
    ClassResult,
    FailureCase,
    Measurement,
    MetricRow,
    TestOutcome,
)
from .protocol import GateClass, Metric, Protocol
from .public_corpus import PublicCorpusMeasurement, measure_public_corpus
from .runner import ClassRun
from .shards import required_test_files

#: Where the tree's committed corpora live.
FIXTURES_DIR: Final = Path("tests") / "fixtures"

#: Where the retrieval ground truth lives — a human reading of three papers.
GROUND_TRUTH_PATH: Final = Path("tests") / "fixtures" / "retrieval" / "ground_truth.json"


@dataclass(frozen=True, slots=True)
class TreeFacts:
    """What the tree holds, as the "not measured" reasons depend on it.

    **The reasons are facts about the tree, so the facts are read at run
    time.** A reason written down when the harness was built goes stale the
    moment the tree changes, and it goes stale *silently*: the copy keeps
    answering, and the answer is about a tree that is no longer the one in
    front of the reader. This harness carried a reason that said the public
    fixtures *"are not in this tree"* through the very merge that delivered
    them, and another that said the tree *"holds no no-evidence fixture"*
    while one sat in ``tests/fixtures/public/no_evidence/``.

    A reason that says an input is missing when it is present is worse than
    no reason at all: it tells a reader *"this cannot be measured"* when the
    truth is *"nobody measured it"*. So the facts are read here and the
    reasons are written from them.
    """

    #: The public fixture corpus's measurement, or ``None`` when the corpus
    #: is not in the tree.
    public: PublicCorpusMeasurement | None
    #: Whether the tree holds the retrieval ground truth.
    ground_truth: bool
    #: The committed corpora the tree holds, by name.
    corpora: tuple[str, ...]


def read_tree_facts(repo_root: Path, public: PublicCorpusMeasurement | None) -> TreeFacts:
    """What the tree holds, read now."""
    fixtures = repo_root / FIXTURES_DIR
    corpora = (
        tuple(sorted(path.name for path in fixtures.glob("*") if path.is_dir()))
        if fixtures.is_dir()
        else ()
    )
    return TreeFacts(
        public=public,
        ground_truth=(repo_root / GROUND_TRUTH_PATH).is_file(),
        corpora=corpora,
    )


def not_measured_reason(metric_key: str, facts: TreeFacts) -> str:
    """Why this metric's value could not be produced, as this tree makes it.

    **Each reason says what is missing**, not "not implemented". A reason
    that named a missing feature would be a promise; a reason that names a
    missing input is a fact about the tree the run was made against — and a
    fact about a tree has to be re-read, or it is a fact about a tree that is
    no longer there.
    """
    if metric_key == "end-to-end-task-success":
        return _end_to_end_reason(facts)
    if metric_key == "evidence-locator-validity":
        return _evidence_locator_reason(facts)
    if metric_key == "unsupported-claim-detection":
        return _abstention_reason(facts)
    if metric_key == "revision-consistency":
        return _revision_reason(facts)
    return (
        "this metric has no measurement in this harness; the witness score "
        "below is what the run can say about it"
    )


def _end_to_end_reason(facts: TreeFacts) -> str:
    """Why the end-to-end task success metric could not be measured."""
    lead = (
        "the protocol's metric counts successful verified deliveries over "
        "attempted tasks; this run counts test cases"
    )
    public = facts.public
    if public is None:
        return (
            lead + ", and the tree holds no corpus of attempted tasks with verified "
            "deliveries. The public fixtures that would be that corpus are "
            "LC-P1-13 T00's deliverable and are not in this tree."
        )
    return (
        lead + f". The tree holds the public fixture corpus — {public.fixtures} "
        f"fixture(s) and {public.questions} question(s) with their answer "
        "keys — but a corpus of questions with known answers is not a record "
        "of deliveries, and nothing in the tree records a delivery that was "
        "attempted and verified, so the numerator would count nothing."
    )


def _evidence_locator_reason(facts: TreeFacts) -> str:
    """Why the evidence-locator metric could not be measured."""
    lead = (
        "the protocol asks for a human-checked sample; the tree records none, "
        "and a machine count is not a substitute for one"
    )
    if not facts.ground_truth:
        return lead + "."
    return (
        lead + ". The retrieval ground truth's observed column is a human reading "
        "of three papers, and it is not a citation-support sample over "
        "produced reports."
    )


def _abstention_reason(facts: TreeFacts) -> str:
    """Why the abstention metric could not be measured."""
    lead = (
        "the protocol's metric is about abstention, and abstention only shows "
        "up where the answer is not there"
    )
    public = facts.public
    if public is None:
        return (
            lead + "; the tree holds no no-evidence fixture to abstain over, so the "
            "numerator would count nothing."
        )
    if public.abstention_questions == 0:
        return (
            lead + "; the public fixture corpus in this tree holds no question whose "
            "answer is an abstention, so the numerator would count nothing."
        )
    return (
        lead + f"; the public fixture corpus holds {public.abstention_questions} "
        "question(s) whose answer is an abstention, and the corpus measurement "
        "did not produce the figure."
    )


def _revision_reason(facts: TreeFacts) -> str:
    """Why the revision-consistency metric could not be measured."""
    corpora = ", ".join(facts.corpora) if facts.corpora else "none"
    return (
        "the protocol's metric is the rate over source changes; this run "
        "counts the tests that check the property. The tree's committed "
        f"corpora are {corpora}, and none of them records a source change "
        "with the outcome that followed it, so the numerator would count "
        "nothing."
    )


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


#: The blocker whose subject is the required CI tests.
SKIPPED_TESTS_BLOCKER: Final = "no-skipped-required-tests"


def _excluded_required_tests(index: OutcomeIndex, repo_root: Path) -> tuple[str, ...]:
    """The required CI tests this run excluded — skipped, or not run at all.

    **The exclusion is recorded, not ruled on.** The protocol's sixth blocker
    is about required CI tests that are skipped, and the harness's witnesses
    for it watch the *mechanism* rather than the required tests themselves.
    So the fact the blocker is about was invisible: a required test with a
    skipped case sat in the tree, in the CI shards on both platforms, and
    the report's row said HELD.

    Whether a **declared** skip fails that blocker is the owner's ruling and
    not this harness's: the harness says what happened, names the file, and
    quotes the reason the test gave for not running. The exclusion is in the
    report, so a reader sees it, and the ruling is still open.
    """
    excluded: list[str] = []
    for name in required_test_files(repo_root):
        outcomes = index.by_file.get(name, ())
        if not outcomes:
            excluded.append(f"{name} — not part of this run")
            continue
        skipped = [outcome for outcome in outcomes if outcome.status == SKIPPED]
        if not skipped:
            continue
        reasons = "; ".join(
            f"{outcome.node_id}: {outcome.message or 'no reason given'}" for outcome in skipped[:3]
        )
        excluded.append(f"{name} — {len(skipped)} case(s) skipped: {reasons}")
    return tuple(excluded)


def blocker_results(
    protocol: Protocol, index: OutcomeIndex, *, repo_root: Path
) -> tuple[BlockerResult, ...]:
    """One row per Phase 1 blocker.

    **The rule.** A blocker is held when every one of its witnesses was
    collected **and passed**. A witness that was skipped is a witness that
    did not hold: the protocol's sixth blocker is exactly about required
    tests that do not run, and a witness that is skipped is a required test
    that did not run. A witness that was not part of the run at all cannot
    be evaluated, and a blocker that could not be evaluated has not held.

    **And the sixth blocker carries its exclusion.** Its witnesses watch the
    mechanism, not the required tests, so a required test that was skipped
    would not show up in them. The exclusion is therefore read out of the
    shard list and stated in the row — recorded, not ruled on.
    """
    results: list[BlockerResult] = []
    for blocker in protocol.blockers:
        witnesses = manifest.BLOCKER_WITNESSES.get(blocker.key, ())
        excluded_note = ""
        if blocker.key == SKIPPED_TESTS_BLOCKER:
            excluded = _excluded_required_tests(index, repo_root)
            if excluded:
                excluded_note = (
                    f" This run excluded {len(excluded)} required CI test(s): "
                    + "; ".join(excluded)
                    + ". The exclusion is recorded rather than ruled on: "
                    "whether a declared skip fails this blocker is the owner's "
                    "decision, and this harness does not make it."
                )
        if not witnesses:
            results.append(
                BlockerResult(
                    key=blocker.key,
                    text=blocker.text,
                    witnesses=(),
                    status="NOT_EVALUATED",
                    reason=(
                        "no test file witnesses this blocker, so the blocker "
                        "is unwatched and the run cannot say whether it holds" + excluded_note
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
                        "blocker could not be evaluated: " + ", ".join(missing) + excluded_note
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
                        "not pass; a skipped witness counts against the blocker" + excluded_note
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
                reason="every witness was collected and passed" + excluded_note,
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


def _cases_that_passed(outcomes: tuple[TestOutcome, ...]) -> dict[str, bool]:
    """Which of the crash matrix's cases passed, by case name.

    **A case's name is its node id's last segment**, and a parameterised
    case keeps its base name: a parameterisation is one case run several
    ways, and every way has to pass for the case to have passed.
    """
    passed: dict[str, bool] = {}
    for outcome in outcomes:
        name = outcome.node_id.rsplit("::", 1)[-1].split("[", 1)[0]
        passed[name] = passed.get(name, True) and outcome.passed
    return passed


def _recovery_measurement(index: OutcomeIndex, coverage: CrashMatrixCoverage | None) -> Measurement:
    """The fault-injection measurement.

    **What the denominator counts.** A **crash point**: one member of the
    product's :class:`~labcairn.recovery.contracts.CrashPoint` enumeration,
    counted once however many cases inject it. The denominator is every crash
    point the product defines, so the figure says two things at once — that
    the matrix exercises the layer, and that what it found there was right.
    A crash point the matrix never injects sits in the denominator and not in
    the numerator, so a hole in the matrix shows up in the rate instead of
    quietly shrinking the thing being measured.

    **What a case is not.** A case is not a fault. The matrix collects more
    cases than it injects faults (some of its cases re-run a fault an earlier
    case injected) and injects more faults than it has cases (one case kills
    three child processes in turn), so the number of collected cases is
    neither the number of faults nor the number of distinct faults. The
    earlier version of this measurement reported that number and called it
    the number of injected faults, and it was wrong in the way that matters:
    the number on the page was not the number the sentence described.
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
    if coverage is None:
        return Measurement(
            status="NOT_MEASURED",
            reason=(
                f"the crash matrix file ({CRASH_MATRIX_FILE}) is not in the "
                "tree, so its fault-injection coverage could not be read"
            ),
        )
    passed = _cases_that_passed(outcomes)
    correct = 0
    for member in coverage.defined:
        cases = coverage.cases_for(member)
        if not cases:
            continue
        if all(passed.get(case, False) for case in cases):
            correct += 1
    return Measurement(
        status="MEASURED",
        numerator=correct,
        denominator=len(coverage.defined),
        how=(
            "the distinct crash points the crash matrix injects and that "
            "behaved the way the matrix specifies, over the crash points the "
            "product defines — a crash point is one member of the product's "
            "CrashPoint enumeration and is counted once however many cases "
            "inject it, so the figure says whether every crash point the "
            "product defines is exercised and correct"
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


def _corpus_failures(
    corpus: CorpusMeasurement | None, public: PublicCorpusMeasurement | None
) -> list[str]:
    """What the corpus measurements found that did not match."""
    failures: list[str] = []
    if corpus is not None:
        failures.extend(corpus.failures)
    if public is not None:
        failures.extend(public.failures)
    return failures


def _metric_value(
    metric: Metric,
    index: OutcomeIndex,
    corpus: CorpusMeasurement | None,
    public: PublicCorpusMeasurement | None,
    facts: TreeFacts,
    coverage: CrashMatrixCoverage | None,
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
        also = [corpus.quantity_extraction, corpus.unit_consistency]
        if public is not None:
            also.append(public.agreement)
        failures = _corpus_failures(corpus, public)
        if failures:
            context.append("**The corpus measurements found:** " + "; ".join(failures))
        return corpus.exactness, tuple(also), tuple(context)

    if metric.key == "unsupported-claim-detection":
        if public is not None and public.abstention_questions > 0:
            failures = list(public.failures)
            if failures:
                context.append("**The public corpus measurement found:** " + "; ".join(failures))
            context.append(
                f"the public fixture corpus holds {public.fixtures} fixture(s) and "
                f"{public.questions} question(s); the metric above is over the "
                f"{public.abstention_questions} of them whose answer is an "
                "abstention, and the corpus's numeric questions are measured "
                "under the numeric-cell extraction metric"
            )
            return public.abstention, (), tuple(context)
        return (
            Measurement(status="NOT_MEASURED", reason=not_measured_reason(metric.key, facts)),
            (),
            tuple(context),
        )

    if metric.key == "recovery-correctness":
        value = _recovery_measurement(index, coverage)
        cases = len(index.by_file.get(CRASH_MATRIX_FILE, ()))
        covered = len(coverage.covered) if coverage is not None else 0
        context.append(
            f"the crash matrix collected {cases} case(s) in this run and "
            f"injects {covered} distinct crash point(s). A case is not a "
            "fault — the matrix's cases do not correspond one to one with the "
            "faults they inject — so the figure above counts crash points and "
            "not cases."
        )
        return value, (), tuple(context)

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

    value = Measurement(status="NOT_MEASURED", reason=not_measured_reason(metric.key, facts))
    return value, (), tuple(context)


def metric_rows(
    protocol: Protocol,
    index: OutcomeIndex,
    classes: tuple[ClassResult, ...],
    corpus: CorpusMeasurement | None,
    total_seconds: float,
    context: tuple[str, ...] = (),
    *,
    repo_root: Path,
) -> tuple[MetricRow, ...]:
    """One row per protocol metric.

    **The measurements are made against the tree, not against a copy of what
    the tree held once.** The public fixture corpus is read here, so a tree
    that has the corpus and a tree that does not are measured differently,
    and the difference is visible in the report rather than in a note
    somebody remembered to write.
    """
    public = measure_public_corpus(repo_root)
    facts = read_tree_facts(repo_root, public)
    coverage: CrashMatrixCoverage | None
    try:
        coverage = read_crash_matrix(repo_root)
    except FileNotFoundError:
        coverage = None
    rows: list[MetricRow] = []
    for metric in protocol.metrics:
        witnesses = manifest.METRIC_WITNESSES.get(metric.key, ())
        value, also, metric_context = _metric_value(
            metric, index, corpus, public, facts, coverage, classes, total_seconds
        )
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
