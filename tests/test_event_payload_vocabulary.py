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

**And a name belongs to the tree, not to a document.** The same shape, one
level up: ADR-0002 §"Contracts and acceptance tests" calls its test names
*"binding"*, and a binding name that no witness carries is a promise the tree
is not keeping. The witnesses below close four of ADR-0002's absent names,
and the last one in this file watches the ADR's own list: every name it
declares is either witnessed here or listed in the ADR's table of what this
tree does not carry yet.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import get_args

import pytest
from deadline_support import bounded_run
from pydantic import ValidationError
from store_support import StoreEnv, make_operation, make_run, make_stage, make_task
from store_support import env as _shared_env

from labcairn.core.ids import OperationId, RunId, StageId, TaskId, new_id
from labcairn.core.schema import LabCairnModel
from labcairn.runtime.event import (
    EVENT_PAYLOAD_SCHEMAS,
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
    completed = bounded_run(
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


#: The exchange event's schema, asked of the vocabulary in isolation.
#:
#: **The model path is not loaded here** — it is the writer, and the reader
#: must have the schema without it.
_MODEL_REGISTRY = """
import json, sys
from labcairn.runtime.event import EVENT_PAYLOAD_SCHEMAS, EventType
print(json.dumps({
    "model_path_loaded": sorted(
        name for name in sys.modules
        if name == "labcairn.application.model_request"
        or name.startswith("labcairn.application.model_request.")
    ),
    "schema": EVENT_PAYLOAD_SCHEMAS[EventType.MODEL_EXCHANGED].__name__,
}))
"""


def test_the_model_exchanges_schema_is_in_the_readers_reach() -> None:
    """The exchange event's payload is checked where the event is read back.

    **The schema was registered only where the writer was imported** — the
    model path's own module — so a process that only *read* events had no
    schema for the exchange event, and a stored exchange's payload was
    accepted unchecked. The writer's tests were green and the reader was
    blind, which is the shape this file exists to catch.

    **The fix is in the runtime package's own import**, beside the
    trajectory's: the payload models are registered where every reader
    reaches them, not where the writer happens to be.
    """
    decoded = _run_in_fresh_interpreter(_MODEL_REGISTRY)

    assert decoded["model_path_loaded"] == [], repr(decoded["model_path_loaded"])
    assert decoded["schema"] == "ModelExchangePayload"


def test_an_exchange_payload_that_does_not_fit_the_schema_is_refused() -> None:
    """The exchange event's payload is checked, not merely carried.

    Before the schema reached the reader, *any* payload fitted — and an
    exchange event with nothing in it was the well-typed one. The list of
    exchanges is a list, so the empty one is refused here as it is
    everywhere else the schema applies.
    """
    from labcairn.runtime.model_exchange import ModelExchangePayload

    valid = ModelExchangePayload(
        provider="minimax",
        model="a-model",
        destination="https://example.invalid/v1",
        exchanges=[{"provider_attempts": 1}],
        credential_fingerprint="f" * 64,
    )
    # **An annotation carries no run.** The exchange event is one — the
    # model path's call is observed outside any attempt — so the document
    # has no run, stage or operation on it.
    document: dict[str, object] = {
        "event_id": str(new_id()),
        "seq": 1,
        "task_id": str(TaskId(new_id())),
        "type": "model_exchanged",
        "payload": valid.model_dump(mode="json"),
    }

    Event.model_validate(document)

    for payload in (
        {},
        {**valid.model_dump(mode="json"), "exchanges": []},
        {**valid.model_dump(mode="json"), "credential_fingerprint": ""},
    ):
        broken = dict(document)
        broken["payload"] = payload
        with pytest.raises(ValidationError):
            Event.model_validate(broken)


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


# --- ADR-0002 §"Contracts and acceptance tests": the record's own discipline --


def test_event_records_are_frozen_and_forbid_extra_fields() -> None:
    """ADR-0002 binding name. The event record cannot be edited, and it admits
    no key it does not name.

    **The behaviour was already there; nothing watched it.** ADR-0002's
    §"Reversibility" calls the frozen / ``extra="forbid"`` event discipline
    *"the one genuinely hard-to-reverse choice"* — cheap now and expensive
    after Phase 1 data exists — and
    :class:`labcairn.core.schema.LabCairnModel` sets both. But a property
    that is stated and not watched is not held: dropping either setting broke
    nothing, because nothing asked. This is the witness that asks.

    **Two questions, asked of the envelope and of every registered payload.**
    *Can it be edited after it was written?* — ``frozen=True`` refuses the
    assignment rather than applying it, because a record that can be changed
    after the fact is a record whose history nobody can audit.
    *Can it carry a key it does not name?* — ``extra="forbid"`` refuses the
    key rather than dropping it, because an unrecognised key is either a
    newer writer or a typo, and both deserve to be loud.
    """
    event = Event(seq=1, task_id=TaskId(new_id()), type=EventType.TASK_CREATED)

    with pytest.raises(ValidationError) as frozen:
        event.seq = 2
    assert frozen.value.errors()[0]["type"] == "frozen_instance"

    with pytest.raises(ValidationError) as extra:
        Event.model_validate(
            {
                "seq": 1,
                "task_id": TaskId(new_id()),
                "type": EventType.TASK_CREATED,
                "unexpected": "x",
            }
        )
    assert extra.value.errors()[0]["type"] == "extra_forbidden"

    # Every registered payload schema holds the same two settings. The
    # registry is the tree's own list of what may be persisted, so a schema
    # that opted out of the discipline would be a hole in it.
    assert EVENT_PAYLOAD_SCHEMAS, "the registry is empty; the walk below proves nothing"
    for event_type, schema in EVENT_PAYLOAD_SCHEMAS.items():
        assert schema.model_config.get("extra") == "forbid", (
            f"{event_type.value} carries {schema.__name__}, which admits unknown keys"
        )
        assert schema.model_config.get("frozen") is True, (
            f"{event_type.value} carries {schema.__name__}, whose fields can be edited"
        )

    # And the behaviour, on a payload rather than on the envelope.
    payload = _RESOLVED
    with pytest.raises(ValidationError) as frozen_payload:
        payload.verdict = "changed"
    assert frozen_payload.value.errors()[0]["type"] == "frozen_instance"

    with pytest.raises(ValidationError) as extra_payload:
        ReconciliationPayload.model_validate(
            {
                "resolution": "confirmed",
                "verdict": "match",
                "reached_by": "probe",
                "unexpected": "x",
            }
        )
    assert extra_payload.value.errors()[0]["type"] == "extra_forbidden"


#: The prefix a pydantic-ai type's module carries. Checked by module name and
#: not by import, because the whole point is that these types must not have to
#: be imported to be noticed.
_UPSTREAM_PREFIX = "pydantic_ai"


def _annotation_type_names(annotation: object) -> set[str]:
    """Every type an annotation names, nested to any depth.

    ``list[ModelRequest]``, ``ModelRequest | None`` and
    ``Annotated[ModelRequest, Field(...)]`` all name the same upstream type,
    and a guard that only looked at the top level would miss two of the three.
    """
    names: set[str] = set()
    if isinstance(annotation, type):
        names.add(f"{annotation.__module__}.{annotation.__qualname__}")
    for argument in get_args(annotation):
        names |= _annotation_type_names(argument)
    return names


def _every_labcairn_contract() -> tuple[type[LabCairnModel], ...]:
    """Every ``LabCairnModel`` subclass this build can construct.

    **The package is imported module by module** rather than trusting the
    imports this test process happens to have. A guard that sees only the
    modules pytest collected goes blind the moment the offending contract
    moves into a module nothing imports — which is exactly how a persisted
    upstream type would arrive: in a new file, written once, never touched
    again.

    An import that fails is a failure here rather than a skip: a guard that
    cannot reach a module is a guard that cannot vouch for it.
    """
    import importlib
    import pkgutil

    import labcairn

    for module in pkgutil.walk_packages(labcairn.__path__, f"{labcairn.__name__}."):
        importlib.import_module(module.name)

    found: set[type[LabCairnModel]] = set()

    def collect(model: type[LabCairnModel]) -> None:
        for subclass in model.__subclasses__():
            found.add(subclass)
            collect(subclass)

    collect(LabCairnModel)
    return tuple(sorted(found, key=lambda model: (model.__module__, model.__qualname__)))


def test_no_pydantic_ai_type_in_persisted_schema() -> None:
    """ADR-0002 binding name. No persisted contract names an upstream type.

    ADR-0002 §"Reversibility" promises that *"the Pydantic AI dependency can
    be swapped (§A3) without touching persisted schemas"*, and §A3's rule is
    that the persisted forms are LabCairn's own. A field typed as
    ``pydantic_ai.messages.ModelRequest`` inside a stored contract makes that
    promise false in the one place it could not afterwards be repaired: the
    rows already written. The type is in the database's own vocabulary, and
    swapping the library changes what those rows mean.

    **The guard did not exist.** Nothing walked the schema looking for an
    upstream type, so the promise was a sentence in a document and nothing
    more. This is the walk.

    **What it walks, and why that is enough.** Every ``LabCairnModel`` in the
    package — the contracts the tree stores as JSON payloads — plus every
    column of every table the ORM defines, which is where a row's own type
    would show up if one was ever declared. The first is where an upstream
    type would be *readable*; the second is where it would be *stored*.
    """
    contracts = _every_labcairn_contract()
    assert contracts, "no LabCairn contract was found; the walk below proves nothing"

    offenders: list[str] = []
    for contract in contracts:
        for field_name, field in contract.model_fields.items():
            for name in sorted(_annotation_type_names(field.annotation)):
                if name.split(".")[0] == _UPSTREAM_PREFIX:
                    where = f"{contract.__module__}.{contract.__qualname__}.{field_name}"
                    offenders.append(f"{where} -> {name}")

    assert not offenders, (
        "persisted contracts name pydantic-ai types, so swapping the library "
        "would change what the stored rows mean: " + "; ".join(offenders)
    )

    # The columns themselves. A row's type is what a reader has to load the
    # row, so an upstream type there would bind the database to the library
    # more tightly than the contracts do.
    from labcairn.db import models as _models  # noqa: F401 - registers the tables
    from labcairn.db.base import Base

    column_offenders: list[str] = []
    for table_name, table in Base.metadata.tables.items():
        for column in table.columns:
            python_type = getattr(column.type, "python_type", None)
            if isinstance(python_type, type) and python_type.__module__.split(".")[0] == (
                _UPSTREAM_PREFIX
            ):
                column_offenders.append(f"{table_name}.{column.name} -> {python_type!r}")

    assert not column_offenders, "persisted columns carry pydantic-ai types: " + "; ".join(
        column_offenders
    )


def _an_exchange_payload(prompt_digest: str) -> dict[str, object]:
    """One exchange event's payload, in the wire form the model path writes."""
    return {
        "provider": "fake",
        "model": "a-model",
        "destination": "https://example.invalid/v1",
        "exchanges": [
            {
                "provider": "fake",
                "model": "a-model",
                "transcript_step": prompt_digest,
                "prompt_digest": prompt_digest,
                "tool_names": [],
                "outbound": {"sends_prompt": True},
                "provider_attempts": 1,
                "observed_at": "2026-11-25T00:00:00+00:00",
                "usage_input": {"kind": "known", "value": 12},
                "usage_output": {"kind": "known", "value": 7},
            }
        ],
        "credential_fingerprint": "f" * 64,
        "cost_micros": 3,
    }


def test_llm_message_projection_is_derived_and_discardable(env: StoreEnv) -> None:
    """ADR-0002 binding name. The projection is derived from the event log,
    and throwing it away costs nothing.

    **The projection did not exist.** ADR-0002's clause names one — *"delete
    the projection, re-derive from the event log, assert byte-identical;
    assert the re-derived projection is not the task state"* — and the tree
    had the event log, the exchange payload and nothing built on them. A
    clause that names an object which does not exist cannot be witnessed, so
    the object is built here: :mod:`labcairn.runtime.message_projection`
    reads the exchange events through the registry's own schema and answers
    with a projection.

    **Derived.** The log is the only input. A different log projects
    differently, so the projection is a reading of the record rather than a
    constant that happens to be shaped like one.

    **Discardable.** Delete it and re-derive it and the bytes are the same:
    the projection holds nothing the log does not, so losing it loses
    nothing.

    **And not the task state.** The task's state is the rows the store holds.
    Building, dropping and rebuilding the projection leaves those rows
    exactly as they were, and nothing in ``src/`` imports the projection
    module at all — so there is no writer that could turn it into a second
    authority beside the log.
    """
    from labcairn.db.repository import events_after
    from labcairn.runtime.message_projection import project_messages

    store = env.store()
    task = make_task()
    store.create_task(task)

    with store.unit(task.task_id) as work:
        work.emit(EventType.MODEL_EXCHANGED, payload=_an_exchange_payload("d" * 64))
        work.emit(EventType.MODEL_EXCHANGED, payload=_an_exchange_payload("e" * 64))

    log = events_after(env.session, task.task_id)
    exchanges = [event for event in log if event.type is EventType.MODEL_EXCHANGED]
    assert len(exchanges) == 2, f"expected two exchange events; got {log!r}"

    # Derived, and thrown away.
    projection = project_messages(log)
    projected_bytes = projection.canonical()
    projected_digest = projection.digest()
    assert projected_bytes, "the projection rendered nothing"
    del projection

    rebuilt = project_messages(log)
    assert rebuilt.canonical() == projected_bytes, (
        "re-deriving the projection from the same log produced different bytes"
    )
    assert rebuilt.digest() == projected_digest

    # A different log projects differently: the projection is derived, not a
    # constant that happens to look like an answer.
    assert project_messages(exchanges[:1]).canonical() != projected_bytes

    # The projection holds nothing the log does not.
    payloads = {event.seq: event.payload for event in log}
    for call in rebuilt.calls:
        payload = payloads[call.seq]
        assert call.provider == payload["provider"]
        assert call.model == payload["model"]
        assert call.destination == payload["destination"]
        assert call.credential_fingerprint == payload["credential_fingerprint"]
        assert call.cost_micros == payload["cost_micros"]
        assert [dict(exchange) for exchange in call.exchanges] == payload["exchanges"]

    # And the task's state is untouched by all of it: the rows are the same
    # before and after, and no writer in ``src/`` imports the projection, so
    # there is nowhere for a second authority to live.
    assert events_after(env.session, task.task_id) == log

    package = Path(__file__).resolve().parents[1] / "src" / "labcairn"
    importers = [
        path.relative_to(package).as_posix()
        for path in sorted(package.rglob("*.py"))
        if path.name != "message_projection.py"
        and "message_projection" in path.read_text(encoding="utf-8")
    ]
    assert not importers, (
        "something in src/ imports the message projection, so it could be "
        f"written down and become a second authority: {importers!r}"
    )


# --- ADR-0002's own list, watched -------------------------------------------

#: The ADR whose contracts section this file watches.
_ADR = "docs/adr/ADR-0002-model-and-tool-execution-boundary.md"

#: The labels of ADR-0002's accounting table, and the account each names.
_ACCOUNT_LABELS = {
    "Carried under the name declared above": "carried",
    "Carried under a path": "pathed",
    "Carried under another name": "drift",
    "Not carried": "outstanding",
    "**Declared in this section**": "declared",
}


def _the_adr(repo_root: Path) -> str:
    return (repo_root / _ADR).read_text(encoding="utf-8")


def _the_contracts_section(adr: str) -> str:
    """The ADR's contracts section — the part that declares the names."""
    start = adr.index("## Contracts and acceptance tests")
    end = adr.index("## Re-evaluation trigger")
    return adr[start:end]


def _the_accounting_section(adr: str) -> str:
    """The accounting: the counts and the two tables that account for the names."""
    start = adr.index("### Accounting for the names above")
    end = adr.index("## Re-evaluation trigger")
    return adr[start:end]


def _table_rows(block: str) -> list[list[str]]:
    """Every table row in a block, with the separator row dropped."""
    rows: list[list[str]] = []
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(set(cell) <= set("-: ") for cell in cells):
            continue
        rows.append(cells)
    return rows


def _the_declared_names(contracts: str) -> list[str]:
    """The names the contracts section declares binding.

    A binding name is the **bolded** name at the head of a clause. The
    upstream names the clauses cite as counter-examples are mentioned inside
    a clause, not headed by one, and they are OpenHands' to have.
    """
    return re.findall(r"^- \*\*`([^`]+)`\*\*", contracts, re.MULTILINE)


def _the_tree_test_names(repo_root: Path) -> dict[str, list[str]]:
    """Every test function in the tree, and the files that hold it."""
    names: dict[str, list[str]] = {}
    for path in sorted((repo_root / "tests").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
                "test_"
            ):
                names.setdefault(node.name, []).append(path.relative_to(repo_root).as_posix())
    return names


def test_the_binding_names_are_carried_or_declared_outstanding(repo_root: Path) -> None:
    """ADR-0002's own list is watched: every name it declares is accounted for.

    **Why a document needs a witness.** ADR-0002's contracts section opens
    with *"Test names below are binding"*, and a binding name nobody witnesses
    is a promise the tree is not keeping — which is exactly what a sweep of
    that section found: eleven names absent, and nothing in the suite to say
    so. Four of them turned out to be witnessed under another name and seven
    were genuine gaps; this window closed four of the seven, and the other
    three are recorded in the ADR's own accounting.

    **What is watched.** Every name the section declares is in exactly one of
    three places: a witness in this tree carries it under that name; a
    witness carries it under another name and the ADR's accounting says
    which; or the ADR's accounting declares it outstanding and says which
    layer owns it and what would close it.

    **And what fails.** A name with none of the three; a row naming a
    witness that has gone; a row declaring a name outstanding that has since
    acquired a witness; and an accounting table whose counts disagree with
    the tree. The last one is the *"a record is not evidence"* rule made
    mechanical: where the ADR and the tree differ, the tree is right and the
    ADR has to be corrected.
    """
    adr = _the_adr(repo_root)
    contracts = _the_contracts_section(adr)
    accounting = _the_accounting_section(adr)
    tree_names = _the_tree_test_names(repo_root)

    declared = _the_declared_names(contracts)
    assert declared, "the contracts section declares no names; the walk below proves nothing"

    # The accounting's counts and its two tables.
    counts: dict[str, int] = {}
    for row in _table_rows(accounting):
        label = row[0]
        if label in _ACCOUNT_LABELS:
            counts[_ACCOUNT_LABELS[label]] = int(row[1].strip("*"))

    drift_block = accounting[
        accounting.index("#### Carried under another name") : accounting.index("#### Not carried")
    ]
    outstanding_block = accounting[accounting.index("#### Not carried") :]

    drift: dict[str, str] = {}
    for row in _table_rows(drift_block):
        if row[0] == "Name above":
            continue
        drift[row[0].strip("`")] = row[1].strip("`")

    outstanding: dict[str, str] = {}
    for row in _table_rows(outstanding_block):
        if row[0] == "Name above":
            continue
        outstanding[row[0].strip("`")] = row[1]

    # Every declared name is accounted for.
    for name in declared:
        if "::" in name:
            path, _, function = name.partition("::")
            assert (repo_root / path).exists(), f"{name} names a file that does not exist"
            assert function in tree_names, f"{name} names a witness that does not exist"
            continue
        assert name in tree_names or name in drift or name in outstanding, (
            f"{name} is declared binding and is neither witnessed nor recorded "
            "as outstanding in ADR-0002's accounting"
        )

    # A drift row names a witness that exists, in the file it says.
    for name, witness in drift.items():
        assert name in declared, f"{name} is accounted for but is not a declared name"
        path, _, function = witness.partition("::")
        assert (repo_root / path).exists(), f"{name} names a witness file that does not exist"
        assert function in tree_names, f"{name} names a witness that does not exist: {witness}"
        assert path in tree_names[function], f"{function} is not in {path}"
        assert name not in tree_names, (
            f"{name} is carried under another name and also has a witness of its own"
        )

    # An outstanding row names a name that has no witness — yet.
    for name in outstanding:
        assert name in declared, f"{name} is accounted for but is not a declared name"
        assert name not in tree_names, (
            f"{name} is recorded as outstanding but a witness now carries it; "
            "the ADR's accounting has to be corrected"
        )

    # The two tables do not overlap, and they cover the names that need them.
    assert not (set(drift) & set(outstanding)), "a name is accounted for twice"
    assert set(drift) | set(outstanding) <= set(declared)

    # And the counts are the tree's counts.
    measured = {
        "carried": len([n for n in declared if "::" not in n and n in tree_names]),
        "pathed": len([n for n in declared if "::" in n]),
        "drift": len(drift),
        "outstanding": len(outstanding),
        "declared": len(declared),
    }
    assert counts == measured, (
        "ADR-0002's accounting table disagrees with the tree: "
        f"the ADR says {counts!r}, the tree says {measured!r}"
    )
