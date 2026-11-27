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
``--json`` prints the same data for the test to compare against. ``--totals``
prints the per-file Han totals -- the companion measurement the short-name
witness pins, because a name shorter than the file's longest run does not move
the longest run at all.

**What the ceilings cannot say: what a run is.** Both measurements above are
about *how much* Chinese a file carries. They read the same whether the run is
the project's own ADR prose, a synthetic fixture, or a sentence quoted from the
manuscript -- and a short quotation inside a file that already carries a longer
run is invisible to both. ``--classify`` adds the missing dimension: every Han
run is recorded as ``(digest, length)`` in run order, and a registry
(``tests/cjk_run_classes.json``) gives each file one class -- with per-run
exceptions -- from :data:`RUN_CLASSES`. A run in a class outside
:data:`ALLOWED_RUN_CLASSES` is a run that does not belong, and
``tests/test_chinese_run_classes.py`` holds the registry against the tree.

The digest is the identity, not the text: a registry that carried the runs it
watches would spend the budget it exists to protect. A new run gets classified
by re-running ``--classify --json`` and recording it -- an act visible in the
diff, under its file's class, or ``unclassified`` for a new file, which the
witness refuses until a person says what the run is.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Final

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

#: What a Han run can be. The first five are allowed in the tree; the last
#: three are the classes a run must not be in. The class is a judgment about
#: the run's source, recorded per file in ``tests/cjk_run_classes.json`` with a
#: reason, and per run where one file carries more than one kind.
RUN_CLASSES: Final[dict[str, str]] = {
    "project-voice": "the project's own documents, written in Chinese by design",
    "design-quotation": "the project's own execution design, quoted verbatim",
    "product-vocabulary": "Chinese strings the product or its tests must recognise",
    "measurement": "Han code points in the machinery that measures Chinese",
    "machine-output": "a machine's own string, quoted as evidence",
    "corpus-quotation": "words of the manuscript corpus, quoted (not allowed)",
    "corpus-label": "a label carrying the manuscript's title-of-record (not allowed)",
    "person-name": "a label carrying a person's name (not allowed)",
}

#: The classes the tree is allowed to carry. Kept here for ``--classify``'s
#: report; the witness in ``tests/test_chinese_run_classes.py`` holds its own
#: copy, so one file's mutation cannot relax the rule and also hide it.
ALLOWED_RUN_CLASSES: Final[frozenset[str]] = frozenset(
    {
        "project-voice",
        "design-quotation",
        "product-vocabulary",
        "measurement",
        "machine-output",
    }
)

#: The class a run carries before a person has said what it is.
UNCLASSIFIED: Final[str] = "unclassified"

#: Where the classification registry lives, relative to the repository root.
DEFAULT_REGISTRY: Final[str] = "tests/cjk_run_classes.json"


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


def total_han(text: str) -> int:
    """Every Han character the file carries, not only the longest run.

    The longest run is a budget on *new long Chinese*: a quoted paragraph, a
    distilled rule statement. It cannot see a short addition -- a three- or
    four-character name appended to a file that already carries a longer run
    leaves ``longest_run`` exactly where it was, so the pin stays green while
    the name sits in the tree. This measures the other thing: the file's whole
    Han load, so that any addition, however short, moves a number the pin
    holds.
    """
    return sum(len(m.group(0)) for m in HAN_RUN.finditer(text))


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


def measure_totals(root: Path) -> dict[str, int]:
    """path -> every Han character the file carries, for files that carry any.

    The companion to :func:`measure`, and the measurement the short-name
    witness pins: a name of any length moves this number even when it does not
    move the longest run. Same skip list, same undecodable-file value.
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
        total = total_han(text)
        if total:
            out[rel] = total
    return out


def run_digest(run: str) -> str:
    """One Han run's identity, in a form that does not carry the run.

    A registry that stored the text it classifies would spend the very budget
    it exists to protect, and would become the place the corpus's words are
    copied to. Sixteen hex characters distinguish the runs in this tree; the
    length and the file disambiguate a collision.
    """
    return hashlib.sha256(run.encode("utf-8")).hexdigest()[:16]


def run_records(text: str) -> list[tuple[str, int]]:
    """Every Han run in the text, in file order, as ``(digest, length)``."""
    return [(run_digest(m.group(0)), len(m.group(0))) for m in HAN_RUN.finditer(text)]


def measure_runs(root: Path) -> dict[str, list[tuple[str, int]]]:
    """path -> every Han run's ``(digest, length)``, for files that carry any.

    This is the measurement the classification witness pins. It is the third
    companion to :func:`measure` and :func:`measure_totals`, and it holds the
    one thing neither of them can: a run replaced by a **different run of the
    same length** leaves the longest run and the total exactly where they were,
    and changes this number.
    """
    out: dict[str, list[tuple[str, int]]] = {}
    for rel in tracked_files(root):
        path = root / rel
        if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        records = run_records(text)
        if records:
            out[rel] = records
    return out


def load_registry(path: Path) -> dict[str, object]:
    """Read the classification registry; an absent one classifies nothing."""
    if not path.is_file():
        return {"classes": dict(RUN_CLASSES), "files": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("files"), dict):
        raise ValueError(f"not a classification registry: {path}")
    return data


def classify_runs(
    measured: dict[str, list[tuple[str, int]]], registry: dict[str, object]
) -> dict[str, dict[str, object]]:
    """Give every measured run the class the registry records for it.

    The registry's shape is one entry per file, and one **class per run**::

        {"README.md": {"reason": <one line>,
                       "runs": [[digest, length, class], ...]}}

    A run whose ``(digest, length)`` the registry does not hold is
    ``unclassified`` -- which includes every run of a file the registry does
    not know at all. That is the registry saying "nobody has said what this
    is yet"; re-running ``--classify --json`` records the run, and the person
    re-pinning either deletes it or writes the class the run is.
    """
    files = registry.get("files")
    known: dict[str, object] = files if isinstance(files, dict) else {}
    out: dict[str, dict[str, object]] = {}
    for rel, records in measured.items():
        entry = known.get(rel)
        held: dict[tuple[object, object], str] = {}
        reason = ""
        if isinstance(entry, dict):
            raw_reason = entry.get("reason")
            reason = raw_reason if isinstance(raw_reason, str) else ""
            rows = entry.get("runs")
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, list) and len(row) >= 3:
                        held[(row[0], row[1])] = str(row[2])
        out[rel] = {
            "reason": reason,
            "runs": [
                [digest, length, held.get((digest, length), UNCLASSIFIED)]
                for digest, length in records
            ],
        }
    return out


def effective_classes(classified: dict[str, dict[str, object]]) -> set[str]:
    """Every class the measured runs carry."""
    out: set[str] = set()
    for entry in classified.values():
        rows = entry.get("runs")
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, list) and len(row) >= 3:
                    out.add(str(row[2]))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a Python literal")
    parser.add_argument(
        "--totals",
        action="store_true",
        help="emit the per-file Han totals (the short-name measurement) as JSON",
    )
    parser.add_argument(
        "--classify",
        action="store_true",
        help="report every Han run's class from the registry, and refuse a run "
        "in a class the tree is not allowed to carry",
    )
    parser.add_argument(
        "--registry",
        default=None,
        help=f"classification registry to read (defaults to {DEFAULT_REGISTRY} under the root)",
    )
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
    if args.classify:
        registry_path = (
            Path(args.registry).resolve() if args.registry is not None else root / DEFAULT_REGISTRY
        )
        classified = classify_runs(measure_runs(root), load_registry(registry_path))
        if args.json:
            print(
                json.dumps(
                    {"classes": dict(RUN_CLASSES), "files": classified},
                    ensure_ascii=False,
                    indent=1,
                    sort_keys=True,
                )
            )
            return 0
        counts: dict[str, int] = {}
        for rel in sorted(classified):
            entry = classified[rel]
            rows = entry.get("runs")
            runs = rows if isinstance(rows, list) else []
            classes = sorted({str(row[2]) for row in runs if isinstance(row, list)})
            reason = entry.get("reason")
            print(f"{rel}\t{len(runs)} runs\t{','.join(classes)}\t{reason or ''}")
            for cls in classes:
                counts[cls] = counts.get(cls, 0) + 1
        forbidden = sorted(c for c in counts if c not in ALLOWED_RUN_CLASSES)
        print(
            f"# files: {len(classified)}; classes: "
            + ", ".join(f"{c}={n}" for c, n in sorted(counts.items())),
            file=sys.stderr,
        )
        if forbidden:
            print(
                f"# refused: classes the tree is not allowed to carry: {', '.join(forbidden)}",
                file=sys.stderr,
            )
            return 1
        return 0
    if args.totals:
        print(json.dumps(measure_totals(root), ensure_ascii=False, sort_keys=True))
        return 0
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
