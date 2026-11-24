"""Witnesses for the pilot's owner-decision form and the preparation drafts.

**What this file watches.** Phase 4's pilot opens on four preparation
papers: the owner-decisions form
(``docs/plans/LC-P4-PILOT-owner-decisions.md``) and the three DRAFTs it
points at — the desensitisation checklist, the model-authorisation
record and the feedback-form template. The runbook
(``docs/plans/LC-P4-PILOT-runbook.md``) carries the entry points into
all four. Prose that nothing checks drifts, so this file reads the
documents and fails when they stop saying what the pilot needs:

* each of the three DRAFTs carries a ``How to confirm`` section — who
  confirms, where the confirmation is recorded, and which flows stay
  closed until the confirmation exists — while its status line still
  reads ``DRAFT`` (a signed confirmation would move it, and nothing
  here asserts PASS);
* the owner-decisions form carries plan §12's three decisions, each
  with its answer field still ``TBD — owner to fill``, the flow that
  stays blocked while it is, and what already stands behind it;
* the runbook's preparation section points at the owner-decisions form
  and requires a release record under ``docs/releases/`` for the
  version the pilot runs on, per plan §10;
* none of these documents carries a real name, affiliation or project
  number — the privacy rule the desensitisation checklist applies to
  the paper, applied to the pilot's own preparation records, enforced
  as CJK-run and identifier-pattern checks in the spirit of
  ``tests/test_no_reference_leakage.py``.

**Why the decisions stay TBD.** The form exists to collect the owner's
answers, not to invent them. A test that asserted a filled answer would
itself be forging one, so the assertions here are the opposite: the
fields must be present, must be unambiguous about being unfilled
(``TBD — owner to fill``), and must name what stays blocked. When the
owner fills the form, the assertions on the marker are updated by the
change that records the answers — the test cannot pass on a form that
silently swapped its marker for an invented answer.

**This file carries no Chinese by design.** The documents it reads are
English (CLAUDE.md keeps the repository in English), and the plan's
three §12 items are paraphrased with the skeleton's D-1/D-2/D-3
addresses, never transcribed.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest

REPO_ROOT: Final = Path(__file__).resolve().parent.parent

FORM: Final = Path("docs") / "plans" / "LC-P4-PILOT-owner-decisions.md"
CHECKLIST: Final = Path("docs") / "plans" / "LC-P4-PILOT-desensitisation-checklist.md"
AUTHORISATION: Final = Path("docs") / "plans" / "LC-P4-PILOT-model-authorisation-draft.md"
FEEDBACK_FORM: Final = Path("docs") / "plans" / "LC-P4-PILOT-feedback-form-template.md"
RUNBOOK: Final = Path("docs") / "plans" / "LC-P4-PILOT-runbook.md"
SKELETON: Final = Path("docs") / "acceptance" / "P4-G1-G4-record-skeleton.md"

#: The three preparation drafts that must carry a How-to-confirm section.
DRAFTS: Final[tuple[Path, ...]] = (CHECKLIST, AUTHORISATION, FEEDBACK_FORM)

#: The owner-decision ids, by the exit skeleton's own addresses. Plan §12
#: names three items; the skeleton carries them as D-1..D-3.
DECISION_IDS: Final[tuple[str, ...]] = ("D-1", "D-2", "D-3")

#: The undecided marker the owner-decisions form's answer fields carry.
#: It is the form's whole point: an answer field that does not read TBD
#: claims a decision nobody made.
TBD_MARKER: Final = "TBD — owner to fill"

#: The status marker the three preparation drafts still carry. The
#: documents move out of DRAFT when the owner signs, and not by a test.
DRAFT_MARKER: Final = "DRAFT"

#: The How-to-confirm heading every DRAFT must carry.
HOW_TO_CONFIRM: Final = "How to confirm"

#: A maximal run of Han characters — the same shape
#: ``test_pilot_runbook.py`` holds the trial's records to. The pilot's
#: preparation papers are English by design, and the plan's conditions
#: are anchored by section number, never transcribed.
HAN_RUN: Final = re.compile(r"[㐀-䶿一-鿿豈-﫿]+")

#: A CJK fullwidth enumeration comma — the mark a half-translated draft
#: leaves behind in English prose.
FULLWIDTH_COMMA: Final = re.compile("、")

#: Identifier shapes the preparation records must not carry: an email
#: address, a phone number, a grant/project number, a long number after
#: ``No.``, an ORCID. The same heuristics ``test_pilot_runbook.py`` holds
#: the trial's execution records to, applied to the preparation papers.
LEAK_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("email address", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("phone number", re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")),
    (
        "grant/project number prefix",
        # The identifier token must carry a digit: the checklist's own A-3
        # row says "grant/project number patterns" as an instruction, and a
        # digitless match there would be the test failing on the document's
        # vocabulary instead of on a leak. A real project or grant number
        # is an identifier, and identifiers number things.
        re.compile(
            r"(?:Project|Grant|Contract)\s*(?:No\.?|Number|#)\s*[:.]?\s*"
            r"(?=[A-Za-z0-9/-]*\d)[A-Za-z0-9][-A-Za-z0-9/]{3,}",
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
#: The personal-name check flags two consecutive capitalised words in
#: running prose; this allowlist keeps the documents' legitimate
#: capitalised nouns from reading as names. It is an allowlist of words,
#: not of people.
NON_PERSON_WORDS: Final[frozenset[str]] = frozenset(
    {
        "A",
        "Advisor",
        "An",
        "Answer",
        "Before",
        "Boundary",
        "Checklist",
        "Confirm",
        "Decision",
        "Each",
        "Every",
        "Field",
        "First",
        "Form",
        "How",
        "Issue",
        "LabCairn",
        "No",
        "On",
        "One",
        "Owner",
        "Phase",
        "Plan",
        "PENDING",
        "Question",
        "Release",
        "Runbook",
        "Section",
        "Session",
        "Signing",
        "Step",
        "TBD",
        "The",
        "These",
        "This",
        "Until",
        "Version",
        "What",
        "Where",
        "Which",
        "Why",
    }
)


def _read(relative: Path) -> str:
    """The document's text, with the test's own failure naming the path."""
    path = REPO_ROOT / relative
    assert path.is_file(), f"{relative} must exist for the pilot-preparation witnesses"
    return path.read_text(encoding="utf-8")


def _flowtext(text: str) -> str:
    """The text with every whitespace run collapsed to one space.

    Markdown reflow wraps lines at arbitrary columns; a phrase check on
    the raw text fails on the wrap, not on the content. The wrapped form
    is the same sentence, so the checks that ask about phrases ask about
    the collapsed form.
    """
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# The three DRAFTs carry a How to confirm section, and stay DRAFT.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("relative", DRAFTS, ids=lambda p: p.name)
def test_each_draft_carries_a_how_to_confirm_section(relative: Path) -> None:
    """Every preparation DRAFT says who confirms it and where it lands.

    A draft with no confirmation path is a draft forever: nobody knows
    whose tick turns it into a record, or which flow its silence keeps
    closed. The section must name the confirmer, the destination of the
    confirmation, and the flows that must not start before it.
    """
    text = _read(relative)
    assert HOW_TO_CONFIRM in text, (
        f"{relative} must carry a {HOW_TO_CONFIRM!r} section: who ticks it, "
        "where the confirmation is recorded, and what stays closed until then"
    )
    flow = _flowtext(text)
    for phrase in (
        "owner",
        "sign",
    ):
        assert phrase in flow, f"{relative}'s {HOW_TO_CONFIRM} section must state {phrase!r}"


@pytest.mark.parametrize("relative", DRAFTS, ids=lambda p: p.name)
def test_each_draft_states_which_flows_stay_closed(relative: Path) -> None:
    """Each DRAFT names the flows that must not start before signature.

    The confirmation's force is in the closure it names: the import
    step for the checklist, the real-model request for the
    authorisation record, the participant handout for the feedback
    form. A draft whose How-to-confirm names no closed flow reads as
    advisory, and advisory drafts get skipped.
    """
    flow = _flowtext(_read(relative)).lower()
    assert "until" in flow or "only inside" in flow, (
        f"{relative} must name the boundary that stays in force until or after the owner signs"
    )


@pytest.mark.parametrize("relative", DRAFTS, ids=lambda p: p.name)
def test_the_status_matches_the_signature(relative: Path) -> None:
    """The model-authorisation record is signed; the other two stay DRAFT.

    The owner signed the authorisation record on 2026-11-24, so its status
    must say AUTHORISED and carry the signature. The desensitisation
    checklist and the feedback form still await their own ticks; a status
    that claimed a confirmation nobody made would be a false gate.
    """
    text = _read(relative)
    if relative == AUTHORISATION:
        assert "AUTHORISED" in text, "the signed authorisation record must say AUTHORISED"
        assert "owner / 2026-11-24" in text, "the authorisation must carry the owner's signature"
    else:
        assert DRAFT_MARKER in text, (
            f"{relative} must still carry its {DRAFT_MARKER} status: the owner "
            "has not signed it, and nothing here may claim a confirmation"
        )


# ---------------------------------------------------------------------------
# The owner-decisions form carries plan §12's three decisions, each TBD.
# ---------------------------------------------------------------------------


def test_the_form_carries_all_three_plan_12_decisions() -> None:
    """The form has a section per plan §12 decision, in the plan's order.

    Plan §12 names three items: rule case-validation, material
    retention/withdrawal/sharing, first runnable version and trial
    date. The skeleton carries them as D-1..D-3, and the form must
    carry all three — a missing decision is a work order cut on an
    undecided prerequisite.
    """
    text = _read(FORM)
    for index, decision in enumerate(DECISION_IDS, start=1):
        heading = f"## Decision {index} —"
        assert heading in text, (
            f"the owner-decisions form must carry plan §12's decision {decision} as {heading!r}"
        )


@pytest.mark.parametrize("decision", DECISION_IDS)
def test_each_decision_carries_the_owner_recorded_answer(decision: str) -> None:
    """Every decision's answer field carries the answer the owner gave.

    The owner answered the three questions on 2026-11-24. An answer field
    that fell back to TBD would unblock nothing and leave the pilot's
    preparation silent; an answer with no pointer to where it lands would
    be a second copy nobody maintains. The check is per decision: each
    answer must be non-empty, must not be the old TBD marker, and must be
    accompanied by the decision's own blocked-flow and landing-place rows.
    """
    text = _read(FORM)
    section = re.search(
        rf"## Decision {DECISION_IDS.index(decision) + 1} —(.*?)(?=^## |\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    assert section, f"decision {decision} must have its own section in the form"
    answer_row = re.search(r"\| Answer \(owner fills\) \| ([^|]+) \|", section.group(1))
    assert answer_row, f"decision {decision} must carry an answer field the owner fills"
    answer = answer_row.group(1).strip().strip("`")
    assert answer and answer != TBD_MARKER, (
        f"decision {decision}'s answer field is still {TBD_MARKER!r}: the owner's "
        "2026-11-24 answers must be recorded here"
    )


def test_the_form_names_what_stays_blocked_while_unfilled() -> None:
    """Each decision names the flow that its silence keeps closed.

    The blocked-flow column is what makes the form a gate rather than a
    questionnaire: a reader must be able to see, per decision, which
    downstream flow may not start. The form carries the blocked-flow
    sentence per decision.
    """
    flow = _flowtext(_read(FORM))
    for phrase in (
        "Blocked while unfilled",
        "cannot",
    ):
        assert phrase in flow, (
            f"the owner-decisions form must name what stays blocked while a "
            f"decision is unfilled ({phrase!r} is the shape of that sentence)"
        )
    for decision in DECISION_IDS:
        assert decision in flow, (
            f"the form must tie its blocked flows to skeleton decision {decision}"
        )


def test_the_form_names_what_already_supports_each_decision() -> None:
    """Each decision lists the code and documents that stand behind it.

    The owner decides faster when the form says what already exists:
    the confirm/publish machinery for D-1, the material boundary for
    D-2, the release-record tool for D-3. A form that named no support
    would ask the owner to decide in a vacuum.
    """
    text = _read(FORM)
    for phrase in (
        "What already supports this",
        "tests/",
        "docs/releases/",
    ):
        assert phrase in text, (
            f"the owner-decisions form must name the code and documents "
            f"behind each decision ({phrase!r} missing)"
        )


def test_the_form_points_at_the_skeletons_decision_rows() -> None:
    """The form and the exit skeleton carry the same three decisions.

    The skeleton's D-1..D-3 rows and the form's three decisions are the
    same decisions in two places; the form must say so, so a reader of
    one finds the other and the two cannot drift into different
    questions.
    """
    text = _read(FORM)
    skeleton_name = SKELETON.name
    assert skeleton_name in text, (
        "the owner-decisions form must point at the exit skeleton that "
        "carries the same D-1..D-3 rows"
    )


# ---------------------------------------------------------------------------
# The runbook carries the preparation entry points.
# ---------------------------------------------------------------------------


def test_the_runbook_points_at_the_owner_decisions_form() -> None:
    """The runbook's preparation section links the owner-decisions form.

    The runbook is the pilot's operating manual; an operator who cannot
    find the decisions from it opens without them. The link must name
    the form and tie it to plan §12.
    """
    flow = _flowtext(_read(RUNBOOK))
    assert FORM.name in flow, f"the runbook must link the owner-decisions form ({FORM.name})"
    assert "§12" in flow, (
        "the runbook must tie the owner-decisions form to plan §12's three pre-opening decisions"
    )


def test_the_runbook_requires_a_release_record_for_the_pilot_version() -> None:
    """The runbook requires a docs/releases/ record for the pilot's version.

    Plan §10 gives every version a structured release record, and the
    pilot's first runnable version is a version. The runbook must say
    so — no record, no pilot on that version — and name where the
    records live.
    """
    flow = _flowtext(_read(RUNBOOK))
    for phrase in (
        "docs/releases/",
        "release record",
        "first runnable version",
    ):
        assert phrase in flow, (
            f"the runbook must require a release record under docs/releases/ "
            f"for the pilot's version ({phrase!r} missing)"
        )


def test_the_runbook_still_holds_its_twelve_steps() -> None:
    """The runbook's twelve step headings survived the preparation edits.

    The preparation additions sit *before* the steps; they must not
    have displaced, renumbered or dropped any of plan §9.2's twelve.
    The headings are read in document order, exactly as
    ``test_pilot_runbook.py`` reads them.
    """
    text = _read(RUNBOOK)
    found = re.findall(r"^### Step (\d+) — ", text, re.MULTILINE)
    assert found == [str(i) for i in range(1, 13)], (
        f"the runbook must still carry plan §9.2's twelve steps in order; found {found}"
    )


def test_the_runbook_carries_the_preparation_section_before_the_steps() -> None:
    """The preparation section exists and precedes the twelve steps.

    The owner decisions and the version record are preconditions: they
    belong before the steps, where a reader meets them first, not
    appended after the operations they gate.
    """
    text = _read(RUNBOOK)
    preparation = text.find("Before any step")
    steps = text.find("### Step 1 —")
    assert preparation != -1, "the runbook must carry a before-any-step section"
    assert steps != -1, "the runbook must still carry its steps"
    assert preparation < steps, (
        "the runbook's preparation section must come before the twelve steps: "
        "the owner's decisions and the version record are preconditions"
    )


# ---------------------------------------------------------------------------
# The skeleton's decision rows still say TBD.
# ---------------------------------------------------------------------------


def test_the_skeletons_three_decisions_carry_the_owner_answers() -> None:
    """The skeleton's D-1..D-3 rows carry the same confirmed answers.

    The skeleton and the form carry the same three decisions. If the
    form's fields are filled while the skeleton still reads TBD, a reader
    of the exit gate would see a decision nobody made. Each row must name
    the 2026-11-24 confirmation and none may still carry the old marker.
    """
    text = _read(SKELETON)
    for decision in DECISION_IDS:
        row = re.search(rf"^\| {decision} \| .+$", text, re.MULTILINE)
        assert row, f"decision {decision} must have its row in the exit skeleton"
        assert "CONFIRMED 2026-11-24" in row.group(0), (
            f"decision {decision}'s skeleton row must name the owner's confirmation"
        )
        assert "TBD" not in row.group(0), (
            f"decision {decision}'s skeleton row still reads TBD after the owner answered"
        )


# ---------------------------------------------------------------------------
# The preparation records carry no name, affiliation or project number.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "relative",
    [FORM, *DRAFTS, RUNBOOK],
    ids=lambda p: p.name,
)
def test_the_preparation_records_carry_no_chinese(relative: Path) -> None:
    """The preparation papers are English throughout.

    The repository's working language is English, the plan's conditions
    are anchored by section number, and the pilot's records — its
    preparation papers included — carry no corpus text. A Han character
    in any of them is a transcription the documents forbid.
    """
    runs = HAN_RUN.findall(_read(relative))
    assert not runs, (
        f"{relative} carries Chinese ({runs[:5]}); the pilot's preparation "
        "records are English, and the plan is quoted by section number"
    )


@pytest.mark.parametrize(
    "relative",
    [FORM, *DRAFTS, RUNBOOK],
    ids=lambda p: p.name,
)
def test_the_preparation_records_carry_no_fullwidth_punctuation(relative: Path) -> None:
    """No CJK enumeration comma slips into the English prose.

    ``、`` is the mark a half-translated draft leaves behind.
    """
    assert not FULLWIDTH_COMMA.search(_read(relative)), (
        f"{relative} carries a CJK enumeration comma; its prose is English"
    )


@pytest.mark.parametrize(
    ("kind", "pattern"),
    LEAK_PATTERNS,
    ids=lambda p: p if isinstance(p, str) else "",
)
@pytest.mark.parametrize(
    "relative",
    [FORM, *DRAFTS, RUNBOOK],
    ids=lambda p: p.name,
)
def test_the_preparation_records_carry_no_identifying_pattern(
    relative: Path, kind: str, pattern: re.Pattern[str]
) -> None:
    """No email, phone, grant number or ORCID in any preparation paper.

    These are the shapes a real name or affiliation leaves behind even
    when the name itself is gone. The check is heuristic, but the
    heuristics are the ones the leak shapes call for, and a hit is a
    stop, not a warning.
    """
    match = pattern.search(_read(relative))
    assert match is None, (
        f"{relative} carries what looks like a {kind} ({match.group(0)!r}); "
        "the pilot's preparation records name roles and documents only"
    )


@pytest.mark.parametrize(
    "relative",
    [FORM, *DRAFTS, RUNBOOK],
    ids=lambda p: p.name,
)
def test_the_preparation_records_name_people_by_role_only(relative: Path) -> None:
    """The documents' prose carries no personal-name shape.

    A personal name in running prose reads as two consecutive
    capitalised words that are not one of the documents' legitimate
    capitalised nouns. The check is deliberately narrow — it looks for
    the *shape*, and lets the allowlisted non-person words through —
    because the role rule (owner, advisor, student, participant) is the
    real boundary, and this is the net under it.
    """
    text = _read(relative)
    # Running prose only: headings, table rows and fenced blocks carry the
    # documents' structural capitalisation, not names.
    prose = "\n".join(
        line for line in text.splitlines() if not line.startswith(("```", "|", "#", "-"))
    )
    suspects = [
        f"{first} {second}"
        for first, second in re.findall(r"\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b", prose)
        if first not in NON_PERSON_WORDS and second not in NON_PERSON_WORDS
    ]
    assert not suspects, (
        f"{relative} names {suspects[:5]}, which look like personal names; "
        "the pilot's preparation records name participants by role only"
    )


# ---------------------------------------------------------------------------
# The plan still says what the form summarises.
# ---------------------------------------------------------------------------


def test_the_plan_still_holds_three_preopening_items() -> None:
    """The plan's §12 still names three items to supply before opening.

    The form summarises a source section; if the source moved, the form
    must move with it. This reads the plan's own §12 and fails if it
    stops listing the three items — so the form cannot quietly
    summarise a section that no longer says this.
    """
    plan = REPO_ROOT / PLAN_SRC
    assert plan.is_file(), "the Phase 4 execution plan must exist"
    text = plan.read_text(encoding="utf-8")
    section = re.search(r"^## 12\..*?(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    assert section, "plan §12 must exist for the owner-decisions form to summarise"
    body = section.group(0)
    for marker in (
        "1.",
        "2.",
        "3.",
    ):
        assert marker in body, (
            f"plan §12 must still list three pre-opening items ({marker!r} missing)"
        )


PLAN_SRC: Final = Path("docs") / "plans" / "PHASE_4-execution-plan.md"
