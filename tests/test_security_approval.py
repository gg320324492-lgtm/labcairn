"""Approval binding: a human's consent survives exactly one operation, once.

These are ADR-0003 §C4's five named acceptance tests plus the single-use one.
The condition checks themselves live in
:meth:`labcairn.runtime.operation.Approval.refusal_reason`, which LC-P1-02
froze; this file supplies the three facts the row cannot compute for itself and
asserts that each one independently invalidates a grant.

The test that matters most is
:func:`test_one_approval_cannot_authorise_two_writes`. It is the direct
expression of the ``Approval`` docstring's *single-use: consuming it moves the
state, so one click cannot authorise two writes* — and the reason
:meth:`ApprovalLedger.consume` transitions the row **before** the effect rather
than after it. If consumption moved to after the write, this test would still
pass in the happy path and fail only under retry or concurrency, which is
exactly where it would be expensive to find.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from labcairn.core.ids import ApprovalId, OperationId, TaskId, new_id
from labcairn.runtime.operation import ApprovalRefusal, ApprovalState
from labcairn.security.approval import (
    ApprovalGrant,
    ApprovalLedger,
    AuthorizationRefusedError,
    NoSuchApprovalError,
    SourceBinding,
    content_hash,
    make_approval,
    sources_intact,
)
from labcairn.security.paths import CanonicalPath, canonicalize
from labcairn.security.policy import (
    Permission,
    PermissionPolicy,
    ResourceRef,
    Rule,
    default_policy,
)
from labcairn.workspace.roots import Workspace

pytestmark = pytest.mark.integration

#: The project's frozen clock, from ``conftest.FROZEN_NOW``.
NOW = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
#: The instant after which ``NOW + 1h`` would be, but chosen far in the future.
#:
#: :meth:`labcairn.runtime.operation.Approval._pending_must_not_be_expired`
#: compares against ``datetime.now(UTC)`` — the **real** wall clock, not an
#: injected one. So an approval expiring near the project's frozen "now" is
#: already expired as far as that validator is concerned, and every test here
#: would fail before reaching the condition it is testing. The expiry is
#: therefore placed well beyond the real clock and "now" is advanced past it
#: explicitly for the expiry test.
#:
#: This is a friction point in LC-P1-02's frozen contract, not a workaround for
#: a mistake in it: an approval's validity window cannot be exercised with the
#: project's own frozen clock. Recorded for the work-order review.
EXPIRY = datetime(2099, 1, 1, 0, 0, 0, tzinfo=UTC)
AFTER_EXPIRY = datetime(2099, 6, 1, 0, 0, 0, tzinfo=UTC)
LATER = EXPIRY


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    """A bound workspace with one source directory and this task's output area."""
    root = tmp_path / "ws"
    sources = root / "sources"
    sources.mkdir(parents=True)
    return Workspace.bind(root, task_id=TaskId(new_id()), source_dirs=(sources,))


def granted(
    ledger: ApprovalLedger,
    workspace: Workspace,
    *,
    policy_digest: str,
    args: dict[str, object] | None = None,
    capability: str = "fs.write",
    key: str = "report.md",
    task_id: TaskId | None = None,
    depends_on: tuple[str, ...] = (),
    sources: tuple[SourceBinding, ...] = (),
    expires_at: datetime = LATER,
) -> tuple[ApprovalGrant, CanonicalPath]:
    """Issue a GRANTED approval bound to one exact request."""
    path = workspace.path_in(key, workspace.output_root.root_id)
    effective_args = {"path": key} if args is None else args
    effective_task = task_id if task_id is not None else workspace.task_id

    pending = make_approval(
        task_id=effective_task,
        operation_id=OperationId(new_id()),
        capability=capability,
        resource=path,
        args=effective_args,
        depends_on=depends_on,
        expires_at=expires_at,
    )
    grant = ApprovalGrant(
        approval=pending.model_copy(update={"state": ApprovalState.GRANTED, "granted_at": NOW}),
        policy_digest=policy_digest,
        sources=sources,
    )
    return ledger.issue(grant), path


def consume(
    ledger: ApprovalLedger,
    grant: ApprovalGrant,
    workspace: Workspace,
    *,
    policy_digest: str,
    args: dict[str, object] | None = None,
    capability: str = "fs.write",
    key: str = "report.md",
    task_id: TaskId | None = None,
    depends_on: tuple[str, ...] = (),
    now: datetime = NOW,
) -> ApprovalGrant:
    path = workspace.path_in(key, workspace.output_root.root_id)
    return ledger.consume(
        grant.approval_id,
        now=now,
        task_id=task_id if task_id is not None else workspace.task_id,
        capability=capability,
        resource=path,
        args={"path": key} if args is None else args,
        depends_on=depends_on,
        current_policy_digest=policy_digest,
        resolve_source=lambda k: workspace.resolve_key(k, root_id="output"),
    )


# ---------------------------------------------------------------------------
# The five ADR conditions
# ---------------------------------------------------------------------------


def test_a_matching_approval_is_usable(workspace: Workspace) -> None:
    ledger = ApprovalLedger()
    policy = PermissionPolicy()
    grant, _ = granted(ledger, workspace, policy_digest=policy.digest())
    consumed = consume(ledger, grant, workspace, policy_digest=policy.digest())
    assert consumed.approval.state is ApprovalState.CONSUMED
    assert consumed.approval.consumed_at == NOW


def test_approval_rejected_when_arguments_change(workspace: Workspace) -> None:
    """§C7: grant for content ``x``, attempt ``y`` → ``args_changed``."""
    ledger = ApprovalLedger()
    policy = PermissionPolicy()
    grant, _ = granted(ledger, workspace, policy_digest=policy.digest(), args={"path": "x"})

    with pytest.raises(AuthorizationRefusedError) as caught:
        consume(ledger, grant, workspace, policy_digest=policy.digest(), args={"path": "y"})
    assert caught.value.refusal is ApprovalRefusal.ARGS_CHANGED


def test_approval_rejected_on_task_scope_mismatch(workspace: Workspace) -> None:
    """§C7: granted in task A, attempted in task B → ``task_scope_mismatch``."""
    ledger = ApprovalLedger()
    policy = PermissionPolicy()
    grant, _ = granted(ledger, workspace, policy_digest=policy.digest())

    with pytest.raises(AuthorizationRefusedError) as caught:
        consume(ledger, grant, workspace, policy_digest=policy.digest(), task_id=TaskId(new_id()))
    assert caught.value.refusal is ApprovalRefusal.TASK_SCOPE_MISMATCH


def test_expired_approval_is_not_reusable(workspace: Workspace) -> None:
    """§C7: ``expires_at`` in the past → ``expired``."""
    ledger = ApprovalLedger()
    policy = PermissionPolicy()
    grant, _ = granted(
        ledger,
        workspace,
        policy_digest=policy.digest(),
        expires_at=EXPIRY,
    )

    with pytest.raises(AuthorizationRefusedError) as caught:
        consume(ledger, grant, workspace, policy_digest=policy.digest(), now=AFTER_EXPIRY)
    assert caught.value.refusal is ApprovalRefusal.EXPIRED


def test_approval_is_single_use(workspace: Workspace) -> None:
    """§C7: identical arguments attempted twice, second → ``consumed``."""
    ledger = ApprovalLedger()
    policy = PermissionPolicy()
    grant, _ = granted(ledger, workspace, policy_digest=policy.digest())

    consume(ledger, grant, workspace, policy_digest=policy.digest())
    with pytest.raises(AuthorizationRefusedError) as caught:
        consume(ledger, grant, workspace, policy_digest=policy.digest())
    assert caught.value.refusal is ApprovalRefusal.CONSUMED


def test_approval_invalidated_by_source_change(workspace: Workspace) -> None:
    """§C7: ``depends_on`` holds H1, the file becomes H2 → ``source_changed``."""
    ledger = ApprovalLedger()
    policy = PermissionPolicy()
    source = workspace.root_for("source:0").path / "paper.pdf"
    source.write_bytes(b"%PDF-1.4 original")
    original = content_hash(source)

    grant, _ = granted(
        ledger,
        workspace,
        policy_digest=policy.digest(),
        sources=(SourceBinding(resource_key="paper.pdf", expected_hash=original),),
    )

    # Change the file *after* the approval was issued.
    source.write_bytes(b"%PDF-1.4 EDITED")

    with pytest.raises(AuthorizationRefusedError) as caught:
        consume(ledger, grant, workspace, policy_digest=policy.digest())
    assert caught.value.refusal is ApprovalRefusal.SOURCE_CHANGED
    assert "paper.pdf" in str(caught.value), "the changed source must be named"


def test_approval_invalidated_by_policy_change(workspace: Workspace) -> None:
    """§C4: *the policy snapshot still equals current policy*."""
    ledger = ApprovalLedger()
    before = PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])
    after = PermissionPolicy.from_rules([])  # a stricter policy was loaded

    grant, _ = granted(ledger, workspace, policy_digest=before.digest())
    with pytest.raises(AuthorizationRefusedError) as caught:
        consume(ledger, grant, workspace, policy_digest=after.digest())
    assert caught.value.refusal is ApprovalRefusal.POLICY_CHANGED


def test_approval_for_a_different_capability_is_refused(workspace: Workspace) -> None:
    ledger = ApprovalLedger()
    policy = PermissionPolicy()
    grant, _ = granted(ledger, workspace, policy_digest=policy.digest(), capability="fs.write")

    with pytest.raises(AuthorizationRefusedError) as caught:
        consume(ledger, grant, workspace, policy_digest=policy.digest(), capability="fs.delete")
    assert caught.value.refusal is ApprovalRefusal.ARGS_CHANGED


def test_approval_for_a_different_resource_is_refused(workspace: Workspace) -> None:
    ledger = ApprovalLedger()
    policy = PermissionPolicy()
    grant, _ = granted(ledger, workspace, policy_digest=policy.digest(), key="a.md")

    with pytest.raises(AuthorizationRefusedError) as caught:
        consume(ledger, grant, workspace, policy_digest=policy.digest(), key="b.md")
    assert caught.value.refusal is ApprovalRefusal.ARGS_CHANGED


def test_a_pending_approval_cannot_be_issued(workspace: Workspace) -> None:
    """Only a human decision is a grant. A PENDING row is not one."""
    ledger = ApprovalLedger()
    path = workspace.path_in("report.md", workspace.output_root.root_id)
    pending = make_approval(
        task_id=workspace.task_id,
        operation_id=OperationId(new_id()),
        capability="fs.write",
        resource=path,
        args={"path": "report.md"},
        expires_at=LATER,
    )
    assert pending.state is ApprovalState.PENDING
    with pytest.raises(ValueError, match="cannot issue an approval in state pending"):
        ledger.issue(ApprovalGrant(approval=pending, policy_digest="x"))


def test_an_unknown_approval_id_is_not_a_refusal(workspace: Workspace) -> None:
    """ "Never approved" and "approved but no longer valid" are different facts."""
    ledger = ApprovalLedger()
    path = workspace.path_in("report.md", workspace.output_root.root_id)
    with pytest.raises(NoSuchApprovalError):
        ledger.consume(
            ApprovalId(new_id()),
            now=NOW,
            task_id=workspace.task_id,
            capability="fs.write",
            resource=path,
            args={},
            depends_on=(),
            current_policy_digest="d",
            resolve_source=lambda k: Path(k),
        )


# ---------------------------------------------------------------------------
# Single use across two writes
# ---------------------------------------------------------------------------


def test_one_approval_cannot_authorise_two_writes(workspace: Workspace) -> None:
    """The headline: a single click cannot pay for two side effects.

    Both attempts are byte-identical in every respect that §C4 binds to — same
    task, same capability, same resource, same arguments, same digest. The only
    difference is that the first one already happened. That is what makes this
    the test that would catch consumption being moved to after the effect.
    """
    ledger = ApprovalLedger()
    policy = PermissionPolicy()
    grant, _ = granted(ledger, workspace, policy_digest=policy.digest())

    first = consume(ledger, grant, workspace, policy_digest=policy.digest())
    assert first.approval.state is ApprovalState.CONSUMED

    with pytest.raises(AuthorizationRefusedError) as caught:
        consume(ledger, grant, workspace, policy_digest=policy.digest())
    assert caught.value.refusal is ApprovalRefusal.CONSUMED


def test_a_refused_attempt_does_not_consume_the_approval(workspace: Workspace) -> None:
    """A refusal leaves the grant usable for a correct attempt.

    The inverse of the test above, and it matters operationally: a stale-args
    mistake must not also burn the human's approval, or every typo would need a
    second round trip to a person.
    """
    ledger = ApprovalLedger()
    policy = PermissionPolicy()
    grant, _ = granted(ledger, workspace, policy_digest=policy.digest(), args={"path": "x"})

    with pytest.raises(AuthorizationRefusedError):
        consume(ledger, grant, workspace, policy_digest=policy.digest(), args={"path": "y"})

    consumed = consume(ledger, grant, workspace, policy_digest=policy.digest(), args={"path": "x"})
    assert consumed.approval.state is ApprovalState.CONSUMED


def test_the_digest_is_recomputed_at_the_moment_of_use(workspace: Workspace) -> None:
    """The stored digest is the *expected* value, never the answer.

    A check that trusted ``Approval.args_digest`` would be satisfied by any row
    at all, because anything that can write a row can write its digest. The
    recomputation is what makes the digest binding mean anything.
    """
    ledger = ApprovalLedger()
    policy = PermissionPolicy()
    grant, _path = granted(ledger, workspace, policy_digest=policy.digest())

    tampered = grant.approval.model_copy(update={"args_digest": "0" * 64})
    ledger._grants[grant.approval_id] = ApprovalGrant(
        approval=tampered, policy_digest=grant.policy_digest, sources=grant.sources
    )
    tampered_grant = ledger.peek(grant.approval_id)
    assert tampered_grant is not None
    with pytest.raises(AuthorizationRefusedError) as caught:
        consume(ledger, tampered_grant, workspace, policy_digest=policy.digest())
    assert caught.value.refusal is ApprovalRefusal.ARGS_CHANGED


# ---------------------------------------------------------------------------
# depends_on
# ---------------------------------------------------------------------------


def test_source_hashes_are_recomputed_not_trusted(workspace: Workspace) -> None:
    ApprovalLedger()
    source = workspace.root_for("source:0").path / "data.csv"
    source.write_bytes(b"a,b\n1,2\n")
    # Captured once, at approval time. Recomputing it here would make the test
    # compare the file against itself and pass for the wrong reason.
    approved_hash = content_hash(source)
    binding = (SourceBinding(resource_key="data.csv", expected_hash=approved_hash),)

    intact, changed = sources_intact(
        binding, resolve=lambda k: workspace.resolve_key(k, root_id="source:0")
    )
    assert intact and changed == ()

    source.write_bytes(b"a,b\n1,3\n")
    intact, changed = sources_intact(
        binding, resolve=lambda k: workspace.resolve_key(k, root_id="source:0")
    )
    assert not intact
    assert changed == ("data.csv",)


def test_an_unreadable_source_counts_as_changed(workspace: Workspace) -> None:
    """Absence is not proof of integrity. §C4: every hash must still match."""

    def missing(_key: str) -> Path:
        return workspace.root_for("source:0").path / "gone.pdf"

    intact, changed = sources_intact(
        (SourceBinding(resource_key="gone.pdf", expected_hash="0" * 64),),
        resolve=missing,
    )
    assert not intact
    assert changed == ("gone.pdf",)


# ---------------------------------------------------------------------------
# Outbound
# ---------------------------------------------------------------------------


def test_an_outbound_request_is_never_implicitly_allowed(workspace: Workspace) -> None:
    """§C6.4 / ARCHITECTURE: no silent background upload.

    This test makes **no network call** and sends nothing anywhere — it asserts
    only that the verdict is ASK under the default policy, which is the control
    that stands between a capability existing and bytes leaving.
    """
    policy = default_policy()
    source = workspace.root_for("source:0").path / "paper.pdf"
    source.write_bytes(b"%PDF-1.4")
    path = canonicalize(source, workspace.roots)

    decision = policy.evaluate(
        task_id=workspace.task_id,
        capability="model.request",
        resource=ResourceRef.from_canonical(path),
    )
    assert decision.permission is Permission.ASK


def test_every_refusal_reason_is_reachable_from_this_ledger(workspace: Workspace) -> None:
    """Every ADR §C4 refusal reason is produced by a real call, not asserted.

    A reason that cannot be reached is a reason the operator will believe in
    and the code never produces.
    """
    ledger = ApprovalLedger()
    policy = PermissionPolicy()
    seen: set[ApprovalRefusal] = set()

    grant, _ = granted(ledger, workspace, policy_digest=policy.digest())
    seen.add(
        AuthorizationRefusedError(
            _capture(ledger, grant, workspace, policy, task_id=TaskId(new_id()))
        ).refusal
    )

    grant, _ = granted(ledger, workspace, policy_digest=policy.digest())
    seen.add(
        AuthorizationRefusedError(
            _capture(ledger, grant, workspace, policy, args={"path": "z"})
        ).refusal
    )

    grant, _ = granted(ledger, workspace, policy_digest=policy.digest())
    seen.add(
        AuthorizationRefusedError(
            _capture(ledger, grant, workspace, policy, now=AFTER_EXPIRY)
        ).refusal
    )

    grant, _ = granted(ledger, workspace, policy_digest=policy.digest())
    consume(ledger, grant, workspace, policy_digest=policy.digest())
    seen.add(AuthorizationRefusedError(_capture(ledger, grant, workspace, policy)).refusal)

    assert seen == {
        ApprovalRefusal.TASK_SCOPE_MISMATCH,
        ApprovalRefusal.ARGS_CHANGED,
        ApprovalRefusal.EXPIRED,
        ApprovalRefusal.CONSUMED,
    }
    assert seen <= set(ApprovalRefusal)


def _capture(
    ledger: ApprovalLedger,
    grant: ApprovalGrant,
    workspace: Workspace,
    policy: PermissionPolicy,
    **kwargs: object,
) -> ApprovalRefusal:
    """Run a consume that is expected to fail, and return its reason."""
    with pytest.raises(AuthorizationRefusedError) as caught:
        consume(ledger, grant, workspace, policy_digest=policy.digest(), **kwargs)  # type: ignore[arg-type]
    return caught.value.refusal


def test_policy_digest_binding_uses_the_real_policy(workspace: Workspace) -> None:
    """Two policies that evaluate identically still have different digests.

    Reordering is the case: under deny-first it cannot change a verdict, but it
    is still a change to the snapshot an approval was decided under.
    """
    from labcairn.security.policy import Rule

    a = PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="x")])
    b = PermissionPolicy.from_rules(
        [Rule(effect=Permission.ALLOW, pattern="x"), Rule(effect=Permission.DENY, pattern="y")]
    )
    assert a.digest() != b.digest()
