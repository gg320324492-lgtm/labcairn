"""The loop that the pieces existed for, witnessed against real files.

LC-P3-03 is an integration ticket: the read-only door, the single write point,
the approval binding and the reconciliation branch already had witnesses of
their own. What this file witnesses is **the binding** — one import receipt
whose hash is re-compared at every effect, an independent copy that hashes to
the original, a publication receipt derived from both, and a recovery path
whose probe resolves an interrupted publication without a second receipt.

Every file here is a real file on disk, and every number that is printed in
the acceptance record is measured from these operations. No mocked filesystem.

The witness that catches the original being written
----------------------------------------------------
``test_the_original_is_unchanged_through_the_loop`` asserts the hash against
the known bytes before and after, and the negative file's drift witness
replaces the source with a writable junction to prove the assertion actually
fails when a write to the original succeeds.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from revision_loop_support import (
    EDITED_BYTES,
    MOMENT,
    ORIGINAL_BYTES,
    LoopFixture,
    build_fixture,
    granted_copy_approval,
    granted_publication_approval,
    open_a_loop,
)
from sqlalchemy import update
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.application.recovery import reconcile_abandoned, resolve_abandoned
from labcairn.application.refusal import ApplicationRefusedError
from labcairn.application.revision_loop import (
    publish_revision,
    stage_copy,
    verify_original,
)
from labcairn.core.ids import OperationId
from labcairn.db.models import OperationRow
from labcairn.db.repository import list_artifacts
from labcairn.runtime.operation import OperationState
from labcairn.security.approval import content_hash
from labcairn.workspace.readonly import SourceIsReadOnlyError

pytestmark = pytest.mark.integration

# Fixture resolution is by parameter name; the shared env fixture must be bound
# under that name in this module.
env = _shared_env


@pytest.fixture
def fixture(env: StoreEnv, tmp_path: Path) -> LoopFixture:
    return build_fixture(env.store(), tmp_path / "workspace")


def test_the_import_receipt_carries_the_hash_of_the_real_original(fixture: LoopFixture) -> None:
    """The receipt's hash is the file's hash, and the manifest is on disk."""
    loop = open_a_loop(fixture)
    assert loop.import_receipt.original_sha256 == content_hash(fixture.original_path)
    assert loop.import_receipt.size_bytes == len(ORIGINAL_BYTES)

    manifest = fixture.workspace_root / "output" / str(fixture.context.task_id) / loop.manifest_key
    assert manifest.is_file()
    assert loop.import_receipt.receipt_id.encode() in manifest.read_bytes()
    assert loop.import_receipt.original_sha256.encode() in manifest.read_bytes()

    with fixture.context.store.unit(fixture.context.task_id) as _unused:
        pass  # a unit with nothing to do: the reader below is the assertion
    artifacts = list_artifacts(fixture.context.store.session, fixture.context.task_id)
    assert any(receipt.receipt_id == loop.import_artifact_id for receipt in artifacts)


def test_the_import_receipt_derivation_names_the_original_and_its_hash(
    fixture: LoopFixture,
) -> None:
    """A receipt whose derivation is not the original's hash derives nothing."""
    loop = open_a_loop(fixture)
    artifacts = list_artifacts(fixture.context.store.session, fixture.context.task_id)
    receipt = next(row for row in artifacts if row.receipt_id == loop.import_artifact_id)
    derivation = receipt.derived_from[0]
    assert derivation.target_id == loop.import_receipt.relative_path
    assert derivation.content_sha256 == loop.import_receipt.original_sha256


def test_the_copy_is_independent_and_hashes_to_the_original(fixture: LoopFixture) -> None:
    """The original that was read is never the file that was written."""
    loop = open_a_loop(fixture)
    approval = granted_copy_approval(fixture.context, loop)
    staged = stage_copy(fixture.context, loop, approval_id=approval, now=MOMENT)

    copy_path = fixture.workspace_root / "output" / str(fixture.context.task_id) / loop.copy_key
    assert copy_path.is_file()
    assert copy_path.read_bytes() == ORIGINAL_BYTES
    assert staged.copy_sha256 == loop.import_receipt.original_sha256
    assert staged.copy_sha256 == content_hash(copy_path)
    assert copy_path.resolve() != fixture.original_path.resolve()
    assert fixture.original_path.read_bytes() == ORIGINAL_BYTES


def test_the_original_is_unchanged_through_the_loop(fixture: LoopFixture) -> None:
    """The load-bearing claim: the same hash at import and after publication."""
    before = content_hash(fixture.original_path)
    loop = open_a_loop(fixture)
    copy_approval = granted_copy_approval(fixture.context, loop)
    stage_copy(fixture.context, loop, approval_id=copy_approval, now=MOMENT)
    publication_approval = granted_publication_approval(fixture.context, loop)
    published = publish_revision(
        fixture.context,
        loop,
        approval_id=publication_approval,
        edited_bytes=EDITED_BYTES,
        now=MOMENT,
    )

    assert fixture.original_path.read_bytes() == ORIGINAL_BYTES
    assert content_hash(fixture.original_path) == before
    assert verify_original(fixture.context, loop) == loop.import_receipt.original_sha256
    assert published.publication_sha256 == content_hash(
        fixture.workspace_root / "output" / str(fixture.context.task_id) / loop.publication_key
    )
    assert published.publication_sha256 != loop.import_receipt.original_sha256


def test_the_publication_receipt_derives_from_both_the_original_and_the_import(
    fixture: LoopFixture,
) -> None:
    """Two derivations, two hashes: neither is a prose description of the other."""
    loop = open_a_loop(fixture)
    copy_approval = granted_copy_approval(fixture.context, loop)
    stage_copy(fixture.context, loop, approval_id=copy_approval, now=MOMENT)
    publication_approval = granted_publication_approval(fixture.context, loop)
    published = publish_revision(
        fixture.context,
        loop,
        approval_id=publication_approval,
        edited_bytes=EDITED_BYTES,
        now=MOMENT,
    )
    derivations = {d.target_kind.value: d for d in published.publication.derived_from}
    assert derivations["material_file"].content_sha256 == loop.import_receipt.original_sha256
    assert derivations["material_file"].target_id == loop.import_receipt.relative_path
    assert derivations["artifact"].target_id == loop.import_artifact_id
    assert derivations["artifact"].content_sha256 == content_hash(
        fixture.workspace_root / "output" / str(fixture.context.task_id) / loop.manifest_key
    )


def test_the_read_only_guard_still_refuses_a_write_through_the_loop(
    fixture: LoopFixture,
) -> None:
    """The loop binds the guard; it does not replace it with a convention."""
    from labcairn.workspace.readonly import SourceMaterial

    loop = open_a_loop(fixture)
    material = SourceMaterial(fixture.context.workspace, fixture.context.policy)
    with pytest.raises(SourceIsReadOnlyError):
        material.write("original.bin", b"overwritten", root_id=fixture.source_root_id)
    assert fixture.original_path.read_bytes() == ORIGINAL_BYTES
    assert verify_original(fixture.context, loop) == loop.import_receipt.original_sha256


def test_a_second_loop_over_the_same_file_reuses_the_material(fixture: LoopFixture) -> None:
    """One file, one ledger row: two loops do not split the material in two."""
    first = open_a_loop(fixture)
    second = open_a_loop(fixture)
    assert second.import_receipt.source_id == first.import_receipt.source_id
    assert second.import_receipt.receipt_id != first.import_receipt.receipt_id
    assert second.import_receipt.original_sha256 == first.import_receipt.original_sha256


def test_an_interrupted_publication_resolves_to_one_receipt(fixture: LoopFixture) -> None:
    """The recovery half: a crash between write and confirm resolves by probe.

    The drill is real, not a flag: after a committed publication, the operation
    row is put back to ``ATTEMPTING`` through the store's own session — the
    state a process that died before its confirming transaction would have
    left — and then the repository's recovery pass and probe run for real.
    The predicted hash is the publication's own content hash, which is what a
    caller that planned the write can state and the store cannot reconstruct.
    """
    loop = open_a_loop(fixture)
    copy_approval = granted_copy_approval(fixture.context, loop)
    stage_copy(fixture.context, loop, approval_id=copy_approval, now=MOMENT)
    publication_approval = granted_publication_approval(fixture.context, loop)
    published = publish_revision(
        fixture.context,
        loop,
        approval_id=publication_approval,
        edited_bytes=EDITED_BYTES,
        now=MOMENT,
    )

    session = fixture.context.store.session
    session.execute(
        update(OperationRow)
        .where(OperationRow.operation_id == str(published.operation.operation_id))
        .values(state=OperationState.ATTEMPTING.value)
    )
    session.commit()

    uncertain = reconcile_abandoned(fixture.context)
    assert len(uncertain) == 1
    assert uncertain[0].state is OperationState.UNCERTAIN

    outcome = resolve_abandoned(
        fixture.context,
        OperationId(published.operation.operation_id),
        expected_sha256=published.publication_sha256,
    )
    assert outcome.resulting_state is OperationState.CONFIRMED
    assert outcome.replay_permitted is False

    artifacts = list_artifacts(session, fixture.context.task_id)
    assert sum(r.receipt_id == loop.publication_artifact_id for r in artifacts) == 1
    assert (
        fixture.workspace_root / "output" / str(fixture.context.task_id) / loop.publication_key
    ).read_bytes() == EDITED_BYTES


def test_a_conflicting_recovery_does_not_overwrite_an_unrelated_file(
    fixture: LoopFixture,
) -> None:
    """A differing file at the publication key stays blocked, not clobbered."""
    loop = open_a_loop(fixture)
    copy_approval = granted_copy_approval(fixture.context, loop)
    stage_copy(fixture.context, loop, approval_id=copy_approval, now=MOMENT)
    publication_approval = granted_publication_approval(fixture.context, loop)
    published = publish_revision(
        fixture.context,
        loop,
        approval_id=publication_approval,
        edited_bytes=EDITED_BYTES,
        now=MOMENT,
    )
    publication_path = (
        fixture.workspace_root / "output" / str(fixture.context.task_id) / loop.publication_key
    )
    foreign = b"bytes this loop never wrote\n"
    publication_path.write_bytes(foreign)

    session = fixture.context.store.session
    session.execute(
        update(OperationRow)
        .where(OperationRow.operation_id == str(published.operation.operation_id))
        .values(state=OperationState.ATTEMPTING.value)
    )
    session.commit()
    reconcile_abandoned(fixture.context)

    with pytest.raises(ApplicationRefusedError):
        resolve_abandoned(
            fixture.context,
            OperationId(published.operation.operation_id),
            expected_sha256=published.publication_sha256,
        )
    assert publication_path.read_bytes() == foreign
