"""The LC-P3-02 substitute run: the option space measured, and the evidence it leaves.

**What this is.** `LC-P3-02` §5.7 item 4 asks for the substitute-set round
trip — write, reopen, compare, with the original's hash unchanged and the
non-target regions compared rather than assumed. This module is that
measurement, in the shape `tests/evaluation_docx_fidelity.py` set for LC-P2-07:
the computation is importable so a witness can re-derive any number in the
records, and the run is a command a reviewer can repeat.

**Usage.**

```bash
python -m tests.evaluation_docx_edit_fidelity --out <dir> --head <commit>
```

``--out`` is **required** and must be outside the repository: the evidence rule
in ``CLAUDE.md`` is that a run's artifacts live outside the checkout, and the
sample files exist here for a person to open in WPS and Word, not for the tree
to carry them. ``--head`` is required too, because every number in the report
belongs to the tree it was measured on.

**What the run writes, and who reads it.**

| File | Who reads it |
|---|---|
| ``samples/<sample>.docx`` | §4.9's reopen checklist, as the input |
| ``outputs/<sample>-surgical-<form>.docx`` | the checklist, as the artifact to open and reopen |
| ``fidelity/<sample>-<option>-<form>.md`` | the machine read-side comparison for that artifact |
| ``reopen-rows.csv`` | §4.9's rows, with the human columns left empty for the operator |
| ``manifest.jsonl`` | the bridge: path, sha256, size, measured_at, tool, row ids |
| ``report.json`` | every arm result, machine-side only |

**What is not here.** No host is started and no automation is attempted: §2
item 2 of the work orders takes COM and ProgID automation off the table, so
every open/reopen judgement in ``reopen-rows.csv`` is a human cell waiting for
a person, and the verdict column says ``PENDING-HUMAN`` for that reason. A
record that printed anything else would be reporting a step nobody performed.

**The advisor sample is not here either.** §5.9 holds that half open until the
owner supplies the manuscript, and `LC-P3-00` §3 forbids reporting a synthetic
row as advisor use.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from labcairn.editing.drafts import DraftForm, surgical_bytes
from labcairn.editing.evidence import (
    HOSTS,
    PRESENCE_BY_CLASS,
    ROW_COLUMNS,
    PathBudgetError,
    artifact_name,
    visible_path,
)
from labcairn.editing.fidelity import ArmResult, RegionStatus, run_arm, sha256
from labcairn.editing.samples import SAMPLES, Sample, sample_bytes
from labcairn.editing.survey import CLASS_ELEMENTS, StructureClass, survey

#: The options the run compares, in the order the matrix prints them.
OPTION_ORDER: Final[tuple[str, ...]] = ("surgical", "reserialize", "library", "rebuild")

#: Both export forms. An option with no way to write a tracked change is run
#: in both anyway and reports the same bytes twice, which is itself the
#: finding: ``ADR-0021`` says so in the column the report prints.
FORMS: Final[tuple[DraftForm, ...]] = (DraftForm.MARKED, DraftForm.CLEAN)

#: The artifacts a person is asked to open: the adopted option's output, on
#: every sample the seam wrote. The rejected options are measured in full but
#: their bytes are not handed to anyone, because no one should spend an hour
#: opening files the record already decided against.
CHECKLIST_OPTION: Final[str] = "surgical"

#: The classes evidenced by elements rather than by a part name.
_ELEMENT_CLASSES: Final[frozenset[StructureClass]] = frozenset(CLASS_ELEMENTS)


@dataclass
class Run:
    """One full pass over the substitute set."""

    results: list[ArmResult] = field(default_factory=list)
    artifacts: dict[str, bytes] = field(default_factory=dict)
    inputs: dict[str, bytes] = field(default_factory=dict)

    def produced(self) -> list[ArmResult]:
        return [result for result in self.results if not result.refused]

    def refused(self) -> list[ArmResult]:
        return [result for result in self.results if result.refused]

    def for_option(self, option: str) -> list[ArmResult]:
        return [result for result in self.results if result.option == option]

    def sample(self, name: str) -> Sample:
        for sample in SAMPLES:
            if sample.name == name:
                return sample
        raise KeyError(f"no substitute sample is named {name!r}")


def run_substitute_set(samples: tuple[Sample, ...] = SAMPLES) -> Run:
    """Every sample through every option and both forms. No path is involved."""
    run = Run()
    for sample in samples:
        data = sample_bytes(sample)
        run.inputs[f"{sample.name}.docx"] = data
        for option in OPTION_ORDER:
            for form in FORMS:
                result = run_arm(sample.name, data, sample.edit, option, form)
                run.results.append(result)
                if option == CHECKLIST_OPTION and not result.refused:
                    name = artifact_name(sample.name, option, form.value)
                    run.artifacts[name] = surgical_bytes(data, sample.edit, form)
    return run


def expected_presence(sample: Sample) -> str:
    """What the operator is asked to confirm is visible, read off the written file."""
    found = survey(sample_bytes(sample)).classes
    return "|".join(
        sorted(
            {PRESENCE_BY_CLASS[structure] for structure in found if structure in PRESENCE_BY_CLASS}
        )
    )


_NO_MEASUREMENT: Final[str] = "not measured by this run"


def matrix_rows(run: Run, samples: tuple[Sample, ...] = SAMPLES) -> list[dict[str, Any]]:
    """One row per structure class, derived from the run rather than restated.

    **``carried`` is measured twice, because a class lives in two places.** A
    class evidenced by elements is carried when the per-class comparison of a
    sample that holds it outside the edit came back identical; a class
    evidenced by a *part name* -- media, a macro, a bound custom XML item -- is
    carried when that part's digest did not move. Without the second reading
    the matrix would say "not measured" about the parts the splice is proudest
    of carrying.

    **``aimed_written`` and ``aimed_refused`` are the two columns §5.7 item 2
    asks to keep apart.** A class the seam wrote into and a class the seam
    carried but refused to write into are different answers, and one word
    covering both would let a refusal read as a loss.
    """
    rows: list[dict[str, Any]] = []
    for structure in StructureClass:
        carried = _NO_MEASUREMENT
        written_by = 0
        refused_by: list[str] = []
        for sample in samples:
            if structure not in sample.carries:
                continue
            results = [
                result
                for result in run.for_option(CHECKLIST_OPTION)
                if result.sample == sample.name
            ]
            produced = [result for result in results if not result.refused]
            if not produced:
                continue
            if structure in _ELEMENT_CLASSES:
                verdicts = [
                    line
                    for result in produced
                    for line in result.classes
                    if line.structure == structure.value
                ]
                observed = _worst(verdicts)
            else:
                parts = [
                    part
                    for result in produced
                    for part in result.parts
                    if _part_belongs_to(structure, part.name)
                ]
                if not parts:
                    continue
                observed = (
                    "IDENTICAL" if all(part.verdict == "IDENTICAL" for part in parts) else "CHANGED"
                )
            carried = observed if carried == _NO_MEASUREMENT else _merge(carried, observed)
            if sample.focus is structure and sample.role != "preserve":
                written_by += len(produced)
        for sample in samples:
            if sample.focus is not structure:
                continue
            for result in run.for_option(CHECKLIST_OPTION):
                if result.sample == sample.name and result.refused:
                    refused_by.append(result.refused)
        rows.append(
            {
                "class": structure.value,
                "carried": carried,
                "aimed_written": written_by,
                "aimed_refused": sorted(set(refused_by)),
            }
        )
    return rows


def _merge(current: str, observed: str) -> str:
    """The worst verdict a class received, because one exception falsifies a row."""
    order = ["IDENTICAL", "RESPELLED", "CHANGED", "MISSING"]
    if current not in order:
        return observed
    return observed if order.index(observed) > order.index(current) else current


def _part_belongs_to(structure: StructureClass, name: str) -> bool:
    """Whether one part name is the evidence of a package-level class."""
    from labcairn.editing.survey import CLASS_PART_PATTERNS

    pattern = CLASS_PART_PATTERNS.get(structure)
    return bool(pattern and pattern.match(name))


def _worst(verdicts: list[Any]) -> str:
    """The worst verdict a class received; an empty list is not a verdict."""
    if not verdicts:
        return "no measurement"
    order = ["IDENTICAL", "RESPELLED", "CHANGED", "MISSING"]
    worst = "IDENTICAL"
    for verdict in verdicts:
        value = verdict.status.value
        if value in order and order.index(value) > order.index(worst):
            worst = value
    return worst


def reopen_rows(run: Run, evidence_root: Path) -> list[dict[str, str]]:
    """§4.9's checklist rows for this ticket's artifacts, human cells empty.

    **One row per (artifact x host).** The machine columns — path, visible-path
    length, sha256, byte size, host, host version, the presence list — are
    filled here from the bytes. The judgement columns are empty and
    ``verdict`` says ``PENDING-HUMAN``: the machine may report what it wrote,
    and only a person may report what a host did with it.
    """
    rows: list[dict[str, str]] = []
    for name, data in sorted(run.artifacts.items()):
        sample_name = name.rsplit(f"-{CHECKLIST_OPTION}-", 1)[0]
        form = name.rsplit("-", 1)[1].removesuffix(".docx")
        sample = run.sample(sample_name)
        for role, host, version in HOSTS:
            path = visible_path(evidence_root / "outputs", name)
            rows.append(
                {
                    "row_id": f"{name.removesuffix('.docx')}-{role}",
                    "ticket": "LC-P3-02",
                    "sample_id": sample_name,
                    "artifact": name,
                    "file_path": str(path),
                    "file_path_chars": str(len(str(path))),
                    "sha256_before": sha256(data),
                    "byte_size_before": str(len(data)),
                    "host_name": host,
                    "host_file_version": version,
                    "host_version_measured_at": "2026-11-08",
                    "expected_presence": expected_presence(sample),
                    "operator": "",
                    "opened_at": "",
                    "open_result": "",
                    "prompt_verbatim_or_NONE": "",
                    "presence_after_open": "",
                    "close_action": "",
                    "reopened_at": "",
                    "presence_after_reopen": "",
                    "reopen_result": "",
                    "save_performed": "",
                    "sha256_after": "",
                    "byte_size_after": "",
                    "hash_changed": "",
                    "verdict": "PENDING-HUMAN",
                    "notes": f"{CHECKLIST_OPTION} {form}; §4.9's instrument performs this row",
                }
            )
    return rows


def option_numbers(run: Run, option: str) -> dict[str, Any]:
    """The per-option summary the report and the records print."""
    results = run.for_option(option)
    produced = [result for result in results if not result.refused]
    return {
        "produced": len(produced),
        "refused": len(results) - len(produced),
        "region_rows": sum(len(result.regions) for result in produced),
        "class_rows": sum(len(result.classes) for result in produced),
        "regions_identical": sum(
            1 for r in produced for v in r.regions if v.status is RegionStatus.IDENTICAL
        ),
        "regions_respelled": sum(
            1 for r in produced for v in r.regions if v.status is RegionStatus.RESPELLED
        ),
        "regions_changed": sum(
            1 for r in produced for v in r.regions if v.status is RegionStatus.CHANGED
        ),
        "regions_missing": sum(
            1 for r in produced for v in r.regions if v.status is RegionStatus.MISSING
        ),
        "classes_identical": sum(
            1 for r in produced for v in r.classes if v.status is RegionStatus.IDENTICAL
        ),
        "classes_respelled": sum(
            1 for r in produced for v in r.classes if v.status is RegionStatus.RESPELLED
        ),
        "classes_changed_or_missing": sum(
            1
            for r in produced
            for v in r.classes
            if v.status in (RegionStatus.CHANGED, RegionStatus.MISSING)
        ),
        "parts_changed": sorted(
            {part.name for r in produced for part in r.parts if part.verdict != "IDENTICAL"}
        ),
        "declaration_kept": all(r.xml_declaration_kept for r in produced),
        "entry_order_kept": all(r.entry_order_kept for r in produced),
        "untouched_bytes_equal": sorted({str(r.untouched_bytes_equal) for r in produced}),
        "ignorables_missing": sorted({i for r in produced for i in r.ignorables}),
        "reopen_problems": sorted({p for r in produced for p in r.reopened_problems}),
        "marked_draft_carries_the_change": all(
            any("revision:ins:LabCairn" in line for line in r.reopened_inventory)
            for r in produced
            if r.form == "marked"
        ),
    }


def report_json(run: Run, head: str, measured_at: str, evidence_root: Path) -> dict[str, Any]:
    """The machine-side report, in the form ``report.json`` carries."""
    return {
        "ticket": "LC-P3-02",
        "head": head,
        "measured_at": measured_at,
        "machine": "the trial machine, Windows, measured locally: no runner took these numbers",
        "samples": len(SAMPLES),
        "written_samples": sum(1 for sample in SAMPLES if sample.written),
        "refusal_samples": sum(1 for sample in SAMPLES if not sample.written),
        "options": list(OPTION_ORDER),
        "forms": [form.value for form in FORMS],
        "results": len(run.results),
        "by_option": {option: option_numbers(run, option) for option in OPTION_ORDER},
        "refusal_reasons": sorted({result.refused for result in run.refused()}),
        "matrix": matrix_rows(run),
        "artifacts": sorted(run.artifacts),
        "checklist_rows": len(reopen_rows(run, evidence_root)),
    }


def fidelity_markdown(result: ArmResult) -> str:
    """One artifact's machine read-side comparison, as the evidence file."""
    lines = [
        f"# {result.sample} / {result.option} / {result.form}",
        "",
        f"- original sha256 before: `{result.original_sha256}`",
        f"- original sha256 after: `{result.original_sha256_after}`",
        f"- bytes outside the located run identical: {result.untouched_bytes_equal}",
        f"- entry order kept: {result.entry_order_kept}",
        f"- XML declaration kept: {result.xml_declaration_kept}",
        f"- undeclared mc:Ignorable prefixes: {', '.join(result.ignorables) or 'none'}",
        "",
        "## parts",
        "",
        "| part | verdict | sha256 before | sha256 after |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| {part.name} | {part.verdict} | {part.sha_before[:12]} | {part.sha_after[:12]} |"
        for part in result.parts
    ]
    lines += [
        "",
        "## regions the edit did not name (top-level body children)",
        "",
        "| address | verdict | detail |",
        "|---|---|---|",
    ]
    lines += [
        f"| {region.address} | {region.status.value} | {region.detail} |"
        for region in result.regions
    ]
    lines += [
        "",
        "## structure classes the document held",
        "",
        "| class | count | verdict | detail |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| {row.structure} | {row.address} | {row.status.value} | {row.detail} |"
        for row in result.classes
    ]
    lines += [
        "",
        "## reopened by the project's own reader",
        "",
        f"- paragraphs: {result.reopened_paragraphs}",
        f"- revisions: {result.reopened_revisions}",
        f"- comments: {result.reopened_comments}",
        f"- problems: {', '.join(result.reopened_problems) or 'none'}",
        f"- inventory: {'; '.join(result.reopened_inventory) or 'empty'}",
        "",
    ]
    return "\n".join(lines)


def write_evidence(run: Run, root: Path, head: str, now: datetime) -> dict[str, Any]:
    """Write the substitute set and its evidence under ``root``, outside the tree."""
    samples_dir = root / "samples"
    outputs_dir = root / "outputs"
    fidelity_dir = root / "fidelity"
    for directory in (samples_dir, outputs_dir, fidelity_dir):
        visible_path(root, directory.name)
        directory.mkdir(parents=True, exist_ok=True)

    longest = 0
    for name, data in sorted(run.inputs.items()):
        if run.sample(name.removesuffix(".docx")).hostile:
            # **The two hostile inputs are measured, never written.** A file
            # that is not a package is refused before any bytes exist, and
            # putting it on disk under a ``.docx`` name would hand §4.9's
            # operator something to open that the seam already refused to
            # read. The manifest carries their hashes instead, and the report
            # counts them.
            continue
        path = visible_path(samples_dir, name)
        path.write_bytes(data)
        longest = max(longest, len(str(path)))
    for name, data in sorted(run.artifacts.items()):
        path = visible_path(outputs_dir, name)
        path.write_bytes(data)
        longest = max(longest, len(str(path)))

    for result in run.produced():
        name = f"{result.sample}-{result.option}-{result.form}.md"
        (fidelity_dir / name).write_text(fidelity_markdown(result), encoding="utf-8")

    rows = reopen_rows(run, root)
    (root / "reopen-rows.csv").write_text(
        ",".join(ROW_COLUMNS) + "\n" + "\n".join(_csv_row(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    entries = [
        ("sample-input", "samples", run.inputs),
        ("rewrite-output", "outputs", run.artifacts),
    ]
    lines = []
    for kind, folder, table in entries:
        for name, data in sorted(table.items()):
            if kind == "sample-input" and run.sample(name.removesuffix(".docx")).hostile:
                # **The manifest describes the disk.** The two hostile inputs
                # are refused before a path exists, so they are never written
                # and never hashed here; the report counts them among the
                # refusal samples, where a file that was never written cannot
                # be mistaken for an entry someone dropped.
                continue
            path = root / folder / name
            lines.append(
                json.dumps(
                    {
                        "kind": kind,
                        "path": str(path),
                        "file_path_chars": len(str(path)),
                        "sha256": sha256(data),
                        "byte_size": len(data),
                        "measured_at": now.isoformat(),
                        "measuring_tool": "python -m tests.evaluation_docx_edit_fidelity",
                        "head": head,
                        "row_ids": [row["row_id"] for row in rows if row["artifact"] == name],
                    },
                    ensure_ascii=False,
                )
            )
    (root / "manifest.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (root / "report.json").write_text(
        json.dumps(
            report_json(run, head, now.isoformat(), root),
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return {
        "evidence_root": str(root),
        "inputs": sum(1 for name in run.inputs if not run.sample(name.removesuffix(".docx")).hostile),
        "hostile_inputs": sum(
            1 for name in run.inputs if run.sample(name.removesuffix(".docx")).hostile
        ),
        "artifacts": len(run.artifacts),
        "rows": len(rows),
        "longest_visible_path": longest,
    }


def _csv_row(row: dict[str, str]) -> str:
    return ",".join(json.dumps(row.get(column, ""), ensure_ascii=False) for column in ROW_COLUMNS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, required=True, help="the evidence directory, outside the repository"
    )
    parser.add_argument("--head", default="", help="the commit the numbers belong to")
    parser.add_argument("--quiet", action="store_true")
    arguments = parser.parse_args(argv)

    root = arguments.out.resolve()
    repository = Path(__file__).resolve().parent.parent
    if _is_within(root, repository):
        print(  # noqa: T201 - a measurement report, not product code
            f"--out {root} is inside the repository; the evidence root lives outside it",
            file=sys.stderr,
        )
        return 2
    if not arguments.head:
        print(  # noqa: T201 - a measurement report, not product code
            "--head is required: these numbers belong to the tree they were measured on",
            file=sys.stderr,
        )
        return 2
    try:
        run = run_substitute_set()
        summary = write_evidence(run, root, arguments.head, datetime.now(UTC))
    except PathBudgetError as exc:
        print(str(exc), file=sys.stderr)  # noqa: T201 - a measurement report, not product code
        return 2
    if not arguments.quiet:
        print(json.dumps(summary, indent=2, ensure_ascii=False))  # noqa: T201 - a measurement report
    return 0


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


__all__ = [
    "CHECKLIST_OPTION",
    "FORMS",
    "OPTION_ORDER",
    "Run",
    "expected_presence",
    "fidelity_markdown",
    "main",
    "matrix_rows",
    "option_numbers",
    "reopen_rows",
    "report_json",
    "run_substitute_set",
    "write_evidence",
]


if __name__ == "__main__":
    raise SystemExit(main())
