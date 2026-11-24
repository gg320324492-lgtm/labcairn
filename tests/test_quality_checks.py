"""Round-level quality and evidence checks — execution plan §7.4, watched.

The binding closes a round with a dossier manifest; the six §7.4 checks read
that manifest and say whether the round holds together. What these witnesses
establish:

* **A healthy round passes all six** — the full apply path through the
  binding's own fixture, measured at the close.
* **Each check fails for its own property, and names the fact.** A round
  where the check fails is constructible, and the failing fact names the
  opinion, the paragraph or the digest mismatch — not a bare ``passed:
  false``.

The failing rounds are built by **tampering with the record the check
reads**, not by breaking the binding: the binding's own witnesses already
hold the binding honest, and these witnesses hold the *checks* honest. A
check that could not fail, or that failed for the wrong fact, would be a
green light nobody could trust.

Every file is a real DOCX on disk, written by the corpus's own builder; no
mocked filesystem, no provider call.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from binding_support import (
    MOMENT,
    BindingFixture,
    build_binding_fixture,
    feedback_id_of,
    open_the_binding,
    read_dossier,
)
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.application.quality_checks import (
    CHECK_NAMES,
    CheckOutcome,
    RoundQualityReport,
    run_round_quality_checks,
)
from labcairn.papers.binding import (
    DossierManifest,
    ReviewDecision,
    ReviewVerdict,
    apply_approved_edits,
)

pytestmark = pytest.mark.integration

env = _shared_env


@pytest.fixture
def fixture(env: StoreEnv, tmp_path: Path) -> BindingFixture:
    return build_binding_fixture(env.store(), tmp_path / "workspace")


def _decisions(fixture: BindingFixture) -> tuple[ReviewDecision, ...]:
    """The reviewer's sitting: one accepted, one flagged for evidence."""
    return (
        ReviewDecision(
            feedback_id=feedback_id_of(fixture, "c-1"),
            verdict=ReviewVerdict.ACCEPTED,
            operator="Dr. Chen",
            decided_at=MOMENT,
        ),
        ReviewDecision(
            feedback_id=feedback_id_of(fixture, "c-2"),
            verdict=ReviewVerdict.PENDING,
            operator="Dr. Chen",
            decided_at=MOMENT,
            needs_evidence=True,
        ),
    )


def _close_round(fixture: BindingFixture) -> DossierManifest:
    """One healthy round, applied through the binding, and its manifest."""
    opened = open_the_binding(fixture)
    closed = apply_approved_edits(
        fixture.context,
        project_id=fixture.project_id,
        input_version_id=fixture.version_id,
        opened=opened,
        decisions=_decisions(fixture),
        source_root_id=fixture.source_root_id,
        source_key=fixture.source_key,
        output_label="quality-round-1",
        window_end=MOMENT.replace(year=MOMENT.year + 1),
        now=MOMENT,
    )
    return DossierManifest.model_validate_json(read_dossier(fixture, closed.dossier_key))


def _run(
    fixture: BindingFixture, manifest: DossierManifest, *, dossier_artifact_id: str = "d"
) -> RoundQualityReport:
    """The checks over a manifest, addressed at the fixture's own project.

    **The manifest is written as the binding writes it** — into the task
    output area, under a MANIFEST receipt the store holds — so the checks
    read it through the layer's own door, exactly as a real round's dossier
    is read.
    """
    import hashlib

    from labcairn.reports.receipt import (
        ArtifactKind,
        ArtifactProducerKind,
        ArtifactReceipt,
    )

    manifest_bytes = json.dumps(
        manifest.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, indent=2
    ).encode()
    receipt = ArtifactReceipt(
        receipt_id=dossier_artifact_id,
        task_id=str(fixture.context.task_id),
        kind=ArtifactKind.MANIFEST,
        relative_path="revisions/probe/binding-dossier.json",
        content_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        size_bytes=len(manifest_bytes),
        produced_by=ArtifactProducerKind.STAGE,
        producer_id="labcairn.papers.binding",
        derived_from=(),
        media_type="application/json",
        created_at=MOMENT,
    )
    written = fixture.workspace_root / Path(*receipt.relative_path.split("/"))
    written.parent.mkdir(parents=True, exist_ok=True)
    written.write_bytes(manifest_bytes)
    from labcairn.db.repository import TaskStore

    store = TaskStore(fixture.context.store.session)
    with store.unit(fixture.context.task_id) as work_unit:
        work_unit.put_artifact(receipt)
    return run_round_quality_checks(
        fixture.context,
        project_id=fixture.project_id,
        dossier_artifact_id=dossier_artifact_id,
    )


def _outcome(report: RoundQualityReport, check: str) -> CheckOutcome:
    """One check's outcome, from the report."""
    for outcome in report.checks:
        if outcome.check == check:
            return outcome
    raise AssertionError(f"the report carries no {check!r} outcome")


# --------------------------------------------------------------------------- #
# the healthy round
# --------------------------------------------------------------------------- #


def test_a_healthy_round_passes_all_six_checks(fixture: BindingFixture) -> None:
    """The full apply path closes, and every §7.4 check holds."""
    manifest = _close_round(fixture)
    report = _run(fixture, manifest)

    assert [outcome.check for outcome in report.checks] == list(CHECK_NAMES), (
        "the report carries the six checks in §7.4's own order"
    )
    for outcome in report.checks:
        assert outcome.passed, f"{outcome.check} failed: {outcome.facts}"
    assert report.passed
    assert report.input_version_id == fixture.version_id
    assert report.dossier_artifact_id == "d"


def test_the_apply_result_carries_the_rounds_quality_report(
    fixture: BindingFixture,
) -> None:
    """A closed round's apply result carries its own quality report.

    **The report is measured from the round's own manifest**, so the ids it
    carries are the ids the result publishes — one round, one report, and
    not a second derivation of the same facts. The round is the whole
    three-opinion sample, decided the way the binding's own witnesses decide
    it, so the report is the healthy round's.
    """
    from labcairn.application.review import (
        ApplyReviewRequest,
        apply_review,
        record_review_decision,
        record_review_suggestion,
    )

    feedback_id = feedback_id_of(fixture, "c-1")
    record_review_suggestion(
        fixture.context,
        project_id=fixture.project_id,
        version_id=fixture.version_id,
        feedback_id=feedback_id,
        part="word/document.xml",
        paragraph=1,
        old_text="The method estimates the parameter from a single observation.",
        new_text="The method estimates the parameter theta from a single observation.",
        author="substitute-model",
        proposed_at=MOMENT,
    )
    record_review_decision(
        fixture.context,
        project_id=fixture.project_id,
        feedback_id=feedback_id,
        verdict=ReviewVerdict.ACCEPTED.value,
        operator="Dr. Chen",
        decided_at=MOMENT,
    )
    evidence_id = feedback_id_of(fixture, "c-2")
    record_review_suggestion(
        fixture.context,
        project_id=fixture.project_id,
        version_id=fixture.version_id,
        feedback_id=evidence_id,
        part="word/document.xml",
        paragraph=2,
        old_text="The results section reports the measured values.",
        new_text="The results section compares against the measured values.",
        author="substitute-model",
        proposed_at=MOMENT,
    )
    record_review_decision(
        fixture.context,
        project_id=fixture.project_id,
        feedback_id=evidence_id,
        verdict=ReviewVerdict.PENDING.value,
        operator="Dr. Chen",
        needs_evidence=True,
        decided_at=MOMENT,
    )
    result = apply_review(
        fixture.context,
        ApplyReviewRequest(
            project_id=fixture.project_id,
            input_version_id=fixture.version_id,
            source_root_id=fixture.source_root_id,
            source_key=fixture.source_key,
            output_label="quality-round-1",
            window_end=MOMENT.replace(year=MOMENT.year + 1).isoformat(),
        ),
    )
    assert result.quality is not None, "the apply result carries the quality report"
    assert result.quality.passed, f"the healthy round's report passes: {result.quality.checks}"
    assert result.quality.dossier_artifact_id == result.dossier_artifact_id
    assert result.quality.output_version_id == result.output_version_id


# --------------------------------------------------------------------------- #
# 1. opinion coverage
# --------------------------------------------------------------------------- #


def test_opinion_coverage_fails_for_an_opinion_the_round_dropped(
    fixture: BindingFixture,
) -> None:
    """An opinion with no suggestion, decision or task is named as dropped."""
    manifest = _close_round(fixture)
    # The reviewer's accepted decision is the only record that accounts for
    # the evidence-flagged opinion's *suggestion*... remove every record that
    # covers one opinion, and the check must name it.
    manifest = manifest.model_copy(
        update={
            "suggestions": tuple(
                suggestion
                for suggestion in manifest.suggestions
                if suggestion.feedback_id != manifest.opinions[0].feedback_id
            ),
            "decisions": tuple(
                decision
                for decision in manifest.decisions
                if decision.feedback_id != manifest.opinions[0].feedback_id
            ),
            "unresolved": tuple(
                task
                for task in manifest.unresolved
                if task.feedback_id != manifest.opinions[0].feedback_id
            ),
        }
    )
    report = _run(fixture, manifest)
    outcome = _outcome(report, "opinion_coverage")
    assert not outcome.passed
    named = {fact.feedback_id for fact in outcome.facts}
    assert manifest.opinions[0].feedback_id in named, (
        "the check names the opinion the round dropped"
    )


# --------------------------------------------------------------------------- #
# 2. suggestion-to-opinion correspondence
# --------------------------------------------------------------------------- #


def test_suggestion_correspondence_fails_for_a_suggestion_about_nothing(
    fixture: BindingFixture,
) -> None:
    """A suggestion naming an opinion the manifest does not hold is caught."""
    manifest = _close_round(fixture)
    ghost = copy.deepcopy(manifest.suggestions[0].model_dump())
    ghost["feedback_id"] = "fb-ghost-opinion"
    ghost_entry = type(manifest.suggestions[0]).model_validate(ghost)
    manifest = manifest.model_copy(update={"suggestions": (*manifest.suggestions, ghost_entry)})
    report = _run(fixture, manifest)
    outcome = _outcome(report, "suggestion_correspondence")
    assert not outcome.passed
    assert any(fact.feedback_id == "fb-ghost-opinion" for fact in outcome.facts), (
        "the check names the suggestion that answers nothing"
    )


def test_suggestion_correspondence_fails_for_a_suggestion_the_chain_does_not_hold(
    fixture: BindingFixture,
) -> None:
    """A stored suggestion naming an opinion the chain does not hold is caught.

    **The store row is the other place a suggestion lives.** A row written
    under a ``feedback_id`` the chain does not hold is a proposal about
    nothing, even when the manifest itself is clean — and the check reads
    the store beside the manifest for exactly this.
    """
    manifest = _close_round(fixture)
    # **The damaged row is written with the schema's own guard off.** The
    # foreign key the table carries is what makes "a suggestion about an
    # opinion nobody holds" impossible to write in a healthy round — which
    # is the property the chain's own witnesses hold. This witness writes
    # the damaged row anyway, over a raw connection with that guard off —
    # the same way the migration witnesses write their legacy rows — because
    # what it tests is that the *check* still catches the shape if anything
    # ever writes it.
    import sqlite3

    from sqlalchemy import Engine

    bind = fixture.context.store.session.get_bind()
    assert isinstance(bind, Engine), "the fixture's store binds an engine"
    db_path = bind.url.database
    assert db_path, "the fixture's store is a file-backed SQLite database"
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute(
            "INSERT INTO review_suggestions (feedback_id, project_id, version_id, "
            "part, paragraph, old_text, new_text, author, proposed_at, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "fb-not-in-the-chain",
                fixture.project_id,
                fixture.version_id,
                "word/document.xml",
                1,
                "old",
                "new",
                "substitute-model",
                MOMENT.isoformat(),
                MOMENT.isoformat(),
            ),
        )
        connection.commit()
    finally:
        connection.close()
    report = _run(fixture, manifest)
    outcome = _outcome(report, "suggestion_correspondence")
    assert not outcome.passed
    assert any(fact.feedback_id == "fb-not-in-the-chain" for fact in outcome.facts), (
        "the check names the stored suggestion that answers nothing"
    )


# --------------------------------------------------------------------------- #
# 3. modification scope
# --------------------------------------------------------------------------- #


def test_edit_scope_fails_for_an_edit_outside_the_anchored_paragraph(
    fixture: BindingFixture,
) -> None:
    """An edit that landed outside the opinion's anchored paragraph is named.

    **The paragraph mismatch is the fact.** The suggestion's 1-based
    paragraph and the opinion's 0-based anchor must name the same paragraph;
    a suggestion that claims a different paragraph is an edit that reached
    outside the reviewed set.
    """
    manifest = _close_round(fixture)
    suggestion = manifest.suggestions[0]
    opinion = next(
        entry for entry in manifest.opinions if entry.feedback_id == suggestion.feedback_id
    )
    assert opinion.anchor_paragraph is not None
    moved = suggestion.model_copy(update={"paragraph": opinion.anchor_paragraph + 7})
    manifest = manifest.model_copy(
        update={
            "suggestions": tuple(
                moved if entry.feedback_id == suggestion.feedback_id else entry
                for entry in manifest.suggestions
            )
        }
    )
    report = _run(fixture, manifest)
    outcome = _outcome(report, "edit_scope")
    assert not outcome.passed
    fact = next(fact for fact in outcome.facts if fact.feedback_id == suggestion.feedback_id)
    assert fact.paragraph == opinion.anchor_paragraph + 7, (
        "the fact names the paragraph the edit claimed"
    )
    assert fact.expected == str(opinion.anchor_paragraph + 1)
    assert fact.actual == str(opinion.anchor_paragraph + 7)


def test_edit_scope_fails_for_an_edit_on_an_unresolved_anchor(
    fixture: BindingFixture,
) -> None:
    """An applied edit whose opinion has no resolved anchor is named."""
    manifest = _close_round(fixture)
    suggestion = manifest.suggestions[0]
    opinion = next(
        entry for entry in manifest.opinions if entry.feedback_id == suggestion.feedback_id
    )
    moved_opinion = opinion.model_copy(
        update={"anchor_status": "unknown", "anchor_paragraph": None}
    )
    manifest = manifest.model_copy(
        update={
            "opinions": tuple(
                moved_opinion if entry.feedback_id == opinion.feedback_id else entry
                for entry in manifest.opinions
            )
        }
    )
    report = _run(fixture, manifest)
    outcome = _outcome(report, "edit_scope")
    assert not outcome.passed
    assert any(fact.feedback_id == suggestion.feedback_id for fact in outcome.facts), (
        "the check names the edit whose opinion has no anchored paragraph"
    )


# --------------------------------------------------------------------------- #
# 4. evidence completeness
# --------------------------------------------------------------------------- #


def test_evidence_check_fails_when_a_needs_evidence_verdict_leaves_no_task(
    fixture: BindingFixture,
) -> None:
    """A needs-evidence verdict with no unresolved entry is caught."""
    manifest = _close_round(fixture)
    flagged = next(decision for decision in manifest.decisions if decision.needs_evidence)
    manifest = manifest.model_copy(
        update={
            "unresolved": tuple(
                task for task in manifest.unresolved if task.feedback_id != flagged.feedback_id
            )
        }
    )
    report = _run(fixture, manifest)
    outcome = _outcome(report, "evidence_complete")
    assert not outcome.passed
    assert any(fact.feedback_id == flagged.feedback_id for fact in outcome.facts), (
        "the check names the opinion the round promised to remember"
    )


# --------------------------------------------------------------------------- #
# 5. response-table-vs-actual-edits consistency
# --------------------------------------------------------------------------- #


def test_response_table_check_fails_when_a_row_names_an_edit_that_did_not_land(
    fixture: BindingFixture,
) -> None:
    """A response row naming a change the chain does not hold is caught.

    **The tampering is in the manifest's response entry** — the table renders
    from it, so the table now shows a change the chain's own rows do not
    carry. The check names the opinion whose row lies.
    """
    manifest = _close_round(fixture)
    response = manifest.responses[0]
    forged = response.model_copy(update={"edit_action_id": "ea-does-not-exist"})
    manifest = manifest.model_copy(
        update={
            "responses": tuple(
                forged if entry.feedback_id == response.feedback_id else entry
                for entry in manifest.responses
            )
        }
    )
    report = _run(fixture, manifest)
    outcome = _outcome(report, "response_table_consistency")
    assert not outcome.passed
    assert any(fact.feedback_id == response.feedback_id for fact in outcome.facts), (
        "the check names the opinion whose response row names an edit that did not land"
    )


def test_response_table_check_fails_when_a_row_shows_a_change_for_an_unapplied_opinion(
    fixture: BindingFixture,
) -> None:
    """A row that shows a change where nothing was applied is caught."""
    manifest = _close_round(fixture)
    # The unplaceable opinion has no suggestion and nothing applied to it.
    # Give the manifest a response link for it — a row the table renders as a
    # change — and the check must catch the row that names an edit that did
    # not land.
    unapplied = next(
        opinion
        for opinion in manifest.opinions
        if opinion.feedback_id
        not in {suggestion.feedback_id for suggestion in manifest.suggestions}
    )
    from labcairn.papers.binding import ResponseEntry

    forged = ResponseEntry(
        response_link_id="rl-forged",
        feedback_id=unapplied.feedback_id,
        edit_action_id="ea-forged",
        state="addressed",
    )
    manifest = manifest.model_copy(update={"responses": (*manifest.responses, forged)})
    report = _run(fixture, manifest)
    outcome = _outcome(report, "response_table_consistency")
    assert not outcome.passed
    assert any(fact.feedback_id == unapplied.feedback_id for fact in outcome.facts), (
        "the check names the opinion whose row shows a change that never landed"
    )


# --------------------------------------------------------------------------- #
# 6. quality-report-vs-four-deliverables binding consistency
# --------------------------------------------------------------------------- #


def test_report_binding_fails_when_a_drafts_digest_disagrees(
    fixture: BindingFixture,
) -> None:
    """A manifest binding a digest the store's receipt does not carry is caught."""
    manifest = _close_round(fixture)
    tampered = manifest.model_copy(update={"clean_sha256": "0" * 64})
    report = _run(fixture, tampered)
    outcome = _outcome(report, "report_binding")
    assert not outcome.passed
    assert any(fact.expected == "0" * 64 for fact in outcome.facts), (
        "the fact carries the digest the manifest bound"
    )


def test_report_binding_fails_when_the_output_version_is_not_the_marked_draft(
    fixture: BindingFixture,
) -> None:
    """An output version whose hash is not the marked draft's hash is caught.

    **The output version *is* the marked draft, registered** — a manifest
    that binds a different version row under the output id describes a round
    whose deliverables do not bind to one another.
    """
    manifest = _close_round(fixture)
    # Point the manifest's output version at the *input* version, whose hash
    # is the original manuscript's — not the marked draft's.
    manifest = manifest.model_copy(update={"output_version_id": manifest.input_version_id})
    report = _run(fixture, manifest)
    outcome = _outcome(report, "report_binding")
    assert not outcome.passed
    assert any("not the marked draft's hash" in fact.detail for fact in outcome.facts), (
        "the check names the version whose hash disagrees"
    )


def test_report_binding_fails_when_the_rendered_report_loses_an_id(
    fixture: BindingFixture,
) -> None:
    """A report that does not carry an id the manifest binds is caught.

    **The renderer is the deliverable's own.** The check renders the
    manifest through the quality report's own renderer and asks the bytes to
    carry every id — so a renderer that dropped an id, or a manifest whose
    ids do not survive rendering, is caught here rather than by a reader.
    """
    manifest = _close_round(fixture)
    report = _run(fixture, manifest)
    outcome = _outcome(report, "report_binding")
    assert outcome.passed, f"the healthy round's report binds: {outcome.facts}"

    # And the same renderer, asked to print an id the whitelist refuses,
    # fails loudly rather than silently dropping it — the property the check
    # leans on.
    from labcairn.reports.quality_report import render_quality_report_markdown

    with pytest.raises(ValueError):
        render_quality_report_markdown(
            manifest.model_copy(update={"edge_id": "not an id!"}).model_dump_json()
        )
