"""Rebuild the CI shard file.

**What this is for.** The CI workflow runs the suite in shards, each shard in
its own job on its own runner, because one runner doing everything is the
worst possible arrangement for a suite whose cost is spread unevenly. The
shards are balanced against **measured** per-file costs, and this script does
the balancing.

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

**How to measure a new file's cost:**

    uv run pytest tests/test_the_new_file.py -vv --durations=0

and read the seconds out of the durations section. (``-vv`` is what shows the
durations of tests that finish in under five milliseconds, which is most of
a new file's tests.)

**Usage:**

    python .github/make_ci_shards.py [--shards N] [--measure]

``--measure`` re-measures every file from scratch, which takes a full suite
run; without it, the recorded costs are reused and only the balance changes.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARD_FILE = REPO_ROOT / ".github" / "ci-shards.json"
TESTS = REPO_ROOT / "tests"


def test_files() -> list[str]:
    """Every test file, by name."""
    return sorted(path.name for path in TESTS.glob("test_*.py"))


def measure(name: str) -> float:
    """The seconds one test file takes, measured on its own.

    Run as a separate pytest process, because that is how CI runs it: one
    process, one file, one collection. The startup is counted in, which is
    fair — CI pays it too.
    """
    with tempfile.TemporaryDirectory(prefix="labcairn-shard-measure-") as base:
        started = time.perf_counter()
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                f"tests/{name}",
                "-q",
                "--tb=no",
                "-p",
                "no:cacheprovider",
                "--basetemp",
                f"{base}/bt",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        return round(time.perf_counter() - started, 2)


def load() -> dict[str, Any]:
    if not SHARD_FILE.is_file():
        return {"shards": [], "costs": {}}
    return json.loads(SHARD_FILE.read_text(encoding="utf-8"))


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
        "--measure", action="store_true", help="re-measure every file from scratch"
    )
    args = parser.parse_args()

    document = load()
    costs: dict[str, float] = dict(document.get("costs", {}))
    files = test_files()

    if args.measure:
        for name in files:
            costs[name] = measure(name)
            print(f"measured {name}: {costs[name]}s", flush=True)
    else:
        missing = [name for name in files if name not in costs]
        if missing:
            print(
                "these files have never been measured, and this script will not "
                "guess a cost for them:\n  "
                + "\n  ".join(missing)
                + "\n\nMeasure them with:\n  uv run pytest tests/<file> -vv --durations=0"
                + "\n\nand add the seconds to the \"costs\" in "
                + str(SHARD_FILE.relative_to(REPO_ROOT))
                + " — or re-measure everything with:\n  python .github/make_ci_shards.py --measure",
                file=sys.stderr,
            )
            return 1

    shards = args.shards or len(document.get("shards", [])) or 4
    groups = balance(files, costs, shards)
    # The shards name paths relative to the repository root, not bare file
    # names, because the workflow passes them to pytest as arguments and a
    # bare name is not a path pytest can find.
    groups = [[f"tests/{name}" for name in group] for group in groups]
    loads = [sum(costs[n] for n in group) for group in groups]
    print(f"{len(files)} files into {shards} shards")
    for index, (group, group_load) in enumerate(zip(groups, loads, strict=True)):
        print(f"  shard {index}: {group_load:8.1f}s  ({len(group):2d} files)")
    print(f"  balance factor: {max(loads) / min(loads):.3f}")

    SHARD_FILE.write_text(
        json.dumps(
            {"shards": groups, "costs": {name: round(costs[name], 2) for name in files}},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"written {SHARD_FILE.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
