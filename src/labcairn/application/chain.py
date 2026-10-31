"""The feedback chain's own facts, read through the layer.

**What this module is.** The mentor line reads the chain's rows — the
comments the advisor wrote, the changes that were made, the judgements on
them, the versions and the accepted edges between them, and the tracked
changes a marked-up manuscript records — and it used to read them by
importing ``labcairn.db.models`` and writing its own ``select(...)``
statements. **That is the arrangement the application layer exists to
prevent**: a reader that reaches the store directly is a reader the
capability model does not reach, and a guard applied to an operation
would apply to some of the callers and not the others.

So the chain's reads live here, and the modules that reason over them call
these operations instead of the store.

**And the revision events are read here too, because they are read beside
the comments.** ADR-0014's ``revision_events`` table holds what a
marked-up manuscript's file records — hundreds of changes, each with its
own text and its own address — and the chain's ``feedback_events`` holds
what a person wrote in the margins. **The two are read separately and are
not joined**: the pairing of a comment with a change is a judgement, it
carries its own evidence, and the chain asserts none that nobody made.
A manuscript that holds hundreds of changes and no comment at all is a
shape the chain can report and does not explain away.

**What these operations return.** Rows are not returned; the chain's own
facts are. A caller wants *a comment* — the advisor's words, the anchored
text, the version it was written against — and not a row it has to know the
shape of. The same is true of a change and of an accepted edge.

**What these operations refuse.** Nothing, beyond what the store itself
refuses: a row that is not there is reported as an empty answer, and the
*rule* that says what may be done with what was found is the caller's —
:mod:`labcairn.guidance.retrieval` and :mod:`labcairn.roles.trajectory`
hold those rules, and they ask the permission layer themselves where the
material is named.

**And why there is no capability check here.** The capability model judges
*resources*, and a resource is a path in a workspace. The chain's rows are
not the task's own rows — they belong to a paper project, not to a task —
and they name no path of their own. **The permission that governs what a
reader may be shown is the permission on the material**, and it is asked
where the material is named: the retrieval asks it per source at serve time
and drops the sources the reader may not reach (ADR-0003 C5), and the
chain's own operations ask it on the manuscript they read. Centralising the
reads here is what makes a guard added to this module reach **every**
caller — which is the property the seam exists for.
"""

from __future__ import annotations

import collections
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from sqlalchemy import select

from labcairn.application.context import ApplicationContext
from labcairn.db.models import (
    EditActionRow,
    FeedbackEventRow,
    PaperVersionRow,
    ResponseLinkRow,
    RevisionEventRow,
    VersionEdgeRow,
)
from labcairn.db.repository import load_source


@dataclass(frozen=True)
class ChainComment:
    """One comment, as the chain holds it.

    **The words and the anchor travel together.** A role may not put
    words in the advisor's mouth, so the quote a role proposes is checked
    against the very comment it points at — and the anchored text is what
    the scope of a distilled rule is built from.
    """

    feedback_id: str
    #: The chain's own key for the issue the comment is about. **Not
    #: ``None``**: a comment is only here because it was asked for by key.
    issue_key: str
    #: The manuscript state the comment was written against.
    version_id: str
    comment_text: str
    anchor_text: str


@dataclass(frozen=True)
class ChainEdit:
    """One change made in answer to a comment, and who made it."""

    edit_action_id: str
    #: The comment it answers, or ``None`` when it answers none.
    feedback_id: str | None
    #: The edge it is — the parent/child pair it moved.
    version_edge_id: str
    #: ``student``, ``advisor``, ``model`` or ``human``.
    actor_kind: str
    #: ``observed``, ``inferred`` or ``human_verified``.
    grade: str


@dataclass(frozen=True)
class ChainRevision:
    """One tracked change, as the chain holds it.

    **The change's own words and its own address travel together.** A
    reader asking what a reviewer changed needs the text *and* the place,
    and the place is what makes the text checkable: the view is part of
    the address, so a deletion is addressed in the rejected view and the
    same element in the two views is two addresses.

    **And there is more than one kind of change.** Word's markup carries
    a reviewer's insertion of a space and a cursor left behind under the
    same tag, and they are not the same act; :attr:`change_kind` says
    which one this is.
    """

    revision_event_id: str
    #: The manuscript version whose document the change was read from.
    version_id: str
    #: ``ins``, ``del``, ``moveFrom`` or ``moveTo`` — the element's kind.
    kind: str
    #: **What kind of change this is** — one of
    #: :data:`REVISION_CHANGE_KINDS`. Not the same thing as :attr:`kind`:
    #: the element's kind is how Word spells it, and this is what it did.
    change_kind: str
    #: The inserted or the deleted text. **Empty is a real value.**
    text: str
    #: The package part the change is in.
    part: str | None
    #: The path of the element inside that part.
    element_path: str | None
    #: ``accepted`` or ``rejected``.
    view: str | None
    #: The paragraph the change sits in.
    paragraph: int | None
    #: Who made it, or ``None`` when the file records no author.
    author: str | None
    #: When it was made, or ``None`` when the file records no date.
    occurred_at: datetime | None
    #: ``observed``, ``inferred`` or ``human_verified``.
    grade: str


#: The four kinds of change a stored revision event can record.
#:
#: **They are not the same thing, and counting them as one is how a panel
#: ends up drawing "this reviewer made 58 changes" when the file holds
#: 32 changes, 26 cursors left behind and no words at all.**
#:
#: - ``with_text`` — the change carries words.
#: - ``whitespace_only`` — the change carries only whitespace. **A space
#:   was inserted, and that is a change.**
#: - ``formatting_only`` — the run's formatting changed and its text did
#:   not.
#: - ``empty_marker`` — the element carries nothing at all: a cursor left
#:   behind by an operation at a point. **It is not a change, and it
#:   carries no judgement.**
REVISION_CHANGE_KINDS: Final[tuple[str, ...]] = (
    "with_text",
    "whitespace_only",
    "formatting_only",
    "empty_marker",
)

#: The element steps that say a revision is about a *mark* — a paragraph's
#: properties or a run's — rather than about the text. Word writes such a
#: revision with no children at all.
_MARK_STEPS: Final[frozenset[str]] = frozenset({"rPr", "pPr"})


def classify_revision_change(text: str, element_path: str | None) -> str:
    """What kind of change a stored revision event records.

    **Three of the four are told by the text.** A change that carries
    words is a change of the words; a change that carries only
    whitespace is a change too — a space was inserted — and it is not the
    same thing as a change that carries nothing.

    **And the fourth is told by the address.** Word records a revision to
    a paragraph mark or to a run's properties **under the properties
    element**, and it writes it with no children at all: that is a cursor
    left behind, and **it carries no judgement**. A revision in the run
    sequence that carries no words is a run whose formatting changed and
    whose text did not — which is a change, and a different one.

    **The reader flattens the two.** Both arrive with an empty text, and
    the address is what tells them apart. That is why this rule reads the
    address and not only the text, and why the empty marker must never
    be counted as a change.

    :param text: the text the event carries, exactly as it was read.
    :param element_path: the address of the element, in the reader's own
        spelling — ``/document[1]/body[1]/p[8]/pPr[1]/rPr[1]/ins[1]``.
    :returns: one of :data:`REVISION_CHANGE_KINDS`.
    """
    if text.strip():
        return "with_text"
    if text:
        return "whitespace_only"
    steps = {
        step.split("[")[0].replace("w:", "") for step in (element_path or "").split("/") if step
    }
    if steps & _MARK_STEPS:
        return "empty_marker"
    return "formatting_only"


@dataclass(frozen=True)
class ChainRevisionActivity:
    """What a marked-up manuscript holds, and what explains it.

    **The counts are the four kinds of change, not one number.** A
    marked-up manuscript holds changes in its text and comments in its
    margins, and **how many of each is a fact a reader can see for
    itself** — 303 changes in 14 paragraphs and no comment is a shape,
    and it is a shape the chain can report without explaining it away.

    **And the four kinds are told apart, because they are not the same
    act.** A reviewer's insertion of a space is a change; a cursor left
    behind at a point is not, and a run whose formatting changed and
    whose text did not is a third thing again. **A single total would
    count all three as changes, and the number a panel draws would be
    wrong** — one reviewer's copy in the corpus that motivated this table
    holds 58 revision elements and **32 changes** in it.

    **And nothing here says why anything was changed.** The counts are
    what the chain holds; the reason a reviewer gave for a change is in
    the comment that accompanies it, and a manuscript with no comments has
    no such reason to report.
    """

    #: The manuscript version.
    version_id: str
    #: The revision events the chain holds for it. **A total of events,
    #: and not a count of changes** — an empty marker is an event.
    revision_event_count: int
    #: The changes that carry words.
    changes_with_text: int
    #: The changes that carry only whitespace. **A space was inserted, and
    #: that is a change.**
    whitespace_only_changes: int
    #: The changes that carry no words because the formatting changed and
    #: the text did not.
    formatting_only_changes: int
    #: The events that carry nothing at all: a cursor left behind.
    #: **These are not changes, and they carry no judgement.**
    empty_markers: int
    #: How many paragraphs those events fall in.
    paragraphs_touched: int
    #: The largest number of events in one paragraph.
    most_events_in_a_paragraph: int
    #: How many comments the chain holds for the same version.
    comment_count: int


@dataclass(frozen=True)
class ChainEdge:
    """One accepted relationship between two versions.

    **Only accepted edges are here.** An edge nobody accepted is a
    proposal, and a proposal may not decide an order.
    """

    edge_id: str
    parent_version_id: str
    child_version_id: str


@dataclass(frozen=True)
class ProjectGraph:
    """The versions a project holds among the ones named, and its accepted edges.

    **The two facts are one read.** Whether a version is in the graph and
    what the graph's accepted edges say are both facts about the project's
    rows, and a reader that had to ask twice could be answered twice
    differently.
    """

    #: The versions of the project among the ones named. **A version the
    #: project does not hold is absent here** — a missing round is not a
    #: present one.
    version_ids: frozenset[str]
    #: The accepted edges between the versions named.
    edges: tuple[ChainEdge, ...]


def read_comments(
    context: ApplicationContext, *, issue_keys: Sequence[str]
) -> tuple[ChainComment, ...]:
    """The comments the chain holds under the issue keys named.

    **An empty answer is an empty answer.** A key the chain holds nothing
    under is reported as no comments, and it is the caller's rule that says
    what an absent comment means — a card that quotes it may not, a
    distillation that needs a case may not invent one.

    :param issue_keys: the chain's own keys. **Duplicates and blanks are
        the caller's business**: the chain's keys are names, not values,
        and a key that matches nothing contributes nothing.
    """
    keys = tuple(key for key in issue_keys if key)
    if not keys:
        return ()
    rows = context.store.session.scalars(
        select(FeedbackEventRow).where(FeedbackEventRow.issue_key.in_(keys))
    ).all()
    return tuple(
        ChainComment(
            feedback_id=row.feedback_id,
            issue_key=row.issue_key or "",
            version_id=row.version_id,
            comment_text=row.comment_text,
            anchor_text=row.anchor_text,
        )
        for row in rows
    )


def read_edits(
    context: ApplicationContext, *, feedback_ids: Sequence[str]
) -> tuple[ChainEdit, ...]:
    """The changes made in answer to the comments named.

    **A change that answers no comment is not here.** The changes are read
    by the comment they answer, so a change nobody asked about is not
    among them — and the caller that wants to know whether a named change
    answers a comment reads this and looks for it.
    """
    ids = tuple(feedback_id for feedback_id in feedback_ids if feedback_id)
    if not ids:
        return ()
    rows = context.store.session.scalars(
        select(EditActionRow).where(EditActionRow.feedback_id.in_(ids))
    ).all()
    return tuple(
        ChainEdit(
            edit_action_id=row.edit_action_id,
            feedback_id=row.feedback_id,
            version_edge_id=row.version_edge_id,
            actor_kind=row.actor_kind,
            grade=row.grade,
        )
        for row in rows
    )


def read_response_states(
    context: ApplicationContext, *, feedback_ids: Sequence[str]
) -> tuple[str, ...]:
    """The states of the judgements on the comments named.

    **The state is the judgement, and nothing else is.** Whether a change
    answered a comment is a fact the chain holds; which of the four
    states it holds is what a caller asks, and *which states count as
    standing* is the caller's rule.
    """
    ids = tuple(feedback_id for feedback_id in feedback_ids if feedback_id)
    if not ids:
        return ()
    rows = context.store.session.scalars(
        select(ResponseLinkRow.state).where(ResponseLinkRow.feedback_id.in_(ids))
    ).all()
    return tuple(str(state) for state in rows)


def read_revision_events(
    context: ApplicationContext, *, version_ids: Sequence[str]
) -> tuple[ChainRevision, ...]:
    """The tracked changes the chain holds for the versions named.

    **A change is reported with the words that changed and the address
    they changed at.** The two travel together because a text without a
    place cannot be checked: the view is part of the address, so a
    deletion is addressed in the rejected view and the same element in the
    two views is two addresses.

    **A version nobody holds changes for is simply not among them.** The
    events are read by the version they were read from, and a version with
    no events is a version whose document holds none.

    **And the permission is asked where the material is named**, as this
    module's rule says: the events carry the reviewer's own words, so the
    caller asks about the material through
    :func:`read_material_paths` before it shows any of them.
    """
    ids = tuple(version_id for version_id in version_ids if version_id)
    if not ids:
        return ()
    rows = context.store.session.scalars(
        select(RevisionEventRow).where(RevisionEventRow.version_id.in_(ids))
    ).all()
    return tuple(
        ChainRevision(
            revision_event_id=row.revision_event_id,
            version_id=row.version_id,
            kind=row.kind,
            change_kind=classify_revision_change(row.text, row.element_path),
            text=row.text,
            part=row.part,
            element_path=row.element_path,
            view=row.view,
            paragraph=row.paragraph,
            author=row.author,
            occurred_at=row.occurred_at,
            grade=row.grade,
        )
        for row in rows
    )


def read_revision_activity(
    context: ApplicationContext, *, version_ids: Sequence[str]
) -> tuple[ChainRevisionActivity, ...]:
    """What each version holds, and how much of it is explained.

    **The change counts are read from one table and the comment count from
    another, and the two are not joined.** A revision event says what
    changed; a comment says what a person wrote. The chain records both
    and asserts **no correspondence between them** — the pairing of a
    comment with a change is a judgement, it carries its own evidence, and
    nobody has made one here.

    **And the changes are counted by kind, not in one number.** A
    manuscript's revision elements are not all changes: some carry
    whitespace, some carry no words at all, and some are a cursor left
    behind. **A single total would call all of them changes**, and the
    number a panel draws would be wrong — so the four kinds are counted
    apart by :func:`classify_revision_change`, and the empty marker is
    never counted as a change.

    **So the honest reading of a marked-up manuscript is the four counts
    and the comment count, side by side**, and the shape a reader sees for
    itself.
    """
    ids = tuple(version_id for version_id in version_ids if version_id)
    if not ids:
        return ()
    session = context.store.session
    events = session.execute(
        select(
            RevisionEventRow.version_id,
            RevisionEventRow.paragraph,
            RevisionEventRow.text,
            RevisionEventRow.element_path,
        ).where(RevisionEventRow.version_id.in_(ids))
    ).all()
    comments = session.execute(
        select(FeedbackEventRow.version_id, FeedbackEventRow.feedback_id).where(
            FeedbackEventRow.version_id.in_(ids)
        )
    ).all()

    per_version: dict[str, list[int | None]] = {version_id: [] for version_id in ids}
    kinds: dict[str, collections.Counter[str]] = {
        version_id: collections.Counter() for version_id in ids
    }
    for version_id, paragraph, text, element_path in events:
        per_version.setdefault(version_id, []).append(paragraph)
        kinds.setdefault(version_id, collections.Counter())[
            classify_revision_change(text, element_path)
        ] += 1
    comment_counts: dict[str, int] = {}
    for version_id, _ in comments:
        comment_counts[version_id] = comment_counts.get(version_id, 0) + 1

    activities: list[ChainRevisionActivity] = []
    for version_id in ids:
        events_here = per_version.get(version_id, [])
        paragraphs = [paragraph for paragraph in events_here if paragraph is not None]
        counts: dict[int, int] = {}
        for paragraph in paragraphs:
            counts[paragraph] = counts.get(paragraph, 0) + 1
        found = kinds.get(version_id, collections.Counter())
        activities.append(
            ChainRevisionActivity(
                version_id=version_id,
                revision_event_count=len(events_here),
                changes_with_text=found["with_text"],
                whitespace_only_changes=found["whitespace_only"],
                formatting_only_changes=found["formatting_only"],
                empty_markers=found["empty_marker"],
                paragraphs_touched=len(counts),
                most_events_in_a_paragraph=max(counts.values()) if counts else 0,
                comment_count=comment_counts.get(version_id, 0),
            )
        )
    return tuple(activities)


def read_material_paths(
    context: ApplicationContext, *, version_ids: Sequence[str]
) -> Mapping[str, str]:
    """The workspace-relative path of the material each version was made from.

    **A version whose material the ledger does not hold is absent here.**
    The path is the spelling
    :meth:`~labcairn.application.context.ApplicationContext.resource_for`
    resolves, so a caller can ask the permission layer about it directly.

    :returns: the paths that were found, keyed by version id.
    """
    paths: dict[str, str] = {}
    session = context.store.session
    for version_id in version_ids:
        version = session.get(PaperVersionRow, version_id)
        if version is None:
            continue
        source = load_source(session, version.source_id)
        if source is None:
            continue
        paths[version_id] = source.relative_path
    return paths


def read_project_graph(
    context: ApplicationContext, *, project_id: str, version_ids: Sequence[str]
) -> ProjectGraph:
    """The project's graph, as the accepted edges have it.

    **Only the accepted edges are here, and only those between the
    versions named.** An edge nobody accepted is a proposal, and a
    proposal may not decide an order; an edge between two versions the
    caller did not name says nothing about the order the caller asked
    for.
    """
    session = context.store.session
    wanted = set(version_ids)
    held = frozenset(
        str(version_id)
        for version_id in session.scalars(
            select(PaperVersionRow.version_id).where(
                PaperVersionRow.version_id.in_(wanted),
                PaperVersionRow.project_id == project_id,
            )
        )
    )
    edges = tuple(
        ChainEdge(
            edge_id=edge.edge_id,
            parent_version_id=edge.parent_version_id,
            child_version_id=edge.child_version_id,
        )
        for edge in session.scalars(
            select(VersionEdgeRow).where(
                VersionEdgeRow.project_id == project_id,
                VersionEdgeRow.accepted_by.is_not(None),
                VersionEdgeRow.superseded_by.is_(None),
            )
        )
        if edge.parent_version_id in wanted and edge.child_version_id in wanted
    )
    return ProjectGraph(version_ids=held, edges=edges)


__all__ = [
    "REVISION_CHANGE_KINDS",
    "ChainComment",
    "ChainEdge",
    "ChainEdit",
    "ChainRevision",
    "ChainRevisionActivity",
    "ProjectGraph",
    "classify_revision_change",
    "read_comments",
    "read_edits",
    "read_material_paths",
    "read_project_graph",
    "read_response_states",
    "read_revision_activity",
    "read_revision_events",
]
