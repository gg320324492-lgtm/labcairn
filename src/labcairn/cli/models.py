"""The machine-readable forms, and the two models the layer does not have.

**Most of the CLI's JSON is the layer's own model, untouched.**
``task status`` prints the layer's :class:`~labcairn.application.tasks.TaskState`,
``task run`` prints its :class:`~labcairn.application.stages.StageRun`,
``sources inspect`` prints its
:class:`~labcairn.application.sources.SourceView` and ``artifacts list``
prints an array of its
:class:`~labcairn.application.artifacts.ArtifactView`. Those serializations are
pydantic's, produced by the same call the API will make, so the two surfaces
serve the same bytes without anybody transcribing one into the other.

**Three commands have no layer operation, and their models are the CLI's.**
``init`` and ``doctor`` describe a *workspace* — a directory, a database, a
policy, a provider — and ``serve`` describes a *service* — an address, an
origin, a token's path — and the application layer has no operation that
reports either, because a task is the layer's unit and a workspace and a
service are not tasks. The models below are therefore the CLI's, and the
local API will need equivalents of its own or a layer operation that answers
the same questions. That is recorded here rather than hidden, because a second
surface that invented a second spelling of the same facts is exactly what
§1.4.2 of the task breakdown forbids.

**The models exist so the two forms cannot disagree.** Every command builds one
model and then either serialises it or draws it; there is no path where the
prose is parsed to produce the JSON, because there is no prose until after the
JSON could have been written.
"""

from __future__ import annotations

import json
from types import GenericAlias
from typing import Any

import typer
from pydantic import BaseModel, TypeAdapter
from rich.console import Console

from labcairn.application.models import Result

#: The JSON style every machine-readable form uses.
#:
#: Compact separators and no ASCII escaping, so the bytes are the same ones
#: pydantic's own ``model_dump_json`` produces for the layer's models. A
#: command that switched styles would break the property the whole scheme
#: rests on: that the CLI's output and the API's response are one
#: serialization.
_JSON_SEPARATORS = (",", ":")

#: The reasons the CLI itself refuses with.
#:
#: The layer has its own vocabulary, and a refusal it produces is rendered
#: from :meth:`labcairn.application.ApplicationRefusedError.to_payload` without
#: being renamed. These are for the conditions the layer has no operation for:
#: a workspace that is not there, a workspace that is already one, a task the
#: operator did not name, an argument the CLI will not act on, and a
#: workspace the CLI cannot use. The shape is the same two fields, so a
#: caller reads one refusal format whichever surface produced it.
CLI_REFUSAL_INVALID_ARGUMENTS = "invalid_arguments"
CLI_REFUSAL_NO_TASK_SELECTED = "task_not_selected"
CLI_REFUSAL_WORKSPACE_EXISTS = "workspace_exists"
CLI_REFUSAL_WORKSPACE_NOT_INITIALISED = "workspace_not_initialised"
CLI_REFUSAL_WORKSPACE_UNUSABLE = "workspace_unusable"
#: The supplied material could not all be read.
#:
#: The layer's ingestion reports a file it could not read as a **fact** rather
#: than as a refusal, because one unreadable file should not stop the rest of
#: a workspace being inventoried — and ``sources ingest`` has a model with a
#: field for it. A command whose model has nowhere to put that fact has to
#: refuse instead, and ``task create`` prints the Task, which has no field
#: for a file that could not be read: a task that quietly holds less than the
#: material it was given is a task nobody can check a claim against.
CLI_REFUSAL_MATERIAL_INCOMPLETE = "material_incomplete"


def dumps(value: Any) -> str:
    """A value as the CLI's JSON.

    Used for the shapes pydantic does not model — a refusal payload, which is
    the layer's own two-field mapping.
    """
    return json.dumps(value, ensure_ascii=False, separators=_JSON_SEPARATORS)


def emit_model(model: BaseModel) -> None:
    """Print a model's machine-readable form.

    The model's own serialization, byte for byte. Not a re-encoding of a
    rendered string, and not a hand-written dict: pydantic's output is what
    the API will serve, and matching it is the point.
    """
    typer.echo(model.model_dump_json())


def emit_models(models: tuple[BaseModel, ...], element: type[BaseModel]) -> None:
    """Print an array of models, as the layer's models serialise them.

    The adapter is pydantic's, so an array of the layer's models is spelled
    the way pydantic spells it rather than the way a JSON library would.

    **The element type is named, and it has to be.** A pydantic adapter
    built for :class:`~pydantic.BaseModel` serialises a subclass through the
    *base* schema, which has no fields: ``TypeAdapter(tuple[BaseModel, ...])``
    turns every model into ``{}``. That is not a hypothetical — it is what
    this function did, and an empty listing could not tell. The adapter is
    therefore built for the concrete model, and the caller says which.

    The array type is assembled with :class:`types.GenericAlias` rather than
    written as ``tuple[element, ...]``, because the element is a value and a
    subscript is a type expression; the two produce the same object, and only
    one of them is something a type checker can read.
    """
    array_type: Any = GenericAlias(tuple, (element, Ellipsis))
    adapter: TypeAdapter[Any] = TypeAdapter(array_type)
    typer.echo(adapter.dump_json(models).decode("utf-8"))


def emit_refusal(reason: str, message: str, *, as_json: bool) -> None:
    """Print a refusal, and say what was refused.

    The machine-readable form is the two fields the layer uses, so a script
    reads one refusal format whichever surface produced it. The human form
    goes to stderr, because a refusal on stdout would be indistinguishable
    from a result to a script that forgot to check the exit code.
    """
    if as_json:
        typer.echo(dumps({"reason": reason, "message": message}))
        return
    Console(stderr=True).print(f"[bold red]refused[/bold red] ({reason}): {message}")


__all__ = [
    "CLI_REFUSAL_INVALID_ARGUMENTS",
    "CLI_REFUSAL_MATERIAL_INCOMPLETE",
    "CLI_REFUSAL_NO_TASK_SELECTED",
    "CLI_REFUSAL_WORKSPACE_EXISTS",
    "CLI_REFUSAL_WORKSPACE_NOT_INITIALISED",
    "CLI_REFUSAL_WORKSPACE_UNUSABLE",
    "ApiSessionFinding",
    "CapabilityFinding",
    "DatabaseFinding",
    "DoctorReport",
    "PolicyFinding",
    "ProviderFinding",
    "SourceRootFinding",
    "WorkspaceFinding",
    "WorkspaceInitialised",
    "dumps",
    "emit_model",
    "emit_models",
    "emit_refusal",
]


class WorkspaceInitialised(Result):
    """What ``init`` made.

    ``created`` lists the paths that now exist because the command ran, so a
    reader can see what the command did rather than infer it from the state it
    left behind.
    """

    root: str
    database_path: str
    migration_revision: str
    source_dirs: tuple[str, ...]
    created: tuple[str, ...]
    policy_digest: str


class SourceRootFinding(Result):
    """One configured source root, and the way it cannot be used.

    ``problem`` is one of :class:`labcairn.cli.workspace.SourceRootKind`'s
    values, and those values are **the words the refusals use**: ``missing``,
    ``not a directory``, ``outside the workspace``, ``unusable name``. A
    diagnostic that named the condition differently from the refusal would be
    telling the operator two things about the same source root, and one of
    them would be wrong.
    """

    name: str
    problem: str


class WorkspaceFinding(Result):
    """What ``doctor`` found about the workspace.

    ``unusable_source_roots`` are the configured source roots the commands
    will refuse, and each one says **which of the ways** it is unusable —
    missing, not a directory, outside the workspace, or a name this build
    cannot speak. They are reported because a workspace that names a source
    root the commands will refuse **cannot be bound**: the module refuses it,
    and every task-scoped command refuses it with it. A diagnostic that
    called such a workspace fine would be calling a workspace fine that no
    command can use.

    **The list is every way, not one of them.** The field used to be called
    ``missing_source_dirs`` and was computed as "not a directory on disk",
    which is two conditions under one name and neither of the word the
    refusal used: a source root that was a file was reported as *missing*,
    and a source root outside the workspace was not reported at all, so the
    diagnostic said the workspace was initialised while every task-scoped
    command refused it.
    """

    root: str
    initialised: bool
    source_dirs: tuple[str, ...]
    unusable_source_roots: tuple[SourceRootFinding, ...]
    output_root: str
    current_task: str | None


class DatabaseFinding(Result):
    """What ``doctor`` found about the store."""

    path: str
    present: bool
    revision: str | None
    at_head: bool


class PolicyFinding(Result):
    """What ``doctor`` found about the policy.

    ``rules`` are the rules rendered as text, in the order the policy holds
    them, because a rule's scope and its note are the parts an operator has
    to read.
    """

    source: str
    digest: str
    rules: tuple[str, ...]


class CapabilityFinding(Result):
    """One model provider capability, as ``doctor`` found it.

    ``outcome`` is the provider layer's own vocabulary — ``ok``,
    ``unsupported``, ``unverified`` or ``refused``. ``assumed`` says the
    operator overrode it, and ``usable`` says whether the stage that needs it
    may proceed: because the outcome was observed, or because the operator
    said so.
    """

    capability: str
    outcome: str
    reason: str | None
    assumed: bool
    usable: bool


class ProviderFinding(Result):
    """One configured model provider, as ``doctor`` found it."""

    name: str
    protocol: str
    model: str
    endpoint_fingerprint: str
    probed: bool
    capabilities: tuple[CapabilityFinding, ...]


class ApiSessionFinding(Result):
    """The local API's session token, as ``doctor`` found it.

    ``token`` is ``None`` unless the operator asked for it. A token in a
    diagnostic dump is a token in whatever the dump was pasted into, so it is
    withheld by default and the path it lives at is given instead.
    """

    path: str
    present: bool
    token: str | None = None


class DoctorReport(Result):
    """Everything ``doctor`` found, in one value.

    One value rather than four, because the command's job is to report and a
    report that can be half-printed is a report nobody can rely on.
    """

    workspace: WorkspaceFinding
    database: DatabaseFinding
    policy: PolicyFinding
    providers: tuple[ProviderFinding, ...]
    api_session: ApiSessionFinding


class ServiceStarting(Result):
    """The service ``serve`` is about to run.

    **The token is not here.** The service mints one at start-up and writes
    it to the workspace; this names the *path* it was written to, which is
    what a client needs in order to read it, and never the value. A secret
    in a machine-readable form is a secret in whatever the form was pasted
    into, which is the same reason ``doctor`` withholds the token unless the
    operator asks for it.

    ``origins`` is the allow-list the service will answer to, so the
    decision about the development web server is visible in the command's own
    output rather than only in a reading of its source. It is the service's
    own list, read from the service, and not a list the command composed
    twice.
    """

    host: str
    port: int
    origin: str
    origins: tuple[str, ...]
    task_id: str
    token_path: str
    static_dir: str | None = None


__all__ = [
    "ApiSessionFinding",
    "CapabilityFinding",
    "DatabaseFinding",
    "DoctorReport",
    "PolicyFinding",
    "ProviderFinding",
    "ServiceStarting",
    "SourceRootFinding",
    "WorkspaceFinding",
    "WorkspaceInitialised",
    "dumps",
    "emit_model",
    "emit_models",
]
