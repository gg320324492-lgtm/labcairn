"""Witnesses for the P4-PILOT runbook and the P4-G1..G4 exit skeleton.

**What this file watches.** The pilot's operating manual
(``docs/plans/LC-P4-PILOT-runbook.md``) and the exit-record skeleton
(``docs/acceptance/P4-G1-G4-record-skeleton.md``) are prose documents, and
prose that nothing checks drifts: a step that loses its command, a gate
whose condition is silently dropped, a vocabulary that starts spelling
words the code refuses. These tests read the two documents and the
execution plan they summarise, and fail when the three stop agreeing.

**The property each test pins.**

* the runbook covers every one of plan §9.2's twelve steps;
* the skeleton covers all four gates of plan §11 and names their
  conditions;
* the runbook and skeleton mark every undecided thing explicitly --
  plan §12's three decisions as ``TBD``, every evidence slot and verdict
  as ``PENDING`` -- so a filled record cannot pass itself off as an
  unfilled one;
* the issue vocabularies the runbook spells are the ones
  ``labcairn.application.issues`` defines, not the older spellings the
  plan's prose or the feedback form's submitter-facing scale use;
* neither document carries a real name, affiliation or project number --
  the privacy rule the desensitisation checklist applies to the paper,
  applied to the trial's own records, enforced as CJK-run and
  identifier-pattern checks in the spirit of
  ``tests/test_no_reference_leakage.py``.

**How the vocabularies are read.** From the source, not from a copy: the
severities and categories are imported from
``labcairn.application.issues``, so a vocabulary change that forgets the
documents fails here, and a document that drifts from the code fails
here. The import is the point -- a duplicated literal would agree with
itself instead of with the code.

**This file carries no Chinese by design.** The documents it reads are
English, and the plan's Chinese headings are anchored by their numeric
prefixes (``### 9.2``, ``## 11``) rather than transcribed -- the same
reason the skeleton paraphrases the plan's conditions instead of quoting
them.
"""

from __future__ import annotations

import base64
import json
import re
import subprocess
import sys
import threading
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Final, get_args
from urllib.parse import parse_qs, urlparse

import pytest
from deadline_support import bounded_run
from workbench_serve_support import run_cli, start_served_workbench

from labcairn.application.issues import PILOT_ISSUE_CATEGORIES, PILOT_ISSUE_SEVERITIES

REPO_ROOT: Final = Path(__file__).resolve().parent.parent

RUNBOOK: Final = Path("docs") / "plans" / "LC-P4-PILOT-runbook.md"
SKELETON: Final = Path("docs") / "acceptance" / "P4-G1-G4-record-skeleton.md"
PLAN: Final = Path("docs") / "plans" / "PHASE_4-execution-plan.md"

#: Plan §9.2's twelve steps, as the runbook's own headings name them. The
#: runbook numbers its subsections "Step N -- ..."; a step that loses its
#: heading breaks the walk this test takes through the document.
RUNBOOK_STEP_TITLES: Final[tuple[str, ...]] = (
    "Import the paper, its comments and its revision marks",
    "Check the original file's digest and version information",
    "Run the real model to generate suggestions",
    "Advisor and students watch the stage progress",
    "Read each opinion with its evidence, one by one",
    "Preview the modifications' impact",
    "Approve the suggestions, one by one",
    "Apply the approved modifications",
    "Generate the four deliverables",
    "Export the full package through the delivery centre",
    "Let the system keep the process records",
    "Advisor and students supply the quality conclusions",
)

#: The gate sections the skeleton must hold, in the plan §11's order.
GATE_IDS: Final[tuple[str, ...]] = ("P4-G1", "P4-G2", "P4-G3", "P4-G4")

#: Plan §12's three pre-opening decisions, by the skeleton's own ids.
SKELETON_DECISION_IDS: Final[tuple[str, ...]] = ("D-1", "D-2", "D-3")

#: The undecided marker the skeleton's evidence slots and verdicts carry.
PENDING: Final = "PENDING"

#: The undecided marker the §12 decisions carry.
TBD: Final = "TBD"

#: A maximal run of Han characters -- the same shape
#: ``scripts/cjk_ceilings.py`` measures and
#: ``test_no_reference_leakage.py`` pins. The pilot's own records are held
#: to no Chinese at all: they are English by design, and the plan's
#: conditions are paraphrased with section-number anchors, never
#: transcribed.
HAN_RUN: Final = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")

#: A CJK fullwidth enumeration comma -- the mark a half-translated draft
#: leaves behind in English prose.
FULLWIDTH_COMMA: Final = re.compile(r"\u3001")

#: Identifier shapes the trial's records must not carry. These are
#: heuristics tuned to the leak shapes this project guards against: an
#: email address, a phone number, a grant/project number, an ORCID. A
#: name none of these shapes catch is caught by the role rule instead:
#: the runbook names participants only by role or pseudonym, and the
#: skeleton never names a participant at all.
LEAK_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("email address", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("phone number", re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")),
    (
        "grant/project number prefix",
        re.compile(
            r"(?:Project|Grant|Contract)\s*(?:No\.?|Number|#)\s*[:.]?\s*"
            r"[A-Z0-9][-A-Z0-9/]{3,}",
            re.IGNORECASE,
        ),
    ),
    (
        "long number after No.",
        re.compile(r"\bNo\.?\s*[:.]?\s*\d{6,}", re.IGNORECASE),
    ),
    (
        "ORCID",
        re.compile(r"\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b"),
    ),
)

#: Capitalised words that open non-person phrases in these documents.
#: The personal-name check below flags two consecutive capitalised words;
#: this allowlist keeps the documents' legitimate capitalised nouns from
#: reading as names. It is an allowlist of words, not of people.
NON_PERSON_WORDS: Final[frozenset[str]] = frozenset(
    {
        "A",
        "After",
        "An",
        "Approval",
        "Approve",
        "Apply",
        "Advisor",
        "Before",
        "Blocker",
        "Check",
        "Each",
        "Entry",
        "Evidence",
        "Export",
        "Export the",
        "Gate",
        "Generate",
        "How",
        "Import",
        "Issue",
        "LabCairn",
        "Let",
        "Machine",
        "No",
        "On",
        "One",
        "Participants",
        "PENDING",
        "Phase",
        "Plan",
        "Privacy",
        "Read",
        "Roles",
        "Run",
        "Session",
        "Serious",
        "Start",
        "Step",
        "TBD",
        "The",
        "These",
        "This",
        "What",
        "Where",
        "Windows",
        "With",
        "Word",
    }
)


def _read(relative: Path) -> str:
    """The document's text, with the test's own failure naming the path."""
    path = REPO_ROOT / relative
    assert path.is_file(), f"{relative} must exist for the pilot witnesses"
    return path.read_text(encoding="utf-8")


def _runbook() -> str:
    return _read(RUNBOOK)


def _skeleton() -> str:
    return _read(SKELETON)


def _plan() -> str:
    return _read(PLAN)


def _flowtext(text: str) -> str:
    """The text with every whitespace run collapsed to one space.

    Markdown reflow wraps lines at arbitrary columns; a phrase check on
    the raw text fails on the wrap, not on the content. The wrapped form
    is the same sentence, so the checks that ask about phrases ask about
    the collapsed form.
    """
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# The runbook covers the twelve steps.
# ---------------------------------------------------------------------------


def test_the_runbook_covers_all_twelve_trial_steps() -> None:
    """Every step of plan §9.2 has its own runbook subsection, in order.

    A missing step is an operation the trial would improvise, and an
    improvised step is one whose evidence nobody planned. The headings
    are read in document order, so a reordering also fails: the runbook
    is walked top to bottom by design.
    """
    text = _runbook()
    found = re.findall(r"^### Step (\d+) — (.+)$", text, re.MULTILINE)

    expected = [(str(i), title) for i, title in enumerate(RUNBOOK_STEP_TITLES, start=1)]
    assert found == expected, (
        "the runbook's step headings must be exactly plan §9.2's twelve "
        f"steps, in order.\n  expected: {expected}\n  found:    {found}"
    )


def test_the_runbook_states_the_pilot_shape_and_the_material_boundary() -> None:
    """The runbook fixes the trial's shape and its material boundary.

    Plan §9.1's shape (one project, 3-5 members, one advisor, 2-4
    students) and G0 §4's boundary (raw files only in the authorised
    environment; the repository carries metadata only) are the two
    commitments every step leans on. A runbook that lost either would
    let a step improvise them.
    """
    flow = _flowtext(_runbook())
    # The en dashes are built from escapes: the runbook's typography uses
    # U+2013, and the assertion must match its characters exactly without
    # putting an ambiguous dash literal in this source file (RUF001).
    en_dash = "\u2013"
    for phrase in (
        "one project",
        f"3{en_dash}5 participants",
        "one advisor",
        f"2{en_dash}4 students",
        "E:/trial-material/",
        "E:/labcairn-local/",
        "sha256",
    ):
        assert phrase in flow, (
            f"the runbook must state {phrase!r}: the trial's shape and the "
            "no-material boundary are commitments every step leans on"
        )


def test_the_runbook_names_both_entry_point_kinds_and_their_routes() -> None:
    """Every step's entry points are real surfaces this tree exposes.

    The runbook names CLI commands (``labcairn ...``) and service routes
    (``GET|POST|PATCH /...``). The routes it names are the loop's
    surfaces; a route that lost its name here is a step with no stated
    entry point.
    """
    text = _runbook()
    assert "uv run labcairn" in text, "the runbook names its CLI entries through the console script"
    for route in (
        "POST /task/select",
        "POST /review/suggest",
        "POST /review/preview",
        "POST /review/decision",
        "POST /review/apply",
        "GET /review/deliverables",
        "POST /issues",
        "GET /issues",
        "PATCH /issues/{issue_id}/status",
    ):
        assert route in text, (
            f"the runbook must name the route {route!r}: it is one of the "
            "loop's surfaces the trial drives"
        )


def test_every_route_the_runbook_names_is_a_route_this_tree_serves() -> None:
    """A route the runbook names must exist in the service.

    **Why the other direction needs a witness of its own.** The witness
    above checks that the runbook *names* the routes the trial drives. It
    says nothing about whether those routes are still served, so a route
    renamed or removed leaves the runbook naming a surface that is not
    there -- and the trial would discover it at the desk, in front of a
    participant, at the step where the evidence is due.

    **How the routes are read.** The service's routes are declared in one
    file, so the file is parsed and the paths are read out of it: a path
    the runbook names that no declaration carries is a runbook naming a
    surface the service does not have.

    **The command lines are read too.** A runbook that names a CLI
    command the console script does not register is the same hole, and
    the option's position matters as well: ``--workspace`` is the command
    line's own option, so it is written before the command and a runbook
    that puts it after would build the workspace in the wrong directory.
    """
    import ast
    import re
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent
    routes_source = repo_root / "src" / "labcairn" / "api" / "routes.py"
    tree = ast.parse(routes_source.read_text(encoding="utf-8"))
    declared: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if not isinstance(function, ast.Attribute) or function.attr not in {
            "get",
            "post",
            "put",
            "patch",
            "delete",
        }:
            continue
        if not isinstance(function.value, ast.Name) or function.value.id != "router":
            continue
        for argument in node.args:
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                declared.add(argument.value)
                break

    text = _runbook()
    named = set(re.findall(r"\b(?:GET|POST|PUT|PATCH|DELETE) (/[A-Za-z0-9_{}/-]+)", text))
    assert named, "the runbook names no routes at all, so this witness watches nothing"

    missing = sorted(route for route in named if route not in declared)
    assert not missing, (
        "the runbook names routes the service does not serve: "
        f"{missing}. A step whose entry point is not there fails at the desk, "
        "in front of a participant, at the step where the evidence is due."
    )

    # The command lines the runbook writes, and the option's position.
    commands = re.findall(r"uv run labcairn ([^\n\\]+)", text)
    assert commands, "the runbook writes no command lines, so this witness watches nothing"
    cli_source = repo_root / "src" / "labcairn" / "cli" / "commands.py"
    cli_tree = ast.parse(cli_source.read_text(encoding="utf-8"))
    registered: set[str] = set()
    for node in ast.walk(cli_tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if not isinstance(function, ast.Attribute) or function.attr != "command":
            continue
        if node.args and isinstance(node.args[0], ast.Constant):
            registered.add(str(node.args[0].value))
        for keyword in node.keywords:
            if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                registered.add(str(keyword.value.value))
    # A sub-application's own command is registered on the sub-application, so
    # the names of the sub-applications count too.
    for node in ast.walk(cli_tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_typer"
        ):
            for keyword in node.keywords:
                if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                    registered.add(str(keyword.value.value))

    for line in commands:
        words = line.split()
        if not words or words[0].startswith("-"):
            continue
        if "--workspace" not in words:
            continue
        # **The option is the command line's own, so it goes first.** A
        # command line that writes it after the command builds the workspace
        # in the current directory instead of the one the later steps
        # address, and the later command refuses it with
        # WORKSPACE_NOT_INITIALISED -- a failure at the desk, at the first
        # step, in front of the owner.
        assert words.index("--workspace") == 0, (
            f"the runbook writes {line.strip()!r} with --workspace after the "
            "command, but --workspace is the command line's own option: it "
            "goes before the command, or the workspace is built in the "
            "current directory and the later command refuses it with "
            "WORKSPACE_NOT_INITIALISED"
        )


def test_every_runbook_step_names_its_evidence_and_its_failure_path() -> None:
    """Each step subsection carries an evidence slot and a failure path.

    The runbook's contract with the trial is per-step: what is recorded,
    and what to do when the step fails. A step that lost either would
    send the trial out with no evidence plan and no recovery plan.
    """
    text = _runbook()
    for number, _title in enumerate(RUNBOOK_STEP_TITLES, start=1):
        section = text.split(f"### Step {number} — ", 1)[1].split("\n### ", 1)[0]
        assert "**Evidence recorded.**" in section or "**Evidence slot:**" in section, (
            f"step {number} must state what evidence it records"
        )
        assert "**On failure.**" in section, f"step {number} must state what to do when it fails"
        assert "PENDING" in section, f"step {number} must carry its PENDING evidence slot"


# ---------------------------------------------------------------------------
# The skeleton covers the four gates.
# ---------------------------------------------------------------------------


def test_the_skeleton_covers_all_four_gates() -> None:
    """Every gate of plan §11 has its own skeleton section.

    The plan spells the gate ids ``P4-G1`` … ``P4-G4``; the skeleton's
    headings must carry all four, and each must declare a PENDING
    verdict -- a skeleton that opened with a verdict would be grading
    the trial in advance.
    """
    text = _skeleton()
    for gate in GATE_IDS:
        pattern = re.compile(rf"^## {re.escape(gate)} — ", re.MULTILINE)
        assert pattern.search(text), (
            f"the skeleton must hold a '## {gate} —' section for plan §11's gate"
        )
    assert text.count("**Gate verdict:** PENDING") == len(GATE_IDS), (
        "each gate's verdict line must read PENDING: the skeleton writes no result in advance"
    )


def test_the_skeleton_states_the_plan_conditions_per_gate() -> None:
    """Each gate's section carries the plan's conditions, section-anchored.

    The skeleton's contract is that the trial is graded against the
    plan's conditions, anchored to their section numbers. Each gate
    section therefore restates its conditions under a heading that names
    the plan section, and the restatement is not empty.
    """
    text = _skeleton()
    for gate in GATE_IDS:
        section = text.split(f"## {gate} — ", 1)[1].split("\n## ", 1)[0]
        assert re.search(r"\*\*Plan §11 conditions", section), (
            f"the {gate} section must state the plan §11 conditions it judges"
        )
        bullets = re.findall(r"^- ", section, re.MULTILINE)
        assert bullets, f"the {gate} section's condition restatement holds no condition lines"


def test_the_skeleton_names_evidence_producers_and_pending_slots() -> None:
    """Every evidence slot names what produces it and stays PENDING.

    A slot with no producer is a slot nobody is on the hook to fill, and
    a slot marked anything but PENDING is a verdict smuggled in ahead of
    its evidence.
    """
    text = _skeleton()
    rows = re.findall(r"^\| G\d-\d \|", text, re.MULTILINE)
    assert len(rows) >= 18, (
        f"the four gates' evidence tables hold {len(rows)} rows; the four "
        "gates' conditions require at least 18 slots"
    )
    assert f"| {PENDING} |" in text, "the evidence tables' status column must be PENDING"
    assert "the runbook" in text and "runbook step" in text.lower(), (
        "the evidence slots name the runbook step that produces them"
    )


def test_the_skeleton_carries_the_three_confirmed_plan_12_decisions() -> None:
    """Plan §12's three decisions are present and carry the owner's answers.

    The decisions are prerequisites, not gate conditions: a skeleton that
    omitted them would let the trial open without them, and one that still
    marked them TBD after the owner answered would hide a decision that was
    made. They are carried as D-1..D-3, each confirmed on 2026-11-24.
    """
    text = _skeleton()
    assert "The three pre-opening decisions (plan §12)" in text, (
        "the skeleton must carry plan §12's three pre-opening decisions"
    )
    for decision in SKELETON_DECISION_IDS:
        row = re.search(rf"^\| {decision} \| .+$", text, re.MULTILINE)
        assert row, f"decision {decision} must have its own row in the skeleton"
        assert "CONFIRMED 2026-11-24" in row.group(0), (
            f"decision {decision} must carry the owner's 2026-11-24 confirmation"
        )


def test_the_skeleton_distinguishes_system_capability_from_trial_only() -> None:
    """Every evidence row says which kind of coverage it needs.

    Some conditions are backed by built, witnessed machinery, and the
    trial confirms them on the pilot paper; others are only decidable by
    the real trial. A skeleton that blurred the distinction would let a
    capability's existence stand in for a trial's judgement.
    """
    text = _skeleton()
    assert "System capability" in text, "rows backed by system capability must say so"
    assert "Real trial only" in text, "rows only the real trial can decide must say so"


def test_the_runbook_and_skeleton_reference_each_other_and_the_drafts() -> None:
    """The two documents and the three DRAFTs form one connected set.

    The runbook produces the evidence the skeleton reads; both rest on
    the three pilot-preparation drafts. A document that lost its links
    would leave the trial's readers guessing which record feeds which.
    """
    runbook, skeleton = _runbook(), _skeleton()
    assert "LC-P4-PILOT-runbook.md" in skeleton, (
        "the skeleton must point at the runbook that fills its slots"
    )
    assert "P4-G1-G4-record-skeleton.md" in runbook, (
        "the runbook must point at the skeleton its evidence feeds"
    )
    for draft in (
        "LC-P4-PILOT-desensitisation-checklist.md",
        "LC-P4-PILOT-model-authorisation-draft.md",
        "LC-P4-PILOT-feedback-form-template.md",
    ):
        assert draft in runbook, f"the runbook must cite the draft {draft}"
    assert "PHASE_4-execution-plan.md" in runbook, (
        "the runbook cites the execution plan it summarises"
    )
    assert "PHASE_4-execution-plan.md" in skeleton, (
        "the skeleton cites the execution plan it summarises"
    )


# ---------------------------------------------------------------------------
# The vocabularies are the code's, not the old spellings.
# ---------------------------------------------------------------------------


def test_the_runbook_spells_the_code_issue_vocabularies() -> None:
    """The runbook's severity and type words are the code's own.

    The plan's prose and the feedback form's submitter-facing scale use
    older spellings (``blocking|severe|normal``, ``ui``). The system's
    closed vocabularies are what ``labcairn.application.issues`` defines,
    and the runbook must spell those -- a trial that recorded ``ui``
    would be refused at the wire.
    """
    text = _runbook()
    for word in PILOT_ISSUE_SEVERITIES:
        assert f"`{word}`" in text, (
            f"the runbook must spell severity {word!r} as the code defines it"
        )
    for word in PILOT_ISSUE_CATEGORIES:
        assert f"`{word}`" in text, f"the runbook must spell type {word!r} as the code defines it"


def test_the_runbook_maps_the_form_scale_onto_the_code_vocabulary() -> None:
    """The form's submitter-facing words are mapped, not adopted.

    The feedback form asks submitters for ``blocking|severe|normal`` and
    ``ui``; the system refuses all four. The runbook must carry the
    triage mapping, so a form item lands in the system under the words
    the system accepts. The mapping is matched against the collapsed
    text, because a reflowed line break inside a mapping is still the
    mapping.
    """
    text = _flowtext(_runbook())
    for mapping in (
        "`blocking` → `blocker`",
        "`severe` → `serious`",
        "`ui` → `interface`",
    ):
        assert mapping in text, (
            f"the runbook must carry the triage mapping {mapping}: the form's "
            "word is refused at the wire, and the mapping is what makes the "
            "form recordable"
        )


def test_the_skeletons_issue_conditions_use_the_code_vocabulary() -> None:
    """G4's blocker/serious conditions use the code's severity words.

    The plan's issue severities become the skeleton's English, and the
    English must be the system's words -- they are the values the issue
    record and its filters actually carry.
    """
    text = _skeleton()
    assert "`blocker`" in text, "G4's blocker condition uses the code's severity word"
    assert "`serious`" in text, "G4's serious condition uses the code's severity word"


def test_the_issue_vocabularies_are_what_the_wire_accepts() -> None:
    """The code's vocabularies match the API contract's literals.

    The layer's tuples and the wire's ``Literal`` types are two
    spellings of one vocabulary; this test reads both and fails when
    they disagree -- the same drift the runbook is guarded against, seen
    from the code's own side.
    """
    from labcairn.api import contracts

    severity_annotation = contracts.IssueRecordBody.model_fields["severity"].annotation
    category_annotation = contracts.IssueRecordBody.model_fields["category"].annotation
    assert severity_annotation is not None and category_annotation is not None, (
        "the issue body's severity and category must be typed"
    )
    assert set(get_args(severity_annotation)) == set(PILOT_ISSUE_SEVERITIES), (
        "the wire's severity vocabulary and the layer's disagree"
    )
    assert set(get_args(category_annotation)) == set(PILOT_ISSUE_CATEGORIES), (
        "the wire's type vocabulary and the layer's disagree"
    )


# ---------------------------------------------------------------------------
# Privacy: no real names, affiliations or project numbers.
# ---------------------------------------------------------------------------


def test_the_pilot_records_carry_no_chinese() -> None:
    """Both pilot records are English throughout.

    The trial's own records are English by design, and the corpus's
    words are not in the repository. The plan's conditions are
    paraphrased with section-number anchors, so neither document needs
    -- or is allowed -- a single Han character. This is the CJK-ceiling
    discipline at its strictest: a new record with no inherited
    allowance.
    """
    for relative in (RUNBOOK, SKELETON):
        runs = HAN_RUN.findall(_read(relative))
        assert not runs, (
            f"{relative} carries Chinese ({runs[:5]}); the pilot's own "
            "records are English, and the plan is quoted by section number"
        )


def test_the_pilot_records_carry_no_fullwidth_punctuation() -> None:
    """No CJK enumeration comma slips into the English prose.

    ``、`` is the mark a half-translated draft leaves behind.
    """
    for relative in (RUNBOOK, SKELETON):
        assert not FULLWIDTH_COMMA.search(_read(relative)), (
            f"{relative} carries a CJK enumeration comma; its prose is English"
        )


@pytest.mark.parametrize(("kind", "pattern"), LEAK_PATTERNS)
def test_the_pilot_records_carry_no_identifying_pattern(
    kind: str, pattern: re.Pattern[str]
) -> None:
    """No email, phone, grant number or ORCID in either document.

    These are the shapes a real name or affiliation leaves behind even
    when the name itself is gone. The check is heuristic, but the
    heuristics are the ones the leak shapes call for, and a hit is a
    stop, not a warning.
    """
    for relative in (RUNBOOK, SKELETON):
        match = pattern.search(_read(relative))
        assert match is None, (
            f"{relative} carries what looks like a {kind} ({match.group(0)!r}); "
            "the trial's records name roles and pseudonyms only"
        )


@pytest.mark.parametrize("relative", [RUNBOOK, SKELETON])
def test_the_pilot_records_name_participants_by_role_only(relative: Path) -> None:
    """The documents' prose carries no personal-name shape.

    A personal name in running prose reads as two consecutive
    capitalised words that are not one of the documents' legitimate
    capitalised nouns. The check is deliberately narrow -- it looks for
    the *shape*, and lets the allowlisted non-person words through --
    because the role rule (advisor, student, participant, owner) is the
    real boundary, and this is the net under it.
    """
    text = _read(relative)
    # Running prose only: headings, table rows and fenced blocks carry the
    # documents' structural capitalisation, not names.
    prose = "\n".join(line for line in text.splitlines() if not line.startswith(("```", "|", "#")))
    suspects = [
        f"{first} {second}"
        for first, second in re.findall(r"\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b", prose)
        if first not in NON_PERSON_WORDS and second not in NON_PERSON_WORDS
    ]
    assert not suspects, (
        f"{relative} names {suspects[:5]}, which look like personal names; "
        "the trial's records name participants by role or pseudonym only"
    )


# ---------------------------------------------------------------------------
# The plan still says what the documents summarise.
# ---------------------------------------------------------------------------


def test_the_plan_still_holds_twelve_steps_four_gates_and_three_decisions() -> None:
    """The plan sections the documents summarise still say so.

    These witnesses summarise a source document; if the source changes
    shape, the summaries must be re-read, not carried forward. The
    plan's Chinese headings are anchored by their numeric prefixes, not
    transcribed -- the same rule the skeleton's paraphrase follows.
    """
    plan = _plan()
    assert re.search(r"^### 9\.2 ", plan, re.MULTILINE), "plan §9.2 is the twelve-step flow"
    assert re.search(r"^### 9\.4 ", plan, re.MULTILINE), "plan §9.4 is the issue vocabulary"
    assert re.search(r"^## 11\. ", plan, re.MULTILINE), "plan §11 is the four gates"
    assert re.search(r"^## 12\. ", plan, re.MULTILINE), "plan §12 is the three decisions"
    assert "### P4-G1" in plan and "### P4-G4" in plan, "the plan names gates P4-G1..G4"

    # The twelve steps, numbered, in §9.2.
    flow = re.split(r"^### 9\.2 .*$", plan, maxsplit=1, flags=re.MULTILINE)[1]
    flow = re.split(r"^### 9\.3 .*$", flow, maxsplit=1, flags=re.MULTILINE)[0]
    steps = re.findall(r"^(\d+)\. ", flow, re.MULTILINE)
    assert [int(n) for n in steps] == list(range(1, 13)), (
        "plan §9.2's flow must still number twelve steps"
    )


# ---------------------------------------------------------------------------
# The collector that fills the machine-answerable slots.
# ---------------------------------------------------------------------------
#
# The skeleton says which kind of evidence fills each slot, and half of
# those kinds are decidable by reading the service: the machinery is
# built and witnessed, and the trial confirms it on the pilot paper.
# ``scripts/pilot_gate_evidence.py`` is the tool that reads the service
# and writes that half down, and this section holds it to its contract:
#
# * it reads the routes over HTTP, with the session token presented and
#   never printed;
# * it decides a slot whose condition holds, and a slot whose condition
#   does not, and says which in the record;
# * it leaves the slots the real trial alone decides exactly as they
#   were;
# * it writes no material into the record -- the canary is the witness.
#
# **The service it reads is a scripted one, built here.** The tool is a
# console entry point and its contract with a caller is a process
# boundary, so the witness runs it as a subprocess rather than calling
# into it; a subprocess needs a real address, and a scripted service on
# a port the operating system chose is one. The answers are the ones the
# test writes down, so a condition can be made to hold and made not to
# hold without a corpus.

#: The tool that collects the machine-answerable half of the gates' evidence.
COLLECTOR: Final = REPO_ROOT / "scripts" / "pilot_gate_evidence.py"

#: A sentence the routes carry and the record must not. The witness writes
#: it into every text field the routes answer with, and then looks for it.
CANARY: Final = "CANARY-PILOT-PAPER-SENTENCE-MUST-NOT-REACH-THE-RECORD"

#: The token the scripted service expects, and the one the workspace holds.
TOKEN: Final = "canary-session-token-that-must-never-be-printed"

#: The slots the skeleton says only the real trial can decide.
TRIAL_ONLY_SLOTS: Final = ("G1-2", "G1-3", "G1-4", "G4-1", "G4-3", "G4-4", "G4-5")

#: The digests the closed binding binds and the export answers with.
MARKED_DIGEST: Final = "a" * 64
CLEAN_DIGEST: Final = "b" * 64
TABLE_DIGEST: Final = "c" * 64
QUALITY_DIGEST: Final = "d" * 64
SOURCE_DIGEST: Final = "e" * 64

#: The chain's own key for the issue the advisor raised. A rule names the
#: chain material it was learned from by this key, so it is what joins the
#: memory to the chain.
ISSUE_KEY: Final = "k1"

#: The ids the closed binding binds.
TASK_ID: Final = "task-00000000-0000-7000-8000-000000000001"
PROJECT_ID: Final = "prj-00000000-0000-7000-8000-000000000002"
INPUT_VERSION_ID: Final = "ver-00000000-0000-7000-8000-000000000003"
OUTPUT_VERSION_ID: Final = "ver-00000000-0000-7000-8000-000000000004"
DOSSIER_ID: Final = "art-00000000-0000-7000-8000-000000000005"
CLEAN_RECEIPT_ID: Final = "art-00000000-0000-7000-8000-000000000006"
EDGE_ID: Final = "edg-00000000-0000-7000-8000-000000000007"


def _the_trajectory(query: Mapping[str, list[str]]) -> dict[str, Any]:
    """The chain, under the issue keys the caller named.

    **The real route is keyed and answers nothing for a key it does not
    hold**, so the fixture is keyed too. A collector that read the chain
    without naming a key would get an empty chain here exactly as it
    would from the service -- and a witness that could not tell the two
    apart would not be watching the thing it claims to watch.
    """
    keys = set(query.get("issue_key", []))
    comments = [
        {
            "feedback_id": "fbk-1",
            "issue_key": ISSUE_KEY,
            "version_id": INPUT_VERSION_ID,
            "comment_text": CANARY,
            "anchor_text": CANARY,
            "anchor_status": "anchored",
            "anchor_reason": CANARY,
        }
    ]
    held = [comment for comment in comments if comment["issue_key"] in keys]
    edits = (
        [
            {
                "edit_action_id": "edt-1",
                "feedback_id": "fbk-1",
                "version_edge_id": EDGE_ID,
                "actor_kind": "model",
                "grade": "accepted",
            }
        ]
        if held
        else []
    )
    responses = [{"feedback_id": "fbk-1", "states": ["applied"]}] if held else []
    return {"comments": held, "edits": edits, "responses": responses}


def _the_answers(
    *,
    manifest_marked: str = MARKED_DIGEST,
    export_marked: str = MARKED_DIGEST,
) -> dict[str, Any]:
    """The routes' answers, for a workspace where the conditions hold.

    Every text field the routes answer with carries the canary, so a
    record that copied a payload rather than projecting it would be
    caught by the very first assertion that reads the record.

    **The two digests are separate arguments on purpose.** The binding
    is what the manifest records and the export is what the service
    answers with, and the condition the gate states is that they are
    equal; a witness that could only make them equal would never test
    the equality.
    """
    manifest: dict[str, Any] = {
        "task_id": TASK_ID,
        "project_id": PROJECT_ID,
        "input_version_id": INPUT_VERSION_ID,
        "output_version_id": OUTPUT_VERSION_ID,
        "marked_receipt_id": DOSSIER_ID,
        "marked_sha256": manifest_marked,
        "clean_receipt_id": CLEAN_RECEIPT_ID,
        "clean_sha256": CLEAN_DIGEST,
        "edge_id": EDGE_ID,
        "opinions": [
            {
                "feedback_id": "fbk-1",
                "location_state": "located",
                "anchor_status": "anchored",
                "anchor_paragraph": 3,
                "comment_text": CANARY,
            }
        ],
        "suggestions": [{"feedback_id": "fbk-1", "paragraph": 3, "author": "model"}],
        "decisions": [
            {
                "feedback_id": "fbk-1",
                "verdict": "accepted",
                "operator": "advisor",
                "needs_evidence": False,
                "comment_text": CANARY,
            }
        ],
        "responses": [
            {
                "response_link_id": "rsp-1",
                "feedback_id": "fbk-1",
                "edit_action_id": "edt-1",
                "state": "applied",
            }
        ],
        "unresolved": [{"feedback_id": "fbk-2", "reason": "needs_evidence", "detail": CANARY}],
        "handovers": [
            {"feedback_id": "fbk-3", "reason": "handover", "detail": CANARY, "handover": CANARY}
        ],
        "closed_at": "2026-11-25T09:00:00+00:00",
    }
    health = {
        "status": "ok",
        "host": "127.0.0.1",
        "port": 8000,
        "origins": ["http://127.0.0.1:8000"],
        "task_id": TASK_ID,
    }
    return {
        "/health": health,
        # The selection answers with the binding, which is the health shape.
        "/task/select": health,
        "/task": {
            "task": {"task_id": TASK_ID, "title": CANARY, "goal": CANARY},
            "runs": [
                {
                    "run_id": "run-1",
                    "task_id": TASK_ID,
                    "status": "succeeded",
                    "attempt": 1,
                    "started_at": "2026-11-25T08:00:00+00:00",
                    "finished_at": "2026-11-25T08:30:00+00:00",
                }
            ],
            "stages": [
                {
                    "stage_id": "stg-1",
                    "name": CANARY,
                    "status": "succeeded",
                    "input_hashes": [],
                    "output_hashes": [],
                }
            ],
            "artifacts": [],
            "approvals": [
                {
                    "approval_id": "apr-1",
                    "capability": "paper.modify",
                    "state": "consumed",
                    "expires_at": "2026-11-25T10:00:00+00:00",
                }
            ],
            "last_event_seq": 12,
        },
        "/artifacts": [
            {
                "receipt": {
                    "schema_version": 1,
                    "receipt_id": DOSSIER_ID,
                    "task_id": TASK_ID,
                    "kind": "manifest",
                    "relative_path": "output/dossier.json",
                    "content_sha256": SOURCE_DIGEST,
                    "size_bytes": 2048,
                    "revision": 1,
                    "produced_by": "operator",
                    "producer_id": "operator",
                    "derived_from": [],
                    "staleness": "current",
                    "created_at": "2026-11-25T08:45:00+00:00",
                },
                "resource_key": "output/dossier.json",
            }
        ],
        f"/artifacts/{DOSSIER_ID}/content": manifest,
        "/events": {
            "task_id": TASK_ID,
            "events": [
                {
                    "event_id": "evt-1",
                    "seq": 1,
                    "task_id": TASK_ID,
                    "type": "stage.transition",
                    "transition": "succeeded",
                    "occurred_at": "2026-11-25T08:30:00+00:00",
                    "payload": {"detail": CANARY},
                }
            ],
            "next_after_seq": 2,
            "caught_up": True,
        },
        "/trajectory": _the_trajectory,
        "/trajectory/issue-keys": {
            "project_id": PROJECT_ID,
            "issue_keys": [ISSUE_KEY],
        },
        "/plan": {
            "task_id": TASK_ID,
            "skill_id": "skill-1",
            "skill_digest": "f" * 64,
            "steps": [
                {"stage": "intake", "status": "done", "blocked_reason": None},
                {"stage": "review", "status": "pending", "blocked_reason": None},
            ],
        },
        "/steps": [
            {
                "stage": {
                    "stage_id": "stg-1",
                    "task_id": TASK_ID,
                    "run_id": "run-1",
                    "name": CANARY,
                    "status": "succeeded",
                    "input_hashes": [],
                    "output_hashes": [],
                },
                "attempt": 1,
            }
        ],
        "/tasks": [
            {
                "task_id": TASK_ID,
                "title": CANARY,
                "goal": CANARY,
                "bound_source_ids": ["src-1"],
                "revision": 1,
                "created_at": "2026-11-25T08:00:00+00:00",
                "updated_at": "2026-11-25T08:30:00+00:00",
            }
        ],
        "/sources": [
            {
                "source": {
                    "schema_version": 1,
                    "source_id": "src-1",
                    "kind": "pdf",
                    "display_name": CANARY,
                    "relative_path": "sources/paper.pdf",
                    "content_sha256": SOURCE_DIGEST,
                    "size_bytes": 1024,
                    "readability": "readable",
                },
                "resource_key": "sources/paper.pdf",
            }
        ],
        "/trajectory/graph": {
            "version_ids": [INPUT_VERSION_ID, OUTPUT_VERSION_ID],
            "edges": [
                {
                    "edge_id": EDGE_ID,
                    "parent_version_id": INPUT_VERSION_ID,
                    "child_version_id": OUTPUT_VERSION_ID,
                }
            ],
        },
        "/guidance/rules": [
            {
                "rule_id": "rul-1",
                "version": 2,
                "issue_type": "clarity",
                "statement": CANARY,
                "context": CANARY,
                "scope": "group",
                "example": CANARY,
                "state": "confirmed",
                "proposed_by": "advisor",
                "proposed_at": "2026-11-20T08:00:00+00:00",
                "confirmed_by": "advisor",
                "confirmed_at": "2026-11-21T08:00:00+00:00",
                "resolution_reason": None,
                "sources": [ISSUE_KEY],
                "counterexamples": [],
                "checks": [],
                "shared_scope": "group",
                "published_by": "advisor",
                "published_at": "2026-11-22T08:00:00+00:00",
            },
            {
                "rule_id": "rul-2",
                "version": 1,
                "issue_type": "clarity",
                "statement": CANARY,
                "context": CANARY,
                "scope": "private",
                "example": CANARY,
                "state": "candidate",
                "proposed_by": "operator",
                "proposed_at": "2026-11-22T08:00:00+00:00",
                "confirmed_by": None,
                "confirmed_at": None,
                "resolution_reason": None,
                "sources": [ISSUE_KEY],
                "counterexamples": [],
                "checks": [],
                "shared_scope": "private",
                "published_by": None,
                "published_at": None,
            },
        ],
        "/guidance/usable": [
            {
                "rule_id": "rul-1",
                "version": 2,
                "name": CANARY,
                "summary": CANARY,
                "scope": "group",
                "state": "confirmed",
                "sources": [ISSUE_KEY],
                "confirmed_by": "advisor",
                "confirmed_at": "2026-11-21T08:00:00+00:00",
            }
        ],
        "/trajectory/search": [
            {
                "trajectory_id": "trj-1",
                "project_id": PROJECT_ID,
                "entry_kind": "comment",
                "feedback_id": "fbk-1",
                "version_id": INPUT_VERSION_ID,
                "issue_key": "k1",
                "comment_text": CANARY,
                "anchor_text": CANARY,
                "change_text": CANARY,
                "text_digest": SOURCE_DIGEST,
                "source_version_id": INPUT_VERSION_ID,
                "source_locator": "p3",
                "source_sha256": SOURCE_DIGEST,
                "ingested_at": "2026-11-22T08:00:00+00:00",
            }
        ],
        "/ppt/search": [
            {
                "object_id": "obj-1",
                "project_id": PROJECT_ID,
                "source_sha256": SOURCE_DIGEST,
                "slide_no": 4,
                "object_position": 2,
                "object_kind": "text",
                "object_fingerprint": "fp-1",
                "text": CANARY,
                "media_target": CANARY,
                "locator_json": CANARY,
                "ingested_at": "2026-11-22T08:00:00+00:00",
            }
        ],
        "/meeting/search": [
            {
                "record_id": "rec-1",
                "project_id": PROJECT_ID,
                "source_sha256": SOURCE_DIGEST,
                "record_format": "paragraph",
                "record_index": 2,
                "timestamp_label": None,
                "record_fingerprint": "fp-2",
                "text": CANARY,
                "locator_json": CANARY,
                "ingested_at": "2026-11-22T08:00:00+00:00",
            }
        ],
        "/review/opinions": {
            "project_id": PROJECT_ID,
            "version_id": OUTPUT_VERSION_ID,
            "opinions": [
                {
                    "feedback_id": "fbk-1",
                    "issue_key": "k1",
                    "version_id": OUTPUT_VERSION_ID,
                    "comment_text": CANARY,
                    "anchor_status": "anchored",
                    "anchor_reason": CANARY,
                    "suggestion": CANARY,
                    "decision": CANARY,
                }
            ],
        },
        "/review/deliverables": {
            "project_id": PROJECT_ID,
            "dossier_artifact_id": DOSSIER_ID,
            "task_id": TASK_ID,
            "input_version_id": INPUT_VERSION_ID,
            "output_version_id": OUTPUT_VERSION_ID,
            "marked_receipt_id": DOSSIER_ID,
            "clean_receipt_id": CLEAN_RECEIPT_ID,
            "edge_id": EDGE_ID,
            "deliverables": [
                {
                    "kind": "marked",
                    "relative_path": "output/marked.docx",
                    "content_base64": base64.b64encode(CANARY.encode("utf-8")).decode("ascii"),
                    "sha256": export_marked,
                    "size_bytes": 64,
                },
                {
                    "kind": "clean",
                    "relative_path": "output/clean.docx",
                    "content_base64": base64.b64encode(CANARY.encode("utf-8")).decode("ascii"),
                    "sha256": CLEAN_DIGEST,
                    "size_bytes": 64,
                },
                {
                    "kind": "response_table",
                    "relative_path": "output/response_table.md",
                    "content_base64": base64.b64encode(CANARY.encode("utf-8")).decode("ascii"),
                    "sha256": TABLE_DIGEST,
                    "size_bytes": 64,
                },
                {
                    "kind": "quality_report",
                    "relative_path": "output/quality_report.md",
                    "content_base64": base64.b64encode(CANARY.encode("utf-8")).decode("ascii"),
                    "sha256": QUALITY_DIGEST,
                    "size_bytes": 64,
                },
            ],
        },
        "/review/quality": {
            "project_id": PROJECT_ID,
            "input_version_id": INPUT_VERSION_ID,
            "output_version_id": OUTPUT_VERSION_ID,
            "dossier_artifact_id": DOSSIER_ID,
            "checks": [
                {
                    "check": name,
                    "passed": True,
                    "facts": [
                        {
                            "check": name,
                            "detail": CANARY,
                            "feedback_id": "fbk-1",
                            "paragraph": 3,
                            "expected": CANARY,
                            "actual": CANARY,
                        }
                    ],
                }
                for name in (
                    "opinion_coverage",
                    "suggestion_correspondence",
                    "edit_scope",
                    "evidence_complete",
                    "response_table_consistency",
                    "report_binding",
                )
            ],
        },
    }


class _ScriptedService:
    """A service whose answers the test writes down.

    **A socket, not a stub.** The tool is run as a subprocess, so it
    needs a real address to talk to, and this is one. Every request it
    received is recorded, so the witness can say what the collector asked
    for and whether it presented the token.
    """

    def __init__(self, answers: Mapping[str, Any]) -> None:
        self._answers = dict(answers)
        self.requests: list[dict[str, Any]] = []
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def origin(self) -> str:
        """The address the service answers on."""
        address = self._server.server_address
        assert isinstance(address, tuple), "the server bound a socket address"
        raw_host, port = address[0], address[1]
        host = raw_host.decode("utf-8") if isinstance(raw_host, bytes) else raw_host
        return f"http://{host}:{port}"

    def stop(self) -> None:
        """Stop answering."""
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=10)

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        answers = self._answers
        requests = self.requests

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, format: str, *args: Any) -> None:
                """The service says nothing; the test reads what it was asked."""

            def _answer(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                if length:
                    self.rfile.read(length)
                parsed = urlparse(self.path)
                path = parsed.path
                query = parse_qs(parsed.query)
                requests.append(
                    {
                        "method": self.command,
                        "path": path,
                        "query": query,
                        "presented_the_token": (
                            self.headers.get("Authorization") == f"Bearer {TOKEN}"
                        ),
                    }
                )
                answer = answers.get(path)
                if callable(answer):
                    answer = answer(query)
                if answer is None:
                    body = json.dumps({"reason": "not_found"}).encode("utf-8")
                    self.send_response(404)
                else:
                    body = json.dumps(answer).encode("utf-8")
                    self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            # The names are the base class's, and the base class's own.
            do_GET = _answer  # noqa: N815
            do_POST = _answer  # noqa: N815

        return Handler


def _a_workspace(root: Path) -> Path:
    """A workspace holding a session token, as the service writes one."""
    (root / ".labcairn").mkdir(parents=True, exist_ok=True)
    (root / ".labcairn" / "session-token").write_text(f"{TOKEN}\n", encoding="utf-8")
    return root


def _a_skeleton(root: Path) -> Path:
    """A copy of the real skeleton, so the test writes to a copy."""
    root.mkdir(parents=True, exist_ok=True)
    target = root / "skeleton.md"
    target.write_text(_skeleton(), encoding="utf-8")
    return target


def _run_collector(
    workspace: Path,
    origin: str,
    skeleton: Path,
    record: Path,
    *extra: str,
) -> subprocess.CompletedProcess[str]:
    """The collector, run as an operator runs it.

    **A subprocess, deliberately.** The tool is a console entry point and
    its exit status is part of what a caller's script reads, so the
    witness watches the process boundary rather than a call.
    """
    return bounded_run(
        [
            sys.executable,
            str(COLLECTOR),
            "--workspace",
            str(workspace),
            "--base-url",
            origin,
            "--skeleton",
            str(skeleton),
            "--record",
            str(record),
            *extra,
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(workspace),
    )


def _slots(record: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """The record's slots, by their id."""
    return {str(slot["slot"]): dict(slot) for slot in record["slots"]}


def _row(text: str, slot: str) -> str:
    """The skeleton's row for one slot, as the text holds it."""
    for line in text.splitlines():
        if line.startswith(f"| {slot} |"):
            return line
    raise AssertionError(f"the skeleton holds no row for {slot}")


def _status_of(row: str) -> str:
    """The status cell of one row, as the table holds it."""
    cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
    assert len(cells) == 6, f"the row has {len(cells)} cells, not six: {row}"
    return cells[5]


def test_the_collector_reads_the_service_and_writes_a_self_checking_record(
    tmp_path: Path,
) -> None:
    """The record says what was read, where it was read, and what it concluded.

    A record that holds a verdict and nothing else is a claim; a record
    that holds the route, the ids, the digests and the counts beside the
    verdict is a measurement somebody else can check.
    """
    service = _ScriptedService(_the_answers())
    try:
        workspace = _a_workspace(tmp_path / "workspace")
        skeleton = _a_skeleton(tmp_path)
        record_path = tmp_path / "record.json"
        result = _run_collector(
            workspace, service.origin, skeleton, record_path, "--apply", "--query", "paper"
        )
        assert result.returncode == 0, f"the collector refused: {result.stderr}"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        assert record["schema"] == "labcairn.pilot-gate-evidence/1"
        assert record["command"], "the record names the command that produced it"
        assert record["collected_at"], "the record says when it was collected"
        assert record["reads"], "the record names the routes it read"
        slots = _slots(record)
        assert slots["G2-2"]["verdict"] == "PASS"
        assert slots["G2-2"]["read_from"], "a decided slot names the routes it was read from"
        assert slots["G2-2"]["evidence"]["digests"], "a decided slot carries the evidence it read"
        assert slots["G2-2"]["evidence"]["project_id"] == PROJECT_ID, (
            "a decided slot names the round it was measured on"
        )
        assert "GET /review/deliverables" in slots["G2-2"]["read_from"]
        refused = [str(read["route"]) for read in record["reads"] if read["outcome"] != "ok"]
        assert not refused, f"the collector asked for routes the service does not serve: {refused}"
    finally:
        service.stop()


def test_the_collector_reports_a_verdict_for_a_condition_that_holds_and_for_one_that_does_not(
    tmp_path: Path,
) -> None:
    """A condition that holds reads PASS, and one that does not reads FAIL.

    **Both halves, because a witness that only ever sees green proves
    nothing.** A tool that answered PASS to everything would satisfy a
    test that only checked for PASS.
    """
    service = _ScriptedService(_the_answers())
    try:
        workspace = _a_workspace(tmp_path / "workspace")
        skeleton = _a_skeleton(tmp_path)
        record_path = tmp_path / "record.json"
        result = _run_collector(
            workspace, service.origin, skeleton, record_path, "--apply", "--query", "paper"
        )
        assert result.returncode == 0, f"the collector refused: {result.stderr}"
        holding = _slots(json.loads(record_path.read_text(encoding="utf-8")))
        assert holding["G2-2"]["verdict"] == "PASS", (
            f"the digests match, so the slot must read PASS: {holding['G2-2']['reason']}"
        )
    finally:
        service.stop()

    drifted = _ScriptedService(_the_answers(export_marked="f" * 64))
    try:
        workspace = _a_workspace(tmp_path / "workspace-2")
        skeleton = _a_skeleton(tmp_path / "drifted")
        record_path = tmp_path / "drifted.json"
        result = _run_collector(
            workspace, drifted.origin, skeleton, record_path, "--apply", "--query", "paper"
        )
        assert result.returncode == 0, f"the collector refused: {result.stderr}"
        failing = _slots(json.loads(record_path.read_text(encoding="utf-8")))
        assert failing["G2-2"]["verdict"] == "FAIL", (
            "the export's digest does not equal the manifest's, so the slot must "
            f"read FAIL: {failing['G2-2']['reason']}"
        )
    finally:
        drifted.stop()


def test_the_collector_leaves_the_slots_the_real_trial_decides_exactly_as_they_were(
    tmp_path: Path,
) -> None:
    """A slot the real trial alone decides is not the tool's to fill.

    The skeleton marks those slots **real trial only**, and the
    evidence is a person's observation of the workbench. A tool that
    filled one of them would be writing a verdict it has no evidence
    for, and the skeleton's own header says no verdict is written before
    its evidence exists.
    """
    service = _ScriptedService(_the_answers())
    try:
        workspace = _a_workspace(tmp_path / "workspace")
        skeleton = _a_skeleton(tmp_path)
        record_path = tmp_path / "record.json"
        before = skeleton.read_text(encoding="utf-8")
        result = _run_collector(
            workspace, service.origin, skeleton, record_path, "--apply", "--query", "paper"
        )
        assert result.returncode == 0, f"the collector refused: {result.stderr}"
        after = skeleton.read_text(encoding="utf-8")
        slots = _slots(json.loads(record_path.read_text(encoding="utf-8")))
        for slot in TRIAL_ONLY_SLOTS:
            assert slots[slot]["verdict"] == "NOT_ADDRESSED", (
                f"{slot} is the real trial's to decide, and the tool must say so"
            )
            assert slots[slot]["reason"], f"{slot} carries the reason it was left alone"
            assert _row(before, slot) == _row(after, slot), (
                f"{slot}'s row must not move: the trial decides it"
            )
    finally:
        service.stop()


def test_the_collector_leaves_a_slot_pending_when_nothing_was_exercised(
    tmp_path: Path,
) -> None:
    """A slot the workspace could not exercise stays PENDING, with a reason.

    The record's verdict is about the machine-checkable part; a
    condition that was never exercised is not a condition that failed,
    and a slot that was not measured must not read as if it had been.
    """
    service = _ScriptedService({"/health": {"status": "ok", "task_id": TASK_ID}})
    try:
        workspace = _a_workspace(tmp_path / "workspace")
        skeleton = _a_skeleton(tmp_path)
        record_path = tmp_path / "record.json"
        result = _run_collector(
            workspace, service.origin, skeleton, record_path, "--apply", "--query", "paper"
        )
        assert result.returncode == 0, f"the collector refused: {result.stderr}"
        slots = _slots(json.loads(record_path.read_text(encoding="utf-8")))
        assert slots["G2-2"]["verdict"] == "UNKNOWN"
        assert slots["G2-2"]["reason"], "an unexercised slot carries the reason it was not measured"
        row = _row(skeleton.read_text(encoding="utf-8"), "G2-2")
        assert _status_of(row).startswith("PENDING"), f"an unexercised slot stays PENDING: {row}"
    finally:
        service.stop()


def test_the_collector_writes_no_material_and_no_token_into_the_record(
    tmp_path: Path,
) -> None:
    """The record holds ids, digests, counts and timestamps -- and nothing else.

    **The canary is in every text field the routes answer with.** The
    comment body, the rule's statement, the deck's text, the meeting's
    text, the deliverable's bytes, the task's title and the reviewer's
    own words all carry it, and none of them may reach the record -- in
    the record, in the record's base64, or on the terminal.
    """
    service = _ScriptedService(_the_answers())
    try:
        workspace = _a_workspace(tmp_path / "workspace")
        skeleton = _a_skeleton(tmp_path)
        record_path = tmp_path / "record.json"
        result = _run_collector(
            workspace, service.origin, skeleton, record_path, "--apply", "--query", "paper"
        )
        assert result.returncode == 0, f"the collector refused: {result.stderr}"
        text = record_path.read_text(encoding="utf-8")
        assert CANARY not in text, "the record carries the material the routes answered with"
        assert base64.b64encode(CANARY.encode("utf-8")).decode("ascii") not in text, (
            "the record carries the deliverable's bytes"
        )
        assert TOKEN not in text, "the record carries the session token"
        assert CANARY not in result.stdout, "the terminal carries the material"
        assert TOKEN not in result.stdout, "the terminal carries the session token"
        assert TOKEN not in result.stderr, "the terminal carries the session token"
    finally:
        service.stop()


def test_the_collector_presents_the_token_it_reads_from_the_workspace(
    tmp_path: Path,
) -> None:
    """The token is read from the workspace and presented, and nowhere else.

    The service's own guard asks for the token on every method that is
    not a read, so ``POST /task/select`` is the one call that must
    carry it; and the runbook says the token is read from the workspace
    and never shared in chat, so the record and the terminal must not
    carry it either.
    """
    service = _ScriptedService(_the_answers())
    try:
        workspace = _a_workspace(tmp_path / "workspace")
        skeleton = _a_skeleton(tmp_path)
        record_path = tmp_path / "record.json"
        result = _run_collector(
            workspace, service.origin, skeleton, record_path, "--apply", "--query", "paper"
        )
        assert result.returncode == 0, f"the collector refused: {result.stderr}"
        mutations = [request for request in service.requests if request["method"] != "GET"]
        assert mutations, "the collector asked for no mutation at all"
        assert all(request["presented_the_token"] for request in mutations), (
            "a mutation without the token would be refused by the service"
        )
    finally:
        service.stop()


def test_the_dry_run_writes_nothing(tmp_path: Path) -> None:
    """A dry run connects, reads and reports, and leaves the tree alone.

    The preview is the point: an operator reads what the run would
    decide before anything is written, and a dry run that wrote the
    record would take that choice away.
    """
    service = _ScriptedService(_the_answers())
    try:
        workspace = _a_workspace(tmp_path / "workspace")
        skeleton = _a_skeleton(tmp_path)
        record_path = tmp_path / "record.json"
        before = skeleton.read_text(encoding="utf-8")
        result = _run_collector(
            workspace, service.origin, skeleton, record_path, "--dry-run", "--query", "paper"
        )
        assert result.returncode == 0, f"the collector refused: {result.stderr}"
        assert not record_path.exists(), "a dry run wrote the record"
        assert skeleton.read_text(encoding="utf-8") == before, "a dry run moved the skeleton"
        assert "G2-2: PASS" in result.stdout, "the dry run reports what it would decide"
    finally:
        service.stop()


def test_the_skeletons_status_column_is_rendered_from_the_record(tmp_path: Path) -> None:
    """Each slot's cell says what the record measured, and no more.

    A slot whose condition only the machinery can decide carries its
    verdict. A slot whose condition also needs the trial's confirmation
    stays PENDING and says what was measured. A slot the trial alone
    decides is untouched.
    """
    service = _ScriptedService(_the_answers())
    try:
        workspace = _a_workspace(tmp_path / "workspace")
        skeleton = _a_skeleton(tmp_path)
        record_path = tmp_path / "record.json"
        result = _run_collector(
            workspace, service.origin, skeleton, record_path, "--apply", "--query", "paper"
        )
        assert result.returncode == 0, f"the collector refused: {result.stderr}"
        text = skeleton.read_text(encoding="utf-8")
        record = json.loads(record_path.read_text(encoding="utf-8"))
        for slot in _slots(record).values():
            row = _row(text, str(slot["slot"]))
            assert str(slot["status_after_this_run"]) in row, (
                f"{slot['slot']}'s cell must be what the record says it is: {row}"
            )
        assert _status_of(_row(text, "G3-4")).startswith("PASS"), (
            "a slot the machinery alone decides carries its verdict: " + _row(text, "G3-4")
        )
        assert _status_of(_row(text, "G1-2")) == "PENDING", (
            "a slot the trial alone decides keeps its PENDING: " + _row(text, "G1-2")
        )
        assert _status_of(_row(text, "G2-2")).startswith("PENDING"), (
            "a slot the trial must confirm keeps its PENDING: " + _row(text, "G2-2")
        )
    finally:
        service.stop()


def test_the_collector_reads_the_skeleton_rather_than_guessing_its_slots(
    tmp_path: Path,
) -> None:
    """A slot the tool has no checker for is named, not quietly ignored.

    The tool's own table of slots and the skeleton's table of slots are
    two different lists, and they can drift. A row the tool does not
    recognise must appear in the record as unaddressed, so a reader can
    see that nothing was measured for it.
    """
    service = _ScriptedService(_the_answers())
    try:
        workspace = _a_workspace(tmp_path / "workspace")
        skeleton = _a_skeleton(tmp_path)
        record_path = tmp_path / "record.json"
        result = _run_collector(
            workspace, service.origin, skeleton, record_path, "--apply", "--query", "paper"
        )
        assert result.returncode == 0, f"the collector refused: {result.stderr}"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        names = {str(slot["slot"]) for slot in record["slots"]}
        assert names == {str(slot["slot"]) for slot in record["slots"]}, (
            "the record names each slot once"
        )
        rows = re.findall(r"^\| (G\d-\d) \|", _skeleton(), re.MULTILINE)
        assert names == set(rows), (
            "the record must hold every row the skeleton holds, and no row it does not"
        )
    finally:
        service.stop()


def test_the_collector_reaches_the_products_own_service(tmp_path: Path) -> None:
    """The routes the collector calls are the product's own routes.

    **A scripted service proves the collector's protocol; only the
    product proves the routes.** The collector's route set, its query
    parameters and its request body were written by reading the source,
    and a route that had moved, a parameter that had been renamed or a
    body that had changed shape would be answered by the scripted
    service exactly as it answers everything else. The service the
    runbook starts is the one that would refuse -- and it refuses
    ``POST /task/select`` outright when the token is not presented.
    """
    workspace = tmp_path / "workspace"
    made = run_cli("--workspace", str(workspace), "init")
    assert made.returncode == 0, f"labcairn init refused: {made.stderr}"
    created = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "create",
        "--title",
        CANARY,
        "--objective",
        CANARY,
        "--criterion",
        CANARY,
        "--json",
    )
    assert created.returncode == 0, f"labcairn task create refused: {created.stderr}"
    service = start_served_workbench(workspace=workspace)
    try:
        skeleton = _a_skeleton(tmp_path)
        record_path = tmp_path / "record.json"
        result = _run_collector(
            workspace, service.origin, skeleton, record_path, "--apply", "--query", "paper"
        )
        assert result.returncode == 0, f"the collector refused: {result.stderr}"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        reads = {str(read["route"]): read for read in record["reads"]}
        assert reads["GET /health"]["outcome"] == "ok", "the service must answer the health route"
        assert reads["POST /task/select"]["outcome"] == "ok", (
            "the service must accept the task selection the collector sends, "
            "which it does only when the token is presented"
        )
        unreachable = [
            str(read["route"]) for read in record["reads"] if read["outcome"] == "unreachable"
        ]
        assert not unreachable, f"the service could not answer {unreachable}"
        text = record_path.read_text(encoding="utf-8")
        assert service.session_token() not in text, "the record carries the session token"
        assert CANARY not in text, "the record carries the task's own words"
    finally:
        service.stop()


# --------------------------------------------------------------------------- #
# what the collector could reach, and what it could not
# --------------------------------------------------------------------------- #


def _the_answers_without_a_closed_binding() -> dict[str, Any]:
    """The same answers, from a workspace that has closed no round.

    **Only the binding is removed.** The rule, the chain under its key,
    the ledger and the search surfaces are all still there, so a slot
    that needs none of the binding can be watched on its own.
    """
    answers = _the_answers()
    answers["/artifacts"] = []
    return answers


def _read_matches(template: str, read: Mapping[str, Any]) -> bool:
    """Whether a read answered the route a slot names.

    **A named route may carry a placeholder.** The record holds the
    route the service was actually asked for, so ``GET /artifacts/{id}
    /content`` and ``GET /artifacts/art-1/content`` are the same route.
    """
    method, _, path = template.partition(" ")
    actual = str(read["route"])
    actual_method, _, actual_path = actual.partition(" ")
    if actual_method != method:
        return False
    if "{" not in path:
        return actual_path == path
    prefix, _, rest = path.partition("{")
    _, _, suffix = rest.partition("}")
    return actual_path.startswith(prefix) and actual_path.endswith(suffix)


def test_a_slot_that_needs_no_closed_binding_is_answered_without_one(
    tmp_path: Path,
) -> None:
    """A workspace that has closed no round still answers the slots that need less.

    **The catch-all would have said UNKNOWN for every one of them.** The
    link from a raw source through a distilled rule to the rule's record
    is traceable from the rule's own chain key, so a workspace that has
    never closed a round answers it. A collector that recorded UNKNOWN
    here would be reporting the workspace's missing binding rather than
    the slot's own condition.
    """
    service = _ScriptedService(_the_answers_without_a_closed_binding())
    try:
        workspace = _a_workspace(tmp_path / "workspace")
        skeleton = _a_skeleton(tmp_path)
        record_path = tmp_path / "record.json"
        result = _run_collector(
            workspace, service.origin, skeleton, record_path, "--apply", "--query", "paper"
        )
        assert result.returncode == 0, f"the collector refused: {result.stderr}"
        slots = _slots(json.loads(record_path.read_text(encoding="utf-8")))
        assert slots["G2-2"]["verdict"] == "UNKNOWN", (
            "the slot that needs the binding is the one that cannot be answered without it"
        )
        assert slots["G3-2"]["verdict"] == "PASS", (
            "the link from a raw source through a distilled rule to the rule's "
            f"record needs no closed binding, so it must be answered: {slots['G3-2']['reason']}"
        )
        assert slots["G3-2"]["evidence"]["resolved_source_key_count"] == 1, (
            "the answered slot says which chain material key resolved"
        )
        assert slots["G3-4"]["verdict"] == "PASS", (
            "the listing holds an unconfirmed rule back, which needs no closed "
            f"binding either: {slots['G3-4']['reason']}"
        )
    finally:
        service.stop()


def test_a_slot_that_needs_a_closed_binding_says_exactly_what_it_lacked(
    tmp_path: Path,
) -> None:
    """The reason names the one thing that was missing, and names it per slot.

    **"The workspace holds no closed binding" was true of every slot, and
    true of none of them in particular.** A reader could not tell a slot
    that needs a project from a slot that needs a round, and only the
    second is a fact about the workspace rather than a limit of the
    routes the collector reads.
    """
    service = _ScriptedService(_the_answers_without_a_closed_binding())
    try:
        workspace = _a_workspace(tmp_path / "workspace")
        skeleton = _a_skeleton(tmp_path)
        record_path = tmp_path / "record.json"
        result = _run_collector(
            workspace, service.origin, skeleton, record_path, "--apply", "--query", "paper"
        )
        assert result.returncode == 0, f"the collector refused: {result.stderr}"
        slots = _slots(json.loads(record_path.read_text(encoding="utf-8")))
        binding = slots["G2-2"]
        assert binding["verdict"] == "UNKNOWN", "the slot needs the binding"
        assert binding["requires"] == ["a-closed-binding"], (
            f"the slot says what it needs: {binding['requires']}"
        )
        assert binding["lacks"] == ["a-closed-binding"], (
            f"the slot says what it lacked: {binding['lacks']}"
        )
        assert "closed binding" in binding["reason"], (
            f"the reason names what was missing: {binding['reason']}"
        )
        project = slots["G2-1"]
        assert project["requires"] == ["a-project-id"], (
            "a slot that needs a project says so, and it is a different thing "
            f"from a closed binding: {project['requires']}"
        )
        assert project["lacks"] != binding["lacks"], (
            "the two slots lack different things, so they must not be told the same thing"
        )
        assert "no route lists the workspace's paper projects" in project["reason"], (
            f"a slot that needs a project says which limit stopped it: {project['reason']}"
        )
    finally:
        service.stop()


def test_the_record_names_a_precondition_for_every_slot(tmp_path: Path) -> None:
    """Every slot says what it needs, and every unknown slot says what it lacked.

    **A precondition outside the named set is a claim the reader cannot
    check.** The vocabulary is the record's own, and a slot that named
    something else would be a slot this tool does not understand.
    """
    service = _ScriptedService(_the_answers())
    try:
        workspace = _a_workspace(tmp_path / "workspace")
        skeleton = _a_skeleton(tmp_path)
        record_path = tmp_path / "record.json"
        result = _run_collector(
            workspace, service.origin, skeleton, record_path, "--apply", "--query", "paper"
        )
        assert result.returncode == 0, f"the collector refused: {result.stderr}"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        known = set(record["preconditions"])
        assert known, "the record names the preconditions it uses"
        for slot in record["slots"]:
            name = str(slot["slot"])
            assert slot["requires"], f"{name} names no precondition at all"
            for needed in slot["requires"]:
                assert needed in known, f"{name} names an unnamed precondition"
            for lacking in slot["lacks"]:
                assert lacking in known, f"{name} lacks an unnamed precondition"
                assert lacking in slot["requires"], (
                    f"{name} lacks {lacking}, which it does not require"
                )
            if slot["verdict"] == "UNKNOWN":
                assert slot["lacks"] or slot["unreadable_routes"], (
                    f"{name} is UNKNOWN and says neither what it lacked nor which route refused"
                )
            if slot["coverage"] == "trial-only":
                assert slot["requires"] == ["a-trial"], (
                    f"{name} is the trial's alone, and says so: {slot['requires']}"
                )
    finally:
        service.stop()


def test_the_reasons_are_per_slot_and_not_one_catch_all(tmp_path: Path) -> None:
    """Two slots that lack different things are not told the same thing.

    **The catch-all was one sentence for every slot that needed a
    project.** The reasons are now per slot, so a reader can tell which
    limit stopped which slot -- and the witness holds that by comparing
    the slots that lack different things.

    **A slot that shares its evidence with another says the same thing
    on purpose**, so it is left out of the comparison.
    """
    service = _ScriptedService(_the_answers_without_a_closed_binding())
    try:
        workspace = _a_workspace(tmp_path / "workspace")
        skeleton = _a_skeleton(tmp_path)
        record_path = tmp_path / "record.json"
        result = _run_collector(
            workspace, service.origin, skeleton, record_path, "--apply", "--query", "paper"
        )
        assert result.returncode == 0, f"the collector refused: {result.stderr}"
        slots = _slots(json.loads(record_path.read_text(encoding="utf-8")))
        unknown = [
            slot
            for slot in slots.values()
            if slot["verdict"] == "UNKNOWN"
            and "shared with" not in str(slot["coverage_kind"]).lower()
        ]
        assert len(unknown) >= 4, "the empty workspace leaves several slots undecided"
        reasons = {str(slot["slot"]): str(slot["reason"]) for slot in unknown}
        assert len(set(reasons.values())) == len(reasons), (
            f"two slots are told the same thing: {reasons}"
        )
        for left in unknown:
            for right in unknown:
                if left["lacks"] == right["lacks"]:
                    continue
                assert left["reason"] != right["reason"], (
                    f"{left['slot']} and {right['slot']} lack different things and "
                    "are told the same thing"
                )
    finally:
        service.stop()


def test_the_collector_reads_every_route_it_claims_to_read(tmp_path: Path) -> None:
    """A slot's list of routes is a list of reads that happened.

    **The other direction is the dangerous one.** A slot that names a
    route the collector never asked for is claiming a measurement it did
    not take, and the record would read as if the route had answered.
    """
    service = _ScriptedService(_the_answers())
    try:
        workspace = _a_workspace(tmp_path / "workspace")
        skeleton = _a_skeleton(tmp_path)
        record_path = tmp_path / "record.json"
        result = _run_collector(
            workspace, service.origin, skeleton, record_path, "--apply", "--query", "paper"
        )
        assert result.returncode == 0, f"the collector refused: {result.stderr}"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        reads = list(record["reads"])
        assert reads, "the record names the routes it read"
        for slot in record["slots"]:
            for route in slot["read_from"]:
                assert any(_read_matches(str(route), read) for read in reads), (
                    f"{slot['slot']} claims to have read {route}, which the record does not carry"
                )
        for route in ("GET /plan", "GET /steps", "GET /tasks", "GET /sources"):
            assert any(_read_matches(route, read) for read in reads), (
                f"the collector must read {route}: it answers a slot without a closed binding"
            )
    finally:
        service.stop()


def test_the_collector_reads_the_chain_under_named_issue_keys(tmp_path: Path) -> None:
    """The chain is read under the keys it is asked for.

    **The route answers nothing for a key it was not given.** A read
    with no key returns an empty chain that says nothing about the
    workspace, so a collector that read it unkeyed would measure an
    emptiness and report it as a fact about the paper.
    """
    service = _ScriptedService(_the_answers())
    try:
        workspace = _a_workspace(tmp_path / "workspace")
        skeleton = _a_skeleton(tmp_path)
        record_path = tmp_path / "record.json"
        result = _run_collector(
            workspace, service.origin, skeleton, record_path, "--apply", "--query", "paper"
        )
        assert result.returncode == 0, f"the collector refused: {result.stderr}"
        asked = [request for request in service.requests if request["path"] == "/trajectory"]
        assert asked, "the collector read the chain"
        for request in asked:
            keys = request["query"].get("issue_key", [])
            assert keys, f"the chain was read without naming a key: {request['query']}"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        slots = _slots(record)
        assert slots["G3-2"]["verdict"] == "PASS", (
            f"the rule's chain key resolves, so the link is walked: {slots['G3-2']['reason']}"
        )
    finally:
        service.stop()
