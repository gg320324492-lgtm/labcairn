"""The report artefact manifest — the five rules, and what each of them refuses.

LC-P1-11's manifest is the document that says what a report is made of: every
figure, every table and the report document itself, each with where it is,
what it hashes to, and what it was made from. It is what makes a report
**checkable**, and the property that matters is that it **cannot disagree
with the report it describes**.

This file tests it the way it is judged: **every rule needs a test that fails
when the rule is broken.** A rule that is broken is not a manifest that is
slightly wrong — it is a manifest that would be read as a statement about
bytes that are not there. So the tests below break one thing at a time and
watch it be refused: a part whose hash is not the report's, a report whose
digest is not the digest of its canonical bytes, a part that names no
upstream, a manifest with two document parts, a manifest that carries the
report's prose.

The helpers build a valid document and a valid manifest and then change
exactly one thing, so that a failure points at a rule rather than at a
fixture. The frozen clock comes from the repository's own ``frozen_now``
fixture, so no test here reads a wall clock.

Nothing in this file is a placeholder for a later task's test: the renderers
(T01), the revisions (T03) and the content checks (T04) have their own.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from labcairn.analysis.manifest import (
    FileRef,
    RenderEnvironment,
    ReproducibilityManifest,
    canonical_digest,
    manifest_bytes,
)
from labcairn.core.ids import TaskId, new_id
from labcairn.core.schema import LabCairnModel
from labcairn.evidence.states import EvidenceKind, VerificationStatus
from labcairn.reports.manifest import (
    DOCUMENT_PART_ID,
    ManifestPart,
    ManifestPartKind,
    ReportManifest,
    ReportManifestRefusedError,
    build_report_manifest,
    manifest_chain,
    write_report_manifest,
)
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
    DerivationRef,
    DerivationTargetKind,
)
from labcairn.sources.locators import ComputationLocator, PdfLocator
from labcairn.workspace.roots import Workspace

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

#: Where the report's canonical document bytes are written.
DOCUMENT_PATH: str = "outputs/report/report.json"
#: Where the figure artefact is.
FIGURE_PATH: str = "outputs/figures/fig-1.svg"
#: Where the table artefact is.
TABLE_PATH: str = "outputs/tables/tab-1.csv"

#: The caption of the figure. It must not turn up in the manifest.
CAPTION: str = "Mean yield across the five measured runs."
#: The text of the claim the report rests on. It must not turn up either.
CLAIM_TEXT: str = "The material reports a yield of 4.253%."


def _figure_manifest(*, mean: float = 4.253) -> ReproducibilityManifest:
    """A valid reproducibility manifest for one figure.

    Built through the manifest's own fields rather than through
    :func:`labcairn.analysis.manifest.build_manifest`, because the builder
    wants a source on disk and a workspace, and neither is what this file is
    about. The *mean* varies so that two figures can hold two different
    manifests, which is what a constant manifest id would collide.
    """
    output: dict[str, Any] = {"mean": mean, "n_used": 5}
    selection: dict[str, Any] = {
        "source_id": "src-1",
        "content_sha256": SOURCE_HASH,
        "columns": ["yield"],
        "rows": {"kind": "range", "start": 1, "end": 5},
        "missing": "exclude",
    }
    return ReproducibilityManifest(
        input_file=FileRef(relative_path="material/exp1.csv", content_sha256=SOURCE_HASH),
        operator="labcairn.analysis.mean@1.0.0",
        locator=ComputationLocator(
            operator_id="labcairn.analysis.mean",
            operator_version="1.0.0",
            parameters={"selection": selection, "column": "yield"},
            input_hashes=(SOURCE_HASH,),
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
    figure_hash: str = FIGURE_HASH,
    table_hash: str = TABLE_HASH,
    with_table: bool = True,
    second_figure: bool = False,
) -> ReportDocument:
    """A valid document with a figure and, unless told otherwise, a table."""
    record = LedgerRecordView(
        record_id="rec-1",
        record_kind=EvidenceKind.NUMERIC,
        value=4.253,
        unit="%",
        status=VerificationStatus.VERIFIED_BY_RULE,
        anchor_ids=("anc-1",),
        source_content_hash=SOURCE_HASH,
    )
    footnote = ProvenanceFootnote(
        footnote_id="fn-1",
        source_id="src-1",
        locator=PdfLocator(page=3),
        content_sha256=SOURCE_HASH,
    )
    figure = ReportFigure(
        figure_id="fig-1",
        relative_path=FIGURE_PATH,
        content_sha256=figure_hash,
        caption=CAPTION,
        manifest=_figure_manifest(),
    )
    table = ReportTable(
        table_id="tab-1",
        relative_path=TABLE_PATH,
        content_sha256=table_hash,
    )
    blocks: tuple[Any, ...] = (ClaimBlock(claim_id="clm-1"), FigureBlock(figure_id="fig-1"))
    figures: tuple[ReportFigure, ...] = (figure,)
    tables: tuple[ReportTable, ...] = ()
    if with_table:
        blocks = (*blocks, TableBlock(table_id="tab-1"))
        tables = (table,)
    if second_figure:
        figures = (
            figure,
            ReportFigure(
                figure_id="fig-2",
                relative_path="outputs/figures/fig-2.svg",
                content_sha256=_hash("figure-2"),
                caption="Median yield across the same five runs.",
                manifest=_figure_manifest(mean=4.501),
            ),
        )
        blocks = (*blocks, FigureBlock(figure_id="fig-2"))
    return ReportDocument(
        title="A first-pass report",
        snapshot=LedgerSnapshot(as_of=as_of, record_ids=("rec-1",)),
        sections=(ReportSection(section_id="sec-1", heading="Findings", blocks=blocks),),
        claims=(ReportClaim(claim_id="clm-1", record=record, footnote_ids=("fn-1",)),),
        figures=figures,
        tables=tables,
        footnotes=(footnote,),
    )


def _upstream(
    *,
    target_id: str = "material/exp1.csv",
    content_sha256: str = SOURCE_HASH,
) -> DerivationRef:
    """What produced the table: the material it was computed from."""
    return DerivationRef(
        target_kind=DerivationTargetKind.MATERIAL_FILE,
        target_id=target_id,
        content_sha256=content_sha256,
    )


def _manifest(
    document: ReportDocument,
    *,
    upstreams: dict[str, tuple[DerivationRef, ...]] | None = None,
    document_relative_path: str = DOCUMENT_PATH,
) -> ReportManifest:
    """The manifest for *document*, with the table's upstream supplied."""
    if upstreams is None:
        upstreams = {"tab-1": (_upstream(),)}
    return build_report_manifest(
        document=document,
        document_relative_path=document_relative_path,
        upstreams=upstreams,
    )


def _part(manifest: ReportManifest, part_id: str) -> ManifestPart:
    """The part with this id, or a failure that says which id is missing."""
    for part in manifest.parts:
        if part.part_id == part_id:
            return part
    raise AssertionError(f"the manifest has no part {part_id!r}")


def _workspace(tmp_path: Path) -> Workspace:
    """A workspace with one task, for the writer."""
    return Workspace.bind(tmp_path, task_id=TaskId(new_id()))


def _named(receipt: ArtifactReceipt) -> dict[tuple[DerivationTargetKind, str], str | None]:
    """The receipt's chain, by what each link names."""
    return {
        (link.target_kind, link.target_id): link.content_sha256 for link in receipt.derived_from
    }


# ---------------------------------------------------------------------------
# Rule 1 — the manifest is built from the document, and cannot disagree with it
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_every_part_is_read_out_of_the_report(frozen_now: datetime) -> None:
    """The manifest's parts are the report's parts, not a parallel account.

    A manifest assembled beside the report is a second spelling of it, and
    the second spelling is the one that goes stale. So each part's path and
    hash are the document's own.
    """
    document = _document(as_of=frozen_now)
    manifest = _manifest(document)

    figure = _part(manifest, "fig-1")
    assert figure.relative_path == document.figures[0].relative_path
    assert figure.content_sha256 == document.figures[0].content_sha256

    table = _part(manifest, "tab-1")
    assert table.relative_path == document.tables[0].relative_path
    assert table.content_sha256 == document.tables[0].content_sha256


@pytest.mark.unit
def test_the_manifest_lists_every_figure_and_table_of_the_report(
    frozen_now: datetime,
) -> None:
    """A part the manifest does not list is a part nobody can check.

    The manifest is the report's statement of what it is made of, and a
    figure or a table missing from that list is a part the reader cannot
    name when it changes.
    """
    document = _document(as_of=frozen_now)
    manifest = _manifest(document)

    listed = {part.part_id for part in manifest.parts}
    assert {figure.figure_id for figure in document.figures} <= listed
    assert {table.table_id for table in document.tables} <= listed
    assert len(manifest.parts) == len(document.figures) + len(document.tables) + 1


@pytest.mark.unit
def test_a_changed_part_changes_the_manifest(frozen_now: datetime) -> None:
    """The manifest is a function of the report, not of a parallel account.

    A builder that read the parts from somewhere else would produce the same
    manifest for two different reports, and the manifest would then be a
    statement about a report nobody wrote.
    """
    before = _manifest(_document(as_of=frozen_now))
    after = _manifest(_document(as_of=frozen_now, figure_hash=_hash("figure-v2")))

    assert _part(before, "fig-1").content_sha256 != _part(after, "fig-1").content_sha256
    assert before.report_sha256 != after.report_sha256


@pytest.mark.unit
def test_the_manifest_cannot_name_a_part_with_other_bytes_than_the_parts(
    frozen_now: datetime,
) -> None:
    """A manifest that disagrees with itself is refused.

    The document's lineage is the list of the parts, and each link names the
    bytes of the part it names. A hand-built manifest whose document part
    names one hash and whose figure part carries another is a document whose
    two halves disagree, and a reader would have no way to tell which half
    to believe.
    """
    document = _document(as_of=frozen_now)
    manifest = _manifest(document)
    payload = json.loads(manifest.canonical_bytes().decode("utf-8"))

    for part in payload["parts"]:
        if part["part_id"] == "fig-1":
            part["content_sha256"] = _hash("some-other-bytes")

    with pytest.raises(ValidationError, match="other bytes"):
        ReportManifest.model_validate(payload)


@pytest.mark.unit
def test_a_manifest_may_not_name_a_part_it_does_not_list(frozen_now: datetime) -> None:
    """And it may not name a part that is not there.

    The document's lineage is the list of the parts. A link to a part the
    manifest does not hold makes the list unanswerable: "what is this report
    made of" would have two answers.
    """
    manifest = _manifest(_document(as_of=frozen_now))
    payload = json.loads(manifest.canonical_bytes().decode("utf-8"))

    for part in payload["parts"]:
        if part["part_id"] == DOCUMENT_PART_ID:
            part["lineage"].append(
                {
                    "target_kind": "material_file",
                    "target_id": "outputs/tables/tab-9.csv",
                    "content_sha256": _hash("ghost"),
                }
            )

    with pytest.raises(ValidationError, match="which the manifest does not list"):
        ReportManifest.model_validate(payload)


@pytest.mark.unit
def test_a_manifest_may_not_omit_a_part_it_lists(frozen_now: datetime) -> None:
    """Nor may it leave one out.

    A part the document does not name is a part a reader cannot check, and
    the document's lineage is what says which parts there are.
    """
    manifest = _manifest(_document(as_of=frozen_now))
    payload = json.loads(manifest.canonical_bytes().decode("utf-8"))

    for part in payload["parts"]:
        if part["part_id"] == DOCUMENT_PART_ID:
            part["lineage"] = [link for link in part["lineage"] if link["target_id"] != TABLE_PATH]

    with pytest.raises(ValidationError, match="does not name the part"):
        ReportManifest.model_validate(payload)


# ---------------------------------------------------------------------------
# Rule 2 — the report's own digest is over its canonical bytes
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_the_report_digest_is_the_digest_of_the_documents_canonical_bytes(
    frozen_now: datetime,
) -> None:
    """The digest is one a reader can recompute.

    The model's own ``canonical_bytes`` are what the digest is taken over, so
    a reader who has the report can compute the manifest's digest for
    themselves rather than taking it on trust.
    """
    document = _document(as_of=frozen_now)
    manifest = _manifest(document)

    assert manifest.report_sha256 == hashlib.sha256(document.canonical_bytes()).hexdigest()


@pytest.mark.unit
def test_the_documents_own_line_holds_that_same_digest(frozen_now: datetime) -> None:
    """The document is one of the parts, and its line is that digest.

    The manifest lists the document among the parts, so the digest appears
    twice — once as the manifest's subject and once as a part's hash. The
    two are one value, and the manifest refuses to hold them apart.
    """
    manifest = _manifest(_document(as_of=frozen_now))
    document_part = _part(manifest, DOCUMENT_PART_ID)

    assert document_part.content_sha256 == manifest.report_sha256


@pytest.mark.unit
def test_a_manifest_may_not_report_a_digest_that_is_not_the_document_parts(
    frozen_now: datetime,
) -> None:
    """The two answers may not differ.

    A manifest whose digest and whose document part disagree would send a
    reader to look for bytes that are not there.
    """
    manifest = _manifest(_document(as_of=frozen_now))
    payload = json.loads(manifest.canonical_bytes().decode("utf-8"))

    payload["report_sha256"] = _hash("another-report")

    with pytest.raises(ValidationError, match="document part hashes to"):
        ReportManifest.model_validate(payload)


@pytest.mark.unit
def test_the_digest_changes_when_the_reports_content_changes(frozen_now: datetime) -> None:
    """The digest is of the content, so a changed report has a changed digest.

    A digest that did not move would make "the report changed" unanswerable
    from the manifest, and the manifest's whole job is to answer it.
    """
    before = _manifest(_document(as_of=frozen_now))
    later = _manifest(_document(as_of=datetime(2026, 6, 1, tzinfo=UTC)))

    assert before.report_sha256 != later.report_sha256


@pytest.mark.unit
def test_the_documents_path_is_the_one_the_caller_named(frozen_now: datetime) -> None:
    """The path the builder cannot derive, it keeps.

    The report model carries no path, so the caller names where the report's
    canonical bytes are written, and the manifest must carry **that** path.
    The path used here is deliberately not the one the other tests use, so
    that a builder with the path hard-coded cannot pass by accident.
    """
    elsewhere = "outputs/reports/second-attempt/report.json"
    manifest = _manifest(_document(as_of=frozen_now), document_relative_path=elsewhere)

    assert _part(manifest, DOCUMENT_PART_ID).relative_path == elsewhere


# ---------------------------------------------------------------------------
# Rule 3 — each part's lineage names its upstream
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_a_figure_names_the_manifest_that_describes_it(frozen_now: datetime) -> None:
    """The figure's upstream is the manifest that says how it was made.

    The report model holds that manifest by value, so the link can be built
    from the document and can be checked by hashing the manifest's canonical
    bytes again.
    """
    document = _document(as_of=frozen_now)
    manifest = _manifest(document)
    figure = _part(manifest, "fig-1")

    assert len(figure.lineage) == 1
    link = figure.lineage[0]
    assert link.target_kind is DerivationTargetKind.ARTIFACT
    assert (
        link.content_sha256
        == hashlib.sha256(manifest_bytes(document.figures[0].manifest)).hexdigest()
    )


@pytest.mark.unit
def test_a_table_names_what_produced_it(frozen_now: datetime) -> None:
    """A table's upstream is what computed it.

    The report model carries a table as a fact about a file, and a path and
    a hash do not say what made them. The builder is therefore given the
    table's upstream, and the manifest records it.
    """
    manifest = _manifest(_document(as_of=frozen_now))
    table = _part(manifest, "tab-1")

    assert len(table.lineage) == 1
    link = table.lineage[0]
    assert link.target_kind is DerivationTargetKind.MATERIAL_FILE
    assert link.target_id == "material/exp1.csv"
    assert link.content_sha256 == SOURCE_HASH


@pytest.mark.unit
def test_a_table_may_not_name_no_upstream(frozen_now: datetime) -> None:
    """A table nobody can trace is a table nobody can say is current.

    The refusal is the whole answer: a manifest with a table that names no
    upstream would be a blank where a fact should be, and a blank is the
    thing this repository refuses to write.
    """
    document = _document(as_of=frozen_now)

    with pytest.raises(ReportManifestRefusedError, match="name no upstream"):
        build_report_manifest(
            document=document,
            document_relative_path=DOCUMENT_PATH,
            upstreams={},
        )


@pytest.mark.unit
def test_a_part_may_not_be_declared_without_an_upstream() -> None:
    """The model refuses it too, not only the builder.

    A manifest built by hand — read back from a file, say — must not be
    able to hold a part with no lineage either, or the rule would hold only
    for manifests nobody assembles by hand.
    """
    with pytest.raises(ValidationError, match="names no upstream"):
        ReportManifest.model_validate(
            {
                "report_sha256": _hash("report"),
                "parts": [
                    {
                        "part_id": "tab-1",
                        "part_kind": "table",
                        "relative_path": TABLE_PATH,
                        "content_sha256": TABLE_HASH,
                        "lineage": [],
                    },
                    {
                        "part_id": DOCUMENT_PART_ID,
                        "part_kind": "document",
                        "relative_path": DOCUMENT_PATH,
                        "content_sha256": _hash("report"),
                        "lineage": [
                            {
                                "target_kind": "material_file",
                                "target_id": TABLE_PATH,
                                "content_sha256": TABLE_HASH,
                            }
                        ],
                    },
                ],
            }
        )


@pytest.mark.unit
def test_a_chain_link_with_no_hash_is_refused(frozen_now: datetime) -> None:
    """A link with no hash is a link nothing can invalidate.

    The manifest's lineage is a tuple of the receipt's own
    :class:`~labcairn.reports.receipt.DerivationRef` rather than a type of
    this module's making, and that model already requires a hash for the two
    kinds the staleness walk compares. The rule therefore holds for the
    manifest's lineage, and the test holds the manifest to it rather than
    holding the receipt to its own rule.
    """
    manifest = _manifest(_document(as_of=frozen_now))
    payload = json.loads(manifest.canonical_bytes().decode("utf-8"))

    for part in payload["parts"]:
        if part["part_id"] == "tab-1":
            del part["lineage"][0]["content_sha256"]

    with pytest.raises(ValidationError, match="content_sha256"):
        ReportManifest.model_validate(payload)


@pytest.mark.unit
def test_an_upstream_for_a_part_the_report_does_not_carry_is_refused(
    frozen_now: datetime,
) -> None:
    """An upstream for a part that is not in the report describes nothing.

    It would be a statement about a report nobody wrote, and a manifest
    carrying one would be a manifest that cannot be checked against the
    report it claims to describe.
    """
    document = _document(as_of=frozen_now)

    with pytest.raises(ReportManifestRefusedError, match="does not carry"):
        build_report_manifest(
            document=document,
            document_relative_path=DOCUMENT_PATH,
            upstreams={"tab-1": (_upstream(),), "tab-9": (_upstream(),)},
        )


@pytest.mark.unit
def test_a_figure_and_a_table_may_not_share_an_id(frozen_now: datetime) -> None:
    """One id may not mean two parts.

    The manifest names its parts by id, and the report model gives figures
    and tables separate id spaces of their own. Two parts with one id would
    make "which part is this" answerable two ways.
    """
    document = _document(as_of=frozen_now)
    payload = document.model_dump(mode="json")
    for table in payload["tables"]:
        table["table_id"] = "fig-1"
    for section in payload["sections"]:
        for block in section["blocks"]:
            if "table_id" in block:
                block["table_id"] = "fig-1"

    with pytest.raises(ReportManifestRefusedError, match="both as a figure and as a table"):
        build_report_manifest(
            document=ReportDocument.model_validate(payload),
            document_relative_path=DOCUMENT_PATH,
            upstreams={"fig-1": (_upstream(),)},
        )


@pytest.mark.unit
def test_a_lineage_may_not_name_a_thing_twice(frozen_now: datetime) -> None:
    """One upstream thing cited twice is one dependency.

    Listing it twice makes "how many inputs" answerable two ways, and the
    input count is exactly what a reader checks the manifest for.
    """
    manifest = _manifest(_document(as_of=frozen_now))
    payload = json.loads(manifest.canonical_bytes().decode("utf-8"))

    for part in payload["parts"]:
        if part["part_id"] == "tab-1":
            part["lineage"].append(
                {
                    "target_kind": "material_file",
                    "target_id": "material/exp1.csv",
                    "content_sha256": SOURCE_HASH,
                }
            )

    with pytest.raises(ValidationError, match="twice"):
        ReportManifest.model_validate(payload)


@pytest.mark.unit
def test_each_figure_names_its_own_manifest(frozen_now: datetime) -> None:
    """Two figures, two manifests, two names.

    The name a figure's manifest is given is derived from the figure's id,
    so two figures cannot land on one name. A constant name would make the
    chain refuse — the same upstream named twice with different hashes — and
    a reader would be shown a report whose two figures claim the same
    manifest.
    """
    document = _document(as_of=frozen_now, second_figure=True)
    manifest = _manifest(document)

    first = _part(manifest, "fig-1").lineage
    second = _part(manifest, "fig-2").lineage

    assert first[0].target_id == "fig-1.manifest"
    assert second[0].target_id == "fig-2.manifest"
    assert first[0].content_sha256 != second[0].content_sha256


@pytest.mark.unit
def test_a_supplied_upstream_for_a_figure_is_kept_after_its_own_manifest_link(
    frozen_now: datetime,
) -> None:
    """A caller who hands the builder an upstream is not ignored.

    The builder accepts extra links for a figure — the manifest receipt's id,
    say — and records them **after** the figure's own manifest link, so the
    figure's lineage still reads from the manifest outwards. A builder that
    accepted them and dropped them would be telling the caller it had
    recorded something it had not.
    """
    extra = DerivationRef(
        target_kind=DerivationTargetKind.ARTIFACT,
        target_id="receipt-figure-1",
        content_sha256=_hash("figure-manifest-artefact"),
    )
    document = _document(as_of=frozen_now)

    manifest = build_report_manifest(
        document=document,
        document_relative_path=DOCUMENT_PATH,
        upstreams={"fig-1": (extra,), "tab-1": (_upstream(),)},
    )
    lineage = _part(manifest, "fig-1").lineage

    assert len(lineage) == 2
    assert lineage[0].target_id == "fig-1.manifest"
    assert lineage[1] == extra


# ---------------------------------------------------------------------------
# Rule 4 — the manifest is a document with canonical bytes of its own
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_the_manifest_has_canonical_bytes(frozen_now: datetime) -> None:
    """The bytes are JSON, and they are the *canonical* JSON.

    Sorted keys, no incidental whitespace, and a round trip back to the same
    document: a manifest whose bytes could be written two ways could not be
    compared with another manifest, and a manifest that cannot be compared
    cannot be checked.
    """
    manifest = _manifest(_document(as_of=frozen_now))
    raw = manifest.canonical_bytes()

    parsed = json.loads(raw)
    assert list(parsed) == sorted(parsed)
    assert b", " not in raw
    assert b": " not in raw
    assert ReportManifest.model_validate_json(raw) == manifest


@pytest.mark.unit
def test_two_manifests_of_the_same_report_have_the_same_bytes(
    frozen_now: datetime,
) -> None:
    """The bytes are a function of the report, and of nothing else.

    The parts are sorted by id, so a manifest built from the same report in
    a different order is the same manifest.
    """
    document = _document(as_of=frozen_now)

    assert _manifest(document).canonical_bytes() == _manifest(document).canonical_bytes()


@pytest.mark.unit
def test_the_receipt_hashes_exactly_the_bytes_that_were_written(
    tmp_path: Path, frozen_now: datetime
) -> None:
    """The receipt's hash is the hash of the manifest file, not of a likeness.

    The receipt and the file cannot disagree, because the writer hashes what
    it wrote. A receipt whose hash was taken over some other spelling of the
    manifest would be a statement about bytes nobody can find.
    """
    workspace = _workspace(tmp_path)
    manifest = _manifest(_document(as_of=frozen_now))

    receipt = write_report_manifest(
        workspace,
        key="report-manifest.json",
        manifest=manifest,
        receipt_id="receipt-1",
        created_at=frozen_now,
    )

    written = (tmp_path / receipt.relative_path).read_bytes()
    assert written == manifest.canonical_bytes()
    assert receipt.content_sha256 == hashlib.sha256(written).hexdigest()
    assert receipt.size_bytes == len(written)


@pytest.mark.unit
def test_the_manifest_is_a_frozen_versioned_labcairn_model(frozen_now: datetime) -> None:
    """It is a persisted contract, and a persisted contract cannot drift.

    ``extra="forbid"`` is the setting that matters: a payload carrying a
    field this build does not know is rejected rather than ignored.
    """
    manifest = _manifest(_document(as_of=frozen_now))

    assert issubclass(ReportManifest, LabCairnModel)
    assert ReportManifest.model_config["frozen"] is True
    assert ReportManifest.model_config["extra"] == "forbid"
    with pytest.raises(ValidationError):
        manifest.report_sha256 = _hash("edited")


# ---------------------------------------------------------------------------
# Rule 5 — the manifest records what the report is made of, and nothing else
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_the_manifest_carries_no_content(frozen_now: datetime) -> None:
    """It holds a list of parts and one digest, and no more.

    A manifest that carries content is a second copy of the content, and
    the copy is the one that goes stale. So the fields are exactly these,
    and the model's own schema is walked rather than listed.
    """
    assert set(ReportManifest.model_fields) == {"schema_version", "report_sha256", "parts"}
    assert set(ManifestPart.model_fields) == {
        "schema_version",
        "part_id",
        "part_kind",
        "relative_path",
        "content_sha256",
        "lineage",
    }


@pytest.mark.unit
def test_the_manifests_bytes_carry_neither_the_prose_nor_the_caption(
    frozen_now: datetime,
) -> None:
    """Nothing of the report's own text is in the manifest.

    The claim's text and the figure's caption are the report's content, and
    the manifest is not a place for content: a copy of the caption would be
    a copy that goes stale while the report's caption did not.
    """
    manifest = _manifest(_document(as_of=frozen_now))
    raw = manifest.canonical_bytes().decode("utf-8")

    assert CAPTION not in raw
    assert CLAIM_TEXT not in raw
    assert "Findings" not in raw


@pytest.mark.unit
def test_the_manifest_may_not_be_given_a_field_it_does_not_know(frozen_now: datetime) -> None:
    """A field nobody wrote is refused rather than ignored.

    An unrecognised key is either a newer writer or a typo, and both
    deserve to be loud.
    """
    manifest = _manifest(_document(as_of=frozen_now))
    payload = json.loads(manifest.canonical_bytes().decode("utf-8"))
    payload["narrative"] = "The catalyst therefore improves yield."

    with pytest.raises(ValidationError):
        ReportManifest.model_validate(payload)


# ---------------------------------------------------------------------------
# The receipt: the record that points at the manifest
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_the_manifest_is_recorded_as_a_receipt_of_kind_manifest(
    tmp_path: Path, frozen_now: datetime
) -> None:
    """The kind was already reserved for this, and it is used.

    There is no new table and no migration: the manifest is a file, and the
    receipt is the ledger's row about it.
    """
    workspace = _workspace(tmp_path)

    receipt = write_report_manifest(
        workspace,
        key="report-manifest.json",
        manifest=_manifest(_document(as_of=frozen_now)),
        receipt_id="receipt-1",
        created_at=frozen_now,
    )

    assert receipt.kind is ArtifactKind.MANIFEST
    assert receipt.produced_by is ArtifactProducerKind.STAGE
    assert receipt.producer_id == "labcairn.reports.manifest"
    assert receipt.task_id == str(workspace.task_id)


@pytest.mark.unit
def test_the_receipts_chain_names_the_parts(tmp_path: Path, frozen_now: datetime) -> None:
    """The receipt names each part, with the part's bytes.

    The chain is what the staleness walk reads, and it is what makes a
    changed part nameable: the walk compares the hashes in ``derived_from``
    with the hashes that changed.
    """
    workspace = _workspace(tmp_path)
    document = _document(as_of=frozen_now)

    receipt = write_report_manifest(
        workspace,
        key="report-manifest.json",
        manifest=_manifest(document),
        receipt_id="receipt-1",
        created_at=frozen_now,
    )

    named = _named(receipt)
    assert (
        named[(DerivationTargetKind.MATERIAL_FILE, document.figures[0].relative_path)]
        == document.figures[0].content_sha256
    )
    assert (
        named[(DerivationTargetKind.MATERIAL_FILE, document.tables[0].relative_path)]
        == document.tables[0].content_sha256
    )
    assert (
        named[(DerivationTargetKind.MATERIAL_FILE, DOCUMENT_PATH)]
        == hashlib.sha256(document.canonical_bytes()).hexdigest()
    )


@pytest.mark.unit
def test_the_receipts_chain_names_the_parts_upstream(tmp_path: Path, frozen_now: datetime) -> None:
    """The material the table came from is in the chain too.

    A report whose material changed has to be markable stale, and the walk
    that marks it compares hashes in ``derived_from``. A chain that named
    only the report's own files would not notice that the material under
    them had moved.
    """
    workspace = _workspace(tmp_path)

    receipt = write_report_manifest(
        workspace,
        key="report-manifest.json",
        manifest=_manifest(_document(as_of=frozen_now)),
        receipt_id="receipt-1",
        created_at=frozen_now,
    )

    named = _named(receipt)
    assert named[(DerivationTargetKind.MATERIAL_FILE, "material/exp1.csv")] == SOURCE_HASH


@pytest.mark.unit
def test_the_chain_names_a_thing_once(tmp_path: Path, frozen_now: datetime) -> None:
    """One upstream thing cited twice is one dependency.

    The receipt's own model refuses a repeated derivation, so the chain
    keeps one link per upstream — the document's own lineage already names
    the parts, and the chain would otherwise name each of them twice.
    """
    workspace = _workspace(tmp_path)

    receipt = write_report_manifest(
        workspace,
        key="report-manifest.json",
        manifest=_manifest(_document(as_of=frozen_now)),
        receipt_id="receipt-1",
        created_at=frozen_now,
    )

    keys = [(link.target_kind, link.target_id) for link in receipt.derived_from]
    assert len(keys) == len(set(keys))


@pytest.mark.unit
def test_the_chain_refuses_one_upstream_named_twice_with_different_hashes(
    frozen_now: datetime,
) -> None:
    """The same file under two hashes is a contradiction, not a dependency.

    A figure and a table that both read the same material file, and disagree
    about what it holds, would leave the chain naming one thing twice under
    two hashes. The walk that marks things stale would then mark the report
    for one of them and leave it current for the other, and a reader would
    have no way to tell which was meant.
    """
    document = _document(as_of=frozen_now)
    manifest = _manifest(
        document,
        upstreams={
            "fig-1": (_upstream(content_sha256=_hash("one-reading")),),
            "tab-1": (_upstream(content_sha256=_hash("another-reading")),),
        },
    )

    with pytest.raises(ReportManifestRefusedError, match="twice with different"):
        manifest_chain(manifest)


@pytest.mark.unit
def test_the_writer_honours_the_receipt_id_the_producer_and_the_revision(
    tmp_path: Path, frozen_now: datetime
) -> None:
    """Every parameter the writer accepts, it keeps.

    A parameter that is accepted and then ignored is a parameter that lies:
    the caller reads the receipt back and finds something else there. The
    revision is the one T03 builds on — a report's second version is a
    second receipt with a higher number, and a writer that quietly wrote 1
    would make every revision the first one.
    """
    workspace = _workspace(tmp_path)

    receipt = write_report_manifest(
        workspace,
        key="report-manifest.json",
        manifest=_manifest(_document(as_of=frozen_now)),
        receipt_id="receipt-42",
        created_at=frozen_now,
        producer_id="labcairn.reports.deliver",
        produced_by=ArtifactProducerKind.ANALYSIS_OPERATOR,
        revision=7,
    )

    assert receipt.receipt_id == "receipt-42"
    assert receipt.producer_id == "labcairn.reports.deliver"
    assert receipt.produced_by is ArtifactProducerKind.ANALYSIS_OPERATOR
    assert receipt.revision == 7


@pytest.mark.unit
def test_the_manifest_is_written_inside_the_tasks_output_area(
    tmp_path: Path, frozen_now: datetime
) -> None:
    """A generated file lives in the task's output area, and nowhere else.

    The output area is the only place in this codebase a generated file may
    be written: it is what keeps a report out of the supplied material, and
    a manifest written beside the material would be a generated artefact
    living where only source is allowed to live.
    """
    workspace = _workspace(tmp_path)

    receipt = write_report_manifest(
        workspace,
        key="report-manifest.json",
        manifest=_manifest(_document(as_of=frozen_now)),
        receipt_id="receipt-1",
        created_at=frozen_now,
    )

    written = (workspace.selected_root / receipt.relative_path).resolve()
    assert written.is_relative_to(workspace.output_root.path)
    assert written.is_file()


# ---------------------------------------------------------------------------
# The manifest's own consistency: one document part, one name per part
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_a_manifest_may_not_hold_two_document_parts(frozen_now: datetime) -> None:
    """A manifest is about one report.

    Two document parts would make "which report is this" answerable two
    ways, and the whole point of the digest is that it answers it. The
    message is the one that says *how many* there are, so that a reader of a
    failure is told which of the manifest's two guards spoke.
    """
    manifest = _manifest(_document(as_of=frozen_now))
    payload = json.loads(manifest.canonical_bytes().decode("utf-8"))
    payload["parts"].append(dict(payload["parts"][0]))

    with pytest.raises(ValidationError, match="holds 2 document parts"):
        ReportManifest.model_validate(payload)


@pytest.mark.unit
def test_a_manifest_may_not_hold_no_document_part() -> None:
    """And it may not hold none.

    The document is the subject of the manifest, and a manifest with no
    subject is a manifest about nothing.
    """
    with pytest.raises(ValidationError, match="document parts"):
        ReportManifest.model_validate(
            {
                "report_sha256": _hash("report"),
                "parts": [
                    {
                        "part_id": "tab-1",
                        "part_kind": "table",
                        "relative_path": TABLE_PATH,
                        "content_sha256": TABLE_HASH,
                        "lineage": [
                            {
                                "target_kind": "material_file",
                                "target_id": "material/exp1.csv",
                                "content_sha256": SOURCE_HASH,
                            }
                        ],
                    }
                ],
            }
        )


@pytest.mark.unit
def test_a_manifest_may_not_name_the_same_part_twice(frozen_now: datetime) -> None:
    """Two rows for one id make "which part is this" answerable two ways."""
    manifest = _manifest(_document(as_of=frozen_now))
    payload = json.loads(manifest.canonical_bytes().decode("utf-8"))
    payload["parts"].append(dict(payload["parts"][1]))

    with pytest.raises(ValidationError, match="names the same part twice"):
        ReportManifest.model_validate(payload)


@pytest.mark.unit
def test_the_parts_are_sorted_by_id(frozen_now: datetime) -> None:
    """The order is a fact about the manifest, not about how it was built.

    Two manifests of the same report have the same parts in the same order,
    so a reader can compare them without sorting first.
    """
    manifest = _manifest(_document(as_of=frozen_now))

    ids = [part.part_id for part in manifest.parts]
    assert ids == sorted(ids)


@pytest.mark.unit
def test_the_part_kinds_are_a_closed_set() -> None:
    """A part that could be several things at once would be listed several
    ways."""
    assert {kind.value for kind in ManifestPartKind} == {"figure", "table", "document"}
