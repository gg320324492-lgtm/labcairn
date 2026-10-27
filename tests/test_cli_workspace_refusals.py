"""The CLI's own workspace refusals, watched one at a time.

The API service's guards are watched in ``tests/test_api.py``. This file
watches the refusals the **CLI** owns and the API does not have: the
workspace's configuration, the operator's policy file, the providers file, and
the source roots the configuration names. Each of them is raised *before* the
application layer is reached, and each of them has one exact message.

**A witness is the product's own words.** Every test here asserts the refusal
the module writes — a sentence of it, quoted — and not "something was raised".
A test that only checked that an exception happened would pass for four
different reasons at once, and would go on passing if the message were changed
to say the opposite of what it says now.

**Neighbouring refusals are told apart by the sentence they use, or by the
file they name.** The configuration that cannot be read and the policy that
cannot be read say the same three words; what separates them is *which path
the refusal names*. The configuration's refusals — missing, unparseable, not an
object, of another schema version, of a shape this build does not understand —
each use a different sentence, and each is watched by a different test. The
policy's refusals are told apart the same way.

**The reason is part of the refusal, and a witness that does not assert it
cannot tell two refusals apart.** The command's own refusal for a source root
outside the workspace and the module's refusal for the same condition say
*the same sentence*; only the reason differs — ``invalid_arguments`` for the
command, ``workspace_unusable`` for the module — and a client that branches
on the reason must see the difference. So the witnesses here assert the
reason as well as the message.

**Most of them are watched through the command line**, because that is what an
operator meets: a refusal the CLI renders is a refusal a script can read. The
one that is not — a configuration file that is not there — is watched in
process, and the test says why: the command line cannot reach it, because the
CLI asks whether the workspace is initialised before it reads the
configuration, and refuses in another shape when it is not.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from refusal_witnesses import compared_texts

from labcairn.cli.commands import EXIT_REFUSED, PROVIDERS_FILE_NAME
from labcairn.cli.workspace import (
    CONFIG_DIR_NAME,
    CONFIG_FILE_NAME,
    CONFIG_SCHEMA_VERSION,
    POLICY_FILE_NAME,
    WorkspaceSetupError,
    locate,
    read_config,
    source_paths,
)

pytestmark = pytest.mark.negative

#: The reason the CLI gives for a workspace it cannot use.
#:
#: The CLI's own vocabulary, from :data:`labcairn.cli.models.CLI_REFUSAL_WORKSPACE_UNUSABLE`.
#: Every refusal in this file is that one: the layer was never reached, so the
#: layer's vocabulary has nothing to say about it.
WORKSPACE_UNUSABLE = "workspace_unusable"

#: The reason the CLI gives for an argument it will not act on.
#:
#: The CLI's own vocabulary, from :data:`labcairn.cli.models.CLI_REFUSAL_INVALID_ARGUMENTS`.
#: This is the reason a **command's** own refusal carries — the one the
#: command answers with, rather than the module's answer to the same
#: condition.
INVALID_ARGUMENTS = "invalid_arguments"


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


def run_cli(*args: str) -> CliResult:
    """Run the console script and return what it produced.

    ``PYTHONIOENCODING`` and ``COLUMNS`` are set for the reasons
    ``tests/test_cli.py`` sets them: a path with a non-ASCII character in it
    must not fail for the machine's locale, and Rich must not lay the output
    out for eighty columns because the child is writing to a pipe.

    The machine-readable form is used for every assertion here, so the refusal
    is read out of one JSON string rather than out of a rendered paragraph: a
    paragraph is wrapped at the terminal's width, and a phrase a test asserts
    on can be split across two lines by a width the test does not control.
    """
    script = _console_script()
    if not script.is_file():
        pytest.fail(
            f"the console script is not installed at {script}. The CLI is tested "
            "through the script a developer types, so it has to be there; run "
            "`uv sync`."
        )
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
def task_workspace(workspace: Path) -> Path:
    """A workspace the CLI itself made, holding one task.

    The task is what a task-scoped command is about, and the policy is what
    governs one, so the policy refusals are watched on a command that has
    something to govern.
    """
    result = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "create",
        "--title",
        "A task to report on",
        "--objective",
        "Establish what the corpus says about the question.",
        "--criterion",
        "A cited answer, or an honest 'not established'.",
        "--json",
    )
    assert result.returncode == 0, f"task create failed: {result.stderr}"
    return workspace


def _config_path(workspace: Path) -> Path:
    """The configuration file, at the path the product writes it."""
    return workspace / CONFIG_DIR_NAME / CONFIG_FILE_NAME


def _write_source_dirs(workspace: Path, source_dirs: list[str]) -> None:
    """The configuration the product wrote, with its source roots replaced.

    Written through the product's own file, because that is the operator's
    file: a source root is unusable because the *configuration* names it, and
    the configuration is the one place a name can carry a spelling the
    command line cannot carry — a NUL byte among them.
    """
    path = _config_path(workspace)
    config = json.loads(path.read_text(encoding="utf-8"))
    config["source_dirs"] = source_dirs
    path.write_text(json.dumps(config), encoding="utf-8")


def _policy_path(workspace: Path) -> Path:
    """The policy file, at the path the product writes it."""
    return workspace / CONFIG_DIR_NAME / POLICY_FILE_NAME


def _write_policy(workspace: Path, rules: object) -> None:
    """Write a policy file holding *rules*."""
    _policy_path(workspace).write_text(
        json.dumps({"schema_version": CONFIG_SCHEMA_VERSION, "rules": rules}),
        encoding="utf-8",
    )


def _refusal(result: CliResult) -> dict[str, Any]:
    """The refusal the CLI printed, checked to be one.

    The exit code and the reason are asserted before the message is read, so
    a test that fails says *which* of the two went wrong.
    """
    return _refusal_with_reason(result, WORKSPACE_UNUSABLE)


def _refusal_with_reason(result: CliResult, reason: str) -> dict[str, Any]:
    """The refusal the CLI printed, with the reason it must carry.

    The same three checks as :func:`_refusal`, with the reason as an
    argument. A witness that asserts only *that* something was refused cannot
    tell two refusals apart, and the reason is what a client branches on.
    """
    assert result.returncode == EXIT_REFUSED, (
        f"expected the refusal exit code {EXIT_REFUSED}, got {result.returncode}; "
        f"stderr was {result.stderr!r}"
    )
    assert "Traceback" not in result.stderr, "the refusal was raised, not rendered"
    payload: dict[str, Any] = result.json()
    assert payload["reason"] == reason, payload
    return payload


# --------------------------------------------------------------------------- #
# the configuration
# --------------------------------------------------------------------------- #


def test_a_missing_workspace_configuration_is_refused(tmp_path: Path) -> None:
    """A configuration this build cannot read is refused rather than guessed at.

    The file that is not there is named, and the operator is told what to do
    about it. A default in its place would drop the operator's source roots and
    their current task, and the run would go on against a workspace that is not
    the one on disk, saying nothing.

    **This one is watched in process, and the reason is the product's own
    shape.** The command line asks whether the workspace is initialised before
    it reads the configuration, so a directory with no configuration file is
    refused *there*, in another shape and with another message, and this
    refusal is never reached from a command. What is watched here is the
    refusal the module owns, called the way the module's own callers call it.
    """
    location = locate(tmp_path)

    with pytest.raises(WorkspaceSetupError) as refusal:
        read_config(location)

    assert str(refusal.value) == (
        f"{location.config_path} does not exist, so {location.root} is not a "
        "LabCairn workspace. Run `labcairn init` there, or point --workspace at "
        "one that is."
    )


def test_a_workspace_configuration_that_is_not_json_is_refused(workspace: Path) -> None:
    """A configuration that is not JSON is refused, and the file is named.

    The refusal quotes the parse error, because an operator who cannot see
    which file is broken cannot fix it.

    **Told apart from the configuration that is not an object** by the
    sentence: this one says the file *could not be read as JSON*, and that one
    says what the file *holds* instead.

    ``doctor`` is the command, because it is the command that reads the
    configuration: it reports the workspace's own settings, so a
    configuration it cannot read is a report it cannot make. And because it
    needs no task, a configuration that is quietly replaced by a default makes
    the command *succeed* — which is the failure this witness is for.
    """
    location = locate(workspace)
    _config_path(workspace).write_text("{ this is not json", encoding="utf-8")

    result = run_cli("--workspace", str(workspace), "doctor", "--json")

    payload = _refusal(result)
    assert f"{location.config_path} could not be read as JSON" in payload["message"]


def test_a_workspace_configuration_that_is_not_an_object_is_refused(workspace: Path) -> None:
    """A configuration that is JSON but not an object is refused.

    A JSON array, a JSON string, a JSON number: each of them parses, and none
    of them is a configuration. Reading one as a configuration would be reading
    a shape this build does not understand.

    **Told apart from the configuration that is not JSON** by the sentence:
    this one says the file *must hold a JSON object*, and that one says the
    file *could not be read as JSON*.
    """
    location = locate(workspace)
    _config_path(workspace).write_text("[]", encoding="utf-8")

    result = run_cli("--workspace", str(workspace), "doctor", "--json")

    payload = _refusal(result)
    assert f"{location.config_path} must hold a JSON object." in payload["message"]


def test_a_workspace_configuration_of_another_schema_version_is_refused(
    workspace: Path,
) -> None:
    """A configuration written by another build's schema is refused.

    The refusal names both versions: the one the file declares and the one
    this build reads. That sentence is the only thing separating the two
    schemas, because everything else about the file — its keys, its shape —
    is the same in both.

    **Told apart from the other three configuration refusals** by its
    sentence: this one names a *version*, and the others say the file is
    missing, unreadable, or not an object.
    """
    location = locate(workspace)
    config = json.loads(_config_path(workspace).read_text(encoding="utf-8"))
    config["schema_version"] = CONFIG_SCHEMA_VERSION + 1
    _config_path(workspace).write_text(json.dumps(config), encoding="utf-8")

    result = run_cli("--workspace", str(workspace), "doctor", "--json")

    payload = _refusal(result)
    assert (
        f"{location.config_path} declares schema version {CONFIG_SCHEMA_VERSION + 1}, "
        f"and this build reads version {CONFIG_SCHEMA_VERSION}."
    ) in payload["message"]


def test_a_workspace_configuration_this_build_cannot_understand_is_refused(
    workspace: Path,
) -> None:
    """A configuration whose shape this build does not know is refused.

    ``source_dirs`` is a list of names in the file and a bare string here. A
    build that read the string as a list would bind a source root named "m",
    and one that read it as nothing would bind no source root at all — and
    the operator's material would be quietly absent from every task. A
    configuration this build cannot read is refused rather than guessed at.

    **Told apart from the other four configuration refusals** by its
    sentence: this one says the file *is not a configuration this build
    understands*, and the others say the file is missing, could not be read
    as JSON, must hold a JSON object, or declares another schema version.
    """
    location = locate(workspace)
    config = json.loads(_config_path(workspace).read_text(encoding="utf-8"))
    config["source_dirs"] = "materials"
    _config_path(workspace).write_text(json.dumps(config), encoding="utf-8")

    result = run_cli("--workspace", str(workspace), "doctor", "--json")

    payload = _refusal(result)
    assert (
        f"{location.config_path} is not a workspace configuration this build understands"
    ) in payload["message"]


# --------------------------------------------------------------------------- #
# the policy
# --------------------------------------------------------------------------- #


def test_a_policy_file_that_is_not_json_is_refused(task_workspace: Path) -> None:
    """A policy file that is not JSON is refused, and the file is named.

    The posture stays safe — a policy that cannot be read denies everything —
    but the operator's own grants are gone, and the reason they are gone is
    "denied" rather than "your policy file is broken". This refusal is what
    tells them which.

    **Told apart from the configuration that is not JSON** by the file the
    refusal names: this one names ``policy.json``, that one names
    ``workspace.json``, and the three words they share are the same.
    """
    location = locate(task_workspace)
    _policy_path(task_workspace).write_text("{ this is not json", encoding="utf-8")

    result = run_cli("--workspace", str(task_workspace), "task", "status", "--json")

    payload = _refusal(result)
    assert f"{location.policy_path} could not be read as JSON" in payload["message"]


def test_a_policy_file_without_a_rules_list_is_refused(task_workspace: Path) -> None:
    """A policy file that holds no ``"rules"`` list is refused.

    A policy file is the rules and nothing else, so a file without them is a
    file this build cannot read as a policy — and it is not an empty policy
    either, which would be a strange thing for an operator to have written.

    **Told apart from the policy file that is not JSON** by the sentence:
    this one says what the file *must hold*, and that one says it could not
    be *read*.
    """
    location = locate(task_workspace)
    _policy_path(task_workspace).write_text(
        json.dumps({"schema_version": CONFIG_SCHEMA_VERSION}), encoding="utf-8"
    )

    result = run_cli("--workspace", str(task_workspace), "task", "status", "--json")

    payload = _refusal(result)
    expected = f'{location.policy_path} must hold a JSON object with a "rules" list.'
    assert expected in payload["message"]


def test_a_policy_rule_that_is_not_an_object_is_refused(task_workspace: Path) -> None:
    """A rule that is not an object is refused, and not dropped.

    Dropping it would be the quieter failure: the policy would go on holding
    the other rules, and it would **deny** what the dropped rule used to
    allow, and nothing would say so.

    **Told apart from the other three policy refusals** by its sentence: this
    one is about an *entry in* the rules list, and the others are about the
    file, about a key in a rule, and about a rule's effect.
    """
    _write_policy(task_workspace, ["not a rule"])

    result = run_cli("--workspace", str(task_workspace), "task", "status", "--json")

    payload = _refusal(result)
    expected = 'every entry in a policy file\'s "rules" list must be an object.'
    assert expected in payload["message"]


def test_an_unknown_key_in_a_policy_rule_is_refused(task_workspace: Path) -> None:
    """A key this build does not know in a rule is refused, and not dropped.

    A typo in a rule's scope would otherwise widen what the rule covers: a
    ``capabilites`` that is quietly dropped is a rule that covers every
    capability, and a rule that covers every capability is not the rule the
    operator wrote.

    **Told apart from the rule with no effect** by its sentence: this one
    names the *key* that is unknown, and that one names the *effect* that is
    missing or wrong.
    """
    _write_policy(
        task_workspace,
        [{"effect": "allow", "pattern": "output", "capabilites": ["fs.read"]}],
    )

    result = run_cli("--workspace", str(task_workspace), "task", "status", "--json")

    payload = _refusal(result)
    assert "unknown key(s) in a policy rule: capabilites" in payload["message"]


def test_a_policy_rule_with_no_effect_is_refused(task_workspace: Path) -> None:
    """A rule with no effect at all is refused.

    A rule with no effect is a rule that was meant to say something, and
    guessing which thing it was meant to say would be granting a permission
    nobody wrote down.

    **Told apart from the rule with an unknown effect** by the tail of the
    sentence: this one names the missing *key*, and that one names the value
    that is not one of the three.
    """
    _write_policy(task_workspace, [{"pattern": "output"}])

    result = run_cli("--workspace", str(task_workspace), "task", "status", "--json")

    payload = _refusal(result)
    expected = "a policy rule needs an \"effect\" of allow, ask or deny: 'effect'"
    assert expected in payload["message"]


def test_a_policy_rule_with_an_unknown_effect_is_refused(task_workspace: Path) -> None:
    """A rule whose effect is not one of the three is refused.

    A rule meant to be ALLOW read as a DENY, and a rule meant to be ASK that
    never asks, are the two failures this refusal is there to stop. The
    spelling the operator wrote is quoted back, because ``permit`` and
    ``allowed`` are the two typos this is most likely to meet.

    **Told apart from the rule with no effect** by the tail of the sentence:
    this one names the *value* that is not one of the three, and that one
    names the missing *key*.

    **The whole sentence is the expectation, not a part of it.** The refusal
    exists to tell the operator *what is wrong with their policy*, and a
    sentence that names the right value and then says something false about
    it — "'permit' is not a valid Permission (the key is 'effect')" — would
    send the operator to fix a key that is present and correct. A witness
    that accepted the sentence as a substring accepts that, so the message
    is compared whole: it must end where the product's sentence ends, with
    nothing appended to it.
    """
    _write_policy(task_workspace, [{"effect": "permit", "pattern": "output"}])

    result = run_cli("--workspace", str(task_workspace), "task", "status", "--json")

    payload = _refusal(result)
    expected = (
        'a policy rule needs an "effect" of allow, ask or deny: '
        "'permit' is not a valid Permission"
    )
    assert payload["message"] == expected


def test_a_policy_rule_that_cannot_be_read_is_refused(task_workspace: Path) -> None:
    """A rule whose scope cannot be read is refused, and not dropped.

    A rule with an **empty** scope list is a rule that was meant to say
    something and says nothing. Reading it as "any scope" would widen what
    the rule covers, and reading it as "no scope" would make it match
    nothing — and both readings are guesses about a rule the operator wrote.

    **Told apart from the other six policy refusals** by its sentence: this
    one says a rule *could not be read*, and the others say the file could
    not be read, the file must hold a rules list, an entry is not an object,
    a key is unknown, or the effect is missing or wrong.
    """
    _write_policy(
        task_workspace,
        [{"effect": "allow", "pattern": "output", "capabilities": []}],
    )

    result = run_cli("--workspace", str(task_workspace), "task", "status", "--json")

    payload = _refusal(result)
    assert "a policy rule could not be read" in payload["message"]
    assert "a rule scope may not be empty" in payload["message"]


# --------------------------------------------------------------------------- #
# the providers
# --------------------------------------------------------------------------- #


def test_a_providers_file_that_is_not_json_is_refused(workspace: Path) -> None:
    """A providers file that is not JSON is refused, and the file is named.

    The refusal quotes the parse error, because an operator who cannot see
    which file is broken cannot fix it.

    **Told apart from the configuration that is not JSON** by the file the
    refusal names: this one names ``providers.json``, that one names
    ``workspace.json``, and the three words they share are the same.
    """
    location = locate(workspace)
    (workspace / PROVIDERS_FILE_NAME).write_text("{ this is not json", encoding="utf-8")

    result = run_cli("--workspace", str(workspace), "doctor", "--json")

    payload = _refusal(result)
    expected = f"{location.root / PROVIDERS_FILE_NAME} could not be read as JSON"
    assert expected in payload["message"]


def test_a_providers_file_without_a_providers_object_is_refused(workspace: Path) -> None:
    """A providers file holding no ``"providers"`` object is refused.

    A file of providers that is not keyed by ``"providers"`` is a file this
    build cannot read as one. Reading it as an empty set of providers would
    be the quieter failure: the operator's model providers would silently
    disappear from ``doctor``'s report, and nothing would say so.

    **Told apart from the providers file that is not JSON** by the sentence:
    this one says what the file *must hold*, and that one says it could not
    be *read*.
    """
    location = locate(workspace)
    (workspace / PROVIDERS_FILE_NAME).write_text('{"models": {}}', encoding="utf-8")

    result = run_cli("--workspace", str(workspace), "doctor", "--json")

    payload = _refusal(result)
    assert (
        f'{location.root / PROVIDERS_FILE_NAME} must hold a top-level "providers" object.'
    ) in payload["message"]


# --------------------------------------------------------------------------- #
# the source roots
# --------------------------------------------------------------------------- #


def test_a_source_directory_outside_the_workspace_is_refused(
    task_workspace: Path, tmp_path: Path
) -> None:
    """A source root the workspace does not contain is refused.

    The refusal names the directory **as the operator wrote it**, because the
    operator wrote it: the configuration is the operator's file, and this is
    the one way a source root outside the workspace can reach the CLI — the
    ``--source-dir`` option refuses the same thing earlier, in the command's
    own words.

    **Two sites speak that sentence, so the sentence cannot say which site
    refused.** ``labcairn.cli.workspace.source_paths`` refuses the root the
    *configuration* names; ``labcairn.cli.commands._resolve_source_dirs``
    refuses the root the *``--source-dir`` option* names; and the two
    sentences are byte for byte the same — only the variable they interpolate
    differs. What tells them apart is the **reason code**: the workspace's
    own site refuses under ``workspace_unusable`` and the command's own site
    under ``invalid_arguments``. So this witness asserts the reason as well
    as the sentence, and it says which site it is about.

    **And it asks that site, so the binding does not rest on today's reason
    codes.** The site under test is called in process and raises the very
    sentence the command line then renders; the other site is not in the
    path at all, because ``task status`` binds the *configured* roots and
    never reads the option.

    The layer refuses it too, in different words (``Workspace.bind`` says the
    source directory "is outside the selected workspace", and says the
    *user's* selection where this says the *operator's*), so this witness
    asserts the CLI's own sentence and not merely that something was refused.
    """
    (tmp_path / "outside").mkdir()
    config = json.loads(_config_path(task_workspace).read_text(encoding="utf-8"))
    config["source_dirs"] = ["../outside"]
    _config_path(task_workspace).write_text(json.dumps(config), encoding="utf-8")

    location = locate(task_workspace)
    expected = (
        "the source directory '../outside' resolves to "
        f"{(location.root / '../outside').resolve()}, which is "
        f"outside the workspace {location.root}. A source root the workspace "
        "does not contain is a root the operator's selection does not govern."
    )

    # The site under test, asked directly: the sentence is its own.
    with pytest.raises(WorkspaceSetupError) as refusal:
        source_paths(location, read_config(location))
    assert str(refusal.value) == expected

    # And the refusal the command line renders for the same root.
    result = run_cli("--workspace", str(task_workspace), "task", "status", "--json")

    payload = _refusal(result)
    assert payload["message"] == expected


def test_a_source_directory_that_is_not_a_directory_is_refused(task_workspace: Path) -> None:
    """A source root the configuration names, that is a file, is refused.

    The configuration may name anything, and a file is not a source root.
    Binding it would give the task a root it cannot read material from, and
    the task would quietly hold nothing.

    **The sentence is the module's own, and not the command's.** The
    command refuses the same condition in its own words — *`task create`
    binds directories that are there; it does not make them* — and the two
    refusals are told apart by the words they use, which is why this
    witness quotes the module's.
    """
    config = json.loads(_config_path(task_workspace).read_text(encoding="utf-8"))
    (task_workspace / "not-a-directory").write_text("a file, not a directory", encoding="utf-8")
    config["source_dirs"] = ["not-a-directory"]
    _config_path(task_workspace).write_text(json.dumps(config), encoding="utf-8")

    result = run_cli("--workspace", str(task_workspace), "task", "status", "--json")

    payload = _refusal(result)
    assert "the source directory 'not-a-directory' is" in payload["message"]
    assert "which is not a directory. A source root is a directory." in payload["message"]


def test_a_source_directory_the_command_names_outside_the_workspace_is_refused(
    workspace: Path, tmp_path: Path
) -> None:
    """A source root the **command** names, outside the workspace, is refused.

    **The reason is the whole point of this witness.** The module's refusal
    for the same condition — a source root the *configuration* names outside
    the workspace — says the *same sentence*, and the witness above watches
    it. Only the reason differs: the command answers with
    ``invalid_arguments`` and the module answers with ``workspace_unusable``.
    A client that branches on the reason has to see the command's, because
    the command is what refused.

    So this witness asserts the reason, and not merely that something was
    refused: without the reason it would pass for the module's refusal too,
    and the difference between the two answers would go unwatched.
    """
    (tmp_path / "elsewhere").mkdir()
    result = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "create",
        "--title",
        "A task to report on",
        "--objective",
        "Establish what the corpus says about the question.",
        "--criterion",
        "A cited answer, or an honest 'not established'.",
        "--source-dir",
        "../elsewhere",
        "--json",
    )

    payload = _refusal_with_reason(result, INVALID_ARGUMENTS)
    assert "the source directory '../elsewhere' resolves to" in payload["message"]
    assert "which is outside the workspace" in payload["message"]


def test_a_source_directory_the_command_names_that_is_not_a_directory_is_refused(
    workspace: Path,
) -> None:
    """A source root the command names that is not a directory is refused.

    A file is not a source root, and the command does not make it into one.
    Dropping it would be the quieter failure: the task would be created
    without the root the operator named, and nothing would say so.

    **Told apart from the source root outside the workspace** by the
    sentence: this one says the path *is not a directory*, and that one says
    it is *outside the workspace*. Both are the command's own refusal and
    carry the command's own reason.
    """
    (workspace / "not-a-directory").write_text("a file, not a directory", encoding="utf-8")
    result = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "create",
        "--title",
        "A task to report on",
        "--objective",
        "Establish what the corpus says about the question.",
        "--criterion",
        "A cited answer, or an honest 'not established'.",
        "--source-dir",
        "not-a-directory",
        "--json",
    )

    payload = _refusal_with_reason(result, INVALID_ARGUMENTS)
    assert "the source directory 'not-a-directory' is" in payload["message"]
    assert "which is not a directory" in payload["message"]
    # The command says in its own words what it does about a directory that
    # is not there, and that is not the module's sentence.
    assert "`task create` binds directories that are there" in payload["message"]


def test_a_configured_source_directory_whose_name_cannot_be_spoken_is_refused(
    task_workspace: Path,
) -> None:
    """A configured source root whose name this build cannot speak is refused.

    **This is the crash the CLI used to have instead of this refusal.** The
    source-root handling asked the *filesystem* about the operator's name
    first, and the filesystem has no answer for a name carrying a NUL byte:
    ``Path.resolve()`` raises a bare ``ValueError`` on it — not an
    ``OSError``, and not the layer's own ``PathRefusedError`` — so it
    escaped the CLI's handler as a **traceback**: exit 1, and a stack trace
    where the program had promised a refusal.

    The product's own spelling guard answers the question the filesystem
    cannot, and **the guard is asked before the filesystem is asked at
    all**. That order is the whole of this refusal: the refusal exists
    because the question was put in the right order.
    """
    _write_source_dirs(task_workspace, ["materials\0"])

    result = run_cli("--workspace", str(task_workspace), "task", "status", "--json")

    payload = _refusal(result)
    expected = (
        "the source directory 'materials\\x00' is not a name this build can use: "
        "nul_byte: path contains a NUL byte. A source root is named by a path the "
        "workspace can speak."
    )
    assert payload["message"] == expected


def test_a_source_directory_the_command_names_that_cannot_be_spoken_is_refused(
    workspace: Path,
) -> None:
    """A source root the command names that this build cannot speak is refused.

    **The command's own source-root handling, asked the same question.** The
    command resolves the operator's name before the guard is asked, so a name
    the product cannot speak was silently bound as a different directory: on
    Windows a name ending in a dot is the same file as the name without it,
    so ``--source-dir materials.`` would have bound ``materials`` and said
    nothing.

    **The name here is one the command line can carry.** A NUL byte cannot
    cross a command line — the operating system ends the argument there —
    so the spelling that reaches the command is one the guard also refuses:
    a segment ending in a dot, which Win32 silently strips.
    """
    result = run_cli(
        "--workspace",
        str(workspace),
        "task",
        "create",
        "--title",
        "A task to report on",
        "--objective",
        "Establish what the corpus says about the question.",
        "--criterion",
        "A cited answer, or an honest 'not established'.",
        "--source-dir",
        "materials.",
        "--json",
    )

    payload = _refusal_with_reason(result, INVALID_ARGUMENTS)
    expected = (
        "the source directory 'materials.' is not a name this build can use: "
        "trailing_dot_or_space: segment 'materials.' ends in a dot or space. "
        "Win32 strips both, so 'secret.txt.' and 'secret.txt' are the same file and "
        "a rule written against one spelling would miss the other. `task create` "
        "binds source roots the workspace can speak, and it will not make one up."
    )
    assert payload["message"] == expected


# --------------------------------------------------------------------------- #
# the binding
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "arguments",
    [
        pytest.param(
            (
                "task",
                "create",
                "--title",
                "A task to report on",
                "--objective",
                "Establish what the corpus says about the question.",
                "--criterion",
                "A cited answer, or an honest 'not established'.",
            ),
            id="task_create",
        ),
        pytest.param(("task", "status"), id="task_status"),
        pytest.param(("sources", "ingest"), id="sources_ingest"),
    ],
)
def test_a_configured_source_directory_that_is_missing_is_refused(
    task_workspace: Path, arguments: tuple[str, ...]
) -> None:
    """A source root the configuration names, and that is not there, is refused.

    **This is the crash the CLI used to have instead of this refusal.** The
    layer refuses a root it cannot canonicalise with a ``ValueError`` that is
    not an ``OSError``, so the CLI's handler let it out as a **traceback**:
    exit 1, and a stack trace where the program had promised a refusal. The
    CLI's own rule is that ``EXIT_REFUSED`` is a refusal and *anything else
    that fails is a bug*.

    Three commands are watched, because they reach the binding by different
    routes and each of them used to crash: ``task create`` binds through the
    layer, ``task status`` and ``sources ingest`` bind through the CLI's own
    context.

    The refusal names the directory **as the configuration wrote it**,
    because the configuration is the operator's file, and says the directory
    is *missing* rather than that a path could not be canonicalised.
    """
    location = locate(task_workspace)
    shutil.rmtree(location.materials_path)

    result = run_cli("--workspace", str(task_workspace), *arguments, "--json")

    payload = _refusal(result)
    expected = f"the source directory 'materials' is missing: {location.materials_path}"
    assert expected in payload["message"]


def test_a_workspace_whose_output_area_cannot_be_created_is_refused(
    task_workspace: Path,
) -> None:
    """A workspace whose task output area cannot be made is refused.

    **This drives the other half of the binding's catch.** A refusal that
    catches only ``OSError`` covers a directory that cannot be written, and
    this is what reaches it: the workspace's ``output`` directory is replaced
    by a file, so creating the task's own area underneath it fails.

    The refusal names the workspace and says it could not be bound, which is
    what the operator has to act on — and it is not the missing-source-root
    refusal, which the message says outright.
    """
    location = locate(task_workspace)
    shutil.rmtree(location.output_path)
    location.output_path.write_text("a file, not a directory", encoding="utf-8")

    result = run_cli("--workspace", str(task_workspace), "task", "status", "--json")

    payload = _refusal(result)
    assert f"the workspace at {location.root} could not be bound" in payload["message"]
    assert "source directory" not in payload["message"]


def test_a_configured_source_directory_that_is_not_a_directory_is_refused(
    task_workspace: Path,
) -> None:
    """A source root the configuration names, and that is a file, is refused.

    **This is the workspace's own site, and the command's own site says the
    same words.** ``labcairn.cli.workspace.source_paths`` refuses a
    configured root that is not a directory, and
    ``labcairn.cli.commands._resolve_source_dirs`` refuses one the *option*
    names — and the two sentences are the same. Only the reason tells them
    apart: this one is the module's (``workspace_unusable``), that one is
    the command's (``invalid_arguments``).

    So this witness asserts the reason as well as the sentence, and it feeds
    the refusal the **configuration**, which is the only way to reach the
    module's site at all.

    A file where a source root should be is a routine mistake — a path left
    behind by a copy, a symlink to something that has gone — and reading it
    as a root would bind nothing while the operator's material was quietly
    absent from every task.
    """
    location = locate(task_workspace)
    (location.root / "not-a-directory").write_text("a file, not a directory", encoding="utf-8")
    config = json.loads(_config_path(task_workspace).read_text(encoding="utf-8"))
    config["source_dirs"] = ["not-a-directory"]
    _config_path(task_workspace).write_text(json.dumps(config), encoding="utf-8")

    result = run_cli("--workspace", str(task_workspace), "task", "status", "--json")

    payload = _refusal(result)
    expected = (
        f"the source directory 'not-a-directory' is {location.root / 'not-a-directory'}, "
        "which is not a directory. A source root is a directory."
    )
    assert payload["message"] == expected


# --------------------------------------------------------------------------- #
# the ledger
# --------------------------------------------------------------------------- #

#: The modules whose refusal sites this file watches, relative to the root.
#:
#: The sites are in the product's own source, so the test has to read the
#: product's own source. **Both** of the CLI's modules are here: a ledger
#: that watched one of them would leave the other's sites to a hand.
REFUSAL_MODULES: tuple[str, ...] = (
    "src/labcairn/cli/workspace.py",
    "src/labcairn/cli/commands.py",
)

#: How many sites raise ``WorkspaceSetupError`` across those modules.
#:
#: The number is the gate's bar, so it is written down here and checked
#: against the source rather than counted by reading the file and hoping. A
#: table of refusals counted by hand was wrong once — it said ten, and there
#: were thirteen — and a count is what the gate turns on.
#:
#: **Nineteen, and one of them is new.** The source-root handling now asks
#: the product's own spelling guard before it asks the filesystem, so a
#: configured source root whose name the product cannot speak is refused
#: with the module's own vocabulary rather than crashing on a bare
#: ``ValueError``. A new site is a new refusal, and a new refusal needs a
#: witness: it is in the ledger below.
REFUSAL_SITE_COUNT = 19

#: Every refusal site, and the witnesses that watch it.
#:
#: A site is named by **the module it is in**, **the function it is in** and
#: **a phrase of the sentence it writes**. The three together name one site,
#: because two sites in one function can share a prefix — ``read_config``
#: refuses a configuration that could not be read as JSON and one that could
#: not be read as a configuration, and only the sentence tells them apart.
#:
#: The phrase is also what ties a witness to a site. The test at the bottom
#: of this file checks that every site in the source matches exactly one
#: entry here, that every entry here matches exactly one site in the source,
#: and that every witness this ledger names exists in the suite *and*
#: compares the refusal with a string carrying that site's phrase. A ledger
#: that only listed the tests would be a list of claims; this one is
#: checked.
#:
#: Two sites have two witnesses. One ``raise`` refuses two different
#: mistakes — a rule with no effect and a rule with an effect this build does
#: not know — and the two are told apart by what the mistake is, not by
#: where it is refused. And a source root that is not a directory is watched
#: twice over: once by the test that names it as the root the configuration
#: binds, and once by the test that says the same words of it.
#:
#: **The enumeration in ``tests/test_cli_refusal_enumeration.py`` names the
#: same witnesses for the same sites**, and it says which witness watches
#: which site by the value the site names — the configuration's path, the
#: policy's path, the providers file's path. A witness that compares the
#: configuration's path is the witness of the configuration's refusal and
#: not of the policy's, and the two enumerations cannot disagree about it.
WATCHED_REFUSALS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "src/labcairn/cli/workspace.py",
        "read_config",
        "does not exist, so",
        ("test_a_missing_workspace_configuration_is_refused",),
    ),
    (
        "src/labcairn/cli/workspace.py",
        "read_config",
        "could not be read as JSON",
        ("test_a_workspace_configuration_that_is_not_json_is_refused",),
    ),
    (
        "src/labcairn/cli/workspace.py",
        "read_config",
        "must hold a JSON object.",
        ("test_a_workspace_configuration_that_is_not_an_object_is_refused",),
    ),
    (
        "src/labcairn/cli/workspace.py",
        "read_config",
        "is not a workspace configuration this build understands",
        ("test_a_workspace_configuration_this_build_cannot_understand_is_refused",),
    ),
    (
        "src/labcairn/cli/workspace.py",
        "read_config",
        "declares schema version",
        ("test_a_workspace_configuration_of_another_schema_version_is_refused",),
    ),
    (
        "src/labcairn/cli/workspace.py",
        "load_policy",
        "could not be read as JSON",
        ("test_a_policy_file_that_is_not_json_is_refused",),
    ),
    (
        "src/labcairn/cli/workspace.py",
        "load_policy",
        'must hold a JSON object with a "rules" list.',
        ("test_a_policy_file_without_a_rules_list_is_refused",),
    ),
    (
        "src/labcairn/cli/workspace.py",
        "_rule_from_mapping",
        "must be an object.",
        ("test_a_policy_rule_that_is_not_an_object_is_refused",),
    ),
    (
        "src/labcairn/cli/workspace.py",
        "_rule_from_mapping",
        "unknown key(s) in a policy rule",
        ("test_an_unknown_key_in_a_policy_rule_is_refused",),
    ),
    (
        "src/labcairn/cli/workspace.py",
        "_rule_from_mapping",
        'needs an "effect" of allow, ask or deny',
        (
            "test_a_policy_rule_with_no_effect_is_refused",
            "test_a_policy_rule_with_an_unknown_effect_is_refused",
        ),
    ),
    (
        "src/labcairn/cli/workspace.py",
        "_rule_from_mapping",
        "a policy rule could not be read",
        ("test_a_policy_rule_that_cannot_be_read_is_refused",),
    ),
    (
        "src/labcairn/cli/workspace.py",
        "source_paths",
        "outside the workspace",
        (
            "test_a_source_directory_outside_the_workspace_is_refused",
            "test_doctor_names_a_source_root_outside_the_workspace",
        ),
    ),
    (
        "src/labcairn/cli/workspace.py",
        "source_paths",
        "is not a name this build can use",
        ("test_a_configured_source_directory_whose_name_cannot_be_spoken_is_refused",),
    ),
    (
        "src/labcairn/cli/workspace.py",
        "source_paths",
        "is missing",
        ("test_a_configured_source_directory_that_is_missing_is_refused",),
    ),
    (
        "src/labcairn/cli/workspace.py",
        "source_paths",
        "which is not a directory",
        (
            "test_a_configured_source_directory_that_is_not_a_directory_is_refused",
            "test_a_source_directory_that_is_not_a_directory_is_refused",
        ),
    ),
    (
        "src/labcairn/cli/workspace.py",
        "bind_workspace",
        "could not be bound",
        ("test_a_workspace_whose_output_area_cannot_be_created_is_refused",),
    ),
    (
        "src/labcairn/cli/commands.py",
        "_provider_findings",
        "unknown model provider capabilit",
        ("test_an_unknown_assumed_capability_is_refused",),
    ),
    (
        "src/labcairn/cli/commands.py",
        "_provider_settings",
        "could not be read as JSON",
        ("test_a_providers_file_that_is_not_json_is_refused",),
    ),
    (
        "src/labcairn/cli/commands.py",
        "_provider_settings",
        'must hold a top-level "providers" object.',
        ("test_a_providers_file_without_a_providers_object_is_refused",),
    ),
)

#: The name of the test below, which is a witness of the ledger rather than
#: of a refusal, and so is not named by the ledger itself.
LEDGER_TEST = "test_every_refusal_site_in_the_cli_is_watched"


def _the_literal_text(node: ast.AST) -> str:
    """The text *node* writes, with the values it interpolates left out.

    The interpolated values are dropped rather than guessed at: what a site
    writes is decided by the text around them, and the text around them is
    what tells two sites apart.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            _the_literal_text(value) for value in node.values if isinstance(value, ast.Constant)
        )
    return ""


def _the_enclosing_function(functions: list[ast.FunctionDef], node: ast.stmt) -> str:
    """The name of the innermost function *node* is in."""
    owners = [
        function
        for function in functions
        if function.lineno <= node.lineno <= (function.end_lineno or function.lineno)
    ]
    if not owners:
        return "<module>"
    innermost = min(owners, key=lambda function: function.end_lineno or function.lineno)
    return innermost.name


def _the_refusal_sites(source: Path, relative: str) -> list[tuple[str, str, str]]:
    """Every site in *source* that raises ``WorkspaceSetupError``.

    Read out of the source with the parser, so a site is a site however it
    is written: a site added in a shape nobody expected is still found here.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    sites: list[tuple[str, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        call = node.exc
        if not isinstance(call, ast.Call) or not call.args:
            continue
        if not (isinstance(call.func, ast.Name) and call.func.id == "WorkspaceSetupError"):
            continue
        sites.append(
            (
                relative,
                _the_enclosing_function(functions, node),
                _the_literal_text(call.args[0]),
            )
        )
    return sites


def _the_tests_in_the_suite(repo_root: Path) -> dict[str, ast.FunctionDef]:
    """Every test in the suite, by name.

    The witnesses are not all in this file — one of them is in
    ``tests/test_cli.py`` — so the ledger looks them up wherever they are.
    """
    tests: dict[str, ast.FunctionDef] = {}
    for path in sorted((repo_root / "tests").glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                tests[node.name] = node
    return tests


def _the_texts_a_test_compares_with(function: ast.FunctionDef) -> list[str]:
    """The strings *function* compares the refusal with.

    **A mention is not a comparison.** The docstring is left out: it is prose
    *about* the refusal, and a phrase in prose is not a witness. And a string
    the test merely *holds* is not a witness either: a test that binds the
    refusal's sentence to a name and never compares it watches nothing, and
    an enumeration that accepted the mention would let that test stand for a
    witness forever. That was measured: the phrase stayed in the witness, the
    comparison went, and the whole suite was green.

    So the rule is the shared one, in :mod:`tests.refusal_witnesses`: the
    sentence has to be **compared** inside an assertion — put beside the
    product's output as an operand of a comparison, or as an argument of a
    call.
    """
    return compared_texts(function)


def test_every_refusal_site_in_the_cli_is_watched(repo_root: Path) -> None:
    """Every site that raises ``WorkspaceSetupError`` is watched, and the count is right.

    **The count was wrong once.** A table of the workspace module's refusals
    said ten; the module raised at thirteen sites, and three of them — a
    configuration of another shape, a rule whose scope is empty, and a
    workspace that could not be bound — had no witness at all. So the sites
    are not counted by hand any more: this test reads the CLI's own source,
    finds every ``raise WorkspaceSetupError`` in it, and checks that each
    one is watched by a test named in the ledger above.

    **How a site is found.** A site is a ``raise`` whose exception is a call
    to ``WorkspaceSetupError``, read out of the source with the parser.

    **How a site is recognised as watched.** A site is named by the module
    it is in, the function it is in and a phrase of the sentence it writes;
    the ledger pairs that name with the tests that watch it; and this test
    checks the pairing three ways. Every site in the source matches exactly
    one entry of the ledger — so a site added without a witness is caught.
    Every entry of the ledger matches exactly one site in the source — so
    an entry left behind by a changed sentence is caught. And every test the
    ledger names exists in the suite *and* **compares** the refusal with a
    string carrying that site's phrase — so a witness that stopped asserting
    its refusal is caught, and so is a witness that was deleted or renamed.

    **"Compares", and not "mentions".** The check used to ask whether the
    phrase was *among the witness's string constants*, and that is not the
    same question: a witness that keeps the sentence as a constant and stops
    comparing it (``_ = expected``) still has the phrase, so the check
    passed, the witness watched nothing, and the whole suite was green. The
    check now asks that the sentence be compared inside an assertion — put
    beside the product's output as an operand of a comparison, or as an
    argument of a call. See :mod:`tests.refusal_witnesses`, which both
    enumerations read, so that they cannot drift apart on what a witness is.

    The count is asserted as well, because the count is what the gate turns
    on: a site added on purpose has to be written down here as well as
    watched.

    **What this does not cover, said here so that it is not a surprise.**
    The command's own refusals — the ones raised as ``_refuse(...)`` with
    the command's own reason — are not counted here, because they are not
    ``WorkspaceSetupError`` and they are not refusals about the workspace.
    They are watched by ``tests/test_cli_refusal_enumeration.py``, which
    enumerates every refusal the CLI raises — those and these — and requires
    a witness of its own for each. The sentence that used to stand here —
    *"They are watched by the command's own tests"* — was a claim, and it was
    false: nine of the seventeen had no witness at all.
    """
    sites: list[tuple[str, str, str]] = []
    for relative in REFUSAL_MODULES:
        sites.extend(_the_refusal_sites(repo_root / relative, relative))
    assert len(sites) == REFUSAL_SITE_COUNT, (
        f"the CLI raises WorkspaceSetupError at {len(sites)} sites, not "
        f"{REFUSAL_SITE_COUNT}. A new site is a new refusal, and a new refusal "
        "needs a witness: add it to the ledger and to this file."
    )

    ledger: dict[tuple[str, str, str], tuple[str, ...]] = {
        (module, function, phrase): witnesses
        for module, function, phrase, witnesses in WATCHED_REFUSALS
    }
    assert len(ledger) == len(WATCHED_REFUSALS), "two ledger entries name the same site"

    for key in ledger:
        found = [
            site for site in sites if site[0] == key[0] and site[1] == key[1] and key[2] in site[2]
        ]
        assert found, (
            f"the ledger names a refusal in {key[1]} that {key[0]} does not raise: "
            f"{key[2]!r}. The sentence the site writes has changed, and the ledger "
            "has to be told."
        )
        assert len(found) == 1, (
            f"the refusal {key[2]!r} in {key[1]} matches more than one site: "
            f"{found}. A site is named by its module, its function and its "
            "sentence, and this one does not name one."
        )

    unwatched = [
        site
        for site in sites
        if not any(site[0] == key[0] and site[1] == key[1] and key[2] in site[2] for key in ledger)
    ]
    assert not unwatched, (
        f"these refusals are raised and watched by no test: {unwatched}. Every "
        "site in the CLI needs a witness, and the ledger is where the witness "
        "is named."
    )

    tests = _the_tests_in_the_suite(repo_root)
    named: list[str] = []
    for (module, function, phrase), witnesses in ledger.items():
        for witness in witnesses:
            assert witness in tests, (
                f"the ledger names {witness!r} as the witness for the refusal in "
                f"{module}::{function}, and there is no such test in the suite."
            )
            compared = _the_texts_a_test_compares_with(tests[witness])
            assert any(phrase in text for text in compared), (
                f"{witness} does not compare the refusal with {phrase!r}, so it "
                f"does not watch the refusal in {module}::{function}."
            )
            named.append(witness)

    assert len(named) == len(set(named)), (
        "a test is named for two refusals. A witness that watches two refusals "
        "cannot be told, by this ledger, which refusal it is watching."
    )
