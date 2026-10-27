"""The ``SourceId`` type must agree with the ids the tree actually mints.

A source id is location-derived text -- ``src-`` followed by sixteen lowercase
hex characters -- and not a UUID. The type saying otherwise was a lie with
consequences: a Task could not bind a material that existed, and the store's
read path parsed the stored value as a UUID, so any row holding a real id
raised ``ValueError`` on read.

These tests hold the type to the data. Where the property is about
persistence they drive the **store** rather than a hand-built model, because a
type that only agrees with a model in memory is not yet a type the ledger can
hold.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from test_store_support import StoreEnv
from test_store_support import env as _shared_env

from labcairn.core.ids import SourceId
from labcairn.db.materials import put_source
from labcairn.db.models import TaskRow
from labcairn.db.repository import load_source, load_task
from labcairn.material import ingest_bytes
from labcairn.runtime.lifecycle import Task, TaskGoal
from labcairn.sources.source import Source

pytestmark = pytest.mark.unit

# pytest resolves a fixture by the parameter name in a test's signature, so the
# shared `env` fixture must be bound under that name here.
env = _shared_env

_MOMENT = datetime(2026, 1, 1, tzinfo=UTC)


def _ingested(relative_path: str = "materials/one.csv") -> Source:
    """A material ingested the way the product ingests one.

    The id comes out of the ingestion path rather than being written here, so
    a test that binds it is binding the id the product would really mint.
    """
    material = ingest_bytes(
        b"a,b\n1,2\n",
        relative_path=relative_path,
        display_name=relative_path.rsplit("/", 1)[-1],
        ingested_at=_MOMENT,
    )
    return material.source


def _task(*bound: SourceId) -> Task:
    """A Task bound to *bound*."""
    return Task(
        title="Bound task",
        goal=TaskGoal(
            objective="Establish whether the observation holds.",
            success_criterion="A cited answer, or an honest 'not established'.",
        ),
        bound_source_ids=bound,
    )


# --------------------------------------------------------------------------- #
# the shape
# --------------------------------------------------------------------------- #


def test_the_id_the_ingestion_path_mints_is_a_source_id() -> None:
    """The type and the minting path agree on the shape.

    If the ingestion path's id form changed and the type did not, this is the
    test that says so -- and it is checked against the id the product
    produces, not against a hand-written one.
    """
    source = _ingested()

    task = _task(SourceId(source.source_id))

    assert [str(value) for value in task.bound_source_ids] == [source.source_id]


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("not-a-source-id", id="no-prefix"),
        pytest.param("material-0123456789abcdef", id="wrong-prefix"),
        pytest.param("src-", id="no-digest"),
        pytest.param("src-0123456789abcde", id="fifteen-characters"),
        pytest.param("src-0123456789abcdef0", id="seventeen-characters"),
        pytest.param("src-0123456789ABCDEF", id="uppercase"),
        pytest.param("src-0123456789abcdeg", id="non-hex"),
        pytest.param("", id="empty"),
    ],
)
def test_a_wrong_shaped_source_id_is_refused(value: str) -> None:
    """The shape is enforced where the value enters a model.

    ``model_validate`` rather than the constructor, because this is the shape
    of the thing that arrives from outside: a payload read back out of the
    store, or a document handed in by a caller. A wrong shape that was only
    documented would sail through both.
    """
    with pytest.raises(ValidationError):
        Task.model_validate(
            {
                "title": "Wrong shape",
                "goal": {"objective": "o", "success_criterion": "s"},
                "bound_source_ids": [value],
            }
        )


# --------------------------------------------------------------------------- #
# the store
# --------------------------------------------------------------------------- #


def test_a_real_source_id_round_trips_through_a_tasks_binding(env: StoreEnv) -> None:
    """The property the whole change exists for.

    A source id the ingestion path really mints is bound to a Task, the Task
    is written to the store, and the Task is read back: the binding must
    survive the round trip and come back as the same id. The read path used to
    parse the stored value as a UUID, so this raised ``ValueError`` on any row
    holding a real id -- which is every row that could have existed.
    """
    source = _ingested()
    put_source(env.session, source)

    task = _task(SourceId(source.source_id))
    env.store().create_task(task)

    row = env.session.execute(
        select(TaskRow).where(TaskRow.task_id == str(task.task_id))
    ).scalar_one()
    assert row.bound_source_ids == [source.source_id]

    loaded = load_task(env.session, task.task_id)
    assert [str(value) for value in loaded.bound_source_ids] == [source.source_id]
    # The binding names a material the ledger holds. Before the fix there was
    # no id that could satisfy this: the type wanted a UUID and the ledger
    # held text.
    assert load_source(env.session, source.source_id) is not None


def test_a_row_holding_a_wrong_shaped_source_id_is_refused_on_read(env: StoreEnv) -> None:
    """The store is the authority, so a row it cannot read raises.

    A binding holding something the ledger could never have minted is not a
    row to be silently repaired: the read raises, because a Task that claims
    a material it cannot produce is worse than an error.
    """
    task = _task(SourceId("src-0123456789abcdef"))
    env.store().create_task(task)

    row = env.session.execute(
        select(TaskRow).where(TaskRow.task_id == str(task.task_id))
    ).scalar_one()
    row.bound_source_ids = ["not-a-source-id"]
    env.session.commit()

    with pytest.raises(ValidationError):
        load_task(env.session, task.task_id)


# --------------------------------------------------------------------------- #
# nominality
# --------------------------------------------------------------------------- #

_PROBE_STR = textwrap.dedent(
    """
    from labcairn.core.ids import SourceId

    def bare_string_is_not_a_source_id(value: str) -> SourceId:
        return value
    """
)

_PROBE_TASK = textwrap.dedent(
    """
    from labcairn.core.ids import SourceId, TaskId

    def a_task_id_is_not_a_source_id(task: TaskId) -> SourceId:
        return task
    """
)

_PROBE_FIELD = textwrap.dedent(
    """
    from labcairn.core.ids import SourceId
    from labcairn.runtime.lifecycle import Task

    def the_binding_is_nominally_typed(task: Task) -> tuple[SourceId, ...]:
        return task.bound_source_ids
    """
)

_PROBE_CONTROL = textwrap.dedent(
    """
    from labcairn.core.ids import TaskId

    def the_control_probe_type_checks(value: str) -> str:
        return value

    def the_control_probe_type_checks_a_task_id(task: TaskId) -> TaskId:
        return task
    """
)


def _mypy(probes: dict[str, str], tmp_path: Path) -> dict[str, list[str]]:
    """Run mypy over *probes* and attribute each error to the file it came from.

    One invocation rather than one per probe: mypy reports every error in
    every file it is given, and each line names the file it came from, so the
    attribution survives without a subprocess per property.
    """
    paths = []
    for name, source in probes.items():
        path = tmp_path / f"{name}.py"
        path.write_text(source, encoding="utf-8")
        paths.append(path)

    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--no-incremental", "--strict", *(str(p) for p in paths)],
        capture_output=True,
        text=True,
        # Both halves of the pipe are stated, and they agree. mypy is a
        # Python program, so its output encoding is otherwise the machine's
        # locale encoding, and every diagnostic names the file it came from,
        # so its output carries the path of every probe. Pinning only the
        # parent would be the same failure with the arrow turned round: mypy
        # would still write the locale's bytes and the parent would read
        # them as UTF-8.
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
        timeout=300,
    )

    errors: dict[str, list[str]] = {name: [] for name in probes}
    for line in (result.stdout + result.stderr).splitlines():
        for name in probes:
            # mypy echoes the path it was given, so the file name is what
            # identifies the probe, not the start of the line.
            if f"{name}.py:" in line:
                errors[name].append(line)
    return errors


def test_a_source_id_is_nominal_and_the_binding_is_typed_as_one(tmp_path: Path) -> None:
    """The checker half of "distinct types", asserted by running mypy.

    A bare string must not stand in for a source id, a task id must not stand
    in for one either, and the binding field must be typed as source ids
    rather than as plain strings. The control probe proves the failures below
    are about nominality and not about a broken environment.
    """
    errors = _mypy(
        {
            "probe_str": _PROBE_STR,
            "probe_task": _PROBE_TASK,
            "probe_field": _PROBE_FIELD,
            "probe_control": _PROBE_CONTROL,
        },
        tmp_path,
    )

    assert errors["probe_control"] == [], (
        "a control probe failed; the results below would be meaningless:\n"
        + "\n".join(errors["probe_control"])
    )
    assert errors["probe_str"], "mypy accepted a bare string where a source id was expected"
    assert "SourceId" in "\n".join(errors["probe_str"]), "\n".join(errors["probe_str"])
    assert errors["probe_task"], "mypy accepted a task id where a source id was expected"
    assert "TaskId" in "\n".join(errors["probe_task"]), "\n".join(errors["probe_task"])
    assert errors["probe_field"] == [], (
        "the binding field is not typed as source ids:\n" + "\n".join(errors["probe_field"])
    )
