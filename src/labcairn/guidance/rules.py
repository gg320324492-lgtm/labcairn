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
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from labcairn.application.context import ApplicationContext
from labcairn.application.refusal import guidance_refused
from labcairn.db.models import (
    GuidanceRuleCounterexampleRow,
    GuidanceRuleRow,
    GuidanceRuleSourceRow,
)
from labcairn.guidance.refusals import GuidanceRefusal
from labcairn.papers.labels import ISSUE_LABELS


@dataclass(frozen=True)
class RuleCounterexample:
    """The case where a rule does not hold, as the memory serves it."""

    statement: str
    #: The chain material the counterexample came from, when it has one.
    issue_key: str | None
    recorded_by: str
    recorded_at: datetime


@dataclass(frozen=True)
class GuidanceRule:
    """A mentor's rule as the memory holds it, with its sources and its cases.

    **The counterexamples travel with the rule, not beside it.** The
    work order's acceptance says a counterexample stops the rule being
    served unconditionally, and the mechanism starts here: a caller that
    has a rule has its cases against it, because they came back in the
    same read.
    """

    rule_id: str
    version: int
    issue_type: str
    statement: str
    context: str
    scope: str
    example: str
    state: str
    proposed_by: str
    proposed_at: datetime
    confirmed_by: str | None
    confirmed_at: datetime | None
    resolution_reason: str | None
    #: The chain material the rule was learned from, by the chain's own
    #: key. **At least one: a rule without a source is not a rule.**
    sources: tuple[str, ...]
    #: The cases against the rule. **Possibly empty, never optional** —
    #: an empty tuple says the memory holds none, not that it did not look.
    counterexamples: tuple[RuleCounterexample, ...]


def _rule_id(issue_type: str, statement: str, proposed_by: str, now: datetime) -> str:
    """Caller-visible identity, derived from what the rule says and who said it."""
    material = f"{issue_type}|{statement}|{proposed_by}|{now.isoformat()}"
    return f"rule-{hashlib.sha256(material.encode('utf-8')).hexdigest()[:16]}"


def _latest(session: Session, rule_id: str) -> GuidanceRuleRow:
    """The highest version of the rule, or the refusal that says it is not there."""
    row = session.scalar(
        select(GuidanceRuleRow)
        .where(GuidanceRuleRow.rule_id == rule_id)
        .order_by(GuidanceRuleRow.version.desc())
        .limit(1)
    )
    if row is None:
        raise guidance_refused(
            GuidanceRefusal.RULE_NOT_FOUND,
            f"no rule carries the id {rule_id!r}",
        )
    return row


def _row_to_rule(session: Session, row: GuidanceRuleRow) -> GuidanceRule:
    """One row, its sources and its cases, as the memory serves them."""
    source_keys = tuple(
        session.scalars(
            select(GuidanceRuleSourceRow.issue_key)
            .where(
                GuidanceRuleSourceRow.rule_id == row.rule_id,
                GuidanceRuleSourceRow.version == row.version,
            )
            .order_by(GuidanceRuleSourceRow.issue_key)
        )
    )
    cases = tuple(
        RuleCounterexample(
            statement=case.statement,
            issue_key=case.issue_key,
            recorded_by=case.recorded_by,
            recorded_at=case.recorded_at,
        )
        for case in session.scalars(
            select(GuidanceRuleCounterexampleRow)
            .where(
                GuidanceRuleCounterexampleRow.rule_id == row.rule_id,
                GuidanceRuleCounterexampleRow.version == row.version,
            )
            .order_by(GuidanceRuleCounterexampleRow.id)
        )
    )
    return GuidanceRule(
        rule_id=row.rule_id,
        version=row.version,
        issue_type=row.issue_type,
        statement=row.statement,
        context=row.context,
        scope=row.scope,
        example=row.example,
        state=row.state,
        proposed_by=row.proposed_by,
        proposed_at=row.proposed_at,
        confirmed_by=row.confirmed_by,
        confirmed_at=row.confirmed_at,
        resolution_reason=row.resolution_reason,
        sources=source_keys,
        counterexamples=cases,
    )


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


def _insert_candidate(
    session: Session,
    *,
    rule_id: str,
    version: int,
    issue_type: str,
    statement: str,
    rule_context: str,
    scope: str,
    example: str,
    proposed_by: str,
    sources: Sequence[str],
    now: datetime,
) -> GuidanceRuleRow:
    """One candidate row and its source bindings, written and flushed."""
    row = GuidanceRuleRow(
        rule_id=rule_id,
        version=version,
        issue_type=issue_type,
        statement=statement,
        context=rule_context,
        scope=scope,
        example=example,
        state="candidate",
        proposed_by=proposed_by,
        proposed_at=now,
    )
    session.add(row)
    session.add_all(
        GuidanceRuleSourceRow(rule_id=rule_id, version=version, issue_key=key) for key in sources
    )
    session.flush()
    return row


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
    session = context.store.session
    issue_type, statement, rule_context, scope, example, proposed_by, sources = _validated_fields(
        issue_type=issue_type,
        statement=statement,
        rule_context=rule_context,
        scope=scope,
        example=example,
        proposed_by=proposed_by,
        sources=sources,
    )
    rule_id = _rule_id(issue_type, statement, proposed_by, now)
    row = _insert_candidate(
        session,
        rule_id=rule_id,
        version=1,
        issue_type=issue_type,
        statement=statement,
        rule_context=rule_context,
        scope=scope,
        example=example,
        proposed_by=proposed_by,
        sources=sources,
        now=now,
    )
    return _row_to_rule(session, row)


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

    :raises ApplicationRefusedError: the rule is not there; the confirmer
        is the proposer; the rule is not a candidate.
    """
    session = context.store.session
    row = _latest(session, rule_id)
    if confirmed_by == row.proposed_by:
        raise guidance_refused(
            GuidanceRefusal.CONFIRMER_IS_PROPOSER,
            f"the rule was proposed by {row.proposed_by!r}, and its proposer"
            " cannot be the one who confirms it",
        )
    if row.state != "candidate":
        raise guidance_refused(
            GuidanceRefusal.TRANSITION_NOT_POSSIBLE,
            f"a rule in state {row.state!r} cannot be confirmed; only a candidate can",
        )
    row.state = "confirmed"
    row.confirmed_by = confirmed_by
    row.confirmed_at = now
    session.flush()
    return _row_to_rule(session, row)


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
    session = context.store.session
    row = _latest(session, rule_id)
    if not reason.strip():
        raise guidance_refused(
            GuidanceRefusal.RESOLUTION_WITHOUT_REASON,
            "a dispute without a reason is a shrug, and the memory does not record shrugs",
        )
    if row.state == "withdrawn":
        raise guidance_refused(
            GuidanceRefusal.TRANSITION_NOT_POSSIBLE,
            "a withdrawn rule cannot be disputed; propose a new version instead",
        )
    row.state = "disputed"
    row.resolution_reason = reason
    row.confirmed_at = row.confirmed_at if row.confirmed_at is not None else now
    row.confirmed_by = row.confirmed_by or disputed_by
    session.flush()
    return _row_to_rule(session, row)


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
    session = context.store.session
    row = _latest(session, rule_id)
    if not reason.strip():
        raise guidance_refused(
            GuidanceRefusal.RESOLUTION_WITHOUT_REASON,
            "a retraction without a reason is a shrug, and the memory does not record shrugs",
        )
    if row.state == "withdrawn":
        raise guidance_refused(
            GuidanceRefusal.TRANSITION_NOT_POSSIBLE,
            f"the rule is already withdrawn, for {row.resolution_reason!r}",
        )
    row.state = "withdrawn"
    row.resolution_reason = reason
    session.flush()
    return _row_to_rule(session, row)


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
    session = context.store.session
    old = _latest(session, rule_id)
    issue_type, statement, rule_context, scope, example, proposed_by, sources = _validated_fields(
        issue_type=issue_type,
        statement=statement,
        rule_context=rule_context,
        scope=scope,
        example=example,
        proposed_by=proposed_by,
        sources=sources,
    )
    row = _insert_candidate(
        session,
        rule_id=rule_id,
        version=old.version + 1,
        issue_type=issue_type,
        statement=statement,
        rule_context=rule_context,
        scope=scope,
        example=example,
        proposed_by=proposed_by,
        sources=sources,
        now=now,
    )
    return _row_to_rule(session, row)


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
    session = context.store.session
    row = _latest(session, rule_id)
    if not statement.strip() or not recorded_by.strip():
        raise guidance_refused(
            GuidanceRefusal.COUNTEREXAMPLE_EMPTY,
            "a counterexample with no case in it challenges nothing",
        )
    if issue_key is not None and not issue_key.strip():
        issue_key = None
    session.add(
        GuidanceRuleCounterexampleRow(
            rule_id=row.rule_id,
            version=row.version,
            statement=statement,
            issue_key=issue_key,
            recorded_by=recorded_by,
            recorded_at=now,
        )
    )
    session.flush()
    return _row_to_rule(session, row)


def read_rule(context: ApplicationContext, *, rule_id: str) -> GuidanceRule:
    """The rule, at its highest version, with its sources and its cases.

    :raises ApplicationRefusedError: the rule is not there.
    """
    session = context.store.session
    return _row_to_rule(session, _latest(session, rule_id))


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
