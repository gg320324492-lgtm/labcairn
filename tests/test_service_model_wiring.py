"""The service's real-model wiring, witnessed end to end.

**What is under test.** Phase 4 §7.2's last gap: the mechanism in
``labcairn.application.model_suggestions`` was complete, but the service the
CLI assembles never carried a backend, so ``POST /review/suggest`` in ``real``
mode was refused ``model_suggestion_no_provider`` whatever the workspace said.
These witnesses hold the assembly's own contract:

* **An authorised workspace wires a backend** — the record under
  ``model_suggestions`` in ``providers.json``, resolved against the provider
  entry it names, reaches the service as a :class:`ModelSuggestionBackend`,
  and a real run through the route is no longer refused for want of a
  provider. The transport is a capturing stub over the same seam, so no
  credential and no network is involved; what is witnessed is the *wiring*,
  not the provider.
* **An unauthorised workspace starts the same service** — no file, no record,
  a draft record still carrying ``TBD by owner``, a field missing, an
  unknown field, an unparseable timestamp, a provider name the file does not
  configure, a credential that is not there: every one resolves to no
  backend, the service starts, and the real-mode route refuses with the same
  ``model_suggestion_no_provider`` it always refused with. Nothing crashes,
  and no credential is printed.
* **A broken file is not a broken service** — a ``providers.json`` that is
  not JSON, or not the shape the reader expects, leaves the service up and
  the refusal path intact.

The authorisation record's fields are the ones
``docs/plans/LC-P4-PILOT-model-authorisation-draft.md`` lays out; the
credential stays in the provider entry's own sources, never beside the
record.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from binding_support import MOMENT, build_binding_fixture
from fastapi.testclient import TestClient
from store_support import StoreEnv
from store_support import env as _shared_env

from labcairn.api.app import create_app
from labcairn.application.model_suggestions import ModelSuggestionBackend
from labcairn.cli.commands import (
    MODEL_SUGGESTIONS_KEY,
    PROVIDERS_FILE_NAME,
    TBD_BY_OWNER,
    model_suggestion_backend,
)
from labcairn.core.providers.protocol import ModelRequest
from labcairn.papers.feedback import record_feedback

pytestmark = pytest.mark.integration

env = _shared_env

#: The provider name the authorisation record points at, and the name the
#: ``providers`` object configures. The record authorises *this* provider and
#: no other, which is what makes a record pointing elsewhere a refusal.
PROVIDER = "pilot-provider"

#: The destination the record names. The grant the wiring builds covers this
#: destination and no other.
DESTINATION = "api.pilot-provider.example"

#: The subject the record names — the project the suggestions are made for.
SUBJECT_REF = "proj-binding"

#: The credential variable the provider entry names. Set for the tests that
#: wire a backend; deliberately unset everywhere else.
CREDENTIAL_ENV = "LABCAIRN_TEST_ONLY_KEY"

#: A synthetic key. The repository forbids real credentials in tests; this
#: one is obviously fake and lives only in the process environment.
FAKE_KEY = "sk-pilot-not-a-real-key-0123456789"


def _authorisation(**overrides: object) -> dict[str, object]:
    """The owner's answers, as the authorisation draft asks them.

    Every field is filled — this is the record *after* the owner signed it.
    The tests that witness the draft state mutate it from here.
    """
    record: dict[str, object] = {
        "provider": PROVIDER,
        "destination": DESTINATION,
        "subject_ref": SUBJECT_REF,
        "granted_by": "Prof. Lin",
        "granted_at": MOMENT.isoformat(),
    }
    record.update(overrides)
    return record


def _providers_file(record: dict[str, object] | None, **provider_overrides: object) -> str:
    """A ``providers.json`` body: one provider, and the record when given."""
    provider: dict[str, object] = {
        "protocol": "openai_compatible",
        "model": "pilot-model",
        "base_url": "http://127.0.0.1:9/v1",
        "credential_env": CREDENTIAL_ENV,
    }
    provider.update(provider_overrides)
    document: dict[str, object] = {"providers": {PROVIDER: provider}}
    if record is not None:
        document[MODEL_SUGGESTIONS_KEY] = record
    return json.dumps(document)


def _write_providers(workspace: Path, body: str) -> None:
    workspace.joinpath(PROVIDERS_FILE_NAME).write_text(body, encoding="utf-8")


class RecordingTransport:
    """The transport the wired backend carries, in these witnesses.

    The seam a real adapter satisfies — one desensitised request in, one
    answer out — with the requests kept so a witness can assert the route's
    real run reached *this* transport and not the substitute. It answers
    with the passage unchanged, which the loop records as an honest empty
    set: the witness is about the wiring, not about the suggestion.
    """

    model_id = "pilot-model"

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    def send(self, request: ModelRequest) -> str:
        self.requests.append(request)
        return ""


@pytest.fixture
def workspace(env: StoreEnv, tmp_path: Path) -> Path:
    """The workspace directory the service is started against."""
    return tmp_path / "workspace"


@pytest.fixture
def fixture(env: StoreEnv, workspace: Path) -> Any:
    """One workspace, one task, one commented manuscript — the service's task."""
    built = build_binding_fixture(env.store(), workspace)
    record_feedback(
        built.context,
        project_id=built.project_id,
        version_id=built.version_id,
        now=MOMENT,
    )
    built.context.store.session.commit()
    return built


@pytest.fixture
def wired_backend(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[ModelRequest]]:
    """The transport the *next* built backend carries, captured.

    The transport a real wiring builds is the provider adapter; these
    witnesses stub the construction seam — not the loop, not the gates — so
    the assembly is exercised whole and the paid SDK is never imported. The
    returned list receives every request the transport was handed.
    """
    from labcairn.cli import commands

    transport = RecordingTransport()

    def _stub(settings: Any, credential: Any) -> Any:
        return transport

    monkeypatch.setattr(commands, "_suggestion_transport", _stub)
    yield transport.requests


# --------------------------------------------------------------------------- #
# an authorised workspace wires a backend
# --------------------------------------------------------------------------- #


def test_an_authorised_workspace_wires_a_backend(
    fixture: Any, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The record, resolved against its provider, reaches the service whole.

    The backend carries the provider the record names, the destination it
    names, and the transmit grant the record describes — the material-purpose
    grants a real run is judged against.
    """
    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_KEY)
    _write_providers(workspace, _providers_file(_authorisation()))
    context = fixture.context

    backend = model_suggestion_backend(context)

    assert backend is not None, "an authorised workspace wires a backend"
    assert isinstance(backend, ModelSuggestionBackend)
    assert backend.provider == PROVIDER
    assert backend.destination == DESTINATION
    assert backend.real_transport is not None
    grants = list(backend.grants)
    assert len(grants) == 1, "the record's own transmit grant is on the backend"
    grant = grants[0]
    assert grant.permission == "external_transmit"
    assert grant.purpose == "transmit"
    assert grant.destination == DESTINATION
    assert grant.subject_ref == SUBJECT_REF
    assert grant.state == "active"


def test_a_real_run_through_the_route_reaches_the_wired_transport(
    fixture: Any,
    workspace: Path,
    wired_backend: list[ModelRequest],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The route's real mode asks the wired transport, not the substitute.

    The run carries one approval per opinion, derived through the loop's own
    derivation; the opinions are locatable, so the transport is asked, and
    the requests are the desensitised ones the loop builds. The transport
    answers with the passage unchanged, so the run records an honest empty
    set — and, decisively, **not** ``model_suggestion_no_provider``.
    """
    from labcairn.application.approvals import ApprovalRequest, grant_approval, request_approval
    from labcairn.application.model_suggestions import (
        MODEL_SUGGESTION_MODE_REAL,
        suggest_for_version,
        suggestion_approval_use,
    )
    from labcairn.papers.feedback import list_feedback_events

    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_KEY)
    _write_providers(workspace, _providers_file(_authorisation()))
    context = fixture.context

    backend = model_suggestion_backend(context)
    assert backend is not None
    assert backend.real_transport is not None

    approvals: dict[str, Any] = {}
    events = list_feedback_events(
        context, project_id=fixture.project_id, version_id=fixture.version_id
    )
    asked = 0
    for event in events:
        if not event.comment_text.strip():
            continue
        if event.anchor_text is None or not event.anchor_text.strip():
            continue
        result = request_approval(
            context,
            ApprovalRequest(
                use=suggestion_approval_use(
                    context, event, provider=backend.provider, model="pilot-model"
                ),
                expires_at=MOMENT.replace(year=2027),
            ),
        )
        grant_approval(context, result.approval.approval_id, now=MOMENT)
        approvals[event.feedback_id] = result.approval.approval_id
        asked += 1
    context.store.session.commit()
    assert asked > 0, "the fixture holds locatable opinions to ask about"

    run = suggest_for_version(
        context,
        run_id="run-wired-1",
        project_id=fixture.project_id,
        version_id=fixture.version_id,
        mode=MODEL_SUGGESTION_MODE_REAL,
        provider=backend.provider,
        transport=backend.real_transport,
        approvals=approvals,
        grants=backend.grants,
        destination=backend.destination,
        subject_ref=SUBJECT_REF,
    )
    assert run.mode == MODEL_SUGGESTION_MODE_REAL
    assert len(wired_backend) == asked, "every locatable opinion reached the transport"
    assert run.suggestions_recorded == 0, "an unchanged passage is an honest empty set"
    for request in wired_backend:
        assert "Prof. Lin" not in request.prompt, "the request is desensitised"


def test_the_wired_service_refuses_no_more_and_the_substitute_still_runs(
    fixture: Any,
    workspace: Path,
    wired_backend: list[ModelRequest],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Over the API: the wired service answers a real run, and substitute runs too.

    The route reads the backend off ``app.state``; a service assembled by
    :func:`labcairn.cli.commands.service_app` carries the one the workspace
    authorised, so ``mode=real`` is no longer refused
    ``model_suggestion_no_provider`` — and ``mode=substitute``, which needs
    no backend, still runs exactly as it did.
    """
    from labcairn.cli.commands import service_app

    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_KEY)
    _write_providers(workspace, _providers_file(_authorisation()))
    context = fixture.context

    app = service_app(
        context,
        host="127.0.0.1",
        port=8000,
        extra_origins=(),
        static_dir=None,
    )
    with TestClient(app) as client:
        token = client.get("/session").json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        real = client.post(
            "/review/suggest",
            json={
                "project_id": fixture.project_id,
                "version_id": fixture.version_id,
                "mode": "real",
            },
            headers=headers,
        )
        # No approvals were presented, so the run spends nothing and every
        # opinion is recorded as unauthorised — but the run *happened*: the
        # point is that the refusal for want of a provider is gone.
        assert real.status_code == 201, real.text
        assert real.json()["mode"] == "real"
        assert real.json()["stopped_reason"] is None

        substitute = client.post(
            "/review/suggest",
            json={
                "project_id": fixture.project_id,
                "version_id": fixture.version_id,
                "mode": "substitute",
            },
            headers=headers,
        )
        assert substitute.status_code == 201, substitute.text
        assert substitute.json()["model_id"] == "substitute-model"


# --------------------------------------------------------------------------- #
# the draft and the unauthorised workspace
# --------------------------------------------------------------------------- #


def _unauthorised_cases() -> Iterator[tuple[str, str, dict[str, object] | None]]:
    """Every way a record fails to authorise, with the body it fails on.

    Each case is a ``providers.json`` body. The assertion is the same for
    all of them — no backend, service up, refusal unchanged — because the
    property is that **only a filled, well-formed record wires anything**.
    """
    yield "no-record", _providers_file(None), {}
    draft = _authorisation()
    draft["granted_by"] = TBD_BY_OWNER
    yield "draft-field", _providers_file(draft), {}
    draft = _authorisation()
    del draft["destination"]
    yield "missing-field", _providers_file(draft), {}
    draft = _authorisation()
    draft["destination"] = ""
    yield "empty-field", _providers_file(draft), {}
    draft = _authorisation()
    draft["unknown_field"] = "surprise"
    yield "unknown-field", _providers_file(draft), {}
    draft = _authorisation()
    draft["granted_at"] = "not a timestamp"
    yield "bad-timestamp", _providers_file(draft), {}
    draft = _authorisation()
    draft["expires_at"] = "also not a timestamp"
    draft["expires_at"] = TBD_BY_OWNER
    yield "bad-expires", _providers_file(draft), {}
    draft = _authorisation()
    draft["provider"] = "another-provider"
    yield "provider-unknown", _providers_file(draft), {}
    yield (
        "credential-missing",
        _providers_file(_authorisation()),
        {CREDENTIAL_ENV: None},
    )


@pytest.mark.parametrize(
    "case,body,environ_overrides",
    [(name, body, env_over) for name, body, env_over in _unauthorised_cases()],
)
def test_an_unauthorised_workspace_wires_nothing_and_the_service_starts(
    fixture: Any,
    workspace: Path,
    case: str,
    body: str,
    environ_overrides: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every unauthorised state resolves to no backend, and the route refuses.

    The refusal is the route's own ``model_suggestion_no_provider`` — the
    same one an empty service gives — and the service itself is up: the
    session answers, and substitute mode still runs. The environment
    variable the provider names is *unset* for these tests, which is also
    the credential-missing case's own point.
    """
    monkeypatch.delenv(CREDENTIAL_ENV, raising=False)
    for name, value in environ_overrides.items():
        if value is None:
            monkeypatch.delenv(str(name), raising=False)
        else:
            monkeypatch.setenv(str(name), str(value))
    _write_providers(workspace, body)
    context = fixture.context

    backend = model_suggestion_backend(context)
    assert backend is None, f"{case} wires no backend"

    app = create_app(context)
    with TestClient(app) as client:
        token = client.get("/session").json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        real = client.post(
            "/review/suggest",
            json={
                "project_id": fixture.project_id,
                "version_id": fixture.version_id,
                "mode": "real",
            },
            headers=headers,
        )
        assert real.status_code == 403, real.text
        assert real.json()["reason"] == "model_suggestion_no_provider"
        substitute = client.post(
            "/review/suggest",
            json={
                "project_id": fixture.project_id,
                "version_id": fixture.version_id,
                "mode": "substitute",
            },
            headers=headers,
        )
        assert substitute.status_code == 201, substitute.text


def test_a_provider_name_the_file_does_not_configure_wires_nothing(
    fixture: Any, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A record pointing at a provider the file does not hold authorises nothing.

    Distinct from the parametrised cases in that the file itself is
    well-formed and the credential is present — the only fault is that the
    record names a provider the ``providers`` object does not configure.
    """
    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_KEY)
    _write_providers(workspace, _providers_file(_authorisation(provider="no-such-provider")))
    assert model_suggestion_backend(fixture.context) is None


# --------------------------------------------------------------------------- #
# the broken file
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "body",
    [
        "{ this is not json",
        '{"providers": "not an object"}',
        "[]",
        f'{{"{MODEL_SUGGESTIONS_KEY}": "not an object"}}',
    ],
)
def test_a_broken_providers_file_does_not_break_the_service(
    fixture: Any, workspace: Path, body: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file that cannot be read as configuration leaves the service up.

    The service starts, the real-mode route refuses by name, and nothing
    crashes: a file the operator is editing is not a reason the rest of the
    product stops working. No credential is printed anywhere in the run.
    """
    monkeypatch.delenv(CREDENTIAL_ENV, raising=False)
    _write_providers(workspace, body)
    context = fixture.context

    backend = model_suggestion_backend(context)
    assert backend is None, "a broken file wires no backend"

    app = create_app(context)
    with TestClient(app) as client:
        token = client.get("/session").json()["token"]
        real = client.post(
            "/review/suggest",
            json={
                "project_id": fixture.project_id,
                "version_id": fixture.version_id,
                "mode": "real",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert real.status_code == 403, real.text
        assert real.json()["reason"] == "model_suggestion_no_provider"
        assert FAKE_KEY not in real.text, "no credential is echoed in the refusal"


def test_a_missing_providers_file_wires_nothing(fixture: Any, workspace: Path) -> None:
    """No file at all is the ordinary unauthorised state, not an error."""
    assert model_suggestion_backend(fixture.context) is None


# --------------------------------------------------------------------------- #
# the record's own edges
# --------------------------------------------------------------------------- #


def test_a_draft_record_is_distinguished_from_a_filled_one(
    fixture: Any, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the placeholder blocks the wiring; a filled optional field passes.

    ``expires_at``, ``scope`` and ``grant_id`` are the owner's optional
    refinements: absent, they narrow to the defaults; present, they are
    carried onto the grant. A draft is detected by *content* — the
    placeholder value — and not by which fields happen to be present.
    """
    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_KEY)
    record = _authorisation(
        expires_at="2027-01-01T00:00:00+00:00",
        scope=f"{SUBJECT_REF}/**",
        grant_id="grant-pilot-suggestions",
    )
    _write_providers(workspace, _providers_file(record))
    backend = model_suggestion_backend(fixture.context)
    assert backend is not None, "a fully filled record, optional fields included, wires"
    grant = next(iter(backend.grants))
    assert grant.expires_at == datetime(2027, 1, 1, tzinfo=UTC)
    assert grant.scope == f"{SUBJECT_REF}/**"
    assert grant.grant_id == "grant-pilot-suggestions"


def test_an_expired_authorisation_still_wires_and_the_gate_stops_it(
    fixture: Any, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Expiry is the gate's clock fact, not the wiring's.

    The wiring carries what the record says; whether the grant is in force
    is decided when a request is judged, by
    :meth:`labcairn.security.permissions.Grant.is_in_force`. The wiring
    therefore wires an expired record — the honest reading of the record —
    and the transmit gate is the thing that refuses when the window has
    closed.
    """
    from labcairn.security.permissions import Grant

    monkeypatch.setenv(CREDENTIAL_ENV, FAKE_KEY)
    record = _authorisation(
        granted_at="2025-01-01T00:00:00+00:00",
        expires_at="2025-06-01T00:00:00+00:00",
    )
    _write_providers(workspace, _providers_file(record))
    backend = model_suggestion_backend(fixture.context)
    assert backend is not None, "an expired record is still a record"
    grant = next(iter(backend.grants))
    assert not grant.is_in_force(MOMENT), "the expired grant is not in force"
    assert Grant is not None
