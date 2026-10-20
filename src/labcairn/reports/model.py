"""``ReportDocument`` — the report's content as data, and the bytes that name it.

LC-P1-11 owns report assembly, and the work order's requirement that
*"content verification [is] separate from formatting/rendering"* can only be
met if the report's content exists as something other than a rendered page.
So the content is a **model**: sections, claims, figures, tables and
provenance footnotes — one document that four renderers draw from, and one
document the content checks verify.

The renderers draw; they do not decide. A number in a report comes from the
model, a caption comes from the model, and a renderer's only freedom is how
it draws them. A renderer that has to compute a number to draw it is a
renderer that can disagree with the ledger, which is the failure the work
order's "content verification separate from formatting" clause exists to
prevent.

Six decisions shape the document, and each of them costs something.

**1. A claim names the record it rests on, and only a record that may be
stated as a finding may become a claim.** A ``conflicted`` or ``unsupported``
record is carried in the document as what it is — a conflict, with its reason
— and never as a report sentence that reads as a finding. This is the
condition the task breakdown lists as A3, and it is why the claim carries a
*status* rather than only a text: a document that could not say how far its
records had been checked would be a document whose sentences all read the
same way whether they were verified or not.

**2. The numbers in the document are the ledger's numbers.** The document
copies them; it does not compute them and it does not reformat them into a
different precision. The number lives in exactly one place — a claim's
record — and a numeric record may carry no text, so there is nowhere for a
rounded or re-worded version of it to sit beside the original and be
rendered in its place. Two kinds of number in the document are *not* the
ledger's, and both are bounded: a figure's manifest carries the
derivation's own output, which the manifest's own hash chain binds rather
than the ledger, and it belongs to the figure rather than to the report's
findings; and a number inside the report's own narrative prose is the
report's own sentence, which is interpretation, which ADR-0004's A10
covers and the content checks compare against the ledger.

**3. A figure carries its caption.** The caption is the model's, and a
renderer may not invent one. A figure whose caption the renderer supplies is
a figure whose wording changes with the renderer, and two exports of one
document would then say different things.

**4. A citation is a locator.** The owner decided this on 2026-10-20: the
document carries the source, the locator and the content hash, and **no
external identifier**. The source model has a slot for identifiers that
ingestion never fills and that nothing resolves, so an identifier printed as
a citation would be the *material's* claim and not the report's — which is
the fabrication the ledger's own acceptance clause refuses.

**5. The document is a frozen view at one moment, and it names that
moment.** It is not "current" the way the ledger is. A report built from a
changed ledger is a new revision, not a correction of this one, and the
staleness of a report is a fact about its receipt rather than a note the
document keeps for itself.

**6. Canonical bytes, one spelling.** The document's bytes are the
project's canonical JSON — sorted keys, no incidental whitespace, UTF-8 —
by :meth:`labcairn.core.schema.LabCairnModel.json_canonical`, the same
convention :func:`labcairn.analysis.manifest.manifest_bytes` uses. A third
spelling is not added here: the tree already has two helpers and they agree
byte for byte, which the test suite asserts against both of them.

The cost of the whole model
---------------------------
It is a second representation of the ledger's contents. The price is paid by
making it a **frozen view at one moment** rather than a live one: it names
the records it is made of, and it says when it was taken. A document that
could hold a contradiction is a document nobody can rely on, so the
cross-checks are in the model rather than in the checks that run later: a
block that names a claim the document does not carry, a claim that cites a
footnote the document does not carry, a record that is both a finding and an
unresolved conflict, and a snapshot that does not name the records the
document carries are all refused on construction.

An import note, because it is a trap rather than a detail
----------------------------------------------------------
This module imports :class:`labcairn.analysis.manifest.ReproducibilityManifest`,
because a figure's manifest is part of the report's content and not a
parallel description of it. That import runs *into*
:mod:`labcairn.reports.receipt`, which is why ``labcairn.reports.__init__``
must not import this module: the package would then import a module that
depends on the package, and which of the two finished loading would depend
on who was imported first. The receipt is the one thing in this package that
``labcairn.analysis`` already depends on, and the dependency is not
reversed here.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final, Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from labcairn.analysis.manifest import ReproducibilityManifest
from labcairn.core.schema import LabCairnModel
from labcairn.evidence.states import EvidenceKind, VerificationStatus
from labcairn.sources.locators import SourceLocator
from labcairn.sources.primitives import (
    ContentHash,
    NonEmptyText,
    StrictFloat,
    WorkspaceRelativePath,
)

__all__ = [
    "FINDING_STATUSES",
    "UNRESOLVED_STATUSES",
    "BlockKind",
    "ClaimBlock",
    "FigureBlock",
    "LedgerRecordView",
    "LedgerSnapshot",
    "NarrativeBlock",
    "ProvenanceFootnote",
    "ReportBlock",
    "ReportClaim",
    "ReportDocument",
    "ReportFigure",
    "ReportSection",
    "ReportTable",
    "TableBlock",
    "UnresolvedBlock",
    "UnresolvedRecord",
]

#: The record states a report may state as a finding.
#:
#: ``extracted`` is in it because the text was located, copied out and
#: hashed: that is something a report can stand on, and the claim carries the
#: status so a reader can see it was not confirmed by a rule. ``planned`` is
#: not in it because a record that has not been located states a
#: declaration, and a declaration with no anchor behind it is not a finding.
FINDING_STATUSES: Final[frozenset[VerificationStatus]] = frozenset(
    {
        VerificationStatus.EXTRACTED,
        VerificationStatus.VERIFIED_BY_RULE,
        VerificationStatus.USER_ATTESTED,
    }
)

#: The record states a report may carry, but never as a finding.
#:
#: ``conflicted`` because ADR-0004's rule is that neither of two disagreeing
#: readings wins by recency and the conflict is *displayed*; ``unsupported``
#: because a record nothing supports is not a statement. Both are carried in
#: :class:`UnresolvedRecord`, with the reason they are unresolved.
UNRESOLVED_STATUSES: Final[frozenset[VerificationStatus]] = frozenset(
    {
        VerificationStatus.CONFLICTED,
        VerificationStatus.UNSUPPORTED,
    }
)


class LedgerRecordView(LabCairnModel):
    """The ledger record a report statement rests on, as the report needs it.

    A **projection**, not the record: the report carries the fields a reader
    and a checker need, and the ledger keeps the whole record. The
    alternative — embedding
    :class:`~labcairn.evidence.record.EvidenceRecord` — would make the
    document a copy of the ledger with its own staleness, and a report whose
    record it could not check would be a report nobody could trust.

    The record's own cross-type rule is reproduced here because it is the
    rule that keeps a number and a sentence apart: a **numeric** record
    carries a value and a declared unit and no text, and a **claim** or
    **result** record carries text and no value, unit or tolerance. A
    numeric record that could carry text would have somewhere for a
    re-worded, re-rounded number to sit beside the one the ledger holds.
    """

    #: The ledger's own id for the record. The claim names it; nothing here
    #: resolves it.
    record_id: NonEmptyText
    record_kind: EvidenceKind
    #: The statement, for a ``claim`` or ``result`` record. ``None`` for a
    #: numeric one, out loud, so that a sentence cannot ride along on a
    #: number unnoticed.
    text: NonEmptyText | None = None
    #: The compared quantity, for a numeric record. Copied from the record;
    #: never computed and never re-rounded. See the module docstring.
    value: StrictFloat | None = None
    #: The **declared** unit, for a numeric record. Never inferred, and never
    #: ``None``: a dimensionless quantity says so.
    unit: NonEmptyText | None = None
    #: How far the record has been through the six-state machine. Carried so
    #: that the report can say which of its sentences were checked.
    status: VerificationStatus
    #: Ids of the source anchors the record is bound to. A claim with no
    #: anchor is a claim no reader can check.
    anchor_ids: tuple[NonEmptyText, ...] = ()
    #: The source's content hash as it was read. Compared, never refreshed.
    source_content_hash: ContentHash | None = None

    @model_validator(mode="after")
    def _the_kind_decides_which_fields_mean_anything(self) -> Self:
        if self.record_kind is EvidenceKind.NUMERIC:
            if self.text is not None:
                raise ValueError(
                    "a numeric record view may not carry text. The value and its "
                    "declared unit are the record; a sentence alongside them is a "
                    "second claim riding on a number, and the report would have "
                    "two things to say about one quantity."
                )
            if self.value is None:
                raise ValueError(
                    "a numeric record view must carry a value. There is no quantity to state."
                )
            if self.unit is None:
                raise ValueError(
                    "a numeric record view must declare its unit. The unit is "
                    "declared, never inferred; a dimensionless quantity writes "
                    "'dimensionless' rather than leaving this null."
                )
            return self

        if self.text is None:
            raise ValueError(
                f"a {self.record_kind.value} record view must carry the text of the "
                "statement. A record with nothing stated attests to nothing."
            )
        for field_name, value in (
            ("value", self.value),
            ("unit", self.unit),
        ):
            if value is not None:
                raise ValueError(
                    f"a {self.record_kind.value} record view may not carry "
                    f"{field_name!r}; that field belongs to a numeric record. A "
                    "number attached to a sentence is a second record that no "
                    "check will ever look at."
                )
        return self


class ProvenanceFootnote(LabCairnModel):
    """One citation: what the report points at, and which bytes it pointed at.

    A **locator**, in the sense ADR-0004 A1 gives the word: a re-derivable
    address, not a display string. The source's own identifier is not here,
    and deliberately so — the owner decided on 2026-10-20 that a report cites
    locators only, because an identifier in the source model is a slot that
    ingestion never fills and that nothing in the tree resolves. An
    identifier printed as a citation would be the material's claim and not
    the report's. ``source_id`` is not that kind of identifier: it is the
    ledger's own row id, and it is the thing a reader needs in order to look
    the source up.
    """

    footnote_id: NonEmptyText
    #: The ledger's id for the source the citation points into.
    source_id: NonEmptyText
    #: Where in the source. The structured address, never a rendered one.
    locator: SourceLocator
    #: The source's content hash as it was read. A citation whose bytes have
    #: moved is a citation nobody can check, and the hash is what makes the
    #: drift visible.
    content_sha256: ContentHash


class ReportClaim(LabCairnModel):
    """One statement the report makes, and the ledger record it rests on.

    The record is a member of the claim, not a reference to one, because a
    report has to be readable on its own: a sentence with a footnote but no
    statement of what it rests on is a sentence whose authority is invisible.
    What the document does **not** do is resolve the record — that is the
    ledger's job — and this is a view, frozen at the moment the document
    names.
    """

    claim_id: NonEmptyText
    #: The record this claim rests on, in the form the report needs.
    record: LedgerRecordView
    #: The citations that show where the record came from. At least one: a
    #: finding with no locator is a finding a reader cannot check.
    footnote_ids: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def _the_record_may_be_stated_as_a_finding(self) -> Self:
        if self.record.status not in FINDING_STATUSES:
            raise ValueError(
                f"a claim may not rest on a {self.record.status.value!r} record. A "
                "record that was never located states a declaration, and a record "
                "that is conflicted or unsupported does not stand as a statement: "
                "ADR-0004's rule is that neither of two disagreeing readings wins "
                "by recency and the conflict is displayed instead. Carry the "
                f"record in the document's unresolved records with its reason "
                f"({self.record.status.value!r} is one of "
                f"{sorted(status.value for status in UNRESOLVED_STATUSES)})."
            )
        return self

    @model_validator(mode="after")
    def _the_record_is_traceable_to_a_source(self) -> Self:
        if not self.record.anchor_ids:
            raise ValueError(
                f"the record {self.record.record_id!r} has no anchor, so the claim "
                "cannot be traced to a source. A claim no reader can check is not "
                "a claim."
            )
        if self.record.source_content_hash is None:
            raise ValueError(
                f"the record {self.record.record_id!r} carries no source content "
                "hash, so the claim is not bound to the bytes it was read from."
            )
        return self

    @model_validator(mode="after")
    def _a_claim_cites_something(self) -> Self:
        if not self.footnote_ids:
            raise ValueError(
                f"the claim {self.claim_id!r} cites nothing. A statement in a "
                "report is shown with where it came from, and the citation is a "
                "locator rather than a name."
            )
        return self


class UnresolvedRecord(LabCairnModel):
    """A record the report carries as what it is: a conflict, or no support.

    The counterpart to :class:`ReportClaim`. A record in one of these states
    is not a finding, so it is not stated as one; it is *disclosed*, with the
    reason it could not be resolved. A disclosure nobody can act on is
    decoration, so the reason is required and may not be blank.
    """

    #: The record, in the same form a claim carries it.
    record: LedgerRecordView
    #: Why the record is unresolved: what the conflict was, or what was
    #: missing. Never blank.
    reason: NonEmptyText

    @model_validator(mode="after")
    def _the_record_is_one_of_the_unresolved_states(self) -> Self:
        if self.record.status not in UNRESOLVED_STATUSES:
            raise ValueError(
                f"a record in state {self.record.status.value!r} is not an "
                "unresolved record. A record that may be stated as a finding is "
                "a claim; a record that is neither is a record the report does "
                f"not carry. The unresolved states are "
                f"{sorted(status.value for status in UNRESOLVED_STATUSES)}."
            )
        return self


class ReportFigure(LabCairnModel):
    """One figure the report shows, and the caption it is shown under.

    The caption is required and may not be blank, because a renderer that
    has to invent one invents a different one for every format — and then
    the four exports of one document stop saying the same thing.

    The manifest is part of the figure, not a note about it: it is what says
    which bytes were computed from which inputs, and a report that carried
    the picture without the derivation would be asking the reader to trust a
    number they cannot trace.
    """

    figure_id: NonEmptyText
    #: Where the figure's bytes are, workspace-relative and canonical.
    relative_path: WorkspaceRelativePath
    #: The hash of those bytes. Compared, never refreshed.
    content_sha256: ContentHash
    #: The caption, in the model's words. A renderer may not invent one.
    caption: NonEmptyText
    #: The manifest that describes how the figure was made.
    manifest: ReproducibilityManifest


class ReportTable(LabCairnModel):
    """One table the report includes.

    A fact about a file rather than a copy of it: the bytes are in the
    workspace, and the report says which bytes. The table's own heading is
    part of the table artefact rather than of the report, which is why a
    table carries no caption here — the same reason a figure's caption is
    required and a table's is not is that a figure is drawn into the report
    and a table is included in it.
    """

    table_id: NonEmptyText
    relative_path: WorkspaceRelativePath
    content_sha256: ContentHash


class BlockKind(StrEnum):
    """What a block of a section is.

    Closed, because a block that could be several things at once would be
    drawn several ways. The kinds are the report's own two voices — the
    narrative it writes, and the findings it states — plus the three things
    it places.
    """

    #: The report's own words. Its interpretation, and never a finding:
    #: nothing here rests on a ledger record.
    NARRATIVE = "narrative"
    #: A statement that rests on a ledger record.
    CLAIM = "claim"
    #: A figure, placed under its caption.
    FIGURE = "figure"
    #: A table, placed.
    TABLE = "table"
    #: A record the report discloses as unresolved.
    UNRESOLVED = "unresolved"


class NarrativeBlock(LabCairnModel):
    """A paragraph of the report's own prose.

    The report's interpretation, and the only place it may appear. A
    finding is a claim, and a claim rests on a record; a paragraph rests on
    nothing but the report's author, and the renderers mark it as
    interpretation that no machine verified.
    """

    block_kind: Literal[BlockKind.NARRATIVE] = BlockKind.NARRATIVE
    text: NonEmptyText


class ClaimBlock(LabCairnModel):
    """A placement of one of the report's claims."""

    block_kind: Literal[BlockKind.CLAIM] = BlockKind.CLAIM
    claim_id: NonEmptyText


class FigureBlock(LabCairnModel):
    """A placement of one of the report's figures."""

    block_kind: Literal[BlockKind.FIGURE] = BlockKind.FIGURE
    figure_id: NonEmptyText


class TableBlock(LabCairnModel):
    """A placement of one of the report's tables."""

    block_kind: Literal[BlockKind.TABLE] = BlockKind.TABLE
    table_id: NonEmptyText


class UnresolvedBlock(LabCairnModel):
    """A placement of one of the report's unresolved records.

    The record is disclosed rather than stated, and the kind says so: a
    renderer that drew this block as it drew a claim block would be stating
    a conflict as a finding.
    """

    block_kind: Literal[BlockKind.UNRESOLVED] = BlockKind.UNRESOLVED
    record_id: NonEmptyText


#: The block union, discriminated on ``block_kind``.
ReportBlock = Annotated[
    NarrativeBlock | ClaimBlock | FigureBlock | TableBlock | UnresolvedBlock,
    Field(discriminator="block_kind"),
]


class ReportSection(LabCairnModel):
    """One section of the report: a heading and what is under it.

    The blocks are a discriminated union rather than one wide model with
    optional fields, for the reason the locators are: a single model whose
    fields are all optional cannot say which combination of them makes
    sense, and every new field would silently widen what a block may be.
    """

    section_id: NonEmptyText
    heading: NonEmptyText
    #: What is under the heading. At least one: a heading with nothing
    #: under it is a heading the reader cannot do anything with.
    blocks: Annotated[tuple[ReportBlock, ...], Field(min_length=1)]


class LedgerSnapshot(LabCairnModel):
    """The moment the document is a view of, and the records it is made of.

    A report is not the ledger. It is a view of a set of ledger records,
    frozen at a moment, and the document says which moment and which
    records. Without that, a report would read as current the way the
    ledger is, and a reader would have no way to know that the ledger had
    moved on since.

    The record ids are **sorted and without repeats**, so two views of the
    same set of records have the same extent however they were gathered.
    """

    #: When the view was taken.
    as_of: AwareDatetime
    #: The records the view is made of, by id: sorted, and without repeats.
    record_ids: tuple[NonEmptyText, ...] = ()

    @model_validator(mode="after")
    def _the_records_are_canonical(self) -> Self:
        if len(set(self.record_ids)) != len(self.record_ids):
            raise ValueError(
                f"the snapshot names a record twice: {list(self.record_ids)}. One "
                "record named twice is one record, and listing it twice makes "
                "'which records is this a view of' answerable two ways."
            )
        if list(self.record_ids) != sorted(self.record_ids):
            raise ValueError(
                f"the snapshot's record ids are not in sorted order: "
                f"{list(self.record_ids)}. Sort on write rather than normalising "
                "on read — a view that renders two ways cannot be compared."
            )
        return self


class ReportDocument(LabCairnModel):
    """The report: its sections, its claims, its figures, its tables, its
    provenance, and the moment it is a view of.

    Frozen, because a report that could be edited in place would be a
    document whose bytes mean different things at different times, and the
    whole point of the canonical form is that a report can be *hashed*.
    A change to a report is a new document.

    The cross-checks below are the point of the model rather than
    decoration. A block that names a claim the document does not carry, a
    claim that cites a footnote the document does not carry, a claim that is
    never placed, a record that is both a finding and an unresolved
    conflict, and a snapshot that does not name the records the document
    carries are all contradictions, and a document that could hold one is a
    document nobody can rely on.
    """

    title: NonEmptyText
    #: The moment, and the records. See :class:`LedgerSnapshot`.
    snapshot: LedgerSnapshot
    #: The report's sections, in the order they are read.
    sections: tuple[ReportSection, ...] = ()
    #: The findings. Each names the record it rests on.
    claims: tuple[ReportClaim, ...] = ()
    #: The figures, each with its caption.
    figures: tuple[ReportFigure, ...] = ()
    #: The tables.
    tables: tuple[ReportTable, ...] = ()
    #: The citations. Each is a locator, and no external identifier.
    footnotes: tuple[ProvenanceFootnote, ...] = ()
    #: The records the report discloses rather than states.
    unresolved_records: tuple[UnresolvedRecord, ...] = ()

    @model_validator(mode="after")
    def _a_report_has_a_section(self) -> Self:
        if not self.sections:
            raise ValueError(
                "the report has no section. A report is a sequence of sections, "
                "and a document with none carries nothing for a renderer to draw "
                "or for a check to verify."
            )
        return self

    @model_validator(mode="after")
    def _the_ids_are_unique(self) -> Self:
        for label, values in (
            ("section", tuple(section.section_id for section in self.sections)),
            ("claim", tuple(claim.claim_id for claim in self.claims)),
            ("figure", tuple(figure.figure_id for figure in self.figures)),
            ("table", tuple(table.table_id for table in self.tables)),
            ("footnote", tuple(footnote.footnote_id for footnote in self.footnotes)),
        ):
            repeated = _repeated(values)
            if repeated:
                raise ValueError(
                    f"the report names the same {label} twice: {repeated}. One "
                    f"{label} named twice is one {label}, and two rows for it make "
                    f"'which {label} is this' answerable two ways."
                )
        return self

    @model_validator(mode="after")
    def _every_reference_resolves(self) -> Self:
        claim_ids = {claim.claim_id for claim in self.claims}
        figure_ids = {figure.figure_id for figure in self.figures}
        table_ids = {table.table_id for table in self.tables}
        footnote_ids = {footnote.footnote_id for footnote in self.footnotes}
        unresolved_ids = {record.record.record_id for record in self.unresolved_records}

        for section in self.sections:
            for block in section.blocks:
                match block:
                    case ClaimBlock(claim_id=claim_id):
                        if claim_id not in claim_ids:
                            raise ValueError(
                                f"the section {section.section_id!r} places the claim "
                                f"{claim_id!r}, which the report does not carry. A "
                                "block that points at nothing is a hole in the "
                                "document, and a renderer would draw it as an empty "
                                "space."
                            )
                    case FigureBlock(figure_id=figure_id):
                        if figure_id not in figure_ids:
                            raise ValueError(
                                f"the section {section.section_id!r} places the "
                                f"figure {figure_id!r}, which the report does not "
                                "carry."
                            )
                    case TableBlock(table_id=table_id):
                        if table_id not in table_ids:
                            raise ValueError(
                                f"the section {section.section_id!r} places the "
                                f"table {table_id!r}, which the report does not "
                                "carry."
                            )
                    case UnresolvedBlock(record_id=record_id):
                        if record_id not in unresolved_ids:
                            raise ValueError(
                                f"the section {section.section_id!r} places the "
                                f"record {record_id!r}, which the report does not "
                                "carry as an unresolved record."
                            )
                    case NarrativeBlock():
                        pass

        for claim in self.claims:
            for footnote_id in claim.footnote_ids:
                if footnote_id not in footnote_ids:
                    raise ValueError(
                        f"the claim {claim.claim_id!r} cites the footnote "
                        f"{footnote_id!r}, which the report does not carry."
                    )
        return self

    @model_validator(mode="after")
    def _every_finding_is_placed(self) -> Self:
        placed_claims: set[str] = set()
        placed_records: set[str] = set()
        for section in self.sections:
            for block in section.blocks:
                match block:
                    case ClaimBlock(claim_id=claim_id):
                        placed_claims.add(claim_id)
                    case UnresolvedBlock(record_id=record_id):
                        placed_records.add(record_id)
                    case FigureBlock() | TableBlock() | NarrativeBlock():
                        pass

        for claim in self.claims:
            if claim.claim_id not in placed_claims:
                raise ValueError(
                    f"the claim {claim.claim_id!r} is in the report but in no "
                    "section. A finding the report does not place is a finding "
                    "nobody reads, and the checks that verify the report against "
                    "the ledger would be verifying a statement that is not in it."
                )
        for record in self.unresolved_records:
            if record.record.record_id not in placed_records:
                raise ValueError(
                    f"the record {record.record.record_id!r} is disclosed by the "
                    "report but placed in no section. A conflict nobody is shown "
                    "is a conflict the report has hidden."
                )
        return self

    @model_validator(mode="after")
    def _a_record_is_carried_once(self) -> Self:
        claim_records = {claim.record.record_id for claim in self.claims}
        unresolved_records = {record.record.record_id for record in self.unresolved_records}
        both = sorted(claim_records & unresolved_records)
        if both:
            raise ValueError(
                f"the record(s) {both} are carried more than once. One record is "
                "one statement in a report: a record may be stated as a finding "
                "or disclosed as unresolved, and a document that carried it both "
                "ways would be showing the same record as a result and as a "
                "conflict, in the space of one page."
            )
        repeated_claims = _repeated(tuple(claim.record.record_id for claim in self.claims))
        if repeated_claims:
            raise ValueError(
                f"the record(s) {repeated_claims} back more than one claim. A "
                "record states one thing; a report that states it twice says it "
                "twice, and the second statement is the one no check would "
                "notice. Place the same claim in two sections instead."
            )
        return self

    @model_validator(mode="after")
    def _the_snapshot_names_the_records_the_report_carries(self) -> Self:
        carried = {claim.record.record_id for claim in self.claims}
        carried |= {record.record.record_id for record in self.unresolved_records}
        named = set(self.snapshot.record_ids)
        missing = sorted(carried - named)
        if missing:
            raise ValueError(
                f"the report carries the record(s) {missing}, which its snapshot "
                "does not name. The snapshot is the report's statement of which "
                "records it is a view of, and a record it does not name is a "
                "record the reader cannot check the view against."
            )
        unplaced = sorted(named - carried)
        if unplaced:
            raise ValueError(
                f"the snapshot names the record(s) {unplaced}, which the report "
                "does not carry. The snapshot names the extent of the view, and a "
                "record it names that the report does not show makes the view's "
                "extent unanswerable."
            )
        return self

    @model_validator(mode="after")
    def _a_citation_binds_the_record_to_its_bytes(self) -> Self:
        by_id = {footnote.footnote_id: footnote for footnote in self.footnotes}
        for claim in self.claims:
            record_hash = claim.record.source_content_hash
            for footnote_id in claim.footnote_ids:
                footnote = by_id[footnote_id]
                if footnote.content_sha256 != record_hash:
                    raise ValueError(
                        f"the claim {claim.claim_id!r} rests on a record read from "
                        f"bytes that hash to {record_hash!r}, but the citation "
                        f"{footnote_id!r} points at bytes that hash to "
                        f"{footnote.content_sha256!r}. A citation that names other "
                        "bytes than the record was read from is a citation to "
                        "something the claim does not rest on."
                    )
        return self

    def canonical_bytes(self) -> bytes:
        """The document's bytes: the canonical JSON, encoded as UTF-8.

        These are the bytes a receipt's ``content_sha256`` is taken over and
        the bytes two exports of one report are compared by. UTF-8 rather
        than the default escaping, because a caption written in the author's
        own characters should be the same document after it is hashed as it
        was before.
        """
        return self.json_canonical().encode("utf-8")


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
