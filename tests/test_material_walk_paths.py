"""The path the walk records, and what the ledger can do with it.

``Source.relative_path`` is **workspace-relative** -- where the material is
measured from the workspace root -- and the walk is handed a **root-relative**
key. Recording the key as it stands put the row in the wrong root, where the
``source.inventory`` capability refuses it, so a material the walk ingested
could not be listed or inspected at all; and because the ledger's path is
UNIQUE, two source roots holding a file of the same name collided and the
second was never recorded.

This file holds the tests that watch the fix from the outside: the walk
records the path the contract names, the ids do not move with it, the two
roots no longer collide, and a material that came in through the walk is
readable by the layer's own readers.

**The ids are watched separately from the path.** They are already written in
the ledger for material ingested before the fix, and the recorded text, the
recorded hash and the drift detection that reads them all hang off them. An
id that moved with the path would orphan all three, and nothing else in the
suite would say so.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text as sql_text
from test_store_support import StoreEnv
from test_store_support import env as _shared_env

from labcairn.application import (
    ApplicationContext,
    create_task,
    ingest_material,
    inspect_source,
    list_sources,
)
from labcairn.core.ids import SourceId, TaskId, new_id
from labcairn.material.walk import ingest_workspace
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import CapabilityId
from labcairn.security.policy import Permission, PermissionPolicy, Rule
from labcairn.workspace.readonly import SourceMaterial
from labcairn.workspace.roots import Workspace

pytestmark = pytest.mark.unit

# pytest resolves a fixture by the parameter name in a test's signature, so the
# shared `env` fixture must be bound under that name here.
env = _shared_env

_MOMENT = datetime(2026, 1, 1, tzinfo=UTC)


def _allow_all() -> PermissionPolicy:
    """A policy that allows everything, so a test can vary one thing at a time."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])


def _inventory_only() -> PermissionPolicy:
    """A policy that allows the inventory of material, and nothing else."""
    return PermissionPolicy.from_rules(
        [
            Rule(
                effect=Permission.ALLOW,
                pattern="**",
                capabilities=frozenset({CapabilityId.SOURCE_INVENTORY.value}),
            )
        ]
    )


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """A workspace with a source directory in it."""
    root = tmp_path / "workspace"
    (root / "materials").mkdir(parents=True)
    return root


def _context(
    env: StoreEnv,
    workspace_root: Path,
    policy: PermissionPolicy,
    *,
    source_dirs: tuple[Path, ...] | None = None,
) -> ApplicationContext:
    """A context for a task that exists, under the policy the test wants."""
    directories = source_dirs if source_dirs is not None else (workspace_root / "materials",)
    store = env.store()
    created = create_task(
        store=store,
        policy=_allow_all(),
        workspace_root=workspace_root,
        title="Walk path task",
        goal=TaskGoal(
            objective="Establish what the material says.",
            success_criterion="A cited answer, or an honest 'not established'.",
        ),
        source_dirs=directories,
    )
    return ApplicationContext(
        workspace=created.workspace,
        store=store,
        policy=policy,
        ledger=ApprovalLedger(),
    )


def _walk(
    env: StoreEnv,
    workspace_root: Path,
    *,
    source_dirs: tuple[Path, ...] | None = None,
) -> Any:
    """Walk the workspace's material, and return the report.

    The walk itself, not the application operation: what is under test here is
    what the walk *records*, and an operation that relocates the rows after
    the fact would hide the very thing being asserted.
    """
    directories = source_dirs if source_dirs is not None else (workspace_root / "materials",)
    workspace = Workspace.bind(
        workspace_root,
        task_id=TaskId(new_id()),
        source_dirs=directories,
    )
    return ingest_workspace(
        env.session,
        SourceMaterial(workspace, _inventory_only()),
        ingested_at=_MOMENT,
    )


# --------------------------------------------------------------------------- #
# what the walk records
# --------------------------------------------------------------------------- #


def test_the_walk_records_the_workspace_relative_path(env: StoreEnv, workspace_root: Path) -> None:
    """The path in the ledger is measured from the **workspace** root.

    The material is under ``<workspace>/materials``, so the path is
    ``materials/notes.md`` -- not the root-relative ``notes.md`` the walk was
    handed.
    """
    (workspace_root / "materials" / "notes.md").write_text("# Notes\n", encoding="utf-8")

    report = _walk(env, workspace_root)

    assert report.failures == (), [message for _, message in report.failures]
    assert [o.material.source.relative_path for o in report.outcomes] == ["materials/notes.md"]


def test_the_ledger_holds_the_workspace_relative_path(env: StoreEnv, workspace_root: Path) -> None:
    """The report is not the claim; the store is.

    A walk that reported one path and wrote another would leave a caller
    reading a ledger that disagrees with it, and nothing in the report would
    say so.
    """
    (workspace_root / "materials" / "notes.md").write_text("# Notes\n", encoding="utf-8")

    _walk(env, workspace_root)

    stored = [row[0] for row in env.session.execute(sql_text("SELECT relative_path FROM sources"))]
    assert stored == ["materials/notes.md"], "the store and the report disagree"


def test_the_display_name_is_still_the_files_own_name(env: StoreEnv, workspace_root: Path) -> None:
    """The path grew a prefix; the name did not.

    ``display_name`` is the file's own name, and it is what a reader sees.
    Prefixing it would put the directory in the name twice.
    """
    (workspace_root / "materials" / "notes.md").write_text("# Notes\n", encoding="utf-8")

    report = _walk(env, workspace_root)

    assert [o.material.source.display_name for o in report.outcomes] == ["notes.md"]


# --------------------------------------------------------------------------- #
# the ids do not move with the path
# --------------------------------------------------------------------------- #


def test_the_source_id_is_derived_from_the_root_and_the_root_relative_key(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The id is the one the ledger already holds, and it says so.

    ``_stable_source_id`` mints the id from the root's id and the
    **root-relative** key, and those ids are already recorded for material
    ingested before the path was fixed. The recorded text, the recorded hash
    and the drift detection that reads them hang off the id, so an id that
    moved with the recorded path would orphan all three.

    The expectation is spelled out here rather than imported, because the
    property *is* the value: this is the id the ledger holds today.
    """
    (workspace_root / "materials" / "notes.md").write_text("# Notes\n", encoding="utf-8")

    report = _walk(env, workspace_root)

    expected = hashlib.sha256(f"source:0{chr(0)}notes.md".encode()).hexdigest()[:16]
    assert [o.material.source.source_id for o in report.outcomes] == [f"src-{expected}"]


def test_two_roots_holding_the_same_file_name_get_different_ids(
    env: StoreEnv, workspace_root: Path
) -> None:
    """Two roots, one file name: two ids, because they are two locations.

    The id is scoped by the root, so the roots' files never share an
    identity -- which is what lets the ledger hold both.
    """
    first = workspace_root / "first"
    second = workspace_root / "second"
    first.mkdir()
    second.mkdir()
    (first / "notes.md").write_text("from the first root\n", encoding="utf-8")
    (second / "notes.md").write_text("from the second root\n", encoding="utf-8")

    report = _walk(env, workspace_root, source_dirs=(first, second))

    ids = [o.material.source.source_id for o in report.outcomes]
    assert len(ids) == 2, "the two roots' files share an identity"
    assert ids[0] != ids[1]


def test_a_ledger_written_before_the_fix_is_repaired_by_the_next_ingestion(
    env: StoreEnv, workspace_root: Path
) -> None:
    """A row the old walk wrote becomes listable again.

    The old walk recorded the root-relative path, and the store's refresh
    branch does not move a row's path -- so a ledger written before the fix
    still holds the old spelling, and the material in it is still unlistable.
    The ids are what make the repair possible at all: they are derived from
    the root and the root-relative key, so the new ingestion finds the row
    the old one wrote instead of writing a second one beside it.

    The repair is a side effect of the operation that compensates for the
    walk, and this is the test that says so out loud rather than leaving it
    to be discovered.
    """
    material = workspace_root / "materials" / "notes.md"
    material.write_text("# Notes\n", encoding="utf-8")
    digest = hashlib.sha256(material.read_bytes()).hexdigest()
    source_id = f"src-{hashlib.sha256(f'source:0{chr(0)}notes.md'.encode()).hexdigest()[:16]}"
    env.session.execute(
        sql_text(
            "INSERT INTO sources (source_id, owner_id, kind, display_name, relative_path,"
            " content_sha256, size_bytes, readability, readability_disclosure, identifiers,"
            " ingested_at, schema_version)"
            " VALUES (:sid,'local-user','markdown','notes.md','notes.md',:sha,:size,"
            "'readable',NULL,'[]',:now,1)"
        ),
        {"sid": source_id, "sha": digest, "size": material.stat().st_size, "now": _MOMENT},
    )
    env.session.commit()
    context = _context(env, workspace_root, _inventory_only())

    ingest_material(context, now=_MOMENT)

    stored = [row[0] for row in env.session.execute(sql_text("SELECT relative_path FROM sources"))]
    assert stored == ["materials/notes.md"], "the row the old walk wrote was not repaired"
    views = list_sources(context)
    assert [view.source.relative_path for view in views] == ["materials/notes.md"]


# --------------------------------------------------------------------------- #
# a material that came in through the walk is readable
# --------------------------------------------------------------------------- #


def test_a_material_ingested_through_the_walk_can_be_listed(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The layer's own listing finds it.

    This is the defect, asserted from the reader's side: the row the walk
    wrote resolves into the wrong root, the ``source.inventory`` capability
    refuses it, and the material the walk ingested cannot be listed at all.
    """
    (workspace_root / "materials" / "notes.md").write_text("# Notes\n", encoding="utf-8")
    context = _context(env, workspace_root, _inventory_only())

    report = _walk(env, workspace_root)
    source_ids = [SourceId(o.material.source.source_id) for o in report.outcomes]
    context.store.bind_sources(context.task_id, source_ids, occurred_at=_MOMENT)

    views = list_sources(context)

    assert [view.source.relative_path for view in views] == ["materials/notes.md"]
    assert [view.source.source_id for view in views] == [
        str(o.material.source.source_id) for o in report.outcomes
    ]


def test_a_material_ingested_through_the_walk_can_be_inspected(
    env: StoreEnv, workspace_root: Path
) -> None:
    """And the single-source read finds it too.

    Listing and inspecting are two different questions, and a path that
    resolves for one does not have to resolve for the other.
    """
    (workspace_root / "materials" / "notes.md").write_text("# Notes\n", encoding="utf-8")
    context = _context(env, workspace_root, _inventory_only())

    report = _walk(env, workspace_root)
    source_id = report.outcomes[0].material.source.source_id
    context.store.bind_sources(context.task_id, [SourceId(source_id)], occurred_at=_MOMENT)

    view = inspect_source(context, source_id)

    assert view.source.source_id == source_id
    assert view.source.relative_path == "materials/notes.md"
    # The key the policy matched is the one in the source root, and the
    # source row's path is the one in the workspace. Both are named here
    # because a reader that confuses them matches the wrong rule.
    assert view.resource_key == "notes.md"


def test_two_roots_holding_the_same_file_name_are_both_recorded(
    env: StoreEnv, workspace_root: Path
) -> None:
    """Two roots, one file name, and both of them in the ledger.

    The ledger's path is UNIQUE, so the two files can only live side by side
    if their paths differ -- and they do, because each root's own place in
    the workspace is part of the path.
    """
    first = workspace_root / "first"
    second = workspace_root / "second"
    first.mkdir()
    second.mkdir()
    (first / "notes.md").write_text("from the first root\n", encoding="utf-8")
    (second / "notes.md").write_text("from the second root\n", encoding="utf-8")
    context = _context(env, workspace_root, _inventory_only(), source_dirs=(first, second))

    result = ingest_material(context, now=_MOMENT)

    assert result.failures == (), list(result.failures)
    assert sorted(item.source.relative_path for item in result.files) == [
        "first/notes.md",
        "second/notes.md",
    ]


# --------------------------------------------------------------------------- #
# the compensation is a no-op
# --------------------------------------------------------------------------- #


def test_the_ingestion_operation_now_relocates_nothing(
    env: StoreEnv, workspace_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The workaround has nothing left to do.

    The operation that drives the walk one root at a time and then moves each
    root's rows to the workspace-relative path was written to become a no-op
    once the walk wrote that path itself. It has: the mapping it hands the
    store names the path each row **already** holds, so no row moves.
    """
    (workspace_root / "materials" / "notes.md").write_text("# Notes\n", encoding="utf-8")
    context = _context(env, workspace_root, _inventory_only())

    consulted: list[dict[str, str]] = []
    real = context.store.relocate_sources

    def recording(renames_given: dict[str, str]) -> int:
        for source_id, path in renames_given.items():
            current: Any = env.session.execute(
                sql_text("SELECT relative_path FROM sources WHERE source_id = :s"),
                {"s": source_id},
            ).scalar_one()
            assert current == path, (
                f"the operation moved {source_id} from {current!r} to {path!r}; the walk "
                "already writes the workspace-relative path, so there is nothing to move"
            )
        consulted.append(dict(renames_given))
        return real(renames_given)

    monkeypatch.setattr(context.store, "relocate_sources", recording)

    result = ingest_material(context, now=_MOMENT)

    assert consulted, "the operation did not consult the store about the paths at all"
    assert [item.source.relative_path for item in result.files] == ["materials/notes.md"]
    stored = [row[0] for row in env.session.execute(sql_text("SELECT relative_path FROM sources"))]
    assert stored == ["materials/notes.md"], "the row moved after all"
