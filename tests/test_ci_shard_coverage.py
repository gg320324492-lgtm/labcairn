"""The CI shards, watched.

**The property.** Every test file in the repository belongs to **exactly one**
shard, on **every platform**, and the number of shards is **the number the
workflow's matrix declares**.

**Why it needs watching.** The CI workflow runs the suite in shards, each
shard in its own job on its own runner, because a runner that runs the whole
suite is slow — and the slowness is not evenly spread, so one runner doing
everything is the worst possible arrangement.

The cost of that arrangement is a hole: **a test file that is in no shard is
never run by CI at all**, and every other check stays green while it goes.
That is the same shape as F30 — the mechanism that does the watching, unwatched
— and it is worse here, because a shard list is edited by hand and a hand-
edited list is exactly the thing that drifts.

So this file watches it, in three parts:

* every ``tests/test_*.py`` is in exactly one shard on every platform — none
  missing, none twice;
* every file a shard names actually exists;
* the shard count is the workflow matrix's shard count, so the two cannot
  drift apart.

And it watches the **balance** too, against the measured costs recorded
alongside the shards. A shard list that is correct but lopsided is not wrong;
it is just slow, and the way that gets noticed is that somebody adds a slow
test file and the CI time goes up and nobody knows why.

**Why the partition is per platform.** The two runners do not cost the same,
and they do not cost the same *in the same proportions* either: measured on
the runner, one shard was 310 seconds on Windows and 163 on Ubuntu, while
another was 671 on Windows and 144 on Ubuntu. A partition balanced for one
platform is lopsided on the other, so each platform gets its own.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import subprocess
import sys
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

import pytest
import yaml
from evaluation import manifest
from workflow_job_names import MATRIX_NON_AXIS_KEYS, load_workflows, rendered_job_names

#: The shard file, next to the workflow that uses it.
SHARD_FILE: Final[Path] = Path(".github") / "ci-shards.json"

#: The workflow that uses it.
WORKFLOW_FILE: Final[Path] = Path(".github") / "workflows" / "python.yml"

#: Every workflow whose job names branch protection may identify. The witness
#: below reads the whole directory: a name collision between two workflow files
#: is the same deadlock as one inside a single file, and a new workflow that no
#: witness reads is a workflow that can repeat any name it likes.
WORKFLOWS_DIR: Final[Path] = Path(".github") / "workflows"

#: The platforms the workflow runs on. The partition is per platform.
PLATFORMS: Final[tuple[str, ...]] = ("ubuntu-latest", "windows-latest")


#: How far the longest shard may be from the shortest, as a multiple. The
#: slack this buys is what decides whether a change needs the costs
#: re-measured: a file that costs less than the slack cannot unbalance the
#: partition however much its own cost moves.
BALANCE_LIMIT: Final[float] = 1.6


def _workflow_job_names(repo_root: Path) -> list[tuple[Path, dict[str, Any]]]:
    """Every workflow in the directory, parsed — the shared reader's output.

    The rendering is `workflow_job_names.rendered_job_names`, shared with
    `tests/test_shell_ci.py`. Two witnesses that each spelled out the matrix
    substitution drifted apart exactly once already, and that is how
    `release-dependency-licences (matrix.os)` stayed a collision no check read.
    """
    documents = load_workflows(repo_root / WORKFLOWS_DIR)
    assert documents, f"{WORKFLOWS_DIR} declares no workflows to check"
    return documents


def _shard_document(repo_root: Path) -> dict[str, Any]:
    path = repo_root / SHARD_FILE
    assert path.is_file(), f"the CI workflow reads {SHARD_FILE}, and it is not there"
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return document


def _shards(repo_root: Path, platform: str) -> list[list[str]]:
    document = _shard_document(repo_root)
    partitions = document.get("shards")
    assert isinstance(partitions, dict), "the shard file must hold one partition per platform"
    assert platform in partitions, f"the shard file has no partition for {platform}"
    shards = partitions[platform]
    assert isinstance(shards, list) and shards, f"the {platform} partition names no shards"
    return shards


def _matrix_shard_count(repo_root: Path) -> int:
    """The number of shards the workflow's matrix declares."""
    path = repo_root / WORKFLOW_FILE
    assert path.is_file(), f"{WORKFLOW_FILE} is not there"
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    job = workflow["jobs"]["python-quality"]
    shards = job["strategy"]["matrix"]["shard"]
    return len(shards)


def test_every_test_file_is_in_exactly_one_shard(repo_root: Path) -> None:
    """No file is missing from the shards, and no file is in two of them.

    A missing file is a test that CI never runs. A file in two shards is a
    test that runs twice, which is not a hole but is a lie about what the
    suite is — and it makes the shard times add up to more than the suite.

    **The shards name paths relative to the repository root** (``tests/...``),
    because the workflow hands them to pytest as arguments, and a bare file
    name is not a path pytest can find. A shard that named bare names would
    collect nothing and would look like it had passed.
    """
    files = {f"tests/{path.name}" for path in (repo_root / "tests").glob("test_*.py")}

    for platform in PLATFORMS:
        assigned = [name for shard in _shards(repo_root, platform) for name in shard]

        duplicates = {name for name in assigned if assigned.count(name) > 1}
        assert not duplicates, (
            f"on {platform}, these files are in more than one shard: {sorted(duplicates)}"
        )

        missing = files - set(assigned)
        assert not missing, (
            f"on {platform}, these test files are in no shard, so CI never runs "
            f"them: {sorted(missing)}"
        )

        unknown = set(assigned) - files
        assert not unknown, (
            f"on {platform}, these shards name files that are not test files: {sorted(unknown)}"
        )


def test_the_shards_and_the_workflow_agree_on_how_many_there_are(
    repo_root: Path,
) -> None:
    """The shard file and the workflow's matrix must have the same count.

    If the matrix declares four shards and the file names three, the fourth
    job runs a shard that does not exist — and depending on how the workflow
    reads the file, that job either runs nothing (and the coverage of the
    last shard is lost) or runs everything (and the shards are pointless).
    """
    for platform in PLATFORMS:
        assert len(_shards(repo_root, platform)) == _matrix_shard_count(repo_root), (
            f"the {platform} partition names {len(_shards(repo_root, platform))} "
            f"shards but the workflow's matrix declares {_matrix_shard_count(repo_root)}"
        )


def test_the_workflow_names_every_shard_distinctly(repo_root: Path) -> None:
    """The job's name must say which shard it is, or the gate is not a gate.

    GitHub identifies a check by its name. Four jobs that share a name are
    **one** check as far as branch protection is concerned, so a required
    check that names one of them is satisfied by whichever of them happens
    to report first — and the other three shards, which never have to pass,
    look like they did.

    This is the shape of the hole the shards were introduced to close, so it
    is watched here rather than left to a reviewer's eye.
    """
    workflow = yaml.safe_load((repo_root / WORKFLOW_FILE).read_text(encoding="utf-8"))
    name = workflow["jobs"]["python-quality"]["name"]
    assert "matrix.shard" in name, (
        "the python-quality job's name does not mention matrix.shard, so every "
        "shard's job reports under the same name and branch protection cannot "
        "tell them apart"
    )
    for key in ("matrix.os", "matrix.shard"):
        assert key in name, (
            f"the python-quality job's name does not mention {key}, so the "
            "jobs of two matrix entries share a name and branch protection "
            "cannot tell them apart"
        )


def test_the_lint_job_is_one_job_and_the_shards_do_not_repeat_it(
    repo_root: Path,
) -> None:
    """The static checks run once, in a job named ``lint``, and nowhere else.

    **The property.** ``ruff check .``, ``ruff format --check .`` and
    ``mypy`` are steps of one job, and that job has no matrix. They used to
    run inside every shard job: one lint error turned all ten checks red,
    and the same three commands were paid for ten times over. A shard job
    that ran them again would bring both costs back.

    **The name is the gate.** ``lint`` must be a name no other job shares,
    because branch protection identifies a check by name. This test can
    watch only that the workflow *offers* a job of that name and that no
    other job shares it. **Whether GitHub requires it is a branch-protection
    setting the owner controls**, and no workflow file can assert it.

    **The uniqueness read spans the whole workflows directory**, not just this
    file, and it compares *rendered* names. A collision between two workflow
    files is the same deadlock as one inside a file: `release.yml`'s
    `release-dependency-licences (matrix.os)` was a name its two platform legs
    both reported, and a witness that read one file and compared templates
    could not see it.
    """
    workflow = yaml.safe_load((repo_root / WORKFLOW_FILE).read_text(encoding="utf-8"))
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict) and jobs, "the workflow declares no jobs"

    documents = _workflow_job_names(repo_root)
    assert any(path.name == WORKFLOW_FILE.name for path, _document in documents), (
        f"{WORKFLOW_FILE} is not among the workflows the name witness reads"
    )
    job_names = [
        name for path, document in documents for name in rendered_job_names(document, path.name)
    ]
    duplicates = sorted({name for name in job_names if job_names.count(name) > 1})
    assert not duplicates, (
        f"these job names are shared by more than one job: {duplicates}. "
        "Branch protection identifies a check by its name, so jobs sharing "
        "one are one check, and a required check would be satisfied by "
        "whichever job reported first."
    )

    assert "lint" in jobs, (
        "the workflow has no job named `lint`. The static checks are a job "
        "of their own, and branch protection is asked to require that name."
    )
    lint = jobs["lint"]
    assert lint.get("name") == "lint", (
        f"the lint job's name is {lint.get('name')!r}, not `lint`; the check "
        "branch protection names would be a different one"
    )
    assert lint.get("runs-on") == "ubuntu-latest", (
        "the lint job must run on one runner; a matrix here would multiply "
        "the checks this job exists to run once"
    )
    assert "matrix" not in lint.get("strategy", {}), (
        "the lint job has a matrix, so the three static checks run more than "
        "once and report under more than one name"
    )

    def commands(job: Any) -> str:
        return "\n".join(str(step.get("run", "")) for step in job.get("steps", []))

    lint_commands = commands(lint)
    for command in ("ruff check .", "ruff format --check .", "mypy"):
        assert command in lint_commands, (
            f"the lint job does not run `{command}`. A check that moved out "
            "of the shard jobs and not into this one is a check CI no longer "
            "runs at all."
        )

    shard_commands = commands(jobs["python-quality"])
    for command in ("ruff check", "ruff format", "mypy"):
        assert command not in shard_commands, (
            f"a shard job runs `{command}`. The static checks are the lint "
            "job's, and repeating them here pays for them ten times and turns "
            "one lint error into ten red checks."
        )


def test_the_shards_are_balanced(repo_root: Path) -> None:
    """The shards should cost about the same, and the cost is recorded.

    The costs are measured **on the runner**, which is the only place the
    measurement means anything: a development machine with other work on it
    gives a different answer, and not only a different total — a different
    *order*. One file measured as the most expensive locally was the second
    cheapest on the runner.

    A shard list that is correct but lopsided is not *wrong*; it is slow, and
    it gets slow by someone adding a slow test file. The way that is noticed
    is here.
    """
    document = _shard_document(repo_root)
    costs = document.get("costs")
    assert isinstance(costs, dict) and costs, (
        "the shard file must record the measured cost of each test file, so "
        "that a shard list that has gone lopsided is noticed"
    )

    for platform in PLATFORMS:
        platform_costs = costs.get(platform)
        assert isinstance(platform_costs, dict) and platform_costs, (
            f"the shard file must record the measured cost of each test file on {platform}"
        )
        shards = _shards(repo_root, platform)
        shard_costs = [
            sum(float(platform_costs.get(Path(name).name, 0.0)) for name in shard)
            for shard in shards
        ]
        assert max(shard_costs) > 0, "the recorded costs are all zero, so they measure nothing"

        # **The property is that no file could be moved to shorten the wait.**
        # A threshold on how equal the shards are would be arbitrary, and it
        # would also be wrong: the shards cannot be equal when one file is
        # the floor. Measured on 2026-10-25, ``tests/test_cli.py`` takes 350
        # seconds on the Windows runner and no arrangement of the other files
        # can make that shard shorter.
        #
        # So the check is the one that is actually about the partition: if
        # some file, moved to the shard with the least work in it, would
        # make the wait shorter, then the partition is not the one the
        # costs imply. That is false of a partition the generator made, and
        # true of one that has been edited by hand or left over from costs
        # that have since changed.
        floor_cost = max(shard_costs)
        shortest = min(range(len(shards)), key=lambda index: shard_costs[index])
        for index, shard in enumerate(shards):
            for name in shard:
                cost = float(platform_costs.get(Path(name).name, 0.0))
                if index == shortest:
                    continue
                moved = list(shard_costs)
                moved[index] -= cost
                moved[shortest] += cost
                assert max(moved) >= floor_cost - 0.001, (
                    f"on {platform}, moving {name} into the shortest shard would "
                    f"shorten the wait from {floor_cost:.0f}s to "
                    f"{max(moved):.0f}s, so the shards are not the balance "
                    "the costs imply. Regenerate the shard file."
                )


def test_the_recorded_costs_cover_every_test_file(repo_root: Path) -> None:
    """A cost is recorded for every file, so the balance is measured on all of it.

    A file with no recorded cost counts as zero, which would make its shard
    look cheaper than it is — and the balance check above would pass on a
    number that was never measured.
    """
    files = {path.name for path in (repo_root / "tests").glob("test_*.py")}
    costs = _shard_document(repo_root).get("costs", {})
    for platform in PLATFORMS:
        platform_costs = costs.get(platform, {})
        missing = files - set(platform_costs)
        assert not missing, (
            f"on {platform}, these test files have no measured cost recorded: "
            f"{sorted(missing)}. Regenerate the shard file."
        )


def test_the_costs_belong_to_the_tree_they_were_measured_on(repo_root: Path) -> None:
    """The costs must still describe the tree, or the shards are lopsided.

    **Why this is watched.** The costs are a measurement, and a measurement
    belongs to the tree it was taken on. The rule the project already states
    is the one that applies: *a value that can change is re-measured, not
    carried forward*.

    Without this, the shard file's costs go stale silently and the shards go
    lopsided silently. That is not a hypothetical: the fix that made the
    tests copy a migrated database instead of migrating one each time took
    ``tests/test_material_schema.py`` from 383 seconds to under five, and
    the partition that had been balanced around it was not balanced any
    more -- one shard was doing five seconds of work while another did 378.

    **What is checked is the files the costs are about.** A change under
    ``src/`` or ``tests/`` can change how long a test takes; a change to a
    document cannot. The shard file itself and this file are excluded, and
    the reason is that they are **the things being changed** -- they are
    where the measurement is recorded, and a witness cannot be expected to
    be unchanged by the tree it watches.

    **A file that is new is caught by the other test**, the one that says
    every test file has a measured cost: a file nobody measured has no
    cost, and a file whose cost is unknown is not a shard that is balanced.
    """
    document = _shard_document(repo_root)
    measured_at = document.get("measured_at")
    assert measured_at, (
        "the shard file must say which commit its costs were measured at, so "
        "that a cost which no longer belongs to the tree is noticed"
    )

    changed = _changed_paths(repo_root, measured_at)
    if not changed:
        return

    # **Not every change needs a re-measurement.** A cost is only worth
    # re-measuring if the change could unbalance the partition, and the
    # partition has slack: the longest shard may grow by this much before the
    # balance is lost.
    #
    #   (longest + growth) / shortest <= BALANCE_LIMIT
    #   so  growth <= shortest * BALANCE_LIMIT - longest
    #
    # A file whose cost is smaller than that cannot unbalance the partition
    # however much its own cost moves, so the table is still good enough to
    # balance by. **A change to a test file that costs three seconds is not
    # a reason to spend a CI run**, and a run is the most expensive thing
    # this project does.
    platform_costs = document.get("costs", {})
    for platform in PLATFORMS:
        costs = platform_costs.get(platform, {})
        shards = _shards(repo_root, platform)
        heavy, reason = _files_that_need_a_remeasurement(changed, shards, costs)
        assert not heavy, (
            f"on {platform}, these files changed since the costs were measured "
            f"at {measured_at}, and {reason}:\n  "
            + "\n  ".join(heavy)
            + "\n\nRe-measure the costs on the runner and regenerate the shard "
            "file."
        )


def test_the_cost_figures_the_documents_print_are_the_costs_the_table_measures(
    repo_root: Path,
) -> None:
    """The five-class cost the documents print is what the shard table sums to.

    **Why this exists.** The evaluation job's cost was printed in three
    places -- `.github/CI.md`, `.github/workflows/python.yml` and
    `docs/plans/LC-P1-13-evaluation-ci.md` -- and every one of them had
    drifted: each carried an earlier measurement's anchor and the total
    that anchor gave, while `.github/ci-shards.json` had moved on. A value
    that can change is re-measured, not carried forward, and a figure that
    nobody recomputes is a figure that rots. The owner ruled on 2026-11-11
    that the three comments are corrected and watched rather than left as a
    recorded risk.

    **What is recomputed, and how.** The offline classes come from
    `evaluation.manifest`, not from a second literal written here: the
    per-file costs in `.github/ci-shards.json` are summed over the files
    the manifest assigns to a class that runs offline. The anchor is the
    shard file's own `measured_at`, so a re-measurement that is not
    carried into the documents is red here.

    **What it cannot watch.** The documents may print the figure in their
    own words. What is checked is that the number and the anchor they
    print are the ones the table gives.
    """
    document = _shard_document(repo_root)
    measured_at = document.get("measured_at")
    assert measured_at, "the shard file names no revision its costs were measured at"
    costs = document.get("costs", {})

    offline = {key for key, (runnable, _) in manifest.OFFLINE_CLASSES.items() if runnable}
    totals: dict[str, str] = {}
    for platform in PLATFORMS:
        table = costs.get(platform, {})
        total = sum(
            table.get(name, 0.0)
            for name, (gate_class, _clause) in manifest.FILE_ASSIGNMENTS.items()
            if gate_class in offline
        )
        totals[platform] = f"{total:.1f} s"

    ubuntu = totals["ubuntu-latest"]
    windows = totals["windows-latest"]

    for relative in (
        Path(".github") / "CI.md",
        Path(".github") / "workflows" / "python.yml",
        Path("docs") / "plans" / "LC-P1-13-evaluation-ci.md",
    ):
        text = (repo_root / relative).read_text(encoding="utf-8")
        assert measured_at in text, (
            f"{relative} prints a cost anchor the shard file does not carry; "
            f"the costs were measured at {measured_at}."
        )
        assert ubuntu in text, (
            f"{relative} does not print the Ubuntu five-class total the shard "
            f"table sums to ({ubuntu}); re-measure the costs and carry the "
            "figure into the document."
        )

    plan = (repo_root / "docs" / "plans" / "LC-P1-13-evaluation-ci.md").read_text(encoding="utf-8")
    assert windows in plan, (
        "the evaluation plan does not print the Windows five-class total the "
        f"shard table sums to ({windows})."
    )


#: The workflow whose shard matrix carries the "five, and not six" narration.
COST_NARRATION_WORKFLOW: Final[Path] = Path(".github") / "workflows" / "python.yml"

#: A date in the form this project dates a measurement with.
DATED_MEASUREMENT: Final[re.Pattern[str]] = re.compile(r"20\d\d-\d\d-\d\d")


def _shard_matrix_paragraphs(text: str) -> list[str]:
    """The comment block above a workflow's `shard:` matrix, split into paragraphs.

    The split matters because the block holds **two kinds of figure**: the costs
    the table measures now, and the figures the 2026-10-25 decision was made
    on. Both belong there — one states the current cost, the other records why
    six was rejected — and what makes them readable is that the second names its
    date. Paragraph-level reading is what distinguishes them; a search over the
    whole block would call the paragraph about 2026-10-25 a claim about today.
    """
    match = re.search(r"((?:^[ \t]*#.*\n)+)[ \t]*shard: \[", text, re.M)
    assert match is not None, (
        f"{COST_NARRATION_WORKFLOW} has no comment block above its `shard:` matrix, "
        "so there is no cost narration to compare with the table"
    )

    paragraphs: list[str] = []
    current: list[str] = []
    for raw in match.group(1).splitlines():
        line = re.sub(r"^[ \t]*#[ \t]?", "", raw).rstrip()
        if not line.strip():
            if current:
                paragraphs.append("\n".join(current))
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append("\n".join(current))
    assert paragraphs, "the comment block above the matrix holds no prose"
    return paragraphs


def test_the_cost_narration_above_the_shard_matrix_prints_the_costs_the_table_measures(
    repo_root: Path,
) -> None:
    """The floor's cost, as the workflow states it, is the cost the table records.

    **Why this is watched separately from the totals.** The existing witness
    above checks the five-class totals three documents print. This one checks the
    sentence a maintainer reads when deciding how many shards to run: `python.yml`
    calls `tests/test_cli.py` *"the floor"* and quotes its cost, and the quote sat
    next to a comment anchored at `46e2c219…` while the figures themselves came
    from the 2026-10-25 measurement — 325 Windows / 216 Ubuntu, and 216 against
    169 for five shards. That is a record that had drifted rather than a wrong
    decision: the numbers were correct for the tree they named and wrong for the
    anchor they sat beside.

    **How the two kinds of figure are told apart.** A paragraph that names the
    floor's cost **without a date** is a claim about the current costs, and must
    match the table to the precision the table records. A paragraph that names a
    date is a dated record and is left as written — the project's own rule, that
    a stale sentence in a dated snapshot is a historical fact and a stale sentence
    in a current pointer is a defect.

    **What it cannot watch.** Whether the table's costs are today's costs on a
    runner. That is what `test_the_costs_belong_to_the_tree_they_were_measured_on`
    presses for, and it is settled by a runner run the owner starts.
    """
    document = _shard_document(repo_root)
    measured_at = document.get("measured_at")
    assert measured_at, "the shard file names no revision its costs were measured at"
    costs = document.get("costs", {})

    paragraphs = _shard_matrix_paragraphs(
        (repo_root / COST_NARRATION_WORKFLOW).read_text(encoding="utf-8")
    )
    current = [
        paragraph
        for paragraph in paragraphs
        if "test_cli.py" in paragraph and not DATED_MEASUREMENT.search(paragraph)
    ]
    assert current, (
        "the shard matrix's comment names the floor file only in dated paragraphs, "
        "so it makes no current claim about its cost — which is the shape a "
        "narration takes after its figures stop being current"
    )
    assert len(current) == 1, (
        f"{len(current)} undated paragraphs state the floor's cost, so which one "
        "the workflow means is a guess"
    )
    paragraph = current[0]

    for platform in PLATFORMS:
        value = costs.get(platform, {}).get(Path("tests/test_cli.py").name)
        assert value is not None, f"the table records no {platform} cost for tests/test_cli.py"
        printed = f"{value:.2f}"
        assert printed in paragraph, (
            f"the shard matrix's comment states the floor's {platform} cost without "
            f"the figure the table records at {measured_at} ({printed}); the "
            "narration and the anchor beside it describe different trees"
        )
    assert measured_at in paragraph, (
        f"the paragraph that states the floor's current cost names no revision; the "
        f"costs it quotes were measured at {measured_at}, and a figure without its "
        "anchor is a figure that cannot be noticed going stale"
    )

    # **The dated half of the block dates itself, or its figures are orphaned.**
    # The decision figures are what identify the paragraph, not a date somewhere
    # in the block: a witness that asked only for "a dated paragraph" is satisfied
    # by a date added anywhere, including to the paragraph that states today's
    # costs — and then the 216/135/169 figures have no tree they belong to while
    # the witness stays green.
    decision = [paragraph for paragraph in paragraphs if _QUOTES_DECISION_FIGURES.search(paragraph)]
    assert decision, (
        "the five-versus-six figures (216 against 135, 1.603, 216 against 169) are no "
        "longer in the shard matrix's comment, so the reason the matrix has five legs "
        "is not recorded where the matrix is written"
    )
    assert len(decision) == 1, (
        f"{len(decision)} paragraphs quote the five-versus-six figures, so which one is "
        "the record of the decision is a guess"
    )
    assert DATED_MEASUREMENT.search(decision[0]), (
        "the paragraph that quotes the five-versus-six figures names no date, so a "
        "reader cannot tell whether they are the current costs or the measurement they "
        f"came from; the table records {measured_at} as the current one"
    )


#: The figures the 2026-10-25 five-versus-six decision was made on. They identify
#: the paragraph that records it — see the witness above for why the figures, and
#: not a date, are the identifying feature.
_QUOTES_DECISION_FIGURES: Final[re.Pattern[str]] = re.compile(r"1\.603|216 against 169")


def _files_that_need_a_remeasurement(
    changed: list[str],
    shards: list[list[str]],
    costs: dict[str, float],
) -> tuple[list[str], str]:
    """The changed files whose cost could unbalance the partition.

    **Two cases, and the second one is not a way through the check.**

    *The partition is inside the limit.* The longest shard may grow by the
    slack before the limit is lost, so a changed file costing more than the
    slack is one that could unbalance it.

    *The partition is outside the limit.* Then the imbalance is
    **structural**: one file costs more than the limit allows, and no
    arrangement of the other files brings the factor back under it.
    Measured on the Ubuntu runner, ``tests/test_cli.py`` costs 278 seconds
    of a 959-second suite, and with five shards the best factor any
    arrangement reaches is ``278 / (681 / 4) = 1.634`` — above the 1.6
    this file asks for. **No re-measurement fixes that**, so the question
    changes from *"is this file big enough to unbalance the partition"* to
    *"is this file the thing that unbalanced it"*, and only the bottleneck
    is.

    The second case is not a loophole: the bottleneck is precisely the
    file whose cost is worth measuring again, and a change to it is still
    caught. What it stops is the reading where a three-second test file is
    reported as the reason a partition is lopsided.
    """
    loads = [sum(costs.get(Path(name).name, 0.0) for name in shard) for shard in shards]
    if not loads or max(loads) <= 0:
        return [], "the recorded costs measure nothing"

    slack = min(loads) * BALANCE_LIMIT - max(loads)
    if slack > 0:
        heavy = [name for name in changed if float(costs.get(Path(name).name, 0.0)) > slack]
        return heavy, f"each costs more than the partition's slack ({slack:.0f}s)"

    longest = max(range(len(shards)), key=lambda index: loads[index])
    bottleneck = max(shards[longest], key=lambda name: costs.get(Path(name).name, 0.0))
    heavy = [name for name in changed if name == bottleneck]
    return heavy, (
        f"the partition is outside the limit by structure ({bottleneck} alone "
        f"costs {costs.get(Path(bottleneck).name, 0.0):.0f}s of a "
        f"{max(loads):.0f}s shard set), so only the bottleneck's own change "
        f"is worth measuring again"
    )


def test_a_partition_inside_the_limit_asks_about_the_slack() -> None:
    """Inside the limit, the slack decides what is worth measuring again.

    **The property.** A file that costs less than the slack cannot unbalance
    the partition however much its own cost moves, and one that costs more
    can. This is the case the rule was written for, and it is the case the
    structural one must not swallow.
    """
    shards = [
        ["tests/a.py"],
        ["tests/b.py"],
        ["tests/c.py"],
        ["tests/d.py"],
        ["tests/e.py"],
    ]
    costs = {
        "a.py": 100.0,
        "b.py": 100.0,
        "c.py": 100.0,
        "d.py": 100.0,
        "e.py": 100.0,
    }
    loads = [sum(costs[Path(name).name] for name in shard) for shard in shards]
    slack = min(loads) * BALANCE_LIMIT - max(loads)

    heavy, _ = _files_that_need_a_remeasurement(["tests/a.py"], shards, costs)
    assert heavy == ["tests/a.py"], (
        f"a file costing more than the slack ({slack:.0f}s) could unbalance the "
        "partition, and it must be reported"
    )

    heavy, _ = _files_that_need_a_remeasurement(["tests/new.py"], shards, costs)
    assert heavy == [], "a file with no recorded cost cannot unbalance anything"

    costs["new.py"] = slack
    heavy, _ = _files_that_need_a_remeasurement(["tests/new.py"], shards, costs)
    assert heavy == [], (
        f"a file costing exactly the slack ({slack:.0f}s) leaves the partition "
        "inside the limit, so it is not worth a run"
    )


def test_the_structural_case_re_asks_the_bottleneck_and_not_the_rest() -> None:
    """Outside the limit, the question is the bottleneck, not the size.

    **The property.** When one file costs more than the balance limit
    allows, no re-measurement of the other files can bring the partition
    back inside it — the imbalance is that file's. So the check names that
    file and leaves the rest alone: a change to the bottleneck is still
    caught, and a change to anything else is not reported as the reason
    the partition is lopsided.
    """
    shards = [
        ["tests/heavy.py", "tests/with_heavy.py"],
        ["tests/one.py"],
        ["tests/two.py"],
        ["tests/three.py"],
        ["tests/four.py"],
    ]
    costs = {
        "heavy.py": 278.0,
        "with_heavy.py": 1.0,
        "one.py": 170.0,
        "two.py": 170.0,
        "three.py": 170.0,
        "four.py": 170.0,
    }
    loads = [sum(costs[Path(name).name] for name in shard) for shard in shards]
    assert max(loads) / min(loads) > BALANCE_LIMIT, (
        "the case under test has to be the structural one, or it proves nothing"
    )

    heavy, reason = _files_that_need_a_remeasurement(["tests/heavy.py"], shards, costs)
    assert heavy == ["tests/heavy.py"], (
        "the bottleneck's own change must still be caught -- the structural "
        "case is not a way through the check"
    )
    assert "bottleneck" in reason, "the refusal has to say which file it means"

    heavy, _ = _files_that_need_a_remeasurement(["tests/one.py"], shards, costs)
    assert heavy == [], (
        "a file that is not the bottleneck is not why the partition is "
        "lopsided, and its change is not worth a run"
    )

    heavy, _ = _files_that_need_a_remeasurement(["src/labcairn/papers/labels.py"], shards, costs)
    assert heavy == [], "a change to production code is not the bottleneck either"


def _changed_paths(repo_root: Path, since: str) -> list[str]:
    """The files under ``src/`` and ``tests/`` that changed since ``since``.

    **The shard file and the witness that reads it are excluded**, and the
    reason is in the test above: they are where the measurement is recorded,
    and they are the things a rebalance changes.
    """
    excluded = ("--", "src/", "tests/")
    proc = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "diff",
            "--name-only",
            f"{since}..HEAD",
            *excluded,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        # **The witness must not pass when it cannot check.** A measurement
        # that cannot be located is not a measurement that says the costs are
        # still good; it is a measurement that says nothing, and a witness
        # that says nothing is a witness that has been turned off.
        #
        # This is not hypothetical. The re-measure command used to record the
        # *run id* as the commit the costs were measured at, and a run id is
        # not a git revision: `git diff` refused it, the changed-path list
        # came back as a sentence with no file in it, and every file's cost
        # was read as zero -- so the check passed without having looked at
        # anything. The command now records the run's head commit, and this
        # fails when it cannot find one.
        pytest.fail(
            f"the commit {since} is not in this checkout, so the costs cannot "
            "be checked. The shard file's measured_at must name a commit the "
            "checkout contains -- a run id, for instance, is not one."
        )
    return [
        line
        for line in proc.stdout.splitlines()
        if line.strip() and line.strip() not in EXCLUDED_FROM_THE_COST_CHECK
    ]


#: The files whose own cost is not what the table is about.
EXCLUDED_FROM_THE_COST_CHECK: frozenset[str] = frozenset({"tests/test_ci_shard_coverage.py"})


def test_the_cost_check_fails_when_it_cannot_look(repo_root: Path) -> None:
    """The check must not pass when it cannot check.

    **The witness must fail for the property it watches.** The rule being
    watched is "the costs describe the tree they were measured on", and the
    way that rule gets neutered is for the measurement's commit to become
    unresolvable -- at which point a check that read "nothing changed" would
    pass, and the costs would be describing a tree nobody can look at.

    That is not a made-up failure. The re-measure command used to record the
    *run id* as the commit, and a run id is not a git revision, so this is
    the exact shape of the mistake the check has to be immune to.
    """
    with pytest.raises(pytest.fail.Exception) as caught:
        _changed_paths(repo_root, "not-a-commit-at-all")
    assert "not in this checkout" in str(caught.value), (
        f"the failure must say the commit could not be found, not {caught.value!r}"
    )


def test_a_shard_names_files_that_exist(repo_root: Path) -> None:
    """A shard must name files that exist — a typo would run nothing.

    This is the failure that a missing-file check cannot catch on its own: a
    shard naming ``test_cl.py`` instead of ``test_cli.py`` would still cover
    every real file if another shard had it, and the typo would cost the
    coverage of the file it meant to name.
    """
    for platform in PLATFORMS:
        for index, shard in enumerate(_shards(repo_root, platform)):
            for name in shard:
                assert (repo_root / name).is_file(), (
                    f"the {platform} shard {index} names {name}, which is not a file"
                )


@pytest.mark.parametrize("platform", PLATFORMS)
def test_both_platforms_run_the_same_tests(repo_root: Path, platform: str) -> None:
    """The two partitions must cover the same files.

    The partitions are allowed to *arrange* the files differently — that is
    the point of having one per platform. They are not allowed to run
    different sets, because a test that runs on one platform and not the
    other is a test that only half of the gate checks.
    """
    sets = []
    for name in PLATFORMS:
        sets.append({n for shard in _shards(repo_root, name) for n in shard})
    assert sets[0] == sets[1], (
        "the two platforms run different tests: "
        f"only on ubuntu {sorted(sets[0] - sets[1])}, "
        f"only on windows {sorted(sets[1] - sets[0])}"
    )


def test_the_evaluation_job_runs_the_offline_classes_on_a_schedule(
    repo_root: Path,
) -> None:
    """The evaluation harness is in CI without making a pull request red.

    **The property.** A job named ``evaluation`` runs
    ``python -m tests.evaluation`` over **exactly** the classes the harness
    can run offline, on a schedule event only. The fifth protocol class is
    named nowhere in the command: it cannot run offline, and the owner's
    2026-10-28 ruling gives it a different workflow (``provider-smoke.yml``).

    **Why the class list is computed and not spelled.** The offline set is
    ``manifest.OFFLINE_CLASSES``; a second literal in the workflow would
    drift from it. The list must not be shortened either: a blocker is held
    only when every one of its witnesses was collected and passed, and the
    witnesses span all five offline classes. ``--classes unit`` passed
    1789/1789 and still exited 1, because five of the six blockers became
    NOT_EVALUATED; that was measured on 2026-11-03.

    **Why the trigger and the guards are watched.** The five classes cost
    1622.3 s on an Ubuntu runner at
    ``46e2c21918286a723f9d07d5409d0e52e7551a85`` (the costs in
    ``.github/ci-shards.json``), so a pull-request job would add about
    twelve minutes to the wall clock on top of the ten shard jobs that
    already run the same files. A schedule that also ran ``lint`` and the
    ten shards would multiply the cost instead of moving it. The guards on
    those jobs are part of the property, not incidental.

    **What this cannot watch.** GitHub fires a schedule only from the
    default branch, and branch protection is configured outside the
    repository. The test can watch what the workflow offers; it cannot watch
    what GitHub does with it.
    """
    workflow = yaml.safe_load((repo_root / WORKFLOW_FILE).read_text(encoding="utf-8"))

    # PyYAML reads the YAML 1.1 bare `on` as the boolean True.
    triggers = workflow.get("on", workflow.get(True))
    assert isinstance(triggers, dict), "the workflow has no trigger mapping"
    assert "schedule" in triggers, (
        "the evaluation job is gated on a schedule event, and the workflow "
        "declares no schedule trigger"
    )

    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    assert "evaluation" in jobs, "the workflow has no evaluation job"
    job = jobs["evaluation"]
    assert isinstance(job, dict)
    assert job.get("name") == "evaluation", (
        "the evaluation job's check name is not exactly `evaluation`; branch "
        "protection identifies a check by its name"
    )
    assert job.get("if") == "${{ github.event_name == 'schedule' }}", (
        "the evaluation job does not say it runs only on the schedule event"
    )
    assert job.get("runs-on") == "ubuntu-latest", (
        "the evaluation job must run on one Ubuntu runner; the five classes "
        "cost about 75 minutes on Windows against about 27 on Ubuntu"
    )
    assert "strategy" not in job, "the evaluation job must not have a matrix"

    offline = [key for key, (runnable, _) in manifest.OFFLINE_CLASSES.items() if runnable]
    expected = "--classes " + ",".join(offline)
    commands = [
        str(step.get("run", ""))
        for step in job["steps"]
        if isinstance(step, dict) and "run" in step
    ]
    harness = [command for command in commands if "python -m tests.evaluation" in command]
    assert len(harness) == 1, (
        "the evaluation job must run the harness exactly once, "
        f"and it runs it {len(harness)} time(s)"
    )
    command = harness[0]
    assert expected in command, (
        f"the harness command does not select the offline classes: {expected!r} "
        f"is not in {command!r}"
    )
    assert "real_model_smoke" not in command, (
        "the harness command names the fifth protocol class, which cannot run "
        "offline; provider-smoke.yml is its ruled shape"
    )
    assert '--out "$RUNNER_TEMP/evaluation-report"' in command, (
        "the harness report must be written to the directory the artifact "
        "step uploads, under the runner's temp and outside the checkout"
    )

    uploads = [
        step
        for step in job["steps"]
        if isinstance(step, dict) and "upload-artifact" in str(step.get("uses", ""))
    ]
    assert len(uploads) == 1, (
        f"the evaluation job must upload its report exactly once, and it uploads {len(uploads)}"
    )
    upload = uploads[0]
    assert upload.get("if") == "always()", (
        "the report must be uploaded whether the harness passed or failed; "
        "a failed run is exactly when the blocker table is read"
    )
    settings = upload["with"]
    assert settings["path"] == "${{ runner.temp }}/evaluation-report", (
        "the artifact path is not the harness report directory under the "
        "runner's temp; a path over the checkout could sweep the tree into a "
        "downloadable bundle"
    )

    for guarded in ("lint", "python-quality"):
        guard = str(jobs[guarded].get("if", ""))
        assert "github.event_name != 'schedule'" in guard, (
            f"{guarded} would also run on the schedule event, so a scheduled "
            "run would spend twelve jobs instead of one — `lint` plus the ten "
            "shard legs, on top of `evaluation`"
        )

    names = [str(entry.get("name", "")) for entry in jobs.values()]
    assert len(names) == len(set(names)), (
        f"two jobs share a check name, and branch protection cannot tell them apart: {names}"
    )


# ---------------------------------------------------------------------------
# Triggers, guards and version pins across every workflow
# ---------------------------------------------------------------------------

#: An event named by a job-level `if:` guard: `github.event_name == 'schedule'`
#: or `github.event_name != 'schedule'`.
EVENT_NAME_GUARD: Final[re.Pattern[str]] = re.compile(
    r"github\.event_name\s*(?:==|!=)\s*'([a-z_]+)'"
)


def _declared_triggers(document: dict[Any, Any]) -> set[str]:
    """The events a workflow's `on:` declares.

    PyYAML reads YAML 1.1's bare `on` as the boolean `True`, the same handling
    `tests/test_shell_ci.py::_triggers` and the rescan script use, and the key
    type has to say so: a `dict[str, Any]` annotation makes `document.get(True)`
    a call mypy rightly refuses. `on:` may also be the scalar form (`on: push`),
    which declares exactly one event.
    """
    triggers = document.get("on", document.get(True))
    if isinstance(triggers, dict):
        return {str(key) for key in triggers}
    if isinstance(triggers, (str, list)):
        values = [triggers] if isinstance(triggers, str) else triggers
        return {str(value) for value in values}
    return set()


def _guards_naming_an_undeclared_event(document: dict[str, Any]) -> list[str]:
    """Every job `if:` in a workflow that names an event the file never triggers.

    **Why a guard like this is a defect.** `github.event_name` inside a workflow
    can only be one of the events that workflow's `on:` declares. A guard naming
    any other event is therefore true on every run of that job — it cannot be
    false, so it cannot be load-bearing, and the comment written for it
    describes a run the file cannot have. That is the shape CLAUDE.md calls
    *"a defence without a witness is dead code"*, with the witness replaced by
    an event that never arrives. `shell.yml` carried exactly this until
    2026-11-11: `if: github.event_name != 'schedule'` in a file that declares
    only `push` and `pull_request`.

    **What this cannot watch.** A guard whose event *is* declared. Whether the
    guard is worth having — whether a scheduled run should spend one job or
    twelve — is a design decision the workflow's own comment records, and
    `test_the_evaluation_job_runs_the_offline_classes_on_a_schedule` watches
    `python.yml`'s three guards individually.
    """
    declared = _declared_triggers(document)
    offenders: list[str] = []
    jobs = document.get("jobs")
    if not isinstance(jobs, dict):
        return offenders
    for job_key, job in jobs.items():
        if not isinstance(job, dict):
            continue
        for event in EVENT_NAME_GUARD.findall(str(job.get("if", ""))):
            if event not in declared:
                offenders.append(
                    f"job {job_key}: `if:` names {event!r}, which this workflow's "
                    f"`on:` ({sorted(declared)}) never delivers, so the condition "
                    "is true on every run"
                )
    return offenders


def test_no_workflow_guards_against_an_event_its_triggers_never_deliver(
    repo_root: Path,
) -> None:
    """A job `if:` may only name an event the workflow's `on:` declares.

    The read spans `.github/workflows/`: a guard copied from one workflow into
    another is exactly how `shell.yml` got a `schedule` guard without a
    `schedule` trigger (`git show 19fee54` introduced the guard and its
    misleading comment together on 2026-11-11, lifted from `python.yml`, where
    the trigger exists and the guard does work). No witness in the tree put a
    job's `if` beside the file's trigger set before this one.
    """
    offenders: list[str] = []
    for path, document in _workflow_job_names(repo_root):
        offenders.extend(
            f"{path.name}: {offence}" for offence in _guards_naming_an_undeclared_event(document)
        )
    assert not offenders, (
        "these job guards name an event their workflow never triggers, so they "
        "are dead code and their comments describe a run that cannot happen:\n  "
        + "\n  ".join(offenders)
    )


def test_the_guard_witness_fails_on_a_dead_schedule_guard() -> None:
    """The witness must fail for the property, against the shape it exists for.

    **The demonstration.** `shell.yml`'s deleted guard, rebuilt: `push` to
    `main` plus an unfiltered `pull_request`, and a job that says
    `github.event_name != 'schedule'`. The condition is true on every run of
    that job, so it is not a guard. A witness that only checked the triggers
    (`test_the_shell_workflow_exists_and_runs_on_a_pull_request` reads
    `shell.yml`'s triggers and never its `if`) would call that tree clean, and
    the dead guard would come back with its misleading comment.

    **The control beside it.** The same guard in a workflow that *does* declare
    `schedule` — `python.yml`'s real shape — must not be reported. Without the
    control, the witness would flag every guard, and a witness that flags
    everything is indistinguishable from one that flags nothing.
    """
    dead_guard = {
        "on": {"push": {"branches": ["main"]}, "pull_request": None},
        "jobs": {
            "shell-test": {"name": "shell-test", "if": "${{ github.event_name != 'schedule' }}"}
        },
    }
    offenders = _guards_naming_an_undeclared_event(dead_guard)
    assert len(offenders) == 1, (
        f"a guard against an undeclared event reported {offenders}; the witness "
        "must catch exactly this shape, since it is the shape `shell.yml` had"
    )
    assert "schedule" in offenders[0], offenders[0]

    live_guard = {
        "on": {
            "push": {"branches": ["main"]},
            "pull_request": None,
            "schedule": [{"cron": "17 3 * * 1"}],
        },
        "jobs": {
            "lint": {"name": "lint", "if": "${{ github.event_name != 'schedule' }}"},
            "evaluation": {"name": "evaluation", "if": "${{ github.event_name == 'schedule' }}"},
        },
    }
    assert _guards_naming_an_undeclared_event(live_guard) == [], (
        "a guard naming a declared event was reported: "
        f"{_guards_naming_an_undeclared_event(live_guard)}. The control is what "
        "says the witness reads the trigger set rather than rejecting every guard"
    )


#: `(action, step key)` → the pin name a witness compares across files. The
#: pair is what makes the key meaningful: `version` means the uv release under
#: setup-uv and the pnpm release under pnpm/action-setup, and a witness that
#: compared `version` alone would call those two a disagreement.
_PINNED_STEP_KEYS: Final[dict[tuple[str, str], str]] = {
    ("astral-sh/setup-uv", "version"): "uv (setup-uv `version`)",
    ("pnpm/action-setup", "version"): "pnpm (action-setup `version`)",
    ("actions/setup-node", "node-version"): "Node (`node-version`)",
}

#: `env:` keys that name a tool version or its checksum, whatever step carries
#: them. `GITLEAKS_VERSION: 8.30.1` and `GITLEAKS_SHA256_LINUX_X64` sit under a
#: `run:` step with no `uses:`, so they cannot be keyed by action.
_PINNED_ENV_KEYS: Final[frozenset[str]] = frozenset(
    {"GITLEAKS_VERSION", "GITLEAKS_SHA256_LINUX_X64"}
)


def _step_pins_and_action_tags(
    documents: list[tuple[Path, dict[str, Any]]],
) -> dict[str, list[tuple[str, str]]]:
    """Every tool pin the workflows declare, as pin name → where it is written.

    Two shapes are collected. `uses: owner/repo@vX` — the action's own version,
    repeated per file. On 2026-11-11 the directory held `actions/checkout@v7`
    eleven times, `astral-sh/setup-uv@v10.3.0` nine, `actions/setup-python@v7`
    nine, `actions/upload-artifact@v7` seven, `actions/setup-node@v7` four and
    `pnpm/action-setup@v6` three. And a step's `with:` / `env:` value naming a
    pinned tool version or checksum — `version: "0.11.21"` under setup-uv,
    `version: 9.15.9` under pnpm/action-setup, `node-version: 24.16.0`, and the
    gitleaks pair in `security.yml` and `release.yml`.

    **Occurrences, not a set of values.** Each entry is `(file, value)`, because
    a witness about duplication has to be able to say how many times a pin was
    written. Comparing a set of values would report one value for a pin written
    six times and one value for a pin written once, and the two are different
    situations: the first is a pin that can drift, the second cannot.

    **A name is only collected where it appears.** `pnpm version` does not
    exist in `python.yml`, and that is not a missing pin — the job installs no
    pnpm. The property is that a pin which *is* written is written the same way
    everywhere, not that every file declares every tool.
    """
    found: dict[str, list[tuple[str, str]]] = {}

    def record(name: str, file_name: str, value: Any) -> None:
        found.setdefault(name, []).append((file_name, str(value)))

    for path, document in documents:
        jobs = document.get("jobs")
        if not isinstance(jobs, dict):
            continue
        for job in jobs.values():
            if not isinstance(job, dict):
                continue
            for step in job.get("steps") or []:
                if not isinstance(step, dict):
                    continue
                uses = str(step.get("uses", ""))
                action, _, tag = uses.partition("@")
                if uses and tag:
                    record(f"action {action}", path.name, tag)
                for section in ("with", "env"):
                    values = step.get(section)
                    if not isinstance(values, dict):
                        continue
                    for key, value in values.items():
                        if value is None:
                            continue
                        named = _PINNED_STEP_KEYS.get((action, key))
                        if named is None and key in _PINNED_ENV_KEYS:
                            named = f"gitleaks ({key})"
                        if named is not None:
                            record(named, path.name, value)
    return found


def _pin_values(pins: dict[str, list[tuple[str, str]]], name: str) -> list[str]:
    """The distinct values one pin name is written with."""
    return sorted({value for _file, value in pins.get(name, [])})


def _pin_writes(pins: dict[str, list[tuple[str, str]]], name: str) -> int:
    """How many times one pin name is written across the directory."""
    return len(pins.get(name, []))


def test_a_tool_pinned_in_two_workflows_is_pinned_to_the_same_thing(
    repo_root: Path,
) -> None:
    """A repeated pin is one pin, or the second copy is a second version.

    **Why this needs watching.** `GITLEAKS_VERSION: 8.30.1` and its
    `GITLEAKS_SHA256_LINUX_X64` are written twice (`security.yml:71-73` and
    `release.yml:313-316`), `astral-sh/setup-uv`'s `version: "0.11.21"` in six
    files, `pnpm version: 9.15.9` and `node-version: 24.16.0` in three each, and
    every action tag once per use. **Nothing read them**: on 2026-11-11 a grep
    for `GITLEAKS_VERSION` and `GITLEAKS_SHA256` across `tests/` and
    `.github/*.py` returned nothing, so bumping one file's gitleaks release left
    the other pinned to the older one and green. `tests/test_no_reference_leakage.py:1296`
    and `:1440` go further and claim a behaviour of gitleaks **8.30.1** —
    *"measured against the pinned binary"* — while no witness connects that
    claim to the version either workflow actually installs. The same reasoning
    is why the checksum is compared: a version and its digest that were bumped
    apart would download one release and verify another.

    **What is compared, and what is not.** Only a pin that appears more than
    once has a value to agree on, and this test requires the duplicated pins it
    names to actually be duplicated — a witness that watches nothing because
    the names vanished reads as green. It does not restructure the workflows:
    the duplication stays, and the duplication is what stops drifting.
    """
    pins = _step_pins_and_action_tags(_workflow_job_names(repo_root))

    disagreements = {
        name: sorted({value for _file, value in writes})
        for name, writes in pins.items()
        if len({value for _file, value in writes}) > 1
    }
    assert not disagreements, (
        "these pins are written differently in different workflows: "
        + "; ".join(f"{name} as {values}" for name, values in sorted(disagreements.items()))
        + ". Two workflows then install two versions of one tool, and a claim "
        "measured against one of them describes neither."
    )

    for name in sorted(DUPLICATED_PINS):
        assert name in pins, (
            f"{name} is no longer a pin any workflow writes, so this witness is "
            "watching nothing. Either the pin moved to one place — then delete "
            "it from here — or it was dropped, and the tool is unpinned."
        )
        assert _pin_writes(pins, name) > 1, (
            f"{name} is written {_pin_writes(pins, name)} time; a pin written once "
            "has nothing to agree with, and this witness exists to keep the "
            "duplicated ones from drifting"
        )


def test_the_duplicated_gitleaks_pin_is_one_version_and_one_checksum(
    repo_root: Path,
) -> None:
    """`security.yml` and `release.yml` install the same gitleaks.

    The scan `release.yml` runs is described in its own comment as *"the same
    scan `security.yml` runs"*, and the two install blocks are near-duplicates:
    the same version, the same checksum, a different following step. The
    general witness above catches a bump in one file; this one names the pair,
    because the claim that pairs them is the one a reader is meant to trust.

    **The claim it also ties.** `tests/test_no_reference_leakage.py` measures a
    gitleaks behaviour against *"the pinned binary"* and names the version. That
    version is now read from the workflows rather than restated, so a bump in
    the workflows makes the mismatch visible here instead of leaving the claim
    pointing at a release nothing installs.
    """
    pins = _step_pins_and_action_tags(_workflow_job_names(repo_root))
    version_writes = pins.get("gitleaks (GITLEAKS_VERSION)", [])
    checksum_writes = pins.get("gitleaks (GITLEAKS_SHA256_LINUX_X64)", [])
    assert len(version_writes) >= 2 and len(checksum_writes) >= 2, (
        f"gitleaks is pinned {len(version_writes)} time(s) and its checksum "
        f"{len(checksum_writes)} time(s); the two workflows that run the scan "
        "are expected to both write both"
    )
    version_values = sorted({value for _file, value in version_writes})
    checksum_values = sorted({value for _file, value in checksum_writes})
    assert len(version_values) == 1 and len(checksum_values) == 1, (
        f"the workflows that run the secret scan install gitleaks {version_values} "
        f"and verify against {checksum_values}"
    )
    pinned_version = version_values[0]
    pinned_checksum = checksum_values[0]

    # The claim is read out of the file that makes it, rather than restated
    # here. A copy of "8.30.1" in this witness would compare the witness with
    # itself and miss the drift between the claim and the pinned binary.
    claims = {
        match.group(1)
        for line in (repo_root / "tests" / "test_no_reference_leakage.py")
        .read_text(encoding="utf-8")
        .splitlines()
        if (match := re.search(r"[Gg]itleaks (\d+\.\d+\.\d+)", line))
    }
    assert claims, "no witness names a gitleaks version any more"
    assert claims == {pinned_version}, (
        f"tests/test_no_reference_leakage.py measures gitleaks {sorted(claims)} while "
        f"the workflows install {pinned_version}. A claim 'measured against the "
        "pinned binary' must name the pinned binary."
    )
    assert re.fullmatch(r"[0-9a-f]{64}", pinned_checksum), (
        f"the pinned checksum is {pinned_checksum!r}, not a 64-hex SHA-256"
    )


#: The pins the tree writes more than once, measured on 2026-11-11 against the
#: eight files in `.github/workflows/`: uv's `version` in six files, pnpm's and
#: Node's in three each, gitleaks' version and checksum in two each, and six
#: action tags repeated per use. They are named so that the witness cannot go
#: vacuous: if a pin stops being written, the witness says so instead of passing
#: on an empty comparison.
DUPLICATED_PINS: Final[frozenset[str]] = frozenset(
    {
        "uv (setup-uv `version`)",
        "pnpm (action-setup `version`)",
        "Node (`node-version`)",
        "gitleaks (GITLEAKS_VERSION)",
        "gitleaks (GITLEAKS_SHA256_LINUX_X64)",
        "action actions/checkout",
        "action actions/setup-node",
        "action actions/setup-python",
        "action actions/upload-artifact",
        "action astral-sh/setup-uv",
        "action pnpm/action-setup",
    }
)


def test_the_workflow_tool_pins_satisfy_the_pins_the_project_declares(
    repo_root: Path,
) -> None:
    """CI's literal pins sit inside the ranges the project declares.

    **The third copy of a pin.** uv's floor lives in three places:
    `pyproject.toml`'s `[tool.uv] required-version = ">=0.11.21,<0.12"`, each
    setup-uv step's `version: "0.11.21"`, and `lockfiles.yml`'s comment. Node
    and pnpm live in `web/package.json` (`engines`, `packageManager`) and —
    deliberately, and said so at `web.yml:17-19` and `lockfiles.yml:27-28` —
    also as literals in the workflows. A literal that drifts below the declared
    range makes CI install a tool the project itself refuses: `uv` would refuse
    to run at all, and the shard jobs would fail for a reason no test names.

    **The comparison is the repository's own.** `scripts/outsider_path.py`'s
    `satisfies` is the implementation the web-environment check already uses,
    and `test_outsider_path.py::test_the_version_comparison_reads_the_ranges_the_repository_writes`
    watches it. Reading the ranges through it is the alternative to writing a
    second range parser here that could disagree with the first. The one
    adaptation is the separator: `satisfies` splits comparators on spaces and
    PEP 440 writes them with commas, so the comparators are split on both —
    `test_the_range_split_reads_the_specifier_form_the_project_writes` below
    watches that adaptation rather than assuming it.

    **What it cannot watch.** Whether `uv` on the runner is the version the
    step asks for. That is a runner fact; this is the declaration-side check
    that the two ranges the repository writes do not contradict each other.
    """
    pins = _step_pins_and_action_tags(_workflow_job_names(repo_root))
    satisfies = _load_version_comparison()

    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    web = json.loads((repo_root / "web" / "package.json").read_text(encoding="utf-8"))

    checked = (
        ("uv (setup-uv `version`)", pyproject["tool"]["uv"]["required-version"]),
        ("pnpm (action-setup `version`)", web["engines"]["pnpm"]),
        ("pnpm (action-setup `version`)", f"={web['packageManager'].split('@')[1]}"),
        ("Node (`node-version`)", web["engines"]["node"]),
    )
    for name, requirement in checked:
        values = _pin_values(pins, name)
        assert values, f"{name} is written by no workflow, so this check reads nothing"
        for value in values:
            for comparator in _comparators(requirement):
                verdict = satisfies(value, comparator)
                assert verdict is True, (
                    f"{name} is pinned to {value}, which does not satisfy "
                    f"{comparator!r} from the declared range {requirement!r} "
                    f"(the comparison said {verdict!r}; `None` means it could not "
                    "read the comparator)"
                )


def _comparators(requirement: str) -> list[str]:
    """One declared range, as the comparators `satisfies` reads.

    `satisfies` splits a range on spaces; `pyproject.toml` writes uv's range
    with commas (`">=0.11.21,<0.12"`). Splitting on both separators is what
    makes one implementation read both forms. A range that splits into nothing
    is reported rather than silently treated as satisfied.
    """
    comparators = [part for part in re.split(r"[,\s]+", requirement.strip()) if part]
    assert comparators, f"the declared range {requirement!r} names no comparator"
    return comparators


def test_the_range_split_reads_the_specifier_form_the_project_writes() -> None:
    """The comma/space adaptation is watched, with its control.

    **Why this is a witness and not a helper detail.** The adaptation is the
    only place this file interprets a range. If `_comparators` were wrong — say
    it split on commas only — uv's range would read as two comparators and the
    Node range `">=24.16.0 <25"` as one string the helper reports `None` for,
    and the check would fail for a reason that has nothing to do with the pin.
    **The control:** a range the helper cannot read at all must stay unreadable
    rather than becoming satisfied, the way `test_outsider_path.py` requires of
    `satisfies` itself.
    """
    assert _comparators(">=0.11.21,<0.12") == [">=0.11.21", "<0.12"]
    assert _comparators(">=24.16.0 <25") == [">=24.16.0", "<25"]
    satisfies = _load_version_comparison()
    assert satisfies("0.11.21", ">=0.11.21") is True
    assert satisfies("0.11.20", ">=0.11.21") is False
    assert satisfies("0.12.0", "<0.12") is False
    # The control: an unparseable range is `None`, not a pass.
    assert satisfies("24.16.0", "^24.16.0") is None
    with pytest.raises(AssertionError):
        # An empty declared range is refused, not read as "no comparators to
        # fail", which would satisfy anything.
        _comparators("")


def _load_version_comparison() -> Any:
    """`scripts/outsider_path.py`'s `satisfies`, loaded the way the tool runs it."""
    script = Path(__file__).resolve().parent.parent / "scripts" / "outsider_path.py"
    spec = importlib.util.spec_from_file_location("outsider_path_for_pin_witness", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    satisfies: Any = module.satisfies
    return satisfies


def test_a_pin_witness_that_reads_nothing_is_not_a_green_witness() -> None:
    """The pin reader is driven with a tree whose pins disagree.

    **The failure this closes.** A reader that collected nothing would satisfy
    `test_a_tool_pinned_in_two_workflows_is_pinned_to_the_same_thing` by
    vacuity — no disagreement, no values, green — which is the shape this
    project calls a witness that has been turned off. So the same reader is
    driven with a synthetic tree, and the answer it gives there must differ from
    the one it gives for the real tree.

    **What the synthetic tree says.** Two workflows pinning uv differently, and
    two writing gitleaks' version under an `env:` block (where no `uses:` keys
    anything). Both must be reported, by name, with both values; the action tag
    must be collected too, since a tag that drifted per file is the same defect
    in a different shape.
    """
    synthetic: list[tuple[Path, dict[str, Any]]] = [
        (
            Path("security.yml"),
            {
                "on": {"pull_request": None},
                "jobs": {
                    "secret-scan": {
                        "steps": [
                            {"uses": "astral-sh/setup-uv@v10.3.0", "with": {"version": "0.11.21"}},
                            {
                                "name": "install gitleaks",
                                "env": {
                                    "GITLEAKS_VERSION": "8.30.1",
                                    "GITLEAKS_SHA256_LINUX_X64": "a" * 64,
                                },
                                "run": "curl …",
                            },
                        ]
                    }
                },
            },
        ),
        (
            Path("release.yml"),
            {
                "on": {"pull_request": None},
                "jobs": {
                    "release-contents": {
                        "steps": [
                            {"uses": "astral-sh/setup-uv@v10.4.0", "with": {"version": "0.12.0"}},
                            {
                                "name": "install gitleaks",
                                "env": {
                                    "GITLEAKS_VERSION": "8.30.1",
                                    "GITLEAKS_SHA256_LINUX_X64": "b" * 64,
                                },
                                "run": "curl …",
                            },
                        ]
                    }
                },
            },
        ),
    ]
    pins = _step_pins_and_action_tags(synthetic)

    assert _pin_values(pins, "uv (setup-uv `version`)") == ["0.11.21", "0.12.0"], (
        "two workflows pinning uv differently were read as "
        f"{_pin_values(pins, 'uv (setup-uv `version`)')}; the disagreement is the "
        "defect the witness exists to report"
    )
    assert _pin_values(pins, "action astral-sh/setup-uv") == ["v10.3.0", "v10.4.0"], (
        f"the action tags were read as {_pin_values(pins, 'action astral-sh/setup-uv')}"
    )
    assert len(_pin_values(pins, "gitleaks (GITLEAKS_SHA256_LINUX_X64)")) == 2, (
        "two checksums for one version must be two values — a version and a "
        "digest bumped apart would download one release and verify another"
    )
    assert _pin_values(pins, "gitleaks (GITLEAKS_VERSION)") == ["8.30.1"], (
        "the version both files agree on was not read as one value"
    )


# ---------------------------------------------------------------------------
# The records about branch protection, watched against the tree
# ---------------------------------------------------------------------------

#: The record that keeps the dated reading of branch protection.
REQUIRED_CHECK_RECORD: Final[Path] = Path(".github") / "CI.md"

#: The markers around the list of required contexts. A record a witness reads
#: has to have an edge: "the bullet lines of a section" would sweep in the
#: prose around it, and a witness that reads prose as data is a witness that
#: reads whatever was written last.
REQUIRED_LIST_BEGIN: Final[str] = "<!-- required-status-checks:begin"
REQUIRED_LIST_END: Final[str] = "<!-- required-status-checks:end -->"

#: A full git revision, as every anchor in this repository must be written.
FULL_SHA: Final[re.Pattern[str]] = re.compile(r"\b[0-9a-f]{40}\b")


def _required_contexts(repo_root: Path) -> tuple[list[str], str]:
    """The required contexts `.github/CI.md` lists, and the revision it names.

    Read from the marked block rather than from prose, for the reason given on
    the markers. The anchor is taken from the begin marker itself, so a list
    and the revision it was read at cannot be edited apart.
    """
    text = (repo_root / REQUIRED_CHECK_RECORD).read_text(encoding="utf-8")
    begin = text.find(REQUIRED_LIST_BEGIN)
    end = text.find(REQUIRED_LIST_END)
    assert begin != -1 and end > begin, (
        f"{REQUIRED_CHECK_RECORD} carries no {REQUIRED_LIST_BEGIN} … "
        f"{REQUIRED_LIST_END} block, so the required-check set it describes is "
        "prose rather than a reading"
    )
    anchor_match = FULL_SHA.search(text[begin : begin + 300])
    assert anchor_match is not None, (
        f"the required-check block's begin marker must name the full revision it "
        f"was measured at; found {text[begin : begin + 120]!r}"
    )
    contexts = [
        match.group(1)
        for line in text[begin:end].splitlines()
        if (match := re.match(r"\s*-\s*`([^`]+)`\s*$", line))
    ]
    assert contexts, "the required-check block lists no contexts"
    return contexts, anchor_match.group(0)


def test_every_required_check_the_record_lists_is_a_name_a_job_reports(
    repo_root: Path,
) -> None:
    """Branch protection's list and the workflows' names are the same set of names.

    **The failure this closes.** A required check is identified by its name, and
    GitHub waits for a name whether or not any job reports it. A record that
    carries an old name — a renamed job, a dropped matrix axis, a renamed
    workflow — is a merge that can never happen, and the tree would be green
    while it waited. The record is also the only place the repository keeps the
    required set at all, so before this witness nothing compared it to anything.

    **The direction it can check, and the one it cannot.** What can be checked
    from inside the repository is that **every name the record lists is a name a
    job in `.github/workflows/` reports**, rendered per matrix leg. The other
    direction — a job whose name is *not* required — is the owner's decision and
    is deliberately not asserted: `evaluation`, `real-model smoke`, the three
    `release-…` jobs and both `shell-test (…)` legs are reported without being
    required, and `.github/CI.md` records that as the owner's call.

    **The anchor is checked too.** A dated reading that names a revision no
    longer in the checkout is not dated, so the revision the block carries must
    resolve to a commit here.
    """
    contexts, anchor = _required_contexts(repo_root)
    reported = {
        name
        for _path, document in _workflow_job_names(repo_root)
        for name in rendered_job_names(document, _path.name)
    }
    missing = sorted(set(contexts) - reported)
    assert not missing, (
        f"branch protection requires {missing}, and no job in {WORKFLOWS_DIR} "
        "reports those names. A required check that no job reports is a check "
        "GitHub waits for forever. Either the record is stale — re-read it with "
        "`gh api repos/gg320324492-lgtm/labcairn/branches/main/protection` — or "
        "the rename was the mistake."
    )

    proc = subprocess.run(
        ["git", "-C", str(repo_root), "cat-file", "-t", anchor],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0 and proc.stdout.strip() == "commit", (
        f"the required-check record is anchored at {anchor}, which is not a "
        "commit in this checkout — a dated reading has to be a reading of a tree "
        "this repository can still show"
    )


def test_the_current_pointers_agree_with_the_measured_required_check_set(
    repo_root: Path,
) -> None:
    """`CLAUDE.md` and the handoff do not contradict the dated reading.

    **Why this is watched.** Three current-pointer files stated the required-check
    set, and all three had drifted from it. `CLAUDE.md` said "the sixteen required
    checks" and that `lint` "is not a required check until the owner adds it"; the
    handoff repeated the second sentence; `docs/REPOSITORY-MAP.md` said the
    workflow directory holds seven workflows. The measurement on 2026-11-11 gave
    **fifteen** contexts, **including `lint`**, and **eight** workflow files. A
    current pointer that is wrong is worse than no pointer: a reader follows it.

    **How it is checked, rather than restated.** The anchor requirement is
    **paragraph-scoped**, which is the whole point of the shape. A file-wide
    `anchor in text` is satisfied by an anchor sitting anywhere in the document,
    and a mutation that deleted the revision from the sentence stating the count
    left another mention in place and stayed green — the first mutation run caught
    exactly that. So every paragraph that makes a required-set claim must carry
    the revision the record was measured at, in that paragraph's own text.

    **What counts as a claim, and why the wording of the records matters.** The
    detector reads a *count next to the phrase* (`fifteen required checks`), the
    phrase `required contexts`, and `is a required check`. Those three are chosen
    so that a paragraph about shard cost — "every other required check together
    came to under two minutes" — is not a required-set claim and is not asked for
    an anchor. The records were written to use those forms rather than a loose
    paraphrase, because a detector that reads a document's claims only works if the
    claims have a shape it can see; that is also why the count in `CLAUDE.md` moved
    into the same paragraph as its revision.

    **What it cannot watch.** Whether the owner changes the required set tomorrow.
    That is a GitHub setting; what is watched is that the tree's own sentences
    are not left behind. And a **dated** plan record — `LC-P1-11-12-task-breakdown.md`
    and `P2-AMD-01-impact-matrix.md` still say "the sixteen required checks" — is a
    historical record of what protection was when it was written, deliberately not
    rewritten here.
    """
    _contexts, anchor = _required_contexts(repo_root)

    for relative in CURRENT_POINTER_FILES:
        text = (repo_root / relative).read_text(encoding="utf-8")
        claiming = [
            paragraph for paragraph in text.split("\n\n") if _makes_required_claim(paragraph)
        ]
        assert claiming, (
            f"{relative} no longer states anything about required checks, so this "
            "witness reads nothing. If the claim moved out of the pointers, delete "
            "the file from CURRENT_POINTER_FILES rather than leaving a green witness "
            "over an empty one."
        )
        unanchored = [paragraph for paragraph in claiming if anchor not in paragraph]
        assert not unanchored, (
            f"{relative} makes {len(unanchored)} required-set claim(s) without naming "
            f"the revision `{anchor}` in the same paragraph: "
            f"{[p[:70] for p in unanchored]}. A count or a required/optional claim "
            "without its own anchor is a memory — another paragraph's anchor cannot "
            "vouch for it."
        )
        stale = [phrase for phrase in STALE_REQUIRED_CHECK_PHRASES if phrase in text]
        assert not stale, (
            f"{relative} still says {stale}, which the measured set contradicts: "
            f"`lint` is among the required contexts recorded at {anchor}. "
            "Correct the sentence against the measurement rather than leaving "
            "both in the tree."
        )


#: The current pointers that state the required-check set. Dated plan records are
#: deliberately absent: a stale sentence in a dated snapshot is a historical fact.
CURRENT_POINTER_FILES: Final[tuple[Path, ...]] = (
    Path("CLAUDE.md"),
    Path("docs") / "handoff" / "CURRENT.md",
    Path("docs") / "REPOSITORY-MAP.md",
)

#: Sentences the 2026-11-11 measurement contradicts, so they cannot stay in a
#: current pointer beside the reading that contradicts them.
STALE_REQUIRED_CHECK_PHRASES: Final[tuple[str, ...]] = (
    "sixteen required checks",
    "`lint` is not a required check",
    "not a required check until the owner adds",
)

_NUMBER_WORDS: Final[str] = "|".join(
    [
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
        "eighteen",
        "nineteen",
        r"\d{1,2}",
    ]
)

#: The three shapes a required-set claim takes in these documents. A count is
#: only a claim when it sits directly beside the phrase — the alternative, a
#: window of any length, sweeps in prose about shard cost that mentions a
#: required check and some number for entirely unrelated reasons.
#: The whitespace in these patterns is `\s+` rather than a space: a paragraph's
#: lines wrap, and a claim split across a line break is the same claim. A
#: detector that reads only single-line phrasings silently skips one — the
#: handoff's "among the required\ncontexts" is what showed it.
REQUIRED_SET_CLAIMS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(rf"\b(?:{_NUMBER_WORDS})\s+required\s+(?:status\s+)?checks?\b", re.I),
    re.compile(r"\brequired\s+contexts\b", re.I),
    re.compile(r"\bis\s+a\s+required\s+check\b", re.I),
)


def _makes_required_claim(paragraph: str) -> bool:
    return any(pattern.search(paragraph) for pattern in REQUIRED_SET_CLAIMS)


def test_the_workflow_directory_count_the_map_prints_is_the_count_it_holds(
    repo_root: Path,
) -> None:
    """`docs/REPOSITORY-MAP.md` counts the workflows by reading them.

    **The defect this is for.** The map said `.github/workflows/` holds seven
    workflows and enumerated six of them, because `shell.yml` joined the directory
    on 2026-11-11 and the sentence did not follow. A directory listing in a map is
    the sentence a newcomer trusts, and the project's rule is that a value that
    can change is re-measured.

    **How it is recomputed.** The count comes from `load_workflows`, the shared
    reader the job-name witnesses use, so the map and the witness enumerate the
    same files. The map must also name the revision it was read at, for the same
    reason the required-check record does.
    """
    paths = sorted([*(repo_root / WORKFLOWS_DIR).glob("*.yml")])
    documents = load_workflows(repo_root / WORKFLOWS_DIR)
    assert len(paths) == len(documents), (
        "the workflow directory and the shared reader disagree about how many "
        f"workflows there are: {len(paths)} files, {len(documents)} read"
    )

    text = (repo_root / "docs" / "REPOSITORY-MAP.md").read_text(encoding="utf-8")
    stated = re.search(r"holds (\w+) workflows:", text)
    assert stated is not None, (
        "the map no longer states how many workflows the directory holds, so this "
        "witness reads nothing"
    )
    assert _WORD_NUMBERS[stated.group(1)] == len(documents), (
        f"the map says the directory holds {stated.group(1)} workflows and it holds "
        f"{len(documents)}: {[path.name for path in paths]}. Re-measure and update "
        "the sentence with the revision it was measured at."
    )

    # **The enumeration is parsed as an enumeration, not searched for.** Scanning
    # a window for `` `name.yml` `` tokens reads the prose after the sentence too,
    # and that is how this witness first passed a mutated map that had dropped
    # `shell.yml` from the list: the paragraph goes on to say "The earlier figure
    # of seven is the count before `shell.yml` joined", and the backticked name in
    # that sentence filled the gap. Here the names are read as a comma list from
    # the colon, and the read stops at the first token that is not a name.
    enumerated = _enumerated_names(text, stated.end())
    assert enumerated, "the map's workflow sentence enumerates nothing"
    assert len(enumerated) == _WORD_NUMBERS[stated.group(1)], (
        f"the map says {stated.group(1)} workflows and enumerates {len(enumerated)}: "
        f"{enumerated}. A count and a list that disagree is a sentence that was "
        "half updated."
    )
    assert set(enumerated) == {path.name for path in paths}, (
        f"the map enumerates {sorted(enumerated)} and the directory holds "
        f"{sorted(path.name for path in paths)}: a directory listing with a file "
        "missing is a listing that was not read"
    )

    paragraph = _paragraph_containing(text, stated.start())
    anchor_match = FULL_SHA.search(paragraph)
    assert anchor_match is not None, (
        "the map's workflow sentence names no revision in its own paragraph, so the "
        "count is a memory rather than a reading"
    )


def _enumerated_names(text: str, start: int) -> list[str]:
    """The comma list of workflow file names that begins at ``start``.

    Reading stops at the first token that is not a backticked YAML name, so the
    sentences after the list cannot lend their backticked names to it.
    """
    names: list[str] = []
    position = start
    while True:
        match = re.match(r"\s*(?:and\s+|,\s*)?`([a-z0-9-]+\.ya?ml)`", text[position:])
        if match is None:
            return names
        names.append(match.group(1))
        position += match.end()


def _paragraph_containing(text: str, offset: int) -> str:
    """The paragraph a match sits in — bounded by blank lines.

    The bound is what makes "the sentence names its revision" mean something: a
    search over the whole file lets an anchor from another paragraph vouch for a
    claim in this one.
    """
    begin = text.rfind("\n\n", 0, offset) + 1
    end = text.find("\n\n", offset)
    return text[begin : len(text) if end == -1 else end]


#: A spelled-out count, as a map writes it, read back as a number.
_WORD_NUMBERS: Final[dict[str, int]] = {
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def _contexts_missing_from_tree(contexts: list[str], reported: set[str]) -> list[str]:
    """Required names that no job reports — the set that would hang a merge."""
    return sorted(set(contexts) - reported)


def test_the_required_check_comparison_fails_when_a_record_names_a_dead_name(
    tmp_path: Path,
) -> None:
    """The comparison that watches the record is seen to fail for the property.

    **The demonstration.** A copy of `.github/CI.md` in a scratch tree with one
    context renamed to a name no job reports — `secret-scan` becomes
    `secret-scan (ubuntu-latest)`, which is the residue a rename leaves. The
    scratch record is read by the *same* `_required_contexts` the main witness
    uses, and the diff against the real workflows is required to be exactly that
    one name. "The main witness is green" is not evidence that it can fail; this
    is.

    **The controls beside it.** Three, each one a way the demonstration could be
    hollow: the unedited copy must give an empty diff, so the failure is the edit
    and not the reader; the name being introduced must genuinely not be reported
    by any job, so the edit says something; and a record whose block end marker
    is removed must be **refused**, not read — a reader that sweeps prose into
    the list would report whatever the prose happened to say.
    """
    repo_root = _this_repo_root()
    reported = {
        name
        for _path, document in _workflow_job_names(repo_root)
        for name in rendered_job_names(document, _path.name)
    }
    dead_name = "secret-scan (ubuntu-latest)"
    assert "secret-scan" in reported, (
        "the real tree no longer reports `secret-scan`, so the demonstration "
        "below would be comparing a record that is already wrong"
    )
    assert dead_name not in reported, (
        f"the tree already reports {dead_name}, so renaming to it demonstrates nothing"
    )

    text = (repo_root / REQUIRED_CHECK_RECORD).read_text(encoding="utf-8")
    scratch = tmp_path / ".github"
    scratch.mkdir(parents=True)
    target = scratch / "CI.md"

    target.write_text(text, encoding="utf-8")
    unchanged, _anchor = _required_contexts(tmp_path)
    assert _contexts_missing_from_tree(unchanged, reported) == [], (
        "the unedited record already disagrees with the tree, so a failure below "
        "could not be attributed to the edit"
    )

    target.write_text(text.replace("\n- `secret-scan`", f"\n- `{dead_name}`", 1), encoding="utf-8")
    renamed, _anchor = _required_contexts(tmp_path)
    missing = _contexts_missing_from_tree(renamed, reported)
    assert missing == [dead_name], (
        f"the record with a renamed context reported {missing}; the comparison "
        f"must report exactly {dead_name!r}"
    )

    target.write_text(text.replace(REQUIRED_LIST_END, "", 1), encoding="utf-8")
    with pytest.raises(AssertionError) as caught:
        _required_contexts(tmp_path)
    assert REQUIRED_LIST_END in str(caught.value), (
        f"a record with its end marker removed produced {caught.value!r}; the reader "
        "must refuse a list with no edge rather than read prose as data"
    )


def _this_repo_root() -> Path:
    """This repository, from this file's own path."""
    return Path(__file__).resolve().parent.parent


#
# ``.github/remeasure_shards.py`` turns a CI run's durations section into the
# per-file costs the checks above balance against. Until this witness existed,
# nothing under ``tests/`` mentioned either shard tool: the checks above watch
# the shape of the result, and a parser that read a number off the wrong line
# would leave every one of them green.
#
# The witness runs the tool against a **copied mini-repo** in ``tmp_path``.
# The tool derives ``REPO_ROOT``, ``SHARD_FILE`` and ``TESTS`` from
# ``__file__``, so the copy moves all three at once. The checkout's real table
# is captured before and after as well, so the test is provably unable to
# write the artefact it guards.

#: The two scripts a re-measurement is made of.
REMEASURE_SCRIPTS: Final[tuple[str, ...]] = ("remeasure_shards.py", "make_ci_shards.py")

#: The commit the synthetic logs were "measured at". The tool writes it
#: through; whether the checkout contains it is not part of this contract.
MEASURED_AT: Final[str] = "0123456789abcdef0123456789abcdef01234567"

#: The mini tree's test files and their ``def test_`` counts. Only gamma (1)
#: and delta (3) matter to the arithmetic: they are absent from the logs, so
#: their weights split the residual 1:3.
MINI_TEST_FILES: Final[dict[str, int]] = {
    "test_alpha.py": 3,
    "test_beta.py": 2,
    "test_gamma.py": 1,
    "test_delta.py": 3,
}

#: A synthetic ``--durations=0`` section whose arithmetic a reader can check.
#: Alpha is ``1.00 + 0.10 + 0.05 + 2.85 = 4.00`` (all three phases), beta is
#: ``0.60 + 0.40 = 1.00`` (``setup`` and ``teardown`` only, no ``call``
#: line), and the summary says 13.00s, so the two unlogged files share 8.00s.
UBUNTU_JOB_LOG: Final[str] = """\
1.00s call     tests/test_alpha.py::test_one
0.10s setup    tests/test_alpha.py::test_one
0.05s teardown tests/test_alpha.py::test_one
2.85s call     tests/test_alpha.py::test_two
0.60s setup    tests/test_beta.py::test_one
0.40s teardown tests/test_beta.py::test_one
===== 9 passed, 1116 warnings in 13.00s =====
"""

#: The Windows log names three files and omits gamma, which is therefore the
#: only file the residual reaches: ``12.00 - 6.00 = 6.00``.
WINDOWS_JOB_LOG: Final[str] = """\
3.00s call     tests/test_alpha.py::test_one
1.00s setup    tests/test_beta.py::test_one
2.00s call     tests/test_delta.py::test_one
===== 5 passed, 10 warnings in 12.00s =====
"""


def _write_mini_checkout(repo_root: Path, destination: Path) -> Path:
    """A copied checkout: the two tools, a tiny ``tests/`` tree, a shard file.

    **Why a copy and not a ``--shard-file`` argument.** The tool resolves
    ``REPO_ROOT``, ``SHARD_FILE`` and ``TESTS`` from ``__file__``. Moving only
    the output would leave ``_test_files()`` and the missing-file weights
    reading the real ``tests/`` tree, so the expected arithmetic would depend
    on the repository's own corpus and could not be checked by hand. A copy
    moves all three at once, and needs no change to the tool.

    The tools are copied **byte for byte**, so a mutation applied to the
    checkout's copy is the version the witness runs.
    """
    tools = destination / ".github"
    tools.mkdir(parents=True)
    (destination / "tests").mkdir()
    for script in REMEASURE_SCRIPTS:
        (tools / script).write_bytes((repo_root / ".github" / script).read_bytes())
    for name, count in MINI_TEST_FILES.items():
        source = "".join(
            f"def test_{index}() -> None:\n    assert True\n\n" for index in range(count)
        )
        (destination / "tests" / name).write_text(source, encoding="utf-8")
    (tools / "ci-shards.json").write_text(
        json.dumps(
            {
                "measured_at": None,
                "shards": {platform: [[], [], [], []] for platform in PLATFORMS},
                "costs": {},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return destination


def _write_job_logs(directory: Path, logs: dict[str, str]) -> Path:
    """Write job logs under stems that name their platform.

    ``--from`` derives the platform from the file stem by substring, so the
    stem must contain ``ubuntu-latest`` or ``windows-latest``.
    """
    directory.mkdir()
    for stem, body in logs.items():
        (directory / f"{stem}.log").write_text(body, encoding="utf-8")
    return directory


def _run_remeasure(
    checkout: Path, logs: Path, measured_at: str | None
) -> subprocess.CompletedProcess[str]:
    """Run the copied tool through ``--from``; never with a run id (no network)."""
    command = [
        sys.executable,
        str(checkout / ".github" / "remeasure_shards.py"),
        "--from",
        str(logs),
    ]
    if measured_at is not None:
        command.extend(["--measured-at", measured_at])
    return subprocess.run(command, capture_output=True, text=True, check=False)


def test_the_remeasurement_reads_the_numbers_out_of_the_logs(
    repo_root: Path, tmp_path: Path
) -> None:
    """The tool's contract, on a log whose arithmetic a reader can check.

    **What is watched.** A tool that turns a log into the numbers the shard
    partition is balanced against has no witness unless a wrong number fails
    one. This fixture's numbers are round and small enough to verify in the
    head:

    * **All three phases count.** Alpha's Ubuntu cost is
      ``1.00 + 0.10 + 0.05 + 2.85 = 4.00``. A parser that read only the
      ``call`` line would say 3.85. (The work order described the contract as
      "the call line"; the code sums ``call``, ``setup`` and ``teardown``,
      and the witness asserts what the code does.)
    * **A file with no ``call`` line is not zero.** Beta's Ubuntu lines are
      ``setup`` and ``teardown`` only, and its cost is 1.00.
    * **The summary line is read and the residual is apportioned.** Ubuntu's
      summary is 13.00s against 5.00s of visible files, so the files in no
      log share 8.00s. Their weights are their ``def test_`` counts, gamma 1
      and delta 3, which is 2.00 and 6.00.
    * **``measured_at`` lands as the commit passed.**
    * **A file in ``tests/`` but in no log is apportioned, not dropped** —
      gamma and delta are both present in the costs, and the partition the
      tool rebuilds contains every mini test file exactly once.

    **What it cannot watch.** The numbers are synthetic: this says the parser
    reads the log it is given, not that a runner's log has this shape.
    """
    checkout = _write_mini_checkout(repo_root, tmp_path / "checkout")
    logs = _write_job_logs(
        tmp_path / "logs",
        {
            "python-quality-ubuntu-latest-0": UBUNTU_JOB_LOG,
            "python-quality-windows-latest-3": WINDOWS_JOB_LOG,
        },
    )
    real_table = repo_root / SHARD_FILE
    real_before = real_table.read_bytes()

    proc = _run_remeasure(checkout, logs, MEASURED_AT)

    assert real_table.read_bytes() == real_before, (
        "the witness wrote the checkout's real shard table; the tool must run "
        "against the copied checkout only"
    )
    assert proc.returncode == 0, f"the tool failed: {proc.stderr}"

    table = checkout / ".github" / "ci-shards.json"
    document: dict[str, Any] = json.loads(table.read_text(encoding="utf-8"))
    assert document["measured_at"] == MEASURED_AT
    assert document["costs"] == {
        "ubuntu-latest": {
            "test_alpha.py": 4.00,
            "test_beta.py": 1.00,
            "test_delta.py": 6.00,
            "test_gamma.py": 2.00,
        },
        "windows-latest": {
            "test_alpha.py": 3.00,
            "test_beta.py": 1.00,
            "test_delta.py": 2.00,
            "test_gamma.py": 6.00,
        },
    }

    for platform in PLATFORMS:
        shards = document["shards"][platform]
        assert len(shards) == 4, f"{platform} no longer has four shards: {len(shards)}"
        placed = sorted(name for shard in shards for name in shard)
        assert placed == sorted(f"tests/{name}" for name in MINI_TEST_FILES), (
            "the tool wrote the costs but did not rebuild the partition from "
            f"them: {platform} places {placed}"
        )


def test_the_remeasurement_refuses_to_write_a_table_it_could_not_measure(
    repo_root: Path, tmp_path: Path
) -> None:
    """No commit, or no durations, means no write.

    **Why both refusals.** The table is what the partition is balanced
    against, and a table of zeros is worse than no table: every check stays
    green while ten CI jobs are balanced against nothing. The tool's own
    docstring records that this happened once and the table had to be
    restored from git.

    **The real table is checked too.** The run happens in a copied checkout,
    and both that checkout's bytes and the real checkout's bytes are compared
    before and after, so the test is provably unable to touch the artefact it
    guards.
    """
    checkout = _write_mini_checkout(repo_root, tmp_path / "checkout")
    logs = _write_job_logs(tmp_path / "logs", {"python-quality-ubuntu-latest-0": UBUNTU_JOB_LOG})
    table = checkout / ".github" / "ci-shards.json"
    real_table = repo_root / SHARD_FILE
    before = table.read_bytes()
    real_before = real_table.read_bytes()

    without_commit = _run_remeasure(checkout, logs, None)
    assert without_commit.returncode == 2, without_commit.stderr
    assert "--measured-at" in without_commit.stderr
    assert table.read_bytes() == before

    # Only Ubuntu logs exist, so Windows measures nothing. Writing the table
    # anyway would record a platform of zeros.
    without_windows = _run_remeasure(checkout, logs, MEASURED_AT)
    assert without_windows.returncode == 1, without_windows.stderr
    assert "Nothing was written" in without_windows.stderr
    assert table.read_bytes() == before
    assert real_table.read_bytes() == real_before


# --------------------------------------------------------------------------
# The job counts the records print, held to the workflows that produce them
# --------------------------------------------------------------------------
#
# Four records printed the same wrong job count on 2026-11-12: `.github/CI.md`,
# `python.yml`'s own `lint` comment, `docs/plans/LC-P1-13-evaluation-ci.md` §5,
# and — found only on a second sweep, because it sits in a helper rather than in a
# test — `test_the_evaluation_job_runs_the_offline_classes_on_a_schedule`'s failure
# message. All four said *thirteen*. Nothing in the tree could notice, because
# nothing compared a printed count with the workflow that decides it.
#
# **What a witness here can hold.** It cannot read a document's meaning. What it can
# hold is that a number a record prints **for a named job quantity** is the number the
# workflow gives for that quantity: the names GitHub renders, the legs a job's matrix
# expands to, the length of a matrix axis, the jobs that run for a trigger event, the
# count of job templates. A cardinal sitting near the word `job` that names no such
# quantity is not a job count, and a witness that read those as counts had to be
# switched off. Three instruments were built for this before the one below, and the
# first two were discarded for exactly that reason: they read `Four kinds of job`,
# `no two jobs share a check name`, `not worth adding twelve minutes to every pull
# request` and `eight workers made the whole suite faster` as job counts. The third
# attributed a quantity from any role word anywhere in the clause, which made
# `One job, shell-test (${{ matrix.os }}), … on push to main and unfiltered
# pull_request` a claim of *push jobs* — a false positive that would have reddened on
# a correct record. What is left captures only shapes that **state the quantity they
# count**.

#: The records held today: the CI contract records, the files whose job it is to state
#: what the gate runs, and — since the owner decided on 2026-11-12 — the **live pointers**
#: a session reads before it decides whether to push, and the decision record that says
#: why: `CLAUDE.md`, `CONTRIBUTING.md`, `docs/handoff/CURRENT.md` and
#: `docs/plans/LC-P1-11-12-task-breakdown.md`.
#:
#: The 2026-11-12 sweep found job-count sentences in 24 files; widening this list is a
#: decision about which records phrase their claims in a form a witness can read, so it is
#: reported to the owner rather than taken here. The owner took it for the four below, and
#: the wording in them was changed so that the reader can see the count each one states:
#: **a record this witness cannot read is a record it cannot watch.** Two of them also
#: carry a historical sentence about the six-shard matrix, and those name the revision the
#: six shards were measured in — an exemption earned by producing the figure, not by
#: mentioning a date.
JOB_COUNT_RECORDS: Final[tuple[Path, ...]] = (
    Path(".github") / "CI.md",
    WORKFLOW_FILE,
    Path("docs") / "plans" / "LC-P1-13-evaluation-ci.md",
    Path("CLAUDE.md"),
    Path("CONTRIBUTING.md"),
    Path("docs") / "handoff" / "CURRENT.md",
    Path("docs") / "plans" / "LC-P1-11-12-task-breakdown.md",
)

#: The workflow a claim is judged against when its own sentence names none. Every record
#: above is `python.yml`'s records.
DEFAULT_WORKFLOW: Final[str] = "python.yml"

_COUNTED_EVENTS: Final[tuple[str, ...]] = ("pull_request", "push", "schedule")

_CARDINAL_WORDS: Final[dict[str, int]] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
}
_ORDINAL_WORDS: Final[dict[str, int]] = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "eleventh": 11,
    "twelfth": 12,
    "thirteenth": 13,
}
_NUMBER: Final[str] = r"(?:" + "|".join(_CARDINAL_WORDS) + r"|\d{1,2})"
_ORDINAL: Final[str] = r"(?:" + "|".join(_ORDINAL_WORDS) + r")"

#: The multiplication sign CI.md prints between the factors of its shard arithmetic. Built
#: with `chr` rather than typed, because a typed one is indistinguishable from the letter `x`
#: to anyone reading the source — which is exactly what a lint rule exists to point at — and
#: a pattern that silently matched only `x` would stop matching the record.
MULTIPLICATION_SIGN: Final[str] = chr(0xD7)

#: The claim shapes. Each one carries the quantity it states **in its own wording**, and
#: that is the whole design: CI.md's `2 platforms (multiplication sign) 5 shards = 10 jobs`
#: states a shard-leg count; `the run spends one job` states a schedule-event count;
#: `as the eleventh` states a
#: member of a sum whose total the same sentence names. A number that appears near a job
#: word without stating a quantity is left alone, because a witness that counts those has
#: to be switched off — which is what the first two instruments needed.
_JOB_CLAIM_SHAPES: Final[tuple[tuple[str, re.Pattern[str], str], ...]] = (
    (
        "rendered job names",
        re.compile(
            rf"(?:names?|in total|total of)\s+(?:the\s+)?({_NUMBER})"
            r"\s+(?:\w+\s+)?jobs?\b(?:\s+in\s+total)?",
            re.I,
        ),
        "rendered",
    ),
    (
        "shard legs",
        re.compile(rf"\b({_NUMBER})\s+shard\s+(?:jobs?|legs)\b", re.I),
        "shard-legs",
    ),
    (
        "shard legs",
        # CI.md's arithmetic cell is `2 platforms <sign> 5 shards = 10 jobs`, where the sign is
        # the multiplication sign. The pattern takes `MULTIPLICATION_SIGN` — built from its code
        # point rather than typed, so it cannot be confused with the letter `x` — alongside the
        # plain `x` and `*`. A pattern that quietly matched only `x` would stop matching the
        # record, and the claim would leave the witness while the record stayed put.
        re.compile(
            rf"({_NUMBER})\s+platforms?\s*[{MULTIPLICATION_SIGN}x*]"
            rf"\s*({_NUMBER})\s+shards?\s*=\s*({_NUMBER})\s+jobs?",
            re.I,
        ),
        "shard-legs",
    ),
    (
        "matrix legs",
        re.compile(rf"({_NUMBER})\s+platforms?\s*=\s*({_NUMBER})\s+jobs?", re.I),
        "legs",
    ),
    (
        "shard axis",
        # **Plural, and not `one shard`.** The axis length is what a record states as
        # `five shards` or `6 shards`. `one shard` in `jobs that share a name are one
        # check` or `in one shard, on every platform` states a *placement*, not a count of
        # shards; an earlier version of this shape read it as the axis and reddened on a
        # correct sentence.
        re.compile(rf"\b({_NUMBER})\s+shards\b(?!\s*(?:jobs?|legs))", re.I),
        "shard-axis",
    ),
    (
        "job templates",
        re.compile(rf"\b({_NUMBER})\s+job\s+templates?\b", re.I),
        "templates",
    ),
    (
        "event jobs",
        re.compile(
            rf"(?:the run|a scheduled run|the schedule|a run)\s+spends"
            rf"\s+(?:the\s+)?({_NUMBER})\s+jobs?\b",
            re.I,
        ),
        "event:schedule",
    ),
    (
        "event jobs",
        re.compile(
            rf"\b({_NUMBER})\s+(?:that\s+)?(?:the\s+|a\s+|an\s+)?"
            r"(pull[- ]request|pull request|push|schedule)(?:\s+event)?"
            r"\s+(?:spends|starts|runs|costs|produces)",
            re.I,
        ),
        "event:named",
    ),
    (
        "sum member",
        re.compile(rf"as\s+the\s+({_ORDINAL})", re.I),
        "sum",
    ),
)

#: A revision token, in the 7-to-40-hex forms the records use.
_SENTENCE_REVISION: Final[re.Pattern[str]] = re.compile(r"\b[0-9a-f]{7,40}\b")
_WORKFLOW_NAMED: Final[re.Pattern[str]] = re.compile(r"\b([a-z0-9][a-z0-9-]*\.ya?ml)\b")

#: How many job-count claims each record carries, measured 2026-11-12 by running this
#: instrument over the records above. Pinned, because the way a check goes green while a
#: record moves out of its reach is that a claim stops being readable: the count moving says
#: either the record changed or this witness stopped seeing a claim it used to see, and the
#: second is the more dangerous of the two. `python.yml` reads 8 rather than 7 because an
#: earlier `_record_paragraphs` left a `# ` inside a joined YAML comment, which cut
#: "not the eleven that a / pull-request event spends" between the number and its quantity:
#: the claim was invisible to the witness while the comment stayed exactly where it was.
#: The four live pointers were added on 2026-11-12 and measured the same day, with the same
#: instrument: each of them carries one push-event claim of eleven, readable because the
#: wording states the quantity it counts rather than putting the number beside the word
#: "push".
JOB_COUNT_CLAIMS: Final[dict[str, int]] = {
    "CI.md": 11,
    "python.yml": 8,
    "LC-P1-13-evaluation-ci.md": 4,
    "CLAUDE.md": 6,
    "CONTRIBUTING.md": 3,
    "CURRENT.md": 6,
    "LC-P1-11-12-task-breakdown.md": 1,
}

#: **Why a record is outside the completeness rule, on the record's own terms.** An
#: exemption nobody wrote down is indistinguishable from a forgotten record — the same
#: shape as an unwatched claim, arrived at from the other side. Each rule names the class
#: the tree itself uses for these files, and the reasons are the ones the tree already
#: states: a *dated log* carries its counts inside dated entries, so a sentence that was
#: true when written stays as written; a *dated record* keeps the wording of the decision
#: it records; and the *mechanism* file is where the ruler itself lives, so its prose
#: describes the shapes it reads rather than claiming today's figures.
#:
#: Measured 2026-11-13 at `ab0ba12`: the tree holds **11** files whose sentences the
#: `_job_count_claims` ruler reads; the seven above are watched, and these rules remove
#: the other four. `docs/changelog/phase-3.md` carries five claims, all inside dated
#: entries — the *failed five shard jobs* of run `42733499009`, the *six shards* the
#: 2026-11-08 correction quoted out of `CONTRIBUTING.md`'s earlier wording, and the
#: *five shards* quoted as the defect that was fixed. `docs/acceptance/G5-acceptance.md`'s
#: *Five shards* is the S3 decision of 2026-10-25, stated as the fix that was applied.
#: `docs/adr/ADR-0022-…`'s *the two shards that carry the README-accuracy witness* counts
#: **two shard jobs** — one per platform — and is not a shard-axis claim at all; the
#: ruler's `N shards` shape reads it that way, which is the one known false positive, and
#: it is watched by hand rather than by widening the shape to match it.
_JOB_COUNT_EXEMPTIONS: Final[tuple[tuple[str, str], ...]] = (
    (
        "docs/changelog/phase-3.md",
        "dated log: every job-count sentence sits inside a dated entry that was true when "
        "written — the run that failed five shard jobs, the superseded six-shard wording "
        "quoted as the defect, the correction that fixed it",
    ),
    (
        "docs/acceptance/G5-acceptance.md",
        "dated record: the S3 decision of 2026-10-25 that fixed five shards, kept as "
        "written under the dated-snapshot rule",
    ),
    (
        "docs/adr/ADR-0022-platform-conditional-code-keeps-one-reachable-body.md",
        "dated record: 'the two shards that carry the README-accuracy witness' counts two "
        "shard jobs, one per platform — not a shard-axis claim; the ruler's shape reads it "
        "that way and the misreading is recorded here rather than shaped around",
    ),
    (
        "tests/test_ci_shard_coverage.py",
        "the mechanism itself: this file's numbered sentences state the shapes the ruler "
        "reads ('if the matrix declares four shards and the file names three'), not "
        "figures any workflow gives",
    ),
)


def _job_count_exemption_reason(relative: str) -> str | None:
    """Why this repository-relative path is outside the completeness rule, or None.

    The rules are written with forward slashes; `PurePath.as_posix()` is what makes a
    rule apply on both platforms, and a rule that matched nothing would be an exemption
    that silently stopped working — the same wrong-green the list check exists to catch.
    """
    for pattern, reason in _JOB_COUNT_EXEMPTIONS:
        if relative == pattern:
            return reason
    return None


def _job_count_record_candidates(repo_root: Path) -> dict[str, int]:
    """Every tracked text file whose sentences the job-count ruler reads, with its count.

    **The same ruler that reads the listed records reads the whole tree.** The list
    `JOB_COUNT_RECORDS` is hand-written, and a hand-written list drifts in both
    directions: a record that gains a job-count sentence and is never added is a claim
    no check reads, and a listed file whose claims have gone is coverage claimed over
    nothing. So the candidate set is derived from the tree and compared with the list
    both ways — the arrangement `test_the_live_document_list_covers_what_the_tree_contains`
    uses for the anchor declarations, with this file's own ruler in place of that one's
    citation reader.

    A file `git ls-files` names but Python cannot decode is skipped rather than failed:
    the ruler reads prose, and the tree's undecodable files are fixtures (measured
    2026-11-13: three PDFs). A decode failure is not a record going unreadable; a
    *readable* file gaining an unreadable claim is, and that is what the count pins.
    """
    return _derive_with_ruler(repo_root, _job_count_claims)


def _derive_with_ruler(
    repo_root: Path, ruler: Callable[[str], list[dict[str, Any]]]
) -> dict[str, int]:
    """The candidate derivation, with the ruler supplied: the seam the control below blinds."""
    tracked = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    assert tracked.returncode == 0, (
        "git ls-files failed, so the tree's records cannot be enumerated"
    )
    candidates: dict[str, int] = {}
    for name in tracked.stdout.decode("utf-8").split("\0"):
        if not name:
            continue
        path = repo_root / name
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        count = len(ruler(text))
        if count:
            candidates[name.replace("\\", "/")] = count
    return candidates


def _strip_markup(text: str) -> str:
    """Markdown emphasis, code spans and table pipes, replaced by spaces.

    The records write `**eleven**` and ``the `evaluation` job``, and CI.md's job table
    separates its cells with `|`. Left in, each one splits a cardinal from the words it
    counts, and a claim becomes unreadable for a typographic reason.
    """
    return re.sub(r"[*_`|]+", " ", text)


def _record_paragraphs(text: str) -> list[tuple[int, str]]:
    """Paragraphs, headings, table rows and YAML comment blocks, each with its first line.

    **Paragraphs, not lines.** A record wraps a sentence across lines, and the instrument
    that read `.github/CI.md` line by line cut `On the schedule event … so the run spends
    one job, not the eleven a pull-request event spends` after its first line. What
    survived stated no quantity, so the figure went unreadable — the same failure the
    required-check witness above documents for paragraph anchors.

    A `#` comment block in a workflow is a paragraph too, and **its comment marker is
    stripped from every line before joining**. Keeping the marker on the line that *starts*
    a block — which is what an earlier version of this function did — leaves `# ` inside the
    joined text, and the sentence `not the eleven that a` / `pull-request event spends` gets a
    `# ` between the number and the quantity it states. The claim then matches no shape, and
    the record silently drops out of the witness while the sentence stays exactly where it
    was: a claim that leaves the check without anyone editing the record.

    A Markdown **heading** ends a paragraph instead of joining one, because a heading carries
    a date and that date must not leak into the dating of the sentence beneath it.
    """
    out: list[tuple[int, str]] = []
    buffer: list[str] = []
    start = 0
    inside_fence = False
    previous_was_marker = False

    def flush() -> None:
        if buffer:
            out.append((start, " ".join(buffer)))
            buffer.clear()

    for number, raw in enumerate(text.split("\n"), start=1):
        line = raw.strip()
        if line.startswith("```"):
            flush()
            inside_fence = not inside_fence
            previous_was_marker = False
            continue
        if inside_fence:
            # A workflow's YAML body is read structurally by `_workflow_figures`, never as
            # prose: `shard: [0, 1, 2, 3, 4]` is the matrix, not a sentence about five.
            continue
        if not line:
            flush()
            previous_was_marker = False
            continue
        if line.startswith("|"):
            # A table row is a paragraph of its own. CI.md's job table is where the shard
            # arithmetic cell (`2 platforms <multiplication sign> 5 shards = 10 jobs`) and
            # `2 platforms = 2 jobs` are stated, and a reader that skipped table rows dropped
            # three claims from the witness while the table stayed exactly where it was.
            flush()
            out.append((number, line))
            previous_was_marker = False
            continue
        if line.startswith("##"):
            # A Markdown heading: its own paragraph, marker removed.
            flush()
            out.append((number, line.lstrip("#").strip()))
            previous_was_marker = False
            continue
        if line.startswith("#"):
            body = line.lstrip("#").strip()
            if not body:
                # A bare `#` is a separator inside a comment block, not part of the sentence:
                # two comment paragraphs joined into one read as one long sentence.
                flush()
                previous_was_marker = False
                continue
            # The marker is removed on **every** comment line before joining. Keeping it on the
            # line that starts a block — which an earlier version of this function did — leaves
            # `# ` inside the joined text, so `not the eleven that a` / `pull-request event
            # spends` gets a `# ` between the number and the quantity it states, matches no
            # shape, and the claim leaves the check without anyone editing the record.
            if previous_was_marker and buffer:
                buffer.append(body)
            else:
                flush()
                start = number
                buffer.append(body)
            previous_was_marker = True
            continue
        if previous_was_marker:
            flush()
        if not buffer:
            start = number
        buffer.append(line)
        previous_was_marker = False
    flush()
    return out


def _job_count_claims(text: str) -> list[dict[str, Any]]:
    """Every cardinal a record prints for a named job quantity, with its quantity and anchors."""
    claims: list[dict[str, Any]] = []
    for line, paragraph in _record_paragraphs(text):
        plain = _strip_markup(paragraph)
        for sentence in (s.strip() for s in re.split(r"(?<=[.!?])\s+", plain) if s.strip()):
            if not re.search(r"\bjobs?\b", sentence, re.I):
                continue
            # **Anchors are read from the sentence, never the paragraph.** `What this sentence
            # printed until 2026-11-12 was thirteen` sits in the same paragraph as a
            # present-tense claim about today; letting a paragraph's anchors cover every
            # sentence in it lets any record dodge the check by naming a date near the number.
            anchors = _SENTENCE_REVISION.findall(sentence)
            named = _WORKFLOW_NAMED.search(sentence)
            for shape, pattern, kind in _JOB_CLAIM_SHAPES:
                for match in pattern.finditer(sentence):
                    groups = match.groups()
                    stated = [g for g in groups if g and re.fullmatch(_NUMBER, g, re.I)]
                    if not stated:
                        continue
                    values = [_CARDINAL_WORDS.get(g.lower()) or int(g) for g in stated]
                    claims.append(
                        {
                            "line": line,
                            "shape": shape,
                            "kind": kind,
                            "value": values[-1] if kind in ("shard-legs", "legs") else values[0],
                            "event": (groups[1] if kind == "event:named" else "schedule"),
                            "matched": match.group(0),
                            "anchors": anchors,
                            "workflow": named.group(1) if named else DEFAULT_WORKFLOW,
                            "sentence": sentence,
                        }
                    )
    return claims


def _matrix_legs(job: dict[str, Any]) -> int:
    """How many legs one job's matrix expands to — 1 when it has no matrix."""
    strategy = job.get("strategy")
    matrix = strategy.get("matrix") if isinstance(strategy, dict) else None
    if not isinstance(matrix, dict):
        return 1
    legs = 1
    for axis, values in matrix.items():
        if axis in MATRIX_NON_AXIS_KEYS or not isinstance(values, list):
            continue
        legs *= len(values)
    return legs


def _figures_from_document(document: dict[str, Any], workflow_name: str) -> dict[str, Any]:
    """One workflow document's job quantities.

    Rendered names, job templates, each job's matrix legs, each axis's length, the legs of the
    jobs with a `shard` axis, and the jobs that run for each counted event.

    **The same function reads today's file and a revision's file.** A record is exempt from
    matching today only if its figure measured true **at the revision it names**, and the only
    way to know that is to measure that revision the way today is measured. Two readers of
    the same quantities, written twice, is where a history check goes soft.

    An `if` guard this cannot read as an event condition is **refused**, not assumed open: a
    record that prints a job count for an event nobody can compute is a figure nothing checks.
    """
    jobs = document.get("jobs")
    assert isinstance(jobs, dict) and jobs, f"{workflow_name} declares no jobs"

    axes: dict[str, int] = {}
    legs: dict[str, int] = {}
    shard_legs = 0
    for key, job in jobs.items():
        assert isinstance(job, dict), f"{workflow_name}'s {key} job is not a mapping"
        legs[key] = _matrix_legs(job)
        strategy = job.get("strategy")
        matrix = strategy.get("matrix") if isinstance(strategy, dict) else None
        if isinstance(matrix, dict):
            for axis, values in matrix.items():
                if axis in MATRIX_NON_AXIS_KEYS or not isinstance(values, list):
                    continue
                axes[axis] = len(values)
        if legs[key] > 1 and isinstance(matrix, dict) and "shard" in matrix:
            shard_legs += legs[key]

    declared = _declared_triggers(document)
    per_event: dict[str, int] = {}
    for event in _COUNTED_EVENTS:
        total = 0
        for key, job in jobs.items():
            guard = str(job.get("if", ""))
            if not guard:
                runs = event in declared
            elif "github.event_name != 'schedule'" in guard:
                runs = event != "schedule"
            elif "github.event_name == 'schedule'" in guard:
                runs = event == "schedule"
            else:
                pytest.fail(
                    f"{workflow_name}'s {key} job carries the guard {guard!r}, which this "
                    "witness cannot read as an event condition. A job count a record prints "
                    "for an event nobody can compute is a figure nothing checks, so an "
                    "unreadable guard is refused rather than assumed open."
                )
            if runs:
                total += legs[key]
        per_event[event] = total

    return {
        "rendered": len(rendered_job_names(document, workflow_name)),
        "templates": len(jobs),
        "legs": legs,
        "axes": axes,
        "shard-legs": shard_legs,
        "events": per_event,
    }


def _workflow_figures(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Each workflow's job quantities, measured from its YAML rather than carried from a record.

    **What a record is compared with.** For every workflow file: the job names GitHub
    renders, the count of job templates, each job's matrix legs, each axis's length, the
    legs of the jobs that have a `shard` axis, and the jobs that run for each trigger event.
    `include` and `exclude` are refused by the shared renderer rather than skipped here, so
    the leg counts are the legs CI actually runs.
    """
    figures: dict[str, dict[str, Any]] = {}
    for path, document in _workflow_job_names(repo_root):
        figures[path.name] = _figures_from_document(document, path.name)
    return figures


def _figures_at_revision(
    repo_root: Path, revision: str, workflow_relative: Path
) -> dict[str, Any] | None:
    """The job quantities of one workflow **at a revision the record names** — or None.

    **Why the history is measured rather than believed.** A claim that does not match today
    is exempt only if it measured true at the revision it points at. So the exemption is
    computed from that revision's YAML, not from the fact that a date appears nearby: a
    sentence can name a date, name a commit, and still print a figure that commit's workflow
    never produced. That is what makes this a dated-snapshot rule instead of a licence to
    mention a date beside a number.

    None means unreadable — no such revision, no such file at it, or unparseable — which the
    caller reports as a failed claim rather than treating as an exemption.
    """
    shown = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"{revision}:{workflow_relative.as_posix()}"],
        capture_output=True,
        check=False,
    )
    if shown.returncode != 0:
        return None
    try:
        # **Decoded as UTF-8 explicitly.** `text=True` would use the machine's locale
        # encoding — `gbk` on this one — and the workflow's comments carry em-dashes and the
        # multiplication sign. The first run of this witness crashed a reader thread on exactly
        # that, and `stdout` arrived as None: an environment defect dressed up as a tree defect.
        document = yaml.safe_load(shown.stdout.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError):
        return None
    if not isinstance(document, dict):
        return None
    return _figures_from_document(document, workflow_relative.name)


def _expected_figure(claim: dict[str, Any], figures: dict[str, dict[str, Any]]) -> set[int]:
    """The figure this claim's own wording names, from the workflow it attributes it to."""
    figures_ = figures[claim["workflow"]]
    kind = claim["kind"]
    if kind == "rendered":
        return {int(figures_["rendered"])}
    if kind == "shard-legs":
        return {int(figures_["shard-legs"])}
    if kind == "legs":
        return {int(v) for v in figures_["legs"].values()}
    if kind == "shard-axis":
        axes = figures_["axes"]
        if "shard" not in axes:
            # A record that states a shard count for a workflow with no `shard` axis is not
            # out of date — it is pointing at the wrong workflow. Reported as such rather
            # than compared with a figure that does not exist.
            return set()
        return {int(axes["shard"])}
    if kind == "templates":
        return {int(figures_["templates"])}
    if kind == "event:schedule":
        return {int(figures_["events"]["schedule"])}
    if kind == "event:named":
        event = (
            str(claim["event"])
            .lower()
            .replace("pull request", "pull_request")
            .replace("pull-request", "pull_request")
        )
        if event not in figures_["events"]:
            return set()
        return {int(figures_["events"][event])}
    if kind == "sum":
        # `as the eleventh` states a member of a sum. It is not equal to a quantity; it must
        # fit inside the total the same sentence names, and that total is what the other
        # claims in this witness hold to.
        return set(range(1, int(figures_["rendered"]) + 1))
    raise AssertionError(f"unhandled claim kind {kind!r}")


def _job_count_reports(
    repo_root: Path,
    texts: dict[Path, str],
    figures: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[str], list[str], list[str]]:
    """Read the records against the workflows: (stale, unresolvable, anchored-in-history).

    A function rather than inline assertions, so the demonstration below runs the **same
    reader** the main witness runs instead of a paraphrase of it. `figures` may be supplied
    already measured, which is what lets the demonstration read the records against a
    workflow that does not exist on disk — a six-shard matrix held in memory — without
    writing anything.

    **The rule the reports implement.** A claim's figure has to be the figure the workflow
    gives for the quantity the claim states, **or** the claim has to name a revision at which
    it measured. The second branch is verified by measuring that revision's YAML, not by
    noticing that a date was mentioned. The 2026-11-12 calibration over the three records is
    why: it found the genuinely dated claim's nearest anchor **28 characters** away and a
    present-tense claim's cost anchor **27 characters** away, so no distance rule separates
    them, and any distance rule would exempt a wrong figure that happens to sit near a date.
    Anchors earn the exemption by having produced the number.
    """
    if figures is None:
        figures = _workflow_figures(repo_root)
    stale: list[str] = []
    unresolvable: list[str] = []
    anchored: list[str] = []
    for relative, text in texts.items():
        for claim in _job_count_claims(text):
            if claim["workflow"] not in figures:
                unresolvable.append(
                    f"{relative}:{claim['line']} attributes {claim['value']} to "
                    f"{claim['workflow']}, which is not a workflow in {WORKFLOWS_DIR}: a job "
                    "count naming a file that does not exist cannot be checked against anything"
                )
                continue
            if claim["value"] in _expected_figure(claim, figures):
                continue
            # Today's figure does not give it. The only remaining reading is history, and
            # history has to be measured at the revision the sentence itself names.
            measured_then: list[tuple[str, set[int]]] = []
            unreadable: list[str] = []
            for anchor in claim["anchors"]:
                then = _figures_at_revision(repo_root, anchor, WORKFLOWS_DIR / claim["workflow"])
                if then is None:
                    unreadable.append(anchor)
                    continue
                measured_then.append((anchor, _expected_figure(claim, {claim["workflow"]: then})))
            if any(claim["value"] in expected for _anchor, expected in measured_then):
                proven = next(
                    anchor for anchor, expected in measured_then if claim["value"] in expected
                )
                anchored.append(
                    f"{relative}:{claim['line']} {claim['shape']} {claim['value']} "
                    f"measured at {proven[:12]}"
                )
                continue
            then_note = (
                "; at the revisions it names "
                + ", ".join(f"{a[:12]} gives {sorted(expected)}" for a, expected in measured_then)
                if measured_then
                else ""
            )
            anchor_note = (
                f" — and {', '.join(unreadable[:3])} is not a readable revision of "
                f"{claim['workflow']}, so the anchor does not date anything"
                if unreadable
                else ""
            )
            stale.append(
                f"{relative}:{claim['line']} prints {claim['value']} for {claim['shape']} "
                f"({claim['matched']!r}); {claim['workflow']} gives "
                f"{sorted(_expected_figure(claim, figures))}{then_note}{anchor_note}: "
                f"{claim['sentence'][:120]}"
            )
    return stale, unresolvable, anchored


#: The claim the demonstration mutates, and the figure four records carried on 2026-11-12.
#:
#: **The needles are patterns, and the raw bytes are asserted.** `.github/CI.md` writes
#: `not the **eleven** a pull-request event` and wraps `spends.` onto the next line, and
#: `the ten` / `shard jobs` sit on two source lines. A literal needle typed from the joined
#: sentence matched nothing, so the "mutation" changed no bytes and the demonstration
#: reported nothing — a green demonstration that demonstrated nothing. The first two runs
#: of this witness failed on exactly that, and both failures are the reason these needles
#: carry `\s+` and the patterns are counted before anything is replaced.
_MUTATIONS: Final[tuple[tuple[str, re.Pattern[str], str], ...]] = (
    (
        "the pull-request job count read as thirteen",
        re.compile(r"eleven(\*{0,2}\s+a\s+pull[- ]request)"),
        r"thirteen\1",
    ),
    (
        "the shard-leg count read as eleven",
        re.compile(r"\bten(\s+shard jobs)\b"),
        r"eleven\1",
    ),
)

#: A dated job-count claim: `12` is the leg count of `d8f5788`'s six-shard matrix, and no
#: job in `python.yml` expands to 12 today. It is the control pair that shows the dated
#: exemption is a rule about history rather than a value that happens to be legal: with its
#: anchor kept, changing the figure must stay quiet; with the anchor stripped, the same
#: figure must be reported.
_DATED_CLAIM: Final[str] = "reported **12** shard jobs"
_DATED_ANCHOR: Final[str] = "the six-shard matrix `d8f5788` (2026-10-24) tried"


def test_the_job_counts_the_records_print_are_the_figures_the_workflows_give(
    repo_root: Path,
) -> None:
    """Every job count a CI record prints is the figure its workflow gives for that quantity.

    **The property.** How many jobs a run spends is what a push is costed against, what
    decides whether a schedule multiplies the gate, and what a proposed sixth shard is
    argued with. The authority for it is the workflow: its matrix axes, its jobs' `if`
    guards, and the names GitHub renders for each leg. Four records printed *thirteen* on
    2026-11-12 and the count had never been thirteen at any revision of `python.yml`.

    **A claim is judged against the quantity its own wording states, and the workflow its own
    sentence names.** `2 platforms = 2 jobs` in the shell row is compared with `shell.yml`'s
    matrix legs, not with `python.yml`'s twelve names; `names twelve jobs in total` is
    compared with the rendered total; `not the eleven a pull-request event spends` is
    compared with 11 — **not** with 12, which would let `twelve jobs a pull request spends`
    pass. That specificity is what makes this a witness rather than a search: the first
    instrument accepted any number the workflow produced anywhere, and so could not have
    caught the figure it was built to catch.

    **A figure that is not today's is exempt only if it measured true where it says it did.**
    `the six-shard matrix d8f5788 (2026-10-24) tried reported 12 shard jobs` is checked
    against `d8f5788`'s own YAML, which gives 12 shard legs — so the sentence keeps its
    wording, which is what the project's dated-snapshot rule requires. **Mentioning a date
    near a number exempts nothing.** The 2026-11-12 calibration over these three records is
    the reason: the genuinely dated claim's nearest anchor sits 28 characters from its figure
    and a present-tense claim's cost anchor sits 27 characters from its own, so no distance
    rule separates a dated snapshot from a stale sentence, and one would exempt a wrong
    figure that merely happened to sit near a date. An anchor earns the exemption by having
    produced the number.
    """
    texts = {
        relative: (repo_root / relative).read_text(encoding="utf-8")
        for relative in JOB_COUNT_RECORDS
    }
    stale, unresolvable, anchored = _job_count_reports(repo_root, texts)

    assert not unresolvable, "a record's job count could not be checked at all:\n  " + "\n  ".join(
        unresolvable
    )
    assert not stale, (
        "a record prints a job count no workflow gives — today or at the revision it names:\n  "
        + "\n  ".join(stale)
        + "\n\nEither the record is behind the workflow — a defect, corrected to the figure "
        "with the revision it was measured at — or the workflow changed under a sentence that "
        "was true when written, in which case the sentence keeps its wording and gains a dated "
        "marker naming the later reading."
    )

    measured = {relative.name: len(_job_count_claims(text)) for relative, text in texts.items()}
    for name, count in measured.items():
        assert count == JOB_COUNT_CLAIMS[name], (
            f"{name} carries {count} job-count claims where this witness records "
            f"{JOB_COUNT_CLAIMS[name]}. The count moving means the record's claims moved: a "
            "claim added has to be checked, and a claim that stopped being readable is a claim "
            "no check reads. Read what changed in the record before updating JOB_COUNT_CLAIMS, "
            "and record the measurement that produced the new figure."
        )
    assert anchored, (
        "no record's job count is anchored in the workflow's history any more. The anchored "
        "ones are how a figure's past stays readable — the six-shard trial, the thirteen that "
        "was never the count — and their disappearance means the records were flattened into "
        "present tense rather than corrected."
    )


def test_the_job_count_reader_fails_for_a_record_left_behind_by_the_matrix(
    repo_root: Path,
) -> None:
    """The reader that watches the records is seen to fail for the property.

    **The demonstration.** `.github/CI.md` is copied **in memory** and three mutations are
    applied to the copy, each read by `_job_count_reports` — the same function the witness
    above runs. `CI.md` is chosen because it is a **current pointer**: its bytes never need
    mutating for its reader to be proven, which is what `test_the_required_check_comparison_
    fails_when_a_record_names_a_dead_name` does for the required-check reader.

    **Three mutations, and what each one proves.** (1) `eleven` → `thirteen` for the
    pull-request count: the exact figure four records carried, and the reader must report it
    **once**, naming thirteen and naming the workflow. (2) `ten` → `eleven` for the shard-leg
    count: a number that is legal *somewhere* in this repository (11 is `python.yml`'s
    pull-request figure) and has to be reddened because it is wrong **for the quantity the
    sentence states** — the specificity the witness exists for. (3) The matrix mutation, in
    memory: `shard: [0, 1, 2, 3, 4]` → six values, which makes **five present-tense claims**
    report at once, because the records are true of the five-shard matrix and not of a
    six-shard one. That is the clearest form of "fails for the property": the records are not
    touched, only the thing they describe.

    **Controls.** The unmutated copy reports nothing, so every report above is the mutation
    and not the reader; the dated `12 shard jobs` claim stays quiet when its figure changes
    and its anchor is kept, and is reported once the anchor is stripped; and the real
    `CI.md` and `python.yml` bytes are compared before and after, so the demonstration is
    provably unable to write the records it guards.
    """
    ci_path = repo_root / JOB_COUNT_RECORDS[0]
    workflow_path = repo_root / WORKFLOW_FILE
    ci_bytes = ci_path.read_bytes()
    workflow_bytes = workflow_path.read_bytes()
    ci_text = ci_bytes.decode("utf-8")
    workflow_text = workflow_bytes.decode("utf-8")

    # **Each mutation is checked to change bytes before it is credited with anything.** A
    # needle that matches nothing produces a "mutant" identical to the original, and the test
    # then reports a caught defect while having changed nothing. Two runs of this witness
    # failed on exactly that: a literal needle typed from the joined sentence matched no bytes
    # in the wrapped source, and a mutant was reported as red when it was never red.
    for label, pattern, replacement in _MUTATIONS:
        found = pattern.findall(ci_text)
        assert len(found) == 1, (
            f"{label}: the needle {pattern.pattern!r} matches {len(found)} places in "
            f"{JOB_COUNT_RECORDS[0]}, not one. A needle matching nothing mutates nothing, and "
            "a needle matching twice edits a sentence this demonstration did not mean to edit."
        )
        assert pattern.sub(replacement, ci_text, count=1) != ci_text, (
            f"{label}: the substitution changed no bytes, so the mutant below is the original "
            "record and any report from it describes nothing."
        )
    assert _DATED_CLAIM in ci_text and _DATED_ANCHOR in ci_text, (
        f"{JOB_COUNT_RECORDS[0]} no longer carries the dated six-shard claim, so the control "
        "below that requires an anchor to be measured has nothing to test"
    )
    assert workflow_text.count("shard: [0, 1, 2, 3, 4]") == 1, (
        f"{WORKFLOW_FILE} no longer holds exactly one `shard: [0, 1, 2, 3, 4]` matrix literal, "
        "so the workflow-side mutation below would not apply"
    )

    relative = JOB_COUNT_RECORDS[0]

    # Control: the unmutated record reports nothing.
    clean, clean_unresolvable, clean_anchored = _job_count_reports(repo_root, {relative: ci_text})
    assert clean == [] and clean_unresolvable == [], (
        f"the reader reddens on the unedited record: {clean + clean_unresolvable}"
    )
    assert clean_anchored, (
        "no job count in the record is anchored in the workflow's history, so the control "
        "below that requires an anchor to be measured has nothing to test"
    )

    # Mutation 1: the pull-request job count, read as thirteen.
    first = _MUTATIONS[0][1].sub(_MUTATIONS[0][2], ci_text, count=1)
    assert first != ci_text
    stale, _missing, _dated = _job_count_reports(repo_root, {relative: first})
    assert stale, "the reader stayed green on a record that prints thirteen pull-request jobs"
    assert len(stale) == 1, f"one edited figure produced {len(stale)} reports: {stale}"
    assert "thirteen" in stale[0] and "pull-request" in stale[0], stale[0]

    # Mutation 2: the shard-leg count, read as eleven — a legal figure for a different
    # quantity, which is why comparing a claim with the quantity it states is the property.
    second = _MUTATIONS[1][1].sub(_MUTATIONS[1][2], ci_text, count=1)
    assert second != ci_text
    stale, _missing, _dated = _job_count_reports(repo_root, {relative: second})
    assert stale, "the reader stayed green on a record that prints eleven shard jobs"
    assert len(stale) == 1, f"one edited figure produced {len(stale)} reports: {stale}"
    assert "shard" in stale[0], stale[0]

    # The workflow-side mutations. Both are applied to a **copy of the YAML held in memory**
    # and measured by `_figures_from_document` — the same reader that measures the file on
    # disk — so no file is written and the records are not touched either. That is what makes
    # this the strongest half of the demonstration: the only thing that changes is the thing
    # the records describe.
    six_shard_text = workflow_text.replace("shard: [0, 1, 2, 3, 4]", "shard: [0, 1, 2, 3, 4, 5]", 1)
    assert six_shard_text != workflow_text, "the matrix mutation did not apply to the copy"
    six_figures = copy.deepcopy(_workflow_figures(repo_root))
    six_figures[WORKFLOW_FILE.name] = _figures_from_document(
        yaml.safe_load(six_shard_text), WORKFLOW_FILE.name
    )

    six_stale: list[str] = []
    for other in JOB_COUNT_RECORDS:
        text = (repo_root / other).read_text(encoding="utf-8")
        found, _unresolvable, _anchored = _job_count_reports(repo_root, {other: text}, six_figures)
        six_stale.extend(found)
    assert len(six_stale) >= 3, (
        f"a six-shard matrix left {len(six_stale)} job counts behind in the records. The "
        "records state five shards, ten shard legs, eleven jobs for a push or a pull request, "
        "and twelve rendered names; against a six-shard matrix every one of those is wrong, so "
        "a reader that reports fewer is reading the wording rather than the quantities."
    )
    assert any("shard axis" in report or "shards" in report for report in six_stale), six_stale
    assert any("rendered job names" in report or "twelve" in report for report in six_stale), (
        six_stale
    )

    # A second workflow-side mutation, the one the records are most likely to fall behind:
    # the `evaluation` job's schedule guard removed, so it runs on a pull request too. The
    # matrix is untouched — the shard counts stay true — and only the **event** figures move.
    unguarded = workflow_text.replace("    if: ${{ github.event_name == 'schedule' }}", "", 1)
    assert unguarded != workflow_text, "the guard mutation did not apply to the copy"
    unguarded_figures = copy.deepcopy(_workflow_figures(repo_root))
    unguarded_figures[WORKFLOW_FILE.name] = _figures_from_document(
        yaml.safe_load(unguarded), WORKFLOW_FILE.name
    )
    assert (
        unguarded_figures[WORKFLOW_FILE.name]["events"]["pull_request"]
        > _workflow_figures(repo_root)[WORKFLOW_FILE.name]["events"]["pull_request"]
    ), (
        "removing the evaluation job's schedule guard did not raise the pull-request job "
        "count, so the mutation changed a line the figures do not depend on"
    )
    guard_stale: list[str] = []
    for other in JOB_COUNT_RECORDS:
        text = (repo_root / other).read_text(encoding="utf-8")
        found, _unresolvable, _anchored = _job_count_reports(
            repo_root, {other: text}, unguarded_figures
        )
        guard_stale.extend(found)
    assert guard_stale, (
        "removing the evaluation job's schedule guard left no job count behind in the records. "
        "The records state eleven jobs for a pull request, and un-gating `evaluation` makes it "
        "twelve, so a reader that stays green is reading the records' wording and not the "
        "workflow's guards."
    )
    assert any("pull-request" in report or "eleven" in report for report in guard_stale), (
        guard_stale
    )

    # Control: the dated claim is exempt because its anchor **produces its figure**...
    _stale, _unresolvable, anchored_reports = _job_count_reports(repo_root, {relative: ci_text})
    assert any("12" in report and "d8f5788" in report for report in anchored_reports), (
        f"the six-shard claim was not exempted by measuring `d8f5788`, which gives 12 shard "
        f"legs: {anchored_reports}"
    )

    # ...and a **wrong figure keeps its anchor and is still reported**, which is the whole
    # point of earning the exemption. Under the distance rule this window discarded, the
    # sentence `the six-shard matrix d8f5788 (2026-10-24) tried reported 13 shard jobs` was
    # exempt — a date and a revision sat near the number — and a wrong figure walked free.
    # Under the measured rule, `d8f5788` gives 12 shard legs, so 13 is reported even with the
    # anchor standing.
    moved_figure = ci_text.replace(_DATED_CLAIM, "reported **13** shard jobs", 1)
    assert moved_figure != ci_text
    anchored_stale, _unresolvable, _anchored = _job_count_reports(
        repo_root, {relative: moved_figure}
    )
    assert any("13" in report and "shard" in report for report in anchored_stale), (
        f"a dated claim's figure was accepted because a revision was named near it: "
        f"{anchored_stale}. `d8f5788`'s workflow gives 12 shard legs, so 13 is wrong there too "
        "— an anchor is evidence, not a licence."
    )

    # And with the anchor removed the claim is reported for the plain reason: no reading,
    # today or in history, gives the figure.
    unanchored = moved_figure.replace(_DATED_ANCHOR, "the six-shard matrix tried", 1)
    assert unanchored != moved_figure
    stripped_stale, _unresolvable, stripped_anchored = _job_count_reports(
        repo_root, {relative: unanchored}
    )
    assert any("13" in report and "shard" in report for report in stripped_stale), (
        f"removing the anchor did not make the claim reportable: {stripped_stale}"
    )
    assert not any("13" in report for report in stripped_anchored), stripped_anchored

    # Control: the records the witness guards were not touched.
    assert ci_path.read_bytes() == ci_bytes, (
        f"{JOB_COUNT_RECORDS[0]} changed while it was being read"
    )
    assert workflow_path.read_bytes() == workflow_bytes, (
        f"{WORKFLOW_FILE} changed while it was being read"
    )


#: The push-count sentence the live pointers share, and the wrong figure a control writes into
#: it. **The needle is a pattern and the substitution is asserted.** A needle that matches
#: nothing leaves the record untouched, and the control would then be proving that a reader
#: stays quiet — the opposite of what it is for. The pattern carries `\s+` because the
#: sentence wraps in two of the three records (`CLAUDE.md` and `CONTRIBUTING.md` break it
#: between "push" and "event", and `docs/handoff/CURRENT.md` prefixes the second line with
#: the blockquote mark), and a needle typed from the joined sentence would match none of
#: them.
_PUSH_COUNT_CLAIM: Final[re.Pattern[str]] = re.compile(r"eleven that a push\s+event\s+starts", re.I)
_PUSH_COUNT_WRONG: Final[str] = "ten that a push event starts"

#: The parenthesis that holds the revision a historical six-shard sentence names, stripped to
#: show the exemption is load-bearing: without it the sentence is judged against today's
#: shard axis, and today's axis is five. **The pattern carries `\s+` because the parenthesis
#: wraps in both records** — `CLAUDE.md` breaks the line before it and the task breakdown
#: breaks it inside — and a needle typed from the joined sentence would match neither.
_SIX_SHARD_ANCHOR: Final[re.Pattern[str]] = re.compile(
    r"\s*\(the six-shard matrix `d8f5788[0-9a-f]*`(?:\s+tried)?\)"
)


def test_the_live_pointers_job_counts_are_watched_too(repo_root: Path) -> None:
    """The live pointers' job counts are held to the workflow, and their dated sentences to
    the revision they name.

    **The property.** `CLAUDE.md`, `CONTRIBUTING.md` and `docs/handoff/CURRENT.md` are what a
    session reads before it decides whether to push, and
    `docs/plans/LC-P1-11-12-task-breakdown.md` is the record of the decision that pushing is
    expensive. Their job counts are claims like any other, and a claim nobody checks is a
    claim nobody keeps true: the 2026-11-12 sweep found two of them printing a push
    starting ten jobs where `python.yml` gives eleven.

    **What this control does that the demonstration above does not.** The demonstration
    mutates `.github/CI.md` and the workflow; this one mutates the **records the owner added
    on 2026-11-12**, one figure at a time, on a copy of the text. Two things are checked per
    record. First, that a wrong figure is reported, and that the report names the file and
    the figure — a report that says only "something is wrong" leaves the reader to guess
    which record to open. Second, that the historical six-shard sentence is exempt only
    because it names the revision the six shards were measured in: strip that revision and
    the sentence has to be reported, because nothing gives six shards today.

    **The records are not touched.** Every mutation here happens on a copy of the text, and
    the bytes on disk are compared before and after, so the control cannot be the thing
    that breaks the records it guards.
    """
    pointers = (
        Path("CLAUDE.md"),
        Path("CONTRIBUTING.md"),
        Path("docs") / "handoff" / "CURRENT.md",
    )
    dated = (
        Path("CLAUDE.md"),
        Path("docs") / "plans" / "LC-P1-11-12-task-breakdown.md",
    )
    before = {
        relative: (repo_root / relative).read_bytes()
        for relative in dict.fromkeys(pointers + dated)
    }

    for relative in pointers:
        text = before[relative].decode("utf-8")
        stale, unresolvable, _anchored = _job_count_reports(repo_root, {relative: text})
        assert not stale and not unresolvable, (
            f"{relative} is read as carrying a job count no workflow gives, today or at the "
            f"revision it names: {stale + unresolvable}"
        )

        wrong = _PUSH_COUNT_CLAIM.sub(_PUSH_COUNT_WRONG, text, count=1)
        assert wrong != text, (
            f"{relative} carries no push-count sentence this control can mutate "
            f"({_PUSH_COUNT_CLAIM.pattern!r}), so the mutation would change nothing and the "
            "control would prove nothing"
        )
        stale, _unresolvable, _anchored = _job_count_reports(repo_root, {relative: wrong})
        assert len(stale) == 1, (
            f"one wrong figure in {relative} produced {len(stale)} reports: {stale}"
        )
        report = stale[0]
        assert relative.name in report, (
            f"the report for {relative} does not name the record it is about: {report}"
        )
        assert "prints 10" in report and "gives [11]" in report, (
            f"the report for {relative} does not name the figure the record prints and the "
            f"figure the workflow gives: {report}"
        )

    for relative in dated:
        text = before[relative].decode("utf-8")
        stale, unresolvable, anchored = _job_count_reports(repo_root, {relative: text})
        assert not stale and not unresolvable, (
            f"{relative} is read as carrying a job count no workflow gives: {stale + unresolvable}"
        )
        assert any("d8f5788" in report for report in anchored), (
            f"{relative} carries a six-shard sentence that names no revision the six shards "
            f"were measured in, so nothing exempts it: {anchored}"
        )

        stripped = _SIX_SHARD_ANCHOR.sub("", text, count=1)
        assert stripped != text, (
            f"{relative} carries no six-shard anchor for this control to strip, so stripping "
            "it would change nothing and the control would prove nothing"
        )
        stale, _unresolvable, _anchored = _job_count_reports(repo_root, {relative: stripped})
        assert len(stale) == 1, (
            f"removing the revision a six-shard sentence named produced {len(stale)} reports "
            f"in {relative}: {stale}"
        )
        assert "prints 6" in stale[0] and "shard axis" in stale[0], stale[0]

    for relative, original in before.items():
        assert (repo_root / relative).read_bytes() == original, (
            f"{relative} changed while it was being read"
        )


def test_the_job_count_record_list_covers_what_the_tree_contains(repo_root: Path) -> None:
    """The hand-written record list is checked against the tree it claims to describe, both ways.

    **The hole this closes.** `JOB_COUNT_RECORDS` is written by hand, and deleting a real
    record from it left the witnesses green — the main job-count witness reads the records
    the list names, and a list that no longer names a record is a witness that reads one
    file fewer without anything noticing. That is the defect the 2026-11-13 independent
    review measured: removing `CI.md` from the list left every job-count check green.

    **A list that is only enforced one direction is a list that drifts.** So the candidate
    set is derived with the same ruler the list was built with — `_job_count_claims`, the
    reader the main witness runs — and compared with the list **and** with the exemptions.
    A file the tree carries that the list neither names nor exempts is a job-count claim
    no check reads; a file the list names that the tree no longer supports is coverage
    claimed over a record that states nothing.
    """
    derived = _job_count_record_candidates(repo_root)
    listed = {relative.as_posix() for relative in JOB_COUNT_RECORDS}

    omitted: list[str] = []
    for name, count in sorted(derived.items()):
        if name in listed:
            continue
        reason = _job_count_exemption_reason(name)
        if reason is None:
            omitted.append(
                f"{name} ({count} job-count claim{'s' if count != 1 else ''}) is neither "
                "listed in JOB_COUNT_RECORDS nor exempted by a stated rule"
            )
    assert not omitted, (
        "the tree carries job-count sentences in records this file's list does not watch:\n  "
        + "\n  ".join(omitted)
        + "\n\nAdd the record to JOB_COUNT_RECORDS (and to JOB_COUNT_CLAIMS, with the "
        "measurement that produced its count), or state why it is outside the rule in "
        "_JOB_COUNT_EXEMPTIONS."
    )

    unsupported: list[str] = []
    for name in sorted(listed):
        if name not in derived:
            unsupported.append(
                f"{name} is listed as a watched record but carries no "
                "job-count claim the ruler can read"
            )
    assert not unsupported, (
        "JOB_COUNT_RECORDS names records the tree no longer supports:\n  "
        + "\n  ".join(unsupported)
        + "\n\nA listed record whose claims have gone is coverage claimed over nothing — "
        "drop it from the list, or restore the wording the ruler reads."
    )


def test_the_job_count_record_derivation_fails_when_the_ruler_stops_reading(
    repo_root: Path,
) -> None:
    """The derivation is seen to derive: a ruler that reads nothing turns the check red.

    **Why the mechanism needs its own witness.** The list check above is only as good as
    the derivation it compares with. A derivation that returned an empty dict — a ruler
    switched off, a pattern that stopped matching, a file reader that swallowed every
    record — would make the *omitted* half agree with whatever the list said, and the
    only red left would be the unsupported half. So the ruler is blinded here and the
    comparison is run against the blind output: every listed record must be named as
    unsupported, which is the red that proves the derivation is the thing doing the
    work. A check that stays green when its ruler stops reading is a check that has
    already been turned off.
    """
    real = _job_count_record_candidates(repo_root)
    watchable = [name for name in real if _job_count_exemption_reason(name) is None]
    assert watchable, (
        "the tree carries no watchable job-count record at all, so this control has "
        "nothing to prove — re-point it at the records the ruler should read"
    )

    def _blind_candidates() -> dict[str, int]:
        """The derivation with its ruler blinded: the walk runs, nothing is read."""
        return _derive_with_ruler(repo_root, lambda _text: [])

    blinded = _blind_candidates()
    assert not blinded, "the blinded ruler is not blind"

    # The comparison the list check runs, run against the blind output: every listed
    # record has to land in the unsupported half, because the blind derivation sees
    # nothing at all. That is the red which proves the real derivation is the thing
    # doing the work.
    listed = {relative.as_posix() for relative in JOB_COUNT_RECORDS}
    unsupported = [name for name in sorted(listed) if name not in blinded]
    assert unsupported == sorted(listed), (
        f"a blinded ruler did not put every listed record beyond the derivation's sight: "
        f"unsupported={unsupported}, listed={sorted(listed)}"
    )
    assert sorted(watchable) == sorted(name for name in real if name in listed), (
        "the watchable records the ruler reads are not exactly the listed ones; the "
        "omitted half of the list check is what catches a record that gains claims "
        "outside this list, and its ruler has to be this one"
    )


#: What the property has held for across the workflow's own history, measured 2026-11-12 over
#: the 17 revisions of `.github/workflows/python.yml` reachable with `--all`: the file has
#: rendered 2, 10, 11, 12 and 16 job names, and **13 has never been among them**. **No revision
#: ever declared both a six-shard matrix and a `lint` job** — thirteen is what those two give
#: together (12 shard legs, `lint`, `evaluation`); the six-shard matrix was rejected on
#: 2026-10-25 at `5a4d8e9`, and `lint` was split out on 2026-11-02 at `e5472f8`. So the four
#: *thirteen* sentences were never true of any tree: a different defect from a stale one, and
#: the reason none of them owed a marker.
_THIRTEEN_JOBS: Final[int] = 13


def test_thirteen_jobs_is_a_figure_no_revision_of_the_workflow_ever_produced(
    repo_root: Path,
) -> None:
    """The corrected figure was not just wrong today — it was never true of any tree.

    **Why the history is watched rather than written as prose.** "Thirteen was not the count
    at any revision" is a claim about every revision of `python.yml`, and it is the sentence
    that decides whether a *thirteen* found somewhere is a stale record (a marker is owed) or
    an error (the sentence is wrong). Stating it in a document and checking nothing is the
    failure mode the project's own witness ledger exists to catch.

    **The two shapes thirteen comes from.** Twelve shard legs from a six-shard matrix, plus a
    separate `lint` job, plus `evaluation`. Both halves exist in this repository's history and
    **no revision ever had them at once**, so no run ever spent thirteen jobs.

    **What it cannot watch.** A future workflow that does produce thirteen. That would be
    correct, and this test would go red for the right reason: the records' "never thirteen"
    sentence would have become a dated snapshot, and a marker naming the later reading is what
    turns it back into a green test.
    """
    # **The pathspec is forward-slated.** `str(WORKFLOW_FILE)` on Windows is
    # `.github\workflows\python.yml`, and git reads a backslash in a pathspec as an escape:
    # the first run of this witness reported the file "exists on disk, but not in" a revision
    # where it plainly does. A witness that cannot read the history it asserts about has to
    # fail, and it did — but the fix is the pathspec, not the claim.
    listing = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "log",
            "--format=%H",
            "--all",
            "--",
            WORKFLOW_FILE.as_posix(),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert listing.returncode == 0, listing.stderr
    revisions = [h for h in listing.stdout.split("\n") if h.strip()]
    assert len(revisions) >= 10, (
        f"only {len(revisions)} revisions of {WORKFLOW_FILE} are reachable, which is too few "
        "to read a 'never at any revision' claim from"
    )

    totals: dict[int, int] = {}
    thirteen_revisions: list[str] = []
    six_with_lint: list[str] = []
    for revision in revisions:
        shown = subprocess.run(
            ["git", "-C", str(repo_root), "show", f"{revision}:{WORKFLOW_FILE.as_posix()}"],
            capture_output=True,
            check=False,
        )
        assert shown.returncode == 0, (
            f"{WORKFLOW_FILE} is not readable at {revision[:12]}. A 'never at any revision' "
            "claim cannot be read from a history the witness cannot open."
        )
        document = yaml.safe_load(shown.stdout)
        jobs = document.get("jobs")
        assert isinstance(jobs, dict), f"{WORKFLOW_FILE} at {revision[:12]} declares no jobs"
        rendered = len(rendered_job_names(document, WORKFLOW_FILE.name))
        totals[rendered] = totals.get(rendered, 0) + 1
        if rendered == _THIRTEEN_JOBS:
            thirteen_revisions.append(revision[:12])

        strategy = jobs.get("python-quality", {}).get("strategy")
        matrix = strategy.get("matrix") if isinstance(strategy, dict) else None
        shard_axis = matrix.get("shard") if isinstance(matrix, dict) else None
        if isinstance(shard_axis, list) and len(shard_axis) >= 6 and "lint" in jobs:
            six_with_lint.append(revision[:12])

    assert not thirteen_revisions, (
        f"{WORKFLOW_FILE} rendered {_THIRTEEN_JOBS} job names at {'/'.join(thirteen_revisions)}. "
        f"The totals across {len(revisions)} revisions are {sorted(totals)}. The records' "
        "'thirteen was never the count' sentence is then a dated snapshot rather than an error, "
        "and every place that says so has to say which."
    )
    assert not six_with_lint, (
        f"{'/'.join(six_with_lint)} declared both a six-or-more-shard matrix and a `lint` job "
        f"on {WORKFLOW_FILE}. That pairing is exactly what thirteen counts, so it is the pairing "
        "the corrected records deny; if a revision had it, the denial describes a tree that no "
        "longer exists."
    )


# --------------------------------------------------------------------------
# A superseded dated record has to say it was superseded
# --------------------------------------------------------------------------
#
# The project's rule, restated in the owner's 2026-11-12 decision: a stale sentence in
# a **dated snapshot** is a historical fact and keeps its wording; a stale sentence in a
# **current pointer** is a defect and gets corrected. The correction half is watched —
# `test_the_current_pointers_agree_with_the_measured_required_check_set` refuses the
# phrases the 2026-11-11 reading contradicts in `CLAUDE.md`, `docs/handoff/CURRENT.md`
# and `docs/REPOSITORY-MAP.md`. **The other half was watched by nothing**: no check asked
# whether a dated sentence the tree had since overtaken was *marked* as superseded rather
# than quietly rewritten, or quietly left standing.
#
# The gap is not hypothetical. `.github/CI.md` §"2026-11-02 — lint split out of the shard
# jobs" states that `lint` "is **not a required status check**", while the marked
# required-check block in the same file lists `lint` among the fifteen contexts read from
# GitHub on 2026-11-11. Both sentences are in one file, both readable locally, and nothing
# compared them. The correction that landed on 2026-11-12 kept the older sentence and added
# a marker; this is what notices if the next one does not.
#
# **What "marked" has to mean, or the check is decoration.** A block that says "superseded
# since" without saying *since what* is a sentence with a label on it. The marker has to
# locate the later reading — a revision in this repository, a record file here, or a command
# a reader can run — and name a date **after** its own section's date. A marker naming only
# the section's own date restates the snapshot and supersedes nothing.

#: The records whose **dated sections** this witness reads. The scope is declared rather
#: than swept: `docs/` holds 195 Markdown files, and most dated prose in them is history
#: about another project, another machine or a decision, which no local measurement
#: contradicts. What is read here is where a dated claim meets a quantity this repository
#: can re-measure — the required-check set, whose names the workflows either report or do
#: not.
DATED_SNAPSHOT_RECORDS: Final[tuple[Path, ...]] = (
    REQUIRED_CHECK_RECORD,
    Path("CLAUDE.md"),
    Path("docs") / "README.md",
    Path("docs") / "ROADMAP.md",
    Path("docs") / "REPOSITORY-MAP.md",
    Path("docs") / "handoff" / "CURRENT.md",
    Path("docs") / "RELEASE-NOTES.md",
    Path("docs") / "plans" / "LC-P1-13-evaluation-ci.md",
)

_SECTION_DATE: Final[re.Pattern[str]] = re.compile(r"20\d\d-\d\d-\d\d")

#: The marker phrase the 2026-11-12 convention settled on.
SUPERSESSION_MARKER: Final[re.Pattern[str]] = re.compile(r"dated snapshot", re.I)

#: A statement that a check is not required. The subject is resolved from the same
#: paragraph, because the records put the name in one clause and the negation in the next:
#: "`lint` is a check the workflow reports; it is **not a required status check**".
NOT_A_REQUIRED_CHECK: Final[re.Pattern[str]] = re.compile(
    r"\bis not a required(?: status)? check|\bnot a required status check"
    r"|\bdoes not (?:block|gate) a merge\b|\bit cannot be one\b",
    re.I,
)
#: A name a record cites as code — the shape every job and check name in these records has.
CITED_NAME: Final[re.Pattern[str]] = re.compile(r"`([A-Za-z][A-Za-z0-9 ()_./,{}-]{1,60})`")

#: What a marker may point a reader at. A date alone is not on this list: it renumbers the
#: snapshot rather than locating a later reading.
MARKER_COMMAND: Final[re.Pattern[str]] = re.compile(
    r"\b(gh api|git merge-base|git cat-file|git ls-files|git log|python \.github/\S+)\b"
)
MARKER_LINK: Final[re.Pattern[str]] = re.compile(r"\]\(([^)\s]+)\)")


def _markdown_sections(text: str) -> list[dict[str, Any]]:
    """Each `##`-level section of a record, with its heading and its lines."""
    out: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for number, line in enumerate(text.split("\n"), start=1):
        heading = re.match(r"^#{2,6}\s+(.*?)\s*#*\s*$", line)
        if heading:
            if current:
                out.append(current)
            current = {"heading": heading.group(1), "start": number, "lines": []}
            continue
        if current is not None:
            current["lines"].append((number, line))
    if current:
        out.append(current)
    return out


def _marker_blocks(lines: list[tuple[int, str]]) -> list[dict[str, Any]]:
    """Every supersession marker in a section, with what each one actually names.

    A marker is read as the **run of `>` lines it sits in**, not as the one line that
    matched. The block is where the later reading is written: CI.md's marker spans ten
    lines, and its revisions, its dates and its `gh api` command sit on lines a one-line
    reader never sees. That is also what makes a marker removable without the word
    "snapshot" surviving in the file — which is what the demonstration below does.
    """
    out: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        _number, line = lines[index]
        if not SUPERSESSION_MARKER.search(line):
            index += 1
            continue
        first = index
        while first > 0 and lines[first - 1][1].startswith(">"):
            first -= 1
        last = index
        while last + 1 < len(lines) and lines[last + 1][1].startswith(">"):
            last += 1
        block = " ".join(text_line for _number, text_line in lines[first : last + 1])
        out.append(
            {
                "first_line": lines[first][0],
                "last_line": lines[last][0],
                "dates": _SECTION_DATE.findall(block),
                "revisions": FULL_SHA.findall(block),
                "links": [m.group(1) for m in MARKER_LINK.finditer(block)],
                "commands": sorted({m.group(1) for m in MARKER_COMMAND.finditer(block)}),
            }
        )
        index = last + 1
    return out


def _section_paragraphs(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """The section's prose paragraphs, with a marker block excluded from them.

    The marker is not a claim; it is the record's note *about* a claim. Reading it as
    another paragraph would let a marker answer the question it exists to answer.
    """
    out: list[tuple[int, str]] = []
    buffer: list[str] = []
    start = 0
    for number, line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(">"):
            if buffer:
                out.append((start, " ".join(buffer)))
                buffer = []
            continue
        if not buffer:
            start = number
        buffer.append(stripped)
    if buffer:
        out.append((start, " ".join(buffer)))
    return out


def _commit_exists(repo_root: Path, revision: str) -> bool:
    return (
        subprocess.run(
            ["git", "-C", str(repo_root), "cat-file", "-e", f"{revision}^{{commit}}"],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def _superseded_dated_claims(
    repo_root: Path, text: str, contexts: list[str]
) -> list[dict[str, Any]]:
    """Dated-section claims that this record's own required-check reading contradicts.

    **Only claims whose subject is in the measured set.** `docs/handoff/CURRENT.md` and
    `docs/plans/LC-P1-13-evaluation-ci.md` both say the `evaluation` job is not a required
    check, and both are **true** — `evaluation` is not among the fifteen contexts and cannot
    be, because GitHub fires a schedule only from the default branch. A witness that reddened
    on those sentences would be banning a phrase rather than measuring a referent. The check
    is "does the record's own list require this name", not "does the file contain the words".
    """
    claimed: list[dict[str, Any]] = []
    for section in _markdown_sections(text):
        section_date = _SECTION_DATE.search(section["heading"])
        if section_date is None:
            # An undated section makes a current claim, and current claims belong to
            # `test_the_current_pointers_agree_with_the_measured_required_check_set`.
            continue
        for paragraph_start, paragraph in _section_paragraphs(section["lines"]):
            # Emphasis is stripped and code spans are kept, so the name positions in the
            # string are the positions the name-citation and the negation are compared at.
            plain = re.sub(r"[*_]+", " ", paragraph)
            negation = NOT_A_REQUIRED_CHECK.search(plain)
            if negation is None:
                continue
            # The subject is a name cited **before** the negation. CI.md writes "`lint` is a
            # check the workflow reports; it is **not a required status check**", so the name
            # sits in the earlier clause and the negation in the later one. Requiring the name
            # to precede stops a name mentioned after the claim from being read as its subject.
            subjects = [m.group(1) for m in CITED_NAME.finditer(plain[: negation.start()])]
            required = next(
                (
                    context
                    for name in reversed(subjects)
                    for context in contexts
                    if name == context or context.startswith(f"{name} (")
                ),
                None,
            )
            if required is None:
                continue
            claimed.append(
                {
                    "line": paragraph_start,
                    "subject": required,
                    "section": section["heading"],
                    "section_date": section_date.group(0),
                    "section_start": section["start"],
                    "matched": negation.group(0),
                }
            )
    return claimed


def _marker_problems(
    repo_root: Path, claim: dict[str, Any], record: Path, markers: list[dict[str, Any]]
) -> list[str]:
    """Why none of a section's markers carries the supersession the claim needs."""
    if not markers:
        return [
            f"{record}:{claim['line']} says {claim['subject']!r} {claim['matched']!r} inside the "
            f"dated section {claim['section']!r}, and the section carries no supersession marker. "
            f"The same record's required-check block lists {claim['subject']!r}, so the sentence "
            "is contradicted by a reading this repository can re-run. Either correct it to the "
            "current state, or keep it as written and mark it."
        ]
    problems: list[str] = []
    for marker in markers:
        refusals: list[str] = []
        real = [r for r in marker["revisions"] if _commit_exists(repo_root, r)]
        fake = [r for r in marker["revisions"] if not _commit_exists(repo_root, r)]
        resolved_links = [
            link
            for link in marker["links"]
            if (repo_root / link).exists() or (repo_root / "docs" / link).exists()
        ]
        locators = real + resolved_links + list(marker["commands"])
        if not locators:
            refusals.append(
                f"the marker at {record}:{marker['first_line']} names no revision that exists "
                f"here, no record file here and no runnable command"
                + (
                    f" — the full revisions it cites ({', '.join(h[:12] + '…' for h in fake)}) "
                    "are not commits in this repository"
                    if fake
                    else ""
                )
                + ", so a reader cannot find the reading that supersedes the sentence"
            )
        elif fake:
            refusals.append(
                f"the marker at {record}:{marker['first_line']} cites "
                f"{', '.join(h[:12] + '…' for h in fake)}, which is not a commit in this repository"
            )
        later = sorted(d for d in marker["dates"] if d > claim["section_date"])
        if not later:
            refusals.append(
                f"the marker at {record}:{marker['first_line']} names no date after its section's "
                f"own {claim['section_date']} (it names {marker['dates'] or 'none'}), so it "
                "restates the snapshot instead of superseding it"
            )
        if not refusals:
            return []
        problems.extend(refusals)
    return problems


def test_a_superseded_dated_record_carries_a_marker_naming_the_later_reading(
    repo_root: Path,
) -> None:
    """A dated sentence the tree has overtaken is kept **and marked**, or corrected.

    **The property.** `.github/CI.md` carries the required-check set as data: a marked block
    listing fifteen contexts, whose names the witness above checks against every workflow.
    When a *dated section* of a record states that one of those names is not a required
    check, the record contradicts itself and only one of the two sentences can be about
    today. The project's rule lets the dated one stay exactly as written **provided it is
    marked as superseded**. Nothing watched that "provided".

    **What a marker has to do.** Name where the later reading is — a revision that exists in
    this repository, a record file that exists here, or a command a reader can run — and name
    a date after the section's own date. `superseded since` with nothing after it is a label
    on a sentence, not a pointer. CI.md's marker passes both ways: it cites `6b3211ae…`
    (2026-11-11) and `0655bb8b…` (2026-11-12) and prints the `gh api` call that renews the
    reading.

    **What this does not watch, said out loud.** Undated sections — the current pointers — are
    policed by `test_the_current_pointers_agree_with_the_measured_required_check_set`, which
    refuses the contradicting phrases there instead of asking for a marker. A dated claim whose
    subject is **not** in the required set is left alone on purpose: `evaluation` genuinely is
    not a required check, and a witness that reddens on true sentences is a witness that gets
    switched off. And a marker's prose is not judged — only whether it points somewhere a
    reader can follow.
    """
    contexts, _anchor = _required_contexts(repo_root)
    assert contexts, f"{REQUIRED_CHECK_RECORD} lists no required contexts to contradict"

    problems: list[str] = []
    contradicted = 0
    for relative in DATED_SNAPSHOT_RECORDS:
        path = repo_root / relative
        assert path.is_file(), f"{relative} is a record this witness reads, and it is not there"
        text = path.read_text(encoding="utf-8")
        sections = _markdown_sections(text)
        for claim in _superseded_dated_claims(repo_root, text, contexts):
            contradicted += 1
            section = next(s for s in sections if s["start"] == claim["section_start"])
            problems.extend(
                _marker_problems(repo_root, claim, relative, _marker_blocks(section["lines"]))
            )

    assert not problems, (
        "a dated record states something its own measured reading contradicts, and the "
        "supersession is not carried properly:\n  "
        + "\n  ".join(problems)
        + "\n\nThe project's rule: a stale sentence in a dated snapshot is a historical fact and "
        "keeps its wording — **if it is marked**, and the marker names the later reading. A "
        "stale sentence left unmarked is either an unmarked supersession or a wrong sentence, "
        "and the record has to say which."
    )
    assert contradicted, (
        "no dated record contradicts the required-check reading any more. This witness exists to "
        "check what happens to a dated sentence the tree overtakes; if nothing in the records is "
        "such a sentence, the dated history was flattened into present tense and the witness is "
        "looking at nothing."
    )


def test_the_supersession_marker_check_fails_when_a_marker_is_deleted_or_hollow(
    repo_root: Path,
) -> None:
    """The marker check is seen to fail for the property, on copies held in memory.

    **The baseline that makes the demonstration meaningful.** `.github/CI.md` today carries
    exactly one dated claim its own required-check block contradicts — `lint` "is not a
    required status check" in §"2026-11-02 — lint split out of the shard jobs" — covered by
    the marker at line 265. The unmutated copy therefore reports nothing.

    **Three mutations, each one a distinct way the convention fails.** (1) **The marker block
    is deleted**: the stale sentence stands alone, which is the exact hole this witness exists
    for. (2) **The marker's revisions are replaced by a well-formed revision that is not a
    commit here, and its `gh api` command removed**: the marker still says "superseded since",
    still carries dates, and points nowhere a reader can follow. (3) **The marker keeps its
    real revisions but its later dates are moved onto the section's own date**: it then names
    no later reading, so it restates the snapshot rather than superseding it. Each mutation is
    asserted to change bytes before any report is credited to it.

    **Control.** The real `CI.md` bytes are compared before and after, so the demonstration is
    provably unable to write the record it guards.
    """
    record = repo_root / REQUIRED_CHECK_RECORD
    original_bytes = record.read_bytes()
    text = original_bytes.decode("utf-8")

    contexts, _anchor = _required_contexts(repo_root)
    baseline = _superseded_dated_claims(repo_root, text, contexts)
    assert len(baseline) == 1, (
        f"{REQUIRED_CHECK_RECORD} now carries {len(baseline)} dated claims its own required-check "
        "block contradicts. The demonstrations below mutate a specific one, so they have to be "
        "re-read against the record before these numbers change."
    )
    claim = baseline[0]
    sections = _markdown_sections(text)
    baseline_section = next(s for s in sections if s["start"] == claim["section_start"])
    baseline_markers = _marker_blocks(baseline_section["lines"])
    assert baseline_markers, (
        f"the dated claim at {REQUIRED_CHECK_RECORD}:{claim['line']} has no marker in this tree, "
        "so the main witness is already red and this demonstration would be testing a broken "
        "record rather than a reader"
    )
    marker_first = baseline_markers[0]["first_line"]
    marker_last = baseline_markers[0]["last_line"]
    lines = text.split("\n")
    assert lines[marker_first - 1].startswith(">"), (
        f"the marker block is expected to begin at line {marker_first} with a `>` line; the "
        f"reader found {lines[marker_first - 1][:60]!r}"
    )

    def reports(mutated: str) -> list[str]:
        found: list[str] = []
        mutated_sections = _markdown_sections(mutated)
        for mutated_claim in _superseded_dated_claims(repo_root, mutated, contexts):
            start = mutated_claim["section_start"]
            section = next(s for s in mutated_sections if s["start"] == start)
            markers = _marker_blocks(section["lines"])
            found.extend(_marker_problems(repo_root, mutated_claim, REQUIRED_CHECK_RECORD, markers))
        return found

    assert reports(text) == [], f"the unmutated record reports: {reports(text)}"

    # Mutation 1: the marker block is removed and the stale sentence stands alone.
    kept = [
        line
        for index, line in enumerate(lines, start=1)
        if not marker_first <= index <= marker_last
    ]
    without_marker = "\n".join(kept)
    assert without_marker != text, "removing the marker block changed no bytes"
    removed_reports = reports(without_marker)
    assert any("no supersession marker" in report for report in removed_reports), (
        f"deleting the marker block left the stale dated sentence covered: {removed_reports}. "
        "Then the witness is not reading the marker at all."
    )

    # The marker block as written, shared by the two mutations below so each one edits the
    # same span of the record rather than a pattern that could match elsewhere in the file.
    marker_text = "\n".join(lines[marker_first - 1 : marker_last])

    # Mutation 2: a marker that points nowhere.
    real_revisions = baseline_markers[0]["revisions"]
    assert real_revisions, "the marker names no revision, so this control has nothing to replace"
    impostor = "f" * 40
    assert not _commit_exists(repo_root, impostor), (
        f"{impostor[:12]}… resolves to a commit here, so replacing the marker's revisions with "
        "it would not make the marker hollow"
    )
    # Both edits are applied **inside the marker block**, and the block is then swapped back
    # into the record once. A revision the marker cites also appears in the required-check
    # block's begin marker 220 lines earlier, so replacing over the whole record — even with
    # `count=1` — would edit the anchor of the reading instead of the marker that cites it,
    # and the demonstration would break the thing it is meant to leave intact.
    hollow_marker = marker_text
    for revision in real_revisions:
        hollow_marker = hollow_marker.replace(revision, impostor)
    hollow_marker = MARKER_COMMAND.sub("the owner has since added it", hollow_marker)
    assert hollow_marker != marker_text, "the marker edit changed nothing inside the marker block"
    hollow = text.replace(marker_text, hollow_marker, 1)
    assert hollow != text, "the marker-hollowing mutation changed no bytes"
    hollow_reports = reports(hollow)
    assert any("names no revision that exists here" in report for report in hollow_reports), (
        "a marker citing a non-existent commit and naming no command was accepted: "
        f"{hollow_reports}"
    )

    # Mutation 3: a marker that points at a real reading but not at a *later* one.
    same_date = marker_text
    for date in sorted(set(_SECTION_DATE.findall(marker_text))):
        if date != claim["section_date"]:
            same_date = same_date.replace(date, claim["section_date"])
    assert same_date != marker_text, (
        "the marker names no date other than its section's own, so this control has nothing to move"
    )
    no_later_date = text.replace(marker_text, same_date, 1)
    assert no_later_date != text, "the date mutation changed no bytes"
    date_reports = reports(no_later_date)
    assert any("no date after its section" in report for report in date_reports), (
        f"a marker naming no later date was accepted: {date_reports}. `superseded since` "
        "with nothing after it is a label, not a pointer."
    )

    assert record.read_bytes() == original_bytes, (
        f"{REQUIRED_CHECK_RECORD} changed while it was being read"
    )
