"""The rule memory's own reasons for saying no.

**The enumeration lives apart from the factory** for the reason the chain's
does: :mod:`labcairn.application.refusal` imports this module to name the
refusals it renders, and a module the application layer imports cannot
import the application layer back. The lifecycle that *raises* them is
:mod:`labcairn.guidance.rules`.
"""

from __future__ import annotations

from enum import StrEnum


class GuidanceRefusal(StrEnum):
    """Why the rule memory said no.

    **Each one names what was wrong**, because a refusal that says only
    "no" is a refusal nobody can act on. They are the memory's own
    reasons, and :data:`labcairn.application.refusal.GUIDANCE_REFUSALS`
    gives each one the name a surface renders.
    """

    #: The problem is not one of the closed vocabulary's labels. A rule
    #: whose problem is outside them cannot be measured against the gold
    #: set that uses them, so it cannot be stored.
    PROBLEM_OUTSIDE_VOCABULARY = "problem_outside_vocabulary"
    #: A required field of the rule — the statement, the context, the
    #: scope, the example, the proposer — is missing or empty. The work
    #: order's "must not" row is a rule with nothing in it.
    RULE_FIELD_EMPTY = "rule_field_empty"
    #: The rule names no chain material. **A rule without a source is not
    #: a rule** — it is a sentence nobody can check.
    RULE_WITHOUT_SOURCE = "rule_without_source"
    #: The rule, at that id and version, is not there.
    RULE_NOT_FOUND = "rule_not_found"
    #: Whoever proposed a rule cannot be the one who confirms it. One
    #: person reading twice is one person reading once with extra steps.
    CONFIRMER_IS_PROPOSER = "confirmer_is_proposer"
    #: The state transition asked for is not one the machine has: a rule
    #: cannot be confirmed twice, withdrawn twice, or moved from a state
    #: it does not hold.
    TRANSITION_NOT_POSSIBLE = "transition_not_possible"
    #: A dispute or a retraction without a reason is a shrug.
    RESOLUTION_WITHOUT_REASON = "resolution_without_reason"
    #: A counterexample with no case in it challenges nothing.
    COUNTEREXAMPLE_EMPTY = "counterexample_empty"
