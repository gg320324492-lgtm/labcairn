"""The substitute set: short synthetic manuscripts the edit seam is measured on.

**Why these are generated and not collected.** `LC-P3-02` §5.9 keeps the real
advisor sample out until the owner supplies it, and a synthetic document is the
only kind that can carry an exact expected answer: the corpus states what each
sample holds, and the corpus's own test reads the written XML back with
`zipfile` and ElementTree and disagrees loudly when the bytes do not say it.
A collected manuscript would tell us what happened, not what should have
happened, and a rewrite that agreed with a real file is not thereby correct.

**Why the XML is written directly.** python-docx cannot create a tracked
change — it has no model for ``w:ins`` or ``w:del`` — which is the same fact
that makes it the wrong library for this ticket's edit, as
``tests/docx_fixtures.py`` found for the read side. So the parts are assembled
as text and zipped, the way the Phase 2 corpus does it, and a sample carries
exactly the markup a host would write and nothing the tooling added.

**What is deliberately *not* claimed.** These are not files Word produced, and
the record does not say they are. ``ADR-0021`` records that the corpus is
synthetic, that §4.9's human reopen checklist is what speaks about hosts, and
that the advisor sample is a named gap. A host's answer about a synthetic file
is a fact about that file; the claim that transfers to a real manuscript is
the claim about *which structures the seam refuses to write into*.

**Byte reproducibility, and the platform trap that makes it.** Every entry
carries a fixed date, ``create_system = 3`` and a fixed order. ``zipfile``
writes ``create_system = 0`` on Windows otherwise, so two writes of one sample
on two platforms hash differently and every sha256 in the support matrix would
belong to whichever machine happened to make it.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from typing import Final

from labcairn.editing.drafts import ApprovedEdit
from labcairn.editing.survey import DOCUMENT_PART, StructureClass

_STAMP: Final[tuple[int, int, int, int, int, int]] = (2026, 3, 2, 9, 45, 0)

W: Final[str] = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M: Final[str] = "http://schemas.openxmlformats.org/officeDocument/2006/math"
R: Final[str] = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
MC: Final[str] = "http://schemas.openxmlformats.org/markup-compatibility/2006"
WP: Final[str] = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A: Final[str] = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC: Final[str] = "http://schemas.openxmlformats.org/drawingml/2006/picture"
WPS: Final[str] = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
V: Final[str] = "urn:schemas-microsoft-com:vml"
OLE_NS: Final[str] = "urn:schemas-microsoft-com:office:office"
W14: Final[str] = "http://schemas.microsoft.com/office/word/2010/wordml"

_XML_HEAD: Final[str] = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'

#: The prefixes every sample declares, ``w14`` included. A document that names
#: a prefix in ``mc:Ignorable`` without declaring it is the defect
#: :func:`labcairn.editing.fidelity.ignorables_missing` looks for, so the
#: corpus must not carry it: a detector that fires on its own inputs measures
#: the corpus, not the rewrite.
_ROOT: Final[str] = (
    f'<w:document xmlns:w="{W}" xmlns:m="{M}" xmlns:r="{R}" xmlns:mc="{MC}"'
    f' xmlns:wp="{WP}" xmlns:a="{A}" xmlns:pic="{PIC}" xmlns:wps="{WPS}"'
    f' xmlns:v="{V}" xmlns:o="{OLE_NS}" xmlns:w14="{W14}" mc:Ignorable="w14">'
)

#: A one-pixel PNG, so the image sample carries bytes a host can decode and a
#: relationship that points at something. Without the part, "the relationship
#: survived" would be a claim about an attribute alone.
_PNG: Final[bytes] = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63600000020001e221bc330000000049454e44ae426082"
)

#: The author the seam stamps and the moment it stamps. Neither is read from a
#: clock: a sample whose bytes move when the hour moves cannot anchor a hash.
AUTHOR: Final[str] = "LabCairn"
WHEN: Final[str] = "2026-11-08T09:00:00Z"

#: The two invented reviewers. No real name appears in this module, and
#: ``tests/test_docx_edit_samples.py`` holds that line.
LIN: Final[str] = "Prof. Lin"
ZHAO: Final[str] = "Dr. Zhao"
DAY_ONE: Final[str] = "2026-03-02T09:45:00Z"
DAY_TWO: Final[str] = "2026-03-03T10:00:00Z"

TARGET: Final[str] = "The baseline sentence stands at the head of the manuscript."
REPLACED: Final[str] = "The baseline sentence was approved and rewritten."
TAIL: Final[str] = "The closing sentence rounds the paragraph set off."
CELL: Final[str] = "The measured sentence sits inside a cell."
BOXED: Final[str] = "The caption inside the text box repeats itself."
BOUND: Final[str] = "The sentence bound to a content control."
SIDE: Final[str] = "The paragraph beside the figure carries the claim."
LINKED: Final[str] = "The cited sentence carries the reference."
AMBIGUOUS: Final[str] = "The same clause appears twice."
CACHED: Final[str] = "3"
INSTRUCTION: Final[str] = "PAGE"


# --------------------------------------------------------------------------- #
# the markup fragments
# --------------------------------------------------------------------------- #


def para(text: str) -> str:
    """One body paragraph carrying exactly one plain run."""
    return f'<w:p><w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'


def paragraph_with_insert(baseline: str, inserted: str, author: str, date: str, ident: str) -> str:
    """A sentence another reviewer has already inserted."""
    return (
        f'<w:p><w:r><w:t xml:space="preserve">{baseline}</w:t></w:r>'
        f'<w:ins w:id="{ident}" w:author="{author}" w:date="{date}">'
        f'<w:r><w:t xml:space="preserve">{inserted}</w:t></w:r></w:ins>'
        "<w:r><w:t>.</w:t></w:r></w:p>"
    )


def paragraph_with_delete(removed: str, author: str, date: str, ident: str, tail: str) -> str:
    """A deletion, whose text lives in ``w:delText`` and nowhere else."""
    return (
        f'<w:p><w:del w:id="{ident}" w:author="{author}" w:date="{date}">'
        f'<w:r><w:delText xml:space="preserve">{removed}</w:delText></w:r></w:del>'
        f'<w:r><w:t xml:space="preserve">{tail}</w:t></w:r></w:p>'
    )


def paragraph_commented(text: str, comment_id: str) -> str:
    """A paragraph whose sentence a reviewer marked, markers around the run."""
    return (
        f'<w:p><w:commentRangeStart w:id="{comment_id}"/>'
        f'<w:r><w:t xml:space="preserve">{text}</w:t></w:r>'
        f'<w:commentRangeEnd w:id="{comment_id}"/>'
        f'<w:r><w:commentReference w:id="{comment_id}"/></w:r></w:p>'
    )


def table(rows: tuple[tuple[str, ...], ...]) -> str:
    """A table whose cells each hold one paragraph."""
    body = "".join(
        "<w:tr>"
        + "".join(
            '<w:tc><w:tcPr><w:tcW w:w="4000" w:type="dxa"/></w:tcPr>'
            f'<w:p><w:r><w:t xml:space="preserve">{cell}</w:t></w:r></w:p></w:tc>'
            for cell in row
        )
        + "</w:tr>"
        for row in rows
    )
    return f'<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/></w:tblPr>{body}</w:tbl>'


def equation(text: str) -> str:
    """A display equation. Its runs are ``m:r``, which the seam cannot locate."""
    return f"<w:p><m:oMathPara><m:oMath><m:r><m:t>{text}</m:t></m:r></m:oMath></m:oMathPara></w:p>"


def image(rid: str, name: str) -> str:
    """An inline picture, reached through a relationship and a media part."""
    return (
        '<w:p><w:r><w:drawing><wp:inline><wp:extent cx="360000" cy="360000"/>'
        f'<wp:docPr id="1" name="{name}"/><a:graphic><a:graphicData uri="{PIC}">'
        f'<pic:pic><pic:nvPicPr><pic:cNvPr id="0" name="{name}"/><pic:cNvPicPr/>'
        f'</pic:nvPicPr><pic:blipFill><a:blip r:embed="{rid}"/><a:stretch>'
        "<a:fillRect/></a:stretch></pic:blipFill><pic:spPr/></pic:pic>"
        "</a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>"
    )


def text_box(text: str) -> str:
    """A text box written as ``mc:Choice`` with a VML ``mc:Fallback``.

    **Both branches carry the same words, and that is the refusal.** A rewrite
    of the modern branch alone leaves a document whose legacy spelling of the
    same caption says something else, and no measurement of "the box survived"
    would see the disagreement.
    """
    inner = para(text)
    return (
        '<w:p><mc:AlternateContent><mc:Choice Requires="wps">'
        '<w:drawing><wp:anchor><wp:extent cx="1" cy="1"/><a:graphic>'
        f'<a:graphicData uri="{WPS}"><wps:wsp><wps:txbx><w:txbxContent>{inner}'
        f"</w:txbxContent></wps:txbx></wps:wsp></a:graphicData></a:graphic></wp:anchor>"
        f'</w:drawing></mc:Choice><mc:Fallback><w:pict><v:shape id="box"><v:textbox>'
        f"<w:txbxContent>{inner}</w:txbxContent></v:textbox></v:shape></w:pict>"
        "</mc:Fallback></mc:AlternateContent></w:p>"
    )


def vml_figure(text: str) -> str:
    """A figure caption written in VML only, the way a 2003-era document spells it.

    **Why this shape is in the set at all.** It is the only realistic way an
    edit gets aimed *at* a figure: the caption's runs live inside
    ``v:shape > v:textbox > w:txbxContent``, so the located run's ancestors
    name the image class and the text-box class. A seam that said "images are
    not editable" without ever having been handed one would be making a claim
    with no measurement under it, which is the defect §3 rule 5 names.
    """
    return (
        '<w:p><w:r><w:pict><v:shape id="fig1" type="#_x0000_t75"'
        ' style="width:9pt;height:9pt"><v:imagedata r:id="rId4" o:title="figure-1"/></v:shape>'
        '<v:shape id="cap1" type="#_x0000_t202"><v:textbox>'
        f"<w:txbxContent>{para(text)}</w:txbxContent></v:textbox></v:shape></w:pict></w:r></w:p>"
    )


def field(instr: str, cached: str) -> str:
    """A field: an instruction, and the answer the host cached when it last ran.

    **The cached answer is not the answer.** Word recomputes the instruction
    when it opens the file or when the user asks, so a rewrite that replaced
    the cached text while leaving ``w:instrText`` alone would put a sentence in
    the manuscript that the manuscript's own instruction overrules.
    """
    return (
        '<w:p><w:r><w:t xml:space="preserve">The page reads </w:t></w:r>'
        '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
        f'<w:r><w:instrText xml:space="preserve"> {instr} </w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
        f'<w:r><w:t xml:space="preserve">{cached}</w:t></w:r>'
        '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
        '<w:r><w:t xml:space="preserve">.</w:t></w:r></w:p>'
    )


def content_control(text: str) -> str:
    """A paragraph wrapped in a bound content control."""
    return (
        '<w:sdt><w:sdtPr><w:alias w:val="Title"/></w:sdtPr><w:sdtContent>'
        + para(text)
        + "</w:sdtContent></w:sdt>"
    )


def embedded_object(rid: str) -> str:
    """An OLE object: a drawing that stands for a part outside the document.

    **The relationship id is lowercase.** ``R:id`` is an undeclared prefix, a
    part with an undeclared prefix does not parse, and a sample that failed to
    parse would be refused for the wrong reason: the refusal would then be
    evidence about the corpus rather than about the seam.
    """
    return (
        '<w:p><w:r><w:object><v:shape id="ole1" type="#_x0000_t75">'
        f'<v:imagedata r:id="{rid}"/></v:shape><o:OLEObject Type="Embed"'
        f' ProgID="Equation.3" r:id="{rid}"/></w:object></w:r></w:p>'
    )


def hyperlink(rid: str, text: str) -> str:
    """A paragraph whose run sits inside an external hyperlink relationship."""
    return (
        f'<w:p><w:hyperlink r:id="{rid}"><w:r><w:rPr><w:b/></w:rPr>'
        f'<w:t xml:space="preserve">{text}</w:t></w:r></w:hyperlink></w:p>'
    )


def split_runs(head: str, tail: str) -> str:
    """One sentence written as two runs, because Word put formatting between them.

    **The case that decides the seam's locating rule.** A reviewer's approved
    change usually names a phrase, and the phrase is often spelled as two runs.
    A seam that replaced the first run's text with the whole new sentence would
    delete the second run's words — damage in the very paragraph the edit named,
    invisible to a region comparison that is told to skip that paragraph.
    """
    return (
        f'<w:p><w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">{head}</w:t></w:r>'
        f'<w:r><w:t xml:space="preserve">{tail}</w:t></w:r></w:p>'
    )


def twice(text: str) -> str:
    """A paragraph carrying one identical plain run twice."""
    run = f'<w:r><w:t xml:space="preserve">{text}</w:t></w:r>'
    return f"<w:p>{run}{run}</w:p>"


def math_holding_plain_run(text: str) -> str:
    """An equation that carries one ordinary run inside its markup.

    **Why this shape is in a synthetic corpus.** Word spells a math run as
    ``m:r``, which the seam cannot locate at all, and documents produced by
    other tools do carry a ``w:r`` inside ``m:oMath``. That is the case the
    refusal column exists for: the seam locates the run and refuses to write
    into the equation, because emitting a run inside an equation is not the act
    the substitute run measured.
    """
    return (
        f"<w:p><m:oMath><m:r><m:t>x=</m:t></m:r>"
        f'<w:r><w:t xml:space="preserve">{text}</w:t></w:r></m:oMath></w:p>'
    )


def wrapped_box(text: str) -> str:
    """A paragraph whose only content is a text box, the way Word writes a caption."""
    inner = text_box(text).removeprefix("<w:p>").removesuffix("</w:p>")
    return f"<w:p>{inner}</w:p>"


def box_beside(sentence: str, boxed: str) -> str:
    """One paragraph carrying a plain sentence and a text box beside it."""
    inner = wrapped_box(boxed).removeprefix("<w:p>").removesuffix("</w:p>")
    return f'<w:p><w:r><w:t xml:space="preserve">{sentence}</w:t></w:r>{inner}</w:p>'


# --------------------------------------------------------------------------- #
# the sample declaration
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Sample:
    """One manuscript, the edit it is handed, and what the seam must do with it.

    ``carries`` is the survey's expected answer, not a wish: the corpus's own
    test reads the written XML with no part of the seam involved and fails when
    the bytes disagree with the sentence here. A sample that does not carry what
    it claims measures nothing.

    ``role`` says which side of a support-matrix row the sample decides. A class
    is **carried** by a sample that holds it outside the edit, and is written or
    refused by the sample that aims a change at it. One word covering both would
    let a refusal read as a loss.
    """

    name: str
    purpose: str
    carries: frozenset[StructureClass]
    body: str
    edit: ApprovedEdit
    written: bool
    reason: str = ""
    focus: StructureClass | None = None
    role: str = "preserve"
    comment_bodies: tuple[tuple[str, str, str, str], ...] = ()
    media: bool = False
    object_rid: str = ""
    hyperlink_rid: str = ""
    macro: bool = False
    custom_xml: bool = False
    #: A signed package. The class is evidenced by the part name, and the
    #: reason it is refused is not a measurement but an arithmetic fact: the
    #: signature is a digest over the parts, and a rewrite changes them.
    signature: bool = False
    #: Two inputs are not manuscripts at all. They are here because a package
    #: the seam cannot read is the one refusal the read side already has a
    #: word for, and the write side must answer with the same word rather than
    #: with a traceback.
    hostile: str = ""


def _edit(paragraph: int, old: str, new: str, part: str = DOCUMENT_PART) -> ApprovedEdit:
    return ApprovedEdit(
        part=part, paragraph=paragraph, old_text=old, new_text=new, author=AUTHOR, date=WHEN
    )


# --------------------------------------------------------------------------- #
# assembling one sample into bytes
# --------------------------------------------------------------------------- #

_DOC_TYPE: Final[str] = "application/vnd.openxmlformats-officedocument.wordprocessingml"


def _content_types(sample: Sample) -> str:
    lines = [
        _XML_HEAD + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-'
        'package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
    ]
    if sample.media:
        lines.append('<Default Extension="png" ContentType="image/png"/>')
    if sample.object_rid or sample.macro or sample.custom_xml:
        lines.append('<Default Extension="bin" ContentType="application/octet-stream"/>')
    if sample.signature:
        lines.append(
            "<Default Extension=\"xml\" ContentType=\"application/vnd.oasis.opendocument.text\"/>"
        )
    lines.append(
        f'<Override PartName="/word/document.xml" ContentType="{_DOC_TYPE}.document.main+xml"/>'
    )
    if sample.comment_bodies:
        lines.append(
            f'<Override PartName="/word/comments.xml" ContentType="{_DOC_TYPE}.comments+xml"/>'
        )
    lines.append(f'<Override PartName="/word/styles.xml" ContentType="{_DOC_TYPE}.styles+xml"/>')
    return "".join(lines) + "</Types>"


def _root_rels() -> str:
    return (
        _XML_HEAD
        + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        'relationships/officeDocument" Target="word/document.xml"/></Relationships>'
    )


def _document_rels(sample: Sample) -> str:
    """The document part's relationships, built from the parts the sample carries.

    **Every ``r:id`` the body mentions is declared here, and the corpus's own
    test holds that to account.** A dangling reference is refused by a host
    before the seam's fidelity is ever visible, and the report would then be
    measuring the fixture.
    """
    entries = [
        (
            "rId1",
            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles",
            "styles.xml",
            "",
        )
    ]
    if sample.comment_bodies:
        entries.append(
            (
                "rId2",
                "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments",
                "comments.xml",
                "",
            )
        )
    if sample.media:
        entries.append(
            (
                "rId4",
                "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
                "media/image1.png",
                "",
            )
        )
    if sample.hyperlink_rid:
        entries.append(
            (
                sample.hyperlink_rid,
                "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
                "https://example.org/reference",
                ' TargetMode="External"',
            )
        )
    if sample.object_rid:
        entries.append(
            (
                sample.object_rid,
                "http://schemas.openxmlformats.org/officeDocument/2006/relationships/oleObject",
                "embeddings/ole1.bin",
                "",
            )
        )
    body = "".join(
        f'<Relationship Id="{rid}" Type="{kind}" Target="{target}"{mode}/>'
        for rid, kind, target, mode in entries
    )
    return (
        _XML_HEAD
        + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + body
        + "</Relationships>"
    )


def _styles() -> str:
    return (
        _XML_HEAD + f'<w:styles xmlns:w="{W}"><w:style w:type="paragraph" w:styleId="Normal">'
        '<w:name w:val="Normal"/></w:style><w:style w:type="table" w:styleId="TableGrid">'
        '<w:name w:val="Table Grid"/></w:style></w:styles>'
    )


def _comments(sample: Sample) -> str:
    bodies = "".join(
        f'<w:comment w:id="{comment_id}" w:author="{author}" w:date="{date}" '
        f'w:initials="{author[:1]}"><w:p><w:r><w:t xml:space="preserve">{text}</w:t></w:r>'
        "</w:p></w:comment>"
        for comment_id, author, date, text in sample.comment_bodies
    )
    return _XML_HEAD + f'<w:comments xmlns:w="{W}">{bodies}</w:comments>'


def sample_parts(sample: Sample) -> dict[str, bytes]:
    """Every part of one sample, as bytes, in archive order."""
    parts: dict[str, bytes] = {
        "[Content_Types].xml": _content_types(sample).encode(),
        "_rels/.rels": _root_rels().encode(),
        "word/_rels/document.xml.rels": _document_rels(sample).encode(),
        "word/styles.xml": _styles().encode(),
    }
    if sample.comment_bodies:
        parts["word/comments.xml"] = _comments(sample).encode()
    if sample.media:
        parts["word/media/image1.png"] = _PNG
    if sample.object_rid:
        parts["word/embeddings/ole1.bin"] = b"\xd0\xcf\x11\xe0 synthetic ole payload"
    if sample.macro:
        parts["word/vbaProject.bin"] = b"\xd0\xcf\x11\xe0 synthetic macro storage"
    if sample.custom_xml:
        parts["customXml/item1.xml"] = (_XML_HEAD + "<root/>").encode()
        parts["customXml/itemProps1.xml"] = (_XML_HEAD + "<dataObject/>").encode()
    if sample.signature:
        parts["signatures/xmlSignature1.xml"] = (
            _XML_HEAD
            + '<Signature xmlns="http://www.w3.org/2000/09/xmldsig#">'
            "<SignedInfo/></Signature>"
        ).encode()
    parts[DOCUMENT_PART] = (
        _XML_HEAD + _ROOT + f"<w:body>{sample.body}</w:body></w:document>"
    ).encode()
    return parts


def part_names(sample: Sample) -> tuple[str, ...]:
    """The part names in the order they are written — archive order is a claim."""
    return tuple(sample_parts(sample))


#: Bytes that are not a package, so a refusal branch has a case.
_NOT_A_PACKAGE: Final[bytes] = b"this is not a zip archive, and it never was"


def sample_bytes(sample: Sample) -> bytes:
    """One sample as a ``.docx``, byte-reproducible across platforms."""
    if sample.hostile == "not-a-package":
        return _NOT_A_PACKAGE
    if sample.hostile == "no-document-part":
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
            info = zipfile.ZipInfo("[Content_Types].xml", date_time=_STAMP)
            info.create_system = 3
            archive.writestr(info, _content_types(sample).encode())
        return out.getvalue()
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in sample_parts(sample).items():
            info = zipfile.ZipInfo(name, date_time=_STAMP)
            info.compress_type = (
                zipfile.ZIP_STORED if name.endswith((".png", ".bin")) else zipfile.ZIP_DEFLATED
            )
            info.create_system = 3
            info.external_attr = 0o600 << 16
            archive.writestr(info, payload)
    return out.getvalue()


def _sample(
    name: str,
    purpose: str,
    carries: tuple[StructureClass, ...],
    body: str,
    edit: ApprovedEdit,
    *,
    written: bool = True,
    reason: str = "",
    focus: StructureClass | None = None,
    role: str = "preserve",
    comments: tuple[tuple[str, str, str, str], ...] = (),
    media: bool = False,
    object_rid: str = "",
    hyperlink_rid: str = "",
    macro: bool = False,
    custom_xml: bool = False,
    signature: bool = False,
    hostile: str = "",
) -> Sample:
    return Sample(
        name=name,
        purpose=purpose,
        carries=frozenset(carries),
        body=body,
        edit=edit,
        written=written,
        reason=reason,
        focus=focus,
        role=role,
        comment_bodies=comments,
        media=media,
        object_rid=object_rid,
        hyperlink_rid=hyperlink_rid,
        macro=macro,
        custom_xml=custom_xml,
        signature=signature,
        hostile=hostile,
    )


_B: Final = StructureClass


_SAMPLES: Final[tuple[Sample, ...]] = (
    # ---- the half the seam writes: the preservation evidence ----
    _sample(
        "01-mixed-comments-revisions",
        "comments and tracked changes by two authors, with an edit in plain text beside them",
        (_B.BODY_TEXT, _B.COMMENTS, _B.COMMENT_PART, _B.TRACKED_REVISIONS),
        para(TARGET)
        + paragraph_with_insert(
            "Second sentence grows by", " an inserted clause", LIN, DAY_ONE, "11"
        )
        + paragraph_commented("Third sentence is marked.", "7")
        + paragraph_with_delete("removed words", ZHAO, DAY_TWO, "12", " remain here.")
        + para(TAIL),
        _edit(1, TARGET, REPLACED),
        focus=_B.COMMENTS,
        role="preserve",
        comments=(("7", LIN, DAY_ONE, "Why is this sentence here?"),),
    ),
    _sample(
        "01b-commented-sentence-rewritten",
        "an edit landing on the very sentence a reviewer marked, between the range markers",
        (_B.BODY_TEXT, _B.COMMENTS, _B.COMMENT_PART),
        para(TARGET) + paragraph_commented("Third sentence is marked.", "7") + para(TAIL),
        _edit(2, "Third sentence is marked.", "Third sentence is marked, and rewritten."),
        focus=_B.COMMENTS,
        role="editable",
        comments=(("7", LIN, DAY_ONE, "Why is this sentence here?"),),
    ),
    _sample(
        "02-table-outside-the-target",
        "a table whose cells hold text, with the edit in a body paragraph",
        (_B.BODY_TEXT, _B.TABLES),
        para(TARGET) + table(((CELL, "Second cell"), ("Third cell", "Fourth cell"))) + para(TAIL),
        _edit(1, TARGET, REPLACED),
        focus=_B.TABLES,
    ),
    _sample(
        "03-table-target-inside-a-cell",
        "an edit aimed at a sentence inside a table cell",
        (_B.BODY_TEXT, _B.TABLES),
        para(TARGET) + table(((CELL, "Second cell"),)) + para(TAIL),
        _edit(2, CELL, "The measured sentence now sits inside a rewritten cell."),
        focus=_B.TABLES,
        role="editable",
    ),
    _sample(
        "04-equation-outside-the-target",
        "a display equation, with the edit in plain text beside it",
        (_B.BODY_TEXT, _B.EQUATIONS),
        para(TARGET) + equation("E=m c^2") + para(SIDE) + para(TAIL),
        _edit(1, TARGET, REPLACED),
        focus=_B.EQUATIONS,
    ),
    _sample(
        "05-image-and-relationship",
        "an inline picture reached through a relationship and a media part",
        (_B.BODY_TEXT, _B.IMAGES, _B.MEDIA),
        para(TARGET) + image("rId4", "figure-1.png") + para(SIDE) + para(TAIL),
        _edit(1, TARGET, REPLACED),
        focus=_B.IMAGES,
        media=True,
    ),
    _sample(
        "06-hyperlink-and-relationship",
        "an external hyperlink whose relationship the rewrite must carry",
        (_B.BODY_TEXT, _B.HYPERLINKS),
        para(TARGET) + hyperlink("rId5", LINKED) + para(TAIL),
        _edit(1, TARGET, REPLACED),
        focus=_B.HYPERLINKS,
        role="editable",
        hyperlink_rid="rId5",
    ),
    _sample(
        "07-everything-at-once",
        "the composite: comments, revisions, a table, an equation, an image, a link",
        (
            _B.BODY_TEXT,
            _B.COMMENTS,
            _B.COMMENT_PART,
            _B.TRACKED_REVISIONS,
            _B.TABLES,
            _B.EQUATIONS,
            _B.IMAGES,
            _B.HYPERLINKS,
            _B.MEDIA,
        ),
        para(TARGET)
        + paragraph_with_insert(
            "Second sentence grows by", " an inserted clause", LIN, DAY_ONE, "11"
        )
        + paragraph_commented("Third sentence is marked.", "7")
        + table(((CELL, "Second cell"),))
        + equation("a + b = c")
        + image("rId4", "figure-1.png")
        + hyperlink("rId5", LINKED)
        + paragraph_with_delete("removed words", ZHAO, DAY_TWO, "12", " remain here.")
        + para(TAIL),
        _edit(1, TARGET, REPLACED),
        focus=_B.BODY_TEXT,
        role="editable",
        comments=(("7", LIN, DAY_ONE, "Why is this sentence here?"),),
        media=True,
        hyperlink_rid="rId5",
    ),
    _sample(
        "08-refusals-elsewhere-in-the-document",
        "a text box, a field and a content control, none of them where the edit goes",
        (_B.BODY_TEXT, _B.TEXT_BOXES, _B.FIELDS, _B.CONTENT_CONTROLS, _B.IMAGES),
        para(TARGET)
        + box_beside(SIDE, BOXED)
        + field(INSTRUCTION, CACHED)
        + content_control(BOUND),
        _edit(1, TARGET, REPLACED),
    ),
    _sample(
        "09-target-inside-another-reviewers-insertion",
        "an edit aimed at the whole text of a run that sits inside a reviewer's insertion",
        (_B.BODY_TEXT, _B.TRACKED_REVISIONS),
        para(TARGET)
        + paragraph_with_insert(
            "The inserted passage begins here", ", and the edit lands on it", ZHAO, DAY_TWO, "21"
        )
        + para(TAIL),
        _edit(2, ", and the edit lands on it", ", and the seam rewrote it"),
        focus=_B.TRACKED_REVISIONS,
        role="editable",
    ),
    # ---- the half the seam refuses: the gate's evidence ----
    _sample(
        "10-refuse-edit-inside-an-equation",
        "an edit aimed at the one plain run sitting inside a math element",
        (_B.BODY_TEXT, _B.EQUATIONS),
        math_holding_plain_run(CACHED),
        _edit(1, CACHED, "4"),
        written=False,
        reason="target_inside_unsupported_structure",
        focus=_B.EQUATIONS,
        role="refused",
    ),
    _sample(
        "11-refuse-edit-inside-a-text-box",
        "an edit aimed at a caption inside a text box, whose fallback repeats it",
        (_B.BODY_TEXT, _B.TEXT_BOXES, _B.IMAGES),
        para(TARGET) + wrapped_box(BOXED),
        _edit(3, BOXED, "The caption inside the box was rewritten."),
        written=False,
        reason="target_inside_unsupported_structure",
        focus=_B.TEXT_BOXES,
        role="refused",
    ),
    _sample(
        "12-refuse-edit-of-a-fields-cached-answer",
        "an edit aimed at the cached answer of a field, which the instruction overrules",
        (_B.BODY_TEXT, _B.FIELDS),
        para(TARGET) + field(INSTRUCTION, CACHED),
        _edit(2, CACHED, "4"),
        written=False,
        reason="target_inside_unsupported_structure",
        focus=_B.FIELDS,
        role="refused",
    ),
    _sample(
        "12b-refuse-edit-of-a-vml-figure-caption",
        "an edit aimed at a caption whose only home is a VML shape",
        (_B.BODY_TEXT, _B.IMAGES, _B.TEXT_BOXES, _B.MEDIA),
        para(TARGET) + vml_figure(BOXED),
        _edit(3, BOXED, "The figure caption was rewritten."),
        written=False,
        reason="target_inside_unsupported_structure",
        focus=_B.IMAGES,
        role="refused",
        media=True,
    ),
    _sample(
        "13-refuse-edit-inside-a-content-control",
        "an edit aimed at a sentence bound to a content control",
        (_B.BODY_TEXT, _B.CONTENT_CONTROLS),
        para(TARGET) + content_control(BOUND),
        _edit(2, BOUND, "The bound sentence was rewritten."),
        written=False,
        reason="target_inside_unsupported_structure",
        focus=_B.CONTENT_CONTROLS,
        role="refused",
    ),
    _sample(
        "14-refuse-package-carrying-macros",
        "an ordinary body edit in a package that also carries a macro part",
        (_B.BODY_TEXT, _B.VBA),
        para(TARGET) + para(TAIL),
        _edit(1, TARGET, REPLACED),
        written=False,
        reason="package_outside_support_matrix",
        focus=_B.VBA,
        role="refused",
        macro=True,
    ),
    _sample(
        "15-refuse-package-carrying-an-embedded-object",
        "an ordinary body edit in a package that also carries an OLE object",
        (_B.BODY_TEXT, _B.EMBEDDED_OBJECTS, _B.IMAGES),
        para(TARGET) + embedded_object("rId6"),
        _edit(1, TARGET, REPLACED),
        written=False,
        reason="package_outside_support_matrix",
        focus=_B.EMBEDDED_OBJECTS,
        role="refused",
        object_rid="rId6",
    ),
    _sample(
        "16-refuse-package-carrying-custom-xml",
        "an ordinary body edit in a package with a bound customXml item",
        (_B.BODY_TEXT, _B.CUSTOM_XML),
        para(TARGET) + para(TAIL),
        _edit(1, TARGET, REPLACED),
        written=False,
        reason="package_outside_support_matrix",
        focus=_B.CUSTOM_XML,
        role="refused",
        custom_xml=True,
    ),
    _sample(
        "16b-refuse-package-carrying-a-digital-signature",
        "a signed package: rewriting any part invalidates the digest over the whole",
        (_B.BODY_TEXT, _B.SIGNATURES),
        para(TARGET) + para(TAIL),
        _edit(1, TARGET, REPLACED),
        written=False,
        reason="package_outside_support_matrix",
        focus=_B.SIGNATURES,
        role="refused",
        signature=True,
    ),
    _sample(
        "17-refuse-edit-aimed-at-the-comment-part",
        "an edit aimed at a reviewer's own words in word/comments.xml",
        (_B.BODY_TEXT, _B.COMMENTS, _B.COMMENT_PART),
        paragraph_commented("Third sentence is marked.", "7"),
        _edit(1, "Why is this sentence here?", "Answered.", part="word/comments.xml"),
        written=False,
        reason="part_outside_support_matrix",
        focus=_B.COMMENT_PART,
        role="refused",
        comments=(("7", LIN, DAY_ONE, "Why is this sentence here?"),),
    ),
    _sample(
        "18-refuse-ambiguous-occurrence",
        "an edit whose text occurs twice in the located paragraph",
        (_B.BODY_TEXT,),
        twice(AMBIGUOUS),
        _edit(1, AMBIGUOUS, "Rewritten once."),
        written=False,
        reason="text_ambiguous",
        role="refused",
    ),
    _sample(
        "19-refuse-edit-cutting-a-run-in-two",
        "an edit naming half a sentence, where the file wrote it as two runs",
        (_B.BODY_TEXT,),
        split_runs("The sentence that a bold ", "word splits in two."),
        _edit(1, "The sentence that a bold word", "The sentence that an italic word"),
        written=False,
        reason="text_not_located",
        role="refused",
    ),
    _sample(
        "20-refuse-absent-text",
        "an edit whose text is not in the located paragraph at all",
        (_B.BODY_TEXT,),
        para(TARGET) + para(TAIL),
        _edit(1, "A sentence the manuscript does not contain.", REPLACED),
        written=False,
        reason="text_not_located",
        role="refused",
    ),
    _sample(
        "21-refuse-unchanged-edit",
        "an edit whose approved text is the text already there",
        (_B.BODY_TEXT,),
        para(TARGET),
        _edit(1, TARGET, TARGET),
        written=False,
        reason="edit_changes_nothing",
        role="refused",
    ),
    _sample(
        "22-refuse-paragraph-number-that-is-not-there",
        "an edit addressed to a paragraph past the end of the document",
        (_B.BODY_TEXT,),
        para(TARGET),
        _edit(9, TARGET, REPLACED),
        written=False,
        reason="paragraph_absent",
        role="refused",
    ),
    _sample(
        "23-refuse-a-date-that-is-not-a-date",
        "an edit whose revision stamp is not the form the format declares",
        (_B.BODY_TEXT,),
        para(TARGET),
        ApprovedEdit(
            part=DOCUMENT_PART,
            paragraph=1,
            old_text=TARGET,
            new_text=REPLACED,
            author=AUTHOR,
            date="2026-11-08 09:00",
        ),
        written=False,
        reason="date_not_iso_8601",
        role="refused",
    ),
    _sample(
        "24-refuse-a-paragraph-with-no-plain-run",
        "a sentence the host wrote as one run split by a line break",
        (_B.BODY_TEXT,),
        (
            '<w:p><w:r><w:t xml:space="preserve">Half a sentence </w:t><w:br/>'
            '<w:t xml:space="preserve">and its other half.</w:t></w:r></w:p>'
        ),
        _edit(1, "Half a sentence and its other half.", "One sentence, rewritten."),
        written=False,
        reason="paragraph_holds_no_plain_run",
        role="refused",
    ),
    _sample(
        "25-refuse-a-package-that-is-not-a-package",
        "bytes that are not a Word package at all, handed to the write-back",
        (),
        para(TARGET),
        _edit(1, TARGET, REPLACED),
        written=False,
        reason="package_unreadable",
        role="refused",
        hostile="not-a-package",
    ),
    _sample(
        "26-refuse-a-package-with-no-document-part",
        "a zip that declares itself a package and holds no document part",
        (),
        para(TARGET),
        _edit(1, TARGET, REPLACED),
        written=False,
        reason="package_unreadable",
        role="refused",
        hostile="no-document-part",
    ),
)

#: The substitute set, ordered the way the matrix prints it: the half the seam
#: writes first, each half by name. **Sorted here rather than at each print
#: site**, because the artifact names, the row ids and the record's tables all
#: come off this tuple, and an ordering that lived in three places would be
#: three orderings that could disagree.
SAMPLES: Final[tuple[Sample, ...]] = tuple(
    sorted(_SAMPLES, key=lambda sample: (not sample.written, sample.name))
)


WRITABLE: Final[tuple[Sample, ...]] = tuple(sample for sample in SAMPLES if sample.written)
REFUSED: Final[tuple[Sample, ...]] = tuple(sample for sample in SAMPLES if not sample.written)


def by_name(name: str) -> Sample:
    """One sample by name, so a record can cite it without an index."""
    for sample in SAMPLES:
        if sample.name == name:
            return sample
    raise KeyError(f"no substitute sample is named {name!r}")
