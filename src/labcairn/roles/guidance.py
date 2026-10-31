"""Role B: the guidance card — a diagnosis a student can act on, with its limits.

LC-P2-12 T02. The card is role B's one output, and it carries every
field the architecture names (ADR-0018 D3): where in the manuscript it
points, what the problem is, how bad it is, why it is a problem, the
evidence behind it, the cases in history it stands on, **where it does
not hold**, what to do next, and how sure the role is.

**Four prohibitions the work order makes refusals, not requests.**

- **A card without evidence is not a card.** The evidence references are
  not optional, and every claim's own reference must be among them —
  a claim citing evidence the card does not declare is a claim nothing
  supports.
- **Scientific facts and stylistic advice are recorded separately.** A
  claim that a method underpowers a study is a different kind of
  sentence from a note that the figure order could improve, and the
  type keeps them apart: a style note cannot ride in as a fact, and a
  fact cannot hide as a style note.
- **And the advisor's opinion is quoted, not invented.** A claim of
  kind ``advisor`` names the chain's key and quotes the comment, and
  the quote must be a verbatim substring of what the chain holds —
  the same rule role A's candidates keep.
- **No write-back.** The card is a proposal in memory; nothing here
  touches a manuscript, and the contract's forbidden actions say so
  where a caller could forget.

**An abstention is a result** (§2.3): material the role cannot answer
produces :func:`abstaining_card` — a card whose uncertainty names what
was missing — and never an empty return, and never a crash.

**And a card cites a rule with its counter-examples** (§2.4): the
citation is built by :func:`cite_rule` from the memory's own read, so
the cases against a rule travel with the advice and cannot be dropped
by a caller who found them inconvenient.

**The chain's rows are reached through the application layer.** The
comments a card's advisor claims are quoted from come from
:mod:`labcairn.application.chain`, so the card reads no table of its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from labcairn.application import chain as chain_layer
from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import ApplicationRefusedError, role_refused
from labcairn.guidance.rules import read_rule
from labcairn.papers.labels import ISSUE_LABELS
from labcairn.roles.models import AgentRoleSpec, RoleOutput
from labcairn.roles.refusals import RoleRefusal

#: How bad the problem is. Closed: a fourth degree arrives by a
#: decision, not by a call.
SEVERITIES: Final[frozenset[str]] = frozenset({"minor", "moderate", "major"})

#: What kind of sentence a claim is. **The two kinds the work order
#: separates are ``scientific`` and ``advisor``** — a fact about the
#: study, and what the advisor said. ``reference`` is a claim whose
#: warrant is a source the card's evidence list names.
CLAIM_KINDS: Final[frozenset[str]] = frozenset({"scientific", "advisor", "reference"})

#: The kinds of uncertainty a card can carry. The abstention is the
#: honest one: the role cannot answer, and it says what was missing.
UNCERTAINTY_KINDS: Final[frozenset[str]] = frozenset({"low", "moderate", "high", "abstention"})


@dataclass(frozen=True)
class Uncertainty:
    """How sure the role is, and what it would need to be surer.

    An abstention's ``missing`` is the **named** list of what the role
    did not have — an abstention that cannot say what it lacks is a
    shrug wearing a result's clothes, and the constructor refuses it.
    """

    kind: str
    what_is_uncertain: str
    missing: tuple[str, ...] = ()


@dataclass(frozen=True)
class CardClaim:
    """One sentence of the card's case, with its warrant.

    A ``scientific`` or ``reference`` claim carries an evidence
    reference the card declares; an ``advisor`` claim names the chain
    key and quotes the comment, verbatim. **A claim of no kind is not
    a claim** — the kinds are how the reader tells a fact from a note
    from a voice.
    """

    text: str
    kind: str
    evidence_ref: str | None = None
    issue_key: str | None = None
    advisor_quote: str | None = None


@dataclass(frozen=True)
class RuleCitation:
    """A rule the card cites, with the cases against it.

    **Built by :func:`cite_rule` from the memory's own read** — the
    counterexamples are the memory's, not the card's, and a caller has
    no parameter to thin them with.
    """

    rule_id: str
    version: int
    statement: str
    counterexamples: tuple[str, ...]


@dataclass(frozen=True)
class GuidanceCard(RoleOutput):
    """Role B's output: the diagnosis, the evidence, the limits, the step."""

    target_locator: str
    issue_type: str
    severity: str
    reason: str
    evidence_refs: tuple[str, ...]
    suggested_next_action: str
    uncertainty: Uncertainty
    claims: tuple[CardClaim, ...] = ()
    style_notes: tuple[str, ...] = ()
    rule_refs: tuple[RuleCitation, ...] = ()
    historical_case_refs: tuple[str, ...] = ()
    counterexamples_or_limits: tuple[str, ...] = ()


def cite_rule(context: ApplicationContext, *, rule_id: str) -> RuleCitation:
    """The rule as the memory holds it, with its counterexamples attached.

    :raises ApplicationRefusedError: the memory holds no rule under
        that id.
    """
    try:
        rule = read_rule(context, rule_id=rule_id)
    except ApplicationRefusedError as refused:
        raise role_refused(
            RoleRefusal.RULE_NOT_IN_THE_MEMORY,
            f"the memory holds no rule under {rule_id!r}, and a card cannot"
            " cite one it did not read",
        ) from refused
    return RuleCitation(
        rule_id=rule.rule_id,
        version=rule.version,
        statement=rule.statement,
        counterexamples=tuple(item.statement for item in rule.counterexamples),
    )


def _checked_claims(
    context: ApplicationContext, *, claims: tuple[CardClaim, ...], evidence_refs: tuple[str, ...]
) -> tuple[CardClaim, ...]:
    """The card's claims, each against its own rule.

    :raises ApplicationRefusedError: a claim's kind is outside the
        vocabulary; a non-advisor claim cites evidence the card does
        not declare; an advisor claim lacks its key or its quote, or
        quotes words the chain does not hold.
    """
    declared = set(evidence_refs)
    for claim in claims:
        if claim.kind not in CLAIM_KINDS:
            raise role_refused(
                RoleRefusal.CLAIM_KIND_UNKNOWN,
                f"{claim.kind!r} is not one of {sorted(CLAIM_KINDS)}; a claim"
                " of no kind is a sentence the reader cannot weigh",
            )
        if claim.kind == "advisor":
            if not claim.issue_key or not claim.advisor_quote:
                raise role_refused(
                    RoleRefusal.ADVICE_NOT_IN_THE_CHAIN,
                    "an advisor claim names the chain key and quotes the"
                    " comment; a voice without a source is an invention",
                )
            held = chain_layer.read_comments(context, issue_keys=(claim.issue_key,))
            if not held or not any(claim.advisor_quote in row.comment_text for row in held):
                raise role_refused(
                    RoleRefusal.ADVICE_NOT_IN_THE_CHAIN,
                    "the quote is not the advisor's words in the chain, and"
                    " a card may not put words in the advisor's mouth",
                )
        elif not claim.evidence_ref or claim.evidence_ref not in declared:
            raise role_refused(
                RoleRefusal.CLAIM_WITHOUT_EVIDENCE,
                f"the claim {claim.text!r} cites evidence the card does not"
                " declare, and a claim nothing supports is not a claim",
            )
    return claims


def build_card(
    context: ApplicationContext,
    *,
    spec: AgentRoleSpec,
    target_locator: str,
    issue_type: str,
    severity: str,
    reason: str,
    evidence_refs: tuple[str, ...],
    suggested_next_action: str,
    uncertainty: Uncertainty,
    claims: tuple[CardClaim, ...] = (),
    style_notes: tuple[str, ...] = (),
    rule_refs: tuple[RuleCitation, ...] = (),
    historical_case_refs: tuple[str, ...] = (),
    counterexamples_or_limits: tuple[str, ...] = (),
) -> GuidanceCard:
    """The card, checked: every field the architecture names, none invented.

    :raises ApplicationRefusedError: a required field is empty; the
        evidence list is empty; the severity, a claim's kind, or the
        issue type is outside its vocabulary; a claim cites evidence
        the card does not declare; or an advisor claim quotes words
        the chain does not hold.
    """
    for what, value in (
        ("target locator", target_locator),
        ("reason", reason),
        ("suggested next action", suggested_next_action),
        ("uncertainty statement", uncertainty.what_is_uncertain),
    ):
        if not value.strip():
            raise role_refused(
                RoleRefusal.CARD_FIELD_EMPTY,
                f"the card's {what} is empty, and a card with nothing in it advises nothing",
            )
    if not evidence_refs:
        raise role_refused(
            RoleRefusal.CARD_WITHOUT_EVIDENCE,
            "a card whose evidence list is empty is an opinion wearing a card's clothes",
        )
    if severity not in SEVERITIES:
        raise role_refused(
            RoleRefusal.SEVERITY_UNKNOWN,
            f"{severity!r} is not one of {sorted(SEVERITIES)}",
        )
    if issue_type not in ISSUE_LABELS:
        raise role_refused(
            RoleRefusal.CANDIDATE_ISSUE_TYPE_UNKNOWN,
            f"{issue_type!r} is not one of the closed vocabulary's labels",
        )
    if uncertainty.kind not in UNCERTAINTY_KINDS:
        raise role_refused(
            RoleRefusal.UNCERTAINTY_KIND_UNKNOWN,
            f"{uncertainty.kind!r} is not one of {sorted(UNCERTAINTY_KINDS)}",
        )
    checked = _checked_claims(context, claims=claims, evidence_refs=evidence_refs)
    return GuidanceCard(
        role_id=spec.role_id,
        role_version=spec.role_version,
        target_locator=target_locator,
        issue_type=issue_type,
        severity=severity,
        reason=reason,
        evidence_refs=evidence_refs,
        suggested_next_action=suggested_next_action,
        uncertainty=uncertainty,
        claims=checked,
        style_notes=style_notes,
        rule_refs=rule_refs,
        historical_case_refs=historical_case_refs,
        counterexamples_or_limits=counterexamples_or_limits,
    )


def abstaining_card(
    *,
    spec: AgentRoleSpec,
    issue_type: str,
    what_is_uncertain: str,
    missing: tuple[str, ...],
) -> GuidanceCard:
    """The card a role that cannot answer produces instead of a guess.

    **An abstention is a structured record**: it names the kind —
    ``abstention`` — and it names **what was missing**, because the
    difference between "the system does not know" and "the system is
    broken" is the difference between a product and an outage. An
    abstention that cannot say what it lacks is refused.

    :raises ApplicationRefusedError: the issue type is outside the
        closed vocabulary, or the missing list is empty.
    """
    if issue_type not in ISSUE_LABELS:
        raise role_refused(
            RoleRefusal.CANDIDATE_ISSUE_TYPE_UNKNOWN,
            f"{issue_type!r} is not one of the closed vocabulary's labels",
        )
    if not missing:
        raise role_refused(
            RoleRefusal.ABSTENTION_WITHOUT_A_MISSING,
            "an abstention that cannot say what it lacks is a shrug, not a result",
        )
    return GuidanceCard(
        role_id=spec.role_id,
        role_version=spec.role_version,
        target_locator="",
        issue_type=issue_type,
        severity="minor",
        reason="the material the card needs was not in reach, and the role does not guess",
        evidence_refs=(),
        suggested_next_action="supply what the card names as missing, and ask again",
        uncertainty=Uncertainty(
            kind="abstention",
            what_is_uncertain=what_is_uncertain,
            missing=missing,
        ),
    )
