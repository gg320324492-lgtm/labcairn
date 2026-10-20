"""The one walk of the model that every renderer draws from.

The report's model holds ids: a block says ``clm-1`` and the document carries
the claim under that id. Turning the document into something a reader can
look at therefore needs a **resolution** step, and the question this module
answers is where that step lives.

It lives here, once, for all four renderers. The alternative — each renderer
looking ids up in the document itself — is four chances to resolve the same
reference four ways, and the failure is silent: a renderer that looked a
claim up wrongly would draw an empty space where a finding should be, and
nothing in the tree would notice, because the model is perfectly valid and
the export is perfectly well formed. One walk, resolved once, is the only way
"the four forms are four renderings of one model" is a property of the code
rather than of four implementations agreeing.

What the walk does is **resolve and compose, never decide**. It turns ids
into the objects they name; it groups the objects into sections; and it
composes, **once**, the words the report says about each of them. Every
renderer draws those words, so the four exports of one document say the same
thing — not because four implementations agreed, but because there is only
one sentence to draw.

Two properties of the resolution are worth naming.

**Every claim carries the citations it names, resolved.** A claim's
``footnote_ids`` are ids, and a renderer that printed the ids would print
``fn-1`` where the reader needs to know *where* ``fn-1`` is. The footnote
objects are attached to the claim here, so all four renderers show the same
citation for the same claim.

**Nothing in the model is dropped.** The model requires every claim and every
disclosed record to be placed in a section, but it does not require a figure
or a table to be: a document may carry a figure that no section places. A
renderer that drew only the placed figures would silently lose that one, and
"the export is openable" would not notice. The figures and tables that no
section places are therefore carried separately, and every renderer draws
them under a heading of their own rather than losing them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from labcairn.reports.model import (
    BlockKind,
    ClaimBlock,
    FigureBlock,
    InterpretationBlock,
    LedgerRecordView,
    NarrativeBlock,
    ProvenanceFootnote,
    ReportBlock,
    ReportClaim,
    ReportDocument,
    ReportFigure,
    ReportTable,
    TableBlock,
    UnresolvedBlock,
    UnresolvedRecord,
)
from labcairn.reports.render.constants import INTERPRETATION_MARKER
from labcairn.sources.locators import describe_locator

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "ClaimItem",
    "FigureItem",
    "FootnoteItem",
    "InterpretationItem",
    "NarrativeItem",
    "ReportItem",
    "ReportRenderError",
    "ResolvedReport",
    "ResolvedSection",
    "TableItem",
    "UnresolvedItem",
    "resolve",
    "with_interpretation_marker",
]


class ReportRenderError(RuntimeError):
    """The model holds something a renderer cannot draw.

    A refusal, in the tree's own idiom: a figure with something missing from
    it is worse than a figure that was refused, because a reader cannot tell
    which part was meant. The model refuses contradictions on construction,
    so reaching this is a statement that the model was not built by this
    tree's model — and it names what it was drawing.
    """


@dataclass(frozen=True, slots=True)
class NarrativeItem:
    """A paragraph of the report's own prose that infers nothing.

    What the material is, what was done, what the report does not cover. It
    carries no marker, and that is the point: a renderer that marked every
    paragraph would be calling a description an inference.
    """

    text: str

    @property
    def kind(self) -> BlockKind:
        """Which kind of block this is. The model says so; the renderer asks."""
        return BlockKind.NARRATIVE

    @property
    def is_interpretation(self) -> bool:
        """Whether this item is an interpretation. This one is not."""
        return False

    @property
    def lines(self) -> tuple[str, ...]:
        """What the report says about this item, in plain text.

        The wording is composed **here**, once, and every renderer draws
        it. A renderer that composed its own wording would be a second
        spelling of the report's voice, and the four exports of one
        document would then not be saying the same thing — which is the
        whole property the report's four forms are supposed to have.

        The text is the model's and is not escaped here: escaping is the
        renderer's business, because the four renderers escape for four
        different destinations.
        """
        return (self.text,)


@dataclass(frozen=True, slots=True)
class InterpretationItem:
    """The report's own inference: what its findings mean.

    The kind says so, so the renderer does not have to work it out — and a
    renderer that worked it out from the wording of the prose would be
    guessing, which is the failure ADR-0004's A10 exists to prevent.
    """

    text: str

    @property
    def kind(self) -> BlockKind:
        """Which kind of block this is."""
        return BlockKind.INTERPRETATION

    @property
    def is_interpretation(self) -> bool:
        """Whether this item is an interpretation. This one is."""
        return True

    @property
    def lines(self) -> tuple[str, ...]:
        """What the report says about this item, in plain text.

        The interpretation marker is **not** part of it: the marker is the
        product's own sentence, and the renderer appends it after the
        escaping, so that it appears in the export exactly as the product
        spells it.
        """
        return (self.text,)


@dataclass(frozen=True, slots=True)
class ClaimItem:
    """One statement the report makes, and the citations that show where.

    The record is the claim's own: what it says, how far it was checked, and
    whether it is an interpretation. The citations are resolved here, so the
    four renderers show the same locator for the same claim.
    """

    claim: ReportClaim
    footnotes: tuple[FootnoteItem, ...]

    @property
    def kind(self) -> BlockKind:
        """Which kind of block this is."""
        return BlockKind.CLAIM

    @property
    def label(self) -> str:
        """The claim's id, as the report names it."""
        return self.claim.claim_id

    @property
    def statement(self) -> str:
        """What the claim says, in the record's own words.

        A numeric record's statement is its number and its declared unit;
        a claim or result record's statement is its text. The number is the
        ledger's, at the ledger's precision: it is drawn with ``repr``,
        which is the shortest spelling that reads back as the same float, so
        a report cannot say 4.25 where the ledger says 4.253.
        """
        return _record_statement(self.claim.record)

    @property
    def status(self) -> str:
        """How far the record has been through the six-state machine.

        Carried so that a reader can see which of the report's sentences
        were checked and which were not.
        """
        return self.claim.record.status.value

    @property
    def is_interpretation(self) -> bool:
        """Whether the claim rests on an interpretation.

        A claim resting on a ``claim`` or ``result`` record is an
        interpretation, because the record's kind says the record states
        something no rule confirmed. :attr:`LedgerRecordView.is_interpretation`
        is the one spelling of that rule, and the renderer asks it rather
        than working out the kinds again.
        """
        return self.claim.record.is_interpretation

    @property
    def citation_ids(self) -> tuple[str, ...]:
        """The ids of the citations this claim names."""
        return tuple(footnote.label for footnote in self.footnotes)

    @property
    def lines(self) -> tuple[str, ...]:
        """What the report says about this claim, in plain text.

        The label, the statement, how far the record was checked, and the
        citations it names — in that order, and in one spelling, so that
        the four exports say the same thing about the same claim.
        """
        line = f"{self.label} — {self.statement} ({self.status})"
        if self.citation_ids:
            line = f"{line} [{', '.join(self.citation_ids)}]"
        return (line,)


@dataclass(frozen=True, slots=True)
class FigureItem:
    """One figure, under its caption.

    The caption is the model's, and it is carried here so that no renderer
    can be the one that wrote it. The figure's *bytes* are not in the model:
    the document names the artefact and its hash, and the artefact manifest
    is what records those bytes. A renderer therefore **names** the figure
    rather than embedding it — embedding would mean reading the workspace,
    and a renderer that reads the workspace is not a function of the model.
    """

    figure: ReportFigure

    @property
    def kind(self) -> BlockKind:
        """Which kind of block this is."""
        return BlockKind.FIGURE

    @property
    def is_interpretation(self) -> bool:
        """Whether this item is an interpretation. This one is not."""
        return False

    @property
    def label(self) -> str:
        """The figure's id, as the report names it."""
        return self.figure.figure_id

    @property
    def caption(self) -> str:
        """The caption, in the model's words."""
        return self.figure.caption

    @property
    def path(self) -> str:
        """Where the figure's bytes are, workspace-relative."""
        return self.figure.relative_path

    @property
    def content_sha256(self) -> str:
        """The hash of the figure's bytes, as they were when the report saw them."""
        return self.figure.content_sha256

    @property
    def lines(self) -> tuple[str, ...]:
        """What the report says about this figure, in plain text.

        The caption, and then the artefact it names: the path and the hash
        of the bytes. The bytes themselves are not in the model, so the
        report names the artefact and the artefact manifest carries it.
        """
        return (
            f"Figure {self.label}. {self.caption}",
            f"Artefact: {self.path} (sha256 {self.content_sha256})",
        )


@dataclass(frozen=True, slots=True)
class TableItem:
    """One table, named.

    A fact about a file rather than a copy of it, for the reason the model's
    own docstring gives: the bytes are in the workspace, and the report says
    which bytes.
    """

    table: ReportTable

    @property
    def kind(self) -> BlockKind:
        """Which kind of block this is."""
        return BlockKind.TABLE

    @property
    def is_interpretation(self) -> bool:
        """Whether this item is an interpretation. This one is not."""
        return False

    @property
    def label(self) -> str:
        """The table's id, as the report names it."""
        return self.table.table_id

    @property
    def path(self) -> str:
        """Where the table's bytes are, workspace-relative."""
        return self.table.relative_path

    @property
    def content_sha256(self) -> str:
        """The hash of the table's bytes."""
        return self.table.content_sha256

    @property
    def lines(self) -> tuple[str, ...]:
        """What the report says about this table, in plain text."""
        return (
            f"Table {self.label}",
            f"Artefact: {self.path} (sha256 {self.content_sha256})",
        )


@dataclass(frozen=True, slots=True)
class UnresolvedItem:
    """A record the report discloses rather than states.

    Drawn differently from a claim, because it is a different kind of
    statement: a conflict or an absence of support, with the reason it
    could not be resolved. A renderer that drew this as it drew a claim
    would be stating a conflict as a finding.
    """

    unresolved: UnresolvedRecord

    @property
    def kind(self) -> BlockKind:
        """Which kind of block this is."""
        return BlockKind.UNRESOLVED

    @property
    def is_interpretation(self) -> bool:
        """Whether this item is an interpretation. This one is not."""
        return False

    @property
    def label(self) -> str:
        """The record's id, as the report names it."""
        return self.unresolved.record.record_id

    @property
    def statement(self) -> str:
        """What the record holds, in the record's own words."""
        return _record_statement(self.unresolved.record)

    @property
    def status(self) -> str:
        """Why the record is not a finding."""
        return self.unresolved.record.status.value

    @property
    def reason(self) -> str:
        """Why the record is unresolved. Never blank: the model requires it."""
        return self.unresolved.reason

    @property
    def lines(self) -> tuple[str, ...]:
        """What the report says about this disclosure, in plain text.

        The record, what it holds, why it is not a finding, and why it
        could not be resolved — a reader who is shown a conflict has to be
        shown what it was about.
        """
        return (f"{self.label} — {self.statement} — {self.status} — {self.reason}",)


@dataclass(frozen=True, slots=True)
class FootnoteItem:
    """One citation: what it points at, and which bytes it pointed at.

    The locator's own rendering is
    :func:`labcairn.sources.locators.describe_locator`, because that
    function computes the address **from the structured fields** and is the
    only rendering path there is. A renderer that formatted the locator
    itself would be a second spelling of a re-derivable address, and the two
    spellings could drift.
    """

    footnote: ProvenanceFootnote

    @property
    def label(self) -> str:
        """The citation's id, as the report names it."""
        return self.footnote.footnote_id

    @property
    def source_id(self) -> str:
        """The ledger's id for the source the citation points into."""
        return self.footnote.source_id

    @property
    def locator(self) -> str:
        """Where in the source, rendered from the structured address."""
        return describe_locator(self.footnote.locator)

    @property
    def content_sha256(self) -> str:
        """The hash of the bytes the citation pointed at."""
        return self.footnote.content_sha256

    @property
    def lines(self) -> tuple[str, ...]:
        """What the report says about this citation, in plain text.

        The citation, the source it points into, the address within it, and
        the hash of the bytes it pointed at: the three things ADR-0004's A6
        asks a source to be recorded with, and no external identifier,
        because nothing in the tree resolves one.
        """
        return (
            f"{self.label} — source {self.source_id} — {self.locator}"
            f" — sha256 {self.content_sha256}",
        )


#: One resolved block of a section.
#:
#: A union rather than one wide model with optional fields, for the reason
#: the report's own model is: a single shape whose fields are all optional
#: cannot say which combination of them makes sense, and every new field
#: would silently widen what a block may be.
ReportItem = (
    NarrativeItem | InterpretationItem | ClaimItem | FigureItem | TableItem | UnresolvedItem
)


@dataclass(frozen=True, slots=True)
class ResolvedSection:
    """One section, with its blocks resolved."""

    section_id: str
    heading: str
    items: tuple[ReportItem, ...]


@dataclass(frozen=True, slots=True)
class ResolvedReport:
    """The report, walked once: what every renderer draws."""

    title: str
    #: The moment the document is a view of.
    as_of: datetime
    #: The records the view is made of, in the model's order.
    record_ids: tuple[str, ...]
    sections: tuple[ResolvedSection, ...]
    #: Every citation the document carries.
    footnotes: tuple[FootnoteItem, ...]
    #: Figures and tables the document carries but no section places.
    unplaced_figures: tuple[FigureItem, ...]
    unplaced_tables: tuple[TableItem, ...]


def resolve(document: ReportDocument) -> ResolvedReport:
    """Walk the document once, and hand the four renderers the same result.

    :param document: the report's model, frozen at one moment.
    :returns: the resolved report: sections with their blocks resolved, the
        citations resolved, and the artefacts no section placed carried
        separately so that no renderer loses them.
    :raises ReportRenderError: when the document names something it does not
        carry. The model refuses such a document on construction, so this is
        a statement that the document was not built by this tree's model.
    """
    claims_by_id = {claim.claim_id: claim for claim in document.claims}
    figures_by_id = {figure.figure_id: figure for figure in document.figures}
    tables_by_id = {table.table_id: table for table in document.tables}
    unresolved_by_id = {record.record.record_id: record for record in document.unresolved_records}
    footnotes_by_id = {footnote.footnote_id: footnote for footnote in document.footnotes}

    placed_figures: set[str] = set()
    placed_tables: set[str] = set()
    sections: list[ResolvedSection] = []

    for section in document.sections:
        items: list[ReportItem] = []
        for block in section.blocks:
            item = _resolve_block(
                block,
                claims_by_id=claims_by_id,
                figures_by_id=figures_by_id,
                tables_by_id=tables_by_id,
                unresolved_by_id=unresolved_by_id,
                footnotes_by_id=footnotes_by_id,
                placed_figures=placed_figures,
                placed_tables=placed_tables,
            )
            items.append(item)
        sections.append(
            ResolvedSection(
                section_id=section.section_id,
                heading=section.heading,
                items=tuple(items),
            )
        )

    return ResolvedReport(
        title=document.title,
        as_of=document.snapshot.as_of,
        record_ids=document.snapshot.record_ids,
        sections=tuple(sections),
        footnotes=tuple(FootnoteItem(footnote=footnote) for footnote in document.footnotes),
        unplaced_figures=tuple(
            FigureItem(figure=figure)
            for figure in document.figures
            if figure.figure_id not in placed_figures
        ),
        unplaced_tables=tuple(
            TableItem(table=table)
            for table in document.tables
            if table.table_id not in placed_tables
        ),
    )


def _resolve_block(
    block: ReportBlock,
    *,
    claims_by_id: dict[str, ReportClaim],
    figures_by_id: dict[str, ReportFigure],
    tables_by_id: dict[str, ReportTable],
    unresolved_by_id: dict[str, UnresolvedRecord],
    footnotes_by_id: dict[str, ProvenanceFootnote],
    placed_figures: set[str],
    placed_tables: set[str],
) -> ReportItem:
    """One block, resolved into the item a renderer draws.

    Dispatched on the block's **class**, which is the discriminator the
    model declares, and every branch is one of the six kinds the model
    allows. The model resolves every id on construction, so a lookup that
    misses is a document this tree's model did not build — and it is
    refused by name rather than drawn as an empty space.
    """
    if isinstance(block, NarrativeBlock):
        return NarrativeItem(text=block.text)

    if isinstance(block, InterpretationBlock):
        return InterpretationItem(text=block.text)

    if isinstance(block, ClaimBlock):
        claim = claims_by_id.get(block.claim_id)
        if claim is None:
            raise ReportRenderError(
                f"the section places the claim {block.claim_id!r}, which the report does not carry."
            )
        footnotes: list[FootnoteItem] = []
        for footnote_id in claim.footnote_ids:
            footnote = footnotes_by_id.get(footnote_id)
            if footnote is None:
                raise ReportRenderError(
                    f"the claim {claim.claim_id!r} cites the footnote "
                    f"{footnote_id!r}, which the report does not carry."
                )
            footnotes.append(FootnoteItem(footnote=footnote))
        return ClaimItem(claim=claim, footnotes=tuple(footnotes))

    if isinstance(block, FigureBlock):
        figure = figures_by_id.get(block.figure_id)
        if figure is None:
            raise ReportRenderError(
                f"the section places the figure {block.figure_id!r}, which the "
                "report does not carry."
            )
        placed_figures.add(block.figure_id)
        return FigureItem(figure=figure)

    if isinstance(block, TableBlock):
        table = tables_by_id.get(block.table_id)
        if table is None:
            raise ReportRenderError(
                f"the section places the table {block.table_id!r}, which the report does not carry."
            )
        placed_tables.add(block.table_id)
        return TableItem(table=table)

    if isinstance(block, UnresolvedBlock):
        unresolved = unresolved_by_id.get(block.record_id)
        if unresolved is None:
            raise ReportRenderError(
                f"the section places the record {block.record_id!r}, which the "
                "report does not carry as an unresolved record."
            )
        return UnresolvedItem(unresolved=unresolved)

    raise ReportRenderError(f"the report carries a block of an unknown kind: {block!r}")


def with_interpretation_marker(lines: Sequence[str], is_interpretation: bool) -> list[str]:
    """The lines to draw, with the interpretation marker on the last of them.

    The marker is the **product's** sentence, and the renderer appends it
    *after* the escaping: the model's text is escaped because it came from
    a source, and the product's own words are constants that cannot open a
    span. Appending it here rather than composing it into the lines is what
    keeps the marker in every export spelled exactly as
    :data:`labcairn.reports.render.constants.INTERPRETATION_MARKER` spells
    it — the same string the figure's renderer uses.

    :param lines: the item's lines, already escaped by the renderer.
    :param is_interpretation: whether the item is an interpretation.
    :returns: the lines to write, with the marker appended when the item
        is an interpretation and untouched when it is not.
    """
    marked = list(lines)
    if is_interpretation:
        marked[-1] = f"{marked[-1]} {INTERPRETATION_MARKER}"
    return marked


def _record_statement(record: LedgerRecordView) -> str:
    """What a record holds, in the record's own words.

    A record states either a sentence or a quantity, and the model says
    which: a numeric record carries a value and a declared unit and no
    text, and a claim or result record carries text and no value. A
    renderer that had to choose between them would be reading a record it
    was not given.

    The number is drawn with ``repr``, which is the shortest spelling that
    reads back as the same float. That is what keeps the report's number
    the ledger's number: a renderer that rounded to two decimals would be
    stating a different quantity, and the acceptance clause compares
    numbers.
    """
    if record.text is not None:
        return record.text

    value = record.value
    unit = record.unit
    if value is None or unit is None:
        raise ReportRenderError(
            f"the record {record.record_id!r} carries neither a statement nor a "
            "quantity, so there is nothing to draw. The model refuses to build "
            "such a record."
        )
    return f"{value!r} {unit}"
