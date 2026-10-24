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

#: How far the slowest shard may be from the fastest, as a multiple. The
#: costs are measured, and they are only as fresh as the last measurement —
#: so this is generous enough that an ordinary new test does not trip it, and
#: tight enough that a *slow* new test does.
BALANCE_LIMIT: Final[float] = 1.6


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
    assert "matrix.workers" in name, (
        "the python-quality job's name does not mention matrix.workers, so two "
        "runs of the same shard under different worker counts share a name"
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
        shard_costs = [
            sum(float(costs.get(Path(name).name, 0.0)) for name in shard)
            for shard in _shards(repo_root, platform)
        ]
        cheapest = min(shard_costs)
        dearest = max(shard_costs)
        assert cheapest > 0, "the recorded costs are all zero, so they measure nothing"
        assert dearest <= cheapest * BALANCE_LIMIT, (
            f"the {platform} shards are not balanced: the dearest costs "
            f"{dearest:.0f}s and the cheapest {cheapest:.0f}s, a factor of "
            f"{dearest / cheapest:.2f} (limit {BALANCE_LIMIT}). Regenerate the "
            "shard file."
        )


def test_the_recorded_costs_cover_every_test_file(repo_root: Path) -> None:
    """A cost is recorded for every file, so the balance is measured on all of it.

    A file with no recorded cost counts as zero, which would make its shard
    look cheaper than it is — and the balance check above would pass on a
    number that was never measured.
    """
    files = {path.name for path in (repo_root / "tests").glob("test_*.py")}
    costs = _shard_document(repo_root).get("costs", {})
    missing = files - set(costs)
    assert not missing, (
        f"these test files have no measured cost recorded: {sorted(missing)}. "
        "Regenerate the shard file."
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
