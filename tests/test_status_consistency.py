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

Three more records are watched here now, because they fail the same way
-- a record that points at something a reader cannot open:

5. the carried-open-issues regions of ``docs/PHASE_1_WORKORDERS.md`` and
   ``docs/ROADMAP.md`` cite file paths; a row that cites neither a
   tracked file nor a revision at which the file existed is a pointer to
   nothing
6. ``docs/RELEASE-NOTES.md`` says pull request #146 is open, and this
   repository has the merge commit naming it; the sentence is legal only
   while a supersession marker says it is a dated reading
7. ``docs/REVIEW-DOSSIER.md`` declares the tree it describes, and every
   claim it makes -- a witness, an ADR, a path -- must be about that
   tree, or be named in the dossier's supersession marker as a later
   reading

Item 7 is the only one of the three that needs this repository's
**history** rather than its working tree, so it reads a fixed revision
with git. It is the one check here that can be skipped: a checkout
without that revision cannot answer the question, and a check that
guessed would be worse than one that says so.
"""

from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

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
#: A commit: backticked, 7-40 characters, **all hex**.
_HEX_TOKEN = re.compile(r"`([0-9a-f]{7,40})`")

#: Any backticked token that *could* be a mistyped commit. Matched loosely so
#: ``623e3XX`` is caught -- a hex-only pattern would skip it silently, which
#: is the rot this file exists for. But loose matching alone also catches
#: ``alembic13``, so a loose token is only reported when it also sits within
#: a typo's distance of a commit that really is cited on the board.
_LOOSE_TOKEN = re.compile(r"`([0-9A-Za-z]{7,40})`")
_TYPO_DISTANCE = 2


def _cited_shas(evidence: str) -> list[str]:
    """Tokens in an evidence cell that are commits, not package names."""
    return [token for token in _HEX_TOKEN.findall(evidence) if any(c.isdigit() for c in token)]


def _within(a: str, b: str, limit: int) -> bool:
    """Whether two tokens differ by at most ``limit`` characters."""
    if abs(len(a) - len(b)) > limit:
        return False
    differing = sum(1 for x, y in zip(a, b, strict=False) if x != y)
    return differing + abs(len(a) - len(b)) <= limit


def _looks_mistyped(token: str) -> bool:
    """A token too close to a commit's shape to be an ordinary word.

    A commit here is lowercase hex. A *mistyped* one keeps its length and
    its digits, and the wrong characters are almost always **uppercase** --
    someone reaching for a letter and hitting Shift. That is the whole
    discriminator, and it is a real limitation rather than a rule: a typo
    made of lowercase non-hex characters (``623e3zz``) is not caught, and
    neither is an all-lowercase package name, which is why this only fires
    on uppercase.

    Rejected alternatives, both measured: a hex-only pattern skips
    ``623e3XX`` silently, and a share-of-hex rule does not separate it from
    ``alembic13`` -- that word carries five hex characters out of eight,
    more than the ratio suggests.
    """
    return (
        len(token) >= 7
        and any(c.isupper() for c in token)
        and any(c.isdigit() for c in token)
        and any(c not in "0123456789abcdefABCDEF" for c in token)
    )


def _mistyped_commits(evidence: str) -> list[str]:
    """Loose tokens that look like a commit with characters mistyped."""
    cited = set(_cited_shas(evidence))
    return [
        token
        for token in _LOOSE_TOKEN.findall(evidence)
        if token not in cited and _looks_mistyped(token) and not _commit_exists(token)
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
    typos = _mistyped_commits(evidence)
    assert not typos, (
        f"{work} cites {typos}, which are not commits and are within "
        f"{_TYPO_DISTANCE} characters of ones that are. A mistyped reference "
        f"is more dangerous than a missing one: it looks right."
    )


# --------------------------------------------------------------------------
# item 3: NOT STARTED while a merge commit names the work order
# --------------------------------------------------------------------------


@pytest.mark.parametrize(("work", "gate", "status", "evidence"), ROWS)
def test_a_not_started_work_order_has_no_merged_work(
    work: str, gate: str, status: str, evidence: str
) -> None:
    """The one of the four stale statements that is mechanically decidable.

    **What counts as a delivery, and what does not.** A pull-request merge
    is a delivery: GitHub writes it as ``Merge pull request #N from
    owner/branch``, and the branch is the name the delivery was given. A
    merge of one branch into another *inside* a delivery branch is not a
    delivery — it is the branch being assembled — and the two are told
    apart by their shape, not by a list of exceptions.

    **The name is read off the branch, not off the subject.** The subject
    is a fixed sentence and the work-order id lives in the branch it
    carries; and the id is not always in the branch at all. G5 was
    delivered on ``delivery/g5``, which names the **gate** and neither work
    order, and a board that says ``LC-P1-13 | NOT STARTED`` while that
    merge sits in the history is a stale row this check has to be able to
    see. So the name that is looked for is the work order's **or** its
    gate's, and both are looked for in the branch.

    **And the commit has to be the commit.** A merge commit's SHA is not
    the first word of its subject — the subject is a sentence, and its
    first word is ``Merge`` — so the check reads the SHA out of the log
    rather than out of the subject, and compares the merge against its
    first parent. **An earlier draft read the SHA out of the subject, so
    every comparison failed, every candidate was discarded, and this check
    passed without having looked at anything.**
    """
    if status != "NOT STARTED":
        return
    merges = _merge_commits()
    if merges is None:
        pytest.skip("shallow checkout; merge history is not available")
    candidates = [(sha, subject) for sha, subject in merges if _names_the_work(subject, work, gate)]
    hits = [f"{sha} {subject}" for sha, subject in candidates if _merge_touched_code(sha)]
    assert not hits, (
        f"{work} is NOT STARTED but {len(hits)} pull-request merge(s) that "
        f"changed code name it or its gate: {hits[:3]}. Either the row is "
        f"stale or the commit is not this work. "
        f"(Planning commits are ignored: writing "
        f"{len(candidates) - len(hits)} document(s) that plan this work "
        f"order is not doing it.)"
    )


def _names_the_work(subject: str, work: str, gate: str) -> bool:
    """Whether a pull-request merge's branch names this work order or its gate."""
    branch = _delivered_branch(subject)
    if branch is None:
        return False
    lowered = branch.lower()
    return work.lower() in lowered or gate.lower() in lowered


def _delivered_branch(subject: str) -> str | None:
    """The branch a pull-request merge brought in, or ``None``.

    Only the pull-request shape is a delivery. ``Merge branch 'x' into
    'y'`` is one branch being assembled inside another, and treating it as
    a delivery would make every work order look delivered the moment its
    branch was touched.
    """
    match = re.match(r"^Merge pull request #\d+ from \S+/(\S+)\s*$", subject)
    return match.group(1) if match else None


def _merge_commits() -> list[tuple[str, str]] | None:
    """Every pull-request merge that landed on ``main``, as ``(sha, subject)``.

    **The history that carries the deliveries is main's, and main's
    *first-parent* history at that.** A merge of one branch into another
    inside a delivery branch sits on the second parent, not on the first,
    so the first-parent chain is the list of what landed on main and
    nothing else. And main's history is where the deliveries are: the
    branch a pull request was made from does not contain the merges that
    carried the earlier ones, so **asking the current branch would ask a
    question whose answer is always "nothing landed"**.

    ``origin/main`` is tried first, because a checkout of a pull request
    has main's remote-tracking ref and not always main itself.
    """
    for ref in ("origin/main", "main"):
        result = subprocess.run(
            ["git", "log", "--merges", "--first-parent", ref, "--format=%H%x00%s"],
            cwd=REPO,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            continue
        pairs = []
        for line in result.stdout.splitlines():
            sha, _, subject = line.partition("\x00")
            if sha:
                pairs.append((sha, subject))
        # A depth-1 checkout has no merge commits at all, so an empty result
        # means "cannot tell", not "nothing happened".
        return pairs or None
    return None


def _merge_touched_code(sha: str) -> bool:
    """Whether a merge commit changed ``src/`` or ``migrations/``.

    **The comparison is against the merge's first parent.** A merge commit
    has more than one parent, and the others are the branches it absorbed;
    their differences say what those branches carried, not what this merge
    brought in. The first parent is the state the merge landed on, so the
    difference against it is the delivery.

    **The distinction matters because the project's own precedent is a
    planning artefact named for a work order** --
    ``docs/plans/LC-P1-01-approved-amendments.md`` -- so the first PR that
    *plans* a NOT STARTED work order would otherwise turn this row red for
    doing exactly the right thing.
    """
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{sha}^1", sha],
        cwd=REPO,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return any(name.startswith(("src/", "migrations/")) for name in result.stdout.splitlines())


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


def _closed_gates_from_handoff() -> set[str] | None:
    """CURRENT.md's gate table.

    Tolerates a bolded gate name, a bolded or plain status, and any of the
    words the plan uses for done. ``CURRENT.md`` bolds the gate it considers
    current, so a pattern assuming a bare ``G2`` loses exactly the gate a
    reader most wants to see.
    """
    text = HANDOFF.read_text(encoding="utf-8")
    if "## Gates" not in text:
        # A renamed heading in a handoff document is an ordinary edit. Skip
        # rather than fail: a test that fires on it teaches people to ignore
        # it, and the check is about the two documents agreeing, not about
        # the shape of one of them.
        return None
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
    # A paragraph runs to the next *blank line*. A soft wrap -- a physical
    # newline with no indent, which is what an editor's reflow produces --
    # is the ordinary case and an earlier version only followed indented
    # continuations, so it failed on the most common edit there is.
    # A paragraph runs to the next *blank line* -- that is what Markdown
    # means, and it is what an editor's reflow produces when it rewraps a
    # line at the column limit. An earlier version followed only indented
    # continuations and stopped at the first non-blank line after the first,
    # so it failed on the most ordinary edit there is.
    collected: list[str] = []
    for line in lines[start:]:
        if not line.strip():
            if collected:
                break
            continue
        collected.append(line.strip())
    paragraph = " ".join(collected) or lines[start]

    matches = list(re.finditer(_CLOSED_WORDS, paragraph, re.IGNORECASE))
    if not matches:
        return set()
    sl = paragraph[: matches[-1].end()]
    return set(re.findall(r"G\d", sl))


def test_the_two_documents_agree_on_which_gates_are_closed() -> None:
    """How item 2 survived: two documents state one fact and drifted.

    Nothing checked that they said the same thing, so a resolved decision
    kept being reported as open in one of them.
    """
    handoff = _closed_gates_from_handoff()
    if handoff is None:
        pytest.skip("CURRENT.md no longer has a '## Gates' section to compare")
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
    gates = _closed_gates_from_handoff() if source == "CURRENT.md" else _closed_gates_from_plan()
    if gates is None:
        pytest.skip("CURRENT.md no longer has a '## Gates' section to check")
    closed = gates
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


#: A heading, and the text of it.
_HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$")

#: The documents outside ``docs/`` whose in-page anchors are watched.
_ANCHORED_DOCUMENTS: tuple[str, ...] = (
    "README.md",
    "README.zh-CN.md",
    "CHANGELOG.md",
)


def _slug(heading: str) -> str:
    """The anchor GitHub gives a heading.

    **GitHub's own rule, in its own order**: drop the markdown emphasis,
    lowercase what is left, remove everything that is not a letter, a
    number, a space or a hyphen, and turn the spaces into hyphens.

    **The spaces are why the order matters.** A heading that carries an
    em-dash between two words loses the dash and keeps *both* spaces, so
    ``Licence status — MIT`` becomes ``licence-status--mit`` with two
    hyphens — while ``许可证状态——MIT`` loses the dashes and keeps no space
    at all, and becomes ``许可证状态mit``. **A link that names one of those
    resolves and the other does not**, and a reader cannot tell which one
    the renderer produced.
    """
    text = re.sub(r"[`*]", "", heading).strip().lower()
    text = re.sub(r"[^\w\- ]", "", text, flags=re.UNICODE)
    return text.replace(" ", "-")


def _anchors(path: Path) -> set[str]:
    """The anchors the headings in a document make."""
    found: set[str] = set()
    fence: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        marker = _FENCE.match(line)
        if marker:
            token = marker.group(1)
            fence = None if fence == token else (fence or token)
            continue
        if fence is not None:
            continue
        match = _HEADING.match(line)
        if match:
            found.add(_slug(match.group(1)))
    return found


@pytest.mark.parametrize(
    "path",
    [
        *sorted((REPO / "docs").rglob("*.md")),
        *(REPO / name for name in _ANCHORED_DOCUMENTS),
    ],
    ids=str,
)
def test_in_page_anchors_resolve(path: Path) -> None:
    """A link to a heading in this document lands on that heading.

    **The relative-link check above cannot see these.** A target that
    starts with ``#`` names a heading in the document it is already in,
    and nothing checked that such a heading existed — so a link to a
    renamed heading stayed broken. The Chinese README's link to its own
    licence section was one of them, and it was broken in the way that is
    hardest to see: the English one beside it resolves, because its
    heading has a space on each side of the dash and the Chinese one does
    not.
    """
    anchors = _anchors(path)
    broken: list[str] = []
    for target in _links(path.read_text(encoding="utf-8")):
        if not target.startswith("#") or target == "#":
            continue
        wanted = unquote(target[1:])
        if wanted in anchors:
            continue
        # GitHub numbers a repeated heading: the second ``## Notes`` is
        # ``#notes-1``. A link to it is a link to the second one.
        if re.sub(r"-\d+$", "", wanted) in anchors:
            continue
        broken.append(target)
    assert not broken, (
        f"{path.relative_to(REPO)} links to an anchor that no heading in it "
        f"carries: {sorted(set(broken))[:5]}. The slug of a heading is what "
        "GitHub makes of it, and a link that guesses it is a dead link."
    )


# --------------------------------------------------------------------------
# the G1/G2 human-review checklist names node ids, and they have to exist
# --------------------------------------------------------------------------

#: The checklist a human reviewer works from. Its whole value is that each row
#: names something a reader can run and read, so a node id that does not exist
#: is not a typo — it is a clause nobody can re-verify.
CHECKLIST = REPO / "docs" / "acceptance" / "G1-G2-human-review-checklist.md"

#: A citation, in the two forms the checklist uses: a file with its `::`
#: segments, or a bare `::segment` continuation that inherits the file — and,
#: when the earlier citation carried a class, the class — of the citation before
#: it. An optional `[parameterisation]` suffix is part of a node id a reader
#: would type but not part of a definition's name.
_CITATION = re.compile(
    r"(?P<file>tests/[a-z_0-9]+\.py)(?P<full>(?:::[A-Za-z_0-9]+(?:\[[^\]]*\])?)*)|"
    r"(?P<cont>::[A-Za-z_0-9]+(?:\[[^\]]*\])?(?:::[A-Za-z_0-9]+(?:\[[^\]]*\])?)*)"
)


def _file_symbols(source: Path) -> tuple[set[str], dict[str, set[str]]]:
    """The module-level tests of a file, and each test class's methods."""
    module_tests: set[str] = set()
    classes: dict[str, set[str]] = {}
    for node in ast.parse(source.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            module_tests.add(node.name)
        elif isinstance(node, ast.ClassDef):
            classes[node.name] = {
                method.name
                for method in node.body
                if isinstance(method, ast.FunctionDef) and method.name.startswith("test_")
            }
    return module_tests, classes


def _segments(raw: str) -> list[str]:
    """The `::` segments of a citation, without their parameterisation suffixes."""
    return [part.split("[", 1)[0] for part in raw.split("::") if part]


def test_the_human_review_checklists_node_ids_exist() -> None:
    """Every node id the checklist cites exists, **under the class it claims**.

    **Why this is watched mechanically.** The checklist was written from the two
    gate records, and those records cite whole files rather than node ids for
    most of G1's clauses — §6.1 of the checklist says so. Re-deriving the ids by
    hand went wrong three times: a class named `TestApprovalGate` where the tree
    has `TestApprovalCheckpoint`, a file `tests/test_recovery_probe.py` that has
    never existed, and two methods cited under `TestPlaceholderVocabulary` that
    live in `TestSubstanceRejection`. All three were plausible, none was
    falsifiable by reading, and a reviewer following any of them would report a
    missing witness where the witness is fine.

    **And why the first version of this check was not enough.** It matched only
    citations carrying the file prefix — a quarter of them — and it asked whether
    each segment appears anywhere in the file rather than whether the method is
    **inside the class the citation names**. The third error above slipped
    through green. So continuations are resolved against the file and class of
    the citation before them, which is exactly what a reader typing the id does,
    and the definitions are read out of the file's syntax tree rather than by
    regular expression.

    **What it still does not do.** A citation of a bare file (`tests/x.py`, no
    `::`) is not checked — the checklist uses those deliberately, and §6.1 counts
    them. And existence is not the same as *sufficiency*: this witness cannot
    tell whether a test that exists actually establishes the property its row
    claims. That is the reviewer's job.
    """
    broken: list[str] = []
    checked = 0
    file: str | None = None
    klass: str | None = None
    symbols: dict[str, tuple[set[str], dict[str, set[str]]]] = {}
    for match in _CITATION.finditer(CHECKLIST.read_text(encoding="utf-8")):
        raw = match.group("full") if match.group("file") else match.group("cont")
        if match.group("file"):
            file = match.group("file")
            klass = None
        if not file or not raw:
            continue
        parts = _segments(raw)
        if not parts:
            continue
        checked += 1
        if file not in symbols:
            source = REPO / file
            symbols[file] = _file_symbols(source) if source.is_file() else (set(), {})
        module_tests, classes = symbols[file]
        if parts[0][:1].isupper():
            klass = parts[0]
            if klass not in classes:
                broken.append(f"{file}::{'::'.join(parts)} (no class {klass})")
                continue
            if len(parts) > 1 and parts[1] not in classes[klass]:
                broken.append(f"{file}::{'::'.join(parts)} (no {parts[1]} in {klass})")
        else:
            owner = classes.get(klass, set()) if klass else module_tests
            if parts[0] not in owner:
                where = f"the class {klass}" if klass else "module level"
                broken.append(f"{file}::{'::'.join(parts)} (no {parts[0]} at {where})")
    assert checked >= 20, f"the check resolved only {checked} citations, so it proves nothing"
    assert not broken, (
        "the checklist cites node ids that are not in the tree, so a reviewer "
        f"following it would report a missing witness: {broken}"
    )


# --------------------------------------------------------------------------
# item 8: paths cited in a carried-open-issues region
# --------------------------------------------------------------------------

#: A repo-rooted path a record cites: ``docs/acceptance/x.md``, ``tests/test_x.py``.
_CITED_PATH = re.compile(
    r"(?<![\w/.-])((?:src|tests|docs|web|shell|scripts|examples|\.github|migrations)"
    r"/[\w./-]+\.(?:py|md|yml|yaml|json|mjs|ts|tsx|txt|toml|sql|nsh))"
)

#: A revision in backticks, in the 7-to-12-character short form the board writes.
_SHORT_REV = re.compile(r"`([0-9a-f]{7,12})`")

#: The lines that open a carried-issues region. **The phrase, not the `#`**: both records
#: write their region header as a bold sentence rather than a Markdown heading, so a reader
#: keyed on headings finds neither region and reports the carried issues as checked.
ISSUE_REGION_HEADERS = ("carried open issues", "open issues carried forward")

#: The records whose carried-issues regions are read.
ISSUE_REGION_RECORDS = (PLAN, REPO / "docs" / "ROADMAP.md")


def _tracked_files() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO,
        capture_output=True,
        check=False,
    )
    return {line for line in result.stdout.decode("utf-8").split("\n") if line.strip()}


def _existed_at(revision: str, path: str) -> bool:
    result = subprocess.run(
        ["git", "ls-tree", "--name-only", revision, "--", path],
        cwd=REPO,
        capture_output=True,
        check=False,
    )
    return result.stdout.decode("utf-8").strip() != ""


def _issue_region_rows(text: str) -> list[tuple[int, str]]:
    """The rows of every carried-issues region: **table rows and bullets**.

    `docs/PHASE_1_WORKORDERS.md` writes its carried issues as a Markdown table and
    `docs/ROADMAP.md` writes its carried-forward summary as a bullet list. Both cite file
    paths. A reader that understood only tables would leave the second region's citations
    unwatched while the witness still reported that carried issues are checked — which is a
    check that covers one of the two places the claim lives.
    """
    out: list[tuple[int, str]] = []
    inside = False
    for number, line in enumerate(text.split("\n"), start=1):
        stripped = line.strip()
        if not inside:
            inside = any(phrase in stripped.lower() for phrase in ISSUE_REGION_HEADERS)
            continue
        if stripped.startswith("#"):
            inside = False
            continue
        if stripped.startswith(("|", "- ")):
            out.append((number, stripped))
    return out


def _unopenable_issue_paths(text: str, tracked: set[str]) -> list[str]:
    """Paths a carried-issues row cites that a reader cannot open.

    **Two readings are legal, and both are checked.** The file is tracked today — the issue
    is still open at a path that exists. Or the **same row** cites a revision at which the
    path existed: the row is naming the file as it was when the finding was filed, which is
    what a closed issue legitimately does. `PHASE_1_WORKORDERS.md`'s three support-module rows
    are exactly this case — `tests/test_store_support.py` has not existed since `a1f9e54`
    renamed them out of the `test_*` glob on 2026-11-02, and the row cites `e9b56ba`, `5dbf09b`
    and `a1f9e54`, all of which have it.

    A row that cites a path neither tracked today nor present at any revision the row itself
    names is a pointer to nothing, and the reader following it finds no evidence either way.
    """
    problems: list[str] = []
    for _number, row in _issue_region_rows(text):
        if set(row) <= {"|", "-", " "}:
            continue
        revisions = sorted(set(_SHORT_REV.findall(row)))
        for path in sorted(set(_CITED_PATH.findall(row))):
            if path in tracked:
                continue
            if any(_existed_at(revision, path) for revision in revisions):
                continue
            problems.append(
                f"{row[:60].strip()}…"
                f"\n    cites {path}, which is not a tracked file, and the row names "
                f"{revisions or 'no revision'} — none of which has that path. A reader "
                "following the row cannot open the file it names, in this tree or at the "
                "revision it cites."
            )
    return problems


def test_a_carried_open_issue_cites_a_path_a_reader_can_open() -> None:
    """Every path a carried-issues row names exists, or existed at a revision that row cites.

    **Why this is watched.** A carried-open-issues row is the board's promise that a finding
    is still findable: its Note column names the file the finding is about, and a reader —
    a reviewer, or the next window — goes there. If the path is gone and the row names no
    revision that has it, the row is a pointer to nothing, and the issue reads as still open
    when its evidence is unlocatable. `docs/ROADMAP.md` carries nine such rows and
    `docs/PHASE_1_WORKORDERS.md` thirteen; until now neither was read.

    **Why "existed at a cited revision" is a legal reading, and why the revision has to be in
    the same row.** Three rows cite `tests/test_store_support.py`, `tests/test_recovery_support.py`
    and `tests/test_skill_support.py`, and no such file exists in this checkout: they were
    renamed out of the `test_*` glob on 2026-11-02. Banning those paths would be the mistake
    this project already names — rewriting a dated record to match today. They are legal
    **because the same row cites `e9b56ba`, `5dbf09b` and `a1f9e54`, and each of those
    revisions has the files.** The exemption is measured at the revision the row itself names;
    a row that names no revision gets no exemption.

    **What it cannot watch.** Whether the row's prose is still true, and whether an issue that
    reads as open actually is. It watches only the one mechanical thing: the path it sends a
    reader to is openable.
    """
    tracked = _tracked_files()
    assert tracked, "no tracked files, so nothing this witness checks could resolve"

    problems: list[str] = []
    read = 0
    for record in ISSUE_REGION_RECORDS:
        assert record.is_file(), (
            f"{record.relative_to(REPO)} is a board record, and it is not there"
        )
        text = record.read_text(encoding="utf-8")
        rows = _issue_region_rows(text)
        assert rows, f"{record.relative_to(REPO)} carries no carried-issues rows to read"
        read += len(rows)
        problems.extend(_unopenable_issue_paths(text, tracked))

    assert read >= 20, (
        f"the carried-issues regions together yielded only {read} rows, which is too few for "
        "this to be a check of the board rather than of one row"
    )
    assert not problems, (
        "carried open issues cite paths a reader cannot open:\n  "
        + "\n  ".join(problems)
        + "\n\nEither the path is current and a rename or a move broke the citation, or the row "
        "means the name as filed and has to cite the revision that has it."
    )


def test_the_issue_path_check_fails_on_an_unanchored_citation() -> None:
    """The path check is seen to fail for the property, on copies in memory.

    **Two mutations, each one a distinct way the rule is real.** (1) A path in a row that
    cites **no revision** is renamed to a plausible sibling that has never existed: the row
    keeps its shape, its wording, and its table cell, and the pointer breaks. (2) The
    revisions are stripped out of the row that legitimately cites historical names: the paths
    are unchanged and still legal-looking, and the row loses the only thing that made them
    legal. Mutation (2) is the one that proves the exemption is measured — a reader that
    reddens only on (1) is reading file existence, not the row.

    **Controls.** The unmutated records report nothing, so every report below is the mutation;
    each mutation is asserted to change bytes before any report is credited to it, because a
    needle that matches nothing produces a "mutant" identical to the original; and the real
    records' bytes are compared before and after.
    """
    tracked = _tracked_files()

    board = PLAN.read_text(encoding="utf-8")
    roadmap = (REPO / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
    board_bytes = PLAN.read_bytes()
    roadmap_bytes = (REPO / "docs" / "ROADMAP.md").read_bytes()

    def problems_for(board_text: str, roadmap_text: str) -> list[str]:
        return _unopenable_issue_paths(board_text, tracked) + _unopenable_issue_paths(
            roadmap_text, tracked
        )

    assert problems_for(board, roadmap) == [], (
        f"the records as they stand already report: {problems_for(board, roadmap)}"
    )

    rows = _issue_region_rows(board)

    # Mutation 1: a row that cites no revision gets a path that never existed.
    plain_rows = [
        (number, row)
        for number, row in rows
        if _CITED_PATH.search(row) and not _SHORT_REV.search(row)
    ]
    assert plain_rows, "no carried-issues row cites a path without citing a revision"
    _number, row = plain_rows[0]
    citation = _CITED_PATH.search(row)
    assert citation is not None, "the row selected for mutation 1 cites no path"
    path = citation.group(0)
    # The extension is kept: a needle anchored on `.py` matched nothing in the row this
    # check picked, which cites a `.md`, and the "mutation" rewrote nothing while the
    # calibration reported "0 problems" for it.
    bogus = re.sub(r"[A-Za-z0-9_-]+(\.\w+)$", r"never_witness_here\1", path)
    assert bogus != path, f"the rename needle matched nothing in {path!r}"
    mutated_board = board.replace(path, bogus, 1)
    assert mutated_board != board, "mutation 1 changed no bytes"
    found = problems_for(mutated_board, roadmap)
    assert any(bogus in problem for problem in found), (
        f"renaming {path} to {bogus} — a path that has never existed — was not reported: {found}"
    )

    # Mutation 2: strip the revisions from the row whose historical names are legal.
    anchored = [
        (number, row)
        for number, row in rows
        if _CITED_PATH.search(row) and _SHORT_REV.search(row) and "test_store_support" in row
    ]
    assert anchored, (
        "no carried-issues row cites both a historical path and a revision, so the exemption "
        "this witness grants is not exercised by the tree and this control tests nothing"
    )
    _number, row = anchored[0]
    stripped_row = _SHORT_REV.sub("that revision", row)
    assert stripped_row != row, "mutation 2's row edit changed nothing"
    mutated_board2 = board.replace(row, stripped_row, 1)
    assert mutated_board2 != board, "mutation 2 changed no bytes"
    found2 = problems_for(mutated_board2, roadmap)
    assert found2, (
        "removing the revisions from a row that cites historical paths left it clean. The "
        "exemption is then not measured at the cited revision at all — any path would pass."
    )
    assert any("test_store_support.py" in problem for problem in found2), found2

    assert PLAN.read_bytes() == board_bytes, (
        f"{PLAN.relative_to(REPO)} changed while it was being read"
    )
    assert (REPO / "docs" / "ROADMAP.md").read_bytes() == roadmap_bytes, (
        "docs/ROADMAP.md changed while it was being read"
    )


# --------------------------------------------------------------------------
# item 9: the release notes' claims about repository state
# --------------------------------------------------------------------------

RELEASE_NOTES = REPO / "docs" / "RELEASE-NOTES.md"

#: The marker phrase this repository's supersession convention settled on.
_SUPERSESSION = re.compile(r"dated snapshot", re.I)

#: A commit the file states as the place something landed, closed or merged.
_LANDED_AT = re.compile(r"\bat\s+`([0-9a-f]{7,40})`|\(`([0-9a-f]{7,40})`\)")

#: A full commit token, as an anchor must be written.
_FULL_TOKEN = re.compile(r"\b[0-9a-f]{7,40}\b")

#: The file's statement of its own release state.
_NO_TAG = re.compile(r"\bno tag has been cut\b", re.I)

#: `#146 … open` and `open … #146`, with **no sentence terminator in between**. The bound is
#: the whole claim: a window around the reference matched `(PR #118)` against `when the gate
#: was still open` two sentences earlier — a claim about a gate, not about a pull request —
#: and the first calibration run reported both references as defects on a file whose wording
#: is correct.
_OPEN_NEAR_PR: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?:pull request|PR) #(\d{2,4})[^.!?]*?\b(?:open|not (?:yet )?merged|awaiting|unmerged)\b",
        re.I,
    ),
    re.compile(
        r"\b(?:open|not (?:yet )?merged|awaiting|unmerged)\b[^.!?]*?(?:pull request|PR) #(\d{2,4})",
        re.I,
    ),
)


def _is_ancestor(token: str) -> bool:
    full = subprocess.run(
        ["git", "rev-parse", "--verify", f"{token}^{{commit}}"],
        cwd=REPO,
        capture_output=True,
        check=False,
    )
    if full.returncode:
        return False
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", full.stdout.decode().strip(), "HEAD"],
            cwd=REPO,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def _merge_commit_for(pr: int) -> str | None:
    """The merge commit whose **subject** names this pull request, or None.

    Subjects, not bodies: `git log --grep` matches bodies by default, and this project's
    merge subjects are where the branch convention lives. A body match is how an earlier
    attempt in this file appeared to fail on changes that had nothing to do with the claim.
    """
    result = subprocess.run(
        ["git", "log", "--all", "--format=%H\x1f%s", "--grep", f"#{pr}"],
        cwd=REPO,
        capture_output=True,
        check=False,
    )
    for line in result.stdout.decode("utf-8").split("\n"):
        if "\x1f" not in line:
            continue
        sha, subject = line.split("\x1f", 1)
        if re.search(rf"Merge pull request #{pr}\b", subject):
            return sha
    return None


def _supersession_blocks(lines: list[str]) -> list[tuple[int, int]]:
    """(first, last) line numbers of each marker block, 1-based and inclusive."""
    blocks: list[tuple[int, int]] = []
    index = 0
    while index < len(lines):
        if _SUPERSESSION.search(lines[index]):
            first = index
            while first > 0 and lines[first - 1].startswith(">"):
                first -= 1
            last = index
            while last + 1 < len(lines) and lines[last + 1].startswith(">"):
                last += 1
            blocks.append((first + 1, last + 1))
            index = last + 1
        else:
            index += 1
    return blocks


def _paragraph_starts(lines: list[str], before_line: int) -> int:
    """The first line of the paragraph that ends just before `before_line` (1-based)."""
    index = before_line - 2
    while index >= 0 and not lines[index].strip():
        index -= 1
    if index < 0:
        return before_line
    start = index
    while start - 1 >= 0 and lines[start - 1].strip():
        start -= 1
    return start + 1


def _marked_lines(text: str) -> tuple[set[int], list[int]]:
    """Lines a supersession marker covers, and the lines where a marker phrase sits badly.

    **The block, and the paragraph immediately above it.** This repository writes the marker
    as a note *about* the passage it follows: `RELEASE-NOTES.md`'s says "The clause above is a
    dated snapshot", and `.github/CI.md`'s says "The two sentences above … are left as
    written". A reader that covers only the block calls both records' dated claims unmarked
    and reddens on correct records — which is the false positive the calibration produced
    twice. Walking up over the blank line that separates a marker from its passage is what
    makes the convention's own wording readable; starting at the line directly above and
    refusing when it is blank covers nothing.
    """
    lines = text.split("\n")
    covered: set[int] = set()
    misplaced: list[int] = []
    for first, last in _supersession_blocks(lines):
        covered.update(range(first, last + 1))
        paragraph_start = _paragraph_starts(lines, first)
        if paragraph_start < first:
            covered.update(range(paragraph_start, first))
        if not lines[first - 1].startswith(">"):
            misplaced.append(first)
    return covered, misplaced


def _paragraph_claims(text: str) -> list[tuple[int, str]]:
    """(first line, paragraph) for each prose paragraph — the unit a claim is read in.

    A `>` block-quote is skipped as a paragraph of its own: it is the record's note about a
    claim, not another claim. Reading a marker as a claim would let the marker answer the
    question it exists to be asked.
    """
    out: list[tuple[int, str]] = []
    paragraph: list[str] = []
    start = 0
    for number, line in enumerate(text.split("\n"), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ">")):
            if paragraph:
                out.append((start, " ".join(paragraph)))
                paragraph = []
            continue
        if not paragraph:
            start = number
        paragraph.append(stripped)
    if paragraph:
        out.append((start, " ".join(paragraph)))
    return out


def _release_note_problems(text: str) -> list[str]:
    """Every claim `docs/RELEASE-NOTES.md` makes that this repository's own state contradicts."""
    problems: list[str] = []
    covered, misplaced = _marked_lines(text)
    tags = [
        t
        for t in subprocess.run(["git", "tag"], cwd=REPO, capture_output=True, check=False)
        .stdout.decode()
        .split("\n")
        if t.strip()
    ]

    for number, paragraph in _paragraph_claims(text):
        exempt = number in covered

        for pattern in _OPEN_NEAR_PR:
            for match in pattern.finditer(paragraph):
                pr = int(match.group(1))
                merged = _merge_commit_for(pr)
                if not merged or exempt:
                    continue
                problems.append(
                    f"line {number} says pull request #{pr} is open, and this repository has a "
                    f"merge commit naming it ({merged[:12]}…). The claim sits outside a "
                    "supersession marker, so it reads as a description of today and today "
                    "contradicts it."
                )

        for match in _LANDED_AT.finditer(paragraph):
            token = match.group(1) or match.group(2)
            if _is_ancestor(token):
                continue
            problems.append(
                f"line {number} states that something landed at {token[:12]}, and that token is "
                "not a commit on this repository's history — the sentence names a place a reader "
                "cannot go."
            )

        if _NO_TAG.search(paragraph) and tags and not exempt:
            problems.append(
                f"line {number} says no tag has been cut, and this repository has {len(tags)} "
                f"tag(s): {tags[:4]}"
            )

    for first in misplaced:
        problems.append(
            f"line {first} carries the supersession phrase outside a block-quote, so the marker "
            "this project's convention relies on is not in the form a reader or a tool looks for"
        )

    header = "\n".join(text.split("\n")[:14])
    anchor = re.search(r"tree this describes[^`]*`([0-9a-f]{7,40})`", header, re.I)
    if anchor and not _is_ancestor(anchor.group(1)):
        problems.append(
            f"the header says this document describes the tree at {anchor.group(1)[:12]}, which "
            "is not an ancestor of HEAD — a reader following the anchor lands elsewhere"
        )
    return problems


def test_the_release_notes_agree_with_the_repositorys_own_state() -> None:
    """Every state claim `docs/RELEASE-NOTES.md` makes is checkable against this repository.

    **Why this is watched.** The release notes are the document an outsider reads to decide
    what is true of the tree: which commit it describes, whether a pull request is still open,
    which commit closed what, whether a tag exists. None of those needs GitHub to verify — the
    anchor is an ancestor or it is not, a merge commit names a pull request or does not, a tag
    exists or does not. A release document contradicted by the repository it documents is the
    worst kind of stale record, because it is read as authoritative by someone with no way to
    check it.

    **The case this was written for.** Line 8 says the 2026-11-03 items are measured on a
    branch that has not landed, "pull request #146 open", and that their numbers "are not
    claims about `main` until the merge". Pull request #146 **merged** on 2026-11-04 as
    `384eb2f3a6c8`, a merge commit this repository has. The claim is true of 2026-11-03 and
    false today, and the file already says so: the marker at line 12 states that the clause
    above is a dated snapshot and that #146 merged. **The exemption is the marker, and the
    marker is what is watched** — remove the phrase and the same sentence is reported.

    **Dated-and-marked is legal; unmarked is a defect** — the same rule the supersession
    witness applies to `.github/CI.md`. A marker covers the block **and the paragraph it
    annotates**, because the convention writes the marker *after* the passage it is about.

    **What it cannot watch.** Whether the release's *substance* is accurately described: the
    limitations, the measurements, the licence position. It watches the claims the repository
    itself can answer, and only those.
    """
    assert RELEASE_NOTES.is_file(), f"{RELEASE_NOTES.relative_to(REPO)} is missing"
    text = RELEASE_NOTES.read_text(encoding="utf-8")

    claims = _release_note_problems(text)
    assert not claims, (
        "docs/RELEASE-NOTES.md states repository state the repository contradicts:\n  "
        + "\n  ".join(claims)
        + "\n\nEither the sentence is current and wrong — correct it — or it was true when "
        "written, in which case it keeps its wording and gains a supersession marker naming the "
        "reading that supersedes it."
    )

    marked, _misplaced = _marked_lines(text)
    assert marked, (
        "no dated snapshot in the release notes is marked any more. The marked ones are where "
        "the file's own history stays readable — the 2026-11-03 quarantine, the 2026-10-25 "
        "G5 paragraph — and their disappearance means the document was flattened rather than "
        "corrected."
    )
    references = len(_OPEN_NEAR_PR[0].findall(text)) + len(_OPEN_NEAR_PR[1].findall(text))
    assert references, (
        "the release notes no longer state a pull-request state beside an open/merged word, so "
        "this witness has nothing to compare against the merge commits"
    )


def test_the_release_state_check_fails_when_the_marker_is_removed_or_a_commit_is_invented(
    repo_root: Path,
) -> None:
    """The release-state reader is seen to fail for the property, on copies in memory.

    **Two mutations, one for each half of the rule.** (1) **The supersession phrase is
    removed** from the marker under the "pull request #146 open" clause, leaving every other
    word intact. The claim is unchanged and is now unmarked, so it must be reported against
    the merge commit this repository has. This is the half that proves the marker — not the
    wording — is what makes a superseded sentence legal. (2) **A `landed at` commit is
    replaced** by a token that is well-formed — exactly 40 hex characters — and is not a
    commit here. The sentence keeps its shape and names a place a reader cannot reach.

    **A control on the needle itself.** The first version of mutation 2 invented a 41-character
    token, which the revision pattern refuses to match at all, so the "mutant" produced no
    report from a mutation that had genuinely happened. Both mutations are asserted to change
    bytes, and mutation 2's token is asserted to be the length the reader recognises.

    **Control.** The real file's bytes are compared before and after, so the demonstration
    cannot write the record it guards.
    """
    path = repo_root / "docs" / "RELEASE-NOTES.md"
    original_bytes = path.read_bytes()
    text = original_bytes.decode("utf-8")

    assert _release_note_problems(text) == [], (
        f"the release notes as they stand already report: {_release_note_problems(text)}"
    )

    lines = text.split("\n")
    marked, misplaced = _marked_lines(text)
    assert not misplaced, f"the tree already carries a misplaced marker: {misplaced}"
    assert marked, "the tree carries no supersession marker, so mutation 1 has nothing to remove"
    blocks = _supersession_blocks(lines)
    assert blocks, "no marker block found, so mutation 1 has nothing to remove"
    # The **block's** first line, not the first covered line: `_marked_lines` also covers the
    # paragraph the block annotates, and `min(marked)` is that paragraph — the first run of
    # this demonstration read it as the block and asserted a `>` line was where ordinary prose
    # sits.
    marker_first, marker_last = blocks[0]
    assert lines[marker_first - 1].startswith(">"), (
        f"the marker block is expected to begin at line {marker_first} with a `>` line; found "
        f"{lines[marker_first - 1][:60]!r}"
    )

    # Mutation 1: the phrase goes, the prose stays.
    marker_text = "\n".join(lines[marker_first - 1 : marker_last])
    assert _SUPERSESSION.search(marker_text), "the marker block does not contain the phrase"
    unmarked_marker = _SUPERSESSION.sub("recorded at the time", marker_text, count=1)
    assert unmarked_marker != marker_text, "mutation 1's phrase removal matched nothing"
    unmarked = text.replace(marker_text, unmarked_marker, 1)
    assert unmarked != text, "mutation 1 changed no bytes"
    found = _release_note_problems(unmarked)
    assert any("pull request #146" in problem for problem in found), (
        f"removing the supersession phrase left the 'pull request #146 open' claim unreported. "
        f"This repository has a merge commit naming #146, so the marker is the only thing that "
        f"makes that sentence legal, and the reader did not see it: {found}"
    )

    # Mutation 2: an invented commit where a real one is cited.
    landed = _LANDED_AT.findall(text)
    assert landed, "the release notes cite no `landed at` commit, so mutation 2 has no target"
    real = next(t for pair in landed for t in pair if t)
    # Exactly 40 hex characters: a longer token is not a revision shape the reader matches at
    # all, and the first version of this control "mutated" a file into something its reader
    # could not see a commit in — 0 problems from a mutation that had happened.
    impostor = real[:7] + "9" * (40 - 7)
    assert len(impostor) == 40, f"the impostor token is {len(impostor)} characters, not 40"
    assert not _commit_exists(impostor), f"{impostor[:12]}… is a commit here, so it is not invented"
    invented = text.replace(f"`{real}`", f"`{impostor}`", 1)
    assert invented != text, "mutation 2 changed no bytes"
    found2 = _release_note_problems(invented)
    assert any(impostor[:12] in problem for problem in found2), (
        f"replacing the cited commit {real[:12]} with {impostor[:12]} — well-formed, not a "
        f"commit in this repository — was not reported: {found2}"
    )

    assert path.read_bytes() == original_bytes, (
        "docs/RELEASE-NOTES.md changed while it was being read"
    )


# --------------------------------------------------------------------------- #
# The dossier holds to the tree it declares
# --------------------------------------------------------------------------- #

#: The review dossier: the document an external reviewer reads to tell LabCairn's own work
#: from somebody else's. Its header declares the tree it describes, and that declaration is
#: a claim about this repository's own history.
DOSSIER = REPO / "docs" / "REVIEW-DOSSIER.md"

#: The tree the dossier says it describes.
_DECLARED_TREE = re.compile(r"\*\*Tree it describes:\*\*\s*`([0-9a-f]{7,40})`")

#: A path the dossier cites, read in the same shape ``tests/test_review_dossier.py`` reads
#: them: backticked, and rooted in one of the repository's own directories.
_DOSSIER_PATH = re.compile(r"`((?:src|tests|docs|scripts|examples|web|\.github)/[A-Za-z0-9_./-]+)`")

#: A test the dossier names as the witness for a LabCairn behaviour.
_DOSSIER_TEST = re.compile(r"tests/(test_[A-Za-z0-9_]+\.py)::(test_[A-Za-z0-9_]+)")

#: An ADR the dossier names.
_DOSSIER_ADR = re.compile(r"ADR-(\d{4})")


def _revision_exists(revision: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{revision}^{{commit}}"],
        cwd=REPO,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def _text_at(revision: str, path: str) -> str | None:
    """The file's text at `revision`, or None if that tree does not carry it."""
    result = subprocess.run(
        ["git", "show", f"{revision}:{path}"],
        cwd=REPO,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        return None
    return result.stdout.decode("utf-8", "replace")


def _supersession_marker(text: str) -> str:
    """The dossier's supersession marker: the blockquote that carries the phrase.

    The dossier has three blockquotes and only one of them marks a superseded sentence, so
    the marker is found by the phrase the 2026-11-12 convention settled on rather than by
    its position in the file.
    """
    blocks: list[str] = []
    current: list[str] = []
    for line in text.split("\n"):
        if line.lstrip().startswith(">"):
            current.append(line)
        elif current:
            blocks.append("\n".join(current))
            current = []
    if current:
        blocks.append("\n".join(current))
    for block in blocks:
        if "dated snapshot" in block.lower():
            return block
    return ""


def _dossier_exceptions(revision: str, text: str) -> list[str]:
    """Every claim the dossier makes that the tree it declares does not carry.

    **Three kinds of claim, and each one is about a tree.** A test the dossier names as a
    witness has to be defined at the declared tree: a reader who checks the claim there must
    find the witness. An ADR it names has to exist there. A path it points at has to be
    there.
    """
    exceptions: list[str] = []
    for file_name, function in sorted(set(_DOSSIER_TEST.findall(text))):
        body = _text_at(revision, f"tests/{file_name}")
        if body is None or f"def {function}(" not in body:
            exceptions.append(f"tests/{file_name}::{function}")
    adr_listing = subprocess.run(
        ["git", "ls-tree", "--name-only", revision, "--", "docs/adr/"],
        cwd=REPO,
        capture_output=True,
        check=False,
    ).stdout.decode("utf-8", "replace")
    for number in sorted(set(_DOSSIER_ADR.findall(text))):
        if not any(name.startswith(f"docs/adr/ADR-{number}-") for name in adr_listing.split("\n")):
            exceptions.append(f"ADR-{number}")
    for path in sorted(set(_DOSSIER_PATH.findall(text))):
        if not _existed_at(revision, path):
            exceptions.append(path)
    return exceptions


def _unnamed_exceptions(text: str, revision: str) -> list[str]:
    """The claims the dossier makes outside its declared tree that it does not name.

    A dossier that says "every claim below is about the tree at `dd08573`" and then cites
    something that tree does not carry is sending the reader to a tree where the evidence is
    not. The repair is not to hide the claim; it is to **name** it, in a marker, so that the
    reader knows which claims are later readings and which are about the declared tree.
    """
    marker = _supersession_marker(text)
    return [item for item in _dossier_exceptions(revision, text) if item not in marker]


def test_the_dossier_holds_to_the_tree_it_declares() -> None:
    """Every claim the dossier makes must be about the tree it declares, or be named.

    ``docs/REVIEW-DOSSIER.md`` says "**Tree it describes:** `dd08573` ... Every claim below
    is about the tree at that commit." A reader who opens that tree to check a claim must
    find what the claim leans on: the witness test, the ADR, the path. Where the dossier
    has since named something the declared tree does not carry, it must **say so** in its
    supersession marker, or the sentence sends the reader to a tree where the evidence is
    not.

    **Measured at the tree the dossier declares** (`dossier-labcairn-side.py` in the
    evidence folder): of the 24 witness tests, 12 ADRs and 59 paths the dossier names, two
    are not in that tree -- its own witness ``tests/test_review_dossier.py`` (added the same
    day, ``76d5e1c``) and
    ``tests/test_source_contracts.py::test_locator_kinds_are_closed_at_six_members`` (added
    2026-10-29, ``56595a1``). Both are named in the marker, which is what makes them
    legal rather than a mismatch.

    The one check here that can be skipped: a checkout without the declared revision cannot
    answer the question, and a check that guessed would be worse than one that says so.
    """
    text = DOSSIER.read_text(encoding="utf-8")
    match = _DECLARED_TREE.search(text)
    assert match, "the dossier declares no tree"
    revision = match.group(1)
    if not _revision_exists(revision):
        pytest.skip(f"{revision} is not in this checkout, so the question cannot be asked")

    unnamed = _unnamed_exceptions(text, revision)
    assert not unnamed, (
        f"the dossier declares the tree at {revision}, and these claims are not about it, "
        f"and its supersession marker does not name them:\n  " + "\n  ".join(unnamed)
    )


def test_the_dossier_tree_check_fails_when_the_marker_stops_naming_an_exception(
    repo_root: Path,
) -> None:
    """The reader is seen to fail for the property, on copies held in memory.

    **Two mutations.** (1) The supersession marker is removed from the copy: the dossier's
    two later claims are still there, nothing says they are later, and the reader must
    report both. This is the half that proves the marker -- not the claim -- is what makes
    a later claim legal. (2) A claim outside the declared tree is added to the copy, naming
    a file that tree does not have, and the reader must report it with the marker intact.

    **Control.** The real file's bytes are compared before and after, so the demonstration
    cannot write the record it guards.
    """
    path = repo_root / "docs" / "REVIEW-DOSSIER.md"
    original_bytes = path.read_bytes()
    text = original_bytes.decode("utf-8")
    match = _DECLARED_TREE.search(text)
    assert match, "the dossier declares no tree"
    revision = match.group(1)
    if not _revision_exists(revision):
        pytest.skip(f"{revision} is not in this checkout, so the question cannot be asked")

    assert _unnamed_exceptions(text, revision) == [], (
        f"the dossier as it stands already reports: {_unnamed_exceptions(text, revision)}"
    )

    # Mutation 1: the marker goes, the claims stay.
    marker = _supersession_marker(text)
    assert marker, "the dossier carries no supersession marker, so mutation 1 has no target"
    stripped = text.replace(marker, "", 1)
    assert stripped != text, "mutation 1 changed no bytes"
    assert _supersession_marker(stripped) == "", "the marker survived the removal"
    found = _unnamed_exceptions(stripped, revision)
    assert found, "removing the marker left the later claims unreported"
    assert set(found) == set(_dossier_exceptions(revision, text)), (
        f"removing the marker reported {found}, but the claims outside the declared tree "
        f"are {_dossier_exceptions(revision, text)}"
    )

    # Mutation 2: a claim outside the declared tree, with the marker intact.
    invented = "tests/test_a_file_the_declared_tree_does_not_have.py"
    assert not _existed_at(revision, invented), f"{invented} is in the tree at {revision}"
    extended = text + f"\n\nThe behaviour is witnessed by `{invented}`.\n"
    found2 = _unnamed_exceptions(extended, revision)
    assert invented in found2, (
        f"a claim naming {invented}, which the declared tree does not carry, was not "
        f"reported even though the marker is intact: {found2}"
    )

    assert path.read_bytes() == original_bytes, (
        "docs/REVIEW-DOSSIER.md changed while it was being read"
    )


# --------------------------------------------------------------------------
# the pointers a reader follows carry the words they cite
# --------------------------------------------------------------------------

#: **The format, as the owner settled it on 2026-11-12.** A converted pointer is
#:
#: ``path/to/file.ext:LINE`` — ``the words on that line``
#:
#: — the pointer and a span of **the words actually printed on that line** — and a document
#: that has converted its pointers prints how many of them there are, under its title:
#:
#: ``**Anchors:** N — every converted pointer below carries the words it cites.``
#:
#: This is the rule ``tests/test_review_dossier.py`` already holds ``docs/REVIEW-DOSSIER.md``
#: to, applied to the documents a reader follows today. A stored line number is a claim about
#: one revision of a file another batch edits: after the file grows, the pointer still *looks*
#: like a citation and points at a different line, and nothing noticed. Carrying the wording
#: turns the pointer into a lookup that can be checked, and turns the failure into a useful
#: one -- the wording is **found**, and the report names the line it moved to.
#:
#: **A pointer without words is not read.** The conversion is happening in several windows,
#: and 553 single-line pointers exist across 62 documents today; a check that reddened on the
#: documents that have not converted yet is a check people route around. The declaration is
#: what opts a document in -- which is also the gap: a document that never declares is
#: unchecked, and that is stated here rather than hidden.

#: The count a converted document declares. **Only the number is read**, because a document
#: that reworded the sentence beside it would otherwise switch the watch off silently -- the
#: failure this file exists for. The contract's sentence is quoted in the failures, so a
#: document that mis-declares is legible rather than merely unwatched.
_ANCHOR_DECLARATION = re.compile(r"^\*\*Anchors:\*\*[ \t]+(?P<count>\d+)\b", re.MULTILINE)

#: A pointer: a path and one line number, in backticks. A **span** citation (``:120-135``) is
#: not this form and is not read here. 266 spans exist across 28 documents today; that is a
#: gap in the format, recorded rather than papered over with a rule nobody agreed to.
_POINTER = re.compile(r"`(?P<path>[^`\s:]+):(?P<line>\d{1,6})`")

#: The shape a path segment has to have before the token is read as a pointer at all: a name,
#: a dot, and an extension that **starts with a letter**. Directory separators are part of the
#: name; `docs/plans/PHASE_3-work-orders.md` is a pointer and must survive the shape check.
#:
#: **Why this exists.** Nine documents in this tree write ``127.0.0.1:8000`` and
#: ``localhost:4317`` in backticks -- a host and a port, not a file and a line. Matched
#: against the pattern above, ``127.0.0.1:8000`` is a path of ``127.0.0.1`` and a line of
#: 8000, and the document that carries it would be told a file does not exist. Nine such
#: tokens sit in documents today that declare nothing, so they are not read today either;
#: the day one of those documents converts a pointer is the day the false report arrives,
#: and a witness is not allowed to be *almost* right about the document that opts in.
#:
#: The cost is stated: an extensionless file (``Makefile:12``) is not read either. Measured
#: at `f92e556`, every extensionless ``name:NUMBER`` token in the tree -- 33 of them -- is
#: either a host and port, or a symbol citation in an upstream study (`_step:707`), or a
#: section citation in an ADR (`ADR-0002:391`). Not one names a file this repository carries.
#: `test_the_pointer_pattern_reads_a_file_and_not_a_host` holds that measurement, so the day
#: the rule starts skipping something real is noticed rather than absorbed.
_FILE_SHAPED_PATH = re.compile(r"^[A-Za-z0-9_/+.\-]*\.[A-Za-z][A-Za-z0-9]*$")

#: The words a converted pointer carries: an em dash -- ``--`` accepted too, because a document
#: typed without an em dash has reworded rather than broken -- and a backtick span. The leading
#: ``\s*`` crosses a line break, so a pointer left at the end of a line by a wrapping editor is
#: still read; the span itself is read on one line.
_ANCHOR_TAIL = re.compile(r"(?P<gap>\s*)(?:—|--)[ \t]*`(?P<words>[^\n`]+)`")

#: A pointer that is a link **label**: ``[`path:LINE`](target)``. Nine such pointers exist
#: today, and the format as written cannot be applied to one -- the words would have to sit
#: either inside the label, making the link's own text carry the citation, or after the
#: closing parenthesis, where a reader-only pattern would not find them. This reads the second
#: shape, and resolves the file from the link's **target**, which is where the document
#: actually says the file is. ``docs/ROADMAP.md:88`` is this shape, and it is one of the two
#: example documents, so the extension is not theoretical.
_LINK_CLOSE = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+[\"'][^\"']*[\"'])?\s*\)")

#: Below this a quoted span does not identify a line. A short span is **reported**, never
#: treated as an unconverted pointer: a rule that silently skips its own violations is the rule
#: that stops working.
_MIN_ANCHOR_WORDS = 12


def _fenced_lines(text: str) -> set[int]:
    """The 1-based lines **inside** a fenced block, fence lines included.

    A document that quotes this format inside a fence is *illustrating* it. Reading the
    example as a pointer would hold the document that explains the rule to it, which is how a
    check starts firing on correct prose.
    """
    out: set[int] = set()
    fence: str | None = None
    for number, line in enumerate(text.splitlines(), start=1):
        marker = _FENCE.match(line)
        if marker:
            token = marker.group(1)
            fence = None if fence == token else (fence or token)
            out.add(number)
            continue
        if fence is not None:
            out.add(number)
    return out


def _tracked_markdown() -> list[Path]:
    """Every tracked Markdown file. Tracked, not merely present: a scratch file in the
    checkout is not a record, and it is not what a reader opens."""
    result = subprocess.run(
        ["git", "ls-files", "-z", "*.md"],
        cwd=REPO,
        capture_output=True,
        check=False,
    )
    return [REPO / name for name in result.stdout.decode("utf-8").split("\0") if name]


def _flat(value: str) -> str:
    """Whitespace-normalised text -- the comparison the format states."""
    return re.sub(r"\s+", " ", value).strip()


def _word_lines(lines: list[str], needle: str, limit: int = 8) -> list[int]:
    """Every 1-based line of the cited file that carries ``needle``.

    **This is the report.** A stored number that no longer carries the wording is not
    information; the lines that *do* carry it are. `tests/test_review_dossier.py` found that
    its earlier failures accused records of losing text that had only moved, and named no
    destination.
    """
    return [n for n, text in enumerate(lines, 1) if needle in _flat(text)][:limit]


def _cited_file(doc: Path, cited: str, href: str | None = None) -> Path | None:
    """The file a cited path names: repo-root-relative, or relative to the document.

    Both are used in this tree -- measured at `3fcfbf6`: 238 pointers resolve from the root
    and 5 from their own directory. A pointer that resolves neither is a pointer to nothing,
    and the 117 that resolve only under a written-out prefix (`application/context.py` for
    `src/labcairn/application/context.py`) are named in the report rather than forgiven here.

    For a link-labelled pointer the link's **target** is tried last: the document said where
    the file is, and the label is the shorter spelling of the same thing. It is tried last so
    a label that names the wrong file is still reported when the target does not rescue it.
    """
    candidates = [REPO / cited, doc.parent / cited]
    if href:
        candidates += [REPO / href, doc.parent / href]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _declarations(text: str) -> list[re.Match[str]]:
    """The anchor-count declarations outside fenced examples."""
    fenced = _fenced_lines(text)
    return [
        match
        for match in _ANCHOR_DECLARATION.finditer(text)
        if text[: match.start()].count("\n") + 1 not in fenced
    ]


def _anchored_pointers(
    text: str, fenced: set[int], shape: re.Pattern[str] = _FILE_SHAPED_PATH
) -> list[tuple[int, str, int, str, str | None]]:
    """Each ``(line here, cited path, cited line, words, link target)`` in the anchored form.

    A pointer whose words sit **after** the pointer is the plain form. A pointer that is a
    link label -- ``[`path:LINE`](target)`` -- has its words after the closing parenthesis, and
    its target is carried so the file can be resolved from what the document says the path is.
    A pointer followed by a *different* backtick span that is not an anchor (no dash) is left
    alone: an ordinary citation beside an ordinary citation is not a broken anchor.
    """
    out: list[tuple[int, str, int, str, str | None]] = []
    for match in _POINTER.finditer(text):
        here = text[: match.start()].count("\n") + 1
        if here in fenced:
            continue
        if not shape.match(match.group("path")):
            continue
        start = match.end()
        href: str | None = None
        link = _LINK_CLOSE.match(text, start)
        if link is not None:
            href = link.group(1)
            start = link.end()
        tail = _ANCHOR_TAIL.match(text, start)
        if tail is None or tail.group("gap").count("\n") > 1:
            continue
        out.append((here, match.group("path"), int(match.group("line")), tail.group("words"), href))
    return out


def _anchor_problems(doc: Path, text: str, lines_of: dict[Path, list[str]]) -> list[str]:
    """Every anchored pointer in ``doc`` that would mislead a reader following it today."""
    name = doc.relative_to(REPO)
    fenced = _fenced_lines(text)
    pointers = _anchored_pointers(text, fenced)
    found = _declarations(text)
    if not found:
        return []

    problems: list[str] = []
    if len(found) > 1:
        problems.append(
            f"{name} declares an anchor count {len(found)} times; a document makes one "
            "count claim, and two counts cannot both be the document's own"
        )
    declared = int(found[0].group("count"))
    if declared != len(pointers):
        problems.append(
            f"{name} declares **Anchors:** {declared} and carries {len(pointers)} anchored "
            f"pointer(s): {[(p[1], p[2]) for p in pointers[:6]]}"
        )

    for here, path, line, words, href in pointers:
        target = _cited_file(doc, path, href)
        if target is None:
            problems.append(
                f"{name}:{here} anchors `{path}:{line}` and no file resolves that path -- "
                "neither from the repository root nor from the document's own directory"
                + (f" nor the link target {href!r}" if href else "")
            )
            continue
        if target not in lines_of:
            lines_of[target] = target.read_text(encoding="utf-8").splitlines()
        cited_lines = lines_of[target]
        needle = _flat(words)

        if len(words) < _MIN_ANCHOR_WORDS:
            problems.append(
                f"{name} anchors `{path}:{line}` with the {len(words)}-character span "
                f"{words!r}; the format asks for at least {_MIN_ANCHOR_WORDS} characters, "
                "and a span that short does not identify a line"
            )
        if line > len(cited_lines):
            where = _word_lines(cited_lines, needle)
            problems.append(
                f"{name} cites `{path}:{line}` — `{words}` — and {path} has "
                f"{len(cited_lines)} lines. "
                + (
                    f"The words are on line{'s' if len(where) != 1 else ''} "
                    f"{', '.join(str(n) for n in where)}."
                    if where
                    else f"The words are not in {path} at all."
                )
            )
            continue
        if needle in _flat(cited_lines[line - 1]):
            continue
        where = _word_lines(cited_lines, needle)
        problems.append(
            f"{name} cites `{path}:{line}` — `{words}` — and {path}:{line} does not carry "
            "them. "
            + (
                f"They are on line{'s' if len(where) != 1 else ''} "
                f"{', '.join(str(n) for n in where)} of {path}."
                if where
                else f"They are not in {path} at all."
            )
        )
    return problems


def test_every_declared_anchor_carries_the_line_and_the_words_it_cites() -> None:
    """A document that declares how many pointers carry their words is held to both.

    Each tracked Markdown file that prints ``**Anchors:** N`` is read: it must carry exactly
    N anchored pointers, each cited file must exist, each cited line must be inside it, and
    each carried span must be on the line it is cited for -- whitespace-normalised, at least
    twelve characters. Where the span is not there, the failure names the line it **is** on,
    because the wording is the anchor and the number is the thing being checked.
    """
    lines_of: dict[Path, list[str]] = {}
    declared: list[Path] = []
    problems: list[str] = []
    for doc in _tracked_markdown():
        text = doc.read_text(encoding="utf-8")
        if not _declarations(text):
            continue
        declared.append(doc)
        problems.extend(_anchor_problems(doc, text, lines_of))

    assert declared, (
        "no tracked document declares an anchor count, so this check reports success over a "
        "tree whose pointers it has not read"
    )
    assert not problems, (
        f"{len(declared)} document(s) declare an anchor count "
        f"({', '.join(str(d.relative_to(REPO)) for d in declared)}) and {len(problems)} "
        "pointer(s) fail it:\n  " + "\n  ".join(problems)
    )


def test_the_anchor_check_fails_when_a_pointer_or_its_words_are_wrong() -> None:
    """The check above is seen to fail for the property, on copies in memory.

    **Five mutations, each a distinct way the rule is real.** (1) A line number moves by
    three while the cited file is untouched: the pointer keeps its shape and points at the
    wrong line, and the failure must say where the wording actually is. (2) The carried words
    are replaced by a phrase the cited file does not carry: the pointer keeps a plausible
    shape and its content is fiction. (3) An anchor's words are deleted, leaving a bare
    pointer: the document's own count claim breaks. (4) The cited path is renamed to a
    plausible sibling that has never existed: the line number and the words are both fine and
    there is nothing to read. (5) The carried words are shortened below the format's floor.

    **And one control that is a finding, not a pass.** With the declaration removed, the same
    broken pointer reports nothing. That is the format's gap as stated -- a document that
    never declares is not watched -- and this control is here so the gap is *measured* rather
    than assumed away by a reader who believes the check covers the tree.

    **Controls.** The unmutated documents report nothing, so every report below is the
    mutation; each mutation is asserted to change bytes before any report is credited to it;
    and the real documents' bytes are compared before and after.
    """
    docs = [d for d in _tracked_markdown() if _declarations(d.read_text(encoding="utf-8"))]
    assert docs, "no document declares an anchor count, so this control tests nothing"
    texts = {d: d.read_text(encoding="utf-8") for d in docs}
    bytes_before = {d: d.read_bytes() for d in docs}

    def problems_for(mutated: dict[Path, str]) -> list[str]:
        shared: dict[Path, list[str]] = {}
        out: list[str] = []
        for doc in docs:
            out.extend(_anchor_problems(doc, mutated[doc], shared))
        return out

    assert problems_for(texts) == [], (
        f"the records as they stand already report: {problems_for(texts)}"
    )

    # The document with the most anchors carries the most ways to break it.
    doc = max(
        docs, key=lambda d: (len(_anchored_pointers(texts[d], _fenced_lines(texts[d]))), str(d))
    )
    pointers = _anchored_pointers(texts[doc], _fenced_lines(texts[doc]))
    assert pointers, f"{doc.relative_to(REPO)} declares a count and carries no pointer"
    _, path, line, words, _href = pointers[0]

    # Mutation 1: the line number moves; the cited file does not.
    moved = texts[doc].replace(f"`{path}:{line}`", f"`{path}:{line + 3}`", 1)
    assert moved != texts[doc], "mutation 1 changed no bytes"
    found1 = problems_for({**texts, doc: moved})
    assert any(f"{path}:{line + 3}" in problem for problem in found1), (
        f"moving the pointer from {path}:{line} to {path}:{line + 3} was not reported: {found1}"
    )
    assert any(str(line) in problem for problem in found1), (
        f"the failure for {path}:{line + 3} did not name line {line}, where the words really "
        f"are: {found1}"
    )

    # Mutation 2: the words are replaced by something the cited file does not carry.
    invented = "a phrase this cited file does not carry"
    assert len(invented) >= _MIN_ANCHOR_WORDS
    falsified = texts[doc].replace(f"`{words}`", f"`{invented}`", 1)
    assert falsified != texts[doc], "mutation 2 changed no bytes"
    found2 = problems_for({**texts, doc: falsified})
    assert any(invented in problem for problem in found2), (
        f"carrying words the cited file does not print was not reported: {found2}"
    )
    assert any("not in" in problem for problem in found2), (
        f"the failure did not say the words are absent from the cited file: {found2}"
    )

    # Mutation 3: the words go, the pointer stays -- and the document's count claim breaks.
    match = re.search(rf"`{re.escape(path)}:{line}`", texts[doc])
    assert match is not None
    tail = _ANCHOR_TAIL.match(texts[doc], match.end())
    assert tail is not None, "the anchor's words were not readable after the pointer"
    unanchored = texts[doc][: tail.start()] + texts[doc][tail.end() :]
    assert unanchored != texts[doc], "mutation 3 changed no bytes"
    found3 = problems_for({**texts, doc: unanchored})
    assert any("**Anchors:**" in problem for problem in found3), (
        f"deleting an anchor's words left the declared count unchallenged: {found3}"
    )

    # Mutation 4: the path becomes a plausible sibling that has never existed.
    directory, _, name = path.rpartition("/")
    bogus = f"{directory}/never-existed-{name}"
    assert _cited_file(doc, bogus) is None, f"{bogus} exists, so this mutation tests nothing"
    renamed = texts[doc].replace(f"`{path}:{line}`", f"`{bogus}:{line}`", 1)
    assert renamed != texts[doc], "mutation 4 changed no bytes"
    found4 = problems_for({**texts, doc: renamed})
    assert any(bogus in problem for problem in found4), (
        f"renaming {path} to {bogus} -- a path that has never existed -- was not reported: {found4}"
    )

    # Mutation 5: the carried words fall below the format's floor.
    short = "the route"
    assert len(short) < _MIN_ANCHOR_WORDS
    shortened = texts[doc].replace(f"`{words}`", f"`{short}`", 1)
    assert shortened != texts[doc], "mutation 5 changed no bytes"
    found5 = problems_for({**texts, doc: shortened})
    assert any("characters" in problem for problem in found5), (
        f"a {len(short)}-character span was not reported as too short: {found5}"
    )

    # Control: without the declaration, the same broken pointer is invisible. The gap is the
    # format's, stated in the format -- and measured here so nobody has to discover it by
    # trusting a green run.
    silent = {**texts, doc: _ANCHOR_DECLARATION.sub("", moved, count=1)}
    assert silent[doc] != moved, "the control's declaration removal changed no bytes"
    assert problems_for(silent) == [], (
        "a document with its declaration removed and a wrong pointer still reported something"
    )

    for target, original in bytes_before.items():
        assert target.read_bytes() == original, (
            f"{target.relative_to(REPO)} changed while it was read"
        )


# --------------------------------------------------------------------------
# the shape rule that keeps a host and a port out of the pointer pattern
# --------------------------------------------------------------------------

#: The same pattern with **no shape rule at all**: every ``[^`\s:]+`` the pointer pattern can
#: produce is accepted as a path. This is what the guard replaced, and it is what the first
#: half of the witness below reads a document with.
_ANY_PATH = re.compile(r"^[^`\s:]+$")

#: A dotted quad -- the shape the shape rule exists to reject. Four dot-separated numbers.
_HOST_TOKEN = re.compile(r"^\d+\.\d+\.\d+\.\d+$")


def _tokens_the_shape_rule_rejects() -> list[tuple[Path, int, str, int]]:
    """Every ``name:NUMBER`` in a tracked document that the shape rule will not read as a file.

    Read through the witness's own patterns -- `_POINTER` and `_FILE_SHAPED_PATH` -- not
    through a second copy of them, because a measurement that re-implements what it is
    measuring only agrees with itself.
    """
    out: list[tuple[Path, int, str, int]] = []
    for doc in _tracked_markdown():
        text = doc.read_text(encoding="utf-8")
        fenced = _fenced_lines(text)
        for match in _POINTER.finditer(text):
            here = text[: match.start()].count("\n") + 1
            if here in fenced or _FILE_SHAPED_PATH.match(match.group("path")):
                continue
            out.append((doc, here, match.group("path"), int(match.group("line"))))
    return out


def test_the_pointer_pattern_reads_a_file_and_not_a_host() -> None:
    """A host and a port is not a file and a line, and the rule separating them skips nothing real.

    **Both halves are watched, because the guard can fail in either direction.**

    *It lets something through that is not a file.* Nine tracked documents write
    ``127.0.0.1:8000`` and ``localhost:4317`` in backticks. Read as a pointer,
    ``127.0.0.1`` is a path and ``8000`` is a line, and the document carrying it is told a
    file does not exist -- a red that is not about the property. The probe below is a document
    that declares an anchor count and carries a host-and-port beside its words: with the guard
    off it reports a missing file, and with the guard as shipped it reports nothing.

    *It keeps something out that is a file.* The shape rule accepts a dot and an extension
    beginning with a letter, so an extensionless file is not read. Measured through the
    witness's own patterns at `f92e556`, **41** ``name:NUMBER`` tokens are rejected, and not
    one of them names a file this repository tracks -- they are hosts and ports, symbol
    citations in the upstream studies (`_step:707`, `FilesystemPermission:366`), a section
    citation in an ADR (`ADR-0002:391`) and one measurement row (`l=2`). This asserts that
    measurement, so the day the rule starts skipping something real -- a `Makefile:12` in a
    document that converted its pointers -- the check goes red and names it, instead of the
    pointer quietly going unread. `.gitignore:4` is in the accepted set precisely because
    a leading dot is a file's name and not an extension.
    """
    # **Half one: the guard is doing the work it claims.** The probe is synthetic text; the
    # document path only supplies how a relative path would resolve.
    probe_text = (
        "# Probe\n\n"
        "**Anchors:** 1 — every converted pointer below carries the words it cites.\n\n"
        "The service listens on `127.0.0.1:8000` — `bound to the loopback address`.\n"
    )
    probe_doc = REPO / "README.md"

    loose: list[str] = []
    loose_pointers = _anchored_pointers(probe_text, _fenced_lines(probe_text), _ANY_PATH)
    assert len(loose_pointers) == 1, (
        "the probe no longer carries the host-and-port token the guard exists for, so this "
        "witness tests nothing"
    )
    for _here, path, line, _words, href in loose_pointers:
        if _cited_file(probe_doc, path, href) is None:
            loose.append(f"{path}:{line} resolves to no file")
    assert loose, "with the shape rule off, the host-and-port token resolved to a file"

    guarded = _anchor_problems(probe_doc, probe_text, {})
    assert guarded, (
        "the probe declares 1 anchor and the guard skips the only candidate, so the count "
        "claim itself went unreported: the guard must not silence the document's own count"
    )
    assert not any("127.0.0.1" in problem for problem in guarded), (
        f"the guard did not keep the host-and-port token out of the report: {guarded}"
    )

    # **Half two: what the guard rejects names nothing real.** The tripwire.
    rejected = _tokens_the_shape_rule_rejects()
    assert rejected, "no tracked document carries a host-and-port or symbol token at all"
    tracked = {Path(name) for name in _tracked_files()}
    real = [
        (doc, here, name, line)
        for doc, here, name, line in rejected
        if Path(name) in tracked or (doc.parent / name) in tracked
    ]
    assert not real, (
        f"the shape rule skips {len(real)} token(s) that name a file this repository tracks: "
        f"{real[:6]}. The pattern is now silently leaving real pointers unread -- widen it "
        "rather than leave the pointers unwatched."
    )
    hosts = [entry for entry in rejected if _HOST_TOKEN.match(entry[2])]
    assert hosts, (
        "none of the rejected tokens is a host and port, so the guard is being tested against "
        "a tree that does not contain the thing it was written for"
    )
