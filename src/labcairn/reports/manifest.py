"""``ReportManifest`` — the list of what a report is made of.

LC-P1-11's artefact manifest is the document that says *what the report is
made of*: every figure, every table, and the report document itself, each
with where it is, what it hashes to, and what it was made from. It is what
makes a report **checkable** — a reader who has the manifest can name the
part that changed, and a reader who has the report can recompute the digest
that ties the two together.

Not to be confused with :mod:`labcairn.analysis.manifest`. That module is
**one computation's** manifest — the derivation of a single number, which
the report model holds by value inside each figure. This one is **a report's**
manifest: the list of what the report is made of. The two share a name and
nothing else.

The form, and why it is this form
---------------------------------
**The manifest is a document with canonical bytes of its own; the receipt is
the record that points at it.** :class:`~labcairn.reports.receipt.ArtifactReceipt`
already reserves ``ArtifactKind.MANIFEST`` for this, and the receipt is what
the ledger stores — so there is no new table and no migration. The manifest
is written as a file, the receipt names that file and hashes it, and the
receipt's ``derived_from`` names the parts.

This is the relation the task breakdown's §2.2 describes — *"the manifest
lists the model's parts and the receipt records the manifest's hash"* — and it
is the only form that works: a manifest that cannot be hashed cannot be the
thing a receipt's hash points at. The alternative, a receipt that *is* the
manifest, would put the parts list in ``derived_from`` and leave the report's
own digest with nowhere to go but the receipt's ``content_sha256`` — which is
the hash of the receipt, not of the report.

The receipt's chain is an **ancestor closure**
----------------------------------------------
The receipt's ``derived_from`` names the parts **and** the parts' own
upstream, in one flat list. That shape is deliberate, and it is the shape the
whole report lineage should take: the staleness walk
(:meth:`labcairn.recovery.resume.ResumeCoordinator.invalidate_on_source_change`)
is **one hop** — an artefact is marked stale only when its *own*
``derived_from`` names the changed hash — so a chain that named only its
immediate parent would never see the material underneath it move. The closure
is what makes the report's lineage one line of hashes from the material to
the exported file, and it is why the chain is assembled before anything is
written: a chain that contradicts itself is refused before a byte lands.

The five rules, and what each one costs
---------------------------------------
**1. The manifest is built *from* the document, not assembled beside it.**
Every **figure's** and **table's** path and hash is read out of the
:class:`~labcairn.reports.model.ReportDocument` the manifest describes, and
the document part's hash is the digest of that document's canonical bytes. A
manifest assembled from a parallel description is a second spelling of the
report, and the second spelling is the one that goes stale. *The cost:* the
builder can only record what the document knows — and a table in the report
model is a fact about a file, so the table's **upstream** has to be handed to
the builder. The report does not say what computed a table, and nothing else
does either. The document part's **path** is the one thing the builder cannot
derive at all, and it is the caller's to name.

**2. The report's own digest is over its canonical bytes** — the model's
:meth:`~labcairn.reports.model.ReportDocument.canonical_bytes` — so the
manifest's line for the document is a hash a reader can recompute from the
model rather than one they have to take on trust.

**3. Each part's lineage names its upstream.** A figure names the
reproducibility manifest that describes it; a table names what produced it;
the document names the parts **and the sources the report's claims were
read from**. The links are
:class:`~labcairn.reports.receipt.DerivationRef` objects rather than a new
type, because that model already carries the rule this manifest needs: a
link to an artefact or a material file **must** carry a hash, because a chain
link with no hash is a link nothing can invalidate.

**The document's own material is named here, and not left to the caller.**
The parts of a report say what produced them, and that is how the material
reached the chain — but a report with **no parts** says nothing at all about
what it rests on, and the staleness walk is one hop: a receipt is marked only
when its own ``derived_from`` names the changed hash. A report whose chain
named nothing but its own files could therefore never be marked stale, and
nothing would have noticed. The material is read out of the document's own
citations, so it is named whether the report has parts or not.

**4. The manifest is a document with canonical bytes of its own**, so it can
be hashed, and so a receipt's hash has something to point at.

**5. The manifest records what the report is made of, and nothing else.** It
carries no narrative, no checks and no interpretation. A manifest that
carries content is a second copy of the content, and the copy is the one that
goes stale.

What the manifest does not know, and does not guess
---------------------------------------------------
Two things in a part's line are **not** derived from the report, and both are
named in the builder's signature rather than invented inside it:

* **Where the report's canonical bytes are written.** The report model
  carries no path, so the caller names it. It is a location and not a fact
  about the content: the hash beside it is computed, never supplied.
* **What produced each table.** A table in the report model is a path and a
  hash, and a path and a hash do not say what made them. The builder
  **refuses** a table with no upstream rather than recording a blank, because
  a table that names no upstream is a table nobody can say is current.

A figure needs neither, because the report model holds the figure's
reproducibility manifest by value: the figure's upstream is *in* the
document, and the manifest's canonical bytes can be hashed from there. A
caller may still hand the builder an extra upstream for a figure — the
manifest receipt id of the artefact that holds the figure's manifest, say —
and those links are recorded **after** the figure's own manifest link, so
that the figure's lineage still reads from the manifest outwards.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Final, Self

from pydantic import ValidationError, model_validator

from labcairn.analysis.manifest import manifest_bytes
from labcairn.core.schema import LabCairnModel
from labcairn.reports.model import ReportDocument
from labcairn.reports.receipt import (
    ArtifactKind,
    ArtifactProducerKind,
    ArtifactReceipt,
    DerivationRef,
    DerivationTargetKind,
)
from labcairn.sources.primitives import ContentHash, NonEmptyText, WorkspaceRelativePath
from labcairn.workspace.outputs import TaskOutputArea
from labcairn.workspace.roots import Workspace

__all__ = [
    "DEFAULT_MANIFEST_PRODUCER_ID",
    "DOCUMENT_PART_ID",
    "ManifestPart",
    "ManifestPartKind",
    "ReportManifest",
    "ReportManifestRefusedError",
    "build_report_manifest",
    "manifest_chain",
    "write_report_manifest",
]

#: The id of the report document's own part.
#:
#: A constant rather than the report's title, because a title is *content*:
#: the manifest says what the report is made of, and what it is called is
#: one of the things it is made of. The manifest carries exactly one document
#: part, so the id only has to be unique within one manifest — and it has to
#: be distinct from every figure and table id, or a part would have two names.
DOCUMENT_PART_ID: Final[str] = "document"

#: Who produced the manifest, when the caller does not say.
#:
#: The module that builds the manifest is a true answer, and a receipt whose
#: producer names nothing is a receipt nobody can hold to anything.
DEFAULT_MANIFEST_PRODUCER_ID: Final[str] = "labcairn.reports.manifest"


class ReportManifestRefusedError(RuntimeError):
    """The manifest could not be built, and saying why is the whole answer.

    A refusal rather than a manifest with a blank in it. The alternatives are
    worse: a manifest whose table named no upstream would claim a table
    nobody could check, and one whose parts were assembled beside the report
    would be a second spelling of it. The project's rule is that an unknown is
    never a zero and a missing thing is never a blank -- here it is a
    refusal.
    """


class ManifestPartKind(StrEnum):
    """What a part of a report is.

    Closed, for the reason the report's block kinds are: a part that could be
    several things at once would be listed several ways, and "what is this
    report made of" would have no single answer.
    """

    #: A figure the report shows.
    FIGURE = "figure"
    #: A table the report includes.
    TABLE = "table"
    #: The report document itself.
    DOCUMENT = "document"


class ManifestPart(LabCairnModel):
    """One part of a report: where it is, what it holds, and what it came from.

    A **fact about a file**, not a copy of it. The bytes live in the
    workspace; the part says which bytes, and the hash is what makes the
    statement checkable later.

    ``lineage`` names the part's upstream, and it is a tuple of
    :class:`~labcairn.reports.receipt.DerivationRef` rather than a type of
    this module's own, because that model already carries the rule this
    manifest needs: a link to an artefact or a material file must carry a
    hash, since a chain link with no hash is a link nothing can invalidate.
    """

    #: The report's own name for this part. Unique within one manifest.
    part_id: NonEmptyText
    part_kind: ManifestPartKind
    #: Where the part's bytes are, workspace-relative and canonical.
    relative_path: WorkspaceRelativePath
    #: The hash of those bytes. Compared, never refreshed.
    content_sha256: ContentHash
    #: What the part was made from. At least one link for a figure or a
    #: table; the document's own lineage names the parts.
    lineage: tuple[DerivationRef, ...] = ()


class ReportManifest(LabCairnModel):
    """What a report is made of, and the digest that ties it to the report.

    The manifest is **about a report**, and it is not a copy of one. It holds
    a list of parts and one digest, and every part holds a path, a hash and a
    lineage. There is nowhere in it for the report's prose, its checks or its
    interpretation to go, and that is deliberate: a manifest that carries
    content is a second copy of the content, and the copy is the one that
    goes stale.

    The cross-checks below are the point of the model rather than
    decoration. A manifest with two document parts, a digest that is not the
    document's, a document that does not name the parts it lists, a part that
    names no upstream, and a lineage that names the same thing twice are all
    contradictions, and a document that could hold one is a document nobody
    can rely on.
    """

    #: The digest of the report document's canonical bytes.
    report_sha256: ContentHash
    #: The parts: the figures, the tables and the document itself. Sorted by
    #: :attr:`ManifestPart.part_id`, so two manifests of the same report have
    #: the same parts in the same order however they were gathered.
    parts: tuple[ManifestPart, ...]

    @model_validator(mode="after")
    def _there_is_one_document_part(self) -> Self:
        document_parts = [
            part for part in self.parts if part.part_kind is ManifestPartKind.DOCUMENT
        ]
        if len(document_parts) != 1:
            raise ValueError(
                f"the manifest holds {len(document_parts)} document parts. A "
                "manifest is about one report, and a manifest with two document "
                "parts would say which report it describes two ways."
            )
        return self

    @model_validator(mode="after")
    def _the_digest_is_the_document_parts_hash(self) -> Self:
        document_part = self._document_part()
        if document_part.content_sha256 != self.report_sha256:
            raise ValueError(
                f"the manifest records the report digest {self.report_sha256!r}, but "
                f"its document part hashes to {document_part.content_sha256!r}. The "
                "digest is the document's, and a manifest whose two answers differ "
                "would send a reader to look for bytes that are not there."
            )
        return self

    @model_validator(mode="after")
    def _the_parts_are_distinct(self) -> Self:
        repeated = _repeated(tuple(part.part_id for part in self.parts))
        if repeated:
            raise ValueError(
                f"the manifest names the same part twice: {repeated}. One part "
                "named twice is one part, and two rows for it make 'which part "
                "is this' answerable two ways."
            )
        return self

    @model_validator(mode="after")
    def _the_document_names_exactly_the_parts(self) -> Self:
        document_part = self._document_part()
        parts = {
            part.relative_path: part.content_sha256
            for part in self.parts
            if part is not document_part
        }
        named: dict[str, str | None] = {}
        for link in document_part.lineage:
            if link.target_kind is DerivationTargetKind.SOURCE:
                # A source is not a part. The document's lineage names the
                # parts of the report **and** the sources the report rests
                # on, and the two are told apart by their kind.
                continue
            if link.target_kind is not DerivationTargetKind.MATERIAL_FILE:
                raise ValueError(
                    f"the document names {link.target_id!r}, which is a "
                    f"{link.target_kind.value!r}. The document names the parts of "
                    "the report and the sources it rests on, and nothing else: a "
                    "part is a file with bytes in it, and a source is a file the "
                    "report was read from."
                )
            previous = named.get(link.target_id)
            if previous is not None and previous != link.content_sha256:
                raise ValueError(
                    f"the document names {link.target_id!r} twice, with different "
                    "bytes. One part is one file, and the manifest would be "
                    "recording two of them under one name."
                )
            named[link.target_id] = link.content_sha256

        missing = sorted(set(parts) - set(named))
        if missing:
            raise ValueError(
                f"the document does not name the part(s) {missing}. The document's "
                "lineage is the report's statement of what it is made of, and a "
                "part it does not name is a part a reader cannot check."
            )
        extra = sorted(set(named) - set(parts))
        if extra:
            raise ValueError(
                f"the document names the part(s) {extra}, which the manifest does "
                "not list. The document's lineage is the list of the parts, and a "
                "part it names that is not there makes the list unanswerable."
            )
        for path, digest in parts.items():
            if named[path] != digest:
                raise ValueError(
                    f"the document names {path!r} with hash {named[path]!r}, but "
                    f"the part it lists hashes to {digest!r}. A part named with "
                    "other bytes than the part's is a name for something else."
                )
        return self

    @model_validator(mode="after")
    def _every_part_names_its_upstream(self) -> Self:
        for part in self.parts:
            if part.part_kind is ManifestPartKind.DOCUMENT:
                continue
            if not part.lineage:
                raise ValueError(
                    f"the {part.part_kind.value!r} {part.part_id!r} names no "
                    "upstream. A part that says what it was made from can be "
                    "checked against it, and a part that says nothing can only be "
                    "looked at."
                )
        return self

    @model_validator(mode="after")
    def _no_lineage_names_a_thing_twice(self) -> Self:
        for part in self.parts:
            seen: set[tuple[DerivationTargetKind, str]] = set()
            for link in part.lineage:
                key = (link.target_kind, link.target_id)
                if key in seen:
                    raise ValueError(
                        f"the {part.part_kind.value!r} {part.part_id!r} names "
                        f"{link.target_id!r} twice. One upstream thing cited twice "
                        "is one dependency, and listing it twice makes 'how many "
                        "inputs' answerable two ways."
                    )
                seen.add(key)
        return self

    def _document_part(self) -> ManifestPart:
        """The one document part.

        The count guard, :meth:`_there_is_one_document_part`, runs first and
        is the one that speaks in the code as written; this refusal is the
        belt to that braces, for a model that reaches this method by a path
        that does not run the count guard. It is raised rather than asserted
        because a validator that asserts can be made to fail the wrong way.

        Its wording differs from the count guard's **on purpose**. The count
        guard's message is a published behaviour and the test suite pins it,
        so a belt that said the same thing would answer for a count guard
        that had stopped working: the manifest would still be refused, the
        message would still match, and nothing would have noticed that the
        first guard was gone.
        """
        document_parts = [
            part for part in self.parts if part.part_kind is ManifestPartKind.DOCUMENT
        ]
        if len(document_parts) != 1:
            raise ValueError(
                f"the manifest has no single document part to answer for: it holds "
                f"{len(document_parts)} of them."
            )
        return document_parts[0]

    def canonical_bytes(self) -> bytes:
        """The manifest's bytes: the canonical JSON, encoded as UTF-8.

        These are the bytes that are written and the bytes that are hashed, so
        the receipt's ``content_sha256`` is the hash of exactly this document
        and not of something like it.
        """
        return self.json_canonical().encode("utf-8")


def build_report_manifest(
    *,
    document: ReportDocument,
    document_relative_path: str,
    upstreams: Mapping[str, tuple[DerivationRef, ...]] | None = None,
) -> ReportManifest:
    """Build the manifest for one report document.

    Every part's path and hash is read out of *document*, and the report's own
    digest is the digest of that document's canonical bytes. Nothing here is
    assembled beside the report.

    **The document part names the report's parts and the report's material.**
    The parts are the files the report includes; the material is the sources
    its claims were read from, and it is read out of the document's own
    citations — see :func:`_the_material`. It is named here rather than left
    to the caller because the report's chain is what the staleness walk reads,
    and a report that named nothing but its own files could never be marked
    stale when the material moved.

    :param document: the report the manifest describes.
    :param document_relative_path: where the report's **canonical document
        bytes** are written — workspace-relative and canonical. The rendered
        report (Markdown, HTML, DOCX, PDF) is a different artefact with its
        own receipt; this manifest describes the document the renderers draw
        from. The path is the one thing in the manifest the builder cannot
        derive, and it is a location rather than a fact about the content:
        the hash beside it is computed.
    :param upstreams: what produced each part, by part id. A **table** must
        have one: the report model carries a table as a path and a hash, and
        a path and a hash do not say what computed them. A figure's upstream
        is not asked for, because the document holds the figure's
        reproducibility manifest and that manifest is the figure's upstream;
        links supplied for a figure are added after it.
    :raises ReportManifestRefusedError: when a part is named twice, when a
        table names no upstream, when an upstream names a part the report does
        not carry, when two claims cite one source with different bytes, or
        when the manifest would contradict itself.
    """
    supplied: Mapping[str, tuple[DerivationRef, ...]] = upstreams or {}

    figure_ids = {figure.figure_id for figure in document.figures}
    table_ids = {table.table_id for table in document.tables}
    shared = sorted(figure_ids & table_ids)
    if shared:
        raise ReportManifestRefusedError(
            f"the report names the part {shared} both as a figure and as a table. "
            "The manifest names its parts by id, and one id that means two parts "
            "would make 'which part is this' answerable two ways."
        )

    unknown = sorted(set(supplied) - figure_ids - table_ids)
    if unknown:
        raise ReportManifestRefusedError(
            f"the upstream names the part(s) {unknown}, which the report does not "
            "carry. An upstream for a part that is not in the report describes a "
            "report nobody wrote."
        )

    report_sha256 = _digest_bytes(document.canonical_bytes())

    unnamed_tables = sorted(
        table.table_id for table in document.tables if not supplied.get(table.table_id)
    )
    if unnamed_tables:
        raise ReportManifestRefusedError(
            f"the table(s) {unnamed_tables} name no upstream. The report model "
            "carries a table as a fact about a file, and the file does not say "
            "what computed it; a manifest that records a table with no upstream "
            "cannot say whether the table is still the one the report used."
        )

    material = _the_material(document)

    try:
        figure_parts = tuple(
            ManifestPart(
                part_id=figure.figure_id,
                part_kind=ManifestPartKind.FIGURE,
                relative_path=figure.relative_path,
                content_sha256=figure.content_sha256,
                lineage=(
                    DerivationRef(
                        target_kind=DerivationTargetKind.ARTIFACT,
                        target_id=_figure_manifest_id(figure.figure_id),
                        content_sha256=_digest_bytes(manifest_bytes(figure.manifest)),
                    ),
                    *supplied.get(figure.figure_id, ()),
                ),
            )
            for figure in document.figures
        )
        table_parts = tuple(
            ManifestPart(
                part_id=table.table_id,
                part_kind=ManifestPartKind.TABLE,
                relative_path=table.relative_path,
                content_sha256=table.content_sha256,
                lineage=supplied.get(table.table_id, ()),
            )
            for table in document.tables
        )

        other_parts = (*figure_parts, *table_parts)
        document_part = ManifestPart(
            part_id=DOCUMENT_PART_ID,
            part_kind=ManifestPartKind.DOCUMENT,
            relative_path=document_relative_path,
            content_sha256=report_sha256,
            lineage=(
                *(
                    DerivationRef(
                        target_kind=DerivationTargetKind.MATERIAL_FILE,
                        target_id=part.relative_path,
                        content_sha256=part.content_sha256,
                    )
                    for part in other_parts
                ),
                *material,
            ),
        )

        parts = tuple(sorted((*other_parts, document_part), key=lambda part: part.part_id))
        return ReportManifest(report_sha256=report_sha256, parts=parts)
    except ValidationError as error:
        raise ReportManifestRefusedError(
            f"the manifest could not be built from these facts: {error}. A "
            "manifest that contradicts itself is not a manifest with a blank in "
            "it -- it is a document whose parts disagree, and a reader would have "
            "no way to tell which part to believe."
        ) from error


def _the_material(document: ReportDocument) -> tuple[DerivationRef, ...]:
    """The sources the report's claims were read from, one link each.

    **The report's own material.** The *parts* of a report name their own
    upstream — a table names what computed it, a figure names its
    reproducibility manifest — and that is how the material used to reach
    the chain. A report with **no parts** therefore named nothing but its
    own files, and the staleness walk is one hop: a receipt is marked only
    when its *own* ``derived_from`` names the changed hash. Such a report
    could never be marked stale, and nothing would have noticed.

    So the material is read out of the document itself. A claim rests on
    the bytes its citation names, and those bytes are the source's: one
    link per source, carrying the hash the claim was read from, so that
    the walk has something to match.

    The kind is ``source`` and not ``material_file`` because the link
    points at a source the ledger holds — a file with a row of its own —
    and because the two kinds are told apart in the document's lineage:
    the parts are the files the report includes, and the sources are the
    files the report was read from.

    :raises ReportManifestRefusedError: when two claims cite the same
        source with different bytes. That is one source under two
        versions, and the chain would name it twice with two hashes — the
        walk would then mark the report for one of them and leave it
        current for the other.
    """
    footnotes = {footnote.footnote_id: footnote for footnote in document.footnotes}
    material: dict[str, str] = {}
    for claim in document.claims:
        for footnote_id in claim.footnote_ids:
            footnote = footnotes.get(footnote_id)
            if footnote is None:
                # The model refuses a claim that cites a citation the
                # report does not carry, so a document that reaches here
                # has one. Skipping it keeps this a reader of the
                # document rather than a second validator of it.
                continue
            previous = material.get(footnote.source_id)
            if previous is not None and previous != footnote.content_sha256:
                raise ReportManifestRefusedError(
                    f"the report cites the source {footnote.source_id!r} twice, with "
                    f"different bytes: one reading of it hashes to {previous!r} and "
                    f"another to {footnote.content_sha256!r}. One source is one "
                    "dependency, and a chain that named it under two hashes would "
                    "mark the report for one of them and leave it current for the "
                    "other."
                )
            material[footnote.source_id] = footnote.content_sha256
    return tuple(
        DerivationRef(
            target_kind=DerivationTargetKind.SOURCE,
            target_id=source_id,
            content_sha256=digest,
        )
        for source_id, digest in sorted(material.items())
    )


def write_report_manifest(
    workspace: Workspace,
    *,
    key: str,
    manifest: ReportManifest,
    receipt_id: str,
    created_at: datetime,
    producer_id: str = DEFAULT_MANIFEST_PRODUCER_ID,
    produced_by: ArtifactProducerKind = ArtifactProducerKind.STAGE,
    revision: int = 1,
) -> ArtifactReceipt:
    """Write the manifest and return the receipt that records it.

    The file goes through :class:`labcairn.workspace.outputs.TaskOutputArea`,
    which is the only thing in this codebase that writes a file: atomic,
    output-root-only, and it reports what it did. A builder that opened its
    own file would bypass all of that. The receipt's ``content_sha256`` is
    the writer's own hash of the bytes on disk, so the receipt and the file
    cannot disagree.

    The chain is assembled **before** the file is written, so that a manifest
    whose chain contradicts itself is refused without leaving a file behind:
    a generated file with no receipt is an artefact nothing can account for.
    """
    chain = manifest_chain(manifest)
    outputs = TaskOutputArea(workspace)
    write = outputs.write(key, manifest.canonical_bytes())
    relative_path = write.absolute_path.relative_to(workspace.selected_root).as_posix()
    return ArtifactReceipt(
        receipt_id=receipt_id,
        task_id=str(workspace.task_id),
        kind=ArtifactKind.MANIFEST,
        relative_path=relative_path,
        content_sha256=write.content_hash,
        size_bytes=write.size_bytes,
        revision=revision,
        produced_by=produced_by,
        producer_id=producer_id,
        derived_from=chain,
        media_type="application/json",
        created_at=created_at,
    )


def manifest_chain(manifest: ReportManifest) -> tuple[DerivationRef, ...]:
    """The receipt's chain: the parts, and the parts' own upstream.

    An **ancestor closure**, in one flat list. Each part contributes a link
    to its own bytes, and each part's lineage contributes its upstream links.
    The closure is what the one-hop staleness walk needs: it compares the
    hashes in an artefact's *own* ``derived_from``, so a chain that stopped
    at the immediate parent would never see the material underneath it move.

    A link named twice is kept once — one upstream thing cited twice is one
    dependency — but two links that name the same thing with **different**
    hashes are a contradiction, and the chain refuses rather than picking
    one. The refusal is not decoration: a chain that named one file under
    two hashes would mark the report stale for one of them and current for
    the other, and a reader would have no way to tell which was meant.

    :raises ReportManifestRefusedError: when one upstream is named twice with
        different hashes.
    """
    links: list[DerivationRef] = []
    seen: dict[tuple[DerivationTargetKind, str], str | None] = {}
    for part in manifest.parts:
        candidates = (
            DerivationRef(
                target_kind=DerivationTargetKind.MATERIAL_FILE,
                target_id=part.relative_path,
                content_sha256=part.content_sha256,
            ),
            *part.lineage,
        )
        for link in candidates:
            key = (link.target_kind, link.target_id)
            if key in seen:
                if seen[key] != link.content_sha256:
                    raise ReportManifestRefusedError(
                        f"the chain names {link.target_id!r} twice with different "
                        "hashes. One upstream thing is one dependency, and the "
                        "chain would be recording two of them under one name."
                    )
                continue
            seen[key] = link.content_sha256
            links.append(link)
    return tuple(links)


def _figure_manifest_id(figure_id: str) -> str:
    """The name a figure's own reproducibility manifest is given.

    A reproducibility manifest carries no id of its own, so the figure is
    what names it: ``fig-1.manifest`` is "the manifest that describes
    fig-1". The link's hash is the digest of that manifest's canonical bytes,
    so one manifest is distinguishable from another, and a reader who has the
    manifest in hand can recompute it.
    """
    return f"{figure_id}.manifest"


def _digest_bytes(data: bytes) -> str:
    """The SHA-256 of *data*, lowercase hex.

    The same definition the ledger's file hash takes
    (:func:`labcairn.security.approval.content_hash`), over bytes in memory
    rather than over a file: a report's canonical bytes may never have been
    written to disk, and a hash that needed a file could not describe them.
    """
    return hashlib.sha256(data).hexdigest()


def _repeated(values: tuple[str, ...]) -> list[str]:
    """The values that appear more than once, in the order they first repeat."""
    seen: set[str] = set()
    repeated: list[str] = []
    for value in values:
        if value in seen:
            if value not in repeated:
                repeated.append(value)
        else:
            seen.add(value)
    return repeated
