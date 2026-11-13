"""Read NOTICE's replaceability record, and check it against the bytes it names.

NOTICE §2.5.1 records the LGPL-2.1 §6(b) replaceability measurement as a state, a
date, three modified plug-ins with byte counts and sha256 values, a table of the
installers built with them and the exit codes their runs returned, and four
observation files the installs produced. Every one of those is a claim about a
file or a process, so this tool reads the claims out of the record and, where the
artefacts are on the machine, hashes the files and compares.

Two separate things it can fail for, deliberately:

  * the record's own shape — a state with no date, a variant with no sha256, an
    installer row with no exit code, a measurement with no observed difference, or
    no paragraph saying what the measurement does not show;
  * the bytes behind it — a file whose sha256 is not the one §2.5.1 prints.

It never rebuilds anything and never supplies a number the record does not print.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
NOTICE_PATH: Final[Path] = REPO_ROOT / "NOTICE"

#: A 64-hex-digit sha256.
FULL_SHA256: Final[str] = r"[0-9a-f]{64}"

#: The §2.5.1 replaceability item and the state it states. The state is the thing
#: the rest of this file's checks hinge on: `NOT MEASURED` records a route, and
#: `MEASURED <date>` records a result. The bold opens before the heading and closes
#: after the state, which is how §2.5.1 writes every one of its item headings, and
#: the item wraps across lines, so the span is allowed to cross a newline.
REPLACEABILITY_ITEM: Final[re.Pattern[str]] = re.compile(
    r"\*\*Replaceability \(§6\(b\)[\s\S]*?—\s*(?P<state>NOT\s+MEASURED|MEASURED[^.]{0,60})\.\*\*"
)

#: The date a measurement says it was taken on.
MEASUREMENT_DATE: Final[re.Pattern[str]] = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")

#: A modified plug-in, as §2.5.1 names it: a file name, a byte count, and its
#: sha256 — which §2.5.1 writes on the following line, so the value is read from
#: the item's own continuation rather than assumed to sit on the same line.
VARIANT_CLAIM: Final[re.Pattern[str]] = re.compile(
    r"^\s{4,6}\* `(?P<name>[A-Za-z0-9_.-]+\.dll)` — (?P<bytes>[\d,]+) bytes, sha256\s*$",
    re.MULTILINE,
)

#: An observation file the record says an install produced.
OBSERVATION_CLAIM: Final[re.Pattern[str]] = re.compile(
    r"^\s{4,8}\* `(?P<name>observations[A-Za-z0-9_.-]*\.txt)` — "
    r"(?P<bytes>[\d,]+) bytes, sha256\s*$",
    re.MULTILINE,
)

#: One installer row of §2.5.1's table: a label, the installer's size, its sha256,
#: the sha256 prefix of the plug-in it carries, and the two exit codes. The table
#: is indented under the bullet it belongs to, which is why the row is not required
#: to start at column zero: a pattern anchored there reads no row out of a record
#: that states four of them.
INSTALLER_ROW: Final[re.Pattern[str]] = re.compile(
    r"^\s*\| (?P<label>[^|]+?) \| (?P<bytes>[\d,]+) \| `(?P<sha>[0-9a-f]{64})` \| "
    r"`(?P<plugin>[0-9a-f]{8})…` \| (?P<install_exit>\d+) \| (?P<files>\d+) \| "
    r"(?P<uninstall_exit>\d+) \|$",
    re.MULTILINE,
)

#: The paragraph that states the measurement's limits. A measurement that does not
#: say what it does not show is a claim dressed as a measurement.
LIMITS_HEADING: Final[str] = "**What this evidence does not show.**"

#: A sha256 that is almost right: 63 or 65 hex digits, or a value with a non-hex
#: character where a digit belongs.
NEAR_SHA: Final[re.Pattern[str]] = re.compile(r"\b[0-9a-f]{60,68}\b")


#: §2.5's own `StdUtils.dll` entry, whose sha256 is the shipped file's. §2.5.1's
#: replaceability item is about modified copies of that file, so the shipped hash is
#: the one value the item's own claims have to differ from.
SHIPPED_BINARY_ENTRY: Final[re.Pattern[str]] = re.compile(
    r"^ {2}StdUtils\.dll — [\d,]+ bytes$[\s\S]{0,400}?^ {4}sha256\s+(?P<sha>[0-9a-f]{64})$",
    re.MULTILINE,
)


def shipped_plugin_sha256(notice_text: str) -> str | None:
    """The sha256 §2.5 records for the `StdUtils.dll` it distributes."""
    match = SHIPPED_BINARY_ENTRY.search(notice_text)
    return match.group("sha") if match else None


def _section(notice_text: str, heading: str) -> str:
    """One NOTICE subsection, up to the next `N.M  Title` heading."""
    lines = notice_text.split("\n")
    start = next((i for i, line in enumerate(lines) if line.startswith(f"{heading}  ")), -1)
    if start < 0:
        raise RuntimeError(f"NOTICE has no subsection {heading}")
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if re.match(r"^\d+(\.\d+)*\.?  \S", lines[index]):
            end = index
            break
    return "\n".join(lines[start:end])


def replaceability_section(notice_text: str) -> str:
    return _section(notice_text, "2.5.1")


@dataclass
class ArtefactClaim:
    """One file §2.5.1 names, with the size and hash it states for it."""

    kind: str
    name: str
    recorded_bytes: int
    recorded_sha256: str | None

    def problems(self) -> list[str]:
        found: list[str] = []
        if self.recorded_sha256 is None:
            found.append(
                f"{self.kind} {self.name}: §2.5.1 gives it a byte count and no sha256, so "
                "the claim names bytes it never hashes"
            )
        elif len(self.recorded_sha256) != 64:
            found.append(
                f"{self.kind} {self.name}: §2.5.1 states a sha256 of "
                f"{len(self.recorded_sha256)} characters, not 64"
            )
        return found


@dataclass
class InstallerRow:
    """One installer §2.5.1 says it built, with the exit codes it says it returned."""

    label: str
    recorded_bytes: int
    recorded_sha256: str
    plugin_sha_prefix: str
    install_exit: str
    installed_files: int
    uninstall_exit: str


def artefact_claims(notice_text: str, pattern: re.Pattern[str], kind: str) -> list[ArtefactClaim]:
    """Every `name — N bytes, sha256` claim of one kind, with the hash from its next line."""
    section = replaceability_section(notice_text)
    claims: list[ArtefactClaim] = []
    for match in pattern.finditer(section):
        tail = section[match.end() : match.end() + 400]
        sha_match = re.match(rf"\s*`({FULL_SHA256})`", tail)
        claims.append(
            ArtefactClaim(
                kind=kind,
                name=match.group("name"),
                recorded_bytes=int(match.group("bytes").replace(",", "")),
                recorded_sha256=sha_match.group(1) if sha_match else None,
            )
        )
    return claims


def variant_claims(notice_text: str) -> list[ArtefactClaim]:
    return artefact_claims(notice_text, VARIANT_CLAIM, "plug-in")


def observation_claims(notice_text: str) -> list[ArtefactClaim]:
    return artefact_claims(notice_text, OBSERVATION_CLAIM, "observation")


def installer_rows(notice_text: str) -> list[InstallerRow]:
    section = replaceability_section(notice_text)
    return [
        InstallerRow(
            label=match.group("label").strip(),
            recorded_bytes=int(match.group("bytes").replace(",", "")),
            recorded_sha256=match.group("sha"),
            plugin_sha_prefix=match.group("plugin"),
            install_exit=match.group("install_exit"),
            installed_files=int(match.group("files")),
            uninstall_exit=match.group("uninstall_exit"),
        )
        for match in INSTALLER_ROW.finditer(section)
    ]


def replaceability_state(notice_text: str) -> str:
    """§2.5.1's own statement of where replaceability stands."""
    match = REPLACEABILITY_ITEM.search(replaceability_section(notice_text))
    if not match:
        raise RuntimeError(
            "NOTICE §2.5.1 states no replaceability item — the read found nothing to check"
        )
    return match.group("state").strip()


def record_problems(notice_text: str) -> list[str]:
    """Every way the record can state a measurement it does not support."""
    section = replaceability_section(notice_text)
    state = replaceability_state(notice_text)
    if state == "NOT MEASURED":
        return []

    problems: list[str] = []
    if not MEASUREMENT_DATE.search(state):
        problems.append(
            f"§2.5.1 states replaceability as {state!r} with no date it was measured on"
        )

    variants = variant_claims(notice_text)
    observations = observation_claims(notice_text)
    rows = installer_rows(notice_text)

    if not variants:
        problems.append(
            "§2.5.1 calls this a measurement and names no modified plug-in, so there is no "
            "modified byte anywhere in the record"
        )
    for claim in variants:
        problems.extend(claim.problems())

    # The item is about modified copies of the file §2.5 distributes, so its own claims
    # have to differ from the hash §2.5 prints for that file, and the installers it lists
    # have to carry one of the plug-ins the item names (or the shipped one, for a control
    # row). Those are checks inside the record: they hold whether or not the artefacts are
    # on the machine, and they are the ones a mistyped prefix or a copied hash trips.
    shipped = shipped_plugin_sha256(notice_text)
    if shipped is None:
        problems.append(
            "§2.5.1's replaceability item is about copies of the shipped plug-in and §2.5 "
            "states no sha256 for StdUtils.dll to compare them against"
        )
    recorded_hashes = [
        claim.recorded_sha256 for claim in variants if claim.recorded_sha256 is not None
    ]
    for claim in variants:
        if shipped is not None and claim.recorded_sha256 == shipped:
            problems.append(
                f"{claim.kind} {claim.name}: §2.5.1 records it as the modified plug-in and "
                f"hashes it to {claim.recorded_sha256}, which is the sha256 §2.5 records for "
                "the shipped file, so the entry names unmodified bytes"
            )
    for row in rows:
        prefix_matches_a_variant = any(
            hash_value.startswith(row.plugin_sha_prefix) for hash_value in recorded_hashes
        )
        prefix_is_the_shipped_file = shipped is not None and shipped.startswith(
            row.plugin_sha_prefix
        )
        if not prefix_matches_a_variant and not prefix_is_the_shipped_file:
            problems.append(
                f"installer {row.label!r}: §2.5.1 says it carries plug-in "
                f"{row.plugin_sha_prefix}…, and no plug-in the item names hashes to a value "
                "beginning with those characters"
            )

    if not rows:
        problems.append(
            "§2.5.1 names modified plug-ins and no installer built with one, so the record "
            "states a route rather than a run"
        )
    for row in rows:
        if not re.fullmatch(r"\d+", row.install_exit):
            problems.append(f"installer {row.label!r}: no exit code stated for its install run")
        elif row.install_exit != "0":
            problems.append(
                f"installer {row.label!r}: its install run states exit {row.install_exit}, where "
                "the measurement's claim is that an installer carrying a modified plug-in "
                "completed the installation"
            )
        if not re.fullmatch(r"\d+", row.uninstall_exit):
            problems.append(f"installer {row.label!r}: no exit code stated for its uninstall run")
        elif row.uninstall_exit != "0":
            problems.append(
                f"installer {row.label!r}: its uninstall states exit {row.uninstall_exit}, where "
                "the measurement's claim is that each install was uninstalled"
            )
        if row.installed_files <= 0:
            problems.append(
                f"installer {row.label!r}: states {row.installed_files} files installed, which "
                "is not an install"
            )

    if not observations:
        problems.append(
            "§2.5.1 states a measurement and no observed difference, so nothing in the record "
            "shows the modified plug-in was the one used"
        )
    for claim in observations:
        problems.extend(claim.problems())

    if LIMITS_HEADING not in section:
        problems.append(
            "§2.5.1 states a replaceability measurement and no paragraph saying what it does "
            f"not show ({LIMITS_HEADING})"
        )

    # A sha256 that is almost a sha256: the shape that a transcription error leaves.
    for value in NEAR_SHA.findall(section):
        if len(value) != 64:
            problems.append(f"§2.5.1 prints a {len(value)}-character hex value {value!r}")

    return problems


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def check_against_directory(directory: Path, claims: list[ArtefactClaim]) -> list[str]:
    """Hash the files in `directory` against the sha256 values §2.5.1 records."""
    if not directory.is_dir():
        return [f"{directory} is no directory, so no recorded artefact could be hashed"]
    problems: list[str] = []
    for claim in claims:
        candidate = directory / claim.name
        if not candidate.is_file():
            problems.append(
                f"{claim.kind} {claim.name}: §2.5.1 records {claim.recorded_bytes:,} bytes with "
                f"sha256 {(claim.recorded_sha256 or 'none')!r}, and {candidate} is not a file, "
                "so that sha256 was not measured against any bytes here"
            )
            continue
        size = candidate.stat().st_size
        if size != claim.recorded_bytes:
            problems.append(
                f"{claim.kind} {claim.name}: §2.5.1 records {claim.recorded_bytes:,} bytes; "
                f"{candidate} is {size}"
            )
        if claim.recorded_sha256 is not None:
            actual = _sha256(candidate)
            if actual != claim.recorded_sha256:
                problems.append(
                    f"{claim.kind} {claim.name}: §2.5.1 records sha256 {claim.recorded_sha256}; "
                    f"{candidate} is {actual}"
                )
    return problems


def render(notice_text: str) -> str:
    """What the record states, read out of it."""
    state = replaceability_state(notice_text)
    dates = MEASUREMENT_DATE.findall(state)
    variants = variant_claims(notice_text)
    observations = observation_claims(notice_text)
    rows = installer_rows(notice_text)

    lines = [
        "LGPL-2.1 §6(b) replaceability, read out of NOTICE §2.5.1.",
        f"§2.5.1 states replaceability as: {state}",
        f"date stated: {', '.join(dates) if dates else 'none'}",
        f"modified plug-ins named with bytes and sha256: {len(variants)}",
    ]
    for claim in variants:
        lines.append(
            f"  {claim.name} — {claim.recorded_bytes:,} bytes, sha256 "
            f"{claim.recorded_sha256 or '(none stated)'}"
        )
    lines.append(f"installers built with them: {len(rows)}")
    for row in rows:
        lines.append(
            f"  {row.label} — {row.recorded_bytes:,} bytes, sha256 {row.recorded_sha256}, "
            f"carrying plug-in {row.plugin_sha_prefix}…, install exit {row.install_exit}, "
            f"{row.installed_files} files, uninstall exit {row.uninstall_exit}"
        )
    lines.append(f"observation files the installs produced: {len(observations)}")
    for claim in observations:
        lines.append(
            f"  {claim.name} — {claim.recorded_bytes:,} bytes, sha256 "
            f"{claim.recorded_sha256 or '(none stated)'}"
        )
    if LIMITS_HEADING in replaceability_section(notice_text):
        lines.append("the record states what the measurement does not show")
    else:
        lines.append("the record states no limits of the measurement")
    return "\n".join(lines)


def check_installer_hashes(directory: Path, rows: list[InstallerRow]) -> list[str]:
    """Hash every `Setup 0.0.0.exe` under `directory` against the sha256 values the table states.

    The installers are 124-megabyte build products and are not in the checkout, so the
    table's own hashes are the only part of it that can be checked against bytes. What this
    does is collect the installers on the machine and require each row's stated hash to be
    one of them: a row whose hash is a transcription error matches nothing, and a reader
    that matched rows to files by position rather than by hash would not notice.
    """
    if not directory.is_dir():
        return [f"{directory} is no directory, so no installer could be hashed"]
    candidates: dict[str, Path] = {}
    for path in directory.rglob("*Setup 0.0.0.exe"):
        if path.is_file():
            candidates[_sha256(path)] = path
    if not candidates:
        return [f"no file named `*Setup 0.0.0.exe` was found under {directory}"]

    problems: list[str] = []
    for row in rows:
        if row.recorded_sha256 not in candidates:
            problems.append(
                f"installer {row.label!r}: §2.5.1 records it as sha256 {row.recorded_sha256}; "
                f"no installer under {directory} hashes to that value "
                f"(measured: {', '.join(sorted(h[:12] for h in candidates))})"
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read NOTICE §2.5.1's replaceability record and check it against bytes."
    )
    parser.add_argument(
        "--notice",
        metavar="FILE",
        default=str(NOTICE_PATH),
        help="the NOTICE to read (default: this repository's)",
    )
    parser.add_argument(
        "--check-artefacts",
        metavar="DIR",
        help="directory holding the modified plug-ins and observation files "
        "§2.5.1 names, hashed against the record",
    )
    parser.add_argument(
        "--check-installers",
        metavar="DIR",
        help="directory holding the installer build products §2.5.1's table "
        "records, hashed against the sha256 values that table states",
    )
    arguments = parser.parse_args(argv)

    notice_path = Path(arguments.notice)
    try:
        notice_text = notice_path.read_text(encoding="utf-8")
        state = replaceability_state(notice_text)
    except (OSError, RuntimeError) as error:
        print(f"the record could not be read: {error}", file=sys.stderr)
        return 1

    print(render(notice_text))

    problems = record_problems(notice_text)
    if problems:
        print("the replaceability record is incomplete:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    if state == "NOT MEASURED":
        print("§2.5.1 records the route and no measurement, and asks for nothing further")
        return 0

    if arguments.check_artefacts:
        claims = variant_claims(notice_text) + observation_claims(notice_text)
        byte_problems = check_against_directory(Path(arguments.check_artefacts), claims)
        if byte_problems:
            print("the bytes behind the record:", file=sys.stderr)
            for problem in byte_problems:
                print(f"  {problem}", file=sys.stderr)
            return 1
        measured = ", ".join(claim.name for claim in claims)
        print(f"measured: {measured} — each hashed to the sha256 §2.5.1 records")

    if arguments.check_installers:
        installer_problems = check_installer_hashes(
            Path(arguments.check_installers), installer_rows(notice_text)
        )
        if installer_problems:
            print("the installers behind the record:", file=sys.stderr)
            for problem in installer_problems:
                print(f"  {problem}", file=sys.stderr)
            return 1
        print(
            f"measured: {len(installer_rows(notice_text))} installers under "
            f"{arguments.check_installers} — each hashed to the sha256 its table row states"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
