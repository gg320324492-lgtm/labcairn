"""One file, one identity, whichever door carried it in.

The trial's real sample is ingested by the CLI's ``task create``/inventory
walk **before** anything loops over it. The walk mints source ids from the
root id and the root-relative key (``_stable_source_id``); ``open_loop``
used to let ``ingest_bytes`` derive one from the workspace-relative path
instead. One file then arrived as two identities for one
``sources.relative_path`` -- a UNIQUE violation, an ``IntegrityError``, and
a session poisoned for every later call. The 2026-11-16 trial dry run hit
exactly this (finding F-1) and could only dodge it by looping material from
a separate root -- a dodge the trial day cannot take, because the real
sample must be CLI-ingested first.

These witnesses pin the alignment: looping a file that the walk already
ingested reuses the walk's row (no second row, no refusal), looping a file
the walk has *not* ingested still works, and a loop after an edit moves the
recorded hash instead of minting a new material.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.application.revision_loop import open_loop
from labcairn.material.walk import _stable_source_id, ingest_workspace
from labcairn.workspace.readonly import SourceMaterial
from revision_loop_support import LoopFixture, build_fixture

pytestmark = pytest.mark.integration

env = _shared_env


@pytest.fixture
def fixture(env: StoreEnv, tmp_path: Path) -> LoopFixture:
    return build_fixture(env.store(), tmp_path / "workspace")


def _walk_the_source_dir(store_env: StoreEnv, fixture: LoopFixture) -> None:
    """Ingest the fixture's source root the way the CLI's inventory does."""
    from datetime import UTC, datetime

    workspace = fixture.context.workspace
    material = SourceMaterial(workspace, fixture.context.policy)
    report = ingest_workspace(
        store_env.session,
        material,
        ingested_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert not report.failures, f"the walk itself must not fail: {report.failures}"


def test_a_loop_over_walk_ingested_material_reuses_the_walks_identity(
    env: StoreEnv, fixture: LoopFixture
) -> None:
    """CLI first, loop second: one row, the walk's id, no IntegrityError.

    The order matters -- this is the trial day's actual sequence. The walk
    records the material under the root+key id; the loop must arrive at the
    same id, or ``put_source`` inserts a second row whose
    ``relative_path`` collides with the UNIQUE constraint.
    """
    _walk_the_source_dir(env, fixture)

    loop = open_loop(
        fixture.context,
        source_root_id=fixture.context.workspace.source_roots[0].root_id,
        source_key="original.bin",
    )
    expected = _stable_source_id(
        fixture.context.workspace.source_roots[0].root_id, "original.bin"
    )
    assert loop.import_receipt.source_id == expected


def test_a_loop_over_unwalked_material_still_opens(fixture: LoopFixture) -> None:
    """Loop first, no walk: the loop still imports, under the same derivation.

    The alignment must not depend on the walk having run: the derivation is
    a function of (root id, root-relative key), both of which the loop's own
    admission already knows.
    """
    loop = open_loop(
        fixture.context,
        source_root_id=fixture.context.workspace.source_roots[0].root_id,
        source_key="original.bin",
    )
    expected = _stable_source_id(
        fixture.context.workspace.source_roots[0].root_id, "original.bin"
    )
    assert loop.import_receipt.source_id == expected


def test_a_second_loop_after_an_edit_moves_the_hash_not_the_identity(
    env: StoreEnv, fixture: LoopFixture
) -> None:
    """Edit between loops: same id, moved hash -- the drift the ledger must see.

    A content-derived id would make the edit a *new* material; a
    location-derived id shared with the walk keeps the identity and lets
    ``put_source``'s refresh branch move the recorded hash.
    """
    first = open_loop(
        fixture.context,
        source_root_id=fixture.context.workspace.source_roots[0].root_id,
        source_key="original.bin",
    )
    fixture.original_path.write_bytes(b"edited after the first loop\n")
    second = open_loop(
        fixture.context,
        source_root_id=fixture.context.workspace.source_roots[0].root_id,
        source_key="original.bin",
    )
    assert second.import_receipt.source_id == first.import_receipt.source_id
    assert second.import_receipt.original_sha256 != first.import_receipt.original_sha256
