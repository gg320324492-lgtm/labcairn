"""A dangling source id, read back through the record and attestation faces.

The acceptance record
``docs/acceptance/LC-P4-PILOT-dangling-source-ids-2026-11-26.md`` measured
every face the product has over the ledger's shape -- a source holding
addresses, taken back: the source-id faces (``list_source_addresses``,
``inspect_source``) refuse it, and the report builder refuses a record that
cites it, naming the source whose row is gone. The same reading found two
faces that did **not** refuse, and this file is the witness that they now do.

* the record's own read -- ``list_task_records``, the layer operation the
  service's ``GET /records`` serves -- returns the citing record, but as
  ``extracted``: a status a report may not cite. The reading is sound and the
  record is not citable, which is the whole of what a reader needs to know.
* the attestation -- ``attest_claim``, the layer operation the CLI's
  ``task claim-attest`` serves -- **refuses**. Reaching ``user_attested`` is
  the door to a citable status, and a citation rests on its source; the store
  runs C1 at that door (ADR-0004 I4), so a record whose anchor names a source
  the ledger no longer holds cannot be advanced. The refusal names the source.

**What would make these red.** The attestation learning to advance a record
whose source is gone -- the behaviour the 2026-11-26 record measured -- or the
removal cascade-deleting the record or its anchor, so the reading would refuse
for a different reason than the one measured. The reading assertion is the
control that keeps the second from standing in for the first: the record is
still listed, still ``extracted``, so the attestation's refusal is C1's and not
the cascade's.

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
    ApplicationRefusal,
    ApplicationRefusedError,
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
from labcairn.evidence.store import load_record
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
    """The record's own read lists it, but as ``extracted`` -- not citable.

    ``list_task_records`` is the face the service's ``GET /records`` serves. It
    returns the citing record, status and anchor ids and source hash intact,
    while the source row its anchor names is not in the ledger. That is sound:
    the record is ``extracted``, a status **no report may cite**, so a reader
    who stops at the read is told the truth -- here is the record, and it is not
    yet citable. This is the control for the attestation witness below: the
    record is still listed and still ``extracted``, so the attestation's refusal
    is C1's and not the removal having taken the record with the row.

    **What would make this red.** A ``list_task_records`` that checked each
    record's anchors against the sources table and stopped listing a record
    whose anchor names a taken-back row, or a removal that cascade-deleted the
    record -- either would leave the attestation with nothing to refuse.
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
        "the face returns the record the ledger holds -- same fields, same anchors"
    )
    assert listed.status is VerificationStatus.EXTRACTED
    assert listed.status not in CITABLE_STATUSES, (
        "a report may not cite the record while it is only extracted, so the "
        "read tells a reader the truth without certifying anything"
    )
    assert listed.anchor_ids == (anchor_id,)
    assert listed.source_content_hash is not None
    anchor = load_anchor(env.session.connection(), anchor_id)
    assert anchor is not None and anchor.source_id == stale_id, (
        "the record's anchor is still in the ledger, and it still names the "
        "source the ledger no longer holds"
    )


def test_the_attestation_refuses_a_record_whose_source_is_gone(
    env: StoreEnv, workspace_root: Path
) -> None:
    """A person's word may not make the record citable while its source is gone.

    ``attest_claim`` is the face the CLI's ``task claim-attest`` serves. The
    2026-11-26 record measured it advancing the record to ``user_attested`` --
    a state a report may cite -- while the anchor's source row was not in the
    ledger. It now refuses: reaching a citable status is the door a citation
    comes through, the store runs C1 at that door (ADR-0004 I4), and the refusal
    names the source whose bytes could not be observed.

    **What would make this red.** An attestation that stopped re-checking the
    anchor's source -- the behaviour the record measured -- would advance the
    record and this would fail; so would a refusal that did not name the source,
    or one that fired because the removal had taken the record (the read witness
    above is the control that it did not).
    """
    context, stale_id, _survivor_id, _task_id, record, anchor_id = _a_shape(env, workspace_root)
    assert load_source(env.session, stale_id) is None

    with pytest.raises(ApplicationRefusedError) as caught:
        attest_claim(
            context,
            record.evidence_id,
            user_id="the-reader",
            note="I read it against the address.",
            now=_MOMENT,
        )

    assert caught.value.reason is ApplicationRefusal.CITATION_SOURCE_UNOBSERVABLE, (
        "the refusal is the source one, not a generic ledger refusal"
    )
    assert stale_id in str(caught.value), (
        "the refusal names the source whose bytes could not be observed, so a "
        "reader is not left hunting for the row"
    )
    still = load_record(env.session.connection(), record.evidence_id)
    assert still is not None and still.status is VerificationStatus.EXTRACTED, (
        "a refused attestation leaves the record where it was -- not citable"
    )
    anchor = load_anchor(env.session.connection(), anchor_id)
    assert anchor is not None and anchor.source_id == stale_id, (
        "the anchor is still in the ledger, so the refusal is C1's and not the "
        "removal having taken the record with the row"
    )
