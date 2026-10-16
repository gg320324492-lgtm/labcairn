"""``ArtifactReceipt`` — what LabCairn generated, and what it was generated from.

``docs/ARCHITECTURE.md``, "Identity and authority": *"ArtifactReceipt records
generated outputs and their provenance."* That is the whole job, and the model
is sized to it.

What this is **not**
-------------------
It is not the export. LC-P1-11 owns report assembly and export, and its scope is
explicit about formats: **DOCX and PDF are not Phase 1**; Markdown and HTML
preview are, with basic editable DOCX/PDF later. This package records the hash
and the provenance of whatever an export produced; it never renders one. A
receipt with no ``relative_path`` would be useless and is not permitted, but
whether the bytes at that path are a good document is LC-P1-11's question.

The provenance chain is one mechanism, not four
----------------------------------------------
:attr:`ArtifactReceipt.derived_from` is a tuple of :class:`DerivationRef`, each
naming one upstream thing by kind and id — an evidence record, a source, an
anchor, a prior artifact, or a raw input file. One closed union instead of five
parallel id lists, because five parallel lists have no order between them and
"what did this figure come from" would need a priority rule nobody wrote down.

The hash requirement tracks the target kind. For ``MATERIAL_FILE`` and
``ARTIFACT`` a content hash is mandatory: those are the links in the chain that
LC-P1-06 invalidates on drift, and a chain link with no hash is a link that
cannot be checked. For ``EVIDENCE_RECORD``, ``SOURCE`` and ``SOURCE_ANCHOR`` it
is optional, because those carry their own — re-recording them here would be a
second copy of a fact with its own staleness.

Staleness is a paired field
---------------------------
ADR-0004 I4 requires downstream artifacts to be **marked** when a source changes;
LC-P1-06 requires the same. :attr:`ArtifactReceipt.staleness` is a closed pair
with :attr:`ArtifactReceipt.staleness_reason`, and a stale receipt must name
why — a stale mark nobody can act on is decoration. Nothing here *computes*
staleness; deciding it needs the source bytes and is LC-P1-06's.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Self

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, model_validator

from labcairn.sources.primitives import (
    ContentHash,
    NonEmptyText,
    StrictNonNegInt,
    StrictPosInt,
    WorkspaceRelativePath,
    require_schema_version,
)

#: The artifact schema version this build reads. Bumped only with a migration.
ARTIFACT_SCHEMA_VERSION: int = 1


def _receipt_version(value: int) -> int:
    return require_schema_version(value, expected=ARTIFACT_SCHEMA_VERSION, schema="ArtifactReceipt")


class ArtifactKind(StrEnum):
    """What sort of output this is.

    ``OTHER`` keeps the set closed while letting a new output type be recorded
    before someone has decided what to call it — an unlabelled row in a ledger
    is worse than a loosely-named one.
    """

    #: A prose deliverable. LC-P1-11's concern.
    REPORT = "report"
    #: A figure with its deterministic data source. LC-P1-10's concern.
    FIGURE = "figure"
    #: A machine-readable table the report cites.
    TABLE = "table"
    #: An exported dataset derived from a source.
    DATASET = "dataset"
    #: A reproducibility manifest.
    MANIFEST = "manifest"
    OTHER = "other"


class ArtifactProducerKind(StrEnum):
    """Who or what wrote the bytes.

    Paired with :attr:`ArtifactReceipt.producer_id` because the *kind* alone
    names nobody: "produced by a tool" is not a provenance statement, "produced
    by ``labcairn.analysis.mean@1.2.0``" is. This is ADR-0002's rule applied to
    artifacts — a final state must name who or what established it.
    """

    #: A workflow stage.
    STAGE = "stage"
    #: A vetted analysis operator (LC-P1-10).
    ANALYSIS_OPERATOR = "analysis_operator"
    #: A named human.
    USER = "user"
    #: A model, indirectly — through a stage that was itself audited. Not a
    #: licence to attribute a file to a model directly.
    MODEL = "model"


class DerivationTargetKind(StrEnum):
    """What a :class:`DerivationRef` points at."""

    #: A :class:`~labcairn.evidence.record.EvidenceRecord`.
    EVIDENCE_RECORD = "evidence_record"
    #: A :class:`~labcairn.sources.source.Source` file.
    SOURCE = "source"
    #: A :class:`~labcairn.sources.source.SourceAnchor` inside one.
    SOURCE_ANCHOR = "source_anchor"
    #: A prior :class:`ArtifactReceipt`.
    ARTIFACT = "artifact"
    #: A raw input file with no ledger row of its own — the "changed source
    #: invalidates downstream" link that LC-P1-06 walks.
    MATERIAL_FILE = "material_file"


#: Target kinds whose link must carry a content hash. See the module docstring.
_HASHED_TARGETS: frozenset[DerivationTargetKind] = frozenset(
    {DerivationTargetKind.ARTIFACT, DerivationTargetKind.MATERIAL_FILE}
)


class DerivationRef(BaseModel):
    """One upstream thing an artifact was made from.

    Ids are plain strings, not embedded objects, for the same reason
    :attr:`~labcairn.evidence.record.EvidenceRecord.anchor_ids` are: the
    artifact must be reproducible from the ledger rather than become a second,
    divergent copy of it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_kind: DerivationTargetKind
    target_id: NonEmptyText
    #: Required for the hashed target kinds, optional otherwise — see the module
    #: docstring.
    content_sha256: ContentHash | None = None

    @model_validator(mode="after")
    def _hash_requirement_tracks_the_target_kind(self) -> Self:
        if self.target_kind in _HASHED_TARGETS and self.content_sha256 is None:
            raise ValueError(
                f"a {self.target_kind.value!r} derivation must carry content_sha256. "
                f"This is the link LC-P1-06 walks when a source changes, and a link "
                f"with no hash is a link nothing can invalidate."
            )
        return self


class ArtifactStaleness(StrEnum):
    """Whether the artifact still matches the material it was derived from."""

    #: Verified current as of :attr:`ArtifactReceipt.created_at`.
    CURRENT = "current"
    #: An input changed underneath it. LC-P1-06 requires this to be marked, and
    #: requires the reason to be recorded — see the model validators.
    STALE = "stale"


class ArtifactReceipt(BaseModel):
    """One generated output and everything needed to say where it came from.

    ``relative_path`` is workspace-relative and canonical, so an exported bundle
    of receipts and sources resolves on the reader's machine rather than
    pointing at the machine that produced it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Annotated[int, AfterValidator(_receipt_version)] = ARTIFACT_SCHEMA_VERSION
    receipt_id: NonEmptyText
    #: The owning Task, as an opaque id — this ledger loads without the runtime.
    task_id: NonEmptyText
    kind: ArtifactKind
    #: Workspace-relative, POSIX-separated, no drive letter. See
    #: :func:`~labcairn.sources.primitives.require_workspace_relative`.
    relative_path: WorkspaceRelativePath
    #: The bytes as written. Compared, never refreshed: an artifact whose hash
    #: silently tracks its own edits is one nothing can detect a change to.
    content_sha256: ContentHash
    size_bytes: StrictNonNegInt
    #: 1 for a first emission. LC-P1-11's artifact versioning increments it
    #: rather than overwriting, so the previous bytes stay addressable.
    revision: StrictPosInt = 1

    produced_by: ArtifactProducerKind
    #: Which stage or which operator version. Never empty — see the class
    #: docstring on :class:`ArtifactProducerKind`.
    producer_id: NonEmptyText

    #: The provenance chain. May be empty only for an artifact nothing was
    #: derived from; a report that cites nothing is still a recordable outcome,
    #: and forcing a fake input here would be worse than saying none.
    derived_from: tuple[DerivationRef, ...] = ()

    staleness: ArtifactStaleness = ArtifactStaleness.CURRENT
    #: Required non-empty when ``staleness`` is ``STALE``; must be absent
    #: otherwise.
    staleness_reason: NonEmptyText | None = None

    #: IANA media type when it is known and stable. ``None`` for outputs whose
    #: format is decided by the consumer; not inferred from the extension.
    media_type: NonEmptyText | None = None
    created_at: AwareDatetime

    @model_validator(mode="after")
    def _staleness_is_paired_with_a_reason(self) -> Self:
        stale = self.staleness is ArtifactStaleness.STALE
        explained = self.staleness_reason is not None
        if stale and not explained:
            raise ValueError(
                "a stale receipt must carry staleness_reason. ADR-0004 I4 marks "
                "downstream artifacts stale when the source changes; a stale mark "
                "nobody can act on is decoration, not a state."
            )
        if explained and not stale:
            raise ValueError(
                "staleness_reason is set on a current receipt. A reason attached to "
                "something that is not stale is a claim about something that did not "
                "happen."
            )
        return self

    @model_validator(mode="after")
    def _derivations_are_distinct(self) -> Self:
        seen: set[tuple[DerivationTargetKind, str]] = set()
        for reference in self.derived_from:
            key = (reference.target_kind, reference.target_id)
            if key in seen:
                raise ValueError(
                    f"duplicate derivation target: {reference.target_kind.value!r} "
                    f"{reference.target_id!r}. One upstream thing cited twice is one "
                    f"dependency, and listing it twice makes 'how many inputs' "
                    f"answerable two ways."
                )
            seen.add(key)
        return self
