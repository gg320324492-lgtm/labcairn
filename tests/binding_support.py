"""Shared builders for the comment-to-revision binding's witnesses. Not a test module.

The binding's witnesses all need the same hard part — **a manuscript whose
adviser's comments are readable and whose anchor the seam can rewrite** — and
a fixture assembly that spans four modules (the DOCX corpus, the revision
loop, the version graph and the access-grant table) is four places for it to
be wrong. This is the repository's own convention for shared setup: a support
module the test files import, no ``tests/conftest.py`` growth.

Everything here is deterministic: a fixed moment rather than the wall clock,
a substitute suggester that dispatches on the opinion's text rather than on
anything the clock or a provider produces, and **real files on disk** — the
binding's claim is about real bytes, and a witness that faked the files would
witness the fake.

The three-case sample
---------------------

Execution plan §4's research-quality row names the cases the sample must
carry: a **directly editable** comment (its anchor resolves to text the seam
can rewrite), a case **needing further evidence** (the reviewer flags it), and
an **uncertain location** (the reader places it on a position with no passage).
The builders below write exactly those three, and the witnesses assert all
three land in the binding's own vocabulary.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from docx_fixtures import Comment, Fixture, write_fixture
from labcairn.db.repository import TaskStore

from labcairn.application.context import ApplicationContext
from labcairn.application.papers import ProjectRequest, record_project
from labcairn.application.revision_loop import LoopOpened, open_loop
from labcairn.application.tasks import create_task
from labcairn.db.materials import put_source
from labcairn.db.models import PaperVersionRow
from labcairn.editing.drafts import ApprovedEdit
from labcairn.material.ingest import ingest_bytes
from labcairn.papers.binding import BindingOpened, open_binding
from labcairn.papers.feedback import FeedbackEvent
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.policy import Permission, PermissionPolicy, Rule

#: The single moment the binding's witnesses date themselves with. Determinism
#: rule: no wall clock, no fixture drift.
MOMENT: datetime = datetime(2026, 2, 1, 0, 0, 0, tzinfo=UTC)

#: An approval's window, so staleness is about the material, not the window.
WINDOW_END: datetime = MOMENT + timedelta(hours=1)

#: The reviewer whose sitting every decision and edge records.
OPERATOR: str = "Dr. Chen"

#: The model identity the roster carries. The substitute suggester stamps this
#: name into the edits it proposes, and the chain's roster maps the file's
#: author string back to it.
MODEL_ACTOR_ID: str = "substitute-model"

#: The substitute suggester's author string — what lands in ``w:author``.
MODEL_AUTHOR: str = MODEL_ACTOR_ID

PARAGRAPH_TEXT: str = "The method estimates the parameter from a single observation."
SECOND_PARAGRAPH_TEXT: str = "The results section reports the measured values."

#: The three comment bodies. The suggester dispatches on these; the witnesses
#: assert the dispatch, so the sample and the assertion cannot drift apart.
EDITABLE_TEXT: str = "Define the parameter in the methods."
EVIDENCE_TEXT: str = "Add a comparison with the previous study."
UNPLACEABLE_TEXT: str = "This whole section needs work."

SOURCE_KEY: str = "manuscript.docx"
ROOT_ID: str = "source:0"


def allow_all() -> PermissionPolicy:
    """The policy the task is created under; the binding's own context asks."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])


def ask_all() -> PermissionPolicy:
    """A policy that asks about everything: a question, not a denial."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ASK, pattern="**")])


@dataclass(frozen=True)
class BindingFixture:
    """One workspace, one task, one commented manuscript, one context."""

    context: ApplicationContext
    workspace_root: Path
    source_dir: Path
    manuscript: Path
    project_id: str
    version_id: str
    source_id: str
    source_root_id: str = ROOT_ID
    source_key: str = SOURCE_KEY


def build_manuscript(directory: Path) -> Path:
    """Write the three-case manuscript, and return its path.

    **One comment per paragraph, three paragraphs, no tracked changes.** The
    seam rewrites whole plain runs, and a paragraph with no revisions in it is
    exactly one plain run — so each comment's anchor resolves to a passage the
    seam can locate, and the two comments the binding must refuse or defer are
    refused for their own reasons, not because the fixture was awkward.
    """
    fixture = Fixture(
        name="binding-sample",
        paragraphs=(PARAGRAPH_TEXT, SECOND_PARAGRAPH_TEXT, "The discussion collects the threads."),
        comments=(
            Comment(
                comment_id="c-1",
                author="Prof. Lin",
                date="2026-01-20T09:00:00Z",
                text=EDITABLE_TEXT,
                paragraph=0,
                anchor_text="the parameter",
            ),
            Comment(
                comment_id="c-2",
                author="Prof. Lin",
                date="2026-01-20T09:05:00Z",
                text=EVIDENCE_TEXT,
                paragraph=1,
                anchor_text="the measured values",
            ),
            Comment(
                comment_id="c-3",
                author="Prof. Lin",
                date="2026-01-20T09:10:00Z",
                text=UNPLACEABLE_TEXT,
                paragraph=2,
                anchor_text="",
                after_text="",
                anchor="none",
            ),
        ),
        purpose="The binding's three-case sample: editable, needs evidence, unplaceable.",
    )
    directory.mkdir(parents=True, exist_ok=True)
    built = write_fixture(fixture, directory)
    path = directory / SOURCE_KEY
    path.write_bytes(built.read_bytes())
    return path


def _grant(context: ApplicationContext, project_id: str) -> None:
    """One store_read grant over the project, in LC-P2-06's own shape.

    The product has no writer for grants yet — the row is written the way
    ``tests/test_version_store.py`` writes it, and what the operations ask is
    the store's own reader over it.
    """
    from sqlalchemy import text

    context.store.session.execute(
        text(
            "INSERT INTO access_grants (grant_id, subject_ref, permission, purpose, "
            "scope, destination, granted_by, granted_at, expires_at, state, "
            "withdrawn_at, withdrawn_by, withdrawal_reason) VALUES "
            "(:grant_id, :subject_ref, :permission, :purpose, :scope, NULL, "
            "'Prof. Lin', :granted_at, NULL, :state, NULL, NULL, NULL)"
        ),
        {
            "grant_id": f"grant-{project_id}",
            "subject_ref": project_id,
            "permission": "store_read",
            "purpose": "read",
            "scope": f"{project_id}/**",
            "granted_at": MOMENT.isoformat(),
            "state": "active",
        },
    )
    context.store.session.commit()


def build_binding_fixture(env_store: TaskStore, workspace_root: Path) -> BindingFixture:
    """Bind a workspace whose source directory holds the three-case manuscript.

    The project and the version are written through the application layer's
    own writers — :func:`record_project` and the version row the version
    graph stores — so the witness exercises the same path a real round does,
    and the grant row resolves the project's ``consent_ref``.
    """
    manuscript = build_manuscript(workspace_root / "materials")

    created = create_task(
        store=env_store,
        policy=allow_all(),
        workspace_root=workspace_root,
        title="Binding witness task",
        goal=TaskGoal(
            objective="Answer every comment, and say which ones cannot be answered.",
            success_criterion="Four deliverables bound to one task and one output version.",
        ),
        source_dirs=(workspace_root / "materials",),
        now=MOMENT,
    )
    context = ApplicationContext(
        workspace=created.workspace,
        store=env_store,
        policy=ask_all(),
        ledger=ApprovalLedger(),
    )
    # **The manuscript is ingested the way the loop ingests it.** The ask-everything
    # context is the loop's own, and ``ingest_material`` would refuse under it —
    # so the fixture mints the source row through ``ingest_bytes`` + ``put_source``,
    # the same writers ``open_loop`` uses, against the same location-derived id.
    # What the witnesses exercise is the binding, not the ingestion gate.
    relative_path = f"materials/{SOURCE_KEY}"
    ingested = ingest_bytes(
        manuscript.read_bytes(),
        relative_path=relative_path,
        display_name=SOURCE_KEY,
        ingested_at=MOMENT,
    )
    put_source(env_store.session, ingested.source)
    env_store.session.commit()
    source_id = str(ingested.source.source_id)

    project_id = "proj-binding"
    version_id = "ver-input"
    # **The rows a fixture needs are written under the policy that allows
    # them.** The binding's own context asks about everything — that is the
    # property its effects are witnessed against — but a record about the
    # task's own area is bookkeeping the fixture performs, not an effect the
    # binding performs. The two writers get an allowing context, and the
    # binding's ask-everything context is what every effect after that runs
    # under.
    bookkeeping = ApplicationContext(
        workspace=created.workspace,
        store=env_store,
        policy=allow_all(),
        ledger=ApprovalLedger(),
    )
    # **The grant lands before the project names it.** ``record_project``
    # resolves the ``consent_ref`` it is given, so a reference to a grant the
    # table does not hold yet is a reference to nothing — the same refusal the
    # version-store witnesses hold.
    _grant(bookkeeping, project_id)
    record_project(
        bookkeeping,
        ProjectRequest(
            project_id=project_id,
            workspace_id="ws-binding",
            subject_pseudonym="subject-1",
            consent_ref=f"grant-{project_id}",
        ),
        now=MOMENT,
    )
    from sqlalchemy import text

    env_store.session.add(
        PaperVersionRow(
            version_id=version_id,
            project_id=project_id,
            source_id=source_id,
            source_content_sha256=env_store.session.execute(
                text("SELECT content_sha256 FROM sources WHERE source_id = :id"),
                {"id": source_id},
            ).scalar_one(),
            version_label_raw=SOURCE_KEY,
            stage_candidate="advisor_reviewed",
            status="resolved",
            created_at=MOMENT,
        )
    )
    env_store.session.commit()
    return BindingFixture(
        context=context,
        workspace_root=workspace_root,
        source_dir=workspace_root / "materials",
        manuscript=manuscript,
        project_id=project_id,
        version_id=version_id,
        source_id=source_id,
    )


def substitute_suggester(
    event: FeedbackEvent,
) -> ApprovedEdit | None:
    """The substitute suggestion source: deterministic, dispatches on the body.

    **What reproducibility meant in this run.** The source is a pure function
    of the opinion it is given: no provider call, no clock, no randomness.
    The same comment yields the same edit every time, which is what the
    record's reproducibility note cites — and it is the property the real
    model path (LC-P3-08) will have to replace with its own.

    **And it speaks in the seam's vocabulary.** The edit names a whole plain
    run — the anchor paragraph's full text — because that is the unit the
    seam rewrites; a suggestion aimed at a substring would be refused by the
    seam, not completed by the binding.
    """
    if event.comment_text == EDITABLE_TEXT:
        return ApprovedEdit(
            part="word/document.xml",
            paragraph=1,
            old_text=PARAGRAPH_TEXT,
            new_text=PARAGRAPH_TEXT.replace(
                "estimates the parameter", "estimates the parameter theta"
            ),
            author=MODEL_AUTHOR,
            date="2026-02-01T00:00:00+00:00",
        )
    if event.comment_text == EVIDENCE_TEXT:
        # The evidence case: the source has a suggestion, and the reviewer's
        # ``needs_evidence`` flag is what leaves the opinion unresolved.
        return ApprovedEdit(
            part="word/document.xml",
            paragraph=2,
            old_text=SECOND_PARAGRAPH_TEXT,
            new_text=SECOND_PARAGRAPH_TEXT.replace("reports", "compares against"),
            author=MODEL_AUTHOR,
            date="2026-02-01T00:00:00+00:00",
        )
    return None


def open_the_binding(fixture: BindingFixture) -> BindingOpened:
    """Open the binding over the fixture's manuscript, dated at the moment."""
    return open_binding(
        fixture.context,
        project_id=fixture.project_id,
        version_id=fixture.version_id,
        source_root_id=fixture.source_root_id,
        source_key=fixture.source_key,
        suggest=substitute_suggester,
        now=MOMENT,
    )


def feedback_id_of(fixture: BindingFixture, comment_id: str) -> str:
    """The chain's own id for one comment, read from the chain after recording.

    **The id is derived by the product, and the witness asks the product.**
    Re-deriving the hash here would be a second spelling of the derivation —
    two derivations that can drift — so the support module records the
    comments (idempotent: the same rows the binding's open writes) and reads
    the ids back from the chain.
    """
    from labcairn.papers.feedback import list_feedback_events, record_feedback

    record_feedback(
        fixture.context,
        project_id=fixture.project_id,
        version_id=fixture.version_id,
        now=MOMENT,
    )
    bodies = {
        "c-1": EDITABLE_TEXT,
        "c-2": EVIDENCE_TEXT,
        "c-3": UNPLACEABLE_TEXT,
    }
    for event in list_feedback_events(
        fixture.context, project_id=fixture.project_id, version_id=fixture.version_id
    ):
        if event.comment_text == bodies[comment_id]:
            return event.feedback_id
    raise AssertionError(f"the chain holds no comment with the body of {comment_id!r}")


def output_area_path(fixture: BindingFixture, key: str) -> Path:
    """The absolute path a key in the task output area lands at."""
    return fixture.workspace_root / "output" / str(fixture.context.task_id) / Path(*key.split("/"))


def read_dossier(fixture: BindingFixture, key: str) -> str:
    """The dossier's JSON, read back from the output area."""
    path = output_area_path(fixture, key)
    assert path.is_file(), f"the dossier was not written at {key!r}"
    return path.read_text(encoding="utf-8")


def second_loop(fixture: BindingFixture) -> LoopOpened:
    """A loop over the same material, for the duplicate-refusal witnesses."""
    return open_loop(
        fixture.context,
        source_root_id=fixture.source_root_id,
        source_key=fixture.source_key,
        now=MOMENT,
    )


def document_part_of(path: Path) -> bytes:
    """The ``word/document.xml`` part of a DOCX on disk."""
    with zipfile.ZipFile(path, "r") as archive:
        return archive.read("word/document.xml")
