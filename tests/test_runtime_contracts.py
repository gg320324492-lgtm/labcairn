"""Contract tests for the runtime layer.

Two of these tests exist to prevent a specific regression rather than to check
new behaviour. ADR-0003 originally said ``run_id`` was always non-null and that
``seq`` was an ``INTEGER PRIMARY KEY AUTOINCREMENT``; both were wrong and both
were corrected by review. Nothing else in the suite would notice if they
crept back, so they are asserted directly and named for what they hold.

Everything else here is the acceptance LC-P1-02 names: JSON round-trip,
schema incompatibility, malformed payloads rejected, and Task/Run separation
made explicit.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, TypedDict

import pytest
from pydantic import ValidationError

from labcairn.core.ids import RunId, TaskId, is_uuid7, new_id
from labcairn.core.schema import (
    CURRENT_SCHEMA_VERSION,
    LabCairnModel,
    SchemaVersionError,
)
from labcairn.runtime.event import (
    ANNOTATION_EVENTS,
    RUN_SCOPED_PREFIXES,
    TASK_LEVEL_EVENTS,
    Event,
    EventStreamPage,
    EventTransition,
    EventType,
    event_requires_operation_context,
    event_requires_run,
)
from labcairn.runtime.lifecycle import (
    Run,
    RunStatus,
    Stage,
    StageStatus,
    Task,
    TaskGoal,
)
from labcairn.runtime.operation import (
    Approval,
    ApprovalRefusal,
    ApprovalState,
    Checkpoint,
    Operation,
    OperationState,
    compute_args_digest,
)

pytestmark = pytest.mark.unit

CAPTURE = "fs.write"


@pytest.fixture
def ids() -> dict[str, Any]:
    """Fresh ids for one test.

    Typed ``Any`` deliberately. ``TaskId`` and friends are nominal, so a
    fixture returning plain ``UUID`` would produce a type error at every call
    site and bury the real assertions in noise. The nominal typing itself is
    not left unchecked — it is enforced where it can be observed, by
    ``tests/test_id_aliases_are_nominal.py``, which runs mypy over a probe.
    """
    return {k: new_id() for k in ("task", "run", "stage", "operation", "approval", "checkpoint")}


@pytest.fixture
def task(ids: dict[str, Any]) -> Task:
    return Task(
        task_id=ids["task"],
        title="Does X correlate with Y",
        goal=TaskGoal(objective="quantify the relationship", success_criterion="r2 > 0.7"),
    )


# --------------------------------------------------------------------------
# R-02 — run_id is nullable, and that is not optional
# --------------------------------------------------------------------------


def test_task_level_events_may_omit_run_id(ids: dict[str, Any]) -> None:
    """A Task exists before its first Run and can be revised between Runs."""
    event = Event(seq=1, task_id=ids["task"], run_id=None, type=EventType.TASK_CREATED)
    assert event.run_id is None


@pytest.mark.parametrize("event_type", sorted(TASK_LEVEL_EVENTS))
def test_task_level_events_reject_a_run_id(ids: dict[str, Any], event_type: EventType) -> None:
    with pytest.raises(ValidationError, match="Task-level"):
        Event(seq=1, task_id=ids["task"], run_id=ids["run"], type=event_type)


#: Hard-coded from ADR-0003 C1's table rather than derived from the function
#: under test. A parameter list sampled from `event_requires_run` skips silently
#: when that function returns False for everything, which is how a broken
#: prefix went unnoticed.
RUN_SCOPED_TYPES = (
    EventType.RUN_STARTED,
    EventType.RUN_PAUSED,
    EventType.RUN_RESUMED,
    EventType.RUN_FINISHED,
    EventType.STAGE_ENTERED,
    EventType.STAGE_COMPLETED,
    EventType.STAGE_BLOCKED,
    EventType.OPERATION_INTENT,
    EventType.OPERATION_AWAITING_APPROVAL,
    EventType.OPERATION_ATTEMPTED,
    EventType.OPERATION_CONFIRMED,
    EventType.OPERATION_FAILED,
    EventType.OPERATION_UNCERTAIN,
    EventType.OPERATION_RECONCILED,
    EventType.APPROVAL_REQUESTED,
    EventType.APPROVAL_GRANTED,
    EventType.APPROVAL_DENIED,
    EventType.APPROVAL_EXPIRED,
    EventType.APPROVAL_CONSUMED,
    EventType.CHECKPOINT_CREATED,
)


@pytest.mark.parametrize("event_type", RUN_SCOPED_TYPES)
def test_run_scoped_events_require_a_run_id(ids: dict[str, Any], event_type: EventType) -> None:
    with pytest.raises(ValidationError, match="requires run_id"):
        Event(
            seq=1,
            task_id=ids["task"],
            type=event_type,
            transition=EventTransition(from_state="a", to_state="b"),
        )


def test_operation_events_require_both_stage_and_operation(
    ids: dict[str, Any],
) -> None:
    """Named for the prefix bug: the check used to match ``operation.`` and so
    never fired, letting operation events carry no context and rejecting those
    that did."""
    event_type = EventType.OPERATION_ATTEMPTED
    assert event_requires_operation_context(event_type) is True

    with pytest.raises(ValidationError, match="stage_id and operation_id"):
        Event(
            seq=1,
            task_id=ids["task"],
            run_id=ids["run"],
            type=event_type,
            transition=EventTransition(from_state="authorized", to_state="attempting"),
        )

    ok = Event(
        seq=1,
        task_id=ids["task"],
        run_id=ids["run"],
        stage_id=ids["stage"],
        operation_id=ids["operation"],
        type=event_type,
        transition=EventTransition(from_state="authorized", to_state="attempting"),
    )
    assert ok.operation_id == ids["operation"]


def test_non_operation_events_reject_an_operation_id(ids: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="must not carry operation_id"):
        Event(
            seq=1,
            task_id=ids["task"],
            run_id=ids["run"],
            type=EventType.STAGE_COMPLETED,
            transition=EventTransition(from_state="entered", to_state="completed"),
            operation_id=ids["operation"],
        )


# --------------------------------------------------------------------------
# R-01 — seq is per-Task position, not row identity
# --------------------------------------------------------------------------


def test_seq_starts_at_one_and_is_per_task(ids: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Event(seq=0, task_id=ids["task"], type=EventType.TASK_CREATED)

    # Two tasks both start at 1. That is the whole point: a rowid would hand
    # the second task a different number and no client could reason about one
    # task's contiguous tail.
    a = Event(seq=1, task_id=ids["task"], type=EventType.TASK_CREATED)
    b = Event(seq=1, task_id=TaskId(new_id()), type=EventType.TASK_CREATED)
    assert a.seq == b.seq == 1


def test_events_do_not_expose_a_row_identity_field(ids: dict[str, Any]) -> None:
    """``id`` is table-wide row identity and must never appear on the model.

    If it did, a consumer could sort by it and silently get the wrong order.
    """
    event = Event(seq=1, task_id=ids["task"], type=EventType.TASK_CREATED)
    assert "id" not in type(event).model_fields
    with pytest.raises(ValidationError):
        Event(seq=1, task_id=ids["task"], type=EventType.TASK_CREATED, id=7)  # type: ignore[call-arg]


# --------------------------------------------------------------------------
# Closed vocabulary and transition invariant
# --------------------------------------------------------------------------


def test_unknown_event_type_is_rejected_not_coerced(ids: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Event.model_validate(
            {
                "seq": 1,
                "task_id": str(ids["task"]),
                "type": "task_teleported",
                "schema_version": CURRENT_SCHEMA_VERSION,
            }
        )


def test_events_that_describe_a_change_require_a_transition(
    ids: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError, match="requires a transition"):
        Event(seq=1, task_id=ids["task"], run_id=ids["run"], type=EventType.STAGE_COMPLETED)


@pytest.mark.parametrize("event_type", [EventType.ARTIFACT_RECORDED, EventType.SOURCE_CHANGED])
def test_annotations_must_not_carry_a_transition(
    ids: dict[str, Any], event_type: EventType
) -> None:
    with pytest.raises(ValidationError, match="annotation"):
        Event(
            seq=1,
            task_id=ids["task"],
            type=event_type,
            transition=EventTransition(from_state="a", to_state="b"),
        )


# --------------------------------------------------------------------------
# Task / Run separation
# --------------------------------------------------------------------------


def test_task_and_run_have_independent_identities(ids: dict[str, Any]) -> None:
    run = Run(task_id=ids["task"], attempt=2)
    assert run.task_id == ids["task"]
    assert run.run_id != ids["task"]
    # A resumed attempt is a new Run against the same Task, never a new Task.
    assert run.attempt == 2


def test_run_rejects_finishing_before_it_started(ids: dict[str, Any]) -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError, match="must not precede"):
        Run(task_id=ids["task"], started_at=now, finished_at=now - timedelta(seconds=1))


def test_blocked_stage_requires_a_reason_and_only_then(ids: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="requires status=BLOCKED"):
        Stage(
            stage_id=ids["stage"],
            task_id=ids["task"],
            run_id=ids["run"],
            name="retrieve",
            status=StageStatus.ENTERED,
            blocked_reason="waiting on approval",
        )
    ok = Stage(
        stage_id=ids["stage"],
        task_id=ids["task"],
        run_id=ids["run"],
        name="retrieve",
        status=StageStatus.BLOCKED,
        blocked_reason="waiting on approval",
    )
    assert ok.blocked_reason == "waiting on approval"


# --------------------------------------------------------------------------
# Approval binding — ADR-0003 C4, every condition
# --------------------------------------------------------------------------


@pytest.fixture
def approval(ids: dict[str, Any]) -> Approval:
    return Approval(
        approval_id=ids["approval"],
        task_id=ids["task"],
        operation_id=ids["operation"],
        capability=CAPTURE,
        resource_key="outputs/report.md",
        args_digest=compute_args_digest(
            task_id=ids["task"],
            capability=CAPTURE,
            resource_key="outputs/report.md",
            args={"content": "x", "mode": "w"},
        ),
        state=ApprovalState.GRANTED,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def _refuse(
    approval: Approval,
    ids: dict[str, Any],
    *,
    now: datetime | None = None,
    task_id: Any = None,
    capability: str = CAPTURE,
    resource_key: str = "outputs/report.md",
    recomputed_digest: str | None = None,
    depends_on_intact: bool = True,
    policy_unchanged: bool = True,
) -> ApprovalRefusal | None:
    """Exercise the refusal path with every condition explicitly named.

    Written with explicit keywords rather than a ``**kwargs`` splat: the splat
    reads shorter but defeats the type checker's keyword matching, which is how
    thirty type errors accumulated here unnoticed.
    """
    return approval.refusal_reason(
        now=now or datetime.now(UTC),
        task_id=task_id or TaskId(ids["task"]),
        capability=capability,
        resource_key=resource_key,
        recomputed_digest=recomputed_digest
        or compute_args_digest(
            task_id=ids["task"],
            capability=CAPTURE,
            resource_key="outputs/report.md",
            args={"content": "x", "mode": "w"},
        ),
        depends_on_intact=depends_on_intact,
        policy_unchanged=policy_unchanged,
    )


def test_a_matching_approval_is_usable(approval: Approval, ids: dict[str, Any]) -> None:
    assert _refuse(approval, ids) is None


class _Overrides(TypedDict, total=False):
    """The conditions :func:`_refuse` can override.

    A ``TypedDict`` rather than ``dict[str, object]``: a splat of the latter
    defeats the type checker's keyword matching, which is how thirty errors
    accumulated here without anyone noticing them.
    """

    now: datetime
    task_id: uuid.UUID
    capability: str
    resource_key: str
    recomputed_digest: str
    depends_on_intact: bool
    policy_unchanged: bool


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"now": datetime.now(UTC) + timedelta(days=2)}, ApprovalRefusal.EXPIRED),
        ({"task_id": TaskId(new_id())}, ApprovalRefusal.TASK_SCOPE_MISMATCH),
        ({"resource_key": "outputs/other.md"}, ApprovalRefusal.ARGS_CHANGED),
        ({"capability": "fs.delete"}, ApprovalRefusal.ARGS_CHANGED),
        ({"recomputed_digest": "b" * 64}, ApprovalRefusal.ARGS_CHANGED),
        ({"depends_on_intact": False}, ApprovalRefusal.SOURCE_CHANGED),
        ({"policy_unchanged": False}, ApprovalRefusal.POLICY_CHANGED),
    ],
)
def test_every_refusal_reason_is_reachable(
    approval: Approval,
    ids: dict[str, Any],
    overrides: _Overrides,
    expected: ApprovalRefusal,
) -> None:
    # ``overrides`` is a TypedDict, so the splat is checked against the
    # signature. An earlier plain ``dict[str, object]`` version defeated that
    # matching and accumulated thirty errors here unseen.
    assert _refuse(approval, ids, **overrides) is expected


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (ApprovalState.CONSUMED, ApprovalRefusal.CONSUMED),
        (ApprovalState.PENDING, ApprovalRefusal.NOT_GRANTED),
        (ApprovalState.DENIED, ApprovalRefusal.NOT_GRANTED),
        (ApprovalState.EXPIRED, ApprovalRefusal.EXPIRED),
    ],
)
def test_an_approval_that_is_not_granted_cannot_be_used(
    approval: Approval,
    ids: dict[str, Any],
    state: ApprovalState,
    expected: ApprovalRefusal,
) -> None:
    assert _refuse(approval.model_copy(update={"state": state}), ids) is expected


def test_digest_ignores_argument_order_but_not_argument_values(
    ids: dict[str, Any],
) -> None:
    a = _digest(ids, args={"x": 1, "y": 2})
    b = _digest(ids, args={"y": 2, "x": 1})
    c = _digest(ids, args={"x": 1, "y": 3})
    assert a == b
    assert a != c


def test_digest_is_bound_to_task_and_capability(ids: dict[str, Any]) -> None:
    other_task = compute_args_digest(
        task_id=TaskId(new_id()), capability="c", resource_key="r", args={"a": 1}
    )
    mine = compute_args_digest(task_id=ids["task"], capability="c", resource_key="r", args={"a": 1})
    other_cap = compute_args_digest(
        task_id=ids["task"], capability="d", resource_key="r", args={"a": 1}
    )
    assert mine != other_task
    assert mine != other_cap


def test_digest_covers_depends_on_but_sorts_it(ids: dict[str, Any]) -> None:
    def digest_of(depends_on: tuple[str, ...]) -> str:
        return compute_args_digest(
            task_id=ids["task"],
            capability=CAPTURE,
            resource_key="r",
            args={},
            depends_on=depends_on,
        )

    assert digest_of(("b", "a")) == digest_of(("a", "b"))
    assert digest_of(("a",)) != digest_of(("a", "b"))


# --------------------------------------------------------------------------
# Schema versioning
# --------------------------------------------------------------------------


def test_unknown_fields_are_refused(ids: dict[str, Any]) -> None:
    """An unrecognised key is either a newer writer or a typo; both are loud."""
    payload = json_of(Event(seq=1, task_id=ids["task"], type=EventType.TASK_CREATED))
    payload["surprise"] = 1
    with pytest.raises(ValidationError):
        Event.model_validate(payload)


@pytest.mark.parametrize("version", [0, 2, 99, -1])
def test_unsupported_schema_versions_are_refused(ids: dict[str, Any], version: int) -> None:
    event = Event(seq=1, task_id=ids["task"], type=EventType.TASK_CREATED)
    with pytest.raises(SchemaVersionError):
        event.model_copy(update={"schema_version": version}).check_version(contract="Event")


def test_malformed_payloads_are_rejected(ids: dict[str, Any]) -> None:
    for payload in (
        {"seq": 1, "task_id": str(ids["task"])},  # no type
        {"seq": -1, "task_id": str(ids["task"]), "type": "task_created"},  # negative seq
        {"seq": 1, "task_id": "not-a-uuid", "type": "task_created"},
        {"seq": 1, "task_id": str(uuid.uuid4()), "type": "task_created"},  # v4, not v7
    ):
        with pytest.raises(ValidationError):
            Event.model_validate(payload)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_numbers_are_refused(value: float) -> None:
    """JSON has no literal for NaN or Inf; emitting one would produce bytes
    another reader cannot round-trip."""

    class Model(LabCairnModel):
        x: float

    with pytest.raises(ValidationError):
        Model(x=value)


# --------------------------------------------------------------------------
# JSON round-trip and canonical form
# --------------------------------------------------------------------------


def _roundtrip(model: LabCairnModel) -> LabCairnModel:
    return type(model).model_validate_json(model.model_dump_json())


def test_every_contract_round_trips_through_json(task: Task, ids: dict[str, Any]) -> None:
    now = datetime.now(UTC)
    models: list[LabCairnModel] = [
        task,
        Run(task_id=ids["task"], status=RunStatus.RUNNING, started_at=now),
        Stage(stage_id=ids["stage"], task_id=ids["task"], run_id=ids["run"], name="retrieve"),
        Operation(
            operation_id=ids["operation"],
            task_id=ids["task"],
            run_id=ids["run"],
            stage_id=ids["stage"],
            state=OperationState.PLANNED,
            capability=CAPTURE,
            resource_key="outputs/report.md",
            args_digest="c" * 64,
            depends_on=("d" * 64,),
        ),
        Approval(
            approval_id=ids["approval"],
            task_id=ids["task"],
            operation_id=ids["operation"],
            capability=CAPTURE,
            resource_key="outputs/report.md",
            args_digest="c" * 64,
            expires_at=now + timedelta(hours=1),
        ),
        Checkpoint(
            checkpoint_id=ids["checkpoint"],
            task_id=ids["task"],
            run_id=ids["run"],
            stage_id=ids["stage"],
            through_seq=7,
        ),
        Event(seq=1, task_id=ids["task"], type=EventType.TASK_CREATED),
    ]
    for model in models:
        assert _roundtrip(model) == model, type(model).__name__


def test_round_trip_is_byte_stable(task: Task) -> None:
    once = task.model_dump_json()
    twice = _roundtrip(task).model_dump_json()
    assert once == twice


def test_canonical_json_is_key_sorted_and_stable(task: Task) -> None:
    canonical = task.json_canonical()
    assert canonical == _roundtrip(task).json_canonical()
    keys = list(json.loads(canonical))
    assert keys == sorted(keys)


# --------------------------------------------------------------------------
# Identifiers
# --------------------------------------------------------------------------


def test_ids_are_uuid7_and_monotonic_within_a_millisecond() -> None:
    """The docstring claims within-millisecond ordering; this is what holds it.

    Two bugs were found by exactly this test: a 48-bit counter written into a
    12-bit field, silently overlapping the timestamp; and a reseed on counter
    wrap that reordered ids sharing a timestamp.
    """
    batch = [new_id() for _ in range(20_000)]
    assert all(is_uuid7(i) for i in batch)
    assert len({str(i) for i in batch}) == len(batch)
    as_text = [str(i) for i in batch]
    assert as_text == sorted(as_text)


def test_v4_and_junk_are_rejected_as_ids() -> None:
    assert is_uuid7(uuid.uuid4()) is False
    assert is_uuid7("not-a-uuid") is False
    assert is_uuid7(12345) is False


def test_id_types_are_runtime_transparent_but_distinct_to_the_checker() -> None:
    """Ids are UUIDs at runtime and distinct nominal types to mypy.

    The runtime half is ``isinstance``; the checker half cannot be asserted
    here, so it is asserted by ``tests/test_id_aliases_are_nominal.py`` which
    runs mypy over a probe. The earlier version of this test asserted
    ``new_id() == new_id().__class__ or True``, which is true for any value at
    any time and therefore asserted nothing.
    """
    assert isinstance(new_id(), uuid.UUID)
    # NewType is a passthrough at runtime, so the constructor returns the very
    # same UUID. That is the honest half of the claim; the checker half lives
    # in tests/test_id_aliases_are_nominal.py.
    raw = new_id()
    assert TaskId(raw) is raw
    assert isinstance(RunId(raw), uuid.UUID)


# --------------------------------------------------------------------------
# Event stream resumption
# --------------------------------------------------------------------------


def test_event_stream_page_resumes_from_the_last_seq(ids: dict[str, Any]) -> None:
    events = tuple(
        Event(seq=n, task_id=ids["task"], type=EventType.TASK_REVISED) for n in (4, 5, 6)
    )
    page = EventStreamPage(task_id=ids["task"], events=events, next_after_seq=6)
    assert page.last_seq == 6
    # Default is False: a caller who forgets must not claim the client is
    # caught up when it may not be.
    assert page.caught_up is False

    empty = EventStreamPage(task_id=ids["task"], events=(), next_after_seq=6, caught_up=True)
    assert empty.last_seq == 0
    assert empty.caught_up is True


@pytest.mark.parametrize("event_type", sorted(ANNOTATION_EVENTS))
def test_annotations_do_not_need_a_run(ids: dict[str, Any], event_type: EventType) -> None:
    """ADR-0003 requires a Run only for five families.

    An annotation about the Task's material can be observed outside any
    attempt. An earlier draft defined "needs a run" as "everything except
    Task-level", which wrongly demanded a Run of every annotation.
    """
    assert event_requires_run(event_type) is False
    event = Event(seq=1, task_id=ids["task"], type=event_type)
    assert event.run_id is None


def test_every_family_prefix_matches_real_enum_values() -> None:
    """The dot/underscore mistake happened twice.

    ADR-0003 writes the families as ``operation.*`` in prose while the enum
    values are ``operation_confirmed``. A prefix written with a dot matches
    nothing, and the failure is silent — the check simply never fires.
    """
    for prefix in RUN_SCOPED_PREFIXES:
        assert "." not in prefix, "ADR prose uses dots; enum values use underscores"
        matched = [t for t in EventType if t.value.startswith(prefix)]
        assert matched, f"prefix {prefix!r} matches no event type"


def test_run_scoping_matches_the_five_adr_families() -> None:
    expected = {t for t in EventType if t not in TASK_LEVEL_EVENTS and t not in ANNOTATION_EVENTS}
    actual = {t for t in EventType if event_requires_run(t)}
    assert actual == expected


def json_of(model: LabCairnModel) -> dict[str, object]:
    loaded: object = json.loads(model.model_dump_json())
    assert isinstance(loaded, dict)
    return loaded


def _digest(ids: dict[str, Any], **kwargs: object) -> str:
    return compute_args_digest(
        task_id=ids["task"],
        capability=CAPTURE,
        resource_key="outputs/report.md",
        **kwargs,  # type: ignore[arg-type]
    )


# --------------------------------------------------------------------------
# Digest honesty
# --------------------------------------------------------------------------


def test_digest_refuses_arguments_that_would_make_it_lie(ids: dict[str, Any]) -> None:
    """Three ways the digest could lie, all found by cross-review.

    ``json.dumps`` coerces an integer key to a string, so ``{1: "x"}`` and
    ``{"1": "x"}`` produced the *same* digest — two different operations
    sharing one approval. It also emits bare ``NaN``, which is not valid JSON,
    so no compliant reader could reproduce the digest at all.
    """

    def digest(args: object) -> str:
        return compute_args_digest(
            task_id=TaskId(ids["task"]),
            capability=CAPTURE,
            resource_key="r",
            args=args,  # type: ignore[arg-type]
        )

    with pytest.raises(TypeError, match="keys must be strings"):
        digest({1: "x"})

    with pytest.raises(ValueError, match="not JSON-representable"):
        digest({"a": float("nan")})

    with pytest.raises(TypeError):
        digest({"a": {1, 2}})


def test_distinct_keys_never_share_a_digest(ids: dict[str, Any]) -> None:
    def digest(args: object) -> str:
        return compute_args_digest(
            task_id=TaskId(ids["task"]),
            capability=CAPTURE,
            resource_key="r",
            args=args,  # type: ignore[arg-type]
        )

    # "1", "01" and "1" would all stringify to something json.dumps considers
    # distinct, but an integer key is refused outright — so no pair of keys can
    # ever collide by coercion.
    assert len({digest({"1": "x"}), digest({"01": "x"}), digest({"x": "1"})}) == 3
    with pytest.raises(TypeError):
        digest({1: "x"})


def test_digest_is_reproducible_by_a_plain_json_reader(ids: dict[str, Any]) -> None:
    """The claim is "same digest on any platform", which means an independent
    implementation of canonical JSON must land on the same bytes."""
    import hashlib

    args: dict[str, object] = {"b": 2, "a": 1}
    expected_payload: dict[str, object] = {
        "schema_version": 1,
        "task_id": str(ids["task"]),
        "capability": CAPTURE,
        "resource_key": "r",
        "args": args,
        "depends_on": [],
    }
    independent = json.dumps(
        expected_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    actual = compute_args_digest(
        task_id=TaskId(ids["task"]),
        capability=CAPTURE,
        resource_key="r",
        args=args,
    )
    assert actual == hashlib.sha256(independent.encode("utf-8")).hexdigest()


def test_annotation_events_say_so_in_their_error(ids: dict[str, Any]) -> None:
    """An annotation is neither Task-level nor Run-scoped. Saying otherwise
    sends a reader looking in the wrong place."""
    with pytest.raises(ValidationError, match="is an annotation"):
        Event(seq=1, task_id=ids["task"], run_id=ids["run"], type=EventType.SOURCE_CHANGED)

    with pytest.raises(ValidationError, match="is Task-level"):
        Event(seq=1, task_id=ids["task"], run_id=ids["run"], type=EventType.TASK_CREATED)


#: ADR-0003 is the document that fixes this vocabulary.
_ADR_0003 = (
    Path(__file__).resolve().parents[1] / "docs" / "adr" / "ADR-0003-event-and-permission-model.md"
)

_ADR_LINE_PREFIX = "Refusal reasons are enumerated and machine-readable:"


def _adr_refusal_reasons(line: str) -> set[str]:
    """The reasons C4 lists, and nothing else.

    **It refuses rather than returning an empty set.** A parser that quietly
    yields nothing on a reworded line turns the closure check below into an
    assertion that a vocabulary is empty — green forever. This is the shape the
    project has been caught by three gates running: the watcher that cannot fail
    is not watching.
    """
    if not line.startswith(_ADR_LINE_PREFIX):
        raise AssertionError(f"the refusal line does not start with its own prefix: {line!r}")
    reasons = {
        part.strip().removesuffix(".").strip("`")
        for part in line.removeprefix(_ADR_LINE_PREFIX).split(",")
    }
    reasons.discard("")
    if not reasons:
        raise AssertionError(f"the refusal list parsed to nothing usable: {line!r}")
    return reasons


def test_adr_c4_and_the_enum_are_one_vocabulary() -> None:
    """The ADR names the reasons, the code raises them, and neither may drift.

    `ApprovalRefusal` is what a surface branches on and ADR-0003 C4 is what an
    auditor reads. When the two differ, the reader is told a fact about a
    consent model the code does not implement — which is the failure this
    repository has named in every gate review since G3.
    """
    lines = [
        line
        for line in _ADR_0003.read_text(encoding="utf-8").splitlines()
        if line.startswith(_ADR_LINE_PREFIX)
    ]
    assert len(lines) == 1, f"expected one refusal-vocabulary line in ADR-0003, found {len(lines)}"

    listed = _adr_refusal_reasons(lines[0])
    members = {reason.value for reason in ApprovalRefusal}
    assert listed == members, (
        f"ADR-0003 C4 names {sorted(listed - members)} that the enum does not have, "
        f"and the enum has {sorted(members - listed)} the ADR does not name"
    )

    # -- the control: a list that lost a reason must be caught, not accepted -- #
    doctored = lines[0].replace(", `capability_unregistered`", "")
    assert _adr_refusal_reasons(doctored) != members, (
        "the comparison is decorative: dropping a reason from the ADR left it equal"
    )
