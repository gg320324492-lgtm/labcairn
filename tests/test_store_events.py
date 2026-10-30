"""The per-Task event sequence, and proof that it is not the rowid.

The failure this file exists to prevent is the one ADR-0003 C1 documents in
detail: ``seq`` declared as ``INTEGER PRIMARY KEY AUTOINCREMENT`` *and*
``UNIQUE(task_id, seq)``. In SQLite an ``INTEGER PRIMARY KEY`` **is** the rowid,
so it is unique table-wide and its values are distributed across Tasks rather
than restarted per Task — Task A holds 1, 2, 5 while Task B holds 3, 4. No
client resuming with ``after_seq=<last_seen>`` can then reason about one Task's
contiguous tail.

:func:`test_interleaved_tasks_each_get_a_gapless_run_from_one` reproduces that
exact counterexample as a live test: it interleaves two Tasks, asserts each has
``1, 2, 3``, and *separately* asserts the rowids came out ``1..6`` table-wide.
If ``seq`` were ever the rowid again, the two assertions cannot both hold.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

# `env` is imported for its fixture role, not its value: pytest only sees a
# fixture that is present in the test module's namespace, which is why the
# shared environment lives in an importable module rather than a conftest this
# task does not own.
from test_store_support import (  # noqa: F401
    StoreEnv,
    frozen_clock,
    make_run,
    make_stage,
    make_task,
)
from test_store_support import env as _shared_env

from labcairn.core.ids import TaskId
from labcairn.core.schema import LabCairnModel
from labcairn.db.models import EventRow, TaskRow
from labcairn.db.repository import (
    TaskStore,
    UnknownTaskError,
    count_events,
    events_after,
    last_seq,
)
from labcairn.runtime.event import EventTransition, EventType
from labcairn.runtime.lifecycle import RunStatus

pytestmark = pytest.mark.integration

# pytest resolves a fixture by the parameter name in a test's signature, so the
# shared `env` fixture must be bound under that name here. Importing it directly
# and taking `env` as a parameter makes every signature below an F811
# redefinition; aliasing the import and rebinding it reads as a plain
# assignment instead.
env = _shared_env


def _seqs(session: Session, task_id: TaskId) -> list[int]:
    # A `text()` column has no static type, so the value is narrowed by
    # conversion rather than by an annotation the checker cannot verify.
    rows: Sequence[int] = (
        session.execute(
            text("SELECT seq FROM events WHERE task_id = :t ORDER BY seq"), {"t": str(task_id)}
        )
        .scalars()
        .all()
    )
    return [int(value) for value in rows]


def _rowids(session: Session, task_id: TaskId) -> list[int]:
    rows: Sequence[int] = (
        session.execute(
            text("SELECT id FROM events WHERE task_id = :t ORDER BY seq"), {"t": str(task_id)}
        )
        .scalars()
        .all()
    )
    return [int(value) for value in rows]


def _touch(store: TaskStore, task_id: TaskId, count: int = 1) -> None:
    """Append *count* annotation events, which need no Run context."""
    with store.unit(task_id) as work:
        for _ in range(count):
            work.emit(EventType.SOURCE_CHANGED)


# --------------------------------------------------------------------------- #
# the gaplessness invariant
# --------------------------------------------------------------------------- #


def test_interleaved_tasks_each_get_a_gapless_run_from_one(env: StoreEnv) -> None:
    """Two Tasks interleaved: each is gapless from 1, while rowids run 1..7.

    This is the ADR's counterexample run forwards. The gaplessness assertion and
    the rowid assertion are deliberately in one test, because the rowid
    assertion is what gives the first one its teeth: "A is 1,2,3,4" only means
    something if the table-wide ids are demonstrably a *different* sequence,
    and "B is 1,2,3" only means something if A's rowids are demonstrably
    interleaved with B's.

    The expected rowid split is the point. A holds rows 1, 3, 4, 7 and B holds
    2, 5, 6 — so if ``seq`` ever became the rowid, A would read 1, 3, 4, 7 and
    the assertion below would fail on the gap.
    """
    session = env.session
    store = env.store()
    task_a = make_task(title="A")
    task_b = make_task(title="B")

    store.create_task(task_a)  # A seq 1, rowid 1
    store.create_task(task_b)  # B seq 1, rowid 2

    _touch(store, task_a.task_id, 2)  # A seq 2,3  rowid 3,4
    _touch(store, task_b.task_id, 2)  # B seq 2,3  rowid 5,6
    _touch(store, task_a.task_id, 1)  # A seq 4    rowid 7

    assert _seqs(session, task_a.task_id) == [1, 2, 3, 4]
    assert _seqs(session, task_b.task_id) == [1, 2, 3]

    all_rowids: list[int] = sorted(session.execute(text("SELECT id FROM events")).scalars().all())
    assert all_rowids == [1, 2, 3, 4, 5, 6, 7]
    # Interleaved table-wide, contiguous per Task. If seq were the rowid, these
    # two lines and the two above could not both be true.
    assert _rowids(session, task_a.task_id) == [1, 3, 4, 7]
    assert _rowids(session, task_b.task_id) == [2, 5, 6]


def test_seq_is_not_the_primary_key(env: StoreEnv) -> None:
    """The structural half of the same claim, asserted on the schema itself."""
    mapper = inspect(EventRow)
    event_table = inspect(EventRow).local_table
    primary_key = [c.name for c in mapper.primary_key]
    assert primary_key == ["id"], (
        "events.seq must not be the primary key: in SQLite an INTEGER PRIMARY KEY is "
        "the rowid, which is unique table-wide and therefore cannot be per-Task"
    )
    # And the backstop that makes a concurrent allocation bug loud.
    unique_pairs = {
        tuple(c.name for c in constraint.columns)
        for constraint in event_table.constraints  # type: ignore[attr-defined]
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("task_id", "seq") in unique_pairs


def test_counter_and_event_count_agree(env: StoreEnv) -> None:
    """``tasks.last_event_seq`` is the newest ``seq``, so a gap is detectable."""
    session = env.session
    store = env.store()
    task = make_task()
    store.create_task(task)
    assert last_seq(session, task.task_id) == 1
    assert count_events(session, task.task_id) == 1

    _touch(store, task.task_id, 4)

    assert last_seq(session, task.task_id) == 5
    assert count_events(session, task.task_id) == 5
    assert _seqs(session, task.task_id) == [1, 2, 3, 4, 5]


def test_a_block_contiguous_range_is_handed_out(env: StoreEnv) -> None:
    """Several events in one transaction receive consecutive ``seq`` values.

    Allocation is one statement for the whole block, so a unit of three events
    cannot interleave with another writer and leave a gap behind it.
    """
    session = env.session
    store = env.store()
    task = make_task()
    store.create_task(task)

    with store.unit(task.task_id) as work:
        for _ in range(3):
            work.emit(EventType.SOURCE_CHANGED)

    assert [e.seq for e in events_after(session, task.task_id)] == [1, 2, 3, 4]
    assert _seqs(session, task.task_id) == [1, 2, 3, 4]


def test_duplicate_seq_is_refused_by_the_index(env: StoreEnv) -> None:
    """The UNIQUE backstop fires rather than letting an interleaved log through."""
    session = env.session
    store = env.store()
    task = make_task()
    store.create_task(task)
    _touch(store, task.task_id)

    # Write a second event claiming seq 1 for the same Task, bypassing the store
    # the way a buggy future writer would.
    row: int = session.execute(
        text("SELECT seq FROM events WHERE task_id = :t ORDER BY seq LIMIT 1"),
        {"t": str(task.task_id)},
    ).scalar_one()
    assert row == 1
    # SQLite reports a UNIQUE violation by its columns rather than by the
    # constraint's name, so this asserts the backstop's actual effect.
    with pytest.raises(
        IntegrityError, match=r"UNIQUE constraint failed: events\.task_id, events\.seq"
    ):
        session.execute(
            text(
                # Two columns since ADR-0007: `document` holds the whole event,
                # `payload` the type-specific part. These tests drive raw SQL to
                # exercise the table's own constraints, so they must satisfy both.
                "INSERT INTO events (seq, event_id, task_id, run_id, stage_id, operation_id,"
                " type, from_state, to_state, schema_version, occurred_at, document, payload)"
                " VALUES (1, :eid, :t, NULL, NULL, NULL, 'source_changed', NULL, NULL, 1,"
                " '2026-01-01T00:00:00+00:00', '{}', '{}')"
            ),
            {"eid": "0193b0a0-0000-7000-8000-0000000000ff", "t": str(task.task_id)},
        )
    session.rollback()


# --------------------------------------------------------------------------- #
# after_seq resumption
# --------------------------------------------------------------------------- #


def test_after_seq_returns_the_contiguous_tail(env: StoreEnv) -> None:
    """The reason ``seq`` is per-Task: a client can resume and know it is caught up."""
    session = env.session
    store = env.store()
    task = make_task()
    store.create_task(task)
    _touch(store, task.task_id, 5)

    # Resume from the third event, exactly as EventStreamRequest asks.
    tail = events_after(session, task.task_id, after_seq=3)
    assert [e.seq for e in tail] == [4, 5, 6]

    # Draining to the end yields an empty page rather than an error, which is
    # what makes "caught up" a question with an answer.
    assert events_after(session, task.task_id, after_seq=6) == ()


def test_order_is_by_seq_and_never_by_occurred_at(env: StoreEnv) -> None:
    """A backdated timestamp must not reorder the log.

    ADR-0003 C1: ``occurred_at`` is informational only. A resumed process can
    legitimately emit an event whose wall-clock is *earlier* than one already
    recorded, so anything that sorted by time would invert the log.
    """
    session = env.session
    store = env.store()
    task = make_task()
    store.create_task(task)

    late = datetime(2030, 1, 1, tzinfo=UTC)
    early = datetime(2000, 1, 1, tzinfo=UTC)

    with store.unit(task.task_id) as work:
        work.emit(EventType.SOURCE_CHANGED, occurred_at=late)
        work.emit(EventType.SOURCE_CHANGED, occurred_at=early)

    ordered = events_after(session, task.task_id)
    assert [e.seq for e in ordered] == [1, 2, 3]
    # seq 2 is the *later* event and carries the *earlier* timestamp. Anything
    # that ordered by time would return them the other way round.
    assert ordered[1].seq < ordered[2].seq
    assert ordered[1].occurred_at > ordered[2].occurred_at


# --------------------------------------------------------------------------- #
# run_id is required per event type, never per column (ADR-0003 R-02)
# --------------------------------------------------------------------------- #


def test_task_level_events_carry_no_run(env: StoreEnv) -> None:
    """``task_created`` and ``task_revised`` are uninsertable *with* a run_id."""
    session = env.session
    store = env.store()
    task = make_task()
    store.create_task(task)

    # Two scalar reads rather than one two-column row: SQLAlchemy's Row stubs
    # do not narrow a column's type, so a single query would silence the
    # checker rather than inform it.
    stored_type: str = session.execute(
        text("SELECT type FROM events WHERE task_id = :t ORDER BY seq"),
        {"t": str(task.task_id)},
    ).scalar_one()
    stored_run: str | None = session.execute(
        text("SELECT run_id FROM events WHERE task_id = :t ORDER BY seq"),
        {"t": str(task.task_id)},
    ).scalar_one()
    assert stored_type == "task_created"
    assert stored_run is None

    # task_revised is a Task-level event and must also carry none.
    with store.unit(task.task_id) as work:
        work.emit(EventType.TASK_REVISED)
    assert (
        session.execute(
            text("SELECT run_id FROM events WHERE task_id = :t AND type = 'task_revised'"),
            {"t": str(task.task_id)},
        ).scalar_one()
        is None
    )


def test_run_scoped_events_must_name_a_run(env: StoreEnv) -> None:
    """``run_started`` without a run_id is refused, by the contract and by the DB."""
    session = env.session
    store = env.store()
    task = make_task()
    store.create_task(task)
    run = make_run(task.task_id)
    with store.unit(task.task_id) as work:
        work.put_run(run)
        work.emit(
            EventType.RUN_STARTED,
            run_id=run.run_id,
            transition=EventTransition(
                from_state=RunStatus.PENDING.value, to_state=RunStatus.RUNNING.value
            ),
        )
    assert session.execute(
        text("SELECT run_id FROM events WHERE type = 'run_started'")
    ).scalar_one() == str(run.run_id)

    # The same event with no run_id cannot even be constructed.
    from pydantic import ValidationError

    with (
        pytest.raises(ValidationError, match="requires run_id"),
        store.unit(task.task_id) as work,
    ):
        work.emit(
            EventType.RUN_STARTED,
            transition=EventTransition(from_state="pending", to_state="running"),
        )
    session.rollback()


def test_the_database_refuses_a_mislabelled_run_id(env: StoreEnv) -> None:
    """The CHECK constraint catches a raw writer the Pydantic contract cannot.

    A writer that goes straight to SQL — a future migration, a script, a
    different language's client — never constructs an ``Event``. The constraint
    is what stops ``task_created`` arriving with a run_id attached.
    """
    session = env.session
    store = env.store()
    task = make_task()
    store.create_task(task)

    with pytest.raises(IntegrityError, match="ck_events_run_id_matches_event_type"):
        session.execute(
            text(
                # Two columns since ADR-0007: `document` holds the whole event,
                # `payload` the type-specific part. These tests drive raw SQL to
                # exercise the table's own constraints, so they must satisfy both.
                "INSERT INTO events (seq, event_id, task_id, run_id, stage_id, operation_id,"
                " type, from_state, to_state, schema_version, occurred_at, document, payload)"
                " VALUES (99, :eid, :t, :r, NULL, NULL, 'task_created', NULL, NULL, 1,"
                " '2026-01-01T00:00:00+00:00', '{}', '{}')"
            ),
            {
                "eid": "0193b0a0-0000-7000-8000-0000000000aa",
                "t": str(task.task_id),
                "r": str(make_run(task.task_id).run_id),
            },
        )
    session.rollback()


def test_unknown_event_type_is_refused_not_coerced(env: StoreEnv) -> None:
    """A type this build has never heard of is a newer writer. Refuse it.

    Which CHECK fires first is SQLite's business — an unknown type matches
    neither the run_id list nor the closed vocabulary, so both refuse it and the
    first one evaluated wins. The refusal is the guarantee; the specific
    constraint is asserted separately in
    :func:`test_the_vocabulary_constraint_lists_exactly_the_frozen_enum`.
    """
    session = env.session
    store = env.store()
    task = make_task()
    store.create_task(task)

    with pytest.raises(IntegrityError, match="ck_events_"):
        session.execute(
            text(
                # Two columns since ADR-0007: `document` holds the whole event,
                # `payload` the type-specific part. These tests drive raw SQL to
                # exercise the table's own constraints, so they must satisfy both.
                "INSERT INTO events (seq, event_id, task_id, run_id, stage_id, operation_id,"
                " type, from_state, to_state, schema_version, occurred_at, document, payload)"
                " VALUES (50, :eid, :t, NULL, NULL, NULL, 'task_vaporised', NULL, NULL, 1,"
                " '2026-01-01T00:00:00+00:00', '{}', '{}')"
            ),
            {"eid": "0193b0a0-0000-7000-8000-0000000000bb", "t": str(task.task_id)},
        )
    session.rollback()
    assert count_events(session, task.task_id) == 1


def test_the_vocabulary_constraint_lists_exactly_the_frozen_enum(env: StoreEnv) -> None:
    """The database's vocabulary cannot drift from the frozen contract.

    ``models.py`` builds these constraints from :class:`EventType` at import
    time, so a new event type reaches the database automatically. This asserts
    the generated SQL really does contain every member and no non-member — the
    link between "the contract has 29 types" and "the table accepts 29 types",
    which is the property a reader of the migration alone could not verify.
    """
    session = env.session
    ddl: str = session.execute(
        text("SELECT sql FROM sqlite_master WHERE name = 'events' AND type = 'table'")
    ).scalar_one()
    members = {t.value for t in EventType}
    for value in members:
        assert f"'{value}'" in ddl, f"{value} is missing from the events constraints"
    assert "'task_vaporised'" not in ddl
    # 29 members, each named in more than one constraint.
    assert len(members) == 29


def _minimal_payload(schema: type[LabCairnModel]) -> dict[str, object]:
    """The smallest mapping that satisfies *schema*.

    Offsets the sweep's job: it proves every type can reach the database, and a
    schema is now part of what "can reach" means.
    """
    payload: dict[str, object] = {}
    for name, field in schema.model_fields.items():
        if field.is_required():
            payload[name] = "x" if field.annotation is str else 0
    return payload


@pytest.mark.parametrize("event_type", list(EventType), ids=lambda t: t.value)
def test_every_frozen_event_type_reaches_the_database(env: StoreEnv, event_type: EventType) -> None:
    """Each of the 29 types can be inserted with the context the ADR assigns it.

    The drift guard between ADR-0003 C1 and the CHECK constraints: a type added
    to the frozen enum but forgotten in a constraint fails here, per type,
    rather than at some later task's first real insert.
    """
    from labcairn.runtime.event import (
        EVENT_PAYLOAD_SCHEMAS,
        TASK_LEVEL_EVENTS,
        event_requires_operation_context,
        event_requires_run,
    )

    session = env.session
    store = env.store()
    task = make_task()
    store.create_task(task)

    run = make_run(task.task_id)
    stage = make_stage(task.task_id, run.run_id)
    from test_store_support import make_operation

    operation = make_operation(task.task_id, run.run_id, stage.stage_id)

    transition = None
    if event_type.name.startswith(("RUN_", "STAGE_", "OPERATION_", "APPROVAL_")):
        transition = EventTransition(from_state="before", to_state="after")

    # ADR-0007's anti-bag rule: a type with a registered schema must carry a
    # payload satisfying it, and a type without one must carry none. This sweep
    # is what makes that rule visible per type — a newly registered schema that
    # no caller populates fails here rather than at some later real insert.
    schema = EVENT_PAYLOAD_SCHEMAS.get(event_type)
    payload = _minimal_payload(schema) if schema is not None else None

    with store.unit(task.task_id) as work:
        if event_type not in TASK_LEVEL_EVENTS and event_requires_run(event_type):
            work.put_run(run)
            work.put_stage(stage)
        if event_requires_operation_context(event_type):
            work.put_operation(operation)

        work.emit(
            event_type,
            run_id=run.run_id if event_requires_run(event_type) else None,
            stage_id=stage.stage_id if event_requires_operation_context(event_type) else None,
            operation_id=(
                operation.operation_id if event_requires_operation_context(event_type) else None
            ),
            transition=transition,
            payload=payload,
        )

    stored = events_after(session, task.task_id, after_seq=1)
    assert [e.type for e in stored] == [event_type]


def test_annotations_carry_neither_transition_nor_operation(env: StoreEnv) -> None:
    """``artifact_recorded`` is an annotation; a transition on it is a lie."""
    session = env.session
    store = env.store()
    task = make_task()
    store.create_task(task)

    with pytest.raises(IntegrityError, match="ck_events_transition_matches_event_type"):
        session.execute(
            text(
                # Two columns since ADR-0007: `document` holds the whole event,
                # `payload` the type-specific part. These tests drive raw SQL to
                # exercise the table's own constraints, so they must satisfy both.
                "INSERT INTO events (seq, event_id, task_id, run_id, stage_id, operation_id,"
                " type, from_state, to_state, schema_version, occurred_at, document, payload)"
                " VALUES (60, :eid, :t, NULL, NULL, NULL, 'artifact_recorded', 'a', 'b', 1,"
                " '2026-01-01T00:00:00+00:00', '{}', '{}')"
            ),
            {"eid": "0193b0a0-0000-7000-8000-0000000000cc", "t": str(task.task_id)},
        )
    session.rollback()


def test_an_unknown_task_cannot_allocate_a_seq(env: StoreEnv) -> None:
    """A unit of work for a Task that was never created fails loudly."""
    from labcairn.core.ids import TaskId, new_id

    store = env.store()
    with (
        pytest.raises(UnknownTaskError, match="no Task row"),
        store.unit(TaskId(new_id())) as work,
    ):
        work.emit(EventType.SOURCE_CHANGED)


# --------------------------------------------------------------------------- #
# what the store actually wrote
# --------------------------------------------------------------------------- #


def test_events_round_trip_through_the_payload(env: StoreEnv) -> None:
    """A stored event validates back into the frozen contract, unchanged."""
    session = env.session
    store = env.store()
    task = make_task()
    created = store.create_task(task)
    _touch(store, task.task_id)

    stored = events_after(session, task.task_id)
    assert len(stored) == 2
    assert stored[0].type is EventType.TASK_CREATED
    # The provisional seq from emit() never escaped: the committed value is 1.
    assert stored[0].seq == 1
    assert stored[0].event_id == created.event_id
    assert stored[0].occurred_at == task.created_at


def test_a_full_lifecycle_is_storable(env: StoreEnv) -> None:
    """Every table the work order names is reachable from one task lifecycle.

    Not a smoke test of the happy path — a check that the eight tables are
    actually wired to the seven frozen contracts rather than only the two the
    sequence tests happen to touch.
    """
    from test_store_support import (
        make_approval,
        make_checkpoint,
        make_operation,
        make_receipt,
    )

    from labcairn.runtime.operation import OperationState

    session = env.session
    store = env.store()
    task = make_task()
    store.create_task(task)

    run = make_run(task.task_id, now=datetime(2026, 1, 1, tzinfo=UTC))
    stage = make_stage(task.task_id, run.run_id)
    operation = make_operation(task.task_id, run.run_id, stage.stage_id)
    approval = make_approval(task.task_id, operation.operation_id)
    checkpoint = make_checkpoint(task.task_id, run.run_id, stage.stage_id, through_seq=1)
    receipt = make_receipt(task.task_id)

    with store.unit(task.task_id) as work:
        work.put_run(run)
        work.put_stage(stage)
        work.put_operation(operation)
        work.put_approval(approval)
        work.put_checkpoint(checkpoint)
        work.put_artifact(receipt, run_id=run.run_id)
        work.emit(
            EventType.RUN_STARTED,
            run_id=run.run_id,
            transition=EventTransition(
                from_state=RunStatus.PENDING.value, to_state=RunStatus.RUNNING.value
            ),
        )

    counts: dict[str, int] = dict(
        session.execute(
            text(
                "SELECT 'tasks', COUNT(*) FROM tasks UNION ALL"
                " SELECT 'runs', COUNT(*) FROM runs UNION ALL"
                " SELECT 'stages', COUNT(*) FROM stages UNION ALL"
                " SELECT 'events', COUNT(*) FROM events UNION ALL"
                " SELECT 'operations', COUNT(*) FROM operations UNION ALL"
                " SELECT 'approvals', COUNT(*) FROM approvals UNION ALL"
                " SELECT 'checkpoints', COUNT(*) FROM checkpoints UNION ALL"
                " SELECT 'artifacts', COUNT(*) FROM artifacts"
            )
        ).all()
    )
    assert counts == {
        "tasks": 1,
        "runs": 1,
        "stages": 1,
        "events": 2,
        "operations": 1,
        "approvals": 1,
        "checkpoints": 1,
        "artifacts": 1,
    }

    # The operation row kept the digest the contract computed, and the
    # checkpoint's through_seq points at the event that preceded it.
    stored_op: str = session.execute(text("SELECT state FROM operations")).scalar_one()
    assert stored_op == OperationState.PLANNED.value
    through: int = session.execute(text("SELECT through_seq FROM checkpoints")).scalar_one()
    assert through == 1


def test_the_task_row_records_the_local_single_user_scope(env: StoreEnv) -> None:
    """``owner_id`` is written for every Task; Phase 1 has exactly one value."""
    from labcairn.db.models import LOCAL_USER_ID

    session = env.session
    store = env.store()
    store.create_task(make_task(title="one"))
    store.create_task(make_task(title="two"))

    owners: set[str] = set(session.execute(text("SELECT DISTINCT owner_id FROM tasks")).scalars())
    assert owners == {LOCAL_USER_ID}


def test_a_task_with_no_events_cannot_exist(env: StoreEnv) -> None:
    """``create_task`` writes the row and its first event in one transaction.

    Asserted from the other side: the counter starts at zero and the first
    event takes seq 1, so a Task row can never sit in the database describing a
    log that does not exist.
    """
    session = env.session
    store = env.store()
    task = make_task()
    store.create_task(task)

    row = session.execute(select(TaskRow).where(TaskRow.task_id == str(task.task_id))).scalar_one()
    assert row is not None
    assert row.last_event_seq == 1
    assert count_events(session, task.task_id) == 1
    # Touching the far end of the contract's default window, so a regression in
    # created_at handling shows up here rather than in a UI three tasks later.
    assert row.created_at - row.updated_at == timedelta(0)
