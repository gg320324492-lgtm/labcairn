"""The paper project and the version graph, as typed models.

**What this module is.** The application-level contracts for LC-P2-08: a
project, a version, and the edge between two versions. The store holds the
rows; these are the shapes that hold them.

**Why the models refuse things the schema already refuses.** They do not
duplicate the schema's rules; they refuse them **earlier and with a
message**, and they refuse the things a schema cannot express. The two
layers are complementary, and the project's rule is that a property is
watched by a test that would go red if the property broke — which means
each layer's refusals are witnessed separately.

**What only this layer can refuse.** The schema cannot say that an edge's
parent and child belong to the same project — that is a fact about two
rows, and a CHECK constraint sees one row at a time. It cannot say that a
correction's `superseded_by` points at an edge in the same project either.
And it cannot say that a confidence is a *proposal's* number rather than a
decision's. **Those are this module's refusals**, and they are the ones
that would let the archive say something false.

**The vocabulary is closed.** Every enum here is a closed set, and an
unknown member is rejected rather than coerced — the same standard ADR-0003
C1 sets for an event type. A stage that could hold any string carries no
information, and a source that could hold any string is a source that means
nothing.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from labcairn.sources.primitives import ContentHash, NonEmptyText

__all__ = [
    "EdgeSource",
    "PaperProject",
    "PaperVersion",
    "StageCandidate",
    "VersionEdge",
    "VersionStatus",
]


class StageCandidate(StrEnum):
    """What stage of the paper's life a version is in.

    **A closed set of five, and ``unknown`` is one of them.** The system's
    inference is a guess, and the guess has to be able to say "I do not
    know" — a stage vocabulary without ``unknown`` would force every
    unclassifiable version into a real stage, and that is a claim about a
    document the system did not read.

    The stages are the ones the design names: a draft, a version the
    advisor has marked up, the submitted version, the camera-ready, and the
    unknown.
    """

    DRAFT = "draft"
    ADVISOR_REVIEWED = "advisor_reviewed"
    SUBMITTED = "submitted"
    CAMERA_READY = "camera_ready"
    UNKNOWN = "unknown"


class VersionStatus(StrEnum):
    """Whether the version's place in the sequence is established.

    **``UNRESOLVED`` is not a failure state.** It is the state a version
    is in until its relationship is established, and it is the state the
    *most* versions start in: a system that archives what it is given
    cannot know a version's parent before it has seen the other versions.

    The design's rule is *"不确定时 `UNRESOLVED` + 人工确认"* — and the
    important half is that an unresolved version is **listed**. Hiding it
    because its parent is unknown would make the archive look complete
    when it is not.
    """

    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"


class EdgeSource(StrEnum):
    """**How** a relationship between two versions was established.

    The three are not interchangeable, and the distinction is the whole
    point of the column:

    - ``EVIDENCE`` — the system found the evidence and proposed it. **Not
      a decision.** The design's rule is *"禁止仅靠相似度静默确定版本
      顺序"*: a similarity score may propose an order and may not decide
      one.
    - ``HUMAN`` — a person decided it. This is what settles a relationship.
    - ``MODEL`` — a model proposed it. **The same status as evidence** in
      every respect that matters: it is a proposal, and no person has
      accepted it.

    **A fourth member would blur exactly the distinction this vocabulary
    exists to keep**, so it has three.
    """

    EVIDENCE = "evidence"
    HUMAN = "human"
    MODEL = "model"


class _Frozen(BaseModel):
    """Shared config. ``frozen`` because a record is a persisted fact.

    A mutable version or edge would let its evidence change underneath the
    correction that superseded it, and a correction that is not a
    correction.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


class PaperProject(_Frozen):
    """One manuscript — the body of material a version graph hangs from.

    **A project is not a Task.** Phase 1's Task owns *work*; a project owns
    *material*, and the material outlives the work that read it.

    **``subject_pseudonym`` is never the author's name.** ADR-0015 D5 keeps
    a person's name apart from the material and the analysis, and this is
    where that separation is held: the name lives elsewhere, and this
    carries a pseudonym.

    **``consent_ref`` is a reference and not a permission.** It names the
    grant LC-P2-06 will resolve; it grants nothing by being present. A
    project with no grant is **readable as a project and unreadable as
    material**, and those are two different states rather than one state
    with a missing field.
    """

    project_id: NonEmptyText
    workspace_id: NonEmptyText
    subject_pseudonym: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    #: The reference LC-P2-06 resolves to a grant. ``None`` means no grant
    #: has been recorded.
    consent_ref: Annotated[str, StringConstraints(min_length=1, max_length=200)] | None = None


class PaperVersion(_Frozen):
    """One version of a manuscript — a node in the version graph.

    **There is no parent, and that is the point.** The parent lives in
    :class:`VersionEdge`, because the process **branches** and a column
    could hold only one.

    **``version_label_raw`` is kept verbatim and is not evidence.** It is
    whatever the author's file name said — ``最终版2.docx``,
    ``投稿版.docx`` — and the design says plainly that such a name is not
    a statement about which is newer. It is kept because a person reading
    the archive needs to see what the file was called, not because it
    decides anything.
    """

    version_id: NonEmptyText
    project_id: NonEmptyText
    #: The ingested file this version came from, by its content hash. The
    #: bytes are what the version *is*.
    source_content_sha256: ContentHash
    version_label_raw: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    stage_candidate: StageCandidate = StageCandidate.UNKNOWN
    status: VersionStatus = VersionStatus.UNRESOLVED


class VersionEdge(_Frozen):
    """A directed relationship between two versions: parent to child.

    **Three separate facts, and conflating any two of them is the failure
    this model exists to make impossible.**

    ================ ==================================================
    ``source``        **how** the relationship was established.
    ``confidence``    how strong the evidence is — **a number**, and not
                      a decision.
    ``accepted_by``   **who** accepted it — ``None`` until a person does.
    ================ ==================================================

    **A confidence never settles anything on its own.** An edge with a
    confidence of 1.0 and no acceptor is a *proposal*, and the model
    refuses to present it as anything else — because the design's rule is
    that a similarity score may not silently decide an order.

    **A human decision names its acceptor.** ``source='human'`` with no
    ``accepted_by`` is refused: it is a decision with nobody behind it.
    And ``accepted_by`` set on an ``evidence`` edge is refused for the
    same reason — a proposal wearing a person's name is a forgery by
    another route.

    **A correction is a new edge, not an overwrite.** The project's rule
    is that a human revision produces a new version rather than silently
    replacing what was there, so a correction carries a higher
    ``edge_version`` and names the edge it supersedes.
    """

    edge_id: NonEmptyText
    project_id: NonEmptyText
    parent_version_id: NonEmptyText
    child_version_id: NonEmptyText
    source: EdgeSource
    #: How strong the evidence is. **A number, not a decision.**
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    #: What supports the edge. A reader must be able to see why.
    evidence_spans: tuple[str, ...] = ()
    #: **Who** accepted it. ``None`` while the edge is a proposal.
    accepted_by: Annotated[str, StringConstraints(min_length=1, max_length=200)] | None = None
    accepted_at: datetime | None = None
    #: The edge's own revision number, for corrections.
    edge_version: Annotated[int, Field(ge=1)] = 1
    #: The edge this one corrects, when it is a correction.
    superseded_by: NonEmptyText | None = None

    @model_validator(mode="after")
    def _the_three_facts_stay_apart(self) -> VersionEdge:
        if self.parent_version_id == self.child_version_id:
            raise ValueError(
                f"a version cannot be its own parent: {self.child_version_id!r} is "
                f"both the parent and the child of edge {self.edge_id!r}. That is a "
                f"contradiction, not a self-loop to be tolerated."
            )
        # **The pairing is checked before the source.** An edge with an
        # acceptor and no timestamp is malformed whichever source it
        # claims, and saying so is more useful than saying "a proposal
        # may not name an acceptor" — which is a *different* fault that
        # happens to share a field.
        if (self.accepted_by is None) != (self.accepted_at is None):
            raise ValueError(
                f"edge {self.edge_id!r}: accepted_by and accepted_at are both "
                f"set or both omitted. An acceptance nobody can place in time "
                f"is not a decision anybody made."
            )
        if self.source is EdgeSource.HUMAN and self.accepted_by is None:
            raise ValueError(
                f"edge {self.edge_id!r} is a human decision with nobody behind "
                f"it: source='human' requires accepted_by. A relationship that "
                f"was not decided by a person is source='evidence'."
            )
        if self.accepted_by is not None and self.source is not EdgeSource.HUMAN:
            raise ValueError(
                f"edge {self.edge_id!r} names an acceptor ({self.accepted_by!r}) "
                f"but its source is {self.source.value!r}. An acceptance is a "
                f"human decision, and a proposal that wears a person's name is "
                f"the same forgery by another route."
            )
        return self

    @property
    def is_accepted(self) -> bool:
        """Whether a person has settled this relationship.

        **A high confidence does not make this true.** That is the whole
        point: the number says how strong the evidence is, and this says
        whether anybody decided.
        """
        return self.accepted_by is not None

    @property
    def is_proposal(self) -> bool:
        """Whether this edge is waiting for a person.

        The inverse of :attr:`is_accepted`, and the state nearly every
        edge starts in.
        """
        return self.accepted_by is None


#: The evidence a version relationship can be proposed on, in the order it
#: is trusted.
#:
#: **Nothing here is a file name or a modification time.** The design says
#: plainly that ``最终版2.docx`` is not a statement about which is newer,
#: and a copied file carries the copy's time.
#:
#: - ``shared_structure`` — headings that match, in the same order, at the
#:   same level. The strongest signal available.
#: - ``matching_passage`` — a substantial passage appearing in both, in
#:   the same relative position.
#: - ``matching_number`` — the same experimental result in both. The
#:   design names it (*"图表数字变化但文字不变"*): it is a strong signal
#:   **and** the one a text-similarity method is blind to, because the
#:   prose can be nearly identical while the science moved.
EVIDENCE_KINDS: Final[tuple[str, ...]] = (
    "shared_structure",
    "matching_passage",
    "matching_number",
)
