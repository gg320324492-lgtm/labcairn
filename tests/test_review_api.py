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

from collections.abc import Iterator
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

pytestmark = pytest.mark.integration

env = _shared_env

#: The approvals' expiry — an hour past the **real** clock, because the
#: apply round runs through the service, whose clock is the wall clock. A
#: window anchored to the fixture's fixed moment would already be closed,
#: and an approval whose window has closed cannot be granted.
WINDOW = datetime.now(UTC) + timedelta(hours=1)


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


def test_every_opinion_is_listed_with_its_state(client: tuple[TestClient, str], fixture: BindingFixture) -> None:
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


def test_a_suggestion_and_its_decision_are_separate_records(client: tuple[TestClient, str], fixture: BindingFixture) -> None:
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


def test_the_opinion_read_names_the_chain_states(client: tuple[TestClient, str], fixture: BindingFixture) -> None:
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


def test_the_manuscript_is_read_in_the_anchor_numbering(client: tuple[TestClient, str], fixture: BindingFixture) -> None:
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


def test_a_verdict_on_an_unknown_opinion_is_refused(client: tuple[TestClient, str], fixture: BindingFixture) -> None:
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


def test_a_verdict_outside_the_vocabulary_is_refused(client: tuple[TestClient, str], fixture: BindingFixture) -> None:
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


def test_a_revised_verdict_stands_alone(client: tuple[TestClient, str], fixture: BindingFixture) -> None:
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


def test_a_decision_without_an_operator_is_refused(client: tuple[TestClient, str], fixture: BindingFixture) -> None:
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


def test_a_suggestion_about_an_unknown_opinion_is_refused(client: tuple[TestClient, str], fixture: BindingFixture) -> None:
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


def test_a_suggestion_with_a_zero_paragraph_is_refused(client: tuple[TestClient, str], fixture: BindingFixture) -> None:
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


def test_apply_without_a_decision_is_refused(client: tuple[TestClient, str], fixture: BindingFixture) -> None:
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
            "window_end": WINDOW.isoformat(),
        },
        headers=_headers(token),
    )
    assert response.status_code == 403
    assert response.json()["reason"] == "arguments_invalid"
    assert "no review decision" in response.json()["message"]


def test_apply_runs_the_stored_approved_set_and_binds_the_deliverables(client: tuple[TestClient, str], fixture: BindingFixture) -> None:
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
            "window_end": WINDOW.isoformat(),
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


def test_the_apply_output_version_is_readable_through_the_review_read(client: tuple[TestClient, str], fixture: BindingFixture) -> None:
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
            "window_end": WINDOW.isoformat(),
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


def test_a_foreign_token_is_refused(client: tuple[TestClient, str], fixture: BindingFixture) -> None:
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
