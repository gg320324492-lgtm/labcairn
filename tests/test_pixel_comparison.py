"""The picture comparison, watched.

**What this file watches.** ``scripts/pilot_picture_comparison.py`` reads the
pilot's desensitised copy and the original it was derived from, decodes
each document's pictures and reports whether the two decode to the same
pixels. The acceptance record
(``docs/acceptance/LC-P4-PILOT-desensitisation-measurement-2026-11-25.md``)
carries that reading and says that the tool that took it was not in the
repository; this file watches the tool that is.

So the properties witnessed here are:

- two documents whose pictures decode to the same pixels are reported as
  identical;
- a copy whose picture lost a single pixel is reported as differing, with
  the count of the pixels that differ -- and the count is of pixels, not of
  bytes;
- a copy whose picture's *metadata* was blanked -- the bytes differ, the
  pixels do not -- is reported as identical, because the reading is about
  pixels, and a tool that compared bytes would get this one wrong;
- a picture the decoder refuses is named with the reason it was refused,
  counted as not read, and never reported as identical;
- the report carries no picture's content;
- the pictures are paired in the order the body shows them, and a picture
  one document has and the other does not is reported on its own;
- the reader's own decoder reads a PNG and an LZW TIFF back to their exact
  pixels, including the TIFF that carries the horizontal-differencing
  predictor, and reads an LZW stream whose table grows past 1023 entries
  at the widths libtiff wrote them at.

**The fixtures are not the reader's own work.** The PNG and the TIFFs below
were written by an independent implementation -- Pillow's zlib writer and
its libtiff writer -- and the pixels they hold are written out as literals
or named by their digest, so the reader is checked against something other
than itself. The PNG that Pillow wrote uses the Sub and Paeth filters, the
LZW TIFF is libtiff's own encoding, and the LZW stream whose table grows
past 1023 entries is libtiff's too. The predictor fixture's compressed
strip is libtiff's; the predictor is the reader's to undo.

**The witnesses must fail for the property.** Each test below names what it
would take to make it red, and none of them is red for a reason unrelated
to the property it watches.

**Nothing here touches the real material.** Every document here is built in
a temporary directory out of synthetic parts; the documents the tool is
pointed at in production live outside this checkout.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import io
import json
import struct
import sys
import zipfile
import zlib
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "pilot_picture_comparison.py"

_spec = importlib.util.spec_from_file_location("pilot_picture_comparison_under_test", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None, (
    "scripts/pilot_picture_comparison.py could not be loaded as a module"
)
comparison: ModuleType = importlib.util.module_from_spec(_spec)
# A dataclass looks its own module up in ``sys.modules`` while the class is
# being built, so the module is registered before it is executed.
sys.modules[_spec.name] = comparison
_spec.loader.exec_module(comparison)
main = comparison.main

#: A sentence that is in a picture's pixels and in nothing else. If it turns
#: up in the report, the report is holding content.
CONTENT_MARKER = b"PICTURE-CONTENT-MUST-NOT-REACH-THE-REPORT-4b17"

#: A PNG written by an independent implementation (Pillow's zlib writer).
#: It uses the Sub and Paeth filters.
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAGCAIAAABxZ0isAAAAKklEQVR4nGNkYGBQ5caCWBhZGRhZmTERXIINDSFLcCIj"
    "NAkeOMKU4IcgACJaA1VRh9BSAAAAAElFTkSuQmCC"
)

#: The pixels that PNG holds, as literals.
PNG_PIXELS = bytes.fromhex(
    "000000250b004a16006f2100942c00b93700de4200034d000105002610034b1b0670260995310cba3c0fdf471204"
    "5215020a002715064c200c712b12963618bb411ee04c2405572a030f00281a094d251272301b973b24bc462de151"
    "36065c3f041400291f0c4e2a18733524984030bd4b3ce256480761540519002a240f4f2f1e743a2d99453cbe504b"
    "e35b5a086669"
)

#: An LZW TIFF written by an independent implementation (libtiff, through
#: Pillow's writer).
LZW_TIFF_BYTES = base64.b64decode(
    "SUkqAKwAAACAACBCUFgAlBYAG8QgBKCwALkbgBvEIAAMmgAAgUACYIAMlhsDHATAlKjEGLoeA9vkcJAQpBUBAoACcKgY"
    "mCAGHEVhJLDYMLsgh5wEwSAUrioBg8ACgNAkmiUJHIYBtLjsSLwjC1wlEbAYuD8CBQACkPgwnCoMHMaiRMEAYL0ljxxF"
    "YkAcwlQChkACoSA8ni8PHQdC1MkUeL4oEtxlstAgzGmAgAoAAAEDAAEAAAAIAAAAAQEDAAEAAAAGAAAAAgEDAAMAAAAq"
    "AQAAAwEDAAEAAAAFAAAABgEDAAEAAAACAAAAEQEEAAEAAAAIAAAAFQEDAAEAAAADAAAAFgEDAAEAAAAGAAAAFwEEAAEA"
    "AACkAAAAHAEDAAEAAAABAAAAAAAAAAgACAAIAA=="
)

#: The pixels that LZW TIFF holds, as literals.
LZW_TIFF_PIXELS = bytes.fromhex(
    "000000250b004a16006f2100942c00b93700de4200034d000105002610034b1b0670260995310cba3c0fdf471204"
    "5215020a002715064c200c712b12963618bb411ee04c2405572a030f00281a094d251272301b973b24bc462de151"
    "36065c3f041400291f0c4e2a18733524984030bd4b3ce256480761540519002a240f4f2f1e743a2d99453cbe504b"
    "e35b5a086669"
)

#: A TIFF whose strip was compressed by libtiff and whose predictor is the
#: horizontal differencing the reader has to undo.
PREDICTOR_TIFF_BYTES = base64.b64decode(
    "SUkqAAgAAAALAAABBAABAAAACAAAAAEBBAABAAAABgAAAAIBAwADAAAAkgAAAAMBAwABAAAABQAAAAYBAwABAAAAAgAA"
    "ABEBBAABAAAAmAAAABUBAwABAAAAAwAAABYBBAABAAAABgAAABcBBAABAAAATgAAABwBAwABAAAAAQAAAD0BAwABAAAA"
    "AgAAAAAAAAAIAAgACACAACBCUFgCCQaCweFQmCgECwgBwSIguJxWJRIBAqEAaCRwFx6QR2OgMHwgEwSTguUyuUSgCBSE"
    "AyCTIFzSbTOZgUMwgHwSeguf0GfT6Ag="
)

#: The pixels that predictor TIFF holds, as literals.
PREDICTOR_TIFF_PIXELS = bytes.fromhex(
    "000000250b004a16006f2100942c00b93700de4200034d000105002610034b1b0670260995310cba3c0fdf471204"
    "5215020a002715064c200c712b12963618bb411ee04c2405572a030f00281a094d251272301b973b24bc462de151"
    "36065c3f041400291f0c4e2a18733524984030bd4b3ce256480761540519002a240f4f2f1e743a2d99453cbe504b"
    "e35b5a086669"
)

#: A greyscale TIFF whose strip was compressed by libtiff and whose table
#: grows past 511 and 1023 entries, so the codes are read at more than one
#: width. The pixels it holds are not written out; they are named by their
#: length and their digest, which is what the repository holds.
LZW_WIDTH_TIFF_BYTES = base64.b64decode(
    "SUkqAAgAAAALAAABBAABAAAAQAAAAAEBBAABAAAAIAAAAAIBAwADAAAAkgAAAAMBAwABAAAABQAAAAYBAwABAAAAAQAA"
    "ABEBBAABAAAAmAAAABUBAwABAAAAAQAAABYBBAABAAAAIAAAABcBBAABAAAAxwIAABwBAwABAAAAAQAAAD0BAwABAAAA"
    "AQAAAAAAAAAIAAgACACAAMBgAAAIBAEBAABwcAwKDQ0AAGCwuDQqEw2GAGEQuBQOPRKJRyFSKDQeHwiNQuFRiHQSBwcB"
    "w2JRGEy6CSiNSOSwSKxSCxOYz+g0KITKFxoBQ6cSekzGYTmDUehwOVwqgTGZzKrUmGx2kzeNzehQyk1yE1+a02EwOQRu"
    "ZzaS1yOUWqVaEWWKSqXSeJ12PzyX2ukV211GI0eVxCGSqXy6qUiz3OLyqUwiLWy42DNY2ySWc3mWUiRYqDz+kQWswSRx"
    "jSU6YXnPW6eVvF6qK2vV2mUXWJ3iuSG1RGcyCR6rUzm98LF4TkSmC3KaZaTU3d37cTSBRGxcKjbbLRjY6WISPs6yoxyT"
    "dinaiscit3qq0a3zep4eIeiQQLv42NUbFv0lbIomnierIqCQuGo7dto/UEPYrD6KgnawukrquuenyYrmhyLs8p7FJS6a"
    "sMQxLSqe2C8OQtSNte1TUP6naXOqwSxQ0lLyuawKoruxy7x4zCLuE2z2xs4sAOkyiyp2jySQ+rzdtKqiHwwir3Qgw8Rv"
    "67ThKDJ7Ju9F6rOwnS1o67SHJ8/LFJVKrXMrMq2vI+EuPEsqgNQ4rINvD88qFO6tokr6wRa/zorfE6nKGorjQ4wyKLbJ"
    "6MRerSGNXNy1NrM6asw6KKpvArRP4s6np1SLrOc7DiRKuTXruqSfL2jKZIeyaRPI0rns/RzUo6tlb1nEK6qPKqzvG8D2"
    "TrYDnphZFJJWySHqdSVh168CqUa0Dxqek7GK/HEovPBDMUSizCu/La2w++UA3LWsI2rDUU2YxKZRui0YL5ILvstT70Nd"
    "PEzxvBTHr0qTDWK0EMQHZkbOBc62MelDgtQ37uUDB9+zPPKOPQ6kl21EFhtvDK2RvEzt4lXslMXTzCuzDSaK5ikpvgj1"
    "aMfOF7o+/E7JC7TBUFMWHJ5Ndw27FMHZ9JcuJo7io1oAKAg="
)

#: How many pixels that TIFF holds.
LZW_WIDTH_TIFF_PIXEL_COUNT = 2048

#: The digest of those pixels.
LZW_WIDTH_TIFF_DIGEST = "bd73a4231f6bbe2e51ce8d5dcfb9302aaad5672e28c4582f2d73fb79e39a24f1"

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PIC_NS = "http://schemas.openxmlformats.org/drawingml/2006/picture"
PKG_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _run(*arguments: str) -> tuple[int, str, str]:
    """Run the tool the way its callers do, and read its status separately."""
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(arguments))
    return code, out.getvalue(), err.getvalue()


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    """One PNG chunk: its length, its kind, its payload and its checksum."""
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _png(
    width: int,
    height: int,
    samples: bytes,
    *,
    channels: int = 4,
    colour_type: int = 6,
    depth: int = 8,
    text: bytes = b"",
) -> bytes:
    """A PNG of the given samples, with one unfiltered row each.

    The rows carry the PNG's "none" filter, which is the one filter that
    needs no undoing; the reader's other filters are watched against the
    fixtures above.
    """
    stride = width * channels
    raw = bytearray()
    for row in range(height):
        raw.append(0)
        raw += samples[row * stride : (row + 1) * stride]
    header = struct.pack(">IIBBBBB", width, height, depth, colour_type, 0, 0, 0)
    parts = [b"\x89PNG\r\n\x1a\n", _png_chunk(b"IHDR", header)]
    if text:
        parts.append(_png_chunk(b"tEXt", text))
    parts.append(_png_chunk(b"IDAT", zlib.compress(bytes(raw))))
    parts.append(_png_chunk(b"IEND", b""))
    return b"".join(parts)


def _png_with_filter(
    kind: int, width: int, height: int, samples: bytes, channels: int = 4
) -> bytes:
    """A PNG whose every row carries the given filter.

    The filters are the PNG's own: Sub against the pixel to the left, Up
    against the row above, Average against both, and Paeth against the
    nearest of the three. They are written here from the format's
    definition, and the reader undoes them.
    """
    stride = width * channels
    raw = bytearray()
    prior = bytes(stride)
    for row in range(height):
        line = samples[row * stride : (row + 1) * stride]
        raw.append(kind)
        for index in range(stride):
            left = line[index - channels] if index >= channels else 0
            up = prior[index]
            upper_left = prior[index - channels] if index >= channels else 0
            if kind == 0:
                value = line[index]
            elif kind == 1:
                value = (line[index] - left) % 256
            elif kind == 2:
                value = (line[index] - up) % 256
            elif kind == 3:
                value = (line[index] - ((left + up) >> 1)) % 256
            else:
                estimate = left + up - upper_left
                distance_left = abs(estimate - left)
                distance_up = abs(estimate - up)
                distance_upper_left = abs(estimate - upper_left)
                if distance_left <= distance_up and distance_left <= distance_upper_left:
                    nearest = left
                elif distance_up <= distance_upper_left:
                    nearest = up
                else:
                    nearest = upper_left
                value = (line[index] - nearest) % 256
            raw.append(value)
        prior = line
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(bytes(raw)))
        + _png_chunk(b"IEND", b"")
    )


def _document_xml(order: list[str]) -> str:
    """A body that shows the named pictures, in the named order."""
    body = ""
    for identifier in order:
        body += (
            "<w:p><w:r><w:drawing><a:graphic><a:graphicData><pic:pic><pic:blipFill>"
            f'<a:blip r:embed="{identifier}"/></pic:blipFill></pic:pic>'
            "</a:graphicData></a:graphic></w:drawing></w:r></w:p>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{W_NS}" xmlns:a="{A_NS}" xmlns:r="{R_NS}" xmlns:pic="{PIC_NS}">'
        f"<w:body>{body}</w:body></w:document>"
    )


def _relationships_xml(pictures: list[tuple[str, str]], in_full: bool = False) -> str:
    """The document's relationships: an id and the part it points at.

    The target is written the way Word writes it -- relative to the part
    that holds it, so a picture in ``word/media`` is named
    ``media/image1.png``. Some writers name the part in full instead, so
    that spelling is available here too.
    """
    entries = ""
    for identifier, part in pictures:
        target = part if in_full else part.removeprefix("word/")
        entries += f'<Relationship Id="{identifier}" Type="{R_NS}/image" Target="{target}"/>'
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{PKG_NS}">{entries}</Relationships>'
    )


def _docx(
    path: Path,
    pictures: list[tuple[str, bytes]],
    order: list[str] | None = None,
    targets_in_full: bool = False,
) -> Path:
    """A document whose parts are written out one by one.

    It is not a Word file a Word would open without complaint; it is the
    parts the tool reads, and nothing else. The tool reads the archive, so
    that is what a witness of the tool needs.

    ``pictures`` is a list of (media part name, bytes). The body shows the
    pictures in the order given, unless ``order`` names the relationship
    identifiers to show instead.
    """
    identifiers = [f"rId{index + 1}" for index in range(len(pictures))]
    parts: dict[str, bytes] = {
        "word/document.xml": _document_xml(order if order is not None else identifiers).encode(),
        "word/_rels/document.xml.rels": _relationships_xml(
            list(zip(identifiers, [name for name, _ in pictures], strict=True)), targets_in_full
        ).encode(),
    }
    for name, data in pictures:
        parts[name] = data
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in parts.items():
            archive.writestr(name, data)
    return path


def test_two_documents_whose_pictures_are_the_same_are_reported_as_identical(
    tmp_path: Path,
) -> None:
    """The reading the record rests on: the same picture on both sides.

    The tool would go red here if the comparison stopped being about the
    pictures -- if it reported a difference for two pictures that are the
    same, or if the status stopped being ``0`` when everything matched.
    """
    picture = _png(4, 3, bytes(range(48)))
    copy = _docx(tmp_path / "copy.docx", [("word/media/image1.png", picture)])
    original = _docx(tmp_path / "original.docx", [("word/media/image1.png", picture)])
    code, out, _ = _run("--copy", str(copy), "--original", str(original))
    assert code == 0, out
    assert "pixels identical" in out
    assert "bytes same" in out
    assert "pictures: 1 compared, 1 identical, 0 differing, 0 not read" in out


def test_a_copy_whose_picture_lost_one_pixel_is_reported_as_differing(
    tmp_path: Path,
) -> None:
    """One pixel that changed is a difference, and the count is one.

    The tool would go red here if the comparison were blind to a changed
    pixel, or if the count of the differing pixels were not reported.
    """
    samples = bytearray(range(48))
    picture = _png(4, 3, bytes(samples))
    changed = bytearray(samples)
    changed[10] = 255
    copy = _docx(tmp_path / "copy.docx", [("word/media/image1.png", _png(4, 3, bytes(changed)))])
    original = _docx(tmp_path / "original.docx", [("word/media/image1.png", picture)])
    code, out, _ = _run("--copy", str(copy), "--original", str(original))
    assert code == 1, out
    assert "pixels differ by 1 pixel(s)" in out
    assert "pictures: 1 compared, 0 identical, 1 differing, 0 not read" in out


def test_the_count_of_differing_pixels_counts_pixels_and_not_bytes(
    tmp_path: Path,
) -> None:
    """A pixel whose three channels all differ is still one pixel.

    The tool would go red here if the count were a count of bytes, which
    is the mistake a reader would make reading "3" where the answer is
    "one pixel".
    """
    samples = bytearray(range(48))
    picture = _png(4, 3, bytes(samples))
    changed = bytearray(samples)
    # The first pixel's four channels -- one pixel, three channels changed.
    changed[0] = 255
    changed[1] = 254
    changed[2] = 253
    # And one channel of a second pixel, in the second row.
    changed[20] = 0
    copy = _docx(tmp_path / "copy.docx", [("word/media/image1.png", _png(4, 3, bytes(changed)))])
    original = _docx(tmp_path / "original.docx", [("word/media/image1.png", picture)])
    code, out, _ = _run("--copy", str(copy), "--original", str(original))
    assert code == 1, out
    assert "pixels differ by 2 pixel(s)" in out


def test_a_copy_whose_picture_metadata_was_blanked_is_reported_as_the_same_pixels(
    tmp_path: Path,
) -> None:
    """The bytes differ and the pixels do not, and the reading says pixels.

    This is the case the record's reading turns on: the redaction blanked
    a path inside a picture's own metadata, in place and at the same
    length, so the two pictures' bytes differ where the two pictures'
    pixels do not. A tool that compared bytes would report these pictures
    as different, which is true of the bytes and false of the pictures.

    The tool would go red here if the comparison were a comparison of
    bytes.
    """
    samples = bytes(range(48))
    picture = _png(4, 3, samples)
    blanked = _png(4, 3, samples, text=b"Software\x00C:\\Users\\somebody\\drawing.tif")
    assert picture != blanked
    copy = _docx(tmp_path / "copy.docx", [("word/media/image1.png", blanked)])
    original = _docx(tmp_path / "original.docx", [("word/media/image1.png", picture)])
    code, out, _ = _run("--copy", str(copy), "--original", str(original))
    assert code == 0, out
    assert "bytes differ" in out
    assert "pixels identical" in out
    assert "pictures: 1 compared, 1 identical, 0 differing, 0 not read" in out


def test_a_picture_the_decoder_refuses_is_named_and_not_reported_as_identical(
    tmp_path: Path,
) -> None:
    """A picture the reader cannot read is a fact to report, not to hide.

    The tool would go red here if a refusal were swallowed -- if the
    picture were reported as identical, or counted as read, or left out of
    the report altogether.
    """
    picture = _png(4, 3, bytes(range(48)), depth=16)
    copy = _docx(tmp_path / "copy.docx", [("word/media/image1.png", picture)])
    original = _docx(tmp_path / "original.docx", [("word/media/image1.png", picture)])
    code, out, _ = _run("--copy", str(copy), "--original", str(original))
    assert code == 1, out
    assert "not decoded" in out
    assert "16-bit PNG is refused" in out
    assert "pictures: 1 compared, 0 identical, 0 differing, 1 not read" in out
    assert "pixels identical" not in out


def test_a_picture_in_a_format_the_reader_does_not_read_is_named(
    tmp_path: Path,
) -> None:
    """A picture that is not a picture at all is refused by name.

    The tool would go red here if an undecodable picture were passed over
    silently rather than reported with the reason.
    """
    picture = b"\xff\xd8\xff\xe0 not a picture at all"
    copy = _docx(tmp_path / "copy.docx", [("word/media/image1.jpg", picture)])
    original = _docx(tmp_path / "original.docx", [("word/media/image1.jpg", picture)])
    code, out, _ = _run("--copy", str(copy), "--original", str(original))
    assert code == 1, out
    assert "not decoded" in out
    assert "format the decoder does not read" in out


def test_the_report_carries_no_picture_content(tmp_path: Path) -> None:
    """The report is counts, booleans and digests; the picture stays outside it.

    The tool would go red here if any part of a picture reached the report
    -- a sample, a row, sixteen bytes of the picture's pixels in any
    spelling.
    """
    samples = CONTENT_MARKER + bytes(range(100))
    picture = _png(12, 3, samples)
    copy = _docx(tmp_path / "copy.docx", [("word/media/image1.png", picture)])
    original = _docx(tmp_path / "original.docx", [("word/media/image1.png", picture)])
    code, out, _ = _run("--copy", str(copy), "--original", str(original))
    assert code == 0, out
    for start in range(len(samples) - 15):
        window = samples[start : start + 16]
        assert window.decode() not in out, f"the report holds bytes {start}..{start + 15}"
        assert window.hex() not in out, f"the report holds bytes {start}..{start + 15}"


def test_the_report_names_the_decoder_and_says_what_it_cannot_do(
    tmp_path: Path,
) -> None:
    """A reader has to know what read the pixels before believing them.

    The tool would go red here if the report stopped naming the decoder,
    or stopped saying what the decoder refuses.
    """
    picture = _png(4, 3, bytes(range(48)))
    copy = _docx(tmp_path / "copy.docx", [("word/media/image1.png", picture)])
    original = _docx(tmp_path / "original.docx", [("word/media/image1.png", picture)])
    _, out, _ = _run("--copy", str(copy), "--original", str(original))
    assert "decoder:" in out
    assert "zlib" in out
    assert "refuses:" in out
    assert "BigTIFF" in out


def test_the_pictures_are_paired_in_the_order_the_body_shows_them(
    tmp_path: Path,
) -> None:
    """The first picture of the copy is read against the first of the original.

    The two documents here show their pictures in opposite orders, and the
    names of their parts are in the archive's order rather than the body's,
    so a tool that paired by name would pair different pictures. The
    reading is about the figures a reader counts, and the figures are
    counted as the body shows them.

    The tool would go red here if the pictures were paired by the
    archive's order rather than the body's.
    """
    first = _png(4, 3, bytes(range(48)))
    second = _png(4, 3, bytes(range(48, 96)))
    # The copy shows the second picture first; the original shows the first.
    copy = _docx(
        tmp_path / "copy.docx",
        [("word/media/image1.png", first), ("word/media/image2.png", second)],
        order=["rId2", "rId1"],
    )
    original = _docx(
        tmp_path / "original.docx",
        [("word/media/image1.png", second), ("word/media/image2.png", first)],
        order=["rId1", "rId2"],
    )
    code, out, _ = _run("--copy", str(copy), "--original", str(original))
    assert code == 0, out
    first_row = next(line for line in out.splitlines() if line.startswith("picture 1"))
    assert "copy word/media/image2.png" in first_row
    assert "original word/media/image1.png" in first_row
    assert "pixels identical" in first_row
    assert "pictures: 2 compared, 2 identical, 0 differing, 0 not read" in out


def test_a_relationship_that_names_the_part_in_full_is_still_read(
    tmp_path: Path,
) -> None:
    """A writer that names the part in full is read the same way.

    The tool would go red here if the target were resolved only one way:
    the pictures would fall back to the archive's order and the pairing
    would be about different pictures.
    """
    first = _png(4, 3, bytes(range(48)))
    second = _png(4, 3, bytes(range(48, 96)))
    copy = _docx(
        tmp_path / "copy.docx",
        [("word/media/image1.png", first), ("word/media/image2.png", second)],
        order=["rId2", "rId1"],
        targets_in_full=True,
    )
    original = _docx(
        tmp_path / "original.docx",
        [("word/media/image1.png", second), ("word/media/image2.png", first)],
        order=["rId1", "rId2"],
        targets_in_full=True,
    )
    code, out, _ = _run("--copy", str(copy), "--original", str(original))
    assert code == 0, out
    first_row = next(line for line in out.splitlines() if line.startswith("picture 1"))
    assert "copy word/media/image2.png" in first_row
    assert "original word/media/image1.png" in first_row
    assert "pixels identical" in first_row


def test_a_picture_only_the_copy_has_is_reported_on_its_own(tmp_path: Path) -> None:
    """A picture one document has and the other does not is not passed over.

    The tool would go red here if the extra picture were dropped from the
    report, or if a document with an extra picture were reported as
    identical.
    """
    picture = _png(4, 3, bytes(range(48)))
    copy = _docx(
        tmp_path / "copy.docx",
        [("word/media/image1.png", picture), ("word/media/image2.png", picture)],
    )
    original = _docx(tmp_path / "original.docx", [("word/media/image1.png", picture)])
    code, out, _ = _run("--copy", str(copy), "--original", str(original))
    assert code == 1, out
    assert "only in the copy: word/media/image2.png" in out
    assert "pictures: 1 compared, 1 identical, 0 differing, 0 not read" in out


def test_the_tool_refuses_a_file_that_is_not_an_archive(tmp_path: Path) -> None:
    """A file that is not a document is refused, not measured.

    The tool would go red here if the refusal were swallowed and the tool
    reported a comparison of nothing.
    """
    not_an_archive = tmp_path / "not-a-document.docx"
    not_an_archive.write_bytes(b"this is not a document")
    picture = _png(4, 3, bytes(range(48)))
    original = _docx(tmp_path / "original.docx", [("word/media/image1.png", picture)])
    code, out, _ = _run("--copy", str(not_an_archive), "--original", str(original))
    assert code == 2, out
    assert "is not a document archive" in out


def test_the_reader_reads_a_png_back_to_its_exact_pixels() -> None:
    """The reader reads the PNG an independent writer wrote.

    The tool would go red here if the reader's filters were wrong: the
    fixture is Pillow's PNG, and it carries the Sub and Paeth filters.
    """
    decoded = comparison.decode_picture(PNG_BYTES)
    assert decoded.width == 8
    assert decoded.height == 6
    assert decoded.channels == 3
    assert decoded.samples == PNG_PIXELS


def test_the_reader_reads_an_lzw_tiff_back_to_its_exact_pixels() -> None:
    """The reader reads the LZW TIFF libtiff wrote.

    The tool would go red here if the reader's LZW were wrong -- if the
    codes were read at the wrong width, or the table grew at the wrong
    moment. The fixture is libtiff's own encoding.
    """
    decoded = comparison.decode_picture(LZW_TIFF_BYTES)
    assert decoded.width == 8
    assert decoded.height == 6
    assert decoded.channels == 3
    assert decoded.samples == LZW_TIFF_PIXELS


def test_the_reader_undoes_the_horizontal_differencing_predictor() -> None:
    """The reader undoes the predictor a TIFF's encoder applied.

    The tool would go red here if the predictor were not undone, or undone
    wrongly: the fixture's pixels are the ones the encoder started from.
    """
    decoded = comparison.decode_picture(PREDICTOR_TIFF_BYTES)
    assert decoded.width == 8
    assert decoded.height == 6
    assert decoded.channels == 3
    assert decoded.samples == PREDICTOR_TIFF_PIXELS


def test_the_reader_follows_the_lzw_width_rule() -> None:
    """The reader reads the codes at the widths libtiff wrote them at.

    A short LZW stream never grows its table past the first width, so it
    cannot tell a reader that reads every code at nine bits from a reader
    that widens them on time. This fixture's table grows past 511 and past
    1023 entries, so the codes are read at three widths; the pixels it
    holds are named by their length and their digest.

    The tool would go red here if the table were made to grow one code
    late, or one code early.
    """
    decoded = comparison.decode_picture(LZW_WIDTH_TIFF_BYTES)
    assert decoded.width == 64
    assert decoded.height == 32
    assert decoded.channels == 1
    assert len(decoded.samples) == LZW_WIDTH_TIFF_PIXEL_COUNT
    assert hashlib.sha256(decoded.samples).hexdigest() == LZW_WIDTH_TIFF_DIGEST


def test_the_reader_undoes_every_png_filter() -> None:
    """The reader undoes each of the PNG's five filters.

    The tool would go red here for any one filter the reader got wrong:
    the five are written into the picture here and read back.
    """
    samples = bytes((index * 37 + 11) % 256 for index in range(64))
    for kind in (0, 1, 2, 3, 4):
        picture = _png_with_filter(kind, 4, 4, samples)
        decoded = comparison.decode_picture(picture)
        assert decoded.samples == samples, f"filter {kind} was not undone"


def test_the_json_report_carries_the_same_readings_as_the_text(tmp_path: Path) -> None:
    """The report a record quotes can be written down as data.

    The tool would go red here if the JSON and the text disagreed about a
    reading, or if the JSON left the pictures' digests out.
    """
    picture = _png(4, 3, bytes(range(48)))
    copy = _docx(tmp_path / "copy.docx", [("word/media/image1.png", picture)])
    original = _docx(tmp_path / "original.docx", [("word/media/image1.png", picture)])
    target = tmp_path / "report.json"
    code, out, _ = _run("--copy", str(copy), "--original", str(original), "--json", str(target))
    assert code == 0, out
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["summary"]["compared"] == 1
    assert written["summary"]["identical"] == 1
    assert written["summary"]["all_identical"] is True
    assert written["pictures"][0]["pixels_identical"] is True
    assert written["pictures"][0]["width"] == 4
    assert written["pictures"][0]["height"] == 3
    assert len(written["copy"]["sha256"]) == 64
    assert len(written["original"]["sha256"]) == 64
    assert written["decoder"]
    assert written["limits"]
