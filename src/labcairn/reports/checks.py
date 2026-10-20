"""The content checks: what a report must agree with before it may be written.

LC-P1-11 asks for *"content verification separate from formatting/rendering"*,
and this module is that separation made mechanical. The work order's acceptance
clause — *"numeric values agree with ledger, figures/captions intact, links
resolve"* — is three sentences about the report's **content**, and not one of
them is about Markdown or HTML or DOCX or PDF. So the checks run against
:class:`~labcairn.reports.model.ReportDocument`, before anything is rendered.

**Why the model and not an export.** A check on a rendered file would be a
*second* content: the export's own numbers, its own captions, its own links.
The four renderers would then have to agree with each other, which is the
defect this subtask exists to prevent — one report, four renderings, four
chances to say something the ledger does not say. The model is the one place
the content is, so the checks are about the model and the renderers only draw
it.

**Why a refusal and not a warning.** A report that says 4.25 where the ledger
says 4.5 must not be written. A check that *corrected* the document would be a
second copy of the ledger with its own idea of what the numbers are, and a
check that warned and went on would put the disagreement on the page. So a
failed check raises :class:`ReportRefusedError` and the report is not written.

**Why the live ledger.** A check that compared the model's copy of a record
with the model's copy of the same record would be comparing the thing under
test with itself. So the checks read the ledger: the record they name, the
value it holds, the state it is in. Where the model says ``verified_by_rule``
and the ledger now says ``conflicted``, the report is refused — the model's
copy is what is being checked, and a copy is not an authority.

The five checks
---------------
1. :func:`check_numbers_agree_with_the_ledger` — every number in the report
   is the ledger's number, compared exactly.
2. :func:`check_figures_carry_their_captions_and_their_bytes` — every figure
   is captioned, and the bytes on disk are the bytes the model names.
3. :func:`check_links_resolve` — every citation is an address the index can
   resolve, and the check is a resolution rather than a comparison of strings.
4. :func:`check_claims_rest_on_records_that_may_be_stated` — every claim names
   a record the ledger holds, and that record may be stated as a finding.
5. :func:`check_the_snapshot_names_the_records_the_report_carries` — the
   report's extent is answerable: it names exactly the records it carries.

The cost
--------
**The checks need the ledger, and the index, and the disk.** A report cannot
be verified against nothing, which means a report's content is only as good
as the machinery that can look at the material behind it — and a caller that
wants to check an *older* revision has to hand over a ledger as it was at that
revision's moment, because the live ledger has moved on. The seam for that is
:class:`LedgerReader`: the checks read records through it and never through
the model, so the reader is the one thing a caller chooses.

**Two of the five are rules the model already enforces.** A figure without a
caption and a snapshot that disagrees with the records the report carries are
both refused by :class:`~labcairn.reports.model.ReportDocument` on
construction. The checks say them again anyway, and the duplication is the
point: the model is the rule a document meets when it is *built*, and these
are the rules a document meets when it is *written out*. A check that relied
on the model's validators would be a check that could not fail on its own.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from sqlalchemy.engine import Connection

from labcairn.evidence.cite_support import LocationResolution, SourceIndex
from labcairn.evidence.record import EvidenceRecord
from labcairn.evidence.store import load_record
from labcairn.reports.model import (
    FINDING_STATUSES,
    ProvenanceFootnote,
    ReportClaim,
    ReportDocument,
)
from labcairn.security.approval import content_hash
from labcairn.sources.locators import describe_locator
from labcairn.sources.source import SourceAnchor

__all__ = [
    "LedgerReader",
    "ReportRefusedError",
    "check_claims_rest_on_records_that_may_be_stated",
    "check_figures_carry_their_captions_and_their_bytes",
    "check_links_resolve",
    "check_numbers_agree_with_the_ledger",
    "check_report",
    "check_the_snapshot_names_the_records_the_report_carries",
    "ledger_reader",
]


class ReportRefusedError(RuntimeError):
    """The report is refused: it does not agree with the material it names.

    A refusal and not a warning, and never a correction — see the module
    docstring. The message names the check that refused and says what
    disagreed, because a refusal nobody can act on is the same as no refusal:
    the person fixing it has to know which of the five rules it broke.
    """

    def __init__(self, check: str, reason: str) -> None:
        super().__init__(f"{check}: {reason}")
        self.check = check
        self.reason = reason


@runtime_checkable
class LedgerReader(Protocol):
    """The ledger, as the checks read it.

    One member, and it is the one the checks need: a record by its id, or
    ``None`` for an id the ledger has never heard of. A Protocol rather than a
    :class:`~sqlalchemy.engine.Connection` so that the checks are about the
    report and not about SQL, and so that a caller may hand them the ledger
    as it stood at the report's moment rather than the ledger as it is now.
    """

    def load_record(self, evidence_id: str) -> EvidenceRecord | None:
        """The record with this id, or ``None`` if the ledger holds no such record."""
        ...


class _ConnectionLedger:
    """The live ledger, read through the ledger's own reader."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def load_record(self, evidence_id: str) -> EvidenceRecord | None:
        return load_record(self._connection, evidence_id)


def ledger_reader(connection: Connection) -> LedgerReader:
    """The live ledger, as the checks read it.

    The one place the connection becomes a ledger. Everything above it reads
    records through :class:`LedgerReader`, so a caller that wants to check a
    report against the ledger as it was at some earlier moment can hand over
    a reader over that moment instead.
    """
    return _ConnectionLedger(connection)


def check_numbers_agree_with_the_ledger(document: ReportDocument, *, ledger: LedgerReader) -> None:
    """Every number in the report is the ledger's number.

    The comparison is **exact**, and that is the whole content of the check.
    The ledger's number and the report's number are two floats, and a check
    that compared their rounded forms would accept a report that says 4.25
    where the ledger says 4.253 — a different claim about the same cell, and
    one that no reader could see was different. So the values are compared as
    they are, and a tolerance is never invented here: ADR-0004's rule is that
    a unit and a tolerance are *declared*, and a report that restates a
    quantity may not widen the comparison that authorised it.

    A record the ledger does not hold is left to
    :func:`check_claims_rest_on_records_that_may_be_stated`: there is no
    number here to compare with anything, and a check that reported it twice
    would say the same thing in two places.
    """
    problems: list[str] = []
    for claim in document.claims:
        view = claim.record
        record = ledger.load_record(view.record_id)
        if record is None:
            continue
        if view.value != record.value:
            problems.append(
                f"the claim {claim.claim_id!r} states the value {view.value!r}, but the "
                f"ledger's record {record.evidence_id!r} holds {record.value!r}. A report "
                "states the ledger's number; a report that states another one is not "
                "written"
            )
        if view.unit != record.unit:
            problems.append(
                f"the claim {claim.claim_id!r} states the unit {view.unit!r}, but the "
                f"ledger's record {record.evidence_id!r} declares {record.unit!r}. The "
                "unit is declared and never inferred, and a report may not restate it"
            )
    if problems:
        raise ReportRefusedError("numbers", "; ".join(problems))


def check_claims_rest_on_records_that_may_be_stated(
    document: ReportDocument, *, ledger: LedgerReader
) -> None:
    """Every claim names a record the ledger holds, and that record is statable.

    Three things, and the first is the one the model cannot do.

    **The record must exist.** A claim names the record it rests on, and the
    ledger is where records live. A claim naming an id the ledger has never
    heard of rests on nothing, and a report that carried it would be making a
    statement about a record no reader could look up.

    **The record must be in a state that may be stated.** ADR-0004's rule is
    that neither of two disagreeing readings wins by recency and the conflict
    is *displayed*, and a record that is ``conflicted`` or ``unsupported`` is
    therefore carried in the report as a disclosure rather than as a finding.
    The model enforces that on its own copy of the record; this check reads
    the ledger, because the ledger is what the record *is*. A record that was
    verified when the report was written and has since been found to conflict
    is refused here, and refused is what should happen: the report would be
    stating as a finding something the ledger now says is a conflict.

    **The report must state the ledger's words.** A claim record's text is
    what the report prints, so the text in the report and the text in the
    ledger have to be the same text. The number and the sentence are the same
    kind of obligation, and the model keeps them apart only because one of
    them is a quantity and the other is a statement.
    """
    problems: list[str] = []
    for claim in document.claims:
        view = claim.record
        record = ledger.load_record(view.record_id)
        if record is None:
            problems.append(
                f"the claim {claim.claim_id!r} rests on the record {view.record_id!r}, "
                "which the ledger does not hold. A claim names the record it rests "
                "on, and a record nobody holds is nothing to rest on"
            )
            continue
        if record.status not in FINDING_STATUSES:
            problems.append(
                f"the claim {claim.claim_id!r} rests on the record "
                f"{record.evidence_id!r}, which the ledger now holds as "
                f"{record.status.value!r}. A record in that state may not be stated "
                "as a finding: neither of two disagreeing readings wins by recency, "
                "and the conflict is displayed rather than resolved"
            )
        if record.kind is not view.record_kind:
            problems.append(
                f"the claim {claim.claim_id!r} states a {view.record_kind.value!r} "
                f"record, but the ledger's record {record.evidence_id!r} is a "
                f"{record.kind.value!r} one. A number and a sentence are kept apart "
                "on purpose, and a report may not turn one into the other"
            )
        if record.text != view.text:
            problems.append(
                f"the claim {claim.claim_id!r} states {view.text!r}, but the ledger's "
                f"record {record.evidence_id!r} says {record.text!r}. The report "
                "states the ledger's words, not its own"
            )
    if problems:
        raise ReportRefusedError("claims", "; ".join(problems))


def check_links_resolve(document: ReportDocument, *, index: SourceIndex) -> None:
    """Every citation is an address the index can resolve.

    The check is a **resolution**, and that is the difference between a check
    and a comparison. Two locators can be equal as text and name an address
    that holds nothing — page 99 of a three-page paper is a well-formed
    address. So the citation is resolved against the material, and the answer
    the material gives is the answer the check acts on: ``resolved`` and
    nothing else. ADR-0004's A1 requires that an address which does not
    resolve cites *nothing* in its place — not the nearest page, not the last
    page — and there is no free-text label here to trim, so the only possible
    fallback would be a different address, which is a different claim.

    A citation is also the address of a record a claim rests on, so it is
    resolved through that record's own anchors: the ledger's registered
    addresses are the ones the record was read from, and a citation that
    names another address is a citation to something else.
    """
    problems: list[str] = []
    footnotes = {footnote.footnote_id: footnote for footnote in document.footnotes}
    cited: set[str] = set()
    for claim in document.claims:
        for footnote_id in claim.footnote_ids:
            cited.add(footnote_id)
            footnote = footnotes.get(footnote_id)
            if footnote is None:
                problems.append(
                    f"the claim {claim.claim_id!r} cites the citation {footnote_id!r}, "
                    "which the report does not carry"
                )
                continue
            problems.extend(_resolve_citation(claim, footnote, index))
    for footnote in document.footnotes:
        if footnote.footnote_id not in cited:
            problems.append(
                f"the citation {footnote.footnote_id!r} is cited by no claim. A "
                "citation is the address of the record a claim rests on, and a "
                "citation with no claim behind it has no address to resolve"
            )
    if problems:
        raise ReportRefusedError("links", "; ".join(problems))


def _resolve_citation(
    claim: ReportClaim, footnote: ProvenanceFootnote, index: SourceIndex
) -> list[str]:
    """What resolving one citation found, as the sentences that say so."""
    problems: list[str] = []
    anchors: list[SourceAnchor] = []
    for anchor_id in claim.record.anchor_ids:
        anchor = index.load_anchor(anchor_id)
        if anchor is None:
            problems.append(
                f"the claim {claim.claim_id!r} rests on the anchor {anchor_id!r}, which "
                "the ledger has never heard of"
            )
            continue
        anchors.append(anchor)

    matching = [
        anchor
        for anchor in anchors
        if anchor.source_id == footnote.source_id and anchor.locator == footnote.locator
    ]
    if not matching:
        problems.append(
            f"the citation {footnote.footnote_id!r} names {footnote.source_id!r} at "
            f"{describe_locator(footnote.locator)}, which is not an address the record "
            f"behind the claim {claim.claim_id!r} was read from"
        )
        return problems

    for anchor in matching:
        located = index.locate(anchor)
        if located is None:
            problems.append(
                f"the citation {footnote.footnote_id!r} points at "
                f"{describe_locator(footnote.locator)}, and the index cannot resolve "
                "it at all. A citation to an address nothing answers is a citation to "
                "nothing"
            )
            continue
        if located.resolution is not LocationResolution.RESOLVED:
            problems.append(
                f"the citation {footnote.footnote_id!r} points at "
                f"{describe_locator(footnote.locator)}, which the material answers "
                f"with {located.resolution.value!r}. Nothing is cited in its place"
            )
    return problems


def check_figures_carry_their_captions_and_their_bytes(
    document: ReportDocument, *, workspace_root: Path
) -> None:
    """Every figure is captioned, and the bytes on disk are the bytes it names.

    Two things, and the second is the one that can be done wrong.

    **The caption is the model's.** A figure without a caption is a picture
    the reader has to interpret alone, and a caption invented by a renderer is
    a caption that changes with the format — which is how four exports of one
    report stop saying the same thing. The model refuses a blank caption and
    so does this check, because the model is the rule a document meets when it
    is built and this is the rule a document meets when it is written out.

    **The bytes are read, not believed.** The figure's ``content_sha256`` is
    the model's *claim* about the file; the file's own hash is the fact. A
    check that compared the model's hash with the model's hash would pass on
    a figure that was never drawn, and the report would show a picture of
    something else. So the file is opened and hashed here, and the two are
    compared — the same way the ledger compares a recorded hash with the
    source as it now stands, and never the other way round.
    """
    problems: list[str] = []
    root = workspace_root.resolve()
    for figure in document.figures:
        if not figure.caption.strip():
            problems.append(
                f"the figure {figure.figure_id!r} carries no caption. A caption is the "
                "model's, and a renderer that has to invent one invents a different "
                "one for every format"
            )
        target = root / figure.relative_path
        resolved = target.resolve()
        if not resolved.is_relative_to(root):
            problems.append(
                f"the figure {figure.figure_id!r} names {figure.relative_path!r}, which "
                "resolves outside the workspace. A figure is a file in the workspace, "
                "and one somewhere else is not it"
            )
            continue
        try:
            observed = content_hash(resolved)
        except OSError as error:
            problems.append(
                f"the figure {figure.figure_id!r} names {figure.relative_path!r}, which "
                f"cannot be read: {error}. A figure the report cannot find is a "
                "picture of nothing"
            )
            continue
        if observed != figure.content_sha256:
            problems.append(
                f"the figure {figure.figure_id!r} names {figure.relative_path!r}, whose "
                f"bytes hash to {observed}, but the report records "
                f"{figure.content_sha256}. The figure in the report is not the figure "
                "on disk"
            )
    if problems:
        raise ReportRefusedError("figures", "; ".join(problems))


def check_the_snapshot_names_the_records_the_report_carries(document: ReportDocument) -> None:
    """The report's extent is answerable, in both directions.

    A report is a view of a set of ledger records, frozen at a moment, and
    the snapshot says which set. So the records the report carries are the
    records the snapshot names, and neither may exceed the other: a record
    the snapshot does not name is a record the reader cannot check the view
    against, and a record the snapshot names that the report does not show
    makes "which records is this a view of" answerable two ways.

    The model refuses both on construction, and this check says them again
    for the reason
    :func:`check_figures_carry_their_captions_and_their_bytes` gives: a check
    that leaned on the model's validators would be a check that could not
    fail on its own.
    """
    carried = {claim.record.record_id for claim in document.claims}
    carried |= {record.record.record_id for record in document.unresolved_records}
    named = set(document.snapshot.record_ids)

    problems: list[str] = []
    missing = sorted(carried - named)
    if missing:
        problems.append(
            f"the report carries the record(s) {missing}, which its snapshot does not "
            "name. The snapshot is the report's statement of which records it is a "
            "view of, and a record it does not name is a record the reader cannot "
            "check the view against"
        )
    extra = sorted(named - carried)
    if extra:
        problems.append(
            f"the snapshot names the record(s) {extra}, which the report does not "
            "carry. The snapshot names the extent of the view, and a record it names "
            "that the report does not show makes the view's extent unanswerable"
        )
    if problems:
        raise ReportRefusedError("snapshot", "; ".join(problems))


def check_report(
    document: ReportDocument,
    *,
    ledger: LedgerReader,
    index: SourceIndex,
    workspace_root: Path,
) -> None:
    """Every content check, in the order the report's own dependencies come.

    The order is the order of the report: the extent of the view, then the
    numbers, then the records the claims rest on, then the citations, then the
    figures on disk. The first refusal stops the run, because a report is not
    written on the strength of the checks that happened to pass — and a check
    that warns and carries on is exactly what this work order forbids.

    :param document: the report to check. The model, never an export.
    :param ledger: the records are read from here, not from the document.
    :param index: the citations are resolved through here.
    :param workspace_root: the root the figures' workspace-relative paths are
        read under.
    :raises ReportRefusedError: if any check finds anything.
    """
    check_the_snapshot_names_the_records_the_report_carries(document)
    check_numbers_agree_with_the_ledger(document, ledger=ledger)
    check_claims_rest_on_records_that_may_be_stated(document, ledger=ledger)
    check_links_resolve(document, index=index)
    check_figures_carry_their_captions_and_their_bytes(document, workspace_root=workspace_root)
