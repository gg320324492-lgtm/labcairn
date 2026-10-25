"""Re-measure the shard costs from a CI run, and rewrite the shard file.

**What this is for.** The shard file holds the measured per-file costs the
partition is balanced against, and the commit those costs were measured at.
When the tree changes, the costs stop describing it — and the shard
coverage's own witness says so, and fails. **This is the fix, and it is one
command.**

**Why it is a command and not a paragraph.** The costs come out of a CI
run's log: pytest runs with ``--durations=0`` and the per-file seconds are
read from the durations section. Reading them out by hand is a dozen steps
and every one of them is a chance to transcribe a number wrongly, which is
the project's own recurring lesson. **A measurement that is transcribed is a
measurement that can be wrong.**

**Usage:**

    python .github/remeasure_shards.py <run-id> [--repo REPO]

or, when the logs are already on disk:

    python .github/remeasure_shards.py --from <directory>

``<run-id>`` is a GitHub Actions run id, and the logs are fetched with
``gh api``. ``--from`` takes a directory of job logs (the ones
``gh api .../actions/jobs/<id>/logs`` writes).

**What it does.** It reads the per-file seconds for each platform, works out
the fast files' share of what the shards reported, writes the costs and the
commit they were measured at into ``.github/ci-shards.json``, and then
rebuilds the partition from them with ``make_ci_shards.py``.

**What it does not do.** It does not measure anything itself: every number
in the table comes from a runner, because **a development machine gives a
different answer** — not only a different total, a different *order*, which
is why the partition is one per platform.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARD_FILE = REPO_ROOT / ".github" / "ci-shards.json"
TESTS = REPO_ROOT / "tests"

#: The platforms the workflow runs on.
PLATFORMS = ("ubuntu-latest", "windows-latest")

#: A duration line: "12.34s call     tests/test_x.py::test_y".
_DURATION = re.compile(r"([0-9.]+)s\s+(call|setup|teardown)\s+(tests/\S+)")
#: A shard's own summary: "..., 1116 warnings in 134.12s (0:02:14)".
_SUMMARY = re.compile(r"warnings in ([\d.]+)s")


def _test_files() -> list[str]:
    return sorted(path.name for path in TESTS.glob("test_*.py"))


def _fetch_logs(run_id: str, repo: str) -> dict[str, str]:
    """The run's job logs, keyed by the job's name."""
    logs: dict[str, str] = {}
    jobs = subprocess.run(
        [
            "gh",
            "api",
            f"repos/{repo}/actions/runs/{run_id}/jobs",
            "--jq",
            '.jobs[]|select(.name|startswith("python-quality"))|.id',
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    for job_id in jobs:
        name = subprocess.run(
            ["gh", "api", f"repos/{repo}/actions/jobs/{job_id}", "--jq", ".name"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        body = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{repo}/actions/jobs/{job_id}/logs",
                "--allow-escape-sequences",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        logs[name] = body
    return logs


def _run_head_sha(run_id: str, repo: str) -> str | None:
    """The commit the run tested, which is what the costs belong to.

    **The run id is not a commit, and the difference matters.** The shard
    file's ``measured_at`` is read by the coverage witness as a git
    revision: it asks what changed since the costs were measured. A run id
    is not a revision, so ``git diff`` refuses it, and the witness then
    cannot check anything -- which, before the witness was taught to fail
    when it cannot check, meant the check passed without having looked.
    """
    proc = subprocess.run(
        ["gh", "api", f"repos/{repo}/actions/runs/{run_id}", "--jq", ".head_sha"],
        capture_output=True,
        text=True,
        check=False,
    )
    sha = proc.stdout.strip()
    if proc.returncode != 0 or not sha:
        return None
    return sha


def _logs_from(directory: Path) -> dict[str, str]:
    logs: dict[str, str] = {}
    for path in sorted(directory.glob("*.log")):
        logs[path.stem] = path.read_text(encoding="utf-8", errors="replace")
    return logs


def _platform_of(name: str) -> str | None:
    for platform in PLATFORMS:
        if platform in name:
            return platform
    return None


def measure(logs: dict[str, str]) -> dict[str, dict[str, float]]:
    """The per-file seconds, per platform, and the fast files' share."""
    files = _test_files()
    costs: dict[str, dict[str, float]] = {}
    for platform in PLATFORMS:
        per_file: dict[str, float] = defaultdict(float)
        reported = 0.0
        for name, body in logs.items():
            if _platform_of(name) != platform:
                continue
            summary = _SUMMARY.search(body)
            if summary:
                reported += float(summary.group(1))
            for match in _DURATION.finditer(body):
                per_file[match.group(3).split("::")[0].split("/")[-1]] += float(match.group(1))
        measured = sum(per_file.values())
        remainder = max(0.0, reported - measured)
        missing = [name for name in files if name not in per_file]
        counts: dict[str, int] = {}
        for name in missing:
            source = (TESTS / name).read_text(encoding="utf-8", errors="replace")
            counts[name] = max(1, len(re.findall(r"^\s*def test_", source, re.M)))
        total = sum(counts.values()) or 1
        for name in missing:
            per_file[name] = round(remainder * counts[name] / total, 3)
        costs[platform] = {name: round(per_file.get(name, 0.0), 2) for name in files}
        print(
            f"{platform}: the shards reported {reported:.0f}s, the visible files "
            f"measured {measured:.0f}s, and the {len(missing)} fast files share "
            f"{remainder:.0f}s"
        )
    return costs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id", nargs="?", help="the GitHub Actions run id")
    parser.add_argument("--repo", default="gg320324492-lgtm/labcairn")
    parser.add_argument("--from", dest="directory", help="a directory of job logs")
    parser.add_argument("--measured-at", default=None, help="the commit the costs were measured at")
    args = parser.parse_args()

    if args.directory:
        logs = _logs_from(Path(args.directory))
    elif args.run_id:
        logs = _fetch_logs(args.run_id, args.repo)
    else:
        parser.error("a run id or --from is needed")
    if not logs:
        print("no job logs were found", file=sys.stderr)
        return 1

    measured_at = args.measured_at
    if not measured_at and args.run_id:
        measured_at = _run_head_sha(args.run_id, args.repo)
    if not measured_at:
        parser.error(
            "the commit the costs were measured at is needed: pass "
            "--measured-at, or give a run id whose head commit the API can "
            "name. A directory of logs does not say which commit they came "
            "from, and a run id is not a commit."
        )

    costs = measure(logs)

    # **A run that measured nothing must not be written over a table that
    # measured something.** The failure this guards against is a run that was
    # still in progress, or whose logs are empty: the durations are not there,
    # every file reads as zero, and the table that comes out of that is a
    # partition balanced against nothing. It was done once, and the table was
    # gone until it was restored from git.
    for platform, measured in costs.items():
        if sum(measured.values()) <= 0:
            print(
                f"the {platform} logs carry no durations -- the run is still "
                "going, or its logs are empty. Nothing was written.",
                file=sys.stderr,
            )
            return 1

    document: dict[str, Any] = json.loads(SHARD_FILE.read_text(encoding="utf-8"))
    document["measured_at"] = measured_at
    document["costs"] = costs
    SHARD_FILE.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"the costs are written, measured at {measured_at}")

    subprocess.run([sys.executable, str(REPO_ROOT / ".github" / "make_ci_shards.py")], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
