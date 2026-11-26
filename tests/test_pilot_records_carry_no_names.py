"""The pilot's own records carry no name, and the tree watches them for it.

**What this file watches.** The pilot's records are the documents this
project writes about real material: the desensitisation measurement, the
import, the first real request, the first whole round, the removal and
its witnesses, the report checks, the replay, the CLI's own request, and
the reviews of the batches that closed the gaps. **They are English, and
they carry counts, digests, ids and timings — never a person's name.**

**Why it is a separate file.** The preparation papers have their own
witness already (``tests/test_pilot_decisions.py`` holds the owner-decision
form and the three drafts to no Chinese, no fullwidth punctuation and no
identifying pattern). **The measurement records were not covered by
anything**, and that gap was not theoretical: the replay's record carried
the workspace's own issue key, version id and file name for the second
corpus, and all three carried a person's name — a Chinese name, in a
Chinese document, copied out of a workspace that is allowed to hold it and
into a tree that is not. The record was corrected and the names were
redacted; **the rule that stops it happening again is this file.**

**Why a Han character is the test.** The corpus is Chinese. A run of Han
characters in an English record is not a style question — it is a
transcription, and the only Han text in this repository that is legitimate
is the project's own Chinese documents, which are not in these records'
scope. **The same applies to the fullwidth enumeration comma** (the mark a
half-translated line leaves behind) and to the identifier shapes a real
name or affiliation leaves behind: an email address, a phone number, a
grant or project number, an ORCID.

**What it does not say.** It does not say the records are complete, and it
does not say the ids in them are the right ones. A digest identifies bytes
and an id identifies a row; this file says that neither of them may be a
person's name.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest

#: The pilot's measurement records, and the reviews of the batches that
#: closed what the records found. Every file that names the material.
RECORDS: Final[tuple[Path, ...]] = (
    *sorted(Path("docs/acceptance").glob("LC-P4-PILOT-*.md")),
    *sorted(Path("docs/acceptance").glob("batch-1[3-5]-review-*.md")),
)

#: A maximal run of Han characters, written as code points rather than as
#: the characters themselves: **the tree's Chinese is measured**, and a
#: witness that spent the budget it exists to protect would break its own
#: rule before it could keep it.
#: A maximal run of Han characters — the same shape
#: ``tests/test_pilot_decisions.py`` holds the preparation papers to.
HAN_RUN: Final = re.compile(
    "["
    + chr(0x3400)
    + "-"
    + chr(0x4DBF)
    + chr(0x4E00)
    + "-"
    + chr(0x9FFF)
    + chr(0xF900)
    + "-"
    + chr(0xFAFF)
    + "]+"
)

#: A CJK fullwidth enumeration comma — the mark a half-translated line
#: leaves behind in English prose.
FULLWIDTH_COMMA: Final = re.compile(chr(0x3001))

#: Identifier shapes the records must not carry, in the same shapes
#: ``tests/test_pilot_decisions.py`` and ``tests/test_pilot_runbook.py``
#: hold the preparation papers and the trial's execution records to.
LEAK_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("email address", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("phone number", re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")),
    (
        "grant/project number prefix",
        re.compile(
            r"(?:Project|Grant|Contract)\s*(?:No\.?|Number|#)\s*[:.]?\s*"
            r"(?=[A-Za-z0-9/-]*\d)[A-Za-z0-9][-A-Za-z0-9/]{3,}",
            re.IGNORECASE,
        ),
    ),
    ("long number after No.", re.compile(r"\bNo\.?\s*[:.]?\s*\d{6,}", re.IGNORECASE)),
    ("ORCID", re.compile(r"\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b")),
)


def _read(relative: Path) -> str:
    return relative.read_text(encoding="utf-8")


@pytest.mark.parametrize("relative", RECORDS, ids=lambda p: p.name)
def test_the_pilot_records_carry_no_chinese(relative: Path) -> None:
    """The pilot's records are English throughout.

    **What would make this red.** A Han character run in one of them —
    which is a transcription of the corpus, or of a name inside the
    workspace's own labels. The corpus is Chinese; the records are not,
    and the rule that says so is the desensitisation checklist's.
    """
    runs = HAN_RUN.findall(_read(relative))
    assert not runs, (
        f"{relative} carries Chinese ({runs[:5]}); the pilot's records are "
        "English, and the material stays outside the tree"
    )


@pytest.mark.parametrize("relative", RECORDS, ids=lambda p: p.name)
def test_the_pilot_records_carry_no_fullwidth_punctuation(relative: Path) -> None:
    """No CJK enumeration comma slips into the English prose.

    **What would make this red.** The mark a half-translated line leaves
    behind — the same mark the preparation papers are held to.
    """
    assert not FULLWIDTH_COMMA.search(_read(relative)), (
        f"{relative} carries a CJK enumeration comma; its prose is English"
    )


@pytest.mark.parametrize("relative", RECORDS, ids=lambda p: p.name)
@pytest.mark.parametrize(
    ("kind", "pattern"),
    LEAK_PATTERNS,
    ids=lambda p: p if isinstance(p, str) else "",
)
def test_the_pilot_records_carry_no_identifying_pattern(
    relative: Path,
    kind: str,
    pattern: re.Pattern[str],
) -> None:
    """No email address, phone number, project number or ORCID.

    **What would make this red.** An identifier shape that a real name or
    affiliation leaves behind, copied out of the workspace along with the
    numbers. The counts and digests in these records need none of them.
    """
    assert not pattern.search(_read(relative)), (
        f"{relative} carries a {kind}; the pilot's records hold counts, digests, ids and timings"
    )
