"""The LGPL §4 delivery checklist, read out of NOTICE and checked against bytes.

**What this script is.** `NOTICE` §2.5.1 records, for every binary §2.5 lists under
an LGPL-2.1 term, a delivery entry: the file a release must carry, where it was
fetched from, its byte count and its sha256, and the point at which it is offered.
LGPL-2.1 §4 obliges a distributor to convey the complete corresponding source with
the object code, and its final paragraph allows that to happen by "offering
equivalent access to copy the source code from the same place". This script turns
that record into the two things a release actually needs: a checklist it can carry
into the release, and a byte check that says whether the archives on hand are the
archives the record names.

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
and the bytes disagree, the bytes win and the script exits 1 naming the entry.

Run with no argument to print the checklist. Run with ``--check <dir>`` to hash the
archives in ``<dir>`` against the hashes §2.5.1 records: exit 0 when every delivered
file matches, exit 1 with one line per mismatch.

"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
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

    lgpl_count = sum(1 for record in records if record.is_lgpl)
    print(f"§2.5 records {len(records)} binaries, {lgpl_count} under an LGPL term;")
    print(f"§2.5.1 carries {len(entries)} delivery entries, one or more for each of them.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
