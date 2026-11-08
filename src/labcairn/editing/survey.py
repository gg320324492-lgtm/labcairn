"""What a manuscript carries, and where a located passage sits inside it.

**The question this answers.** `LC-P3-02` §5.1 asks whether the product can
edit an **existing** manuscript without damaging what it did not touch, and
for which structures. The first half of that is a fact about the file: what
is in it, and where. A `.docx` is a package, and what a rewrite can lose
lives in different places — an equation and a figure are in
`word/document.xml`, the figure's bytes are in `word/media/`, the reviewer's
words are in `word/comments.xml`, a macro is in `word/vbaProject.bin`. A
survey that read only the document part would call a manuscript carrying a
macro an ordinary manuscript, and the write-back would rewrite the package
around it. So this is a **package** survey, and it also answers the
sharper question the write side needs: *is the passage I am about to
replace sitting inside something I have not measured?*

**Two columns, because preserved and editable are different claims.**
§5.7 item 2 asks for the *"preserved-or-refused structure classes"*.
**Preserved** means the seam carries the structure's bytes forward without
opening it; **editable** means a change may be aimed at a passage sitting
inside it. Equations are the case the two columns exist for: the surgical
seam preserves every equation it is not told to touch, byte for byte, and
refuses an edit aimed at one of the equation's runs — emitting an equation is
a different act from carrying one along, and the substitute run measured
carrying.

**Why byte spans and not a tree.** :func:`element_spans` walks a part with
`expat` and records where each element sits in the bytes. ElementTree hands
over no offsets, and a seam that re-serialises a part it parsed re-spells
every element in it: the `standalone` declaration goes, the namespace
declarations are hoisted and reordered, empty elements change form. That is
damage to regions the edit did not name. :mod:`labcairn.editing.reserialize`
exists so the cost of that choice is measured rather than argued about, and
:mod:`labcairn.editing.surgical` is the option that avoids it.

**The paragraph numbering is the reader's.** ``w:p`` elements are numbered in
document order here exactly as :func:`labcairn.material.ooxml.read_document`
numbers them, so an edit's address and a citation's address are one address
and cannot drift apart.
"""

from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ElementTree
import xml.parsers.expat as expat
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

# --------------------------------------------------------------------------- #
# namespaces and the part the seam rewrites
# --------------------------------------------------------------------------- #

#: The namespaces the survey matches on. **URIs, not prefixes**: a prefix is a
#: spelling and a URI is the fact, and Word renames prefixes between saves.
W_NS: Final[str] = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NS: Final[str] = "http://schemas.openxmlformats.org/officeDocument/2006/math"
MC_NS: Final[str] = "http://schemas.openxmlformats.org/markup-compatibility/2006"
WPS_NS: Final[str] = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
VML_NS: Final[str] = "urn:schemas-microsoft-com:vml"

#: The one part the seam rewrites. Every other part is carried forward.
DOCUMENT_PART: Final[str] = "word/document.xml"

#: The element spellings the byte walk is asked about. The walk runs with no
#: namespace processing, so it sees what the file writes, not what it means.
TAG_PARAGRAPH: Final[str] = "w:p"
TAG_RUN: Final[str] = "w:r"
TAG_TEXT: Final[str] = "w:t"


class StructureClass(StrEnum):
    """The classes the support matrix is written in.

    The names are §5.3's list (*"mixed comments and tracked revisions, tables,
    equations and images"*) plus the classes the refusal evidence needs. A
    class not named here is not in the matrix, and
    ``tests/test_docx_edit_records.py`` holds the three statements of it —
    this enum, :data:`SUPPORT`, and the rows printed in the acceptance record
    — to one set, because a record naming a class the mechanism does not know
    is a claim with nothing behind it.
    """

    BODY_TEXT = "body-text"
    TRACKED_REVISIONS = "tracked-revisions"
    COMMENTS = "comments"
    TABLES = "tables"
    EQUATIONS = "equations"
    IMAGES = "images"
    TEXT_BOXES = "text-boxes"
    FIELDS = "fields"
    CONTENT_CONTROLS = "content-controls"
    HYPERLINKS = "hyperlinks"
    COMMENT_PART = "comment-part"
    MEDIA = "media"
    VBA = "vba"
    EMBEDDED_OBJECTS = "embedded-objects"
    CUSTOM_XML = "custom-xml"
    SIGNATURES = "signatures"


#: Elements that evidence an in-document class, by resolved namespace URI.
CLASS_ELEMENTS: Final[Mapping[StructureClass, frozenset[str]]] = {
    StructureClass.BODY_TEXT: frozenset({f"{{{W_NS}}}t", f"{{{W_NS}}}r"}),
    StructureClass.TRACKED_REVISIONS: frozenset(
        {f"{{{W_NS}}}ins", f"{{{W_NS}}}del", f"{{{W_NS}}}moveFrom", f"{{{W_NS}}}moveTo"}
    ),
    StructureClass.COMMENTS: frozenset(
        {
            f"{{{W_NS}}}commentRangeStart",
            f"{{{W_NS}}}commentRangeEnd",
            f"{{{W_NS}}}commentReference",
        }
    ),
    StructureClass.COMMENT_PART: frozenset({f"{{{W_NS}}}comment"}),
    StructureClass.TABLES: frozenset({f"{{{W_NS}}}tbl", f"{{{W_NS}}}tr", f"{{{W_NS}}}tc"}),
    StructureClass.EQUATIONS: frozenset({f"{{{M_NS}}}oMath", f"{{{M_NS}}}oMathPara"}),
    StructureClass.IMAGES: frozenset(
        {f"{{{W_NS}}}drawing", f"{{{W_NS}}}object", f"{{{VML_NS}}}imagedata"}
    ),
    StructureClass.TEXT_BOXES: frozenset(
        {f"{{{W_NS}}}txbxContent", f"{{{WPS_NS}}}wsp", f"{{{MC_NS}}}AlternateContent"}
    ),
    StructureClass.FIELDS: frozenset(
        {f"{{{W_NS}}}fldSimple", f"{{{W_NS}}}fldChar", f"{{{W_NS}}}instrText"}
    ),
    StructureClass.CONTENT_CONTROLS: frozenset(
        {f"{{{W_NS}}}sdt", f"{{{W_NS}}}sdtContent", f"{{{W_NS}}}sdtPr"}
    ),
    StructureClass.HYPERLINKS: frozenset({f"{{{W_NS}}}hyperlink"}),
}

#: Part names that evidence a package-level class.
CLASS_PART_PATTERNS: Final[Mapping[StructureClass, re.Pattern[str]]] = {
    StructureClass.MEDIA: re.compile(r"^word/media/"),
    StructureClass.VBA: re.compile(r"^word/vbaProject\.bin$"),
    StructureClass.EMBEDDED_OBJECTS: re.compile(r"^word/embeddings/"),
    StructureClass.CUSTOM_XML: re.compile(r"^customXml/"),
    StructureClass.SIGNATURES: re.compile(r"^signatures/"),
}

#: The spellings the byte walk reads as "this element is not plain text".
#: :data:`UNEDITABLE_CLASSES` names the class; this maps the *spelling* to it,
#: because the walk is namespace-unaware and a URI-matched answer would not
#: be an answer about these bytes.
TAG_CLASS: Final[Mapping[str, StructureClass]] = {
    "m:oMath": StructureClass.EQUATIONS,
    "m:oMathPara": StructureClass.EQUATIONS,
    "w:drawing": StructureClass.IMAGES,
    "w:object": StructureClass.IMAGES,
    "v:shape": StructureClass.IMAGES,
    "v:imagedata": StructureClass.IMAGES,
    "mc:AlternateContent": StructureClass.TEXT_BOXES,
    "mc:Choice": StructureClass.TEXT_BOXES,
    "mc:Fallback": StructureClass.TEXT_BOXES,
    "w:pict": StructureClass.TEXT_BOXES,
    "w:txbxContent": StructureClass.TEXT_BOXES,
    "wps:wsp": StructureClass.TEXT_BOXES,
    "w:fldSimple": StructureClass.FIELDS,
    "w:fldChar": StructureClass.FIELDS,
    "w:instrText": StructureClass.FIELDS,
    "w:sdt": StructureClass.CONTENT_CONTROLS,
    "w:sdtContent": StructureClass.CONTENT_CONTROLS,
    "w:sdtPr": StructureClass.CONTENT_CONTROLS,
    "w:tbl": StructureClass.TABLES,
    "w:hyperlink": StructureClass.HYPERLINKS,
}

#: Classes a change may be aimed at. Each of these wraps plain runs rather
#: than replacing them, so replacing the run leaves the wrapper's own work —
#: the revision mark, the comment range, the cell, the link — standing.
EDITABLE_CLASSES: Final[frozenset[StructureClass]] = frozenset(
    {
        StructureClass.BODY_TEXT,
        StructureClass.TRACKED_REVISIONS,
        StructureClass.COMMENTS,
        StructureClass.TABLES,
        StructureClass.HYPERLINKS,
    }
)

#: Classes a change may **not** be aimed at, because the seam emits plain
#: runs and the substitute run measured it carrying these, never writing one.
UNEDITABLE_CLASSES: Final[frozenset[StructureClass]] = frozenset(
    {
        StructureClass.EQUATIONS,
        StructureClass.IMAGES,
        StructureClass.TEXT_BOXES,
        StructureClass.FIELDS,
        StructureClass.CONTENT_CONTROLS,
    }
)

#: Classes that make the package unsafe to rewrite at all, wherever the
#: passage sits. Each is a part the substitute run carried through a rewrite
#: without ever opening, so the run says nothing about editing *it* — and the
#: seam has no way to promise the host will not mind.
UNSAFE_PACKAGE_CLASSES: Final[frozenset[StructureClass]] = frozenset(
    {
        StructureClass.VBA,
        StructureClass.EMBEDDED_OBJECTS,
        StructureClass.CUSTOM_XML,
        StructureClass.SIGNATURES,
    }
)


# --------------------------------------------------------------------------- #
# the support matrix, as data
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ClassSupport:
    """What the seam claims about one structure class.

    ``editable`` is the refusal column: may a change be aimed at this?
    ``carried`` is the preservation column for the seam the record adopts —
    the class's bytes survive a rewrite of somewhere else. The two are kept
    apart because §5.7 item 2 asks for *"preserved-or-refused"* and one word
    covering both claims would let a refusal read as a loss.
    """

    structure: StructureClass
    editable: bool
    carried: bool
    reason: str


def _support(
    structure: StructureClass, *, editable: bool, carried: bool, reason: str
) -> ClassSupport:
    return ClassSupport(structure=structure, editable=editable, carried=carried, reason=reason)


#: The matrix as data. ``docs/acceptance/LC-P3-02-support-matrix.md`` prints
#: exactly this table, and ``tests/test_docx_edit_records.py`` re-derives
#: every row from a fresh measurement of the substitute set: a row that stops
#: being true stops being printable.
SUPPORT: Final[Mapping[StructureClass, ClassSupport]] = {
    support.structure: support
    for support in (
        _support(
            StructureClass.BODY_TEXT,
            editable=True,
            carried=True,
            reason="a plain run is what the seam exists to replace",
        ),
        _support(
            StructureClass.TRACKED_REVISIONS,
            editable=True,
            carried=True,
            reason=(
                "a revision outside the located run travels untouched; aimed at, "
                "its run is still a plain run"
            ),
        ),
        _support(
            StructureClass.COMMENTS,
            editable=True,
            carried=True,
            reason="the range markers sit around the run, not inside it",
        ),
        _support(
            StructureClass.COMMENT_PART,
            editable=False,
            carried=True,
            reason=(
                "word/comments.xml is carried verbatim when the edit is in the body, "
                "and the seam rewrites the document part alone: an edit aimed at a "
                "reviewer's own words is a different act with a different contract"
            ),
        ),
        _support(
            StructureClass.TABLES,
            editable=True,
            carried=True,
            reason=(
                "a cell paragraph is addressable and its run is a plain run; the "
                "grid, the row and the cell properties are not opened"
            ),
        ),
        _support(
            StructureClass.HYPERLINKS,
            editable=True,
            carried=True,
            reason="a hyperlink wraps runs, so replacing the run leaves the wrap",
        ),
        _support(
            StructureClass.EQUATIONS,
            editable=False,
            carried=True,
            reason="an equation's runs are m:r, not w:r: the seam emits plain runs",
        ),
        _support(
            StructureClass.IMAGES,
            editable=False,
            carried=True,
            reason="a drawing carries no text the seam could replace",
        ),
        _support(
            StructureClass.TEXT_BOXES,
            editable=False,
            carried=True,
            reason=(
                "a nested body inside an AlternateContent pair: writing the Choice "
                "alone leaves the Fallback saying something else"
            ),
        ),
        _support(
            StructureClass.FIELDS,
            editable=False,
            carried=True,
            reason="a field's text is the last result the host cached, not the answer",
        ),
        _support(
            StructureClass.CONTENT_CONTROLS,
            editable=False,
            carried=True,
            reason="a content control's alias and its bound data are outside the seam",
        ),
        _support(
            StructureClass.MEDIA,
            editable=False,
            carried=True,
            reason="a part, not a region: carried byte for byte",
        ),
        _support(
            StructureClass.VBA,
            editable=False,
            carried=False,
            reason="a macro part was carried but never opened by this run's rewrite",
        ),
        _support(
            StructureClass.EMBEDDED_OBJECTS,
            editable=False,
            carried=False,
            reason="word/embeddings/ was carried but never opened by this run's rewrite",
        ),
        _support(
            StructureClass.CUSTOM_XML,
            editable=False,
            carried=False,
            reason="a customXml item is bound to the document by parts the seam never read",
        ),
        _support(
            StructureClass.SIGNATURES,
            editable=False,
            carried=False,
            reason="any rewrite of the package invalidates the signature over it",
        ),
    )
}


# --------------------------------------------------------------------------- #
# the package survey
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PackageSurvey:
    """What the manuscript carries, and where each class was seen.

    ``parts`` is in **archive order**: the seam is asked to preserve that
    order, and a survey that sorted the names could not see a reorder.
    """

    parts: tuple[str, ...]
    classes: frozenset[StructureClass]
    #: Classes seen inside the part the seam rewrites. A class outside this
    #: set travels in a part the seam never parses.
    classes_in_document: frozenset[StructureClass]
    seen_in: Mapping[StructureClass, tuple[str, ...]] = field(default_factory=dict)

    def carries(self, structure: StructureClass) -> bool:
        return structure in self.classes

    def blocked(self) -> frozenset[StructureClass]:
        """Classes that make the package unsafe, so no plan is ever built."""
        return self.classes & UNSAFE_PACKAGE_CLASSES


def _parse_part(blob: bytes) -> ElementTree.Element | None:
    try:
        return ElementTree.fromstring(blob)
    except ElementTree.ParseError:
        # An unreadable part is the read side's finding, not a structure
        # class. Inventing one here would report the same defect twice, in
        # two different words.
        return None


def survey(data: bytes) -> PackageSurvey:
    """Every structure class this manuscript carries, part by part.

    **No file is opened and no byte is written.** The bytes go into memory
    and are walked, which is what lets a refusal be reported as *"nothing
    happened"* rather than *"something happened and was undone"*.
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError(f"these bytes are not a package this seam can survey: {exc}") from exc

    with archive:
        names = tuple(info.filename for info in archive.infolist())
        if DOCUMENT_PART not in names:
            raise ValueError(f"the package has no {DOCUMENT_PART}; it is not a manuscript")

        found: set[StructureClass] = set()
        in_document: set[StructureClass] = set()
        seen: dict[StructureClass, list[str]] = {}

        def note(structure: StructureClass, where: str) -> None:
            found.add(structure)
            listed = seen.setdefault(structure, [])
            if where not in listed:
                listed.append(where)
            if where == DOCUMENT_PART:
                in_document.add(structure)

        blobs: dict[str, bytes] = {}
        for name in names:
            payload = archive.read(name)
            for structure, pattern in CLASS_PART_PATTERNS.items():
                if pattern.match(name):
                    note(structure, name)
            if name.endswith((".xml", ".rels")):
                blobs[name] = payload

        for name, payload in blobs.items():
            root = _parse_part(payload)
            if root is None:
                continue
            tags = {element.tag for element in root.iter()}
            for structure, elements in CLASS_ELEMENTS.items():
                if tags & elements:
                    note(structure, name)

    return PackageSurvey(
        parts=names,
        classes=frozenset(found),
        classes_in_document=frozenset(in_document),
        seen_in={key: tuple(value) for key, value in seen.items()},
    )


# --------------------------------------------------------------------------- #
# byte spans
# --------------------------------------------------------------------------- #


@dataclass
class Span:
    """One element's byte span within a part, ``[start, end)``.

    ``end`` is the offset just past the element's **closing** ``>``, so a
    self-closing element's span is its single tag and an element with a
    separate end tag's span runs through that tag. The seam replaces
    ``part[start:end]`` and nothing else, which is the whole of its claim to
    leave the surrounding bytes alone.

    ``ancestors`` is the chain of element spellings the walk was inside when
    this element opened. It is kept because the refusal question is exactly
    ``is this run inside an equation?``, and answering that from spans alone
    would mean re-walking the tree for every candidate.
    """

    tag: str
    start: int
    end: int
    ancestors: tuple[str, ...]
    #: ``len(ancestors)``. Two elements share a parent exactly when their
    #: depths differ by one and the shallower one holds the deeper: every run
    #: spells ``w:r``, so the tag alone cannot tell one run's child from
    #: another run's, and a text box guarantees both appear.
    depth: int
    #: The element's own attributes, spelled as the file spells them. Needed
    #: because a Word field is a *sequence* of sibling elements rather than an
    #: element, and the only thing that says which end of the sequence a
    #: ``w:fldChar`` is, is its ``w:fldCharType``.
    attrs: Mapping[str, str] = field(default_factory=dict)
    #: 1-based ordinal among the paragraphs of the part, when it is one.
    paragraph_ordinal: int | None = None

    def holds(self, other: Span) -> bool:
        return self.start <= other.start and other.end <= self.end

    @property
    def classes(self) -> frozenset[StructureClass]:
        """The classes this element sits inside, itself included."""
        spelled = {TAG_CLASS[tag] for tag in (*self.ancestors, self.tag) if tag in TAG_CLASS}
        return frozenset(spelled)


@dataclass(frozen=True)
class Spans:
    """The located shapes inside one XML part, in document order.

    ``every`` is ordered by where an element **closes**, because that is when
    its span is known; :attr:`opened` is ordered by where it opens, and a
    question about what comes *before* a run — whether a field was opened and
    not yet closed — can only be answered in that order.
    """

    every: tuple[Span, ...]
    paragraphs: tuple[Span, ...]
    runs: tuple[Span, ...]
    opened: tuple[Span, ...] = ()

    def runs_inside(self, paragraph: Span) -> tuple[Span, ...]:
        """The runs of this paragraph, and no deeper paragraph's.

        **The exclusion is the whole of the nested-body case.** A text box
        inside paragraph 9 holds paragraphs of its own; a seam that collected
        runs by byte offsets alone would locate a boxed run as though it were
        a body run and edit a sentence the reviewer wrote inside a figure.
        """
        nested = tuple(
            other for other in self.paragraphs if other is not paragraph and paragraph.holds(other)
        )
        return tuple(
            run
            for run in self.runs
            if paragraph.holds(run) and not any(other.holds(run) for other in nested)
        )


def element_spans(part: bytes) -> Spans:
    """Every element's byte span, with the paragraphs and the runs in order.

    **The offsets come from expat, and expat does not report the same thing
    to the two handlers.** Inside the start handler ``CurrentByteIndex`` is
    the offset of this element's own ``<``. Inside the end handler it is the
    offset of the closing tag's ``<`` for an element written with a separate
    end tag, and the offset just past ``/>`` for a self-closing one. The two
    are told apart by reading the bytes at the reported position rather than
    by assuming a shape: a walk that got it wrong would end every empty
    element six bytes past itself, and the seam would splice bytes it had
    never located.
    """
    parser = expat.ParserCreate()
    every: list[Span] = []
    opened: list[Span] = []
    paragraphs: list[Span] = []
    runs: list[Span] = []
    stack: list[Span] = []
    ordinals = {"count": 0}

    def on_start(tag: str, attrs: dict[str, str]) -> None:
        span = Span(
            tag=tag,
            attrs=dict(attrs),
            start=parser.CurrentByteIndex,
            end=parser.CurrentByteIndex,
            ancestors=tuple(opened.tag for opened in stack),
            depth=len(stack),
        )
        if tag == TAG_PARAGRAPH:
            ordinals["count"] += 1
            span.paragraph_ordinal = ordinals["count"]
        opened.append(span)
        stack.append(span)

    def on_end(tag: str) -> None:
        span = stack.pop()
        index = parser.CurrentByteIndex
        if part[index : index + 2] == b"</":
            span.end = index + len(f"</{tag}>".encode())
        else:
            span.end = index
        every.append(span)
        if tag == TAG_PARAGRAPH:
            paragraphs.append(span)
        elif tag == TAG_RUN:
            runs.append(span)

    parser.StartElementHandler = on_start
    parser.EndElementHandler = on_end
    try:
        parser.Parse(part, True)
    except expat.ExpatError as exc:
        raise ValueError(f"the part does not parse: {exc}") from exc

    # **Sorted by where an element opens, not by where it closes.** The end
    # handler reports a nested element before its enclosing one — a text box's
    # paragraph closes before the paragraph holding the box — and
    # :func:`labcairn.material.ooxml.read_document` numbers paragraphs in the
    # order they open. A walk that kept close order would hand the seam and
    # the reader different numbers for the same sentence, which is the drift
    # this module's heading says it must not have.
    return Spans(
        every=tuple(sorted(every, key=lambda span: span.start)),
        paragraphs=tuple(sorted(paragraphs, key=lambda span: span.start)),
        runs=tuple(sorted(runs, key=lambda span: span.start)),
        opened=tuple(opened),
    )


def enclosing_paragraph(run: Span, spans: Spans) -> Span | None:
    """The paragraph a run belongs to: the tightest one that holds it."""
    holders = [paragraph for paragraph in spans.paragraphs if paragraph.holds(run)]
    return min(holders, key=lambda paragraph: paragraph.end - paragraph.start) if holders else None


def inside_field(run: Span, spans: Spans) -> bool:
    """Whether the run sits between a field's begin and its end.

    **Why this is a question about order and not about containment.** A Word
    field is not an element: it is a *sequence* — ``w:fldChar`` begin, the
    instruction in ``w:instrText``, a separate, the cached answer, an end.
    The cached answer's run has the paragraph as its parent and no refused
    ancestor at all, so an ancestor check lets it through, and replacing it
    puts a sentence in the document that the document's own instruction
    contradicts the next time the host recomputes. The only way to see the
    field is to walk what comes before the run.
    """
    paragraph = enclosing_paragraph(run, spans)
    if paragraph is None:
        return False
    if "w:fldSimple" in run.ancestors:
        return True
    depth = 0
    for span in spans.opened:
        if span.start >= run.start:
            break
        if not paragraph.holds(span):
            continue
        if span.tag != "w:fldChar":
            continue
        kind = span.attrs.get("w:fldCharType", "")
        if kind == "begin":
            depth += 1
        elif kind == "end":
            depth -= 1
    return depth > 0


_DECLARATION: Final[re.Pattern[str]] = re.compile(r'xmlns:([A-Za-z0-9_]+)="([^"]+)"')


def root_open_tag(part: bytes) -> str:
    """The root element's opening tag, verbatim, past the declaration.

    **Why this is a walk and not a slice to the first ``>``.** A Word part
    begins ``<?xml …?>``, and that ``?&gt;`` is the first ``>`` in the file. A
    scan that stopped there would read the declaration as the root element,
    find no ``xmlns`` in it, and report that the document declares no prefixes
    at all — which is a measurement of the scanner, not of the file. Two
    callers depend on the answer being the file's: the survey resolves the
    byte walk's spelled tags through it, and the whole-part serialiser
    registers it before writing. Get it wrong there and every prefix becomes
    ``ns0`` and ``mc:Choice Requires="wps"`` names a prefix nothing declares.
    """
    text = part.decode("utf-8", "replace")
    index = 0
    while True:
        start = text.find("<", index)
        if start == -1:
            return ""
        if text.startswith("<?", start):
            end = text.find("?>", start)
            index = end + 2 if end != -1 else len(text)
            continue
        if text.startswith("<!--", start):
            end = text.find("-->", start)
            index = end + 3 if end != -1 else len(text)
            continue
        if text.startswith("<!", start):
            end = text.find(">", start)
            bracket = text.find("[", start)
            if bracket != -1 and end != -1 and bracket < end:
                close = text.find("]", bracket)
                after = text.find(">", close) if close != -1 else end
                index = after + 1
            else:
                index = end + 1 if end != -1 else len(text)
            continue
        end = text.find(">", start)
        return text[start : end + 1] if end != -1 else text[start:]


def prefix_map(part: bytes) -> Mapping[str, str]:
    """The ``prefix`` to ``uri`` declarations on the part's root element."""
    return dict(_DECLARATION.findall(root_open_tag(part)))


def resolve_tag(spelled: str, prefixes: Mapping[str, str]) -> str:
    """``w:ins`` to ``{uri}ins``, the form :data:`CLASS_ELEMENTS` is keyed on.

    **The byte walk spells names; the survey matches URIs; this is where they
    meet.** A host that writes the WordprocessingML namespace under some other
    prefix still resolves, because the resolution reads the file's own
    declarations rather than a table of expected spellings — which is the same
    reason the survey compares URIs in the first place.
    """
    prefix, _, local = spelled.partition(":")
    if not local:
        return spelled
    uri = prefixes.get(prefix)
    return f"{{{uri}}}{local}" if uri else spelled


def element_text(part: bytes, span: Span) -> str:
    """The text one ``w:t`` element carries, with the escapes resolved.

    **Read with ``expat``, not with ``ElementTree``, and the reason is a
    prefix.** A fragment of a Word part says ``<w:t>`` and the declaration of
    ``w:`` sits on the root element the fragment came from, so a
    namespace-aware parse of the fragment fails on an unbound prefix. The
    byte walk and this reader both run with namespace processing off: they
    answer questions about the bytes as written, which is exactly what a
    seam that replaces bytes needs.

    Escapes matter because ``&amp;`` in a manuscript sentence is ordinary,
    and a seam comparing raw bytes would refuse the edits it exists to make.
    """
    parser = expat.ParserCreate()
    chunks: list[str] = []
    parser.CharacterDataHandler = chunks.append
    try:
        parser.Parse(part[span.start : span.end], True)
    except expat.ExpatError:
        return ""
    return "".join(chunks)


def escape(text: str) -> str:
    """Escape text for a ``w:t`` node.

    The three characters that can break a text node, and nothing else: a
    quote inside ``<w:t>`` is not special, and escaping it would put
    backslashes in the reviewer's sentence.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
