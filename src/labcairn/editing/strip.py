"""Strip an advisor's tracked revisions and comment markers from a DOCX.

**What this is for.** The LC-P3-08 trial (2026-11-21) needed the advisor's
annotated sample turned into the clean text the trial loop runs on. The
first pass did it with regex substitution and produced a package Word 2019
refuses: two ``<w:del>`` elements in the advisor's sample open inside a
``<w:rPr>`` (the paragraph-mark run properties) and close outside it —
legal OOXML — and a non-greedy ``<w:del ...>...</w:del>`` span crossed the
``</w:rPr></w:pPr>`` closes and swallowed them. WPS tolerates the
malformed part; Word validates strictly and rejects the file. The trial
record names the defect (row 2, T6); this module is the fix, and the
dual-host reopen of its output is the evidence it holds.

**Why a tree walk and not a regex.** A tracked revision is a container, not
a span: ``w:ins`` wraps the runs it introduces, ``w:del`` wraps the runs it
removes, and both can sit anywhere a run can — including inside the
paragraph properties. A tree walk removes or unwraps exactly the marked
elements and leaves every other element, attribute and close tag alone, so
the part stays well-formed by construction.

**Why lxml, lazily.** The same rule the other edit arms keep (ADR-0013
constraint 2): a run that never strips a manuscript does not pay for lxml.
lxml is what preserves the source's own namespace prefixes —
``ElementTree`` renames them (``wp14`` → ``ns4`` …), and ``mc:Ignorable``
names prefixes by spelling, so a renamed prefix is an undeclared one: the
exact repair-prompt shape the reserialize module documents.

**What is removed.** Every ``w:del`` element whole (its ``w:delText`` runs
are deleted content and go with it); every ``w:ins`` element unwrapped (its
runs stay, the marker goes), iterated until neither remains — a ``w:del``
can sit inside an ``w:ins`` and the other way round; and the comment
markers (``w:commentRangeStart/End``, ``w:commentReference``), whose
``comments*.xml`` parts and relationships are dropped from the package.

**What is kept.** Everything else, byte for byte where the serialiser
allows: body text, tables, images, fields, equations, styles, numbering,
settings, theme, and the namespace declarations the root carries.
"""

from __future__ import annotations

import re
import zipfile
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from lxml import etree as lxml_etree

__all__ = ["strip_advisor_marks", "strip_advisor_marks_package"]

W: Final[str] = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

_COMMENTS_PARTS: Final[frozenset[str]] = frozenset(
    {
        "word/comments.xml",
        "word/commentsExtended.xml",
        "word/commentsIds.xml",
    }
)

_COMMENTS_REL: Final[re.Pattern[str]] = re.compile(
    r"<Relationship [^>]*comments[^>]*/>"
)


def _w(tag: str) -> str:
    return f"{{{W}}}{tag}"


def _strip_tree(root: "lxml_etree._Element") -> None:
    """Remove every tracked-revision and comment marker from the tree."""
    del_tag, ins_tag = _w("del"), _w("ins")
    markers = (
        _w("commentRangeStart"),
        _w("commentRangeEnd"),
        _w("commentReference"),
    )
    while True:
        for parent in list(root.iter()):
            for child in list(parent):
                if child.tag == ins_tag:
                    index = parent.index(child)
                    for offset, grandchild in enumerate(child):
                        parent.insert(index + offset, grandchild)
                    parent.remove(child)
        for parent in list(root.iter()):
            for child in list(parent):
                if child.tag == del_tag:
                    parent.remove(child)
        remaining = sum(
            1 for tag in (ins_tag, del_tag) for _ in root.iter(tag)
        )
        if remaining == 0:
            break
    for parent in list(root.iter()):
        for child in list(parent):
            if child.tag in markers:
                parent.remove(child)


def strip_advisor_marks(data: bytes) -> bytes:
    """The manuscript with the advisor's tracked revisions and comment
    markers removed, its other content and namespace prefixes preserved."""
    from lxml import etree as lxml_etree

    root = lxml_etree.fromstring(data)
    _strip_tree(root)
    return lxml_etree.tostring(
        root, encoding="UTF-8", xml_declaration=True, standalone=True
    )


def strip_advisor_marks_package(package: bytes) -> bytes:
    """The whole DOCX package with the advisor's marks stripped.

    ``document.xml`` is rewritten through :func:`strip_advisor_marks`; the
    ``comments*.xml`` parts and their relationships are dropped; every other
    part is carried through unchanged, in its original order and with its
    original ZIP metadata.
    """
    with zipfile.ZipFile(
        io := __import__("io").BytesIO(package)
    ) as source:
        stripped_document = strip_advisor_marks(source.read("word/document.xml"))
        rels_names = source.namelist()
        if "word/_rels/document.xml.rels" in rels_names:
            rels = source.read("word/_rels/document.xml.rels").decode("utf-8")
            stripped_rels = _COMMENTS_REL.sub("", rels)
        else:
            stripped_rels = None
        buffer = __import__("io").BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as target:
            for item in source.infolist():
                if item.filename in _COMMENTS_PARTS:
                    continue
                if item.filename == "word/document.xml":
                    target.writestr(item, stripped_document)
                elif item.filename == "word/_rels/document.xml.rels":
                    if stripped_rels is not None:
                        target.writestr(item, stripped_rels)
                else:
                    target.writestr(item, source.read(item.filename))
    return buffer.getvalue()
