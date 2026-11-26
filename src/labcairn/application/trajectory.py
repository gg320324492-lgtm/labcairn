"""The multi-source learning index: a paper's revision trajectory, searchable.

**What this module is.** Phase 4's P4-MS line, first source (execution plan
§8.1): the paper and its revision trajectory. The chain's four tables hold
the facts of a revision round — the advisor's comments, the tracked changes,
the edits made in answer, and the judgements on them — and this module turns
those facts into **one searchable index** whose every entry carries its
source version and locator, the way §8.2 requires raw material to enter the
knowledge base.

**Two layers, and this module is the seam between them.** The *raw* layer is
the trajectory index: comments and edits, searchable by free text, each row
pointing back at the chain row it came from. The *refined* layer is the
guidance memory: rules a mentor has confirmed. This module writes the raw
layer and proposes candidates into the refined one — **and the retrieval
below serves only what a card may cite**: confirmed rules, never candidates,
which is §8.5's hard line that unreviewed experience is not a code of
conduct.

**The writes go through the session the context holds, and commit.** The
review workbench's writers established this shape: the store's session owns
the transaction, the operation commits, and a caller that wants both the
index rows and anything else in one unit wraps the calls itself. Re-ingesting
a project is the same rows — the ids are derived from the project, the kind
and the chain's own id — so an index that is read twice is an index that was
written once.

**And the permission is asked where the material is named.** Ingest reads a
version's comments and changes, so each version's material goes through
``source.inventory`` like any other bulk listing (ADR-0003 C5): a version
the policy denies is *dropped* from the index rather than refusing the
ingest, and an entry whose material cannot be shown is an entry the index
does not claim to hold.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Final

from sqlalchemy import select
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from labcairn.application import consent
from labcairn.application.context import ApplicationContext
from labcairn.application.models import Result
from labcairn.application.refusal import (
    ApplicationRefusal,
    ApplicationRefusedError,
    chain_refused,
)
from labcairn.db.models import (
    EditActionRow,
    FeedbackEventRow,
    PaperProjectRow,
    PaperVersionRow,
    ResponseLinkRow,
    RevisionEventRow,
    TrajectoryIndexRow,
    VersionEdgeRow,
)
from labcairn.evidence.index import build_match_expression
from labcairn.guidance.models import GuidanceRule
from labcairn.guidance.rules import confirm_rule, propose_rule
from labcairn.papers.chain import (
    ChainRefusal,
    material_relative_path,
    project_row,
    project_version_rows,
)
from labcairn.security.capabilities import CapabilityId

#: The default result size, for the same reason the guidance retrieval pins
#: one: a query nobody narrowed cannot stream the whole index into a card.
DEFAULT_LIMIT: Final[int] = 20

#: The two kinds of entry the index holds. **The vocabulary is closed** —
#: the schema's CHECK repeats it — because an entry that is neither a
#: comment nor an edit is a row nobody can render.
COMMENT_KIND: Final[str] = "comment"
EDIT_KIND: Final[str] = "edit"

#: The id prefix. Derived ids carry it, the way the chain's own ids do.
_ID_PREFIX: Final[str] = "trj-"

#: The longest display name the retrieval hands back. The memory stores a
#: rule's *statement* and no separate name; the display name is cut from the
#: statement's first line rather than invented.
_NAME_CEILING: Final[int] = 80


# -- the results ------------------------------------------------------------ #


class TrajectoryEntry(Result):
    """One indexed entry, as the ingest recorded it."""

    trajectory_id: str
    project_id: str
    entry_kind: str
    feedback_id: str | None
    edit_action_id: str | None
    revision_event_id: str | None
    version_id: str
    issue_key: str | None
    comment_text: str | None
    anchor_text: str | None
    anchor_paragraph: int | None
    verdict: str | None
    change_kind: str | None
    change_text: str | None
    text_digest: str
    source_version_id: str
    source_locator: str
    source_sha256: str
    ingested_at: datetime


class TrajectoryIngested(Result):
    """What one ingest pass indexed, and what it honestly skipped.

    ``skipped_versions`` counts the versions whose material the policy
    denied. **The skip is not an error**: a bulk write that refused whole
    because one version was out of reach would disclose that the version
    exists (ADR-0003 C5), so the ingest indexes what it may and says what
    it did not.
    """

    project_id: str
    entries_indexed: int
    comment_entries: int
    edit_entries: int
    skipped_versions: int
    ingested_at: str


class PaperProjectListed(Result):
    """One paper project, as a caller that would index its trajectory sees it.

    The subject's pseudonym is the row's own — never a name (the same rule
    :class:`~labcairn.db.models.PaperProjectRow` states). ``consent_ref``
    names the grant that governs the material; it grants nothing by being
    present, and the ingest still asks the policy per version.
    """

    project_id: str
    workspace_id: str
    subject_pseudonym: str
    consent_ref: str | None
    created_at: datetime


class ReviewRoundListed(Result):
    """One revision round, named by its ids and nothing else.

    **A round is an address, not a content.** The pair ``project_id`` and
    ``version_id`` says which paper and which revision of it a surface is
    working on; the words of the paper, the advisor's comments and the
    tracked changes live behind the versions' material and are reached
    through the service's own review routes, which apply the policy. A
    listing that carried a paragraph would be a listing that leaked the
    material it was supposed to name.

    ``created_at`` is when the version was recorded, so a reader can tell
    which of several rounds is the recent one without asking.
    """

    project_id: str
    version_id: str
    created_at: str


class TrajectoryHit(Result):
    """One search hit: the entry, with the provenance it was ingested with."""

    trajectory_id: str
    project_id: str
    entry_kind: str
    feedback_id: str | None
    edit_action_id: str | None
    revision_event_id: str | None
    version_id: str
    issue_key: str | None
    comment_text: str | None
    anchor_text: str | None
    anchor_paragraph: int | None
    verdict: str | None
    change_kind: str | None
    change_text: str | None
    text_digest: str
    source_version_id: str
    source_locator: str
    source_sha256: str
    ingested_at: str


class UsableRule(Result):
    """One rule a card may cite: confirmed by a mentor, and still standing.

    **The name is cut from the statement, not stored beside it.** The
    memory's schema holds a rule's statement, context, scope and example,
    and no separate name column — so the display name §8.2 asks for is the
    statement's first line, cut at :data:`_NAME_CEILING`, and the summary
    is the whole statement. A derived name is one spelling of one fact; a
    second stored name would be two facts to keep in step.
    """

    rule_id: str
    version: int
    name: str
    summary: str
    scope: str
    #: ``confirmed`` or ``disputed`` — the states a card may cite. A
    #: ``disputed`` rule travels with its reason in the memory's own read;
    #: this listing carries the state so a caller knows which it drew.
    state: str
    #: The chain material the rule was learned from, by the chain's own
    #: key — the source's *location* in the sense §8.2 asks the rule to
    #: keep. A card that cites the rule can follow these.
    sources: tuple[str, ...]
    confirmed_by: str | None
    confirmed_at: str | None


# -- the ingest ------------------------------------------------------------- #


def ingest_paper_trajectory(
    context: ApplicationContext,
    *,
    project_id: str,
    ingested_at: datetime | None = None,
) -> TrajectoryIngested:
    """Index one paper project's revision trajectory, and report the count.

    **Every comment becomes a comment entry; every recorded change becomes
    an edit entry.** A comment entry carries the advisor's words, the text
    they were anchored to, the paragraph they sit in, and the judgement
    that answered them — or no judgement, when nobody has given one, which
    is a fact and not a gap to fill. An edit entry carries the change's
    kind and words, the comment it answered, and the change's own address.

    **And the index is rebuilt in place, not appended to.** The ids are
    derived, so re-ingesting finds the rows that are already there and
    rewrites their fields; the FTS rows for the entries written are deleted
    and re-inserted in the same transaction. An index that appended a
    second copy of every entry on every read would be a record of
    ingestions, not of the trajectory.

    :raises ApplicationRefusedError: the project is not there, or the
        arguments are not usable.
    """
    moment = ingested_at if ingested_at is not None else datetime.now(UTC)
    session = context.store.session
    if project_row(session, project_id) is None:
        raise chain_refused(
            ChainRefusal.PROJECT_NOT_FOUND,
            f"the store holds no paper project with the id {project_id!r}. A "
            "trajectory is a project's revision history, and a history of a "
            "project nobody holds is a history of nothing.",
        )

    versions = _permitted_versions(context, project_id)
    comments = _comment_rows(session, tuple(version.version_id for version in versions))
    verdicts = _verdicts_by_feedback(session, tuple(c.feedback_id or "" for c in comments))
    edits = _edit_rows(session, project_id)

    indexed = 0
    comment_count = 0
    edit_count = 0
    for version in versions:
        sha = version.source_content_sha256 or ""
        for comment_row in (c for c in comments if c.version_id == version.version_id):
            entry = _comment_entry(
                context,
                comment_row,
                version.version_id,
                sha,
                verdicts.get(comment_row.feedback_id or ""),
                moment,
            )
            _write_entry(session, entry)
            indexed += 1
            comment_count += 1
    for edit_row, edge_project_id in edits:
        edit_entry = _edit_entry(session, edit_row, edge_project_id, comments, verdicts, moment)
        if edit_entry is None:
            continue
        _write_entry(session, edit_entry)
        indexed += 1
        edit_count += 1

    session.commit()
    return TrajectoryIngested(
        project_id=project_id,
        entries_indexed=indexed,
        comment_entries=comment_count,
        edit_entries=edit_count,
        skipped_versions=len(project_version_rows(session, project_id)) - len(versions),
        ingested_at=moment.isoformat(),
    )


def list_paper_projects(context: ApplicationContext) -> tuple[PaperProjectListed, ...]:
    """The paper projects the store holds, oldest first.

    **A listing of what ingesting can be asked about.** The CLI's
    ``sources ingest`` reads a whole workspace's material and then offers
    to index each paper project's revision trajectory; this is the read
    that says which projects those are. The rows name no resource of their
    own — the material is named per version, and the ingest asks the
    permission there — so this listing is not a capability question.

    :raises ApplicationRefusedError: the task's own store session is not
        usable.
    """
    rows: Sequence[PaperProjectRow] = context.store.session.scalars(
        select(PaperProjectRow).order_by(PaperProjectRow.created_at, PaperProjectRow.project_id)
    ).all()
    return tuple(
        PaperProjectListed(
            project_id=row.project_id,
            workspace_id=row.workspace_id,
            subject_pseudonym=row.subject_pseudonym,
            consent_ref=row.consent_ref,
            created_at=row.created_at,
        )
        for row in rows
    )


def list_review_rounds(context: ApplicationContext) -> tuple[ReviewRoundListed, ...]:
    """The revision rounds this workspace holds, **newest first**.

    **A round is an address, and this listing is addresses.** The service
    could not tell the workbench which round it was working on: the projects
    were in the store and nothing exposed them, so a surface that wanted a
    round had to name one it had been told about by something other than the
    service — which is how a surface ends up addressing a sample round
    forever. This is that read.

    **The material is not named, and the permission is asked anyway.** A
    round's ids say which paper and which revision of it; the words behind
    them are reached through the review routes, which apply the policy. The
    permission is still asked per version, on the version's own material,
    because a version the policy denies is dropped from the listing rather
    than named in it — the same rule the ingest follows, and the same rule
    ADR-0003 C5 asks a bulk listing to keep.

    **Newest first, because the recent one is the one a person is
    working on.** The order is the version's own recording time, and the
    project and version ids break a tie, so the same workspace answers the
    same way twice.

    :raises ApplicationRefusedError: the task's own store session is not
        usable.
    """
    dated: list[tuple[datetime, str, str]] = []
    for project in list_paper_projects(context):
        for version in _permitted_versions(context, project.project_id):
            dated.append((version.created_at, project.project_id, version.version_id))
    dated.sort(reverse=True)
    return tuple(
        ReviewRoundListed(
            project_id=project_id,
            version_id=version_id,
            created_at=created_at.isoformat(),
        )
        for created_at, project_id, version_id in dated
    )


def _permitted_versions(
    context: ApplicationContext, project_id: str
) -> tuple[PaperVersionRow, ...]:
    """The project's versions whose material the reader may reach.

    **The permission is asked once per version, on the material.** A denied
    version is dropped, not refused: the ingest of the versions a reader
    *may* see goes on, and the report says how many were skipped.
    """
    session = context.store.session
    versions = project_version_rows(session, project_id)
    paths = {
        version.version_id: material_relative_path(session, version.version_id)
        for version in versions
    }
    resources = tuple(context.resource_for(path) for path in paths.values() if path is not None)
    permitted = {
        resource.resolved_key
        for resource in consent.evaluate_each(
            context,
            capability=CapabilityId.SOURCE_INVENTORY,
            arguments={},
            resources=resources,
        )
    }
    return tuple(
        version
        for version in versions
        if (path := paths[version.version_id]) is not None
        and context.resource_for(path).resolved_key in permitted
    )


def _comment_rows(session: Session, version_ids: tuple[str, ...]) -> tuple[FeedbackEventRow, ...]:
    """The chain's comment rows for the versions named, in the reader's order."""
    if not version_ids:
        return ()
    return tuple(
        session.scalars(
            select(FeedbackEventRow)
            .where(FeedbackEventRow.version_id.in_(version_ids))
            .order_by(FeedbackEventRow.created_at, FeedbackEventRow.feedback_id)
        ).all()
    )


def _verdicts_by_feedback(session: Session, feedback_ids: tuple[str, ...]) -> dict[str, str]:
    """One judgement per comment: the first state any response link holds.

    **A link is a judgement, and a comment may have been judged once.** The
    chain is append-only, so a second link under one comment is a later
    word on the same question; this read takes the first and leaves the
    caller who needs the whole history to the chain's own reads. **No
    link, no verdict** — the absence travels as ``None``.
    """
    if not feedback_ids:
        return {}
    rows = session.scalars(
        select(ResponseLinkRow).where(ResponseLinkRow.feedback_id.in_(feedback_ids))
    ).all()
    verdicts: dict[str, str] = {}
    for row in rows:
        verdicts.setdefault(row.feedback_id, row.state)
    return verdicts


def _edit_rows(session: Session, project_id: str) -> tuple[tuple[EditActionRow, str], ...]:
    """The project's edit rows, reached through the edge each change moved along.

    **The edit table carries no project column**, because a change belongs
    to the edge it travelled — so the project's edits are the edits whose
    edge is the project's. A change on an edge of another project is not
    this project's history, however similar the words. Each row comes back
    with the edge's project id, which is the project the entry names.
    """
    rows = session.execute(
        select(EditActionRow, VersionEdgeRow.project_id)
        .join(VersionEdgeRow, EditActionRow.version_edge_id == VersionEdgeRow.edge_id)
        .where(VersionEdgeRow.project_id == project_id)
        .order_by(EditActionRow.edit_action_id)
    ).all()
    return tuple((row, str(edge_project_id)) for row, edge_project_id in rows)


def _comment_entry(
    context: ApplicationContext,
    row: FeedbackEventRow,
    version_id: str,
    sha: str,
    verdict: str | None,
    moment: datetime,
) -> TrajectoryEntry:
    """One comment entry: the advisor's words, their anchor, and the verdict."""
    anchor = row.anchor_text
    paragraph = row.anchor_paragraph
    locator = (
        f"paragraph:{paragraph}:start:{row.anchor_start}:end:{row.anchor_end}"
        if anchor is not None and paragraph is not None
        else f"comment:{row.feedback_id}"
    )
    digest = row.comment_text + ("\n" + anchor if anchor else "")
    trajectory_id = _entry_id(
        context.store.session, "comment", row.project_id, row.feedback_id or ""
    )
    return TrajectoryEntry(
        trajectory_id=trajectory_id,
        project_id=row.project_id,
        entry_kind=COMMENT_KIND,
        feedback_id=row.feedback_id,
        edit_action_id=None,
        revision_event_id=None,
        version_id=version_id,
        issue_key=row.issue_key,
        comment_text=row.comment_text,
        anchor_text=anchor,
        anchor_paragraph=paragraph,
        verdict=verdict,
        change_kind=None,
        change_text=None,
        text_digest=digest,
        source_version_id=version_id,
        source_locator=locator,
        source_sha256=sha,
        ingested_at=moment,
    )


def _edit_entry(
    session: Session,
    row: EditActionRow,
    edge_project_id: str,
    comments: tuple[FeedbackEventRow, ...],
    verdicts: dict[str, str],
    moment: datetime,
) -> TrajectoryEntry | None:
    """One edit entry: the change, the comment it answered, and the address.

    ``None`` when the change's revision event is not in the store — an edit
    whose change cannot be shown is an entry about nothing, and the index
    does not claim to hold it.
    """
    revision_id = row.edit_action_id[len("ea-") :] if row.edit_action_id.startswith("ea-") else None
    revision = session.get(RevisionEventRow, revision_id) if revision_id else None
    if revision is None:
        return None
    comment = next((c for c in comments if c.feedback_id == row.feedback_id), None)
    version_sha = ""
    if revision.version_id:
        version = session.get(PaperVersionRow, revision.version_id)
        version_sha = version.source_content_sha256 or "" if version is not None else ""
    change_kind = revision.kind
    commented = comment.comment_text if comment is not None else None
    digest_parts = [f"{change_kind}: {revision.text}"]
    if commented:
        digest_parts.append(f"replying to: {commented}")
    locator = f"{revision.part or 'word/document.xml'}#{revision.element_path or ''}"
    return TrajectoryEntry(
        trajectory_id=_entry_id(session, "edit", edge_project_id, row.edit_action_id or ""),
        project_id=edge_project_id,
        entry_kind=EDIT_KIND,
        feedback_id=row.feedback_id,
        edit_action_id=row.edit_action_id,
        revision_event_id=revision.revision_event_id,
        version_id=revision.version_id,
        issue_key=comment.issue_key if comment is not None else None,
        comment_text=commented,
        anchor_text=None,
        anchor_paragraph=revision.paragraph,
        verdict=verdicts.get(row.feedback_id or "") if row.feedback_id else None,
        change_kind=change_kind,
        change_text=revision.text,
        text_digest="\n".join(digest_parts),
        source_version_id=revision.version_id,
        source_locator=locator,
        source_sha256=version_sha,
        ingested_at=moment,
    )


def _entry_id(session: Session, kind: str, project_id: str, source_id: str) -> str:
    """The derived id of one index entry, stable across re-ingestions.

    **The id names the entry, not the moment it was written.** The digest
    folds the project, the kind and the chain's own id, so ingesting the
    same trajectory twice finds the same rows — the rule the chain's own
    derived ids apply to re-reading a manuscript.
    """
    digest = hashlib.sha256(f"{project_id}\x00{kind}\x00{source_id}".encode()).hexdigest()
    return f"{_ID_PREFIX}{digest[:32]}"


def _write_entry(session: Session, entry: TrajectoryEntry) -> None:
    """Write one entry and its FTS row, replacing whatever stood before."""
    row = session.get(TrajectoryIndexRow, entry.trajectory_id)
    if row is None:
        row = TrajectoryIndexRow(trajectory_id=entry.trajectory_id)
        session.add(row)
    row.project_id = entry.project_id
    row.entry_kind = entry.entry_kind
    row.feedback_id = entry.feedback_id
    row.edit_action_id = entry.edit_action_id
    row.revision_event_id = entry.revision_event_id
    row.version_id = entry.version_id
    row.issue_key = entry.issue_key
    row.comment_text = entry.comment_text
    row.anchor_text = entry.anchor_text
    row.anchor_paragraph = entry.anchor_paragraph
    row.verdict = entry.verdict
    row.change_kind = entry.change_kind
    row.change_text = entry.change_text
    row.text_digest = entry.text_digest
    row.source_version_id = entry.source_version_id
    row.source_locator = entry.source_locator
    row.source_sha256 = entry.source_sha256
    row.ingested_at = entry.ingested_at
    session.flush()
    session.execute(
        sql_text("DELETE FROM trajectory_fts WHERE trajectory_id = :tid"),
        {"tid": entry.trajectory_id},
    )
    session.execute(
        sql_text("INSERT INTO trajectory_fts (text_digest, trajectory_id) VALUES (:body, :tid)"),
        {"body": entry.text_digest, "tid": entry.trajectory_id},
    )


# -- the retrieval ---------------------------------------------------------- #


def search_trajectory(
    context: ApplicationContext,
    *,
    query: str,
    project_id: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> tuple[TrajectoryHit, ...]:
    """The trajectory entries whose digest matches *query*, best first.

    **A hit carries the whole entry**, not a snippet: the caller learns
    what was said or changed **and** which version and locator it came
    from, which is the point of keeping provenance in the index.

    **The match is the evidence index's own expression builder**, on the
    same trigram tokenizer, so the two indexes answer queries the same way
    — including the honest empty answer for a query with no servable terms.
    A query with no terms is an empty answer, not an error.

    **And a project filter narrows, it does not widen.** A hit from another
    project is not this project's history, however well it matches.
    """
    if limit < 1:
        return ()
    expression = build_match_expression(query)
    if expression is None:
        return ()
    session = context.store.session
    rows = session.execute(
        sql_text(
            "SELECT r.trajectory_id FROM trajectory_fts AS f "
            "JOIN trajectory_index_rows AS r ON r.trajectory_id = f.trajectory_id "
            "WHERE trajectory_fts MATCH :expression "
            "AND (:project_id IS NULL OR r.project_id = :project_id) "
            "ORDER BY rank LIMIT :limit"
        ),
        {"expression": expression, "project_id": project_id, "limit": limit},
    ).fetchall()
    hits: list[TrajectoryHit] = []
    for (trajectory_id,) in rows:
        row = session.get(TrajectoryIndexRow, str(trajectory_id))
        if row is not None:
            hits.append(_the_hit(row))
    return tuple(hits)


def _the_hit(row: TrajectoryIndexRow) -> TrajectoryHit:
    """One index row, as the search returns it."""
    return TrajectoryHit(
        trajectory_id=row.trajectory_id,
        project_id=row.project_id,
        entry_kind=row.entry_kind,
        feedback_id=row.feedback_id,
        edit_action_id=row.edit_action_id,
        revision_event_id=row.revision_event_id,
        version_id=row.version_id,
        issue_key=row.issue_key,
        comment_text=row.comment_text,
        anchor_text=row.anchor_text,
        anchor_paragraph=row.anchor_paragraph,
        verdict=row.verdict,
        change_kind=row.change_kind,
        change_text=row.change_text,
        text_digest=row.text_digest,
        source_version_id=row.source_version_id,
        source_locator=row.source_locator,
        source_sha256=row.source_sha256,
        ingested_at=row.ingested_at.isoformat(),
    )


# -- the rule candidates ---------------------------------------------------- #


def propose_rule_candidate(
    context: ApplicationContext,
    *,
    trajectory_id: str,
    issue_type: str,
    statement: str,
    rule_context: str,
    scope: str,
    example: str,
    proposed_by: str,
    now: datetime,
) -> GuidanceRule:
    """Draft a rule *candidate* from one indexed trajectory entry.

    **The candidate is not a rule yet.** It lands in the memory as a
    ``candidate`` — the same state a person's proposal lands in — and no
    retrieval serves it until a second reader confirms it (§8.5: unreviewed
    experience is a candidate, never a code of conduct).

    **The entry is the source, and the binding is the entry's own.** A
    comment entry binds the rule to the comment's issue key — the chain's
    own name for the material it was learned from; an edit entry binds it
    to the change's revision event. **An entry that cannot name its
    material proposes nothing**: a comment nobody has keyed and a change
    whose revision event was never recorded are material the memory cannot
    show, and a rule the memory cannot show the source of is the bare
    preference the work order refuses.

    :raises ApplicationRefusedError: the entry is not indexed, it names no
        chain material, or the draft fails the memory's own validation.
    """
    row = context.store.session.get(TrajectoryIndexRow, trajectory_id)
    if row is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"no trajectory entry with the id {trajectory_id!r} is indexed. A "
            "candidate is drafted from material the index holds, and a draft "
            "about nothing is a draft about nothing.",
        )
    if row.entry_kind == COMMENT_KIND:
        source = row.issue_key
        if not source:
            raise ApplicationRefusedError(
                ApplicationRefusal.ARGUMENTS_INVALID,
                f"the comment behind {trajectory_id!r} carries no issue key, and "
                "a candidate names the chain material it was learned from. Key "
                "the comment first, then propose from it.",
            )
    else:
        source = row.revision_event_id
        if not source:
            raise ApplicationRefusedError(
                ApplicationRefusal.ARGUMENTS_INVALID,
                f"the change behind {trajectory_id!r} was never recorded as a "
                "revision event, and a candidate names the chain material it "
                "was learned from.",
            )
    return propose_rule(
        context,
        issue_type=issue_type,
        statement=statement,
        rule_context=rule_context,
        scope=scope,
        example=example,
        sources=(source,),
        proposed_by=proposed_by,
        now=now,
    )


def confirm_rule_candidate(
    context: ApplicationContext,
    *,
    rule_id: str,
    confirmed_by: str,
    now: datetime,
) -> GuidanceRule:
    """A mentor confirms a candidate, and the candidate becomes a rule.

    **This is the review the §8.5 line is about.** The proposer cannot be
    the confirmer, a rule that is not a candidate cannot be confirmed, and
    the confirmation names the person and the moment — the memory's own
    second-reader rule, asked rather than restated.
    """
    return confirm_rule(context, rule_id=rule_id, confirmed_by=confirmed_by, now=now)


# -- the usable listing ----------------------------------------------------- #


def usable_guidance(
    context: ApplicationContext,
    *,
    scope: str | None = None,
    project_id: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> tuple[UsableRule, ...]:
    """The rules a card may cite: mentor-confirmed, still standing, in scope.

    **Candidates are not here.** The retrieval underneath serves confirmed
    and disputed rules only — a candidate reaching a card would be a
    proposal dressed as a record, and §8.5 makes that a hard refusal. A
    withdrawn rule is not here either: the state machine's ``withdrawn`` is
    outside the served states, so **a rule the mentor has retracted stops
    being served the moment it is retracted**, and the next task does not
    see it.

    **A rule's sources are checked at query time.** The retrieval resolves
    each source against the chain as it stands now — a rule whose source
    material has been judged unanswered, or that the reader may not reach,
    is not served. What comes back is what stands, for this reader, now.

    :param scope: narrow the answer to rules whose scope mentions this
        text, case-insensitively. ``None`` or empty serves every scope.
    :param project_id: narrow the answer to the rules this project may be
        served — the ones learned from its chain material, plus the ones
        a mentor has published to the group (Phase 4 §8.5 / P4-G3).
        ``None`` serves every standing rule, which is the workbench's own
        view. A shared rule's sources are still resolved through the
        permission layer, so a source this reader may not reach is
        dropped, never widened.
    """
    from labcairn.guidance.retrieval import search_rules

    if limit < 1:
        return ()
    needle = scope.strip().lower() if scope else ""
    usable: list[UsableRule] = []
    for hit in search_rules(context, include_candidates=False, project_id=project_id):
        if needle and needle not in hit.rule.scope.lower():
            continue
        usable.append(
            UsableRule(
                rule_id=hit.rule.rule_id,
                version=hit.rule.version,
                name=_display_name(hit.rule.statement),
                summary=hit.rule.statement,
                scope=hit.rule.scope,
                state=hit.rule.state,
                sources=hit.rule.sources,
                confirmed_by=hit.rule.confirmed_by,
                confirmed_at=hit.rule.confirmed_at.isoformat() if hit.rule.confirmed_at else None,
            )
        )
        if len(usable) >= limit:
            break
    return tuple(usable)


def _display_name(statement: str) -> str:
    """The statement's first line, cut to the display ceiling.

    **A cut is not a second fact.** The whole statement travels in
    :attr:`UsableRule.summary`; the name exists so a card can show one
    line, and a line that was cut says so.
    """
    first_line = statement.strip().splitlines()[0] if statement.strip() else ""
    if len(first_line) <= _NAME_CEILING:
        return first_line
    return first_line[: _NAME_CEILING - 1] + "…"
