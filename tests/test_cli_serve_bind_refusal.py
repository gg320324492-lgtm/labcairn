"""The refusal the service's own bind guard raises, at the moment of binding.

``labcairn serve`` checks the bind address before it starts anything: the
command asks :func:`labcairn.api.bind.ensure_loopback` whether the address is
loopback, and refuses there if it is not. The service asks the same question
again, at the point where the socket is about to be opened, and refuses
there too.

**The second refusal is a branch no invocation of the command can reach, and
it is watched anyway.** The command has already asked the same question about
the same address, and the guard is a pure function of the address, so the
answer cannot change between the two. A witness that waited for the command
to arrive there would wait for ever — and the refusal would be one that a
change to the product could remove with nothing noticing.

So the guard's refusal is **injected where the guard raises it**: the
service's own runner is asked to bind an address the command never checked,
the guard refuses that address, and the tree is asked what the command does
with the refusal. What the command does is the property: a refusal rendered
with the exit code a script branches on, carrying the command's own sentence
and the guard's reason, and not a traceback.

**The port is one the operating system says is free.** The command binds a
probe socket to the port before it starts the service, so a test that used
the machine's own port 8000 would be refused for the address rather than
reach the refusal it is about — and would pass for the wrong reason on a
machine where 8000 happened to be busy.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from typer.testing import CliRunner

from labcairn.cli.commands import EXIT_REFUSED, app

pytestmark = pytest.mark.negative

#: The address the command is asked to bind.
HOST = "127.0.0.1"

#: The address the service's own guard is asked about, in the injection.
#:
#: **A routable address, and that is the point.** The guard refuses it, and
#: the refusal is the layer's own — the one the command would have been given
#: had it asked about this address rather than the one it did.
GUARDED_ADDRESS = "0.0.0.0"


# --------------------------------------------------------------------------- #
# the environment
# --------------------------------------------------------------------------- #


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A workspace the CLI itself made.

    **The command is run in this process, not as a child.** The failure this
    file is about has to be injected where the service binds, and that is
    inside the command; a child process could not be given the injection.
    """
    root = tmp_path / "workspace"
    result = CliRunner().invoke(app, ["--workspace", str(root), "init"])
    assert result.exit_code == 0, result.output
    return root


@pytest.fixture
def task_workspace(workspace: Path) -> Path:
    """A workspace holding one task, which the serve command is about."""
    result = CliRunner().invoke(
        app,
        [
            "--workspace",
            str(workspace),
            "task",
            "create",
            "--title",
            "Read the literature",
            "--objective",
            "Establish what the corpus says about the question.",
            "--criterion",
            "A cited answer, or an honest 'not established'.",
        ],
    )
    assert result.exit_code == 0, result.output
    return workspace


def _a_free_port() -> int:
    """A port the operating system says is free.

    **Never the machine's own port 8000.** The command binds a probe socket
    to the port before it starts the service, so a port that is already taken
    is refused for the address — a different refusal, with a different
    sentence — and the witness would be answering for the wrong reason.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((HOST, 0))
        return int(probe.getsockname()[1])


def _the_refusal(output: str) -> dict[str, Any]:
    """The refusal in the command's output.

    **The last document, not the first.** The command reports the service it
    is about to start before it starts it, so the machine-readable output
    holds that report and then the refusal, and the refusal is the one that
    says what happened.
    """
    documents: list[dict[str, Any]] = [
        json.loads(line) for line in output.splitlines() if line.strip()
    ]
    assert documents, "the command printed nothing"
    return documents[-1]


# --------------------------------------------------------------------------- #
# the refusal
# --------------------------------------------------------------------------- #


def _the_service_refuses_the_bind(service: FastAPI, *, host: str, port: int) -> None:
    """The service's own runner, handed an address the command never checked.

    **The layer's own refusal, raised where the layer raises it.** The
    service's runner asks the guard whether the address is loopback, and the
    guard refuses one that is not. So this is the failure the command's
    handler exists for, produced by the code that produces it — and not a
    hand-written error that only looks like one.
    """
    del host
    from labcairn.api import serve

    serve(service, host=GUARDED_ADDRESS, port=port)


def test_the_command_refuses_a_bind_the_service_would_not_make(
    task_workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A service that will not bind is refused, and the refusal is the command's.

    **A refusal and not a crash.** The exit code is the one a script branches
    on, and the reason is the command's own: an argument the command will not
    act on. A command that let the guard's refusal out would exit 1 and print
    a traceback, and a traceback where the program promised a refusal is a
    crash.

    **The sentence is the command's own, and the guard's reason is carried
    with it.** The refusal names the guard that refused the bind, so that it
    can be told apart from the address check's own refusal — which carries
    the same failure and is reachable — and it quotes the guard's reason, so
    that the operator is told which address was refused and why.
    """
    monkeypatch.setattr("labcairn.cli.commands.run_service", _the_service_refuses_the_bind)
    port = _a_free_port()

    result = CliRunner().invoke(
        app,
        [
            "--workspace",
            str(task_workspace),
            "serve",
            "--host",
            HOST,
            "--port",
            str(port),
            "--json",
        ],
    )

    assert result.exit_code == EXIT_REFUSED, (
        f"the command exited {result.exit_code} rather than refusing; the "
        f"exception was {result.exception!r}"
    )
    payload = _the_refusal(result.stdout)
    assert payload["reason"] == "invalid_arguments"
    assert "the service's own guard refused the bind" in payload["message"]
    assert "loopback" in payload["message"]
