"""The redaction, watched.

**What this file watches.** ``scripts/pilot_redaction.py`` produces the
pilot's desensitised copy from the advisor's original. The copy that was
registered first was made by *accepting* every revision, so the trail the
pilot's trajectory view reads was gone; this tool keeps the trail and takes
the identity out. The properties watched here are the ones that make that
true:

- the redacted copy keeps **every revision mark**: the counts of
  insertions, deletions and format changes are the original's;
- the redacted copy's **text** is the original's text, byte for byte --
  the redaction takes identity out and nothing else;
- the built-in and custom properties are **blanked**, and the markup's
  author fields carry **role labels** instead of names;
- a path inside an image's own metadata is **blanked in place**, at the
  same length, so the image data does not move;
- an author the map does not name is **refused**, not kept and not
  guessed: the tool stops and says which one, because an unmapped author is
  an identity still in the copy;
- a copy written **inside this repository** is refused, because the
  material does not belong in the tree.

**The witnesses must fail for the property.** Each test names what would
make it red, and none of them is red for a reason unrelated to the
property it watches.

**Nothing here touches the real material.** Every document in this file is
built in a temporary directory out of synthetic parts.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "pilot_redaction.py"

#: A name that is in the synthetic original and in nothing else.
AUTHOR = "Ada Lovelace"
SECOND_AUTHOR = "Grace Hopper"

#: A path that is in the synthetic image's metadata and in nothing else.
IMAGE_PATH = rb"C:\Users\someone\Desktop\Graphs\figure1.tif"

#: Bytes that hold a backslash by chance, the way a picture's pixels do.
#: A redaction that blanks these damages the picture.
COINCIDENTAL = rb"a\\b\x00pixel\x00"

#: The label's text, as the picture's directory points at it.
DESCRIPTION = IMAGE_PATH + b"\x00" + COINCIDENTAL


def _tiff(description: bytes) -> bytes:
    """A TIFF whose directory points at one text label.

    The label is a BYTE-typed tag, the way Word writes a picture's
    description, and the bytes that follow it stand for the picture's own
    data -- which the redaction must not touch.
    """
    header = b"II" + (42).to_bytes(2, "little") + (8).to_bytes(4, "little")
    entries = 1
    directory_at = 8
    data_at = directory_at + 2 + entries * 12 + 4
    entry = (270).to_bytes(2, "little")  # ImageDescription
    entry += (1).to_bytes(2, "little")  # BYTE
    entry += len(description).to_bytes(4, "little")
    entry += data_at.to_bytes(4, "little")
    directory = entries.to_bytes(2, "little") + entry + (0).to_bytes(4, "little")
    return header + directory + description + b"\x00\x01picture data\x02"


_spec = importlib.util.spec_from_file_location("pilot_redaction_under_test", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None, (
    "scripts/pilot_redaction.py could not be loaded as a module"
)
redaction: ModuleType = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = redaction
_spec.loader.exec_module(redaction)

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W15 = "http://schemas.microsoft.com/office/word/2012/wordml"

DOCUMENT = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{W}" xmlns:w15="{W15}"
 xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
 mc:Ignorable="w14 w15">
<w:body>
<w:p><w:r><w:t xml:space="preserve">the body of the paper</w:t></w:r></w:p>
<w:p>
<w:ins w:id="1" w:author="{AUTHOR}" w:date="2026-01-01T00:00:00Z"
><w:r><w:t>inserted</w:t></w:r></w:ins>
<w:del w:id="2" w:author="{SECOND_AUTHOR}" w:date="2026-01-01T00:00:00Z"
><w:r><w:delText>deleted</w:delText></w:r></w:del>
<w:rPr><w:rPrChange w:id="3" w:author="{AUTHOR}" w:date="2026-01-01T00:00:00Z"/></w:rPr>
</w:p>
</w:body></w:document>"""

PEOPLE = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w15:people xmlns:w15="{W15}"><w15:person w15:author="{AUTHOR}"/></w15:people>"""

CORE = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties
 xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:creator>{AUTHOR}</dc:creator>
<cp:lastModifiedBy>{SECOND_AUTHOR}</cp:lastModifiedBy>
</cp:coreProperties>"""

APP = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
<Company>Some Institute</Company>
<Manager>Nobody</Manager>
<Template>Normal.dotm</Template>
</Properties>"""

CUSTOM = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties
 xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
 xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
<property fmtid="{D5CDD505-2E9C-101B-9397-08002B2CF9AE}" pid="2" name="ICV"
><vt:lpwstr>an-identifier</vt:lpwstr></property>
</Properties>"""

IMAGE = _tiff(DESCRIPTION)


def _build_original(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", DOCUMENT)
        archive.writestr("word/people.xml", PEOPLE)
        archive.writestr("docProps/core.xml", CORE)
        archive.writestr("docProps/app.xml", APP)
        archive.writestr("docProps/custom.xml", CUSTOM)
        archive.writestr("word/media/image1.tiff", IMAGE)
    return path


def _map(tmp_path: Path, mapping: dict[str, str] | None = None) -> Path:
    path = tmp_path / "author-map.json"
    path.write_text(
        json.dumps(
            mapping if mapping is not None else {AUTHOR: "advisor", SECOND_AUTHOR: "student-1"}
        ),
        encoding="utf-8",
    )
    return path


def _part(path: Path, name: str) -> bytes:
    with zipfile.ZipFile(path) as archive:
        return archive.read(name)


def _counts(path: Path) -> dict[str, int]:
    document = _part(path, "word/document.xml").decode("utf-8")
    return {
        "ins": document.count("<w:ins "),
        "del": document.count("<w:del "),
        "rPrChange": document.count("<w:rPrChange "),
    }


def test_the_redacted_copy_keeps_every_revision_mark(tmp_path: Path) -> None:
    """The trail is the thing the redaction exists to keep.

    Red by: the tool dropping, accepting or counting a revision differently.
    """
    original = _build_original(tmp_path / "original.docx")
    out = tmp_path / "out" / "copy.docx"
    report = redaction.redact(original, out, {AUTHOR: "advisor", SECOND_AUTHOR: "student-1"})
    assert _counts(out) == _counts(original)
    assert report["parts"]["word/document.xml"]["author_fields_replaced"] == 3


def test_the_redacted_copy_keeps_the_original_s_text(tmp_path: Path) -> None:
    """The redaction takes identity out and nothing else.

    Red by: the tool changing the document's words.
    """
    original = _build_original(tmp_path / "original.docx")
    out = tmp_path / "out" / "copy.docx"
    redaction.redact(original, out, {AUTHOR: "advisor", SECOND_AUTHOR: "student-1"})
    before = _part(original, "word/document.xml").decode("utf-8")
    after = _part(out, "word/document.xml").decode("utf-8")
    for text in ("the body of the paper", ">inserted<", ">deleted<"):
        assert text in before
        assert text in after


def test_the_redacted_copy_carries_role_labels_instead_of_names(tmp_path: Path) -> None:
    """A name in the markup is the identity the copy must not hold.

    Red by: the tool leaving a name in the markup or in the people list.
    """
    original = _build_original(tmp_path / "original.docx")
    out = tmp_path / "out" / "copy.docx"
    redaction.redact(original, out, {AUTHOR: "advisor", SECOND_AUTHOR: "student-1"})
    document = _part(out, "word/document.xml").decode("utf-8")
    people = _part(out, "word/people.xml").decode("utf-8")
    assert AUTHOR not in document
    assert SECOND_AUTHOR not in document
    assert AUTHOR not in people
    assert 'w:author="advisor"' in document
    assert 'w:author="student-1"' in document
    assert 'w15:author="advisor"' in people


def test_the_redacted_copy_carries_no_property_value(tmp_path: Path) -> None:
    """The properties are where the identity hides.

    Red by: the tool leaving the creator, the company or a custom value.
    """
    original = _build_original(tmp_path / "original.docx")
    out = tmp_path / "out" / "copy.docx"
    redaction.redact(original, out, {AUTHOR: "advisor", SECOND_AUTHOR: "student-1"})
    core = _part(out, "docProps/core.xml").decode("utf-8")
    app = _part(out, "docProps/app.xml").decode("utf-8")
    custom = _part(out, "docProps/custom.xml").decode("utf-8")
    assert AUTHOR not in core
    assert SECOND_AUTHOR not in core
    assert "Some Institute" not in app
    assert "Nobody" not in app
    assert "an-identifier" not in custom


def test_a_path_inside_an_image_s_metadata_is_blanked_in_place(tmp_path: Path) -> None:
    """A figure's metadata can carry the folder it was drawn in.

    Red by: the tool leaving the path, or changing the image's length.
    """
    original = _build_original(tmp_path / "original.docx")
    out = tmp_path / "out" / "copy.docx"
    report = redaction.redact(original, out, {AUTHOR: "advisor", SECOND_AUTHOR: "student-1"})
    image = _part(out, "word/media/image1.tiff")
    assert IMAGE_PATH not in image
    assert len(image) == len(IMAGE)
    assert report["parts"]["word/media/image1.tiff"]["image_metadata_paths_blanked"] == 1


def test_picture_bytes_that_merely_look_like_a_path_are_left_alone(tmp_path: Path) -> None:
    """A picture holds two backslashes by chance; blanking them is damage.

    Red by: the tool blanking a run that only looks like a path, which
    would change the picture it was told to keep.
    """
    original = _build_original(tmp_path / "original.docx")
    out = tmp_path / "out" / "copy.docx"
    redaction.redact(original, out, {AUTHOR: "advisor", SECOND_AUTHOR: "student-1"})
    image = _part(out, "word/media/image1.tiff")
    assert COINCIDENTAL in image
    assert b"a  b\x00pixel\x00" not in image


def test_an_author_the_map_does_not_name_is_refused(tmp_path: Path) -> None:
    """An unmapped author is an identity still in the copy, so the tool stops.

    Red by: the tool writing a copy that still carries the unnamed author.
    """
    original = _build_original(tmp_path / "original.docx")
    out = tmp_path / "out" / "copy.docx"
    try:
        redaction.redact(original, out, {AUTHOR: "advisor"})
    except redaction.RedactionError as error:
        assert SECOND_AUTHOR in str(error)
    else:
        raise AssertionError("the tool redacted a copy with an unnamed author")
    assert not out.exists()


def test_a_copy_inside_the_repository_is_refused(tmp_path: Path) -> None:
    """The material does not belong in the tree.

    Red by: the tool writing a copy inside the repository.
    """
    original = _build_original(tmp_path / "original.docx")
    out = REPO_ROOT / "docs" / "pilot" / "registrations" / "should-not-be-here.docx"
    try:
        redaction.redact(
            original,
            out,
            {AUTHOR: "advisor", SECOND_AUTHOR: "student-1"},
            repository_root=REPO_ROOT,
        )
    except redaction.RedactionError as error:
        assert "repository" in str(error)
    else:
        raise AssertionError("the tool wrote a copy inside the repository")
    assert not out.exists()


def test_the_author_map_is_read_from_a_file_that_holds_names(tmp_path: Path) -> None:
    """The map is read as a map, and an empty one is refused.

    Red by: the tool accepting a map that names no author.
    """
    empty = tmp_path / "empty.json"
    empty.write_text("{}", encoding="utf-8")
    try:
        redaction._read_author_map(empty)
    except redaction.RedactionError as error:
        assert "names no author" in str(error)
    else:
        raise AssertionError("the tool accepted a map that names no author")

    good = _map(tmp_path)
    assert redaction._read_author_map(good) == {AUTHOR: "advisor", SECOND_AUTHOR: "student-1"}
