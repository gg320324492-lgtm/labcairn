"""Single-use approval, backed by the row rather than by a flag in memory.

:class:`labcairn.security.approval.ApprovalLedger` is LC-P1-04's in-memory
ledger, and its own docstring says where it goes next: "LC-P1-05 moves it into
SQLite next to the ``Approval`` row, at which point ``consume`` becomes a
conditional ``UPDATE ... WHERE state = 'granted'`` whose affected-row count is
the single-use guarantee."

LC-P1-05 stored the row. This module is the half that was left: the conditional
update, and the decision logic that runs before it.

The single-use guarantee
------------------------
:meth:`ApprovalStore.consume` ends with one statement::

    UPDATE approvals SET state='consumed', consumed_at=:now
     WHERE approval_id=:id AND state='granted'

and refuses unless exactly one row changed. That is the whole enforcement. An
``if row.state == GRANTED: row.state = CONSUMED`` written in Python reads the
same and proves nothing: two processes can both read ``granted`` and both write
``consumed``, and the second write is a silent double-spend. SQLite serialises
the statements, and the ``state='granted'`` predicate is what makes the second
one match zero rows. The check that follows is not politeness — it is the
detector for the bug where someone replaces the conditional update with an
unconditional one.

Consumption happens before the effect, not after
------------------------------------------------
:mod:`labcairn.security.approval` argues this at length and the argument holds
here too: a retry loop, a second stage or a crash-and-resume can all reach the
same approval, and the only place to stop them is before the irreversible step.
The cost is that a failed write burns its approval. That is the right trade —
asking a human again is cheap, silently repeating a side effect is not.

Every other refusal is the ADR's, not this module's
---------------------------------------------------
Expiry, task scope, changed arguments, changed sources and changed policy are
all decided by
:meth:`labcairn.runtime.operation.Approval.refusal_reason`, the one place
ADR-0003 C4 is implemented. This module supplies the three facts that row cannot
compute for itself — the policy digest, the re-hashed sources and the recomputed
argument digest — and then lets the frozen contract answer. Re-deriving any of
it here would create a second implementation of the same rule, and a second
implementation is how two rules drift apart.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import Update

from labcairn.core.ids import ApprovalId, OperationId, RunId, TaskId
from labcairn.db.models import ApprovalRow, OperationRow
from labcairn.db.repository import Clock, TaskStore, utc_now
from labcairn.recovery.persistence import load_approval
from labcairn.runtime.event import EventTransition, EventType
from labcairn.runtime.operation import (
    Approval,
    ApprovalRefusal,
    ApprovalState,
    compute_args_digest,
)
from labcairn.security.approval import (
    AuthorizationRefusedError,
    NoSuchApprovalError,
    SourceBinding,
    assert_capability_registered,
    sources_intact,
)

#: How long a freshly issued approval stays usable when the caller does not say.
#: Long enough for a human to answer, short enough that an approval abandoned
#: overnight does not authorise a write the next morning.
DEFAULT_TTL_SECONDS: Final = 900


class ApprovalAlreadySpentError(AuthorizationRefusedError):
    """The conditional update matched zero rows: somebody else got there first.

    Distinct from :class:`ApprovalRefusal.CONSUMED` on purpose. ``CONSUMED``
    means this caller read a row that was already spent — an ordinary, expected
    refusal. This means this caller read a row that was *not* spent and then
    could not spend it, which is a race, and a caller that retries is right to
    do so.
    """

    def __init__(self, approval_id: ApprovalId) -> None:
        super().__init__(ApprovalRefusal.CONSUMED, detail=f"raced on approval {approval_id}")


class ApprovalStore:
    """Request, grant and consume approvals against the frozen ``approvals`` table."""

    __slots__ = ("_clock", "_session", "_store")

    def __init__(
        self,
        store: TaskStore,
        session: Session,
        *,
        clock: Clock | None = None,
    ) -> None:
        self._store = store
        self._session = session
        self._clock: Clock = clock or utc_now

    # -- lifecycle ----------------------------------------------------------- #

    def request(
        self,
        task_id: TaskId,
        run_id: RunId,
        operation_id: OperationId,
        *,
        capability: str,
        resource_key: str,
        args: Mapping[str, object],
        depends_on: tuple[str, ...] = (),
        expires_at: datetime | None = None,
    ) -> Approval:
        """Record a pending approval and emit ``approval_requested``.

        Pending is a real state and not a formality: it is what a UI renders,
        and it is what makes "was this ever approved?" answerable from the log
        even when nobody answered.

        The emitted event names the Run but **not** the operation. That is the
        frozen envelope's rule, not an oversight here: ADR-0003 C1 makes only
        ``operation_*`` events carry operation context, and :class:`Event`
        rejects the field outright on every other type. The link from an
        approval to the operation it authorises lives on the ``approvals`` row,
        where :attr:`Approval.operation_id` is a column — which is the right
        place for it anyway, since it has to survive a client that never sees
        the event.
        """
        expiry = expires_at if expires_at is not None else _default_expiry(self._clock)
        approval = Approval(
            task_id=task_id,
            operation_id=operation_id,
            capability=capability,
            resource_key=resource_key,
            args_digest=compute_args_digest(
                task_id=task_id,
                capability=capability,
                resource_key=resource_key,
                args=dict(args),
                depends_on=depends_on,
            ),
            state=ApprovalState.PENDING,
            expires_at=expiry,
        )
        with self._store.unit(task_id) as work:
            work.emit(
                EventType.APPROVAL_REQUESTED,
                run_id=run_id,
                transition=EventTransition(
                    from_state=ApprovalState.PENDING.value, to_state=ApprovalState.PENDING.value
                ),
            )
            work.put_approval(approval)
        return approval

    def grant(self, task_id: TaskId, approval_id: ApprovalId) -> Approval:
        """Move PENDING → GRANTED and emit ``approval_granted``."""
        approval = self._require(task_id, approval_id)
        if approval.state is not ApprovalState.PENDING:
            raise ValueError(
                f"approval {approval_id} is {approval.state.value}; only a PENDING "
                f"approval can be granted"
            )
        granted = approval.model_copy(
            update={"state": ApprovalState.GRANTED, "granted_at": self._clock()}
        )
        with self._store.unit(task_id) as work:
            work.emit(
                EventType.APPROVAL_GRANTED,
                run_id=self._run_id_for(approval),
                transition=_transition(ApprovalState.PENDING, ApprovalState.GRANTED),
            )
            work.put_approval(granted)
        return granted

    def deny(self, task_id: TaskId, approval_id: ApprovalId) -> Approval:
        """Move PENDING → DENIED. Terminal."""
        approval = self._require(task_id, approval_id)
        denied = approval.model_copy(update={"state": ApprovalState.DENIED})
        with self._store.unit(task_id) as work:
            work.emit(
                EventType.APPROVAL_DENIED,
                run_id=self._run_id_for(approval),
                transition=_transition(ApprovalState.PENDING, ApprovalState.DENIED),
            )
            work.put_approval(denied)
        return denied

    # -- the single-use path -------------------------------------------------- #

    def consume(
        self,
        task_id: TaskId,
        approval_id: ApprovalId,
        *,
        capability: str,
        resource_key: str,
        args: Mapping[str, object],
        depends_on: tuple[str, ...],
        current_policy_digest: str,
        policy_digest_at_grant: str,
        sources: tuple[SourceBinding, ...] = (),
        resolve_source: Callable[[str], Path],
    ) -> Approval:
        """Validate an approval for this exact use and spend it, atomically.

        The order is deliberate: **every** refusal is decided *before* the row is
        touched. An approval that fails its checks must still be unspent, because
        "we refused to use it" is not "we used it" — burning it on a refusal
        would punish a caller for asking a question the ADR says to ask.

        **The registry is asked first, before even the row is read.** A capability
        that is not registered is a fact about the request rather than about the
        approval, and ADR-0003 §C4's "evaluate before you consume" was only ever
        prose: nothing here asked whether the id named a capability this build
        has. See :func:`~labcairn.security.approval.assert_capability_registered`
        for why the ledger is the second choke point and not a replacement for
        the policy's verdict.

        The conditional update runs last and is the enforcement. Everything
        before it is a check that could, in principle, be wrong; this is the
        statement that makes two spends impossible.
        """
        assert_capability_registered(capability)
        approval = self._require(task_id, approval_id)
        now = self._clock()

        intact, changed = sources_intact(sources, resolve=resolve_source)
        recomputed = compute_args_digest(
            task_id=task_id,
            capability=capability,
            resource_key=resource_key,
            args=dict(args),
            depends_on=depends_on,
        )

        refusal = approval.refusal_reason(
            now=now,
            task_id=task_id,
            capability=capability,
            resource_key=resource_key,
            recomputed_digest=recomputed,
            depends_on_intact=intact,
            policy_unchanged=current_policy_digest == policy_digest_at_grant,
        )
        if refusal is not None:
            detail = f"changed sources: {list(changed)}" if changed else ""
            raise AuthorizationRefusedError(refusal, detail=detail)

        consumed = approval.model_copy(update={"state": ApprovalState.CONSUMED, "consumed_at": now})
        with self._store.unit(task_id) as work:
            result = cast(
                "CursorResult[Any]",
                work.session.execute(conditional_spend(approval_id, now)),
            )
            spent = result.rowcount
            if spent is None:
                # The driver did not report how many rows matched, so the
                # single-use property cannot be established from this statement.
                # Failing closed is the only safe reading: a default of zero here
                # would be indistinguishable from a genuine "already spent", and a
                # default of one would be a lie that authorises a second effect.
                raise ApprovalAlreadySpentError(approval_id)
            if spent != 1:
                raise ApprovalAlreadySpentError(approval_id)
            work.emit(
                EventType.APPROVAL_CONSUMED,
                run_id=self._run_id_for(approval),
                transition=_transition(ApprovalState.GRANTED, ApprovalState.CONSUMED),
            )
        return consumed

    # -- helpers --------------------------------------------------------------- #

    def _require(self, task_id: TaskId, approval_id: ApprovalId) -> Approval:
        """Load the row, or refuse.

        Deliberately does **not** compare ``task_id``. That check already exists
        inside :meth:`Approval.refusal_reason` as ``TASK_SCOPE_MISMATCH``, and
        duplicating it here would give the rule two homes — one of which would
        eventually stop being consulted.
        """
        approval = load_approval(self._session, approval_id)
        if approval is None:
            raise NoSuchApprovalError(str(approval_id))
        return approval

    def _run_id_for(self, approval: Approval) -> RunId:
        """The Run an approval's events belong to.

        ``Approval`` carries no ``run_id`` — the frozen contract has no such
        field — but ADR-0003 C1 makes every ``approval_*`` event Run-scoped, and
        the event envelope rejects one without it. The Run is therefore read
        back from the operation the approval was issued for, which is where the
        field actually lives. Looked up rather than passed in so that a caller
        cannot label one operation's approval as belonging to another's run.
        """
        run_id = self._session.execute(
            select(OperationRow.run_id).where(
                OperationRow.operation_id == str(approval.operation_id)
            )
        ).scalar_one_or_none()
        if run_id is None:
            raise NoSuchApprovalError(
                f"approval {approval.approval_id} names operation "
                f"{approval.operation_id}, which has no row; an approval for a "
                f"non-existent operation cannot be honoured"
            )
        return RunId(UUID(run_id))


def conditional_spend(approval_id: ApprovalId, now: datetime) -> Update:
    """The single statement that enforces ADR-0003 C4's single-use rule.

    Named and exported rather than inlined at the call site, because *this
    statement* is the guarantee: ``WHERE ... AND state = 'granted'`` makes the
    second attempt match zero rows, and :meth:`ApprovalStore.consume` turns that
    zero into a refusal. Everything before it in ``consume`` is a check that could
    in principle be wrong; this is the part that cannot be.

    A first draft inlined it, and the test that was supposed to prove the
    predicate load-bearing re-implemented the statement in the test file instead
    of calling it — so deleting the predicate from the product left the suite
    green. Naming it is what lets the test exercise the real thing.

    Whether the predicate is *reached* by a genuine concurrent race is a
    separate question this module does not claim: every unit opens with
    ``BEGIN IMMEDIATE``, so a concurrent second reader blocks on the write lock
    and is refused on read instead. The predicate is defence in depth against a
    future change to that transaction boundary.
    """
    return (
        update(ApprovalRow)
        .where(
            ApprovalRow.approval_id == str(approval_id),
            ApprovalRow.state == ApprovalState.GRANTED.value,
        )
        .values(state=ApprovalState.CONSUMED.value, consumed_at=now)
    )


def _transition(from_state: ApprovalState, to_state: ApprovalState) -> EventTransition:
    return EventTransition(from_state=from_state.value, to_state=to_state.value)


def _default_expiry(clock: Clock) -> datetime:
    return clock() + timedelta(seconds=DEFAULT_TTL_SECONDS)


__all__ = [
    "DEFAULT_TTL_SECONDS",
    "ApprovalAlreadySpentError",
    "ApprovalStore",
    "conditional_spend",
]
