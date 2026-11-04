"""Assemble LC-P2-18's two-side task package outside the repository.

The package is the runner input both sides of the competitor comparison
consume — the same bytes handed to our side and to the competitor's
(see ``tests/evaluation/competitor_package.py`` for what is inside). The
output directory is always this script's ``--out`` argument; there is no
default path, and a directory inside the repository is refused.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "tests"))
sys.path.insert(0, str(REPOSITORY / "tests" / "evaluation"))

from evaluation.competitor_package import (  # noqa: E402
    PackageBuildError,
    build_package,
    package_manifest_sha256,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="the directory to build the package into (must be outside the repository)",
    )
    arguments = parser.parse_args()

    try:
        manifest = build_package(arguments.out)
    except PackageBuildError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2

    counts = {entry["face"]: entry["file_count"] for entry in manifest["tasks"]}
    print(f"package built at {Path(arguments.out).resolve()}")
    print(f"manifest sha256: {package_manifest_sha256(Path(arguments.out))}")
    for face, count in counts.items():
        print(f"  {face}: {count} files")
    print(json.dumps({entry["face"]: entry["file_count"] for entry in manifest["tasks"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
