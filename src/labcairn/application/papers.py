"""The version graph's writer: storing a project, a version and an edge.

**What this module is.** LC-P2-09 T00. LC-P2-08 landed the contracts and the
checks for the paper project and the version graph, and landed no way to
*store* them: ``confirm_edge`` builds in-memory edges, ``propose_alignment``
builds a proposal, and nothing in ``src/`` wrote a row. So an edge that a
feedback chain needs to name could not exist, and **an edge that cannot exist
is a reference to nothing.**

**What it does, and what it does not.** It stores the three things the version
graph is made of, reads them back **as the frozen models rather than as
rows**, and **refuses what the models refuse**. The models are the checks:
this module asks them and reports their answers, and it does not restate a
single one of their rules. What it adds is the two facts a CHECK constraint
cannot see — which file a version came from, and whether an edge's two
versions are inside the edge's project.

**The store's job is to write what the models accept.** That is why a row the
contract refuses is not written, and why a row the contract refuses is not
*readable* as a valid one either: the round trip goes through
:meth:`~labcairn.papers.versions.VersionEdge.model_validate`, so the three
facts that stay apart are checked on the way out as well as on the way in.

**And two facts that had nowhere to live now have somewhere.**

- **A version keeps the bytes it was recorded with.** The row names the
  *file*, and a file's bytes move when it is re-ingested — so a version that
  took its identity from the file would move with it, and the rule that two
  files with the same bytes are one version could not be held. The hash is
  written when the version is written and read from the row, so the version
  is that set of bytes for ever.
- **A refusal is written down.** It is the one outcome that leaves no mark
  on the graph, and a proposal that was looked at and turned down would
  otherwise be indistinguishable from a proposal nobody had looked at. The
  refusal gets a row of its own: who looked, when, why, and about which
  proposal. **A refusal is not an absence of a row.**

The two gates
-------------

**Every operation goes through the capability model**, and the capability is
one the repository already has.

- **A version and an edge are records *about* material.** A version says
  "this ingested file is a version of this manuscript"; an edge says "this
  version came from that one". Neither draws bytes out of the material, and
  both are about it — which is exactly the posture
  :mod:`labcairn.application.evidence` takes for a claim, and it uses the same
  capability for the same reason: *a second capability for "write a record
  about this material" would be a second spelling of the same decision.* So
  the capability is ``source.inventory`` and the resource is the material's
  own path.
- **A project is not material.** It names a workspace, a pseudonym and a
  consent reference, and it says of no file at all — which is why the
  contract says a project with no grant is *"readable as a project and
  unreadable as a material"*. The project row is the task's own record, so it
  is asked about on the task's own area, under ``fs.write`` for the write and
  ``fs.read`` for the read.

**And the material's own consent is asked about as well.** The capability
answers *may this operation touch this path*; the **grant** answers *may this
material be used, by this project, for this purpose*. Both must answer yes,
and neither answers for the other — the same two-gate shape
:mod:`labcairn.application.model_transmit` has, and the same reason: an
approval is minted for the *operation*, and the material is governed by the
grant.

So the operations that touch material also ask LC-P2-06's own check —
``may_use`` with ``store_read``, over the grants the store holds — and
**a project whose grant does not cover the material is refused**. And
``PaperProject.consent_ref`` is **resolved rather than merely recorded**: a
project that names a grant the store does not hold has named nothing, and
the write is refused.

**What the grant does not do.** It does not replace the capability check and
the capability check does not replace it, and neither of them mints an
approval: an approval is a person's answer about one operation, and it is
not asked for here.

Idempotency, and what "the same operation twice" means
-------------------------------------------------------

**An id is minted once, and a second write with it is refused by name.** Not
a no-op: a no-op would make a caller that wrote the wrong payload believe it
had succeeded, and the refusal says which id is taken. The correction path
does not go through that door — a correction writes a *new* edge and then
points the old one at it, and only that one pointer is written.

**And a correction never overwrites.** The proposal the system made is
evidence about what the system got wrong, so the corrected edge is a second
row and the original keeps its parent, its child, its confidence and its
evidence. The one thing written on the original is the pointer to its
replacement.

What is never invented
----------------------

**No row carries a field the caller did not name.** There is no default
project, no default parent, no default decision and no default moment: the
request models make the project's workspace, the edge's parent and child, the
edge's source and confidence, and the confirmation's decider and moment
required. The two defaults that survive are the ones that state a fact
rather than invent one — a stage candidate of ``unknown`` says the system
inferred nothing, and a status of ``unresolved`` says the version's place in
the sequence is not established, which is where nearly every version starts.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from labcairn.application import consent
from labcairn.application.context import ApplicationContext
from labcairn.application.models import Result
from labcairn.application.refusal import (
    ApplicationRefusal,
    ApplicationRefusedError,
    consent_refusal_name,
    paper_refusal_name,
)
from labcairn.core.ids import new_id
from labcairn.db.repository import (
    VersionStoreError,
    accept_version_edge,
    list_access_grants,
    list_paper_versions,
    list_version_edge_rejections,
    list_version_edges,
    load_paper_project,
    load_paper_version,
    load_source,
    load_version_edge,
    load_version_source_id,
    put_paper_project,
    put_paper_version,
    put_version_edge,
    put_version_edge_rejection,
    supersede_version_edge,
)
from labcairn.papers.versions import (
    Confirmation,
    ConfirmationOutcome,
    EdgeSource,
    PaperProject,
    PaperVersion,
    StageCandidate,
    VersionEdge,
    VersionEdgeRejection,
    VersionStatus,
    confirm_edge,
)
from labcairn.security.capabilities import CapabilityId
from labcairn.security.permissions import may_use
from labcairn.security.policy import Permission
from labcairn.sources.source import Source

__all__ = [
    "ConfirmationRecorded",
    "ConfirmationRequest",
    "EdgeRequest",
    "EdgeStored",
    "ProjectRequest",
    "ProjectStored",
    "VersionRequest",
    "VersionStored",
    "list_edges",
    "list_rejections",
    "list_versions",
    "read_edge",
    "read_project",
    "read_version",
    "record_confirmation",
    "record_edge",
    "record_project",
    "record_version",
]


# --------------------------------------------------------------------------- #
# the requests
# --------------------------------------------------------------------------- #


class ProjectRequest(Result):
    """What a paper project is called, and whose it is.

    **The workspace is named, not derived.** A project says which workspace
    its material lives in, and a default would put a project somewhere the
    caller never chose.

    **``consent_ref`` is a reference and not a permission.** It names the
    grant LC-P2-06 will resolve; it grants nothing by being present, and a
    project with no grant is readable as a project and unreadable as material.
    """

    project_id: str
    workspace_id: str
    #: A pseudonym for the subject. **Never** the author's name.
    subject_pseudonym: str
    consent_ref: str | None = None


class VersionRequest(Result):
    """One version of a manuscript.

    **The file is named and the bytes are not.** The bytes are the file's
    own, and the store reads them from the ledger's row for that file — so a
    version cannot claim to be a file it is not.

    **``stage_candidate`` and ``status`` default to the honest answers.**
    ``unknown`` says the system inferred no stage, and ``unresolved`` says the
    version's place in the sequence is not established — which is the state
    nearly every version starts in, and the state an unresolved version is
    *listed* in rather than hidden.
    """

    version_id: str
    project_id: str
    #: The ingested file this version came from.
    source_id: str
    #: The label the author's file name gave, kept verbatim. **Not evidence
    #: of order.**
    version_label_raw: str
    stage_candidate: StageCandidate = StageCandidate.UNKNOWN
    status: VersionStatus = VersionStatus.UNRESOLVED


class EdgeRequest(Result):
    """One relationship between two versions: parent to child.

    **``source`` and ``confidence`` are required.** *How* the relationship
    was established and *how strong the evidence is* are two different facts,
    and a default for either would be a default for a claim. A confidence is a
    number and never a decision.

    **``accepted_by`` and ``accepted_at`` are set together or not at all**,
    and the contract refuses the half-set case: an acceptance nobody can
    place in time is not a decision anybody made. Both default to absent,
    which is what a proposal is.

    **``edge_version`` and ``superseded_by`` are the correction's own
    bookkeeping**, and a first edge is version 1 with nothing superseding it.
    """

    edge_id: str
    project_id: str
    parent_version_id: str
    child_version_id: str
    #: How the relationship was established: ``evidence``, ``human`` or
    #: ``model``.
    source: EdgeSource
    confidence: float
    evidence_spans: tuple[str, ...] = ()
    accepted_by: str | None = None
    accepted_at: datetime | None = None
    edge_version: int = 1
    superseded_by: str | None = None


class ConfirmationRequest(Result):
    """A person's decision about a proposed edge.

    **The decider and the moment are required.** A decision is a person's and
    it happens at a time, and neither is invented here — a default would
    attribute a decision to nobody, at a moment nobody chose.

    **``corrected_parent_version_id`` is the correction's own answer**, and
    it is absent for the other two outcomes. A correction that does not say
    what the right answer is is not a correction, and the contract refuses it.
    """

    edge_id: str
    outcome: ConfirmationOutcome
    decided_by: str
    decided_at: datetime
    reason: str = ""
    corrected_parent_version_id: str | None = None


# --------------------------------------------------------------------------- #
# the results
# --------------------------------------------------------------------------- #


class ProjectStored(Result):
    """The project the store now holds."""

    project: PaperProject


class VersionStored(Result):
    """The version the store now holds."""

    version: PaperVersion


class EdgeStored(Result):
    """The edge the store now holds."""

    edge: VersionEdge


class ConfirmationRecorded(Result):
    """What a person's decision produced, and what the store now holds.

    **The confirmation is the contract's own object**, whole — the outcome,
    the decider, the moment, the reason, and both edges. A caller that
    wanted only the new edge would have to read the decision's shape anyway,
    and a decision that lost half of itself on the way out would be a
    decision nobody could check.
    """

    confirmation: Confirmation


# --------------------------------------------------------------------------- #
# the operations
# --------------------------------------------------------------------------- #


def record_project(
    context: ApplicationContext,
    request: ProjectRequest,
    *,
    now: datetime | None = None,
) -> ProjectStored:
    """Write the project row.

    **The project is written once.** A second write with the same id is
    refused by name, because a project that overwrote another would leave an
    archive saying two things about one manuscript.

    :raises ApplicationRefusedError: the policy denied the task's own area,
        the contract refused the project, or the id is already recorded.
    """
    moment = now if now is not None else datetime.now(UTC)
    _require_task_area(context, CapabilityId.FS_WRITE)
    if request.consent_ref is not None:
        # **The consent is resolved, not merely recorded.** A project that
        # names a grant the store does not hold has named nothing.
        _require_the_named_grant(
            context,
            request.consent_ref,
            project_id=request.project_id,
            at=moment,
        )
    project = _the_model(
        PaperProject,
        {
            "project_id": request.project_id,
            "workspace_id": request.workspace_id,
            "subject_pseudonym": request.subject_pseudonym,
            "consent_ref": request.consent_ref,
        },
    )
    with _store_refusals(context.store.session):
        put_paper_project(context.store.session, project, created_at=moment)
        context.store.session.commit()
    return ProjectStored(project=project)


def record_version(
    context: ApplicationContext,
    request: VersionRequest,
    *,
    now: datetime | None = None,
) -> VersionStored:
    """Write the row for one version.

    **The bytes come from the file the caller named.** The version is
    rebuilt with the ledger's own hash for that file, so a version cannot
    claim to be a file it is not.

    :raises ApplicationRefusedError: the project or the file does not exist,
        the policy denied the material, the contract refused the version, or
        the id is already recorded.
    """
    moment = now if now is not None else datetime.now(UTC)
    _require_project(context, request.project_id)
    _require_grant(context, request.project_id, at=moment)
    source = _the_source(context, request.source_id)
    _require_material(context, source)
    version = _the_model(
        PaperVersion,
        {
            "version_id": request.version_id,
            "project_id": request.project_id,
            "source_content_sha256": source.content_sha256,
            "version_label_raw": request.version_label_raw,
            "stage_candidate": request.stage_candidate,
            "status": request.status,
        },
    )
    with _store_refusals(context.store.session):
        put_paper_version(
            context.store.session,
            version,
            source_id=source.source_id,
            created_at=moment,
        )
        context.store.session.commit()
    return VersionStored(version=version)


def record_edge(
    context: ApplicationContext,
    request: EdgeRequest,
    *,
    now: datetime | None = None,
) -> EdgeStored:
    """Write the row for one edge between two versions.

    **The contract is asked before the row is written.** The edge is rebuilt
    through the frozen model — so the self-parent and the three facts that
    stay apart are checked — and the store asks the cross-project rule, which
    is a fact about three rows and a CHECK constraint cannot see it.

    **A proposal may be written.** An edge with no acceptor is a proposal,
    and it is the normal state of an edge the system inferred and no person
    has confirmed; a store that refused it could not record a proposal at
    all.

    :raises ApplicationRefusedError: the project or one of the versions does
        not exist, the policy denied the material, the contract refused the
        edge, the edge crosses a project, or the id is already recorded.
    """
    moment = now if now is not None else datetime.now(UTC)
    _require_project(context, request.project_id)
    _require_grant(context, request.project_id, at=moment)
    _require_material(context, _the_version_source(context, request.parent_version_id))
    _require_material(context, _the_version_source(context, request.child_version_id))
    edge = _the_model(
        VersionEdge,
        {
            "edge_id": request.edge_id,
            "project_id": request.project_id,
            "parent_version_id": request.parent_version_id,
            "child_version_id": request.child_version_id,
            "source": request.source,
            "confidence": request.confidence,
            "evidence_spans": request.evidence_spans,
            "accepted_by": request.accepted_by,
            "accepted_at": request.accepted_at,
            "edge_version": request.edge_version,
            "superseded_by": request.superseded_by,
        },
    )
    with _store_refusals(context.store.session):
        put_version_edge(context.store.session, edge, created_at=moment)
        context.store.session.commit()
    return EdgeStored(edge=edge)


def record_confirmation(
    context: ApplicationContext,
    request: ConfirmationRequest,
    *,
    now: datetime | None = None,
) -> ConfirmationRecorded:
    """Apply a person's decision to a proposed edge, and record what it produced.

    **The three outcomes produce three different shapes, and the store
    follows each one.** An acceptance settles the stored edge in place — the
    same edge, with an acceptor and a moment, and the confidence untouched,
    because how strong the evidence was is still a fact about the evidence. A
    correction writes a **second** edge naming the parent the person meant,
    and points the proposal at it. A rejection writes **no edge at all**,
    because there is no relationship here.

    **A rejection is written down.** It is the one outcome that leaves no
    mark on the graph — there is no relationship to record — so the refusal
    gets a row of its own: who looked, when, why, and about which proposal.
    **A refusal is not an absence of a row.** A proposal that was looked at
    and turned down is a fact about the archive, and without the row it would
    be indistinguishable from a proposal nobody had looked at, and the next
    run would propose it again having learned nothing from the refusal.

    :raises ApplicationRefusedError: there is no such edge, the policy denied
        the material, or the contract refused the decision.
    """
    moment = now if now is not None else datetime.now(UTC)
    proposal = read_edge(context, request.edge_id, now=moment)
    try:
        confirmation = confirm_edge(
            proposal,
            request.outcome,
            decided_by=request.decided_by,
            decided_at=request.decided_at,
            reason=request.reason,
            corrected_parent_version_id=request.corrected_parent_version_id,
            edge_id_factory=lambda: str(new_id()),
        )
    except ValueError as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.PAPER_CONTRACT_REFUSED,
            f"the decision was refused: {error}",
        ) from error

    with _store_refusals(context.store.session):
        if confirmation.outcome is ConfirmationOutcome.ACCEPTED:
            accepted = confirmation.edge
            assert accepted is not None  # the contract's own shape
            accept_version_edge(context.store.session, accepted)
        elif confirmation.outcome is ConfirmationOutcome.CORRECTED:
            corrected = confirmation.edge
            superseded = confirmation.corrects
            assert corrected is not None and superseded is not None  # the contract's shape
            # **The correction names a version of its own**, and that
            # version's material is asked about too: a relationship the
            # policy denies must not be recorded by the back door of a
            # correction.
            _require_material(context, _the_version_source(context, corrected.parent_version_id))
            # The correction is a second edge, and the proposal it corrects
            # is left readable with a pointer to its replacement.
            put_version_edge(context.store.session, corrected, created_at=moment)
            supersede_version_edge(
                context.store.session,
                superseded.edge_id,
                corrected.edge_id,
            )
        else:
            # A rejection writes no edge: there is no relationship to record.
            # **It writes the record of the refusal**, which is the fact the
            # edge table cannot hold.
            rejection = VersionEdgeRejection(
                rejection_id=str(new_id()),
                edge_id=proposal.edge_id,
                project_id=proposal.project_id,
                decided_by=confirmation.decided_by,
                decided_at=confirmation.decided_at,
                reason=confirmation.reason,
            )
            put_version_edge_rejection(
                context.store.session,
                rejection,
                created_at=moment,
            )
        context.store.session.commit()
    return ConfirmationRecorded(confirmation=confirmation)


def read_project(context: ApplicationContext, project_id: str) -> PaperProject:
    """The project the store holds, as the frozen contract.

    :raises ApplicationRefusedError: the policy denied the task's own area,
        or there is no such project.
    """
    _require_task_area(context, CapabilityId.FS_READ)
    with _store_refusals(context.store.session):
        project = load_paper_project(context.store.session, project_id)
    if project is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.PAPER_PROJECT_NOT_FOUND,
            f"the store holds no paper project with the id {project_id!r}.",
        )
    return project


def read_version(
    context: ApplicationContext,
    version_id: str,
    *,
    now: datetime | None = None,
) -> PaperVersion:
    """The version the store holds, as the frozen contract.

    **The material is asked about before the version is handed back**, because
    a version discloses the file it came from — and the project's grant is
    asked about too, because that is what the file's use depends on.

    :raises ApplicationRefusedError: the policy denied the material, no grant
        covers the project, there is no such version, or the stored row does
        not make one.
    """
    moment = now if now is not None else datetime.now(UTC)
    with _store_refusals(context.store.session):
        version = load_paper_version(context.store.session, version_id)
    if version is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.PAPER_VERSION_NOT_FOUND,
            f"the store holds no version with the id {version_id!r}.",
        )
    _require_grant(context, version.project_id, at=moment)
    _require_material(context, _the_version_source(context, version_id))
    return version


def read_edge(
    context: ApplicationContext,
    edge_id: str,
    *,
    now: datetime | None = None,
) -> VersionEdge:
    """The edge the store holds, as the frozen contract.

    **Both of the edge's materials are asked about**, because the edge names
    two files and disclosing one of them is disclosing half the claim — and
    the project's grant is asked about too.

    :raises ApplicationRefusedError: the policy denied the material, no grant
        covers the project, there is no such edge, or the stored row does not
        make one.
    """
    moment = now if now is not None else datetime.now(UTC)
    with _store_refusals(context.store.session):
        edge = load_version_edge(context.store.session, edge_id)
    if edge is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.PAPER_EDGE_NOT_FOUND,
            f"the store holds no edge with the id {edge_id!r}.",
        )
    _require_grant(context, edge.project_id, at=moment)
    _require_material(context, _the_version_source(context, edge.parent_version_id))
    _require_material(context, _the_version_source(context, edge.child_version_id))
    return edge


def list_rejections(
    context: ApplicationContext,
    edge_id: str,
    *,
    now: datetime | None = None,
) -> tuple[VersionEdgeRejection, ...]:
    """The refusals of one edge, oldest first.

    **This is how the archive answers "was this proposal ever looked at?"**
    An edge with no acceptor and no replacement has either been looked at
    and turned down or never looked at, and the two are different facts —
    and the difference is what stops the next run proposing it again.

    :raises ApplicationRefusedError: the policy denied the material, no grant
        covers the project, or there is no such edge.
    """
    moment = now if now is not None else datetime.now(UTC)
    edge = read_edge(context, edge_id, now=moment)
    with _store_refusals(context.store.session):
        return list_version_edge_rejections(context.store.session, edge.edge_id)


def list_versions(
    context: ApplicationContext,
    project_id: str,
    *,
    now: datetime | None = None,
) -> tuple[PaperVersion, ...]:
    """A project's versions, oldest first.

    **Denied versions are dropped, not refused.** A listing that refuses
    because one entry is denied discloses that the entry is there and denies
    work the operator wanted allowed; a version named on its own is refused.
    The two are different answers on purpose.

    :raises ApplicationRefusedError: there is no such project, or no grant
        covers it.
    """
    moment = now if now is not None else datetime.now(UTC)
    _require_project(context, project_id)
    _require_grant(context, project_id, at=moment)
    with _store_refusals(context.store.session):
        versions = list_paper_versions(context.store.session, project_id)
    kept: list[PaperVersion] = []
    for version in versions:
        try:
            _require_material(context, _the_version_source(context, version.version_id))
        except ApplicationRefusedError as error:
            if error.reason is ApplicationRefusal.PERMISSION_DENIED:
                continue
            raise
        kept.append(version)
    return tuple(kept)


def list_edges(
    context: ApplicationContext,
    project_id: str,
    *,
    now: datetime | None = None,
) -> tuple[VersionEdge, ...]:
    """A project's edges, oldest first.

    **Denied edges are dropped, not refused**, for the reason
    :func:`list_versions` gives.

    :raises ApplicationRefusedError: there is no such project, or no grant
        covers it.
    """
    moment = now if now is not None else datetime.now(UTC)
    _require_project(context, project_id)
    _require_grant(context, project_id, at=moment)
    with _store_refusals(context.store.session):
        edges = list_version_edges(context.store.session, project_id)
    kept: list[VersionEdge] = []
    for edge in edges:
        try:
            _require_material(context, _the_version_source(context, edge.parent_version_id))
            _require_material(context, _the_version_source(context, edge.child_version_id))
        except ApplicationRefusedError as error:
            if error.reason is ApplicationRefusal.PERMISSION_DENIED:
                continue
            raise
        kept.append(edge)
    return tuple(kept)


# --------------------------------------------------------------------------- #
# the gate
# --------------------------------------------------------------------------- #


def _require_grant(context: ApplicationContext, project_id: str, *, at: datetime) -> None:
    """Ask LC-P2-06's permission check whether the project's grant covers this.

    **The absence of a row is the refusal.** ADR-0015 D2 says the permission
    is denied *in the model*: there is no row, so there is nothing to check,
    so the path cannot proceed. This is that rule, asked through the consent
    layer's own check — ``may_use`` with ``store_read`` — over the grants the
    store holds.

    **And it is the second gate, not the first.** The capability says *may
    this operation touch this path*; the grant says *may this material be
    used, by this project, for this purpose*. Both must answer yes, and
    neither answers for the other: a grant naming provider A does not
    authorise provider B, and a path rule says nothing about whose material
    it is.

    **The grant that governs is the one the project names.** A project that
    names no grant has no consent, and the contract's own words are that such
    a project is *"readable as a project and unreadable as a material"* — so
    the absence of a named grant refuses the material, and it is not enough
    that some other grant happens to cover the same project.

    **The grants come from the store, not from the caller.** The store is
    the authority on what was permitted, and a caller that gathered fewer
    grants than the store holds would be asking the question about a smaller
    world.

    :raises ApplicationRefusedError: no grant covers this project's material.
    """
    with _store_refusals(context.store.session):
        project = load_paper_project(context.store.session, project_id)
    if project is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.PAPER_PROJECT_NOT_FOUND,
            f"the store holds no paper project with the id {project_id!r}.",
        )
    if project.consent_ref is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.CONSENT_NO_GRANT,
            f"the project {project_id!r} names no grant, so nothing permits its "
            "material to be used. A project with no grant is readable as a project "
            "and unreadable as a material; the remedy is a grant.",
        )
    _require_the_named_grant(
        context,
        project.consent_ref,
        project_id=project_id,
        at=at,
    )


def _require_the_named_grant(
    context: ApplicationContext,
    consent_ref: str,
    *,
    project_id: str,
    at: datetime,
) -> None:
    """The grant a project names must be there, and must cover the project.

    **A reference that names nothing is not a consent.** ``consent_ref`` is a
    reference and not a permission -- it grants nothing by being present --
    and a reference to a grant the store does not hold resolves to nothing at
    all. So the grant is resolved here, at the moment the project is written,
    rather than left as a string for a reader to chase.

    **A project with no grant is still a project.** ``consent_ref`` may be
    absent, and the project is then readable as a project and unreadable as
    material -- which is the contract's own distinction, and the material
    operations refuse such a project because no grant covers it.
    """
    named = [
        grant
        for grant in list_access_grants(context.store.session)
        if grant.grant_id == consent_ref
    ]
    decision = may_use(
        named,
        permission="store_read",
        purpose="read",
        subject_ref=project_id,
        at=at,
    )
    if not decision.allowed:
        reason = decision.reason
        assert reason is not None  # a refused check always carries a reason
        raise ApplicationRefusedError(consent_refusal_name(reason), decision.detail)


def _require_material(context: ApplicationContext, source: Source) -> None:
    """Ask the policy about the material, and refuse a denial or a question.

    **The resource is the material's own path**, and the capability is
    ``source.inventory`` — the same one a claim about the material is
    recorded under, because a version and a claim are the same kind of thing:
    a record about material, made without drawing bytes out of it.

    **A question is refused too.** An ASK is a question the operator has not
    answered yet, and the answer would be an approval. This operation has no
    approval to present, so the material the policy asked about is not
    recorded.
    """
    resource = context.resource_for(source.relative_path)
    authorisation = consent.evaluate(
        context,
        capability=CapabilityId.SOURCE_INVENTORY,
        arguments={},
        resource=resource,
    )
    if authorisation.permission is Permission.ASK:
        raise ApplicationRefusedError(
            ApplicationRefusal.POLICY_ASKED,
            f"the policy asked about {CapabilityId.SOURCE_INVENTORY.value} on "
            f"{resource.resolved_key!r}, and no approval was supplied. A record "
            "about material the policy asked about needs consent: grant the "
            "approval and record it again.",
        )


def _require_task_area(context: ApplicationContext, capability: CapabilityId) -> None:
    """Ask the policy about the task's own area.

    **This is the gate for the project row, and it is the weakest one here.**
    A project names a workspace and a pseudonym and no file at all, so there
    is no material to ask about; what it *is* is the task's own record of the
    manuscript it is working on, and the repository's way of asking "may this
    task record something here?" is its own area. The consent that actually
    governs a project is the grant its ``consent_ref`` names, and nothing in
    ``src/`` can resolve that yet — LC-P2-06's grant table has no reader.
    """
    resource = context.task_area()
    authorisation = consent.evaluate(
        context,
        capability=capability,
        arguments={},
        resource=resource,
    )
    if authorisation.permission is Permission.ASK:
        raise ApplicationRefusedError(
            ApplicationRefusal.POLICY_ASKED,
            f"the policy asked about {capability.value} on "
            f"{resource.resolved_key!r}, and no approval was supplied. A record "
            "the policy asked about needs consent: grant the approval and "
            "record it again.",
        )


# --------------------------------------------------------------------------- #
# the store's answers
# --------------------------------------------------------------------------- #


def _require_project(context: ApplicationContext, project_id: str) -> None:
    """Refuse a write or a read of a project the store does not hold.

    **A project that does not exist is not an empty project.** The store
    would accept the row and let the foreign key refuse it at COMMIT, which
    is a constraint error out of the middle of a transaction rather than an
    answer the caller can act on.
    """
    with _store_refusals(context.store.session):
        project = load_paper_project(context.store.session, project_id)
    if project is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.PAPER_PROJECT_NOT_FOUND,
            f"the store holds no paper project with the id {project_id!r}.",
        )


def _the_source(context: ApplicationContext, source_id: str) -> Source:
    """The material the caller named, as the ledger holds it.

    **A source the ledger does not hold is the ledger's refusal**, and the
    layer already has a name for it: a file nobody ingested cannot be a
    version of anything.
    """
    with _store_refusals(context.store.session):
        source = load_source(context.store.session, source_id)
    if source is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.SOURCE_NOT_FOUND,
            f"the ledger holds no source with the id {source_id!r}. A version with "
            "no file is not a version.",
        )
    return source


def _the_version_source(context: ApplicationContext, version_id: str) -> Source:
    """The file a stored version came from."""
    with _store_refusals(context.store.session):
        source_id = load_version_source_id(context.store.session, version_id)
    if source_id is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.PAPER_VERSION_NOT_FOUND,
            f"the store holds no version with the id {version_id!r}, so it names no file.",
        )
    return _the_source(context, source_id)


#: The model a payload is built into.


def _the_model[ModelT: BaseModel](model: type[ModelT], payload: Mapping[str, object]) -> ModelT:
    """The frozen contract for this payload, or a refusal naming what is wrong.

    **The contract is asked, not restated.** The version's label length, the
    edge's confidence range and the three facts that stay apart are the
    contract's rules, and a second statement of them here would be a second
    thing to keep in step.
    """
    try:
        return model.model_validate(payload)
    except ValidationError as error:
        raise ApplicationRefusedError(
            ApplicationRefusal.PAPER_CONTRACT_REFUSED,
            f"the arguments do not make a {model.__name__}: {error}. Nothing was written.",
        ) from error


@contextmanager
def _store_refusals(session: Session) -> Iterator[None]:
    """The store's refusals, translated into the layer's one.

    **And the transaction is rolled back**, because the store's writes are
    pending in the session and a refusal that left them there would leave a
    half-applied write for the next caller to commit.
    """
    try:
        yield
    except VersionStoreError as error:
        session.rollback()
        raise ApplicationRefusedError(
            paper_refusal_name(error.reason),
            error.detail,
        ) from error
