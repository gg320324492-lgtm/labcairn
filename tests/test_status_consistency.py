"""The status board must agree with the rest of the repository.

Four statements about LC-P1-08's and G2's progress were found stale by
reading and hand-corrected:

1. ``G2-acceptance.md`` named migration head ``0001 and 0002`` when the
   head was ``0003``
2. the same document still listed the PyMuPDF licence decision as open
   after ADR-0008 resolved it
3. the status board still said ``NOT STARTED`` after the schema merged
4. the row described only the schema after the adapters had merged too

None of the four is a mechanical failure, and this file does not pretend to
catch them. Items 3 and 4 are *how far along* a work order actually is,
which is a semantic judgement -- a commit-message grep for the work-order id
was tried and false-positived on three work orders, because commits
mention them incidentally through ADRs that plan future work.

What **is** mechanical, and what this file checks, is the set of rules the
plan already states about itself:

* line 19 of the plan: *"every non-``NOT STARTED`` row cites the commit or
  report that is the evidence"*
* line 21 of the plan: a closed status vocabulary
* the plan's priority legend: *"A gate with an incomplete P0 cannot be
  released"*
* and two documents that must agree -- the status board and
  ``docs/handoff/CURRENT.md`` -- silently diverging, which is how item 2
  survived
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PLAN = REPO / "docs" / "PHASE_1_WORKORDERS.md"
HANDOFF = REPO / "docs" / "handoff" / "CURRENT.md"

#: Declared by the plan at "Status vocabulary:".
STATUS_VOCABULARY = {
    "NOT STARTED",
    "IN PROGRESS",
    "PASS",
    "PASS WITH NOTES",
    "BLOCKED",
    "FAIL",
}

#: A closed gate implies these and nothing looser.
ACCEPTED = {"PASS", "PASS WITH NOTES"}

_ROW = re.compile(
    r"^\|\s*(LC-P1-\d+)\s*\|\s*(P[01])\s*\|\s*(G\d)\s*\|\s*\*?\*?([A-Z][A-Z ]*?)\*?\*?\s*\|(.*)$"
)
_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def _rows() -> list[tuple[str, str, str, str, str]]:
    out = []
    for line in PLAN.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| LC-P1-"):
            continue
        match = _ROW.match(line)
        assert match is not None, f"status board row does not parse: {line[:80]}"
        work, _pri, gate, status, evidence = match.groups()
        out.append((work, gate, status.strip(), evidence, line))
    return out


ROWS = _rows()


# --------------------------------------------------------------------------
# the plan's own rules about the board
# --------------------------------------------------------------------------


def test_the_status_board_exists_and_parses() -> None:
    assert ROWS, "no work-order rows found; the table format changed"
    assert len(ROWS) >= 14, f"only {len(ROWS)} work orders found"


@pytest.mark.parametrize(("work", "gate", "status", "evidence", "line"), ROWS)
def test_status_is_from_the_declared_vocabulary(
    work: str, gate: str, status: str, evidence: str, line: str
) -> None:
    """A status outside the vocabulary is a typo nobody can act on."""
    assert status in STATUS_VOCABULARY, (
        f"{work} has status {status!r}, which is not in the declared vocabulary "
        f"{sorted(STATUS_VOCABULARY)}.\n{line}"
    )


@pytest.mark.parametrize(("work", "gate", "status", "evidence", "line"), ROWS)
def test_a_started_work_order_cites_its_evidence(
    work: str, gate: str, status: str, evidence: str, line: str
) -> None:
    """The plan states it: *"every non-``NOT STARTED`` row cites the commit or
    report that is the evidence."* A row marked done with nothing to point at
    is an assertion, and assertions are what this project keeps having to
    unpick later.
    """
    if status == "NOT STARTED":
        return
    has_sha = re.search(r"`\b[0-9a-f]{7,40}\b`", evidence) is not None
    has_link = _LINK.search(evidence) is not None
    assert has_sha or has_link, (
        f"{work} is {status!r} but its evidence cell cites no commit and no report.\n{line}"
    )


@pytest.mark.parametrize(("work", "gate", "status", "evidence", "line"), ROWS)
def test_a_started_work_order_also_says_so_in_its_title(
    work: str, gate: str, status: str, evidence: str, line: str
) -> None:
    """`NOT STARTED` and a commit citation cannot both be true."""
    if status == "NOT STARTED":
        assert re.search(r"`\b[0-9a-f]{7,40}\b`", evidence) is None, (
            f"{work} is NOT STARTED but its evidence cell names a commit, so it is not.\n{line}"
        )


# --------------------------------------------------------------------------
# gates
# --------------------------------------------------------------------------


def _closed_gates_from_handoff() -> set[str]:
    """The gate table's rows, tolerating a bolded gate name.

    ``CURRENT.md`` bolds the gate it considers current (``| **G2** |``), so a
    pattern that assumes a bare ``G2`` silently loses exactly the gate a
    reader most wants to see.
    """
    text = HANDOFF.read_text(encoding="utf-8")
    table = text.split("## Gates", 1)[1].split("##", 1)[0]
    return {
        match.group(1)
        for line in table.splitlines()
        if (match := re.search(r"^\|\s*\*{0,2}(G\d)\*{0,2}\s*\|\s*\*\*closed\*\*", line))
    }


def _closed_gates_from_plan() -> set[str]:
    """The plan states gates in prose: "G0, G1 and **G2 closed**. **G3 next**".

    That is an **enumeration**, so the split is at the word rather than per
    gate: every gate named *before* "closed" is closed. A per-gate window
    reads the text between G0 and G1 as G0's segment, finds no "closed" in
    it, and concludes G0 is open -- which is how this returned {G2} alone
    the first time.
    """
    line = next(
        line
        for line in PLAN.read_text(encoding="utf-8").splitlines()
        if line.startswith("**Gate status:**")
    )
    head, marker, _tail = line.partition("closed")
    return set(re.findall(r"\bG\d\b", head)) if marker else set()


def test_the_two_documents_agree_on_which_gates_are_closed() -> None:
    """How item 2 survived: two documents state the same fact and drifted.

    `CURRENT.md` has a gate table; the plan has a gate line. Nothing
    checked that they said the same thing.
    """
    handoff = _closed_gates_from_handoff()
    plan = _closed_gates_from_plan()
    assert handoff, "no closed gates parsed from CURRENT.md; its table changed"
    assert plan, "no closed gates parsed from the plan's gate line; it changed"
    assert handoff == plan, (
        f"CURRENT.md says {sorted(handoff)} are closed; the plan says "
        f"{sorted(plan)}. Two documents stating one fact and drifting is how "
        f"a resolved decision kept being reported as open."
    )


def test_a_closed_gate_has_no_unaccepted_work_order() -> None:
    """The plan's legend: *"A gate with an incomplete P0 cannot be released."*

    Read for every gate, not just P0 rows: a gate whose P1 work order is
    still ``NOT STARTED`` is not a gate that has been closed, whatever the
    gate line says.
    """
    for gate in sorted(_closed_gates_from_handoff()):
        outstanding = [
            f"{work} ({status})"
            for work, row_gate, status, _evidence, _line in ROWS
            if row_gate == gate and status not in ACCEPTED
        ]
        assert not outstanding, (
            f"{gate} is recorded as closed but has unaccepted work orders: "
            f"{outstanding}. Either the gate is not closed or the row is stale."
        )


# --------------------------------------------------------------------------
# links and commit references
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", sorted((REPO / "docs").rglob("*.md")), ids=str)
def test_relative_links_in_docs_resolve(path: Path) -> None:
    """A renamed ADR or a moved evidence file leaves every link to it dead."""
    text = path.read_text(encoding="utf-8")
    for target in _LINK.findall(text):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        clean = target.split("#", 1)[0]
        if not clean:
            continue
        assert (path.parent / clean).resolve().exists(), (
            f"{path.relative_to(REPO)} links to {target!r}, which does not exist. "
            f"If the file was renamed, every reference to it is now dead."
        )


#: **Not checked here: whether a cited commit exists.** An earlier draft of
#: this file did, with one allowlisted exception, and it failed across seven
#: documents -- the ADRs and UPSTREAM_REFERENCES.md cite the histories of
#: pydantic-ai, OpenHands and others by design, because that is what an
#: upstream study is. An allowlist that grows by one entry per upstream study
#: is not a check; it is a list nobody maintains, and it goes stale silently,
#: which is the failure this whole file exists to catch.
#:
#: Local commit references are covered indirectly: the evidence-cell rule
#: above requires a commit or a report on every row that is not
#: NOT STARTED, and the board's rows cite this repository.
