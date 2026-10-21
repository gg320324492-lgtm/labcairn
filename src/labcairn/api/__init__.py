"""The local API: a service on loopback, with the guards that make it safe to
leave running, and the typed contract the web workbench consumes.

``docs/ARCHITECTURE.md`` puts it in the stack — *"FastAPI exposes a
localhost-bound API"*, *"React + TypeScript + Vite consumes typed API
contracts"* — and its privacy invariants say why it needs guards at all:
*"localhost API requires origin restrictions and a local authenticated
session/token even if launched on loopback."* The plan's §2.6 gives the three
in order, and this package is them.

The three guards
----------------

1. **the bind address** — :func:`labcairn.api.bind.ensure_loopback` refuses a
   non-loopback address, and the service does not start. Not a warning: a
   service that is already listening is a service that is already reachable,
   and a warning is a thing a user reads once;
2. **the origin** — every request whose ``Origin`` is not the service's own is
   refused, whatever it asks for. The browser sets that header, and a page on
   another site cannot change it, so this is the defence that does not depend
   on the requester cooperating;
3. **the session** — a token minted at start-up, required on every request
   that changes something.

The session, stated exactly
---------------------------

* **Where the token lives.** In the service's memory, and in a file at
  ``<workspace>/.labcairn/session-token`` with the narrowest permissions the
  platform allows. The CLI prints the path.
* **How a client presents it.** The ``Authorization`` header, as
  ``Bearer <token>``. **A header and nothing else** — no cookie and no query
  parameter. A URL is pasted; a header is not. §1.4.4 did not take the cookie
  session, and a second way to present the token would be a second thing to
  get wrong.
* **How a client obtains it.** ``GET /session``, which the origin guard
  confines to the service's own origin.
* **Which requests require it.** Every request whose method is not ``GET``,
  ``HEAD`` or ``OPTIONS``. A read needs no token, so the workbench can draw
  the task before it has one.

How a browser reaches it
------------------------

**The API serves the built web app** (pass ``static_dir=``), so the browser
and the API share one origin and the origin check means what it says. While
the workbench is being developed it is served by Vite on another port, and
the service is then started with that origin in ``extra_origins`` — an
explicit, empty-by-default allow-list. The development server does **not**
rewrite the ``Origin`` header: a rewritten origin would make the check
vacuous in the very path that relies on it.

One serialization, two surfaces
-------------------------------

The response models are the application layer's own — ``TaskState``,
``TaskPlan``, ``SourceView``, ``ArtifactView`` and the rest — because §1.4.2
decided that the CLI and the API serve the same bytes. There is no "API view"
of a task here, because that would be the second spelling the plan warns
about, and the web app would then be showing the API's idea of the task
rather than the task.

The TypeScript types are in :mod:`labcairn.api.typescript` rather than
re-exported here, so that ``python -m labcairn.api.typescript`` does not
import the module twice — once as ``labcairn.api.typescript`` and once as
``__main__`` — which the interpreter warns about. They are generated into
**``web/src/api/generated.ts``**::

    uv run python -m labcairn.api.typescript web/src/api/generated.ts

and the web app imports that file rather than writing types of its own.

What this package does not do
-----------------------------

It does not reach the store. ``tests/test_application_layer.py`` asserts that
the application layer is the only way to the store, and a module here that
imported the store's readers would fail that test. Every route calls the
layer, and the event stream reads through a port the host supplies — see
:mod:`labcairn.api.events` for what that costs and what it is waiting for.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from labcairn.api.bind import (
    DEFAULT_BIND_HOST,
    DEFAULT_BIND_PORT,
    BindRefusedError,
    ensure_loopback,
)
from labcairn.api.guards import (
    GuardRefusal,
    GuardRefusedError,
    OriginPolicy,
    SessionGuard,
)
from labcairn.api.session import SessionToken, mint_token, write_token_file

if TYPE_CHECKING:
    from labcairn.api.app import contract_app, create_app, refusal_response, serve
    from labcairn.api.contracts import RefusalBody
    from labcairn.api.events import EventSource, UnwiredEventSource

__all__ = [
    "DEFAULT_BIND_HOST",
    "DEFAULT_BIND_PORT",
    "BindRefusedError",
    "EventSource",
    "GuardRefusal",
    "GuardRefusedError",
    "OriginPolicy",
    "RefusalBody",
    "SessionGuard",
    "SessionToken",
    "UnwiredEventSource",
    "contract_app",
    "create_app",
    "ensure_loopback",
    "mint_token",
    "refusal_response",
    "serve",
    "write_token_file",
]


def __getattr__(name: str) -> object:
    """The service's own machinery, imported on first use.

    :mod:`labcairn.api.app` imports FastAPI and the application layer, and
    :mod:`labcairn.api.contracts` and :mod:`labcairn.api.events` import the
    layer's models. **The bind address is cheap and the service is not**, and
    the CLI has to name one without paying for the other: the command line's
    own import is deferred, and the command that starts the service is the
    one that loads the service. So the package imports the cheap half
    eagerly and defers the half that would drag the layer in.
    """
    if name in ("contract_app", "create_app", "refusal_response", "serve"):
        from labcairn.api import app

        return getattr(app, name)
    if name == "RefusalBody":
        from labcairn.api.contracts import RefusalBody

        return RefusalBody
    if name in ("EventSource", "UnwiredEventSource"):
        from labcairn.api import events

        return getattr(events, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """The deferred symbols in the listing, so ``dir()`` is not a lie."""
    return sorted(
        [
            *globals(),
            "contract_app",
            "create_app",
            "refusal_response",
            "serve",
            "RefusalBody",
            "EventSource",
            "UnwiredEventSource",
        ]
    )
