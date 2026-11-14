"""The baseline's arrangement, watched: a service started by a helper, on a socket.

**What this file is about.** `docs/plans/PHASE_3-work-orders.md` §4.1 lists four
things the real-browser baseline must arrange before it asserts anything: a helper
starts and stops the service, in a temporary workspace, on a port the operating
system chose and never a fixed 8000; the workspace is outside the repository; the
environment is recorded. Those are not assertions about the product's behaviour —
they are conditions under which an assertion about the product would mean something.
A plan can state them and a run can silently drop them, and then the run's results
are about somebody's other service on port 8000 or about the checkout the run was
measuring. So each condition is witnessed here, against the helper the baseline uses
(`tests/workbench_serve_support.py`).

**What is *not* in this file.** What the screen shows, which is
`tests/test_workbench_real_browser.py`. And the guard the CLI itself applies to a
non-loopback bind, which `tests/test_cli_serve_bind_refusal.py` already witnesses —
what is witnessed here is that the *helper* asks for a loopback bind in the first
place, and asks before it starts anything.

**The socket is the point.** `tests/test_workbench_live_service.py` drives the
service through an in-process ASGI transport, which opens no socket. That was the
right first step and it is why its comparisons are trustworthy. It is not a wire: the
origin guard, the static mount and the session token all behave through a real
connection, and this file is where they are read through one.

**The last test is a measured gap, not an aspiration.** It records what the served
service actually does with an event stream it was never given a source for — a
refusal on the JSON read and a stream that opens with 200 and dies with nothing in
it — because §4.7's second deliverable is the list of boundaries the run did not
cover, with an evidence address for each.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
import workbench_serve_support as support
from workbench_serve_support import (
    WEB_DIST_DIR,
    ServedWorkbench,
    free_loopback_port,
    run_cli,
    start_served_workbench,
)

from labcairn.api.bind import BindRefusedError
from labcairn.cli.commands import EXIT_REFUSED

pytestmark = pytest.mark.e2e

#: This repository's root, from this file's own location — the same derivation
#: `workbench_serve_support.REPO_ROOT` uses, kept separate so this file can read
#: another test file's source without importing it.
REPO_ROOT_FOR_HELPER = Path(__file__).resolve().parent.parent

#: The port ``labcairn serve`` falls back to, and the port the development server
#: uses. §4.1 forbids the first for a baseline; the second belongs to a process this
#: suite does not own.
DEFAULT_SERVE_PORT = 8000
DEVELOPMENT_SERVER_PORT = 5173

#: An origin that is not the service's own and not the development server's.
FOREIGN_ORIGIN = "http://labcairn.example.invalid"


def _make_workspace(root: Path, *tasks: tuple[str, str, str]) -> Path:
    """A workspace and its tasks, made by the CLI a person would use."""
    made = run_cli("--workspace", str(root), "init")
    assert made.returncode == 0, f"labcairn init refused: {made.stderr}"
    for title, objective, criterion in tasks:
        created = run_cli(
            "--workspace",
            str(root),
            "task",
            "create",
            "--title",
            title,
            "--objective",
            objective,
            "--criterion",
            criterion,
            "--json",
        )
        assert created.returncode == 0, f"labcairn task create refused: {created.stderr}"
    return root


#: The read-only tests in this file read the same service, so one service is shared
#: and only the tests that *change* something — a stop, a second port, a refused
#: build — build their own. Starting the service costs the console script's whole
#: import chain, and a file that paid it once per test would spend a minute of the
#: suite for no added witness.
TASK: tuple[str, str, str] = (
    "Baseline task",
    "What the served service answers.",
    "Each read answered.",
)


def _fresh_service(root: Path, *, dist_dir: Path | None = None) -> ServedWorkbench:
    """One service, in a directory of its own, in a workspace the CLI made."""
    workspace = _make_workspace(root / "workspace", TASK)
    return start_served_workbench(workspace=workspace, dist_dir=dist_dir)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """One workspace, one task, made through the console script."""
    return _make_workspace(tmp_path / "workspace", TASK)


@pytest.fixture(scope="module")
def served(tmp_path_factory: pytest.TempPathFactory) -> Iterator[ServedWorkbench]:
    """The service, running, and stopped at the end whatever the test asserted."""
    service = _fresh_service(tmp_path_factory.mktemp("served"))
    try:
        yield service
    finally:
        service.stop()


# --------------------------------------------------------------------------- #
# the helper starts the service, and ends it
# --------------------------------------------------------------------------- #


def test_the_helper_starts_the_console_script_and_the_service_answers_on_a_socket(
    served: ServedWorkbench,
) -> None:
    """The service a helper started is the service a person would have started."""
    health = served.get("/health")
    assert health.status == 200, health.body
    body = health.json()
    assert body["host"] == "127.0.0.1"
    assert body["port"] == served.port
    assert body["status"] == "ok"
    assert served.origin == f"http://127.0.0.1:{served.port}"


def test_the_helper_stops_the_service_when_asked_and_the_port_stops_answering(
    tmp_path: Path,
) -> None:
    """Stopping is a fact about the socket, not about a call the helper made.

    A service that kept running would hold the workspace's database and a store write
    lock into the next test. This project has already lost measurements that way
    twice, both times to a process that outlived the run that started it.
    """
    service = _fresh_service(tmp_path)
    assert service.alive()
    assert service.accepts_connections(), f"nothing was answering on {service.origin} while it ran"

    outcome = service.stop()

    assert outcome.forced is False, (
        "the service did not stop when its process group was asked to; the helper had "
        f"to end it by force. Service output:\n{service.output()}"
    )
    assert not service.alive()
    assert not service.accepts_connections(), f"something still answers on {service.origin}"


def test_the_port_is_one_the_operating_system_chose_and_not_the_default(
    workspace: Path,
) -> None:
    """§4.1: never a fixed 8000, and not the development server's port either."""
    first = start_served_workbench(workspace=workspace)
    first_port = first.port
    first.stop()

    second = start_served_workbench(workspace=workspace)
    second_port = second.port
    second.stop()

    assert first_port != DEFAULT_SERVE_PORT, (
        "the baseline took the port a developer's own service uses"
    )
    assert first_port != DEVELOPMENT_SERVER_PORT
    assert second_port != first_port, (
        "two runs of the helper took the same port, so one of them was not asking the "
        "operating system for one"
    )


def test_the_helper_refuses_a_bind_that_is_not_loopback_before_it_starts_anything(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The refusal is before the spawn, so nothing is left listening.

    The guard the helper uses is the product's own — :func:`ensure_loopback`, the
    function ``labcairn serve`` and the service both call — so the helper cannot drift
    into a second copy of the rule that nobody keeps in step. The witness is that no
    process was started to find out.
    """
    started: list[list[str]] = []

    def record_spawn(arguments: list[str], log_path: Path) -> None:
        started.append(arguments)
        raise AssertionError("the helper started a process it should have refused first")

    monkeypatch.setattr(support, "_spawn", record_spawn)

    with pytest.raises(BindRefusedError):
        start_served_workbench(workspace=workspace, host="0.0.0.0")

    assert started == [], f"the helper started the console script anyway: {started}"


def test_the_helper_refuses_to_run_in_the_repository_it_is_run_from(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    repo_root: Path,
) -> None:
    """The helper refuses a workspace inside the checkout, which is the only thing that does.

    **Measured, not assumed.** ``labcairn init`` does *not* refuse a workspace inside
    a repository: on 2026-11-08 an ``init`` into ``<checkout>/probe-inside-repo``
    returned exit code 0 and created the directory. §4.1's rule is about the
    baseline's arrangement, so the helper holds it and this test is its witness. The
    reason is the one CLAUDE.md gives for the base temp directory — a run whose
    workspace is inside the tree under review makes the run depend on that tree and
    leaves the checkout dirty.
    """
    started: list[list[str]] = []

    def record_spawn(arguments: list[str], log_path: Path) -> None:
        started.append(arguments)
        raise AssertionError("the helper started a service inside the repository")

    monkeypatch.setattr(support, "_spawn", record_spawn)

    inside = repo_root / "baseline-workspace-inside-the-checkout"
    with pytest.raises(AssertionError, match="will not run in the repository it is run from"):
        start_served_workbench(workspace=inside)

    assert started == []
    assert not inside.exists(), "the helper created the directory it then refused to use"


def test_the_workspace_the_service_writes_into_is_outside_the_repository(
    served: ServedWorkbench,
    repo_root: Path,
) -> None:
    """The workspace is outside the checkout, and the service wrote its token there."""
    workspace = served.workspace.resolve()
    assert repo_root not in workspace.parents and workspace != repo_root, (
        f"the baseline ran in {workspace}, which is inside {repo_root}"
    )
    assert served.session_token_path.is_file()


# --------------------------------------------------------------------------- #
# the build, served from the service's own origin
# --------------------------------------------------------------------------- #


def _require_build() -> None:
    """Skip with the missing piece named, rather than pass on an absent build."""
    if not WEB_DIST_DIR.is_dir():
        pytest.skip(
            f"{WEB_DIST_DIR} does not exist; the build is made by `pnpm install "
            "--frozen-lockfile && pnpm build` in web/, and it is git-ignored. §4.2 asks "
            "a run to name the build it used, not to assume one was there."
        )


@pytest.fixture(scope="module")
def served_with_build(tmp_path_factory: pytest.TempPathFactory) -> Iterator[ServedWorkbench]:
    """The service, with the built workbench on its own origin."""
    _require_build()
    service = _fresh_service(tmp_path_factory.mktemp("served-build"), dist_dir=WEB_DIST_DIR)
    try:
        yield service
    finally:
        service.stop()


def test_the_service_serves_the_built_page_at_its_own_origin(
    served_with_build: ServedWorkbench,
) -> None:
    """§4.4 row 3 / §4.6 row 3: the build and the API on one origin."""
    page = served_with_build.get("/")
    assert page.status == 200, page.body
    assert "text/html" in page.headers.get("content-type", "")
    assert page.body == (WEB_DIST_DIR / "index.html").read_text(encoding="utf-8")
    assert '<div id="root">' in page.body

    asset = re.search(r'src="(/assets/[^"]+\.js)"', page.body)
    assert asset is not None, f"the served page names no built script: {page.body[:400]}"
    served_asset = served_with_build.get(asset.group(1))
    assert served_asset.status == 200, served_asset.body[:400]
    assert "javascript" in served_asset.headers.get("content-type", "")
    on_disk = WEB_DIST_DIR / asset.group(1).removeprefix("/")
    assert served_asset.body == on_disk.read_text(encoding="utf-8"), (
        "the page the service served is not the build in the tree it was served from"
    )


def test_the_api_still_answers_on_the_origin_that_serves_the_build(
    served_with_build: ServedWorkbench,
) -> None:
    """Mounting the build at ``/`` must not swallow the API under it.

    The static mount is at the root, and every API path begins at the root too. A
    service that served the build *instead of* ``/task`` would still look like a
    working page: the client would get HTML with a 200 and the panels would show
    nothing, and the failure would read as an empty workspace.
    """
    for path in ("/task", "/tasks", "/plan", "/steps", "/sources", "/artifacts", "/session"):
        reply = served_with_build.get(path)
        assert reply.status == 200, f"{path} -> {reply.status}: {reply.body[:200]}"
        assert "text/html" not in reply.headers.get("content-type", ""), (
            f"{path} was answered with the built page rather than with the API"
        )


def test_a_build_that_is_not_there_is_refused_rather_than_ignored(workspace: Path) -> None:
    """``--static-dir`` naming nothing is a refusal, not a service with nothing on it."""
    result = run_cli(
        "--workspace",
        str(workspace),
        "serve",
        "--port",
        str(free_loopback_port()),
        "--static-dir",
        str(workspace / "no-such-build"),
    )
    assert result.returncode == EXIT_REFUSED, (
        f"exit {result.returncode}: {result.stdout} {result.stderr}"
    )
    assert "is not a directory" in result.stderr, result.stderr


# --------------------------------------------------------------------------- #
# the session token, over a real socket
# --------------------------------------------------------------------------- #


def test_the_session_token_is_read_at_the_service_s_own_origin(served: ServedWorkbench) -> None:
    """§4.4 row 4 / §4.6 row 11, at the wire rather than in process."""
    reply = served.get("/session")
    assert reply.status == 200, reply.body
    body = reply.json()
    assert body["token"] == served.session_token()
    assert Path(body["path"]) == served.session_token_path

    with_own_origin = served.request("/session", origin=served.origin)
    assert with_own_origin.status == 200, with_own_origin.body


def test_a_foreign_origin_is_refused_on_the_socket_that_serves_the_build(
    served: ServedWorkbench,
) -> None:
    """The origin guard is real over a socket, and the refusal is a refusal.

    The control is the same request without the foreign ``Origin``, which the test
    above shows is served: what refused this one is the origin.
    """
    reply = served.request("/session", origin=FOREIGN_ORIGIN)
    assert reply.status == 403, f"a foreign origin was served: {reply.status} {reply.body[:200]}"
    assert reply.json()["reason"] == "origin_refused", reply.body


def test_the_development_server_s_origins_are_answered_to_by_default(
    served: ServedWorkbench,
) -> None:
    """The widening §4 names is the command's own default, and it is printed.

    This is recorded rather than judged: ``labcairn serve`` answers to the
    development server's origins so that ``labcairn serve`` and ``pnpm dev`` work as a
    pair, and the cost — that whatever listens on the development port may drive the
    service — is stated in the command's own text. A baseline that ran through a
    different port would be measuring a different allow-list.
    """
    origins = served.get("/health").json()["origins"]
    assert served.origin in origins
    assert "http://127.0.0.1:5173" in origins
    assert "http://localhost:5173" in origins
    assert FOREIGN_ORIGIN not in origins


# --------------------------------------------------------------------------- #
# the gap the run found
# --------------------------------------------------------------------------- #


def test_the_event_stream_the_page_reads_is_unwired_in_the_service_the_cli_starts(
    served: ServedWorkbench,
) -> None:
    """The stream the page reads is still unwired — and now says so to the reader.

    ``labcairn serve`` builds the service without an event source — the command's own
    docstring says the stream belongs to the packages that own it — so the honest
    answer is a refusal, and it is one this test measures rather than carries: both
    reads answer ``403`` with ``not_implemented``.

    **What this test used to record, and what closed it.** Until 2026-11-10 the stream
    route raised the same refusal *inside* its response generator, by which point the
    ``200`` and ``text/event-stream`` headers had been sent: the client saw a stream
    that opened and ended with nothing in it, the service logged a traceback, and the
    Events panel said *"the event stream is live"*. That traceback was measured at
    6,205 bytes for one short stream against an 8,192-byte pipe capacity, and a service
    whose output is a pipe nobody drains parks in the write and answers nothing after
    that — the defect named O6. The route now refuses an unwired source before it
    starts a response (`src/labcairn/api/routes.py`, `get_event_stream`), so the
    refusal is a response, and the record is
    `docs/acceptance/o6-event-stream-stall-2026-11-10.md`.

    **Why it is still a test and not a note.** The stream is *not wired*: a service
    that answered this read with a live stream would be claiming an event source it
    does not have. What the read is for is that the refusal reaches the reader in the
    same two fields the JSON read carries — a refusal the client cannot see is a
    refusal nobody acts on.
    """
    page_read = served.get("/events", timeout=20.0)
    assert page_read.status == 403, page_read.body[:200]
    assert page_read.json()["reason"] == "not_implemented", page_read.body[:200]

    # The gap is closed: the refusal reaches the reader, in the same two
    # fields the JSON read carries. It used to open a 200 stream that then
    # died with nothing in it and left the service to log a traceback — the
    # traceback that, measured, was the fuel of the O6 stall (see
    # docs/acceptance/o6-event-stream-stall-2026-11-10.md).
    stream = served.get("/events/stream?follow=false", timeout=20.0)
    assert stream.status == 403, (
        "the stream no longer carries its refusal as a response: it answered "
        f"{stream.status} with {stream.body[:200]!r}"
    )
    assert stream.json()["reason"] == "not_implemented", stream.body[:200]


# --------------------------------------------------------------------------- #
# the channel-skip judgment, watched directly
# --------------------------------------------------------------------------- #


def test_the_channel_skip_reason_names_a_missing_pinned_channel() -> None:
    """The launch failure that *is* a missing channel is judged, and named.

    **The defence this watches.** `workbench_serve_support.channel_skip_reason`
    is what turns the real-browser fixture's launch failure into a named skip on a
    machine without the pinned channel (an Ubuntu runner carries no Edge). Until
    the 2026-11-14 review, that judgment had no witness of its own: the fixture in
    `tests/test_workbench_real_browser.py` calls it, but a call is not a witness —
    widening the judgment (for example, returning a skip reason for *every* launch
    failure) left the whole tree green, and a broken browser would then hide
    behind "the channel is missing".

    **The message is the driver's own shape.** Playwright's registry fails a
    missing channel before any process is spawned, with
    `Chromium distribution 'msedge' is not found at <path>` — measured against the
    1.65.1 driver and quoted in `workbench_serve_support.channel_skip_reason`'s
    docstring. The probe here uses that exact shape, so the witness tests the
    judgment against the words the driver really produces, not a paraphrase.

    **The reason carries the channel and the driver's words.** A skip reason that
    did not name the channel would be interchangeable with any other skip; the
    run's environment record is supposed to say which channel was missing and what
    the driver said, so the judgment's answer is required to carry both.
    """
    message = (
        f"Chromium distribution '{support.BROWSER_CHANNEL}' is not found at "
        "/opt/microsoft/msedge/msedge"
    )
    failure = type("ChannelMissing", (Exception,), {})(message)
    reason = support.channel_skip_reason(failure)
    assert reason is not None, (
        f"the driver's own missing-channel message ({message!r}) was not judged a "
        "channel skip, so the real-browser file would report a red launch failure "
        "on a machine that merely lacks the pinned browser"
    )
    assert support.BROWSER_CHANNEL in reason, (
        f"the skip reason does not name the channel {support.BROWSER_CHANNEL!r}: {reason!r}"
    )
    assert "is not found" in reason, (
        f"the skip reason does not carry the driver's own verdict: {reason!r}"
    )


def test_the_channel_skip_reason_refuses_every_other_launch_failure() -> None:
    """A launch failure that is *not* a missing channel stays a failure.

    **Why the negative side is the point.** A broken browser and an absent one are
    different facts. Collapsing them — any exception becoming a channel skip — is
    exactly the widening the 2026-11-14 review measured as silent: every witness
    stayed green while the skip reason swallowed launch crashes. So this side
    probes the failures a machine actually produces when the browser *exists* but
    cannot start, in the shapes the driver and the OS produce them, and requires
    `None` from each.

    **Each probe is a shape, not a paraphrase.** A process that starts and dies
    (the driver's "Browser closed unexpectedly"), a page/target crash, a timeout,
    an executable that is not runnable, and a bare OSError with no message at all:
    none of them names the channel, and none of them may read as its absence.
    """
    probes = {
        "browser died after spawn": Exception(
            "Browser closed unexpectedly on launch. Something is wrong with the browser process."
        ),
        "target crashed": Exception("Target page, context or browser has been closed"),
        "launch timed out": Exception("Timeout 30000ms exceeded during launch."),
        "executable not runnable": Exception("Failed to launch: spawn msedge ENOENT"),
        "bare OS error with no words": OSError(13, "Permission denied"),
    }
    for label, failure in probes.items():
        reason = support.channel_skip_reason(failure)
        assert reason is None, (
            f"{label} ({failure!r}) was judged a channel skip ({reason!r}). A browser "
            "that exists but failed to start is not an absent browser; reading it as "
            "one hides the breakage behind the pinned channel's absence."
        )

    # The judgment reads the pinned channel's name, so a *different* channel's
    # missing-channel message is not this run's skip either: the reason names
    # `BROWSER_CHANNEL`, and a message about another channel says the driver was
    # pointed somewhere else — a different fact.
    other_channel = Exception(
        "Chromium distribution 'chrome' is not found at /usr/bin/google-chrome"
    )
    assert support.channel_skip_reason(other_channel) is None, (
        "a missing-channel message about a channel this run does not pin was read "
        "as this run's channel skip"
    )


def test_the_real_browser_fixture_skips_through_this_judgment() -> None:
    """The real-browser file's skip path goes through `channel_skip_reason`.

    **Why an import-level assertion.** The two probes above witness the judgment's
    behaviour; this one witnesses that the fixture which turns a launch failure
    into a named skip still calls it. The 2026-11-14 review's concern was the
    defence with no witness; the fixture in `tests/test_workbench_real_browser.py`
    is the defence's only call site, and a call site that stops calling leaves the
    function tested but unused — the skip would become a red on every channel-less
    machine. Reading the fixture's source keeps that fact from rotting without
    touching that file's cases.
    """
    source = (REPO_ROOT_FOR_HELPER / "tests" / "test_workbench_real_browser.py").read_text(
        encoding="utf-8"
    )
    assert "channel_skip_reason(error)" in source, (
        "the real-browser fixture no longer consults channel_skip_reason, so a "
        "missing channel would surface as a red launch failure instead of the "
        "named skip the environment record expects"
    )
