"""Ingesting a workspace's supplied material, and binding it to the task.

LC-P1-08 built the machinery — the walk, the adapters, the store's writers —
and the application layer had no operation that called it. So a material could
be put in the ledger but never bound to a task: ``create_task`` took
``bound_source_ids`` and nothing ever supplied a non-empty value, the CLI bound
a source *directory* and never a source id, and a report built from such a task
could carry disclosures and never a claim — because a claim rests on a cited
record, and a citation points into material the task holds.

This module is the operation that closes that gap.

**It ingests through :class:`~labcairn.workspace.readonly.SourceMaterial`, and
never through a bare filesystem read.** The boundary is what applies the
capability to every file, and it is also what makes the supplied material
read-only by construction. An operation that read the files any other way
would depend on every future caller for that promise.

**A denied subtree stays invisible.** The boundary filters denied entries out
of a listing rather than refusing the call — ADR-0003 §C5 is explicit that a
bulk operation must not teach a model that a denied name exists — so a denied
subtree is never listed, never read, and never appears in the failures. The
failures this operation reports are the files the policy **permitted** and the
filesystem would not give: a file that cannot be read is a fact the caller
must see, and a fact about a permitted file is not a disclosure.

**An ask is answered by refusing, and never by reading.** A policy that asks
about the material is asking for a human, and this operation has no approval to
present. So the boundary is given a policy whose questions are denials — the
entry is dropped from the listing and never opened — and the operation refuses
before anything is read. A refusal the operator can act on beats a ledger that
quietly holds what nobody agreed to.

**Unreadable, empty and readable material are kept apart.** ADR-0004 A7 and
A9 insist on the distinction most systems collapse: *"we could not look"* is not
*"there was nothing there"*. A scanned PDF is in the second state, not the
first, and a file that was read and produced no text is a third fact again.
The report of an ingestion therefore carries each file's own readability and
whether it yielded any text, and the totals for each — and the totals are
computed from the files, so the two cannot disagree.

**It is idempotent.** Running it twice over the same material writes nothing
the second time: the source row is keyed by the id the walk mints from the
material's *location*, the extracted text is keyed by its content hash and its
locator, and a binding that already holds these ids is not a revision, so no
event is emitted for it either.

**The binding accumulates, and the report says what the task holds.** The
store's writer sets the binding to what it is handed, so a task that was given
material and then ingested again would forget what it was given — and the
operator removing a file from the workspace would take the task's material
with it. The binding after an operation is therefore the **union** of what
the task held and what this run ingested, computed here because the decision
belongs to the operation and not to a setter. The report carries both halves:
``source_ids`` is what this run ingested, ``bound_source_ids`` is what the
task holds. They are the same on a first ingestion and differ when the task
already held material this run did not touch, which is how a caller sees that
the two are not the same thing.

The one thing this module works around
-------------------------------------

``Source.relative_path`` is **workspace-relative** — that is the contract the
model states and the one the layer's readers resolve against the workspace
root. The walk used to write the key it was given, and the key is
**root-relative**: a file at ``materials/one.csv`` was recorded as
``one.csv``. A row holding that path resolves into the wrong root, and the
``source.inventory`` capability refuses it — so a material the walk ingested
could not be listed or inspected at all.

**The walk writes the workspace-relative path itself now**, so the
compensation below has nothing left to move: it computes the path the
contract names, and that is the path the row already holds. Two things
survive it, and both are why the code is still here rather than deleted.

**It repairs a ledger written before the fix.** The store's refresh branch
does not move a row's path, so a row the old walk wrote still holds the old
spelling — and the material in it is still unlistable. The relocation below
is what puts it right, and it can only find the old row because the source
id is derived from the root and the root-relative key and has not moved.

**It keeps the walk's ids the ones a single walk would have minted.** The
walk is driven **one source root at a time** so that the operation knows
which root each file came from, and the root's own id is carried over.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from labcairn.application import consent
from labcairn.application.context import ApplicationContext, store_refusals
from labcairn.application.models import Result
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.core.ids import SourceId
from labcairn.db.models import PaperVersionRow, SourceProblemRow, SourceRow
from labcairn.db.repository import list_tasks, load_source, load_task
from labcairn.material.ingest import IngestOutcome
from labcairn.material.walk import WalkReport, ingest_workspace
from labcairn.security.capabilities import CapabilityId
from labcairn.security.paths import AllowedRoot, RootKind, bind_root
from labcairn.security.policy import Permission, PermissionPolicy
from labcairn.sources.source import Source, SourceReadability
from labcairn.workspace.readonly import bind_source_material
from labcairn.workspace.roots import Workspace

__all__ = [
    "IngestFailure",
    "IngestedFile",
    "MaterialIngested",
    "SourceRemoved",
    "ingest_material",
    "remove_source",
]


class IngestedFile(Result):
    """One material the walk read, as the ledger now holds it.

    ``source`` is the ledger's own row — its kind, its hash, its size and its
    readability — so a caller does not have to read it back to know what was
    ingested.

    ``text_rows`` and ``problem_rows`` count what the material **yielded**,
    not what this run wrote: a file ingested a second time yields the same
    text and writes none of it again, and a report that counted the writes
    would call a full file an empty one. ``rows_written`` is the other half —
    what this run put in the store, which is zero the second time and is how
    a caller can see that the second run changed nothing.

    ``empty`` separates *"we read it and there was nothing in it"* from *"we
    read it and it says nothing about why it is empty"*. The store records the
    second as a problem row of its own, and a caller that cannot tell the two
    apart would report an empty file as a file it failed to read.
    """

    source: Source
    #: The text rows the material yielded.
    text_rows: int
    #: The problem rows — the disclosures — the material yielded.
    problem_rows: int
    #: The rows this run wrote: the text and the problems, together.
    rows_written: int
    #: Readable, and no text came out of it.
    empty: bool


class IngestFailure(Result):
    """One file the walk could not read, and why.

    The file was **permitted** — the policy allowed it and the boundary listed
    it — and the filesystem or the store would not give it up. A denied file is
    not here: it was never listed, so the caller is not told it exists.
    """

    relative_path: str
    reason: str


class MaterialIngested(Result):
    """What the ingestion of a workspace's material produced.

    ``bound_source_ids`` is the task's binding after the operation, and
    ``source_ids`` is what this run ingested. They are the same set on a first
    ingestion and differ when the task already held material this run did not
    touch — the binding is the task's, and the ingestion is this run's.

    **The difference between them is a fact, not an accident.** A report
    carrying one list for both would say that what the task rests on is what
    this run read — which stops being true the moment the operator removes a
    file and the task keeps holding it. Two lists are where a caller sees
    that, so they are kept apart rather than collapsed into the one the store
    holds.

    The three totals are the separation ADR-0004 A7 asks for, counted from
    ``files``: ``readable`` is material that may be cited, ``empty`` is
    readable material that yielded no text, and ``unreadable`` is material
    that could not be turned into addressable text at all.
    """

    source_ids: tuple[str, ...]
    files: tuple[IngestedFile, ...]
    failures: tuple[IngestFailure, ...]
    #: Files whose format has no adapter: inventoried and hashed, not extracted.
    skipped: tuple[str, ...]
    bound_source_ids: tuple[str, ...]
    readable: int
    empty: int
    unreadable: int


class SourceRemoved(Result):
    """What the removal took out of the ledger.

    ``released_task_ids`` are the tasks that held the material and no longer
    do. **A task that keeps holding a source the ledger does not hold is a
    task that claims material it cannot produce**, and the layer refuses that
    when it lists a task's sources -- so the binding is released here rather
    than left broken.

    ``removed_problem_count`` is how many disclosures about *that file at that
    location* went with it. The extracted text and the addresses do not: they
    are the evidence side, and ADR-0009 says a file that is deleted does not
    take its text with it.

    ``repointed_version_ids`` are the paper versions that named the material
    and now name it where it lives, with ``repointed_to_source_id`` saying
    where that is. **A version's identity is the bytes it was made from**, so
    a version that follows the bytes is still the same version; the ones that
    could not follow are not listed here, because the removal refused.
    """

    source_id: str
    relative_path: str
    content_sha256: str
    released_task_ids: tuple[str, ...]
    removed_problem_count: int
    repointed_version_ids: tuple[str, ...] = ()
    repointed_to_source_id: str | None = None


def ingest_material(
    context: ApplicationContext,
    *,
    now: datetime | None = None,
) -> MaterialIngested:
    """Ingest the workspace's supplied material, and bind it to the task.

    The material is read through the permission boundary and stored by the
    machinery LC-P1-08 built; the ids it mints are then bound to the task, so
    the task **holds** what it rests on. One file that cannot be read does not
    stop the others: the failure is recorded and reported, because a workspace
    with one corrupt file should still be inventoried.

    :param context: everything the operation is given. The workspace's source
        roots are the material's home, and the context's policy is what the
        boundary applies to every file it reads.
    :param now: the moment the ingestion is dated with. Passed in rather than
        read, so that "when was this made" is a fact and not a re-derivation.
    :raises ApplicationRefusedError: the workspace binds no source root, the
        policy asked about the material, or the store holds no such task.
    """
    moment = now if now is not None else datetime.now(UTC)

    roots = context.workspace.source_roots
    if not roots:
        raise ApplicationRefusedError(
            ApplicationRefusal.PATH_REFUSED,
            f"the workspace at {context.workspace.selected_root} binds no source "
            "root, so there is no supplied material to ingest. A source root is a "
            "directory inside the workspace that holds the material the researcher "
            "supplied; `labcairn task create --source-dir` names one.",
        )

    _refuse_a_question(context)

    # The boundary reads with a policy whose questions are denials, so nothing
    # the policy asked about is ever opened.
    policy = _without_questions(context.policy)
    outcomes: list[IngestOutcome] = []
    failures: list[tuple[str, str]] = []
    skipped: list[str] = []
    renames: dict[str, str] = {}

    for root in roots:
        workspace = _one_root_workspace(context.workspace, root)
        material = bind_source_material(workspace, policy)
        report = ingest_workspace(context.store.session, material, ingested_at=moment)
        outcomes.extend(report.outcomes)
        failures.extend(report.failures)
        skipped.extend(report.skipped)
        renames.update(_the_workspace_relative_paths(context.workspace, root, report))

    if renames:
        context.store.relocate_sources(renames)

    ingested = tuple(outcome.material.source.source_id for outcome in outcomes)
    bound = _bind(context, ingested, moment=moment)
    return _the_report(outcomes, failures, skipped, ingested, bound, renames)


def _one_root_workspace(workspace: Workspace, root: AllowedRoot) -> Workspace:
    """The same workspace, with one source root bound.

    The walk mints a source id from the root's id and the file's key, so two
    roots holding a file of the same name must not share an id — and the
    root's own id is what keeps them apart. Walking one root at a time is how
    the operation knows which root each file came from, and the id is carried
    over so the ids are the ones a single walk would have minted.
    """
    others = tuple(bound for bound in workspace.roots if bound.kind is not RootKind.SOURCE)
    return Workspace(
        selected_root=workspace.selected_root,
        task_id=workspace.task_id,
        roots=(bind_root(root.root_id, root.path, RootKind.SOURCE), *others),
    )


def _the_workspace_relative_paths(
    workspace: Workspace,
    root: AllowedRoot,
    report: WalkReport,
) -> dict[str, str]:
    """Where each ingested file lives, in the spelling the ledger holds.

    The walk writes the key it was given, and the key is root-relative; the
    ledger's contract is workspace-relative. A path that already carries the
    root's own prefix is left alone, so the operation does nothing once the
    walk writes the workspace-relative path itself.
    """
    prefix = root.path.relative_to(workspace.selected_root).as_posix()
    renames: dict[str, str] = {}
    for outcome in report.outcomes:
        source = outcome.material.source
        key = source.relative_path
        if prefix and key.startswith(f"{prefix}/"):
            renames[source.source_id] = key
        else:
            renames[source.source_id] = f"{prefix}/{key}" if prefix else key
    return renames


def _without_questions(policy: PermissionPolicy) -> PermissionPolicy:
    """The same policy, with every question turned into a denial.

    An ASK is a question the operator has not answered yet, and the answer
    would be an approval. This operation has none to present, so the material
    the policy asked about must not be read — and the boundary's answer to a
    denial is to drop the entry from the listing, which is also what makes a
    denied subtree invisible.

    Only the rules that asked are changed. An allow rule stays an allow rule
    and a deny rule stays a deny rule, so the policy's other verdicts are the
    ones the operator wrote.
    """
    return PermissionPolicy.from_rules(
        replace(rule, effect=Permission.DENY) if rule.effect is Permission.ASK else rule
        for rule in policy.rules
    )


def _refuse_a_question(context: ApplicationContext) -> None:
    """Refuse when the policy asked about the material.

    Asked at the top of each source root, because that is where the entries a
    blanket question covers live: a rule that asks about the material asks
    about all of it. The refusal happens **before** the walk, so nothing has
    been read when the operator is told their policy needs an answer.
    """
    material = bind_source_material(context.workspace, context.policy)
    for root in context.workspace.source_roots:
        for entry in material.list_dir("", root_id=root.root_id):
            resource = context.resource_in(root.root_id, entry)
            authorisation = consent.evaluate(
                context,
                capability=CapabilityId.SOURCE_INVENTORY,
                arguments={},
                resource=resource,
            )
            if authorisation.permission is Permission.ASK:
                raise ApplicationRefusedError(
                    ApplicationRefusal.POLICY_ASKED,
                    f"the policy asked about {CapabilityId.SOURCE_INVENTORY.value} on "
                    f"{resource.resolved_key!r}, and no approval was supplied. An "
                    "ingestion the policy asked about needs consent: grant the "
                    "approval and ingest the material again.",
                )


def _bind(
    context: ApplicationContext,
    ingested: Sequence[str],
    *,
    moment: datetime,
) -> tuple[SourceId, ...]:
    """Bind what was ingested to the task, and return the binding it now holds.

    **The binding is the union of what the task held and what this run
    ingested.** The binding is the task's: material it was given is not taken
    back because the operator removed the file from the workspace, and a task
    that quietly forgot what it rests on is a task whose report rests on
    nothing. The store's writer is a setter — it sets the column to what it
    is handed — so the union is computed here, where the decision belongs, and
    the store is handed the result.

    The binding and the event that describes it commit together, in the
    store's own transaction: a binding nobody was told about is a state
    change with no record, and a task that claims material the ledger does not
    hold is a binding that cannot be honoured.
    """
    with store_refusals():
        held = load_task(context.store.session, context.task_id).bound_source_ids
        bound = _the_union(held, tuple(SourceId(source_id) for source_id in ingested))
        context.store.bind_sources(context.task_id, bound, occurred_at=moment)
    return bound


def _the_union(
    held: tuple[SourceId, ...],
    ingested: tuple[SourceId, ...],
) -> tuple[SourceId, ...]:
    """What the task holds once this run's material is bound to it.

    The task's own binding first, in the order it bound it, and then what
    this run brought that it did not already hold. **The order is the
    task's**, because a binding's order is the order the researcher bound the
    material in, and a union that reshuffled it would be a revision of a
    state that did not move — which is what the store would then record.
    """
    union = list(held)
    known = set(held)
    for source_id in ingested:
        if source_id not in known:
            known.add(source_id)
            union.append(source_id)
    return tuple(union)


def _the_report(
    outcomes: list[IngestOutcome],
    failures: list[tuple[str, str]],
    skipped: list[str],
    ingested: tuple[str, ...],
    bound: tuple[SourceId, ...],
    renames: Mapping[str, str],
) -> MaterialIngested:
    """The walk's outcome, as the operation reports it.

    The three totals are counted from the files rather than kept beside them,
    so a count cannot disagree with the list it counts. And the source each
    file carries is the one **the ledger holds**: a report that named the
    path the walk happened to use would say something the ledger does not.

    The two id lists are the operation's own two facts, kept apart: what this
    run read, and what the task now holds.
    """
    files: list[IngestedFile] = []
    for outcome in outcomes:
        material = outcome.material
        source = material.source
        relocated = renames.get(source.source_id)
        if relocated is not None:
            source = source.model_copy(update={"relative_path": relocated})
        files.append(
            IngestedFile(
                source=source,
                text_rows=len(material.texts),
                problem_rows=len(material.problems),
                rows_written=outcome.text_rows_written + outcome.problem_rows_written,
                empty=not material.texts and source.readability is SourceReadability.READABLE,
            )
        )
    readable = sum(1 for item in files if item.source.readability is SourceReadability.READABLE)
    empty = sum(1 for item in files if item.empty)
    unreadable = len(files) - readable
    return MaterialIngested(
        source_ids=ingested,
        files=tuple(files),
        failures=tuple(
            IngestFailure(relative_path=path, reason=reason) for path, reason in failures
        ),
        skipped=tuple(skipped),
        bound_source_ids=tuple(str(source_id) for source_id in bound),
        readable=readable,
        empty=empty,
        unreadable=unreadable,
    )


def remove_source(context: ApplicationContext, source_id: str) -> SourceRemoved:
    """Take a source back out of the ledger.

    **A source's identity is where the material is, not what it holds.** The
    ledger keys a source by its location -- the id is minted from the root and
    the key inside it, and the path is unique -- while the digest is recorded
    and never the key. So a material that is *moved* is a *new* source, and
    ingesting it where it now sits writes a second row rather than moving the
    first one. That is the rule working, not the rule failing: the row the
    old path left behind names a path that is not there any more, and this is
    the operation that takes it back.

    **The row goes; the evidence stays.** The extracted text and the
    addresses into it are keyed by the content hash and the locator, not by
    the source, and ADR-0009 says a file that is deleted does not take its
    text with it -- so the records resting on those addresses keep
    resolving. What leaves with the row is the material's own inventory
    entry and the disclosures about *that file at that location*.

    **A task that held the material lets it go.** The binding is the task's
    own state, and the store's writer records a revision with the event that
    describes it, so the release is written with its event rather than by
    editing the column behind the log's back.

    **A paper version that named the material follows the bytes.** A version
    is the set of bytes it was made from -- the model says so, and says that
    two files with the same bytes are one version -- so when the material is
    at another location and the ledger holds a row for it there, the version
    follows the bytes to that row. When no such row exists the bytes are
    gone, and the removal refuses rather than take a manuscript's revision
    history with it.

    **The operation refuses before it has had any effect.** A source the
    ledger does not hold, a policy that denies the material, and a paper
    version whose material is nowhere else are refusals, and none of them
    leaves a half-applied removal behind.

    :param context: everything the operation is given.
    :param source_id: the id of the source to take back.
    :raises ApplicationRefusedError: the ledger holds no such source, the
        policy denied the material, or a paper version names the file and the
        material is nowhere else in the ledger.
    """
    session = context.store.session
    source = load_source(session, str(source_id))
    if source is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.SOURCE_NOT_FOUND,
            f"the ledger holds no source with the id {source_id!r}.",
        )

    resource = context.resource_for(source.relative_path)
    consent.evaluate(
        context,
        capability=CapabilityId.SOURCE_INVENTORY,
        arguments={},
        resource=resource,
    )

    versions, survivor = _take_the_versions_with_the_material(session, source)

    # The binding first, then the row. A release that commits and a deletion
    # that does not leaves a task that no longer holds material the ledger
    # still holds, which is a state the operator can undo; the other order
    # leaves a task holding a source that is not there, which is the broken
    # state this operation exists to end.
    released = _release_the_bindings(context, source.source_id)
    problems = _remove_the_source_rows(session, source.source_id)
    session.commit()
    return SourceRemoved(
        source_id=source.source_id,
        relative_path=source.relative_path,
        content_sha256=source.content_sha256,
        released_task_ids=released,
        removed_problem_count=problems,
        repointed_version_ids=versions,
        repointed_to_source_id=survivor,
    )


def _release_the_bindings(context: ApplicationContext, source_id: str) -> tuple[str, ...]:
    """Every task that held the material lets it go, and says so in the log.

    The binding is the task's own state, and the store's writer is the only
    thing that writes it -- it records the revision with the event that
    describes it, which is what ADR-0003 C3 asks for. **A task that kept
    holding a source the ledger does not hold is a task that claims material
    it cannot produce**, and the layer refuses that when it lists a task's
    sources.

    Every task is looked at, not only the one the caller happens to be in: a
    source is workspace state, and the tasks that hold it are the ones that
    would be left claiming it.
    """
    released: list[str] = []
    with store_refusals():
        for task in list_tasks(context.store.session):
            if source_id not in task.bound_source_ids:
                continue
            remaining = tuple(
                SourceId(bound) for bound in task.bound_source_ids if bound != source_id
            )
            context.store.bind_sources(task.task_id, remaining)
            released.append(str(task.task_id))
    return tuple(released)


def _remove_the_source_rows(session: Session, source_id: str) -> int:
    """The row, and the disclosures about that file at that location, gone.

    The disclosures go with the row because they are about *this file at this
    path*: the same bytes ingested somewhere else are disclosed again there,
    and a disclosure about a file the ledger no longer holds is a disclosure
    about nothing.

    The extracted text and the addresses into it stay. They are keyed by the
    content hash and the locator rather than by the source, and ADR-0009 is
    explicit that a file which is deleted does not take its text with it --
    so the records that rest on those addresses keep resolving.
    """
    problems = cast(
        CursorResult[Any],
        session.execute(delete(SourceProblemRow).where(SourceProblemRow.source_id == source_id)),
    ).rowcount
    row = session.scalar(select(SourceRow).where(SourceRow.source_id == source_id))
    if row is not None:
        session.delete(row)
    return max(problems, 0)


def _take_the_versions_with_the_material(
    session: Session, source: Source
) -> tuple[tuple[str, ...], str | None]:
    """The versions that named the material follow the bytes, or the removal refuses.

    **A version's identity is the bytes it was made from.** The version
    graph's own model says so: the file's bytes move, a version that took
    its identity from the file would move with it, and *two files with the
    same bytes are one version*. So when the material is at another location
    and the ledger holds a row for it there, the version follows the bytes to
    that row -- it keeps naming the same set of bytes, and its recorded hash
    still matches the row it names.

    When there is no such row the bytes are gone, and **a version with no
    file is not a version**: the schema cascades, so the version's row would
    go with the file. The removal refuses rather than take a manuscript's
    revision history with it, and the refusal comes before anything is
    written.

    :returns: the versions that were re-pointed, and the row they now name.
    """
    versions = tuple(
        session.scalars(
            select(PaperVersionRow).where(PaperVersionRow.source_id == source.source_id)
        )
    )
    if not versions:
        return (), None
    survivor = session.scalar(
        select(SourceRow)
        .where(
            SourceRow.content_sha256 == source.content_sha256,
            SourceRow.source_id != source.source_id,
        )
        .order_by(SourceRow.ingested_at.asc(), SourceRow.source_id.asc())
        .limit(1)
    )
    if survivor is None:
        raise ApplicationRefusedError(
            ApplicationRefusal.PAPER_CONTRACT_REFUSED,
            f"the paper version {versions[0].version_id!r} was recorded against "
            f"the material {source.source_id!r}, and a version with no file is "
            "not a version: the material's bytes are nowhere else in the ledger, "
            "so taking the material back would take that version's row with it. "
            "The material stays in the ledger until the version does.",
        )
    for version in versions:
        version.source_id = survivor.source_id
    # The re-pointing is on the wire before the row it points at is deleted:
    # the foreign key is checked per statement, and a delete that ran first
    # would cascade the version's row away.
    session.flush()
    return tuple(version.version_id for version in versions), survivor.source_id
