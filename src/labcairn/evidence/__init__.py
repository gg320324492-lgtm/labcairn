"""``labcairn.evidence`` — what was claimed, where it came from, and how far it was checked.

* :class:`~labcairn.evidence.record.EvidenceRecord` — a claim, a number or a
  result, bound to anchors and one of exactly six verification states.
* :class:`~labcairn.evidence.record.VerificationRecord` — one immutable entry in
  the append-only audit log that says **what was actually checked**.
* :mod:`~labcairn.evidence.states` — the closed vocabularies, and the six states
  as data so nothing downstream re-spells them.
* :mod:`~labcairn.evidence.cite_support` — the four validators C1-C4. Only **C4**
  can answer in Phase 1, and its answer is permanently ``not_checked``.

The one idea this package is built around
-----------------------------------------
**Verification is not a label.** ``docs/ARCHITECTURE.md``: *"Verification records
include what was actually checked. `verified_by_rule` can mean numeric/structural
verification; it must not imply a scientific hypothesis is established."* So the
status alone never carries the claim: a record past ``planned`` is rejected
unless it also carries the log entries that earned the status, and
:attr:`~labcairn.evidence.states.CheckOutcome` keeps ``indeterminate`` and
``not_checked`` as members that are simply not ``pass``.

Nothing here implements retrieval, extraction or analysis. A record describes a
piece of evidence and what has been checked about it; deciding whether the
checks pass is LC-P1-09.
"""

from __future__ import annotations

from labcairn.evidence.cite_support import (
    C4_CHECKER_ID,
    C4_DETAIL,
    CITE_SUPPORT_SCHEMA_VERSION,
    CiteSupportNotImplementedError,
    LocatedContent,
    LocationResolution,
    NotCheckedVerdict,
    SourceIndex,
    Verdict,
    check_numeric_consistency,
    check_quotation_support,
    check_scientific_interpretation,
    check_source_exists,
)
from labcairn.evidence.record import (
    EVIDENCE_SCHEMA_VERSION,
    UPGRADING_CHECKS,
    EvidenceRecord,
    VerificationRecord,
)
from labcairn.evidence.states import (
    CHECK_KINDS,
    CHECK_OUTCOMES,
    IMPLEMENTED_CHECKS,
    VERIFICATION_STATES,
    CheckKind,
    CheckOutcome,
    EvidenceCreator,
    EvidenceKind,
    NormalizationProfile,
    VerificationStatus,
)

__all__ = [
    "C4_CHECKER_ID",
    "C4_DETAIL",
    "CHECK_KINDS",
    "CHECK_OUTCOMES",
    "CITE_SUPPORT_SCHEMA_VERSION",
    "EVIDENCE_SCHEMA_VERSION",
    "IMPLEMENTED_CHECKS",
    "UPGRADING_CHECKS",
    "VERIFICATION_STATES",
    "CheckKind",
    "CheckOutcome",
    "CiteSupportNotImplementedError",
    "EvidenceCreator",
    "EvidenceKind",
    "EvidenceRecord",
    "LocatedContent",
    "LocationResolution",
    "NormalizationProfile",
    "NotCheckedVerdict",
    "SourceIndex",
    "Verdict",
    "VerificationRecord",
    "VerificationStatus",
    "check_numeric_consistency",
    "check_quotation_support",
    "check_scientific_interpretation",
    "check_source_exists",
]
