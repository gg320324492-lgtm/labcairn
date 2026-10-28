"""The one command.

    python -m tests.evaluation

runs the protocol's gate classes, measures what can be measured, and writes
the report. The exit code says what the run found:

* **0** — every selected class ran, every case passed, and every Phase 1
  blocker held.
* **1** — a case failed, errored or was skipped, or a blocker did not hold.
* **2** — a selected class could not be run.

**Why the default exit code is not 0.** The protocol names five mandatory
gate classes and one of them — the real-model smoke — needs *"at least one
real supported provider under declared model/version/parameters"*. There is
no credential for one, so the default run **selects** that class, **cannot
run** it, reports it as NOT RUN with the reason, and exits 2. The tool did
its job; the protocol is not satisfied by this tree. A harness that
exited 0 there would be reporting a pass for a class it never ran, which
is the shape the protocol's sixth blocker names.

``--classes`` narrows the selection, and the exit code then speaks about
what was selected.

**Where the report goes.** Outside the repository, by default under the
system's temporary directory. The repository's own rules are that runtime
artefacts do not live inside the checkout, and a harness that wrote its
report into the tree it measures would dirty the tree it measures.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Final

from . import manifest
from .aggregate import (
    blocker_results,
    class_result,
    index_outcomes,
    metric_rows,
)
from .comparison import (
    ComparisonBasis,
    assess,
    load_baseline,
    pairs,
)
from .corpus import CORPUS_FIXTURES, measure_corpus
from .model import ClassResult, ComparisonOutcome, EvaluationRun, MetricRow, WorkingTree
from .protocol import GateClass, Protocol, parse_protocol, protocol_path
from .report import write_report
from .runner import DEFAULT_TIMEOUT_SECONDS, ClassRun, run_class

#: The exit codes, and what each one means.
EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
EXIT_NOT_RUN: Final = 2

#: The repository root, found from this file's own location.
REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent.parent


def _git(repo_root: Path, *arguments: str) -> str | None:
    """The output of a git command, or ``None`` when git could not be run."""
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout


def _revision(repo_root: Path) -> str:
    """The commit the tree is at, or a plain statement that it is unknown."""
    output = _git(repo_root, "rev-parse", "HEAD")
    if output is None:
        return "unknown (git could not be run)"
    return output.strip() or "unknown"


def _working_tree(repo_root: Path) -> WorkingTree:
    """The state of the working tree the run was made against.

    **A revision names a commit, and a commit is not a working tree.** The
    report's ``revision`` is the commit, and it says nothing about the
    uncommitted changes that were on disk while the run happened. So a run
    over a dirty tree reported a number against a commit that did not contain
    it, and the number was off by whatever the uncommitted change did to the
    suite. A number has to be anchored to the tree it was measured on, and
    the tree is the working tree — so the report says which one it measured.
    """
    output = _git(repo_root, "status", "--porcelain")
    if output is None:
        return WorkingTree(
            dirty=False,
            changed=(),
            description="unknown (git could not be run)",
        )
    changed: list[str] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        changed.append(path.strip('"'))
    if not changed:
        return WorkingTree(
            dirty=False,
            changed=(),
            description="clean — the commit is the tree that was measured",
        )
    return WorkingTree(
        dirty=True,
        changed=tuple(sorted(changed)),
        description=(
            f"dirty — {len(changed)} file(s) changed and not committed: "
            + ", ".join(sorted(changed))
        ),
    )


def _default_classes() -> tuple[str, ...]:
    """Every class, the protocol's five and the repository's own."""
    return manifest.ALL_CLASS_KEYS


def build_parser() -> argparse.ArgumentParser:
    """The command's arguments."""
    parser = argparse.ArgumentParser(
        prog="python -m tests.evaluation",
        description=(
            "Run the evaluation protocol's gate classes and report the "
            "results with their denominators."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="the repository to measure (default: the one this package is in)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=(
            "where to write the report (default: a directory under the "
            "system's temporary directory, outside the repository)"
        ),
    )
    parser.add_argument(
        "--classes",
        default="",
        help=(
            "a comma-separated list of classes to select (default: all of "
            "them). The class names are the protocol's own: " + ", ".join(manifest.ALL_CLASS_KEYS)
        ),
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="a baseline document to compare against, if there is one",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"how long one class may take (default: {DEFAULT_TIMEOUT_SECONDS:.0f} s)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="print the partition and exit without running anything",
    )
    return parser


def _selected_classes(requested: str) -> tuple[str, ...]:
    """The classes the command was asked to select."""
    if not requested.strip():
        return _default_classes()
    names = tuple(name.strip() for name in requested.split(",") if name.strip())
    unknown = [name for name in names if name not in manifest.ALL_CLASS_KEYS]
    if unknown:
        known = list(manifest.ALL_CLASS_KEYS)
        msg = f"these are not classes this harness knows: {unknown}. Known: {known}"
        raise SystemExit(msg)
    return names


def _print(text: str) -> None:
    """Write to the terminal without ``print``, which the lint forbids here.

    **Flushed.** The run takes minutes and the progress line is the only
    thing that says it is alive; a buffered line that appears all at once
    at the end is a tool that looks hung.
    """
    sys.stdout.write(text)
    sys.stdout.flush()


def main(argv: list[str] | None = None) -> int:
    """Run the protocol's checks and report them."""
    parser = build_parser()
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    protocol = parse_protocol(
        protocol_path(repo_root),
        manifest.METRIC_PREFIXES,
        manifest.BLOCKER_PREFIXES,
        manifest.OFFLINE_CLASSES,
    )

    if args.list:
        _print(_partition_listing())
        return EXIT_OK

    selected = _selected_classes(args.classes)
    out_dir = args.out or (Path(tempfile.gettempdir()) / "labcairn-evaluation")
    temp_root = Path(tempfile.gettempdir())

    started = time.monotonic()
    runs = []
    #: Whether the reader named the classes, rather than taking the default of
    #: all of them. This is the only distinction between "the run may spend
    #: money" and "it may not", and it is a command-line fact rather than a
    #: guess about the environment.
    named_on_the_command_line = bool(args.classes.strip())
    for gate_class in (*protocol.gate_classes, manifest.REPOSITORY_GATE_CLASS):
        files = manifest.paths_for_class(gate_class.key)
        if gate_class.key not in selected:
            runs.append(_not_selected(gate_class.key, files, "this class was not selected"))
            continue
        if not gate_class.runnable_offline and not named_on_the_command_line:
            runs.append(_not_runnable(gate_class.key, files, gate_class.offline_reason))
            continue
        if not gate_class.runnable_offline:
            # The reader named a class the runnability table says is not
            # runnable offline, so the table's sentence about the environment
            # is no longer allowed to stand in for an observation: the class's
            # own witness skips when no credential is named, and the report says
            # that with the reason the test gave rather than this harness's
            # guess about somebody else's machine.
            _print(
                f"the {gate_class.label} class was named on the command line, so its own "
                "witness decides what happens — it spends money if a credential is named, "
                "and skips if not.\n"
            )
        _print(f"running the {gate_class.label} class ({len(files)} files)...\n")
        runs.append(
            run_class(
                repo_root,
                gate_class.key,
                files,
                temp_root,
                timeout=args.timeout,
            )
        )
    duration = time.monotonic() - started

    index = index_outcomes(tuple(runs))
    classes = tuple(
        class_result(
            _gate_class(protocol, run.key),
            run,
            selected=run.key in selected,
        )
        for run in runs
    )
    blockers = blocker_results(protocol, index, repo_root=repo_root)

    corpus = measure_corpus(repo_root)
    revision = _revision(repo_root)
    working_tree = _working_tree(repo_root)
    metrics = metric_rows(
        protocol,
        index,
        classes,
        corpus,
        duration,
        context=(
            f"dataset revision: {revision}",
            f"working tree: {working_tree.description}",
            "seeds: this repository's determinism rule — no RNG and a frozen "
            "clock, and the corpus is committed data — so a run is "
            "reproducible from the revision above.",
        ),
        repo_root=repo_root,
    )

    comparison = _comparison(args.baseline, repo_root, classes, metrics)

    run = EvaluationRun(
        repo_root=str(repo_root),
        revision=revision,
        protocol_path=str(protocol.path),
        classes=classes,
        blockers=blockers,
        metrics=metrics,
        comparison=comparison,
        duration_seconds=duration,
        command="python -m tests.evaluation " + " ".join(argv or sys.argv[1:]),
        working_tree=working_tree,
        notes=(
            "the corpus measurement compares the product's own selection code "
            "against the committed answer key, cell by cell; the public "
            "fixture corpus is measured the same way, against its own key, "
            "and the witness scores below are the tests that check the same "
            "properties, and they are not the same number.",
        ),
    )

    markdown_path, json_path = write_report(
        out_dir,
        run,
        protocol.benchmark_clause,
        protocol.superiority_clause,
    )

    _print(_summary(run, markdown_path, json_path))
    return _exit_code(run)


def _not_runnable(key: str, files: tuple[str, ...], reason: str) -> ClassRun:
    """A class that was selected and could not be run."""
    return ClassRun(
        key=key,
        files=files,
        outcomes=(),
        exit_code=EXIT_NOT_RUN,
        duration_seconds=0.0,
        stdout="",
        stderr="",
        error=reason,
    )


def _not_selected(key: str, files: tuple[str, ...], reason: str) -> ClassRun:
    """A class the reader did not select.

    Not selected is not the same as not run: the first is the reader's
    choice and says nothing about the protocol, and the second is a gap in
    the evidence. The report tells them apart and the exit code only
    speaks about the second.
    """
    return ClassRun(
        key=key,
        files=files,
        outcomes=(),
        exit_code=EXIT_OK,
        duration_seconds=0.0,
        stdout="",
        stderr="",
        error=reason,
    )


def _gate_class(protocol: Protocol, key: str) -> GateClass:
    """The class with this key — the protocol's, or the repository's own."""
    if key == manifest.REPOSITORY_CLASS:
        return manifest.REPOSITORY_GATE_CLASS
    return protocol.gate_class(key)


def _run_basis(repo_root: Path, classes: tuple[ClassResult, ...]) -> ComparisonBasis:
    """What this run says about itself, for the comparison to check.

    **The model is empty, and that is the fact.** The offline run used the
    deterministic ``FakeProvider``, which is not *"a declared model, version
    and parameter set"*. So this run declares no model, and a baseline that
    declares one cannot be matched against it — which is the protocol's own
    rule producing the answer rather than the harness deciding to refuse.
    """
    versions: dict[str, str] = {}
    for fixture in CORPUS_FIXTURES:
        key = repo_root / "tests" / "fixtures" / "analysis" / f"{fixture}.expected.json"
        if key.is_file():
            versions[fixture] = hashlib.sha256(key.read_bytes()).hexdigest()
    return ComparisonBasis(
        label="this run",
        fixture_labels=CORPUS_FIXTURES,
        fixture_versions=versions,
        model="",
        budget="",
        verified_capabilities=tuple(
            result.key for result in classes if result.ran and result.collected > 0
        ),
        limitations=(
            "the offline run used the deterministic FakeProvider, so its "
            "numbers are a measurement of the repository's own tests and not "
            "of a model's behaviour"
        ),
    )


def _comparison(
    baseline_path: Path | None,
    repo_root: Path,
    classes: tuple[ClassResult, ...],
    metrics: tuple[MetricRow, ...],
) -> ComparisonOutcome:
    """Decide whether a baseline may be compared against this run."""
    if baseline_path is None:
        return ComparisonOutcome(
            comparable=False,
            reasons=(
                "no baseline document was given, so no comparison was made. "
                "The protocol permits a comparison only when it is "
                "like-for-like, and an unasked-for comparison is not one.",
            ),
        )
    baseline = load_baseline(baseline_path)
    outcome = assess(_run_basis(repo_root, classes), baseline.basis)
    if not outcome.comparable:
        return outcome
    run_values = {
        row.key: (row.value.numerator, row.value.denominator)
        for row in metrics
        if row.value.measured
        and row.value.numerator is not None
        and row.value.denominator is not None
    }
    return ComparisonOutcome(comparable=True, deltas=pairs(run_values, baseline.metrics))


def _exit_code(run: EvaluationRun) -> int:
    """What the run found.

    Only a **selected** class that could not be run is a gap in the
    evidence. A class the reader did not select says nothing about the
    protocol, and it is the reader's choice.
    """
    if any(not result.ran and result.selected for result in run.classes):
        return EXIT_NOT_RUN
    if run.failures:
        return EXIT_FAILED
    if not run.blockers_held:
        return EXIT_FAILED
    return EXIT_OK


def _summary(run: EvaluationRun, markdown_path: Path, json_path: Path) -> str:
    """What the terminal says."""
    lines = [
        "",
        "The evaluation, run against the protocol.",
        "",
        f"  report (markdown): {markdown_path}",
        f"  report (json):     {json_path}",
        "",
    ]
    for result in run.classes:
        if not result.ran:
            state = "NOT SELECTED" if not result.selected else "NOT RUN"
            lines.append(f"  {result.title:<18} {state} — {result.not_run_reason}")
            continue
        rate = "n/a" if result.pass_rate is None else f"{result.pass_rate:.3f}"
        lines.append(
            f"  {result.title:<14} {result.passed}/{result.collected} passed "
            f"({rate}), {result.failed} failed, {result.skipped} skipped, "
            f"{result.xfailed} xfailed"
        )
    lines.append("")
    for blocker in run.blockers:
        lines.append(f"  blocker {blocker.key}: {blocker.status}")
    lines.append("")
    for row in run.metrics:
        if row.value.measured:
            lines.append(f"  metric {row.key}: {row.value.numerator}/{row.value.denominator}")
        else:
            lines.append(f"  metric {row.key}: NOT MEASURED")
    lines.append("")
    return "\n".join(lines)


def _partition_listing() -> str:
    """The partition, as text — what ``--list`` prints."""
    lines = ["The partition of the repository's test files:"]
    for class_key in manifest.ALL_CLASS_KEYS:
        files = manifest.files_for_class(class_key)
        lines.append(f"  {class_key} ({len(files)} files)")
        for name in files:
            clause = manifest.clause_for_file(name)
            lines.append(f"      {name:<45} {clause}")
    lines.append("")
    return "\n".join(lines)
