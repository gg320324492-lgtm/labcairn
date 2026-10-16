"""The record of what a run has actually produced, and how it is known to be that.

The ledger is the answer to *"is this artifact the one the run made?"* — a
question the acceptance rule *"every stage consumes actual previous artifacts"*
turns out to need, because nothing about an artifact's shape says who produced
it. A schema-valid :class:`~labcairn.skills.artifacts.SourceInventory` can be
written by a caller in one line. What it cannot be is *the inventory of this
run* without either passing the checks in this module.

Two independent properties
--------------------------

**Provenance at write time.** :meth:`ArtifactLedger.record` is called by the
orchestrator, and only after the artifact has cleared the type, lineage,
substance and closure gates. It computes the canonical digest and stores it
alongside the stage that produced it. A caller with a forged artifact cannot
get it recorded without naming, in ``derived_from``, the digests of artifacts
the orchestrator actually handed to the stage — which the caller does not control
and does not, until that moment, know.

**Integrity at read time.** :meth:`ArtifactLedger.load` recomputes the digest and
compares it with the recorded one. Write-time checks cannot catch a substitution
that happens afterwards, because the substitution happens after the checks. This
one is evaluated on every single read, so the artifact a stage receives is the
artifact that was verified.

Neither is a substitute for the other. The write-time check catches a forgery
before it becomes part of the record; the read-time check catches tampering with
a record that was legitimately made.

Why the digest covers ``derived_from``
-------------------------------------
The canonical payload includes ``derived_from``, so two artifacts with identical
prose but different ancestors have different digests. That is deliberate: "this
paragraph is supported by these bytes" is part of what the paragraph *is*, and a
digest that ignored provenance would let an unsupported claim borrow a supported
claim's identity.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol, cast

from pydantic import AwareDatetime

from labcairn.core.schema import LabCairnModel
from labcairn.skills.artifacts import ArtifactKind, StageName, artifact_type
from labcairn.skills.errors import (
    ArtifactSubstitutedError,
    ArtifactTypeError,
    StageContractError,
)

#: Bumped when the canonical-digest algorithm changes, so an old digest is
#: refused rather than silently compared against a new algorithm's output.
DIGEST_ALGORITHM: str = "sha256/canonical-json/v1"


class _HasLineage(Protocol):
    """The one field every skill artifact carries that the shared base lacks.

    Declared read-only because the artifacts are frozen. :func:`artifact_lineage`
    casts to this rather than using ``getattr``, which ``ruff``'s ``B009``
    correctly rejects as no safer than attribute access — and a ``cast`` says the
    same thing without a rule to work around: the field is guaranteed by
    :mod:`labcairn.skills.artifacts`, and a model without it is caught at runtime
    by the ``try`` rather than by a comment.
    """

    @property
    def derived_from(self) -> tuple[str, ...]: ...


def artifact_lineage(artifact: LabCairnModel) -> tuple[str, ...]:
    """The artifact's declared ``derived_from``, read through the base class.

    Every artifact in :mod:`labcairn.skills.artifacts` carries the field — the
    root one with a default of ``()`` — but ``LabCairnModel`` is the shared base
    in :mod:`labcairn.core.schema` and adding a skill-specific field to it would
    couple the whole project to this package. So the access goes through here,
    and it **raises** rather than defaulting: an artifact with no lineage field at
    all is a contract defect, and returning ``()`` would quietly make it look like
    a root artifact.

    :raises StageContractError: the model has no ``derived_from`` field.
    """
    try:
        return tuple(cast("_HasLineage", artifact).derived_from)
    except AttributeError as problem:
        raise StageContractError(
            f"{type(artifact).__name__} has no derived_from field. Every skill "
            f"artifact must declare its lineage; a model without one is not a stage "
            f"output and must not be recorded."
        ) from problem


def artifact_digest(artifact: LabCairnModel) -> str:
    """Lowercase-hex sha256 over the artifact's canonical JSON.

    Canonical means sorted keys and no incidental whitespace, so the digest is
    reproducible across platforms and across runs — the property that lets a
    digest be compared instead of eyeballed.
    """
    return hashlib.sha256(artifact.json_canonical().encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RecordedArtifact:
    """One artifact this run produced, with the evidence that it did.

    ``produced_by`` is ``None`` only for an artifact installed by
    :meth:`~labcairn.skills.execution.Orchestrator.adopt_artifact`, which
    verifies lineage against the declaration before it will record anything. The
    distinction is kept rather than erased, because "this run made it" and
    "something outside asserted it, and the assertion was checked against what
    this run recorded" are different facts and an audit log that merges them
    cannot answer either.
    """

    kind: ArtifactKind
    stage: StageName
    artifact: LabCairnModel
    digest: str
    produced_by: StageName | None
    derived_from: tuple[str, ...]
    recorded_at: AwareDatetime

    @property
    def externally_asserted(self) -> bool:
        """Whether this artifact was installed rather than produced here."""
        return self.produced_by is None


@dataclass(frozen=True, slots=True)
class LedgerMismatch:
    """One ledger entry that failed its read-time integrity check.

    Returned rather than raised by :meth:`ArtifactLedger.verify_all` so a caller
    can report *every* substituted artifact at once; ``load`` raises on the first.
    """

    stage: StageName
    recorded_digest: str
    actual_digest: str


@dataclass
class ArtifactLedger:
    """Append-only record of verified artifacts, with a current view by stage.

    ``history`` grows and is never rewritten. ``by_stage`` is the current answer
    to "what does stage X hold", and a re-run of a stage adds to ``history``
    while moving ``by_stage`` forward. Keeping both is what lets a reader ask
    "what did this stage produce the first time?" — the question a plan that is
    discarded and regenerated would otherwise destroy.
    """

    history: list[RecordedArtifact] = field(default_factory=list)
    by_stage: dict[StageName, RecordedArtifact] = field(default_factory=dict)

    def record(
        self,
        kind: ArtifactKind,
        stage: StageName,
        artifact: LabCairnModel,
        *,
        produced_by: StageName | None,
        now: datetime,
    ) -> RecordedArtifact:
        """Record a verified artifact.

        :raises ArtifactTypeError: when *artifact* is not the model
            :data:`~labcairn.skills.artifacts.ARTIFACT_TYPES` names for *kind*.
            Checked here rather than trusted from the caller, because the caller
            is the stage and the stage is the thing being supervised.
        """
        expected = artifact_type(kind)
        if type(artifact) is not expected:
            raise ArtifactTypeError(
                f"port {kind.value!r} declares {expected.__name__}, but stage "
                f"{stage.value!r} returned {type(artifact).__name__}. The port type is "
                f"the contract; a stage returning something else means the caller and "
                f"the declaration disagree about what this stage produces."
            )
        if now.tzinfo is None:
            raise ValueError("ledger timestamps must be timezone-aware")

        recorded = RecordedArtifact(
            kind=kind,
            stage=stage,
            artifact=artifact,
            digest=artifact_digest(artifact),
            produced_by=produced_by,
            derived_from=artifact_lineage(artifact),
            recorded_at=now,
        )
        self.history.append(recorded)
        self.by_stage[stage] = recorded
        return recorded

    def load(self, stage: StageName, kind: ArtifactKind) -> RecordedArtifact:
        """The current artifact for *stage*, with its integrity re-checked.

        :raises KeyError: the stage has not produced anything.
        :raises ArtifactTypeError: the recorded kind is not the one expected.
        :raises ArtifactSubstitutedError: the stored object no longer hashes to
            its recorded digest. Raised on **every** read, which is the point:
            the substitution happens after the write-time checks ran.
        """
        recorded = self.by_stage.get(stage)
        if recorded is None:
            raise KeyError(f"no artifact recorded for stage {stage.value!r}")
        if recorded.kind is not kind:
            raise ArtifactTypeError(
                f"stage {stage.value!r} holds {recorded.kind.value!r}, not {kind.value!r}"
            )
        actual = artifact_digest(recorded.artifact)
        if actual != recorded.digest:
            raise ArtifactSubstitutedError(
                f"artifact for stage {stage.value!r} was substituted after it was "
                f"verified: recorded digest {recorded.digest}, actual {actual} "
                f"(algorithm {DIGEST_ALGORITHM}). Every guard this run applied to the "
                f"original is void for whatever is in the slot now."
            )
        return recorded

    def digests(self, stages: tuple[StageName, ...]) -> tuple[str, ...]:
        """Digests for *stages*, in that order, re-checking each.

        :raises ArtifactSubstitutedError: on the first substitution, so a stage is
            never handed a mix of verified and swapped ancestors.
        """
        return tuple(self.load(stage, self._kind_of(stage)).digest for stage in stages)

    def _kind_of(self, stage: StageName) -> ArtifactKind:
        recorded = self.by_stage.get(stage)
        if recorded is None:
            raise KeyError(f"no artifact recorded for stage {stage.value!r}")
        return recorded.kind

    def verify_all(self) -> tuple[LedgerMismatch, ...]:
        """Every entry whose stored bytes no longer match its recorded digest."""
        mismatches: list[LedgerMismatch] = []
        for stage, recorded in self.by_stage.items():
            actual = artifact_digest(recorded.artifact)
            if actual != recorded.digest:
                mismatches.append(
                    LedgerMismatch(
                        stage=stage, recorded_digest=recorded.digest, actual_digest=actual
                    )
                )
        return tuple(mismatches)

    def artifact_for(self, stage: StageName) -> LabCairnModel:
        """The artifact object for *stage*, without its kind."""
        return self.by_stage[stage].artifact

    def completed_stages(self) -> tuple[StageName, ...]:
        """Stages holding a verified artifact, in declaration order where possible.

        Order follows the ``by_stage`` insertion order, which is production
        order — the only order that means anything for a workflow whose stages
        are strictly sequential.
        """
        return tuple(self.by_stage)


def utc_now() -> datetime:
    """The ledger's clock entry point, so tests can inject a frozen one."""
    return datetime.now(UTC)


__all__ = [
    "DIGEST_ALGORITHM",
    "ArtifactLedger",
    "LedgerMismatch",
    "RecordedArtifact",
    "artifact_digest",
    "artifact_lineage",
    "utc_now",
]
