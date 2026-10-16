"""Crash recovery, reconciliation and resume.

LC-P1-06. What this package is:

* :mod:`~labcairn.recovery.executor` — one side effect, driven as
  write-ahead intent, attempt, confirm-behind;
* :mod:`~labcairn.recovery.reconciliation` — the pass that turns "the database
  cannot vouch for this" into one of ADR-0003 C2's four named outcomes;
* :mod:`~labcairn.recovery.probes` — the read-only filesystem check those
  outcomes come from;
* :mod:`~labcairn.recovery.approvals` — single-use approval, enforced by a
  conditional UPDATE rather than by an in-memory flag;
* :mod:`~labcairn.recovery.resume` — checkpoints, resume from the last verified
  stage, scoped pause/stop, and what a changed source invalidates.

The organising idea is in ADR-0003 C2 and nowhere else: ``UNCERTAIN`` is a
state recovery **enters**, never one it assumes away. A crash does not write
``UNCERTAIN`` — nothing is running to write it — so the only evidence a write
was in flight is an ``operation_attempted`` row committed before it. Recovery
reads that evidence and enters the state; only then may a probe run, and no
replay is permitted until the probe has resolved it. The rejected alternative,
asserting "not done" because a provider API tolerates it, is ADR-0003 A2 and is
what this package exists to not be.

Consequence worth stating: the three crash cases do not cost the same.
Crashing *before* the write-ahead intent commits costs nothing to recover from,
and crashing *after* the confirmation commits costs nothing either — a client
that reconnects re-reads the log by ``after_seq``. Only the window between the
two is expensive, and one transaction boundary is what makes the second case as
cheap as the first.
"""

from __future__ import annotations

from labcairn.recovery.approvals import (
    ApprovalAlreadySpentError,
    ApprovalStore,
)
from labcairn.recovery.contracts import (
    ArmedFaults,
    ConflictDetected,
    ContentHash,
    CrashPoint,
    EventSink,
    FaultInjector,
    InjectedCrash,
    Probe,
    ProbeVerdict,
    ReconciliationOutcome,
    ReconciliationRequired,
    ReconciliationResolution,
    RecoveryError,
    ResolutionSource,
    SideEffect,
    UnknownOperationError,
    UnknownStageError,
    hash_bytes,
)
from labcairn.recovery.executor import (
    AlreadyConfirmedError,
    SideEffectExecutor,
)
from labcairn.recovery.persistence import load_operation
from labcairn.recovery.probes import FileSystemProbe
from labcairn.recovery.reconciliation import (
    CONFLICT_BLOCK_REASON,
    UNCERTAIN_BLOCK_REASON,
    RecoveryCoordinator,
)
from labcairn.recovery.resume import (
    STALE_REASON,
    InvalidationReport,
    MaterialResolver,
    MaterialSnapshot,
    ResumeCoordinator,
    ResumePlan,
)

__all__ = [
    "CONFLICT_BLOCK_REASON",
    "STALE_REASON",
    "UNCERTAIN_BLOCK_REASON",
    "AlreadyConfirmedError",
    "ApprovalAlreadySpentError",
    "ApprovalStore",
    "ArmedFaults",
    "ConflictDetected",
    "ContentHash",
    "CrashPoint",
    "EventSink",
    "FaultInjector",
    "FileSystemProbe",
    "InjectedCrash",
    "InvalidationReport",
    "MaterialResolver",
    "MaterialSnapshot",
    "Probe",
    "ProbeVerdict",
    "ReconciliationOutcome",
    "ReconciliationRequired",
    "ReconciliationResolution",
    "RecoveryCoordinator",
    "RecoveryError",
    "ResolutionSource",
    "ResumeCoordinator",
    "ResumePlan",
    "SideEffect",
    "SideEffectExecutor",
    "UnknownOperationError",
    "UnknownStageError",
    "hash_bytes",
    "load_operation",
]
