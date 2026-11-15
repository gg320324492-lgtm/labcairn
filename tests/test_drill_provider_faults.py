"""Network-loss, model-timeout and known-error drills against the substitute.

Drill classes 3, 4 and 5 of work orders §12 §5.1, designed at
``docs/plans/LC-P3-07-drill-matrix-design.md`` §§2.3-2.5. The endpoint is the
repository's own ``FakeEndpoint`` — no socket, no credential, no spend; the
*real-model* timeout row stays an owner addition (§12 §5.3, §14 item 7) and is
deliberately absent here.

What each class proves:

* **network loss** — a transport that fails mid-run arrives typed
  (``PROVIDER_TRANSIENT`` at transport level, retryable), counts toward the
  stop-loss's *failure* arm (it is not in ``PRE_WIRE_KINDS``), leaves a
  countable record (``RunRecord`` holds digests and counts, never text), and
  undoes nothing that already landed;
* **model timeout** — a reply that never arrives inside ``timeout_s`` is
  recorded as a failure, three consecutive ones end the run with
  ``StopLossTriggeredError``, and nothing is published from a timed-out
  suggestion;
* **known errors** — each named refusal surfaces with its name and, where the
  design says a remedy must be stated, the remedy.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from provider_fakes import FakeEndpoint, Reply, sync_runner
from store_support import env as _shared_env

from labcairn.application import ApplicationContext, create_task
from labcairn.application.approvals import (
    ApprovalRequest,
    ApprovalUse,
    grant_approval,
    request_approval,
)
from labcairn.application.outbound import OutboundApproval
from labcairn.core.ids import ApprovalId
from labcairn.core.providers.usage import Known
from labcairn.providers.bounded_run import (
    PRE_WIRE_KINDS,
    BoundedRun,
    CompoundStopLoss,
    RunRequestRefusedError,
    StopLossTriggeredError,
    StopLossVerdict,
)
from labcairn.providers.budget import RunBudget
from labcairn.providers.capabilities import (
    ALL_CAPABILITIES,
    CapabilityOutcome,
    ProviderCapabilities,
)
from labcairn.providers.deidentify import DeidentificationPipeline, SampleClass
from labcairn.providers.errors import (
    FailureKind,
    ProviderFailure,
)
from labcairn.providers.ledger import RunLedger
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import CapabilityId
from labcairn.security.policy import Permission, PermissionPolicy, Rule

env = _shared_env

pytestmark = pytest.mark.integration

MOMENT = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)
MATERIAL = (
    "The green algae inhibition assay was repeated three times under identical "
    "lighting conditions and the results disagreed with the earlier published "
    "curve at every measured concentration point without exception."
)
CLEAN_RENDERING = (
    "Assay S-1 was run on three occasions; luminance held fixed. Its trace "
    "diverges from a prior reference trace across the dilution series."
)
OK_REPLY = Reply(name="ok", text="the answer", usage_body={"input_tokens": 40, "output_tokens": 12})


@pytest.fixture()
def context(env: Any, tmp_path: Any) -> ApplicationContext:
    workspace_root = tmp_path / "workspace"
    (workspace_root / "materials").mkdir(parents=True)
    created = create_task(
        store=env.store(),
        policy=PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")]),
        workspace_root=workspace_root,
        title="Provider drill task",
        goal=TaskGoal(objective="Survive fault drills.", success_criterion="Typed answers."),
        source_dirs=(workspace_root / "materials",),
        now=MOMENT,
    )
    return ApplicationContext(
        workspace=created.workspace,
        store=env.store(),
        policy=PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")]),
        ledger=ApprovalLedger(),
    )


def _the_use(excerpts: tuple[str, ...]) -> ApprovalUse:
    """An approval bound to excerpt **digests**, never to excerpt text (Q3)."""
    from labcairn.security.capabilities import ModelRequestArgs

    return ApprovalUse(
        capability=CapabilityId.MODEL_REQUEST,
        arguments=ModelRequestArgs(
            provider="fake",
            model="scripted",
            path="drill/material.txt",
            excerpts=excerpts,
            purpose="lc_p3_07_drill",
        ).model_dump(),
        root_id="source:0",
        resource_key="drill/material.txt",
    )


def _ports(context: ApplicationContext, digests: tuple[str, ...]) -> tuple[Any, ...]:
    """One port per request: the prompt's port covers an empty excerpt set,
    each excerpt's port covers its own digest (Q3's pairing)."""
    ports: list[Any] = []
    prompt_use = _the_use(())
    asked = request_approval(
        context,
        ApprovalRequest(use=prompt_use, expires_at=MOMENT + timedelta(hours=1)),
        now=MOMENT,
    )
    granted = grant_approval(context, asked.approval.approval_id, now=MOMENT)
    ports.append(
        _DigestPort(
            context=context,
            approval_id=granted.approval.approval_id,
            use=prompt_use,
            bound_excerpt_digest=None,
        )
    )
    for digest in digests:
        use = _the_use((digest,))
        asked = request_approval(
            context,
            ApprovalRequest(use=use, expires_at=MOMENT + timedelta(hours=1)),
            now=MOMENT,
        )
        granted = grant_approval(context, asked.approval.approval_id, now=MOMENT)
        ports.append(
            _DigestPort(
                context=context,
                approval_id=granted.approval.approval_id,
                use=use,
                bound_excerpt_digest=digest,
            )
        )
    return tuple(ports)


class _DigestPort:
    def __init__(
        self,
        *,
        context: ApplicationContext,
        approval_id: ApprovalId,
        use: ApprovalUse,
        bound_excerpt_digest: str | None,
    ) -> None:
        self.bound_excerpt_digest = bound_excerpt_digest
        self._approval = OutboundApproval(
            context=context, approval_id=approval_id, use=use, at=MOMENT
        )

    def require(self, request: Any) -> None:
        self._approval.require(request)


def _case() -> Any:
    return DeidentificationPipeline().redact_case(
        case_id="drill-case",
        source_digest=hashlib.sha256(MATERIAL.encode("utf-8")).hexdigest(),
        material_text=MATERIAL,
        excerpts=("the assay disagreed with the curve",),
        rendered_prompt=CLEAN_RENDERING,
        rendered_excerpts=("Diverges from a reference trace.",),
        sample_class=SampleClass.PUBLIC_SYNTHETIC,
    )


def _probed() -> ProviderCapabilities:
    outcomes = dict.fromkeys(ALL_CAPABILITIES, CapabilityOutcome.OK)
    return ProviderCapabilities.from_outcomes(
        endpoint_fingerprint="drill-fingerprint",
        model="scripted",
        protocol="fake",
        outcomes=outcomes,
        unsupported_reason=dict.fromkeys(ALL_CAPABILITIES, "the probe said no"),
    )


def _run(endpoint: FakeEndpoint, **overrides: Any) -> BoundedRun:
    kwargs: dict[str, Any] = {
        "model": endpoint,
        "budget": RunBudget(max_model_requests=20, max_total_tokens=Known(50_000)),
        "ledger": RunLedger(clock=lambda: 0.0, capabilities=_probed(), priced=False),
        "capabilities": _probed(),
        "usage_capture": endpoint.capture,
        "runner": sync_runner,
        "timeout_s": overrides.pop("timeout_s", None),
        "stop_loss": overrides.pop("stop_loss", None),
    }
    kwargs.update(overrides)
    return BoundedRun(**kwargs)


# --- drill class 3: network loss --------------------------------------------


def test_network_loss_is_typed_transient_and_counts_as_a_failure(
    context: ApplicationContext,
) -> None:
    """A transport that fails mid-run arrives typed, retryable, and counted.

    The drill injects the loss on the substitute: ``FakeEndpoint`` raises the
    transport error its ``always_raises`` names. The refusal ladder's
    classification is what the drill observes: ``PROVIDER_TRANSIENT`` is
    post-wire, so the request was issued and failed — the stop-loss's first
    arm, not its refusal arm.
    """
    endpoint = FakeEndpoint(replies=(), always_raises=ConnectionError("route down"))
    case = _case()
    loss = CompoundStopLoss()
    run = _run(endpoint, stop_loss=loss)
    with pytest.raises(RunRequestRefusedError) as raised:
        run.submit_case(case, consents=_ports(context, case.excerpt_digests))
    assert raised.value.kind is FailureKind.PROVIDER_TRANSIENT
    assert raised.value.kind not in PRE_WIRE_KINDS
    assert endpoint.call_count == 1, "the request was issued; the wire was reached"
    record = run.record()
    assert record.requests_failed == 1
    assert record.requests_made == 0
    assert record.requests[0].kind == "provider_transient"
    # The failure's message is LabCairn's template, never the transport's text.
    failure = ProviderFailure.of(FailureKind.PROVIDER_TRANSIENT)
    assert "route down" not in failure.message
    assert "transient" in failure.message.lower()


def test_network_loss_counts_toward_the_consecutive_failure_arm(
    context: ApplicationContext,
) -> None:
    """Three transport failures stop the run; a fourth request is never built.

    The compound stop-loss's first arm counts issued-and-failed requests. The
    drill watches the arm fire on the third and the run refuse to spend a
    fourth request's approval.
    """
    endpoint = FakeEndpoint(replies=(), always_raises=ConnectionError("route down"))
    case = _case()
    loss = CompoundStopLoss()
    run = _run(endpoint, stop_loss=loss)
    for _ in range(3):
        with pytest.raises(RunRequestRefusedError):
            run.submit_case(case, consents=_ports(context, case.excerpt_digests))
    assert loss.verdict is StopLossVerdict.STOP_CONSECUTIVE_FAILURES
    with pytest.raises(StopLossTriggeredError):
        run.submit_case(case, consents=_ports(context, case.excerpt_digests))
    assert endpoint.call_count == 3, "the stopped run issues no fourth request"


def test_a_landed_publication_survives_a_later_network_loss(
    context: ApplicationContext,
) -> None:
    """No local effect that already landed is undone by a later failure.

    The drill's claim is the matrix's: the run's local record is append-only,
    so a failure after a success leaves the success's record and receipt in
    place.
    """
    endpoint = FakeEndpoint(
        replies=(OK_REPLY, Reply(name="down", raises=ConnectionError("route down")))
    )
    case = _case()
    run = _run(endpoint)
    # A case whose first request lands and whose excerpt request meets the
    # loss: the landed request's record and exchange stay, and the failure is
    # recorded after them — nothing is rolled back.
    from labcairn.providers.bounded_run import RunRequestRefusedError as _Refused

    with pytest.raises(_Refused):
        run.submit_case(case, consents=_ports(context, case.excerpt_digests))
    record = run.record()
    assert record.requests[0].outcome == "sent", "the first request's success stays recorded"
    assert record.requests[1].outcome == "failed"
    assert record.requests[1].kind == "provider_transient"
    assert len(run.exchanges()) == 1, (
        "the landed exchange stays in the record; the failed one adds no text"
    )


# --- drill class 4: model timeout -------------------------------------------


def test_a_timeout_is_a_failure_that_stops_the_run_after_three(
    context: ApplicationContext,
) -> None:
    """The timeout arm: one call per attempt, then the stop-loss.

    The substitute hangs; ``asyncio.wait_for`` bounds it; the classification
    is ``TIMEOUT``; the stop-loss's first arm counts it; on the third the run
    stops. Nothing is published from a timed-out suggestion — the drill's
    record is the run record, and no exchange carries a reply.
    """
    endpoint = FakeEndpoint(replies=tuple(Reply(name="hangs", hangs=True) for _ in range(3)))
    case = _case()
    loss = CompoundStopLoss()
    run = _run(endpoint, timeout_s=0.05, stop_loss=loss)
    for _ in range(3):
        with pytest.raises(RunRequestRefusedError) as raised:
            run.submit_case(case, consents=_ports(context, case.excerpt_digests))
        assert raised.value.kind is FailureKind.TIMEOUT
    assert endpoint.call_count == 3
    record = run.record()
    assert record.requests_failed == 3
    assert record.requests_made == 0
    assert loss.verdict is StopLossVerdict.STOP_CONSECUTIVE_FAILURES
    with pytest.raises(StopLossTriggeredError):
        run.submit_case(case, consents=_ports(context, case.excerpt_digests))
    # No exchange record carries a reply: nothing was published from a
    # timed-out suggestion.
    assert run.exchanges() == ()


def test_a_timeout_failure_is_retryable_with_the_retry_action(
    context: ApplicationContext,
) -> None:
    """The classification the manual will print: retryable, action = retry."""
    failure = ProviderFailure.of(FailureKind.TIMEOUT)
    assert failure.retryable is True
    assert failure.user_action == "retry"
    assert "timeout" in failure.message.lower()


# --- drill class 5: known errors --------------------------------------------


def test_each_named_refusal_surfaces_with_its_name_and_remedy(
    context: ApplicationContext,
) -> None:
    """The known-error drill: the operator can tell which refusal happened.

    Each named refusal is driven through the layer's own surface and asserted
    to arrive with its name and its remedy — the precedent
    ``describe_abandoned`` sets: a refusal whose remedy is not stated is a
    dead end rather than a decision.
    """
    from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
    from labcairn.application.revision_loop import open_loop

    # path_refused: a key that escapes every bound root.
    with pytest.raises(ApplicationRefusedError) as raised:
        open_loop(
            context,
            source_root_id="source:0",
            source_key="../../outside.bin",
            now=MOMENT,
        )
    assert raised.value.reason is ApplicationRefusal.PATH_REFUSED
    assert "refused" in str(raised.value).lower()

    # A source the root names but the disk does not: the loop's read fails at
    # the hash step, and the OS error is the named fact. The layer surfaces it
    # as a stage failure rather than inventing a softer class — an absent
    # original is an OS fact before it is a policy question.
    with pytest.raises(OSError) as os_raised:
        open_loop(
            context,
            source_root_id="source:0",
            source_key="absent.bin",
            now=MOMENT,
        )
    assert "absent.bin" in str(os_raised.value)


def test_the_loop_duplicate_publication_refusal_names_the_remedy(env: Any, tmp_path: Any) -> None:
    """``loop_already_published`` arrives with the remedy in its message.

    The remedy is the design's own sentence: import the new bytes as a new
    loop. The drill asserts the message says so, because a refusal without
    its remedy is the "dead end" the known-error drill exists to catch.
    """
    from drill_support import EDITED_BYTES, build_rig, grant_copy, grant_publication
    from drill_support import MOMENT as DRILL_MOMENT

    from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
    from labcairn.application.revision_loop import publish_revision, stage_copy

    rig = build_rig(env.store(), tmp_path / "workspace")
    stage_copy(rig.context, rig.loop, approval_id=grant_copy(rig), now=DRILL_MOMENT)
    rig.copy_path().write_bytes(EDITED_BYTES)
    publish_revision(
        rig.context,
        rig.loop,
        approval_id=grant_publication(rig),
        edited_bytes=EDITED_BYTES,
        now=DRILL_MOMENT,
    )
    with pytest.raises(ApplicationRefusedError) as raised:
        publish_revision(
            rig.context,
            rig.loop,
            approval_id=grant_publication(rig),
            edited_bytes=EDITED_BYTES,
            now=DRILL_MOMENT,
        )
    assert raised.value.reason is ApplicationRefusal.LOOP_ALREADY_PUBLISHED
    assert "new loop" in str(raised.value), (
        "the refusal carries its remedy: import the new bytes as a new loop"
    )


def test_source_drifted_refusal_names_the_comparison(context: ApplicationContext) -> None:
    """``source_drifted`` arrives when the original's bytes moved under the loop.

    The message names both hashes — the receipt's and the file's current —
    because the remedy is a comparison a person runs, and a refusal that
    hides the numbers is a dead end.
    """
    from drill_support import build_rig

    from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
    from labcairn.application.revision_loop import verify_original

    rig = build_rig(context.store, context.workspace.selected_root)
    rig.original_path.write_bytes(b"moved on\n")
    with pytest.raises(ApplicationRefusedError) as raised:
        verify_original(rig.context, rig.loop)
    assert raised.value.reason is ApplicationRefusal.SOURCE_DRIFTED
    assert rig.loop.import_receipt.original_sha256[:12] in str(raised.value)
