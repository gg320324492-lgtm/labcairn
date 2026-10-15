"""LabCairn research core.

Phase 1 scope. This package is intentionally empty of domain models in LC-P1-01:
`Task`, `Run`, `Stage`, `EvidenceRecord`, `ArtifactReceipt` and `Checkpoint` belong
to LC-P1-02 and later, and the module boundaries that own them are not settled yet
(see ``docs/adr/ADR-0003-event-and-permission-model.md``).

What exists here today is packaging and toolchain only. Anything that looks like
product behaviour should be traceable to a work order.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
