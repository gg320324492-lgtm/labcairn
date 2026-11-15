"""`tests/test_cli.py`'s section, split out for the shard partition.

The section is byte-identical to the monolith's; the rig comes from
`test_cli_support`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from test_cli_support import (
    _SOURCE_ID,
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
from typer.main import get_command

import labcairn.cli
from labcairn.application import inspect_source, read_plan, read_task_state
from labcairn.application.sources import SourceView
from labcairn.application.stages import TaskPlan
from labcairn.application.tasks import TaskState
from labcairn.cli.commands import EXIT_REFUSED, app
from labcairn.runtime.lifecycle import Task

artifacts = _artifacts_fixture
material = _material_fixture
source_id = _source_id_fixture
task_id = _task_id_fixture
workspace = _workspace_fixture


artifacts = _artifacts_fixture
material = _material_fixture
source_id = _source_id_fixture
task_id = _task_id_fixture
workspace = _workspace_fixture

pytestmark = pytest.mark.e2e


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


def test_task_report_refuses_a_task_with_nothing_to_carry_and_writes_nothing(
    workspace: Path, task_id: str, source_id: str
) -> None:
    """``task report`` is the layer's report operation, and its refusal is its own.

    **What is proved here is the plumbing, not a report.** The task under test has
    no evidence record, and the document builder refuses a document with nothing
    under any heading, so what comes back is ``report_content_refused`` — the
    layer's reason, in the CLI's refusal shape, with ``EXIT_REFUSED`` rather than a
    zero the caller might read as success. **The second half is the one that
    matters**: a refusal that left a half-written report in the output area would
    be an artefact the ledger does not support, and `artifacts list` would show it.

    **The success path at a surface** is
    :func:`test_task_claim_makes_the_task_reportable`: the product records the
    claim (``docs/RELEASE-NOTES.md`` §2.2) and the report is rendered from it.
    What is proved *here* is the other half — that a task with no record is
    refused, with the layer's reason, and nothing is left behind.
    """
    result = run_cli("--workspace", str(workspace), "task", "report", "--path", "report", "--json")
    assert result.returncode == EXIT_REFUSED, result.stdout
    payload = result.json()
    assert payload["reason"] == "report_content_refused"
    assert "Nothing was written" in payload["message"]

    listed = run_cli("--workspace", str(workspace), "artifacts", "list", "--json")
    assert listed.returncode == 0, listed.stderr
    assert listed.json() == [], "a refused report left an artefact behind"

    forms = sorted(
        path.name for path in (workspace / "output" / task_id).rglob("report*") if path.is_file()
    )
    assert forms == [], f"the output area holds {forms}"


def test_task_report_refuses_a_template_that_does_not_exist(workspace: Path, task_id: str) -> None:
    """One template exists; asking for another is refused, not silently replaced.

    **The distinction a caller needs**: an unknown template is the caller's error,
    so the reason is not the content's refusal and the message names the template
    that was asked for. Rendering the default instead would be the CLI deciding
    what the person meant.
    """
    result = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "report",
        "--template",
        "no-such-template",
        "--json",
    )
    assert result.returncode == EXIT_REFUSED, result.stdout
    payload = result.json()
    assert "no-such-template" in payload["message"]
    assert payload["reason"] != "report_content_refused", (
        "the request was refused before the document was built, so the reason must say so"
    )
