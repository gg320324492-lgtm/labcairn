"""Redact a copy of the pilot's paper without touching its revision trail.

**What this is for.** The registered copy of the pilot's paper was made by
accepting every revision the advisor had made: the 96 insertions and 17
deletions are gone, and what is left is the paper as it reads after the
edits. The checklist's item B-2 asks for the opposite -- *insertions,
deletions and format changes are present, and their count matches the
original's recorded count* -- because the pilot's trajectory view and its
multi-source line read the revision trail, and a copy without it is a
different paper.

So the copy is redacted from the **original**: the trail stays, and the
identity goes.

**What is removed, and where.** The tool works part by part, because the
identity is not in one place:

* the built-in properties -- ``Author``, ``Last Modified By``, ``Company``,
  ``Manager``, ``Template`` -- are blanked;
* every custom property's value is blanked, which is where a WPS user id
  and a Grammarly document id live;
* every author field in the markup -- the revisions' ``w:author`` and the
  people list Word keeps beside them -- is replaced by a **role label**;
* the paths inside the images' own metadata -- a TIFF's description can
  carry the folder it was drawn in -- are blanked, in place, at the same
  length, so the image data does not move.

**What is not removed.** The document's text, its figures, its structure and
its revision trail are untouched. A redacted copy is the same paper.

**What the tool refuses.** An author the map does not name is **not**
silently kept and **not** silently replaced: the tool stops and says which
one, because an author nobody mapped is an identity still in the copy. A
copy written inside this repository is refused, because the material does
not belong in the tree.

Usage::

    python scripts/pilot_redaction.py \\
        --original <path> --out <path> --author-map <path> [--pseudonym NAME]

The author map is a JSON object of ``{"the name as it appears": "the role
label"}``. It holds names, so it lives with the material and not in this
repository.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import struct
import zipfile
from pathlib import Path
from typing import Any

TOOL_VERSION = 1

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
W15 = "{http://schemas.microsoft.com/office/word/2012/wordml}"
DC = "{http://purl.org/dc/elements/1.1/}"
CP = "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}"
EP = "{http://schemas.openxmlformats.org/officeDocument/2006/extended-properties}"

#: The built-in properties the checklist's items A-1 and A-6 name.
CORE_PROPERTIES = ("creator", "lastModifiedBy")
APP_PROPERTIES = ("Company", "Manager", "Template")

#: The parts that carry an author field.
AUTHOR_PARTS = ("word/document.xml", "word/comments.xml", "word/people.xml")

#: The TIFF tag types whose value is text rather than numbers: BYTE,
#: ASCII and UNDEFINED. A path hides in one of them.
TIFF_TEXT_TYPES = (1, 2, 7)

#: The size of each TIFF type, in bytes.
TIFF_TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}

#: A path inside an image's metadata. The test is deliberately narrow: a
#: picture's pixels hold two backslashes by chance often enough that a
#: loose test would blank the picture. A path names a user folder, a
#: desktop, a directory, or runs through several segments.
#:
#: The Chinese words are written as escapes on purpose: the material's
#: paths name their folders in the document's own script, and the tree
#: carries no Chinese characters of its own -- the pattern matches them
#: without naming them.
PATH_WORD = re.compile(
    r"(users|folder|desktop|documents|pictures|"
    r"\u7528\u6237|\u6587\u6863|\u56fe\u7247|\u684c\u9762)",
    re.IGNORECASE,
)
PATH_SEGMENTS = re.compile(r"(?:/[A-Za-z0-9_ .+-]+){2,}")

#: Where a path may begin: a drive letter, or a slash.
PATH_START = re.compile(rb"[A-Za-z]:\\|/[A-Za-z0-9_ .+-]")


class RedactionError(Exception):
    """A refusal to redact, with the reason in English."""


def _tiff_text_ranges(data: bytes) -> list[tuple[int, int]]:
    """The byte ranges the TIFF's own labels occupy.

    Only the labels the image's directory points at are read. A picture's
    pixels are not a label, and a path that is not in a label is not the
    picture's metadata -- so this is where the redaction is allowed to
    look, and everything outside these ranges is left byte for byte.
    """
    if data[:2] == b"II":
        order = "<"
    elif data[:2] == b"MM":
        order = ">"
    else:
        return []
    magic = struct.unpack(order + "H", data[2:4])[0]
    if magic == 42:
        big = False
    elif magic == 43:
        big = True
    else:
        return []

    ranges: list[tuple[int, int]] = []
    seen: set[int] = set()
    if big:
        offset = struct.unpack(order + "Q", data[8:16])[0]
    else:
        offset = struct.unpack(order + "I", data[4:8])[0]

    while offset and offset not in seen and 0 < offset < len(data):
        seen.add(offset)
        if big:
            count = struct.unpack(order + "Q", data[offset : offset + 8])[0]
            entry = offset + 8
            entry_size = 20
        else:
            count = struct.unpack(order + "H", data[offset : offset + 2])[0]
            entry = offset + 2
            entry_size = 12
        if count > 4096:
            break
        for _ in range(count):
            if entry + entry_size > len(data):
                break
            kind = struct.unpack(order + "H", data[entry + 2 : entry + 4])[0]
            if big:
                items = struct.unpack(order + "Q", data[entry + 4 : entry + 12])[0]
                inline = 8
            else:
                items = struct.unpack(order + "I", data[entry + 4 : entry + 8])[0]
                inline = 4
            size = TIFF_TYPE_SIZES.get(kind, 1) * items
            if kind in TIFF_TEXT_TYPES and 0 < size < 65536:
                if size <= inline:
                    start = entry + 8
                else:
                    pointer_at = entry + 4 + inline
                    width = 8 if big else 4
                    start = struct.unpack(
                        order + ("Q" if big else "I"),
                        data[pointer_at : pointer_at + width],
                    )[0]
                if start >= 0 and start + size <= len(data):
                    ranges.append((start, start + size))
            entry += entry_size
        if big:
            offset = struct.unpack(order + "Q", data[entry : entry + 8])[0]
        else:
            offset = struct.unpack(order + "I", data[entry : entry + 4])[0]
    return ranges


def _png_text_ranges(data: bytes) -> list[tuple[int, int]]:
    """The byte ranges of a PNG's own text chunks."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return []
    ranges: list[tuple[int, int]] = []
    offset = 8
    while offset + 8 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        kind = data[offset + 4 : offset + 8]
        body_start = offset + 8
        if body_start + length > len(data):
            break
        if kind in (b"tEXt", b"iTXt", b"zTXt"):
            ranges.append((body_start, body_start + length))
        offset = body_start + length + 4
    return ranges


def _text_run_end(data: bytes, start: int) -> int:
    """Where the readable text at ``start`` ends.

    The text may be ASCII, and it may be UTF-8 -- a path on a Chinese
    machine carries its folder's name in its own script -- so the run is
    read byte by byte and a multi-byte sequence is followed as one.
    """
    index = start
    while index < len(data):
        byte = data[index]
        if byte == 0:
            break
        if 32 <= byte < 127:
            index += 1
            continue
        if byte >= 0xC2:
            length = 2 if byte < 0xE0 else 3 if byte < 0xF0 else 4
            chunk = data[index : index + length]
            try:
                chunk.decode("utf-8")
            except UnicodeDecodeError:
                break
            index += length
            continue
        break
    return index


def _looks_like_a_path(value: str) -> bool:
    """Whether a readable run carries a path rather than picture bytes.

    The test has to be narrow. A picture's pixel data holds two
    backslashes by chance often enough that a loose test would blank the
    picture, and a blanked picture is a damaged copy -- a worse failure
    than a path left in a label. A path names a folder or runs through
    several segments; two backslashes do not.
    """
    if PATH_WORD.search(value):
        return True
    return bool(PATH_SEGMENTS.search(value))


def _blank_paths(data: bytes) -> tuple[bytes, int]:
    """Blank a path inside a picture's own metadata, and nothing else.

    The path is found inside the ranges the picture's own directory points
    at, so the picture's pixels are never read and never written. The
    bytes are replaced by spaces of the same length, so every offset the
    directory holds stays true.
    """
    ranges = _tiff_text_ranges(data) or _png_text_ranges(data)
    if not ranges:
        return data, 0

    result = bytearray(data)
    blanks = 0
    for start_of_range, end_of_range in ranges:
        for match in PATH_START.finditer(data, start_of_range, end_of_range):
            start = match.start()
            end = _text_run_end(data, start)
            if end > end_of_range:
                end = end_of_range
            if end <= start:
                continue
            run = data[start:end].decode("utf-8", "replace")
            if not _looks_like_a_path(run):
                continue
            result[start:end] = b" " * (end - start)
            blanks += 1
    return bytes(result), blanks


def _blank_core(data: bytes, pseudonym: str) -> tuple[bytes, int]:
    """Blank the author properties in place, byte by byte.

    The part is edited with a pattern rather than parsed and written back:
    a rewritten part renames its namespace prefixes, and Word's
    ``mc:Ignorable`` names the prefixes it expects.
    """
    changed = 0
    for tag in ("dc:creator", "cp:lastModifiedBy"):
        pattern = re.compile(rb"(<" + tag.encode() + rb">)([^<]*)(</" + tag.encode() + rb">)")

        def replace(match: re.Match[bytes]) -> bytes:
            nonlocal changed
            if match.group(2) == pseudonym.encode():
                return match.group(0)
            changed += 1
            return match.group(1) + pseudonym.encode() + match.group(3)

        data = pattern.sub(replace, data)
    return data, changed


def _blank_app(data: bytes) -> tuple[bytes, int]:
    changed = 0
    for tag in APP_PROPERTIES:
        pattern = re.compile(rb"(<" + tag.encode() + rb">)([^<]*)(</" + tag.encode() + rb">)")

        def replace(match: re.Match[bytes]) -> bytes:
            nonlocal changed
            if not match.group(2).strip():
                return match.group(0)
            changed += 1
            return match.group(1) + b"" + match.group(3)

        data = pattern.sub(replace, data)
    return data, changed


def _blank_custom(data: bytes) -> tuple[bytes, int]:
    """Blank every custom property's value, wherever its type keeps it."""
    changed = 0
    pattern = re.compile(rb"(<vt:(?:lpwstr|bstr|i4|bool|filetime)>)([^<]*)(</vt:)")

    def replace(match: re.Match[bytes]) -> bytes:
        nonlocal changed
        if not match.group(2):
            return match.group(0)
        changed += 1
        return match.group(1) + b"" + match.group(3)

    data = pattern.sub(replace, data)
    return data, changed


def _replace_authors(
    data: bytes, author_map: dict[str, str]
) -> tuple[bytes, int, set[str], set[str]]:
    """Replace the markup's author fields with their role labels.

    The names are found as attribute values, so the part's own structure --
    its namespace prefixes, its ids, its dates -- is left exactly as it was.
    """
    seen: set[str] = set()
    replaced = 0
    unmapped: set[str] = set()

    def replace(match: re.Match[bytes]) -> bytes:
        nonlocal replaced
        name = match.group(2).decode("utf-8", "replace")
        seen.add(name)
        label = author_map.get(name)
        if label is None:
            unmapped.add(name)
            return match.group(0)
        replaced += 1
        return match.group(1) + label.encode("utf-8") + match.group(3)

    data = re.sub(rb'((?:w15:)?author=")([^"]*)(")', replace, data)
    return data, replaced, seen, unmapped


def redact(
    original: Path,
    out: Path,
    author_map: dict[str, str],
    *,
    pseudonym: str = "",
    repository_root: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Write the redacted copy and report what each part gave up."""
    if not original.is_file():
        raise RedactionError(f"{original} is not a file")
    if repository_root is not None:
        try:
            out.resolve().relative_to(repository_root.resolve())
        except ValueError:
            pass
        else:
            raise RedactionError(
                f"{out} is inside the repository; the material does not belong in the tree"
            )
    if out.exists() and not force:
        raise RedactionError(f"{out} already exists; pass --force to replace it")

    report: dict[str, Any] = {
        "tool": "pilot-redaction",
        "tool_version": TOOL_VERSION,
        "parts": {},
        "authors_seen": [],
        "authors_unmapped": [],
    }

    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_suffix(out.suffix + ".partial")
    unmapped: set[str] = set()
    seen_authors: set[str] = set()

    with (
        zipfile.ZipFile(original) as source,
        zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as target,
    ):
        for info in source.infolist():
            if info.is_dir():
                continue
            data = source.read(info.filename)
            part_report: dict[str, Any] = {}

            if info.filename in AUTHOR_PARTS:
                data, changed, seen, missing = _replace_authors(data, author_map)
                part_report["author_fields_replaced"] = changed
                seen_authors.update(seen)
                unmapped.update(missing)
            elif info.filename == "docProps/core.xml":
                data, changed = _blank_core(data, pseudonym)
                part_report["properties_blanked"] = changed
            elif info.filename == "docProps/app.xml":
                data, changed = _blank_app(data)
                part_report["properties_blanked"] = changed
            elif info.filename == "docProps/custom.xml":
                data, changed = _blank_custom(data)
                part_report["custom_property_values_blanked"] = changed
            elif info.filename.startswith("word/media/"):
                data, blanks = _blank_paths(data)
                part_report["image_metadata_paths_blanked"] = blanks

            target.writestr(info, data)
            if part_report:
                report["parts"][info.filename] = part_report

    if unmapped:
        temporary.unlink(missing_ok=True)
        raise RedactionError(
            "these authors are in the copy and the map does not name them: "
            + ", ".join(sorted(unmapped))
        )

    shutil.move(str(temporary), str(out))
    report["authors_seen"] = sorted(seen_authors)
    report["out"] = str(out)
    return report


def _read_author_map(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise RedactionError(f"{path} is not a file")
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RedactionError(f"{path} is not readable JSON: {error}") from error
    if not isinstance(loaded, dict):
        raise RedactionError(f"{path} does not hold an object of names and labels")
    mapping: dict[str, str] = {}
    for key, value in loaded.items():
        if not isinstance(key, str) or not isinstance(value, str) or not value.strip():
            raise RedactionError(f"{path} holds an entry that is not a name and a label")
        mapping[key] = value
    if not mapping:
        raise RedactionError(f"{path} names no author")
    return mapping


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pilot_redaction",
        description="Redact a copy of the pilot's paper and keep its revision trail.",
    )
    parser.add_argument("--original", required=True, help="the document to redact")
    parser.add_argument("--out", required=True, help="where to write the redacted copy")
    parser.add_argument("--author-map", required=True, help="a JSON map of names to role labels")
    parser.add_argument(
        "--pseudonym",
        default="",
        help="the fixed pseudonym the author properties carry; empty by default",
    )
    parser.add_argument("--force", action="store_true", help="replace a copy that already exists")
    parser.add_argument("--json", default=None, help="where to write the report as JSON")
    arguments = parser.parse_args(argv)

    repository_root = Path(__file__).resolve().parents[1]
    try:
        author_map = _read_author_map(Path(arguments.author_map))
        report = redact(
            Path(arguments.original),
            Path(arguments.out),
            author_map,
            pseudonym=arguments.pseudonym,
            repository_root=repository_root,
            force=arguments.force,
        )
    except RedactionError as error:
        print(str(error))
        return 2

    print(f"wrote {report['out']}")
    for part, counts in report["parts"].items():
        summary = ", ".join(f"{key}={value}" for key, value in counts.items())
        print(f"  {part}: {summary}")
    if arguments.json is not None:
        Path(arguments.json).write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {arguments.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
