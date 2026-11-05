#!/usr/bin/env python3
"""Measure the longest Chinese run each tracked file carries.

**Why this exists.** The repository is public and the pilot corpus is the owner's
unpublished work, so the project states a rule in prose: *the corpus's words are
not in the tree*. Prose is not a gate. The gate is
``tests/test_no_reference_leakage.py::test_the_tree_carries_no_more_chinese_than_was_measured``,
which pins what this script measures, and reddens when the tree and the pinned
table disagree in **either** direction -- growth because someone wrote a sentence
in, shrinkage because a value was carried forward instead of re-measured.

**What it is not.** The Chinese in this repository is mostly the project's own
voice: ADRs state their rules in the owner's language, fixtures hold synthetic
sentences, and the README is bilingual by design. A ceiling is not a ban. What a
ceiling does is make a **new** long Chinese run -- the shape a quoted comment, a
distilled rule statement or a manuscript paragraph has -- an act someone must
register deliberately, in the commit that adds it.

Run: ``python scripts/cjk_ceilings.py`` prints the registry as a Python literal.
``--json`` prints the same data for the test to compare against.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

#: A maximal run of Han characters. Punctuation is deliberately outside the run:
#: a sentence quoted with 「」 still measures by the words it carries.
HAN_RUN: re.Pattern[str] = re.compile(r"[㐀-䶿一-鿿豈-﫿]+")

#: Files that are not read: they are not text, or their bytes are the point.
SKIP_SUFFIXES = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".woff",
        ".woff2",
        ".ttf",
        ".pdf",
        ".docx",
        ".xlsx",
        ".pptx",
        ".zip",
        ".lock",
    }
)


def tracked_files(root: Path) -> list[str]:
    """The real index, via ``git ls-files -z``.

    A listing over the working tree would watch files that are not committed, and
    miss the thing the promise is about.
    """
    proc = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=True
    )
    return sorted(p for p in proc.stdout.decode("utf-8").split("\0") if p)


def longest_run(text: str) -> int:
    return max((len(m.group(0)) for m in HAN_RUN.finditer(text)), default=0)


def measure(root: Path) -> dict[str, int]:
    """path -> longest Han run, for every tracked file that carries one at all.

    A file whose bytes cannot be decoded is reported under its own name with the
    value ``-1``, because an undecodable file is not the same thing as a clean one
    and the test has to say which it is looking at.
    """
    out: dict[str, int] = {}
    for rel in tracked_files(root):
        path = root / rel
        if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            out[rel] = -1
            continue
        run = longest_run(text)
        if run:
            out[rel] = run
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a Python literal")
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parent.parent),
        help="repository to measure (defaults to the one this script lives in)",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not (root / "pyproject.toml").is_file():
        print(f"not a repository root: {root}", file=sys.stderr)
        return 2
    data = measure(root)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, sort_keys=True))
        return 0
    total = sum(data.values())
    print("# measured by scripts/cjk_ceilings.py -- longest Han run per tracked file")
    print(f"# files carrying Chinese at all: {len(data)}; total Han-run characters: {total}")
    print("CJK_RUN_CEILINGS: dict[str, int] = {")
    for path, run in sorted(data.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"    {path!r}: {run},")
    print("}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
