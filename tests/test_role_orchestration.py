"""The arrangement: which roles run is data, and every decision leaves a record.

**What is under test.** LC-P2-12 T04: ``roles.orchestration`` — the
routing tables, the priced invocation and its retry, the audit trail of
human decisions, and the one gate between an operation and a role's
contract.

====================================================  =========================
     the roles that run are the ones the request needed   a comment
                                                          extraction runs A
                                                          alone; the critique
                                                          has four ways in and
                                                          no fifth
     an unmeasurable cost refuses                         and a retry is the
                                                          same plan, paid once
     a human decision is audited                          appended, attributed,
                                                          never overwritten
     no role writes back, releases, or executes           the five forbidden
                                                          actions are on every
                                                          contract, and the gate
                                                          enforces them
====================================================  =========================
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from test_store_support import StoreEnv
from test_store_support import env as _shared_env

from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import ApplicationRefusedError
from labcairn.application.tasks import create_task
from labcairn.roles.orchestration import (
    ESCALATION_TABLE,
    DecisionLedger,
    InvocationPlan,
    LoopRequest,
    RoutingDecision,
    decide_roles,
    enforce_contract,
    prepare_invocation,
    record_human_decision,
    retry,
)
from labcairn.roles.refusals import RoleRefusal
from labcairn.roles.spec import (
    FORBIDDEN_ACTIONS,
    AgentRoleSpec,
    define_role_spec,
    load_spec,
)
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import CapabilityId
from labcairn.security.policy import Permission, PermissionPolicy, Rule

pytestmark = pytest.mark.integration

env = _shared_env

MOMENT = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)


def allow_all() -> PermissionPolicy:
    """A policy that permits everything, for a test about something else."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])


def _spec(context: ApplicationContext, role_id: str, *, cost_budget: float | None) -> AgentRoleSpec:
    """One role's contract, with the ceiling a test names."""
    capability = CapabilityId.MODEL_REQUEST if role_id == "guidance" else CapabilityId.SOURCE_READ
    return define_role_spec(
        context,
        role_id=role_id,
        role_version=1,
        objective=f"What the {role_id} role is for.",
        input_schema="Input",
        output_schema="Output",
        allowed_capabilities=(capability,),
        forbidden_actions=FORBIDDEN_ACTIONS,
        allowed_data_purposes=("guidance_review",),
        provider_routing_policy="single-provider-per-call",
        cost_budget=cost_budget,
        token_budget=4000,
        timeout_seconds=120,
        retry_policy="no-retry",
        fallback_policy="abstain",
        abstain_conditions=("material_under_two_comments",),
        escalation_conditions=("a_conflict_between_two_rules",),
        prompt_template_version=f"{role_id}-v1",
        model_config_ref="configs/model.json",
        now=MOMENT,
    )


@pytest.fixture()
def context(env: StoreEnv, tmp_path: Path) -> ApplicationContext:
    """A migrated store and a context, with the three roles' contracts defined."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    store = env.store()
    created = create_task(
        store=store,
        policy=allow_all(),
        workspace_root=workspace_root,
        title="Routing the roles",
        goal=TaskGoal(
            objective="Route the roles the request needs, and no more.",
            success_criterion="A decision the table explains.",
        ),
        source_dirs=(),
        now=MOMENT,
    )
    return ApplicationContext(
        workspace=created.workspace,
        store=store,
        policy=allow_all(),
        ledger=ApprovalLedger(),
    )


def _refusal(call: object) -> RoleRefusal:
    """The contract's refusal an expected error carries, so the test fails loudly."""
    assert isinstance(call, ApplicationRefusedError), f"expected a refusal, saw {call!r}"
    return RoleRefusal(call.reason.value.removeprefix("role_"))


def test_the_roles_that_run_are_the_ones_the_request_needed(
    context: ApplicationContext,
) -> None:
    """A comment extraction runs A alone; the critique has four ways in and no fifth."""
    extraction = decide_roles(LoopRequest(kind="a_comment_extraction", risk="low"))
    assert extraction.roles == ("trajectory",), "B and C are not the reader's roles"
    suggestion = decide_roles(LoopRequest(kind="a_research_suggestion", risk="low"))
    assert suggestion.roles == ("trajectory", "guidance")
    assert "critique" not in suggestion.roles

    high_risk = decide_roles(LoopRequest(kind="a_research_suggestion", risk="high"))
    assert high_risk.roles == ("trajectory", "guidance", "critique")
    thin = decide_roles(LoopRequest(kind="a_research_suggestion", risk="low", evidence_thin=True))
    assert "critique" in thin.roles
    disagree = decide_roles(
        LoopRequest(kind="a_research_suggestion", risk="low", models_disagree=True)
    )
    assert "critique" in disagree.roles
    asked = decide_roles(LoopRequest(kind="a_research_suggestion", risk="low", a_person_asks=True))
    assert "critique" in asked.roles

    # **The decision is recorded**: every role has its reason, named.
    assert len(high_risk.reasons) == 2
    assert high_risk.reasons[1] == ESCALATION_TABLE["high_risk"]
    assert all(decision.reasons for decision in (extraction, suggestion, thin))

    # **The routing is data**: a caller's own table is the decision.
    custom = decide_roles(
        LoopRequest(kind="a_research_suggestion", risk="high"),
        table={"a_research_suggestion": ("guidance",)},
        escalation={"high_risk": "the caller's own reason"},
    )
    assert custom.roles == ("guidance", "critique")
    assert custom.reasons[1] == "the caller's own reason"
    assert isinstance(
        decide_roles(LoopRequest(kind="a_comment_extraction", risk="low")), RoutingDecision
    )

    refused = _refusal(_capture(lambda: decide_roles(LoopRequest(kind="a_swarm", risk="low"))))
    assert refused is RoleRefusal.REQUEST_KIND_UNKNOWN
    refused = _refusal(
        _capture(lambda: decide_roles(LoopRequest(kind="a_comment_extraction", risk="wild")))
    )
    assert refused is RoleRefusal.REQUEST_RISK_UNKNOWN


def test_an_unmeasurable_cost_refuses_and_a_retry_does_not_pay_twice(
    context: ApplicationContext,
) -> None:
    """A budget whose price is unknown fails closed; a retry is the same plan."""
    unpriced = _spec(context, "trajectory", cost_budget=None)
    refused = _refusal(_capture(lambda: prepare_invocation(context, spec=unpriced)))
    assert refused is RoleRefusal.SPEC_COST_UNMEASURED

    priced = _spec(context, "guidance", cost_budget=0.5)
    plan = prepare_invocation(context, spec=priced)
    assert isinstance(plan, InvocationPlan)
    assert plan.token_budget == priced.token_budget
    assert plan.timeout_seconds == priced.timeout_seconds
    assert retry(plan) is plan, "the retry is the same invocation, paid once"


def test_a_human_decision_on_a_card_is_audited() -> None:
    """The decision is appended, attributed, and never overwritten."""
    ledger = DecisionLedger()
    first = record_human_decision(
        ledger,
        card_locator="docx:word/document.xml#para=12",
        decision="accepted",
        decided_by="the-student",
        reason="the card names the baseline; the paragraph now has one.",
        now=MOMENT,
    )
    assert first.decision == "accepted"
    assert first.decided_by == "the-student"
    assert ledger.decisions_for("docx:word/document.xml#para=12") == (first,)
    second = record_human_decision(
        ledger,
        card_locator="docx:word/document.xml#para=12",
        decision="rejected",
        decided_by="the-student",
        reason="on reflection the rule has a case against it here.",
        now=MOMENT,
    )
    trail = ledger.decisions_for("docx:word/document.xml#para=12")
    assert trail == (first, second), "a change of mind is a second record"
    assert not hasattr(ledger, "update") and not hasattr(ledger, "delete")

    refused = _refusal(
        _capture(
            lambda: record_human_decision(
                ledger,
                card_locator="docx:word/document.xml#para=12",
                decision="maybe",
                decided_by="the-student",
                reason="a third answer",
                now=MOMENT,
            )
        )
    )
    assert refused is RoleRefusal.DECISION_UNKNOWN
    refused = _refusal(
        _capture(
            lambda: record_human_decision(
                ledger,
                card_locator="docx:word/document.xml#para=12",
                decision="accepted",
                decided_by="   ",
                reason="nobody signed",
                now=MOMENT,
            )
        )
    )
    assert refused is RoleRefusal.DECISION_WITHOUT_A_PERSON
    refused = _refusal(
        _capture(
            lambda: record_human_decision(
                ledger,
                card_locator="docx:word/document.xml#para=12",
                decision="accepted",
                decided_by="the-student",
                reason=" ",
                now=MOMENT,
            )
        )
    )
    assert refused is RoleRefusal.DECISION_WITHOUT_A_REASON


def test_no_role_may_write_back_release_or_execute(context: ApplicationContext) -> None:
    """The five forbidden actions are on every contract, and the gate enforces them."""
    for role_id in ("trajectory", "guidance", "critique"):
        spec = _spec(context, role_id, cost_budget=0.5)
        assert spec.forbidden_actions == FORBIDDEN_ACTIONS, role_id
        for action in FORBIDDEN_ACTIONS:
            refused = _refusal(
                _capture(lambda spec=spec, action=action: enforce_contract(spec, action=action))
            )
            assert refused is RoleRefusal.SPEC_FORBIDDEN_ACTION_REQUESTED, (
                f"{role_id} does not refuse {action.value!r}"
            )
        refused = _refusal(
            _capture(
                lambda spec=spec: enforce_contract(
                    spec, capability=CapabilityId.ARTIFACT_WRITE.value
                )
            )
        )
        assert refused is RoleRefusal.SPEC_CAPABILITY_NOT_LISTED, role_id

    guidance = load_spec(context, role_id="guidance")
    enforce_contract(guidance, capability=CapabilityId.MODEL_REQUEST.value)
    refused = _refusal(
        _capture(lambda: enforce_contract(guidance, capability="capability.that.does.not.exist"))
    )
    assert refused is RoleRefusal.SPEC_CAPABILITY_UNKNOWN


def _capture(call: object) -> ApplicationRefusedError:
    """The refusal a call that must raise carries."""
    assert callable(call)
    try:
        call()
    except ApplicationRefusedError as refused:
        return refused
    raise AssertionError("the call was expected to refuse, and it did not")
