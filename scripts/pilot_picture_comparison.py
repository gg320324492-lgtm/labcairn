"""Compare the pictures in two documents by decoded pixels.

**What this is for.** The pilot's desensitisation record
(``docs/acceptance/LC-P4-PILOT-desensitisation-measurement-2026-11-25.md``)
says that the redacted copy's seven pictures decode to the same pixels as
the original's, and it says in the same breath that the reading was taken by
a one-off script that is not in the repository -- so a later reader cannot
repeat it.  The record's own next sentence is that the character count *is*
reported by a tool that is in the repository and can be read again.  The
pixel comparison was the one reading left without a tool.

This is that tool.  It takes the copy and the original, reads the pictures
out of both archives, decodes each one, and reports per picture whether the
two decode to the same pixels.

**Why pixels and not bytes.** The redaction blanked a path inside a
picture's own metadata, in place and at the same length, so the copy's bytes
and the original's bytes differ where the picture's pixels do not.  A tool
that compared bytes would report those pictures as different -- which is
true of the bytes and false of the pictures.  The reading this record needs
is about the pictures, so the comparison is over decoded pixels.  The report
still says whether the bytes were the same, because that is the fact that
tells a reader *why* the pixels have to be compared.

**What it prints.**  The two documents' digests, the decoder's name and its
limits, and then per picture: the size, whether the bytes were the same,
whether the pixels are the same, and how many pixels differ when they are
not.  Counts, booleans and digests.  **It never prints a picture's
content** -- not a sample, not a colour, not a row.  A picture that the
decoder refuses is named with the reason it was refused, because a reading
that quietly passes over the pictures it could not read is a reading nobody
can check.

**What the decoder is.**  The project's declared dependencies carry no image
decoder, so the decoder is the one in this script: ``zlib`` from the
standard library for PNG, and a TIFF 6.0 reader for uncompressed and LZW
strips.  Its limits are stated in the report and are part of the reading:
8-bit PNG that is not interlaced, and 8-bit TIFF in chunky layout with
uncompressed or LZW strips and predictor 1 or 2.  Tiles, BigTIFF, 16-bit
samples and JPEG-in-TIFF are refused, and a picture in any other format is
refused too.  A refusal is a fact about the picture, not a failure of the
tool.

Usage::

    python scripts/pilot_picture_comparison.py \\
        --copy <path> --original <path> [--json OUT.json]

**What the status means.**  ``0`` when every picture in both documents
decoded and every pair is pixel-identical; ``1`` when a picture differs, a
picture could not be decoded, or a picture is in one document and not the
other; ``2`` when the tool could not run at all.  The report is printed in
every case, so the counts can be read whatever the status is.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import struct
import sys
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

#: The decoder's name, as the report states it.  A reader has to know what
#: read the pixels before the reading can be believed.
DECODER_NAME = (
    "the built-in decoder: zlib for PNG, and a TIFF 6.0 reader for uncompressed and LZW strips"
)

#: What the decoder refuses.  These limits are part of the reading, so the
#: report states them rather than leaving a reader to guess.
DECODER_LIMITS = (
    "8-bit PNG that is not interlaced; 8-bit TIFF in chunky layout with "
    "uncompressed or LZW strips and predictor 1 or 2; no tiles, no BigTIFF, "
    "no 16-bit samples, no JPEG-in-TIFF, no other format"
)

#: The relationship namespace Word writes its picture references in.
RELATIONSHIPS_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

#: The PNG colour types and how many samples each one carries.
PNG_CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}

#: The TIFF tag numbers the reader reads.
TIFF_IMAGE_WIDTH = 256
TIFF_IMAGE_LENGTH = 257
TIFF_BITS_PER_SAMPLE = 258
TIFF_COMPRESSION = 259
TIFF_STRIP_OFFSETS = 273
TIFF_SAMPLES_PER_PIXEL = 277
TIFF_ROWS_PER_STRIP = 278
TIFF_STRIP_BYTE_COUNTS = 279
TIFF_PLANAR_CONFIG = 284
TIFF_PREDICTOR = 317
TIFF_TILE_OFFSETS = 324

#: The size of each TIFF field type, in bytes.
TIFF_TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}


class ComparisonRefusedError(Exception):
    """A refusal to compare, with the reason in English."""


class PictureNotDecodedError(Exception):
    """A picture the decoder refuses, with the reason in English."""


@dataclass(frozen=True)
class DecodedPicture:
    """A picture's pixels, as the decoder read them.

    ``samples`` is the raw samples in reading order, row by row, with no
    header and no padding -- the thing two pictures are compared on.
    """

    width: int
    height: int
    channels: int
    samples: bytes


@dataclass(frozen=True)
class PictureComparison:
    """One picture's reading, from both sides."""

    index: int
    copy_part: str
    original_part: str
    width: int | None
    height: int | None
    channels: int | None
    bytes_identical: bool
    pixels_identical: bool | None
    differing_pixels: int | None
    not_decoded: str | None
    note: str | None


@dataclass(frozen=True)
class DocumentComparison:
    """The whole comparison: the two documents, and every picture read."""

    copy_path: str
    copy_digest: str
    original_path: str
    original_digest: str
    pictures: tuple[PictureComparison, ...]
    copy_only: tuple[str, ...]
    original_only: tuple[str, ...]

    @property
    def identical_count(self) -> int:
        """The pictures whose pixels are the same on both sides."""
        return sum(1 for picture in self.pictures if picture.pixels_identical is True)

    @property
    def differing_count(self) -> int:
        """The pictures whose pixels are not the same on both sides."""
        return sum(1 for picture in self.pictures if picture.pixels_identical is False)

    @property
    def undecoded_count(self) -> int:
        """The pictures the decoder could not read."""
        return sum(1 for picture in self.pictures if picture.pixels_identical is None)

    @property
    def all_identical(self) -> bool:
        """Whether every picture in both documents was read and matched.

        A document with no pictures at all is not "identical": nothing was
        compared, so nothing was established.
        """
        return (
            bool(self.pictures)
            and not self.copy_only
            and not self.original_only
            and all(picture.pixels_identical is True for picture in self.pictures)
        )


def _digest(path: Path) -> str:
    """The file's sha256, read in blocks so a large document is not held."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _undo_png_filters(raw: bytes, height: int, stride: int, step: int) -> bytes:
    """Undo the PNG's per-row filters, returning the samples in reading order.

    The PNG format filters each row against the row above it and against
    its own left neighbour; the filters have to be undone in that order or
    the pixels come out as noise.
    """
    out = bytearray()
    prior = bytes(stride)
    position = 0
    for _ in range(height):
        if position >= len(raw):
            raise PictureNotDecodedError("the PNG's picture data stops in the middle of a row")
        kind = raw[position]
        position += 1
        line = bytearray(raw[position : position + stride])
        position += stride
        if len(line) < stride:
            raise PictureNotDecodedError("a PNG row is shorter than its width says")
        if kind == 0:
            pass
        elif kind == 1:
            for index in range(step, stride):
                line[index] = (line[index] + line[index - step]) & 0xFF
        elif kind == 2:
            for index in range(stride):
                line[index] = (line[index] + prior[index]) & 0xFF
        elif kind == 3:
            for index in range(stride):
                left = line[index - step] if index >= step else 0
                line[index] = (line[index] + ((left + prior[index]) >> 1)) & 0xFF
        elif kind == 4:
            for index in range(stride):
                left = line[index - step] if index >= step else 0
                up = prior[index]
                upper_left = prior[index - step] if index >= step else 0
                estimate = left + up - upper_left
                distance_left = abs(estimate - left)
                distance_up = abs(estimate - up)
                distance_upper_left = abs(estimate - upper_left)
                if distance_left <= distance_up and distance_left <= distance_upper_left:
                    predictor = left
                elif distance_up <= distance_upper_left:
                    predictor = up
                else:
                    predictor = upper_left
                line[index] = (line[index] + predictor) & 0xFF
        else:
            raise PictureNotDecodedError(f"the PNG uses filter {kind}, which is not a filter")
        out += line
        prior = bytes(line)
    return bytes(out)


def _apply_palette(samples: bytes, palette: bytes) -> bytes:
    """Replace a palette picture's indices with the palette's colours."""
    if not palette or len(palette) % 3:
        raise PictureNotDecodedError("the PNG names a palette it does not carry")
    out = bytearray()
    for index in samples:
        entry = index * 3
        if entry + 3 > len(palette):
            raise PictureNotDecodedError(
                "the PNG's picture data names a colour outside its palette"
            )
        out += palette[entry : entry + 3]
    return bytes(out)


def decode_png(data: bytes) -> DecodedPicture:
    """Read a PNG's pixels with the standard library's ``zlib``.

    The reader takes 8-bit pictures that are not interlaced: greyscale,
    truecolour, palette, greyscale with alpha and truecolour with alpha.
    A palette picture with a transparency chunk is refused, because the
    transparency is a colour the reader does not read and two pictures
    could differ in it without the comparison seeing it.
    """
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise PictureNotDecodedError("the bytes do not begin with a PNG signature")
    header: tuple[int, int, int, int, int, int, int] | None = None
    palette = b""
    transparency = b""
    compressed = bytearray()
    offset = 8
    while offset + 8 <= len(data):
        length = int(struct.unpack(">I", data[offset : offset + 4])[0])
        kind = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if kind == b"IHDR":
            if len(payload) != 13:
                raise PictureNotDecodedError("the PNG header is not thirteen bytes")
            header = struct.unpack(">IIBBBBB", payload)
        elif kind == b"PLTE":
            palette = payload
        elif kind == b"tRNS":
            transparency = payload
        elif kind == b"IDAT":
            compressed += payload
        elif kind == b"IEND":
            break
    if header is None:
        raise PictureNotDecodedError("the PNG carries no header")
    width, height, depth, colour, method, filtering, interlace = header
    if depth != 8:
        raise PictureNotDecodedError(f"a {depth}-bit PNG is refused")
    if interlace != 0:
        raise PictureNotDecodedError("an interlaced PNG is refused")
    if method != 0 or filtering != 0:
        raise PictureNotDecodedError(
            "a PNG with an unknown compression or filter method is refused"
        )
    if colour not in PNG_CHANNELS:
        raise PictureNotDecodedError(f"a PNG of colour type {colour} is refused")
    if transparency:
        raise PictureNotDecodedError("a PNG with a transparency chunk is refused")
    try:
        raw = zlib.decompress(bytes(compressed))
    except zlib.error as error:
        raise PictureNotDecodedError(
            f"the PNG's picture data does not decompress: {error}"
        ) from error
    channels = PNG_CHANNELS[colour]
    stride = width * channels
    if len(raw) < height * (stride + 1):
        raise PictureNotDecodedError("the PNG's picture data is shorter than its header says")
    samples = _undo_png_filters(raw, height, stride, channels)
    if colour == 3:
        samples = _apply_palette(samples, palette)
        channels = 3
    return DecodedPicture(width=width, height=height, channels=channels, samples=samples)


def _lzw_decode(data: bytes) -> bytes:
    """Decode a TIFF's LZW strip.

    The codes are packed most significant bit first and grow from nine bits
    to twelve.  The table grows by one entry for every code after the
    first, and the width grows when the next code to be assigned would be
    511, 1023 or 2047 -- the rule TIFF's own encoder follows, which is one
    code earlier than the rule GIF's does.
    """
    clear = 256
    end = 257
    table = [bytes((index,)) for index in range(256)] + [b"", b""]
    width = 9
    next_code = 258
    previous = -1
    out = bytearray()
    buffer = 0
    bits = 0
    position = 0
    length = len(data)
    while True:
        while bits < width:
            if position >= length:
                return bytes(out)
            buffer = (buffer << 8) | data[position]
            position += 1
            bits += 8
        bits -= width
        code = (buffer >> bits) & ((1 << width) - 1)
        buffer &= (1 << bits) - 1
        if code == end:
            break
        if code == clear:
            table = [bytes((index,)) for index in range(256)] + [b"", b""]
            width = 9
            next_code = 258
            previous = -1
            continue
        if code < 256:
            entry = bytes((code,))
        elif code < next_code:
            entry = table[code]
        elif code == next_code and previous >= 0:
            entry = table[previous] + table[previous][:1]
        else:
            raise PictureNotDecodedError("the LZW stream names a code the table does not hold")
        out += entry
        if previous >= 0:
            table.append(table[previous] + entry[:1])
            next_code += 1
            if next_code == 511:
                width = 10
            elif next_code == 1023:
                width = 11
            elif next_code == 2047:
                width = 12
        previous = code
    return bytes(out)


def _undo_horizontal_differencing(samples: bytes, stride: int, channels: int) -> bytes:
    """Undo TIFF's horizontal differencing predictor.

    Each sample is stored as its difference from the sample to its left;
    the row is rebuilt by running the differences back together.
    """
    out = bytearray(samples)
    for start in range(0, len(out), stride):
        row = out[start : start + stride]
        for index in range(channels, stride):
            row[index] = (row[index] + row[index - channels]) & 0xFF
        out[start : start + stride] = row
    return bytes(out)


@dataclass(frozen=True)
class _TiffField:
    """One field of a TIFF's directory."""

    kind: int
    count: int
    payload: bytes


def _tiff_fields(data: bytes, order: str, offset: int) -> dict[int, _TiffField]:
    """Read the directory at ``offset`` into a map of tag to field."""
    count = int(struct.unpack(order + "H", data[offset : offset + 2])[0])
    fields: dict[int, _TiffField] = {}
    for index in range(count):
        entry = offset + 2 + index * 12
        values = struct.unpack(order + "HHI", data[entry : entry + 8])
        tag = int(values[0])
        kind = int(values[1])
        items = int(values[2])
        size = TIFF_TYPE_SIZES.get(kind, 1) * items
        if size <= 4:
            payload = data[entry + 8 : entry + 8 + size]
        else:
            pointer = int(struct.unpack(order + "I", data[entry + 8 : entry + 12])[0])
            payload = data[pointer : pointer + size]
        fields[tag] = _TiffField(kind=kind, count=items, payload=payload)
    return fields


def _tiff_numbers(field: _TiffField, order: str) -> tuple[int, ...]:
    """A field's values, as numbers."""
    if field.kind == 3:
        return tuple(struct.unpack(order + "H" * field.count, field.payload[: 2 * field.count]))
    if field.kind == 4:
        return tuple(struct.unpack(order + "I" * field.count, field.payload[: 4 * field.count]))
    if field.kind == 1:
        return tuple(field.payload[: field.count])
    raise PictureNotDecodedError(f"a TIFF field of type {field.kind} is not a number")


def _tiff_number(fields: dict[int, _TiffField], tag: int, order: str, default: int) -> int:
    """One field's value, or ``default`` when the field is not there."""
    field = fields.get(tag)
    if field is None:
        return default
    values = _tiff_numbers(field, order)
    if not values:
        return default
    return values[0]


def decode_tiff(data: bytes) -> DecodedPicture:
    """Read a TIFF's pixels: strips, uncompressed or LZW, chunky layout.

    The reader takes 8-bit samples in chunky layout, with the whole picture
    in strips, compressed with nothing at all or with LZW, and with
    predictor 1 (none) or 2 (horizontal differencing).  Tiles, BigTIFF,
    planar layout and every other compression are refused.
    """
    if data[:2] == b"II":
        order = "<"
    elif data[:2] == b"MM":
        order = ">"
    else:
        raise PictureNotDecodedError("the bytes do not begin with a TIFF header")
    if data[2:4] in (b"\x2b\x00", b"\x00\x2b"):
        raise PictureNotDecodedError("a BigTIFF is refused")
    if data[2:4] not in (b"\x2a\x00", b"\x00\x2a"):
        raise PictureNotDecodedError("the TIFF header is not the classic one")
    first = int(struct.unpack(order + "I", data[4:8])[0])
    fields = _tiff_fields(data, order, first)
    if TIFF_TILE_OFFSETS in fields:
        raise PictureNotDecodedError("a tiled TIFF is refused")
    width = _tiff_number(fields, TIFF_IMAGE_WIDTH, order, 0)
    height = _tiff_number(fields, TIFF_IMAGE_LENGTH, order, 0)
    compression = _tiff_number(fields, TIFF_COMPRESSION, order, 0)
    samples = _tiff_number(fields, TIFF_SAMPLES_PER_PIXEL, order, 1)
    planar = _tiff_number(fields, TIFF_PLANAR_CONFIG, order, 1)
    predictor = _tiff_number(fields, TIFF_PREDICTOR, order, 1)
    if width <= 0 or height <= 0:
        raise PictureNotDecodedError("the TIFF does not say how big it is")
    if planar != 1:
        raise PictureNotDecodedError("a TIFF in planar layout is refused")
    if compression not in (1, 5):
        raise PictureNotDecodedError(f"a TIFF compressed with {compression} is refused")
    if predictor not in (1, 2):
        raise PictureNotDecodedError(f"a TIFF with predictor {predictor} is refused")
    bits_field = fields.get(TIFF_BITS_PER_SAMPLE)
    if bits_field is not None:
        bits = _tiff_numbers(bits_field, order)
        if any(bit != 8 for bit in bits):
            raise PictureNotDecodedError("a TIFF that is not 8 bits per sample is refused")
    if samples < 1:
        raise PictureNotDecodedError("the TIFF does not say how many samples a pixel has")
    offsets_field = fields.get(TIFF_STRIP_OFFSETS)
    counts_field = fields.get(TIFF_STRIP_BYTE_COUNTS)
    if offsets_field is None or counts_field is None:
        raise PictureNotDecodedError("the TIFF's strips are not described")
    offsets = _tiff_numbers(offsets_field, order)
    counts = _tiff_numbers(counts_field, order)
    rows_per_strip = _tiff_number(fields, TIFF_ROWS_PER_STRIP, order, height)
    if rows_per_strip <= 0:
        raise PictureNotDecodedError("the TIFF says a strip holds no rows")
    stride = width * samples
    rows_done = 0
    chunks: list[bytes] = []
    for index, offset in enumerate(offsets):
        rows = min(rows_per_strip, height - rows_done)
        if rows <= 0:
            break
        size = counts[index] if index < len(counts) else 0
        chunk = data[offset : offset + size]
        decoded = chunk if compression == 1 else _lzw_decode(chunk)
        wanted = rows * stride
        if len(decoded) < wanted:
            raise PictureNotDecodedError("a strip decodes to fewer samples than its rows need")
        row_bytes = decoded[:wanted]
        if predictor == 2:
            row_bytes = _undo_horizontal_differencing(row_bytes, stride, samples)
        chunks.append(row_bytes)
        rows_done += rows
    if rows_done < height:
        raise PictureNotDecodedError("the TIFF's strips do not cover every row")
    return DecodedPicture(width=width, height=height, channels=samples, samples=b"".join(chunks))


def decode_picture(data: bytes) -> DecodedPicture:
    """Read a picture's pixels, whichever format the bytes are in."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return decode_png(data)
    if data[:2] in (b"II", b"MM"):
        return decode_tiff(data)
    raise PictureNotDecodedError("the bytes are in a format the decoder does not read")


def _relationship_targets(relationships: bytes) -> dict[str, str]:
    """The document's relationships: an id and the target it points at."""
    targets: dict[str, str] = {}
    if not relationships:
        return targets
    try:
        root = ElementTree.fromstring(relationships)
    except ElementTree.ParseError:
        return targets
    for element in root:
        identifier = element.get("Id")
        target = element.get("Target")
        if identifier is None or target is None:
            continue
        if element.get("TargetMode") == "External":
            continue
        targets[identifier] = target
    return targets


def _resolve_target(target: str, parts: list[str]) -> str | None:
    """The part a relationship points at, in the archive's own names.

    A relationship's target is written relative to the part that holds it,
    so a picture in ``word/media`` is named ``media/image1.png``. Some
    writers name the part in full instead, so both are resolved here and
    the archive's own names decide which one is right.
    """
    candidates: list[str] = []
    if target.startswith("/"):
        candidates.append(posixpath.normpath(target).lstrip("/"))
    else:
        candidates.append(posixpath.normpath(posixpath.join("word", target)))
        candidates.append(posixpath.normpath(target))
    for candidate in candidates:
        if candidate in parts:
            return candidate
    return None


def _body_order(body: bytes, relationships: bytes, parts: list[str]) -> list[str]:
    """The media parts the body refers to, in the order it refers to them.

    The order is the body's, not the archive's: a reader counts the figures
    as they appear, and the archive's order is an implementation detail of
    whoever wrote the file.
    """
    targets = _relationship_targets(relationships)
    order: list[str] = []
    if not body:
        return order
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError:
        return order
    for element in root.iter():
        # ``str`` rather than the tag itself: a node that is not an
        # element -- a comment, say -- has a callable tag, and its name is
        # never the name of a picture.
        local = str(element.tag).rsplit("}", 1)[-1]
        if local not in ("blip", "imagedata"):
            continue
        reference = element.get(f"{{{RELATIONSHIPS_NS}}}embed")
        if reference is None:
            reference = element.get(f"{{{RELATIONSHIPS_NS}}}id")
        if reference is None:
            continue
        target = targets.get(reference)
        if target is None:
            continue
        name = _resolve_target(target, parts)
        if name is not None and name not in order:
            order.append(name)
    return order


def read_pictures(path: Path) -> list[tuple[str, bytes]]:
    """The document's pictures: the part's name and its bytes.

    The pictures come back in the order the body shows them, and a media
    part the body does not refer to comes after them.
    """
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            media = sorted(
                name for name in names if name.startswith("word/media/") and not name.endswith("/")
            )
            body = archive.read("word/document.xml") if "word/document.xml" in names else b""
            relationships = (
                archive.read("word/_rels/document.xml.rels")
                if "word/_rels/document.xml.rels" in names
                else b""
            )
            order = _body_order(body, relationships, media)
            ordered = [name for name in order if name in media]
            rest = [name for name in media if name not in ordered]
            return [(name, archive.read(name)) for name in ordered + rest]
    except zipfile.BadZipFile as error:
        raise ComparisonRefusedError(f"{path} is not a document archive: {error}") from error
    except OSError as error:
        raise ComparisonRefusedError(f"{path} cannot be read: {error}") from error


def _count_differing_pixels(left: bytes, right: bytes, width: int, channels: int) -> int:
    """How many pixels of two same-sized pictures differ.

    The rows are compared as bytes first, and a row that differs is counted
    with the whole row's bytes turned into one number: the difference of
    the two rows, folded so that each pixel's channels share one byte, and
    then counted.  The count is of pixels, not of bytes -- one pixel whose
    three channels all differ counts once.
    """
    if left == right:
        return 0
    total = 0
    stride = width * channels
    marker = b"\xff" + b"\x00" * (channels - 1)
    for start in range(0, len(left), stride):
        left_row = left[start : start + stride]
        right_row = right[start : start + stride]
        if left_row == right_row:
            continue
        difference = int.from_bytes(left_row, "little") ^ int.from_bytes(right_row, "little")
        folded = difference
        for shift in range(8, channels * 8, 8):
            folded |= difference >> shift
        mask = int.from_bytes(marker * width, "little")
        marked = (folded & mask).to_bytes(stride, "little")
        # Only the first byte of each pixel's group carries the group, so
        # only those bytes are counted.
        total += width - marked[::channels].count(b"\x00")
    return total


def compare_pictures(
    index: int,
    copy_part: str,
    copy_bytes: bytes,
    original_part: str,
    original_bytes: bytes,
) -> PictureComparison:
    """Read both sides' picture and say whether they decode to the same pixels."""
    copy_decoded: DecodedPicture | None = None
    original_decoded: DecodedPicture | None = None
    reasons: list[str] = []
    try:
        copy_decoded = decode_picture(copy_bytes)
    except PictureNotDecodedError as error:
        reasons.append(f"the copy's picture: {error}")
    try:
        original_decoded = decode_picture(original_bytes)
    except PictureNotDecodedError as error:
        reasons.append(f"the original's picture: {error}")
    if copy_decoded is None or original_decoded is None:
        return PictureComparison(
            index=index,
            copy_part=copy_part,
            original_part=original_part,
            width=None,
            height=None,
            channels=None,
            bytes_identical=copy_bytes == original_bytes,
            pixels_identical=None,
            differing_pixels=None,
            not_decoded="; ".join(reasons),
            note=None,
        )
    size = (copy_decoded.width, copy_decoded.height, copy_decoded.channels)
    other_size = (original_decoded.width, original_decoded.height, original_decoded.channels)
    if size != other_size:
        return PictureComparison(
            index=index,
            copy_part=copy_part,
            original_part=original_part,
            width=copy_decoded.width,
            height=copy_decoded.height,
            channels=copy_decoded.channels,
            bytes_identical=copy_bytes == original_bytes,
            pixels_identical=False,
            differing_pixels=None,
            not_decoded=None,
            note=(
                f"the two pictures are of different sizes: {size[0]}x{size[1]} "
                f"and {other_size[0]}x{other_size[1]}"
            ),
        )
    identical = copy_decoded.samples == original_decoded.samples
    differing = (
        0
        if identical
        else _count_differing_pixels(
            copy_decoded.samples,
            original_decoded.samples,
            copy_decoded.width,
            copy_decoded.channels,
        )
    )
    return PictureComparison(
        index=index,
        copy_part=copy_part,
        original_part=original_part,
        width=copy_decoded.width,
        height=copy_decoded.height,
        channels=copy_decoded.channels,
        bytes_identical=copy_bytes == original_bytes,
        pixels_identical=identical,
        differing_pixels=differing,
        not_decoded=None,
        note=None,
    )


def compare_documents(copy_path: Path, original_path: Path) -> DocumentComparison:
    """Read both documents' pictures and compare them picture by picture.

    The two documents' pictures are paired by position: the first picture
    of the copy against the first picture of the original, and so on, in
    the order each body shows them.  A picture one document has and the
    other does not is reported on its own rather than paired with nothing.
    """
    copy_pictures = read_pictures(copy_path)
    original_pictures = read_pictures(original_path)
    pictures: list[PictureComparison] = []
    copy_only: list[str] = []
    original_only: list[str] = []
    for index in range(max(len(copy_pictures), len(original_pictures))):
        if index < len(copy_pictures) and index < len(original_pictures):
            copy_part, copy_bytes = copy_pictures[index]
            original_part, original_bytes = original_pictures[index]
            pictures.append(
                compare_pictures(
                    index + 1,
                    copy_part,
                    copy_bytes,
                    original_part,
                    original_bytes,
                )
            )
        elif index < len(copy_pictures):
            copy_only.append(copy_pictures[index][0])
        else:
            original_only.append(original_pictures[index][0])
    return DocumentComparison(
        copy_path=str(copy_path),
        copy_digest=_digest(copy_path),
        original_path=str(original_path),
        original_digest=_digest(original_path),
        pictures=tuple(pictures),
        copy_only=tuple(copy_only),
        original_only=tuple(original_only),
    )


def render(comparison: DocumentComparison) -> str:
    """The comparison as text: the anchors, then one line per picture."""
    lines: list[str] = [
        "Pilot picture comparison",
        "",
        f"copy:      {comparison.copy_path}",
        f"           sha256 {comparison.copy_digest}",
        f"original:  {comparison.original_path}",
        f"           sha256 {comparison.original_digest}",
        "",
        f"decoder:   {DECODER_NAME}",
        f"refuses:   {DECODER_LIMITS}",
        "",
    ]
    for picture in comparison.pictures:
        size = f"{picture.width}x{picture.height}" if picture.width is not None else "-"
        if picture.pixels_identical is True:
            verdict = "pixels identical"
        elif picture.pixels_identical is False:
            if picture.differing_pixels is None:
                verdict = "pixels differ"
            else:
                verdict = f"pixels differ by {picture.differing_pixels} pixel(s)"
        else:
            verdict = "pixels not read"
        bytes_reading = "bytes same" if picture.bytes_identical else "bytes differ"
        lines.append(
            f"picture {picture.index}  copy {picture.copy_part}  "
            f"original {picture.original_part}  {size}  {bytes_reading}  {verdict}"
        )
        if picture.not_decoded is not None:
            lines.append(f"    not decoded: {picture.not_decoded}")
        if picture.note is not None:
            lines.append(f"    note: {picture.note}")
    lines.append("")
    lines.append(
        f"pictures: {len(comparison.pictures)} compared, "
        f"{comparison.identical_count} identical, "
        f"{comparison.differing_count} differing, "
        f"{comparison.undecoded_count} not read"
    )
    lines.append(
        "only in the copy: " + (", ".join(comparison.copy_only) if comparison.copy_only else "none")
    )
    lines.append(
        "only in the original: "
        + (", ".join(comparison.original_only) if comparison.original_only else "none")
    )
    return "\n".join(lines)


def as_json(comparison: DocumentComparison) -> dict[str, Any]:
    """The comparison as data: the same readings, with the part digests."""
    pictures: list[dict[str, Any]] = []
    for picture in comparison.pictures:
        pictures.append(
            {
                "index": picture.index,
                "copy_part": picture.copy_part,
                "original_part": picture.original_part,
                "width": picture.width,
                "height": picture.height,
                "channels": picture.channels,
                "bytes_identical": picture.bytes_identical,
                "pixels_identical": picture.pixels_identical,
                "differing_pixels": picture.differing_pixels,
                "not_decoded": picture.not_decoded,
                "note": picture.note,
            }
        )
    return {
        "decoder": DECODER_NAME,
        "limits": DECODER_LIMITS,
        "copy": {"path": comparison.copy_path, "sha256": comparison.copy_digest},
        "original": {
            "path": comparison.original_path,
            "sha256": comparison.original_digest,
        },
        "pictures": pictures,
        "summary": {
            "compared": len(comparison.pictures),
            "identical": comparison.identical_count,
            "differing": comparison.differing_count,
            "not_read": comparison.undecoded_count,
            "only_in_the_copy": list(comparison.copy_only),
            "only_in_the_original": list(comparison.original_only),
            "all_identical": comparison.all_identical,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pilot_picture_comparison",
        description="Compare the pictures in two documents by decoded pixels.",
    )
    parser.add_argument("--copy", required=True, help="the desensitised copy")
    parser.add_argument("--original", required=True, help="the original the copy was derived from")
    parser.add_argument("--json", default=None, help="where to write the report as JSON")
    arguments = parser.parse_args(argv)
    try:
        comparison = compare_documents(Path(arguments.copy), Path(arguments.original))
    except ComparisonRefusedError as error:
        print(str(error))
        return 2
    print(render(comparison))
    if arguments.json is not None:
        target = Path(arguments.json)
        target.write_text(
            json.dumps(as_json(comparison), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {target}")
    return 0 if comparison.all_identical else 1


if __name__ == "__main__":
    sys.exit(main())
