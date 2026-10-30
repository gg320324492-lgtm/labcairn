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
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from labcairn.application import consent
from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError, chain_refused
from labcairn.db.models import EditActionRow
from labcairn.papers.chain import (
    ChainRefusal,
    edge_row,
    edit_row,
    feedback_row,
    material_relative_path,
)
from labcairn.security.capabilities import CapabilityId
from labcairn.security.paths import CanonicalPath

#: Who made a change. **Four, and the fourth is the one the design is
#: about.**
ACTOR_KINDS: frozenset[str] = frozenset({"student", "advisor", "model", "human"})

#: The grades an edit may carry — ADR-0014 D2's three levels.
EDIT_GRADES: frozenset[str] = frozenset({"observed", "inferred", "human_verified"})


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
    session.commit()
    return _action_from_row(row)


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
    "EditAction",
    "list_edit_actions",
    "record_edit",
]
