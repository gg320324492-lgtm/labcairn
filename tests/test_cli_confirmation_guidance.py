"""`tests/test_cli.py`'s section, split out for the shard partition.

The section is byte-identical to the monolith's; the rig comes from
`test_cli_support`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from test_cli_evidence_writer import _addresses, _ingest
from test_cli_support import (
    _MOMENT,
    CliResult,
    _context,
    run_cli,
)
from test_cli_support import (
    material as _material_fixture,
)
from test_cli_support import (
    source_id as _source_id_fixture,
)
from test_cli_support import (
    task_id as _task_id_fixture,
)
from test_cli_support import (
    workspace as _workspace_fixture,
)

from labcairn.application import (
    RuleDraft,
    read_guidance_rule,
    write_guidance_counterexample,
    write_guidance_rule_version,
)
from labcairn.cli.commands import EXIT_REFUSED, RULE_VERDICTS
from labcairn.cli.workspace import application_context, locate, read_config
from labcairn.core.ids import TaskId
from labcairn.guidance.checks import bind_check, confirm_check, propose_check

material = _material_fixture
source_id = _source_id_fixture
task_id = _task_id_fixture
workspace = _workspace_fixture


material = _material_fixture
source_id = _source_id_fixture
task_id = _task_id_fixture
workspace = _workspace_fixture

pytestmark = pytest.mark.e2e


# --------------------------------------------------------------------------- #
# the confirmation door, through the console script
# --------------------------------------------------------------------------- #


def test_task_claim_attest_puts_a_person_behind_the_claim(
    workspace: Path, task_id: str, material: Path
) -> None:
    """The attestation is reached through the console script, and the JSON says who.

    **The claim is recorded through the CLI too**, so the whole path a person
    types is the path under test: record, attest, and the record is
    ``user_attested`` with the attester's name on it.
    """
    source_id = _ingest(workspace)
    address = next(item for item in _addresses(workspace, source_id) if item["text"].strip() == "2")

    claimed = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "claim",
        "--source",
        source_id,
        "--address",
        address["locator_key"],
        "--kind",
        "numeric",
        "--value",
        "2",
        "--unit",
        "dimensionless",
        "--json",
    )
    assert claimed.returncode == 0, claimed.stderr
    evidence_id = str(claimed.json()["record"]["evidence_id"])

    attested = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "claim-attest",
        evidence_id,
        "--user",
        "the-advisor",
        "--note",
        "I read it against the table.",
        "--json",
    )

    assert attested.returncode == 0, attested.stderr
    record = attested.json()["record"]
    assert record["status"] == "user_attested"
    assert record["created_by"] == "user"
    assert attested.json()["user_id"] == "the-advisor"


def test_task_proposal_confirm_settles_a_models_proposal_through_the_console(
    workspace: Path, task_id: str, material: Path
) -> None:
    """The settlement is reached through the console script.

    **The proposal is written by the layer, not by the console**, because the
    console has no command that records a model's answer — the model path is
    code, and the operator's half is this command. So the proposal is put in
    the ledger the way the pilot's own request puts it there, and the
    settlement is the one thing under test.
    """
    from uuid import UUID

    from labcairn.application import ClaimRequest, record_model_proposal
    from labcairn.evidence.states import EvidenceKind

    source_id = _ingest(workspace)
    address = next(item for item in _addresses(workspace, source_id) if item["text"].strip() == "2")

    location = locate(workspace)
    config = read_config(location)
    with application_context(location, config, TaskId(UUID(config.current_task))) as context:
        proposed = record_model_proposal(
            context,
            ClaimRequest(
                source_id=source_id,
                locator_key=address["locator_key"],
                kind=EvidenceKind.CLAIM,
                text="The value reads 2.",
            ),
        )
    proposal_id = str(proposed.record.evidence_id)

    settled = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "proposal-confirm",
        proposal_id,
        "--verdict",
        "confirmed",
        "--user",
        "the-advisor",
        "--json",
    )

    assert settled.returncode == 0, settled.stderr
    body = settled.json()
    assert body["verdict"] == "confirmed"
    assert body["user_id"] == "the-advisor"
    assert body["confirmation"]["status"] == "user_attested"
    assert body["confirmation"]["created_by"] == "user"
    assert body["proposal"]["superseded_by"] == body["confirmation"]["evidence_id"]


def test_task_claim_attest_refuses_an_id_that_is_not_an_evidence_id(
    workspace: Path, task_id: str
) -> None:
    """The command's own refusal, before it reaches the layer.

    **An id that is not an evidence id is refused by the command**, with the
    same sentence the command's own argument check writes — and the layer
    never sees it, so nothing is written.
    """
    refused = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "claim-attest",
        "not-an-id",
        "--user",
        "the-advisor",
        "--note",
        "I read it.",
    )

    assert refused.returncode != 0, refused.stdout
    assert "is not a claim id" in refused.stderr
    assert "claim ids are UUIDv7" in refused.stderr


def test_task_proposal_confirm_refuses_an_id_that_is_not_a_proposal_id(
    workspace: Path, task_id: str
) -> None:
    """The command's own refusal, before it reaches the layer.

    **One witness watches one refusal**, so the two commands' sentences
    differ: a witness that quoted one of them would otherwise watch both.
    """
    refused = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "proposal-confirm",
        "not-an-id",
        "--verdict",
        "confirmed",
        "--user",
        "the-advisor",
        "--note",
        "I read it.",
    )

    assert refused.returncode != 0, refused.stdout
    assert "is not a proposal id" in refused.stderr
    assert "proposal ids are UUIDv7" in refused.stderr


# --------------------------------------------------------------------------- #
# the guidance door
# --------------------------------------------------------------------------- #


@pytest.fixture
def rule_id(workspace: Path, task_id: str) -> str:
    """A candidate rule in the memory, proposed by a distillation run.

    **Written through the layer, and not through the console**, because the
    console's half of the door is the settling and not the proposing: a
    candidate is what the memory holds until a person says otherwise, and
    the rule under test is a candidate.

    **It carries a case against it**, because a rule the door serves without
    its cases would be a rule served as though it were the whole truth — and
    a witness that only ever saw a rule with nothing against it would not
    notice.
    """
    with _context(workspace, task_id) as context:
        rule = write_guidance_rule_version(
            context,
            RuleDraft(
                rule_id="rule-1",
                version=1,
                issue_type="figures",
                statement="A figure's caption states what the axes are.",
                rule_context="A figure a reader cannot read without the caption.",
                scope="Every figure in the group's papers.",
                example="The figure of 2026-03-11.",
                proposed_by="distil-run-7",
                sources=("iss-gold-a-r1",),
                proposed_at=_MOMENT,
            ),
        )
        write_guidance_counterexample(
            context,
            rule_id=rule.rule_id,
            statement="The figure of 2026-03-20 carried its unit in the axis label.",
            recorded_by="reader-2",
            recorded_at=_MOMENT,
            issue_key="iss-gold-a-r2",
        )
    return rule.rule_id


def _settle(
    workspace: Path,
    rule_id: str,
    *,
    verdict: str,
    user: str,
    reason: str | None = None,
    as_json: bool = True,
) -> CliResult:
    """Run the door, the way a person types it."""
    args = [
        "--workspace",
        str(workspace),
        "guidance",
        "rule-confirm",
        rule_id,
        "--verdict",
        verdict,
        "--user",
        user,
    ]
    if reason is not None:
        args.extend(("--reason", reason))
    if as_json:
        args.append("--json")
    return run_cli(*args)


def test_the_guidance_door_confirms_a_rule_through_the_console(
    workspace: Path, task_id: str, rule_id: str
) -> None:
    """A second reader's confirmation lands, and the rule says who gave it.

    **The whole path a person types is the path under test**: the rule is a
    candidate, the reader is somebody other than the proposer, and the rule
    the console answers with is the memory's own rule — with its state, its
    scope, its source and the reader's name on it.
    """
    confirmed = _settle(workspace, rule_id, verdict="confirmed", user="the-advisor")

    assert confirmed.returncode == 0, confirmed.stderr
    body = confirmed.json()
    assert body["rule_id"] == "rule-1"
    assert body["state"] == "confirmed"
    assert body["confirmed_by"] == "the-advisor"
    assert body["proposed_by"] == "distil-run-7"
    assert body["sources"] == ["iss-gold-a-r1"]

    with _context(workspace, task_id) as context:
        stored = read_guidance_rule(context, rule_id=rule_id)
    assert stored.state == "confirmed"
    assert stored.confirmed_by == "the-advisor"


def test_the_guidance_door_refuses_the_proposer(
    workspace: Path, task_id: str, rule_id: str
) -> None:
    """The second-reader rule, at the door: one person reading twice is one reading.

    **This is the acceptance clause, at the surface a person uses.** Whoever
    proposed a rule cannot be the one who confirms it, and the refusal says
    who was missing — so the caller learns that the rule needs *another*
    reader and not merely that something went wrong.

    **And nothing is written.** The rule keeps the state it had, because a
    refusal that moved the rule would be a refusal that did the thing it
    refused.
    """
    refused = _settle(workspace, rule_id, verdict="confirmed", user="distil-run-7")

    assert refused.returncode == EXIT_REFUSED, refused.stdout
    payload = refused.json()
    assert payload["reason"] == "guidance_confirmer_is_proposer"
    assert "distil-run-7" in payload["message"]

    with _context(workspace, task_id) as context:
        stored = read_guidance_rule(context, rule_id=rule_id)
    assert stored.state == "candidate"
    assert stored.confirmed_by is None


def test_the_guidance_door_refuses_a_verdict_outside_the_vocabulary(
    workspace: Path, task_id: str, rule_id: str
) -> None:
    """The door's own vocabulary, refused before the memory is asked.

    **"The person had a look" is not a verdict a rule can carry**, so the
    command says which two words are the whole of it — and the message
    names the word it refused, because a refusal nobody can act on is the
    same as no reason at all.
    """
    refused = _settle(workspace, rule_id, verdict="maybe", user="the-advisor")

    assert refused.returncode == EXIT_REFUSED, refused.stdout
    payload = refused.json()
    assert payload["reason"] == "invalid_arguments"
    assert "is not a verdict a person can return about a rule" in payload["message"]
    assert "'maybe'" in payload["message"]
    assert "confirmed, disputed" in payload["message"]


def test_the_guidance_door_refuses_a_person_nobody_names(
    workspace: Path, task_id: str, rule_id: str
) -> None:
    """A confirmation nobody signs is not a confirmation.

    **The command refuses it before the memory is asked**, because the
    memory's own write would fail the schema's check on the row — and a
    constraint error out of the middle of a transaction is a crash, not a
    refusal.
    """
    refused = _settle(workspace, rule_id, verdict="confirmed", user="   ")

    assert refused.returncode == EXIT_REFUSED, refused.stdout
    payload = refused.json()
    assert payload["reason"] == "invalid_arguments"
    assert "a confirmation nobody signs is not a confirmation" in payload["message"]


def test_the_guidance_door_refuses_a_reason_it_cannot_keep(
    workspace: Path, task_id: str, rule_id: str
) -> None:
    """A reason belongs to a dispute, and a confirmation cannot keep one.

    **The command refuses it rather than dropping it**, because the memory
    holds no reason on a rule that stands — so a reason given with a
    confirmation would be accepted and then lost, and a person who believed
    it was recorded would be wrong.
    """
    refused = _settle(
        workspace,
        rule_id,
        verdict="confirmed",
        user="the-advisor",
        reason="I read it against the table.",
    )

    assert refused.returncode == EXIT_REFUSED, refused.stdout
    payload = refused.json()
    assert payload["reason"] == "invalid_arguments"
    assert "a reason belongs to a dispute" in payload["message"]


def test_the_guidance_door_refuses_a_rule_that_is_not_there(workspace: Path, task_id: str) -> None:
    """A rule nobody proposed is refused by name, not answered with an empty one.

    **The memory's own reason**, rendered the way the CLI renders every
    other refusal, so a caller that asked for a rule which does not exist
    learns that and not a rule that looks like a rule.
    """
    refused = _settle(workspace, "rule-nobody-proposed", verdict="confirmed", user="the-advisor")

    assert refused.returncode == EXIT_REFUSED, refused.stdout
    payload = refused.json()
    assert payload["reason"] == "guidance_rule_not_found"


def test_the_guidance_door_refuses_a_dispute_without_a_reason(
    workspace: Path, task_id: str, rule_id: str
) -> None:
    """A dispute without a reason is a shrug, and the memory refuses one.

    **The reason is the memory's business, and the refusal is the
    memory's** — the command asks it rather than ruling on the reason
    itself, so a reader learns which rule was broken and not merely that
    the command was unhappy.
    """
    refused = _settle(workspace, rule_id, verdict="disputed", user="reader-2")

    assert refused.returncode == EXIT_REFUSED, refused.stdout
    payload = refused.json()
    assert payload["reason"] == "guidance_resolution_without_reason"

    with _context(workspace, task_id) as context:
        stored = read_guidance_rule(context, rule_id=rule_id)
    assert stored.state == "candidate"


def test_the_guidance_door_disputes_a_rule_through_the_console(
    workspace: Path, task_id: str, rule_id: str
) -> None:
    """A dispute moves the rule, and the reason travels with it.

    **The dispute is not a retraction.** The rule stays in the memory, in
    the ``disputed`` state, with the case against it — and the reason the
    person gave is on the rule, because a dispute nobody can read later is
    a dispute that never happened.
    """
    disputed = _settle(
        workspace,
        rule_id,
        verdict="disputed",
        user="reader-2",
        reason="The ablation paragraph of 2026-03-09 named its baseline.",
    )

    assert disputed.returncode == 0, disputed.stderr
    body = disputed.json()
    assert body["state"] == "disputed"
    assert body["resolution_reason"] == "The ablation paragraph of 2026-03-09 named its baseline."

    with _context(workspace, task_id) as context:
        stored = read_guidance_rule(context, rule_id=rule_id)
    assert stored.state == "disputed"
    assert stored.resolution_reason is not None


def test_the_guidance_door_refuses_a_confirmation_it_has_already_given(
    workspace: Path, task_id: str, rule_id: str
) -> None:
    """A rule is confirmed once: the state machine is closed.

    **The second confirmation is refused by name**, so a reader who clicks
    twice is told that the rule is already confirmed rather than shown a
    second decision that overwrites the first.
    """
    first = _settle(workspace, rule_id, verdict="confirmed", user="the-advisor")
    assert first.returncode == 0, first.stderr

    second = _settle(workspace, rule_id, verdict="confirmed", user="reader-3")

    assert second.returncode == EXIT_REFUSED, second.stdout
    assert second.json()["reason"] == "guidance_transition_not_possible"


def test_the_guidance_door_serves_the_layers_own_rule(
    workspace: Path, task_id: str, rule_id: str
) -> None:
    """The console's ``--json`` is the memory's rule, in the API's bytes.

    **One serialization, two surfaces.** The console's machine-readable form
    is compared with the bytes the local API serves for the same rule, read
    from the same store — so a command that spelled the rule a second time
    would show here, and so would a service that spelled it differently.
    """
    from fastapi.testclient import TestClient

    from labcairn.api import create_app
    from labcairn.api.events import UnwiredEventSource

    settled = _settle(workspace, rule_id, verdict="confirmed", user="the-advisor")
    assert settled.returncode == 0, settled.stderr

    with _context(workspace, task_id) as context:
        app = create_app(context, event_source=UnwiredEventSource())
        with TestClient(app) as served:
            response = served.get(f"/guidance/rules/{rule_id}")
    assert response.status_code == 200, response.text

    assert settled.stdout.strip() == response.content.decode("utf-8")


def test_the_guidance_door_says_what_its_json_says(
    workspace: Path, task_id: str, rule_id: str
) -> None:
    """The rendered form and the machine-readable form are one answer.

    **The prose names the state, the person and the rule**, and the JSON
    says the same three — because a reader who is told one thing by the
    terminal and another by the script is being handed two answers.
    """
    settled = _settle(workspace, rule_id, verdict="confirmed", user="the-advisor", as_json=False)

    assert settled.returncode == 0, settled.stderr
    assert "confirmed" in settled.stdout
    assert "the-advisor" in settled.stdout
    assert "rule-1" in settled.stdout


def test_the_cli_and_the_route_accept_the_same_verdicts() -> None:
    """The door's vocabulary is one, and the two surfaces say the same words.

    **The console's closed vocabulary and the contract's closed type are
    compared**, because a door whose two faces disagree about what a person
    may say is a door with two vocabularies — and the console would be
    refusing a word the service accepts.
    """
    from typing import get_args

    from labcairn.api.contracts import GuidanceRuleVerdictBody

    annotation = GuidanceRuleVerdictBody.model_fields["verdict"].annotation
    assert tuple(get_args(annotation)) == RULE_VERDICTS
    assert RULE_VERDICTS == ("confirmed", "disputed")


def test_the_console_shows_the_check_that_decides_the_rule(
    workspace: Path, task_id: str, rule_id: str
) -> None:
    """**A reader handed a rule is handed the thing that decides it.**

    The machine-readable answer has carried the rule's checks for as long as
    the binding has existed; the console's own answer did not, so a person at
    a terminal read the standard and not the question that decides it. **The
    two faces of one door must not disagree about what a rule carries.**
    """
    with _context(workspace, task_id) as context:
        check = propose_check(
            context,
            question="Does the caption say what the two axes are?",
            pass_criterion="Passes when the caption names both axes and their units.",
            proposed_by="distil-run-7",
            now=_MOMENT,
        )
        confirm_check(context, check_id=check.check_id, confirmed_by="reader-2", now=_MOMENT)
        bind_check(context, rule_id=rule_id, check_id=check.check_id)

    answered = _settle(workspace, rule_id, verdict="confirmed", user="reader-2", as_json=False)

    assert answered.returncode == 0, answered.stdout
    assert "Does the caption say what the two axes are?" in answered.stdout, (
        "the console did not print the question that decides the rule:\n" + answered.stdout
    )
    assert "Passes when the caption names both axes and their units." in answered.stdout, (
        "the console did not print the criterion that answers it:\n" + answered.stdout
    )


def test_the_console_says_when_a_rule_names_no_check(
    workspace: Path, task_id: str, rule_id: str
) -> None:
    """**A rule that names no check says so** — the silence is the ambiguity.

    A reader who cannot tell "this rule has no check" from "the door dropped
    it" cannot judge the rule; the console says which it is.
    """
    answered = _settle(workspace, rule_id, verdict="confirmed", user="reader-2", as_json=False)

    assert answered.returncode == 0, answered.stdout
    assert "the rule names no check" in answered.stdout, answered.stdout
