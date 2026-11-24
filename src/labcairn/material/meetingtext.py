"""Reading meeting text -- an existing transcript or organised notes.

This is Phase 4's P4-MS third source (execution plan §8.4): **the meeting
material a group already has as text**. The first version reads what is on
disk -- an SRT or WebVTT transcript, or a TXT/Markdown file someone
organised by hand -- and nothing here transcribes audio; automatic
transcription is explicitly not a first-version condition, and §8.4 names
what its later arrival must add (timestamps, speaker uncertainty, proofing
records) so this reader's contract is written to leave that room.

**What it reads.**

* **SRT / WebVTT** -- each cue is one record, carrying its 1-based cue
  order and the timestamp the container spells it with (``00:01:23,400``
  for SRT, ``00:01:23.400`` for WebVTT). The timestamp is kept **as the
  file spells it**: normalising it would be a second rendering of the same
  fact, and the record is evidence of what the file says.
* **TXT / Markdown** -- each blank-line-separated paragraph is one record,
  carrying its 1-based paragraph order in reading order. Markdown headings
  are kept as the paragraph text they open, not stripped: a heading is
  words the author wrote, and dropping them would be an omission that
  leaves no trace.

**Every record carries the provenance §8.3/§8.5 require**: the record's
index (its order in the file), the container's timestamp when it has one,
and a **source fingerprint** that folds the file's content hash and the
record's own address -- so a hit in the search index points back at the
exact entry or paragraph it came from, and re-reading the same file
fingerprints every record the same way.

**What it refuses to do.**

* **It never writes.** The bytes are decoded and closed.
* **It never guesses an encoding.** The shared ``decode_text`` runs: bytes
  that are not text are one recorded problem and no records, never a
  replacement-character decode that puts characters in the record no
  author wrote.
* **It never invents a timestamp.** A paragraph has no time; a cue
  without a readable timestamp is a problem and a record with no time,
  not a cue with a made-up one.
"""

from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass
from types import ModuleType
from typing import Final

from labcairn.material.text import decode_text
from labcairn.material.units import (
    ExtractedUnit,
    ExtractionProblem,
    ExtractionResult,
    register,
)
from labcairn.sources.locators import MeetingTextLocator
from labcairn.sources.source import SourceKind

__all__ = ["MeetingRecord", "MeetingText", "MeetingTextAdapter", "read_meeting_text"]


#: The record formats the reader produces -- the closed vocabulary the
#: locator's ``record_format`` field accepts.
ENTRY_FORMAT: Final[str] = "entry"
PARAGRAPH_FORMAT: Final[str] = "paragraph"

#: SRT timing: ``00:01:23,400 --> 00:01:26,100``. The arrow line separates
#: cues; everything until the next blank line is the cue's text.
_SRT_ARROW: Final[re.Pattern[str]] = re.compile(
    r"^\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})"
)

#: WebVTT timing: ``00:01:23.400 --> 00:01:26.100``. Same shape, but the
#: milliseconds are dot-separated and the hours may be absent.
_VTT_ARROW: Final[re.Pattern[str]] = re.compile(
    r"^\s*((?:\d{1,2}:)?\d{2}:\d{2}\.\d{1,3})\s*-->\s*(?:\d{1,2}:)?\d{2}:\d{2}\.\d{1,3}"
)

#: A WebVTT cue identifier line, which precedes the timing line and is not
#: the cue's text. SRT numbers its cues too, but there the number *is* the
#: cue's ordinal and is dropped in favour of the file's own order.
_VTT_CUE_ID: Final[re.Pattern[str]] = re.compile(r"^cue\d+$", re.IGNORECASE)

#: WebVTT header blocks (``WEBVTT``, ``Kind:``, ``Language:``) and SRT's
#: ordinal numbering are container furniture, not records.
_VTT_HEADER: Final[re.Pattern[str]] = re.compile(r"^(WEBVTT|Kind:|Language:)", re.IGNORECASE)


@dataclass(frozen=True)
class MeetingRecord:
    """One addressable record of meeting text, with §8.3's provenance.

    ``text`` is what the record says. ``record_format`` is which shape it
    is -- a transcript ``entry`` or an organised ``paragraph``.
    ``record_index`` is the record's 1-based order in the file.
    ``timestamp`` is the container's own timestamp string for a transcript
    entry, and ``None`` for a paragraph -- a paragraph has no time, and
    inventing one would be a conclusion the bytes do not carry.

    ``locator`` is the structured address; ``fingerprint`` folds the
    file's content hash and the record's own address, so the same record
    in the same file always fingerprints the same way and a re-ingestion
    is the same rows.
    """

    record_format: str
    record_index: int
    text: str
    locator: MeetingTextLocator
    fingerprint: str
    timestamp: str | None = None


@dataclass(frozen=True)
class MeetingText:
    """Everything the reader found in one meeting-text file.

    ``problems`` is not an afterthought: an adapter that can only report
    success is indistinguishable from one that silently dropped a cue,
    and §8.3's rule -- unreadable input is recorded, never fabricated --
    is carried in this field.
    """

    records: tuple[MeetingRecord, ...] = ()
    problems: tuple[ExtractionProblem, ...] = ()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_record(
    record_format: str,
    record_index: int,
    text: str,
    file_sha: str,
    timestamp: str | None = None,
) -> MeetingRecord:
    """One record, addressed and fingerprinted.

    **The fingerprint folds the file's content hash, the record's shape,
    its index and its timestamp** -- not the text, which two records can
    share. The same record in the same file always fingerprints the same
    way, which is what makes a re-ingestion the same rows.
    """
    digest = hashlib.sha256(
        f"{file_sha}\x00{record_format}\x00{record_index}\x00{timestamp or ''}".encode()
    ).hexdigest()
    return MeetingRecord(
        record_format=record_format,
        record_index=record_index,
        text=text,
        locator=MeetingTextLocator(
            record_format=record_format,  # type: ignore[arg-type]  # closed at the two names above
            record_index=record_index,
            timestamp=timestamp,
        ),
        fingerprint=f"{file_sha[:16]}:{digest[:32]}",
        timestamp=timestamp,
    )


def _parse_srt(data: bytes, file_sha: str) -> MeetingText:
    """Read an SRT transcript: one record per cue, with its timestamp.

    **A cue is its timing line plus the text that follows it**, up to the
    next blank line. The cue's ordinal is the record's index, and the
    timestamp is kept as the file spells it -- SRT's comma milliseconds
    are the container's own rendering, and the record is evidence of what
    the file says, not of what a normaliser would prefer.
    """
    decoded, problems = decode_text(data)
    if decoded is None:
        return MeetingText(problems=problems)

    records: list[MeetingRecord] = []
    found_problems: list[ExtractionProblem] = list(problems)
    blocks = re.split(r"\n\s*\n", decoded.strip())
    index = 0
    for block in blocks:
        lines = [line for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        timestamp: str | None = None
        text_lines: list[str] = []
        for line in lines:
            match = _SRT_ARROW.match(line)
            if match is not None:
                timestamp = match.group(1)
            elif _VTT_CUE_ID.match(line) is None and not line.strip().isdigit():
                text_lines.append(line.strip())
        if timestamp is None:
            # A block with no timing line is not a cue this reader can
            # address: it is recorded, and no record is invented for it.
            found_problems.append(
                ExtractionProblem(
                    code="meeting_srt_cue_untimed",
                    detail=(
                        f"subtitle block {index + 1} carries no timing line; the "
                        f"block is recorded as a problem and no entry is indexed "
                        f"for it, because an untimed block is not a cue the "
                        f"reader can address."
                    ),
                    location=f"entry:{index + 1}",
                )
            )
            index += 1
            continue
        if not text_lines:
            found_problems.append(
                ExtractionProblem(
                    code="meeting_srt_cue_empty",
                    detail=(
                        f"subtitle block {index + 1} is timed but carries no "
                        f"text; it is recorded as a problem rather than "
                        f"indexed as an empty entry."
                    ),
                    location=f"entry:{index + 1}",
                )
            )
            index += 1
            continue
        index += 1
        records.append(
            _make_record(
                ENTRY_FORMAT,
                index,
                " ".join(text_lines),
                file_sha,
                timestamp=timestamp,
            )
        )
    return MeetingText(records=tuple(records), problems=tuple(found_problems))


def _parse_vtt(data: bytes, file_sha: str) -> MeetingText:
    """Read a WebVTT transcript: one record per cue, with its timestamp.

    **The header and cue identifiers are furniture, not records** -- the
    ``WEBVTT`` line, ``Kind:``/``Language:`` metadata and ``cueN`` ids are
    skipped, and each timed block becomes one entry. The timestamp is
    kept as the file spells it -- WebVTT's dot milliseconds -- for the
    same reason SRT's are.
    """
    decoded, problems = decode_text(data)
    if decoded is None:
        return MeetingText(problems=problems)

    records: list[MeetingRecord] = []
    found_problems: list[ExtractionProblem] = list(problems)
    blocks = re.split(r"\n\s*\n", decoded.strip())
    index = 0
    for block in blocks:
        lines = [line for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        if _VTT_HEADER.match(lines[0]) is not None:
            continue
        timestamp: str | None = None
        text_lines: list[str] = []
        for line in lines:
            match = _VTT_ARROW.match(line)
            if match is not None:
                timestamp = match.group(1)
            elif _VTT_CUE_ID.match(line) is None:
                text_lines.append(line.strip())
        if timestamp is None:
            found_problems.append(
                ExtractionProblem(
                    code="meeting_vtt_cue_untimed",
                    detail=(
                        f"cue block {index + 1} carries no timing line; the "
                        f"block is recorded as a problem and no entry is indexed "
                        f"for it, because an untimed block is not a cue the "
                        f"reader can address."
                    ),
                    location=f"entry:{index + 1}",
                )
            )
            index += 1
            continue
        if not text_lines:
            found_problems.append(
                ExtractionProblem(
                    code="meeting_vtt_cue_empty",
                    detail=(
                        f"cue block {index + 1} is timed but carries no text; "
                        f"it is recorded as a problem rather than indexed as "
                        f"an empty entry."
                    ),
                    location=f"entry:{index + 1}",
                )
            )
            index += 1
            continue
        index += 1
        records.append(
            _make_record(
                ENTRY_FORMAT,
                index,
                " ".join(text_lines),
                file_sha,
                timestamp=timestamp,
            )
        )
    return MeetingText(records=tuple(records), problems=tuple(found_problems))


def _parse_paragraphs(data: bytes, file_sha: str) -> MeetingText:
    """Read organised text: one record per blank-line-separated paragraph.

    **Every non-empty paragraph is a record, in reading order**, with its
    1-based ordinal. The paragraph's interior newlines are kept as
    spaces -- the paragraph is one record, and its address is its order,
    not a line within it. A heading line that opens a paragraph is kept as
    the paragraph's first words: it is text the author wrote, and dropping
    it would be an omission that leaves no trace.
    """
    decoded, problems = decode_text(data)
    if decoded is None:
        return MeetingText(problems=problems)

    records: list[MeetingRecord] = []
    blocks = re.split(r"\n\s*\n", decoded.strip())
    index = 0
    for block in blocks:
        text = " ".join(line.strip() for line in block.splitlines() if line.strip())
        if not text:
            continue
        index += 1
        records.append(_make_record(PARAGRAPH_FORMAT, index, text, file_sha))
    return MeetingText(records=tuple(records), problems=problems)


def read_meeting_text(data: bytes, *, container: str) -> MeetingText:
    """Read meeting text by its container: ``srt``, ``vtt`` or ``paragraphs``.

    **The bytes are never modified.** They are decoded and closed; the
    caller keeps the original and this function keeps nothing of it.

    A container this reader does not name is refused rather than guessed
    at -- the caller says what the file is, and the reader reads it as
    that. The application layer derives the container from the file's
    extension, which is the one place a guess is a *decision* rather than
    a fabrication.
    """
    if container == "srt":
        return _parse_srt(data, _sha256(data))
    if container == "vtt":
        return _parse_vtt(data, _sha256(data))
    if container == "paragraphs":
        return _parse_paragraphs(data, _sha256(data))
    raise ValueError(
        f"no meeting-text reader for container {container!r}; the containers are "
        f"'srt', 'vtt' and 'paragraphs'. A container the reader does not name is "
        f"refused rather than guessed at."
    )


@register
class MeetingTextAdapter:
    """One record per transcript entry or organised paragraph, addressed.

    **Every record is a unit, and every unit carries its address.** A
    transcript's entries and an organiser's paragraphs are all citable
    text: a hit in the search index points back at the entry or paragraph
    it came from, which is §8.4's requirement and the adapter's whole
    shape.
    """

    kind = SourceKind.MEETING_TEXT

    def extract(self, data: bytes) -> ExtractionResult:
        """Read the bytes as meeting text, container sniffed from content.

        **The sniff is structural, not a guess about meaning**: a file
        that opens ``WEBVTT`` is WebVTT, a file whose first cue line
        carries an SRT arrow is SRT, and everything else is organised
        text. The application layer may name the container itself, which
        is the path an ingest takes; this adapter is the registry-facing
        shape, and it has to decide from the bytes alone.
        """
        head = data[:4096]
        if head.startswith(b"\xef\xbb\xbf"):
            head = head[3:]
        sample = head.lstrip()
        if sample.startswith(b"WEBVTT"):
            meeting = read_meeting_text(data, container="vtt")
        elif _SRT_ARROW.match(sample.split(b"\n", 1)[0].decode("utf-8", "replace")) is not None:
            meeting = read_meeting_text(data, container="srt")
        else:
            meeting = read_meeting_text(data, container="paragraphs")
        units = tuple(
            ExtractedUnit(locator=record.locator, text=record.text) for record in meeting.records
        )
        return ExtractionResult(units=units, problems=meeting.problems)

    def libraries(self) -> dict[str, str]:
        """No dependency beyond the standard library.

        The reader uses :mod:`re` and the shared text decoder, both of
        which ship with the project. **Adding a caption library would add
        exactly the behaviour this reader exists to avoid**: one that
        reads what its author's use case saw, and silently drops the rest.
        """
        return {}

    def source_modules(self) -> tuple[ModuleType, ...]:
        return (sys.modules[__name__],)
