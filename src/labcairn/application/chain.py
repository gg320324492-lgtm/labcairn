"""The feedback chain's own facts, read through the layer.

**What this module is.** The mentor line reads the chain's rows — the
comments the advisor wrote, the changes that were made, the judgements on
them, the versions and the accepted edges between them, the tracked
changes a marked-up manuscript records, and the exchanges a response
document holds — and it used to read them by importing
``labcairn.db.models`` and writing its own ``select(...)`` statements.
**That is the arrangement the application layer exists to prevent**: a
reader that reaches the store directly is a reader the capability model
does not reach, and a guard applied to an operation would apply to some of
the callers and not the others.

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

**And the replies are read here too, because they are read beside the
comments — and because they are not the chain's own.** The ``replies``
table holds a *reviewer's* objection and *the authors'* answer, read out
of a response document: **the paper's own review history, and neither the
mentor's exchange nor the student's.** So the chain's keys, its
judgements and its issue keys do not reach a reply, and :func:`read_replies`
is a read of what two parties said rather than a verdict on anything.

**And the six write doors are operations of the layer too.** The comment a
chain holds was written by :func:`record_feedback`, the change by
:func:`record_edit`, the tracked changes by :func:`record_revision_events`,
the judgement on a comment by :func:`record_response`, the judgement on an
exchange by :func:`settle_reply`, and the later assessment by
:func:`record_assessment`. Those functions lived in :mod:`labcairn.papers`
and the layer did not hold them, so a caller wrote to the chain by reaching
past the layer into the domain package -- and **a chain the layer cannot
write is a chain whose consent accounting depends on who thought to call
which module**. Each operation here is thin: it delegates to the domain
function it names, and the domain function's own `consent` call is what the
capability table row is read from. The `source.read` doors ask permission on
the manuscript they read; the `source.inventory` doors ask it on the
materials their rows are drawn from. :func:`settle_reply` is the one
operation whose permission is conditional: it asks nothing when the
settlement is pending or its anchor is unknown, and asks `source.read` on
the manuscript when it resolves an address there.

**What these operations return.** Rows are not returned; the chain's own
facts are. A caller wants *a comment* — the advisor's words, the anchored
text, the version it was written against — and not a row it has to know the
shape of. The same is true of a change and of an accepted edge.

**What these operations refuse.** Almost nothing, beyond what the store
itself refuses: a row that is not there is reported as an empty answer, and
the *rule* that says what may be done with what was found is the caller's —
:mod:`labcairn.guidance.retrieval` and :mod:`labcairn.roles.trajectory`
hold those rules, and they ask the permission layer themselves where the
material is named.

**The one exception is the issue-key listing, and it refuses two things.**
:func:`read_issue_keys` answers *which issues there are to look at*, and an
answer about a chain that is not the one asked for is an answer about
something else: **a project the chain does not hold, and a version that does
not belong to it, are refused by name** rather than answered about
silently. The rest of the module's operations report what they did not find
as an empty answer, and this one refuses because its answer is a *list of
what there is* — an empty list for a project nobody holds would be a
statement that the project has no issues, and that is a different fact from
"there is no such project".

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
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import ApplicationRefusedError, chain_refused
from labcairn.db.models import (
    EditActionRow,
    FeedbackEventRow,
    PaperVersionRow,
    ReplyRow,
    ResponseLinkRow,
    RevisionEventRow,
    VersionEdgeRow,
)
from labcairn.db.repository import load_source
from labcairn.papers.chain import (
    REVISION_CHANGE_KINDS,
    ChainRefusal,
    classify_revision_change,
    edit_action_id_for,
    project_row,
    project_version_rows,
    revision_source_key,
)

if TYPE_CHECKING:
    # **Only for the annotations below, and only because of the cycle.** The
    # writers at :mod:`labcairn.papers.feedback` and its siblings import
    # ``labcairn.application.consent`` at their top, and this module is loaded
    # by this package's aggregator: a runtime import of them here is the edge
    # the comment above :class:`ChainComment` records, and it breaks in the one
    # order that a process imports the writer first. The annotation is a string
    # -- ``from __future__ import annotations`` is in force -- so the name is
    # needed for the reader and the type checker, and not at call time.
    from labcairn.papers.assessments import FollowupAssessment
    from labcairn.papers.edits import EditAction
    from labcairn.papers.feedback import FeedbackEvent
    from labcairn.papers.replies import ReplySettlement
    from labcairn.papers.responses import ResponseLink
    from labcairn.papers.revisions import RevisionRecord

# **Not `from labcairn.papers.revisions import read_paragraph_context`.** That
# name is reached for here, at line ~714, and only there — and a module-level
# import of it closes a cycle that breaks in exactly one order. A process that
# imports the writer first runs its `from labcairn.application import consent`,
# which runs this package's aggregator, which imports this module, which asks
# the half-initialised writer for a name its body has not bound yet:
# `ImportError: cannot import name 'read_paragraph_context' from partially
# initialized module`. Every other order works, which is what made it
# invisible: the suite collects a file that imports the layer first, and the
# writer is then already loaded. The same remedy as
# :mod:`labcairn.analysis.chart.recipe`, and the same reason for it — the edge
# is needed at **call** time, not at load time.
# `tests/test_application_layer.py` holds the witness: every first-party module
# is imported first, alone, in a fresh process.


@dataclass(frozen=True)
class ChainComment:
    """One comment, as the chain holds it.

    **The words and the anchor travel together.** A role may not put
    words in the advisor's mouth, so the quote a role proposes is checked
    against the very comment it points at — and the anchored text is what
    the scope of a distilled rule is built from.

    **And the anchor's status travels with them, because the text alone
    does not say where the comment sits.** A comment the reader could not
    place in the body carries no anchored text, and neither does a comment
    the reader *did* place on a stretch of the manuscript that holds no
    text. **Those are two different facts**: the first is a remark the
    reader could not attach to anything, the second is a remark about a
    place the reader found and that is empty.

    **So the layer carries the status and the reason, and a caller can
    ask.** A caller that cannot tell the two apart will say something
    false about the case — and the scope of a distilled rule that quotes
    the empty string as though it were the advisor's words is exactly
    that. The reason is the chain's own, carried through so a caller may
    name it rather than invent one.
    """

    feedback_id: str
    #: The chain's own key for the issue the comment is about. **Not
    #: ``None``**: a comment is only here because it was asked for by key.
    issue_key: str
    #: The manuscript state the comment was written against.
    version_id: str
    comment_text: str
    #: The text the comment was written against. **``None`` when the
    #: anchor covers no text** -- a comment the reader could not place, or
    #: one the reader placed on a position that holds no words -- which is
    #: why the status below is here. Rows written while the schema forced
    #: an empty string onto every anchor read as ``""`` here; both spell
    #: the one fact, and neither is ever quoted as the advisor's words.
    anchor_text: str | None
    #: ``"resolved"``, ``"unknown"`` or ``"position"``.
    anchor_status: str
    #: Why the anchor is unknown, or ``None`` when it resolved or was
    #: placed on a position. **The chain's own reason**, so a caller may
    #: name it.
    anchor_reason: str | None


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
class ChainReply:
    """One exchange read out of a document: an objection and the answer to it.

    **Both halves and both parties travel together.** A reader asking what
    the authors said in answer to a reviewer wants the objection, the
    answer and who said which — and the answer is the half that carries
    the reasoning, so a row that kept only the objection would be half an
    answer to the question.

    **And the address is the reader's own.** The paragraph is where the
    half was read in the document the version names — the response
    document, **not** the manuscript under review, which the material
    does not have. A reply carries no address into that manuscript, and
    the place the objection points at lives in the objection's own words.
    """

    reply_id: str
    #: The document the exchange was read from.
    version_id: str
    #: ``reviewer`` or ``author`` — **the reply's own vocabulary**, and
    #: not the chain's ``actor_kind``, which cannot say what a peer
    #: reviewer and the authors of a submitted paper are.
    objection_party: str
    objection_text: str
    #: Where in the document the objection was read.
    objection_paragraph: int
    #: ``reviewer`` or ``author``.
    answer_party: str
    answer_text: str
    #: Where in the document the answer was read.
    answer_paragraph: int
    #: How the pairing was established: ``observed``, ``inferred`` or
    #: ``human_verified``.
    pairing_grade: str


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


# **The four kinds of change a stored revision event can record, and the
# rule that tells them apart, live in :mod:`labcairn.papers.chain`** — below
# both this layer and the chain's own writer — and they are imported here
# rather than spelled a second time: the layer counts a marked-up
# manuscript's activity with them and the chain's writer records a change
# with them, and a rule the two sides spelled separately is a rule that can
# drift. **The empty marker is not a change**, and it must never be
# counted as one.


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
class ChainRevisionSource:
    """One revision case, as the chain holds it: the change and its place.

    **A revision case is a change and the paragraph it sits in.** The
    change's own words are what the reviewer wrote, and the paragraph is
    where they wrote them — **and the paragraph is what makes the words
    checkable**, the same way a comment's anchored text does for a comment
    case. A change with no paragraph to sit in is a change with no
    context, and a scope that quoted nothing would be a scope that
    claimed the reviewer wrote about nothing.

    **And the actor travels with it.** A change is a change *somebody
    made*, and the chain records who: ``actor_kind`` is the kind of actor
    and ``actor_id`` the operator's handle for them, or ``None`` for a
    model, which has no id (ADR-0016). **A revision case whose actor is
    a model is not the advisor's advice**, and a rule distilled from it
    says so rather than borrowing the advisor's name.
    """

    #: The key the product minted for this case. **Not a parameter**: it
    #: is derived from the revision event's own id.
    source_key: str
    #: The revision event the case is.
    revision_event_id: str
    #: The manuscript version whose document carries the change.
    version_id: str
    #: ``ins``, ``del``, ``moveFrom`` or ``moveTo``.
    kind: str
    #: **What kind of change this is** — one of
    #: :data:`REVISION_CHANGE_KINDS`.
    change_kind: str
    #: The inserted or the deleted text. **Empty is a real value.**
    text: str
    #: The paragraph the change sits in, and the text of that paragraph
    #: **as the change's own view reads it**: an insertion belongs to the
    #: accepted text, a deletion to the rejected text. **Empty when the
    #: paragraph holds no such text**, and then the scope says so.
    paragraph: int | None
    paragraph_text: str
    #: Who made it, and of what kind. **``None`` for a model**, which has
    #: no id.
    actor_kind: str | None
    actor_id: str | None
    #: The edit action the chain recorded for this change.
    edit_action_id: str | None


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

    **And the anchor's status comes with the comment**, so that a caller
    may tell a remark the advisor's words sit at some text from one the
    reader could not place in the body at all.

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
            anchor_status=row.anchor_status,
            anchor_reason=row.anchor_reason,
        )
        for row in rows
    )


def read_issue_keys(
    context: ApplicationContext, *, project_id: str, version_ids: Sequence[str] = ()
) -> tuple[str, ...]:
    """The issue keys the chain holds for a project.

    **Which keys.** The keys the chain's own rows carry. **A key is a
    person's judgement and it is given, never derived** — the same wording
    is not the same issue — so a comment nobody keyed is *uncategorised*:
    it is not in this list, and it is not keyed by similarity to one that
    is. **A key nobody has given is not in the chain**, and so it is not in
    this list either: the chain's rows are the only source, and a key that
    lives in some other table is a name about the chain, not a key of it.

    **How the list is ordered.** **Sorted, and sorted because the chain's
    rows carry no time and no sequence.** There is no chronology in the
    chain to read an order out of, so an order taken from the rows would
    be the *storage engine's* and not the chain's — and the same chain
    would then be two lists. **Sorting is an order of the names
    themselves**: the same set of keys answers the same list, on every
    machine, however the rows happened to come back. A reader that draws
    the list twice draws the same thing.

    **What it refuses.** **A project the chain does not hold**, and **a
    version that does not belong to it**. The second is refused rather
    than ignored: a version outside the project would widen the answer to
    a chain that is not this one, and the caller who named it would be
    answered about something else without being told.

    **What the list carries, and what it does not.** **The keys, and
    nothing else.** A key says *which problem*, not *what the advisor
    wrote*: no comment's words, no anchored text, no author, no date and
    no grade travel with it. The layer's own comment — which does carry
    them — is a different answer to a different question, and a caller
    that wants the words asks for the comments under the key.

    :param project_id: the project whose chain is read.
    :param version_ids: the versions to narrow the answer to. **Naming
        none means the whole project** — every version of it. Blanks name
        nothing, as they do everywhere else in this module.
    :raises ApplicationRefusedError: the chain holds no such project, or
        one of the versions named does not belong to it.
    """
    session = context.store.session
    if project_row(session, project_id) is None:
        raise chain_refused(
            ChainRefusal.PROJECT_NOT_FOUND,
            f"the store holds no paper project with the id {project_id!r}, so the chain "
            "holds no issue key for it.",
        )
    named = _the_versions_named(session, project_id, version_ids)
    conditions = [
        FeedbackEventRow.project_id == project_id,
    ]
    if named is not None:
        conditions.append(FeedbackEventRow.version_id.in_(named))
    keys = {
        str(key)
        for key in session.scalars(select(FeedbackEventRow.issue_key).where(*conditions))
        if key
    }
    return tuple(sorted(keys))


def _the_versions_named(
    session: Session, project_id: str, version_ids: Sequence[str]
) -> tuple[str, ...] | None:
    """The versions the issue-key answer is about, or ``None`` for all of them.

    **The versions named narrow the answer, and they must belong to the
    project.** Naming none means the project's whole chain, which is the
    one scope a caller reaches before it knows which versions it wants.

    :raises ApplicationRefusedError: a version named does not belong to the
        project.
    """
    wanted = tuple(dict.fromkeys(version_id for version_id in version_ids if version_id))
    if not wanted:
        return None
    held = {row.version_id for row in project_version_rows(session, project_id)}
    outside = tuple(version_id for version_id in wanted if version_id not in held)
    if outside:
        raise chain_refused(
            ChainRefusal.VERSION_NOT_FOUND,
            f"the project {project_id!r} holds no version with the id {outside[0]!r}, so the "
            "issue keys of that version are not the issue keys of this chain.",
        )
    return wanted


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


def read_revision_sources(
    context: ApplicationContext, *, revision_event_ids: Sequence[str]
) -> tuple[ChainRevisionSource, ...]:
    """The revision cases the chain holds, each with its key and its place.

    **The caller names the revision, and the key is the product's.**
    The caller passes the chain's own address for a change — the
    revision event's id — and this read mints the key the case is filed
    under. **A caller cannot hand in a key**, because a key that a caller
    wrote is a key nobody can check: it would name a case the chain may
    not hold, and the rule would be bound to material that does not
    exist.

    **And a revision nobody holds is absent here, not invented.** The
    read returns only the changes the chain records, so a caller that
    names an id the chain does not hold learns that by the empty answer
    — and the distillation refuses a rule with no case behind it.

    **The actor travels with the case.** A change is a change somebody
    made, and the chain recorded who: the edit action carries the actor
    the operator's roster named. **A change with no edit action has no
    actor**, and a case with no actor says so rather than borrowing one.

    **And the paragraph is read in the view the change sits in.** An
    insertion belongs to the accepted text and a deletion to the rejected
    one, so the context is read through
    :func:`labcairn.papers.revisions.read_paragraph_context` or its
    rejected counterpart, and the case carries the text of the paragraph
    the change was written into.
    """
    ids = tuple(dict.fromkeys(event_id for event_id in revision_event_ids if event_id))
    if not ids:
        return ()
    session = context.store.session
    rows = session.scalars(
        select(RevisionEventRow).where(RevisionEventRow.revision_event_id.in_(ids))
    ).all()
    if not rows:
        return ()

    # **The actor comes from the chain's own record of the change.**
    # The edit action's id is derived from the revision event's, so the
    # one is found from the other — and a change with no edit action has
    # no actor, which the case says rather than guesses.
    edits = {
        row.edit_action_id: row
        for row in session.scalars(
            select(EditActionRow).where(
                EditActionRow.edit_action_id.in_(
                    tuple(edit_action_id_for(event_id) for event_id in ids)
                )
            )
        )
    }

    # **The paragraphs are read once per version, not once per change.**
    # A marked-up manuscript holds hundreds of changes in a handful of
    # paragraphs, and the paragraph is read out of the **document** —
    # so a read that opened the file per change would parse the same
    # manuscript hundreds of times. **The file is read once per version
    # and per view, and the changes in it are looked up afterwards.**
    paragraphs = _the_paragraph_texts(context, rows)

    found: list[ChainRevisionSource] = []
    for row in rows:
        edit = edits.get(edit_action_id_for(row.revision_event_id))
        found.append(
            ChainRevisionSource(
                source_key=revision_source_key(row.revision_event_id),
                revision_event_id=row.revision_event_id,
                version_id=row.version_id,
                kind=row.kind,
                change_kind=classify_revision_change(row.text, row.element_path),
                text=row.text,
                paragraph=row.paragraph,
                paragraph_text=(
                    paragraphs.get((row.version_id, row.view, row.paragraph), "")
                    if row.paragraph is not None
                    else ""
                ),
                actor_kind=edit.actor_kind if edit is not None else None,
                actor_id=edit.actor_id if edit is not None else None,
                edit_action_id=edit.edit_action_id if edit is not None else None,
            )
        )
    return tuple(found)


def _the_paragraph_texts(
    context: ApplicationContext, rows: Sequence[RevisionEventRow]
) -> Mapping[tuple[str, str | None, int], str]:
    """The text of every paragraph a change sits in, read once per file.

    **Keyed by the version, the view and the paragraph** — the three
    facts that name a paragraph's text. **A version is read once for the
    accepted view and once for the rejected one**, because the two views
    are two different manuscripts (ADR-0014 D4a).

    **And a version that cannot be read is absent, not empty.** The
    caller says so in the scope; the empty string is never quoted as
    the reviewer's surroundings.

    **And the paragraph readers are imported here, not at the top of this
    module** — the module comment above :func:`read_revision_sources` says
    why: the top-level import closes a cycle that fails only when the writer
    is the first module a process loads.
    """
    from labcairn.papers.revisions import (
        read_paragraph_context,
        read_rejected_paragraph_context,
    )

    wanted: dict[tuple[str, str | None], set[int]] = {}
    for row in rows:
        if row.paragraph is None:
            continue
        wanted.setdefault((row.version_id, row.view), set()).add(row.paragraph)

    texts: dict[tuple[str, str | None, int], str] = {}
    for (version_id, view), paragraphs in wanted.items():
        try:
            if view == "rejected":
                read = read_rejected_paragraph_context(
                    context, version_id=version_id, paragraphs=tuple(sorted(paragraphs))
                )
            else:
                read = read_paragraph_context(
                    context, version_id=version_id, paragraphs=tuple(sorted(paragraphs))
                )
        except ApplicationRefusedError:
            continue
        for paragraph, text in read.items():
            texts[(version_id, view, paragraph)] = text
    return texts


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


def read_replies(
    context: ApplicationContext, *, version_ids: Sequence[str]
) -> tuple[ChainReply, ...]:
    """The exchanges read out of the documents the chain holds.

    **A reply is a record of what was said, and this read returns both
    halves.** The objection and the answer travel together, and so do the
    parties that wrote them: a caller that wanted only the objection
    would throw away the half that carries the reasoning.

    **A version nobody holds an exchange for is simply not among them.**
    The exchanges are read by the version they were read from, and a
    version with none is a version whose document holds none.

    **And they come back in the document's order.** The exchanges are
    ordered by the paragraph the objection was read from and then by the
    paragraph the answer was read from, which is the order a person
    reading the response document would meet them in -- and the same
    answer on every machine, however the rows happened to come back.
    **The second key is not decoration**: two exchanges may answer the
    same objection, and an order that stopped at the objection would
    leave their order to the storage engine's.

    **And the reply is not the mentor's exchange**, so the chain's own
    keys and judgements do not reach it: a reply is a reviewer's
    objection and the authors' answer, read out of a response document,
    and it is a record of what was said rather than a verdict on
    anything.

    **And the permission is asked where the material is named**, as this
    module's rule says: the exchanges carry the reviewer's and the
    authors' own words, so the caller asks about the material through
    :func:`read_material_paths` before it shows any of them.
    """
    ids = tuple(version_id for version_id in version_ids if version_id)
    if not ids:
        return ()
    rows = context.store.session.scalars(
        select(ReplyRow)
        .where(ReplyRow.version_id.in_(ids))
        .order_by(ReplyRow.version_id, ReplyRow.objection_paragraph, ReplyRow.answer_paragraph)
    ).all()
    return tuple(
        ChainReply(
            reply_id=row.reply_id,
            version_id=row.version_id,
            objection_party=row.objection_party,
            objection_text=row.objection_text,
            objection_paragraph=row.objection_paragraph,
            answer_party=row.answer_party,
            answer_text=row.answer_text,
            answer_paragraph=row.answer_paragraph,
            pairing_grade=row.pairing_grade,
        )
        for row in rows
    )


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


# --------------------------------------------------------------------------- #
# the chain's write doors
# --------------------------------------------------------------------------- #

# **Every writer here imports its domain function inside the body, not at the
# top of the module.** The reason is the one :class:`ChainComment` records: the
# writers at :mod:`labcairn.papers.feedback` and its siblings ask
# ``from labcairn.application import consent`` at their top, and this module is
# loaded by this package's aggregator. A module-level import of the writer from
# here closes that edge, and it breaks in exactly one order -- a process whose
# first import is the writer asks this half-initialised module for a name its
# body has not bound yet. ``tests/test_application_layer.py`` holds the witness
# that settles it: every first-party module is imported first, alone, in a
# fresh process.


def record_feedback(
    context: ApplicationContext,
    *,
    project_id: str,
    version_id: str,
    now: datetime,
) -> tuple[FeedbackEvent, ...]:
    """Record the comments one version's manuscript holds.

    **The door is the layer's, the writing is the domain's.** This operation
    delegates to :func:`labcairn.papers.feedback.record_feedback` and changes
    nothing about it: the ids, the anchor check, the refusal of a stale anchor
    and the trajectory event are all made there. What the door adds is that a
    surface cannot reach it except through the layer.

    **And the permission it answers to is** ``source.read`` **on the manuscript
    the version was made from**, asked by that function's own
    ``consent.evaluate(context, capability=CapabilityId.SOURCE_READ, ...)`` —
    so a policy that denies the read denies the write, on this path as on any
    other.

    :raises ApplicationRefusedError: the project or the version is not there,
        the material is missing, unreadable or drifted, the policy denied the
        read, or an anchor no longer matches the text it was set in.
    """
    from labcairn.papers.feedback import record_feedback as _record_feedback

    return _record_feedback(context, project_id=project_id, version_id=version_id, now=now)


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
    """Record the change made in answer to a comment.

    **The id is the caller's, and the edge is the change's path.** A change is
    recorded against the edge it moved along, and the row says who made it --
    a person, or a model whose inference may not carry a name.

    **And the permission it answers to is** ``source.inventory`` **on the
    materials the row is drawn from**, asked by
    :func:`labcairn.papers.edits.record_edit`'s own
    ``consent.evaluate_all(context, capability=CapabilityId.SOURCE_INVENTORY,
    ...)`` over the child version's material and the comment's.

    :raises ApplicationRefusedError: the edge or the comment is not there, the
        actor kind or the grade is outside its vocabulary, a model is named as
        a person, or the policy denied the inventory.
    """
    from labcairn.papers.edits import record_edit as _record_edit

    return _record_edit(
        context,
        edit_action_id=edit_action_id,
        version_edge_id=version_edge_id,
        actor_kind=actor_kind,
        feedback_id=feedback_id,
        actor_id=actor_id,
        grade=grade,
        now=now,
    )


def record_revision_events(
    context: ApplicationContext,
    *,
    project_id: str,
    version_id: str,
    now: datetime,
) -> tuple[RevisionRecord, ...]:
    """Record the tracked changes a marked-up manuscript holds.

    **The rows say what changed and not why, because the file says not why.**
    A second reading of the same bytes finds the same rows: the ids are
    derived from the version and the change, not from the moment.

    **And the permission it answers to is** ``source.read`` **on the manuscript
    the version was made from**, asked by
    :func:`labcairn.papers.revisions.record_revision_events`'s own
    ``consent.evaluate(context, capability=CapabilityId.SOURCE_READ, ...)``.

    :raises ApplicationRefusedError: the project or the version is not there,
        the material is missing, unreadable or drifted, the policy denied the
        read, or an anchor no longer matches the text it was set in.
    """
    from labcairn.papers.revisions import record_revision_events as _record_revision_events

    return _record_revision_events(context, project_id=project_id, version_id=version_id, now=now)


def record_response(
    context: ApplicationContext,
    *,
    response_link_id: str,
    feedback_id: str,
    edit_action_id: str,
    state: str,
    grade: str = "observed",
    decided_by: str | None = None,
    decided_at: datetime | None = None,
    evidence_refs: tuple[str, ...] = (),
    now: datetime,
) -> ResponseLink:
    """Record the judgement of whether a change answered a comment.

    **A state other than** ``pending`` **needs a decider and evidence, and a
    model may not decide one.** That is the same line the acceptance of a
    change may not cross: the answer to *"did it address the comment"* is a
    person's, or it is nobody's.

    **And the permission it answers to is** ``source.inventory`` **on the
    material the comment was written against**, asked by
    :func:`labcairn.papers.responses.record_response`'s own
    ``consent.evaluate_all(context, capability=CapabilityId.SOURCE_INVENTORY,
    ...)``.

    :raises ApplicationRefusedError: the comment or the change is not there,
        the state, the grade or the decider is outside its vocabulary, a
        decision is claimed without its evidence, a model decides it, or the
        policy denied the inventory.
    """
    from labcairn.papers.responses import record_response as _record_response

    return _record_response(
        context,
        response_link_id=response_link_id,
        feedback_id=feedback_id,
        edit_action_id=edit_action_id,
        state=state,
        grade=grade,
        decided_by=decided_by,
        decided_at=decided_at,
        evidence_refs=evidence_refs,
        now=now,
    )


def settle_reply(
    context: ApplicationContext,
    *,
    settlement_id: str,
    reply_id: str,
    state: str,
    grade: str = "observed",
    decided_by: str | None = None,
    decided_at: datetime | None = None,
    evidence_refs: tuple[str, ...] = (),
    claim_terms: tuple[str, ...] = (),
    change_version_id: str | None = None,
    change_paragraph: int | None = None,
    anchor_status: str = "unknown",
    feedback_id: str | None = None,
    hold_reason: str | None = None,
    now: datetime,
) -> ReplySettlement:
    """Record the judgement that an author's answer settled a review point.

    **One point is judged once, and the judgement is a person's.** A model may
    put a settlement forward as ``pending`` and ``inferred``; it may not decide
    one. A settled settlement names the claim terms that the manuscript's
    accepted text bears out, and a held one names what the hold is waiting for.

    **And the permission it answers to is conditional, and the door says so.**
    :func:`labcairn.papers.replies.settle_reply` asks nothing of the policy for
    a settlement that is pending or whose anchor is ``unknown`` -- the row
    records a judgement about an exchange, and the exchange is already in the
    store. It asks ``source.read`` **when the settlement resolves an address**,
    because placing the change means reading the manuscript it was placed in.

    :raises ApplicationRefusedError: the reply, the comment or the version is
        not there, the point is already decided, the state, the grade, the
        anchor status or the decider is outside its vocabulary, the address and
        the anchor status disagree, a decision is claimed without its evidence,
        a model decides it, the claim is not in the manuscript, or the policy
        denied the read the resolution needs.
    """
    from labcairn.papers.replies import settle_reply as _settle_reply

    return _settle_reply(
        context,
        settlement_id=settlement_id,
        reply_id=reply_id,
        state=state,
        grade=grade,
        decided_by=decided_by,
        decided_at=decided_at,
        evidence_refs=evidence_refs,
        claim_terms=claim_terms,
        change_version_id=change_version_id,
        change_paragraph=change_paragraph,
        anchor_status=anchor_status,
        feedback_id=feedback_id,
        hold_reason=hold_reason,
        now=now,
    )


def record_assessment(
    context: ApplicationContext,
    *,
    assessment_id: str,
    project_id: str,
    assessment: str,
    outcome: str,
    basis: str,
    assessor_kind: str,
    feedback_id: str | None = None,
    issue_key: str | None = None,
    grade: str = "observed",
    evidence_refs: tuple[str, ...] = (),
    now: datetime,
) -> FollowupAssessment:
    """Record the later judgement about an issue, with its own evidence.

    **The advisor's advice may not be recorded as correct because the student's
    change was accepted.** Acceptance is a fact about the process; the
    correctness of the advice is a claim about the science, and the second needs
    evidence of its own. So an assessment with no evidence is refused here, and
    a basis of *"the change was accepted"* is not in the vocabulary at all.

    **And the permission it answers to is** ``source.inventory`` **on the
    project's materials**, asked by
    :func:`labcairn.papers.assessments.record_assessment`'s own
    ``consent.evaluate_all(context, capability=CapabilityId.SOURCE_INVENTORY,
    arguments={}, resources=_materials(context, project_id))``.

    :raises ApplicationRefusedError: the project, the comment or the issue is
        not there, the basis, the outcome, the assessor or the grade is outside
        its vocabulary, the assessment names neither a comment nor an issue, the
        assessment has no evidence, or the policy denied the inventory.
    """
    from labcairn.papers.assessments import record_assessment as _record_assessment

    return _record_assessment(
        context,
        assessment_id=assessment_id,
        project_id=project_id,
        assessment=assessment,
        outcome=outcome,
        basis=basis,
        assessor_kind=assessor_kind,
        feedback_id=feedback_id,
        issue_key=issue_key,
        grade=grade,
        evidence_refs=evidence_refs,
        now=now,
    )


__all__ = [
    "REVISION_CHANGE_KINDS",
    "ChainComment",
    "ChainEdge",
    "ChainEdit",
    "ChainReply",
    "ChainRevision",
    "ChainRevisionActivity",
    "ChainRevisionSource",
    "ProjectGraph",
    "classify_revision_change",
    "read_comments",
    "read_edits",
    "read_issue_keys",
    "read_material_paths",
    "read_project_graph",
    "read_replies",
    "read_response_states",
    "read_revision_activity",
    "read_revision_events",
    "read_revision_sources",
    "record_assessment",
    "record_edit",
    "record_feedback",
    "record_response",
    "record_revision_events",
    "settle_reply",
]
