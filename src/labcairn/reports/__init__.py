"""``labcairn.reports`` — the receipt side of the ledger.

:docs:`ARCHITECTURE.md` ("Identity and authority") puts the artifact boundary in
one line: *"ArtifactReceipt records generated outputs and their provenance."*
This package is that, and nothing else — no rendering, no export, no report
assembly. LC-P1-11 owns those, and its format scope is explicit: **DOCX and PDF
are not Phase 1**; Markdown and HTML preview land there, with basic editable
DOCX/PDF after.

What is here is the part that has to be right regardless of format: where the
bytes are, what they hashed to, which task they belong to, which stage or
operator produced them, and — through
:attr:`~labcairn.reports.receipt.ArtifactReceipt.derived_from` — the chain of
upstream ids and hashes that makes the output reproducible rather than merely
present.
"""

from __future__ import annotations

from labcairn.reports.receipt import (
    ARTIFACT_SCHEMA_VERSION,
    ArtifactKind,
    ArtifactProducerKind,
    ArtifactReceipt,
    ArtifactStaleness,
    DerivationRef,
    DerivationTargetKind,
)

__all__ = [
    "ARTIFACT_SCHEMA_VERSION",
    "ArtifactKind",
    "ArtifactProducerKind",
    "ArtifactReceipt",
    "ArtifactStaleness",
    "DerivationRef",
    "DerivationTargetKind",
]
