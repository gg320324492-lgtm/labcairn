"""The substitute set is checked against the bytes it wrote, before anything trusts it.

**Why this file exists.** `LC-P3-02` measures a rewrite by comparing what came
back, and every one of those comparisons is worth exactly what the corpus is
worth. A sample that did not really carry an equation makes "the equation
survived" a sentence about nothing; a sample that carried one while saying it
did not makes a real loss invisible. So the corpus is checked here against the
file it produced, read with `zipfile` and ElementTree -- deliberately **not**
with the seam's own survey. A gold verified by the same code that will be
measured against it is a second copy of the same mistake, and
``tests/test_docx_fixture_corpus.py`` states that rule for the Phase 2 corpus.

**Why this file declares no marker.** It watches the repository's own material
rather than a protocol behaviour. The evaluation harness treats a
repository-class file that declares a protocol marker as a contradiction, so
the partition row here is the repository class and the file says nothing about
markers.

**What each test would catch.**

| Test | The mistake it catches |
|---|---|
| the written XML carries the declared classes | markup that does not say what the sentence says |
| the ticket's classes are carried outside the edit | a set that quietly omits one of them |
| two writes give the same bytes | a corpus whose hashes move between runs |
| the parts a docx needs are there | a sample a host would reject for unrelated reasons |
| every referenced relationship is declared | a dangling id no region test would see |
| the comment marks have comment bodies | a claim about a comment never anchored |
| the AlternateContent branches agree | a straw-man refusal against a file no host writes |
| the hostile inputs are hostile | a refusal branch reached by nothing |
| the reasons are reached and documented | a refusal nobody raises; a raise nobody tells |
"""

from __future__ import annotations

import hashlib
import io
import re
import xml.etree.ElementTree as ElementTree
import zipfile
from typing import Final

import pytest

from labcairn.editing.drafts import REFUSALS
from labcairn.editing.samples import REFUSED, SAMPLES, WRITABLE, Sample, sample_bytes
from labcairn.editing.survey import StructureClass

# An independent statement of what evidences each class, keyed on the element
# names the format declares. It is written out here rather than imported from
# labcairn.editing.survey for the reason in this file's heading: the corpus
# must not be verified by the machinery it is about to constrain.
W: Final[str] = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M: Final[str] = "http://schemas.openxmlformats.org/officeDocument/2006/math"
VML: Final[str] = "urn:schemas-microsoft-com:vml"
WPS: Final[str] = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
MC: Final[str] = "http://schemas.openxmlformats.org/markup-compatibility/2006"

EVIDENCE: Final[dict[str, frozenset[str]]] = {
    "body-text": frozenset({f"{{{W}}}t", f"{{{W}}}r"}),
    "tracked-revisions": frozenset(
        {f"{{{W}}}ins", f"{{{W}}}del", f"{{{W}}}moveFrom", f"{{{W}}}moveTo"}
    ),
    "comments": frozenset(
        {f"{{{W}}}commentRangeStart", f"{{{W}}}commentRangeEnd", f"{{{W}}}commentReference"}
    ),
    "comment-part": frozenset({f"{{{W}}}comment"}),
    "tables": frozenset({f"{{{W}}}tbl", f"{{{W}}}tr", f"{{{W}}}tc"}),
    "equations": frozenset({f"{{{M}}}oMath", f"{{{M}}}oMathPara"}),
    "images": frozenset({f"{{{W}}}drawing", f"{{{W}}}object", f"{{{VML}}}imagedata"}),
    "text-boxes": frozenset({f"{{{W}}}txbxContent", f"{{{WPS}}}wsp", f"{{{MC}}}AlternateContent"}),
    "fields": frozenset({f"{{{W}}}fldSimple", f"{{{W}}}fldChar", f"{{{W}}}instrText"}),
    "content-controls": frozenset({f"{{{W}}}sdt", f"{{{W}}}sdtContent", f"{{{W}}}sdtPr"}),
    "hyperlinks": frozenset({f"{{{W}}}hyperlink"}),
    "media": frozenset(),
    "vba": frozenset(),
    "embedded-objects": frozenset(),
    "custom-xml": frozenset(),
    "diagrams": frozenset(),
    "charts": frozenset(),
    "signatures": frozenset(),
}

PART_EVIDENCE: Final[dict[str, re.Pattern[str]]] = {
    "media": re.compile(r"^word/media/"),
    "vba": re.compile(r"^word/vbaProject\.bin$"),
    "embedded-objects": re.compile(r"^word/embeddings/"),
    "custom-xml": re.compile(r"^customXml/"),
    "diagrams": re.compile(r"^word/diagrams/"),
    "charts": re.compile(r"^word/charts/"),
    "signatures": re.compile(r"^signatures/"),
}

#: The classes §5.3 of the work orders names, in the words it names them in.
TICKET_CLASSES: Final[tuple[str, ...]] = (
    "comments",
    "tracked-revisions",
    "tables",
    "equations",
    "images",
)


def _document_of(sample: Sample) -> str:
    """The document part as text. **A `.docx` is a ZIP**: a substring search
    over the package's bytes searches deflated data and finds nothing, which
    is how a test can report that no sample carries a text box."""
    with zipfile.ZipFile(io.BytesIO(sample_bytes(sample))) as archive:
        return archive.read("word/document.xml").decode()


def _classes_in_the_written_file(data: bytes) -> set[str]:
    """The classes this package's bytes evidence, read without the seam."""
    found: set[str] = set()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = [info.filename for info in archive.infolist()]
        for structure, pattern in PART_EVIDENCE.items():
            if any(pattern.match(name) for name in names):
                found.add(structure)
        for name in names:
            if not name.endswith((".xml", ".rels")):
                continue
            try:
                root = ElementTree.fromstring(archive.read(name))
            except ElementTree.ParseError:
                continue
            tags = {element.tag for element in root.iter()}
            for structure, elements in EVIDENCE.items():
                if tags & elements:
                    found.add(structure)
    return found


def test_the_written_xml_carries_the_classes_the_sample_declares() -> None:
    """A sample that does not carry what it claims measures nothing.

    **Both directions.** A declared class missing from the bytes makes a
    preservation claim false. An undeclared class present in the bytes means
    the matrix's row for it was decided by a sample nobody said carried it.
    """
    for sample in SAMPLES:
        if sample.hostile:
            continue
        found = _classes_in_the_written_file(sample_bytes(sample))
        declared = {structure.value for structure in sample.carries}
        assert declared == found, (
            f"{sample.name}: declares {sorted(declared)} but the bytes carry "
            f"{sorted(found)}; missing {sorted(declared - found)}, "
            f"undeclared {sorted(found - declared)}"
        )


def test_the_classes_the_ticket_names_are_carried_where_the_edit_does_not_go() -> None:
    """§5.3 names five, and only a written sample can answer whether they survive.

    A refusal sample proves the gate. It never proves preservation, because
    the seam produced no file, so a corpus that carried every class only in a
    refused region would leave the preservation column empty while looking
    full.
    """
    carried: set[str] = set()
    for sample in WRITABLE:
        carried |= _classes_in_the_written_file(sample_bytes(sample))
    for structure in TICKET_CLASSES:
        assert structure in carried, (
            f"no sample the seam writes carries {structure!r}, so nothing measures "
            "whether it survives a rewrite aimed elsewhere"
        )


def test_writing_a_sample_twice_gives_the_same_bytes() -> None:
    """A corpus whose bytes move between runs makes every hash in the records false."""
    for sample in SAMPLES:
        digests = {hashlib.sha256(sample_bytes(sample)).hexdigest() for _ in range(2)}
        assert len(digests) == 1, f"{sample.name} is not reproducible: {sorted(digests)}"


def test_the_parts_a_docx_needs_are_all_there() -> None:
    """A sample a host would reject for a reason unrelated to the seam tests nothing."""
    required = {
        "[Content_Types].xml",
        "_rels/.rels",
        "word/_rels/document.xml.rels",
        "word/document.xml",
    }
    for sample in SAMPLES:
        if sample.hostile:
            continue
        with zipfile.ZipFile(io.BytesIO(sample_bytes(sample))) as archive:
            names = set(archive.namelist())
            assert required <= names, f"{sample.name} is missing {sorted(required - names)}"
            content_types = archive.read("[Content_Types].xml").decode()
            document = archive.read("word/document.xml")
            relationships = archive.read("word/_rels/document.xml.rels").decode()
        assert "wordprocessingml.document.main+xml" in content_types, (
            f"{sample.name} declares no content type for its own document part"
        )
        for token in {
            match.decode() for match in re.findall(rb'r:(?:id|embed)="(rId\d+)"', document)
        }:
            assert f'Id="{token}"' in relationships, (
                f"{sample.name} references {token} in the document part and the "
                "relationship part does not declare it"
            )


def test_comments_have_a_body_where_the_mark_says_there_is_one() -> None:
    """A comment marker whose id matches no comment body is damage, not a fixture."""
    for sample in SAMPLES:
        if sample.hostile:
            continue
        with zipfile.ZipFile(io.BytesIO(sample_bytes(sample))) as archive:
            names = set(archive.namelist())
            document = archive.read("word/document.xml")
            marked = {
                match.group(1).decode()
                for match in re.finditer(rb'w:commentRangeStart w:id="(\d+)"', document)
            }
            if not marked:
                continue
            assert "word/comments.xml" in names, (
                f"{sample.name} marks comment ids {sorted(marked)} with no comments part"
            )
            bodies = {
                match.group(1).decode()
                for match in re.finditer(
                    rb'<w:comment w:id="(\d+)"', archive.read("word/comments.xml")
                )
            }
            assert marked <= bodies, f"{sample.name} marks {sorted(marked - bodies)} with no body"


def test_the_alternate_content_carries_the_same_words_in_both_branches() -> None:
    """The text box the corpus refuses on is a real one, not a straw man.

    **Why this is stated at byte level.** The claim that a rewrite damages an
    AlternateContent pair is only worth making about a document where both
    branches really do carry the same sentence, and the two branches must be
    read from the part rather than guessed at from the sample's declaration.
    The VML figure and the hostile inputs are not AlternateContent pairs, so
    they are not in this set: a test that walked them would fail on bytes that
    are not a ZIP at all, which is a fact about the fixture, not about the seam.
    """
    boxed = [
        sample
        for sample in SAMPLES
        if not sample.hostile and "<mc:AlternateContent" in _document_of(sample)
    ]
    assert boxed, "no sample carries an AlternateContent pair, so the refusal has no case"
    for sample in boxed:
        document = _document_of(sample)
        assert "<mc:Fallback" in document and "<mc:Choice" in document, sample.name
        sentences = re.findall(r"<w:txbxContent>.*?</w:txbxContent>", document, flags=re.S)
        assert len(sentences) >= 2, f"{sample.name} has one branch, so there is no pair to disagree"
        assert sentences.count(sentences[0]) == len(sentences), (
            f"{sample.name}'s branches do not carry the same text: {sentences}"
        )


def test_the_hostile_inputs_really_are_not_packages() -> None:
    """The two hostile inputs must be hostile, or their refusal measures nothing."""
    hostile = [sample for sample in SAMPLES if sample.hostile]
    assert len(hostile) == 2, f"expected two hostile inputs, found {len(hostile)}"
    for sample in hostile:
        data = sample_bytes(sample)
        if sample.hostile == "not-a-package":
            with pytest.raises(zipfile.BadZipFile):
                zipfile.ZipFile(io.BytesIO(data))
            continue
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            assert "word/document.xml" not in archive.namelist(), (
                f"{sample.name} claims to have no document part and has one"
            )


def test_every_documented_refusal_reason_is_reached_by_a_sample() -> None:
    """A described refusal nobody raises, and a raised refusal nobody describes.

    **Both directions, because the two failures are different.** A sample
    naming a reason the seam never gives measures a gate that does not exist.
    A reason the seam can give that no sample reaches is code no witness has
    ever made fail.
    """
    declared = {sample.reason for sample in REFUSED if sample.reason}
    assert declared <= set(REFUSALS), (
        f"samples naming undocumented reasons: {sorted(declared - set(REFUSALS))}"
    )
    assert set(REFUSALS) <= declared, (
        f"documented reasons no sample reaches: {sorted(set(REFUSALS) - declared)}"
    )


def test_the_authors_are_the_two_invented_reviewers_and_the_product() -> None:
    """Public-boundary hygiene, applied to the corpus rather than to a diff."""
    allowed = {"Prof. Lin", "Dr. Zhao", "LabCairn"}
    for sample in SAMPLES:
        if sample.hostile:
            continue
        with zipfile.ZipFile(io.BytesIO(sample_bytes(sample))) as archive:
            names = [n for n in archive.namelist() if n.endswith(".xml")]
            blobs = [archive.read(name).decode() for name in names]
        authors = {match for blob in blobs for match in re.findall(r'w:author="([^"]+)"', blob)}
        assert authors <= allowed, f"{sample.name} carries authorship {sorted(authors - allowed)}"
        text = " ".join(blobs)
        assert not re.search(r"[\u3400-\u9fff]{5,}", text), (
            f"{sample.name} carries a Chinese run of five or more characters; the "
            "corpus is synthetic English and the CJK ceiling watches new files"
        )


def test_the_samples_are_short_and_say_why_they_exist() -> None:
    """§5.1 asks for short samples; §5.7 asks for a decision, not a corpus project."""
    for sample in SAMPLES:
        data = sample_bytes(sample)
        assert len(data) < 4096, f"{sample.name} is {len(data)} bytes; this is an experiment"
        assert len(sample.purpose) > 24, f"{sample.name} does not say why it exists"
        assert len(sample.name) <= 52, f"{sample.name} is too long to keep a visible path short"


def test_the_sample_names_are_unique_and_the_two_halves_do_not_interleave() -> None:
    """Names are row ids: unique, and the halves must not sort together.

    A duplicate name would make an artifact and a row id point at two
    documents at once. The ordering is not cosmetics: the support matrix
    prints the samples the seam wrote and then the samples it refused, and a
    corpus whose names did not sort that way would have the record and the
    corpus disagree about which half a row belongs to.
    """
    names = [sample.name for sample in SAMPLES]
    assert len(names) == len(set(names)), f"duplicate sample names: {names}"
    written = sorted(sample.name for sample in WRITABLE)
    refused = sorted(sample.name for sample in REFUSED)
    assert [sample.name for sample in WRITABLE] == written, (
        "the written half must be named in order"
    )
    assert [sample.name for sample in REFUSED] == refused, "the refused half must be named in order"
    assert max(written) < min(refused), "no refusal sample may sort in among the written ones"


def test_a_sample_is_its_own_edit_target() -> None:
    """The edit each sample is handed names text that sample really holds.

    **Why this is not obvious.** A sample whose ``old_text`` had drifted from
    its body would be refused for ``text_not_located``, and a refusal sample
    would then be measuring the wrong thing while a written sample would have
    been edited into a different paragraph. Both halves of the matrix depend
    on the named passage being in the named paragraph.
    """
    for sample in SAMPLES:
        if sample.hostile or not sample.written:
            continue
        assert sample.edit.old_text in sample.body, (
            f"{sample.name}: the edit names text the body does not hold"
        )
        assert sample.edit.new_text != sample.edit.old_text, f"{sample.name}: a no-op edit"


def test_the_refusal_samples_name_the_class_or_the_gate_they_refuse_on() -> None:
    """Every refusal row in the matrix is decided by a sample that says which gate."""
    gates = {
        "target_inside_unsupported_structure",
        "package_outside_support_matrix",
        "part_outside_support_matrix",
        "text_ambiguous",
        "text_not_located",
        "paragraph_absent",
        "paragraph_holds_no_plain_run",
        "package_unreadable",
        "edit_changes_nothing",
        "date_not_iso_8601",
    }
    reasons = {sample.reason for sample in REFUSED}
    assert reasons <= gates, f"reasons outside the gate vocabulary: {sorted(reasons - gates)}"
    for sample in REFUSED:
        if sample.reason == "target_inside_unsupported_structure":
            assert sample.focus is not None, (
                f"{sample.name}: a structure refusal with no structure named"
            )
            assert sample.focus in StructureClass, (
                f"{sample.name}: {sample.focus!r} is not a structure class"
            )
        elif sample.focus is not None:
            assert sample.focus in StructureClass, (
                f"{sample.name}: {sample.focus!r} is not a structure class"
            )
