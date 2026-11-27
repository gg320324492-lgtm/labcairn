"""The evidence gate is the door a report goes through, and it is witnessed here.

The gate's own rules are `tests/test_evidence_gate.py`'s to hold. What this
file holds is the seam the last batch found open: **no surface ran the gate
before a report said something.** The report operation now does, in one place
(`labcairn.application.reports.render_report`), so the CLI and the API inherit
one answer rather than each spelling its own. These tests run the console
script the way a person does, over a ledger assembled from the product's own
operations, and assert what the two surfaces' one operation does.

**The scope is part of the property and is witnessed as such.** The gate
judges the records the document states as *established* — the claims whose
status the report does not qualify. The report carries other records with
their status printed beside them (an ``extracted`` claim says so), and it does
not carry planned or superseded records at all. The tests below pin all three
sides of that: a labelled record does not refuse the report, a record the
report does not carry does not refuse it, and a record the report does state
as established and the gate refuses does refuse it.

Every ledger state here is built in a scratch workspace under the registered
temp area, from a synthetic material of the tests' own. No pilot material is
read and no model request is made.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from test_cli_support import _context, run_cli
from test_cli_support import (
    material as _material_fixture,
)
from test_cli_support import (
    task_id as _task_id_fixture,
)
from test_cli_support import (
    workspace as _workspace_fixture,
)

from labcairn.cli.commands import EXIT_REFUSED
from labcairn.core.ids import new_id
from labcairn.evidence.index import LabCairnIndex
from labcairn.evidence.record import EvidenceRecord
from labcairn.evidence.states import (
    CheckKind,
    EvidenceCreator,
    EvidenceKind,
    VerificationStatus,
)
from labcairn.evidence.store import advance, append_record

workspace = _workspace_fixture
task_id = _task_id_fixture
material = _material_fixture

pytestmark = pytest.mark.e2e


# --------------------------------------------------------------------------- #
# the rig: a workspace the CLI made, and the writes the CLI has no command for
# --------------------------------------------------------------------------- #


def _ingest(workspace: Path) -> str:
    """Ingest the material through the CLI, and return the one source's id."""
    result = run_cli("--workspace", str(workspace), "sources", "ingest", "--json")
    assert result.returncode == 0, result.stderr
    source_ids = result.json()["source_ids"]
    assert len(source_ids) == 1, source_ids
    return str(source_ids[0])


def _the_address_whose_text_is(workspace: Path, source_id: str, text: str) -> str:
    """The one address whose extracted text is exactly *text*."""
    result = run_cli(
        "--workspace", str(workspace), "sources", "addresses", "--source", source_id, "--json"
    )
    assert result.returncode == 0, result.stderr
    matches = [item for item in result.json() if item["text"].strip() == text]
    assert len(matches) == 1, matches
    return str(matches[0]["locator_key"])


def _claim(
    workspace: Path,
    *,
    source_id: str,
    address: str,
    value: float,
    span: str | None = None,
) -> dict[str, Any]:
    """Record a numeric claim through the CLI, and return its record."""
    arguments = [
        "--workspace",
        str(workspace),
        "task",
        "claim",
        "--source",
        source_id,
        "--address",
        address,
        "--kind",
        "numeric",
        "--value",
        str(value),
        "--unit",
        "dimensionless",
        "--tolerance",
        "0.01",
        "--json",
    ]
    if span is not None:
        arguments.extend(["--span", span])
    result = run_cli(*arguments)
    assert result.returncode == 0, result.stderr
    payload: dict[str, Any] = result.json()
    assert payload["record"]["status"] == "extracted"
    return payload


def _attest(workspace: Path, evidence_id: str) -> None:
    """A person stands behind their own claim, through the CLI."""
    result = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "claim-attest",
        evidence_id,
        "--user",
        "dr-who",
        "--note",
        "I read the cell and the number is the cell's.",
        "--json",
    )
    assert result.returncode == 0, result.stderr


def _a_second_record_on_the_same_anchor(
    workspace: Path,
    task_id: str,
    *,
    anchor_id: str,
    value: float,
    source_content_hash: str,
) -> str:
    """A record claiming *value* about the address the anchor points into.

    Planted with the store's own write seam, because the CLI's claim command
    mints a fresh anchor per claim and a disagreement is two records about one
    address. The extracted span is the claimed number as text: the record
    says the address holds it, which is exactly the claim C3 exists to judge.
    """
    span = str(value)
    evidence_id = str(new_id())
    with _context(workspace, task_id) as context:
        connection = context.store.session.connection()
        append_record(
            connection,
            EvidenceRecord(
                evidence_id=evidence_id,
                task_id=task_id,
                kind=EvidenceKind.NUMERIC,
                text=None,
                value=value,
                unit="dimensionless",
                tolerance=0.01,
                anchor_ids=(anchor_id,),
                extracted_span=span,
                extracted_span_sha256=hashlib.sha256(span.encode("utf-8")).hexdigest(),
                source_content_hash=source_content_hash,
                status=VerificationStatus.EXTRACTED,
                created_by=EvidenceCreator.RULE,
                created_by_id="seed",
                created_at=datetime.now(UTC),
            ),
        )
        context.store.session.commit()
    return evidence_id


def _advance_to(
    workspace: Path,
    task_id: str,
    evidence_id: str,
    status: VerificationStatus,
    checks: tuple[CheckKind, ...],
) -> None:
    """Move a record through the state machine, with the checks the move needs."""
    with _context(workspace, task_id) as context:
        connection = context.store.session.connection()
        advance(
            connection,
            evidence_id,
            status,
            index=LabCairnIndex(connection),
            checks=checks,
            checked_at=datetime.now(UTC),
        )
        context.store.session.commit()


def _report(workspace: Path) -> Any:
    """Run ``task report --json`` and return the finished process."""
    return run_cli("--workspace", str(workspace), "task", "report", "--json")


@pytest.fixture()
def ingested(workspace: Path, material: Path) -> str:
    """A workspace with its material ingested and bound to the task.

    ``material`` is requested for its side effect: it writes the file the
    ingestion reads, and a fixture that is not requested is not run.
    """
    del material
    return _ingest(workspace)


# --------------------------------------------------------------------------- #
# the door passes, and says what it judged
# --------------------------------------------------------------------------- #


def test_a_report_over_an_attested_record_carries_the_gate_s_verdict(
    workspace: Path, task_id: str, ingested: str
) -> None:
    """The report's own record says which records the gate judged, and that they passed.

    This is the positive control: the whole door, on the simplest ledger that
    reaches it. The record is citable — a person attested it — so the report
    states it as established, and the gate judges it.
    """
    address = _the_address_whose_text_is(workspace, ingested, "2")
    claimed = _claim(workspace, source_id=ingested, address=address, value=2.0)
    evidence_id = claimed["record"]["evidence_id"]
    _attest(workspace, evidence_id)

    reported = _report(workspace)
    assert reported.returncode == 0, reported.stdout + reported.stderr
    payload = reported.json()

    gate = payload["evidence_gate"]
    assert gate["passed"] is True
    assert gate["findings"] == []
    assert gate["considered"] == [evidence_id]
    assert payload["unjudged_records"] == []


def test_the_gate_does_not_refuse_a_record_the_report_labels_with_its_status(
    workspace: Path, task_id: str, ingested: str
) -> None:
    """An extracted claim is printed with ``(extracted)``, and the report says so.

    The document model's whole honesty is the graded claim: a sentence that
    says how far it was checked. The gate's status finding on such a record is
    a finding the report's own text has already stated, so it is not a reason
    to refuse — and the result names the record as one the gate did not judge,
    which is the other half of the same statement.

    **The two lists partition the report.** The document's own snapshot names
    every record the report carries; the result's ``considered`` and
    ``unjudged_records`` together are that same set. So a reader can see the
    gate's extent from the report's own record, and a gate that quietly
    stopped judging one record would leave it in neither list rather than
    hide inside a total.
    """
    extracted_address = _the_address_whose_text_is(workspace, ingested, "1")
    attested_address = _the_address_whose_text_is(workspace, ingested, "2")
    extracted = _claim(workspace, source_id=ingested, address=extracted_address, value=1.0)
    attested = _claim(workspace, source_id=ingested, address=attested_address, value=2.0)
    _attest(workspace, attested["record"]["evidence_id"])

    reported = _report(workspace)
    assert reported.returncode == 0, reported.stdout + reported.stderr
    payload = reported.json()

    assert payload["evidence_gate"]["considered"] == [attested["record"]["evidence_id"]]
    assert payload["unjudged_records"] == [extracted["record"]["evidence_id"]]

    document = json.loads(
        (workspace / "output" / task_id / "report" / "v1" / "report.json").read_text(
            encoding="utf-8"
        )
    )
    assert (
        sorted(payload["evidence_gate"]["considered"] + payload["unjudged_records"])
        == document["snapshot"]["record_ids"]
    )


def test_the_gate_does_not_refuse_a_record_the_report_does_not_carry(
    workspace: Path, task_id: str, ingested: str
) -> None:
    """A planned record is not in the report, so it is not the report's refusal.

    This is the cost the whole-task door would pay: a planned record fails the
    gate over the task, while the document never quotes it. Refusing here
    would be a refusal with no repair the caller can make by editing the
    report, so the report does not ask the gate about it — and the result
    names neither it nor its own extent.
    """
    address = _the_address_whose_text_is(workspace, ingested, "2")
    claimed = _claim(workspace, source_id=ingested, address=address, value=2.0)
    evidence_id = claimed["record"]["evidence_id"]
    _attest(workspace, evidence_id)

    planned_id = str(new_id())
    with _context(workspace, task_id) as context:
        connection = context.store.session.connection()
        append_record(
            connection,
            EvidenceRecord(
                evidence_id=planned_id,
                task_id=task_id,
                kind=EvidenceKind.CLAIM,
                text="A claim declared, not yet located.",
                anchor_ids=(),
                extracted_span=None,
                extracted_span_sha256=None,
                source_content_hash=None,
                status=VerificationStatus.PLANNED,
                created_by=EvidenceCreator.USER,
                created_by_id="local-user",
                created_at=datetime.now(UTC),
            ),
        )
        context.store.session.commit()

    reported = _report(workspace)
    assert reported.returncode == 0, reported.stdout + reported.stderr
    payload = reported.json()
    assert payload["evidence_gate"]["considered"] == [evidence_id]
    assert planned_id not in payload["unjudged_records"]


# --------------------------------------------------------------------------- #
# the door closes, and the surface says why
# --------------------------------------------------------------------------- #


def test_the_report_is_refused_when_the_gate_finds_a_contradicted_number(
    workspace: Path, task_id: str, ingested: str
) -> None:
    """Two records about one cell, and the report is about to state one of them.

    The cell says 2. The report's claim says 2 and the rule confirmed it; a
    second record says 9 and C3 refused it. The claim's own number agrees with
    the ledger and every content check would pass — **the gate is the only
    door that sees the disagreement**, because the disagreement is not in the
    document, it is in the ledger the document rests on.

    So this is the witness that the gate is load-bearing: the refusal names
    both records and the conflict, the reason is the gate's own, and nothing
    was written.
    """
    address = _the_address_whose_text_is(workspace, ingested, "2")
    claimed = _claim(workspace, source_id=ingested, address=address, value=2.0)
    evidence_id = claimed["record"]["evidence_id"]
    disputed_id = _a_second_record_on_the_same_anchor(
        workspace,
        task_id,
        anchor_id=claimed["anchor_id"],
        value=9.0,
        source_content_hash=claimed["record"]["source_content_hash"],
    )
    _advance_to(
        workspace,
        task_id,
        evidence_id,
        VerificationStatus.VERIFIED_BY_RULE,
        (CheckKind.C1, CheckKind.C3),
    )
    _advance_to(workspace, task_id, disputed_id, VerificationStatus.UNSUPPORTED, (CheckKind.C3,))

    reported = _report(workspace)
    assert reported.returncode == EXIT_REFUSED, reported.stdout
    payload = reported.json()
    assert payload["reason"] == "report_evidence_refused"
    message = payload["message"]
    assert evidence_id in message
    assert disputed_id in message
    assert "conflict" in message
    assert "Nothing was written" in message

    listed = run_cli("--workspace", str(workspace), "artifacts", "list", "--json")
    assert listed.returncode == 0, listed.stderr
    assert listed.json() == [], "a refused report left an artefact behind"
    forms = sorted(
        path.name for path in (workspace / "output" / task_id).rglob("report*") if path.is_file()
    )
    assert forms == [], f"the output area holds {forms}"
