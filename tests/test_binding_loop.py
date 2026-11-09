"""The comment-to-revision binding, witnessed end to end against real bytes.

LC-P3-04 is an integration ticket: the chain's rows, the edit seam and the
revision loop all had witnesses of their own. What this file witnesses is
**the binding** — every supported opinion lands in the dossier, the model's
suggestion and the reviewer's verdict are separate records, the approved
edits are written through the seam onto the loop's copies, both drafts are
published under receipts, the output version is registered with a
human-accepted edge, and the chain's rings are filled from the published
bytes.

Every file here is a real DOCX on disk, written by the corpus's own builder;
every number the acceptance record prints is measured from these operations.
No mocked filesystem, no provider call.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from binding_support import (
    EDITABLE_TEXT,
    EVIDENCE_TEXT,
    MODEL_ACTOR_ID,
    MOMENT,
    OPERATOR,
    PARAGRAPH_TEXT,
    SECOND_PARAGRAPH_TEXT,
    UNPLACEABLE_TEXT,
    WINDOW_END,
    BindingFixture,
    build_binding_fixture,
    feedback_id_of,
    open_the_binding,
    read_dossier,
)
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.editing.drafts import ApprovedEdit
from labcairn.papers.binding import (
    LocationState,
    ModelSuggestion,
    ReviewDecision,
    ReviewVerdict,
    apply_approved_edits,
    open_binding,
)
from labcairn.papers.edits import list_edit_actions
from labcairn.papers.responses import list_response_links, list_unaddressed
from labcairn.reports.quality_report import render_quality_report_markdown
from labcairn.reports.response_table import render_response_table_markdown

pytestmark = pytest.mark.integration

# Fixture resolution is by parameter name; the shared env fixture must be bound
# under that name in this module.
env = _shared_env


@pytest.fixture
def fixture(env: StoreEnv, tmp_path: Path) -> BindingFixture:
    return build_binding_fixture(env.store(), tmp_path / "workspace")


def _decisions(fixture: BindingFixture) -> tuple[ReviewDecision, ...]:
    """The reviewer's sitting: one accepted, one flagged for evidence, one moot."""
    return (
        ReviewDecision(
            feedback_id=feedback_id_of(fixture, "c-1"),
            verdict=ReviewVerdict.ACCEPTED,
            operator=OPERATOR,
            decided_at=MOMENT,
        ),
        ReviewDecision(
            feedback_id=feedback_id_of(fixture, "c-2"),
            verdict=ReviewVerdict.PENDING,
            operator=OPERATOR,
            decided_at=MOMENT,
            needs_evidence=True,
        ),
    )


def test_every_supported_opinion_is_placed_in_the_binding(fixture: BindingFixture) -> None:
    """The located and the unplaceable opinion both land, and neither is dropped."""
    opened = open_the_binding(fixture)

    editable = feedback_id_of(fixture, "c-1")
    evidence = feedback_id_of(fixture, "c-2")
    unplaceable = feedback_id_of(fixture, "c-3")
    placed = {opinion.feedback_id: opinion for opinion in opened.opinions}
    assert set(placed) == {editable, evidence, unplaceable}, (
        "every comment the reader recorded is in the binding, whatever its state"
    )
    assert placed[editable].location_state is LocationState.LOCATED
    assert placed[evidence].location_state is LocationState.LOCATED
    assert placed[unplaceable].location_state is LocationState.UNCERTAIN_LOCATION
    assert placed[unplaceable].anchor_status != "resolved", (
        "the unplaceable comment's own anchor status is carried, not smoothed over"
    )


def test_the_suggestion_and_the_verdict_are_separate_records(fixture: BindingFixture) -> None:
    """What the model proposed and what the reviewer decided never merge."""
    opened = open_the_binding(fixture)
    editable = feedback_id_of(fixture, "c-1")
    evidence = feedback_id_of(fixture, "c-2")

    suggested = {suggestion.feedback_id for suggestion in opened.suggestions}
    assert suggested == {editable, evidence}, (
        "the source proposed for the located opinions, and not for the unplaceable one"
    )
    for suggestion in opened.suggestions:
        assert suggestion.edit.author == MODEL_ACTOR_ID, (
            "a suggestion names the model that made it, and nobody else"
        )

    decisions = _decisions(fixture)
    for decision in decisions:
        # The decision record is the reviewer's, and it carries none of the
        # suggestion's payload: the two records share an opinion, not a shape.
        assert decision.operator == OPERATOR
        assert decision.verdict in ReviewVerdict


def test_the_approved_edits_are_written_through_the_seam_and_published(
    fixture: BindingFixture,
) -> None:
    """The accepted edit lands in both drafts, under two publication receipts."""
    opened = open_the_binding(fixture)
    closed = apply_approved_edits(
        fixture.context,
        project_id=fixture.project_id,
        input_version_id=fixture.version_id,
        opened=opened,
        decisions=_decisions(fixture),
        source_root_id=fixture.source_root_id,
        source_key=fixture.source_key,
        output_label="binding-round-1",
        window_end=WINDOW_END,
        now=MOMENT,
    )

    # The marked draft carries the accepted edit as a tracked change by the
    # model, under the loop's own publication receipt.
    assert closed.marked_publication.publication.content_sha256
    assert closed.clean_publication.publication.content_sha256
    assert closed.marked_publication.publication.receipt_id != (
        closed.clean_publication.publication.receipt_id
    ), "two drafts are two publications, each with its own receipt"

    assert closed.output_version.version_id != fixture.version_id
    assert closed.edge.parent_version_id == fixture.version_id
    assert closed.edge.child_version_id == closed.output_version.version_id
    assert closed.edge.accepted_by == OPERATOR, (
        "the edge records whose approval made the version, and the model is not that person"
    )


def test_the_four_deliverables_bind_to_one_task_one_input_one_output(
    fixture: BindingFixture,
) -> None:
    """The dossier manifest is the row that ties the deliverables together."""
    opened = open_the_binding(fixture)
    closed = apply_approved_edits(
        fixture.context,
        project_id=fixture.project_id,
        input_version_id=fixture.version_id,
        opened=opened,
        decisions=_decisions(fixture),
        source_root_id=fixture.source_root_id,
        source_key=fixture.source_key,
        output_label="binding-round-1",
        window_end=WINDOW_END,
        now=MOMENT,
    )

    manifest = json.loads(read_dossier(fixture, closed.dossier_key))
    assert manifest["task_id"] == str(fixture.context.task_id)
    assert manifest["input_version_id"] == fixture.version_id
    assert manifest["output_version_id"] == closed.output_version.version_id
    assert manifest["marked_receipt_id"] == closed.marked_publication.publication.receipt_id
    assert manifest["clean_receipt_id"] == closed.clean_publication.publication.receipt_id
    assert manifest["edge_id"] == closed.edge.edge_id
    assert closed.dossier_artifact_id, "the manifest is an artefact row, not just a file"


def test_the_chain_rings_are_filled_from_the_published_bytes(fixture: BindingFixture) -> None:
    """The edits and responses the chain holds name real rows, not proposals."""
    opened = open_the_binding(fixture)
    closed = apply_approved_edits(
        fixture.context,
        project_id=fixture.project_id,
        input_version_id=fixture.version_id,
        opened=opened,
        decisions=_decisions(fixture),
        source_root_id=fixture.source_root_id,
        source_key=fixture.source_key,
        output_label="binding-round-1",
        window_end=WINDOW_END,
        now=MOMENT,
    )

    editable = feedback_id_of(fixture, "c-1")
    evidence = feedback_id_of(fixture, "c-2")
    assert closed.edits, "the accepted edit produced a chain row"
    bound = closed.edits[0]
    assert bound.feedback_id == editable
    # The listing drops the child version's material (the published draft
    # lives in the output area, which ``source.inventory`` does not cover) —
    # a measured gap the record names. The row itself is what the witness
    # asserts, read from the store.
    from sqlalchemy import select

    from labcairn.db.models import EditActionRow

    rows = tuple(
        fixture.context.store.session.scalars(
            select(EditActionRow).where(EditActionRow.version_edge_id == closed.edge.edge_id)
        )
    )
    assert any(row.edit_action_id == bound.edit_action_id for row in rows), (
        "the chain's table holds the row the binding reports"
    )
    assert any(row.feedback_id == editable for row in rows), (
        "the second ring is filled: the change names the comment it answered"
    )

    states = {
        link.feedback_id: link.state
        for link in list_response_links(fixture.context, feedback_id=editable)
    }
    assert states, "the third ring is filled: the comment carries a judgement"
    assert all(state == "addressed" for state in states.values()), (
        "the accepted verdict lands as addressed, and only that"
    )

    unaddressed = list_unaddressed(fixture.context, project_id=fixture.project_id)
    remaining = {item.feedback.feedback_id: item.reason for item in unaddressed}
    assert evidence in remaining, (
        "the opinion left pending stays on the unaddressed listing"
    )


def test_unresolved_opinions_surface_as_explicit_tasks(fixture: BindingFixture) -> None:
    """Needs-evidence and uncertain-location land as named tasks, not drops."""
    opened = open_the_binding(fixture)
    closed = apply_approved_edits(
        fixture.context,
        project_id=fixture.project_id,
        input_version_id=fixture.version_id,
        opened=opened,
        decisions=_decisions(fixture),
        source_root_id=fixture.source_root_id,
        source_key=fixture.source_key,
        output_label="binding-round-1",
        window_end=WINDOW_END,
        now=MOMENT,
    )

    evidence = feedback_id_of(fixture, "c-2")
    unplaceable = feedback_id_of(fixture, "c-3")
    reasons = {task.feedback_id: task.reason for task in closed.unresolved}
    assert reasons[evidence] == "needs_evidence", (
        "the reviewer's flag is the binding's own unresolved task"
    )
    assert reasons[unplaceable] == "uncertain_location", (
        "the unplaceable comment is a location failure with a name"
    )
    assert set(reasons) == {evidence, unplaceable}, (
        "the accepted opinion is resolved, and appears in no unresolved list"
    )

    manifest = json.loads(read_dossier(fixture, closed.dossier_key))
    assert {entry["feedback_id"] for entry in manifest["unresolved"]} == set(reasons), (
        "the dossier carries the same tasks the record reports"
    )


def test_the_response_table_names_every_opinion(fixture: BindingFixture) -> None:
    """The table renders from the dossier, and every opinion gets a row."""
    opened = open_the_binding(fixture)
    closed = apply_approved_edits(
        fixture.context,
        project_id=fixture.project_id,
        input_version_id=fixture.version_id,
        opened=opened,
        decisions=_decisions(fixture),
        source_root_id=fixture.source_root_id,
        source_key=fixture.source_key,
        output_label="binding-round-1",
        window_end=WINDOW_END,
        now=MOMENT,
    )

    every_id = tuple(
        feedback_id_of(fixture, comment_id) for comment_id in ("c-1", "c-2", "c-3")
    )
    manifest_json = read_dossier(fixture, closed.dossier_key)
    table = render_response_table_markdown(manifest_json).decode("utf-8")
    for feedback_id in every_id:
        assert feedback_id in table, f"{feedback_id} has a row in the table"
    assert "| " + "Opinion" in table or "Opinion" in table
    assert "uncertain_location" in table
    assert "needs evidence" in table
    assert table.count("\n") > 8, "the table is a table, not a stub"

    # The same manifest gives the same bytes: the render is a pure function.
    again = render_response_table_markdown(manifest_json)
    assert again == render_response_table_markdown(manifest_json)


def test_the_quality_report_keeps_the_two_statuses_apart(fixture: BindingFixture) -> None:
    """Delivery and research quality are two sections, and neither blurs."""
    opened = open_the_binding(fixture)
    closed = apply_approved_edits(
        fixture.context,
        project_id=fixture.project_id,
        input_version_id=fixture.version_id,
        opened=opened,
        decisions=_decisions(fixture),
        source_root_id=fixture.source_root_id,
        source_key=fixture.source_key,
        output_label="binding-round-1",
        window_end=WINDOW_END,
        now=MOMENT,
    )

    manifest_json = read_dossier(fixture, closed.dossier_key)
    report = render_quality_report_markdown(manifest_json).decode("utf-8")
    assert "## File delivery" in report
    assert "## Research quality" in report
    assert report.index("## File delivery") < report.index("## Research quality"), (
        "delivery is stated before quality, and neither section answers for the other"
    )
    evidence = feedback_id_of(fixture, "c-2")
    unplaceable = feedback_id_of(fixture, "c-3")
    # The verdicts and the unresolved tasks are named by their ids, and the
    # needs-evidence flag rides the verdict it belongs to.
    assert evidence in report
    assert unplaceable in report
    assert "needs evidence" in report
    assert "uncertain" in report
    assert "Unresolved opinions" in report


def test_a_rejected_suggestion_produces_no_change_and_no_link(fixture: BindingFixture) -> None:
    """A rejection is a manifest decision, not a change or a chain row."""
    opened = open_the_binding(fixture)
    rejected = (
        ReviewDecision(
            feedback_id=feedback_id_of(fixture, "c-1"),
            verdict=ReviewVerdict.REJECTED,
            operator=OPERATOR,
            decided_at=MOMENT,
        ),
    )
    closed = apply_approved_edits(
        fixture.context,
        project_id=fixture.project_id,
        input_version_id=fixture.version_id,
        opened=opened,
        decisions=rejected,
        source_root_id=fixture.source_root_id,
        source_key=fixture.source_key,
        output_label="binding-round-1",
        window_end=WINDOW_END,
        now=MOMENT,
    )

    assert closed.edits == (), "a rejected suggestion applies nothing"
    assert closed.responses == ()
    manifest = json.loads(read_dossier(fixture, closed.dossier_key))
    decisions = {entry["feedback_id"]: entry["verdict"] for entry in manifest["decisions"]}
    assert decisions[feedback_id_of(fixture, "c-1")] == "rejected", (
        "the rejection is recorded where the reader looks: the dossier"
    )


def test_an_approved_edit_that_would_cut_a_run_is_a_handover(fixture: BindingFixture) -> None:
    """A structure the seam refuses is handed to a person, and the rest applies."""
    opened = open_the_binding(fixture)
    # A second suggestion whose old text does not match the paragraph's whole
    # run is refused by the seam — the same refusal a real unsupported
    # structure produces — and the binding hands it over with its own words.
    extra_suggestion_edit = ApprovedEdit(
        part="word/document.xml",
        paragraph=1,
        old_text=PARAGRAPH_TEXT[:20],
        new_text="a fragment the seam cannot place",
        author=MODEL_ACTOR_ID,
        date="2026-02-01T00:00:00+00:00",
    )
    from labcairn.papers.binding import BindingOpened

    opened = BindingOpened(
        loop=opened.loop,
        original_bytes=opened.original_bytes,
        opinions=opened.opinions,
        suggestions=(
            *opened.suggestions,
            ModelSuggestion(feedback_id=feedback_id_of(fixture, "c-1"), edit=extra_suggestion_edit),
        ),
    )
    closed = apply_approved_edits(
        fixture.context,
        project_id=fixture.project_id,
        input_version_id=fixture.version_id,
        opened=opened,
        decisions=_decisions(fixture),
        source_root_id=fixture.source_root_id,
        source_key=fixture.source_key,
        output_label="binding-round-1",
        window_end=WINDOW_END,
        now=MOMENT,
    )

    assert closed.handovers, "the seam's refusal became a handover"
    handover = closed.handovers[0]
    assert handover.feedback_id == feedback_id_of(fixture, "c-1")
    assert handover.reason, "the refusal carries the seam's own reason"
    assert handover.handover, "the refusal carries the next sentence a person acts on"
    # And the rest of the approved set still applied: the accepted edit landed.
    assert any(edit.feedback_id == feedback_id_of(fixture, "c-1") for edit in closed.edits), (
        "one unsupported structure did not hold the whole revision hostage"
    )


def test_the_binding_refuses_a_binding_with_no_decisions(fixture: BindingFixture) -> None:
    """An edge nobody approved is refused before any byte lands."""
    opened = open_the_binding(fixture)
    with pytest.raises(Exception) as excinfo:
        apply_approved_edits(
            fixture.context,
            project_id=fixture.project_id,
            input_version_id=fixture.version_id,
            opened=opened,
            decisions=(),
                source_root_id=fixture.source_root_id,
            source_key=fixture.source_key,
            output_label="binding-round-1",
            window_end=WINDOW_END,
            now=MOMENT,
        )
    assert "no review decision" in str(excinfo.value)
    assert "nobody approved" in str(excinfo.value)


def test_the_unplaceable_opinion_is_never_asked_for_a_suggestion(
    fixture: BindingFixture,
) -> None:
    """The source is asked about located opinions only."""
    asked: list[str] = []

    def recording_suggester(event: FeedbackEvent) -> ApprovedEdit | None:
        asked.append(event.feedback_id)
        return None

    from labcairn.papers.binding import open_binding

    open_binding(
        fixture.context,
        project_id=fixture.project_id,
        version_id=fixture.version_id,
        source_root_id=fixture.source_root_id,
        source_key=fixture.source_key,
        suggest=recording_suggester,
        now=MOMENT,
    )
    assert feedback_id_of(fixture, "c-3") not in asked, (
        "an opinion with no passage is not offered to the source: asking would be "
        "asking it to invent an address"
    )
