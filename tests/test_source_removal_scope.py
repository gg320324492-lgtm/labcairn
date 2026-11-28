"""What a removal releases when more than one task holds the material.

The acceptance record ``docs/acceptance/LC-P4-PILOT-source-removal-2026-11-26.md``
§9.5 states that the command's ``--task`` option **does not narrow what the
removal releases**: the release goes to every task that held the material.
**The run that recorded that could not distinguish the two readings**, because
the stale id it took back was held by one task only — with one holder,
"released the task named" and "released every holder" are the same observation.

This file builds the shape that run could not: **two tasks holding the same
source**, and a third task holding a different one. Every byte is written by
the test into a temporary workspace and every row by the product into a
temporary database; nothing here reads the pilot's material.

**Which reading is asserted, and why.** The wider one. The product states the
rule in its own words: :func:`~labcairn.application.material_ingestion.remove_source`
takes no task argument at all, the helper that performs the release walks
**every** task ("Every task is looked at, not only the one the caller happens
to be in." — ``_release_the_bindings``), and the CLI passes ``--task`` to its
own ``_select_task`` only to build the context; the id never reaches the
release (``sources_remove`` in ``src/labcairn/cli/commands.py``). A witness
asserting the narrow reading would contradict the product's own statement of
its rule.

**What would make each witness red.**

* ``test_a_removal_releases_every_task_that_held_the_material`` — a release
  that stops at the caller's task, leaving the other holder bound to an id the
  ledger no longer holds, or a report that names only the caller.
* ``test_a_removal_subtracts_the_material_and_leaves_every_other_binding_alone``
  — a release that clears each holder's binding instead of subtracting the one
  source, or that releases a task which never held the material.
* ``test_the_task_option_does_not_narrow_the_release`` — the same property
  observed through the CLI, with ``--task`` naming the first holder: red if a
  future implementation hands the option to the release and narrows it.

The CLI runs in this process (``typer.testing.CliRunner``) against the same
database the application layer wrote through, and the workspace's
configuration and policy are written the way ``labcairn init`` writes them.
The CLI resolves its database as ``<root>/labcairn.db``, so the workspace root
is the temporary directory itself: the store the test writes through and the
store the CLI reads are the same file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session
from store_support import StoreEnv
from store_support import env as _shared_env
from typer.testing import CliRunner

from labcairn.application import create_task, ingest_material
from labcairn.application.context import ApplicationContext
from labcairn.application.material_ingestion import remove_source
from labcairn.cli.commands import app
from labcairn.cli.workspace import (
    CONFIG_SCHEMA_VERSION,
    DEFAULT_POLICY_RULES,
    WorkspaceConfig,
    WorkspaceLocation,
    write_config,
    write_policy,
)
from labcairn.core.ids import SourceId, TaskId
from labcairn.db.repository import load_task
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import CapabilityId
from labcairn.security.policy import Permission, PermissionPolicy, Rule

pytestmark = pytest.mark.integration

# pytest resolves a fixture by the parameter name in a test's signature, so the
# shared `env` fixture must be bound under that name here.
env = _shared_env

#: A fixed instant, and the step between the tasks' creations. The store lists
#: tasks by ``(created_at, task_id)``, so distinct instants make the order of
#: ``released_task_ids`` deterministic rather than a tie broken by an id.
_MOMENT = datetime(2026, 1, 1, tzinfo=UTC)
_STEP = timedelta(minutes=1)

#: Two materials written by the test. The shared one is the material both
#: tasks rest on; the other one belongs to only some of them.
_SHARED_BODY = b"the material both tasks rest on\n"
_OTHER_BODY = b"the material only some tasks rest on\n"


# --------------------------------------------------------------------------- #
# the workspace
# --------------------------------------------------------------------------- #


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """The workspace, with its source directory.

    It is ``tmp_path`` itself rather than a directory below it because the CLI
    opens ``<root>/labcairn.db`` and the store fixture's database is at exactly
    that path; one root keeps the application layer and the CLI on one file.
    """
    (tmp_path / "materials").mkdir()
    return tmp_path


def _allow_all() -> PermissionPolicy:
    """A policy that allows everything, used where the test itself is setting up."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])


def _inventory_only() -> PermissionPolicy:
    """A policy that allows inventorying material, and nothing else.

    The removal goes through the permission boundary like every other
    operation, so the context it runs in carries the capability it needs rather
    than a test bypass.
    """
    return PermissionPolicy.from_rules(
        [
            Rule(
                effect=Permission.ALLOW,
                pattern="**",
                capabilities=frozenset({CapabilityId.SOURCE_INVENTORY.value}),
            )
        ]
    )


def _a_task(
    env: StoreEnv,
    workspace_root: Path,
    *,
    title: str,
    moment: datetime,
    bound_source_ids: tuple[SourceId, ...] = (),
) -> ApplicationContext:
    """A task in the shared workspace, and the context the removal runs in.

    ``bound_source_ids`` is the layer's own way of making a task that begins
    holding material without ingesting it, and it is how a test gives a task a
    binding narrower than everything its source root holds.
    """
    created = create_task(
        store=env.store(),
        policy=_allow_all(),
        workspace_root=workspace_root,
        title=title,
        goal=TaskGoal(
            objective="Establish what the material says.",
            success_criterion="A cited answer, or an honest 'not established'.",
        ),
        source_dirs=(workspace_root / "materials",),
        bound_source_ids=bound_source_ids,
        now=moment,
    )
    return ApplicationContext(
        workspace=created.workspace,
        store=env.store(),
        policy=_inventory_only(),
        ledger=ApprovalLedger(),
    )


def _configure_for_the_cli(env: StoreEnv, root: Path, *, current_task: TaskId) -> None:
    """Write the configuration and policy ``labcairn init`` writes.

    The database is named relative to the root because that is how the CLI
    resolves it (``location.root / config.database``), and the test's store is
    at exactly that path.
    """
    location = WorkspaceLocation(root=root)
    write_policy(location, DEFAULT_POLICY_RULES)
    write_config(
        location,
        WorkspaceConfig(
            schema_version=CONFIG_SCHEMA_VERSION,
            database=str(env.db_path.relative_to(root)),
            source_dirs=("materials",),
            current_task=str(current_task),
        ),
    )


def _run_cli(root: Path, *args: str) -> Result:
    """The command, in this process, with the arguments a person would type.

    The width is declared because Rich asks the terminal how wide it is; a
    captured stream is not a terminal. The replies this file reads are JSON,
    which does not wrap, but a refusal is rendered through the same console.
    """
    return CliRunner().invoke(app, ["--workspace", str(root), *args], env={"COLUMNS": "200"})


# --------------------------------------------------------------------------- #
# reading the ledger back
# --------------------------------------------------------------------------- #


def _held(env: StoreEnv, task_id: TaskId) -> tuple[str, ...]:
    """The ids the task's binding holds, read through the store's own reader."""
    task = load_task(env.session, task_id)
    return tuple(str(bound) for bound in task.bound_source_ids)


def _source_ids(session: Session) -> tuple[str, ...]:
    """The ids of the sources the ledger holds."""
    rows = session.execute(sql_text("SELECT source_id FROM sources ORDER BY source_id")).all()
    return tuple(str(row[0]) for row in rows)


# --------------------------------------------------------------------------- #
# the shape the pilot run could not build: one source, two holders
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _TwoHolders:
    """One source, held by both tasks, and each task's own context."""

    first: ApplicationContext
    second: ApplicationContext
    source_id: str
    digest: str


def _one_material_held_by_two_tasks(env: StoreEnv, workspace_root: Path) -> _TwoHolders:
    """Two tasks, one material, both bound to it.

    The material is ingested **through each task's own context** rather than
    bound by a test shortcut: a source's id is minted from the source root and
    the file's key inside it, and both tasks bind the same ``materials``
    directory as the same root — so the same file is the same row, and the
    product's own ingestion is what binds it. Both tasks therefore hold the
    same source id.
    """
    (workspace_root / "materials" / "shared.txt").write_bytes(_SHARED_BODY)

    first = _a_task(env, workspace_root, title="The first holder", moment=_MOMENT)
    first_ingested = ingest_material(first, now=_MOMENT)

    second = _a_task(
        env,
        workspace_root,
        title="The second holder",
        moment=_MOMENT + _STEP,
    )
    second_ingested = ingest_material(second, now=_MOMENT)

    assert first_ingested.source_ids == second_ingested.source_ids, (
        "the same file under the same source root must be the same source row, so "
        "both tasks hold one id; the second ingestion minted a different one and "
        "the shape this witness needs does not exist"
    )
    return _TwoHolders(
        first=first,
        second=second,
        source_id=first_ingested.source_ids[0],
        digest=first_ingested.files[0].source.content_sha256,
    )


# --------------------------------------------------------------------------- #
# the witnesses
# --------------------------------------------------------------------------- #


def test_a_removal_releases_every_task_that_held_the_material(
    env: StoreEnv, workspace_root: Path
) -> None:
    """Both holders let the material go, and the report names both.

    **The reading asserted is the wider one**: the removal releases every task
    that held the material, not only the task the command was addressed to.
    The product says so (``_release_the_bindings``: "Every task is looked at,
    not only the one the caller happens to be in."), and §9.5 of the removal
    record states it as the behaviour the pilot run could not distinguish.

    **What would make this red.** A release that stops at the context's task:
    the second holder would keep an id the ledger no longer holds, which is the
    broken state the release exists to end. A report that names only the
    caller also turns it red. The exact tuple is asserted because the store
    lists tasks oldest first (``(created_at, task_id)``) and the report follows
    that walk, so each holder is named exactly once.
    """
    holders = _one_material_held_by_two_tasks(env, workspace_root)
    assert _held(env, holders.first.task_id) == (holders.source_id,)
    assert _held(env, holders.second.task_id) == (holders.source_id,)

    removed = remove_source(holders.first, holders.source_id)

    assert removed.content_sha256 == holders.digest, (
        "the removal's report is about a different material than the one removed"
    )
    assert removed.released_task_ids == (
        str(holders.first.task_id),
        str(holders.second.task_id),
    ), "the release named only the task the command was addressed to"
    assert _held(env, holders.first.task_id) == ()
    assert _held(env, holders.second.task_id) == (), (
        "the second holder still claims a source the ledger no longer holds"
    )
    assert holders.source_id not in _source_ids(env.session)


def test_a_removal_subtracts_the_material_and_leaves_every_other_binding_alone(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The release subtracts the one source, and touches nothing else.

    **The reading asserted is the wider one** — every holder is released — and
    this witness adds the other boundary: a task that never held the material
    is not named, and a source a holder also holds stays bound.

    **What would make this red.** A release that sets each binding to empty
    instead of subtracting the one source: the second holder would lose the
    other material. A release with no guard over who actually held the source:
    the third task would be named as released although its state did not move.
    A removal by digest rather than id would take the other source's row too,
    which the last assertions refuse.
    """
    materials = workspace_root / "materials"
    (materials / "shared.txt").write_bytes(_SHARED_BODY)

    # The first task exists while only the shared material does, so ingestion
    # binds that one thing and nothing else.
    first = _a_task(env, workspace_root, title="Holds the shared material", moment=_MOMENT)
    shared = ingest_material(first, now=_MOMENT).source_ids[0]

    (materials / "other.txt").write_bytes(_OTHER_BODY)
    second = _a_task(
        env,
        workspace_root,
        title="Holds both materials",
        moment=_MOMENT + _STEP,
    )
    second_ingested = ingest_material(second, now=_MOMENT)

    other = next(source_id for source_id in second_ingested.source_ids if source_id != shared)
    assert set(second_ingested.source_ids) == {shared, other}

    # The third task never held the shared material: it begins bound to the
    # other source alone, through the layer's own ``bound_source_ids``.
    third = _a_task(
        env,
        workspace_root,
        title="Holds the other material",
        moment=_MOMENT + 2 * _STEP,
        bound_source_ids=(SourceId(other),),
    )
    assert set(_held(env, second.task_id)) == {shared, other}
    assert _held(env, third.task_id) == (other,)

    removed = remove_source(first, shared)

    assert removed.released_task_ids == (str(first.task_id), str(second.task_id)), (
        "the release must name the holder that co-held the material and must not "
        "name the task that never held it"
    )
    assert _held(env, first.task_id) == ()
    assert _held(env, second.task_id) == (other,), (
        "the release cleared the holder's binding instead of subtracting the one source"
    )
    assert _held(env, third.task_id) == (other,)
    assert shared not in _source_ids(env.session)
    assert other in _source_ids(env.session), (
        "the removal took a source that was not the one it named"
    )


def test_the_task_option_does_not_narrow_the_release(env: StoreEnv, workspace_root: Path) -> None:
    """``sources remove --task`` releases the other holder too.

    **The reading asserted is the wider one.** ``--task`` selects which task
    the command is *about* — the context it builds — and not which bindings are
    released; the option is consumed by ``_select_task`` and no task id reaches
    ``remove_source``. §9.5 of the removal record is the same statement.

    **What would make this red.** An implementation that hands ``--task`` to
    the release and narrows it: the second holder would keep the id, and the
    report would name only the first. The command is run in this process
    against the database this test wrote through, because what is under test is
    what the command does with its own option.
    """
    holders = _one_material_held_by_two_tasks(env, workspace_root)
    _configure_for_the_cli(env, workspace_root, current_task=holders.first.task_id)

    # The session's snapshot must not be the one the CLI's connection writes
    # past; roll it back so the read below begins after the command's commit.
    env.session.rollback()
    outcome = _run_cli(
        workspace_root,
        "sources",
        "remove",
        "--source",
        holders.source_id,
        "--task",
        str(holders.first.task_id),
        "--json",
    )

    assert outcome.exit_code == 0, f"the removal refused: {outcome.output}"
    report: dict[str, Any] = json.loads(outcome.stdout)
    assert set(report["released_task_ids"]) == {
        str(holders.first.task_id),
        str(holders.second.task_id),
    }, "--task narrowed the release to the task it named"

    env.session.rollback()
    assert _held(env, holders.first.task_id) == ()
    assert _held(env, holders.second.task_id) == (), (
        "the task named by --task was released and the other holder was not"
    )
    assert holders.source_id not in _source_ids(env.session)
