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
    # -- the card's own reasons (LC-P2-12 T02) ------------------------------ #
    #: A required field of the card — the target, the reason, the next
    #: action, the uncertainty's own statement — is empty. A card with
    #: nothing in it advises nothing.
    CARD_FIELD_EMPTY = "card_field_empty"
    #: The card's evidence list is empty. **A card without evidence is
    #: an opinion wearing a card's clothes.**
    CARD_WITHOUT_EVIDENCE = "card_without_evidence"
    #: The severity named is not one the vocabulary closes.
    SEVERITY_UNKNOWN = "severity_unknown"
    #: A claim's kind is not one of scientific, advisor, reference. A
    #: claim of no kind is a sentence the reader cannot weigh.
    CLAIM_KIND_UNKNOWN = "claim_kind_unknown"
    #: A claim cites evidence the card does not declare. A claim nothing
    #: supports is not a claim.
    CLAIM_WITHOUT_EVIDENCE = "claim_without_evidence"
    #: An advisor claim's quote is not the advisor's words in the chain,
    #: or names no key or quote at all. **A voice without a source is
    #: an invention.**
    ADVICE_NOT_IN_THE_CHAIN = "advice_not_in_the_chain"
    #: The uncertainty named is not one the vocabulary closes.
    UNCERTAINTY_KIND_UNKNOWN = "uncertainty_kind_unknown"
    #: An abstention that cannot say what it lacks. **A shrug is not a
    #: result.**
    ABSTENTION_WITHOUT_A_MISSING = "abstention_without_a_missing"
    #: The memory holds no rule under the id a card tries to cite.
    RULE_NOT_IN_THE_MEMORY = "rule_not_in_the_memory"
    # -- the critique's own reasons (LC-P2-12 T03) -------------------------- #
    #: The verdict named is not one of the four the vocabulary closes.
    VERDICT_UNKNOWN = "verdict_unknown"
    #: The evidence a card names is in no form the review can check, and
    #: the verdict offered would claim it was checked. **The honest
    #: answer is cannot_assess, not a verdict that pretends.**
    UNVERIFIABLE_EVIDENCE_ACCEPTED = "unverifiable_evidence_accepted"
    #: A chain reference names a key the chain does not hold. **The
    #: review does not take the card's word about its own evidence.**
    EVIDENCE_NOT_IN_THE_CHAIN = "evidence_not_in_the_chain"
    #: A verdict that refuses the card carries no reason for the
    #: hand-over. A hand-over nobody can act on is not a hand-over.
    HANDOVER_WITHOUT_A_REASON = "handover_without_a_reason"
    # -- the arrangement's own reasons (LC-P2-12 T04) ----------------------- #
    #: The role's cost ceiling is not priced. **A budget whose price is
    #: unknown fails closed** — the call is refused, not sent and hoped
    #: about.
    SPEC_COST_UNMEASURED = "spec_cost_unmeasured"
    #: The request's kind is not one the routing table knows. A request
    #: the table does not know is not routed by a default.
    REQUEST_KIND_UNKNOWN = "request_kind_unknown"
    #: The request's risk is not one the vocabulary closes.
    REQUEST_RISK_UNKNOWN = "request_risk_unknown"
    #: The decision is neither accepted nor rejected.
    DECISION_UNKNOWN = "decision_unknown"
    #: The decision names nobody who made it.
    DECISION_WITHOUT_A_PERSON = "decision_without_a_person"
    #: The decision carries no reason. A shrug with a signature is not
    #: an auditable decision.
    DECISION_WITHOUT_A_REASON = "decision_without_a_reason"
