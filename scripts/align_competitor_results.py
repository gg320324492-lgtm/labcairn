"""Align LC-P2-18's two sides' raw outputs over one package, or refuse.

Reads the package, our side's output directory, and the competitor's;
produces the comparison document (two bases, the six-condition verdict,
the metric pairs) or a refusal naming everything that is wrong. See
``tests/evaluation/competitor_align.py`` for the refusal rules and the
closed scoring table.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "tests"))
sys.path.insert(0, str(REPOSITORY / "tests" / "evaluation"))

from evaluation.competitor_align import AlignmentRefusedError, align  # noqa: E402
from evaluation.competitor_package import PackageInvalidError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True, help="the task package directory")
    parser.add_argument("--ours", type=Path, required=True, help="our side's output directory")
    parser.add_argument(
        "--competitor", type=Path, required=True, help="the competitor's output directory"
    )
    parser.add_argument(
        "--out", type=Path, help="where to write the comparison document (default: stdout)"
    )
    arguments = parser.parse_args()

    try:
        outcome = align(arguments.package, arguments.ours, arguments.competitor)
    except (AlignmentRefusedError, PackageInvalidError) as error:
        reasons = getattr(error, "reasons", (str(error),))
        print("alignment refused; no score was produced:", file=sys.stderr)
        for reason in reasons:
            print(f"  - {reason}", file=sys.stderr)
        return 2

    document = outcome.as_document()
    rendered = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if arguments.out is None:
        print(rendered, end="")
    else:
        arguments.out.parent.mkdir(parents=True, exist_ok=True)
        arguments.out.write_text(rendered, encoding="utf-8")
        print(f"comparison document written to {arguments.out}")
        print(f"comparable: {document['comparable']}")
        for condition in document["conditions"]:
            print(f"  [{condition['met']}] {condition['name']}: {condition['detail']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
