"""The commands, and the plumbing they share.

Every command's data comes from the application layer. A command here decides
*what* to ask and *how to draw the answer*; it never reads the store, never
reaches past the layer, and never computes a thing the layer would compute.
The one thing it constructs for the layer is the store handle, because the
handle is what the layer consumes and the surface's only job is to supply it.

**The machine-readable form and the rendered form come from one model.** Each
command builds a value — the layer's own where the layer has one — and then
either serialises it or draws it. There is no path where the prose is parsed
to produce the JSON, because the prose is produced *after* the JSON could have
been written.

**A refusal is rendered, not raised.** The layer's
:class:`~labcairn.application.ApplicationRefusedError` becomes a message naming
what was refused and a non-zero exit, never a traceback. A script tells a
refusal from a crash by the exit code alone: :data:`EXIT_REFUSED` is a
refusal, and anything else that fails is a bug.

**The options are declared with ``Annotated`` rather than as defaults.**
Typer's older spelling puts a call in the argument default, and ruff's
bugbear rule (B008) is right that a call in a default is a call that happens
at import time. The annotation form keeps the default a value and the option
beside it, and it is the form this project's lint rules can be left to.

**The layer is imported when a command needs it, not when the CLI is loaded.**
``labcairn --help`` is the first thing a person types, and it must not cost
two seconds: importing the application layer takes about that, because the
layer imports the store, the evidence readers and the provider stack. So no
layer module is named at module level — every layer name is imported
*inside* the command that uses it — and the module-level imports of this
module, outside the standard library and Typer, are exactly these:
:mod:`labcairn.api.bind`, for the two defaults ``serve``'s own signature
needs. Everything that package imports is the standard library, so naming it
costs the CLI nothing it was trying to avoid.

**That is only possible because the command line does not mention the layer.**
Typer builds the command line from a command's *parameters*, and every
parameter here is a plain type — ``str``, ``Path``, ``bool`` — so no layer
type is needed to draw the help. The layer's types appear in annotations only,
and ``from __future__ import annotations`` leaves those as strings; the ones
that are never evaluated at runtime live under ``TYPE_CHECKING``, where mypy
reads them and the interpreter does not.
"""

from __future__ import annotations

import ipaddress
import json
import socket
import uuid
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, NoReturn, cast
from urllib.parse import urlsplit

import typer

from labcairn.api.bind import DEFAULT_BIND_HOST, DEFAULT_BIND_PORT

if TYPE_CHECKING:
    from fastapi import FastAPI
    from rich.console import Console, RenderableType

    from labcairn.application import ApplicationContext, MaterialIngested
    from labcairn.application.sources import SourceView
    from labcairn.application.stages import StageOutcome, TaskPlan
    from labcairn.application.tasks import TaskState
    from labcairn.cli.models import (
        CapabilityFinding,
        DoctorReport,
        ProviderFinding,
        ServiceStarting,
        SourceRootFinding,
    )
    from labcairn.cli.workspace import WorkspaceConfig, WorkspaceLocation
    from labcairn.core.ids import TaskId
    from labcairn.providers.capabilities import Capability, ProviderCapabilities
    from labcairn.providers.credentials import ProviderSettings
    from labcairn.security.paths import CanonicalPath

#: The exit code a refusal carries.
#:
#: Not 1, because 1 is what an unhandled exception carries and a script must
#: be able to tell "the layer said no" from "the program is broken" without
#: reading the message. Not 2, because 2 is Click's own usage-error code and
#: means the command was never run.
EXIT_REFUSED = 3

#: The exit code a usage error carries. Click's own.
EXIT_USAGE = 2

#: The file a workspace's model providers are configured in.
#:
#: The product's own format — :func:`labcairn.providers.credentials.
#: load_providers_config` reads it — so the CLI does not invent a second one.
PROVIDERS_FILE_NAME = "providers.json"

#: The option every command shares, declared once.
WorkspaceOption = Annotated[
    Path | None,
    typer.Option(
        "--workspace",
        "-w",
        help="The workspace directory. The one root every command is bound to.",
    ),
]

#: The machine-readable form, declared once.
JsonOption = Annotated[
    bool,
    typer.Option(
        "--json",
        help="Print the machine-readable form instead of the rendered one.",
    ),
]

#: Which task a command is about, declared once.
TaskOption = Annotated[
    str | None,
    typer.Option(
        "--task",
        help="The task the command is about. Defaults to the workspace's current task.",
    ),
]


@dataclass(frozen=True, slots=True)
class CliOptions:
    """What the root callback decided, passed to every command.

    The workspace path is a *selection*, made once at the top of the command
    line so that every subcommand judges the same directory. It is the
    explicit root selection ADR-0003 §C5 asks for; the default is the
    process's working directory, which is a convenience and not an inference —
    the path is still named, and still checked.
    """

    workspace: Path


app = typer.Typer(
    name="labcairn",
    help="LabCairn — a local-first research workspace.",
    no_args_is_help=True,
    add_completion=False,
)
task_app = typer.Typer(help="Create, run, inspect and resume a task.", no_args_is_help=True)
sources_app = typer.Typer(help="Inspect the material a task is bound to.", no_args_is_help=True)
artifacts_app = typer.Typer(help="List what a task has produced.", no_args_is_help=True)

app.add_typer(task_app, name="task")
app.add_typer(sources_app, name="sources")
app.add_typer(artifacts_app, name="artifacts")


@app.callback()
def _root(
    ctx: typer.Context,
    workspace: Annotated[
        Path | None,
        typer.Option(
            "--workspace",
            "-w",
            help="The workspace directory. The one root every command is bound to.",
        ),
    ] = None,
) -> None:
    """The options every command shares."""
    ctx.obj = CliOptions(workspace=workspace if workspace is not None else Path.cwd())


# --------------------------------------------------------------------------- #
# plumbing
# --------------------------------------------------------------------------- #


def _options(ctx: typer.Context) -> CliOptions:
    """The root callback's decision, as the command sees it."""
    return cast(CliOptions, ctx.obj)


def _console() -> Console:
    """The console a human reads.

    Standard output, because a command's result is its output; the refusals
    go to standard error, so a script that ignores the exit code still does
    not mistake a refusal for a result.
    """
    from rich.console import Console

    return Console()


@contextmanager
def _refusals(as_json: bool) -> Iterator[None]:
    """Render a refusal instead of letting it out.

    Both the layer's refusals and the CLI's own two conditions come out of
    here, so every failure a command can have has one rendering, one exit
    code and one JSON shape.

    **A path the workspace binds cannot be resolved is a refusal too.** The
    layer refuses a root it cannot canonicalise with
    :class:`~labcairn.security.paths.PathRefusedError`, which is a
    ``ValueError`` and not an ``OSError``, so a handler that caught only the
    latter let it out as a traceback. A traceback is a crash, and this module's
    own rule is that a crash is a bug.
    """
    from labcairn.application import ApplicationRefusedError
    from labcairn.cli.models import CLI_REFUSAL_WORKSPACE_UNUSABLE, emit_refusal
    from labcairn.cli.workspace import WorkspaceSetupError
    from labcairn.security.paths import PathRefusedError

    try:
        yield
    except ApplicationRefusedError as error:
        payload = error.to_payload()
        emit_refusal(payload["reason"], payload["message"], as_json=as_json)
        raise typer.Exit(code=EXIT_REFUSED) from None
    except WorkspaceSetupError as error:
        emit_refusal(
            CLI_REFUSAL_WORKSPACE_UNUSABLE,
            str(error),
            as_json=as_json,
        )
        raise typer.Exit(code=EXIT_REFUSED) from None
    except PathRefusedError as error:
        emit_refusal(
            CLI_REFUSAL_WORKSPACE_UNUSABLE,
            f"the workspace could not be bound: {error}",
            as_json=as_json,
        )
        raise typer.Exit(code=EXIT_REFUSED) from None


def _refuse(reason: str, message: str, *, as_json: bool) -> NoReturn:
    """Refuse, and end the command."""
    from labcairn.cli.models import emit_refusal

    emit_refusal(reason, message, as_json=as_json)
    raise typer.Exit(code=EXIT_REFUSED)


def _require_workspace(location: WorkspaceLocation, *, as_json: bool) -> WorkspaceConfig:
    """The workspace's configuration, or a refusal naming what is missing."""
    from labcairn.cli.models import CLI_REFUSAL_WORKSPACE_NOT_INITIALISED
    from labcairn.cli.workspace import is_initialised, read_config

    if not is_initialised(location):
        _refuse(
            CLI_REFUSAL_WORKSPACE_NOT_INITIALISED,
            f"{location.root} is not a LabCairn workspace: there is no "
            f"{location.config_path}. Run `labcairn init` there, or point "
            "--workspace at one that is.",
            as_json=as_json,
        )
    return read_config(location)


def _select_task(
    config: WorkspaceConfig,
    requested: str | None,
    *,
    as_json: bool,
) -> TaskId:
    """Which task the command is about.

    The explicit ``--task`` wins; otherwise the workspace's current task. A
    workspace with neither is a usage problem rather than a refusal by the
    layer — but it is reported in the refusal shape so that a caller reads
    one failure format, and it carries its own reason so the two are
    distinguishable.
    """
    from labcairn.cli.models import (
        CLI_REFUSAL_INVALID_ARGUMENTS,
        CLI_REFUSAL_NO_TASK_SELECTED,
    )
    from labcairn.core.ids import TaskId, is_uuid7

    chosen = requested if requested is not None else config.current_task
    if chosen is None:
        _refuse(
            CLI_REFUSAL_NO_TASK_SELECTED,
            "no task was named. Pass --task <task-id>, or run `labcairn task "
            "create` to make one and make it the workspace's current task.",
            as_json=as_json,
        )
    if not is_uuid7(chosen):
        _refuse(
            CLI_REFUSAL_INVALID_ARGUMENTS,
            f"{chosen!r} is not a task id: task ids are UUIDv7.",
            as_json=as_json,
        )
    return TaskId(uuid.UUID(chosen))


# --------------------------------------------------------------------------- #
# init
# --------------------------------------------------------------------------- #


@app.command()
def init(
    ctx: typer.Context,
    as_json: JsonOption = False,
) -> None:
    """Create a workspace, and say what it made.

    A workspace is a directory, a database, a source directory and a policy.
    This command makes them; it never makes them over an existing workspace,
    because a workspace holds a task's history and a second `init` must not
    be able to leave two of them disagreeing about what the workspace is.
    """
    from labcairn.cli import render
    from labcairn.cli.models import (
        CLI_REFUSAL_INVALID_ARGUMENTS,
        CLI_REFUSAL_WORKSPACE_EXISTS,
        WorkspaceInitialised,
        emit_model,
    )
    from labcairn.cli.workspace import (
        DEFAULT_POLICY_RULES,
        WorkspaceConfig,
        is_initialised,
        load_policy,
        locate,
        write_config,
        write_policy,
    )
    from labcairn.db.migrations import (
        MigrationsUnavailableError,
        current_revision,
        upgrade_to_head,
    )

    options = _options(ctx)
    location = locate(options.workspace)
    with _refusals(as_json):
        if location.root.exists() and not location.root.is_dir():
            _refuse(
                CLI_REFUSAL_INVALID_ARGUMENTS,
                f"{location.root} exists and is not a directory, so it cannot be a workspace.",
                as_json=as_json,
            )
        if is_initialised(location) or location.database_path.exists():
            _refuse(
                CLI_REFUSAL_WORKSPACE_EXISTS,
                f"{location.root} already holds a LabCairn workspace, and `init` does "
                "not overwrite an existing one. Use the workspace as it is, or "
                "choose another directory.",
                as_json=as_json,
            )

        created: list[str] = []
        location.root.mkdir(parents=True, exist_ok=True)
        created.append(str(location.root))
        location.materials_path.mkdir(parents=True, exist_ok=True)
        created.append(str(location.materials_path))
        location.output_path.mkdir(parents=True, exist_ok=True)
        created.append(str(location.output_path))

        try:
            upgrade_to_head(location.database_path)
        except MigrationsUnavailableError as error:
            _refuse(
                CLI_REFUSAL_INVALID_ARGUMENTS,
                f"the database could not be created: {error}",
                as_json=as_json,
            )
        created.append(str(location.database_path))

        write_policy(location, DEFAULT_POLICY_RULES)
        created.append(str(location.policy_path))

        config = WorkspaceConfig(
            schema_version=1,
            database=location.database_path.name,
            source_dirs=(location.materials_path.name,),
            current_task=None,
        )
        write_config(location, config)
        created.append(str(location.config_path))

        model = WorkspaceInitialised(
            root=str(location.root),
            database_path=str(location.database_path),
            migration_revision=current_revision(location.database_path) or "none",
            source_dirs=config.source_dirs,
            created=tuple(created),
            policy_digest=load_policy(location).digest(),
        )
    if as_json:
        emit_model(model)
    else:
        _console().print(render.render_initialised(model))


# --------------------------------------------------------------------------- #
# doctor
# --------------------------------------------------------------------------- #


@app.command()
def doctor(
    ctx: typer.Context,
    as_json: JsonOption = False,
    probe: Annotated[
        bool,
        typer.Option(
            "--probe",
            help=(
                "Ask the configured model providers what they can do, by making real "
                "requests. Costs money; without it the capabilities are reported as "
                "declared but unverified."
            ),
        ),
    ] = False,
    assume_capability: Annotated[
        list[str] | None,
        typer.Option(
            "--assume-capability",
            help=(
                "Treat a model provider capability as supported, whatever was "
                "observed. May be given more than once."
            ),
        ),
    ] = None,
    show_token: Annotated[
        bool,
        typer.Option(
            "--show-token",
            help="Print the local API's session token, if one has been written.",
        ),
    ] = False,
) -> None:
    """Report what the workspace, the store, the policy and the providers are.

    The findings are data and the prose is drawn from them, so the two cannot
    disagree. This is the command that most wants to be a paragraph, and the
    one the architecture's rule catches; the way out is to make the paragraph
    generated rather than written.

    **A workspace that cannot be used is reported, not called fine.** Every
    configured source root the commands will refuse is named in the findings,
    together with **which of the ways** it is unusable — missing, not a
    directory, outside the workspace, or a name this build cannot speak —
    because the module refuses to bind a workspace that names one, and a
    diagnostic that said nothing about it would be saying the workspace is
    fine when no command can use it. The command still reports: a
    diagnostic that refuses to run on the thing that is broken is not a
    diagnostic.
    """
    from labcairn.cli import render
    from labcairn.cli.models import emit_model
    from labcairn.cli.workspace import is_initialised, locate, read_config

    options = _options(ctx)
    location = locate(options.workspace)
    with _refusals(as_json):
        config = read_config(location) if is_initialised(location) else None
        model = _doctor_report(
            location,
            config,
            probe=probe,
            assume_capability=tuple(assume_capability or ()),
            show_token=show_token,
        )
    if as_json:
        emit_model(model)
    else:
        _console().print(render.render_doctor(model))


def _doctor_report(
    location: WorkspaceLocation,
    config: WorkspaceConfig | None,
    *,
    probe: bool,
    assume_capability: tuple[str, ...],
    show_token: bool,
) -> DoctorReport:
    """Everything doctor found, assembled from the workspace's own files."""
    from labcairn.cli.models import (
        ApiSessionFinding,
        DatabaseFinding,
        DoctorReport,
        PolicyFinding,
        WorkspaceFinding,
    )
    from labcairn.cli.workspace import load_policy
    from labcairn.db.migrations import current_revision

    database_path = location.root / (config.database if config is not None else "labcairn.db")
    present = database_path.is_file()
    revision = current_revision(database_path) if present else None
    database = DatabaseFinding(
        path=str(database_path),
        present=present,
        revision=revision,
        at_head=present and revision == _head_revision(),
    )

    policy = load_policy(location)
    policy_finding = PolicyFinding(
        source=str(location.policy_path) if location.policy_path.is_file() else "default (no file)",
        digest=policy.digest(),
        rules=tuple(rule.render() for rule in policy.rules),
    )

    workspace_finding = WorkspaceFinding(
        root=str(location.root),
        initialised=config is not None,
        source_dirs=config.source_dirs if config is not None else (),
        unusable_source_roots=_unusable_source_roots(location, config),
        output_root=str(location.output_path),
        current_task=config.current_task if config is not None else None,
    )

    session = ApiSessionFinding(
        path=str(location.token_path),
        present=location.token_path.is_file(),
        token=_read_token(location) if show_token else None,
    )

    return DoctorReport(
        workspace=workspace_finding,
        database=database,
        policy=policy_finding,
        providers=_provider_findings(location, probe=probe, assume_capability=assume_capability),
        api_session=session,
    )


def _unusable_source_roots(
    location: WorkspaceLocation,
    config: WorkspaceConfig | None,
) -> tuple[SourceRootFinding, ...]:
    """The configured source roots the commands will refuse, and how.

    **A source root the commands will refuse is a workspace that cannot be
    bound.** The module refuses it — ``labcairn.cli.workspace.source_paths``
    refuses a root that is missing, one that is a file, one the workspace
    does not contain, and one whose name this build cannot speak — so every
    task-scoped command refuses the workspace with it. A diagnostic that
    reported the workspace as initialised and said nothing about the root
    would be reporting a workspace as fine that no command can use.

    **Every way, and each one named.** The finding used to be a list of
    names, computed as "not a directory on disk", which is two conditions
    under one word and neither of them the word the refusal used: a source
    root that was a file was reported as *missing*, and a source root the
    workspace did not contain was not reported at all — so the diagnostic
    said the workspace was initialised while every task-scoped command
    refused it.

    The answer is computed by the same function the commands' refusals are
    computed by, so the diagnostic and the refusal cannot disagree about the
    same source root.

    The names are the ones the configuration writes, because those are the
    names the operator has to act on.
    """
    from labcairn.cli.models import SourceRootFinding
    from labcairn.cli.workspace import source_root_problem

    if config is None:
        return ()
    findings: list[SourceRootFinding] = []
    for relative in config.source_dirs:
        problem = source_root_problem(location, relative)
        if problem is not None:
            findings.append(SourceRootFinding(name=problem.name, problem=problem.kind.value))
    return tuple(findings)


def _head_revision() -> str:
    """The newest revision the repository knows about."""
    from labcairn.db.migrations import MigrationsUnavailableError, head_revision

    try:
        return head_revision()
    except MigrationsUnavailableError:
        return "none"


def _read_token(location: WorkspaceLocation) -> str | None:
    """The API's session token, if the API has written one."""
    if not location.token_path.is_file():
        return None
    try:
        return location.token_path.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _provider_findings(
    location: WorkspaceLocation,
    *,
    probe: bool,
    assume_capability: tuple[str, ...],
) -> tuple[ProviderFinding, ...]:
    """What the workspace's model providers can do.

    Without ``--probe`` nothing is asked of a provider, so every capability is
    reported as unverified — which is the honest state of a workspace whose
    endpoints have never been asked. With it, the providers are probed for
    real, which costs money and is why it is opt-in.
    """
    from labcairn.cli.models import ProviderFinding
    from labcairn.cli.workspace import WorkspaceSetupError
    from labcairn.providers.capabilities import ALL_CAPABILITIES
    from labcairn.providers.probe import endpoint_fingerprint

    settings_by_name = _provider_settings(location)
    if not settings_by_name:
        return ()

    known = {capability.value for capability in ALL_CAPABILITIES}
    unknown = sorted(set(assume_capability) - known)
    if unknown:
        raise WorkspaceSetupError(
            f"unknown model provider capabilit{'y' if len(unknown) == 1 else 'ies'}: "
            f"{', '.join(unknown)}. The capabilities are {', '.join(sorted(known))}."
        )

    findings: list[ProviderFinding] = []
    for name, settings in settings_by_name.items():
        fingerprint = endpoint_fingerprint(
            base_url=settings.sanitised_base_url(),
            model=settings.model,
            protocol=settings.protocol_label,
        )
        capabilities = _probe_capabilities(settings, fingerprint) if probe else None
        findings.append(
            ProviderFinding(
                name=name,
                protocol=settings.protocol_label,
                model=settings.model,
                endpoint_fingerprint=fingerprint,
                probed=capabilities is not None,
                capabilities=_capability_findings(
                    capabilities,
                    assume_capability=assume_capability,
                ),
            )
        )
    return tuple(findings)


def _provider_settings(location: WorkspaceLocation) -> Mapping[str, ProviderSettings]:
    """The workspace's configured model providers."""
    from labcairn.cli.workspace import WorkspaceSetupError
    from labcairn.providers.credentials import ProviderSettings

    path = location.root / PROVIDERS_FILE_NAME
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise WorkspaceSetupError(f"{path} could not be read as JSON: {error}") from error
    if not isinstance(raw, Mapping) or not isinstance(raw.get("providers"), Mapping):
        raise WorkspaceSetupError(f'{path} must hold a top-level "providers" object.')
    entries = raw["providers"]
    return {str(name): ProviderSettings.from_mapping(entry) for name, entry in entries.items()}


def _probe_capabilities(
    settings: ProviderSettings,
    fingerprint: str,
) -> ProviderCapabilities | None:
    """Ask one endpoint what it can do.

    A probe that fails is reported as a capability that could not be observed
    rather than as a crash: ``doctor`` is a diagnostic, and a diagnostic that
    dies on the first thing it cannot read is not a diagnostic.
    """
    from labcairn.providers.capabilities import Capability, CapabilityOutcome, ProviderCapabilities

    try:
        from labcairn.providers.pydantic_models import smoke_test

        wire = smoke_test(settings)
    except Exception:
        return None

    outcomes = wire.get("outcomes", {})
    evidence = wire.get("evidence", {})
    if not isinstance(outcomes, Mapping) or not isinstance(evidence, Mapping):
        return None
    try:
        parsed_outcomes = {
            Capability(str(capability)): CapabilityOutcome(str(outcome))
            for capability, outcome in outcomes.items()
        }
    except ValueError:
        return None
    return ProviderCapabilities.from_outcomes(
        endpoint_fingerprint=str(wire.get("endpoint_fingerprint", fingerprint)),
        model=str(wire.get("model", settings.model)),
        protocol=str(wire.get("protocol", settings.protocol_label)),
        outcomes=parsed_outcomes,
        unsupported_reason=_evidence_by_capability(evidence),
    )


def _evidence_by_capability(evidence: Mapping[Any, Any]) -> dict[Capability, str]:
    """The probe's evidence, keyed by the capability it explains.

    An entry whose key is not a capability this build knows is dropped rather
    than guessed at: the reason is only meaningful against the capability it
    was observed for, and a reason attached to the wrong one would be a claim
    about something nobody measured.
    """
    from labcairn.providers.capabilities import Capability

    reasons: dict[Capability, str] = {}
    for key, value in evidence.items():
        try:
            capability = Capability(str(key))
        except ValueError:
            continue
        reasons[capability] = str(value)
    return reasons


def _capability_findings(
    capabilities: ProviderCapabilities | None,
    *,
    assume_capability: tuple[str, ...],
) -> tuple[CapabilityFinding, ...]:
    """One finding per capability, in the provider layer's own order."""
    from labcairn.cli.models import CapabilityFinding
    from labcairn.providers.capabilities import ALL_CAPABILITIES, ProviderCapabilities

    if capabilities is None:
        capabilities = ProviderCapabilities.unverified(
            endpoint_fingerprint="unprobed",
            model="unprobed",
            protocol="unprobed",
        )

    findings: list[CapabilityFinding] = []
    for capability in ALL_CAPABILITIES:
        outcome = capabilities.outcome_for(capability)
        assumed = capability.value in assume_capability
        reason = capabilities.unsupported_reason.get(capability)
        findings.append(
            CapabilityFinding(
                capability=capability.value,
                outcome=outcome.value,
                reason=reason,
                assumed=assumed,
                usable=outcome.usable or assumed,
            )
        )
    return tuple(findings)


# --------------------------------------------------------------------------- #
# task
# --------------------------------------------------------------------------- #


@task_app.command("create")
def task_create(
    ctx: typer.Context,
    title: Annotated[str, typer.Option("--title", help="What the task is called.")],
    objective: Annotated[
        str,
        typer.Option("--objective", help="What the task is trying to establish."),
    ],
    criterion: Annotated[
        str,
        typer.Option("--criterion", help="What would count as having established it."),
    ],
    source_dir: Annotated[
        list[str] | None,
        typer.Option(
            "--source-dir",
            help=(
                "A directory of supplied material, inside the workspace, to bind as a "
                "source root. May be given more than once."
            ),
        ),
    ] = None,
    as_json: JsonOption = False,
) -> None:
    """Make a task, its workspace, and its first event.

    The task's output area is created and the task's first event is written
    in one transaction by the layer, so a task that exists has a history.

    **The workspace's material is ingested, and the task is bound to it.** A
    task that holds no material can carry disclosures and never a claim,
    because a claim rests on a cited record and a citation points into
    material the task holds. So the material under the workspace's source
    roots is read through the permission boundary and bound to the task
    before this command returns.

    A file that could not be read makes the command refuse: the Task model
    has no field for a failure, and a task that quietly holds less than the
    operator asked for is a task nobody can trust. The message names each
    file and why it could not be read.
    """
    from labcairn.application import create_task, ingest_material, read_task_state
    from labcairn.cli import render
    from labcairn.cli.models import CLI_REFUSAL_MATERIAL_INCOMPLETE, emit_model
    from labcairn.cli.workspace import (
        application_context,
        load_policy,
        locate,
        source_paths,
        write_config,
    )
    from labcairn.db import TaskStore, create_db_engine, create_session_factory, session_scope
    from labcairn.runtime.lifecycle import TaskGoal

    options = _options(ctx)
    location = locate(options.workspace)
    with _refusals(as_json):
        config = _require_workspace(location, as_json=as_json)
        sources = _resolve_source_dirs(location, config, tuple(source_dir or ()), as_json=as_json)
        if sources != config.source_dirs:
            config = config.model_copy(update={"source_dirs": sources})

        engine = create_db_engine(location.root / config.database)
        factory = create_session_factory(engine)
        try:
            with session_scope(factory) as session:
                created = create_task(
                    store=TaskStore(session),
                    policy=load_policy(location),
                    workspace_root=location.root,
                    title=title,
                    goal=TaskGoal(objective=objective, success_criterion=criterion),
                    source_dirs=source_paths(location, config),
                )
        finally:
            engine.dispose()

        task_id = created.task.task_id
        with application_context(location, config, task_id) as context:
            ingested = ingest_material(context)
            # Read back through the layer rather than patched from the value
            # above: the binding moved the task's own ``updated_at``, and the
            # model this command prints has to be the one the layer reports.
            model = read_task_state(context).task

        write_config(location, config.model_copy(update={"current_task": str(task_id)}))
        if ingested.failures:
            _refuse(
                CLI_REFUSAL_MATERIAL_INCOMPLETE,
                _the_unreadable_material(ingested, task_id=task_id),
                as_json=as_json,
            )
    if as_json:
        emit_model(model)
    else:
        output_area = location.output_path / str(model.task_id)
        _console().print(render.render_task(model, output_area))


def _the_unreadable_material(ingested: MaterialIngested, *, task_id: TaskId) -> str:
    """What could not be read, and what the task holds because of it.

    The message names each file and why it could not be read, because a reason
    nobody can act on is the same as no reason. The task is named too: it
    exists, and it holds the material that could be read.
    """
    listed = "; ".join(
        f"{failure.relative_path} ({failure.reason})" for failure in ingested.failures
    )
    return (
        f"{len(ingested.failures)} file(s) of the supplied material could not be read, "
        f"so the task {task_id} holds only the material that could: {listed}. "
        "A task that quietly holds less than the material it was given is a task "
        "nobody can check a claim against."
    )


def _resolve_source_dirs(
    location: WorkspaceLocation,
    config: WorkspaceConfig,
    requested: tuple[str, ...],
    *,
    as_json: bool,
) -> tuple[str, ...]:
    """The source roots, after the operator's additions.

    A source directory the workspace does not contain is refused rather than
    silently dropped: a source root outside the workspace is a root the
    operator's selection of the workspace does not govern, and the layer
    refuses it too — but the layer cannot say which directory the operator
    named.

    **The spelling guard is asked before the filesystem is**, for the same
    reason the module asks it first: ``Path.resolve()`` on a name carrying a
    NUL byte raises a bare ``ValueError``, which is a crash where the
    command promised a refusal. The guard's answer is a refusal the command
    can render.
    """
    from labcairn.cli.models import CLI_REFUSAL_INVALID_ARGUMENTS
    from labcairn.cli.workspace import SourceRootKind, source_root_problem

    directories = list(config.source_dirs)
    for entry in requested:
        problem = source_root_problem(location, entry)
        if problem is not None and problem.kind is SourceRootKind.UNUSABLE_NAME:
            _refuse(
                CLI_REFUSAL_INVALID_ARGUMENTS,
                f"the source directory {entry!r} is not a name this build can use: "
                f"{problem.detail} `task create` binds source roots the workspace can "
                "speak, and it will not make one up.",
                as_json=as_json,
            )
        candidate = (location.root / entry).resolve()
        if not candidate.is_relative_to(location.root):
            _refuse(
                CLI_REFUSAL_INVALID_ARGUMENTS,
                f"the source directory {entry!r} resolves to {candidate}, which is "
                f"outside the workspace {location.root}. A source root the workspace "
                "does not contain is a root the operator's selection does not govern.",
                as_json=as_json,
            )
        if not candidate.is_dir():
            _refuse(
                CLI_REFUSAL_INVALID_ARGUMENTS,
                f"the source directory {entry!r} is {candidate}, which is not a "
                "directory. `task create` binds directories that are there; it does "
                "not make them.",
                as_json=as_json,
            )
        relative = candidate.relative_to(location.root).as_posix()
        if relative not in directories:
            directories.append(relative)
    return tuple(directories)


@task_app.command("status")
def task_status(
    ctx: typer.Context,
    task: TaskOption = None,
    plan: Annotated[
        bool,
        typer.Option(
            "--plan",
            help=(
                "Report the declared workflow and how far the task has got through it, "
                "instead of the task's current state."
            ),
        ),
    ] = False,
    as_json: JsonOption = False,
) -> None:
    """Report where a task is.

    The state is one value and the plan is another, and the layer keeps them
    apart because neither is derived from the other: the plan is what should
    happen, the state is what did. ``--plan`` says which one to report.
    """
    from labcairn.application import read_plan, read_task_state
    from labcairn.application.stages import TaskPlan
    from labcairn.cli import render
    from labcairn.cli.models import emit_model
    from labcairn.cli.workspace import application_context, locate

    options = _options(ctx)
    location = locate(options.workspace)
    with _refusals(as_json):
        config = _require_workspace(location, as_json=as_json)
        task_id = _select_task(config, task, as_json=as_json)
        with application_context(location, config, task_id) as context:
            if plan:
                model: TaskState | TaskPlan = read_plan(context)
            else:
                model = read_task_state(context)
    if as_json:
        emit_model(model)
    else:
        console = _console()
        if isinstance(model, TaskPlan):
            console.print(render.render_task_plan(model))
        else:
            console.print(render.render_task_state(model))


@task_app.command("run")
def task_run(
    ctx: typer.Context,
    source: Annotated[str, typer.Option("--source", help="The source to inventory.")],
    task: TaskOption = None,
    as_json: JsonOption = False,
) -> None:
    """Run a stage, in the task's current run.

    The stage this build can run is ``inventory``: the work is the layer's own
    ``inspect_source``, and the stage's output hash is the material's content
    hash. The other declared stages have bodies in LC-P1-08, LC-P1-09,
    LC-P1-10 and LC-P1-11, and this command does not pretend to have them.
    """
    _run_a_stage(ctx, source=source, task=task, as_json=as_json, resume=False)


@task_app.command("resume")
def task_resume(
    ctx: typer.Context,
    source: Annotated[str, typer.Option("--source", help="The source to inventory.")],
    task: TaskOption = None,
    as_json: JsonOption = False,
) -> None:
    """Start a new attempt against the task, and run a stage in it.

    A resume is a **new Run against the same Task** and never a new Task
    (ADR-0003 C1, R-02): the task's identity survives every attempt, and the
    attempt number is what says how many there have been. ``task run``
    continues the current run instead.
    """
    _run_a_stage(ctx, source=source, task=task, as_json=as_json, resume=True)


def _run_a_stage(
    ctx: typer.Context,
    *,
    source: str,
    task: str | None,
    as_json: bool,
    resume: bool,
) -> None:
    """The stage run both ``task run`` and ``task resume`` perform.

    The difference is the run the stage belongs to, and nothing else: a
    resume names no run, so the layer opens a new one, and a run names the
    task's current one.
    """
    from labcairn.application import (
        StageRequest,
        inspect_source,
        read_task_state,
        run_stage,
    )
    from labcairn.cli import render
    from labcairn.cli.models import emit_model
    from labcairn.cli.workspace import application_context, locate
    from labcairn.security.capabilities import CapabilityId
    from labcairn.skills.artifacts import StageName

    options = _options(ctx)
    location = locate(options.workspace)
    with _refusals(as_json):
        config = _require_workspace(location, as_json=as_json)
        task_id = _select_task(config, task, as_json=as_json)
        with application_context(location, config, task_id) as context:
            view = inspect_source(context, source)
            resource = context.resource_for(view.source.relative_path)
            run_id = None
            if not resume:
                state = read_task_state(context)
                if state.runs:
                    run_id = state.runs[-1].run_id
            request = StageRequest(
                stage_name=StageName.INVENTORY.value,
                capability=CapabilityId.SOURCE_INVENTORY,
                arguments={},
                root_id=resource.root_id,
                resource_key=resource.resolved_key,
                run_id=run_id,
            )
            outcome = run_stage(context, request, _inventory_work(context, source))
    if as_json:
        emit_model(outcome)
    else:
        _console().print(render.render_stage_run(outcome))


def _inventory_work(context: Any, source_id: str) -> Any:
    """The ``inventory`` stage's body.

    A composition of the layer's own ``inspect_source`` and nothing else: the
    stage reads the material through the capability model, exactly as every
    other read does, and records the content hash it saw. The stage bodies
    for the other declared stages belong to the packages that own them, and
    this one is here only because the CLI has to give ``run_stage`` something
    to run.
    """
    from labcairn.application import StageOutcome, inspect_source

    def work(resource: CanonicalPath) -> StageOutcome:
        del resource
        inspected = inspect_source(context, source_id)
        return StageOutcome(output_hashes=(inspected.source.content_sha256,))

    return work


# --------------------------------------------------------------------------- #
# sources
# --------------------------------------------------------------------------- #


@sources_app.command("inspect")
def sources_inspect(
    ctx: typer.Context,
    source: Annotated[str, typer.Option("--source", help="The source to inspect.")],
    task: TaskOption = None,
    as_json: JsonOption = False,
) -> None:
    """Report one source, as the ledger holds it.

    The layer inventories the ledger and does not read the material: what a
    source *is* — its kind, its hash, its size, and the disclosure that says
    why it could not be read — is one operation, and reading its bytes is
    another.
    """
    from labcairn.application import inspect_source
    from labcairn.cli import render
    from labcairn.cli.models import emit_model
    from labcairn.cli.workspace import application_context, locate

    options = _options(ctx)
    location = locate(options.workspace)
    with _refusals(as_json):
        config = _require_workspace(location, as_json=as_json)
        task_id = _select_task(config, task, as_json=as_json)
        with application_context(location, config, task_id) as context:
            model: SourceView = inspect_source(context, source)
    if as_json:
        emit_model(model)
    else:
        _console().print(render.render_source(model))


@sources_app.command("ingest")
def sources_ingest(
    ctx: typer.Context,
    task: TaskOption = None,
    as_json: JsonOption = False,
) -> None:
    """Ingest the workspace's supplied material, and bind it to the task.

    The material under the workspace's source roots is read through the
    permission boundary, stored in the ledger, and bound to the task by the
    ids the ingestion mints. A task that holds no material can carry
    disclosures and never a claim, because a claim rests on a cited record
    and a citation points into material the task holds.

    Running it again over the same material writes nothing new, and running it
    again over an edited file refreshes what the ledger records about it.

    A file that could not be read is **reported, not swallowed**: the report
    names it and says why, and the rest of the material is still ingested.
    """
    from labcairn.application import ingest_material
    from labcairn.cli.models import emit_model
    from labcairn.cli.workspace import application_context, locate

    options = _options(ctx)
    location = locate(options.workspace)
    with _refusals(as_json):
        config = _require_workspace(location, as_json=as_json)
        task_id = _select_task(config, task, as_json=as_json)
        with application_context(location, config, task_id) as context:
            model: MaterialIngested = ingest_material(context)
    if as_json:
        emit_model(model)
    else:
        _console().print(_render_ingestion(model))


def _render_ingestion(model: MaterialIngested) -> RenderableType:
    """What the ingestion produced, drawn from the model.

    The picture is generated from the same value the ``--json`` form
    serialises, so the two cannot disagree. The failures are on their own
    lines: a file that could not be read is a fact the reader has to act on,
    and a count alone would not say which one.
    """
    from rich.panel import Panel
    from rich.table import Table

    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("ingested", str(len(model.source_ids)))
    table.add_row("readable", str(model.readable))
    table.add_row("empty", str(model.empty))
    table.add_row("unreadable", str(model.unreadable))
    table.add_row("no adapter", str(len(model.skipped)))
    table.add_row("failed", str(len(model.failures)))
    table.add_row("bound", ", ".join(model.bound_source_ids) or "(nothing)")
    for failure in model.failures:
        table.add_row("failed", f"{failure.relative_path}: {failure.reason}")
    return Panel(table, title="ingested", expand=False)


# --------------------------------------------------------------------------- #
# artifacts
# --------------------------------------------------------------------------- #


@artifacts_app.command("list")
def artifacts_list(
    ctx: typer.Context,
    task: TaskOption = None,
    as_json: JsonOption = False,
) -> None:
    """List what a task has produced.

    The receipts, oldest revision first. The list is of what the store holds
    — an artefact that was written and not recorded is not one the task has
    produced.
    """
    from labcairn.application import list_artifacts
    from labcairn.application.artifacts import ArtifactView
    from labcairn.cli import render
    from labcairn.cli.models import emit_models
    from labcairn.cli.workspace import application_context, locate

    options = _options(ctx)
    location = locate(options.workspace)
    with _refusals(as_json):
        config = _require_workspace(location, as_json=as_json)
        task_id = _select_task(config, task, as_json=as_json)
        with application_context(location, config, task_id) as context:
            models = list_artifacts(context)
    if as_json:
        emit_models(models, ArtifactView)
    else:
        _console().print(render.render_artifacts(models))


# --------------------------------------------------------------------------- #
# serve
# --------------------------------------------------------------------------- #


#: The origins the development web server is served from.
#:
#: ``web/vite.config.ts`` binds the development server to ``127.0.0.1:5173``,
#: and a request the workbench makes from that page carries that page's
#: origin — so the service has to answer to it, or the workbench cannot
#: change anything and does not know why.
#:
#: **Both spellings are here, and both are needed.** A developer who types
#: ``localhost:5173`` into the browser is on a page whose origin is
#: ``http://localhost:5173``, and the browser sends that string; the address
#: the server bound is not what travels. Both reach the same server, so
#: allowing one and not the other would refuse the same page for a spelling.
#:
#: **This is a widening of the allow-list, and it is deliberate.** The
#: alternative — an empty list and an explicit ``--origin`` — would make
#: ``labcairn serve`` and ``pnpm dev`` a pair that fails at the first write
#: with an origin refusal that reads like a bug. The cost is that whatever
#: is listening on the development port may drive the service, so the
#: command prints the allow-list it will answer to.
DEVELOPMENT_ORIGINS: tuple[str, ...] = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
)


@app.command()
def serve(
    ctx: typer.Context,
    task: TaskOption = None,
    host: Annotated[
        str,
        typer.Option(
            "--host",
            help=(
                "The address to bind. A loopback address and nothing else: the "
                "service refuses to start on any other."
            ),
        ),
    ] = DEFAULT_BIND_HOST,
    port: Annotated[
        int,
        typer.Option(
            "--port",
            help="The port to bind, and the port the service's own origin carries.",
        ),
    ] = DEFAULT_BIND_PORT,
    origin: Annotated[
        list[str] | None,
        typer.Option(
            "--origin",
            help=(
                "An origin to answer to besides the service's own and the "
                "development server's. May be given more than once."
            ),
        ),
    ] = None,
    static_dir: Annotated[
        Path | None,
        typer.Option(
            "--static-dir",
            help=(
                "The built workbench to serve from the service's own origin, so "
                "the browser and the API share one."
            ),
        ),
    ] = None,
    as_json: JsonOption = False,
) -> None:
    """Start the local service, and serve the workspace's current task.

    The service is the local API, and the API is task-scoped: it serves one
    task's state, so the workspace must have a current task and the command
    refuses rather than guess which task was meant.

    The bind address is refused and not warned about, and the port is 8000
    because that is where the workbench's proxy points. The token the
    service mints is written to the workspace and never printed, and the
    development web server's origins are answered to by default — with the
    allow-list printed, so that the decision is visible rather than buried.

    The event stream and the stage bodies belong to the packages that own
    them, so a request for either is refused in the layer's own vocabulary
    rather than answered with something that looks like a result.
    """
    from labcairn.cli.models import emit_model
    from labcairn.cli.workspace import application_context, locate

    options = _options(ctx)
    location = locate(options.workspace)
    with _refusals(as_json):
        config = _require_workspace(location, as_json=as_json)
        task_id = _select_task(config, task, as_json=as_json)
        _check_host(host, as_json=as_json)
        _check_port(port, as_json=as_json)
        origins = _resolve_origins(tuple(origin or ()), as_json=as_json)
        workbench = _resolve_static_dir(static_dir, as_json=as_json)
        _check_port_free(host, port, as_json=as_json)
        with application_context(location, config, task_id) as context:
            app = service_app(
                context,
                host=host,
                port=port,
                extra_origins=origins,
                static_dir=workbench,
            )
            model = _service_report(
                app, host=host, port=port, task_id=task_id, static_dir=workbench
            )
            if as_json:
                emit_model(model)
            else:
                _console().print(_render_service_starting(model))
            _run_service(app, host=host, port=port, as_json=as_json)


def service_app(
    context: ApplicationContext,
    *,
    host: str,
    port: int,
    extra_origins: Sequence[str],
    static_dir: Path | None,
) -> FastAPI:
    """The service, as this command builds it.

    Named apart from the command so that what the command starts can be
    looked at without starting it. The wiring — the bind address, the port,
    the origins and the task — is the thing worth looking at, and a test
    that had to bind a socket to look at it would be a test that fails when
    the machine's ports are busy.
    """
    from labcairn.api import create_app

    return create_app(
        context,
        host=host,
        port=port,
        extra_origins=extra_origins,
        static_dir=static_dir,
    )


def _service_report(
    app: FastAPI,
    *,
    host: str,
    port: int,
    task_id: TaskId,
    static_dir: Path | None,
) -> ServiceStarting:
    """What the service is, read from the service.

    The origins and the token's path are the service's own and not a second
    spelling of them: the command composed the origins once and the service
    holds them, and the path the token was written to is the service's fact
    and not the command's arithmetic.
    """
    from labcairn.api.bind import own_origin
    from labcairn.api.guards import OriginPolicy
    from labcairn.api.session import SessionToken
    from labcairn.cli.models import ServiceStarting

    origins = cast(OriginPolicy, app.state.origins)
    token = cast(SessionToken, app.state.session)
    return ServiceStarting(
        host=host,
        port=port,
        origin=own_origin(host, port),
        origins=tuple(sorted(origins.allowed)),
        task_id=str(task_id),
        token_path=str(token.path),
        static_dir=str(static_dir) if static_dir is not None else None,
    )


def _render_service_starting(model: ServiceStarting) -> RenderableType:
    """What ``serve`` is about to serve.

    Drawn here rather than in :mod:`labcairn.cli.render` because the service
    is the one thing this CLI starts rather than reports on, and the model
    it draws is the one this command builds.
    """
    from rich.panel import Panel
    from rich.table import Table

    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("service", model.origin)
    table.add_row("task", model.task_id)
    table.add_row("origins", ", ".join(model.origins))
    table.add_row("token", model.token_path)
    if model.static_dir is not None:
        table.add_row("workbench", model.static_dir)
    return Panel(table, title="service starting", expand=False)


def _check_host(host: str, *, as_json: bool) -> None:
    """The bind address, if it is one the service may bind.

    The service's own check is asked first and its own words are used, so
    the refusal a developer reads here is the refusal the service would have
    given. It is asked here rather than left to
    :func:`~labcairn.api.app.create_app` because **nothing may be bound
    before it has been answered**, and the command binds the address once to
    find out whether it can.
    """
    from labcairn.api.bind import BindRefusedError, ensure_loopback
    from labcairn.cli.models import CLI_REFUSAL_INVALID_ARGUMENTS

    try:
        ensure_loopback(host)
    except BindRefusedError as error:
        _refuse(CLI_REFUSAL_INVALID_ARGUMENTS, str(error), as_json=as_json)


def _check_port(port: int, *, as_json: bool) -> None:
    """The port, if it is one a socket can carry.

    Zero is refused with the rest: it would let the operating system choose
    the port, and the service's own origin is computed from the port it was
    told — so the origin would name a port nothing is listening on.
    """
    from labcairn.cli.models import CLI_REFUSAL_INVALID_ARGUMENTS

    if not 1 <= port <= 65535:
        _refuse(
            CLI_REFUSAL_INVALID_ARGUMENTS,
            f"{port} is not a port number. A port is between 1 and 65535, and the "
            "service's own origin is computed from the port it is given.",
            as_json=as_json,
        )


def _check_port_free(host: str, port: int, *, as_json: bool) -> None:
    """Whether the address can be bound.

    Checked before the command prints anything, so that its output is not a
    claim that the service is running when the address was already taken.
    The socket is bound and let go without ever listening, and the service
    binds the address again a moment later.
    """
    from labcairn.cli.models import CLI_REFUSAL_INVALID_ARGUMENTS

    version = ipaddress.ip_address(host).version
    family = socket.AF_INET6 if version == 6 else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as probe:
            probe.bind((host, port))
    except OSError as error:
        _refuse(
            CLI_REFUSAL_INVALID_ARGUMENTS,
            f"the service could not bind {host}:{port}: {error}. Something else may "
            "be listening there.",
            as_json=as_json,
        )


def _resolve_origins(requested: tuple[str, ...], *, as_json: bool) -> tuple[str, ...]:
    """The origins the service will answer to.

    The development server's origins are in the list whatever was asked for,
    and every other origin is one somebody named.
    """
    origins = list(DEVELOPMENT_ORIGINS)
    for entry in requested:
        if entry in origins:
            continue
        _check_origin(entry, as_json=as_json)
        origins.append(entry)
    return tuple(origins)


def _check_origin(entry: str, *, as_json: bool) -> None:
    """An origin, if it is spelled as one.

    An origin is a scheme, a host and a port and nothing else, because that
    is what the browser sends and what the guard compares. A path or a
    trailing slash would never match a header, so accepting one would be
    accepting an origin that does nothing.
    """
    from labcairn.cli.models import CLI_REFUSAL_INVALID_ARGUMENTS

    parts = urlsplit(entry)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        _refuse(
            CLI_REFUSAL_INVALID_ARGUMENTS,
            f"{entry!r} is not an origin. An origin is a scheme, a host and a port "
            "— 'http://localhost:5173' — and nothing else.",
            as_json=as_json,
        )
    if parts.path or parts.query or parts.fragment:
        _refuse(
            CLI_REFUSAL_INVALID_ARGUMENTS,
            f"{entry!r} is not an origin. An origin carries no path, no query and no "
            "fragment: 'http://localhost:5173' is one, and "
            f"{entry!r} is not.",
            as_json=as_json,
        )


def _resolve_static_dir(static_dir: Path | None, *, as_json: bool) -> Path | None:
    """The built workbench the service will serve, if one was named.

    A directory that is not there is refused rather than ignored: the
    service would answer to the same origin with no workbench on it, and the
    developer would be left with a service that serves nothing and no reason
    why.
    """
    from labcairn.cli.models import CLI_REFUSAL_INVALID_ARGUMENTS

    if static_dir is None:
        return None
    resolved = static_dir.expanduser().resolve()
    if not resolved.is_dir():
        _refuse(
            CLI_REFUSAL_INVALID_ARGUMENTS,
            f"{resolved} is not a directory, so there is no built workbench there to serve.",
            as_json=as_json,
        )
    return resolved


def run_service(app: FastAPI, *, host: str, port: int) -> None:
    """The service's own runner, imported when the service is actually run.

    **The import is inside the function on purpose.** :mod:`labcairn.api.app`
    imports FastAPI and the application layer, and the command line's own
    import is deferred so that loading the CLI does not load the service.
    The command that starts the service is the one that loads it.
    """
    from labcairn.api import serve

    serve(app, host=host, port=port)


def _run_service(app: FastAPI, *, host: str, port: int, as_json: bool) -> None:
    """Run the service until it is stopped.

    The refusal is rendered rather than raised, because a service that could
    not start is not a crash: it is a service that declined, and the two are
    told apart by their exit code.

    **The bind refusal carries this command's own sentence as well as the
    layer's reason.** The layer's words alone are not a refusal this command
    can be held to: a message that is only ``str(error)`` is another
    component's refusal passing through, and nothing in the tree can say
    which site refused or tell this one apart from the address check's. So
    the sentence is the command's own, and the guard's reason follows it.

    **The address is not named here, because the guard is the one that knows
    which address it refused.** The command asked for one address and the
    service may have been handed another, so a sentence that named the
    command's address would be a claim about an address the refusal is not
    about. The guard names the address in its own words, and they are carried
    through whole.
    """
    from labcairn.api.bind import BindRefusedError
    from labcairn.cli.models import CLI_REFUSAL_INVALID_ARGUMENTS

    try:
        run_service(app, host=host, port=port)
    except BindRefusedError as error:
        _refuse(
            CLI_REFUSAL_INVALID_ARGUMENTS,
            f"the service's own guard refused the bind: {error}",
            as_json=as_json,
        )
    except SystemExit:
        _refuse(
            CLI_REFUSAL_INVALID_ARGUMENTS,
            f"the service could not start on {host}:{port}. The address may have been "
            "taken between the check and the bind.",
            as_json=as_json,
        )


__all__ = [
    "EXIT_REFUSED",
    "EXIT_USAGE",
    "app",
    "artifacts_app",
    "serve",
    "service_app",
    "sources_app",
    "task_app",
]
