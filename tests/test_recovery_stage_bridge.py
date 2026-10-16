"""The bridge between the Skill's stage names and the runtime's stage ids.

LC-P1-06 and LC-P1-07 were built by two agents that never read each other, and
they disagreed about what identifies a stage: the workflow names stages with a
closed enum, the runtime identifies them with a UUID because a stage row belongs
to one Run. Neither is wrong — a name is the right key for a declared workflow,
a UUID is the right key for a row — and the store holds both columns.

These tests hold the conversion, including the two ways it could silently bridge
the wrong thing.
"""

from __future__ import annotations

import pytest
from test_store_support import env  # noqa: F401 - registers the fixture for this module

from labcairn.core.ids import RunId, StageId, TaskId, new_id
from labcairn.db.repository import TaskStore
from labcairn.recovery.stages import (
    UnknownStageError,
    checkpoint_from_stage_boundary,
    stage_id_for,
)
from labcairn.runtime.event import EventTransition
from labcairn.runtime.lifecycle import Run, RunStatus, Stage, StageStatus, Task, TaskGoal


@pytest.fixture
def store_env(env):  # type: ignore[no-untyped-def]  # noqa: F811
    """A task with two runs, each carrying a stage of the same name."""
    store: TaskStore = env.store()
    task = Task(
        task_id=TaskId(new_id()),
        title="bridge",
        goal=TaskGoal(objective="o", success_criterion="s"),
    )
    store.create_task(task)
    runs: dict[str, tuple[RunId, StageId]] = {}
    for label in ("first", "second"):
        run_id, stage_id = RunId(new_id()), StageId(new_id())
        with store.unit(task.task_id) as w:
            w.put_run(Run(task_id=task.task_id, run_id=run_id, status=RunStatus.RUNNING))
            w.put_stage(
                Stage(
                    task_id=task.task_id,
                    run_id=run_id,
                    stage_id=stage_id,
                    name="draft",
                    status=StageStatus.ENTERED,
                )
            )
        runs[label] = (run_id, stage_id)
    return store, task, runs


def test_a_stage_name_resolves_to_the_row_it_names(store_env) -> None:  # type: ignore[no-untyped-def]
    store, _, runs = store_env
    run_id, stage_id = runs["first"]
    assert stage_id_for(store.session, run_id, "draft") == stage_id


def test_the_same_name_in_another_run_resolves_elsewhere(store_env) -> None:  # type: ignore[no-untyped-def]
    """A name-only lookup would bridge two different attempts.

    Both runs have a stage called ``draft``. A lookup that ignored the run would
    return whichever row came first and a checkpoint would be recorded against
    the wrong attempt — durable, plausible, and wrong.
    """
    store, _, runs = store_env
    first_run, first_stage = runs["first"]
    second_run, second_stage = runs["second"]
    assert first_stage != second_stage
    assert stage_id_for(store.session, first_run, "draft") == first_stage
    assert stage_id_for(store.session, second_run, "draft") == second_stage


def test_an_unknown_stage_name_is_an_error_not_a_missing_value(store_env) -> None:  # type: ignore[no-untyped-def]
    """The caller is about to write a durable record; a silent ``None`` would
    become a checkpoint attributing a boundary to nothing."""
    store, _, runs = store_env
    run_id, _ = runs["first"]
    with pytest.raises(UnknownStageError, match="no stage named"):
        stage_id_for(store.session, run_id, "a-stage-that-does-not-exist")


def test_a_boundary_becomes_a_checkpoint_against_the_right_row(store_env) -> None:  # type: ignore[no-untyped-def]
    store, task, runs = store_env
    run_id, stage_id = runs["first"]
    material = ("a" * 64,)
    checkpoint = checkpoint_from_stage_boundary(
        store.session,
        task_id=task.task_id,
        run_id=run_id,
        stage_name="draft",
        through_seq=7,
        material_hashes=material,
    )
    assert checkpoint.stage_id == stage_id
    assert checkpoint.through_seq == 7
    assert checkpoint.material_hashes == material
    assert checkpoint.task_id == task.task_id
    assert checkpoint.run_id == run_id


def test_through_seq_comes_from_the_caller_not_from_a_read(store_env) -> None:  # type: ignore[no-untyped-def]
    """ADR-0003 C1 makes ``seq`` the only ordering, so it must come from the
    transaction that wrote the events being checkpointed.

    The bridge therefore takes it as a parameter rather than deriving it. This
    test pins that: append events, checkpoint at a stated seq, and confirm the
    value stored is the one passed rather than "however far the log happens to
    have got".
    """
    store, task, runs = store_env
    run_id, _ = runs["first"]
    for _ in range(3):
        with store.unit(task.task_id) as w:
            w.emit(
                "stage_entered",
                run_id=run_id,
                transition=EventTransition(from_state="pending", to_state="entered"),
            )
    checkpoint = checkpoint_from_stage_boundary(
        store.session,
        task_id=task.task_id,
        run_id=run_id,
        stage_name="draft",
        through_seq=2,
    )
    # The log has more than two events; the checkpoint covers two, because that
    # is what the caller stated covered the boundary.
    assert checkpoint.through_seq == 2
