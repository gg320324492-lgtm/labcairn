"""The DOCX reader, and the properties it is required to hold.

**What is under test.** LC-P2-07's acceptance, measured against the
synthetic corpus in ``tests/docx_corpus.py``:

* every revision is reported, with its kind, text, author and date;
* every deletion's **text** is recovered -- the deleted text lives in
  ``w:delText``, and a reader that reads ``w:t`` sees an empty run;
* every comment is reported, including the five whose anchor cannot be
  resolved, each with the reason it cannot;
* a missing author or date is ``UNKNOWN`` and never a guess;
* the original bytes are unchanged;
* the two views are the texts ADR-0014 D4 names.

**And two things the corpus cannot reach**, which are tested here
against documents built in this file: a part that declares a **DTD**, and
a **corrupt archive**. The corpus's ``KNOWN_GAPS`` says why they are not
there, and the corpus's other unreachable shapes are representable in it
(``19-nested-revision`` states the nesting in its XML) or were added once
real material named them (``30-revision-in-drawing-textbox``).

**The drawing's text box.** That fixture is in the corpus **because the
corpus-wide witnesses need its data**: a witness that loops over
``FIXTURES`` can only catch what the corpus holds, and the double-read
survived the corpus-wide count for exactly that reason. The hand-built
case below stays: it asserts what the fixture's gold does not -- which
paragraph reports a text-box revision, and that none of them is nested.

**The witnesses must fail for the property.** Each test below names what
it would take for the reader to stop holding it, and the mutation that
would break it is the thing a reviewer should try. A test that fails
because of an unrelated encoding or lint matter is not a witness.
"""

from __future__ import annotations

import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from docx_corpus import FIXTURES
from docx_fixtures import Fixture, gold_for, write_fixture

from labcairn.material.addressing import render_locator_key, split_locator_key
from labcairn.material.ooxml import CommentEvent, RevisionDocument, read_document
from labcairn.material.units import adapter_for, registered_kinds
from labcairn.sources.locators import DocxLocator
from labcairn.sources.source import SourceKind

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def corpus(tmp_path_factory: pytest.TempPathFactory) -> dict[str, RevisionDocument]:
    """Every fixture in the corpus, read once."""
    directory = tmp_path_factory.mktemp("docx-read")
    documents: dict[str, RevisionDocument] = {}
    for fixture in FIXTURES:
        path = write_fixture(fixture, directory)
        documents[fixture.name] = read_document(path.read_bytes())
    return documents


def _docx_bytes(
    document_xml: str | None,
    comments_xml: str | None = None,
    extra_parts: dict[str, bytes] | None = None,
) -> bytes:
    """A ``.docx`` assembled from parts, for the cases the corpus cannot reach.

    ``document_xml=None`` omits the document part entirely, which is the
    case an archive that is not a Word document at all produces.
    """
    import io

    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="'
        "application/vnd.openxmlformats-package.relationships+xml"
        '"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="'
        "application/vnd.openxmlformats-officedocument.wordprocessingml"
        '.document.main+xml"/>'
        "</Types>"
    )
    package_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="'
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        '/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", package_rels)
        if document_xml is not None:
            archive.writestr("word/document.xml", document_xml)
        if comments_xml is not None:
            archive.writestr("word/comments.xml", comments_xml)
        for name, content in (extra_parts or {}).items():
            archive.writestr(name, content)
    return buffer.getvalue()


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _document(body: str) -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>'
    )


# --------------------------------------------------------------------------- #
# the acceptance measure
# --------------------------------------------------------------------------- #


def test_every_revision_in_the_corpus_is_reported(corpus: dict[str, RevisionDocument]) -> None:
    """Revision recall is 1.0 over the whole corpus.

    **What breaks it:** a reader that skips a revision kind, or that drops
    one when a document holds several. The corpus has 35 revisions across
    the four kinds, and the two paragraphs that carry a revision *and* a
    comment are the ones where a reader that loses one while collecting the
    other shows up.
    """
    expected = sum(len(fixture.revisions) for fixture in FIXTURES)
    found = sum(len(document.revisions) for document in corpus.values())
    assert found == expected, f"{found} of {expected} revisions were reported"


def test_every_revision_carries_its_kind_text_author_and_date(
    corpus: dict[str, RevisionDocument],
) -> None:
    """Each reported revision matches the gold on all four fields.

    **What breaks it:** a reader that reports the text but not the author,
    or that parses the date into a different instant. The date comparison
    is on the *instant*, not on its spelling: ``2026-03-02T09:15:00Z`` and
    ``2026-03-02T09:15:00+00:00`` are the same moment and a reader that
    disagrees about the spelling has not disagreed about the time.
    """
    for fixture in FIXTURES:
        gold = gold_for(fixture)
        document = corpus[fixture.name]
        reported = [
            (
                revision.kind,
                revision.text,
                revision.author if revision.author is not None else "UNKNOWN",
                revision.date,
            )
            for revision in document.revisions
        ]
        expected = [
            (
                entry["kind"],
                entry["text"],
                entry["author"],
                None
                if entry["date"] == "UNKNOWN"
                else datetime.fromisoformat(entry["date"].replace("Z", "+00:00")),
            )
            for entry in gold["revisions"]
        ]
        assert sorted(reported) == sorted(expected), fixture.name


def test_every_deletion_text_is_recovered(corpus: dict[str, RevisionDocument]) -> None:
    """Deletion recovery is 1.0 -- **the text, not an empty run**.

    This is the property the whole phase rests on. The deleted text lives
    in ``w:delText``; a reader that reads ``w:t`` sees an empty run and
    reports a deletion with no text, which is a deletion the ledger cannot
    cite and the mentor's guidance cannot be learned from.

    **What breaks it:** reading ``w:t`` only. Every text-extraction arm in
    the fidelity baseline scores zero here, so this is not a hypothetical.
    """
    for fixture in FIXTURES:
        gold = gold_for(fixture)
        deleted = {entry["text"] for entry in gold["revisions"] if entry["kind"] == "del"}
        recovered = {
            revision.text for revision in corpus[fixture.name].revisions if revision.kind == "del"
        }
        assert deleted == recovered, fixture.name


def test_every_comment_is_reported_including_the_unanchorable_ones(
    corpus: dict[str, RevisionDocument],
) -> None:
    """Comment recall is 1.0, and the five un-anchorable comments are in it.

    **What breaks it:** the failure the upstream study found in a library --
    a count mismatch makes the whole comment set vanish. Here the corpus
    holds a document with two comments and one malformed anchor, and
    **both** comments must be reported. A reader that keeps the first and
    drops the second has found the same bug.
    """
    for fixture in FIXTURES:
        gold = gold_for(fixture)
        expected = {entry["text"] for entry in gold["comments"]}
        reported = {comment.text for comment in corpus[fixture.name].comments}
        assert expected == reported, fixture.name


def test_a_comment_with_no_resolvable_anchor_is_still_a_comment(
    corpus: dict[str, RevisionDocument],
) -> None:
    """The un-anchorable comments keep their body, author and date.

    **What breaks it:** a reader that reports an un-anchorable comment as
    an empty string, or that drops it. The corpus's five un-anchorable
    cases are the design's §7 "isolated comment marker" case and the
    cross-paragraph range, and each of them has a **body that is in the
    file** -- dropping it loses a remark the advisor actually wrote.
    """
    unanchorable = [
        fixture
        for fixture in FIXTURES
        if any(comment["anchor_status"] == "UNKNOWN" for comment in gold_for(fixture)["comments"])
    ]
    assert len(unanchorable) == 5, "the corpus must hold the five un-anchorable cases"

    for fixture in unanchorable:
        document = corpus[fixture.name]
        gold = gold_for(fixture)
        for entry in gold["comments"]:
            if entry["anchor_status"] != "UNKNOWN":
                continue
            match = next(
                comment for comment in document.comments if comment.comment_id == entry["id"]
            )
            assert match.text == entry["text"], fixture.name
            assert match.anchor.status == "unknown", fixture.name
            assert match.anchor.reason, f"{fixture.name}: the reason must be named"


def test_each_unresolvable_anchor_names_its_own_reason(corpus: dict[str, RevisionDocument]) -> None:
    """The four unresolvable-anchor cases are told apart.

    A range that starts and never ends, a range that ends and never
    started, a comment with no range at all, and a range whose two markers
    sit in different paragraphs are **four different defects**. A reader
    that reports them as one has thrown away the distinction between a
    damaged document and an unusual one.
    """
    reasons = {
        fixture.name: {
            comment.anchor.reason
            for comment in corpus[fixture.name].comments
            if comment.anchor.status == "unknown"
        }
        for fixture in FIXTURES
    }
    assert reasons["12-orphan-comment-start-only"] == {"the comment's range starts but never ends"}
    assert reasons["13-orphan-comment-end-only"] == {"the comment's range ends but never starts"}
    assert reasons["14-comment-without-anchor"] == {"the comment carries no range markers"}
    assert reasons["29-comment-spanning-two-paragraphs"] == {
        "the comment's range spans two paragraphs"
    }

    # **Four defects, four phrases.** A reader that reused one phrase for
    # two of them would say the corpus's cases are the same case, and the
    # distinction is the whole point of naming them.
    named = [
        next(iter(reasons[name]))
        for name in (
            "12-orphan-comment-start-only",
            "13-orphan-comment-end-only",
            "14-comment-without-anchor",
            "29-comment-spanning-two-paragraphs",
        )
    ]
    assert len(set(named)) == 4, f"the four reasons are not four phrases: {named}"


def test_a_comment_whose_range_spans_two_paragraphs_has_no_resolvable_anchor(
    corpus: dict[str, RevisionDocument],
) -> None:
    """A range across two paragraphs is reported as an anchor it cannot name.

    **This is the case the owner's real material found.** Word writes a
    comment covering several paragraphs with its ``w:commentRangeStart`` in
    the first paragraph and its ``w:commentRangeEnd`` in the last, and
    **each marker carries an offset within its own paragraph**. The two
    offsets are therefore offsets into two different texts.

    The reader used to pair them: it reported the start marker's paragraph
    with the end marker's offset, which names a range that cannot exist.
    On the corpus that is characters 0-106 of a 61-character paragraph.
    On the owner's ``v03-chinese-draft.docx`` it is comment 192, stored as
    paragraph 64 characters 0-134, in a paragraph whose baseline is 10
    characters long.

    **What breaks it:** a reader that borrows the other paragraph's offset
    instead of saying it cannot name the range. The address it stores
    resolves to text nobody wrote, and the chain that follows it cites
    text the advisor never marked.

    **And the comment itself is untouched.** The body, the author and the
    date are in the file, and dropping them because the anchor did not
    pair is the failure the upstream study found in a library.
    """
    document = corpus["29-comment-spanning-two-paragraphs"]
    comment = next(c for c in document.comments if c.comment_id == "215")

    assert comment.anchor.status == "unknown", (
        "a range that spans two paragraphs must not be reported as resolved: "
        "the end offset belongs to another paragraph"
    )
    assert comment.anchor.reason == "the comment's range spans two paragraphs"
    assert comment.anchor.paragraph == 0, "the paragraph the range starts in is kept"
    assert comment.anchor.start is None
    assert comment.anchor.end is None, (
        "the end offset belongs to the other paragraph and must not be borrowed"
    )
    assert comment.anchor.text == ""

    # The comment is still a comment: body, author and date are all there.
    assert comment.text == "This remark covers both paragraphs."
    assert comment.author == "Prof. Lin"
    assert comment.date == datetime(2026, 3, 2, 9, 30, tzinfo=UTC)


def test_a_resolved_anchor_never_names_a_range_outside_its_own_paragraph(
    corpus: dict[str, RevisionDocument],
) -> None:
    """Every resolved anchor slices the paragraph it names, and says so.

    **This is the invariant that was broken.** A resolved anchor is a pair
    of offsets into one paragraph's baseline, and the text it carries is
    that slice. A reader that reports an offset borrowed from another
    paragraph produces an address that resolves to nothing -- or, worse, to
    text nobody wrote.

    **What breaks it:** a reader that pairs a start marker's paragraph
    with an end marker's offset without asking whether they are the same
    paragraph. The corpus holds the case now, so the question is asked.

    **And it is checked over the whole corpus**, not over the one fixture
    that carries the case: an address is an address whatever document it
    came from, and a reader that is right on one file can be wrong on the
    next.
    """
    for fixture in FIXTURES:
        document = corpus[fixture.name]
        for comment in document.comments:
            anchor = comment.anchor
            if anchor.status != "resolved":
                continue
            assert anchor.paragraph is not None, fixture.name
            assert anchor.start is not None and anchor.end is not None, fixture.name
            baseline = document.baseline_paragraphs[anchor.paragraph]
            assert 0 <= anchor.start <= anchor.end <= len(baseline), (
                f"{fixture.name}: comment {comment.comment_id} names characters "
                f"{anchor.start}-{anchor.end} of a {len(baseline)}-character "
                f"paragraph"
            )
            assert anchor.text == baseline[anchor.start : anchor.end], (
                f"{fixture.name}: comment {comment.comment_id} carries text that is "
                f"not the text its offsets name"
            )


def test_a_missing_author_or_date_is_unknown_and_never_guessed(
    corpus: dict[str, RevisionDocument],
) -> None:
    """The absent metadata stays absent.

    **What breaks it:** a reader that falls back to the document's author
    property, to the file's mtime, or to the empty string. The corpus holds
    all three cases -- no author, no date, and neither -- and the design's
    rule is that a missing author is ``UNKNOWN``, never a guess.
    """
    document = corpus["06-insertion-without-author"]
    revision = document.revisions[0]
    assert revision.author is None
    assert revision.date == datetime(2026, 3, 2, 9, 15, tzinfo=UTC)

    document = corpus["07-insertion-without-date"]
    revision = document.revisions[0]
    assert revision.author == "Prof. Lin"
    assert revision.date is None

    document = corpus["08-insertion-without-author-or-date"]
    revision = document.revisions[0]
    assert revision.author is None
    assert revision.date is None

    # And the event still exists: missing metadata does not delete the
    # change.
    assert len(document.revisions) == 1
    assert document.revisions[0].text == "carefully"


def test_the_two_views_are_the_texts_adr_0014_names(corpus: dict[str, RevisionDocument]) -> None:
    """The accepted view has the insertions and not the deletions; the
    rejected view has the deletions and not the insertions.

    **What breaks it:** a reader that computes one text and uses it for
    both, which is what a reader that ignores the revision elements does.
    The corpus holds a document with one of each, so the two views differ
    and the difference is observable.
    """
    document = corpus["04-insert-and-delete"]
    assert "repeated" in document.accepted_text
    assert "a single" not in document.accepted_text
    assert "a single" in document.rejected_text
    assert "repeated" not in document.rejected_text


def test_reading_does_not_change_the_bytes(tmp_path: Path) -> None:
    """The original is untouched.

    **What breaks it:** a reader that opens the archive for writing, or
    that "helpfully" accepts the revisions. ADR-0014 D6 forbids the
    second, and the first-party ``docx`` skill's ``accept_changes.py`` is
    exactly the tool that would do it -- which is why the rule is a
    property and not a convention.

    **And this test is the *weak* half of the pair.** ``read_document``
    takes bytes, so it **cannot** change the file they came from: the
    property holds by construction rather than by the reader's care. The
    strong half is :func:`test_the_reader_module_writes_nothing`, which
    watches the module itself, because the way this property breaks is
    somebody adding a write path in a later edit.
    """
    fixture = _fixture("23-everything-at-once")
    path = write_fixture(fixture, tmp_path)
    before = path.read_bytes()

    read_document(before)

    assert path.read_bytes() == before, "the reader changed the original"


def test_the_reader_module_writes_nothing() -> None:
    """The reader has no write path at all.

    **This is the strong half of the "the original is untouched" pair**, and
    it exists because the other half holds by construction: ``read_document``
    takes bytes and cannot change the file they came from. The way this
    property actually breaks is somebody adding a write — a "helpful"
    normalisation, an "accept the revisions" convenience — in a later edit,
    and the file-bytes test would not notice it until the damage was done.

    The watch is on the module's **source**, so it fails on the edit rather
    than on a document that has already been rewritten. This is the same
    shape as the project's other source-level watches: the rule reads the
    code, so the rule itself needs a test of its own.

    **What breaks it:** any call that writes — ``write_bytes``, ``write_text``,
    an ``open(...)`` in write mode, or a ``shutil`` move or copy out of the
    archive.
    """
    import inspect

    import labcairn.material.ooxml as ooxml

    source = inspect.getsource(ooxml)
    forbidden = (
        "write_bytes",
        "write_text",
        "shutil.copy",
        "shutil.move",
        "os.remove",
        "os.unlink",
        'ZipFile(data, "w")',
    )
    for needle in forbidden:
        assert needle not in source, (
            f"the OOXML reader now contains {needle!r}. It must read and never "
            f"write: a reader that rewrites the document it was handed is the "
            f"failure ADR-0014 D6 names."
        )


def test_no_test_writes_a_document_into_the_repository() -> None:
    """The tests do not leave files in the checkout.

    **This exists because it happened.** An earlier version of this file
    passed ``Path(".")`` as the directory to write a fixture into, and a
    test run left twenty-eight ``.docx`` files in the repository root --
    untracked, and one ``git add -A`` away from the commit. The project's
    own rule is that a run's working directory must not be inside the
    checkout, and the tests obey it now; this watch is what keeps them
    obeying it.

    **The watch is on the calls, not on the text.** A source scan for the
    bare text would match this test's own source -- a watch that can never
    pass is not a watch -- so the check reads the **call sites** and asks
    where each fixture is written.

    **What breaks it:** any ``write_fixture`` whose directory is the
    repository root rather than the test's temporary directory.
    """
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(sys.modules[__name__]))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "id", None)
        if name != "write_fixture" or len(node.args) < 2:
            continue
        directory = node.args[1]
        # The repository root is the literal ``Path(".")`` or a name bound
        # to it. Anything else -- a fixture's own temporary directory, a
        # module-level constant -- is left alone.
        if isinstance(directory, ast.Call):
            inner = getattr(directory.func, "id", None)
            if inner == "Path" and directory.args:
                first = directory.args[0]
                if isinstance(first, ast.Constant) and first.value in (".", ""):
                    offenders.append(ast.unparse(node))
    assert not offenders, (
        "these calls write a fixture into the repository root, and a test run "
        f"leaves files in the checkout: {offenders}. Fixtures belong under "
        f"the test's own temporary directory."
    )


# --------------------------------------------------------------------------- #
# what the corpus cannot reach
# --------------------------------------------------------------------------- #


def test_a_revision_nested_inside_another_is_reported_separately() -> None:
    """Nesting is not flattened.

    Word permits a ``w:del`` inside a ``w:ins``. A reader that flattens it
    cannot tell "inserted and then deleted" from "inserted", and those are
    different histories.

    **What breaks it:** a reader that stops at the first revision element
    it finds in a paragraph, or that treats a nested revision as part of
    its parent's text.
    """
    body = (
        "<w:p>"
        '<w:r><w:t xml:space="preserve">The method estimates </w:t></w:r>'
        '<w:ins w:id="1" w:author="Prof. Lin" w:date="2026-03-02T09:15:00Z">'
        '<w:r><w:t xml:space="preserve">carefully</w:t></w:r>'
        '<w:del w:id="2" w:author="Prof. Lin" w:date="2026-03-02T09:16:00Z">'
        '<w:r><w:delText xml:space="preserve">never</w:delText></w:r>'
        "</w:del>"
        "</w:ins>"
        "</w:p>"
    )
    document = read_document(_docx_bytes(_document(body)))

    assert len(document.revisions) == 2, "the nested revision must be reported"
    kinds = {revision.kind for revision in document.revisions}
    assert kinds == {"ins", "del"}
    nested = [revision for revision in document.revisions if revision.nested]
    assert len(nested) == 1
    assert nested[0].kind == "del"

    # The deleted text is still recoverable -- nesting does not lose it.
    deleted = [revision for revision in document.revisions if revision.kind == "del"]
    assert deleted[0].text == "never"

    # And the nesting is disclosed, because a reader that reports it
    # silently has flattened it as far as the caller can tell.
    assert "docx_nested_revision" in {problem.code for problem in document.problems}


_MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
_WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_WPS = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
_V = "urn:schemas-microsoft-com:vml"


def _document_with_drawing_namespaces(body: str) -> str:
    """A ``w:document`` whose root also declares the drawing namespaces.

    The drawing the body below carries is the shape real material holds:
    an ``mc:AlternateContent`` with a modern ``Choice`` and a VML
    ``Fallback``, each wrapping a text box of paragraphs.
    """
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{W}" xmlns:mc="{_MC}" xmlns:wp="{_WP}" '
        f'xmlns:a="{_A}" xmlns:wps="{_WPS}" xmlns:v="{_V}">'
        f"<w:body>{body}</w:body></w:document>"
    )


def test_a_revision_inside_a_drawing_textbox_is_reported_once() -> None:
    """One tracked change, one event -- even across a drawing's text box.

    Real material holds a paragraph whose run carries a figure, and the
    figure carries a text box of its own paragraphs, and ``iter`` finds
    those paragraphs just as it finds the body's. A walk that crosses
    into a text box after the box's own paragraphs have been scanned
    reports the same ``w:ins`` twice -- four changes became six events
    on the file that found this. The reporter is the **nearest
    paragraph**: the outer walk keeps advancing the offset through the
    box (the outer paragraph's text counts the box's text either way,
    and the two coordinate systems must agree), but it reports nothing
    there.

    **What breaks it:** a walk that reports a revision inside a nested
    paragraph's subtree as well as the nested paragraph's own scan.
    """
    body = (
        # A plain paragraph: the ordinary case, untouched by the drawing.
        "<w:p>"
        '<w:ins w:id="1" w:author="Prof. Lin" w:date="2026-03-02T09:15:00Z">'
        '<w:r><w:t xml:space="preserve">plain insert</w:t></w:r>'
        "</w:ins>"
        "</w:p>"
        # The drawing paragraph: one revision whose run carries the
        # AlternateContent, whose two branches each carry a text box
        # holding one paragraph of two revisions.
        "<w:p>"
        '<w:ins w:id="2" w:author="Prof. Lin" w:date="2026-03-02T09:15:00Z">'
        "<w:r>"
        "<mc:AlternateContent>"
        '<mc:Choice Requires="wps">'
        "<w:drawing>"
        "<wp:anchor><a:graphic><a:graphicData>"
        "<wps:wsp><wps:txbx><w:txbxContent>"
        "<w:p>"
        '<w:ins w:id="3" w:author="Prof. Lin" w:date="2026-03-02T09:15:00Z">'
        '<w:r><w:t xml:space="preserve">choice first</w:t></w:r></w:ins>'
        '<w:ins w:id="4" w:author="Prof. Lin" w:date="2026-03-02T09:15:00Z">'
        '<w:r><w:t xml:space="preserve">choice second</w:t></w:r></w:ins>'
        "</w:p>"
        "</w:txbxContent></wps:txbx></wps:wsp>"
        "</a:graphicData></a:graphic></wp:anchor>"
        "</w:drawing>"
        "</mc:Choice>"
        "<mc:Fallback>"
        "<w:pict>"
        "<v:shape><v:textbox><w:txbxContent>"
        "<w:p>"
        '<w:ins w:id="5" w:author="Prof. Lin" w:date="2026-03-02T09:15:00Z">'
        '<w:r><w:t xml:space="preserve">fallback first</w:t></w:r></w:ins>'
        '<w:ins w:id="6" w:author="Prof. Lin" w:date="2026-03-02T09:15:00Z">'
        '<w:r><w:t xml:space="preserve">fallback second</w:t></w:r></w:ins>'
        "</w:p>"
        "</w:txbxContent></v:textbox></v:shape>"
        "</w:pict>"
        "</mc:Fallback>"
        "</mc:AlternateContent>"
        "</w:r>"
        "</w:ins>"
        "</w:p>"
    )
    document = read_document(_docx_bytes(_document_with_drawing_namespaces(body)))

    # The file holds six revision elements and six is what comes back:
    # the outer one, and the two pairs inside the two text boxes.
    assert len(document.revisions) == 6, (
        f"expected one event per revision element, got {len(document.revisions)}"
    )

    # And no two events share an address -- the four text-box revisions
    # were the four whose paths collided with themselves.
    paths = [revision.locator.element_path for revision in document.revisions]
    assert len(set(paths)) == len(paths), "two events share one element path"

    # The text-box revisions are reported by their own paragraphs (the
    # document order puts both boxes' paragraphs after the two body
    # ones), with their own text, and not as the outer revision's
    # nested revision.
    # A revision may sit outside every paragraph (a table row's mark does),
    # and then its paragraph is ``None``. This document holds none of those:
    # every change here is inside a paragraph, and the assertion says so
    # rather than assuming it, because a document that grew a row mark would
    # otherwise silently change what the four keys below mean.
    by_paragraph: dict[int, list[str]] = {}
    for revision in document.revisions:
        assert revision.paragraph is not None, (
            f"{revision.locator.element_path}: this document holds no revision outside a paragraph"
        )
        by_paragraph.setdefault(revision.paragraph, []).append(revision.text)
    assert sorted(by_paragraph) == [0, 1, 2, 3]
    assert by_paragraph[0] == ["plain insert"]
    assert sorted(by_paragraph[2]) == ["choice first", "choice second"]
    assert sorted(by_paragraph[3]) == ["fallback first", "fallback second"]
    assert all(not revision.nested for revision in document.revisions), (
        "a revision in its own paragraph is not a nested revision"
    )
    assert "docx_nested_revision" not in {problem.code for problem in document.problems}


# **The document every one of the three witnesses below reads.** It holds a
# revision in each of the three places one can sit, so that the partition the
# reader draws -- *the nearest paragraph reports it, and where there is no
# paragraph the document does* -- is checked on one file rather than on three:
#
# * a ``w:ins`` in a paragraph's run sequence (id 301): reported by that
#   paragraph, with its text and a paragraph index;
# * a ``w:ins`` under a paragraph's own properties (id 304, ``w:pPr/w:rPr``):
#   the paragraph **mark** inserted, still inside a paragraph, an empty
#   change with a paragraph index;
# * a ``w:ins`` and a ``w:del`` on a table row's properties (ids 302, 303,
#   ``w:trPr``): outside every paragraph, empty, and -- before this shape was
#   read -- invisible;
# * a third row's ``w:ins`` (id 305) with **no author and no date at all**:
#   the new code path reads the same two attributes the paragraph path reads,
#   and a scan that filled an absent author with a guess is caught here rather
#   than in the paragraph case, where the rule has had a witness for a year.
#
# The names are invented and the sentences are about a parameter, like the
# rest of this file: a document built to hold a shape, not to hold a meaning.
_ROW_MARKER_BODY = (
    "<w:p>"
    '<w:r><w:t xml:space="preserve">The body sentence stands first.</w:t></w:r>'
    '<w:ins w:id="301" w:author="Prof. Lin" w:date="2026-03-02T09:15:00Z">'
    '<w:r><w:t xml:space="preserve"> and carries a change of its own</w:t></w:r>'
    "</w:ins>"
    "</w:p>"
    "<w:tbl>"
    '<w:tblPr><w:tblW w:w="0" w:type="auto"/></w:tblPr>'
    "<w:tr>"
    '<w:trPr><w:ins w:id="302" w:author="Prof. Lin" w:date="2026-03-02T09:16:00Z"/></w:trPr>'
    "<w:tc>"
    '<w:p><w:r><w:t xml:space="preserve">The inserted row states one cell.</w:t></w:r></w:p>'
    "</w:tc>"
    "</w:tr>"
    "<w:tr>"
    '<w:trPr><w:del w:id="303" w:author="Dr. Ayala" w:date="2026-03-02T09:17:00Z"/></w:trPr>'
    "<w:tc>"
    '<w:p><w:r><w:t xml:space="preserve">The deleted row states one cell.</w:t></w:r></w:p>'
    "</w:tc>"
    "</w:tr>"
    "<w:tr>"
    # No ``w:author`` and no ``w:date`` at all: the absence is the answer.
    '<w:trPr><w:ins w:id="305"/></w:trPr>'
    "<w:tc>"
    '<w:p><w:r><w:t xml:space="preserve">A row whose mark names nobody.</w:t></w:r></w:p>'
    "</w:tc>"
    "</w:tr>"
    "</w:tbl>"
    "<w:p>"
    "<w:pPr><w:rPr>"
    '<w:ins w:id="304" w:author="Prof. Lin" w:date="2026-03-02T09:18:00Z"/>'
    "</w:rPr></w:pPr>"
    '<w:r><w:t xml:space="preserve">A paragraph whose mark was inserted last.</w:t></w:r>'
    "</w:p>"
)


def _row_marker_document() -> RevisionDocument:
    return read_document(_docx_bytes(_document(_ROW_MARKER_BODY)))


def test_a_table_row_marker_is_reported_though_no_paragraph_holds_it() -> None:
    """A change on a row's properties is a tracked change, and is reported.

    The fidelity baseline recorded this and left it unfixed
    (``docs/acceptance/LC-P2-07-fidelity-baseline.md``, the closing paragraph
    of §5.6): Word writes a table row's insertion as ``w:trPr/w:ins`` -- an
    empty element outside every paragraph -- and a reader that walks
    paragraphs never reaches it. Real material holds one: a review copy whose
    part carries 223 revision elements while the reader reported 222.

    **What breaks it:** a scan that reports only what a paragraph contains.
    That is the defect, and this witness is the property the fix holds: the
    row's mark comes back as an event.

    **And what the event carries is what the file says.** The marker is
    empty, so the event's text is empty -- not the row's cell prose, which
    belongs to the cells' paragraphs and is reported by them. Its author,
    its date, its ``w:id`` and its address are its own. It has no paragraph
    and no place in any baseline, because the file gives it neither: a
    paragraph index invented here would name a paragraph the change is not
    in, and a coordinate in a text the element does not sit in is a
    coordinate nobody can check.
    """
    document = _row_marker_document()
    by_id = {revision.element_id: revision for revision in document.revisions}

    inserted = by_id["302"]
    assert inserted.kind == "ins"
    assert inserted.text == "", "the row's marker holds no text of its own"
    assert inserted.author == "Prof. Lin"
    assert inserted.date == datetime(2026, 3, 2, 9, 16, tzinfo=UTC)
    assert inserted.locator.view == "accepted"
    assert inserted.locator.char_start == 0
    assert inserted.locator.char_end == 0
    assert inserted.locator.element_path.endswith("/trPr[1]/ins[1]"), inserted.locator.element_path
    assert "/tbl[1]/tr[1]/" in inserted.locator.element_path, "it names the row it marks"
    assert inserted.paragraph is None
    assert inserted.baseline_start is None
    assert inserted.baseline_end is None
    assert inserted.nested is False

    deleted = by_id["303"]
    assert deleted.kind == "del"
    assert deleted.text == ""
    assert deleted.author == "Dr. Ayala"
    assert deleted.locator.view == "rejected", "a deletion is read in the view it lives in"
    assert deleted.locator.element_path.endswith("/trPr[1]/del[1]"), deleted.locator.element_path
    assert deleted.paragraph is None

    # **And a marker that names nobody stays unnamed on the new path too.**
    # The rule "a missing author is absent, never guessed" was witnessed
    # where the paragraph scan reads the attributes; this row's mark is read
    # by the document scan, which reads the same two attributes and must
    # answer the same way. A scan that fell back to the empty string, or to
    # somebody else's name, is caught here.
    unnamed = by_id["305"]
    assert unnamed.kind == "ins"
    assert unnamed.author is None, "no w:author, so no author -- and not the empty string"
    assert unnamed.date is None, "no w:date, so no date -- and not the file's mtime"
    assert unnamed.text == ""
    assert unnamed.paragraph is None

    # The cells' prose is not lost and not double-counted: it is the cells'
    # paragraphs, and they stand in the document's paragraph list once each.
    assert "The inserted row states one cell." in document.paragraphs
    assert document.paragraphs.count("The inserted row states one cell.") == 1


def test_a_revision_in_a_paragraph_is_still_reported_by_that_paragraph() -> None:
    """The partition runs on the container, not on the element's shape.

    A ``w:ins`` under ``w:pPr/w:rPr`` is empty too -- it marks the
    paragraph's own mark -- and it is *inside* a paragraph, so the paragraph
    reports it and the event carries a paragraph index. The two empty changes
    in this document differ in exactly that one field, and a reader that
    reported both the same way would be saying something the file does not:
    either that a row's mark sits in a paragraph, or that a paragraph's own
    mark sits in none.

    **What breaks it:** a scan that keys on "is this element empty", or one
    that hands a paragraph's revision to the document scan as well.
    """
    document = _row_marker_document()
    by_id = {revision.element_id: revision for revision in document.revisions}

    paragraph_mark = by_id["304"]
    assert paragraph_mark.text == ""
    assert paragraph_mark.paragraph is not None, "a paragraph holds it"
    assert paragraph_mark.baseline_start is not None
    assert paragraph_mark.locator.element_path.endswith("/pPr[1]/rPr[1]/ins[1]")

    run_change = by_id["301"]
    assert run_change.text == " and carries a change of its own"
    assert run_change.paragraph is not None
    assert run_change.baseline_start is not None

    row_mark = by_id["302"]
    assert row_mark.paragraph is None
    assert row_mark.baseline_start is None


def test_a_table_row_marker_is_reported_once_and_not_twice() -> None:
    """One marker, one event -- the §5.6 property, now over both reporters.

    Exactly-once was proved for revisions a paragraph contains. It has to be
    proved again for a document read by **two** scans, because the new risk
    is the one the double-read already was: the same element reported twice,
    two events at one address, and one derived row id for two changes.

    **What breaks it:** a walk that reports an element here and in the
    paragraph scan, or one that emits a marker twice; and an address that
    names two elements.
    """
    document = _row_marker_document()

    addresses = [revision.locator.element_path for revision in document.revisions]
    assert len(set(addresses)) == len(addresses), "two events share one element path"
    assert sorted(addresses) == sorted(_row_marker_element_paths()), (
        "the events are not the elements the part holds"
    )


def _row_marker_element_paths() -> list[str]:
    """The part's revision elements, counted straight from the XML.

    The private function is imported because the witness is about it: the
    count has to use the reader's own addressing, or it measures a copy of
    the rule instead of the rule the reader runs.
    """
    from xml.etree import ElementTree

    from labcairn.material.ooxml import _element_path, _revision_kind

    xml = _document(_ROW_MARKER_BODY)
    root = ElementTree.fromstring(xml)
    elements = [element for element in root.iter() if _revision_kind(element.tag) is not None]
    return [_element_path(element, root) for element in elements]


def test_the_reader_reports_each_revision_element_exactly_once(tmp_path: Path) -> None:
    """Over the whole corpus, the events' addresses are the elements' addresses.

    The file holds what it holds: counted straight from ``document.xml``,
    the revision elements are exactly the events the reader reports, one
    address each, no more and no fewer. This is the property the chain's
    writer rests on -- ``_revision_event_id`` derives a row's identity
    from the element's path, and it can only do that while one path
    names one element.

    **What breaks it:** a walk that reports an element twice (the
    drawing-text-box defect), a walk that skips one, or an
    ``_element_path`` that gives two elements one address.

    **And the count runs over the shape the corpus cannot declare.** The
    corpus's gold model anchors a revision in a paragraph, so a marker on a
    table row's properties -- outside every paragraph -- has no place in it;
    the hand-built document below is therefore read by this witness as well,
    because a count that loops only over ``FIXTURES`` can only catch what the
    corpus holds, and the double-read survived exactly that for exactly that
    reason (§5.6 of the fidelity baseline).

    The two private functions are imported because this witness is
    about them: counting with anything else would measure a copy of the
    rule, not the rule the reader runs.
    """
    import io
    from xml.etree import ElementTree

    from labcairn.material.ooxml import _element_path, _revision_kind

    documents: list[tuple[str, bytes]] = [
        (fixture.name, write_fixture(fixture, tmp_path).read_bytes()) for fixture in FIXTURES
    ]
    documents.append(("hand-built-table-row-markers", _docx_bytes(_document(_ROW_MARKER_BODY))))

    for name, raw in documents:
        document = read_document(raw)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
        elements = [element for element in root.iter() if _revision_kind(element.tag) is not None]
        addresses = [_element_path(element, root) for element in elements]
        event_addresses = [revision.locator.element_path for revision in document.revisions]
        assert sorted(event_addresses) == sorted(addresses), name
        assert len(set(event_addresses)) == len(event_addresses), name


def test_the_derived_revision_event_id_names_one_change_per_address(
    tmp_path: Path,
) -> None:
    """The writer's derived id distinguishes what the reader distinguishes.

    ``_revision_event_id`` hashes the version, the part and the element's
    path, and its docstring claims the path is unique inside a part. The
    reader witnesses that uniqueness one test above; this witness holds
    the id to it: two events that differ in address get different ids
    (a writer that drops the path from the digest would fold two
    revisions into one row), the same address always gets the same id
    (recording the same file twice is the same rows, and an id that
    depends on when it was made is not an identity), and so two
    different revisions at one address cannot both land -- which is why
    the reader's own uniqueness is the property that matters.

    The private function is imported because the witness is about it.
    """
    from labcairn.papers.revisions import _revision_event_id

    for fixture in FIXTURES:
        raw = write_fixture(fixture, tmp_path).read_bytes()
        document = read_document(raw)
        if not document.revisions:
            continue
        ids = [
            _revision_event_id(
                "version-under-test",
                revision.locator.part or "",
                revision.locator.element_path or "",
            )
            for revision in document.revisions
        ]
        assert len(ids) == len(set(ids)), (
            f"two revisions of {fixture.name} derive the same revision_event_id"
        )
        first = document.revisions[0]
        again = _revision_event_id(
            "version-under-test", first.locator.part or "", first.locator.element_path or ""
        )
        assert again == ids[0], fixture.name


def test_the_revision_event_id_carries_an_occurrence_per_change_at_one_address() -> None:
    """The identity is per change, not per path.

    ``_revision_event_id`` used to hash ``(version, part, element_path)``
    alone and its docstring asserted the path is unique inside a part -- a
    claim about a *reader*, held up as if it were a constraint. This witness
    holds the property that claim was standing in for, and the two halves of
    it are both tested here because each fails a different mutation:

    * **The first change at an address keeps the digest every stored row
      already carries.** ``occurrence`` defaults to ``0`` and that path
      hashes ``version|part|path`` with no suffix at all -- byte-for-byte the
      pre-occurrence id. This is what lets the fix land without moving the
      ``2164`` rows in the pilot's ``revision_events`` or re-pointing a rule
      bound to one; a derivation that folded the occurrence in unconditionally
      (``f"...\x00{occurrence}"`` with no ``if``) would change every id and
      orphan every binding, and this assertion is red the moment it does.
    * **A second and third genuinely different change at one address each get
      a different id.** They are distinct events, so a writer that ignored the
      occurrence -- the silent-loss defect itself -- would fold them onto the
      first row, and the assertion ``len({id0, id1, id2}) == 3`` goes red.
    """
    import hashlib

    from labcairn.papers.revisions import _revision_event_id

    version, part, path = "ver-under-test", "word/document.xml", "/document[1]/body[1]/p[1]/ins[1]"

    legacy = "rv-" + hashlib.sha256(f"{version}\x00{part}\x00{path}".encode()).hexdigest()[:16]
    assert _revision_event_id(version, part, path) == legacy, "the first change at an address moved"
    assert _revision_event_id(version, part, path, 0) == legacy

    first = _revision_event_id(version, part, path, 0)
    second = _revision_event_id(version, part, path, 1)
    third = _revision_event_id(version, part, path, 2)
    assert len({first, second, third}) == 3, "two changes at one address collide on one id"


def test_the_revision_event_id_is_re_derivable_not_position_dependent() -> None:
    """The occurrence is a function of the change, so re-reading is stable.

    The writer numbers each address from the document's own order, not from
    any caller's arrangement, so the same ``(version, part, path, occurrence)``
    gives the same id every time it is asked. **What breaks it:** mixing the
    wall clock or a per-call counter that starts elsewhere into the digest --
    recording the same manuscript a second time would then mint new ids for
    the same changes, and the rows already in the store would be found by
    neither the replay check nor the reader.
    """
    from labcairn.papers.revisions import _revision_event_id

    args = ("ver-a", "word/document.xml", "/document[1]/body[1]/p[3]/del[1]", 1)
    assert _revision_event_id(*args) == _revision_event_id(*args)
    assert _revision_event_id(*args) == _revision_event_id(*args)


def test_a_part_that_declares_a_dtd_is_refused() -> None:
    """A DTD is refused, and the refusal says which part and why.

    **What breaks it:** a reader that expands entities. Entity expansion is
    a denial-of-service vector, and the standard library's parser is not
    the place to decide that a document's entities are safe.
    """
    body = (
        '<!DOCTYPE w:document [<!ENTITY x "expanded">]>'
        f'<w:document xmlns:w="{W}"><w:body>'
        "<w:p><w:r><w:t>text</w:t></w:r></w:p>"
        "</w:body></w:document>"
    )
    document = read_document(_docx_bytes(body))

    codes = {problem.code for problem in document.problems}
    assert "docx_part_refused" in codes
    assert document.revisions == ()
    problem = next(p for p in document.problems if p.code == "docx_part_refused")
    assert "DTD" in problem.detail
    assert "word/document.xml" in problem.detail


def test_a_corrupt_archive_is_refused_and_says_so() -> None:
    """Bytes that are not a Word document are a refusal, not an empty document.

    **What breaks it:** a reader that raises instead of refusing, or that
    reports "no revisions" for a file it could not open. ADR-0004 A7: *"we
    could not look" is not "there was nothing there."*
    """
    document = read_document(b"this is not a zip file at all")

    codes = {problem.code for problem in document.problems}
    assert codes == {"docx_unreadable"}
    assert document.revisions == ()
    assert document.comments == ()
    assert "hashed" in document.problems[0].detail


def test_a_zip_without_a_document_part_is_refused() -> None:
    """An archive with no ``word/document.xml`` is not a Word document.

    **What breaks it:** a reader that reports an empty document for an
    archive it did not understand.
    """
    document = read_document(_docx_bytes(None, extra_parts={"readme.txt": b"hello"}))

    codes = {problem.code for problem in document.problems}
    assert codes == {"docx_part_absent"}


# --------------------------------------------------------------------------- #
# the addresses
# --------------------------------------------------------------------------- #


def test_a_revision_locator_resolves_to_the_revisions_own_text(
    corpus: dict[str, RevisionDocument],
) -> None:
    """Every revision's locator resolves to the text the revision carries.

    **What breaks it:** a locator that addresses the paragraph rather than
    the revision element, which would resolve to the paragraph's text and
    make the deleted text unreachable by citation.
    """
    for fixture in FIXTURES:
        for revision in corpus[fixture.name].revisions:
            locator = revision.locator
            assert locator.char_start == 0
            assert locator.char_end == len(revision.text)
            expected_view = "accepted" if revision.kind in ("ins", "moveTo") else "rejected"
            assert locator.view == expected_view


def test_a_deletion_is_addressed_in_the_rejected_view(corpus: dict[str, RevisionDocument]) -> None:
    """A deletion's address is in the rejected view, because that is where
    its text is.

    **What breaks it:** a reader that addresses a deletion in the accepted
    view. The deleted text is not there, so the address would resolve to
    nothing -- which is the whole point of the view field.
    """
    for fixture in FIXTURES:
        for revision in corpus[fixture.name].revisions:
            if revision.kind in ("del", "moveFrom"):
                assert revision.locator.view == "rejected"
            else:
                assert revision.locator.view == "accepted"


def test_the_same_element_in_the_two_views_is_two_addresses() -> None:
    """The view is part of the address, and the key carries it.

    **What breaks it:** a key that omits the view, so the accepted and the
    rejected text of one element collided on one row -- and the UNIQUE
    would have protected the wrong one.
    """
    accepted = DocxLocator(
        part="word/document.xml",
        element_path="/w:document/w:body/w:p[1]",
        view="accepted",
        char_start=0,
        char_end=10,
    )
    rejected = accepted.model_copy(update={"view": "rejected"})

    assert render_locator_key(accepted) != render_locator_key(rejected)
    assert split_locator_key(render_locator_key(accepted))["v"] == "accepted"
    assert split_locator_key(render_locator_key(rejected))["v"] == "rejected"


def test_a_docx_locator_key_round_trips(corpus: dict[str, RevisionDocument]) -> None:
    """Every key the reader produces parses back into its components.

    **What breaks it:** a renderer that writes a value containing a
    separator, which would shift a boundary on the way back.
    """
    for fixture in FIXTURES:
        document = corpus[fixture.name]
        for revision in document.revisions:
            fields = split_locator_key(render_locator_key(revision.locator))
            assert fields["k"] == "docx"
            assert fields["p"] == "word/document.xml"
            assert fields["v"] == revision.locator.view


# --------------------------------------------------------------------------- #
# the adapter
# --------------------------------------------------------------------------- #


def test_docx_is_a_registered_kind_and_a_path_maps_to_it() -> None:
    """The kind is registered, and ``.docx`` maps to it.

    **What breaks it:** a kind with no adapter, which would make every
    ``.docx`` a material that is inventoried and cannot be used -- the
    state ``OTHER`` was for.
    """
    assert SourceKind.DOCX in registered_kinds()
    from labcairn.material.ingest import kind_for_path

    assert kind_for_path("paper.docx") is SourceKind.DOCX
    assert kind_for_path("PAPER.DOCX") is SourceKind.DOCX


def test_the_adapter_produces_a_unit_for_every_paragraph_revision_and_comment(
    corpus: dict[str, RevisionDocument],
    tmp_path: Path,
) -> None:
    """Everything the reader found is citable.

    **What breaks it:** an adapter that reports the revisions and comments
    as a side-channel with no address, which would make them
    unreferenceable -- the same defect as not reporting them, because a
    claim cannot cite what has no address.
    """
    adapter = adapter_for(SourceKind.DOCX)
    for fixture in FIXTURES:
        document = corpus[fixture.name]
        result = adapter.extract(write_fixture(fixture, tmp_path).read_bytes())
        expected = len(document.paragraphs) + len(document.revisions) + len(document.comments)
        assert len(result.units) == expected, fixture.name
        for unit in result.units:
            assert isinstance(unit.locator, DocxLocator)


def test_the_adapter_discloses_the_same_problems_the_reader_found(tmp_path: Path) -> None:
    """The adapter does not swallow what the reader disclosed.

    **What breaks it:** an adapter that returns the units and drops the
    problems, which is the "an adapter that can only report success is
    indistinguishable from one that silently dropped a comment" failure.
    """
    adapter = adapter_for(SourceKind.DOCX)
    fixture = _fixture("23-everything-at-once")
    result = adapter.extract(write_fixture(fixture, tmp_path).read_bytes())
    codes = {problem.code for problem in result.problems}
    assert "docx_comment_range_unclosed" in codes
    assert "docx_comment_unanchored" in codes

    # And the nesting disclosure survives the adapter too, for the document
    # that has one.
    body = (
        "<w:p>"
        '<w:ins w:id="1" w:author="Prof. Lin" w:date="2026-03-02T09:15:00Z">'
        '<w:r><w:t xml:space="preserve">carefully</w:t></w:r>'
        '<w:del w:id="2" w:author="Prof. Lin" w:date="2026-03-02T09:16:00Z">'
        '<w:r><w:delText xml:space="preserve">never</w:delText></w:r>'
        "</w:del>"
        "</w:ins>"
        "</w:p>"
    )
    result = adapter.extract(_docx_bytes(_document(body)))
    assert "docx_nested_revision" in {problem.code for problem in result.problems}


def _fixture(name: str) -> Fixture:
    for fixture in FIXTURES:
        if fixture.name == name:
            return fixture
    raise AssertionError(f"no fixture named {name!r}")


# --------------------------------------------------------------------------- #
# the anchor a deletion holds, and the anchor that is a position
# --------------------------------------------------------------------------- #


def _comments_part(*comments: tuple[str, str]) -> str:
    """The comments part for the given ``(id, text)`` comments."""
    bodies = "".join(
        f'<w:comment w:id="{cid}" w:author="Prof. Lin" w:date="2026-03-02T09:30:00Z">'
        f'<w:p><w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'
        "</w:comment>"
        for cid, text in comments
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:comments xmlns:w="{W}">{bodies}</w:comments>'
    )


def _comment_by_id(document: RevisionDocument, comment_id: str) -> CommentEvent:
    for comment in document.comments:
        if comment.comment_id == comment_id:
            return comment
    raise AssertionError(f"the document holds no comment {comment_id!r}")


def test_a_comment_whose_markers_sit_inside_a_deletion_anchors_the_deleted_words() -> None:
    """A comment Word wrapped in the deletion of the words it covers.

    When a commented-upon span is later deleted, Word moves the comment's
    range markers *inside* the ``w:del`` element, around the deleted runs.
    The deleted text **is baseline text** -- the rejected view is the
    manuscript as it read before the change -- so the anchor is the span
    the words occupy, and the words themselves. A walk that entered a
    top-level revision at the offset past its whole width recorded both
    markers at that one point, sliced the empty string, and hashed it
    into an integrity value: the pilot's three ``resolved`` rows with no
    anchored text were exactly this shape, and the file held 66, 66 and
    10 baseline characters the reader dropped.

    **What breaks it:** reverting the walk to enter a revision at its
    end offset. Every marker inside then collapses onto one point, the
    anchor covers no words, and this test fails on the text.
    """
    lead, deleted, tail = "Lead in. ", "removed span", " Tail."
    body = (
        "<w:p>"
        f'<w:r><w:t xml:space="preserve">{lead}</w:t></w:r>'
        '<w:del w:id="900" w:author="Prof. Lin" w:date="2026-03-02T09:30:00Z">'
        '<w:commentRangeStart w:id="7"/>'
        f'<w:r><w:delText xml:space="preserve">{deleted}</w:delText></w:r>'
        '<w:commentRangeEnd w:id="7"/>'
        '<w:r><w:commentReference w:id="7"/></w:r>'
        "</w:del>"
        '<w:commentRangeStart w:id="8"/>'
        f'<w:r><w:t xml:space="preserve">{tail}</w:t></w:r>'
        '<w:commentRangeEnd w:id="8"/>'
        '<w:r><w:commentReference w:id="8"/></w:r>'
        "</w:p>"
    )
    document = read_document(
        _docx_bytes(
            _document(body),
            _comments_part(("7", "Reword this."), ("8", "The tail needs a comma.")),
        )
    )
    assert not document.problems, [problem.code for problem in document.problems]

    covered = _comment_by_id(document, "7")
    anchor = covered.anchor
    assert anchor.status == "resolved", (anchor.status, anchor.reason)
    assert anchor.paragraph == 0
    assert anchor.start == len(lead), (anchor.start, anchor.end)
    assert anchor.end == len(lead) + len(deleted)
    assert anchor.text == deleted
    assert document.baseline_paragraphs[0][anchor.start : anchor.end] == deleted, (
        "the anchored text is the text at the offsets the anchor names"
    )

    # The deletion's own span is the whole width it removes, unchanged:
    # the walk counts the deletion's text once, at the top level, and the
    # markers inside it are positioned within that span.
    (revision,) = [r for r in document.revisions if r.kind == "del"]
    assert (revision.baseline_start, revision.baseline_end) == (
        len(lead),
        len(lead) + len(deleted),
    ), "the deletion's own span moved"

    # And the good path is not collateral: the comment anchored on the
    # tail run still resolves to the words it covers, cut from the same
    # baseline the offsets are into.
    tail_comment = _comment_by_id(document, "8")
    assert tail_comment.anchor.status == "resolved"
    assert tail_comment.anchor.text == tail
    assert tail_comment.anchor.start == len(lead) + len(deleted)


def test_a_range_that_closes_where_it_opens_is_a_position_not_a_passage() -> None:
    """A reviewer commenting on the place, not on words.

    Word writes a comment whose range closes where it opens when the
    reviewer comments at a point. The pre-fix reader reported that as
    ``resolved`` with the empty string as the covered text -- the claim
    nothing backs, stored on every zero-width row of the pilot. **The
    position is still a place the reader found**, so the paragraph is
    kept and the comment is reported with its body; what is not reported
    is a passage.
    """
    lead = "Lead in. "
    body = (
        "<w:p>"
        f'<w:r><w:t xml:space="preserve">{lead}</w:t></w:r>'
        '<w:commentRangeStart w:id="8"/>'
        '<w:commentRangeEnd w:id="8"/>'
        '<w:r><w:commentReference w:id="8"/></w:r>'
        '<w:r><w:t xml:space="preserve">Tail.</w:t></w:r>'
        "</w:p>"
    )
    document = read_document(_docx_bytes(_document(body), _comments_part(("8", "Tighten here."))))
    assert {problem.code for problem in document.problems} == {"docx_comment_position_anchor"}, (
        "the position is disclosed, not passed in silence"
    )
    (comment,) = document.comments
    anchor = comment.anchor
    assert anchor.status == "unknown"
    assert anchor.reason == "the comment's range is a position, not a passage of text"
    assert anchor.paragraph == 0, "the place the reader found is kept"
    assert anchor.start is None
    assert anchor.end is None
    assert anchor.text == ""


def test_a_comment_over_inserted_text_is_a_position_in_the_baseline() -> None:
    """A comment covering words the revisions added, seen from the baseline.

    The anchor's coordinates are the baseline's, and **inserted text is
    not in the baseline** -- so a comment whose markers sit inside an
    insertion covers a position there, whatever words the accepted view
    shows. The pre-fix reader reported that position as ``resolved`` over
    the empty string; the pilot's over-insertion rows were this shape,
    eleven of the sixteen.
    """
    body = (
        "<w:p>"
        '<w:r><w:t xml:space="preserve">Lead in. </w:t></w:r>'
        '<w:ins w:id="910" w:author="Prof. Lin" w:date="2026-03-02T09:30:00Z">'
        '<w:commentRangeStart w:id="9"/>'
        '<w:r><w:t xml:space="preserve">inserted words</w:t></w:r>'
        '<w:commentRangeEnd w:id="9"/>'
        '<w:r><w:commentReference w:id="9"/></w:r>'
        "</w:ins>"
        "</w:p>"
    )
    document = read_document(
        _docx_bytes(_document(body), _comments_part(("9", "Check this addition.")))
    )
    (comment,) = document.comments
    anchor = comment.anchor
    assert anchor.status == "unknown"
    assert anchor.reason == "the comment's range is a position, not a passage of text"
    assert anchor.paragraph == 0
    assert anchor.start is None
    assert anchor.end is None
    assert anchor.text == ""
    # The comment itself is not lost: its body, author and date are the
    # file's, and they are reported with the position.
    assert comment.text == "Check this addition."
    assert comment.author == "Prof. Lin"
