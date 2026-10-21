"""The report's revisions: what one is, and what makes it stale.

LC-P1-11's T03 makes two claims true, and they are tested here the way they
are judged: **every rule needs a test that fails when the rule is broken.**

* **"Revisions keep v1 and generate v2 without altering originals."** So the
  tests below write v1, write v2, and then check that v1's *bytes* are still
  the bytes v1's receipts describe. A test that only compared the receipt
  numbers would pass against an implementation that overwrote v1's file and
  left the receipt alone — which is the defect the work order names.
* **"Re-rendering after a material change invalidates stale output."** So the
  staleness tests drive the repository's own walk —
  :meth:`labcairn.recovery.resume.ResumeCoordinator.invalidate_on_source_change`
  — and check that the report, the manifest and the figure are all marked in
  **one pass**. The claim is not "my code noticed the change"; the claim is
  "the ledger noticed, and my chain let it reach the report".

**The chain is the load-bearing part.** The walk is one hop: it marks an
artefact stale when *that artefact's* ``derived_from`` names a changed hash.
A report receipt naming only the manifest would therefore never be marked
when the *source* changed, and the report would sit there saying ``CURRENT``
about bytes whose material had moved. So the tests below assert that the
material's hash is in the report's **own** chain — not merely somewhere in the
ledger — because that is the difference between a report that can go stale and
one that cannot.

The material is written **without its mtime moving** in the staleness tests.
A normal edit would also pass against an implementation comparing timestamps,
which would make the test evidence for a rule the code does not implement.

Nothing in this file is a placeholder for a later task's test: the renderers
(T01) and the content checks (T04) have their own.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from test_recovery_support import Scenario, build_scenario
from test_store_support import StoreEnv
from test_store_support import env as _shared_env

from labcairn.analysis.manifest import (
    FileRef,
    RenderEnvironment,
    ReproducibilityManifest,
    canonical_digest,
)
from labcairn.core.ids import TaskId, new_id
from labcairn.evidence.states import EvidenceKind, VerificationStatus
from labcairn.recovery import STALE_REASON, MaterialResolver
from labcairn.reports.manifest import DOCUMENT_PART_ID, ReportManifest, build_report_manifest
from labcairn.reports.model import (
    ClaimBlock,
    FigureBlock,
    LedgerRecordView,
    LedgerSnapshot,
    ProvenanceFootnote,
    ReportClaim,
    ReportDocument,
    ReportFigure,
    ReportSection,
    ReportTable,
    TableBlock,
)
from labcairn.reports.receipt import (
    ArtifactKind,
    ArtifactProducerKind,
    ArtifactReceipt,
    ArtifactStaleness,
    DerivationRef,
    DerivationTargetKind,
)
from labcairn.reports.revisions import (
    ReportForm,
    ReportRevision,
    ReportRevisionRefusedError,
    existing_revisions,
    report_chain,
    write_report_revision,
)
from labcairn.runtime.event import EventType
from labcairn.sources.locators import ComputationLocator, PdfLocator
from labcairn.workspace.roots import Workspace

#: The store fixture, re-exported under the name pytest looks for.
#:
#: It lives in ``test_store_support`` because LC-P1-05 owns it, and a fixture
#: that has to be imported under another name is a fixture this file cannot
#: reason about; so it is imported once, here, and named.
env = _shared_env

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


def _hash(marker: str) -> str:
    """A well-formed content hash for *marker*.

    Derived from the marker rather than written out, so that two different
    hashes in one test are visibly different hashes and a test that expects
    a *mismatch* cannot pass by accident.
    """
    return hashlib.sha256(marker.encode("utf-8")).hexdigest()


#: The bytes the report's material had when it was read.
SOURCE_HASH: str = _hash("source")
#: The bytes of the figure artefact.
FIGURE_HASH: str = _hash("figure")
#: The bytes of the table artefact.
TABLE_HASH: str = _hash("table")
#: The bytes of the recipe the figure was made with.
RECIPE_HASH: str = _hash("recipe")

#: Where the figure artefact is.
FIGURE_PATH: str = "outputs/figures/fig-1.svg"
#: Where the table artefact is.
TABLE_PATH: str = "outputs/tables/tab-1.csv"
#: Where the material the table was computed from is.
MATERIAL_PATH: str = "material/exp1.csv"
#: Where the source the claims were read from is.
#:
#: A different file from the material above, and for a different reason:
#: the material is what the *table* was computed from, and the source is
#: what the *claims* were read from. A report that carries only claims
#: rests on the source and on nothing else.
SOURCE_PATH: str = "materials/one.pdf"

#: The caption of the figure.
CAPTION: str = "Mean yield across the five measured runs."

#: The four rendered forms, as bytes.
#:
#: Real renderers belong to T01; this file is about what the revision does
#: with the four forms it is given, so the bytes here only have to be
#: distinguishable from one another — and they are, so a test that expects one
#: form's bytes cannot pass by reading another's file.
FORM_BYTES: dict[ReportForm, bytes] = {
    ReportForm.MARKDOWN: b"# A first-pass report\n\nThe material reports a yield of 4.253%.\n",
    ReportForm.HTML: b"<html><body><p>The material reports a yield of 4.253%.</p></body></html>",
    ReportForm.DOCX: b"PK\x03\x04\x00\x00the docx form",
    ReportForm.PDF: b"%PDF-1.7\n%the pdf form\n",
}


def _figure_manifest(*, source_hash: str = SOURCE_HASH) -> ReproducibilityManifest:
    """A valid reproducibility manifest for the figure.

    Built through the manifest's own fields rather than through
    :func:`labcairn.analysis.manifest.build_manifest`, because the builder
    wants a source on disk and a workspace, and neither is what this file is
    about.
    """
    output: dict[str, Any] = {"mean": 4.253, "n_used": 5}
    selection: dict[str, Any] = {
        "source_id": "src-1",
        "content_sha256": source_hash,
        "columns": ["yield"],
        "rows": {"kind": "range", "start": 1, "end": 5},
        "missing": "exclude",
    }
    return ReproducibilityManifest(
        input_file=FileRef(relative_path=MATERIAL_PATH, content_sha256=source_hash),
        operator="labcairn.analysis.mean@1.0.0",
        locator=ComputationLocator(
            operator_id="labcairn.analysis.mean",
            operator_version="1.0.0",
            parameters={"selection": selection, "column": "yield"},
            input_hashes=(source_hash,),
        ),
        recipe=FileRef(relative_path="recipes/mean.py", content_sha256=RECIPE_HASH),
        output=output,
        output_sha256=canonical_digest(output),
        environment=RenderEnvironment(
            matplotlib_version="3.11.2",
            svg_hashsalt="labcairn",
            font_families=("sans-serif",),
            platform="TestOS-1.0",
        ),
    )


def _document(
    *,
    as_of: datetime,
    source_hash: str = SOURCE_HASH,
) -> ReportDocument:
    """A valid document with a figure and a table.

    The source hash is a parameter because a *second* run over a changed
    ledger must be a **different document** — that is what makes the second
    revision a new artefact rather than a new version of the old bytes.
    """
    record = LedgerRecordView(
        record_id="rec-1",
        record_kind=EvidenceKind.NUMERIC,
        value=4.253,
        unit="%",
        status=VerificationStatus.VERIFIED_BY_RULE,
        anchor_ids=("anc-1",),
        source_content_hash=source_hash,
    )
    footnote = ProvenanceFootnote(
        footnote_id="fn-1",
        source_id="src-1",
        locator=PdfLocator(page=3),
        content_sha256=source_hash,
    )
    figure = ReportFigure(
        figure_id="fig-1",
        relative_path=FIGURE_PATH,
        content_sha256=FIGURE_HASH,
        caption=CAPTION,
        manifest=_figure_manifest(source_hash=source_hash),
    )
    table = ReportTable(
        table_id="tab-1",
        relative_path=TABLE_PATH,
        content_sha256=TABLE_HASH,
    )
    return ReportDocument(
        title="A first-pass report",
        snapshot=LedgerSnapshot(as_of=as_of, record_ids=("rec-1",)),
        sections=(
            ReportSection(
                section_id="sec-1",
                heading="Findings",
                blocks=(
                    ClaimBlock(claim_id="clm-1"),
                    FigureBlock(figure_id="fig-1"),
                    TableBlock(table_id="tab-1"),
                ),
            ),
        ),
        claims=(ReportClaim(claim_id="clm-1", record=record, footnote_ids=("fn-1",)),),
        figures=(figure,),
        tables=(table,),
        footnotes=(footnote,),
    )


def _claims_only_document(
    *,
    as_of: datetime,
    source_hash: str = SOURCE_HASH,
) -> ReportDocument:
    """A valid document with one claim, and **no figure and no table**.

    The shape the report path had no answer for. Every other staleness
    test in this file builds a document with a figure, and the figure's
    receipt names the material — so the material reached the chain through
    the *parts*, and a report with no parts had no way to name it at all.

    A report is not obliged to carry a figure or a table: a task whose
    records can be stated produces a report of claims, and that report
    rests on the source its claims were read from.
    """
    record = LedgerRecordView(
        record_id="rec-1",
        record_kind=EvidenceKind.NUMERIC,
        value=4.253,
        unit="%",
        status=VerificationStatus.VERIFIED_BY_RULE,
        anchor_ids=("anc-1",),
        source_content_hash=source_hash,
    )
    footnote = ProvenanceFootnote(
        footnote_id="fn-1",
        source_id="src-1",
        locator=PdfLocator(page=3),
        content_sha256=source_hash,
    )
    return ReportDocument(
        title="A first-pass report",
        snapshot=LedgerSnapshot(as_of=as_of, record_ids=("rec-1",)),
        sections=(
            ReportSection(
                section_id="sec-1",
                heading="Findings",
                blocks=(ClaimBlock(claim_id="clm-1"),),
            ),
        ),
        claims=(ReportClaim(claim_id="clm-1", record=record, footnote_ids=("fn-1",)),),
        figures=(),
        tables=(),
        footnotes=(footnote,),
    )


def _upstream(*, content_sha256: str = SOURCE_HASH) -> DerivationRef:
    """What produced the table: the material it was computed from.

    This is the link that carries the **material's hash** into the chain, and
    so the link that lets the one-hop staleness walk reach the report at all.
    """
    return DerivationRef(
        target_kind=DerivationTargetKind.MATERIAL_FILE,
        target_id=MATERIAL_PATH,
        content_sha256=content_sha256,
    )


def _accepts(document: ReportDocument) -> None:
    """A verifier that accepts the document.

    The content checks are T04's, and this file is about what the revision
    does with a document that has been checked. What matters here is that the
    verifier is **called** and that its answer is obeyed.
    """
    del document


def _refuses(document: ReportDocument) -> None:
    """A verifier that refuses the document, as T04's checks would.

    Raised as a plain :class:`ValueError` because the point is not which
    exception the checks use but that *any* refusal stops the write.
    """
    del document
    msg = "the ledger says 4.5 and the report says 4.253"
    raise ValueError(msg)


def _workspace(tmp_path: Path) -> Workspace:
    """A workspace with one task, for the writer."""
    return Workspace.bind(tmp_path, task_id=TaskId(new_id()))


def _write(
    workspace: Workspace,
    document: ReportDocument,
    *,
    created_at: datetime,
    revision: int | None = None,
    upstreams: dict[str, tuple[DerivationRef, ...]] | None = None,
    source_hash: str = SOURCE_HASH,
    verify: Any = _accepts,
) -> ReportRevision:
    """Write one revision, with the table's upstream supplied unless told not to.

    The upstream names the material by **hash**, so the hash has to be the one
    the material actually has — hence the parameter. A test that built the
    chain with a hash the material does not have would be testing a report
    that could never go stale, and would pass for the wrong reason.

    ``verify`` is typed as ``Any`` here only so that a test may pass a
    refusing verifier; the writer's own signature is the strict one.
    """
    supplied = (
        {"tab-1": (_upstream(content_sha256=source_hash),)} if upstreams is None else upstreams
    )
    return write_report_revision(
        workspace,
        document=document,
        forms=FORM_BYTES,
        verify=verify,
        upstreams=supplied,
        revision=revision,
        created_at=created_at,
    )


def _named(receipt: ArtifactReceipt) -> dict[tuple[DerivationTargetKind, str], str | None]:
    """The receipt's chain, by what each link names."""
    return {
        (link.target_kind, link.target_id): link.content_sha256 for link in receipt.derived_from
    }


def _record(scenario: Scenario, receipts: tuple[ArtifactReceipt, ...]) -> None:
    """Put receipts in the ledger, the way the application layer would."""
    with scenario.store().unit(scenario.task_id) as work:
        for receipt in receipts:
            work.emit(EventType.ARTIFACT_RECORDED)
            work.put_artifact(receipt, run_id=scenario.run_id)


def _rewrite_preserving_mtime(path: Path, body: bytes) -> None:
    """Replace the bytes and put the mtime back where it was.

    The load-bearing trick of the invalidation tests. Without it a
    timestamp-based implementation would also pass, and the test would be
    evidence for a rule the code does not implement.
    """
    original = path.stat().st_mtime_ns
    path.write_bytes(body)
    os.utime(path, ns=(original, original))
    assert path.stat().st_mtime_ns == original, "the mtime must look untouched"


# ---------------------------------------------------------------------------
# What one revision is
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_a_revision_is_six_receipts_sharing_one_revision_number_and_one_task(
    tmp_path: Path, frozen_now: datetime
) -> None:
    """Six receipts, one revision number, one identity: the task and the revision.

    Not five and not seven. The number is the work order's: the canonical
    document, the manifest, and the four rendered forms.
    """
    workspace = _workspace(tmp_path)

    revision = _write(workspace, _document(as_of=frozen_now), created_at=frozen_now)

    assert len(revision.receipts) == 6
    assert {receipt.revision for receipt in revision.receipts} == {1}
    assert {receipt.task_id for receipt in revision.receipts} == {str(workspace.task_id)}
    assert len({receipt.receipt_id for receipt in revision.receipts}) == 6, (
        "one identity means one name each: two receipts sharing an id would be "
        "one receipt to the ledger and two artefacts on the disk"
    )


@pytest.mark.unit
def test_every_artefact_is_written_under_a_path_that_carries_its_revision(
    tmp_path: Path, frozen_now: datetime
) -> None:
    """The revision is in the path, and that is what lets v1 and v2 coexist.

    A path that did not carry the revision would be a path that is
    overwritten, and "without altering originals" would be a promise rather
    than a property of the filesystem.
    """
    workspace = _workspace(tmp_path)

    revision = _write(workspace, _document(as_of=frozen_now), created_at=frozen_now)

    for receipt in revision.receipts:
        assert "/v1/" in receipt.relative_path, receipt.relative_path
        assert (tmp_path / receipt.relative_path).is_file()


@pytest.mark.unit
def test_each_receipt_hashes_exactly_the_bytes_that_were_written(
    tmp_path: Path, frozen_now: datetime
) -> None:
    """The receipt and the file cannot disagree, because the writer hashed what it wrote.

    A receipt whose hash was taken over some other spelling of the artefact
    would be a statement about bytes nobody can find.
    """
    workspace = _workspace(tmp_path)

    revision = _write(workspace, _document(as_of=frozen_now), created_at=frozen_now)

    for receipt in revision.receipts:
        written = (tmp_path / receipt.relative_path).read_bytes()
        assert receipt.content_sha256 == hashlib.sha256(written).hexdigest()
        assert receipt.size_bytes == len(written)


@pytest.mark.unit
def test_the_document_that_was_written_is_the_models_canonical_bytes(
    tmp_path: Path, frozen_now: datetime
) -> None:
    """The canonical document is the model's own bytes, not a rendering of them.

    A reader who has the model can recompute the file, and a reader who has
    the file can tell whether it is the document the manifest describes.
    """
    workspace = _workspace(tmp_path)
    document = _document(as_of=frozen_now)

    revision = _write(workspace, document, created_at=frozen_now)

    assert (tmp_path / revision.document.relative_path).read_bytes() == document.canonical_bytes()


@pytest.mark.unit
def test_the_manifest_names_the_document_that_was_written(
    tmp_path: Path, frozen_now: datetime
) -> None:
    """The manifest's document part is the file, at the path it was written to.

    Both halves are asserted, because either alone would pass by accident: a
    manifest that named the right bytes at the wrong path would send a reader
    to a file that is not there, and a manifest that named the right path with
    the wrong bytes would name something else.
    """
    workspace = _workspace(tmp_path)

    revision = _write(workspace, _document(as_of=frozen_now), created_at=frozen_now)

    manifest = ReportManifest.model_validate_json(
        (tmp_path / revision.manifest.relative_path).read_bytes()
    )
    document_part = next(part for part in manifest.parts if part.part_id == DOCUMENT_PART_ID)
    assert document_part.relative_path == revision.document.relative_path
    assert document_part.content_sha256 == revision.document.content_sha256


@pytest.mark.unit
def test_the_four_forms_are_written_and_recorded_with_their_media_types(
    tmp_path: Path, frozen_now: datetime
) -> None:
    """All four forms, each with the bytes it was given and the type it is.

    The media type is a claim about the bytes, not a guess from the file
    suffix, so it is stated rather than derived.
    """
    workspace = _workspace(tmp_path)

    revision = _write(workspace, _document(as_of=frozen_now), created_at=frozen_now)

    assert len(revision.forms) == 4
    for form, receipt in zip(ReportForm, revision.forms, strict=True):
        assert (tmp_path / receipt.relative_path).read_bytes() == FORM_BYTES[form]
        assert receipt.media_type is not None
        assert receipt.kind is ArtifactKind.REPORT
    assert {receipt.media_type for receipt in revision.forms} == {
        "text/markdown; charset=utf-8",
        "text/html; charset=utf-8",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/pdf",
    }


@pytest.mark.unit
def test_the_manifest_is_recorded_as_a_receipt_of_kind_manifest(
    tmp_path: Path, frozen_now: datetime
) -> None:
    """The kind was already reserved for this, and it is used."""
    workspace = _workspace(tmp_path)

    revision = _write(workspace, _document(as_of=frozen_now), created_at=frozen_now)

    assert revision.manifest.kind is ArtifactKind.MANIFEST
    assert revision.document.kind is ArtifactKind.REPORT


@pytest.mark.unit
def test_every_parameter_the_writer_accepts_it_keeps(tmp_path: Path, frozen_now: datetime) -> None:
    """A parameter that is accepted and then ignored is a parameter that lies.

    The caller reads the receipts back and finds something else there. So
    the revision, the producer and the task are each shown to have changed
    what happened — not merely that the function ran.
    """
    workspace = _workspace(tmp_path)

    revision = write_report_revision(
        workspace,
        document=_document(as_of=frozen_now),
        forms=FORM_BYTES,
        verify=_accepts,
        upstreams={"tab-1": (_upstream(),)},
        revision=7,
        created_at=frozen_now,
        producer_id="labcairn.reports.deliver",
        produced_by=ArtifactProducerKind.ANALYSIS_OPERATOR,
    )

    assert revision.revision == 7
    for receipt in revision.receipts:
        assert receipt.revision == 7
        assert receipt.producer_id == "labcairn.reports.deliver"
        assert receipt.produced_by is ArtifactProducerKind.ANALYSIS_OPERATOR
        assert receipt.task_id == str(workspace.task_id)


@pytest.mark.unit
def test_a_chain_that_would_name_the_manifest_twice_is_refused(
    tmp_path: Path, frozen_now: datetime
) -> None:
    """One upstream thing cited twice is one dependency, and the receipt refuses it.

    The manifest's closure already names the figure's own reproducibility
    manifest, so a caller that chose the same name for the manifest's receipt
    would put one thing in the chain under two names. The chain refuses rather
    than writing a receipt the ledger would reject.
    """
    manifest = build_report_manifest(
        document=_document(as_of=frozen_now),
        document_relative_path="output/report/v1/report.json",
        upstreams={"tab-1": (_upstream(),)},
    )

    with pytest.raises(ReportRevisionRefusedError, match="already names"):
        report_chain(manifest, manifest_receipt_id="fig-1.manifest")


# ---------------------------------------------------------------------------
# v1 survives v2
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_the_second_revision_carries_a_higher_revision_number(
    tmp_path: Path, frozen_now: datetime
) -> None:
    """The revision increments.

    A writer that always wrote 1 would make every revision the first one, and
    the two artefacts would be indistinguishable.
    """
    workspace = _workspace(tmp_path)

    first = _write(workspace, _document(as_of=frozen_now), created_at=frozen_now)
    second = _write(workspace, _document(as_of=frozen_now), created_at=frozen_now)

    assert first.revision == 1
    assert second.revision == 2
    assert {receipt.revision for receipt in second.receipts} == {2}


@pytest.mark.unit
def test_the_second_revision_does_not_alter_the_first(tmp_path: Path, frozen_now: datetime) -> None:
    """v1's bytes are still v1's bytes, and v1's receipts still describe them.

    The file bytes are read back and compared, and then v1's receipts are
    checked against the files that are there now. A test that only compared
    the receipt numbers would pass against a writer that overwrote v1's file
    and left the receipt alone — which is exactly the defect this rule exists
    to prevent.
    """
    workspace = _workspace(tmp_path)
    first = _write(workspace, _document(as_of=frozen_now), created_at=frozen_now)
    before = {
        receipt.relative_path: (tmp_path / receipt.relative_path).read_bytes()
        for receipt in first.receipts
    }

    _write(workspace, _document(as_of=frozen_now), created_at=frozen_now)

    for path, content in before.items():
        assert (tmp_path / path).read_bytes() == content, f"{path} was altered"
    for receipt in first.receipts:
        now = (tmp_path / receipt.relative_path).read_bytes()
        assert receipt.content_sha256 == hashlib.sha256(now).hexdigest()


@pytest.mark.unit
def test_a_revision_number_below_one_is_refused(tmp_path: Path, frozen_now: datetime) -> None:
    """A revision numbered zero is a revision with no first.

    The receipt's own model counts revisions from one, and the writer holds
    to it: a revision numbered zero would be a revision with nothing
    before it, and the number would then answer "which revision is this"
    two ways.

    This is the **other** half of the immutability refusal above, and it is
    a different one: that one is about a number that has been used, and
    this one is about a number that is not a number at all.
    """
    workspace = _workspace(tmp_path)

    with pytest.raises(ReportRevisionRefusedError, match="not a revision number"):
        _write(workspace, _document(as_of=frozen_now), created_at=frozen_now, revision=0)

    assert list(workspace.output_root.path.iterdir()) == []


@pytest.mark.unit
def test_the_revision_refuses_a_manifest_the_chain_does_not_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, frozen_now: datetime
) -> None:
    """The chain must name the manifest that was written.

    The chain's manifest link is built from the manifest's canonical bytes
    before anything is written, and the receipt's hash is taken over the
    bytes on disk — the same bytes, so this cannot fail. It is said out
    loud anyway, because a chain that named a manifest nobody wrote would
    leave the report's lineage pointing at bytes that are not there, and
    nothing downstream would notice.

    The writer is made to hand back a receipt for a manifest that is not
    the one it wrote, so that the belt is seen to hold rather than merely
    to be there.
    """
    from labcairn.reports.manifest import write_report_manifest as real_writer

    def a_manifest_that_is_not_the_one(*args: Any, **kwargs: Any) -> ArtifactReceipt:
        receipt = real_writer(*args, **kwargs)
        return receipt.model_copy(update={"content_sha256": _hash("not the manifest")})

    monkeypatch.setattr(
        "labcairn.reports.revisions.write_report_manifest", a_manifest_that_is_not_the_one
    )
    workspace = _workspace(tmp_path)

    with pytest.raises(ReportRevisionRefusedError, match="point at bytes that are not there"):
        _write(workspace, _document(as_of=frozen_now), created_at=frozen_now)


@pytest.mark.unit
def test_a_revision_that_has_been_written_is_refused(tmp_path: Path, frozen_now: datetime) -> None:
    """A revision is immutable once written.

    The DOCX is a ZIP whose entries carry timestamps and the PDF carries a
    creation date, so a second render of revision 1 produces different bytes
    for the same revision number. Two artefacts claiming to be revision 1 with
    different hashes is the ambiguity the revision number exists to prevent,
    so the second write is refused rather than performed.
    """
    workspace = _workspace(tmp_path)
    _write(workspace, _document(as_of=frozen_now), created_at=frozen_now)

    with pytest.raises(ReportRevisionRefusedError, match="immutable"):
        _write(workspace, _document(as_of=frozen_now), revision=1, created_at=frozen_now)


@pytest.mark.unit
def test_a_revision_number_that_is_not_beyond_the_ones_already_written_is_refused(
    tmp_path: Path, frozen_now: datetime
) -> None:
    """Revision 1 cannot be written after revision 2 exists.

    The refusal is about the *number*, not about the files: a revision whose
    directory was removed by hand is still in the ledger, and reusing its
    number would put two different artefacts under one identity.
    """
    workspace = _workspace(tmp_path)
    _write(workspace, _document(as_of=frozen_now), created_at=frozen_now)
    _write(workspace, _document(as_of=frozen_now), created_at=frozen_now)

    with pytest.raises(ReportRevisionRefusedError, match="not beyond"):
        _write(workspace, _document(as_of=frozen_now), revision=1, created_at=frozen_now)
    with pytest.raises(ReportRevisionRefusedError, match="not beyond"):
        _write(workspace, _document(as_of=frozen_now), revision=2, created_at=frozen_now)


@pytest.mark.unit
def test_the_revisions_a_task_holds_are_the_ones_on_disk(
    tmp_path: Path, frozen_now: datetime
) -> None:
    """What the output area holds is what the task has.

    This is the answer the writer's own refusal is built on, so it is worth
    its own test: a reader must be able to ask the question and get the
    truth.
    """
    workspace = _workspace(tmp_path)

    assert existing_revisions(workspace) == ()

    _write(workspace, _document(as_of=frozen_now), created_at=frozen_now)
    assert existing_revisions(workspace) == (1,)

    _write(workspace, _document(as_of=frozen_now), created_at=frozen_now)
    assert existing_revisions(workspace) == (1, 2)


# ---------------------------------------------------------------------------
# The chain
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_the_reports_chain_names_the_manifest_with_its_hash(
    tmp_path: Path, frozen_now: datetime
) -> None:
    """The report names the manifest that describes it.

    The manifest is one of the report's ancestors, so the report's chain names
    it — and names it with the hash of the bytes that were written, because a
    link with no hash is a link nothing can invalidate.
    """
    workspace = _workspace(tmp_path)

    revision = _write(workspace, _document(as_of=frozen_now), created_at=frozen_now)

    named = _named(revision.document)
    assert named[(DerivationTargetKind.ARTIFACT, revision.manifest.receipt_id)] == (
        revision.manifest.content_sha256
    )


@pytest.mark.unit
def test_the_reports_chain_is_an_ancestor_closure(tmp_path: Path, frozen_now: datetime) -> None:
    """The chain names the parts **and** the parts' upstream, in one flat list.

    The closure is what the one-hop walk needs. A chain that stopped at the
    immediate parent would never see the material underneath it move.
    """
    workspace = _workspace(tmp_path)

    revision = _write(workspace, _document(as_of=frozen_now), created_at=frozen_now)

    named = _named(revision.document)
    assert named[(DerivationTargetKind.MATERIAL_FILE, TABLE_PATH)] == TABLE_HASH
    assert named[(DerivationTargetKind.MATERIAL_FILE, FIGURE_PATH)] == FIGURE_HASH
    assert named[(DerivationTargetKind.MATERIAL_FILE, MATERIAL_PATH)] == SOURCE_HASH


@pytest.mark.unit
def test_the_materials_hash_is_in_every_receipts_own_chain(
    tmp_path: Path, frozen_now: datetime
) -> None:
    """The material's hash is directly in each receipt's chain.

    This is the load-bearing assertion of the whole subtask. The walk is one
    hop: it marks an artefact stale when *that artefact's* ``derived_from``
    names a changed hash. A report receipt naming only the manifest would
    never be marked when a **source** changed — the manifest would be marked,
    and the report would sit there saying ``CURRENT`` about bytes whose
    material had moved.

    Asserted for all six receipts, because "the report" is all six of them:
    the document, the manifest and the four forms.
    """
    workspace = _workspace(tmp_path)

    revision = _write(workspace, _document(as_of=frozen_now), created_at=frozen_now)

    for receipt in revision.receipts:
        hashes = {link.content_sha256 for link in receipt.derived_from}
        assert SOURCE_HASH in hashes, (
            f"{receipt.receipt_id} does not name the material's hash, so the "
            "staleness walk cannot reach it"
        )


@pytest.mark.unit
def test_every_link_in_the_chain_carries_a_hash(tmp_path: Path, frozen_now: datetime) -> None:
    """A link with no hash is a link nothing can invalidate.

    The receipt's own model enforces this for artefacts and material files;
    this asserts it of the chain the writer actually built.
    """
    workspace = _workspace(tmp_path)

    revision = _write(workspace, _document(as_of=frozen_now), created_at=frozen_now)

    for receipt in revision.receipts:
        for link in receipt.derived_from:
            assert link.content_sha256 is not None, link


@pytest.mark.unit
def test_the_chain_is_the_manifests_own_closure_plus_the_manifest(
    tmp_path: Path, frozen_now: datetime
) -> None:
    """The chain is built from the manifest's closure, not a second closure.

    Two builders of the ancestor closure could drift apart, and the one that
    drifts is the one the walk reads. So the report's chain is checked against
    the builder the manifest itself uses.
    """
    workspace = _workspace(tmp_path)

    revision = _write(workspace, _document(as_of=frozen_now), created_at=frozen_now)

    manifest = ReportManifest.model_validate_json(
        (tmp_path / revision.manifest.relative_path).read_bytes()
    )
    expected = report_chain(manifest, manifest_receipt_id=revision.manifest.receipt_id)

    assert revision.document.derived_from == expected
    assert revision.manifest.derived_from == expected[1:], (
        "the manifest's own chain is the closure without the manifest's link: it is the manifest"
    )


# ---------------------------------------------------------------------------
# The checks gate the write
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_a_document_the_checks_refuse_is_not_written(tmp_path: Path, frozen_now: datetime) -> None:
    """A report that says something the ledger does not support must not be written.

    The refusal comes first and the output area is left empty. Both halves
    are asserted, because either alone would pass by accident: a test that
    only checked the raising would pass even when files had been written and
    then abandoned, and a generated file that no receipt names is an artefact
    nothing can account for.
    """
    workspace = _workspace(tmp_path)

    with pytest.raises(ReportRevisionRefusedError, match="content checks refused"):
        _write(
            workspace,
            _document(as_of=frozen_now),
            created_at=frozen_now,
            verify=_refuses,
        )

    assert list(workspace.output_root.path.iterdir()) == []


@pytest.mark.unit
def test_a_missing_form_is_refused(tmp_path: Path, frozen_now: datetime) -> None:
    """A revision is the document, the manifest and the four forms.

    A revision missing a form is a revision nobody can open in that form, and
    writing the other three would leave a revision that claims to be complete
    and is not.
    """
    workspace = _workspace(tmp_path)
    forms: dict[ReportForm, bytes] = {
        form: data for form, data in FORM_BYTES.items() if form is not ReportForm.PDF
    }

    with pytest.raises(ReportRevisionRefusedError, match="missing"):
        write_report_revision(
            workspace,
            document=_document(as_of=frozen_now),
            forms=forms,
            verify=_accepts,
            upstreams={"tab-1": (_upstream(),)},
            created_at=frozen_now,
        )

    assert list(workspace.output_root.path.iterdir()) == []


@pytest.mark.unit
def test_an_unknown_form_is_refused(tmp_path: Path, frozen_now: datetime) -> None:
    """A form the repository cannot name is a form nobody can serve."""
    workspace = _workspace(tmp_path)
    forms: dict[Any, bytes] = dict(FORM_BYTES)
    forms["rtf"] = b"a form nobody knows"

    with pytest.raises(ReportRevisionRefusedError, match="not a report form"):
        write_report_revision(
            workspace,
            document=_document(as_of=frozen_now),
            forms=forms,
            verify=_accepts,
            upstreams={"tab-1": (_upstream(),)},
            created_at=frozen_now,
        )

    assert list(workspace.output_root.path.iterdir()) == []


@pytest.mark.unit
def test_a_manifest_that_cannot_be_built_writes_nothing(
    tmp_path: Path, frozen_now: datetime
) -> None:
    """The manifest is built from the document, and a table with no upstream is refused.

    A table in the report model is a fact about a file, and the file does not
    say what computed it. The manifest builder refuses rather than recording
    a blank, and the refusal lands before a byte does.
    """
    workspace = _workspace(tmp_path)

    with pytest.raises(Exception, match="name no upstream"):
        _write(
            workspace,
            _document(as_of=frozen_now),
            created_at=frozen_now,
            upstreams={},
        )

    assert list(workspace.output_root.path.iterdir()) == []


@pytest.mark.unit
def test_a_chain_that_contradicts_itself_writes_nothing(
    tmp_path: Path, frozen_now: datetime
) -> None:
    """One upstream named twice with two hashes is refused before anything lands.

    The two readings are the same material with different bytes, and a chain
    that picked one of them would mark the report stale for one hash and
    current for the other, with no way for a reader to tell which was meant.
    """
    workspace = _workspace(tmp_path)
    upstreams: dict[str, tuple[DerivationRef, ...]] = {
        "fig-1": (_upstream(content_sha256=_hash("one-reading")),),
        "tab-1": (_upstream(content_sha256=_hash("another-reading")),),
    }

    with pytest.raises(Exception, match="twice with different"):
        _write(
            workspace,
            _document(as_of=frozen_now),
            created_at=frozen_now,
            upstreams=upstreams,
        )

    assert list(workspace.output_root.path.iterdir()) == []


# ---------------------------------------------------------------------------
# Staleness: the repository's own walk
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_a_changed_material_marks_the_report_the_manifest_and_the_figure_stale(
    env: StoreEnv, tmp_path: Path, frozen_now: datetime
) -> None:
    """The ledger notices, not this module.

    The material changes; the repository's own walk is called with the hash
    that changed; and the report, the manifest, the four forms **and** the
    figure are all marked stale in one pass, each with the repository's own
    reason.

    The assertion that matters is the *figure* alongside the report: the
    figure was produced by other code and names the material directly, and
    the report names the material only because the chain is a flat ancestor
    closure. If the report's chain had stopped at the manifest, the figure
    would have gone stale and the report would not.
    """
    scenario = build_scenario(env, tmp_path)
    workspace = Workspace.bind(scenario.root, task_id=scenario.task_id)
    material = scenario.root.joinpath(*MATERIAL_PATH.split("/"))
    material.parent.mkdir(parents=True, exist_ok=True)
    body = b"yield\n4.253\n"
    material.write_bytes(body)
    source_hash = hashlib.sha256(body).hexdigest()

    document = _document(as_of=frozen_now, source_hash=source_hash)
    revision = _write(workspace, document, created_at=frozen_now, source_hash=source_hash)
    figure = ArtifactReceipt(
        receipt_id="figure-1",
        task_id=str(scenario.task_id),
        kind=ArtifactKind.FIGURE,
        relative_path=FIGURE_PATH,
        content_sha256=FIGURE_HASH,
        size_bytes=128,
        produced_by=ArtifactProducerKind.ANALYSIS_OPERATOR,
        producer_id="labcairn.analysis.mean@1.0.0",
        derived_from=(_upstream(content_sha256=source_hash),),
        created_at=frozen_now,
    )
    _record(scenario, (*revision.receipts, figure))

    before = MaterialResolver(scenario.root).snapshot([MATERIAL_PATH])
    _rewrite_preserving_mtime(material, b"yield\n4.500\n")
    after = MaterialResolver(scenario.root).snapshot([MATERIAL_PATH])
    changed = sorted(set(before.values()) - set(after.values()))

    report = scenario.resume().invalidate_on_source_change(scenario.task_id, changed)

    expected = {receipt.receipt_id for receipt in revision.receipts} | {figure.receipt_id}
    assert set(report.stale_artifact_ids) == expected, (
        "one pass must reach the report, the manifest, the four forms and the "
        "figure; the walk is one hop, so the report's chain has to carry the "
        "material's hash itself"
    )
    stale = scenario.resume().stale_artifacts(scenario.task_id)
    assert {receipt.receipt_id for receipt in stale} == expected
    assert all(receipt.staleness is ArtifactStaleness.STALE for receipt in stale)
    assert all(receipt.staleness_reason == STALE_REASON for receipt in stale), (
        "ADR-0004 I4: a stale mark nobody can act on is decoration. The reason "
        "is the repository's own, so a reader can act on it."
    )


@pytest.mark.unit
def test_a_claims_only_report_names_the_material_in_its_own_chain(
    tmp_path: Path, frozen_now: datetime
) -> None:
    """A report with claims and no parts still names the material.

    The mirror image of the test above, and the one that was missing. Every
    other staleness test in this file builds a document with a figure, and
    the figure's receipt names the material — so the material reached the
    chain through the report's **parts**. A report with claims and no
    figure and no table has no parts, and nothing else used to put the
    material in its chain.

    The consequence was not a small one: the walk is one hop, so a report
    whose chain named nothing but its own files could **never** be marked
    stale. It would sit there saying ``CURRENT`` about bytes whose material
    had moved, and nothing would notice.

    So the material's hash is in the report's own chain, for a report with
    no parts as well as one with, and it is *directly* there rather than
    one hop away — the owner's fifth decision, and the reason the chain is
    a flat ancestor closure.
    """
    workspace = _workspace(tmp_path)

    revision = _write(
        workspace,
        _claims_only_document(as_of=frozen_now),
        created_at=frozen_now,
        upstreams={},
    )

    for receipt in revision.receipts:
        hashes = {link.content_sha256 for link in receipt.derived_from}
        assert SOURCE_HASH in hashes, (
            f"{receipt.receipt_id} does not name the material's hash, so the "
            "staleness walk cannot reach it"
        )

    named = _named(revision.document)
    assert named[(DerivationTargetKind.SOURCE, "src-1")] == SOURCE_HASH, (
        "the report's chain names the source its claim was read from, and the "
        "bytes it was read from"
    )


@pytest.mark.integration
def test_a_changed_material_marks_a_claims_only_report_and_its_manifest_stale(
    env: StoreEnv, tmp_path: Path, frozen_now: datetime
) -> None:
    """The ledger notices, for a report that has no parts to notice through.

    The same walk, the same reason, and the same one pass — but the report
    here carries **claims only**: no figure, no table, and so no part
    whose receipt names the material. The source the claim was read from is
    the only thing the report rests on, and when it moves the report and
    its manifest must both go stale.

    This is the acceptance clause, *"Re-rendering after material change
    invalidates stale output"*, discharged for that shape.
    """
    scenario = build_scenario(env, tmp_path)
    workspace = Workspace.bind(scenario.root, task_id=scenario.task_id)
    source = scenario.root.joinpath(*SOURCE_PATH.split("/"))
    source.parent.mkdir(parents=True, exist_ok=True)
    body = b"%PDF-1.7\nthe source the claim was read from\n"
    source.write_bytes(body)
    source_hash = hashlib.sha256(body).hexdigest()

    document = _claims_only_document(as_of=frozen_now, source_hash=source_hash)
    revision = _write(
        workspace,
        document,
        created_at=frozen_now,
        upstreams={},
        source_hash=source_hash,
    )
    _record(scenario, revision.receipts)

    before = MaterialResolver(scenario.root).snapshot([SOURCE_PATH])
    _rewrite_preserving_mtime(source, b"%PDF-1.7\nthe source, changed\n")
    after = MaterialResolver(scenario.root).snapshot([SOURCE_PATH])
    changed = sorted(set(before.values()) - set(after.values()))

    report = scenario.resume().invalidate_on_source_change(scenario.task_id, changed)

    expected = {receipt.receipt_id for receipt in revision.receipts}
    assert set(report.stale_artifact_ids) == expected, (
        "the report and the manifest must both go stale: the walk is one hop, "
        "so the report's own chain has to carry the material's hash"
    )
    stale = scenario.resume().stale_artifacts(scenario.task_id)
    assert {receipt.receipt_id for receipt in stale} == expected
    assert all(receipt.staleness is ArtifactStaleness.STALE for receipt in stale)
    assert all(receipt.staleness_reason == STALE_REASON for receipt in stale)


@pytest.mark.integration
def test_a_stale_revision_cannot_be_written_again_as_current(
    env: StoreEnv, tmp_path: Path, frozen_now: datetime
) -> None:
    """A revision marked stale stays stale: it cannot be re-rendered into currency.

    This is the mutation that matters most. The revision's receipt ids are
    derived from the task and the revision, so a second write of revision 1
    would put **the same six receipts** back into the ledger — and the store
    upserts by receipt id. Without the immutability refusal, a stale receipt
    would be written over as a current one and the mark would be gone.

    So the second write is refused, and the ledger still holds the stale
    receipts with their reason.
    """
    scenario = build_scenario(env, tmp_path)
    workspace = Workspace.bind(scenario.root, task_id=scenario.task_id)
    material = scenario.root.joinpath(*MATERIAL_PATH.split("/"))
    material.parent.mkdir(parents=True, exist_ok=True)
    body = b"yield\n4.253\n"
    material.write_bytes(body)
    source_hash = hashlib.sha256(body).hexdigest()

    document = _document(as_of=frozen_now, source_hash=source_hash)
    revision = _write(workspace, document, created_at=frozen_now, source_hash=source_hash)
    _record(scenario, revision.receipts)

    before = MaterialResolver(scenario.root).snapshot([MATERIAL_PATH])
    _rewrite_preserving_mtime(material, b"yield\n4.500\n")
    after = MaterialResolver(scenario.root).snapshot([MATERIAL_PATH])
    changed = sorted(set(before.values()) - set(after.values()))
    scenario.resume().invalidate_on_source_change(scenario.task_id, changed)

    stale_ids = {
        receipt.receipt_id for receipt in scenario.resume().stale_artifacts(scenario.task_id)
    }
    assert stale_ids == {receipt.receipt_id for receipt in revision.receipts}

    with pytest.raises(ReportRevisionRefusedError, match="immutable"):
        again = _write(
            workspace, document, created_at=frozen_now, revision=1, source_hash=source_hash
        )
        _record(scenario, again.receipts)

    assert {
        receipt.receipt_id for receipt in scenario.resume().stale_artifacts(scenario.task_id)
    } == stale_ids, (
        "a stale receipt must not be written over as a current one; the mark is "
        "the only record that the report's material moved"
    )


@pytest.mark.integration
def test_a_revision_written_after_a_change_coexists_with_the_stale_one(
    env: StoreEnv, tmp_path: Path, frozen_now: datetime
) -> None:
    """Re-rendering after a material change produces a **new** revision.

    The old one stays stale and says so; the new one is current and sits
    beside it. And the new revision is a **different document**, because the
    report's content is a function of the ledger at a moment — calling it a
    revision of the same one would be a lie about what the first one says.
    """
    scenario = build_scenario(env, tmp_path)
    workspace = Workspace.bind(scenario.root, task_id=scenario.task_id)
    material = scenario.root.joinpath(*MATERIAL_PATH.split("/"))
    material.parent.mkdir(parents=True, exist_ok=True)
    body = b"yield\n4.253\n"
    material.write_bytes(body)
    source_hash = hashlib.sha256(body).hexdigest()

    first = _write(
        workspace,
        _document(as_of=frozen_now, source_hash=source_hash),
        created_at=frozen_now,
        source_hash=source_hash,
    )
    _record(scenario, first.receipts)
    first_bytes = {
        receipt.relative_path: (scenario.root / receipt.relative_path).read_bytes()
        for receipt in first.receipts
    }

    before = MaterialResolver(scenario.root).snapshot([MATERIAL_PATH])
    _rewrite_preserving_mtime(material, b"yield\n4.500\n")
    new_hash = hashlib.sha256(b"yield\n4.500\n").hexdigest()
    after = MaterialResolver(scenario.root).snapshot([MATERIAL_PATH])
    changed = sorted(set(before.values()) - set(after.values()))
    scenario.resume().invalidate_on_source_change(scenario.task_id, changed)

    second = _write(
        workspace,
        _document(as_of=frozen_now, source_hash=new_hash),
        created_at=frozen_now,
        source_hash=new_hash,
    )
    _record(scenario, second.receipts)

    assert second.revision == 2
    assert second.document.content_sha256 != first.document.content_sha256, (
        "a second run over a changed ledger is a different document; calling it "
        "the same report with a new number would be a lie about what the first "
        "one says"
    )
    for path, content in first_bytes.items():
        assert (scenario.root / path).read_bytes() == content, f"{path} was altered"

    stale = scenario.resume().stale_artifacts(scenario.task_id)
    assert {receipt.receipt_id for receipt in stale} == {
        receipt.receipt_id for receipt in first.receipts
    }
    assert not (
        {receipt.receipt_id for receipt in second.receipts}
        & {receipt.receipt_id for receipt in stale}
    ), "the new revision is current: it was rendered from the material as it is now"
