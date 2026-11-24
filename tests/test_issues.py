"""The pilot's in-system issue record, witnessed through the service.

P4-PILOT §9.4 asks the trial to record each problem twice: in the unified
feedback form and **in the system**. What this file witnesses is the
system side -- an issue recorded against a trial round, listed by severity
and status, and its status advanced along the four states with the fix
fields -- against a real commented manuscript on disk and no provider call.

The fixture is the binding's own three-case sample, so a version an issue
names here is the version the binding's own witnesses read -- one sample,
two surfaces.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from binding_support import BindingFixture, build_binding_fixture
from fastapi.testclient import TestClient
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.api.app import create_app
from labcairn.application.context import ApplicationContext
from labcairn.application.issues import record_issue
from labcairn.application.refusal import ApplicationRefusal, ApplicationRefusedError
from labcairn.db.models import PilotIssueRow

pytestmark = pytest.mark.integration

env = _shared_env


class _NoEvents:
    """An event source that serves nothing: the issue routes do not stream.

    It satisfies the ``EventSource`` protocol's shape, and it is never
    reached -- the issue witnesses call no stream route. A stream call
    would be a test of a route this file does not exercise, and the
    service's own unwired refusal is what a stream caller would meet.
    """

    def page(self, session: Any, request: Any) -> Any:
        raise NotImplementedError("the issue witnesses read no event stream")


@pytest.fixture
def fixture(env: StoreEnv, tmp_path: Any) -> BindingFixture:
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


def _record_body(fixture: BindingFixture, **overrides: Any) -> dict[str, Any]:
    """One well-formed issue body, with the fixture's own addresses.

    The version is the fixture's, so the record is about something the
    store holds; the opinion id is left off by default, because a recorded
    problem need not name an opinion (a login failure names none).
    """
    body: dict[str, Any] = {
        "issue_id": "issue-1",
        "project_id": fixture.project_id,
        "version_id": fixture.version_id,
        "step": "apply",
        "error_text": "the apply step stalled for two minutes and then refused",
        "duration_seconds": 121.5,
        "retry_count": 1,
        "severity": "serious",
        "category": "function",
        "reported_by": "student-a",
    }
    body.update(overrides)
    return body


def _record(client: tuple[TestClient, str], body: dict[str, Any]) -> Any:
    wired, token = client
    return wired.post("/issues", json=body, headers=_headers(token))


def _list(client: tuple[TestClient, str], fixture: BindingFixture, **params: Any) -> Any:
    wired, token = client
    query = {"project_id": fixture.project_id, **params}
    return wired.get("/issues", params=query, headers=_headers(token))


# --------------------------------------------------------------------------- #
# the record and the listing
# --------------------------------------------------------------------------- #


def test_an_issue_is_recorded_and_read_back(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The record round-trips: what the team reported is what the read says.

    **Every field the trial's evaluation reads survives the wire.** The
    task, the version, the step, the error, the duration, the retry count,
    the two tags and the reporter are the §9.4 record; a field lost on the
    way in would be a reading the trial cannot take.
    """
    response = _record(client, _record_body(fixture))
    assert response.status_code == 201, response.text
    recorded = response.json()
    assert recorded["issue_id"] == "issue-1"
    assert recorded["project_id"] == fixture.project_id
    assert recorded["version_id"] == fixture.version_id
    assert recorded["step"] == "apply"
    assert recorded["error_text"] == "the apply step stalled for two minutes and then refused"
    assert recorded["duration_seconds"] == 121.5
    assert recorded["retry_count"] == 1
    assert recorded["severity"] == "serious"
    assert recorded["category"] == "function"
    assert recorded["reported_by"] == "student-a"
    # A recorded issue is open, and no fix is claimed for it.
    assert recorded["status"] == "open"
    assert recorded["fix_version"] is None
    assert recorded["regression_note"] is None
    assert recorded["reported_at"]

    listing = _list(client, fixture)
    assert listing.status_code == 200, listing.text
    assert [row["issue_id"] for row in listing.json()] == ["issue-1"]


def test_an_issue_may_name_the_opinion_it_concerns(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """An issue about one opinion carries the opinion's id.

    **The opinion must be one the chain holds.** The §9.4 record ties a
    problem to the opinion it concerns; a name the chain does not hold is
    a report about nothing, and the record refuses it by name rather than
    carrying a dangling id.
    """
    from binding_support import feedback_id_of

    feedback_id = feedback_id_of(fixture, "c-1")
    fixture.context.store.session.commit()

    response = _record(client, _record_body(fixture, feedback_id=feedback_id, step="suggest"))
    assert response.status_code == 201, response.text
    assert response.json()["feedback_id"] == feedback_id

    refused = _record(
        client, _record_body(fixture, issue_id="issue-ghost", feedback_id="fb-nowhere")
    )
    assert refused.status_code == 403, refused.text
    assert refused.json()["reason"] == "chain_feedback_not_found"


def test_an_issue_about_an_unknown_version_is_refused(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """A version nobody ingested is a report about nothing.

    **The named thing must be there.** A version or a project outside the
    store is refused, the same way the review workbench refuses a read of
    a round nobody opened.
    """
    response = _record(client, _record_body(fixture, version_id="ver-nowhere"))
    assert response.status_code == 403, response.text
    assert response.json()["reason"] == "chain_version_not_found"

    response = _record(client, _record_body(fixture, project_id="proj-nowhere"))
    assert response.status_code == 403, response.text
    assert response.json()["reason"] == "chain_project_not_found"


def test_an_issue_without_a_step_or_a_reporter_is_refused(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """A problem nobody can place is a problem nobody can reproduce.

    **The step and the reporter are the record's minimum.** The step says
    where in the operation the problem happened; the reporter says who saw
    it. Either missing, the record would not be findable in the trial's
    own terms.
    """
    # An empty field is refused at the wire (the body's ``min_length``);
    # a blank-but-nonempty one reaches the layer and is refused there, by
    # name -- the same rule the review workbench's own bodies follow.
    response = _record(client, _record_body(fixture, step="   "))
    assert response.status_code == 403, response.text
    assert response.json()["reason"] == "arguments_invalid"

    response = _record(client, _record_body(fixture, reported_by=""))
    assert response.status_code == 422, response.text

    response = _record(client, _record_body(fixture, error_text=""))
    assert response.status_code == 422, response.text

    response = _record(client, _record_body(fixture, step=""))
    assert response.status_code == 422, response.text

    response = _record(client, _record_body(fixture, reported_by="   "))
    assert response.status_code == 403, response.text
    assert response.json()["reason"] == "arguments_invalid"


def test_a_negative_retry_count_or_duration_is_refused(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """A count and a duration are measurements, and neither runs backwards.

    **The layer refuses the impossible value by name**, so a caller that
    reached past the wire meets the same refusal a browser's 422 would
    have given it.
    """
    # The retry count's floor is in the body's own type (``ge=0``), so a
    # negative one is refused at the wire; the duration has no wire floor
    # and is refused by the layer, by name -- the same value a caller that
    # reached past the wire would meet.
    response = _record(client, _record_body(fixture, retry_count=-1))
    assert response.status_code == 422, response.text

    response = _record(client, _record_body(fixture, duration_seconds=-0.5))
    assert response.status_code == 403, response.text
    assert response.json()["reason"] == "arguments_invalid"


# --------------------------------------------------------------------------- #
# the two closed vocabularies
# --------------------------------------------------------------------------- #


def test_a_severity_outside_the_closed_four_is_refused_at_the_wire(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """§9.4's severity is a closed four, and the wire refuses a fifth.

    **The vocabulary is in the type rather than in the handler.** The body
    carries the four words as a ``Literal``, so a tag the service does not
    accept is refused at the wire with the 422 every other closed
    vocabulary answers with -- before the layer is reached, and before a
    row could carry a tag nobody can group by.
    """
    response = _record(client, _record_body(fixture, severity="catastrophic"))
    assert response.status_code == 422, response.text

    for severity in ("blocker", "serious", "minor", "suggestion"):
        ok = _record(
            client,
            _record_body(fixture, issue_id=f"issue-{severity}", severity=severity),
        )
        assert ok.status_code == 201, ok.text
        assert ok.json()["severity"] == severity


def test_a_type_outside_the_closed_five_is_refused_at_the_wire(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """§9.4's type is a closed five, and the wire refuses a sixth.

    **The five are the trial's own grouping**: function, interface,
    performance, model, documentation. A problem tagged with a word
    outside the five would fall outside every grouping the trial's
    evaluation reads.
    """
    response = _record(client, _record_body(fixture, category="network"))
    assert response.status_code == 422, response.text

    for category in ("function", "interface", "performance", "model", "documentation"):
        ok = _record(
            client,
            _record_body(fixture, issue_id=f"issue-{category}", category=category),
        )
        assert ok.status_code == 201, ok.text
        assert ok.json()["category"] == category


def test_a_filter_outside_the_vocabulary_is_refused_by_name(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """A filter names a state the record can hold, or no filter at all.

    **A filter that cannot be understood is not an empty answer.** An
    empty list would read as "none recorded"; a misspelled filter is
    refused by name, so the caller knows the question -- not the trial --
    was wrong.
    """
    response = _list(client, fixture, status="reopened")
    assert response.status_code == 403, response.text
    assert response.json()["reason"] == "pilot_issue_status_move_refused"

    response = _list(client, fixture, severity="catastrophic")
    assert response.status_code == 403, response.text
    assert response.json()["reason"] == "pilot_issue_severity_unknown"


def test_issues_are_listed_newest_first_and_narrowed_by_the_filters(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The listing narrows by status and severity, newest first.

    **A filter narrows; it does not refuse.** An empty answer is a fact
    about the trial -- "no blocker has been recorded" -- and the newest
    first is the order a trial team reads a log in.
    """
    wired, token = client
    for issue_id, severity in (
        ("issue-a", "blocker"),
        ("issue-b", "minor"),
        ("issue-c", "blocker"),
    ):
        response = _record(
            client,
            _record_body(fixture, issue_id=issue_id, severity=severity),
        )
        assert response.status_code == 201, response.text
    # Advance one issue to confirmed, so the status filter has something
    # to separate.
    moved = wired.patch(
        "/issues/issue-a/status",
        json={"project_id": fixture.project_id, "status": "confirmed"},
        headers=_headers(token),
    )
    assert moved.status_code == 200, moved.text

    every = _list(client, fixture)
    assert every.status_code == 200, every.text
    assert [row["issue_id"] for row in every.json()] == ["issue-c", "issue-b", "issue-a"]

    blockers = _list(client, fixture, severity="blocker")
    assert [row["issue_id"] for row in blockers.json()] == ["issue-c", "issue-a"]

    confirmed = _list(client, fixture, status="confirmed")
    assert [row["issue_id"] for row in confirmed.json()] == ["issue-a"]

    # A filter over an empty corner of the record answers "none", not an
    # error: nothing has been fixed yet.
    fixed = _list(client, fixture, status="fixed")
    assert fixed.status_code == 200, fixed.text
    assert fixed.json() == []


def test_the_listing_of_an_unknown_project_is_refused(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """A listing is about a project, and the project must be there.

    **The same refusal the record path gives.** A read that answered an
    unknown project with an empty list would be indistinguishable from a
    project whose trial recorded nothing.
    """
    response = _list(client, fixture, project_id="proj-nowhere")
    assert response.status_code == 403, response.text
    assert response.json()["reason"] == "chain_project_not_found"


# --------------------------------------------------------------------------- #
# the two closed vocabularies at the layer
# --------------------------------------------------------------------------- #


def _record_directly(fixture: BindingFixture, **overrides: Any) -> None:
    """One well-formed issue, recorded through the layer rather than the wire.

    **The application layer is a public door.** The tool that walks the
    pilot's feedback form into the record
    (``scripts/pilot_feedback_ingest.py``) calls
    :func:`labcairn.application.issues.record_issue` directly, so the
    request body's ``Literal`` never stands between it and the store. The
    witnesses below reach the layer the same way that tool does.
    """
    arguments: dict[str, Any] = {
        "issue_id": "issue-direct",
        "project_id": fixture.project_id,
        "version_id": fixture.version_id,
        "step": "apply",
        "error_text": "the apply step stalled for two minutes and then refused",
        "severity": "serious",
        "category": "function",
        "reported_by": "student-a",
    }
    arguments.update(overrides)
    record_issue(fixture.context, **arguments)


def test_a_type_outside_the_closed_five_is_refused_by_the_layer(
    fixture: BindingFixture,
) -> None:
    """§9.4's type is a closed five, and the layer refuses a sixth by name.

    **The wire's 422 is the friendly error; this refusal is the
    invariant.** The request body carries the five words as a
    ``Literal``, so a browser is told which words the service accepts --
    but a caller that reached past the wire gets no such help, and the
    layer is the last line before a row is written. So the layer refuses
    the same word, by the same reason, and names the word that was wrong
    rather than letting the store's CHECK constraint fail in the middle
    of the transaction.
    """
    with pytest.raises(ApplicationRefusedError) as caught:
        _record_directly(fixture, issue_id="issue-bad-type", category="network")

    assert caught.value.reason is ApplicationRefusal.PILOT_ISSUE_CATEGORY_UNKNOWN
    assert caught.value.reason.value == "pilot_issue_category_unknown"
    assert "network" in caught.value.detail
    # The refusal came before the store was asked: no row was written.
    assert fixture.context.store.session.get(PilotIssueRow, "issue-bad-type") is None


def test_a_severity_outside_the_closed_four_is_refused_by_the_layer(
    fixture: BindingFixture,
) -> None:
    """§9.4's severity is a closed four, and the layer refuses a fifth by name.

    **The write's own guard, watched where it fires.** The filtering path
    has its own severity check, and the witness for that one reaches it
    through a listing; this guard is the one inside the write, and it is
    reached by the same door the ingest tool uses. Without it the store's
    CHECK constraint would refuse the row -- late, in the middle of the
    transaction, and with a reason nobody can branch on.
    """
    with pytest.raises(ApplicationRefusedError) as caught:
        _record_directly(fixture, issue_id="issue-bad-severity", severity="catastrophic")

    assert caught.value.reason is ApplicationRefusal.PILOT_ISSUE_SEVERITY_UNKNOWN
    assert caught.value.reason.value == "pilot_issue_severity_unknown"
    assert "catastrophic" in caught.value.detail
    # The refusal came before the store was asked: no row was written.
    assert fixture.context.store.session.get(PilotIssueRow, "issue-bad-severity") is None


def test_a_well_formed_issue_is_written_by_the_same_door(
    fixture: BindingFixture,
) -> None:
    """The layer's own door writes a row when the tags are inside the lists.

    **The refusal above is the tags' check and not a closed door.** A
    witness that only ever saw refusals would not know whether the layer
    can record at all; this one records through the same door and reads
    the row back out of the store.
    """
    _record_directly(fixture, issue_id="issue-direct")

    row = fixture.context.store.session.get(PilotIssueRow, "issue-direct")
    assert row is not None
    assert row.category == "function"
    assert row.severity == "serious"
    assert row.status == "open"


# --------------------------------------------------------------------------- #
# the status walk
# --------------------------------------------------------------------------- #


def test_an_issue_is_confirmed_then_fixed_with_its_fix_version(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The walk: open -> confirmed -> fixed, naming the version that fixed it.

    **A fixed issue names the version that fixed it.** The fix version is
    what the trial's regression check reads when it re-opens the
    manuscript; the regression note travels with it, in the words the team
    agreed on.
    """
    wired, token = client
    recorded = _record(client, _record_body(fixture))
    assert recorded.status_code == 201, recorded.text

    confirmed = wired.patch(
        "/issues/issue-1/status",
        json={"project_id": fixture.project_id, "status": "confirmed"},
        headers=_headers(token),
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["issue"]["status"] == "confirmed"
    assert confirmed.json()["issue"]["fix_version"] is None

    fixed = wired.patch(
        "/issues/issue-1/status",
        json={
            "project_id": fixture.project_id,
            "status": "fixed",
            "fix_version": "ver-fix-1",
            "regression_note": "re-open the marked draft and check the reply table",
        },
        headers=_headers(token),
    )
    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["issue"]["status"] == "fixed"
    assert fixed.json()["issue"]["fix_version"] == "ver-fix-1"
    assert fixed.json()["issue"]["regression_note"] == (
        "re-open the marked draft and check the reply table"
    )

    # The walk is visible in the listing, too.
    fixed_list = _list(client, fixture, status="fixed")
    assert [row["issue_id"] for row in fixed_list.json()] == ["issue-1"]


def test_a_fixed_issue_without_a_fix_version_is_refused(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """A fix without a version is a claim the next regression cannot check.

    **The refusal is the record's own rule**, not the wire's: the body's
    ``fix_version`` is optional, because a wontfix carries none, and the
    layer demands it for the one move that claims the problem is solved.
    """
    wired, token = client
    assert _record(client, _record_body(fixture)).status_code == 201
    assert (
        wired.patch(
            "/issues/issue-1/status",
            json={"project_id": fixture.project_id, "status": "confirmed"},
            headers=_headers(token),
        ).status_code
        == 200
    )
    refused = wired.patch(
        "/issues/issue-1/status",
        json={"project_id": fixture.project_id, "status": "fixed"},
        headers=_headers(token),
    )
    assert refused.status_code == 403, refused.text
    assert refused.json()["reason"] == "arguments_invalid"

    # The refusal left the row where it was: still confirmed, still not fixed.
    still = _list(client, fixture, status="confirmed")
    assert [row["issue_id"] for row in still.json()] == ["issue-1"]


def test_a_status_move_that_skips_a_state_is_refused(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The states are walked, not set: an open issue is not fixed outright.

    **A caller that set a status outright could record a confirmation
    nobody made.** The trial's own record of *what happened* is the
    sequence, so the sequence is what the layer enforces -- by name, and
    without writing the row.
    """
    wired, token = client
    assert _record(client, _record_body(fixture)).status_code == 201

    skipped = wired.patch(
        "/issues/issue-1/status",
        json={
            "project_id": fixture.project_id,
            "status": "fixed",
            "fix_version": "ver-fix-1",
        },
        headers=_headers(token),
    )
    assert skipped.status_code == 403, skipped.text
    assert skipped.json()["reason"] == "pilot_issue_status_move_refused"

    # An open issue cannot be wontfix'd either: someone has to have
    # confirmed it first.
    wontfix = wired.patch(
        "/issues/issue-1/status",
        json={"project_id": fixture.project_id, "status": "wontfix"},
        headers=_headers(token),
    )
    assert wontfix.status_code == 403, wontfix.text
    assert wontfix.json()["reason"] == "pilot_issue_status_move_refused"

    # And an unknown word is not a state at all.
    unknown = wired.patch(
        "/issues/issue-1/status",
        json={"project_id": fixture.project_id, "status": "reopened"},
        headers=_headers(token),
    )
    assert unknown.status_code == 422, unknown.text


def test_a_closed_issue_moves_nowhere(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """Reopening a fixed issue is a new record, not an edit of the first.

    **The history is the record.** A fixed row that could be re-opened
    would stop saying what happened, and the trial's count of fixed
    problems -- one of §9.3's efficiency readings -- would be a count of
    whichever state the last caller left.
    """
    wired, token = client
    assert _record(client, _record_body(fixture)).status_code == 201
    assert (
        wired.patch(
            "/issues/issue-1/status",
            json={"project_id": fixture.project_id, "status": "confirmed"},
            headers=_headers(token),
        ).status_code
        == 200
    )
    assert (
        wired.patch(
            "/issues/issue-1/status",
            json={
                "project_id": fixture.project_id,
                "status": "fixed",
                "fix_version": "ver-fix-1",
            },
            headers=_headers(token),
        ).status_code
        == 200
    )
    reopened = wired.patch(
        "/issues/issue-1/status",
        json={"project_id": fixture.project_id, "status": "confirmed"},
        headers=_headers(token),
    )
    assert reopened.status_code == 403, reopened.text
    assert reopened.json()["reason"] == "pilot_issue_status_move_refused"

    # A wontfix closes the walk the same way.
    assert _record(client, _record_body(fixture, issue_id="issue-2")).status_code == 201
    assert (
        wired.patch(
            "/issues/issue-2/status",
            json={"project_id": fixture.project_id, "status": "confirmed"},
            headers=_headers(token),
        ).status_code
        == 200
    )
    wontfix = wired.patch(
        "/issues/issue-2/status",
        json={
            "project_id": fixture.project_id,
            "status": "wontfix",
            "regression_note": "upstream reader limitation; worked around by hand",
        },
        headers=_headers(token),
    )
    assert wontfix.status_code == 200, wontfix.text
    assert wontfix.json()["issue"]["status"] == "wontfix"
    assert wontfix.json()["issue"]["regression_note"] == (
        "upstream reader limitation; worked around by hand"
    )
    after = wired.patch(
        "/issues/issue-2/status",
        json={"project_id": fixture.project_id, "status": "confirmed"},
        headers=_headers(token),
    )
    assert after.status_code == 403, after.text
    assert after.json()["reason"] == "pilot_issue_status_move_refused"


def test_a_status_move_on_an_unknown_or_foreign_issue_is_refused(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The move names an issue that is there, under the project it belongs to.

    **An issue belongs to one project.** A move addressed to an issue of
    another project -- or to an id nobody recorded -- is refused by name,
    and the row it named keeps the state it had.
    """
    wired, token = client
    assert _record(client, _record_body(fixture)).status_code == 201

    nowhere = wired.patch(
        "/issues/issue-nowhere/status",
        json={"project_id": fixture.project_id, "status": "confirmed"},
        headers=_headers(token),
    )
    assert nowhere.status_code == 403, nowhere.text
    assert nowhere.json()["reason"] == "pilot_issue_not_found"

    # The project is checked first -- the same order the record takes --
    # so a move under a project nobody holds is refused as a project, and
    # the issue row it named keeps the state it had.
    foreign_project = wired.patch(
        "/issues/issue-1/status",
        json={"project_id": "proj-nowhere", "status": "confirmed"},
        headers=_headers(token),
    )
    assert foreign_project.status_code == 403, foreign_project.text
    assert foreign_project.json()["reason"] == "chain_project_not_found"

    still_open = _list(client, fixture)
    assert [row["status"] for row in still_open.json()] == ["open"]


def test_a_foreign_token_is_refused_on_the_issue_routes(
    client: tuple[TestClient, str], fixture: BindingFixture
) -> None:
    """The session guard covers the issue routes like every other route.

    **A read is free, a mutation is not.** The guard's rule is that the
    safe methods may proceed on any token and a mutation may not proceed
    on a wrong one -- so the witness is a *write*: an issue recorded with
    a token that is not the service's is refused, the same way a foreign
    token on ``/review/suggestion`` is.
    """
    wired, _token = client
    response = wired.post(
        "/issues",
        json=_record_body(fixture),
        headers={"Authorization": "Bearer not-the-token"},
    )
    assert response.status_code == 401, response.text
    assert response.json()["reason"] == "session_required"

    patched = wired.patch(
        "/issues/issue-1/status",
        json={"project_id": fixture.project_id, "status": "confirmed"},
        headers={"Authorization": "Bearer not-the-token"},
    )
    assert patched.status_code == 401, patched.text
    assert patched.json()["reason"] == "session_required"
