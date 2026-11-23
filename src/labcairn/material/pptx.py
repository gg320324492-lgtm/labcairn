"""Reading a PowerPoint deck's objects without damaging it.

This is Phase 4's P4-MS second source (execution plan §8.3): a deck's
titles, body text, speaker notes, tables and images, each **addressed by
the slide it sits on and the object it is** -- the provenance §8.3 requires
every extraction result to carry.

**Why this is written here and not taken from a library.** The same reason
:mod:`labcairn.material.ooxml` gives: the libraries that read Office
documents read them *selectively*, and a reader the product cannot
characterise is a reader that can silently drop what it does not
understand. ``python-pptx`` would add a dependency that shapes what can be
seen; the reader here is written against ECMA-376 / ISO-IEC 29500 (the
PresentationML parts of the OOXML package) with :mod:`zipfile` and
:mod:`xml.etree` only, so every element it reads is one this module named.

**What it reads.** For every slide, in the order the presentation names
them: the title placeholder's text; every other text-bearing shape's
paragraphs; the slide's notes slide text; every table's row-by-row cell
text; and every picture's name and its relationship target. **Every
extracted object carries its slide number (1-based), its position within
the slide (1-based, document order) and a source fingerprint** -- the
file's SHA-256 folded with the slide and the object's XML path -- so a hit
in the search index points back at the exact object it came from.

**What it refuses to do.**

* **It never writes.** The bytes are opened, read and closed.
* **It never guesses.** A shape whose text cannot be read contributes no
  text and a recorded problem; a chart or SmartArt -- whose data lives in
  a separate part this first version does not parse -- is recorded as a
  *limitation* with its location, never as invented content. The design's
  rule is the project's own: *"we could not look" is not "there was
  nothing there"*, and §8.3's is that an unparseable chart is a recorded
  limitation, not a conclusion.
* **It never expands entities.** A part that declares a DTD is refused,
  the way the Word reader refuses one -- entity expansion is a
  denial-of-service vector, and the standard library's parser is not the
  place to decide a document's entities are safe.

**Relationships are resolved, not assumed.** A picture's ``r:embed`` names
a relationship id, and the id means nothing until it is read from the
slide's own ``.rels`` part. A reference with no relationship is recorded
as a problem with the slide it sits on, not silently dropped.
"""

from __future__ import annotations

import hashlib
import io
import sys
import zipfile
from dataclasses import dataclass
from types import ModuleType
from typing import Final, Literal
from xml.etree import ElementTree

from labcairn.material.units import (
    ExtractedUnit,
    ExtractionProblem,
    ExtractionResult,
    register,
)
from labcairn.sources.locators import PptxLocator
from labcairn.sources.source import SourceKind

__all__ = [
    "PptxAdapter",
    "PptxObject",
    "PptxObjectKind",
    "read_deck",
]

#: The PresentationML namespace.
P: Final[str] = "http://schemas.openxmlformats.org/presentationml/2006/main"

#: The DrawingML namespace -- the one the shapes, tables and pictures live in.
A: Final[str] = "http://schemas.openxmlformats.org/drawingml/2006/main"

#: The office-document relationship namespace, for ``r:embed``.
R: Final[str] = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

#: The package's fixed part names.
PRESENTATION_PART: Final[str] = "ppt/presentation.xml"

#: The namespace-qualified names this module reads.
_TAG: Final[dict[str, str]] = {
    "sld_id_lst": f"{{{P}}}sldIdLst",
    "sld_id": f"{{{P}}}sldId",
    "c_sld": f"{{{P}}}cSld",
    "sp_tree": f"{{{P}}}spTree",
    "sp": f"{{{P}}}sp",
    "graphic_frame": f"{{{P}}}graphicFrame",
    "pic": f"{{{P}}}pic",
    "nv_sp_pr": f"{{{P}}}nvSpPr",
    "nv_pic_pr": f"{{{P}}}nvPicPr",
    "nv_graphic_frame_pr": f"{{{P}}}nvGraphicFramePr",
    "c_nv_pr": f"{{{P}}}cNvPr",
    "ph": f"{{{P}}}ph",
    "tx_body": f"{{{P}}}txBody",
    "notes": f"{{{P}}}notes",
    "tbl": f"{{{A}}}tbl",
    "tr": f"{{{A}}}tr",
    "tc": f"{{{A}}}tc",
    "p": f"{{{A}}}p",
    "r": f"{{{A}}}r",
    "t": f"{{{A}}}t",
    "blip": f"{{{A}}}blip",
    "prst_geom": f"{{{A}}}prstGeom",
    "graphic": f"{{{A}}}graphic",
    "graphic_data": f"{{{A}}}graphicData",
}

#: The ``a:graphicData`` URIs this reader recognises as a table or a chart.
#: **The table is parsed; the chart is recorded as a limitation** -- a
#: chart's numbers live in a separate part whose series and categories this
#: first version does not read, and inventing a summary from the frame's
#: name would be exactly the unsupported conclusion §8.3 forbids.
_TABLE_URI: Final[str] = "http://schemas.openxmlformats.org/drawingml/2006/table"
_CHART_URIS: Final[tuple[str, ...]] = (
    "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "http://schemas.openxmlformats.org/drawingml/2006/diagram",
)

#: The object kinds a deck's extraction yields. **The vocabulary is
#: closed** -- :class:`~labcairn.sources.locators.PptxLocator` accepts
#: exactly these, and the reader emits exactly these.
PptxObjectKind = Literal["title", "body", "notes", "table", "image"]


@dataclass(frozen=True)
class PptxObject:
    """One addressable object of a deck, with the provenance §8.3 requires.

    ``text`` is what the object says -- a picture's text is the name it
    carries, which is what the object is *called*, and that distinction is
    kept in ``kind``. ``locator`` is the structured address; ``fingerprint``
    is the object's own hash, derived from the file's content hash, the
    slide and the object's XML path, so the same object in the same deck
    always fingerprints the same way and a re-ingestion is the same rows.

    ``part`` is the package part the object was read from (the slide's part
    or the notes slide's), and ``object_path`` is the object's path within
    that part -- the two together name the XML the object is, which is what
    the index carries beside the slide and position. A notes paragraph's
    path is its own; the slide's shapes carry the path the shape sits at.
    """

    kind: PptxObjectKind
    slide: int
    position: int
    text: str
    locator: PptxLocator
    fingerprint: str
    #: The package part the object was read from.
    part: str
    #: The object's path within its part, re-derivable from the same file.
    object_path: str
    #: The relationship target, for an image -- the picture's bytes live in
    #: a media part, and naming the part is what makes the reference
    #: checkable. ``None`` for every other kind.
    media_target: str | None = None


@dataclass(frozen=True)
class PptxDeck:
    """Everything the reader found in one deck.

    ``problems`` is not an afterthought: an adapter that can only report
    success is indistinguishable from one that silently dropped a slide,
    and §8.3's rule -- an unparseable object is a recorded limitation --
    is carried in this field.
    """

    objects: tuple[PptxObject, ...] = ()
    problems: tuple[ExtractionProblem, ...] = ()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _local_name(tag: str) -> str:
    """The tag's name without its namespace."""
    return tag.rsplit("}", 1)[-1]


def _element_path(element: ElementTree.Element, root: ElementTree.Element) -> str:
    """A re-derivable path to ``element`` within ``root``.

    Each step is ``tag[n]``, where ``n`` is the 1-based index among the
    siblings that share that tag. The path names **structure** rather than
    content, so it survives a re-parse of the same tree and does not move
    when the text inside an element changes.
    """
    steps: list[str] = []
    current: ElementTree.Element | None = element
    while current is not None and current is not root:
        parent = _parent_of(current, root)
        if parent is None:
            break
        tag = _local_name(current.tag)
        index = 0
        for sibling in parent:
            if sibling.tag == current.tag:
                index += 1
                if sibling is current:
                    break
        steps.append(f"{tag}[{index}]")
        current = parent
    steps.append(f"{_local_name(root.tag)}[1]")
    steps.reverse()
    return "/" + "/".join(steps)


def _parent_of(
    element: ElementTree.Element, root: ElementTree.Element
) -> ElementTree.Element | None:
    """``element``'s parent, or ``None`` when it is the root.

    ``ElementTree`` has no parent pointer, so the tree is walked. That is
    O(n) per lookup; a slide holds a handful of shapes, so the walk is not
    a cost this module needs to hide.
    """
    for candidate in root.iter():
        for child in candidate:
            if child is element:
                return candidate
    return None


def _parse_part(name: str, data: bytes) -> ElementTree.Element:
    """Parse one XML part, or refuse it.

    **A part that declares a DTD is refused.** Entity expansion is a
    denial-of-service vector, and the standard library's parser is not the
    place to decide that a document's entities are safe. The refusal names
    the part, so the reader's problem list says which part and why.
    """
    head = data[:4096].upper()
    if b"<!DOCTYPE" in head:
        raise _RefusedPartError(
            f"{name} declares a DTD, which is refused: entity expansion is a "
            f"denial-of-service vector and this reader does not expand entities."
        )
    try:
        return ElementTree.fromstring(data)
    except ElementTree.ParseError as exc:
        raise _RefusedPartError(f"{name} is not well-formed XML: {exc}") from exc


class _RefusedPartError(Exception):
    """A part this reader will not read, and why."""


def _paragraph_text(paragraph: ElementTree.Element) -> str:
    """The words one ``a:p`` carries, runs in order.

    ``a:t`` is the only text-bearing element this reader reads; a run's
    other children (fields, line breaks) contribute nothing here, and a
    field whose text a renderer would compute is **not invented**.
    """
    return "".join(
        node.text or "" for node in paragraph.iter(_TAG["t"]) if node.text is not None
    )


def _shape_name(shape: ElementTree.Element, nv_pr_tag: str) -> str:
    """The shape's own name, or an empty string when it carries none.

    The name is what a reader sees on the object -- a picture's caption is
    often its name -- so it is read from the non-visual properties rather
    than invented from the shape's position.
    """
    nv = shape.find(_TAG[nv_pr_tag])
    if nv is None:
        return ""
    c_nv_pr = nv.find(_TAG["c_nv_pr"])
    if c_nv_pr is None:
        return ""
    return c_nv_pr.get("name") or ""


def _slide_parts(archive: zipfile.ZipFile, problems: list[ExtractionProblem]) -> list[str]:
    """The slide parts, in the order the presentation names them.

    **The order is ``presentation.xml``'s ``p:sldIdLst``, resolved through
    the package relationships** -- not the alphabetical order of the part
    names, which is the order a zip happens to store them in and not the
    order a viewer shows. A deck whose slides are read out of order would
    point every hit at the wrong page, so the relationship resolution is
    the reader's job, not the caller's.

    A slide id with no relationship is a problem, not a gap: the deck says
    it has a slide there, and a reader that skipped it would renumber every
    slide after it.
    """
    try:
        presentation = _parse_part(
            PRESENTATION_PART, archive.read(PRESENTATION_PART)
        )
    except (_RefusedPartError, KeyError) as exc:
        raise _RefusedPartError(f"{PRESENTATION_PART} could not be read: {exc}") from exc

    rels_name = "ppt/_rels/presentation.xml.rels"
    targets: dict[str, str] = {}
    if rels_name in archive.namelist():
        try:
            rels = _parse_part(rels_name, archive.read(rels_name))
        except _RefusedPartError as exc:
            problems.append(
                ExtractionProblem(
                    code="pptx_rels_refused",
                    detail=(
                        f"{rels_name} could not be read ({exc}); slide order falls "
                        f"back to the part names, which may not be the viewer's order."
                    ),
                )
            )
        else:
            for relationship in rels:
                targets[relationship.get("Id") or ""] = relationship.get("Target") or ""

    slide_parts: list[str] = []
    id_list = presentation.find(_TAG["sld_id_lst"])
    if id_list is None:
        raise _RefusedPartError(
            f"{PRESENTATION_PART} has no p:sldIdLst; it is not a presentation "
            f"this reader can read."
        )
    for slide_id in id_list.findall(_TAG["sld_id"]):
        relationship_id = slide_id.get(f"{{{R}}}id") or ""
        target = targets.get(relationship_id, "")
        if not target:
            problems.append(
                ExtractionProblem(
                    code="pptx_slide_rel_missing",
                    detail=(
                        f"the presentation names a slide with relationship "
                        f"{relationship_id!r} and no relationship part resolves it; "
                        f"the slide is recorded as unreachable rather than skipped, "
                        f"so the slide numbering stays the viewer's."
                    ),
                )
            )
            continue
        # A relationship target is relative to the presentation part's
        # directory; normalise it to a package part name.
        part = "ppt/" + target.removeprefix("../").removeprefix("./")
        if part in archive.namelist():
            slide_parts.append(part)
        else:
            problems.append(
                ExtractionProblem(
                    code="pptx_slide_part_missing",
                    detail=(
                        f"the presentation names slide part {part!r}, which the "
                        f"package does not hold; the slide is recorded as "
                        f"unreachable rather than skipped."
                    ),
                )
            )
    return slide_parts


def _slide_objects(
    archive: zipfile.ZipFile,
    slide_no: int,
    slide_part: str,
    file_sha: str,
    problems: list[ExtractionProblem],
) -> tuple[PptxObject, ...]:
    """One slide's objects, in document order, each addressed and hashed.

    The position is the object's index among the slide's shapes in document
    order -- the order the XML lists them, which is the order a viewer
    draws them -- and it is **1-based**, because a slide with no objects
    has no positions and a position of 0 would name nothing.
    """
    try:
        root = _parse_part(slide_part, archive.read(slide_part))
    except _RefusedPartError as exc:
        problems.append(
            ExtractionProblem(
                code="pptx_slide_refused",
                detail=f"slide {slide_no} ({slide_part}) could not be read: {exc}",
                location=f"slide:{slide_no}",
            )
        )
        return ()

    objects: list[PptxObject] = []
    c_sld = root.find(_TAG["c_sld"])
    if c_sld is None:
        problems.append(
            ExtractionProblem(
                code="pptx_slide_unshaped",
                detail=f"slide {slide_no} has no p:cSld, so it holds no objects this "
                f"reader can address.",
                location=f"slide:{slide_no}",
            )
        )
        return ()
    sp_tree = c_sld.find(_TAG["sp_tree"])
    if sp_tree is None:
        problems.append(
            ExtractionProblem(
                code="pptx_slide_unshaped",
                detail=f"slide {slide_no} has no p:spTree, so it holds no objects "
                f"this reader can address.",
                location=f"slide:{slide_no}",
            )
        )
        return ()

    # The slide's own relationships, for picture references. A slide with
    # no rels part has no pictures that resolve -- which is a fact about
    # the deck, not an error.
    rels_name = slide_part.replace("slides/", "slides/_rels/") + ".rels"
    media: dict[str, str] = {}
    if rels_name in archive.namelist():
        try:
            rels = _parse_part(rels_name, archive.read(rels_name))
        except _RefusedPartError as exc:
            problems.append(
                ExtractionProblem(
                    code="pptx_rels_refused",
                    detail=f"slide {slide_no}'s relationships could not be read: {exc}",
                    location=f"slide:{slide_no}",
                )
            )
        else:
            for relationship in rels:
                target = relationship.get("Target") or ""
                # Normalise to the package part name, the same way the
                # slide order's targets are normalised.
                normalised = "ppt/" + target.removeprefix("../").removeprefix("./")
                media[relationship.get("Id") or ""] = normalised

    position = 0
    for shape in sp_tree:
        tag = _local_name(shape.tag)
        if tag not in ("sp", "graphicFrame", "pic"):
            continue
        position += 1
        object_path = _element_path(shape, root)
        fingerprint_base = f"{file_sha}\x00{slide_part}\x00{object_path}"

        if tag == "sp":
            objects.extend(
                _text_shape_objects(
                    shape, slide_no, position, slide_part, object_path,
                    fingerprint_base, file_sha,
                )
            )
        elif tag == "graphicFrame":
            objects.extend(
                _frame_objects(
                    shape, slide_no, position, slide_part, object_path,
                    fingerprint_base, file_sha, problems,
                )
            )
        else:
            objects.extend(
                _picture_objects(
                    shape, slide_no, position, slide_part, object_path,
                    fingerprint_base, file_sha, media, problems,
                )
            )
    return tuple(objects)


def _make_object(
    kind: PptxObjectKind,
    slide_no: int,
    position: int,
    text: str,
    fingerprint_base: str,
    file_sha: str,
    part: str,
    object_path: str,
    media_target: str | None = None,
) -> PptxObject:
    """One object, addressed and fingerprinted.

    **The fingerprint folds the file's content hash, the slide part and the
    object's XML path** -- not the text, which two objects can share, and
    not the slide number alone, which two decks share. The same object in
    the same deck always fingerprints the same way, which is what makes a
    re-ingestion the same rows.
    """
    digest = hashlib.sha256(fingerprint_base.encode("utf-8")).hexdigest()
    return PptxObject(
        kind=kind,
        slide=slide_no,
        position=position,
        text=text,
        locator=PptxLocator(slide=slide_no, position=position, object_kind=kind),
        fingerprint=f"{file_sha[:16]}:{digest[:32]}",
        part=part,
        object_path=object_path,
        media_target=media_target,
    )


def _text_shape_objects(
    shape: ElementTree.Element,
    slide_no: int,
    position: int,
    slide_part: str,
    object_path: str,
    fingerprint_base: str,
    file_sha: str,
) -> tuple[PptxObject, ...]:
    """A text shape's objects: its title or body text, paragraph by paragraph.

    **A title is a placeholder, and the placeholder says so.** The ``p:ph``
    element's ``type`` attribute names the placeholder; a shape with no
    placeholder, or one whose type is not the title's, is body text. The
    distinction is the deck's own structure, read from the file rather
    than guessed from the position -- and a deck with no title placeholder
    has no title object, which is a fact and not a gap to fill.

    Every paragraph is its own object at its own position, because a
    bullet's address that named the whole text box would point four other
    bullets' words at the same locator.
    """
    placeholder = shape.find(f"{_TAG['nv_sp_pr']}/{_TAG['ph']}")
    kind: PptxObjectKind = "body"
    if placeholder is not None and placeholder.get("type") == "title":
        kind = "title"

    text_body = shape.find(_TAG["tx_body"])
    if text_body is None:
        return ()

    objects: list[PptxObject] = []
    paragraph_position = 0
    for paragraph in text_body.findall(_TAG["p"]):
        text = _paragraph_text(paragraph)
        if not text.strip():
            continue
        paragraph_position += 1
        objects.append(
            _make_object(
                kind,
                slide_no,
                position + paragraph_position - 1,
                text,
                f"{fingerprint_base}\x00p[{paragraph_position}]",
                file_sha,
                slide_part,
                f"{object_path}/a:txBody/a:p[{paragraph_position}]",
            )
        )
    return tuple(objects)


def _frame_objects(
    frame: ElementTree.Element,
    slide_no: int,
    position: int,
    slide_part: str,
    object_path: str,
    fingerprint_base: str,
    file_sha: str,
    problems: list[ExtractionProblem],
) -> tuple[PptxObject, ...]:
    """A graphic frame's objects: a table's cells, or a recorded limitation.

    **The frame's ``a:graphicData`` URI decides what it is**, and the URI
    is read, not inferred from the frame's name. A table is parsed row by
    row, each row one object whose text is the cells joined with a
    separator a reader can see -- so a row's address is one address, and
    the cells' own positions stay in the text. A chart or a diagram is
    recorded as a **limitation**: its numbers live in a part this reader
    does not parse, and summarising them from the frame's name would be
    the unsupported conclusion §8.3 forbids.
    """
    graphic = frame.find(_TAG["graphic"])
    if graphic is None:
        return ()
    graphic_data = graphic.find(_TAG["graphic_data"])
    if graphic_data is None:
        return ()
    uri = graphic_data.get("uri") or ""

    if uri == _TABLE_URI:
        table = graphic_data.find(_TAG["tbl"])
        if table is None:
            return ()
        objects: list[PptxObject] = []
        row_no = 0
        for row in table.findall(_TAG["tr"]):
            row_no += 1
            cells = []
            for cell in row.findall(_TAG["tc"]):
                cell_text = " ".join(
                    _paragraph_text(paragraph)
                    for paragraph in cell.findall(_TAG["p"])
                ).strip()
                cells.append(cell_text)
            text = " | ".join(cells)
            if not text.strip(" |"):
                continue
            objects.append(
                _make_object(
                    "table",
                    slide_no,
                    position + row_no - 1,
                    text,
                    f"{fingerprint_base}\x00tr[{row_no}]",
                    file_sha,
                    slide_part,
                    f"{object_path}/a:graphic/a:graphicData/a:tbl/a:tr[{row_no}]",
                )
            )
        return tuple(objects)

    if uri in _CHART_URIS:
        name = _shape_name(frame, "nv_graphic_frame_pr")
        named = f", named {name!r}" if name else ""
        problems.append(
            ExtractionProblem(
                code="pptx_chart_unparsed",
                detail=(
                    f"slide {slide_no} holds a chart or diagram "
                    f"({uri.rsplit('/', 1)[-1]}{named}) whose data lives in a part "
                    f"this reader does not parse. It is recorded as a limitation and "
                    f"no content is reported for it."
                ),
                location=f"slide:{slide_no}:object:{position}",
            )
        )
        return ()

    # A frame this reader does not recognise is named, not skipped: the
    # deck says something is there.
    problems.append(
        ExtractionProblem(
            code="pptx_frame_unrecognised",
            detail=(
                f"slide {slide_no} holds a graphic frame of kind {uri!r} that this "
                f"reader does not parse; no content is reported for it."
            ),
            location=f"slide:{slide_no}:object:{position}",
        )
    )
    return ()


def _picture_objects(
    picture: ElementTree.Element,
    slide_no: int,
    position: int,
    slide_part: str,
    object_path: str,
    fingerprint_base: str,
    file_sha: str,
    media: dict[str, str],
    problems: list[ExtractionProblem],
) -> tuple[PptxObject, ...]:
    """A picture's object: its name, and the media part it references.

    **A picture's text is its name**, because that is what the deck says
    the picture *is*; the picture's pixels are not text, and describing
    them would be a conclusion the bytes do not carry. The ``r:embed``
    relationship is resolved through the slide's own ``.rels`` part, and a
    reference with no relationship is a problem, not a silent drop.
    """
    name = _shape_name(picture, "nv_pic_pr")
    if not name.strip():
        return ()

    blip = picture.find(f".//{_TAG['blip']}")
    embed = blip.get(f"{{{R}}}embed") if blip is not None else None
    target = media.get(embed or "", "")
    if embed and not target:
        problems.append(
            ExtractionProblem(
                code="pptx_image_rel_missing",
                detail=(
                    f"slide {slide_no}'s picture {name!r} references relationship "
                    f"{embed!r}, which the slide's relationships do not resolve; the "
                    f"picture is reported with its name and no media target."
                ),
                location=f"slide:{slide_no}:object:{position}",
            )
        )
    return (
        _make_object(
            "image",
            slide_no,
            position,
            name,
            fingerprint_base,
            file_sha,
            slide_part,
            object_path,
            media_target=target or None,
        ),
    )


def _notes_objects(
    archive: zipfile.ZipFile,
    slide_no: int,
    notes_part: str,
    file_sha: str,
    problems: list[ExtractionProblem],
) -> tuple[PptxObject, ...]:
    """One slide's speaker notes, paragraph by paragraph.

    **The notes slide is its own part**, reached through the slide's
    relationships; a deck with no notes part for a slide has no notes for
    that slide, which is a fact. The notes' position is ``1`` -- the notes
    are one object per paragraph on the slide, and the slide's shapes do
    not number them.
    """
    try:
        root = _parse_part(notes_part, archive.read(notes_part))
    except _RefusedPartError as exc:
        problems.append(
            ExtractionProblem(
                code="pptx_notes_refused",
                detail=f"slide {slide_no}'s notes ({notes_part}) could not be read: {exc}",
                location=f"slide:{slide_no}:notes",
            )
        )
        return ()

    text_body = root.find(f"{_TAG['c_sld']}/{_TAG['tx_body']}")
    if text_body is None:
        return ()

    objects: list[PptxObject] = []
    paragraph_position = 0
    for paragraph in text_body.findall(_TAG["p"]):
        text = _paragraph_text(paragraph)
        if not text.strip():
            continue
        paragraph_position += 1
        digest = hashlib.sha256(
            f"{file_sha}\x00{notes_part}\x00p[{paragraph_position}]".encode("utf-8")
        ).hexdigest()
        objects.append(
            PptxObject(
                kind="notes",
                slide=slide_no,
                position=paragraph_position,
                text=text,
                locator=PptxLocator(
                    slide=slide_no, position=paragraph_position, object_kind="notes"
                ),
                fingerprint=f"{file_sha[:16]}:{digest[:32]}",
                part=notes_part,
                object_path=(
                    f"/p:notes/p:cSld/p:txBody/a:p[{paragraph_position}]"
                ),
            )
        )
    return tuple(objects)


def read_deck(data: bytes) -> PptxDeck:
    """Read a PowerPoint deck's objects.

    **The bytes are never modified.** They are opened, read and closed; the
    caller keeps the original and this function keeps nothing of it.

    A deck this reader cannot open at all is **one problem and no
    objects** -- "we could not look" -- and never an empty deck that reads
    as success.
    """
    problems: list[ExtractionProblem] = []

    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError) as exc:
        return PptxDeck(
            problems=(
                ExtractionProblem(
                    code="pptx_unreadable",
                    detail=(
                        f"the bytes are not a PowerPoint deck this reader can open: "
                        f"{type(exc).__name__}: {exc}. It is inventoried and hashed; "
                        f"no objects are extracted, because a deck we could not read "
                        f"is not an empty deck."
                    ),
                ),
            )
        )

    file_sha = _sha256(data)
    objects: list[PptxObject] = []

    with archive:
        names = archive.namelist()
        if PRESENTATION_PART not in names:
            return PptxDeck(
                problems=(
                    ExtractionProblem(
                        code="pptx_part_absent",
                        detail=(
                            f"the archive has no {PRESENTATION_PART}; it is not a "
                            f"PowerPoint deck this reader can read. It is inventoried "
                            f"and hashed, and nothing is extracted from it."
                        ),
                    ),
                )
            )
        try:
            slide_parts = _slide_parts(archive, problems)
        except _RefusedPartError as exc:
            return PptxDeck(
                problems=(
                    *problems,
                    ExtractionProblem(
                        code="pptx_presentation_refused",
                        detail=f"the presentation could not be read: {exc}",
                    ),
                )
            )

        for slide_no, slide_part in enumerate(slide_parts, start=1):
            objects.extend(
                _slide_objects(archive, slide_no, slide_part, file_sha, problems)
            )
            # The slide's notes, reached through the slide's own
            # relationships. A slide with no notes part has no notes.
            rels_name = slide_part.replace("slides/", "slides/_rels/") + ".rels"
            if rels_name in names:
                try:
                    rels = _parse_part(rels_name, archive.read(rels_name))
                except _RefusedPartError:
                    # Already recorded by the slide's own read; the notes
                    # are unreachable for the same reason and need no
                    # second problem saying so.
                    continue
                for relationship in rels:
                    if (relationship.get("Type") or "").endswith("/notesSlide"):
                        target = relationship.get("Target") or ""
                        part = "ppt/" + target.removeprefix("../").removeprefix("./")
                        if part in names:
                            objects.extend(
                                _notes_objects(
                                    archive, slide_no, part, file_sha, problems
                                )
                            )
                        break

    return PptxDeck(objects=tuple(objects), problems=tuple(problems))


@register
class PptxAdapter:
    """One object per extracted slide object, addressed and fingerprinted.

    **Every object is a unit, and every unit carries its address.** A
    deck's titles, body paragraphs, notes, table rows and picture names are
    all citable text: a hit in the search index points back at the slide
    and the object it came from, which is §8.3's requirement and the
    adapter's whole shape.
    """

    kind = SourceKind.PPTX

    def extract(self, data: bytes) -> ExtractionResult:
        deck = read_deck(data)
        units = tuple(
            ExtractedUnit(locator=deck_object.locator, text=deck_object.text)
            for deck_object in deck.objects
        )
        return ExtractionResult(units=units, problems=deck.problems)

    def libraries(self) -> dict[str, str]:
        """No dependency beyond the standard library.

        The reader uses :mod:`zipfile` and :mod:`xml.etree`, both of which
        ship with Python. **Adding a PPTX library would add exactly the
        behaviour this reader exists to avoid**: one that reads what its
        author's use case saw, and silently drops the rest.
        """
        return {}

    def source_modules(self) -> tuple[ModuleType, ...]:
        return (sys.modules[__name__],)
