"""The local API: the three guards, the event stream, and the typed contract.

What is asserted here, and why each assertion is written the way it is
-----------------------------------------------------------------------

**The guards are properties of the wire, not of a function.** An origin
header, a bearer token and a status code exist only on the wire, so every
guard test drives the service over HTTP. A test that called the guard
function directly would be testing the function, not the service.

**A test that only exercises the happy path observes nothing.** Every guard
is therefore asserted twice: once showing that the guarded request is
refused, and once showing that the *same* request is served when the thing
that triggered the refusal is removed. Without the second half, a guard that
refused everything would pass every test in the file.

**A parameter that is accepted and ignored is a parameter that lies.** The
origin allow-list, the bind address and the port are each exercised with a
value that is *not* the default, and each test shows that the value changed
what happened.

**The typed contract is checked, not asserted.** The checked-in TypeScript is
compared with the document the Python models produce now, so a model that
changes without the TypeScript being regenerated is a failing test.

**This package does not reach the store.** The application layer is the only
way to the store — ``tests/test_application_layer.py`` says so — and this
file asserts it for the API package too, so a future route that reached past
the layer would fail here as well as there.
"""

from __future__ import annotations

import ast
import hashlib
import hmac
import json
import logging
import os
import secrets
from collections.abc import Iterator, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, Engine, select, text
from sqlalchemy import event as sa_event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from test_store_support import StoreEnv, make_receipt
from test_store_support import env as _shared_env

from labcairn.api import (
    BindRefusedError,
    GuardRefusal,
    contract_app,
    create_app,
    ensure_loopback,
)
from labcairn.api import session as session_module
from labcairn.api.app import refusal_response
from labcairn.api.events import UnwiredEventSource
from labcairn.api.session import SessionToken, read_bearer
from labcairn.api.typescript import render_types
from labcairn.application import (
    ApplicationContext,
    ApplicationRefusedError,
    create_task,
    ingest_material,
    read_task_state,
)
from labcairn.application.refusal import ApplicationRefusal
from labcairn.core.ids import TaskId, new_id
from labcairn.db import create_db_engine
from labcairn.db.models import TaskRow
from labcairn.db.repository import events_after
from labcairn.reports.receipt import ArtifactKind, ArtifactProducerKind, ArtifactReceipt
from labcairn.runtime.event import EventStreamPage, EventStreamRequest, EventType
from labcairn.runtime.lifecycle import TaskGoal
from labcairn.security.approval import ApprovalLedger
from labcairn.security.policy import Permission, PermissionPolicy, Rule

pytestmark = pytest.mark.integration

# pytest resolves a fixture by the parameter name in a test's signature, so the
# shared `env` fixture must be bound under that name here.
env = _shared_env

#: The origin the service answers to by default.
OWN_ORIGIN = "http://127.0.0.1:8000"

#: An origin that is not the service's own. A page on another site sends
#: exactly this.
FOREIGN_ORIGIN = "https://evil.example"

#: A moment far enough ahead that an approval asked for now has not lapsed.
_FUTURE = datetime(2027, 1, 1, tzinfo=UTC)


# --------------------------------------------------------------------------- #
# the environment
# --------------------------------------------------------------------------- #


def _allow_all() -> PermissionPolicy:
    """A policy that allows everything, so a test can vary one thing at a time."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.ALLOW, pattern="**")])


def _deny_all() -> PermissionPolicy:
    """A policy that denies everything."""
    return PermissionPolicy.from_rules([Rule(effect=Permission.DENY, pattern="**")])


@pytest.fixture
def workspace_root(tmp_path: Path) -> Path:
    """A workspace with a source directory in it."""
    root = tmp_path / "workspace"
    (root / "materials").mkdir(parents=True)
    return root


def _make_context(
    env: StoreEnv,
    workspace_root: Path,
    policy: PermissionPolicy | None = None,
) -> ApplicationContext:
    """A context for a task that exists, under the policy the test wants."""
    store = env.store()
    created = create_task(
        store=store,
        policy=_allow_all(),
        workspace_root=workspace_root,
        title="API test task",
        goal=TaskGoal(
            objective="Establish whether the observation holds.",
            success_criterion="A cited answer, or an honest 'not established'.",
        ),
        source_dirs=(workspace_root / "materials",),
    )
    return ApplicationContext(
        workspace=created.workspace,
        store=store,
        policy=policy if policy is not None else _allow_all(),
        ledger=ApprovalLedger(),
    )


@pytest.fixture
def context(env: StoreEnv, workspace_root: Path) -> ApplicationContext:
    """A context for a task that exists."""
    return _make_context(env, workspace_root)


@pytest.fixture
def client(context: ApplicationContext) -> Iterator[TestClient]:
    """A client for the service, with the event stream wired to the store."""
    app = create_app(context, event_source=_StoreEventSource())
    with TestClient(app) as wired:
        yield wired


@pytest.fixture
def token(client: TestClient) -> str:
    """The service's session token, read the way a client reads it."""
    response = client.get("/session")
    assert response.status_code == 200
    return str(response.json()["token"])


def _authorization(value: str) -> dict[str, str]:
    """The header a client presents the token in."""
    return {"Authorization": f"Bearer {value}"}


def _approval_body() -> dict[str, Any]:
    """A request for consent, as the API accepts it.

    The resource is a key *inside* the task's output area: a key that names
    the root it sits in is refused, because a directory that is a root reduces
    to the root.
    """
    return {
        "capability": "fs.read",
        "arguments": {},
        "root_id": "output",
        "resource_key": "report.md",
        "expires_at": _FUTURE.isoformat(),
    }


class _StoreEventSource:
    """The event source the service's host would give it.

    It reads the store's event log, which is what the port is for. It lives
    in this file because the API package may not reach the store: the
    application layer is the only way to the store, and the layer's frozen
    operation list has no event read for the port to sit on yet.

    **It holds no session.** The caller hands it the session to read on, so
    two requests that read the stream never share one.
    """

    def page(self, session: Session, request: EventStreamRequest) -> EventStreamPage:
        """The events after the request's cursor, and the cursor to resume from."""
        events = events_after(
            session, request.task_id, after_seq=request.after_seq, limit=request.limit
        )
        return EventStreamPage(
            task_id=request.task_id,
            events=events,
            next_after_seq=events[-1].seq if events else request.after_seq,
            caught_up=len(events) < request.limit,
        )


# --------------------------------------------------------------------------- #
# guard one: the bind address
# --------------------------------------------------------------------------- #


def test_the_service_refuses_to_start_on_a_non_loopback_address(
    context: ApplicationContext,
) -> None:
    """A service that listens on a routable address is a service on the network.

    Each address here is refused, and the refusal is a refusal to *start*:
    there is no service to warn with, because there is no service.
    """
    for host in ("0.0.0.0", "192.168.1.10", "::", "10.0.0.1", "example.test", "localhost", ""):
        with pytest.raises(BindRefusedError):
            create_app(context, host=host)


def test_the_service_binds_the_loopback_addresses(context: ApplicationContext) -> None:
    """The addresses it will bind, and they are the platform's idea of loopback.

    ``::1`` is not the default, so this shows the address is read rather than
    hardcoded: a service that ignored the argument and always bound
    ``127.0.0.1`` would fail the second half of this.
    """
    for host in ("127.0.0.1", "::1"):
        app = create_app(context, host=host)
        assert app.state.host == host
        assert app.state.origins.allowed == frozenset({f"http://{host}:8000"})


def test_the_bind_check_is_not_hardcoded_to_one_address() -> None:
    """The check asks the platform, so a non-loopback address is refused.

    Asserted against the function rather than through the factory, because
    the factory's refusal is already covered; what is being pinned here is
    that the verdict comes from the address and not from a list in this
    repository.
    """
    assert ensure_loopback("127.0.0.1") == "127.0.0.1"
    assert ensure_loopback("::1") == "::1"
    for host in ("0.0.0.0", "8.8.8.8", "fe80::1"):
        with pytest.raises(BindRefusedError):
            ensure_loopback(host)


def test_the_port_is_part_of_the_service_s_own_origin(context: ApplicationContext) -> None:
    """A different port is a different origin, and the guard knows it.

    The port used here is not the default, so the test shows the port is
    read rather than assumed: a service that compared only the host would
    accept the second request below, and this test would fail.
    """
    app = create_app(context, port=8765)
    with TestClient(app) as wired:
        assert wired.get("/task", headers={"Origin": "http://127.0.0.1:8765"}).status_code == 200
        assert wired.get("/task", headers={"Origin": OWN_ORIGIN}).status_code == 403


# --------------------------------------------------------------------------- #
# guard two: the origin
# --------------------------------------------------------------------------- #


def test_a_foreign_origin_is_refused_with_and_without_a_token(
    client: TestClient, token: str
) -> None:
    """The real defence, in both of the forms it can be attempted in.

    The token makes no difference: a token is not a pass to a page on
    another site. The third assertion is the one that gives the first two
    their meaning — the same request without the foreign origin is served, so
    what refused it was the origin and not something incidental.
    """
    for headers in (
        {"Origin": FOREIGN_ORIGIN},
        {"Origin": FOREIGN_ORIGIN, **_authorization(token)},
    ):
        response = client.get("/task", headers=headers)
        assert response.status_code == 403
        assert response.json()["reason"] == GuardRefusal.ORIGIN_REFUSED.value
    assert client.get("/task").status_code == 200


def test_the_origin_check_covers_every_route(client: TestClient) -> None:
    """Every request is checked, whatever it asks for.

    A guard on the mutating routes only would leave the reads open, and a
    read is a read of the user's research: the task, the material, the
    artefacts and the event log are all the user's work.
    """
    for path in (
        "/health",
        "/session",
        "/task",
        "/tasks",
        "/plan",
        "/steps",
        "/sources",
        "/artifacts",
        "/events",
    ):
        response = client.get(path, headers={"Origin": FOREIGN_ORIGIN})
        assert response.status_code == 403, f"{path} was served to a foreign origin"
        assert response.json()["reason"] == GuardRefusal.ORIGIN_REFUSED.value


def test_a_mutation_from_a_foreign_origin_is_refused_before_the_session_is_read(
    client: TestClient,
) -> None:
    """The origin is checked first, and the token does not get past it.

    The order matters: a service that read the session first and the origin
    second would leak the difference between "no token" and "wrong origin"
    to a page on another site, and would be one refactor away from serving
    the wrong one.
    """
    response = client.post("/approvals", json=_approval_body(), headers={"Origin": FOREIGN_ORIGIN})
    assert response.status_code == 403
    assert response.json()["reason"] == GuardRefusal.ORIGIN_REFUSED.value


def test_an_added_origin_changes_what_is_refused(context: ApplicationContext) -> None:
    """The allow-list is honoured, and it is empty unless somebody fills it.

    Two services, one with the development origin named and one without, and
    the same request to both. A setting that was accepted and ignored would
    refuse the request in both, and this test would fail.
    """
    development = "http://localhost:5173"
    without = create_app(context)
    with TestClient(without) as plain:
        assert plain.get("/task", headers={"Origin": development}).status_code == 403
    with_extra = create_app(context, extra_origins=[development])
    with TestClient(with_extra) as wired:
        assert wired.get("/task", headers={"Origin": development}).status_code == 200
        assert wired.get("/task", headers={"Origin": FOREIGN_ORIGIN}).status_code == 403


# --------------------------------------------------------------------------- #
# guard three: the session
# --------------------------------------------------------------------------- #


def test_a_mutation_from_the_right_origin_without_the_token_is_refused(
    client: TestClient,
) -> None:
    """The right origin is not consent to act.

    The last assertion is the one that gives the first its meaning: a read
    from the same client with no token is served, so what refused the
    mutation was the missing session and not the origin.
    """
    response = client.post("/approvals", json=_approval_body(), headers={"Origin": OWN_ORIGIN})
    assert response.status_code == 401
    assert response.json()["reason"] == GuardRefusal.SESSION_REQUIRED.value
    assert client.get("/task", headers={"Origin": OWN_ORIGIN}).status_code == 200


def test_a_mutation_with_the_token_is_applied(client: TestClient, token: str) -> None:
    """The token does not merely unlock the route: the work happens.

    The approval is fetched back afterwards, because a 201 that recorded
    nothing would satisfy a test that only looked at the status code.
    """
    response = client.post(
        "/approvals",
        json=_approval_body(),
        headers={"Origin": OWN_ORIGIN, **_authorization(token)},
    )
    assert response.status_code == 201
    state = client.get("/task").json()
    assert len(state["approvals"]) == 1
    assert state["approvals"][0]["state"] == "pending"


def test_a_mutation_with_the_wrong_token_is_refused(client: TestClient, token: str) -> None:
    """The token's *identity* is checked, and not only its presence.

    The origin guard trusts a header that only a browser sets honestly, and
    **a local process is not a browser**: it can send the service's own
    origin freely. So the token is the only barrier between a local process
    and the store's mutations, and what makes it a barrier is that it is
    *this service's* token. A check that only asked whether a token was
    present would let any local process through, and the acceptance clause
    — *"a local authenticated session/token even if launched on loopback"* --
    would be prose.

    The right token is sent afterwards, because a guard that refused every
    mutation would pass this test too.
    """
    refused = client.post(
        "/approvals",
        json=_approval_body(),
        headers={"Origin": OWN_ORIGIN, "Authorization": "Bearer not-this-service's-token"},
    )
    assert refused.status_code == 401
    assert refused.json()["reason"] == GuardRefusal.SESSION_REQUIRED.value

    accepted = client.post(
        "/approvals",
        json=_approval_body(),
        headers={"Origin": OWN_ORIGIN, **_authorization(token)},
    )
    assert accepted.status_code == 201


def test_the_token_is_read_only_from_the_authorization_header(
    client: TestClient, token: str
) -> None:
    """One header, and one place to look for the token.

    :meth:`SessionGuard.read` says it is *"the only reading of the
    ``Authorization`` header in the service, so there is one place to look
    when asking where a token could come from"*. That is a claim about
    **which headers are read**, and it is watched here rather than asserted:
    a token offered under any other name is not a token at all.

    The scheme is the other half of the same claim: a scheme the service
    does not use is a token the service did not issue.

    The request is made over the wire as well as read directly, because the
    claim is about the service and not about a function.
    """
    from labcairn.api.guards import SessionGuard

    assert SessionGuard.read({"authorization": f"Bearer {token}"}) == token
    for name in ("token", "x-token", "x-auth-token", "session-token", "x-api-key", "cookie"):
        assert SessionGuard.read({name: f"Bearer {token}"}) is None, (
            f"the token was read from the {name!r} header"
        )

    assert read_bearer("Bearer abc") == "abc"
    assert read_bearer("bearer abc") == "abc"
    assert read_bearer("Basic abc") is None
    assert read_bearer("Bearer   ") is None
    assert read_bearer(None) is None

    offered_elsewhere = client.post(
        "/approvals",
        json=_approval_body(),
        headers={"Origin": OWN_ORIGIN, "X-Token": token},
    )
    assert offered_elsewhere.status_code == 401
    assert offered_elsewhere.json()["reason"] == GuardRefusal.SESSION_REQUIRED.value


def test_a_read_needs_no_token(client: TestClient) -> None:
    """A read is served without a session.

    Stated rather than assumed, because it is the other half of the rule:
    the token is required on the requests that change something, and only on
    those.
    """
    assert client.get("/task").status_code == 200
    assert client.get("/task", headers={"Origin": OWN_ORIGIN}).status_code == 200


def test_the_token_is_never_accepted_from_a_url(client: TestClient, token: str) -> None:
    """A URL is pasted; a header is not.

    The token in the query string is the real token, presented correctly and
    in the wrong place, and it is refused. A service that read it from
    anywhere but the header would serve this request, and this test would
    fail.
    """
    response = client.post(
        f"/approvals?token={token}",
        json=_approval_body(),
        headers={"Origin": OWN_ORIGIN},
    )
    assert response.status_code == 401
    assert response.json()["reason"] == GuardRefusal.SESSION_REQUIRED.value


def test_the_token_is_written_to_a_file_the_client_can_point_at(
    context: ApplicationContext,
) -> None:
    """The token is in a file, and the file holds the token that is in use.

    The file is the service's own, under the workspace the user selected, and
    it is not in the task's output area: an artefact is something a report
    may cite, and a secret is not a finding.
    """
    app = create_app(context)
    written = Path(app.state.session.path)
    assert written.is_file()
    assert written.read_text(encoding="utf-8") == app.state.session.value
    assert written.parent.name == ".labcairn"
    assert "output" not in written.relative_to(context.workspace.selected_root).parts


def test_each_service_gets_its_own_token(context: ApplicationContext) -> None:
    """A new service is a new session.

    Two services over one context, and the tokens differ: a token that were
    the same would make the session worthless.
    """
    first = create_app(context)
    second = create_app(context)
    assert first.state.session.value != second.state.session.value


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_the_session_directory_can_still_be_entered(context: ApplicationContext) -> None:
    """The session directory carries a *directory's* mode, not a file's.

    On POSIX a directory is traversed with the **execute** bit, and a
    directory without one cannot be entered — not even by its owner. The
    session directory was given the token file's ``0o600``, which has no
    execute bit, so the **first** token could be written into it and the
    **second** raised ``PermissionError``: the directory could no longer be
    entered. Windows does not see it — there ``chmod`` only toggles the
    read-only attribute and every directory stays traversable — so this is
    asserted where the bits exist.

    The narrowest mode a directory can carry and still be usable is ``0o700``:
    the owner may enter it, and nobody else may.
    """
    app = create_app(context)
    directory = Path(app.state.session.path).parent

    assert directory.stat().st_mode & 0o700 == 0o700
    # The behaviour, not just the bits: a directory that cannot be entered
    # cannot hold a second token either.
    (directory / "probe").write_text("written", encoding="utf-8")


# --------------------------------------------------------------------------- #
# the browser's fetch metadata
# --------------------------------------------------------------------------- #


#: A request that another site's page made, as a subresource load. It carries
#: no ``Origin``, which is what the origin check permits by omission.
_CROSS_SITE_SUBRESOURCE = {"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "no-cors"}

#: The same request, made by a link the user clicked.
_CROSS_SITE_NAVIGATION = {"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "navigate"}


def test_a_cross_site_subresource_with_no_origin_is_refused(client: TestClient) -> None:
    """The subresource load is the request the origin check waves through.

    A page on another site embeds this service with an ``<img>``, a
    ``<script>`` or an ``<embed>``, and the browser puts no ``Origin`` on
    any of them — so there is nothing for the origin check to judge. The
    browser's own metadata says where it came from, and the rule refuses it.

    Checked on the token endpoint as well as on a read: the subresource load
    of ``/session`` is the one that would hand a page the token.
    """
    for path in ("/session", "/task"):
        response = client.get(path, headers=_CROSS_SITE_SUBRESOURCE)
        assert response.status_code == 403, f"{path} was served to a cross-site subresource"
        assert response.json()["reason"] == "cross_site_refused"


def test_a_cross_site_navigation_is_served(tmp_path: Path, context: ApplicationContext) -> None:
    """A link the user clicked still opens the workbench.

    A navigation is a thing the *user* did; a subresource load is something a
    page did to the user. The rule permits the first, and this is what
    ``Sec-Fetch-Mode: navigate`` buys — the workbench page and the API's own
    reads are both served.
    """
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>workbench</title>", encoding="utf-8")
    with TestClient(create_app(context, static_dir=dist)) as wired:
        for path in ("/", "/task", "/health"):
            response = wired.get(path, headers=_CROSS_SITE_NAVIGATION)
            assert response.status_code == 200, f"{path} refused a navigation the user made"


def test_an_allow_listed_origin_is_judged_by_the_origin_check_alone(
    context: ApplicationContext,
) -> None:
    """The development web server keeps working, cross-site metadata and all.

    ``http://localhost:5173`` is **cross-site** to ``http://127.0.0.1:8000`` —
    an address is its own site — so the request carries ``cross-site`` even
    though the origin is the one the operator allow-listed. The rule does not
    touch a request that carries an origin, and this is what says so: the
    fetch metadata is sent, and the request is still served.
    """
    development = "http://localhost:5173"
    with TestClient(create_app(context, extra_origins=[development])) as wired:
        response = wired.get(
            "/task",
            headers={"Origin": development, **_CROSS_SITE_SUBRESOURCE},
        )
        assert response.status_code == 200


def test_a_request_with_no_fetch_metadata_is_judged_by_the_origin_check_alone(
    client: TestClient,
) -> None:
    """A client that says nothing about where it is is judged by the origin.

    That is every client that is not a browser, and it is also the request
    the rule must not touch. The second assertion is the one that gives the
    first its meaning: the origin check is still in force, and a foreign
    origin is still refused.
    """
    assert client.get("/task").status_code == 200
    assert client.get("/task", headers={"Origin": FOREIGN_ORIGIN}).status_code == 403
    assert client.get("/task", headers={"Sec-Fetch-Site": "same-origin"}).status_code == 200
    assert client.get("/task", headers={"Sec-Fetch-Site": "none"}).status_code == 200


# --------------------------------------------------------------------------- #
# what the artefact route serves
# --------------------------------------------------------------------------- #


def _media_type(headers: Mapping[str, str]) -> str:
    """The media type in a response's headers, without the parameters.

    ``text/markdown; charset=utf-8`` is the same media type as
    ``text/markdown``, and a test that compared the whole header would be
    asserting the charset as well.
    """
    return headers["content-type"].split(";")[0].strip().lower()


def _put_artifact(
    context: ApplicationContext, *, name: str, body: bytes, media_type: str | None
) -> str:
    """An artefact in the store, with its bytes on disk and its receipt.

    The receipt is written the way the store holds one, and the file is put
    where the receipt says it is, so the layer's own read finds both.
    """
    relative = f"output/{context.task_id}/{name}"
    path = context.workspace.selected_root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    receipt = ArtifactReceipt(
        receipt_id=f"artifact-{new_id()}",
        task_id=str(context.task_id),
        kind=ArtifactKind.REPORT,
        relative_path=relative,
        content_sha256=hashlib.sha256(body).hexdigest(),
        size_bytes=len(body),
        produced_by=ArtifactProducerKind.STAGE,
        producer_id="draft",
        media_type=media_type,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    with context.store.unit(context.task_id) as work:
        work.put_artifact(receipt, run_id=None)
    return receipt.receipt_id


def test_the_artefact_route_serves_a_sandboxed_response(
    context: ApplicationContext, client: TestClient
) -> None:
    """An artefact is a document, and a document must not run in our origin.

    ``Content-Security-Policy: sandbox`` puts the document in an opaque
    origin: it cannot read this service's origin, cannot script it, and
    cannot reach the token. Without it, a page on another site could frame
    an HTML or SVG artefact, and the framed document — running in *our*
    origin, where every guard passes — could fetch ``/session`` and hand
    the token back.

    The bytes are unchanged, so the report's own HTML form renders as it
    did; a frame cannot be rendered in this suite, so the checkable form of
    the property is the header.
    """
    body = b"<html><body>report</body></html>"
    receipt_id = _put_artifact(context, name="sandboxed.html", body=body, media_type="text/html")
    response = client.get(f"/artifacts/{receipt_id}/content")
    assert response.status_code == 200
    assert response.headers["content-security-policy"] == "sandbox"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.content == body


def test_the_artefact_content_type_is_the_receipt_s_own(
    context: ApplicationContext, client: TestClient
) -> None:
    """The content type is declared, not guessed from the file's name.

    A route that guessed would call an artefact called ``.html`` a document,
    and a document loaded in a frame runs in this service's origin. The
    names here end in ``.html`` and the receipts say otherwise, and the
    receipt is what the response carries — the receipt's own contract says
    the media type is "not inferred from the extension".

    The second case is the one that matters for a receipt that declares
    nothing: the fallback is an opaque type, not a guess.
    """
    declared = _put_artifact(
        context, name="declared.html", body=b"# Report\n", media_type="text/markdown"
    )
    response = client.get(f"/artifacts/{declared}/content")
    assert _media_type(response.headers) == "text/markdown"

    undeclared = _put_artifact(context, name="undeclared.html", body=b"# Report\n", media_type=None)
    fallback = client.get(f"/artifacts/{undeclared}/content")
    assert _media_type(fallback.headers) == "application/octet-stream"


def test_the_session_response_is_not_sniffable(client: TestClient) -> None:
    """The browser must not decide that the token is something else.

    The session response is ``application/json`` already, and
    ``nosniff`` says the browser must not decide otherwise — which is the
    difference between a media type that is right and a media type that is
    merely declared.
    """
    response = client.get("/session")
    assert response.headers["x-content-type-options"] == "nosniff"


# --------------------------------------------------------------------------- #
# the two absences the session endpoint depends on
# --------------------------------------------------------------------------- #


#: The media types a browser will run as a classic script. The list is the
#: HTML standard's JavaScript MIME types, and it is spelled out here rather
#: than imported because the point of the test is what the browser does with
#: a type, not what a library calls one.
_JAVASCRIPT_MEDIA_TYPES = frozenset(
    {
        "application/ecmascript",
        "application/javascript",
        "application/x-ecmascript",
        "application/x-javascript",
        "text/ecmascript",
        "text/javascript",
        "text/javascript1.0",
        "text/javascript1.1",
        "text/javascript1.2",
        "text/javascript1.3",
        "text/javascript1.4",
        "text/javascript1.5",
        "text/jscript",
        "text/livescript",
        "text/x-ecmascript",
        "text/x-javascript",
    }
)


def test_no_response_carries_an_access_control_allow_origin(client: TestClient) -> None:
    """The browser's cross-origin read rule is what stands between a page and the token.

    A response with no ``Access-Control-Allow-Origin`` is one a browser will
    not let another origin's script read, and that absence is the *whole*
    defence of the session endpoint against a page on another site. The
    origin guard refuses a request that **carries** a foreign origin, which
    stops a page that would ask; this stops a page that loads the response
    as a subresource and reads what it can.

    An absence is not a property until something watches it. One line of
    ``app.add_middleware(CORSMiddleware, allow_origins=["*"])`` — which is
    exactly what somebody would add to make the development server work —
    would let every page on the internet read this service's session token,
    and nothing else in this suite would notice.

    The token endpoint, a read and a refusal are all checked, because the
    property is about the service and not about one route.

    The requests carry an ``Origin``, and that is load-bearing rather than
    incidental: a CORS middleware only answers a request that has an origin
    to answer about, so a check made without one would see no header
    whether the middleware was installed or not. The service's own origin is
    used for the two that are served, because that is the request a
    permissive middleware would answer with ``Access-Control-Allow-Origin:
    *``.
    """
    for response in (
        client.get("/session", headers={"Origin": OWN_ORIGIN}),
        client.get("/task", headers={"Origin": OWN_ORIGIN}),
        client.get("/task", headers={"Origin": FOREIGN_ORIGIN}),
    ):
        assert "access-control-allow-origin" not in response.headers
        assert "access-control-allow-credentials" not in response.headers


def test_the_session_response_is_not_a_javascript_type(client: TestClient) -> None:
    """A classic script load is not a CORS-restricted fetch, so the MIME type is what stops it.

    ``<script src=".../session">`` is not a CORS request: the browser
    fetches it and, if the media type is a JavaScript type, runs it in the
    page that asked for it. The session response is ``application/json``,
    which the browser refuses to execute, and that refusal is the second of
    the two things the session endpoint's safety rests on.

    The check is on the *type*, not on the one value it happens to have
    today, so a change of content type to something a browser would run is
    caught whatever it is called.

    The artefact content route is deliberately not in this list: it serves
    the artefact's own media type, because the bytes are the artefact's. An
    artefact is a document, not a script, and the type it declares is the
    caller's business.
    """
    response = client.get("/session")
    media_type = response.headers["content-type"].split(";")[0].strip().lower()
    assert media_type not in _JAVASCRIPT_MEDIA_TYPES
    assert media_type == "application/json"


# --------------------------------------------------------------------------- #
# the token does not leak
# --------------------------------------------------------------------------- #


def _service_log(caplog: pytest.LogCaptureFixture) -> str:
    """What the *service* logged.

    Scoped to the service's own logger on purpose. The test client is an
    HTTP client and it logs the URL it was given, query string and all —
    which is a fact about the client, and one of the reasons a token is never
    put in a URL. The rule this repository states is about the service's
    events, traces and exports, so the service's log is what is asserted.
    """
    return "\n".join(
        f"{record.getMessage()} {record.__dict__}"
        for record in caplog.records
        if record.name == "labcairn.api"
    )


def test_the_token_appears_in_no_response_but_the_session_endpoint(
    client: TestClient, token: str, caplog: pytest.LogCaptureFixture
) -> None:
    """The architecture's rule: no credential in a response, an event or a log.

    The session endpoint is the one place the token is meant to be, and it is
    excluded deliberately rather than forgotten. Everywhere else — the task
    state, the artefacts, the event log, the log records — it must not be.
    """
    caplog.set_level(logging.DEBUG)
    bodies = [
        client.get("/task").text,
        client.get("/tasks").text,
        client.get("/plan").text,
        client.get("/steps").text,
        client.get("/sources").text,
        client.get("/artifacts").text,
        client.get("/events").text,
        client.get("/health").text,
        client.post(
            "/approvals",
            json=_approval_body(),
            headers={"Origin": OWN_ORIGIN, **_authorization(token)},
        ).text,
        # A token in the query string, refused — and the refusal must not
        # quote it back.
        client.post(f"/approvals?token={token}", json=_approval_body()).text,
    ]
    for body in bodies:
        assert token not in body
    assert token not in _service_log(caplog)


def test_the_log_records_the_path_and_not_the_query_string(
    client: TestClient, token: str, caplog: pytest.LogCaptureFixture
) -> None:
    """A log that recorded the query string would record a pasted token.

    The request is refused, and the refusal is logged; what the log holds is
    the path and the reason, and the query string is not among them.
    """
    caplog.set_level(logging.DEBUG)
    client.post(f"/approvals?token={token}", json=_approval_body())
    paths = [
        record.path
        for record in caplog.records
        if record.name == "labcairn.api" and hasattr(record, "path")
    ]
    assert paths == ["/approvals"]
    assert token not in _service_log(caplog)


# --------------------------------------------------------------------------- #
# a refusal is a response
# --------------------------------------------------------------------------- #


def test_a_layer_refusal_is_a_response_and_not_a_crash(env: StoreEnv, workspace_root: Path) -> None:
    """The layer's refusal becomes a status code and the layer's own payload.

    The body is compared with the refusal the layer raises when it is called
    directly, so the test pins the *bytes* rather than the shape.
    """
    context = _make_context(env, workspace_root, policy=_deny_all())
    with TestClient(create_app(context)) as wired:
        response = wired.get("/task")
    assert response.status_code == 403
    with pytest.raises(ApplicationRefusedError) as caught:
        read_task_state(context)
    assert response.json() == caught.value.to_payload()
    assert response.json()["reason"] == "permission_denied"


def test_every_refusal_carries_the_same_two_fields(env: StoreEnv, workspace_root: Path) -> None:
    """One shape for every refusal, whatever produced it.

    A layer refusal and a guard refusal are the same two fields, so a script
    branches on one field either way and never has to ask which kind it got.
    """
    context = _make_context(env, workspace_root, policy=_deny_all())
    with TestClient(create_app(context)) as wired:
        layer = wired.get("/task")
        guard = wired.get("/task", headers={"Origin": FOREIGN_ORIGIN})
    assert set(layer.json()) == {"reason", "message"}
    assert set(guard.json()) == {"reason", "message"}
    assert layer.json()["reason"] != guard.json()["reason"]


def test_a_refusal_response_is_built_from_the_refusal_s_own_payload() -> None:
    """The response body is the refusal's payload, not a hand-built dictionary."""
    error = ApplicationRefusedError(ApplicationRefusal.TASK_NOT_FOUND, "no such task")
    response = refusal_response(error, 403)
    assert response.status_code == 403
    assert json.loads(bytes(response.body)) == error.to_payload()


# --------------------------------------------------------------------------- #
# the event stream
# --------------------------------------------------------------------------- #


def test_the_stream_carries_events_and_never_a_command(client: TestClient) -> None:
    """The stream is facts about what happened, and nothing else.

    Every event is one of the runtime's closed vocabulary of event types,
    and the page has no field that could carry an instruction. That is what
    makes a reconnecting browser safe: it can ask for what it missed and
    cannot ask for anything to be done.
    """
    page = client.get("/events").json()
    assert page["events"], "the task was created, so the log is not empty"
    known = {member.value for member in EventType}
    for event in page["events"]:
        assert event["type"] in known
        assert set(event) <= {
            "schema_version",
            "event_id",
            "seq",
            "task_id",
            "run_id",
            "stage_id",
            "operation_id",
            "type",
            "transition",
            "payload",
            "occurred_at",
        }
    assert set(page) == {
        "schema_version",
        "task_id",
        "events",
        "next_after_seq",
        "caught_up",
    }


def test_the_service_serves_the_workbench_from_the_same_origin(
    tmp_path: Path, context: ApplicationContext
) -> None:
    """The API serves the built web app, so there is exactly one origin.

    This is the shape the origin guard assumes: the page the browser runs
    and the API it talks to are the same origin, so the check means what it
    says. The API's own routes are registered before the mount, so they win
    over the workbench's files.
    """
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>workbench</title>", encoding="utf-8")
    with TestClient(create_app(context, static_dir=dist)) as wired:
        served = wired.get("/")
        assert served.status_code == 200
        assert "workbench" in served.text
        assert wired.get("/task").status_code == 200
        assert wired.get("/task", headers={"Origin": FOREIGN_ORIGIN}).status_code == 403


def test_the_task_response_is_the_layer_s_own_value(
    client: TestClient, context: ApplicationContext, token: str
) -> None:
    """The API serves the layer's value, field for field.

    The response is compared with the value the layer returns when it is
    called directly, so a route that answered with a subset — an
    "API-shaped" view of the task — would fail here. §1.4.2's decision is
    that the CLI and the API serve the same bytes, and this is the test
    that says so: there is one model, and this body is it.

    The state is given something in *every* field first. A fresh task has
    no runs, no stages, no artefacts and no approvals, and comparing an
    empty state with an empty state observes nothing at all: a route that
    dropped a field would look identical.
    """
    with context.store.unit(context.task_id) as work:
        work.put_artifact(make_receipt(context.task_id), run_id=None)
    client.post(
        "/approvals",
        json=_approval_body(),
        headers={"Origin": OWN_ORIGIN, **_authorization(token)},
    )
    expected = read_task_state(context)
    assert expected.runs and expected.stages and expected.artifacts and expected.approvals
    # The layer's read left a transaction open on the test's own session, and
    # the store's engine opens every transaction with ``BEGIN IMMEDIATE``: that
    # session holds SQLite's write lock. The service reads on a session of its
    # own, so it would wait for the lock this one holds. The value is already
    # materialised, so the transaction can end here.
    context.store.session.rollback()
    response = client.get("/task")
    assert response.status_code == 200
    assert response.json() == json.loads(expected.model_dump_json())


def test_the_stream_resumes_from_its_cursor(client: TestClient, token: str) -> None:
    """A browser that reconnects asks for what it missed, and gets exactly that.

    The cursor is the runtime's own ``after_seq``, and the events after it
    are the ones with a higher sequence. The approval is asked for first, so
    that the log holds more than one event: without it there would be
    nothing after the first one to resume from, and the test would be
    asserting that an empty page is empty.
    """
    client.post(
        "/approvals",
        json=_approval_body(),
        headers={"Origin": OWN_ORIGIN, **_authorization(token)},
    )
    first = client.get("/events").json()
    assert len(first["events"]) > 1
    cursor = first["events"][0]["seq"]
    after = client.get(f"/events?after_seq={cursor}").json()
    assert after["events"]
    assert all(event["seq"] > cursor for event in after["events"])
    assert after["events"] == first["events"][1:]
    assert after["next_after_seq"] == after["events"][-1]["seq"]


def test_the_stream_endpoint_takes_no_request_body(client: TestClient) -> None:
    """The contract says the stream cannot be written to.

    Read from the OpenAPI document rather than from the code, because the
    document is what the web app is built against: a request body on the
    stream route would be a way to ask for something to happen.

    Every path under ``/events`` is checked, not the two the service serves
    today, because a route added tomorrow is exactly the case this is meant
    to catch. A fixed list of two paths would have passed while a third one
    sat in the contract taking a body.
    """
    document = contract_app().openapi()
    event_paths = [path for path in document["paths"] if path.startswith("/events")]
    assert event_paths, "the contract has no event path at all, which is also wrong"
    for path in event_paths:
        for method, operation in document["paths"][path].items():
            assert "requestBody" not in operation, f"{method.upper()} {path} takes a body"
            assert method in {"get", "head"}, f"{method.upper()} {path} is not a read"


def test_the_mutating_surface_of_the_service_is_exactly_the_routes_it_admits() -> None:
    """What this service can be *asked to do* is seven routes and no more.

        Every other route reads. That is the whole of the "the stream carries
        events and never commands" claim at the level of the contract: a browser
        that has the token can ask for consent, ask for a stage to run, and ask for
        the report to be rendered — and can do nothing else at all. A route that
        changed something else — a route that could delete an artefact, say — would
        be a permission the CLI does not have either.

        **The analysis run is on this list for the same reason the report is: LC-P1-12
    asks the local service to reach the layer's operations, and a figure the user
    cannot ask the service to draw is a figure with no surface at all. **It is not
    the consent's own route** — the approval is asked for over `POST /approvals` and
    answered over `/approvals/{approval_id}/grant`, and a run that could mint its own
    consent would not be a consented run.

    **The report render is on this list because G4's exit test is *"CLI and Web
        produce same versioned report"*.** That sentence asks the web to be able to
        *produce* the report, not only to read one the CLI happened to write; the
        route is the layer's own operation and the layer's own result model, so the
        bytes are the same bytes whichever surface asked.

    **The claim route is here because the web could not otherwise make a task
    reportable.** Recording a claim is what gives a report something to carry
    (§2.2), and a service that could render a report but not record what it is
    made of would be a surface that can only show work another surface did.
    """
    document = contract_app().openapi()
    mutating = {
        f"{method.upper()} {path}"
        for path, operations in document["paths"].items()
        for method in operations
        if method not in {"get", "head", "options"}
    }
    assert mutating == {
        "POST /approvals",
        "POST /approvals/{approval_id}/grant",
        "POST /approvals/{approval_id}/consume",
        "POST /stages",
        "POST /report",
        "POST /analysis",
        "POST /claims",
    }


def test_a_report_render_from_a_foreign_origin_is_refused(client: TestClient) -> None:
    """The route that writes an artefact is behind the same origin guard.

    **Why it is watched separately.** A CSRF-able route that produces a file is
    worth guarding more than one that only reads: the page on another site could
    make this workspace write a revision of a report nobody asked for.
    """
    response = client.post(
        "/report",
        json={"path": "report", "template_id": "default"},
        headers={"Origin": FOREIGN_ORIGIN},
    )
    assert response.status_code == 403
    assert response.json()["reason"] == GuardRefusal.ORIGIN_REFUSED.value


def test_a_report_render_without_the_token_is_refused(client: TestClient) -> None:
    """The right origin is not consent to write."""
    response = client.post(
        "/report", json={"path": "report", "template_id": "default"}, headers={"Origin": OWN_ORIGIN}
    )
    assert response.status_code == 401
    assert response.json()["reason"] == GuardRefusal.SESSION_REQUIRED.value


def test_a_report_render_with_the_token_reaches_the_layer_and_reports_its_reason(
    client: TestClient, token: str
) -> None:
    """The route is the layer's operation, and the answer is the layer's answer.

    **What this proves, and what it deliberately does not.** The task under test
    has no record and no figure, and the document builder refuses a report with
    nothing to carry — so what comes back is ``report_content_refused``, the
    layer's own reason, delivered through the service's own refusal shape. That
    is the plumbing proved end to end: HTTP request → typed body → the layer's
    ``render_report`` → its refusal → this response.

    **It is not a claim that a report was written.** None was, and nothing was:
    a refusal that left a file behind would be the worst failure this route could
    have. The assertion below is that the output area holds no report.

    **The success path is the claim route's**: the task under test is refused
    because it holds no record, and
    :func:`test_a_claim_recorded_through_the_service_makes_the_task_reportable`
    records one through this service and then renders the report. What this
    test proves is the other half — the refusal is the layer's, and nothing was
    written.
    """
    response = client.post(
        "/report",
        json={"path": "report", "template_id": "default"},
        headers={"Origin": OWN_ORIGIN, **_authorization(token)},
    )
    assert response.status_code == 403, response.text
    assert response.json()["reason"] == ApplicationRefusal.REPORT_CONTENT_REFUSED.value
    assert "Nothing was written" in response.json()["message"], (
        "the refusal must say the output area is untouched"
    )

    listed = client.get("/artifacts", headers={"Origin": OWN_ORIGIN})
    assert listed.status_code == 200
    assert listed.json() == [], "a refused report must leave no artefact behind"


def test_a_claim_recorded_through_the_service_makes_the_task_reportable(
    context: ApplicationContext,
    client: TestClient,
    token: str,
    workspace_root: Path,
) -> None:
    """The success path: ingest, read an address, record the claim, render.

    Every step except the ingestion is a request to this service, and the
    ingestion is the layer's (the service has no ingest route). The report that
    comes back is rendered from a record this service wrote, which is the
    property §2.2 exists for: a surface can make a task reportable without
    writing the ledger rows itself.
    """
    (workspace_root / "materials" / "one.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    ingestion = ingest_material(context)
    source_id = ingestion.source_ids[0]

    addresses = client.get(f"/sources/{source_id}/addresses", headers={"Origin": OWN_ORIGIN})
    assert addresses.status_code == 200, addresses.text
    address = next(item for item in addresses.json() if item["text"].strip() == "2")

    claimed = client.post(
        "/claims",
        json={
            "source_id": source_id,
            "locator_key": address["locator_key"],
            "kind": "numeric",
            "value": 2,
            "unit": "dimensionless",
        },
        headers={"Origin": OWN_ORIGIN, **_authorization(token)},
    )

    assert claimed.status_code == 201, claimed.text
    recorded = claimed.json()
    assert recorded["record"]["status"] == "extracted"
    assert recorded["record"]["value"] == 2.0
    assert recorded["anchor_id"]

    reported = client.post(
        "/report",
        json={"path": "report", "template_id": "default"},
        headers={"Origin": OWN_ORIGIN, **_authorization(token)},
    )
    assert reported.status_code == 200, reported.text
    assert reported.json()["resource_key"] == "report"

    listed = client.get("/artifacts", headers={"Origin": OWN_ORIGIN})
    assert listed.status_code == 200
    assert listed.json(), "the rendered report is not in the ledger"


def test_a_claim_from_a_foreign_origin_is_refused(client: TestClient) -> None:
    """The route that writes a record is behind the same origin guard."""
    response = client.post(
        "/claims",
        json={"source_id": "src-0123456789abcdef", "locator_key": "k=3:csv|r=1:1|c=1:a"},
        headers={"Origin": FOREIGN_ORIGIN},
    )
    assert response.status_code == 403
    assert response.json()["reason"] == GuardRefusal.ORIGIN_REFUSED.value


def test_a_claim_without_the_token_is_refused(client: TestClient) -> None:
    """The right origin is not consent to write a record."""
    response = client.post(
        "/claims",
        json={"source_id": "src-0123456789abcdef", "locator_key": "k=3:csv|r=1:1|c=1:a"},
        headers={"Origin": OWN_ORIGIN},
    )
    assert response.status_code == 401
    assert response.json()["reason"] == GuardRefusal.SESSION_REQUIRED.value


def test_a_report_render_names_the_template_it_was_asked_for(
    client: TestClient, token: str
) -> None:
    """One template exists, and a request for another is refused rather than guessed.

    **The refusal is the request's, not the content's**: an unknown template is a
    caller error, and serving the default instead would be the service deciding
    what the caller meant.
    """
    response = client.post(
        "/report",
        json={"path": "report", "template_id": "no-such-template"},
        headers={"Origin": OWN_ORIGIN, **_authorization(token)},
    )
    assert response.status_code == 403, response.text
    assert response.json()["reason"] != GuardRefusal.SESSION_REQUIRED.value
    assert "no-such-template" in response.json()["message"]


def test_the_stream_delivers_the_same_page_as_the_json_endpoint(client: TestClient) -> None:
    """One serialization, two deliveries.

    The server-sent frame carries the same page the JSON endpoint returns,
    serialised by the same model, so a client that reconnects reads the same
    cursor either way.
    """
    page = client.get("/events").json()
    with client.stream("GET", "/events/stream", params={"follow": "false"}) as response:
        body = "".join(response.iter_text())
    frames = [line for line in body.splitlines() if line.startswith("data: ")]
    assert len(frames) == 1
    assert json.loads(frames[0][len("data: ") :]) == page


def test_the_stream_is_refused_from_a_foreign_origin(client: TestClient) -> None:
    """The guard covers the stream as it covers everything else."""
    response = client.get("/events", headers={"Origin": FOREIGN_ORIGIN})
    assert response.status_code == 403
    assert response.json()["reason"] == GuardRefusal.ORIGIN_REFUSED.value


def test_an_unwired_stream_says_so_rather_than_looking_empty(
    context: ApplicationContext,
) -> None:
    """A stream that cannot see the events says it cannot see them.

    An empty page would say the task has no events, and the task has one:
    the ``task_created`` the store wrote. A service that quietly reported
    nothing would be lying about the state of the work.
    """
    with TestClient(create_app(context)) as wired:
        response = wired.get("/events")
    assert response.status_code == 403
    assert response.json()["reason"] == "not_implemented"


def test_the_unwired_source_refuses_rather_than_returning_an_empty_page() -> None:
    """The refusal is the source's own, and it is not an empty page."""
    source = UnwiredEventSource()
    request = EventStreamRequest(task_id=TaskId(new_id()), after_seq=0)
    with pytest.raises(ApplicationRefusedError) as caught:
        source.page(MagicMock(spec=Session), request)
    assert caught.value.reason.value == "not_implemented"


# --------------------------------------------------------------------------- #
# the typed contract
# --------------------------------------------------------------------------- #


def test_the_checked_in_typescript_is_what_the_python_models_produce(
    repo_root: Path,
) -> None:
    """Drift is a test failure, not a note.

    The file is generated from the OpenAPI document, which is generated from
    the application layer's models. A model that changes without the file
    being regenerated makes the two differ, and this fails.
    """
    generated = render_types(contract_app().openapi())
    path = repo_root / "web" / "src" / "api" / "generated.ts"
    raw = path.read_bytes()
    assert b"\r\n" not in raw, (
        "the generated file must have LF endings on every platform; the "
        "repository's .gitattributes says the checkout is LF, and a file that "
        "changed its endings between two machines would be a byte difference "
        "for no reason at all"
    )
    assert raw.decode("utf-8") == generated, (
        "the checked-in TypeScript is not what the Python models produce. "
        "Regenerate it with: uv run python -m labcairn.api.typescript "
        "web/src/api/generated.ts"
    )


def test_the_contract_names_the_layer_s_response_models() -> None:
    """The contract is the layer's models, not an API-shaped copy of them.

    Each name here is a class in :mod:`labcairn.application` or in the
    runtime, and the contract is what the web app is built against.
    """
    schemas = contract_app().openapi()["components"]["schemas"]
    for name in (
        "TaskState",
        "TaskPlan",
        "TaskStep",
        "SourceView",
        "ArtifactView",
        "ArtifactReceipt",
        "ApprovalRequested",
        "ApprovalGranted",
        "ApprovalConsumed",
        "StageRun",
        "EventStreamPage",
        "Event",
        "RefusalBody",
    ):
        assert name in schemas, f"{name} is not in the contract"


def test_the_running_service_and_the_contract_agree(context: ApplicationContext) -> None:
    """The contract is read from the same routes the service serves.

    If the two documents ever differ, the contract the web app is built
    against is not the contract the service honours.
    """
    assert create_app(context).openapi() == contract_app().openapi()


def test_the_generator_spells_the_shapes_it_is_given() -> None:
    """The generator is tested on the shapes it has to handle.

    A generator with a bug would produce a file that is stable and wrong,
    and a test that only compared the file with the generator would not
    notice.
    """
    document = {
        "components": {
            "schemas": {
                "Thing": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}, "count": {"type": "integer"}},
                    "required": ["name"],
                },
                "Colour": {"enum": ["red", "green"]},
                "Maybe": {
                    "anyOf": [
                        {"$ref": "#/components/schemas/Thing"},
                        {"type": "null"},
                    ]
                },
                "Things": {"type": "array", "items": {"$ref": "#/components/schemas/Thing"}},
                "Anything": {"type": "object", "additionalProperties": True},
            }
        }
    }
    rendered = render_types(document)
    assert "export type Thing = {" in rendered
    assert "  name: string" in rendered
    assert "  count?: number" in rendered
    assert "export type Colour = 'red' | 'green'" in rendered
    assert "export type Maybe = Thing | null" in rendered
    assert "export type Things = Thing[]" in rendered
    assert "export type Anything = Record<string, unknown>" in rendered


def test_the_generator_refuses_a_shape_it_does_not_know() -> None:
    """An unknown shape is a failure, not a silent ``any``.

    A generator that shrugged would turn a model change into a type that
    says nothing, and the drift test would still pass.
    """
    document = {"components": {"schemas": {"Odd": {"type": "quaternion"}}}}
    with pytest.raises(ValueError):
        render_types(document)


# --------------------------------------------------------------------------- #
# the seam
# --------------------------------------------------------------------------- #


def test_no_module_of_the_api_reaches_the_store(repo_root: Path) -> None:
    """The API package does not read the store.

    The application layer is the only way to the store, and
    ``tests/test_application_layer.py`` says so for the package as a whole.
    This says it for the API package in particular: a route that read the
    store itself would be a caller the capability model's guards do not
    reach.
    """
    package = repo_root / "src" / "labcairn" / "api"
    offenders: list[str] = []
    for path in sorted(package.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            imported: list[str] = []
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = [node.module]
            for name in imported:
                if name == "labcairn.db" or name.startswith("labcairn.db."):
                    offenders.append(f"{path.relative_to(repo_root)} imports {name}")
    assert not offenders, (
        "the API package reaches the store: " + "; ".join(offenders) + ". The "
        "application layer is the only way to the store."
    )


def test_the_api_package_calls_the_layer_and_nothing_else(
    repo_root: Path,
) -> None:
    """Every route's data comes from the application layer.

    Checked by name rather than by behaviour: the layer's operations are the
    ones the routes call, and a route that grew a second way to the task
    state would show up here.
    """
    from labcairn.api import routes

    layer = {
        "list_tasks",
        "read_task_state",
        "read_plan",
        "read_steps",
        "list_sources",
        "inspect_source",
        "list_artifacts",
        "read_artifact",
        "request_approval",
        "grant_approval",
        "consume_approval",
        "run_stage",
    }
    called = {name for name in dir(routes) if name in layer and callable(getattr(routes, name))}
    assert called == layer, f"the routes do not call every layer operation: {layer - called}"


# --------------------------------------------------------------------------- #
# the session token's own type
# --------------------------------------------------------------------------- #


def test_the_session_token_compares_in_constant_time_over_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The token is compared with the constant-time comparison, over bytes.

    **Watched at the call, and not by the clock.** A timing test would be
    flaky, and it would not be the property either: the property is *which*
    comparison is made. So the comparison is intercepted — every name it can
    be reached by is patched, because :func:`secrets.compare_digest` and
    :func:`hmac.compare_digest` are one function under two names — and what
    the module does with it is asserted.

    Three things, each of which can be broken on its own:

    * **the comparison is made at all.** A comparison made with ``==`` makes
      no call, and answers exactly the same way.
    * **it is made on every candidate.** A comparison that answered a
      candidate of a different length without comparing would leak the
      token's length through its running time, which is what the module's
      own docstring says it does not do.
    * **its answer is the answer.** A call made and then ignored, the
      comparison's result thrown away for one of the module's own, would
      compare in constant time and still not be the comparison.
    """
    original = secrets.compare_digest
    calls: list[tuple[Any, Any]] = []

    def recording(left: Any, right: Any) -> bool:
        calls.append((left, right))
        if isinstance(left, bytes) and isinstance(right, bytes):
            return original(left, right)
        return False

    def always_agrees(left: Any, right: Any) -> bool:
        return True

    for owner in (secrets, hmac, session_module):
        if hasattr(owner, "compare_digest"):
            monkeypatch.setattr(owner, "compare_digest", recording)

    token = SessionToken(value="abc", path=Path("token"))
    verified = (
        token.verify("abc"),
        token.verify("abd"),
        token.verify("ab"),
        token.verify("é"),
    )

    assert all(isinstance(argument, bytes) for call in calls for argument in call), (
        f"the comparison was made over {calls!r} and not over bytes: a candidate "
        "carrying non-ASCII characters would raise rather than be refused"
    )
    assert verified == (True, False, False, False), (
        f"the token verified as {verified!r} and not as (True, False, False, False)"
    )
    for candidate in (b"abc", b"abd", b"ab", "é".encode()):
        assert any({left, right} == {b"abc", candidate} for left, right in calls), (
            f"the token and {candidate!r} were not compared with each other: "
            f"{calls!r}. A comparison that answers without comparing leaks the "
            "length it answered on."
        )

    for owner in (secrets, hmac, session_module):
        if hasattr(owner, "compare_digest"):
            monkeypatch.setattr(owner, "compare_digest", always_agrees)
    assert token.verify("abd") is True, (
        "verify answered from a comparison of its own rather than from the "
        "constant-time one: the call is made and its answer thrown away"
    )


def test_the_session_module_makes_no_comparison_but_the_constant_time_one(
    repo_root: Path,
) -> None:
    """``SessionToken.verify`` compares the token, and nothing else.

    **The constant-time comparison is the only comparison the method
    makes.** A fast path that decided the answer before handing the two
    strings over — an equality test, a length test, a prefix test — would
    still call the constant-time comparison, and would still leak through
    its running time everything the constant-time comparison was there to
    hide. A test that watched only the call would see that call made and
    pass.

    Checked in the module's own source, because the claim is about the code
    as written: a test that ran the comparison would watch one run of it.
    """
    source = (repo_root / "src" / "labcairn" / "api" / "session.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    session_class = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "SessionToken"
    )
    verify = next(
        node
        for node in session_class.body
        if isinstance(node, ast.FunctionDef) and node.name == "verify"
    )

    comparisons = [node for node in ast.walk(verify) if isinstance(node, ast.Compare)]
    assert not comparisons, (
        "SessionToken.verify compares the token with something other than the "
        "constant-time comparison. A comparison that answers as soon as the two "
        "differ leaks the token through its running time, and the constant-time "
        "comparison is there to stop exactly that."
    )

    called = {ast.unparse(node.func) for node in ast.walk(verify) if isinstance(node, ast.Call)}
    modules = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    bound = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module in {"secrets", "hmac"}
        for alias in node.names
        if alias.name == "compare_digest"
    }
    acceptable = {f"{module}.compare_digest" for module in ("secrets", "hmac") if module in modules}
    acceptable |= bound
    assert called & acceptable, (
        f"SessionToken.verify calls {sorted(called)} and not the constant-time "
        "comparison: a comparison that is not constant-time leaks the token "
        "through its running time"
    )


def test_the_service_refuses_a_bind_address_before_it_mints_anything(
    context: ApplicationContext,
) -> None:
    """The bind check comes first, so a refused service leaves no token behind.

    A token file written by a service that then refused to start would be a
    secret lying on disk for a service nobody is running.
    """
    workspace = context.workspace.selected_root
    with pytest.raises(BindRefusedError):
        create_app(context, host="0.0.0.0")
    assert not (workspace / ".labcairn" / "session-token").exists()


# --------------------------------------------------------------------------- #
# the store between requests
# --------------------------------------------------------------------------- #


def _another_process(db_path: Path) -> Engine:
    """An engine of its own on the same database, as a second process has.

    Its own engine rather than a second session on the service's: a second
    *process* has its own engine, and the lock this is about is a lock on the
    file, not on the session.
    """
    return create_db_engine(db_path, busy_timeout_ms=250)


def _event_seqs(connection: Connection, task_id: TaskId) -> list[int]:
    """A Task's committed ``seq`` values, read through a plain connection."""
    rows: Sequence[Any] = (
        connection.execute(
            text("SELECT seq FROM events WHERE task_id = :t ORDER BY seq"),
            {"t": str(task_id)},
        )
        .scalars()
        .all()
    )
    return [int(value) for value in rows]


def _event_types(connection: Connection, task_id: TaskId) -> list[str]:
    """A Task's committed event types, read through a plain connection."""
    rows: Sequence[Any] = (
        connection.execute(
            text("SELECT type FROM events WHERE task_id = :t ORDER BY seq"),
            {"t": str(task_id)},
        )
        .scalars()
        .all()
    )
    return [str(value) for value in rows]


def test_the_service_lets_go_of_the_write_lock_between_requests(
    client: TestClient, env: StoreEnv
) -> None:
    """A second process may take the write lock while the service is idle.

    **The store opens every transaction with ``BEGIN IMMEDIATE``** — ADR-0003
    C3's clause, and the right one for a write, because two writers must not
    interleave. A read is a transaction too, so a read takes SQLite's *write*
    lock, and the session the service holds lives as long as the process
    does. If the service did not end the transaction at the end of a request
    it would hold that lock from its first read until its next commit, and
    the other surface of the same workspace — the CLI — would be refused
    with "database is locked".

    The probe opens the transaction through the engine rather than issuing
    ``BEGIN IMMEDIATE`` itself: the engine's ``begin`` event issues one
    already, and a second one lands inside it and is refused with "cannot
    start a transaction within a transaction" whether or not the service is
    holding anything.
    """
    served = client.get("/task", headers={"Origin": OWN_ORIGIN})
    assert served.status_code == 200, served.text

    other = _another_process(env.db_path)
    try:
        with other.connect() as connection, connection.begin():
            connection.exec_driver_sql("SELECT 1")
    except OperationalError as error:
        pytest.fail(f"the service holds the store's write lock: {error}")
    finally:
        other.dispose()


def test_a_write_through_the_service_is_committed_exactly_once(
    client: TestClient, env: StoreEnv, context: ApplicationContext, token: str
) -> None:
    """The service's write is committed, and it is committed once.

    **Nothing is lost.** The approval is in the store afterwards, and a
    second process reads it *there* — not from the service's memory of it.

    **Nothing is written twice.** The log holds exactly one more
    ``approval_requested`` event than it did, and the ledger holds exactly
    one approval. A write applied twice would leave two of each, and the log
    is append-only, so a second event is the only shape a duplicate can take.
    """
    other = _another_process(env.db_path)
    try:
        with other.connect() as before:
            types_before = _event_types(before, context.task_id)
            seqs_before = _event_seqs(before, context.task_id)
    finally:
        other.dispose()

    response = client.post(
        "/approvals",
        json=_approval_body(),
        headers={"Origin": OWN_ORIGIN, **_authorization(token)},
    )
    assert response.status_code == 201

    other = _another_process(env.db_path)
    try:
        with other.connect() as after:
            types_after = _event_types(after, context.task_id)
            seqs_after = _event_seqs(after, context.task_id)
            approvals: int = after.execute(
                text("SELECT COUNT(*) FROM approvals WHERE task_id = :t"),
                {"t": str(context.task_id)},
            ).scalar_one()
    finally:
        other.dispose()

    asked = EventType.APPROVAL_REQUESTED.value
    assert types_after.count(asked) == types_before.count(asked) + 1, (
        f"the request was recorded {types_after.count(asked) - types_before.count(asked)} "
        f"times: {types_after}"
    )
    assert int(approvals) == 1, "the approval was not committed exactly once"
    assert seqs_after[: len(seqs_before)] == seqs_before, "the log's earlier events changed"
    assert seqs_after == list(range(1, len(seqs_after) + 1)), "the sequence has a hole in it"


def test_the_next_request_reads_the_database_and_not_the_last_request_s_memory(
    client: TestClient, env: StoreEnv, context: ApplicationContext
) -> None:
    """A change another process made is visible to the next request.

    The service's session is long-lived, so the objects it loaded are
    long-lived too, and the session's identity map answers a query with the
    object it already holds rather than with the row. If those objects were
    not let go of at the end of a request, the next request would be answered
    from the last request's memory of the database — and the CLI's and the
    web's answers would disagree about a task the CLI had just changed.

    **The test holds the row itself, and that is the point of it.** A
    session's identity map holds its objects *weakly*, so an object nothing
    else refers to is collected and the map empties by itself: the property
    would then hold by the garbage collector's cooperation rather than by the
    code's doing. Holding the row keeps it in the map, and makes the
    property the code's to keep.
    """
    session = context.store.session
    held = session.execute(
        select(TaskRow).where(TaskRow.task_id == str(context.task_id))
    ).scalar_one()
    # The test's own transaction ends here, so that the other process below
    # can take the write lock. The row stays loaded: the session does not
    # expire what it holds when it commits.
    session.commit()
    assert held.title == "API test task"

    first = client.get("/task", headers={"Origin": OWN_ORIGIN}).json()
    assert first["task"]["title"] == "API test task"

    other = _another_process(env.db_path)
    try:
        with other.begin() as connection:
            connection.execute(
                text("UPDATE tasks SET title = :title WHERE task_id = :id"),
                {"title": "changed by another process", "id": str(context.task_id)},
            )
    finally:
        other.dispose()

    second = client.get("/task", headers={"Origin": OWN_ORIGIN}).json()
    assert second["task"]["title"] == "changed by another process"


def test_the_write_path_still_opens_its_transaction_with_begin_immediate(
    client: TestClient, env: StoreEnv, token: str
) -> None:
    """The write path's SQL is the one ADR-0003 C3 asks for.

    Letting go of the transaction between requests must not have changed how
    a write opens one: ``BEGIN IMMEDIATE``, the write lock taken up front,
    and never a deferred ``BEGIN`` that would take the lock at the first
    write and fail with ``SQLITE_BUSY`` instead of waiting for it.

    Every ``BEGIN`` the request issued is checked, not the first one: a
    transaction that began IMMEDIATE and a second that began deferred would
    both have issued *a* ``BEGIN``.
    """
    statements: list[str] = []

    def record(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        statements.append(" ".join(statement.split()))

    sa_event.listen(env.engine, "before_cursor_execute", record)
    try:
        response = client.post(
            "/approvals",
            json=_approval_body(),
            headers={"Origin": OWN_ORIGIN, **_authorization(token)},
        )
        assert response.status_code == 201
    finally:
        sa_event.remove(env.engine, "before_cursor_execute", record)

    begins = [statement for statement in statements if statement.upper().startswith("BEGIN")]
    assert begins, f"no BEGIN was issued at all; captured: {statements[:5]}"
    assert all(statement.upper() == "BEGIN IMMEDIATE" for statement in begins), (
        f"every transaction must begin IMMEDIATE, saw: {sorted(set(begins))}"
    )


def _analysis_body(approval_id: str) -> dict[str, object]:
    """A figure run the service can be asked for, with no material behind it."""
    return {
        "root_id": "source:0",
        "path": "one.csv",
        "operator_id": "labcairn.analysis.mean",
        "recipe": "recipe.json",
        "parameters": {},
        "approval_id": approval_id,
    }


def test_an_analysis_run_from_a_foreign_origin_is_refused(client: TestClient) -> None:
    """The route that draws a file is behind the origin guard like every change."""
    response = client.post(
        "/analysis",
        json=_analysis_body(str(new_id())),
        headers={"Origin": FOREIGN_ORIGIN},
    )
    assert response.status_code == 403
    assert response.json()["reason"] == GuardRefusal.ORIGIN_REFUSED.value


def test_an_analysis_run_without_the_token_is_refused(client: TestClient) -> None:
    """The right origin is not consent to run, and not consent to spend either."""
    response = client.post(
        "/analysis",
        json=_analysis_body(str(new_id())),
        headers={"Origin": OWN_ORIGIN},
    )
    assert response.status_code == 401
    assert response.json()["reason"] == GuardRefusal.SESSION_REQUIRED.value


def test_an_analysis_run_reaches_the_layer_and_returns_its_reason(
    client: TestClient, token: str
) -> None:
    """HTTP body -> the layer's request -> the seam's own refusal, in its shape.

    **What this proves and what it does not.** The task under test has no recipe
    file, so the seam answers `recipe_unreadable` — before the consent, and before
    the material. That the layer's reason arrives through the service's refusal
    shape is the plumbing; **it is not a claim that a figure was drawn**, and none
    was. The run's success path at a surface is witnessed where a material exists:
    `tests/test_cli.py::test_the_figure_command_refuses_before_the_run_with_the_layers_reasons`
    walks the same order at the console script, and the seam's own tests cover the
    consent, the operator and the receipts.
    """
    response = client.post(
        "/analysis",
        json=_analysis_body(str(new_id())),
        headers={"Origin": OWN_ORIGIN, **_authorization(token)},
    )
    assert response.status_code == 403, response.text
    assert response.json()["reason"] == ApplicationRefusal.RECIPE_UNREADABLE.value
