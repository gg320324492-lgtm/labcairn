"""The role loop's operable entry points: the API's two routes and the CLI's
one command, each reaching the same layer operation.

**What is under test.** Phase 4 execution plan §8.2: ``application.roles_run``
already had its own witnesses (``tests/test_roles_run.py``); the gap was that
no surface could reach it. This file watches the *wiring*:

======================================================  =========================
     acceptance                                         witness
======================================================  =========================
the API's ask writes the question down and              ``POST
spends nothing                                          /roles/run-questions``
                                                        answers with the layer's
                                                        own ticket: the roles,
                                                        the prompt, the excerpts,
                                                        and the *pending*
                                                        approval -- and no event
                                                        row, because nothing ran
the API's run spends a granted approval and             ``POST /roles/run`` with
returns the roles' outputs                              a granted approval id
                                                        answers with the
                                                        candidate the role
                                                        produced, and the model's
                                                        exchange event
an unknown role is refused by name                      the route answers
                                                        ``role_run_unknown_role``,
                                                        not a crash and not a
                                                        default routing
a contract that does not list the capability is         ``role_spec_capability_not_listed``
refused                                                 -- the roles' own checks
                                                        are the gate, at the
                                                        surface too
a declaration of material the chain does not hold       ``role_run_material_mismatch``
is refused
a run without a wired backend is refused, not           ``role_run_no_provider``
simulated                                               for a run that needs a
                                                        model judgement; a run
                                                        whose judgements are all
                                                        supplied needs no backend
the run route presents the token, like every            401 without it, 403 from
mutating route                                          a foreign origin
the CLI reaches the same operation                      ``roles run --json``
                                                        prints the layer's own
                                                        result model's bytes
the CLI's ask is not the spend                          without ``--approval``,
                                                        the command prints the
                                                        pending approval and
                                                        exits clean
======================================================  =========================

**The fixture is the chain's own.** The comments, versions, edges, role
contracts and the confirmed rule are the scaffolding ``test_roles_run.py``
uses, so a run this file asserts is a run the product wrote, read back
through the surface under test.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from feedback_chain_fixtures import MOMENT, ChainEnv, a_comment, build_chain
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.api import create_app
from labcairn.api.events import UnwiredEventSource
from labcairn.application.model_request import ModelInvocation
from labcairn.application.roles_run import ModelCallPlan, RoleRunBackend
from labcairn.db.models import EditActionRow
from labcairn.guidance.rules import confirm_rule, propose_rule, record_counterexample
from labcairn.papers.feedback import record_feedback, set_issue_key
from labcairn.providers.capabilities import (
    ALL_CAPABILITIES,
    Capability,
    CapabilityOutcome,
    ProviderCapabilities,
)
from labcairn.roles.spec import FORBIDDEN_ACTIONS, define_role_spec
from labcairn.security.capabilities import CapabilityId
from labcairn.security.permissions import Grant

pytestmark = pytest.mark.integration

env = _shared_env

EXPIRES = MOMENT.replace(year=2027)

KEY = "iss-gold-a-r1"
COMMENT = "Define the parameter."
QUOTE = "Define the parameter"

RULE = (
    "When the advisor asks what a parameter is, the answer names the quantity"
    " it estimates and where it comes from."
)
COUNTEREXAMPLE = "The parameter was defined in the previous draft, and the advisor still asked."

DESTINATION = "api.model-provider.example"

#: The workspace-relative path of the comment's material, as the chain holds it.
MATERIAL_PATH = "materials/manuscript.docx"
#: The root and the key the chain's material landed in, as the ledger
#: canonicalises them. Derived from the fixture the way the loop derives them.
MATERIAL_ROOT = "source:0"
MATERIAL_KEY = "manuscript.docx"

OBJECTIVES: dict[str, str] = {
    "trajectory": "Align the advisor's comments with the edits actually made.",
    "guidance": "Turn a confirmed case into a card a student can act on.",
    "critique": "Review a card independently and retrieve the counter-evidence.",
}

#: The service's own origin, spelled as the guard allows it.
OWN_ORIGIN = "http://127.0.0.1:8000"

#: An origin that is not the service's own. A page on another site sends
#: exactly this.
FOREIGN_ORIGIN = "https://evil.example"

#: The fixture the running test made, so a helper that builds a request body
#: can name the rule the fixture confirmed. One test runs at a time; the box
#: is the module's, and the fixture fills it.
_LAST_LOOP: list[ChainEnv] = [None]  # type: ignore[list-item]

#: The id of the rule the fixture confirmed, read once when it was written.
#: The rule's id is derived from its draft's fields, so the fixture reads the
#: row back rather than recomputing it -- and a helper that builds a request
#: body names it without touching the store again, because a read on the
#: fixture's session would hold SQLite's read lock against the request under
#: test.
_LAST_RULE_ID: list[str | None] = [None]


# --------------------------------------------------------------------------- #
# the environment
# --------------------------------------------------------------------------- #


def _spec(context: Any, role_id: str) -> None:
    """One role's contract, with the capability the run exercises.

    **Written through the layer's own operation**, so the contract the loop
    reads is one a product wrote, not a row a test inserted.
    """
    define_role_spec(
        context,
        role_id=role_id,
        role_version=1,
        objective=OBJECTIVES[role_id],
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
        prompt_template_version=f"{role_id}-v1",
        model_config_ref="configs/model.json",
        now=MOMENT,
    )


@pytest.fixture()
def loop(env: StoreEnv, tmp_path: Path) -> ChainEnv:
    """A chain with a keyed comment and its edit, a confirmed rule, the contracts.

    **The workspace carries the files a surface command reads.** The chain
    fixture binds a task to the directory, but the CLI's own command reads
    the workspace's ``workspace.json``, its policy and its database by
    name; those are written here, so ``roles run`` -- which runs in its own
    process against this workspace -- finds what a workspace the product
    initialised would hold. The database is the fixture's own file, named
    in the configuration; the policy allows everything, because what is
    under test is the wiring, not the policy.
    """
    from labcairn.cli.workspace import (
        CONFIG_SCHEMA_VERSION,
        DEFAULT_POLICY_RULES,
        WorkspaceConfig,
        WorkspaceLocation,
        write_config,
        write_policy,
    )
    from labcairn.security.policy import Permission, Rule

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    store = env.store()
    chain = build_chain(store, workspace_root, comments=(a_comment("201"),))
    (event,) = record_feedback(
        chain.context,
        project_id=chain.project_id,
        version_id=chain.version_id,
        now=MOMENT,
    )
    set_issue_key(chain.context, feedback_id=event.feedback_id, issue_key=KEY, now=MOMENT)
    session = chain.context.store.session
    session.add(
        EditActionRow(
            edit_action_id="edit-201",
            feedback_id=event.feedback_id,
            version_edge_id=chain.edge_id,
            actor_kind="student",
            grade="observed",
            created_at=MOMENT,
        )
    )
    session.flush()
    rule = propose_rule(
        chain.context,
        issue_type="method_and_hypothesis",
        statement=RULE,
        rule_context="A methods section whose parameter is never named.",
        scope="Empirical papers in this group's field.",
        example="The comment of the run, on the methods paragraph.",
        sources=(KEY,),
        proposed_by="a-mentor",
        now=MOMENT,
    )
    confirm_rule(chain.context, rule_id=rule.rule_id, confirmed_by="the-advisor", now=MOMENT)
    record_counterexample(
        chain.context,
        rule_id=rule.rule_id,
        statement=COUNTEREXAMPLE,
        recorded_by="a-reader",
        now=MOMENT,
    )
    for role_id in ("trajectory", "guidance", "critique"):
        _spec(chain.context, role_id)
    session.commit()

    location = WorkspaceLocation(root=workspace_root)
    write_policy(
        location,
        (
            *DEFAULT_POLICY_RULES,
            Rule(effect=Permission.ALLOW, pattern="**"),
        ),
    )
    write_config(
        location,
        WorkspaceConfig(
            schema_version=CONFIG_SCHEMA_VERSION,
            database="../labcairn.db",
            source_dirs=("materials",),
            current_task=str(chain.context.task_id),
        ),
    )
    assert location.config_path.is_file(), "the workspace carries its configuration"
    _LAST_LOOP[0] = chain
    _LAST_RULE_ID[0] = rule.rule_id
    return chain


def _plan(**overrides: object) -> ModelCallPlan:
    """What the model call needs from the caller, declaring the chain's material."""
    plan: dict[str, object] = {
        "provider": "fake",
        "model": "scripted",
        "root_id": MATERIAL_ROOT,
        "resource_key": MATERIAL_KEY,
        "material_ref": MATERIAL_PATH,
        "purpose": "guidance_review",
        "destination": DESTINATION,
        "subject_ref": "proj-1",
    }
    plan.update(overrides)
    return ModelCallPlan(**plan)  # type: ignore[arg-type]


def _body(**overrides: object) -> dict[str, Any]:
    """One role-loop request, as the API's body accepts it.

    **The rule is the fixture's own.** A body that named no rule would ask
    a question without the rule's text, and the excerpts a run sends would
    be the comment alone.
    """
    body: dict[str, Any] = {
        "roles": ["trajectory"],
        "project_id": "proj-1",
        "issue_key": KEY,
        "version_ids": ["ver-1", "ver-2"],
        "rule_id": _LAST_RULE_ID[0],
        "provider": "fake",
        "model": "scripted",
        "root_id": MATERIAL_ROOT,
        "resource_key": MATERIAL_KEY,
        "material_ref": MATERIAL_PATH,
        "purpose": "guidance_review",
        "destination": DESTINATION,
        "subject_ref": "proj-1",
        "expires_at": EXPIRES.isoformat(),
    }
    body.update(overrides)
    return body


def _trajectory_judgement() -> dict[str, Any]:
    """The judgement role A works from, as the rehearsal supplied it."""
    return {
        "issue_type": "method_and_hypothesis",
        "alignment": "partial",
        "advisor_quote": QUOTE,
        "note": "the change answered the wording, not the missing quantity.",
        "edit_action_id": "edit-201",
    }


def _trajectory_answer() -> dict[str, Any]:
    """The document role A's judgement takes, as the model would state it."""
    return _trajectory_judgement()


def _invocation(structured: dict[str, Any]) -> ModelInvocation:
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


def _grants() -> list[Grant]:
    """The material-purpose grants the model call is judged against.

    **The scope reaches the material the loop computes** -- the workspace
    path of the comment's manuscript -- so the grant covers the material
    that leaves.
    """
    return [
        Grant(
            grant_id="g-model-1",
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


def _backend(structured: dict[str, Any] | None = None, *, probed: bool = True) -> RoleRunBackend:
    """A real-model backend wired to a scripted transport.

    **The transport is the seam, not the loop.** The loop's own gates --
    the transmit check, the approval spend, the exchange record -- run
    exactly as they run against a wired adapter; what is scripted here is
    the provider's answer, which is what a test may stand in for.
    """
    captured: list[str] = []

    def send(prompt: str) -> ModelInvocation:
        captured.append(prompt)
        return _invocation(structured if structured is not None else {})

    return RoleRunBackend(
        provider="fake",
        model="scripted",
        send=send,
        capabilities=_probed(Capability.STRUCTURED_OUTPUT_NATIVE) if probed else None,
        grants=_grants(),
        destination=DESTINATION,
    )


# --------------------------------------------------------------------------- #
# the API's ask: POST /roles/run-questions
# --------------------------------------------------------------------------- #


@pytest.fixture()
def client(loop: ChainEnv) -> TestClient:
    """A client for the service over the chain's own task."""
    app = create_app(loop.context, event_source=UnwiredEventSource())
    with TestClient(app) as wired:
        yield wired


@pytest.fixture()
def token(client: TestClient) -> str:
    """The service's session token, read the way a client reads it."""
    response = client.get("/session")
    assert response.status_code == 200
    return str(response.json()["token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Origin": OWN_ORIGIN}


def test_the_ask_writes_the_question_down_and_spends_nothing(
    loop: ChainEnv, client: TestClient, token: str
) -> None:
    """``POST /roles/run-questions`` answers with the layer's own ticket.

    **Nothing has been spent**: the approval the ticket names is *pending*,
    no role has run, and the event log holds no model exchange. The prompt
    and the excerpts are carried, because a person grants an approval for
    *this* question and *this* material, and a ticket that did not show
    them would be a consent asked blind.
    """
    from labcairn.application.events import read_events
    from labcairn.runtime.event import EventType

    response = client.post("/roles/run-questions", json=_body(), headers=_auth(token))
    assert response.status_code == 201, response.text
    ticket = response.json()
    assert ticket["roles"] == ["trajectory"]
    assert "trajectory" in ticket["prompt"]
    assert ticket["excerpts"] == [COMMENT, RULE, COUNTEREXAMPLE]
    assert ticket["approval_id"] is not None, "a judgement is missing, so an approval was asked"
    assert ticket["material"]["resource_key"] == MATERIAL_KEY
    assert ticket["plan"]["destination"] == DESTINATION

    page = read_events(loop.context)
    assert not [event for event in page.events if event.type is EventType.MODEL_EXCHANGED], (
        "the ask reached no wire, and the event log says so"
    )


def test_the_ask_needs_no_approval_when_every_judgement_is_supplied(
    loop: ChainEnv, client: TestClient, token: str
) -> None:
    """A request whose judgements are all supplied mints no approval.

    **Asking is not spending, and a run that needs nothing asks for
    nothing.** The ticket still names the question -- the roles and the
    material -- because the ask is the whole of what this route is for.
    """
    response = client.post(
        "/roles/run-questions",
        json=_body(trajectory=_trajectory_judgement()),
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    ticket = response.json()
    assert ticket["approval_id"] is None, "nothing was needed, so nothing was asked for"
    assert ticket["excerpts"] == [COMMENT, RULE, COUNTEREXAMPLE]


def test_the_ask_refuses_an_unknown_role_by_name(
    loop: ChainEnv, client: TestClient, token: str
) -> None:
    """A role the loop does not know is refused, not routed by a default."""
    response = client.post(
        "/roles/run-questions",
        json=_body(roles=["astronomer"]),
        headers=_auth(token),
    )
    assert response.status_code == 403
    assert response.json()["reason"] == "role_run_unknown_role"


def test_the_ask_refuses_a_contract_that_does_not_list_the_capability(
    loop: ChainEnv, client: TestClient, token: str
) -> None:
    """A contract without the run's capability is refused at the surface too.

    **The roles' own checks are the gate.** The route adds no capability
    check of its own -- the refusal here is the layer's, reached through
    the route, which is the whole claim of the seam.
    """
    define_role_spec(
        loop.context,
        role_id="trajectory",
        role_version=2,
        objective=OBJECTIVES["trajectory"],
        input_schema="Input",
        output_schema="Output",
        allowed_capabilities=(CapabilityId.REPORT_RENDER,),
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
        prompt_template_version="trajectory-v2",
        model_config_ref="configs/model.json",
        now=MOMENT,
    )
    loop.context.store.session.commit()

    response = client.post("/roles/run-questions", json=_body(), headers=_auth(token))
    assert response.status_code == 403
    assert response.json()["reason"] == "role_spec_capability_not_listed"


def test_the_ask_refuses_a_material_declaration_that_is_not_the_chains(
    loop: ChainEnv, client: TestClient, token: str
) -> None:
    """A declaration of material the chain does not hold is refused by name.

    **The grant the transmit gate checks names a material, and the approval
    binds a set of excerpts** -- so a run that could send something else
    under this approval would be a consent that covered one thing and sent
    another.
    """
    response = client.post(
        "/roles/run-questions",
        json=_body(material_ref="materials/other.docx"),
        headers=_auth(token),
    )
    assert response.status_code == 403
    assert response.json()["reason"] == "role_run_material_mismatch"


# --------------------------------------------------------------------------- #
# the API's run: POST /roles/run
# --------------------------------------------------------------------------- #


def _ask(client: TestClient, token: str, **overrides: object) -> str:
    """The approval id the ask minted, from the body the run will present."""
    response = client.post("/roles/run-questions", json=_body(**overrides), headers=_auth(token))
    assert response.status_code == 201, response.text
    approval_id = response.json()["approval_id"]
    assert approval_id is not None
    return str(approval_id)


def test_the_run_spends_a_granted_approval_and_returns_the_roles_outputs(
    loop: ChainEnv, client: TestClient, token: str
) -> None:
    """``POST /roles/run`` with a granted approval runs the role and answers.

    **The response is what the roles produced, and the account of the
    call.** The candidate carries the contract that governed it; the
    model's answer and the exchange event are carried beside it, because a
    run that asked the model says so.
    """
    from labcairn.application import grant_approval
    from labcairn.core.ids import ApprovalId

    approval_id = _ask(client, token)
    grant_approval(loop.context, ApprovalId(uuid.UUID(approval_id)), now=MOMENT)
    loop.context.store.session.commit()

    client.app.state.role_runs = _backend({"trajectory": _trajectory_answer()})

    response = client.post("/roles/run", json=_body(approval_id=approval_id), headers=_auth(token))
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["roles"] == ["trajectory"]
    assert run["answer"] == "the model's answer"
    assert run["exchange_event_id"] is not None
    candidate = run["candidate"]
    assert candidate is not None
    assert candidate["issue_key"] == KEY
    assert candidate["alignment"] == "partial"
    assert candidate["role_id"] == "trajectory"
    assert candidate["role_version"] == 1
    assert candidate["advisor_quote"] == QUOTE


def test_the_run_refuses_an_ungranted_approval(
    loop: ChainEnv, client: TestClient, token: str
) -> None:
    """A run that spends an approval nobody granted is refused.

    **The consent is a person's act.** The ask mints a *pending* approval;
    a run that presents it before a person has granted it is refused, and
    the refusal is the approval machinery's own -- the ledger has no grant
    to spend, and the refusal says so.
    """
    approval_id = _ask(client, token)
    client.app.state.role_runs = _backend({"trajectory": _trajectory_answer()})
    response = client.post("/roles/run", json=_body(approval_id=approval_id), headers=_auth(token))
    assert response.status_code == 403
    assert response.json()["reason"] == "approval_refused"


def test_the_run_refuses_a_run_without_a_wired_backend(
    loop: ChainEnv, client: TestClient, token: str
) -> None:
    """A run that needs a model judgement and has no backend is refused.

    **The refusal, not a failure, is the honest state of a service the
    owner has not authorised.** An invented judgement would put words in a
    model's mouth that no model said.
    """
    approval_id = _ask(client, token)
    from labcairn.application import grant_approval
    from labcairn.core.ids import ApprovalId

    grant_approval(loop.context, ApprovalId(uuid.UUID(approval_id)), now=MOMENT)
    loop.context.store.session.commit()
    client.app.state.role_runs = None

    response = client.post("/roles/run", json=_body(approval_id=approval_id), headers=_auth(token))
    assert response.status_code == 403
    assert response.json()["reason"] == "role_run_no_provider"


def test_the_run_without_a_backend_runs_supplied_judgements(
    loop: ChainEnv, client: TestClient, token: str
) -> None:
    """A run whose judgements are all supplied needs no backend and no wire.

    **The roles judge what the caller brought.** The refusal above is for
    a run that needs the model; this one reaches no wire, and it runs on a
    service the owner has not authorised, because nothing leaves.
    """
    client.app.state.role_runs = None
    response = client.post(
        "/roles/run",
        json=_body(trajectory=_trajectory_judgement()),
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["roles"] == ["trajectory"]
    assert run["answer"] is None, "no model call was needed, and none was made"
    assert run["exchange_event_id"] is None
    assert run["candidate"] is not None


def test_the_run_needing_a_model_refuses_without_an_approval_id(
    loop: ChainEnv, client: TestClient, token: str
) -> None:
    """A run that needs the model and presents no approval id is refused.

    **A model call may only be spent with one.** The ask minted a pending
    approval; the run route refuses before the layer is reached, because a
    run without a granted consent is not a run this service may make.
    """
    client.app.state.role_runs = _backend({"trajectory": _trajectory_answer()})
    response = client.post("/roles/run", json=_body(), headers=_auth(token))
    assert response.status_code == 403
    assert response.json()["reason"] == "approval_missing"


def test_the_run_route_presents_the_token(loop: ChainEnv, client: TestClient, token: str) -> None:
    """The run changes something, so the session guard covers it.

    **The right origin is not consent to act, and a token is not a pass
    from a foreign origin** -- the same two guards every mutating route
    answers to.
    """
    foreign = client.post(
        "/roles/run",
        json=_body(),
        headers={"Authorization": f"Bearer {token}", "Origin": FOREIGN_ORIGIN},
    )
    assert foreign.status_code == 403
    assert foreign.json()["reason"] == "origin_refused"

    tokenless = client.post("/roles/run", json=_body(), headers={"Origin": OWN_ORIGIN})
    assert tokenless.status_code == 401

    foreign_ask = client.post(
        "/roles/run-questions",
        json=_body(),
        headers={"Authorization": f"Bearer {token}", "Origin": FOREIGN_ORIGIN},
    )
    assert foreign_ask.status_code == 403
    assert foreign_ask.json()["reason"] == "origin_refused"

    tokenless_ask = client.post(
        "/roles/run-questions", json=_body(), headers={"Origin": OWN_ORIGIN}
    )
    assert tokenless_ask.status_code == 401


def test_the_run_refuses_an_unprobed_provider(
    loop: ChainEnv, client: TestClient, token: str
) -> None:
    """A schema request the provider's probe does not license is refused.

    **Before the wire, at no cost.** A backend wired with no probe record
    cannot be assumed to answer in a schema's shape, and the refusal says
    so rather than sending the material on the chance.
    """
    approval_id = _ask(client, token)
    from labcairn.application import grant_approval
    from labcairn.core.ids import ApprovalId

    grant_approval(loop.context, ApprovalId(uuid.UUID(approval_id)), now=MOMENT)
    loop.context.store.session.commit()
    client.app.state.role_runs = _backend({"trajectory": _trajectory_answer()}, probed=False)

    response = client.post("/roles/run", json=_body(approval_id=approval_id), headers=_auth(token))
    assert response.status_code == 403
    assert response.json()["reason"] == "model_schema_unprobed"


# --------------------------------------------------------------------------- #
# the CLI's command: roles run
# --------------------------------------------------------------------------- #


def _console_script() -> Path:
    """The script a developer types, as this interpreter would find it."""
    name = "labcairn.exe" if os.name == "nt" else "labcairn"
    return Path(sys.executable).parent / name


def _run_roles_cli(
    workspace: Path, *extra: str, expect_refusal: bool = False
) -> subprocess.CompletedProcess[str]:
    """One run of ``roles run``, through the console script.

    ``COLUMNS`` is set for the reason ``test_cli_support`` states: Rich asks
    the terminal how wide it is, and a pipe is not a terminal.
    """
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["COLUMNS"] = "200"
    completed = subprocess.run(
        [str(_console_script()), "--workspace", str(workspace), "roles", "run", *extra],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=300,
    )
    if expect_refusal:
        assert completed.returncode != 0, f"the command was expected to refuse: {completed.stdout}"
    else:
        assert completed.returncode == 0, f"the command refused: {completed.stderr}"
    return completed


def _loop_options() -> list[str]:
    """The options every CLI run carries: the request's work and plan fields."""
    return [
        "--role",
        "trajectory",
        "--project",
        "proj-1",
        "--issue-key",
        KEY,
        "--version",
        "ver-1",
        "--version",
        "ver-2",
        "--provider",
        "fake",
        "--model",
        "scripted",
        "--root",
        MATERIAL_ROOT,
        "--resource-key",
        MATERIAL_KEY,
        "--material-ref",
        MATERIAL_PATH,
        "--purpose",
        "guidance_review",
        "--destination",
        DESTINATION,
        "--subject-ref",
        "proj-1",
    ]


def test_the_cli_runs_supplied_judgements_and_prints_the_layers_own_result(
    loop: ChainEnv,
) -> None:
    """``roles run --json`` prints the layer's result model's bytes.

    **One serialization, two surfaces.** The command and the API's route
    pass through the same conversion, so what the CLI prints is what the
    API returned. The judgements are supplied outright, so the run reaches
    no wire and needs no approval -- the roles judge what the caller
    brought, under the contracts the store holds.
    """
    completed = _run_roles_cli(
        loop.context.workspace.selected_root,
        "--json",
        "--judgements",
        json.dumps({"trajectory": _trajectory_judgement()}),
        *_loop_options(),
    )
    run = json.loads(completed.stdout)
    assert run["roles"] == ["trajectory"]
    assert run["answer"] is None, "no model call was needed, and none was made"
    candidate = run["candidate"]
    assert candidate is not None
    assert candidate["issue_key"] == KEY
    assert candidate["alignment"] == "partial"
    assert candidate["role_id"] == "trajectory"


def test_the_cli_ask_prints_the_pending_approval_and_spends_nothing(loop: ChainEnv) -> None:
    """``roles run`` without ``--approval`` prints the ask, and spends nothing.

    **The ask is not the spend.** The command's output names the pending
    approval, the event log holds no exchange, and the approval row is
    still waiting for an answer.
    """
    from labcairn.application.events import read_events
    from labcairn.runtime.event import EventType

    completed = _run_roles_cli(loop.context.workspace.selected_root, "--json", *_loop_options())
    ticket = json.loads(completed.stdout)
    assert ticket["roles"] == ["trajectory"]
    assert ticket["approval_id"] is not None, "the ask names the approval to grant"

    page = read_events(loop.context)
    assert not [event for event in page.events if event.type is EventType.MODEL_EXCHANGED], (
        "the ask reached no wire"
    )


def test_the_cli_refuses_an_unknown_role(loop: ChainEnv) -> None:
    """An unknown role is refused by name at the console too."""
    completed = _run_roles_cli(
        loop.context.workspace.selected_root,
        "--json",
        "--role",
        "astronomer",
        "--project",
        "proj-1",
        "--issue-key",
        KEY,
        expect_refusal=True,
    )
    refusal = json.loads(completed.stdout)
    assert refusal["reason"] == "role_run_unknown_role"
