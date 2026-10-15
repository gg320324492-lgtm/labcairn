"""Operation, Approval and Checkpoint — the side-effect machinery.

Everything here exists to answer one question honestly after a crash: *did this
side effect happen?* A database transaction can tell you what it committed. It
cannot tell you what a file write did, because the filesystem is not inside the
transaction. So the intent is written ahead of the attempt and the outcome is
confirmed behind it, and anything in between is recorded as UNCERTAIN rather
than guessed at.

See ADR-0003 C2 (state machine), C3 (transaction boundary) and C4 (approval
binding) — this module is their executable form, not a restatement of them.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field, ValidationInfo, field_validator

from labcairn.core.ids import ApprovalId, CheckpointId, OperationId, RunId, StageId, TaskId, new_id
from labcairn.core.primitives import StrictPosInt
from labcairn.core.schema import LabCairnModel


class OperationState(StrEnum):
    """ADR-0003 C2. ``UNCERTAIN`` is the state that makes the rest meaningful."""

    PLANNED = "planned"
    AWAITING_APPROVAL = "awaiting_approval"
    AUTHORIZED = "authorized"
    DENIED = "denied"
    ATTEMPTING = "attempting"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    UNCERTAIN = "uncertain"


#: States from which no further automatic transition is possible.
TERMINAL_OPERATION_STATES: frozenset[OperationState] = frozenset(
    {OperationState.DENIED, OperationState.CONFIRMED, OperationState.FAILED}
)


class ApprovalState(StrEnum):
    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    CONSUMED = "consumed"
    EXPIRED = "expired"


class ApprovalRefusal(StrEnum):
    """Why an approval was not honoured. Enumerated so callers can branch."""

    NOT_GRANTED = "not_granted"
    EXPIRED = "expired"
    CONSUMED = "consumed"
    TASK_SCOPE_MISMATCH = "task_scope_mismatch"
    ARGS_CHANGED = "args_changed"
    SOURCE_CHANGED = "source_changed"
    POLICY_CHANGED = "policy_changed"


class Operation(LabCairnModel):
    """One attempt at one side effect."""

    operation_id: OperationId = Field(default_factory=lambda: OperationId(new_id()))
    task_id: TaskId
    run_id: RunId
    stage_id: StageId
    state: OperationState = OperationState.PLANNED
    #: Registered capability id, not a free string: policy resolves by
    #: capability, and a typo must fail closed rather than fall through to a
    #: default.
    capability: str = Field(min_length=1, max_length=200)
    #: Canonical, workspace-relative, POSIX-separated. An uncanonicalisable
    #: path is a deny, not an ask — see ADR-0003 C4.
    resource_key: str = Field(min_length=1, max_length=2000)
    #: Sorted content hashes of every source this operation reads. This is the
    #: mechanism by which "changed source invalidates downstream".
    depends_on: tuple[str, ...] = ()
    #: SHA256 over the canonical form of (schema_version, task_id, capability,
    #: resource_key, args, depends_on). Recomputed at the moment of use.
    args_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


def compute_args_digest(
    *,
    task_id: TaskId,
    capability: str,
    resource_key: str,
    args: dict[str, object],
    depends_on: tuple[str, ...] = (),
) -> str:
    """SHA256 over the canonical arguments an approval is bound to.

    Fixed now so it cannot drift (ADR-0003 C4). Argument keys are sorted, no
    timestamps or counters enter the digest, and ``depends_on`` is the sorted
    content-hash list. Canonicalisation is JSON with sorted keys and no
    incidental whitespace, so the same logical call yields the same digest on
    any platform.
    """
    _reject_undigestible_args(args)
    payload = {
        "schema_version": 1,
        "task_id": str(task_id),
        "capability": capability,
        "resource_key": resource_key,
        "args": args,
        "depends_on": sorted(depends_on),
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _reject_undigestible_args(args: dict[str, object]) -> None:
    """Refuse arguments that would make the digest lie.

    Two failures were found by review and are cheap to prevent:

    - ``json.dumps`` coerces an integer key to a string, so ``{1: "x"}`` and
      ``{"1": "x"}`` produced the **same** digest. Two different operations
      would then share one approval.
    - ``json.dumps`` emits bare ``NaN``, which is not valid JSON, so no
      compliant reader could reproduce the digest — directly contradicting the
      "same digest on any platform" claim. It also raises a bare
      ``TypeError``, which a caller's ``except ValueError`` would not catch.
    """
    for key in args:
        if not isinstance(key, str):
            raise TypeError(
                f"args keys must be strings: {key!r} ({type(key).__name__}). "
                f"An integer key would be silently stringified by json.dumps and "
                f"collide with the equivalent string key."
            )
    try:
        json.dumps(args, allow_nan=False)
    except ValueError as exc:
        raise ValueError(
            f"args are not JSON-representable: {exc}. A NaN or Infinity would "
            f"produce a digest no compliant reader could reproduce."
        ) from exc
    except TypeError as exc:
        raise TypeError(f"args are not JSON-serialisable: {exc}") from exc


class Approval(LabCairnModel):
    """A human decision, recorded as a row rather than a transient UI flag.

    Single-use: consuming it moves the state, so one click cannot authorise two
    writes.
    """

    approval_id: ApprovalId = Field(default_factory=lambda: ApprovalId(new_id()))
    task_id: TaskId
    operation_id: OperationId
    capability: str = Field(min_length=1, max_length=200)
    resource_key: str = Field(min_length=1, max_length=2000)
    args_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    state: ApprovalState = ApprovalState.PENDING
    expires_at: datetime
    granted_at: datetime | None = None
    consumed_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def _pending_must_not_be_expired(cls, value: datetime, info: ValidationInfo) -> datetime:
        if info.data.get("state") is ApprovalState.PENDING and value <= datetime.now(UTC):
            raise ValueError("a pending approval must expire in the future")
        return value

    def refusal_reason(
        self,
        *,
        now: datetime,
        task_id: TaskId,
        capability: str,
        resource_key: str,
        recomputed_digest: str,
        depends_on_intact: bool,
        policy_unchanged: bool,
    ) -> ApprovalRefusal | None:
        """Why this approval may not be used right now, or ``None`` if it may.

        Every condition from ADR-0003 C4 is checked in one place so a caller
        cannot accidentally enforce a subset of them. Expiry is checked twice
        on purpose: once because the row may have been moved to EXPIRED, and
        once because a GRANTED row whose time has passed is expired even if
        nothing wrote that fact down.
        """
        if self.state is ApprovalState.CONSUMED:
            return ApprovalRefusal.CONSUMED
        if self.state is not ApprovalState.GRANTED:
            if self.state is ApprovalState.EXPIRED or self.expires_at <= now:
                return ApprovalRefusal.EXPIRED
            return ApprovalRefusal.NOT_GRANTED
        if self.expires_at <= now:
            return ApprovalRefusal.EXPIRED
        if self.task_id != task_id:
            return ApprovalRefusal.TASK_SCOPE_MISMATCH
        if self.capability != capability or self.resource_key != resource_key:
            return ApprovalRefusal.ARGS_CHANGED
        if recomputed_digest != self.args_digest:
            return ApprovalRefusal.ARGS_CHANGED
        if not depends_on_intact:
            return ApprovalRefusal.SOURCE_CHANGED
        if not policy_unchanged:
            return ApprovalRefusal.POLICY_CHANGED
        return None


class Checkpoint(LabCairnModel):
    """Immutable, versioned evidence that a stage boundary was crossed."""

    checkpoint_id: CheckpointId = Field(default_factory=lambda: CheckpointId(new_id()))
    task_id: TaskId
    run_id: RunId
    stage_id: StageId
    #: Highest per-Task ``seq`` included. Per ADR-0003 C1 this is the only
    #: ordering; a wall-clock time is never used to order anything.
    through_seq: StrictPosInt
    material_hashes: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
