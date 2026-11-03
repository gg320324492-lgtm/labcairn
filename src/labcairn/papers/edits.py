"""The edit: a change made in answer to a comment, and **who made it**.

**Why the table exists at all.** ADR-0016 names *model → accepted change*
as the third of its three promotion paths: a model rewrites the
manuscript, the change is recorded, and it is attributed to the advisor.
The schema would be satisfied, the report would cite an address, and
**nothing would say the sentence was invented.** A feedback chain that
records who made the edit is the only thing that catches it.

**And there is no default actor.** A default is how a model's change
becomes the advisor's, so the column is not nullable, its vocabulary is
closed, and a ``model`` row may not carry a person's id.

**A change that answers nothing is not an error.** A student may edit for
reasons the advisor never wrote down, so ``feedback_id`` is nullable and
says so.

**And what one row is.** **One change**, and *not* one change-that-
answers-a-comment: the nullable column above is the reason, and a table
that held only the answers would have nothing for it to say. A marked-up
manuscript holds hundreds of changes and a handful of comments, and the
chain records the changes and names the comment each one answers **where
the caller says it answers one**.

**And the step that fills the ring.** :func:`record_edits_from_revisions`
reads the changes a manuscript's file records and writes one row for
each, with **the actor the operator's roster names** — because a name in
a file is a string somebody typed, and **the chain does not read an
actor out of a file.**
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from labcairn.application import consent
from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError, chain_refused
from labcairn.db.models import EditActionRow, RevisionEventRow
from labcairn.papers.chain import (
    ChainRefusal,
    classify_revision_change,
    edge_row,
    edit_action_id_for,
    edit_row,
    feedback_row,
    material_relative_path,
    project_row,
    version_row,
)
from labcairn.papers.revisions import record_revision_events
from labcairn.runtime.trajectory import emit_edit_action_recorded
from labcairn.security.capabilities import CapabilityId
from labcairn.security.paths import CanonicalPath

#: Who made a change. **Four, and the fourth is the one the design is
#: about.**
ACTOR_KINDS: frozenset[str] = frozenset({"student", "advisor", "model", "human"})

#: The grades an edit may carry — ADR-0014 D2's three levels.
EDIT_GRADES: frozenset[str] = frozenset({"observed", "inferred", "human_verified"})

#: The kind of change a cursor left behind is, and **it is not a
#: change**. A revision Word writes with no children under a run's or a
#: paragraph's properties is the mark an operation at a point leaves
#: behind, and the chain records changes and not marks.
EMPTY_MARKER: str = "empty_marker"


@dataclass(frozen=True, slots=True)
class EditAction:
    """One change, as the chain records it.

    **The actor is the point.** Every other column says what happened;
    ``actor_kind`` says who did it.
    """

    edit_action_id: str
    feedback_id: str | None
    version_edge_id: str
    actor_kind: str
    actor_id: str | None
    grade: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ActorClaim:
    """What the operator says a name the file records is.

    **The claim is the operator's, and it is made in the open.** A Word
    file records the *string* an editor typed into the revision's author
    box, and that string is not an identity: the same person is spelled
    two ways across two drafts, and a change a model drafted and a person
    pasted into Word carries **that person's** name. **So the chain does
    not read an actor out of a file** — it reads the operator's answer
    to the question *"whose change is this?"*, and the answer is supplied
    every time the ring is filled.

    **And the answer names a kind and a plain id.** The kind is one of
    the four the table's column names; the id is the operator's own
    handle for that person, and **the file's author string is never
    copied into it** — the string is a lookup key and not an id, and
    LC-P2-09's own boundary says the chain records kinds of actor and
    plain ids and does not decide who a person is.
    """

    actor_kind: str
    actor_id: str | None = None


def _action_from_row(row: EditActionRow) -> EditAction:
    """The record a row is."""
    return EditAction(
        edit_action_id=row.edit_action_id,
        feedback_id=row.feedback_id,
        version_edge_id=row.version_edge_id,
        actor_kind=row.actor_kind,
        actor_id=row.actor_id,
        grade=row.grade,
        created_at=row.created_at,
    )


def _material(context: ApplicationContext, version_id: str) -> CanonicalPath:
    """The material a version was made from, as a resource.

    :raises ApplicationRefusedError: the version names material the ledger
        does not hold.
    """
    relative_path = material_relative_path(context.store.session, version_id)
    if relative_path is None:
        raise chain_refused(
            ChainRefusal.SOURCE_NOT_FOUND,
            f"the manuscript version {version_id!r} names material the ledger does "
            "not hold. An edit is a change in a manuscript, and a change in a "
            "manuscript nobody holds is a change about nothing.",
        )
    return context.resource_for(relative_path)


def record_edit(
    context: ApplicationContext,
    *,
    edit_action_id: str,
    version_edge_id: str,
    actor_kind: str,
    feedback_id: str | None = None,
    actor_id: str | None = None,
    grade: str = "observed",
    now: datetime,
) -> EditAction:
    """Record a change made in answer to a comment.

    **The id is the caller's**, because identity cannot depend on
    insertion order: an edit is cited from a later run and from a
    decision record.

    **And the actor is what the caller says it is — and the vocabulary is
    closed.** A kind outside the four is a change nobody made, and a
    ``model`` row carrying a person's id is a model's change wearing
    somebody's name. Both are refused, here and by the schema.

    :raises ApplicationRefusedError: the edge or the comment is not
        there; the actor kind or the grade is outside its vocabulary; a
        model's row carries a person's id; or the policy denied reading
        the manuscript.
    """
    session = context.store.session
    edge = edge_row(session, version_edge_id)
    if edge is None:
        raise chain_refused(
            ChainRefusal.VERSION_NOT_FOUND,
            f"the store holds no version edge with the id {version_edge_id!r}. An "
            "edit names the edge it is -- the parent/child pair it moved -- and an "
            "edge that cannot exist is a reference to nothing.",
        )
    if actor_kind not in ACTOR_KINDS:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"{actor_kind!r} is not a kind of actor. An edit is made by a student, an "
            "advisor, a model or a person, and a change nobody made is not a change "
            "the chain can record.",
        )
    if grade not in EDIT_GRADES:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"{grade!r} is not a grade. A change is observed, inferred or confirmed "
            "by a person, and a grade outside those three says nothing about how the "
            "change is known.",
        )
    if actor_kind == "model" and actor_id is not None:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the edit {edit_action_id!r} names the model as its actor and also "
            f"names {actor_id!r}. A model is not a person, and a change that "
            "carries somebody's name is the forgery ADR-0016's third promotion path "
            "makes: the schema would be satisfied, the report would cite an "
            "address, and nothing would say the sentence was invented.",
        )
    if feedback_id is not None and feedback_row(session, feedback_id) is None:
        raise chain_refused(
            ChainRefusal.FEEDBACK_NOT_FOUND,
            f"the store holds no feedback event with the id {feedback_id!r}. An edit "
            "that answers a comment names it, and a comment nobody holds is a "
            "comment it cannot have answered.",
        )

    resources = [_material(context, edge.child_version_id)]
    if feedback_id is not None:
        feedback = feedback_row(session, feedback_id)
        assert feedback is not None  # checked above
        resources.append(_material(context, feedback.version_id))
    consent.evaluate_all(
        context,
        capability=CapabilityId.SOURCE_INVENTORY,
        arguments={},
        resources=tuple(resources),
    )

    existing = edit_row(session, edit_action_id)
    if existing is not None:
        return _action_from_row(existing)
    row = EditActionRow(
        edit_action_id=edit_action_id,
        feedback_id=feedback_id,
        version_edge_id=version_edge_id,
        actor_kind=actor_kind,
        actor_id=actor_id,
        grade=grade,
        created_at=now,
    )
    session.add(row)
    # **The row and the event land together**: an edit the stream cannot
    # show is a change the report's hash chain does not cover.
    with context.store.unit(context.task_id) as work:
        emit_edit_action_recorded(
            work,
            edit_action_id=edit_action_id,
            project_id=edge.project_id,
            version_edge_id=version_edge_id,
            actor_kind=actor_kind,
            feedback_id=feedback_id,
        )
    return _action_from_row(row)


def _edit_action_id(version_id: str, revision_event_id: str) -> str:
    """The id one recorded change takes, derived.

    **Derived, so recording the same manuscript twice is the same rows**
    and identity does not depend on insertion order — the rule the
    revision events' own ids follow, for the same reason.

    **And it names the change it is.** This table holds no text and no
    address of its own, so the id is what joins a row to the revision
    event it records — and a reader that wants to know what the change
    was, or whose name the file gives it, follows the id to the event.

    **The derivation is shared, not repeated.** The application layer
    also derives this id when an operator names a revision, so it lives
    in :func:`labcairn.papers.chain.edit_action_id_for` — one spelling,
    used by the side that writes and the side that reads.
    """
    del version_id  # The event's id is the change's; the version is the caller's check.
    return edit_action_id_for(revision_event_id)


def record_edits_from_revisions(
    context: ApplicationContext,
    *,
    project_id: str,
    version_id: str,
    version_edge_id: str,
    actors: Mapping[str, ActorClaim],
    answers: Mapping[str, str] | None = None,
    now: datetime,
) -> tuple[EditAction, ...]:
    """Record the changes a manuscript's file records, and who made each.

    **This is the step that fills the chain's second ring.** The reader
    has already read the file's tracked changes into ``revision_events``
    — each with its own text, its own address and **the name the file
    records** — and this operation turns them into the chain's own
    record: **one row per change, on the edge the change travelled, with
    the actor the operator's roster names.**

    **The roster is the operator's, and there is no default.** A name in
    a file is a string somebody typed; the same person is spelled two
    ways across two drafts, and a change a model drafted and a person
    pasted into Word carries that person's name. **So a name the roster
    does not name is refused** — the whole operation, before anything is
    written — and the refusal names the author. **The chain guesses
    nothing**, because a guess here is how a model's change becomes the
    advisor's.

    **And the file's name is never copied into the row.** The roster's
    ``actor_id`` is the operator's own handle for that person; the
    string the file carries is a lookup key and not an id, and the chain
    records kinds of actor and plain ids.

    **And the correspondence is the caller's.** ``answers`` names, by
    revision-event id, which comment each change answers. **The file
    does not say**, and a change that answers nothing is not an error —
    so a change the caller does not name a comment for is recorded with
    no comment, which is the state a student edits for reasons the
    advisor never wrote down.

    **And the correspondence cannot be added later.** The writer is
    insert-only — a second write with the same id returns the row that
    is there — so the comment a change answers is fixed when the change
    is recorded. **A recorded fact is not rewritten in place**, and a
    roster that contradicts a row already written is refused rather than
    silently ignored.

    **And a cursor left behind is not a change.** Word writes a
    revision with no children under a run's or a paragraph's properties
    when an operation at a point leaves one behind; it carries no
    judgement, and **the chain records changes and not marks**.

    **And nothing is written until everything is checked.** The whole
    plan — every change resolved to an actor, every answer checked
    against a comment the chain holds — is made before the first row is
    written, so a refusal leaves nothing behind.

    :raises ApplicationRefusedError: the project, the version, the edge
        or the comment is not there; the edge does not arrive at the
        version; the roster names a kind outside its vocabulary or a
        model carrying a person's id; a name in the file is not in the
        roster; an answer names a change or a comment the chain does
        not hold; or the policy denied reading the manuscript.
    """
    session = context.store.session
    if project_row(session, project_id) is None:
        raise chain_refused(
            ChainRefusal.PROJECT_NOT_FOUND,
            f"the store holds no paper project with the id {project_id!r}. A change "
            "belongs to a manuscript, and a change in a manuscript nobody holds is a "
            "change about nothing.",
        )
    version = version_row(session, version_id)
    if version is None:
        raise chain_refused(
            ChainRefusal.VERSION_NOT_FOUND,
            f"the store holds no manuscript version with the id {version_id!r}. A "
            "change is a change in a manuscript, and a change in a manuscript nobody "
            "holds is a change about nothing.",
        )
    if version.project_id != project_id:
        raise chain_refused(
            ChainRefusal.VERSION_NOT_FOUND,
            f"the manuscript version {version_id!r} belongs to the project "
            f"{version.project_id!r}, not to {project_id!r}. A change is recorded "
            "against the project its manuscript belongs to.",
        )
    edge = edge_row(session, version_edge_id)
    if edge is None:
        raise chain_refused(
            ChainRefusal.VERSION_NOT_FOUND,
            f"the store holds no version edge with the id {version_edge_id!r}. A "
            "change moves along an edge, and a change on an edge that cannot exist "
            "is a change about nothing.",
        )
    if edge.child_version_id != version_id:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the edge {version_edge_id!r} moves to the version "
            f"{edge.child_version_id!r} and not to {version_id!r}. A change is a "
            "change in the version the edge arrives at, and a change recorded "
            "against an edge it did not travel is a change on no edge at all.",
        )
    if edge.project_id != project_id:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the edge {version_edge_id!r} is in the project {edge.project_id!r} and "
            f"not in {project_id!r}. An edge across manuscripts is a claim about a "
            "lineage that does not exist.",
        )

    for name, claim in actors.items():
        if claim.actor_kind not in ACTOR_KINDS:
            raise ApplicationRefusedError(
                ApplicationRefusal.ARGUMENTS_INVALID,
                f"the roster says {name!r} is {claim.actor_kind!r}, and that is not a "
                "kind of actor. An edit is made by a student, an advisor, a model or "
                "a person, and a change nobody made is not a change the chain can "
                "record.",
            )
        if claim.actor_kind == "model" and claim.actor_id is not None:
            raise ApplicationRefusedError(
                ApplicationRefusal.ARGUMENTS_INVALID,
                f"the roster says {name!r} is a model and also names "
                f"{claim.actor_id!r}. A model is not a person, and a change that "
                "carries somebody's name is the forgery ADR-0016's third promotion "
                "path makes: the schema would be satisfied, the report would cite an "
                "address, and nothing would say the sentence was invented.",
            )

    correspondences = dict(answers or {})
    for revision_event_id, feedback_id in correspondences.items():
        stored = session.get(RevisionEventRow, revision_event_id)
        if stored is None or stored.version_id != version_id:
            raise ApplicationRefusedError(
                ApplicationRefusal.ARGUMENTS_INVALID,
                f"the answer names the change {revision_event_id!r}, which is not one "
                f"of the changes the version {version_id!r} records. An answer names "
                "a change the chain holds, and a change nobody holds cannot answer "
                "anything.",
            )
        comment = feedback_row(session, feedback_id)
        if comment is None:
            raise chain_refused(
                ChainRefusal.FEEDBACK_NOT_FOUND,
                f"the store holds no feedback event with the id {feedback_id!r}. A "
                "change that answers a comment names it, and a comment nobody holds "
                "is a comment it cannot have answered.",
            )
        if comment.project_id != project_id:
            raise ApplicationRefusedError(
                ApplicationRefusal.ARGUMENTS_INVALID,
                f"the comment {feedback_id!r} belongs to the project "
                f"{comment.project_id!r} and not to {project_id!r}. A change in this "
                "manuscript cannot answer a comment in another manuscript.",
            )

    events = record_revision_events(
        context,
        project_id=project_id,
        version_id=version_id,
        now=now,
    )

    plan: list[tuple[str, ActorClaim, str | None]] = []
    for change in events:
        if classify_revision_change(change.text, change.element_path) == EMPTY_MARKER:
            continue
        if change.author is None:
            raise ApplicationRefusedError(
                ApplicationRefusal.ARGUMENTS_INVALID,
                f"the change {change.revision_event_id!r} records no author. A change "
                "nobody made is not a change the chain can record, and a roster "
                "cannot name an author the file does not give.",
            )
        named = actors.get(change.author)
        if named is None:
            raise ApplicationRefusedError(
                ApplicationRefusal.ARGUMENTS_INVALID,
                f"the roster names no actor for {change.author!r}, and the change "
                f"{change.revision_event_id!r} is that author's. The chain does not "
                "guess who made a change: a default is how a model's change becomes "
                "the advisor's, and a name the roster does not name is a name "
                "somebody must be asked about.",
            )
        plan.append(
            (
                change.revision_event_id,
                named,
                correspondences.get(change.revision_event_id),
            )
        )

    # **A row already written is not rewritten in place**, and a roster
    # that contradicts it is refused rather than quietly ignored: the
    # chain would otherwise hold two stories about one change.
    for revision_event_id, named, comment_id in plan:
        existing = edit_row(session, _edit_action_id(version_id, revision_event_id))
        if existing is None:
            continue
        if existing.actor_kind != named.actor_kind or existing.actor_id != named.actor_id:
            raise ApplicationRefusedError(
                ApplicationRefusal.ARGUMENTS_INVALID,
                f"the change {revision_event_id!r} is already recorded as "
                f"{existing.actor_kind!r} {existing.actor_id!r} and the roster now "
                f"says {named.actor_kind!r} {named.actor_id!r}. A recorded change is "
                "not rewritten in place, and a roster that contradicts the record is "
                "a contradiction the chain will not carry.",
            )
        if existing.feedback_id != comment_id:
            raise ApplicationRefusedError(
                ApplicationRefusal.ARGUMENTS_INVALID,
                f"the change {revision_event_id!r} is already recorded against the "
                f"comment {existing.feedback_id!r} and the answer now names "
                f"{comment_id!r}. A recorded correspondence is not rewritten in "
                "place either, and a change may answer a further comment only "
                "through the judgement that links the two.",
            )
        if existing.version_edge_id != version_edge_id:
            raise ApplicationRefusedError(
                ApplicationRefusal.ARGUMENTS_INVALID,
                f"the change {revision_event_id!r} is already recorded on the edge "
                f"{existing.version_edge_id!r} and the roster now names the edge "
                f"{version_edge_id!r}. A change moves along one edge, and a change "
                "recorded against an edge it did not travel is a change on no edge "
                "at all.",
            )

    recorded: list[EditAction] = []
    for revision_event_id, named, comment_id in plan:
        recorded.append(
            record_edit(
                context,
                edit_action_id=_edit_action_id(version_id, revision_event_id),
                version_edge_id=version_edge_id,
                actor_kind=named.actor_kind,
                actor_id=named.actor_id,
                feedback_id=comment_id,
                grade="observed",
                now=now,
            )
        )
    return tuple(recorded)


def list_edit_actions(
    context: ApplicationContext,
    *,
    feedback_id: str | None = None,
    version_edge_id: str | None = None,
) -> tuple[EditAction, ...]:
    """The changes the chain holds, by comment or by edge.

    **Denied material is dropped, not refused** — ADR-0003 C5's rule for a
    bulk listing.

    :raises ApplicationRefusedError: the arguments are not usable.
    """
    session = context.store.session
    statement = select(EditActionRow).order_by(
        EditActionRow.created_at, EditActionRow.edit_action_id
    )
    if feedback_id is not None:
        statement = statement.where(EditActionRow.feedback_id == feedback_id)
    if version_edge_id is not None:
        statement = statement.where(EditActionRow.version_edge_id == version_edge_id)
    rows = tuple(session.scalars(statement))
    if not rows:
        return ()

    resources: list[CanonicalPath] = []
    for row in rows:
        edge = edge_row(session, row.version_edge_id)
        if edge is None:
            continue
        resources.append(_material(context, edge.child_version_id))
    permitted = consent.evaluate_each(
        context,
        capability=CapabilityId.SOURCE_INVENTORY,
        arguments={},
        resources=tuple(resources),
    )
    allowed = {resource.resolved_key for resource in permitted}
    kept = [
        row
        for row in rows
        if (edge := edge_row(session, row.version_edge_id)) is not None
        and _material(context, edge.child_version_id).resolved_key in allowed
    ]
    return tuple(_action_from_row(row) for row in kept)


__all__ = [
    "ACTOR_KINDS",
    "EDIT_GRADES",
    "EMPTY_MARKER",
    "ActorClaim",
    "EditAction",
    "list_edit_actions",
    "record_edit",
    "record_edits_from_revisions",
]
