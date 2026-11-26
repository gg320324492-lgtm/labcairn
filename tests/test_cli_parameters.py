"""`tests/test_cli.py`'s section, split out for the shard partition.

The section is byte-identical to the monolith's; the rig comes from
`test_cli_support`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_cli_support import (
    artifacts as _artifacts_fixture,
)
from test_cli_support import (
    material as _material_fixture,
)
from test_cli_support import (
    run_cli,
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

from labcairn.cli.commands import EXIT_REFUSED
from labcairn.cli.workspace import CONFIG_DIR_NAME, locate, read_config
from labcairn.workspace.readonly import MAX_SOURCE_READ_BYTES

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
    # The binding is the task's and the ingestion is this run's; the binding is
    # the union of the two, so it always holds what the run ingested. They are
    # equal here because `task create` already ingested and bound this same
    # material — and they are *not* the same field.
    assert set(report["bound_source_ids"]) >= set(report["source_ids"])
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

    The bytes are never read -- the refusal is on the size -- so the file is
    made by seeking past the end and writing one byte, and the arrangement
    cannot skip on a platform where symlinks are unavailable.

    **And the size is derived from the ceiling it means to cross, not written
    out.** This arrangement was once a hardcoded 72 MB against a 64 MB limit;
    when the limit moved to 96 MB the file stayed where it was, the refusal
    stopped happening, and the witness went red for a reason that had nothing
    to do with the property under test. A fixture that names a number the
    product owns is a fixture that decouples the moment that number moves.
    """
    (workspace / "materials" / "one.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (workspace / "other").mkdir()
    oversized = workspace / "other" / "oversized.csv"
    with oversized.open("wb") as handle:
        handle.seek(MAX_SOURCE_READ_BYTES)
        handle.write(b"x")
    assert oversized.stat().st_size == MAX_SOURCE_READ_BYTES + 1, (
        "the arrangement must be one byte past the ceiling the product names"
    )
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
    # The refusal says in its own words that material could not be read,
    # and not only which file could not be.
    assert "file(s) of the supplied material could not be read" in refusal["message"]


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

    **The refusal's own words, and the whole of them.** The refusal names
    the capability that is not known and lists the ones that are, because
    the operator has to be able to act on it; a witness that accepted a
    part of the sentence would go on passing if the rest of it were changed
    to say something else.
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
    # The refusal says what was wrong and what the capabilities are, and the
    # witness quotes the refusal's own words rather than only the spelling
    # the operator got wrong. The enumeration in
    # tests/test_cli_refusal_enumeration.py is what asked for this: a
    # witness that quotes only the value watches the value, not the refusal.
    #
    # **Both forms are checked, and that is not belt and braces.** The CLI
    # renders the same refusal twice -- once as prose for a person and once
    # as a machine-readable payload -- and F32 was the finding that the two
    # forms can disagree while the suite is green. A witness that reads only
    # one of them watches only that one.
    assert "unknown model provider capability: telepathy." in result.stdout
    assert "The capabilities are" in result.stdout
    payload = result.json()
    assert "unknown model provider capability" in payload["message"], payload
    assert "The capabilities are" in payload["message"], payload


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
    from labcairn.cli.workspace import SESSION_TOKEN_FILE_NAME

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
    # The refusal says in its own words that no task was named, and not
    # only which option would name one.
    assert "no task was named" in result.json()["message"]


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
    # The refusal says in its own words what a task id is, and not only
    # which format it is in.
    assert "task ids are UUIDv7" in result.stderr


# --------------------------------------------------------------------------- #
# taking a source back
# --------------------------------------------------------------------------- #


def test_sources_remove_takes_the_source_out_of_the_ledger(workspace: Path) -> None:
    """``sources remove`` takes a source back, and the ledger says so.

    **What would make this red.** A command that reported success without
    taking the row out would leave the operator believing the material was
    gone while the row went on naming a path that is not there -- which is
    the gap the command exists to close. The proof is the ledger itself: the
    source is no longer there to be inspected.
    """
    (workspace / "materials" / "one.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    created = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "create",
        "--title",
        "Taking a source back",
        "--objective",
        "One.",
        "--criterion",
        "Done.",
        "--json",
    )
    assert created.returncode == 0, created.stderr
    ingested = run_cli("--workspace", str(workspace), "sources", "ingest", "--json")
    assert ingested.returncode == 0, ingested.stderr
    source = ingested.json()["source_ids"][0]

    removed = run_cli(
        "--workspace", str(workspace), "sources", "remove", "--source", source, "--json"
    )
    assert removed.returncode == 0, removed.stderr
    assert removed.json()["source_id"] == source

    inspected = run_cli(
        "--workspace", str(workspace), "sources", "inspect", "--source", source, "--json"
    )
    assert inspected.returncode == EXIT_REFUSED
    assert inspected.json()["reason"] == "source_not_found"


def test_sources_remove_refuses_a_source_the_ledger_does_not_hold(workspace: Path) -> None:
    """A source that is not there is refused, and the command says which.

    **What would make this red.** A command that reported success for a
    source it could not find would tell an operator the material was taken
    back when nothing happened at all -- and the row they wanted gone would
    still be there. The refusal carries the layer's own reason, so a script
    reads one refusal format whichever surface produced it.
    """
    (workspace / "materials" / "one.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    created = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "create",
        "--title",
        "Taking nothing back",
        "--objective",
        "One.",
        "--criterion",
        "Done.",
        "--json",
    )
    assert created.returncode == 0, created.stderr

    result = run_cli(
        "--workspace",
        str(workspace),
        "sources",
        "remove",
        "--source",
        "src-0000000000000000",
        "--json",
    )
    assert result.returncode == EXIT_REFUSED
    assert result.json()["reason"] == "source_not_found"
    assert "src-0000000000000000" in result.json()["message"]
