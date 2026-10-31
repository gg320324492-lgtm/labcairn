"""The model-call path, end to end — with the fake provider, and nothing sent.

**What this demonstrates.** LC-P2-01's four outcomes, on one task that
holds real material and asks one declared model:

1. **Consented** — the material gate runs first, the approval pays only
   for a permitted request, and the answer comes back.
2. **Budgeted** — a ceiling that cannot be measured stops the call
   **before anything is spent**: no wire, no approval, no record.
3. **Recorded** — what the call left in the log: a prompt digest, the
   usage, the credential's fingerprint, the cost — and the answer's own
   text is not in the record, and no plaintext key has a field to live
   in.
4. **Refused** — a schema request the provider's probe never licensed,
   stopped before a socket exists: no approval spent, no wire touched.
   **This is the refusal that matters most**, because it is the one
   that has to happen before a socket exists.

**And throughout: nothing leaves the machine.** Every claim is a
``check()`` that raises; the demonstration's exit code is its verdict.
The provider is the repository's scripted fake — a real call needs the
owner's authorisation, a limit, and synthetic content that may be sent,
and this demonstration is not that.

This file is the acceptance demonstration of LC-P2-01; it is run by
``tests/test_model_request_demo.py`` on every suite, and a second run
of that test plants the first claim false **from outside this source**
so the exit code keeps meaning something.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from labcairn.application import ApplicationContext, create_task, ingest_material
from labcairn.application.approvals import (
    ApprovalRequest,
    ApprovalUse,
    grant_approval,
    request_approval,
)
from labcairn.application.events import read_events
from labcairn.application.model_request import ModelInvocation, request_model
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.core.ids import ApprovalId
from labcairn.core.providers import ModelRequest
from labcairn.core.providers.fake import FakeProvider, Transcript, TranscriptStep
from labcairn.core.providers.usage import Unknown, UnknownReason
from labcairn.core.schema import LabCairnModel
from labcairn.db.migrations import upgrade_to_head
from labcairn.db.repository import TaskStore, list_approvals
from labcairn.db.session import create_db_engine, create_session_factory
from labcairn.providers.budget import RunBudget
from labcairn.providers.errors import BudgetEnforcementUnavailableError
from labcairn.providers.ledger import LedgerSnapshot
from labcairn.runtime.event import EventType
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import CapabilityId, ModelRequestArgs
from labcairn.security.permissions import Grant
from labcairn.security.policy import Permission, PermissionPolicy, Rule

MOMENT = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)

#: The destination a permitted request sends to. An example domain, the
#: way every demonstration's destination is one.
DESTINATION = "api.model-provider.example"

MATERIAL_REF = "proj-1/manuscript.txt"

#: The sentence the demonstration's material carries.
SENTENCE = "The method estimates the parameter from a single observation."

STEPS = (
    "1. Consented — the material gate permits, and the approval pays",
    "2. Budgeted — a ceiling that cannot be measured stops the call",
    "3. Recorded — what the call left in the log, and what it did not",
    "4. Refused — an unprobed schema request, stopped before a socket exists",
)

#: The schema the refused request asks for. Nothing ever decodes into
#: it: the demonstration's fourth scene stops the request before the
#: wire, because the provider was never probed.


class DemoCard(LabCairnModel):
    """The structured answer the refused request would have asked for."""

    title: str
    verdict: str


def check(condition: bool, message: str = "") -> bool:
    """Every claim the demonstration makes. A false one stops the show."""
    if not condition:
        raise AssertionError(message or "the demonstration's claim does not hold")
    return True


def _plant(db_path: Path, workspace: Path) -> ApplicationContext:
    """The store, the material, and the task that holds it.

    **The material is real** — one small text file, ingested through the
    product's own intake — because the model-call path's gate asks about
    material the task holds, and a gate against a file that is not there
    would refuse everything.
    """
    upgrade_to_head(db_path)
    materials = workspace / "materials"
    materials.mkdir(parents=True)
    (materials / "manuscript.txt").write_text(
        f"Introduction.\n{SENTENCE}\nResults follow in the next section.\n",
        encoding="utf-8",
    )
    policy = PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])
    engine = create_db_engine(db_path)
    factory = create_session_factory(engine)
    session = factory()
    created = create_task(
        store=TaskStore(session),
        policy=policy,
        workspace_root=workspace,
        title="The model-call path's demonstration",
        goal=TaskGoal(
            objective="Ask a declared model under the two gates.",
            success_criterion=(
                "An answer the consent layer permitted, and refusals that cost nothing."
            ),
        ),
        source_dirs=(materials,),
        now=MOMENT,
    )
    context = ApplicationContext(
        workspace=created.workspace,
        store=TaskStore(session),
        policy=policy,
        ledger=ApprovalLedger(),
    )
    ingest_material(context, now=MOMENT)
    return context


def _model_use() -> ApprovalUse:
    """What a model call is spent on — the capability whose payload leaves."""
    return ApprovalUse(
        capability=CapabilityId.MODEL_REQUEST,
        arguments=ModelRequestArgs(
            provider="fake",
            model="scripted",
            path=MATERIAL_REF,
            excerpts=(),
            purpose="guidance_review",
        ).model_dump(),
        root_id="source:0",
        resource_key=MATERIAL_REF,
    )


def _grants() -> list[Grant]:
    """The material-purpose grant the request is judged against."""
    return [
        Grant(
            grant_id="g-model-demo",
            subject_ref="proj-1",
            permission="external_transmit",
            purpose="transmit",
            scope="proj-1/**",
            destination=DESTINATION,
            granted_by="Dr. Chen",
            granted_at=MOMENT,
            expires_at=None,
            state="active",
            withdrawn_at=None,
            withdrawn_by=None,
            withdrawal_reason=None,
        )
    ]


def _an_approval(context: ApplicationContext) -> ApprovalId:
    """One approval, asked for and granted, not yet spent."""
    asked = request_approval(
        context,
        ApprovalRequest(use=_model_use(), expires_at=MOMENT.replace(year=2027)),
    )
    grant_approval(context, asked.approval.approval_id, now=MOMENT)
    return asked.approval.approval_id


def _send() -> ModelInvocation:
    """The invocation: the fake provider runs its script, nothing leaves.

    The exchange record is the wire form the provider layer persists —
    a prompt digest, the outbound disclosure, the usage — because that
    is the shape the path records by construction.
    """
    request = ModelRequest(prompt=f"What does the manuscript say? {SENTENCE}")
    transcript = Transcript.of(
        "model-request-demo",
        (TranscriptStep.of("the-answer", request, {"text": "It estimates the parameter."}),),
    )
    responses = FakeProvider(transcript, clock=lambda: MOMENT).run()
    answer = responses[0]
    return ModelInvocation(
        answer=answer.text,
        provider="fake",
        model="scripted",
        exchanges=(
            {
                "provider": "fake",
                "model": "scripted",
                "transcript_step": "the-answer",
                "prompt_digest": hashlib.sha256(request.prompt.encode("utf-8")).hexdigest(),
                "tool_names": [],
                "outbound": {"destination": DESTINATION, "digest": "b" * 64},
                "provider_attempts": 1,
                "observed_at": MOMENT.isoformat(),
                "usage_input": answer.usage.input_tokens.to_wire(),
                "usage_output": answer.usage.output_tokens.to_wire(),
            },
        ),
        credential_fingerprint="fp-" + "c" * 16,
        cost_micros=1200,
    )


def _unspent(context: ApplicationContext, approval_id: ApprovalId) -> bool:
    """Whether the approval named is still unspent, as the store holds it."""
    rows = list_approvals(context.store.session, context.task_id)
    return all(row.approval_id != approval_id or row.state != "consumed" for row in rows)


def main() -> int:
    """Run the four scenes; every claim is a check that raises."""
    workspace = Path(tempfile.mkdtemp(prefix="model-request-demo-"))
    try:
        db_path = workspace / "labcairn.db"

        _print(STEPS[0])
        context = _plant(db_path, workspace)
        answer = request_model(
            context,
            _an_approval(context),
            _grants(),
            use=_model_use(),
            subject_ref="proj-1",
            destination=DESTINATION,
            material_ref=MATERIAL_REF,
            at=MOMENT,
            send=_send,
        )
        check(answer.answer == "It estimates the parameter.", "the answer is the script's")
        check(answer.destination == DESTINATION, "the answer names where it was permitted to go")
        check(
            any(
                row.state == "consumed"
                for row in list_approvals(context.store.session, context.task_id)
            ),
            "the approval paid for the permitted call",
        )
        print(f"  the answer: {answer.answer}")

        _print(STEPS[1])
        budgeted_id = _an_approval(context)
        try:
            request_model(
                context,
                budgeted_id,
                _grants(),
                use=_model_use(),
                subject_ref="proj-1",
                destination=DESTINATION,
                material_ref=MATERIAL_REF,
                at=MOMENT,
                send=_send,
                budget=RunBudget(max_cost_usd=Decimal("5.00")),
                ledger=LedgerSnapshot(cost_micros=Unknown(reason=UnknownReason.UNPRICED)),
            )
        except BudgetEnforcementUnavailableError:
            check(True)
        else:
            check(False, "an unpriced model under a cost ceiling went through")
        check(_unspent(context, budgeted_id), "the budget's refusal cost the person nothing")
        print("  the ceiling held, and nothing was spent")

        _print(STEPS[2])
        page = read_events(context)
        exchanges = [event for event in page.events if event.type is EventType.MODEL_EXCHANGED]
        check(len(exchanges) == 1, "one permitted call, one exchange record")
        payload = json.loads(json.dumps(exchanges[0].payload))
        exchange = payload["exchanges"][0]
        prompt = f"What does the manuscript say? {SENTENCE}"
        check(
            exchange["prompt_digest"] == hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "what was sent is a digest",
        )
        check(
            payload["credential_fingerprint"] == "fp-" + "c" * 16,
            "the credential is named by its fingerprint",
        )
        check(payload["cost_micros"] == 1200, "the cost is recorded")
        rendered = repr(payload)
        check("sk-" not in rendered, "no plaintext key-shaped string is in the record")
        check(answer.answer not in rendered, "the answer's own text is not the record")
        print("  the record carries digests and counts, and never the words")

        _print(STEPS[3])
        refused_id = _an_approval(context)
        try:
            request_model(
                context,
                refused_id,
                _grants(),
                use=_model_use(),
                subject_ref="proj-1",
                destination=DESTINATION,
                material_ref=MATERIAL_REF,
                at=MOMENT,
                send=_send,
                output_schema=DemoCard,
            )
        except ApplicationRefusedError as refused:
            check(
                refused.reason is ApplicationRefusal.MODEL_SCHEMA_UNPROBED,
                "the refusal names the unprobed provider",
            )
        else:
            check(False, "an unprobed provider was asked to try")
        check(_unspent(context, refused_id), "the refusal left the approval unspent")
        page = read_events(context)
        check(
            len([event for event in page.events if event.type is EventType.MODEL_EXCHANGED]) == 1,
            "no exchange was recorded, because no request was made",
        )
        print("  the request was refused before a socket existed")

        print()
        print("The demonstration holds:")
        print("  consented, budgeted, recorded — and refused before a socket exists.")
        print("  Nothing left the machine: the provider is the repository's fake.")
        return 0
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def _print(step: str) -> None:
    print(step)


if __name__ == "__main__":
    raise SystemExit(main())
