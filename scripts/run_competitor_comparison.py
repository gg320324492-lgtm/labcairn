"""LC-P2-18's comparison driver, from the command line.

**What it runs.** ``--mode dry-run`` (the default) builds our side from
the frozen Phase 1 baseline and the competitor side from the paper-qa
adapter's deterministic stub, asks the six conditions, and writes the
report and the JSON record. Neither side calls a provider.

``--mode real`` is **refused** unless a budget ceiling, our side's
outbound-consent record and the owner's approval for the competitor run
are all supplied — and even then it is refused, because our side has no
model-declaring frozen run. The refusals are printed one per line and the
exit status is 2. No provider is constructed by this script, so there is
no path around the outbound-consent bridge.

The output directory is required for a dry run: the report and the record
are artifacts of the run, and the repository's rule is that runtime
artifacts do not live inside the checkout. The report is also printed to
stdout so a reader can see it without opening a file.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "tests"))

from evaluation.competitor_run import (  # noqa: E402
    DRY_RUN,
    MODES,
    FrozenBaselineMovedError,
    RealRunRefusedError,
    render_report,
    run_comparison,
    write_report,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run LC-P2-18's comparison driver. The dry run spends nothing; "
            "the real mode refuses without the budget, the outbound-consent "
            "record and the owner's approval, and refuses with them until a "
            "model-declaring frozen run exists on our side."
        )
    )
    parser.add_argument("--mode", choices=MODES, default=DRY_RUN)
    parser.add_argument(
        "--budget",
        default="",
        help="the real mode's declared budget ceiling; empty refuses",
    )
    parser.add_argument(
        "--our-consent",
        type=Path,
        default=None,
        help="the real mode's outbound-consent record for our side",
    )
    parser.add_argument(
        "--competitor-approval",
        type=Path,
        default=None,
        help="the owner's approval for the competitor run",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="override the frozen baseline document",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="directory for comparison-report.md and comparison-record.json",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        run = run_comparison(
            args.mode,
            REPOSITORY,
            budget=args.budget,
            our_consent=args.our_consent,
            competitor_approval=args.competitor_approval,
            baseline_path=args.baseline,
        )
    except RealRunRefusedError as refused:
        print("refused: a real comparison does not start", file=sys.stderr)
        for reason in refused.reasons:
            print(f"- {reason}", file=sys.stderr)
        return 2
    except FrozenBaselineMovedError as moved:
        print(f"refused: {moved.message}", file=sys.stderr)
        return 2
    report_path, record_path = write_report(run, args.output)
    print(render_report(run))
    print(f"report: {report_path}", file=sys.stderr)
    print(f"record: {record_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
