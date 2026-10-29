"""The LC-P2-07 fidelity measurement: how much of a revision history survives.

**What this measures.** For every fixture in the synthetic corpus, three
arms read the same file, and the result is compared against the gold:

| Arm | What it is | What it can know |
|---|---|---|
| **OOXML-native** | the project's own reader, once it exists | the revision history, if read |
| **Text extraction** | `pandoc --track-changes=all`, or `python-docx` | the text, and which text |
| **Library** | `docx2python` | comments, if they pair |

The measurement reports **precision, recall and false negatives separately**,
and that separation is the point. A metric that counted only the comments a
parser got right would let a parser that returns *nothing* score perfectly.
A metric that counted only "did it find them all" would hide the difference
between "found them" and "found them *and* could say where".

**The three findings it is designed to be able to show**, each of which was
read out of upstream source before the measurement was written:

1. A reader of `w:t` alone **loses every deletion** — the deleted text
   lives in `w:delText`. (Docling, `msword_backend.py:2053`.)
2. A comment whose range markers do not pair can take **the whole comment
   set** with it. (docx2python, `docx_output.py:418`.)
3. A **text-extraction** view cannot distinguish an insertion from text the
   author wrote, and cannot recover who changed anything.

**How to read the output.** A number is a number *about this corpus, on this
machine, with these arms*. The corpus is synthetic and the arms are
particular versions. Nothing here is a claim about Word documents in
general, and the report says so.

**Usage.**

```bash
python -m tests.evaluation_docx_fidelity --json report.json
```

The module is runnable without pytest so that a reviewer can reproduce a
number by hand.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from docx_corpus import FIXTURES, KNOWN_GAPS
from docx_fixtures import Fixture, gold_for, revision_range, write_fixture

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


# --------------------------------------------------------------------------- #
# the arms
# --------------------------------------------------------------------------- #


@dataclass
class ArmResult:
    """What one arm found in one fixture."""

    arm: str
    fixture: str
    #: The revisions the arm reported: a list of
    #: ``(kind, text, author, date)`` tuples, with ``"UNKNOWN"`` for a
    #: value the arm could not determine.
    revisions: list[tuple[str, str, str, str]] = field(default_factory=list)
    #: The comments the arm reported: ``(id, text, anchor_text, author)``
    #: quadruples. The id may be empty — an arm that cannot reach the
    #: document's comment ids says so rather than inventing one.
    comments: list[tuple[str, str, str, str]] = field(default_factory=list)
    #: Why the arm could not read the file, if it could not.
    error: str | None = None
    #: The arm's accepted-text and rejected-text views, where it has them.
    accepted_text: str | None = None
    rejected_text: str | None = None
    #: Whether the arm can attribute a change to a person. An arm that
    #: renders text rather than events cannot, and saying "UNKNOWN" is the
    #: honest answer.
    attributes: bool = False

    @property
    def usable(self) -> bool:
        return self.error is None


def _flatten(value: Any) -> str:
    """Turn a nested body structure into plain text.

    ``docx2python`` returns its body as a tree of nested lists and strings.
    The tree is not the text, and a measurement that compared it to a
    string would report a mismatch that says nothing about the reader.
    This walks the tree and joins the strings it finds, which is the
    reading the arm is actually about.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return " ".join(part for part in (_flatten(item) for item in value) if part)
    return ""


def _pandoc(path: Path, mode: str) -> str | None:
    """Run pandoc with one track-changes mode.

    Returns the converted text, or ``None`` when pandoc is not installed or
    the conversion fails. A missing tool is reported as *missing*, not as a
    zero — an arm that did not run has not failed the measurement.
    """
    if shutil.which("pandoc") is None:
        return None
    try:
        completed = subprocess.run(
            ["pandoc", "--track-changes=" + mode, "-t", "plain", str(path)],
            capture_output=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.decode("utf-8", errors="replace")


def arm_pandoc(path: Path) -> ArmResult:
    """The text-extraction arm.

    pandoc's three ``--track-changes`` modes give the **views** — the text
    a document reads as if the revisions were accepted, or as if they were
    rejected. That is a real capability and it is measured as one: the
    accepted and rejected views are compared against the expected ones.

    What pandoc cannot do is **attribute** a change. Its plain writer
    renders an insertion and a deletion as text, with no author and no
    date, and it reports nothing as a *revision*. So this arm reports no
    structured revision events, and saying otherwise would be the exact
    error the measurement exists to catch.

    **A measured behaviour worth recording.** On this corpus, pandoc
    **silently drops a tracked insertion that carries no ``w:author``**.
    The XML of the "insertion without an author" fixture and the "insertion
    with an author" fixture differ in that attribute and in nothing else,
    and pandoc's accepted view contains the inserted text in one case and
    not in the other. A missing author is not a reason to discard a change
    — it is a reason to report the author as unknown — and an arm that
    discards it loses the edit silently. This is the design's §7 case
    "a revision whose metadata is missing", and it is measured here rather
    than asserted.
    """
    result = ArmResult(arm="pandoc", fixture=path.stem)
    if shutil.which("pandoc") is None:
        result.error = "pandoc is not installed"
        return result

    accepted = _pandoc(path, "accept")
    rejected = _pandoc(path, "reject")
    if accepted is None or rejected is None:
        result.error = "pandoc failed to convert the file"
        return result

    result.accepted_text = accepted
    result.rejected_text = rejected
    result.revisions = []
    result.comments = []
    result.attributes = False
    result.error = (
        "pandoc renders revisions as text views; it reports no structured "
        "revision or comment events, and attributes nothing"
    )
    return result


def arm_python_docx(path: Path) -> ArmResult:
    """The ``python-docx`` arm.

    This is the arm that shows the ``w:t`` problem most directly:
    ``python-docx`` is the project's own declared dependency for *writing*
    DOCX, and it cannot see a deletion. ``Run.text`` reads ``w:t`` only, so
    a deleted run reads as empty.

    It has **one** view — the text as it stands, revisions invisible — so
    both its accepted and its rejected views are that one text, and both
    are wrong whenever the document carries a revision.
    """
    result = ArmResult(arm="python-docx", fixture=path.stem)
    try:
        from docx import Document
    except ImportError:
        result.error = "python-docx is not installed"
        return result

    try:
        document = Document(str(path))
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"
        return result

    paragraphs = [p.text for p in document.paragraphs]
    text = "\n".join(paragraphs)
    result.accepted_text = text
    result.rejected_text = text
    result.revisions = []
    result.comments = []
    result.attributes = False
    result.error = (
        "python-docx reads w:t only; it reports no structured revision or "
        "comment events, and shows one text for both views"
    )
    return result


def arm_docx2python(path: Path) -> ArmResult:
    """The library arm.

    ``docx2python`` is not a project dependency and is not installed by
    default; when it is absent the arm reports that it did not run, which
    is different from running and finding nothing.

    **Measured on this corpus** (2026-10-29, SHA
    ``66b1ae3e24ffa7040ed5244490ce2872ac2e86bb``):

    - a well-formed comment is extracted, with its body, author and date;
    - the anchor it reports is the **whole paragraph's** text, not the
      comment's range — the range is paragraph-granular;
    - a comment whose range markers do not pair produces a warning and an
      **empty** comment list, so **every comment in the document is lost**;
    - a comment with no range markers at all is likewise lost entirely,
      even though its body, author and date are present in
      ``word/comments.xml``.

    The last two are the design's §7 "isolated comment marker" case, and
    they are why the corpus measures comment **recall** and not just the
    comments that were extracted correctly.
    """
    result = ArmResult(arm="docx2python", fixture=path.stem)
    try:
        from docx2python import docx2python  # type: ignore[import-not-found]
    except ImportError:
        result.error = "docx2python is not installed"
        return result

    try:
        extracted = docx2python(str(path))
        comments = extracted.comments
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"
        return result

    result.comments = [
        # docx2python's comment tuple is (reference_text, author, date,
        # text) and it carries **no comment id** — the id lives in the
        # document's range markers, which this library does not surface.
        # The id is therefore reported as the empty string, and the
        # scorer matches a comment on its text and author rather than on
        # an id it cannot know.
        ("", text, reference, author)
        for (reference, author, _date, text) in comments
    ]
    result.revisions = []
    result.accepted_text = _flatten(extracted.body)
    result.rejected_text = _flatten(extracted.body)
    result.attributes = False
    return result


def arm_ooxml_native(path: Path) -> ArmResult:
    """The OOXML-native arm.

    **It does not exist yet.** LC-P2-07 is the ticket that writes it. Until
    then this arm reports that it is unimplemented, which is the honest
    answer and keeps the measurement's shape fixed for when the reader
    lands.

    The measurement is written *before* the parser on purpose: the arms and
    the scoring are the contract the parser will be held to, and a scoring
    function written after the parser exists tends to score what the parser
    does.
    """
    result = ArmResult(arm="ooxml-native", fixture=path.stem)
    result.error = "the OOXML-native reader is LC-P2-07's deliverable and does not exist yet"
    return result


ARMS = {
    "ooxml-native": arm_ooxml_native,
    "pandoc": arm_pandoc,
    "python-docx": arm_python_docx,
    "docx2python": arm_docx2python,
}


# --------------------------------------------------------------------------- #
# the scoring
# --------------------------------------------------------------------------- #


def expected_views(fixture: Fixture) -> tuple[str, str]:
    """The accepted and rejected texts a correct reader must produce.

    The **accepted** view is the baseline with every insertion added and
    every deletion removed. The **rejected** view is the baseline with every
    deletion restored and every insertion absent.

    Both are derived from the fixture's own words, so a parser's views can
    be compared without a second implementation of the same rule.

    **The concatenation is literal.** An insertion's text is joined to the
    text before it with no separator, because that is how the XML reads —
    the inserted run follows the preceding run, and the reader cannot know
    that a space belongs between them. A reader that adds a space is
    *editing* the document rather than reading it, and the measurement
    says so.
    """
    accepted: list[str] = []
    rejected: list[str] = []
    for index, baseline in enumerate(fixture.paragraphs):
        revisions = [r for r in fixture.revisions if r.paragraph == index]
        if not revisions:
            accepted.append(baseline)
            rejected.append(baseline)
            continue

        # Work on the baseline, replacing or inserting at the derived
        # ranges.
        ranges = {r.element_id: revision_range(fixture, r) for r in revisions}
        ordered = sorted(revisions, key=lambda r: ranges[r.element_id])

        acc_parts: list[str] = []
        rej_parts: list[str] = []
        emitted_up_to = 0
        for rev in ordered:
            start, end = ranges[rev.element_id]
            if start > emitted_up_to:
                acc_parts.append(baseline[emitted_up_to:start])
                rej_parts.append(baseline[emitted_up_to:start])
            if rev.kind in ("ins", "moveTo"):
                acc_parts.append(rev.text)
            else:
                # A deletion or a move source is present in the rejected
                # view and absent from the accepted one.
                rej_parts.append(rev.text)
            emitted_up_to = max(emitted_up_to, end)
        if emitted_up_to < len(baseline):
            acc_parts.append(baseline[emitted_up_to:])
            rej_parts.append(baseline[emitted_up_to:])
        accepted.append("".join(acc_parts))
        rejected.append("".join(rej_parts))

    return "\n".join(accepted), "\n".join(rejected)


@dataclass
class Score:
    """How one arm did on one fixture."""

    arm: str
    fixture: str
    #: Revisions in the gold.
    gold_revisions: int = 0
    #: Revisions the arm reported, correctly.
    revisions_found: int = 0
    #: Revisions the arm reported that the gold does not have.
    revisions_spurious: int = 0
    #: Gold revisions the arm missed entirely.
    revisions_missed: int = 0
    #: Comments in the gold.
    gold_comments: int = 0
    comments_found: int = 0
    comments_spurious: int = 0
    comments_missed: int = 0
    #: How many of the gold's revisions had their **deleted text** present.
    deletions_recovered: int = 0
    gold_deletions: int = 0
    #: Whether the accepted view is exactly right, whether the rejected
    #: view is exactly right, and whether the arm can attribute a change
    #: to a person.
    accepted_view_correct: bool = False
    rejected_view_correct: bool = False
    attributes_changes: bool = False
    #: The arm could not read the file.
    error: str | None = None

    @property
    def revision_precision(self) -> float | None:
        reported = self.revisions_found + self.revisions_spurious
        return None if reported == 0 else self.revisions_found / reported

    @property
    def revision_recall(self) -> float | None:
        if self.gold_revisions == 0:
            return None
        return self.revisions_found / self.gold_revisions

    @property
    def comment_precision(self) -> float | None:
        reported = self.comments_found + self.comments_spurious
        return None if reported == 0 else self.comments_found / reported

    @property
    def comment_recall(self) -> float | None:
        if self.gold_comments == 0:
            return None
        return self.comments_found / self.gold_comments

    def as_dict(self) -> dict[str, Any]:
        return {
            "arm": self.arm,
            "fixture": self.fixture,
            "gold_revisions": self.gold_revisions,
            "revisions_found": self.revisions_found,
            "revisions_spurious": self.revisions_spurious,
            "revisions_missed": self.revisions_missed,
            "revision_precision": self.revision_precision,
            "revision_recall": self.revision_recall,
            "gold_comments": self.gold_comments,
            "comments_found": self.comments_found,
            "comments_spurious": self.comments_spurious,
            "comments_missed": self.comments_missed,
            "comment_precision": self.comment_precision,
            "comment_recall": self.comment_recall,
            "gold_deletions": self.gold_deletions,
            "deletions_recovered": self.deletions_recovered,
            "accepted_view_correct": self.accepted_view_correct,
            "rejected_view_correct": self.rejected_view_correct,
            "attributes_changes": self.attributes_changes,
            "error": self.error,
        }


def _normalise(text: str) -> str:
    return " ".join(text.split())


def score_arm(
    arm: ArmResult,
    gold: dict[str, Any],
    fixture: Fixture | None = None,
) -> Score:
    """Compare one arm's result against one fixture's gold.

    The comparison is on **content**, not on identity: a revision matches
    when its kind, text, author and date all agree. A revision whose author
    the arm could not determine does **not** match a gold revision that has
    an author, because reporting an author you do not know as though you did
    is the failure this measurement exists to catch — and the gold states
    ``"UNKNOWN"`` precisely so that "I do not know" and "the author is
    Lin" cannot be confused.
    """
    score = Score(
        arm=arm.arm,
        fixture=arm.fixture,
        gold_revisions=len(gold["revisions"]),
        gold_comments=len(gold["comments"]),
        gold_deletions=sum(1 for r in gold["revisions"] if r["kind"] == "del"),
        attributes_changes=arm.attributes,
        error=arm.error,
    )

    if fixture is not None:
        expected_accepted, expected_rejected = expected_views(fixture)
        score.accepted_view_correct = arm.accepted_text is not None and _normalise(
            arm.accepted_text
        ) == _normalise(expected_accepted)
        score.rejected_view_correct = arm.rejected_text is not None and _normalise(
            arm.rejected_text
        ) == _normalise(expected_rejected)

    if not arm.usable:
        score.revisions_missed = score.gold_revisions
        score.comments_missed = score.gold_comments
        return score

    gold_revisions = [
        (r["kind"], _normalise(r["text"]), r["author"], r["date"]) for r in gold["revisions"]
    ]
    remaining = list(gold_revisions)
    for revision in arm.revisions:
        revision_candidate = (
            revision[0],
            _normalise(revision[1]),
            revision[2],
            revision[3],
        )
        if revision_candidate in remaining:
            remaining.remove(revision_candidate)
            score.revisions_found += 1
        else:
            score.revisions_spurious += 1
    score.revisions_missed = len(remaining)

    # A comment matches on its **id** when the arm reports one, and on its
    # **text and author** when it does not. The second case is not a
    # loosening: an arm that cannot reach the document's comment ids says
    # so, and a comment's body and author are still a specific claim that
    # can be right or wrong. What is *not* matched is the anchor text,
    # because its granularity is a property of the library rather than of
    # the document — that is measured separately.
    gold_comments = [(c["id"], _normalise(c["text"]), c["author"]) for c in gold["comments"]]
    remaining_comments: list[tuple[str, str, str]] = list(gold_comments)
    for comment in arm.comments:
        comment_id, text, _anchor, author = comment
        comment_candidate: tuple[str, str, str]
        if comment_id:
            comment_candidate = (comment_id, _normalise(text), author)
        else:
            comment_candidate = next(
                (
                    (gid, gtext, gauthor)
                    for gid, gtext, gauthor in remaining_comments
                    if gtext == _normalise(text) and gauthor == author
                ),
                ("", _normalise(text), author),
            )
        if comment_candidate in remaining_comments:
            remaining_comments.remove(comment_candidate)
            score.comments_found += 1
        else:
            score.comments_spurious += 1
    score.comments_missed = len(remaining_comments)

    # A deletion is "recovered" when the arm reported an event whose text
    # is the deleted text. The arms that render text rather than events
    # recover nothing here, which is the finding.
    deleted_texts = {
        _normalise(r["text"]) for r in gold["revisions"] if r["kind"] == "del" and r["text"]
    }
    reported_texts = {_normalise(r[1]) for r in arm.revisions}
    score.deletions_recovered = len(deleted_texts & reported_texts)

    return score


def measure(directory: Path, arms: list[str] | None = None) -> dict[str, Any]:
    """Run every arm over every fixture and score the results."""
    chosen = arms or list(ARMS)
    for fixture in FIXTURES:
        write_fixture(fixture, directory)

    scores: list[Score] = []
    for fixture in FIXTURES:
        gold = gold_for(fixture)
        path = directory / f"{fixture.name}.docx"
        for arm_name in chosen:
            arm = ARMS[arm_name](path)
            scores.append(score_arm(arm, gold, fixture))

    return {
        "corpus": {
            "fixtures": len(FIXTURES),
            "total_revisions": sum(len(f.revisions) for f in FIXTURES),
            "total_comments": sum(len(f.comments) for f in FIXTURES),
            "total_deletions": sum(1 for f in FIXTURES for r in f.revisions if r.kind == "del"),
        },
        "scores": [s.as_dict() for s in scores],
        "known_gaps": list(KNOWN_GAPS),
    }


def summarise(measurement: dict[str, Any]) -> list[dict[str, Any]]:
    """Aggregate per arm.

    An arm that could not read a file is counted as missing everything,
    **not** as excluded. Excluding it would let an arm that fails on every
    fixture report an average over the fixtures it happened to read, which
    is the false-negative floor this measurement exists to keep.
    """
    by_arm: dict[str, list[dict[str, Any]]] = {}
    for score in measurement["scores"]:
        by_arm.setdefault(score["arm"], []).append(score)

    summary: list[dict[str, Any]] = []
    for arm, rows in by_arm.items():
        gold_revisions = sum(r["gold_revisions"] for r in rows)
        revisions_found = sum(r["revisions_found"] for r in rows)
        revisions_spurious = sum(r["revisions_spurious"] for r in rows)
        revisions_missed = sum(r["revisions_missed"] for r in rows)
        gold_comments = sum(r["gold_comments"] for r in rows)
        comments_found = sum(r["comments_found"] for r in rows)
        comments_spurious = sum(r["comments_spurious"] for r in rows)
        comments_missed = sum(r["comments_missed"] for r in rows)
        gold_deletions = sum(r["gold_deletions"] for r in rows)
        deletions_recovered = sum(r["deletions_recovered"] for r in rows)
        errored = sum(1 for r in rows if r["error"])
        accepted_ok = sum(1 for r in rows if r["accepted_view_correct"])
        rejected_ok = sum(1 for r in rows if r["rejected_view_correct"])
        attributes = sum(1 for r in rows if r["attributes_changes"])

        summary.append(
            {
                "arm": arm,
                "fixtures": len(rows),
                "fixtures_with_error": errored,
                "gold_revisions": gold_revisions,
                "revisions_found": revisions_found,
                "revisions_spurious": revisions_spurious,
                "revisions_missed": revisions_missed,
                "revision_precision": (
                    revisions_found / (revisions_found + revisions_spurious)
                    if (revisions_found + revisions_spurious)
                    else None
                ),
                "revision_recall": (revisions_found / gold_revisions if gold_revisions else None),
                "gold_comments": gold_comments,
                "comments_found": comments_found,
                "comments_spurious": comments_spurious,
                "comments_missed": comments_missed,
                "comment_precision": (
                    comments_found / (comments_found + comments_spurious)
                    if (comments_found + comments_spurious)
                    else None
                ),
                "comment_recall": (comments_found / gold_comments if gold_comments else None),
                "gold_deletions": gold_deletions,
                "deletions_recovered": deletions_recovered,
                "deletion_recovery_rate": (
                    deletions_recovered / gold_deletions if gold_deletions else None
                ),
                "accepted_view_correct": accepted_ok,
                "rejected_view_correct": rejected_ok,
                "attributes_changes": attributes,
            }
        )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        type=Path,
        help="write the measurement as JSON to this path",
    )
    parser.add_argument(
        "--arm",
        action="append",
        dest="arms",
        help="run only this arm (repeatable); default is every arm",
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=Path(".local") / "docx-fidelity",
        help="where to write the corpus for the run",
    )
    args = parser.parse_args(argv)

    directory = args.corpus_dir.resolve()
    measurement = measure(directory, args.arms)
    summary = summarise(measurement)
    measurement["summary"] = summary

    print(  # noqa: T201 - a measurement report, not product code
        f"corpus: {measurement['corpus']['fixtures']} fixtures, "
        f"{measurement['corpus']['total_revisions']} revisions, "
        f"{measurement['corpus']['total_comments']} comments, "
        f"{measurement['corpus']['total_deletions']} deletions"
    )
    print()  # noqa: T201 - a measurement report, not product code
    header = (
        f"{'arm':<14} {'rev found':>9} {'rev miss':>8} {'rev rec':>8} "
        f"{'cmt found':>9} {'cmt miss':>8} {'cmt rec':>8} "
        f"{'del recov':>11} {'accept ok':>10} {'reject ok':>10} {'attr':>5}"
    )
    print(header)  # noqa: T201 - a measurement report, not product code
    print("-" * len(header))  # noqa: T201 - a measurement report, not product code
    for row in summary:
        rev_recall = row["revision_recall"]
        cmt_recall = row["comment_recall"]
        print(  # noqa: T201 - a measurement report, not product code
            f"{row['arm']:<14} "
            f"{row['revisions_found']:>9} "
            f"{row['revisions_missed']:>8} "
            f"{'n/a' if rev_recall is None else f'{rev_recall:.3f}':>8} "
            f"{row['comments_found']:>9} "
            f"{row['comments_missed']:>8} "
            f"{'n/a' if cmt_recall is None else f'{cmt_recall:.3f}':>8} "
            f"{row['deletions_recovered']:>5}/{row['gold_deletions']:<5} "
            f"{row['accepted_view_correct']:>4}/{row['fixtures']:<5} "
            f"{row['rejected_view_correct']:>4}/{row['fixtures']:<5} "
            f"{'yes' if row['attributes_changes'] else 'no':>5}"
        )
    print()  # noqa: T201 - a measurement report, not product code
    print(  # noqa: T201 - a measurement report, not product code
        "rev rec / cmt rec: revision and comment recall over the whole corpus.\n"
        "del recov:       deletions whose text the arm recovered.\n"
        "accept/reject ok: fixtures where the arm's accepted (resp. rejected)\n"
        "                 text view is exactly the expected one.\n"
        "attr:            whether the arm can attribute a change to a person.\n"
        "\nA zero in a column is a fact about the arm, not a failure of the\n"
        "measurement: an arm that renders text cannot report revision events."
    )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(measurement, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"\nwrote {args.json}")  # noqa: T201 - a measurement report, not product code
    return 0


if __name__ == "__main__":
    sys.exit(main())
