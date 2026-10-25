"""Rebuild the CI shard file.

**What this is for.** The CI workflow runs the suite in shards, each shard in
its own job on its own runner, because one runner doing everything is the
worst possible arrangement for a suite whose cost is spread unevenly. The
shards are balanced against **measured** per-file costs, and this script does
the balancing.

**One partition per platform.** The two runners do not cost the same, and
they do not cost the same *in the same proportions* either: measured on the
runner, one file took 383 seconds on Windows and 45 on Ubuntu, and another
took 153 on Ubuntu and 288 on Windows. A partition balanced for one platform
is lopsided on the other, so each platform gets its own. The two partitions
run **the same tests** — only the arrangement differs.

**When to run it.** When a test file is added, or when
``tests/test_ci_shard_coverage.py`` goes red. That test is the watch: it
fails if a test file is in no shard, in two shards, if the shard count
disagrees with the workflow's matrix, if a cost is missing, or if the shards
have drifted out of balance. **It fails first; this script is the fix.**

**The costs come from a measurement, not from an estimate.** The measured
costs are recorded in the shard file itself, so this script can re-balance
without re-measuring, and so the balance check has something measured to
check against. A file that has never been measured has no cost yet; the
script refuses to guess one, and says what to run to get it.

**How the costs were measured.** On the runner, not on a development
machine: a machine with other work on it gives a different answer, and not
only a different total — a different *order*. The CI job runs pytest with
``--durations=0``, and the per-file seconds are read out of the durations
section of the log. (``-vv`` is what shows the durations of tests that finish
in under five milliseconds, which is most of a fast file's tests.)

**Usage:**

    python .github/make_ci_shards.py [--shards N] [--platform NAME]

``--platform`` rebuilds one platform's partition and leaves the other alone;
without it, both are rebuilt. The costs are reused, not re-measured, so the
numbers stay the measured ones.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARD_FILE = REPO_ROOT / ".github" / "ci-shards.json"
TESTS = REPO_ROOT / "tests"

#: The platforms the workflow runs on.
PLATFORMS = ("ubuntu-latest", "windows-latest")


def test_files() -> list[str]:
    """Every test file, by name."""
    return sorted(path.name for path in TESTS.glob("test_*.py"))


def load() -> dict[str, Any]:
    if not SHARD_FILE.is_file():
        return {"shards": {}, "costs": {}}
    return json.loads(SHARD_FILE.read_text(encoding="utf-8"))


def shard_count(document: dict[str, Any]) -> int:
    """How many shards the file already has, whatever shape it is in."""
    shards = document.get("shards", {})
    if isinstance(shards, dict):
        for value in shards.values():
            if isinstance(value, list) and value:
                return len(value)
        return 0
    if isinstance(shards, list) and shards:
        return len(shards)
    return 0


def balance(files: list[str], costs: dict[str, float], shards: int) -> list[list[str]]:
    """The shards, balanced by cost.

    Longest-processing-time first: the most expensive file goes to the
    cheapest shard, and so on. That is the standard greedy bound, and it
    lands within a few percent of optimal for the cost spread this suite
    has.
    """
    groups: list[list[str]] = [[] for _ in range(shards)]
    loads = [0.0] * shards
    for name in sorted(files, key=lambda n: -costs.get(n, 0.0)):
        index = loads.index(min(loads))
        groups[index].append(name)
        loads[index] += costs.get(name, 0.0)
    return groups


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shards", type=int, default=None, help="how many shards")
    parser.add_argument(
        "--platform",
        choices=PLATFORMS,
        default=None,
        help="rebuild one platform's partition and leave the other alone",
    )
    args = parser.parse_args()

    document = load()
    all_costs = document.get("costs", {})
    files = test_files()

    missing = [
        name
        for name in files
        if any(name not in all_costs.get(platform, {}) for platform in PLATFORMS)
    ]
    if missing:
        print(
            "these files have never been measured, and this script will not "
            "guess a cost for them:\n  " + "\n  ".join(missing) + "\n\nMeasure them on the "
            "runner: read the per-file seconds out of the durations section of "
            "a CI log (the pytest step runs with --durations=0), and add them "
            'to the "costs" in ' + str(SHARD_FILE.relative_to(REPO_ROOT)) + ".",
            file=sys.stderr,
        )
        return 1

    shards = args.shards or shard_count(document) or 4
    partitions = document.get("shards", {})
    if not isinstance(partitions, dict):
        partitions = {}

    for platform in PLATFORMS:
        if args.platform is not None and args.platform != platform:
            continue
        costs = all_costs.get(platform, {})
        # The shards name paths relative to the repository root, not bare file
        # names, because the workflow hands them to pytest as arguments and a
        # bare name is not a path pytest can find.
        groups = [[f"tests/{name}" for name in group] for group in balance(files, costs, shards)]
        partitions[platform] = groups
        loads = [sum(costs.get(Path(n).name, 0.0) for n in g) for g in groups]
        print(f"{platform}: {len(groups)} shards")
        for index, group_load in enumerate(loads):
            print(f"  shard {index}: {group_load:8.1f}s")
        print(f"  balance factor: {max(loads) / min(loads):.3f}")

    SHARD_FILE.write_text(
        json.dumps(
            {
                # The commit the costs were measured at. It is carried through
                # unchanged: a rebalance does not re-measure, and a measurement
                # is the only thing that may change it.
                "measured_at": document.get("measured_at"),
                "shards": partitions,
                "costs": {
                    platform: {name: round(all_costs[platform][name], 2) for name in files}
                    for platform in PLATFORMS
                    if platform in all_costs
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"written {SHARD_FILE.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
