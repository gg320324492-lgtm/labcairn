"""The role contracts: the specs' own reads and writes, through the layer.

**What this module is.** A role's contract is a row — ``agent_role_specs`` —
and :mod:`labcairn.roles.spec` used to read and write it directly, by
importing ``labcairn.db.models`` and writing its own ``select(...)``
statements. **That is the arrangement the application layer exists to
prevent**: a caller that reaches the store directly is a caller the
capability model does not reach, and a guard applied to an operation would
apply to some of the callers and not the others.

So the contract's reads and writes live here, and :mod:`labcairn.roles.spec`
calls these operations instead of the store.

**What these operations refuse.** The contract's own reasons, in the layer's
vocabulary: no spec carries that role id at that version, and a spec at that
role id and version is already defined. The rules about **the words** — the
fields that may not be empty, the capability the security layer has not
registered, the forbidden action outside the closed five, the purpose that
was not declared — stay with the module that owns them, because they are
about what the caller said rather than about what a row may hold.

**And a contract names no resource.** A role's spec says what a role may
do, and it says it about no file at all: the capability model's resources
are paths in a workspace, and a contract is not one. The permission that
governs what a role may *read* is asked by the operations that name the
material — :mod:`labcairn.guidance.retrieval` asks it per source at serve
time and drops the sources the reader may not reach (ADR-0003 C5). These
operations are the only way to the rows, and a guard added here reaches
**every** caller.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import role_refused
from labcairn.db.models import AgentRoleSpecRow
from labcairn.roles.refusals import RoleRefusal
from labcairn.security.capabilities import CapabilityId

if TYPE_CHECKING:
    from labcairn.roles.models import AgentRoleSpec, ForbiddenAction


@dataclass(frozen=True)
class RoleSpecDraft:
    """The contract a role works under, as the write takes it.

    **Every field the contract has is here, and none of them has a
    default.** A contract that granted a capability the caller did not
    name, or a budget nobody set, would be a contract the code invented —
    and the whole point of the D1 list is that it is written down.
    """

    role_id: str
    role_version: int
    objective: str
    input_schema: str
    output_schema: str
    allowed_capabilities: tuple[CapabilityId, ...]
    forbidden_actions: tuple[ForbiddenAction, ...]
    allowed_data_purposes: tuple[str, ...]
    provider_routing_policy: str
    cost_budget: float | None
    token_budget: int
    timeout_seconds: int
    retry_policy: str
    fallback_policy: str
    abstain_conditions: tuple[str, ...]
    escalation_conditions: tuple[str, ...]
    prompt_template_version: str
    model_config_ref: str
    defined_at: datetime


def read_role_spec(
    context: ApplicationContext, *, role_id: str, version: int | None = None
) -> AgentRoleSpec:
    """The contract a role works under — the version named, or the highest.

    **The highest, when no version is named.** A role's contract is
    versioned, and a caller that means "the contract this role works
    under" means the newest one; a caller that means a particular version
    names it.

    :raises ApplicationRefusedError: no row carries that role id, at the
        version named or at any version.
    """
    session = context.store.session
    if version is not None:
        row = session.get(AgentRoleSpecRow, (role_id, version))
    else:
        row = session.scalars(
            select(AgentRoleSpecRow)
            .where(AgentRoleSpecRow.role_id == role_id)
            .order_by(AgentRoleSpecRow.role_version.desc())
            .limit(1)
        ).first()
    if row is None:
        raise role_refused(
            RoleRefusal.SPEC_NOT_FOUND,
            f"the store holds no spec for {role_id!r}"
            + ("" if version is None else f" at version {version}"),
        )
    return _the_spec(row)


def write_role_spec(context: ApplicationContext, draft: RoleSpecDraft) -> AgentRoleSpec:
    """Write the contract, as a versioned row.

    **A new contract is a new row, never an overwrite.** The primary key is
    the pair of the role's id and the contract's version, so a second write
    with the same pair would be a second row wearing one name — and the
    old terms would be gone, which is what versioning exists to prevent.

    **The list clauses are written as JSON arrays.** The database can say
    ``json_valid`` and that the column holds an array; what it cannot say
    across a JSON column it leaves to the API — that every capability named
    is one the security layer has registered, and that every forbidden action
    is one of the five the architecture closes. Those are the caller's
    checks, and this operation writes what they accepted.

    :raises ApplicationRefusedError: a spec at that role id and version is
        already defined.
    """
    session = context.store.session
    existing = session.get(AgentRoleSpecRow, (draft.role_id, draft.role_version))
    if existing is not None:
        raise role_refused(
            RoleRefusal.SPEC_ALREADY_DEFINED,
            f"a spec for {draft.role_id!r} at version {draft.role_version} is already"
            " defined; a new contract is a new version, not an overwrite",
        )
    row = AgentRoleSpecRow(
        role_id=draft.role_id,
        role_version=draft.role_version,
        objective=draft.objective,
        input_schema=draft.input_schema,
        output_schema=draft.output_schema,
        allowed_capabilities=json.dumps([item.value for item in draft.allowed_capabilities]),
        forbidden_actions=json.dumps([item.value for item in draft.forbidden_actions]),
        allowed_data_purposes=json.dumps(list(draft.allowed_data_purposes)),
        provider_routing_policy=draft.provider_routing_policy,
        cost_budget=draft.cost_budget,
        token_budget=draft.token_budget,
        timeout_seconds=draft.timeout_seconds,
        retry_policy=draft.retry_policy,
        fallback_policy=draft.fallback_policy,
        abstain_conditions=json.dumps(list(draft.abstain_conditions)),
        escalation_conditions=json.dumps(list(draft.escalation_conditions)),
        prompt_template_version=draft.prompt_template_version,
        model_config_ref=draft.model_config_ref,
        defined_at=draft.defined_at,
    )
    session.add(row)
    session.flush()
    return _the_spec(row)


def _the_spec(row: AgentRoleSpecRow) -> AgentRoleSpec:
    """The contract a row holds, decoded.

    **The vocabulary is the code's, not the row's.** A row names a
    capability by its id and a forbidden action by its value, and both are
    the enums the security layer and the architecture close — so a row that
    named something else would fail here rather than be carried into a role
    that believes it holds a grant nobody made.

    **The contract's own types are imported here rather than at the top of
    the module, and the reason is a loop.** The contract types live in
    :mod:`labcairn.roles.models`, and that module reaches for the layer's
    refusal vocabulary at import time — so a module-level import here would
    make ``labcairn.roles.models`` half-built while the layer was still
    being built, and the import of the contract type would fail with *"cannot
    import name ... from partially initialized module"*. The loop was hidden
    while this module was reached only through
    :mod:`labcairn.application.roles`; the layer's own package now exports
    these operations, and a package that cannot be imported is a package
    that cannot be used.
    """
    from labcairn.roles.models import AgentRoleSpec, ForbiddenAction

    return AgentRoleSpec(
        role_id=row.role_id,
        role_version=row.role_version,
        objective=row.objective,
        input_schema=row.input_schema,
        output_schema=row.output_schema,
        allowed_capabilities=tuple(
            CapabilityId(item) for item in json.loads(row.allowed_capabilities)
        ),
        forbidden_actions=tuple(
            ForbiddenAction(item) for item in json.loads(row.forbidden_actions)
        ),
        allowed_data_purposes=tuple(json.loads(row.allowed_data_purposes)),
        provider_routing_policy=row.provider_routing_policy,
        cost_budget=row.cost_budget,
        token_budget=row.token_budget,
        timeout_seconds=row.timeout_seconds,
        retry_policy=row.retry_policy,
        fallback_policy=row.fallback_policy,
        abstain_conditions=tuple(json.loads(row.abstain_conditions)),
        escalation_conditions=tuple(json.loads(row.escalation_conditions)),
        prompt_template_version=row.prompt_template_version,
        model_config_ref=row.model_config_ref,
    )


__all__ = ["RoleSpecDraft", "read_role_spec", "write_role_spec"]
