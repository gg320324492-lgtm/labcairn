"""The Typer command line — one of the three surfaces on the application layer.

``docs/plans/LC-P1-11-12-task-breakdown.md`` §2.5 is the requirement: *"CLI/
API/UI call same application layer"*. A property like that is not made by
three implementations agreeing; it is made by there being one implementation
for the three to call.

What this package is
--------------------

Eight commands — ``init``, ``doctor``, ``task create/run/status/resume``,
``sources inspect``, ``artifacts list`` — and the plumbing they share:

* **every command's data comes from the application layer.** A command here
  decides what to ask and how to draw the answer. It never reads the store
  and never computes a thing the layer would compute. The one thing it
  builds for the layer is the store handle, because the handle is what the
  layer consumes;
* **every command has a machine-readable form, and the rendered form is a
  drawing of the same data.** ``docs/ARCHITECTURE.md`` says formatting must
  never be load-bearing for a machine-readable command, and this package is
  arranged so that it cannot be: the model is built first, and the prose and
  the JSON are two renderings of it;
* **a refusal is rendered, not raised.** The layer's
  :class:`~labcairn.application.ApplicationRefusedError` becomes a message
  naming what was refused and exit code :data:`~labcairn.cli.commands.
  EXIT_REFUSED`. A command that raises a traceback is a command that has
  failed to be a command.

The JSON and the API
--------------------

The machine-readable form is the layer's own pydantic model, serialised by
pydantic — the same bytes the local API will serve for the same question.
The two exceptions are ``init`` and ``doctor``, which report on a *workspace*
rather than on a task; the application layer has no operation that does that,
so their models are this package's, and that is recorded in
:mod:`labcairn.cli.models` rather than left for someone to discover.
"""

from __future__ import annotations

import sys
from typing import TextIO

from labcairn.cli.commands import app

#: The console script. ``labcairn init``, ``labcairn doctor``, and so on.
console_script = "labcairn"


def main() -> None:
    """The console script's entry point.

    The output encoding is set to UTF-8 before anything is written, and that
    is load-bearing rather than tidiness. **The bytes the CLI writes are the
    bytes the API serves**, and a redirected stream on Windows takes the
    machine's ANSI code page: a task whose title or a source's name holds a
    character that code page cannot spell would either be mangled or raise,
    and the JSON a script read would not be the JSON the API returned. A
    fixed encoding makes the answer the same wherever the bytes land.
    """
    _write_utf8(sys.stdout)
    _write_utf8(sys.stderr)
    app()


def _write_utf8(stream: TextIO | None) -> None:
    """Ask *stream* for UTF-8, if it can be asked.

    A stream that cannot be reconfigured — a test's capture object, a
    replaced handle — is left alone rather than made an error: the encoding
    is a correctness matter for real output, not a reason to refuse to run.
    """
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(encoding="utf-8")
    except (OSError, ValueError):  # pragma: no cover - depends on the stream
        return


__all__ = ["app", "console_script", "main"]
