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
from sqlalchemy import text
from sqlalchemy.orm import Session

from labcairn.api import create_app
from labcairn.application import list_source_addresses
from labcairn.cli.workspace import (
    DEFAULT_POLICY_RULES,
    application_context,
    locate,
    read_config,
    task_selector,
)
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


def _create_task_with_material(root: Path, title: str, csv_text: str) -> str:
    """A task the CLI made, bound to a source directory that holds one CSV.

    The report the version witnesses read is rendered from a claim, and a
    claim rests on material the task holds. This makes the workspace and the
    task the way the CLI a person would use makes them, so the service the
    witnesses drive is the service that workspace really produces.
    """
    (root / "materials").mkdir(parents=True, exist_ok=True)
    (root / "materials" / "one.csv").write_text(csv_text, encoding="utf-8")
    result = _run_cli(
        "--workspace",
        str(root),
        "task",
        "create",
        "--title",
        title,
        "--objective",
        "Establish whether the observation holds.",
        "--criterion",
        "A cited answer, or an honest 'not established'.",
        "--source-dir",
        "materials",
        "--json",
    )
    assert result.returncode == 0, f"task create failed: {result.stderr}"
    return str(result.json()["task_id"])


def test_the_report_has_two_revisions_and_both_are_served(tmp_path: Path) -> None:
    """The versioned writes §8 promises, over the wire the workbench reads.

    **The path the versions come from is the product's own.** A claim is
    recorded (the layer's ``record_claim``, as ``labcairn task claim`` runs
    it), the report is rendered **twice** through the same ``POST /report``
    the workbench's Render button sends, and each render is a new revision —
    ``report/v1/...`` is never altered by the second. The witnesses read
    what the workbench reads: ``GET /artifacts`` for the list, and
    ``GET /artifacts/{id}/content`` for the bytes, on the same ``create_app``
    the ``serve`` command builds.

    **Four things are asserted, and each fails for its own breakage:**

    1. the two renders produced **two revisions** of the report, and the
       receipts say so — a service that overwrote v1 would leave one;
    2. each revision's document bytes are served, and each hash matches its
       receipt — a content route that served the wrong file would not;
    3. the two revisions' bytes **differ** — a "new revision" that wrote the
       same bytes under a new number would be a rename, not a version;
    4. the v1 document is **unchanged** after the second render — the
       immutability the revision machinery claims, read back through the
       service.

    **What this witness does not claim.** It does not claim a version
    *selection* exists on the service: there is no route that stores a
    current version, and the workbench's choice is a view (witnessed on the
    page side). It does not claim the default policy serves the bytes
    either — the workspace's policy here allows reading the task's own
    outputs, which is the operator's own configuration act, and the gap that
    leaves is recorded, not assumed away.
    """
    root = tmp_path / "workspace"
    _make_workspace(root)
    task_id = _create_task_with_material(root, "The versioned report", "a,b\n1,2\n")

    location = locate(root)
    # The workspace's own policy decides whether the task's outputs may be
    # read, and the default one denies everything. The operator's own act of
    # allowing reads of the task's output area is what the content route
    # serves under, so this workspace carries that rule — written to the
    # policy file, where every rule the CLI and the service both read lives.
    from labcairn.cli.workspace import write_policy
    from labcairn.security.policy import Permission, Rule

    write_policy(
        location,
        (
            *DEFAULT_POLICY_RULES,
            Rule(
                effect=Permission.ALLOW,
                pattern="**",
                capabilities=frozenset({"fs.read", "fs.list"}),
                note="the version witnesses read the task's own outputs back",
            ),
        ),
    )
    config = read_config(location)
    assert config.current_task == task_id

    # The report is rendered from a claim, so the claim is recorded first,
    # through the layer, the way the CLI records it.
    with application_context(location, config, TaskId(uuid.UUID(task_id))) as context:
        from labcairn.application import record_claim
        from labcairn.application.evidence import ClaimRequest
        from labcairn.evidence.states import EvidenceKind

        source_id: str = context.store.session.execute(
            text("SELECT source_id FROM sources ORDER BY source_id LIMIT 1")
        ).scalar_one()
        addresses = list_source_addresses(context, source_id)
        assert addresses, "the ingest left no address a claim could be recorded at"
        recorded = record_claim(
            context,
            ClaimRequest(
                source_id=source_id,
                locator_key=addresses[0].locator_key,
                kind=EvidenceKind.NUMERIC,
                value=1.0,
                unit="dimensionless",
            ),
        )
        assert recorded.record.status == "extracted"

    with application_context(location, config, TaskId(uuid.UUID(task_id))) as context:
        app = create_app(context, event_source=_StoreEventSource())

        token = _request(app, "GET", "/session").json()["token"]

        # 1. Two renders, through the route the workbench's button sends.
        #    The route's success is 200 (it is the layer's own answer, and
        #    the contract test fixes it there).
        first = _request(
            app, "POST", "/report", token=token, body={"path": "report", "template_id": "default"}
        )
        assert first.status_code == 200, first.text
        second = _request(
            app, "POST", "/report", token=token, body={"path": "report", "template_id": "default"}
        )
        assert second.status_code == 200, second.text

        # The receipts: two revisions of the report, each naming its own
        # document bytes.
        artifacts = _request(app, "GET", "/artifacts").json()
        documents = [
            view
            for view in artifacts
            if view["receipt"]["kind"] == "report"
            and view["receipt"]["relative_path"].endswith("report.json")
        ]
        revisions = sorted(view["receipt"]["revision"] for view in documents)
        assert revisions == [1, 2], (
            f"two renders did not leave two report revisions; the store holds {revisions}"
        )
        v1, v2 = (
            next(view for view in documents if view["receipt"]["revision"] == number)
            for number in (1, 2)
        )
        assert v1["receipt"]["relative_path"] != v2["receipt"]["relative_path"]
        assert v1["receipt"]["content_sha256"] != v2["receipt"]["content_sha256"], (
            "revision 2 carries revision 1's hash: the second render wrote the same bytes"
        )

        # 2. Each revision's bytes are served, and each matches its receipt.
        import hashlib

        served: dict[int, bytes] = {}
        for number, view in ((1, v1), (2, v2)):
            receipt_id = view["receipt"]["receipt_id"]
            response = _request(app, "GET", f"/artifacts/{receipt_id}/content", token=token)
            assert response.status_code == 200, (
                f"revision {number}'s document was not served: {response.text}"
            )
            assert (
                hashlib.sha256(response.content).hexdigest() == (view["receipt"]["content_sha256"])
            ), f"revision {number}'s bytes do not hash to its receipt"
            served[number] = response.content

        # 3. Two revisions are two documents, not one written twice.
        assert served[1] != served[2], (
            "the two revisions' document bytes are identical; the second render "
            "is not a new version"
        )

        # 4. The v1 receipt still names the same bytes after the second
        #    render: the first revision was not altered. This is read back
        #    from the service a second time, so a receipt that had been
        #    quietly repointed would fail here.
        again = _request(app, "GET", "/artifacts").json()
        v1_again = next(
            view for view in again if view["receipt"]["receipt_id"] == v1["receipt"]["receipt_id"]
        )
        assert v1_again["receipt"]["content_sha256"] == v1["receipt"]["content_sha256"]
        reread = _request(
            app, "GET", f"/artifacts/{v1['receipt']['receipt_id']}/content", token=token
        )
        assert reread.status_code == 200, reread.text
        assert reread.content == served[1], "revision 1's bytes changed after the second render"


def test_the_workbench_has_no_version_selection_route(tmp_path: Path) -> None:
    """The honest boundary: no route stores a current version.

    The gap this batch closes is the workbench's **view** of the versions the
    service already writes; the service itself holds no "current version"
    pointer. This witness reads the service's own contract — the same
    OpenAPI document the TypeScript types are generated from — and asserts
    that no route claims to select one. If a version-selection route is ever
    added, this test fails and the workbench's panel, which says that
    choosing writes nothing, must be rewritten with it.
    """
    root = tmp_path / "workspace"
    _make_workspace(root)
    task_id = _create_task(root, "The unselected version")

    location = locate(root)
    config = read_config(location)
    with application_context(location, config, TaskId(uuid.UUID(task_id))) as context:
        app = create_app(context, event_source=_StoreEventSource())
        paths = set(app.openapi()["paths"])
        selectors = [
            path for path in paths if "version" in path.lower() and "select" in path.lower()
        ]
        assert not selectors, (
            f"the service now declares version-selection route(s) {selectors}: the "
            "workbench's version panel no longer tells the truth about choosing, and "
            "the witnesses must be rewritten with the route"
        )
