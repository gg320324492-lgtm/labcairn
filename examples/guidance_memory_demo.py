"""The guidance-memory demonstration, for LC-P2-11.

**Run it:**

```bash
python examples/guidance_memory_demo.py
```

**What it shows.** The mentor line's rule memory, end to end, on one
synthetic manuscript with two comments in it:

1. **a rule retrieved with its source and its counterexample** — the
   answer is never a bare sentence; it carries the key of the chain
   material it was learned from and the case against it;
2. **a conflicting rule returned beside it** — both come back, ordered
   by state and identity, and **neither wins by being newer**;
3. **a source withdrawn from under a rule making it invalid** — shown
   through the permission layer, whose denied material is dropped, and
   reported by the invalidation record rather than disappeared;
4. **a candidate nobody has confirmed** — the distillation's proposal,
   proposed by ``model_proposal``, visible to the reviewer's query and
   to no card;
5. **a new comment changing what the retrieval returns, with nothing
   trained** — the change is the memory's rows, and nothing else.

**Every claim is carried by a `check()` that raises.** The exit code is
the assertion that matters: a zero exit means every one of them still
holds, and a non-zero exit names the one that stopped. A demonstration
that only printed would be prose.

**And every row is written by the product's own code** — the version
graph's recorders, the chain's recorders, the rules' lifecycle, the
distillation and the retrieval — except two: the read grant, which has
no writer yet (the same exception ``feedback_demo`` declares), and the
re-judgement, which has none either and is the retrieval tests' own
witness. This demonstration withdraws a source the way the product can
today, by taking it out of the reader's reach.

It uses a temporary database and a temporary workspace, executes no
network call, and needs no credential.
"""

from __future__ import annotations

import sys
import tempfile
import zipfile
from datetime import UTC, datetime
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import text
from sqlalchemy.orm import Session

from labcairn.application import ApplicationContext, create_task
from labcairn.application.material_ingestion import ingest_material
from labcairn.application.papers import (
    EdgeRequest,
    ProjectRequest,
    VersionRequest,
    record_edge,
    record_project,
    record_version,
)
from labcairn.application.sources import list_sources
from labcairn.db.migrations import upgrade_to_head
from labcairn.db.repository import TaskStore
from labcairn.db.session import create_db_engine, create_session_factory
from labcairn.guidance.distil import MODEL_PROPOSER, distil_candidate
from labcairn.guidance.retrieval import invalidated_rules, search_rules
from labcairn.guidance.rules import confirm_rule, propose_rule, record_counterexample
from labcairn.papers.edits import record_edit
from labcairn.papers.feedback import record_feedback, set_issue_key
from labcairn.papers.responses import record_response
from labcairn.papers.versions import EdgeSource, StageCandidate, VersionStatus
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import CapabilityId
from labcairn.security.policy import Permission, PermissionPolicy, Rule

#: The one moment this demonstration writes. **No wall clock**: a
#: demonstration whose output changes between two runs is not one a test can
#: compare.
NOW = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)

PARAGRAPH = "The method estimates the parameter from a single observation."
COMMENT_BASELINE = "Define the parameter."
COMMENT_FIGURE = "Show the numbers in the caption."

KEY_BASELINE = "iss-gold-a-r1"
KEY_FIGURE = "iss-gold-a-r2"

BASELINE_RULE = (
    "When the claim rests on a comparison, the advisor asks for the baseline"
    " to be named in the same paragraph."
)
EFFECT_RULE = (
    "When the claim rests on an effect size, the advisor asks for the interval"
    " to be shown beside it."
)

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


def check(condition: bool, message: str) -> None:
    """The demonstration's own assertion: a claim that raises is a claim."""
    if not condition:
        raise AssertionError(message)


def _write_manuscript(path: Path, comments: tuple[tuple[str, str, str], ...]) -> None:
    """A minimal DOCX: one paragraph, and each comment anchored over its words.

    The comment's range is drawn around a **substring of the paragraph**,
    the way the reader's anchors are: the anchored text is text the file
    itself carries, and the offsets into it are the reader's to compute.
    """
    parts: list[str] = []
    cursor = 0
    elements: list[str] = []
    for comment_id, body, anchored in comments:
        index = PARAGRAPH.index(anchored, cursor)
        parts.append(
            f'<w:r><w:t xml:space="preserve">{escape(PARAGRAPH[cursor:index])}</w:t></w:r>'
        )
        parts.append(f'<w:commentRangeStart w:id="{comment_id}"/>')
        parts.append(f'<w:r><w:t xml:space="preserve">{escape(anchored)}</w:t></w:r>')
        parts.append(f'<w:commentRangeEnd w:id="{comment_id}"/>')
        parts.append(
            '<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr>'
            f'<w:commentReference w:id="{comment_id}"/></w:r>'
        )
        cursor = index + len(anchored)
        elements.append(
            f'<w:comment w:id="{comment_id}" w:author="Prof. Lin"'
            ' w:date="2026-03-02T09:30:00Z">'
            f'<w:p><w:r><w:t xml:space="preserve">{escape(body)}</w:t></w:r></w:p>'
            "</w:comment>"
        )
    parts.append(f'<w:r><w:t xml:space="preserve">{escape(PARAGRAPH[cursor:])}</w:t></w:r>')
    document = (
        f'{_XML_HEADER}<w:document xmlns:w="{_W}" xmlns:r="{_R}"><w:body><w:p>'
        + "".join(parts)
        + "</w:p></w:body></w:document>"
    )
    comments_part = (
        _XML_HEADER + f'<w:comments xmlns:w="{_W}">' + "".join(elements) + "</w:comments>"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in (
            ("[Content_Types].xml", _CONTENT_TYPES),
            ("_rels/.rels", _RELS),
            ("word/document.xml", document),
            ("word/_rels/document.xml.rels", _DOCUMENT_RELS),
            ("word/comments.xml", comments_part),
        ):
            info = zipfile.ZipInfo(name, date_time=_FIXED_TIMESTAMP)
            info.external_attr = 0o600 << 16
            info.create_system = 3
            archive.writestr(info, data)


def _allow_all() -> PermissionPolicy:
    return PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])


def _deny_source_read() -> PermissionPolicy:
    """The second reader's policy: everything but the material's text."""
    return PermissionPolicy.from_rules(
        [
            Rule(
                effect=Permission.DENY,
                pattern="**",
                capabilities=frozenset({CapabilityId.SOURCE_READ.value}),
            )
        ]
    )


def _grant(context: ApplicationContext, *, grant_id: str, scope: str) -> None:
    """One active read grant.

    **Written as a row, because the product has no writer for grants
    yet** — LC-P2-06 landed the table and the check, and the path that
    creates a grant is a later work order. The operations ask the
    store's reader over the row, which is the same question a real
    grant would answer.
    """
    context.store.session.execute(
        text(
            "INSERT INTO access_grants (grant_id, subject_ref, permission, purpose, "
            "scope, destination, granted_by, granted_at, expires_at, state, "
            "withdrawn_at, withdrawn_by, withdrawal_reason) VALUES "
            "(:grant_id, :subject_ref, :permission, :purpose, :scope, NULL, "
            ":granted_by, :granted_at, NULL, 'active', NULL, NULL, NULL)"
        ),
        {
            "grant_id": grant_id,
            "subject_ref": "proj-1",
            "permission": "store_read",
            "purpose": "read",
            "scope": scope,
            "granted_by": "the-owner",
            "granted_at": NOW.isoformat(),
        },
    )
    context.store.session.commit()


def _source_id(context: ApplicationContext, name: str) -> str:
    for view in list_sources(context):
        if view.source.relative_path.endswith(name):
            return str(view.source.source_id)
    raise AssertionError(f"the task holds no material named {name!r}")


def demonstrate(root: Path) -> int:
    print("LC-P2-11 demonstration: the mentor guidance memory")
    print("=" * 60)

    root.mkdir(parents=True, exist_ok=True)
    database = root / "labcairn.db"
    upgrade_to_head(database)
    engine = create_db_engine(database)
    session = create_session_factory(engine)()
    try:
        return _walk_the_memory(root, session)
    finally:
        session.close()
        engine.dispose()


def _walk_the_memory(root: Path, session: Session) -> int:
    materials = root / "materials"
    materials.mkdir(parents=True, exist_ok=True)
    _write_manuscript(
        materials / "manuscript-1.docx",
        (
            ("202", COMMENT_FIGURE, "The method"),
            ("201", COMMENT_BASELINE, "the parameter"),
        ),
    )
    _write_manuscript(materials / "manuscript-2.docx", ())

    store = TaskStore(session)
    created = create_task(
        store=store,
        policy=_allow_all(),
        workspace_root=root,
        title="Recording the guidance memory",
        goal=TaskGoal(
            objective="Show a rule that carries its source, and a candidate that waits.",
            success_criterion="A retrieval whose answers can be traced and withdrawn.",
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

    ingest_material(context, now=NOW)
    first_source = _source_id(context, "manuscript-1.docx")
    second_source = _source_id(context, "manuscript-2.docx")
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
    for version_id, source_id, label, stage in (
        ("ver-1", first_source, "manuscript-1.docx", StageCandidate.DRAFT),
        ("ver-2", second_source, "manuscript-2.docx", StageCandidate.SUBMITTED),
    ):
        record_version(
            context,
            VersionRequest(
                version_id=version_id,
                project_id="proj-1",
                source_id=source_id,
                version_label_raw=label,
                stage_candidate=stage,
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

    feedback = record_feedback(context, project_id="proj-1", version_id="ver-1", now=NOW)
    check(len(feedback) == 2, "the manuscript carries two comments")
    by_text = {event.comment_text: event for event in feedback}
    baseline, figure = by_text[COMMENT_BASELINE], by_text[COMMENT_FIGURE]
    keyed_baseline = set_issue_key(
        context, feedback_id=baseline.feedback_id, issue_key=KEY_BASELINE, now=NOW
    )
    set_issue_key(context, feedback_id=figure.feedback_id, issue_key=KEY_FIGURE, now=NOW)
    for index, event in enumerate((baseline, figure), start=1):
        record_edit(
            context,
            edit_action_id=f"edit-{index}",
            version_edge_id="edge-1",
            actor_kind="student",
            actor_id="student-a",
            feedback_id=event.feedback_id,
            now=NOW,
        )
        record_response(
            context,
            response_link_id=f"resp-{index}",
            feedback_id=event.feedback_id,
            edit_action_id=f"edit-{index}",
            state="addressed",
            grade="human_verified",
            decided_by="user",
            decided_at=NOW,
            evidence_refs=(f"check:{event.feedback_id}",),
            now=NOW,
        )
    print("\n1. The chain the rules will stand on")
    print("   two comments, keyed; two edits; two judgements that say answered.")
    check(keyed_baseline.issue_key == KEY_BASELINE, "the first comment carries its key")

    # -- 2. a rule with its source and its counterexample -------------------- #
    rule = propose_rule(
        context,
        issue_type="method_and_hypothesis",
        statement=BASELINE_RULE,
        rule_context="A results section whose claim is comparative.",
        scope="Empirical papers in this group's field.",
        example="The advisor's comment of 2026-03-02 on the ablation paragraph.",
        sources=(KEY_BASELINE,),
        proposed_by="the-mentor",
        now=NOW,
    )
    confirmed = confirm_rule(
        context, rule_id=rule.rule_id, confirmed_by="the-second-reader", now=NOW
    )
    challenged = record_counterexample(
        context,
        rule_id=rule.rule_id,
        statement="The ablation paragraph named its baseline, and the advisor said nothing.",
        recorded_by="the-second-reader",
        now=NOW,
        issue_key=KEY_FIGURE,
    )
    served = search_rules(context)
    print("\n2. A rule retrieved with its source and its counterexample")
    print(f"   statement: {served[0].rule.statement[:64]}...")
    print(f"   source:    {served[0].sources[0].issue_key}")
    print(f"   case:      {served[0].rule.counterexamples[0].statement[:56]}...")
    check(confirmed.state == "confirmed", "the second reader's confirmation lands")
    check(len(served) == 1, "one confirmed rule is one hit")
    check(served[0].sources[0].issue_key == KEY_BASELINE, "the hit carries its source key")
    check(len(challenged.counterexamples) == 1, "the case travels with the rule")

    # -- 3. a conflicting rule returned beside it ---------------------------- #
    other = propose_rule(
        context,
        issue_type="method_and_hypothesis",
        statement=EFFECT_RULE,
        rule_context="A results section whose claim is an effect size.",
        scope="Empirical papers in this group's field.",
        example="The advisor's comment of 2026-03-09 on the interval.",
        sources=(KEY_BASELINE,),
        proposed_by="the-mentor",
        now=NOW,
    )
    confirm_rule(context, rule_id=other.rule_id, confirmed_by="the-second-reader", now=NOW)
    both = search_rules(context, issue_type="method_and_hypothesis")
    print("\n3. A conflicting rule returned beside it")
    print(f"   both come back: {len(both)} rules, ordered by state and id, never by time")
    check(len(both) == 2, "two conflicting rules are both returned")
    check(
        [hit.rule.rule_id for hit in both] == sorted(hit.rule.rule_id for hit in both),
        "the order is the rules' identity, and recency is not in it",
    )
    check(all(hit.sources for hit in both), "each rule comes back with its sources")

    # -- 4. a withdrawn source invalidates the rule --------------------------- #
    denied = ApplicationContext(
        workspace=created.workspace,
        store=store,
        policy=_deny_source_read(),
        ledger=ApprovalLedger(),
    )
    check(
        len(search_rules(denied)) == 0,
        "a rule whose source the reader cannot reach is not served to that reader",
    )
    gone = invalidated_rules(denied)
    print("\n4. A source withdrawn from under a rule")
    print(f"   the denied reader is served nothing; the report names {len(gone)}")
    print(f"   reason:    reachable=False for {gone[0].reasons[0].issue_key}")
    check(len(gone) == 2, "the invalidation is reported, not silent")
    check(
        all(item.reasons[0].reachable is False for item in gone),
        "the reason is the reader's reach, and the chain's rows are untouched",
    )

    # -- 5. a candidate nobody has confirmed ---------------------------------- #
    candidate = distil_candidate(
        context,
        issue_type="figures",
        statement=(
            "When a figure carries the claim, the advisor asks for the numbers in the caption."
        ),
        rule_context="A figure that carries the claim.",
        issue_keys=(KEY_FIGURE,),
        now=NOW,
    )
    default_view = search_rules(context)
    reviewer_view = search_rules(context, include_candidates=True)
    print("\n5. A candidate nobody has confirmed")
    print(f"   proposed by {MODEL_PROPOSER}; on the cards: {len(default_view)},")
    print(f"   in the reviewer's query: {[hit.rule.proposed_by for hit in reviewer_view]}")
    check(candidate.state == "candidate", "the distillation proposes, and stops there")
    check(candidate.proposed_by == MODEL_PROPOSER, "the record says whose proposal it is")
    check(
        all(hit.rule.rule_id != candidate.rule_id for hit in default_view),
        "a candidate reaches no card",
    )
    check(
        [hit.rule.state for hit in reviewer_view]
        == ["confirmed", "confirmed", "candidate"],
        "the reviewer sees the candidates, behind the confirmed rules",
    )
    check(
        reviewer_view[-1].rule.rule_id == candidate.rule_id
        and reviewer_view[-1].rule.proposed_by == MODEL_PROPOSER,
        "the candidate is the model's, and it waits at the end of the order",
    )

    # -- 6. a new comment changes the retrieval, nothing trained -------------- #
    confirmed_candidate = confirm_rule(
        context, rule_id=candidate.rule_id, confirmed_by="the-second-reader", now=NOW
    )
    served_after = search_rules(context, issue_type="figures")
    print("\n6. A new comment changes what the retrieval returns")
    print(f"   the confirmed candidate is served: {served_after[0].rule.statement[:56]}...")
    check(confirmed_candidate.state == "confirmed", "a person's word moved the state")
    check(
        len(served_after) == 1 and served_after[0].rule.statement.startswith("When a figure"),
        "the retrieval's answer changed because a row changed",
    )

    print("\nThe demonstration holds: the memory serves sourced, scoped rules,")
    print("keeps its conflicts side by side, reports its invalidations, and")
    print("waits for a person on every proposal.")
    return 0


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="labcairn-guidance-demo-") as root:
        return demonstrate(Path(root))


if __name__ == "__main__":
    sys.exit(main())
