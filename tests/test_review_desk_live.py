"""The review desk's live seam: what the workbench reads is what the service serves.

The workbench's contract types (`web/src/views/reviewContract.ts`) are the
shape the desk draws, and the service's `/review` routes are the shape the
store answers. **The two cannot be allowed to drift** — a field renamed on
one side alone is a desk that reads `undefined` where the service wrote a
value, and every unit test on either side stays green while it happens.

So this file drives the service with the binding's own three-case sample and
asserts, field by field, that the JSON `GET /review/opinions` answers can be
read as the contract's `ReviewOpinion`: the anchor fields, the suggestion's
`old_text`/`new_text`/`author`/`proposed_at`, the decision's
`verdict`/`operator`/`needs_evidence`, and the chain's `response_states`.
It then walks the desk's own round — one verdict posted, the opinion read
again, the approved set applied — as the smoke the workbench's click makes
of the same calls.

**The field names are compared against the frontend's own file.** The
`reviewContract.ts` source is read here, so a field the TypeScript renamed
without the service knowing is a failing Python test — the drift check the
workbench's own `paths.test.ts` performs for routes, performed here for the
opinion record's fields.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from binding_support import (
    MODEL_AUTHOR,
    MOMENT,
    BindingFixture,
    build_binding_fixture,
    feedback_id_of,
)
from fastapi.testclient import TestClient
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.api.app import create_app
from labcairn.application.context import ApplicationContext
from labcairn.papers.feedback import record_feedback

pytestmark = pytest.mark.integration

env = _shared_env

#: The apply window, an hour past the real clock — the service's clock is
#: the wall clock, and a window the fixture's fixed moment anchors would
#: already be closed.
WINDOW = datetime.now(UTC) + timedelta(hours=1)

#: The frontend's contract file, read as text. The fields the desk draws are
#: written there; a name the service stopped serving is a desk that draws
#: nothing, so the comparison is part of this witness.
CONTRACT_PATH = (
    Path(__file__).resolve().parent.parent / "web" / "src" / "views" / "reviewContract.ts"
)

#: The fields the contract's `ReviewSuggestion` declares, as the service must
#: spell them.
SUGGESTION_FIELDS = ("part", "paragraph", "old_text", "new_text", "author", "proposed_at")

#: The fields the contract's `ReviewDecision` declares.
DECISION_FIELDS = ("verdict", "operator", "decided_at", "needs_evidence")

#: The fields the contract's `ReviewOpinion` declares.
OPINION_FIELDS = (
    "feedback_id",
    "issue_key",
    "version_id",
    "comment_text",
    "author",
    "anchor_status",
    "anchor_reason",
    "anchor_paragraph",
    "anchor_start",
    "anchor_end",
    "anchor_text",
    "comment_locator",
    "location_state",
    "suggestion",
    "decision",
    "response_states",
)


def _record_comments(fixture: BindingFixture) -> None:
    """Record the sample's comments through the product's own door.

    The import precedes the review; the workbench reads what the import
    recorded. The fixture's transaction is ended here, so the service's
    forked sessions can take SQLite's write lock — the same courtesy
    ``tests/test_review_api.py`` extends.
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


class _NoEvents:
    """An event source that serves nothing; the review routes do not stream."""

    def page(self, session: Any, request: Any) -> Any:
        raise NotImplementedError("the desk's live witness reads no event stream")


@pytest.fixture
def fixture(env: StoreEnv, tmp_path: Path) -> BindingFixture:
    return build_binding_fixture(env.store(), tmp_path / "workspace")


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


def _store_suggestion(
    client: TestClient,
    token: str,
    fixture: BindingFixture,
    feedback_id: str,
) -> dict[str, Any]:
    """Store one suggestion for the first paragraph, as the model would."""
    response = client.post(
        "/review/suggestion",
        json={
            "project_id": fixture.project_id,
            "version_id": fixture.version_id,
            "feedback_id": feedback_id,
            "part": "word/document.xml",
            "paragraph": 1,
            "old_text": "The method estimates the parameter from a single observation.",
            "new_text": "The method re-estimates the parameter from a single observation.",
            "author": MODEL_AUTHOR,
        },
        headers=_headers(token),
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


# --------------------------------------------------------------------------- #
# the shape the desk reads
# --------------------------------------------------------------------------- #


def test_the_contract_file_is_where_the_witness_reads_it() -> None:
    """The frontend's contract file exists; a missing file is a moved file.

    A witness that quietly compared against nothing would pass while the
    desk drifted, so the file's absence is loud.
    """
    assert CONTRACT_PATH.exists(), (
        f"the workbench's contract file is not at {CONTRACT_PATH}; point this "
        "witness at where it moved rather than deleting the comparison."
    )


def test_opinion_json_carries_the_contract_fields(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """Every field the desk's `ReviewOpinion` draws is in the service's JSON.

    **The comparison runs both ways.** A field the service omits is a desk
    that reads `undefined`; a field the contract does not name is a shape the
    desk was never taught to draw. Both are drift, and this witness names
    them.
    """
    _record_comments(fixture)
    wired, token = client
    source = CONTRACT_PATH.read_text(encoding="utf-8")
    for name in OPINION_FIELDS:
        assert f"readonly {name}:" in source, (
            f"the contract no longer declares `{name}`; the witness's field "
            "list is the service's promise, and it is re-read, not carried forward."
        )
    for opinion in _opinions(wired, token, fixture):
        assert set(opinion) == set(OPINION_FIELDS), (
            f"the opinion's fields drifted: the service answered "
            f"{sorted(opinion)}, the contract declares {sorted(OPINION_FIELDS)}."
        )


def test_suggestion_json_is_readable_as_the_contract_suggestion(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The suggestion's fields — including `proposed_at` — match the contract.

    **`proposed_at` is the contract's word for the proposal's moment.** The
    contract once said `date`; the service and the generated TypeScript both
    say `proposed_at`, and a fixture or a contract that still carried `date`
    would be a desk reading `undefined` where a moment was written.
    """
    _record_comments(fixture)
    wired, token = client
    feedback_id = _feedback_id(fixture, "c-1")
    stored = _store_suggestion(wired, token, fixture, feedback_id)
    assert set(stored) == set(SUGGESTION_FIELDS), (
        f"the suggestion's fields drifted: {sorted(stored)} against {sorted(SUGGESTION_FIELDS)}."
    )
    assert "proposed_at" in stored, "the suggestion's moment is `proposed_at`, not `date`."

    source = CONTRACT_PATH.read_text(encoding="utf-8")
    for name in SUGGESTION_FIELDS:
        assert f"readonly {name}:" in source, (
            f"the contract's `ReviewSuggestion` no longer declares `{name}`."
        )
    assert "readonly date:" not in source, (
        "the contract still declares a `date` field on the suggestion; the "
        "service and the generated types say `proposed_at`."
    )

    (opinion,) = [o for o in _opinions(wired, token, fixture) if o["feedback_id"] == feedback_id]
    suggestion = opinion["suggestion"]
    assert suggestion is not None
    assert set(suggestion) == set(SUGGESTION_FIELDS)
    assert suggestion["old_text"].startswith("The method estimates")
    assert suggestion["new_text"].startswith("The method re-estimates")
    assert suggestion["author"] == MODEL_AUTHOR
    assert isinstance(suggestion["proposed_at"], str) and suggestion["proposed_at"]


def test_decision_json_is_readable_as_the_contract_decision(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """A posted verdict comes back with the decision fields the desk draws."""
    _record_comments(fixture)
    wired, token = client
    feedback_id = _feedback_id(fixture, "c-1")
    _store_suggestion(wired, token, fixture, feedback_id)
    response = wired.post(
        "/review/decision",
        json={
            "project_id": fixture.project_id,
            "feedback_id": feedback_id,
            "verdict": "accepted",
            "operator": "Dr. Chen",
            "needs_evidence": False,
        },
        headers=_headers(token),
    )
    assert response.status_code == 200, response.text
    decision = dict(response.json())
    assert set(decision) == set(DECISION_FIELDS), (
        f"the decision's fields drifted: {sorted(decision)} against {sorted(DECISION_FIELDS)}."
    )
    assert decision["verdict"] == "accepted"
    assert decision["operator"] == "Dr. Chen"
    assert decision["needs_evidence"] is False

    source = CONTRACT_PATH.read_text(encoding="utf-8")
    for name in DECISION_FIELDS:
        assert f"readonly {name}:" in source, (
            f"the contract's `ReviewDecision` no longer declares `{name}`."
        )

    (opinion,) = [o for o in _opinions(wired, token, fixture) if o["feedback_id"] == feedback_id]
    assert opinion["decision"] == decision


def test_response_states_travel_with_every_opinion(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The chain's states are on the read, in the contract's own vocabulary."""
    _record_comments(fixture)
    wired, token = client
    vocabulary = {"addressed", "partially_addressed", "not_addressed", "pending"}
    for opinion in _opinions(wired, token, fixture):
        states = opinion["response_states"]
        assert isinstance(states, list)
        assert set(states) <= vocabulary, (
            f"a response state outside the contract's four words: {states}."
        )


# --------------------------------------------------------------------------- #
# the desk's own round, end to end
# --------------------------------------------------------------------------- #


def test_the_desk_round_runs_decision_then_apply(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The smoke the workbench's click makes: suggest, decide, read, apply.

    **The reads the desk draws are the reads these calls answer.** A verdict
    is posted; the opinion list is read again and carries the verdict; the
    approved set is applied and the round closes with the deliverables'
    bindings — the same round a person walks on the desk, through the same
    routes.
    """
    _record_comments(fixture)
    wired, token = client
    feedback_id = _feedback_id(fixture, "c-1")
    _store_suggestion(wired, token, fixture, feedback_id)

    verdict_response = wired.post(
        "/review/decision",
        json={
            "project_id": fixture.project_id,
            "feedback_id": feedback_id,
            "verdict": "accepted",
            "operator": "Dr. Chen",
        },
        headers=_headers(token),
    )
    assert verdict_response.status_code == 200, verdict_response.text

    (opinion,) = [o for o in _opinions(wired, token, fixture) if o["feedback_id"] == feedback_id]
    assert opinion["decision"]["verdict"] == "accepted"

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
    result = dict(apply_response.json())
    assert result["input_version_id"] == fixture.version_id
    assert result["output_version_id"] != fixture.version_id
    assert feedback_id in result["applied"]


def test_the_fixture_carries_the_service_shapes(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The fallback fixtures are the service's shapes, not a third shape.

    **A fallback that lied about its shape is worse than none.** The desk
    draws the fixtures when the service is not up; if a fixture's fields
    drifted from what the service answers, the desk would practise a shape
    the service never sends. The service's own answer and the fixture's
    opinion are compared field by field here — the opinion record itself,
    and a suggestion stored through the service against the fixture's.
    """
    _record_comments(fixture)
    wired, token = client
    fixture_path = (
        Path(__file__).resolve().parent.parent / "web" / "src" / "fixtures" / "review-sample.json"
    )
    assert fixture_path.exists(), f"the fixture moved from {fixture_path}."
    fixture_opinions = json.loads(fixture_path.read_text(encoding="utf-8"))["opinions"]
    served = _opinions(wired, token, fixture)

    assert set(served[0]) == set(fixture_opinions[0]), (
        "the fixture's opinion fields drifted from the service's answer: "
        f"{sorted(fixture_opinions[0])} against {sorted(served[0])}."
    )

    # A suggestion stored through the service must answer with the fields
    # the fixture's suggestion carries — including `proposed_at`, the name
    # the contract settled on.
    feedback_id = _feedback_id(fixture, "c-1")
    stored = _store_suggestion(wired, token, fixture, feedback_id)
    fixture_suggestion = next(o["suggestion"] for o in fixture_opinions if o["suggestion"])
    assert set(stored) == set(fixture_suggestion), (
        "the fixture's suggestion fields drifted from the service's answer: "
        f"{sorted(fixture_suggestion)} against {sorted(stored)}."
    )
    assert "proposed_at" in stored, "the fixture still says `date`; the service says `proposed_at`."
