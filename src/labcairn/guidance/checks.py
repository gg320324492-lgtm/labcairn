"""The checks that decide the rules: a decidable question, and its criterion.

**What this module is.** The memory holds rules — what the advisor
demands, recovered from where their hand went — and it now holds
**checks**: the questions a reader can run against a piece of a manuscript
and answer yes or no. **The binding between the two is what this module
owns**, because without it the group's checklist and the advisor's
distilled rules are two documents that happen to use the same words.

**What a check is, and why it is two fields.** A check is **decidable**:
a reader must be able to run it and get yes or no. Decidability takes two
things — **the question** the reader asks, and **the pass criterion**,
the condition under which the answer is yes. **They are different
things**, and they are kept apart: a question with no criterion cannot be
answered, and a criterion with no question decides nothing. A checklist
that gives only a question leaves the reader to guess what would pass; one
that gives only a criterion leaves them to guess what to run it on. **So
the two are two fields, and neither may be empty.**

**Where a check lives.** Beside the rules it decides, in the rule
memory's own store — **and not in the chain**. The chain is the mentor's
material: a comment, a change, a judgement. **A checklist written down in
advance is not the mentor's material**, and putting it in the chain would
say it was learned from the advisor's mouth when it was not. **And it is
not a counterexample either**: a counterexample is a case *against* a
rule, and a check is a test *for* one. The two answer different
questions, so they are stored apart.

**How a rule names a check, and what the binding is.** The binding is a
row of its own, ``guidance_rule_checks``, and it names **the version of
the rule** as well as the check. **A rule is a versioned row** — a new
statement is a new version, and :func:`~labcairn.guidance.rules.supersede_rule`
inserts the next version as a fresh candidate — so **the check that
decides version 1's words is not automatically the check that decides
version 2's**. The binding therefore belongs to the version, and a new
version starts with none: **a rewording is not a confirmation, and it is
not a carry-over.**

**And a binding is in force only while both of its ends are.** A rule
that is withdrawn names no check, and a withdrawn check is named by no
rule. **That is what makes "a check no rule names" answerable** — a check
nobody's rule leans on is a norm nobody uses, and the memory can say so
because the bindings that were released are gone.

**May two rules share one check? Yes.** The group's checklist is
generic, and the same item may decide more than one rule; a check that
could be named by only one rule would have to be written once per rule,
and the memory would hold two different questions with the same answer.
**The binding is many-to-many, and one rule names one check once.**

**Who may put a check there.** **What a model proposes, a person
confirms** — the same rule the memory applies to a rule, and the same
reason: a check is a norm, and a norm that reached the record without a
person reading it would be applied to papers nobody looked at. So a check
is proposed as a ``candidate``, **only a second reader confirms it** (the
proposer may not), and **a rule may name only a confirmed check**.

**What this module does not do.** It does not run a check against a
manuscript, and it does not judge whether the manuscript passes: **a
check is decidable, and deciding it is the reader's work.** It does not
put a check into the chain, and it does not decide which check a rule
should name — the binding is a person's claim about a pair of things, and
the person who makes it is the one who is answerable for it.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Final

from labcairn.application import guidance as guidance_layer
from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import guidance_refused
from labcairn.guidance.models import GuidanceCheck, GuidanceRule
from labcairn.guidance.refusals import GuidanceRefusal


def _check_id(question: str, pass_criterion: str, proposed_by: str, now: datetime) -> str:
    """Caller-visible identity, derived from what the check says and who said it."""
    material = f"{question}|{pass_criterion}|{proposed_by}|{now.isoformat()}"
    return f"check-{hashlib.sha256(material.encode('utf-8')).hexdigest()[:16]}"


def _validated_fields(
    *, question: str, pass_criterion: str, proposed_by: str
) -> tuple[str, str, str]:
    """The fields a check may carry, or the refusal that names what is missing.

    **The question and the criterion are both required, and they are
    required of each other.** A check that names what to ask but not what
    would pass is a question a reader answers by taste, and a check that
    names what would pass but not what to ask is a criterion nobody can
    apply. **So the empty one is refused by name**, and the reason says
    which of the two it was.
    """
    fields = {
        "question": question,
        "pass_criterion": pass_criterion,
        "proposed_by": proposed_by,
    }
    empty = sorted(name for name, value in fields.items() if not value.strip())
    if empty:
        raise guidance_refused(
            GuidanceRefusal.CHECK_FIELD_EMPTY,
            f"a check carries every one of its fields, and {empty} is empty",
        )
    return question, pass_criterion, proposed_by


def propose_check(
    context: ApplicationContext,
    *,
    question: str,
    pass_criterion: str,
    proposed_by: str,
    now: datetime,
) -> GuidanceCheck:
    """Propose a check, as a candidate.

    **A candidate is what this returns, whatever wrote it.** A person
    writing the group's checklist down and a distillation run proposing
    one land here the same way, and neither is confirmed until a second
    reader confirms it — **what a model proposes, a person confirms**, and
    a rule may name only a confirmed check.

    :raises ApplicationRefusedError: the question, the pass criterion or
        the proposer is empty.
    """
    question, pass_criterion, proposed_by = _validated_fields(
        question=question,
        pass_criterion=pass_criterion,
        proposed_by=proposed_by,
    )
    return guidance_layer.write_guidance_check(
        context,
        guidance_layer.CheckDraft(
            check_id=_check_id(question, pass_criterion, proposed_by, now),
            question=question,
            pass_criterion=pass_criterion,
            proposed_by=proposed_by,
            proposed_at=now,
        ),
    )


def confirm_check(
    context: ApplicationContext,
    *,
    check_id: str,
    confirmed_by: str,
    now: datetime,
) -> GuidanceCheck:
    """Confirm a check — as a **second reader**.

    **The refusal this function exists for is one line long**: the
    proposer cannot confirm their own check. One person reading twice is
    one person reading once with extra steps, and a check's confirmer is
    that check's arbiter.

    **And the closed state machine is the layer's.** Whether a check may
    be confirmed is a fact about the row, so the transition is the layer's
    to refuse and this function asks it rather than restating it.

    :raises ApplicationRefusedError: the check is not there; the confirmer
        is the proposer; the check is not a candidate.
    """
    check = guidance_layer.read_guidance_check(context, check_id=check_id)
    if confirmed_by == check.proposed_by:
        raise guidance_refused(
            GuidanceRefusal.CONFIRMER_IS_PROPOSER,
            f"the check was proposed by {check.proposed_by!r}, and its proposer"
            " cannot be the one who confirms it",
        )
    return guidance_layer.write_guidance_check_confirmation(
        context,
        check_id=check_id,
        confirmed_by=confirmed_by,
        confirmed_at=now,
    )


def withdraw_check(
    context: ApplicationContext,
    *,
    check_id: str,
    reason: str,
    now: datetime,
) -> GuidanceCheck:
    """Withdraw a check, with the reason the record will carry.

    **The reason is not bureaucracy**, for the reason a rule's retraction
    carries one: a withdrawn check is how the memory says *this stopped
    being the test*, and a retraction that says only "no" is a retraction
    nobody can learn from.

    **And the bindings go with it.** A check that is withdrawn decides
    nothing, so the rules that named it are unbound — and the check stays,
    for a rule that is still in force to name.

    :raises ApplicationRefusedError: the check is not there; the reason is
        empty; the check is already withdrawn.
    """
    guidance_layer.read_guidance_check(context, check_id=check_id)
    if not reason.strip():
        raise guidance_refused(
            GuidanceRefusal.RESOLUTION_WITHOUT_REASON,
            "a retraction without a reason is a shrug, and the memory does not record shrugs",
        )
    return guidance_layer.write_guidance_check_withdrawal(
        context,
        check_id=check_id,
        reason=reason,
    )


def bind_check(context: ApplicationContext, *, rule_id: str, check_id: str) -> GuidanceRule:
    """Name the check as the one that decides this rule.

    **The binding is made at the rule's highest version, and the check
    must be one a person has confirmed.** A candidate is a proposal, and a
    rule that leans on a proposal leans on nothing that has been decided.

    **And a withdrawn rule names no check**, so a binding to one is
    refused: the rule is out of force, and there is nothing left for the
    check to decide.

    :raises ApplicationRefusedError: the rule is not there; the check is
        not there; the check is not confirmed; the rule is withdrawn.
    """
    return guidance_layer.write_guidance_rule_check(
        context,
        rule_id=rule_id,
        check_id=check_id,
    )


def read_check(context: ApplicationContext, *, check_id: str) -> GuidanceCheck:
    """The check, as the memory holds it.

    :raises ApplicationRefusedError: the check is not there.
    """
    return guidance_layer.read_guidance_check(context, check_id=check_id)


def read_checks(context: ApplicationContext) -> tuple[GuidanceCheck, ...]:
    """Every check the memory holds, in the order the table holds them."""
    return guidance_layer.read_guidance_checks(context)


def read_rule_checks(context: ApplicationContext, *, rule_id: str) -> tuple[GuidanceCheck, ...]:
    """The checks that decide this rule, at its highest version.

    :raises ApplicationRefusedError: the rule is not there.
    """
    return guidance_layer.read_guidance_rule_checks(context, rule_id=rule_id)


def read_check_rules(context: ApplicationContext, *, check_id: str) -> tuple[GuidanceRule, ...]:
    """The rules the check decides, at each rule's highest version.

    **This is the question the binding was made for**: a reader holding a
    checklist item asks which rule it is checking.

    :raises ApplicationRefusedError: the check is not there.
    """
    return guidance_layer.read_guidance_check_rules(context, check_id=check_id)


#: The module's own surface, for ``from labcairn.guidance import checks``.
__all__: Final = [
    "GuidanceCheck",
    "GuidanceRule",
    "bind_check",
    "confirm_check",
    "propose_check",
    "read_check",
    "read_check_rules",
    "read_checks",
    "read_rule_checks",
    "withdraw_check",
]
