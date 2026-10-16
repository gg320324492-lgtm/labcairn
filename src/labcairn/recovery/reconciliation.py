"""Resolving an operation the database cannot vouch for.

ADR-0003 C2's reconcile branch is four lines long::

    reconcile (read-only probe)
        |
        v
    CONFIRMED | REPLAY_SAFE | FAILED | CONFLICT

and almost all of the work is in deciding that you are allowed to reach that
line at all. This module refuses to touch anything in ``ATTEMPTING`` or
``UNCERTAIN`` until a probe has run, and records the probe's answer with the
same transaction discipline as everything else.

Why there is a separate "enter UNCERTAIN" step
----------------------------------------------
A crash does not write ``UNCERTAIN``. Nothing is executing when the process is
gone, so nothing can record that fact; the only evidence is an ``ATTEMPTING``
row that was committed before the write. :meth:`RecoveryCoordinator.mark_uncertain`
is the pass that reads that evidence and *enters* the state, and it runs on
startup, before anything is retried. Folding it into the probe would mean a
process could be "unsure" and "resolved" in the same breath, and an audit of
the event log would show no record that the uncertainty ever existed.

What the probe cannot tell you
------------------------------
It compares bytes. It does not know whether those bytes came from *this* attempt
or from an earlier one that wrote the same content — and it does not need to,
because the question is not "did this operation write the file" but "is the file
in the state this operation was about to leave behind". A pre-existing identical
file resolves the same way: replaying would be harmless, and confirming is
correct. The genuinely unresolvable case is a *differing* file, which is
``CONFLICT`` and is left for a human.

Storage note, and what it costs
-------------------------------
AT-4 wants the resolution recorded as ``confirmed_by_probe``. The frozen
:class:`~labcairn.runtime.event.Event` has ``extra="forbid"`` and no payload
field, and :mod:`labcairn.db` has no table for reconciliation results, so the
string ``confirmed_by_probe`` cannot be stored as a column or as an event
attribute without changing a module this ticket does not own.

What *is* stored is the resolution itself, as the ``operation_reconciled``
event's ``to_state``, using C2's own vocabulary. That is enough to re-derive
the fact, because ``CONFIRMED`` is reachable two ways and the event log tells
them apart: an operation reaches ``CONFIRMED`` through
:class:`~labcairn.recovery.executor.SideEffectExecutor` (which always emits
``operation_confirmed`` *and* an ``artifact_recorded`` in one transaction) or
through here (which emits ``operation_reconciled`` and no receipt). A confirmed
operation carrying ``operation_reconciled`` was confirmed by probe.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from sqlalchemy.orm import Session

from labcairn.core.ids import OperationId, TaskId
from labcairn.db.repository import Clock, TaskStore, utc_now
from labcairn.recovery.contracts import (
    RESOLUTION_TO_STATE,
    ConflictDetected,
    ContentHash,
    Probe,
    ProbeVerdict,
    ReconciliationOutcome,
    ReconciliationRequired,
    ReconciliationResolution,
    ResolutionSource,
)
from labcairn.recovery.persistence import (
    find_operations_in_state,
    find_stage,
    load_operation,
)
from labcairn.runtime.event import EventTransition, EventType
from labcairn.runtime.lifecycle import Stage, StageStatus
from labcairn.runtime.operation import Operation, OperationState

#: Why a stage is blocked, recorded verbatim on the stage row. A reader seeing
#: ``BLOCKED`` must be able to tell "a human is being asked" from "the system
#: does not know whether the last write landed", and a bare status cannot.
UNCERTAIN_BLOCK_REASON: Final = (
    "blocked: an operation is UNCERTAIN. A crash left a side effect whose outcome "
    "the database cannot vouch for; reconciliation must resolve it before the "
    "stage continues. Replay is refused."
)

#: The one resolution that leaves a stage blocked.
CONFLICT_BLOCK_REASON: Final = (
    "blocked: reconciliation found a CONFLICT. Bytes exist at the canonical path "
    "that this operation did not predict, so no automatic action was taken. A "
    "human must decide whether to overwrite them."
)


class RecoveryCoordinator:
    """Owns the uncertain/resolved boundary."""

    __slots__ = ("_clock", "_probe", "_session", "_store", "_workspace")

    def __init__(
        self,
        store: TaskStore,
        session: Session,
        *,
        workspace_root: Path,
        probe: Probe,
        clock: Clock | None = None,
    ) -> None:
        self._store = store
        self._session = session
        self._workspace = workspace_root
        self._probe = probe
        self._clock: Clock = clock or utc_now

    # -- entering UNCERTAIN -------------------------------------------------- #

    def mark_uncertain(self, task_id: TaskId) -> tuple[Operation, ...]:
        """Move every in-flight operation of *task_id* into UNCERTAIN and block its stage.

        Idempotent, and safe to call on every startup: an operation already in
        ``UNCERTAIN`` is left exactly as it is, and no second
        ``operation_uncertain`` event is emitted. Re-emitting would be harmless
        for the log (it is append-only) but it would make "how many times was
        this operation found in doubt" a question the log answers wrongly.
        """
        in_flight = find_operations_in_state(self._session, task_id, OperationState.ATTEMPTING)
        entered: list[Operation] = []
        for operation in in_flight:
            uncertain = operation.model_copy(update={"state": OperationState.UNCERTAIN})
            with self._store.unit(task_id) as work:
                work.emit(
                    EventType.OPERATION_UNCERTAIN,
                    run_id=operation.run_id,
                    stage_id=operation.stage_id,
                    operation_id=operation.operation_id,
                    transition=_transition(OperationState.ATTEMPTING, OperationState.UNCERTAIN),
                )
                work.put_operation(uncertain)
                stage = find_stage(self._session, operation.stage_id)
                if stage is not None:
                    work.put_stage(_blocked(stage, UNCERTAIN_BLOCK_REASON))
            entered.append(uncertain)
        return tuple(entered)

    # -- resolving ------------------------------------------------------------ #

    def reconcile(
        self,
        operation_id: OperationId,
        *,
        expected_sha256: ContentHash,
    ) -> ReconciliationOutcome:
        """Probe, then commit the answer.

        The probe runs **before** the transaction opens. It is read-only, so it
        cannot roll anything back, and keeping it outside means the write lock
        is not held while a possibly-slow hash of a large file is computed.

        *expected_sha256* is required rather than looked up. There is no column
        for it (see the module docstring) — it is inside ``args`` and therefore
        inside ``args_digest``, which is a hash of a hash: the value itself is
        not recoverable from the store. The caller that planned the operation
        is the one that can state it, and a caller that cannot is a caller that
        should not be reconciling.
        """
        operation = load_operation(self._session, operation_id)
        if operation.state is not OperationState.UNCERTAIN:
            raise ReconciliationRequired(operation_id, state=operation.state)

        verdict = self._probe.inspect(operation.resource_key, expected_sha256)
        resulting = RESOLUTION_TO_STATE[verdict.resolution]
        return self._commit_resolution(operation, verdict, resulting)

    def probe(
        self,
        operation_id: OperationId,
        *,
        expected_sha256: ContentHash,
    ) -> ProbeVerdict:
        """Ask the probe a question **without** recording an answer.

        For the caller that wants to know whether a repair would clobber
        something before it decides to offer one — a UI offering "overwrite the
        file?" should have the verdict in hand, and should not get it by
        committing an ``operation_reconciled`` event it never meant to commit.

        Read-only in the strict sense: no transaction opens, no event is
        emitted, no row is written. It is exactly what :meth:`reconcile` runs
        before it opens one.
        """
        operation = load_operation(self._session, operation_id)
        return self._probe.inspect(operation.resource_key, expected_sha256)

    def assert_no_conflict(
        self,
        operation_id: OperationId,
        *,
        expected_sha256: ContentHash,
    ) -> ProbeVerdict:
        """:meth:`probe`, refusing the answer that needs a human.

        The single place ``ConflictDetected`` is raised, so that "may I touch
        this path?" has one answer rather than one per call site. Returning the
        verdict rather than ``None`` means the caller who passed still has the
        observed hash to show the user.
        """
        verdict = self.probe(operation_id, expected_sha256=expected_sha256)
        if verdict.resolution is ReconciliationResolution.CONFLICT:
            raise ConflictDetected(verdict)
        return verdict

    def _commit_resolution(
        self,
        operation: Operation,
        verdict: ProbeVerdict,
        resulting: OperationState,
    ) -> ReconciliationOutcome:
        resolution = verdict.resolution
        updated = operation.model_copy(update={"state": resulting})
        with self._store.unit(operation.task_id) as work:
            work.emit(
                EventType.OPERATION_RECONCILED,
                run_id=operation.run_id,
                stage_id=operation.stage_id,
                operation_id=operation.operation_id,
                transition=EventTransition(
                    from_state=OperationState.UNCERTAIN.value, to_state=resolution.value
                ),
            )
            work.put_operation(updated)
            stage = find_stage(self._session, operation.stage_id)
            if stage is not None and stage.status is StageStatus.BLOCKED:
                work.put_stage(_unblocked_or_reblocked(stage, verdict))
        return ReconciliationOutcome(
            operation_id=operation.operation_id,
            resolution=resolution,
            reached_by=ResolutionSource.PROBE,
            verdict=verdict,
            resulting_state=resulting,
            replay_permitted=resolution is ReconciliationResolution.REPLAY_SAFE,
            operation_uncertain=updated.state is OperationState.UNCERTAIN,
        )

    # -- the guard ------------------------------------------------------------ #

    def assert_replayable(self, operation_id: OperationId) -> None:
        """Raise unless this operation may be replayed.

        The single choke point for "no blind replay". Everything that could
        otherwise re-attempt a side effect calls this first, so the rule lives
        in one place and a caller cannot enforce a subset of it.
        """
        operation = load_operation(self._session, operation_id)
        if operation.state in (OperationState.UNCERTAIN, OperationState.ATTEMPTING):
            raise ReconciliationRequired(operation_id, state=operation.state)


def _transition(from_state: OperationState, to_state: OperationState) -> EventTransition:
    return EventTransition(from_state=from_state.value, to_state=to_state.value)


def _blocked(stage: Stage, reason: str) -> Stage:
    """Re-validate rather than ``model_copy``.

    ``model_copy`` does not run validators, and the frozen ``Stage`` model's
    ``blocked_reason`` validator is the thing that keeps a reason attached only
    to a blocked stage. Going through :meth:`Stage.model_validate` means a
    mistake here fails here instead of producing a row that cannot be loaded
    back.
    """
    return Stage.model_validate(
        {**stage.model_dump(), "status": StageStatus.BLOCKED, "blocked_reason": reason}
    )


def _unblocked_or_reblocked(stage: Stage, verdict: ProbeVerdict) -> Stage:
    resolution = verdict.resolution
    if resolution is ReconciliationResolution.CONFLICT:
        return Stage.model_validate(
            {
                **stage.model_dump(),
                "status": StageStatus.BLOCKED,
                "blocked_reason": CONFLICT_BLOCK_REASON,
            }
        )
    return Stage.model_validate(
        {**stage.model_dump(), "status": StageStatus.ENTERED, "blocked_reason": None}
    )


__all__ = [
    "CONFLICT_BLOCK_REASON",
    "UNCERTAIN_BLOCK_REASON",
    "RecoveryCoordinator",
]
