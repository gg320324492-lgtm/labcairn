"""A removal names the source it took back: the log's own witness.

The acceptance record ``docs/acceptance/LC-P4-PILOT-source-removal-2026-11-26.md``
measured the removal's effect and then recorded the gap (§7 and §9.1): the
removal wrote exactly one event, ``task_revised``, and that event's payload was
empty. **A source that left the ledger and a task that was revised are not the
same fact**, and only the second was in the log — so the next morning the log
could not say what had been taken back.

This file holds the answer still. Every byte is written by the test into its
own temporary workspace, and every row is written by the product into its own
temporary database; nothing here reads the pilot.

**What the witnesses are about.** The entry has to *name that source id* — an
event count going up is not the property — and it has to be the removal's own
event rather than the released tasks' revisions. The event also has to be an
annotation: a removal happens to a task outside any run, and an event that
claimed an attempt would be a trace a reader could mistake for work that
started.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text as sql_text
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.application import create_task, ingest_material
from labcairn.application.context import ApplicationContext
from labcairn.application.material_ingestion import remove_source
from labcairn.core.ids import TaskId, new_id
from labcairn.db.repository import events_after
from labcairn.runtime.event import Event, EventType
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import CapabilityId
from labcairn.security.policy import Permission, PermissionPolicy, Rule

pytestmark = pytest.mark.integration

# pytest resolves a fixture by the parameter name in a test's signature, so the
# shared `env` fixture must be bound under that name here.
env = _shared_env

_MOMENT = datetime(2026, 1, 1, tzinfo=UTC)

#: A material with two cells and a header. A CSV carries disclosures of its
#: own, so the removal has something to take with the row; a plain text file
#: would leave the disclosure count at zero and prove less.
_CSV_BODY = b"a,b\n1,2\n"


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """A workspace with a source directory in it."""
    root = tmp_path / "workspace"
    (root / "materials").mkdir(parents=True)
    return root


def _allow_all() -> PermissionPolicy:
    """A policy that allows everything, so a test can vary one thing at a time."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])


def _allow_inventory() -> PermissionPolicy:
    """The policy the removal runs under: the inventory, and nothing else.

    The removal goes through the permission boundary like every other
    operation, so the policy under which it runs is part of the behaviour and
    not a detail of the test.
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


def _context(env: StoreEnv, workspace_root: Path) -> ApplicationContext:
    """A context for a task that exists, under the policy the operation needs."""
    created = create_task(
        store=env.store(),
        policy=_allow_all(),
        workspace_root=workspace_root,
        title="Naming what was taken back",
        goal=TaskGoal(
            objective="Establish what the material says.",
            success_criterion="A cited answer, or an honest 'not established'.",
        ),
        source_dirs=(workspace_root / "materials",),
    )
    return ApplicationContext(
        workspace=created.workspace,
        store=env.store(),
        policy=_allow_inventory(),
        ledger=ApprovalLedger(),
    )


def _a_material_ingested(
    env: StoreEnv, workspace_root: Path, *, relative: str = "one.csv", body: bytes = _CSV_BODY
) -> tuple[ApplicationContext, str, str, str]:
    """Ingest one material, and hand back what the removal needs to name it."""
    materials = workspace_root / "materials"
    (materials / relative).write_bytes(body)
    context = _context(env, workspace_root)
    ingested = ingest_material(context, now=_MOMENT)
    return (
        context,
        ingested.source_ids[0],
        ingested.files[0].source.relative_path,
        ingested.files[0].source.content_sha256,
    )


def _removal_events(env: StoreEnv, task_id: TaskId, *, after_seq: int = 0) -> list[Event]:
    """Every ``source_removed`` event on the task's log after the cursor."""
    return [
        event
        for event in events_after(env.session, task_id, after_seq=after_seq)
        if event.type is EventType.SOURCE_REMOVED
    ]


def _row_count(env: StoreEnv, table: str, key: str, value: str) -> int:
    """How many rows of *table* name *value* in column *key*."""
    return int(
        env.session.execute(
            sql_text(f"SELECT COUNT(*) FROM {table} WHERE {key} = :value"),
            {"value": value},
        ).scalar_one()
    )


def test_the_log_names_the_source_a_removal_took_back(env: StoreEnv, workspace_root: Path) -> None:
    """The removal writes an event whose payload names that source id.

    **What would make this red.** A removal that wrote no event at all (the
    state the pilot measured), an event whose payload was empty, or an event
    that named the survivor rather than the row that left. An event count
    going up would not hold the property: the count can be satisfied by the
    task's own revision, which is exactly what was in the log before this
    event existed.

    The path and the digest are asserted too, because a source's identity is
    its location: the id alone does not tell a reader which path left, and
    the digest says what the path held.
    """
    context, stale_id, relative_path, digest = _a_material_ingested(env, workspace_root)
    before = events_after(env.session, context.task_id)

    removed = remove_source(context, stale_id)

    assert removed.source_id == stale_id
    new = events_after(env.session, context.task_id, after_seq=before[-1].seq)
    naming = [event for event in new if event.type is EventType.SOURCE_REMOVED]
    assert len(naming) == 1, (
        "the removal did not leave exactly one source_removed event; "
        f"the log after it was {[event.type.value for event in new]}"
    )
    payload: Any = dict(naming[0].payload)
    assert payload["source_id"] == stale_id
    assert payload["relative_path"] == relative_path
    assert payload["content_sha256"] == digest
    assert payload["released_task_ids"] == [str(context.task_id)]


def test_the_entry_that_names_the_source_is_not_the_tasks_revision(
    env: StoreEnv, workspace_root: Path
) -> None:
    """A removal and a task's revision are two facts, and both are in the log.

    **What would make this red.** A removal that kept writing only
    ``task_revised`` (the pilot's shape), or one that replaced the release's
    revision with the removal event and left the task's own state change
    unrecorded. The binding release and the row's departure are different
    changes: the first is the task's, the second is the ledger's.

    The binding is released before the removal so that the only event this
    test's window can see is the removal's own; the revision that let the
    material go is then asserted to be *absent from that window* rather than
    absent from the log.
    """
    context, stale_id, _path, _digest = _a_material_ingested(env, workspace_root)
    env.store().bind_sources(context.task_id, ())
    before = events_after(env.session, context.task_id)

    remove_source(context, stale_id)

    new = events_after(env.session, context.task_id, after_seq=before[-1].seq)
    assert [event.type for event in new] == [EventType.SOURCE_REMOVED], (
        "the removal's window holds something other than its own event: "
        f"{[event.type.value for event in new]}"
    )
    assert new[0].payload["source_id"] == stale_id


def test_a_removal_that_released_a_task_says_which_task(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The event names the tasks that had to let the material go.

    **What would make this red.** An event that named the source and dropped
    the release, which would leave ``released_task_ids`` empty for the one
    removal where it matters. **What the record measured**: the removal
    released the pilot task's binding and wrote ``task_revised``; the log
    could say *a task changed* but not *which task lost which source*.
    """
    context, stale_id, _path, _digest = _a_material_ingested(env, workspace_root)
    before = events_after(env.session, context.task_id)

    removed = remove_source(context, stale_id)

    assert removed.released_task_ids == (str(context.task_id),)
    new = events_after(env.session, context.task_id, after_seq=before[-1].seq)
    removal = _removal_events(env, context.task_id, after_seq=before[-1].seq)
    assert len(removal) == 1
    assert removal[0].payload["released_task_ids"] == [str(context.task_id)]
    revision = next(
        (event for event in new if event.type is EventType.TASK_REVISED),
        None,
    )
    assert revision is not None, "the released task's revision is not in the log"
    assert revision.payload == {}, (
        "the task's revision payload is no longer empty; the removal's own "
        "event is where the source is named"
    )


def test_the_removal_event_is_an_annotation_and_carries_no_attempt(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The removal event names no run, stage, operation or transition.

    **What would make this red.** An event written with a Run or an Operation
    invented for it. A removal happens to a task outside any attempt, and the
    invented attempt would be the trace that could be mistaken for work that
    started — the same rule ``refusal_recorded`` follows.

    The seq is also asserted to follow the task's previous event, because an
    event outside the task's own gapless counter would not be reachable by a
    client resuming with ``after_seq``.
    """
    context, stale_id, _path, _digest = _a_material_ingested(env, workspace_root)
    env.store().bind_sources(context.task_id, ())
    before = events_after(env.session, context.task_id)

    remove_source(context, stale_id)

    new = events_after(env.session, context.task_id, after_seq=before[-1].seq)
    assert len(new) == 1
    event = new[0]
    assert event.type is EventType.SOURCE_REMOVED
    assert event.seq == before[-1].seq + 1
    assert event.run_id is None
    assert event.stage_id is None
    assert event.operation_id is None
    assert event.transition is None


def test_a_removal_whose_event_cannot_be_written_leaves_the_row(
    env: StoreEnv,
    workspace_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The deletion and the event commit together, or neither does.

    **What would make this red.** A removal that deleted the row and then
    failed to write the event. The log would then be silent about a row that
    is gone — the pilot's gap, one direction further. ADR-0003 C3 is what
    forbids it, and the store's unit is the mechanism: the deletion is issued
    on the same session, and the unit's rollback takes it back.

    The binding is released before the unit is broken so that the failure
    happens inside the removal's own transaction and not in the release.
    """
    context, stale_id, _path, _digest = _a_material_ingested(env, workspace_root)
    env.store().bind_sources(context.task_id, ())

    def refuse(self: Any, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError("the store refused the removal event")

    monkeypatch.setattr("labcairn.db.repository.UnitOfWork.emit", refuse)

    with pytest.raises(RuntimeError, match="refused the removal event"):
        remove_source(context, stale_id)

    assert _row_count(env, "sources", "source_id", stale_id) == 1, (
        "the row left the ledger although the event that names it was never written"
    )


def test_the_removal_payload_must_name_the_source() -> None:
    """The event's schema refuses a removal that names nothing.

    **What would make this red.** Registering an empty schema, or removing
    the registration so that a removal payload becomes a free-form bag. The
    event contract's own rule is that a type with no schema must carry an
    empty payload; a type *with* a schema must satisfy it.
    """
    with pytest.raises(ValueError, match="source_id"):
        Event(
            seq=1,
            task_id=TaskId(new_id()),
            type=EventType.SOURCE_REMOVED,
            payload={},
        )
