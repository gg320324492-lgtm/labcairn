"""Model providers and the tri-state quantities that describe what they cost.

LC-P1-01 ships two things under this package and nothing else:

* :mod:`labcairn.core.providers.usage` — ``Known`` / ``Unknown`` / ``UsageValue`` /
  ``UnknownReason``, the four value types amendment C-3 permits, so a missing
  measurement can be told apart from a measured zero.
* :mod:`labcairn.core.providers.fake` — ``FakeProvider``, a scripted replay that
  needs no API key, no network and no wall clock, discharging the work order's
  *"A FakeProvider and deterministic demo fixtures must run without paid APIs."*

and the seam between them: :class:`~labcairn.core.providers.protocol.ModelProvider`,
which a real adapter drops in behind in LC-P1-03 without any caller changing.

**Not in this package, and not missing by accident** — capability probes,
provider adapters, budget ceilings and cancel/timeout are LC-P1-03 (amendment
C-3). Neither is LC-P1-02's data model (``Task`` / ``Run`` / ``Stage`` /
``Evidence``); a transcript records what a *model* said, which is deliberately
not the same thing as what a *run* did.

Package placement note: docs/plans/LC-P1-01-task-breakdown.md T08 sketched these
under ``src/labcairn/core/providers/``. The LC-P1-01 file-ownership assignment
for this work placed them at ``src/labcairn/providers/**`` instead, and
``src/labcairn/core/`` was out of scope to edit. The public import path is
therefore ``labcairn.core.providers.*``. If the coordinator prefers
``labcairn.core.providers``, that is a directory move plus a re-export shim;
the package deliberately keeps no imports pointing at its own location beyond
absolute ``labcairn.core.providers.*`` paths, so nothing outside it needs editing.
"""

from __future__ import annotations

from labcairn.core.providers.fake import (
    Exchange,
    FakeProvider,
    ScriptDeviationError,
    Transcript,
    TranscriptExhaustedError,
    TranscriptStep,
)
from labcairn.core.providers.protocol import (
    USAGE_FIELDS,
    MalformedResponseError,
    ModelProvider,
    ModelRequest,
    ModelResponse,
    ToolCall,
    UsageReport,
    canonical_json,
)
from labcairn.core.providers.usage import (
    Known,
    Unknown,
    UnknownReason,
    UnmeasuredQuantityError,
    UsageValue,
    format_usage,
    merge,
    require_known,
    usage_from_wire,
    usage_to_json,
)

__all__ = [
    "USAGE_FIELDS",
    "Exchange",
    "FakeProvider",
    "Known",
    "MalformedResponseError",
    "ModelProvider",
    "ModelRequest",
    "ModelResponse",
    "ScriptDeviationError",
    "ToolCall",
    "Transcript",
    "TranscriptExhaustedError",
    "TranscriptStep",
    "Unknown",
    "UnknownReason",
    "UnmeasuredQuantityError",
    "UsageReport",
    "UsageValue",
    "canonical_json",
    "format_usage",
    "merge",
    "require_known",
    "usage_from_wire",
    "usage_to_json",
]
