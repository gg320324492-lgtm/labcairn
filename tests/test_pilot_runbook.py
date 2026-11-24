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

import re
from pathlib import Path
from typing import Final, get_args

import pytest

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
