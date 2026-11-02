"""The workbench's reads, driven against the live service.

**What the carried limitation said.** LC-P1-12's acceptance clause is *"CLI
and UI show identical Task state"*, and the Phase 1 closeout recorded that
the clause *"stays discharged through the API rather than measured"*: the
web tests stopped at a fake of `fetch`, and the API tests asserted the
service's own answers. Nothing drove the two surfaces against one running
service and compared them.

**What is measured here.** The service is built the way ``labcairn serve``
builds it — the same ``create_app``, the same context, the same selection
port — and it is driven through ``httpx``'s in-process ASGI transport, so no
socket is opened and no network is reached. The CLI is the console script a
developer types, run in a subprocess. The comparison is between the CLI's
``task status --json`` and the exact endpoint the workbench reads for its
state, ``GET /task``; the workbench's own rendering is ``reads.state.data``
verbatim, so identical bytes at that endpoint are what "identical Task
state" means for the two surfaces.

**The selection is measured as a write, not as a reply.** The service is
started bound to the second task, the UI's route selects the first, and then
the CLI — run *without* ``--task`` — must report the first. A route that
answered "selected" without persisting the workspace's pointer would pass a
test that only read the response; this one fails.

**The event stream is the same task's.** The page and the SSE frame are read
from the same service, and their cursor is compared with the task state's
``last_event_seq`` — the field the state carries precisely so that a client
can follow the stream without a gap.

**Why the costs in the shard file are apportioned.** No CI run is spent on a
new test file (the owner's rule), so its per-file seconds are apportioned
from the measured costs of the files it resembles; the shard file's
``measured_at`` is not moved, because no measurement happened at this
commit.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy.orm import Session

from labcairn.api import create_app
from labcairn.cli.workspace import application_context, locate, read_config, task_selector
from labcairn.core.ids import TaskId
from labcairn.db.repository import events_after
from labcairn.runtime.event import EventStreamPage, EventStreamRequest

pytestmark = pytest.mark.e2e

#: The origin the service answers to. The ASGI transport opens no socket, but
#: the guard still reads the header, so the request says where it is from.
OWN_ORIGIN = "http://127.0.0.1:8000"


def _console_script() -> Path:
    """The script a developer types, as this interpreter would find it."""
    name = "labcairn.exe" if os.name == "nt" else "labcairn"
    return Path(sys.executable).parent / name


@dataclass(frozen=True)
class _CliResult:
    """What the console script produced."""

    returncode: int
    stdout: str
    stderr: str

    def json(self) -> Any:
        """The stdout, parsed as the JSON the ``--json`` form prints."""
        return json.loads(self.stdout)


def _run_cli(*args: str) -> _CliResult:
    """Run the console script, with the encoding and width the CLI tests use."""
    script = _console_script()
    if not script.is_file():
        pytest.fail(f"the console script is not installed at {script}; run `uv sync`.")
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["COLUMNS"] = "200"
    completed = subprocess.run(
        [str(script), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=300,
    )
    return _CliResult(completed.returncode, completed.stdout, completed.stderr)


def _make_workspace(root: Path) -> None:
    """A workspace the CLI itself made."""
    result = _run_cli("--workspace", str(root), "init")
    assert result.returncode == 0, f"init failed: {result.stderr}"


def _create_task(root: Path, title: str) -> str:
    """A task the CLI itself made, and one whose id it printed."""
    result = _run_cli(
        "--workspace",
        str(root),
        "task",
        "create",
        "--title",
        title,
        "--objective",
        "Check what the records say.",
        "--criterion",
        "A cited answer, or an honest 'not established'.",
        "--json",
    )
    assert result.returncode == 0, f"task create failed: {result.stderr}"
    return str(result.json()["task_id"])


def _request(
    app: Any,
    method: str,
    path: str,
    *,
    token: str | None = None,
    body: dict[str, Any] | None = None,
) -> httpx.Response:
    """One request through the ASGI transport, with no socket and no network."""

    async def go() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        headers = {"Origin": OWN_ORIGIN}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(transport=transport, base_url=OWN_ORIGIN) as client:
            if body is None:
                return await client.request(method, path, headers=headers)
            return await client.request(method, path, headers=headers, json=body)

    return asyncio.run(go())


class _StoreEventSource:
    """The event source the service's host gives it.

    It reads the store's event log, which is what the port is for; the API
    package may not reach the store, so the host supplies this. It keeps no
    session: the caller hands it one per read.
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


def test_the_live_service_and_the_cli_report_the_same_task_state(tmp_path: Path) -> None:
    """One store, two surfaces, and bytes that agree.

    The service starts bound to the second task — the workspace's current
    task, as ``task create`` left it. The workbench's selection route moves
    the binding to the first, and the CLI run without ``--task`` follows it.
    Every read is compared field for field, and the state read after the
    selection is compared again with a fresh CLI invocation, so a page that
    cached the first answer would fail.
    """
    root = tmp_path / "workspace"
    _make_workspace(root)
    first = _create_task(root, "The first task")
    second = _create_task(root, "The second task")

    location = locate(root)
    config = read_config(location)
    assert config.current_task == second, "the CLI's create did not move the current task"

    with application_context(location, config, TaskId(uuid.UUID(second))) as context:
        app = create_app(
            context,
            event_source=_StoreEventSource(),
            select_task=task_selector(location, config),
        )

        # 1. The state the workbench draws and the state the CLI prints are
        #    the same document, before anything moves.
        service_state = _request(app, "GET", "/task")
        assert service_state.status_code == 200, service_state.text
        cli_state = _run_cli("--workspace", str(root), "task", "status", "--json")
        assert cli_state.returncode == 0, cli_state.stderr
        assert service_state.json() == json.loads(cli_state.stdout)
        assert service_state.json()["task"]["task_id"] == second

        # 2. The workbench's selection route moves the binding, and the
        #    response names the task it moved to.
        token = _request(app, "GET", "/session").json()["token"]
        selected = _request(app, "POST", "/task/select", token=token, body={"task_id": first})
        assert selected.status_code == 200, selected.text
        assert selected.json()["task_id"] == first
        assert _request(app, "GET", "/health").json()["task_id"] == first

        # 3. The CLI, run with no --task, follows the selection — so the
        #    switch was written where the other surface reads it.
        moved = _run_cli("--workspace", str(root), "task", "status", "--json")
        assert moved.returncode == 0, moved.stderr
        assert json.loads(moved.stdout) == _request(app, "GET", "/task").json()
        assert json.loads(moved.stdout)["task"]["task_id"] == first

        # 4. The task that is no longer current is still there, and an
        #    explicit --task still reaches it: a selection is a pointer, not
        #    a deletion.
        explicit = _run_cli("--workspace", str(root), "task", "status", "--task", second, "--json")
        assert explicit.returncode == 0, explicit.stderr
        assert json.loads(explicit.stdout)["task"]["task_id"] == second

        # 5. The event stream the workbench follows is the same task's, and
        #    its cursor agrees with the state's last_seq — the field that
        #    exists so a client can follow without a gap.
        state = _request(app, "GET", "/task").json()
        page = _request(app, "GET", "/events?after_seq=0").json()
        assert page["task_id"] == first
        assert page["next_after_seq"] == state["last_event_seq"]

        streamed = _request(app, "GET", "/events/stream?after_seq=0&follow=false")
        assert streamed.status_code == 200, streamed.text
        frame = streamed.text.strip().split("\n\n")[0]
        assert frame.startswith("data: ")
        assert json.loads(frame.removeprefix("data: "))["task_id"] == first
