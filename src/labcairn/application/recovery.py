"""The recovery pass a surface runs, and what a surface can and cannot answer.

ADR-0003 C2 gives crash recovery two halves. The first is **entering**
``UNCERTAIN``: a process died with an operation ``ATTEMPTING``, which is the one
state that says *the record does not know whether the effect happened*. The
second is **resolving** it, which only a probe may do.

Until this module existed, only the demos ran either half. The CLI and the local
service let an abandoned operation sit at ``ATTEMPTING`` forever, and the next
``task run`` planned a **second** operation for the same work — which is the
protocol's fourth blocker in the shape it takes at a surface, and the finding
``docs/acceptance/G5-acceptance.md`` handed over rather than fixed.

:func:`reconcile_abandoned` is the first half, and it runs at the front of every
stage run, so every surface gets it: the operation moves to ``UNCERTAIN``, the
stage is blocked with the reason the recovery layer states, and the run is
**refused** rather than replanned. No second operation is ever planned for work
whose outcome is unknown, and the record stops claiming a work is in flight when
no process is running it.

**The second half is deliberately not automatic here.** A probe answers "are the
bytes this operation predicted at the path this operation named?", and the
prediction is not in the store: it lived in ``args`` and therefore in
``args_digest``, which is a hash of a hash —
:func:`~labcairn.recovery.reconciliation.RecoveryCoordinator.reconcile` says so
at its own signature and requires the caller to state the value. **A surface
that invented a hash would be guessing at whether your data moved.** So
:func:`resolve_abandoned` is the operator's answer, and the CLI is the surface
that asks for it. What is *not* possible from a surface is a reconciliation that
quietly assumes the effect did not land, which is the failure ADR-0003 A2
rejected in OpenHands' orphan-action recovery.
"""

from __future__ import annotations

from datetime import datetime

from labcairn.application.context import ApplicationContext, store_refusals
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.core.ids import OperationId
from labcairn.recovery.contracts import (
    ContentHash,
    ProbeVerdict,
    ReconciliationOutcome,
    ReconciliationRequired,
    ReconciliationResolution,
    UnknownOperationError,
)
from labcairn.recovery.persistence import find_operations_in_state
from labcairn.recovery.reconciliation import RecoveryCoordinator
from labcairn.runtime.operation import Operation, OperationState
from labcairn.security.approval import content_hash
from labcairn.workspace.roots import AllowedRoot

#: A SHA-256 as the contracts spell it: 64 lowercase hex characters. The store
#: pattern-checks its digest columns the same way, so the shape is the product's
#: own and not this module's invention.
_HASH_LENGTH = 64


class WorkspaceResourceProbe:
    """Answer "did this operation's effect land?" for a record that names no root.

    **Why this exists rather than :class:`FileSystemProbe`.** An operation row
    carries ``resource_key`` and nothing else, and that key is relative to the
    **root the request named**, not to the workspace: a material in
    ``source:0`` is ``notes.md``, not ``materials/notes.md``. A probe rooted at the
    workspace would therefore ask about a path that never existed, answer
    "nothing is there", and call a landed effect a missing one — the exact
    inversion this module exists to prevent.

    So the key is asked of every root the workspace holds, and the answer is
    shaped by what is found:

    * **nothing at any root** — ``REPLAY_SAFE``. The effect provably did not land
      anywhere this workspace can name.
    * **one file, same bytes** — ``CONFIRMED``.
    * **one file, other bytes** — ``CONFLICT``. Nothing is overwritten.
    * **the same key in more than one root** — ``CONFLICT``, not a guess. The
      record cannot say which root the operation addressed, and picking one would
      make the recovery's answer depend on the order a tuple happens to be in.
    """

    __slots__ = ("_roots",)

    def __init__(self, roots: tuple[AllowedRoot, ...]) -> None:
        self._roots = roots

    def inspect(self, resource_key: str, expected_sha256: ContentHash) -> ProbeVerdict:
        """Read-only: no path is created, opened for writing, truncated or removed."""
        parts = resource_key.split("/")
        present = [
            (root, path) for root in self._roots if (path := root.path.joinpath(*parts)).is_file()
        ]

        if not present:
            return ProbeVerdict(
                resolution=ReconciliationResolution.REPLAY_SAFE,
                resource_key=resource_key,
                expected_sha256=expected_sha256,
                observed_sha256=None,
                detail=(
                    "no file with this key is in any root of the workspace; the effect "
                    "provably did not land"
                ),
            )

        if len(present) > 1:
            named = ", ".join(f"{root.root_id}/{resource_key}" for root, _ in present)
            return ProbeVerdict(
                resolution=ReconciliationResolution.CONFLICT,
                resource_key=resource_key,
                expected_sha256=expected_sha256,
                observed_sha256=None,
                detail=(
                    f"the key is held by {len(present)} roots ({named}) and the operation "
                    "does not record which it addressed. Choosing one would make the "
                    "answer depend on the order the roots are stored in."
                ),
            )

        root, path = present[0]
        try:
            observed = content_hash(path)
        except OSError as error:  # an unreadable file is not evidence it did not land
            return ProbeVerdict(
                resolution=ReconciliationResolution.CONFLICT,
                resource_key=resource_key,
                expected_sha256=expected_sha256,
                observed_sha256=None,
                detail=f"{root.root_id}/{resource_key} exists but cannot be read: {error}",
            )

        if observed == expected_sha256:
            return ProbeVerdict(
                resolution=ReconciliationResolution.CONFIRMED,
                resource_key=resource_key,
                expected_sha256=expected_sha256,
                observed_sha256=observed,
                detail=f"the predicted bytes are on disk at {root.root_id}/{resource_key}",
            )

        return ProbeVerdict(
            resolution=ReconciliationResolution.CONFLICT,
            resource_key=resource_key,
            expected_sha256=expected_sha256,
            observed_sha256=observed,
            detail=(
                f"a file is at {root.root_id}/{resource_key} but its content is not what "
                "this operation predicted. It may be a partial write, an earlier "
                "revision, or something else entirely. No automatic action: overwriting "
                "could destroy work this operation did not produce."
            ),
        )


def _coordinator(context: ApplicationContext) -> RecoveryCoordinator:
    """The recovery coordinator for this context, probing the workspace's roots."""
    return RecoveryCoordinator(
        context.store,
        context.store.session,
        workspace_root=context.workspace.selected_root,
        probe=WorkspaceResourceProbe(context.workspace.roots),
    )


def reconcile_abandoned(
    context: ApplicationContext,
    *,
    now: datetime | None = None,
) -> tuple[Operation, ...]:
    """Return every operation of this task whose outcome is unknown, entering doubt.

    Two shapes arrive here, and a run must be refused for both: an operation a
    crash left ``ATTEMPTING``, which this call moves into ``UNCERTAIN`` and blocks
    its stage; and an operation already in ``UNCERTAIN`` — which means someone has
    already asked the question and no probe has answered it. The second is the one
    that is easy to miss, and missing it lets a run plan a second operation for
    work a human has not decided about.

    Idempotent, and safe to call at the front of every stage run: an operation
    already in ``UNCERTAIN`` is left exactly as it is, and no second
    ``operation_uncertain`` event is written. **What this does not do is resolve
    anything** — entering doubt is the honest half of what a surface can do with
    a crash it did not witness.

    :returns: the operations whose outcome the record cannot state, in the order
        the store holds them. Empty, which is the normal case, when nothing was
        abandoned and nothing is waiting on a probe.
    :raises ApplicationRefusedError: the store refused the read or the write.
    """
    del now  # the coordinator takes its own clock; the transition is not timestamped here
    with store_refusals():
        abandoned = find_operations_in_state(
            context.store.session, context.task_id, OperationState.ATTEMPTING
        )
    if abandoned:
        with store_refusals():
            _coordinator(context).mark_uncertain(context.task_id)
    with store_refusals():
        return find_operations_in_state(
            context.store.session, context.task_id, OperationState.UNCERTAIN
        )


def describe_abandoned(operations: tuple[Operation, ...]) -> str:
    """The refusal message for a run that found work in doubt.

    It names the operations and the one command that can answer them, because a
    refusal whose remedy is not stated is a dead end rather than a decision.
    """
    named = ", ".join(
        f"{operation.operation_id} ({operation.capability})" for operation in operations
    )
    return (
        f"a crash left {len(operations)} operation(s) whose outcome the record cannot "
        f"state: {named}. The stage is blocked, and replay is refused — re-running "
        "would plan a second operation for work that may already have happened. "
        "Resolve it with the probe it needs: "
        f"`labcairn task reconcile {operations[0].operation_id} "
        "--expected-sha256 <the content hash this operation predicted>`. "
        "The hash is not in the store, so this cannot be answered automatically."
    )


def resolve_abandoned(
    context: ApplicationContext,
    operation_id: OperationId,
    *,
    expected_sha256: str,
) -> ReconciliationOutcome:
    """Answer the question a crash left open, for one operation.

    **The caller states the predicted hash.** It is the only fact the store cannot
    supply, and the only one a probe needs: without it the answer would be
    "the file is there", which is not "the bytes this operation wrote are there".

    :raises ApplicationRefusedError: the hash is not a SHA-256, the operation does
        not exist, it is not in ``UNCERTAIN``, or the probe found bytes at the
        canonical path that this operation did not predict — the last one is a
        ``CONFLICT`` and stays blocked, because overwriting a file this operation
        did not write is not a recovery, it is a second writer.
    """
    if len(expected_sha256) != _HASH_LENGTH or any(
        character not in "0123456789abcdef" for character in expected_sha256.lower()
    ):
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"expected_sha256 must be 64 hexadecimal characters, not {expected_sha256!r}. "
            "It is the content hash the operation predicted, not a path or a prefix.",
        )

    coordinator = _coordinator(context)
    try:
        with store_refusals():
            outcome = coordinator.reconcile(operation_id, expected_sha256=expected_sha256.lower())
    except UnknownOperationError as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.OPERATION_NOT_FOUND,
            f"the store holds no operation {operation_id}.",
        ) from error
    except ReconciliationRequired as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.OPERATION_NOT_UNCERTAIN,
            f"operation {operation_id} is {error.state.value}, not uncertain. Only an "
            "operation whose outcome is unknown can be reconciled — a confirmed one "
            "is settled and a replanned one would duplicate its effect.",
        ) from error

    if outcome.resolution is ReconciliationResolution.CONFLICT:
        # The coordinator does not raise for a conflict — it leaves the operation in
        # UNCERTAIN, keeps the stage blocked and hands the verdict back. At a surface
        # that answer is a refusal: the operator asked the work to continue, and what
        # it gets is "bytes you did not predict are there, and nothing was overwritten".
        verdict = outcome.verdict
        raise ApplicationRefusedError(
            ApplicationRefusal.OPERATION_CONFLICT,
            f"reconciliation found a conflict for operation {operation_id}. "
            f"Expected {verdict.expected_sha256}, observed {verdict.observed_sha256}. "
            "The operation stays uncertain and the stage stays blocked: overwriting "
            "a file this operation did not write is a second writer, not a recovery.",
        )
    return outcome


__all__ = ["describe_abandoned", "reconcile_abandoned", "resolve_abandoned"]
