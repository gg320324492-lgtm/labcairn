"""The G1 helper: the service and the browser, started and stopped by a helper.

**Why this file exists.** `docs/plans/PHASE_3-work-orders.md` §4.1 states four
rules for the real-browser baseline, and three of them are about *how the run is
arranged* rather than about what it asserts:

* the service and the browser are started and stopped by a helper, in a temporary
  workspace and on a port the operating system chose, never a fixed 8000;
* the temporary workspace is outside the repository;
* the environment the run used — driver version, browser and channel, the browser
  cache in force, the platform — is recorded by the run that used it.

A rule about how a run is arranged is a rule too, and a rule that is stated in a
plan and carried in nobody's code is a rule that the next run quietly drops. So
the arrangement lives here, once, and `tests/test_workbench_serve_helper.py`
watches that it holds — including the parts that only fail on *this* machine,
like the browser-cache pin below.

**The browser-cache pin is the reason this file is not just a subprocess wrapper.**
`PLAYWRIGHT_BROWSERS_PATH` is set at both User and Machine scope on this machine to
another project's cache (`G1-ENV-EVIDENCE-PREP-2026-11-08.md` §1.3). A driver that
inherits it downloads into, or launches from, a directory that belongs to a
different project and is pinned to a different driver's browser revision. The pin
is therefore not a nicety: it is the difference between measuring this project's
browser and measuring somebody else's.

**No product code lives here.** The helper starts the console script a developer
types; every guard it enforces is the product's own guard, imported rather than
restated, so that the helper cannot drift into being a second policy nobody
maintains.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from labcairn.api.bind import ensure_loopback, own_origin

#: The repository's own root, so that "outside the repository" is a measured
#: relation and not a phrase.
REPO_ROOT = Path(__file__).resolve().parent.parent

#: The build the browser loads. ``web/dist`` is git-ignored: it is produced by
#: ``pnpm build`` from ``web/pnpm-lock.yaml``, and §4.2 asks that the run name the
#: build it used rather than assume one was there.
WEB_DIST_DIR = REPO_ROOT / "web" / "dist"

#: The system-browser channel the owner's decision of 2026-11-08 points at.
#: ``msedge`` is Edge's own install; nothing is downloaded for it.
BROWSER_CHANNEL = "msedge"

#: Headless because the baseline runs beside the person's own browser sessions.
#: The preparation record §1.2 notes that an ``msedge --version`` probe joined a
#: running session; a baseline must not attach to the user's profiles.
BROWSER_HEADLESS = True

#: How long the helper waits for the service to answer before it says the service
#: did not start. It is a ceiling on the *wait*, not a claim that the service is
#: slow: the helper reports what the service printed when the ceiling is reached.
READY_TIMEOUT_SECONDS = 60.0


#: The browser cache this machine carried when the process started, before this file
#: pinned its own. Read at import for exactly that reason: a value read later is the
#: pin, and a record that compares a pin with itself shows nothing. On this machine it
#: is another project's cache — `E:\microbubble-agent\data\ms-playwright`, per
#: `G1-ENV-EVIDENCE-PREP-2026-11-08.md` §1.3.
INHERITED_BROWSER_CACHE_PATH: str | None = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")


def browser_cache_dir() -> Path:
    """The browser cache this project owns, and uses, and never inherits.

    **The rule.** ``PLAYWRIGHT_BROWSERS_PATH`` is set for every process on this
    machine to ``E:\\microbubble-agent\\data\\ms-playwright`` — another project's
    cache. Inheriting it would make a "Playwright baseline" a measurement of that
    project's browsers, which is the shared-environment failure this repository has
    been burned by twice with virtualenvs.

    **How the replacement is chosen, so it is the same rule on any machine.**
    ``LABCAIRN_BROWSER_CACHE_DIR`` wins when the owner names one. Otherwise the
    cache sits under the system temp directory the project already pins outside
    the repository (``CLAUDE.md``, *Running the suite*), because the project's own
    guard already refuses a workspace that is inside a repository — a browser cache
    written into the checkout would be an untracked directory the checkout's
    cleanliness depends on.
    """
    named = os.environ.get("LABCAIRN_BROWSER_CACHE_DIR")
    if named:
        return Path(named).expanduser().resolve()
    return (Path(tempfile.gettempdir()) / "labcairn-ms-playwright").resolve()


def pin_browser_cache() -> tuple[Path, str | None]:
    """Put the project's own cache in force, and report what the machine carried.

    :returns: the path now in force, and the value this process inherited **before
        anything in it was pinned**. The second half is not decoration: §4.2's row asks
        for the ``PLAYWRIGHT_BROWSERS_PATH`` in force, and a record naming only the
        replacement cannot show that an inherited one was overridden. It is read once,
        at import, because a second call would otherwise report the first call's own
        pin as though it had been the machine's value.
    """
    pinned = browser_cache_dir()
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(pinned)
    return pinned, INHERITED_BROWSER_CACHE_PATH


@dataclass(frozen=True)
class CliResult:
    """What the console script produced."""

    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    def json(self) -> Any:
        """The stdout, parsed as the JSON the ``--json`` form prints."""
        return json.loads(self.stdout)


def console_script() -> Path:
    """The script a developer types, as this interpreter would find it.

    The tests drive the CLI through the installed launcher, not through
    ``python -m``, because the launcher is what a person runs — and because a
    copied virtualenv that shares somebody else's launcher measures that
    somebody else's source tree (``CLAUDE.md``, *A copied virtualenv is not a
    virtualenv of its own*). Resolving it from ``sys.executable`` is what makes
    "the script of the environment running these tests" a fact rather than a hope.
    """
    name = "labcairn.exe" if os.name == "nt" else "labcairn"
    return Path(sys.executable).parent / name


def run_cli(*args: str, timeout: float = 90.0) -> CliResult:
    """Run the console script with the width and encoding the CLI tests use.

    ``COLUMNS=200`` is not cosmetics. The CLI renders its refusals through Rich,
    which wraps at the terminal width, and a wrap that falls inside a phrase
    truncates it — so an assertion about that phrase would fail for a reason that
    has nothing to do with the property under test.
    """
    script = console_script()
    if not script.is_file():
        raise AssertionError(f"the console script is not installed at {script}")
    environment = {**os.environ, "COLUMNS": "200", "PYTHONIOENCODING": "utf-8"}
    completed = subprocess.run(
        [str(script), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=timeout,
        check=False,
    )
    return CliResult(
        args=tuple(args),
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )


def free_loopback_port() -> int:
    """A port the operating system says is free, on the loopback address.

    §4.1 forbids a fixed 8000 for two reasons the plan spells out: the developer's
    own service may be listening there, and a test that shares a port with it
    passes or fails for the wrong reason. Binding port 0 and reading back what the
    kernel chose is the only way to ask.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


@dataclass(frozen=True)
class HttpReply:
    """One answer on the socket, kept small."""

    status: int
    body: str
    headers: dict[str, str]

    def json(self) -> Any:
        """The body, parsed as JSON."""
        return json.loads(self.body)


class ServedWorkbench:
    """The service, running, on a port nobody chose in advance.

    The helper owns a subprocess: the same console script a developer types, with
    the same ``serve`` command, in a temporary workspace. It is not the in-process
    ASGI transport the earlier workbench witness uses — the point of this one is
    that a socket is opened and something on the other end of it is the product.
    """

    def __init__(
        self,
        *,
        workspace: Path,
        host: str,
        port: int,
        dist_dir: Path | None,
        process: subprocess.Popen[str],
        log_path: Path,
    ) -> None:
        self.workspace = workspace
        self.host = ensure_loopback(host)
        self.port = port
        self.origin = own_origin(host, port)
        self.dist_dir = dist_dir
        self._process = process
        #: The service's own stdout and stderr, kept in a file rather than a pipe:
        #: a pipe nobody reads fills up and blocks the writer, which is a failure
        #: whose cause is the harness and not the product.
        self.log_path = log_path

    # -- the workspace's own paths ---------------------------------------- #

    @property
    def session_token_path(self) -> Path:
        """Where the service wrote the token it mints."""
        return self.workspace / ".labcairn" / "session-token"

    def session_token(self) -> str:
        """The token file's contents, as the service wrote them."""
        return self.session_token_path.read_text(encoding="utf-8").strip()

    # -- talking to it ----------------------------------------------------- #

    def request(
        self,
        path: str,
        *,
        origin: str | None = None,
        token: bool = False,
        body: str | None = None,
        timeout: float = 20.0,
    ) -> HttpReply:
        """One request to the service over its socket.

        The ``Origin`` is given because the guard reads it: a same-origin browser
        GET carries no ``Origin`` at all, so a request that *names* a foreign one is
        the control that shows the guard is there.
        """
        headers = {"Accept": "application/json"}
        if origin is not None:
            headers["Origin"] = origin
        if token:
            headers["Authorization"] = f"Bearer {self.session_token()}"
        payload = None
        if body is not None:
            payload = body.encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{self.origin}{path}",
            data=payload,
            headers=headers,
            method="GET" if payload is None else "POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return HttpReply(
                    status=int(response.status),
                    body=response.read().decode("utf-8", errors="replace"),
                    headers={str(k): str(v) for k, v in response.headers.items()},
                )
        except urllib.error.HTTPError as error:
            return HttpReply(
                status=int(error.code),
                body=error.read().decode("utf-8", errors="replace"),
                headers={str(k): str(v) for k, v in error.headers.items()},
            )

    def get(self, path: str, **kwargs: Any) -> HttpReply:
        """A ``GET`` with no ``Origin``, which is what a same-origin browser sends."""
        return self.request(path, **kwargs)

    def post(self, path: str, payload: dict[str, Any], **kwargs: Any) -> HttpReply:
        """A change, from the service's own origin, with the session token presented."""
        return self.request(
            path,
            origin=self.origin,
            token=True,
            body=json.dumps(payload),
            **kwargs,
        )

    # -- ending it --------------------------------------------------------- #

    def output(self) -> str:
        """Everything the service printed, which is what a failed start is read from."""
        try:
            return self.log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def stop(self, *, timeout: float = 20.0) -> StopOutcome:
        """End the service, and prove the *whole of it* ended.

        The property is not "a call was made". It is that no process is left holding
        the workspace's database, the port, or a store write lock into the next test —
        the shape of failure this project has been burned by twice, where a stopped
        test's service kept running for a while and the next run measured the wrong
        thing for a reason nothing named.

        **Asked, then forced, and the difference is recorded.** The helper starts the
        service in its own process group and asks that group to stop, which on Windows
        is ``CTRL_BREAK_EVENT`` and elsewhere ``SIGTERM``. If the service ignores the
        asking, the helper ends the tree by force and says so: a stop that had to be
        forced is a fact about the service, and a helper that hid it would report a
        clean shutdown that never happened.
        """
        self._ask_to_stop()
        code, timed_out = self._wait_for_exit(timeout=timeout)
        forced = False
        if timed_out:
            code, still_running = self._force_the_tree(timeout=timeout)
            forced = True
            if still_running:
                raise AssertionError(
                    f"the service's process group was asked to stop and then ended by "
                    f"force, and pid {self._process.pid} is still running. Service "
                    f"output:\n{self.output()}"
                )
        if self.accepts_connections():
            raise AssertionError(
                f"the service still answers on {self.origin} after its process group was "
                f"asked to stop and then ended by force (exit code {code}). A service "
                f"that outlives the run that started it holds the workspace, the port "
                f"and the store's write lock.\n--- service output ---\n{self.output()}"
            )
        return StopOutcome(exit_code=int(code), forced=forced, stopped_at=time.time())

    def _ask_to_stop(self) -> None:
        """Ask the service's own process group to stop."""
        if _this_platform_is_windows():
            self._process.send_signal(_windows_group_stop_signal())
        else:
            self._process.terminate()

    def _wait_for_exit(self, *, timeout: float) -> tuple[int, bool]:
        """Wait for the asked stop, and report whether it had to be forced."""
        try:
            return int(self._process.wait(timeout=timeout)), False
        except subprocess.TimeoutExpired:
            return -1, True

    def _force_the_tree(self, *, timeout: float) -> tuple[int, bool]:
        """End the process group by force, and report whether even that failed."""
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(self._process.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                check=False,
            )
        else:
            self._process.kill()
        try:
            return int(self._process.wait(timeout=timeout)), False
        except subprocess.TimeoutExpired:
            return -1, True

    def accepts_connections(self) -> bool:
        """Whether something is still answering on the service's port.

        Binding the port is the wrong question — a closed listener leaves the port
        in a state where a bind may fail for reasons that have nothing to do with
        the service. Asking whether a connection is accepted and answered is the
        question that matches the claim.
        """
        try:
            with socket.create_connection((self.host, self.port), timeout=2.0):
                return True
        except OSError:
            return False

    def alive(self) -> bool:
        """Whether the service's launcher process is still running."""
        return self._process.poll() is None


@dataclass(frozen=True)
class StopOutcome:
    """How the service ended, as opposed to whether the helper tried to end it."""

    exit_code: int
    forced: bool
    stopped_at: float


def start_served_workbench(
    *,
    workspace: Path,
    dist_dir: Path | None = None,
    host: str = "127.0.0.1",
    port: int | None = None,
) -> ServedWorkbench:
    """Start the real service in a temporary workspace, and wait for it to answer.

    **The bind address is refused here, by the product's own guard, before anything
    is started.** The helper does not restate the loopback rule — it calls
    :func:`labcairn.api.bind.ensure_loopback`, the same function the command and
    the service call. A helper with its own copy of the rule would be a second rule
    nobody keeps in step.

    :param workspace: the temporary workspace the service is bound to. It must be
        outside the repository; the caller passes a pytest temporary directory, and
        ``tests/test_workbench_serve_helper.py`` watches that the workspace the CLI
        made really is outside the checkout.
    :param dist_dir: the built workbench to serve from the service's own origin.
    :param host: the address to bind, and it is refused unless it is loopback.
    :param port: the port to bind, or ``None`` to take one the operating system
        chose. The default is deliberately *not* the 8000 ``labcairn serve`` falls
        back to, which is where a developer's own service is listening.
    :raises AssertionError: the service did not answer within
        :data:`READY_TIMEOUT_SECONDS`, with everything it printed attached.
    """
    ensure_loopback(host)
    _refuse_a_workspace_inside_the_repository(workspace)
    chosen = free_loopback_port() if port is None else port
    arguments = [
        "--workspace",
        str(workspace),
        "serve",
        "--host",
        host,
        "--port",
        str(chosen),
        "--json",
    ]
    if dist_dir is not None:
        arguments += ["--static-dir", str(dist_dir)]

    log_path = workspace.parent / f"serve-{chosen}.log"
    process = _spawn([str(console_script()), *arguments], log_path)

    served = ServedWorkbench(
        workspace=workspace,
        host=host,
        port=chosen,
        dist_dir=dist_dir,
        process=process,
        log_path=log_path,
    )
    if not _wait_until_ready(served, process):
        raise AssertionError(
            f"the service did not answer GET /health within {READY_TIMEOUT_SECONDS}s at "
            f"{served.origin}. The console script was run as: {arguments}\n"
            f"--- service output ---\n{served.output()}"
        )
    return served


def _spawn(arguments: list[str], log_path: Path) -> subprocess.Popen[str]:
    """Start the console script in its own process group, with its output in a file.

    This is the one place the helper starts a process, so that
    ``tests/test_workbench_serve_helper.py`` can watch the claim that a refusal
    happens **before** anything is started — a guard that runs after the spawn would
    leave a service listening on a port the test never meant to open.
    """
    log_file = log_path.open("w+", encoding="utf-8")
    try:
        return subprocess.Popen(
            arguments,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "COLUMNS": "200", "PYTHONIOENCODING": "utf-8"},
            # Its own process group: the stop is addressed to the group, so a service
            # that spawned something cannot keep the port open after the run that
            # started it says it is finished.
            creationflags=_windows_process_group_flags(),
        )
    finally:
        log_file.close()


def _this_platform_is_windows() -> bool:
    """Whether this host is Windows, asked through a call.

    **Compared through a function so no checker narrows it away.** A checker
    running on Linux constant-folds ``os.name`` and judges the Windows-only
    attribute accesses unreachable; routing the question through a call
    keeps the runtime behaviour identical while every platform's checker
    sees the same reachable body.
    """
    return os.name == "nt"


def _windows_group_stop_signal() -> signal.Signals:
    """The signal a Windows process group is asked to stop with.

    See :func:`_this_platform_is_windows` for why the Windows-only read
    lives in a helper behind a call. ``CTRL_BREAK_EVENT`` is a Windows-only
    constant, so its use site carries the project's scoped ignore.
    """
    signal_value: int = signal.CTRL_BREAK_EVENT  # type: ignore[attr-defined,unused-ignore]
    return signal.Signals(signal_value)


def _windows_process_group_flags() -> int:
    """The creation flags that put the service in its own process group.

    See :func:`_this_platform_is_windows` for why the Windows-only read
    lives in a helper behind a call.
    """
    flags: int = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined,unused-ignore]
    return flags


def _refuse_a_workspace_inside_the_repository(workspace: Path) -> None:
    """Refuse to run the baseline in the checkout it is being run from.

    **Why the helper says this and the product does not.** ``labcairn init`` accepts
    a workspace inside a repository — measured 2026-11-08, ``init`` into
    ``<checkout>/probe-inside-repo`` succeeded with exit code 0 and created the
    directory. The rule §4.1 states is a rule about the *baseline's* arrangement, so
    it is the baseline's helper that holds it, and
    ``tests/test_workbench_serve_helper.py`` watches that it does. The reason is the
    one ``CLAUDE.md`` gives for the base temp directory: a workspace inside the
    checkout makes the run depend on the tree it runs in and leaves the checkout
    dirty — and a run whose outputs are inside the tree under review is not a
    measurement of that tree.
    """
    resolved = workspace.expanduser().resolve()
    if resolved == REPO_ROOT or REPO_ROOT in resolved.parents:
        raise AssertionError(
            f"the baseline will not run in the repository it is run from: {resolved} is "
            f"inside {REPO_ROOT}. §4.1 asks for a temporary workspace outside the "
            "repository, and `labcairn init` does not refuse one — measured on "
            "2026-11-08, init into the checkout succeeded."
        )


def _wait_until_ready(served: ServedWorkbench, process: subprocess.Popen[str]) -> bool:
    """Poll the one endpoint that needs no token, until it answers or time runs out."""
    deadline = time.monotonic() + READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            return False
        try:
            if served.get("/health", timeout=2.0).status == 200:
                return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.25)
    return False


@dataclass(frozen=True)
class BrowserLaunch:
    """The browser facts §4.2 asks a run to record, taken from the run itself."""

    driver_version: str
    channel: str
    browser_version: str
    cache_in_force: str
    cache_replaced: str | None
    driver_default_cache: str


def start_playwright() -> Any:
    """Start the Playwright driver owned by this project's environment.

    **The import is dynamic on purpose.** Playwright is not a declared dependency
    of the product and is not installed on a CI runner; a top-level
    ``from playwright.sync_api import ...`` would make ``mypy --strict`` fail on a
    runner that has no such module — a lint red whose cause is the witness file and
    not the change under review. The driver is imported where it is used, and the
    test that needs it skips when it is not there, with the reason named.

    **The pin happens here, before the driver starts, and the order is the point.**
    The driver reads ``PLAYWRIGHT_BROWSERS_PATH`` when it starts, not when a browser
    is asked for: pinning it after ``start()`` leaves the driver resolved against
    whatever the machine carries. That was measured on 2026-11-08 — with the pin
    applied after the driver was started, the driver's own answer for where its
    browser lives was the inherited directory, and a baseline run would have been a
    measurement of another project's browser while looking entirely normal.
    """
    pin_browser_cache()
    return importlib.import_module("playwright.sync_api").sync_playwright().start()


def launch_workbench_browser(playwright: Any) -> tuple[Any, BrowserLaunch]:
    """Launch the browser the baseline drives, and record what it actually was.

    The channel is the owner's decision: the system Edge, not a downloaded build.
    Nothing here downloads a browser, and the cache pin is installed *before* the
    launch so that the driver resolves its own defaults against the project's path.
    """
    pinned, replaced = pin_browser_cache()
    browser = playwright.chromium.launch(channel=BROWSER_CHANNEL, headless=BROWSER_HEADLESS)
    facts = BrowserLaunch(
        driver_version=importlib.metadata.version("playwright"),
        channel=BROWSER_CHANNEL,
        browser_version=str(browser.version),
        cache_in_force=str(pinned),
        cache_replaced=replaced,
        driver_default_cache=str(playwright.chromium.executable_path),
    )
    return browser, facts


__all__ = [
    "BROWSER_CHANNEL",
    "REPO_ROOT",
    "WEB_DIST_DIR",
    "BrowserLaunch",
    "CliResult",
    "HttpReply",
    "ServedWorkbench",
    "StopOutcome",
    "browser_cache_dir",
    "console_script",
    "free_loopback_port",
    "launch_workbench_browser",
    "pin_browser_cache",
    "run_cli",
    "start_playwright",
    "start_served_workbench",
]
