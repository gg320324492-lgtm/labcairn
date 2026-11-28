"""The door to ``verified_by_rule``: what the rule's pass does, and what it refuses.

**What this file watches.** The record
``docs/acceptance/LC-P4-PILOT-verified-by-rule-unreachable-2026-11-28.md``
measured that ``labcairn.evidence.store.advance`` -- the store's only writer of
``verified_by_rule`` -- had no caller in the product, so no surface could put a
record in that state and half of the evidence machinery described a state
nothing could reach. The owner chose the record's option A: a verify surface
calling ``advance``. This file is the behavioural witness of that decision, and
each test is a property the door must hold:

**A pass moves the record, and the status is the residue of a check that ran.**
The check is evaluated against the ledger's own anchors and its verdict is in
the log; the status is ``verified_by_rule`` only because the verdict was a
pass.

**A check that does not pass does not move the record.** The verdict is still
committed -- it is evidence, and the store appends it before it judges the
move -- and the refusal names the outcome and the detail. "The quotation did
not match" and "the claim was verified" cannot be the same state.

**Only C1, C2 and C3 can verify.** C4 is a person's attestation's entry, whose
only outcome is ``not_checked``; asking for it is refused with the reason
rather than sent into a move that could only fail.

**A record the task does not hold is refused.** A context bound to one task
may not move another task's record into a state a report cites.

**The report's gate treats the status as citable beside an attestation.** A
task holding one ``verified_by_rule`` record and one ``user_attested`` record
passes the gate after the rule's move and fails before it, with the status
finding naming the unverified claim -- so the gate's verdict is about the
status the door produced, not about a status that was always there.

**The surfaces reach it.** The CLI's ``task claim-verify`` and the API's
``POST /records/{id}/verify`` call the layer's operation, and the rules a
person reaches (ids, exit codes, response bodies) are the ones a person meets.

The static half of the same property -- that the operation is the one caller
of the store's writer, and that no surface writes the status itself -- is
``tests/test_surface_status_reach.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from store_support import StoreEnv
from store_support import env as _shared_env
from test_application_evidence import _an_address, _context, _source_id, _write_the_material
from test_cli_evidence_writer import _addresses, _ingest
from test_cli_support import (
    _context as _cli_context,
)
from test_cli_support import (
    material as _material_fixture,
)
from test_cli_support import (
    run_cli,
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

from labcairn.api import create_app
from labcairn.application import (
    ApplicationContext,
    ApplicationRefusal,
    ApplicationRefusedError,
    ClaimRequest,
    attest_claim,
    record_claim,
    record_model_proposal,
    verify_claim,
)
from labcairn.cli.commands import EXIT_REFUSED
from labcairn.db.repository import events_after
from labcairn.evidence.gate import evaluate_task
from labcairn.evidence.index import LabCairnIndex
from labcairn.evidence.states import (
    CheckKind,
    CheckOutcome,
    EvidenceKind,
    VerificationStatus,
)
from labcairn.evidence.store import load_record
from labcairn.runtime.event import EventStreamPage, EventStreamRequest

env = _shared_env
material = _material_fixture
source_id = _source_id_fixture
task_id = _task_id_fixture
workspace = _workspace_fixture

#: The instant the writes are dated with, as the application tests date theirs.
_MOMENT_AT = datetime(2026, 1, 1, tzinfo=UTC)

#: The origin the service's own guard accepts.
_OWN_ORIGIN = "http://127.0.0.1:8000"


class _StoreEventSource:
    """The event source the service's host gives it.

    It reads the store's event log, which is what the port is for; the API
    package may not reach the store, so the host supplies this. It keeps no
    session: the caller hands it one per read. Two other test files define the
    same small adapter for the same reason -- it is the host's half of the
    port, not the service's.
    """

    def page(self, session: Session, request: EventStreamRequest) -> EventStreamPage:
        """The events after the request's cursor, and the cursor to resume from."""
        events = events_after(
            session, request.task_id, after_seq=request.after_seq, limit=request.limit
        )
        return EventStreamPage(
            task_id=request.task_id,
            events=events,
            next_after_seq=events[-1].seq if events else request.after_seq,
            caught_up=len(events) < request.limit,
        )


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """A workspace with the two materials the claims are read from."""
    root = tmp_path / "workspace"
    (root / "materials").mkdir(parents=True)
    return root


def _a_numeric_claim(context: ApplicationContext) -> str:
    """Record a numeric claim over the CSV cell ``2``, and return its id.

    The value is the cell's own, so C3 re-reads the address and passes -- the
    record is a claim back to which a rule can hold the ledger.
    """
    csv_id = _source_id(context, "groups.csv")
    locator_key, _ = _an_address(context, csv_id, predicate=lambda a: a.text.strip() == "2")
    recorded = record_claim(
        context,
        ClaimRequest(
            source_id=csv_id,
            locator_key=locator_key,
            kind=EvidenceKind.NUMERIC,
            value=2.0,
            unit="dimensionless",
            tolerance=0.0,
        ),
        now=_MOMENT_AT,
    )
    return str(recorded.record.evidence_id)


def _a_quotation_claim(context: ApplicationContext) -> str:
    """Record a quotation claim over the note's sentence, and return its id."""
    notes_id = _source_id(context, "notes.md")
    locator_key, text = _an_address(
        context, notes_id, predicate=lambda a: a.text.strip().startswith("The yield")
    )
    recorded = record_claim(
        context,
        ClaimRequest(source_id=notes_id, locator_key=locator_key, text=text.strip()),
        now=_MOMENT_AT,
    )
    return str(recorded.record.evidence_id)


def _assert_refused(
    call: Callable[[], object], reason: ApplicationRefusal
) -> ApplicationRefusedError:
    with pytest.raises(ApplicationRefusedError) as caught:
        call()
    assert caught.value.reason is reason
    return caught.value


# --------------------------------------------------------------------------- #
# the operation
# --------------------------------------------------------------------------- #


@pytest.mark.integration
def test_a_rules_pass_moves_the_record_to_verified_by_rule(
    env: StoreEnv, workspace_root: Path
) -> None:
    """C3 runs, its pass is logged, and the status is the pass's residue.

    The assertion is threefold on purpose: the status, the log entry, and a
    fresh read of the row. A status written without a verdict would be the
    assertion ``advance`` refuses to let anyone make, and a verdict without
    the move would be a check that changed nothing.
    """
    _write_the_material(workspace_root)
    context = _context(env, workspace_root)
    evidence_id = _a_numeric_claim(context)

    verified = verify_claim(context, evidence_id, check=CheckKind.C3, now=_MOMENT_AT)

    assert verified.check is CheckKind.C3
    assert verified.record.status is VerificationStatus.VERIFIED_BY_RULE
    entry = verified.record.verification_log[-1]
    assert entry.check is CheckKind.C3, "the entry the operation appended is the check asked for"
    assert entry.outcome is CheckOutcome.PASS

    fresh = load_record(context.store.session.connection(), evidence_id)
    assert fresh is not None
    assert fresh.status is VerificationStatus.VERIFIED_BY_RULE, (
        "the move must be committed, not only returned"
    )


@pytest.mark.integration
def test_a_check_that_does_not_pass_is_refused_and_does_not_move(
    env: StoreEnv, workspace_root: Path
) -> None:
    """C3 on a quotation finds no number, and the refusal says so.

    The verdict is *committed*: the store appends it before it judges the
    move, and the layer commits it because it is evidence. What does not
    happen is the move. The message carries the outcome and the detail, so a
    person can tell a failed check from a refused transition.
    """
    _write_the_material(workspace_root)
    context = _context(env, workspace_root)
    evidence_id = _a_quotation_claim(context)

    error = _assert_refused(
        lambda: verify_claim(context, evidence_id, check=CheckKind.C3, now=_MOMENT_AT),
        ApplicationRefusal.VERIFICATION_REFUSED,
    )

    assert "indeterminate" in str(error), f"the refusal must carry the check's verdict: {error}"
    fresh = load_record(context.store.session.connection(), evidence_id)
    assert fresh is not None
    assert fresh.status is VerificationStatus.EXTRACTED, (
        "a check that did not pass moved the record"
    )
    last = fresh.verification_log[-1]
    assert last.check is CheckKind.C3
    assert last.outcome is CheckOutcome.INDETERMINATE, (
        "the verdict that refused the move must stay in the log"
    )


@pytest.mark.integration
def test_c4_cannot_verify_and_the_record_is_untouched(env: StoreEnv, workspace_root: Path) -> None:
    """C4 is a person's entry, never a pass; the request is refused up front.

    The refusal is ``arguments_invalid`` rather than the store's transition
    refusal: C4 is not a rule that could verify, so the caller is told the
    vocabulary rather than sent into a move whose precondition could never
    hold. Nothing is written -- not even a log entry -- because no check ran.
    """
    _write_the_material(workspace_root)
    context = _context(env, workspace_root)
    evidence_id = _a_numeric_claim(context)

    _assert_refused(
        lambda: verify_claim(context, evidence_id, check=CheckKind.C4, now=_MOMENT_AT),
        ApplicationRefusal.ARGUMENTS_INVALID,
    )

    fresh = load_record(context.store.session.connection(), evidence_id)
    assert fresh is not None
    assert fresh.status is VerificationStatus.EXTRACTED
    assert fresh.verification_log == (), "a refused request must not have run a check"


@pytest.mark.integration
def test_a_models_proposal_cannot_be_verified_from_planned(
    env: StoreEnv, workspace_root: Path
) -> None:
    """A proposal is ``planned``; Contract 2 has no edge from there to the status.

    The proposal's route to a citable state is a person's own record
    (``confirm_proposal``), not a rule's pass. The refusal names the
    transition, and nothing is appended, because the store refuses before it
    runs a check.
    """
    _write_the_material(workspace_root)
    context = _context(env, workspace_root)
    csv_id = _source_id(context, "groups.csv")
    locator_key, _ = _an_address(context, csv_id, predicate=lambda a: a.text.strip() == "2")
    proposal = record_model_proposal(
        context,
        ClaimRequest(
            source_id=csv_id,
            locator_key=locator_key,
            kind=EvidenceKind.NUMERIC,
            value=2.0,
            unit="dimensionless",
        ),
        creator_id="test:model",
        now=_MOMENT_AT,
    )
    assert proposal.record.status is VerificationStatus.PLANNED

    error = _assert_refused(
        lambda: verify_claim(
            context, proposal.record.evidence_id, check=CheckKind.C3, now=_MOMENT_AT
        ),
        ApplicationRefusal.VERIFICATION_REFUSED,
    )

    assert "planned" in str(error)
    fresh = load_record(context.store.session.connection(), proposal.record.evidence_id)
    assert fresh is not None
    assert fresh.status is VerificationStatus.PLANNED
    assert fresh.verification_log == ()


@pytest.mark.integration
def test_another_tasks_record_is_refused_as_not_held(env: StoreEnv, workspace_root: Path) -> None:
    """A context bound to one task may not verify another task's record.

    The refusal is ``evidence_not_found`` rather than a distinct "not your
    task": a context that learned the difference could probe another task's
    ledger, and the operation's answer to "is this record mine" is the same
    answer it gives to "does it exist".
    """
    _write_the_material(workspace_root)
    context = _context(env, workspace_root)
    evidence_id = _a_numeric_claim(context)
    other = _context(env, workspace_root)
    assert other.task_id != context.task_id

    _assert_refused(
        lambda: verify_claim(other, evidence_id, check=CheckKind.C3, now=_MOMENT_AT),
        ApplicationRefusal.EVIDENCE_NOT_FOUND,
    )

    fresh = load_record(context.store.session.connection(), evidence_id)
    assert fresh is not None
    assert fresh.status is VerificationStatus.EXTRACTED


@pytest.mark.integration
def test_the_report_gate_cites_the_rule_verified_record_beside_the_attested_one(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The status is what flips the gate, and both citable states are cited.

    Before the rule's pass the task holds an ``extracted`` claim, and the gate
    refuses the set with a status finding naming it. After the pass the gate
    accepts the set and its ``citable`` tuple holds the rule-verified record
    **and** the person-attested one -- the two statuses the vocabulary has
    called citable all along, now both reachable from the product.
    """
    _write_the_material(workspace_root)
    context = _context(env, workspace_root)
    verified_id = _a_numeric_claim(context)
    attested_id = _a_quotation_claim(context)
    attested = attest_claim(
        context,
        attested_id,
        user_id="the-advisor",
        note="I read it against the note.",
        now=_MOMENT_AT,
    )
    assert attested.record.status is VerificationStatus.USER_ATTESTED

    first_connection = context.store.session.connection()
    before = evaluate_task(
        first_connection,
        task_id=str(context.task_id),
        index=LabCairnIndex(first_connection),
    )
    assert not before.passed, "an extracted claim must keep the gate closed"
    assert any(finding.evidence_id == verified_id for finding in before.findings)

    # ``verify_claim`` commits, and a commit ends the transaction the previous
    # connection was bound to; the gate is asked again on a fresh one.
    verify_claim(context, verified_id, check=CheckKind.C3, now=_MOMENT_AT)

    connection = context.store.session.connection()
    after = evaluate_task(connection, task_id=str(context.task_id), index=LabCairnIndex(connection))
    assert after.passed, [finding.reason for finding in after.findings]
    assert set(after.citable) == {verified_id, attested_id}, (
        "both the rule's pass and the person's attestation must be citable"
    )


# --------------------------------------------------------------------------- #
# the surfaces
# --------------------------------------------------------------------------- #


@pytest.mark.e2e
def test_task_claim_verify_moves_the_claim_through_the_console(
    workspace: Path, task_id: str, material: Path
) -> None:
    """The whole path a person types: record, check, and the status with its verdict.

    The console script is the surface under test, so the claim is recorded
    through it as well. The JSON is the layer's own result model -- the same
    bytes the API returns -- so the assertion on ``check`` and the log entry
    is an assertion on the product's contract, not on the command's wording.
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
        "--tolerance",
        "0",
        "--json",
    )
    assert claimed.returncode == 0, claimed.stderr
    evidence_id = str(claimed.json()["record"]["evidence_id"])

    verified = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "claim-verify",
        evidence_id,
        "--check",
        "c3",
        "--json",
    )

    assert verified.returncode == 0, verified.stderr
    record = verified.json()["record"]
    assert record["status"] == "verified_by_rule"
    assert verified.json()["check"] == "c3"
    assert record["verification_log"][-1]["check"] == "c3"
    assert record["verification_log"][-1]["outcome"] == "pass"


@pytest.mark.e2e
def test_task_claim_verify_refuses_a_check_it_does_not_run(
    workspace: Path, task_id: str, material: Path
) -> None:
    """An unknown ``--check`` is the CLI's own refusal, and the record is untouched.

    The vocabulary is closed at the console because the operator typed the
    word; the layer would refuse it too, but a surface that sent ``--check
    c9`` to the ledger would be a surface that made the ledger answer for the
    operator's typo. The exit code and the reason are the CLI's, and the
    record's status proves nothing ran.
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
        "--tolerance",
        "0",
        "--json",
    )
    assert claimed.returncode == 0, claimed.stderr
    evidence_id = str(claimed.json()["record"]["evidence_id"])

    refused = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "claim-verify",
        evidence_id,
        "--check",
        "c9",
        "--json",
    )

    assert refused.returncode == EXIT_REFUSED
    assert refused.json()["reason"] == "invalid_arguments"

    with _cli_context(workspace, task_id) as context:
        fresh = load_record(context.store.session.connection(), evidence_id)
    assert fresh is not None
    assert fresh.status is VerificationStatus.EXTRACTED


@pytest.mark.e2e
def test_the_verify_route_moves_the_record_the_layer_holds(
    env: StoreEnv, workspace_root: Path
) -> None:
    """``POST /records/{id}/verify`` runs the rule and writes the status.

    The route is the layer's operation and the layer's result: the response
    body is the same model the CLI's ``--json`` prints, and a fresh read of
    the store through the layer shows the status. C4 is refused through the
    same door with the layer's refusal body, so an API caller sees one
    vocabulary for every refusal.
    """
    _write_the_material(workspace_root)
    context = _context(env, workspace_root)
    evidence_id = _a_numeric_claim(context)

    app = create_app(context, event_source=_StoreEventSource())
    with TestClient(app) as client:
        token = client.get("/session").json()["token"]
        headers = {"Origin": _OWN_ORIGIN, "Authorization": f"Bearer {token}"}

        verified = client.post(
            f"/records/{evidence_id}/verify",
            json={"check": "c3"},
            headers=headers,
        )
        assert verified.status_code == 200, verified.text
        body = verified.json()
        assert body["check"] == "c3"
        assert body["record"]["status"] == "verified_by_rule"
        assert body["record"]["verification_log"][-1]["outcome"] == "pass"

        # C4 is not a rule that verifies; the layer's refusal is the body.
        refused = client.post(
            f"/records/{evidence_id}/verify",
            json={"check": "c4"},
            headers=headers,
        )
        assert refused.status_code == 403, refused.text
        payload = refused.json()
        assert payload["reason"] == "arguments_invalid"
        assert "c4" in payload["message"]

    fresh = load_record(context.store.session.connection(), evidence_id)
    assert fresh is not None
    assert fresh.status is VerificationStatus.VERIFIED_BY_RULE
