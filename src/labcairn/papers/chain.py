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
from typing import Final

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
    #: The store holds no reply with that id. A settlement judges an
    #: exchange, and a settlement of an exchange nobody holds is a
    #: settlement about nothing.
    REPLY_NOT_FOUND = "reply_not_found"
    #: A settlement state other than ``pending`` was asked for with no
    #: evidence behind it.
    SETTLEMENT_NEEDS_EVIDENCE = "settlement_needs_evidence"
    #: A model may put a settlement forward, but it may not decide one.
    #: Only a rule or a person settles whether an answer settled a point.
    SETTLEMENT_MAY_NOT_BE_DECIDED_BY_A_MODEL = "settlement_may_not_be_decided_by_a_model"
    #: A reply that has already been judged was judged again. A judgement
    #: is a fact, and a second judgement over the same reply is a revision
    #: of a fact, which the store does not hold.
    SETTLEMENT_ALREADY_DECIDED = "settlement_already_decided"
    #: A settlement claimed a reply settled because the manuscript holds
    #: what the answer claims, and the claimed thing is not in the
    #: manuscript's accepted text. **Refused by name, never silently
    #: accepted** -- the refusal says which term was not found.
    CLAIM_NOT_IN_MANUSCRIPT = "claim_not_in_manuscript"


def edit_action_id_for(revision_event_id: str) -> str:
    """The id one recorded change takes, derived from the event it records.

    **It lives here, and not in the writer, because both sides need it.**
    ``labcairn.papers.edits`` mints it when the row is written, and the
    application layer derives it when it is asked for the change behind a
    revision an operator names. **A second spelling of the derivation is
    a second address for one row**, and the two would drift apart
    silently — the write would succeed and the read would find nothing.

    The derivation is the event's own id, because ``revision_events``
    already mints that from the version and the element's path (recorded
    twice, the same rows are found), and an edit is the same change
    said in the chain's own vocabulary.
    """
    return f"ea-{revision_event_id}"


#: The prefix the ids of ``revision_events`` carry. **It is the prefix
#: the product's own derivation gives them**, and it is recorded here
#: because a revision source's key is one of those ids.
#:
#: **It is not a namespace, and nothing may be decided by it.** A
#: comment's issue key is a person's judgement and may be spelled any
#: way at all — including with this prefix — so **a key that starts with
#: it is not thereby a revision.** The chain tells the two apart by
#: looking them up, not by reading their spelling, and a rule that
#: decided a key's kind from its first letters would be a rule that
#: guessed (ADR-0017 C10).
REVISION_SOURCE_PREFIX: Final[str] = "rv-"


def revision_source_key(revision_event_id: str) -> str:
    """The key one revision case is filed under, minted by the product.

    **The product mints it, and nobody else may.** A comment's issue key
    is a person's judgement about what the same problem is (ADR-0017
    C10), so it is given and never derived. **A revision has no such
    judgement to give**: a tracked change is a fact about a file, and its
    address already names it. So the key is *derived* — from the
    revision event's own id, which is itself derived from the version and
    the element's path — and a caller that wants a revision case names
    the revision, never the key.

    **And the derivation is here, beside :func:`edit_action_id_for`,
    because the two are the same kind of thing.** Both are addresses the
    product derives from an address the chain already has, and a second
    spelling of either is a second name for one row.

    **And the key *is* the revision event's id.** The revision events'
    own ids already carry :data:`REVISION_SOURCE_PREFIX`, so prefixing
    them again would spell the same address twice. **The chain holds the
    event under that id**, and a reader who follows the key finds the
    change itself — **which is what makes the key traceable**.
    """
    return revision_event_id


def is_revision_source_key(key: str) -> bool:
    """Whether *key* **spells** like a revision id.

    **It is a spelling test and not a kind test, and it decides
    nothing.** A comment's issue key is a person's judgement and may be
    spelled any way at all, so this function cannot tell the two apart —
    it says only what a key *looks* like. **The chain tells them apart
    by looking them up**: a key the chain holds a revision under is a
    revision's, and a key it holds a comment under is a comment's.

    **It exists for the reader's benefit, and the reader must not trust
    it alone.** A key spelled like a revision that the chain holds no
    revision under is a key the chain holds nothing under, and it dies
    as one.
    """
    return key.startswith(REVISION_SOURCE_PREFIX)


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


#: The four kinds of change a tracked revision can record.
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
    the address is what tells them apart. This is why this rule reads
    the address and not only the text, and why the empty marker must
    never be counted as a change.

    **And it lives here, and not in the read layer, because both sides
    need it.** The chain's own writer asks it when it records a change as
    the chain's, and the layer's read asks it when it counts a marked-up
    manuscript's activity — and a rule the two sides spelled separately
    is a rule that can drift. **This module imports nothing from the
    application layer**, so it sits below both of them and is imported by
    both.

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


__all__ = [
    "REVISION_CHANGE_KINDS",
    "REVISION_SOURCE_PREFIX",
    "ChainRefusal",
    "classify_revision_change",
    "edge_row",
    "edit_action_id_for",
    "edit_row",
    "feedback_row",
    "feedback_rows_for_issue",
    "is_revision_source_key",
    "material_relative_path",
    "material_source",
    "project_row",
    "project_version_rows",
    "revision_source_key",
    "version_row",
]
