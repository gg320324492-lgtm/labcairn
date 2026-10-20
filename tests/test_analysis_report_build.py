"""The report builder: the ledger's records and artefacts, turned into a document.

LC-P1-11's model is the spine and this is the thing that fills it. T00 built
:class:`~labcairn.reports.model.ReportDocument` and the six rules it refuses
to break; T01 built the four renderers; T02 built the artefact manifest; and
between them they left the middle of the chain out — **nothing assembled a
document out of what a task actually has**.

So this file tests the builder the way the model is judged: **every rule
needs a test that fails when the rule is broken.** The helpers below build a
task with records in every one of the six states, a figure with its own
manifest, and a table, and the tests then change exactly one thing so that
a failure points at a decision rather than at a fixture.

The properties that matter, and the tests that hold them:

* a conflicted record is not a claim --
  ``test_a_record_that_may_not_be_stated_is_disclosed``
* a view carries the record's value and status --
  ``test_the_claim_view_is_the_record``
* a citation is the record's own address --
  ``test_a_claim_cites_the_addresses_its_record_was_read_from``
* a figure's manifest is the artefact's own --
  ``test_a_figure_carries_the_manifest_its_artefact_recorded``
* a disclosure's reason is never blank --
  ``test_a_disclosure_carries_a_reason_the_ledger_supports``
* the snapshot names the carried records, and only those --
  ``test_the_snapshot_names_exactly_the_records_the_report_carries``

The refusal tests matter as much as the routing ones. A builder that drops a
record it cannot cite produces a report that reads complete and is not, and
the only thing that stops it is a test that says the build is refused.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

import pytest

from labcairn.analysis.manifest import (
    FileRef,
    RenderEnvironment,
    ReproducibilityManifest,
    canonical_digest,
    manifest_bytes,
)
from labcairn.evidence.record import EvidenceRecord, VerificationRecord
from labcairn.evidence.states import (
    CheckKind,
    CheckOutcome,
    EvidenceCreator,
    EvidenceKind,
    VerificationStatus,
)
from labcairn.reports.build import (
    FIGURES_SECTION_ID,
    FINDINGS_SECTION_ID,
    TABLES_SECTION_ID,
    UNRESOLVED_SECTION_ID,
    ReportBuildRefusedError,
    build_report_document,
)
from labcairn.reports.model import (
    BlockKind,
    ClaimBlock,
    FigureBlock,
    InterpretationBlock,
    NarrativeBlock,
    ReportClaim,
    ReportDocument,
    TableBlock,
    UnresolvedBlock,
)
from labcairn.reports.receipt import (
    ArtifactKind,
    ArtifactProducerKind,
    ArtifactReceipt,
    DerivationRef,
    DerivationTargetKind,
)
from labcairn.reports.render.constants import INTERPRETATION_MARKER
from labcairn.reports.render.markdown import render_markdown
from labcairn.reports.render.resolve import resolve
from labcairn.sources.locators import ComputationLocator, PdfLocator, SourceLocator
from labcairn.sources.source import (
    AnchorKind,
    Source,
    SourceAnchor,
    SourceKind,
    SourceReadability,
)

# --------------------------------------------------------------------------- #
# Fixtures and helpers
# --------------------------------------------------------------------------- #

MOMENT: datetime = datetime(2026, 1, 1, tzinfo=UTC)


def _hash(marker: str) -> str:
    """A well-formed content hash for *marker*.

    Derived from the marker rather than written out, so that two different
    hashes in one test are visibly different hashes and a test that expects
    a *mismatch* cannot pass by accident.
    """
    return hashlib.sha256(marker.encode("utf-8")).hexdigest()


#: The bytes of the source the records were read from.
SOURCE_HASH: str = _hash("source")
#: The bytes of a *different* version of that source: what a drifted anchor
#: is bound to.
DRIFTED_HASH: str = _hash("drifted-source")
#: The bytes of the figure artefact.
FIGURE_HASH: str = _hash("figure")
#: The bytes of the table artefact.
TABLE_HASH: str = _hash("table")
#: The bytes of the recipe the figure was made with.
RECIPE_HASH: str = _hash("recipe")
#: The number the ledger holds, at a precision a rounding step would lose.
LEDGER_VALUE: float = 4.253

#: The caption the author gave the figure.
FIGURE_CAPTION: str = "Mean yield across the five measured runs."
#: The reading the author gave the figure, which the recipe keeps apart
#: from the caption because an interpretation is never machine-verified.
FIGURE_INTERPRETATION: str = "The treated group yields more than the control."


def _source(
    *,
    source_id: str = "src-1",
    content_sha256: str = SOURCE_HASH,
    readability: SourceReadability = SourceReadability.READABLE,
) -> Source:
    """One ingested material file."""
    return Source(
        source_id=source_id,
        kind=SourceKind.PDF,
        display_name="exp1.pdf",
        relative_path="material/exp1.pdf",
        content_sha256=content_sha256,
        size_bytes=1024,
        readability=readability,
        readability_disclosure=(
            "the file has no text layer and OCR is not available"
            if readability is not SourceReadability.READABLE
            else None
        ),
        ingested_at=MOMENT,
    )


def _anchor(
    *,
    anchor_id: str = "anc-1",
    source_id: str = "src-1",
    page: int = 3,
    bound_sha256: str = SOURCE_HASH,
) -> SourceAnchor:
    """One addressable place inside a source."""
    return SourceAnchor(
        anchor_id=anchor_id,
        source_id=source_id,
        kind=AnchorKind.QUOTATION,
        locator=PdfLocator(page=page),
        bound_source_sha256=bound_sha256,
        created_at=MOMENT,
    )


def _entry(
    check: CheckKind = CheckKind.C3,
    outcome: CheckOutcome = CheckOutcome.PASS,
    *,
    detail: str = "the cell agrees with the record",
    checker_id: str = "rule:c3",
) -> VerificationRecord:
    """One entry of a verification log."""
    return VerificationRecord(
        check=check,
        checker_id=checker_id,
        outcome=outcome,
        detail=detail,
        checked_at=MOMENT,
    )


def _record(
    *,
    record_id: str,
    kind: EvidenceKind = EvidenceKind.NUMERIC,
    status: VerificationStatus = VerificationStatus.VERIFIED_BY_RULE,
    text: str | None = None,
    value: float | None = LEDGER_VALUE,
    unit: str | None = "%",
    anchors: tuple[str, ...] = ("anc-1",),
    source_hash: str | None = SOURCE_HASH,
    created_by: EvidenceCreator = EvidenceCreator.RULE,
    log: tuple[VerificationRecord, ...] | None = None,
    superseded_by: str | None = None,
) -> EvidenceRecord:
    """An evidence record, valid under the ledger's own rules.

    The status decides what the log must contain, because the ledger's rule
    is that a status may never be upgraded without the entry that earned it:
    ``verified_by_rule`` needs a passing check, ``user_attested`` needs a
    person and an entry, ``conflicted`` needs an entry, and ``unsupported``
    needs either a failing check or no anchors at all.
    """
    if log is None:
        if status is VerificationStatus.VERIFIED_BY_RULE:
            log = (_entry(),)
        elif status is VerificationStatus.USER_ATTESTED:
            created_by = EvidenceCreator.USER
            log = (_entry(CheckKind.C1, detail="a person read it and said so"),)
        elif status is VerificationStatus.CONFLICTED:
            log = (_entry(CheckKind.C3, CheckOutcome.FAIL, detail="the two readings differ"),)
        elif status is VerificationStatus.UNSUPPORTED:
            log = (_entry(CheckKind.C3, CheckOutcome.FAIL, detail="no cell agrees"),)
        else:
            log = ()

    located = status is not VerificationStatus.PLANNED
    return EvidenceRecord(
        evidence_id=record_id,
        task_id="task-1",
        kind=kind,
        text=text,
        value=value,
        unit=unit,
        anchor_ids=anchors,
        extracted_span="the quoted span" if located else None,
        extracted_span_sha256=_hash(f"span-{record_id}") if located else None,
        status=status,
        verification_log=log,
        created_by=created_by,
        created_by_id="rule:c3",
        source_content_hash=source_hash,
        created_at=MOMENT,
        superseded_by=superseded_by,
    )


def _manifest(*, mean: float = LEDGER_VALUE) -> ReproducibilityManifest:
    """A valid reproducibility manifest for the figure.

    Built through the manifest's own fields rather than through
    :func:`labcairn.analysis.manifest.build_manifest`, because the builder
    wants a source on disk and a workspace, and none of that is what this
    file is about.
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


def _manifest_receipt(
    *, receipt_id: str = "manifest-1", manifest: ReproducibilityManifest
) -> ArtifactReceipt:
    """The receipt of the artefact that holds a manifest.

    The receipt's ``content_sha256`` is the hash of the file the manifest was
    written to, which is the manifest's canonical bytes — so the builder can
    check that the manifest it was given is the artefact's own.
    """
    return ArtifactReceipt(
        receipt_id=receipt_id,
        task_id="task-1",
        kind=ArtifactKind.MANIFEST,
        relative_path="analysis/mean/run1.manifest.json",
        content_sha256=hashlib.sha256(manifest_bytes(manifest)).hexdigest(),
        size_bytes=512,
        produced_by=ArtifactProducerKind.ANALYSIS_OPERATOR,
        producer_id="labcairn.analysis.mean@1.0.0",
        derived_from=(
            DerivationRef(
                target_kind=DerivationTargetKind.MATERIAL_FILE,
                target_id="material/exp1.csv",
                content_sha256=SOURCE_HASH,
            ),
        ),
        media_type="application/json",
        created_at=MOMENT,
    )


def _figure_receipt(
    *,
    receipt_id: str = "figure-1",
    manifest_receipt: ArtifactReceipt,
    revision: int = 1,
    relative_path: str = "analysis/mean/run1.figure.svg",
    content_sha256: str = FIGURE_HASH,
) -> ArtifactReceipt:
    """The receipt of a figure, whose chain runs back through its manifest."""
    return ArtifactReceipt(
        receipt_id=receipt_id,
        task_id="task-1",
        kind=ArtifactKind.FIGURE,
        relative_path=relative_path,
        content_sha256=content_sha256,
        size_bytes=2048,
        revision=revision,
        produced_by=ArtifactProducerKind.ANALYSIS_OPERATOR,
        producer_id="labcairn.analysis.mean@1.0.0",
        derived_from=(
            DerivationRef(
                target_kind=DerivationTargetKind.ARTIFACT,
                target_id=manifest_receipt.receipt_id,
                content_sha256=manifest_receipt.content_sha256,
            ),
            *manifest_receipt.derived_from,
        ),
        media_type="image/svg+xml",
        created_at=MOMENT,
    )


def _table_receipt(*, receipt_id: str = "table-1") -> ArtifactReceipt:
    """The receipt of a table artefact."""
    return ArtifactReceipt(
        receipt_id=receipt_id,
        task_id="task-1",
        kind=ArtifactKind.TABLE,
        relative_path="analysis/mean/run1.table.csv",
        content_sha256=TABLE_HASH,
        size_bytes=128,
        produced_by=ArtifactProducerKind.ANALYSIS_OPERATOR,
        producer_id="labcairn.analysis.mean@1.0.0",
        media_type="text/csv",
        created_at=MOMENT,
    )


# --------------------------------------------------------------------------- #
# the task under test
# --------------------------------------------------------------------------- #


@pytest.fixture
def task() -> dict[str, Any]:
    """A task with a record in every state that can be carried or not.

    The records are:

    * ``rec-num`` -- a verified number, and the report's first finding;
    * ``rec-text`` -- an attested sentence, and its second finding;
    * ``rec-conflict`` -- a conflict, and a disclosure;
    * ``rec-unsupported`` -- a record nothing supports, and a disclosure;
    * ``rec-unanchored`` -- an unsupported record with no anchor at all;
    * ``rec-planned`` -- a declaration, and not carried;
    * ``rec-superseded`` -- a record that has been replaced, and not carried.
    """
    manifest = _manifest()
    manifest_artifact = _manifest_receipt(manifest=manifest)
    figure = _figure_receipt(manifest_receipt=manifest_artifact)
    table = _table_receipt()

    return {
        "title": "Yield across the five measured runs",
        "as_of": MOMENT,
        "records": [
            _record(record_id="rec-num"),
            _record(
                record_id="rec-text",
                kind=EvidenceKind.CLAIM,
                status=VerificationStatus.USER_ATTESTED,
                text="The material reports a yield of 4.253%.",
                value=None,
                unit=None,
                anchors=("anc-2",),
            ),
            _record(record_id="rec-conflict", status=VerificationStatus.CONFLICTED),
            _record(record_id="rec-unsupported", status=VerificationStatus.UNSUPPORTED),
            _record(
                record_id="rec-unanchored",
                status=VerificationStatus.UNSUPPORTED,
                anchors=(),
                source_hash=None,
                log=(),
            ),
            _record(
                record_id="rec-planned",
                status=VerificationStatus.PLANNED,
                anchors=(),
                source_hash=None,
                log=(),
            ),
            _record(record_id="rec-superseded", superseded_by="rec-num"),
        ],
        "artifacts": [manifest_artifact, figure, table],
        "sources": [_source()],
        "anchors": {
            "anc-1": _anchor(anchor_id="anc-1", page=3),
            "anc-2": _anchor(anchor_id="anc-2", page=7),
        },
        "manifests": {"manifest-1": manifest},
        "captions": {"figure-1": FIGURE_CAPTION},
        "interpretations": {"figure-1": FIGURE_INTERPRETATION},
    }


def _build(task: dict[str, Any], **overrides: Any) -> ReportDocument:
    """Build the document for the task, with whatever the test changes."""
    arguments = {**task, **overrides}
    return build_report_document(
        title=arguments["title"],
        as_of=arguments["as_of"],
        records=arguments["records"],
        artifacts=arguments["artifacts"],
        sources=arguments["sources"],
        anchors=arguments["anchors"],
        manifests=arguments["manifests"],
        captions=arguments["captions"],
        interpretations=arguments.get("interpretations"),
    )


def _claim_for(document: ReportDocument, record_id: str) -> ReportClaim:
    """The claim the document makes about *record_id*."""
    return next(claim for claim in document.claims if claim.record.record_id == record_id)


# --------------------------------------------------------------------------- #
# the routing
# --------------------------------------------------------------------------- #


def test_a_record_that_may_be_stated_becomes_a_claim(task: dict[str, Any]) -> None:
    """A finding-status record is stated, and it is stated as a claim."""
    document = _build(task)

    claim = _claim_for(document, "rec-num")
    assert claim.claim_id == "clm-rec-num"
    assert claim.record.status is VerificationStatus.VERIFIED_BY_RULE


def test_a_record_that_may_not_be_stated_is_disclosed(task: dict[str, Any]) -> None:
    """A conflicted record is disclosed, never stated.

    ADR-0004's A5: neither of two disagreeing readings wins by recency and
    the conflict is *displayed*. So the record is in the unresolved records
    and is **not** among the claims — the two are different statements and
    the document may not make both.
    """
    document = _build(task)

    disclosed = {record.record.record_id for record in document.unresolved_records}
    claimed = {claim.record.record_id for claim in document.claims}
    assert "rec-conflict" in disclosed
    assert "rec-conflict" not in claimed


def test_an_unsupported_record_is_disclosed_too(task: dict[str, Any]) -> None:
    """A record nothing supports is not a statement either."""
    document = _build(task)

    disclosed = {record.record.record_id for record in document.unresolved_records}
    assert "rec-unsupported" in disclosed
    assert "rec-unsupported" not in {claim.record.record_id for claim in document.claims}


def test_a_planned_record_is_not_carried(task: dict[str, Any]) -> None:
    """A planned record is a declaration with nothing behind it.

    The model's own words: *"a record that is neither is a record the report
    does not carry."* It is not a claim and it is not a disclosure, so it is
    in neither — and, because the snapshot names exactly the records the
    report carries, it is not in the snapshot either.
    """
    document = _build(task)

    carried = {claim.record.record_id for claim in document.claims} | {
        record.record.record_id for record in document.unresolved_records
    }
    assert "rec-planned" not in carried
    assert "rec-planned" not in document.snapshot.record_ids


def test_a_superseded_record_is_not_carried(task: dict[str, Any]) -> None:
    """The ledger keeps the old row for the audit trail; the report states the new one.

    A report that stated both would say the same thing twice, and the second
    statement is the one no check would notice.
    """
    document = _build(task)

    carried = {claim.record.record_id for claim in document.claims} | {
        record.record.record_id for record in document.unresolved_records
    }
    assert "rec-superseded" not in carried
    assert "rec-superseded" not in document.snapshot.record_ids


def test_the_snapshot_names_exactly_the_records_the_report_carries(task: dict[str, Any]) -> None:
    """The snapshot is the report's statement of which records it is a view of.

    Both halves of the model's rule: no record the report carries is left
    unnamed, and no record is named that the report does not carry. The
    second half is the one a builder gets wrong by gathering the task's
    records and naming them all.
    """
    document = _build(task)

    carried = {claim.record.record_id for claim in document.claims} | {
        record.record.record_id for record in document.unresolved_records
    }
    assert set(document.snapshot.record_ids) == carried
    assert list(document.snapshot.record_ids) == sorted(document.snapshot.record_ids)


def test_the_snapshot_names_the_moment(task: dict[str, Any]) -> None:
    """The document is a frozen view, and it says when it was taken."""
    document = _build(task)

    assert document.snapshot.as_of == MOMENT


# --------------------------------------------------------------------------- #
# the claim's view
# --------------------------------------------------------------------------- #


def test_the_claim_view_is_the_record(task: dict[str, Any]) -> None:
    """Every field of the view is the record's own field.

    The number is the ledger's number at the ledger's precision, the unit is
    the declared one, the kind is the record's, and the status is the record's
    status — a report that raised a status would be claiming a record was
    verified by a rule when it was not.
    """
    document = _build(task)

    view = _claim_for(document, "rec-num").record
    assert view.value == LEDGER_VALUE
    assert view.value == 4.253
    assert view.unit == "%"
    assert view.record_kind is EvidenceKind.NUMERIC
    assert view.text is None
    assert view.status is VerificationStatus.VERIFIED_BY_RULE
    assert view.anchor_ids == ("anc-1",)
    assert view.source_content_hash == SOURCE_HASH

    # A second record, so that a status the builder raised for *every* record
    # cannot pass: rec-num's status happens to be the one a raised status
    # would be, and rec-text's is not.
    attested = _claim_for(document, "rec-text").record
    assert attested.status is VerificationStatus.USER_ATTESTED
    assert attested.record_kind is EvidenceKind.CLAIM
    assert attested.anchor_ids == ("anc-2",)


def test_a_claim_rests_on_the_record_it_names(task: dict[str, Any]) -> None:
    """The claim carries the record, not a reference to one."""
    document = _build(task)

    claim = _claim_for(document, "rec-text")
    assert claim.record.record_kind is EvidenceKind.CLAIM
    assert claim.record.text == "The material reports a yield of 4.253%."
    assert claim.record.value is None


def test_a_claim_cites_the_addresses_its_record_was_read_from(task: dict[str, Any]) -> None:
    """A citation is a locator, and it is the record's own.

    The footnote names the source, the address inside it and the bytes it
    pointed at — and the address is the one the record's own anchor carries.
    A builder that cited some other address would produce a report whose
    citations check out and whose claims do not.
    """
    document = _build(task)

    claim = _claim_for(document, "rec-num")
    assert len(claim.footnote_ids) == 1
    footnote = next(note for note in document.footnotes if note.footnote_id in claim.footnote_ids)
    assert footnote.source_id == "src-1"
    assert footnote.locator == PdfLocator(page=3)
    assert footnote.content_sha256 == SOURCE_HASH

    # A second record, so that a citation that named *some* address cannot
    # pass: rec-num's address is the first one in the map, and rec-text's is
    # the second.
    attested = _claim_for(document, "rec-text")
    attested_note = next(
        note for note in document.footnotes if note.footnote_id in attested.footnote_ids
    )
    assert attested_note.locator == PdfLocator(page=7)


def test_a_claim_cites_every_anchor_its_record_names(task: dict[str, Any]) -> None:
    """A record read from two places is cited from both."""
    document = _build(
        task,
        records=[
            _record(record_id="rec-two", anchors=("anc-1", "anc-2")),
            *_task_records(task),
        ],
    )

    claim = _claim_for(document, "rec-two")
    assert len(claim.footnote_ids) == 2
    locators = {
        footnote.locator
        for footnote in document.footnotes
        if footnote.footnote_id in claim.footnote_ids
    }
    assert locators == {PdfLocator(page=3), PdfLocator(page=7)}


def _task_records(task: dict[str, Any]) -> list[EvidenceRecord]:
    """The task's records, as the fixture holds them."""
    return list(task["records"])


# --------------------------------------------------------------------------- #
# the disclosure's reason
# --------------------------------------------------------------------------- #


def test_a_disclosure_carries_a_reason_the_ledger_supports(task: dict[str, Any]) -> None:
    """The reason is never blank, and it is the ledger's own words.

    The ledger holds a state and a log, not a sentence, so the sentence has
    to be written — and it is written out of the log: the check that failed,
    the checker, the moment and the detail, quoted rather than paraphrased.
    """
    document = _build(task)

    disclosure = next(
        record
        for record in document.unresolved_records
        if record.record.record_id == "rec-conflict"
    )
    assert disclosure.reason.strip()
    assert "conflicted" in disclosure.reason
    assert "c3" in disclosure.reason
    assert "the two readings differ" in disclosure.reason


def test_a_disclosure_of_an_unanchored_record_says_so(task: dict[str, Any]) -> None:
    """A record with no anchor is disclosed with the absence as its reason.

    ADR-0004's Contract 2 allows "no anchor at all" as a reason a record is
    unsupported, and the absence is the whole of the reason.
    """
    document = _build(task)

    disclosure = next(
        record
        for record in document.unresolved_records
        if record.record.record_id == "rec-unanchored"
    )
    assert disclosure.reason.strip()
    assert "no anchor" in disclosure.reason


# --------------------------------------------------------------------------- #
# the artefacts
# --------------------------------------------------------------------------- #


def test_a_figure_carries_the_manifest_its_artefact_recorded(task: dict[str, Any]) -> None:
    """The figure's manifest is the artefact's own, and it is checked.

    The manifest artefact recorded the hash of the file it wrote; the
    builder hashes the manifest it was given again and compares. A manifest
    that is somebody else's would produce a report whose figure cannot be
    reproduced from its own derivation.
    """
    document = _build(task)

    assert len(document.figures) == 1
    figure = document.figures[0]
    assert figure.figure_id == "fig-figure-1"
    assert figure.relative_path == "analysis/mean/run1.figure.svg"
    assert figure.content_sha256 == FIGURE_HASH
    assert figure.caption == FIGURE_CAPTION
    assert figure.manifest.operator == "labcairn.analysis.mean@1.0.0"


def test_a_figure_whose_manifest_is_not_its_own_is_refused(task: dict[str, Any]) -> None:
    """A manifest that is not the artefact's own is refused, not carried.

    The figure names one manifest; a different one is a derivation of a
    different computation, and the report would be showing a picture under
    the numbers of something else.
    """
    other = _manifest(mean=99.0)
    with pytest.raises(ReportBuildRefusedError, match="not the artefact's own"):
        _build(task, manifests={"manifest-1": other})


def test_a_figure_with_no_caption_is_refused(task: dict[str, Any]) -> None:
    """The caption is the author's words, so the builder will not write one.

    The model forbids a renderer from inventing a caption, and a caption
    composed from the file name would say nothing about what is plotted.
    """
    with pytest.raises(ReportBuildRefusedError, match="no caption"):
        _build(task, captions={})


def test_a_figure_with_no_manifest_is_refused(task: dict[str, Any]) -> None:
    """A figure without the derivation that produced it is refused."""
    with pytest.raises(ReportBuildRefusedError, match="was not given"):
        _build(task, manifests={})


def test_a_table_carries_its_path_and_hash(task: dict[str, Any]) -> None:
    """A table is a fact about a file: where it is and what it holds."""
    document = _build(task)

    assert len(document.tables) == 1
    table = document.tables[0]
    assert table.table_id == "tbl-table-1"
    assert table.relative_path == "analysis/mean/run1.table.csv"
    assert table.content_sha256 == TABLE_HASH


def test_the_newest_revision_of_an_artefact_is_the_one_carried(task: dict[str, Any]) -> None:
    """Two receipts at one path are two emissions of one artefact.

    A report that carried both would show the same figure twice, and the
    second copy is the one no check would notice.
    """
    manifest_artifact = _manifest_receipt(manifest=_manifest())
    first = _figure_receipt(
        receipt_id="figure-1",
        manifest_receipt=manifest_artifact,
        revision=1,
    )
    second = _figure_receipt(
        receipt_id="figure-2",
        manifest_receipt=manifest_artifact,
        revision=2,
        content_sha256=_hash("figure-v2"),
    )

    document = _build(
        task,
        artifacts=[manifest_artifact, first, second],
        captions={"figure-1": FIGURE_CAPTION, "figure-2": FIGURE_CAPTION},
    )

    assert [figure.figure_id for figure in document.figures] == ["fig-figure-2"]
    assert document.figures[0].content_sha256 == _hash("figure-v2")


def test_an_artefact_of_a_kind_the_report_has_no_part_for_is_not_carried(
    task: dict[str, Any],
) -> None:
    """The report's own artefacts are not parts of the report."""
    report_artifact = ArtifactReceipt(
        receipt_id="report-1",
        task_id="task-1",
        kind=ArtifactKind.REPORT,
        relative_path="reports/report-1.md",
        content_sha256=_hash("report"),
        size_bytes=99,
        produced_by=ArtifactProducerKind.STAGE,
        producer_id="labcairn.reports.render",
        media_type="text/markdown",
        created_at=MOMENT,
    )

    document = _build(task, artifacts=[*task["artifacts"], report_artifact])

    assert {figure.figure_id for figure in document.figures} == {"fig-figure-1"}
    assert {table.table_id for table in document.tables} == {"tbl-table-1"}


# --------------------------------------------------------------------------- #
# the refusals
# --------------------------------------------------------------------------- #


def test_a_record_with_no_anchor_is_refused(task: dict[str, Any]) -> None:
    """A finding that cannot cite an address is refused, not dropped.

    The record's state says it may be stated, so dropping it would leave a
    verified finding out of a report whose snapshot claims to be a view of
    the records. The build is refused instead.
    """
    broken = _record(record_id="rec-num").model_copy(update={"anchor_ids": ()})
    with pytest.raises(ReportBuildRefusedError, match="no anchor"):
        _build(task, records=[broken, *_task_records(task)[1:]])


def test_a_record_whose_anchor_the_ledger_does_not_hold_is_refused(
    task: dict[str, Any],
) -> None:
    """A dangling anchor id is a citation the report cannot resolve."""
    with pytest.raises(ReportBuildRefusedError, match="which the ledger does not hold"):
        _build(task, anchors={})


def test_a_citation_that_names_other_bytes_is_refused(task: dict[str, Any]) -> None:
    """A citation must be an address the record was actually read from.

    The anchor is bound to the bytes it was made against; the record names
    the bytes it was read from. When the two differ, the address does not
    name this record's evidence.
    """
    anchors = {**task["anchors"], "anc-1": _anchor(anchor_id="anc-1", bound_sha256=DRIFTED_HASH)}
    with pytest.raises(ReportBuildRefusedError, match="the record was actually read from"):
        _build(task, anchors=anchors)


def test_a_citation_into_an_unreadable_source_is_refused(task: dict[str, Any]) -> None:
    """ADR-0004's A7 refuses an unreadable source as a citation target."""
    unreadable = _source(
        source_id="src-2",
        content_sha256=SOURCE_HASH,
        readability=SourceReadability.UNREADABLE_NO_OCR,
    )
    anchors = {**task["anchors"], "anc-1": _anchor(anchor_id="anc-1", source_id="src-2")}
    with pytest.raises(ReportBuildRefusedError, match="citation target"):
        _build(task, sources=[unreadable], anchors=anchors)


def test_a_citation_into_a_source_the_report_does_not_carry_is_refused(
    task: dict[str, Any],
) -> None:
    """A citation into material the report does not have cannot be opened."""
    with pytest.raises(ReportBuildRefusedError, match="does not carry"):
        _build(task, sources=[])


def test_a_task_with_nothing_to_report_is_refused(task: dict[str, Any]) -> None:
    """A report with nothing in it is refused rather than faked.

    The model refuses a document with no section, and a section with nothing
    under its heading is a heading the reader cannot do anything with. The
    sentence 'there is nothing here' is the author's, and the builder is not
    allowed to write it.
    """
    empty = [
        _record(
            record_id="rec-planned",
            status=VerificationStatus.PLANNED,
            anchors=(),
            source_hash=None,
            log=(),
        )
    ]
    with pytest.raises(ReportBuildRefusedError, match="nothing a report may carry"):
        _build(
            task,
            records=empty,
            artifacts=[],
            manifests={},
            captions={},
            interpretations={},
        )


def test_two_artefacts_with_one_receipt_id_are_refused(task: dict[str, Any]) -> None:
    """One id that means two artefacts makes 'which one is it' unanswerable."""
    table = _table_receipt()
    twin = table.model_copy(update={"relative_path": "analysis/mean/other.table.csv"})
    with pytest.raises(ReportBuildRefusedError, match="share a receipt id"):
        _build(task, artifacts=[*task["artifacts"], table, twin])


# --------------------------------------------------------------------------- #
# the sections
# --------------------------------------------------------------------------- #


def test_the_sections_place_every_block_the_document_carries(task: dict[str, Any]) -> None:
    """The layout is four sections, one per kind, and each places its blocks.

    Grouped by kind, because the model's rules are about kinds: a
    disclosure may not be stated as a finding, and a claim may not be
    restated as an interpretation. A layout that mixed kinds would have to be
    argued for; one that separates them makes the mixing impossible.
    """
    document = _build(task)

    assert [section.section_id for section in document.sections] == [
        FINDINGS_SECTION_ID,
        FIGURES_SECTION_ID,
        TABLES_SECTION_ID,
        UNRESOLVED_SECTION_ID,
    ]

    findings = document.sections[0]
    claim_blocks = [block for block in findings.blocks if isinstance(block, ClaimBlock)]
    assert len(claim_blocks) == len(findings.blocks)
    assert {block.claim_id for block in claim_blocks} == {
        claim.claim_id for claim in document.claims
    }

    figures = document.sections[1]
    figure_blocks = [block for block in figures.blocks if isinstance(block, FigureBlock)]
    assert {block.figure_id for block in figure_blocks} == {
        figure.figure_id for figure in document.figures
    }
    # The figure's own interpretation is placed with it, so the section holds
    # the figure and the reading of it and nothing else.
    assert all(isinstance(block, FigureBlock | InterpretationBlock) for block in figures.blocks)

    tables = document.sections[2]
    table_blocks = [block for block in tables.blocks if isinstance(block, TableBlock)]
    assert len(table_blocks) == len(tables.blocks)
    assert {block.table_id for block in table_blocks} == {
        table.table_id for table in document.tables
    }


def test_a_disclosure_is_placed_in_the_disclosure_section_and_nowhere_else(
    task: dict[str, Any],
) -> None:
    """A conflict may not be drawn where a finding is drawn."""
    document = _build(task)

    placed_in_findings = [
        block for block in document.sections[0].blocks if isinstance(block, UnresolvedBlock)
    ]
    assert placed_in_findings == []

    disclosed = document.sections[-1]
    assert all(isinstance(block, UnresolvedBlock) for block in disclosed.blocks)


def test_the_builder_writes_no_narrative(task: dict[str, Any]) -> None:
    """No narrative: a narrative describes what the report covers, and
    nothing in the ledger holds those sentences.

    The only prose the builder carries is a figure's own interpretation,
    and that one it carries rather than writes.
    """
    document = _build(task)

    for section in document.sections:
        for block in section.blocks:
            assert not isinstance(block, NarrativeBlock)


def test_a_figures_own_interpretation_is_carried_as_an_interpretation(
    task: dict[str, Any],
) -> None:
    """The recipe's reading of the figure reaches the report, marked.

    The recipe keeps the caption and the interpretation apart for ADR-0004's
    A10, and so does the report: the caption says what is plotted and the
    interpretation says what it means, and only the second is an
    interpretation.
    """
    document = _build(task)

    figures_section = next(
        section for section in document.sections if section.section_id == FIGURES_SECTION_ID
    )
    readings = [block for block in figures_section.blocks if isinstance(block, InterpretationBlock)]
    assert len(readings) == 1
    assert readings[0].text == FIGURE_INTERPRETATION

    # Immediately after the figure it belongs to.
    kinds = [block.block_kind for block in figures_section.blocks]
    assert kinds == [BlockKind.FIGURE, BlockKind.INTERPRETATION]


def test_a_figure_with_no_interpretation_contributes_no_block(task: dict[str, Any]) -> None:
    """An absent interpretation is absent, and not an empty one.

    The recipe's field is optional, and a figure with none must not carry a
    block saying nothing — the marker would then ride on an absence.
    """
    document = _build(task, interpretations={})

    figures_section = next(
        section for section in document.sections if section.section_id == FIGURES_SECTION_ID
    )
    assert [block.block_kind for block in figures_section.blocks] == [BlockKind.FIGURE]


def test_the_interpretation_reaches_the_export_marked_as_unverified(
    task: dict[str, Any],
) -> None:
    """The marker fires, and it is the figure's own marker.

    A claim resting on a ``claim`` or ``result`` record is marked for the
    same reason, and the marker is the constant the figure's renderer uses.
    The two lines are the report's whole A10 story: a statement no rule
    confirmed and a reading no rule verified.
    """
    document = _build(task)

    markdown = render_markdown(document)
    text = markdown.decode("utf-8") if isinstance(markdown, bytes) else markdown

    marked = [line for line in text.splitlines() if INTERPRETATION_MARKER in line]
    # The Markdown writer escapes the full stop, so the comparison is made
    # without it: the writer escapes for the reader and the text under the
    # marker is the researcher's own.
    assert any(FIGURE_INTERPRETATION.rstrip(".") in line for line in marked)


def test_an_interpretation_that_names_no_figure_is_refused(task: dict[str, Any]) -> None:
    """A reading keyed to nothing would be dropped in silence.

    A parameter that is accepted and ignored is a parameter that lies, and a
    mistyped key is exactly how the report would lose a figure's reading
    without anything saying so.
    """
    with pytest.raises(ReportBuildRefusedError, match="does not carry"):
        _build(task, interpretations={"figure-typo": FIGURE_INTERPRETATION})


def test_a_blank_interpretation_is_refused(task: dict[str, Any]) -> None:
    """A blank reading is a different fact from an absent one."""
    with pytest.raises(ReportBuildRefusedError, match="blank interpretation"):
        _build(task, interpretations={"figure-1": "   "})


def test_a_section_with_nothing_to_carry_is_not_a_section(task: dict[str, Any]) -> None:
    """A kind with nothing to carry contributes no section at all."""
    document = _build(task, artifacts=[], manifests={}, captions={}, interpretations={})

    assert [section.section_id for section in document.sections] == [
        FINDINGS_SECTION_ID,
        UNRESOLVED_SECTION_ID,
    ]


def test_the_document_can_be_drawn(task: dict[str, Any]) -> None:
    """The builder's output is one the renderers can walk.

    The renderers draw the model and decide nothing, so a document that
    cannot be resolved is a document nobody can export.
    """
    document = _build(task)

    resolved = resolve(document)
    assert resolved.title == "Yield across the five measured runs"
    assert len(resolved.sections) == 4
    assert resolved.footnotes


# --------------------------------------------------------------------------- #
# determinism
# --------------------------------------------------------------------------- #


def test_two_gatherings_of_the_same_task_produce_the_same_bytes(task: dict[str, Any]) -> None:
    """The document is a function of the task, not of the order it was gathered in.

    The report's bytes are hashed, and a document that rendered two ways
    could not be compared with another run's.
    """
    shuffled = dict(task)
    shuffled["records"] = list(reversed(task["records"]))
    shuffled["artifacts"] = list(reversed(task["artifacts"]))

    assert _build(task).canonical_bytes() == _build(shuffled).canonical_bytes()


def test_the_title_and_the_moment_are_the_callers(task: dict[str, Any]) -> None:
    """The title is content and the moment is the caller's; the builder takes both."""
    later = datetime(2026, 3, 4, 12, 30, tzinfo=UTC)
    document = _build(task, title="Another report", as_of=later)

    assert document.title == "Another report"
    assert document.snapshot.as_of == later


# --------------------------------------------------------------------------- #
# the types the builder refuses to draw from
# --------------------------------------------------------------------------- #


def test_the_builder_never_reaches_for_the_store() -> None:
    """The builder is a function of its arguments, and never of the ledger.

    The repository has a guard that fails when a module outside the
    application layer reaches past it, and this is the reason the builder is
    written the way it is: a builder that read the store would be a second
    way in.
    """
    import ast
    from pathlib import Path

    source = Path(__file__).resolve().parents[1] / "src" / "labcairn" / "reports" / "build.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))

    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    assert not [name for name in imported if name.startswith("labcairn.db")]
    assert not [name for name in imported if name.startswith("labcairn.evidence.store")]


def test_the_locator_of_a_citation_is_the_structured_address(task: dict[str, Any]) -> None:
    """A citation is a re-derivable address, not a display string.

    ADR-0004's A1: the locator is the structured fields, and the only
    rendering of it is computed from them.
    """
    document = _build(task)

    locator: SourceLocator = document.footnotes[0].locator
    assert locator == PdfLocator(page=3)
