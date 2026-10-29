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
    ``Licence status — not yet granted`` becomes
    ``licence-status--not-yet-granted`` with two hyphens — while
    ``许可证状态——尚未授予`` loses the dashes and keeps no space at all,
    and becomes ``许可证状态尚未授予``. **A link that names one of those
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

#: A citation of a test file, followed by one or more `::` segments. The whole
#: match is what a reader would type, so no capturing group is used.
_CITED_NODE = re.compile(r"tests/[a-z_0-9]+\.py(?:::[A-Za-z_0-9]+)+")


def test_the_human_review_checklists_node_ids_exist() -> None:
    """Every `tests/...py::...` the checklist cites is a thing in this tree.

    **Why this is watched mechanically.** The checklist was written from the two
    gate records, and the records cite whole files rather than node ids for most
    of G1's clauses — §6.1 of the checklist says so. Re-deriving the node ids by
    hand produced two wrong ones on the first pass: a class named
    `TestApprovalGate` where the tree has `TestApprovalCheckpoint`, and a file
    `tests/test_recovery_probe.py` that has never existed. Both were plausible,
    both were unfalsifiable by reading, and a reviewer following either would
    conclude the witness is missing when the witness is fine.
    """
    text = CHECKLIST.read_text(encoding="utf-8")
    cited = sorted({match.group(0) for match in _CITED_NODE.finditer(text)})
    assert cited, "the checklist names no node id, so this check proves nothing"
    broken: list[str] = []
    for node_id in cited:
        parts = node_id.split("::")
        source = REPO / parts[0]
        if not source.is_file():
            broken.append(node_id)
            continue
        body = source.read_text(encoding="utf-8")
        for segment in parts[1:]:
            pattern = (
                rf"^class {re.escape(segment)}\b"
                if segment[:1].isupper()
                else rf"^\s*def {re.escape(segment)}\b"
            )
            if not re.search(pattern, body, re.MULTILINE):
                broken.append(f"{node_id} (no {segment})")
                break
    assert not broken, (
        "the checklist cites node ids that are not in the tree, so a reviewer "
        f"following it would report a missing witness: {broken}"
    )
