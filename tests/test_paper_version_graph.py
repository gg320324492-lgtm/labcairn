"""The version graph's schema, and the rows it must refuse.

**What is under test.** LC-P2-08 T00: three tables — `paper_projects`,
`paper_versions`, `version_edges` — and the three refusals the design's
rules imply.

**A schema that is only compared is not checked.** The project's own
lesson from revision 0007 is that *"the parity test passed through it,
because the migration and the ORM were mangled identically — a test
comparing two texts cannot catch both being wrong"*. So every rule below is
witnessed by **writing a row the schema must refuse** and watching the
database refuse it. The parity test says the migration and the ORM agree;
these say that what they agree on is the right thing.

**The three refusals.**

1. **A version is not its own parent.** A contradiction, not a self-loop to
   be tolerated.
2. **An edge that claims an acceptance names who accepted it.** An
   `accepted_by` with no acceptor is a human decision with nobody behind
   it. **The absence of an acceptor is not an error** — that is what a
   proposal looks like — and telling those two apart is the whole point.
3. **A stage or a status outside its vocabulary is refused.** A closed set,
   because a stage that could hold any string carries no information.

**And the two that are *not* refusals**, which matter as much:

- **A proposal with no acceptor is storable.** It is the normal state of an
  edge the system inferred and no person has confirmed, and a schema that
  refused it would make the system unable to record a proposal at all.
- **An unresolved version is storable.** It exists, it is material, and
  hiding it because its parent is unknown would make the archive look
  complete when it is not.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from labcairn.db.migrations import upgrade_to_head
from labcairn.db.repository import TaskStore
from labcairn.db.session import create_db_engine, create_session_factory

pytestmark = pytest.mark.unit

NOW = datetime(2026, 3, 2, 9, 15, tzinfo=UTC)


@pytest.fixture()
def store(tmp_path: Path) -> TaskStore:
    """A migrated store, with one project and two sources to hang things on."""
    database = tmp_path / "versions.db"
    upgrade_to_head(database)
    engine = create_db_engine(database)
    session = create_session_factory(engine)()
    task_store = TaskStore(session)

    session.execute(
        text(
            "INSERT INTO sources (source_id, owner_id, kind, display_name, "
            "relative_path, content_sha256, size_bytes, readability, "
            "identifiers, ingested_at, schema_version) VALUES "
            "('src-1', 'local-user', 'text', 'v1.docx', 'v1.docx', :h, "
            "10, 'readable', '[]', :t, 1)"
        ),
        {"h": "a" * 64, "t": NOW.isoformat()},
    )
    session.execute(
        text(
            "INSERT INTO sources (source_id, owner_id, kind, display_name, "
            "relative_path, content_sha256, size_bytes, readability, "
            "identifiers, ingested_at, schema_version) VALUES "
            "('src-2', 'local-user', 'text', 'v2.docx', 'v2.docx', :h, "
            "10, 'readable', '[]', :t, 1)"
        ),
        {"h": "b" * 64, "t": NOW.isoformat()},
    )
    session.execute(
        text(
            "INSERT INTO paper_projects (project_id, workspace_id, "
            "subject_pseudonym, consent_ref, created_at) VALUES "
            "('proj-1', 'ws-1', 'student-a', 'grant-1', :t)"
        ),
        {"t": NOW.isoformat()},
    )
    session.commit()
    return task_store


def _insert_version(session: Session, version_id: str, source_id: str, **overrides: object) -> None:
    """Insert a version row directly, so the schema is what is under test.

    The application layer is deliberately not involved: **the point is that
    a raw INSERT bypassing the ORM is refused too**, which is the standard
    every closed vocabulary in this project holds itself to.
    """
    values: dict[str, object] = {
        "version_id": version_id,
        "project_id": "proj-1",
        "source_id": source_id,
        "version_label_raw": "draft.docx",
        "stage_candidate": "draft",
        "status": "unresolved",
        "created_at": NOW.isoformat(),
    }
    values.update(overrides)
    columns = ", ".join(values)
    placeholders = ", ".join(f":{key}" for key in values)
    session.execute(
        text(f"INSERT INTO paper_versions ({columns}) VALUES ({placeholders})"),
        values,
    )
    session.commit()


def _insert_edge(session: Session, edge_id: str, **overrides: object) -> None:
    values: dict[str, object] = {
        "edge_id": edge_id,
        "project_id": "proj-1",
        "parent_version_id": "v1",
        "child_version_id": "v2",
        "source": "evidence",
        "confidence": 0.8,
        "evidence_spans": "[]",
        "accepted_by": None,
        "accepted_at": None,
        "edge_version": 1,
        "superseded_by": None,
        "created_at": NOW.isoformat(),
    }
    values.update(overrides)
    columns = ", ".join(values)
    placeholders = ", ".join(f":{key}" for key in values)
    session.execute(
        text(f"INSERT INTO version_edges ({columns}) VALUES ({placeholders})"),
        values,
    )
    session.commit()


# --------------------------------------------------------------------------- #
# the schema refuses
# --------------------------------------------------------------------------- #


def test_a_version_cannot_be_its_own_parent(store: TaskStore) -> None:
    """A self-edge is refused.

    **What breaks it:** dropping the constraint. The edge would then say
    that a version came from itself, which is a contradiction rather than a
    self-loop to be tolerated — and a contradiction in the archive is the
    kind that a reader cannot see and a report would print.
    """
    session = store.session
    _insert_version(session, "v1", "src-1")
    _insert_version(session, "v2", "src-2")

    with pytest.raises(IntegrityError) as refused:
        _insert_edge(session, "edge-self", parent_version_id="v1", child_version_id="v1")
    assert "version_edges_not_self_parent" in str(refused.value)


def test_an_edge_that_claims_an_acceptance_must_name_the_acceptor(store: TaskStore) -> None:
    """An ``accepted_by`` with no acceptor is refused.

    **What breaks it:** allowing an acceptance without an actor. The row
    would say "a person accepted this" and name nobody, and a reader would
    take the acceptance as settled when nothing settled it.

    **And the timestamp is part of the claim.** An acceptor with no time is
    a decision nobody can place, so the constraint covers both or neither.
    """
    session = store.session
    _insert_version(session, "v1", "src-1")
    _insert_version(session, "v2", "src-2")

    with pytest.raises(IntegrityError) as refused:
        _insert_edge(session, "edge-1", accepted_by="Prof. Lin", accepted_at=None)
    assert "version_edges_acceptance_names_an_acceptor" in str(refused.value)

    with pytest.raises(IntegrityError) as refused:
        _insert_edge(session, "edge-2", accepted_by=None, accepted_at=NOW.isoformat())
    assert "version_edges_acceptance_names_an_acceptor" in str(refused.value)


def test_a_stage_outside_the_vocabulary_is_refused(store: TaskStore) -> None:
    """``stage_candidate`` is a closed set.

    **What breaks it:** widening it to free text. A stage that could hold
    anything carries no information, and a typo like ``advised`` would
    sail through and be indistinguishable from ``advisor_reviewed``.
    """
    with pytest.raises(IntegrityError) as refused:
        _insert_version(store.session, "v1", "src-1", stage_candidate="advised")
    assert "paper_versions_stage_vocabulary" in str(refused.value)


def test_a_status_outside_the_vocabulary_is_refused(store: TaskStore) -> None:
    """``status`` is a closed set, and it has exactly two members.

    The two are ``resolved`` and ``unresolved``, and **the second is not a
    failure state** — it is the state a version is in until its place in
    the sequence is established.
    """
    with pytest.raises(IntegrityError) as refused:
        _insert_version(store.session, "v1", "src-1", status="probably")
    assert "paper_versions_status_vocabulary" in str(refused.value)


def test_a_confidence_outside_the_range_is_refused(store: TaskStore) -> None:
    """A confidence above 1.0 is refused.

    **What breaks it:** widening the range. A confidence of 1.5 is a number
    that means nothing, and it would sort above every real score in a
    ranking — so the check is on the number itself, not on how it is read.
    """
    session = store.session
    _insert_version(session, "v1", "src-1")
    _insert_version(session, "v2", "src-2")

    with pytest.raises(IntegrityError) as refused:
        _insert_edge(session, "edge-1", confidence=1.5)
    assert "version_edges_confidence_in_range" in str(refused.value)


def test_an_edge_source_outside_the_vocabulary_is_refused(store: TaskStore) -> None:
    """``source`` is a closed set of three.

    **What breaks it:** adding a fourth source that means something else.
    The three are not interchangeable — ``evidence`` is a proposal the
    system made, ``human`` is a decision somebody made, and ``model`` is a
    proposal a model made — and a fourth would blur exactly the distinction
    the column exists to keep.
    """
    session = store.session
    _insert_version(session, "v1", "src-1")
    _insert_version(session, "v2", "src-2")

    with pytest.raises(IntegrityError) as refused:
        _insert_edge(session, "edge-1", source="heuristic")
    assert "version_edges_source_vocabulary" in str(refused.value)


# --------------------------------------------------------------------------- #
# the schema accepts what it must
# --------------------------------------------------------------------------- #


def test_a_proposal_with_no_acceptor_is_storable(store: TaskStore) -> None:
    """The normal state of an inferred edge is storable.

    **This is the counterpart of the acceptance refusal, and it is the one
    that is easy to get wrong in the other direction.** A schema that
    required an acceptor for every edge would be unable to record a
    proposal at all — and a proposal is exactly what the system produces
    before a person has looked.

    The design's rule is *"禁止仅靠相似度静默确定版本顺序"*: a similarity
    score may not **decide** an order. It may propose one, and the
    proposal is stored with its confidence and its evidence and **no
    acceptor**.
    """
    session = store.session
    _insert_version(session, "v1", "src-1")
    _insert_version(session, "v2", "src-2")

    _insert_edge(session, "edge-1", source="evidence", confidence=0.99)

    row = session.execute(
        text("SELECT source, confidence, accepted_by FROM version_edges WHERE edge_id = 'edge-1'")
    ).one()
    assert row.source == "evidence"
    assert row.confidence == pytest.approx(0.99)
    assert row.accepted_by is None


def test_a_high_confidence_proposal_is_still_unaccepted(store: TaskStore) -> None:
    """Confidence is a number and not a decision.

    **What breaks it:** a rule that treats a confidence above some
    threshold as settled. That is the design's prohibition in another form:
    the score would decide the order, and a score that decides an order is
    the thing this whole ticket is about not doing.
    """
    session = store.session
    _insert_version(session, "v1", "src-1")
    _insert_version(session, "v2", "src-2")

    _insert_edge(session, "edge-1", source="evidence", confidence=1.0)

    row = session.execute(
        text("SELECT accepted_by FROM version_edges WHERE edge_id = 'edge-1'")
    ).one()
    assert row.accepted_by is None


def test_an_unresolved_version_is_storable(store: TaskStore) -> None:
    """A version whose parent is unknown is listed, not hidden.

    **What breaks it:** requiring a resolved status at insert time, which
    would mean a version cannot be recorded until its relationship is
    known — and a relationship cannot be established until the version is
    recorded. **The absence of an edge is not the absence of a version.**
    """
    session = store.session
    _insert_version(session, "v1", "src-1", status="unresolved")

    row = session.execute(
        text("SELECT status, version_label_raw FROM paper_versions WHERE version_id = 'v1'")
    ).one()
    assert row.status == "unresolved"
    # The author's label is kept verbatim. It is **not** evidence of order,
    # and keeping it is what lets a person see what the file was called.
    assert row.version_label_raw == "draft.docx"


def test_a_project_with_no_consent_reference_is_storable(store: TaskStore) -> None:
    """A project with no grant is storable, and it grants nothing.

    **This is the seam between LC-P2-06 and LC-P2-08.** The project's
    ``consent_ref`` is a *reference* — LC-P2-06 resolves it to a grant — and
    its absence means "no grant has been recorded", not "the material may
    be read". A project is **readable as a project and unreadable as
    material**, and those are two different states.
    """
    session = store.session
    session.execute(
        text(
            "INSERT INTO paper_projects (project_id, workspace_id, "
            "subject_pseudonym, consent_ref, created_at) VALUES "
            "('proj-2', 'ws-1', 'student-b', NULL, :t)"
        ),
        {"t": NOW.isoformat()},
    )
    session.commit()
    row = session.execute(
        text("SELECT consent_ref FROM paper_projects WHERE project_id = 'proj-2'")
    ).one()
    assert row.consent_ref is None


def test_two_versions_of_one_source_may_both_exist(store: TaskStore) -> None:
    """The same file may be recorded as two versions.

    **What breaks it:** a uniqueness constraint on ``source_id``. The design
    says two files with the same name and different bytes are two
    versions, and the reverse — the same bytes under two names — is a
    **duplicate** that the system reports rather than resolves. The schema
    must be able to hold the situation, because refusing it would hide a
    duplicate instead of showing one.
    """
    session = store.session
    _insert_version(session, "v1", "src-1")
    _insert_version(session, "v1-copy", "src-1", version_label_raw="copy of draft.docx")

    count: int = session.execute(
        text("SELECT COUNT(*) FROM paper_versions WHERE source_id = 'src-1'")
    ).scalar_one()
    assert count == 2


def test_a_branch_is_representable(store: TaskStore) -> None:
    """Two versions may share one parent.

    **This is the case the schema's shape exists for.** The teacher's
    process contains parallel branches — a student sent two different
    revised drafts and the advisor replied to both — and a column on the
    version could hold only one parent. The edges are rows, so the graph
    branches.
    """
    session = store.session
    _insert_version(session, "v1", "src-1")
    _insert_version(session, "v2a", "src-2")
    _insert_version(session, "v2b", "src-2", version_label_raw="v2b.docx")

    _insert_edge(session, "edge-a", parent_version_id="v1", child_version_id="v2a")
    _insert_edge(session, "edge-b", parent_version_id="v1", child_version_id="v2b")

    children: int = session.execute(
        text("SELECT COUNT(*) FROM version_edges WHERE parent_version_id = 'v1'")
    ).scalar_one()
    assert children == 2
