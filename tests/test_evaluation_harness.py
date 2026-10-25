"""The evaluation harness, watched.

**What this file is for.** ``tests/evaluation/`` is a **mechanism**: it
partitions the repository's test files, runs them, reads the outcomes and
reports them with their denominators. A mechanism that nobody watches can
be neutered, and then the tree stays green while the evaluation stops
measuring anything. That is the same shape as F30, and the repository has
paid for it once.

So every claim the harness makes about itself is watched here, and each
test names the property it holds:

* **The partition is complete.** Every ``tests/test_*.py`` is filed under
  exactly one gate class, and every file the partition names exists. A test
  file that is in no class is a file whose cases enter no denominator, and
  that is the hole the harness exists to close — so the hole is closed by a
  test, not by a convention.
* **The partition agrees with the repository's own markers.** 33 files
  declare ``unit``, ``integration`` or ``e2e``; where a file declares one,
  the partition may not contradict it.
* **The protocol is read, not restated.** The parser finds the protocol's
  five gate classes, its metrics and its blockers, and refuses a protocol
  that is not there — a parser that returned nothing would make the harness
  report an empty, green run.
* **A skip is not a pass.** The protocol's sixth Phase 1 blocker names
  *"Required CI tests [that] are skipped"*; a skipped witness therefore
  fails its blocker, and a witness that did not run leaves the blocker
  unevaluated rather than held.
* **Every number carries its denominator**, and a class that collected
  nothing has **no rate** rather than a rate of zero.
* **The corpus measurement agrees with the committed answer key**, counted
  a second time here.
* **The comparison refuses a baseline that is not like-for-like**, and the
  rendered comparison carries no winner's language.
* **The real-model smoke is reported as not run**, with its reason, and is
  never counted as a pass.

**What this file does not do.** It does not run the suite. The harness's
own end-to-end path is exercised over **one small file** — the whole point
of a witness is to fail for the property it holds, and a witness that takes
twenty minutes is a witness nobody runs.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Final

import pytest
from evaluation import manifest
from evaluation.aggregate import (
    blocker_results,
    class_result,
    index_outcomes,
    metric_rows,
)
from evaluation.cli import EXIT_FAILED, EXIT_NOT_RUN, EXIT_OK, main
from evaluation.comparison import (
    ComparisonBasis,
    assess,
    load_baseline,
    pairs,
)
from evaluation.corpus import measure_corpus
from evaluation.junit import parse_junit
from evaluation.model import (
    ERRORED,
    FAILED,
    PASSED,
    SKIPPED,
    XFAIL,
    ClassResult,
    EvaluationRun,
    Measurement,
    TestOutcome,
)
from evaluation.protocol import parse_protocol, protocol_path
from evaluation.report import RANKING_WORDS, render_json, render_markdown
from evaluation.runner import ClassRun, run_class

#: The file the end-to-end path is exercised over. It is small, it is fast,
#: and it passes in a clean checkout — so a red result means the harness
#: broke, not that the file did.
SMOKE_FILE: Final = "test_scaffolding.py"

#: The marker a file may declare, and the gate class each one names.
MARKER_CLASSES: Final[dict[str, str]] = {
    "unit": "unit",
    "integration": "integration",
    "e2e": "e2e",
}


def _protocol(repo_root: Path) -> Any:
    """The protocol, parsed."""
    return parse_protocol(
        protocol_path(repo_root),
        manifest.METRIC_PREFIXES,
        manifest.BLOCKER_PREFIXES,
        manifest.OFFLINE_CLASSES,
    )


# --------------------------------------------------------------------------
# The partition
# --------------------------------------------------------------------------


def test_the_partition_files_every_test_file_exactly_once(repo_root: Path) -> None:
    """No test file is in no class, and none is in two.

    A file that is in no class is a test CI never runs **and** a test whose
    cases enter no denominator of this evaluation — the same hole, twice.
    The partition is a dictionary, so "twice" cannot happen by accident; the
    check is that the two sides agree.
    """
    files = {path.name for path in (repo_root / "tests").glob("test_*.py")}
    assigned = set(manifest.FILE_ASSIGNMENTS)
    assert assigned == files, (
        "these test files are in no gate class, so their cases enter no "
        f"denominator: {sorted(files - assigned)}; and these are filed but "
        f"do not exist: {sorted(assigned - files)}"
    )
    assert len(manifest.FILE_ASSIGNMENTS) == len(files)


def test_every_file_the_partition_names_exists(repo_root: Path) -> None:
    """A filed file that is not there is a class that quietly runs less."""
    for name in manifest.FILE_ASSIGNMENTS:
        assert (repo_root / "tests" / name).is_file(), (
            f"the partition files {name}, which is not in the tree"
        )


def test_the_partition_agrees_with_the_markers_a_file_declares(repo_root: Path) -> None:
    """Where a file declares a marker, the partition may not contradict it.

    The markers are the repository's own statement about what a file is,
    and 33 files make one. The partition is allowed to choose between two
    declared classes; it is not allowed to put a file in a class its own
    markers rule out. That is the check that catches a misclassification
    before it reaches a report.
    """
    for name, (class_key, _clause) in manifest.FILE_ASSIGNMENTS.items():
        text = (repo_root / "tests" / name).read_text(encoding="utf-8")
        declared = set(re.findall(r"pytest\.mark\.(unit|integration|e2e)\b", text))
        if not declared:
            continue
        allowed = {MARKER_CLASSES[marker] for marker in declared}
        assert class_key in allowed, (
            f"{name} declares {sorted(declared)} and the partition files it "
            f"under {class_key!r}, which its own markers rule out"
        )


def test_every_clause_the_partition_names_is_in_the_vocabulary() -> None:
    """A clause outside the vocabulary is a clause the report cannot place."""
    for name, (_class_key, clause) in manifest.FILE_ASSIGNMENTS.items():
        assert clause in manifest.CLAUSES, (
            f"{name} is filed under the clause {clause!r}, which the "
            "harness's clause vocabulary does not name"
        )


def test_the_repository_class_is_not_one_of_the_protocols_five() -> None:
    """The repository's own gates are reported separately from the protocol's.

    Counting them into a class the protocol did not name would inflate that
    class's denominator with checks the protocol never asked for.
    """
    assert manifest.REPOSITORY_CLASS not in manifest.PROTOCOL_CLASS_KEYS
    assert set(manifest.PROTOCOL_CLASS_KEYS) == {
        "unit",
        "integration",
        "negative",
        "e2e",
        "real_model_smoke",
    }


# --------------------------------------------------------------------------
# The protocol
# --------------------------------------------------------------------------


def test_the_parser_reads_the_protocol(repo_root: Path) -> None:
    """The protocol's classes, metrics and blockers are found.

    A parser that returned nothing would make the harness report an empty,
    green run — the worst possible failure for a tool whose job is to
    report honestly.
    """
    protocol = _protocol(repo_root)
    assert [gate.key for gate in protocol.gate_classes] == list(manifest.PROTOCOL_CLASS_KEYS)
    assert len(protocol.metrics) >= 7
    assert len(protocol.blockers) >= 6
    assert "Do not claim superiority" in protocol.superiority_clause
    assert "Results are benchmarks only when" in protocol.benchmark_clause
    for gate in protocol.gate_classes:
        assert gate.definition, f"the {gate.label} class has no definition"


def test_the_parser_refuses_a_protocol_that_is_not_there(tmp_path: Path) -> None:
    """A document without the protocol's sections is an error, not an empty result."""
    missing = tmp_path / "EVALUATION.md"
    missing.write_text("# Something else\n\nNo sections here.\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Mandatory automated gates"):
        parse_protocol(
            missing,
            manifest.METRIC_PREFIXES,
            manifest.BLOCKER_PREFIXES,
            manifest.OFFLINE_CLASSES,
        )


def test_the_parser_refuses_an_item_it_has_no_witness_key_for(tmp_path: Path) -> None:
    """A protocol item with no witness key is an error, not a silent omission."""
    protocol_text = protocol_path(Path(__file__).resolve().parent.parent).read_text(
        encoding="utf-8"
    )
    grown = protocol_text.replace(
        "- End-to-end task success (successful verified deliveries / attempted tasks).",
        "- End-to-end task success (successful verified deliveries / attempted tasks).\n"
        "- A metric the harness has never heard of.",
    )
    grown_path = tmp_path / "EVALUATION.md"
    grown_path.write_text(grown, encoding="utf-8")
    with pytest.raises(ValueError, match="witness key"):
        parse_protocol(
            grown_path,
            manifest.METRIC_PREFIXES,
            manifest.BLOCKER_PREFIXES,
            manifest.OFFLINE_CLASSES,
        )


def test_every_metric_the_protocol_names_has_witnesses(repo_root: Path) -> None:
    """A metric with no witness is a metric this repository does not check."""
    protocol = _protocol(repo_root)
    for metric in protocol.metrics:
        assert metric.key in manifest.METRIC_WITNESSES, (
            f"the protocol's metric {metric.text!r} has no witnesses"
        )
    for key in manifest.METRIC_WITNESSES:
        assert any(metric.key == key for metric in protocol.metrics), (
            f"the manifest has witnesses for {key!r}, which the protocol does not name"
        )


def test_every_blocker_the_protocol_names_has_witnesses(repo_root: Path) -> None:
    """A blocker with no witness is a blocker nobody is watching."""
    protocol = _protocol(repo_root)
    for blocker in protocol.blockers:
        assert blocker.key in manifest.BLOCKER_WITNESSES, (
            f"the protocol's blocker {blocker.text!r} has no witnesses"
        )
    for key in manifest.BLOCKER_WITNESSES:
        assert any(blocker.key == key for blocker in protocol.blockers), (
            f"the manifest has witnesses for {key!r}, which the protocol does not name"
        )


def test_every_witness_file_is_one_the_partition_files(repo_root: Path) -> None:
    """A witness outside the partition would never run, and would look like a pass."""
    for group in (manifest.METRIC_WITNESSES, manifest.BLOCKER_WITNESSES):
        for key, witnesses in group.items():
            for witness in witnesses:
                assert witness in manifest.FILE_ASSIGNMENTS, (
                    f"{key} names the witness {witness}, which the partition does not file"
                )


# --------------------------------------------------------------------------
# The runner and the JUnit reader
# --------------------------------------------------------------------------


def test_a_real_pytest_run_is_read_as_outcomes(repo_root: Path, tmp_path: Path) -> None:
    """The runner and the JUnit reader work on a real pytest run.

    The whole end-to-end path is exercised over one small file: the
    subprocess, the JUnit XML it writes, the parser that reads it, and the
    class result built from it. The denominator has to be the number of
    cases pytest actually collected.
    """
    import tempfile

    run = run_class(
        repo_root,
        "unit",
        (f"tests/{SMOKE_FILE}",),
        Path(tempfile.gettempdir()),
    )
    assert run.ran, f"the run did not happen: {run.error}"
    assert run.outcomes, "the run collected nothing"
    assert all(outcome.passed for outcome in run.outcomes), (
        f"the smoke file did not pass: "
        f"{[outcome.node_id for outcome in run.outcomes if not outcome.passed]}"
    )
    assert all(outcome.file.endswith(SMOKE_FILE) for outcome in run.outcomes)
    assert {outcome.status for outcome in run.outcomes} == {PASSED}


def test_the_junit_reader_tells_a_skip_from_an_expected_failure(tmp_path: Path) -> None:
    """A ``pytest.skip`` and an ``xfail`` are both ``<skipped>`` elements.

    Conflating them is a lie in one direction or the other: a required test
    that did not run is not a test that failed the way it was declared it
    would, and the protocol's sixth blocker is about the first.
    """
    xml = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="5">
  <testcase classname="test_x" name="test_passed" time="0.001"/>
  <testcase classname="test_x" name="test_failed" time="0.001">
    <failure message="assert 1 == 2">long traceback</failure>
  </testcase>
  <testcase classname="test_x" name="test_errored" time="0.001">
    <error message="boom">the traceback</error>
  </testcase>
  <testcase classname="test_x" name="test_skipped" time="0.001">
    <skipped type="pytest.skip" message="no credential"/>
  </testcase>
  <testcase classname="test_x" name="test_xfailed" time="0.001">
    <skipped type="pytest.xfail" message="known failure"/>
  </testcase>
</testsuite></testsuites>
"""
    path = tmp_path / "junit.xml"
    path.write_text(xml, encoding="utf-8")
    outcomes = {outcome.node_id.split("::")[-1]: outcome for outcome in parse_junit(path)}
    assert outcomes["test_passed"].status == PASSED
    assert outcomes["test_failed"].status == FAILED
    assert outcomes["test_errored"].status == ERRORED
    assert outcomes["test_skipped"].status == SKIPPED
    assert outcomes["test_xfailed"].status == XFAIL
    assert outcomes["test_failed"].message == "assert 1 == 2"


def test_the_junit_reader_refuses_a_report_that_is_not_there(tmp_path: Path) -> None:
    """A missing report is an error, not an empty result.

    An empty result would report a class of zero collected tests, which
    reads as "the class ran and found nothing" — the shape of a hole.
    """
    with pytest.raises(FileNotFoundError):
        parse_junit(tmp_path / "absent.xml")


def test_the_runner_refuses_a_temporary_directory_inside_the_repository(
    repo_root: Path,
) -> None:
    """A temporary directory inside the checkout makes the run depend on the tree.

    The repository's own rules are explicit about it, and two of its tests
    enforce it. The harness runs the whole suite, so it would inherit the
    failure — and it would leave the checkout dirty.
    """
    inside = repo_root / ".local" / "tmp-inside"
    inside.mkdir(parents=True, exist_ok=True)
    try:
        with pytest.raises(ValueError, match="inside the repository"):
            run_class(repo_root, "unit", (f"tests/{SMOKE_FILE}",), repo_root)
    finally:
        inside.rmdir()


# --------------------------------------------------------------------------
# The blocker rule
# --------------------------------------------------------------------------


def _outcome(file: str, name: str, status: str) -> TestOutcome:
    """One synthetic outcome."""
    return TestOutcome(
        file=file,
        node_id=f"{file}::{name}",
        status=status,
        duration_seconds=0.0,
        message="" if status == PASSED else "it did not pass",
    )


def _blockers_with(outcomes: list[TestOutcome], ran: set[str]) -> list[Any]:
    """The blocker results for a synthetic run."""
    runs = (
        ClassRun(
            key="negative",
            files=tuple(ran),
            outcomes=tuple(outcomes),
            exit_code=0,
            duration_seconds=0.0,
            stdout="",
            stderr="",
        ),
    )
    protocol = _protocol(Path(__file__).resolve().parent.parent)
    return list(blocker_results(protocol, index_outcomes(runs)))


#: The blocker the three cases below are about, and its witnesses.
CITATION_BLOCKER: Final = "no-fake-citation-or-unsupported-number"


def _citation_witnesses() -> tuple[str, ...]:
    """Every witness of the citation blocker."""
    return manifest.BLOCKER_WITNESSES[CITATION_BLOCKER]


def test_a_skipped_witness_fails_its_blocker() -> None:
    """A required test that did not run is a blocker that did not hold.

    The protocol's sixth blocker names exactly this: *"Required CI tests
    [that] are skipped, ignored or only pass by mocking the actual behavior
    under acceptance"*. A skip is not neutral.
    """
    witnesses = _citation_witnesses()
    outcomes = [
        _outcome(name, "test_one", SKIPPED if index == 0 else PASSED)
        for index, name in enumerate(witnesses)
    ]
    blockers = _blockers_with(outcomes, set(witnesses))
    blocker = next(b for b in blockers if b.key == CITATION_BLOCKER)
    assert blocker.status == "FAILED"
    assert [case.status for case in blocker.failures] == [SKIPPED]


def test_a_failed_witness_fails_its_blocker() -> None:
    """A failing witness fails its blocker, and the case is listed."""
    witnesses = _citation_witnesses()
    outcomes = [
        _outcome(name, "test_one", FAILED if index == 0 else PASSED)
        for index, name in enumerate(witnesses)
    ]
    blockers = _blockers_with(outcomes, set(witnesses))
    blocker = next(b for b in blockers if b.key == CITATION_BLOCKER)
    assert blocker.status == "FAILED"
    assert len(blocker.failures) == 1


def test_a_witness_that_did_not_run_leaves_the_blocker_unevaluated() -> None:
    """A blocker that could not be evaluated has not held.

    "Not run" and "passed" are different facts, and the report has to tell
    them apart: a blocker that is neither is not a blocker that held.
    """
    blockers = _blockers_with([], set())
    blocker = next(b for b in blockers if b.key == CITATION_BLOCKER)
    assert blocker.status == "NOT_EVALUATED"
    assert not blocker.held
    assert "not part of this run" in blocker.reason


def test_a_blocker_whose_witnesses_all_passed_holds() -> None:
    """The positive case, so the three above are not passing vacuously."""
    witnesses = _citation_witnesses()
    outcomes = [_outcome(name, "test_one", PASSED) for name in witnesses]
    blockers = _blockers_with(outcomes, set(witnesses))
    blocker = next(b for b in blockers if b.key == CITATION_BLOCKER)
    assert blocker.status == "HELD"
    assert blocker.held


# --------------------------------------------------------------------------
# The denominators
# --------------------------------------------------------------------------


def test_a_class_that_collected_nothing_has_no_rate() -> None:
    """No cases is not zero cases.

    A rate of zero says "every case failed"; a class that collected nothing
    has no rate at all, and the difference is the difference between "the
    class failed" and "the class never ran".
    """
    result = ClassResult(
        key="unit",
        title="Unit",
        definition="...",
        files=(),
        outcomes=(),
        duration_seconds=0.0,
    )
    assert result.collected == 0
    assert result.pass_rate is None
    assert not result.denominator_is_small


def test_a_small_denominator_is_said_so() -> None:
    """A rate over a handful of cases is called small, in the row itself."""
    from evaluation.model import SMALL_DENOMINATOR

    outcomes = [_outcome("tests/test_a.py", f"test_{index}", PASSED) for index in range(3)]
    small = ClassResult(
        key="unit",
        title="Unit",
        definition="...",
        files=("tests/test_a.py",),
        outcomes=tuple(outcomes),
        duration_seconds=0.0,
    )
    assert small.denominator_is_small
    assert small.collected < SMALL_DENOMINATOR

    many = ClassResult(
        key="unit",
        title="Unit",
        definition="...",
        files=("tests/test_a.py",),
        outcomes=tuple(
            _outcome("tests/test_a.py", f"test_{index}", PASSED)
            for index in range(SMALL_DENOMINATOR)
        ),
        duration_seconds=0.0,
    )
    assert not many.denominator_is_small


def test_the_report_carries_the_denominators() -> None:
    """The rendered report states each rate as numerator over denominator.

    A rate whose denominator is not on the page is a rate a reader cannot
    check, and the protocol asks for transparent denominators.
    """
    outcomes = [
        _outcome("tests/test_a.py", "test_one", PASSED),
        _outcome("tests/test_a.py", "test_two", PASSED),
        _outcome("tests/test_a.py", "test_three", FAILED),
    ]
    protocol = _protocol(Path(__file__).resolve().parent.parent)
    runs = (
        ClassRun(
            key="unit",
            files=("tests/test_a.py",),
            outcomes=tuple(outcomes),
            exit_code=1,
            duration_seconds=1.0,
            stdout="",
            stderr="",
        ),
    )
    result = class_result(protocol.gate_class("unit"), runs[0])
    index = index_outcomes(runs)
    evaluation = EvaluationRun(
        repo_root="/tmp/repo",
        revision="abc123",
        protocol_path="docs/EVALUATION.md",
        classes=(result,),
        blockers=blocker_results(protocol, index),
        metrics=metric_rows(protocol, index, (result,), None, 1.0),
        comparison=assess(
            ComparisonBasis(label="this run"),
            ComparisonBasis(label="baseline"),
        ),
        duration_seconds=1.0,
        command="python -m tests.evaluation",
    )
    markdown = render_markdown(evaluation, protocol.benchmark_clause, protocol.superiority_clause)
    assert "2/3" in markdown
    assert "Collected (denominator)" in markdown
    assert "Passed (numerator)" in markdown
    assert "test_three" in markdown
    assert "failed" in markdown

    document = json.loads(
        render_json(evaluation, protocol.benchmark_clause, protocol.superiority_clause)
    )
    unit = document["classes"][0]
    assert unit["passed"] == 2
    assert unit["collected"] == 3
    assert unit["pass_rate"] == pytest.approx(2 / 3)
    assert unit["failures"][0]["node_id"].endswith("test_three")


# --------------------------------------------------------------------------
# The corpus measurement
# --------------------------------------------------------------------------


def _independent_cell_count(repo_root: Path) -> tuple[int, int]:
    """The corpus's addressed cells and its quantity cells, counted again.

    **Deliberately a second implementation.** The harness counts the cells
    with its own row reader; this counts them with a reader written here,
    so that a bug in the harness's reader shows up as a disagreement rather
    than as a quietly wrong denominator. The rule is small — a row
    specification is either a range string or a list of numbers — and it is
    exactly the kind of rule two readers should agree about.
    """
    addressed = 0
    quantities = 0
    for path in sorted((repo_root / "tests" / "fixtures" / "analysis").glob("*.expected.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        for selection in document.get("selections", []):
            expect = selection.get("expect", {})
            if expect.get("outcome") == "refused":
                continue
            rows = selection["rows"]
            if isinstance(rows, str):
                start, _, end = rows.partition("-")
                row_count = int(end) - int(start) + 1
            else:
                row_count = len(rows)
            cells = row_count * len(selection["columns"])
            addressed += cells
            unusable = (
                len(expect.get("absent") or [])
                + len(expect.get("empty") or [])
                + len(expect.get("not_a_quantity") or [])
            )
            quantities += cells - unusable
    return addressed, quantities


def test_the_corpus_measurement_agrees_with_the_committed_answer_key(
    repo_root: Path,
) -> None:
    """The measurement's denominator is the corpus's own, counted twice.

    The harness reads the answer key through the product's selection code;
    this counts the key's cells with a reader of its own. If the two
    disagree, the number in the report is wrong, and the report is the
    thing a reader trusts.
    """
    measurement = measure_corpus(repo_root)
    addressed, quantities = _independent_cell_count(repo_root)
    assert measurement.cells_addressed == addressed, (
        f"the harness counted {measurement.cells_addressed} cells and the "
        f"answer key holds {addressed}"
    )
    assert measurement.quantity_cells == quantities, (
        f"the harness counted {measurement.quantity_cells} quantity cells and "
        f"the answer key holds {quantities}"
    )
    assert measurement.quantity_cells_exact == quantities, (
        f"the harness read {measurement.quantity_cells_exact} quantity cells "
        f"as quantities and the answer key has {quantities}"
    )


def test_the_corpus_measurement_reports_no_failure(repo_root: Path) -> None:
    """Every cell is read exactly as the key says, and every refusal refuses.

    A failure here is a real finding: either the product reads a cell
    differently from the committed key, or the harness measures the wrong
    thing. Both are worth a red test.
    """
    measurement = measure_corpus(repo_root)
    assert measurement.failures == (), measurement.failures
    assert measurement.cells_exact == measurement.cells_addressed
    assert measurement.selections_unit_consistent == measurement.selections_with_units
    assert measurement.refusals_correct == measurement.refusals_expected
    assert measurement.cells_addressed > 0


# --------------------------------------------------------------------------
# The comparison
# --------------------------------------------------------------------------


def _matching_basis(label: str) -> ComparisonBasis:
    """A basis that satisfies every requirement."""
    return ComparisonBasis(
        label=label,
        fixture_labels=("fixture-a",),
        fixture_versions={"fixture-a": "v1"},
        model="model-x@1",
        budget="1.00 USD",
        verified_capabilities=("citation",),
        limitations="the sample is small",
    )


def test_a_like_for_like_baseline_is_comparable() -> None:
    """The positive case: everything the protocol names is present."""
    outcome = assess(_matching_basis("run"), _matching_basis("baseline"))
    assert outcome.comparable
    assert outcome.reasons == ()


@pytest.mark.parametrize(
    ("drop", "expected"),
    [
        ("verified_capabilities", "verified capabilities"),
        ("limitations", "confidence intervals nor limitations"),
    ],
)
def test_a_baseline_missing_a_requirement_is_refused(drop: str, expected: str) -> None:
    """A baseline that does not meet the protocol's rule is not compared.

    The protocol allows a comparison only with like-for-like matched tasks,
    verified capabilities **and** documented confidence intervals or
    limitations. Two of the three are enough to make it a comparison the
    protocol permits, and one of them is not.
    """
    baseline = _matching_basis("baseline")
    without = ComparisonBasis(
        label=baseline.label,
        fixture_labels=baseline.fixture_labels,
        fixture_versions=baseline.fixture_versions,
        model=baseline.model,
        budget=baseline.budget,
        verified_capabilities=(),
        limitations="",
    )
    if drop == "verified_capabilities":
        without = ComparisonBasis(
            label=baseline.label,
            fixture_labels=baseline.fixture_labels,
            fixture_versions=baseline.fixture_versions,
            model=baseline.model,
            budget=baseline.budget,
            verified_capabilities=(),
            limitations=baseline.limitations,
        )
    outcome = assess(_matching_basis("run"), without)
    assert not outcome.comparable
    assert any(expected in reason for reason in outcome.reasons), outcome.reasons


def test_a_baseline_on_different_tasks_is_refused() -> None:
    """Matched tasks are the first requirement, and it is not optional."""
    baseline = ComparisonBasis(
        label="baseline",
        fixture_labels=("fixture-b",),
        fixture_versions={"fixture-b": "v1"},
        model="model-x@1",
        budget="1.00 USD",
        verified_capabilities=("citation",),
        limitations="small sample",
    )
    outcome = assess(_matching_basis("run"), baseline)
    assert not outcome.comparable
    assert any("not matched" in reason for reason in outcome.reasons)


def test_the_comparison_prints_pairs_and_never_a_verdict() -> None:
    """The structure stops a ranking, not a disclaimer.

    The protocol forbids claiming superiority without like-for-like matched
    tasks, and the output has no aggregate for a reader to be handed: it
    prints one metric at a time.
    """
    outcome = assess(_matching_basis("run"), _matching_basis("baseline"))
    assert outcome.comparable
    printed = pairs({"a": (10, 10), "b": (1, 2)}, {"a": (9, 10), "b": (2, 2)})
    assert printed == (("a", "10/10 against 9/10"), ("b", "1/2 against 2/2"))
    assert len(printed) == 2


def test_the_rendered_comparison_carries_no_winners_language() -> None:
    """The report's comparison section names no winner.

    The watch is on the **rendered** text, not on the intent: a section
    that says "better" is a section that has claimed something, however
    carefully the code meant it.
    """
    protocol = _protocol(Path(__file__).resolve().parent.parent)
    index = index_outcomes(())
    evaluation = EvaluationRun(
        repo_root="/tmp/repo",
        revision="abc123",
        protocol_path="docs/EVALUATION.md",
        classes=(),
        blockers=(),
        metrics=metric_rows(protocol, index, (), None, 0.0),
        comparison=assess(_matching_basis("run"), _matching_basis("baseline")),
        duration_seconds=0.0,
        command="python -m tests.evaluation",
    )
    markdown = render_markdown(evaluation, protocol.benchmark_clause, protocol.superiority_clause)
    section = markdown.split("## The comparison", 1)[1].split("\n## ", 1)[0]
    lowered = section.lower()
    for word in RANKING_WORDS:
        assert word not in lowered, f"the comparison section says {word!r}"


def test_a_baseline_document_is_read_with_its_numbers(tmp_path: Path) -> None:
    """A baseline file carries its basis and its numbers.

    The numbers are only ever printed if the basis matched, so reading them
    is not the same as comparing them.
    """
    path = tmp_path / "baseline.json"
    path.write_text(
        json.dumps(
            {
                "label": "model without the evidence workflow",
                "fixtures": {"names": ["fixture-a"], "versions": {"fixture-a": "v1"}},
                "model": {"name": "model-x", "version": "1"},
                "budget": "1.00 USD",
                "verified_capabilities": ["citation"],
                "limitations": "the sample is small",
                "metrics": {"numeric-extraction-exactness": {"numerator": 9, "denominator": 10}},
            }
        ),
        encoding="utf-8",
    )
    document = load_baseline(path)
    assert document.basis.label == "model without the evidence workflow"
    assert document.basis.fixture_labels == ("fixture-a",)
    assert document.metrics == {"numeric-extraction-exactness": (9, 10)}


# --------------------------------------------------------------------------
# The real-model smoke
# --------------------------------------------------------------------------


def test_the_real_model_smoke_is_reported_as_not_run_with_its_reason() -> None:
    """The class that needs a credential says so, and says why.

    The protocol requires *"at least one real supported provider under
    declared model/version/parameters"*, and there is no credential for
    one. The report has to say that, in the class's own words — not to
    report it as a class that ran and passed.
    """
    protocol = _protocol(Path(__file__).resolve().parent.parent)
    smoke = protocol.gate_class("real_model_smoke")
    assert not smoke.runnable_offline
    assert "real supported provider" in smoke.offline_reason
    assert "mock-only success is insufficient" in smoke.offline_reason


def test_the_real_model_smoke_is_not_counted_as_a_pass() -> None:
    """A class that did not run has no rate, and is not a pass.

    The exit code is where this shows: a run whose selected class could
    not be run exits 2, not 0.
    """
    from evaluation.cli import _exit_code

    evaluation = EvaluationRun(
        repo_root="/tmp/repo",
        revision="abc123",
        protocol_path="docs/EVALUATION.md",
        classes=(
            ClassResult(
                key="real_model_smoke",
                title="Real-model smoke",
                definition="...",
                files=(),
                outcomes=(),
                duration_seconds=0.0,
                ran=False,
                not_run_reason="no credential",
            ),
        ),
        blockers=(),
        metrics=(),
        comparison=assess(ComparisonBasis(label="run"), ComparisonBasis(label="baseline")),
        duration_seconds=0.0,
    )
    assert _exit_code(evaluation) == EXIT_NOT_RUN


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------


def test_the_command_lists_the_partition(capsys: pytest.CaptureFixture[str]) -> None:
    """``--list`` prints the partition and runs nothing."""
    assert main(["--list"]) == EXIT_OK
    printed = capsys.readouterr().out
    assert "unit" in printed
    assert "real_model_smoke" in printed
    assert SMOKE_FILE in printed


def test_the_command_refuses_a_class_it_does_not_know() -> None:
    """An unknown class is refused rather than silently ignored."""
    with pytest.raises(SystemExit, match="not classes this harness knows"):
        main(["--classes", "nonsense"])


def test_the_command_writes_a_report_and_says_what_it_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The command's whole path, with the run stubbed out.

    The real runner is exercised over one file elsewhere in this file; what
    this test covers is the orchestration — the protocol is parsed, the
    classes are selected, the results are aggregated, the report is written
    and the exit code speaks about what was found.
    """
    from evaluation import cli

    def fake_run_class(
        repo_root: Path,
        key: str,
        files: tuple[str, ...],
        temp_root: Path,
        **kwargs: Any,
    ) -> ClassRun:
        return ClassRun(
            key=key,
            files=files,
            outcomes=tuple(
                _outcome(f"tests/{name}", f"test_{index}", PASSED)
                for index, name in enumerate(files)
            ),
            exit_code=0,
            duration_seconds=0.1,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(cli, "run_class", fake_run_class)
    out = tmp_path / "report"
    code = main(
        [
            "--out",
            str(out),
            "--classes",
            "unit,integration,negative,e2e,repository",
        ]
    )
    markdown = (out / "evaluation-report.md").read_text(encoding="utf-8")
    document = json.loads((out / "evaluation-report.json").read_text(encoding="utf-8"))
    assert "## The gate classes" in markdown
    assert "NOT SELECTED" in markdown
    assert document["classes"]
    assert any(not entry["ran"] for entry in document["classes"])
    # The real-model smoke was not selected, so the run speaks only about
    # what was selected — and the comparison says no comparison was made.
    assert code in (EXIT_OK, EXIT_FAILED)


def test_the_command_reports_the_classes_it_could_not_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Selecting the real-model smoke reports it as NOT RUN and exits 2.

    The default selection includes it, so the default run says the truth
    about the protocol not being satisfied: the tool did its job and the
    protocol is still unmet, because there is no credential for a real
    provider.
    """
    from evaluation import cli

    def fake_run_class(
        repo_root: Path,
        key: str,
        files: tuple[str, ...],
        temp_root: Path,
        **kwargs: Any,
    ) -> ClassRun:
        return ClassRun(
            key=key,
            files=files,
            outcomes=(),
            exit_code=0,
            duration_seconds=0.0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(cli, "run_class", fake_run_class)
    out = tmp_path / "report"
    code = main(["--out", str(out), "--classes", "real_model_smoke"])
    markdown = (out / "evaluation-report.md").read_text(encoding="utf-8")
    assert code == EXIT_NOT_RUN
    assert "NOT RUN" in markdown
    assert "real supported provider" in markdown


def test_the_report_and_the_json_say_the_same_thing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both renderings come from one run, and neither is derived from the other.

    A reader reads the Markdown and a machine reads the JSON; if they could
    disagree, one of them would be a fact the other does not carry.
    """
    from evaluation import cli

    def fake_run_class(
        repo_root: Path,
        key: str,
        files: tuple[str, ...],
        temp_root: Path,
        **kwargs: Any,
    ) -> ClassRun:
        return ClassRun(
            key=key,
            files=files,
            outcomes=tuple(
                _outcome(f"tests/{name}", f"test_{index}", PASSED)
                for index, name in enumerate(files)
            ),
            exit_code=0,
            duration_seconds=0.1,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(cli, "run_class", fake_run_class)
    out = tmp_path / "report"
    main(["--out", str(out), "--classes", "unit"])
    markdown = (out / "evaluation-report.md").read_text(encoding="utf-8")
    document = json.loads((out / "evaluation-report.json").read_text(encoding="utf-8"))
    unit = next(entry for entry in document["classes"] if entry["key"] == "unit")
    expected = len(manifest.files_for_class("unit"))
    assert unit["collected"] == expected
    assert f"{unit['passed']}/{unit['collected']}" in markdown
    assert document["benchmark_clause"]
    assert document["superiority_clause"]


def test_the_measurement_carries_its_denominator_and_its_reason() -> None:
    """A measurement that is not a number says why, and says so in the model."""
    measured = Measurement(status="MEASURED", numerator=3, denominator=4, how="cells")
    assert measured.measured
    assert measured.rate == pytest.approx(0.75)
    assert measured.denominator_is_small

    missing = Measurement(status="NOT_MEASURED", reason="no corpus in this tree")
    assert not missing.measured
    assert missing.rate is None
    assert missing.reason == "no corpus in this tree"


def test_the_harness_runs_on_the_pinned_interpreter() -> None:
    """The harness runs under the interpreter the project pins.

    It reads a protocol, imports the product's own selection code and runs
    pytest as a subprocess; on the wrong interpreter the imports fail and
    the failure looks like a broken harness rather than a broken machine.
    """
    assert sys.version_info >= (3, 12), (
        "the harness uses PEP 695 type syntax and the project's pinned "
        f"interpreter; this is {sys.version_info}"
    )
