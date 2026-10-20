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

from typing import TYPE_CHECKING

from labcairn.reports.receipt import (
    ARTIFACT_SCHEMA_VERSION,
    ArtifactKind,
    ArtifactProducerKind,
    ArtifactReceipt,
    ArtifactStaleness,
    DerivationRef,
    DerivationTargetKind,
)

if TYPE_CHECKING:
    from labcairn.reports.model import ReportDocument

__all__ = [
    "ARTIFACT_SCHEMA_VERSION",
    "ArtifactKind",
    "ArtifactProducerKind",
    "ArtifactReceipt",
    "ArtifactStaleness",
    "DerivationRef",
    "DerivationTargetKind",
    "ReportDocument",
]


def __getattr__(name: str) -> object:
    """The report document model, imported on first use.

    The model imports :mod:`labcairn.analysis.manifest`, and that module
    imports this package. Importing the model here would make the
    package import a module that is, in one order, already half-loaded --
    so the import is deferred to the moment a caller asks for the symbol.
    """
    if name == "ReportDocument":
        from labcairn.reports.model import ReportDocument

        return ReportDocument
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """The deferred symbol in the listing, so ``dir()`` is not a lie."""
    return sorted([*globals(), "ReportDocument"])
