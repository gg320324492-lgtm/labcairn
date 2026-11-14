"""`tests/test_cli.py`'s section, split out for the shard partition.

The section is byte-identical to the monolith's; the rig comes from
`test_cli_support`.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from test_cli_support import (
    CliResult,
    run_cli,
)
from test_cli_support import (
    task_id as _task_id_fixture,
)
from test_cli_support import (
    workspace as _workspace_fixture,
)

from labcairn.cli.commands import EXIT_REFUSED
from labcairn.cli.workspace import CONFIG_DIR_NAME, CONFIG_FILE_NAME, locate, read_config

task_id = _task_id_fixture
workspace = _workspace_fixture


task_id = _task_id_fixture
workspace = _workspace_fixture

pytestmark = pytest.mark.e2e


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


def test_init_refuses_a_path_that_is_not_a_directory(tmp_path: Path) -> None:
    """``init`` refuses a path that is a file.

    A workspace is a directory, and a file cannot become one. The refusal
    says so in the command's own words, and the enumeration in
    ``tests/test_cli_refusal_enumeration.py`` is what asks for the sentence
    to be quoted rather than only the exit code.
    """
    root = tmp_path / "a-file"
    root.write_text("a file, not a directory", encoding="utf-8")

    result = run_cli("--workspace", str(root), "init", "--json")

    assert result.returncode == EXIT_REFUSED
    payload = result.json()
    assert payload["reason"] == "invalid_arguments"
    assert "exists and is not a directory, so it cannot be a workspace" in payload["message"]


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


def _set_source_dirs(workspace: Path, source_dirs: list[str]) -> None:
    """The configuration the product wrote, with its source roots replaced.

    Written through the product's own file, because that is the operator's
    file: a source root is unusable because the *configuration* names it.
    """
    path = workspace / CONFIG_DIR_NAME / CONFIG_FILE_NAME
    config = json.loads(path.read_text(encoding="utf-8"))
    config["source_dirs"] = source_dirs
    path.write_text(json.dumps(config), encoding="utf-8")


#: The Unicode block Rich draws its tables and panels with.
#:
#: **They are the layout, not the words.** A finding too long for the
#: terminal's width is folded across lines, and the border characters fall
#: in the middle of the sentence the diagnostic wrote. A test that asserts
#: on a phrase has to take the borders out first, or it asserts on where
#: the width put a line break — which is a property of the machine and not
#: of the diagnostic.
_BOX_CHARACTERS = str.maketrans("", "", "".join(chr(code) for code in range(0x2500, 0x2580)))


def _the_doctor_says(workspace: Path) -> tuple[dict[str, Any], str]:
    """What ``doctor`` says about the workspace: its JSON, and its prose.

    **The prose is normalised** — the borders are taken out and the words
    are put back together — so that a test asserts on what the diagnostic
    says rather than on how the terminal's width laid it out.
    """
    machine = run_cli("--workspace", str(workspace), "doctor", "--json")
    assert machine.returncode == 0, machine.stderr
    prose = run_cli("--workspace", str(workspace), "doctor")
    assert prose.returncode == 0, prose.stderr
    return machine.json(), " ".join(prose.stdout.translate(_BOX_CHARACTERS).split())


def _a_task_create(workspace: Path) -> CliResult:
    """``task create``, which binds the workspace's source roots.

    The command that reaches the binding: a task-scoped command with no task
    selected refuses for a different reason, and the point of these tests is
    what the commands say about a source root they cannot bind.
    """
    return run_cli(
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


def test_doctor_does_not_call_a_workspace_with_a_missing_source_root_fine(
    workspace: Path,
) -> None:
    """``doctor`` names a source root that is not there, and does not call the workspace fine.

    A configured source root that is not there is a workspace the module
    refuses to bind: every task-scoped command refuses it with it. So a
    diagnostic that reported the workspace as initialised and said nothing
    about the root would be reporting a workspace as fine that no command can
    use — and the operator would get no warning before the refusal.

    The finding names the root, because a name is what an operator can act
    on, and it says **which of the ways** the root is unusable — here,
    *missing*. The command still reports rather than refuses: a diagnostic
    that refuses to run on the thing that is broken is not a diagnostic.
    """
    shutil.rmtree(workspace / "materials")

    payload, prose = _the_doctor_says(workspace)

    assert payload["workspace"]["initialised"] is True
    assert payload["workspace"]["unusable_source_roots"] == [
        {"name": "materials", "problem": "missing"}
    ]
    assert "materials" in prose
    assert "missing" in prose
    assert "(initialised)" not in prose

    refused = _a_task_create(workspace)
    assert refused.returncode == EXIT_REFUSED
    assert "is missing" in refused.json()["message"]


def test_doctor_names_a_source_root_that_is_a_file_as_not_a_directory(
    workspace: Path,
) -> None:
    """A source root that is a file is reported as a file, not as missing.

    **The diagnostic and the refusal must not contradict each other about
    the same source root.** The root is there — it is a file — so reporting
    it as *missing* would send the operator to look for something that is
    not gone.
    """
    (workspace / "not-a-directory").write_text("a file, not a directory", encoding="utf-8")
    _set_source_dirs(workspace, ["not-a-directory"])

    payload, prose = _the_doctor_says(workspace)

    assert payload["workspace"]["unusable_source_roots"] == [
        {"name": "not-a-directory", "problem": "not a directory"}
    ]
    assert "not a directory" in prose
    assert "missing" not in prose

    refused = _a_task_create(workspace)
    assert refused.returncode == EXIT_REFUSED
    assert "which is not a directory" in refused.json()["message"]


def test_doctor_names_a_source_root_outside_the_workspace(
    workspace: Path,
) -> None:
    """A source root the workspace does not contain is reported at all.

    **This is the case the diagnostic used to miss entirely.** The finding
    was a list of the roots that were not directories on disk, so a root
    outside the workspace — which is not a directory on disk either, but
    which the *commands* refuse for a different reason — was reported as
    fine, and the diagnostic said the workspace was initialised while every
    task-scoped command refused it.
    """
    _set_source_dirs(workspace, ["../outside"])

    payload, prose = _the_doctor_says(workspace)

    assert payload["workspace"]["unusable_source_roots"] == [
        {"name": "../outside", "problem": "outside the workspace"}
    ]
    assert "outside the workspace" in prose
    assert "(initialised)" not in prose

    refused = _a_task_create(workspace)
    assert refused.returncode == EXIT_REFUSED
    assert "which is outside the workspace" in refused.json()["message"]


def test_doctor_names_a_source_root_whose_name_cannot_be_spoken(
    workspace: Path,
) -> None:
    """A source root this build cannot speak is reported, and refused.

    **The fourth way, and the one the crash came from.** A name carrying a
    NUL byte is not a directory the commands can refuse in the ordinary way:
    the filesystem's answer to it is a bare ``ValueError``, which is a
    crash. The spelling guard answers it instead, and the diagnostic has to
    say the same thing the refusal does.
    """
    _set_source_dirs(workspace, ["materials\0"])

    payload, prose = _the_doctor_says(workspace)

    assert payload["workspace"]["unusable_source_roots"] == [
        {"name": "materials\0", "problem": "unusable name"}
    ]
    assert "unusable name" in prose
    assert "(initialised)" not in prose

    refused = _a_task_create(workspace)
    assert refused.returncode == EXIT_REFUSED
    assert "is not a name this build can use" in refused.json()["message"]


def test_doctor_calls_a_workspace_with_usable_source_roots_fine(
    workspace: Path,
) -> None:
    """A workspace whose source roots are usable is called fine.

    **The other half of the property.** A diagnostic that called every
    workspace unusable would be as wrong as one that called this one fine.
    """
    payload, prose = _the_doctor_says(workspace)

    assert payload["workspace"]["unusable_source_roots"] == []
    assert "(initialised)" in prose
    assert "unusable" not in prose


def test_a_task_scoped_command_refuses_a_workspace_that_is_not_initialised(
    tmp_path: Path,
) -> None:
    """A workspace that is not a workspace is refused, and named as such.

    ``doctor`` reports a workspace that is not there as a finding, because a
    diagnostic that refuses to run on the thing that is broken is not a
    diagnostic. A task-scoped command has nothing to report: it refuses, and
    the refusal says which directory is not a workspace and what to do about
    it.

    **The sentence is the command's own, and not the module's.** The module
    refuses a *configuration file* that is missing in its own words, and the
    two refusals are told apart by the words they use.
    """
    root = tmp_path / "not-a-workspace"

    result = run_cli("--workspace", str(root), "task", "status", "--json")

    assert result.returncode == EXIT_REFUSED
    payload = result.json()
    assert payload["reason"] == "workspace_not_initialised"
    assert "is not a LabCairn workspace: there is no" in payload["message"]


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
