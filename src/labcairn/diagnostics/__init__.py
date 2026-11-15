"""Local, de-identified diagnostics: what is collected, what is proven absent.

LC-P3-07 deliverable 2 (work orders §12 §5.4, §5.6 deliverable 2). The package
carries digests and counts, and the shapes of what may be absent are decided
before anything is collected — the same design :mod:`labcairn.providers.errors`
applied to the whole product surface.
"""

from labcairn.diagnostics.package import (
    DiagnosticsPackage,
    DiagnosticsRefusedError,
    EventFact,
    FileFact,
    OperationFact,
    RefusalFact,
    collect_diagnostics,
    to_json_dict,
)

__all__ = [
    "DiagnosticsPackage",
    "DiagnosticsRefusedError",
    "EventFact",
    "FileFact",
    "OperationFact",
    "RefusalFact",
    "collect_diagnostics",
    "to_json_dict",
]
