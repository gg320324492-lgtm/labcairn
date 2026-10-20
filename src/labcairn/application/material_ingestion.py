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

The one thing this module works around
-------------------------------------

``Source.relative_path`` is **workspace-relative** — that is the contract the
model states and the one the layer's readers resolve against the workspace
root. The walk, on the other hand, writes the key it was given, and the key
is **root-relative**: a file at ``materials/one.csv`` is recorded as
``one.csv``. A row holding that path resolves into the wrong root, and the
``source.inventory`` capability refuses it — so a material the walk ingested
cannot be listed or inspected at all.

So the walk is driven **one source root at a time**, and each root's rows are
then moved to the path the contract names. The root is walked on its own so
that the operation knows which root each file came from, and the root's own id
is carried over so the source ids are the ones a single walk would have
minted. The fix belongs in the walk; this is the operation compensating for
it, and it is written so that it does nothing once the walk writes the
workspace-relative path itself.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from labcairn.application import consent
from labcairn.application.context import ApplicationContext, store_refusals
from labcairn.application.models import Result
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.core.ids import SourceId
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
    "ingest_material",
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

    bound = _bind(
        context, [outcome.material.source.source_id for outcome in outcomes], moment=moment
    )
    return _the_report(outcomes, failures, skipped, bound)


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
    source_ids: list[str],
    *,
    moment: datetime,
) -> tuple[SourceId, ...]:
    """Bind what was ingested to the task, and return the binding.

    The binding and the event that describes it commit together, in the
    store's own transaction: a binding nobody was told about is a state
    change with no record, and a task that claims material the ledger does not
    hold is a binding that cannot be honoured.
    """
    bound = tuple(SourceId(source_id) for source_id in source_ids)
    with store_refusals():
        context.store.bind_sources(context.task_id, bound, occurred_at=moment)
    return bound


def _the_report(
    outcomes: list[IngestOutcome],
    failures: list[tuple[str, str]],
    skipped: list[str],
    bound: tuple[SourceId, ...],
) -> MaterialIngested:
    """The walk's outcome, as the operation reports it.

    The three totals are counted from the files rather than kept beside them,
    so a count cannot disagree with the list it counts.
    """
    files: list[IngestedFile] = []
    for outcome in outcomes:
        material = outcome.material
        source = material.source
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
        source_ids=tuple(str(source_id) for source_id in bound),
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
