"""A dangling source id, read back through the record and attestation faces.

The acceptance record
``docs/acceptance/LC-P4-PILOT-dangling-source-ids-2026-11-26.md`` measured
every face the product has over the ledger's shape — a source holding
addresses, taken back: the source-id faces (``list_source_addresses``,
``inspect_source``) refuse it, and the report builder refuses a record that
cites it, naming the source whose row is gone. But two faces the same record
measured returned the record as **sound**:

* the record's own read — ``list_task_records``, the layer operation the
  service's ``GET /records`` serves — returned the citing record at all:
  its status, its anchor ids and its source hash, with no refusal, while the
  anchor's ``source_id`` named a source the ledger no longer holds; and
* the attestation — ``attest_claim``, the layer operation the CLI's
  ``task claim-attest`` serves — **advanced** that record into
  ``user_attested``, a state a report may cite, without asking of the
  anchor's source row a second time.

A row whose source is gone reading back as if nothing were wrong is the
finding that record exists to hold still, and this file is the witness of it.
**What would make these red.** Either face learning to check the anchor's
source row again — a record the ledger holds would stop being listed or
attested for the better or the worse — or the removal cascade-deleting the
record or its anchor, so the faces would refuse for a different reason than
the one measured.

Nothing under the local material area is read: the shape is built in a
workspace of its own, under a temporary directory, through the product's own
operations, and every row below is written by the product into its own
temporary database.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.application import (
    ApplicationContext,
    ClaimRequest,
    attest_claim,
    create_task,
    ingest_material,
    list_source_addresses,
    list_task_records,
    record_claim,
)
from labcairn.application.material_ingestion import remove_source
from labcairn.db.repository import load_source
from labcairn.evidence.gate import CITABLE_STATUSES
from labcairn.evidence.index import load_anchor
from labcairn.evidence.record import EvidenceRecord
from labcairn.evidence.states import EvidenceKind, VerificationStatus
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import CapabilityId
from labcairn.security.policy import Permission, PermissionPolicy, Rule

pytestmark = pytest.mark.integration

env = _shared_env

_MOMENT = datetime(2026, 1, 1, tzinfo=UTC)

#: A material with a header and a reading: the shape the record describes —
#: two cells a claim can be recorded at, one of them the value.
_CSV_BODY = b"metric,reading\nvalue,4.2\n"


# --------------------------------------------------------------------------- #
# the workspace, in the record's shape
# --------------------------------------------------------------------------- #


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """A workspace with a source directory in it."""
    root = tmp_path / "workspace"
    (root / "materials").mkdir(parents=True)
    return root


def _allow_all() -> PermissionPolicy:
    """A policy that allows everything, so a face can be driven on its own."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])


def _inventory_only() -> PermissionPolicy:
    """The removal's own policy, the way the house witness runs it: the
    inventory and nothing else, because the removal goes through the
    permission boundary like every other operation."""
    return PermissionPolicy.from_rules(
        [
            Rule(
                effect=Permission.ALLOW,
                pattern="**",
                capabilities=frozenset({CapabilityId.SOURCE_INVENTORY.value}),
            )
        ]
    )


def _a_shape(
    env: StoreEnv, workspace_root: Path
) -> tuple[ApplicationContext, str, str, str, EvidenceRecord, str]:
    """The record's shape, measured before and after the row is taken back.

    A material is ingested; a claim is recorded at one of its addresses, so
    the ledger holds a source, an anchor into it and the record that cites
    the anchor. The material is then **moved** and ingested again — a source
    is a location, so that is a second row rather than a moved one — and the
    row the old path left behind, the one that held the addresses, is taken
    back by the product's own removal. What is returned is enough to read
    every face over the result: the contexts the faces run under, the two
    source ids, the record and its anchor.
    """
    materials = workspace_root / "materials"
    (materials / "one.csv").write_bytes(_CSV_BODY)
    context = _a_context_all(env, workspace_root)

    first = ingest_material(context, now=_MOMENT)
    stale_id = first.source_ids[0]
    addresses = list_source_addresses(context, stale_id)
    address = next(a for a in addresses if a.text == "4.2")

    recorded = record_claim(
        context,
        ClaimRequest(
            source_id=stale_id,
            locator_key=address.locator_key,
            kind=EvidenceKind.CLAIM,
            text="The reading is recorded at this address.",
        ),
        now=_MOMENT,
    )

    # the move: the old path leaves the disk, and the material sits at a new one
    (materials / "one.csv").unlink()
    (materials / "moved").mkdir()
    (materials / "moved" / "one.csv").write_bytes(_CSV_BODY)
    second = ingest_material(context, now=_MOMENT)

    removal = ApplicationContext(
        workspace=context.workspace,
        store=context.store,
        policy=_inventory_only(),
        ledger=context.ledger,
    )
    remove_source(removal, stale_id)

    return (
        context,
        stale_id,
        second.source_ids[0],
        str(context.task_id),
        recorded.record,
        recorded.anchor_id,
    )


def _a_context_all(env: StoreEnv, workspace_root: Path) -> ApplicationContext:
    """A task that holds the material, under a policy that allows the reads."""
    created = create_task(
        store=env.store(),
        policy=_allow_all(),
        workspace_root=workspace_root,
        title="Reading a dangling id back",
        goal=TaskGoal(
            objective="Establish what the material says.",
            success_criterion="A cited answer, or an honest 'not established'.",
        ),
        source_dirs=(workspace_root / "materials",),
    )
    return ApplicationContext(
        workspace=created.workspace,
        store=env.store(),
        policy=_allow_all(),
        ledger=ApprovalLedger(),
    )


# --------------------------------------------------------------------------- #
# the faces the record measured
# --------------------------------------------------------------------------- #


def test_the_records_read_back_the_record_whose_source_is_gone(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The record's own read lists it, in full, after its source row goes.

    **What would make this red.** A ``list_task_records`` that checked each
    record's anchors against the sources table would stop listing a record
    whose anchor names a taken-back row — and the face the service's
    ``GET /records`` serves would stop returning a record the ledger holds.
    The measurement the witness holds is the one the record says reads as
    sound: the record comes back, status and anchor ids and source hash
    intact, while the source row its anchor names is not in the ledger.
    """
    context, stale_id, _survivor_id, _task_id, record, anchor_id = _a_shape(env, workspace_root)
    assert load_source(env.session, stale_id) is None, (
        "the shape is the premise of this witness: the source row is gone"
    )

    records = list_task_records(context)

    assert [r.evidence_id for r in records] == [record.evidence_id], (
        "the record the ledger holds is the record the face returns"
    )
    listed = records[0]
    assert listed == record, (
        "the face returns the record the ledger holds — same fields, same anchors"
    )
    assert listed.status is VerificationStatus.EXTRACTED
    assert listed.anchor_ids == (anchor_id,)
    assert listed.source_content_hash is not None
    anchor = load_anchor(env.session.connection(), anchor_id)
    assert anchor is not None and anchor.source_id == stale_id, (
        "the record's anchor is still in the ledger, and it still names the "
        "source the ledger no longer holds"
    )


def test_the_attestation_advances_a_record_whose_source_is_gone(
    env: StoreEnv, workspace_root: Path
) -> None:
    """A person's word puts the record into the citable set, with its source gone.

    ``attest_claim`` is the face the CLI's ``task claim-attest`` serves, and
    the record measured it returning the record advanced to
    ``user_attested`` — a state a report may cite — while the anchor's source
    row was not in the ledger. **What would make this red.** An attestation
    that re-checked the anchor's source row, or a removal that took the
    record with the row, and the advance would fail or be unnecessary;
    the property held still is that the two faces do not ask the question.
    """
    context, stale_id, _survivor_id, _task_id, record, anchor_id = _a_shape(env, workspace_root)
    assert load_source(env.session, stale_id) is None

    attested = attest_claim(
        context,
        record.evidence_id,
        user_id="the-reader",
        note="I read it against the address.",
        now=_MOMENT,
    )

    assert attested.record.status is VerificationStatus.USER_ATTESTED
    assert attested.record.status in CITABLE_STATUSES, (
        "the state the attestation reaches is one a report may cite from, and "
        "the report builder is the only face that catches what the record cites"
    )
    anchor = load_anchor(env.session.connection(), anchor_id)
    assert anchor is not None and anchor.source_id == stale_id, (
        "the record that just became citable still rests on an address into a "
        "source the ledger does not hold"
    )
