"""The clean-clone developer launch, on its own, and the gaps it found.

``tests/test_smoke_path.py`` runs the whole demonstration. This file checks
the launch it starts with, separately: that a checkout can be launched into a
working workspace, with no network and no credential, by the console script a
developer would type.

**The launch is the acceptance clause's first sentence** -- *"clean clone
developer launch with working smoke path"* -- and it is worth a file of its
own, because a launch that needs a credential or a network is a launch that
cannot be repeated on another machine.

**Three tests here are expected to fail.** They record defects found in code
this task does not own, and each says what the defect is and where it is.
They are marked ``xfail(strict=True)``: the suite stays green, and the day
the defect is fixed the test passes and the strict marker turns that into a
failure until the marker is removed. A defect recorded as a skip would go on
being skipped after it was fixed, which is the opposite of what a record is
for.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.exc import OperationalError

from labcairn.api.app import create_app
from labcairn.cli.workspace import application_context, locate, read_config
from labcairn.core.ids import TaskId
from labcairn.db import create_db_engine
from labcairn.db.migrations import head_revision


#: The console script a developer types, as this interpreter would find it.
#: Beside the running interpreter rather than on ``PATH``: the test must
#: exercise the script the project installs, and ``PATH`` is the machine's
#: business.
def _console_script() -> Path:
    name = "labcairn.exe" if os.name == "nt" else "labcairn"
    return Path(sys.executable).parent / name


def run_cli(
    workspace: Path,
    *arguments: str,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """The console script, and what it produced.

    ``PYTHONIOENCODING`` and ``COLUMNS`` are set because the child's output
    encoding and terminal width are otherwise the machine's business.
    """
    script = _console_script()
    if not script.is_file():
        pytest.fail(
            f"the console script is not installed at {script}. The CLI is launched "
            "through the script a developer types, so it has to be there; run "
            "`uv sync`."
        )
    child_environment = dict(os.environ)
    child_environment["PYTHONIOENCODING"] = "utf-8"
    child_environment["COLUMNS"] = "200"
    if environment is not None:
        child_environment.update(environment)
    return subprocess.run(
        [str(script), "--workspace", str(workspace), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=child_environment,
        timeout=300,
    )


@pytest.fixture
def launched(tmp_workspace: Path) -> Path:
    """A workspace the CLI itself made."""
    result = run_cli(tmp_workspace, "init")
    assert result.returncode == 0, f"init failed: {result.stderr}"
    return tmp_workspace


@pytest.mark.integration
def test_the_console_script_is_where_a_developer_would_type_it() -> None:
    """The project installs a console script, and it is the one under test.

    A launch that had to be ``python -m labcairn.cli`` would be a different
    claim from one a developer types.
    """
    assert _console_script().is_file(), f"no console script at {_console_script()}; run `uv sync`"


@pytest.mark.integration
def test_a_clean_workspace_launches(launched: Path) -> None:
    """``labcairn init`` makes a workspace, a migrated database and a policy.

    The database is at the newest migration rather than merely present: a
    launch that made a database the current build cannot read is not a launch.
    """
    result = run_cli(launched, "init", "--json")
    assert result.returncode != 0, "init made a second workspace over the first"

    location = locate(launched)
    config = read_config(location)
    assert config.source_dirs == ("materials",), (
        f"the launch bound {config.source_dirs} rather than the source root"
    )
    assert location.database_path.is_file(), "the launch made no database"
    assert location.policy_path.is_file(), "the launch wrote no policy"
    assert location.materials_path.is_dir(), "the launch made no source root"

    doctor = run_cli(launched, "doctor", "--json")
    assert doctor.returncode == 0, doctor.stderr
    findings: dict[str, Any] = json.loads(doctor.stdout)
    assert findings["database"]["at_head"] is True, (
        f"the database is at {findings['database']['revision']}, not at {head_revision()}"
    )
    assert findings["workspace"]["initialised"] is True
    assert findings["providers"] == [], "the launch configured a model provider"


@pytest.mark.integration
def test_the_launch_needs_no_credential(launched: Path) -> None:
    """The launch works with every credential removed from the environment.

    The environment is *scrubbed* rather than merely empty: a key inherited
    from the developer's shell would otherwise make a launch that needs it
    look like one that does not.
    """
    scrubbed = {
        name: value
        for name, value in os.environ.items()
        if not name.endswith(("_API_KEY", "_TOKEN", "_SECRET"))
    }
    scrubbed = {name: value for name, value in scrubbed.items() if "KEY" not in name}

    for arguments in (("init",), ("doctor", "--json")):
        result = run_cli(
            launched.parent / "scrubbed",
            *arguments,
            environment={**scrubbed, "PATH": os.environ.get("PATH", "")},
        )
        assert result.returncode == 0, (
            f"the launch needed a credential: {arguments} -> {result.stderr[-400:]}"
        )


@pytest.mark.integration
def test_the_launch_makes_no_network_call(tmp_workspace: Path) -> None:
    """The launch works with every proxy pointed at a closed port.

    A library that honours the proxy variables cannot reach anything through
    them, so a launch that succeeded with the proxies pointing at a closed
    port made no outbound request through one. It is not a proof that no
    socket was opened -- nothing short of a sandbox proves that -- but it is
    the check the project's own "no network" claim can be made against.
    """
    closed = "http://127.0.0.1:9"
    environment = {
        "HTTP_PROXY": closed,
        "HTTPS_PROXY": closed,
        "ALL_PROXY": closed,
        "http_proxy": closed,
        "https_proxy": closed,
        "all_proxy": closed,
        "NO_PROXY": "",
        "no_proxy": "",
    }
    result = run_cli(tmp_workspace, "init", environment=environment)
    assert result.returncode == 0, f"the launch tried the network: {result.stderr[-400:]}"
    doctor = run_cli(tmp_workspace, "doctor", "--json", environment=environment)
    assert doctor.returncode == 0, f"the launch tried the network: {doctor.stderr[-400:]}"


# --------------------------------------------------------------------------- #
# the gaps the launch found
# --------------------------------------------------------------------------- #


@pytest.mark.integration
@pytest.mark.xfail(
    strict=True,
    reason=(
        "labcairn/cli/workspace.py: the CLI's task create binds a source "
        "*directory* and never a source id, so a task made through the CLI "
        "carries an empty bound_source_ids and the layer's list_sources finds "
        "nothing. The layer's create_task is the only caller that can bind a "
        "material."
    ),
)
def test_the_cli_can_bind_a_material_to_a_task(tmp_workspace: Path) -> None:
    """``labcairn task create --source-dir`` binds the material it names.

    The desired behaviour, which the product does not have yet: the task
    should hold the ids of the materials it ingested.
    """
    materials = tmp_workspace / "materials"
    materials.mkdir(parents=True, exist_ok=True)
    (materials / "one.csv").write_text("a,b\n1,2\n", encoding="utf-8")

    result = run_cli(
        tmp_workspace,
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
    task: dict[str, Any] = json.loads(result.stdout)
    assert task["bound_source_ids"], (
        "the task holds no material, although the CLI was told where the material is"
    )


@pytest.mark.integration
@pytest.mark.xfail(
    strict=True,
    reason=(
        "labcairn/cli/workspace.py: the CLI's doctor looks for the API's "
        "session token at <workspace>/.labcairn/api-token, and the API writes "
        "it to <workspace>/.labcairn/session-token. The two names do not "
        "match, so doctor never reports a session that exists."
    ),
)
def test_the_doctor_reports_the_api_session_token(launched: Path) -> None:
    """``labcairn doctor`` reports the session the running service minted.

    The desired behaviour, which the product does not have yet: the CLI
    should find the token the API wrote.
    """
    location = locate(launched)
    config = read_config(location)
    with application_context(location, config, _a_task(launched)) as context:
        create_app(context)

    result = run_cli(launched, "doctor", "--json")
    assert result.returncode == 0, result.stderr
    findings: dict[str, Any] = json.loads(result.stdout)
    assert findings["api_session"]["present"] is True, (
        "the service is running and wrote its token, and doctor did not report it"
    )


@pytest.mark.integration
@pytest.mark.xfail(
    strict=True,
    reason=(
        "labcairn/db/session.py: every transaction is opened with BEGIN "
        "IMMEDIATE, and the service's session lives as long as the service "
        "does, so the service holds SQLite's write lock between requests and "
        "a second process -- the CLI -- is refused with 'database is locked'."
    ),
)
def test_the_service_does_not_hold_the_store_while_it_is_running(
    launched: Path,
) -> None:
    """A second process may open a transaction while the service is running.

    The desired behaviour, which the product does not have yet: the CLI and
    the local API have to be usable against one workspace at the same time,
    because G4's exit test compares what they say.
    """
    location = locate(launched)
    config = read_config(location)
    with application_context(location, config, _a_task(launched)) as context:
        create_app(context)
        engine = create_db_engine(location.database_path, busy_timeout_ms=250)
        try:
            with engine.connect() as other:
                other.exec_driver_sql("BEGIN IMMEDIATE")
        except OperationalError:
            pytest.fail("the service holds the store's write lock")
        finally:
            engine.dispose()


def _a_task(workspace: Path) -> TaskId:
    """A task in the workspace, made by the CLI."""
    result = run_cli(
        workspace,
        "task",
        "create",
        "--title",
        "A task",
        "--objective",
        "One.",
        "--criterion",
        "Done.",
        "--json",
    )
    assert result.returncode == 0, result.stderr
    task: dict[str, Any] = json.loads(result.stdout)
    return TaskId(task["task_id"])
