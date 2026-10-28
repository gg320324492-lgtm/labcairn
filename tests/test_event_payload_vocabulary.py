"""A payload schema belongs to the vocabulary, not to the writer's import.

ADR-0007's registry turns a payload into a checked shape, but an entry exists
only once the module that declares it has been imported. The reader —
:func:`labcairn.db.repository.events_after` — imports
:mod:`labcairn.runtime.event` and not the recovery layer, so a schema
registered as a side effect of importing the coordinator is missing exactly
where the event is read back. The row then validates in the process that wrote
it and fails in every process that only reads, which is the worst shape a
defect can take: the writer's tests are green and the task cannot be loaded.

The read path is therefore exercised **in a fresh interpreter** and required to
work without ``labcairn.recovery`` being loaded at all. A test in this process
cannot make that assertion: pytest collects modules that import the recovery
layer, so the registry here can be populated by a writer the reader lacks.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Mapping

import pytest
from pydantic import ValidationError
from test_store_support import StoreEnv, make_operation, make_run, make_stage, make_task
from test_store_support import env as _shared_env

from labcairn.core.ids import OperationId, RunId, StageId, TaskId, new_id
from labcairn.runtime.event import (
    Event,
    EventTransition,
    EventType,
    ReconciliationPayload,
)
from labcairn.runtime.operation import OperationState

pytestmark = pytest.mark.integration

# The shared fixture, bound under the name the signatures use. See the note in
# tests/test_recovery_crash_matrix.py for why this is an alias and not an
# import under the fixture's own name.
env = _shared_env

#: What the coordinator writes for a reconciled operation, minus anything it
#: could only know from a probe. The point is the shape, not the verdict.
_RESOLVED = ReconciliationPayload(resolution="confirmed", verdict="match", reached_by="probe")

#: A reader that never names the recovery layer: it opens the store, reads the
#: task's events, and reports what came back and what the interpreter loaded.
_READER = """
import json, sys
from labcairn.core.ids import TaskId
from labcairn.db.repository import events_after
from labcairn.db.session import create_db_engine, create_session_factory

engine = create_db_engine(sys.argv[1])
session = create_session_factory(engine)()
events = events_after(session, TaskId(sys.argv[2]))
print(json.dumps({
    "recovery_loaded": sorted(
        name for name in sys.modules
        if name == "labcairn.recovery" or name.startswith("labcairn.recovery.")
    ),
    "events": [
        {"seq": event.seq, "type": event.type.value, "payload": dict(event.payload)}
        for event in events
    ],
}))
"""

#: A registry question asked without loading anything but the vocabulary.
_REGISTRY = """
import json, sys
from labcairn.runtime.event import EVENT_PAYLOAD_SCHEMAS, EventType
print(json.dumps({
    "recovery_loaded": sorted(
        name for name in sys.modules
        if name == "labcairn.recovery" or name.startswith("labcairn.recovery.")
    ),
    "schema": EVENT_PAYLOAD_SCHEMAS[EventType.OPERATION_RECONCILED].__name__,
}))
"""


def _write_a_reconciled_event(env: StoreEnv) -> tuple[str, dict[str, object]]:
    """Store one ``operation_reconciled`` event through the normal write path."""
    store = env.store()
    task = make_task()
    store.create_task(task)
    run = make_run(task.task_id)
    stage = make_stage(task.task_id, run.run_id)
    operation = make_operation(
        task.task_id, run.run_id, stage.stage_id, state=OperationState.UNCERTAIN
    )
    payload = _RESOLVED.model_dump(mode="json")
    with store.unit(task.task_id) as work:
        work.put_run(run)
        work.put_stage(stage)
        work.put_operation(operation)
        work.emit(
            EventType.OPERATION_RECONCILED,
            run_id=run.run_id,
            stage_id=stage.stage_id,
            operation_id=operation.operation_id,
            transition=EventTransition(
                from_state=OperationState.UNCERTAIN.value, to_state="confirmed"
            ),
            payload=payload,
        )
    return str(task.task_id), payload


def _run_in_fresh_interpreter(program: str, *arguments: str) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, "-c", program, *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert completed.returncode == 0, completed.stderr
    decoded: dict[str, object] = json.loads(completed.stdout)
    return decoded


def test_a_process_that_only_reads_decodes_a_reconciled_event(env: StoreEnv) -> None:
    """The event written by the coordinator is readable where nobody wrote it.

    The process below imports ``labcairn.db`` and nothing else, and it is
    required to load no part of ``labcairn.recovery``. Before the schema moved
    to the vocabulary, this read failed with "operation_reconciled has no
    registered payload schema, so its payload must be empty" — a decision the
    reader made about a row it could not have written.
    """
    task_id, written = _write_a_reconciled_event(env)

    # Release the file before another interpreter opens it, and prove nothing
    # this process still holds is what makes the read succeed.
    env.engine.dispose()

    decoded = _run_in_fresh_interpreter(_READER, str(env.db_path), task_id)

    assert decoded["recovery_loaded"] == [], (
        "the read path loaded " + repr(decoded["recovery_loaded"]) + "; the "
        "reader must not need the writer, or the schema's presence here proves "
        "nothing about a process that only reads"
    )
    events = decoded["events"]
    assert isinstance(events, list)
    reconciled = [event for event in events if event["type"] == "operation_reconciled"]
    assert len(reconciled) == 1, f"expected one reconciliation event; got {events!r}"
    assert reconciled[0]["payload"] == written, (
        "the payload the coordinator wrote did not survive the read: "
        f"{reconciled[0]['payload']!r} != {written!r}"
    )


def test_the_registry_holds_the_schema_without_the_writer_being_imported() -> None:
    """The registration is part of loading the vocabulary, judged in isolation."""
    decoded = _run_in_fresh_interpreter(_REGISTRY)

    assert decoded["recovery_loaded"] == [], repr(decoded["recovery_loaded"])
    assert decoded["schema"] == "ReconciliationPayload"


def _document(payload: Mapping[str, object]) -> dict[str, object]:
    """One valid reconciled event with *payload* substituted in."""
    return {
        "event_id": str(new_id()),
        "seq": 1,
        "task_id": str(TaskId(new_id())),
        "run_id": str(RunId(new_id())),
        "stage_id": str(StageId(new_id())),
        "operation_id": str(OperationId(new_id())),
        "type": "operation_reconciled",
        "transition": {"from_state": "uncertain", "to_state": "confirmed"},
        "payload": payload,
    }


def test_a_payload_that_does_not_fit_the_schema_is_refused() -> None:
    """The registry checks content; it is not a permission to carry anything.

    A reader that accepted an unknown key would still decode, and the drift it
    saw would be invisible — the reason ``extra="forbid"`` exists. The empty
    payload is refused for the same reason: before the schema was registered,
    ``{}`` was the only payload this event type could carry, so an event whose
    provenance is gone would have been the *well-typed* one.
    """
    Event.model_validate(_document(_RESOLVED.model_dump(mode="json")))

    for payload in (
        {},
        {"resolution": "confirmed", "verdict": "match"},
        {**_RESOLVED.model_dump(mode="json"), "attempted_by": "someone"},
    ):
        with pytest.raises(ValidationError):
            Event.model_validate(_document(payload))
