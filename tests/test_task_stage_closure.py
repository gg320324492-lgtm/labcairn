"""The two places the product's bookkeeping stopped, closed.

**What is under test.** The pilot's first whole round measured two gaps in
the product's own bookkeeping (``docs/acceptance/
LC-P4-PILOT-first-round-2026-11-26.md`` §6):

1. **A refusal left no event.** ``roles run`` refused with exit code 3 and
   the message ``role_comment_not_in_the_chain``, and the task's event log
   held no entry for it. An exit code and a stderr line live and die with
   the process; the log the next morning could not say that anything was
   asked for.
2. **A stage stayed blocked after its approval was consumed.** The chain
   for one real model request was complete and in the right order and then
   stopped: no ``stage_completed``, no ``run_finished``. The stage still
   read ``blocked`` and the run still read ``running`` although the
   approval was spent and the request answered.

====================================================  =========================
     a refusal is a fact the log holds                 the refusal event names
                                                          the reason, the
                                                          message and the ask
     an answered request closes what asked for it      the operation is
                                                          confirmed, the stage
                                                          completed, the run
                                                          finished, in that
                                                          order in the log
======================================================================

**The witnesses fail for the property, not for something else.** Each was
checked against a mutation of the code it watches: removing the refusal
record turns the first red, and removing the closure turns the second red.

**The material is a fixture, not the pilot's.** The chain is built the way
the chain tests build one; nothing under ``E:/labcairn-local/`` is read.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
from feedback_chain_fixtures import ChainEnv, a_comment, build_chain
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.application.approvals import grant_approval
from labcairn.application.context import ApplicationContext
from labcairn.application.events import read_events
from labcairn.application.model_request import ModelInvocation
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.application.roles_run import (
    ModelCallPlan,
    RoleRunRequest,
    request_role_run,
    run_role_run,
    run_role_run_service,
)
from labcairn.db.repository import list_approvals, list_operations, list_runs, list_stages
from labcairn.papers.feedback import record_feedback, set_issue_key
from labcairn.providers.capabilities import (
    ALL_CAPABILITIES,
    Capability,
    CapabilityOutcome,
    ProviderCapabilities,
)
from labcairn.roles.spec import FORBIDDEN_ACTIONS, define_role_spec
from labcairn.runtime.event import EventType
from labcairn.runtime.lifecycle import RunStatus, StageStatus
from labcairn.runtime.operation import OperationState
from labcairn.security.capabilities import CapabilityId
from labcairn.security.permissions import Grant

pytestmark = pytest.mark.integration

# pytest resolves a fixture by the parameter name in a test's signature, so the
# shared `env` fixture must be bound under that name here. Importing it directly
# and taking `env` as a parameter makes every signature below an F811
# redefinition; aliasing the import and rebinding it reads as a plain assignment.
env = _shared_env

#: The one moment these tests write. **No wall clock**, for the project's
#: reason: an ordering assertion over two wall-clock reads is flaky.
MOMENT = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)

EXPIRES = MOMENT.replace(year=2027)

KEY = "iss-closure-r1"
COMMENT = "Define the parameter."
QUOTE = "Define the parameter"
DESTINATION = "api.model-provider.example"

#: The workspace-relative path of the comment's material, as the chain holds
#: it, and the root it landed in.
MATERIAL_PATH = "materials/manuscript.docx"
MATERIAL_KEY = "manuscript.docx"
MATERIAL_ROOT = "source:0"

#: A key the chain does not hold, which is the pilot's own refusal.
MISSING_KEY = "iss-not-in-the-chain"

OBJECTIVE = "Align the advisor's comments with the edits actually made."


@dataclass(frozen=True)
class Chain:
    """The chain and the contract the one role works under."""

    context: ApplicationContext
    chain: ChainEnv


@pytest.fixture()
def chain(env: StoreEnv, tmp_path: Path) -> Chain:
    """A keyed comment, and a trajectory contract to route a request to it.

    **Only what the two witnesses need.** The request is refused before the
    chain is read when its key is not there, and the run needs one comment
    with a key. No rule, no edit and no response are planted: neither
    property is about them, and a fixture that planted them would hide that.
    """
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    store = env.store()
    built = build_chain(store, workspace_root, comments=(a_comment("201"),))
    (event,) = record_feedback(
        built.context,
        project_id=built.project_id,
        version_id=built.version_id,
        now=MOMENT,
    )
    set_issue_key(built.context, feedback_id=event.feedback_id, issue_key=KEY, now=MOMENT)
    define_role_spec(
        built.context,
        role_id="trajectory",
        role_version=1,
        objective=OBJECTIVE,
        input_schema="Input",
        output_schema="Output",
        allowed_capabilities=(CapabilityId.MODEL_REQUEST,),
        forbidden_actions=FORBIDDEN_ACTIONS,
        allowed_data_purposes=("guidance_review",),
        provider_routing_policy="single-provider-per-call",
        cost_budget=None,
        token_budget=4000,
        timeout_seconds=120,
        retry_policy="no-retry",
        fallback_policy="abstain",
        abstain_conditions=("material_under_two_comments",),
        escalation_conditions=("a_conflict_between_two_rules",),
        prompt_template_version="trajectory-candidate-v1",
        model_config_ref="configs/model.json",
        now=MOMENT,
    )
    return Chain(context=built.context, chain=built)


def _request(chain: Chain, *, issue_key: str = KEY) -> RoleRunRequest:
    """A trajectory request on the chain the fixture planted."""
    return RoleRunRequest(
        roles=("trajectory",),
        project_id=chain.chain.project_id,
        issue_key=issue_key,
        version_ids=(chain.chain.version_id, chain.chain.second_version_id),
    )


def _plan() -> ModelCallPlan:
    """What the model call declares, as the chain's own address."""
    return ModelCallPlan(
        provider="fake",
        model="scripted",
        root_id=MATERIAL_ROOT,
        resource_key=MATERIAL_KEY,
        material_ref=MATERIAL_PATH,
        purpose="guidance_review",
        destination=DESTINATION,
        subject_ref="proj-1",
    )


def _grants() -> list[Grant]:
    """The material-purpose grant the request is judged against."""
    return [
        Grant(
            grant_id="g-closure-1",
            subject_ref="proj-1",
            permission="external_transmit",
            purpose="transmit",
            scope="materials/**",
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


def _probed(*capable: Capability) -> ProviderCapabilities:
    """A probe record that licenses exactly the capabilities named."""
    outcomes = {
        capability: (
            CapabilityOutcome.OK if capability in capable else CapabilityOutcome.UNSUPPORTED
        )
        for capability in ALL_CAPABILITIES
    }
    return ProviderCapabilities.from_outcomes(
        endpoint_fingerprint="fp-" + "p" * 16,
        model="scripted",
        protocol="openai-chat",
        outcomes=outcomes,
        unsupported_reason=dict.fromkeys(
            ALL_CAPABILITIES, "the probe asked and it did not do the thing"
        ),
    )


def _invocation(structured: Mapping[str, object] | None) -> ModelInvocation:
    """One call's record, in the provider layer's wire form."""
    return ModelInvocation(
        answer="the model's answer",
        provider="fake",
        model="scripted",
        exchanges=(
            {
                "provider": "fake",
                "model": "scripted",
                "transcript_step": "the-judgements",
                "prompt_digest": "a" * 64,
                "tool_names": [],
                "outbound": {"destination": DESTINATION, "digest": "b" * 64},
                "provider_attempts": 1,
                "observed_at": MOMENT.isoformat(),
                "usage_input": {"kind": "known", "tokens": 120},
                "usage_output": {"kind": "known", "tokens": 40},
            },
        ),
        credential_fingerprint="fp-" + "c" * 16,
        cost_micros=1200,
        structured=structured,
    )


def _trajectory_answer() -> dict[str, object]:
    """The document the trajectory role's judgement takes."""
    return {
        "issue_type": "method_and_hypothesis",
        "alignment": "partial",
        "advisor_quote": QUOTE,
        "note": "the change answered the wording, not the missing quantity.",
    }


# --------------------------------------------------------------------------- #
# (a) a refusal is a fact the task's own log holds
# --------------------------------------------------------------------------- #


def test_a_refused_request_leaves_a_refusal_event(chain: Chain) -> None:
    """The pilot's refusal, recorded rather than only reported.

    ``request_role_run`` is refused because the chain holds no comment under
    the key — the pilot's ``role_comment_not_in_the_chain`` — and the task's
    event log has to carry the refusal: its reason, its message, and the
    ask.

    **The state assertion is a fact, not an absence of an error.** The event
    must be there, it must be the last thing the log holds, and it must
    carry the three fields a reader needs. A log that simply did not raise
    would satisfy "no error" and fail every assertion below.

    Red by: removing the record from ``request_role_run``'s refusal path,
    which leaves the log with no new event at all.
    """
    before = read_events(chain.context).events

    with pytest.raises(ApplicationRefusedError) as raised:
        request_role_run(
            chain.context,
            _request(chain, issue_key=MISSING_KEY),
            plan=_plan(),
            expires_at=EXPIRES,
            now=MOMENT,
        )

    assert raised.value.reason is ApplicationRefusal.ROLE_COMMENT_NOT_IN_THE_CHAIN
    page = read_events(chain.context)
    new = page.events[len(before) :]
    assert [event.type for event in new] == [EventType.REFUSAL_RECORDED], (
        "the refusal wrote no event, or wrote something beside it"
    )

    refusal = new[0]
    assert refusal.run_id is None, "a refusal happens to the task, not inside an attempt"
    assert refusal.stage_id is None, "a refused request entered no stage"
    assert refusal.operation_id is None, "a refused request planned no operation"
    assert refusal.transition is None, "a refused request changed no state"
    assert refusal.payload["reason"] == ApplicationRefusal.ROLE_COMMENT_NOT_IN_THE_CHAIN.value
    assert MISSING_KEY in str(refusal.payload["message"]), (
        "the event's message does not name the key the refusal was about"
    )
    asked_for = refusal.payload["asked_for"]
    assert isinstance(asked_for, Mapping), "the ask was not recorded as a mapping"
    assert asked_for["operation"] == "roles run: request"
    assert asked_for["roles"] == "trajectory"
    assert asked_for["issue_key"] == MISSING_KEY
    assert asked_for["project"] == chain.chain.project_id


def test_a_refused_spend_leaves_a_refusal_event(chain: Chain) -> None:
    """A refusal on the spend path is recorded too, with the approval it named.

    The same rule as the ask's: the run is refused because no provider
    invocation was wired, and the task's log carries the refusal, its
    message, and the ask — which on this path is the ticket's approval and
    the roles its contracts name.

    Red by: removing the record from ``run_role_run``'s refusal path.
    """
    ticket = request_role_run(
        chain.context,
        _request(chain),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    assert ticket.approval_id is not None
    before = read_events(chain.context).events

    with pytest.raises(ApplicationRefusedError) as raised:
        run_role_run(chain.context, ticket, grants=_grants(), at=MOMENT, send=None)

    assert raised.value.reason is ApplicationRefusal.ROLE_RUN_NO_PROVIDER_INVOCATION
    new = read_events(chain.context).events[len(before) :]
    assert [event.type for event in new] == [EventType.REFUSAL_RECORDED], (
        "the refused spend wrote no event, or wrote something beside it"
    )
    refusal = new[0]
    assert refusal.run_id is None, "the refusal is a fact about the task, not an attempt"
    assert refusal.payload["reason"] == ApplicationRefusal.ROLE_RUN_NO_PROVIDER_INVOCATION.value
    asked_for = refusal.payload["asked_for"]
    assert isinstance(asked_for, Mapping)
    assert asked_for["operation"] == "roles run: spend"
    assert asked_for["roles"] == "trajectory"
    assert asked_for["approval"] == str(ticket.approval_id)


def test_a_service_refusal_leaves_a_refusal_event(chain: Chain) -> None:
    """The service's own refusal is recorded even though no spend reaches it.

    ``run_role_run_service`` refuses before calling ``run_role_run`` when a
    model judgement is needed and no backend is wired. That refusal never
    reaches the spend's wrapper, so it is recorded where it is raised —
    otherwise the service's most common refusal would be the one the log
    still cannot show.

    Red by: removing the record from the service's backend check.
    """
    ticket = request_role_run(
        chain.context,
        _request(chain),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    before = read_events(chain.context).events

    with pytest.raises(ApplicationRefusedError) as raised:
        run_role_run_service(chain.context, ticket, backend=None, at=MOMENT)

    assert raised.value.reason is ApplicationRefusal.ROLE_RUN_NO_PROVIDER
    new = read_events(chain.context).events[len(before) :]
    assert [event.type for event in new] == [EventType.REFUSAL_RECORDED]
    assert new[0].payload["reason"] == ApplicationRefusal.ROLE_RUN_NO_PROVIDER.value


# --------------------------------------------------------------------------- #
# (b) an answered request closes its stage and its run
# --------------------------------------------------------------------------- #


def test_an_answered_request_completes_the_stage_and_finishes_the_run(chain: Chain) -> None:
    """The pilot's model request, closed.

    The run asks for an approval, a person grants it, and the run spends it
    on a scripted model answer. When the answer comes back the operation its
    intent named is confirmed, the stage that was parked on the approval is
    completed, and the run is finished — and the log says so in that order.

    **The state is asserted as a fact.** The stage's status, the run's
    status and its ``finished_at`` are read from the store, not inferred
    from the absence of an exception.

    Red by: removing the closure after ``request_model`` returns, which
    leaves the stage ``blocked`` and the run ``running`` after the exchange
    was recorded — exactly the pilot's chain.
    """
    ticket = request_role_run(
        chain.context,
        _request(chain),
        plan=_plan(),
        expires_at=EXPIRES,
        now=MOMENT,
    )
    assert ticket.approval_id is not None, "the run will need a judgement, so it needed consent"
    grant_approval(chain.context, ticket.approval_id, now=MOMENT)

    result = run_role_run(
        chain.context,
        ticket,
        grants=_grants(),
        at=MOMENT,
        send=lambda prompt: _invocation({"trajectory": _trajectory_answer()}),
        capabilities=_probed(Capability.STRUCTURED_OUTPUT_NATIVE),
    )
    assert result.candidate is not None, "the run did not finish its own work"

    # -- the rows are the facts the log claims ------------------------------- #
    approvals = list_approvals(chain.context.store.session, chain.context.task_id)
    assert [row.state.value for row in approvals] == ["consumed"], (
        "the approval was not the one this run spent"
    )
    operations = list_operations(chain.context.store.session, chain.context.task_id)
    assert len(operations) == 1, "the run planned a second operation"
    assert operations[0].state is OperationState.CONFIRMED, (
        "the operation the approval authorised was not confirmed"
    )
    stages = list_stages(chain.context.store.session, chain.context.task_id)
    assert len(stages) == 1, "the run created a second stage"
    stage = stages[0]
    assert stage.name == "approval"
    assert stage.status is StageStatus.COMPLETED, (
        "the stage stayed blocked after its approval was consumed"
    )
    assert stage.blocked_reason is None, "a completed stage still carries a reason to wait"
    runs = list_runs(chain.context.store.session, chain.context.task_id)
    assert len(runs) == 1, "the run created a second attempt"
    run = runs[0]
    assert run.status is RunStatus.FINISHED, "the run stayed running after its stage completed"
    assert run.finished_at == MOMENT, "the run was finished at a moment it did not record"

    # -- the log says what happened, in the order it happened ---------------- #
    events = read_events(chain.context).events
    types = [event.type for event in events]
    # The task's creation precedes the run; the ask's chain starts at the run.
    start = types.index(EventType.RUN_STARTED)
    assert types[start : start + 5] == [
        EventType.RUN_STARTED,
        EventType.STAGE_ENTERED,
        EventType.OPERATION_AWAITING_APPROVAL,
        EventType.APPROVAL_REQUESTED,
        EventType.STAGE_BLOCKED,
    ], "the ask's own chain is not the one the pilot recorded"
    assert types[-3:] == [
        EventType.OPERATION_CONFIRMED,
        EventType.STAGE_COMPLETED,
        EventType.RUN_FINISHED,
    ], "the closure is missing from the end of the log, or is out of order"
    assert (
        types.index(EventType.APPROVAL_CONSUMED)
        < types.index(EventType.OPERATION_INTENT)
        < types.index(EventType.MODEL_EXCHANGED)
        < types.index(EventType.OPERATION_CONFIRMED)
    ), "the spend, the call and the closure are not in the order they happened"

    completed = next(event for event in events if event.type is EventType.STAGE_COMPLETED)
    assert completed.transition is not None
    assert completed.transition.from_state == StageStatus.BLOCKED.value
    assert completed.transition.to_state == StageStatus.COMPLETED.value

    finished = next(event for event in events if event.type is EventType.RUN_FINISHED)
    assert finished.transition is not None
    assert finished.transition.from_state == RunStatus.RUNNING.value
    assert finished.transition.to_state == RunStatus.FINISHED.value
