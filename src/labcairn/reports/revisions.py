"""``labcairn.reports.revisions`` — one revision of a report, and what makes it stale.

LC-P1-11's T03 is *"revisions and staleness"*, and it is two properties that
have nothing to do with each other except that they are both about the same
artefacts:

* **a revision is a new artefact, not a new version of the old bytes** — a
  second report of the same task is a new revision with new files, and the
  first revision's files are never altered;
* **a report whose material changed is stale** — and it is stale because the
  repository's own walk says so, not because this module compared two hashes.

What one revision is
--------------------
A revision of a task's report is a **set of artefacts that share one revision
number**: the canonical document (the model's
:meth:`~labcairn.reports.model.ReportDocument.canonical_bytes`), the manifest
that describes it, and the four rendered forms. Six receipts, one revision
number, one identity — **the task and the revision**. Each is written under a
path that carries its revision, so ``report/v1/report.md`` and
``report/v2/report.md`` can both exist and the first is never touched. That is
what "without altering originals" means, and it is why the receipt carries a
revision rather than a path that is overwritten.

**A revision is immutable once written.** The DOCX is a ZIP whose entries carry
timestamps and the PDF carries a creation date, so re-rendering revision 1
produces *different bytes* for the same revision number. Two artefacts
claiming to be revision 1 with different hashes is exactly the ambiguity the
revision number exists to prevent, so a revision that has been written is
refused rather than rewritten.

**A revision is written in six writes, and a crash between them leaves a
partial directory.** The next write of that revision is refused rather than
completed: the DOCX and the PDF are not byte-reproducible, so a re-render
would produce different bytes for a revision number that already has bytes on
disk, which is the ambiguity above wearing a different hat. The operator
removes the directory and writes again. The ledger holds no receipt for an
unfinished revision, so what happened is visible there.

The chain, and why it is flat
-----------------------------
The report's chain is an **ancestor closure** — the manifest, the parts, and
the parts' own upstream, in one flat list — and the flatness is the point
rather than a simplification. The staleness walk that already exists,
:meth:`labcairn.recovery.resume.ResumeCoordinator.invalidate_on_source_change`,
is **one hop**: it marks an artefact stale when *that artefact's* ``derived_from``
names a changed hash, and it does not follow parent to child. A chain that
named only its immediate parent would stop at the manifest and never see the
material underneath it move — the manifest would be marked, and the report would
sit there saying ``CURRENT`` about bytes whose material had changed.

The alternatives were weighed and rejected: naming only the direct parent would
need the walk to become a graph traversal, which means changing
:mod:`labcairn.recovery.resume` — **G3's accepted code**, and changing accepted
code re-opens a closed gate. The flat closure is where the cost is spent
instead. With it, the existing walk marks the report, the manifest and the
figure in **one pass**, with no new mechanism and no change to accepted code.

The closure itself is :func:`labcairn.reports.manifest.manifest_chain` — the
same builder that gives the manifest receipt its chain — so the report's chain
and the manifest's chain cannot drift apart, and this module does not contain a
second implementation of the ancestor closure.

**The material has to be in that closure.** A link with no hash is a link
nothing can invalidate, so every link in the chain carries one; and the chain
must reach *outside* the report's own files, because the report's own files
never change when the material does. The material reaches the chain twice
over, and both routes are needed. The **parts**' material reaches it through
the ``upstreams`` the caller hands to the manifest builder: a table's
upstream is what produced it, and that link is what names the material. The
**report's own** material — the sources its claims were read from — reaches
it through the document part of the manifest, which names them.

The second route is not a nicety. A report with no parts has no upstreams to
hand over, so the first route names nothing for it at all; and a report whose
chain names nothing but its own files cannot be marked stale when the material
moves. The walk would have nothing to match, and nothing in this module would
notice.

What the report's own face cannot know
--------------------------------------
**A file on disk does not watch itself.** The staleness mark is the
**receipt's**, and it is paired: a ``STALE`` receipt carries a reason and a
``CURRENT`` one does not, which is the receipt model's own rule. A reader who
opens the file sees a report that is not marked stale and has to look at the
receipt to know — and the report may carry a line saying it was rendered from
material that has since changed, but **only because it was re-rendered**, not
because the file noticed. That is the honest limit of the mechanism, and it is
the same trade the figures already make.

What this module does not do
----------------------------
It does not decide staleness. Nothing here compares two hashes to decide
whether a report is current; the repository's own walk decides, and the reason
it records is the repository's own. If this module made that comparison, the
report would be stale only when *this* code ran, and the ledger's answer would
be a second one.

It does not render, and it does not check. The four forms arrive as bytes and
the content checks arrive as a callable, because those are T01's and T04's.
What this module owns is the part neither of them owns: **which revision a
report is, where it goes, and what its chain says.**
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from typing import Final

from labcairn.reports.manifest import (
    ReportManifest,
    build_report_manifest,
    manifest_chain,
    write_report_manifest,
)
from labcairn.reports.model import ReportDocument
from labcairn.reports.receipt import (
    ArtifactKind,
    ArtifactProducerKind,
    ArtifactReceipt,
    DerivationRef,
    DerivationTargetKind,
)
from labcairn.workspace.outputs import TaskOutputArea, WriteReceipt
from labcairn.workspace.roots import Workspace

#: The directory, inside a task's output area, that holds every revision.
#:
#: One directory per task, so two tasks cannot write over each other's
#: reports, and one subdirectory per revision inside it, so one task's
#: revisions cannot write over each other's either.
REPORT_DIR: Final[str] = "report"

#: The canonical document's filename, inside a revision's directory.
#:
#: The canonical bytes are JSON, and the file is named for what it is rather
#: than for the form it is a preview of.
DOCUMENT_FILENAME: Final[str] = "report.json"

#: The manifest's filename, inside a revision's directory.
MANIFEST_FILENAME: Final[str] = "report-manifest.json"

#: Who produced a revision, when the caller does not say.
#:
#: The module that writes a revision is a true answer, and a receipt whose
#: producer names nothing is a receipt nobody can hold to anything.
DEFAULT_REVISION_PRODUCER_ID: Final[str] = "labcairn.reports.revisions"

#: The media type the canonical document is recorded as.
DOCUMENT_MEDIA_TYPE: Final[str] = "application/json"


class ReportForm(StrEnum):
    """The four forms a report is written in.

    Closed, because a revision writes **four** forms and a form nobody has a
    media type for is a form nobody can serve. The enum is also the check:
    a mapping with a fifth key is refused rather than written under a name
    the repository does not recognise.
    """

    #: The reference form. Byte-reproducible.
    MARKDOWN = "markdown"
    #: The preview form. Byte-reproducible.
    HTML = "html"
    #: The editable form. Its bytes are recorded, not claimed reproducible.
    DOCX = "docx"
    #: The fixed form. Its bytes are recorded, not claimed reproducible.
    PDF = "pdf"


#: The file suffix each form is written under.
_FORM_SUFFIX: Final[dict[ReportForm, str]] = {
    ReportForm.MARKDOWN: "md",
    ReportForm.HTML: "html",
    ReportForm.DOCX: "docx",
    ReportForm.PDF: "pdf",
}

#: The media type each form is recorded as.
#:
#: Stated rather than inferred from the suffix: the suffix is a convention on
#: the filesystem and the media type is a claim about the bytes.
_FORM_MEDIA_TYPE: Final[dict[ReportForm, str]] = {
    ReportForm.MARKDOWN: "text/markdown; charset=utf-8",
    ReportForm.HTML: "text/html; charset=utf-8",
    ReportForm.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ReportForm.PDF: "application/pdf",
}


class ReportRevisionRefusedError(RuntimeError):
    """The revision was refused, and saying why is the whole answer.

    A refusal rather than a revision with a blank in it. The alternatives are
    worse: a revision written from a document the checks refused is a report
    nobody may rely on, and a revision written over an existing one is two
    artefacts claiming the same number. The project's rule is that an unknown
    is never a zero and a missing thing is never a blank — here it is a
    refusal.
    """


@dataclass(frozen=True, slots=True)
class ReportRevision:
    """One revision of a task's report: the six artefacts and what they say.

    The six receipts share one revision number and one task, and that is the
    identity. :attr:`receipts` is them all, in the order they were written.
    """

    #: The revision number every receipt in this revision carries.
    revision: int
    #: The canonical document's receipt.
    document: ArtifactReceipt
    #: The manifest's receipt. Its chain is the ancestor closure *without*
    #: the manifest's own link — it is the manifest.
    manifest: ArtifactReceipt
    #: The four rendered forms' receipts, in :class:`ReportForm` order.
    forms: tuple[ArtifactReceipt, ...]

    @property
    def receipts(self) -> tuple[ArtifactReceipt, ...]:
        """Every receipt this revision wrote, the document first."""
        return (self.document, self.manifest, *self.forms)


def report_chain(
    manifest: ReportManifest, *, manifest_receipt_id: str
) -> tuple[DerivationRef, ...]:
    """The report's chain: the manifest, the parts, and the parts' upstream.

    An **ancestor closure**, in one flat list, and the flatness is the point
    rather than a simplification. The staleness walk that already exists —
    :meth:`labcairn.recovery.resume.ResumeCoordinator.invalidate_on_source_change`
    — is **one hop**: it marks an artefact stale when that artefact's *own*
    ``derived_from`` names a changed hash, and it does not follow parent to
    child. A chain that named only its immediate parent would therefore stop
    at the manifest and never see the material underneath it move: the manifest
    would be marked, and the report would sit there saying ``CURRENT`` about
    bytes whose material had changed.

    So the chain names the manifest **and** everything the manifest's parts
    were made from, in one list, and the material's hash is directly in the
    report's chain. The existing walk then reaches the report, the manifest
    and the figure in one pass, with no new mechanism and without a change to
    G3's accepted code.

    **The material is in the manifest, so it is in the closure.** The
    manifest's document part names the parts of the report *and* the sources
    the report's claims were read from, so a report with claims and no
    figure and no table names its material all the same — and the material's
    hash is **directly** in the report's chain, which is what the one-hop
    walk needs.

    The closure is :func:`labcairn.reports.manifest.manifest_chain` — the same
    builder that gives the manifest receipt its chain — so the two cannot
    drift apart, and this is not a second implementation of the closure.

    :param manifest: the manifest that describes the report.
    :param manifest_receipt_id: the id the manifest's own receipt will carry.
        It is what the report's chain names the manifest by, so it has to be
        the id the ledger will hold.
    :raises ReportRevisionRefusedError: when the closure already names the
        manifest's receipt id — one upstream thing cited twice with two names
        is one dependency, and the receipt's own model refuses it.
    """
    manifest_hash = sha256(manifest.canonical_bytes()).hexdigest()
    link = DerivationRef(
        target_kind=DerivationTargetKind.ARTIFACT,
        target_id=manifest_receipt_id,
        content_sha256=manifest_hash,
    )
    closure = manifest_chain(manifest)
    if any(
        reference.target_kind is link.target_kind and reference.target_id == link.target_id
        for reference in closure
    ):
        raise ReportRevisionRefusedError(
            f"the chain already names {manifest_receipt_id!r}. The report's chain "
            "names the manifest and the manifest's closure, and naming the same "
            "thing twice is one dependency recorded two ways."
        )
    return (link, *closure)


def existing_revisions(workspace: Workspace) -> tuple[int, ...]:
    """The revision numbers this task's output area already holds.

    The filesystem's answer, and the module's authority on what a task has
    been written. It is *not* the ledger's answer: the receipts are what the
    ledger holds, and a revision whose directory was removed by hand is still
    in the ledger. A caller that knows the ledger's receipts should name the
    revision explicitly rather than let this decide it.
    """
    root = workspace.output_root.path / REPORT_DIR
    if not root.is_dir():
        return ()
    found: set[int] = set()
    for entry in root.iterdir():
        if not entry.is_dir() or not entry.name.startswith("v"):
            continue
        suffix = entry.name[1:]
        if suffix.isdigit():
            found.add(int(suffix))
    return tuple(sorted(found))


def write_report_revision(
    workspace: Workspace,
    *,
    document: ReportDocument,
    forms: Mapping[ReportForm, bytes],
    verify: Callable[[ReportDocument], None],
    upstreams: Mapping[str, tuple[DerivationRef, ...]] | None = None,
    revision: int | None = None,
    created_at: datetime,
    producer_id: str = DEFAULT_REVISION_PRODUCER_ID,
    produced_by: ArtifactProducerKind = ArtifactProducerKind.STAGE,
) -> ReportRevision:
    """Write one revision of a task's report, and return what it wrote.

    The revision is prepared **before** a byte lands: the checks run, the
    manifest is built from the document, and the chain is assembled, all
    before the first write. A revision that cannot be prepared is refused
    without leaving a file behind — a generated file no receipt names is an
    artefact nothing can account for.

    The manifest is written **first**, because the report's chain names it. A
    chain that named a file that was not there would be a chain nothing could
    check.

    :param document: the report, as the model holds it. Its canonical bytes
        are the revision's canonical document.
    :param forms: the four rendered forms' bytes, keyed by :class:`ReportForm`.
        All four are required: a revision is the document, the manifest and
        the four forms, and a revision missing one is a revision nobody can
        open in that form.
    :param verify: the content checks (LC-P1-11's T04) — a callable that
        **raises** if the document says anything the ledger does not support.
        Required, and called before anything is written, because a report that
        says something the ledger does not support must not be written at all.
    :param upstreams: what produced each part of the report, by part id. It
        is how the **parts'** material reaches the chain: a table's upstream
        is what computed it, and that link is the one the staleness walk
        matches when the material moves. The report's *own* material — the
        sources its claims were read from — reaches the chain through the
        manifest's document part, so a report with no parts is marked stale
        as well; a report whose chain names nothing outside its own files
        cannot be marked stale at all.
    :param revision: the revision number. Left out, it is one beyond the
        highest this task's output area holds. Given, it must be beyond that
        too — a revision that has been written is immutable, and re-rendering
        it would produce different bytes for the same number.
    :param created_at: when the revision was produced. Passed in rather than
        read, so that "when was this made" is a fact and not a re-derivation.
    :raises ReportRevisionRefusedError: when the checks refuse the document,
        when a form is missing or unrecognised, when the revision has already
        been written, or when the chain contradicts itself.
    """
    task_id = str(workspace.task_id)

    # 1. The checks. Before anything is written, and before anything is built.
    try:
        verify(document)
    except Exception as error:
        raise ReportRevisionRefusedError(
            f"the content checks refused the document, so no revision was written: "
            f"{error}. A report that says something the ledger does not support "
            "must not be written at all."
        ) from error

    # 2. The revision number. A revision that exists is immutable.
    resolved = _resolve_revision(workspace, revision)

    # 3. The forms. All four, and only four.
    supplied = _supplied_forms(forms)

    # 4. The manifest, built from the document.
    document_key = _revision_key(resolved, DOCUMENT_FILENAME)
    manifest = build_report_manifest(
        document=document,
        document_relative_path=_workspace_relative(workspace, document_key),
        upstreams=upstreams,
    )

    # 5. The chain: an ancestor closure, assembled before anything is written.
    manifest_receipt_id = _receipt_id(task_id, resolved, "manifest")
    chain = report_chain(manifest, manifest_receipt_id=manifest_receipt_id)

    # 6. The writes.
    outputs = TaskOutputArea(workspace)
    manifest_receipt = write_report_manifest(
        workspace,
        key=_revision_key(resolved, MANIFEST_FILENAME),
        manifest=manifest,
        receipt_id=manifest_receipt_id,
        created_at=created_at,
        producer_id=producer_id,
        produced_by=produced_by,
        revision=resolved,
    )
    _assert_the_manifest_is_the_one_the_chain_names(manifest, manifest_receipt, chain)

    document_write = outputs.write(document_key, document.canonical_bytes())
    document_receipt = _receipt(
        workspace,
        document_write,
        receipt_id=_receipt_id(task_id, resolved, "document"),
        kind=ArtifactKind.REPORT,
        media_type=DOCUMENT_MEDIA_TYPE,
        revision=resolved,
        chain=chain,
        created_at=created_at,
        producer_id=producer_id,
        produced_by=produced_by,
    )

    form_receipts: list[ArtifactReceipt] = []
    for form in ReportForm:
        write = outputs.write(
            _revision_key(resolved, f"report.{_FORM_SUFFIX[form]}"),
            supplied[form],
        )
        form_receipts.append(
            _receipt(
                workspace,
                write,
                receipt_id=_receipt_id(task_id, resolved, form.value),
                kind=ArtifactKind.REPORT,
                media_type=_FORM_MEDIA_TYPE[form],
                revision=resolved,
                chain=chain,
                created_at=created_at,
                producer_id=producer_id,
                produced_by=produced_by,
            )
        )

    return ReportRevision(
        revision=resolved,
        document=document_receipt,
        manifest=manifest_receipt,
        forms=tuple(form_receipts),
    )


def _resolve_revision(workspace: Workspace, demanded: int | None) -> int:
    """The revision number to write, and the refusal when it is not allowed.

    A revision that has been written is **immutable**: the DOCX is a ZIP whose
    entries carry timestamps and the PDF carries a creation date, so a second
    render of revision 1 produces different bytes for the same revision
    number. Two artefacts claiming to be revision 1 with different hashes is
    exactly the ambiguity the revision number exists to prevent, so a revision
    that is not beyond every revision already written is refused.
    """
    written = existing_revisions(workspace)
    highest = max(written, default=0)
    if demanded is None:
        return highest + 1
    if demanded < 1:
        raise ReportRevisionRefusedError(
            f"revision {demanded} is not a revision number. The receipt's own "
            "model counts revisions from one, and a revision numbered zero would "
            "be a revision with no first."
        )
    if demanded <= highest:
        raise ReportRevisionRefusedError(
            f"revision {demanded} is not beyond the highest revision this task has "
            f"({highest}). A revision is immutable once written: re-rendering it "
            "would produce different bytes for the same revision number -- a DOCX "
            "is a ZIP whose entries carry timestamps and a PDF carries a creation "
            "date -- and two artefacts claiming to be revision "
            f"{demanded} with different hashes is exactly the ambiguity the "
            "revision number exists to prevent. Write revision "
            f"{highest + 1} instead."
        )
    return demanded


def _supplied_forms(forms: Mapping[ReportForm, bytes]) -> dict[ReportForm, bytes]:
    """The four forms, keyed by member, and the refusal when they are not four.

    The keys are normalised rather than trusted, so that a caller may use the
    plain strings ``"markdown"`` and friends — a :class:`ReportForm` is a
    string, and a mapping keyed by strings is the natural thing to hand over.
    """
    try:
        supplied = {ReportForm(form): data for form, data in forms.items()}
    except ValueError as error:
        raise ReportRevisionRefusedError(
            f"the forms are keyed by something that is not a report form: {error}. "
            "A revision is written in four known forms, and a form the "
            "repository cannot name is a form nobody can serve."
        ) from error
    missing = [form.value for form in ReportForm if form not in supplied]
    if missing:
        raise ReportRevisionRefusedError(
            f"the forms are missing {missing}. A revision is the canonical "
            "document, the manifest and the four rendered forms, and a revision "
            "missing a form is a revision nobody can open in that form."
        )
    return supplied


def _assert_the_manifest_is_the_one_the_chain_names(
    manifest: ReportManifest,
    receipt: ArtifactReceipt,
    chain: tuple[DerivationRef, ...],
) -> None:
    """The chain's manifest link must name the manifest that was written.

    The chain's link is built from the manifest's canonical bytes before
    anything is written, and the receipt's hash is taken over the bytes on
    disk. They are the same bytes, so this cannot fail — and that is exactly
    why it is worth saying out loud: a chain that named a manifest nobody
    wrote would leave the report's lineage pointing at bytes that are not
    there, and nothing downstream would notice.
    """
    named = next(
        (
            reference.content_sha256
            for reference in chain
            if reference.target_kind is DerivationTargetKind.ARTIFACT
            and reference.target_id == receipt.receipt_id
        ),
        None,
    )
    if named != receipt.content_sha256:
        raise ReportRevisionRefusedError(
            f"the chain names the manifest as {named!r}, but the manifest that was "
            f"written hashes to {receipt.content_sha256!r}. The report's lineage "
            "would point at bytes that are not there."
        )


def _receipt(
    workspace: Workspace,
    write: WriteReceipt,
    *,
    receipt_id: str,
    kind: ArtifactKind,
    media_type: str,
    revision: int,
    chain: tuple[DerivationRef, ...],
    created_at: datetime,
    producer_id: str,
    produced_by: ArtifactProducerKind,
) -> ArtifactReceipt:
    """The receipt for one artefact, from the write that produced it.

    The hash and the size are the writer's own, taken over the bytes on disk,
    so the receipt and the file cannot disagree.
    """
    return ArtifactReceipt(
        receipt_id=receipt_id,
        task_id=str(workspace.task_id),
        kind=kind,
        relative_path=write.absolute_path.relative_to(workspace.selected_root).as_posix(),
        content_sha256=write.content_hash,
        size_bytes=write.size_bytes,
        revision=revision,
        produced_by=produced_by,
        producer_id=producer_id,
        derived_from=chain,
        media_type=media_type,
        created_at=created_at,
    )


def _receipt_id(task_id: str, revision: int, part: str) -> str:
    """The id of one artefact of one revision.

    Derived from the task and the revision rather than minted, so that the
    revision's six artefacts carry **one identity**: the task and the
    revision. A minted id would make a second write of the same revision look
    like six new artefacts, and the ledger's upsert would then hold two sets of
    receipts claiming one revision number — which is the ambiguity the
    revision number exists to prevent, arrived at from the other side.
    """
    return f"{task_id}-r{revision}-{part}"


def _revision_key(revision: int, filename: str) -> str:
    """The key one artefact of one revision is written under.

    The revision is in the path, which is what lets two revisions coexist:
    the second is a new set of files beside the first, and the first is never
    touched.
    """
    return f"{REPORT_DIR}/v{revision}/{filename}"


def _workspace_relative(workspace: Workspace, key: str) -> str:
    """The key's path in the workspace, as a receipt records it.

    Workspace-relative and POSIX-separated, because a stored path has to
    resolve on the reader's machine rather than pointing at the machine that
    produced it.
    """
    return (workspace.output_root.path / key).relative_to(workspace.selected_root).as_posix()


__all__ = [
    "DEFAULT_REVISION_PRODUCER_ID",
    "DOCUMENT_FILENAME",
    "DOCUMENT_MEDIA_TYPE",
    "MANIFEST_FILENAME",
    "REPORT_DIR",
    "ReportForm",
    "ReportRevision",
    "ReportRevisionRefusedError",
    "existing_revisions",
    "report_chain",
    "write_report_revision",
]
