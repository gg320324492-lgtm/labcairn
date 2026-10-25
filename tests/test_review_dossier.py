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
    """One catalogue line the dossier leans on.

    ``token`` is the anchor as the dossier writes it — ``"187"`` or
    ``"38-48"``. ``line`` is the catalogue line the token starts at, and
    ``fragment`` is wording that line must carry for the anchor to mean
    anything. ``citations`` is how many times the dossier cites it.
    """

    token: str
    line: int
    fragment: str
    citations: int


#: Every catalogue line the dossier leans on.
#:
#: The fragment is the wording that makes the line worth citing, and the
#: citation count is the number of places the dossier says so. A citation
#: that moves off the line it belongs to drops that line's count, and this
#: file notices. That is the whole mechanism: the dossier cannot quietly
#: start pointing at a neighbouring line that happens to exist.
_LOAD_BEARING: Final[tuple[Anchor, ...]] = (
    Anchor(
        "30",
        30,
        "verified by opening the LICENSE files at the pinned commit",
        3,
    ),
    Anchor("32", 32, "local shallow-clone snapshot taken on **2026-10-15**", 2),
    Anchor("34", 34, "resolved all five commits against GitHub at review time", 2),
    Anchor("38-48", 38, "| ID | GitHub | Study areas |", 1),
    Anchor("45-48", 45, "| `opencode` | https://github.com/anomalyco/opencode |", 1),
    Anchor("48", 48, "| `ai-scientist-v2` |", 1),
    Anchor("50", 50, "an invented or guessed SHA is worse than a blank", 1),
    Anchor("52", 52, "a capability counts only when a code path constructs it", 3),
    Anchor("54", 54, "## Verified license boundaries (measured 2026-10-15)", 2),
    Anchor("56", 56, "a root statement is not a repository statement", 1),
    Anchor("58-64", 58, "| Clone | LICENSE files | What they actually say |", 1),
    Anchor("68", 68, "GNU Affero General Public License v3", 1),
    Anchor("70", 70, "PyMuPDF>=1.24.12", 1),
    Anchor("74", 74, "is **incomplete**", 1),
    Anchor("75", 75, "is **study-only** for LabCairn", 2),
    Anchor("76", 76, "The AGPL boundary is a *component* boundary", 1),
    Anchor("81", 81, "collection of agent skills", 1),
    Anchor("83", 83, "439 `.py` files and 570 `.md` files", 1),
    Anchor("85", 85, "This makes it a non-executable asset", 1),
    Anchor("87", 87, "OpenCode uses a different core language stack", 2),
    Anchor("114-127", 114, "## Reference → decision → test workflow", 1),
    Anchor(
        "127",
        127,
        "never claim superiority from source-code inspection alone",
        1,
    ),
    Anchor("141", 141, "are **untrusted input**", 1),
    Anchor("142", 142, "139 files named `AGENTS.md`, `CLAUDE.md` or `SKILL.md`", 1),
    Anchor("143", 143, "`paperspine` is the sharpest instance", 1),
    Anchor("144", 144, "Cloning does **not** imply executing", 1),
    Anchor("146", 146, "Don't commit third-party source trees", 1),
    Anchor(
        "147",
        147,
        "Never ingest all upstream code into a model context by default",
        1,
    ),
    Anchor("156", 156, "**`labcairn-upstreams*`**", 1),
    Anchor("163", 163, "Assert that `git ls-files` output contains no reference path", 1),
    Anchor(
        "164",
        164,
        "neither the `git ls-files` listing nor the member names of the built sdist",
        1,
    ),
    Anchor("173", 173, "The sibling directory is unprotected", 1),
    Anchor("185", 185, "No hard runtime/CI dependency on reference clones", 1),
    Anchor("186", 186, "no upstream source was copied or adapted", 1),
    Anchor(
        "187",
        187,
        "P1 review dossier names relevant upstream designs and clearly identifies",
        2,
    ),
    Anchor("191", 191, "A build system now exists", 1),
    Anchor("192", 192, "`reference-exclusion` is a required status check", 2),
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


def test_every_load_bearing_anchor_carries_the_wording_it_is_cited_for() -> None:
    """Each catalogue line the dossier leans on must say what it is cited for.

    The dossier's upstream claims are only as good as the record behind them.
    This checks the catalogue side: that the line the dossier points at still
    carries the wording that made it worth pointing at. If the catalogue is
    edited and the line no longer says that, the dossier's claim has lost its
    ground and the reader would not know.
    """
    lines = _catalogue_lines()
    problems: list[str] = []
    for anchor in _LOAD_BEARING:
        if anchor.line > len(lines):
            problems.append(f":{anchor.token} is past the end of {CATALOGUE}")
            continue
        if anchor.fragment not in lines[anchor.line - 1]:
            problems.append(
                f"{CATALOGUE}:{anchor.line} no longer carries {anchor.fragment!r}, "
                f"which is what :{anchor.token} is cited for"
            )
    assert not problems, (
        "the dossier leans on catalogue lines that no longer say what it needs:\n  "
        + "\n  ".join(problems)
    )


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
