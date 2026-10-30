"""The feedback chain's shared vocabulary, and the rows it is made of.

**What this module is.** LC-P2-09's four tables are one chain — *a question,
an edit, a response, and a later assessment* — and the three of them that
refuse something share the refusal vocabulary that lives here.

**Why the vocabulary is in its own module.** The chain's refusals are
translated into the application layer's names by
:data:`labcairn.application.refusal.CHAIN_REFUSALS`, and that table imports
this module. **If the vocabulary lived in :mod:`labcairn.papers.feedback`,
the import would run in a circle** — the feedback module raises the
application layer's refusal, and the application layer's refusal table
would import the feedback module's vocabulary. So the vocabulary sits
below both, in a module that imports nothing from the application layer.

**And the vocabulary is closed.** Every reason the chain can refuse has a
name in the application layer, and every name the application layer holds
for the chain is reached by one of these reasons. The witness is
``tests/test_feedback_events.py``.

**What the chain refuses, and why each refusal is a fact rather than a
convention.**

- **A row naming a thing that is not there.** A feedback event for a
  comment the store does not hold is a link to nothing.
- **A model writing a comment.** ADR-0016 names *model → accepted change*
  as a promotion path, and a row carrying a locator nobody read *is* the
  advisor being claimed to have said something.
- **A judgement with no evidence behind it.** A status anybody can set is
  not a status.
- **An assessment that rests on the acceptance of a change.** The change
  being accepted says the process went on; it does not say the advice was
  right, and the second needs its own evidence.
- **An issue key that was inferred.** The same wording is not the same
  issue, and a key is a person's judgement.
"""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from labcairn.db.models import (
    EditActionRow,
    FeedbackEventRow,
    PaperProjectRow,
    PaperVersionRow,
    VersionEdgeRow,
)
from labcairn.db.repository import load_source
from labcairn.sources.source import Source


class ChainRefusal(StrEnum):
    """Why the feedback chain said no.

    **Each one names what was wrong**, because a refusal that says only
    "no" is a refusal nobody can act on. They are the chain's own reasons,
    and :data:`labcairn.application.refusal.CHAIN_REFUSALS` gives each one
    the name a surface renders.
    """

    #: The store holds no paper project with that id.
    PROJECT_NOT_FOUND = "project_not_found"
    #: The store holds no manuscript version with that id.
    VERSION_NOT_FOUND = "version_not_found"
    #: The store holds no feedback event with that id.
    FEEDBACK_NOT_FOUND = "feedback_not_found"
    #: The store holds no edit action with that id.
    EDIT_NOT_FOUND = "edit_not_found"
    #: The version names material the ledger does not hold. A chain that
    #: points at a file nobody has is a chain about nothing.
    SOURCE_NOT_FOUND = "source_not_found"
    #: The material is there but could not be read. **Unreadable is not
    #: the same as empty**, and a comment in a file nobody can open is a
    #: comment the chain cannot claim to have found.
    MATERIAL_UNREADABLE = "material_unreadable"
    #: The file's bytes are not the bytes the version was made from. The
    #: version names a manuscript, and a manuscript that has changed under
    #: the name is not the one the coordinates would name.
    MATERIAL_DRIFTED = "material_drifted"
    #: The anchored text no longer hashes to what was recorded. The
    #: manuscript's bytes changed under the anchor, and the anchor is
    #: **stale** — reported as stale rather than silently re-pointed.
    ANCHOR_STALE = "anchor_stale"
    #: A model may not write a comment. **The row that holds a locator is
    #: the row the reader wrote**, and a model may not cause the system to
    #: claim the advisor said something.
    MODEL_MAY_NOT_WRITE_A_COMMENT = "model_may_not_write_a_comment"
    #: A response state other than ``pending`` was asked for with no
    #: evidence behind it.
    RESPONSE_NEEDS_EVIDENCE = "response_needs_evidence"
    #: A model may put a link forward, but it may not decide one. Only a
    #: rule or a person settles whether a change answered a comment.
    RESPONSE_MAY_NOT_BE_DECIDED_BY_A_MODEL = "response_may_not_be_decided_by_a_model"
    #: An assessment was asked for with no evidence of its own.
    ASSESSMENT_NEEDS_EVIDENCE = "assessment_needs_evidence"
    #: The assessment rests on something that is not evidence of the
    #: advice's correctness. **"The change was accepted" is one of those
    #: things.**
    ASSESSMENT_BASIS_REFUSED = "assessment_basis_refused"
    #: An issue key was asked to be derived rather than given. The same
    #: wording is not the same issue, and a recurrence is recorded rather
    #: than inferred.
    ISSUE_KEY_MAY_NOT_BE_INFERRED = "issue_key_may_not_be_inferred"


def project_row(session: Session, project_id: str) -> PaperProjectRow | None:
    """The paper project row, or ``None`` when the store holds no such row."""
    return session.get(PaperProjectRow, project_id)


def version_row(session: Session, version_id: str) -> PaperVersionRow | None:
    """The manuscript version row, or ``None`` when there is no such row."""
    return session.get(PaperVersionRow, version_id)


def feedback_row(session: Session, feedback_id: str) -> FeedbackEventRow | None:
    """The feedback event row, or ``None`` when there is no such row."""
    return session.get(FeedbackEventRow, feedback_id)


def edit_row(session: Session, edit_action_id: str) -> EditActionRow | None:
    """The edit action row, or ``None`` when there is no such row."""
    return session.get(EditActionRow, edit_action_id)


def edge_row(session: Session, edge_id: str) -> VersionEdgeRow | None:
    """The version edge row, or ``None`` when there is no such row."""
    return session.get(VersionEdgeRow, edge_id)


def feedback_rows_for_issue(
    session: Session, project_id: str, issue_key: str
) -> tuple[FeedbackEventRow, ...]:
    """The feedback rows of a project that carry an issue key.

    **Ordered by the version they were written against and then by their
    id**, so a recurrence reads in the order the rounds happened.
    """
    return tuple(
        session.scalars(
            select(FeedbackEventRow)
            .where(FeedbackEventRow.project_id == project_id)
            .where(FeedbackEventRow.issue_key == issue_key)
            .order_by(FeedbackEventRow.version_id, FeedbackEventRow.feedback_id)
        )
    )


def project_version_rows(session: Session, project_id: str) -> tuple[PaperVersionRow, ...]:
    """The manuscript versions of a project, in a stable order.

    **Ordered by id, not by insertion.** A listing that came back in a
    different order on a second run would be a listing nobody could
    compare with the first.
    """
    return tuple(
        session.scalars(
            select(PaperVersionRow)
            .where(PaperVersionRow.project_id == project_id)
            .order_by(PaperVersionRow.version_id)
        )
    )


def material_source(session: Session, version_id: str) -> Source | None:
    """The ledger's row for the material a version was made from.

    ``None`` when the version is not there, or when it names material the
    ledger does not hold. **The source carries the hash of the bytes the
    version was ingested from**, which is what makes a drifted manuscript
    detectable rather than merely different.
    """
    version = version_row(session, version_id)
    if version is None:
        return None
    return load_source(session, version.source_id)


def material_relative_path(session: Session, version_id: str) -> str | None:
    """The workspace-relative path of the material a version was made from.

    ``None`` when the version is not there, or when it names material the
    ledger does not hold. **The path is the workspace-relative spelling**,
    which is what :meth:`~labcairn.application.context.ApplicationContext.resource_for`
    resolves.
    """
    source = material_source(session, version_id)
    return None if source is None else source.relative_path


__all__ = [
    "ChainRefusal",
    "edge_row",
    "edit_row",
    "feedback_row",
    "feedback_rows_for_issue",
    "material_relative_path",
    "material_source",
    "project_row",
    "project_version_rows",
    "version_row",
]
