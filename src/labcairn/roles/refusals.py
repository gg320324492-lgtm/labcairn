"""The role machinery's own reasons for saying no.

**The enumeration lives apart from the factory** for the reason the
guidance memory's does: :mod:`labcairn.application.refusal` imports this
module to name the refusals it renders, and a module the application layer
imports cannot import the application layer back. The contract that
*raises* them is :mod:`labcairn.roles.spec`.
"""

from __future__ import annotations

from enum import StrEnum


class RoleRefusal(StrEnum):
    """Why the role machinery said no.

    **Each one names what was wrong**, because a refusal that says only
    "no" is a refusal nobody can act on. They are the contract's own
    reasons, and :data:`labcairn.application.refusal.ROLE_REFUSALS` gives
    each one the name a surface renders.
    """

    #: A required field of the spec — the objective, the schemas, the
    #: routing and budget fields, the prompt version, the model-config
    #: reference — is missing or empty. A contract with nothing in it
    #: binds nobody.
    SPEC_FIELD_EMPTY = "spec_field_empty"
    #: The spec names a capability that is not one the security layer has
    #: registered. A misspelled capability would otherwise grant nothing
    #: and be discovered only when the role tried to work.
    SPEC_CAPABILITY_UNKNOWN = "spec_capability_unknown"
    #: The spec names a forbidden action outside the closed five the
    #: architecture names. The list exists so the code can check it;
    #: a sixth action arrives by editing the enum, not by typing it in.
    SPEC_FORBIDDEN_ACTION_UNKNOWN = "spec_forbidden_action_unknown"
    #: The spec declares no purpose for which it may read material. A role
    #: that may read anything may read everything, which is not a grant.
    SPEC_PURPOSE_EMPTY = "spec_purpose_empty"
    #: The operation asked to exercise a capability the spec does not list.
    #: **This is the refusal the boundary exists to make** — machine
    #: readable, so a caller can branch on it without reading a message.
    SPEC_CAPABILITY_NOT_LISTED = "spec_capability_not_listed"
    #: The operation asked to perform an action the spec forbids. The
    #: prompt asking is not the boundary; this refusal is.
    SPEC_FORBIDDEN_ACTION_REQUESTED = "spec_forbidden_action_requested"
    #: The store holds no spec under that role id, or not at the version
    #: that was named.
    SPEC_NOT_FOUND = "spec_not_found"
    #: A spec at that role id and version is already defined. A new
    #: contract is a new version, not an overwrite of the old one.
    SPEC_ALREADY_DEFINED = "spec_already_defined"
