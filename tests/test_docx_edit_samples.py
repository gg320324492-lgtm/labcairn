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
| every anchor carries docPr and a real extent | a file Word refuses (D-4) or cannot show (D-3) |
| anchor docPr ids are distinct per document | two drawings minting one id |
| sample 08's image declaration is carried | a declared class the package does not hold |
"""

from __future__ import annotations

import hashlib
import io
import re
import xml.etree.ElementTree as ElementTree
import zipfile
import zlib
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


WP: Final[str] = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A_NS: Final[str] = "http://schemas.openxmlformats.org/drawingml/2006/main"

# CT_Anchor's children, in the order ECMA-376 Part 1 §20.4.2.1 puts them.
# The wrap element is a choice of five, exactly one of which must be
# present; the rest are required exactly once, except the two marked
# optional below.
ANCHOR_ORDER: Final[tuple[str, ...]] = (
    f"{{{WP}}}simplePos",
    f"{{{WP}}}positionH",
    f"{{{WP}}}positionV",
    f"{{{WP}}}extent",
    f"{{{WP}}}effectExtent",
    f"{{{WP}}}wrapNone",
    f"{{{WP}}}wrapSquare",
    f"{{{WP}}}wrapTight",
    f"{{{WP}}}wrapThrough",
    f"{{{WP}}}wrapTopAndBottom",
    f"{{{WP}}}docPr",
    f"{{{WP}}}cNvGraphicFramePr",
    f"{{{A_NS}}}graphic",
)
ANCHOR_REQUIRED: Final[tuple[str, ...]] = (
    f"{{{WP}}}simplePos",
    f"{{{WP}}}positionH",
    f"{{{WP}}}positionV",
    f"{{{WP}}}extent",
    f"{{{WP}}}docPr",
    f"{{{A_NS}}}graphic",
)
ANCHOR_OPTIONAL: Final[tuple[str, ...]] = (
    f"{{{WP}}}effectExtent",
    f"{{{WP}}}cNvGraphicFramePr",
)
ANCHOR_WRAPS: Final[tuple[str, ...]] = (
    f"{{{WP}}}wrapNone",
    f"{{{WP}}}wrapSquare",
    f"{{{WP}}}wrapTight",
    f"{{{WP}}}wrapThrough",
    f"{{{WP}}}wrapTopAndBottom",
)

# CT_Anchor's attributes that the schema marks ``use="required"``. The
# anchor the corpus used to write carried none of them at all.
ANCHOR_REQUIRED_ATTRIBUTES: Final[tuple[str, ...]] = (
    "relativeHeight",
    "behindDoc",
    "locked",
    "layoutInCell",
    "allowOverlap",
)


def _anchor_schema_problems(anchor: ElementTree.Element) -> list[str]:
    """What one anchor gets wrong, in words.

    **Written out rather than imported.** The corpus must not be checked by
    the machinery it constrains, and there is no schema validator here: the
    rules below are the ones ECMA-376 Part 1 §20.4.2.1 states for
    ``CT_Anchor``, spelled out so that a change in the generator that breaks
    them is caught here and not by a host.
    """
    children = [child.tag for child in anchor]
    problems: list[str] = []
    for required in ANCHOR_REQUIRED:
        count = children.count(required)
        if count == 0:
            problems.append(f"no {_local(required)}")
        elif count > 1:
            problems.append(f"{_local(required)} appears {count} times")
    for optional in ANCHOR_OPTIONAL:
        if children.count(optional) > 1:
            problems.append(f"{_local(optional)} appears more than once")
    wraps = [tag for tag in children if tag in ANCHOR_WRAPS]
    if len(wraps) != 1:
        problems.append(f"{len(wraps)} wrap elements, where exactly one of the five is required")
    present = [tag for tag in children if tag in ANCHOR_ORDER]
    if present != sorted(present, key=ANCHOR_ORDER.index):
        problems.append(
            "the children are out of the schema's order: "
            + ", ".join(_local(tag) for tag in present)
        )
    for attribute in ANCHOR_REQUIRED_ATTRIBUTES:
        if anchor.get(attribute) is None:
            problems.append(f"no {attribute} attribute")
    return problems


def _local(tag: str) -> str:
    """The element's own name, without the namespace."""
    return tag.rsplit("}", 1)[-1]


def test_every_anchored_drawing_carries_its_required_children() -> None:
    """An anchor missing a required child is a file Word refuses, not a fixture.

    **What this witnesses.** ECMA-376's ``CT_Anchor`` requires a ``wp:docPr``
    child, and the ``wps:wsp`` inside a text box requires a ``wps:spPr``
    child ahead of ``wps:txbx``. The 44-row ledger's D-4 finding is Word 2019
    refusing sample 08 outright with both missing; WPS opened the same file,
    so only a host as strict as Word catches it. A second drawing in one
    document must mint a second ``wp:docPr`` id, so the ids are asserted
    unique per document. The extent must be a readable size: the 1x1-EMU box
    the first version wrote is the ledger's D-3 finding, a caption no host
    can show.

    **And the anchor needs a position and a wrap.** ``CT_Anchor`` also
    requires ``wp:simplePos``, ``wp:positionH``, ``wp:positionV`` and
    exactly one of the five wrap elements, and it marks five attributes
    ``use="required"``: ``relativeHeight``, ``behindDoc``, ``locked``,
    ``layoutInCell`` and ``allowOverlap``. The corpus's anchor carried
    **none** of the five attributes and three of the six children.

    **What that cost, measured on 2026-11-19.** WPS 12.1.0.29690 opened
    sample 08 and drew the body text and the picture but not the caption,
    and Word 2019 16.0.17932.21140 refused the file outright with its
    severe-open-error dialog. The earlier witness checked ``wp:docPr``
    and the extent and said nothing about the position, the wrap or the
    attributes, so the defect survived every fix that came after it --
    including the one that restored the children and was still refused.
    """
    anchors = 0
    for sample in SAMPLES:
        if sample.hostile:
            continue
        document = _document_of(sample)
        root = ElementTree.fromstring(document)
        for anchor in root.iter(f"{{{WP}}}anchor"):
            anchors += 1
            children = [child.tag for child in anchor]
            assert f"{{{WP}}}docPr" in children, (
                f"{sample.name} has a wp:anchor without wp:docPr, which Word 2019 "
                "refuses the file over (the ledger's D-4 finding)"
            )
            extent = anchor.find(f"{{{WP}}}extent")
            assert extent is not None, f"{sample.name} has a wp:anchor without wp:extent"
            cx, cy = int(extent.get("cx", "0")), int(extent.get("cy", "0"))
            assert (cx, cy) != (1, 1) and cx > 0 and cy > 0, (
                f"{sample.name} has a {cx}x{cy}-EMU anchored drawing, which no host "
                "can show (the ledger's D-3 finding)"
            )
            problems = _anchor_schema_problems(anchor)
            assert not problems, (
                f"{sample.name} has a wp:anchor that CT_Anchor does not admit: "
                + "; ".join(problems)
                + ". Word 2019 refuses such a file outright, and WPS opens it "
                "without drawing the caption (measured 2026-11-19)."
            )
        for shape in root.iter(f"{{{WPS}}}wsp"):
            children = [child.tag for child in shape]
            assert f"{{{WPS}}}spPr" in children, (
                f"{sample.name} has a wps:wsp without wps:spPr, which Word 2019 "
                "refuses the file over (the ledger's D-4 finding)"
            )
            assert children.index(f"{{{WPS}}}spPr") < children.index(f"{{{WPS}}}txbx"), (
                f"{sample.name}'s wps:spPr does not precede wps:txbx, which the "
                "CT_WordprocessingShape sequence requires"
            )
            for required in (f"{{{WPS}}}cNvSpPr", f"{{{WPS}}}bodyPr"):
                assert required in children, (
                    f"{sample.name} has a wps:wsp without {required}, which is "
                    "not the shape Word writes: every real Word text box "
                    "measured on 2026-11-19 carries both"
                )
    assert anchors > 0, "no sample carries an anchored drawing, so nothing witnesses the anchor"


def test_the_markup_compatibility_element_sits_inside_a_run() -> None:
    """Run-level content at paragraph level is a file Word refuses.

    **What this witnesses.** ``w:drawing`` and ``w:pict`` are run-level
    content: they belong in a ``w:r``. ``CT_P`` does not admit them, and
    the corpus's text box put the whole ``mc:AlternateContent`` -- both
    branches -- directly into a ``w:p``.

    **What that cost, measured on 2026-11-19.** Word 2019
    16.0.17932.21140 refused the ``08`` family's artifacts outright. The
    twenty-two other artifacts of the rerun -- the ones the 44-row ledger
    records as opened, or as PRESENCE-LOSS rather than
    REFUSAL-RECORDED -- carry no anchored drawing at all, and none of them
    has run-level content outside a run.

    **How the rule is read.** A consumer performs the
    markup-compatibility preprocessing before the content model applies: it
    replaces the ``mc:AlternateContent`` with the content of the branch it
    understands, and that content has to be legal where the element stood.
    So the drawing's place is decided by where the ``mc:AlternateContent``
    sits, and the rule is stated on the ``mc:AlternateContent``.
    """
    for sample in SAMPLES:
        if sample.hostile:
            continue
        root = ElementTree.fromstring(_document_of(sample))
        parents: dict[ElementTree.Element, ElementTree.Element] = {}
        for parent in root.iter():
            for child in parent:
                parents[child] = parent
        for element in root.iter(f"{{{MC}}}AlternateContent"):
            holder = parents.get(element)
            assert holder is not None and holder.tag == f"{{{W}}}r", (
                f"{sample.name} has an mc:AlternateContent that is not inside a "
                "w:r; its branches carry w:drawing and w:pict, which are "
                "run-level content that CT_P does not admit"
            )
        for tag in (f"{{{W}}}drawing", f"{{{W}}}pict"):
            for element in root.iter(tag):
                ancestor = parents.get(element)
                while ancestor is not None and ancestor.tag in (
                    f"{{{MC}}}Choice",
                    f"{{{MC}}}Fallback",
                    f"{{{MC}}}AlternateContent",
                ):
                    ancestor = parents.get(ancestor)
                assert ancestor is not None and ancestor.tag == f"{{{W}}}r", (
                    f"{sample.name} has a {tag} that is not inside a w:r, which "
                    "the WordprocessingML content model does not admit"
                )


def test_every_anchored_drawing_mints_distinct_docpr_ids() -> None:
    """Two drawings sharing one ``wp:docPr`` id is a conflict Word reports.

    Sample 08 carries both the text box's anchored drawing and an inline
    picture, and each names its own ``wp:docPr``; the ids are asserted
    distinct within one document part.
    """
    for sample in SAMPLES:
        if sample.hostile:
            continue
        root = ElementTree.fromstring(_document_of(sample))
        ids = [int(element.get("id", "0")) for element in root.iter(f"{{{WP}}}docPr")]
        assert len(ids) == len(set(ids)), (
            f"{sample.name} mints the same wp:docPr id twice: {sorted(ids)}"
        )


def test_sample_08_declares_the_image_its_carries_claim_names() -> None:
    """A declared class the package does not carry makes the ledger row fiction.

    **The mismatch this witnesses.** Sample 08's first version declared the
    image class while carrying no media part, no picture relationship and no
    drawing — the ledger's D-3 follow-on finding. The declaration and the
    bytes must agree in both directions: the media part and the image
    relationship exist, the relationship target names the part, and every
    ``r:embed`` the body mentions is that relationship.
    """
    sample = next(item for item in SAMPLES if item.name.startswith("08-refusals"))
    assert StructureClass.IMAGES in sample.carries and StructureClass.MEDIA in sample.carries
    with zipfile.ZipFile(io.BytesIO(sample_bytes(sample))) as archive:
        names = archive.namelist()
        media_parts = [name for name in names if name.startswith("word/media/")]
        relationships = archive.read("word/_rels/document.xml.rels").decode()
        document = archive.read("word/document.xml")
    assert media_parts, f"{sample.name} declares images and carries no media part"
    embeds = {match.decode() for match in re.findall(rb'r:embed="(rId\d+)"', document)}
    declared = {
        match.group(1)
        for match in re.finditer(r'Id="(rId\d+)"[^>]*relationships/image"', relationships)
    }
    assert embeds == declared and declared, (
        f"{sample.name}'s picture references {sorted(embeds)} and its relationships "
        f"declare {sorted(declared)}"
    )
    for rid in declared:
        target = re.search(rf'Id="{rid}"[^>]*Target="([^"]+)"', relationships)
        assert target is not None, f"{sample.name} declares {rid} with no target"
        assert f"word/{target.group(1)}" in names, (
            f"{sample.name}'s {rid} targets {target.group(1)} and no such part exists"
        )


def test_media_png_chunks_carry_correct_checksums() -> None:
    """The corpus's own image is decodable, or the images row is a self-inflicted loss.

    **Why this is a byte-level witness.** The previous value of the media part
    carried an IDAT chunk whose CRC field was ``0x00000000`` and a stream that
    was four bytes short, so neither host decoded it and eight support-matrix
    rows recorded a presence loss that was the corpus's defect, not the seam's.
    A test that only asks whether the part is present would have stayed green
    through all of that, so this one reads the chunk structure the PNG
    specification defines -- length, type, data, CRC -- and checks each
    against :func:`zlib.crc32`, independently of any image library.

    **Every sample that writes the part, refused ones included.** A refusal
    sample still ships the media part; a host that opens it before the seam
    refuses would hit the same broken bytes.
    """
    for sample in SAMPLES:
        if not sample.media or sample.hostile:
            continue
        with zipfile.ZipFile(io.BytesIO(sample_bytes(sample))) as archive:
            png = archive.read("word/media/image1.png")
        assert png.startswith(b"\x89PNG\r\n\x1a\n"), (
            f"{sample.name}: word/media/image1.png does not start with the PNG signature"
        )
        offset = 8
        seen_idat = False
        while offset < len(png):
            if offset + 8 > len(png):
                pytest.fail(
                    f"{sample.name}: word/media/image1.png ends inside the header of "
                    f"the chunk at byte {offset}"
                )
            length = int.from_bytes(png[offset : offset + 4], "big")
            end = offset + 12 + length
            if end > len(png):
                pytest.fail(
                    f"{sample.name}: the chunk at byte {offset} declares "
                    f"{length} data bytes but only {len(png) - offset - 8} remain in the part"
                )
            chunk_type = png[offset + 4 : offset + 8]
            chunk_data = png[offset + 8 : offset + 8 + length]
            stored = int.from_bytes(png[offset + 8 + length : end], "big")
            computed = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
            assert stored == computed, (
                f"{sample.name}: the {chunk_type!r} chunk at byte {offset} stores "
                f"crc32 {stored:08x} but its type and data hash to {computed:08x}"
            )
            if chunk_type == b"IDAT":
                seen_idat = True
                try:
                    zlib.decompress(chunk_data)
                except zlib.error as error:
                    pytest.fail(
                        f"{sample.name}: the IDAT chunk at byte {offset} does not inflate: {error}"
                    )
            if chunk_type == b"IHDR":
                width = int.from_bytes(chunk_data[0:4], "big")
                height = int.from_bytes(chunk_data[4:8], "big")
                colour = chunk_data[9]
                assert (width, height) == (1, 1), (
                    f"{sample.name}: the IHDR chunk declares {width}x{height}, "
                    "not the one-pixel image the corpus documents"
                )
                assert colour == 6, (
                    f"{sample.name}: the IHDR chunk declares colour type {colour}, not RGBA (6)"
                )
            offset = end
        assert seen_idat, f"{sample.name}: word/media/image1.png carries no IDAT chunk"


def test_media_png_pixel_is_not_transparent() -> None:
    """A transparent pixel is not a picture; the part being in the package is not the show.

    **Why this is a witness of its own.** The chunk witness above asks whether
    the media part is *well formed*; this one asks whether it is *visible*.
    Those are two claims, and the value the chunk witness accepted was a
    well-formed PNG whose one pixel was ``RGBA(0, 0, 0, 0)`` -- fully
    transparent. The document draws that image one centimetre square, so on
    white paper the picture is not there at all: the package held a part, no
    host drew anything, and the eight support-matrix rows whose ``images``
    column is ``yes`` could never record a pass. A CRC says the bytes were
    not corrupted; only the pixel says there is something to see.

    **The pixel is read from the inflated IDAT, not from the constant.** The
    claim is about what a host would decode, so it is taken from the bytes a
    host decodes: the IDAT stream is inflated, its first byte is the
    per-scanline filter and the four after it are the RGBA sample.
    """
    for sample in SAMPLES:
        if not sample.media or sample.hostile:
            continue
        with zipfile.ZipFile(io.BytesIO(sample_bytes(sample))) as archive:
            png = archive.read("word/media/image1.png")
        idat = b""
        offset = 8
        while offset < len(png):
            length = int.from_bytes(png[offset : offset + 4], "big")
            chunk_type = png[offset + 4 : offset + 8]
            if chunk_type == b"IDAT":
                idat += png[offset + 8 : offset + 8 + length]
            offset = offset + 12 + length
        assert idat, f"{sample.name}: word/media/image1.png carries no IDAT chunk"
        raw = zlib.decompress(idat)
        assert len(raw) >= 5, (
            f"{sample.name}: the IDAT stream inflates to {len(raw)} bytes, too few for "
            "one RGBA pixel behind its filter byte"
        )
        assert raw[0] == 0, (
            f"{sample.name}: the IDAT stream's filter byte is {raw[0]}, not the 0 this "
            "witness reads the pixel behind"
        )
        red, green, blue, alpha = raw[1], raw[2], raw[3], raw[4]
        assert alpha == 255, (
            f"{sample.name}: the media pixel is RGBA({red}, {green}, {blue}, {alpha}) -- "
            f"alpha is {alpha}, not 255; a transparent pixel is invisible on paper, so "
            "the images row can never record a pass"
        )
        assert red or green or blue, (
            f"{sample.name}: the media pixel is RGBA({red}, {green}, {blue}, {alpha}) -- "
            "every colour channel is zero, so there is nothing to draw"
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
