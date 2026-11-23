"""Round-level quality and evidence checks — execution plan §7.4.

**What this module is.** The six checks the execution plan's §7.4 names for a
closed review round. The binding (LC-P3-04) already refuses to drop an
opinion silently, and the export hash-checks the drafts it serves; what did
not exist is **one measurement that says whether the round as a whole holds
together** — that every opinion is accounted for, that every suggestion
answers a real opinion, that the edits stayed inside the anchored
paragraphs, that a needs-evidence verdict left an explicit task behind, that
the response table's rows say what actually landed, and that the quality
report renders from the same manifest the four deliverables bind.

**The dossier manifest is the authority.** Every check reads the round's
:class:`~labcairn.papers.binding.DossierManifest` — the binding's own record,
written once at the close — and the store's rows beside it. **No check
re-derives from bytes what the manifest already binds**: the drafts' digests
are compared with the manifest's digests, never recomputed from a fresh fold
of the manuscript. A check that re-derived the round would be a second
spelling of the binding, and the two would drift.

**Each check names its failing facts.** A check that fails says *which*
opinion, *which* paragraph, *which* digest mismatch — a bare ``passed:
false`` would send the operator back to re-derive what the record already
knows.

**The checks are reads.** They run through the layer's own
:func:`~labcairn.application.artifacts.read_artifact` for the manifest and
its bytes, and they write nothing.

The six checks
--------------

1. **opinion coverage** — every opinion the chain holds for the round's
   input version is accounted for: it carries a suggestion, or a reviewer's
   decision, or an explicit unresolved task. An opinion absent from all
   three is an opinion the round silently dropped.
2. **suggestion-to-opinion correspondence** — every suggestion maps to
   exactly one opinion, and no suggestion names an opinion that does not
   exist — in the manifest, or in the chain's own rows.
3. **modification scope** — the edits the round applied sit inside the
   paragraphs the opinions anchored. The seam's unit is one whole run of one
   paragraph, so an applied edit's paragraph must be the opinion's anchored
   paragraph (the reader's 0-based anchor, plus the 1-based offset the
   suggestion vocabulary uses). Nothing outside the reviewed set changed is
   the digest discipline the export already carries; this check is the
   address-level half of the same claim.
4. **evidence completeness** — an opinion the reviewer decided as needing
   evidence stands as an explicit unresolved task. A needs-evidence verdict
   with no unresolved entry is a task somebody silently dropped.
5. **response-table-vs-actual-edits consistency** — the response table's
   per-opinion rows match the edits actually folded into the drafts: a row
   for an applied edit names the change the chain recorded, and a row for an
   opinion nothing was applied to says so. A row that names an edit that did
   not land is the failure this check exists to catch.
6. **quality-report-vs-four-deliverables binding consistency** — the quality
   report renders from the same manifest the four deliverables bind: the
   receipts it names exist in the store with the digests the manifest binds,
   the output version's own hash is the marked draft's hash, and the
   rendered report carries every id the manifest binds.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from sqlalchemy import select

from labcairn.application.context import ApplicationContext
from labcairn.application.models import Result
from labcairn.application.refusal import (
    ApplicationRefusal,
    ApplicationRefusedError,
    chain_refused,
)
from labcairn.db.models import EditActionRow, PaperVersionRow, ReviewSuggestionRow
from labcairn.db.repository import list_artifacts as store_list_artifacts
from labcairn.papers.chain import ChainRefusal, feedback_row, project_row

if TYPE_CHECKING:
    from labcairn.papers.binding import DossierManifest

__all__ = [
    "CHECK_NAMES",
    "CheckOutcome",
    "QualityCheckFact",
    "RoundQualityReport",
    "check_edit_scope",
    "check_evidence_complete",
    "check_opinion_coverage",
    "check_report_binding",
    "check_response_table_consistency",
    "check_suggestion_correspondence",
    "run_round_quality_checks",
]


#: The six checks, in the order execution plan §7.4 names them. The order is
#: part of the report: the same round reads the same way every time.
CHECK_NAMES: Final[tuple[str, ...]] = (
    "opinion_coverage",
    "suggestion_correspondence",
    "edit_scope",
    "evidence_complete",
    "response_table_consistency",
    "report_binding",
)

_CHECK_COVERAGE: Final[str] = "opinion_coverage"
_CHECK_CORRESPONDENCE: Final[str] = "suggestion_correspondence"
_CHECK_SCOPE: Final[str] = "edit_scope"
_CHECK_EVIDENCE: Final[str] = "evidence_complete"
_CHECK_RESPONSE_TABLE: Final[str] = "response_table_consistency"
_CHECK_REPORT_BINDING: Final[str] = "report_binding"


class QualityCheckFact(Result):
    """One failing fact a check names.

    ``feedback_id`` names the opinion when the fact is about one;
    ``paragraph`` names the paragraph an edit landed at; ``expected`` and
    ``actual`` carry the two sides of a mismatch. ``detail`` is the sentence
    a person reads. Every field is data — a surface renders them, and the
    report does not format them itself.
    """

    check: str
    detail: str
    feedback_id: str | None = None
    paragraph: int | None = None
    expected: str | None = None
    actual: str | None = None


class CheckOutcome(Result):
    """One check's verdict, with the facts that made it."""

    check: str
    passed: bool
    facts: tuple[QualityCheckFact, ...] = ()


class RoundQualityReport(Result):
    """The six checks' verdicts for one closed round.

    ``checks`` carries one outcome per check, in :data:`CHECK_NAMES`'s order.
    :attr:`passed` is true when every check passed — the property the apply
    result and any surface reading this report branches on.
    """

    project_id: str
    input_version_id: str
    output_version_id: str
    dossier_artifact_id: str
    checks: tuple[CheckOutcome, ...]

    @property
    def passed(self) -> bool:
        """Whether every check passed."""
        return all(outcome.passed for outcome in self.checks)


def run_round_quality_checks(
    context: ApplicationContext,
    *,
    project_id: str,
    dossier_artifact_id: str,
) -> RoundQualityReport:
    """Run the six §7.4 checks over one closed round's dossier manifest.

    **The manifest is read through the layer's own door.** The dossier is an
    artefact row, read back under the policy's verdict; a manifest that is
    not there, or that binds another project, is refused rather than
    measured.

    :raises ApplicationRefusedError: the project is not there, the artefact
        is not a dossier manifest, or the manifest binds another project.
    """
    from labcairn.application.artifacts import read_artifact
    from labcairn.papers.binding import DossierManifest
    from labcairn.reports.receipt import ArtifactKind

    if project_row(context.store.session, project_id) is None:
        raise chain_refused(
            ChainRefusal.PROJECT_NOT_FOUND,
            f"the store holds no paper project with the id {project_id!r}. A "
            "round's quality is measured for a project, and a project nobody "
            "holds has no round to measure.",
        )
    dossier = read_artifact(context, dossier_artifact_id)
    if dossier.receipt.kind is not ArtifactKind.MANIFEST:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the artefact {dossier_artifact_id!r} is a "
            f"{dossier.receipt.kind.value!r} receipt, not a dossier manifest. "
            "The round's quality checks read the binding's own manifest, and "
            "another artefact names no round to check.",
        )
    manifest_json = dossier.content.decode("utf-8")
    manifest = DossierManifest.model_validate_json(manifest_json)
    if manifest.project_id != project_id:
        raise ApplicationRefusedError(
            ApplicationRefusal.ARGUMENTS_INVALID,
            f"the dossier {dossier_artifact_id!r} binds the project "
            f"{manifest.project_id!r}, not {project_id!r}. A round's quality "
            "is measured for the project the dossier binds, or not at all.",
        )

    outcomes = (
        check_opinion_coverage(manifest),
        check_suggestion_correspondence(context, manifest),
        check_edit_scope(manifest),
        check_evidence_complete(manifest),
        check_response_table_consistency(context, manifest, manifest_json),
        check_report_binding(context, manifest, manifest_json),
    )
    return RoundQualityReport(
        project_id=project_id,
        input_version_id=manifest.input_version_id,
        output_version_id=manifest.output_version_id,
        dossier_artifact_id=dossier_artifact_id,
        checks=outcomes,
    )


def _fact(
    check: str,
    detail: str,
    *,
    feedback_id: str | None = None,
    paragraph: int | None = None,
    expected: str | None = None,
    actual: str | None = None,
) -> QualityCheckFact:
    """One failing fact, with the check's name attached."""
    return QualityCheckFact(
        check=check,
        detail=detail,
        feedback_id=feedback_id,
        paragraph=paragraph,
        expected=expected,
        actual=actual,
    )


def check_opinion_coverage(manifest: DossierManifest) -> CheckOutcome:
    """Every opinion the chain holds is suggested, decided, or unresolved.

    The manifest's ``opinions`` are the chain's own rows read back at the
    close, so what the chain holds is what this check accounts for. A
    suggestion, a decision and an unresolved task are the three records a
    round can carry about one opinion; an opinion carrying none of them is
    an opinion the round dropped without saying so.
    """
    covered = (
        {suggestion.feedback_id for suggestion in manifest.suggestions}
        | {decision.feedback_id for decision in manifest.decisions}
        | {task.feedback_id for task in manifest.unresolved}
    )
    facts = [
        _fact(
            _CHECK_COVERAGE,
            "the round records no suggestion, no reviewer decision and no "
            "unresolved task for this opinion",
            feedback_id=opinion.feedback_id,
        )
        for opinion in manifest.opinions
        if opinion.feedback_id not in covered
    ]
    return CheckOutcome(check=_CHECK_COVERAGE, passed=not facts, facts=tuple(facts))


def check_suggestion_correspondence(
    context: ApplicationContext, manifest: DossierManifest
) -> CheckOutcome:
    """Every suggestion answers exactly one opinion the chain holds.

    Two layers, because a suggestion lives in two places: the manifest
    carries the round's own suggestions, and the store's
    ``review_suggestions`` table carries what the workbench showed the
    reviewer. Both must name opinions the chain actually holds — a
    suggestion about an opinion nobody holds is a proposal about nothing.
    """
    facts: list[QualityCheckFact] = []
    opinion_ids = {opinion.feedback_id for opinion in manifest.opinions}
    seen: set[str] = set()
    for suggestion in manifest.suggestions:
        if suggestion.feedback_id in seen:
            facts.append(
                _fact(
                    _CHECK_CORRESPONDENCE,
                    "more than one suggestion is carried for this opinion",
                    feedback_id=suggestion.feedback_id,
                )
            )
        seen.add(suggestion.feedback_id)
        if suggestion.feedback_id not in opinion_ids:
            facts.append(
                _fact(
                    _CHECK_CORRESPONDENCE,
                    "the suggestion names an opinion the manifest does not hold",
                    feedback_id=suggestion.feedback_id,
                )
            )
    rows = context.store.session.scalars(
        select(ReviewSuggestionRow).where(ReviewSuggestionRow.project_id == manifest.project_id)
    ).all()
    for row in rows:
        if feedback_row(context.store.session, row.feedback_id) is None:
            facts.append(
                _fact(
                    _CHECK_CORRESPONDENCE,
                    "the stored suggestion names an opinion the chain does not hold",
                    feedback_id=row.feedback_id,
                )
            )
    return CheckOutcome(check=_CHECK_CORRESPONDENCE, passed=not facts, facts=tuple(facts))


def check_edit_scope(manifest: DossierManifest) -> CheckOutcome:
    """Every applied edit sits inside the paragraph its opinion anchored.

    **The comparison is between two addresses the record already holds**: the
    suggestion's 1-based paragraph and the opinion's 0-based anchor. The
    seam rewrites one whole run of one paragraph, so an applied edit whose
    paragraph is not the anchored one is an edit that reached outside the
    reviewed set. Byte-level fidelity — that nothing *else* in the package
    changed — is the export's own digest discipline; this check is the
    address-level half, from the manifest alone.
    """
    facts: list[QualityCheckFact] = []
    opinions = {opinion.feedback_id: opinion for opinion in manifest.opinions}
    for suggestion in manifest.suggestions:
        opinion = opinions.get(suggestion.feedback_id)
        if opinion is None:
            # The missing opinion is the correspondence check's fact; the
            # scope check has no anchor to compare against and says nothing
            # about it here.
            continue
        if opinion.anchor_status != "resolved" or opinion.anchor_paragraph is None:
            facts.append(
                _fact(
                    _CHECK_SCOPE,
                    "an edit was applied for an opinion whose anchor does not "
                    "resolve to a paragraph",
                    feedback_id=suggestion.feedback_id,
                    paragraph=suggestion.paragraph,
                    expected="a resolved anchor paragraph",
                    actual=f"anchor {opinion.anchor_status!r}",
                )
            )
            continue
        expected_paragraph = opinion.anchor_paragraph + 1
        if suggestion.paragraph != expected_paragraph:
            facts.append(
                _fact(
                    _CHECK_SCOPE,
                    "the applied edit lands outside the paragraph the opinion anchored",
                    feedback_id=suggestion.feedback_id,
                    paragraph=suggestion.paragraph,
                    expected=str(expected_paragraph),
                    actual=str(suggestion.paragraph),
                )
            )
    return CheckOutcome(check=_CHECK_SCOPE, passed=not facts, facts=tuple(facts))


def check_evidence_complete(manifest: DossierManifest) -> CheckOutcome:
    """A needs-evidence verdict stands as an explicit unresolved task.

    The unresolved list is the round's record of what is owed; a verdict
    that says the manuscript lacks evidence, with no entry in that list, is
    an opinion the round promised to remember and did not.
    """
    unresolved = {task.feedback_id for task in manifest.unresolved}
    facts = [
        _fact(
            _CHECK_EVIDENCE,
            "the reviewer decided this opinion needs evidence, and the round "
            "records no unresolved task for it",
            feedback_id=decision.feedback_id,
        )
        for decision in manifest.decisions
        if decision.needs_evidence and decision.feedback_id not in unresolved
    ]
    return CheckOutcome(check=_CHECK_EVIDENCE, passed=not facts, facts=tuple(facts))


def check_response_table_consistency(
    context: ApplicationContext, manifest: DossierManifest, manifest_json: str
) -> CheckOutcome:
    """The response table's rows say what actually landed.

    **The table is rendered from the manifest, then compared with the
    manifest's own facts.** The renderer is the deliverable's own, so the
    comparison is between what the table shows a reader and what the chain
    recorded: an applied edit's row must name the change the chain holds —
    and that change must exist in the store — and an opinion nothing was
    applied to must read "no change applied". A row that names an edit that
    did not land is the failure this check exists to catch.
    """
    from labcairn.reports.response_table import render_response_table_markdown

    facts: list[QualityCheckFact] = []
    rendered = render_response_table_markdown(manifest_json).decode("utf-8")
    rows = [
        line
        for line in rendered.splitlines()
        if line.startswith("|") and not line.startswith("|--") and "Opinion" not in line
    ]
    if len(rows) != len(manifest.opinions):
        facts.append(
            _fact(
                _CHECK_RESPONSE_TABLE,
                f"the response table holds {len(rows)} opinion rows for "
                f"{len(manifest.opinions)} opinions",
            )
        )
        return CheckOutcome(check=_CHECK_RESPONSE_TABLE, passed=False, facts=tuple(facts))

    # **Rows are matched by the opinion id they carry**, not by position: the
    # table's first column is the opinion's own id, so the comparison is an
    # equality test on the record rather than an assumption about order.
    rows_by_id: dict[str, list[str]] = {}
    for line in rows:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        rows_by_id[cells[0]] = cells

    suggested = {suggestion.feedback_id for suggestion in manifest.suggestions}
    links = {response.feedback_id: response for response in manifest.responses}
    edit_rows = {
        row.edit_action_id: row
        for row in context.store.session.scalars(select(EditActionRow)).all()
    }
    for opinion in manifest.opinions:
        cells = rows_by_id.get(opinion.feedback_id, [])
        change_cell = cells[4] if len(cells) > 4 else ""
        link = links.get(opinion.feedback_id)
        if opinion.feedback_id in suggested:
            if link is None:
                facts.append(
                    _fact(
                        _CHECK_RESPONSE_TABLE,
                        "an edit was applied for this opinion, and the response "
                        "table holds no change for it",
                        feedback_id=opinion.feedback_id,
                    )
                )
                continue
            edit_row = edit_rows.get(link.edit_action_id)
            if edit_row is None or edit_row.feedback_id != opinion.feedback_id:
                facts.append(
                    _fact(
                        _CHECK_RESPONSE_TABLE,
                        "the response row names an edit that did not land",
                        feedback_id=opinion.feedback_id,
                        expected="an edit action the chain holds",
                        actual=link.edit_action_id,
                    )
                )
            if change_cell != link.edit_action_id:
                facts.append(
                    _fact(
                        _CHECK_RESPONSE_TABLE,
                        "the response table's change cell disagrees with the chain's judgement",
                        feedback_id=opinion.feedback_id,
                        expected=link.edit_action_id,
                        actual=change_cell,
                    )
                )
        else:
            if link is not None:
                facts.append(
                    _fact(
                        _CHECK_RESPONSE_TABLE,
                        "the chain holds a change for this opinion, and no edit was applied for it",
                        feedback_id=opinion.feedback_id,
                        actual=link.edit_action_id,
                    )
                )
            if change_cell != "no change applied":
                facts.append(
                    _fact(
                        _CHECK_RESPONSE_TABLE,
                        "the response table's change cell names a change for an "
                        "opinion nothing was applied to",
                        feedback_id=opinion.feedback_id,
                        expected="no change applied",
                        actual=change_cell,
                    )
                )
    return CheckOutcome(check=_CHECK_RESPONSE_TABLE, passed=not facts, facts=tuple(facts))


def check_report_binding(
    context: ApplicationContext, manifest: DossierManifest, manifest_json: str
) -> CheckOutcome:
    """The quality report renders from the manifest the deliverables bind.

    **Three facts, all from the record.** The marked and the clean draft's
    receipts exist in the store with the digests the manifest binds; the
    output version's own hash is the marked draft's hash (the output version
    *is* the marked draft, registered); and the rendered report carries
    every id the manifest binds — verbatim, because the renderer prints
    product-minted ids unescaped so a reader can copy them back.
    """
    from labcairn.reports.quality_report import render_quality_report_markdown

    facts: list[QualityCheckFact] = []
    receipts = {
        receipt.receipt_id: receipt
        for receipt in store_list_artifacts(context.store.session, context.task_id)
    }
    for name, receipt_id, bound_digest in (
        ("marked", manifest.marked_receipt_id, manifest.marked_sha256),
        ("clean", manifest.clean_receipt_id, manifest.clean_sha256),
    ):
        receipt = receipts.get(receipt_id)
        if receipt is None:
            facts.append(
                _fact(
                    _CHECK_REPORT_BINDING,
                    f"the {name} draft's receipt is not in the store",
                    expected=receipt_id,
                    actual="no receipt",
                )
            )
        elif receipt.content_sha256 != bound_digest:
            facts.append(
                _fact(
                    _CHECK_REPORT_BINDING,
                    f"the {name} draft's bytes do not match the digest the manifest binds",
                    expected=bound_digest,
                    actual=receipt.content_sha256,
                )
            )
    version = context.store.session.get(PaperVersionRow, manifest.output_version_id)
    if version is None:
        facts.append(
            _fact(
                _CHECK_REPORT_BINDING,
                "the output version the manifest binds is not in the store",
                expected=manifest.output_version_id,
                actual="no version row",
            )
        )
    elif version.source_content_sha256 != manifest.marked_sha256:
        facts.append(
            _fact(
                _CHECK_REPORT_BINDING,
                "the output version's hash is not the marked draft's hash",
                expected=manifest.marked_sha256,
                actual=version.source_content_sha256 or "",
            )
        )
    report = render_quality_report_markdown(manifest_json).decode("utf-8")
    for token in (
        manifest.task_id,
        manifest.input_version_id,
        manifest.output_version_id,
        manifest.edge_id,
        manifest.marked_receipt_id,
        manifest.clean_receipt_id,
        manifest.marked_sha256,
        manifest.clean_sha256,
    ):
        if token not in report:
            facts.append(
                _fact(
                    _CHECK_REPORT_BINDING,
                    "the rendered quality report does not carry an id the manifest binds",
                    expected=token,
                    actual="absent from the report",
                )
            )
    return CheckOutcome(check=_CHECK_REPORT_BINDING, passed=not facts, facts=tuple(facts))
