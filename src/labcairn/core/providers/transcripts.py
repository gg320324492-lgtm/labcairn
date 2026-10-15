"""Scripted transcripts — the reusable fixture set, one per situation worth reproducing.

Named for the *situation* each reproduces, not for the assertion it happens to
serve today, so LC-P1-03's provider tests and LC-P1-13's end-to-end path can
build on these instead of writing their own.

Scope (deliberate, from docs/plans/LC-P1-01-task-breakdown.md §5.3)
------------------------------------------------------------------
**LC-P1-01 ships provider transcripts only.** PDF/CSV/XLSX source material,
locator fixtures and evidence fixtures belong to LC-P1-08 / LC-P1-09. Nothing in
this module should grow a scientific payload; that boundary is what stops a
later task from "helpfully" adding real material and having it look like an
LC-P1-08 deliverable.

The four ``usage_*`` transcripts exist because they are the four rows of the
contrast table in §5.4, and the third row is the one that earns the file:

===========================  ==============================  ==========================
``usage`` block              pydantic-ai (``usage.py:89-93``)  LabCairn
===========================  ==============================  ==========================
absent                       ``0``                           ``Unknown(PROVIDER_OMITTED)``
``{}``                       ``0``                           ``Unknown(PROVIDER_OMITTED)``
``{"input_tokens": 0}``      ``0``                           ``Known(0)`` — a zero is a measurement
``{"input_tokens": 12}``     ``12``                          ``Known(12)``
===========================  ==============================  ==========================

Row three is the load-bearing one: it proves the fake is not merely
"absent ⇒ unknown", and it pins ADR-0002's ``coerce`` contract in both
directions.

``tool_call_ignored`` is the ADR-0002 §A4 regression, staged early and without a
probe: a provider offered a tool and answers in prose anyway. There is no
capability probe in LC-P1-01 (amendment C-3), so nothing here *decides* whether
that is acceptable — but the transcript makes it assertable today that the fake
produces **zero** tool calls from prose and never parses one out. That is the
behaviour ``NonNativeToolCallingMixin.post_response_non_fc`` would violate, and
LC-P1-03 inherits a ready-made fixture for it.
"""

from __future__ import annotations

from typing import Final

from labcairn.core.providers.fake import Transcript, TranscriptStep
from labcairn.core.providers.protocol import ModelRequest

# --- the request that produces each usage situation ------------------------
# Kept shared so the four usage transcripts differ *only* in their `usage`
# block. If they also differed in their prompt, a failure would not tell you
# which variable moved.
_USAGE_REQUEST: Final[ModelRequest] = ModelRequest(prompt="Summarise the attached file.")

#: Offered to the model. Two tools so a transcript can also show one being
#: ignored.
_TOOL_REQUEST: Final[ModelRequest] = ModelRequest(
    prompt="How many rows does results.csv have?",
    tools=("read_csv", "count_rows"),
)

# --- the usage situations --------------------------------------------------

#: Provider reported real numbers. → ``Known(12)`` / ``Known(34)``.
USAGE_PRESENT: Final[Transcript] = Transcript.of(
    "usage_present",
    [
        TranscriptStep.of(
            "usage_present",
            _USAGE_REQUEST,
            {
                "text": "The file has 12 columns and 34 rows.",
                "tool_calls": [],
                "usage": {"input_tokens": 12, "output_tokens": 34},
            },
        )
    ],
)

#: Provider reported an explicit zero. → ``Known(0)``, never ``Unknown``.
#: The provider said "zero"; zero is a measurement, not a missing one.
USAGE_ZERO: Final[Transcript] = Transcript.of(
    "usage_zero",
    [
        TranscriptStep.of(
            "usage_zero",
            _USAGE_REQUEST,
            {
                "text": "The request carried no input.",
                "tool_calls": [],
                "usage": {"input_tokens": 0, "output_tokens": 0},
            },
        )
    ],
)

#: No ``usage`` block at all. → every field ``Unknown(PROVIDER_OMITTED)``.
#: This is the row upstream answers with zeros.
USAGE_ABSENT: Final[Transcript] = Transcript.of(
    "usage_absent",
    [
        TranscriptStep.of(
            "usage_absent",
            _USAGE_REQUEST,
            {"text": "The file has 12 columns.", "tool_calls": []},
        )
    ],
)

#: ``"usage": {}`` — the block exists and says nothing. → still
#: ``Unknown(PROVIDER_OMITTED)``. An empty object is an absent measurement
#: wearing a present measurement's clothes.
USAGE_EMPTY: Final[Transcript] = Transcript.of(
    "usage_empty",
    [
        TranscriptStep.of(
            "usage_empty",
            _USAGE_REQUEST,
            {"text": "The file has 12 columns.", "tool_calls": [], "usage": {}},
        )
    ],
)

#: The block is present and a field is present in it, but the value is not a
#: usable non-negative integer (here: a string). → ``Unknown(EXTRACTION_FAILED)``.
#: Distinct from ``USAGE_ABSENT`` because data *arrived*; we could not read it.
#: One fixture per failure kind is the minimal form that keeps the two
#: indistinguishable at the top and distinct where it matters.
USAGE_MALFORMED: Final[Transcript] = Transcript.of(
    "usage_malformed",
    [
        TranscriptStep.of(
            "usage_malformed",
            _USAGE_REQUEST,
            {
                "text": "The file has 12 columns.",
                "tool_calls": [],
                "usage": {"input_tokens": "12", "output_tokens": -3},
            },
        )
    ],
)

# --- the tool-calling situations ------------------------------------------

#: The provider honours ``tools``. → exactly one parsed tool call.
TOOL_CALL_OK: Final[Transcript] = Transcript.of(
    "tool_call_ok",
    [
        TranscriptStep.of(
            "tool_call_ok",
            _TOOL_REQUEST,
            {
                "text": "",
                "tool_calls": [{"name": "count_rows", "arguments": {"path": "results.csv"}}],
                "usage": {"input_tokens": 40, "output_tokens": 9},
            },
        )
    ],
)

#: The provider ignores ``tools`` and answers in prose. → **zero** tool calls.
#: The prose names a file that looks like it could have been a call; the fake
#: does not care. Parsing intent out of model prose is the injection surface
#: ADR-0002 §A4 refuses, and this fixture is where that refusal becomes
#: checkable. LC-P1-03 gates on it with a real probe.
TOOL_CALL_IGNORED: Final[Transcript] = Transcript.of(
    "tool_call_ignored",
    [
        TranscriptStep.of(
            "tool_call_ignored",
            _TOOL_REQUEST,
            {
                "text": "To find out, call read_csv on results.csv and count the rows.",
                "tool_calls": [],
                "usage": {"input_tokens": 41, "output_tokens": 18},
            },
        )
    ],
)

# --- a multi-step transcript ----------------------------------------------

#: Two exchanges in one script. Exists so the cursor, the ordering and the
#: byte-identity comparison are exercised over a *sequence* rather than a
#: single lookup — one-step transcripts cannot distinguish "replays in order"
#: from "replays at all". LC-P1-13's e2e path is the intended consumer.
TOOL_THEN_TEXT: Final[Transcript] = Transcript.of(
    "tool_then_text",
    [
        TranscriptStep.of(
            "tool_then_text.step1",
            _TOOL_REQUEST,
            {
                "text": "",
                "tool_calls": [{"name": "count_rows", "arguments": {"path": "results.csv"}}],
                "usage": {"input_tokens": 40, "output_tokens": 9},
            },
        ),
        TranscriptStep.of(
            "tool_then_text.step2",
            ModelRequest(
                prompt="You called count_rows and it returned 128. Now answer in one sentence.",
            ),
            {
                "text": "results.csv has 128 rows.",
                "tool_calls": [],
                "usage": {"input_tokens": 55, "output_tokens": 11},
            },
        ),
    ],
)

#: Every transcript above, for tests that sweep the whole set. A tuple, so a new
#: fixture added here is swept automatically rather than needing to be remembered.
ALL_TRANSCRIPTS: Final[tuple[Transcript, ...]] = (
    USAGE_PRESENT,
    USAGE_ZERO,
    USAGE_ABSENT,
    USAGE_EMPTY,
    USAGE_MALFORMED,
    TOOL_CALL_OK,
    TOOL_CALL_IGNORED,
    TOOL_THEN_TEXT,
)
