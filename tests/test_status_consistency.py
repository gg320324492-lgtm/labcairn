"""The status board must agree with the rest of the repository.

Four statements about LC-P1-08's and G2's progress were found stale by
reading and hand-corrected:

1. ``G2-acceptance.md`` named migration head ``0001 and 0002`` when the
   head was ``0003``
2. the same document still listed the PyMuPDF licence decision as open
   after ADR-0008 resolved it
3. the status board still said ``NOT STARTED`` after the schema merged
4. the row described only the schema after the adapters had merged too

Three of the four are in documents that record *facts about the past*,
where a value is correct when written and rots silently afterwards.

Item 4 is free text and cannot be checked. Item 3 **can** be, and this
file does it: a row reading ``NOT STARTED`` must have no merge commit
naming it. An earlier attempt used ``git log --grep`` and appeared to
fail, because ``--grep`` matches commit *bodies* by default and the
bodies of merged work orders mention the ones after them ("LC-P1-08
through LC-P1-11"). Restricting to merge-commit subjects -- where this
project's branch convention lives -- gives no false positives.

Every check here runs on every commit on two platforms, so a check that
fires on an unrelated legitimate change is worse than no check: it
teaches people to ignore it. The parsers below are therefore tolerant of
the ways these documents get reworded -- bold, capitalisation, synonyms,
enumeration, line wrapping -- rather than exact. An earlier draft was
not, and fired on eight ordinary phrasings of the gate line.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PLAN = REPO / "docs" / "PHASE_1_WORKORDERS.md"
HANDOFF = REPO / "docs" / "handoff" / "CURRENT.md"

#: The words the plan uses for a gate that is done. Matched
#: case-insensitively; all three appear in the plan's own prose ("declared
#: passed", "cannot be released", "once acceptance passes"), so a check that
#: accepted only one of them would fail on a correct rewording.
_CLOSED_WORDS = r"closed|passed|released"

_STATUS_CELL = r"\*{0,2}([A-Z][A-Z ]*?)\*{0,2}"
_ROW = re.compile(
    rf"^\|\s*(LC-P1-\d+)\s*\|\s*\*?\*?(P[01])\*?\*?\s*\|\s*\*?\*?(G\d)\*?\*?\s*\|"
    rf"\s*{_STATUS_CELL}\s*\|(.*)$"
)
#: SHA-shaped: backticked, 7-40 characters, all alphanumeric, with both
#: a digit and a letter. Deliberately NOT [0-9a-f] -- a mistyped SHA like
#: ``623e3XX`` would then stop matching, and the check would skip it
#: silently instead of reporting it, which is the rot this file exists for.
_SHA_SHAPED = re.compile(r"`([0-9A-Za-z]{7,40})`")


def _cited_shas(evidence: str) -> list[str]:
    """Backticked tokens in an evidence cell that look like a commit."""
    return [
        token
        for token in _SHA_SHAPED.findall(evidence)
        if any(c.isdigit() for c in token) and any(c.isalpha() for c in token)
    ]


_FENCE = re.compile(r"^\s*(```|~~~)")
#: [text](target), [text](<target>) and [text](target "title")
_LINK = re.compile(r"\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+[\"'][^\"']*[\"'])?\s*\)")


def _plan_text() -> str:
    return PLAN.read_text(encoding="utf-8")


def _board_rows() -> list[tuple[str, str, str, str]]:
    """(work order, gate, status, evidence cell) for each board row.

    Tolerates a bolded priority, a bolded gate and a bolded or inline-coded
    status. An earlier version asserted inside the parser, so one
    reformatted row raised at import time and pytest reported *every* test
    in the file as a collection error.
    """
    rows = []
    for line in _plan_text().splitlines():
        if not line.startswith("|"):
            continue
        match = _ROW.match(line)
        if match is None:
            continue
        work, _pri, gate, status, evidence = match.groups()
        rows.append((work, gate, status.strip(), evidence))
    return rows


ROWS = _board_rows()
VOCABULARY = _plan_text().split("Status vocabulary:", 1)[1].split("\n", 1)[0]


@pytest.fixture(scope="module")
def rows() -> list[tuple[str, str, str, str]]:
    return ROWS


# --------------------------------------------------------------------------
# parsing, checked on its own so a format change is not a mystery
# --------------------------------------------------------------------------


def test_the_status_vocabulary_is_read_from_the_plan_not_restated() -> None:
    """Restating it would let the two drift, silently and in one direction.

    Adding a word to the plan would fail the tests until this file was
    edited; *removing* one would not fail them at all.
    """
    assert VOCABULARY.strip(), (
        "the plan no longer declares a status vocabulary where this file "
        "expects one. It is parsed rather than restated, so a reworded plan "
        "stops being checkable -- and that should be loud."
    )
    declared = set(re.findall(r"`([^`]+)`", VOCABULARY))
    assert declared, f"no backticked words found in {VOCABULARY!r}"
    assert "NOT STARTED" in declared
    assert "PASS" in declared


def test_the_status_board_parses_entirely() -> None:
    ids = re.findall(r"^\|\s*(LC-P1-\d+)\s*\|", _plan_text(), re.MULTILINE)
    assert len(ROWS) == len(ids), (
        f"{len(ids)} work-order rows in the board, {len(ROWS)} parsed. A row "
        f"changed shape -- bolded priority, an inserted column, a different "
        f"status style -- and the difference is which rows went unparsed."
    )


def test_the_gate_line_parses() -> None:
    assert _closed_gates_from_plan() is not None


# --------------------------------------------------------------------------
# the plan's rules about the board
# --------------------------------------------------------------------------


@pytest.mark.parametrize(("work", "gate", "status", "evidence"), ROWS)
def test_status_is_from_the_vocabulary_the_plan_declares(
    work: str, gate: str, status: str, evidence: str
) -> None:
    declared = set(re.findall(r"`([^`]+)`", VOCABULARY))
    assert status in declared, (
        f"{work} has status {status!r}, which the plan does not declare. "
        f"Declared: {sorted(declared)}"
    )


@pytest.mark.parametrize(("work", "gate", "status", "evidence"), ROWS)
def test_a_started_work_order_cites_its_evidence(
    work: str, gate: str, status: str, evidence: str
) -> None:
    """Plan line 19: *"every non-``NOT STARTED`` row cites the commit or
    report that is the evidence."*"""
    if status == "NOT STARTED":
        return
    has_commit = bool(_cited_shas(evidence))
    has_link = _LINK.search(evidence) is not None
    assert has_commit or has_link, (
        f"{work} is {status!r} but its evidence cell names no commit and no "
        f"report. If that status is genuinely blocked on something prose, the "
        f"plan's rule needs amending rather than this row being exempt."
    )


@pytest.mark.parametrize(("work", "gate", "status", "evidence"), ROWS)
def test_a_not_started_work_order_cites_no_commit(
    work: str, gate: str, status: str, evidence: str
) -> None:
    if status != "NOT STARTED":
        return
    assert bool(_cited_shas(evidence)) is False, (
        f"{work} is NOT STARTED but names a commit, so it is not"
    )


@pytest.mark.parametrize(("work", "gate", "status", "evidence"), ROWS)
def test_a_commits_cited_on_the_board_exist_here(
    work: str, gate: str, status: str, evidence: str
) -> None:
    """Every commit the board cites is a commit of *this* repository.

    Scoped to the board's evidence cells rather than all of ``docs/``:
    ``UPSTREAM_REFERENCES.md`` and the ADRs cite other projects' histories
    on purpose, and an allowlist that grows with each upstream study is not
    a check. The board cites only ours, so this needs no allowlist and
    catches a mistyped or force-pushed SHA — which is the rot this file
    exists for.
    """
    for sha in _cited_shas(evidence):
        assert _commit_exists(sha), (
            f"{work} cites {sha!r}, which is not a commit in this repository"
        )


# --------------------------------------------------------------------------
# item 3: NOT STARTED while a merge commit names the work order
# --------------------------------------------------------------------------


@pytest.mark.parametrize(("work", "gate", "status", "evidence"), ROWS)
def test_a_not_started_work_order_has_no_merged_work(
    work: str, gate: str, status: str, evidence: str
) -> None:
    """The one of the four stale statements that is mechanically decidable.

    Matched against merge-commit *subjects*, where this project's branch
    convention (``feat/lc-p1-08-...``) puts the work-order id. Matching
    bodies instead would false-positive: a commit that merges LC-P1-08 says
    "LC-P1-08 through LC-P1-11" in its message, so LC-P1-09/10/11 would
    appear to have been worked on.
    """
    if status != "NOT STARTED":
        return
    subjects = _merge_subjects()
    if subjects is None:
        pytest.skip("shallow checkout; merge history is not available")
    hits = [line for line in subjects if work.lower() in line.lower()]
    assert not hits, (
        f"{work} is NOT STARTED but {len(hits)} merge commit(s) name it: "
        f"{hits[:3]}. Either the row is stale or the commit is not this work."
    )


def _merge_subjects() -> list[str] | None:
    result = subprocess.run(
        ["git", "log", "--merges", "--format=%s"],
        cwd=REPO,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return None
    # A depth-1 checkout has no merge commits at all, so an empty result
    # means "cannot tell", not "nothing happened".
    return result.stdout.splitlines() or None


def _commit_exists(sha: str) -> bool:
    return (
        subprocess.run(
            ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
            cwd=REPO,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


# --------------------------------------------------------------------------
# gates
# --------------------------------------------------------------------------


def _closed_gates_from_handoff() -> set[str]:
    """CURRENT.md's gate table.

    Tolerates a bolded gate name, a bolded or plain status, and any of the
    words the plan uses for done. ``CURRENT.md`` bolds the gate it considers
    current, so a pattern assuming a bare ``G2`` loses exactly the gate a
    reader most wants to see.
    """
    text = HANDOFF.read_text(encoding="utf-8")
    if "## Gates" not in text:
        return set()
    table = text.split("## Gates", 1)[1].split("\n## ", 1)[0]
    closed = set()
    for line in table.splitlines():
        match = re.match(
            rf"^\|\s*\*{{0,2}}(G\d)\*{{0,2}}\s*\|\s*\*{{0,2}}(?:{_CLOSED_WORDS})\*{{0,2}}",
            line,
            re.IGNORECASE,
        )
        if match:
            closed.add(match.group(1))
    return closed


def _closed_gates_from_plan() -> set[str]:
    """The plan's gate line.

    States gates in prose -- "G0, G1 and **G2 closed**. **G3 next**" -- and
    the closed ones are an **enumeration**, so the split is at the word
    rather than per gate: everything named up to the *last* closed word is
    closed. A per-gate window reads the text between G0 and G1 as G0's
    segment, finds no "closed" in it, and concludes G0 is open.

    Line-wrapped and bulleted forms are tolerated, because both are ordinary
    edits to a Markdown document and neither changes what it means.
    """
    lines = _plan_text().splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.lstrip("- ").startswith("**Gate status:**")),
        None,
    )
    if start is None:
        return set()
    # Take the paragraph: the gate line and its continuation.
    paragraph = lines[start]
    for line in lines[start + 1 :]:
        if line.strip() and not line.startswith((" ", "\t")):
            break
        paragraph += " " + line.strip()

    matches = list(re.finditer(_CLOSED_WORDS, paragraph, re.IGNORECASE))
    if not matches:
        return set()
    return set(re.findall(r"\bG\d\b", paragraph[: matches[-1].end()]))


def test_the_two_documents_agree_on_which_gates_are_closed() -> None:
    """How item 2 survived: two documents state one fact and drifted.

    Nothing checked that they said the same thing, so a resolved decision
    kept being reported as open in one of them.
    """
    handoff = _closed_gates_from_handoff()
    plan = _closed_gates_from_plan()
    assert handoff, "no closed gates parsed from CURRENT.md's gate table"
    assert plan, "no closed gates parsed from the plan's gate line"
    assert handoff == plan, (
        f"CURRENT.md says {sorted(handoff)} are closed; the plan says "
        f"{sorted(plan)}. Two documents stating one fact and drifting is how "
        f"a resolved decision kept being reported as open."
    )


@pytest.mark.parametrize("source", ["CURRENT.md", "the plan"])
def test_a_closed_gate_has_no_unaccepted_work_order(
    source: str, rows: list[tuple[str, str, str, str]]
) -> None:
    """The plan's legend: a gate with incomplete work cannot be released.

    Checked against **both** documents' gate statements, not just one. A
    single source would let the other drift without this noticing, which is
    the defect above all over again one level down.
    """
    closed = _closed_gates_from_handoff() if source == "CURRENT.md" else _closed_gates_from_plan()
    accepted = {"PASS", "PASS WITH NOTES"}
    for gate in sorted(closed):
        outstanding = [
            f"{work} ({status})"
            for work, row_gate, status, _evidence in rows
            if row_gate == gate and status not in accepted
        ]
        assert not outstanding, (
            f"{source} records {gate} as closed but the board has unaccepted "
            f"work orders for it: {outstanding}"
        )


# --------------------------------------------------------------------------
# links
# --------------------------------------------------------------------------


def _links(text: str) -> list[str]:
    """Relative link targets, ignoring fenced code and inline examples.

    Skipping fences matters: the upstream-study documents quote Markdown
    inside fenced blocks as examples, and following those turns a citation
    into a false alarm.
    """
    out: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        marker = _FENCE.match(line)
        if marker:
            token = marker.group(1)
            fence = None if fence == token else (fence or token)
            continue
        if fence is not None:
            continue
        out.extend(_LINK.findall(line))
    return out


@pytest.mark.parametrize("path", sorted((REPO / "docs").rglob("*.md")), ids=str)
def test_relative_links_in_docs_resolve(path: Path) -> None:
    """A renamed ADR or a moved evidence file leaves every link to it dead.

    Directories count: ``docs/README.md`` links to ``adr/`` as an index.
    """
    for target in _links(path.read_text(encoding="utf-8")):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        clean = target.split("#", 1)[0]
        if not clean:
            continue
        assert (path.parent / clean).resolve().exists(), (
            f"{path.relative_to(REPO)} links to {target!r}, which does not exist."
        )
