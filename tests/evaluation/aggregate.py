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

   **§1.4.1b puts one category outside that rule, and keeps it visible.** A
   skip whose reason names a fact of the machine — an OS, a filesystem, a
   volume with no 8.3 names — is not evidence that a blocker failed, because
   the CI matrix runs both platforms and no single runner carries the pair.
   Those skips, and a test in a class the owner has ruled is discharged
   outside the offline run, are **accepted and still named** in the row.
   A skip whose reason names no standing category **fails**, on both sides:
   a witness case that skipped that way fails its blocker, and a required CI
   test that skipped that way fails the sixth. See
   :func:`_witness_cases` and :func:`_excluded_required_tests`.

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
    #: The files the run *asked* pytest for, whether or not a case came out of
    #: them. A support module named `test_*.py` is selected and collects
    #: nothing, and that is a different fact from a file no class holds — the
    #: first says a required test checked nothing here, the second says only
    #: that this run did not look.
    files_selected: frozenset[str]

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
    files_selected: set[str] = set()
    for run in runs:
        for path in run.files:
            files_selected.add(PurePosixPath(path.replace("\\", "/")).name)
        for outcome in run.outcomes:
            name = PurePosixPath(outcome.file).name
            by_file.setdefault(name, []).append(outcome)
            files_run.add(name)
    return OutcomeIndex(
        by_file={name: tuple(outcomes) for name, outcomes in by_file.items()},
        files_run=frozenset(files_run),
        files_selected=frozenset(files_selected),
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


#: A required test skipped because of a fact about the machine the run happens
#: to sit on — an OS, a filesystem feature, a volume with no 8.3 names. The CI
#: matrix spans both platforms, so no single runner carries a platform pair, and
#: ruling these a failure would demand the suite prove a POSIX fact on Windows.
PLATFORM_CONDITIONAL: Final = "platform-conditional"

#: A required test in a class the default run never selects, in a class the
#: owner has ruled on from the other side: the real-model smoke, discharged by
#: the scheduled workflow (§1.4.2). Its absence is a fact about the protocol's
#: offline posture, not a required test that skipped.
OWNER_RULED_ABSENT: Final = "owner-ruled-absent"

#: A required test the run did not select, in a class the default run *does*
#: select. Naming this a skip would be a claim about a test that was never
#: skipped, so it carries its own category: recorded, and not something the
#: blocker's status is decided by.
NOT_IN_RUN: Final = "not-in-this-run"

#: A required test the run asked pytest for, and in which pytest collected no
#: case. A support module named `test_*.py` is the shape: it is selected, it is
#: in the CI's shard list, and it carries nothing to check. Naming it is the
#: point — calling it "not selected" would be false, and calling it a pass
#: would be worse.
COLLECTED_NOTHING: Final = "selected-and-collected-nothing"

#: Neither. §1.4.1b's ruling is that these **fail** the sixth blocker: "required
#: CI tests are skipped" is exactly the hole the blocker watches, and a reason
#: that names no standing category is not a declaration.
UNDECLARED: Final = "undeclared"

#: The phrases that make a skip's reason a platform or filesystem fact. Read as
#: substrings of the reason the test itself gave, so the declaration lives with
#: the skip and there is no second list to keep in step. A new machine-conditional
#: skip whose wording misses these becomes UNDECLARED and fails the blocker —
#: failing closed, and loud enough that the fix is to add the phrase here with a
#: sentence about which fact of the machine it names.
_PLATFORM_REASON: Final[tuple[str, ...]] = (
    "POSIX permission bits",
    "meaningless on POSIX",
    "Windows path semantics",
    "8.3 short names",
    "Windows facility",
    "Windows-specific",
    "mklink /J unavailable",
    "junction creation refused",
    "symlink creation unavailable",
    "alternate data streams unavailable",
    "does not exist on this machine",
    "refused by the OS",
)


@dataclass(frozen=True, slots=True)
class ExcludedTest:
    """One required CI test this run did not carry to a pass, and why."""

    name: str
    category: str
    detail: str


def _category_of(
    file_name: str, reason: str, *, selected: bool = True, collected: bool = True
) -> str:
    """Which standing category a required test's exclusion falls in, per §1.4.1b.

    **A file the run does not even select is classified by its class, not its
    message** — the real-model smoke never reaches a skip on the offline path,
    because its class is not run at all. The class table (`OFFLINE_CLASSES`) is
    the existing declaration of that, so this reads it rather than naming a
    file, and a future non-offline class is covered by the same rule. A file in
    an *offline* class that this particular run left out was not skipped
    either, so it gets its own category rather than the failure one — and a
    file the run *did* ask for that produced no case gets a third, because
    saying it "was not selected" would be false.
    """
    if any(phrase in reason for phrase in _PLATFORM_REASON):
        return PLATFORM_CONDITIONAL
    class_key = manifest.FILE_ASSIGNMENTS.get(file_name, (None, None))[0]
    if class_key is None:
        return UNDECLARED
    if not manifest.OFFLINE_CLASSES.get(class_key, (True,))[0]:
        return OWNER_RULED_ABSENT
    if not selected:
        return NOT_IN_RUN
    if not collected:
        return COLLECTED_NOTHING
    return UNDECLARED


def _excluded_required_tests(index: OutcomeIndex, repo_root: Path) -> tuple[ExcludedTest, ...]:
    """The required CI tests this run excluded — skipped, or not run at all.

    **The exclusion used to be recorded and not ruled on, and §1.4.1b has now
    ruled.** The protocol's sixth blocker is about required CI tests that are
    skipped; the harness's witnesses watch the *mechanism* rather than the
    required tests themselves, so the fact the blocker is about was invisible.
    The owner's answer splits the exclusions into the categories above and one
    failure mode: a machine-conditional skip and a test in a class the owner has
    ruled discharged elsewhere are accepted and still named; so is a test this
    run simply did not select, because it was not skipped. A required test that
    skipped for a reason naming no standing category fails the blocker, by name
    and with the reason the test gave.
    """
    excluded: list[ExcludedTest] = []
    for name in required_test_files(repo_root):
        outcomes = index.by_file.get(name, ())
        selected = name in index.files_selected
        if not outcomes:
            excluded.append(
                ExcludedTest(
                    name=name,
                    category=_category_of(name, "", selected=selected, collected=False),
                    detail="no case was collected in it",
                )
            )
            continue
        skipped = [outcome for outcome in outcomes if outcome.status == SKIPPED]
        if not skipped:
            continue
        for outcome in skipped:
            excluded.append(
                ExcludedTest(
                    name=name,
                    category=_category_of(name, outcome.message, selected=selected),
                    detail=f"{outcome.node_id}: {outcome.message or 'no reason given'}",
                )
            )
    return tuple(excluded)


#: The wording each standing category carries in a row, so the two notes below
#: cannot drift apart by saying the same thing in two different sentences.
_STANDING_LABEL: Final[dict[str, str]] = {
    PLATFORM_CONDITIONAL: "a platform or filesystem fact, which the CI "
    "matrix's other platform carries (§1.4.1b)",
    OWNER_RULED_ABSENT: "a test in a class the owner has ruled is discharged outside it (§1.4.1b)",
    NOT_IN_RUN: "a test this run did not select, which is a fact about the "
    "run's scope and not a skipped test (§1.4.1b)",
    COLLECTED_NOTHING: "a test this run asked pytest for and in which no case "
    "was collected, which is not a skip and is not a check either (§1.4.1b)",
}

#: The categories §1.4.1b accepts. `NOT_IN_RUN` is absent because it can only
#: describe a file the run never touched, and a file the run never touched is
#: not a witness case — the witness rule reports that as unevaluated.
ACCEPTED_CATEGORIES: Final[frozenset[str]] = frozenset({PLATFORM_CONDITIONAL, OWNER_RULED_ABSENT})


def _exclusion_note(excluded: tuple[ExcludedTest, ...]) -> str:
    """The row's account of what the run excluded, grouped by category.

    Every one is shown, including the accepted ones: an acceptance that hides
    what it accepted is the same invisibility this blocker exists to close.
    """
    if not excluded:
        return ""
    parts: list[str] = []
    for category, label in _STANDING_LABEL.items():
        named = [e for e in excluded if e.category == category]
        if named:
            # One line per file, not per case: three platform skips in one file
            # are three facts, and listing the file three times reads as three
            # files. The per-case detail is what the refused listing carries.
            files = list(dict.fromkeys(e.name for e in named))
            parts.append(
                f"This run accepted {len(files)} required CI test(s) as {label}: "
                + ", ".join(files)
                + "."
            )
    refused = [e for e in excluded if e.category == UNDECLARED]
    if refused:
        parts.append(
            f"This run found {len(refused)} required CI test(s) skipped with no "
            "standing category, which fails the blocker (§1.4.1b): "
            + "; ".join(f"{e.name} — {e.detail}" for e in refused)
            + "."
        )
    return " " + " ".join(parts)


def _witness_cases(
    outcomes: tuple[TestOutcome, ...],
) -> tuple[tuple[ExcludedTest, ...], tuple[FailureCase, ...]]:
    """The witness cases that did not pass, split into accepted and counted.

    **§1.4.1b seen from the witness side.** The CI matrix runs both platforms
    and no single runner carries a platform pair, so a witness case that
    skipped for a fact of the machine is not evidence that the blocker failed —
    it is evidence that this runner is one of the two. Every other non-passing
    case counts against the blocker exactly as it always has: a failure, an
    error, or a skip whose reason names no standing category.
    """
    accepted: list[ExcludedTest] = []
    failures: list[FailureCase] = []
    for outcome in outcomes:
        if outcome.passed:
            continue
        if outcome.status == SKIPPED:
            category = _category_of(PurePosixPath(outcome.file).name, outcome.message)
            if category in ACCEPTED_CATEGORIES:
                accepted.append(
                    ExcludedTest(name=outcome.node_id, category=category, detail=outcome.message)
                )
                continue
        failures.append(
            FailureCase(
                node_id=outcome.node_id,
                file=outcome.file,
                status=outcome.status,
                message=outcome.message,
            )
        )
    return tuple(accepted), tuple(failures)


def _acceptance_note(accepted: tuple[ExcludedTest, ...]) -> str:
    """The row's account of the witness cases it accepted, case by case.

    The case and the reason pytest recorded are both printed: an acceptance
    that does not say what it accepted is indistinguishable from a hole.
    """
    if not accepted:
        return ""
    parts: list[str] = []
    for category, label in _STANDING_LABEL.items():
        named = [e for e in accepted if e.category == category]
        if named:
            parts.append(
                f"This run accepted {len(named)} witness case(s) as {label}: "
                + "; ".join(f"{e.name} — {e.detail or 'no reason given'}" for e in named)
                + "."
            )
    return " " + " ".join(parts)


def blocker_results(
    protocol: Protocol, index: OutcomeIndex, *, repo_root: Path
) -> tuple[BlockerResult, ...]:
    """One row per Phase 1 blocker.

    **The rule.** A blocker is held when every one of its witnesses was
    collected **and passed**. A witness that was skipped is a witness that
    did not hold — unless §1.4.1b accepts the skip's reason, which is the
    ruling's other half and is what `_witness_cases` applies. A witness that
    was not part of the run at all cannot be evaluated, and a blocker that
    could not be evaluated has not held.

    **And the sixth blocker rules on the required tests themselves.** Its
    witnesses watch the mechanism, not the required tests, so a required test
    that was skipped would not show up in them. §1.4.1b's ruling is that a
    skip naming no standing category fails the blocker, and an accepted one
    is still named in the row: the exclusion is read out of the shard list,
    classified, and stated.
    """
    results: list[BlockerResult] = []
    for blocker in protocol.blockers:
        witnesses = manifest.BLOCKER_WITNESSES.get(blocker.key, ())
        excluded: tuple[ExcludedTest, ...] = ()
        excluded_note = ""
        if blocker.key == SKIPPED_TESTS_BLOCKER:
            excluded = _excluded_required_tests(index, repo_root)
            excluded_note = _exclusion_note(excluded)
        refused = tuple(e for e in excluded if e.category == UNDECLARED)
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
        accepted, failures = _witness_cases(outcomes)
        witness_note = _acceptance_note(accepted)
        if refused:
            results.append(
                BlockerResult(
                    key=blocker.key,
                    text=blocker.text,
                    witnesses=witnesses,
                    status="FAILED",
                    failures=failures,
                    reason=(
                        f"{len(refused)} required CI test(s) the run skipped for "
                        "a reason that names no standing category, which is what "
                        "this blocker watches"
                        + (
                            "; its witnesses were also not part of this run: " + ", ".join(missing)
                            if missing
                            else ""
                        )
                        + witness_note
                        + excluded_note
                    ),
                )
            )
            continue
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
                        "blocker could not be evaluated: "
                        + ", ".join(missing)
                        + witness_note
                        + excluded_note
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
                        "not pass; a case that did not pass counts against the "
                        "blocker unless §1.4.1b accepts it" + witness_note + excluded_note
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
                reason=(
                    "every witness was collected and passed"
                    + (
                        f" ({len(accepted)} witness case(s) skipped for a reason "
                        "this harness's ruling accepts)"
                        if accepted
                        else ""
                    )
                    + witness_note
                    + excluded_note
                ),
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
