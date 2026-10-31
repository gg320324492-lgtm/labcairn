"""The scaffolding the feedback chain's four test files share.

**Why this module exists.** The chain's tests all need the same four
things: a manuscript with comments in it, a task that holds it, a paper
project the manuscript belongs to, and a version — and most of them need
a *second* version, because a recurrence is a fact about two versions.
Building that four times over, in four files, is four places for it to be
wrong.

**It is a helper and not a fixture**, because a fixture that grows a
second responsibility is a fixture that later tests cannot reason about;
and the project's rule is that a test needing more than the shared three
builds its own, locally and visibly.

**The version graph is written directly.** ``paper_projects``,
``paper_versions`` and ``version_edges`` have no writer in ``src/`` — that
is LC-P2-09 T00's subtask — so the scaffolding writes the rows itself.
**It writes them the way the schema wants them**, so a test that depends
on this module is not quietly depending on a writer that does not exist.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from docx_fixtures import Comment, Fixture, Revision, write_fixture

from labcairn.application.context import ApplicationContext
from labcairn.application.material_ingestion import ingest_material
from labcairn.application.sources import list_sources
from labcairn.application.tasks import create_task
from labcairn.db.models import PaperProjectRow, PaperVersionRow, VersionEdgeRow
from labcairn.db.repository import TaskStore
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.policy import Permission, PermissionPolicy, Rule

#: The one moment the chain's tests write. **No wall clock**, for the
#: project's reason.
MOMENT = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)

#: The paragraph every fixture is built on, unless a test says otherwise.
PARAGRAPH = "The method estimates the parameter from a single observation."

#: The comments part's own namespace, which the hand-written one below
#: must match.
_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def allow_all() -> PermissionPolicy:
    """A policy that permits everything, for a test about something else."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])


@dataclass(frozen=True)
class ChainEnv:
    """Everything a chain test needs, in one place.

    **Two versions, because one is not a chain.** A recurrence is a fact
    about two versions, and the edge between them is what a change moves
    along.
    """

    context: ApplicationContext
    project_id: str
    version_id: str
    second_version_id: str
    edge_id: str
    source_id: str
    second_source_id: str
    manuscript: Path
    second_manuscript: Path


def _source_id(context: ApplicationContext, suffix: str) -> str:
    """The id of the ingested material whose path ends with *suffix*."""
    for view in list_sources(context):
        if view.source.relative_path.endswith(suffix):
            return str(view.source.source_id)
    raise AssertionError(f"the task holds no material ending in {suffix!r}")


def _source_sha256(context: ApplicationContext, suffix: str) -> str:
    """The hash of the ingested material whose path ends with *suffix*.

    **A version names the bytes it was recorded with**, and the version
    rows below now carry that hash. It is what lets the revision-event
    path refuse a manuscript whose bytes changed under the name, which is
    the check ADR-0014 D6 asks for.
    """
    for view in list_sources(context):
        if view.source.relative_path.endswith(suffix):
            return str(view.source.content_sha256)
    raise AssertionError(f"the task holds no material ending in {suffix!r}")


def _without_author_or_date(manuscript: Path, comment_ids: tuple[str, ...]) -> Path:
    """The manuscript with *comment_ids* carrying no author and no date.

    **The attributes are removed, not emptied.** The corpus's writer
    always writes ``w:author``, and an *empty* author is a different case
    from a *missing* one — the corpus says so, and the reader treats them
    differently: an empty author is an anonymous remark, and a missing one
    is an unknown with a reason.

    **And the file is replaced, not joined by a second copy.** A second
    copy in the same directory would be ingested as a second material, and
    the source the chain resolved would still be the original.

    The parts are copied rather than rewritten, so the manuscript keeps
    every other byte — including the fixed timestamps that make the
    archive byte-reproducible.
    """
    with zipfile.ZipFile(manuscript, "r") as archive:
        parts = [(info, archive.read(info.filename)) for info in archive.infolist()]
    temporary = manuscript.with_name(f"{manuscript.stem}-rewritten.docx")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
        for info, data in parts:
            if info.filename == "word/comments.xml":
                text = data.decode("utf-8")
                for comment_id in comment_ids:
                    text = re.sub(
                        rf'(<w:comment w:id="{comment_id}")[^>]*>',
                        r"\1>",
                        text,
                    )
                data = text.encode("utf-8")
            archive.writestr(info, data)
    temporary.replace(manuscript)
    return manuscript


def build_chain(
    store: TaskStore,
    workspace_root: Path,
    *,
    comments: tuple[Comment, ...] = (),
    paragraphs: tuple[str, ...] = (PARAGRAPH,),
    revisions: tuple[Revision, ...] = (),
    second_comments: tuple[Comment, ...] | None = None,
    bare_comment_ids: tuple[str, ...] = (),
) -> ChainEnv:
    """A workspace, a task, a project, two versions and an edge.

    :param comments: the comments in the first manuscript.
    :param second_comments: the comments in the second manuscript. ``None``
        means the second manuscript carries no comments at all, which is
        what a test about a *first* round wants.
    :param bare_comment_ids: the comments whose author and date are
        removed from the file altogether.
    """
    materials = workspace_root / "materials"
    materials.mkdir(parents=True, exist_ok=True)

    first = Fixture(
        name="chain-first",
        paragraphs=paragraphs,
        revisions=revisions,
        comments=comments,
        purpose="The chain's first round.",
    )
    second = Fixture(
        name="chain-second",
        paragraphs=paragraphs,
        revisions=revisions,
        comments=second_comments or (),
        purpose="The chain's second round.",
    )
    directory = workspace_root / "built"
    directory.mkdir(exist_ok=True)
    manuscript = materials / "manuscript.docx"
    second_manuscript = materials / "manuscript-2.docx"
    manuscript.write_bytes(write_fixture(first, directory).read_bytes())
    second_manuscript.write_bytes(write_fixture(second, directory).read_bytes())
    if bare_comment_ids:
        manuscript = _without_author_or_date(manuscript, bare_comment_ids)

    created = create_task(
        store=store,
        policy=allow_all(),
        workspace_root=workspace_root,
        title="Recording the feedback chain",
        goal=TaskGoal(
            objective="Record what the advisor wrote and what answered it.",
            success_criterion="A chain a reader can traverse, and an honest gap.",
        ),
        source_dirs=(materials,),
        now=MOMENT,
    )
    context = ApplicationContext(
        workspace=created.workspace,
        store=store,
        policy=allow_all(),
        ledger=ApprovalLedger(),
    )
    ingest_material(context, now=MOMENT)

    source_id = _source_id(context, "manuscript.docx")
    second_source_id = _source_id(context, "manuscript-2.docx")

    session = store.session
    session.add(
        PaperProjectRow(
            project_id="proj-1",
            workspace_id="ws-1",
            subject_pseudonym="subject-1",
            consent_ref=None,
            created_at=MOMENT,
        )
    )
    session.add(
        PaperVersionRow(
            version_id="ver-1",
            project_id="proj-1",
            source_id=source_id,
            source_content_sha256=_source_sha256(context, "manuscript.docx"),
            version_label_raw="manuscript.docx",
            stage_candidate="advisor_reviewed",
            status="resolved",
            created_at=MOMENT,
        )
    )
    session.add(
        PaperVersionRow(
            version_id="ver-2",
            project_id="proj-1",
            source_id=second_source_id,
            source_content_sha256=_source_sha256(context, "manuscript-2.docx"),
            version_label_raw="manuscript-2.docx",
            stage_candidate="draft",
            status="resolved",
            created_at=MOMENT,
        )
    )
    session.add(
        VersionEdgeRow(
            edge_id="edge-1",
            project_id="proj-1",
            parent_version_id="ver-1",
            child_version_id="ver-2",
            source="human",
            confidence=1.0,
            evidence_spans=[{"kind": "revision", "text": "revised"}],
            accepted_by="Dr. Chen",
            accepted_at=MOMENT,
            edge_version=1,
            superseded_by=None,
            created_at=MOMENT,
        )
    )
    session.commit()
    return ChainEnv(
        context=context,
        project_id="proj-1",
        version_id="ver-1",
        second_version_id="ver-2",
        edge_id="edge-1",
        source_id=source_id,
        second_source_id=second_source_id,
        manuscript=manuscript,
        second_manuscript=second_manuscript,
    )


def a_comment(
    comment_id: str,
    *,
    text: str = "Define the parameter.",
    author: str = "Prof. Lin",
    date: str = "2026-03-02T09:30:00Z",
    anchor_text: str = "the parameter",
    anchor: str = "both",
) -> Comment:
    """One comment on the standard paragraph.

    **The author and the date are parameters** because the reader's
    handling of a missing one is one of the things under test: a comment
    with no author has an unknown author, and never a guessed one. Pass
    ``author=""`` for the *empty* author, which is a different case from a
    missing one.
    """
    return Comment(
        comment_id=comment_id,
        author=author,
        date=date,
        text=text,
        paragraph=0,
        anchor_text=anchor_text,
        anchor=anchor,
    )


__all__ = [
    "MOMENT",
    "PARAGRAPH",
    "ChainEnv",
    "a_comment",
    "allow_all",
    "build_chain",
]
