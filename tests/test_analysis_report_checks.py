"""The content checks: what each one refuses, and what it lets through.

LC-P1-11's acceptance clause says *"numeric values agree with ledger,
figures/captions intact, links resolve"*, and this file is what makes those
three sentences mechanical. It is written the way the checks are judged:
**a check that cannot fail is not a check**, so every rule here has a case
that the rule refuses and a case that the rule lets through. The positive
control is not optional — a gate that refuses everything would satisfy every
refusal test below and tell nobody anything.

The refusals are the point. A report that says 4.25 where the ledger says 4.5
is not a report that is slightly wrong; it is a document that must not be
written, and the test says so by building it and watching the gate refuse
it.

Two kinds of case earn their place here. The first is the **near miss**: a
check that compares the *rounded* number, a link check that compares the
locator's text, a figure check that believes the model's own hash, a claim
check that reads the model's copy of the record. Each of those looks like a
check and is not one, and each has a test below that fails when the check is
broken that way. The second is the case the model already refuses — a figure
without a caption, a snapshot that disagrees with the records the report
carries — where the document is built *without* the model's validators, so
that the **check** is what refuses and the model is not what makes the test
pass.

Every test drives the whole gate, :func:`~labcairn.reports.checks.check_report`
rather than one check in isolation, so that removing any check from the gate
breaks the test that says that check refuses something.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import inspect
import os
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text as sql_text
from sqlalchemy.engine import Connection

from labcairn.analysis.manifest import (
    FileRef,
    RenderEnvironment,
    ReproducibilityManifest,
    canonical_digest,
)
from labcairn.db.migrations import upgrade_to_head
from labcairn.db.session import create_db_engine
from labcairn.evidence.checks.c3 import C3_CHECKER_ID
from labcairn.evidence.index import LabCairnIndex
from labcairn.evidence.record import EvidenceRecord, VerificationRecord
from labcairn.evidence.states import (
    CheckKind,
    CheckOutcome,
    EvidenceCreator,
    EvidenceKind,
    VerificationStatus,
)
from labcairn.evidence.store import advance, append_record, append_verification
from labcairn.material.addressing import render_locator_key
from labcairn.reports.checks import (
    LedgerReader,
    ReportRefusedError,
    check_claims_and_disclosures_rest_on_records_the_ledger_holds,
    check_figures_and_tables_are_the_artefacts_on_disk,
    check_links_resolve,
    check_numbers_agree_with_the_ledger,
    check_report,
    check_the_snapshot_names_the_records_the_report_carries,
    ledger_reader,
)
from labcairn.reports.model import (
    ClaimBlock,
    FigureBlock,
    LedgerRecordView,
    LedgerSnapshot,
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
from labcairn.security.approval import content_hash
from labcairn.sources.locators import ComputationLocator, PdfLocator

# ---------------------------------------------------------------------------
# The material the report is checked against
# ---------------------------------------------------------------------------

NOW = dt.datetime(2026, 10, 18, tzinfo=dt.UTC)

#: The bytes the material had when it was read.
SOURCE_HASH = "a" * 64

#: The number the ledger holds, at a precision a rounding step would lose.
LEDGER_VALUE = 4.253
#: What a report that rounded the ledger's number would state.
ROUNDED_VALUE = 4.25

#: The text at the address the citation points at.
PAGE_TEXT = "The yield across the five runs was 4.253%."
#: The words the ledger holds for the claim record.
CLAIM_TEXT = "The material reports a yield of 4.253%."

#: The figure's bytes on disk.
FIGURE_BYTES = b"<svg xmlns='http://www.w3.org/2000/svg'><rect width='10' height='10'/></svg>"

#: The figure's path, workspace-relative.
FIGURE_PATH = "outputs/figures/fig-1.svg"

#: The table's bytes on disk.
TABLE_BYTES = b"run,yield\n1,4.253\n"

#: The table's path, workspace-relative.
TABLE_PATH = "outputs/tables/tab-1.csv"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class World:
    """The material a report is checked against: a ledger, an index and a disk."""

    root: Path
    connection: Connection
    index: LabCairnIndex
    ledger: LedgerReader
    figure_hash: str
    table_hash: str


def _insert_source(connection: Connection, source_id: str, sha: str) -> None:
    connection.execute(
        sql_text(
            "INSERT INTO sources (source_id, owner_id, kind, display_name, relative_path,"
            " content_sha256, size_bytes, readability, readability_disclosure, identifiers,"
            " ingested_at, schema_version)"
            " VALUES (:sid,'local-user','pdf',:name,:rel,:sha,1,'readable',NULL,'[]',:now,1)"
        ),
        {
            "sid": source_id,
            "name": f"{source_id}.pdf",
            "rel": f"{source_id}.pdf",
            "sha": sha,
            "now": NOW,
        },
    )


def _insert_text(connection: Connection, sha: str, locator: Any, body: str) -> None:
    connection.execute(
        sql_text(
            "INSERT INTO source_texts (source_content_sha256, extraction_version,"
            " locator_kind, locator_key, page, row_number, column_name, text, text_sha256,"
            " created_at)"
            " VALUES (:sha,'v1',:kind,:key,:page,NULL,NULL,:body,:tsha,:now)"
        ),
        {
            "sha": sha,
            "kind": locator.locator_kind.value,
            "key": render_locator_key(locator),
            "page": getattr(locator, "page", None),
            "body": body,
            "tsha": _sha(body),
            "now": NOW,
        },
    )


def _insert_anchor(
    connection: Connection, anchor_id: str, source_id: str, locator: Any, bound: str
) -> None:
    connection.execute(
        sql_text(
            "INSERT INTO source_anchors (anchor_id, source_id, kind, locator_key,"
            " bound_source_sha256, excerpt_sha256, created_at)"
            " VALUES (:aid,:sid,'quotation',:key,:bound,NULL,:now)"
        ),
        {
            "aid": anchor_id,
            "sid": source_id,
            "key": render_locator_key(locator),
            "bound": bound,
            "now": NOW,
        },
    )


def _numeric_ledger_record(
    *, record_id: str = "rec-1", value: float = LEDGER_VALUE, unit: str = "%"
) -> EvidenceRecord:
    """A numeric record in the ledger: a quantity, its unit, and where it was read.

    The extracted span is the number as it was written, so two records on the
    same cell with different values carry different spans — the ledger's own
    uniqueness rule on ``(task_id, extracted_span_sha256)`` refuses two
    records that claim the same span, and a sibling conflict needs two.
    """
    span = str(value)
    return EvidenceRecord(
        evidence_id=record_id,
        task_id="task-1",
        kind=EvidenceKind.NUMERIC,
        text=None,
        value=value,
        unit=unit,
        anchor_ids=("anc-1",),
        extracted_span=span,
        extracted_span_sha256=_sha(span),
        status=VerificationStatus.EXTRACTED,
        created_by=EvidenceCreator.RULE,
        created_by_id="seed",
        source_content_hash=SOURCE_HASH,
        created_at=NOW,
    )


def _claim_ledger_record(*, record_id: str = "rec-2", text: str = CLAIM_TEXT) -> EvidenceRecord:
    """A claim record in the ledger: a statement, and where it was read."""
    return EvidenceRecord(
        evidence_id=record_id,
        task_id="task-1",
        kind=EvidenceKind.CLAIM,
        text=text,
        anchor_ids=("anc-1",),
        extracted_span=text,
        extracted_span_sha256=_sha(text),
        status=VerificationStatus.EXTRACTED,
        created_by=EvidenceCreator.RULE,
        created_by_id="seed",
        source_content_hash=SOURCE_HASH,
        created_at=NOW,
    )


@pytest.fixture()
def world(tmp_path: Path) -> Iterator[World]:
    """A ledger, an index and a workspace, with one page of material behind them.

    The material is real: a source row, the text of the page it holds, an
    anchor at that page, and two records read from it. A stub would make
    every assertion here a statement about the stub, and these checks are
    about what the ledger holds.
    """
    root = tmp_path / "workspace"
    root.mkdir()
    figure_file = root / FIGURE_PATH
    figure_file.parent.mkdir(parents=True)
    figure_file.write_bytes(FIGURE_BYTES)
    table_file = root / TABLE_PATH
    table_file.parent.mkdir(parents=True)
    table_file.write_bytes(TABLE_BYTES)

    database = tmp_path / "checks.db"
    upgrade_to_head(database)
    engine = create_db_engine(database)
    connection = engine.connect()
    _insert_source(connection, "src-1", SOURCE_HASH)
    _insert_text(connection, SOURCE_HASH, PdfLocator(page=2), PAGE_TEXT)
    _insert_anchor(connection, "anc-1", "src-1", PdfLocator(page=2), SOURCE_HASH)
    append_record(connection, _numeric_ledger_record())
    append_record(connection, _claim_ledger_record())
    connection.commit()

    yield World(
        root=root,
        connection=connection,
        index=LabCairnIndex(connection),
        ledger=ledger_reader(connection),
        figure_hash=content_hash(figure_file),
        table_hash=content_hash(table_file),
    )
    engine.dispose()


# ---------------------------------------------------------------------------
# The report, and the pieces it is made of
# ---------------------------------------------------------------------------


def _numeric_view(
    *,
    record_id: str = "rec-1",
    value: float = LEDGER_VALUE,
    unit: str = "%",
    status: VerificationStatus = VerificationStatus.EXTRACTED,
    anchors: tuple[str, ...] = ("anc-1",),
) -> LedgerRecordView:
    """The model's copy of the numeric record: a number, its unit, and no text."""
    return LedgerRecordView(
        record_id=record_id,
        record_kind=EvidenceKind.NUMERIC,
        value=value,
        unit=unit,
        status=status,
        anchor_ids=anchors,
        source_content_hash=SOURCE_HASH,
    )


def _claim_view(*, record_id: str = "rec-2", text: str = CLAIM_TEXT) -> LedgerRecordView:
    """The model's copy of the claim record: the ledger's words."""
    return LedgerRecordView(
        record_id=record_id,
        record_kind=EvidenceKind.CLAIM,
        text=text,
        status=VerificationStatus.EXTRACTED,
        anchor_ids=("anc-1",),
        source_content_hash=SOURCE_HASH,
    )


def _unresolved_view(
    *,
    record_id: str = "rec-9",
    status: VerificationStatus = VerificationStatus.CONFLICTED,
    value: float = LEDGER_VALUE,
) -> LedgerRecordView:
    """The model's copy of a record the report discloses rather than states."""
    return LedgerRecordView(
        record_id=record_id,
        record_kind=EvidenceKind.NUMERIC,
        value=value,
        unit="%",
        status=status,
        anchor_ids=("anc-1",),
        source_content_hash=SOURCE_HASH,
    )


def _unresolved_claim_view(
    *,
    record_id: str = "rec-2",
    status: VerificationStatus = VerificationStatus.UNSUPPORTED,
    text: str = CLAIM_TEXT,
) -> LedgerRecordView:
    """The model's copy of an unresolved *claim* record: words and no number."""
    return LedgerRecordView(
        record_id=record_id,
        record_kind=EvidenceKind.CLAIM,
        text=text,
        status=status,
        anchor_ids=("anc-1",),
        source_content_hash=SOURCE_HASH,
    )


def _unresolved(
    *,
    record_id: str = "rec-9",
    status: VerificationStatus = VerificationStatus.CONFLICTED,
    value: float = LEDGER_VALUE,
    view: LedgerRecordView | None = None,
) -> UnresolvedRecord:
    """An unresolved record, disclosed with the report's own reason for it.

    The reason is prose the ledger does not hold, and nothing compares the
    two: the ledger records *that* a record could not be resolved, and the
    report says *why*. The record's own **text** is the other matter
    entirely — that is the ledger's words, and it is compared.
    """
    return UnresolvedRecord(
        record=(
            view
            if view is not None
            else _unresolved_view(record_id=record_id, status=status, value=value)
        ),
        reason="Two readings of the same cell disagree beyond the declared tolerance.",
    )


def _conflicted_in_the_ledger(world: World, record_id: str = "rec-1") -> None:
    """Put a record into the ledger's conflicted state, the way the ledger does it.

    Two records on the same cell whose C3 verdicts disagree, and then the
    transition the state machine allows: ADR-0004's A5 says neither reading
    wins by recency, and the conflict is displayed instead.
    """
    append_verification(
        world.connection,
        record_id,
        VerificationRecord(
            check=CheckKind.C3,
            checker_id=C3_CHECKER_ID,
            outcome=CheckOutcome.PASS,
            detail="the cell holds 4.253",
            checked_at=NOW,
        ),
    )
    append_record(world.connection, _numeric_ledger_record(record_id="rec-3", value=4.5))
    append_verification(
        world.connection,
        "rec-3",
        VerificationRecord(
            check=CheckKind.C3,
            checker_id=C3_CHECKER_ID,
            outcome=CheckOutcome.FAIL,
            detail="the cell holds 4.5",
            checked_at=NOW,
        ),
    )
    world.connection.commit()
    advance(
        world.connection,
        record_id,
        VerificationStatus.CONFLICTED,
        index=world.index,
        checked_at=NOW,
    )
    world.connection.commit()


def _unsupported_in_the_ledger(world: World, record_id: str = "rec-1") -> None:
    """Put a record into the ledger's unsupported state, the way the ledger does it.

    ``unsupported`` is reached when a check failed, so the log says which one.
    It is reachable from every other state, which is why a report may not
    disclose a conflict about a record the ledger holds as unsupported: the
    record may never have had one.
    """
    append_verification(
        world.connection,
        record_id,
        VerificationRecord(
            check=CheckKind.C3,
            checker_id=C3_CHECKER_ID,
            outcome=CheckOutcome.FAIL,
            detail="the cell does not support the record",
            checked_at=NOW,
        ),
    )
    world.connection.commit()
    advance(
        world.connection,
        record_id,
        VerificationStatus.UNSUPPORTED,
        index=world.index,
        checked_at=NOW,
    )
    world.connection.commit()


def _disclosure_report(
    *,
    record_id: str = "rec-1",
    status: VerificationStatus = VerificationStatus.CONFLICTED,
    value: float = LEDGER_VALUE,
    view: LedgerRecordView | None = None,
    snapshot_record_ids: tuple[str, ...] | None = None,
) -> ReportDocument:
    """A report that discloses one unresolved record and states nothing else.

    A disclosure carries no citation: the model gives citations to claims
    only, so a report that discloses and states nothing has no footnote
    either, and one it does not cite would be a link with nothing behind it.
    """
    if view is None:
        view = _unresolved_view(record_id=record_id, status=status, value=value)
    return _document(
        claims=(),
        footnotes=(),
        sections=(_section(blocks=(UnresolvedBlock(record_id=view.record_id),)),),
        unresolved_records=(
            _unresolved(record_id=view.record_id, status=status, value=value, view=view),
        ),
        record_ids=snapshot_record_ids,
    )


def _link_out_of_the_workspace(link: Path, target: Path) -> None:
    """A directory *inside* the workspace that leads out of it.

    A junction on Windows, because ``Path.is_symlink()`` does not report one
    and a symlink there may need privileges the test runner does not have; a
    symlink everywhere else. Both are followed by ``resolve()``, which is the
    only thing that sees through either.
    """
    if os.name == "nt":
        proc = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            pytest.skip("mklink /J unavailable: " + proc.stderr.decode("utf-8", "replace"))
        return
    link.symlink_to(target, target_is_directory=True)


def _claim(
    *,
    claim_id: str = "clm-1",
    record: LedgerRecordView | None = None,
    footnote_ids: tuple[str, ...] = ("fn-1",),
) -> ReportClaim:
    """A claim on a record, citing the citation that shows where it came from."""
    return ReportClaim(
        claim_id=claim_id,
        record=_numeric_view() if record is None else record,
        footnote_ids=footnote_ids,
    )


def _footnote(
    *,
    footnote_id: str = "fn-1",
    source_id: str = "src-1",
    locator: Any = None,
    content_sha256: str = SOURCE_HASH,
) -> ProvenanceFootnote:
    """A citation: a source, an address and the bytes it pointed at."""
    return ProvenanceFootnote(
        footnote_id=footnote_id,
        source_id=source_id,
        locator=PdfLocator(page=2) if locator is None else locator,
        content_sha256=content_sha256,
    )


def _manifest() -> ReproducibilityManifest:
    """The derivation the figure came from."""
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
            parameters={"selection": selection, "column": "yield"},
            input_hashes=(SOURCE_HASH,),
        ),
        recipe=FileRef(relative_path="recipes/mean.py", content_sha256=_sha("recipe")),
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
    relative_path: str = FIGURE_PATH,
    content_sha256: str = "b" * 64,
    caption: str = "Mean yield across the five measured runs.",
) -> ReportFigure:
    """A figure with its caption and the manifest that describes it."""
    return ReportFigure(
        figure_id=figure_id,
        relative_path=relative_path,
        content_sha256=content_sha256,
        caption=caption,
        manifest=_manifest(),
    )


def _table(
    *,
    table_id: str = "tab-1",
    relative_path: str = TABLE_PATH,
    content_sha256: str = "c" * 64,
) -> ReportTable:
    """A table artefact, by path and hash — and, unlike a figure, no caption."""
    return ReportTable(
        table_id=table_id,
        relative_path=relative_path,
        content_sha256=content_sha256,
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
    claims: tuple[ReportClaim, ...] | None = None,
    figures: tuple[ReportFigure, ...] = (),
    tables: tuple[ReportTable, ...] = (),
    footnotes: tuple[ProvenanceFootnote, ...] | None = None,
    sections: tuple[ReportSection, ...] | None = None,
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
        title="A first-pass report",
        snapshot=LedgerSnapshot(as_of=NOW, record_ids=record_ids),
        sections=sections,
        claims=claims,
        figures=figures,
        tables=tables,
        footnotes=footnotes,
        unresolved_records=unresolved_records,
    )


def _report(world: World) -> ReportDocument:
    """A report that agrees with the ledger, the index and the disk.

    The positive control: everything the checks look at, in agreement.
    """
    return _document(
        claims=(_claim(),),
        figures=(_figure(content_sha256=world.figure_hash),),
        tables=(_table(content_sha256=world.table_hash),),
        footnotes=(_footnote(),),
        sections=(
            _section(
                blocks=(
                    ClaimBlock(claim_id="clm-1"),
                    FigureBlock(figure_id="fig-1"),
                    TableBlock(table_id="tab-1"),
                )
            ),
        ),
        record_ids=("rec-1",),
    )


def _gate(world: World, document: ReportDocument) -> None:
    """Run the whole gate over a document."""
    check_report(
        document,
        ledger=world.ledger,
        index=world.index,
        workspace_root=world.root,
    )


# ---------------------------------------------------------------------------
# The gate lets a good report through
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_a_report_that_agrees_with_the_ledger_and_the_disk_is_accepted(world: World) -> None:
    """The positive control, and it is not optional.

    Every other test in this file is satisfied by a gate that refuses
    everything, and a gate that cannot pass is as useless as a gate that
    cannot fail. This is the report the checks exist to let through: its
    numbers are the ledger's, its figure is the file on disk, its citation
    resolves, its claim rests on a record the ledger holds.
    """
    _gate(world, _report(world))


@pytest.mark.unit
def test_every_check_takes_the_model_and_the_material_it_is_checked_against() -> None:
    """The checks are about the model, and about nothing else.

    A check that took an export would be a *second* content: the export's
    own numbers, its own captions, its own links. The four renderings would
    then have to agree with each other, which is the defect this work order
    exists to prevent. So every check takes the model and the machinery it
    is checked against — the ledger, the index, the disk — and nothing that
    could carry a rendered report.
    """
    allowed = {"document", "ledger", "index", "workspace_root"}
    checks = (
        check_report,
        check_numbers_agree_with_the_ledger,
        check_claims_and_disclosures_rest_on_records_the_ledger_holds,
        check_links_resolve,
        check_figures_and_tables_are_the_artefacts_on_disk,
        check_the_snapshot_names_the_records_the_report_carries,
    )
    for check in checks:
        names = set(inspect.signature(check).parameters)
        assert names <= allowed, f"{check.__name__} takes {sorted(names - allowed)}"
        assert "document" in names, f"{check.__name__} takes no model"


# ---------------------------------------------------------------------------
# Check 1 — every number in the report is the ledger's number
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_a_report_that_states_a_number_the_ledger_does_not_hold_is_refused(world: World) -> None:
    """4.25 where the ledger says 4.5.

    The work order's own example, and the refusal is the whole answer: the
    report is not written, and nothing anywhere corrects the number to
    4.5. A check that repaired the document would be a second copy of the
    ledger with its own idea of what the number is.
    """
    world.connection.execute(
        sql_text("UPDATE evidence_records SET value = 4.5 WHERE evidence_id = 'rec-1'")
    )
    world.connection.commit()
    document = _document(
        claims=(_claim(record=_numeric_view(value=ROUNDED_VALUE)),),
        record_ids=("rec-1",),
    )

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, document)

    assert refusal.value.check == "numbers"


@pytest.mark.unit
def test_a_report_that_rounds_the_ledger_number_is_refused(world: World) -> None:
    """The near miss: the number, compared rounded.

    The ledger holds 4.253 and the report says 4.25. The two are the same
    quantity to two decimal places and a different claim to three, and a
    check that compared their rounded forms would accept it — so the number
    a reader would check against the ledger is not the number the ledger
    holds. The comparison here is exact, and this is the test that says so.
    """
    document = _document(
        claims=(_claim(record=_numeric_view(value=ROUNDED_VALUE)),),
        record_ids=("rec-1",),
    )

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, document)

    assert refusal.value.check == "numbers"


@pytest.mark.unit
def test_a_report_that_restates_the_unit_is_refused(world: World) -> None:
    """The unit is declared and never inferred.

    A report that says "percent" where the ledger says "%" is not a
    different quantity — but it is a report that does not say what the
    ledger says, and a reader comparing the two would have to guess which
    spelling is the record's.
    """
    document = _document(
        claims=(_claim(record=_numeric_view(unit="percent")),),
        record_ids=("rec-1",),
    )

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, document)

    assert refusal.value.check == "numbers"


# ---------------------------------------------------------------------------
# Check 2 — every figure is captioned, and is the picture on disk
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_a_figure_whose_bytes_are_not_the_ones_on_disk_is_refused(world: World) -> None:
    """The near miss: the model's own hash, believed.

    The picture on disk is replaced after the report names it. A check that
    compared the model's hash with the model's hash would pass — the model
    and the model always agree — and the report would show a picture of
    something else, with a caption about the first one.
    """
    (world.root / FIGURE_PATH).write_bytes(b"<svg><!-- replaced --></svg>")
    document = _report(world)

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, document)

    assert refusal.value.check == "artefacts"


@pytest.mark.unit
def test_a_figure_that_is_not_on_disk_is_refused(world: World) -> None:
    """A figure the report cannot find is a picture of nothing.

    The path is workspace-relative, and a path that resolves to nothing is a
    broken link in the shape of a figure.
    """
    (world.root / FIGURE_PATH).unlink()
    document = _report(world)

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, document)

    assert refusal.value.check == "artefacts"


@pytest.mark.unit
def test_a_figure_without_a_caption_is_refused(world: World) -> None:
    """The caption is the model's.

    The document here is built **without** the model's validators — Pydantic's
    ``model_copy`` does not run them — so that the *check* is what refuses.
    The model refuses this document too, and that is not what this test
    observes: a check that leaned on the model would be a check that could
    not fail on its own.
    """
    document = _report(world)
    figure = document.figures[0].model_copy(update={"caption": "   "})
    blank = document.model_copy(update={"figures": (figure,)})

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, blank)

    assert refusal.value.check == "artefacts"


@pytest.mark.unit
def test_a_table_whose_bytes_are_not_the_ones_on_disk_is_refused(world: World) -> None:
    """A table is a reference in the same shape as a figure, so it is checked
    the same way.

    The model carries the table by path and by hash, exactly as it carries
    the figure, and the file on disk is replaced after the report names it.
    Verifying a figure's bytes and leaving a table's alone would have no
    principle behind it: a reader of the checks would assume the table the
    report includes is the table on disk, and the answer would be that
    nobody looked.
    """
    (world.root / TABLE_PATH).write_bytes(b"run,yield\n1,9.999\n")
    document = _report(world)

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, document)

    assert refusal.value.check == "artefacts"


@pytest.mark.unit
def test_a_table_that_is_not_on_disk_is_refused(world: World) -> None:
    """And a table that cannot be found is refused the same way.

    The report includes a table that is not there, which is a reference to
    nothing — the same failure as a figure that is not there, and the same
    refusal.
    """
    (world.root / TABLE_PATH).unlink()
    document = _report(world)

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, document)

    assert refusal.value.check == "artefacts"


# ---------------------------------------------------------------------------
# Check 3 — every citation is an address the index can resolve
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_a_citation_to_an_address_that_does_not_resolve_is_refused(world: World) -> None:
    """The near miss: the locator's text, compared.

    The anchor is registered at page 99 and the citation names page 99, so
    every comparison of addresses agrees — and the material has three pages,
    so the address holds nothing. A check that compared the two locators
    would pass it; a check that *resolves* it cannot. ADR-0004's A1 is
    explicit that nothing is cited in its place: not the nearest page, not
    the last one.
    """
    _insert_anchor(world.connection, "anc-9", "src-1", PdfLocator(page=99), SOURCE_HASH)
    world.connection.execute(
        sql_text(
            "INSERT INTO evidence_anchors (evidence_id, position, anchor_id)"
            " VALUES ('rec-1', 1, 'anc-9')"
        )
    )
    world.connection.commit()
    document = _document(
        claims=(_claim(record=_numeric_view(anchors=("anc-1", "anc-9"))),),
        footnotes=(_footnote(locator=PdfLocator(page=99)),),
        record_ids=("rec-1",),
    )

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, document)

    assert refusal.value.check == "links"


@pytest.mark.unit
def test_a_citation_to_an_address_the_ledger_never_registered_is_refused(world: World) -> None:
    """Page 3 is in the material and no anchor names it.

    The citation names a well-formed address that the record was not read
    from, and a comparison of addresses would find nothing to disagree
    with: there is no second address to compare it with.
    """
    _insert_text(world.connection, SOURCE_HASH, PdfLocator(page=3), "Discussion.")
    world.connection.commit()
    document = _document(
        claims=(_claim(),),
        footnotes=(_footnote(locator=PdfLocator(page=3)),),
        record_ids=("rec-1",),
    )

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, document)

    assert refusal.value.check == "links"


@pytest.mark.unit
def test_a_citation_no_claim_rests_on_is_refused(world: World) -> None:
    """A citation with no claim behind it has no address to resolve.

    The address of a citation is the address of the record a claim rests
    on. A citation nobody rests on is a link in the report's reference list
    that no record vouches for — and a report is a document, not a
    bibliography.
    """
    document = _document(
        claims=(_claim(),),
        footnotes=(_footnote(), _footnote(footnote_id="fn-2")),
        record_ids=("rec-1",),
    )

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, document)

    assert refusal.value.check == "links"


# ---------------------------------------------------------------------------
# Check 4 — every claim names a record that may be stated as a finding
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_a_claim_whose_record_has_since_become_a_conflict_is_refused(world: World) -> None:
    """The near miss: the model's own copy of the record.

    The report was written when the record was verified; the ledger now
    says the two readings of the same cell disagree. A check that read the
    model's copy would pass it — the model says ``extracted`` and the model
    is what is being checked — and the report would state a conflict as a
    finding, which is the one thing ADR-0004's rule about neither reading
    winning by recency exists to prevent.

    The ledger's state is one the ledger produced: a second record on the
    same cell with the opposite C3 verdict, and the transition the state
    machine allows.
    """
    _conflicted_in_the_ledger(world)

    document = _report(world)

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, document)

    assert refusal.value.check == "records"


@pytest.mark.unit
def test_a_claim_whose_record_the_ledger_does_not_hold_is_refused(world: World) -> None:
    """A claim names the record it rests on, and the ledger holds the records.

    The id is well-formed and the number is the right number; there is
    simply no record behind it, and a reader cannot look up what the
    report says it rests on.
    """
    document = _document(
        claims=(_claim(record=_numeric_view(record_id="rec-absent")),),
        record_ids=("rec-absent",),
    )

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, document)

    assert refusal.value.check == "records"


@pytest.mark.unit
def test_a_claim_that_states_words_the_ledger_does_not_hold_is_refused(world: World) -> None:
    """The report's sentence is the ledger's sentence.

    A claim record's text is what the report prints. A report that printed
    a different sentence would be making a statement the ledger never made,
    and no hash anywhere would say so — the hash binds the *record*, not the
    wording the report chose for it.
    """
    document = _document(
        claims=(
            _claim(
                claim_id="clm-2",
                record=_claim_view(text="The material reports a yield of 9.999%."),
            ),
        ),
        sections=(_section(blocks=(ClaimBlock(claim_id="clm-2"),)),),
        record_ids=("rec-2",),
    )

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, document)

    assert refusal.value.check == "records"


# ---------------------------------------------------------------------------
# Check 5 — the report's extent is answerable
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_a_snapshot_that_does_not_name_a_record_the_report_carries_is_refused(
    world: World,
) -> None:
    """The snapshot is the report's statement of what it is a view of.

    The document is built **without** the model's validators — Pydantic's
    ``model_copy`` does not run them — so that the *check* is what refuses.
    A record the snapshot does not name is a record the reader cannot check
    the view against.
    """
    document = _report(world)
    short = document.model_copy(
        update={"snapshot": LedgerSnapshot(as_of=NOW, record_ids=("rec-2",))}
    )

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, short)

    assert refusal.value.check == "snapshot"


@pytest.mark.unit
def test_a_snapshot_that_names_a_record_the_report_does_not_carry_is_refused(
    world: World,
) -> None:
    """And the extent is answerable in the other direction too.

    A snapshot naming a record the report does not show makes "which records
    is this a view of" answerable two ways.
    """
    document = _report(world)
    wide = document.model_copy(
        update={"snapshot": LedgerSnapshot(as_of=NOW, record_ids=("rec-1", "rec-2"))}
    )

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, wide)

    assert refusal.value.check == "snapshot"


# ---------------------------------------------------------------------------
# What the ledger decides, and what the report may say about it
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_a_report_that_overstates_the_record_verification_is_refused(world: World) -> None:
    """The status may not be stronger than the ledger's.

    The ledger holds the record as ``extracted`` — located, copied out,
    hashed, and confirmed by nothing. The report says ``verified_by_rule``,
    which is a claim about the strength of a verification the ledger does
    not record, and the report prints that status beside the statement it
    makes.
    """
    document = _document(
        claims=(_claim(record=_numeric_view(status=VerificationStatus.VERIFIED_BY_RULE)),),
        record_ids=("rec-1",),
    )

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, document)

    assert refusal.value.check == "records"


@pytest.mark.unit
def test_a_report_that_understates_the_record_verification_is_accepted(world: World) -> None:
    """The rule is a ceiling and not equality, and this is what says so.

    The record was promoted after the report was written: the ledger now
    holds it as ``verified_by_rule`` and the report says ``extracted``.
    Understating is not drift — "this was located and copied out" was true
    when the report was written and it is true now — so nothing refuses it.

    A check that compared the two statuses for *equality* would refuse it,
    and would be wrong: equality would turn "this was true then" into "this
    was never written".
    """
    append_verification(
        world.connection,
        "rec-1",
        VerificationRecord(
            check=CheckKind.C3,
            checker_id=C3_CHECKER_ID,
            outcome=CheckOutcome.PASS,
            detail="the cell holds 4.253",
            checked_at=NOW,
        ),
    )
    world.connection.commit()
    advance(
        world.connection,
        "rec-1",
        VerificationStatus.VERIFIED_BY_RULE,
        index=world.index,
        checked_at=NOW,
    )
    world.connection.commit()

    document = _document(
        claims=(_claim(record=_numeric_view(status=VerificationStatus.EXTRACTED)),),
        record_ids=("rec-1",),
    )

    _gate(world, document)


@pytest.mark.unit
def test_a_claim_that_says_a_numeric_record_is_a_claim_is_refused(world: World) -> None:
    """A number and a sentence are kept apart on purpose.

    The ledger holds ``rec-2`` as a claim — a statement — and the report
    says it is a numeric record with a value, so the report would print a
    number the ledger does not hold and call it the record's.

    The refusal names the two kinds, and the assertion is on that wording
    rather than on the refusal alone: a text comparison is a second guard
    for the same case, so a refusal that said only "the words differ" would
    be a report that mis-states the kind refused for the wrong reason.
    """
    document = _document(
        claims=(_claim(record=_numeric_view(record_id="rec-2")),),
        record_ids=("rec-2",),
    )

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, document)

    assert refusal.value.check == "records"
    assert "states a 'numeric' record" in refusal.value.reason
    assert "is a 'claim' one" in refusal.value.reason


@pytest.mark.unit
def test_a_claim_that_says_a_claim_record_is_a_number_is_refused(world: World) -> None:
    """And the other way round.

    The ledger holds ``rec-1`` as a number and the report says it is a
    statement, so the report would print the ledger's words for a record
    that has none.
    """
    document = _document(
        claims=(_claim(record=_claim_view(record_id="rec-1")),),
        record_ids=("rec-1",),
    )

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, document)

    assert refusal.value.check == "records"
    assert "states a 'claim' record" in refusal.value.reason
    assert "is a 'numeric' one" in refusal.value.reason


@pytest.mark.unit
def test_a_claim_resting_on_an_anchor_the_ledger_never_heard_of_is_refused(
    world: World,
) -> None:
    """Every anchor a claim rests on must be one the ledger holds.

    The claim names an anchor id that was never registered. The ledger has
    never heard of it, so nothing vouches for the address it was read from,
    and one good anchor among several does not make the others good.
    """
    document = _document(
        claims=(_claim(record=_numeric_view(anchors=("anc-1", "anc-ghost"))),),
        record_ids=("rec-1",),
    )

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, document)

    assert refusal.value.check == "links"


@pytest.mark.unit
def test_a_snapshot_that_does_not_name_an_unresolved_record_is_refused(world: World) -> None:
    """A disclosure is a record the report carries too.

    The report discloses a conflicted record and its snapshot does not name
    it, so "which records is this a view of" is unanswerable for exactly the
    records that matter most — the ones nobody could agree on.

    The document is built **without** the model's validators — Pydantic's
    ``model_copy`` does not run them — so that the *check* is what refuses.
    """
    _conflicted_in_the_ledger(world)
    document = _disclosure_report(record_id="rec-1", snapshot_record_ids=("rec-1",))
    short = document.model_copy(update={"snapshot": LedgerSnapshot(as_of=NOW, record_ids=())})

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, short)

    assert refusal.value.check == "snapshot"


@pytest.mark.unit
def test_a_figure_whose_path_leaves_the_workspace_is_refused(world: World) -> None:
    """A figure is a file in the workspace, and one outside it is not it.

    The path names a file above the workspace root. The model refuses such a
    path on construction — the document here is built **without** the model's
    validators, so that the *check* is what refuses — and the check refuses
    it because the resolved path is outside the workspace, not because the
    bytes happen to differ.
    """
    outside = world.root.parent / "outside"
    outside.mkdir()
    (outside / "fig-1.svg").write_bytes(FIGURE_BYTES)
    document = _report(world)
    figure = document.figures[0].model_copy(update={"relative_path": "../outside/fig-1.svg"})
    escaped = document.model_copy(update={"figures": (figure,)})

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, escaped)

    assert refusal.value.check == "artefacts"
    assert "outside the workspace" in refusal.value.reason


@pytest.mark.unit
def test_a_figure_reached_through_a_link_out_of_the_workspace_is_refused(world: World) -> None:
    """The escape that only ``resolve()`` sees.

    The path is inside the workspace and stays there — no ``..``, no drive
    letter, nothing the model's own rule can refuse — and the file it names
    is outside, because a directory inside the workspace leads out of it.
    A Windows junction is not a symlink and ``Path.is_symlink()`` does not
    report one, which is why the guard resolves the path and then asks where
    it landed.
    """
    outside = world.root.parent / "outside"
    outside.mkdir(exist_ok=True)
    (outside / "fig-1.svg").write_bytes(FIGURE_BYTES)
    _link_out_of_the_workspace(world.root / "escape", outside)
    document = _report(world)
    figure = document.figures[0].model_copy(update={"relative_path": "escape/fig-1.svg"})
    escaped = document.model_copy(update={"figures": (figure,)})

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, escaped)

    assert refusal.value.check == "artefacts"
    assert "outside the workspace" in refusal.value.reason


# ---------------------------------------------------------------------------
# A disclosure is the ledger's own state, and the two directions are both
# refused
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_a_disclosure_that_matches_the_ledger_is_accepted(world: World) -> None:
    """The positive control for the disclosure rule.

    The ledger holds the record as ``conflicted`` and the report discloses it
    as ``conflicted``. Nothing refuses that, and nothing should: a disclosure
    that says what the ledger says is the whole of what a disclosure is.
    """
    _conflicted_in_the_ledger(world)
    document = _disclosure_report(record_id="rec-1")

    _gate(world, document)


@pytest.mark.unit
def test_a_disclosure_of_a_conflict_the_ledger_does_not_record_is_refused(
    world: World,
) -> None:
    """A conflict the ledger does not record is a conflict the report invented.

    ``unsupported`` is reachable from ``planned``, ``extracted``,
    ``verified_by_rule`` and ``user_attested`` as well as from ``conflicted``,
    so a record the ledger holds as unsupported may never have had a conflict
    at all. Disclosing one is a statement the ledger does not make.
    """
    _unsupported_in_the_ledger(world)
    document = _disclosure_report(
        record_id="rec-1",
        status=VerificationStatus.CONFLICTED,
    )

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, document)

    assert refusal.value.check == "records"


@pytest.mark.unit
def test_a_disclosure_that_hides_a_conflict_is_refused(world: World) -> None:
    """And a conflict the ledger records may not be disclosed as anything else.

    The ledger says two readings disagree beyond tolerance, and ADR-0004's
    A5 says the conflict is *displayed* rather than resolved. A disclosure
    that says ``unsupported`` about it displays the absence of support
    instead, which is a different and weaker statement.
    """
    _conflicted_in_the_ledger(world)
    document = _disclosure_report(
        record_id="rec-1",
        status=VerificationStatus.UNSUPPORTED,
    )

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, document)

    assert refusal.value.check == "records"


@pytest.mark.unit
def test_a_disclosure_of_a_record_the_ledger_does_not_hold_is_refused(world: World) -> None:
    """A disclosure is a record the ledger carries and could not resolve.

    The report discloses a record the ledger has never heard of, which is a
    conflict with nothing behind it — and the ledger's own answer to "could
    this be resolved?" is a fact about a record it holds.
    """
    document = _disclosure_report(record_id="rec-absent")

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, document)

    assert refusal.value.check == "records"


@pytest.mark.unit
def test_a_disclosure_that_states_a_number_the_ledger_does_not_hold_is_refused(
    world: World,
) -> None:
    """A number printed beside a conflict is a number the ledger holds.

    The disclosure carries the quantity the conflict is about, and the report
    prints it. So the number is compared like any other number in the report,
    and the comparison is the exact one.
    """
    _conflicted_in_the_ledger(world)
    document = _disclosure_report(record_id="rec-1", value=ROUNDED_VALUE)

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, document)

    assert refusal.value.check == "numbers"


@pytest.mark.unit
def test_a_disclosure_that_says_a_numeric_record_is_a_claim_is_refused(world: World) -> None:
    """A number and a sentence are kept apart on purpose — in a disclosure too.

    The ledger holds ``rec-1`` as a number and the report discloses it as a
    statement, so the report would print the ledger's words for a record that
    has none, and call the record a statement.
    """
    _unsupported_in_the_ledger(world, "rec-1")
    document = _disclosure_report(
        view=_unresolved_claim_view(record_id="rec-1", status=VerificationStatus.UNSUPPORTED)
    )

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, document)

    assert refusal.value.check == "records"
    assert "discloses a 'claim' record" in refusal.value.reason
    assert "but the ledger's record is a 'numeric' one" in refusal.value.reason


@pytest.mark.unit
def test_a_disclosure_that_says_a_claim_record_is_a_number_is_refused(world: World) -> None:
    """And the other way round.

    The ledger holds ``rec-2`` as a statement and the report discloses it as a
    number, so the report would print a quantity for a record that has none.
    """
    _unsupported_in_the_ledger(world, "rec-2")
    document = _disclosure_report(
        view=_unresolved_view(record_id="rec-2", status=VerificationStatus.UNSUPPORTED)
    )

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, document)

    assert refusal.value.check == "records"
    assert "discloses a 'numeric' record" in refusal.value.reason
    assert "but the ledger's record is a 'claim' one" in refusal.value.reason


@pytest.mark.unit
def test_a_disclosure_that_states_words_the_ledger_does_not_hold_is_refused(
    world: World,
) -> None:
    """A disclosure prints the record's words, so they are the ledger's.

    The record's **text** is the ledger's words and is compared; the
    disclosure's **reason** is the report's own prose about why the record
    could not be resolved, and the ledger holds no reason to compare it
    with. The two are different matters, and only one of them is checked.
    """
    _unsupported_in_the_ledger(world, "rec-2")
    document = _disclosure_report(
        view=_unresolved_claim_view(
            record_id="rec-2",
            status=VerificationStatus.UNSUPPORTED,
            text="The material reports a yield of 9.999%.",
        )
    )

    with pytest.raises(ReportRefusedError) as refusal:
        _gate(world, document)

    assert refusal.value.check == "records"
    assert "but the ledger's record says" in refusal.value.reason
