"""The judgement's vocabulary has one owner, and a field the role does not
take is refused by name.

**What is under test.** A judgement is the caller's own answer to one role,
and the role takes a fixed set of fields. That set was written down three
times -- as the layer's dataclasses, as the API's wire models, and implicitly
in the CLI's own reader, which read the fields one by one and dropped
whatever it did not recognise. **Two spellings of one vocabulary is how the
two faces drifted:** the API refused a field the role does not take, and the
CLI accepted the same field and dropped it without a word.

The CLI's own docstring promised that it would refuse it:

    "A part that is not an object, or a part with a field the role does not
    take, is refused here: the refusal is about the command's own arguments,
    and it is the CLI's vocabulary rather than a 500 from a bad cast."

The first half was implemented and witnessed. **The second half was not
implemented anywhere**, and there was no witness for it, because there was
nothing to witness.

======================================================  =========================
     acceptance                                         witness
======================================================  =========================
the field vocabulary has one owner                     the shared module's
                                                      lists are read off the
                                                      layer's dataclasses, and
                                                      the API's wire models
                                                      take exactly those
                                                      fields
the API refuses a part with an unknown field, by      ``POST
name                                                 /roles/run-questions``
                                                      answers 422 with
                                                      ``extra_forbidden`` and
                                                      the field's name in the
                                                      location
the CLI refuses a part with an unknown field, by      ``roles run --judgements
name                                                 ...`` refuses with
                                                      ``invalid_arguments``,
                                                      and the message names
                                                      the field
a part with exactly the role's fields is still        the CLI's own reader
accepted                                             returns the layer's own
                                                      dataclass, and the
                                                      command does not refuse
                                                      the part
======================================================  =========================

**Who implements the CLI half.** This file is the contract, not the
implementation: the CLI's reader is window E's file, and the witness below
is written to be lifted into it. **The three tests to lift are the ones
whose names begin ``test_the_cli_``** — their fixtures here are this file's
own, and window E's file already has a chain to run against, so only the
assertions travel. The refusal is **expected to fail until that change
lands**, and the failure messages say what has to be true for them to go
green.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result
from fastapi.testclient import TestClient
from store_support import StoreEnv
from store_support import env as _shared_env
from typer.testing import CliRunner

from labcairn.api import create_app
from labcairn.api.contracts import (
    RoleCritiqueJudgement,
    RoleGuidanceJudgement,
    RoleRunBody,
    RoleTrajectoryJudgement,
)
from labcairn.application import ApplicationContext, create_task
from labcairn.application.judgement_fields import (
    CRITIQUE,
    GUIDANCE,
    TRAJECTORY,
    fields_taken,
    unknown_fields,
)
from labcairn.application.roles_run import (
    CritiqueJudgement,
    GuidanceJudgement,
    TrajectoryJudgement,
)
from labcairn.cli.commands import _the_judgements_from_json, app
from labcairn.cli.models import CLI_REFUSAL_INVALID_ARGUMENTS
from labcairn.cli.workspace import (
    CONFIG_SCHEMA_VERSION,
    WorkspaceConfig,
    WorkspaceLocation,
    write_config,
)
from labcairn.roles.guidance import CardClaim
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.policy import Permission, PermissionPolicy, Rule

pytestmark = pytest.mark.integration

# pytest resolves a fixture by the parameter name in a test's signature, so the
# shared `env` fixture must be bound under that name here.
env = _shared_env

#: The field a test adds to a part to make it one the role does not take.
UNKNOWN = "field_the_role_does_not_take"

#: The three parts, named as the API's body names them.
PARTS = (TRAJECTORY, GUIDANCE, CRITIQUE)


# --------------------------------------------------------------------------- #
# the payloads
# --------------------------------------------------------------------------- #


def _the_part_payload(part: str) -> dict[str, Any]:
    """A judgement part carrying **exactly** the fields the role takes.

    **Built from the vocabulary rather than written out**, so the payload and
    the vocabulary cannot disagree: a field the role takes is here, and
    nothing else is. The values are ordinary -- the roles check the values
    themselves, and this file is about the shape.
    """
    values: dict[str, Any] = {
        TRAJECTORY: {
            "issue_type": "method_and_hypothesis",
            "alignment": "partial",
            "advisor_quote": "Define the parameter",
            "note": "the change answered the wording, not the quantity.",
            "edit_action_id": "edit-201",
        },
        GUIDANCE: {
            "issue_type": "method_and_hypothesis",
            "severity": "blocking",
            "reason": "the quantity is never named",
            "suggested_next_action": "name the quantity in the methods section",
            "uncertainty_kind": "missing_measurement",
            "what_is_uncertain": "the size of the effect",
            "claims": [
                {
                    "text": "the effect was not estimated",
                    "kind": "scientific",
                    "evidence_ref": "source:0/manuscript.docx",
                    "issue_key": "LC-1",
                    "advisor_quote": "Define the parameter",
                },
            ],
            "style_notes": ["the methods section reads as a list of steps"],
        },
        CRITIQUE: {
            "verdict": "not_established",
            "repair_advice": "name the quantity and the estimate",
            "handover_reason": "the effect was never estimated",
        },
    }
    payload = values[part]
    assert set(payload) == set(fields_taken(part)), (
        f"the {part!r} payload must carry exactly the fields the role takes, "
        f"and it does not: {sorted(set(payload) ^ set(fields_taken(part)))}"
    )
    return dict(payload)


# --------------------------------------------------------------------------- #
# the environment
# --------------------------------------------------------------------------- #


def _allow_all() -> PermissionPolicy:
    """A policy that allows everything, so a test can vary one thing at a time."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """A workspace with a source directory in it."""
    root = tmp_path / "workspace"
    (root / "materials").mkdir(parents=True)
    return root


@pytest.fixture
def context(env: StoreEnv, workspace_root: Path) -> ApplicationContext:
    """A context for a task that exists."""
    store = env.store()
    created = create_task(
        store=store,
        policy=_allow_all(),
        workspace_root=workspace_root,
        title="Judgement vocabulary test task",
        goal=TaskGoal(
            objective="Establish whether the observation holds.",
            success_criterion="A cited answer, or an honest 'not established'.",
        ),
        source_dirs=(workspace_root / "materials",),
    )
    return ApplicationContext(
        workspace=created.workspace,
        store=store,
        policy=_allow_all(),
        ledger=ApprovalLedger(),
    )


@pytest.fixture
def client(context: ApplicationContext) -> Iterator[TestClient]:
    """A client for the service."""
    service = create_app(context)
    with TestClient(service) as wired:
        yield wired


@pytest.fixture
def workspace(context: ApplicationContext) -> Path:
    """A workspace the CLI can run against: its configuration, and its task.

    **The CLI reads its workspace by name**, so the configuration file is
    written here the way ``labcairn init`` writes it -- the database path
    beside the workspace, and the current task named -- so the command
    reaches its own arguments rather than stopping at the setup.
    """
    root = context.workspace.selected_root
    location = WorkspaceLocation(root=root)
    write_config(
        location,
        WorkspaceConfig(
            schema_version=CONFIG_SCHEMA_VERSION,
            database="../labcairn.db",
            source_dirs=("materials",),
            current_task=str(context.workspace.task_id),
        ),
    )
    assert location.config_path.is_file(), "the workspace carries its configuration"
    return root


# --------------------------------------------------------------------------- #
# the vocabulary has one owner
# --------------------------------------------------------------------------- #


def test_the_field_lists_are_read_off_the_layers_dataclasses() -> None:
    """The shared module's lists are the layer's dataclasses, not a second copy.

    **A module that re-spelled the fields would be a second place for the
    same answer to drift**, which is the mistake this module exists to end.
    So the witness is against the dataclasses themselves: if somebody writes
    the list out by hand and the dataclass gains a field, this goes red.
    """
    for part, dataclass_type in (
        (TRAJECTORY, TrajectoryJudgement),
        (GUIDANCE, GuidanceJudgement),
        (CRITIQUE, CritiqueJudgement),
    ):
        assert fields_taken(part) == tuple(f.name for f in fields(dataclass_type)), (
            f"the {part!r} field list must be the layer's dataclass's own fields: "
            f"{fields_taken(part)} is not "
            f"{tuple(f.name for f in fields(dataclass_type))}"
        )


def test_the_api_models_take_exactly_the_fields_the_layer_takes() -> None:
    """The API's wire models take the layer's fields, and no others.

    **This is the drift the two faces had.** The API's models are a spelling
    of the layer's dataclasses for the wire, so a field in one and not the
    other is a caller that is refused by one surface and accepted by the
    other. The comparison is made both ways: a field the layer takes and the
    API drops is as much a drift as one the API takes and the layer does not.
    """
    for part, model in (
        (TRAJECTORY, RoleTrajectoryJudgement),
        (GUIDANCE, RoleGuidanceJudgement),
        (CRITIQUE, RoleCritiqueJudgement),
    ):
        taken = fields_taken(part)
        assert tuple(model.model_fields) == taken, (
            f"the API's {part!r} model takes {tuple(model.model_fields)}, and "
            f"the layer's dataclass takes {taken}. The wire model is a "
            "spelling of the layer's dataclass, and the two must not drift: "
            "a field one takes and the other does not is a caller the API "
            "refuses and the CLI accepts."
        )


def test_unknown_fields_reports_what_a_part_does_not_take() -> None:
    """The helper says which fields a payload carries that the part does not.

    **The order is the payload's own**, so a caller is told about the fields
    in the order it wrote them, and a part that takes every field the
    payload carries has none.
    """
    payload = _the_part_payload(TRAJECTORY)
    assert unknown_fields(TRAJECTORY, payload) == ()
    assert unknown_fields(TRAJECTORY, {**payload, UNKNOWN: "surprise"}) == (UNKNOWN,)
    assert unknown_fields(TRAJECTORY, {UNKNOWN: "surprise", "also_new": 1}) == (
        UNKNOWN,
        "also_new",
    )


def test_a_part_this_module_does_not_know_has_no_vocabulary() -> None:
    """An unrecognised part name is a different question, and is not answered here.

    **Whether the part exists at all** is the layer's question, and the
    layer answers it by name. Refusing a payload for a part this module does
    not know would be refusing it for a reason that has nothing to do with
    the fields in it.
    """
    assert unknown_fields("astronomer", {"anything": 1}) == ()


# --------------------------------------------------------------------------- #
# the API refuses a part with a field the role does not take
# --------------------------------------------------------------------------- #


def _the_api_body(part: str, payload: dict[str, Any]) -> dict[str, Any]:
    """One role-loop request, with the part the test wrote."""
    return {
        "roles": [part],
        "project_id": "proj-1",
        "issue_key": "LC-1",
        part: payload,
    }


@pytest.mark.parametrize("part", PARTS)
def test_the_api_refuses_a_part_with_a_field_the_role_does_not_take(
    client: TestClient, part: str
) -> None:
    """The API names the field it will not accept, and answers 422.

    **The refusal is the wire model's own**: ``extra="forbid"`` turns a
    field the role does not take into a validation error, and the error
    names the field in its location. The status is 422 -- FastAPI's own
    answer to a body that does not validate -- and the body is its
    ``detail`` list, which is *not* the layer's ``{"reason", "message"}``
    shape. That difference is real and is reported in the hand-over note.
    """
    token = str(client.get("/session").json()["token"])
    payload = {**_the_part_payload(part), UNKNOWN: "surprise"}
    response = client.post(
        "/roles/run-questions",
        json=_the_api_body(part, payload),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422, (
        f"the API must refuse a {part!r} part carrying a field the role does "
        f"not take, and it answered {response.status_code}: {response.text}"
    )
    detail = response.json()["detail"]
    forbidden = [
        entry
        for entry in detail
        if entry.get("type") == "extra_forbidden" and entry.get("loc") == ["body", part, UNKNOWN]
    ]
    assert forbidden, (
        f"the API's refusal must name the offending field, so a caller can "
        f"see what was wrong. It answered: {json.dumps(detail)}"
    )


@pytest.mark.parametrize("part", PARTS)
def test_the_api_accepts_a_part_with_exactly_the_roles_fields(part: str) -> None:
    """A part carrying exactly the role's fields is accepted by the API.

    **The refusal must not be over-broad.** A guard that refused everything
    would satisfy the other test, so this one asserts the other direction:
    the same body, without the extra field, validates.
    """
    body = _the_api_body(part, _the_part_payload(part))
    validated = RoleRunBody.model_validate(body)
    assert getattr(validated, part) is not None, (
        f"the API's body must carry the {part!r} judgement it was given"
    )


# --------------------------------------------------------------------------- #
# the CLI refuses a part with a field the role does not take
# --------------------------------------------------------------------------- #


def _run_roles(workspace: Path, part: str, payload: dict[str, Any]) -> Result:
    """One run of ``roles run``, carrying the part the test wrote.

    **The runner is the in-process one**, because the point of this witness
    is what the command *does* with the part, and that has to be observed
    where the command runs. ``--json`` is passed because the refusal is
    machine-readable only in that form.
    """
    outcome = CliRunner().invoke(
        app,
        [
            "--workspace",
            str(workspace),
            "roles",
            "run",
            "--json",
            "--role",
            part,
            "--project",
            "proj-1",
            "--issue-key",
            "LC-1",
            "--judgements",
            json.dumps({part: payload}),
        ],
    )
    assert outcome.exit_code != 0, f"the command was expected to refuse: {outcome.stdout}"
    return outcome


def _the_refusal(outcome: Result) -> dict[str, Any]:
    """The refusal the command answered with, as the machine reads it."""
    assert outcome.stdout.strip(), (
        "the command refused without saying anything a machine can read: "
        f"stderr was {outcome.stderr!r} and the exception was "
        f"{outcome.exception!r}"
    )
    refusal: dict[str, Any] = json.loads(outcome.stdout)
    return refusal


@pytest.mark.parametrize("part", PARTS)
def test_the_cli_refuses_a_part_with_a_field_the_role_does_not_take(
    workspace: Path, part: str
) -> None:
    """The CLI refuses a part carrying a field the role does not take, by name.

    **This is the half that window E implements.** The reader is
    :func:`labcairn.cli.commands._the_judgements_from_json`, and it is where
    the docstring says the refusal belongs: "the refusal is about the
    command's own arguments, and it is the CLI's vocabulary rather than a
    500 from a bad cast."

    The refusal must therefore:

    * carry the reason ``invalid_arguments`` -- the CLI's own reason for a
      command whose arguments are wrong, and the one the sibling refusal
      (a part that is not an object) already uses;
    * name the offending field in its message, so a caller can see *what*
      was wrong and not only that something was.

    **The vocabulary comes from one place**:
    :func:`labcairn.application.judgement_fields.unknown_fields` reads the
    layer's dataclasses, so the CLI is not carrying a list of its own.
    """
    payload = {**_the_part_payload(part), UNKNOWN: "surprise"}
    refusal = _the_refusal(_run_roles(workspace, part, payload))
    assert refusal["reason"] == CLI_REFUSAL_INVALID_ARGUMENTS, (
        "the CLI must refuse a judgement part that carries a field the role "
        f"does not take, and it must refuse it as a problem with the "
        f"command's own arguments: reason {CLI_REFUSAL_INVALID_ARGUMENTS!r}, "
        f"not {refusal['reason']!r}. The refusal belongs in the CLI's own "
        "reader (_the_judgements_from_json), which is where the docstring "
        "says it belongs, and the field's vocabulary comes from "
        "labcairn.application.judgement_fields.unknown_fields."
    )
    assert UNKNOWN in refusal["message"], (
        f"the refusal must name the field the role does not take, so a "
        f"caller can see what was wrong: the message must contain "
        f"{UNKNOWN!r}. The message is the human half of the refusal, and the "
        f"field's name is what the human needs. The message was: "
        f"{refusal['message']!r}"
    )


@pytest.mark.parametrize("part", PARTS)
def test_a_part_with_exactly_the_roles_fields_is_accepted(part: str) -> None:
    """A part carrying exactly the role's fields is still accepted.

    **The refusal must not be over-broad.** A guard that refused everything
    would satisfy the test above, so this one asserts the other direction:
    the reader turns the part into the layer's own dataclass, with the
    values the caller wrote and nothing invented.
    """
    payload = _the_part_payload(part)
    judgements = _the_judgements_from_json(json.dumps({part: payload}), as_json=True)
    assert set(judgements) == {part}, (
        f"the reader must answer with the {part!r} judgement it was given, "
        f"and it answered with {sorted(judgements)}"
    )
    assert judgements[part] == _the_expected_judgement(part, payload), (
        f"the reader must turn the {part!r} part into the layer's own "
        f"dataclass, with the caller's values: it answered "
        f"{judgements[part]!r}"
    )


def _the_expected_judgement(part: str, payload: dict[str, Any]) -> Any:
    """The dataclass the reader is expected to answer with."""
    if part == TRAJECTORY:
        return TrajectoryJudgement(
            issue_type=payload["issue_type"],
            alignment=payload["alignment"],
            advisor_quote=payload["advisor_quote"],
            note=payload["note"],
            edit_action_id=payload["edit_action_id"],
        )
    if part == GUIDANCE:
        return GuidanceJudgement(
            issue_type=payload["issue_type"],
            severity=payload["severity"],
            reason=payload["reason"],
            suggested_next_action=payload["suggested_next_action"],
            uncertainty_kind=payload["uncertainty_kind"],
            what_is_uncertain=payload["what_is_uncertain"],
            claims=tuple(
                CardClaim(
                    text=claim["text"],
                    kind=claim["kind"],
                    evidence_ref=claim["evidence_ref"],
                    issue_key=claim["issue_key"],
                    advisor_quote=claim["advisor_quote"],
                )
                for claim in payload["claims"]
            ),
            style_notes=tuple(payload["style_notes"]),
        )
    return CritiqueJudgement(
        verdict=payload["verdict"],
        repair_advice=payload["repair_advice"],
        handover_reason=payload["handover_reason"],
    )


@pytest.mark.parametrize("part", PARTS)
def test_the_cli_does_not_refuse_a_part_that_takes_the_roles_fields(
    workspace: Path, part: str
) -> None:
    """The command does not refuse a part the role takes.

    **The over-broad guard.** A reader that refused every part would pass
    the refusal above and break every caller. So the command is run with a
    part that takes exactly the role's fields, and the refusal it answers
    is not the one about an unknown field.
    """
    payload = _the_part_payload(part)
    refusal = _the_refusal(_run_roles(workspace, part, payload))
    assert UNKNOWN not in refusal["message"], (
        "the CLI must not refuse a judgement part that carries exactly the "
        "fields the role takes. It refused with: "
        f"{refusal['message']!r}"
    )
    assert refusal["reason"] != CLI_REFUSAL_INVALID_ARGUMENTS, (
        "the CLI must not answer a part that takes exactly the role's fields "
        f"with {CLI_REFUSAL_INVALID_ARGUMENTS!r}; the part is well formed, "
        "and the refusal that follows is about the request around it. It "
        f"answered {refusal['reason']!r}: {refusal['message']!r}"
    )
