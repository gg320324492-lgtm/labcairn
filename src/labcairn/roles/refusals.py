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
    # -- the trajectory's own reasons (LC-P2-12 T01) ------------------------ #
    #: The chain holds no comment under the issue key a candidate points
    #: at. A judgement about a comment that is not there is invented.
    COMMENT_NOT_IN_THE_CHAIN = "comment_not_in_the_chain"
    #: The candidate quotes the advisor, and the words are not the
    #: comment's words. **A role may not put words in the advisor's
    #: mouth** — the quote must be a verbatim substring of the chain.
    QUOTE_NOT_IN_THE_CHAIN = "quote_not_in_the_chain"
    #: The alignment named is not one of the four the vocabulary closes.
    ALIGNMENT_STATE_UNKNOWN = "alignment_state_unknown"
    #: The candidate's issue type is not one of the closed vocabulary's
    #: labels — the same thirteen the memory and the gold set use.
    CANDIDATE_ISSUE_TYPE_UNKNOWN = "candidate_issue_type_unknown"
    #: The edit named does not answer the comment named, or is not in
    #: the store. An alignment to an edit that answers nothing is an
    #: alignment to nothing.
    EDIT_DOES_NOT_ANSWER_THE_COMMENT = "edit_does_not_answer_the_comment"
    #: A version the trajectory was asked to order is not in the
    #: project's graph. **A missing round is not a present one** — it is
    #: named, not papered over.
    VERSION_OUTSIDE_THE_GRAPH = "version_outside_the_graph"
    #: The accepted edges leave the order ambiguous — two versions no
    #: accepted edge separates, or a fork. **A similarity score may
    #: never silently decide an order**, and neither may this module.
    VERSION_ORDER_AMBIGUOUS = "version_order_ambiguous"
