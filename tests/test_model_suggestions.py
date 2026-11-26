"""The real-model suggestion loop, witnessed end to end.

**What is under test.** Phase 4 §7.2's loop, over the binding's own
three-case sample: the opinions the chain holds, a transport that answers,
and the suggestions that land in the workbench's own read. The witnesses
ask the questions the loop exists to answer:

* **End to end** — an opinion becomes a desensitised request, the request
  becomes a stored suggestion, and the stored suggestion is what
  ``GET /review/opinions`` reads back.
* **The budget stops the run and names itself** — a ceiling that fires
  mid-walk leaves the rest of the opinions unasked, and the run row says
  which stop fired.
* **A non-retryable failure is not retried** — the transport is asked
  once for the opinion, and the run falls back rather than asking again.
* **Spent retries fall back to the substitute, labelled** — the run row's
  model id and the suggestion rows' author both say ``substitute-model``.
* **An empty answer is an honest empty set** — recorded as no suggestion,
  never as a failure.
* **The request is desensitised** — the captured request body carries no
  author name, even though every fixture comment names one.

The transport is a capturing stub: the same seam a real adapter satisfies,
with the requests it received kept for the witnesses to assert against.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from binding_support import (
    EDITABLE_TEXT,
    MOMENT,
    PARAGRAPH_TEXT,
    SECOND_PARAGRAPH_TEXT,
    BindingFixture,
    build_binding_fixture,
)
from fastapi.testclient import TestClient
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.api.app import create_app
from labcairn.application.approvals import ApprovalRequest, grant_approval, request_approval
from labcairn.application.context import ApplicationContext
from labcairn.application.model_suggestions import (
    MODEL_SUGGESTION_MODE_REAL,
    MODEL_SUGGESTION_MODE_SUBSTITUTE,
    SUBSTITUTE_AUTHOR,
    SuggestionLoopConfig,
    _entry_from_record,
    read_suggestion_run,
    suggest_for_version,
    suggestion_approval_use,
)
from labcairn.application.refusal import ApplicationRefusedError
from labcairn.core.providers.protocol import ModelRequest, UsageReport
from labcairn.core.providers.usage import Known, Unknown, UnknownReason
from labcairn.papers.feedback import list_feedback_events, record_feedback
from labcairn.security.permissions import Grant

pytestmark = pytest.mark.integration

env = _shared_env

#: The destination the real run's transmit grant names. The grant covers
#: this destination and no other, which is what makes a destination
#: mismatch a refusal rather than a silent send.
DESTINATION = "api.test-provider.example"

#: The provider name the real run's approvals and requests share. The
#: digest the approval is bound to covers it, so a run that asked under one
#: provider and sent under another would be refused — which is the point.
PROVIDER = "test-provider"


class CapturingTransport:
    """A transport that answers every request and keeps what it was sent.

    The stub the witnesses drive instead of a provider: same seam, no
    credential, and a record of every request body so the desensitisation
    witness can assert against what actually left. ``answers`` are handed
    out one per call, the last one repeating when the run asks more than
    the script holds.
    """

    def __init__(
        self,
        *,
        model_id: str = "gpt-test-model",
        answers: list[str] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.model_id = model_id
        self._answers = list(answers) if answers is not None else None
        self._error = error
        self.requests: list[ModelRequest] = []
        self.calls = 0

    def send(self, request: ModelRequest) -> str:
        """Record the request, then answer or raise, as the script says."""
        self.requests.append(request)
        self.calls += 1
        if self._error is not None:
            raise self._error
        if self._answers is None:
            return "The method estimates the parameter theta."
        index = min(self.calls - 1, len(self._answers) - 1)
        return self._answers[index]


class _ReportingTransport(CapturingTransport):
    """A transport that also reports what the provider spent.

    The seam a real adapter presents: the answer, and the provider's own
    usage report for the call it just made. ``usage`` is what the provider
    reports on every call, and leaving it ``None`` makes the transport
    report nothing at all — the case the fallback estimate exists for.
    """

    def __init__(
        self,
        *,
        usage: UsageReport | None = None,
        model_id: str = "gpt-test-model",
        answers: list[str] | None = None,
    ) -> None:
        super().__init__(model_id=model_id, answers=answers)
        self._usage = usage

    def last_usage(self) -> UsageReport | None:
        """The provider's own report for the call just made."""
        return self._usage


class _HTTPStatusError(Exception):
    """A third-party-shaped exception: an HTTP status, duck-typed the way
    ``httpx.HTTPStatusError`` and ``pydantic_ai.ModelHTTPError`` both carry one.

    The loop's classification reads the status off the exception — 401 is
    an auth refusal and not retried; 500 is transient and retried — which
    is the same path a real provider error takes through
    :func:`classify_exception`.
    """

    def __init__(self, status_code: int) -> None:
        super().__init__(f"HTTP {status_code}")
        self.response = _ResponseStatus(status_code)


class _ResponseStatus:
    """The ``response.status_code`` the classifier duck-types on."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def _failure(*, retryable: bool) -> Exception:
    """A transport failure of the retryability the caller asks for.

    A 500 is transient and retried; a 401 is an auth rejection and is not
    — the same request would be refused again, so retrying it would spend
    the budget on a foregone conclusion. The classification is the
    provider layer's own, read off the status the way a real error
    arrives.
    """
    return _HTTPStatusError(500 if retryable else 401)


def _grant_for(project_id: str, destination: str = DESTINATION) -> Grant:
    """The material-purpose transmit grant a real run is judged against.

    The same shape the model-call path's own witnesses hold, scoped to the
    fixture's project and to one destination.
    """
    return Grant(
        grant_id=f"grant-suggest-{project_id}",
        subject_ref=project_id,
        permission="external_transmit",
        purpose="transmit",
        scope=f"{project_id}/**",
        destination=destination,
        granted_by="Prof. Lin",
        granted_at=MOMENT,
        expires_at=None,
        state="active",
        withdrawn_at=None,
        withdrawn_by=None,
        withdrawal_reason=None,
    )


@pytest.fixture
def fixture(env: StoreEnv, tmp_path: Path) -> BindingFixture:
    """The binding's three-case sample: one workspace, one commented manuscript."""
    return build_binding_fixture(env.store(), tmp_path / "workspace")


@pytest.fixture
def commented(fixture: BindingFixture) -> BindingFixture:
    """The fixture with its comments recorded, so the chain holds opinions.

    The loop reads the opinions the chain holds; without this read the
    walk has nothing to walk, and a green run would mean nothing.
    """
    record_feedback(
        fixture.context,
        project_id=fixture.project_id,
        version_id=fixture.version_id,
        now=MOMENT,
    )
    fixture.context.store.session.commit()
    return fixture


@pytest.fixture
def client(commented: BindingFixture) -> Iterator[tuple[TestClient, str]]:
    """A client for the service, with the fixture's context behind it.

    The service carries no real-model backend — the substitute run needs
    none, and a real run against this service is refused by name, which is
    its own witness below.
    """
    context: ApplicationContext = commented.context
    app = create_app(context, event_source=_NoEvents())
    with TestClient(app) as wired:
        session = wired.get("/session")
        assert session.status_code == 200
        token = str(session.json()["token"])
        yield wired, token


class _NoEvents:
    """An event source that serves nothing: these witnesses call no stream.

    It satisfies the ``EventSource`` protocol's shape, and it is never
    reached - the suggestion-loop witnesses call no stream route.
    """

    def page(self, session: Any, request: Any) -> Any:
        raise NotImplementedError("these witnesses call no stream route")


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _opinions(client: TestClient, token: str, fixture: BindingFixture) -> list[dict[str, Any]]:
    """The workbench's own read, over the fixture's project and version."""
    response = client.get(
        "/review/opinions",
        params={"project_id": fixture.project_id, "version_id": fixture.version_id},
        headers=_headers(token),
    )
    assert response.status_code == 200, response.text
    return list(response.json()["opinions"])


def _approvals_for(fixture: BindingFixture, model_id: str) -> dict[str, Any]:
    """Ask, grant, and return one approval per locatable opinion.

    The approvals are derived through the one derivation the loop spends
    against — the same ``suggestion_approval_use`` — so the question the
    fixture answered and the request the loop makes are the same request,
    digest and all.
    """
    approvals: dict[str, Any] = {}
    events = list_feedback_events(
        fixture.context, project_id=fixture.project_id, version_id=fixture.version_id
    )
    for event in events:
        if not event.comment_text.strip():
            continue
        if event.anchor_text is None or not event.anchor_text.strip():
            continue
        asked = request_approval(
            fixture.context,
            ApprovalRequest(
                use=suggestion_approval_use(
                    fixture.context, event, provider=PROVIDER, model=model_id
                ),
                expires_at=MOMENT.replace(year=2027),
            ),
        )
        grant_approval(fixture.context, asked.approval.approval_id, now=MOMENT)
        approvals[event.feedback_id] = asked.approval.approval_id
    fixture.context.store.session.commit()
    return approvals


def _run_real(
    fixture: BindingFixture,
    transport: CapturingTransport,
    *,
    run_id: str,
    config: SuggestionLoopConfig | None = None,
) -> Any:
    """A real run over the fixture's opinions, with one approval per opinion."""
    return suggest_for_version(
        fixture.context,
        run_id=run_id,
        project_id=fixture.project_id,
        version_id=fixture.version_id,
        mode=MODEL_SUGGESTION_MODE_REAL,
        provider=PROVIDER,
        transport=transport,
        approvals=_approvals_for(fixture, transport.model_id),
        grants=[_grant_for(fixture.project_id)],
        destination=DESTINATION,
        config=config,
    )


# --------------------------------------------------------------------------- #
# end to end: opinion → request → suggestion → read back
# --------------------------------------------------------------------------- #


def test_a_substitute_run_records_suggestions_the_workbench_reads(
    commented: BindingFixture, client: tuple[TestClient, str]
) -> None:
    """The loop's whole path: opinion in, stored suggestion out, workbench shows it.

    The substitute source answers both locatable opinions; the unplaceable
    third has no passage to rewrite and is left out of the walk rather
    than pretended handled. What the loop records is what
    ``GET /review/opinions`` reads — one store, two surfaces, the same
    bytes.
    """
    wired, token = client
    run = suggest_for_version(
        commented.context,
        run_id="run-sub-1",
        project_id=commented.project_id,
        version_id=commented.version_id,
        mode=MODEL_SUGGESTION_MODE_SUBSTITUTE,
    )
    assert run.mode == MODEL_SUGGESTION_MODE_SUBSTITUTE
    assert run.model_id == SUBSTITUTE_AUTHOR
    assert run.suggestions_recorded == 2, (
        "the sample holds two locatable opinions, and the substitute answers both"
    )
    assert run.stopped_reason is None, "a walk that runs out of opinions stops for no reason"
    assert run.requests_made == 2

    opinions = _opinions(wired, token, commented)
    with_suggestions = [o for o in opinions if o["suggestion"] is not None]
    assert len(with_suggestions) == 2
    for opinion in with_suggestions:
        assert opinion["suggestion"]["author"] == SUBSTITUTE_AUTHOR
        # The seam's unit is the whole paragraph: the stored old_text is
        # the paragraph the anchor sits in, not the anchor's substring.
        assert opinion["suggestion"]["old_text"] in (PARAGRAPH_TEXT, SECOND_PARAGRAPH_TEXT)


def test_a_real_run_spends_one_approval_per_opinion_and_records_the_answer(
    commented: BindingFixture, client: tuple[TestClient, str]
) -> None:
    """A real run asks the wired transport and stores what it said, as ``model:<id>``.

    One digest-bound approval per opinion — the consent the caller presents
    is the consent the loop spends — and the stored suggestion's author
    names the model that answered, not the substitute.
    """
    wired, token = client
    transport = CapturingTransport()
    run = _run_real(commented, transport, run_id="run-real-1")
    assert run.mode == MODEL_SUGGESTION_MODE_REAL
    assert run.model_id == transport.model_id
    assert run.suggestions_recorded == 2
    assert len(transport.requests) == 2, "one desensitised request per locatable opinion"
    assert run.stopped_reason is None

    opinions = _opinions(wired, token, commented)
    answered = [o for o in opinions if o["suggestion"] is not None]
    assert len(answered) == 2
    for opinion in answered:
        assert opinion["suggestion"]["author"] == f"model:{transport.model_id}"
        assert "theta" in opinion["suggestion"]["new_text"]


# --------------------------------------------------------------------------- #
# the budget stops the run, and names itself
# --------------------------------------------------------------------------- #


def test_the_request_budget_stops_the_walk_and_names_the_stop(
    commented: BindingFixture,
) -> None:
    """A one-request ceiling answers the first opinion and skips the second.

    The ceiling is checked before each call, so the overshoot is zero
    requests: the source is asked once, the second opinion is recorded as
    skipped, and the run row says ``request_budget``.
    """
    run = suggest_for_version(
        commented.context,
        run_id="run-budget-1",
        project_id=commented.project_id,
        version_id=commented.version_id,
        mode=MODEL_SUGGESTION_MODE_SUBSTITUTE,
        config=SuggestionLoopConfig(max_requests=1),
    )
    assert run.stopped_reason == "request_budget"
    assert run.suggestions_recorded == 1
    assert run.opinions_skipped == 1
    assert run.requests_made == 1, "the overshoot is zero requests, not one"


def test_the_token_budget_stops_the_walk_and_names_the_stop(
    commented: BindingFixture,
) -> None:
    """A token ceiling the first answer crosses stops the walk under ``token_budget``.

    The estimate is the figure the ceiling is checked against — the seam
    returns text, not usage — and the row records the estimate as an
    estimate, never as a measured count.
    """
    run = suggest_for_version(
        commented.context,
        run_id="run-budget-2",
        project_id=commented.project_id,
        version_id=commented.version_id,
        mode=MODEL_SUGGESTION_MODE_SUBSTITUTE,
        config=SuggestionLoopConfig(max_tokens=10),
    )
    assert run.stopped_reason == "token_budget"
    assert run.tokens_estimated > 10
    assert run.suggestions_recorded == 1
    assert run.opinions_skipped == 1


# --------------------------------------------------------------------------- #
# what the provider reported, and what was counted
# --------------------------------------------------------------------------- #


def test_the_token_ceiling_is_checked_against_the_provider_s_own_report(
    commented: BindingFixture,
) -> None:
    """A ceiling the provider's report crosses stops the walk; the estimate would not.

    The pilot measured the gap this closes. A 1,666-character answer was
    reported as 6,089 output tokens — 3.65 tokens per character — and the
    factor moved between 1.25 and 6.75 across the round's own calls
    (``docs/acceptance/LC-P4-PILOT-real-request-2026-11-25.md`` §8.4), so a
    ceiling written from characters is written from a number that moves by
    nearly a factor of three. A ceiling of 1,000 tokens is crossed by the
    provider's report and not by the character count.

    **What makes this red:** a loop that counts the estimate instead of the
    report. The transport reports 6,089 output tokens, the character count
    for the same answer is a few hundred, and the run must stop on the
    report.
    """
    transport = _ReportingTransport(
        usage=UsageReport(input_tokens=Known(506), output_tokens=Known(6089))
    )
    run = _run_real(
        commented,
        transport,
        run_id="run-usage-report",
        config=SuggestionLoopConfig(max_tokens=1000),
    )
    assert run.stopped_reason == "token_budget"
    assert run.suggestions_recorded == 1
    assert run.opinions_skipped == 1
    assert run.tokens_measured == 6595
    assert run.tokens_estimated == 6595, "the run's token figure is the provider's report"
    assert run.token_origin == "measured"


def test_a_run_whose_provider_reported_nothing_is_recorded_as_an_estimate(
    commented: BindingFixture,
) -> None:
    """A transport that reports nothing leaves the run's tokens an estimate.

    **What makes this red:** a run that called its estimate a measurement.
    The origin would read ``measured`` for tokens nobody measured, and a
    reader would take the figure for a report.
    """
    transport = CapturingTransport()
    run = _run_real(commented, transport, run_id="run-usage-estimated")
    assert run.tokens_measured == 0
    assert run.tokens_estimated > 0
    assert run.token_origin == "estimated"


def test_the_run_records_the_provider_s_report_and_not_the_estimate(
    commented: BindingFixture,
) -> None:
    """The estimate is a fallback: it is not added on top of a measurement.

    **What makes this red:** a spend that counted the estimate for a side
    the provider had already reported. The total would be the report and
    the estimate added together, and the run would be charged twice for
    one call.
    """
    transport = _ReportingTransport(
        usage=UsageReport(input_tokens=Known(506), output_tokens=Known(6089))
    )
    run = _run_real(commented, transport, run_id="run-usage-measured")
    assert run.requests_made == len(transport.requests)
    assert run.tokens_measured == 6595 * run.requests_made
    assert run.tokens_estimated == run.tokens_measured, (
        "the estimate was not used: the provider reported every side"
    )
    assert run.token_origin == "measured"


def test_a_half_reported_response_is_recorded_as_mixed(
    commented: BindingFixture,
) -> None:
    """The provider reported the input and not the output: the run is mixed.

    **What makes this red:** a spend that dropped the unreported side
    instead of falling back to the estimate for it, or one that called the
    whole run ``measured`` when half of it was counted by LabCairn.
    """
    transport = _ReportingTransport(
        usage=UsageReport(
            input_tokens=Known(506),
            output_tokens=Unknown(UnknownReason.PROVIDER_OMITTED),
        )
    )
    run = _run_real(commented, transport, run_id="run-usage-mixed")
    assert run.token_origin == "mixed"
    assert run.tokens_measured == 506 * run.requests_made
    assert run.tokens_estimated > run.tokens_measured, (
        "the estimated part is counted beside the measured one"
    )


def test_each_request_entry_says_which_of_its_tokens_were_measured(
    commented: BindingFixture,
) -> None:
    """The entries carry the split, not only the run.

    **What makes this red:** an entry that recorded the total alone. A
    reader of one request would see a figure and could not tell whether
    the provider reported it.
    """
    transport = _ReportingTransport(
        usage=UsageReport(input_tokens=Known(506), output_tokens=Known(6089))
    )
    run = _run_real(commented, transport, run_id="run-usage-entries")
    assert run.requests
    for entry in run.requests:
        assert entry.tokens_measured == 6595
        assert entry.tokens_estimated == 6595


def test_the_row_keeps_the_split_between_what_was_measured_and_what_was_counted(
    commented: BindingFixture,
) -> None:
    """The persisted entry carries the split, so a read-back can rebuild it.

    **What makes this red:** an entry written without the measured part.
    The read-back would rebuild the run as an estimate, and a run the
    provider had measured would be recorded as a count of characters.
    """
    transport = _ReportingTransport(
        usage=UsageReport(input_tokens=Known(506), output_tokens=Known(6089))
    )
    _run_real(commented, transport, run_id="run-usage-row")

    from labcairn.db.models import ModelSuggestionRunRow

    row = commented.context.store.session.get(ModelSuggestionRunRow, "run-usage-row")
    assert row is not None
    assert row.requests_json
    for record in row.requests_json:
        assert record["tokens_measured"] == 6595
        assert record["tokens_estimated"] == 6595


def test_a_run_read_back_says_what_was_measured(commented: BindingFixture) -> None:
    """The read-back run carries the split it was written with.

    **What makes this red:** a read-back that dropped the measured part.
    The record would read as an estimate after the fact, and the run's own
    account would differ from the one the reader is shown.
    """
    transport = _ReportingTransport(
        usage=UsageReport(input_tokens=Known(506), output_tokens=Known(6089))
    )
    run = _run_real(commented, transport, run_id="run-usage-readback")
    read = read_suggestion_run(commented.context, "run-usage-readback")
    assert read.tokens_measured == run.tokens_measured
    assert read.tokens_estimated == run.tokens_estimated
    assert read.token_origin == run.token_origin


# --------------------------------------------------------------------------- #
# failure classification, retry and fallback
# --------------------------------------------------------------------------- #


def test_a_non_retryable_failure_is_not_retried_and_falls_back(
    commented: BindingFixture,
) -> None:
    """An auth refusal is asked once and never again — the same request would refuse again.

    The transport's call count is the witness: one request, not three and
    not one per opinion. The first opinion's auth refusal spends the real
    model's chance — the run falls back to the substitute and stays there,
    so the second opinion is answered locally without asking a model whose
    credential was just rejected. The substitute answers under its own
    name; the real model's failure is recorded, not papered over.
    """
    transport = CapturingTransport(error=_failure(retryable=False))
    run = _run_real(commented, transport, run_id="run-auth-1")
    assert len(transport.requests) == 1, (
        "one attempt: a non-retryable failure is not retried, and the run "
        "does not ask the rejected credential again"
    )
    assert run.model_id == SUBSTITUTE_AUTHOR, "the run row names the model that answered"
    assert run.suggestions_recorded == 2, "the substitute answered both opinions"
    assert run.stopped_reason is None


def test_spent_retries_fall_back_to_a_labelled_substitute(
    commented: BindingFixture, client: tuple[TestClient, str]
) -> None:
    """After the retry budget is spent, the substitute answers, and says so twice.

    The run row's model id becomes the substitute's, and every suggestion
    the fallback recorded carries the substitute author. **A substitute
    output that could be read as the real model's answer is the defect
    this witness exists to make impossible.**
    """
    wired, token = client
    transport = CapturingTransport(error=_failure(retryable=True))
    run = _run_real(
        commented,
        transport,
        run_id="run-fallback-1",
        config=SuggestionLoopConfig(retry_attempts=2),
    )
    assert len(transport.requests) == 3, (
        "the first opinion spent its three attempts; the run then fell back "
        "and stayed fallen back, so the second opinion was never asked"
    )
    assert run.model_id == SUBSTITUTE_AUTHOR, "the run row names the model that answered"
    assert run.suggestions_recorded == 2

    opinions = _opinions(wired, token, commented)
    answered = [o for o in opinions if o["suggestion"] is not None]
    assert len(answered) == 2
    for opinion in answered:
        assert opinion["suggestion"]["author"] == SUBSTITUTE_AUTHOR


def test_consecutive_failures_stop_the_run_and_name_the_stop(
    commented: BindingFixture,
) -> None:
    """The failure ceiling fires after the opinion that exhausted it; the rest are skipped.

    The sample holds two locatable opinions and the ceiling is one: the
    first exhausted opinion fires the stop, and the second is recorded as
    skipped rather than asked.
    """
    transport = CapturingTransport(error=_failure(retryable=True))
    run = _run_real(
        commented,
        transport,
        run_id="run-stop-1",
        config=SuggestionLoopConfig(max_consecutive_failures=1, retry_attempts=0),
    )
    assert run.stopped_reason == "consecutive_failures"
    assert run.opinions_skipped == 1
    assert run.suggestions_recorded == 0


# --------------------------------------------------------------------------- #
# the honest empty set
# --------------------------------------------------------------------------- #


def test_an_empty_answer_is_recorded_as_no_suggestion(
    commented: BindingFixture, client: tuple[TestClient, str]
) -> None:
    """An answer that changes nothing is the model's honest no, not a failure.

    The transport answers with one passage verbatim and then with the empty
    string; the loop records no suggestion and no failure, and the run
    finishes with the reason it finished: the opinions ran out. The two
    locatable opinions were asked, and neither produced an edit.
    """
    wired, token = client
    transport = CapturingTransport(answers=[PARAGRAPH_TEXT, ""])
    run = _run_real(commented, transport, run_id="run-empty-1")
    assert run.stopped_reason is None
    assert run.suggestions_recorded == 0
    assert len(transport.requests) == 2, "both locatable opinions were asked"
    opinions = _opinions(wired, token, commented)
    assert all(o["suggestion"] is None for o in opinions), "no suggestion was invented"


# --------------------------------------------------------------------------- #
# desensitisation
# --------------------------------------------------------------------------- #


def test_the_request_carries_no_author_name(commented: BindingFixture) -> None:
    """Every captured request body is free of the comment author's name.

    The fixture's comments are all signed ``Prof. Lin``; the requests the
    loop built carry the comment text and the anchor text and **never the
    signature**. This is the witness the desensitisation claim is held by:
    it reads what the transport actually received, not what the code
    intends to send. Each request carries its own comment — the first
    opinion's body is not the second's — which is what makes the
    per-opinion approval's digest the right granularity.
    """
    transport = CapturingTransport()
    _run_real(commented, transport, run_id="run-desens-1")
    assert transport.requests, "the loop asked the transport at least once"
    assert len(transport.requests) == 2, "one desensitised request per locatable opinion"
    assert EDITABLE_TEXT in transport.requests[0].prompt
    for request in transport.requests:
        assert "Prof. Lin" not in request.prompt


def test_the_run_row_accounts_for_every_call(commented: BindingFixture) -> None:
    """The run row is the budget's account: counts, estimates, and the entries.

    The row's request count covers every transport call the run made, its
    token figure is the estimate, and the JSON entries name the opinion,
    the outcome and the cost of each call — and none of them carries the
    request text.
    """
    transport = CapturingTransport()
    run = _run_real(commented, transport, run_id="run-account-1")
    assert run.requests_made == len(transport.requests)
    assert run.tokens_estimated > 0

    from labcairn.db.models import ModelSuggestionRunRow

    row = commented.context.store.session.get(ModelSuggestionRunRow, "run-account-1")
    assert row is not None
    assert row.requests_made == len(transport.requests)
    assert row.mode == MODEL_SUGGESTION_MODE_REAL
    assert row.model_id == transport.model_id
    assert row.requests_json, "every call has an entry"
    assert len(row.requests_json) == len(transport.requests)
    for entry in row.requests_json:
        assert "prompt" not in entry
        assert set(entry) >= {"feedback_id", "outcome", "attempts", "tokens_estimated"}


# --------------------------------------------------------------------------- #
# the route's own refusal and its substitute run
# --------------------------------------------------------------------------- #


def test_a_real_run_without_a_backend_is_refused_and_writes_nothing(
    commented: BindingFixture, client: tuple[TestClient, str]
) -> None:
    """A service with no real-model transport refuses a real run, by name.

    The refusal is ``model_suggestion_no_provider`` — the same rule claim
    extraction holds: a suggestion this service cannot ask for is not one
    it may simulate. Nothing is written: no run row, no suggestion rows.
    """
    wired, token = client
    response = wired.post(
        "/review/suggest",
        json={
            "project_id": commented.project_id,
            "version_id": commented.version_id,
            "mode": "real",
        },
        headers=_headers(token),
    )
    assert response.status_code == 403, response.text
    assert response.json()["reason"] == "model_suggestion_no_provider"
    opinions = _opinions(wired, token, commented)
    assert all(o["suggestion"] is None for o in opinions), "no suggestion was written"


def test_a_substitute_run_through_the_route_records_and_reads_back(
    commented: BindingFixture, client: tuple[TestClient, str]
) -> None:
    """The route's substitute run lands in the store, and the workbench reads it.

    The run needs no approvals and no transport — nothing leaves the
    machine — and the response is the account: the mode, the substitute's
    model id, the counts, and no stop.
    """
    wired, token = client
    response = wired.post(
        "/review/suggest",
        json={
            "project_id": commented.project_id,
            "version_id": commented.version_id,
            "mode": "substitute",
            "max_requests": 5,
        },
        headers=_headers(token),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["mode"] == "substitute"
    assert body["model_id"] == SUBSTITUTE_AUTHOR
    assert body["suggestions_recorded"] == 2
    assert body["stopped_reason"] is None
    opinions = _opinions(wired, token, commented)
    assert any(o["suggestion"] is not None for o in opinions)


def test_a_stored_count_is_read_back_as_the_number_it_is() -> None:
    """The record's counts come back as counts.

    **The shape a run wrote is the shape the reader reads.** A stored
    attempt count comes back as an integer and a stored duration as a
    float, whether the store spelled them as numbers or as strings — a
    record that crossed a hand-edited store can arrive spelled ``"3"``, and
    that is a measurement rather than a mystery.
    """
    entry = _entry_from_record(
        {
            "feedback_id": "fb-1",
            "source": "model-a",
            "outcome": "answered",
            "attempts": "3",
            "elapsed_s": "1.5",
            "tokens_estimated": 12,
        },
        mode=MODEL_SUGGESTION_MODE_REAL,
    )
    assert entry.attempts == 3
    assert entry.elapsed_s == 1.5
    assert entry.tokens_estimated == 12


def test_a_damaged_count_is_refused_rather_than_read_as_zero() -> None:
    """A count that does not spell a number is not a count of zero.

    **The reader does not invent a number the record does not hold.** A
    stored value that spells no number is refused, so a damaged record is
    visible rather than quietly read as a run that tried nothing and
    spent nothing. The repository's own negative control
    (``tests/test_fake_provider_invariants.py``) watches for that fold.
    """
    with pytest.raises(ApplicationRefusedError):
        _entry_from_record(
            {"feedback_id": "fb-3", "attempts": "three"},
            mode=MODEL_SUGGESTION_MODE_REAL,
        )
    with pytest.raises(ApplicationRefusedError):
        _entry_from_record(
            {"feedback_id": "fb-4", "elapsed_s": "a while"},
            mode=MODEL_SUGGESTION_MODE_REAL,
        )


def test_a_record_that_carries_no_count_is_refused_rather_than_read_as_zero() -> None:
    """A count the record does not carry is refused, not read as zero.

    **A missing field and a zero are different facts.** The run writes
    these three values itself and always writes them, so a record without
    one was not written by this writer — and reading it as a zero would
    say "it tried nothing" about a run whose attempt count was never
    recorded. The refusal names the field, so the reader knows which one is
    missing rather than seeing a run that looks as though it did nothing.
    """
    with pytest.raises(ApplicationRefusedError) as raised:
        _entry_from_record({"feedback_id": "fb-5"}, mode=MODEL_SUGGESTION_MODE_REAL)
    message = str(raised.value)
    assert "attempts" in message, f"the refusal must name the field that is missing: {message}"
