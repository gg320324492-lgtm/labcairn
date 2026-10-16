"""Executing one side effect so that a crash at any point is answerable.

The whole module is one shape: **intent ahead, outcome behind**. Three
transactions and one filesystem write, in this order:

1. ``operation_intent`` — the operation is authorised and recorded. Crash here
   and nothing was attempted (ADR-0003 C2 row 1/2: nothing to reconcile).
2. ``operation_attempted`` — committed **on its own, before** the effect runs.
   This is what makes an in-flight attempt visible to a process that did not
   survive it. Without it, a crash during the write leaves no evidence anything
   was happening and cases 1 and 2 are indistinguishable.
3. — the filesystem write. Never inside a transaction; it cannot be.
4. ``operation_confirmed`` + the artifact receipt — one transaction. Crash
   after it and the only thing lost is the *notification*, which a reconnecting
   client recovers with ``after_seq`` and no reconciliation at all.

The gap between 2 and 4 is the only dangerous window, and it is narrow on
purpose: one write. Everything this module knows how to do is defined by what it
can say about that window, and it says "UNCERTAIN" rather than guessing.

Why the receipt is in the same transaction as the confirmation
-------------------------------------------------------------
It is the reason crash case 3 needs no reconciliation. If the confirmation and
the receipt were separate writes, a crash between them would leave an operation
that claims to have landed with no artefact describing what it produced — and
recovering that would require exactly the reconciliation the ADR wants absent.
Together, they are one atomic fact: "this happened, and here is what it is".

Single-use of the approval
--------------------------
An approval, when one is required, is consumed **before** step 2 and is never
re-issued. A replay after a crash re-authorises from scratch: it may reuse an
approval only if a fresh, unconsumed one exists, because the approval that
authorised the crashed attempt was already spent and its digest no longer
describes what is about to happen.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from sqlalchemy.orm import Session

from labcairn.core.ids import OperationId, RunId, StageId, TaskId, new_id
from labcairn.db.repository import Clock, TaskStore, utc_now
from labcairn.recovery.contracts import (
    CrashPoint,
    EventSink,
    FaultInjector,
    ReconciliationRequired,
    RecoveryError,
    SideEffect,
    resource_path,
)
from labcairn.recovery.persistence import load_operation
from labcairn.reports.receipt import (
    ArtifactKind,
    ArtifactProducerKind,
    ArtifactReceipt,
    ArtifactStaleness,
    DerivationRef,
)
from labcairn.runtime.event import Event, EventTransition, EventType
from labcairn.runtime.operation import (
    Approval,
    ApprovalState,
    Operation,
    OperationState,
    compute_args_digest,
)

#: The key every ``execute``/``replay`` call must carry in ``args``.
#:
#: There is no column for the hash an operation is expected to produce, and
#: inventing one would mean touching the frozen schema. Binding it through
#: ``args`` puts it inside ``args_digest`` instead, where it is durable, and
#: where an approval granted for the operation covers it too — a replay cannot
#: supply a different expected hash without producing a different digest.
EXPECTED_HASH_ARG: Final = "expected_sha256"


class AlreadyConfirmedError(RuntimeError):
    """Refusing to re-run an operation whose effect is confirmed.

    Not an error the caller can work around and not a bug report: re-running a
    confirmed effect is the one thing crash case 3 exists to make impossible, so
    the refusal is the deliverable. The same refusal is what makes AT-3's
    "write counter still 1" true after a client reconnects.
    """


@dataclass(frozen=True, slots=True)
class NullEventSink:
    """A sink that discards. Used when nobody is listening.

    The default matters: it means "no client attached" is an ordinary
    configuration rather than a branch every call site has to take. Events are
    committed either way, so a client that attaches later still gets them from
    ``after_seq`` — the log, not the notification, is the record.
    """

    def deliver(self, events: Sequence[Event]) -> None:
        return None


#: The singleton, so the common case allocates nothing.
NULL_SINK: Final[EventSink] = NullEventSink()


class SideEffectExecutor:
    """Drives one side effect through the three transactions and the write."""

    __slots__ = ("_clock", "_faults", "_session", "_sink", "_store", "_workspace")

    def __init__(
        self,
        store: TaskStore,
        session: Session,
        *,
        workspace_root: Path,
        clock: Clock | None = None,
        faults: FaultInjector | None = None,
        sink: EventSink = NULL_SINK,
    ) -> None:
        # The session is passed in rather than read off the store: `TaskStore`
        # owns it privately, and reaching in would make a refactor of LC-P1-05's
        # constructor a silent break here. The caller already has it — it built
        # the store with it.
        self._store = store
        self._session = session
        self._workspace = workspace_root
        self._clock: Clock = clock or utc_now
        self._faults: FaultInjector | None = faults
        self._sink: EventSink = sink

    # -- public API ---------------------------------------------------------- #

    def execute(
        self,
        task_id: TaskId,
        run_id: RunId,
        stage_id: StageId,
        *,
        capability: str,
        effect: SideEffect,
        args: Mapping[str, object],
        depends_on: Sequence[str] = (),
        kind: ArtifactKind = ArtifactKind.OTHER,
        derived_from: Sequence[DerivationRef] = (),
        approval: Approval | None = None,
    ) -> Operation:
        """Plan, authorise and attempt *effect*. See :meth:`_attempt` for the shape."""
        digest_args = self._bind_expected_hash(args, effect)
        hashes = tuple(depends_on)
        operation = Operation(
            operation_id=OperationId(new_id()),
            task_id=task_id,
            run_id=run_id,
            stage_id=stage_id,
            state=OperationState.PLANNED,
            capability=capability,
            resource_key=effect.resource_key,
            depends_on=hashes,
            args_digest=compute_args_digest(
                task_id=task_id,
                capability=capability,
                resource_key=effect.resource_key,
                args=digest_args,
                depends_on=hashes,
            ),
        )

        authorised = operation.model_copy(update={"state": OperationState.AUTHORIZED})
        with self._store.unit(task_id) as work:
            work.emit(
                EventType.OPERATION_INTENT,
                run_id=run_id,
                stage_id=stage_id,
                operation_id=operation.operation_id,
                transition=_transition(OperationState.PLANNED, OperationState.AUTHORIZED),
            )
            work.put_operation(authorised)

        return self._attempt(
            authorised,
            effect=effect,
            kind=kind,
            derived_from=derived_from,
            approval=approval,
        )

    def replay(
        self,
        operation_id: OperationId,
        *,
        effect: SideEffect,
        args: Mapping[str, object],
        kind: ArtifactKind = ArtifactKind.OTHER,
        derived_from: Sequence[DerivationRef] = (),
        approval: Approval | None = None,
    ) -> Operation:
        """Re-attempt an operation whose previous attempt is not in doubt.

        Two refusals, and they are the point of the whole ticket:

        * ``UNCERTAIN`` (or still ``ATTEMPTING``) raises
          :class:`ReconciliationRequired`. The effect may have landed; only a
          probe can say. Assuming "it did not run" is the assumption ADR-0003
          A2 rejected in OpenHands.
        * ``CONFIRMED`` raises :class:`AlreadyConfirmedError`. There is nothing
          to fix and re-running would duplicate the effect.
        """
        operation = load_operation(self._session, operation_id)

        if operation.state is OperationState.UNCERTAIN:
            raise ReconciliationRequired(operation_id, state=operation.state)
        if operation.state is OperationState.ATTEMPTING:
            # Still ATTEMPTING means recovery has not run yet. It is the same
            # fact as UNCERTAIN with a step to go, so it gets the same refusal
            # rather than a special case that might later drift.
            raise ReconciliationRequired(operation_id, state=operation.state)
        if operation.state is OperationState.CONFIRMED:
            raise AlreadyConfirmedError(
                f"operation {operation_id} is confirmed; its effect is already on "
                f"disk and re-running it would duplicate the side effect"
            )
        if operation.state in (OperationState.DENIED, OperationState.FAILED):
            raise AlreadyConfirmedError(
                f"operation {operation_id} is terminal ({operation.state.value})"
            )

        if effect.resource_key != operation.resource_key:
            raise ValueError(
                f"replay targets {effect.resource_key} but operation {operation_id} "
                f"was planned against {operation.resource_key}. A replay must perform "
                f"the same operation, not a different one."
            )

        recomputed = compute_args_digest(
            task_id=operation.task_id,
            capability=operation.capability,
            resource_key=operation.resource_key,
            args=dict(self._bind_expected_hash(args, effect)),
            depends_on=operation.depends_on,
        )
        if recomputed != operation.args_digest:
            raise ValueError(
                f"replay arguments digest to {recomputed[:12]}… but operation "
                f"{operation_id} was planned for {operation.args_digest[:12]}…"
            )

        return self._attempt(
            operation,
            effect=effect,
            kind=kind,
            derived_from=derived_from,
            approval=approval,
        )

    # -- the shape ----------------------------------------------------------- #

    def _attempt(
        self,
        operation: Operation,
        *,
        effect: SideEffect,
        kind: ArtifactKind,
        derived_from: Sequence[DerivationRef],
        approval: Approval | None,
    ) -> Operation:
        """Write ahead, write, confirm behind. Three transactions, one write."""
        if approval is not None:
            self._require_unconsumed(approval, operation)

        task_id = operation.task_id
        run_id = operation.run_id
        stage_id = operation.stage_id

        # --- 2. write-ahead intent, its own transaction ---------------------- #
        attempting = operation.model_copy(update={"state": OperationState.ATTEMPTING})
        with self._store.unit(task_id) as work:
            work.emit(
                EventType.OPERATION_ATTEMPTED,
                run_id=run_id,
                stage_id=stage_id,
                operation_id=operation.operation_id,
                transition=_transition(OperationState.AUTHORIZED, OperationState.ATTEMPTING),
            )
            work.put_operation(attempting)
            # Inside the unit on purpose: this must abort the transaction, not
            # merely interrupt the Python call. Placed after the emit so the
            # staged events are rolled back with the state row rather than
            # never having been staged — the stronger of the two claims.
            self._trip(CrashPoint.BEFORE_ATTEMPTED_COMMIT)

        # --- 3. the effect, outside every transaction ----------------------- #
        self._trip(CrashPoint.AFTER_ATTEMPTED_BEFORE_WRITE)
        produced = effect.apply()
        self._trip(CrashPoint.AFTER_WRITE_BEFORE_CONFIRM)

        if produced != effect.expected_sha256:
            # The write happened but not the write we intended. FAILED is
            # honest — not UNCERTAIN, because we know exactly what landed.
            failed = attempting.model_copy(update={"state": OperationState.FAILED})
            with self._store.unit(task_id) as work:
                work.emit(
                    EventType.OPERATION_FAILED,
                    run_id=run_id,
                    stage_id=stage_id,
                    operation_id=operation.operation_id,
                    transition=_transition(OperationState.ATTEMPTING, OperationState.FAILED),
                )
                work.put_operation(failed)
            return failed

        # --- 4. confirmation and receipt, one transaction ------------------- #
        target = resource_path(self._workspace, effect.resource_key)
        receipt = ArtifactReceipt(
            receipt_id=f"artifact-{new_id()}",
            task_id=str(task_id),
            kind=kind,
            relative_path=effect.resource_key,
            content_sha256=produced,
            size_bytes=target.stat().st_size,
            produced_by=ArtifactProducerKind.STAGE,
            producer_id=f"stage:{stage_id}",
            derived_from=tuple(derived_from),
            staleness=ArtifactStaleness.CURRENT,
            created_at=self._clock(),
        )
        confirmed = attempting.model_copy(update={"state": OperationState.CONFIRMED})
        with self._store.unit(task_id) as work:
            work.emit(
                EventType.OPERATION_CONFIRMED,
                run_id=run_id,
                stage_id=stage_id,
                operation_id=operation.operation_id,
                transition=_transition(OperationState.ATTEMPTING, OperationState.CONFIRMED),
            )
            work.emit(EventType.ARTIFACT_RECORDED)
            work.put_operation(confirmed)
            work.put_artifact(receipt, run_id=run_id)
            committed = work.events

        # --- 5. tell the client, knowing it may not be listening ------------- #
        self._trip(CrashPoint.AFTER_CONFIRM_BEFORE_NOTIFY)
        self._deliver(committed)

        return confirmed

    # -- helpers ------------------------------------------------------------- #

    def _trip(self, point: CrashPoint) -> None:
        if self._faults is not None:
            self._faults.trip(point)

    def _deliver(self, events: Sequence[Event]) -> None:
        self._sink.deliver(events)

    @staticmethod
    def _bind_expected_hash(args: Mapping[str, object], effect: SideEffect) -> dict[str, object]:
        """Force the expected hash into the arguments, so it lands in the digest.

        Without this the expected hash would exist only in the caller's stack:
        after a crash there would be nothing on disk or in the store to compare
        a probe's findings against, and the probe would be guessing.
        """
        bound = dict(args)
        bound[EXPECTED_HASH_ARG] = effect.expected_sha256
        return bound

    @staticmethod
    def _require_unconsumed(approval: Approval, operation: Operation) -> None:
        """Refuse a spent or ungranted approval before any write-ahead intent.

        The full ADR-0003 C4 check — expiry, digest, sources, policy — happens in
        :mod:`labcairn.recovery.approvals`, which owns the DB-backed row. What
        remains here is the narrow case where a caller hands a contract straight
        to the executor: it must at least not be one already spent.
        """
        if approval.state is ApprovalState.CONSUMED:
            raise RecoveryError(
                f"approval {approval.approval_id} is already consumed; a spent "
                f"approval never authorises a second effect (ADR-0003 C4)"
            )
        if approval.operation_id != operation.operation_id:
            raise ValueError(
                f"approval {approval.approval_id} was issued for operation "
                f"{approval.operation_id}, not {operation.operation_id}"
            )


def _transition(from_state: OperationState, to_state: OperationState) -> EventTransition:
    return EventTransition(from_state=from_state.value, to_state=to_state.value)


__all__ = [
    "EXPECTED_HASH_ARG",
    "NULL_SINK",
    "AlreadyConfirmedError",
    "NullEventSink",
    "SideEffectExecutor",
]
