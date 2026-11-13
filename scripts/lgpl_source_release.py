"""The LGPL §4 delivery checklist, read out of NOTICE and checked against bytes.

**What this script is.** `NOTICE` §2.5.1 records, for every binary §2.5 lists under
an LGPL-2.1 term, a delivery entry: the file a release must carry, where it was
fetched from, its byte count and its sha256, and the point at which it is offered.
LGPL-2.1 §4 obliges a distributor to convey the complete corresponding source with
the object code, and its final paragraph allows that to happen by "offering
equivalent access to copy the source code from the same place". This script turns
that record into the three things a release actually needs: a checklist it can carry
into the release, a byte check that says whether the archives on hand are the
archives the record names, and a re-measurement of the closure §2.5.2 prints about
the plug-in's compilation project.

**What it refuses to do.** It never states that the obligation is discharged. As
long as the record's own state is the one §2.5.1 prints -- PARTLY DONE, NOT YET
POINTED AT -- every line it prints is future tense, because nothing has been
released. A record that said DONE while no archive had been attached to a release
would be a claim with nothing behind it, and this script is the place such a claim
would be noticed: it reports the sha256 of the file it actually hashed, or it says
the file was not there.

**Why it reads NOTICE rather than carrying its own list.** A second list of
artefacts and hashes is a second place for the same values to go wrong. The record
is the authority, and this script is a reader of it; where the record names a hash
and the bytes disagree, the bytes win and the script exits 1 naming the entry. The
same rule governs ``--audit-extracts``: the numbers it re-measures are the numbers
§2.5.2 prints, read out of §2.5.2's own sentences, so an audit that drifted from the
record it audits would report a mismatch rather than agree with itself.

Run with no argument to print the checklist. Run with ``--check <dir>`` to hash the
archives in ``<dir>`` against the hashes §2.5.1 records: exit 0 when every delivered
file matches, exit 1 with one line per mismatch. Run with ``--audit-extracts
<nsis7z-extract> <sevenzip-extract>`` -- two directories the archives were unpacked
into -- to re-count the closure §2.5.2 states and report where the record and the
extracts disagree.

"""

from __future__ import annotations

import argparse
import hashlib
import posixpath
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
NOTICE_PATH: Final[Path] = REPO_ROOT / "NOTICE"

#: A §2.5 binary block heading: `  StdUtils.dll — 102,400 bytes`.
BINARY_HEADING: Final[re.Pattern[str]] = re.compile(
    r"^ {2}([A-Za-z0-9_.-]+\.(?:dll|exe)) — ([\d,]+) bytes$"
)

#: One field of a §2.5 binary block: `    licence  LGPL-2.1-or-later`.
BINARY_FIELD: Final[re.Pattern[str]] = re.compile(
    r"^ {4}(path|sha256|bundle|licence|holder|where)\s{2,}(\S.*)$"
)

#: A wrapped §2.5 field value, aligned under its value.
BINARY_CONTINUATION: Final[re.Pattern[str]] = re.compile(r"^ {5,}\S")

#: A §2.5.1 delivery entry: `    Delivery entry — \`StdUtils.dll\`` or
#: `    Delivery entry — \`nsis7z.dll\`, 1 of 2`.
DELIVERY_HEADING: Final[re.Pattern[str]] = re.compile(
    r"^ {4}Delivery entry — `(?P<binary>[A-Za-z0-9_.-]+\.(?:dll|exe))`(?P<part>[^\n]*)"
)

#: One labelled line of a delivery entry: `      artefact name — 972,800 bytes, sha256`.
#: The separator is one-or-more spaces rather than two: `artefact` is §2.5.1's longest
#: label, so that one carries a single space, and a pattern demanding two read no
#: artefact out of a record that states one.
DELIVERY_LABEL: Final[re.Pattern[str]] = re.compile(r"^ {6}(?P<label>[a-z]+) +(?P<value>\S.*)$")

#: A wrapped delivery-entry value, aligned under its value.
DELIVERY_CONTINUATION: Final[re.Pattern[str]] = re.compile(r"^ {7,}\S")

#: `972,800 bytes` as a delivery entry writes it.
BYTES_CLAIM: Final[re.Pattern[str]] = re.compile(r"([\d,]+) bytes")

#: A sha256 written out in full.
FULL_SHA256: Final[re.Pattern[str]] = re.compile(r"\b[0-9a-f]{64}\b")

#: An upstream location: the place a release's reader would go to for the same bytes.
URL: Final[re.Pattern[str]] = re.compile(r"https?://[^\s`.,;)]+")

#: A §2.5.1 obligation state line, as §2.5.1 prints it and as the Node witness reads it.
CORRESPONDING_SOURCE_STATE: Final[re.Pattern[str]] = re.compile(
    r"\*\*The corresponding source \(§4, §6\(c\)\) — (?P<state>[^*]+)\.\*\*"
)

_SECTION_HEADING: Final[re.Pattern[str]] = re.compile(r"^\d+(\.\d+)*\.?  \S")

#: The §2.5 licence field that makes a binary's corresponding source obligatory here.
LGPL_TERM: Final[re.Pattern[str]] = re.compile(r"LGPL", re.IGNORECASE)


def _subsection(notice_text: str, heading: str) -> str:
    """The lines of one NOTICE subsection, up to the next section heading."""
    lines = notice_text.split("\n")
    start = next((i for i, line in enumerate(lines) if line.startswith(f"{heading}  ")), -1)
    if start < 0:
        raise RuntimeError(f"NOTICE has no subsection {heading}")
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if _SECTION_HEADING.match(lines[index]):
            end = index
            break
    return "\n".join(lines[start:end])


class BinaryRecord:
    """One §2.5 binary block, as the record states it."""

    def __init__(self, name: str, bytes_claim: int, fields: dict[str, str]) -> None:
        self.name = name
        self.bytes_claim = bytes_claim
        self.fields = fields

    @property
    def licence(self) -> str:
        return self.fields.get("licence", "")

    @property
    def is_lgpl(self) -> bool:
        return bool(LGPL_TERM.search(self.licence))


class DeliveryEntry:
    """One §2.5.1 delivery entry: the labels it carries and their values."""

    def __init__(self, binary: str, part: str, labels: dict[str, str]) -> None:
        self.binary = binary
        # `§2.5.1 writes a part as `, 1 of 2`; the comma is punctuation, not part of
        # the label a checklist prints.
        self.part = part.strip().strip(",").strip()
        self.labels = labels

    @property
    def label(self) -> str:
        return f"{self.binary}{f' {self.part}' if self.part else ''}"

    @property
    def artefact(self) -> str:
        """The file a release must carry, as the `artefact` label names it."""
        return self.labels.get("artefact", "")

    def problems(self) -> list[str]:
        """What this entry fails to state. An entry that states less is not a step."""
        problems: list[str] = []
        artefact = self.artefact
        if not artefact:
            problems.append(
                f"{self.label}: the entry carries no `artefact` label, so it names no file"
            )
            return problems
        name = artefact.split(" — ")[0].strip()
        if not name:
            problems.append(f"{self.label}: the `artefact` label names no file")
        if not BYTES_CLAIM.search(artefact):
            problems.append(f"{self.label}: the `artefact` label states no byte count for {name}")
        if not FULL_SHA256.search(artefact):
            problems.append(
                f"{self.label}: the `artefact` label states no 64-hex-digit sha256 for {name}"
            )
        joined = " ".join(self.labels.values())
        if not URL.search(joined):
            problems.append(
                f"{self.label}: the entry names no upstream URL the source is taken from"
            )
        if "at" not in self.labels:
            problems.append(
                f"{self.label}: the entry states no point at which the source is offered"
            )
        return problems

    def recorded_sha256(self) -> str | None:
        """The sha256 §2.5.1 records for this entry's artefact, if it records one."""
        match = FULL_SHA256.search(self.artefact)
        return match.group(0) if match else None

    def recorded_bytes(self) -> int | None:
        match = BYTES_CLAIM.search(self.artefact)
        return int(match.group(1).replace(",", "")) if match else None

    def artefact_name(self) -> str:
        return self.artefact.split(" — ")[0].strip()


def binary_records(notice_text: str) -> list[BinaryRecord]:
    """§2.5's binary blocks, each with all six fields."""
    records: list[BinaryRecord] = []
    current: BinaryRecord | None = None
    last_field: str | None = None
    for line in _subsection(notice_text, "2.5").split("\n"):
        heading = BINARY_HEADING.match(line)
        if heading:
            current = BinaryRecord(heading.group(1), int(heading.group(2).replace(",", "")), {})
            records.append(current)
            last_field = None
            continue
        if current is None:
            continue
        field = BINARY_FIELD.match(line)
        if field:
            current.fields[field.group(1)] = field.group(2).strip()
            last_field = field.group(1)
            continue
        if BINARY_CONTINUATION.match(line) and last_field:
            current.fields[last_field] += " " + line.strip()
            continue
        last_field = None
    if not records:
        raise RuntimeError("NOTICE §2.5 names no binary — the read found nothing")
    return records


def delivery_entries(notice_text: str) -> list[DeliveryEntry]:
    """§2.5.1's delivery entries, each with its labels joined back onto their values."""
    entries: list[DeliveryEntry] = []
    current: DeliveryEntry | None = None
    last_label: str | None = None
    for line in _subsection(notice_text, "2.5.1").split("\n"):
        heading = DELIVERY_HEADING.match(line)
        if heading:
            current = DeliveryEntry(heading.group("binary"), heading.group("part") or "", {})
            entries.append(current)
            last_label = None
            continue
        if current is None:
            continue
        label = DELIVERY_LABEL.match(line)
        if label:
            current.labels[label.group("label")] = label.group("value").strip()
            last_label = label.group("label")
            continue
        if DELIVERY_CONTINUATION.match(line) and last_label:
            current.labels[last_label] += " " + line.strip()
            continue
        last_label = None
    if not entries:
        raise RuntimeError("NOTICE §2.5.1 carries no delivery entry — the read found nothing")
    return entries


def obligation_state(notice_text: str) -> str:
    """§2.5.1's own statement of where the corresponding-source obligation stands."""
    section = " ".join(_subsection(notice_text, "2.5.1").split("\n"))
    match = CORRESPONDING_SOURCE_STATE.search(section)
    if not match:
        raise RuntimeError(
            "NOTICE §2.5.1 states no corresponding-source state — the read found nothing"
        )
    return match.group("state").strip()


def coverage_problems(records: list[BinaryRecord], entries: list[DeliveryEntry]) -> list[str]:
    """Every LGPL binary §2.5 records has a delivery entry, and each entry is complete."""
    problems: list[str] = []
    lgpl = [record for record in records if record.is_lgpl]
    if not lgpl:
        problems.append(
            "§2.5 records no binary under an LGPL term, so the delivery entries watch nothing"
        )
    named = {entry.binary for entry in entries}
    for record in lgpl:
        if record.name not in named:
            problems.append(
                f"{record.name}: §2.5 records it under {record.licence.split(' — ')[0]!r} "
                "and §2.5.1 carries no delivery entry naming it"
            )
    for entry in entries:
        if entry.binary not in {record.name for record in records}:
            problems.append(
                f"{entry.label}: §2.5.1 delivers a source for {entry.binary}, "
                "which §2.5 records no binary of that name"
            )
        problems.extend(entry.problems())
    return problems


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def check_against_directory(entries: list[DeliveryEntry], directory: Path) -> list[str]:
    """Hash the artefacts in `directory` against the hashes §2.5.1 records."""
    if not directory.is_dir():
        return [f"{directory} is no directory, so no delivered file could be hashed"]
    problems: list[str] = []
    for entry in entries:
        name = entry.artefact_name()
        expected = entry.recorded_sha256()
        recorded_bytes = entry.recorded_bytes()
        if not name or expected is None:
            problems.append(f"{entry.label}: no artefact or no recorded sha256 to check against")
            continue
        candidate = directory / name
        if not candidate.is_file():
            problems.append(
                f"{entry.label}: {name} is not in {directory}, so §2.5.1's sha256 "
                f"{expected[:16]}… was not measured against any file here"
            )
            continue
        actual = _sha256(candidate)
        size = candidate.stat().st_size
        if recorded_bytes is not None and size != recorded_bytes:
            problems.append(
                f"{entry.label}: §2.5.1 records {name} as {recorded_bytes} bytes; "
                f"{candidate} is {size}"
            )
        if actual != expected:
            problems.append(
                f"{entry.label}: §2.5.1 records {name} as sha256 {expected}; "
                f"{candidate} is {actual}"
            )
    return problems


#: §2.5.1's `limit` label on the plug-in entry: how much of the project that
#: archive does not supply. §2.5.2's closure audit re-measures it.
#: Read as one run of text, because §2.5.1 wraps the label across lines and the
#: audit joins the section's lines before matching.
PLUGIN_LIMIT: Final[re.Pattern[str]] = re.compile(
    r"of the (?P<sources>\d+) sources the archive's own `Nsis7z\.vcxproj` compiles, "
    r"(?P<sources_absent>\d+) are not in it, and of the (?P<headers>\d+) headers it names, "
    r"(?P<headers_absent>\d+) are absent"
)

#: §2.5.1's `taken` label on the 7-Zip entry: how much of that gap it closes.
SEVENZIP_COVERAGE: Final[re.Pattern[str]] = re.compile(
    r"supplies the (?P<sources>\d+) remaining compiled sources and "
    r"(?P<headers>\d+) of the (?P<headers_absent>\d+) missing headers"
)

#: A header count written as a word: "one header is in neither archive".
COUNT_WORD: Final[re.Pattern[str]] = re.compile(
    r"(?P<count>none|one|two|three|four|five|six|seven|eight|nine|\d+) headers? (?:is|are) in "
    r"neither (?:7-Zip )?archive"
)

#: §2.5.2's Rar item: the compiled-source census and how many of them name Rar.
RAR_COMPILED_CLAIM: Final[re.Pattern[str]] = re.compile(
    r"`Nsis7z\.vcxproj` lists \*\*(?P<compiled>\d+)\*\* compiled sources and "
    r"\*\*(?P<rar_named>[a-z]+)\*\* of them names a Rar file"
)

#: §2.5.2's Rar item: how many files the plug-in's own archive carries. The record
#: writes the count as a sentence ("no file named `*Rar*` at all"), so the word is
#: captured rather than a zero hard-coded: a reader that matched the sentence and then
#: read its own constant would print "measured 0" against a plug-in archive that
#: carried nine.
PLUGIN_RAR_CLAIM: Final[re.Pattern[str]] = re.compile(
    r"the plug-in's own release archive contains \*\*(?P<count>[a-z]+|\d+) files? named "
    r"`\*Rar\*` at all\*\*"
)

#: §2.5.2's Rar item: what the shipped binary's own bytes contain.
DLL_TOKEN_CLAIM: Final[re.Pattern[str]] = re.compile(
    r"the shipped DLL's bytes contain `Rar`, `NRar` and `unrar` \*\*(?P<count>\d+) times each\*\*"
)

#: §2.5.2's Rar item: the handlers the 7-Zip source release carries, and the notice
#: document beside them.
SEVENZIP_RAR_CLAIM: Final[re.Pattern[str]] = re.compile(
    r"contains \*\*all (?P<files>[a-z]+|\d+)\*\* files of `CPP/7zip/Archive/Rar/` "
    r"and a (?P<doc_bytes>[\d,]+)-byte `DOC/unRarLicense\.txt`"
)

#: §2.5.2's Rar item: the same count for the archive the plug-in's build note names.
LZMA_RAR_CLAIM: Final[re.Pattern[str]] = re.compile(
    r"The `lzma1900\.7z` archive the plug-in's build note names contains "
    r"\*\*(?P<count>[a-z]+|\d+)\*\* of the nine"
)

#: Spelled-out counts, as §2.5.1 and §2.5.2 write a small count in words.
WORD_COUNTS: Final[dict[str, int]] = {
    "none": 0,
    "no": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
}


def _flat(notice_text: str, heading: str) -> str:
    """One subsection as one run of text, with every wrap and its indentation collapsed.

    §2.5.1 and §2.5.2 wrap their sentences, and a wrapped line carries its own
    indentation, so a sentence spans several spaces in the middle. A claim reader
    matches sentences, not lines, and matching a claim against a single space per
    wrap is how a reader reports "NOTICE states nothing" about a record that states
    it plainly.
    """
    return " ".join(_subsection(notice_text, heading).split())


def _count(text: str, *, where: str) -> int:
    """A count the record wrote as a digit or as a word."""
    text = text.strip()
    if text.isdigit():
        return int(text)
    if text.lower() in WORD_COUNTS:
        return WORD_COUNTS[text.lower()]
    raise RuntimeError(
        f"NOTICE states {where} as {text!r}, which is not a count this reader parses"
    )


@dataclass
class ClosureClaim:
    """The closure numbers §2.5.1 and §2.5.2 print about the plug-in's project."""

    compiled_sources: int
    named_headers: int
    sources_absent_from_plugin: int
    headers_absent_from_plugin: int
    sources_supplied_by_sevenzip: int
    headers_supplied_by_sevenzip: int
    headers_in_neither: int
    compiled_naming_rar: int
    plugin_rar_files: int
    dll_token_occurrences: int
    sevenzip_rar_files: int
    unrar_notice_bytes: int
    lzma_rar_files: int


def closure_claims(notice_text: str) -> ClosureClaim:
    """Read the closure numbers out of the record, or refuse naming none of them.

    Every expected value here comes from NOTICE's own sentences. An audit that
    carried its own copy of the numbers would only ever agree with itself, which is
    the failure mode this whole file is written against.
    """
    section_251 = _flat(notice_text, "2.5.1")
    section_252 = _flat(notice_text, "2.5.2")

    def need(pattern: re.Pattern[str], text: str, where: str) -> re.Match[str]:
        match = pattern.search(text)
        if not match:
            raise RuntimeError(f"NOTICE {where} states nothing this reader can match")
        return match

    limit = need(
        PLUGIN_LIMIT, section_251, "§2.5.1's `limit` label on the nsis7z.dll plug-in entry"
    )
    coverage = need(
        SEVENZIP_COVERAGE, section_251, "§2.5.1's `taken` label on the nsis7z.dll 7-Zip entry"
    )
    gap = need(COUNT_WORD, section_251, "§2.5.1's `gap` label on the nsis7z.dll 7-Zip entry")
    rar_compiled = need(RAR_COMPILED_CLAIM, section_252, "§2.5.2's Rar item")
    rar_dir = need(SEVENZIP_RAR_CLAIM, section_252, "§2.5.2's Rar item")
    lzma = need(LZMA_RAR_CLAIM, section_252, "§2.5.2's Rar item")
    dll = need(DLL_TOKEN_CLAIM, section_252, "§2.5.2's Rar item")

    return ClosureClaim(
        compiled_sources=int(limit.group("sources")),
        named_headers=int(limit.group("headers")),
        sources_absent_from_plugin=int(limit.group("sources_absent")),
        headers_absent_from_plugin=int(limit.group("headers_absent")),
        sources_supplied_by_sevenzip=int(coverage.group("sources")),
        headers_supplied_by_sevenzip=int(coverage.group("headers")),
        headers_in_neither=_count(gap.group("count"), where="§2.5.1's header gap"),
        compiled_naming_rar=_count(
            rar_compiled.group("rar_named"),
            where="§2.5.2's count of compiled sources naming a Rar file",
        ),
        plugin_rar_files=_count(
            need(
                PLUGIN_RAR_CLAIM,
                section_252,
                "§2.5.2's claim about Rar files in the plug-in archive",
            ).group("count"),
            where="§2.5.2's count of Rar files in the plug-in archive",
        ),
        dll_token_occurrences=int(dll.group("count")),
        sevenzip_rar_files=_count(rar_dir.group("files"), where="§2.5.2's count of Rar handlers"),
        unrar_notice_bytes=int(rar_dir.group("doc_bytes").replace(",", "")),
        lzma_rar_files=_count(
            lzma.group("count"), where="§2.5.2's count of Rar files in lzma1900.7z"
        ),
    )


#: The plug-in project, relative to the unpacked plug-in archive.
PLUGIN_PROJECT: Final[Path] = Path("Contrib/nsis7z/CPP/7zip/Bundles/Nsis7z/Nsis7z.vcxproj")

#: The includes the project lists, and the shape each one has in the archives.
INCLUDE_ENTRY: Final[re.Pattern[str]] = re.compile(r'<(ClCompile|ClInclude) Include="([^"]+)"')

#: Where the plug-in archive puts the binary §2.5 records.
PLUGIN_DLL: Final[Path] = Path("Plugins/x86-unicode/nsis7z.dll")

#: The unRAR-restricted handlers, and the notice document, inside the 7-Zip release.
RAR_HANDLER_DIR: Final[Path] = Path("CPP/7zip/Archive/Rar")
UNRAR_NOTICE: Final[Path] = Path("DOC/unRarLicense.txt")

#: The strings §2.5.2 says the shipped binary's bytes do not contain.
RAR_TOKENS: Final[tuple[bytes, ...]] = (b"Rar", b"NRar", b"unrar")

#: What a count stands for when the archive it would be measured against was not given.
NOT_MEASURED: Final[int] = -1


def _project_includes(extract: Path) -> dict[str, list[str]]:
    """The include entries the plug-in's own project file lists, by kind."""
    project = extract / PLUGIN_PROJECT
    if not project.is_file():
        raise RuntimeError(f"{project} is no file, so the compiled-source list was not read")
    text = project.read_text(encoding="utf-8", errors="replace")
    kinds: dict[str, list[str]] = {"ClCompile": [], "ClInclude": []}
    for kind, entry in INCLUDE_ENTRY.findall(text):
        kinds[kind].append(entry.replace("\\", "/"))
    return {kind: sorted(set(entries)) for kind, entries in kinds.items()}


def _relative_to_extract(extract: Path, entry: str) -> Path:
    r"""Where a project entry lands inside an unpacked archive.

    The project lists its includes relative to its own directory, and many of them
    walk out of it (`..\..\UI\Common\…`). Resolving the entry against the project
    directory and then back against the extract root is how the archive's own layout
    is read; matching the entry text against the tree instead would report a header
    that is plainly present as being in neither archive.
    """
    project_dir = (extract / PLUGIN_PROJECT).parent
    resolved = Path(posixpath.normpath(posixpath.join(project_dir.as_posix(), entry)))
    try:
        return resolved.relative_to(extract)
    except ValueError:
        return Path(posixpath.normpath(entry))


def _archive_side(extract: Path, entry: str) -> Path:
    """The path that same include has in an archive rooted at the plug-in's position.

    The plug-in's build note describes putting an archive's `C/` and `CPP/` trees at
    `Contrib/nsis7z/`, so an entry that resolves below that prefix resolves at the
    root of such an archive.
    """
    parts = _relative_to_extract(extract, entry).parts
    if parts[:2] == ("Contrib", "nsis7z"):
        return Path(*parts[2:])
    return Path(*parts)


def _in_plugin_archive(extract: Path, entry: str) -> bool:
    """Whether the plug-in's own release supplies this include."""
    return (extract / _relative_to_extract(extract, entry)).is_file()


def audit_extracts(
    claim: ClosureClaim,
    records: list[BinaryRecord],
    nsis7z_extract: Path,
    sevenzip_extract: Path,
    lzma_extract: Path | None,
) -> tuple[list[str], list[str]]:
    """Re-count §2.5.2's closure numbers on the unpacked archives.

    Returns the report lines and the problems. A problem is a number the record
    prints that the extracts do not print, or an archive that was not there to be
    counted at all. A count whose archive was not passed prints NOT_MEASURED rather
    than a number, so "the audit ran" never looks like "the claim held".
    """
    lines: list[str] = []
    problems: list[str] = []
    given = [
        ("@audit-extracts nsis7z", nsis7z_extract),
        ("@audit-extracts sevenzip", sevenzip_extract),
    ]
    if lzma_extract is not None:
        given.append(("@audit-extracts lzma", lzma_extract))
    for name, directory in given:
        if not directory.is_dir():
            problems.append(f"{name}: {directory} is no directory, so nothing there was counted")
    if problems:
        return lines, problems

    includes = _project_includes(nsis7z_extract)
    compiled, headers = includes["ClCompile"], includes["ClInclude"]
    compiled_missing = [e for e in compiled if not _in_plugin_archive(nsis7z_extract, e)]
    headers_missing = [e for e in headers if not _in_plugin_archive(nsis7z_extract, e)]
    headers_in_neither = [
        e
        for e in headers_missing
        if not (sevenzip_extract / _archive_side(nsis7z_extract, e)).is_file()
    ]

    def compare(what: str, expected: int, actual: int) -> None:
        lines.append(f"{what}: record {expected}, measured {actual}")
        if expected != actual:
            problems.append(f"{what}: §2.5.1/§2.5.2 print {expected}, the extracts give {actual}")

    compare("compiled sources the project lists", claim.compiled_sources, len(compiled))
    compare("headers the project lists", claim.named_headers, len(headers))
    compare(
        "compiled sources absent from the plug-in archive",
        claim.sources_absent_from_plugin,
        len(compiled_missing),
    )
    compare(
        "headers absent from the plug-in archive",
        claim.headers_absent_from_plugin,
        len(headers_missing),
    )
    compare(
        "compiled sources the 7-Zip archive supplies",
        claim.sources_supplied_by_sevenzip,
        sum(
            1
            for e in compiled_missing
            if (sevenzip_extract / _archive_side(nsis7z_extract, e)).is_file()
        ),
    )
    compare(
        "headers the 7-Zip archive supplies",
        claim.headers_supplied_by_sevenzip,
        sum(
            1
            for e in headers_missing
            if (sevenzip_extract / _archive_side(nsis7z_extract, e)).is_file()
        ),
    )
    compare("headers in neither archive", claim.headers_in_neither, len(headers_in_neither))
    for entry in headers_in_neither:
        lines.append(f"  in neither archive: {_archive_side(nsis7z_extract, entry).as_posix()}")
    compare(
        "compiled sources naming a Rar file",
        claim.compiled_naming_rar,
        sum(1 for e in compiled if "Rar" in Path(e).name),
    )
    compare(
        "files named *Rar* in the plug-in archive",
        claim.plugin_rar_files,
        sum(1 for p in nsis7z_extract.rglob("*") if "Rar" in p.name and p.is_file()),
    )
    rar_dir = sevenzip_extract / RAR_HANDLER_DIR
    sevenzip_rar_files = (
        sorted(p for p in rar_dir.rglob("*") if p.is_file()) if rar_dir.is_dir() else []
    )
    compare(
        "files of CPP/7zip/Archive/Rar in the 7-Zip archive",
        claim.sevenzip_rar_files,
        len(sevenzip_rar_files),
    )
    unrar_notice = sevenzip_extract / UNRAR_NOTICE
    compare(
        "bytes of DOC/unRarLicense.txt",
        claim.unrar_notice_bytes,
        unrar_notice.stat().st_size if unrar_notice.is_file() else NOT_MEASURED,
    )
    compare(
        "files named *Rar* in lzma1900.7z",
        claim.lzma_rar_files,
        NOT_MEASURED
        if lzma_extract is None
        else sum(1 for p in lzma_extract.rglob("*") if "Rar" in p.name and p.is_file()),
    )
    if lzma_extract is None:
        lines.append(
            "  lzma1900.7z was not passed, so §2.5.2's count of its Rar files was not re-measured"
        )

    dll = nsis7z_extract / PLUGIN_DLL
    if not dll.is_file():
        problems.append(
            "@audit-extracts nsis7z: "
            f"{dll} is no file, so §2.5.2's counts of the shipped binary's bytes "
            "were not measured against any binary"
        )
        return lines, problems

    shipped = next((record for record in records if record.name == "nsis7z.dll"), None)
    recorded_sha = shipped.fields.get("sha256", "").strip() if shipped else ""
    actual_sha = _sha256(dll)
    if not recorded_sha:
        problems.append(
            "@audit-extracts nsis7z: §2.5 records no sha256 for nsis7z.dll to compare against"
        )
    elif actual_sha != recorded_sha:
        problems.append(
            f"@audit-extracts nsis7z: §2.5 records nsis7z.dll as sha256 {recorded_sha}; "
            f"{dll} is {actual_sha}, so the binary counted here is not the binary §2.5 records"
        )
    data = dll.read_bytes()
    counts = {token.decode(): data.count(token) for token in RAR_TOKENS}
    lines.append(
        "shipped binary's bytes: "
        + ", ".join(f"{token}={count}" for token, count in counts.items())
    )
    for token, count in counts.items():
        if count != claim.dll_token_occurrences:
            problems.append(
                f"@audit-extracts nsis7z: §2.5.2 prints {token!r} "
                f"{claim.dll_token_occurrences} times in nsis7z.dll; measured {count}"
            )
    return lines, problems


def render_checklist(records: list[BinaryRecord], entries: list[DeliveryEntry], state: str) -> str:
    """The checklist a release performs, printed from the record rather than restated in code."""
    # Whether these are future steps is §2.5.1's own statement, not this script's.
    # A record that has moved to a done state gets a different sentence, and a
    # script that asserted "no release exists" would keep saying it after one did.
    opening = (
        "Every step below is a step a release performs: §2.5.1 does not record the "
        "obligation as discharged."
        if "PARTLY DONE" in state
        else f"§2.5.1 records the obligation as: {state}."
    )
    lines = [
        "LGPL-2.1 §4 corresponding-source delivery, read out of NOTICE §2.5.1.",
        f"§2.5.1 states the obligation as: {state}",
        opening,
        "",
    ]
    by_binary: dict[str, list[DeliveryEntry]] = {}
    for entry in entries:
        by_binary.setdefault(entry.binary, []).append(entry)
    for record in records:
        if not record.is_lgpl:
            continue
        lines.append(
            f"{record.name} — {record.bytes_claim} bytes — {record.licence.split(' — ')[0]}"
        )
        for entry in by_binary.get(record.name, []):
            suffix = f" ({entry.part})" if entry.part else ""
            lines.append(f"  carry{suffix}  {entry.artefact_name()}")
            lines.append(f"    recorded  {entry.artefact}")
            for label in ("taken", "fetched", "limit", "also", "gap", "at"):
                value = entry.labels.get(label)
                if value:
                    lines.append(f"    {label:9s}  {value}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Print the §2.5.1 delivery checklist, or check delivered bytes against it.",
    )
    parser.add_argument(
        "--check",
        metavar="DIR",
        help="hash the artefacts in DIR against the sha256 values §2.5.1 records",
    )
    parser.add_argument(
        "--notice",
        metavar="FILE",
        default=str(NOTICE_PATH),
        help="the NOTICE to read (default: this repository's)",
    )
    parser.add_argument(
        "--audit-extracts",
        nargs="+",
        metavar="DIR",
        help=(
            "directories the plug-in archive, the 7-Zip source archive and (optionally) the "
            "LZMA SDK archive were unpacked into; re-counts §2.5.2's closure numbers "
            "against what §2.5.1 and §2.5.2 print"
        ),
    )
    arguments = parser.parse_args(argv)

    notice_path = Path(arguments.notice)
    try:
        notice_text = notice_path.read_text(encoding="utf-8")
        records = binary_records(notice_text)
        entries = delivery_entries(notice_text)
        state = obligation_state(notice_text)
    except (OSError, RuntimeError) as error:
        print(f"the record could not be read: {error}", file=sys.stderr)
        return 1

    print(render_checklist(records, entries, state))

    problems = coverage_problems(records, entries)
    if problems:
        print("the record is incomplete:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    if arguments.check:
        directory = Path(arguments.check)
        byte_problems = check_against_directory(entries, directory)
        if byte_problems:
            print("the bytes behind the record:", file=sys.stderr)
            for problem in byte_problems:
                print(f"  {problem}", file=sys.stderr)
            return 1
        measured = ", ".join(entry.artefact_name() for entry in entries)
        print(f"measured: {measured} — each hashed to the sha256 §2.5.1 records")

    if arguments.audit_extracts:
        extracts = [Path(directory) for directory in arguments.audit_extracts]
        if len(extracts) == 3:
            lzma_extract: Path | None = extracts[2]
        elif len(extracts) == 2:
            lzma_extract = None
        else:
            print(
                "--audit-extracts takes two directories (the plug-in archive, the 7-Zip source "
                "archive) or three (with the LZMA SDK archive); "
                f"{len(extracts)} were given",
                file=sys.stderr,
            )
            return 2
        try:
            claim = closure_claims(notice_text)
        except RuntimeError as error:
            print(f"the closure claims could not be read: {error}", file=sys.stderr)
            return 1
        print("§2.5.2's closure numbers, re-measured on the unpacked archives:")
        audit_lines, audit_problems = audit_extracts(
            claim, records, extracts[0], extracts[1], lzma_extract
        )
        for line in audit_lines:
            print(f"  {line}")
        if audit_problems:
            print("the closure record and the extracts disagree:", file=sys.stderr)
            for problem in audit_problems:
                print(f"  {problem}", file=sys.stderr)
            return 1
        print(
            "each number §2.5.1 and §2.5.2 print about the plug-in's project was re-counted "
            "from the archives and matched"
        )

    lgpl_count = sum(1 for record in records if record.is_lgpl)
    print(f"§2.5 records {len(records)} binaries, {lgpl_count} under an LGPL term;")
    print(f"§2.5.1 carries {len(entries)} delivery entries, one or more for each of them.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
