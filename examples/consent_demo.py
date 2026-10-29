"""The consent exit demonstration, for LC-P2-06.

**Run it:**

```bash
python examples/consent_demo.py
```

**What it shows.** The consent machinery doing the five things it exists for:

1. **a grant** for reading, and the use it permits;
2. **a request to transmit** that is refused, with the reason and the
   remedy — and **the approval left unspent**, because asking is not
   spending;
3. **a request to a destination the grant does not name**, refused with
   both destinations named;
4. **a withdrawal**, and a **derived copy that is stale because of it**;
5. **a material with no grant at all**, which is not opened.

**Every claim is carried by a `check()` that raises.** The exit code is the
assertion that matters: a zero exit means every one of them still holds, and
a non-zero exit names the one that stopped. A demonstration that only
printed would be prose.
"""

from __future__ import annotations

import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from labcairn.application.approvals import (
    ApprovalRequest,
    ApprovalUse,
    grant_approval,
    request_approval,
)
from labcairn.application.context import ApplicationContext
from labcairn.application.model_transmit import (
    check_transmit,
    transmit_request,
)
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.application.tasks import create_task
from labcairn.core.ids import ApprovalId
from labcairn.db.migrations import upgrade_to_head
from labcairn.db.repository import TaskStore, list_approvals
from labcairn.db.session import create_db_engine, create_session_factory
from labcairn.material.intake import IntakeRefusal, inspect_archive
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import CapabilityId
from labcairn.security.permissions import (
    DerivedCopy,
    Grant,
    is_copy_stale,
    may_use,
    stale_copies,
    withdraw_grant,
)
from labcairn.security.policy import Permission, PermissionPolicy, Rule

NOW = datetime(2026, 3, 2, 9, 15, tzinfo=UTC)


@contextmanager
def _an_approval() -> Iterator[tuple[ApplicationContext, ApprovalId]]:
    """A context with an approval asked for and granted, and **not yet spent**.

    **A temporary workspace and a temporary store**, so the demonstration
    leaves nothing behind: the directory goes when the block ends, and it
    was never in the repository.

    **The real machinery, not a stand-in.** The claim this demonstration
    makes is about an *operation approval*, and a claim about the
    approval ledger is witnessed by the approval ledger — a made-up
    approval would make the demonstration prove something about itself.
    """
    with tempfile.TemporaryDirectory(prefix="labcairn-consent-demo-") as root:
        base = Path(root)
        workspace_root = base / "workspace"
        (workspace_root / "materials").mkdir(parents=True)
        database = base / "demo.db"
        upgrade_to_head(database)
        engine = create_db_engine(database)
        store = TaskStore(create_session_factory(engine)())
        created = create_task(
            store=store,
            policy=PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")]),
            workspace_root=workspace_root,
            title="Consent demonstration",
            goal=TaskGoal(
                objective="Show that a refused request does not spend the approval.",
                success_criterion="The approval is still spendable after the refusal.",
            ),
            source_dirs=(workspace_root / "materials",),
        )
        context = ApplicationContext(
            workspace=created.workspace,
            store=store,
            policy=PermissionPolicy.from_rules([Rule(effect=Permission.ASK, pattern="**")]),
            ledger=ApprovalLedger(),
        )
        asked = request_approval(
            context,
            ApprovalRequest(
                use=ApprovalUse(
                    capability=CapabilityId.ANALYSIS_RUN,
                    arguments={
                        "operator_id": "mean",
                        "parameters": {},
                        "recipe": "figure.recipe.json",
                    },
                    root_id="source:0",
                    resource_key="one.csv",
                ),
                expires_at=NOW + timedelta(hours=1),
            ),
            now=NOW,
        )
        granted = grant_approval(context, asked.approval.approval_id, now=NOW)
        try:
            yield context, granted.approval.approval_id
        finally:
            # **The store is closed before the directory goes.** A SQLite
            # file that is still open cannot be deleted on Windows, and a
            # demonstration that leaves its temporary directory behind is
            # a demonstration that does not clean up after itself.
            store.session.close()
            engine.dispose()


def check(condition: bool, message: str) -> None:
    """Assert, by raising.

    **A demonstration that warns is a demonstration that fails quietly.**
    The exit code carries every claim, so each one has to stop the run when
    it stops holding.
    """
    if not condition:
        raise AssertionError(message)


def _read_grant() -> Grant:
    return Grant(
        grant_id="g-read",
        subject_ref="proj-1",
        permission="store_read",
        purpose="read",
        scope="proj-1/**",
        destination=None,
        granted_by="Dr. Chen",
        granted_at=NOW,
        expires_at=None,
        state="active",
        withdrawn_at=None,
        withdrawn_by=None,
        withdrawal_reason=None,
    )


def _transmit_grant() -> Grant:
    return Grant(
        grant_id="g-transmit",
        subject_ref="proj-1",
        permission="external_transmit",
        purpose="transmit",
        scope="proj-1/**",
        destination="api.minimax.cn",
        granted_by="Dr. Chen",
        granted_at=NOW,
        expires_at=None,
        state="active",
        withdrawn_at=None,
        withdrawn_by=None,
        withdrawal_reason=None,
    )


def main() -> int:
    print("LC-P2-06 exit demonstration: the consent machinery")
    print("=" * 64)

    # -- 1. a grant permits what it covers --------------------------------- #
    print("\n1. A grant, and a use it permits")
    decision = may_use(
        [_read_grant()],
        permission="store_read",
        purpose="read",
        subject_ref="proj-1",
        material_ref="proj-1/drafts/v1.docx",
        at=NOW,
    )
    print(f"   permitted: {decision.allowed}")
    print(f"   by grant:  {decision.grant_id}")
    print(f"   {decision.detail}")
    check(decision.allowed is True, "the read grant permits the read")
    check(decision.grant_id == "g-read", "the decision names the grant")

    # -- 2. a transmission with no grant ------------------------------------- #
    print("\n2. A request to transmit, with no transmit grant")
    check_result = check_transmit(
        [_read_grant()],
        subject_ref="proj-1",
        destination="api.minimax.cn",
        at=NOW,
    )
    print(f"   permitted: {check_result.permitted}")
    print(f"   reason:    {check_result.reason}")
    print(f"   {check_result.detail}")
    check(check_result.permitted is False, "the read grant does not permit a transmission")
    check(
        check_result.reason == "purpose_not_granted",
        "the refusal names the purpose that was not granted",
    )
    check("remedy" in check_result.detail, "the refusal names the remedy")

    # **And the same refusal through the path that spends the approval.**
    # A real approval is behind this one, so the sentence below is carried
    # by something: the path is asked, the path refuses, and the store is
    # read to say that the approval is untouched.
    with _an_approval() as (context, approval_id):
        try:
            transmit_request(
                context,
                approval_id,
                [_read_grant()],
                use=ApprovalUse(
                    capability=CapabilityId.ANALYSIS_RUN,
                    arguments={
                        "operator_id": "mean",
                        "parameters": {},
                        "recipe": "figure.recipe.json",
                    },
                    root_id="source:0",
                    resource_key="one.csv",
                ),
                subject_ref="proj-1",
                destination="api.minimax.cn",
                at=NOW,
            )
        except ApplicationRefusedError as error:
            print(f"   refused:    {error.reason.value}")
            print("   The operation approval was never consumed: asking is not spending.")
            check(
                error.reason is ApplicationRefusal.CONSENT_PURPOSE_NOT_GRANTED,
                "the path refuses for the reason the gate gave",
            )
            spent = [
                row
                for row in list_approvals(context.store.session, context.task_id)
                if row.state == "consumed"
            ]
            check(not spent, "the refusal did not spend the approval")
        else:
            check(False, "the path permitted a transmission with no transmit grant")

    # -- 3. a destination the grant does not name --------------------------- #
    print("\n3. A request to a destination the grant does not name")
    wrong_destination = check_transmit(
        [_transmit_grant()],
        subject_ref="proj-1",
        destination="api.openai.com",
        at=NOW,
    )
    print(f"   permitted: {wrong_destination.permitted}")
    print(f"   reason:    {wrong_destination.reason}")
    print(f"   {wrong_destination.detail}")
    check(wrong_destination.permitted is False, "the other destination is refused")
    check(
        wrong_destination.reason == "destination_not_granted",
        "the refusal names the destination",
    )
    check(
        "api.minimax.cn" in wrong_destination.detail
        and "api.openai.com" in wrong_destination.detail,
        "the refusal names both destinations",
    )

    # -- 4. the withdrawal and the propagation ------------------------------ #
    print("\n4. A withdrawal, and the copy it reaches")
    copy = DerivedCopy(
        copy_id="c-1",
        grant_id="g-transmit",
        kind="embedding",
        location="vectors/c-1",
        subject_ref="proj-1",
    )
    print(f"   before: the copy is stale? {is_copy_stale(copy, [_transmit_grant()])}")
    check(
        is_copy_stale(copy, [_transmit_grant()]) is False,
        "the copy is fresh while the grant stands",
    )

    withdrawn = withdraw_grant(
        _transmit_grant(),
        withdrawn_by="Prof. Lin",
        at=NOW,
        reason="the material left the lab",
    )
    stale = stale_copies([copy], [withdrawn])
    print(f"   after:  the copy is stale? {is_copy_stale(copy, [withdrawn])}")
    print(f"   stale copies: {[c.copy_id for c in stale]}")
    print(f"   withdrawn by {withdrawn.withdrawn_by!r} on {withdrawn.withdrawn_at.isoformat()}")
    check(is_copy_stale(copy, [withdrawn]) is True, "the copy is stale after the withdrawal")
    check(len(stale) == 1, "the withdrawal reaches the copy")
    check(withdrawn.withdrawn_by == "Prof. Lin", "the withdrawal names who")
    check(withdrawn.state == "withdrawn", "the state says withdrawn, not absent")

    # -- 5. a material with no grant ----------------------------------------- #
    print("\n5. A material with no grant at all")
    intake = inspect_archive(
        Path(__file__).resolve().parent / "does-not-matter.zip",
        grant_present=False,
    )
    print(f"   admitted:  {intake.admitted}")
    print(f"   refusal:  {intake.refusal.value if intake.refusal else None}")
    print(f"   {intake.detail}")
    check(intake.admitted is False, "material with no grant is not admitted")
    check(
        intake.refusal is IntakeRefusal.NO_GRANT,
        "the refusal is the missing grant",
    )
    check(intake.entries == (), "the archive was not opened, so nothing was listed")
    print("   It was not opened, not listed and not measured.")

    print("\n" + "=" * 64)
    print("All checks held.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
