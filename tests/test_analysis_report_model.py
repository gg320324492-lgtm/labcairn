"""The report document model — the six rules, and what each of them refuses.

LC-P1-11's model is the spine of G4: the renderers draw it, the content
checks verify it, and the report artefact manifest is a statement about it.
This file tests the model itself, and it tests it the way the model is
judged: **every rule needs a test that fails when the rule is broken.**

What that means in practice is a refusal per rule. A report that carries a
conflicted record as a claim is not a report that is merely inaccurate; it
is a document that cannot be built, and the test says so by building it and
watching it fail. The same goes for the other five: a figure without a
caption, a citation with an external identifier, a document that is not
frozen, a document whose bytes are not canonical, and a number that is not
the ledger's.

The helpers below build valid documents and then break exactly one thing,
so that a failure points at a rule rather than at a fixture. The frozen
clock comes from the repository's own ``frozen_now`` fixture, so no test
here reads a wall clock.

Nothing in this file is a placeholder for a later task's test: the content
checks (T04), the renderers (T01) and the report manifest (T02) have their
own tests. What is tested here is the contract they will all be written
against.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from labcairn.analysis.manifest import (
    FileRef,
    RenderEnvironment,
    ReproducibilityManifest,
    canonical_digest,
    canonical_json,
)
from labcairn.core.schema import LabCairnModel
from labcairn.evidence.record import EvidenceRecord
from labcairn.evidence.states import (
    EvidenceCreator,
    EvidenceKind,
    VerificationStatus,
)
from labcairn.reports.model import (
    BlockKind,
    ClaimBlock,
    FigureBlock,
    InterpretationBlock,
    LedgerRecordView,
    LedgerSnapshot,
    NarrativeBlock,
    ProvenanceFootnote,
    ReportBlock,
    ReportClaim,
    ReportDocument,
    ReportFigure,
    ReportSection,
    ReportTable,
    TableBlock,
    UnresolvedBlock,
    UnresolvedRecord,
)
from labcairn.sources.locators import ComputationLocator, PdfLocator, TextLocator

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
#: The bytes of the recipe the figure was made with.
RECIPE_HASH: str = _hash("recipe")
#: The bytes of the table artefact.
TABLE_HASH: str = _hash("table")

#: The number the ledger holds, at a precision a rounding step would lose.
LEDGER_VALUE: float = 4.253


def _numeric_record(
    *,
    record_id: str = "rec-1",
    value: float = LEDGER_VALUE,
    unit: str = "%",
    status: VerificationStatus = VerificationStatus.VERIFIED_BY_RULE,
    anchors: tuple[str, ...] = ("anc-1",),
    source_hash: str | None = SOURCE_HASH,
) -> LedgerRecordView:
    """A numeric record view: a number and its declared unit, and no text."""
    return LedgerRecordView(
        record_id=record_id,
        record_kind=EvidenceKind.NUMERIC,
        value=value,
        unit=unit,
        status=status,
        anchor_ids=anchors,
        source_content_hash=source_hash,
    )


def _text_record(
    *,
    record_id: str = "rec-2",
    text: str = "The material reports a yield of 4.253%.",
    kind: EvidenceKind = EvidenceKind.CLAIM,
    status: VerificationStatus = VerificationStatus.USER_ATTESTED,
    anchors: tuple[str, ...] = ("anc-2",),
    source_hash: str | None = SOURCE_HASH,
) -> LedgerRecordView:
    """A claim record view: text, and no number."""
    return LedgerRecordView(
        record_id=record_id,
        record_kind=kind,
        text=text,
        status=status,
        anchor_ids=anchors,
        source_content_hash=source_hash,
    )


def _footnote(
    *,
    footnote_id: str = "fn-1",
    source_id: str = "src-1",
    locator: Any = None,
    content_hash: str = SOURCE_HASH,
) -> ProvenanceFootnote:
    """A citation: a source, a locator and the bytes it pointed at."""
    return ProvenanceFootnote(
        footnote_id=footnote_id,
        source_id=source_id,
        locator=PdfLocator(page=3) if locator is None else locator,
        content_sha256=content_hash,
    )


def _claim(
    *,
    claim_id: str = "clm-1",
    record: LedgerRecordView | None = None,
    footnote_ids: tuple[str, ...] = ("fn-1",),
) -> ReportClaim:
    """A claim on a record, citing the footnote that shows where it came from."""
    return ReportClaim(
        claim_id=claim_id,
        record=_numeric_record() if record is None else record,
        footnote_ids=footnote_ids,
    )


def _unresolved(
    *,
    record: LedgerRecordView | None = None,
    reason: str = "Two readings of the same cell disagree beyond the declared tolerance.",
) -> UnresolvedRecord:
    """A record carried as what it is: a conflict, with its reason."""
    if record is None:
        record = _numeric_record(record_id="rec-9", status=VerificationStatus.CONFLICTED)
    return UnresolvedRecord(record=record, reason=reason)


def _manifest(*, parameters: dict[str, Any] | None = None) -> ReproducibilityManifest:
    """A valid reproducibility manifest for one figure.

    Built through the manifest's own fields rather than through
    :func:`labcairn.analysis.manifest.build_manifest`, because the builder
    wants a source on disk and a workspace, and none of that is what this
    file is about.
    """
    output: dict[str, Any] = {"mean": LEDGER_VALUE, "n_used": 5}
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
            parameters=parameters
            if parameters is not None
            else {"selection": selection, "column": "yield"},
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


def _figure(
    *,
    figure_id: str = "fig-1",
    caption: str = "Mean yield across the five measured runs.",
    manifest: ReproducibilityManifest | None = None,
) -> ReportFigure:
    """A figure with its caption and the manifest that describes it."""
    return ReportFigure(
        figure_id=figure_id,
        relative_path="outputs/figures/fig-1.svg",
        content_sha256=FIGURE_HASH,
        caption=caption,
        manifest=manifest if manifest is not None else _manifest(),
    )


def _table(*, table_id: str = "tab-1") -> ReportTable:
    """A table artefact, by path and hash."""
    return ReportTable(
        table_id=table_id,
        relative_path="outputs/tables/tab-1.csv",
        content_sha256=TABLE_HASH,
    )


def _section(
    *,
    section_id: str = "sec-1",
    heading: str = "Findings",
    blocks: tuple[ReportBlock, ...] | None = None,
) -> ReportSection:
    """A section, with one claim block unless told otherwise."""
    if blocks is None:
        blocks = (ClaimBlock(claim_id="clm-1"),)
    return ReportSection(section_id=section_id, heading=heading, blocks=blocks)


def _document(
    *,
    as_of: datetime,
    title: str = "A first-pass report",
    sections: tuple[ReportSection, ...] | None = None,
    claims: tuple[ReportClaim, ...] | None = None,
    figures: tuple[ReportFigure, ...] = (),
    tables: tuple[ReportTable, ...] = (),
    footnotes: tuple[ProvenanceFootnote, ...] | None = None,
    unresolved_records: tuple[UnresolvedRecord, ...] = (),
    record_ids: tuple[str, ...] | None = None,
) -> ReportDocument:
    """A valid document, from which a test changes exactly one thing."""
    if claims is None:
        claims = (_claim(),)
    if footnotes is None:
        footnotes = (_footnote(),)
    if sections is None:
        sections = (_section(),)
    if record_ids is None:
        record_ids = tuple(
            sorted(
                {claim.record.record_id for claim in claims}
                | {record.record.record_id for record in unresolved_records}
            )
        )
    return ReportDocument(
        title=title,
        snapshot=LedgerSnapshot(as_of=as_of, record_ids=record_ids),
        sections=sections,
        claims=claims,
        figures=figures,
        tables=tables,
        footnotes=footnotes,
        unresolved_records=unresolved_records,
    )


def _property_names(schema: dict[str, Any]) -> set[str]:
    """Every property name anywhere in a JSON schema, at any depth.

    Walked rather than listed, so that a field added to a model nobody
    remembered would still be seen.
    """
    names: set[str] = set()
    for key, value in schema.items():
        if key == "properties" and isinstance(value, dict):
            names.update(value)
        if isinstance(value, dict):
            names |= _property_names(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    names |= _property_names(item)
    return names


def _marked_as_interpretation(blocks: tuple[ReportBlock, ...]) -> list[str]:
    """The blocks a renderer would put the interpretation marker on.

    This is the rule the model has to make possible: mark the blocks
    whose kind is ``interpretation``, and nothing else. The renderer
    dispatches on the kind, because the kind is the discriminator, and
    the kind and the class have to agree — which is what the assertion
    inside checks.
    """
    marked: list[str] = []
    for block in blocks:
        if block.block_kind is BlockKind.INTERPRETATION:
            assert isinstance(block, InterpretationBlock)
            marked.append(block.text)
    return marked


# ---------------------------------------------------------------------------
# Rule 1 — a claim names its record, and only a statable record may be one
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_a_claim_may_not_rest_on_a_conflicted_record() -> None:
    """A conflict is not a finding.

    ADR-0004's rule is that neither of two disagreeing readings wins by
    recency and the conflict is *displayed*; a document that stated one of
    them as a finding would be choosing a winner the ledger refused to
    choose.
    """
    with pytest.raises(ValidationError, match="conflicted"):
        _claim(record=_numeric_record(status=VerificationStatus.CONFLICTED))


@pytest.mark.unit
def test_a_claim_may_not_rest_on_an_unsupported_record() -> None:
    """A record nothing supports is not a statement."""
    with pytest.raises(ValidationError, match="unsupported"):
        _claim(record=_numeric_record(status=VerificationStatus.UNSUPPORTED))


@pytest.mark.unit
def test_a_claim_may_not_rest_on_a_record_that_was_never_located() -> None:
    """A declaration is not a finding.

    A ``planned`` record states an intention. It has nothing behind it, and
    a report sentence resting on one would say the ledger's intention and
    the report's finding in the same words.
    """
    with pytest.raises(ValidationError, match="planned"):
        _claim(record=_numeric_record(status=VerificationStatus.PLANNED))


@pytest.mark.unit
def test_a_document_that_carries_a_conflicted_record_as_a_claim_is_refused(
    frozen_now: datetime,
) -> None:
    """The document is refused — not merely flagged.

    This is the clause the work order names: a document that turns a
    conflicted record into a report sentence that reads as a finding must
    not exist. The refusal happens where the claim is built, because that
    is the earliest point at which the contradiction is visible, and a
    document that could hold one would be a document nobody could rely on.
    """
    with pytest.raises(ValidationError, match="conflicted"):
        _document(
            as_of=frozen_now,
            claims=(_claim(record=_numeric_record(status=VerificationStatus.CONFLICTED)),),
        )


@pytest.mark.unit
def test_a_conflicted_record_is_carried_as_what_it_is(frozen_now: datetime) -> None:
    """The conflict is disclosed, with its reason, and the report is built.

    Refusing the claim is not the same as dropping the record: ADR-0004
    requires the conflict to be *displayed*, so the document carries it —
    as a disclosure, in its own block kind, so a renderer cannot draw it
    as a finding by accident.
    """
    disclosure = _unresolved()
    document = _document(
        as_of=frozen_now,
        claims=(),
        unresolved_records=(disclosure,),
        sections=(_section(blocks=(UnresolvedBlock(record_id="rec-9"),)),),
        record_ids=("rec-9",),
    )

    assert document.unresolved_records == (disclosure,)
    assert document.claims == ()
    assert "rec-9" in document.canonical_bytes().decode("utf-8")


@pytest.mark.unit
def test_an_unresolved_record_must_say_why_it_is_unresolved() -> None:
    """A disclosure nobody can act on is decoration.

    A conflict with no reason is two records that happen to disagree, and
    the report would be showing the reader a disagreement with no way to
    tell what it was about.
    """
    with pytest.raises(ValidationError):
        _unresolved(reason="   ")


@pytest.mark.unit
def test_a_record_that_may_be_stated_may_not_be_carried_as_a_disclosure() -> None:
    """A verified record is a claim, not a disclosure.

    The two collections are not two spellings of one thing: the first
    states, the second discloses. A record that could be either would be a
    record whose meaning the report had not decided.
    """
    with pytest.raises(ValidationError, match="not an unresolved record"):
        _unresolved(record=_numeric_record(status=VerificationStatus.VERIFIED_BY_RULE))


@pytest.mark.unit
def test_a_record_may_not_be_both_a_finding_and_a_disclosure(frozen_now: datetime) -> None:
    """One record is one statement.

    A document that showed the same record as a result *and* as a
    conflict would be contradicting itself in the space of one page, and no
    reader could tell which statement to believe.
    """
    finding = _numeric_record(record_id="rec-1", status=VerificationStatus.VERIFIED_BY_RULE)
    conflict = _numeric_record(record_id="rec-1", status=VerificationStatus.CONFLICTED)
    with pytest.raises(ValidationError, match="carried more than once"):
        _document(
            as_of=frozen_now,
            claims=(_claim(record=finding),),
            unresolved_records=(_unresolved(record=conflict),),
            sections=(
                _section(
                    blocks=(
                        ClaimBlock(claim_id="clm-1"),
                        UnresolvedBlock(record_id="rec-1"),
                    )
                ),
            ),
            record_ids=("rec-1",),
        )


@pytest.mark.unit
def test_a_record_may_not_back_two_claims(frozen_now: datetime) -> None:
    """A record states one thing.

    A report that states the same record twice says it twice, and the
    second statement is the one no check would notice. A report that wants
    the finding in two places places the same *claim* in two sections.
    """
    record = _numeric_record(record_id="rec-1")
    with pytest.raises(ValidationError, match="back more than one claim"):
        _document(
            as_of=frozen_now,
            claims=(
                _claim(claim_id="clm-1", record=record),
                _claim(claim_id="clm-2", record=record),
            ),
            sections=(
                _section(
                    blocks=(
                        ClaimBlock(claim_id="clm-1"),
                        ClaimBlock(claim_id="clm-2"),
                    )
                ),
            ),
            record_ids=("rec-1",),
        )


@pytest.mark.unit
def test_a_claim_must_be_traceable_to_a_source() -> None:
    """A claim with no anchor is a claim no reader can check.

    ADR-0004's condition is that every claim is traceable to a source, and
    a record with no anchor and no bound hash is traceable to nothing.
    """
    with pytest.raises(ValidationError, match="no anchor"):
        _claim(record=_numeric_record(anchors=()))

    with pytest.raises(ValidationError, match="no source content hash"):
        _claim(record=_numeric_record(source_hash=None))


@pytest.mark.unit
def test_a_claim_must_cite_something() -> None:
    """A statement shown with no locator is a statement with no authority."""
    with pytest.raises(ValidationError, match="cites nothing"):
        _claim(footnote_ids=())


# ---------------------------------------------------------------------------
# Rule 2 — the numbers are the ledger's numbers
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_a_numeric_record_may_not_carry_text() -> None:
    """There is nowhere for a re-worded number to sit.

    This is the rule that makes rule 2 enforceable: if a numeric record
    could carry a sentence, the document would have two things to say
    about one quantity, and the renderer would be free to prefer the
    sentence.
    """
    view = _numeric_record()
    with pytest.raises(ValidationError, match="may not carry text"):
        LedgerRecordView(
            record_id=view.record_id,
            record_kind=view.record_kind,
            text="The yield was 4.25%.",
            value=view.value,
            unit=view.unit,
            status=view.status,
            anchor_ids=view.anchor_ids,
            source_content_hash=view.source_content_hash,
        )


@pytest.mark.unit
def test_a_record_that_is_not_numeric_may_not_carry_a_number() -> None:
    """A number attached to a sentence is a second record."""
    with pytest.raises(ValidationError, match="may not carry 'value'"):
        LedgerRecordView(
            record_id="rec-2",
            record_kind=EvidenceKind.CLAIM,
            text="The material reports a yield.",
            value=4.253,
            status=VerificationStatus.USER_ATTESTED,
        )

    with pytest.raises(ValidationError, match="may not carry 'unit'"):
        LedgerRecordView(
            record_id="rec-2",
            record_kind=EvidenceKind.CLAIM,
            text="The material reports a yield.",
            unit="%",
            status=VerificationStatus.USER_ATTESTED,
        )


@pytest.mark.unit
def test_a_numeric_record_must_declare_its_unit() -> None:
    """The unit is declared, never inferred.

    A dimensionless quantity writes ``dimensionless``; a missing unit is
    how "we did not record one" looks, and that is a different claim.
    """
    with pytest.raises(ValidationError, match="declare its unit"):
        LedgerRecordView(
            record_id="rec-1",
            record_kind=EvidenceKind.NUMERIC,
            value=LEDGER_VALUE,
            status=VerificationStatus.VERIFIED_BY_RULE,
        )


@pytest.mark.unit
def test_a_value_may_not_arrive_as_a_string() -> None:
    """A number that arrives quoted is not a number.

    The project refuses malformed payloads rather than correcting them,
    and a quoted ``"4.253"`` is a payload that would otherwise be
    silently converted.
    """
    with pytest.raises(ValidationError):
        LedgerRecordView(
            record_id="rec-1",
            record_kind=EvidenceKind.NUMERIC,
            value="4.253",  # type: ignore[arg-type]
            unit="%",
            status=VerificationStatus.VERIFIED_BY_RULE,
        )


@pytest.mark.unit
def test_the_number_in_a_claim_is_the_ledger_number(frozen_now: datetime) -> None:
    """The document copies the number; it does not round it.

    ``4.253`` is a number that a rounding step would turn into ``4.25``,
    which is a different claim about the same cell. The test reads the
    number back out of the canonical bytes, because a value that survived
    the model but was reformatted on the way to the document would be a
    report that said 4.25 where the ledger says 4.253.
    """
    document = _document(as_of=frozen_now)

    assert document.claims[0].record.value == LEDGER_VALUE
    payload = json.loads(document.canonical_bytes().decode("utf-8"))
    assert payload["claims"][0]["record"]["value"] == LEDGER_VALUE
    assert "4.253" in document.canonical_bytes().decode("utf-8")


@pytest.mark.unit
def test_every_number_the_report_states_is_a_record_number(frozen_now: datetime) -> None:
    """The document's quantities are copied, not derived.

    Not a spot check on one field: the canonical bytes are walked, every
    number in them is collected, and the collection is compared with the
    numbers the records hold. A document that carried a computed total, a
    percentage derived from two values, or a second copy of a number at a
    different precision would put a number in the document that no record
    holds.

    The scope is the report's *own* quantities. A figure's manifest
    carries the derivation's own output — that number is bound by the
    manifest's hash chain rather than by the ledger, and it belongs to
    the figure rather than to the report's findings — so the document
    built here carries no figure. A number inside the report's own
    narrative prose is the report's own sentence rather than a quantity
    the renderer draws, and ADR-0004's A10 is what covers it.
    """
    document = _document(
        as_of=frozen_now,
        sections=(
            _section(
                blocks=(
                    ClaimBlock(claim_id="clm-1"),
                    NarrativeBlock(text="The material reports a yield."),
                )
            ),
        ),
    )
    payload = json.loads(document.canonical_bytes().decode("utf-8"))

    numbers: set[float] = set()

    def collect(node: Any) -> None:
        if isinstance(node, dict):
            for value in node.values():
                collect(value)
        elif isinstance(node, list):
            for value in node:
                collect(value)
        elif isinstance(node, float):
            numbers.add(node)

    collect(payload)
    assert numbers == {LEDGER_VALUE}


@pytest.mark.unit
def test_a_claim_number_is_the_ledger_record_number_it_came_from(
    frozen_now: datetime,
) -> None:
    """The projection takes the ledger's own value, not a re-typed one.

    The projection is built from a real
    :class:`~labcairn.evidence.record.EvidenceRecord` — the shape a
    builder will use — and the number in the report is the number the
    ledger holds.
    """
    record = EvidenceRecord(
        evidence_id="rec-1",
        task_id="task-1",
        kind=EvidenceKind.NUMERIC,
        text=None,
        value=LEDGER_VALUE,
        unit="%",
        status=VerificationStatus.EXTRACTED,
        anchor_ids=("anc-1",),
        extracted_span="4.253",
        extracted_span_sha256=_hash("span"),
        source_content_hash=SOURCE_HASH,
        created_by=EvidenceCreator.RULE,
        created_by_id="cite.c3",
        created_at=frozen_now,
    )
    view = LedgerRecordView(
        record_id=record.evidence_id,
        record_kind=record.kind,
        value=record.value,
        unit=record.unit,
        status=record.status,
        anchor_ids=record.anchor_ids,
        source_content_hash=record.source_content_hash,
    )

    assert view.value == record.value
    assert view.value == LEDGER_VALUE
    assert view.unit == record.unit
    assert view.status is record.status


# ---------------------------------------------------------------------------
# Rule 3 — a figure carries its caption
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_a_figure_may_not_be_declared_without_a_caption() -> None:
    """The caption is the model's, so it cannot be the renderer's.

    A renderer that has to invent a caption invents a different one for
    every format, and the four exports of one document stop saying the
    same thing.
    """
    with pytest.raises(ValidationError):
        ReportFigure.model_validate(
            {
                "figure_id": "fig-1",
                "relative_path": "outputs/figures/fig-1.svg",
                "content_sha256": FIGURE_HASH,
                "manifest": json.loads(_manifest().model_dump_json()),
            }
        )


@pytest.mark.unit
def test_a_figure_with_a_blank_caption_is_refused() -> None:
    """A blank caption is not a caption."""
    with pytest.raises(ValidationError):
        _figure(caption="   ")


@pytest.mark.unit
def test_a_figure_may_not_be_declared_without_its_manifest() -> None:
    """The manifest is part of the figure, not a note about it.

    A figure carried without the derivation that produced it is a picture
    the reader is asked to trust, and the report is exactly the document
    that should not ask for that.
    """
    with pytest.raises(ValidationError):
        ReportFigure.model_validate(
            {
                "figure_id": "fig-1",
                "relative_path": "outputs/figures/fig-1.svg",
                "content_sha256": FIGURE_HASH,
                "caption": "Mean yield across the five measured runs.",
            }
        )


@pytest.mark.unit
def test_a_table_may_not_be_declared_without_its_path() -> None:
    """A table is a fact about a file, and the file is named."""
    with pytest.raises(ValidationError):
        ReportTable.model_validate({"table_id": "tab-1", "content_sha256": TABLE_HASH})


@pytest.mark.unit
def test_a_figure_may_not_be_declared_without_its_path() -> None:
    """And so is a figure.

    The path is workspace-relative and canonical, so a bundle of reports
    resolves on the reader's machine rather than pointing at the machine
    that produced it.
    """
    with pytest.raises(ValidationError):
        ReportFigure.model_validate(
            {
                "figure_id": "fig-1",
                "content_sha256": FIGURE_HASH,
                "caption": "Mean yield across the five measured runs.",
                "manifest": json.loads(_manifest().model_dump_json()),
            }
        )


@pytest.mark.unit
def test_the_caption_is_in_the_canonical_bytes(frozen_now: datetime) -> None:
    """The caption is part of the document, not of the rendering.

    If the caption were assembled by the renderer, it would not be in the
    bytes the document is hashed over, and two exports could carry
    different wording under the same document hash.
    """
    document = _document(as_of=frozen_now, figures=(_figure(),))

    assert "Mean yield across the five measured runs." in (
        document.canonical_bytes().decode("utf-8")
    )


# ---------------------------------------------------------------------------
# Rule 4 — a citation is a locator, and never an external identifier
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_a_citation_carries_the_source_the_locator_and_the_hash() -> None:
    """Three things, and no more.

    A citation that named a source, a locator and a content hash is
    checkable: a reader can go to the material, and the hash says whether
    the material is still the material the report was built from.
    """
    footnote = _footnote()

    assert set(ProvenanceFootnote.model_fields) - {"schema_version"} == {
        "footnote_id",
        "source_id",
        "locator",
        "content_sha256",
    }
    assert isinstance(footnote.locator, PdfLocator)


@pytest.mark.unit
def test_a_citation_may_not_carry_an_external_identifier() -> None:
    """The owner's decision of 2026-10-20, enforced structurally.

    An identifier in the source model is a slot ingestion never fills and
    nothing in the tree resolves, so an identifier printed as a citation
    would be the material's claim and not the report's. The model has no
    field for one, and ``extra="forbid"`` means a payload carrying one is
    refused rather than quietly dropped.
    """
    with pytest.raises(ValidationError):
        ProvenanceFootnote.model_validate(
            {
                "footnote_id": "fn-1",
                "source_id": "src-1",
                "locator": {"locator_kind": "pdf", "page": 3},
                "content_sha256": SOURCE_HASH,
                "doi": "10.1234/fabricated",
            }
        )


@pytest.mark.unit
def test_no_part_of_the_report_carries_an_external_identifier() -> None:
    """The rule holds for the whole document, not just for the citation.

    The document reaches the reproducibility manifest, the locator union
    and the record view, so a field added anywhere inside that graph would
    be a field the report could print. The schema is walked rather than
    listed, so a model nobody remembered is still covered.
    """
    names = _property_names(ReportDocument.model_json_schema())

    forbidden = {"identifier", "identifiers", "doi", "arxiv", "isbn"}
    assert not (names & forbidden)
    assert not [name for name in names if "identifier" in name.lower()]


@pytest.mark.unit
def test_a_citation_may_not_name_other_bytes_than_the_record_was_read_from(
    frozen_now: datetime,
) -> None:
    """A citation to bytes the record was not read from is a citation to
    something else.

    The claim rests on a record read from certain bytes; a citation that
    points at different bytes is a claim about a different material, and
    the report would be showing the reader a source that does not say what
    the claim says.
    """
    with pytest.raises(ValidationError, match="names other bytes"):
        _document(
            as_of=frozen_now,
            footnotes=(_footnote(content_hash=_hash("other-bytes")),),
        )


# ---------------------------------------------------------------------------
# Rule 5 — a frozen view at one moment, naming that moment
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_the_document_is_frozen(frozen_now: datetime) -> None:
    """A report that could be edited in place could not be hashed.

    The document's bytes are what a receipt's hash is taken over, and a
    document whose bytes could change under a reader's feet would make
    that hash a claim about nothing.
    """
    document = _document(as_of=frozen_now)

    with pytest.raises(ValidationError):
        document.title = "A different report"


@pytest.mark.unit
def test_the_document_names_the_moment_it_is_a_view_of(frozen_now: datetime) -> None:
    """The moment is named, and it is part of the document's content.

    Two documents built from the same records at different moments are
    different documents, and the bytes say so. A report that did not name
    its moment would read as current the way the ledger is.
    """
    document = _document(as_of=frozen_now)
    later = _document(as_of=datetime(2026, 6, 1, tzinfo=UTC))

    assert document.snapshot.as_of == frozen_now
    assert document.canonical_bytes() != later.canonical_bytes()
    assert "2026-01-01T00:00:00Z" in document.canonical_bytes().decode("utf-8")


@pytest.mark.unit
def test_the_snapshot_must_name_every_record_the_report_carries(
    frozen_now: datetime,
) -> None:
    """The snapshot is the report's statement of what it is a view of.

    A record the snapshot does not name is a record the reader cannot
    check the view against.
    """
    with pytest.raises(ValidationError, match="does not name"):
        _document(as_of=frozen_now, record_ids=("rec-other",))


@pytest.mark.unit
def test_the_snapshot_may_not_name_a_record_the_report_does_not_carry(
    frozen_now: datetime,
) -> None:
    """And the extent of the view has to be answerable.

    A snapshot naming a record the report does not show makes "which
    records is this a view of" answerable two ways.
    """
    with pytest.raises(ValidationError, match="does not carry"):
        _document(as_of=frozen_now, record_ids=("rec-1", "rec-99"))


@pytest.mark.unit
def test_the_snapshot_record_ids_must_be_sorted() -> None:
    """Two views of the same records have the same extent however they
    were gathered."""
    with pytest.raises(ValidationError, match="not in sorted order"):
        LedgerSnapshot(
            as_of=datetime(2026, 1, 1, tzinfo=UTC),
            record_ids=("rec-2", "rec-1"),
        )


@pytest.mark.unit
def test_the_snapshot_may_not_name_a_record_twice() -> None:
    """One record named twice is one record."""
    with pytest.raises(ValidationError, match="names a record twice"):
        LedgerSnapshot(
            as_of=datetime(2026, 1, 1, tzinfo=UTC),
            record_ids=("rec-1", "rec-1"),
        )


@pytest.mark.unit
def test_the_document_is_versioned_and_refuses_a_version_it_cannot_read(
    frozen_now: datetime,
) -> None:
    """A payload from a version this build does not know is refused, not
    guessed at.

    A reader that does not know what field 4 means cannot drop it, and
    quietly dropping it is how provenance gets lost without anyone
    noticing.
    """
    document = _document(as_of=frozen_now)
    payload = json.loads(document.canonical_bytes().decode("utf-8"))

    assert payload["schema_version"] == 1

    payload["schema_version"] = 999
    with pytest.raises(ValidationError, match="schema_version"):
        ReportDocument.model_validate(payload)


# ---------------------------------------------------------------------------
# Rule 6 — canonical bytes, one spelling
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_two_reports_of_the_same_content_have_the_same_canonical_bytes(
    frozen_now: datetime,
) -> None:
    """The bytes are a function of the content, and of nothing else.

    The two documents are built from the same facts, and the manifest's
    parameters are assembled in a different order in each — a dictionary's
    insertion order is a fact about how the builder ran, not about what
    the report says, and it must not reach the bytes.
    """
    first = _document(as_of=frozen_now, figures=(_figure(manifest=_manifest()),))
    second = _document(
        as_of=frozen_now,
        figures=(
            _figure(
                manifest=_manifest(
                    parameters={
                        "column": "yield",
                        "selection": {
                            "source_id": "src-1",
                            "content_sha256": SOURCE_HASH,
                            "columns": ["yield"],
                            "rows": {"kind": "range", "start": 1, "end": 5},
                            "missing": "exclude",
                        },
                    }
                )
            ),
        ),
    )

    assert first.canonical_bytes() == second.canonical_bytes()


@pytest.mark.unit
def test_the_canonical_bytes_are_the_projects_canonical_json(
    frozen_now: datetime,
) -> None:
    """One convention, not two.

    The tree has two canonical-JSON helpers:
    :meth:`labcairn.core.schema.LabCairnModel.json_canonical` and
    :func:`labcairn.analysis.manifest.canonical_json`. The document uses
    the first, and the second is compared with it byte for byte — because
    if they ever disagree, a digest computed by one would not match a
    digest computed by the other, and the report's hash would depend on
    which helper the caller happened to reach for.
    """
    document = _document(as_of=frozen_now, figures=(_figure(),))

    assert document.json_canonical() == canonical_json(document.model_dump(mode="json"))
    assert document.canonical_bytes() == document.json_canonical().encode("utf-8")


@pytest.mark.unit
def test_the_digest_of_the_document_is_the_digest_of_its_canonical_json(
    frozen_now: datetime,
) -> None:
    """The same agreement, one level up: over the bytes.

    ``canonical_digest`` is the ledger's own digest algorithm over a
    payload's canonical JSON. The document's bytes are that payload's
    canonical JSON, so a receipt written with one and a digest computed
    with the other describe the same document.
    """
    document = _document(as_of=frozen_now)

    assert (
        canonical_digest(document.model_dump(mode="json"))
        == hashlib.sha256(document.canonical_bytes()).hexdigest()
    )


@pytest.mark.unit
def test_the_canonical_bytes_are_valid_json_with_sorted_keys_and_no_whitespace(
    frozen_now: datetime,
) -> None:
    """The bytes are JSON, and they are the *canonical* JSON.

    Sorted keys, no incidental whitespace: a digest over them is
    comparable between two runs on two platforms, which is the whole
    reason the form is fixed.
    """
    raw = _document(as_of=frozen_now, figures=(_figure(),)).canonical_bytes()

    parsed = json.loads(raw)
    assert list(parsed) == sorted(parsed)
    assert b", " not in raw
    assert b": " not in raw


@pytest.mark.unit
def test_the_canonical_bytes_do_not_escape_non_ascii() -> None:
    """A caption in the author's own characters survives the hash.

    Escaping would still be JSON, and still canonical under a different
    convention — and the manifest that hashes the bytes would not be the
    manifest this project hashes. The caption carries a character outside
    ASCII on purpose: a caption of plain ASCII would survive the
    escaping and observe nothing.
    """
    caption = "Rendement moyen : 4,253 % (µg) — série 3"
    document = _document(
        as_of=datetime(2026, 1, 1, tzinfo=UTC),
        figures=(_figure(caption=caption),),
    )
    raw = document.canonical_bytes()

    assert b"\\u" not in raw
    assert "µg".encode() in raw
    assert caption in raw.decode("utf-8")


@pytest.mark.unit
def test_the_document_round_trips_through_its_canonical_bytes(
    frozen_now: datetime,
) -> None:
    """The bytes are the document, and reading them back gives the
    document."""
    document = _document(as_of=frozen_now, figures=(_figure(),))

    assert ReportDocument.model_validate_json(document.canonical_bytes()) == document


# ---------------------------------------------------------------------------
# The report's own interpretation: a kind, so the marker has a subject
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_a_renderer_can_tell_an_interpretation_from_a_plain_narrative(
    frozen_now: datetime,
) -> None:
    """The marker has a subject.

    ADR-0004's condition is that an interpretation is never
    machine-verified, because C4 returned ``not_checked``. The renderers
    mark it — exactly as the figure's renderer marks the figure's
    interpretation — and the model says *which* blocks are
    interpretations, so the marker has something to attach to and no
    renderer has to work it out for itself.

    A plain narrative is left alone, and the test says so by putting one
    beside an interpretation and checking that exactly one of them is
    marked.
    """
    document = _document(
        as_of=frozen_now,
        sections=(
            _section(
                blocks=(
                    ClaimBlock(claim_id="clm-1"),
                    NarrativeBlock(text="The dataset contained 120 rows."),
                    InterpretationBlock(text="The catalyst therefore improves yield."),
                )
            ),
        ),
    )
    blocks = document.sections[0].blocks

    assert [block.block_kind for block in blocks] == [
        BlockKind.CLAIM,
        BlockKind.NARRATIVE,
        BlockKind.INTERPRETATION,
    ]
    assert _marked_as_interpretation(blocks) == ["The catalyst therefore improves yield."]


@pytest.mark.unit
def test_an_interpretation_is_not_a_narrative() -> None:
    """The two kinds are separate, so a renderer cannot catch both by
    accident.

    A renderer that dispatches on the class rather than on the kind must
    mark the interpretation and not the narrative, and that is only true
    while the two classes are unrelated.
    """
    assert not issubclass(InterpretationBlock, NarrativeBlock)
    assert not issubclass(NarrativeBlock, InterpretationBlock)
    assert (
        InterpretationBlock(text="An inference.").block_kind.value
        != NarrativeBlock(text="A description.").block_kind.value
    )


@pytest.mark.unit
def test_the_interpretation_survives_the_canonical_bytes(frozen_now: datetime) -> None:
    """The distinction is in the document, not only in the model.

    Every export reads the document back, so a renderer has to find the
    same distinction it found when the document was built. A kind that
    was dropped on the way to the bytes would leave every export marking
    every block.
    """
    document = _document(
        as_of=frozen_now,
        sections=(
            _section(
                blocks=(
                    ClaimBlock(claim_id="clm-1"),
                    NarrativeBlock(text="The dataset contained 120 rows."),
                    InterpretationBlock(text="The catalyst therefore improves yield."),
                )
            ),
        ),
    )
    payload = json.loads(document.canonical_bytes().decode("utf-8"))

    kinds = [block["block_kind"] for block in payload["sections"][0]["blocks"]]
    assert kinds == ["claim", "narrative", "interpretation"]


@pytest.mark.unit
def test_a_claim_resting_on_a_claim_record_is_an_interpretation() -> None:
    """ADR-0004's marker applies to the records as well.

    Every ``claim`` or ``result`` record rendered into a report displays
    an explicit "interpretation not machine-verified" marker, because C4
    returned ``not_checked``. A numeric record is not an interpretation:
    it is a quantity a rule confirmed or a person attested, and the number
    itself is the record.
    """
    claim_record = _text_record(record_id="rec-2", kind=EvidenceKind.CLAIM)
    result_record = _text_record(record_id="rec-3", kind=EvidenceKind.RESULT)
    number = _numeric_record()

    assert claim_record.is_interpretation
    assert result_record.is_interpretation
    assert not number.is_interpretation


# ---------------------------------------------------------------------------
# One import path, and the cycle it has to survive
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_the_report_document_has_one_import_path() -> None:
    """One spelling of where the model lives.

    The rest of G4 imports the model from the package, and this is the
    test that says so. The two spellings have to be the same object, or
    there would be two models and the checks would run against one of
    them.
    """
    from labcairn.reports import ReportDocument as ExportedReportDocument
    from labcairn.reports.model import ReportDocument as DefinedReportDocument

    assert ExportedReportDocument is DefinedReportDocument


@pytest.mark.integration
def test_the_export_does_not_depend_on_who_was_imported_first() -> None:
    """A cycle is only visible in one order, so the orders are the test.

    The model imports :mod:`labcairn.analysis.manifest`, and that module
    imports this package. An eager export would make the package import a
    module that is — in the ``analysis`` first order — already half
    loaded, and the import would fail with a partly-initialised-module
    error that no reader of the code would predict. The export is
    deferred, and this is what keeps it deferred.
    """
    orders = (
        "import labcairn.analysis.manifest; import labcairn.reports as r; assert r.ReportDocument",
        "import labcairn.analysis.service; import labcairn.reports as r; assert r.ReportDocument",
        "from labcairn.reports import ReportDocument; assert ReportDocument",
    )
    for code in orders:
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        assert result.returncode == 0, f"{code!r} failed:\n{result.stderr}"


# ---------------------------------------------------------------------------
# The document's own consistency: references, placement, uniqueness
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_a_block_that_places_a_claim_the_report_does_not_carry_is_refused() -> None:
    """A block that points at nothing is a hole in the document."""
    with pytest.raises(ValidationError, match="places the claim"):
        _document(
            as_of=datetime(2026, 1, 1, tzinfo=UTC),
            sections=(_section(blocks=(ClaimBlock(claim_id="clm-absent"),)),),
        )


@pytest.mark.unit
def test_a_block_that_places_a_figure_the_report_does_not_carry_is_refused() -> None:
    """The same, for the figures."""
    with pytest.raises(ValidationError, match="places the figure"):
        _document(
            as_of=datetime(2026, 1, 1, tzinfo=UTC),
            sections=(_section(blocks=(FigureBlock(figure_id="fig-absent"),)),),
        )


@pytest.mark.unit
def test_a_block_that_places_a_table_the_report_does_not_carry_is_refused() -> None:
    """The same, for the tables."""
    with pytest.raises(ValidationError, match="places the table"):
        _document(
            as_of=datetime(2026, 1, 1, tzinfo=UTC),
            sections=(_section(blocks=(TableBlock(table_id="tab-absent"),)),),
        )


@pytest.mark.unit
def test_a_block_that_places_a_record_the_report_does_not_disclose_is_refused() -> None:
    """And for the disclosures."""
    with pytest.raises(ValidationError, match="places the record"):
        _document(
            as_of=datetime(2026, 1, 1, tzinfo=UTC),
            sections=(_section(blocks=(UnresolvedBlock(record_id="rec-absent"),)),),
        )


@pytest.mark.unit
def test_a_claim_that_cites_a_footnote_the_report_does_not_carry_is_refused() -> None:
    """A citation to a citation that is not there."""
    with pytest.raises(ValidationError, match="cites the footnote"):
        _document(
            as_of=datetime(2026, 1, 1, tzinfo=UTC),
            claims=(_claim(footnote_ids=("fn-absent",)),),
        )


@pytest.mark.unit
def test_a_finding_must_be_placed_in_a_section() -> None:
    """A finding the report does not show is a finding nobody reads.

    The checks that verify a report against the ledger verify the claims
    that are in it; a claim that sits in the model and in no section would
    be verified and never printed.
    """
    with pytest.raises(ValidationError, match="in no section"):
        _document(
            as_of=datetime(2026, 1, 1, tzinfo=UTC),
            sections=(_section(blocks=(NarrativeBlock(text="Nothing found."),)),),
        )


@pytest.mark.unit
def test_a_disclosure_must_be_placed_in_a_section() -> None:
    """A conflict nobody is shown is a conflict the report has hidden."""
    with pytest.raises(ValidationError, match="placed in no section"):
        _document(
            as_of=datetime(2026, 1, 1, tzinfo=UTC),
            claims=(),
            unresolved_records=(_unresolved(),),
            sections=(_section(blocks=(NarrativeBlock(text="Nothing found."),)),),
            record_ids=("rec-9",),
        )


@pytest.mark.unit
def test_the_report_may_not_name_the_same_thing_twice() -> None:
    """Two rows for one id make 'which one' answerable two ways."""
    with pytest.raises(ValidationError, match="names the same claim twice"):
        _document(
            as_of=datetime(2026, 1, 1, tzinfo=UTC),
            claims=(_claim(), _claim()),
            sections=(_section(blocks=(ClaimBlock(claim_id="clm-1"),)),),
        )

    with pytest.raises(ValidationError, match="names the same figure twice"):
        _document(
            as_of=datetime(2026, 1, 1, tzinfo=UTC),
            figures=(_figure(), _figure()),
        )

    with pytest.raises(ValidationError, match="names the same table twice"):
        _document(
            as_of=datetime(2026, 1, 1, tzinfo=UTC),
            tables=(_table(), _table()),
        )

    with pytest.raises(ValidationError, match="names the same footnote twice"):
        _document(
            as_of=datetime(2026, 1, 1, tzinfo=UTC),
            footnotes=(_footnote(), _footnote()),
        )

    with pytest.raises(ValidationError, match="names the same section twice"):
        _document(
            as_of=datetime(2026, 1, 1, tzinfo=UTC),
            sections=(_section(), _section()),
        )


@pytest.mark.unit
def test_a_report_may_not_have_no_section() -> None:
    """There has to be something for a renderer to draw.

    The document carries no claim either, so that this refusal is the only
    one that can fire: a report with a claim and no section would be
    refused anyway, for a different reason, and the rule would go
    unobserved.
    """
    with pytest.raises(ValidationError, match="no section"):
        _document(
            as_of=datetime(2026, 1, 1, tzinfo=UTC),
            sections=(),
            claims=(),
        )


@pytest.mark.unit
def test_a_section_may_not_have_no_block() -> None:
    """A heading with nothing under it is a heading the reader cannot do
    anything with."""
    with pytest.raises(ValidationError):
        ReportSection(section_id="sec-1", heading="Findings", blocks=())


@pytest.mark.unit
def test_the_block_kinds_are_a_closed_set() -> None:
    """A block that could be several things at once would be drawn several
    ways."""
    assert {kind.value for kind in BlockKind} == {
        "narrative",
        "interpretation",
        "claim",
        "figure",
        "table",
        "unresolved",
    }


@pytest.mark.unit
def test_a_locator_is_a_structured_address_not_a_rendered_one() -> None:
    """ADR-0004 A1: a locator is re-derivable, not a display string.

    The citation carries the address itself, so a check resolves it
    against the material rather than matching a string.
    """
    footnote = _footnote(locator=TextLocator(line=42, line_end=44))

    assert isinstance(footnote.locator, TextLocator)
    assert footnote.locator.line == 42
    assert footnote.locator.line_end == 44


@pytest.mark.unit
def test_the_document_is_a_labcairn_model() -> None:
    """The base every persisted contract uses.

    ``extra="forbid"`` is the setting that matters here: a payload
    carrying a field this build does not know is rejected rather than
    ignored, because an unrecognised key is either a newer writer or a
    typo and both deserve to be loud.
    """
    assert issubclass(ReportDocument, LabCairnModel)
    assert ReportDocument.model_config["frozen"] is True
    assert ReportDocument.model_config["extra"] == "forbid"

    with pytest.raises(ValidationError):
        ReportDocument.model_validate(
            {
                "title": "x",
                "snapshot": {"as_of": "2026-01-01T00:00:00Z", "record_ids": []},
                "sections": [],
                "unknown_field": 1,
            }
        )
