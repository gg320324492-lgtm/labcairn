"""The orchestrator: run the declared stages, check what comes back, stop politely.

Everything LC-P1-07 is *for* is in this module's control flow. Four acceptance
rules, and where each one is enforced:

**1. Every stage consumes actual previous artifacts.**
:meth:`Orchestrator._upstream_for` is the only way a stage receives an input, and
it takes them from :class:`~labcairn.skills.ledger.ArtifactLedger` by stage name.
There is no parameter through which a caller could hand a stage an artifact
instead. After the handler returns, :meth:`Orchestrator._verify` checks — in
order — that the artifact is the declared type, that its ``derived_from`` equals
the digests actually handed over, that it is not a placeholder, and that its
references close over its inputs. A caller who wants an artifact in that slot
goes through :meth:`Orchestrator.adopt_artifact`, which verifies lineage against
the ledger before recording anything.

**2. No empty placeholder passes.**
:func:`~labcairn.skills.quality.require_substance` runs on every accepted
artifact, against the definition written down in that module rather than against
an ad-hoc check here.

**3. A blocked user decision awaits approval.**
The guarded stage is named by the declaration, not by a literal. Before it is
entered, :meth:`Orchestrator._gate` consults
:class:`~labcairn.skills.approval.ApprovalGate`. A refusal parks the stage as
``BLOCKED`` and returns — not an exception, and not a failure.

**4. Limited retries on no progress.**
:meth:`Orchestrator._attempt_stage` counts executions and stops at the per-stage
limit, with a whole-run cap behind it so a defect in the retry predicate costs
bounded time instead of hanging. An attempt that returns an artifact identical to
the previous attempt's is named as such in the failure reason, so "it kept
running and kept failing" and "it kept producing the identical result" are
distinguishable in a log.

Cancellation
------------
:meth:`Orchestrator.run` checks :class:`RunControl` **before entering** a stage,
so a stage already in flight always runs to completion and its verified artifact
is recorded. Verified work is never discarded, at any moment of cancellation —
that is the whole of the acceptance rule, and it is why the check is not placed
after the handler returns.

What this module deliberately does not do
-----------------------------------------
It does not resume, reconcile or replay. The stage-boundary records it emits
(:class:`StageCheckpoint`) are the information a recovering process needs; when
to write them durably, when a run may be rebuilt from them, and what to do about
a side effect that may or may not have landed are LC-P1-06's decisions. A
placeholder guess at them here would be worse than nothing, because it would be
an interface somebody wires to.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol

from pydantic import ValidationError

from labcairn.core.ids import RunId, TaskId
from labcairn.core.schema import LabCairnModel
from labcairn.runtime.lifecycle import Stage, StageStatus
from labcairn.skills.approval import ApprovalDecision, ApprovalGate, GateVerdict
from labcairn.skills.artifacts import (
    ArtifactKind,
    ResearchObjective,
    ResearchProposal,
    StageName,
    artifact_type,
)
from labcairn.skills.declaration import SkillDeclaration
from labcairn.skills.errors import (
    ArtifactTypeError,
    DerivationClosureError,
    LineageError,
    PlaceholderError,
    SkillBudgetError,
    SkillDeclarationError,
    StageContractError,
)
from labcairn.skills.ledger import ArtifactLedger, artifact_digest, artifact_lineage
from labcairn.skills.plan import ResearchPlan, build_plan
from labcairn.skills.quality import (
    Upstream,
    UpstreamArtifact,
    require_closure,
    require_substance,
)

#: The stable fragment identifying a "you produced exactly this again" refusal.
#: Matched rather than compared whole, so the sentence around it can be reworded
#: without the attempt counter silently stopping working.
_NO_PROGRESS_REASON_MARKER = "returned byte-identical output to its previous attempt"


@dataclass(frozen=True, slots=True)
class _HandlerOutcome:
    """What one handler call produced, including the two ways of producing nothing.

    Private because it exists only to make the three-way split explicit at the
    call site. ``refusal`` is a retryable "no"; ``blocked`` is a non-retryable "not
    yet"; ``artifact`` is a yes, subject to every check in :meth:`_verify`.
    """

    artifact: LabCairnModel | None = None
    refusal: str | None = None
    blocked: str | None = None


class StageBlockedError(Exception):
    """Raised **by a stage handler** that cannot proceed until a human acts.

    Distinct from :class:`~labcairn.skills.errors.SkillError`, which is the
    orchestrator's own refusal vocabulary. A handler saying "I need the user to
    choose between two search strategies" is not the same event as the
    orchestrator discovering the stage violated its contract, and the two collapse
    into one bug if they share a type.
    """

    def __init__(self, reason: str, *, blocking_kind: ArtifactKind | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.blocking_kind = blocking_kind


class StageFailedError(Exception):
    """Raised **by a stage handler** for a failure that is not a user decision.

    A handler that caught an exception and knows a retry will not help raises
    this, and the reason becomes the stage's recorded failure rather than
    something a reader has to reconstruct from a traceback.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class WorkflowStop(StrEnum):
    """Why the run loop stopped.

    Not :class:`~labcairn.runtime.lifecycle.RunStatus`: that vocabulary is about a
    run's *process* lifecycle (pending, running, paused, finished, abandoned) and
    has no way to say "stopped because a human has not answered yet" or "stopped
    because this stage's output was refused". Collapsing both into ``PAUSED``
    would lose the difference between a task waiting on a person and a task that
    is over.
    """

    COMPLETED = "completed"
    #: Waiting on a person. Re-enterable: the same orchestrator, handed the
    #: decision, continues from the same stage.
    BLOCKED = "blocked"
    #: The stage's output did not satisfy its contract, within budget.
    FAILED = "failed"
    #: The user cancelled. Everything verified so far is retained.
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class StageCheckpoint:
    """What a stage boundary looked like, for whoever has to recover the run.

    **Data, not a mechanism.** This says what was true at a boundary; it does not
    say whether a run may be rebuilt from it, nor what to do about a side effect
    whose outcome is unknown. Those are LC-P1-06's, deliberately not guessed at
    here — a wrong guess about whether an effect landed is exactly the blind replay
    LC-P1-06's acceptance forbids.

    Emitted on every boundary, including failure and blocking: a process that
    crashed after a *failed* stage needs the same information as one that crashed
    after a successful one.
    """

    task_id: str
    run_id: str
    stage: StageName
    status: StageStatus
    attempt: int
    input_digests: tuple[str, ...]
    output_digests: tuple[str, ...]
    recorded_at: datetime
    blocked_reason: str | None = None


@dataclass
class RunControl:
    """Cooperative cancellation.

    A flag rather than a thread kill, and the reason is in
    :meth:`Orchestrator.run`: cancellation is observed at stage boundaries, so a
    stage in flight finishes and its verified output is kept. A thread killed
    mid-stage produces exactly the situation this work order says must not arise —
    work that was done, verified, and then thrown away because the process was
    interrupted.
    """

    _cancelled: bool = False

    def cancel(self) -> None:
        """Ask the run to stop at the next stage boundary."""
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        """Whether cancellation has been requested."""
        return self._cancelled


@dataclass(frozen=True, slots=True)
class BudgetView:
    """What is left of the declared budget, as a handler sees it.

    Handed to handlers so a stage can decide to stop *early* rather than be cut
    off. A stage that keeps working past its allowance and is then cut off has
    spent real effort on a result nobody will use.
    """

    max_attempts_per_stage: int
    max_total_executions: int
    executions_used: int
    attempt: int

    @property
    def total_executions_left(self) -> int:
        """Whole-run executions remaining, counting this one as spent."""
        return max(0, self.max_total_executions - self.executions_used)

    @property
    def attempts_left(self) -> int:
        """Attempts remaining for this stage, counting this one as spent."""
        return max(0, self.max_attempts_per_stage - self.attempt + 1)


@dataclass(frozen=True, slots=True)
class StageContext:
    """Everything a handler is given. Nothing it needs is passed any other way.

    ``inputs`` is keyed by artifact kind, because that is the port name the
    declaration uses; ``upstream`` carries the same objects with their digests
    and in hand-over order, which is what a handler must reproduce in
    ``derived_from``.
    """

    task_id: str
    run_id: str
    stage: StageName
    attempt: int
    inputs: Mapping[ArtifactKind, LabCairnModel]
    upstream: Upstream
    budget: BudgetView
    now: datetime


class StageHandler(Protocol):
    """One stage's body.

    Takes a context, returns the artifact for its declared output port. Returning
    the wrong type is refused rather than coerced; raising :class:`StageBlockedError`
    or :class:`StageFailedError` is how a handler reports a situation it cannot express
    as an artifact.
    """

    def __call__(self, context: StageContext) -> LabCairnModel: ...


@dataclass(frozen=True, slots=True)
class RunOutcome:
    """What a run produced, and why it stopped.

    ``plan`` is here because it is useful to a caller, **not** because the run
    consulted it. See :mod:`labcairn.skills.plan`.
    """

    task_id: str
    run_id: str
    stop: WorkflowStop
    completed_stages: tuple[StageName, ...]
    stopped_at: StageName | None
    reason: str
    attempts_used: Mapping[StageName, int]
    executions: int
    ledger: ArtifactLedger
    checkpoints: tuple[StageCheckpoint, ...]
    stages: tuple[Stage, ...]
    gate_verdict: GateVerdict | None = None
    plan: ResearchPlan | None = field(default=None)

    @property
    def awaiting_approval(self) -> bool:
        """Whether the run is parked waiting on a person."""
        return self.stop is WorkflowStop.BLOCKED


class Orchestrator:
    """Runs a :class:`~labcairn.skills.declaration.SkillDeclaration` under checks.

    Holds the ledger, the gate and the per-run status. One instance per run: the
    ledger is that run's record, and sharing an orchestrator between runs would
    merge two tasks' artifacts into one lineage.

    :param declaration: the stage graph.
    :param handlers: one body per stage. A missing handler is refused at
        construction, not a ``KeyError`` halfway through a run.
    :param task_id: the Task this run is against. Taken from the runtime layer,
        not minted here — identity belongs to
        :class:`~labcairn.runtime.lifecycle.Task`.
    :param run_id: this attempt's Run. A resume creates a new one.
    :param clock: the time source, injected so tests do not read a wall clock.
    """

    def __init__(
        self,
        declaration: SkillDeclaration,
        handlers: Mapping[StageName, StageHandler],
        *,
        task_id: TaskId,
        run_id: RunId,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        missing = [stage.value for stage in declaration.order() if stage not in handlers]
        if missing:
            raise SkillDeclarationError(
                f"skill {declaration.skill_id!r} has no handler for {missing}. LC-P1-07 "
                f"supplies the contract and the supervision, not the science; the "
                f"stage bodies come from LC-P1-08/09/10/11 and must be supplied."
            )
        self.declaration = declaration
        self.handlers = dict(handlers)
        self.task_id = task_id
        self.run_id = run_id
        self.ledger = ArtifactLedger()
        self.gate = ApprovalGate()
        self.clock = clock or (lambda: datetime.now(UTC))
        self._statuses: dict[StageName, StageStatus] = dict.fromkeys(
            declaration.order(), StageStatus.PENDING
        )
        self._reasons: dict[StageName, str] = {}
        self._attempts: dict[StageName, int] = {}
        self._checkpoints: list[StageCheckpoint] = []
        self._runtime_stages: dict[StageName, Stage] = {}
        self._executions = 0

    # -- public surface ---------------------------------------------------

    def run(
        self,
        objective: ResearchObjective,
        *,
        decision: ApprovalDecision | None = None,
        control: RunControl | None = None,
    ) -> RunOutcome:
        """Execute the skill from the first stage that has no verified artifact.

        Re-entrant by design. Calling ``run`` again after a block or a
        cancellation picks up at the first stage the ledger has nothing for, and
        everything already verified is still there. That is ordinary continuation
        from in-process state — it is **not** crash recovery, which has to
        reconcile against durable storage and is LC-P1-06's.

        :param objective: the root artifact, recorded first so the ledger has a
            root even if the first handler fails.
        :param decision: an approval grant, or ``None``. A ``None`` is what
            produces a blocked run at the guarded stage.
        :param control: cooperative cancellation. Omitted means no way to cancel.
        :returns: a :class:`RunOutcome`. This method does not raise for a blocked,
            failed or cancelled run — those are results, not exceptions.
        :raises SkillBudgetError: the whole-run execution cap was reached.
        :raises StageContractError: the objective belongs to a different task.
        """
        control = control or RunControl()
        if not self.ledger.by_stage:
            self._record_objective(objective)

        for stage in self.declaration.order():
            if stage in self.ledger.by_stage:
                continue
            if control.cancelled:
                return self._outcome(
                    WorkflowStop.CANCELLED,
                    stopped_at=stage,
                    reason=(
                        f"cancelled by the user before entering {stage.value!r}; every "
                        f"verified artifact is retained"
                    ),
                )

            spec = self.declaration.spec(stage)
            gate_verdict: GateVerdict | None = None
            if spec.guarded:
                gate_verdict = self._gate(decision)
                if not gate_verdict.approved:
                    return self._block(stage, gate_verdict)

            recorded, failure, blocked = self._attempt_stage(stage)
            if blocked is not None:
                return self._block(
                    stage,
                    GateVerdict(
                        approved=False,
                        required=True,
                        reason=blocked,
                        covered_items=(),
                        covered_goal_changes=(),
                    ),
                )
            if failure is not None or recorded is None:
                reason = failure or "stage produced no artifact"
                self._settle(stage, StageStatus.FAILED, reason=reason)
                return self._outcome(
                    WorkflowStop.FAILED, stopped_at=stage, reason=reason, gate_verdict=gate_verdict
                )

        return self._outcome(
            WorkflowStop.COMPLETED,
            stopped_at=None,
            reason="every declared stage produced a verified artifact",
        )

    def adopt_artifact(self, stage: StageName, artifact: LabCairnModel) -> None:
        """Install an artifact produced outside this process, after checking it.

        The seam a caller uses to hand the run an artifact it already holds — and
        therefore the seam a forgery would come through. So the artifact's
        ``derived_from`` must equal the digests of the artifacts this run recorded
        for the stage's declared inputs, recomputed from the ledger and
        integrity-checked at that moment.

        A forgery has two ways in and neither works: it must name digests that
        were never handed to anything (refused as
        :class:`~labcairn.skills.errors.LineageError`), or name the right ones
        while carrying content unrelated to them (refused by the substance and
        closure checks, applied here exactly as on the normal path).

        Whether the ledger's inputs exist at all is checked first, so a stage
        adopted before its inputs are recorded fails as a lineage error rather
        than a ``KeyError``.

        :raises LineageError: declared lineage does not match the ledger's.
        :raises ArtifactTypeError: wrong model for the port.
        :raises StageContractError: substance or closure failed.
        """
        spec = self.declaration.spec(stage)
        upstream = self._upstream_for(stage)
        kind = spec.produces
        expected = artifact_type(kind)
        if type(artifact) is not expected:
            raise ArtifactTypeError(
                f"port {kind.value!r} declares {expected.__name__}, got {type(artifact).__name__}"
            )
        if artifact_lineage(artifact) != upstream.digests():
            raise LineageError(
                f"adopted {type(artifact).__name__} for stage {stage.value!r} declares "
                f"lineage {list(artifact_lineage(artifact))}, but this run recorded "
                f"{list(upstream.digests())} for that stage's inputs. An artifact whose "
                f"ancestry does not match the ledger's is not this run's output, "
                f"whatever shape it is."
            )
        try:
            require_substance(artifact)
        except PlaceholderError as problem:
            raise StageContractError(
                f"adopted artifact for {stage.value!r} is a placeholder: {problem}"
            ) from problem
        try:
            require_closure(stage, artifact, upstream)
        except DerivationClosureError as problem:
            raise StageContractError(
                f"adopted artifact for {stage.value!r} does not close over its inputs: {problem}"
            ) from problem
        self.ledger.record(kind, stage, artifact, produced_by=None, now=self.clock())
        self._settle(stage, StageStatus.COMPLETED)

    def plan(self) -> ResearchPlan:
        """Derive the current plan. Never cached, never consulted by :meth:`run`."""
        return build_plan(
            task_id=str(self.task_id),
            declaration=self.declaration,
            ledger=self.ledger,
            statuses=self._statuses,
            attempts=self._attempts,
            reasons=self._reasons,
            now=self.clock(),
        )

    def checkpoint_report(self) -> tuple[StageCheckpoint, ...]:
        """Every stage boundary this run crossed, in order."""
        return tuple(self._checkpoints)

    # -- internals --------------------------------------------------------

    def _record_objective(self, objective: ResearchObjective) -> None:
        # The artifact carries an opaque *string* task id (so a ledger stays
        # loadable without importing the runtime, exactly as EvidenceRecord
        # does); the orchestrator carries the runtime's nominal ``TaskId``. Compare
        # the string forms, which is the only comparison that means anything
        # across that boundary.
        if objective.task_id != str(self.task_id):
            raise StageContractError(
                f"objective belongs to task {objective.task_id!r} but this run is "
                f"against {self.task_id!r}. Binding a run to another task's objective "
                f"is how artifacts end up in the wrong ledger."
            )
        self.ledger.record(
            ArtifactKind.RESEARCH_OBJECTIVE,
            StageName.INTAKE,
            objective,
            produced_by=StageName.INTAKE,
            now=self.clock(),
        )
        self._settle(StageName.INTAKE, StageStatus.COMPLETED)

    def _upstream_for(self, stage: StageName) -> Upstream:
        """Load *stage*'s declared inputs, integrity-checked, in declaration order.

        :raises KeyError: an input stage has produced nothing. Reaching here
            without a recorded artifact means the graph was walked out of order,
            which :meth:`~labcairn.skills.declaration.SkillDeclaration.validate`
            is there to prevent.
        :raises ArtifactSubstitutedError: an input was swapped after verification.
        """
        spec = self.declaration.spec(stage)
        entries: list[UpstreamArtifact] = []
        for dependency in spec.consumes:
            kind = self.declaration.produces(dependency)
            recorded = self.ledger.load(dependency, kind)
            entries.append(
                UpstreamArtifact(kind=kind, digest=recorded.digest, artifact=recorded.artifact)
            )
        return Upstream(entries=tuple(entries))

    def _gate(self, decision: ApprovalDecision | None) -> GateVerdict:
        """Evaluate the approval checkpoint against the proposal already recorded."""
        recorded = self.ledger.load(StageName.PROPOSE, ArtifactKind.RESEARCH_PROPOSAL)
        proposal = recorded.artifact
        if not isinstance(proposal, ResearchProposal):
            raise StageContractError(
                f"stage propose recorded {type(proposal).__name__} where a "
                f"ResearchProposal was required; the approval gate cannot read it."
            )
        return self.gate.evaluate(proposal, recorded.digest, decision, now=self.clock())

    def _block(self, stage: StageName, verdict: GateVerdict) -> RunOutcome:
        self._settle(stage, StageStatus.BLOCKED, reason=verdict.reason)
        return self._outcome(
            WorkflowStop.BLOCKED, stopped_at=stage, reason=verdict.reason, gate_verdict=verdict
        )

    def _attempt_stage(self, stage: StageName) -> tuple[Any, str | None, str | None]:
        """Run *stage* under its retry budget.

        :returns: ``(recorded, None, None)`` on success,
            ``(None, reason, None)`` when the stage could not be made to produce a
            valid artifact, or ``(None, None, blocked_reason)`` when the handler
            said it cannot proceed until a human acts. The three are kept apart
            because they end the run differently: a block parks the stage and is
            re-enterable, a failure is final. Retrying a self-blocked stage until
            it ran out of budget and *then* reporting failure would turn "waiting
            on a person" into "broken", which is the distinction
            :class:`~labcairn.runtime.lifecycle.StageStatus` exists to keep.
        :raises SkillBudgetError: the whole-run execution cap was reached before
            the stage succeeded.
        """
        budget = self.declaration.budget
        first_reason: str | None = None
        repeats = 0
        attempt = self._attempts.get(stage, 0) + 1
        previous_digest: str | None = None

        while attempt <= budget.max_attempts_per_stage:
            if self._executions >= budget.max_total_executions:
                raise SkillBudgetError(
                    f"run budget exhausted: {self._executions} of "
                    f"{budget.max_total_executions} whole-run executions used while "
                    f"{stage.value!r} was still on attempt {attempt}. This cap is the "
                    f"backstop that bounds a run when the per-stage no-progress limit "
                    f"is not deciding anything."
                )

            self._statuses[stage] = StageStatus.ENTERED
            self._attempts[stage] = attempt
            outcome = self._run_handler(stage, attempt)
            self._executions += 1

            if outcome.blocked is not None:
                # A self-block is not a failed attempt. Retrying it would spend
                # the budget re-asking a question only a person can answer.
                return None, None, outcome.blocked
            if outcome.refusal is not None:
                if first_reason is None:
                    first_reason = outcome.refusal
                previous_digest = None
                attempt += 1
                continue

            assert outcome.artifact is not None  # implied: refusal and blocked are None
            artifact: LabCairnModel = outcome.artifact
            problem = self._verify(stage, artifact, previous_digest)
            if problem is not None:
                if first_reason is None:
                    first_reason = problem
                elif _NO_PROGRESS_REASON_MARKER in problem:
                    repeats += 1
                previous_digest = artifact_digest(artifact)
                attempt += 1
                continue

            spec = self.declaration.spec(stage)
            recorded = self.ledger.record(
                spec.produces, stage, artifact, produced_by=stage, now=self.clock()
            )
            self._settle(
                stage,
                StageStatus.COMPLETED,
                input_digests=artifact_lineage(artifact),
                output_digests=(recorded.digest,),
            )
            return recorded, None, None

        # The *first* refusal is the one that says what is wrong; the later ones
        # mostly say "and again". Reporting only the last would replace a diagnosis
        # with a symptom, which is the opposite of useful in a log an operator
        # reads once.
        suffix = (
            f"; the following {repeats} attempt(s) returned byte-identical output"
            if repeats
            else ""
        )
        return (
            None,
            f"stage {stage.value!r} made no progress in "
            f"{budget.max_attempts_per_stage} attempt(s); first refusal: "
            f"{first_reason or 'the stage produced nothing'}{suffix}",
            None,
        )

    def _run_handler(self, stage: StageName, attempt: int) -> _HandlerOutcome:
        """Call the handler, classifying whatever it returned or raised.

        Only :class:`StageBlockedError` and :class:`StageFailedError` are caught,
        and only into a classified result. An unexpected exception propagates: a
        bug in a stage body should be a bug report, not a retry.
        """
        spec = self.declaration.spec(stage)
        upstream = self._upstream_for(stage)
        context = StageContext(
            task_id=str(self.task_id),
            run_id=str(self.run_id),
            stage=stage,
            attempt=attempt,
            inputs={entry.kind: entry.artifact for entry in upstream.entries},
            upstream=upstream,
            budget=BudgetView(
                max_attempts_per_stage=self.declaration.budget.max_attempts_per_stage,
                max_total_executions=self.declaration.budget.max_total_executions,
                executions_used=self._executions,
                attempt=attempt,
            ),
            now=self.clock(),
        )
        try:
            return _HandlerOutcome(artifact=self.handlers[stage](context))
        except StageBlockedError as blocked:
            return _HandlerOutcome(blocked=f"stage blocked itself: {blocked.reason}")
        except StageFailedError as failed:
            return _HandlerOutcome(refusal=f"stage reported failure: {failed.reason}")
        except ValidationError as error:
            first = error.errors()[0].get("msg") if error.errors() else "unknown"
            return _HandlerOutcome(
                refusal=(
                    f"stage {stage.value!r} returned a payload that is not a valid "
                    f"{artifact_type(spec.produces).__name__}: {error.error_count()} "
                    f"validation error(s), first: {first}"
                )
            )

    def _verify(self, stage: StageName, artifact: Any, previous_digest: str | None) -> str | None:
        """The acceptance checks, in order. ``None`` means the artifact stands.

        Order is deliberate, and the second position is the one that matters most
        for a retry loop:

        1. **type** — nothing else can be evaluated on the wrong model.
        2. **no progress** — before any substantive check. A stage that returned
           the *identical bytes* it returned last time has told us the single most
           useful thing available, and reporting "the body is a placeholder" for
           the second time when the actionable fact is "you produced exactly this
           again" wastes the operator's reading of the log. Putting this check
           first is also what stops a stage that is stuck re-litigating the same
           refusal from looking like a stage that tried something new.
        3. **lineage**, because an artifact that does not name its ancestors
           cannot be checked against them.
        4. **substance**, then 5. **closure** — the only check that needs the
           upstream objects.

        An earlier draft put the no-progress comparison last, on the reasoning
        that it is "a statement about the previous attempt rather than about this
        artifact". That was wrong in practice: it meant the check was
        unreachable, because any artifact identical to the previous one necessarily
        fails the same substantive check first.
        """
        spec = self.declaration.spec(stage)
        expected = artifact_type(spec.produces)
        if type(artifact) is not expected:
            return (
                f"stage {stage.value!r} returned {type(artifact).__name__}, but port "
                f"{spec.produces.value!r} declares {expected.__name__}"
            )
        if previous_digest is not None and previous_digest == artifact_digest(artifact):
            return (
                f"stage {stage.value!r} {_NO_PROGRESS_REASON_MARKER}. Repeating a result "
                f"is not progress, and retrying it will not produce a different one."
            )
        upstream = self._upstream_for(stage)
        if artifact_lineage(artifact) != upstream.digests():
            return (
                f"stage {stage.value!r} returned an artifact whose derived_from is "
                f"{list(artifact_lineage(artifact))}, not {list(upstream.digests())} — the "
                f"digests of what it was actually handed. A stage that does not name "
                f"its ancestors did not read them."
            )
        try:
            require_substance(artifact)
        except PlaceholderError as problem:
            return f"stage {stage.value!r}: {problem}"
        try:
            require_closure(stage, artifact, upstream)
        except DerivationClosureError as problem:
            return f"stage {stage.value!r}: {problem}"
        return None

    def _settle(
        self,
        stage: StageName,
        status: StageStatus,
        *,
        reason: str | None = None,
        input_digests: tuple[str, ...] = (),
        output_digests: tuple[str, ...] = (),
    ) -> None:
        """Record a stage's final status, its runtime row and its checkpoint."""
        self._statuses[stage] = status
        if reason is not None:
            self._reasons[stage] = reason
        spec = self.declaration.spec(stage)
        if not input_digests:
            input_digests = tuple(
                self.ledger.by_stage[dep].digest
                for dep in spec.consumes
                if dep in self.ledger.by_stage
            )
        if not output_digests:
            recorded = self.ledger.by_stage.get(stage)
            output_digests = (recorded.digest,) if recorded else ()
        self._runtime_stages[stage] = Stage(
            task_id=self.task_id,
            run_id=self.run_id,
            name=stage.value,
            status=status,
            input_hashes=input_digests,
            output_hashes=output_digests,
            blocked_reason=reason if status is StageStatus.BLOCKED else None,
        )
        self._checkpoints.append(
            StageCheckpoint(
                task_id=str(self.task_id),
                run_id=str(self.run_id),
                stage=stage,
                status=status,
                attempt=self._attempts.get(stage, 1),
                input_digests=input_digests,
                output_digests=output_digests,
                recorded_at=self.clock(),
                blocked_reason=reason if status is StageStatus.BLOCKED else None,
            )
        )

    def _outcome(
        self,
        stop: WorkflowStop,
        *,
        stopped_at: StageName | None,
        reason: str,
        gate_verdict: GateVerdict | None = None,
    ) -> RunOutcome:
        return RunOutcome(
            task_id=str(self.task_id),
            run_id=str(self.run_id),
            stop=stop,
            completed_stages=self.ledger.completed_stages(),
            stopped_at=stopped_at,
            reason=reason,
            attempts_used=dict(self._attempts),
            executions=self._executions,
            ledger=self.ledger,
            checkpoints=tuple(self._checkpoints),
            stages=tuple(self._runtime_stages.values()),
            gate_verdict=gate_verdict,
            plan=self.plan(),
        )


__all__ = [
    "BudgetView",
    "Orchestrator",
    "RunControl",
    "RunOutcome",
    "StageBlockedError",
    "StageCheckpoint",
    "StageContext",
    "StageFailedError",
    "StageHandler",
    "WorkflowStop",
]
