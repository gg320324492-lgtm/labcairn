"""The feedback chain's four events: annotations, payloads, and replayability.

**What is under test.** LC-P2-09 T05, ADR-0017 D8: four **annotation** events
on the append-only stream — ``feedback_recorded``, ``edit_action_recorded``,
``response_recorded`` and ``followup_assessed`` — each carrying a registered
payload schema that names the row it is about.

**Four properties, and each has a witness that fails when it breaks.**

1. **They are annotations.** A comment is not an attempt: the event model
   refuses a chain event that carries a transition, and refuses one that
   carries a ``run_id``.
2. **They carry a registered schema, and the anti-bag rule still bites.** A
   type with no registered schema must carry an empty payload; a chain event
   has one, so a payload that does not fit it is refused — an empty payload
   included, because *a chain whose events name nothing is a chain nobody
   can replay*.
3. **They round-trip.** Written through ``UnitOfWork.emit`` and read back
   through the store's event reader, the payload still names its row.
4. **The chain is replayable from the stream alone.** The four events of one
   chain come back in the order they were written, and their payloads are
   enough to walk from the comment to the assessment without a query the
   reader has to guess.
5. **The judgement survives the write and the read.** Who made the change,
   what was judged and what was concluded are the rows' own words, carried
   by the events, so the chain the report's hash chain covers is a replay of
   the judgement and not only of the bookkeeping.

**And the registration has to reach the reader.** A payload schema
registered only where the writer was imported makes every event of that type
unreadable in a process that only reads, while the writer's own tests stay
green — the worst shape a defect can take. So the read is exercised in a
fresh interpreter that imports the vocabulary and nothing else of the
product's chain.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Final

import pytest
from pydantic import ValidationError
from test_store_support import StoreEnv, make_task
from test_store_support import env as _shared_env

from labcairn.core.ids import RunId, TaskId, new_id
from labcairn.core.schema import LabCairnModel
from labcairn.db.repository import UnitOfWork, events_after
from labcairn.runtime.event import (
    ANNOTATION_EVENTS,
    EVENT_PAYLOAD_SCHEMAS,
    Event,
    EventTransition,
    EventType,
    event_requires_run,
)
from labcairn.runtime.trajectory import (
    EditActionRecordedPayload,
    FeedbackRecordedPayload,
    FollowupAssessedPayload,
    ResponseRecordedPayload,
    emit_edit_action_recorded,
    emit_feedback_recorded,
    emit_followup_assessed,
    emit_response_recorded,
)

pytestmark = pytest.mark.integration

# pytest resolves a fixture by the parameter name in a test's signature, so the
# shared `env` fixture must be bound under that name here. See the note in
# tests/test_recovery_crash_matrix.py for why this is an alias and not an
# import under the fixture's own name.
env = _shared_env

#: One chain's rows. The ids are plain strings because the chain's tables mint
#: their own — ``version_edges.edge_id`` is TEXT — and a payload names rows
#: rather than re-typing them.
PROJECT: Final = "project-p2-09"
FEEDBACK: Final = "feedback-1"
VERSION: Final = "version-1"
EDGE: Final = "edge-1"
EDIT: Final = "edit-1"
RESPONSE: Final = "response-1"
ASSESSMENT: Final = "assessment-1"
ISSUE_KEY: Final = "issue-key-1"

#: The three judgements, as the rows' own words. The chain carries the
#: substance and not only the bookkeeping: a reader replaying the stream has
#: to see who made the change, what was judged, and what was concluded.
ACTOR_KIND: Final = "student"
STATE: Final = "addressed"
VERDICT: Final = "not established"

#: The four events of ADR-0017 D8, in the order the chain records them.
CHAIN_TYPES: Final[tuple[EventType, ...]] = (
    EventType.FEEDBACK_RECORDED,
    EventType.EDIT_ACTION_RECORDED,
    EventType.RESPONSE_RECORDED,
    EventType.FOLLOWUP_ASSESSED,
)

#: The schema each chain event's payload must satisfy.
CHAIN_SCHEMAS: Final[dict[EventType, type[LabCairnModel]]] = {
    EventType.FEEDBACK_RECORDED: FeedbackRecordedPayload,
    EventType.EDIT_ACTION_RECORDED: EditActionRecordedPayload,
    EventType.RESPONSE_RECORDED: ResponseRecordedPayload,
    EventType.FOLLOWUP_ASSESSED: FollowupAssessedPayload,
}


#: The payload each chain event carries, built from the models the emitters
#: use. Comparing what comes back against these is what says the event names
#: the row it is about — and carries the judgement it is about.
#:
#: A function and not a table of constants, on purpose: a table is built at
#: import, so a schema that could no longer carry a judgement's word would
#: stop the whole file from loading, and the witness that says so would be a
#: collection error rather than the round-trip going red. Built here, the
#: round-trip is the test that notices.
def chain_payload(event_type: EventType) -> dict[str, object]:
    """The payload the emitter of *event_type* writes, built from the models."""
    if event_type is EventType.FEEDBACK_RECORDED:
        return FeedbackRecordedPayload(
            feedback_id=FEEDBACK,
            project_id=PROJECT,
            version_id=VERSION,
        ).model_dump(mode="json")
    if event_type is EventType.EDIT_ACTION_RECORDED:
        return EditActionRecordedPayload(
            edit_action_id=EDIT,
            project_id=PROJECT,
            version_edge_id=EDGE,
            feedback_id=FEEDBACK,
            actor_kind=ACTOR_KIND,
        ).model_dump(mode="json")
    if event_type is EventType.RESPONSE_RECORDED:
        return ResponseRecordedPayload(
            response_id=RESPONSE,
            project_id=PROJECT,
            feedback_id=FEEDBACK,
            edit_action_id=EDIT,
            state=STATE,
        ).model_dump(mode="json")
    return FollowupAssessedPayload(
        assessment_id=ASSESSMENT,
        project_id=PROJECT,
        feedback_id=FEEDBACK,
        issue_key=ISSUE_KEY,
        verdict=VERDICT,
    ).model_dump(mode="json")


#: The payload field that names the row an event is about, and the row's id.
ROW_ID_FIELD: Final[dict[EventType, str]] = {
    EventType.FEEDBACK_RECORDED: "feedback_id",
    EventType.EDIT_ACTION_RECORDED: "edit_action_id",
    EventType.RESPONSE_RECORDED: "response_id",
    EventType.FOLLOWUP_ASSESSED: "assessment_id",
}

ROW_IDS: Final[dict[EventType, str]] = {
    EventType.FEEDBACK_RECORDED: FEEDBACK,
    EventType.EDIT_ACTION_RECORDED: EDIT,
    EventType.RESPONSE_RECORDED: RESPONSE,
    EventType.FOLLOWUP_ASSESSED: ASSESSMENT,
}

#: The payload field that carries the judgement an event is about, and the
#: word it carries. The feedback event has none: a comment is an
#: observation, and nothing was judged about it yet.
JUDGEMENT_FIELD: Final[dict[EventType, str | None]] = {
    EventType.FEEDBACK_RECORDED: None,
    EventType.EDIT_ACTION_RECORDED: "actor_kind",
    EventType.RESPONSE_RECORDED: "state",
    EventType.FOLLOWUP_ASSESSED: "verdict",
}

JUDGEMENTS: Final[dict[EventType, str | None]] = {
    EventType.FEEDBACK_RECORDED: None,
    EventType.EDIT_ACTION_RECORDED: ACTOR_KIND,
    EventType.RESPONSE_RECORDED: STATE,
    EventType.FOLLOWUP_ASSESSED: VERDICT,
}


def emit_one(work: UnitOfWork, event_type: EventType) -> None:
    """Write the one chain event of *event_type*, through its emitter."""
    if event_type is EventType.FEEDBACK_RECORDED:
        emit_feedback_recorded(
            work,
            feedback_id=FEEDBACK,
            project_id=PROJECT,
            version_id=VERSION,
        )
    elif event_type is EventType.EDIT_ACTION_RECORDED:
        emit_edit_action_recorded(
            work,
            edit_action_id=EDIT,
            project_id=PROJECT,
            version_edge_id=EDGE,
            feedback_id=FEEDBACK,
            actor_kind=ACTOR_KIND,
        )
    elif event_type is EventType.RESPONSE_RECORDED:
        emit_response_recorded(
            work,
            response_id=RESPONSE,
            project_id=PROJECT,
            feedback_id=FEEDBACK,
            edit_action_id=EDIT,
            state=STATE,
        )
    elif event_type is EventType.FOLLOWUP_ASSESSED:
        emit_followup_assessed(
            work,
            assessment_id=ASSESSMENT,
            project_id=PROJECT,
            feedback_id=FEEDBACK,
            issue_key=ISSUE_KEY,
            verdict=VERDICT,
        )
    else:  # pragma: no cover - the parameterisation is closed
        raise AssertionError(f"not a chain event: {event_type.value}")


# --------------------------------------------------------------------------
# 1. Annotations, with registered payloads
# --------------------------------------------------------------------------


@pytest.mark.parametrize("event_type", CHAIN_TYPES)
def test_the_chain_events_are_annotations_with_registered_payloads(
    event_type: EventType,
) -> None:
    """A comment is not an attempt, and it names the row it is about.

    ADR-0017 D8 says the four are annotations, and the event model enforces
    it: an annotation must carry no transition (it does not describe a change
    of state) and no ``run_id`` (it did not happen inside an attempt).

    Each also carries a **registered** payload schema, because a chain whose
    events name nothing is a chain nobody can replay. Named as
    ``docs/plans/LC-P2-09-task-breakdown.md`` §4 names acceptance clause
    A14's witness, so the clause and the test that carries it are found by
    the same name.
    """
    task_id = TaskId(new_id())
    payload = chain_payload(event_type)

    assert event_type in ANNOTATION_EVENTS
    assert event_requires_run(event_type) is False
    assert EVENT_PAYLOAD_SCHEMAS.get(event_type) is CHAIN_SCHEMAS[event_type]

    event = Event(seq=1, task_id=task_id, type=event_type, payload=payload)
    assert event.run_id is None
    assert event.transition is None

    with pytest.raises(ValidationError, match="must not carry a transition"):
        Event(
            seq=1,
            task_id=task_id,
            type=event_type,
            payload=payload,
            transition=EventTransition(from_state="found", to_state="edited"),
        )

    with pytest.raises(ValidationError, match="must not carry run_id"):
        Event(
            seq=1,
            task_id=task_id,
            type=event_type,
            payload=payload,
            run_id=RunId(new_id()),
        )


# --------------------------------------------------------------------------
# 2. A registered schema, and the anti-bag rule
# --------------------------------------------------------------------------


def test_the_anti_bag_rule_refuses_a_payload_for_a_type_with_no_schema() -> None:
    """A type with no declared content must carry none.

    The rule cuts both ways and both halves matter: an unregistered type
    with content is a free-form bag, and a registered type with no content
    is an event that names nothing.
    """
    with pytest.raises(ValidationError, match="has no registered payload schema"):
        Event(
            seq=1,
            task_id=TaskId(new_id()),
            type=EventType.ARTIFACT_RECORDED,
            payload={"anything": "x"},
        )


@pytest.mark.parametrize("event_type", CHAIN_TYPES)
def test_a_chain_event_refuses_an_empty_payload(event_type: EventType) -> None:
    """A chain whose events name nothing is a chain nobody can replay."""
    with pytest.raises(ValidationError) as caught:
        Event(seq=1, task_id=TaskId(new_id()), type=event_type, payload={})
    assert ROW_ID_FIELD[event_type] in str(caught.value), (
        f"the refusal is not about the missing row id, so it is not this property: {caught.value}"
    )


# --------------------------------------------------------------------------
# 3. They round-trip
# --------------------------------------------------------------------------


@pytest.mark.parametrize("event_type", CHAIN_TYPES)
def test_a_chain_event_round_trips_through_the_store(env: StoreEnv, event_type: EventType) -> None:
    """Written through the store, read back through the reader, still naming its row."""
    store = env.store()
    task = make_task()
    store.create_task(task)

    with store.unit(task.task_id) as work:
        emit_one(work, event_type)

    stored = events_after(env.session, task.task_id, after_seq=1)
    assert [event.type for event in stored] == [event_type]

    payload = stored[0].payload
    assert dict(payload) == chain_payload(event_type)
    assert payload[ROW_ID_FIELD[event_type]] == ROW_IDS[event_type]
    assert payload["project_id"] == PROJECT

    judgement_field = JUDGEMENT_FIELD[event_type]
    if judgement_field is not None:
        assert payload.get(judgement_field) == JUDGEMENTS[event_type], (
            f"the {judgement_field} the event was written with did not survive "
            f"the write and the read: {dict(payload)}"
        )


@pytest.mark.parametrize(
    "event_type",
    [event_type for event_type in CHAIN_TYPES if JUDGEMENT_FIELD[event_type] is not None],
)
def test_the_judgement_an_event_is_about_survives_the_write_and_the_read(
    env: StoreEnv, event_type: EventType
) -> None:
    """The chain carries the substance and not only the bookkeeping.

    A reader replaying the stream has to see **who made the change, what was
    judged, and what was concluded** — the words are the rows' own, carried
    verbatim, and this says they arrive.

    The feedback event has no judgement: a comment is an observation, and
    nothing was judged about it yet.
    """
    store = env.store()
    task = make_task()
    store.create_task(task)

    with store.unit(task.task_id) as work:
        emit_one(work, event_type)

    stored = events_after(env.session, task.task_id, after_seq=1)
    assert [event.type for event in stored] == [event_type]

    field = JUDGEMENT_FIELD[event_type]
    assert field is not None
    assert stored[0].payload.get(field) == JUDGEMENTS[event_type], (
        f"the {field} did not survive the write and the read: {dict(stored[0].payload)}"
    )


# --------------------------------------------------------------------------
# 4. The chain is replayable from the stream alone
# --------------------------------------------------------------------------


def test_the_four_events_of_one_chain_come_back_in_the_order_they_were_written(
    env: StoreEnv,
) -> None:
    """The chain's history is a history, and a history has an order.

    ADR-0003 C1's ``seq`` is the only order, and the four events are
    written in one unit of work, so they land on consecutive sequence
    numbers.
    """
    store = env.store()
    task = make_task()
    store.create_task(task)

    with store.unit(task.task_id) as work:
        for event_type in CHAIN_TYPES:
            emit_one(work, event_type)

    stored = events_after(env.session, task.task_id, after_seq=1)
    assert [event.type for event in stored] == list(CHAIN_TYPES)
    assert [event.seq for event in stored] == [2, 3, 4, 5]


def test_a_reader_can_follow_the_chain_from_the_stream_alone(env: StoreEnv) -> None:
    """The payloads are enough to walk the chain, with no query to guess.

    The chain is: a comment written against a version, a change along an
    edge, a judgement joining the two, and a later assessment of the issue.
    Every hop is an id the payload carries, and every link shares the one
    project — so a reader that has only the stream can follow it.
    """
    store = env.store()
    task = make_task()
    store.create_task(task)

    with store.unit(task.task_id) as work:
        for event_type in CHAIN_TYPES:
            emit_one(work, event_type)

    stored = events_after(env.session, task.task_id, after_seq=1)
    by_type = {event.type: event.payload for event in stored}

    feedback = by_type[EventType.FEEDBACK_RECORDED]
    edit = by_type[EventType.EDIT_ACTION_RECORDED]
    response = by_type[EventType.RESPONSE_RECORDED]
    assessment = by_type[EventType.FOLLOWUP_ASSESSED]

    assert {payload["project_id"] for payload in by_type.values()} == {PROJECT}
    assert feedback["version_id"] == VERSION
    assert edit["version_edge_id"] == EDGE
    assert edit["feedback_id"] == feedback["feedback_id"]
    assert response["feedback_id"] == feedback["feedback_id"]
    assert response["edit_action_id"] == edit["edit_action_id"]
    assert assessment["feedback_id"] == feedback["feedback_id"]
    assert assessment["issue_key"] == ISSUE_KEY

    # And the judgements, so the reader sees what was said and not only
    # which rows said it.
    assert edit["actor_kind"] == ACTOR_KIND
    assert response["state"] == STATE
    assert assessment["verdict"] == VERDICT


# --------------------------------------------------------------------------
# The registration reaches the reader
# --------------------------------------------------------------------------

#: A reader that imports the store's reader and nothing else of the
#: product's chain. This is the process ADR-0007's registry exists for: if
#: the schema is missing here, every chain event it reads is unreadable —
#: while the writer's own process, which registered it, is perfectly happy.
_READER = """
import json, sys
from labcairn.core.ids import TaskId
from labcairn.db.repository import events_after
from labcairn.db.session import create_db_engine, create_session_factory

engine = create_db_engine(sys.argv[1])
session = create_session_factory(engine)()
events = events_after(session, TaskId(sys.argv[2]))
print(json.dumps({
    "events": [
        {"seq": event.seq, "type": event.type.value, "payload": dict(event.payload)}
        for event in events
    ],
}))
"""


def test_a_process_that_only_reads_decodes_the_chain_events(env: StoreEnv) -> None:
    """The registration reaches a reader that never named the writer.

    The payload schemas live in the trajectory's module rather than in the
    vocabulary's, and the vocabulary's package imports it — so importing
    the vocabulary is enough. If that link is broken, the read below fails
    with *"has no registered payload schema"* while every test in the
    writer's own process stays green.
    """
    store = env.store()
    task = make_task()
    store.create_task(task)

    with store.unit(task.task_id) as work:
        for event_type in CHAIN_TYPES:
            emit_one(work, event_type)

    # Release the file before another interpreter opens it.
    env.engine.dispose()

    completed = subprocess.run(
        [sys.executable, "-c", _READER, str(env.db_path), str(task.task_id)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert completed.returncode == 0, completed.stderr

    decoded: dict[str, object] = json.loads(completed.stdout)
    events = decoded["events"]
    assert isinstance(events, list)
    chain = [event for event in events if event["type"] in {t.value for t in CHAIN_TYPES}]
    assert [event["type"] for event in chain] == [t.value for t in CHAIN_TYPES]
    assert [event["payload"] for event in chain] == [chain_payload(t) for t in CHAIN_TYPES]
