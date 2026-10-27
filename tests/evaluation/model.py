"""The shapes the harness reports in.

**Why these are dataclasses and not dictionaries.** A report is read by
people, and the failure this module is shaped against is a report that says
``{"passed": 12, "total": 12}`` where "total" could be the number of test
cases, the number of files, or the number of assertions. A number whose
denominator is ambiguous is a number that cannot be checked, and the
protocol's whole instruction is that denominators be *transparent*.

So every count in here has a name that says what it counts, and every rate
is a method that names both ends:

* :attr:`ClassResult.collected` — test cases pytest collected.
* :attr:`ClassResult.passed` — test cases that passed.
* :meth:`ClassResult.pass_rate` — ``passed / collected``, or ``None`` when
  nothing was collected, because a rate over no cases is not zero.

**A zero is not the same as an absence.** The repository's own usage module
makes this point about a provider that reports no cost, and the same
distinction runs through here: a class that was not run has no denominator
at all, and its report row says NOT RUN rather than showing a rate of zero,
which would read as a class that ran and failed everything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

#: A denominator below this is called small in the report.
#:
#: The threshold is a judgement, and it is recorded here rather than
#: buried in the renderer so that a reader can argue with the number. Ten
#: is chosen because a rate over fewer than ten cases moves by more than a
#: tenth for a single case, so it is not a rate that means much on its own.
SMALL_DENOMINATOR: Final = 10

#: The outcome statuses the harness distinguishes.
PASSED: Final = "passed"
FAILED: Final = "failed"
ERRORED: Final = "errored"
SKIPPED: Final = "skipped"
XFAIL: Final = "xfail"

#: The statuses that are not a pass. A skipped test is one of them: the
#: protocol's sixth blocker names skipped required tests, and a skip is
#: never a pass.
NOT_PASSED: Final = frozenset({FAILED, ERRORED, SKIPPED, XFAIL})


@dataclass(frozen=True, slots=True)
class TestOutcome:
    """One collected test case and what happened to it."""

    #: pytest tries to collect this class as a test class because its name
    #: begins with ``Test``. It is a record of an outcome, not a test.
    __test__ = False

    #: The file the test lives in, relative to the repository root.
    file: str
    #: The test's node id, as pytest reports it.
    node_id: str
    #: One of :data:`PASSED`, :data:`FAILED`, :data:`ERRORED`,
    #: :data:`SKIPPED`, :data:`XFAIL`.
    status: str
    #: How long the case took, in seconds.
    duration_seconds: float
    #: The failure or skip message, when there was one.
    message: str = ""

    @property
    def passed(self) -> bool:
        """Whether the case passed."""
        return self.status == PASSED

    @property
    def skipped(self) -> bool:
        """Whether the case was skipped.

        An **expected** failure (``xfail``) is not a skip: the test ran and
        failed the way it was declared it would, and the repository's own
        contract is explicit that a provider's absent measurement is not a
        measurement of zero. The same reasoning applies here.
        """
        return self.status == SKIPPED


@dataclass(frozen=True, slots=True)
class FailureCase:
    """One test case that did not pass, and why."""

    #: The test's node id.
    node_id: str
    #: The file it lives in.
    file: str
    #: The status it ended with.
    status: str
    #: The message pytest recorded, trimmed.
    message: str


@dataclass(frozen=True, slots=True)
class ClassResult:
    """What one protocol gate class's run produced."""

    #: The class key, from the protocol.
    key: str
    #: The protocol's name for the class.
    title: str
    #: The protocol's own definition of the class.
    definition: str
    #: The files the class was run over.
    files: tuple[str, ...]
    #: Every collected case.
    outcomes: tuple[TestOutcome, ...]
    #: How long the class's run took, in seconds.
    duration_seconds: float
    #: Whether the class was run at all.
    ran: bool = True
    #: Whether the class was selected to be run.
    #:
    #: A class that was **not selected** is not the same as a class that
    #: **could not be run**. The first is the reader's choice and says
    #: nothing about the protocol; the second is a gap in the evidence, and
    #: it is the one that decides the exit code.
    selected: bool = True
    #: Why it was not run, when it was not.
    not_run_reason: str = ""

    @property
    def collected(self) -> int:
        """The number of test cases collected — the denominator."""
        return len(self.outcomes)

    @property
    def passed(self) -> int:
        """The number of test cases that passed — the numerator."""
        return sum(1 for outcome in self.outcomes if outcome.passed)

    @property
    def failed(self) -> int:
        """The number of test cases that failed."""
        return sum(1 for outcome in self.outcomes if outcome.status == FAILED)

    @property
    def errored(self) -> int:
        """The number of test cases that errored."""
        return sum(1 for outcome in self.outcomes if outcome.status == ERRORED)

    @property
    def skipped(self) -> int:
        """The number of test cases that were skipped."""
        return sum(1 for outcome in self.outcomes if outcome.skipped)

    @property
    def xfailed(self) -> int:
        """The number of test cases that failed as they were declared to."""
        return sum(1 for outcome in self.outcomes if outcome.status == XFAIL)

    @property
    def failures(self) -> tuple[FailureCase, ...]:
        """Every case that did not pass, listed.

        A failure that is averaged into a rate is a failure that is not
        reported, and the protocol asks for the failure cases themselves.
        """
        return tuple(
            FailureCase(
                node_id=outcome.node_id,
                file=outcome.file,
                status=outcome.status,
                message=outcome.message,
            )
            for outcome in self.outcomes
            if not outcome.passed
        )

    @property
    def pass_rate(self) -> float | None:
        """``passed / collected``, or ``None`` when nothing was collected."""
        if self.collected == 0:
            return None
        return self.passed / self.collected

    @property
    def denominator_is_small(self) -> bool:
        """Whether the denominator is small enough to say so."""
        return 0 < self.collected < SMALL_DENOMINATOR


@dataclass(frozen=True, slots=True)
class BlockerResult:
    """What one Phase 1 blocker's witnesses said."""

    #: The blocker's key.
    key: str
    #: The protocol's own wording of the blocker.
    text: str
    #: The files that witness it.
    witnesses: tuple[str, ...]
    #: ``HELD``, ``FAILED`` or ``NOT_EVALUATED``.
    status: str
    #: The cases that did not pass, when the blocker failed.
    failures: tuple[FailureCase, ...] = ()
    #: Why the blocker could not be evaluated, when it could not be.
    reason: str = ""

    @property
    def held(self) -> bool:
        """Whether the blocker held."""
        return self.status == "HELD"


@dataclass(frozen=True, slots=True)
class Measurement:
    """A number with its denominator, or the reason there is not one."""

    #: ``MEASURED`` or ``NOT_MEASURED``.
    status: str
    #: The numerator.
    numerator: int | None = None
    #: The denominator.
    denominator: int | None = None
    #: Exactly what the numerator and the denominator count.
    how: str = ""
    #: Why the number could not be produced.
    reason: str = ""

    @property
    def measured(self) -> bool:
        """Whether a number was produced."""
        return self.status == "MEASURED"

    @property
    def rate(self) -> float | None:
        """``numerator / denominator``, or ``None``."""
        if self.numerator is None or self.denominator is None:
            return None
        if self.denominator == 0:
            return None
        return self.numerator / self.denominator

    @property
    def denominator_is_small(self) -> bool:
        """Whether the denominator is small enough to say so."""
        return self.denominator is not None and 0 < self.denominator < SMALL_DENOMINATOR


@dataclass(frozen=True, slots=True)
class WorkingTree:
    """The tree the run was made against, as the report states it.

    **A revision names a commit, and a commit is not a working tree.** The
    report's ``revision`` is ``git rev-parse HEAD``, and it says nothing
    about the uncommitted changes that were on disk while the run happened.
    So a run over a dirty tree reported a number against a commit that did
    not contain it — and the number was off by whatever the uncommitted
    change did to the suite. The discipline this repository cares about most
    is that a number is anchored to the tree it was measured on, and a
    revision that names a commit the run did not measure is exactly the hole
    that discipline is about.

    So the state of the tree is reported with the revision, and a dirty tree
    is said to be dirty.
    """

    #: Whether the working tree held changes that are not in the commit.
    dirty: bool
    #: The files that were changed, in name order.
    changed: tuple[str, ...]
    #: What the report says about it.
    description: str


@dataclass(frozen=True, slots=True)
class MetricRow:
    """A metric and everything the report says about it."""

    #: The metric's key.
    key: str
    #: The protocol's own wording.
    text: str
    #: The metric's own value.
    value: Measurement
    #: The witness files.
    witnesses: tuple[str, ...]
    #: The witnesses' score.
    witness_score: Measurement
    #: The witness cases that did not pass.
    failures: tuple[FailureCase, ...] = ()
    #: Further measurements of the same metric, when the protocol's metric
    #: names more than one quantity in one bullet.
    also: tuple[Measurement, ...] = ()
    #: What else the run recorded about this metric — the model name, the
    #: dataset revision, the seeds, and the half of the metric that could
    #: not be measured.
    context: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ComparisonOutcome:
    """Whether a baseline may be compared against this run, and what was said."""

    #: Whether the comparison is like-for-like and may be printed.
    comparable: bool
    #: Why it may not, one reason per line.
    reasons: tuple[str, ...] = ()
    #: The per-metric differences, when the comparison is comparable.
    deltas: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class EvaluationRun:
    """The whole run: every class, every blocker, every metric."""

    #: The repository the run was made against.
    repo_root: str
    #: The commit the tree was at.
    revision: str
    #: The protocol's path.
    protocol_path: str
    #: The class results, in the protocol's order.
    classes: tuple[ClassResult, ...]
    #: The blocker results, in the protocol's order.
    blockers: tuple[BlockerResult, ...]
    #: The metric rows, in the protocol's order.
    metrics: tuple[MetricRow, ...]
    #: What the comparison section concluded.
    comparison: ComparisonOutcome
    #: How long the whole run took, in seconds.
    duration_seconds: float
    #: The command the harness was invoked with.
    command: str = ""
    #: The state of the working tree the run was made against, when the
    #: harness could read it.
    working_tree: WorkingTree | None = None
    #: Anything else the run wants to record.
    notes: tuple[str, ...] = field(default=())

    @property
    def every_class_ran(self) -> bool:
        """Whether every class in the protocol was run."""
        return all(result.ran for result in self.classes)

    @property
    def blockers_held(self) -> bool:
        """Whether every Phase 1 blocker held."""
        return all(blocker.held for blocker in self.blockers)

    @property
    def failures(self) -> tuple[FailureCase, ...]:
        """Every case that did not pass, across every class."""
        return tuple(case for result in self.classes for case in result.failures)
