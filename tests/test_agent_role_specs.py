"""The role contract, as data — and the code that enforces it.

**What is under test.** LC-P2-12 T00: ``agent_role_specs``, and the
module that defines, loads and enforces a role's terms.

====================================================  =========================
     the contract is versioned                          a new contract is a new
                                                        row, and the version is
                                                        on the output
     the boundary is the list, not the prompt           a capability outside it
                                                        is refused, by reason
     no direct path out                                 the five forbidden
                                                        actions are closed and
                                                        the contract refuses one,
                                                        and the module that holds
                                                        them imports no network
     the schema refuses what the API refuses            the rows are written, raw
     a contract is not overwritten                      a second definition of a
                                                        version is refused by name
====================================================  =========================

**Why the schema's refusals are witnessed by writing rows.** The
project's lesson from revision 0007: *"the parity test passed through it,
because the migration and the ORM were mangled identically."* So each
schema rule is witnessed by **writing a row the schema must refuse** with
a raw ``INSERT`` that bypasses the ORM, and watching the database refuse
it.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_store_support import StoreEnv
from test_store_support import env as _shared_env

import labcairn.roles.spec as spec_module
from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import ApplicationRefusedError
from labcairn.application.tasks import create_task
from labcairn.roles.refusals import RoleRefusal
from labcairn.roles.spec import (
    FORBIDDEN_ACTIONS,
    AgentRoleSpec,
    ForbiddenAction,
    RoleOutput,
    define_role_spec,
    load_spec,
)
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import CapabilityId
from labcairn.security.policy import Permission, PermissionPolicy, Rule

pytestmark = pytest.mark.integration

env = _shared_env

MOMENT = datetime(2026, 5, 1, 9, 0, tzinfo=UTC)


def allow_all() -> PermissionPolicy:
    """A policy that permits everything, for a test about something else."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])


@pytest.fixture()
def context(env: StoreEnv, tmp_path: Path) -> ApplicationContext:
    """A migrated store and a context: the contract is a table."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    store = env.store()
    created = create_task(
        store=store,
        policy=allow_all(),
        workspace_root=workspace_root,
        title="Defining a role's contract",
        goal=TaskGoal(
            objective="Define the contract a role works under.",
            success_criterion="A contract the code can enforce.",
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


def _define(
    context: ApplicationContext,
    **overrides: object,
) -> AgentRoleSpec:
    """A contract for the demo role, with the fields a test overrides."""
    fields: dict[str, object] = {
        "role_id": "guidance",
        "role_version": 1,
        "objective": "Turn the trajectory's candidates into a card a student"
        " can act on, with its evidence and its limits.",
        "input_schema": "GuidanceCardInput",
        "output_schema": "GuidanceCard",
        "allowed_capabilities": (CapabilityId.MODEL_REQUEST,),
        "forbidden_actions": FORBIDDEN_ACTIONS,
        "allowed_data_purposes": ("guidance_review",),
        "provider_routing_policy": "single-provider-per-call",
        "cost_budget": None,
        "token_budget": 4000,
        "timeout_seconds": 120,
        "retry_policy": "no-retry",
        "fallback_policy": "abstain",
        "abstain_conditions": ("material_under_two_comments",),
        "escalation_conditions": ("a_conflict_between_two_rules",),
        "prompt_template_version": "guidance-card-v1",
        "model_config_ref": "configs/model.json",
        "now": MOMENT,
    }
    fields.update(overrides)
    return define_role_spec(context, **fields)  # type: ignore[arg-type]


def _reason(call: object) -> RoleRefusal:
    """The contract's refusal an expected error carries, so the test fails loudly."""
    assert isinstance(call, ApplicationRefusedError), f"expected a refusal, saw {call!r}"
    assert call.reason.value.startswith("role_spec_"), (
        f"expected a contract refusal, saw {call.reason.value!r}"
    )
    return RoleRefusal(call.reason.value.removeprefix("role_"))


def test_a_role_spec_is_versioned_and_the_version_is_on_the_output(
    context: ApplicationContext,
) -> None:
    """A new contract is a new row, and an output names the contract it was made under."""
    first = _define(context, role_version=1)
    second = _define(
        context,
        role_version=2,
        token_budget=8000,
    )
    assert second.role_version == 2 and second.token_budget == 8000
    assert load_spec(context, role_id="guidance") == second, (
        "the version a caller did not name should be the highest defined"
    )
    assert load_spec(context, role_id="guidance", version=1) == first, (
        "the old row keeps the terms it had"
    )

    @dataclass(frozen=True)
    class ACard(RoleOutput):
        """The smallest output a role could make, carrying the pair."""

        reason: str

    card = ACard(role_id=second.role_id, role_version=second.role_version, reason="a card")
    assert (card.role_id, card.role_version) == ("guidance", 2)
    with pytest.raises(FrozenInstanceError):
        card.role_version = 3  # type: ignore[misc]


def test_a_call_outside_the_role_spec_is_refused(context: ApplicationContext) -> None:
    """A capability the contract does not list is refused, with a machine-readable reason."""
    spec = _define(context)
    spec.require_allowed(CapabilityId.MODEL_REQUEST)
    refused = _reason(_capture(lambda: spec.require_allowed(CapabilityId.FS_WRITE)))
    assert refused is RoleRefusal.SPEC_CAPABILITY_NOT_LISTED
    assert not spec.allows(CapabilityId.SOURCE_READ)


def test_a_role_holds_no_direct_path_out(context: ApplicationContext, tmp_path: Path) -> None:
    """The five forbidden actions are closed, the contract refuses one, and
    the module that holds the contract imports no network and no writer."""
    spec = _define(context)
    for action in FORBIDDEN_ACTIONS:
        assert spec.forbids(action), f"the contract does not forbid {action.value!r}"
    assert len(FORBIDDEN_ACTIONS) == 5, "the five are closed; a sixth is an edit"
    refused = _reason(_capture(lambda: spec.refuse_forbidden(ForbiddenAction.EXECUTE_CODE)))
    assert refused is RoleRefusal.SPEC_FORBIDDEN_ACTION_REQUESTED

    # **The module carries no path out by import.** A contract module
    # whose import list contains a network client or a writer is a
    # contract whose boundary is already behind it, so the import list
    # is read as text and checked against the closed set of names that
    # would give one.
    source = Path(spec_module.__file__).read_text(encoding="utf-8")
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    for forbidden_module in ("socket", "http", "httpx", "requests", "urllib", "ftplib"):
        assert not any(
            name == forbidden_module or name.startswith(f"{forbidden_module}.") for name in imported
        ), f"the contract module imports {forbidden_module!r}, a path out"


def test_a_second_definition_of_one_version_is_refused(context: ApplicationContext) -> None:
    """A contract is not overwritten; a new contract is a new version."""
    _define(context, role_version=1)
    refused = _reason(_capture(lambda: _define(context, role_version=1)))
    assert refused is RoleRefusal.SPEC_ALREADY_DEFINED


def test_a_spec_nobody_defined_is_not_found(context: ApplicationContext) -> None:
    """A role id nobody defined arrives as a refusal, not as a KeyError."""
    refused = _reason(_capture(lambda: load_spec(context, role_id="trajectory")))
    assert refused is RoleRefusal.SPEC_NOT_FOUND
    _define(context, role_version=1)
    refused = _reason(_capture(lambda: load_spec(context, role_id="guidance", version=9)))
    assert refused is RoleRefusal.SPEC_NOT_FOUND


def test_an_unknown_capability_or_action_is_refused_by_name(
    context: ApplicationContext,
) -> None:
    """A name outside a closed vocabulary is refused at definition, not discovered at work."""
    refused = _reason(_capture(lambda: _define(context, allowed_capabilities=["model.bogus"])))
    assert refused is RoleRefusal.SPEC_CAPABILITY_UNKNOWN
    refused = _reason(_capture(lambda: _define(context, forbidden_actions=["fly_to_the_moon"])))
    assert refused is RoleRefusal.SPEC_FORBIDDEN_ACTION_UNKNOWN


def test_an_empty_field_or_a_zero_ceiling_is_refused(context: ApplicationContext) -> None:
    """A contract with nothing in it binds nobody; a zero ceiling holds nothing."""
    for field_name in (
        "objective",
        "input_schema",
        "output_schema",
        "provider_routing_policy",
        "retry_policy",
        "fallback_policy",
        "prompt_template_version",
        "model_config_ref",
        "role_id",
    ):

        def blank(fn: str = field_name) -> object:
            return _define(context, **{fn: "   "})

        refused = _reason(_capture(blank))
        assert refused is RoleRefusal.SPEC_FIELD_EMPTY, field_name
    refused = _reason(_capture(lambda: _define(context, token_budget=0)))
    assert refused is RoleRefusal.SPEC_FIELD_EMPTY
    refused = _reason(_capture(lambda: _define(context, role_version=0)))
    assert refused is RoleRefusal.SPEC_FIELD_EMPTY
    refused = _reason(_capture(lambda: _define(context, abstain_conditions=())))
    assert refused is RoleRefusal.SPEC_FIELD_EMPTY
    refused = _reason(_capture(lambda: _define(context, allowed_data_purposes=())))
    assert refused is RoleRefusal.SPEC_PURPOSE_EMPTY


def _raw_insert(session: Session, **columns: object) -> None:
    """Write a spec row the way a caller who bypasses the ORM would."""
    rows = ", ".join(columns)
    values = ", ".join(f":{name}" for name in columns)
    session.execute(
        text(f"INSERT INTO agent_role_specs ({rows}) VALUES ({values})"),
        dict(columns),
    )


def test_the_schema_refuses_what_the_api_refuses(env: StoreEnv) -> None:
    """The rows the schema must refuse are written, raw, and refused."""
    session = env.session
    fine = {
        "role_id": "guidance",
        "role_version": 1,
        "objective": "Turn candidates into a card.",
        "input_schema": "GuidanceCardInput",
        "output_schema": "GuidanceCard",
        "allowed_capabilities": json.dumps(["model.request"]),
        "forbidden_actions": json.dumps(["execute_code"]),
        "allowed_data_purposes": json.dumps(["guidance_review"]),
        "provider_routing_policy": "single-provider-per-call",
        "cost_budget": None,
        "token_budget": 4000,
        "timeout_seconds": 120,
        "retry_policy": "no-retry",
        "fallback_policy": "abstain",
        "abstain_conditions": json.dumps(["material_under_two_comments"]),
        "escalation_conditions": json.dumps(["a_conflict_between_two_rules"]),
        "prompt_template_version": "guidance-card-v1",
        "model_config_ref": "configs/model.json",
        "defined_at": MOMENT.isoformat(),
    }
    refusals = (
        ("an empty objective", {"objective": "   "}),
        ("a version below one", {"role_version": 0}),
        ("an empty output schema", {"output_schema": ""}),
        ("an empty model config reference", {"model_config_ref": " "}),
        ("a zero token budget", {"token_budget": 0}),
        ("a zero timeout", {"timeout_seconds": 0}),
        ("capabilities that are not JSON", {"allowed_capabilities": "model.request"}),
        ("an empty capability list", {"allowed_capabilities": json.dumps([])}),
        ("an empty abstain list", {"abstain_conditions": json.dumps([])}),
        ("an empty purpose list", {"allowed_data_purposes": json.dumps([])}),
        ("forbidden actions that are not JSON", {"forbidden_actions": "{not json"}),
    )
    for what, change in refusals:
        row = {**fine, **change}
        with pytest.raises(IntegrityError) as expected:
            _raw_insert(session, **row)
        session.rollback()
        assert expected.value.orig is not None, what
    _raw_insert(session, **fine)
    session.rollback()


def _capture(call: Callable[[], object]) -> ApplicationRefusedError:
    """The refusal a call that must raise carries."""
    try:
        call()
    except ApplicationRefusedError as refused:
        return refused
    raise AssertionError("the call was expected to refuse, and it did not")
