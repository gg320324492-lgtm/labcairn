"""The version graph's writer: what it stores, what it refuses, and what it reads back.

**What is under test.** LC-P2-09 T00. LC-P2-08 landed the contracts and the
checks for the paper project and the version graph, and landed no way to
*store* them — so this file is about the gap: a version and an edge can be
written, they come back as the models rather than as rows, and **the store
refuses what the models refuse**.

**The properties, and what breaks each one.**

- **The read-back is the model, not a row.** A version and an edge are
  rebuilt through the frozen contracts, so a row the contract refuses is not
  readable as a valid one either. *Broken by:* a reader that hands back the
  row's fields without asking the contract.
- **The store refuses what the models refuse.** The self-parent, the human
  source with nobody behind it, the acceptance with no moment, and the edge
  that crosses a project. *Broken by:* a store that writes the row and lets
  the database's own constraints decide.
- **A correction does not overwrite the proposal.** The proposal the system
  made is evidence about what the system got wrong, so the correction is a
  second edge and the first stays readable. *Broken by:* writing the
  corrected parent over the proposal.
- **An id is minted once.** A second write with an id that is taken is
  refused by name. *Broken by:* an upsert that turns a second claim about one
  pair of versions into a second row wearing one name.
- **A refusal is written down.** A rejection is the one outcome that leaves
  no mark on the graph, so it gets a row of its own: who looked, when, why,
  and about which proposal. *Broken by:* a store that treats the refusal as
  nothing to write — and then a proposal that was turned down is
  indistinguishable from one nobody looked at.
- **A version's identity does not move.** The bytes are recorded when the
  version is written, so re-ingesting the file leaves the version alone.
  *Broken by:* a reader that takes the hash from the file rather than from
  the row.
- **The material's own consent is asked about.** The capability says *may
  this operation touch this path*; the grant says *may this material be
  used*. Both must answer yes. *Broken by:* a writer that asks only the
  first, and so records material nobody permitted.

**And the refusal vocabulary is closed.** The version graph has its own
reasons, and the layer maps each of them by lookup; a reason nobody can
raise must not reach a surface as a name, and a name nothing raises is a
name a reader will look for in vain.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from docx_fixtures import Revision
from feedback_chain_fixtures import MOMENT as CHAIN_MOMENT
from feedback_chain_fixtures import ChainEnv, a_comment, build_chain
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_store_support import StoreEnv

from conftest import migrated_database_from
from labcairn.application import (
    ApplicationContext,
    ApplicationRefusal,
    ApplicationRefusedError,
    create_task,
)
from labcairn.application import chain as chain_layer
from labcairn.application.papers import (
    ConfirmationRequest,
    EdgeRequest,
    ProjectRequest,
    VersionRequest,
    list_edges,
    list_rejections,
    list_versions,
    read_edge,
    read_project,
    read_version,
    record_confirmation,
    record_edge,
    record_project,
    record_version,
)
from labcairn.application.refusal import PAPER_REFUSALS, paper_refusal_name
from labcairn.db.materials import put_source
from labcairn.db.models import RevisionEventRow
from labcairn.db.session import create_db_engine, create_session_factory
from labcairn.material.ooxml import read_document
from labcairn.papers.feedback import record_feedback
from labcairn.papers.responses import list_unaddressed
from labcairn.papers.revisions import (
    RevisionRecord,
    list_revision_events,
    record_revision_events,
)
from labcairn.papers.versions import (
    ConfirmationOutcome,
    EdgeSource,
    PaperProject,
    PaperRefusal,
    PaperVersion,
    StageCandidate,
    VersionEdge,
    VersionStatus,
)
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.policy import Permission, PermissionPolicy, Rule
from labcairn.sources.source import Source, SourceKind, SourceReadability

pytestmark = pytest.mark.integration

_MOMENT = datetime(2026, 1, 1, tzinfo=UTC)

#: The material the fixture puts in the ledger, and the path it lives at.
_FIRST = "materials/draft-1.md"
_SECOND = "materials/draft-2.md"
_SECRET = "materials/secret.md"


# --------------------------------------------------------------------------- #
# the environment
# --------------------------------------------------------------------------- #


def _allow_all() -> PermissionPolicy:
    return PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])


@pytest.fixture
def env(tmp_path: Path, migrated_database_template: Path) -> Iterator[StoreEnv]:
    """A database at head, copied from the session's template.

    **The template, not a migration per test.** Migrating the schema takes
    seconds and the suite pays it once per test that does it; the repository's
    own fixture copies an already-migrated database, and this file uses it.
    """
    path = migrated_database_from(migrated_database_template, tmp_path / "labcairn.db")
    engine = create_db_engine(path)
    factory = create_session_factory(engine)
    session = factory()
    try:
        yield StoreEnv(db_path=path, engine=engine, factory=factory, session=session)
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    (root / "materials").mkdir(parents=True)
    return root


def _add_material(context: ApplicationContext, relative_path: str, text_body: str) -> str:
    """One material in the ledger, at a path inside the workspace's source root.

    **The file is not written to disk.** The ledger holds what the ingestion
    read, and the permission boundary is asked about the *path* — so a
    material that is in the ledger and not on the disk exercises the same
    question a real one does, and costs nothing to set up.
    """
    payload = text_body.encode("utf-8")
    source = Source(
        source_id=f"src-{relative_path.replace('/', '-')}",
        kind=SourceKind.MARKDOWN,
        display_name=relative_path.rsplit("/", 1)[-1],
        relative_path=relative_path,
        content_sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        readability=SourceReadability.READABLE,
        ingested_at=_MOMENT,
    )
    put_source(context.store.session, source)
    context.store.session.commit()
    return source.source_id


def _grant(
    context: ApplicationContext,
    *,
    grant_id: str = "grant-1",
    subject_ref: str = "proj-1",
    permission: str = "store_read",
    purpose: str = "read",
    scope: str = "proj-1/**",
    state: str = "active",
    granted_at: str = "2026-01-01T00:00:00+00:00",
) -> None:
    """One grant row, in the shape LC-P2-06's table describes.

    **The product has no writer for grants yet** — LC-P2-06 landed the table
    and the check but not the path that creates one — so the row is written
    here, and what the operations ask is the store's own reader over it.
    """
    context.store.session.execute(
        text(
            "INSERT INTO access_grants (grant_id, subject_ref, permission, purpose, "
            "scope, destination, granted_by, granted_at, expires_at, state, "
            "withdrawn_at, withdrawn_by, withdrawal_reason) VALUES "
            "(:grant_id, :subject_ref, :permission, :purpose, :scope, NULL, "
            "'Prof. Lin', :granted_at, NULL, :state, NULL, NULL, NULL)"
        ),
        {
            "grant_id": grant_id,
            "subject_ref": subject_ref,
            "permission": permission,
            "purpose": purpose,
            "scope": scope,
            "granted_at": granted_at,
            "state": state,
        },
    )
    context.store.session.commit()


def _context(env: StoreEnv, workspace_root: Path) -> ApplicationContext:
    """A task, a workspace with one source root, three materials and a grant."""
    created = create_task(
        store=env.store(),
        policy=_allow_all(),
        workspace_root=workspace_root,
        title="The version graph",
        goal=TaskGoal(
            objective="Archive a manuscript and the drafts it went through.",
            success_criterion="The graph is stored, and it says what it may say.",
        ),
        source_dirs=(workspace_root / "materials",),
    )
    context = ApplicationContext(
        workspace=created.workspace,
        store=env.store(),
        policy=_allow_all(),
        ledger=ApprovalLedger(),
    )
    _add_material(context, _FIRST, "the first draft")
    _add_material(context, _SECOND, "the second draft")
    _add_material(context, _SECRET, "a draft nobody may read")
    _grant(context)
    return context


def _count(context: ApplicationContext, table: str) -> int:
    """How many rows a table holds."""
    return int(context.store.session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one())


# --------------------------------------------------------------------------- #
# the requests
# --------------------------------------------------------------------------- #


def _project(project_id: str = "proj-1", *, consent_ref: str | None = "grant-1") -> ProjectRequest:
    return ProjectRequest(
        project_id=project_id,
        workspace_id="workspace-1",
        subject_pseudonym="subject-42",
        consent_ref=consent_ref,
    )


def _version(version_id: str, project_id: str, source_id: str) -> VersionRequest:
    return VersionRequest(
        version_id=version_id,
        project_id=project_id,
        source_id=source_id,
        version_label_raw=f"{version_id}-final.docx",
    )


def _edge(edge_id: str = "edge-1", project_id: str = "proj-1") -> EdgeRequest:
    return EdgeRequest(
        edge_id=edge_id,
        project_id=project_id,
        parent_version_id="v1",
        child_version_id="v2",
        source=EdgeSource.EVIDENCE,
        confidence=0.6,
        evidence_spans=("Introduction", "0.12"),
    )


def _a_graph(context: ApplicationContext) -> None:
    """One project, two versions and a proposal between them."""
    record_project(context, _project(), now=_MOMENT)
    record_version(
        context, _version("v1", "proj-1", f"src-{_FIRST.replace('/', '-')}"), now=_MOMENT
    )
    record_version(
        context, _version("v2", "proj-1", f"src-{_SECOND.replace('/', '-')}"), now=_MOMENT
    )


def _refused(call: Callable[[], object], reason: ApplicationRefusal) -> ApplicationRefusedError:
    """Run *call* and return the refusal it made."""
    with pytest.raises(ApplicationRefusedError) as caught:
        call()
    assert caught.value.reason is reason, caught.value.detail
    return caught.value


# --------------------------------------------------------------------------- #
# storing, and reading back
# --------------------------------------------------------------------------- #


def test_a_project_is_stored_and_read_back_as_the_model(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The read-back is the contract, and it says what the caller wrote."""
    context = _context(env, workspace_root)

    stored = record_project(context, _project(), now=_MOMENT)
    read = read_project(context, "proj-1")

    assert isinstance(stored.project, PaperProject)
    assert isinstance(read, PaperProject)
    assert read == stored.project
    assert read.project_id == "proj-1"
    assert read.subject_pseudonym == "subject-42"
    assert read.consent_ref == "grant-1"
    assert _count(context, "paper_projects") == 1


def test_a_version_is_stored_and_read_back_as_the_model(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The version comes back as the contract, carrying the file's own bytes.

    **The hash is the file's**, read from the ledger's row for the file the
    caller named — so a version cannot claim to be a file it is not, and the
    round trip is exact.
    """
    context = _context(env, workspace_root)
    record_project(context, _project(), now=_MOMENT)
    source_id = f"src-{_FIRST.replace('/', '-')}"

    stored = record_version(context, _version("v1", "proj-1", source_id), now=_MOMENT)
    read = read_version(context, "v1", now=_MOMENT)

    assert isinstance(stored.version, PaperVersion)
    assert isinstance(read, PaperVersion)
    assert read == stored.version
    assert read.version_id == "v1"
    assert read.source_content_sha256 == hashlib.sha256(b"the first draft").hexdigest()
    # **The defaults say what they say.** An unresolved version is listed, and
    # a stage the system inferred nothing about is ``unknown``.
    assert read.status is VersionStatus.UNRESOLVED
    assert read.stage_candidate is StageCandidate.UNKNOWN


def test_a_version_keeps_its_bytes_when_the_file_is_re_ingested(
    env: StoreEnv, workspace_root: Path
) -> None:
    """**The version's identity does not move.**

    A file's bytes move: re-ingesting it after an edit changes what the
    ledger holds under that id. A version that took its identity from the
    file would move with it — and the rule that two files with the same
    bytes are one version cannot be held by an identity that moves.

    **What breaks it:** a reader that takes the hash from the file rather
    than from the row. The version would silently become a different set of
    bytes, under the same id, in the same archive.
    """
    context = _context(env, workspace_root)
    record_project(context, _project(), now=_MOMENT)
    source_id = f"src-{_FIRST.replace('/', '-')}"
    recorded = record_version(context, _version("v1", "proj-1", source_id), now=_MOMENT)

    # The file is edited and re-ingested under the same id.
    put_source(
        context.store.session,
        Source(
            source_id=source_id,
            kind=SourceKind.MARKDOWN,
            display_name="draft-1.md",
            relative_path=_FIRST,
            content_sha256=hashlib.sha256(b"an edited first draft").hexdigest(),
            size_bytes=len(b"an edited first draft"),
            readability=SourceReadability.READABLE,
            ingested_at=_MOMENT,
        ),
    )
    context.store.session.commit()

    read = read_version(context, "v1", now=_MOMENT)

    assert read.source_content_sha256 == recorded.version.source_content_sha256
    assert read.source_content_sha256 == hashlib.sha256(b"the first draft").hexdigest()


def test_a_stored_edge_round_trips_through_the_models_own_checks(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The edge comes back as the contract — and as a proposal.

    **A proposal with no acceptor is storable**, because it is the normal
    state of an edge the system inferred and nobody has confirmed.
    """
    context = _context(env, workspace_root)
    _a_graph(context)

    stored = record_edge(context, _edge(), now=_MOMENT)
    read = read_edge(context, "edge-1", now=_MOMENT)

    assert isinstance(stored.edge, VersionEdge)
    assert isinstance(read, VersionEdge)
    assert read == stored.edge
    assert read.source is EdgeSource.EVIDENCE
    assert read.confidence == pytest.approx(0.6)
    assert read.evidence_spans == ("Introduction", "0.12")
    assert read.is_proposal is True
    assert read.is_accepted is False
    assert _count(context, "version_edges") == 1


def test_the_versions_and_edges_of_a_project_are_listed(
    env: StoreEnv, workspace_root: Path
) -> None:
    """The listing is the project's own, in the project's own order."""
    context = _context(env, workspace_root)
    _a_graph(context)
    record_edge(context, _edge(), now=_MOMENT)

    versions = list_versions(context, "proj-1", now=_MOMENT)
    edges = list_edges(context, "proj-1", now=_MOMENT)

    assert [version.version_id for version in versions] == ["v1", "v2"]
    assert [edge.edge_id for edge in edges] == ["edge-1"]


# --------------------------------------------------------------------------- #
# the refusals the models make
# --------------------------------------------------------------------------- #


def test_a_self_parented_edge_is_refused(env: StoreEnv, workspace_root: Path) -> None:
    """A version cannot be its own parent.

    **What breaks it:** a store that writes the row and lets the database's
    own constraint decide. The refusal is named, and nothing is written.
    """
    context = _context(env, workspace_root)
    _a_graph(context)

    refused = _refused(
        lambda: record_edge(
            context,
            EdgeRequest(
                edge_id="edge-self",
                project_id="proj-1",
                parent_version_id="v1",
                child_version_id="v1",
                source=EdgeSource.EVIDENCE,
                confidence=0.9,
            ),
            now=_MOMENT,
        ),
        ApplicationRefusal.PAPER_CONTRACT_REFUSED,
    )

    assert "its own parent" in str(refused)
    assert _count(context, "version_edges") == 0


def test_a_human_edge_with_no_acceptor_is_refused(env: StoreEnv, workspace_root: Path) -> None:
    """A decision with nobody behind it is refused.

    **What breaks it:** accepting ``source='human'`` on its own. The edge
    would settle a relationship and attribute it to nobody, which is the
    forgery the three-fact split exists to prevent.
    """
    context = _context(env, workspace_root)
    _a_graph(context)

    refused = _refused(
        lambda: record_edge(
            context,
            EdgeRequest(
                edge_id="edge-human",
                project_id="proj-1",
                parent_version_id="v1",
                child_version_id="v2",
                source=EdgeSource.HUMAN,
                confidence=0.9,
            ),
            now=_MOMENT,
        ),
        ApplicationRefusal.PAPER_CONTRACT_REFUSED,
    )

    assert "nobody behind it" in str(refused)
    assert _count(context, "version_edges") == 0


def test_an_acceptance_with_no_moment_is_refused(env: StoreEnv, workspace_root: Path) -> None:
    """An acceptance nobody can place in time is not a decision anybody made.

    **What breaks it:** letting ``accepted_by`` and ``accepted_at`` be set
    separately. The pairing is the contract's rule, and the refusal is where
    the mistake is made rather than where the constraint is noticed.
    """
    context = _context(env, workspace_root)
    _a_graph(context)

    refused = _refused(
        lambda: record_edge(
            context,
            EdgeRequest(
                edge_id="edge-half",
                project_id="proj-1",
                parent_version_id="v1",
                child_version_id="v2",
                source=EdgeSource.HUMAN,
                confidence=0.9,
                accepted_by="Prof. Lin",
            ),
            now=_MOMENT,
        ),
        ApplicationRefusal.PAPER_CONTRACT_REFUSED,
    )

    assert "both set or both omitted" in str(refused)
    assert _count(context, "version_edges") == 0


def test_an_edge_across_two_projects_is_refused(env: StoreEnv, workspace_root: Path) -> None:
    """An edge may not join two manuscripts.

    **This is the check a CHECK constraint cannot make**, because it is a
    fact about three rows: the edge's project and the projects of the two
    versions it names. An edge that crossed projects would be a claim about a
    lineage that does not exist.
    """
    context = _context(env, workspace_root)
    _a_graph(context)
    _grant(context, grant_id="grant-2", subject_ref="proj-2", scope="proj-2/**")
    record_project(context, _project("proj-2", consent_ref="grant-2"), now=_MOMENT)
    record_version(
        context,
        _version("v-other", "proj-2", f"src-{_SECOND.replace('/', '-')}"),
        now=_MOMENT,
    )

    refused = _refused(
        lambda: record_edge(
            context,
            EdgeRequest(
                edge_id="edge-cross",
                project_id="proj-1",
                parent_version_id="v1",
                child_version_id="v-other",
                source=EdgeSource.EVIDENCE,
                confidence=0.9,
            ),
            now=_MOMENT,
        ),
        ApplicationRefusal.PAPER_CROSS_PROJECT,
    )

    assert "across projects" in str(refused)
    assert _count(context, "version_edges") == 0


def test_an_edge_naming_a_version_nobody_holds_is_refused(
    env: StoreEnv, workspace_root: Path
) -> None:
    """An edge may not point at a version nobody holds."""
    context = _context(env, workspace_root)
    _a_graph(context)

    _refused(
        lambda: record_edge(
            context,
            EdgeRequest(
                edge_id="edge-nowhere",
                project_id="proj-1",
                parent_version_id="v1",
                child_version_id="v-absent",
                source=EdgeSource.EVIDENCE,
                confidence=0.9,
            ),
            now=_MOMENT,
        ),
        ApplicationRefusal.PAPER_VERSION_NOT_FOUND,
    )

    assert _count(context, "version_edges") == 0


def test_an_edge_naming_a_replacement_nobody_holds_is_refused(
    env: StoreEnv, workspace_root: Path
) -> None:
    """A pointer at an edge that is not there is a reference to nothing.

    **What breaks it:** accepting the pointer because the *contract* has no
    rule about it. The correction path writes the replacement first and then
    points the proposal at it, so a pointer the store holds always names an
    edge the store also holds.
    """
    context = _context(env, workspace_root)
    _a_graph(context)

    refused = _refused(
        lambda: record_edge(
            context,
            EdgeRequest(
                edge_id="edge-dangling",
                project_id="proj-1",
                parent_version_id="v1",
                child_version_id="v2",
                source=EdgeSource.EVIDENCE,
                confidence=0.6,
                superseded_by="edge-absent",
            ),
            now=_MOMENT,
        ),
        ApplicationRefusal.PAPER_EDGE_NOT_FOUND,
    )

    assert "reference to nothing" in str(refused)
    assert _count(context, "version_edges") == 0


# --------------------------------------------------------------------------- #
# the id is minted once
# --------------------------------------------------------------------------- #


def test_a_second_write_with_the_same_id_is_refused(env: StoreEnv, workspace_root: Path) -> None:
    """An id is minted once, and the second write is refused by name.

    **What breaks it:** an upsert. A second project, a second version of one
    draft and a second claim about the same pair of versions would each be a
    second row wearing one name, and a reader could not tell which of the two
    the archive is talking about.
    """
    context = _context(env, workspace_root)
    record_project(context, _project(), now=_MOMENT)

    _refused(
        lambda: record_project(context, _project(), now=_MOMENT),
        ApplicationRefusal.PAPER_ALREADY_RECORDED,
    )
    assert _count(context, "paper_projects") == 1

    source_id = f"src-{_FIRST.replace('/', '-')}"
    record_version(context, _version("v1", "proj-1", source_id), now=_MOMENT)
    _refused(
        lambda: record_version(context, _version("v1", "proj-1", source_id), now=_MOMENT),
        ApplicationRefusal.PAPER_ALREADY_RECORDED,
    )
    assert _count(context, "paper_versions") == 1

    record_version(
        context, _version("v2", "proj-1", f"src-{_SECOND.replace('/', '-')}"), now=_MOMENT
    )
    record_edge(context, _edge(), now=_MOMENT)
    _refused(
        lambda: record_edge(context, _edge(), now=_MOMENT),
        ApplicationRefusal.PAPER_ALREADY_RECORDED,
    )
    assert _count(context, "version_edges") == 1


# --------------------------------------------------------------------------- #
# the three outcomes
# --------------------------------------------------------------------------- #


def test_an_acceptance_settles_the_stored_edge(env: StoreEnv, workspace_root: Path) -> None:
    """The same edge gains an acceptor and a moment, and keeps its confidence.

    **What breaks it:** an acceptance that changed the confidence. The person
    accepted the relationship; how strong the evidence was is still a fact
    about the evidence.
    """
    context = _context(env, workspace_root)
    _a_graph(context)
    record_edge(context, _edge(), now=_MOMENT)

    decision = record_confirmation(
        context,
        ConfirmationRequest(
            edge_id="edge-1",
            outcome=ConfirmationOutcome.ACCEPTED,
            decided_by="Prof. Lin",
            decided_at=_MOMENT,
        ),
        now=_MOMENT,
    )

    assert decision.confirmation.outcome is ConfirmationOutcome.ACCEPTED
    stored = read_edge(context, "edge-1", now=_MOMENT)
    assert stored.is_accepted is True
    assert stored.accepted_by == "Prof. Lin"
    assert stored.accepted_at == _MOMENT
    assert stored.source is EdgeSource.HUMAN
    assert stored.confidence == pytest.approx(0.6)
    assert stored.edge_id == "edge-1"
    assert _count(context, "version_edges") == 1


def test_a_correction_writes_a_second_edge_and_leaves_the_first_readable(
    env: StoreEnv, workspace_root: Path
) -> None:
    """**The rule this file exists for.**

    The proposal the system made is evidence about what the system got wrong,
    so the correction is a **second edge** and the first stays readable with
    its own parent, its own confidence and no acceptor.

    **What breaks it:** writing the corrected parent over the proposal, which
    would destroy the record of the error.
    """
    context = _context(env, workspace_root)
    _a_graph(context)
    record_version(
        context,
        _version("v0", "proj-1", f"src-{_SECRET.replace('/', '-')}"),
        now=_MOMENT,
    )
    record_edge(context, _edge(), now=_MOMENT)

    decision = record_confirmation(
        context,
        ConfirmationRequest(
            edge_id="edge-1",
            outcome=ConfirmationOutcome.CORRECTED,
            decided_by="Prof. Lin",
            decided_at=_MOMENT,
            corrected_parent_version_id="v0",
        ),
        now=_MOMENT,
    )

    corrected = decision.confirmation.edge
    assert corrected is not None
    assert corrected.edge_id != "edge-1"
    assert corrected.parent_version_id == "v0"
    assert corrected.edge_version == 2
    assert corrected.accepted_by == "Prof. Lin"

    # **The proposal is still there**, with its own parent and its own
    # confidence, and it is still a proposal.
    original = read_edge(context, "edge-1", now=_MOMENT)
    assert original.parent_version_id == "v1"
    assert original.child_version_id == "v2"
    assert original.source is EdgeSource.EVIDENCE
    assert original.confidence == pytest.approx(0.6)
    assert original.accepted_by is None
    assert original.is_proposal is True
    assert original.superseded_by == corrected.edge_id

    # And the correction is a row of its own.
    assert read_edge(context, corrected.edge_id, now=_MOMENT) == corrected
    assert _count(context, "version_edges") == 2


def test_a_rejection_writes_no_edge_and_leaves_the_proposal(
    env: StoreEnv, workspace_root: Path
) -> None:
    """There is no relationship here, so no edge is written.

    **And the record of the refusal is written.** It is the one outcome that
    leaves no mark on the graph, so it gets a row of its own: who looked,
    when, why, and about which proposal.
    """
    context = _context(env, workspace_root)
    _a_graph(context)
    record_edge(context, _edge(), now=_MOMENT)

    decision = record_confirmation(
        context,
        ConfirmationRequest(
            edge_id="edge-1",
            outcome=ConfirmationOutcome.REJECTED,
            decided_by="Prof. Lin",
            decided_at=_MOMENT,
            reason="these are two different papers that share a template.",
        ),
        now=_MOMENT,
    )

    assert decision.confirmation.outcome is ConfirmationOutcome.REJECTED
    assert decision.confirmation.edge is None
    assert decision.confirmation.corrects is not None
    assert decision.confirmation.corrects.edge_id == "edge-1"
    assert decision.confirmation.reason

    stored = read_edge(context, "edge-1", now=_MOMENT)
    assert stored.accepted_by is None
    assert stored.superseded_by is None
    assert _count(context, "version_edges") == 1


def test_a_rejection_is_written_down(env: StoreEnv, workspace_root: Path) -> None:
    """**A refusal is not an absence of a row.**

    The other two outcomes leave their own mark on the graph — an acceptance
    is the edge with an acceptor, a correction is a second edge — and a
    rejection left nothing, so a proposal that was looked at and turned down
    was indistinguishable from a proposal nobody had looked at. **The next
    run would propose it again, having learned nothing from the refusal.**

    **What breaks it:** a store that treats the refusal as nothing to write.
    The row is the fact.
    """
    context = _context(env, workspace_root)
    _a_graph(context)
    record_edge(context, _edge(), now=_MOMENT)

    record_confirmation(
        context,
        ConfirmationRequest(
            edge_id="edge-1",
            outcome=ConfirmationOutcome.REJECTED,
            decided_by="Prof. Lin",
            decided_at=_MOMENT,
            reason="these are two different papers that share a template.",
        ),
        now=_MOMENT,
    )

    assert _count(context, "version_edge_rejections") == 1
    rejections = list_rejections(context, "edge-1", now=_MOMENT)
    assert len(rejections) == 1
    rejection = rejections[0]
    assert rejection.edge_id == "edge-1"
    assert rejection.project_id == "proj-1"
    assert rejection.decided_by == "Prof. Lin"
    assert rejection.decided_at == _MOMENT
    assert rejection.reason == "these are two different papers that share a template."


def test_a_rejection_leaves_the_proposal_readable(env: StoreEnv, workspace_root: Path) -> None:
    """The refusal is a fact about the review, not a deletion of the proposal.

    **What breaks it:** a store that removes the proposal when it is
    refused. The archive then cannot show what was proposed, and the next
    run proposes it again with nothing to say it was wrong.
    """
    context = _context(env, workspace_root)
    _a_graph(context)
    record_edge(context, _edge(), now=_MOMENT)
    record_confirmation(
        context,
        ConfirmationRequest(
            edge_id="edge-1",
            outcome=ConfirmationOutcome.REJECTED,
            decided_by="Prof. Lin",
            decided_at=_MOMENT,
        ),
        now=_MOMENT,
    )

    stored = read_edge(context, "edge-1", now=_MOMENT)

    assert stored.parent_version_id == "v1"
    assert stored.child_version_id == "v2"
    assert stored.accepted_by is None
    assert stored.is_proposal is True
    assert _count(context, "version_edges") == 1


def test_a_decision_of_nobody_is_refused(env: StoreEnv, workspace_root: Path) -> None:
    """A decision is a person's, and it must name them."""
    context = _context(env, workspace_root)
    _a_graph(context)
    record_edge(context, _edge(), now=_MOMENT)

    refused = _refused(
        lambda: record_confirmation(
            context,
            ConfirmationRequest(
                edge_id="edge-1",
                outcome=ConfirmationOutcome.ACCEPTED,
                decided_by="   ",
                decided_at=_MOMENT,
            ),
            now=_MOMENT,
        ),
        ApplicationRefusal.PAPER_CONTRACT_REFUSED,
    )

    assert "must name them" in str(refused)
    assert _count(context, "version_edges") == 1


# --------------------------------------------------------------------------- #
# the round trip asks the contract
# --------------------------------------------------------------------------- #


def test_a_row_the_contract_refuses_is_not_readable_as_a_valid_edge(
    env: StoreEnv, workspace_root: Path
) -> None:
    """**A row the schema holds and the contract refuses is not a valid edge.**

    The schema's own constraint says an acceptance names *who* accepted it,
    and it says nothing about the source: a row claiming an acceptance on an
    ``evidence`` edge satisfies every CHECK and is still a proposal wearing a
    person's name. **Only the contract refuses it**, so the round trip has to
    ask the contract — and a row like that must not come back as a valid
    edge.

    **What breaks it:** a reader that rebuilds the model without asking it.
    """
    context = _context(env, workspace_root)
    _a_graph(context)
    context.store.session.execute(
        text(
            "INSERT INTO version_edges (edge_id, project_id, parent_version_id, "
            "child_version_id, source, confidence, evidence_spans, accepted_by, "
            "accepted_at, edge_version, superseded_by, created_at) VALUES "
            "('edge-forged', 'proj-1', 'v1', 'v2', 'evidence', 0.9, '[\"Introduction\"]', "
            "'Prof. Lin', '2026-01-01T00:00:00+00:00', 1, NULL, "
            "'2026-01-01T00:00:00+00:00')"
        )
    )
    context.store.session.commit()

    refused = _refused(
        lambda: read_edge(context, "edge-forged", now=_MOMENT),
        ApplicationRefusal.PAPER_CONTRACT_REFUSED,
    )

    assert "wears a person's name" in str(refused)


# --------------------------------------------------------------------------- #
# the gate
# --------------------------------------------------------------------------- #


def test_a_project_naming_a_grant_that_does_not_exist_is_refused(
    env: StoreEnv, workspace_root: Path
) -> None:
    """A reference to a grant that is not there resolves to nothing.

    **What breaks it:** a store that records the reference and asks about it
    later — or never. The project would carry a consent that names nothing,
    and the material operations would refuse it for a reason nobody could
    act on.
    """
    context = _context(env, workspace_root)

    refused = _refused(
        lambda: record_project(
            context,
            _project(consent_ref="grant-nobody-minted"),
            now=_MOMENT,
        ),
        ApplicationRefusal.CONSENT_NO_GRANT,
    )

    assert "grant" in str(refused)
    assert _count(context, "paper_projects") == 0


def test_a_project_with_no_grant_cannot_record_its_material(
    env: StoreEnv, workspace_root: Path
) -> None:
    """A project with no grant is readable as a project and unreadable as material.

    **That is the contract's own distinction**, and the refusal is where it
    is enforced: the project row is written, and the material it holds is
    refused because no grant covers it.
    """
    context = _context(env, workspace_root)
    record_project(context, _project(consent_ref=None), now=_MOMENT)

    refused = _refused(
        lambda: record_version(
            context,
            _version("v1", "proj-1", f"src-{_FIRST.replace('/', '-')}"),
            now=_MOMENT,
        ),
        ApplicationRefusal.CONSENT_NO_GRANT,
    )

    assert "names no grant" in str(refused)
    assert "the remedy is a grant" in str(refused)
    assert _count(context, "paper_versions") == 0


def test_a_withdrawn_grant_refuses_the_material(env: StoreEnv, workspace_root: Path) -> None:
    """A grant that was taken back is not the same as one that was never made.

    **The two are told apart**, and the reason names which one it is: the
    first is a question about a person and the remedy is a new grant.
    """
    context = _context(env, workspace_root)
    _a_graph(context)
    context.store.session.execute(
        text(
            "UPDATE access_grants SET state = 'withdrawn', "
            "withdrawn_at = '2026-02-01T00:00:00+00:00', withdrawn_by = 'Prof. Lin' "
            "WHERE grant_id = 'grant-1'"
        )
    )
    context.store.session.commit()

    refused = _refused(
        lambda: record_version(
            context,
            _version("v3", "proj-1", f"src-{_SECOND.replace('/', '-')}"),
            now=_MOMENT,
        ),
        ApplicationRefusal.CONSENT_GRANT_WITHDRAWN,
    )

    assert "withdrawn" in str(refused)
    assert _count(context, "paper_versions") == 2


def test_a_denied_material_is_not_recorded(env: StoreEnv, workspace_root: Path) -> None:
    """The policy is asked about the material, and a denial writes nothing.

    **What breaks it:** a writer that records the version first and asks
    afterwards. A deny-everything policy would still have written the row.
    """
    context = _context(env, workspace_root)
    record_project(context, _project(), now=_MOMENT)
    deny = PermissionPolicy.from_rules([Rule(effect=Permission.DENY, pattern="**")])
    denied = ApplicationContext(
        workspace=context.workspace,
        store=context.store,
        policy=deny,
        ledger=context.ledger,
    )

    _refused(
        lambda: record_version(
            denied,
            _version("v1", "proj-1", f"src-{_FIRST.replace('/', '-')}"),
            now=_MOMENT,
        ),
        ApplicationRefusal.PERMISSION_DENIED,
    )

    assert _count(context, "paper_versions") == 0


def test_a_correction_into_denied_material_is_refused(env: StoreEnv, workspace_root: Path) -> None:
    """A relationship the policy denies is not recorded by the back door.

    **A correction names a version of its own**, and that version's material
    is asked about as well as the proposal's. Without that, a version nobody
    may read could be brought into the graph by correcting an edge into it —
    while the same version could not be recorded as an edge's parent in the
    first place.
    """
    context = _context(env, workspace_root)
    _a_graph(context)
    record_version(
        context,
        _version("v-secret", "proj-1", f"src-{_SECRET.replace('/', '-')}"),
        now=_MOMENT,
    )
    record_edge(context, _edge(), now=_MOMENT)
    deny = PermissionPolicy.from_rules(
        [
            Rule(effect=Permission.DENY, pattern="secret.md"),
            Rule(effect=Permission.ALLOW, pattern="**"),
        ]
    )
    denied = ApplicationContext(
        workspace=context.workspace,
        store=context.store,
        policy=deny,
        ledger=context.ledger,
    )

    _refused(
        lambda: record_confirmation(
            denied,
            ConfirmationRequest(
                edge_id="edge-1",
                outcome=ConfirmationOutcome.CORRECTED,
                decided_by="Prof. Lin",
                decided_at=_MOMENT,
                corrected_parent_version_id="v-secret",
            ),
            now=_MOMENT,
        ),
        ApplicationRefusal.PERMISSION_DENIED,
    )

    assert _count(context, "version_edges") == 1


def test_a_denied_version_is_dropped_from_the_listing(env: StoreEnv, workspace_root: Path) -> None:
    """A listing drops the denied entries; naming one is refused.

    **A refused listing would disclose that the entry is there**, and would
    deny work the operator wanted allowed. The two are different answers on
    purpose.
    """
    context = _context(env, workspace_root)
    _a_graph(context)
    record_version(
        context,
        _version("v-secret", "proj-1", f"src-{_SECRET.replace('/', '-')}"),
        now=_MOMENT,
    )
    # **Deny first, and an allow behind it.** The policy has no allow rule
    # of its own here, so without one every request would fall through to the
    # default deny and the listing would be empty rather than short.
    deny = PermissionPolicy.from_rules(
        [
            Rule(effect=Permission.DENY, pattern="secret.md"),
            Rule(effect=Permission.ALLOW, pattern="**"),
        ]
    )
    denied = ApplicationContext(
        workspace=context.workspace,
        store=context.store,
        policy=deny,
        ledger=context.ledger,
    )

    listed = list_versions(denied, "proj-1")

    assert [version.version_id for version in listed] == ["v1", "v2"]
    _refused(
        lambda: read_version(denied, "v-secret"),
        ApplicationRefusal.PERMISSION_DENIED,
    )


# --------------------------------------------------------------------------- #
# the refusal vocabulary
# --------------------------------------------------------------------------- #


def test_every_version_graph_refusal_has_a_layer_name() -> None:
    """The version graph's vocabulary and the layer's are closed.

    **Three checks, and the third catches the drift.** No reason is left
    unnamed; the table has no row the vocabulary does not have; and the
    layer's own ``PAPER_`` names are **exactly** the ones the table reaches,
    so a name added to the layer with nothing mapping to it is caught here.
    """
    unmapped = {reason for reason in PaperRefusal if reason not in PAPER_REFUSALS}
    assert not unmapped, (
        f"the version graph can refuse with {unmapped}, which the layer cannot name"
    )
    assert len(PAPER_REFUSALS) == len(set(PaperRefusal))
    invented = {
        layer_reason
        for layer_reason in PAPER_REFUSALS.values()
        if layer_reason not in set(ApplicationRefusal)
    }
    assert not invented, f"the mapping names reasons the layer does not have: {invented}"

    named = {reason for reason in ApplicationRefusal if reason.name.startswith("PAPER_")}
    assert named == set(PAPER_REFUSALS.values()), (
        "the layer's paper names and the reasons that reach them differ: "
        f"{sorted(reason.value for reason in named ^ set(PAPER_REFUSALS.values()))}"
    )


def test_the_names_line_up_with_the_reasons_they_name() -> None:
    """A reason and its name say the same thing.

    **A pair is right when the name is the reason's own word.** The version
    graph's ``CONTRACT_REFUSED`` is the layer's ``PAPER_CONTRACT_REFUSED``,
    and the module the reason came from is part of the name — so the ledger's
    own ``SOURCE_NOT_FOUND`` and the graph's are two different refusals and
    not one wearing two names.
    """
    for reason, name in PAPER_REFUSALS.items():
        assert name.value == f"paper_{reason.value}", (
            f"{reason} is named {name.value!r} by the layer"
        )
    assert ApplicationRefusal.SOURCE_NOT_FOUND not in set(PAPER_REFUSALS.values())


def test_the_lookup_is_a_lookup_and_not_a_default() -> None:
    """The seam asks the table; it does not fall back."""
    assert (
        paper_refusal_name(PaperRefusal.CONTRACT_REFUSED)
        is ApplicationRefusal.PAPER_CONTRACT_REFUSED
    )
    assert paper_refusal_name(PaperRefusal.CROSS_PROJECT) is ApplicationRefusal.PAPER_CROSS_PROJECT


# --------------------------------------------------------------------------- #
# ADR-0014's revision events: the seam between the reader and the store
# --------------------------------------------------------------------------- #

#: The paragraph the marked-up manuscript is built on. **The deletion and
#: the insertion are far apart in it**, so the two addresses cannot be
#: confused with one another.
_MARKED_PARAGRAPH = "The method estimates the parameter roughly."


@pytest.fixture
def marked_up(env: StoreEnv, workspace_root: Path) -> ChainEnv:
    """A marked-up manuscript: two tracked changes and not one comment.

    **This is the shape of a reviewer's hand with no explanation in it**,
    which is the shape of the corpus that motivated this table: a
    manuscript whose changes are all in the text and whose margins are
    empty.
    """
    return build_chain(
        env.store(),
        workspace_root,
        paragraphs=(_MARKED_PARAGRAPH,),
        revisions=(
            Revision(
                kind="ins",
                text="carefully",
                author="Prof. Lin",
                date="2026-03-02T09:30:00Z",
                element_id="101",
                paragraph=0,
                after_text="estimates",
            ),
            Revision(
                kind="del",
                text="roughly",
                author="Prof. Lin",
                date="2026-03-02T09:31:00Z",
                element_id="102",
                paragraph=0,
                anchor_text="roughly",
            ),
        ),
    )


@pytest.fixture
def anonymous(env: StoreEnv, workspace_root: Path) -> ChainEnv:
    """A marked-up manuscript whose one change names neither author nor date.

    **The attributes are removed rather than emptied.** Word permits a
    ``w:ins`` with no ``w:author`` and no ``w:date``, and the reader treats
    a missing one and an empty one as different cases.
    """
    return build_chain(
        env.store(),
        workspace_root,
        paragraphs=(_MARKED_PARAGRAPH,),
        revisions=(
            Revision(
                kind="ins",
                text="carefully",
                author=None,
                date=None,
                element_id="201",
                paragraph=0,
                after_text="estimates",
            ),
        ),
    )


@pytest.fixture
def marked_up_with_a_comment(env: StoreEnv, workspace_root: Path) -> ChainEnv:
    """A marked-up manuscript that carries **both**: changes and a comment.

    **This is the shape of the richest sample in the corpus** — one person
    who both rewrote the text and wrote a remark about it — and **the two
    are two things**. A comment says what a person asked for; a change says
    what was altered. They may correspond and they may not, and the chain
    asserts no correspondence that nobody recorded.
    """
    return build_chain(
        env.store(),
        workspace_root,
        paragraphs=(_MARKED_PARAGRAPH,),
        revisions=(
            Revision(
                kind="ins",
                text="carefully",
                author="Prof. Lin",
                date="2026-03-02T09:30:00Z",
                element_id="101",
                paragraph=0,
                after_text="estimates",
            ),
            Revision(
                kind="del",
                text="roughly",
                author="Prof. Lin",
                date="2026-03-02T09:31:00Z",
                element_id="102",
                paragraph=0,
                anchor_text="roughly",
            ),
        ),
        comments=(a_comment("201", text="Say what the parameter is."),),
    )


def _recorded(context: ApplicationContext, env: ChainEnv) -> tuple[RevisionRecord, ...]:
    """The revision events of the first version, recorded."""
    return record_revision_events(
        context,
        project_id=env.project_id,
        version_id=env.version_id,
        now=CHAIN_MOMENT,
    )


def _raw_insert(session: Session, **overrides: object) -> None:
    """Write a revision event row directly, so the schema is what is under test."""
    values: dict[str, object] = {
        "revision_event_id": "rv-raw",
        "version_id": "ver-1",
        "kind": "ins",
        "text": "carefully",
        "text_sha256": "a" * 64,
        "part": "word/document.xml",
        "element_path": "/document[1]/body[1]/p[1]/ins[1]",
        "view": "accepted",
        "char_start": 0,
        "char_end": 8,
        "paragraph": 0,
        "baseline_start": 0,
        "baseline_end": 0,
        "author": "Prof. Lin",
        "author_unknown_reason": None,
        "occurred_at": "2026-03-02T09:30:00+00:00",
        "date_unknown_reason": None,
        "element_id": "101",
        "nested": 0,
        "parser_version": "parser-1",
        "grade": "observed",
        "created_at": "2026-04-01T09:00:00+00:00",
    }
    values.update(overrides)
    columns = ", ".join(values)
    placeholders = ", ".join(f":{key}" for key in values)
    session.execute(
        text(f"INSERT INTO revision_events ({columns}) VALUES ({placeholders})"),
        values,
    )
    session.commit()


def test_a_revision_event_carries_the_text_and_the_place_of_the_change(
    marked_up: ChainEnv,
) -> None:
    """What the reviewer changed, and where — the two together.

    **The words and the address travel together, and they agree.** A row
    that carried a text without an address would be a sentence nobody could
    check, and a row that carried an address without the words would be a
    place nobody could read. So the test does not only ask the row what it
    says: it re-reads the manuscript and asks the *file* what is at the
    address the row names.

    **What breaks it:** a writer that stores the address and drops the
    text, or stores the text and re-points the address.
    """
    recorded = _recorded(marked_up.context, marked_up)

    assert len(recorded) == 2, "the manuscript holds two tracked changes"
    inserted = next(record for record in recorded if record.kind == "ins")
    deleted = next(record for record in recorded if record.kind == "del")

    assert inserted.text == "carefully"
    assert inserted.part == "word/document.xml"
    assert inserted.element_path is not None
    assert inserted.element_path.endswith("/ins[1]")
    assert inserted.view == "accepted"
    assert inserted.paragraph == 0
    assert inserted.author == "Prof. Lin"
    assert inserted.occurred_at is not None
    assert inserted.grade == "observed"

    assert deleted.text == "roughly"
    assert deleted.view == "rejected"
    assert deleted.author == "Prof. Lin"

    # **An insertion is a point in the baseline** — it contributes nothing
    # to the text as it read before — and **a deletion covers a range**.
    assert inserted.baseline_start == inserted.baseline_end
    assert deleted.baseline_start is not None
    assert deleted.baseline_end is not None
    assert deleted.baseline_end > deleted.baseline_start

    # **And the file agrees with the row.** The text at the address the
    # row names is the text the row carries.
    document = read_document(marked_up.manuscript.read_bytes())
    at_the_address = {event.locator.element_path: event.text for event in document.revisions}
    for record in recorded:
        assert record.element_path is not None
        assert at_the_address[record.element_path] == record.text


def test_a_deletion_keeps_its_text_and_is_addressed_in_the_rejected_view(
    marked_up: ChainEnv,
) -> None:
    """The deleted text is not in the accepted view, and that is why the
    view is part of the address.

    **ADR-0014's thesis in one property.** The text an advisor deleted
    lives in ``w:delText`` and a reader that reads ``w:t`` sees an empty
    run — so the text never reaches the document model at all. And it is
    not in the accepted text either, because accepting a revision throws
    the deleted text away. **So a deletion has no characters in the
    accepted view, and a reader that works in one view cannot cite a
    deletion at all.**

    **What breaks it:** a writer that addresses the deletion in the
    accepted view, or one that stores the accepted text as the deletion's
    text.
    """
    recorded = _recorded(marked_up.context, marked_up)
    deleted = next(record for record in recorded if record.kind == "del")

    assert deleted.text == "roughly"
    assert deleted.view == "rejected"

    document = read_document(marked_up.manuscript.read_bytes())
    assert "roughly" in document.rejected_text
    assert "roughly" not in document.accepted_text


def test_a_revision_with_no_author_or_date_is_unknown_and_never_guessed(
    anonymous: ChainEnv,
) -> None:
    """A missing author is unknown, and the absence is named.

    **ADR-0014 D3.** Word permits a ``w:ins`` with no ``w:author`` and no
    ``w:date``, and the design's rule is that the missing value is
    ``UNKNOWN`` and **never a guess**: not from the document's properties,
    not from the file name, not from the style of the change. So the
    record carries no author at all, and carries a reason for carrying no
    author — because "unknown" that nobody can name is an absence.

    **What breaks it:** a writer that fills the author in from the file's
    name or its mtime, or that writes an empty string and calls it
    unknown.
    """
    recorded = _recorded(anonymous.context, anonymous)

    assert len(recorded) == 1
    record = recorded[0]
    assert record.author is None, "an author nobody wrote down is not guessed at"
    assert record.author_unknown_reason is not None
    assert record.author_unknown_reason.strip() != ""
    assert record.occurred_at is None, "a date nobody wrote down is not guessed at"
    assert record.date_unknown_reason is not None
    assert record.date_unknown_reason.strip() != ""


@pytest.mark.parametrize(
    ("overrides", "what"),
    [
        ({"kind": "robot"}, "a kind outside the vocabulary"),
        ({"grade": "probably"}, "a grade outside the vocabulary"),
        ({"view": "middle"}, "a view outside the vocabulary"),
        ({"revision_event_id": ""}, "an id that is not an id"),
        ({"text_sha256": "abc"}, "a hash that is not a hash"),
        (
            # **The address is present and the words are not**, so the
            # only rule this row breaks is the one about the address.
            {"grade": "inferred", "text": ""},
            "an inferred row carrying an address",
        ),
        (
            # **The words are present and the address is not**, so the
            # only rule this row breaks is the one about the words.
            {
                "grade": "inferred",
                "text": "carefully",
                "part": None,
                "element_path": None,
                "view": None,
            },
            "an inferred row carrying words",
        ),
        ({"char_end": None}, "a range with one end"),
        ({"baseline_start": 9, "baseline_end": 2}, "a baseline range that runs backwards"),
        (
            {"author": None, "author_unknown_reason": None},
            "an author that is missing with no reason",
        ),
        (
            {"occurred_at": None, "date_unknown_reason": None},
            "a date that is missing with no reason",
        ),
        ({"paragraph": -1}, "a paragraph that is not a place"),
    ],
)
def test_the_schema_refuses_a_revision_event_that_breaks_its_rule(
    marked_up: ChainEnv, overrides: dict[str, object], what: str
) -> None:
    """Each of the schema's rules refuses, and each refusal has its own case.

    **The rules are written down where the rows are, and the database
    refuses them.** This test writes the row that breaks one rule, with a
    raw ``INSERT`` that bypasses the ORM, and watches the database refuse
    it — because a text comparison cannot catch a migration and a model
    wrong together.

    **What breaks it:** a constraint removed from the table, or a rule
    that the ORM enforces but the schema does not.
    """
    session = marked_up.context.store.session

    with pytest.raises(IntegrityError):
        _raw_insert(session, **{"revision_event_id": "rv-broken", **overrides})
    session.rollback()

    assert _count(marked_up.context, "revision_events") == 0, what


def test_recording_the_same_version_twice_is_the_same_rows(marked_up: ChainEnv) -> None:
    """The ids are derived, so a second reading finds the rows that are there.

    **Identity cannot depend on insertion order.** An event is cited from a
    later run and from a decision record, so its id must be a function of
    what it is and not of when it was written. The id is the version and
    the element's path.

    **What breaks it:** an id that counts rows, or one that includes the
    moment it was written.
    """
    first = _recorded(marked_up.context, marked_up)
    second = _recorded(marked_up.context, marked_up)

    assert [record.revision_event_id for record in first] == [
        record.revision_event_id for record in second
    ]
    assert _count(marked_up.context, "revision_events") == 2


def test_a_revision_whose_text_no_longer_matches_is_refused_as_stale(
    marked_up: ChainEnv,
) -> None:
    """A row whose text no longer matches the file is stale, and it is
    refused rather than re-pointed.

    **ADR-0014's mitigation for a brittle anchor.** The anchor is the path
    **plus** the text hash, and a hash mismatch reports the anchor as
    stale rather than wrong. Re-pointing it would make the record say
    something the file does not say — and a silent re-point is the failure
    this whole table exists to prevent.

    **What breaks it:** a writer that overwrites the row with the newly
    read text.
    """
    recorded = _recorded(marked_up.context, marked_up)
    session = marked_up.context.store.session
    row = session.get(RevisionEventRow, recorded[0].revision_event_id)
    assert row is not None
    row.text_sha256 = "0" * 64
    session.commit()

    with pytest.raises(ApplicationRefusedError) as caught:
        _recorded(marked_up.context, marked_up)
    assert caught.value.reason is ApplicationRefusal.CHAIN_ANCHOR_STALE


def test_a_manuscript_whose_bytes_changed_under_its_name_is_refused(
    marked_up: ChainEnv,
) -> None:
    """The bytes are checked before anything is written.

    **The version names the file *and* the bytes it was recorded with.**
    A manuscript whose bytes changed under the name is not the one the
    coordinates would name, so nothing is recorded against it — not a
    wrong event, and not a silent re-point.

    **What breaks it:** a writer that parses the file without comparing
    its bytes with the version's.
    """
    marked_up.manuscript.write_bytes(b"these are not the bytes the version was made from")

    with pytest.raises(ApplicationRefusedError) as caught:
        _recorded(marked_up.context, marked_up)
    assert caught.value.reason is ApplicationRefusal.CHAIN_MATERIAL_DRIFTED
    assert _count(marked_up.context, "revision_events") == 0


def test_a_revision_event_is_not_recorded_when_the_policy_denies_the_material(
    marked_up: ChainEnv,
) -> None:
    """The policy is asked about the material, and a denial writes nothing.

    **What breaks it:** a writer that records the events first and asks
    afterwards. A deny-everything policy would still have written the
    rows.
    """
    deny = PermissionPolicy.from_rules([Rule(effect=Permission.DENY, pattern="**")])
    denied = ApplicationContext(
        workspace=marked_up.context.workspace,
        store=marked_up.context.store,
        policy=deny,
        ledger=marked_up.context.ledger,
    )

    with pytest.raises(ApplicationRefusedError) as caught:
        _recorded(denied, marked_up)
    assert caught.value.reason is ApplicationRefusal.PERMISSION_DENIED
    assert _count(marked_up.context, "revision_events") == 0


def test_a_revision_event_about_a_version_nobody_holds_is_refused(
    marked_up: ChainEnv,
) -> None:
    """A change in a document nobody holds is a change about nothing.

    **What breaks it:** a writer that records the events against a version
    the store does not hold, which would make the rows name a document
    that cannot be opened.
    """
    with pytest.raises(ApplicationRefusedError) as caught:
        record_revision_events(
            marked_up.context,
            project_id=marked_up.project_id,
            version_id="ver-nobody-holds",
            now=CHAIN_MOMENT,
        )
    assert caught.value.reason is ApplicationRefusal.CHAIN_VERSION_NOT_FOUND
    assert _count(marked_up.context, "revision_events") == 0


def test_a_listing_drops_the_events_of_denied_material(marked_up: ChainEnv) -> None:
    """Denied material is dropped, not refused.

    **ADR-0003 C5's rule for a bulk listing.** A listing that refused
    would disclose that something is there and deny work the operator
    wanted allowed; a listing that returned the events anyway would show
    the reviewer's prose to somebody the policy says may not have it.

    **What breaks it:** a listing that refuses, or one that does not ask.
    """
    _recorded(marked_up.context, marked_up)

    assert len(list_revision_events(marked_up.context)) == 2

    deny = PermissionPolicy.from_rules([Rule(effect=Permission.DENY, pattern="**")])
    denied = ApplicationContext(
        workspace=marked_up.context.workspace,
        store=marked_up.context.store,
        policy=deny,
        ledger=marked_up.context.ledger,
    )
    assert list_revision_events(denied) == ()


def test_the_application_layer_reads_the_revision_events_and_the_activity(
    marked_up: ChainEnv,
) -> None:
    """The mentor line reads the changes, and the shape of the manuscript.

    **The counts are the two the product needs.** A marked-up manuscript
    holds changes in its text and comments in its margins, and **how many
    of each is a fact a reader can see for itself** — 303 changes in 14
    paragraphs and no comment is a shape, and it is a shape the chain can
    report without explaining it away.

    **What breaks it:** a reader that answers with the rows and not with
    the counts, or that counts the two together.
    """
    _recorded(marked_up.context, marked_up)

    events = chain_layer.read_revision_events(marked_up.context, version_ids=[marked_up.version_id])
    assert {event.kind for event in events} == {"ins", "del"}
    assert {event.text for event in events} == {"carefully", "roughly"}

    activity = chain_layer.read_revision_activity(
        marked_up.context, version_ids=[marked_up.version_id]
    )
    assert len(activity) == 1
    assert activity[0].revision_count == 2
    assert activity[0].paragraphs_touched == 1
    assert activity[0].most_events_in_a_paragraph == 2
    assert activity[0].comment_count == 0


def test_a_comment_and_a_change_in_one_manuscript_are_two_facts(
    marked_up_with_a_comment: ChainEnv,
) -> None:
    """The same person's comment and the same person's change are two
    things, and the chain records them side by side.

    **The corpus's richest sample is one person who both rewrote the text
    and wrote a remark about it, and the two are not one thing.** A
    comment says what a person asked for; a change says what was altered.
    They may correspond and they may not, and **the chain asserts no
    correspondence that nobody recorded** — the pairing is a judgement, it
    carries its own decider and its own evidence, and it lives in
    ``response_links``.

    **So this is what the model says about the two cases.** A comment with
    no change answering it is **listed as unaddressed** — not absent from
    the listing. And the changes stand beside it, with nothing joining
    them.

    **What breaks it:** a reader that joins the two, or one that drops the
    comment because a change exists in the same manuscript.
    """
    marked = marked_up_with_a_comment
    feedback = record_feedback(
        marked.context,
        project_id=marked.project_id,
        version_id=marked.version_id,
        now=CHAIN_MOMENT,
    )
    recorded = _recorded(marked.context, marked)

    assert len(feedback) == 1
    assert len(recorded) == 2

    # **The comment is listed as unaddressed** — the reason says nobody
    # answered it, and it is not absent from the listing.
    unaddressed = list_unaddressed(marked.context, project_id=marked.project_id)
    assert [item.feedback.feedback_id for item in unaddressed] == [feedback[0].feedback_id]
    assert unaddressed[0].reason == "no_response"

    # **And the changes stand beside it, with nothing joining them.**
    activity = chain_layer.read_revision_activity(marked.context, version_ids=[marked.version_id])
    assert activity[0].revision_count == 2
    assert activity[0].comment_count == 1


def test_the_schema_cannot_express_why_a_change_was_made() -> None:
    """A change is observed; **why it was changed is not established**.

    **This is ADR-0016 D9 as a structure rather than as a warning.** The
    corpus that motivated this table is a reviewer's rewriting of a
    manuscript with hundreds of changes and not one sentence of
    explanation, and distilling a rule from it would be learning "this
    person's style is like this" — which the design calls a *risk metric*
    rather than a quality metric.

    **So the table cannot express the reason at all.** There is no column
    for one, and there is no link to the table where a person's words
    live: the pairing of a comment with a change is somebody's judgement,
    it carries its own decider and its own evidence, and this table
    asserts none. **What breaks it:** a column or a foreign key added
    here, which would let a change carry a reason it never had.
    """
    columns = set(RevisionEventRow.__table__.columns.keys())
    assert "feedback_id" not in columns, "a change may not name the comment it answers"
    assert "comment_id" not in columns
    assert "reason" not in columns, "a change has no reason of its own"
    assert "why" not in columns
    assert "motive" not in columns
    assert "explanation" not in columns

    targets = {
        foreign_key.target_fullname for foreign_key in RevisionEventRow.__table__.foreign_keys
    }
    assert not any("feedback_events" in target for target in targets), (
        "the revision events may not be joined to the comments by the schema: "
        "the correspondence is a judgement, and a judgement carries its own "
        "decider and its own evidence"
    )
