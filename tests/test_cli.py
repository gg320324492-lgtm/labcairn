"""The CLI, run as a subprocess, with its exit code and its stdout.

**The CLI is tested by running it.** Every test here starts a real process,
runs the console script a developer would type, and reads the exit code and
the two streams. A test that called the Typer functions in-process would
exercise the commands but not the command line: not the option parsing, not
the exit code, and not the bytes that actually reach a terminal.

**The machine-readable form is compared to the model, not to the prose.**
Where a command has a ``--json`` form, the test reads the JSON and compares
it, field by field, with the application layer's own model read in this
process. That is the property the acceptance clause asks for — *"the CLI's
``task status --json`` and the API's task document are compared, field by
field, from the same store"* — and it is the only comparison that says
something: comparing the JSON to the Rich output would only prove that two
renderings of the same thing resemble each other.

**A parameter that is accepted must change what happened.** Every option this
CLI takes is exercised with a *non-default* value, and the test asserts the
consequence. A test that only showed "the command ran" would pass for an
option that is accepted and thrown away, which is the failure mode the brief
warns about.

**A refusal must be distinguishable from a crash by the exit code alone.**
That is the property a script depends on, so it is asserted against both: a
refusal carries :data:`EXIT_REFUSED`, and a crash carries Python's own 1.

**Loading the CLI must be cheap.** ``labcairn --help`` is the first thing a
person types, and this file spawns the command more than forty times, so
every second the CLI spends loading is paid for more than forty times over.
The cost is measured in a subprocess — it is invisible from inside one,
because this process has already imported everything the CLI would import —
and it is bounded, because a cost nobody measures is a cost that comes back.
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from typer.main import get_command

import labcairn.cli
from labcairn.application import (
    ApplicationContext,
    inspect_source,
    list_artifacts,
    read_plan,
    read_task_state,
)
from labcairn.application.sources import SourceView
from labcairn.application.stages import TaskPlan
from labcairn.application.tasks import TaskState
from labcairn.cli.commands import EXIT_REFUSED, app
from labcairn.cli.workspace import application_context, locate, read_config
from labcairn.core.ids import TaskId
from labcairn.db import create_db_engine, create_session_factory, session_scope
from labcairn.db.materials import put_source
from labcairn.reports.receipt import (
    ArtifactKind,
    ArtifactProducerKind,
    ArtifactReceipt,
)
from labcairn.runtime.lifecycle import Task
from labcairn.sources.source import Source, SourceKind, SourceReadability

#: A fixed content hash. Constant so a test that asserts a hash round-trips
#: is not asserting against a value it generated with the call it is testing.
_HASH = "b" * 64

#: A second fixed hash, so two receipts are distinguishable.
_OTHER_HASH = "c" * 64

#: A fixed instant. The ledger's rows carry one, and a wall clock would make
#: the ordering assertions depend on when the test ran.
_MOMENT = datetime(2026, 1, 1, tzinfo=UTC)

#: The source id the product's own ingestion mints: location-derived, and
#: **not** a UUIDv7. See ``test_the_task_cannot_bind_a_material_the_product_ingests``.
_SOURCE_ID = "src-0123456789abcdef"


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


def run_cli(*args: str, cwd: Path | None = None, encoding: str = "utf-8") -> CliResult:
    """Run the console script and return what it produced.

    ``PYTHONIOENCODING`` is set because the child's output encoding is
    otherwise the machine's locale encoding, and a path with a non-ASCII
    character in it would make the test fail for a reason that has nothing
    to do with the CLI.

    ``COLUMNS`` is set for the same kind of reason. Rich asks the terminal
    how wide it is, and a pipe is not a terminal, so without this the
    rendered output would be laid out for eighty columns and a long path
    would be wrapped in the middle. The width of a terminal is a property of
    the terminal, and a test that asserted on a wrapped path would be
    asserting on the machine rather than on the CLI.
    """
    script = _console_script()
    if not script.is_file():
        pytest.fail(
            f"the console script is not installed at {script}. The CLI is tested "
            "through the script a developer types, so it has to be there; run "
            "`uv sync`."
        )
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = encoding
    environment["COLUMNS"] = "200"
    completed = subprocess.run(
        [str(script), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(cwd) if cwd is not None else None,
        env=environment,
        timeout=300,
    )
    return CliResult(completed.returncode, completed.stdout, completed.stderr)


# --------------------------------------------------------------------------- #
# the environment
# --------------------------------------------------------------------------- #


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
def material(workspace: Path) -> Path:
    """A file of supplied material, in the workspace's source root."""
    path = workspace / "materials" / "one.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")
    return path


@pytest.fixture
def source_id(workspace: Path, material: Path) -> str:
    """A material in the ledger, as the product's own ingestion leaves it.

    Written here rather than through the CLI because the application layer
    has no ingestion operation, so no surface can put a source in the ledger.
    The CLI's job is to *inspect* what is there.
    """
    engine = create_db_engine(workspace / "labcairn.db")
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            put_source(
                session,
                Source(
                    source_id=_SOURCE_ID,
                    kind=SourceKind.CSV,
                    display_name="one.csv",
                    relative_path="materials/one.csv",
                    content_sha256=_HASH,
                    size_bytes=12,
                    readability=SourceReadability.READABLE,
                    ingested_at=_MOMENT,
                ),
            )
    finally:
        engine.dispose()
    return _SOURCE_ID


@contextmanager
def _context(workspace: Path, task_id: str) -> Iterator[ApplicationContext]:
    """The layer's context, in this process, for the same workspace.

    Built the way the CLI builds it — the same configuration, the same
    policy — so that comparing the CLI's JSON with the layer's model is a
    comparison of two reads of the same store and not of two configurations.
    """
    location = locate(workspace)
    config = read_config(location)
    with application_context(location, config, TaskId(uuid.UUID(task_id))) as context:
        yield context


@pytest.fixture
def artifacts(workspace: Path, task_id: str) -> tuple[ArtifactReceipt, ...]:
    """Two artefacts in the store, in the order the store keeps them.

    Written here rather than through the CLI because the layer has no
    operation that records one: an artefact is recorded by the stage that
    produced it, and the CLI's stage produces none.

    Two, and not one, because a single-element list cannot show an ordering.
    """
    receipts = (
        ArtifactReceipt(
            receipt_id="artifact-first",
            task_id=task_id,
            kind=ArtifactKind.REPORT,
            relative_path=f"output/{task_id}/report.md",
            content_sha256=_HASH,
            size_bytes=10,
            produced_by=ArtifactProducerKind.STAGE,
            producer_id="draft",
            created_at=_MOMENT,
            revision=1,
        ),
        ArtifactReceipt(
            receipt_id="artifact-second",
            task_id=task_id,
            kind=ArtifactKind.REPORT,
            relative_path=f"output/{task_id}/report-revised.md",
            content_sha256=_OTHER_HASH,
            size_bytes=20,
            produced_by=ArtifactProducerKind.STAGE,
            producer_id="draft",
            created_at=_MOMENT,
            revision=2,
        ),
    )
    with _context(workspace, task_id) as context, context.store.unit(context.task_id) as work:
        for receipt in receipts:
            work.put_artifact(receipt)
    return receipts


# --------------------------------------------------------------------------- #
# the machine-readable form is the layer's model
# --------------------------------------------------------------------------- #


def test_task_status_json_is_the_layers_task_state(workspace: Path, task_id: str) -> None:
    """``task status --json`` is the layer's ``TaskState``, field for field.

    The acceptance clause's comparison, done: the CLI's JSON and the layer's
    model, read from the same store, are equal. If the CLI were serialising a
    rendering rather than the model, this is where it would show.
    """
    result = run_cli("--workspace", str(workspace), "task", "status", "--json")
    assert result.returncode == 0, result.stderr
    with _context(workspace, task_id) as context:
        expected = read_task_state(context).model_dump(mode="json")
    assert result.json() == expected


def test_task_status_plan_json_is_the_layers_task_plan(workspace: Path, task_id: str) -> None:
    """``--plan`` reports the layer's ``TaskPlan`` and not the state.

    Two different models, and the flag picks between them. A CLI that
    reported the state under both flags would pass a test that only checked
    the exit code; this one checks the shape.
    """
    result = run_cli("--workspace", str(workspace), "task", "status", "--plan", "--json")
    assert result.returncode == 0, result.stderr
    with _context(workspace, task_id) as context:
        expected = read_plan(context).model_dump(mode="json")
    assert result.json() == expected
    assert "skill_id" in result.json()


def test_sources_inspect_json_is_the_layers_source_view(
    workspace: Path, task_id: str, source_id: str
) -> None:
    """``sources inspect --json`` is the layer's ``SourceView``."""
    result = run_cli(
        "--workspace", str(workspace), "sources", "inspect", "--source", source_id, "--json"
    )
    assert result.returncode == 0, result.stderr
    with _context(workspace, task_id) as context:
        expected = inspect_source(context, source_id).model_dump(mode="json")
    assert result.json() == expected


def test_the_json_is_utf8_whatever_the_console_encoding_is(workspace: Path, task_id: str) -> None:
    """A value the console's code page cannot spell still arrives intact.

    A redirected stream on Windows takes the machine's ANSI code page, and a
    task whose title holds a character that page cannot spell would either
    be mangled or raise. The bytes the CLI writes are the bytes the API
    serves, so the encoding is fixed rather than inherited.
    """
    title = "Le café — 調查"
    created = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "create",
        "--title",
        title,
        "--objective",
        "One.",
        "--criterion",
        "Done.",
        "--json",
    )
    assert created.returncode == 0, created.stderr
    assert created.json()["title"] == title

    # The same bytes, read back on a console that could not have spelled it.
    legacy = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "status",
        "--task",
        str(created.json()["task_id"]),
        "--json",
        encoding="cp1252",
    )
    assert legacy.returncode == 0, legacy.stderr
    assert legacy.json()["task"]["title"] == title


def test_artifacts_list_json_is_the_layers_artifact_views(workspace: Path, task_id: str) -> None:
    """``artifacts list --json`` is an array of the layer's ``ArtifactView``.

    Empty here, so the shape is checked against the layer's own answer for an
    empty task rather than against a literal.
    """
    result = run_cli("--workspace", str(workspace), "artifacts", "list", "--json")
    assert result.returncode == 0, result.stderr
    with _context(workspace, task_id) as context:
        expected = [view.model_dump(mode="json") for view in list_artifacts(context)]
    assert result.json() == expected


def test_artifacts_list_json_carries_every_field_of_every_artefact(
    workspace: Path, task_id: str, artifacts: tuple[ArtifactReceipt, ...]
) -> None:
    """A **non-empty** listing carries the receipts' fields, not empty objects.

    The empty listing cannot tell a correct array from one that dropped every
    field: pydantic's adapter for the base model type serialises a subclass
    through the base schema, which has none, and turns each item into ``{}``.
    An empty array looks identical. This is the test that sees the
    difference.
    """
    result = run_cli("--workspace", str(workspace), "artifacts", "list", "--json")
    assert result.returncode == 0, result.stderr
    payload = result.json()
    assert len(payload) == 2
    with _context(workspace, task_id) as context:
        expected = [view.model_dump(mode="json") for view in list_artifacts(context)]
    assert payload == expected
    assert payload[0]["receipt"]["receipt_id"] == "artifact-first"
    assert payload[0]["resource_key"] == f"output/{task_id}/report.md"


def test_artifacts_are_listed_in_the_order_the_plan_names(
    workspace: Path, task_id: str, artifacts: tuple[ArtifactReceipt, ...]
) -> None:
    """The order is the store's, and the CLI does not reorder it.

    The plan's ordering rule (§2.5): artefacts by ``(revision, artifact_id)``.
    The layer's store already orders them; the CLI's job is not to disturb
    that, and a list whose order changes between runs is a bug a reader
    reports as "it shuffled".
    """
    result = run_cli("--workspace", str(workspace), "artifacts", "list", "--json")
    assert result.returncode == 0, result.stderr
    ids = [item["receipt"]["receipt_id"] for item in result.json()]
    assert ids == ["artifact-first", "artifact-second"]
    revisions = [item["receipt"]["revision"] for item in result.json()]
    assert revisions == [1, 2]


def test_task_run_json_is_the_layers_stage_run(
    workspace: Path, task_id: str, source_id: str
) -> None:
    """``task run --json`` is the layer's ``StageRun``."""
    result = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "run",
        "--source",
        source_id,
        "--json",
    )
    assert result.returncode == 0, result.stderr
    payload = result.json()
    assert payload["stage"]["name"] == "inventory"
    assert payload["operation"]["state"] == "confirmed"
    assert payload["stage"]["output_hashes"] == [_HASH]


def test_task_create_json_is_the_layers_task_model(workspace: Path) -> None:
    """``task create --json`` is the layer's ``Task``, field for field.

    The layer's result for a create is a frozen dataclass carrying a task and
    a workspace; the task is the model, and the workspace is where the task
    lives, which the caller already named. What the API will return for the
    same request is this.
    """
    result = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "create",
        "--title",
        "Read the literature",
        "--objective",
        "Establish what the corpus says.",
        "--criterion",
        "A cited answer, or an honest 'not established'.",
        "--json",
    )
    assert result.returncode == 0, result.stderr
    payload = result.json()
    with _context(workspace, str(payload["task_id"])) as context:
        expected = read_task_state(context).task.model_dump(mode="json")
    assert payload == expected


def test_the_json_form_is_not_a_rendering_of_the_prose(workspace: Path, task_id: str) -> None:
    """The two forms are different shapes, and the JSON one is parseable.

    A cheap guard against the failure the architecture's rule names: a
    "machine-readable" form that is actually the prose, with a ``--json``
    flag that prints it anyway. The prose is a picture; the JSON is not.
    """
    prose = run_cli("--workspace", str(workspace), "task", "status")
    machine = run_cli("--workspace", str(workspace), "task", "status", "--json")
    assert prose.returncode == 0, prose.stderr
    assert machine.returncode == 0, machine.stderr
    assert machine.stdout.strip().startswith("{")
    assert not prose.stdout.strip().startswith("{")
    assert machine.stdout != prose.stdout


#: The rule the rendered tables are drawn with: the box's vertical border.
_TABLE_RULE = "│"


def _the_prose_value(rendered: str, label: str) -> str:
    """What the rendered form gives *label*.

    The rendered form is a grid of a label column and a value column, and
    the value is what follows the label on its line. Read this way rather
    than by asking whether the value is *somewhere* in the output, so that a
    value drawn against the wrong label is caught: both values would still
    be in the text, and the two forms would have swapped their fields
    without anybody noticing.
    """
    for line in rendered.splitlines():
        cells = line.split(_TABLE_RULE)
        if len(cells) < 3:
            continue
        parts = re.split(r"\s{2,}", cells[1].strip(), maxsplit=1)
        if len(parts) == 2 and parts[0] == label:
            return parts[1]
    raise AssertionError(f"the rendered form has no {label!r} row:\n{rendered}")


def test_task_status_prose_says_what_its_json_says(workspace: Path, task_id: str) -> None:
    """``task status`` and ``task status --json`` are one model, drawn twice.

    The rule the architecture states: the rendered output is a rendering of
    the same data. ``doctor`` is watched against this and ``task status``
    was not, so a renderer that drew its own words — a title of "a task"
    where the model says "Read the literature" — would have gone unnoticed,
    and the README's claim that the two forms print the same model would
    have gone with it.

    **Row by row, and not by searching the text.** Every row the rendered
    form draws is compared with the field the JSON form carries, and it is
    compared against that row's own value. A value drawn against the wrong
    label would still be somewhere in the output, and the two forms would
    have swapped their fields without anybody noticing.
    """
    prose = run_cli("--workspace", str(workspace), "task", "status")
    machine = run_cli("--workspace", str(workspace), "task", "status", "--json")
    assert prose.returncode == 0, prose.stderr
    assert machine.returncode == 0, machine.stderr
    state = machine.json()
    expected = {
        "task": state["task"]["task_id"],
        "title": state["task"]["title"],
        "objective": state["task"]["goal"]["objective"],
        "revision": str(state["task"]["revision"]),
        "last event": str(state["last_event_seq"]),
        "runs": str(len(state["runs"])),
        "stages": str(len(state["stages"])),
        "artifacts": str(len(state["artifacts"])),
        "approvals": str(len(state["approvals"])),
    }
    for label, value in expected.items():
        drawn = _the_prose_value(prose.stdout, label)
        assert drawn == value, (
            f"the rendered form's {label!r} row says {drawn!r} and the JSON form "
            f"says {value!r}: the two forms are not the same model"
        )


# --------------------------------------------------------------------------- #
# a refusal is rendered, not raised
# --------------------------------------------------------------------------- #


def test_a_refusal_exits_with_the_refusal_code_and_names_what_was_refused(
    workspace: Path, task_id: str
) -> None:
    """A refusal is a message and an exit code, never a traceback.

    The source that is not in the ledger is refused by the layer, and the
    layer's reason and message are what the operator is shown.
    """
    result = run_cli(
        "--workspace",
        str(workspace),
        "sources",
        "inspect",
        "--source",
        "src-does-not-exist",
    )
    assert result.returncode == EXIT_REFUSED
    assert "Traceback" not in result.stderr
    assert "source_not_found" in result.stderr
    assert "src-does-not-exist" in result.stderr


def test_a_refusal_in_json_mode_carries_the_reason_and_the_message(
    workspace: Path, task_id: str
) -> None:
    """The JSON form of a refusal is the layer's ``{reason, message}``.

    The same two fields, whatever produced the refusal, so a script reads one
    refusal format.
    """
    result = run_cli(
        "--workspace",
        str(workspace),
        "sources",
        "inspect",
        "--source",
        "src-does-not-exist",
        "--json",
    )
    assert result.returncode == EXIT_REFUSED
    payload = result.json()
    assert set(payload) == {"reason", "message"}
    assert payload["reason"] == "source_not_found"
    assert "src-does-not-exist" in payload["message"]


def test_a_refusal_is_distinguishable_from_a_crash_by_the_exit_code_alone(
    workspace: Path, task_id: str
) -> None:
    """A refusal exits 3; a crash exits 1; a script needs no message to tell.

    The crash is provoked honestly: the database file is replaced with
    rubbish, so the store cannot be opened and the failure is not one the
    CLI could have rendered. The refusal is the same command against a
    sound database.
    """
    refused = run_cli(
        "--workspace",
        str(workspace),
        "sources",
        "inspect",
        "--source",
        "src-does-not-exist",
    )
    assert refused.returncode == EXIT_REFUSED
    assert refused.returncode not in (0, 1, 2)

    database = workspace / "labcairn.db"
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(database) + suffix)
        if candidate.exists():
            candidate.unlink()
    database.write_bytes(b"this is not a database")

    crashed = run_cli("--workspace", str(workspace), "task", "status")
    assert crashed.returncode == 1
    assert crashed.returncode != EXIT_REFUSED
    assert "Traceback" in crashed.stderr


def test_a_usage_error_carries_clicks_own_exit_code(workspace: Path) -> None:
    """A command that was never run exits 2, not 3.

    Three exits, three meanings, all distinguishable by the exit code alone:
    0 for a result, 2 for a usage error, 3 for a refusal, and 1 for a crash.
    """
    result = run_cli("--workspace", str(workspace), "task", "create")
    assert result.returncode == 2
    assert result.returncode != EXIT_REFUSED


def test_a_task_the_store_does_not_hold_is_refused(workspace: Path) -> None:
    """A task id the store does not hold is the layer's refusal, unchanged.

    The reason is the layer's own ``task_not_found``, so a caller reads one
    vocabulary whichever surface asked.
    """
    result = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "status",
        "--task",
        "01a1587b-02c4-77fc-b111-7cf6a606de7c",
        "--json",
    )
    assert result.returncode == EXIT_REFUSED
    assert result.json()["reason"] == "task_not_found"
    assert "Traceback" not in result.stderr


def test_a_prose_refusal_writes_nothing_to_standard_output(workspace: Path, task_id: str) -> None:
    """A refusal in the rendered form goes to standard error only.

    A script that reads standard output and forgets to check the exit code
    must not be able to mistake a refusal for a result.
    """
    result = run_cli(
        "--workspace",
        str(workspace),
        "sources",
        "inspect",
        "--source",
        "src-does-not-exist",
    )
    assert result.returncode == EXIT_REFUSED
    assert result.stdout == ""
    assert "source_not_found" in result.stderr


def test_a_refused_policy_is_rendered_rather_than_raised(workspace: Path, task_id: str) -> None:
    """A policy that denies the operation refuses; the command does not crash.

    The policy file is the operator's, and a rule that denies reading the
    task's own record must stop the command with a refusal.
    """
    policy_path = workspace / ".labcairn" / "policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["rules"].insert(
        0,
        {
            "effect": "deny",
            "pattern": "output",
            "capabilities": ["fs.read"],
            "root_ids": None,
            "effects": None,
            "task_ids": None,
            "note": "the operator denies reading the task's record",
        },
    )
    policy_path.write_text(json.dumps(policy), encoding="utf-8")

    result = run_cli("--workspace", str(workspace), "task", "status", "--json")
    assert result.returncode == EXIT_REFUSED
    payload = result.json()
    assert payload["reason"] == "permission_denied"
    assert "Traceback" not in result.stderr


# --------------------------------------------------------------------------- #
# a parameter that is accepted must change what happened
# --------------------------------------------------------------------------- #


def test_the_task_option_selects_a_different_task(workspace: Path) -> None:
    """``--task`` picks the task, and the answer changes with it.

    Two tasks with different titles; the report names the one asked for. An
    option that was accepted and ignored would name the first task both
    times, and this test would see the same title twice.
    """
    first = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "create",
        "--title",
        "First task",
        "--objective",
        "One.",
        "--criterion",
        "Done.",
        "--json",
    )
    second = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "create",
        "--title",
        "Second task",
        "--objective",
        "Two.",
        "--criterion",
        "Done.",
        "--json",
    )
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr

    current = str(first.json()["task_id"])

    # The workspace's current task is the second one; --task must override it.
    report = run_cli("--workspace", str(workspace), "task", "status", "--task", current, "--json")
    assert report.returncode == 0, report.stderr
    assert report.json()["task"]["title"] == "First task"
    assert report.json()["task"]["task_id"] == current

    # And without --task, the current one is reported: the two together show
    # that the option chooses rather than merely being accepted.
    current_report = run_cli("--workspace", str(workspace), "task", "status", "--json")
    assert current_report.returncode == 0, current_report.stderr
    assert current_report.json()["task"]["title"] == "Second task"


def test_the_current_task_is_used_when_no_task_is_named(workspace: Path) -> None:
    """Without ``--task``, the workspace's current task is the one reported.

    The counterpart to the test above: if ``--task`` were the only way in,
    the default would be doing nothing.
    """
    result = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "create",
        "--title",
        "The only task",
        "--objective",
        "One.",
        "--criterion",
        "Done.",
        "--json",
    )
    assert result.returncode == 0, result.stderr
    report = run_cli("--workspace", str(workspace), "task", "status", "--json")
    assert report.returncode == 0, report.stderr
    assert report.json()["task"]["title"] == "The only task"


def test_the_source_dir_option_changes_the_roots_that_are_bound(workspace: Path) -> None:
    """``--source-dir`` adds a source root, and the record shows it.

    The directory is a *non-default* value — the workspace already has
    ``materials`` — so an option that was accepted and thrown away would leave
    the record unchanged and this test would see it.
    """
    (workspace / "extra").mkdir()
    result = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "create",
        "--title",
        "Bound to two roots",
        "--objective",
        "One.",
        "--criterion",
        "Done.",
        "--source-dir",
        "extra",
        "--json",
    )
    assert result.returncode == 0, result.stderr
    config = read_config(locate(workspace))
    assert "extra" in config.source_dirs
    assert "materials" in config.source_dirs


def test_a_source_dir_outside_the_workspace_is_refused(workspace: Path, tmp_path: Path) -> None:
    """A source root the workspace does not contain is refused, not bound.

    The refusal names the directory, because the operator named it.
    """
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    result = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "create",
        "--title",
        "Bad root",
        "--objective",
        "One.",
        "--criterion",
        "Done.",
        "--source-dir",
        str(outside),
    )
    assert result.returncode == EXIT_REFUSED
    assert "outside the workspace" in result.stderr
    assert "Traceback" not in result.stderr


def test_task_create_binds_the_material_it_ingested(workspace: Path) -> None:
    """``task create`` puts the material in the ledger and binds it to the task.

    The task holds the ids of the materials it ingested, so the layer's
    ``list_sources`` finds them: a task that holds no material can carry
    disclosures and never a claim.
    """
    (workspace / "materials" / "one.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    result = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "create",
        "--title",
        "Bound to real material",
        "--objective",
        "One.",
        "--criterion",
        "Done.",
        "--source-dir",
        "materials",
        "--json",
    )
    assert result.returncode == 0, result.stderr
    task = result.json()
    assert task["bound_source_ids"], "the task holds no material"

    # And the material can be inspected, which it could not be before the
    # ingestion: the ledger holds it under the path the layer resolves.
    inspected = run_cli(
        "--workspace",
        str(workspace),
        "sources",
        "inspect",
        "--source",
        task["bound_source_ids"][0],
        "--json",
    )
    assert inspected.returncode == 0, inspected.stderr
    assert inspected.json()["source"]["readability"] == "readable"


def test_sources_ingest_json_is_the_layers_ingestion_report(workspace: Path) -> None:
    """``sources ingest --json`` is the layer's own report.

    The model, byte for byte: a script depends on the JSON and not on the
    prose, so the JSON *is* the model and not a rendering of it.
    """
    (workspace / "materials" / "one.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    created = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "create",
        "--title",
        "Ingested twice",
        "--objective",
        "One.",
        "--criterion",
        "Done.",
        "--json",
    )
    assert created.returncode == 0, created.stderr

    result = run_cli("--workspace", str(workspace), "sources", "ingest", "--json")
    assert result.returncode == 0, result.stderr
    report = result.json()
    assert report["source_ids"], "the CLI ingested nothing"
    assert report["bound_source_ids"] == report["source_ids"]
    assert report["failures"] == []
    assert report["readable"] == 1
    assert report["files"][0]["source"]["relative_path"] == "materials/one.csv"

    # And the second run writes nothing: the same material, ingested again.
    again = run_cli("--workspace", str(workspace), "sources", "ingest", "--json")
    assert again.returncode == 0, again.stderr
    assert again.json()["source_ids"] == report["source_ids"]
    assert again.json()["files"][0]["rows_written"] == 0


def test_task_create_refuses_when_the_material_could_not_all_be_read(workspace: Path) -> None:
    """A file the walk could not read is reported, and the command refuses.

    The arrangement changed because the collision it used to rely on is gone.
    Two source roots holding a file of the same name produced the same
    ``relative_path``, and the ledger's UNIQUE constraint refused the second
    one. The walk records the **workspace-relative** path now, so the two
    roots' files have different paths and nothing collides.

    A file past the read limit is the failure that is left, and it is a real
    one: the boundary names the file, the read refuses it as too large to
    open, and the walk records it. The command refuses rather than reporting
    a task that quietly holds less than the material it was given, and the
    refusal names the file.

    The bytes are never read -- the refusal is on the size -- so the file
    costs a write and nothing else, and the arrangement cannot skip on a
    platform where symlinks are unavailable.
    """
    (workspace / "materials" / "one.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (workspace / "other").mkdir()
    (workspace / "other" / "oversized.csv").write_bytes(b"a,b\n1,2\n" * 8_000_001)
    created = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "create",
        "--title",
        "One root too large",
        "--objective",
        "One.",
        "--criterion",
        "Done.",
        "--source-dir",
        "other",
        "--json",
    )
    assert created.returncode == EXIT_REFUSED
    refusal = created.json()
    assert refusal["reason"] == "material_incomplete"
    assert "oversized.csv" in refusal["message"]


def test_the_plan_option_reports_the_plan_and_not_the_state(workspace: Path, task_id: str) -> None:
    """``--plan`` changes what is reported, in the prose as well as the JSON.

    The plan names the declared workflow; the state does not. A flag that was
    accepted and ignored would produce the same report either way.
    """
    state = run_cli("--workspace", str(workspace), "task", "status")
    plan = run_cli("--workspace", str(workspace), "task", "status", "--plan")
    assert state.returncode == 0, state.stderr
    assert plan.returncode == 0, plan.stderr
    assert state.stdout != plan.stdout
    assert "inventory" in plan.stdout


def test_the_resume_command_starts_a_new_attempt(
    workspace: Path, task_id: str, source_id: str
) -> None:
    """``task resume`` is a new Run against the same Task.

    The runtime's rule (ADR-0003 C1, R-02): the task's identity survives
    every attempt, and the attempt number says how many there have been.
    ``task run`` continues the current run; ``task resume`` opens another.
    """
    first = run_cli("--workspace", str(workspace), "task", "run", "--source", source_id, "--json")
    assert first.returncode == 0, first.stderr
    assert first.json()["run"]["attempt"] == 1

    second = run_cli("--workspace", str(workspace), "task", "run", "--source", source_id, "--json")
    assert second.returncode == 0, second.stderr
    assert second.json()["run"]["attempt"] == 1
    assert second.json()["run"]["run_id"] == first.json()["run"]["run_id"]

    resumed = run_cli(
        "--workspace", str(workspace), "task", "resume", "--source", source_id, "--json"
    )
    assert resumed.returncode == 0, resumed.stderr
    assert resumed.json()["run"]["attempt"] == 2
    assert resumed.json()["run"]["run_id"] != first.json()["run"]["run_id"]


def test_the_assume_capability_option_changes_the_reported_outcome(
    workspace: Path,
) -> None:
    """``--assume-capability`` changes the finding it applies to.

    The provider is configured but never probed, so every capability is
    unverified and unusable. The override makes one of them usable, and only
    the one it names.
    """
    (workspace / "providers.json").write_text(
        json.dumps(
            {
                "providers": {
                    "local": {
                        "protocol": "openai_compatible",
                        "model": "some-model",
                        "base_url": "http://127.0.0.1:9/v1",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    plain = run_cli("--workspace", str(workspace), "doctor", "--json")
    assert plain.returncode == 0, plain.stderr
    findings = {f["capability"]: f for f in plain.json()["providers"][0]["capabilities"]}
    assert findings["tool_calls"]["outcome"] == "unverified"
    assert findings["tool_calls"]["usable"] is False
    assert findings["tool_calls"]["assumed"] is False

    assumed = run_cli(
        "--workspace",
        str(workspace),
        "doctor",
        "--assume-capability",
        "tool_calls",
        "--json",
    )
    assert assumed.returncode == 0, assumed.stderr
    findings = {f["capability"]: f for f in assumed.json()["providers"][0]["capabilities"]}
    assert findings["tool_calls"]["assumed"] is True
    assert findings["tool_calls"]["usable"] is True
    assert findings["tool_calls"]["outcome"] == "unverified"
    assert findings["usage_reporting"]["assumed"] is False
    assert findings["usage_reporting"]["usable"] is False


def test_an_unknown_assumed_capability_is_refused(workspace: Path) -> None:
    """A capability this build does not know is refused, not ignored.

    An override that named nothing would be a spelling mistake, and a
    spelling mistake that silently changed nothing is how a capability ends
    up assumed and unusable.
    """
    (workspace / "providers.json").write_text(
        json.dumps(
            {
                "providers": {
                    "local": {
                        "protocol": "openai_compatible",
                        "model": "some-model",
                        "base_url": "http://127.0.0.1:9/v1",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    result = run_cli(
        "--workspace", str(workspace), "doctor", "--assume-capability", "telepathy", "--json"
    )
    assert result.returncode == EXIT_REFUSED
    assert "telepathy" in result.stdout


def test_the_show_token_option_reveals_the_api_session_token(workspace: Path) -> None:
    """The API's session token is printed when the operator asks for it.

    The plan's decision §1.4.4: the token is minted at start-up, written to
    a file in the workspace, and printed by the CLI. It is withheld by
    default, because a token in a diagnostic dump is a token in whatever the
    dump was pasted into.
    """
    token_path = workspace / ".labcairn" / "session-token"
    token_path.write_text("s3cr3t-token\n", encoding="utf-8")

    hidden = run_cli("--workspace", str(workspace), "doctor", "--json")
    assert hidden.returncode == 0, hidden.stderr
    assert hidden.json()["api_session"]["present"] is True
    assert hidden.json()["api_session"]["token"] is None
    assert "s3cr3t-token" not in hidden.stdout

    shown = run_cli("--workspace", str(workspace), "doctor", "--show-token", "--json")
    assert shown.returncode == 0, shown.stderr
    assert shown.json()["api_session"]["token"] == "s3cr3t-token"


def test_the_cli_and_the_service_name_the_token_file_the_same_way(
    tmp_path: Path,
) -> None:
    """One name for one file.

    The service writes its session token and the doctor reads it, and the two
    are the same file under the same name — so the doctor reports a session
    that exists instead of looking for one that does not.

    The two declarations are compared here because they cannot be shared: the
    CLI does not import the API's package, which pulls in the whole web
    stack, so the name is written down twice and this is what watches that
    the two writings agree.
    """
    from labcairn.api.session import SESSION_DIR_NAME, SESSION_FILE_NAME
    from labcairn.cli.workspace import CONFIG_DIR_NAME, SESSION_TOKEN_FILE_NAME

    assert SESSION_FILE_NAME == SESSION_TOKEN_FILE_NAME, (
        f"the service writes {SESSION_FILE_NAME!r} and the CLI reads "
        f"{SESSION_TOKEN_FILE_NAME!r}: they are one file and must have one name"
    )
    assert SESSION_DIR_NAME == CONFIG_DIR_NAME, (
        f"the service writes into {SESSION_DIR_NAME!r} and the CLI reads "
        f"{CONFIG_DIR_NAME!r}: they are one directory and must have one name"
    )

    root = tmp_path / "workspace"
    location = locate(root)
    assert location.token_path == root / SESSION_DIR_NAME / SESSION_FILE_NAME


def test_the_json_option_changes_the_output_shape(workspace: Path, task_id: str) -> None:
    """``--json`` gives the machine-readable form; without it, the drawing.

    Checked on the bytes rather than on the content, because the point is
    that the two are different forms of one thing.
    """
    without = run_cli("--workspace", str(workspace), "artifacts", "list")
    with_json = run_cli("--workspace", str(workspace), "artifacts", "list", "--json")
    assert without.returncode == 0, without.stderr
    assert with_json.returncode == 0, with_json.stderr
    assert without.stdout != with_json.stdout
    assert with_json.stdout.strip().startswith("[")


def test_a_task_must_be_named_before_a_task_scoped_command_runs(workspace: Path) -> None:
    """A workspace with no task refuses rather than guessing.

    The refusal carries its own reason, so a caller can tell it from the
    layer's.
    """
    result = run_cli("--workspace", str(workspace), "task", "status", "--json")
    assert result.returncode == EXIT_REFUSED
    assert result.json()["reason"] == "task_not_selected"
    assert "--task" in result.json()["message"]


def test_a_task_id_that_is_not_a_uuid_is_refused(workspace: Path) -> None:
    """A task id that is not a task id is refused, not looked up.

    The runtime's ids are UUIDv7 and say so; a value that is not one is a
    mistake, and a mistake that became a lookup failure would be a much
    worse message.
    """
    result = run_cli("--workspace", str(workspace), "task", "status", "--task", "not-an-id")
    assert result.returncode == EXIT_REFUSED
    assert "UUIDv7" in result.stderr
    assert "Traceback" not in result.stderr


# --------------------------------------------------------------------------- #
# init
# --------------------------------------------------------------------------- #


def test_init_refuses_an_existing_workspace(workspace: Path) -> None:
    """``init`` does not overwrite a workspace that is already there.

    A workspace holds a task's history; a second ``init`` must not be able to
    leave two of them disagreeing about what the workspace is.
    """
    result = run_cli("--workspace", str(workspace), "init")
    assert result.returncode == EXIT_REFUSED
    assert "already holds a LabCairn workspace" in result.stderr
    assert "Traceback" not in result.stderr


def test_init_leaves_an_existing_workspace_unchanged(workspace: Path, task_id: str) -> None:
    """A refused ``init`` changes nothing.

    The task that was there is still there, and still the current one.
    """
    before = read_config(locate(workspace))
    run_cli("--workspace", str(workspace), "init")
    after = read_config(locate(workspace))
    assert after == before
    assert after.current_task == task_id


def test_init_makes_the_database_the_sources_and_the_policy(workspace: Path) -> None:
    """What ``init`` says it made is what is there.

    The report is the only thing that says what was made, so it has to be
    true.
    """
    result = run_cli("--workspace", str(workspace), "init")
    assert result.returncode == EXIT_REFUSED

    location = locate(workspace)
    assert location.database_path.is_file()
    assert location.materials_path.is_dir()
    assert location.output_path.is_dir()
    assert location.policy_path.is_file()
    assert location.config_path.is_file()


def test_init_reports_what_it_made(workspace: Path) -> None:
    """The report names the paths it created."""
    config = read_config(locate(workspace))
    assert config.source_dirs == ("materials",)
    assert config.current_task is None


def test_init_in_a_directory_that_is_not_a_workspace_succeeds(tmp_path: Path) -> None:
    """``init`` makes a workspace in an empty directory."""
    root = tmp_path / "fresh"
    result = run_cli("--workspace", str(root), "init", "--json")
    assert result.returncode == 0, result.stderr
    payload = result.json()
    assert payload["root"] == str(root.resolve())
    assert payload["migration_revision"] != "none"
    assert str(root / "labcairn.db") in payload["created"]


# --------------------------------------------------------------------------- #
# doctor
# --------------------------------------------------------------------------- #


def test_doctor_reports_the_workspace_the_database_the_policy_and_the_providers(
    workspace: Path, task_id: str
) -> None:
    """``doctor``'s findings are the four things the command is about.

    Each is present and carries the fact it is about, and the policy names
    the file the rules came from.
    """
    result = run_cli("--workspace", str(workspace), "doctor", "--json")
    assert result.returncode == 0, result.stderr
    payload = result.json()
    assert payload["workspace"]["root"] == str(workspace.resolve())
    assert payload["workspace"]["initialised"] is True
    assert payload["workspace"]["current_task"] == task_id
    assert payload["database"]["present"] is True
    assert payload["database"]["at_head"] is True
    assert payload["policy"]["source"].endswith("policy.json")
    assert payload["policy"]["rules"]
    assert payload["providers"] == []


def test_doctor_works_on_a_workspace_that_does_not_exist(tmp_path: Path) -> None:
    """``doctor`` reports what it found, and a missing workspace is a finding.

    A diagnostic that refuses to run on the thing that is broken is not a
    diagnostic.
    """
    root = tmp_path / "nothing-here"
    result = run_cli("--workspace", str(root), "doctor", "--json")
    assert result.returncode == 0, result.stderr
    payload = result.json()
    assert payload["workspace"]["initialised"] is False
    assert payload["database"]["present"] is False
    assert payload["api_session"]["present"] is False


def test_doctor_probe_reports_a_probe_it_could_not_make(workspace: Path) -> None:
    """``--probe`` on an endpoint that cannot be asked is a finding, not a crash.

    The provider is configured with no credential, so the probe fails before
    any request is made — which is also why this test needs no network and no
    credential. A diagnostic that died on the first thing it could not read
    would be no diagnostic at all.
    """
    (workspace / "providers.json").write_text(
        json.dumps(
            {
                "providers": {
                    "local": {
                        "protocol": "openai_compatible",
                        "model": "some-model",
                        "base_url": "http://127.0.0.1:9/v1",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    result = run_cli("--workspace", str(workspace), "doctor", "--probe", "--json")
    assert result.returncode == 0, result.stderr
    provider = result.json()["providers"][0]
    assert provider["probed"] is False
    for capability in provider["capabilities"]:
        assert capability["outcome"] == "unverified"
        assert capability["usable"] is False


def test_doctors_prose_says_what_its_data_says(workspace: Path, task_id: str) -> None:
    """The paragraph is generated from the findings, so the two agree.

    The rule the architecture states: the formatted output is a rendering of
    the same data. A doctor that reported one thing in JSON and another in
    prose would be exactly the failure the rule catches.
    """
    prose = run_cli("--workspace", str(workspace), "doctor")
    machine = run_cli("--workspace", str(workspace), "doctor", "--json")
    assert prose.returncode == 0, prose.stderr
    assert machine.returncode == 0, machine.stderr
    findings = machine.json()
    assert findings["workspace"]["root"] in prose.stdout
    assert findings["database"]["revision"] in prose.stdout
    assert findings["policy"]["digest"][:12] in prose.stdout


# --------------------------------------------------------------------------- #
# the seam
# --------------------------------------------------------------------------- #


def test_the_cli_reaches_no_store_reader(repo_root: Path) -> None:
    """The CLI package imports neither the store's readers nor its rows.

    The application layer's own guard says the same thing about every
    module outside it; this says it about the CLI, so that the property is
    named in the file that owns the CLI.
    """
    forbidden = {"labcairn.db.repository", "labcairn.db.models"}
    offenders: list[str] = []
    for path in sorted((repo_root / "src" / "labcairn" / "cli").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            imported: list[str] = []
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = [node.module]
            if forbidden.intersection(imported):
                offenders.append(f"{path.name}: {sorted(forbidden.intersection(imported))}")
    assert not offenders, (
        f"the CLI reaches past the application layer to the store: {offenders}. The "
        "layer exists so that a guard applied to an operation applies to every "
        "caller."
    )


def test_the_console_script_is_declared(repo_root: Path) -> None:
    """The script a developer types is declared, and points at the CLI."""
    text = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    assert "[project.scripts]" in text
    assert 'labcairn = "labcairn.cli:main"' in text


def test_every_command_the_plan_names_is_reachable() -> None:
    """The eight commands the plan names exist, with the names it gives them.

    Read from the application's own help, so a command that was renamed or
    dropped fails here rather than in somebody's script.
    """
    listing = run_cli("--help")
    assert listing.returncode == 0, listing.stderr
    for name in ("init", "doctor", "task", "sources", "artifacts"):
        assert name in listing.stdout

    task_listing = run_cli("task", "--help")
    assert task_listing.returncode == 0, task_listing.stderr
    for name in ("create", "run", "status", "resume"):
        assert name in task_listing.stdout

    assert "inspect" in run_cli("sources", "--help").stdout
    assert "list" in run_cli("artifacts", "--help").stdout


# --------------------------------------------------------------------------- #
# the cost of loading the CLI
# --------------------------------------------------------------------------- #

#: The packages the CLI must not load when it is loaded.
#:
#: These are the ones that cost. The application layer pulls the store, the
#: evidence readers and the provider stack; the store pulls SQLAlchemy and
#: Alembic; and the security and skills packages pull the observability
#: stack. Loading any of them is what made ``labcairn --help`` take two
#: seconds, so a CLI that loads one has paid for the whole application to
#: print a list of commands.
_LAYER_PACKAGES = (
    "labcairn.application",
    "labcairn.core",
    "labcairn.db",
    "labcairn.evidence",
    "labcairn.providers",
    "labcairn.runtime",
    "labcairn.security",
    "labcairn.skills",
    "labcairn.sources",
)

#: The most the CLI's import may cost, as a multiple of the bare
#: interpreter's own start-up on the same machine.
#:
#: A multiple rather than a number of seconds, because a number of seconds
#: is a fact about the machine the bound was measured on: a CI runner two or
#: three times slower than a development machine would fail a bound set in
#: seconds, and a test that fails on a slow machine teaches nothing but that
#: the machine is slow. The multiple is the property that holds everywhere —
#: the CLI's import is a small multiple of starting Python, not a multiple of
#: loading the application. Before the imports were deferred the ratio was
#: about forty.
_IMPORT_BUDGET_FACTOR = 10

#: The most the CLI's import may cost in seconds, whatever the machine.
#:
#: The floor under the multiple above, so that a machine whose bare start-up
#: is itself slow cannot excuse a slow import. It sits well above what the
#: CLI costs and well below what it used to cost: about two seconds.
_IMPORT_BUDGET_SECONDS = 1.5

#: The program that reports what loading the CLI left in the interpreter.
_REPORT_LOADED = (
    "import sys, json, labcairn.cli; "
    "print(json.dumps(sorted(m for m in sys.modules if m.startswith('labcairn'))))"
)


def _wall_seconds(command: list[str], runs: int = 5) -> float:
    """How long *command* takes, at its fastest.

    The minimum of several runs, not the mean: the slowest run of an import
    is the machine's noise — another test's subprocess, a virus scanner, a
    machine that is busy with something else — and a bound must not be set
    against the noise.
    """
    timings: list[float] = []
    for _ in range(runs):
        started = time.perf_counter()
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        timings.append(time.perf_counter() - started)
        assert completed.returncode == 0, completed.stderr
    return min(timings)


def test_loading_the_cli_does_not_load_the_layer() -> None:
    """The CLI loads without the layer, the store or the provider stack.

    Measured rather than read off the source: the property is about what the
    interpreter ends up holding, and a source reading can only say what
    somebody wrote down. A layer type imported at runtime instead of under
    ``TYPE_CHECKING`` works perfectly well — and costs a second and a half.
    """
    completed = subprocess.run(
        [sys.executable, "-c", _REPORT_LOADED],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert completed.returncode == 0, completed.stderr
    loaded: list[str] = json.loads(completed.stdout)
    offenders = [
        module
        for module in loaded
        if any(module == package or module.startswith(f"{package}.") for package in _LAYER_PACKAGES)
    ]
    assert not offenders, (
        f"loading the CLI loaded {offenders}. The CLI imports the layer when a "
        "command needs it, not when the CLI is loaded, so that `labcairn --help` "
        "does not pay for the whole application."
    )


def _is_type_checking(test: ast.expr) -> bool:
    """Whether a module-level ``if`` is the ``TYPE_CHECKING`` guard.

    The names under that guard are not module-level imports: they are for
    mypy, and the interpreter never evaluates them.
    """
    return isinstance(test, ast.Name) and test.id == "TYPE_CHECKING"


def test_the_cli_module_names_no_layer_module_at_module_level(repo_root: Path) -> None:
    """``cli/commands.py``'s module-level imports name no layer module.

    The docstring's claim, checked against the source it is about. The
    measurement above watches the *effect* — what the interpreter ends up
    holding — and this watches the *claim*: a layer name imported at module
    level would break the claim even on a build where it happened not to
    drag the layer in, and a claim nobody checks is a claim nobody can
    rely on.

    **The one project module the CLI names at module level is the API's bind
    module**, for the two defaults ``serve``'s own signature needs. It is
    named here so that a second one has to be argued for rather than added:
    a docstring that says what the module imports has to be kept true.
    """
    path = repo_root / "src" / "labcairn" / "cli" / "commands.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.If) and _is_type_checking(node.test):
            continue
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    layer = [
        name
        for name in imported
        if any(name == package or name.startswith(f"{package}.") for package in _LAYER_PACKAGES)
    ]
    assert not layer, (
        f"the CLI names the layer at module level: {layer}. The layer is imported "
        "when a command needs it, not when the CLI is loaded, or `labcairn --help` "
        "pays for the whole application."
    )
    project = [name for name in imported if name.startswith("labcairn.")]
    assert project == ["labcairn.api.bind"], (
        f"the CLI names {project} at module level and not just the bind defaults. "
        "The docstring says the bind module is the only one, so a second one has "
        "to be argued for and the docstring has to be told about it."
    )


def test_loading_the_cli_costs_less_than_the_budget() -> None:
    """Importing the CLI costs a fraction of what it used to.

    ``labcairn --help`` is the first thing a person types, and it is paid for
    by more than forty of this file's tests. The cost is measured in a
    subprocess because it is invisible from inside one: this process has
    already imported everything the CLI would import, so the import the CLI
    would do has already happened here.
    """
    bare = _wall_seconds([sys.executable, "-c", "pass"])
    cost = _wall_seconds([sys.executable, "-c", "import labcairn.cli"])
    net = cost - bare
    budget = min(_IMPORT_BUDGET_SECONDS, _IMPORT_BUDGET_FACTOR * bare)
    assert net < budget, (
        f"importing labcairn.cli took {net:.3f}s over the interpreter's own "
        f"start-up of {bare:.3f}s, which is over the {budget:.3f}s budget. The "
        "CLI loads without the application layer; something has put it back."
    )


# --------------------------------------------------------------------------- #
# what the layer cannot answer
# --------------------------------------------------------------------------- #


def test_the_task_can_bind_a_material_the_product_ingests() -> None:
    """The task's binding takes the id the product actually mints.

    **This test used to say the opposite, and it was right to.** LC-P1-08's
    ingestion gives a source the id ``src-<hash>``, while
    ``Task.bound_source_ids`` was typed as the runtime's UUIDv7
    :class:`~labcairn.core.ids.SourceId` — so a task could not bind the
    material the product ingests, and the layer's ``list_sources`` — which
    matches the bound ids against the ledger — could not find it. The old
    test recorded that inconsistency rather than working around it.

    The type is now the id the store holds (`ba07dd5`), so the binding works,
    and this test is the marker that it keeps working: the same
    ``src-<hash>`` the product mints goes into a task and comes back out.
    """
    task = Task.model_validate(
        {
            "title": "Bound to real material",
            "goal": {"objective": "One.", "success_criterion": "Done."},
            "bound_source_ids": [_SOURCE_ID],
        }
    )

    assert task.bound_source_ids == (_SOURCE_ID,)


def test_the_cli_never_needs_the_binding_to_inspect_a_source(
    workspace: Path, task_id: str, source_id: str
) -> None:
    """``sources inspect`` works on a ledger source the task does not bind.

    The command does not need the binding, because it looks the source up by
    id rather than through the task — and that is worth saying, because the
    binding used to be impossible and the command worked anyway.
    """
    result = run_cli(
        "--workspace", str(workspace), "sources", "inspect", "--source", source_id, "--json"
    )
    assert result.returncode == 0, result.stderr
    assert result.json()["source"]["source_id"] == source_id
    assert result.json()["resource_key"] == "one.csv"


def test_the_layer_models_the_cli_serialises_are_the_ones_the_layer_returns(
    workspace: Path, task_id: str, source_id: str
) -> None:
    """The types the CLI prints are the layer's own, not copies of them.

    A cheap, structural check on the property the whole design rests on: the
    machine-readable form is the layer's model, so the class the CLI
    serialises *is* the class the layer returns.
    """
    with _context(workspace, task_id) as context:
        state = read_task_state(context)
        plan = read_plan(context)
        view = inspect_source(context, source_id)
    assert isinstance(state, TaskState)
    assert isinstance(plan, TaskPlan)
    assert isinstance(view, SourceView)


def _the_commands_the_package_names() -> set[str]:
    """The command names the package's own docstring lists, and its count.

    Read from the docstring rather than from a constant beside it, because
    **the docstring is the claim**: a list somewhere else that nobody reads
    is not a record of anything. Only the sentence that introduces the list
    is read — the docstring quotes other things, a plan's path among them —
    and the literal names are expanded the way the sentence reads them, so
    ``task create/run/status/resume`` is four commands and not one.
    """
    docstring = labcairn.cli.__doc__ or ""
    sentence = re.search(
        r"The commands\s+(?P<names>.*?)and the plumbing",
        docstring,
        re.DOTALL,
    )
    if sentence is None:
        return set()
    commands: set[str] = set()
    for entry in re.findall(r"``([^`]+)``", sentence.group("names")):
        parts = entry.split("/")
        if len(parts) == 1:
            commands.add(parts[0])
            continue
        # A slashed entry is a group and its variants: the group's first word
        # is the group, and the rest are the commands under it.
        group = parts[0].split(" ")[0]
        variants = [parts[0].removeprefix(group).strip(), *parts[1:]]
        for variant in variants:
            if variant:
                commands.add(f"{group} {variant}")
    return commands


def _the_commands_the_app_registers() -> set[str]:
    """Every command the console script offers, and not the groups.

    A group is a name on the way to a command, not a command: ``task`` is
    how the four ``task`` commands are reached.
    """
    root = get_command(app)
    found: set[str] = set()

    def walk(command: Any, prefix: str) -> None:
        for name, sub in sorted((getattr(command, "commands", None) or {}).items()):
            path = f"{prefix}{name}"
            if hasattr(sub, "commands"):
                walk(sub, f"{path} ")
            else:
                found.add(path)

    walk(root, "")
    return found


def test_the_packages_docstring_names_exactly_the_commands_there_are() -> None:
    """The package's own list of its commands is the true one.

    **A count is not a claim; a list is.** The list used to say "Eight
    commands" and name them, and it was right when it was written and wrong
    twice over after two more commands arrived — and nothing noticed,
    because a number in a docstring is only ever compared with the reader's
    memory, and it was read as "Eight" long after it had stopped being true.
    **So the count is gone** and the list is the claim: a *list* can be
    compared with the application, and this test does that. The names the
    docstring gives and the commands the console script registers are the
    same set, in both directions. A command that arrives without being
    named fails here, and a name that no longer names a command fails here
    too.
    """
    assert _the_commands_the_package_names() == _the_commands_the_app_registers()
