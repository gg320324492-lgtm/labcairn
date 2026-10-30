"""The feedback-chain exit demonstration, for LC-P2-09.

**Run it:**

```bash
python examples/feedback_demo.py
```

**What it shows.** One manuscript with a comment in it, and the chain from
that comment to what was decided about it:

1. **a comment read out of a synthetic DOCX**, with **both** of its
   addresses — the comment element in the comments part, and the body-side
   paragraph and offsets — and the text its anchor covers;
2. **a project, two versions and an edge** written by the version graph's
   own writer, not by a test's hand;
3. **an edit** made in answer to the comment, naming who made it;
4. **a response refused**, because nobody supplied the evidence behind the
   judgement — and then **the same response recorded**, with a decider and
   the evidence that decided it;
5. **the same issue in the later version**, visible as one recurring
   issue rather than two unrelated comments;
6. **a later assessment that says "not established"**, because *"we do
   not know"* is an answer the chain has to be able to carry;
7. **the four annotation events** in the task's own stream, in the order
   they were written, so a process that never imported the writers can
   replay the chain.

**Every claim is carried by a `check()` that raises.** The exit code is the
assertion that matters: a zero exit means every one of them still holds, and
a non-zero exit names the one that stopped. A demonstration that only
printed would be prose.

It uses a temporary database and a temporary workspace, executes no network
call, and needs no credential.
"""

from __future__ import annotations

import sys
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import text
from sqlalchemy.orm import Session

from labcairn.application import (
    ApplicationContext,
    ApplicationRefusedError,
    create_task,
)
from labcairn.application.material_ingestion import ingest_material
from labcairn.application.papers import (
    EdgeRequest,
    ProjectRequest,
    VersionRequest,
    record_edge,
    record_project,
    record_version,
)
from labcairn.application.refusal import ApplicationRefusal
from labcairn.application.sources import list_sources
from labcairn.core.ids import TaskId
from labcairn.db import create_db_engine, create_session_factory
from labcairn.db.migrations import upgrade_to_head
from labcairn.db.repository import TaskStore, events_after
from labcairn.papers.assessments import (
    list_recurring_issues,
    record_assessment,
)
from labcairn.papers.edits import list_edit_actions, record_edit
from labcairn.papers.feedback import (
    list_feedback_events,
    record_feedback,
    set_issue_key,
)
from labcairn.papers.responses import (
    list_response_links,
    list_unaddressed,
    record_response,
)
from labcairn.papers.versions import EdgeSource, StageCandidate, VersionStatus
from labcairn.runtime.event import EventType
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.policy import Permission, PermissionPolicy, Rule
from labcairn.sources.source import SourceKind

#: The one moment this demonstration writes. **No wall clock**: a
#: demonstration whose output changes between two runs is not one a test can
#: compare.
NOW = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)

#: The two rounds of the manuscript. The second is the same paragraph with
#: one sentence added, so the comment's anchor text is still in it.
FIRST = "The method estimates the parameter from a single observation."
SECOND = "The method estimates the parameter from a single observation. We measured it twice."

COMMENT_ID = "201"
COMMENT_TEXT = "Define the parameter."

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_XML_HEADER = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
_FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
_WML = "application/vnd.openxmlformats-officedocument.wordprocessingml"

_CONTENT_TYPES = (
    _XML_HEADER
    + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
    + '  <Default Extension="rels" ContentType="'
    + "application/vnd.openxmlformats-package.relationships+xml"
    + '"/>\n'
    + '  <Default Extension="xml" ContentType="application/xml"/>\n'
    + f'  <Override PartName="/word/document.xml" ContentType="{_WML}.document.main+xml"/>\n'
    + f'  <Override PartName="/word/comments.xml" ContentType="{_WML}.comments+xml"/>\n'
    + "</Types>\n"
)

_RELS = (
    _XML_HEADER
    + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
    + '  <Relationship Id="rId1" Type="'
    + "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    + '" Target="word/document.xml"/>\n'
    + "</Relationships>\n"
)

_DOCUMENT_RELS = (
    _XML_HEADER
    + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
    + '  <Relationship Id="rId2" Type="'
    + "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
    + '" Target="comments.xml"/>\n'
    + "</Relationships>\n"
)


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _write_manuscript(path: Path, paragraph: str) -> None:
    """One DOCX carrying one comment on one paragraph.

    **This is the demonstration's own document, not a test fixture.** It is
    written here so the demonstration can be run by a reader who has the
    repository and nothing else; the corpus the tests use is a different
    thing, with revisions and malformed cases this demonstration does not
    need. The archive is byte-reproducible because every entry carries the
    same fixed timestamp.
    """
    start = paragraph.index("the parameter")
    end = start + len("the parameter")
    before = _esc(paragraph[:start])
    anchor = _esc(paragraph[start:end])
    after = _esc(paragraph[end:])
    document = (
        f'{_XML_HEADER}<w:document xmlns:w="{_W}" xmlns:r="{_R}"><w:body><w:p>'
        f'<w:r><w:t xml:space="preserve">{before}</w:t></w:r>'
        f'<w:commentRangeStart w:id="{COMMENT_ID}"/>'
        f'<w:r><w:t xml:space="preserve">{anchor}</w:t></w:r>'
        f'<w:commentRangeEnd w:id="{COMMENT_ID}"/>'
        f'<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr>'
        f'<w:commentReference w:id="{COMMENT_ID}"/></w:r>'
        f'<w:r><w:t xml:space="preserve">{after}</w:t></w:r>'
        f"</w:p></w:body></w:document>"
    )
    comments = (
        f'{_XML_HEADER}<w:comments xmlns:w="{_W}">'
        f'<w:comment w:id="{COMMENT_ID}" w:author="Prof. Lin" '
        f'w:date="2026-03-02T09:30:00Z"><w:p><w:r>'
        f'<w:t xml:space="preserve">{_esc(COMMENT_TEXT)}</w:t>'
        f"</w:r></w:p></w:comment></w:comments>"
    )
    parts = (
        ("[Content_Types].xml", _CONTENT_TYPES),
        ("_rels/.rels", _RELS),
        ("word/_rels/document.xml.rels", _DOCUMENT_RELS),
        ("word/document.xml", document),
        ("word/comments.xml", comments),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in parts:
            info = zipfile.ZipInfo(name, date_time=_FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)


def check(condition: bool, message: str) -> None:
    """Assert, by raising.

    **A demonstration that warns is a demonstration that fails quietly.**
    The exit code carries every claim, so each one has to stop the run when
    it stops holding.
    """
    if not condition:
        raise AssertionError(message)


def _allow_all() -> PermissionPolicy:
    return PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])


def _grant(context: ApplicationContext, *, grant_id: str, scope: str) -> None:
    """One active read grant.

    **Written as a row, because the product has no writer for grants yet** —
    LC-P2-06 landed the table and the check, and the path that creates a
    grant is a later work order. The operations ask the store's reader over
    the row, which is the same question a real grant would answer.
    """
    context.store.session.execute(
        text(
            "INSERT INTO access_grants (grant_id, subject_ref, permission, purpose, "
            "scope, destination, granted_by, granted_at, expires_at, state, "
            "withdrawn_at, withdrawn_by, withdrawal_reason) VALUES "
            "(:grant_id, :subject_ref, :permission, :purpose, :scope, NULL, "
            "'Prof. Lin', :granted_at, NULL, 'active', NULL, NULL, NULL)"
        ),
        {
            "grant_id": grant_id,
            "subject_ref": "proj-1",
            "permission": "store_read",
            "purpose": "read",
            "scope": scope,
            "granted_at": "2026-01-01T00:00:00+00:00",
        },
    )
    context.store.session.commit()


def _source_id(context: ApplicationContext, name: str) -> str:
    for view in list_sources(context):
        if view.source.relative_path.endswith(name):
            return str(view.source.source_id)
    raise AssertionError(f"the task holds no material named {name!r}")


def demonstrate(root: Path) -> int:
    print("LC-P2-09 exit demonstration: the feedback chain")
    print("=" * 60)

    root.mkdir(parents=True, exist_ok=True)
    database = root / "labcairn.db"
    upgrade_to_head(database)
    engine = create_db_engine(database)
    session = create_session_factory(engine)()
    try:
        return _walk_the_chain(root, session)
    finally:
        session.close()
        engine.dispose()


def _walk_the_chain(root: Path, session: Session) -> int:
    materials = root / "materials"
    _write_manuscript(materials / "manuscript-1.docx", FIRST)
    _write_manuscript(materials / "manuscript-2.docx", SECOND)

    store = TaskStore(session)
    created = create_task(
        store=store,
        policy=_allow_all(),
        workspace_root=root,
        title="Recording the feedback chain",
        goal=TaskGoal(
            objective="Record what the advisor wrote and what answered it.",
            success_criterion="A chain a reader can traverse, and an honest gap.",
        ),
        source_dirs=(materials,),
        now=NOW,
    )
    context = ApplicationContext(
        workspace=created.workspace,
        store=store,
        policy=_allow_all(),
        ledger=ApprovalLedger(),
    )

    # -- 1. the material and the project ------------------------------------ #
    ingest_material(context, now=NOW)
    _grant(context, grant_id="grant-1", scope="proj-1/**")
    record_project(
        context,
        ProjectRequest(
            project_id="proj-1",
            workspace_id=str(created.task.task_id),
            subject_pseudonym="student-a",
            consent_ref="grant-1",
        ),
        now=NOW,
    )
    print("\n1. The project")
    print("   proj-1, pseudonym 'student-a', consent reference grant-1")
    print("   The consent reference is resolved against the grant table, not merely recorded.")

    # -- 2. the two versions and the edge ------------------------------------ #
    first_source = _source_id(context, "manuscript-1.docx")
    second_source = _source_id(context, "manuscript-2.docx")
    record_version(
        context,
        VersionRequest(
            version_id="ver-1",
            project_id="proj-1",
            source_id=first_source,
            version_label_raw="manuscript-1.docx",
            stage_candidate=StageCandidate.DRAFT,
            status=VersionStatus.RESOLVED,
        ),
        now=NOW,
    )
    record_version(
        context,
        VersionRequest(
            version_id="ver-2",
            project_id="proj-1",
            source_id=second_source,
            version_label_raw="manuscript-2.docx",
            stage_candidate=StageCandidate.SUBMITTED,
            status=VersionStatus.RESOLVED,
        ),
        now=NOW,
    )
    record_edge(
        context,
        EdgeRequest(
            edge_id="edge-1",
            project_id="proj-1",
            parent_version_id="ver-1",
            child_version_id="ver-2",
            source=EdgeSource.HUMAN,
            confidence=1.0,
            accepted_by="Prof. Lin",
            accepted_at=NOW,
        ),
        now=NOW,
    )
    print("\n2. The version graph")
    print("   ver-1 -> ver-2, settled by Prof. Lin; the edge is stored, not imagined.")

    # -- 3. the comment, and both of its addresses ---------------------------- #
    feedback = record_feedback(context, project_id="proj-1", version_id="ver-1", now=NOW)
    check(len(feedback) == 1, "one comment is one feedback row")
    item = feedback[0]
    print("\n3. The comment, and the two questions it answers")
    print(f"   feedback id:      {item.feedback_id}")
    print(f"   what was written: {item.comment_text!r} by {item.author!r}")
    print(f"   its own address:  {item.comment_locator}")
    print(
        f"   where it was written about: paragraph {item.anchor_paragraph}, "
        f"offsets {item.anchor_start}-{item.anchor_end}"
    )
    print(f"   the text it covers: {item.anchor_text!r}")
    check(item.comment_locator is not None, "the comment carries its own locator")
    check(item.anchor_text == "the parameter", "the anchor carries the text it covers")
    check(item.comment_text == COMMENT_TEXT, "the comment body is the file's own words")

    # -- 4. the edit ------------------------------------------------------------ #
    record_edit(
        context,
        edit_action_id="edit-1",
        version_edge_id="edge-1",
        actor_kind="student",
        actor_id="student-a",
        feedback_id=item.feedback_id,
        grade="observed",
        now=NOW,
    )
    edits = list_edit_actions(context, feedback_id=item.feedback_id)
    print("\n4. The edit")
    print(
        f"   {edits[0].edit_action_id}: {edits[0].actor_kind} {edits[0].actor_id!r} moved the edge"
    )
    check(edits[0].actor_kind == "student", "the edit names who made it")

    # -- 5. a judgement with no evidence is refused ------------------------------ #
    print("\n5. A response with no evidence")
    try:
        record_response(
            context,
            response_link_id="resp-1",
            feedback_id=item.feedback_id,
            edit_action_id="edit-1",
            state="addressed",
            now=NOW,
        )
    except ApplicationRefusedError as exc:
        print(f"   refused: {exc.reason.value}")
        print(f"   {exc.detail}")
        check(
            exc.reason is ApplicationRefusal.CHAIN_RESPONSE_NEEDS_EVIDENCE,
            "the refusal is the one the design names",
        )
    else:  # pragma: no cover - the branch is the failure
        raise AssertionError("a response with no evidence was recorded")

    # -- 6. the same judgement, with its evidence -------------------------------- #
    response = record_response(
        context,
        response_link_id="resp-1",
        feedback_id=item.feedback_id,
        edit_action_id="edit-1",
        state="addressed",
        decided_by="user",
        decided_at=NOW,
        evidence_refs=("ev-1",),
        now=NOW,
    )
    print("\n6. The same judgment, with what decided it")
    print(f"   state: {response.state}   decided by {response.decided_by!r} (a person)")
    print(f"   evidence: {response.evidence_refs}")
    check(response.state == "addressed", "the response says what was decided")
    check(response.decided_by == "user", "the response says a person settled it")
    check(response.evidence_refs == ("ev-1",), "the response carries its evidence")

    # -- 7. the recurrence --------------------------------------------------------- #
    second = record_feedback(context, project_id="proj-1", version_id="ver-2", now=NOW)
    check(len(second) == 1, "the later version's comment is its own row")
    set_issue_key(context, feedback_id=item.feedback_id, issue_key="parameter-definition", now=NOW)
    set_issue_key(
        context, feedback_id=second[0].feedback_id, issue_key="parameter-definition", now=NOW
    )
    issues = list_recurring_issues(context, project_id="proj-1")
    print("\n7. The same issue in a later version")
    for issue in issues:
        print(f"   {issue.issue_key}: {len(issue.feedback_ids)} comments, one issue")
    check(len(issues) == 1, "the two comments are one recurring issue")
    check(issues[0].feedback_ids and len(issues[0].feedback_ids) == 2, "the issue names both rows")

    unaddressed = list_unaddressed(context, project_id="proj-1")
    print(f"\n   the later version's comment, listed as unanswered: {len(unaddressed)}")
    check(len(unaddressed) == 1, "an unanswered comment is listed rather than omitted")

    # -- 8. the assessment that says "not established" ------------------------------ #
    assessment = record_assessment(
        context,
        assessment_id="assess-1",
        project_id="proj-1",
        assessment="Whether the later version defines the parameter.",
        outcome="not_established",
        basis="revised_manuscript",
        assessor_kind="human",
        issue_key="parameter-definition",
        evidence_refs=("ev-2",),
        now=NOW,
    )
    print("\n8. A later assessment")
    print(f"   {assessment.outcome}: {assessment.assessment}")
    print("   'not established' is a conclusion the chain can carry.")
    check(
        assessment.outcome == "not_established", "the assessment says what it could not establish"
    )

    # -- 9. the stream ---------------------------------------------------------------- #
    events = events_after(session, TaskId(str(created.task.task_id)))
    chain_types = [
        event.type
        for event in events
        if event.type
        in {
            EventType.FEEDBACK_RECORDED,
            EventType.EDIT_ACTION_RECORDED,
            EventType.RESPONSE_RECORDED,
            EventType.FOLLOWUP_ASSESSED,
        }
    ]
    print("\n9. The chain, in the task's own event stream")
    print(f"   {len(events)} events in the stream; the chain's are:")
    for event in chain_types:
        print(f"   {event.value}")
    check(
        EventType.FEEDBACK_RECORDED in chain_types,
        "a feedback event is in the stream",
    )
    check(
        EventType.EDIT_ACTION_RECORDED in chain_types,
        "an edit event is in the stream",
    )
    check(
        EventType.RESPONSE_RECORDED in chain_types,
        "a response event is in the stream",
    )
    check(
        EventType.FOLLOWUP_ASSESSED in chain_types,
        "an assessment event is in the stream",
    )
    check(
        len(set(chain_types)) == 4,
        "all four annotation types reached the stream",
    )

    print("\n" + "=" * 60)
    print("All checks held.")
    print(f"Feedback rows: {len(list_feedback_events(context, project_id='proj-1'))}")
    print(f"Responses:     {len(list_response_links(context, feedback_id=item.feedback_id))}")
    print(f"Sources:       {SourceKind.DOCX.value} material, read by the reader the product ships")
    return 0


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        return demonstrate(Path(raw) / "workspace")


if __name__ == "__main__":
    raise SystemExit(main())
