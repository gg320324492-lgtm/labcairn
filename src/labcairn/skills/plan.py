"""The plan — an artifact to be read, questioned and thrown away.

The work order says *"a plan is a task artifact, not a new authoritative
store"*, and that sentence is the design. Three things follow, and each is
enforced rather than asserted in a comment.

**It is a pure function of what actually happened.**
:func:`build_plan` takes the declaration, the ledger and the current stage
statuses, and returns the plan. It reads nothing else. So the plan cannot
describe a workflow that did not run, and regenerating it after discarding the
first copy is guaranteed to reproduce it — which is the test for "it is a
derived artifact" rather than a claim about one.

**The orchestrator never reads it.**
:meth:`~labcairn.skills.execution.Orchestrator.run` derives what to do next from
the declaration and the ledger. The plan is produced *from* the run, at the end
of it, as a thing to show a person. There is no code path by which re-reading
the plan returns state, because a plan that could be re-read into state would be
a second source of truth and the two would drift. The acceptance test for this is
a forged plan claiming every stage is complete: the orchestrator runs them all
again, because it never consults the plan.

**Facts stay in Task, Event and Evidence.**
A :class:`PlanStep` carries digests and statuses — pointers, not content. It
does not embed the draft, does not restate the evidence ledger, and cannot be
used to answer a scientific question, because it holds nothing scientific.

What it is *for*
----------------
A human reading "where is this task?" during a long run, and a reviewer asking
"what did stage 3 actually depend on, and does that still match?" The second is
why ``input_digests`` and ``output_digests`` are in the plan rather than left to
the ledger: the plan is the thing a person reads, and a fact nobody reads does
not get checked.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType
from typing import Annotated, Self

from pydantic import AwareDatetime, Field, model_validator

from labcairn.core.primitives import StrictPosInt
from labcairn.core.schema import LabCairnModel
from labcairn.runtime.lifecycle import StageStatus
from labcairn.skills.artifacts import StageName
from labcairn.skills.declaration import SkillDeclaration
from labcairn.skills.errors import SkillDeclarationError
from labcairn.skills.ledger import ArtifactLedger
from labcairn.sources.primitives import ContentHash, NonEmptyText


class PlanStep(LabCairnModel):
    """One stage's position in the run, as it stood when the plan was built.

    ``status`` is the same vocabulary as
    :class:`~labcairn.runtime.lifecycle.StageStatus` and is imported rather than
    redeclared, so a plan cannot report a state the runtime does not have.
    """

    stage: StageName
    status: StageStatus
    attempt: StrictPosInt = 1
    input_digests: tuple[ContentHash, ...] = ()
    output_digests: tuple[ContentHash, ...] = ()
    blocked_reason: str | None = None

    @model_validator(mode="after")
    def _block_reason_matches_status(self) -> Self:
        """Mirrors the pairing :class:`~labcairn.runtime.lifecycle.Stage` enforces.

        Repeated here because a plan is written by a different code path than the
        runtime stage, and a plan reporting a blocked stage with no reason is a
        step a person cannot act on.
        """
        if self.blocked_reason is not None and self.status is not StageStatus.BLOCKED:
            raise ValueError(
                f"step {self.stage.value!r} has status={self.status.value!r} and a "
                f"blocked_reason. A reason attached to a stage that is not blocked "
                f"describes a blockage that did not happen."
            )
        return self

    def digest(self) -> str:
        """The digest of the artifact this step produced, if any."""
        return self.output_digests[0] if self.output_digests else ""


class ResearchPlan(LabCairnModel):
    """A readable summary of a run. Derived, disposable, never consulted.

    ``skill_digest`` binds the plan to the graph it describes, so a plan built by
    an older declaration cannot be read as a description of this one.
    """

    task_id: NonEmptyText
    skill_id: NonEmptyText
    skill_digest: ContentHash
    steps: Annotated[tuple[PlanStep, ...], Field(min_length=1)]
    built_at: AwareDatetime

    def step(self, stage: StageName) -> PlanStep:
        """The step for *stage*."""
        for candidate in self.steps:
            if candidate.stage is stage:
                return candidate
        raise SkillDeclarationError(
            f"plan for skill {self.skill_id!r} has no step for {stage.value!r}; it "
            f"covers {[s.stage.value for s in self.steps]}"
        )

    def completed_stages(self) -> tuple[StageName, ...]:
        """Stages this plan reports as finished."""
        return tuple(step.stage for step in self.steps if step.status is StageStatus.COMPLETED)

    def is_consistent_with(self, ledger: ArtifactLedger) -> bool:
        """Whether the plan still matches the ledger.

        Reported rather than enforced: a plan that has drifted is normal after a
        cancellation, and the right response is to rebuild it, not to refuse to
        show it. The orchestrator never calls this — see the module docstring —
        and it exists so a *caller* can notice that a plan they are holding is
        stale.
        """
        for step in self.steps:
            recorded = ledger.by_stage.get(step.stage)
            if recorded is None:
                if step.status is StageStatus.COMPLETED:
                    return False
                continue
            if step.output_digests != (recorded.digest,):
                return False
        return True


def build_plan(
    *,
    task_id: str,
    declaration: SkillDeclaration,
    ledger: ArtifactLedger,
    statuses: Mapping[StageName, StageStatus],
    attempts: Mapping[StageName, int],
    now: datetime,
    reasons: Mapping[StageName, str] = MappingProxyType({}),
) -> ResearchPlan:
    """Derive a plan from what actually happened.

    Pure. The same ledger, statuses and declaration always produce the same plan,
    which is what makes *"discard it and regenerate"* a safe operation rather than
    a hopeful one.

    :param statuses: the orchestrator's current view of each stage. A stage with
        no entry is reported as :attr:`~labcairn.runtime.lifecycle.StageStatus.PENDING`
        — not as completed, not as absent.
    :raises SkillDeclarationError: if the declaration has no stages, which would
        make the ``min_length`` on :attr:`ResearchPlan.steps` unsatisfiable and the
        failure better reported as a declaration defect.
    """
    if not declaration.stages:
        raise SkillDeclarationError("cannot build a plan for a skill with no stages")

    steps: list[PlanStep] = []
    for spec in declaration.stages:
        status = statuses.get(spec.stage, StageStatus.PENDING)
        recorded = ledger.by_stage.get(spec.stage)
        steps.append(
            PlanStep(
                stage=spec.stage,
                status=status,
                attempt=attempts.get(spec.stage, 1),
                input_digests=tuple(recorded.derived_from) if recorded else (),
                output_digests=(recorded.digest,) if recorded else (),
                blocked_reason=reasons.get(spec.stage) if status is StageStatus.BLOCKED else None,
            )
        )

    return ResearchPlan(
        task_id=task_id,
        skill_id=declaration.skill_id,
        skill_digest=declaration.digest(),
        steps=tuple(steps),
        built_at=now,
    )


def rebuild_plan(
    plan: ResearchPlan,
    *,
    declaration: SkillDeclaration,
    ledger: ArtifactLedger,
    statuses: Mapping[StageName, StageStatus],
    attempts: Mapping[StageName, int],
    now: datetime,
    reasons: Mapping[StageName, str] = MappingProxyType({}),
) -> ResearchPlan:
    """Throw the plan away and derive it again.

    Exists so the "it is disposable" claim has a callable form. Returns a new plan
    and does not mutate the old one — the caller decides whether the old one is
    still worth reading, which is a user-interface question about an audit trail,
    not something this module should decide.
    """
    task_id = plan.task_id
    del plan
    return build_plan(
        task_id=task_id,
        declaration=declaration,
        ledger=ledger,
        statuses=statuses,
        attempts=attempts,
        now=now,
        reasons=reasons,
    )


__all__ = ["PlanStep", "ResearchPlan", "build_plan", "rebuild_plan"]
