"""The feedback chain's own facts, read through the layer.

**What this module is.** The mentor line reads the chain's rows — the
comments the advisor wrote, the changes that were made, the judgements on
them, the versions and the accepted edges between them — and it used to
read them by importing ``labcairn.db.models`` and writing its own
``select(...)`` statements. **That is the arrangement the application layer
exists to prevent**: a reader that reaches the store directly is a reader
the capability model does not reach, and a guard applied to an operation
would apply to some of the callers and not the others.

So the chain's reads live here, and the modules that reason over them call
these operations instead of the store.

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

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy import select

from labcairn.application.context import ApplicationContext
from labcairn.db.models import (
    EditActionRow,
    FeedbackEventRow,
    PaperVersionRow,
    ResponseLinkRow,
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
    "ChainComment",
    "ChainEdge",
    "ChainEdit",
    "ProjectGraph",
    "read_comments",
    "read_edits",
    "read_material_paths",
    "read_project_graph",
    "read_response_states",
]
