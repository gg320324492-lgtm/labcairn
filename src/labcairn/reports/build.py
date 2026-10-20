"""``build_report_document`` — what the task has, turned into one report document.

LC-P1-11 built the report's *classes* (T00), its four renderers (T01), its
artefact manifest (T02), its revisions (T03) and its content checks (T04),
and between them they left one thing out: **nothing assembled a
:class:`~labcairn.reports.model.ReportDocument` out of what a task actually
has.** T00 built the document's shape and the rules it refuses to break;
this module is what puts a task's records into that shape.

The builder is a **pure function over its arguments**. It reads no store and
opens no file: the records, the artefacts, the sources and the anchors arrive
as arguments and the caller gathers them. That is a layering decision rather
than an accident — :mod:`labcairn.reports` sits above the store, and the
repository has a guard that fails when a module outside the application layer
reaches past it. A builder that read the ledger itself would be a second way
in, and the layer above would lose the property it exists to have.

The routing, and what each decision costs
-----------------------------------------
**A record that may be stated becomes a claim; a record that may not becomes
a disclosure.** The model's own two sets decide it —
:data:`~labcairn.reports.model.FINDING_STATUSES` and
:data:`~labcairn.reports.model.UNRESOLVED_STATUSES` — and the builder adds
nothing to them. That is the whole of ADR-0004 A3 and A5: a ``conflicted``
record is *displayed* rather than stated, and neither of two disagreeing
readings wins by recency.

**A record in the ``planned`` state is not carried at all.** The model says
it outright — *"a record that is neither is a record the report does not
carry"* — and a planned record is a declaration with nothing behind it.
The snapshot does not name it either, because the snapshot names exactly the
records the report carries, and a record the report does not carry is not
part of the view's extent.

**A record that has been superseded is not carried.** The ledger keeps the
old row so that the history of a claim stays auditable, and a report that
stated both the old record and the one that replaced it would say the same
thing twice. Supersession is within one task (the store refuses a
replacement from another task), so the record that replaced it is among the
records the caller gathered.

**A record that may be stated but cannot be cited is refused.** This is the
decision the report's own model forces and the builder cannot avoid: the
model refuses a claim with no citation, so a finding-status record whose
anchors do not resolve cannot become a claim, and the model refuses a
disclosure of anything but a conflicted or unsupported record. The three
remaining answers are all bad, and they are bad in the same way — the report
would carry less than the ledger holds:

* **dropping it** would leave a verified finding out of a report whose
  snapshot claims to be a view of the records, and a reader would have no
  way to know it was there;
* **disclosing it** would state it as a conflict, which is a falsehood of
  the same kind the model exists to prevent;
* **refusing the build** says what is wrong and leaves the ledger alone.

So the builder refuses, and says which record and which anchor. The refusals
here are *loud* on purpose: they are the builder's version of the model's
own, and a caller that hits one learns that the ledger holds something the
report cannot honestly say.

**The reason a disclosure carries is composed from the ledger, not from the
builder.** The ledger holds a *state*, not a sentence, and the model refuses
a disclosure whose reason is blank — so the reason has to be written
somewhere. It is written here, out of the record's own facts: the state it
is in, and the entries of its verification log that say why. A check that
failed is named with its check, its checker and its detail, quoted from the
log rather than paraphrased; a record with no anchor is said to have none.
Nothing in the reason is the builder's opinion, because an interpretation is
never machine-verified (ADR-0004's A10) and a builder that composed one
would be putting words in the researcher's mouth.

**The builder writes no prose.** It emits no narrative block, because a
narrative describes what the material is, what was done and what the report
does not cover, and nothing in the ledger holds those sentences. It *does*
carry the **figure's own interpretation**, because that one the ledger does
hold: the chart recipe separates the caption from the interpretation for
exactly the reason the model does, and the recipe is a file the manifest
already binds by path and hash. Those are the researcher's own words, so the
builder carries them rather than writing them — and the renderers mark them,
exactly as the figure's renderer marks the figure's interpretation.

What the builder will not do
----------------------------
It will not state a record the ledger cannot support, and it will not write
an interpretation. Both are refusals rather than best efforts, and both cost
something: a task whose records cannot be cited produces **no report**,
which is a worse outcome for the user than a report with a hole in it, and is
the right one anyway. A report with a hole in it is a report nobody can rely
on, and the whole point of the model is that a document cannot hold a
contradiction.

What the caller has to bring
----------------------------
Four of the arguments are things only the caller can have, and each of them
is a refusal rather than a default:

* **the anchors**, by id, because a record carries anchor *ids* and the
  citation needs the address behind them;
* **the manifests**, by the id of the artefact that holds them, because a
  figure's reproducibility manifest is written beside the figure as its own
  artefact and the builder finds it through the figure's own chain and reads
  it back from there — the figure's manifest is checked against the bytes
  that artefact recorded, so a manifest that is not the artefact's own is
  refused;
* **the captions**, by the figure artefact's id, because a caption is the
  author's words and the model forbids a renderer from inventing one. A
  figure with no caption supplied is refused: the alternative is a caption
  composed from the file name, which says nothing about what is plotted;
* **the interpretations**, by the figure artefact's id, for the same reason
  and because the recipe keeps them apart: a caption says what is plotted and
  an interpretation says what it means, and marking the second and not the
  first is the whole of ADR-0004's A10 for a figure. An interpretation is
  **optional** — a recipe with none contributes no block at all, because an
  absent interpretation and an empty one are different facts and only the
  first is true.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from labcairn.analysis.manifest import ReproducibilityManifest, manifest_bytes
from labcairn.evidence.record import EvidenceRecord
from labcairn.evidence.states import CheckOutcome, VerificationStatus
from labcairn.reports.model import (
    FINDING_STATUSES,
    UNRESOLVED_STATUSES,
    ClaimBlock,
    FigureBlock,
    InterpretationBlock,
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
from labcairn.reports.receipt import (
    ArtifactKind,
    ArtifactReceipt,
    DerivationTargetKind,
)
from labcairn.sources.source import Source, SourceAnchor, SourceReadability

__all__ = [
    "FIGURES_HEADING",
    "FIGURES_SECTION_ID",
    "FINDINGS_HEADING",
    "FINDINGS_SECTION_ID",
    "TABLES_HEADING",
    "TABLES_SECTION_ID",
    "UNRESOLVED_HEADING",
    "UNRESOLVED_SECTION_ID",
    "ReportBuildRefusedError",
    "build_report_document",
]

#: The section ids the builder uses, and the headings under them.
#:
#: Four sections, one for each kind of thing a report carries, and no
#: others. The layout is grouped **by kind** rather than by record or by
#: topic, and the reason is that the model's rules are about kinds: a
#: disclosure may not be stated as a finding, and a claim may not be restated
#: as an interpretation. A layout that mixed kinds would have to be argued
#: for; a layout that separates them makes the mixing impossible.
FINDINGS_SECTION_ID: Final[str] = "findings"
FIGURES_SECTION_ID: Final[str] = "figures"
TABLES_SECTION_ID: Final[str] = "tables"
UNRESOLVED_SECTION_ID: Final[str] = "unresolved"

#: The heading of the section the claims are placed in.
FINDINGS_HEADING: Final[str] = "Findings"
#: The heading of the section the figures are placed in.
FIGURES_HEADING: Final[str] = "Figures"
#: The heading of the section the tables are placed in.
TABLES_HEADING: Final[str] = "Tables"
#: The heading of the section the disclosed records are placed in.
UNRESOLVED_HEADING: Final[str] = "Unresolved records"


class ReportBuildRefusedError(RuntimeError):
    """The report could not be built, and saying why is the whole answer.

    A refusal rather than a report with a hole in it. The alternatives are
    worse: a document that quietly omits a verified finding, or one that
    states a conflict as a result, is a document nobody can rely on, and
    the model's own rules exist to prevent exactly that. The project's rule
    is that an unknown is never a zero and a missing thing is never a blank
    -- here it is a refusal.
    """


@dataclass(frozen=True, slots=True)
class _FigurePart:
    """A figure, and the interpretation that goes with it when it has one.

    The two are kept apart because the recipe keeps them apart and the
    model does too: a caption says what is plotted and an interpretation
    says what it means, and marking the second while leaving the first
    alone is the whole of ADR-0004's A10 for a figure. An absent
    interpretation is ``None`` and not an empty string, because a recipe
    with no interpretation and one with a blank one are different facts
    and only the first of them is true.
    """

    figure: ReportFigure
    interpretation: str | None


def build_report_document(
    *,
    title: str,
    as_of: datetime,
    records: Sequence[EvidenceRecord],
    artifacts: Sequence[ArtifactReceipt],
    sources: Sequence[Source],
    anchors: Mapping[str, SourceAnchor],
    manifests: Mapping[str, ReproducibilityManifest],
    captions: Mapping[str, str],
    interpretations: Mapping[str, str] | None = None,
) -> ReportDocument:
    """Build the report document for one task, from what the task has.

    :param title: the report's title. The caller's words: a title is
        content, and the builder does not write content.
    :param as_of: the moment the document is a view of. The document is a
        frozen view and not a live one, so it names the moment rather than
        being "current" the way the ledger is.
    :param records: the task's evidence records, in any order. The builder
        sorts what it carries, so two callers that gather the same records
        produce the same document and therefore the same bytes.
    :param artifacts: the task's artefact receipts. The figures and the
        tables come from here, and the newest revision of each artefact is
        the one that is carried.
    :param sources: the sources the task is bound to. A citation may only
        point into one of them, and only into one that can be read.
    :param anchors: the anchors, by id. A record carries anchor *ids*, and
        a citation needs the address behind them.
    :param manifests: the reproducibility manifests, by the id of the
        artefact that holds them. The builder finds a figure's manifest
        through the figure's own chain and reads it back from there.
    :param captions: the figure captions, by the figure artefact's id. The
        author's words; the builder refuses a figure whose caption it was
        not given.
    :param interpretations: the figures' own interpretations, by the figure
        artefact's id — the recipe's ``interpretation`` field, which is
        separate from the caption and optional. A figure with one carries it
        as an :class:`~labcairn.reports.model.InterpretationBlock` beside the
        figure, which the renderers mark as never machine-verified. A figure
        with none carries no block at all.
    :returns: the document, which the model has checked against its own
        rules by the time it is returned.
    :raises ReportBuildRefusedError: when the facts do not support a
        document — a record that may be stated but cannot be cited, a
        figure whose manifest is not its own, a figure with no caption, an
        interpretation that names no figure, or a task with nothing in it to
        report.
    """
    source_by_id = {source.source_id: source for source in sources}
    artifact_by_id = {receipt.receipt_id: receipt for receipt in artifacts}
    if len(artifact_by_id) != len(artifacts):
        raise ReportBuildRefusedError(
            "two artefacts share a receipt id, so 'which artefact is this' would "
            "have two answers. The report's parts are named by id and an id that "
            "means two artefacts makes the manifest of one of them describe the "
            "other."
        )

    readings: Mapping[str, str] = interpretations or {}
    _refuse_readings_that_name_no_figure(
        readings,
        artifact_by_id=artifact_by_id,
        label="interpretation",
    )
    _refuse_readings_that_name_no_figure(
        captions,
        artifact_by_id=artifact_by_id,
        label="caption",
    )

    claims: list[ReportClaim] = []
    disclosures: list[UnresolvedRecord] = []
    footnotes: dict[str, ProvenanceFootnote] = {}

    for record in records:
        if record.superseded_by is not None:
            continue
        if record.status in FINDING_STATUSES:
            claim, cited = _claim_for(record, anchors=anchors, sources=source_by_id)
            claims.append(claim)
            for footnote in cited:
                footnotes[footnote.footnote_id] = footnote
        elif record.status in UNRESOLVED_STATUSES:
            disclosures.append(
                UnresolvedRecord(record=_view(record), reason=_disclosure_reason(record))
            )
        elif record.status is VerificationStatus.PLANNED:
            continue
        else:
            raise ReportBuildRefusedError(
                f"the record {record.evidence_id!r} is in state {record.status.value!r}, "
                "which is neither a state a report may state nor one it may disclose. "
                "The six states are closed, so this is a state this build does not "
                "know how to route, and dropping the record would leave the "
                "snapshot claiming an extent the report does not have."
            )

    figure_parts, tables = _parts_from_artifacts(
        artifacts,
        artifact_by_id=artifact_by_id,
        manifests=manifests,
        captions=captions,
        interpretations=readings,
    )

    if not claims and not disclosures and not figure_parts and not tables:
        raise ReportBuildRefusedError(
            "the task has nothing a report may carry: no record that may be stated, "
            "no record that may be disclosed, no figure and no table. The report "
            "model refuses a document with no section, and a section with nothing "
            "under its heading is a heading the reader cannot do anything with. A "
            "report that says 'there is nothing here' is a sentence the builder is "
            "not allowed to write."
        )

    # Sorted here rather than at the point of use, because the section that
    # places the blocks and the collection the document carries have to be in
    # the same order: two gatherers of one task must produce the same bytes,
    # and the bytes include both.
    claims = sorted(claims, key=lambda claim: claim.claim_id)
    disclosures = sorted(disclosures, key=lambda record: record.record.record_id)
    sections = _sections(
        claims=claims,
        figures=figure_parts,
        tables=tables,
        disclosures=disclosures,
    )
    carried = sorted(
        {claim.record.record_id for claim in claims}
        | {record.record.record_id for record in disclosures}
    )

    try:
        return ReportDocument(
            title=title,
            snapshot=LedgerSnapshot(as_of=as_of, record_ids=tuple(carried)),
            sections=sections,
            claims=tuple(claims),
            figures=tuple(part.figure for part in figure_parts),
            tables=tables,
            footnotes=tuple(sorted(footnotes.values(), key=lambda note: note.footnote_id)),
            unresolved_records=tuple(disclosures),
        )
    except ValueError as error:
        raise ReportBuildRefusedError(
            f"the report could not be built from these facts: {error}. A document "
            "that contradicts itself is not a document with a blank in it -- it is "
            "a document whose parts disagree, and a reader would have no way to "
            "tell which part to believe."
        ) from error


# --------------------------------------------------------------------------- #
# the records
# --------------------------------------------------------------------------- #


def _view(record: EvidenceRecord) -> LedgerRecordView:
    """The record, as the report needs it.

    A **projection**, and every field is the record's own: the value at the
    ledger's precision, the declared unit, the kind, the text, the status and
    the anchors. Nothing is recomputed and nothing is re-rounded — a report
    that says 4.25 where the ledger says 4.253 is stating a different
    quantity, and a number that was re-rounded on the way into the report
    would be a number no check would ever compare.
    """
    return LedgerRecordView(
        record_id=record.evidence_id,
        record_kind=record.kind,
        text=record.text,
        value=record.value,
        unit=record.unit,
        status=record.status,
        anchor_ids=record.anchor_ids,
        source_content_hash=record.source_content_hash,
    )


def _claim_for(
    record: EvidenceRecord,
    *,
    anchors: Mapping[str, SourceAnchor],
    sources: Mapping[str, Source],
) -> tuple[ReportClaim, tuple[ProvenanceFootnote, ...]]:
    """The claim the record becomes, and the citations it rests on.

    Every anchor of the record is cited, and each citation is checked against
    the record before it is written: the anchor must be one the ledger holds,
    it must point into a source the report carries, that source must be
    readable, and it must be bound to the very bytes the record was read
    from. The last of those is the rule that makes a citation *this* record's
    citation rather than some other record's.
    """
    source_hash = record.source_content_hash
    if source_hash is None:
        raise ReportBuildRefusedError(
            f"the record {record.evidence_id!r} is in state {record.status.value!r} "
            "but carries no source content hash, so it is not bound to the bytes it "
            "was read from. The ledger's own rule is that a record past 'planned' "
            "must be located, and a claim that is not bound to bytes cannot be "
            "cited."
        )
    if not record.anchor_ids:
        raise ReportBuildRefusedError(
            f"the record {record.evidence_id!r} is in state {record.status.value!r} "
            "but names no anchor, so it has no address and no citation. A finding a "
            "reader cannot check is not a finding the report may state."
        )

    cited: list[ProvenanceFootnote] = []
    for anchor_id in record.anchor_ids:
        cited.append(
            _footnote_for(
                record,
                anchor_id,
                source_hash=source_hash,
                anchors=anchors,
                sources=sources,
            )
        )

    claim = ReportClaim(
        claim_id=f"clm-{record.evidence_id}",
        record=_view(record),
        footnote_ids=tuple(footnote.footnote_id for footnote in cited),
    )
    return claim, tuple(cited)


def _footnote_for(
    record: EvidenceRecord,
    anchor_id: str,
    *,
    source_hash: str,
    anchors: Mapping[str, SourceAnchor],
    sources: Mapping[str, Source],
) -> ProvenanceFootnote:
    """One citation: a source, a locator, and the bytes it pointed at.

    The hash is the **record's** ``source_content_hash`` — the bytes the
    claim was read from — and the address is the anchor's own locator. The
    model's rule is that a citation must name the same bytes the record was
    read from, and the anchor's ``bound_source_sha256`` is what says whether
    it does.
    """
    anchor = anchors.get(anchor_id)
    if anchor is None:
        raise ReportBuildRefusedError(
            f"the record {record.evidence_id!r} names the anchor {anchor_id!r}, which "
            "the ledger does not hold. The record's state says it may be stated as a "
            "finding, and a finding that cannot cite an address is a claim no "
            "reader can check — so the report cannot be built rather than built "
            "without it."
        )

    source = sources.get(anchor.source_id)
    if source is None:
        raise ReportBuildRefusedError(
            f"the anchor {anchor_id!r} of the record {record.evidence_id!r} points at "
            f"the source {anchor.source_id!r}, which the report does not carry. A "
            "citation into material the report does not have is a citation the "
            "reader cannot open."
        )

    if source.readability is not SourceReadability.READABLE:
        raise ReportBuildRefusedError(
            f"the source {source.source_id!r} is {source.readability.value!r} — "
            f"{source.readability_disclosure}. ADR-0004's A7 refuses an unreadable "
            f"source as a citation target, so the record {record.evidence_id!r} "
            "cannot be cited and cannot be stated as a finding."
        )

    if anchor.bound_source_sha256 != source_hash:
        raise ReportBuildRefusedError(
            f"the anchor {anchor_id!r} is bound to bytes that hash to "
            f"{anchor.bound_source_sha256!r}, but the record {record.evidence_id!r} "
            f"was read from bytes that hash to {source_hash!r}. A citation must be an "
            "address the record was actually read from, and this one names bytes "
            "the record did not come from."
        )

    return ProvenanceFootnote(
        footnote_id=f"fn-{anchor_id}",
        source_id=anchor.source_id,
        locator=anchor.locator,
        content_sha256=source_hash,
    )


def _disclosure_reason(record: EvidenceRecord) -> str:
    """Why the record is unresolved, said in the ledger's own words.

    The ledger holds a state and a log, not a sentence, so the sentence has
    to be written — and it is written here out of the record's own facts and
    nothing else. The failing entries of the verification log are the
    reason: a check that failed is named with its check, its checker, its
    moment and its detail, quoted rather than paraphrased. A record with no
    anchor is said to have none, because that absence is itself the reason
    ADR-0004's Contract 2 allows.

    The result is never blank. The model's own rule says a disclosure with no
    reason is decoration, and a reason that said nothing would be the same
    thing wearing a sentence.
    """
    failures = [entry for entry in record.verification_log if entry.outcome is CheckOutcome.FAIL]
    if failures:
        detail = "; ".join(
            f"check {entry.check.value} reported {entry.outcome.value} by "
            f"{entry.checker_id} at {entry.checked_at.isoformat()}: {entry.detail}"
            for entry in failures
        )
        return (
            f"the ledger records this record as {record.status.value!r}: {detail}. "
            "The record is disclosed rather than stated because the ledger does not "
            "say it holds."
        )

    if not record.anchor_ids:
        return (
            f"the ledger records this record as {record.status.value!r} and it names "
            "no anchor, so nothing in the ledger supports it. The record is "
            "disclosed rather than stated because there is nothing behind it."
        )

    entries = ", ".join(
        f"{entry.check.value} {entry.outcome.value}" for entry in record.verification_log
    )
    return (
        f"the ledger records this record as {record.status.value!r}; its "
        f"verification log records {entries or 'no entries'}. The record is "
        "disclosed rather than stated because the ledger does not say it holds."
    )


# --------------------------------------------------------------------------- #
# the artefacts
# --------------------------------------------------------------------------- #


def _parts_from_artifacts(
    artifacts: Sequence[ArtifactReceipt],
    *,
    artifact_by_id: Mapping[str, ArtifactReceipt],
    manifests: Mapping[str, ReproducibilityManifest],
    captions: Mapping[str, str],
    interpretations: Mapping[str, str],
) -> tuple[tuple[_FigurePart, ...], tuple[ReportTable, ...]]:
    """The figures and the tables, from the task's artefacts.

    Only the newest revision of each artefact is carried: the artefacts table
    is unique on (task, path, revision), so two receipts at one path are two
    emissions of one artefact, and a report that carried both would show the
    same figure twice.

    The artefacts of the kinds the report model has no part for — the report
    itself, the report's own manifest, a dataset — are not carried. A part
    the model cannot describe is not a part the report has.
    """
    figures: list[_FigurePart] = []
    tables: list[ReportTable] = []

    for receipt in _current_artifacts(artifacts):
        if receipt.kind is ArtifactKind.FIGURE:
            figures.append(
                _figure_for(
                    receipt,
                    artifact_by_id=artifact_by_id,
                    manifests=manifests,
                    captions=captions,
                    interpretations=interpretations,
                )
            )
        elif receipt.kind is ArtifactKind.TABLE:
            tables.append(
                ReportTable(
                    table_id=f"tbl-{receipt.receipt_id}",
                    relative_path=receipt.relative_path,
                    content_sha256=receipt.content_sha256,
                )
            )

    return (
        tuple(sorted(figures, key=lambda part: part.figure.figure_id)),
        tuple(sorted(tables, key=lambda table: table.table_id)),
    )


def _refuse_readings_that_name_no_figure(
    readings: Mapping[str, str],
    *,
    artifact_by_id: Mapping[str, ArtifactReceipt],
    label: str,
) -> None:
    """Refuse a caption or an interpretation that names no figure.

    A key that names nothing is a typo, and a typo here is silent: the
    reading would simply never reach the report, and the report would be
    missing a figure's caption or its interpretation without anything
    saying so. A parameter that is accepted and ignored is a parameter that
    lies, so the key is checked against the artefacts the report was given.
    """
    for key in sorted(readings):
        receipt = artifact_by_id.get(key)
        if receipt is None:
            raise ReportBuildRefusedError(
                f"the {label} names the artefact {key!r}, which the report does not "
                "carry. A reading that names nothing would be dropped in silence, "
                "and the report would be missing it without anything saying so."
            )
        if receipt.kind is not ArtifactKind.FIGURE:
            raise ReportBuildRefusedError(
                f"the {label} names the artefact {key!r}, which is a "
                f"{receipt.kind.value!r} and not a figure. A figure's caption and a "
                "figure's interpretation are the figure's own, and a reading for "
                "something else would be ignored."
            )


def _current_artifacts(artifacts: Sequence[ArtifactReceipt]) -> tuple[ArtifactReceipt, ...]:
    """The newest emission of each artefact, one per path.

    Sorted by path, so that two callers who gathered the same artefacts in a
    different order produce the same document and therefore the same bytes.
    """
    newest: dict[str, ArtifactReceipt] = {}
    for receipt in artifacts:
        existing = newest.get(receipt.relative_path)
        if existing is None:
            newest[receipt.relative_path] = receipt
            continue
        if existing.kind is not receipt.kind:
            raise ReportBuildRefusedError(
                f"the path {receipt.relative_path!r} is claimed by a "
                f"{existing.kind.value!r} artefact and by a {receipt.kind.value!r} "
                "one. One path is one file, and a report that carried it under two "
                "kinds would have two things to say about one file."
            )
        if receipt.revision > existing.revision:
            newest[receipt.relative_path] = receipt
        elif receipt.revision == existing.revision:
            raise ReportBuildRefusedError(
                f"two artefacts claim the path {receipt.relative_path!r} at revision "
                f"{receipt.revision}. The artefacts table is unique on (task, path, "
                "revision), so this is a ledger that says the same file was produced "
                "twice under one revision — and 'which one is it' would have two "
                "answers."
            )
    return tuple(sorted(newest.values(), key=lambda receipt: receipt.relative_path))


def _figure_for(
    receipt: ArtifactReceipt,
    *,
    artifact_by_id: Mapping[str, ArtifactReceipt],
    manifests: Mapping[str, ReproducibilityManifest],
    captions: Mapping[str, str],
    interpretations: Mapping[str, str],
) -> _FigurePart:
    """One figure: its bytes, its caption, and the manifest that describes it.

    The manifest is **the artefact's own**, and that is checked rather than
    assumed: the figure's chain names the manifest artefact, the manifest
    artefact recorded the hash of the file it wrote, and the manifest the
    caller handed over is hashed again here. Three hashes that agree are a
    manifest that describes this figure; two that agree are a coincidence.
    """
    manifest_receipt, chain_hash = _manifest_receipt_for(receipt, artifact_by_id=artifact_by_id)

    manifest = manifests.get(manifest_receipt.receipt_id)
    if manifest is None:
        raise ReportBuildRefusedError(
            f"the figure {receipt.receipt_id!r} names the manifest artefact "
            f"{manifest_receipt.receipt_id!r}, whose content was not given. A "
            "figure without the derivation that produced it is a picture the "
            "reader is asked to trust, and the model's own rule is that the "
            "manifest is part of the figure rather than a note about it."
        )

    if chain_hash != manifest_receipt.content_sha256:
        raise ReportBuildRefusedError(
            f"the figure {receipt.receipt_id!r} names the manifest artefact "
            f"{manifest_receipt.receipt_id!r} with bytes that hash to {chain_hash!r}, "
            f"but that artefact recorded {manifest_receipt.content_sha256!r}. The "
            "figure's own chain and the artefact it names disagree about the "
            "manifest, and a report that carries one of them would be carrying a "
            "derivation nobody can check."
        )

    observed = _digest_bytes(manifest_bytes(manifest))
    if observed != manifest_receipt.content_sha256:
        raise ReportBuildRefusedError(
            f"the manifest given for the figure {receipt.receipt_id!r} hashes to "
            f"{observed!r}, but the manifest artefact {manifest_receipt.receipt_id!r} "
            f"recorded bytes that hash to {manifest_receipt.content_sha256!r}. The "
            "manifest in the report is not the artefact's own, and a figure whose "
            "derivation is somebody else's is a figure whose numbers nobody can "
            "reproduce."
        )

    caption = captions.get(receipt.receipt_id)
    if caption is None:
        raise ReportBuildRefusedError(
            f"the figure {receipt.receipt_id!r} has no caption. The caption is the "
            "author's words, and the model forbids a renderer from inventing one "
            "because two exports of one document would then not say the same thing. "
            "Composing one from the file name would say nothing about what is "
            "plotted, so the figure is refused instead."
        )

    interpretation = interpretations.get(receipt.receipt_id)
    if interpretation is not None and not interpretation.strip():
        raise ReportBuildRefusedError(
            f"the figure {receipt.receipt_id!r} has a blank interpretation. The "
            "recipe's field is optional, and an absent one means the author wrote "
            "no reading of the figure; a blank one is a different fact and would "
            "carry a marker onto nothing."
        )

    return _FigurePart(
        figure=ReportFigure(
            figure_id=f"fig-{receipt.receipt_id}",
            relative_path=receipt.relative_path,
            content_sha256=receipt.content_sha256,
            caption=caption,
            manifest=manifest,
        ),
        interpretation=interpretation,
    )


def _manifest_receipt_for(
    receipt: ArtifactReceipt,
    *,
    artifact_by_id: Mapping[str, ArtifactReceipt],
) -> tuple[ArtifactReceipt, str]:
    """The manifest artefact a figure names, and the hash its chain gave it.

    The figure's chain names it: a figure is derived from its manifest and
    from everything the manifest was derived from, so the manifest is the
    one link of kind ``artifact`` in that chain. A figure whose chain names
    no manifest, or more than one, cannot be checked — so the builder reads
    the chain rather than guessing which artefact was meant.
    """
    candidates: list[tuple[ArtifactReceipt, str]] = []
    for link in receipt.derived_from:
        if link.target_kind is not DerivationTargetKind.ARTIFACT:
            continue
        named = artifact_by_id.get(link.target_id)
        if named is None or named.kind is not ArtifactKind.MANIFEST:
            continue
        candidates.append((named, link.content_sha256 or named.content_sha256))

    if len(candidates) != 1:
        raise ReportBuildRefusedError(
            f"the figure {receipt.receipt_id!r} names {len(candidates)} manifest "
            "artefacts in its own chain, where it must name exactly one. A figure's "
            "lineage runs file, result, manifest, figure, and a chain that does "
            "not say which manifest describes it describes no derivation at all."
        )
    return candidates[0]


# --------------------------------------------------------------------------- #
# the sections
# --------------------------------------------------------------------------- #


def _sections(
    *,
    claims: Sequence[ReportClaim],
    figures: Sequence[_FigurePart],
    tables: Sequence[ReportTable],
    disclosures: Sequence[UnresolvedRecord],
) -> tuple[ReportSection, ...]:
    """The sections, and what is under each heading.

    Four kinds and four sections, in the order a reader wants them: the
    findings first, because that is what the report is for; then the figures
    and the tables that support them; and the disclosed records **last**,
    because a disclosure is a statement about a record the report does not
    state, and putting it among the findings would invite a reader to read
    it as one.

    A section with nothing under its heading is not a section, so a kind
    with nothing to carry contributes no section at all.

    A figure's **own** interpretation is placed immediately under the
    figure it belongs to, in the figure's section and not in a section of
    its own: it is the reading of that figure and of nothing else, and the
    reader meets it where the figure is.
    """
    sections: list[ReportSection] = []
    if claims:
        sections.append(
            ReportSection(
                section_id=FINDINGS_SECTION_ID,
                heading=FINDINGS_HEADING,
                blocks=tuple(ClaimBlock(claim_id=claim.claim_id) for claim in claims),
            )
        )
    if figures:
        figure_blocks: list[ReportBlock] = []
        for part in figures:
            figure_blocks.append(FigureBlock(figure_id=part.figure.figure_id))
            if part.interpretation is not None:
                figure_blocks.append(InterpretationBlock(text=part.interpretation))
        sections.append(
            ReportSection(
                section_id=FIGURES_SECTION_ID,
                heading=FIGURES_HEADING,
                blocks=tuple(figure_blocks),
            )
        )
    if tables:
        sections.append(
            ReportSection(
                section_id=TABLES_SECTION_ID,
                heading=TABLES_HEADING,
                blocks=tuple(TableBlock(table_id=table.table_id) for table in tables),
            )
        )
    if disclosures:
        sections.append(
            ReportSection(
                section_id=UNRESOLVED_SECTION_ID,
                heading=UNRESOLVED_HEADING,
                blocks=tuple(
                    UnresolvedBlock(record_id=record.record.record_id) for record in disclosures
                ),
            )
        )
    return tuple(sections)


def _digest_bytes(data: bytes) -> str:
    """The SHA-256 of *data*, lowercase hex.

    The same definition the ledger's file hash takes
    (:func:`labcairn.security.approval.content_hash`), over bytes in memory
    rather than over a file: a manifest's bytes may never have been written
    to disk by the time the report is built, and a hash that needed a file
    could not describe them.
    """
    return hashlib.sha256(data).hexdigest()
