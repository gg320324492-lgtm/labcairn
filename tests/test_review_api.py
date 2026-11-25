"""The review workbench's API, witnessed end to end against real bytes.

The workbench's three columns read one round: the opinions (left), the
manuscript (middle), and the suggestions with their verdicts (right). What
this file witnesses is the seam between that workbench and the binding —
**the opinions read with their suggestion and their decision as separate
records, the manuscript read in the feedback reader's own numbering, a
verdict refused on nothing, and the apply step reading the approved set
from the store** — with a real commented DOCX on disk and no provider call.

The fixture is the binding's own three-case sample, so an opinion the
service reads here is the opinion the binding's own witnesses read — one
sample, two surfaces.
"""

from __future__ import annotations

import base64
import hashlib
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from binding_support import (
    EDITABLE_TEXT,
    MODEL_AUTHOR,
    MOMENT,
    PARAGRAPH_TEXT,
    BindingFixture,
    build_binding_fixture,
    feedback_id_of,
)
from fastapi.testclient import TestClient
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.api.app import create_app
from labcairn.application.context import ApplicationContext
from labcairn.papers.binding import ReviewVerdict
from labcairn.papers.feedback import record_feedback
from labcairn.security.policy import Permission, PermissionPolicy, Rule

pytestmark = pytest.mark.integration

env = _shared_env


#: The approvals' expiry — an hour past the **real** clock, taken at the
#: call, not at the import. The apply round runs through the service, whose
#: clock is the wall clock, and a window anchored to the fixture's fixed
#: moment would already be closed. A module-level constant would go stale in
#: a long suite — the whole tree ran for over an hour once, and every apply
#: in this file met a window that had closed while earlier tests ran — so
#: the window is computed where the apply asks for it.
def _window() -> datetime:
    """An approval window that outlives this call, from the real clock."""
    return datetime.now(UTC) + timedelta(hours=1)


def _record_comments(fixture: BindingFixture) -> None:
    """Record the sample's comments through the product's own door.

    **The import precedes the review.** The workbench reads the opinions
    the import recorded; it does not record them itself — a read that wrote
    would be a side effect hiding in a GET. This is the same door the
    binding's open and the trial's import step walk.

    **And the fixture's session ends its transaction here.** Every read
    takes SQLite's write lock under ``BEGIN IMMEDIATE``, and the fixture's
    session outlives the requests — so the transaction is ended before the
    service's forked sessions ask for the lock, the same courtesy
    ``tests/test_api.py``'s own setup extends.
    """
    record_feedback(
        fixture.context,
        project_id=fixture.project_id,
        version_id=fixture.version_id,
        now=MOMENT,
    )
    fixture.context.store.session.commit()


def _feedback_id(fixture: BindingFixture, comment_id: str) -> str:
    """The opinion's id, with the fixture's transaction ended after it."""
    found = feedback_id_of(fixture, comment_id)
    fixture.context.store.session.commit()
    return found


@pytest.fixture
def fixture(env: StoreEnv, tmp_path: Path) -> BindingFixture:
    return build_binding_fixture(env.store(), tmp_path / "workspace")


class _NoEvents:
    """An event source that serves nothing: the review routes do not stream.

    It satisfies the ``EventSource`` protocol's shape, and it is never
    reached — the review witnesses call no stream route. A stream call
    would be a test of a route this file does not exercise, and the
    service's own unwired refusal is what a stream caller would meet.
    """

    def page(self, session: Any, request: Any) -> Any:
        raise NotImplementedError("the review witnesses read no event stream")


@pytest.fixture
def client(fixture: BindingFixture) -> Iterator[tuple[TestClient, str]]:
    """A client for the service, with the fixture's context behind it."""
    context: ApplicationContext = fixture.context
    app = create_app(context, event_source=_NoEvents())
    with TestClient(app) as wired:
        session = wired.get("/session")
        assert session.status_code == 200
        token = str(session.json()["token"])
        yield wired, token


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _opinions(client: TestClient, token: str, fixture: BindingFixture) -> list[dict[str, Any]]:
    response = client.get(
        "/review/opinions",
        params={"project_id": fixture.project_id, "version_id": fixture.version_id},
        headers=_headers(token),
    )
    assert response.status_code == 200, response.text
    return list(response.json()["opinions"])


def _manuscript(client: TestClient, token: str, fixture: BindingFixture) -> dict[str, Any]:
    response = client.get(
        "/review/manuscript",
        params={"project_id": fixture.project_id, "version_id": fixture.version_id},
        headers=_headers(token),
    )
    assert response.status_code == 200, response.text
    return dict(response.json())


def _store_suggestion(
    client: TestClient,
    token: str,
    fixture: BindingFixture,
    feedback_id: str,
    *,
    paragraph: int = 1,
    old_text: str = PARAGRAPH_TEXT,
) -> dict[str, Any]:
    body = {
        "project_id": fixture.project_id,
        "version_id": fixture.version_id,
        "feedback_id": feedback_id,
        "part": "word/document.xml",
        "paragraph": paragraph,
        "old_text": old_text,
        "new_text": old_text.replace("estimates", "re-estimates"),
        "author": MODEL_AUTHOR,
    }
    response = client.post("/review/suggestion", json=body, headers=_headers(token))
    assert response.status_code == 201, response.text
    return dict(response.json())


# --------------------------------------------------------------------------- #
# the opinion read
# --------------------------------------------------------------------------- #


def test_every_opinion_is_listed_with_its_state(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The three-case sample lands in the binding's own vocabulary.

    **An opinion the chain holds is an opinion the read carries**, whatever
    its state: the editable comment is located, the unplaceable one is an
    uncertain location with its anchor's own status carried beside it. An
    opinion absent from this list would be an opinion the workbench cannot
    show, which is the one outcome the binding exists to make impossible.
    """
    _record_comments(fixture)
    wired, token = client
    opinions = _opinions(wired, token, fixture)
    assert len(opinions) == 3
    by_text = {opinion["comment_text"]: opinion for opinion in opinions}
    assert by_text[EDITABLE_TEXT]["location_state"] == "located"
    unplaceable = by_text["This whole section needs work."]
    assert unplaceable["location_state"] == "uncertain_location"
    assert unplaceable["anchor_status"] == "unknown"
    assert unplaceable["anchor_reason"]


def test_a_suggestion_and_its_decision_are_separate_records(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The stored proposal and the stored verdict travel as separate fields.

    **ADR-0016's rule, at the surface.** Before either is written both are
    ``None``; after the suggestion is written only ``suggestion`` is set; a
    pending verdict fills ``decision`` without touching ``suggestion``. A
    reader who wants the model's words reads one field; a reader who wants
    the reviewer's reads the other; neither says anything about the other.
    """
    _record_comments(fixture)
    wired, token = client
    feedback_id = _feedback_id(fixture, "c-1")
    (opinion,) = [o for o in _opinions(wired, token, fixture) if o["feedback_id"] == feedback_id]
    assert opinion["suggestion"] is None
    assert opinion["decision"] is None

    stored = _store_suggestion(wired, token, fixture, feedback_id)
    assert stored["old_text"] == PARAGRAPH_TEXT
    (opinion,) = [o for o in _opinions(wired, token, fixture) if o["feedback_id"] == feedback_id]
    assert opinion["suggestion"]["new_text"] != opinion["suggestion"]["old_text"]
    assert opinion["decision"] is None

    response = wired.post(
        "/review/decision",
        json={
            "project_id": fixture.project_id,
            "feedback_id": feedback_id,
            "verdict": "pending",
            "operator": "Dr. Chen",
        },
        headers=_headers(token),
    )
    assert response.status_code == 200, response.text
    (opinion,) = [o for o in _opinions(wired, token, fixture) if o["feedback_id"] == feedback_id]
    assert opinion["decision"]["verdict"] == "pending"
    assert opinion["decision"]["operator"] == "Dr. Chen"
    # **The suggestion did not move.** A verdict is a read of the proposal,
    # never a write to it.
    assert opinion["suggestion"]["old_text"] == stored["old_text"]


def test_the_opinion_read_names_the_chain_states(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The response states travel with the opinion they belong to.

    The chain's judgements are the fourth fact the workbench renders; a
    read that omitted them would send the workbench back to
    ``/trajectory`` for a second answer to a question this read already
    holds.
    """
    _record_comments(fixture)
    wired, token = client
    for opinion in _opinions(wired, token, fixture):
        assert isinstance(opinion["response_states"], list)


# --------------------------------------------------------------------------- #
# the manuscript read
# --------------------------------------------------------------------------- #


def test_the_manuscript_is_read_in_the_anchor_numbering(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The paragraphs are 1-based, in document order, and the anchor matches.

    The workbench's scroll-sync is an equality test between an opinion's
    ``anchor_paragraph`` and a paragraph's ``index`` — so the two must be
    the same numbering, and this witness holds the sample's own first
    comment to it.
    """
    _record_comments(fixture)
    wired, token = client
    manuscript = _manuscript(wired, token, fixture)
    assert manuscript["project_id"] == fixture.project_id
    assert manuscript["version_id"] == fixture.version_id
    assert manuscript["sha256"]
    paragraphs = manuscript["paragraphs"]
    assert [p["index"] for p in paragraphs] == [1, 2, 3]
    assert paragraphs[0]["text"] == PARAGRAPH_TEXT

    opinions = _opinions(wired, token, fixture)
    located = [o for o in opinions if o["location_state"] == "located"]
    assert located, "the sample carries a located opinion"
    anchored = {o["anchor_paragraph"] for o in located}
    indexes = {p["index"] for p in paragraphs}
    assert anchored & indexes, "an anchor lands on a paragraph the read names"


# --------------------------------------------------------------------------- #
# the decision write
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("verdict", ["accepted", "partly_accepted"])
def test_an_acceptance_without_a_suggestion_is_refused(
    client: tuple[TestClient, str], fixture: BindingFixture, verdict: str
) -> None:
    """A verdict on nothing is refused, not recorded.

    **Reviewing a proposal nobody made would be a decision about nothing** —
    the record would say a decision was made, and nothing was behind it. The
    refusal is the layer's own vocabulary, so the surface renders the same
    two fields it renders for every other refusal.
    """
    _record_comments(fixture)
    wired, token = client
    feedback_id = _feedback_id(fixture, "c-1")
    response = wired.post(
        "/review/decision",
        json={
            "project_id": fixture.project_id,
            "feedback_id": feedback_id,
            "verdict": verdict,
            "operator": "Dr. Chen",
        },
        headers=_headers(token),
    )
    assert response.status_code == 403
    payload = response.json()
    assert payload["reason"] == "arguments_invalid"
    assert "no stored suggestion" in payload["message"]


def test_a_verdict_on_an_unknown_opinion_is_refused(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The chain holds the opinions; a verdict about another one decides nothing."""
    _record_comments(fixture)
    wired, token = client
    response = wired.post(
        "/review/decision",
        json={
            "project_id": fixture.project_id,
            "feedback_id": "fb-does-not-exist",
            "verdict": "rejected",
            "operator": "Dr. Chen",
        },
        headers=_headers(token),
    )
    assert response.status_code == 403
    assert response.json()["reason"] == "chain_feedback_not_found"


def test_a_verdict_outside_the_vocabulary_is_refused(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The four words are closed; a fifth is a typo, and a typo is loud."""
    _record_comments(fixture)
    wired, token = client
    feedback_id = _feedback_id(fixture, "c-1")
    response = wired.post(
        "/review/decision",
        json={
            "project_id": fixture.project_id,
            "feedback_id": feedback_id,
            "verdict": "maybe",
            "operator": "Dr. Chen",
        },
        headers=_headers(token),
    )
    # **The vocabulary is the contract's `Literal`.** A word outside the four
    # is refused at the wire, before the layer is reached — 422, the same
    # answer a typo'd field name would get.
    assert response.status_code == 422


def test_a_revised_verdict_stands_alone(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The store holds the verdict that stands, not the history of the asks.

    **One row per opinion.** A reviewer who revises writes the row again;
    the read then answers with the revision, and the apply step applies
    what the read answers.
    """
    _record_comments(fixture)
    wired, token = client
    feedback_id = _feedback_id(fixture, "c-1")
    _store_suggestion(wired, token, fixture, feedback_id)
    for verdict in ("rejected", "accepted"):
        response = wired.post(
            "/review/decision",
            json={
                "project_id": fixture.project_id,
                "feedback_id": feedback_id,
                "verdict": verdict,
                "operator": "Dr. Chen",
            },
            headers=_headers(token),
        )
        assert response.status_code == 200, response.text
    (opinion,) = [o for o in _opinions(wired, token, fixture) if o["feedback_id"] == feedback_id]
    assert opinion["decision"]["verdict"] == "accepted"


def test_a_decision_without_an_operator_is_refused(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """A decision names its reviewer; an anonymous verdict is a shrug."""
    wired, token = client
    feedback_id = _feedback_id(fixture, "c-2")
    response = wired.post(
        "/review/decision",
        json={
            "project_id": fixture.project_id,
            "feedback_id": feedback_id,
            "verdict": "rejected",
            "operator": "",
        },
        headers=_headers(token),
    )
    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# the suggestion write
# --------------------------------------------------------------------------- #


def test_a_suggestion_about_an_unknown_opinion_is_refused(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """A suggestion answers an opinion; a suggestion about nothing proposes
    nothing."""
    _record_comments(fixture)
    wired, token = client
    response = wired.post(
        "/review/suggestion",
        json={
            "project_id": fixture.project_id,
            "version_id": fixture.version_id,
            "feedback_id": "fb-does-not-exist",
            "part": "word/document.xml",
            "paragraph": 1,
            "old_text": PARAGRAPH_TEXT,
            "new_text": "different",
            "author": MODEL_AUTHOR,
        },
        headers=_headers(token),
    )
    assert response.status_code == 403
    assert response.json()["reason"] == "chain_feedback_not_found"


def test_a_suggestion_with_a_zero_paragraph_is_refused(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The seam's numbering is 1-based; a zero is a typo, and a typo is loud."""
    wired, token = client
    feedback_id = _feedback_id(fixture, "c-1")
    response = wired.post(
        "/review/suggestion",
        json={
            "project_id": fixture.project_id,
            "version_id": fixture.version_id,
            "feedback_id": feedback_id,
            "part": "word/document.xml",
            "paragraph": 0,
            "old_text": PARAGRAPH_TEXT,
            "new_text": "different",
            "author": MODEL_AUTHOR,
        },
        headers=_headers(token),
    )
    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# the apply round
# --------------------------------------------------------------------------- #


def test_apply_without_a_decision_is_refused(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """Applying nothing would publish a version nobody reviewed."""
    _record_comments(fixture)
    wired, token = client
    response = wired.post(
        "/review/apply",
        json={
            "project_id": fixture.project_id,
            "input_version_id": fixture.version_id,
            "source_root_id": fixture.source_root_id,
            "source_key": fixture.source_key,
            "output_label": "output.docx",
            "window_end": _window().isoformat(),
        },
        headers=_headers(token),
    )
    assert response.status_code == 403
    assert response.json()["reason"] == "arguments_invalid"
    assert "no review decision" in response.json()["message"]


def test_apply_runs_the_stored_approved_set_and_binds_the_deliverables(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The full round, end to end: suggest, decide, apply, and the bindings hold.

    **The decisions come from the store, not from the request.** The apply
    body carries the addresses; the verdicts are what the reviewer wrote
    through ``/review/decision``. The approved edit lands in the marked and
    the clean draft, the output version is registered with a human-accepted
    edge, and the dossier ties the deliverables to the round — the binding's
    own discipline, reached through the workbench's seam.
    """
    _record_comments(fixture)
    wired, token = client
    feedback_id = _feedback_id(fixture, "c-1")
    _store_suggestion(wired, token, fixture, feedback_id, paragraph=1)
    response = wired.post(
        "/review/decision",
        json={
            "project_id": fixture.project_id,
            "feedback_id": feedback_id,
            "verdict": ReviewVerdict.ACCEPTED.value,
            "operator": "Dr. Chen",
        },
        headers=_headers(token),
    )
    assert response.status_code == 200, response.text

    apply_response = wired.post(
        "/review/apply",
        json={
            "project_id": fixture.project_id,
            "input_version_id": fixture.version_id,
            "source_root_id": fixture.source_root_id,
            "source_key": fixture.source_key,
            "output_label": "binding-sample-output.docx",
            "window_end": _window().isoformat(),
        },
        headers=_headers(token),
    )
    assert apply_response.status_code == 200, apply_response.text
    result = apply_response.json()
    assert result["project_id"] == fixture.project_id
    assert result["input_version_id"] == fixture.version_id
    assert result["output_version_id"] != fixture.version_id
    assert result["edge_id"]
    assert result["marked_receipt_id"] and result["clean_receipt_id"]
    assert result["marked_sha256"] and result["clean_sha256"]
    assert result["dossier_artifact_id"]
    assert result["applied"] == [feedback_id]
    assert result["handovers"] == []

    # **A second opinion the reviewer did not decide stays unresolved** —
    # an honest answer, carried as an explicit task rather than dropped.
    unresolved_ids = {task["feedback_id"] for task in result["unresolved"]}
    assert feedback_id not in unresolved_ids
    assert len(unresolved_ids) >= 1


def test_the_apply_output_version_is_readable_through_the_review_read(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The published draft is a version of its own, and the chain sees it.

    **The round's output is not a file that happens to exist** — it is a
    version row, reached through the same reads the input version was. The
    workbench can show the before and the after from one seam.
    """
    _record_comments(fixture)
    wired, token = client
    feedback_id = _feedback_id(fixture, "c-1")
    _store_suggestion(wired, token, fixture, feedback_id, paragraph=1)
    wired.post(
        "/review/decision",
        json={
            "project_id": fixture.project_id,
            "feedback_id": feedback_id,
            "verdict": ReviewVerdict.ACCEPTED.value,
            "operator": "Dr. Chen",
        },
        headers=_headers(token),
    )
    apply_response = wired.post(
        "/review/apply",
        json={
            "project_id": fixture.project_id,
            "input_version_id": fixture.version_id,
            "source_root_id": fixture.source_root_id,
            "source_key": fixture.source_key,
            "output_label": "binding-sample-output.docx",
            "window_end": _window().isoformat(),
        },
        headers=_headers(token),
    )
    assert apply_response.status_code == 200, apply_response.text
    output_version_id = apply_response.json()["output_version_id"]

    after = _manuscript(wired, token, fixture)
    assert after["version_id"] == fixture.version_id
    # The input read is unchanged; the output version is a different
    # address, and the read that names the input does not silently become
    # the read that names the output.
    assert output_version_id != after["version_id"]


def test_a_foreign_token_is_refused(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The session guard covers the review routes like every other route.

    **A read is free, a mutation is not.** The guard's rule is that the safe
    methods may proceed on any token and a mutation may not proceed on a
    wrong one — so the witness is a *write*: a decision posted with a token
    that is not the service's is refused, the same way a foreign grant on
    ``/approvals`` is.
    """
    wired, _token = client
    response = wired.post(
        "/review/decision",
        json={
            "project_id": fixture.project_id,
            "feedback_id": "fb-whatever",
            "verdict": "pending",
            "operator": "Dr. Chen",
        },
        headers={"Authorization": "Bearer not-the-token"},
    )
    assert response.status_code == 401
    assert response.json()["reason"] == "session_required"


# --------------------------------------------------------------------------- #
# the pre-apply preview
# --------------------------------------------------------------------------- #


def _preview(wired: TestClient, token: str, fixture: BindingFixture) -> tuple[int, dict[str, Any]]:
    """One preview call, with the apply body's own addresses."""
    response = wired.post(
        "/review/preview",
        json={
            "project_id": fixture.project_id,
            "input_version_id": fixture.version_id,
            "source_root_id": fixture.source_root_id,
            "source_key": fixture.source_key,
            "output_label": "binding-sample-output.docx",
            "window_end": _window().isoformat(),
        },
        headers=_headers(token),
    )
    return response.status_code, response.json()


def _artifact_count(fixture: BindingFixture) -> int:
    """How many artefact rows the store holds — the dry-run's witness gauge.

    **A preview that wrote would move this number.** The apply round writes
    four artefacts (two drafts, the output version's source row is not an
    artefact, the two receipts are) plus the dossier; the preview writes
    none of them. The count is read in its own transaction, because the
    fixture's session and the service's forked sessions take the same
    SQLite write lock.
    """
    from sqlalchemy import func, select

    from labcairn.db.models import ArtifactRow

    session = fixture.context.store.session
    count = session.scalar(select(func.count()).select_from(ArtifactRow))
    session.commit()
    return int(count or 0)


def test_the_preview_matches_the_apply_byte_for_byte(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The preview's digests are the apply's digests — the preview does not lie.

    **The core witness of the dry run.** The same round is previewed and
    then applied, and the two answers must agree on every number a reader
    could act on: the applied count, the affected paragraphs, and above all
    the sha256 of the marked and the clean draft. A preview whose digests
    differed from the apply's would be a forecast the operator cannot
    trust, which is the one outcome execution plan §3.2's requirement
    (read 2026-11-25: *before changes are applied, the number of changes,
    the affected paragraphs and a summary of the output changes must be
    previewed*) exists to prevent.

    **And the preview writes nothing.** The artefact count is read before
    and after the preview call: a dry run that published a draft, wrote a
    manifest or left a store row behind would be the apply step wearing a
    preview's name.
    """
    _record_comments(fixture)
    wired, token = client
    feedback_id = _feedback_id(fixture, "c-1")
    _store_suggestion(wired, token, fixture, feedback_id, paragraph=1)
    verdict = wired.post(
        "/review/decision",
        json={
            "project_id": fixture.project_id,
            "feedback_id": feedback_id,
            "verdict": ReviewVerdict.ACCEPTED.value,
            "operator": "Dr. Chen",
        },
        headers=_headers(token),
    )
    assert verdict.status_code == 200, verdict.text

    before = _artifact_count(fixture)
    status, preview = _preview(wired, token, fixture)
    assert status == 200, preview
    after = _artifact_count(fixture)
    assert before == after, (
        "the preview wrote store rows: the artefact count moved from "
        f"{before} to {after}. A dry run that writes is an apply, not a preview."
    )

    assert preview["project_id"] == fixture.project_id
    assert preview["input_version_id"] == fixture.version_id
    assert preview["applied"] == 1
    assert preview["pending"] == 0
    assert preview["rejected"] == 0
    assert preview["affected_paragraphs"] == [1]
    assert [edit["feedback_id"] for edit in preview["edits"]] == [feedback_id]
    assert preview["edits"][0]["old_text"] == PARAGRAPH_TEXT
    assert preview["edits"][0]["new_text"] == PARAGRAPH_TEXT.replace("estimates", "re-estimates")
    assert preview["original_sha256"] and preview["original_size_bytes"] > 0

    apply_response = wired.post(
        "/review/apply",
        json={
            "project_id": fixture.project_id,
            "input_version_id": fixture.version_id,
            "source_root_id": fixture.source_root_id,
            "source_key": fixture.source_key,
            "output_label": "binding-sample-output.docx",
            "window_end": _window().isoformat(),
        },
        headers=_headers(token),
    )
    assert apply_response.status_code == 200, apply_response.text
    applied = apply_response.json()

    # **The equality the whole preview stands on.** The drafts the preview
    # measured are the drafts the apply published — same sha256, same size.
    assert preview["marked_sha256"] == applied["marked_sha256"]
    assert preview["clean_sha256"] == applied["clean_sha256"]
    assert preview["applied"] == len(applied["applied"])


def test_the_preview_holds_back_undecided_suggestions(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """A suggestion the reviewer has not approved is counted, never applied.

    **The model does not decide.** An undecided suggestion is `pending`, a
    refused one is `rejected`, and neither reaches the affected paragraphs
    nor the edit summaries — applying either would be the model's word
    overriding the reviewer's, which is the separation the whole review
    step exists to keep. The verdict is revised through the store, exactly
    as the apply step would read it, so the preview's counts follow the
    reviewer's word rather than the suggestion's presence.
    """
    _record_comments(fixture)
    wired, token = client
    feedback_id = _feedback_id(fixture, "c-1")
    _store_suggestion(wired, token, fixture, feedback_id, paragraph=1)

    def _decide(verdict_value: str) -> None:
        response = wired.post(
            "/review/decision",
            json={
                "project_id": fixture.project_id,
                "feedback_id": feedback_id,
                "verdict": verdict_value,
                "operator": "Dr. Chen",
            },
            headers=_headers(token),
        )
        assert response.status_code == 200, response.text

    # **No verdict at all is the apply's own refusal, mirrored.** The apply
    # refuses a round with no decision; the preview answers the same
    # refusal rather than forecasting an empty, harmless round.
    status, body = _preview(wired, token, fixture)
    assert status == 403, body
    assert body["reason"] == "arguments_invalid"
    assert "no review decision" in body["message"]

    _decide(ReviewVerdict.PENDING.value)
    status, body = _preview(wired, token, fixture)
    assert status == 200, body
    assert body["applied"] == 0
    assert body["pending"] == 1
    assert body["affected_paragraphs"] == []
    assert body["edits"] == []

    _decide(ReviewVerdict.REJECTED.value)
    status, body = _preview(wired, token, fixture)
    assert status == 200, body
    assert body["applied"] == 0
    assert body["rejected"] == 1
    assert body["pending"] == 0
    assert body["affected_paragraphs"] == []

    _decide(ReviewVerdict.ACCEPTED.value)
    status, body = _preview(wired, token, fixture)
    assert status == 200, body
    assert body["applied"] == 1
    assert body["affected_paragraphs"] == [1]


# --------------------------------------------------------------------------- #
# the four-deliverable export
# --------------------------------------------------------------------------- #


def _apply_round(wired: TestClient, token: str, fixture: BindingFixture) -> dict[str, Any]:
    """One full approved round, applied through the workbench's own seam."""
    feedback_id = _feedback_id(fixture, "c-1")
    _store_suggestion(wired, token, fixture, feedback_id, paragraph=1)
    verdict = wired.post(
        "/review/decision",
        json={
            "project_id": fixture.project_id,
            "feedback_id": feedback_id,
            "verdict": ReviewVerdict.ACCEPTED.value,
            "operator": "Dr. Chen",
        },
        headers=_headers(token),
    )
    assert verdict.status_code == 200, verdict.text
    apply_response = wired.post(
        "/review/apply",
        json={
            "project_id": fixture.project_id,
            "input_version_id": fixture.version_id,
            "source_root_id": fixture.source_root_id,
            "source_key": fixture.source_key,
            "output_label": "binding-sample-output.docx",
            "window_end": _window().isoformat(),
        },
        headers=_headers(token),
    )
    assert apply_response.status_code == 200, apply_response.text
    return dict(apply_response.json())


def _export(
    wired: TestClient, token: str, fixture: BindingFixture, dossier_artifact_id: str
) -> tuple[int, dict[str, Any]]:
    """One deliverables-export call, addressed the way the route names it."""
    response = wired.get(
        "/review/deliverables",
        params={"project_id": fixture.project_id, "dossier_artifact_id": dossier_artifact_id},
        headers=_headers(token),
    )
    return response.status_code, response.json()


def test_the_export_serves_the_four_bound_deliverables(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """One closed binding exports as four files, and the bindings hold.

    **The four are one round's four.** The marked and the clean drafts are
    the apply's own published bytes, hash-checked against the dossier; the
    response table names every opinion the chain holds, the applied one
    with its verdict and its change; and the quality report carries the
    binding's ids — the same input version, output version, edge and
    receipts the manifest binds. A reader who decodes, saves and hashes
    each file verifies it against the digest the binding recorded, which
    is execution plan §7.1's step 9 reached through the API.
    """
    _record_comments(fixture)
    wired, token = client
    applied = _apply_round(wired, token, fixture)
    status, export = _export(wired, token, fixture, applied["dossier_artifact_id"])
    assert status == 200, export

    assert export["project_id"] == fixture.project_id
    assert export["dossier_artifact_id"] == applied["dossier_artifact_id"]
    assert export["input_version_id"] == fixture.version_id
    assert export["output_version_id"] == applied["output_version_id"]
    assert export["marked_receipt_id"] == applied["marked_receipt_id"]
    assert export["clean_receipt_id"] == applied["clean_receipt_id"]
    assert export["edge_id"] == applied["edge_id"]
    assert export["task_id"]

    files = {item["kind"]: item for item in export["deliverables"]}
    assert set(files) == {"marked", "clean", "response_table", "quality_report"}
    for kind, item in files.items():
        assert item["size_bytes"] > 0, f"the {kind} deliverable is empty"
        assert item["content_base64"], f"the {kind} deliverable carries no bytes"
        assert item["sha256"], f"the {kind} deliverable carries no digest"

    marked = base64.b64decode(files["marked"]["content_base64"])
    clean = base64.b64decode(files["clean"]["content_base64"])
    assert hashlib.sha256(marked).hexdigest() == applied["marked_sha256"]
    assert hashlib.sha256(marked).hexdigest() == files["marked"]["sha256"]
    assert hashlib.sha256(clean).hexdigest() == applied["clean_sha256"]
    assert hashlib.sha256(clean).hexdigest() == files["clean"]["sha256"]

    response_table = base64.b64decode(files["response_table"]["content_base64"]).decode("utf-8")
    feedback_id = _feedback_id(fixture, "c-1")
    assert feedback_id in response_table, (
        "the response table does not name the approved opinion — an opinion "
        "absent from the table is an opinion silently dropped"
    )
    assert applied["output_version_id"] in response_table

    quality_report = base64.b64decode(files["quality_report"]["content_base64"]).decode("utf-8")
    assert applied["marked_receipt_id"] in quality_report
    assert applied["clean_receipt_id"] in quality_report
    assert applied["output_version_id"] in quality_report
    assert applied["edge_id"] in quality_report
    assert fixture.version_id in quality_report


def test_the_export_refuses_an_unknown_dossier(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """An export of nothing is refused in the layer's own vocabulary.

    **The manifest is the export's authority, so a missing one is a
    refusal, not an empty bundle.** The refusal is the artefact layer's own
    `artifact_not_found`, rendered in the same two fields every other
    refusal uses — a caller branches on the reason without reading the
    message, the same discipline the whole API's error surface keeps.
    """
    _record_comments(fixture)
    wired, token = client
    status, body = _export(wired, token, fixture, "no-such-dossier-artifact")
    assert status == 403, body
    assert body["reason"] == "artifact_not_found"
    assert "no artefact" in body["message"]


# --------------------------------------------------------------------------- #
# the round the service names
# --------------------------------------------------------------------------- #


def test_the_service_names_the_round_the_workspace_holds(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The service says which round it holds — **and names no material**.

    **This is the read the workbench was missing.** The paper projects were
    in the store and nothing exposed them, so a surface that wanted to work
    on a round had to name one it had been told about by something other
    than the service — and the thing it named was a sample round, forever.
    The route that names the round is what ends that.

    **A round is an address.** The pair of ids says which paper and which
    revision of it; the words behind them are reached through the review
    routes, which apply the policy. So the listing carries three fields and
    no paragraph, no comment and no file name — asserted here, because a
    listing that leaked the material would leak it *by being useful*.
    """
    wired, token = client
    response = wired.get("/review/rounds", headers=_headers(token))
    assert response.status_code == 200, response.text
    rounds = response.json()
    assert rounds, "the service named no round at all"
    named = {(round_["project_id"], round_["version_id"]) for round_ in rounds}
    assert (fixture.project_id, fixture.version_id) in named

    for round_ in rounds:
        assert set(round_) == {"project_id", "version_id", "created_at"}
    assert PARAGRAPH_TEXT not in response.text
    assert EDITABLE_TEXT not in response.text


def test_a_round_the_policy_denies_is_not_named(
    fixture: BindingFixture,
) -> None:
    """A denied version is dropped from the listing, not named in it.

    **ADR-0003 C5's rule, kept where the listing is.** Refusing the whole
    listing would disclose that a version is there and deny the work the
    operator wanted allowed; naming it would say the same thing more
    quietly. So a denied version is simply not in the answer.
    """
    denied = PermissionPolicy.from_rules(
        [
            Rule(
                effect=Permission.DENY,
                pattern="**",
                capabilities=frozenset({"source.inventory"}),
            )
        ]
    )
    narrow = replace(fixture.context, policy=denied)
    app = create_app(narrow, event_source=_NoEvents())
    with TestClient(app) as refused:
        session = refused.get("/session")
        assert session.status_code == 200
        refused_token = str(session.json()["token"])
        response = refused.get("/review/rounds", headers=_headers(refused_token))
    assert response.status_code == 200, response.text
    assert response.json() == [], "a denied version was named in the listing"


# --------------------------------------------------------------------------- #
# the run's own record, read back
# --------------------------------------------------------------------------- #


def test_the_suggest_run_record_is_readable_back_after_the_run(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The run's account outlives the run, and can be read back.

    **The gate needs exactly this.** G2-3's evidence is the suggest run's
    own record — the mode, the model id, the request count, the tokens,
    the durations, the stop reason and the approvals spent per opinion —
    and before this there was no way to collect it: the run answered with
    its account, the row held it, and nothing read either back, so the
    evidence collector could only record the slot as unknown.

    **The account that comes back is the account the run gave.** The two
    are the same object, so a reader that compared them would be comparing
    a thing with itself — and a difference between them would be a bug in
    one of them, which is why they are compared here.
    """
    _record_comments(fixture)
    wired, token = client
    started = wired.post(
        "/review/suggest",
        json={
            "project_id": fixture.project_id,
            "version_id": fixture.version_id,
            "mode": "substitute",
        },
        headers=_headers(token),
    )
    assert started.status_code == 201, started.text
    account = started.json()

    read = wired.get(f"/review/suggest/runs/{account['run_id']}", headers=_headers(token))
    assert read.status_code == 200, read.text
    record = read.json()

    assert record["run_id"] == account["run_id"]
    assert record["mode"] == account["mode"] == "substitute"
    assert record["model_id"] == account["model_id"]
    assert record["requests_made"] == account["requests_made"]
    assert record["tokens_estimated"] == account["tokens_estimated"]
    assert record["duration_seconds"] == account["duration_seconds"]
    assert record["requests"] == account["requests"]

    # The record answers what the gate asks for.
    assert record["requests"], "the run made no request and recorded none"
    for entry in record["requests"]:
        assert set(entry) == {
            "feedback_id",
            "source",
            "outcome",
            "attempts",
            "elapsed_s",
            "tokens_estimated",
            "detail",
            "retryable",
            "approval_id",
            "approval_spent",
        }
        assert entry["elapsed_s"] >= 0.0
    assert record["duration_seconds"] >= 0.0

    # **And no prose.** The boundary holds on the way out too: ids, counts
    # and durations, never the request and never the answer.
    assert PARAGRAPH_TEXT not in read.text
    assert EDITABLE_TEXT not in read.text


def test_the_record_of_a_run_that_never_happened_is_refused(
    client: tuple[TestClient, str],
) -> None:
    """A run id the store does not hold is refused, not answered with nothing.

    **An empty account would be a false account.** A reader that asked for
    a run and got a zeroed one would read "the run spent nothing" where
    the truth is "there is no such run" — and the second is the one a
    refusal says.
    """
    wired, token = client
    response = wired.get("/review/suggest/runs/no-such-run", headers=_headers(token))
    assert response.status_code == 403, response.text
    assert response.json()["reason"] == "arguments_invalid"
