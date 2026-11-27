"""The command line says what the evidence gate judged, the way the API does.

**The gap this file witnesses.** The report's result carries the gate's own
verdict — :attr:`~labcairn.application.reports.ReportRendered.evidence_gate`,
the records it judged, and ``unjudged_records``, the records the report names
without judging — and the API returns both. The command line printed neither:
a reader at the terminal saw that a report was written and nothing about which
records the gate judged and which the report names without judging. The two
lists are **one statement**: they partition the document's snapshot, and a
reader who sees only one of them cannot tell what the other holds.

**The property is an equivalence, not a text.** The human rendering and the
``--json`` rendering are not the same text — one is a picture, the other is the
model's own serialization — so the witness compares them **as facts**: the ids
the JSON carries, the counts it reports, the verdict it gives, and the
refusal it names. A witness that compared the two renderings as bytes would be
a witness of the picture, not of the property.

**The two surfaces are compared, not one against a literal.** Every fact the
human rendering carries is read back out of the JSON the same command printed.
A literal would go stale the moment the layer changed a shape, and would then
fail for a reason that has nothing to do with the property under test.

**Phrases, not lines.** The CLI renders through Rich, which asks the terminal
how wide it is; a pipe is not a terminal, so a wrap that falls inside a phrase
truncates it. Every assertion here is on a phrase, and the rig
(``tests/test_cli_support.py``) pins ``COLUMNS`` at two hundred and the
child's encoding — so a wider or narrower terminal cannot turn this file red
for a reason that has nothing to do with what it witnesses.

**No material leaves the tree.** Every ledger state below is built in a scratch
workspace under the registered temp area, from a synthetic material of the
tests' own. No pilot material is read and no model request is made.
"""

from __future__ import annotations

import hashlib
import re
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
) -> dict[str, Any]:
    """Record a numeric claim through the CLI, and return its record."""
    result = run_cli(
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
    )
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
    address.
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


def _plant_a_planned_record(workspace: Path, task_id: str) -> str:
    """A record the report does not carry at all.

    Planned: the document does not name it, so it is neither judged nor
    unjudged. It is the third side of the statement — the records that are in
    neither list.
    """
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
    return planned_id


def _report(workspace: Path, *extra: str) -> Any:
    """Run ``task report`` and return the finished process."""
    return run_cli("--workspace", str(workspace), "task", "report", *extra)


@pytest.fixture()
def ingested(workspace: Path, material: Path) -> str:
    """A workspace with its material ingested and bound to the task.

    ``material`` is requested for its side effect: it writes the file the
    ingestion reads, and a fixture that is not requested is not run.
    """
    del material
    return _ingest(workspace)


# --------------------------------------------------------------------------- #
# what the human rendering has to carry, read as facts
# --------------------------------------------------------------------------- #


def _ids_in(text: str) -> list[str]:
    """The record ids the human rendering names, in the order it names them.

    **A phrase, not a line.** The rendering is a panel, and Rich folds a long
    row to the terminal's width; an id that lands at a fold boundary would be
    split across two lines. So the ids are read out of the whole text, and the
    assertion is on the ids rather than on the rows they were drawn in.
    """
    return re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", text)


def _the_record_ids(text: str, *, task_id: str) -> list[str]:
    """The record ids the rendering names, with the task's own id set aside.

    **The task id is not a record id.** It is a UUID too, and it appears in
    the output for a different reason — the receipt's path names the task the
    report belongs to — so leaving it in would make the witness compare a
    record's id against a task's id. It is subtracted explicitly rather than
    filtered by shape, because the shape is the same for both.
    """
    return [found for found in _ids_in(text) if found != task_id]


def _the_human_facts(stdout: str, *, task_id: str) -> dict[str, Any]:
    """The facts the human rendering carries, read back out of it."""
    return {
        "ids": _the_record_ids(stdout, task_id=task_id),
        "mentions_gate": "evidence gate" in stdout,
        "mentions_judged": "judged" in stdout,
        "mentions_unjudged": "unjudged" in stdout,
    }


def _the_json_facts(payload: dict[str, Any]) -> dict[str, Any]:
    """The facts the JSON carries, read out of the model's own serialization.

    **The ids only.** The JSON carries them as two lists — the ones the gate
    judged and the ones the report names without judging — and the human
    rendering has to carry the same two lists, in the same order, so they are
    compared as one sequence.
    """
    gate = payload["evidence_gate"]
    return {
        "ids": list(gate.get("considered") or []) + list(payload.get("unjudged_records") or []),
    }


# --------------------------------------------------------------------------- #
# the gate ran, and the command line says so
# --------------------------------------------------------------------------- #


def test_the_command_line_says_the_gate_ran_and_what_it_judged(
    workspace: Path, task_id: str, ingested: str
) -> None:
    """A report over an attested record names the gate's verdict and the record.

    The positive control: the whole door, on the simplest ledger that reaches
    it. The record is citable — a person attested it — so the gate judges it
    and passes, and the command line has to say both.

    **The facts are compared, not the text.** The JSON carries the verdict, the
    judged id and the unjudged ids; the human rendering has to carry the same
    facts. Comparing the two renderings as bytes would witness the picture
    rather than the property, and the two are not the same text.
    """
    address = _the_address_whose_text_is(workspace, ingested, "2")
    claimed = _claim(workspace, source_id=ingested, address=address, value=2.0)
    evidence_id = str(claimed["record"]["evidence_id"])
    _attest(workspace, evidence_id)

    as_json = _report(workspace, "--json")
    assert as_json.returncode == 0, as_json.stdout + as_json.stderr
    payload = as_json.json()

    human = _report(workspace)
    assert human.returncode == 0, human.stdout + human.stderr

    json_facts = _the_json_facts(payload)
    human_facts = _the_human_facts(human.stdout, task_id=task_id)

    # The gate ran, and the rendering says which records it judged.
    assert human_facts["mentions_gate"], human.stdout
    assert human_facts["mentions_judged"], human.stdout
    assert human_facts["mentions_unjudged"], human.stdout
    assert human_facts["ids"] == json_facts["ids"], (
        f"the human rendering names {human_facts['ids']} and the JSON names {json_facts['ids']}"
    )
    assert evidence_id in human_facts["ids"], human.stdout

    # The verdict, as a fact and not as a phrase.
    assert payload["evidence_gate"]["passed"] is True
    assert "passed" in human.stdout


def test_the_two_lists_partition_what_the_report_carries(
    workspace: Path, task_id: str, ingested: str
) -> None:
    """The judged and the unjudged lists are disjoint, and together they are
    the records the report carries.

    This is the statement the two lists make together, and a reader who saw
    only one of them could not tell what the other held. The witness is the
    partition itself: the same two lists, read out of the human rendering and
    out of the JSON, must agree, and must not overlap.
    """
    address = _the_address_whose_text_is(workspace, ingested, "2")
    claimed = _claim(workspace, source_id=ingested, address=address, value=2.0)
    evidence_id = str(claimed["record"]["evidence_id"])
    _attest(workspace, evidence_id)

    payload = _report(workspace, "--json").json()
    judged = list(payload["evidence_gate"]["considered"] or [])
    unjudged = list(payload["unjudged_records"] or [])

    assert judged == [evidence_id], judged
    assert unjudged == [], unjudged
    assert not set(judged) & set(unjudged)

    human = _report(workspace)
    assert human.returncode == 0, human.stdout + human.stderr
    assert set(_the_record_ids(human.stdout, task_id=task_id)) == set(judged) | set(unjudged), (
        human.stdout
    )


def test_the_command_line_names_the_records_the_report_states_without_judging(
    workspace: Path, task_id: str, ingested: str
) -> None:
    """A record the report names without judging is named on the command line.

    The other half of the gate's extent. A claim that is only *extracted* is
    carried by the report with its status printed beside it — the gate does not
    judge it, because the report's own text already says what it is. A reader
    still has to see that the record is there and was not judged: a record
    that vanishes from the rendering looks like a record that was judged and
    passed.
    """
    address = _the_address_whose_text_is(workspace, ingested, "2")
    claimed = _claim(workspace, source_id=ingested, address=address, value=2.0)
    extracted_id = str(claimed["record"]["evidence_id"])

    payload = _report(workspace, "--json").json()
    assert payload["evidence_gate"]["considered"] == []
    assert extracted_id in payload["unjudged_records"], payload

    human = _report(workspace)
    assert human.returncode == 0, human.stdout + human.stderr
    assert extracted_id in _the_record_ids(human.stdout, task_id=task_id), human.stdout

    # And the two lists still partition what the report carries.
    json_facts = _the_json_facts(payload)
    human_facts = _the_human_facts(human.stdout, task_id=task_id)
    assert human_facts["ids"] == json_facts["ids"]


def test_the_command_line_carries_the_records_the_gate_did_not_judge_and_the_ones_it_did(
    workspace: Path, task_id: str, ingested: str
) -> None:
    """Both lists at once: one judged record and one the report names unjudged.

    The partition is only visible when both halves are non-empty. With one
    empty list, a rendering that dropped the other entirely would still look
    right.
    """
    address = _the_address_whose_text_is(workspace, ingested, "2")
    claimed = _claim(workspace, source_id=ingested, address=address, value=2.0)
    attested_id = str(claimed["record"]["evidence_id"])
    _attest(workspace, attested_id)

    # A second, differently-anchored record that stays extracted: the report
    # names it, and the gate does not judge it.
    other_address = _the_address_whose_text_is(workspace, ingested, "1")
    other = _claim(workspace, source_id=ingested, address=other_address, value=1.0)
    extracted_id = str(other["record"]["evidence_id"])

    payload = _report(workspace, "--json").json()
    judged = list(payload["evidence_gate"]["considered"] or [])
    unjudged = list(payload["unjudged_records"] or [])
    assert attested_id in judged, payload
    assert extracted_id in unjudged, payload

    human = _report(workspace)
    assert human.returncode == 0, human.stdout + human.stderr
    assert set(_the_record_ids(human.stdout, task_id=task_id)) == set(judged) | set(unjudged), (
        human.stdout
    )
    assert attested_id in _the_record_ids(human.stdout, task_id=task_id)
    assert extracted_id in _the_record_ids(human.stdout, task_id=task_id)


def test_a_record_the_report_does_not_carry_is_neither_judged_nor_unjudged(
    workspace: Path, task_id: str, ingested: str
) -> None:
    """The third side of the statement: a record that is in neither list.

    A planned record is not carried by the report at all. Naming it as
    unjudged would be a false statement about the report's extent, and naming
    it as judged would be a false statement about the gate's. So it appears in
    neither list, and it does not appear on the command line either.
    """
    address = _the_address_whose_text_is(workspace, ingested, "2")
    claimed = _claim(workspace, source_id=ingested, address=address, value=2.0)
    evidence_id = str(claimed["record"]["evidence_id"])
    _attest(workspace, evidence_id)

    planned_id = _plant_a_planned_record(workspace, task_id)

    payload = _report(workspace, "--json").json()
    assert payload["evidence_gate"]["considered"] == [evidence_id], payload
    assert planned_id not in payload["unjudged_records"], payload

    human = _report(workspace)
    assert human.returncode == 0, human.stdout + human.stderr
    assert planned_id not in _the_record_ids(human.stdout, task_id=task_id), human.stdout


# --------------------------------------------------------------------------- #
# the refusal is unchanged
# --------------------------------------------------------------------------- #


def test_the_refusal_is_unchanged_and_names_the_objection(
    workspace: Path, task_id: str, ingested: str
) -> None:
    """A gate that objects refuses the report, and the refusal is the one it was.

    The rendering this window added must not soften the refusal or change its
    reason: a report the gate refused was never written, so there is no gate
    verdict to draw. The refusal still goes to stderr with the gate's reason
    and names every objection, and the exit code still says *refused*.
    """
    address = _the_address_whose_text_is(workspace, ingested, "2")
    claimed = _claim(workspace, source_id=ingested, address=address, value=2.0)
    evidence_id = str(claimed["record"]["evidence_id"])
    disputed_id = _a_second_record_on_the_same_anchor(
        workspace,
        task_id,
        anchor_id=str(claimed["anchor_id"]),
        value=9.0,
        source_content_hash=str(claimed["record"]["source_content_hash"]),
    )
    _advance_to(
        workspace,
        task_id,
        evidence_id,
        VerificationStatus.VERIFIED_BY_RULE,
        (CheckKind.C1, CheckKind.C3),
    )
    _advance_to(workspace, task_id, disputed_id, VerificationStatus.UNSUPPORTED, (CheckKind.C3,))

    as_json = _report(workspace, "--json")
    assert as_json.returncode == EXIT_REFUSED, as_json.stdout + as_json.stderr
    refusal = as_json.json()
    assert refusal["reason"] == "report_evidence_refused", refusal
    assert "evidence gate" in refusal["message"], refusal
    assert evidence_id in refusal["message"], refusal
    assert disputed_id in refusal["message"], refusal

    human = _report(workspace)
    assert human.returncode == EXIT_REFUSED, human.stdout + human.stderr
    assert "refused" in human.stderr, human.stderr
    assert "report_evidence_refused" in human.stderr, human.stderr

    # And nothing was written, so there is no gate verdict to draw.
    assert "evidence gate" not in human.stdout, human.stdout


# --------------------------------------------------------------------------- #
# the rendering carries no material
# --------------------------------------------------------------------------- #


def test_the_rendering_carries_ids_and_not_the_records_text(
    workspace: Path, task_id: str, ingested: str
) -> None:
    """The rendering carries ids, counts and outcomes — never the records' text.

    The tree's own rule is that material does not travel in a rendering, and a
    record's words are the material. So the claim's text is asserted absent
    from the human rendering, and the id is asserted present.
    """
    address = _the_address_whose_text_is(workspace, ingested, "2")
    claimed = _claim(workspace, source_id=ingested, address=address, value=2.0)
    evidence_id = str(claimed["record"]["evidence_id"])
    _attest(workspace, evidence_id)

    human = _report(workspace)
    assert human.returncode == 0, human.stdout + human.stderr
    assert evidence_id in _the_record_ids(human.stdout, task_id=task_id), human.stdout
    # The material itself — the record's unit and its number — is not in the
    # rendering. Ids, counts and outcomes travel; the record's text does not.
    assert "dimensionless" not in human.stdout, human.stdout
    assert "2.0" not in human.stdout, human.stdout
