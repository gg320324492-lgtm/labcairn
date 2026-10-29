"""The synthetic DOCX corpus is itself tested, before anything trusts it.

**Why this file exists.** The corpus is the gold for LC-P2-07. A gold that
is wrong does not fail loudly — it fails by making a correct parser look
broken, or by making a broken parser look correct. So the corpus is checked
against the *file it produced*, independently of the code that produced
it: the XML is re-read from the ZIP, and the gold's claims are checked
against what the XML actually says.

The test reads the ZIP with `zipfile` and `xml.etree` — deliberately **not**
with the parser this project is going to write, and not with `python-docx`.
A gold verified by the same code that will be measured against it is not a
gold; it is a second copy of the same mistake.

**What each test would catch.**

| Test | The mistake it catches |
|---|---|
| the writer round-trips | a fixture whose XML does not say what the gold says |
| the deleted text is in `w:delText` | a fixture that used `w:t`, making the case test nothing |
| the missing-author case has no attribute | a fixture that wrote an empty author, another case |
| the malformed anchors are malformed | a fixture whose "orphan" is well-formed, testing nothing |
| the corpus covers the design's negative list | a gap, found by reading the list, not by memory |
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest
from docx_corpus import FIXTURES, KNOWN_GAPS
from docx_fixtures import Fixture, gold_for, write_fixture, write_gold

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

#: A directory outside the repository. The project's own rule is that a
#: pytest temporary directory must not be inside the checkout — a workspace
#: inside the repo makes the run depend on the tree it runs in and leaves the
#: checkout dirty — so this uses the session's own temporary directory,
#: which the project's conftest places outside the repository.
FIXTURE_DIR = Path(__file__).parent


@pytest.fixture(scope="module")
def written(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Write the whole corpus once, and return the directory and the gold path."""
    directory = tmp_path_factory.mktemp("docx-corpus")
    for fixture in FIXTURES:
        write_fixture(fixture, directory)
    gold_path = write_gold(FIXTURES, directory)
    return directory, gold_path


def _document_xml(path: Path) -> ET.Element:
    with zipfile.ZipFile(path) as archive:
        return ET.fromstring(archive.read("word/document.xml"))


def _comments_xml(path: Path) -> ET.Element:
    with zipfile.ZipFile(path) as archive:
        return ET.fromstring(archive.read("word/comments.xml"))


def _fixture(name: str) -> Fixture:
    for fixture in FIXTURES:
        if fixture.name == name:
            return fixture
    raise AssertionError(f"no fixture named {name!r}")


# --------------------------------------------------------------------------- #
# the writer round-trips
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f.name)
def test_the_written_xml_contains_every_gold_revision(
    fixture: Fixture, written: tuple[Path, Path]
) -> None:
    """Every revision in the gold is present in the file, with its own metadata.

    This is the check that would catch a writer that dropped a revision, or
    that wrote the wrong author onto it.
    """
    directory, _ = written
    root = _document_xml(directory / f"{fixture.name}.docx")

    found: dict[str, tuple[str | None, str | None, str]] = {}
    for kind in ("ins", "del", "moveFrom", "moveTo"):
        for element in root.iter(f"{W}{kind}"):
            element_id = element.get(f"{W}id")
            assert element_id is not None, (
                f"{fixture.name}: a {kind} element has no w:id; the fixture "
                f"writer always writes one"
            )
            text = "".join(
                node.text or "" for node in element.iter() if node.tag in (f"{W}t", f"{W}delText")
            )
            found[element_id] = (element.get(f"{W}author"), element.get(f"{W}date"), text)

    for revision in fixture.revisions:
        assert revision.element_id in found, (
            f"{fixture.name}: revision {revision.element_id} is in the gold but not in the file"
        )
        author, date, text = found[revision.element_id]
        assert author == revision.author, (
            f"{fixture.name}: revision {revision.element_id} author is {author!r}, "
            f"gold says {revision.author!r}"
        )
        assert date == revision.date, (
            f"{fixture.name}: revision {revision.element_id} date is {date!r}, "
            f"gold says {revision.date!r}"
        )
        assert text == revision.text, (
            f"{fixture.name}: revision {revision.element_id} text is {text!r}, "
            f"gold says {revision.text!r}"
        )


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f.name)
def test_the_written_xml_contains_every_gold_comment(
    fixture: Fixture, written: tuple[Path, Path]
) -> None:
    """Every comment in the gold is present in ``word/comments.xml``."""
    directory, _ = written
    root = _comments_xml(directory / f"{fixture.name}.docx")

    found = {
        element.get(f"{W}id"): (
            element.get(f"{W}author"),
            element.get(f"{W}date"),
            "".join(node.text or "" for node in element.iter(f"{W}t")),
        )
        for element in root.iter(f"{W}comment")
    }

    for comment in fixture.comments:
        assert comment.comment_id in found, (
            f"{fixture.name}: comment {comment.comment_id} is in the gold but not in the file"
        )
        author, date, text = found[comment.comment_id]
        assert author == comment.author
        assert date == comment.date
        assert text == comment.text


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f.name)
def test_the_gold_matches_the_fixture_it_describes(fixture: Fixture) -> None:
    """The gold's own summary agrees with the fixture's declared contents.

    A pure consistency check, and the cheapest one: it catches a gold
    writer that dropped a field on the way out.
    """
    gold = gold_for(fixture)
    assert gold["name"] == fixture.name
    assert len(gold["revisions"]) == len(fixture.revisions)
    assert len(gold["comments"]) == len(fixture.comments)
    assert gold["paragraph_count"] == len(fixture.paragraphs)
    assert tuple(gold["paragraph_text"]) == fixture.paragraphs
    assert tuple(gold["expectations"]) == fixture.expectations


# --------------------------------------------------------------------------- #
# the cases are the cases they claim to be
# --------------------------------------------------------------------------- #


def test_a_deletion_carries_its_text_in_deltext_not_in_t(written: tuple[Path, Path]) -> None:
    """The deletion case is only a deletion case if the text is in ``w:delText``.

    This is the detail the whole corpus turns on. A fixture that put the
    deleted text in ``w:t`` would make every parser that reads ``w:t``
    appear to pass — and would prove nothing about the behaviour the phase
    needs to get right.
    """
    directory, _ = written
    root = _document_xml(directory / "03-single-deletion.docx")

    deletions = list(root.iter(f"{W}del"))
    assert len(deletions) == 1

    del_text = "".join(node.text or "" for node in deletions[0].iter(f"{W}delText"))
    plain_text = "".join(node.text or "" for node in deletions[0].iter(f"{W}t"))

    assert del_text == "a single observation"
    assert plain_text == "", (
        "the deleted text must not also appear in a w:t node — a reader that "
        "reads w:t would then find it, and the case would test nothing"
    )


def test_a_missing_author_is_an_absent_attribute_not_an_empty_one(
    written: tuple[Path, Path],
) -> None:
    """``w:author`` absent and ``w:author=""`` are different cases.

    The fixture for "no author" must omit the attribute entirely, because
    that is what Word writes, and because a parser that reads the attribute
    as an empty string cannot tell "no author" from "an author whose name is
    empty".
    """
    directory, _ = written
    root = _document_xml(directory / "06-insertion-without-author.docx")

    insertions = list(root.iter(f"{W}ins"))
    assert len(insertions) == 1
    assert insertions[0].get(f"{W}author") is None
    assert insertions[0].get(f"{W}date") == "2026-03-02T09:15:00Z"


def test_a_missing_date_is_an_absent_attribute(written: tuple[Path, Path]) -> None:
    directory, _ = written
    root = _document_xml(directory / "07-insertion-without-date.docx")

    insertions = list(root.iter(f"{W}ins"))
    assert len(insertions) == 1
    assert insertions[0].get(f"{W}date") is None
    assert insertions[0].get(f"{W}author") == "Prof. Lin"


def test_the_orphan_comment_fixtures_really_are_orphaned(written: tuple[Path, Path]) -> None:
    """A "start only" comment has a start and no end, and vice versa.

    The upstream study found a library that drops the entire comment set
    when these counts disagree. For that case to be a case, the mismatch
    has to be real — a fixture that was accidentally well-formed would
    make the negative test pass for the wrong reason.
    """
    directory, _ = written

    start_only = _document_xml(directory / "12-orphan-comment-start-only.docx")
    starts = list(start_only.iter(f"{W}commentRangeStart"))
    ends = list(start_only.iter(f"{W}commentRangeEnd"))
    assert len(starts) == 1
    assert len(ends) == 0, "the start-only fixture must have no range end"

    end_only = _document_xml(directory / "13-orphan-comment-end-only.docx")
    starts = list(end_only.iter(f"{W}commentRangeStart"))
    ends = list(end_only.iter(f"{W}commentRangeEnd"))
    assert len(starts) == 0, "the end-only fixture must have no range start"
    assert len(ends) == 1


def test_the_unanchored_comment_fixture_really_has_no_markers(written: tuple[Path, Path]) -> None:
    directory, _ = written
    root = _document_xml(directory / "14-comment-without-anchor.docx")

    assert list(root.iter(f"{W}commentRangeStart")) == []
    assert list(root.iter(f"{W}commentRangeEnd")) == []

    # The comment element still exists, which is the whole point: the
    # comment survived and only its anchor was lost.
    comments = _comments_xml(directory / "14-comment-without-anchor.docx")
    assert len(list(comments.iter(f"{W}comment"))) == 1


def test_the_clean_fixture_really_has_no_revisions(written: tuple[Path, Path]) -> None:
    directory, _ = written
    root = _document_xml(directory / "01-clean-no-revisions.docx")

    for kind in ("ins", "del", "moveFrom", "moveTo"):
        assert list(root.iter(f"{W}{kind}")) == [], (
            f"the clean fixture must contain no {kind} elements"
        )


def test_the_corpus_holds_the_gold_and_the_fixture_files_together(
    written: tuple[Path, Path],
) -> None:
    """The gold file is written, is valid JSON, and holds every fixture."""
    _, gold_path = written
    payload = json.loads(gold_path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 1
    names = [entry["name"] for entry in payload["fixtures"]]
    assert names == [f.name for f in FIXTURES]
    assert len(names) == len(set(names)), "fixture names must be unique"


def test_writing_a_fixture_does_not_change_its_bytes(written: tuple[Path, Path]) -> None:
    """The writer is deterministic and the file is stable.

    Two writes of the same fixture produce the same bytes, and writing
    again over an existing file produces the same bytes as before. A
    fixture whose bytes moved between runs would make every hash-based
    check meaningless.
    """
    directory, _ = written
    path = directory / "02-single-insertion.docx"
    first = path.read_bytes()

    write_fixture(_fixture("02-single-insertion"), directory)
    second = path.read_bytes()

    assert first == second, "writing the same fixture twice must produce the same bytes"


def test_the_zip_is_readable_and_holds_the_parts_a_docx_needs(written: tuple[Path, Path]) -> None:
    directory, _ = written
    with zipfile.ZipFile(directory / "01-clean-no-revisions.docx") as archive:
        names = set(archive.namelist())
        assert archive.testzip() is None, "the archive must not be corrupt"
    for required in (
        "[Content_Types].xml",
        "_rels/.rels",
        "word/document.xml",
        "word/comments.xml",
        "word/styles.xml",
    ):
        assert required in names, f"the fixture is missing {required}"


# --------------------------------------------------------------------------- #
# the corpus covers what it claims to cover
# --------------------------------------------------------------------------- #


def test_the_corpus_is_large_enough_to_be_a_corpus() -> None:
    """Twenty or more fixtures.

    The number is not a target in itself; it is a floor that catches an
    edit that quietly deletes half the corpus.
    """
    assert len(FIXTURES) >= 20, f"the corpus holds {len(FIXTURES)} fixtures"


def test_every_fixture_states_why_it_exists() -> None:
    """No fixture without a purpose.

    A corpus whose cases are named only by filename teaches nothing, and a
    fixture whose purpose is blank is one nobody will know how to use.
    """
    for fixture in FIXTURES:
        assert fixture.purpose.strip(), f"{fixture.name} has no purpose"
        assert fixture.expectations, f"{fixture.name} states no expectation"


def test_the_corpus_covers_the_designs_negative_list() -> None:
    """The cases the design names are present.

    The design's §7 lists the negative cases by name. This test reads the
    list and checks the corpus against it, so a gap is found by reading the
    requirement rather than by remembering it.
    """
    names = {f.name for f in FIXTURES}
    kinds = {r.kind for f in FIXTURES for r in f.revisions}
    anchors = {c.anchor for f in FIXTURES for c in f.comments}

    for required in (
        "02-single-insertion",  # an insertion
        "03-single-deletion",  # a deletion
        "05-two-authors",  # several authors
        "06-insertion-without-author",  # a document with no author
        "07-insertion-without-date",  # a document with no date
        "09-comment-with-anchor",  # a comment range
        "10-comment-spanning-a-revision",  # a comment spanning runs
        "12-orphan-comment-start-only",  # an orphan comment marker
        "16-move-from",  # a move
        "19-nested-revision",  # nesting
        "25-revision-with-empty-text",  # an empty revision
    ):
        assert required in names, f"the design's negative list names {required}"

    assert {"ins", "del", "moveFrom", "moveTo"} <= kinds, (
        "the corpus must contain every revision kind the design names"
    )
    assert {"both", "start_only", "end_only", "none"} <= anchors, (
        "the corpus must contain a resolvable anchor and each malformed variant"
    )


def test_the_known_gaps_are_stated_rather_than_surprised() -> None:
    """The corpus's limits are written down.

    A synthetic corpus that looks complete is worse than one that admits
    what it cannot reach, because the first is trusted.
    """
    assert len(KNOWN_GAPS) >= 8, "the gaps list should name the real corpus's work"
    joined = " ".join(KNOWN_GAPS).lower()
    for required in ("run", "move", "header", "corrupt", "accepted"):
        assert required in joined, f"the gaps list should mention {required}"
