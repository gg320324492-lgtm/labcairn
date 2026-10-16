"""The skill, stated as data: stages, their typed ports, and their dependencies.

Nothing here executes anything. A :class:`SkillDeclaration` is a validated
description of the ``research-report`` flow from ``docs/ARCHITECTURE.md``
"Stage workflow (Phase 1)":

    intake -> inventory -> retrieve -> evidence -> propose
           -> [user approval] -> draft -> validate -> deliver

Why the dependency graph is data rather than a chain of ``if`` statements
-------------------------------------------------------------------
The acceptance rules are about *transitions*, and a transition can only be
checked if it is named somewhere. With the graph in one place:

* :meth:`SkillDeclaration.validate` can prove the graph is a DAG whose every
  edge points backwards, and refuse a declaration that is not the specified
  sequence — before any work starts;
* the orchestrator has one code path for "hand this stage its inputs" rather
  than eight, so a guard cannot be applied to seven of them;
* the plan artifact is derived from the same graph, so it cannot describe a
  workflow the declaration does not implement.

The graph is deliberately **linear**, matching the architecture spec. Independent
inventory operations may run concurrently in principle (the architecture says
so), and nothing here prevents that — but the *transitions* are sequential, and
that is the part the acceptance rules are about.

No stage bodies
---------------
This module ships no implementations. Material parsing is LC-P1-08, retrieval
LC-P1-09, evidence checking and analysis LC-P1-09/10, report rendering LC-P1-11.
LC-P1-07 supplies the contract those stages must satisfy and the supervision
that checks they did; writing a fake "retrieve" that greps a fixture would be
implementing a capability this work order explicitly excludes, and would put a
test double in the product.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Final

from labcairn.core.primitives import StrictPosInt
from labcairn.core.schema import LabCairnModel
from labcairn.skills.artifacts import ArtifactKind, StageName
from labcairn.skills.errors import SkillDeclarationError

#: The flow's identity. Stable string, not a version: the stage list *is* the
#: version, and a skill that changed its stages changed its digest.
RESEARCH_REPORT_SKILL_ID: Final = "labcairn.research-report.v1"


@dataclass(frozen=True, slots=True)
class StageBudget:
    """Declared limits for one run.

    Both numbers are needed, and they are not the same limit:

    * :attr:`max_attempts_per_stage` bounds **one** stage. It is the "limited
      retry" the acceptance rule asks for: a stage that makes no progress three
      times is not going to make progress on the fourth, and burning the run's
      whole allowance on it is how a stuck task eats its budget.
    * :attr:`max_total_executions` bounds the **run**, across every stage and
      every attempt. It is the backstop that makes a bug in the retry predicate
      cost a bounded amount of time rather than hanging. The mutation test for
      "no-progress always reads as progress" turns this into the thing that ends
      the loop, which is precisely why it exists.
    """

    max_attempts_per_stage: StrictPosInt = 3
    max_total_executions: StrictPosInt = 24

    def __post_init__(self) -> None:
        for name in ("max_attempts_per_stage", "max_total_executions"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{name} must be a positive integer, got {value!r}")
        if self.max_total_executions < self.max_attempts_per_stage:
            raise ValueError(
                f"max_total_executions ({self.max_total_executions}) is below "
                f"max_attempts_per_stage ({self.max_attempts_per_stage}), so the "
                f"per-stage limit could never be reached and the backstop would "
                f"always fire first."
            )


#: The declared allowance of the shipped skill. A module-level singleton rather
#: than a call in a default argument, because a mutable-looking default built at
#: import time is evaluated once and silently shared by every caller.
DEFAULT_BUDGET: Final = StageBudget()


@dataclass(frozen=True, slots=True)
class StageSpec:
    """One stage: what it consumes, what it produces, and whether it is guarded.

    ``consumes`` names **stages**, not artifact kinds, so the dependency edge and
    the producing edge cannot disagree. The artifact kind is derived from the
    producing stage's spec, which is what makes "port X receives the wrong type"
    a declaration error rather than a runtime surprise.
    """

    stage: StageName
    consumes: tuple[StageName, ...]
    produces: ArtifactKind
    #: Requires a granted approval to enter. Exactly one stage may set this —
    #: the one that turns a proposal into prose.
    guarded: bool = False

    def __post_init__(self) -> None:
        if self.stage in self.consumes:
            raise SkillDeclarationError(
                f"stage {self.stage.value!r} lists itself as an input; a stage that "
                f"feeds itself has no defined result."
            )
        if len(set(self.consumes)) != len(self.consumes):
            raise SkillDeclarationError(
                f"stage {self.stage.value!r} lists a duplicate input: {self.consumes}"
            )


@dataclass(frozen=True, slots=True)
class SkillDeclaration:
    """A validated stage graph plus the identity it is published under."""

    skill_id: str
    title: str
    stages: tuple[StageSpec, ...]
    budget: StageBudget = StageBudget()

    def spec(self, stage: StageName) -> StageSpec:
        """The spec for *stage*.

        :raises KeyError: the stage is not in this skill. Callers get a clear
            lookup failure rather than a silently skipped stage.
        """
        for candidate in self.stages:
            if candidate.stage is stage:
                return candidate
        raise KeyError(f"stage {stage.value!r} is not declared by skill {self.skill_id!r}")

    def order(self) -> tuple[StageName, ...]:
        """Stage names in execution order."""
        return tuple(spec.stage for spec in self.stages)

    def produces(self, stage: StageName) -> ArtifactKind:
        """The artifact kind *stage* produces."""
        return self.spec(stage).produces

    def stage_for(self, kind: ArtifactKind) -> StageName:
        """The stage that produces *kind*.

        :raises SkillDeclarationError: no declared stage produces it, which is
            how a downstream stage referring to an artifact nobody makes gets
            caught at registration rather than mid-run.
        """
        for candidate in self.stages:
            if candidate.produces is kind:
                return candidate.stage
        raise SkillDeclarationError(
            f"no stage in skill {self.skill_id!r} produces artifact kind {kind.value!r}"
        )

    def validate(self) -> None:
        """Refuse an inconsistent declaration.

        Called by :func:`research_report_skill`, so a malformed skill cannot be
        constructed at all. Kept as a method as well so a caller assembling a
        declaration by hand gets the same checks.

        :raises SkillDeclarationError: on a duplicate stage, a duplicate output
            kind, an input that is not declared or comes later in the order, a
            non-root first stage, or more or fewer than one guarded stage.
        """
        seen: set[StageName] = set()
        kinds: set[ArtifactKind] = set()
        for index, spec in enumerate(self.stages):
            if spec.stage in seen:
                raise SkillDeclarationError(f"stage {spec.stage.value!r} declared twice")
            seen.add(spec.stage)
            if spec.produces in kinds:
                raise SkillDeclarationError(
                    f"artifact kind {spec.produces.value!r} is produced twice. Two "
                    f"stages writing the same port means a consumer cannot tell which "
                    f"one it received."
                )
            kinds.add(spec.produces)
            for dependency in spec.consumes:
                if dependency not in seen:
                    where = "not declared" if dependency not in StageName else "declared later"
                    raise SkillDeclarationError(
                        f"stage {spec.stage.value!r} consumes {dependency.value!r}, which "
                        f"is {where}. Every input must be produced by a stage earlier in "
                        f"the order, or the workflow is not the sequence it claims to be."
                    )
            if index == 0 and spec.consumes:
                raise SkillDeclarationError(
                    f"the first stage {spec.stage.value!r} has inputs {spec.consumes}. "
                    f"A workflow starts from something it was given; if the first stage "
                    f"has an input, the real first stage is missing."
                )
        if not self.stages:
            raise SkillDeclarationError("a skill with no stages is not a skill")
        guarded = [spec.stage for spec in self.stages if spec.guarded]
        if len(guarded) != 1:
            raise SkillDeclarationError(
                f"exactly one stage must be guarded by approval; found {guarded}. Zero "
                f"means the checkpoint can be routed around; more than one means the "
                f"checkpoint is not a checkpoint but a way of life."
            )

    def digest(self) -> str:
        """A digest over the graph, so a plan can name the skill it was built for.

        Built from the JSON of a :class:`SkillContract` rather than from
        ``repr``, because ``repr`` of a dataclass is not a stable serialization
        and a digest computed from it would change without the skill changing.
        """
        contract = SkillContract(
            skill_id=self.skill_id,
            title=self.title,
            stages=tuple(
                (
                    spec.stage.value,
                    tuple(dep.value for dep in spec.consumes),
                    spec.produces.value,
                    spec.guarded,
                )
                for spec in self.stages
            ),
            max_attempts_per_stage=self.budget.max_attempts_per_stage,
            max_total_executions=self.budget.max_total_executions,
        )
        return hashlib.sha256(contract.json_canonical().encode("utf-8")).hexdigest()


class SkillContract(LabCairnModel):
    """The declaration in serialisable form, so :meth:`SkillDeclaration.digest`
    has something stable to hash.

    Exists because ``dataclass`` has no canonical serialisation. Its ``extra=
    "forbid"`` inheritance means a declaration cannot be extended by adding a
    field to :class:`StageSpec` and forgetting to surface it here — the digest
    would keep describing the old shape.
    """

    skill_id: str
    title: str
    stages: tuple[tuple[str, tuple[str, ...], str, bool], ...]
    max_attempts_per_stage: int
    max_total_executions: int


def research_report_skill(budget: StageBudget = DEFAULT_BUDGET) -> SkillDeclaration:
    """The one declared first-party skill.

    ``consumes`` follows ``docs/ARCHITECTURE.md`` exactly. Note what ``evidence``
    and ``draft`` each take: ``evidence`` reads ``retrieve`` and ``inventory``,
    because a claim must be locatable in a retrieved passage that is itself in an
    inventoried material; ``draft`` reads ``evidence`` **and** ``propose``,
    because the prose has to follow the approved direction and cannot be built
    from claims alone.
    """
    declaration = SkillDeclaration(
        skill_id=RESEARCH_REPORT_SKILL_ID,
        title="Research report from bound source material",
        budget=budget,
        stages=(
            StageSpec(
                stage=StageName.INTAKE,
                consumes=(),
                produces=ArtifactKind.RESEARCH_OBJECTIVE,
            ),
            StageSpec(
                stage=StageName.INVENTORY,
                consumes=(StageName.INTAKE,),
                produces=ArtifactKind.SOURCE_INVENTORY,
            ),
            StageSpec(
                stage=StageName.RETRIEVE,
                consumes=(StageName.INVENTORY,),
                produces=ArtifactKind.RETRIEVED_EXCERPTS,
            ),
            StageSpec(
                stage=StageName.EVIDENCE,
                consumes=(StageName.RETRIEVE, StageName.INVENTORY),
                produces=ArtifactKind.EVIDENCE_LEDGER,
            ),
            StageSpec(
                stage=StageName.PROPOSE,
                consumes=(StageName.EVIDENCE,),
                produces=ArtifactKind.RESEARCH_PROPOSAL,
            ),
            StageSpec(
                stage=StageName.DRAFT,
                consumes=(StageName.PROPOSE, StageName.EVIDENCE),
                produces=ArtifactKind.REPORT_DRAFT,
                guarded=True,
            ),
            StageSpec(
                stage=StageName.VALIDATE,
                consumes=(StageName.DRAFT,),
                produces=ArtifactKind.VALIDATION_REPORT,
            ),
            StageSpec(
                stage=StageName.DELIVER,
                consumes=(StageName.VALIDATE, StageName.DRAFT),
                produces=ArtifactKind.DELIVERED_REPORT,
            ),
        ),
    )
    declaration.validate()
    return declaration


__all__ = [
    "DEFAULT_BUDGET",
    "RESEARCH_REPORT_SKILL_ID",
    "SkillContract",
    "SkillDeclaration",
    "StageBudget",
    "StageSpec",
    "research_report_skill",
]
