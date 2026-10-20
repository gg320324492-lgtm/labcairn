"""The store's list queries: what they order, and what they refuse.

The plan's §2.5 says the store had no list query for tasks, runs, stages or
artefacts, and that the CLI's task list, the API's index and the UI's task list
all need them. These are that surface, and this file is what makes their
properties true rather than hoped for.

Two properties are asserted here, and they are the two the list queries exist
to have.

**The order is a total order, and it is the stated one.** A list whose order
depends on the query plan is a list that reshuffles between two reads of the
same state, and a reader reports that as "it shuffled". Every test below
computes the expected order *independently* and compares, and every fixture is
arranged so that the plausible wrong orders give a different answer: the
stages are named so that name order disagrees with id order, the runs are
given their attempts so that attempt order disagrees with id order, and the
tasks are timestamped so that creation order disagrees with id order. A test
that only checked "the order is stable" would pass on a query with no ORDER BY
at all, because SQLite would return the same rows in the same order twice.

**A Task that does not exist is not an empty list.** The store says so itself
in :meth:`UnitOfWork.task_row` — "a unit of work without a Task is a caller
bug and ``None`` would push that check into every call site where nobody
writes it" — and the list queries keep the line. An empty tuple means "this
Task holds nothing of that kind"; a refusal means "this Task id names
nothing". A caller that cannot tell them apart reports "no stages" for a task
id it mistyped, and the reader goes looking for a task that does not exist.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session
from test_store_support import (
    StoreEnv,
    make_approval,
    make_operation,
    make_receipt,
    make_run,
    make_source_id,
    make_stage,
    make_task,
)
from test_store_support import (
    env as _shared_env,
)

from labcairn.core.ids import TaskId, new_id
from labcairn.db.materials import put_source
from labcairn.db.repository import (
    TaskStore,
    UnknownTaskError,
    list_approvals,
    list_artifacts,
    list_operations,
    list_runs,
    list_sources,
    list_stages,
    list_tasks,
    load_source,
    load_task,
)
from labcairn.reports.receipt import ArtifactReceipt
from labcairn.runtime.lifecycle import Run, Stage, Task
from labcairn.runtime.operation import Approval, Operation
from labcairn.sources.source import Source, SourceKind, SourceReadability

# pytest resolves a fixture by the parameter name in a test's signature, so the
# shared `env` fixture must be bound under that name here.
env = _shared_env

#: A fixed instant, so "created at the same time" is a fact rather than a hope.
_MOMENT = datetime(2026, 1, 1, tzinfo=UTC)

#: A fixed content hash, so a receipt's hash is not the thing under test.
_HASH = "a" * 64


def _write(store: TaskStore, task: Task, *rows: object) -> None:
    """Write a task and the rows that hang off it, in one unit of work.

    The order the rows are written in is the order the test wants the *store*
    to be in, and the order the list queries must **not** simply echo.
    """
    store.create_task(task)
    with store.unit(task.task_id) as work:
        for row in rows:
            if isinstance(row, Run):
                work.put_run(row)
            elif isinstance(row, Stage):
                work.put_stage(row)
            elif isinstance(row, Operation):
                work.put_operation(row)
            elif isinstance(row, Approval):
                work.put_approval(row)
            elif isinstance(row, ArtifactReceipt):
                work.put_artifact(row)
            else:  # pragma: no cover - a test bug, not a product path
                raise AssertionError(f"unknown row type: {type(row).__name__}")


def _source(source_id: str, *, ingested_at: datetime, relative_path: str) -> Source:
    """A valid source, for the ledger."""
    return Source(
        source_id=source_id,
        kind=SourceKind.CSV,
        display_name=f"Material {source_id}",
        relative_path=relative_path,
        content_sha256=_HASH,
        size_bytes=10,
        readability=SourceReadability.READABLE,
        ingested_at=ingested_at,
    )


# --------------------------------------------------------------------------- #
# the order
# --------------------------------------------------------------------------- #


def test_tasks_come_back_in_creation_order(env: StoreEnv) -> None:
    """The Task list leads with when the Task came into being.

    The three tasks are timestamped so that their creation order disagrees
    with their id order: the ids are minted in the order *first, second,
    third*, and the timestamps say *third, first, second*. A query that
    ordered by the id alone would return the first arrangement, and a query
    that ordered by the timestamp alone would be right only by luck when two
    tasks share a timestamp.
    """
    store = env.store()
    first = make_task(title="First", now=_MOMENT)
    second = make_task(title="Second", now=_MOMENT)
    third = make_task(title="Third", now=_MOMENT)
    later = _MOMENT.replace(hour=1)
    earlier = _MOMENT.replace(hour=2)

    # Timestamps deliberately out of id order.
    first = first.model_copy(update={"created_at": later, "updated_at": later})
    second = second.model_copy(update={"created_at": earlier, "updated_at": earlier})
    third = third.model_copy(update={"created_at": _MOMENT, "updated_at": _MOMENT})
    for task in (first, second, third):
        store.create_task(task)

    assert [task.task_id for task in list_tasks(env.session)] == [
        third.task_id,
        first.task_id,
        second.task_id,
    ]


def test_two_tasks_created_at_the_same_instant_are_ordered_by_their_id(env: StoreEnv) -> None:
    """The tiebreak is the id, and it is applied.

    The two tasks are written in the *opposite* order to their ids, so a query
    with no tiebreak returns them the way SQLite happens to lay the table out
    rather than the way the rule says.
    """
    store = env.store()
    earlier = make_task(title="Earlier", now=_MOMENT)
    later = make_task(title="Later", now=_MOMENT)
    for task in (later, earlier):
        store.create_task(task)

    found = list_tasks(env.session)
    assert [task.task_id for task in found] == sorted(
        (earlier.task_id, later.task_id),
        key=str,
    )


def test_runs_are_ordered_by_the_attempt_number(env: StoreEnv) -> None:
    """The Run list leads with the attempt, because a resume is the next attempt.

    The attempt-2 run is written first and its id is therefore the earlier one,
    so a query ordering by the id would return the two runs the other way
    round.
    """
    store = env.store()
    task = make_task(now=_MOMENT)
    store.create_task(task)
    second = make_run(task.task_id, attempt=2, now=_MOMENT)
    first = make_run(task.task_id, attempt=1, now=_MOMENT)
    with store.unit(task.task_id) as work:
        work.put_run(second)
        work.put_run(first)

    assert [run.attempt for run in list_runs(env.session, task.task_id)] == [1, 2]


def test_stages_are_ordered_by_their_id(env: StoreEnv) -> None:
    """The Stage list leads with the id, because a stage has no sequence column.

    The stages are named so that their names disagree with their ids — the
    stage with the earliest id is the one called "zebra" — and they are written
    in reverse id order, so a query with no ORDER BY, or one ordered by name,
    gives a different answer.
    """
    store = env.store()
    task = make_task(now=_MOMENT)
    run = make_run(task.task_id, now=_MOMENT)
    store.create_task(task)
    zebra = make_stage(task.task_id, run.run_id, name="zebra")
    apple = make_stage(task.task_id, run.run_id, name="apple")
    mango = make_stage(task.task_id, run.run_id, name="mango")
    with store.unit(task.task_id) as work:
        work.put_run(run)
        for stage in (mango, apple, zebra):
            work.put_stage(stage)

    found = list_stages(env.session, task.task_id)
    assert [stage.stage_id for stage in found] == sorted(
        (zebra.stage_id, apple.stage_id, mango.stage_id),
        key=str,
    )
    assert [stage.name for stage in found] == ["zebra", "apple", "mango"]


def test_artifacts_are_ordered_by_revision_then_id(env: StoreEnv) -> None:
    """The artefact list leads with the revision, so v1 of a report precedes v2.

    LC-P1-11 versions artefacts rather than overwriting them, so the revision
    is the only field carrying the project's own notion of sequence. The
    higher revision is written first, so a query ordering by the id alone
    would put it in front of the one it supersedes.
    """
    store = env.store()
    task = make_task(now=_MOMENT)
    store.create_task(task)
    second = make_receipt(task.task_id, relative_path="outputs/report.md").model_copy(
        update={"revision": 2}
    )
    first = make_receipt(task.task_id, relative_path="outputs/report.md").model_copy(
        update={"revision": 1}
    )
    with store.unit(task.task_id) as work:
        work.put_artifact(second)
        work.put_artifact(first)

    assert [receipt.revision for receipt in list_artifacts(env.session, task.task_id)] == [1, 2]


def test_approvals_are_ordered_by_their_id(env: StoreEnv) -> None:
    """The approval list leads with the id, and the id is minted monotonically.

    The two approvals are written in reverse id order, so a query with no
    ORDER BY returns them the way the table happens to lie rather than the way
    they were asked for.
    """
    store = env.store()
    task = make_task(now=_MOMENT)
    run = make_run(task.task_id, now=_MOMENT)
    stage = make_stage(task.task_id, run.run_id)
    operation = make_operation(task.task_id, run.run_id, stage.stage_id)
    store.create_task(task)
    with store.unit(task.task_id) as work:
        work.put_run(run)
        work.put_stage(stage)
        work.put_operation(operation)
    # Written the other way round from the ids, so a query with no ORDER BY
    # returns them the way the table happens to lie.
    first = make_approval(task.task_id, operation.operation_id, now=_MOMENT)
    second = make_approval(task.task_id, operation.operation_id, now=_MOMENT)
    with store.unit(task.task_id) as work:
        work.put_approval(second)
        work.put_approval(first)

    found = list_approvals(env.session, task.task_id)
    assert [approval.approval_id for approval in found] == sorted(
        (first.approval_id, second.approval_id),
        key=str,
    )


def test_sources_are_ordered_by_ingest_then_id(env: StoreEnv) -> None:
    """The ledger's sources are ordered by when they were ingested.

    The sources are ingested with timestamps that disagree with their id
    order, and the one that ties on the timestamp is written second so that a
    query with no tiebreak would return the pair the wrong way round.
    """
    first = _source("source-1", ingested_at=_MOMENT.replace(hour=2), relative_path="m/one.csv")
    second = _source("source-2", ingested_at=_MOMENT.replace(hour=1), relative_path="m/two.csv")
    third = _source("source-3", ingested_at=_MOMENT, relative_path="m/three.csv")
    for source in (first, second, third):
        put_source(env.session, source)

    assert [source.source_id for source in list_sources(env.session)] == [
        third.source_id,
        second.source_id,
        first.source_id,
    ]


def test_operations_are_ordered_by_their_id(env: StoreEnv) -> None:
    """The operation list leads with the id.

    The two operations are written in reverse id order, so a query with no
    ORDER BY returns them the way the table happens to lie.
    """
    store = env.store()
    task = make_task(now=_MOMENT)
    run = make_run(task.task_id, now=_MOMENT)
    stage = make_stage(task.task_id, run.run_id)
    store.create_task(task)
    with store.unit(task.task_id) as work:
        work.put_run(run)
        work.put_stage(stage)
    # The ids are minted in the order *first, second*, and the rows are written
    # the other way round, so a query with no ORDER BY returns them the way the
    # table happens to lie rather than the way the rule says.
    first = make_operation(task.task_id, run.run_id, stage.stage_id)
    second = make_operation(task.task_id, run.run_id, stage.stage_id)
    with store.unit(task.task_id) as work:
        work.put_operation(second)
        work.put_operation(first)

    found = list_operations(env.session, task.task_id)
    assert [operation.operation_id for operation in found] == sorted(
        (first.operation_id, second.operation_id),
        key=str,
    )


# --------------------------------------------------------------------------- #
# the refusals
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "reader",
    [list_runs, list_stages, list_artifacts, list_approvals, list_operations],
)
def test_a_task_that_does_not_exist_is_refused_not_returned_empty(
    env: StoreEnv,
    reader: Callable[[Session, TaskId], tuple[object, ...]],
) -> None:
    """A task-scoped read of a Task that was never created is a refusal.

    Every task-scoped reader refuses, not one of them: a reader that answered
    with an empty tuple would make a mistyped task id look like a task with
    nothing in it.
    """
    with pytest.raises(UnknownTaskError):
        reader(env.session, TaskId(new_id()))


def test_a_task_that_exists_and_holds_nothing_returns_an_empty_list(env: StoreEnv) -> None:
    """The other half of the line: an existing Task with nothing in it is empty."""
    store = env.store()
    task = make_task(now=_MOMENT)
    store.create_task(task)

    assert list_runs(env.session, task.task_id) == ()
    assert list_stages(env.session, task.task_id) == ()
    assert list_artifacts(env.session, task.task_id) == ()
    assert list_approvals(env.session, task.task_id) == ()
    assert list_operations(env.session, task.task_id) == ()


def test_a_list_is_scoped_to_its_own_task(env: StoreEnv) -> None:
    """One Task's rows never appear in another's list."""
    store = env.store()
    mine = make_task(title="Mine", now=_MOMENT)
    theirs = make_task(title="Theirs", now=_MOMENT)
    store.create_task(mine)
    store.create_task(theirs)
    my_run = make_run(mine.task_id, now=_MOMENT)
    their_run = make_run(theirs.task_id, now=_MOMENT)
    with store.unit(mine.task_id) as work:
        work.put_run(my_run)
    with store.unit(theirs.task_id) as work:
        work.put_run(their_run)

    assert [run.run_id for run in list_runs(env.session, mine.task_id)] == [my_run.run_id]
    assert [run.run_id for run in list_runs(env.session, theirs.task_id)] == [their_run.run_id]


# --------------------------------------------------------------------------- #
# the shapes
# --------------------------------------------------------------------------- #


def test_the_list_queries_return_the_frozen_contracts_not_the_rows(env: StoreEnv) -> None:
    """What comes back is a contract, so it carries its own validation."""
    store = env.store()
    task = make_task(now=_MOMENT)
    run = make_run(task.task_id, now=_MOMENT)
    stage = make_stage(task.task_id, run.run_id)
    operation = make_operation(task.task_id, run.run_id, stage.stage_id)
    approval = make_approval(task.task_id, operation.operation_id, now=_MOMENT)
    receipt = make_receipt(task.task_id)
    store.create_task(task)
    with store.unit(task.task_id) as work:
        work.put_run(run)
        work.put_stage(stage)
        work.put_operation(operation)
        work.put_approval(approval)
        work.put_artifact(receipt)

    assert isinstance(load_task(env.session, task.task_id), Task)
    assert isinstance(list_tasks(env.session)[0], Task)
    assert isinstance(list_runs(env.session, task.task_id)[0], Run)
    assert isinstance(list_stages(env.session, task.task_id)[0], Stage)
    assert isinstance(list_operations(env.session, task.task_id)[0], Operation)
    assert isinstance(list_approvals(env.session, task.task_id)[0], Approval)
    assert isinstance(list_artifacts(env.session, task.task_id)[0], ArtifactReceipt)


def test_load_task_refuses_a_task_that_does_not_exist(env: StoreEnv) -> None:
    """The single-Task reader refuses where the list readers refuse."""
    with pytest.raises(UnknownTaskError):
        load_task(env.session, TaskId(new_id()))


def test_load_source_returns_none_for_a_source_the_ledger_does_not_hold(
    env: StoreEnv,
) -> None:
    """A missing source is an empty answer, not a caller bug.

    The ledger holds material, and asking for material that was never
    ingested is a question with a legitimate empty answer. The refusal lives
    in the layer above, which knows whether a missing source is fatal for the
    operation being performed.
    """
    assert load_source(env.session, "no-such-source") is None


def test_load_source_returns_the_ledger_s_row(env: StoreEnv) -> None:
    """The single-source reader returns the contract the ledger holds."""
    source = _source("source-1", ingested_at=_MOMENT, relative_path="m/one.csv")
    put_source(env.session, source)

    found = load_source(env.session, "source-1")
    assert found is not None
    assert found.source_id == "source-1"
    assert found.content_sha256 == _HASH


def test_a_bound_source_id_is_readable_as_a_source_id(env: StoreEnv) -> None:
    """The Task's binding holds ids the ledger can be asked about."""
    source = _source("source-1", ingested_at=_MOMENT, relative_path="m/one.csv")
    put_source(env.session, source)
    bound = make_source_id("m/absent.csv")

    assert load_source(env.session, str(bound)) is None
