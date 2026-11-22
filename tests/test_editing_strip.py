"""The strip stage keeps the package well-formed and the non-mark content
intact.

``LC-P3-08`` T6 found the trial's regex strip producing two malformed
``document.xml`` sites that Word 2019 refuses (the trial record's named
defect); :func:`labcairn.editing.strip.strip_advisor_marks` is the fix, and
these tests are its witnesses: a malformed output is the defect again, and
a lost non-mark element is the fidelity failure the strip exists to avoid.
"""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree
import zipfile

import pytest

from labcairn.editing.strip import strip_advisor_marks, strip_advisor_marks_package

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _w(tag: str) -> str:
    return f"{{{W}}}{tag}"


def _package(document_xml: bytes) -> bytes:
    import io

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/'
            'content-types"/>',
        )
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def _paragraph_with_marks() -> bytes:
    """A paragraph whose paragraph-mark ``w:rPr`` carries a ``w:del`` —
    the legal OOXML shape the trial's regex swallowed."""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{W}"><w:body>'
        "<w:p><w:pPr><w:spacing w:line=\"400\" w:lineRule=\"exact\"/>"
        "<w:rPr><w:del w:id=\"194\" w:author=\"T\" w:date=\"2025-10-10T17:21:00Z\"/>"
        "<w:sz w:val=\"24\"/></w:rPr></w:pPr>"
        "<w:r><w:rPr><w:sz w:val=\"24\"/></w:rPr><w:t>kept sentence</w:t></w:r>"
        "<w:del w:id=\"195\" w:author=\"T\" w:date=\"2025-10-10T17:21:00Z\">"
        "<w:r><w:delText>deleted sentence</w:delText></w:r></w:del>"
        "<w:ins w:id=\"196\" w:author=\"T\" w:date=\"2025-10-10T17:21:00Z\">"
        "<w:r><w:t>inserted sentence</w:t></w:r></w:ins>"
        "<w:commentRangeStart w:id=\"7\"/>"
        "<w:r><w:t>commented text</w:t></w:r>"
        "<w:commentRangeEnd w:id=\"7\"/>"
        "<w:commentReference w:id=\"7\"/>"
        "</w:p></w:body></w:document>"
    ).encode("utf-8")


def test_strip_removes_every_tracked_revision_and_comment_marker() -> None:
    stripped = strip_advisor_marks(_paragraph_with_marks())
    root = ElementTree.fromstring(stripped)
    tags = [element.tag for element in root.iter()]
    assert _w("del") not in tags
    assert _w("ins") not in tags
    assert _w("delText") not in tags
    assert _w("commentRangeStart") not in tags
    assert _w("commentRangeEnd") not in tags
    assert _w("commentReference") not in tags


def test_strip_keeps_the_paragraph_mark_properties_without_the_marker() -> None:
    stripped = strip_advisor_marks(_paragraph_with_marks())
    root = ElementTree.fromstring(stripped)
    sizes = [
        element.get(_w("val"))
        for element in root.iter(_w("sz"))
    ]
    # The paragraph-mark rPr's sz (24) survives with its del marker gone,
    # and so does the kept run's.
    assert sizes.count("24") == 2


def test_strip_output_is_well_formed_where_the_regex_was_not() -> None:
    # The advisor sample's actual defect: a w:del opening inside w:rPr and
    # closing outside it. A regex span removes the rPr's close with it; the
    # tree walk must not.
    stripped = strip_advisor_marks(_paragraph_with_marks())
    ElementTree.fromstring(stripped)  # raises on malformation


def test_strip_keeps_the_text_the_marks_did_not_own() -> None:
    stripped = strip_advisor_marks(_paragraph_with_marks())
    root = ElementTree.fromstring(stripped)
    texts = [element.text or "" for element in root.iter(_w("t"))]
    assert "kept sentence" in texts
    assert "commented text" in texts
    assert "inserted sentence" in texts
    assert "deleted sentence" not in texts


def test_package_strip_drops_the_comments_parts_and_keeps_the_rest() -> None:
    import io

    package = _package(_paragraph_with_marks())
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", _paragraph_with_marks())
        archive.writestr("word/comments.xml", "<w:comments/>")
        archive.writestr("word/media/image1.png", b"png")
    package = buffer.getvalue()

    stripped = strip_advisor_marks_package(package)
    names = zipfile.ZipFile(io.BytesIO(stripped)).namelist()
    assert "word/comments.xml" not in names
    assert "word/media/image1.png" in names
    assert "word/document.xml" in names


def test_strip_on_a_synthetic_advisor_shaped_document_stays_well_formed() -> None:
    # A deeper shape: a w:del inside a table cell's paragraph, and a w:ins
    # whose parent is the body — the nesting the trial sample carries.
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{W}"><w:body>'
        "<w:tbl><w:tr><w:tc><w:p><w:pPr><w:rPr>"
        "<w:del w:id=\"1\" w:author=\"A\" w:date=\"2025-01-01T00:00:00Z\"/>"
        "</w:rPr></w:pPr>"
        "<w:del w:id=\"2\" w:author=\"A\" w:date=\"2025-01-01T00:00:00Z\">"
        "<w:r><w:delText>cell deletion</w:delText></w:r></w:del>"
        "<w:ins w:id=\"3\" w:author=\"A\" w:date=\"2025-01-01T00:00:00Z\">"
        "<w:r><w:t>cell insertion</w:t></w:r></w:ins>"
        "</w:p></w:tc></w:tr></w:tbl>"
        "</w:body></w:document>"
    ).encode("utf-8")
    stripped = strip_advisor_marks(document)
    root = ElementTree.fromstring(stripped)
    assert not any(element.tag == _w("del") for element in root.iter())
    assert not any(element.tag == _w("ins") for element in root.iter())
    texts = [element.text or "" for element in root.iter(_w("t"))]
    assert "cell insertion" in texts
    assert "cell deletion" not in texts


@pytest.mark.parametrize("document", [_paragraph_with_marks()])
def test_strip_is_idempotent(document: bytes) -> None:
    once = strip_advisor_marks(document)
    twice = strip_advisor_marks(once)
    assert twice == once
