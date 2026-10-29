"""The DOCX reader, and the properties it is required to hold.

**What is under test.** LC-P2-07's acceptance, measured against the
synthetic corpus in ``tests/docx_corpus.py``:

* every revision is reported, with its kind, text, author and date;
* every deletion's **text** is recovered -- the deleted text lives in
  ``w:delText``, and a reader that reads ``w:t`` sees an empty run;
* every comment is reported, including the four whose anchor cannot be
  resolved, each with the reason it cannot;
* a missing author or date is ``UNKNOWN`` and never a guess;
* the original bytes are unchanged;
* the two views are the texts ADR-0014 D4 names.

**And three things the corpus cannot reach**, which are tested here
against documents built in this file: a revision **nested inside another
revision**, a part that declares a **DTD**, and a **corrupt archive**.
The corpus's ``KNOWN_GAPS`` says why they are not there.

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
from labcairn.material.ooxml import RevisionDocument, read_document
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
    one when a document holds several. The corpus has 30 revisions across
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
    """Comment recall is 1.0, and the four un-anchorable comments are in it.

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
    an empty string, or that drops it. The corpus's four un-anchorable
    cases are the design's §7 "isolated comment marker" case, and each of
    them has a **body that is in the file** -- dropping it loses a remark
    the advisor actually wrote.
    """
    unanchorable = [
        fixture
        for fixture in FIXTURES
        if any(comment["anchor_status"] == "UNKNOWN" for comment in gold_for(fixture)["comments"])
    ]
    assert len(unanchorable) == 4, "the corpus must hold the four un-anchorable cases"

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
    """The three malformed-anchor cases are told apart.

    A range that starts and never ends, a range that ends and never
    started, and a comment with no range at all are **three different
    defects**. A reader that reports them as one has thrown away the
    distinction between a damaged document and an unusual one.
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
