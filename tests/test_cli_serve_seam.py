"""`tests/test_cli.py`'s section, split out for the shard partition.

The section is byte-identical to the monolith's; the rig comes from
`test_cli_support`.
"""

from __future__ import annotations

import socket
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from test_cli_support import (
    run_cli,
)
from test_cli_support import (
    task_id as _task_id_fixture,
)
from test_cli_support import (
    workspace as _workspace_fixture,
)

from labcairn.cli.commands import EXIT_REFUSED

task_id = _task_id_fixture
workspace = _workspace_fixture


task_id = _task_id_fixture
workspace = _workspace_fixture

pytestmark = pytest.mark.e2e


# --------------------------------------------------------------------------- #
# serve
# --------------------------------------------------------------------------- #


@contextmanager
def _a_taken_port() -> Iterator[int]:
    """A port this process holds, so that the CLI cannot bind it.

    **Why the witnesses below take one.** ``serve`` checks the origin and
    the workbench *before* it checks the address, and if it finds nothing
    wrong with them it starts the service — which never ends, so a test
    waiting for it waits forever. That is what a witness has to be able to
    survive: the refusal it watches has to be the one that answers, and the
    answer has to be visible.

    So the witness holds the port itself. A command that got past the
    refusal it was meant to be stopped by is then refused for the address —
    a different sentence, on a port the witness chose — and the test fails
    on the sentence rather than hanging. **The machine's own port 8000 is
    not consulted at all**, which is what made the difference: on a machine
    where 8000 happened to be busy the neighbour's refusal answered and the
    witness passed for the wrong reason, and on a machine where it was free
    the service started and the witness hung instead of failing.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen(1)
        yield int(taken.getsockname()[1])


def test_serve_refuses_a_port_that_is_not_a_port(workspace: Path, task_id: str) -> None:
    """A port that is not a port is refused, and refused before anything binds.

    The service's own origin is computed from the port it was given, so a
    port that names nothing would make the origin name a place nothing is
    listening on. The refusal is the command's own, and says why the port
    matters rather than only that it is wrong.

    **The command is given a second defect on purpose** — an origin that is
    not an origin — so that a command which got past this refusal is
    refused for the origin instead of *starting the service*. A port of
    zero is one the operating system would choose, so with this refusal
    removed the service would start and the test would wait for a service
    that never ends. The second defect makes the answer visible, and the
    witness fails on the sentence rather than hanging.
    """
    result = run_cli(
        "--workspace",
        str(workspace),
        "serve",
        "--port",
        "0",
        "--origin",
        "not-an-origin",
        "--json",
    )

    assert result.returncode == EXIT_REFUSED
    payload = result.json()
    assert payload["reason"] == "invalid_arguments"
    assert "is not a port number" in payload["message"]


def test_serve_refuses_an_origin_that_is_not_an_origin(workspace: Path, task_id: str) -> None:
    """An origin that is not spelled as one is refused.

    A path or a trailing slash would never match the header the browser
    sends, so accepting one would be accepting an origin that does nothing.
    The refusal says what an origin is, so the developer can spell one.

    **Told apart by its sentence, and it says which one it is.** The origin
    that carries a path is refused by the next refusal, with the same reason
    and a different sentence; a witness that asserted only the reason would
    be satisfied by either, so this one asserts the sentence.
    """
    with _a_taken_port() as port:
        result = run_cli(
            "--workspace",
            str(workspace),
            "serve",
            "--origin",
            "not-an-origin",
            "--port",
            str(port),
            "--json",
        )

    assert result.returncode == EXIT_REFUSED
    payload = result.json()
    assert payload["reason"] == "invalid_arguments"
    assert "An origin is a scheme, a host and a port" in payload["message"]


def test_serve_refuses_an_origin_that_carries_a_path(workspace: Path, task_id: str) -> None:
    """An origin that carries more than an origin is refused.

    This is a different refusal from the one above, and it says so: an
    origin carries no path, no query and no fragment. The two refusals are
    told apart by the words they use, which is why both are watched.

    **The witness holds the port** so that a command which got past this
    refusal is refused for the address instead of starting the service. See
    :func:`_a_taken_port`: without it the witness passed on a machine whose
    port 8000 was busy and hung on a machine whose port 8000 was free, and
    neither of those is a witness.
    """
    with _a_taken_port() as port:
        result = run_cli(
            "--workspace",
            str(workspace),
            "serve",
            "--origin",
            "http://localhost:5173/path",
            "--port",
            str(port),
            "--json",
        )

    assert result.returncode == EXIT_REFUSED
    payload = result.json()
    assert payload["reason"] == "invalid_arguments"
    assert "carries no path, no query and no fragment" in payload["message"]


def test_serve_refuses_a_workbench_that_is_not_a_directory(
    workspace: Path, task_id: str, tmp_path: Path
) -> None:
    """A workbench that is not a directory is refused, not ignored.

    The service would answer on its own origin with no workbench on it, and
    the developer would be left with a service that serves nothing and no
    reason why.

    **The witness holds the port** so that a command which got past this
    refusal is refused for the address instead of starting the service. See
    :func:`_a_taken_port`.
    """
    not_a_directory = tmp_path / "not-a-directory"
    not_a_directory.write_text("a file, not a directory", encoding="utf-8")

    with _a_taken_port() as port:
        result = run_cli(
            "--workspace",
            str(workspace),
            "serve",
            "--static-dir",
            str(not_a_directory),
            "--port",
            str(port),
            "--json",
        )

    assert result.returncode == EXIT_REFUSED
    payload = result.json()
    assert payload["reason"] == "invalid_arguments"
    assert "no built workbench there to serve" in payload["message"]
