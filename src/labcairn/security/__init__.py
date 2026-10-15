"""Scoped capability policies and path controls — the boundary.

The import direction is one-way and deliberate::

    workspace ──> security ──> core

``security`` imports ``runtime.operation`` for :class:`~labcairn.runtime.operation.Approval`
and nothing else, because §C4's rules are frozen there and this package is not
allowed a second copy of them. ``workspace`` composes the two — a selected root
with a read-only source area and a per-task output area — and adds no policy of
its own.

Entry points, in the order a caller meets them:

* :func:`~labcairn.security.paths.canonicalize` — turn a path into a
  :class:`~labcairn.security.paths.CanonicalPath`, or refuse.
* :meth:`~labcairn.security.policy.PermissionPolicy.evaluate` — the one verdict.
* :meth:`~labcairn.security.approval.ApprovalLedger.consume` — bind a human's
  consent to one specific operation, once.

The three properties that make this a boundary rather than a helper, each
specified in ADR-0003 and each asserted in ``tests/test_security_*.py``:

* **default deny**, and deny wins over every other rule (§C5);
* **both spellings of a path are matched**, declared and resolved (§C5);
* **imported text cannot reach a decision**, by construction (§C6).
"""

from __future__ import annotations

from labcairn.security.approval import (
    ApprovalGrant,
    ApprovalLedger,
    AuthorizationRefusedError,
    NoSuchApprovalError,
    SourceBinding,
    content_hash,
    make_approval,
    sources_intact,
)
from labcairn.security.capabilities import (
    CAPABILITIES,
    FORBIDDEN_ID_TOKENS,
    Capability,
    CapabilityId,
    Effect,
    UnknownArgumentKeyError,
    UnknownCapabilityError,
    looks_like_execution,
    parse_args,
    resolve_capability,
)
from labcairn.security.paths import (
    MAX_RESOURCE_KEY_LEN,
    AllowedRoot,
    CanonicalPath,
    PathRefusedError,
    PathRejection,
    ResourceKey,
    RootKind,
    bind_root,
    canonicalize,
)
from labcairn.security.policy import (
    DecisionReason,
    Permission,
    PermissionDecision,
    PermissionPolicy,
    ResourceRef,
    Rule,
    RulePatternError,
    default_policy,
    validate_rule_pattern,
)
from labcairn.security.untrusted import UntrustedOrigin, UntrustedText

__all__ = [
    "CAPABILITIES",
    "FORBIDDEN_ID_TOKENS",
    "MAX_RESOURCE_KEY_LEN",
    "AllowedRoot",
    "ApprovalGrant",
    "ApprovalLedger",
    "AuthorizationRefusedError",
    "CanonicalPath",
    "Capability",
    "CapabilityId",
    "DecisionReason",
    "Effect",
    "NoSuchApprovalError",
    "PathRefusedError",
    "PathRejection",
    "Permission",
    "PermissionDecision",
    "PermissionPolicy",
    "ResourceKey",
    "ResourceRef",
    "RootKind",
    "Rule",
    "RulePatternError",
    "SourceBinding",
    "UnknownArgumentKeyError",
    "UnknownCapabilityError",
    "UntrustedOrigin",
    "UntrustedText",
    "bind_root",
    "canonicalize",
    "content_hash",
    "default_policy",
    "looks_like_execution",
    "make_approval",
    "parse_args",
    "resolve_capability",
    "sources_intact",
    "validate_rule_pattern",
]
