"""The service: what it is, what it refuses, and how it is reached.

Three guards, in the order the plan puts them
----------------------------------------------

``docs/plans/LC-P1-11-12-task-breakdown.md`` §2.6 lists them, and the order
is the order of the failure they prevent:

1. **the bind address** — :func:`labcairn.api.bind.ensure_loopback` refuses a
   non-loopback address before the service exists, so there is nothing to
   warn about afterwards;
2. **the origin** — every request whose ``Origin`` is not the service's own is
   refused, whatever it asks for. This is the real defence, because the
   browser sets the header and a page on another site cannot;
3. **the session** — a token minted at start-up, required on every request
   that changes something.

How a browser reaches this service
-----------------------------------

**The API serves the built web app**, so there is exactly one origin and the
origin check means what it says. ``create_app`` takes a ``static_dir`` and
mounts it; the workbench is then served from ``http://127.0.0.1:8000`` and
talks to the API on that same origin, which is what §1.4.4's *"the UI obtains
the token through a same-origin request"* describes.

**The development server is the exception, and it is explicit.** While the
web app is being developed it is served by Vite on another port, and a fetch
from there carries that port's origin. The service is therefore started with
the development origin in ``extra_origins``::

    create_app(context, extra_origins=["http://localhost:5173"])

Two things are deliberately *not* done here. The development server does
**not** rewrite the ``Origin`` header on the way through: a rewritten origin
would make the check vacuous in exactly the path where the check is being
relied on, and it would leave the hole open to any other origin too. And the
allow-list is empty by default, so a service that was not told about the
development origin refuses it.

The session, stated exactly
---------------------------

* **Where the token lives.** In the service's memory, and in a file at
  ``<workspace>/.labcairn/session-token`` written with the narrowest
  permissions the platform allows. The CLI prints the path.
* **How a client presents it.** In the ``Authorization`` header, as
  ``Bearer <token>``. **A header and nothing else** — no cookie, no query
  parameter. A URL is pasted and a header is not, and §1.4.4 did not take the
  cookie session.
* **How a client obtains it.** ``GET /session``, which the origin guard
  confines to the service's own origin. A client that cannot be at that
  origin cannot ask.
* **Which requests require it.** Every request whose method is not ``GET``,
  ``HEAD`` or ``OPTIONS``. A read needs no token, so the workbench can draw
  the task before it has one.

Where the contract lives
------------------------

The response models are the application layer's, so the contract is read from
:func:`contract_app` — the same routes with none of the state — and exported
as an OpenAPI document. The TypeScript types are generated from that document
by :mod:`labcairn.api.typescript` into **``web/src/api/generated.ts``**, and
the checked-in file is compared with the generated one by a test, so a Python
model that changes without the TypeScript being regenerated is a **test
failure** rather than a note.

Regenerating them::

    uv run python -m labcairn.api.typescript web/src/api/generated.ts

and checking them::

    uv run pytest -q tests/test_api.py

The web app imports that file rather than writing its own types, and the
check is re-runnable by whoever changes either side.

The service lets go of the store between requests
--------------------------------------------------

**The store's session belongs to the process, and the write lock must not.**

:mod:`labcairn.db.session` opens *every* transaction with ``BEGIN
IMMEDIATE`` — ADR-0003 C3's clause, and the right one for a write: two
writers must not interleave. A read is a transaction too, so a read takes
SQLite's **write** lock rather than a read lock, and the session this service
holds lives as long as the process does. Without a boundary, the service
would hold the write lock from its first read until its next commit, and
every other process — the CLI above all — would be refused with
*"database is locked"*. That was measured, not inferred: a read through the
store's session issues ``BEGIN IMMEDIATE``, a second connection is refused,
and the reader blocks another process's **write**, not only its read.

So the service ends the transaction when a request is over. A local research
workspace whose service holds the database hostage while it runs is not a
workspace two surfaces can be used in, and G4's exit clause compares what the
CLI and the web say about the same task — so they have to be usable against
one workspace at the same time.

:func:`_end_the_store_transaction` says what the ending does, and what it
does not do.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any, Protocol, cast

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from labcairn.api.bind import (
    DEFAULT_BIND_HOST,
    DEFAULT_BIND_PORT,
    BindRefusedError,
    ensure_loopback,
    own_origin,
)
from labcairn.api.contracts import RefusalBody
from labcairn.api.events import EventSource, UnwiredEventSource
from labcairn.api.guards import (
    GUARD_STATUS_CODES,
    FetchMetadata,
    GuardRefusal,
    GuardRefusedError,
    OriginPolicy,
    SessionGuard,
)
from labcairn.api.routes import router
from labcairn.api.session import (
    SESSION_DIR_NAME,
    SESSION_FILE_NAME,
    SessionToken,
    mint_token,
    write_token_file,
)
from labcairn.application import ApplicationContext
from labcairn.application.refusal import ApplicationRefusedError
from labcairn.application.stages import StageWork

#: The logger the service records its requests in.
logger = logging.getLogger("labcairn.api")

#: The OpenAPI document's title and version. Both apps that carry the routes
#: use these, so the contract read from one is the contract read from the
#: other.
API_TITLE = "LabCairn local API"
API_VERSION = "0.1.0"

#: The status a refusal from the application layer is answered with.
#:
#: One status for every refusal, because the reason is what a caller branches
#: on and the status is what a proxy and a log read. 403 is the status that
#: means "refused": the request was understood and the service declined to
#: carry it out.
LAYER_REFUSAL_STATUS = 403


class _Refusal(Protocol):
    """Anything that can render itself as a refusal's two fields."""

    def to_payload(self) -> dict[str, str]:
        """The refusal as data."""
        ...


def refusal_response(refusal: _Refusal, status_code: int) -> JSONResponse:
    """A refusal as a response, in the shape every refusal has.

    The body is the refusal's own payload, validated into
    :class:`~labcairn.api.contracts.RefusalBody` and rendered from *that*, so
    the wire form is described by the OpenAPI document rather than by
    whatever a handler happened to put in a dictionary.
    """
    body = RefusalBody.model_validate(refusal.to_payload())
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


def _enforce_guards(request: Request) -> None:
    """Apply the origin guard, the fetch-metadata rule, and then the session guard.

    The order matters and is the order of the plan: a request from a foreign
    origin is refused *before* the session is looked at, so a request with a
    valid token and a foreign origin is still refused. A token is not a pass
    to a page on another site.

    The fetch-metadata rule sits between the two because it answers a
    question the origin check cannot: the request carries **no** origin, so
    there is nothing there to judge, and the browser's own metadata says
    where it came from instead.
    """
    origins = cast(OriginPolicy, request.app.state.origins)
    origin = request.headers.get("origin")
    if not origins.permits(origin):
        raise GuardRefusedError(
            GuardRefusal.ORIGIN_REFUSED,
            f"the request's origin {origin!r} is not one of this service's own "
            f"({', '.join(sorted(origins.allowed))}). A page on another site cannot "
            "drive a local service, and the browser sends the origin whether the "
            "page means to or not.",
        )
    if origin is None:
        fetch = FetchMetadata.from_headers(request.headers)
        if fetch.is_cross_site_subresource():
            raise GuardRefusedError(
                GuardRefusal.CROSS_SITE_REFUSED,
                "the request carries no origin, and the browser says it came from "
                "another site and was not a navigation. A page on another site can "
                "load a resource from a local service without an origin, and this "
                "is the request that is: a link the user clicks is a navigation and "
                "is still served.",
            )
    guard = cast(SessionGuard, request.app.state.session_guard)
    presented = SessionGuard.read(request.headers)
    if not guard.permits(request.method, presented):
        raise GuardRefusedError(
            GuardRefusal.SESSION_REQUIRED,
            "the request changes something and did not present the session token. "
            "The token is in the Authorization header as 'Bearer <token>'; it is "
            "never in a URL, and a URL is pasted.",
        )


def create_app(
    context: ApplicationContext,
    *,
    host: str = DEFAULT_BIND_HOST,
    port: int = DEFAULT_BIND_PORT,
    extra_origins: Sequence[str] = (),
    session_file: Path | None = None,
    event_source: EventSource | None = None,
    stage_work: StageWork | None = None,
    static_dir: Path | None = None,
) -> FastAPI:
    """The service, bound to a task.

    :param context: the application context every route calls through.
    :param host: the address to bind. Refused unless it is a loopback address.
    :param port: the port to bind, and the port that is part of the service's
        own origin.
    :param extra_origins: origins to answer to besides the service's own. The
        development web server is the only reason this exists, and it is empty
        unless somebody asks for it.
    :param session_file: where the token is written. Defaults to
        ``<workspace>/.labcairn/session-token``.
    :param event_source: where the event stream reads from. Without one the
        stream refuses in the layer's vocabulary rather than pretending to be
        empty.
    :param stage_work: the effect a stage run performs.
    :param static_dir: the built web app to serve, so that the browser and the
        API share one origin.
    :raises BindRefusedError: *host* is not a loopback address.
    """
    ensure_loopback(host)
    origin = own_origin(host, port)
    origins = OriginPolicy.for_service(origin, extra_origins)

    token_file = (
        session_file
        if session_file is not None
        else context.workspace.selected_root / SESSION_DIR_NAME / SESSION_FILE_NAME
    )
    value = mint_token()
    token = SessionToken(value=value, path=write_token_file(token_file, value))

    app = _base_app()
    app.state.context = context
    app.state.host = host
    app.state.port = port
    app.state.origins = origins
    app.state.session = token
    app.state.session_guard = SessionGuard(token=token)
    app.state.event_source = event_source if event_source is not None else UnwiredEventSource()
    app.state.stage_work = stage_work
    app.include_router(router)
    _install_guards(app)
    _install_refusal_handlers(app)
    _mount_workbench(app, static_dir)
    _install_store_release(app)
    return app


def contract_app() -> FastAPI:
    """The app the contract is read from.

    The same routes and the same models, with none of the state and no
    service behind them. It exists so that the OpenAPI document can be read
    without a store, a workspace or a task: the contract is a property of the
    models, and asking for a database to learn a schema would be a bad
    bargain.
    """
    app = _base_app()
    app.include_router(router)
    return app


def serve(app: FastAPI, *, host: str, port: int) -> None:
    """Run the service until it is stopped.

    The bind address is checked again here, at the point where the socket is
    about to be opened, so that a service assembled by hand and handed to
    :func:`serve` cannot skip the check the factory made.

    Uvicorn's access log is switched off. It records the request line, and
    the request line carries the query string — which is where a token
    would be if a client had put one there. The service's own structured log
    records the method, the path and the outcome instead, and leaves the
    query string out on purpose.
    """
    ensure_loopback(host)
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="warning", access_log=False)


def _base_app() -> FastAPI:
    """The app both factories share.

    The interactive documentation is switched off. FastAPI's ``/docs`` page
    loads its assets from a content delivery network, and a local-first tool
    that reaches out to one when a human opens a page is a tool with an
    outbound request it did not say it had. The contract itself — the OpenAPI
    document at ``/openapi.json`` — is generated locally and is served.

    The two refusal statuses are declared for every route, because every
    route can be refused: the origin guard refuses any of them, and the
    application layer refuses any of them for its own reasons. Declaring them
    here rather than on each route is what puts the refusal body in the
    contract, so the workbench knows the shape of an error without having to
    read one to find out.
    """
    return FastAPI(
        title=API_TITLE,
        version=API_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url="/openapi.json",
        responses={
            401: {
                "model": RefusalBody,
                "description": "The request changes something and did not present the "
                "session token.",
            },
            403: {
                "model": RefusalBody,
                "description": "The request was refused: a foreign origin, or the "
                "application layer declined to carry it out.",
            },
        },
    )


def _install_guards(app: FastAPI) -> None:
    """Put the two request guards in front of every route.

    Middleware rather than a dependency, so that a route added later is
    covered without anyone remembering to add the guard to it. The guard is
    the thing that has to be impossible to forget.
    """

    @app.middleware("http")
    async def _guards(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        try:
            _enforce_guards(request)
        except GuardRefusedError as refusal:
            logger.warning(
                "request refused",
                extra={
                    "event": "request_refused",
                    "reason": refusal.reason.value,
                    "method": request.method,
                    "path": request.url.path,
                },
            )
            return refusal_response(refusal, GUARD_STATUS_CODES[refusal.reason])
        response = await call_next(request)
        # The path and the method only. The query string is left out on
        # purpose: it is the one place a client could put a secret, and a log
        # that records it would be a log holding a credential.
        logger.info(
            "request served",
            extra={
                "event": "request",
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
            },
        )
        return response


def _install_refusal_handlers(app: FastAPI) -> None:
    """Turn the layer's refusal into a response.

    A refusal is a response and not a crash: the layer raises
    :class:`~labcairn.application.refusal.ApplicationRefusedError` with a
    machine-readable reason, and the surface renders it. Every route's
    refusal is rendered by this one handler, so they are all the same status
    code and the same two fields.
    """

    @app.exception_handler(ApplicationRefusedError)
    async def _refused(request: Request, error: ApplicationRefusedError) -> JSONResponse:
        del request
        return refusal_response(error, LAYER_REFUSAL_STATUS)


def _mount_workbench(app: FastAPI, static_dir: Path | None) -> None:
    """Serve the built web app, so that the browser and the API share an origin.

    Mounted at the root, after the API's own routes, so a request for
    ``/task`` reaches the API and a request for ``/`` reaches the workbench.
    The mount is skipped when there is no build to serve, which is the case
    while the workbench is being developed.
    """
    if static_dir is None or not static_dir.is_dir():
        return
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="workbench")


def _install_store_release(app: FastAPI) -> None:
    """Put the store release around the service.

    Added last of all, so that it is the outermost middleware: it has to run
    around the guards too, because a request the guards refuse must leave the
    store as it found it.
    """
    app.add_middleware(_StoreRelease)


class _StoreRelease:
    """Let go of the store's transaction when a request is over.

    A plain ASGI middleware rather than the ``@app.middleware("http")`` form,
    and the difference is one of timing rather than of kind. The ``http`` form
    resumes as soon as the handler has returned, which for a streamed
    response is *before* the body has been sent — so a body that reads the
    store would open its transaction after the release and leave it open.
    This one resumes when the response has been sent, which is the moment the
    request is really over.
    """

    def __init__(self, app: Any) -> None:
        self._app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        try:
            await self._app(scope, receive, send)
        finally:
            if scope["type"] == "http":
                _end_the_store_transaction(scope["app"])


def _end_the_store_transaction(app: Any) -> None:
    """End the store's transaction, and with it SQLite's write lock.

    **A rollback and not a commit, and the difference is not a matter of
    taste.** A commit *writes* anything left pending, and a unit of work that
    was never committed is one that ADR-0003 C3 says rolls back; and a commit
    leaves the session's identity map as it was, so the next request would be
    answered from the objects the previous one loaded. That was measured:
    after a request ended with a commit, the next read answered with the
    title as it was *before* another process changed it. A rollback expires
    those objects, so the next read is a fresh one.

    **Why nothing is lost.** Every write goes through
    :meth:`~labcairn.db.repository.TaskStore.unit`, which commits inside the
    request; by the time the request is over there is nothing pending, so the
    rollback discards nothing. A unit that was *not* committed is rolled
    back, which is what C3 asks for.

    **Why nothing is written twice.** A rollback writes nothing at all. The
    write path's SQL is untouched: a write is still ``BEGIN IMMEDIATE``, the
    events, the state rows and the ``COMMIT`` that ADR-0003 C3 describes.

    **Why nothing reads an ORM attribute after this point.** The store's
    readers project their rows into frozen contracts while the transaction is
    open — :func:`~labcairn.db.repository.load_task` and its neighbours
    return a ``Task``, not a ``TaskRow`` — and the response is built before
    the request is over. So the rollback expires objects nobody is going to
    read, and the next request reads the database.
    """
    context = cast(ApplicationContext, app.state.context)
    context.store.session.rollback()


__all__ = [
    "API_TITLE",
    "API_VERSION",
    "LAYER_REFUSAL_STATUS",
    "BindRefusedError",
    "contract_app",
    "create_app",
    "refusal_response",
    "serve",
]
