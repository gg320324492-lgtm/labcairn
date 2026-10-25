"""Rendering the report — as Markdown for a reader, as JSON for a machine.

**Two renderings of one run, and they say the same thing.** The Markdown is
what a reviewer reads; the JSON is what a comparison or a later run reads.
They are rendered from the same :class:`~tests.evaluation.model.EvaluationRun`
and neither is derived from the other, so a bug in one does not quietly
become a fact in the other.

**What the Markdown is careful about.**

* Every number that is a rate is printed as **numerator over denominator**,
  and the denominator is in its own column, so a reader never has to guess
  what the rate is over.
* A **small denominator is said out loud**, in the row, because a rate over
  four cases and a rate over four hundred are not the same claim.
* **Failure cases are listed**, with their node id and their message, under
  the class they belong to. A rate that hides which cases failed is a rate
  that cannot be acted on.
* A class that was **not run** has a row that says NOT RUN and gives the
  reason. It does not have a rate of zero, because zero says "every case
  failed" and no cases is not that.
* The comparison section prints **pairs** and no verdict, because the
  protocol forbids a superiority claim without like-for-like matched tasks,
  and the structure of the output is what stops one.
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any, Final

from .model import (
    SMALL_DENOMINATOR,
    BlockerResult,
    ClassResult,
    ComparisonOutcome,
    EvaluationRun,
    Measurement,
    MetricRow,
)

#: The words the comparison section must never contain. The protocol forbids
#: claiming superiority without like-for-like matched tasks, and a report
#: that says "better" anywhere in its comparison is a report that has
#: claimed something.
#:
#: ``tests/test_evaluation_harness.py`` watches this list against the
#: rendered section, so the list is not a comment.
RANKING_WORDS: Final[tuple[str, ...]] = (
    "better",
    "worse",
    "best",
    "worst",
    "superior",
    "outperform",
    "beats",
    "winner",
    "loses",
    "ahead",
)


def _rate(value: Measurement) -> str:
    """A measurement as ``numerator/denominator`` with its rate."""
    if not value.measured or value.numerator is None or value.denominator is None:
        return "NOT MEASURED"
    rate = value.rate
    shown = "n/a" if rate is None else f"{rate:.3f}"
    return f"{value.numerator}/{value.denominator} ({shown})"


def _small(value: Measurement) -> str:
    """Whether the measurement's denominator is small."""
    if value.denominator is None:
        return ""
    if value.denominator_is_small:
        return f"yes — the denominator is {value.denominator}, under {SMALL_DENOMINATOR}"
    return ""


def render_markdown(run: EvaluationRun, benchmark_clause: str, superiority_clause: str) -> str:
    """The report, as Markdown."""
    lines: list[str] = []
    lines.append("# The evaluation — run against the protocol")
    lines.append("")
    lines.append(
        f"**Repository:** `{run.repo_root}` · **Revision:** `{run.revision}` · "
        f"**Protocol:** `{run.protocol_path}`"
    )
    lines.append(f"**Command:** `{run.command}`")
    lines.append(f"**Duration:** {run.duration_seconds:.1f} s")
    lines.append("")
    lines.append("## The protocol's own conditions")
    lines.append("")
    lines.append(f"> {benchmark_clause}")
    lines.append("")
    lines.append(f"> {superiority_clause}")
    lines.append("")
    lines.append(
        "The comparison section at the end of this report is where the second of "
        "those two sentences is enforced."
    )
    lines.append("")

    lines.append("## The gate classes")
    lines.append("")
    lines.append(
        "| Class | The protocol's definition | Files | Passed / collected | "
        "Collected (denominator) | Passed (numerator) | Failed | Errored | Skipped | "
        "xfail | Rate | Small denominator? |"
    )
    lines.append("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|")
    for result in run.classes:
        if not result.ran:
            state = "**NOT SELECTED**" if not result.selected else "**NOT RUN**"
            lines.append(
                f"| **{result.title}** | {result.definition} | {len(result.files)} | "
                f"{state} | — | — | — | — | — | — | — | — |"
            )
            continue
        rate = "n/a" if result.pass_rate is None else f"{result.pass_rate:.3f}"
        small = (
            f"yes — {result.collected} cases, under {SMALL_DENOMINATOR}"
            if result.denominator_is_small
            else ""
        )
        lines.append(
            f"| **{result.title}** | {result.definition} | {len(result.files)} | "
            f"**{result.passed}/{result.collected}** | "
            f"{result.collected} | {result.passed} | {result.failed} | {result.errored} | "
            f"{result.skipped} | {result.xfailed} | {rate} | {small} |"
        )
    lines.append("")

    not_run = [result for result in run.classes if not result.ran]
    if not_run:
        lines.append("### The classes that were not run, and why")
        lines.append("")
        for result in not_run:
            state = "not selected" if not result.selected else "not run"
            lines.append(f"- **{result.title}** — {state}: {result.not_run_reason}")
        lines.append("")

    lines.append("## The failure cases")
    lines.append("")
    any_failure = False
    for result in run.classes:
        if not result.failures:
            continue
        any_failure = True
        lines.append(f"### {result.title} — {len(result.failures)} case(s)")
        lines.append("")
        for case in result.failures:
            message = case.message or "(no message)"
            lines.append(f"- `{case.node_id}` — **{case.status}** — {message}")
        lines.append("")
    if not any_failure:
        lines.append("No test case failed, was skipped, or errored in this run.")
        lines.append("")

    lines.append("## The Phase 1 blockers")
    lines.append("")
    lines.append("| Blocker | Status | Witnesses | Cases | What the status means |")
    lines.append("|---|---|---|---:|---|")
    for blocker in run.blockers:
        cases = sum(
            1
            for result in run.classes
            for case in result.failures
            if PurePosixPath(case.file).name in blocker.witnesses
        )
        lines.append(
            f"| {blocker.text} | **{blocker.status}** | {len(blocker.witnesses)} | "
            f"{cases} | {blocker.reason or 'every witness was collected and passed'} |"
        )
    lines.append("")
    for blocker in run.blockers:
        if not blocker.failures:
            continue
        lines.append(f"### {blocker.text} — the witness cases that did not pass")
        lines.append("")
        for case in blocker.failures:
            message = case.message or "(no message)"
            lines.append(f"- `{case.node_id}` — **{case.status}** — {message}")
        lines.append("")

    lines.append("## The metrics")
    lines.append("")
    lines.append(
        "A metric's **value** is what the protocol asks for. A metric's "
        "**witness score** is how many of the tests that check that property "
        "passed. They are different numbers, and the witness score is never "
        "presented as the value."
    )
    lines.append("")
    lines.append("| Metric | The protocol's value | The witnesses' score | Small denominator? |")
    lines.append("|---|---|---|---|")
    for row in run.metrics:
        also = ""
        if row.also:
            also = " — " + " — ".join(_rate(value) for value in row.also)
        lines.append(
            f"| {row.text} | {_rate(row.value)}{also} | {_rate(row.witness_score)} | "
            f"{_small(row.value)} |"
        )
    lines.append("")
    for row in run.metrics:
        notes: list[str] = []
        if not row.value.measured:
            notes.append(f"**Why not measured:** {row.value.reason}")
        else:
            notes.append(f"**How it was measured:** {row.value.how}")
        for value in row.also:
            if value.measured:
                notes.append(f"**Also measured:** {value.how}")
            else:
                notes.append(f"**Also measured:** {value.reason}")
        if row.witness_score.measured:
            notes.append(
                f"**The witnesses:** {', '.join(row.witnesses)} — "
                f"{row.witness_score.numerator}/{row.witness_score.denominator} passed"
            )
        else:
            notes.append(f"**The witnesses:** {row.witness_score.reason}")
        for note in row.context:
            notes.append(note)
        lines.append(f"### {row.text}")
        lines.append("")
        for note in notes:
            lines.append(f"- {note}")
        if row.failures:
            lines.append("- **The witness cases that did not pass:**")
            for case in row.failures:
                message = case.message or "(no message)"
                lines.append(f"  - `{case.node_id}` — **{case.status}** — {message}")
        lines.append("")

    lines.append("## The comparison")
    lines.append("")
    lines.extend(_comparison_lines(run.comparison))
    lines.append("")

    if run.notes:
        lines.append("## The run's own notes")
        lines.append("")
        for note in run.notes:
            lines.append(f"- {note}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _comparison_lines(comparison: ComparisonOutcome) -> list[str]:
    """The comparison section.

    **There is no verdict here, and that is structural.** The section
    prints pairs — one metric at a time — and the words that would carry a
    verdict are the ones
    :data:`~tests.evaluation.report.RANKING_WORDS` forbids. A reader who
    wants a winner has to draw the conclusion themselves, which is the
    protocol's point: the comparison is evidence, not a claim.
    """
    if not comparison.comparable:
        lines = [
            "**No comparison was made, and none is printed.** The protocol "
            "allows a comparison only when it is like-for-like, and this one "
            "is not:",
            "",
        ]
        for reason in comparison.reasons:
            lines.append(f"- {reason}")
        lines.append("")
        lines.append(
            "So the numbers above stand on their own. They are measurements of "
            "this tree, and they are not a claim about anything else."
        )
        return lines
    lines = [
        "The comparison is like-for-like on the terms the protocol names: the "
        "same tasks at the same versions, the same model and budget, verified "
        "capabilities on both sides, and documented limitations or confidence "
        "intervals. Each line is a pair, and **there is no overall verdict**: "
        "the protocol permits a comparison only under exactly these "
        "conditions, and the report computes none.",
        "",
    ]
    for key, value in comparison.deltas:
        lines.append(f"- `{key}` — {value}")
    return lines


def render_json(run: EvaluationRun, benchmark_clause: str, superiority_clause: str) -> str:
    """The report, as JSON."""
    document: dict[str, Any] = {
        "repository": run.repo_root,
        "revision": run.revision,
        "protocol": run.protocol_path,
        "command": run.command,
        "duration_seconds": round(run.duration_seconds, 3),
        "benchmark_clause": benchmark_clause,
        "superiority_clause": superiority_clause,
        "classes": [_class_json(result) for result in run.classes],
        "blockers": [_blocker_json(blocker) for blocker in run.blockers],
        "metrics": [_metric_json(row) for row in run.metrics],
        "comparison": {
            "comparable": run.comparison.comparable,
            "reasons": list(run.comparison.reasons),
            "deltas": dict(run.comparison.deltas),
        },
        "notes": list(run.notes),
    }
    return json.dumps(document, indent=2, sort_keys=False) + "\n"


def _class_json(result: ClassResult) -> dict[str, Any]:
    """One class, as JSON."""
    return {
        "key": result.key,
        "title": result.title,
        "definition": result.definition,
        "ran": result.ran,
        "selected": result.selected,
        "not_run_reason": result.not_run_reason,
        "files": list(result.files),
        "collected": result.collected,
        "passed": result.passed,
        "failed": result.failed,
        "errored": result.errored,
        "skipped": result.skipped,
        "xfailed": result.xfailed,
        "pass_rate": result.pass_rate,
        "denominator_is_small": result.denominator_is_small,
        "duration_seconds": round(result.duration_seconds, 3),
        "failures": [
            {
                "node_id": case.node_id,
                "file": case.file,
                "status": case.status,
                "message": case.message,
            }
            for case in result.failures
        ],
    }


def _blocker_json(blocker: BlockerResult) -> dict[str, Any]:
    """One blocker, as JSON."""
    return {
        "key": blocker.key,
        "text": blocker.text,
        "status": blocker.status,
        "witnesses": list(blocker.witnesses),
        "reason": blocker.reason,
        "failures": [
            {
                "node_id": case.node_id,
                "file": case.file,
                "status": case.status,
                "message": case.message,
            }
            for case in blocker.failures
        ],
    }


def _metric_json(row: MetricRow) -> dict[str, Any]:
    """One metric, as JSON."""
    return {
        "key": row.key,
        "text": row.text,
        "value": _measurement_json(row.value),
        "also": [_measurement_json(value) for value in row.also],
        "witnesses": list(row.witnesses),
        "witness_score": _measurement_json(row.witness_score),
        "failures": [
            {
                "node_id": case.node_id,
                "file": case.file,
                "status": case.status,
                "message": case.message,
            }
            for case in row.failures
        ],
        "context": list(row.context),
    }


def _measurement_json(value: Measurement) -> dict[str, Any]:
    """One measurement, as JSON."""
    return {
        "status": value.status,
        "numerator": value.numerator,
        "denominator": value.denominator,
        "rate": value.rate,
        "denominator_is_small": value.denominator_is_small,
        "how": value.how,
        "reason": value.reason,
    }


def write_report(
    directory: Path,
    run: EvaluationRun,
    benchmark_clause: str,
    superiority_clause: str,
) -> tuple[Path, Path]:
    """Write both renderings, and say where they went."""
    directory.mkdir(parents=True, exist_ok=True)
    markdown_path = directory / "evaluation-report.md"
    json_path = directory / "evaluation-report.json"
    markdown_path.write_text(
        render_markdown(run, benchmark_clause, superiority_clause), encoding="utf-8"
    )
    json_path.write_text(render_json(run, benchmark_clause, superiority_clause), encoding="utf-8")
    return markdown_path, json_path
