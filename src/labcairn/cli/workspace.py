"""The workspace on disk, and the one binding every task-scoped command uses.

A workspace is a directory the operator selected. Inside it LabCairn keeps
three things, and the third is why this module exists at all:

* the **store** — ``labcairn.db``, the task authority;
* the **roots** — a source directory for supplied material and a per-task
  output area, both of which the layer binds and the policy judges;
* the **configuration** — a small JSON file saying which database, which
  source directories, which policy and which task is current.

**The configuration is a file rather than a constant because a policy the
surface cannot change is a permission the surface grants itself.**
``docs/plans/LC-P1-11-12-task-breakdown.md`` §2.5 requires that "a surface
cannot grant itself a permission the other surfaces would not", and
:func:`~labcairn.security.policy.default_policy` denies everything: a CLI that
built its own allow-rules in code would be handing itself permissions the API
would not have. So the rules live in the workspace, the CLI reads them, and the
operator can edit them. The same file is what the API will read, which is why
the loader is here and is meant to be imported rather than reimplemented.

**The ``current_task`` field is a selection, not state.** It says which task
the operator is looking at, in the way a branch pointer says which branch is
checked out. The task's own state lives in the store, and this file never
becomes the authority for it: passing ``--task`` overrides it, and a pointer
to a task the store does not hold is refused by the layer rather than believed.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from labcairn.application import ApplicationContext
from labcairn.application.models import Result
from labcairn.core.ids import TaskId
from labcairn.db import TaskStore, create_db_engine, create_session_factory, session_scope
from labcairn.security.approval import ApprovalLedger
from labcairn.security.capabilities import Effect
from labcairn.security.policy import Permission, PermissionPolicy, Rule, default_policy
from labcairn.workspace.roots import OUTPUT_DIR_NAME, Workspace, WorkspaceError

#: The directory inside the workspace that holds LabCairn's own state.
#:
#: A dot-directory because it is not workspace content: it is the workspace's
#: own bookkeeping, and the default policy denies ``**/.*`` — so the CLI's
#: configuration is not something a capability-guarded read can reach either.
CONFIG_DIR_NAME = ".labcairn"

#: The workspace's configuration: the database, the source roots, the policy
#: and the current task.
CONFIG_FILE_NAME = "workspace.json"

#: The operator's policy rules, in the shape :class:`Rule` has.
POLICY_FILE_NAME = "policy.json"

#: Where the API's session token is written. The API mints it at start-up;
#: the CLI prints it. See §1.4.4 of the task breakdown.
#:
#: **The same name the service writes it under**, which is
#: :data:`labcairn.api.session.SESSION_FILE_NAME`. The file says what it *is*
#: — the session the service minted — and not which component wrote it, so
#: that a reader of the workspace does not have to know which surface put the
#: file there. This is a second declaration of one fact rather than a second
#: file, and the CLI does not import the API's package to avoid it: that
#: package pulls in the whole web stack, and a command that prints a path
#: should not pay for it. What keeps the two declarations from drifting apart
#: is
#: ``tests/test_cli.py::test_the_cli_and_the_service_name_the_token_file_the_same_way``.
SESSION_TOKEN_FILE_NAME = "session-token"

#: The store's file, inside the workspace root.
DATABASE_NAME = "labcairn.db"

#: The default source root, created by ``init``.
MATERIALS_DIR_NAME = "materials"

#: The configuration schema this build writes and reads.
CONFIG_SCHEMA_VERSION = 1


class WorkspaceSetupError(RuntimeError):
    """The workspace is not usable as asked.

    Distinct from :class:`labcairn.application.ApplicationRefusedError` because
    it is raised *before* the layer is reached: there is no context to refuse
    with. The CLI renders it with the same shape and the same exit code, so a
    caller sees one failure vocabulary.
    """


class WorkspaceConfig(Result):
    """The workspace's own configuration.

    ``source_dirs`` are workspace-relative and are the directories bound as
    source roots. They are recorded rather than inferred because the layer's
    ``source.inventory`` capability only addresses a *source* root: a material
    that is not inside one cannot be inventoried at all, so a later command
    that failed to rebind the same roots would report the task as having no
    material.
    """

    schema_version: int
    database: str
    source_dirs: tuple[str, ...]
    current_task: str | None = None


#: The rules a fresh workspace starts with.
#:
#: :func:`labcairn.security.policy.default_policy` denies everything, which is
#: the right posture for a workspace nobody has configured and a useless one
#: for a workspace whose operator is sitting in front of it. These rules are the
#: narrowest set that lets the CLI do its own job, and they are written to the
#: file so the operator can see them and change them.
#:
#: The two rules ``default_policy`` already had are kept, for the same
#: reasons: dotfiles are denied because that is where credentials live, and a
#: network effect is asked about because nothing is transmitted without a
#: human. They are listed after the workspace's own allowances because the
#: order of the list does not decide anything — the policy takes the worst
#: verdict, so a deny anywhere wins — and the list is what ``doctor`` prints.
DEFAULT_POLICY_RULES: tuple[Rule, ...] = (
    Rule(
        effect=Permission.ALLOW,
        pattern="output",
        capabilities=frozenset({"fs.read", "fs.list"}),
        note="reading this task's own record, and listing what it has produced",
    ),
    Rule(
        effect=Permission.ALLOW,
        pattern="output",
        capabilities=frozenset({"fs.write"}),
        note="creating this task's own output area",
    ),
    Rule(
        effect=Permission.ALLOW,
        pattern="**",
        capabilities=frozenset({"source.inventory"}),
        note="inventorying the supplied material; the registry keeps this to source roots",
    ),
    Rule(
        effect=Permission.DENY,
        pattern="**/.*",
        note="dotfiles are where credentials live; no research deliverable needs one",
    ),
    Rule(
        effect=Permission.ASK,
        pattern="**",
        effects=frozenset({Effect.NETWORK}),
        note="transmitting data to a provider always needs a human",
    ),
)


@dataclass(frozen=True, slots=True)
class WorkspaceLocation:
    """Where the workspace's files are, before anything is read.

    Held separately from the configuration so that ``init`` can describe a
    workspace that does not exist yet.
    """

    root: Path

    @property
    def config_dir(self) -> Path:
        return self.root / CONFIG_DIR_NAME

    @property
    def config_path(self) -> Path:
        return self.config_dir / CONFIG_FILE_NAME

    @property
    def policy_path(self) -> Path:
        return self.config_dir / POLICY_FILE_NAME

    @property
    def token_path(self) -> Path:
        """Where the service's session token is, if it has written one."""
        return self.config_dir / SESSION_TOKEN_FILE_NAME

    @property
    def database_path(self) -> Path:
        return self.root / DATABASE_NAME

    @property
    def materials_path(self) -> Path:
        return self.root / MATERIALS_DIR_NAME

    @property
    def output_path(self) -> Path:
        return self.root / OUTPUT_DIR_NAME


def locate(root: Path) -> WorkspaceLocation:
    """Where *root*'s files are.

    Not a check: the location exists whether or not the workspace does.
    """
    return WorkspaceLocation(root=root.expanduser().resolve())


def is_initialised(location: WorkspaceLocation) -> bool:
    """Whether *location* holds a workspace.

    The configuration file is the marker, because it is the one file ``init``
    writes last. A directory with a stray ``labcairn.db`` and no configuration
    is a directory the CLI will not claim as a workspace.
    """
    return location.config_path.is_file()


def read_config(location: WorkspaceLocation) -> WorkspaceConfig:
    """The workspace's configuration.

    :raises WorkspaceSetupError: the file is missing, unreadable, or not the shape
        this build writes. A configuration this build cannot read is refused
        rather than guessed at.
    """
    try:
        raw = json.loads(location.config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise WorkspaceSetupError(
            f"{location.config_path} does not exist, so {location.root} is not a "
            "LabCairn workspace. Run `labcairn init` there, or point --workspace at "
            "one that is."
        ) from error
    except (OSError, json.JSONDecodeError) as error:
        raise WorkspaceSetupError(
            f"{location.config_path} could not be read as JSON: {error}"
        ) from error
    if not isinstance(raw, Mapping):
        raise WorkspaceSetupError(f"{location.config_path} must hold a JSON object.")
    try:
        config = WorkspaceConfig.model_validate(raw)
    except ValueError as error:
        raise WorkspaceSetupError(
            f"{location.config_path} is not a workspace configuration this build "
            f"understands: {error}"
        ) from error
    if config.schema_version != CONFIG_SCHEMA_VERSION:
        raise WorkspaceSetupError(
            f"{location.config_path} declares schema version {config.schema_version}, "
            f"and this build reads version {CONFIG_SCHEMA_VERSION}."
        )
    return config


def write_config(location: WorkspaceLocation, config: WorkspaceConfig) -> None:
    """Write the workspace's configuration."""
    location.config_dir.mkdir(parents=True, exist_ok=True)
    location.config_path.write_text(
        json.dumps(config.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_policy(location: WorkspaceLocation, rules: tuple[Rule, ...]) -> None:
    """Write the operator's policy rules.

    The file is the rules and nothing else, so that the shape is the one the
    loader reads back and the one the API will read.
    """
    location.config_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "rules": [_rule_to_mapping(r) for r in rules],
    }
    location.policy_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _rule_to_mapping(rule: Rule) -> dict[str, Any]:
    """A rule as the file spells it.

    Field names are the :class:`Rule` dataclass's own, so the mapping between
    the file and the rule is mechanical and a reader can check it by eye.
    """
    return {
        "effect": rule.effect.value,
        "pattern": rule.pattern,
        "capabilities": sorted(rule.capabilities) if rule.capabilities is not None else None,
        "root_ids": sorted(rule.root_ids) if rule.root_ids is not None else None,
        "effects": sorted(effect.value for effect in rule.effects)
        if rule.effects is not None
        else None,
        "task_ids": sorted(rule.task_ids) if rule.task_ids is not None else None,
        "note": rule.note,
    }


def load_policy(location: WorkspaceLocation) -> PermissionPolicy:
    """The workspace's policy, from its file.

    A workspace with no policy file gets
    :func:`labcairn.security.policy.default_policy`, which denies everything.
    That is deliberate: a workspace whose policy file has gone missing is a
    workspace whose permissions are unknown, and the safe reading of unknown is
    no.
    """
    path = location.policy_path
    if not path.is_file():
        return default_policy()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise WorkspaceSetupError(f"{path} could not be read as JSON: {error}") from error
    if not isinstance(raw, Mapping) or not isinstance(raw.get("rules"), list):
        raise WorkspaceSetupError(f'{path} must hold a JSON object with a "rules" list.')
    return PermissionPolicy.from_rules(tuple(_rule_from_mapping(item) for item in raw["rules"]))


def _rule_from_mapping(payload: Any) -> Rule:
    """One rule from the file.

    :raises WorkspaceSetupError: the entry is not a rule this build understands.
        An unknown key is an error rather than a dropped field, for the same
        reason the persisted contracts forbid extras: a typo in a rule's scope
        would otherwise widen what the rule covers.
    """
    from labcairn.security.policy import Permission

    if not isinstance(payload, Mapping):
        raise WorkspaceSetupError('every entry in a policy file\'s "rules" list must be an object.')
    known = {"effect", "pattern", "capabilities", "root_ids", "effects", "task_ids", "note"}
    unknown = sorted(set(payload) - known)
    if unknown:
        raise WorkspaceSetupError(
            f"unknown key(s) in a policy rule: {', '.join(unknown)}. The rule keys are "
            f"{', '.join(sorted(known))}."
        )
    try:
        effect = Permission(str(payload["effect"]))
    except (KeyError, ValueError) as error:
        raise WorkspaceSetupError(
            f'a policy rule needs an "effect" of allow, ask or deny: {error}'
        ) from error
    try:
        return Rule(
            effect=effect,
            pattern=str(payload["pattern"]),
            capabilities=_optional_set(payload.get("capabilities")),
            root_ids=_optional_set(payload.get("root_ids")),
            effects=_optional_effects(payload.get("effects")),
            task_ids=_optional_set(payload.get("task_ids")),
            note=str(payload.get("note", "")),
        )
    except (KeyError, ValueError) as error:
        raise WorkspaceSetupError(f"a policy rule could not be read: {error}") from error


def _optional_set(value: Any) -> frozenset[str] | None:
    """A scope that may be absent (``None``) but not empty.

    ``None`` means "any" and an empty set means "nothing"; the second is
    almost never what a rule file meant, so it is refused rather than read as
    a rule that matches nothing.
    """
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("a rule scope must be a list of strings, or absent")
    if not value:
        raise ValueError("a rule scope may not be empty; omit it to mean 'any'")
    return frozenset(value)


def _optional_effects(value: Any) -> frozenset[Effect] | None:
    """The ``effects`` scope, read into the enum the rule expects."""
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError('a rule\'s "effects" scope must be a list of strings, or absent')
    if not value:
        raise ValueError("a rule's \"effects\" scope may not be empty; omit it to mean 'any'")
    try:
        return frozenset(Effect(item) for item in value)
    except ValueError as error:
        raise ValueError(f"unknown effect in a rule scope: {error}") from error


def source_paths(location: WorkspaceLocation, config: WorkspaceConfig) -> tuple[Path, ...]:
    """The source roots, as absolute paths.

    A source directory that is not inside the workspace is refused here rather
    than by the layer, so the message can name the directory the operator
    named instead of a path they did not.
    """
    paths: list[Path] = []
    for relative in config.source_dirs:
        candidate = (location.root / relative).resolve()
        if not candidate.is_relative_to(location.root):
            raise WorkspaceSetupError(
                f"the source directory {relative!r} resolves to {candidate}, which is "
                f"outside the workspace {location.root}. A source root the workspace "
                "does not contain is a root the operator's selection does not govern."
            )
        paths.append(candidate)
    return tuple(paths)


def bind_workspace(
    location: WorkspaceLocation,
    config: WorkspaceConfig,
    task_id: TaskId,
) -> Workspace:
    """Bind the workspace for *task_id*.

    :raises WorkspaceSetupError: a root could not be bound — the workspace is not
        there, or a configured source directory is missing. The layer refuses
        the same thing, but it can only say it in terms of the path it was
        given, and the operator named the directory.
    """
    try:
        return Workspace.bind(
            location.root,
            task_id=task_id,
            source_dirs=source_paths(location, config),
        )
    except (WorkspaceError, OSError) as error:
        raise WorkspaceSetupError(
            f"the workspace at {location.root} could not be bound: {error}"
        ) from error


@contextmanager
def application_context(
    location: WorkspaceLocation,
    config: WorkspaceConfig,
    task_id: TaskId,
) -> Iterator[ApplicationContext]:
    """The context every task-scoped command runs against.

    The store handle is built here and nowhere else: the surface's job is to
    hand the layer something it can read and write through, and every read and
    write the layer performs goes through the capability model. The handle is
    the *only* thing the surface constructs, and it is the thing the layer
    consumes.

    The session is closed and the engine disposed on the way out, so a command
    that raises leaves nothing holding the database file open — which matters
    on Windows, where an open file cannot be deleted and a test's temporary
    directory would survive the run that made it.
    """
    workspace = bind_workspace(location, config, task_id)
    engine = create_db_engine(location.root / config.database)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            yield ApplicationContext(
                workspace=workspace,
                store=TaskStore(session),
                policy=load_policy(location),
                ledger=ApprovalLedger(),
            )
    finally:
        engine.dispose()


__all__ = [
    "CONFIG_DIR_NAME",
    "CONFIG_FILE_NAME",
    "CONFIG_SCHEMA_VERSION",
    "DATABASE_NAME",
    "DEFAULT_POLICY_RULES",
    "MATERIALS_DIR_NAME",
    "POLICY_FILE_NAME",
    "SESSION_TOKEN_FILE_NAME",
    "WorkspaceConfig",
    "WorkspaceLocation",
    "WorkspaceSetupError",
    "application_context",
    "bind_workspace",
    "is_initialised",
    "load_policy",
    "locate",
    "read_config",
    "source_paths",
    "write_config",
    "write_policy",
]
