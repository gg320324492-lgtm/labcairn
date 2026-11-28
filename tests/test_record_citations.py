"""The revisions this repository's records cite are revisions this repository has.

``tests/test_status_consistency.py`` watches the commits the *status board* cites.
It is scoped to the board on purpose: ``UPSTREAM_REFERENCES.md`` and the ADRs
cite other projects' histories, and an allowlist that grows with each upstream
study is not a check. The acceptance records, the handoff and the plans were
left unwatched, and the delivery-line rewrite re-pointed dozens of citations in
them with a script of its own. A script that turns the wrong digit produces a
citation that looks right and names nothing, and no test in the tree went red.

What this file reads
--------------------
Every ``*.md`` under ``docs/acceptance``, ``docs/handoff`` and ``docs/plans``
-- the documents that record *this* project's own work. It also reads
``docs/UPSTREAM_REFERENCES.md``, but only as a **catalogue**: the projects whose
revisions this tree records as foreign. It writes nothing.

Which token shapes it considers
-------------------------------
A **code span** whose whole content is lower-case hex, 7 to 64 characters, or a
URL under ``github.com/gg320324492-lgtm/labcairn/{commit,tree,blob}/``. The
length decides what the token can be:

* **64 characters cannot be an object id.** A git object id is a SHA-1 digest,
  at most 40 hex characters. A 64-character token is a SHA-256 content digest -
  a fixture's hash or a record's digest - and this file does not confuse it
  with a commit. Widths of 41 or more are skipped for the same reason.
* **40 characters is judged every time.** It is either a commit, a tree, a
  blob, or nothing this repository has.
* **7 to 39 characters is judged only when this checkout resolves it.** The
  same shape is a CI run id, a content digest's prefix, an upstream
  abbreviation, or an English word inside a code span (``succeeded`` contains
  ``cceeded``). A checkout that cannot resolve such a token does not judge it;
  that is a stated blind spot, and it is why a rewrite that moves a citation
  writes the full id.

How it tells a claim about this repository from a foreign one
-------------------------------------------------------------
**Resolution comes first.** A token this repository's object database resolves
to a commit *is* a commit of this repository, whatever the prose says; a
foreign project's revision and a fixture's digest cannot resolve here. The
record's introducer then decides *what kind of object* the token is claimed to
be: ``the tree that branch commit carries``, ``The blob`` and ``^{tree}`` name
tree and blob objects, while ``commit``, ``merge``, ``run``, ``head`` and the
``**Tree:**`` field name commits. (``**Tree:**`` is this tree's word for the
workspace state a record describes, so its value is a commit despite the noun.)

**Only an unresolvable full id needs provenance.** If its unit - the markdown
block and the headings above it - names a foreign source, the token belongs to
that source and is not this repository's claim. A foreign source is a URL to a
repository other than this one, a path into the upstream clones
(``labcairn-upstreams``, ``_references``, ``.upstreams``), or a project the
catalogue pins a revision for. The catalogue is read, never copied: this file
keeps no list of foreign hashes, and it does not grow when a new revision is
quoted - only when a new project is registered, which this project already
requires of every upstream it studies. If the catalogue cannot be parsed, the
foreign citations turn red rather than passing silently.

What it does not watch
----------------------
* ``docs/adr`` and ``docs/UPSTREAM_REFERENCES.md`` themselves, whose subject is
  foreign history on purpose; ``docs/REVIEW-DOSSIER.md``, which has its own
  witness in ``tests/test_review_dossier.py``.
* Fenced code blocks: they are transcripts of command output, not claims, and
  a hash in one may be an argument passed to a tool rather than a citation.
* Blockquoted lines: they are quotations -- the owner's words, a command's
  output, a finding a review reported -- and a hash in one is quoted, not
  this repository's claim. The prose on either side of a quotation is prose
  again, and is judged.
* Prose: a sentence is not a witness. This file checks ids, paths and kinds.
* A short token this checkout cannot resolve, as above.
* A re-point to a *reachable* commit: no existence witness can tell a right
  commit from a wrong one when both are ancestors of a branch. What this file
  catches is the failure that leaves a citation naming something the tree does
  not have - a mistyped digit, an old id outside every branch, a re-point to a
  tree or a blob.

The exception list
------------------
A hash that names something this repository *deliberately no longer has* may be
declared in :data:`ABSENCES`, and every entry says what is gone and why. An
entry with no reason fails, an entry that names something still reachable from
a branch fails, and a missing full id that is neither a foreign revision nor a
declared absence fails. The list is deliberately short and is not a tolerance:
each entry is a record of a loss this project chose, not a place to silence a
wrong citation.

The guard's own arms
--------------------
Everything above is a mechanism, and each mechanism has an arm below: a token
that names nothing is a finding; a foreign revision is not; a 64-character
digest is not; a tree named as a tree is green and the same tree named as a
commit is a finding; a declared absence is green and one without a reason is
not; a repository whose branch was deleted is seen by the reachability scan.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Final, NamedTuple

import pytest
from deadline_support import bounded_git

#: The checkout this file lives in.
REPO: Final[Path] = Path(__file__).resolve().parents[1]

#: The documents that record this project's own work.
WATCHED: Final[tuple[Path, ...]] = (
    Path("docs") / "acceptance",
    Path("docs") / "handoff",
    Path("docs") / "plans",
)

#: The tree's own catalogue of the foreign projects it studies, and the
#: revisions it pins for them. Read as data; never edited here.
CATALOGUE: Final[Path] = Path("docs") / "UPSTREAM_REFERENCES.md"

#: This repository as a URL names it. A URL with this prefix is a claim about
#: this repository even when the prose around it says nothing.
_OURS_URL: Final[re.Pattern[str]] = re.compile(
    r"github\.com/gg320324492-lgtm/labcairn/(commit|tree|blob)/([0-9a-f]{7,40})"
)

#: A URL to a commit, tree or blob of another repository.
_FOREIGN_URL: Final[re.Pattern[str]] = re.compile(
    r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/(?:commit|tree|blob)/"
)

#: The directories the upstream clones live in. A citation that names one is
#: describing a foreign source.
_UPSTREAM_PATH: Final[re.Pattern[str]] = re.compile(
    r"labcairn-upstreams|_references/|\.upstreams/", re.IGNORECASE
)

#: A code span holding a hash, and a table row, respectively.
_SPAN: Final[re.Pattern[str]] = re.compile(r"`([0-9a-f]{7,64})`")

#: A full id written without a code span: a table cell, a command line, a
#: ``measured_at`` value. Only full widths: a bare abbreviation is a word.
_BARE: Final[re.Pattern[str]] = re.compile(r"(?<![0-9a-fA-F`])[0-9a-f]{40}(?![0-9a-fA-F`])")
_HEADING: Final[re.Pattern[str]] = re.compile(r"^(#{1,6})\s+(.*)$")
_TABLE_ROW: Final[re.Pattern[str]] = re.compile(r"^\s*\|")

#: A SHA-1 object id is 40 hex characters; anything longer is a different hash.
_OBJECT_ID: Final[int] = 40

#: The word floor for an absence's reason. A floor, not a truth check: the arm
#: below shows an entry with no reason fails, and a reader judges the rest.
_MIN_REASON_WORDS: Final[int] = 8

#: A foreign project's name is matched after removing the characters that
#: separate its words, so ``paper-qa`` matches ``PaperQA2``. A name shorter
#: than this after normalisation is not a name, it is a word.
_SHORTEST_UPSTREAM_NAME: Final[int] = 5

#: How far back the introducer is read. A noun further away than this is not
#: introducing the token.
_INTRODUCER_WINDOW: Final[int] = 240

#: The forms that name a git tree or blob **object**, as opposed to the
#: workspace state. The records use both senses of "tree": ``the tree at
#: <commit>`` and ``the tree has moved`` mean a commit, while ``the tree that
#: <commit> carries``, ``^{tree}``, ``tree equality`` and ``the blob`` mean an
#: object. Recognising the nouns alone would turn a commit into a tree; this
#: pattern recognises only the object forms.
_OBJECT_PHRASE: Final[re.Pattern[str]] = re.compile(
    r"\^\{?(?:tree|blob)\}?"
    r"|\b(?:tree|blob)\s+(?:object|equality)\b"
    r"|\bthe\s+(?:tree|blob)\s+(?:that|the|this|its|whose)\b[^`.!?\n]*?\b(?:carries|carried|holds)\b"
    r"|\bblob\b(?![:.])",
    re.IGNORECASE,
)

#: A revision, the way this tree's records introduce one when they do not say
#: which kind of object it is: a merge, a run's head, a branch, a parent.
_REVISION: Final[re.Pattern[str]] = re.compile(
    r"\b(?:commit|merge|squash|tip|branch|run|parent|head|base)\b", re.IGNORECASE
)


class Absence(NamedTuple):
    """A cited hash the repository deliberately no longer has, and why.

    ``sha`` is a full object id so the entry cannot match a shape rather than a
    thing. ``why`` says what is gone and by what act it went.
    """

    sha: str
    why: str


#: The hashes this repository's records cite that it deliberately no longer
#: has. Every entry says why. Nothing else is listed here.
ABSENCES: Final[tuple[Absence, ...]] = (
    Absence(
        sha="25bad72383706e941e9ec22846f802033f6dea02",
        why=(
            "G4's branch commit, the state its acceptance record measured. The "
            "work landed by squash as d65254d, whose tree is this commit's, so "
            "this id is in no branch's history and the branch was deleted."
        ),
    ),
    Absence(
        sha="d74ac7aa98069d647c4bbdfd3299280d12d24954",
        why=(
            "PR #195's branch commit, the head the shard costs were measured "
            "on. The pull request landed by squash as b2e3661 and the branch "
            "was deleted; the record itself says this id is in no history main "
            "has."
        ),
    ),
    Absence(
        sha="e16d82d3ce49d6859ff4c34b18e1880dc7ae417d",
        why=(
            "The merge commit on PR #195's branch that the re-anchor run "
            "measured. The branch was squash-merged and deleted, so this "
            "commit is in no branch's history."
        ),
    ),
    Absence(
        sha="0582cc533a8a52fe8df0e5399c703bf053427925",
        why=(
            "The head of PR #194's run, which failed the same way one hour "
            "later. It is a merge of main into that branch; the branch is gone "
            "and the commit is in no branch's history."
        ),
    ),
    Absence(
        sha="ec260b551655eac6dfc023eb93befa853084d608",
        why=(
            "The tree that d74ac7a carries, named beside it in the record. It "
            "is unreachable with its commit: the branch was squash-merged and "
            "deleted, and no remaining commit carries this tree."
        ),
    ),
    Absence(
        sha="ecdfb94ce018e5c1fa2c7fc9b4348bd188b25cad",
        why=(
            "The blob that carried a person's name in the delivery line. The "
            "line was rewritten to replace that document, so no branch or tag "
            "of the published repository reaches it; it remains in a local "
            "object store until the host-side purge the record requests."
        ),
    ),
    Absence(
        sha="a399bfb1331786bba5db4ecb9f49f064ee4a0a8e",
        why=(
            "The leaked commit before the delivery line was rewritten. The "
            "record names it only to say what became 9c7eb19: the rewrite moved "
            "it out of the branch's history, and the record asks the host to "
            "purge it. The new id is the one the line carries."
        ),
    ),
    Absence(
        sha="40609d659fc434556fbd8f88ddd8bc4c3e04f3d4",
        why=(
            "The delivery line's tip before the rewrite. The record names it "
            "only to say what became fbffd9a1: the tip was re-hashed when the "
            "leaked commit was replaced, so no branch carries this id."
        ),
    ),
)

#: The absence ids, for the judge to consult without re-parsing the reasons.
_ABSENT_IDS: Final[frozenset[str]] = frozenset(absence.sha for absence in ABSENCES)

#: What the scan found on 2026-11-28 at ``9fff78d``: 196 documents and the
#: token and commit counts below, rounded down. The floor is what a scan that
#: stopped reading the tree would fall through; it is not a claim that these
#: numbers cannot change.
_DOCUMENT_FLOOR: Final[int] = 190
_TOKEN_FLOOR: Final[int] = 600
_COMMIT_FLOOR: Final[int] = 400


class Finding(NamedTuple):
    """A citation that names something this repository does not have."""

    path: str
    line: int
    token: str
    why: str


class World(NamedTuple):
    """What the judge needs to know about a repository, read once."""

    objects: Mapping[str, tuple[str | None, str | None]]
    reachable: frozenset[str]
    upstream: frozenset[str]


class _Context(NamedTuple):
    number: int
    line: str
    block: str
    headings: str
    before: str


def _git(root: Path, *args: str, stdin: str | None = None) -> str:
    """Run one git command in ``root`` and return its standard output."""
    completed = bounded_git(
        ["git", *args],
        cwd=root,
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return completed.stdout


def _normalise(value: str) -> str:
    """Lower-case ``value`` with the separators of a project name removed."""
    return re.sub(r"[-_.\s`*]", "", value.lower())


def _object_index(root: Path, tokens: Iterable[str]) -> dict[str, tuple[str | None, str | None]]:
    """Resolve every token in one pass: token -> (full id or None, object kind).

    An abbreviation that resolves ambiguously, and a name that does not exist,
    both come back with no id: only an unambiguous object is judged.
    """
    ordered = sorted(set(tokens))
    if not ordered:
        return {}
    output = _git(
        root,
        "cat-file",
        "--batch-check=%(objectname) %(objecttype)",
        stdin="\n".join(ordered) + "\n",
    )
    index: dict[str, tuple[str | None, str | None]] = {}
    for token, line in zip(ordered, output.splitlines(), strict=True):
        fields = line.split()
        if len(fields) == 2 and fields[1] in {"commit", "tree", "blob"}:
            index[token] = (fields[0], fields[1])
        else:
            index[token] = (None, None)
    return index


def _reachable_objects(root: Path) -> frozenset[str]:
    """Every object reachable from the refs a clone of this repository carries.

    ``HEAD``, the remote branches and the tags. **Local branches other than the
    one checked out are not included**: a window's unpushed branch is not a
    place a clone can look, and a branch cut before a rewrite can still hold an
    object the rewritten line deliberately dropped. Pull request refs, backup
    refs, the stash and the reflog are excluded for the same reason.
    """
    refs = ["HEAD"]
    listing = _git(root, "for-each-ref", "--format=%(refname)", "refs/remotes", "refs/tags")
    refs.extend(line for line in listing.splitlines() if line)
    objects = _git(root, "rev-list", "--objects", *refs)
    return frozenset(line.split(" ", 1)[0] for line in objects.splitlines() if line)


def _upstream_names(catalogue: str) -> frozenset[str]:
    """The foreign projects the catalogue pins a revision for.

    A row of a table counts when its first cell names a project and the row
    carries a hex token: that is the catalogue's shape for a studied revision.
    Read from the file rather than copied here, so a newly registered project
    is recognised without editing this witness.
    """
    names: set[str] = set()
    for line in catalogue.splitlines():
        if not _TABLE_ROW.match(line) or _SPAN.search(line) is None:
            continue
        cells = line.strip().strip("|").split("|")
        if len(cells) < 2:
            continue
        first = cells[0].strip().strip("`*").strip()
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{2,}", first):
            normalised = _normalise(first)
            if len(normalised) >= _SHORTEST_UPSTREAM_NAME:
                names.add(normalised)
    return frozenset(names)


def _contexts(text: str) -> Iterator[_Context]:
    """Every non-empty line outside a fenced block, with its block and headings.

    A *block* is the run of non-empty lines a markdown reader would see as one
    paragraph, table or list. Fenced blocks are dropped: they are transcripts
    of command output, not claims, and a ``#`` line in one is a shell comment
    rather than a heading. ``before`` is the block's text up to the line, so a
    token's introducer can be read without guessing boundaries.
    """
    blocks: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    in_fence = False
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            if current:
                blocks.append(current)
                current = []
            continue
        if in_fence:
            continue
        if line.lstrip().startswith(">"):
            # A quoted line is quoted material -- the owner's words, a
            # command's output, a finding a review reported -- and a hash in
            # one is quoted rather than claimed. The quoted lines are their
            # own block, so the prose on either side of them is prose again.
            if current:
                blocks.append(current)
                current = []
            continue
        if line.strip():
            current.append((number, line))
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)

    headings: list[tuple[int, str]] = []
    for block in blocks:
        for _, line in block:
            heading = _HEADING.match(line)
            if heading:
                level = len(heading.group(1))
                headings = [(depth, title) for depth, title in headings if depth < level]
                headings.append((level, heading.group(2)))
        block_text = "\n".join(line for _, line in block)
        heading_text = "\n".join(title for _, title in headings)
        before = ""
        for number, line in block:
            yield _Context(number, line, block_text, heading_text, before)
            before += line + "\n"


def _introduced_as(before: str) -> str:
    """``commit``, ``tree`` or ``blob``: what the text says the token names.

    Only an **object phrase** names a tree or blob: ``the tree that <commit>
    carries``, ``^{tree}``, ``tree equality``, ``the blob``. Plain ``the tree``
    is this tree's word for the workspace state, and its value is a commit, so
    the default is a commit and the object phrase has to earn the exception. A
    noun inside the object phrase (``branch commit`` in ``the tree that branch
    commit carries``) does not override it; a noun that starts after the phrase
    does, because a new claim has begun.
    """
    line_prefix = before.rsplit("\n", 1)[-1]
    if line_prefix.lstrip().startswith("|"):
        cells = line_prefix.split("|")
        introducer = cells[-2] if len(cells) >= 2 else ""
    else:
        introducer = before
    boundaries = [match.end() for match in re.finditer(r"[.!?](?:\s|$)", introducer)]
    start = max(boundaries[-1] if boundaries else 0, len(introducer) - _INTRODUCER_WINDOW)
    window = introducer[start:]
    object_match: re.Match[str] | None = None
    for match in _OBJECT_PHRASE.finditer(window):
        object_match = match
    revision_match: re.Match[str] | None = None
    for match in _REVISION.finditer(window):
        revision_match = match
    if object_match is not None and (
        revision_match is None or revision_match.start() < object_match.end()
    ):
        return "blob" if "blob" in object_match.group(0).lower() else "tree"
    return "commit"


def _names_a_foreign_source(block: str, headings: str, upstream: frozenset[str]) -> bool:
    """Whether the citation's unit names a source other than this repository."""
    unit = block + "\n" + headings
    normalised = _normalise(unit)
    if any(name in normalised for name in upstream):
        return True
    if _UPSTREAM_PATH.search(unit):
        return True
    return any(
        (match.group(1).lower(), match.group(2).lower()) != ("gg320324492-lgtm", "labcairn")
        for match in _FOREIGN_URL.finditer(unit)
    )


def _documents(root: Path = REPO) -> list[Path]:
    """Every markdown document that records this project's own work."""
    documents: list[Path] = []
    for directory in WATCHED:
        documents.extend(sorted((root / directory).glob("*.md")))
    return documents


def _line_citations(line: str) -> Iterator[tuple[str, int, str | None]]:
    """The tokens one line cites: ``(token, offset, kind from a URL or None)``.

    A token inside a code span or a URL is not also read as a bare token, so
    one citation is judged once.
    """
    covered: list[tuple[int, int]] = []
    for match in _SPAN.finditer(line):
        covered.append(match.span())
        yield match.group(1), match.start(1), None
    for match in _OURS_URL.finditer(line):
        covered.append(match.span())
        yield match.group(2), match.start(2), match.group(1)
    for match in _BARE.finditer(line):
        if any(start <= match.start() and match.end() <= end for start, end in covered):
            continue
        yield match.group(0), match.start(), None


def _tokens(text: str) -> set[str]:
    """Every token shape this witness considers in one document."""
    tokens: set[str] = set()
    for context in _contexts(text):
        tokens.update(token for token, _, _ in _line_citations(context.line))
    return tokens


def _findings(
    path: str,
    text: str,
    world: World,
    absences: frozenset[str] = _ABSENT_IDS,
) -> list[Finding]:
    """Every citation in ``text`` that names something this tree does not have."""
    findings: list[Finding] = []
    for context in _contexts(text):
        for token, offset, url_kind in _line_citations(context.line):
            finding = _judge(path, context, token, offset, url_kind, world, absences)
            if finding is not None:
                findings.append(finding)
    return findings


def _judge(
    path: str,
    context: _Context,
    token: str,
    offset: int,
    url_kind: str | None,
    world: World,
    absences: frozenset[str],
) -> Finding | None:
    """One citation, judged. Returns the finding, or ``None`` for a green one."""
    length = len(token)
    if length > _OBJECT_ID:
        return None
    resolved, actual = world.objects.get(token, (None, None))
    if resolved is None and length < _OBJECT_ID:
        return None
    if resolved is not None and resolved in absences:
        return None
    if resolved is None:
        if token in absences:
            return None
        if _names_a_foreign_source(context.block, context.headings, world.upstream):
            return None
        return Finding(path, context.number, token, "names no object in this repository")
    claimed = url_kind or _introduced_as(context.before + context.line[:offset])
    if actual != claimed:
        return Finding(
            path,
            context.number,
            token,
            f"names a {actual}, where the record claims a {claimed}",
        )
    if resolved not in world.reachable:
        return Finding(
            path,
            context.number,
            token,
            f"the {actual} is reachable from no branch, remote or tag",
        )
    return None


def _world(root: Path, documents: Iterable[Path]) -> World:
    """Read the repository and its catalogue once, for every document."""
    tokens: set[str] = set()
    for document in documents:
        tokens.update(_tokens(document.read_text(encoding="utf-8")))
    return World(
        objects=_object_index(root, tokens),
        reachable=_reachable_objects(root),
        upstream=_upstream_names((root / CATALOGUE).read_text(encoding="utf-8")),
    )


def _absence_fault(absence: Absence) -> str | None:
    """Why ``absence`` is not a valid declaration, or ``None`` when it is."""
    if not re.fullmatch(r"[0-9a-f]{40}", absence.sha):
        return f"{absence.sha!r} is not a full object id"
    if len(absence.why.split()) < _MIN_REASON_WORDS:
        return f"{absence.sha} does not say why it is gone"
    return None


# --------------------------------------------------------------------------
# the witness
# --------------------------------------------------------------------------


def test_every_revision_the_records_cite_is_one_this_repository_has() -> None:
    """The property: no full id names a thing this tree does not have."""
    if _git(REPO, "rev-parse", "--is-shallow-repository").strip() == "true":
        pytest.skip("shallow checkout; reachability cannot be measured")
    documents = _documents()
    world = _world(REPO, documents)
    findings = [
        finding
        for document in documents
        for finding in _findings(
            document.relative_to(REPO).as_posix(),
            document.read_text(encoding="utf-8"),
            world,
        )
    ]
    assert not findings, (
        f"{len(findings)} citation(s) name something this repository does not "
        "have and are not declared as gone:\n"
        + "\n".join(f"  {f.path}:{f.line}: {f.token!r} {f.why}" for f in findings)
    )


def test_the_scan_reads_the_records_it_claims_to() -> None:
    """No arm above may pass by reading nothing."""
    documents = _documents()
    texts = [document.read_text(encoding="utf-8") for document in documents]
    tokens: set[str] = set()
    for text in texts:
        tokens.update(_tokens(text))
    world = _world(REPO, documents)
    commits = {
        full
        for full, kind in world.objects.values()
        if kind == "commit" and full is not None and full in world.reachable
    }
    assert len(documents) >= _DOCUMENT_FLOOR, (
        f"{len(documents)} documents read, below the measured floor of {_DOCUMENT_FLOOR}"
    )
    assert len(tokens) >= _TOKEN_FLOOR, (
        f"{len(tokens)} tokens read, below the measured floor of {_TOKEN_FLOOR}"
    )
    assert len(commits) >= _COMMIT_FLOOR, (
        f"{len(commits)} distinct commits cited, below the measured floor of {_COMMIT_FLOOR}"
    )
    assert sum(1 for document in documents if _tokens(document.read_text(encoding="utf-8"))) >= (
        _DOCUMENT_FLOOR // 2
    ), "fewer than half the documents carry a citation"


def test_the_upstream_catalogue_is_readable() -> None:
    """The catalogue is this witness's only source of foreign names."""
    names = _upstream_names((REPO / CATALOGUE).read_text(encoding="utf-8"))
    assert len(names) >= _SHORTEST_UPSTREAM_NAME, (
        f"the catalogue yielded {len(names)} foreign project names; the parser "
        "or the catalogue changed shape, and foreign citations would turn red"
    )


# --------------------------------------------------------------------------
# the exception list
# --------------------------------------------------------------------------


def test_every_declared_absence_says_what_is_gone_and_why() -> None:
    faults = [fault for absence in ABSENCES if (fault := _absence_fault(absence)) is not None]
    assert not faults, "\n".join(faults)


def test_no_absence_is_declared_twice() -> None:
    ids = [absence.sha for absence in ABSENCES]
    assert len(ids) == len(set(ids)), "an absence is declared twice"


def test_a_declared_absence_names_something_the_repository_no_longer_has() -> None:
    """An exception for an object a branch still reaches is dead weight."""
    index = _object_index(REPO, [absence.sha for absence in ABSENCES])
    reachable = _reachable_objects(REPO)
    for absence in ABSENCES:
        resolved, _kind = index[absence.sha]
        assert resolved is None or resolved not in reachable, (
            f"{absence.sha} is declared gone but is reachable from a branch, "
            "remote or tag; remove the exception"
        )


# --------------------------------------------------------------------------
# the arms: each mechanism, shown to decide
# --------------------------------------------------------------------------


def test_a_full_id_that_names_nothing_is_a_finding() -> None:
    token = "0" * 40
    world = World(objects={}, reachable=frozenset(), upstream=frozenset())
    findings = _findings("synthetic.md", f"At `{token}`, the gate ran.\n", world)
    assert [finding.token for finding in findings] == [token]
    assert "names no object" in findings[0].why


def test_a_quoted_hash_is_quoted_material_and_not_a_claim() -> None:
    """A quoted line is a quotation; the same token in prose is a finding.

    Both directions, because the rule that skips a quotation and the rule
    that judges prose are one mechanism: a witness that skipped every hash
    would pass over a wrong citation, and one that judged every hash would
    report the evidence a review quoted.
    """
    token = "0" * 40
    world = World(objects={}, reachable=frozenset(), upstream=frozenset())
    quoted = f"> the review reported: `{token}` names nothing here.\n"
    assert not _findings("synthetic.md", quoted, world)
    findings = _findings("synthetic.md", f"At `{token}`, the gate ran.\n", world)
    assert [finding.token for finding in findings] == [token]


def test_a_foreign_revision_is_not_a_claim_about_this_repository() -> None:
    """Both directions: the marker decides, and its absence is a finding."""
    token = "f" * 40
    names = _upstream_names((REPO / CATALOGUE).read_text(encoding="utf-8"))
    assert names, "the catalogue must name at least one foreign project"
    name = sorted(names)[0]
    world = World(objects={}, reachable=frozenset(), upstream=names)
    assert not _findings("synthetic.md", f"A revision of {name} at `{token}`.\n", world)
    findings = _findings("synthetic.md", f"A revision at `{token}`.\n", world)
    assert [finding.token for finding in findings] == [token]


def test_a_content_digest_is_not_a_commit_citation() -> None:
    """A 64-character digest is a SHA-256, and no object id has that width."""
    token = "a" * 64
    world = World(objects={}, reachable=frozenset(), upstream=frozenset())
    assert not _findings("synthetic.md", f"sha256 `{token}`\n", world)
    findings = _findings("synthetic.md", f"At `{token[:40]}`.\n", world)
    assert [finding.token for finding in findings] == [token[:40]]


def test_a_tree_named_as_a_tree_is_green_and_as_a_commit_is_a_finding() -> None:
    token = "b" * 40
    world = World(
        objects={token: (token, "tree")}, reachable=frozenset({token}), upstream=frozenset()
    )
    assert not _findings("synthetic.md", f"| the tree that commit carries | `{token}` |\n", world)
    findings = _findings("synthetic.md", f"At `{token}`, the run started.\n", world)
    assert [finding.token for finding in findings] == [token]
    assert "names a tree" in findings[0].why


def test_the_tree_field_names_a_commit_even_though_its_noun_is_tree() -> None:
    token = "c" * 40
    world = World(
        objects={token: (token, "tree")}, reachable=frozenset({token}), upstream=frozenset()
    )
    findings = _findings("synthetic.md", f"**Tree:** `{token}`\n", world)
    assert [finding.token for finding in findings] == [token]


def test_a_commit_no_branch_reaches_is_a_finding() -> None:
    token = "d" * 40
    world = World(objects={token: (token, "commit")}, reachable=frozenset(), upstream=frozenset())
    findings = _findings("synthetic.md", f"At `{token}`, the gate ran.\n", world)
    assert [finding.token for finding in findings] == [token]
    assert "reachable from no branch" in findings[0].why
    reached = world._replace(reachable=frozenset({token}))
    assert not _findings("synthetic.md", f"At `{token}`, the gate ran.\n", reached)


def test_a_url_to_this_repository_is_a_claim_even_without_prose() -> None:
    token = "e" * 40
    world = World(objects={}, reachable=frozenset(), upstream=frozenset())
    link = f"https://github.com/gg320324492-lgtm/labcairn/commit/{token}"
    findings = _findings("synthetic.md", f"[the commit]({link})\n", world)
    assert [finding.token for finding in findings] == [token]


def test_a_declared_absence_is_green_and_an_undeclared_one_is_not() -> None:
    absent = ABSENCES[0].sha
    world = World(objects={}, reachable=frozenset(), upstream=frozenset())
    assert not _findings("synthetic.md", f"At `{absent}`.\n", world)
    undeclared = "1" * 40
    findings = _findings("synthetic.md", f"At `{undeclared}`.\n", world)
    assert [finding.token for finding in findings] == [undeclared]


def test_an_absence_with_no_reason_is_a_fault() -> None:
    reason = "It was rewritten out of the delivery line by the remedy."
    assert _absence_fault(Absence(sha="2" * 40, why="")) is not None
    assert _absence_fault(Absence(sha="2" * 40, why="gone")) is not None
    assert _absence_fault(Absence(sha="2" * 40, why=reason)) is None
    assert _absence_fault(Absence(sha="abc", why=reason)) is not None


# --------------------------------------------------------------------------
# the mechanisms, against a repository built for the purpose
# --------------------------------------------------------------------------


def _temp_repository(root: Path) -> tuple[str, str]:
    """A repository with a commit no branch reaches, and the object id."""
    _git(root, "init", "-q")
    config = ("-c", "user.name=Witness", "-c", "user.email=witness@example.invalid")
    for name, body in (("one.txt", "one\n"), ("two.txt", "two\n")):
        (root / name).write_text(body, encoding="utf-8")
        _git(root, *config, "add", name)
        _git(root, *config, "commit", "-q", "-m", name)
    orphan = _git(root, "rev-parse", "HEAD").strip()
    _git(root, "reset", "--hard", "HEAD~1")
    head = _git(root, "rev-parse", "HEAD").strip()
    return orphan, head


def test_the_reachability_scan_does_not_see_a_commit_no_branch_reaches(
    tmp_path: Path,
) -> None:
    """The mechanism, measured: a deleted branch leaves an unreachable object."""
    orphan, head = _temp_repository(tmp_path)
    reachable = _reachable_objects(tmp_path)
    assert head in reachable
    assert orphan not in reachable
    index = _object_index(tmp_path, [orphan])
    assert index[orphan] == (orphan, "commit"), (
        "the object must still be in the store for this arm to mean anything"
    )
    world = World(objects=index, reachable=reachable, upstream=frozenset())
    findings = _findings("synthetic.md", f"At `{orphan}`.\n", world)
    assert [finding.token for finding in findings] == [orphan]
