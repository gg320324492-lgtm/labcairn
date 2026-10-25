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

import json
from pathlib import Path
from typing import Any, Final

import pytest
import yaml

#: The shard file, next to the workflow that uses it.
SHARD_FILE: Final[Path] = Path(".github") / "ci-shards.json"

#: The workflow that uses it.
WORKFLOW_FILE: Final[Path] = Path(".github") / "workflows" / "python.yml"

#: The platforms the workflow runs on. The partition is per platform.
PLATFORMS: Final[tuple[str, ...]] = ("ubuntu-latest", "windows-latest")


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
    assert not changed, (
        f"the shard costs were measured at {measured_at} and these files have "
        f"changed since, so the costs no longer describe the tree:\n  "
        + "\n  ".join(changed)
        + "\n\nRe-measure the costs on the runner and regenerate the shard file."
    )


def _changed_paths(repo_root: Path, since: str) -> list[str]:
    """The files under ``src/`` and ``tests/`` that changed since ``since``.

    **The shard file and the witness that reads it are excluded**, and the
    reason is in the test above: they are where the measurement is recorded,
    and they are the things a rebalance changes.
    """
    import subprocess

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
        # The commit is not in this checkout; the costs cannot be checked, and
        # saying so is better than passing.
        return [f"the commit {since} is not in this checkout, so the costs cannot be checked"]
    return [
        line
        for line in proc.stdout.splitlines()
        if line.strip() and line.strip() not in EXCLUDED_FROM_THE_COST_CHECK
    ]


#: The files whose own cost is not what the table is about.
EXCLUDED_FROM_THE_COST_CHECK: frozenset[str] = frozenset({"tests/test_ci_shard_coverage.py"})


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
