"""The guidance memory: rules that carry their sources, and the cases against them.

LC-P2-11. A mentor's rule is worth carrying **because it can be traced to
the moment it was learned** — a comment, a revision, a response, an
outcome. This module is the rule record's lifecycle and nothing else: the
retrieval over the memory is :mod:`labcairn.guidance.retrieval` (T02), and
the distillation that proposes a candidate is T01's other half.

**The state machine is closed** (ADR-0016 D8): a rule is proposed as a
``candidate``, and only a person moves it — to ``confirmed`` by a
**second reader** (the owner's rule of 2026-10-31: whoever proposed a
rule cannot be the one who confirms it), to ``disputed`` by a case
against it, or to ``withdrawn`` by a retraction that carries its reason.
**And a new statement is a new row**: :func:`supersede_rule` inserts the
next version as a fresh candidate, and the old version keeps the state
it had, because a memory that rewrites its past is not a memory.

**The rows are reached through the application layer.** Every read and
every write of ``guidance_rules``, ``guidance_rule_sources`` and
``guidance_rule_counterexamples`` goes through
:mod:`labcairn.application.guidance`, so the memory is reached in one
place and a guard applied there reaches every caller — the retrieval, the
distillation and this lifecycle alike. **The rules about words and people
stay here**: the closed vocabulary of problems, the fields that may not be
empty, the source a rule must name, the second reader who may not be the
proposer, and the reason a dispute or a retraction must carry. The layer
holds the transitions and the rows; this module holds what may be said.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import datetime
from typing import Final

from labcairn.application import guidance as guidance_layer
from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import guidance_refused
from labcairn.guidance.models import GuidanceRule, RuleCounterexample
from labcairn.guidance.refusals import GuidanceRefusal
from labcairn.papers.labels import ISSUE_LABELS


def _rule_id(issue_type: str, statement: str, proposed_by: str, now: datetime) -> str:
    """Caller-visible identity, derived from what the rule says and who said it."""
    material = f"{issue_type}|{statement}|{proposed_by}|{now.isoformat()}"
    return f"rule-{hashlib.sha256(material.encode('utf-8')).hexdigest()[:16]}"


def _validated_fields(
    *,
    issue_type: str,
    statement: str,
    rule_context: str,
    scope: str,
    example: str,
    proposed_by: str,
    sources: Sequence[str],
) -> tuple[str, str, str, str, str, str, tuple[str, ...]]:
    """The fields a rule may carry, or the refusal that names what is missing.

    **The API refuses what the schema would refuse, and says which
    requirement failed** — the vocabulary, the four fields and the source
    binding are checked here so a caller learns the reason, and the
    database refuses the same rows behind it.
    """
    if issue_type not in ISSUE_LABELS:
        raise guidance_refused(
            GuidanceRefusal.PROBLEM_OUTSIDE_VOCABULARY,
            f"{issue_type!r} is not one of the closed vocabulary's labels",
        )
    fields = {
        "statement": statement,
        "context": rule_context,
        "scope": scope,
        "example": example,
        "proposed_by": proposed_by,
    }
    empty = sorted(name for name, value in fields.items() if not value.strip())
    if empty:
        raise guidance_refused(
            GuidanceRefusal.RULE_FIELD_EMPTY,
            f"a rule carries every one of its fields, and {empty} is empty",
        )
    if not sources or any(not key.strip() for key in sources):
        raise guidance_refused(
            GuidanceRefusal.RULE_WITHOUT_SOURCE,
            "a rule without a source is not a rule; name the chain material it was learned from",
        )
    return (
        issue_type,
        statement,
        rule_context,
        scope,
        example,
        proposed_by,
        tuple(sorted(set(sources))),
    )


def propose_rule(
    context: ApplicationContext,
    *,
    issue_type: str,
    statement: str,
    rule_context: str,
    scope: str,
    example: str,
    sources: Sequence[str],
    proposed_by: str,
    now: datetime,
) -> GuidanceRule:
    """Propose a rule from real chain material, as a candidate.

    **A candidate is what this returns, whatever wrote it.** A person
    proposing from a history they just read and a distillation run
    proposing from a corpus land here the same way, and neither is
    confirmed until a second reader confirms it (ADR-0016 D8).

    :raises ApplicationRefusedError: the problem is outside the closed
        vocabulary; a required field is empty; the rule names no chain
        material.
    """
    issue_type, statement, rule_context, scope, example, proposed_by, sources = _validated_fields(
        issue_type=issue_type,
        statement=statement,
        rule_context=rule_context,
        scope=scope,
        example=example,
        proposed_by=proposed_by,
        sources=sources,
    )
    return guidance_layer.write_guidance_rule_version(
        context,
        guidance_layer.RuleDraft(
            rule_id=_rule_id(issue_type, statement, proposed_by, now),
            version=1,
            issue_type=issue_type,
            statement=statement,
            rule_context=rule_context,
            scope=scope,
            example=example,
            proposed_by=proposed_by,
            sources=sources,
            proposed_at=now,
        ),
    )


def confirm_rule(
    context: ApplicationContext,
    *,
    rule_id: str,
    confirmed_by: str,
    now: datetime,
) -> GuidanceRule:
    """Confirm a candidate — as a **second reader**.

    **The refusal this function exists for is one line long**: the
    proposer cannot confirm their own rule. The owner's rule of
    2026-10-31 was written for the gold set's readings — *the arbiter
    must be the third reader* — and a rule's confirmer is that rule's
    arbiter: one person reading twice is one person reading once with
    extra steps.

    **And the closed state machine is the layer's.** Whether a rule may
    be confirmed is a fact about the row, so the transition that moves a
    rule out of ``candidate`` is the layer's to refuse and this function
    asks it rather than restating it.

    :raises ApplicationRefusedError: the rule is not there; the confirmer
        is the proposer; the rule is not a candidate.
    """
    rule = guidance_layer.read_guidance_rule(context, rule_id=rule_id)
    if confirmed_by == rule.proposed_by:
        raise guidance_refused(
            GuidanceRefusal.CONFIRMER_IS_PROPOSER,
            f"the rule was proposed by {rule.proposed_by!r}, and its proposer"
            " cannot be the one who confirms it",
        )
    return guidance_layer.write_guidance_rule_confirmation(
        context,
        rule_id=rule_id,
        confirmed_by=confirmed_by,
        confirmed_at=now,
    )


def dispute_rule(
    context: ApplicationContext,
    *,
    rule_id: str,
    reason: str,
    disputed_by: str,
    now: datetime,
) -> GuidanceRule:
    """Mark a rule ``disputed``: a case against it stands, and the record says.

    **Disputing is not retracting.** A disputed rule stays in the memory
    and is served *with* the case against it — T04's display — because a
    rule challenged once is a rule a reader may still judge. The
    retracting happens in :func:`withdraw_rule`, and it is a different
    decision.

    :raises ApplicationRefusedError: the rule is not there; the reason is
        empty; the rule is already withdrawn.
    """
    guidance_layer.read_guidance_rule(context, rule_id=rule_id)
    if not reason.strip():
        raise guidance_refused(
            GuidanceRefusal.RESOLUTION_WITHOUT_REASON,
            "a dispute without a reason is a shrug, and the memory does not record shrugs",
        )
    return guidance_layer.write_guidance_rule_resolution(
        context,
        rule_id=rule_id,
        reason=reason,
        disputed_by=disputed_by,
        now=now,
    )


def withdraw_rule(
    context: ApplicationContext,
    *,
    rule_id: str,
    reason: str,
    now: datetime,
) -> GuidanceRule:
    """Withdraw a rule, with the reason the record will carry.

    **The reason is not bureaucracy.** A withdrawn rule is how the memory
    says *this stopped being true*, and a retraction that says only "no"
    is a retraction nobody can learn from.

    :raises ApplicationRefusedError: the rule is not there; the reason is
        empty; the rule is already withdrawn.
    """
    guidance_layer.read_guidance_rule(context, rule_id=rule_id)
    if not reason.strip():
        raise guidance_refused(
            GuidanceRefusal.RESOLUTION_WITHOUT_REASON,
            "a retraction without a reason is a shrug, and the memory does not record shrugs",
        )
    return guidance_layer.write_guidance_rule_withdrawal(
        context,
        rule_id=rule_id,
        reason=reason,
    )


def supersede_rule(
    context: ApplicationContext,
    *,
    rule_id: str,
    statement: str,
    rule_context: str,
    scope: str,
    example: str,
    issue_type: str,
    sources: Sequence[str],
    proposed_by: str,
    now: datetime,
) -> GuidanceRule:
    """Insert the rule's next version, as a fresh candidate.

    **The memory does not edit its past.** The old version keeps the
    state it had, the sources and the counterexamples stay with the
    versions they belong to, and the new version starts as a candidate
    that needs a second reader like any other — **a rewording is not a
    confirmation**.

    :raises ApplicationRefusedError: whatever :func:`propose_rule`
        refuses, or the rule is not there.
    """
    old = guidance_layer.read_guidance_rule(context, rule_id=rule_id)
    issue_type, statement, rule_context, scope, example, proposed_by, sources = _validated_fields(
        issue_type=issue_type,
        statement=statement,
        rule_context=rule_context,
        scope=scope,
        example=example,
        proposed_by=proposed_by,
        sources=sources,
    )
    return guidance_layer.write_guidance_rule_version(
        context,
        guidance_layer.RuleDraft(
            rule_id=rule_id,
            version=old.version + 1,
            issue_type=issue_type,
            statement=statement,
            rule_context=rule_context,
            scope=scope,
            example=example,
            proposed_by=proposed_by,
            sources=sources,
            proposed_at=now,
        ),
    )


def record_counterexample(
    context: ApplicationContext,
    *,
    rule_id: str,
    statement: str,
    recorded_by: str,
    now: datetime,
    issue_key: str | None = None,
) -> GuidanceRule:
    """Record the case where a rule does not hold.

    **Recording a case is not disputing the rule.** The case travels
    with the rule from now on — every serve carries it — and whether the
    rule moves to ``disputed`` is a reader's decision, not this
    function's.

    :raises ApplicationRefusedError: the rule is not there; the case is
        empty.
    """
    guidance_layer.read_guidance_rule(context, rule_id=rule_id)
    if not statement.strip() or not recorded_by.strip():
        raise guidance_refused(
            GuidanceRefusal.COUNTEREXAMPLE_EMPTY,
            "a counterexample with no case in it challenges nothing",
        )
    if issue_key is not None and not issue_key.strip():
        issue_key = None
    return guidance_layer.write_guidance_counterexample(
        context,
        rule_id=rule_id,
        statement=statement,
        recorded_by=recorded_by,
        recorded_at=now,
        issue_key=issue_key,
    )


def read_rule(context: ApplicationContext, *, rule_id: str) -> GuidanceRule:
    """The rule, at its highest version, with its sources and its cases.

    :raises ApplicationRefusedError: the rule is not there.
    """
    return guidance_layer.read_guidance_rule(context, rule_id=rule_id)


#: The module's own surface, for ``from labcairn.guidance import rules``.
__all__: Final = [
    "GuidanceRefusal",
    "GuidanceRule",
    "RuleCounterexample",
    "confirm_rule",
    "dispute_rule",
    "propose_rule",
    "read_rule",
    "record_counterexample",
    "supersede_rule",
    "withdraw_rule",
]
