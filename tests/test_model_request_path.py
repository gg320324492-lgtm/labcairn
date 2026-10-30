"""The model-call path, watched.

**What is under test.** LC-P2-01: one product operation that asks a
declared model and records what came back, under the repository's
existing consent, budget, capability and refusal machinery — with the
bridge at the caller, so ``providers/`` keeps its disjointness from the
permission layer.

**And a fresh checkout cannot spend money by accident.** The dependency
is declared, and the tree carries no model.
"""

from __future__ import annotations

import re
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from test_store_support import StoreEnv
from test_store_support import env as _shared_env

from labcairn.application import create_task
from labcairn.application.approvals import (
    ApprovalRequest,
    ApprovalUse,
    grant_approval,
    request_approval,
)
from labcairn.application.context import ApplicationContext
from labcairn.application.model_request import request_model
from labcairn.application.refusal import ApplicationRefusedError
from labcairn.core.ids import ApprovalId
from labcairn.db.repository import list_approvals
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import CapabilityId, ModelRequestArgs
from labcairn.security.permissions import Grant
from labcairn.security.policy import Permission, PermissionPolicy, Rule

pytestmark = pytest.mark.integration

env = _shared_env

#: The suppliers the capability probe has measured, by the strings that
#: would mark a written configuration: a model id, and the endpoint a
#: configuration would carry. **The list grows only when the owner
#: authorises a supplier** — a supplier that is not authorised has no
#: entry, and an authorised one arrives here by editing this tuple, which
#: is a review of the writing, not an accident of it. ``api.minimax.cn``
#: is deliberately absent: it is already the destination the consent
#: demonstration sends *against* — data in an example, not configuration.
WRITTEN_MODEL_MARKERS: tuple[str, ...] = (
    "MiniMax-M3.1-Flash",
    "dashscope.aliyuncs",
)


def _pyproject(repo_root: Path) -> dict[str, Any]:
    """The parsed ``pyproject.toml``."""
    return tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))


def test_httpx_is_a_declared_dependency(repo_root: Path) -> None:
    """The HTTP client the provider path runs on is a version this project chose.

    It arrived transitively through ``pydantic-ai`` and was declared by
    nobody; the provider path is built on it, so it belongs in the
    runtime dependencies, and the lockfile moves with the declaration.
    """
    pyproject = _pyproject(repo_root)
    declared = [
        line for line in pyproject["project"]["dependencies"] if re.match(r"^httpx[\s>=<~!]", line)
    ]
    assert declared, "httpx is not in the runtime dependencies"

    lock = tomllib.loads((repo_root / "uv.lock").read_text(encoding="utf-8"))
    root = next(package for package in lock["package"] if package["name"] == "labcairn")
    assert any(dep["name"] == "httpx" for dep in root["dependencies"]), (
        "the lockfile's root package does not depend on httpx"
    )
    locked = next(package for package in lock["package"] if package["name"] == "httpx")
    major, minor = (int(part) for part in locked["version"].split(".")[:2])
    assert (major, minor) >= (0, 27), f"httpx {locked['version']} is outside the declared range"


def test_no_model_id_endpoint_or_price_is_written_into_the_tree(repo_root: Path) -> None:
    """A supplier's identity is the operator's configuration, never the tree's.

    The repository's own configuration is the fake default: no
    ``configs/`` directory exists, because a configuration file is an
    operator's act. And no source file, example or project metadata
    carries a model id or a supplier endpoint — the probe's measured
    answers live in the store and the work orders' measurement
    histories, which are records, not configuration.
    """
    configs = repo_root / "configs"
    assert not configs.exists(), (
        "configs/ exists; the repository ships no configuration, and an"
        " operator's providers.json lives in a workspace, not in the tree"
    )
    surfaces = [
        repo_root / "pyproject.toml",
        *(path for path in (repo_root / "src").rglob("*.py")),
        *(path for path in (repo_root / "examples").rglob("*.py")),
    ]
    for surface in surfaces:
        text = surface.read_text(encoding="utf-8")
        for marker in WRITTEN_MODEL_MARKERS:
            assert marker not in text, f"{surface.name} carries {marker!r}"


# --------------------------------------------------------------------------- #
# the bridge: the material gate first, then the approval (LC-P2-01 T01)
# --------------------------------------------------------------------------- #

MOMENT = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)

#: The destination a permitted request sends to. An example domain, the
#: way the consent demonstration's own destination is one.
DESTINATION = "api.model-provider.example"

MATERIAL_REF = "proj-1/manuscript.txt"


def _model_use() -> ApprovalUse:
    """What a model call is spent on — the capability whose payload leaves.

    The arguments are the request's canonical form: the digest is
    recomputed over them at the moment of use, so an approval to send
    one excerpt set does not authorise another.
    """
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


def _grants(destination: str = DESTINATION) -> list[Grant]:
    """The material-purpose grants the request is judged against."""
    return [
        Grant(
            grant_id="g-model-1",
            subject_ref="proj-1",
            permission="external_transmit",
            purpose="transmit",
            scope="proj-1/**",
            destination=destination,
            granted_by="Dr. Chen",
            granted_at=MOMENT,
            expires_at=None,
            state="active",
            withdrawn_at=None,
            withdrawn_by=None,
            withdrawal_reason=None,
        )
    ]


@pytest.fixture()
def context(env: StoreEnv, tmp_path: Path) -> ApplicationContext:
    """A migrated store and a task under it, with a policy that asks."""
    workspace_root = tmp_path / "workspace"
    materials = workspace_root / "materials"
    materials.mkdir(parents=True)
    created = create_task(
        store=env.store(),
        policy=PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")]),
        workspace_root=workspace_root,
        title="The model-call path",
        goal=TaskGoal(
            objective="Ask a declared model under the two gates.",
            success_criterion="An answer the consent layer permitted.",
        ),
        source_dirs=(materials,),
    )
    return ApplicationContext(
        workspace=created.workspace,
        store=env.store(),
        policy=PermissionPolicy.from_rules([Rule(effect=Permission.ASK, pattern="**")]),
        ledger=ApprovalLedger(),
    )


def _spy(reached: list[str]) -> str:
    """The invocation the refused request must never reach."""
    reached.append("the wire was reached")
    return "an answer"


def _asked(context: ApplicationContext) -> ApprovalId:
    """An approval that has been asked for, and not granted."""
    return request_approval(
        context,
        ApprovalRequest(use=_model_use(), expires_at=MOMENT.replace(year=2027)),
    ).approval.approval_id


def _granted(context: ApplicationContext) -> ApprovalId:
    """An approval asked for and granted, and not yet spent."""
    approval_id = _asked(context)
    grant_approval(context, approval_id, now=MOMENT)
    return approval_id


def test_an_unapproved_model_request_refuses_and_sends_nothing(
    context: ApplicationContext,
) -> None:
    """No granted approval, no request: the wire is never reached."""
    approval_id = _asked(context)
    reached: list[str] = []

    with pytest.raises(ApplicationRefusedError):
        request_model(
            context,
            approval_id,
            _grants(),
            use=_model_use(),
            subject_ref="proj-1",
            destination=DESTINATION,
            material_ref=MATERIAL_REF,
            at=MOMENT,
            send=lambda: _spy(reached),
        )
    assert reached == [], "an unapproved request reached the wire"
    rows = list_approvals(context.store.session, context.task_id)
    assert all(row.state != "consumed" for row in rows), "nothing was spent"


def test_the_material_gate_runs_before_the_approval_is_spent(
    context: ApplicationContext,
) -> None:
    """A refusal for want of a grant leaves the approval unspent.

    The grant names the destination, and the request asks for another:
    the gate refuses, the approval is still grantable, and fixing the
    grant is enough — the person is not asked to pay for the refusal.
    """
    approval_id = _granted(context)
    reached: list[str] = []

    with pytest.raises(ApplicationRefusedError):
        request_model(
            context,
            approval_id,
            _grants(destination="api.other-provider.example"),
            use=_model_use(),
            subject_ref="proj-1",
            destination=DESTINATION,
            material_ref=MATERIAL_REF,
            at=MOMENT,
            send=lambda: _spy(reached),
        )
    assert reached == [], "a refused request reached the wire"
    rows = list_approvals(context.store.session, context.task_id)
    assert all(row.state != "consumed" for row in rows), "the approval stayed unspent"

    answer = request_model(
        context,
        approval_id,
        _grants(),
        use=_model_use(),
        subject_ref="proj-1",
        destination=DESTINATION,
        material_ref=MATERIAL_REF,
        at=MOMENT,
        send=lambda: "the model's answer",
    )
    assert answer.answer == "the model's answer"
    assert answer.destination == DESTINATION
    rows = list_approvals(context.store.session, context.task_id)
    assert any(row.state == "consumed" for row in rows)
