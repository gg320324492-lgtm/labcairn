"""The ingestion operation: what it reads, what it binds, and what it reports.

LC-P1-08 built the machinery and the application layer had no operation that
called it, so nothing could put a material in the ledger and bind it to a
task. This file is about the operation that does, and every property here is
one the product now rests on.

**It reads through the permission boundary.** A denied subtree must be
invisible to the operation exactly as it is to the user: no row, no failure,
and no mention of the name anywhere in what it reports. The test asserts the
last of those rather than only the first two, because a failure list that
named a denied file would disclose it.

**A file it could not read is reported.** One bad file does not stop the
others, and the failure is a fact the caller must see — a report that
swallowed it would be a report that said the workspace was fine.

**It is idempotent.** Running it twice over the same material writes nothing
the second time, and running it over an *edited* file refreshes what the
ledger records about it rather than failing on the row that is already there.

**The task ends up holding the material.** A task that holds no material can
carry disclosures and never a claim, so the binding is the operation's job and
not an afterthought.

**The binding accumulates, and the report says so.** The store's writer sets
the binding to what it is handed, so a task that was given material and then
ingested again would forget what it was given — and an operator removing a
file from the workspace would take the task's material with it, silently. The
binding after an operation is the union of what the task held and what the run
ingested, and the report carries both halves: what this run read, and what the
task holds.

**Unreadable, empty and readable material are kept apart.** ADR-0004 A7 asks
for the distinction most systems collapse, and the report of an ingestion is
where it is either kept or lost.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session
from test_store_support import StoreEnv
from test_store_support import env as _shared_env

from labcairn.application import (
    ApplicationContext,
    ApplicationRefusal,
    ApplicationRefusedError,
    create_task,
    ingest_material,
    list_sources,
)
from labcairn.core.ids import SourceId, TaskId
from labcairn.db.repository import count_events, events_after, load_task
from labcairn.db.repository import list_sources as store_list_sources
from labcairn.runtime.event import EventType
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import CapabilityId
from labcairn.security.policy import Permission, PermissionPolicy, Rule
from labcairn.sources.source import SourceReadability

pytestmark = pytest.mark.integration

# pytest resolves a fixture by the parameter name in a test's signature, so the
# shared `env` fixture must be bound under that name here.
env = _shared_env

_MOMENT = datetime(2026, 1, 1, tzinfo=UTC)

#: The shape of a source id the store uses. Location-derived, not a UUID.
_SOURCE_ID = re.compile(r"^src-[0-9a-f]{16}$")


def _allow_all() -> PermissionPolicy:
    """A policy that allows everything, so a test can vary one thing at a time."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])


def _inventory_only(*extra: Rule) -> PermissionPolicy:
    """A policy that allows the inventory of material, and whatever else is given."""
    rules = [
        Rule(
            effect=Permission.ALLOW,
            pattern="**",
            capabilities=frozenset({CapabilityId.SOURCE_INVENTORY.value}),
        ),
        *extra,
    ]
    return PermissionPolicy.from_rules(rules)


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
    """A context for a task that exists, under the policy the test wants.

    The task is made under an allowing policy whatever the test's policy is,
    because the test is about what happens *after* the task exists.
    """
    directories = source_dirs if source_dirs is not None else (workspace_root / "materials",)
    store = env.store()
    created = create_task(
        store=store,
        policy=_allow_all(),
        workspace_root=workspace_root,
        title="Ingesting task",
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


def _count(session: Session, table: str) -> int:
    """How many rows a table holds."""
    result = session.execute(sql_text(f"SELECT COUNT(*) FROM {table}"))
    return int(result.scalar_one())


def _revisions(session: Session, task_id: TaskId) -> int:
    """How many ``task_revised`` events the task's log holds.

    Counted from the events rather than from the total, because the total
    moves for other reasons — a task is created with an event of its own —
    and the question here is whether *the binding* moved.
    """
    return sum(
        1 for event in events_after(session, task_id) if event.type is EventType.TASK_REVISED
    )


def _held(env: StoreEnv, task_id: TaskId) -> tuple[str, ...]:
    """The ids the task's binding holds, as the store holds them."""
    task = load_task(env.session, task_id)
    return tuple(str(bound) for bound in task.bound_source_ids)


# --------------------------------------------------------------------------- #
# it reads, and what it read is in the ledger
# --------------------------------------------------------------------------- #


def test_the_ingestion_puts_the_material_in_the_ledger(env: StoreEnv, workspace_root: Path) -> None:
    """The material the workspace holds is in the ledger afterwards."""
    (workspace_root / "materials" / "one.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    context = _context(env, workspace_root, _inventory_only())

    result = ingest_material(context, now=_MOMENT)

    ledger = {source.source_id for source in store_list_sources(env.session)}
    assert set(result.source_ids) <= ledger
    assert result.source_ids


def test_the_source_ids_are_the_ids_the_store_uses(env: StoreEnv, workspace_root: Path) -> None:
    """``src-<hex>``, the shape the store's binding means.

    A binding that holds an id the ingestion path could never have minted is
    a binding that names nothing, so the shape is part of the contract rather
    than an accident of the hash.
    """
    (workspace_root / "materials" / "one.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    context = _context(env, workspace_root, _inventory_only())

    result = ingest_material(context, now=_MOMENT)

    assert result.source_ids
    for source_id in result.source_ids:
        assert _SOURCE_ID.match(source_id), f"{source_id!r} is not a source id"
    # And the task's own binding type accepts them.
    assert all(SourceId(source_id) for source_id in result.source_ids)


# --------------------------------------------------------------------------- #
# the task holds the material
# --------------------------------------------------------------------------- #


def test_the_task_holds_the_material_the_operation_ingested(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The binding is the task's, and the layer reads it back.

    A task that claims material it does not hold is a binding that cannot be
    honoured, so this is asserted through the layer's own listing rather than
    through the value the operation returned.
    """
    (workspace_root / "materials" / "one.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    context = _context(env, workspace_root, _inventory_only())

    result = ingest_material(context, now=_MOMENT)

    assert result.bound_source_ids == result.source_ids
    task = load_task(env.session, context.task_id)
    assert tuple(str(bound) for bound in task.bound_source_ids) == result.source_ids
    assert [view.source.source_id for view in list_sources(context)] == list(result.source_ids)


def test_the_binding_is_written_with_an_event(env: StoreEnv, workspace_root: Path) -> None:
    """A binding is a state change, and the log records it.

    ADR-0003 C3: the state row and the event that describes it commit
    together. A binding with no event would be a change nobody was told
    about.
    """
    (workspace_root / "materials" / "one.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    context = _context(env, workspace_root, _inventory_only())
    before = count_events(env.session, context.task_id)

    ingest_material(context, now=_MOMENT)

    assert count_events(env.session, context.task_id) == before + 1


# --------------------------------------------------------------------------- #
# the binding accumulates
# --------------------------------------------------------------------------- #


def test_the_task_keeps_the_material_the_operator_removed(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The operator removed a file; the task still holds it.

    The binding is the task's, and material it was given is not taken back
    because it left the workspace. The loss this closes was **silent**: the
    binding was replaced by what the run ingested, so the task forgot the
    material and nothing in the report said the binding had shrunk.
    """
    materials = workspace_root / "materials"
    (materials / "one.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (materials / "two.csv").write_text("c,d\n3,4\n", encoding="utf-8")
    context = _context(env, workspace_root, _inventory_only())

    first = ingest_material(context, now=_MOMENT)
    by_path = {item.source.relative_path: item.source.source_id for item in first.files}
    removed_id = by_path["materials/two.csv"]
    (materials / "two.csv").unlink()

    ingest_material(context, now=_MOMENT + timedelta(days=1))

    assert removed_id in _held(env, context.task_id), "the task forgot the material it held"
    # And the ledger still holds it, so the binding is not a name for nothing.
    assert removed_id in {source.source_id for source in store_list_sources(env.session)}
    # And the layer can still list it: a task whose report rests on material
    # the operator removed is still a task whose report can be built.
    assert removed_id in {view.source.source_id for view in list_sources(context)}


def test_the_report_names_what_the_task_holds_and_what_this_run_ingested(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The two lists are two facts, and they are not the same list.

    A report carrying one list for both would say that what the task rests on
    is what this run read — which stops being true the moment the task holds
    material this run did not touch.
    """
    materials = workspace_root / "materials"
    (materials / "one.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (materials / "two.csv").write_text("c,d\n3,4\n", encoding="utf-8")
    context = _context(env, workspace_root, _inventory_only())

    first = ingest_material(context, now=_MOMENT)
    by_path = {item.source.relative_path: item.source.source_id for item in first.files}
    (materials / "two.csv").unlink()

    second = ingest_material(context, now=_MOMENT + timedelta(days=1))

    # What this run ingested is exactly what it read.
    assert second.source_ids == tuple(item.source.source_id for item in second.files)
    assert by_path["materials/two.csv"] not in second.source_ids
    # What the task holds is what the store holds.
    assert second.bound_source_ids == _held(env, context.task_id)
    # And the two differ, because the task holds material this run did not touch.
    assert second.bound_source_ids != second.source_ids
    assert by_path["materials/two.csv"] in second.bound_source_ids


def test_a_task_is_bound_to_its_own_material_and_not_to_the_whole_ledger(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The union is with what the task held, not with everything in the ledger.

    The ledger is the workspace's: another task's material sits in it too. A
    binding that reached for the whole ledger would hand a task material it
    neither ingested nor was given — and the report would say it holds it.
    """
    first_dir = workspace_root / "first"
    second_dir = workspace_root / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    (first_dir / "one.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (second_dir / "two.csv").write_text("c,d\n3,4\n", encoding="utf-8")

    one = _context(env, workspace_root, _inventory_only(), source_dirs=(first_dir,))
    two = _context(env, workspace_root, _inventory_only(), source_dirs=(second_dir,))

    first = ingest_material(one, now=_MOMENT)
    second = ingest_material(two, now=_MOMENT)

    assert set(first.source_ids).isdisjoint(second.source_ids)
    assert set(first.source_ids).isdisjoint(second.bound_source_ids)
    assert second.bound_source_ids == _held(env, two.task_id)


def test_the_binding_keeps_the_order_the_task_bound_the_material_in(
    env: StoreEnv, workspace_root: Path
) -> None:
    """What the task already held stays where it was; what is new comes after.

    A binding's order is the order the researcher bound the material in, and
    the union is not allowed to reshuffle it: a union that did would be a
    revision of a state that did not move.
    """
    materials = workspace_root / "materials"
    (materials / "one.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (materials / "two.csv").write_text("c,d\n3,4\n", encoding="utf-8")
    context = _context(env, workspace_root, _inventory_only())

    ingest_material(context, now=_MOMENT)
    held = _held(env, context.task_id)
    assert len(held) == 2

    (materials / "three.csv").write_text("e,f\n5,6\n", encoding="utf-8")
    second = ingest_material(context, now=_MOMENT + timedelta(days=1))

    added = next(
        item.source.source_id
        for item in second.files
        if item.source.relative_path.endswith("three.csv")
    )
    assert second.bound_source_ids[:2] == held
    assert second.bound_source_ids[2:] == (added,)
    assert second.bound_source_ids == _held(env, context.task_id)


# --------------------------------------------------------------------------- #
# idempotence
# --------------------------------------------------------------------------- #


def test_running_the_ingestion_twice_writes_nothing_the_second_time(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The same material, ingested again, changes nothing.

    Two things are asserted: the rows are not duplicated, and no second event
    is emitted. The event matters as much as the rows — a log that recorded a
    revision for a state that did not move would say the task changed when it
    did not.
    """
    (workspace_root / "materials" / "one.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    context = _context(env, workspace_root, _inventory_only())

    first = ingest_material(context, now=_MOMENT)
    sources_after_first = _count(env.session, "sources")
    texts_after_first = _count(env.session, "source_texts")
    events_after_first = count_events(env.session, context.task_id)
    assert texts_after_first > 0

    second = ingest_material(context, now=_MOMENT + timedelta(days=1))

    assert second.source_ids == first.source_ids
    assert all(item.rows_written == 0 for item in second.files)
    assert _count(env.session, "sources") == sources_after_first
    assert _count(env.session, "source_texts") == texts_after_first
    assert count_events(env.session, context.task_id) == events_after_first


def test_ingesting_unchanged_material_again_emits_no_second_revision(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The union does not turn a no-op into a revision.

    A revision says the binding moved. The binding did not move: the task
    already held what the run brought, so the union is the list that was
    already there, and the store — which writes what it is given and reports
    a revision only when the list it was given is not the list it held — has
    nothing to record.
    """
    (workspace_root / "materials" / "one.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    context = _context(env, workspace_root, _inventory_only())

    ingest_material(context, now=_MOMENT)
    assert _revisions(env.session, context.task_id) == 1
    held = _held(env, context.task_id)

    ingest_material(context, now=_MOMENT + timedelta(days=1))

    assert _revisions(env.session, context.task_id) == 1
    assert _held(env, context.task_id) == held


def test_an_edited_file_is_ingested_under_its_new_hash(env: StoreEnv, workspace_root: Path) -> None:
    """The same location keeps its id, and its recorded hash moves.

    The id is derived from where the material lives, not from what it says,
    so an edit is a refresh rather than a new material — which is what makes
    the drift detection have something to detect against.
    """
    material = workspace_root / "materials" / "one.csv"
    material.write_text("a,b\n1,2\n", encoding="utf-8")
    context = _context(env, workspace_root, _inventory_only())
    first = ingest_material(context, now=_MOMENT)

    material.write_text("a,b\n3,4\n", encoding="utf-8")
    second = ingest_material(context, now=_MOMENT + timedelta(days=1))

    assert second.source_ids == first.source_ids
    assert first.files[0].source.content_sha256 != second.files[0].source.content_sha256
    assert second.files[0].rows_written > 0
    # And the binding still names **one** material: an edited file is the same
    # material at a new version, not a second material beside it.
    assert second.bound_source_ids == first.bound_source_ids
    assert len(second.bound_source_ids) == 1


# --------------------------------------------------------------------------- #
# what it reports
# --------------------------------------------------------------------------- #


def test_a_file_that_could_not_be_stored_is_reported_not_swallowed(
    env: StoreEnv, workspace_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One file that cannot be stored does not stop the others, and is named.

    The failure is **arranged** now, and the arrangement changed because the
    property it protected is no longer reachable by accident. It used to be
    real: two source roots holding a file of the same name produced the same
    ``relative_path``, the ledger's UNIQUE constraint refused the second one,
    and the operation had to say so.

    The walk now records the **workspace-relative** path, so two roots
    holding a file of the same name are two different rows and nothing
    collides. What is left to arrange is a store that refuses a row, and the
    property is the same: a failure the caller cannot see is a report that
    says the workspace was fine.
    """
    import labcairn.material.walk as walk_module
    from labcairn.material.ingest import ingest_into_store as real_ingest_into_store

    (workspace_root / "materials" / "one.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (workspace_root / "materials" / "two.csv").write_text("c,d\n3,4\n", encoding="utf-8")
    context = _context(env, workspace_root, _inventory_only())

    # walk.py does ``from ...ingest import ingest_into_store``, so the name it
    # calls is bound in *its* namespace. Patch there, not on the source
    # module, or the patch never lands.
    def refusing(session: Any, data: bytes, **kwargs: Any) -> Any:
        if kwargs.get("relative_path", "").endswith("one.csv"):
            raise RuntimeError("the store refused this row")
        return real_ingest_into_store(session, data, **kwargs)

    monkeypatch.setattr(walk_module, "ingest_into_store", refusing)

    result = ingest_material(context, now=_MOMENT)

    assert len(result.failures) == 1, result.failures
    assert result.failures[0].relative_path == "one.csv"
    assert result.failures[0].reason
    assert len(result.source_ids) == 1


def test_a_denied_subtree_is_invisible(env: StoreEnv, workspace_root: Path) -> None:
    """A denied subtree produces no row, no failure, and no name.

    The last of those is the one that matters: a failure list that named a
    denied file would teach the caller that it exists, which is exactly what
    ADR-0003 §C5 forbids.
    """
    materials = workspace_root / "materials"
    (materials / "private").mkdir()
    (materials / "private" / "secret.md").write_text("a secret\n", encoding="utf-8")
    (materials / "open.md").write_text("# Open\n", encoding="utf-8")
    policy = _inventory_only(Rule(effect=Permission.DENY, pattern="private/**"))
    context = _context(env, workspace_root, policy)

    result = ingest_material(context, now=_MOMENT)

    assert [item.source.relative_path for item in result.files] == ["materials/open.md"]
    assert result.failures == ()
    reported = json.dumps(result.model_dump(mode="json"))
    assert "secret" not in reported, "the report named a file the policy denied"


def test_unreadable_empty_and_readable_material_are_kept_apart(
    env: StoreEnv, workspace_root: Path
) -> None:
    """ "We could not look" is not "there was nothing there".

    Three files, three facts: a readable one, an empty one, and a container
    that would not open. The totals are counted from the files, so a count
    that disagreed with the list it counts would fail here.
    """
    materials = workspace_root / "materials"
    (materials / "open.md").write_text("# Open\n\nsome text\n", encoding="utf-8")
    (materials / "empty.md").write_text("", encoding="utf-8")
    (materials / "broken.pdf").write_bytes(b"%PDF-1.4 this is not a pdf at all")
    context = _context(env, workspace_root, _inventory_only())

    result = ingest_material(context, now=_MOMENT)

    by_path = {item.source.relative_path.rsplit("/", 1)[-1]: item for item in result.files}
    assert by_path["open.md"].source.readability is SourceReadability.READABLE
    assert by_path["open.md"].empty is False
    assert by_path["empty.md"].source.readability is SourceReadability.READABLE
    assert by_path["empty.md"].empty is True
    assert by_path["broken.pdf"].source.readability is SourceReadability.UNPARSEABLE
    assert by_path["broken.pdf"].source.readability_disclosure
    assert result.readable == 2
    assert result.empty == 1
    assert result.unreadable == 1
    # The totals are the files' own facts, not a number kept beside them.
    assert result.readable + result.unreadable == len(result.files)


# --------------------------------------------------------------------------- #
# the refusals
# --------------------------------------------------------------------------- #


def test_a_workspace_with_no_source_root_is_refused(env: StoreEnv, workspace_root: Path) -> None:
    """There is no material to ingest, and the operation says so.

    A refusal rather than an empty report: "the workspace binds no source
    root" and "the workspace has no material" are different facts, and only
    the first one is true.
    """
    context = _context(env, workspace_root, _inventory_only(), source_dirs=())

    with pytest.raises(ApplicationRefusedError) as caught:
        ingest_material(context, now=_MOMENT)

    assert caught.value.reason is ApplicationRefusal.PATH_REFUSED
    assert "source root" in caught.value.detail


def test_a_policy_that_asks_about_the_material_is_refused(
    env: StoreEnv, workspace_root: Path
) -> None:
    """An ask is a question, and this operation has no approval to answer it.

    The refusal comes **before** the walk, so nothing was read: the ledger
    holds no source afterwards.
    """
    (workspace_root / "materials" / "one.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    policy = PermissionPolicy.from_rules(
        [
            Rule(
                effect=Permission.ASK,
                pattern="**",
                capabilities=frozenset({CapabilityId.SOURCE_INVENTORY.value}),
            )
        ]
    )
    context = _context(env, workspace_root, policy)

    with pytest.raises(ApplicationRefusedError) as caught:
        ingest_material(context, now=_MOMENT)

    assert caught.value.reason is ApplicationRefusal.POLICY_ASKED
    assert store_list_sources(env.session) == ()


def test_a_task_the_store_does_not_hold_is_refused(env: StoreEnv, workspace_root: Path) -> None:
    """The store's own refusal is translated into this layer's one.

    A surface catches one exception and not two, so the store's
    ``UnknownTaskError`` becomes the layer's ``TASK_NOT_FOUND``.
    """
    from labcairn.core.ids import new_id
    from labcairn.workspace.roots import Workspace

    (workspace_root / "materials" / "one.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    context = _context(env, workspace_root, _inventory_only())
    missing = ApplicationContext(
        workspace=Workspace.bind(
            workspace_root,
            task_id=TaskId(new_id()),
            source_dirs=(workspace_root / "materials",),
        ),
        store=context.store,
        policy=context.policy,
        ledger=context.ledger,
    )

    with pytest.raises(ApplicationRefusedError) as caught:
        ingest_material(missing, now=_MOMENT)

    assert caught.value.reason is ApplicationRefusal.TASK_NOT_FOUND
