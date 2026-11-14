"""`tests/test_cli.py`'s section, split out for the shard partition.

The section is byte-identical to the monolith's; the rig comes from
`test_cli_support`.
"""

from __future__ import annotations

import json
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
