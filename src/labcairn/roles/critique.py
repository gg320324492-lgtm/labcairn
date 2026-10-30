"""Role C: the independent critique — a review of the card, not of the science.

LC-P2-12 T03. Role C reads what role B read **and more**: the original
material and its sources, B's cards, and **the counter-evidence it
retrieves for itself** — the memory's rules with their cases against
them, looked up by C's own query, not accepted from B's reasoning. It
checks the logic, whether the experiments support the conclusions, the
contrary evidence, the overreach, and whether the advice is actionable,
and it names what is missing and what a person must handle.

**And a review of a card is not a review of the science.** The verdict
enters the record at the grade its own evidence supports — ``inferred``,
a model's judgement about a model's output — and **no verdict promotes
anything**: the review writes nothing, so two models agreeing is still
a corroboration and never a confirmation (ADR-0018 D9). The promotion
paths are the record constructor's and a person's; this module holds
neither.

**C verifies what it can and refuses to pretend about the rest.** An
evidence reference of the form ``chain:<key>`` is checked against the
chain; a reference in no form C can check makes a ``supported`` verdict
a lie, and the module refuses it — C's honest answer to evidence it
cannot reach is ``cannot_assess``, with the reason a person needs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from sqlalchemy import select

from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import role_refused
from labcairn.db.models import FeedbackEventRow
from labcairn.guidance.retrieval import search_rules
from labcairn.roles.guidance import GuidanceCard, RuleCitation
from labcairn.roles.refusals import RoleRefusal
from labcairn.roles.spec import AgentRoleSpec, RoleOutput

#: What an independent review can conclude. Closed: a fifth verdict
#: arrives by a decision, not by a call.
VERDICTS: Final[frozenset[str]] = frozenset(
    {"supported", "needs_revision", "unsupported", "cannot_assess"}
)

#: The grade a review carries. **A review of a card is not a review of
#: the science** — this is a model's judgement about a model's output,
#: and the grade says so rather than letting a verdict wear a check's
#: clothes.
REVIEW_GRADE: Final[str] = "inferred"


@dataclass(frozen=True)
class ReviewVerdict(RoleOutput):
    """Role C's output: what the review concluded, and what it read.

    The ``counter_evidence`` is what **C retrieved** — the memory's
    rules and the cases against them, from C's own query — and not
    what B declared. The ``handover_reason`` is why a person must
    handle what the card could not, and it is required exactly when
    the verdict says the card did not stand.
    """

    reviewed_locator: str
    reviewed_issue_type: str
    verdict: str
    grade: str
    counter_evidence: tuple[RuleCitation, ...]
    repair_advice: str
    handover_reason: str | None


def _chain_key_of(evidence_ref: str) -> str | None:
    """The chain key a reference names, when it names one C can check."""
    prefix = "chain:"
    if not evidence_ref.startswith(prefix):
        return None
    return evidence_ref[len(prefix) :]


def review_card(
    context: ApplicationContext,
    *,
    spec: AgentRoleSpec,
    card: GuidanceCard,
    verdict: str,
    repair_advice: str,
    handover_reason: str | None = None,
) -> ReviewVerdict:
    """One independent review: the card checked against the chain and the memory.

    The card's ``chain:`` evidence references are verified against the
    store; the counter-evidence is retrieved here, by this role's own
    query, and travels in the verdict whether the card survives or not.

    :raises ApplicationRefusedError: the verdict is outside the four;
        the repair advice is empty; a chain reference names a key the
        chain does not hold; a reference C cannot check is offered to
        a verdict that claims the card stands; or a verdict that
        refuses the card carries no reason for the hand-over.
    """
    session = context.store.session
    if verdict not in VERDICTS:
        raise role_refused(
            RoleRefusal.VERDICT_UNKNOWN,
            f"{verdict!r} is not one of {sorted(VERDICTS)}",
        )
    if not repair_advice.strip():
        raise role_refused(
            RoleRefusal.CARD_FIELD_EMPTY,
            "the repair advice is empty, and a verdict that says nothing to do is a shrug",
        )
    for evidence_ref in card.evidence_refs:
        key = _chain_key_of(evidence_ref)
        if key is None:
            if verdict in {"supported", "unsupported"}:
                raise role_refused(
                    RoleRefusal.UNVERIFIABLE_EVIDENCE_ACCEPTED,
                    f"the evidence {evidence_ref!r} is in no form the review"
                    f" can check, and a {verdict!r} verdict would claim it"
                    " was",
                )
            continue
        held = session.scalars(
            select(FeedbackEventRow.feedback_id).where(FeedbackEventRow.issue_key == key)
        ).first()
        if held is None:
            raise role_refused(
                RoleRefusal.EVIDENCE_NOT_IN_THE_CHAIN,
                f"the evidence {evidence_ref!r} names a key the chain does"
                " not hold, and the review does not take the card's word",
            )
    if verdict in {"needs_revision", "unsupported", "cannot_assess"} and not (
        handover_reason and handover_reason.strip()
    ):
        raise role_refused(
            RoleRefusal.HANDOVER_WITHOUT_A_REASON,
            f"a {verdict!r} verdict hands the card to a person, and a"
            " hand-over without its reason is a hand-over nobody can act on",
        )
    counter_evidence = tuple(
        RuleCitation(
            rule_id=hit.rule.rule_id,
            version=hit.rule.version,
            statement=hit.rule.statement,
            counterexamples=tuple(item.statement for item in hit.rule.counterexamples),
        )
        for hit in search_rules(context, issue_type=card.issue_type)
        if hit.rule.counterexamples
    )
    return ReviewVerdict(
        role_id=spec.role_id,
        role_version=spec.role_version,
        reviewed_locator=card.target_locator,
        reviewed_issue_type=card.issue_type,
        verdict=verdict,
        grade=REVIEW_GRADE,
        counter_evidence=counter_evidence,
        repair_advice=repair_advice,
        handover_reason=handover_reason,
    )
