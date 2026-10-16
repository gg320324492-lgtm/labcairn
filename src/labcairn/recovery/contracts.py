"""The vocabulary of recovery: what an uncertain side effect is, and what a probe found.

ADR-0003 C2's crash table is the specification, and the most important line in it
is the one about ``ATTEMPTING``::

    ATTEMPTING  —  operation_attempted committed. The side effect may or may
                   not have landed. The DB cannot distinguish "died before the
                   syscall" from "died after it".

Everything in this package exists to resolve that sentence honestly. The rejected
alternative is recorded in ADR-0003 A2: OpenHands asserts "not done" after a
crash, because its provider APIs are compatible with the assumption. LabCairn
does not get that luxury and must not pretend to — so :class:`UNCERTAIN` is a
state a recovery pass **enters**, and a replay is refused until a read-only
probe has resolved it.

Two ideas carry the design:

* **Write-ahead intent.** ``operation_attempted`` commits in its own
  transaction, before the effect is attempted. Without it, a crash leaves no
  evidence anything was in flight and cases 1 and 2 are indistinguishable.
* **Confirmed behind.** ``operation_confirmed`` and the receipt commit in one
  transaction. The filesystem is never inside a SQLite transaction and cannot
  be; the intent goes ahead of the effect and the outcome is confirmed behind
  it.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final, Protocol

from labcairn.core.ids import OperationId
from labcairn.runtime.event import Event
from labcairn.runtime.operation import OperationState

#: SHA-256, lowercase hex. The one form ``depends_on`` and every probe speak.
type ContentHash = str


def hash_bytes(payload: bytes) -> ContentHash:
    """SHA256 of *payload*, the form :attr:`Operation.depends_on` holds.

    Not a reimplementation of :func:`labcairn.security.approval.content_hash` —
    that one reads a file from disk. This one hashes bytes a caller already has,
    which is the only thing available *before* the write it is predicting.
    """
    return hashlib.sha256(payload).hexdigest()


class CrashPoint(StrEnum):
    """Where in the execute path a fault may be injected.

    Named for the window each one opens, not for the line it sits on. The
    enumeration is the ADR's three cases plus the fourth window AT-5 needs: a
    crash *after* the intent commits but *before* the write lands is also
    ``UNCERTAIN``-shaped, and it is the only way to reach ``REPLAY_SAFE``
    honestly.
    """

    #: Before ``operation_attempted`` commits. Nothing was attempted, so there
    #: is nothing to reconcile. ADR-0003 C2 row 1 / AT-1.
    BEFORE_ATTEMPTED_COMMIT = "before_attempted_commit"

    #: After ``operation_attempted`` commits, before the effect runs. The intent
    #: is durable and the effect did not happen. AT-5.
    AFTER_ATTEMPTED_BEFORE_WRITE = "after_attempted_before_write"

    #: After the effect ran, before ``operation_confirmed`` commits. The intent
    #: is durable, the receipt is not, and the bytes are on disk. This is the
    #: case that becomes UNCERTAIN. AT-2 / AT-4.
    AFTER_WRITE_BEFORE_CONFIRM = "after_write_before_confirm"

    #: After ``operation_confirmed`` commits, before the client is told. Nothing
    #: is uncertain and nothing must be re-run. AT-3.
    AFTER_CONFIRM_BEFORE_NOTIFY = "after_confirm_before_notify"


class FaultInjector(Protocol):
    """Something that can be asked whether to fail at *point*.

    ``None`` is the default everywhere, and the check is ``if self._faults is
    not None`` rather than a truthiness test on a protocol value — a custom
    injector that happens to define ``__bool__`` returning ``False`` would
    otherwise silently disable injection.
    """

    def trip(self, point: CrashPoint) -> None:
        """Raise if a fault is armed at *point*, otherwise return quietly."""
        ...


class InjectedCrash(BaseException):
    """The fault an injector raises.

    :class:`BaseException` rather than :class:`Exception`, for one reason: the
    subprocess matrix test hard-kills the child, and this is the in-process
    equivalent used everywhere else, and both must defeat ``except Exception``
    handlers a caller might plausibly have wrapped around the execute call.
    A ``finally`` still runs — which is what makes it a faithful stand-in for a
    crash rather than for ``SystemExit``.
    """

    def __init__(self, point: CrashPoint) -> None:
        super().__init__(f"injected crash at {point.value}")
        self.point = point


@dataclass(frozen=True, slots=True)
class ArmedFaults:
    """A fault armed at exactly one :class:`CrashPoint`.

    Immutable and single-point on purpose. A mutable "set of armed points"
    invites a test arming three points, tripping the first, and never learning
    whether the other two work — which is a test that passes for the wrong
    reason, and the failure mode this package exists to prevent.
    """

    point: CrashPoint
    #: Trip on the *n*-th arrival, so a test can let an earlier pass through.
    occurrence: int = 1

    def trip(self, at: CrashPoint) -> None:
        if at != self.point:
            return
        if self.occurrence > 1:
            # Arming a later occurrence is done by constructing a new instance;
            # mutating this one would make a fault's behaviour depend on how
            # many times unrelated code happened to pass through.
            raise ValueError("construct ArmedFaults with a lower occurrence instead")
        raise InjectedCrash(at)


class ReconciliationResolution(StrEnum):
    """ADR-0003 C2's reconcile outcomes.

    ``CONFIRMED`` is reachable two ways — the executor committing the receipt,
    or a probe finding the bytes — and the difference matters for an audit, so
    :class:`ReconciliationOutcome` records *which* one happened in
    :attr:`ReconciliationOutcome.reached_by`. The four names here are C2's own.
    """

    #: The effect landed. Bytes on disk hash to what was predicted.
    CONFIRMED = "confirmed"
    #: The effect provably did not land. Replaying it is safe.
    REPLAY_SAFE = "replay_safe"
    #: The effect did not land and will not: something is wrong with the plan.
    FAILED = "failed"
    #: Bytes exist at the canonical path but are not what this operation
    #: predicted. Only a human may resolve this.
    CONFLICT = "conflict"


#: Where a resolved outcome came from. Not an operation state: this is about the
#: *history* of how the answer was reached, and it is the part an audit wants.
class ResolutionSource(StrEnum):
    #: Committed by the executor in the same transaction as the receipt.
    EXECUTOR_COMMIT = "executor_commit"
    #: Found by a read-only probe during recovery. This is what
    #: ``resolution='confirmed_by_probe'`` names.
    PROBE = "probe"


#: The operation state each resolution lands in.
#
#: ``CONFLICT`` deliberately maps to ``UNCERTAIN`` and not to ``FAILED``: a
#: conflict is bytes at the target path that this operation did not write and
#: may not overwrite. Calling that ``FAILED`` would report "the operation did
#: not work" when the truth is "a human has to decide", and would let a later
#: pass treat it as retryable.
RESOLUTION_TO_STATE: Final[dict[ReconciliationResolution, OperationState]] = {
    ReconciliationResolution.CONFIRMED: OperationState.CONFIRMED,
    ReconciliationResolution.REPLAY_SAFE: OperationState.AUTHORIZED,
    ReconciliationResolution.FAILED: OperationState.FAILED,
    ReconciliationResolution.CONFLICT: OperationState.UNCERTAIN,
}


@dataclass(frozen=True, slots=True)
class SideEffect:
    """One effect to attempt, together with what it is expected to produce.

    ``expected_sha256`` is the load-bearing field. A probe can only answer "did
    this land?" by comparing what is on disk against something, and the only
    trustworthy something is a hash computed **before** the write — derived from
    the bytes the caller intends to produce, not from a receipt written
    afterwards (which is exactly the receipt the crash destroyed).

    A caller whose effect is not byte-deterministic cannot supply this, and
    should not use :class:`SideEffect` at all rather than supply a hash it does
    not believe: a wrong ``expected_sha256`` turns the probe into a coin flip
    dressed as a check.
    """

    #: Canonical, workspace-relative, POSIX-separated. Matches the ADR-0003 C4
    #: rule and ``Operation.resource_key``, so probe and approval agree on
    #: which file they mean.
    resource_key: str
    expected_sha256: ContentHash
    #: Performs the effect and returns the SHA256 of what it actually wrote.
    #: Compared against ``expected_sha256`` before anything is confirmed: an
    #: effect that wrote something else is ``FAILED``, never ``CONFIRMED``.
    apply: Callable[[], ContentHash]

    def __post_init__(self) -> None:
        if not self.expected_sha256 or len(self.expected_sha256) != 64:
            raise ValueError(
                "expected_sha256 must be a 64-character hex digest. A probe that "
                "compares against a placeholder compares against nothing."
            )


@dataclass(frozen=True, slots=True)
class ProbeVerdict:
    """What a read-only probe found. No side effects, ever.

    ``observed_sha256`` is ``None`` when the file is absent. ``expected`` is
    carried alongside rather than closed over so that a caller can log the pair
    and a reader can tell "absent" from "different" without re-deriving.
    """

    resolution: ReconciliationResolution
    resource_key: str
    expected_sha256: ContentHash
    observed_sha256: ContentHash | None
    detail: str

    @property
    def landed(self) -> bool:
        """Whether the probe found exactly the bytes the operation predicted."""
        return self.resolution is ReconciliationResolution.CONFIRMED


@dataclass(frozen=True, slots=True)
class ReconciliationOutcome:
    """The result of resolving one uncertain operation.

    ``reached_by`` distinguishes the two ways an operation can be CONFIRMED.
    It is carried in the returned value rather than only in an event because the
    event envelope carries a state transition and no free-form payload — see
    the note in :mod:`labcairn.recovery.reconciliation` on what that costs.
    """

    operation_id: OperationId
    resolution: ReconciliationResolution
    reached_by: ResolutionSource
    verdict: ProbeVerdict
    resulting_state: OperationState
    replay_permitted: bool
    operation_uncertain: bool


class Probe(Protocol):
    """A read-only check of whether one effect landed.

    Read-only is the whole contract, and it is the reason the default
    implementation (:mod:`labcairn.recovery.probes`) is written with
    ``os.stat``/``open`` and no writes at all. A probe that could repair would
    be a second writer, and recovery is exactly where a second writer does the
    most damage.
    """

    def inspect(self, resource_key: str, expected_sha256: ContentHash) -> ProbeVerdict:
        """Report what is at *resource_key*, relative to some agreed root."""
        ...


class EventSink(Protocol):
    """Where a client would be told about committed events.

    Modelled as a protocol rather than a callable so the executor can be handed
    an object that *records* what it was told. Crash case 3 is defined by this
    call not happening, so a test needs to observe the difference between "not
    notified" and "notified and the notification lost" — which only a recording
    sink can distinguish.
    """

    def deliver(self, events: Sequence[Event]) -> None:
        """Hand *events* to the client. Raising means the client missed them;
        the events are committed either way and will be re-read by ``after_seq``.
        """
        ...


class RecoveryError(RuntimeError):
    """Base for every refusal this package raises."""


class ReconciliationRequired(RecoveryError):  # noqa: N818 — the ADR's own name
    """The operation is UNCERTAIN. It may not be replayed until a probe resolves it.

    The refusal carries the operation id so a caller can go and resolve it,
    rather than re-reading the log to find out what it was told.
    """

    def __init__(self, operation_id: OperationId, *, state: OperationState) -> None:
        super().__init__(
            f"operation {operation_id} is {state.value}; reconciliation must resolve "
            f"it before any replay. Assuming it did not run is the assumption "
            f"ADR-0003 C2 forbids."
        )
        self.operation_id = operation_id
        self.state = state


class ConflictDetected(RecoveryError):  # noqa: N818 — reads as a finding, not a fault
    """A probe found bytes at the canonical path that this operation did not write.

    Distinct from :class:`ReconciliationRequired` because the remedy differs:
    reconciliation is finished, and what remains is a human decision.
    """

    def __init__(self, verdict: ProbeVerdict) -> None:
        super().__init__(
            f"conflict at {verdict.resource_key}: expected "
            f"{verdict.expected_sha256[:12]}…, found "
            f"{(verdict.observed_sha256 or 'nothing')[:12]}… — {verdict.detail}"
        )
        self.verdict = verdict


class UnknownOperationError(RecoveryError):
    """An operation id with no row."""


class UnknownStageError(RecoveryError):
    """A stage id with no row, or one belonging to a different task."""


def resource_path(root: Path, resource_key: str) -> Path:
    """Resolve a canonical resource key against the workspace root.

    ``resource_key`` is workspace-relative and POSIX-separated by contract
    (ADR-0003 C4), so this is a join and not a resolution — no ``..``, no drive
    letter and no symlink chasing happens here, because the key is already the
    canonical form. Re-canonicalising would be the job of the workspace module,
    which owns that rule; duplicating it here would give two answers.
    """
    return root.joinpath(*resource_key.split("/"))
