"""The P1 review dossier, watched.

``docs/REVIEW-DOSSIER.md`` is the document an external reviewer reads to tell
which of LabCairn's designs are its own and which were informed by upstream
work. A dossier like that is worth reading only if it is true, and a dossier
that is true until a file moves or a document is edited stops being true
without saying so.

So this file watches three things, and the second of them is the point.

**First, the citations.** Every ``path:line`` the dossier names must resolve to
a file this repository owns and a line inside that file. Every test it cites
must exist. Every ADR it names must exist. Every relative link must resolve.

**Second, the upstream facts.** The dossier leans on
``docs/UPSTREAM_REFERENCES.md`` for what upstream is, where it was read and
under what licence. Those facts are re-derived **from the catalogue** here and
compared with the dossier: the five repositories, their commit SHAs and their
licences. A dossier that names a SHA upstream does not carry, or a licence
upstream does not carry, is caught here rather than by a reader who happens to
know the answer.

**Third, the boundary the dossier claims.** The dossier says no upstream source
is in this repository. This file checks that it names no path into the
reference clones, and that it names no commit SHA except the five the
catalogue records for the repositories that were actually cloned.

What this file deliberately does **not** do
--------------------------------------------
It does not watch the sentences. A test that watched prose would be watching
its own imagination, and a rewrite that changed nothing true would turn it
red. What it watches are *citations* and *numbers*, because those are what a
reader follows and what rots when the tree moves.

The determinism rule holds: no wall clock, no RNG, no network and no
subprocess. The only I/O is reading the repository's own files.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final, NamedTuple

#: The document this file watches.
DOSSIER: Final[Path] = Path("docs") / "REVIEW-DOSSIER.md"

#: The catalogue the dossier's upstream claims are measured against.
CATALOGUE: Final[Path] = Path("docs") / "UPSTREAM_REFERENCES.md"

#: A ``path:line`` or ``path:line-line`` citation, as the document writes them.
_CITATION = re.compile(r"`([A-Za-z0-9_./\\-]+\.(?:py|ts|tsx|md|json|html)):(\d+)(?:-(\d+))?`")

#: An upstream anchor: the line of the catalogue the document leans on.
_ANCHOR = re.compile(r"UPSTREAM_REFERENCES\.md:(\d+(?:-\d+)?)")

#: A path the document names, with or without a line number.
_PATH = re.compile(r"`((?:src|tests|docs|scripts|examples|web|\.github)/[A-Za-z0-9_./-]+)`")

#: A test the document cites.
_TEST_FUNCTION = re.compile(r"tests/(test_[A-Za-z0-9_]+\.py)::(test_[A-Za-z0-9_]+)")

#: An ADR the document names.
_ADR = re.compile(r"ADR-(\d{4})")

#: A commit SHA.
_SHA = re.compile(r"\b[0-9a-f]{40}\b")

#: A relative markdown link.
_LINK = re.compile(r"\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+[\"'][^\"']*[\"'])?\s*\)")

#: A row of the catalogue's table of cloned repositories.
_CATALOGUE_ROW = re.compile(
    r"^\|\s*`(?P<name>[A-Za-z0-9_.-]+)`\s*\|"
    r"\s*(?P<url>https://github\.com/[^|\s]+)\s*\|"
    r"\s*[^|]*\|"
    r"\s*(?P<licence>[^|]*)\|"
    r"\s*`(?P<sha>[0-9a-f]{40})`\s*\|"
)

#: A licence name, as the catalogue writes it.
_LICENCE = re.compile(r"MIT|Apache-2\.0|AGPL-3\.0")

#: The directory families the reference clones live in. A dossier may name the
#: glob that excludes them; it may not name a path inside them.
_REFERENCE_DIRECTORIES: Final[tuple[str, ...]] = (
    "_references/",
    ".upstreams/",
    "labcairn-upstreams/",
)


class Anchor(NamedTuple):
    """One catalogue line the dossier leans on, anchored **by its wording**.

    ``token`` is the anchor as the dossier writes it — ``"197"`` or ``"114-127"``.
    ``fragment`` is the wording that makes the line worth citing, and it is the
    anchor: the line is *found from it*, and the number the dossier cites is then
    checked against where it was found. ``citations`` is how many times the dossier
    cites it.

    **Why the wording is the anchor.** A stored line number is a claim about one
    revision of a file that other batches edit. Replaying the old stored-number
    tests on the tree where 21 lines were inserted into
    ``docs/UPSTREAM_REFERENCES.md`` (``dossier-old-tests-replay.py`` in the
    evidence folder): 3 blank-line failures, 9 "fragment not at its line" failures,
    **and no broken anchor escaped both** — the old mechanism saw the drift. What it
    could not do was describe it truthfully. Each of the 9 read
    ``CATALOGUE:156 no longer carries '<wording>', which is what :156 is cited
    for``, which accuses the record of losing the wording. In all 9 the wording was
    intact exactly ten lines lower, and in 7 of the 9 the cited line was not blank
    at all — so the message read as "the record lost the wording" when the number
    had moved; and none of the 9 said where the wording had gone. Finding the
    wording first turns the report into a lookup, and adds the one check the old
    tests had not: a wording present on more
    than one line anchors nothing (see
    :func:`test_every_load_bearing_anchor_carries_the_wording_it_is_cited_for`).
    """

    token: str
    fragment: str
    citations: int


def _span(token: str) -> tuple[int, int]:
    """The first and last catalogue line a citation token covers: ``1`` for ``"197"``,
    14 lines for ``"114-127"``."""
    start, _, end = token.partition("-")
    return int(start), int(end) if end else int(start)


def _find_fragment(lines: list[str], fragment: str) -> list[int]:
    """Every 1-based line of the catalogue that carries ``fragment``."""
    return [number for number, text in enumerate(lines, start=1) if fragment in text]


#: Every catalogue line the dossier leans on, each anchored **by its wording**.
#:
#: The wording is the anchor; the line number the dossier cites is *found from it*
#: and then checked against it. A stored line number is a claim about one revision
#: of a file other batches edit — `docs/UPSTREAM_REFERENCES.md` gained 21 lines from
#: another batch and every stored number below shifted. Replaying the old tests on
#: that tree (`dossier-old-tests-replay.py` in the evidence folder): 3 blank-line
#: failures and 9 "fragment not at its line" failures, and **nothing escaped both** —
#: the old mechanism did detect the drift. What it could not do was describe it: each
#: of the 9 said `CATALOGUE:<n> no longer carries '<wording>'`, accusing the record
#: of losing text that was intact ten lines lower, and not one said where it had
#: gone. A wording is unique in the catalogue (measured: 37 of 37), so the number can
#: be checked instead of trusted, and a wording that stops being unique is reported
#: instead of silently resolved to its first match.
_LOAD_BEARING: Final[tuple[Anchor, ...]] = (
    Anchor("30", "verified by opening the LICENSE files at the pinned commit", 3),
    Anchor("32", "On 2026-11-02 all five pins were verified against the remote", 2),
    Anchor("34", "resolved all five commits against GitHub at review time", 2),
    Anchor("38-48", "| ID | GitHub | Study areas |", 1),
    Anchor("45-48", "| `opencode` | https://github.com/anomalyco/opencode |", 1),
    Anchor("48", "| `ai-scientist-v2` |", 1),
    Anchor("50", "an invented or guessed SHA is worse than a blank", 1),
    Anchor("52", "a capability counts only when a code path constructs it", 3),
    Anchor("54", "## Verified license boundaries (measured 2026-10-15)", 2),
    Anchor("56", "a root statement is not a repository statement", 1),
    Anchor("58-64", "| Clone | LICENSE files | What they actually say |", 1),
    Anchor("68", "GNU Affero General Public License v3", 1),
    Anchor(
        "70",
        "it depends on `PyMuPDF>=1.24.12`, which is itself AGPL/commercial dual-licensed",
        1,
    ),
    Anchor(
        "74",
        'Any statement of the form "PaperQA2 is Apache-2.0" is **incomplete**',
        1,
    ),
    Anchor("75", "is **study-only** for LabCairn", 2),
    Anchor("76", "The AGPL boundary is a *component* boundary", 1),
    Anchor("81", "collection of agent skills", 1),
    Anchor("83", "439 `.py` files and 570 `.md` files", 1),
    Anchor("85", "This makes it a non-executable asset", 1),
    Anchor("87", "OpenCode uses a different core language stack", 2),
    Anchor("114-127", "## Reference → decision → test workflow", 1),
    Anchor(
        "127",
        "never claim superiority from source-code inspection alone",
        1,
    ),
    Anchor("141", "are **untrusted input**", 1),
    Anchor("142", "139 files named `AGENTS.md`, `CLAUDE.md` or `SKILL.md`", 1),
    Anchor("143", "`paperspine` is the sharpest instance", 1),
    Anchor("144", "Cloning does **not** imply executing", 1),
    Anchor("146", "Don't commit third-party source trees", 1),
    Anchor(
        "147",
        "Never ingest all upstream code into a model context by default",
        1,
    ),
    Anchor(
        "166",
        "Throughout this section the reference paths to exclude are, as glob patterns",
        1,
    ),
    Anchor("173", "Assert that `git ls-files` output contains no reference path", 1),
    Anchor(
        "174",
        "neither the `git ls-files` listing nor the member names of the built sdist",
        1,
    ),
    Anchor("183", "The sibling directory is unprotected", 1),
    Anchor("195", "No hard runtime/CI dependency on reference clones", 1),
    Anchor("196", "no upstream source was copied or adapted", 1),
    Anchor(
        "197",
        "P1 review dossier names relevant upstream designs and clearly identifies",
        2,
    ),
    Anchor("201", "A build system now exists", 1),
    Anchor("202", "`reference-exclusion` is a required status check", 2),
)


def _repo_root() -> Path:
    """The repository root.

    Derived from this file's own location rather than from the working
    directory, because the working directory is whatever the runner chose and
    a test that resolves its own repository relative to that is a test that
    passes in one place and fails in another.
    """
    return Path(__file__).resolve().parent.parent


def _dossier_text() -> str:
    """The dossier's text."""
    return (_repo_root() / DOSSIER).read_text(encoding="utf-8")


def _catalogue_lines() -> list[str]:
    """The catalogue's lines."""
    return (_repo_root() / CATALOGUE).read_text(encoding="utf-8").splitlines()


def _catalogue_rows() -> list[dict[str, str]]:
    """The catalogue's rows for the repositories that were cloned.

    A row that records a commit SHA is a repository that was cloned; a row
    whose SHA cell says ``not cloned`` is not one, and no row of that kind is
    returned here.
    """
    rows: list[dict[str, str]] = []
    for line in _catalogue_lines():
        match = _CATALOGUE_ROW.match(line)
        if match is not None:
            rows.append(match.groupdict())
    return rows


# --------------------------------------------------------------------------- #
# The document exists
# --------------------------------------------------------------------------- #


def test_the_dossier_is_there() -> None:
    """The document this file watches exists and is not a stub.

    Without this, every other test in this file would fail for the same
    uninformative reason — a missing file — and the difference between "the
    dossier is wrong" and "the dossier is gone" would be invisible.
    """
    path = _repo_root() / DOSSIER
    assert path.is_file(), f"{DOSSIER} is not there"
    text = path.read_text(encoding="utf-8")
    assert len(text) > 20000, (
        f"{DOSSIER} is {len(text)} characters. A dossier that names no upstream "
        f"design, no refusal and no witness is not one."
    )


# --------------------------------------------------------------------------- #
# The citations resolve
# --------------------------------------------------------------------------- #


def test_every_citation_resolves_to_a_file_and_a_line() -> None:
    """Every ``path:line`` the dossier names must point at something real.

    A citation is the dossier's evidence. If the file has been renamed, the
    module has moved, or the line number is past the end of the file, then
    the citation is not evidence any more, and a reader who follows it finds
    nothing — which is the same as a claim with no citation at all.

    The check is on **both** halves. A path that exists but whose line
    number is past the end of the file has drifted in the way that matters:
    the file is there and the pointer into it is not.
    """
    root = _repo_root()
    text = _dossier_text()
    citations = _CITATION.findall(text)
    assert citations, "the dossier names no source locations at all"

    problems: list[str] = []
    for path_text, start_text, end_text in citations:
        path = root / path_text.replace("\\", "/")
        if not path.is_file():
            problems.append(f"{path_text} is not a file in this repository")
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        last = int(end_text) if end_text else int(start_text)
        if last > len(lines):
            problems.append(
                f"{path_text}:{start_text}{'-' + end_text if end_text else ''} is past "
                f"the end of the file, which has {len(lines)} lines"
            )
            continue
        if int(start_text) < 1:
            problems.append(f"{path_text}:{start_text} is not a line number")

    assert not problems, (
        "these citations in the dossier do not resolve, so they are not "
        "evidence:\n  " + "\n  ".join(problems)
    )


def test_every_path_the_dossier_names_is_a_file_this_repository_owns() -> None:
    """Every repository path the dossier names must exist.

    The citation check above only sees the paths that carry a line number.
    This one sees the bare ones — the module a reader is told to open — and
    asks the same question of them.
    """
    root = _repo_root()
    text = _dossier_text()
    paths = sorted(set(_PATH.findall(text)))
    assert paths, "the dossier names no repository paths at all"

    missing = [p for p in paths if not (root / p).exists()]
    assert not missing, (
        "the dossier names these paths, and they are not in this repository:\n  "
        + "\n  ".join(missing)
    )


def test_every_cited_test_function_exists() -> None:
    """Every test the dossier names as a witness must exist.

    The dossier's answer to "is this property tested?" is a test name. A
    name that is not a test is not an answer, and a reader who goes looking
    for it finds nothing.
    """
    root = _repo_root()
    text = _dossier_text()
    cited = _TEST_FUNCTION.findall(text)
    assert cited, "the dossier names no test functions at all"

    missing: list[str] = []
    for file_name, function in cited:
        path = root / "tests" / file_name
        if not path.is_file():
            missing.append(f"tests/{file_name} is not a file in this repository")
            continue
        body = path.read_text(encoding="utf-8", errors="replace")
        if f"def {function}(" not in body:
            missing.append(f"tests/{file_name}::{function} is not defined")

    assert not missing, (
        "the dossier names these tests as witnesses, and they are not there:\n  "
        + "\n  ".join(sorted(set(missing)))
    )


def test_every_cited_adr_exists() -> None:
    """Every ADR the dossier names must exist.

    An ADR is where the upstream observation and the LabCairn decision are
    recorded together. A dossier that cites one that is not there sends the
    reader to a document that does not exist.
    """
    root = _repo_root()
    text = _dossier_text()
    numbers = sorted(set(_ADR.findall(text)))
    assert numbers, "the dossier names no ADRs at all"

    missing = [
        f"ADR-{number}"
        for number in numbers
        if not list((root / "docs" / "adr").glob(f"ADR-{number}-*.md"))
    ]
    assert not missing, (
        "the dossier names these ADRs, and they are not in this repository:\n  "
        + "\n  ".join(missing)
    )


# --------------------------------------------------------------------------- #
# The upstream anchors are the ones the catalogue puts them at
# --------------------------------------------------------------------------- #


def test_every_upstream_anchor_is_a_line_that_exists() -> None:
    """Every anchor must be a line of the catalogue, and a line with words on it.

    An anchor that points past the end of the file, or at a blank line, is
    not a pointer into the record — it is a pointer into nothing.
    """
    lines = _catalogue_lines()
    text = _dossier_text()
    anchors = _ANCHOR.findall(text)
    assert anchors, "the dossier cites no line of the upstream catalogue"

    problems: list[str] = []
    for token in anchors:
        start = int(token.split("-")[0])
        end = int(token.split("-")[1]) if "-" in token else start
        if start < 1 or end > len(lines):
            problems.append(f":{token} is not a line of {CATALOGUE}")
            continue
        if not lines[start - 1].strip():
            problems.append(f":{token} is a blank line of {CATALOGUE}")
        if "-" in token and not lines[end - 1].strip():
            problems.append(f":{token} ends on a blank line of {CATALOGUE}")

    assert not problems, "these upstream anchors do not point at anything:\n  " + "\n  ".join(
        problems
    )


def _anchor_problems(lines: list[str]) -> list[str]:
    """Where each load-bearing anchor's wording actually is, against where it is cited.

    The order matters and it is the whole mechanism: the wording is **found** in the
    catalogue first, and the number the dossier cites is then compared with where it
    was found. The reverse — look at the cited number and ask whether the wording is
    there — did see the drift (it failed on 9 of the 37 anchors when another batch
    inserted 21 lines into the catalogue), but it could not say what had happened:
    the failure read as "the record lost the wording" when the wording was intact on
    another line, and it never named that line. Finding the wording first turns the
    report into a lookup.

    Three kinds of problem, each reported differently:
      * the wording is **not in the catalogue at all** — the record no longer says
        what the dossier cites it for, and no number would fix that;
      * the wording appears on **several lines** — it cannot anchor a citation, and
        silently choosing one would be the witness inventing the answer;
      * the wording is found on a **different line from the one cited** — the dossier's
        number is stale, and the report says where the wording actually is so the fix
        is a lookup rather than a search.
    """
    problems: list[str] = []
    for anchor in _LOAD_BEARING:
        start, end = _span(anchor.token)
        found = _find_fragment(lines, anchor.fragment)
        if not found:
            problems.append(
                f":{anchor.token} is cited for {anchor.fragment!r}, which is not in "
                f"{CATALOGUE} any more — the wording the dossier leans on has left the record"
            )
            continue
        if len(found) > 1:
            listed = ", ".join(str(number) for number in found[:6])
            problems.append(
                f":{anchor.token} cannot be anchored: {anchor.fragment!r} appears on "
                f"{len(found)} lines of {CATALOGUE} ({listed}), so it locates nothing"
            )
            continue
        located = found[0]
        if located != start:
            problems.append(
                f":{anchor.token} cites line {start} of {CATALOGUE}, but its wording is on "
                f"line {located}: {lines[located - 1][:90]!r}"
            )
        if end > len(lines):
            problems.append(
                f":{anchor.token} spans to line {end}, past the end of {CATALOGUE}, "
                f"which has {len(lines)} lines"
            )
    return problems


def test_every_load_bearing_anchor_carries_the_wording_it_is_cited_for() -> None:
    """Each catalogue line the dossier leans on is found **by its wording**, at the number cited.

    The dossier's upstream claims are only as good as the record behind them, so the
    record side is checked: the wording that made a line worth citing is still there, it
    is there in exactly one place, and that place is the line the dossier names.

    **This replaced a stored line number.** The table used to carry `line` and require
    the fragment to be found at it. Replaying that mechanism at the tree where another
    batch inserted 21 lines into the catalogue (`dossier-old-tests-replay.py` in the
    evidence folder): 3 blank-line failures, 9 "fragment not at its stored line"
    failures, and **no broken anchor escaped both** — the old tests did detect the
    drift, and a first probe of mine that modelled only the blank-line test reported
    "7 stayed green" and was wrong (`dossier-silent-drift.py`, superseded by the
    replay; the mistake is recorded in the evidence README).

    What the stored number could not do was describe the drift honestly. Each of the 9
    failures read `CATALOGUE:156 no longer carries '<wording>', which is what :156 is
    cited for`. In all 9 the wording sat intact exactly ten lines lower, and in 7 of
    them the cited line was **not blank**, so the message accused the record of losing
    text that had not been lost, and none of the 9 said where the wording was
    (`dossier-what-anchoring-adds.py`). Locating the wording first makes the report a
    lookup — it names the line the wording actually is on — and adds the check the old
    tests had not: a wording present on more than one line anchors nothing, and the
    stored number could not see that, because the number's own line still carried it.
    """
    lines = _catalogue_lines()
    assert lines, f"{CATALOGUE} has no lines to anchor against"

    problems = _anchor_problems(lines)
    assert not problems, (
        "the dossier's catalogue citations and the catalogue have come apart:\n  "
        + "\n  ".join(problems)
        + "\n\nThe dossier's numbers are corrected to where the wording actually is. "
        "If a wording has left the record, the citation is removed or the claim it "
        "supports is corrected — a number is not evidence."
    )


def test_a_load_bearing_anchor_that_moved_is_reported_with_where_it_went() -> None:
    """The reader is seen to fail for the property, on copies held in memory.

    **The mutation the change is for.** Twenty-one lines are prepended to a copy of the
    catalogue — the shape of the edit that broke this batch's citations — and the
    dossier's numbers are left exactly as the dossier writes them. Every anchor's
    wording is still present and still unique: nothing is blank, nothing is past the
    end, and every cited line exists with words on it. All 37 anchors are reported,
    each naming the line its wording actually moved to.

    **What the old mechanism did on the real tree, measured rather than asserted.**
    Replaying it at `0ec96df` (`dossier-old-tests-replay.py` in the evidence folder):
    its blank-line test failed 3 times, its fragment-at-stored-line test failed 9
    times, and no broken anchor escaped both — so this demonstration is **not** proof
    that the old tests missed the drift; they saw it. It is proof that the new reader
    says *where the wording went*, which the old message never did, and each of the 9
    old failures accused the record of losing wording that was intact nearby
    (`dossier-what-anchoring-adds.py`).

    **Two more mutations, each one a distinct way an anchor can stop anchoring.** Removing
    a wording from the copy must be reported as "not in the catalogue", not as a number
    problem. Duplicating a wording across two lines must be reported as unanchorable
    rather than resolved by picking the first hit — a witness that guesses has stopped
    checking. The duplication case is the one class the old tests could not see at all:
    with the wording on two lines, the stored number still names a line that carries it,
    so `fragment in lines[line - 1]` was satisfied and the anchor located nothing.

    **Controls.** The unmutated copy reports nothing, so every report below is the
    mutation; and each mutation is asserted to change the text before any report is
    credited to it.
    """
    lines = _catalogue_lines()
    assert _anchor_problems(lines) == [], (
        f"the catalogue as it stands already reports: {_anchor_problems(lines)}"
    )

    # Mutation 1: lines inserted above everything, dossier numbers untouched. Non-blank
    # insertions on purpose: blank ones would let the shift be reported as blank lines,
    # which is a different defect and would not test the one this case is about.
    inserted = [f"<!-- inserted by another batch: line {index} -->" for index in range(21)] + lines
    shifted = _anchor_problems(inserted)
    assert shifted, (
        "inserting 21 lines above the whole catalogue broke no anchor. Then the anchors "
        "are not being located by their wording at all."
    )
    moved = [problem for problem in shifted if "but its wording is on line" in problem]
    assert len(moved) == len(_LOAD_BEARING), (
        f"every anchor's wording moved and only {len(moved)} were reported: {shifted[:4]}"
    )
    assert all("not in" not in problem for problem in moved), moved[:2]

    # Mutation 2: a wording deleted from the record.
    anchor = _LOAD_BEARING[0]
    removed_line = _find_fragment(lines, anchor.fragment)[0]
    cut = list(lines)
    cut[removed_line - 1] = "(the paragraph the dossier cited here was removed)"
    assert cut != lines, "mutation 2 changed nothing"
    removed_reports = _anchor_problems(cut)
    assert any(
        f":{anchor.token}" in problem and "not in" in problem for problem in removed_reports
    ), f"deleting the cited wording was not reported as a missing record: {removed_reports}"

    # Mutation 3: the same wording on two lines.
    duplicated = list(lines)
    duplicated.insert(removed_line, lines[removed_line - 1])
    assert duplicated != lines, "mutation 3 changed nothing"
    ambiguous_reports = _anchor_problems(duplicated)
    assert any(
        f":{anchor.token}" in problem and "appears on" in problem for problem in ambiguous_reports
    ), f"a wording duplicated onto two lines was not reported as unanchorable: {ambiguous_reports}"


def test_the_dossier_cites_each_load_bearing_anchor_as_often_as_it_claims() -> None:
    """A citation that moves off its line leaves that line cited less often.

    This is the mechanism that catches a wrong line number. Every anchor the
    dossier uses is counted, and every catalogue line it leans on has a
    recorded count of how many places should be pointing at it. Move one
    citation to a neighbouring line — the neighbouring line exists, the
    dossier still reads fine, and the claim it supports silently changed —
    and the count drops, and this fails.
    """
    text = _dossier_text()
    counts: dict[str, int] = {}
    for token in _ANCHOR.findall(text):
        counts[token] = counts.get(token, 0) + 1

    problems: list[str] = []
    for anchor in _LOAD_BEARING:
        found = counts.get(anchor.token, 0)
        if found < anchor.citations:
            problems.append(
                f":{anchor.token} is cited {found} time(s) and should be cited "
                f"{anchor.citations} time(s)"
            )

    uncited = sorted(set(counts) - {a.token for a in _LOAD_BEARING})
    if uncited:
        problems.append(
            "the dossier cites these catalogue lines for nothing this file "
            f"knows about: {', '.join(':' + t for t in uncited)}"
        )

    assert not problems, (
        "the dossier's upstream anchors and the catalogue have come apart:\n  "
        + "\n  ".join(problems)
    )


# --------------------------------------------------------------------------- #
# The upstream facts agree with the catalogue
# --------------------------------------------------------------------------- #


def test_the_dossier_names_the_five_cloned_repositories_as_the_catalogue_does() -> None:
    """Name, URL and licence of each cloned repository must agree with the catalogue.

    The catalogue is the record of what was studied, where, and under what
    terms. The dossier is the reader-facing account of the same thing. If
    they disagree, one of them is wrong, and a reader has no way to tell
    which — so this compares them instead of trusting either.
    """
    text = _dossier_text()
    rows = _catalogue_rows()
    assert len(rows) == 5, (
        f"the catalogue records {len(rows)} cloned repositories, and this file expects five"
    )

    problems: list[str] = []
    for row in rows:
        name = row["name"]
        if f"`{name}`" not in text:
            problems.append(f"the dossier does not name {name}")
        if row["url"] not in text:
            problems.append(f"the dossier does not carry {name}'s URL")
        licences = _LICENCE.findall(row["licence"])
        assert licences, f"the catalogue row for {name} names no licence"
        for licence in licences:
            if licence not in text:
                problems.append(
                    f"the catalogue records {name} as {licence} and the dossier does not say so"
                )

    assert not problems, (
        "the dossier and the catalogue disagree about the upstream repositories:\n  "
        + "\n  ".join(problems)
    )


def test_the_dossier_names_a_sha_only_for_a_repository_that_was_cloned() -> None:
    """The dossier's commit SHAs must be exactly the five the catalogue records.

    Two things go wrong if this does not hold. A SHA that is not upstream's
    is a fabricated citation, and the catalogue says in as many words that a
    guessed SHA is worse than a blank. A SHA that belongs to a repository
    that was never cloned is the same mistake wearing a different name.
    """
    text = _dossier_text()
    catalogue_shas = {row["sha"] for row in _catalogue_rows()}
    dossier_shas = set(_SHA.findall(text))

    assert dossier_shas, "the dossier names no commit SHA at all"

    unknown = sorted(dossier_shas - catalogue_shas)
    assert not unknown, (
        "the dossier names commit SHAs the catalogue does not record:\n  " + "\n  ".join(unknown)
    )

    missing = sorted(catalogue_shas - dossier_shas)
    assert not missing, (
        "the catalogue records these commits and the dossier names none of "
        "them:\n  " + "\n  ".join(missing)
    )


# --------------------------------------------------------------------------- #
# The boundary the dossier claims
# --------------------------------------------------------------------------- #


def test_the_dossier_names_no_path_into_the_reference_clones() -> None:
    """The dossier may name the glob that excludes the clones; not a path inside them.

    The dossier's central claim is that no upstream source is in this
    repository. A path into the sibling clone directory inside the dossier
    would be a pointer that leads a reader straight out of the repository
    and into the prompt-injection corpus the exclusion exists to keep out.
    """
    text = _dossier_text()
    found = [name for name in _REFERENCE_DIRECTORIES if name in text]
    assert not found, (
        "the dossier names these reference-clone directories as paths, and a "
        "reader following one leaves the repository:\n  " + "\n  ".join(found)
    )


def test_every_relative_link_resolves_and_stays_inside_the_repository() -> None:
    """Every relative markdown link must resolve, and resolve inside the repository.

    A link that points at a file that was renamed is the cheapest way for a
    document to rot. A link that points *out* of the repository is a
    different failure: it sends the reader somewhere this repository does
    not vouch for.
    """
    root = _repo_root()
    dossier = root / DOSSIER
    text = dossier.read_text(encoding="utf-8")

    problems: list[str] = []
    for target in _LINK.findall(text):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        clean = target.split("#", 1)[0]
        if not clean:
            continue
        resolved = (dossier.parent / clean).resolve()
        if not resolved.exists():
            problems.append(f"{target!r} does not exist")
            continue
        if not resolved.is_relative_to(root):
            problems.append(f"{target!r} points outside this repository")

    assert not problems, "these links in the dossier do not resolve:\n  " + "\n  ".join(problems)
