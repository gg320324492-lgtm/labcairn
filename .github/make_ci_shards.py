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

**A partition also has to be somewhere a merge waits for.** Branch protection
names the legs it waits for, and a leg it does not name is a leg a merge can
go without. So a test file that sits **only** in an unnamed leg is a test file
no required check runs — the same hole as a file in no shard at all, wearing a
different hat. Reading the protection on 2026-11-18 found the two ``shard 5``
legs unnamed, and nine test files sat only in them.

So the partition this script writes keeps **every** test file in at least one
leg branch protection waits for, on at least one platform. The unprotected
leg is filled by swapping: a file is taken out of it and put into a protected
leg, and a file of nearly the same measured cost takes its place, so the
balance the measurement implies survives the move (the pairs differ by a
fraction of a second, and the legs keep their loads to within that).

**Which legs are protected is read, not assumed.** The set of protected legs
is a setting on GitHub, and the repository keeps a **dated reading** of it in
``docs/ci/required-checks-reading.json``; this script reads that. When the
owner adds the two missing legs to branch protection, the reading changes,
the constraint has nothing left to repair, and the partition returns to being
the plain balance. Nothing here reads GitHub, so the reading is the only
place that can be out of date — and ``tests/test_ci_shard_coverage.py``
watches that the reading and the tree agree.

**Usage:**

    python .github/make_ci_shards.py [--shards N] [--platform NAME]
    python .github/make_ci_shards.py --check

``--platform`` rebuilds one platform's partition and leaves the other alone;
without it, both are rebuilt. The costs are reused, not re-measured, so the
numbers stay the measured ones.

``--check`` asks the question the other way round: it reads the partition on
disk and reports the files that are outside every protected leg, without
writing anything. It is what the ``lint`` job runs, so the property is
watched on every pull request instead of being a fact that was true once.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Final

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARD_FILE = REPO_ROOT / ".github" / "ci-shards.json"
TESTS = REPO_ROOT / "tests"

#: The platforms the workflow runs on.
PLATFORMS = ("ubuntu-latest", "windows-latest")

#: The dated reading of branch protection: the legs a merge waits for.
READING_FILE = REPO_ROOT / "docs" / "ci" / "required-checks-reading.json"

#: A shard leg's name, the way branch protection identifies it.
LEG_NAME: Final[re.Pattern[str]] = re.compile(
    r"^python-quality \((?P<platform>[^,]+), shard (?P<shard>\d+)\)$"
)


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


def protected_shards() -> dict[str, set[int]] | None:
    """The shard indices branch protection waits for, per platform.

    **Read from the dated reading**, not from a constant written here: the
    set of protected legs is a setting that changes, and the reading is the
    file that records it. A constant in this script would go stale the way the
    matrix's leg count did.

    **None when there is no reading to read.** A checkout that carries only
    the two shard tools — the remeasurement witness builds one, so that the
    arithmetic it checks does not depend on this repository's corpus — has no
    reading in it, and a tool that cannot read it balances the partition and
    says so. It does not guess which legs are protected.

    **It refuses a reading that is there and broken.** A reading that names no
    shard leg for a platform would say that no leg of that platform is one a
    merge waits for, and the repair would then have nowhere to put a file;
    that is a broken reading, not a partition to build.
    """
    if not READING_FILE.is_file():
        return None
    reading = json.loads(READING_FILE.read_text(encoding="utf-8"))
    contexts = reading.get("required_contexts")
    if not isinstance(contexts, list):
        return None
    protected: dict[str, set[int]] = {platform: set() for platform in PLATFORMS}
    for context in contexts:
        match = LEG_NAME.match(str(context))
        if match is None:
            continue
        platform = match.group("platform")
        if platform in protected:
            protected[platform].add(int(match.group("shard")))
    empty = sorted(platform for platform, shards in protected.items() if not shards)
    if empty:
        print(
            f"the reading names no shard leg for {', '.join(empty)}, so no leg "
            "of that platform is one a merge waits for. That is a broken "
            "reading, not a partition to build.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return protected


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


def _loads(groups: list[list[str]], costs: dict[str, float]) -> list[float]:
    """What each group costs, by the measured costs."""
    return [sum(costs.get(Path(name).name, 0.0) for name in group) for group in groups]


def _locations(partitions: dict[str, list[list[str]]]) -> dict[str, dict[str, int]]:
    """Where each file is, per platform: the index of the leg holding it."""
    locations: dict[str, dict[str, int]] = {}
    for platform, groups in partitions.items():
        for index, group in enumerate(groups):
            for name in group:
                locations.setdefault(name, {})[platform] = index
    return locations


def files_outside_every_protected_leg(
    partitions: dict[str, list[list[str]]],
    protected: dict[str, set[int]],
) -> list[str]:
    """The files no leg a merge waits for runs.

    A file is outside every protected leg when **every** leg it is in is one
    branch protection does not name. One protected leg is enough: the file is
    then run by a check a merge waits for, on that platform.
    """
    outside = []
    for name, where in sorted(_locations(partitions).items()):
        if all(index not in protected.get(platform, set()) for platform, index in where.items()):
            outside.append(name)
    return outside


def repair_protected_legs(
    partitions: dict[str, list[list[str]]],
    costs: dict[str, float],
    protected: dict[str, set[int]],
) -> list[tuple[str, str, int, str]]:
    """Move every file outside every protected leg into one, by swapping.

    **The move is a swap, and that is the point.** A file is taken out of the
    unprotected leg and put into a protected one, and a file of nearly the
    same measured cost takes its place in the unprotected leg. The two legs
    therefore keep the load they had, to within the difference between the
    two files' measured costs — for most pairs a fraction of a second — and
    the partition stays as balanced as the measurement made it. A plain move
    would have shifted every second of the file's cost into another leg, and
    the legs were within a hundredth of a second of each other to begin with.

    **The partner has to be protected on the other platform too**, or the
    swap would move the hole rather than fill it: the partner leaves a
    protected leg for an unprotected one, and only a partner that is still
    protected on the other platform stays covered.

    **The pair is chosen to keep the balance.** Among the partners whose
    measured cost is closest to the file's, the one whose leg would end up
    lightest is taken, so the repair spreads over the legs rather than piling
    onto one.
    """
    swaps: list[tuple[str, str, int, str]] = []
    for name in files_outside_every_protected_leg(partitions, protected):
        where = _locations(partitions)[name]
        best: tuple[tuple[float, float, str, int], str, int, str] | None = None
        for platform in PLATFORMS:
            if platform not in where or platform not in protected:
                continue
            cost = costs.get(platform, {}).get(Path(name).name, 0.0)
            platform_costs = costs.get(platform, {})
            platform_loads = _loads(partitions[platform], platform_costs)
            for index in sorted(protected[platform]):
                for partner in partitions[platform][index]:
                    if partner == name:
                        continue
                    partner_where = _locations(partitions)[partner]
                    # After the swap the partner sits in this platform's
                    # unprotected leg, so it needs a protected leg on some
                    # *other* platform — otherwise the swap would move the
                    # hole rather than fill it.
                    if not any(
                        other_index in protected.get(other, set())
                        for other, other_index in partner_where.items()
                        if other != platform
                    ):
                        continue
                    partner_cost = platform_costs.get(Path(partner).name, 0.0)
                    key = (
                        round(abs(partner_cost - cost), 6),
                        round(platform_loads[index] + cost - partner_cost, 6),
                        platform,
                        index,
                    )
                    if best is None or key < best[0]:
                        best = (key, platform, index, partner)
        if best is None:
            print(
                f"no protected leg can take {name}: every file of a comparable "
                "measured cost is itself outside every protected leg. The "
                "partition cannot be repaired without leaving a hole somewhere "
                "else.",
                file=sys.stderr,
            )
            raise SystemExit(1)
        _key, platform, index, partner = best
        tail = where[platform]
        partitions[platform][tail].remove(name)
        partitions[platform][index].remove(partner)
        partitions[platform][index].append(name)
        partitions[platform][tail].append(partner)
        swaps.append((name, platform, index, partner))
    return swaps


def _check(partitions: dict[str, list[list[str]]], protected: dict[str, set[int]]) -> int:
    """Report the files outside every protected leg, and say so in the exit code."""
    outside = files_outside_every_protected_leg(partitions, protected)
    for platform in PLATFORMS:
        shards = sorted(protected.get(platform, set()))
        print(
            f"{platform}: the reading names "
            f"{', '.join(str(index) for index in shards)} as protected legs"
        )
    files = len(_locations(partitions))
    if not files:
        print(
            "the partition is empty, so the question cannot be answered: a check "
            "that finds no files finds nothing outside a protected leg.",
            file=sys.stderr,
        )
        return 1
    if outside:
        print(
            f"\n{len(outside)} test file(s) are in no leg branch protection "
            "waits for, so no required check runs them:\n  " + "\n  ".join(outside),
            file=sys.stderr,
        )
        return 1
    print(f"\nevery one of the {files} test files is in a leg branch protection waits for")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shards", type=int, default=None, help="how many shards")
    parser.add_argument(
        "--platform",
        choices=PLATFORMS,
        default=None,
        help="rebuild one platform's partition and leave the other alone",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "check the partition on disk and write nothing: report the test "
            "files that are in no leg branch protection waits for"
        ),
    )
    args = parser.parse_args()

    document = load()
    all_costs = document.get("costs", {})
    files = test_files()
    protected = protected_shards()

    partitions = document.get("shards", {})
    if not isinstance(partitions, dict):
        partitions = {}

    if args.check:
        if protected is None:
            print(
                f"{READING_FILE.relative_to(REPO_ROOT)} is not in this tree, so "
                "the legs branch protection waits for cannot be read, and the "
                "question this mode asks cannot be answered.",
                file=sys.stderr,
            )
            return 1
        return _check(partitions, protected)

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
            "a CI log (the pytest step runs with --durations=0), and add them to the "
            '"costs" in ' + str(SHARD_FILE.relative_to(REPO_ROOT)) + ".",
            file=sys.stderr,
        )
        return 1

    shards = args.shards or shard_count(document) or 4
    for platform in PLATFORMS:
        if args.platform is not None and args.platform != platform:
            continue
        costs = all_costs.get(platform, {})
        # The shards name paths relative to the repository root, not bare file
        # names, because the workflow hands them to pytest as arguments and a
        # bare name is not a path pytest can find.
        groups = [[f"tests/{name}" for name in group] for group in balance(files, costs, shards)]
        partitions[platform] = groups

    if protected is None:
        print(
            "no reading of branch protection in this tree, so the partition is "
            "balanced only: no leg is known to be one a merge waits for."
        )
        swaps: list[tuple[str, str, int, str]] = []
    else:
        swaps = repair_protected_legs(partitions, all_costs, protected)
    for name, platform, index, partner in swaps:
        print(
            f"{platform}: {name} swapped into shard {index}, "
            f"{partner} taking its place in the unprotected leg"
        )

    for platform in PLATFORMS:
        costs = all_costs.get(platform, {})
        loads = _loads(partitions[platform], costs)
        print(f"{platform}: {len(partitions[platform])} shards")
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
