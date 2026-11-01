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

**And a card carries an address of its own** (the owner's decision of
2026-11-01). The chain's comments live in the DOCX's
``word/comments.xml`` part, and the ledger's own source anchors name the
document's *body* paragraphs — so **there is no ledger address a
proposal about a chain comment could point at**. The card's address is
therefore the card's own: it names the comment the card is about, in the
chain's own names, and it is **minted by the product** from what the
card already holds. A caller cannot supply it; it is never a body
address the ledger cannot resolve; and it is never the comment's own
locator borrowed and worn.

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

#: The namespace the card's own address lives in. **It is not the
#: ledger's.** The ledger's addresses are ``locator_key``s and they name
#: body paragraphs; a card about a comment in ``word/comments.xml`` has
#: no such place, so the card's address is spelled in a namespace of its
#: own and can never be mistaken for a source anchor.
CARD_ADDRESS_PREFIX: Final[str] = "card:"

#: The spelling of an evidence reference that names a comment in the
#: chain. **The card's address is not this**: the reference is what the
#: card's evidence says, and the address is where the card itself is.
CHAIN_REFERENCE_PREFIX: Final[str] = "chain:"


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
class CardAddress:
    """The card's own address: the comment the card is about, named three ways.

    **Three pieces, and each answers a question of its own.**

    - ``issue_key`` — *what* the card is about. It is the chain's own key
      for the issue, and it is the key the card's evidence already
      carries, so the address and the evidence cannot disagree about the
      subject.
    - ``feedback_id`` — *which* comment. One issue key can carry several
      comments, and an address that could be two addresses is not an
      address.
    - ``version_id`` — *which round*. The advice is against a manuscript
      state, and a later state is a different manuscript.

    **And it is not a source address.** The ledger's own addresses are
    ``locator_key``s that name body paragraphs, and the advisor's words
    are in ``word/comments.xml``, which the ledger does not index. **A
    card that claimed a body address would be pointing at a place the
    ledger cannot resolve**, and a card that claimed the comment's own
    locator would be wearing the comment's address rather than carrying
    one of its own. So the card's address is spelled in its own
    namespace and is made of names the chain holds.
    """

    issue_key: str
    feedback_id: str
    version_id: str

    def render(self) -> str:
        """The address as the card carries it.

        **One spelling, and it is this one.** The card's address is not
        the ledger's, so it does not borrow the ledger's spelling — and
        the parts are the chain's own names, so a reader of the address
        can ask the chain what each of them is.
        """
        return f"{CARD_ADDRESS_PREFIX}{self.issue_key}@{self.feedback_id}@{self.version_id}"


@dataclass(frozen=True)
class _Subject:
    """The comment the card is about, as the card's own fields name it.

    **The issue key comes from the evidence, and the quotes come from the
    advisor claims.** A card says what it is about by declaring the chain
    reference it rests on; and when one issue key holds several comments,
    the words the card quotes are what single one of them out.
    """

    issue_key: str
    quotes: tuple[str, ...]


def _the_subject(evidence_refs: tuple[str, ...], claims: tuple[CardClaim, ...]) -> _Subject:
    """The comment the card is about, read off the card's own fields.

    :raises ApplicationRefusedError: the evidence names no comment in
        the chain, or names more than one, and the card's own quotes do
        not say which one it is about.
    """
    keys = [
        ref[len(CHAIN_REFERENCE_PREFIX) :]
        for ref in evidence_refs
        if ref.startswith(CHAIN_REFERENCE_PREFIX)
    ]
    if not keys:
        raise role_refused(
            RoleRefusal.CARD_WITHOUT_AN_ADDRESS,
            "the card's evidence names no comment in the chain, so the card has"
            " no address of its own; a card nobody can find advises nobody",
        )
    distinct = sorted(set(keys))
    if len(distinct) > 1:
        raise role_refused(
            RoleRefusal.CARD_ADDRESS_AMBIGUOUS,
            f"the card's evidence names {distinct!r}, and the card does not say"
            " which comment it is about; an address that could be two addresses"
            " is not an address",
        )
    quotes = tuple(
        claim.advisor_quote
        for claim in claims
        if claim.kind == "advisor" and claim.issue_key == distinct[0] and claim.advisor_quote
    )
    return _Subject(issue_key=distinct[0], quotes=quotes)


def the_card_address(
    context: ApplicationContext,
    *,
    evidence_refs: tuple[str, ...],
    claims: tuple[CardClaim, ...] = (),
) -> CardAddress:
    """The address the product mints for a card with this evidence.

    **Read from the chain, and from nothing else.** The comment is found
    by the issue key the card's evidence names; and when the chain holds
    several comments under that key — a recurrence is a fact about two
    versions, not one — **the card's own quoted words say which one it
    is about**.

    **One entry point, and both the card and its review come through
    it.** A card's address and the address the review expects are
    therefore the same address, minted the same way, and they cannot
    disagree because they were minted differently.

    :raises ApplicationRefusedError: the evidence names no comment in
        the chain, or names more than one; the chain holds no comment
        under the key, or holds several and the card's quotes do not
        single one out.
    """
    subject = _the_subject(evidence_refs, claims)
    held = chain_layer.read_comments(context, issue_keys=(subject.issue_key,))
    if not held:
        raise role_refused(
            RoleRefusal.COMMENT_NOT_IN_THE_CHAIN,
            f"the chain holds no comment under the key {subject.issue_key!r}, and a"
            " card about a comment that is not there is about nothing",
        )
    if len(held) > 1:
        matched = tuple(
            row for row in held if any(quote in row.comment_text for quote in subject.quotes)
        )
        if len(matched) != 1:
            raise role_refused(
                RoleRefusal.CARD_ADDRESS_AMBIGUOUS,
                f"the chain holds {len(held)} comments under the key"
                f" {subject.issue_key!r}, and the card does not say which one it is"
                " about; an address that could be two addresses is not an address",
            )
        held = matched
    row = held[0]
    return CardAddress(
        issue_key=subject.issue_key,
        feedback_id=row.feedback_id,
        version_id=row.version_id,
    )


@dataclass(frozen=True)
class GuidanceCard(RoleOutput):
    """Role B's output: the diagnosis, the evidence, the limits, the step."""

    #: **The card's own address**, minted by the product from the comment
    #: the card's evidence names. It is not a place in the manuscript and
    #: not a row of the ledger's: it says **where the advice came from**,
    #: so a person settling the proposal can find the comment behind it.
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

    **And the card's address is minted here, so a caller cannot supply
    it.** There is no ``target_locator`` parameter to fill in: the address
    is read from the chain by :func:`the_card_address`, from the comment
    the card's own evidence names. A caller that could write the address
    could point the card at a comment it is not about, and an address a
    model chose is not a place a person can check.

    :raises ApplicationRefusedError: a required field is empty; the
        evidence list is empty; the evidence names no comment in the
        chain, or more than one; the chain holds no comment under the
        key, or holds several and the card's quotes do not single one
        out; the severity, a claim's kind, or the issue type is outside
        its vocabulary; a claim cites evidence the card does not declare;
        or an advisor claim quotes words the chain does not hold.
    """
    for what, value in (
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
    address = the_card_address(context, evidence_refs=evidence_refs, claims=checked)
    return GuidanceCard(
        role_id=spec.role_id,
        role_version=spec.role_version,
        target_locator=address.render(),
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

    **And it carries no address.** The address is minted from the
    comment the card's evidence names, and an abstention declares no
    evidence — it says what was missing instead. So the empty address
    here is the honest reading, and not a card that points nowhere.

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
