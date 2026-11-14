"""`tests/test_cli.py`'s section, split out for the shard partition.

The section is byte-identical to the monolith's; the rig comes from
`test_cli_support`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from test_cli_support import (
    _HASH,
    _context,
    run_cli,
)
from test_cli_support import (
    artifacts as _artifacts_fixture,
)
from test_cli_support import (
    material as _material_fixture,
)
from test_cli_support import (
    source_id as _source_id_fixture,
)
from test_cli_support import (
    task_id as _task_id_fixture,
)
from test_cli_support import (
    workspace as _workspace_fixture,
)

from labcairn.application import inspect_source, list_artifacts, read_plan, read_task_state
from labcairn.reports.receipt import ArtifactReceipt

artifacts = _artifacts_fixture
material = _material_fixture
source_id = _source_id_fixture
task_id = _task_id_fixture
workspace = _workspace_fixture


artifacts = _artifacts_fixture
source_id = _source_id_fixture
task_id = _task_id_fixture
workspace = _workspace_fixture

pytestmark = pytest.mark.e2e


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
