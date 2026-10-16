"""Approval binding: what a human said yes to, and proving it is still that.

The decision machinery here is **not** written in this module.
:mod:`labcairn.runtime.operation` already freezes the whole of ADR-0003 §C4 —
:meth:`~labcairn.runtime.operation.Approval.refusal_reason` checks every
condition the ADR lists, in one place, so a caller cannot enforce a subset of
them by accident. Re-deriving any of that here would mean two implementations
of the same rule that could drift, and the whole value of that function is
that it is *one* place.

So this module supplies the three things §C4 needs and ``Approval`` does not
carry, and then delegates:

1. **The policy snapshot digest.** §C4 requires *the policy snapshot still
   equals current policy*, and :class:`~labcairn.security.policy.PermissionPolicy`
   produces that digest. ``Approval`` has no field for it, so
   :class:`ApprovalGrant` — the application-side record that pairs an
   ``Approval`` row with the policy it was decided under — holds it here.

2. **The source hashes, checked against the disk.** §C4's ``depends_on`` names
   the hashes; something has to go and re-hash the files to find out whether
   they still match, because that is the mechanism by which "changed source
   invalidates downstream" is enforced rather than merely intended.

3. **Single-use accounting.** ``Approval`` is frozen, so consuming one means
   producing the ``CONSUMED`` successor and remembering it.
   :class:`ApprovalLedger` is that memory.

Why consume *before* the effect, not after
------------------------------------------
The alternative — authorise, do the work, then mark consumed — leaves a window
in which a retry loop, a concurrent stage, or a crash-and-retry can spend the
same approval twice. LC-P1-04's acceptance is that a single approval cannot
authorise two writes, and the only way to guarantee that under concurrency and
crash is to make the consumption the first irreversible step. The cost is that a
failed write still burns its approval; that is the correct trade, because
re-asking a human is cheap and silently repeating a side effect is not.

Persistence
-----------
:class:`ApprovalLedger` is in-memory and exists so LC-P1-04 can be accepted and
tested. LC-P1-05 moves it into SQLite next to the ``Approval`` row, at which
point ``consume`` becomes a conditional ``UPDATE ... WHERE state = 'granted'``
whose affected-row count is the single-use guarantee. The API here is shaped
for that move: the ledger is the only owner of the state transition, and it
takes the current ``Approval`` in and returns the successor out.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from labcairn.core.ids import ApprovalId, OperationId, TaskId
from labcairn.runtime.operation import (
    Approval,
    ApprovalRefusal,
    ApprovalState,
    compute_args_digest,
)
from labcairn.security.paths import CanonicalPath
from labcairn.security.policy import PermissionDecision

#: Read size for content hashing. 1 MiB keeps peak memory flat for a large
#: source file; hashing is I/O-bound anyway.
_HASH_CHUNK_BYTES: Final = 1024 * 1024


class NoSuchApprovalError(KeyError):
    """An approval id that was never issued, or has already been consumed.

    Distinct from an :class:`~labcairn.runtime.operation.ApprovalRefusal` value:
    a refusal is a *recorded decision about a known approval*, whereas this is
    "there is no such row". They are different failures and an audit log that
    conflates them cannot answer "was this ever approved?".
    """


class AuthorizationRefusedError(RuntimeError):
    """The request is not authorised, and why.

    Carries the machine-readable reason so the caller records it rather than
    re-deriving it from a message. Raised rather than returned so that a caller
    which forgets to check cannot proceed: the effect is downstream of this call
    in every path, and a forgotten boolean is the standard way a permission
    check becomes decorative.
    """

    def __init__(self, refusal: ApprovalRefusal, *, detail: str = "") -> None:
        message = f"approval refused: {refusal.value}"
        super().__init__(f"{message} — {detail}" if detail else message)
        self.refusal = refusal


class PermissionDeniedError(RuntimeError):
    """The policy verdict was DENY. No approval can override this."""

    def __init__(self, decision: PermissionDecision) -> None:
        detail = f"{decision.reason.value}"
        if decision.matched_rule:
            detail += f" (rule: {decision.matched_rule})"
        super().__init__(f"permission denied: {detail}")
        self.decision = decision


def content_hash(path: Path) -> str:
    """SHA256 of a file's bytes, lowercase hex — the form ``depends_on`` holds.

    Raises :class:`OSError` if the file cannot be read. Callers treating "source
    changed" and "source unreadable" differently must do so explicitly; the
    permission answer for both is the same, because §C4 requires every hash to
    still match and an unverifiable hash does not match.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class SourceBinding:
    """One source file an operation depends on, with the hash it had.

    ``resource_key`` rather than a :class:`~pathlib.Path`: what is being
    promised is about the *canonical* file, and a path that has since been
    re-pointed by a junction is no longer that file. Re-hashing goes through
    the workspace, which re-canonicalises.
    """

    resource_key: str
    expected_hash: str


@dataclass(frozen=True, slots=True)
class ApprovalGrant:
    """An :class:`Approval` paired with the context it was decided in.

    This is the missing half of §C4. The ``Approval`` row records *what* was
    approved and by whom; this records the policy digest and the source hashes
    in force at that moment, which are the two conditions the row itself cannot
    check.
    """

    approval: Approval
    policy_digest: str
    sources: tuple[SourceBinding, ...] = field(default_factory=tuple)

    @property
    def approval_id(self) -> ApprovalId:
        return self.approval.approval_id


def sources_intact(
    sources: Iterable[SourceBinding],
    *,
    resolve: Callable[[str], Path],
) -> tuple[bool, tuple[str, ...]]:
    """Re-hash every bound source and report whether they all still match.

    ``resolve`` maps a resource key back to its real path and must re-run
    :func:`~labcairn.security.paths.canonicalize`, so that a source which has
    since been replaced by a symlink is caught here as well as at evaluation.

    :returns: ``(all_intact, changed_keys)``. The changed keys are returned as
        well as a boolean so the event log can record *which* source moved,
        which is the difference between "retry the stage" and "the upstream
        document was edited on disk".
    """
    changed: list[str] = []
    for binding in sources:
        try:
            target = resolve(binding.resource_key)
        except (OSError, ValueError):
            changed.append(binding.resource_key)
            continue
        try:
            actual = content_hash(target)
        except OSError:
            changed.append(binding.resource_key)
            continue
        if actual != binding.expected_hash:
            changed.append(binding.resource_key)
    return (not changed, tuple(changed))


class ApprovalLedger:
    """Single-use accounting for approvals.

    Phase 1's in-memory implementation of the §C4 consumption rule. See the
    module docstring for why consumption happens at authorisation time and for
    where this moves in LC-P1-05.
    """

    def __init__(self) -> None:
        self._grants: dict[ApprovalId, ApprovalGrant] = {}

    def issue(self, grant: ApprovalGrant) -> ApprovalGrant:
        """Record a newly granted approval. A pending row is refused."""
        if grant.approval.state is not ApprovalState.GRANTED:
            msg = f"cannot issue an approval in state {grant.approval.state.value}"
            raise ValueError(msg)
        self._grants[grant.approval_id] = grant
        return grant

    def peek(self, approval_id: ApprovalId) -> ApprovalGrant | None:
        return self._grants.get(approval_id)

    def consume(
        self,
        approval_id: ApprovalId,
        *,
        now: datetime,
        task_id: TaskId,
        capability: str,
        resource: CanonicalPath,
        args: Mapping[str, object],
        depends_on: tuple[str, ...],
        current_policy_digest: str,
        resolve_source: Callable[[str], Path],
    ) -> ApprovalGrant:
        """Validate an approval for one specific use and consume it.

        Every condition comes from
        :meth:`~labcairn.runtime.operation.Approval.refusal_reason`; this method
        only supplies the three facts the ``Approval`` row cannot compute for
        itself — the policy digest, the re-hashed sources, and the recomputed
        digest of the arguments **as they are right now**.

        The recomputation at the moment of use is the load-bearing part. §C4
        says the digest is *recomputed at the moment of use* and compared; a
        check that trusted the digest stored on the row would be satisfied by
        any row at all, since an attacker who can write a row can write its
        digest.

        :raises NoSuchApprovalError: the id was never issued or is already consumed.
        :raises AuthorizationRefusedError: named with the ADR's own reason enum.
        """
        grant = self._grants.get(approval_id)
        if grant is None:
            raise NoSuchApprovalError(str(approval_id))

        policy_unchanged = grant.policy_digest == current_policy_digest
        intact, changed = sources_intact(grant.sources, resolve=resolve_source)

        recomputed = compute_args_digest(
            task_id=task_id,
            capability=capability,
            resource_key=resource.resolved_key,
            args=dict(args),
            depends_on=depends_on,
        )

        refusal = grant.approval.refusal_reason(
            now=now,
            task_id=task_id,
            capability=capability,
            resource_key=resource.resolved_key,
            recomputed_digest=recomputed,
            depends_on_intact=intact,
            policy_unchanged=policy_unchanged,
        )
        if refusal is not None:
            detail = f"changed sources: {list(changed)}" if changed else ""
            raise AuthorizationRefusedError(refusal, detail=detail)

        # Consumption is the first irreversible step of the operation, and it
        # happens here rather than after the effect: see the module docstring.
        consumed_at = now
        consumed = grant.approval.model_copy(
            update={"state": ApprovalState.CONSUMED, "consumed_at": consumed_at}
        )
        updated = ApprovalGrant(
            approval=consumed,
            policy_digest=grant.policy_digest,
            sources=grant.sources,
        )
        self._grants[approval_id] = updated
        return updated


def make_approval(
    *,
    task_id: TaskId,
    operation_id: OperationId,
    capability: str,
    resource: CanonicalPath,
    args: Mapping[str, object],
    depends_on: tuple[str, ...] = (),
    expires_at: datetime,
) -> Approval:
    """Build a pending :class:`Approval` bound to this exact request.

    The digest is computed here from the same inputs
    :meth:`ApprovalLedger.consume` will recompute, so a caller cannot
    accidentally record an approval for one thing and attempt another. It is
    still re-derived at use; this is the *expected* value, not a cache.
    """
    return Approval(
        task_id=task_id,
        operation_id=operation_id,
        capability=capability,
        resource_key=resource.resolved_key,
        args_digest=compute_args_digest(
            task_id=task_id,
            capability=capability,
            resource_key=resource.resolved_key,
            args=dict(args),
            depends_on=depends_on,
        ),
        state=ApprovalState.PENDING,
        expires_at=expires_at,
    )


def utc_now() -> datetime:
    """The single clock entry point, so tests can substitute a frozen one."""
    return datetime.now(UTC)


__all__ = [
    "ApprovalGrant",
    "ApprovalLedger",
    "AuthorizationRefusedError",
    "NoSuchApprovalError",
    "PermissionDeniedError",
    "SourceBinding",
    "content_hash",
    "make_approval",
    "sources_intact",
    "utc_now",
]
