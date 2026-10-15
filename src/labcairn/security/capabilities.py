"""The capability registry: what LabCairn can do, and what it deliberately cannot.

ADR-0003 §C5 gives ``evaluate()`` a *capability* parameter, and §C6.4 splits
capabilities into local analysis and outbound model requests. Both only work if
the set of capabilities is closed and known in advance, because the whole
permission argument is "a verdict over every capability" — which is not a
statement you can make about a set nobody can enumerate.

Three properties this module is responsible for
-----------------------------------------------

**1. The registry is closed, and an unknown id is a denial.** A tool layer that
receives ``capability="fs.writex"`` must not fall through to a default. §C5's
last line is *no matching rule returns DENY*, and "unknown capability" is the
case where *no rule can match* — so :func:`resolve_capability` returns ``None``
and the policy turns that into DENY. The refusal is never an exception, because
an exception is a crash the caller may catch and carry on from.

**2. Every capability's arguments are a closed model.** ADR-0003 §C6.2:
unknown keys are *rejected*, and the rejection names the key, because a model
told "invalid arguments" with no field named invents the key again. §C6.2 calls
this the deepagents ``_reject_unknown_keys`` lesson.

**3. There is no arbitrary code execution capability, at all.**
``docs/ARCHITECTURE.md`` says "No arbitrary model-generated host shell/Python
execution in Phase 1", and §Re-evaluation trigger 2 says the permission model was
designed around a closed registry and would need rework if an open execution
surface appeared. So the omission is not an oversight to be filled in later: it
is the property the design rests on. :data:`FORBIDDEN_ID_SUBSTRINGS` names what
must never appear, and a test asserts no registered id matches.

Why local and network are separate capabilities
-----------------------------------------------
§C6.4: *Local-only analysis tools and outbound model requests are distinct
capabilities, each independently scoped, so sending an excerpt to a provider is
never a side effect of running a local computation.* Merging them would mean an
allow rule for "analyse this CSV" also silently authorised transmitting it,
which is the failure ``ARCHITECTURE.md`` calls *no silent background upload*.
:data:`Effect` is the property policy rules can match on, so an operator can
write "deny every outbound request" as one rule that cannot be widened by adding
a local tool later.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field

from labcairn.security.paths import ResourceKey
from labcairn.security.untrusted import StableId, UntrustedField


class CapabilityId(StrEnum):
    """Every capability that exists. Closed — see the module docstring."""

    # -- filesystem, local ------------------------------------------------
    FS_READ = "fs.read"
    FS_LIST = "fs.list"
    FS_WRITE = "fs.write"
    FS_DELETE = "fs.delete"

    # -- source material, local and read-only ------------------------------
    SOURCE_READ = "source.read"
    SOURCE_INVENTORY = "source.inventory"

    # -- retrieval, local --------------------------------------------------
    RETRIEVAL_QUERY = "retrieval.query"

    # -- deterministic analysis, local and vetted --------------------------
    ANALYSIS_RUN = "analysis.run"

    # -- generated output --------------------------------------------------
    ARTIFACT_WRITE = "artifact.write"
    REPORT_RENDER = "report.render"

    # -- outbound model request --------------------------------------------
    MODEL_REQUEST = "model.request"


class Effect(StrEnum):
    """What running a capability can do to the outside world.

    This is the axis ``ARCHITECTURE.md``'s *no silent background upload*
    invariant is enforced on. ``NETWORK`` is not a modifier on a local
    capability; it is a separate capability, so denying one does not require
    auditing every tool that could have implied it.
    """

    #: Reads or writes the local filesystem. Never leaves the machine.
    LOCAL = "local"
    #: Causes bytes to leave the machine. Always requires an explicit,
    #: recorded approval — see :mod:`labcairn.security.approval`.
    NETWORK = "network"


#: Tokens that must never appear in a registered capability id.
#:
#: Matched as whole tokens (see :func:`looks_like_execution`), not as
#: substrings — and that distinction is not cosmetic. ``retrieval`` contains
#: ``eval`` as a substring, so a substring check rejects a perfectly ordinary
#: lexical-search capability while still missing ``fs.exec_helper``. Splitting on
#: non-alphanumerics and comparing tokens catches ``shell``, ``exec``,
#: ``exec_file`` and ``run_shell`` without the false positive.
FORBIDDEN_ID_TOKENS: Final[tuple[str, ...]] = (
    "sh",
    "shell",
    "exec",
    "execve",
    "eval",
    "spawn",
    "command",
    "cmd",
    "subprocess",
    "popen",
    "system",
    "python",
    "interpreter",
    "script",
    "runtime",
    "plugin",
)

_ID_TOKEN_SPLIT: Final = re.compile(r"[^A-Za-z0-9]+")
#: Trailing digits are stripped from a token before comparison, so ``python3``
#: and ``sh2`` are caught as ``python`` and ``sh``. Without this the check is
#: trivially evaded by appending a version number, which is the obvious first
#: thing anyone would do.
_TRAILING_DIGITS: Final = re.compile(r"[0-9]+$")


def looks_like_execution(capability: str) -> str | None:
    """The forbidden token this id contains, or ``None``.

    The executable check for §"no arbitrary code execution in Phase 1". Returns
    the offending token rather than a bool so a failure says *which* word gave
    it away — the id being added and the word that flagged it are usually
    different information, and a bare ``True`` makes the reader go looking.
    """
    tokens = {
        _TRAILING_DIGITS.sub("", token.lower())
        for token in _ID_TOKEN_SPLIT.split(capability)
        if token
    }
    for forbidden in FORBIDDEN_ID_TOKENS:
        if forbidden in tokens:
            return forbidden
    return None


class UnknownArgumentKeyError(ValueError):
    """A tool call carried a key the capability does not define.

    Carries the offending key on the object as well as in the message, because
    ADR-0003 §C6.2 requires the name to reach the model as a tool error, and a
    caller assembling that error wants the field, not a string to re-parse.
    """

    def __init__(self, *, capability: str, unknown_keys: tuple[str, ...]) -> None:
        listed = ", ".join(repr(k) for k in sorted(unknown_keys))
        super().__init__(
            f"{capability} received unknown argument key(s): {listed}. The "
            f"argument model is closed — an unrecognised key is either a typo or a "
            f"newer caller, and both deserve to be loud rather than ignored."
        )
        self.capability = capability
        self.unknown_keys = unknown_keys


class _Args(BaseModel):
    """Base for every capability's argument model.

    ``extra="forbid"`` is the §C6.2 requirement. ``frozen`` because arguments
    are hashed into an approval digest (ADR-0003 §C4): a model that could mutate
    its own arguments between the digest being computed and the operation
    running would make the digest decorative.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


class FsReadArgs(_Args):
    path: ResourceKey
    max_bytes: int = Field(default=1_000_000, ge=1, le=64_000_000)


class FsListArgs(_Args):
    path: ResourceKey
    pattern: str = "*"


class FsWriteArgs(_Args):
    path: ResourceKey


class FsDeleteArgs(_Args):
    path: ResourceKey
    recursive: bool = False


class SourceReadArgs(_Args):
    path: ResourceKey
    max_bytes: int = Field(default=64_000_000, ge=1, le=512_000_000)


class SourceInventoryArgs(_Args):
    path: ResourceKey


class RetrievalQueryArgs(_Args):
    """A local lexical query.

    ``query`` is imported text by construction — it is built from source
    material. It is annotated :data:`~labcairn.security.untrusted.UntrustedField`
    so its untrusted nature is in the type, and it is *not* consulted by
    permission evaluation: the decision is made on ``path`` and the capability.
    """

    path: ResourceKey
    query: UntrustedField
    top_k: int = Field(default=10, ge=1, le=200)


class AnalysisRunArgs(_Args):
    """A vetted, registered, deterministic operator.

    ``operator_id`` names an operator that must already be registered with a
    fixed implementation. There is no field for a code fragment, an expression,
    a module path or anything else that could be evaluated: that is what makes
    ``analysis.run`` different from a shell, and it is visible in the schema.
    """

    path: ResourceKey
    operator_id: StableId
    parameters: dict[str, Any] = Field(default_factory=dict)


class ArtifactWriteArgs(_Args):
    path: ResourceKey
    artifact_id: StableId


class ReportRenderArgs(_Args):
    path: ResourceKey
    template_id: StableId


class ModelRequestArgs(_Args):
    """An outbound request. The only capability whose payload leaves the box.

    ``excerpts`` is imported text, typed as such. What makes sending it
    *consented* is not this field but the approval digest: §C4's digest covers
    ``args``, so an approval to send excerpt set A does not authorise sending
    set B, and does not authorise sending a different number of them.
    """

    provider: StableId
    model: StableId
    path: ResourceKey
    excerpts: tuple[UntrustedField, ...] = ()
    purpose: str = Field(min_length=1, max_length=500)


@dataclass(frozen=True, slots=True)
class Capability:
    """One registered capability and everything policy needs to reason about it."""

    capability_id: CapabilityId
    effect: Effect
    args_model: type[_Args]
    #: What this capability is allowed to address. ``SOURCE`` capabilities may
    #: only ever land in a source root; ``OUTPUT`` capabilities only in the task
    #: output root. Enforced by policy, and asserted in tests.
    root_kinds: frozenset[str]
    #: One-line human description, for the approval prompt a human reads. It is
    #: rendered from the capability id and its *declared* arguments — never from
    #: imported content, because this string ends up in front of the person whose
    #: consent it is.
    summary: str


#: The registry. A mapping rather than an enum lookup so the metadata travels with
#: the id, and so an unknown id is a *miss* the policy can deny rather than an
#: AttributeError.
CAPABILITIES: Final[Mapping[str, Capability]] = {
    CapabilityId.FS_READ.value: Capability(
        capability_id=CapabilityId.FS_READ,
        effect=Effect.LOCAL,
        args_model=FsReadArgs,
        root_kinds=frozenset({"source", "output"}),
        summary="read a file from the workspace",
    ),
    CapabilityId.FS_LIST.value: Capability(
        capability_id=CapabilityId.FS_LIST,
        effect=Effect.LOCAL,
        args_model=FsListArgs,
        root_kinds=frozenset({"source", "output"}),
        summary="list entries under a workspace directory",
    ),
    CapabilityId.FS_WRITE.value: Capability(
        capability_id=CapabilityId.FS_WRITE,
        effect=Effect.LOCAL,
        args_model=FsWriteArgs,
        root_kinds=frozenset({"output"}),
        summary="write a file into the task output area",
    ),
    CapabilityId.FS_DELETE.value: Capability(
        capability_id=CapabilityId.FS_DELETE,
        effect=Effect.LOCAL,
        args_model=FsDeleteArgs,
        root_kinds=frozenset({"output"}),
        summary="delete an entry from the task output area",
    ),
    CapabilityId.SOURCE_READ.value: Capability(
        capability_id=CapabilityId.SOURCE_READ,
        effect=Effect.LOCAL,
        args_model=SourceReadArgs,
        root_kinds=frozenset({"source"}),
        summary="read supplied source material (read-only)",
    ),
    CapabilityId.SOURCE_INVENTORY.value: Capability(
        capability_id=CapabilityId.SOURCE_INVENTORY,
        effect=Effect.LOCAL,
        args_model=SourceInventoryArgs,
        root_kinds=frozenset({"source"}),
        summary="list supplied source material (read-only)",
    ),
    CapabilityId.RETRIEVAL_QUERY.value: Capability(
        capability_id=CapabilityId.RETRIEVAL_QUERY,
        effect=Effect.LOCAL,
        args_model=RetrievalQueryArgs,
        root_kinds=frozenset({"source"}),
        summary="run a local lexical search over source material",
    ),
    CapabilityId.ANALYSIS_RUN.value: Capability(
        capability_id=CapabilityId.ANALYSIS_RUN,
        effect=Effect.LOCAL,
        args_model=AnalysisRunArgs,
        root_kinds=frozenset({"source", "output"}),
        summary="run a registered deterministic analysis operator",
    ),
    CapabilityId.ARTIFACT_WRITE.value: Capability(
        capability_id=CapabilityId.ARTIFACT_WRITE,
        effect=Effect.LOCAL,
        args_model=ArtifactWriteArgs,
        root_kinds=frozenset({"output"}),
        summary="write an artifact into the task output area",
    ),
    CapabilityId.REPORT_RENDER.value: Capability(
        capability_id=CapabilityId.REPORT_RENDER,
        effect=Effect.LOCAL,
        args_model=ReportRenderArgs,
        root_kinds=frozenset({"output"}),
        summary="render a report into the task output area",
    ),
    CapabilityId.MODEL_REQUEST.value: Capability(
        capability_id=CapabilityId.MODEL_REQUEST,
        # The only NETWORK capability. Being the only one is the point of §C6.4.
        effect=Effect.NETWORK,
        args_model=ModelRequestArgs,
        root_kinds=frozenset({"source", "output"}),
        summary="send an excerpt set to a remote model provider (transmits data)",
    ),
}


def resolve_capability(capability: str | CapabilityId) -> Capability | None:
    """Look up a capability, or ``None`` when it is not registered.

    ``None`` — not an exception — is the whole design. ADR-0003 §C5 requires
    that a request with no matching rule is DENY; an unregistered id is the
    extreme case of that, and raising would hand the caller an exception it
    might catch, log as an internal error, and then fall through to a default.
    A ``None`` can only become a DENY at the one place that makes verdicts.
    """
    key = capability.value if isinstance(capability, CapabilityId) else str(capability)
    return CAPABILITIES.get(key)


def parse_args(capability: str | CapabilityId, raw: Mapping[str, Any]) -> _Args:
    """Validate a tool call's arguments against the capability's closed model.

    :raises UnknownCapabilityError: the id is not registered.
    :raises UnknownArgumentKeyError: a key the model does not define, **named**.
    :raises ValidationError: a defined key with an unusable value.
    """
    known = resolve_capability(capability)
    if known is None:
        raise UnknownCapabilityError(str(capability))

    allowed = set(known.args_model.model_fields)
    unknown = tuple(sorted(set(raw) - allowed))
    if unknown:
        raise UnknownArgumentKeyError(
            capability=known.capability_id.value,
            unknown_keys=unknown,
        )
    return known.args_model(**raw)


class UnknownCapabilityError(ValueError):
    """A capability id that is not in the registry.

    Distinct from :class:`UnknownArgumentKeyError` because the remedies differ: an
    unknown *capability* is a policy or wiring bug, an unknown *key* is a model
    that guessed a field name. §C6.2's "return it to the model as a tool error"
    applies to the second, not the first — telling a model to retry a capability
    id that will never exist wastes a turn.
    """

    def __init__(self, capability: str) -> None:
        super().__init__(
            f"{capability!r} is not a registered capability. Phase 1 has no arbitrary "
            f"code execution surface, so a capability cannot be created at runtime."
        )
        self.capability = capability


def declared_paths(args: _Args) -> tuple[ResourceKey, ...]:
    """The resource keys an argument model names, for evaluation and display.

    Every argument model in this registry carries exactly one ``path``. Reading
    it through one function rather than ``getattr`` keeps a future capability
    with two paths from silently dropping one.
    """
    return (args.path,)  # type: ignore[attr-defined]


def resource_key_for_display(key: ResourceKey) -> PurePosixPath:
    """Render a key for a human-facing approval prompt.

    Presentation only, and it never goes back into a decision. The path has
    already been canonicalised and rejected upstream; re-parsing a rendered
    string to make a permission call would reintroduce every aliasing problem
    this module removes.
    """
    return PurePosixPath(key)


def absolute_for_io(workspace_relative: str) -> Path:
    """Join a canonical key onto a base. For I/O only, after evaluation.

    Exists so that no caller does ``Path(cwd) / key`` itself. The base must be a
    root that was already bound and resolved; joining is safe because the key
    has no ``..``, no drive letter and no separators that are not POSIX.
    """
    if PurePosixPath(workspace_relative).is_absolute():
        msg = f"{workspace_relative!r} is absolute; resource keys are workspace-relative"
        raise ValueError(msg)
    return Path(*PurePosixPath(workspace_relative).parts)
