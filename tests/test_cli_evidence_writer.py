"""`tests/test_cli.py`'s section, split out for the shard partition.

The section is byte-identical to the monolith's; the rig comes from
`test_cli_support`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from test_cli_support import (
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

from labcairn.application import list_source_addresses
from labcairn.cli.commands import EXIT_REFUSED
from labcairn.evidence.store import load_task_records

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
# the evidence writer
# --------------------------------------------------------------------------- #


def _ingest(workspace: Path) -> str:
    """Ingest the material through the CLI, and return the one source's id."""
    result = run_cli("--workspace", str(workspace), "sources", "ingest", "--json")
    assert result.returncode == 0, result.stderr
    source_ids = result.json()["source_ids"]
    assert len(source_ids) == 1, source_ids
    return str(source_ids[0])


def _addresses(workspace: Path, source_id: str) -> list[dict[str, Any]]:
    """The addresses `sources addresses --json` reports."""
    result = run_cli(
        "--workspace", str(workspace), "sources", "addresses", "--source", source_id, "--json"
    )
    assert result.returncode == 0, result.stderr
    return list(result.json())


def test_sources_addresses_is_the_layers_own_listing(
    workspace: Path, task_id: str, material: Path
) -> None:
    """``sources addresses --json`` is the layer's ``SourceAddress``, field for field.

    The listing is what a claim is recorded against, so the surface's list and
    the layer's must be one list: a key the CLI printed that the layer does not
    hold would be an address the claim then refuses.
    """
    source_id = _ingest(workspace)

    reported = run_cli(
        "--workspace", str(workspace), "sources", "addresses", "--source", source_id, "--json"
    )

    assert reported.returncode == 0, reported.stderr
    with _context(workspace, task_id) as context:
        expected = [
            address.model_dump(mode="json") for address in list_source_addresses(context, source_id)
        ]
    assert reported.json() == expected
    assert reported.json(), "the ingestion yielded no address"


def test_task_claim_makes_the_task_reportable(
    workspace: Path, task_id: str, material: Path
) -> None:
    """The success path §2.2 was about, through the CLI end to end.

    The material is ingested, an address is read, the claim is recorded and the
    report is rendered — every step through the console script a person types,
    and no test-written record anywhere.
    """
    source_id = _ingest(workspace)
    address = next(item for item in _addresses(workspace, source_id) if item["text"].strip() == "2")

    claimed = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "claim",
        "--source",
        source_id,
        "--address",
        address["locator_key"],
        "--kind",
        "numeric",
        "--value",
        "2",
        "--unit",
        "dimensionless",
        "--json",
    )

    assert claimed.returncode == 0, claimed.stderr
    recorded = claimed.json()
    assert recorded["record"]["status"] == "extracted"
    assert recorded["record"]["kind"] == "numeric"
    assert recorded["record"]["value"] == 2.0
    assert recorded["record"]["source_content_hash"]
    assert recorded["anchor_id"]

    reported = run_cli("--workspace", str(workspace), "task", "report", "--json")
    assert reported.returncode == 0, reported.stderr
    assert reported.json()["resource_key"] == "report"

    listed = run_cli("--workspace", str(workspace), "artifacts", "list", "--json")
    assert listed.returncode == 0, listed.stderr
    assert listed.json(), "the rendered report is not in the ledger"


def test_task_claim_renders_the_layers_refusal_for_an_address_nothing_answers(
    workspace: Path, task_id: str, material: Path
) -> None:
    """An address the material does not answer is refused by name, and writes nothing."""
    source_id = _ingest(workspace)

    claimed = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "claim",
        "--source",
        source_id,
        "--address",
        "k=3:csv|r=2:99|c=1:a",
        "--kind",
        "numeric",
        "--value",
        "2",
        "--unit",
        "dimensionless",
        "--json",
    )

    assert claimed.returncode == EXIT_REFUSED, claimed.stdout
    assert claimed.json()["reason"] == "address_not_found"
    assert "nothing was written" in claimed.json()["message"].lower()

    with _context(workspace, task_id) as context:
        connection = context.store.session.connection()
        assert load_task_records(connection, str(context.task_id)) == ()


def test_task_claim_refuses_a_kind_the_record_model_does_not_have(
    workspace: Path, task_id: str, material: Path
) -> None:
    """An unknown kind is the caller's error, and the CLI says so rather than crashing."""
    source_id = _ingest(workspace)

    claimed = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "claim",
        "--source",
        source_id,
        "--address",
        "k=3:csv|r=2:1|c=1:a",
        "--kind",
        "assertion",
        "--json",
    )

    assert claimed.returncode == EXIT_REFUSED, claimed.stdout
    assert claimed.json()["reason"] == "invalid_arguments"
    assert "assertion" in claimed.json()["message"]
    # The refusal says in its own words that the kind is not one, and names the
    # kinds there are, so a caller can pick one.
    assert "is not an evidence kind" in claimed.json()["message"]
    assert "numeric" in claimed.json()["message"]


def test_approval_request_refuses_arguments_that_are_not_one_json_object(
    workspace: Path,
) -> None:
    """The consent binds the digest of the arguments, so they are stated as one object.

    A list parses as JSON and is still not the object the digest is taken
    over, so the refusal is the caller's error and says what the run expects.
    """
    result = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "approval-request",
        "--capability",
        "analysis.run",
        "--root",
        "source:0",
        "--resource-key",
        "one.csv",
        "--arguments-json",
        "[1,2]",
        "--json",
    )

    assert result.returncode == EXIT_REFUSED, result.stdout
    assert result.json()["reason"] == "invalid_arguments"
    assert "--arguments-json is not one JSON object" in result.json()["message"]
    assert "the arguments must be one JSON object" in result.json()["message"]


def test_approval_grant_refuses_an_id_that_is_not_an_approval_id(workspace: Path) -> None:
    """A typo in an approval id is answered as one, before the task is opened."""
    approval_id = "01-not-a-uuid"
    result = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "approval-grant",
        approval_id,
        "--json",
    )

    assert result.returncode == EXIT_REFUSED, result.stdout
    assert result.json()["reason"] == "invalid_arguments"
    assert "approval ids are UUIDv7" in result.json()["message"]
    assert approval_id in result.json()["message"]


def test_the_figure_refuses_parameters_that_are_not_one_json_object(workspace: Path) -> None:
    """The operator's argument model reads one object, and the CLI states that first."""
    result = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "figure",
        "--path",
        "one.csv",
        "--operator",
        "labcairn.analysis.mean",
        "--recipe",
        "recipe.json",
        "--parameters-json",
        "[1,2]",
        "--approval",
        "01-not-a-uuid",
        "--json",
    )

    assert result.returncode == EXIT_REFUSED, result.stdout
    assert result.json()["reason"] == "invalid_arguments"
    assert "--parameters-json is not one JSON object" in result.json()["message"]
    assert "the parameters must be one JSON object" in result.json()["message"]


def test_the_figure_refuses_an_approval_id_that_is_not_one(workspace: Path) -> None:
    """The consent a figure is drawn under is named by an id, and a typo is the caller's."""
    approval = "01-not-a-uuid"
    result = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "figure",
        "--path",
        "one.csv",
        "--operator",
        "labcairn.analysis.mean",
        "--recipe",
        "recipe.json",
        "--parameters-json",
        "{}",
        "--approval",
        approval,
        "--json",
    )

    assert result.returncode == EXIT_REFUSED, result.stdout
    assert result.json()["reason"] == "invalid_arguments"
    assert "pass --approval with the id" in result.json()["message"]
    assert approval in result.json()["message"]


def test_a_reconcile_that_names_no_operation_id_is_refused(workspace: Path) -> None:
    """The operation a crash left open is named by its id, and a typo says so."""
    operation_id = "not-an-operation"
    result = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "reconcile",
        operation_id,
        "--expected-sha256",
        "0" * 64,
        "--json",
    )

    assert result.returncode == EXIT_REFUSED, result.stdout
    assert result.json()["reason"] == "invalid_arguments"
    assert "is not an operation id" in result.json()["message"]
    assert operation_id in result.json()["message"]


#: A chart recipe the CLI can draw from: the three parts, with the axes naming
#: columns the selection holds.
_RECIPE_TEXT = """{
  "schema_version": 1,
  "data": {
    "operator": "labcairn.analysis.mean@1.0.0",
    "parameters": {},
    "selection": {
      "source": "materials/one.csv",
      "columns": ["a"],
      "rows": {"start": 2, "end": 3},
      "missing": "exclude"
    }
  },
  "encoding": {
    "mark": "bar",
    "x": "a",
    "y": "a",
    "title": "The a column",
    "x_label": "a",
    "y_label": "mean a",
    "caption": "The mean of the a column."
  },
  "output": {"format": "svg", "dpi": 100}
}
"""


def test_the_cli_asks_for_consent_and_records_the_answer(workspace: Path) -> None:
    """The consent chain, through the installed console script.

    **Why it is one test and not two**: `approval-request` writes a question and
    `approval-grant` answers it, and neither means anything alone — the thing the
    pair has to produce is an approval whose state the task's own record shows, so
    the witness reads the state back through a third command rather than trusting
    what the second one printed.
    """
    created = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "create",
        "--title",
        "Ask and answer",
        "--objective",
        "One question.",
        "--criterion",
        "An answer.",
        "--json",
    )
    assert created.returncode == 0, created.stderr

    # The approval is asked for over the four fields the run will state, because
    # the digest is taken over exactly those (ADR-0012 constraint 7): leaving the
    # recipe or the parameters out is a different approval, and the run says so.
    arguments = (
        '{"path":"one.csv","operator_id":"labcairn.analysis.mean",'
        '"recipe":"recipe.json","parameters":{"selection":{'
        '"kind":"range","source_id":"00000000-0000-7000-8000-000000000001",'
        '"content_sha256":"' + "0" * 64 + '","columns":["a"],'
        '"rows":{"kind":"range","start":2,"end":3},"missing":"exclude"}}}'
    )
    requested = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "approval-request",
        "--capability",
        "analysis.run",
        "--root",
        "source:0",
        "--resource-key",
        "one.csv",
        "--arguments-json",
        arguments,
        "--minutes",
        "30",
        "--json",
    )
    assert requested.returncode == 0, requested.stderr
    asked = requested.json()
    assert asked["approval"]["state"] == "pending"
    approval_id = asked["approval"]["approval_id"]

    granted = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "approval-grant",
        approval_id,
        "--json",
    )
    assert granted.returncode == 0, granted.stderr
    assert granted.json()["approval"]["state"] == "granted"

    state = run_cli("--workspace", str(workspace), "task", "status", "--json")
    assert state.returncode == 0, state.stderr
    recorded = [
        approval for approval in state.json()["approvals"] if approval["approval_id"] == approval_id
    ]
    assert [approval["state"] for approval in recorded] == ["granted"], (
        "the task's own record, not the grant command's stdout, is the answer"
    )


def test_the_figure_command_refuses_before_the_run_with_the_layers_reasons(
    workspace: Path, task_id: str
) -> None:
    """Every CLI refusal on the way to a figure names a reason a script can branch on.

    Four windows, in the order the layer reaches them: an approval id that is not
    one is the caller's typo, answered before the task is opened; a recipe that is
    not there is `recipe_unreadable`, answered before the consent is looked at; an
    argument set that is not one JSON object is the caller's error again, named as
    such; and a selection naming material the ledger never ingested is
    `source_not_found`, which the run answers before it reaches the consent — so
    nothing a human granted is spent on a run that could not have started.
    """

    def figure(*args: str) -> Any:
        return run_cli(
            "--workspace",
            str(workspace),
            "task",
            "figure",
            "--path",
            "one.csv",
            "--operator",
            "labcairn.analysis.mean",
            "--recipe",
            "recipe.json",
            "--parameters-json",
            """{"selection":{"kind":"range","source_id":"00000000-0000-7000-8000-000000000001","content_sha256":"0000000000000000000000000000000000000000000000000000000000000000","columns":["a"],"rows":{"kind":"range","start":2,"end":3},"missing":"exclude"}}""",
            *args,
            "--json",
        )

    not_an_id = figure("--approval", "01-not-a-uuid")
    assert not_an_id.returncode == EXIT_REFUSED, not_an_id.stdout
    assert not_an_id.json()["reason"] == "invalid_arguments"

    unknown = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "approval-grant",
        "01-not-a-uuid",
        "--json",
    )
    assert unknown.returncode == EXIT_REFUSED, unknown.stdout
    assert unknown.json()["reason"] == "invalid_arguments"

    # No recipe file yet: that is the first thing the seam answers, before the
    # consent is even looked at, so a made-up approval id is not the reason.
    from labcairn.core.ids import new_id

    no_recipe = figure("--approval", str(new_id()))
    assert no_recipe.returncode == EXIT_REFUSED, no_recipe.stdout
    assert no_recipe.json()["reason"] == "recipe_unreadable", no_recipe.stdout

    # With the recipe readable and the operator's parameters well-formed, the run
    # reaches its material and stops there: the selection names a source the ledger
    # never ingested. **The order is the claim** — a run that cannot resolve its
    # material never gets as far as the consent, so nothing is spent on it.
    (workspace / "recipe.json").write_text(_RECIPE_TEXT, encoding="utf-8")
    unresolved = figure("--approval", str(new_id()))
    assert unresolved.returncode == EXIT_REFUSED, unresolved.stdout
    assert unresolved.json()["reason"] == "source_not_found", unresolved.stdout

    bad_json = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "approval-request",
        "--capability",
        "analysis.run",
        "--root",
        "source:0",
        "--resource-key",
        "one.csv",
        "--arguments-json",
        "[1,2]",
        "--json",
    )
    assert bad_json.returncode == EXIT_REFUSED, bad_json.stdout
    assert bad_json.json()["reason"] == "invalid_arguments"
