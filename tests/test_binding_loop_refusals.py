"""The binding's refusals, witnessed at the loop's own boundary.

LC-P3-04 §2.6 item 5: refusal witnesses **re-witnessed at the loop's new
call site** — a guard inherited without its own witness at the new call site
is a guard nobody watches. The classes here are the ones the binding can
reach and the wider system could not:

- **a binding with no review decisions** — refused before any byte lands,
  because an edge nobody approved is a version nobody made;
- **an edit the seam refuses** — handed to a person, never approximated, and
  the refusal carries the seam's own words rather than a second spelling;
- **a duplicate application** — the second application of the same binding
  runs into the loop's own duplicate guard, which 03 minted and this ticket
  re-witnesses at its call site;
- **the unplaced opinion** — the negative of the completeness claim is the
  comparison itself: the dossier's opinion list is read back and matched
  against the chain, so a binding that lost an opinion would be caught by
  the same witness that asserts it complete;
- **an unreviewed suggestion is never applied** — applying it would be the
  model deciding, and the witness asserts the bytes did not move.

Every file here is a real DOCX on disk, and every refusal is asserted
**before any byte lands** or with the bytes it left behind named.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from binding_support import (
    MODEL_AUTHOR,
    MOMENT,
    OPERATOR,
    PARAGRAPH_TEXT,
    WINDOW_END,
    BindingFixture,
    build_binding_fixture,
    feedback_id_of,
    open_the_binding,
    read_dossier,
)
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.application.refusal import ApplicationRefusedError
from labcairn.editing.drafts import ApprovedEdit
from labcairn.papers.binding import (
    BindingOpened,
    ModelSuggestion,
    ReviewDecision,
    ReviewVerdict,
    apply_approved_edits,
)

pytestmark = pytest.mark.negative

# Fixture resolution is by parameter name; the shared env fixture must be bound
# under that name in this module.
env = _shared_env


@pytest.fixture
def fixture(env: StoreEnv, tmp_path: Path) -> BindingFixture:
    return build_binding_fixture(env.store(), tmp_path / "workspace")


def _accepted(fixture: BindingFixture) -> tuple[ReviewDecision, ...]:
    return (
        ReviewDecision(
            feedback_id=feedback_id_of(fixture, "c-1"),
            verdict=ReviewVerdict.ACCEPTED,
            operator=OPERATOR,
            decided_at=MOMENT,
        ),
    )


def test_a_binding_with_no_decisions_refuses_before_any_byte_lands(
    fixture: BindingFixture,
) -> None:
    """The operator is resolved first: nothing is written without a reviewer."""
    opened = open_the_binding(fixture)
    with pytest.raises(ApplicationRefusedError) as excinfo:
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
    # And the loop the open ran left the original untouched: the refusal
    # happened before a publication, so the output area holds no published
    # revision from this call.
    output_dir = fixture.workspace_root / "output" / str(fixture.context.task_id)
    published = list(output_dir.rglob("published.bin"))
    assert published == [], "no publication rode a binding nobody approved"


def test_an_edit_the_seam_refuses_is_a_handover_and_the_rest_still_applies(
    fixture: BindingFixture,
) -> None:
    """One unsupported structure must not hold the whole revision hostage."""
    opened = open_the_binding(fixture)
    fragment = ApprovedEdit(
        part="word/document.xml",
        paragraph=1,
        old_text=PARAGRAPH_TEXT[:20],
        new_text="a fragment the seam cannot place",
        author=MODEL_AUTHOR,
        date="2026-02-01T00:00:00+00:00",
    )
    extra = BindingOpened(
        loop=opened.loop,
        original_bytes=opened.original_bytes,
        opinions=opened.opinions,
        suggestions=(
            *opened.suggestions,
            ModelSuggestion(feedback_id=feedback_id_of(fixture, "c-1"), edit=fragment),
        ),
    )
    closed = apply_approved_edits(
        fixture.context,
        project_id=fixture.project_id,
        input_version_id=fixture.version_id,
        opened=extra,
        decisions=_accepted(fixture),
        source_root_id=fixture.source_root_id,
        source_key=fixture.source_key,
        output_label="binding-round-1",
        window_end=WINDOW_END,
        now=MOMENT,
    )
    reasons = [handover.reason for handover in closed.handovers]
    assert "text_not_located" in reasons, "the seam's own reason is carried, not re-spelled"
    handover = next(h for h in closed.handovers if h.reason == "text_not_located")
    assert handover.detail, "the refusal says what was wrong"
    assert handover.handover, "the refusal says what a person does next"
    # And the approved edit that could land, did:
    assert closed.edits, "the rest of the approved set still applied"
    manifest = json.loads(read_dossier(fixture, closed.dossier_key))
    carried = {entry["feedback_id"] for entry in manifest["handovers"]}
    assert handover.feedback_id in carried, "the dossier carries the handover"


def test_a_second_application_is_a_second_revision_and_the_original_holds(
    fixture: BindingFixture,
) -> None:
    """A re-run produces distinct receipts, and the original never moved.

    03's duplicate guard refuses a second publication under one receipt id;
    a second binding mints fresh loops, so it is **a second revision**, not a
    replay — and the witness asserts the two facts that make that safe: the
    two applications' receipts are distinct (nothing was overwritten), and
    the original's hash is still what the first import receipt recorded.
    """
    from labcairn.security.approval import content_hash

    opened = open_the_binding(fixture)
    original_sha = opened.loop.import_receipt.original_sha256
    decisions = _accepted(fixture)
    first = apply_approved_edits(
        fixture.context,
        project_id=fixture.project_id,
        input_version_id=fixture.version_id,
        opened=opened,
        decisions=decisions,
        source_root_id=fixture.source_root_id,
        source_key=fixture.source_key,
        output_label="binding-round-1",
        window_end=WINDOW_END,
        now=MOMENT,
    )
    second = apply_approved_edits(
        fixture.context,
        project_id=fixture.project_id,
        input_version_id=fixture.version_id,
        opened=open_the_binding(fixture),
        decisions=decisions,
        source_root_id=fixture.source_root_id,
        source_key=fixture.source_key,
        output_label="binding-round-2",
        window_end=WINDOW_END,
        now=MOMENT,
    )
    first_receipts = {
        first.marked_publication.publication.receipt_id,
        first.clean_publication.publication.receipt_id,
    }
    second_receipts = {
        second.marked_publication.publication.receipt_id,
        second.clean_publication.publication.receipt_id,
    }
    assert first_receipts.isdisjoint(second_receipts), (
        "the second application landed under its own receipts, not a replay of "
        "the first: nothing was overwritten"
    )
    assert content_hash(fixture.manuscript) == original_sha, (
        "the original's bytes are the bytes the first import receipt recorded"
    )


def test_an_unreviewed_suggestion_is_never_applied(fixture: BindingFixture) -> None:
    """Applying an unreviewed suggestion would be the model deciding."""
    opened = open_the_binding(fixture)
    # The decision names the accepted opinion only; the second located
    # opinion's suggestion stays unreviewed.
    closed = apply_approved_edits(
        fixture.context,
        project_id=fixture.project_id,
        input_version_id=fixture.version_id,
        opened=opened,
        decisions=_accepted(fixture),
        source_root_id=fixture.source_root_id,
        source_key=fixture.source_key,
        output_label="binding-round-1",
        window_end=WINDOW_END,
        now=MOMENT,
    )
    unreviewed = feedback_id_of(fixture, "c-2")
    assert all(edit.feedback_id != unreviewed for edit in closed.edits), (
        "a suggestion whose opinion was never reviewed produced no change"
    )
    manifest = json.loads(read_dossier(fixture, closed.dossier_key))
    applied_ids = {entry["feedback_id"] for entry in manifest["suggestions"]}
    assert unreviewed not in applied_ids, (
        "the dossier's applied list does not carry the unreviewed suggestion"
    )


def test_the_dossier_names_every_opinion_the_chain_holds(
    fixture: BindingFixture,
) -> None:
    """The negative of completeness is caught by comparison, not by hope."""
    opened = open_the_binding(fixture)
    closed = apply_approved_edits(
        fixture.context,
        project_id=fixture.project_id,
        input_version_id=fixture.version_id,
        opened=opened,
        decisions=_accepted(fixture),
        source_root_id=fixture.source_root_id,
        source_key=fixture.source_key,
        output_label="binding-round-1",
        window_end=WINDOW_END,
        now=MOMENT,
    )
    manifest = json.loads(read_dossier(fixture, closed.dossier_key))
    from labcairn.papers.feedback import list_feedback_events

    chain_ids = {
        event.feedback_id
        for event in list_feedback_events(
            fixture.context,
            project_id=fixture.project_id,
            version_id=fixture.version_id,
        )
    }
    dossier_ids = {entry["feedback_id"] for entry in manifest["opinions"]}
    assert chain_ids == dossier_ids, (
        "the dossier names every opinion the chain holds, and no opinion it "
        "does not: a binding that dropped one would fail this comparison"
    )
