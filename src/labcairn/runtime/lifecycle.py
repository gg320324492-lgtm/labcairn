"""Task, Run and Stage — the research objective and its attempts.

The separation between these three is the single most load-bearing decision in
the data model, so it is worth stating plainly:

- A **Task** is a continuing research objective. It has a stable identity,
  the materials it is bound to, and an artifact history. It outlives every
  execution attempt and is never "replaced" by one.
- A **Run** is one execution attempt against that Task. A crash-and-resume is
  a *new Run against the same Task*, never a new Task. This is why Task and
  Run ids are different types: conflating them is how a resumed session loses
  its history.
- A **Stage** is a bounded unit of work inside a Run with declared inputs and
  outputs. It exists so progress is inspectable without replaying anything.

None of these hold research content. A Task names its objective and its
materials; what is actually true about the research lives in Evidence, which
is a different model on purpose.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field, ValidationInfo, field_validator

from labcairn.core.ids import RunId, SourceId, StageId, TaskId, new_id
from labcairn.core.schema import LabCairnModel


class RunStatus(StrEnum):
    """Lifecycle of one execution attempt. Closed: an unknown value is a bug, not a variant."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"
    ABANDONED = "abandoned"


class StageStatus(StrEnum):
    """A Stage is either finished, blocked on a decision, or not yet reached.

    ``BLOCKED`` is distinct from ``FAILED``. A blocked stage is waiting for a
    human; a failed one tried and did not work. Collapsing them would make
    "waiting for approval" look like "broken", and the first is a normal state.
    """

    PENDING = "pending"
    ENTERED = "entered"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskGoal(LabCairnModel):
    """What the researcher is trying to establish.

    Held as structured text plus an explicit success criterion rather than as
    free prose, so that a later reviewer can tell whether the goal was met
    instead of being asked to believe it was.
    """

    objective: str = Field(min_length=1, max_length=4000)
    success_criterion: str = Field(min_length=1, max_length=4000)

    @field_validator("objective", "success_criterion")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class Task(LabCairnModel):
    """A continuing research objective. The unit identity survives everything."""

    task_id: TaskId = Field(default_factory=new_id)
    title: str = Field(min_length=1, max_length=300)
    goal: TaskGoal
    #: Materials this Task is bound to. Hashes, not paths: a path moves, a
    #: content hash does not, and binding by path is how a Task silently ends
    #: up describing a different file than it started with.
    bound_source_ids: tuple[SourceId, ...] = ()
    revision: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def next_revision(self) -> int:
        """The revision number a revision *of this state* would carry."""
        return self.revision + 1


class Run(LabCairnModel):
    """One execution attempt against a Task. A resume creates a new Run."""

    run_id: RunId = Field(default_factory=new_id)
    task_id: TaskId
    status: RunStatus = RunStatus.PENDING
    attempt: int = Field(default=1, ge=1)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @field_validator("finished_at")
    @classmethod
    def _after_start(cls, value: datetime | None, info: ValidationInfo) -> datetime | None:
        started = info.data.get("started_at")
        if value is not None and started is not None and value < started:
            raise ValueError("finished_at must not precede started_at")
        return value


class Stage(LabCairnModel):
    """A bounded unit of work with declared inputs and outputs."""

    stage_id: StageId = Field(default_factory=new_id)
    task_id: TaskId
    run_id: RunId
    name: str = Field(min_length=1, max_length=200)
    status: StageStatus = StageStatus.PENDING
    #: Content hashes of the artifacts this stage consumed. "Changed input
    #: invalidates downstream" is enforced by comparing these, not by
    #: timestamps, because a file can change without its mtime moving.
    input_hashes: tuple[str, ...] = ()
    output_hashes: tuple[str, ...] = ()
    blocked_reason: str | None = Field(default=None, max_length=2000)

    @field_validator("blocked_reason")
    @classmethod
    def _reason_only_when_blocked(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value is not None and info.data.get("status") is not StageStatus.BLOCKED:
            raise ValueError("blocked_reason requires status=BLOCKED")
        return value
