"""Role A: the revision-trajectory candidates.

LC-P2-12 T01. Role A reads the chain's own facts — the comments the
advisor wrote, the edits that were actually made, the version graph —
and **proposes** the alignment between a comment and the edit that
answered it, marking the issue type and how far the change went:
``resolved | partial | unresolved | unknown``.

**Two rules the work order makes refusals, not warnings.**

- **A candidate is a judgement, never a fact** (ADR-0018 D4): it points
  at a comment by its issue key, and it carries **no**
  ``comment_locator`` — the locator is what the reader's own row has,
  and a model's proposal carrying one would be a row pretending a
  person wrote it. The candidate's type has no such field, so the
  pretending is not a mistake a caller can make; it is a shape the
  vocabulary does not have.
- **And it may not put words in the advisor's mouth.** A candidate
  quotes the advisor, and the quote must be a **verbatim substring** of
  the comment the chain holds — a paraphrase offered as a quotation is
  refused by name.

**And the order of versions is the graph's, not the file names'.**
``最终版2.docx`` says nothing about which version is newer, and a
similarity score may never silently decide an order either — so
:func:`order_versions` walks the **accepted** edges only, refuses a
version the graph does not hold (a missing round is not a present one),
and refuses an order the accepted edges leave ambiguous rather than
picking one.

**The chain's rows are reached through the application layer.** The
comments, the changes and the accepted edges come from
:mod:`labcairn.application.chain`, so the role reads no table of its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from labcairn.application import chain as chain_layer
from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import role_refused
from labcairn.papers.labels import ISSUE_LABELS
from labcairn.roles.models import AgentRoleSpec, RoleOutput
from labcairn.roles.refusals import RoleRefusal

#: How far a change went toward answering its comment. Closed: a fifth
#: state arrives by a decision, not by a call.
ALIGNMENT_STATES: Final[frozenset[str]] = frozenset(
    {"resolved", "partial", "unresolved", "unknown"}
)


@dataclass(frozen=True)
class TrajectoryInput:
    """Role A's typed input: the material it is asked to read.

    The version ids and the issue keys name the chain's facts; the
    alignment between them is what the role proposes, and it is the
    role's *output*, not a field of this.
    """

    project_id: str
    version_ids: tuple[str, ...]
    issue_keys: tuple[str, ...]


@dataclass(frozen=True)
class TrajectoryComment:
    """A comment as the chain holds it, read for the role."""

    issue_key: str
    comment_text: str
    anchor_text: str


@dataclass(frozen=True)
class TrajectoryEdit:
    """An edit as the chain holds it, read for the role."""

    edit_action_id: str
    feedback_id: str | None
    version_edge_id: str
    actor_kind: str
    grade: str


@dataclass(frozen=True)
class TrajectoryMaterial:
    """What Role A read: the versions in graph order, and the chain's rows.

    **The comments and the edits are the facts; the candidates are not
    among them.** This object is what a model sees; nothing a model says
    is in it.
    """

    project_id: str
    ordered_version_ids: tuple[str, ...]
    comments: tuple[TrajectoryComment, ...]
    edits: tuple[TrajectoryEdit, ...]


@dataclass(frozen=True)
class TrajectoryCandidate(RoleOutput):
    """One alignment, proposed — a judgement, and shaped like one.

    The ``issue_key`` points at the comment; it is not the comment, and
    the type carries nothing that could be mistaken for one: **there is
    no locator field here**, because a locator is what a row the reader
    wrote has. The ``advisor_quote`` is the comment's own words, checked
    verbatim at construction; the ``note`` is where the role's reasoning
    goes, and it is the only free text on the object.
    """

    issue_key: str
    issue_type: str
    edit_action_id: str | None
    alignment: str
    advisor_quote: str
    note: str


def order_versions(
    context: ApplicationContext, *, project_id: str, version_ids: tuple[str, ...]
) -> tuple[str, ...]:
    """The versions in the order the accepted edges give them.

    Every version named must be in the project's graph, and the accepted
    edges must give a single order. **Neither a file name nor a
    similarity score may supply what the edges do not.**

    :raises ApplicationRefusedError: a version is not in the project's
        graph, or the accepted edges leave the order ambiguous.
    """
    wanted = set(version_ids)
    graph = chain_layer.read_project_graph(context, project_id=project_id, version_ids=version_ids)
    missing = sorted(wanted - graph.version_ids)
    if missing:
        raise role_refused(
            RoleRefusal.VERSION_OUTSIDE_THE_GRAPH,
            f"the project's graph holds no version under {missing!r}; a missing"
            " round is not a present one",
        )
    children: dict[str, set[str]] = {version_id: set() for version_id in wanted}
    for edge in graph.edges:
        children[edge.parent_version_id].add(edge.child_version_id)
    ordered: list[str] = []
    ready = sorted(vid for vid in wanted if not any(vid in kids for kids in children.values()))
    while ready:
        if len(ready) > 1:
            raise role_refused(
                RoleRefusal.VERSION_ORDER_AMBIGUOUS,
                f"the accepted edges leave {sorted(ready)!r} in no accepted order;"
                " neither a file name nor a similarity score may pick between"
                " them",
            )
        current = ready.pop()
        ordered.append(current)
        for child in sorted(children[current]):
            children[current].discard(child)
            if not any(child in kids for kids in children.values()):
                ready.append(child)
                ready.sort()
    if len(ordered) != len(wanted):
        raise role_refused(
            RoleRefusal.VERSION_ORDER_AMBIGUOUS,
            "the accepted edges do not reach every version named; the order"
            " they give is not the project's",
        )
    return tuple(ordered)


def read_trajectory(
    context: ApplicationContext, *, trajectory_input: TrajectoryInput
) -> TrajectoryMaterial:
    """The chain's facts for a run of role A, with the versions in graph order.

    **Everything here is a fact the chain holds.** The comments are the
    advisor's own words; the edits are rows somebody recorded; the order
    is the accepted edges'. A caller handing this to a model is handing
    over nothing the model could claim to have written.

    :raises ApplicationRefusedError: a version is outside the graph or
        its accepted order is ambiguous; a named issue key holds no
        comment in the chain.
    """
    ordered = order_versions(
        context,
        project_id=trajectory_input.project_id,
        version_ids=trajectory_input.version_ids,
    )
    by_key: dict[str, list[chain_layer.ChainComment]] = {}
    for comment in chain_layer.read_comments(context, issue_keys=trajectory_input.issue_keys):
        by_key.setdefault(comment.issue_key, []).append(comment)
    comments: list[TrajectoryComment] = []
    for key in trajectory_input.issue_keys:
        found = by_key.get(key, [])
        if not found:
            raise role_refused(
                RoleRefusal.COMMENT_NOT_IN_THE_CHAIN,
                f"the chain holds no comment under the key {key!r}, and a"
                " judgement about a comment that is not there is invented",
            )
        for row in found:
            comments.append(
                TrajectoryComment(
                    issue_key=row.issue_key or "",
                    comment_text=row.comment_text,
                    anchor_text=row.anchor_text,
                )
            )
    feedback_ids = tuple(comment.feedback_id for rows in by_key.values() for comment in rows)
    edits = tuple(
        TrajectoryEdit(
            edit_action_id=edit.edit_action_id,
            feedback_id=edit.feedback_id,
            version_edge_id=edit.version_edge_id,
            actor_kind=edit.actor_kind,
            grade=edit.grade,
        )
        for edit in chain_layer.read_edits(context, feedback_ids=feedback_ids)
    )
    return TrajectoryMaterial(
        project_id=trajectory_input.project_id,
        ordered_version_ids=ordered,
        comments=tuple(comments),
        edits=edits,
    )


def propose_candidate(
    context: ApplicationContext,
    *,
    spec: AgentRoleSpec,
    issue_key: str,
    issue_type: str,
    alignment: str,
    advisor_quote: str,
    note: str,
    edit_action_id: str | None = None,
) -> TrajectoryCandidate:
    """One candidate, checked and stamped: a judgement with its evidence named.

    The quote must be the comment's own words, verbatim; the alignment
    and the issue type must be in their closed vocabularies; and the
    edit named, when one is, must be the edit that answers this
    comment. **The output carries the contract that governed it** — the
    spec's role id and version — because a replay opens the contract
    the candidate was made under.

    :raises ApplicationRefusedError: the chain holds no comment under
        the key; the quote is not the comment's words; the alignment or
        the issue type is outside its vocabulary; or the edit named
        does not answer this comment.
    """
    comments = chain_layer.read_comments(context, issue_keys=(issue_key,))
    if not comments:
        raise role_refused(
            RoleRefusal.COMMENT_NOT_IN_THE_CHAIN,
            f"the chain holds no comment under the key {issue_key!r}",
        )
    if not any(advisor_quote in comment.comment_text for comment in comments):
        raise role_refused(
            RoleRefusal.QUOTE_NOT_IN_THE_CHAIN,
            "the quote is not the advisor's words in the chain, and a role may"
            " not put words in the advisor's mouth",
        )
    if alignment not in ALIGNMENT_STATES:
        raise role_refused(
            RoleRefusal.ALIGNMENT_STATE_UNKNOWN,
            f"{alignment!r} is not one of {sorted(ALIGNMENT_STATES)}",
        )
    if issue_type not in ISSUE_LABELS:
        raise role_refused(
            RoleRefusal.CANDIDATE_ISSUE_TYPE_UNKNOWN,
            f"{issue_type!r} is not one of the closed vocabulary's labels",
        )
    if edit_action_id is not None:
        feedback_ids = {comment.feedback_id for comment in comments}
        answers = chain_layer.read_edits(context, feedback_ids=tuple(feedback_ids))
        if not any(edit.edit_action_id == edit_action_id for edit in answers):
            raise role_refused(
                RoleRefusal.EDIT_DOES_NOT_ANSWER_THE_COMMENT,
                f"the edit {edit_action_id!r} does not answer the comment"
                f" {issue_key!r}, and an alignment to nothing is not an"
                " alignment",
            )
    return TrajectoryCandidate(
        role_id=spec.role_id,
        role_version=spec.role_version,
        issue_key=issue_key,
        issue_type=issue_type,
        edit_action_id=edit_action_id,
        alignment=alignment,
        advisor_quote=advisor_quote,
        note=note,
    )
