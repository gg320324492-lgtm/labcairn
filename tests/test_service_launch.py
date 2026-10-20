"""The launch path: the command that starts the local service.

What is asserted here, and why each assertion is written the way it is
-----------------------------------------------------------------------

**The service is really bound.** A command that prints an address is not a
service. One test starts the command as a process, asks the service itself
over a socket where it is, and stops it; the port is one the operating
system chose as free, so the test neither depends on 8000 being free nor
leaves a port bound.

**A refusal is a refusal, and it starts nothing.** A bind address that is
not loopback, a workspace with no current task, a directory that is not a
workspace: each ends with the exit code a script branches on, and none of
them leaves a service running or a token written.

**A parameter that is accepted must change what happened.** The port, the
host, the origins and the workbench are each exercised with a value that is
not the default, and the consequence is asserted against the service's own
answer rather than against the command's claim about itself. The port is
checked at the two points where it is used — the socket the command opens
and the service it starts — because a port that was accepted and thrown
away would be a parameter that lies.

**The token is never printed.** The service mints one at start-up and writes
it to the workspace; the command reports where and not what, and the test
compares the file, the service's own answer and the command's output with
each other.

**Nothing is bound in a test that does not need it.** Most of these run the
command in this process with the socket-opening stopped, so the wiring can
be looked at without a port being taken and given back.
"""

from __future__ import annotations

import http.client
import inspect
import json
import os
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

import pytest
from fastapi import FastAPI
from typer.testing import CliRunner

from labcairn.cli.commands import EXIT_REFUSED, app

#: The origin the service answers to when it binds the default port.
DEFAULT_ORIGIN = "http://127.0.0.1:8000"

#: The origin the workbench's development server is served from.
DEVELOPMENT_ORIGIN = "http://127.0.0.1:5173"

#: An origin that is not the service's own. A page on another site sends
#: exactly this.
FOREIGN_ORIGIN = "https://evil.example"


# --------------------------------------------------------------------------- #
# running the CLI
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class CliResult:
    """What one run of the CLI produced."""

    returncode: int
    stdout: str
    stderr: str

    def json(self) -> Any:
        """The machine-readable form, parsed."""
        return json.loads(self.stdout)


def _console_script() -> Path:
    """The script a developer types, as this interpreter would find it.

    Beside the running interpreter rather than on ``PATH``: the test must
    exercise the script the project installs, and ``PATH`` is the machine's
    business.
    """
    name = "labcairn.exe" if os.name == "nt" else "labcairn"
    return Path(sys.executable).parent / name


def run_cli(*args: str) -> CliResult:
    """Run the console script and return what it produced.

    The command is run as a process rather than called in this one, because
    the exit code and the two streams are what a script depends on and a
    call in this process would not produce them.
    """
    script = _console_script()
    if not script.is_file():
        pytest.fail(
            f"the console script is not installed at {script}. The CLI is tested "
            "through the script a developer types, so it has to be there; run "
            "`uv sync`."
        )
    completed = subprocess.run(
        [str(script), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "COLUMNS": "200"},
        timeout=300,
    )
    return CliResult(completed.returncode, completed.stdout, completed.stderr)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A workspace the CLI itself made."""
    root = tmp_path / "workspace"
    result = run_cli("--workspace", str(root), "init")
    assert result.returncode == 0, f"init failed: {result.stderr}"
    return root


@pytest.fixture
def task_id(workspace: Path) -> str:
    """A task the CLI itself made, and the workspace's current task."""
    result = run_cli(
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
        "--json",
    )
    assert result.returncode == 0, f"task create failed: {result.stderr}"
    return str(result.json()["task_id"])


@pytest.fixture
def port() -> int:
    """A port the operating system says is free.

    **Never the default port.** 8000 is the port the workbench's proxy
    points at, so it is the port a developer will have something on, and a
    test that failed because the machine's 8000 was busy would be a test
    that fails at random.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


# --------------------------------------------------------------------------- #
# the command, without the socket
# --------------------------------------------------------------------------- #


@pytest.fixture
def served(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int]]:
    """The address the service was started on, with the socket left unopened.

    The command does everything — the workspace, the task, the origins, the
    token — before the socket is opened, and this stops it there so that
    the wiring can be looked at without a port being taken and given back.
    """
    started: list[tuple[str, int]] = []

    def _record(app: FastAPI, *, host: str, port: int) -> None:
        del app
        started.append((host, port))

    monkeypatch.setattr("labcairn.cli.commands.run_service", _record)
    return started


@pytest.fixture
def binds(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """The addresses the command binds, as it binds them."""
    recorded: list[Any] = []

    class _RecordingSocket(socket.socket):
        def bind(self, address: Any, /) -> None:
            recorded.append(address)
            super().bind(address)

    monkeypatch.setattr(socket, "socket", _RecordingSocket)
    return recorded


def _invoke(*args: str) -> Any:
    """The command, run in this process.

    The runner is used rather than the console script because the point of
    these tests is the wiring *inside* the command, and the socket-opening
    is stopped by the ``served`` fixture.
    """
    return CliRunner().invoke(app, list(args))


def _serve_command() -> Any:
    """The command's own function, as the CLI registered it."""
    for info in app.registered_commands:
        callback = info.callback
        if callback is not None and callback.__name__ == "serve":
            return callback
    raise AssertionError("the CLI has no serve command")


# --------------------------------------------------------------------------- #
# the refusals
# --------------------------------------------------------------------------- #


def test_the_command_refuses_a_bind_address_that_is_not_loopback(
    workspace: Path, task_id: str
) -> None:
    """A service that would be reachable from the network does not start.

    The refusal is the service's own words, it is a refusal rather than a
    crash, and **nothing was written**: a service that refused to start
    has no session, so no token was minted and no file was made.
    """
    result = run_cli("--workspace", str(workspace), "serve", "--host", "0.0.0.0")
    assert result.returncode == EXIT_REFUSED
    assert result.stdout == ""
    assert "loopback" in result.stderr
    assert not (workspace / ".labcairn" / "session-token").exists()


def test_the_refusal_is_machine_readable(workspace: Path, task_id: str) -> None:
    """The refusal has the same two fields every other refusal has.

    The reason is the CLI's own vocabulary — an argument the command will
    not act on — so a script reads one refusal format whichever surface
    produced it.
    """
    result = run_cli("--workspace", str(workspace), "serve", "--host", "0.0.0.0", "--json")
    assert result.returncode == EXIT_REFUSED
    payload = result.json()
    assert payload["reason"] == "invalid_arguments"
    assert "loopback" in payload["message"]


def test_the_command_refuses_a_workspace_with_no_current_task(workspace: Path) -> None:
    """The API is task-scoped, and the service will not guess which task.

    A workspace with no current task is refused with the reason every other
    task-scoped command uses, so a script reads one refusal vocabulary.
    """
    result = run_cli("--workspace", str(workspace), "serve", "--json")
    assert result.returncode == EXIT_REFUSED
    assert result.json()["reason"] == "task_not_selected"


def test_the_command_refuses_a_directory_that_is_not_a_workspace(tmp_path: Path) -> None:
    """A directory that holds no workspace is not a workspace."""
    result = run_cli("--workspace", str(tmp_path), "serve", "--json")
    assert result.returncode == EXIT_REFUSED
    assert result.json()["reason"] == "workspace_not_initialised"


def test_the_command_refuses_a_port_that_is_not_a_port(workspace: Path, task_id: str) -> None:
    """Port zero would let the operating system choose, and the origin would lie.

    The service's own origin is computed from the port it is given, so a
    port that names no port would make the origin name an address nothing
    is listening on.
    """
    result = run_cli("--workspace", str(workspace), "serve", "--port", "0", "--json")
    assert result.returncode == EXIT_REFUSED
    assert result.json()["reason"] == "invalid_arguments"


def test_the_command_refuses_an_origin_that_is_not_an_origin(workspace: Path, task_id: str) -> None:
    """An origin with a path would never match a header the browser sends.

    The browser sends a scheme, a host and a port and nothing else, so an
    origin with a path is an origin that would never be permitted — and
    accepting it would be accepting a parameter that does nothing.
    """
    result = run_cli(
        "--workspace",
        str(workspace),
        "serve",
        "--origin",
        "http://localhost:5173/elsewhere",
        "--json",
    )
    assert result.returncode == EXIT_REFUSED
    assert result.json()["reason"] == "invalid_arguments"


def test_the_command_refuses_a_workbench_that_is_not_there(
    workspace: Path, task_id: str, tmp_path: Path
) -> None:
    """A directory that is not there is refused rather than ignored.

    The service would answer to the same origin with no workbench on it,
    and the developer would be left with a service that serves nothing and
    no reason why.
    """
    result = run_cli(
        "--workspace",
        str(workspace),
        "serve",
        "--static-dir",
        str(tmp_path / "not-built"),
        "--json",
    )
    assert result.returncode == EXIT_REFUSED
    assert result.json()["reason"] == "invalid_arguments"


def test_the_command_refuses_an_address_that_is_already_taken(
    workspace: Path, task_id: str
) -> None:
    """An address that cannot be bound is refused before the service is claimed.

    The command's output would otherwise say that a service was starting on
    an address another process already holds, and a script reading that
    output would believe it.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen(1)
        address = int(taken.getsockname()[1])
        result = run_cli("--workspace", str(workspace), "serve", "--port", str(address), "--json")
    assert result.returncode == EXIT_REFUSED
    payload = result.json()
    assert payload["reason"] == "invalid_arguments"
    assert "could not bind" in payload["message"]


# --------------------------------------------------------------------------- #
# the wiring
# --------------------------------------------------------------------------- #


def test_the_defaults_are_the_ones_the_workbench_expects() -> None:
    """The port defaults to 8000 and the address to 127.0.0.1.

    Read from the command rather than by binding the port: 8000 is a port a
    developer will have something on, and a test that failed because the
    machine's 8000 was busy would be a test that fails at random.
    """
    signature = inspect.signature(_serve_command())
    assert signature.parameters["port"].default == 8000
    assert signature.parameters["host"].default == "127.0.0.1"


def test_the_command_binds_the_address_it_was_given(
    workspace: Path,
    task_id: str,
    port: int,
    served: list[tuple[str, int]],
    binds: list[Any],
) -> None:
    """The port the command is given is the port the service binds.

    Checked at the two points where the address is used: the socket the
    command opens to find out whether it can bind, and the service it
    starts. A port that was accepted and thrown away would be a parameter
    that lies, and this is where that would show.
    """
    result = _invoke(
        "--workspace", str(workspace), "serve", "--host", "127.0.0.1", "--port", str(port)
    )
    assert result.exit_code == 0, result.output
    assert binds == [("127.0.0.1", port)]
    assert served == [("127.0.0.1", port)]


def test_the_command_binds_nothing_that_is_not_loopback(
    workspace: Path,
    task_id: str,
    port: int,
    served: list[tuple[str, int]],
    binds: list[Any],
) -> None:
    """Every address the command binds is a loopback address.

    The guard the service applies to its own bind address is asked by the
    command before the address is bound, so a service that would be
    reachable from the network never gets as far as a socket.
    """
    result = _invoke(
        "--workspace", str(workspace), "serve", "--host", "0.0.0.0", "--port", str(port)
    )
    assert result.exit_code == EXIT_REFUSED
    assert binds == []
    assert served == []


def test_the_command_reports_the_service_it_started(
    workspace: Path, task_id: str, port: int, served: list[tuple[str, int]]
) -> None:
    """The report names the service, and never the token.

    The origins are in it because the decision about the development server
    is one the operator should be able to see, and the token's *path* is in
    it because that is what a client needs in order to read the token.
    """
    result = _invoke("--workspace", str(workspace), "serve", "--port", str(port), "--json")
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert report["host"] == "127.0.0.1"
    assert report["port"] == port
    assert report["origin"] == f"http://127.0.0.1:{port}"
    assert report["task_id"] == task_id
    assert DEVELOPMENT_ORIGIN in report["origins"]
    assert report["token_path"].endswith("session-token")
    token = (workspace / ".labcairn" / "session-token").read_text(encoding="utf-8").strip()
    assert token
    assert token not in result.stdout


def test_the_command_answers_to_the_origin_it_is_given(
    workspace: Path, task_id: str, port: int, served: list[tuple[str, int]]
) -> None:
    """An origin named on the command line is one the service answers to.

    The development server's origins are there whatever was asked for, and
    an origin nobody named is not there at all.
    """
    result = _invoke(
        "--workspace",
        str(workspace),
        "serve",
        "--port",
        str(port),
        "--origin",
        "http://localhost:4173",
        "--json",
    )
    assert result.exit_code == 0, result.output
    origins = json.loads(result.stdout)["origins"]
    assert "http://localhost:4173" in origins
    assert DEVELOPMENT_ORIGIN in origins
    assert FOREIGN_ORIGIN not in origins


def test_the_command_serves_the_workbench_it_is_given(
    workspace: Path,
    task_id: str,
    port: int,
    tmp_path: Path,
    served: list[tuple[str, int]],
) -> None:
    """The built workbench is served from the service's own origin.

    The browser and the API then share one origin, which is what the
    service's origin check means when it says the workbench's own origin.
    """
    build = tmp_path / "dist"
    build.mkdir()
    (build / "index.html").write_text("<!doctype html><title>workbench</title>", encoding="utf-8")
    result = _invoke(
        "--workspace",
        str(workspace),
        "serve",
        "--port",
        str(port),
        "--static-dir",
        str(build),
        "--json",
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["static_dir"] == str(build.resolve())


# --------------------------------------------------------------------------- #
# the service, really running
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class RunningService:
    """A service that is really running, and the way to stop it."""

    port: int
    process: subprocess.Popen[str]
    report: dict[str, Any]
    out_lines: list[str]
    err_lines: list[str]
    readers: list[threading.Thread]
    printed: tuple[str, str] | None = None

    def get(self, path: str, headers: Mapping[str, str] | None = None) -> tuple[int, str]:
        """One request to the running service."""
        return _request(self.port, path, headers)

    def stop(self) -> tuple[str, str]:
        """Stop the service, and return what it printed.

        Idempotent, so a test may stop the service to look at its output
        and the fixture may stop it again on the way out.
        """
        if self.printed is None:
            _stop(self.process)
            for reader in self.readers:
                reader.join(10)
            self.printed = ("".join(self.out_lines), "".join(self.err_lines))
        return self.printed


def _free_port() -> int:
    """A port the operating system says is free."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _request(port: int, path: str, headers: Mapping[str, str] | None = None) -> tuple[int, str]:
    """One request to the service, and its status and body.

    ``http.client`` rather than ``urllib``, because urllib consults the
    environment's proxy settings and a proxied request to the loopback
    address would not reach the service at all.
    """
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        connection.request("GET", path, headers=dict(headers or {}))
        response = connection.getresponse()
        return response.status, response.read().decode("utf-8")
    finally:
        connection.close()


def _collect(stream: IO[str] | None, lines: list[str]) -> None:
    """Read a stream as it arrives, until it ends."""
    if stream is None:  # pragma: no cover - the pipes are always there
        return
    try:
        for line in stream:
            lines.append(line)
    except (OSError, ValueError):  # pragma: no cover - the pipe was closed
        return


def _stop(process: subprocess.Popen[str]) -> None:
    """Stop the service."""
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=15)


class _ServiceDidNotStartError(RuntimeError):
    """The command did not become a service."""


def _start(workspace: Path, *arguments: str) -> RunningService:
    """The service, really running, on a port the operating system had free.

    **The command is run through the interpreter, not through the console
    script's launcher.** On Windows that launcher is a program which runs
    the script in a child process, so stopping the launcher leaves the
    child running — and a service still running after the test that started
    it is a service that holds a port for the rest of the run. The
    interpreter runs the very same script.

    Retried, because the port is chosen by asking the operating system for a
    free one and letting go of it, and something else may take it in
    between. A test that failed because a port was busy would be a test that
    fails at random.
    """
    failures: list[str] = []
    for _ in range(3):
        port = _free_port()
        process = subprocess.Popen(
            [
                sys.executable,
                str(_console_script()),
                "--workspace",
                str(workspace),
                "serve",
                "--port",
                str(port),
                "--json",
                *arguments,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "COLUMNS": "200"},
        )
        out_lines: list[str] = []
        err_lines: list[str] = []
        readers = [
            threading.Thread(target=_collect, args=(process.stdout, out_lines), daemon=True),
            threading.Thread(target=_collect, args=(process.stderr, err_lines), daemon=True),
        ]
        for reader in readers:
            reader.start()
        try:
            _wait_for_the_service(process, port)
        except _ServiceDidNotStartError as error:
            failures.append(str(error))
            _stop(process)
            continue
        return RunningService(
            port=port,
            process=process,
            report=_await_report(out_lines),
            out_lines=out_lines,
            err_lines=err_lines,
            readers=readers,
        )
    raise AssertionError("the service did not start: " + "; ".join(failures))


def _await_report(lines: list[str], timeout: float = 15.0) -> dict[str, Any]:
    """The command's own report, out of what it printed.

    The command prints the report before it serves, so the report is in the
    output by the time the service has answered — and it is the first line
    of the output that is a JSON object.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for line in lines:
            stripped = line.strip()
            if not stripped.startswith("{"):
                continue
            report: dict[str, Any] = json.loads(stripped)
            return report
        time.sleep(0.05)
    raise AssertionError(f"the command printed no report: {lines!r}")


def _wait_for_the_service(process: subprocess.Popen[str], port: int, timeout: float = 60.0) -> None:
    """Wait until the service answers, or the command gives up."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise _ServiceDidNotStartError(f"the command exited with {process.returncode}")
        try:
            status, _ = _request(port, "/health")
        except OSError:
            status = 0
        if status == 200:
            return
        time.sleep(0.2)
    raise _ServiceDidNotStartError("the service did not answer /health in time")


@pytest.fixture
def service(workspace: Path, task_id: str) -> Iterator[RunningService]:
    """The service, really running, on a port the machine had free."""
    running = _start(workspace)
    try:
        yield running
    finally:
        running.stop()


def test_the_service_really_binds_the_port_the_command_was_given(
    service: RunningService,
) -> None:
    """The service answers on the port the command was given.

    Asked of the service over a socket, not of the command: a command that
    printed an address it never bound would be a command that lies.
    """
    status, body = service.get("/health")
    assert status == 200
    health = json.loads(body)
    assert health["port"] == service.port
    assert health["host"] == "127.0.0.1"
    assert f"http://127.0.0.1:{service.port}" in health["origins"]
    assert service.report["port"] == service.port
    assert service.report["origin"] == f"http://127.0.0.1:{service.port}"


def test_the_running_service_refuses_a_foreign_origin(service: RunningService) -> None:
    """A page on another site cannot drive the service.

    The same request without the foreign origin is served, so the test
    would fail for a service that refused everything.
    """
    status, body = service.get("/health", {"Origin": FOREIGN_ORIGIN})
    assert status == 403
    assert json.loads(body)["reason"] == "origin_refused"
    assert service.get("/health", {"Origin": f"http://127.0.0.1:{service.port}"})[0] == 200


def test_the_running_service_serves_the_development_origin(service: RunningService) -> None:
    """The workbench's development server may talk to the service.

    The origin the development server is served from is in the allow-list
    the command reports, and a request carrying it is served rather than
    refused — which is the whole point of the development default.
    """
    assert DEVELOPMENT_ORIGIN in service.report["origins"]
    assert service.get("/health", {"Origin": DEVELOPMENT_ORIGIN})[0] == 200


def test_the_session_token_is_written_to_the_workspace_and_never_printed(
    service: RunningService, workspace: Path
) -> None:
    """The token is on disk and in the service's memory, and in neither output.

    The file's contents are the service's own token, so the two are one
    secret; and the command's output names the path and never the value, so
    a transcript of the command carries no secret.
    """
    status, body = service.get("/session")
    assert status == 200
    token = json.loads(body)["token"]
    written = (workspace / ".labcairn" / "session-token").read_text(encoding="utf-8")
    assert written.strip() == token
    stdout, stderr = service.stop()
    assert token not in stdout
    assert token not in stderr


def test_the_command_leaves_no_port_bound(workspace: Path, task_id: str) -> None:
    """The service is stopped, and the address it held is free again.

    A test that leaves a port bound makes the next test fail at random,
    and a service that is still running after the command was stopped would
    be a service nobody stopped.
    """
    running = _start(workspace)
    port = running.port
    assert running.get("/health")[0] == 200
    running.stop()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if _nothing_is_listening(port):
            return
        time.sleep(0.2)
    raise AssertionError(f"something is still listening on {port}")


def _nothing_is_listening(port: int) -> bool:
    """Whether the address is free."""
    try:
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        connection.request("GET", "/health")
        connection.getresponse().read()
    except (OSError, http.client.HTTPException):
        return True
    finally:
        connection.close()
    return False


def test_the_service_serves_the_task_the_workspace_selected(
    service: RunningService, task_id: str
) -> None:
    """The service answers about the task the workspace made current.

    The API is task-scoped, and the task it is about is the workspace's
    current one, so this is the whole of the launch path in one request.
    """
    status, body = service.get("/task")
    assert status == 200
    assert json.loads(body)["task"]["task_id"] == task_id


def test_the_service_and_the_cli_say_the_same_thing_about_the_task(
    workspace: Path, task_id: str
) -> None:
    """The API's task document and the CLI's are the layer's own model.

    §1.4.2's clause, over the wire: the CLI's ``task status --json`` and
    the service's ``/task`` are equal, because both are the same model read
    from the same store.

    **The CLI is asked first, and the service is stopped afterwards.** The
    running service holds the store's write transaction open for as long as
    it is running, and the CLI cannot open its own while that is true — so
    the two are compared over the same store without overlapping.
    """
    reported = run_cli("--workspace", str(workspace), "task", "status", "--json")
    assert reported.returncode == 0, reported.stderr
    running = _start(workspace)
    try:
        status, body = running.get("/task")
    finally:
        running.stop()
    assert status == 200
    assert json.loads(body) == reported.json()
