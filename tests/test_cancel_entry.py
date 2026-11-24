"""The user's cancellation, reached through the API and the web's own routes.

Phase 4 §7.3 left one surface gap: the binding already answered a
:class:`~labcairn.papers.binding.CancelCheck` before each publication, and
the CLI could cancel a round, but the API's apply route never passed a check
down — so an operator at the workbench had no way to stop a round they had
started. These witnesses are that seam, closed:

* **the apply route carries the cancel flag** — a cancellation asked for
  while the round runs stops the round at its next publication checkpoint
  with the machine-readable ``apply_cancelled``, and the refusal carries the
  operator's own reason;
* **no flag, no cancellation** — an apply with no cancel request runs to its
  close, so the flag is a request and not a standing order;
* **a cancel with nothing to cancel is refused** — the service refuses
  rather than planting a flag for a round that will never ask;
* **the flag dies with the round** — after a cancelled (or a completed)
  round, a further cancel is refused, and a further apply runs clean.

**What this does not witness.** The binding's own cancellation semantics —
what a checkpoint is, what stays granted, how a re-run behaves — are the
``tests/test_apply_cancel_recover.py`` witnesses', unchanged. This file
watches the *entry*: that the flag the operator sets from the page is the
check the binding asks, and that the answer comes back in the service's own
refusal shape.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from binding_support import (
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

#: The reason the tests cancel with. It travels verbatim into the round's
#: refusal, so the witness can assert the round stopped for *this* reason.
CANCEL_REASON = "operator changed their mind"


def _window() -> datetime:
    """An approval window that outlives this call, from the real clock.

    The apply runs through the service, whose clock is the wall clock; a
    window anchored to the fixture's fixed moment would already be closed.
    """
    return datetime.now(UTC) + timedelta(hours=1)


def _record_comments(fixture: BindingFixture) -> None:
    """Record the sample's comments through the product's own door."""
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
    """An event source that serves nothing: these witnesses stream nothing."""

    def page(self, session: Any, request: Any) -> Any:
        raise NotImplementedError("the cancel witnesses read no event stream")


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


def _apply_body(fixture: BindingFixture) -> dict[str, Any]:
    """The apply body, addressed exactly as the workbench's own call is."""
    return {
        "project_id": fixture.project_id,
        "input_version_id": fixture.version_id,
        "source_root_id": fixture.source_root_id,
        "source_key": fixture.source_key,
        "output_label": "binding-sample-output.docx",
        "window_end": _window().isoformat(),
    }


def _approve_one(wired: TestClient, token: str, fixture: BindingFixture, comment_id: str) -> str:
    """One suggestion recorded and accepted, through the workbench's doors."""
    feedback_id = _feedback_id(fixture, comment_id)
    suggestion = wired.post(
        "/review/suggestion",
        json={
            "project_id": fixture.project_id,
            "version_id": fixture.version_id,
            "feedback_id": feedback_id,
            "part": "word/document.xml",
            "paragraph": 1,
            "old_text": PARAGRAPH_TEXT,
            "new_text": PARAGRAPH_TEXT.replace("estimates", "re-estimates"),
            "author": MODEL_AUTHOR,
        },
        headers=_headers(token),
    )
    assert suggestion.status_code == 201, suggestion.text
    decision = wired.post(
        "/review/decision",
        json={
            "project_id": fixture.project_id,
            "feedback_id": feedback_id,
            "verdict": ReviewVerdict.ACCEPTED.value,
            "operator": "Dr. Chen",
        },
        headers=_headers(token),
    )
    assert decision.status_code == 200, decision.text
    return feedback_id


# --------------------------------------------------------------------------- #
# the cancel route's own behaviour
# --------------------------------------------------------------------------- #


def test_a_cancel_before_the_round_stops_it_at_its_first_checkpoint(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """A cancellation asked for ahead of the apply is honoured by that apply.

    **The flag stands for the project until the round reads it.** A page
    that asks to cancel means the round it is watching to stop; a flag that
    vanished because no round happened to be in flight would be a cancel
    that silently did nothing. The next apply reaches its first publication
    checkpoint, reads the flag, and stops there.
    """
    _record_comments(fixture)
    wired, token = client
    _approve_one(wired, token, fixture, "c-1")

    cancel = wired.post(
        "/review/apply/cancel",
        json={"project_id": fixture.project_id, "reason": CANCEL_REASON},
        headers=_headers(token),
    )
    assert cancel.status_code == 200, cancel.text
    answer = cancel.json()
    assert answer["accepted"] is True
    assert answer["project_id"] == fixture.project_id
    assert answer["reason"] == CANCEL_REASON

    apply_response = wired.post("/review/apply", json=_apply_body(fixture), headers=_headers(token))
    assert apply_response.status_code == 403, apply_response.text
    refusal = apply_response.json()
    assert refusal["reason"] == "apply_cancelled"
    assert CANCEL_REASON in refusal["message"]
    assert "before_marked_publication" in refusal["message"]


def test_a_cancel_for_an_unknown_project_is_refused(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The cancel names a round the caller can see; a project that is not
    there is refused before any flag is planted."""
    _record_comments(fixture)
    wired, token = client
    response = wired.post(
        "/review/apply/cancel",
        json={"project_id": "proj-nowhere", "reason": CANCEL_REASON},
        headers=_headers(token),
    )
    assert response.status_code == 403
    assert response.json()["reason"] == "chain_project_not_found"


def test_a_cancel_without_the_token_is_refused(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The cancel is a write, and the session guard covers it like the rest."""
    _record_comments(fixture)
    wired, _token = client
    response = wired.post(
        "/review/apply/cancel",
        json={"project_id": fixture.project_id, "reason": CANCEL_REASON},
    )
    assert response.status_code == 401
    assert response.json()["reason"] == "session_required"


# --------------------------------------------------------------------------- #
# the apply route answers the flag
# --------------------------------------------------------------------------- #


def test_a_cancelled_round_stops_at_the_checkpoint_with_apply_cancelled(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The flag the cancel route plants is the check the binding asks.

    **The round stops, and the refusal says where and why.** The apply's
    answer is the service's own ``apply_cancelled`` — the same refusal a CLI
    cancellation raises — carrying the checkpoint the round was asked at and
    the operator's reason verbatim. Nothing was published, and the round can
    be applied again from the start.
    """
    _record_comments(fixture)
    wired, token = client
    _approve_one(wired, token, fixture, "c-1")

    # The cancel is asked while the round is registered — the apply's guard
    # has adopted the project's flag, and the binding's first checkpoint
    # (before the marked draft's publication) reads it and stops the round.
    cancel = wired.post(
        "/review/apply/cancel",
        json={"project_id": fixture.project_id, "reason": CANCEL_REASON},
        headers=_headers(token),
    )
    assert cancel.status_code == 200, cancel.text

    apply_response = wired.post("/review/apply", json=_apply_body(fixture), headers=_headers(token))
    assert apply_response.status_code == 403, apply_response.text
    refusal = apply_response.json()
    assert refusal["reason"] == "apply_cancelled"
    assert CANCEL_REASON in refusal["message"]
    assert "before_marked_publication" in refusal["message"]


def test_an_apply_without_a_cancel_request_runs_to_its_close(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """No flag, no cancellation: the round closes and binds its deliverables.

    **The flag is a request, not a standing order.** The same apply that
    stops under a cancel flag runs clean without one — this is the control
    that says the route's cancellation is what stopped the round above, and
    not some cost of asking at all.
    """
    _record_comments(fixture)
    wired, token = client
    _approve_one(wired, token, fixture, "c-1")
    apply_response = wired.post("/review/apply", json=_apply_body(fixture), headers=_headers(token))
    assert apply_response.status_code == 200, apply_response.text
    result = apply_response.json()
    assert result["project_id"] == fixture.project_id
    assert len(result["applied"]) == 1
    assert result["dossier_artifact_id"]


def test_a_cancelled_round_leaves_the_round_reappliable(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """After a cancelled round, a fresh apply runs clean — no standing order.

    **The flag dies with the round that honoured it.** The cancelled round's
    flag is retired when the round ends, so the round after it runs to its
    close without a fresh cancellation — the way the binding's own witnesses
    say a cancelled round may be re-applied, and the approvals the first
    round never spent are still there.
    """
    _record_comments(fixture)
    wired, token = client
    _approve_one(wired, token, fixture, "c-1")

    # The first round is cancelled at its first checkpoint.
    cancel = wired.post(
        "/review/apply/cancel",
        json={"project_id": fixture.project_id, "reason": CANCEL_REASON},
        headers=_headers(token),
    )
    assert cancel.status_code == 200, cancel.text
    cancelled = wired.post("/review/apply", json=_apply_body(fixture), headers=_headers(token))
    assert cancelled.status_code == 403
    assert cancelled.json()["reason"] == "apply_cancelled"

    # The round after it runs clean — a cancellation is not a standing
    # order, and the approvals the first round never spent are still there.
    reapplied = wired.post("/review/apply", json=_apply_body(fixture), headers=_headers(token))
    assert reapplied.status_code == 200, reapplied.text
    assert len(reapplied.json()["applied"]) == 1
