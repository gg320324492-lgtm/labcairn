#!/usr/bin/env python3
"""Judge the twelve-row reopen rerun, and record it beside the 44-row ledger.

**What this is.** The twelve-row rerun of the reopen ledger was finished on a
regenerated artefact pack on 2026-11-18, and the machinery that turned it into
a record lived *outside* this repository, in a directory under
``E:/labcairn-local``. A tool that exists only in one directory on one
machine is a tool that stops existing the day that directory is moved,
copied to another laptop, or cleaned up. This script is that tool, inside the
repository, and it runs anywhere the pack is.

**What it does, in this order.**

1. Reads the pack: the twelve-row template and the artefacts it names, and
   measures each artefact's digest and size afresh.
2. Validates the filled twelve-row table against that pack -- row identity,
   the artefact each row is about, the vocabulary, and the WPS/Word boundary.
3. Judges each row against the row-level condition of the issue it feeds, and
   each issue against **its own closure condition**: #189 needs eight rows,
   #191 needs four, #192 needs two, and #190 is not in this round's scope.
4. Renders three things: the validation report, the twelve-row **append
   record**, and the closure table.

**What it never does.** It never writes to the 44-row ledger of 2026-11-10.
That ledger is the record of a *different* observation, on *different* bytes;
this rerun is recorded beside it, not merged into it. ``--write`` writes into
``--out-dir`` and nowhere else, and it backs up any file it is about to
replace.

**The failure it exists to prevent.** A row-level ``PASS`` is not an issue
closing. #191's fix is a change to an OOXML construct, and a construct fix is
only *shown* to be a fix once the caption is seen on every host that opens the
file -- and on Word the caption cannot be seen while Word refuses the file,
which is #192. So **#192's fix is a precondition of #191's evidence**, and
#191's four rows include the two Word rows #192 owns. A tool that closed an
issue because its rows read PASS would close #191 on the strength of a WPS
observation, which is the mistake this table exists to stop.

Usage:
    python scripts/closeout_12_rows.py --pack-dir <pack> --filled-csv <csv>
    python scripts/closeout_12_rows.py --pack-dir <pack> --filled-csv <csv> \
        --out-dir <dir> --write
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# --------------------------------------------------------------------------
# The vocabulary -- the same words the project's own ledger uses.
# --------------------------------------------------------------------------

#: The 27 columns of the reopen ledger, in order. The append record is
#: written on these columns, so that it can be read beside the ledger rather
#: than beside a table of its own.
HEADER: tuple[str, ...] = (
    "row_id",
    "ticket",
    "sample_id",
    "artifact",
    "file_path",
    "file_path_chars",
    "sha256_before",
    "byte_size_before",
    "host_name",
    "host_file_version",
    "host_version_measured_at",
    "expected_presence",
    "operator",
    "opened_at",
    "open_result",
    "prompt_verbatim_or_NONE",
    "presence_after_open",
    "close_action",
    "reopened_at",
    "presence_after_reopen",
    "reopen_result",
    "save_performed",
    "sha256_after",
    "byte_size_after",
    "hash_changed",
    "verdict",
    "notes",
)

#: The columns a rerun must not change: they say which artefact and which
#: host the row is about. The pack's template carries the authority for
#: these; the filled table must agree with it. The two hash columns are
#: checked against the measured artefact instead, so that a wrong cell is
#: reported once, against the thing it claims to describe.
IMMUTABLE_COLUMNS: tuple[str, ...] = (
    "row_id",
    "ticket",
    "sample_id",
    "artifact",
    "host_name",
    "expected_presence",
)

LEGAL_VERDICTS: frozenset[str] = frozenset(
    {
        "PASS",
        "REPAIR-PROMPT",
        "HOST-REWROTE",
        "PRESENCE-LOSS",
        "NOT-ATTEMPTED",
        "REFUSAL-RECORDED",
        "PENDING-HUMAN",
    }
)
OPEN_RESULTS: frozenset[str] = frozenset({"opened", "failed", "repair-prompt"})
CLOSE_ACTIONS: frozenset[str] = frozenset({"closed-no-save", "closed-with-save"})
PRESENCE_ANSWERS: frozenset[str] = frozenset({"yes", "no", "not-inspectable"})
SAVE_ANSWERS: frozenset[str] = frozenset({"yes", "no"})
HASH_ANSWERS: frozenset[str] = frozenset({"yes", "no"})
PROMPT_NONE = "NONE"

#: The marker a Word row's notes must carry when the row claims the file was
#: seen on Word. It is the difference between a Word observation and a WPS
#: observation written into a Word row.
WORD_MARKER = "word-observation-confirmed"

#: The role a row's id ends with fixes which host the row is for.
HOST_BY_ROLE: Mapping[str, str] = {
    "primary": "WPS Office",
    "reference": "Microsoft Office 2019",
}

#: A convenience default only. Every machine that does not have this pack
#: passes ``--pack-dir``; nothing in the script requires the path to exist,
#: and no test touches it.
DEFAULT_PACK_DIR = Path("E:/labcairn-local/rerun12-opaque-20261118")

#: The record this run is recorded *beside*, and never merged into. Named
#: here so that the sentence about it appears in every artefact the tool
#: writes, rather than only in the one the reader happened to open.
LEDGER_LEDGER_LINE = (
    "the 44-row ledger of 2026-11-10 is a different observation, on "
    "different bytes; this record does not amend it and does not replace it"
)


# --------------------------------------------------------------------------
# The issues this rerun bears on
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class IssueRule:
    """What one issue's closure condition needs from this rerun.

    **The required rows are the point.** A row-level ``PASS`` is worth
    nothing to an issue whose closure condition asks for a different set of
    rows: #189's image has to be visible on both hosts, so it needs all eight
    of the ``05`` and ``07`` rows; #191's construct fix has to be seen on
    every host that opens the file, so it needs all four ``08`` rows; and
    #192's is a Word refusal, so it needs the two Word ``08`` rows and
    nothing else -- **no WPS row substitutes for it**.
    """

    number: int
    title: str
    samples: tuple[str, ...]
    roles: tuple[str, ...]
    #: The conditions only a person can settle: a screenshot, a recorded
    #: decision, a closing comment. The tool checks their *form* when they
    #: are declared and never their truth.
    owner_conditions: tuple[str, ...]
    #: The issue whose fix is a precondition of this one's evidence. #192's
    #: fix is a precondition of #191's: on Word the caption cannot be seen
    #: while Word refuses the file.
    precondition: int | None = None


ISSUE_RULES: tuple[IssueRule, ...] = (
    IssueRule(
        number=189,
        title="the corpus's own PNG",
        samples=("05-image-and-relationship", "07-everything-at-once"),
        roles=("primary", "reference"),
        owner_conditions=("189-C4", "189-C5", "189-C6"),
    ),
    IssueRule(
        number=191,
        title="the 08 family's text box, and WPS's un-inspectable classes",
        samples=("08-refusals-elsewhere-in-the-document",),
        roles=("primary", "reference"),
        owner_conditions=("191-C4", "191-C5"),
        precondition=192,
    ),
    IssueRule(
        number=192,
        title="Word 2019 refuses the 08 family",
        samples=("08-refusals-elsewhere-in-the-document",),
        roles=("reference",),
        owner_conditions=("192-C5", "192-C6", "192-C7"),
    ),
)

#: #190 is not closed by this rerun and this rerun cannot close it: it is a
#: WPS rendering limitation, its one row is not among the twelve, and its
#: closure route is a dated support-matrix entry rather than a passing row.
#: It is listed here so that the closure table says so in the place a reader
#: looks when deciding what may be closed.
OUT_OF_SCOPE: Mapping[int, str] = {
    190: (
        "#190 is a WPS rendering limitation, not a defect repair; its only "
        "row is not among the twelve rerun rows, and this rerun has no "
        "evidence about it either way. It is closed by a dated "
        "support-matrix entry, not by a row."
    ),
}


# --------------------------------------------------------------------------
# Findings
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    """One thing the tool noticed.

    ``BLOCKER`` means the evidence is not usable as it stands: a row that
    was not run against the pack's artefact, a Word row without the Word
    marker, a verdict cell that contradicts the row's own record. ``REVIEW``
    means a human has to look.
    """

    severity: str
    scope: str
    subject: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "scope": self.scope,
            "subject": self.subject,
            "message": self.message,
        }


@dataclass
class Report:
    """Everything the run noticed, and everything it decided."""

    run_id: str = ""
    pack_dir: Path | None = None
    filled_csv: Path | None = None
    filled_sha256: str = ""
    ledger_path: Path | None = None
    ledger_sha256: str = ""
    ledger_rows: int = 0
    template_rows: dict[str, dict[str, str]] = field(default_factory=dict)
    pack_hashes: dict[str, tuple[str, int]] = field(default_factory=dict)
    rows: list[dict[str, str]] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    row_judgements: list[dict[str, str]] = field(default_factory=list)
    issue_judgements: list[dict[str, object]] = field(default_factory=list)
    written: list[Path] = field(default_factory=list)

    def add(self, severity: str, scope: str, subject: str, message: str) -> None:
        self.findings.append(Finding(severity, scope, subject, message))

    def blockers(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "BLOCKER"]


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    """The digest of a file's bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 16), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read a CSV and return (header, rows), or raise ValueError."""
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            raise ValueError(f"the CSV is empty: {path}") from None
        rows: list[dict[str, str]] = []
        for number, values in enumerate(reader, start=2):
            if not values:
                continue
            if len(values) != len(header):
                raise ValueError(
                    f"line {number} has {len(values)} cells, the header has {len(header)}: {path}"
                )
            rows.append(dict(zip(header, values, strict=True)))
    return header, rows


def normalise_path(text: str) -> str:
    """Return the path with doubled separators collapsed.

    The generator writes Windows paths with the separators doubled, and the
    ledger's ``file_path_chars`` column counts the single-separator
    spelling. Windows resolves both spellings to the same file; the
    character count only matches the collapsed one. A UNC prefix keeps its
    two leading separators, because those two are the prefix and not a
    doubled separator.
    """
    doubled = chr(92) * 2
    if text.startswith(doubled):
        return doubled + text[2:].replace(doubled, chr(92))
    return text.replace(doubled, chr(92))


def parse_presence(value: str) -> dict[str, str] | None:
    """Parse ``token:answer|token:answer`` into a map, or None if malformed."""
    pairs: dict[str, str] = {}
    for part in value.split("|"):
        if part.count(":") != 1:
            return None
        token, answer = part.split(":", 1)
        pairs[token] = answer
    return pairs


# --------------------------------------------------------------------------
# The rows: what a row id says
# --------------------------------------------------------------------------


def sample_of(row_id: str) -> str:
    """The sample part of a row id: everything before ``-surgical-``."""
    marker = "-surgical-"
    index = row_id.find(marker)
    return row_id[:index] if index > 0 else row_id


def role_of(row_id: str) -> str:
    """``primary`` or ``reference``: the last segment of the row id."""
    tail = row_id.rsplit("-", 1)[-1]
    return tail if tail in HOST_BY_ROLE else ""


def variant_of(row_id: str) -> str:
    """``clean`` or ``marked``: the segment before the role."""
    parts = row_id.split("-")
    return parts[-2] if len(parts) >= 2 else ""


def expected_families(row: Mapping[str, str]) -> list[str]:
    """The families the row's own cell says it expects to see."""
    cell = row.get("expected_presence", "")
    return [part for part in cell.split("|") if part]


def required_rows_of(rule: IssueRule, rows: Sequence[Mapping[str, str]]) -> list[str]:
    """The row ids of this rerun that the issue's closure condition needs."""
    return [
        str(row.get("row_id", ""))
        for row in rows
        if sample_of(str(row.get("row_id", ""))) in rule.samples
        and role_of(str(row.get("row_id", ""))) in rule.roles
    ]


def issues_feeding(row_id: str) -> list[int]:
    """The issues whose closure condition this row is a required row of."""
    sample = sample_of(row_id)
    role = role_of(row_id)
    return [rule.number for rule in ISSUE_RULES if sample in rule.samples and role in rule.roles]


# --------------------------------------------------------------------------
# The conditions
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ConditionResult:
    """One condition of one issue, measured on one row."""

    identifier: str
    met: bool
    detail: str


def _presence_of(row: Mapping[str, str], column: str) -> dict[str, str]:
    parsed = parse_presence(row.get(column, ""))
    return parsed if parsed is not None else {}


def _families_yes(row: Mapping[str, str], families: Sequence[str]) -> tuple[bool, str]:
    """Are every named family ``yes`` in both passes?"""
    open_map = _presence_of(row, "presence_after_open")
    reopen_map = _presence_of(row, "presence_after_reopen")
    gaps: list[str] = []
    for family in families:
        for label, mapping in (("open", open_map), ("reopen", reopen_map)):
            answer = mapping.get(family, "ABSENT")
            if answer != "yes":
                gaps.append(f"{family} is {answer!r} after the {label}")
    if gaps:
        return False, "; ".join(gaps)
    return True, f"every one of {', '.join(families)} is yes in both passes"


def _family_yes(row: Mapping[str, str], family: str) -> tuple[bool, str]:
    return _families_yes(row, (family,))


def _word_opened(row: Mapping[str, str]) -> tuple[bool, str]:
    """Did the file open on Word on both passes, with no dialog recorded?"""
    gaps: list[str] = []
    for column, label in (("open_result", "open"), ("reopen_result", "reopen")):
        result = row.get(column, "")
        if result != "opened":
            gaps.append(f"the {label} result is {result!r}")
    prompt = row.get("prompt_verbatim_or_NONE", "")
    if prompt.strip().upper() != PROMPT_NONE:
        gaps.append("a prompt was recorded")
    if gaps:
        return False, "; ".join(gaps)
    return True, "both passes opened and no prompt was recorded"


def _digest_unchanged(row: Mapping[str, str]) -> tuple[bool, str]:
    """Is the artefact's digest the same after the run as before it?"""
    before = row.get("sha256_before", "")
    after = row.get("sha256_after", "")
    if before and after and before == after:
        return True, "the digest is unchanged"
    return False, f"the digest went from {before[:16]}... to {after[:16]}..."


def _wps_limitation_bound(row: Mapping[str, str]) -> tuple[bool, str]:
    """Do the WPS row's notes bind the limitation to the WPS version string?"""
    version = row.get("host_file_version", "").strip()
    notes = row.get("notes", "")
    if not version:
        return False, "the row names no WPS version string to bind the limitation to"
    if version not in notes:
        return False, f"the notes do not name the WPS version {version!r}"
    return True, f"the notes bind the limitation to WPS {version}"


def _wps_uninspectable_or_visible(row: Mapping[str, str]) -> tuple[bool, str]:
    """WPS's content-controls and fields: visible, or honestly not inspectable."""
    families = ("content-controls", "fields")
    open_map = _presence_of(row, "presence_after_open")
    reopen_map = _presence_of(row, "presence_after_reopen")
    gaps: list[str] = []
    for family in families:
        answers = {open_map.get(family, "ABSENT"), reopen_map.get(family, "ABSENT")}
        if answers == {"yes"}:
            continue
        if answers == {"not-inspectable"}:
            bound, detail = _wps_limitation_bound(row)
            if not bound:
                gaps.append(f"{family} is not-inspectable, but {detail}")
            continue
        gaps.append(f"{family} is {sorted(answers)} rather than yes in both passes")
    if gaps:
        return False, "; ".join(gaps)
    return True, "every family is visible, or not-inspectable and bound to the version"


def conditions_for(issue: int, row: Mapping[str, str]) -> list[ConditionResult]:
    """The machine-checkable conditions of ``issue`` that this row bears on.

    **The conditions read the row's own record, not its verdict cell.** A
    row whose verdict cell says ``PASS`` while its ``open_result`` says
    ``failed`` has not opened the file, and a tool that read the verdict
    cell would close the issue on it.
    """
    role = role_of(str(row.get("row_id", "")))
    results: list[ConditionResult] = []

    if issue == 189:
        verdict = row.get("verdict", "")
        results.append(
            ConditionResult(
                "189-C1",
                verdict == "PASS",
                f"the verdict is {verdict!r}",
            )
        )
        met, detail = _families_yes(row, ("images", "media-parts"))
        results.append(ConditionResult("189-C2", met, detail))
        met, detail = _digest_unchanged(row)
        results.append(ConditionResult("189-C3", met, detail))
        return results

    if issue == 191:
        if role == "primary":
            met, detail = _family_yes(row, "text-boxes")
            results.append(ConditionResult("191-C1", met, detail))
            met, detail = _wps_uninspectable_or_visible(row)
            results.append(ConditionResult("191-C2", met, detail))
            return results
        if role == "reference":
            # **#192's fix is a precondition of #191's evidence.** On Word
            # the caption cannot be seen while Word refuses the file, so the
            # Word rows of #191 are measured against #192's own conditions
            # and nothing else.
            opened, opened_detail = _word_opened(row)
            visible, visible_detail = _families_yes(row, expected_families(row))
            met = opened and visible
            detail = f"#192's conditions on this row: {opened_detail}; {visible_detail}"
            results.append(ConditionResult("191-C3", met, detail))
            return results
        return results

    if issue == 192:
        opened, opened_detail = _word_opened(row)
        results.append(ConditionResult("192-C1", opened, opened_detail))
        prompt = row.get("prompt_verbatim_or_NONE", "")
        results.append(
            ConditionResult(
                "192-C2",
                prompt.strip().upper() == PROMPT_NONE,
                f"the prompt cell is {prompt!r}",
            )
        )
        met, detail = _families_yes(row, expected_families(row))
        results.append(ConditionResult("192-C3", met, detail))
        verdict = row.get("verdict", "")
        marker = WORD_MARKER in row.get("notes", "")
        unchanged, digest_detail = _digest_unchanged(row)
        met = verdict == "PASS" and marker and unchanged
        detail = (
            f"the verdict is {verdict!r}; the notes "
            f"{'carry' if marker else 'do not carry'} the {WORD_MARKER!r} "
            f"marker; {digest_detail}"
        )
        results.append(ConditionResult("192-C4", met, detail))
        return results

    return results


# --------------------------------------------------------------------------
# The owner's declarations
# --------------------------------------------------------------------------


@dataclass
class Declaration:
    """One declaration the owner has recorded, checked for form only.

    The tool checks that the declaration exists, that it names a condition of
    the issue it is filed under, and that the evidence files it cites exist
    with the digest it declares. It never checks the truth of any of it: a
    screenshot of the wrong screen is the owner's error to catch, not
    something a byte count can settle.
    """

    issue: int
    condition: str
    note: str
    evidence: list[dict[str, str]] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


@dataclass
class Waivers:
    """The rows an owner has waived, by name, for a named issue."""

    issue: int
    rows: list[str]
    note: str


@dataclass
class Declarations:
    """The owner's declarations, as read from the JSON file."""

    items: list[Declaration] = field(default_factory=list)
    waivers: list[Waivers] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def for_issue(self, issue: int) -> list[Declaration]:
        return [item for item in self.items if item.issue == issue]

    def waived_rows(self, issue: int) -> set[str]:
        rows: set[str] = set()
        for waiver in self.waivers:
            if waiver.issue == issue:
                rows.update(waiver.rows)
        return rows


def load_declarations(path: Path | None) -> Declarations:
    """Read the owner's declaration file, checking the form of each entry."""
    declarations = Declarations()
    if path is None:
        return declarations
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        declarations.problems.append(f"the declaration file could not be read: {exc}")
        return declarations
    if not isinstance(payload, dict):
        declarations.problems.append("the declaration file is not a JSON object")
        return declarations

    known_conditions: dict[int, set[str]] = {}
    for rule in ISSUE_RULES:
        known_conditions[rule.number] = set(rule.owner_conditions)

    raw_items = payload.get("declarations", [])
    if not isinstance(raw_items, list):
        declarations.problems.append("the 'declarations' key is not a list")
        raw_items = []
    for index, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            declarations.problems.append(f"declaration {index} is not an object")
            continue
        issue = raw.get("issue")
        condition = str(raw.get("condition", ""))
        if not isinstance(issue, int) or issue not in known_conditions:
            declarations.problems.append(
                f"declaration {index} names issue {issue!r}, which is not an "
                "issue this rerun bears on"
            )
            continue
        if condition not in known_conditions[issue]:
            declarations.problems.append(
                f"declaration {index} names the condition {condition!r}, which "
                f"is not one of #{issue}'s owner conditions"
            )
            continue
        evidence: list[dict[str, str]] = []
        raw_evidence = raw.get("evidence", [])
        if not isinstance(raw_evidence, list):
            declarations.problems.append(f"declaration {index}'s 'evidence' is not a list")
            raw_evidence = []
        for entry in raw_evidence:
            if not isinstance(entry, dict):
                declarations.problems.append(
                    f"declaration {index} has an evidence entry that is not an object"
                )
                continue
            target = Path(str(entry.get("path", "")))
            declared = str(entry.get("sha256", ""))
            measured = ""
            if not target.is_absolute():
                target = path.parent / target
            if not target.is_file():
                declarations.problems.append(
                    f"declaration {index} cites {entry.get('path')!r}, which does not exist"
                )
                continue
            measured = sha256_file(target)
            if declared and measured != declared:
                declarations.problems.append(
                    f"declaration {index} cites {entry.get('path')!r} with the "
                    f"digest {declared[:16]}..., and the file's digest is "
                    f"{measured[:16]}..."
                )
                continue
            evidence.append(
                {
                    "path": str(target),
                    "sha256": measured,
                }
            )
        declarations.items.append(
            Declaration(
                issue=issue,
                condition=condition,
                note=str(raw.get("note", "")),
                evidence=evidence,
            )
        )

    raw_waivers = payload.get("waivers", [])
    if not isinstance(raw_waivers, list):
        declarations.problems.append("the 'waivers' key is not a list")
        raw_waivers = []
    for index, raw in enumerate(raw_waivers):
        if not isinstance(raw, dict):
            declarations.problems.append(f"waiver {index} is not an object")
            continue
        issue = raw.get("issue")
        rows = raw.get("rows", [])
        if not isinstance(issue, int) or issue not in known_conditions:
            declarations.problems.append(
                f"waiver {index} names issue {issue!r}, which is not an issue this rerun bears on"
            )
            continue
        if not isinstance(rows, list) or not rows:
            declarations.problems.append(f"waiver {index} names no rows")
            continue
        declarations.waivers.append(
            Waivers(
                issue=issue,
                rows=[str(item) for item in rows],
                note=str(raw.get("note", "")),
            )
        )

    return declarations


# --------------------------------------------------------------------------
# Step 1 -- the pack
# --------------------------------------------------------------------------


def find_template(pack_dir: Path) -> Path | None:
    """The pack's twelve-row template, found by name."""
    for name in ("rerun-rows-template-12.csv", "rerun-rows-template.csv"):
        candidate = pack_dir / name
        if candidate.exists():
            return candidate
    matches = sorted(pack_dir.glob("*template*12*.csv"))
    return matches[0] if matches else None


def find_artifacts_dir(pack_dir: Path) -> Path | None:
    """The directory the pack's artefacts live in."""
    for candidate in (pack_dir / "artifacts" / "outputs", pack_dir / "artifacts"):
        if candidate.is_dir():
            return candidate
    return None


def check_pack(pack_dir: Path, report: Report) -> None:
    """Read the pack's template and measure the artefacts it names."""
    template_path = find_template(pack_dir)
    if template_path is None:
        report.add(
            "BLOCKER",
            "pack",
            pack_dir.name,
            "the pack holds no twelve-row template, so no row can be "
            "checked against the pack's identity.",
        )
        return
    try:
        _header, rows = read_csv_rows(template_path)
    except ValueError as exc:
        report.add("BLOCKER", "pack", template_path.name, str(exc))
        return
    for row in rows:
        report.template_rows[str(row.get("row_id", ""))] = dict(row)

    artifacts_dir = find_artifacts_dir(pack_dir)
    if artifacts_dir is None:
        report.add(
            "BLOCKER",
            "pack",
            pack_dir.name,
            "the pack holds no artifacts directory; no artefact can be re-hashed.",
        )
        return

    for row_id, row in report.template_rows.items():
        artifact = artifacts_dir / str(row.get("artifact", ""))
        if not artifact.exists():
            report.add(
                "BLOCKER",
                "pack",
                row_id,
                f"the artefact {artifact.name} is not in the pack; the "
                "row's hash cannot be measured.",
            )
            continue
        digest = sha256_file(artifact)
        size = artifact.stat().st_size
        report.pack_hashes[row_id] = (digest, size)
        if str(row.get("sha256_before", "")) != digest:
            report.add(
                "BLOCKER",
                "pack",
                row_id,
                f"the template's sha256_before is not the artefact's "
                f"(template {str(row.get('sha256_before', ''))[:16]}..., "
                f"measured {digest[:16]}...).",
            )
        if str(row.get("byte_size_before", "")) != str(size):
            report.add(
                "BLOCKER",
                "pack",
                row_id,
                f"the template's byte_size_before is "
                f"{row.get('byte_size_before')!r}, the artefact is "
                f"{size} bytes.",
            )


# --------------------------------------------------------------------------
# Step 2 -- the filled table
# --------------------------------------------------------------------------


def check_filled_csv(path: Path, report: Report) -> list[dict[str, str]]:
    """Validate the filled twelve-row table against the pack and the vocabulary."""
    header, rows = read_csv_rows(path)
    if header != list(HEADER):
        report.add(
            "BLOCKER",
            "table",
            path.name,
            f"the header is not the ledger's 27 columns in order "
            f"(it has {len(header)}: {', '.join(header)}).",
        )
    if len(rows) != 12:
        report.add("BLOCKER", "table", path.name, f"the table holds {len(rows)} rows, not 12.")
    if not report.template_rows:
        report.add(
            "BLOCKER",
            "table",
            path.name,
            "the pack's template could not be read, so no row can be "
            "checked against the pack's identity.",
        )

    seen: set[str] = set()
    for row in rows:
        row_id = str(row.get("row_id", ""))
        if row_id in seen:
            report.add("BLOCKER", "row", row_id, "the row id appears twice.")
        seen.add(row_id)

        template = report.template_rows.get(row_id)
        if template is None:
            report.add(
                "BLOCKER",
                "row",
                row_id or "<no row id>",
                "the row id is not one of the pack's twelve rows.",
            )
            continue
        for column in IMMUTABLE_COLUMNS:
            if str(row.get(column, "")) != str(template.get(column, "")):
                report.add(
                    "BLOCKER",
                    "row",
                    row_id,
                    f"the {column} cell is {row.get(column, '')!r}, the "
                    f"pack's template says {template.get(column, '')!r}.",
                )

        packed = report.pack_hashes.get(row_id)
        if packed is None:
            report.add(
                "REVIEW",
                "row",
                row_id,
                "the artefact could not be measured in the pack; the "
                "row's hash is NOT MEASURED against the pack.",
            )
        else:
            digest, size = packed
            if str(row.get("sha256_before", "")) != digest:
                report.add(
                    "BLOCKER",
                    "row",
                    row_id,
                    f"the sha256_before cell is not the pack's "
                    f"artefact hash (cell "
                    f"{str(row.get('sha256_before', ''))[:16]}..., "
                    f"artefact {digest[:16]}...). The row was not run "
                    "against the pack's artefact.",
                )
            if str(row.get("byte_size_before", "")) != str(size):
                report.add(
                    "BLOCKER",
                    "row",
                    row_id,
                    f"the byte_size_before cell is "
                    f"{row.get('byte_size_before')!r}, the pack's "
                    f"artefact is {size} bytes.",
                )

        spelling = str(row.get("file_path", ""))
        collapsed = normalise_path(spelling)
        declared = str(row.get("file_path_chars", ""))
        if declared and declared != str(len(collapsed)):
            report.add(
                "REVIEW",
                "row",
                row_id,
                f"the file_path_chars cell is {declared}, the collapsed "
                f"path is {len(collapsed)} characters.",
            )

        verdict = str(row.get("verdict", ""))
        if verdict not in LEGAL_VERDICTS:
            report.add(
                "BLOCKER",
                "row",
                row_id,
                f"the verdict cell holds {verdict!r}, which is not one "
                f"of {', '.join(sorted(LEGAL_VERDICTS))}.",
            )
        for column, legal in (
            ("open_result", OPEN_RESULTS),
            ("reopen_result", OPEN_RESULTS),
            ("close_action", CLOSE_ACTIONS),
            ("save_performed", SAVE_ANSWERS),
            ("hash_changed", HASH_ANSWERS),
        ):
            value = str(row.get(column, ""))
            if value not in legal:
                report.add(
                    "BLOCKER",
                    "row",
                    row_id,
                    f"the {column} cell holds {value!r}, which is not "
                    f"one of {', '.join(sorted(legal))}.",
                )

        for column in ("presence_after_open", "presence_after_reopen"):
            value = str(row.get(column, ""))
            parsed = parse_presence(value)
            if parsed is None:
                report.add(
                    "BLOCKER",
                    "row",
                    row_id,
                    f"the {column} cell is not a 'token:answer|token:answer' list.",
                )
                continue
            for token, answer in parsed.items():
                if answer not in PRESENCE_ANSWERS:
                    report.add(
                        "BLOCKER",
                        "row",
                        row_id,
                        f"the {column} cell answers {token!r} with "
                        f"{answer!r}, which is not one of "
                        f"{', '.join(sorted(PRESENCE_ANSWERS))}.",
                    )
            missing = [family for family in expected_families(row) if family not in parsed]
            if missing:
                report.add(
                    "BLOCKER",
                    "row",
                    row_id,
                    f"the {column} cell does not answer {', '.join(missing)}.",
                )

        prompt = str(row.get("prompt_verbatim_or_NONE", ""))
        if prompt.strip().upper() != PROMPT_NONE:
            if not prompt.strip():
                report.add(
                    "BLOCKER",
                    "row",
                    row_id,
                    "the prompt cell is empty; it holds NONE when no "
                    "dialog was recorded, and the dialog's words "
                    "otherwise.",
                )
            elif "\n" in prompt or "\r" in prompt:
                report.add(
                    "BLOCKER",
                    "row",
                    row_id,
                    "the prompt cell holds more than one line; a verbatim prompt is one line.",
                )

        before = str(row.get("sha256_before", ""))
        after = str(row.get("sha256_after", ""))
        changed = str(row.get("hash_changed", ""))
        if before and after and changed:
            actually_changed = "yes" if before != after else "no"
            if changed != actually_changed:
                report.add(
                    "BLOCKER",
                    "row",
                    row_id,
                    f"the hash_changed cell says {changed!r} and the "
                    f"two digests say {actually_changed!r}.",
                )

        # **A verdict cell that contradicts the row's own record.** The row
        # says PASS while the record says the file did not open: the cell is
        # not evidence of anything, and an issue may not be closed on it.
        if verdict == "PASS":
            for column in ("open_result", "reopen_result"):
                if str(row.get(column, "")) != "opened":
                    report.add(
                        "BLOCKER",
                        "row",
                        row_id,
                        f"the verdict cell says PASS and the {column} "
                        f"cell says {row.get(column, '')!r}; the row's "
                        "own record contradicts the cell.",
                    )

    # -- the WPS/Word boundary -------------------------------------------
    by_artifact: dict[str, dict[str, dict[str, str]]] = {}
    for row in rows:
        by_artifact.setdefault(str(row.get("artifact", "")), {})[
            role_of(str(row.get("row_id", "")))
        ] = row

    for pair in by_artifact.values():
        wps = pair.get("primary")
        word = pair.get("reference")
        if wps is None or word is None:
            continue
        wps_notes = str(wps.get("notes", ""))
        word_notes = str(word.get("notes", ""))
        if WORD_MARKER in wps_notes:
            report.add(
                "BLOCKER",
                "row",
                str(wps.get("row_id", "")),
                f"the WPS row's notes carry the {WORD_MARKER!r} "
                "marker; that marker belongs to a Word row only.",
            )
        if word_notes and word_notes == wps_notes:
            report.add(
                "BLOCKER",
                "row",
                str(word.get("row_id", "")),
                "the Word row's notes are a copy of the WPS row's "
                "notes; the Word observation was not recorded on its "
                "own.",
            )
        if "WPS" in word_notes:
            report.add(
                "REVIEW",
                "row",
                str(word.get("row_id", "")),
                "the Word row's notes name the WPS host; check that the "
                "Word observation was made on Word.",
            )
        if str(word.get("verdict", "")) == "PASS" and WORD_MARKER not in word_notes:
            report.add(
                "BLOCKER",
                "row",
                str(word.get("row_id", "")),
                f"a Word row with the verdict PASS does not carry the "
                f"{WORD_MARKER!r} marker; the observation was not "
                "confirmed on Word.",
            )

    return [dict(row) for row in rows]


# --------------------------------------------------------------------------
# Step 3 -- the closure conditions
# --------------------------------------------------------------------------


def judge_rows(report: Report) -> None:
    """Judge every row against the conditions of the issues it feeds."""
    for row in report.rows:
        row_id = str(row.get("row_id", ""))
        for issue in issues_feeding(row_id):
            for condition in conditions_for(issue, row):
                report.row_judgements.append(
                    {
                        "row_id": row_id,
                        "issue": str(issue),
                        "condition": condition.identifier,
                        "met": "YES" if condition.met else "NO",
                        "detail": condition.detail,
                    }
                )


def judge_issues(report: Report, declarations: Declarations) -> None:
    """Judge every issue against its own closure condition.

    **The order of the questions matters.** A machine condition that is
    unmet settles the issue: it is ``NOT-CLOSED``, and the gap is the work.
    Only when every machine condition is met does the question become the
    owner's, and then the verdict is ``NOT-SETTLED-BY-THE-MACHINE`` -- which
    is **not** a soft yes.
    """
    rows_by_id = {str(row.get("row_id", "")): row for row in report.rows}
    blockers_by_row: dict[str, list[Finding]] = {}
    for finding in report.blockers():
        if finding.scope == "row":
            blockers_by_row.setdefault(finding.subject, []).append(finding)
    # **A blocker about the pack or the table blocks every issue.** The
    # artefacts could not be measured, or the table is not the twelve rows:
    # that is not one row's evidence being doubtful, it is the evidence
    # itself being unverified, and no issue may close on it.
    global_blockers = [
        finding for finding in report.blockers() if finding.scope in ("pack", "table")
    ]

    for rule in ISSUE_RULES:
        required = required_rows_of(rule, report.rows)
        expected = [
            row_id
            for row_id in report.template_rows
            if sample_of(row_id) in rule.samples and role_of(row_id) in rule.roles
        ]
        missing = [row_id for row_id in expected if row_id not in rows_by_id]
        waived = declarations.waived_rows(rule.number)

        unmet: list[dict[str, str]] = []
        conditions: list[dict[str, str]] = []
        for row_id in required:
            row = rows_by_id[row_id]
            for condition in conditions_for(rule.number, row):
                status = "MET" if condition.met else "NOT MET"
                conditions.append(
                    {
                        "id": condition.identifier,
                        "row_id": row_id,
                        "status": status,
                        "detail": condition.detail,
                    }
                )
                if not condition.met and row_id not in waived:
                    unmet.append(
                        {
                            "condition": condition.identifier,
                            "row_id": row_id,
                            "detail": condition.detail,
                        }
                    )
        for row_id in missing:
            unmet.append(
                {
                    "condition": "-",
                    "row_id": row_id,
                    "detail": "the row is not in the table; the rerun has no observation for it",
                }
            )

        blocked: list[str] = []
        for row_id in required:
            for finding in blockers_by_row.get(row_id, []):
                blocked.append(f"{row_id}: {finding.message}")
        for finding in global_blockers:
            blocked.append(f"{finding.scope} {finding.subject}: {finding.message}")

        declared = {item.condition for item in declarations.for_issue(rule.number)}
        owner_gaps = [condition for condition in rule.owner_conditions if condition not in declared]

        if unmet or blocked or missing:
            verdict = "NOT-CLOSED"
        elif owner_gaps:
            verdict = "NOT-SETTLED-BY-THE-MACHINE"
        else:
            verdict = "CLOSED-READY"

        report.issue_judgements.append(
            {
                "issue": str(rule.number),
                "title": rule.title,
                "verdict": verdict,
                "required_rows": required,
                "missing_rows": missing,
                "unmet": unmet,
                "blocked_by": blocked,
                "conditions": conditions,
                "owner_conditions": list(rule.owner_conditions),
                "owner_conditions_outstanding": owner_gaps,
                "precondition": str(rule.precondition) if rule.precondition else "",
            }
        )


# --------------------------------------------------------------------------
# Step 4 -- the three artefacts
# --------------------------------------------------------------------------


def build_append_rows(report: Report) -> list[dict[str, str]]:
    """The twelve-row append record, on the ledger's own 27 columns.

    The append record carries the new observation and nothing else. The
    ledger's own rows are left where they are, because they are the record
    of a different observation on different bytes -- and the marker says so
    in every row, so that a reader who takes one row out of context still
    sees it.
    """
    out: list[dict[str, str]] = []
    pack_name = report.pack_dir.name if report.pack_dir else "?"
    for row in report.rows:
        record = {column: str(row.get(column, "")) for column in HEADER}
        marker = (
            f"RERUN {report.run_id} (source pack {pack_name}; "
            f"a second observation of the same row, on the regenerated "
            f"artefact; {LEDGER_LEDGER_LINE})"
        )
        notes = record.get("notes", "")
        record["notes"] = f"{marker}; {notes}" if notes else marker
        out.append(record)
    return out


def render_validation_report(report: Report) -> str:
    """The per-row validation report."""
    lines: list[str] = []
    lines.append(f"# Validation report - run {report.run_id}")
    lines.append("")
    lines.append(f"- pack: `{report.pack_dir}`")
    lines.append(f"- filled table: `{report.filled_csv}`")
    if report.filled_sha256:
        lines.append(f"- filled table SHA-256: `{report.filled_sha256}`")
    if report.ledger_path is not None:
        lines.append(
            f"- 44-row ledger (read-only): `{report.ledger_path}` "
            f"sha256 `{report.ledger_sha256}`, {report.ledger_rows} data rows"
        )
    lines.append(f"- {LEDGER_LEDGER_LINE}.")
    lines.append("")

    lines.append("## The pack's artefacts, measured afresh")
    lines.append("")
    lines.append("| row | artefact | sha256 | bytes |")
    lines.append("|---|---|---|---|")
    for row_id in sorted(report.pack_hashes):
        digest, size = report.pack_hashes[row_id]
        lines.append(f"| {row_id} | `{row_id}` | `{digest}` | {size} |")
    lines.append("")

    lines.append("## Findings")
    lines.append("")
    if not report.findings:
        lines.append("None. Every row matched the pack, the vocabulary and the host boundary.")
    else:
        lines.append("| severity | scope | subject | finding |")
        lines.append("|---|---|---|---|")
        for finding in report.findings:
            lines.append(
                f"| {finding.severity} | {finding.scope} | {finding.subject} | {finding.message} |"
            )
    lines.append("")
    return "\n".join(lines)


def render_closure_table(report: Report) -> str:
    """The closure table: every issue, its condition, and its verdict."""
    lines: list[str] = []
    lines.append(f"# Closure table - run {report.run_id}")
    lines.append("")
    lines.append(f"- pack: `{report.pack_dir}`")
    lines.append(f"- filled table: `{report.filled_csv}`")
    if report.filled_sha256:
        lines.append(f"- filled table SHA-256: `{report.filled_sha256}`")
    lines.append(f"- {LEDGER_LEDGER_LINE}.")
    lines.append("")
    lines.append(
        "**The three verdicts.** `CLOSED-READY` means every condition of the "
        "issue is met and the owner's evidence is on file with a recorded "
        "digest. `NOT-CLOSED` means at least one condition is unmet, and the "
        "gap is named. `NOT-SETTLED-BY-THE-MACHINE` means every "
        "machine-checkable condition is met and what remains is a person's "
        "judgement, a picture or a policy choice -- **it is not a soft "
        "yes**."
    )
    lines.append("")

    for judgement in report.issue_judgements:
        issue = judgement["issue"]
        lines.append(f"## Issue #{issue} - {judgement['title']}")
        lines.append("")
        lines.append(f"**Verdict: {judgement['verdict']}**")
        lines.append("")
        required = judgement["required_rows"]
        lines.append(
            f"Rows this issue's closure condition needs: {len(required)} of this rerun's twelve."
        )
        lines.append("")
        for row_id in required:
            lines.append(f"- `{row_id}`")
        lines.append("")
        if judgement["precondition"]:
            lines.append(
                f"**Precondition:** #{judgement['precondition']}'s fix is a "
                "precondition of this issue's evidence. A construct fix is "
                "only shown to be a fix once the caption is seen on every "
                "host that opens the file, and on Word the caption cannot be "
                f"seen while Word refuses the file, which is "
                f"#{judgement['precondition']}."
            )
            lines.append("")
        lines.append("| condition | row | status | what the row says |")
        lines.append("|---|---|---|---|")
        for condition in judgement["conditions"]:
            lines.append(
                f"| {condition['id']} | `{condition['row_id']}` | "
                f"{condition['status']} | {condition['detail']} |"
            )
        lines.append("")
        if judgement["unmet"]:
            lines.append("### What is unmet")
            lines.append("")
            for item in judgement["unmet"]:
                lines.append(f"- `{item['row_id']}` - {item['condition']}: {item['detail']}")
            lines.append("")
        if judgement["blocked_by"]:
            lines.append("### What blocks the evidence")
            lines.append("")
            for item in judgement["blocked_by"]:
                lines.append(f"- {item}")
            lines.append("")
        outstanding = judgement["owner_conditions_outstanding"]
        lines.append("### The owner's part")
        lines.append("")
        lines.append(
            "Conditions only a person can settle: "
            + ", ".join(f"`{c}`" for c in judgement["owner_conditions"])
            + "."
        )
        if outstanding:
            lines.append("")
            lines.append(
                "Outstanding, so the verdict is not `CLOSED-READY`: "
                + ", ".join(f"`{c}`" for c in outstanding)
                + "."
            )
        lines.append("")

    for issue, note in OUT_OF_SCOPE.items():
        lines.append(f"## Issue #{issue} - not in this round's scope")
        lines.append("")
        lines.append(note)
        lines.append("")

    return "\n".join(lines)


def render_manifest(report: Report, outputs: Sequence[Path]) -> str:
    """The manifest that names the run and what it wrote."""
    payload = {
        "tool": "scripts/closeout_12_rows.py",
        "run_id": report.run_id,
        "pack_dir": str(report.pack_dir) if report.pack_dir else "",
        "filled_csv": str(report.filled_csv) if report.filled_csv else "",
        "filled_sha256": report.filled_sha256,
        "ledger": {
            "path": str(report.ledger_path) if report.ledger_path else "",
            "sha256": report.ledger_sha256,
            "data_rows": report.ledger_rows,
            "written": False,
            "note": LEDGER_LEDGER_LINE,
        },
        "artefacts": {
            row_id: {"sha256": digest, "bytes": size}
            for row_id, (digest, size) in sorted(report.pack_hashes.items())
        },
        "findings": [finding.as_dict() for finding in report.findings],
        "rows": report.row_judgements,
        "issues": report.issue_judgements,
        "out_of_scope": {str(issue): note for issue, note in OUT_OF_SCOPE.items()},
        "written": [str(path) for path in outputs],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


# --------------------------------------------------------------------------
# Step 5 -- writing, atomically, with a backup
# --------------------------------------------------------------------------


def serialise_csv(header: Sequence[str], rows: Sequence[Mapping[str, str]]) -> str:
    """Serialise to text in memory. Nothing on disk is touched.

    ``QUOTE_MINIMAL`` is the point: with ``QUOTE_NONE`` a field holding a
    comma raises "need to escape, but no escapechar set", and the write that
    raised it has already truncated the file it was writing.
    """
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=list(header),
        lineterminator="\r\n",
        quoting=csv.QUOTE_MINIMAL,
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in header})
    return buffer.getvalue()


def write_text_atomically(path: Path, text: str, run_id: str) -> str:
    """Write text through a temp file, a read-back check and an atomic replace.

    Returns the path of the backup taken of the file that was there before,
    or the empty string when there was none.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp-{run_id}")
    payload = text.encode("utf-8")
    with tmp.open("wb") as handle:
        handle.write(payload)
    # Compare the bytes, not the decoded text: reading the file back with
    # universal newlines would turn the CSV's CRLF into LF and the check
    # would fire on a file that is in fact correct.
    if tmp.read_bytes() != payload:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"the round trip of {path.name} changed the bytes; nothing written.")
    backup = ""
    if path.exists():
        backup = str(path.with_name(f"{path.name}.bak-{run_id}"))
        shutil.copy2(path, backup)
    tmp.replace(path)
    return backup


def write_csv_atomically(
    path: Path, header: Sequence[str], rows: Sequence[Mapping[str, str]], run_id: str
) -> str:
    """Write a CSV through the buffer, the read-back check and the replace."""
    text = serialise_csv(header, rows)
    parsed = list(csv.DictReader(io.StringIO(text, newline="")))
    if len(parsed) != len(rows):
        raise RuntimeError(
            f"the round trip of {path.name} lost rows "
            f"({len(parsed)} of {len(rows)}); nothing written."
        )
    for got, want in zip(parsed, rows, strict=True):
        if got != {column: want.get(column, "") for column in header}:
            raise RuntimeError(f"the round trip of {path.name} changed a cell; nothing written.")
    return write_text_atomically(path, text, run_id)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a filled twelve-row reopen rerun, record it as an "
            "append record beside the 44-row ledger, and judge the issues it "
            "bears on against their own closure conditions."
        ),
    )
    parser.add_argument(
        "--pack-dir",
        default=str(DEFAULT_PACK_DIR),
        help="the rerun pack: the twelve-row template and the artefacts",
    )
    parser.add_argument(
        "--filled-csv",
        required=True,
        help="the filled twelve-row table",
    )
    parser.add_argument(
        "--out-dir",
        default=".",
        help="where --write puts its artefacts (default: the current directory)",
    )
    parser.add_argument(
        "--ledger",
        default=None,
        help=(
            "the read-only 44-row ledger of 2026-11-10; it is read for its "
            "digest and is never written to"
        ),
    )
    parser.add_argument(
        "--declarations",
        default=None,
        help="the owner's declarations and waivers, as JSON",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="write the artefacts; without it, everything is printed and nothing is written",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the machine-readable summary instead of the reports",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="the name this run is recorded under (default: the time it ran)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = Report(
        run_id=args.run_id or datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
    )
    pack_dir = Path(args.pack_dir)
    filled_path = Path(args.filled_csv)
    out_dir = Path(args.out_dir)
    report.pack_dir = pack_dir
    report.filled_csv = filled_path

    if not pack_dir.is_dir():
        print(
            f"ERROR: the pack directory does not exist: {pack_dir}. Pass --pack-dir.",
            file=sys.stderr,
        )
        return 2
    if not filled_path.exists():
        print(f"ERROR: the filled table does not exist: {filled_path}.", file=sys.stderr)
        return 2

    check_pack(pack_dir, report)

    if filled_path.is_file():
        report.filled_sha256 = sha256_file(filled_path)

    ledger_path = Path(args.ledger) if args.ledger else None
    if ledger_path is not None:
        report.ledger_path = ledger_path
        if ledger_path.is_file():
            report.ledger_sha256 = sha256_file(ledger_path)
            try:
                _header, ledger_rows = read_csv_rows(ledger_path)
                report.ledger_rows = len(ledger_rows)
            except ValueError as exc:
                report.add("REVIEW", "ledger", ledger_path.name, str(exc))
        else:
            report.add(
                "REVIEW",
                "ledger",
                ledger_path.name,
                "the ledger was named but does not exist; nothing was "
                "read from it and nothing was written to it.",
            )

    try:
        rows = check_filled_csv(filled_path, report)
    except ValueError as exc:
        print(f"ERROR: the filled table could not be read: {exc}", file=sys.stderr)
        return 2
    report.rows = rows

    declarations = load_declarations(Path(args.declarations) if args.declarations else None)
    for problem in declarations.problems:
        report.add("REVIEW", "declarations", "declaration", problem)

    judge_rows(report)
    judge_issues(report, declarations)

    append_rows = build_append_rows(report)
    validation_text = render_validation_report(report)
    closure_text = render_closure_table(report)

    outputs: list[Path] = []
    if args.write:
        ledger_resolved = ledger_path.resolve() if ledger_path is not None else None
        planned = [
            out_dir / f"rerun12-append-{report.run_id}.csv",
            out_dir / f"closeout-validation-{report.run_id}.md",
            out_dir / f"closeout-table-{report.run_id}.md",
            out_dir / f"closeout-manifest-{report.run_id}.json",
        ]
        for path in planned:
            if ledger_resolved is not None and path.resolve() == ledger_resolved:
                print(f"ERROR: refusing to write over the 44-row ledger: {path}", file=sys.stderr)
                return 2
        write_csv_atomically(planned[0], HEADER, append_rows, report.run_id)
        write_text_atomically(planned[1], validation_text, report.run_id)
        write_text_atomically(planned[2], closure_text, report.run_id)
        manifest_text = render_manifest(report, planned)
        write_text_atomically(planned[3], manifest_text, report.run_id)
        outputs = planned
        report.written = list(planned)

    if args.json:
        sys.stdout.write(render_manifest(report, outputs))
    else:
        sys.stdout.write(validation_text)
        sys.stdout.write("\n")
        sys.stdout.write(closure_text)

    blockers = len(report.blockers())
    verdicts = {
        str(judgement["issue"]): judgement["verdict"] for judgement in report.issue_judgements
    }
    if not args.json:
        sys.stdout.write(
            f"run {report.run_id}: {blockers} blocker(s), "
            f"{len(report.findings)} finding(s); "
            + ", ".join(f"#{issue} {verdict}" for issue, verdict in verdicts.items())
            + (f"; wrote {len(outputs)} file(s)" if outputs else "; wrote nothing (no --write)")
            + ".\n"
        )
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
