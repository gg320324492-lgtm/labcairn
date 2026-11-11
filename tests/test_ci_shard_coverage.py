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

import importlib.util
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any, Final

import pytest
import yaml
from evaluation import manifest
from workflow_job_names import load_workflows, rendered_job_names

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

    dated = [p for p in paragraphs if "test_cli" in p or DATED_MEASUREMENT.search(p)]
    assert any("2026-10-25" in p for p in dated), (
        "the shard-count decision is no longer recorded with the measurement it was "
        "taken on, so the figures it quotes have no tree to belong to"
    )


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
            "run would spend thirteen jobs instead of one"
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
    thirteen — is a design decision the workflow's own comment records, and
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

    **How it is checked, rather than restated.** Each pointer must carry the
    record's own anchor — the full revision the reading was taken at — so a
    number in a pointer is attached to the measurement it came from, and the
    sentences that the measurement contradicts must not be present. The count is
    not written a fourth time here: it is read from the record.

    **What it cannot watch.** Whether the owner changes the required set tomorrow.
    That is a GitHub setting; what is watched is that the tree's own sentences
    are not left behind.
    """
    _contexts, anchor = _required_contexts(repo_root)

    for relative in (Path("CLAUDE.md"), Path("docs") / "handoff" / "CURRENT.md"):
        text = (repo_root / relative).read_text(encoding="utf-8")
        assert anchor in text, (
            f"{relative} states something about required checks without naming the "
            f"revision `{anchor}` that `.github/CI.md` measured them at, so the "
            "reader cannot tell a reading from a memory"
        )
        stale = [
            phrase
            for phrase in (
                "sixteen required checks",
                "`lint` is not a required check",
                "not a required check until the owner adds",
            )
            if phrase in text
        ]
        assert not stale, (
            f"{relative} still says {stale}, which the measured set contradicts: "
            f"`lint` is among the required contexts recorded at {anchor}. "
            "Correct the sentence against the measurement rather than leaving "
            "both in the tree."
        )


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

    # The enumeration runs from the colon to the first `. that ends a sentence
    # — which is why the file names are matched explicitly rather than split on
    # `.`, because `lockfiles.yml` and `provider-smoke.yml` both contain one.
    tail = text[stated.end() :]
    listed = set(re.findall(r"`([a-z0-9-]+\.ya?ml)`", tail[:1200]))
    assert listed == {path.name for path in paths}, (
        f"the map enumerates {sorted(listed)} and the directory holds "
        f"{sorted(path.name for path in paths)}: a directory listing with a file "
        "missing is a listing that was not read"
    )
    anchor_match = FULL_SHA.search(tail[:1200])
    assert anchor_match is not None, (
        "the map's workflow sentence names no revision, so the count is a memory "
        "rather than a reading"
    )


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
