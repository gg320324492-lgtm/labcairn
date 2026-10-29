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
  the partition may not contradict it. And the repository's own class holds
  the repository's own gates and nothing else, so a file that declares no
  marker cannot be moved into a protocol class and inflate its denominator.
* **The protocol is read, not restated.** The parser finds the protocol's
  five gate classes, its metrics and its blockers, and refuses a protocol
  that is not there — a parser that returned nothing would make the harness
  report an empty, green run. The same rule governs the reasons a metric
  was not measured: they are derived from the tree, so a reason cannot
  claim an input is missing while the tree holds it.
* **A skip is not a pass.** The protocol's sixth Phase 1 blocker names
  *"Required CI tests [that] are skipped"*; a skipped witness therefore
  fails its blocker, and a witness that did not run leaves the blocker
  unevaluated rather than held. §1.4.1b's ruling extends that to the required
  tests themselves: a required test that skipped for a reason naming no
  standing category **fails** the blocker, and the two standing categories —
  a platform or filesystem fact, and a class the owner ruled is discharged
  outside the offline run — are accepted **and still named**.
* **Every number carries its denominator**, and a class that collected
  nothing has **no rate** rather than a rate of zero. The recovery metric's
  denominator counts **crash points**, not collected cases.
* **The corpus measurement agrees with the committed answer key**, counted
  a second time here — and the **public fixture corpus** is measured too,
  so the protocol's abstention metric is measured over the corpus that
  makes abstention measurable.
* **The comparison refuses a baseline that is not like-for-like**, and the
  rendered comparison carries no winner's language.
* **The real-model smoke is reported as not run by default**, with its reason,
  and is never counted as a pass — and a reader who **names** it on the command
  line gets it run rather than refused, because a class that nothing can ever
  run is not a class that is skipped, it is a class that is unreachable.
* **The report names the tree it measured**, so a revision cannot stand in
  for a working tree that held changes the commit did not.

**What this file does not do.** It does not run the suite. The harness's
own end-to-end path is exercised over **one small file** — the whole point
of a witness is to fail for the property it holds, and a witness that takes
twenty minutes is a witness nobody runs.
"""

from __future__ import annotations

import ast
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
    MetricRow,
    TestOutcome,
)
from evaluation.protocol import parse_protocol, protocol_path
from evaluation.report import RANKING_WORDS, render_json, render_markdown
from evaluation.runner import ClassRun, run_class

#: The repository root, from this file's own location.
_ROOT: Final = Path(__file__).resolve().parent.parent

#: The file the end-to-end path is exercised over. It is small, it is fast,
#: and it passes in a clean checkout — so a red result means the harness
#: broke, not that the file did.
SMOKE_FILE: Final = "test_scaffolding.py"

#: The marker a file may declare, and the gate class each one names.
#:
#: ``requires_provider`` names the protocol's fifth class. Without it that class
#: was **unreachable by construction**: the check below forbids filing a file
#: that declares no marker, and the only markers the vocabulary held were the
#: four offline ones — so a real-provider probe could never be filed, which is
#: one of the reasons the class sat for two gates naming a witness file that did
#: not exist.
MARKER_CLASSES: Final[dict[str, str]] = {
    "unit": "unit",
    "integration": "integration",
    "negative": "negative",
    "e2e": "e2e",
    "requires_provider": "real_model_smoke",
}

#: What a declared marker looks like. One pattern, read by both checks below, so
#: the two cannot drift into different definitions of the same word.
MARKER_PATTERN: Final = re.compile(
    r"pytest\.mark\.(unit|integration|negative|e2e|requires_provider)\b"
)


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
    and every file in a protocol class makes one. The partition is allowed
    to choose between two declared classes; it is not allowed to put a
    file in a class its own markers rule out. That is the check that
    catches a misclassification before it reaches a report.
    """
    for name, (class_key, _clause) in manifest.FILE_ASSIGNMENTS.items():
        text = (repo_root / "tests" / name).read_text(encoding="utf-8")
        declared = set(MARKER_PATTERN.findall(text))
        if not declared:
            continue
        allowed = {MARKER_CLASSES[marker] for marker in declared}
        assert class_key in allowed, (
            f"{name} declares {sorted(declared)} and the partition files it "
            f"under {class_key!r}, which its own markers rule out"
        )


def test_a_file_that_declares_no_protocol_marker_is_in_no_protocol_class(
    repo_root: Path,
) -> None:
    """A file that says nothing about its class may not be filed into one.

    The markers are the file's own statement of what it is, and they are
    the only thing outside the partition table that says so. A file that
    declares none has said nothing — and a class is a statement about the
    protocol's denominator, so **a file that has said nothing may not be
    filed into one.**

    **This is the anchor the table could not be.** The clause beside the
    class is prose, and prose that nothing checks is not a bound: the same
    edit that moves a file into a protocol class can move the clause with
    it, and the class judgement then follows. **The marker is a different
    field, in a different file**, and this check reads the file rather
    than the table — which is the shape the answer key's second fix used,
    and the shape the first one did not.
    """
    for name, (class_key, _clause) in manifest.FILE_ASSIGNMENTS.items():
        text = (repo_root / "tests" / name).read_text(encoding="utf-8")
        declared = set(MARKER_PATTERN.findall(text))
        if class_key == manifest.REPOSITORY_CLASS:
            assert not declared, (
                f"{name} is filed under the repository class and declares "
                f"{sorted(declared)}, so it says it belongs to a protocol "
                "class the table does not file it in"
            )
            continue
        assert declared, (
            f"{name} is filed under the protocol class {class_key!r} but "
            "declares no marker, so nothing outside the partition table says "
            "which class it belongs to"
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


#: A test file that holds **classes**, not bare module-level functions. Chosen
#: because it is the shape the JUnit reader used to get wrong, and it is small.
CLASS_FILE: Final = "test_skill_ledger.py"


def test_a_real_run_keys_a_test_class_to_the_file_it_lives_in(
    repo_root: Path,
) -> None:
    """A case in a class belongs to the file the shard list names.

    **What the reader used to do, and where it went.** pytest writes the module
    path and the class in one dotted `classname` —
    `tests.test_skill_ledger.TestDigests` — and a module and a class are not
    separable from that string: the reader assumed there was no class, turned
    it into `tests/test_skill_ledger/TestDigests.py`, and filed 22 real cases
    under a path that is not in the tree. The manifest, the CI shard list and
    the witness tables all name files, so those cases entered **no**
    denominator: the `unsupported-claim-detection` metric lost a witness file
    it thinks it has, and the required test looked like one the run never
    selected.

    The split is read off the tree, which the run has in front of it.
    """
    import tempfile

    run = run_class(
        repo_root,
        "unit",
        (f"tests/{CLASS_FILE}",),
        Path(tempfile.gettempdir()),
    )
    assert run.ran, f"the run did not happen: {run.error}"
    assert run.outcomes, "the run collected nothing"
    assert {outcome.file for outcome in run.outcomes} == {f"tests/{CLASS_FILE}"}, (
        "a case in a test class was keyed somewhere other than its own file"
    )
    cases = [outcome.node_id for outcome in run.outcomes]
    assert len(set(cases)) == len(cases), (
        "two cases with the same name in two classes collapsed into one node id, "
        "and one of them is now invisible to the denominators"
    )
    assert all("::Test" in node_id for node_id in cases), (
        f"the class is dropped from the node id, so {CLASS_FILE}'s cases cannot be pointed at"
    )


def test_a_file_attribute_still_keeps_the_test_class(tmp_path: Path) -> None:
    """A report that names the file still has the class in its classname.

    **Why this is a separate case.** pytest's legacy JUnit family writes a
    `file` attribute; the current default does not. Reading the file from that
    attribute and then dropping the class is the same collision the tree-read
    avoids — two classes with one test name become one node id — and it arrives
    the moment someone sets `junit_family`. So the classname is still consulted,
    against the now-known module prefix.
    """
    rows = "\n".join(
        '  <testcase classname="tests.test_x.Test' + cls + '" name="test_same_name"'
        ' file="tests/test_x.py" time="0.001"/>'
        for cls in ("First", "Second")
    )
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<testsuites><testsuite name="pytest" tests="2">\n{rows}\n</testsuite></testsuites>\n'
    )
    path = tmp_path / "junit.xml"
    path.write_text(xml, encoding="utf-8")
    outcomes = parse_junit(path, repo_root=tmp_path)
    assert [outcome.file for outcome in outcomes] == ["tests/test_x.py"] * 2
    assert outcomes[0].node_id == "tests/test_x.py::TestFirst::test_same_name"
    assert len({outcome.node_id for outcome in outcomes}) == 2, (
        "two cases with the same name in two classes collapsed into one node id"
    )


def test_the_blockers_table_says_what_its_cases_column_counts() -> None:
    """A HELD blocker can carry cases that did not pass, and the column says so.

    **The row that made this a requirement.** §1.4.1b accepts three platform
    skips on the second blocker and names them in its reason; the number in the
    column beside the status is the count of the cases that did not pass, which
    is not zero. A header that says only *"Cases"* invites a reader to multiply
    it into *"three cases failed this blocker"*, and the row says the opposite.
    """
    blockers = _blockers_with([], set())
    evaluation = EvaluationRun(
        repo_root=str(_ROOT),
        revision="abc123",
        protocol_path="docs/EVALUATION.md",
        classes=(),
        blockers=tuple(blockers),
        metrics=(),
        comparison=assess(ComparisonBasis(label="run"), ComparisonBasis(label="baseline")),
        duration_seconds=0.0,
        command="python -m tests.evaluation",
    )
    markdown = render_markdown(evaluation, "the benchmark clause", "the superiority clause")
    assert "| Cases that did not pass |" in markdown
    assert "| Cases |" not in markdown


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
    return list(blocker_results(protocol, index_outcomes(runs), repo_root=_ROOT))


#: The blocker the three cases below are about, and its witnesses.
CITATION_BLOCKER: Final = "no-fake-citation-or-unsupported-number"


def _citation_witnesses() -> tuple[str, ...]:
    """Every witness of the citation blocker."""
    return manifest.BLOCKER_WITNESSES[CITATION_BLOCKER]


def _skipped_outcome(file: str, name: str, reason: str) -> TestOutcome:
    """One skipped case carrying the reason pytest would have recorded."""
    return TestOutcome(
        file=file,
        node_id=f"{file}::{name}",
        status=SKIPPED,
        duration_seconds=0.0,
        message=reason,
    )


def test_a_platform_conditional_witness_skip_is_accepted_and_named() -> None:
    """§1.4.1b: a witness skipped for a fact of the machine does not fail.

    **This is not a softening of the rule above, and the reason is concrete.**
    No single runner of the CI matrix carries a platform pair — the POSIX half
    of a pair runs on ubuntu and the Windows half runs on windows, and the 8.3
    witnesses depend on a volume that generates short names. Ruling those a
    failure demands that the suite prove a POSIX fact on Windows.

    So the acceptance is conditional on the skip's own wording, and the row
    says what it accepted, case by case and in those words: an acceptance that
    hides what it accepted is the invisibility this blocker exists to close.
    """
    witnesses = _citation_witnesses()
    outcomes = [
        _skipped_outcome(witnesses[0], "test_one", PLATFORM_SKIP_REASON)
        if index == 0
        else _outcome(name, "test_one", PASSED)
        for index, name in enumerate(witnesses)
    ]
    blockers = _blockers_with(outcomes, set(witnesses))
    blocker = next(b for b in blockers if b.key == CITATION_BLOCKER)
    assert blocker.status == "HELD"
    assert not blocker.failures, (
        "an accepted skip is still listed among the cases that failed the blocker"
    )
    assert f"{witnesses[0]}::test_one" in blocker.reason
    assert PLATFORM_SKIP_REASON in blocker.reason


def test_a_witness_skip_outside_the_accepted_categories_still_fails() -> None:
    """The control the witness above needs: the same skip, a different reason.

    One skipped case, one file, one status — only the wording differs, and the
    blocker's status turns on it. Without this, the case above would prove only
    that *some* skip is accepted.
    """
    witnesses = _citation_witnesses()
    outcomes = [
        _skipped_outcome(witnesses[0], "test_one", "the vendor service was down")
        if index == 0
        else _outcome(name, "test_one", PASSED)
        for index, name in enumerate(witnesses)
    ]
    blockers = _blockers_with(outcomes, set(witnesses))
    blocker = next(b for b in blockers if b.key == CITATION_BLOCKER)
    assert blocker.status == "FAILED"
    assert len(blocker.failures) == 1


def test_every_platform_phrase_is_carried_by_a_skip_in_the_tree() -> None:
    """A phrase no skip carries is a dead entry in the ruling.

    **Why this is watched.** The phrase list *is* the declaration: §1.4.1b
    accepts a skip because the test's own reason says which fact of the machine
    it waits on. An entry that nothing in the tree ever says is a rule about a
    skip that does not exist, and a list of those is how the ruling stops
    matching anything without stopping to say so.

    The harness's own test file is left out of the corpus, so this file cannot
    keep a dead phrase alive by quoting it.
    """
    from evaluation.aggregate import _PLATFORM_REASON

    corpus = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (_ROOT / "tests").glob("test_*.py")
        if path.name != "test_evaluation_harness.py"
    )
    dead = tuple(phrase for phrase in _PLATFORM_REASON if phrase not in corpus)
    assert not dead, f"these phrases match no skip in the tree: {dead}"


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
        blockers=blocker_results(protocol, index, repo_root=_ROOT),
        metrics=metric_rows(protocol, index, (result,), None, 1.0, repo_root=_ROOT),
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


def _competitor_baseline_built_on(run: ComparisonBasis) -> ComparisonBasis:
    """A PaperQA2-shaped baseline matched to *run* in everything but the model.

    A competitor that answers questions **is** a model, so a real baseline
    necessarily declares one; that single declaration is the thing this run
    cannot answer. Fixtures, versions and budget are copied from the run's own
    basis precisely so the model is the **only** unmet condition, and the test
    below can say which wall is the real one rather than listing every reason
    the protocol can produce.
    """
    return ComparisonBasis(
        label="paper-qa",
        fixture_labels=run.fixture_labels,
        fixture_versions=dict(run.fixture_versions),
        model="litellm/claude-sonnet-@declared",
        budget=run.budget,
        verified_capabilities=("chunking", "retrieval", "summary context", "citation-key emission"),
        limitations="one run per fixture, no repetition, so no interval is computable",
    )


def test_the_offline_run_refuses_a_competitor_on_the_model_alone(repo_root: Path) -> None:
    """§5.1's blocker, executed rather than described.

    The competitor baseline matches the run's fixtures, versions and budget and
    carries both required disclosures, and the comparison is **still** refused,
    with the model the only unmet condition. That is the finding the credential
    did not clear: our side has no run that declares a model, because the
    numbers this comparison would pair come from the deterministic corpus layer,
    not from a model answering. The release notes' own non-goal — "no task path
    calls a model" — is what this assertion pins.
    """
    from evaluation.cli import _run_basis

    run = _run_basis(repo_root, ())
    assert run.model == "", "the offline run must declare no model"
    competitor = _competitor_baseline_built_on(run)
    outcome = assess(run, competitor)
    assert not outcome.comparable, outcome
    assert any("models are not matched" in reason for reason in outcome.reasons), outcome.reasons

    # Every other condition the protocol names is satisfied on both sides, so
    # the model is the whole of the refusal — not a matcher that rejects all.
    joined = " | ".join(outcome.reasons)
    assert "tasks are not matched" not in joined, outcome.reasons
    assert "budgets are not matched" not in joined, outcome.reasons
    assert "verified capabilities" not in joined, outcome.reasons
    assert "confidence intervals nor limitations" not in joined, outcome.reasons


def test_a_model_declaring_run_makes_that_same_competitor_comparable(repo_root: Path) -> None:
    """The control: the refusal above is our empty basis, not a broken compare.

    The **same** competitor baseline that the offline run refuses becomes
    comparable once the run declares a model. So the moment the product answers
    the fixtures through a declared model, the comparison machinery reaches it —
    and until then nothing should be built to route around the empty basis,
    because a basis stamped with a model the run never used would be the exact
    fabrication §5.1's re-measurement is there to prevent.
    """
    from evaluation.cli import _run_basis

    offline = _run_basis(repo_root, ())
    competitor = _competitor_baseline_built_on(offline)
    declared = ComparisonBasis(
        label="this run, on a model",
        fixture_labels=competitor.fixture_labels,
        fixture_versions=dict(competitor.fixture_versions),
        model=competitor.model,
        budget=competitor.budget,
        verified_capabilities=competitor.verified_capabilities,
        limitations=competitor.limitations,
    )
    assert assess(declared, competitor).comparable


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
        metrics=metric_rows(protocol, index, (), None, 0.0, repo_root=_ROOT),
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


def test_the_real_model_smoke_class_has_a_file_that_carries_it(
    repo_root: Path,
) -> None:
    """The fifth class is **not runnable**, which is not the same as **has no witness**.

    ``REAL_MODEL_SMOKE_FILE`` named a file for two gates and never had one, so
    the report said NOT RUN for a reason that was really "there is nothing to
    run", and the only live probe the project ever made was a hand-call in a
    merge message. This check is what stops that quietly coming back: a renamed
    or deleted probe file leaves the class without its witness and fails here.
    """
    filed = manifest.files_for_class("real_model_smoke")
    assert filed == (manifest.REAL_MODEL_SMOKE_FILE,), (
        f"the class's witness file is named in one place and filed in another: {filed}"
    )
    assert (repo_root / "tests" / manifest.REAL_MODEL_SMOKE_FILE).is_file(), (
        "the harness names a probe file that is not in the tree, so the class "
        "reports NOT RUN while nothing could run it on any machine"
    )


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


def test_the_default_run_reports_the_real_model_class_as_not_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The default run refuses the class that spends money, and says so.

    The default selection includes every class, so the default report says the
    truth about the protocol not being satisfied: the tool did its job and the
    protocol is still unmet, because no credential was named. **What this test
    is really watching is that the inner run was never invoked for that class**
    — a harness that reported NOT RUN while quietly spending money would be
    worse than one that refuses.
    """
    from evaluation import cli

    called: list[str] = []

    def fake_run_class(
        repo_root: Path,
        key: str,
        files: tuple[str, ...],
        temp_root: Path,
        **kwargs: Any,
    ) -> ClassRun:
        called.append(key)
        return ClassRun(
            key=key,
            files=files,
            outcomes=(_outcome("tests/test_one.py", "test_passes", PASSED),),
            exit_code=0,
            duration_seconds=0.0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(cli, "run_class", fake_run_class)
    out = tmp_path / "report"
    code = main(["--out", str(out)])
    markdown = (out / "evaluation-report.md").read_text(encoding="utf-8")
    assert "real_model_smoke" not in called, "the default run invoked the class that spends money"
    assert code == EXIT_NOT_RUN
    assert "NOT RUN" in markdown
    assert "real supported provider" in markdown


def test_a_class_named_on_the_command_line_is_run_rather_than_refused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Naming the fifth class makes the harness **run it**, not decline it.

    The runnability table is a statement about the *default* run. It was also
    being used as a veto: selecting the class still refused it, on a sentence
    the harness asserted about the environment without looking — so the
    protocol's fifth class could not be discharged by any invocation, only
    reported. That is the difference between a gate class that is skipped and
    one that is unreachable, and a reader who supplied a credential had no way
    to tell the two apart.

    **What the report must then carry is the witness's own reason, not the
    table's.** A skip that names `LABCAIRN_PROVIDER_SMOKE_KEY` is a fact about
    this run; the table's paragraph is a fact about the protocol.
    """
    from evaluation import cli

    called: list[str] = []
    skip_reason = (
        "NOT RUN. Needs the project owner's authorisation to spend money, "
        "expressed as LABCAIRN_PROVIDER_SMOKE_KEY and LABCAIRN_PROVIDER_SMOKE_MODEL"
    )

    def fake_run_class(
        repo_root: Path,
        key: str,
        files: tuple[str, ...],
        temp_root: Path,
        **kwargs: Any,
    ) -> ClassRun:
        called.append(key)
        outcome = TestOutcome(
            file="tests/test_real_provider_smoke.py",
            node_id="tests/test_real_provider_smoke.py::test_real_provider_smoke_records_capabilities_and_usage",
            status=SKIPPED,
            duration_seconds=0.0,
            message=skip_reason,
        )
        return ClassRun(
            key=key,
            files=files,
            outcomes=(outcome,),
            exit_code=1,
            duration_seconds=0.0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(cli, "run_class", fake_run_class)
    out = tmp_path / "report"
    code = main(["--out", str(out), "--classes", "real_model_smoke"])
    markdown = (out / "evaluation-report.md").read_text(encoding="utf-8")

    assert called == ["real_model_smoke"], f"the class was named and not run: {called}"
    assert code == EXIT_FAILED, (
        "a class whose witness skipped is a failure to pass, not a harness that "
        "could not run anything — the two are different facts and the exit code "
        "is where a reader tells them apart"
    )
    assert skip_reason in markdown, (
        "the report carried the table's sentence about the environment instead "
        "of the reason the witness actually gave"
    )


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


# --------------------------------------------------------------------------
# The public fixture corpus
# --------------------------------------------------------------------------


def _public_manifest(repo_root: Path) -> dict[str, Any]:
    """The public fixture corpus's manifest."""
    path = repo_root / "tests" / "fixtures" / "public" / "MANIFEST.json"
    loaded: object = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_the_public_corpus_measurement_reads_the_manifest(repo_root: Path) -> None:
    """The harness's corpus measurement reads the public corpus as well.

    **The corpus is the protocol's fixture corpus**, and a corpus nobody
    measures against is not evidence: the key says what the answers are, and
    the harness is what puts the product's own answers beside it. So the
    counts the harness reports are the manifest's own counts, counted again
    here from the manifest rather than from the harness.
    """
    from evaluation.public_corpus import measure_public_corpus

    payload = _public_manifest(repo_root)
    fixtures = payload["fixtures"]
    questions = [question for fixture in fixtures for question in fixture["questions"]]
    abstentions = [question for question in questions if question["answer"]["kind"] == "not_stated"]

    measurement = measure_public_corpus(repo_root)
    assert measurement is not None, "the public fixture corpus was not measured at all"
    assert measurement.fixtures == len(fixtures)
    assert measurement.questions == len(questions)
    assert measurement.abstention_questions == len(abstentions)
    assert measurement.numeric_questions == len(questions) - len(abstentions)


def test_the_public_corpus_measurement_agrees_with_the_material(repo_root: Path) -> None:
    """Every question the corpus asks, the product answers as the key says.

    A disagreement here is a real finding: either the product reads the
    material differently from the key, or the harness measures the wrong
    thing. Both are worth a red test.
    """
    from evaluation.public_corpus import measure_public_corpus

    measurement = measure_public_corpus(repo_root)
    assert measurement is not None
    assert measurement.failures == (), measurement.failures
    assert measurement.numeric_agreed == measurement.numeric_questions
    assert measurement.abstentions_honoured == measurement.abstention_questions
    assert measurement.questions > 0
    assert measurement.abstention_questions > 0, (
        "the corpus holds no question whose answer is an abstention, so the "
        "protocol's abstention metric cannot be measured over it"
    )


def test_the_public_corpus_measurement_can_fail(repo_root: Path, tmp_path: Path) -> None:
    """The measurement can fail, and this is how it is shown.

    A measurement that cannot fail is not a measurement. So two corruptions
    are made to a **copy** of the corpus: a key that names a number the
    material does not give, and a material that carries the quantity an
    abstention question asks about. The first must be caught as a numeric
    disagreement and the second as an abstention the product did not make.
    The committed corpus is never touched.
    """
    import shutil

    from evaluation.public_corpus import measure_public_corpus

    def _copy(name: str) -> Path:
        root = tmp_path / name
        (root / "tests" / "fixtures").mkdir(parents=True)
        shutil.copytree(
            repo_root / "tests" / "fixtures" / "public",
            root / "tests" / "fixtures" / "public",
        )
        return root

    wrong_key = _copy("wrong-key")
    path = wrong_key / "tests" / "fixtures" / "public" / "MANIFEST.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    for fixture in payload["fixtures"]:
        for question in fixture["questions"]:
            if question["id"] == "tension.mean_peak_stress_b2":
                question["answer"]["value"] = 999.0
    path.write_text(json.dumps(payload), encoding="utf-8")
    measurement = measure_public_corpus(wrong_key)
    assert measurement is not None
    assert measurement.failures, "a key that disagrees with the material was not caught"
    assert measurement.numeric_agreed < measurement.numeric_questions

    answered = _copy("answered")
    log = answered / "tests" / "fixtures" / "public" / "no_evidence" / "sample_log.csv"
    log.write_text(
        log.read_text(encoding="utf-8")
        .replace(
            "incubation_temp (C),material_origin",
            "incubation_temp (C),buffer_ph,material_origin",
        )
        .replace(
            ",37,SYNTHETIC MATERIAL",
            ",37,7.2,SYNTHETIC MATERIAL",
        ),
        encoding="utf-8",
    )
    measurement = measure_public_corpus(answered)
    assert measurement is not None
    assert measurement.failures, (
        "a material that answers the abstention question was not caught, so the "
        "abstention measurement would pass on a corpus that is not negative"
    )
    assert measurement.abstentions_honoured < measurement.abstention_questions


def test_the_abstention_metric_is_measured_over_the_public_corpus(repo_root: Path) -> None:
    """The protocol's abstention metric is measured, and over this corpus.

    The metric used to be reported as NOT MEASURED with the reason that the
    tree *"holds no no-evidence fixture to abstain over"* — while
    ``tests/fixtures/public/no_evidence/`` sat in the tree, holding exactly
    that. A reason that says an input is missing when it is present is worse
    than no reason: it tells the reader "this cannot be measured" when the
    truth is "nobody measured it".
    """
    from evaluation.public_corpus import measure_public_corpus

    protocol = _protocol(repo_root)
    rows = metric_rows(protocol, index_outcomes(()), (), None, 0.0, repo_root=repo_root)
    row = next(entry for entry in rows if entry.key == "unsupported-claim-detection")
    measurement = measure_public_corpus(repo_root)
    assert measurement is not None

    assert row.value.measured, row.value.reason
    assert row.value.denominator == measurement.abstention_questions
    assert row.value.numerator == measurement.abstentions_honoured
    assert "public fixture corpus" in row.value.how


# --------------------------------------------------------------------------
# The reasons are derived from the tree
# --------------------------------------------------------------------------


def test_a_not_measured_reason_may_not_contradict_the_tree(repo_root: Path) -> None:
    """A reason that names a missing input has to be true of this tree.

    The reasons are read out of the tree at run time, the way the protocol
    itself is read out of ``docs/EVALUATION.md``: a copy goes stale silently,
    and the copy keeps answering about a tree that is no longer there. So
    the reason has to carry what the tree holds — the corpus's counts — and
    it may not deny an input the tree has.
    """
    from evaluation.aggregate import not_measured_reason, read_tree_facts
    from evaluation.public_corpus import measure_public_corpus

    public = measure_public_corpus(repo_root)
    assert public is not None, "the public fixture corpus is not in this tree"
    facts = read_tree_facts(repo_root, public)

    delivery = not_measured_reason("end-to-end-task-success", facts)
    assert "not in this tree" not in delivery, (
        "the reason says the public fixtures are not in the tree, and they are"
    )
    assert str(public.fixtures) in delivery
    assert str(public.questions) in delivery

    abstention = not_measured_reason("unsupported-claim-detection", facts)
    assert "no no-evidence fixture" not in abstention, (
        "the reason says the tree holds no no-evidence fixture, and it holds one"
    )
    assert str(public.abstention_questions) in abstention

    locator = not_measured_reason("evidence-locator-validity", facts)
    assert facts.ground_truth
    assert "retrieval ground truth" in locator


def test_a_reason_about_a_tree_that_is_not_there_is_still_true(tmp_path: Path) -> None:
    """A tree without the public corpus gets the reason that fits it.

    The reason is derived, so a tree that does not hold the corpus says so
    — and a tree that does hold it says something else. One reason for both
    would be one of the two being a lie.
    """
    from evaluation.aggregate import not_measured_reason, read_tree_facts

    facts = read_tree_facts(tmp_path, None)
    delivery = not_measured_reason("end-to-end-task-success", facts)
    assert "not in this tree" in delivery

    abstention = not_measured_reason("unsupported-claim-detection", facts)
    assert "no no-evidence fixture" in abstention


# --------------------------------------------------------------------------
# The partition's repository class
# --------------------------------------------------------------------------


def test_the_repository_class_holds_only_the_repository_gates() -> None:
    """The repository class is the repository's own gates, and nothing else.

    **Where a file declares no marker, the classification is a judgement**,
    and the partition's own rules say nothing about which way that judgement
    goes: the marker rule covers only the files that declare one, and the
    clause vocabulary covers the clause, not the class. So a file with no
    marker could be moved out of the repository class into a protocol class,
    and every existing check would still pass — while the protocol class's
    denominator grew with checks the protocol never asked for, and the
    repository class's row shrank. That is the very thing the report says
    the repository class exists to prevent.

    So the judgement is bounded here: the repository class holds the
    repository's own gates, and no protocol class holds one of them.
    """
    for name, (class_key, clause) in manifest.FILE_ASSIGNMENTS.items():
        if class_key == manifest.REPOSITORY_CLASS:
            assert clause == "repository-gate", (
                f"{name} is filed under the repository class but checks "
                f"{clause!r}, which is not the repository's own gate clause"
            )
        else:
            assert clause != "repository-gate", (
                f"{name} checks the repository's own gates but is filed under "
                f"the protocol class {class_key!r}, so a protocol class's "
                "denominator would carry checks the protocol never asked for"
            )


# --------------------------------------------------------------------------
# The rendered small denominator
# --------------------------------------------------------------------------


def test_the_rendered_report_says_a_small_denominator_out_loud() -> None:
    """The rendered text, not the model attribute, is what is watched.

    The model carries ``denominator_is_small`` and a test watched that, and
    the report's own sentence — *"yes — the denominator is 3, under 10"* —
    was never rendered by anything. A renderer that said nothing would have
    left the tree green.
    """
    from evaluation.model import SMALL_DENOMINATOR

    protocol = _protocol(_ROOT)
    small = MetricRow(
        key="a-metric",
        text="A metric over a handful of cases.",
        value=Measurement(
            status="MEASURED",
            numerator=2,
            denominator=3,
            how="over three cases",
        ),
        witnesses=(),
        witness_score=Measurement(status="NOT_MEASURED", reason="no witnesses"),
    )
    large = MetricRow(
        key="another-metric",
        text="A metric over enough cases.",
        value=Measurement(
            status="MEASURED",
            numerator=2,
            denominator=SMALL_DENOMINATOR,
            how="over ten cases",
        ),
        witnesses=(),
        witness_score=Measurement(status="NOT_MEASURED", reason="no witnesses"),
    )
    evaluation = EvaluationRun(
        repo_root="/tmp/repo",
        revision="abc123",
        protocol_path="docs/EVALUATION.md",
        classes=(),
        blockers=(),
        metrics=(small, large),
        comparison=assess(ComparisonBasis(label="run"), ComparisonBasis(label="baseline")),
        duration_seconds=0.0,
        command="python -m tests.evaluation",
    )
    markdown = render_markdown(evaluation, protocol.benchmark_clause, protocol.superiority_clause)
    assert f"yes — the denominator is 3, under {SMALL_DENOMINATOR}" in markdown, (
        "the report does not say the denominator is small, so a rate over "
        "three cases reads like a rate over three hundred"
    )
    assert f"yes — the denominator is {SMALL_DENOMINATOR}" not in markdown


# --------------------------------------------------------------------------
# The recovery metric's denominator
# --------------------------------------------------------------------------


def _crash_matrix_run(passing: dict[str, bool]) -> ClassRun:
    """A run over the crash matrix, with the given cases' outcomes."""
    from evaluation.faults import read_crash_matrix

    coverage = read_crash_matrix(_ROOT)
    outcomes = [
        _outcome(
            "tests/test_recovery_crash_matrix.py",
            name,
            PASSED if passing.get(name, True) else FAILED,
        )
        for name in coverage.by_case
    ]
    return ClassRun(
        key="negative",
        files=("tests/test_recovery_crash_matrix.py",),
        outcomes=tuple(outcomes),
        exit_code=0,
        duration_seconds=0.0,
        stdout="",
        stderr="",
    )


def test_the_recovery_metric_counts_crash_points_and_not_cases(repo_root: Path) -> None:
    """The denominator is the crash points, and the sentence says so.

    The number the earlier version reported was the number of collected test
    cases, and the sentence called it *"the fault-injection scenarios the
    crash matrix ran"* — *"one collected test case is one injected fault"*.
    Neither half was true: the matrix collects more cases than it injects
    faults, and it injects more faults than it has cases. The number on the
    page was the number of test functions, and a reader checking it against
    the matrix would find something else.
    """
    from evaluation.faults import read_crash_matrix

    from labcairn.recovery.contracts import CrashPoint

    coverage = read_crash_matrix(repo_root)
    assert set(coverage.defined) == set(CrashPoint.__members__)
    assert coverage.missing == (), (
        f"the matrix does not inject {coverage.missing}, so the layer's coverage is not complete"
    )

    protocol = _protocol(repo_root)
    rows = metric_rows(
        protocol,
        index_outcomes((_crash_matrix_run({}),)),
        (),
        None,
        0.0,
        repo_root=repo_root,
    )
    row = next(entry for entry in rows if entry.key == "recovery-correctness")
    assert row.value.measured
    assert row.value.denominator == len(CrashPoint.__members__)
    assert row.value.numerator == len(CrashPoint.__members__)
    assert "crash point" in row.value.how
    assert "one collected test case is one injected fault" not in row.value.how


def test_the_recovery_metric_drops_when_a_crash_point_behaves_wrongly(repo_root: Path) -> None:
    """A crash point whose case failed is not a crash point that held.

    Otherwise the figure would be a count of cases that happened to pass,
    and the denominator would be a number the protocol never asked for.
    """
    from labcairn.recovery.contracts import CrashPoint

    protocol = _protocol(repo_root)
    failing = "test_at2_crash_after_write_before_commit_marks_uncertain_and_blocks_replay"
    rows = metric_rows(
        protocol,
        index_outcomes((_crash_matrix_run({failing: False}),)),
        (),
        None,
        0.0,
        repo_root=repo_root,
    )
    row = next(entry for entry in rows if entry.key == "recovery-correctness")
    assert row.value.measured
    assert row.value.denominator == len(CrashPoint.__members__)
    assert row.value.numerator == len(CrashPoint.__members__) - 1, (
        "a crash point whose case failed still counted as held"
    )


def test_the_crash_matrix_coverage_is_read_from_the_matrix(repo_root: Path) -> None:
    """The coverage is read out of the matrix's own source.

    A case names the crash point it injects in its body, so the coverage is
    stated there and nowhere else. The reader is also the thing that would
    go stale: a matrix that stopped injecting a crash point would have to
    show up in the metric's rate, and it can only do that if the reader
    reads the matrix rather than a list somebody wrote down.
    """
    from evaluation.faults import read_crash_matrix

    coverage = read_crash_matrix(repo_root)
    assert coverage.by_case, "the matrix's cases were not read at all"
    for case, points in coverage.by_case.items():
        assert points, f"{case} injects no crash point"
    assert set(coverage.covered) == set(coverage.defined)


# --------------------------------------------------------------------------
# The tree the run measured
# --------------------------------------------------------------------------


def _git(repo: Path, *arguments: str) -> str:
    """The output of a git command, run to completion."""
    import subprocess

    completed = subprocess.run(
        ["git", *arguments],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


def test_the_report_says_when_the_tree_it_measured_was_dirty(tmp_path: Path) -> None:
    """A revision names a commit; the tree the run happened on may differ.

    The report's ``revision`` is ``git rev-parse HEAD``, and it says nothing
    about the uncommitted changes that were on disk while the run happened.
    So a run over a dirty tree reported a number against a commit that did
    not contain it — and the number was off by whatever the uncommitted
    change did to the suite. The tree has to be named as well as the commit.
    """
    from evaluation.cli import _working_tree

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(
        repo,
        "-c",
        "user.email=watch@example.invalid",
        "-c",
        "user.name=Watch",
        "commit",
        "--allow-empty",
        "-m",
        "the commit",
    )
    assert not _working_tree(repo).dirty

    note = repo / "notes.md"
    note.write_text("an uncommitted note\n", encoding="utf-8")
    dirty = _working_tree(repo)
    assert dirty.dirty, "an uncommitted change was not seen"
    assert "notes.md" in dirty.description
    assert "notes.md" in dirty.changed

    note.unlink()
    assert not _working_tree(repo).dirty, "the tree was still called dirty"


def test_the_rendered_report_names_the_tree_it_measured() -> None:
    """The report says which tree it measured, and the JSON carries it too."""
    from evaluation.model import WorkingTree

    protocol = _protocol(_ROOT)
    tree = WorkingTree(
        dirty=True,
        changed=("docs/notes.md",),
        description="dirty — 1 file(s) changed and not committed: docs/notes.md",
    )
    evaluation = EvaluationRun(
        repo_root="/tmp/repo",
        revision="abc123",
        protocol_path="docs/EVALUATION.md",
        classes=(),
        blockers=(),
        metrics=(),
        comparison=assess(ComparisonBasis(label="run"), ComparisonBasis(label="baseline")),
        duration_seconds=0.0,
        command="python -m tests.evaluation",
        working_tree=tree,
    )
    markdown = render_markdown(evaluation, protocol.benchmark_clause, protocol.superiority_clause)
    assert "**Working tree:**" in markdown
    assert "dirty" in markdown
    assert "docs/notes.md" in markdown

    document = json.loads(
        render_json(evaluation, protocol.benchmark_clause, protocol.superiority_clause)
    )
    assert document["working_tree"]["dirty"] is True
    assert document["working_tree"]["changed"] == ["docs/notes.md"]


# --------------------------------------------------------------------------
# The sixth blocker's exclusions, and §1.4.1b's ruling over them
# --------------------------------------------------------------------------

#: A skip whose reason names a fact of the machine, worded as the Windows
#: runner actually words it — read out of a real run's ``-rs`` sweep rather
#: than invented, because the classifier matches on these phrases.
PLATFORM_SKIP_REASON: Final = "this machine's volume has no 8.3 short names"


def _skip_blocker_run(skip: str, reason: str = "it did not pass") -> ClassRun:
    """A run in which one required test had a skipped case.

    ``reason`` is the skip's own wording, because under §1.4.1b the wording is
    what classifies the exclusion: the declaration lives with the skip.
    """
    outcomes = [
        _outcome(f"tests/{name}", "test_one", PASSED)
        for name in manifest.BLOCKER_WITNESSES["no-skipped-required-tests"]
    ]
    outcomes.append(
        TestOutcome(
            file="tests/" + skip,
            node_id=f"tests/{skip}::test_a_skipped_case",
            status=SKIPPED,
            duration_seconds=0.0,
            message=reason,
        )
    )
    return ClassRun(
        key="unit",
        files=("tests/" + skip,),
        outcomes=tuple(outcomes),
        exit_code=0,
        duration_seconds=0.0,
        stdout="",
        stderr="",
    )


def _sixth_blocker(repo_root: Path, run: ClassRun) -> Any:
    """The sixth blocker's row for a synthetic run."""
    protocol = _protocol(repo_root)
    index = index_outcomes((run,))
    return next(
        b
        for b in blocker_results(protocol, index, repo_root=repo_root)
        if b.key == "no-skipped-required-tests"
    )


def test_a_platform_conditional_skip_is_accepted_and_named(repo_root: Path) -> None:
    """A required test skipped for a fact of the machine holds, and is named.

    **§1.4.1b's ruling.** The CI matrix runs both platforms, so no single
    runner carries a platform pair: ruling these a failure would demand that
    the suite prove a POSIX fact on Windows. So the blocker holds and the row
    still says which tests were accepted, because an acceptance that hides
    what it accepted is the invisibility this blocker exists to close.
    """
    blocker = _sixth_blocker(
        repo_root,
        _skip_blocker_run("test_security_paths.py", PLATFORM_SKIP_REASON),
    )
    assert blocker.status == "HELD"
    assert "test_security_paths.py" in blocker.reason
    assert "platform or filesystem fact" in blocker.reason, (
        "the row does not say on what standing the skip was accepted"
    )


def test_a_skip_that_names_no_standing_category_fails_the_blocker(repo_root: Path) -> None:
    """A required test skipped for a reason outside the categories fails it.

    **"Required CI tests are skipped" is exactly the hole this blocker
    watches**, and a reason that names no standing category is not a
    declaration. The row carries the file, the case and the reason the test
    gave, so a reader can act on it rather than only see red.
    """
    blocker = _sixth_blocker(
        repo_root,
        _skip_blocker_run("test_provider_credentials.py", "needs a fixture the tree does not hold"),
    )
    assert blocker.status == "FAILED"
    assert "no\n" not in blocker.reason
    assert "test_provider_credentials.py" in blocker.reason
    assert "needs a fixture the tree does not hold" in blocker.reason, (
        "the skip's own reason is not in the row, so the row cannot be acted on"
    )


def test_the_real_model_smoke_file_is_accepted_as_ruled_elsewhere(repo_root: Path) -> None:
    """The offline run's absence of the smoke class is not a skipped test.

    §1.4.2 discharged the real-model class from the scheduled workflow, so the
    offline run never selects it. That is a fact about the protocol's offline
    posture, not a required test that skipped — and the classification comes
    from the class table the harness already holds, not from a named file.
    """
    blocker = _sixth_blocker(
        repo_root,
        _skip_blocker_run("test_security_paths.py", PLATFORM_SKIP_REASON),
    )
    assert "test_real_provider_smoke.py" in blocker.reason
    assert "class the owner has ruled is discharged outside it" in blocker.reason


def test_a_required_test_the_run_did_not_select_is_not_called_a_skip(
    repo_root: Path,
) -> None:
    """Leaving a required test out of a run is scope, not a skip.

    **The wording is the whole claim.** A partial run must not report that a
    test was skipped when it was never selected, and it must not fail the
    blocker for it either — so the category is separate and the sentence says
    "did not select". Making these files undeclared instead would flip the
    status, which is what the assertion below would catch.
    """
    blocker = _sixth_blocker(
        repo_root,
        _skip_blocker_run("test_security_paths.py", PLATFORM_SKIP_REASON),
    )
    assert blocker.status == "HELD"
    assert "test_cite_c1.py" in blocker.reason, (
        "a required test this run left out is not named at all"
    )
    assert "did not select" in blocker.reason


def test_a_required_test_that_collected_nothing_is_named_as_that(repo_root: Path) -> None:
    """Selected-and-empty is neither "not selected" nor a pass.

    **Three of the CI's own required test files are support modules** that
    define no ``test_*`` function — ``test_store_support.py`` and its two
    siblings, which other test files import for their fixtures. They are in the
    shard list, CI pays to collect them, and nothing in them is collected. The
    row has to say that, because the two things a reader might otherwise infer
    are both wrong: that the run skipped the file, or that the file checked
    something and passed.
    """
    from evaluation.aggregate import COLLECTED_NOTHING, _excluded_required_tests

    run = _skip_blocker_run(
        "test_security_paths.py", "this machine's volume has no 8.3 short names"
    )
    selected = ClassRun(
        key="unit",
        files=(*run.files, "tests/test_store_support.py"),
        outcomes=run.outcomes,
        exit_code=0,
        duration_seconds=0.0,
        stdout="",
        stderr="",
    )
    index = index_outcomes((selected,))
    entry = next(
        e for e in _excluded_required_tests(index, repo_root) if e.name == "test_store_support.py"
    )
    assert entry.category == COLLECTED_NOTHING, (
        "a file the run asked for is reported as one it never selected"
    )
    blocker = _sixth_blocker(repo_root, selected)
    assert "no case was collected" in blocker.reason
    assert "test_store_support.py" in blocker.reason


def test_one_file_with_three_skips_is_counted_as_one_file(repo_root: Path) -> None:
    """The row counts files, and says so in the number it prints.

    Three platform skips in one file are three facts, and a row that names the
    file three times reads as three files — which is how a count stops meaning
    what the sentence around it says. This is the shape the first measured run
    produced: `test_security_paths.py` listed three times under "4 required CI
    tests".
    """
    outcomes = [
        _outcome(f"tests/{name}", "test_one", PASSED)
        for name in manifest.BLOCKER_WITNESSES["no-skipped-required-tests"]
    ]
    outcomes.extend(
        _skipped_outcome(f"tests/{CLASS_FILE}", f"test_skip_{index}", PLATFORM_SKIP_REASON)
        for index in range(3)
    )
    run = ClassRun(
        key="unit",
        files=(f"tests/{CLASS_FILE}",),
        outcomes=tuple(outcomes),
        exit_code=0,
        duration_seconds=0.0,
        stdout="",
        stderr="",
    )
    blocker = _sixth_blocker(repo_root, run)
    assert "accepted 1 required CI test(s)" in blocker.reason, blocker.reason
    assert blocker.reason.count(f"{CLASS_FILE}") == 1


def test_the_exclusion_is_in_the_rendered_report(repo_root: Path) -> None:
    """The exclusion is on the page, not only in the model."""
    protocol = _protocol(repo_root)
    index = index_outcomes(
        (
            _skip_blocker_run(
                "test_provider_credentials.py", "needs a fixture the tree does not hold"
            ),
        )
    )
    evaluation = EvaluationRun(
        repo_root=str(repo_root),
        revision="abc123",
        protocol_path="docs/EVALUATION.md",
        classes=(),
        blockers=blocker_results(protocol, index, repo_root=repo_root),
        metrics=(),
        comparison=assess(ComparisonBasis(label="run"), ComparisonBasis(label="baseline")),
        duration_seconds=0.0,
        command="python -m tests.evaluation",
    )
    markdown = render_markdown(evaluation, protocol.benchmark_clause, protocol.superiority_clause)
    assert "test_provider_credentials.py" in markdown
    assert "needs a fixture the tree does not hold" in markdown
    assert "FAILED" in markdown


def test_the_required_tests_are_read_out_of_the_shard_file(repo_root: Path) -> None:
    """The required tests come from the CI's own shard list.

    A copy of the shard list inside the harness would drift from the file
    the CI runs, and a drifted copy would name the wrong required tests —
    which is the shape of hole the protocol parser exists to close.
    """
    from evaluation.shards import required_test_files

    required = required_test_files(repo_root)
    assert "test_provider_credentials.py" in required, (
        "the required tests do not name the file that carries the skip"
    )
    shard_file = repo_root / ".github" / "ci-shards.json"
    document = json.loads(shard_file.read_text(encoding="utf-8"))
    named = {
        Path(entry).name
        for shards in document["shards"].values()
        for shard in shards
        for entry in shard
    }
    assert set(required) == named


# --------------------------------------------------------------------------
# The published records
# --------------------------------------------------------------------------


def _published_records(repo_root: Path) -> tuple[Path, ...]:
    """The Markdown the repository ships."""
    documents = list((repo_root / "docs").rglob("*.md"))
    documents.extend(repo_root / name for name in ("README.md", "README.zh-CN.md", "CHANGELOG.md"))
    return tuple(sorted(path for path in documents if path.is_file()))


#: A paragraph that denies, forbids or excludes. **A denial is not a claim.**
#:
#: The review dossier says outright that it contains *"no claim that LabCairn
#: is better than any upstream project"*, and quotes the protocol's own ban
#: on claiming superiority. **Both carry the words the watch looks for** and
#: both are the opposite of a claim, so a paragraph with one of these in it
#: is not counted.
#:
#: **The limit this leaves is real**: the unit is the paragraph, so a
#: negation anywhere in it exempts every claim the paragraph carries
#: (*"there is no baseline, and this beats B"*). It is stated here rather
#: than left for a reader to discover.
_NEGATION = re.compile(
    r"\b(?:not|no|never|without|forbid|forbids|forbidden|cannot|neither|nor|"
    r"refuse|refuses|prohibit|prohibits)\b",
    re.IGNORECASE,
)


def _paragraphs(path: Path) -> list[tuple[int, str]]:
    """The ordinary paragraphs of a document, each joined into one line.

    **A paragraph, not a line.** A superiority claim whose verdict word
    and whose named system fall on different lines is still a claim — and
    this repository wraps prose at about seventy-nine columns, so a line
    break at the wrong place is a thing that happens. The unit is
    therefore the paragraph, joined, so a wrap cannot hide the claim.

    **A quoted line and a fenced line are not a paragraph.** A block
    quote is a quotation, and the gate's own review reports quote the
    sentence they planted; a fence is a code sample. Neither is a claim
    about anything, and neither is joined to what surrounds it.
    """
    paragraphs: list[tuple[int, str]] = []
    current: list[str] = []
    start = 0
    in_fence = False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            if current:
                paragraphs.append((start, " ".join(current)))
                current = []
            continue
        if in_fence or stripped.startswith(">"):
            continue
        if not stripped:
            if current:
                paragraphs.append((start, " ".join(current)))
                current = []
            continue
        if not current:
            start = number
        current.append(stripped)
    if current:
        paragraphs.append((start, " ".join(current)))
    return paragraphs


def test_no_published_record_claims_superiority_over_another_system(repo_root: Path) -> None:
    """The documents a reader reads are watched for a superiority claim.

    The harness watches its own rendered comparison section for the words
    that carry a verdict, and it keeps that vocabulary in **one** place, so
    that there is one list. But the documents a reader actually reads — the
    acceptance records, the review dossier, the release notes, the README —
    were not watched at all: a sentence saying one system *"outperforms"*
    another went into a published record and nothing said so.

    So the published records are watched here against **the same
    vocabulary**, read from the harness rather than restated, and the
    systems a claim may not be made about are read from **the protocol's own
    superiority clause**, so neither list is a second copy.

    **The unit is the paragraph, and the claim has to name its target.** A
    paragraph that carries a verdict word *and* names one of the systems the
    protocol lists is a superiority claim. A paragraph that carries a verdict
    word and names nothing is ordinary English — *"worse than no test"*,
    *"the worst of it"* — and the published records are full of it.

    **A quoted line is not a claim.** A line inside a Markdown block quote
    or a fenced code block is *being quoted* — the gate's own review
    reports write down the exact sentence they planted, and the mutation
    tables write down the exact answer they corrupted, and **the exact
    sentence is the evidence**. So a quoted line is not a claim about
    anything, and it is not counted as one.

    **That is the limit of this check, and it is a real one.** A record
    that dressed a superiority claim as a block quote would pass here.
    Such a record is still read by the people who write it, and the
    protocol's rule is on the claim rather than on the punctuation.
    """
    from evaluation.report import comparison_targets, ranking_pattern, target_pattern

    protocol = _protocol(repo_root)
    targets = comparison_targets(protocol.superiority_clause)
    assert targets, "the protocol's clause names no system to compare against"

    ranking = ranking_pattern()
    named = target_pattern(targets)
    sample = "LabCairn outperforms PaperQA2 on citation precision."
    assert ranking.search(sample) and named.search(sample), (
        "the watch would not catch the claim it is written for, so it is watching nothing"
    )

    offenders: list[str] = []
    for path in _published_records(repo_root):
        for number, paragraph in _paragraphs(path):
            if not ranking.search(paragraph) or not named.search(paragraph):
                continue
            if _NEGATION.search(paragraph):
                continue
            offenders.append(f"{path.relative_to(repo_root)}:{number}: {paragraph[:180]}")
    assert not offenders, (
        "a published record carries a word that claims a verdict and names "
        "another system, which the protocol forbids without like-for-like "
        "matched-task baselines: " + "; ".join(offenders)
    )


# --------------------------------------------------------------------------
# The inner run's temporary directory
# --------------------------------------------------------------------------


def test_the_inner_run_gets_its_own_temporary_directory_everywhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``TMPDIR`` is set as well, because it is the one that is read first.

    Python's :func:`tempfile.gettempdir` looks at ``TMPDIR``, then ``TEMP``,
    then ``TMP`` — in that order, on **every** platform. So an environment
    that carries a ``TMPDIR`` wins over the two the runner sets, and the
    inner run puts its temporary files where the runner never looked. The
    isolation would have a hole in it the same on Windows as on Linux, and
    the hole would only open on a machine that happens to have a ``TMPDIR``.
    """
    from evaluation.runner import _environment

    root = tmp_path / "run"
    root.mkdir()
    monkeypatch.setenv("TMPDIR", str(tmp_path / "somewhere-else"))
    monkeypatch.setenv("TEMP", str(tmp_path / "somewhere-else"))
    monkeypatch.setenv("TMP", str(tmp_path / "somewhere-else"))
    environment = _environment(root, _ROOT)
    assert environment["TMPDIR"] == str(root)
    assert environment["TEMP"] == str(root)
    assert environment["TMP"] == str(root)


def test_the_evaluation_record_names_every_witness_in_this_file(repo_root: Path) -> None:
    """The record's witness table is re-read from this file, not remembered.

    **Why this is watched.** `docs/acceptance/LC-P1-13-evaluation.md` §9 lists
    the harness's witnesses and says how many there are, and by the time this
    witness was written the count was stale by thirty functions: the file grew
    across four merges and nobody re-read the table. A record that says *"39
    test functions"* while the tree holds twice that is the same shape as a
    reason naming an input the tree no longer has — it keeps answering after the
    thing it describes has moved, and the reader has no way to tell.

    The check runs in one direction only, and the direction is the honest one:
    **every witness this file defines must have a row in the record's table.**
    The record may name functions from other files, and may discuss any of them
    in prose — so a line is counted only when it **opens** a table row with the
    function in backticks. Read as *"does the name appear anywhere in the file"*
    the check is weak, and it was shown to be: the first version of this witness
    stayed green with the table row deleted, because the prose above it still
    quoted the name.
    """
    record = repo_root / "docs" / "acceptance" / "LC-P1-13-evaluation.md"
    named = {
        match.group(1)
        for line in record.read_text(encoding="utf-8").splitlines()
        if (match := re.match(r"\|\s*`(test_[a-z0-9_]+)`\s*\|", line))
    }
    here = {
        node.name
        for node in ast.parse(Path(__file__).read_text(encoding="utf-8")).body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    }
    missing = sorted(here - named)
    assert not missing, (
        "the evaluation record's witness table has no row for these witnesses, so "
        f"it is a memory rather than a reading: {missing}"
    )
    stated = re.search(r"\*\*(\d+) test functions", record.read_text(encoding="utf-8"))
    assert stated is not None and int(stated.group(1)) == len(here), (
        f"the record says {stated.group(1) if stated else 'nothing'} test functions; "
        f"this file defines {len(here)}"
    )
